"""Unit tests for FileRiskStore (V4.5.8 Wave 1).

Coverage focus (≥10 cases):
- happy path roundtrip + schema version
- register_id allowlist (fuzz boundaries)
- path validation: traversal, symlink, missing root
- corrupt JSON handling
- atomic write invariants
- lock timeout enforcement
- transaction commit / rollback semantics
- call counter anti-ghost gate
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.collaboration.file_risk_store import (
    DEFAULT_ROOT,
    SCHEMA_VERSION,
    FileRiskStore,
    FileRiskStoreTransaction,
    RiskStoreCorruptError,
    RiskStoreError,
    RiskStoreLockError,
    RiskStoreValidationError,
    get_call_counter_er,
)
from scripts.collaboration.risk_register import (
    ResponseStrategy,
    RiskItem,
    RiskRegister,
    RiskStatus,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def store(tmp_path: Path) -> FileRiskStore:
    return FileRiskStore(root=tmp_path, lock_timeout=1.0)


def _sample_item(rid: str = "R-001", desc: str = "data loss") -> RiskItem:
    return RiskItem(
        id=rid,
        description=desc,
        probability=0.6,
        impact=0.9,
        response_strategy=ResponseStrategy.MITIGATE,
        owner="devops",
        status=RiskStatus.OPEN,
        category="technical",
    )


class TestSchemaAndRoundtrip:
    def test_save_and_load_roundtrip(self, store: FileRiskStore, tmp_path: Path) -> None:
        payload = store.items_to_payload("default", {"R-1": _sample_item("R-1", "alpha")})
        store.save("default", payload)
        loaded = store.load("default")
        assert loaded["version"] == SCHEMA_VERSION
        assert loaded["register_id"] == "default"
        assert loaded["items"][0]["id"] == "R-1"
        # The canonical file must live under the configured root.
        assert (tmp_path / "default.json").is_file()

    def test_default_root_uses_devsquad_data(self) -> None:
        assert Path(".devsquad_data") / "risks" == DEFAULT_ROOT

    def test_schema_version_is_one(self) -> None:
        assert SCHEMA_VERSION == 1

    def test_payload_items_field_omits_derived_exposure(self, store: FileRiskStore) -> None:
        payload = store.items_to_payload("default", {"R-1": _sample_item()})
        assert set(payload["items"][0]) == {
            "id",
            "description",
            "probability",
            "impact",
            "response_strategy",
            "owner",
            "status",
            "category",
        }


class TestRegisterIdAllowlist:
    @pytest.mark.parametrize(
        "bad",
        ["", "../escape", "with/slash", "with space", "中文", "a" * 65, "a.b", "a$b"],
    )
    def test_invalid_ids_rejected(self, store: FileRiskStore, bad: str) -> None:
        with pytest.raises(RiskStoreValidationError):
            store.load(bad)

    @pytest.mark.parametrize(
        "good",
        ["default", "R-001", "prod_west-2", "a", "A" * 64],
    )
    def test_valid_ids_accepted(self, store: FileRiskStore, good: str) -> None:
        payload = store.load(good)
        assert payload["register_id"] == good


class TestPathAndSymlinkSafety:
    def test_traversal_blocked(self, store: FileRiskStore) -> None:
        with pytest.raises(RiskStoreValidationError):
            store.load("../../etc/passwd")

    def test_symlink_root_refused(self, tmp_path: Path) -> None:
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link_root"
        link.symlink_to(real)
        # The constructor resolves the root eagerly to refuse symlinked roots.
        with pytest.raises(RiskStoreValidationError):
            FileRiskStore(root=link, lock_timeout=1.0).load("default")

    def test_symlink_canonical_file_refused(self, store: FileRiskStore, tmp_path: Path) -> None:
        target = tmp_path / "default.json"
        target.write_text("{}", encoding="utf-8")
        canonical = tmp_path / "extra.json"
        canonical.symlink_to(target)
        with pytest.raises(RiskStoreValidationError):
            store.load("extra")


class TestCorruptJsonHandling:
    def test_corrupt_json_raises_corrupt_error(self, store: FileRiskStore) -> None:
        (store.root / "default.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(RiskStoreCorruptError):
            store.load("default")

    def test_wrong_schema_version_is_rejected(self, store: FileRiskStore) -> None:
        (store.root / "default.json").write_text(
            json.dumps({"version": 2, "register_id": "default", "items": []}),
            encoding="utf-8",
        )
        with pytest.raises(RiskStoreCorruptError):
            store.load("default")

    def test_register_id_mismatch_is_rejected(self, store: FileRiskStore) -> None:
        (store.root / "default.json").write_text(
            json.dumps({"version": 1, "register_id": "other", "items": []}),
            encoding="utf-8",
        )
        with pytest.raises(RiskStoreCorruptError):
            store.load("default")


class TestAtomicWrite:
    def test_save_writes_via_tmp_then_replace(self, store: FileRiskStore) -> None:
        payload = store.items_to_payload("default", {"R-1": _sample_item()})
        store.save("default", payload)
        # No leftover tmp files should exist after a successful write.
        leftovers = [p for p in os.listdir(store.root) if p.endswith(".tmp")]
        assert leftovers == []
        # Canonical file must be valid JSON, not partial.
        data = json.loads((store.root / "default.json").read_text(encoding="utf-8"))
        assert data["version"] == SCHEMA_VERSION

    def test_save_failure_leaves_canonical_intact(self, store: FileRiskStore) -> None:
        payload = store.items_to_payload("default", {"R-1": _sample_item("R-1", "ok")})
        store.save("default", payload)
        original = (store.root / "default.json").read_text(encoding="utf-8")
        # Attempt to save an invalid payload — must raise without corrupting.
        with pytest.raises(RiskStoreCorruptError):
            store.save("default", {"version": 1, "register_id": "default", "items": ["bad"]})
        assert (store.root / "default.json").read_text(encoding="utf-8") == original


class TestTransaction:
    def test_transaction_commits_on_clean_exit(self, store: FileRiskStore) -> None:
        with store.transaction("default") as payload:
            payload["items"].append(_sample_item("R-9", "tx-commit").to_dict())
        loaded = store.load("default")
        assert any(item["id"] == "R-9" for item in loaded["items"])

    def test_transaction_rollback_on_exception(self, store: FileRiskStore) -> None:
        # Seed an existing payload to verify rollback leaves it intact.
        initial = store.items_to_payload("default", {"R-1": _sample_item("R-1", "stable")})
        store.save("default", initial)

        with pytest.raises(RuntimeError), store.transaction("default") as payload:
            payload["items"].append(_sample_item("R-2", "transient").to_dict())
            raise RuntimeError("boom")

        loaded = store.load("default")
        ids = [item["id"] for item in loaded["items"]]
        assert ids == ["R-1"]

    def test_transaction_releases_lock_after_error(self, store: FileRiskStore) -> None:
        with pytest.raises(RiskStoreError), store.transaction("default") as payload:
            payload["items"].append({"not": "valid"})
            # Forcing schema violation at exit time.
            payload["version"] = 99
        # The lock must be free for a new transaction immediately after exit.
        with store.transaction("default") as payload:
            payload["items"].append(_sample_item("R-after", "after-error").to_dict())
        loaded = store.load("default")
        assert any(item["id"] == "R-after" for item in loaded["items"])

    def test_transaction_payload_property_requires_active(self, store: FileRiskStore) -> None:
        tx = store.transaction("default")
        with pytest.raises(RiskStoreError):
            _ = tx.payload

    def test_transaction_is_mapping(self, store: FileRiskStore) -> None:
        with store.transaction("default") as payload:
            payload["version"] = SCHEMA_VERSION
            payload["register_id"] = "default"
            payload["items"] = []
            payload["new_key"] = "value"
            assert payload["new_key"] == "value"
            assert len(payload) >= 4


class TestLockTimeout:
    def test_lock_timeout_raises_after_deadline(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path, lock_timeout=0.2)
        # Acquire the lock externally to simulate a concurrent holder.
        blocker_path = tmp_path / "default.lock"
        blocker = open(blocker_path, "a+b")  # noqa: SIM115
        try:
            import fcntl

            fcntl.flock(blocker.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with pytest.raises(RiskStoreLockError):
                store.load("default")
        finally:
            fcntl.flock(blocker.fileno(), fcntl.LOCK_UN)
            blocker.close()

    def test_negative_lock_timeout_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            FileRiskStore(root=tmp_path, lock_timeout=-1.0)


class TestRegisterIntegration:
    def test_items_roundtrip_via_register(self, store: FileRiskStore) -> None:
        register = RiskRegister()
        register.add(risk_item=_sample_item("R-A", "alpha"))
        register.add(risk_item=_sample_item("R-B", "beta"))
        store.save("default", store.items_to_payload("default", register._items))

        payload = store.load("default")
        rebuilt = RiskRegister.from_items(store.payload_to_items(payload).values())
        assert {r.id for r in rebuilt.items()} == {"R-A", "R-B"}

    def test_from_store_factory(self, store: FileRiskStore) -> None:
        register = RiskRegister()
        register.add(risk_item=_sample_item("R-FACTORY", "from store"))
        store.save("default", store.items_to_payload("default", register._items))
        loaded = RiskRegister.from_store(store, "default")
        assert any(r.id == "R-FACTORY" for r in loaded.items())

    def test_riskitem_to_from_dict(self) -> None:
        item = _sample_item()
        rebuilt = RiskItem.from_dict(item.to_dict())
        assert rebuilt.id == item.id
        assert rebuilt.response_strategy == item.response_strategy
        assert rebuilt.status == item.status

    def test_register_to_from_dict(self) -> None:
        register = RiskRegister()
        register.add(risk_item=_sample_item("R-X", "x"))
        data = register.to_dict()
        rebuilt = RiskRegister.from_dict(data)
        assert {r.id for r in rebuilt.items()} == {"R-X"}

    def test_call_counter_incremented(self, store: FileRiskStore) -> None:
        before = get_call_counter_er()
        store.save("default", store.items_to_payload("default", {}))
        store.load("default")
        with store.transaction("default") as payload:
            payload["items"] = []
        assert get_call_counter_er() >= before + 3

    def test_transaction_exposes_register_id(self, store: FileRiskStore) -> None:
        with store.transaction("register-1") as payload:
            assert isinstance(payload, FileRiskStoreTransaction)
            assert payload.register_id == "register-1"
            assert payload["register_id"] == "register-1"
