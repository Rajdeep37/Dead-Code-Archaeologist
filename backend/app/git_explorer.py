"""Git history explorer – Week 1 module.

Responsibilities:
- List all commits in a repository.
- Return per-file blame (who last changed each line).
- Return the diff for a given commit SHA.

How to use:
    from app.git_explorer import GitExplorer

    explorer = GitExplorer("/path/to/repo")
    commits  = explorer.get_all_commits()
    blame    = explorer.get_file_blame("src/utils.py")
    diff     = explorer.get_commit_diff(commits[0].sha)
"""

from datetime import datetime, timezone
from pathlib import Path

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError

from app.models import BlameEntry, CommitInfo


class GitExplorer:
    """Wraps a local git repository and exposes the history data the pipeline needs."""

    def __init__(self, repo_path: str) -> None:
        """Open an existing git repository at *repo_path*.

        GitPython's ``search_parent_directories=True`` means you can pass any
        sub-directory of a repo and it will walk up until it finds the ``.git``
        folder, just like the ``git`` CLI does.

        Raises:
            ValueError: if the path is not a valid git repository.
        """
        try:
            self.repo = Repo(repo_path, search_parent_directories=True)
        except (InvalidGitRepositoryError, NoSuchPathError) as exc:
            raise ValueError(f"Not a git repository: {repo_path}") from exc

        # Store the root as a Path for convenient file operations later.
        self.root = Path(self.repo.working_dir)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get_all_commits(self, file_path: str | None = None) -> list[CommitInfo]:
        """Return every commit in the repository, newest first.

        Args:
            file_path: when given, only commits that touched this specific
                       file are returned (equivalent to ``git log -- <file>``).
        """
        kwargs: dict = {}
        if file_path:
            kwargs["paths"] = file_path

        # repo.iter_commits() walks the commit graph starting from HEAD.
        # It yields GitPython Commit objects lazily, so large repos are fine.
        return [_to_commit_info(c) for c in self.repo.iter_commits("HEAD", **kwargs)]

    def get_file_blame(self, file_path: str, rev: str = "HEAD") -> list[BlameEntry]:
        """Return a line-by-line blame for *file_path* at revision *rev*.

        ``repo.blame()`` returns a list of ``(Commit, [line, line, ...])``
        groups – each group is a consecutive run of lines that were last
        changed by the same commit.  We flatten that into one ``BlameEntry``
        per line.

        Args:
            file_path: path relative to the repository root.
            rev:       git revision to blame against (default: HEAD).

        Raises:
            ValueError: if git cannot blame the file (e.g. binary file, wrong path).
        """
        try:
            blame_output = self.repo.blame(rev, file_path)
        except GitCommandError as exc:
            raise ValueError(f"Could not blame '{file_path}': {exc}") from exc

        entries: list[BlameEntry] = []
        line_number = 1

        for commit, lines in blame_output:
            for raw_line in lines:
                # GitPython returns lines as bytes; decode leniently.
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
        """Return the full unified diff for a single commit as a plain string.

        Uses ``git show <sha>`` under the hood which works even for the very
        first commit (no parent) – something that ``commit.diff()`` can't do
        without extra handling.

        Raises:
            ValueError: if *sha* is not found in the repository.
        """
        try:
            return self.repo.git.show(sha)
        except GitCommandError as exc:
            raise ValueError(f"Could not get diff for '{sha}': {exc}") from exc

    def get_file_history(self, file_path: str) -> list[CommitInfo]:
        """Shortcut: all commits that touched *file_path*, newest first."""
        return self.get_all_commits(file_path=file_path)


# ------------------------------------------------------------------ #
# Private helpers                                                      #
# ------------------------------------------------------------------ #

def _to_commit_info(commit) -> CommitInfo:
    """Convert a GitPython Commit object into our CommitInfo model."""
    # committed_datetime is timezone-aware; normalise to UTC for display.
    dt: datetime = commit.committed_datetime
    return CommitInfo(
        sha=commit.hexsha[:12],
        author=commit.author.name or "unknown",
        date=dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        message=commit.message.strip(),
    )
