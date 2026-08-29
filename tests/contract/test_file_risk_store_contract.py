"""Contract tests for FileRiskStore (V4.5.8 Wave 1).

Coverage focus (≥4 cases):
- JSON schema v1 invariants (top-level fields, register_id echo, items list).
- RiskItem ↔ JSON roundtrip preserves semantics.
- Transaction behaves as a Mapping[str, Any] context manager.
- Public surface is stable for downstream callers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.collaboration import file_risk_store as frs
from scripts.collaboration.file_risk_store import (
    DEFAULT_ROOT,
    SCHEMA_VERSION,
    FileRiskStore,
    FileRiskStoreTransaction,
    RiskStoreCorruptError,
    RiskStoreError,
    RiskStoreLockError,
    RiskStoreValidationError,
)
from scripts.collaboration.risk_register import (
    ResponseStrategy,
    RiskItem,
    RiskRegister,
    RiskStatus,
)

pytestmark = pytest.mark.contract


REQUIRED_TOP_LEVEL = {"version", "register_id", "items"}
REQUIRED_ITEM_KEYS = {
    "id",
    "description",
    "probability",
    "impact",
    "response_strategy",
    "owner",
    "status",
    "category",
}


@pytest.fixture
def store(tmp_path: Path) -> FileRiskStore:
    return FileRiskStore(root=tmp_path, lock_timeout=1.0)


def _sample_item(rid: str = "R-1", desc: str = "schema check") -> RiskItem:
    return RiskItem(
        id=rid,
        description=desc,
        probability=0.5,
        impact=0.5,
        response_strategy=ResponseStrategy.AVOID,
        owner="architect",
        status=RiskStatus.MITIGATING,
        category="security",
    )


class TestJsonSchemaContract:
    def test_schema_v1_invariants(self, store: FileRiskStore) -> None:
        payload = store.items_to_payload("default", {"R-1": _sample_item()})
        assert payload["version"] == SCHEMA_VERSION
        assert payload["register_id"] == "default"
        assert isinstance(payload["items"], list)
        assert set(payload) == REQUIRED_TOP_LEVEL

    def test_item_schema_keys(self, store: FileRiskStore) -> None:
        payload = store.items_to_payload("default", {"R-1": _sample_item()})
        assert set(payload["items"][0]) == REQUIRED_ITEM_KEYS

    def test_enum_values_are_lowercase_strings(self, store: FileRiskStore) -> None:
        payload = store.items_to_payload("default", {"R-1": _sample_item()})
        item = payload["items"][0]
        assert item["response_strategy"] == "avoid"
        assert item["status"] == "mitigating"

    def test_persisted_file_is_valid_json_v1(self, store: FileRiskStore, tmp_path: Path) -> None:
        payload = store.items_to_payload("default", {"R-1": _sample_item()})
        store.save("default", payload)
        on_disk = json.loads((tmp_path / "default.json").read_text(encoding="utf-8"))
        assert on_disk["version"] == SCHEMA_VERSION
        assert on_disk["register_id"] == "default"
        assert on_disk["items"][0]["id"] == "R-1"


class TestRiskItemRoundtrip:
    def test_riskitem_roundtrip_preserves_all_fields(self, store: FileRiskStore) -> None:
        item = _sample_item()
        rebuilt = RiskItem.from_dict(item.to_dict())
        for field in ("id", "description", "probability", "impact", "owner", "category"):
            assert getattr(rebuilt, field) == getattr(item, field)
        assert rebuilt.response_strategy == item.response_strategy
        assert rebuilt.status == item.status

    def test_riskregister_roundtrip_via_payload(self, store: FileRiskStore) -> None:
        register = RiskRegister()
        register.add(risk_item=_sample_item("R-A", "alpha"))
        register.add(risk_item=_sample_item("R-B", "beta"))
        payload = store.items_to_payload("default", register._items)
        rebuilt_items = list(store.payload_to_items(payload).values())
        assert {r.id for r in rebuilt_items} == {"R-A", "R-B"}
        assert all(isinstance(r, RiskItem) for r in rebuilt_items)


class TestTransactionContract:
    def test_transaction_is_mapping(self, store: FileRiskStore) -> None:
        with store.transaction("default") as payload:
            assert isinstance(payload, FileRiskStoreTransaction)
            assert payload["version"] == SCHEMA_VERSION
            payload["new_marker"] = 1
            assert payload["new_marker"] == 1
            del payload["new_marker"]
            assert "new_marker" not in payload
            assert set(payload.keys()) >= {"version", "register_id", "items"}

    def test_transaction_payload_attribute_matches_dict(self, store: FileRiskStore) -> None:
        with store.transaction("default") as payload:
            assert payload.payload == dict(payload)
            assert payload.payload["register_id"] == "default"

    def test_transaction_rollback_preserves_payload(self, store: FileRiskStore) -> None:
        original = store.items_to_payload("default", {"R-1": _sample_item("R-1", "stable")})
        store.save("default", original)
        with pytest.raises(RuntimeError), store.transaction("default") as payload:
            payload["items"].append(_sample_item("R-2", "transient").to_dict())
            raise RuntimeError("boom")
        # The persisted payload must remain untouched.
        loaded = store.load("default")
        ids = [item["id"] for item in loaded["items"]]
        assert ids == ["R-1"]


class TestPublicSurfaceContract:
    def test_module_exports_are_stable(self) -> None:
        for name in (
            "DEFAULT_ROOT",
            "FileRiskStore",
            "FileRiskStoreTransaction",
            "RiskStoreCorruptError",
            "RiskStoreError",
            "RiskStoreLockError",
            "RiskStoreValidationError",
            "SCHEMA_VERSION",
            "get_call_counter_er",
        ):
            assert hasattr(frs, name), name

    def test_error_hierarchy(self) -> None:
        assert issubclass(RiskStoreValidationError, RiskStoreError)
        assert issubclass(RiskStoreCorruptError, RiskStoreError)
        assert issubclass(RiskStoreLockError, RiskStoreError)

    def test_default_root_path(self) -> None:
        assert str(DEFAULT_ROOT) == ".devsquad_data/risks"

    def test_transaction_payload_outside_with_block(self, store: FileRiskStore) -> None:
        tx = store.transaction("default")
        # Accessing payload before entering the context must fail.
        with pytest.raises(RiskStoreError):
            _ = tx.payload

    def test_save_rejects_payload_with_wrong_register_id(self, store: FileRiskStore) -> None:
        bad: dict[str, Any] = {"version": 1, "register_id": "other", "items": []}
        with pytest.raises(RiskStoreCorruptError):
            store.save("default", bad)
