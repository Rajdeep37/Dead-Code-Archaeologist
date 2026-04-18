"""Tests for the LLM agent module.

All tests mock ChatOllama so no running Ollama instance is needed.
"""

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.llm_agent import EvidenceBundle, LLMAgent, build_evidence
from app.models import CommitInfo, SuspectFunction, Verdict

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


# ---- helpers --------------------------------------------------------------


def _suspect() -> SuspectFunction:
    return SuspectFunction(
        name="dead_function",
        file="sample.py",
        line_start=25,
        line_end=27,
    )


def _good_json() -> str:
    return json.dumps({
        "verdict": "delete",
        "confidence": 95,
        "reason": "Never called anywhere in the project.",
        "author_context": "alice on 2024-01-01 via commit abc123",
    })


@pytest.fixture()
def temp_git_repo(tmp_path: Path):
    """Create a throwaway git repo with sample.py committed."""
    shutil.copy(FIXTURE_DIR / "sample.py", tmp_path / "sample.py")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    yield tmp_path


# ---- tests ----------------------------------------------------------------


class TestBuildEvidence:
    def test_populates_fields(self, temp_git_repo):
        from app.git_explorer import GitExplorer

        explorer = GitExplorer(str(temp_git_repo))
        suspect = _suspect()
        bundle = build_evidence(suspect, explorer)

        assert bundle.suspect is suspect
        assert "dead_function" in bundle.source_snippet or "dead code" in bundle.source_snippet
        assert isinstance(bundle.recent_commits, list)
        assert isinstance(bundle.blame_summary, str)


class TestLLMAgent:
    @pytest.mark.asyncio
    async def test_judge_returns_verdict(self):
        mock_response = AsyncMock()
        mock_response.content = _good_json()

        with patch(
            "app.llm_agent.ChatOllama.ainvoke",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as m:
            agent = LLMAgent()
            bundle = EvidenceBundle(
                suspect=_suspect(),
                source_snippet="def dead_function():\n    return 'dead'",
                recent_commits=[],
                blame_summary="",
            )
            verdict = await agent.judge(bundle)

        assert isinstance(verdict, Verdict)
        assert verdict.verdict == "delete"
        assert verdict.confidence == 95
        m.assert_called_once()

    @pytest.mark.asyncio
    async def test_judge_retries_on_bad_json(self):
        bad_response = AsyncMock()
        bad_response.content = "Sure! Here is my analysis..."

        good_response = AsyncMock()
        good_response.content = _good_json()

        with patch(
            "app.llm_agent.ChatOllama.ainvoke",
            new_callable=AsyncMock,
            side_effect=[bad_response, good_response],
        ):
            agent = LLMAgent()
            bundle = EvidenceBundle(
                suspect=_suspect(),
                source_snippet="def dead_function():\n    return 'dead'",
                recent_commits=[],
                blame_summary="",
            )
            verdict = await agent.judge(bundle)

        assert verdict.verdict == "delete"
