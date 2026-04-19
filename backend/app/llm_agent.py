"""LLM reasoning agent – Week 3 module.

Responsibilities:
- Accept a suspect function + its git evidence bundle.
- Call the local Ollama/Mistral model (or Claude Haiku when hosted).
- Return a structured Verdict with confidence score and rationale.

Provider is chosen via the LLM_PROVIDER env variable:
  LLM_PROVIDER=ollama  (default, local)
  LLM_PROVIDER=anthropic  (hosted demo)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.git_explorer import GitExplorer
from app.models import CommitInfo, SuspectFunction, Verdict

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LLM_MODEL: str = os.getenv("LLM_MODEL", "mistral:7b-instruct-q4_K_M")
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Evidence truncation limits — prevent context-window overflow on large functions
_MAX_SOURCE_LINES: int = int(os.getenv("MAX_SOURCE_LINES", "80"))
_MAX_BLAME_LINES: int  = int(os.getenv("MAX_BLAME_LINES",  "40"))
_MAX_COMMITS: int      = int(os.getenv("MAX_COMMITS",       "3"))

# Per-call timeout for each ainvoke attempt (seconds)
_LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120"))

# Maximum total evidence characters before skipping the LLM call entirely.
# Very large prompts reliably cause timeouts — skip them proactively.
_MAX_EVIDENCE_CHARS: int = int(os.getenv("MAX_EVIDENCE_CHARS", "6000"))

# ---------------------------------------------------------------------------
# Evidence bundle
# ---------------------------------------------------------------------------


@dataclass
class EvidenceBundle:
    """All context the LLM needs to judge a single suspect function."""

    suspect: SuspectFunction
    source_snippet: str
    recent_commits: list[CommitInfo]
    blame_summary: str


def build_evidence(suspect: SuspectFunction, explorer: GitExplorer) -> EvidenceBundle:
    """Assemble an EvidenceBundle for *suspect* using data from *explorer*."""
    # Read the function body from disk (truncated to avoid context overflow)
    abs_path = explorer.root / suspect.file
    lines: list[str] = []
    if abs_path.is_file():
        all_lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
        raw_lines = all_lines[max(0, suspect.line_start - 1) : suspect.line_end]
        if len(raw_lines) > _MAX_SOURCE_LINES:
            half = _MAX_SOURCE_LINES // 2
            omitted = len(raw_lines) - _MAX_SOURCE_LINES
            lines = (
                raw_lines[:half]
                + [f"    # ... {omitted} lines omitted ..."]
                + raw_lines[-half:]
            )
        else:
            lines = raw_lines
    source_snippet = "\n".join(lines)

    # Recent commits that touched this file
    recent_commits: list[CommitInfo] = []
    try:
        recent_commits = explorer.get_file_history(suspect.file)[:_MAX_COMMITS]
    except Exception:
        pass

    # Blame for the function's line range (truncated)
    blame_summary = ""
    try:
        blame_entries = explorer.get_file_blame(suspect.file)
        relevant = [
            e for e in blame_entries
            if suspect.line_start <= e.line_number <= suspect.line_end
        ]
        truncated = len(relevant) > _MAX_BLAME_LINES
        relevant = relevant[:_MAX_BLAME_LINES]
        blame_lines = [
            f"  L{e.line_number}: {e.author} ({e.sha}) | {e.line_content}"
            for e in relevant
        ]
        if truncated:
            blame_lines.append(f"  ... (truncated to first {_MAX_BLAME_LINES} lines)")
        blame_summary = "\n".join(blame_lines)
    except Exception:
        pass

    return EvidenceBundle(
        suspect=suspect,
        source_snippet=source_snippet,
        recent_commits=recent_commits,
        blame_summary=blame_summary,
    )


def evidence_is_oversized(bundle: EvidenceBundle) -> bool:
    """Return True if the total evidence exceeds the configured character budget."""
    total = (
        len(bundle.source_snippet)
        + len(bundle.blame_summary)
        + sum(len(c.message) for c in bundle.recent_commits)
    )
    if total > _MAX_EVIDENCE_CHARS:
        logger.debug(
            "[LLM] evidence too large for %s: %d chars (limit %d)",
            bundle.suspect.name, total, _MAX_EVIDENCE_CHARS,
        )
        return True
    return False


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert code reviewer specialising in dead-code detection.
You will receive a suspect function together with git evidence
(blame, recent commits, source code).

Your job is to decide whether the function is truly dead code.

Reply with **raw JSON only** — no markdown, no explanation outside the JSON.
Use this exact schema:

{
  "verdict": "delete" | "investigate" | "keep",
  "confidence": <int 0-100>,
  "reason": "<one-paragraph explanation>",
  "author_context": "<who wrote it, when, and relevant commit messages>"
}

Guidelines:
- "delete"      → you are ≥80% sure the function is safe to remove.
- "investigate" → suspicious but needs a human to verify (e.g. used via reflection, registered dynamically).
- "keep"        → the function is likely used or important despite appearing uncalled.
"""


def _build_human_message(bundle: EvidenceBundle) -> str:
    """Format the evidence bundle into the human message for the LLM."""
    commits_text = "\n".join(
        f"  {c.sha} {c.date} {c.author}: {c.message}"
        for c in bundle.recent_commits
    ) or "  (no commit history available)"

    return f"""\
## Suspect function

- **Name**: `{bundle.suspect.name}`
- **File**: `{bundle.suspect.file}`
- **Lines**: {bundle.suspect.line_start}–{bundle.suspect.line_end}
- **Suspect type**: {bundle.suspect.suspect_type}
- **In-degree (call count)**: {bundle.suspect.call_count}

### Source code
```python
{bundle.source_snippet}
```

### Git blame (who last touched each line)
{bundle.blame_summary or "(not available)"}

### Recent commits on this file
{commits_text}

Reply with the JSON verdict now.
"""


# ---------------------------------------------------------------------------
# LLM Agent
# ---------------------------------------------------------------------------


class LLMAgent:
    """Send evidence bundles to an LLM and parse structured verdicts."""

    def __init__(
        self,
        model: str = LLM_MODEL,
        base_url: str = OLLAMA_BASE_URL,
    ) -> None:
        self._llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.1,
            format="json",
        )

    async def judge(self, bundle: EvidenceBundle) -> Verdict:
        """Ask the LLM to judge a suspect and return a Verdict."""
        name = bundle.suspect.name
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=_build_human_message(bundle)),
        ]

        # First attempt (bounded by timeout)
        logger.debug("[LLM] invoking for %s", name)
        response = await asyncio.wait_for(
            self._llm.ainvoke(messages), timeout=_LLM_TIMEOUT
        )
        try:
            verdict = self._parse_verdict(response.content, bundle.suspect)
            logger.debug(
                "[LLM] verdict=%s confidence=%d for %s",
                verdict.verdict, verdict.confidence, name,
            )
            return verdict
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.warning("[LLM] bad JSON on first attempt for %s — retrying", name)

        # Retry with a stricter nudge (also bounded)
        messages.append(response)
        messages.append(
            HumanMessage(
                content="That was not valid JSON. Reply with ONLY the raw JSON object, nothing else."
            ),
        )
        response = await asyncio.wait_for(
            self._llm.ainvoke(messages), timeout=_LLM_TIMEOUT
        )
        verdict = self._parse_verdict(response.content, bundle.suspect)
        logger.debug(
            "[LLM] retry verdict=%s confidence=%d for %s",
            verdict.verdict, verdict.confidence, name,
        )
        return verdict

    @staticmethod
    def _parse_verdict(raw: str, suspect: SuspectFunction) -> Verdict:
        """Parse the LLM's raw text into a Verdict, raising on failure."""
        data = json.loads(raw)

        # Handle author_context being a dict instead of a string
        author_context = data.get("author_context", "")
        if isinstance(author_context, dict):
            # Flatten dict to string: "key: value, key2: value2"
            author_context = ", ".join(
                f"{k}: {v}" for k, v in author_context.items()
            )

        # Handle missing or invalid confidence
        try:
            confidence = int(data["confidence"])
        except (KeyError, TypeError, ValueError):
            confidence = 50  # default to "uncertain"

        # Handle missing verdict — default to investigate
        verdict_str = data.get("verdict", "investigate")
        if verdict_str not in ("delete", "investigate", "keep"):
            verdict_str = "investigate"

        return Verdict(
            suspect=suspect,
            verdict=verdict_str,
            confidence=confidence,
            reason=data.get("reason", "No reason provided."),
            author_context=str(author_context),
        )
