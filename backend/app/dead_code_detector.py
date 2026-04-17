"""Dead code detector – Week 2 module.

Responsibilities:
- Build a call graph from parsed functions and call sites.
- Find functions defined but never called (primary suspects).
- Scan for TODO/FIXME/HACK comments, commented-out code blocks,
  and old feature flags.
"""

from __future__ import annotations

import re
from pathlib import Path

import networkx as nx

from app.ast_parser import ParsedFile, parse_file
from app.git_explorer import GitExplorer
from app.models import SuspectFunction

# Functions whose names match these patterns are never flagged.
_EXCLUDE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^__\w+__$"),   # dunder methods
    re.compile(r"^test_"),       # pytest tests
    re.compile(r"^main$"),       # entry points
]

# Regex for comment smells near function definitions
_COMMENT_SMELL_RE = re.compile(
    r"(?:#\s*(?:TODO|FIXME|HACK)\b.*\bdef\s+\w+)|(?:^\s*#\s*def\s+\w+)",
    re.IGNORECASE | re.MULTILINE,
)


class DeadCodeDetector:
    """Analyse a repository to find functions that may be dead code."""

    def __init__(self, repo_path: str) -> None:
        self._explorer = GitExplorer(repo_path)
        self._repo_root = self._explorer.root
        self._py_files = self._collect_python_files()
        self._parsed: list[ParsedFile] = []
        self._graph: nx.DiGraph | None = None

    # ---- public API -------------------------------------------------------

    def find_suspects(self) -> list[SuspectFunction]:
        """Return all suspected dead-code functions."""
        self._ensure_graph()
        suspects: list[SuspectFunction] = []
        suspects.extend(self._uncalled_functions())
        suspects.extend(self._comment_smells())
        return suspects

    def get_call_graph_dict(self) -> dict[str, list[str]]:
        """Return the call graph as an adjacency dict ``{node: [neighbours]}``."""
        self._ensure_graph()
        assert self._graph is not None
        return {
            node: sorted(self._graph.successors(node))
            for node in sorted(self._graph.nodes)
        }

    # ---- private helpers --------------------------------------------------

    def _collect_python_files(self) -> list[str]:
        """Return absolute paths for all tracked ``.py`` files in the repo."""
        tracked = self._explorer.repo.git.ls_files().splitlines()
        py_files: list[str] = []
        for rel in tracked:
            if rel.endswith(".py"):
                abs_path = str(self._repo_root / rel)
                if Path(abs_path).is_file():
                    py_files.append(abs_path)
        return py_files

    def _ensure_graph(self) -> None:
        """Parse all files and build the call graph if not already done."""
        if self._graph is not None:
            return
        self._parsed = []
        for f in self._py_files:
            try:
                self._parsed.append(parse_file(f))
            except ValueError:
                continue  # unsupported extension or parse error
        self._graph = self._build_call_graph()

    def _build_call_graph(self) -> nx.DiGraph:
        """Build a directed graph: node per defined function, edge per call."""
        g = nx.DiGraph()

        # First pass: register every defined function as a node.
        # Key format: "relative/path.py::function_name"
        all_func_names: set[str] = set()
        route_decorated: set[str] = set()

        for pf in self._parsed:
            rel = self._relative(pf.path)
            for fn in pf.functions:
                key = f"{rel}::{fn.name}"
                g.add_node(key, file=rel, line_start=fn.line_start, line_end=fn.line_end)
                all_func_names.add(fn.name)
            route_decorated.update(pf.route_decorated_functions)

        # Store route-decorated names for exclusion later.
        self._route_decorated = route_decorated

        # Second pass: add edges. For each call site, if a function with that
        # name exists anywhere in the project, add an edge caller → callee.
        # This is name-based resolution (no cross-module type inference).
        for pf in self._parsed:
            rel = self._relative(pf.path)
            # Figure out which functions in this file could be the "caller".
            # We attribute all top-level calls to a virtual "<module>" node.
            callers = {fn.name: f"{rel}::{fn.name}" for fn in pf.functions}

            for called_name in pf.calls:
                if called_name not in all_func_names:
                    continue  # external / built-in — skip
                # Find all possible callee nodes
                callee_keys = [n for n in g.nodes if n.endswith(f"::{called_name}")]
                # Find the caller (simplified: attribute to module-level if ambiguous)
                for caller_key in callers.values():
                    for callee_key in callee_keys:
                        if caller_key != callee_key:
                            g.add_edge(caller_key, callee_key)

        return g

    def _uncalled_functions(self) -> list[SuspectFunction]:
        """Return functions with in-degree 0 that aren't excluded."""
        assert self._graph is not None
        suspects: list[SuspectFunction] = []

        for node in self._graph.nodes:
            in_deg = self._graph.in_degree(node)
            if in_deg > 0:
                continue

            data = self._graph.nodes[node]
            func_name = node.split("::")[-1]

            if self._is_excluded(func_name):
                continue

            suspects.append(SuspectFunction(
                name=func_name,
                file=data["file"],
                line_start=data["line_start"],
                line_end=data["line_end"],
                suspect_type="uncalled",
                call_count=in_deg,
            ))

        return suspects

    def _comment_smells(self) -> list[SuspectFunction]:
        """Scan for TODO/FIXME/HACK near ``def`` or commented-out ``def``s."""
        suspects: list[SuspectFunction] = []

        for pf in self._parsed:
            source = Path(pf.path).read_text(encoding="utf-8", errors="replace")
            for m in _COMMENT_SMELL_RE.finditer(source):
                line_no = source[: m.start()].count("\n") + 1
                # Try to extract a function name from the match
                name_match = re.search(r"def\s+(\w+)", m.group())
                name = name_match.group(1) if name_match else "<comment-smell>"
                rel = self._relative(pf.path)
                suspects.append(SuspectFunction(
                    name=name,
                    file=rel,
                    line_start=line_no,
                    line_end=line_no,
                    suspect_type="comment_smell",
                    call_count=0,
                ))

        return suspects

    def _is_excluded(self, func_name: str) -> bool:
        """Return True if this function name should never be flagged."""
        for pat in _EXCLUDE_PATTERNS:
            if pat.search(func_name):
                return True
        if func_name in self._route_decorated:
            return True
        return False

    def _relative(self, abs_path: str) -> str:
        """Make *abs_path* relative to the repo root, using forward slashes."""
        try:
            return str(Path(abs_path).relative_to(self._repo_root)).replace("\\", "/")
        except ValueError:
            return abs_path
