"""Disk cache – Week 3 module.

Responsibilities:
- Persist LLM verdicts to disk keyed by (repo_sha, function_name).
- Return cached results instantly on re-runs so the LLM is only
  called once per unique suspect.
"""

from __future__ import annotations

import hashlib

import diskcache

from app.models import Verdict


class VerdictCache:
    """Thin wrapper around diskcache for storing Verdict objects."""

    def __init__(self, cache_dir: str = ".verdicts_cache") -> None:
        self._cache = diskcache.Cache(cache_dir)

    @staticmethod
    def make_key(repo_sha: str, file: str, name: str) -> str:
        """Return a deterministic cache key for a suspect in a repo snapshot."""
        raw = f"{repo_sha}:{file}:{name}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> Verdict | None:
        """Return the cached Verdict, or None on a miss."""
        raw = self._cache.get(key)
        if raw is None:
            return None
        return Verdict.model_validate_json(raw)

    def set(self, key: str, verdict: Verdict) -> None:
        """Store a Verdict under key."""
        self._cache.set(key, verdict.model_dump_json())

    def close(self) -> None:
        """Close the underlying diskcache handle."""
        self._cache.close()
