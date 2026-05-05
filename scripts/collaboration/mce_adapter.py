#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCEAdapter — CarryMem (formerly MCE) Integration Adapter

Bridges DevSquad's MemoryBridge with CarryMem, the portable AI memory layer.
CarryMem is an EXTERNAL project — never modify its source code.

Design Principles:
  - CarryMem as optional dependency — auto-degrade on import failure
  - All calls wrapped in try/except — zero intrusion, no impact on main flow
  - Lazy initialization — no impact on cold start speed
  - Type mapping between DevSquad MemoryType and CarryMem memory types

CarryMem API Reference (v0.8+):
  - CarryMem() — main entry point (replaces old MemoryClassificationEngineFacade)
  - classify_message(text, context) → dict with entries
  - classify_and_remember(text, context) → dict with entries + stored keys
  - recall_memories(query, filters, limit) → list of dicts
  - forget_memory(memory_id) → bool
  - get_stats() → dict
  - whoami() → dict (user identity profile)
  - check_conflicts() → list of conflicts
  - check_quality(min_score) → list of low-quality memories

Memory Type Mapping (DevSquad ↔ CarryMem):
  DevSquad MemoryType  |  CarryMem Type
  --------------------+------------------
  KNOWLEDGE           |  fact_declaration
  EPISODIC            |  task_pattern
  SEMANTIC            |  sentiment_marker
  FEEDBACK            |  correction
  PATTERN             |  task_pattern
  ANALYSIS            |  decision
  CORRECTION          |  correction
  (no mapping)        |  user_preference
  (no mapping)        |  relationship

Example Usage:
    adapter = MCEAdapter(enable=True)
    if adapter.is_available:
        result = adapter.classify("User successfully logged in")
        print(result)  # MCEResult(memory_type='decision', confidence=0.92, ...)
    else:
        print("CarryMem unavailable, using default classification")
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re as _re
import unicodedata
import logging
import threading

logger = logging.getLogger(__name__)

CARRYMEM_TO_DEVOPSQUAD = {
    "user_preference": "knowledge",
    "correction": "correction",
    "fact_declaration": "knowledge",
    "decision": "analysis",
    "relationship": "knowledge",
    "task_pattern": "pattern",
    "sentiment_marker": "semantic",
}

DEVSQUAD_TO_CARRYMEM = {
    "knowledge": "fact_declaration",
    "episodic": "task_pattern",
    "semantic": "sentiment_marker",
    "feedback": "correction",
    "pattern": "task_pattern",
    "analysis": "decision",
    "correction": "correction",
}

RULE_TYPES = frozenset({"forbid", "avoid", "always", "prefer"})

_MAX_RULE_TEXT_LENGTH = 500
_USER_ID_BLOCKED_CHARS = _re.compile(r'[<>\'";&|`$\\]')

@dataclass
class MCEResult:
    memory_type: str = ""
    confidence: float = 0.0
    tier: str = "tier2"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "type": self.memory_type,
            "confidence": round(self.confidence, 4),
            "tier": self.tier,
            "metadata": self.metadata,
        }


@dataclass
class MCEStatus:
    available: bool = False
    version: str = ""
    init_error: Optional[str] = None
    classify_count: int = 0
    classify_fail_count: int = 0


class MCEAdapter:
    """
    CarryMem Integration Adapter

    Wraps CarryMem (memory_classification_engine.CarryMem) providing
    unified classify / store / retrieve interfaces.
    Gracefully degrades when CarryMem is not installed.

    Thread Safety: All public methods are thread-safe (internal RLock protection)
    """

    _instance = None
    _singleton_lock = threading.Lock()

    def __init__(self, enable: bool = False):
        self._lock = threading.RLock()
        self._status = MCEStatus()
        self._carrymem = None
        self._adapter_type = "none"

        if enable:
            self._try_init()

    def _try_init(self):
        with self._lock:
            try:
                from memory_classification_engine.integration.devsquad import DevSquadAdapter
                self._carrymem = DevSquadAdapter()
                self._status.available = True
                self._adapter_type = "devsquad_adapter"

                version = getattr(
                    __import__('memory_classification_engine'),
                    '__version__',
                    'unknown'
                )
                self._status.version = str(version)

            except ImportError:
                try:
                    from memory_classification_engine import CarryMem
                    self._carrymem = CarryMem()
                    self._status.available = True
                    self._adapter_type = "carrymem_legacy"

                    version = getattr(
                        __import__('memory_classification_engine'),
                        '__version__',
                        'unknown'
                    )
                    self._status.version = str(version)

                except ImportError as e:
                    self._status.available = False
                    self._status.init_error = f"CarryMem not installed: {e}"
                    self._adapter_type = "none"
                except (AttributeError, ModuleNotFoundError) as e:
                    self._status.available = False
                    self._status.init_error = f"CarryMem module error: {e}"
                    self._adapter_type = "none"
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Unexpected error initializing CarryMem: {type(e).__name__}: {e}"
                    )
                    self._status.available = False
                    self._status.init_error = f"{type(e).__name__}: {e}"
                    self._adapter_type = "none"
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Unexpected error in MCEAdapter init: {type(e).__name__}: {e}"
                )
                self._status.available = False
                self._status.init_error = f"{type(e).__name__}: {e}"
                self._adapter_type = "none"

    @property
    def is_available(self) -> bool:
        return self._status.available

    @property
    def status(self) -> MCEStatus:
        with self._lock:
            return MCEStatus(
                available=self._status.available,
                version=self._status.version,
                init_error=self._status.init_error,
                classify_count=self._status.classify_count,
                classify_fail_count=self._status.classify_fail_count,
            )

    def classify(self, text: str,
                  context: Optional[Dict] = None,
                  timeout_ms: int = 500) -> Optional[MCEResult]:
        with self._lock:
            if not self.is_available or not self._carrymem:
                self._status.classify_fail_count += 1
                return None

            try:
                import time as _time
                start = _time.time()
                raw_result = self._carrymem.classify_message(text, context)
                elapsed_ms = (_time.time() - start) * 1000

                if elapsed_ms > timeout_ms:
                    self._status.classify_fail_count += 1
                    return None

                result = self._normalize_result(raw_result)
                self._status.classify_count += 1
                return result

            except Exception as e:
                logger.debug("MCE classify failed: %s", e)
                self._status.classify_fail_count += 1
                return None

    def classify_batch(self,
                        texts: List[str],
                        context: Optional[Dict] = None) -> List[Optional[MCEResult]]:
        return [self.classify(t, context) for t in texts]

    def store_memory(self, memory_data: Dict) -> bool:
        with self._lock:
            if not self.is_available or not self._carrymem:
                return False
            try:
                message = memory_data.get("content", memory_data.get("message", ""))
                context = memory_data.get("context")
                if not message:
                    return False
                result = self._carrymem.classify_and_remember(message, context=context)
                return result.get("stored", False)
            except Exception as e:
                logger.debug("MCE store_memory failed: %s", e)
                return False

    def retrieve_memories(self,
                           query: str,
                           tier: str = "tier2",
                           limit: int = 20,
                           memory_type: Optional[str] = None) -> List[Dict]:
        with self._lock:
            if not self.is_available or not self._carrymem:
                return []
            try:
                filters = {}
                if memory_type:
                    carrymem_type = DEVSQUAD_TO_CARRYMEM.get(memory_type, memory_type)
                    filters["type"] = carrymem_type
                results = self._carrymem.recall_memories(
                    query=query, filters=filters or None, limit=limit,
                )
                return results if isinstance(results, list) else []
            except Exception as e:
                logger.debug("MCE retrieve_memories failed: %s", e)
                return []

    def whoami(self) -> Optional[Dict]:
        with self._lock:
            if not self.is_available or not self._carrymem:
                return None
            try:
                return self._carrymem.whoami()
            except Exception:
                return None

    def check_conflicts(self) -> List[Dict]:
        with self._lock:
            if not self.is_available or not self._carrymem:
                return []
            try:
                return self._carrymem.check_conflicts()
            except Exception:
                return []

    def shutdown(self):
        with self._lock:
            if self._carrymem and hasattr(self._carrymem, 'close'):
                try:
                    self._carrymem.close()
                except Exception:
                    pass
            self._carrymem = None
            self._status.available = False

    def force_reinit(self):
        self.shutdown()
        self._try_init()

    def get_stats(self) -> Dict[str, Any]:
        """Return memory statistics from CarryMem."""
        if not self.is_available or not self._carrymem:
            return {
                "total_users": 0,
                "total_rules": 0,
                "available": False,
                "adapter_type": self._adapter_type,
            }
        with self._lock:
            try:
                if hasattr(self._carrymem, 'get_stats'):
                    return self._carrymem.get_stats()
            except Exception:
                pass
            return {
                "total_users": 0,
                "total_rules": 0,
                "available": self.is_available,
                "adapter_type": self._adapter_type,
            }

    @staticmethod
    def _sanitize_user_id(user_id: str) -> str:
        """Sanitize user_id to prevent injection attacks.

        CarryMem trusts caller-provided user_id without authentication.
        DevSquad must ensure user_id is safe before passing it.
        """
        if not user_id:
            return "default"
        normalized = unicodedata.normalize('NFKC', str(user_id))
        sanitized = _USER_ID_BLOCKED_CHARS.sub('_', normalized)
        while '../' in sanitized or '..\\' in sanitized:
            sanitized = sanitized.replace('../', '_').replace('..\\', '_')
        sanitized = sanitized.replace('/', '_').replace('\\', '_')
        sanitized = sanitized.strip()[:128]
        return sanitized or "default"

    def match_rules(self, task_description: str, user_id: str,
                     role: Optional[str] = None, max_rules: int = 5) -> List[Dict[str, Any]]:
        """Match rules based on task description and role.

        Calls DevSquadAdapter.match_rules() when available (CarryMem v0.2.8+).
        Falls back to CarryMem legacy API, then keyword-based matching.
        """
        safe_user_id = self._sanitize_user_id(user_id)

        if not self.is_available or not self._carrymem:
            return self._keyword_fallback_match(task_description, safe_user_id, role, max_rules)

        with self._lock:
            try:
                if hasattr(self._carrymem, 'match_rules'):
                    result = self._carrymem.match_rules(
                        task_description=task_description,
                        user_id=safe_user_id,
                        role=role,
                        max_rules=max_rules
                    )
                else:
                    return self._keyword_fallback_match(task_description, safe_user_id, role, max_rules)
                if isinstance(result, list):
                    return self._normalize_matched_rules(result)
                return []
            except Exception as e:
                logger.warning("CarryMem match_rules failed: %s", e)
                return self._keyword_fallback_match(task_description, safe_user_id, role, max_rules)

    def format_rules_as_prompt(self, rules: List[Dict[str, Any]]) -> str:
        """Format matched rules as injectable prompt text.

        Calls DevSquadAdapter.format_rules_as_prompt() when available (CarryMem v0.2.8+).
        Falls back to simple formatting when CarryMem is unavailable.
        """
        if not rules:
            return ""

        for rule in rules:
            for key in ("action", "trigger"):
                text = rule.get(key, "")
                if isinstance(text, str) and len(text) > _MAX_RULE_TEXT_LENGTH:
                    rule[key] = text[:_MAX_RULE_TEXT_LENGTH]

        if not self.is_available or not self._carrymem:
            return self._format_rules_fallback(rules)

        with self._lock:
            try:
                if hasattr(self._carrymem, 'format_rules_as_prompt'):
                    return self._carrymem.format_rules_as_prompt(rules)
                return self._format_rules_fallback(rules)
            except Exception as e:
                logger.warning("CarryMem format_rules_as_prompt failed: %s", e)
                return self._format_rules_fallback(rules)

    def add_rule(self, trigger: str, action: str, rule_type: str = "always",
                 confidence: float = 0.8) -> Optional[Dict[str, Any]]:
        """Add a rule to CarryMem or local storage.

        Uses DevSquadAdapter.add_rule() when available (CarryMem v0.2.8+).
        Falls back to local storage when CarryMem is unavailable.
        """
        if rule_type not in ("always", "avoid", "prefer", "forbid"):
            rule_type = "always"

        if self.is_available and self._carrymem:
            with self._lock:
                try:
                    if hasattr(self._carrymem, 'add_rule'):
                        return self._carrymem.add_rule(
                            trigger=trigger, action=action,
                            rule_type=rule_type, confidence=confidence,
                        )
                except Exception as e:
                    logger.warning("CarryMem add_rule failed: %s", e)

        logger.info("CarryMem add_rule unavailable, storing locally")
        try:
            from scripts.collaboration.rule_collector import RuleData, LocalRuleStorage
            storage = LocalRuleStorage()
            rule = RuleData(
                trigger=trigger, action=action, type=rule_type,
                confidence=confidence, source="mce_adapter_fallback",
            )
            result = storage.store(rule)
            if result.success:
                return {"rule_id": result.rule_id, "storage": "local_fallback",
                        "type": rule_type, "success": True}
        except Exception as e:
            logger.error("Local fallback store failed: %s", e)
        return {"rule_id": f"RULE-LOCAL-{uuid.uuid4().hex[:12]}",
                "storage": "local_fallback", "type": rule_type, "success": False}

    def _keyword_fallback_match(self, task_description: str, user_id: str,
                                 role: Optional[str] = None,
                                 max_rules: int = 5) -> List[Dict[str, Any]]:
        """Keyword-based rule matching fallback when CarryMem is unavailable."""
        try:
            all_rules = self._get_all_rules_raw(user_id, role)
        except Exception:
            return []

        if not all_rules:
            return []

        desc_lower = task_description.lower()
        desc_words = set(desc_lower.split())

        scored = []
        for rule in all_rules:
            trigger = rule.get("trigger", "").lower()
            action = rule.get("action", "").lower()
            trigger_words = set(trigger.split())
            overlap = len(desc_words & trigger_words)
            if trigger and trigger in desc_lower:
                overlap += 2
            if overlap > 0:
                rule_copy = dict(rule)
                rule_copy["relevance_score"] = min(1.0, overlap / max(len(trigger_words), 1))
                scored.append(rule_copy)

        scored.sort(key=lambda r: r.get("relevance_score", 0.0), reverse=True)
        return scored[:max_rules]

    def _get_all_rules_raw(self, user_id: str, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all rules as raw dicts for keyword fallback matching."""
        if not self.is_available or not self._carrymem:
            return []

        with self._lock:
            try:
                context = {}
                if role:
                    context["role"] = role
                rules_str = self._carrymem.get_rules(user_id=user_id, context=context)
                if not isinstance(rules_str, list):
                    return []
                return [self._parse_rule_string(r) for r in rules_str if isinstance(r, str)]
            except Exception:
                return []

    @staticmethod
    def _parse_rule_string(rule_str: str) -> Dict[str, Any]:
        """Parse a prefixed rule string into a structured dict.

        Format: "[TYPE] Description text (override)"
        """
        result: Dict[str, Any] = {
            "rule_type": "always",
            "trigger": "",
            "action": rule_str,
            "relevance_score": 0.0,
            "rule_id": "",
            "override": False,
        }

        stripped = rule_str.strip()
        type_match = _re.match(r'^\[(FORBID|AVOID|ALWAYS)\]\s*', stripped, _re.IGNORECASE)
        if type_match:
            type_str = type_match.group(1).lower()
            if type_str in RULE_TYPES:
                result["rule_type"] = type_str
            stripped = stripped[type_match.end():]

        if stripped.endswith("(override)"):
            result["override"] = True
            stripped = stripped[:-len("(override)")].strip()

        result["action"] = stripped
        result["trigger"] = stripped.lower()
        return result

    @staticmethod
    def _format_rules_fallback(rules: List[Dict[str, Any]]) -> str:
        """Simple rule formatting fallback when CarryMem is unavailable."""
        if not rules:
            return ""

        parts = ["=== Applicable Rules ==="]
        for rule in rules:
            rule_type = rule.get("rule_type", "always").upper()
            action = rule.get("action", "")
            override = " (non-overridable)" if rule.get("override") else ""
            parts.append(f"[{rule_type}] {action}{override}")
        parts.append("")
        return "\n".join(parts)

    @staticmethod
    def _normalize_matched_rules(rules: List[Any]) -> List[Dict[str, Any]]:
        """Normalize CarryMem rule objects into standard dict format."""
        normalized = []
        for rule in rules:
            if isinstance(rule, dict):
                rule_type = rule.get("rule_type", rule.get("type", "always"))
                if rule_type not in RULE_TYPES:
                    rule_type = "always"
                normalized.append({
                    "rule_type": rule_type,
                    "trigger": rule.get("trigger", ""),
                    "action": rule.get("action", rule.get("description", "")),
                    "relevance_score": float(rule.get("relevance_score", rule.get("score", 0.0))),
                    "rule_id": str(rule.get("rule_id", rule.get("id", ""))),
                    "override": bool(rule.get("override", False)),
                })
        return normalized

    @staticmethod
    def _normalize_result(raw: Any) -> MCEResult:
        if raw is None:
            return MCEResult()

        if isinstance(raw, dict):
            entries = raw.get("entries", [])
            if entries:
                first = entries[0] if isinstance(entries[0], dict) else {}
                mt = first.get("type", first.get("memory_type", "general"))
                carrymem_type = str(mt)
                devsqu_type = CARRYMEM_TO_DEVOPSQUAD.get(carrymem_type, carrymem_type)
                conf = first.get("confidence", 0.0)
                if isinstance(conf, (int, float)):
                    conf = min(max(float(conf), 0.0), 1.0)
                else:
                    try:
                        conf = float(str(conf))
                    except (ValueError, TypeError):
                        conf = 0.5
                tier = first.get("tier", 2)
                tier_str = f"tier{tier}" if isinstance(tier, int) else str(tier)
                meta = {k: v for k, v in first.items()
                         if k not in ('type', 'memory_type', 'confidence', 'tier')}
                meta["carrymem_type"] = carrymem_type
                return MCEResult(
                    memory_type=devsqu_type,
                    confidence=conf,
                    tier=tier_str,
                    metadata=meta,
                )
            should_remember = raw.get("should_remember", False)
            return MCEResult(
                memory_type="general",
                confidence=0.5,
                metadata={"should_remember": should_remember},
            )

        if isinstance(raw, str):
            devsqu_type = CARRYMEM_TO_DEVOPSQUAD.get(raw, raw)
            return MCEResult(memory_type=devsqu_type)

        return MCEResult(metadata={"raw": str(raw)[:200]})


def get_global_mce_adapter(enable: bool = False) -> MCEAdapter:
    if MCEAdapter._instance is None:
        with MCEAdapter._singleton_lock:
            if MCEAdapter._instance is None:
                MCEAdapter._instance = MCEAdapter(enable=enable)
    return MCEAdapter._instance
