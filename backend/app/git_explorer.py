"""Git history explorer: commits, per-file blame, and commit diffs."""

from datetime import datetime, timezone
from pathlib import Path

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError

from app.models import BlameEntry, CommitInfo


class GitExplorer:
    """Wraps a local git repository and exposes the history data the pipeline needs."""

    def __init__(self, repo_path: str) -> None:
        """Open the git repository at *repo_path*, walking up to find `.git` if needed.

        Raises ValueError if the path is not a valid git repository.
        """
        try:
            self.repo = Repo(repo_path, search_parent_directories=True)
        except (InvalidGitRepositoryError, NoSuchPathError) as exc:
            raise ValueError(f"Not a git repository: {repo_path}") from exc

        self.root = Path(self.repo.working_dir)

    def get_all_commits(self, file_path: str | None = None) -> list[CommitInfo]:
        """Return all commits, newest first. Optionally filter to a single file."""
        kwargs: dict = {}
        if file_path:
            kwargs["paths"] = file_path

        return [_to_commit_info(c) for c in self.repo.iter_commits("HEAD", **kwargs)]

    def get_file_blame(self, file_path: str, rev: str = "HEAD") -> list[BlameEntry]:
        """Return a line-by-line blame for *file_path* at *rev*.

        Raises ValueError if git cannot blame the file.
        """
        try:
            blame_output = self.repo.blame(rev, file_path)
        except GitCommandError as exc:
            raise ValueError(f"Could not blame '{file_path}': {exc}") from exc

        entries: list[BlameEntry] = []
        line_number = 1

        for commit, lines in blame_output:
            for raw_line in lines:
                if isinstance(raw_line, bytes):
                    content = raw_line.decode("utf-8", errors="replace")
                else:
                    content = str(raw_line)

                entries.append(BlameEntry(
                    line_number=line_number,
                    line_content=content.rstrip("\n"),
                    sha=commit.hexsha[:12],
                    author=commit.author.name or "unknown",
                ))
                line_number += 1

        return entries

    def get_commit_diff(self, sha: str) -> str:
        """Return the full unified diff for a single commit.

        Raises ValueError if *sha* is not found in the repository.
        """
        try:
            return self.repo.git.show(sha)
        except GitCommandError as exc:
            raise ValueError(f"Could not get diff for '{sha}': {exc}") from exc

    def get_file_history(self, file_path: str) -> list[CommitInfo]:
        """Shortcut: all commits that touched *file_path*, newest first."""
        return self.get_all_commits(file_path=file_path)


def _to_commit_info(commit) -> CommitInfo:
    """Convert a GitPython Commit to CommitInfo."""
    dt: datetime = commit.committed_datetime
    return CommitInfo(
        sha=commit.hexsha[:12],
        author=commit.author.name or "unknown",
        date=dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        message=commit.message.strip(),
    )
