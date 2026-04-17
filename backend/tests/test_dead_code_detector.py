"""Tests for the dead code detector module.

These tests point the detector at a small temporary git repo containing
the fixtures/sample.py file, so we get realistic results without
touching the main project repo.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.dead_code_detector import DeadCodeDetector

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture()
def temp_git_repo(tmp_path: Path):
    """Create a throwaway git repo with sample.py committed."""
    # Copy the fixture file into the temp repo
    shutil.copy(FIXTURE_DIR / "sample.py", tmp_path / "sample.py")

    # Initialise a git repo and commit the file
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    yield tmp_path


class TestDeadCodeDetector:
    def test_find_suspects_flags_dead_function(self, temp_git_repo):
        detector = DeadCodeDetector(str(temp_git_repo))
        suspects = detector.find_suspects()
        uncalled_names = [s.name for s in suspects if s.suspect_type == "uncalled"]
        assert "dead_function" in uncalled_names
        assert "another_dead" in uncalled_names

    def test_find_suspects_excludes_called(self, temp_git_repo):
        detector = DeadCodeDetector(str(temp_git_repo))
        suspects = detector.find_suspects()
        uncalled_names = [s.name for s in suspects if s.suspect_type == "uncalled"]
        assert "used_function" not in uncalled_names
        assert "used_method" not in uncalled_names

    def test_find_suspects_excludes_dunder(self, temp_git_repo):
        detector = DeadCodeDetector(str(temp_git_repo))
        suspects = detector.find_suspects()
        uncalled_names = [s.name for s in suspects if s.suspect_type == "uncalled"]
        assert "__init__" not in uncalled_names

    def test_comment_smells_detected(self, temp_git_repo):
        detector = DeadCodeDetector(str(temp_git_repo))
        suspects = detector.find_suspects()
        smell_names = [s.name for s in suspects if s.suspect_type == "comment_smell"]
        assert "old_handler" in smell_names

    def test_call_graph_dict(self, temp_git_repo):
        detector = DeadCodeDetector(str(temp_git_repo))
        graph = detector.get_call_graph_dict()
        assert isinstance(graph, dict)
        # caller -> used_function should appear
        caller_key = [k for k in graph if k.endswith("::caller")]
        assert len(caller_key) == 1
        assert any("used_function" in v for v in graph[caller_key[0]])

    def test_invalid_repo_raises(self):
        with pytest.raises(ValueError, match="Not a git repository"):
            DeadCodeDetector("C:/nonexistent/repo/path/xyz")
