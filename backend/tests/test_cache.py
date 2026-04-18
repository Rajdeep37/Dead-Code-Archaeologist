"""Tests for the verdict cache module."""

from app.cache import VerdictCache
from app.models import SuspectFunction, Verdict


def _make_verdict(name: str = "foo") -> Verdict:
    return Verdict(
        suspect=SuspectFunction(name=name, file="a.py", line_start=1, line_end=5),
        verdict="delete",
        confidence=90,
        reason="Not called anywhere.",
        author_context="alice, 2024-01-01",
    )


class TestVerdictCache:
    def test_miss_returns_none(self, tmp_path):
        cache = VerdictCache(str(tmp_path / "cache"))
        assert cache.get("nonexistent") is None
        cache.close()

    def test_set_then_get(self, tmp_path):
        cache = VerdictCache(str(tmp_path / "cache"))
        v = _make_verdict()
        cache.set("k1", v)
        retrieved = cache.get("k1")
        assert retrieved is not None
        assert retrieved.verdict == "delete"
        assert retrieved.suspect.name == "foo"
        cache.close()

    def test_key_is_deterministic(self):
        k1 = VerdictCache.make_key("abc123", "file.py", "func")
        k2 = VerdictCache.make_key("abc123", "file.py", "func")
        assert k1 == k2

    def test_different_inputs_different_keys(self):
        k1 = VerdictCache.make_key("abc123", "file.py", "func")
        k2 = VerdictCache.make_key("def456", "file.py", "func")
        assert k1 != k2
