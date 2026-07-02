#!/usr/bin/env python3
"""
LearnedRuleStore — Two-tier rule persistence (V3.10.0 Phase 4).

Tier 1 (confidence >= 0.8): written to ``.devsquad.yaml`` under
``quality_control.learned_rules`` and auto-injected into prompts by
PromptAssembler.

Tier 2 (confidence 0.5-0.8): written to ``data/tier2/corrections.json``
candidate pool for manual review. Rules below 0.5 are rejected.

Spec: docs/spec/v3.10.0_spec.md §5.7

Design:
- Tier 1: YAML read/write (preserves human-editable format)
- Tier 2: JSON append-only with dedup by rule_text hash
- Thread-safe: ``threading.Lock``
- No external dependencies (stdlib only — ponytail rule)
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any

import yaml

from .models_base import LearnedRule

logger = logging.getLogger(__name__)

DEFAULT_TIER2_PATH = "data/tier2/corrections.json"
DEFAULT_CONFIG_PATH = ".devsquad.yaml"


class LearnedRuleStore:
    """Two-tier persistence for LearnedRule entries.

    Usage:
        store = LearnedRuleStore()
        store.add_rule(LearnedRule(
            rule_text="Always prefer pathlib over os.path",
            trigger_condition="file_path_manipulation",
            confidence=0.85,
            source_task_id="task_001",
        ))
        # Tier 1 rules auto-injected via PromptAssembler on next dispatch
    """

    def __init__(
        self,
        config_path: str = DEFAULT_CONFIG_PATH,
        tier2_path: str = DEFAULT_TIER2_PATH,
    ) -> None:
        self._config_path = Path(config_path)
        self._tier2_path = Path(tier2_path)
        self._lock = threading.Lock()

    def add_rule(self, rule: LearnedRule) -> str:
        """Persist a rule to the appropriate tier.

        Args:
            rule: The LearnedRule to persist.

        Returns:
            Storage outcome: ``"tier1"``, ``"tier2"``, or ``"rejected"``.
        """
        with self._lock:
            tier = rule.tier
            if tier == "tier1":
                self._write_tier1(rule)
                logger.info(
                    "LearnedRule added to tier1 (confidence=%.2f): %s",
                    rule.confidence,
                    rule.rule_text[:60],
                )
            elif tier == "tier2":
                self._write_tier2(rule)
                logger.info(
                    "LearnedRule added to tier2 candidate pool (confidence=%.2f): %s",
                    rule.confidence,
                    rule.rule_text[:60],
                )
            else:
                logger.debug(
                    "LearnedRule rejected (confidence=%.2f < 0.5): %s",
                    rule.confidence,
                    rule.rule_text[:60],
                )
            return tier

    def load_tier1_rules(self) -> list[LearnedRule]:
        """Load tier-1 rules from ``.devsquad.yaml``.

        Returns:
            List of LearnedRule entries with confidence >= 0.8.
        """
        if not self._config_path.exists():
            return []
        try:
            with self._config_path.open("r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            rules_data = config.get("quality_control", {}).get("learned_rules", [])
            return [LearnedRule.from_dict(r) for r in rules_data if isinstance(r, dict)]
        except (OSError, yaml.YAMLError, ValueError, TypeError) as e:
            logger.warning("Failed to load tier1 rules from %s: %s", self._config_path, e)
            return []

    def load_tier2_rules(self) -> list[LearnedRule]:
        """Load tier-2 candidate rules from ``data/tier2/corrections.json``.

        Returns:
            List of LearnedRule entries with confidence 0.5-0.8.
        """
        if not self._tier2_path.exists():
            return []
        try:
            with self._tier2_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            rules_data = data.get("rules", []) if isinstance(data, dict) else data
            return [LearnedRule.from_dict(r) for r in rules_data if isinstance(r, dict)]
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning("Failed to load tier2 rules from %s: %s", self._tier2_path, e)
            return []

    def promote_tier2_to_tier1(self, rule_text: str) -> bool:
        """Promote a tier-2 candidate to tier-1 by rule_text match.

        Args:
            rule_text: Exact rule_text of the candidate to promote.

        Returns:
            True if a candidate was found, promoted, and removed from tier2.
        """
        with self._lock:
            tier2_rules = self._read_tier2_raw()
            target: dict[str, Any] | None = None
            remaining: list[dict[str, Any]] = []
            for r in tier2_rules:
                if r.get("rule") == rule_text and target is None:
                    target = r
                else:
                    remaining.append(r)
            if target is None:
                return False
            target["confidence"] = max(float(target.get("confidence", 0.5)), 0.8)
            self._write_tier1_raw(target)
            self._write_tier2_raw(remaining)
            logger.info("Promoted tier2 rule to tier1: %s", rule_text[:60])
            return True

    def _write_tier1(self, rule: LearnedRule) -> None:
        self._write_tier1_raw(rule.to_dict())

    def _write_tier1_raw(self, rule_dict: dict[str, Any]) -> None:
        config: dict[str, Any] = {}
        if self._config_path.exists():
            try:
                with self._config_path.open("r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
            except (OSError, yaml.YAMLError) as e:
                logger.warning("Failed to read %s for tier1 write: %s", self._config_path, e)
        qc = config.setdefault("quality_control", {})
        rules = qc.setdefault("learned_rules", [])
        rule_hash = hashlib.sha256(rule_dict.get("rule", "").encode()).hexdigest()[:16]
        if any(hashlib.sha256(r.get("rule", "").encode()).hexdigest()[:16] == rule_hash for r in rules if isinstance(r, dict)):
            logger.debug("Tier1 rule already exists (hash=%s), skip", rule_hash)
            return
        rules.append(rule_dict)
        with self._config_path.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _write_tier2(self, rule: LearnedRule) -> None:
        rules = self._read_tier2_raw()
        rule_hash = hashlib.sha256(rule.rule_text.encode()).hexdigest()[:16]
        if any(hashlib.sha256(r.get("rule", "").encode()).hexdigest()[:16] == rule_hash for r in rules if isinstance(r, dict)):
            logger.debug("Tier2 rule already exists (hash=%s), skip", rule_hash)
            return
        rules.append(rule.to_dict())
        self._write_tier2_raw(rules)

    def _read_tier2_raw(self) -> list[dict[str, Any]]:
        if not self._tier2_path.exists():
            return []
        try:
            with self._tier2_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            rules = data.get("rules", []) if isinstance(data, dict) else data
            return list(rules) if isinstance(rules, list) else []
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to read tier2 file %s: %s", self._tier2_path, e)
            return []

    def _write_tier2_raw(self, rules: list[dict[str, Any]]) -> None:
        self._tier2_path.parent.mkdir(parents=True, exist_ok=True)
        with self._tier2_path.open("w", encoding="utf-8") as f:
            json.dump({"rules": rules}, f, ensure_ascii=False, indent=2)
