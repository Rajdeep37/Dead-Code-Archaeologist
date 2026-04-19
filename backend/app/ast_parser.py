"""AST parser: extracts function definitions and call sites from Python files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_python

PY_LANGUAGE = Language(tree_sitter_python.language())

_FUNC_QUERY = Query(
    PY_LANGUAGE,
    "(function_definition name: (identifier) @name) @func",
)

_CALL_QUERY = Query(
    PY_LANGUAGE,
    "(call function: [(identifier) @name (attribute attribute: (identifier) @name)])",
)

_DECORATOR_QUERY = Query(
    PY_LANGUAGE,
    "(decorated_definition (decorator (call function: (attribute attribute: (identifier) @route_name))) definition: (function_definition name: (identifier) @fn_name)) @decorated",
)

# Supported extensions → language tag
_SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
}


@dataclass
class ParsedFunction:
    """A single function extracted from a source file."""

    name: str
    file: str
    line_start: int  # 1-based
    line_end: int  # 1-based
    decorators: list[str] = field(default_factory=list)


@dataclass
class ParsedFile:
    """Aggregated parse result for one source file."""

    path: str
    functions: list[ParsedFunction]
    calls: list[str]
    route_decorated_functions: set[str] = field(default_factory=set)


class FileParser:
    """Parses a single Python source file using Tree-sitter."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        ext = Path(file_path).suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {ext}")

        self._parser = Parser(PY_LANGUAGE)
        source_bytes = Path(file_path).read_bytes()
        self._tree = self._parser.parse(source_bytes)

    def extract_functions(self) -> list[ParsedFunction]:
        """Return every function defined in the file."""
        cursor = QueryCursor(_FUNC_QUERY)
        matches = cursor.matches(self._tree.root_node)

        functions: list[ParsedFunction] = []
        for _pattern_idx, capture_dict in matches:
            func_node = capture_dict["func"][0]
            name_node = capture_dict["name"][0]
            functions.append(
                ParsedFunction(
                    name=name_node.text.decode(),
                    file=self.file_path,
                    line_start=func_node.start_point[0] + 1,
                    line_end=func_node.end_point[0] + 1,
                )
            )
        return functions

    def extract_calls(self) -> list[str]:
        """Return a deduplicated list of function/method names called."""
        cursor = QueryCursor(_CALL_QUERY)
        captures = cursor.captures(self._tree.root_node)
        seen: set[str] = set()
        for node in captures.get("name", []):
            seen.add(node.text.decode())
        return sorted(seen)

    def extract_route_decorated_functions(self) -> set[str]:
        """Return names of functions with route-like decorators (e.g. ``@app.get``)."""
        cursor = QueryCursor(_DECORATOR_QUERY)
        matches = cursor.matches(self._tree.root_node)
        names: set[str] = set()
        for _pattern_idx, capture_dict in matches:
            fn_nodes = capture_dict.get("fn_name", [])
            for fn_node in fn_nodes:
                names.add(fn_node.text.decode())
        return names


def parse_file(path: str) -> ParsedFile:
    """Parse *path* and return a ParsedFile with functions and calls."""
    fp = FileParser(path)
    return ParsedFile(
        path=path,
        functions=fp.extract_functions(),
        calls=fp.extract_calls(),
        route_decorated_functions=fp.extract_route_decorated_functions(),
    )
