"""Tests for ``scripts.collaboration.cache_interface`` — V4.3.0 P0-1.

Coverage focus:
- Dead pickle code branches removed (``serialize`` / ``deserialize`` with
  ``format="pickle"`` now raise ``ValueError``).
- Legacy pickle **read-side fallback** in ``Serializer._deserialize`` is
  opt-in via ``allow_pickle_fallback`` (default ``False``).
- JSON round-trip remains the only supported serialization path.
- ``RedisCacheBackend`` enforces ``require_password`` and rejects
  ``serialization_format="pickle"`` at construction time.
- Malicious pickle payload (RCE via ``__reduce__``) is rejected when the
  fallback is disabled (default), proving the OWASP A08:2021 risk surface
  is closed by default.

These tests align with the V4.3.0 test plan §3 (P0-1 row) and §7.1/§7.2
security tests.
"""

from __future__ import annotations

import gzip
import json
import logging

import pytest

from scripts.collaboration.cache_interface import (
    CacheBackendInterface,
    CacheEntry,
    CacheStats,
    Serializer,
)
from scripts.collaboration.redis_cache import RedisCacheBackend

# ---------------------------------------------------------------------------
# Module-level RCE payload — must be top-level for pickle to serialize it.
# Used by TestPickleFallbackOptIn.test_fallback_disabled_does_not_execute_pickle_reduce.
# ---------------------------------------------------------------------------

# A mutable holder so ``__reduce__`` can flip it from inside pickle.loads
# (if it were ever called). A list[bool] is used because bool is immutable.
_RCE_MALICIOUS_TRIGGERED: list[bool] = [False]


def _rce_trigger() -> None:
    """Module-level callback invoked when ``pickle.loads`` runs the reduce.

    Must be top-level so ``pickle.dumps`` can serialize the reference; nested
    functions cannot be pickled.
    """
    _RCE_MALICIOUS_TRIGGERED[0] = True


class _RCE_MALICIOUS:
    """Malicious payload whose ``__reduce__`` flips the trigger flag.

    If ``pickle.loads`` is ever invoked on a payload containing this class,
    Python will call ``__reduce__`` → ``(_rce_trigger, ())`` which mutates
    ``_RCE_MALICIOUS_TRIGGERED``. The test asserts the flag stays ``False``
    when the fallback is disabled.
    """

    def __reduce__(self):
        return (_rce_trigger, ())


# ---------------------------------------------------------------------------
# P0-1: dead pickle branches removed
# ---------------------------------------------------------------------------


class TestPickleDeadCodeRemoved:
    """Verify ``format="pickle"`` is rejected on both serialize and deserialize."""

    def test_serialize_rejects_pickle_format(self) -> None:
        """``Serializer.serialize(format="pickle")`` must raise ``ValueError``.

        Regression for V4.3.0 P0-1: the dead pickle serialization branch
        (formerly cache_interface.py L207-215) has been removed.
        """
        with pytest.raises(ValueError, match="Pickle serialization format is no longer supported"):
            Serializer.serialize({"key": "value"}, format="pickle")

    def test_deserialize_rejects_pickle_format(self) -> None:
        """``Serializer.deserialize(format="pickle")`` must raise ``ValueError``.

        Regression for V4.3.0 P0-1: the dead pickle deserialization branch
        (formerly cache_interface.py L246-256) has been removed.
        """
        payload = b"\x80\x04\x95\x18\x00\x00\x00\x00\x00\x00\x00}\x94\x8c\x03key\x94\x8c\x05value\x94s."
        with pytest.raises(ValueError, match="Pickle deserialization format is no longer supported"):
            Serializer.deserialize(payload, format="pickle")

    def test_serialize_rejects_unknown_format(self) -> None:
        with pytest.raises(ValueError, match="Unsupported serialization format"):
            Serializer.serialize("x", format="yaml")

    def test_deserialize_rejects_unknown_format(self) -> None:
        with pytest.raises(ValueError, match="Unsupported deserialization format"):
            Serializer.deserialize(b"x", format="yaml")

    def test_dead_code_pickle_branches_removed(self) -> None:
        """Source-level guarantee: no ``pickle.dumps`` / ``pickle.loads`` in Serializer.

        V4.3.0 P2-1: The entire pickle fallback path has been removed.
        Neither ``serialize`` nor ``deserialize`` nor ``_deserialize``
        may contain ``pickle.dumps`` or ``pickle.loads`` calls.
        """
        import inspect

        from scripts.collaboration import cache_interface

        serialize_src = inspect.getsource(Serializer.serialize)
        assert "pickle.dumps" not in serialize_src, (
            "Serializer.serialize still contains pickle.dumps — dead code removal incomplete."
        )
        deserialize_src = inspect.getsource(Serializer.deserialize)
        assert "pickle.loads" not in deserialize_src, (
            "Serializer.deserialize still contains pickle.loads — dead code removal incomplete."
        )
        inner_src = inspect.getsource(Serializer._deserialize)
        assert "pickle.loads" not in inner_src, (
            "Serializer._deserialize still contains pickle.loads — "
            "P2-1 fallback removal incomplete."
        )
        # V4.3.0 P2-1: no pickle import anywhere in the module.
        module_src = inspect.getsource(cache_interface)
        assert "import pickle" not in module_src, (
            "Pickle import must be removed from cache_interface.py (P2-1)."
        )


# ---------------------------------------------------------------------------
# P0-1: JSON round-trip (only supported path)
# ---------------------------------------------------------------------------


class TestJsonRoundTrip:
    """JSON serialization/deserialization works for all JSON-compatible types."""

    @pytest.mark.parametrize(
        "value",
        [
            None,
            True,
            False,
            42,
            -3.14,
            "",
            "hello",
            [1, 2, 3],
            {"key": "value", "nested": {"a": 1}},
            [{"a": 1}, {"b": [2, 3]}],
        ],
        ids=[
            "None",
            "True",
            "False",
            "int",
            "float",
            "empty_str",
            "str",
            "list",
            "dict_nested",
            "list_of_dicts",
        ],
    )
    def test_json_round_trip(self, value: object) -> None:
        serialized = Serializer.serialize(value, format="json")
        assert isinstance(serialized, bytes)
        deserialized = Serializer.deserialize(serialized, format="json")
        assert deserialized == value

    def test_json_round_trip_with_compression(self) -> None:
        value = {"large": "x" * 1000}
        serialized = Serializer.serialize(value, format="json", compress=True)
        # Compressed JSON bytes won't decode as UTF-8 directly — verifying
        # that the serialized form is actually gzip-compressed, not raw JSON.
        with pytest.raises((UnicodeDecodeError, json.JSONDecodeError, gzip.BadGzipFile)):
            json.loads(serialized.decode("utf-8"))
        deserialized = Serializer.deserialize(serialized, format="json", compressed=True)
        assert deserialized == value

    def test_serialize_non_json_coerced_via_default_str(self) -> None:
        """Non-JSON-serializable values are coerced to str via ``default=str``."""

        class Custom:
            def __str__(self) -> str:
                return "custom-instance"

        serialized = Serializer.serialize(Custom(), format="json")
        deserialized = Serializer.deserialize(serialized, format="json")
        assert deserialized == "custom-instance"


# ---------------------------------------------------------------------------
# P2-1: pickle fallback completely removed (V4.3.0)
# ---------------------------------------------------------------------------


class TestPickleFallbackRemoved:
    """V4.3.0 P2-1: ``allow_pickle_fallback`` removed — non-JSON data always rejected."""

    def _make_pickle_payload(self, value: object) -> bytes:
        import pickle

        return pickle.dumps(value)

    def test_pickle_data_always_rejected(self) -> None:
        """Non-JSON bytes raise ``ValueError`` — no fallback path exists."""
        payload = self._make_pickle_payload({"key": "value"})
        with pytest.raises(ValueError, match="Unable to deserialize cache data with JSON"):
            Serializer._deserialize(payload)

    def test_pickle_data_always_rejected_via_deserialize(self) -> None:
        """Same via the public ``deserialize`` API."""
        payload = self._make_pickle_payload({"key": "value"})
        with pytest.raises(ValueError, match="Unable to deserialize cache data with JSON"):
            Serializer.deserialize(payload, format="json")

    def test_pickle_data_does_not_execute_pickle_reduce(self, caplog) -> None:
        """Malicious pickle payload must not trigger ``__reduce__``.

        Security regression for OWASP A08:2021 — ``pickle.loads`` must never
        be called (P2-1 removed the fallback entirely), so the RCE
        ``__reduce__`` is not executed.
        """
        _RCE_MALICIOUS_TRIGGERED[0] = False
        payload = self._make_pickle_payload(_RCE_MALICIOUS())
        _RCE_MALICIOUS_TRIGGERED[0] = False

        with caplog.at_level(logging.WARNING), pytest.raises(ValueError):
            Serializer._deserialize(payload)

        assert not _RCE_MALICIOUS_TRIGGERED[0], (
            "pickle.loads was invoked — RCE attack surface not closed."
        )

    def test_pickle_rejection_logs_warning_on_bytes(self, caplog) -> None:
        """Bytes payload that fails JSON parsing logs a warning mentioning P2-1."""
        payload = self._make_pickle_payload({"k": "v"})
        with caplog.at_level(logging.WARNING), pytest.raises(ValueError):
            Serializer._deserialize(payload)
        assert any(
            "Pickle fallback removed in V4.3.0 P2-1" in rec.message
            for rec in caplog.records
        )

    def test_non_json_str_rejected(self) -> None:
        """Non-JSON str input raises ``ValueError`` — no pickle path for str."""
        with pytest.raises(ValueError):
            Serializer._deserialize("not-json")
        with pytest.raises(ValueError):
            Serializer.deserialize(b"not-json", format="json")

    def test_deserialize_no_allow_pickle_fallback_param(self) -> None:
        """V4.3.0 P2-1: ``allow_pickle_fallback`` parameter removed from API."""
        import inspect

        sig = inspect.signature(Serializer.deserialize)
        assert "allow_pickle_fallback" not in sig.parameters, (
            "allow_pickle_fallback parameter should be removed in P2-1"
        )
        sig_inner = inspect.signature(Serializer._deserialize)
        assert "allow_pickle_fallback" not in sig_inner.parameters, (
            "allow_pickle_fallback parameter should be removed in P2-1"
        )


# ---------------------------------------------------------------------------
# P0-1: RedisCacheBackend security tightening
# ---------------------------------------------------------------------------


class TestRedisCacheBackendSecurity:
    """``RedisCacheBackend`` rejects pickle format and enforces password."""

    def test_redis_rejects_pickle_serialization_format(self) -> None:
        with pytest.raises(ValueError, match="serialization_format='pickle' is no longer supported"):
            RedisCacheBackend(serialization_format="pickle")

    def test_redis_rejects_unknown_serialization_format(self) -> None:
        with pytest.raises(ValueError, match="Unsupported serialization_format"):
            RedisCacheBackend(serialization_format="msgpack")

    def test_redis_require_password_rejects_url_without_password(self) -> None:
        with pytest.raises(ValueError, match="require_password=True but Redis URL carries no password"):
            RedisCacheBackend(
                redis_url="redis://localhost:6379/0",
                require_password=True,
            )

    def test_redis_require_password_accepts_url_with_password(self) -> None:
        # Should not raise — URL carries a password.
        backend = RedisCacheBackend(
            redis_url="redis://:secret@localhost:6379/0",
            require_password=True,
        )
        assert backend.require_password is True

    def test_redis_require_password_accepts_user_password(self) -> None:
        backend = RedisCacheBackend(
            redis_url="redis://user:secret@localhost:6379/0",
            require_password=True,
        )
        assert backend.require_password is True

    def test_redis_no_allow_pickle_fallback_param(self) -> None:
        """V4.3.0 P2-1: ``allow_pickle_fallback`` parameter removed from RedisCacheBackend."""
        import inspect

        sig = inspect.signature(RedisCacheBackend.__init__)
        assert "allow_pickle_fallback" not in sig.parameters, (
            "allow_pickle_fallback parameter should be removed in P2-1"
        )

    def test_redis_require_password_env_url_without_password(self, monkeypatch) -> None:
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        with pytest.raises(ValueError, match="require_password=True but Redis URL carries no password"):
            RedisCacheBackend(require_password=True)

    def test_redis_require_password_env_url_with_password(self, monkeypatch) -> None:
        monkeypatch.setenv("REDIS_URL", "redis://:secret@localhost:6379/0")
        backend = RedisCacheBackend(require_password=True)
        assert backend.require_password is True


# ---------------------------------------------------------------------------
# P0-1: gzip path still works (smoke)
# ---------------------------------------------------------------------------


class TestGzipPath:
    def test_gzip_round_trip(self) -> None:
        value = {"compressed": True, "data": "x" * 500}
        serialized = Serializer.serialize(value, compress=True)
        # Verify it's actually compressed (not raw JSON)
        raw_json = json.dumps(value, default=str).encode("utf-8")
        assert serialized != raw_json
        deserialized = Serializer.deserialize(serialized, compressed=True)
        assert deserialized == value

    def test_gzip_decompress_failure(self) -> None:
        # gzip.BadGzipFile is raised when the input is not a valid gzip stream.
        # ValueError is also acceptable because Serializer.deserialize wraps
        # the underlying gzip error in its own try/except.
        with pytest.raises((gzip.BadGzipFile, ValueError, OSError)):
            Serializer.deserialize(b"not-gzip", compressed=True)


# ---------------------------------------------------------------------------
# Smoke: CacheStats / CacheEntry (unchanged behavior)
# ---------------------------------------------------------------------------


class TestCacheStatsAndEntry:
    def test_cache_stats_to_dict(self) -> None:
        # ``CacheStats.hit_rate`` is an explicit field (not auto-derived from
        # hits/misses) — callers must compute and set it when recording stats.
        stats = CacheStats(hits=5, misses=2, hit_rate=5 / 7, total_size_bytes=1024)
        d = stats.to_dict()
        assert d["hits"] == 5
        assert d["misses"] == 2
        assert d["total_size_bytes"] == 1024
        assert d["hit_rate"] == "71.4%"

    def test_cache_stats_to_dict_default_hit_rate(self) -> None:
        """Default ``hit_rate=0.0`` is rendered as ``0.0%`` when not set."""
        stats = CacheStats(hits=5, misses=2)
        d = stats.to_dict()
        assert d["hit_rate"] == "0.0%"

    def test_cache_stats_total_requests(self) -> None:
        stats = CacheStats(hits=3, misses=1)
        assert stats.total_requests == 4

    def test_cache_entry_is_expired(self) -> None:
        import time

        entry = CacheEntry(key="k", value="v", expires_at=time.time() - 1)
        assert entry.is_expired() is True
        entry2 = CacheEntry(key="k", value="v", expires_at=time.time() + 100)
        assert entry2.is_expired() is False
        entry3 = CacheEntry(key="k", value="v", expires_at=None)
        assert entry3.is_expired() is False

    def test_cache_entry_ttl_remaining(self) -> None:
        import time

        entry = CacheEntry(key="k", value="v", expires_at=time.time() + 50)
        assert 40 < entry.ttl_remaining <= 50

        entry_no_ttl = CacheEntry(key="k", value="v", expires_at=None)
        assert entry_no_ttl.ttl_remaining is None

    def test_cache_entry_age_seconds(self) -> None:
        entry = CacheEntry(key="k", value="v", created_at=0)
        # age should be roughly current time.time()
        assert entry.age_seconds() > 1000


# ---------------------------------------------------------------------------
# Smoke: CacheBackendInterface is abstract
# ---------------------------------------------------------------------------


class TestCacheBackendInterfaceAbstract:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            CacheBackendInterface()  # type: ignore[abstract]

    def test_default_mget_implementation(self) -> None:
        class Stub(CacheBackendInterface):
            async def get(self, key: str) -> object | None:
                return f"v:{key}"

            async def set(self, key: str, value: object, ttl: int | None = None) -> bool:
                return True

            async def delete(self, key: str) -> bool:
                return False

            async def clear(self) -> None:
                pass

            async def stats(self) -> dict[str, object]:
                return {}

            async def close(self) -> None:
                pass

        import asyncio

        stub = Stub()
        results = asyncio.run(stub.mget(["a", "b"]))
        assert results == ["v:a", "v:b"]

    def test_default_touch_implementation(self) -> None:
        class Stub(CacheBackendInterface):
            async def get(self, key: str) -> object | None:
                return "value" if key == "k" else None

            async def set(self, key: str, value: object, ttl: int | None = None) -> bool:
                return True

            async def delete(self, key: str) -> bool:
                return False

            async def clear(self) -> None:
                pass

            async def stats(self) -> dict[str, object]:
                return {}

            async def close(self) -> None:
                pass

        import asyncio

        stub = Stub()
        assert asyncio.run(stub.touch("k", ttl=60)) is True
        assert asyncio.run(stub.touch("missing", ttl=60)) is False

    def test_default_increment_implementation(self) -> None:
        class Stub(CacheBackendInterface):
            async def get(self, key: str) -> object | None:
                return 41 if key == "counter" else None

            async def set(self, key: str, value: object, ttl: int | None = None) -> bool:
                return True

            async def delete(self, key: str) -> bool:
                return False

            async def clear(self) -> None:
                pass

            async def stats(self) -> dict[str, object]:
                return {}

            async def close(self) -> None:
                pass

        import asyncio

        stub = Stub()
        result = asyncio.run(stub.increment("counter"))
        assert result == 42
        # Missing key → None
        assert asyncio.run(stub.increment("missing")) is None
