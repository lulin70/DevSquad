#!/usr/bin/env python3
"""
RuleCollector — Natural Language Rule Collection Module

Intercepts user input to detect rule-storing intent, extracts structured
rule data, sanitizes content, and stores via CarryMem or local JSON fallback.

Integration point: Called by MultiAgentDispatcher.dispatch() before role matching.

Pipeline:
    User Input → IntentDetector → RuleExtractor → RuleSanitizer → RuleStorage
                 (detect intent)   (extract rule)  (security check)  (persist)

Author: DevSquad Team
Version: 3.7.0
"""

import json
import logging
import os
import re
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, cast

logger = logging.getLogger(__name__)

MAX_TRIGGER_LENGTH = 200
MAX_ACTION_LENGTH = 500
MIN_TRIGGER_LENGTH = 2
MIN_ACTION_LENGTH = 5
VALID_RULE_TYPES = ("always", "avoid", "prefer", "forbid")
RULE_TYPE_PRIORITY = {"forbid": 3, "always": 2, "avoid": 1, "prefer": 0}

INTENT_PATTERNS = [
    {"id": "INT-01", "regex": r"记住.*规则", "weight": 1.0, "type_hint": None},
    {"id": "INT-02", "regex": r"添加.*规则", "weight": 1.0, "type_hint": None},
    {"id": "INT-03", "regex": r"我的.*偏好", "weight": 0.9, "type_hint": "prefer"},
    {"id": "INT-04", "regex": r"(总是|必须|应该).*要", "weight": 0.85, "type_hint": "always"},
    {"id": "INT-05", "regex": r"(禁止|不要|不能).*(用|做)", "weight": 0.95, "type_hint": "forbid"},
    {"id": "INT-06", "regex": r"记住这条规则", "weight": 1.0, "type_hint": None},
    {"id": "INT-07", "regex": r"(避免|尽量不|最好不要)", "weight": 0.85, "type_hint": "avoid"},
    {"id": "INT-08", "regex": r"(偏好|喜欢|倾向于|优先)", "weight": 0.85, "type_hint": "prefer"},
    {"id": "INT-09", "regex": r"团队规范", "weight": 0.9, "type_hint": "always"},
    {"id": "INT-10", "regex": r"列出.*规则|查看.*规则|我的规则", "weight": 1.0, "type_hint": "_list"},
    {"id": "INT-11", "regex": r"删除.*规则|忘记.*规则|移除.*规则", "weight": 1.0, "type_hint": "_delete"},
]

EXTRACTION_PATTERNS = [
    {
        "id": "EXT-01",
        "regex": r"记住.*规则[:：]\s*(.+?)(?:时|前|后|的时候|情况下)[，,]?\s*(.+)",
        "trigger_group": 1,
        "action_group": 2,
    },
    {
        "id": "EXT-02",
        "regex": r"添加规则[:：]\s*(.+?)(?:前必须|时必须|后必须|前要|时要|后要)\s*(.+)",
        "trigger_group": 1,
        "action_group": 2,
    },
    {
        "id": "EXT-03",
        "regex": r"我的偏好[:：]\s*(.+?)(?:而不是|而非|而不是用)\s*(.+)",
        "trigger_group": 2,
        "action_group": 1,
    },
    {
        "id": "EXT-04",
        "regex": r"(禁止|不要|不能)\s*(.+?)(?:时|的时候|中)\s*(.+)",
        "trigger_group": 2,
        "action_group": 3,
    },
    {
        "id": "EXT-05",
        "regex": r"(总是|必须|应该)\s*(.+?)(?:当|在)\s*(.+?)(?:时|的时候)",
        "trigger_group": 3,
        "action_group": 2,
    },
    {"id": "EXT-06", "regex": r"记住.*规则[:：]\s*(.+)", "trigger_group": None, "action_group": 1},
    {"id": "EXT-07", "regex": r"团队规范[:：]\s*(.+)", "trigger_group": None, "action_group": 1},
]

TYPE_KEYWORDS = {
    "always": ["必须", "总是", "应该", "要", "一定", "务必"],
    "avoid": ["避免", "尽量不", "最好不要", "不建议"],
    "prefer": ["偏好", "喜欢", "倾向于", "优先", "更愿意"],
    "forbid": ["禁止", "不要", "不能", "绝不", "严禁"],
}

DANGEROUS_PATTERNS = [
    re.compile(r"os\.system", re.IGNORECASE),
    re.compile(r"subprocess\.", re.IGNORECASE),
    re.compile(r"exec\s*\(", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"rm\s+-rf", re.IGNORECASE),
    re.compile(r"__import__", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"DELETE\s+FROM", re.IGNORECASE),
    re.compile(r"import\s+os\b"),
    re.compile(r"import\s+subprocess\b"),
]

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+(instructions?|rules?|prompts?)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(above|previous|prior)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a\s+)?(?:DAN|jailbreak|unrestricted)", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"override\s+(all\s+)?safety", re.IGNORECASE),
    re.compile(r"(?:忽略|无视|忘记)(?:所有|全部)?(?:之前的|上面的)?(?:指令|规则|提示)", re.IGNORECASE),
    re.compile(r"你(?:现在|已经)?是(?:一个)?(?:不受限|越狱|DAN)", re.IGNORECASE),
    re.compile(r"(?:act|pretend|roleplay)\s+(?:as|to\s+be)", re.IGNORECASE),
    re.compile(r"(?:new|updated|changed)\s+instructions?\s*[:：]", re.IGNORECASE),
    re.compile(
        r"(?:output|reveal|show|print|display)\s+(?:your|the|my)\s+(?:system|initial|original)\s+(?:prompt|instructions?)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:developer|admin|sudo|root|debug)\s+mode", re.IGNORECASE),
    re.compile(r"above\s+all\s+else", re.IGNORECASE),
    re.compile(r"most\s+important\s+rule", re.IGNORECASE),
]

_RULE_PARTICLE_RE = re.compile(
    r"(?:记住.*规则[:：]|添加规则[:：]|我的偏好[:：]|团队规范[:：]"
    r"|禁止[^，。？\n]{1,30}(?:做|使用|执行)?"
    r"|避免[^，。？\n]{1,30}"
    r"|必须[^，。？\n]{1,30}"
    r"|不要[^，。？\n]{1,30}"
    r"|不可以[^，。？\n]{1,30}"
    r"|务必[^，。？\n]{1,30}"
    r"|always\s+[^，。？\n]{1,30}"
    r"|never\s+[^，。？\n]{1,30}"
    r"|forbid[^，。？\n]{1,30}"
    r"|avoid\s+[^，。？\n]{1,30})"
    r".*?(?:[，。？！,\.!\?]|$|\n)",
    re.IGNORECASE,
)


@dataclass
class IntentResult:
    is_detected: bool = False
    pattern_id: str | None = None
    confidence: float = 0.0
    matched_span: tuple[int, int] | None = None
    type_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleData:
    trigger: str = ""
    action: str = ""
    type: str = "always"
    confidence: float = 0.0
    source: str = "natural_language"
    raw_text: str = ""
    rule_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    success: bool = False
    rule_data: RuleData | None = None
    alternatives: list[RuleData] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class StoreResult:
    success: bool = False
    rule_id: str | None = None
    storage_method: str = ""
    timestamp: str = ""
    message: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class CollectionResult:
    rule_detected: bool = False
    rule_result: StoreResult | None = None
    remaining_task: str = ""
    list_rules: list[dict[str, Any]] | None = None
    delete_result: bool | None = None
    message: str = ""


class IntentDetector:
    """Detect rule-storing intent from user input using regex patterns."""

    def __init__(self, sensitivity: float = 0.85):
        self.patterns = INTENT_PATTERNS
        self.sensitivity = sensitivity
        self._compiled = [
            {
                "id": p["id"],
                "regex": re.compile(p["regex"], re.IGNORECASE),
                "weight": p["weight"],
                "type_hint": p["type_hint"],
            }
            for p in self.patterns
        ]

    def detect(self, text: str) -> IntentResult:
        """Detect whether the input text contains a rule-creation intent.

        Args:
            text: Natural language input from the user.

        Returns:
            IntentResult describing the best-matching pattern; is_detected is False
            when no pattern exceeds the configured sensitivity threshold.
        """
        if not text or len(text) < 3:
            return IntentResult()

        best_score = 0.0
        best_pattern = None
        best_match = None

        for p in self._compiled:
            m = p["regex"].search(text)
            if m:
                score = p["weight"]
                if score > best_score:
                    best_score = score
                    best_pattern = p
                    best_match = m

        if best_score < self.sensitivity or best_pattern is None:
            return IntentResult(is_detected=False, confidence=best_score)

        assert best_match is not None
        return IntentResult(
            is_detected=True,
            pattern_id=best_pattern["id"],
            confidence=best_score,
            matched_span=(best_match.start(), best_match.end()),
            type_hint=best_pattern["type_hint"],
        )


class RuleExtractor:
    """Extract structured rule data from natural language input."""

    def __init__(self) -> None:
        self.extraction_patterns: list[dict[str, Any]] = cast(list[dict[str, Any]], EXTRACTION_PATTERNS)
        self._compiled = [
            {
                "id": p["id"],
                "regex": re.compile(p["regex"], re.IGNORECASE),
                "trigger_group": p["trigger_group"],
                "action_group": p["action_group"],
            }
            for p in self.extraction_patterns
        ]

    def extract(self, text: str, intent: IntentResult) -> ExtractionResult:
        """Extract a structured RuleData (trigger/action/type) from natural language.

        Args:
            text: Original natural language input.
            intent: IntentResult previously produced by IntentDetector.detect.

        Returns:
            ExtractionResult with the best-scoring RuleData, or success=False with
            warnings when no extraction pattern matches.
        """
        if not intent.is_detected:
            return ExtractionResult()

        best_result = None
        best_confidence = 0.0
        warnings = []

        for p in self._compiled:
            m = p["regex"].search(text)
            if not m:
                continue

            try:
                trigger = m.group(p["trigger_group"]).strip() if p["trigger_group"] is not None else ""
                action = m.group(p["action_group"]).strip()
            except (IndexError, AttributeError):
                continue

            rule_type = self._infer_type(text, intent.type_hint)
            confidence = self._calculate_confidence(trigger, action, rule_type, intent.confidence)

            if confidence > best_confidence:
                best_confidence = confidence
                best_result = RuleData(
                    trigger=trigger,
                    action=action,
                    type=rule_type,
                    confidence=confidence,
                    source="natural_language",
                    raw_text=text,
                )

        if best_result is None:
            warnings.append("Could not extract structured rule from input")
            return ExtractionResult(success=False, warnings=warnings)

        if len(best_result.trigger) < MIN_TRIGGER_LENGTH:
            warnings.append(f"Trigger too short (min {MIN_TRIGGER_LENGTH} chars)")
        if len(best_result.action) < MIN_ACTION_LENGTH:
            warnings.append(f"Action too short (min {MIN_ACTION_LENGTH} chars)")

        return ExtractionResult(
            success=True,
            rule_data=best_result,
            warnings=warnings,
        )

    def _infer_type(self, text: str, hint: str | None) -> str:
        if hint and hint in VALID_RULE_TYPES:
            return hint

        for rule_type, keywords in TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return rule_type

        return "always"

    def _calculate_confidence(self, trigger: str, action: str, rule_type: str, intent_conf: float) -> float:
        score = intent_conf * 0.5
        if len(trigger) >= MIN_TRIGGER_LENGTH:
            score += 0.2
        if len(action) >= MIN_ACTION_LENGTH:
            score += 0.2
        if rule_type in VALID_RULE_TYPES:
            score += 0.1
        return min(1.0, score)


class RuleSanitizer:
    """Sanitize rule content to prevent security issues."""

    @staticmethod
    def sanitize(rule: RuleData) -> tuple[RuleData, list[str]]:
        """Sanitize a rule by redacting dangerous patterns and enforcing length limits.

        Args:
            rule: RuleData to sanitize in place.

        Returns:
            Tuple of (sanitized RuleData, list of warning strings describing each
            redaction/truncation applied).
        """
        warnings = []

        for pat in DANGEROUS_PATTERNS:
            if pat.search(rule.action):
                warnings.append("Dangerous pattern detected in rule action")
                rule.action = pat.sub("[REDACTED]", rule.action)

        for pat in DANGEROUS_PATTERNS:
            if pat.search(rule.trigger):
                warnings.append("Dangerous pattern detected in rule trigger")
                rule.trigger = pat.sub("[REDACTED]", rule.trigger)

        for pat in PROMPT_INJECTION_PATTERNS:
            if pat.search(rule.action):
                warnings.append("Prompt injection pattern detected in rule action")
                rule.action = pat.sub("[REDACTED]", rule.action)

        for pat in PROMPT_INJECTION_PATTERNS:
            if pat.search(rule.trigger):
                warnings.append("Prompt injection pattern detected in rule trigger")
                rule.trigger = pat.sub("[REDACTED]", rule.trigger)

        if len(rule.trigger) > MAX_TRIGGER_LENGTH:
            warnings.append(f"Trigger truncated from {len(rule.trigger)} to {MAX_TRIGGER_LENGTH}")
            rule.trigger = rule.trigger[:MAX_TRIGGER_LENGTH]

        if len(rule.action) > MAX_ACTION_LENGTH:
            warnings.append(f"Action truncated from {len(rule.action)} to {MAX_ACTION_LENGTH}")
            rule.action = rule.action[:MAX_ACTION_LENGTH]

        rule.trigger = unicodedata.normalize("NFC", rule.trigger)
        rule.action = unicodedata.normalize("NFC", rule.action)

        if rule.type not in VALID_RULE_TYPES:
            warnings.append(f"Invalid type '{rule.type}' defaulted to 'always'")
            rule.type = "always"

        return rule, warnings


class LocalRuleStorage:
    """Local JSON file fallback storage for rules."""

    _CACHE_TTL = 5.0

    def __init__(self, storage_path: str | None = None):
        if storage_path is None:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "rules"
            )
            os.makedirs(data_dir, exist_ok=True)
            storage_path = os.path.join(data_dir, "rules_local.json")
        else:
            os.path.realpath(storage_path)
            if not storage_path.endswith(".json") or ".." in storage_path:
                raise ValueError(f"Invalid storage_path: {storage_path}")
        self.storage_path = storage_path
        self._lock = threading.RLock()
        self._cache: dict | None = None
        self._cache_time: float = 0.0
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not os.path.exists(self.storage_path):
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"_metadata": {"version": "1.0", "created": datetime.now().isoformat()}, "rules": {}},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

    def store(self, rule: RuleData) -> StoreResult:
        """Persist a rule to the local JSON store, assigning it a new rule_id.

        Args:
            rule: RuleData to persist; rule.rule_id will be overwritten.

        Returns:
            StoreResult indicating success/failure with the assigned rule_id.
        """
        with self._lock:
            try:
                data = self._read_data()
                rule_id = f"RULE-LOCAL-{uuid.uuid4().hex[:6]}"
                rule.rule_id = rule_id
                data["rules"][rule_id] = {
                    "trigger": rule.trigger,
                    "action": rule.action,
                    "type": rule.type,
                    "confidence": rule.confidence,
                    "source": rule.source,
                    "raw_text": rule.raw_text,
                    "created_at": datetime.now().isoformat(),
                    "active": True,
                }
                self._write_data(data)
                self._cache = data
                self._cache_time = time.time()
                return StoreResult(
                    success=True,
                    rule_id=rule_id,
                    storage_method="local_json",
                    timestamp=datetime.now().isoformat(),
                    message=f"Rule stored: {rule_id}",
                )
            except (OSError, ValueError, TypeError) as e:
                logger.error("LocalRuleStorage store failed: %s", e)
                return StoreResult(success=False, message=str(e))

    def list_rules(self, _user_id: str = "default") -> list[dict[str, Any]]:
        """List all active rules in the local store.

        Args:
            _user_id: Reserved for future per-user filtering (currently unused).

        Returns:
            List of rule dictionaries (each includes its rule_id) marked active.
        """
        with self._lock:
            data = self._read_data()
            return [{"rule_id": k, **v} for k, v in data.get("rules", {}).items() if v.get("active", True)]

    def delete_rule(self, rule_id: str) -> bool:
        """Soft-delete a rule by marking it inactive.

        Args:
            rule_id: Identifier of the rule to delete.

        Returns:
            True if the rule existed and was marked inactive, False otherwise.
        """
        with self._lock:
            data = self._read_data()
            if rule_id in data.get("rules", {}):
                data["rules"][rule_id]["active"] = False
                data["rules"][rule_id]["deleted_at"] = datetime.now().isoformat()
                self._write_data(data)
                self._cache = data
                self._cache_time = time.time()
                return True
            return False

    def query(
        self, trigger_keywords: list[str] | None = None, rule_type: str | None = None, min_confidence: float = 0.0
    ) -> list[dict[str, Any]]:
        """Query active rules by keyword, type, and minimum confidence.

        Args:
            trigger_keywords: Optional keywords that must appear in trigger or action.
            rule_type: Optional rule type filter (e.g. "prefer", "avoid", "always").
            min_confidence: Minimum confidence threshold (inclusive).

        Returns:
            List of matching rule dicts sorted by rule-type priority (descending).
        """
        with self._lock:
            data = self._read_data()
            results = []
            for rid, r in data.get("rules", {}).items():
                if not r.get("active", True):
                    continue
                if rule_type and r.get("type") != rule_type:
                    continue
                if r.get("confidence", 0) < min_confidence:
                    continue
                if trigger_keywords and not any(kw in r.get("trigger", "") or kw in r.get("action", "") for kw in trigger_keywords):
                    continue
                results.append({"rule_id": rid, **r})
            results.sort(key=lambda x: RULE_TYPE_PRIORITY.get(x.get("type", "prefer"), 0), reverse=True)
            return results

    def _read_data(self) -> dict:
        now = time.time()
        if self._cache is not None and (now - self._cache_time) < self._CACHE_TTL:
            return self._cache
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or "rules" not in data or not isinstance(data["rules"], dict):
                    logger.warning("Invalid rules JSON structure, resetting to default")
                    data = {"_metadata": {}, "rules": {}}
                self._cache = data
                self._cache_time = now
                return data  # type: ignore[no-any-return]
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("Corrupted rules JSON: %s, resetting", e)
                data = {"_metadata": {}, "rules": {}}
                self._cache = data
                self._cache_time = now
                return data  # type: ignore[no-any-return]
        return {"_metadata": {}, "rules": {}}

    def _write_data(self, data: dict) -> None:
        tmp_path = self.storage_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.storage_path)


class RuleStorage:
    """Unified rule storage with CarryMem primary + local JSON fallback."""

    _shared_instance: Optional["RuleStorage"] = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_shared(cls, carrymem_config: dict | None = None) -> "RuleStorage":
        """Return the process-wide shared RuleStorage singleton.

        Args:
            carrymem_config: Optional CarryMem configuration passed to the constructor
                when the singleton is first created.

        Returns:
            The shared RuleStorage instance.
        """
        if cls._shared_instance is None:
            with cls._instance_lock:
                if cls._shared_instance is None:
                    cls._shared_instance = cls(carrymem_config)
        return cls._shared_instance

    def __init__(self, carrymem_config: dict | None = None) -> None:
        self.carrymem_available = False
        self._carrymem: Any = None
        self._local = LocalRuleStorage()
        self._init_carrymem(carrymem_config)

    def _init_carrymem(self, _config: dict | None) -> None:
        try:
            from scripts.collaboration.mce_adapter import get_global_mce_adapter

            adapter = get_global_mce_adapter(enable=False)
            if adapter and adapter.is_available:
                self._carrymem = adapter
                self.carrymem_available = True
        except (ImportError, AttributeError, RuntimeError) as e:
            logger.info("CarryMem not available for RuleStorage: %s", e)

    def store(self, rule: RuleData) -> StoreResult:
        """Store a rule via CarryMem if available, falling back to local JSON.

        Args:
            rule: RuleData to persist.

        Returns:
            StoreResult from the successful backend (CarryMem or local JSON).
        """
        if self.carrymem_available and self._carrymem:
            try:
                result = self._store_to_carrymem(rule)
                if result.success:
                    return result
            except (RuntimeError, ValueError, AttributeError) as e:
                logger.warning("CarryMem store failed, using fallback: %s", e)

        return self._local.store(rule)

    def list_rules(self, user_id: str = "default") -> list[dict[str, Any]]:
        """List active rules for the given user from the local fallback store.

        Args:
            user_id: Optional user identifier (reserved for future use).

        Returns:
            List of active rule dictionaries.
        """
        return self._local.list_rules(user_id)

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule by id via the local fallback store.

        Args:
            rule_id: Identifier of the rule to delete.

        Returns:
            True if the rule was found and deleted, False otherwise.
        """
        return self._local.delete_rule(rule_id)

    def query(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Query rules by keyword/type/confidence via the local fallback store.

        Args:
            **kwargs: Forwarded to LocalRuleStorage.query (trigger_keywords,
                rule_type, min_confidence).

        Returns:
            List of matching rule dictionaries.
        """
        return self._local.query(**kwargs)

    def _store_to_carrymem(self, rule: RuleData) -> StoreResult:
        if self._carrymem is not None and hasattr(self._carrymem, "add_rule"):
            result = self._carrymem.add_rule(
                trigger=rule.trigger,
                action=rule.action,
                rule_type=rule.type,
                confidence=rule.confidence,
            )
            if result:
                return StoreResult(
                    success=True,
                    rule_id=result.get("rule_id", ""),
                    storage_method="carrymem",
                    timestamp=datetime.now().isoformat(),
                    message="Rule stored to CarryMem",
                )
        return StoreResult(success=False, message="CarryMem add_rule not available")


class RuleCollector:
    """
    Main orchestrator for natural language rule collection.

    Integration point: Called by MultiAgentDispatcher.dispatch() before
    role matching. Returns CollectionResult with remaining task text.
    """

    def __init__(self, sensitivity: float = 0.85):
        self._detector = IntentDetector(sensitivity=sensitivity)
        self._extractor = RuleExtractor()
        self._sanitizer = RuleSanitizer()
        self._storage = RuleStorage()

    def process(self, text: str, lang: str = "zh") -> CollectionResult:
        """Process natural language text, detecting and storing rules or handling list/delete intents.

        Args:
            text: Natural language input from the user.
            lang: Response language code ("zh" or "en") used for message formatting.

        Returns:
            CollectionResult describing the outcome (rule_detected, stored rule,
            remaining task text, and a localized message).
        """
        intent = self._detector.detect(text)

        if not intent.is_detected:
            return CollectionResult(rule_detected=False, remaining_task=text)

        if intent.type_hint == "_list":
            rules = self._storage.list_rules()
            msg = self._format_list_response(rules, lang)
            return CollectionResult(
                rule_detected=True,
                list_rules=rules,
                remaining_task="",
                message=msg,
            )

        if intent.type_hint == "_delete":
            remaining = self._strip_rule_particle(text)
            delete_ok = self._handle_delete(text, lang)
            msg = self._format_delete_response(delete_ok, text, lang)
            return CollectionResult(
                rule_detected=True,
                delete_result=delete_ok,
                remaining_task=remaining,
                message=msg,
            )

        extraction = self._extractor.extract(text, intent)
        if not extraction.success or extraction.rule_data is None:
            remaining = self._strip_rule_particle(text)
            msg = self._format_failure_response(lang)
            return CollectionResult(
                rule_detected=True,
                remaining_task=remaining,
                message=msg,
            )

        rule, sanitize_warnings = self._sanitizer.sanitize(extraction.rule_data)

        if rule.confidence < 0.5:
            remaining = self._strip_rule_particle(text)
            msg = self._format_low_confidence_response(rule, lang)
            return CollectionResult(
                rule_detected=True,
                remaining_task=remaining,
                message=msg,
            )

        store_result = self._storage.store(rule)
        remaining = self._strip_rule_particle(text)
        msg = self._format_success_response(rule, store_result, lang)

        return CollectionResult(
            rule_detected=True,
            rule_result=store_result,
            remaining_task=remaining,
            message=msg,
        )

    def _strip_rule_particle(self, text: str) -> str:
        cleaned = _RULE_PARTICLE_RE.sub("", text).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) < MIN_ACTION_LENGTH:
            return ""
        return cleaned

    def _handle_delete(self, text: str, _lang: str) -> bool:
        rule_id_match = re.search(r"(RULE-[\w-]+)", text)
        if rule_id_match:
            return self._storage.delete_rule(rule_id_match.group(1))
        return False

    def _format_delete_response(self, deleted: bool, text: str, lang: str) -> str:
        rule_id_match = re.search(r"(RULE-[\w-]+)", text)
        if lang == "en":
            if not rule_id_match:
                return "No rule ID specified. Use 'list rules' first to find the ID, then 'delete rule RULE-xxx'."
            return f"Rule {rule_id_match.group(1)} deleted." if deleted else f"Rule {rule_id_match.group(1)} not found."
        elif lang == "ja":
            if not rule_id_match:
                return "ルールIDが指定されていません。「ルール一覧」でIDを確認後、「ルール削除 RULE-xxx」を実行してください。"
            return (
                f"ルール {rule_id_match.group(1)} を削除しました。"
                if deleted
                else f"ルール {rule_id_match.group(1)} が見つかりません。"
            )
        else:
            if not rule_id_match:
                return "未指定规则ID。请先「列出规则」获取ID，再「删除规则 RULE-xxx」。"
            return f"规则 {rule_id_match.group(1)} 已删除。" if deleted else f"规则 {rule_id_match.group(1)} 未找到。"

    def _format_success_response(self, rule: RuleData, result: StoreResult, lang: str) -> str:
        if lang == "en":
            return (
                f"Rule stored: {rule.action} ({result.rule_id})\n"
                f"  Type: {rule.type} | Trigger: {rule.trigger or 'general'}"
            )
        elif lang == "ja":
            return (
                f"ルール保存: {rule.action} ({result.rule_id})\n"
                f"  タイプ: {rule.type} | トリガー: {rule.trigger or '一般'}"
            )
        else:
            return (
                f"已记住规则: {rule.action} ({result.rule_id})\n"
                f"  类型: {rule.type} | 触发条件: {rule.trigger or '通用'}"
            )

    def _format_failure_response(self, lang: str) -> str:
        if lang == "en":
            return "Could not fully understand your rule. Try: 'Remember rule: [when] [do what]'"
        elif lang == "ja":
            return "ルールを完全に理解できませんでした。次の形式をお試しください: 'ルールを覚えて: [いつ] [何をする]'"
        else:
            return "无法完全理解您的规则，请尝试以下格式: '记住规则: [何时][做什么]'"

    def _format_low_confidence_response(self, rule: RuleData, lang: str) -> str:
        pct = int(rule.confidence * 100)
        if lang == "en":
            return f"Rule recorded with low confidence ({pct}%). Consider using standard format."
        elif lang == "ja":
            return f"ルールを記録しましたが、信頼度が低いです({pct}%)。標準形式の使用をお勧めします。"
        else:
            return f"已记录您的偏好 (置信度: {pct}%)。建议使用标准格式以获得更高准确率。"

    def _format_list_response(self, rules: list[dict[str, Any]], lang: str) -> str:
        if not rules:
            if lang == "en":
                return "No rules stored yet."
            elif lang == "ja":
                return "保存されたルールはまだありません。"
            else:
                return "暂无已存储的规则。"

        lines = []
        for r in rules[:20]:
            rid = r.get("rule_id", "?")
            rtype = r.get("type", "?")
            action = r.get("action", "?")[:50]
            trigger = r.get("trigger", "")
            if lang == "zh":
                lines.append(f"  {rid} [{rtype}] {trigger + ' → ' if trigger else ''}{action}")
            else:
                lines.append(f"  {rid} [{rtype}] {trigger + ' -> ' if trigger else ''}{action}")

        header = "Stored Rules:" if lang == "en" else "保存済みルール:" if lang == "ja" else "已存储规则:"
        return f"{header}\n" + "\n".join(lines)

    def grilling_mode(self, code_graph: Any = None) -> "GrillingMode":
        """Create a grilling session for one-question-at-a-time interview.

        Matt Pocock grilling principles (P0-7):
        - One question at a time — multiple questions confuse users
        - Recommended answer per question — reduce cognitive load
        - Explore codebase before asking — use CodeKnowledgeGraph first
        - Walk down each branch of design tree — sequential exploration

        Args:
            code_graph: Optional CodeKnowledgeGraph instance for explore-before-ask.
                When provided, the grilling session will attempt to find answers
                in the codebase before presenting questions to the user.

        Returns:
            A new GrillingMode session ready to accept questions.
        """
        return GrillingMode(code_graph=code_graph)


# ---------------------------------------------------------------------------
# Module 10 (Matt P0-7): Grilling Mode — one-question-at-a-time interview
# ---------------------------------------------------------------------------


@dataclass
class GrillingQuestion:
    """A single question in a grilling session.

    Attributes:
        question: The question text presented to the user.
        recommended_answers: Suggested answers ordered by likelihood.
            Providing a recommendation reduces user cognitive load.
        context: Why this question matters (design branch justification).
        branch: Which design tree branch this question explores.
        explored: Whether codebase exploration has been attempted for this question.
        explored_answer: Answer found by codebase exploration, or empty string.
        user_answer: The user's answer once provided, or empty string.
    """

    question: str = ""
    recommended_answers: list[str] = field(default_factory=list)
    context: str = ""
    branch: str = ""
    explored: bool = False
    explored_answer: str = ""
    user_answer: str = ""


@dataclass
class GrillingResult:
    """Final result of a completed grilling session.

    Attributes:
        questions: All questions in the session (with answers filled in).
        completed: Whether all questions have been answered.
        explored_answers: Mapping of question text to codebase-explored answer.
        glossary_candidates: Glossary term candidates auto-extracted from
            question text and user answers (Matt Pocock grill-with-docs P1-2).
            Deduplicated and alphabetically sorted.
    """

    questions: list[GrillingQuestion] = field(default_factory=list)
    completed: bool = False
    explored_answers: dict[str, str] = field(default_factory=dict)
    glossary_candidates: list[str] = field(default_factory=list)


class GrillingMode:
    """One-question-at-a-time interview mode with explore-before-ask.

    Matt Pocock grilling discipline (P0-7):

    1. **One question at a time** — asking multiple questions simultaneously
       overwhelms the user and produces lower-quality answers.
    2. **Recommended answer per question** — provide a suggested default so
       the user can confirm rather than reason from scratch.
    3. **Explore the codebase before asking** — use CodeKnowledgeGraph to
       find existing patterns; only ask the user when the codebase is silent.
    4. **Walk down each branch of the design tree** — explore branches
       sequentially rather than in parallel.

    Usage:
        session = collector.grilling_mode(code_graph=graph)
        session.add_question(
            question="Which logging framework?",
            recommended_answers=["structlog", "logging"],
            context="Need structured logging for trace correlation",
            branch="observability",
        )
        if session.is_complete():
            result = session.get_summary()
    """

    def __init__(self, code_graph: Any = None) -> None:
        self._code_graph = code_graph
        self._questions: list[GrillingQuestion] = []
        self._current_index: int = 0
        # Matt Pocock grill-me (P1-6): stateless mode skips codebase exploration
        # and proceeds directly to user questions.
        self._stateless: bool = code_graph is None

    @classmethod
    def stateless_mode(cls, code_graph: Any = None) -> "GrillingMode":
        """Create a stateless GrillingMode that does not depend on CodeKnowledgeGraph.

        Matt Pocock grill-me principle (P1-6): grilling can proceed without a
        codebase. In stateless mode ``explore_before_ask`` skips codebase search
        entirely and returns ``None`` immediately, so every question is asked
        directly to the user.

        Args:
            code_graph: Optional CodeKnowledgeGraph; when None (the typical
                case) the session is fully stateless.

        Returns:
            A new GrillingMode instance configured for stateless operation.
        """
        session = cls(code_graph=code_graph)
        session._stateless = code_graph is None
        return session

    def is_stateless(self) -> bool:
        """Return True when this session operates without a CodeKnowledgeGraph.

        Returns:
            True if no code_graph was supplied (stateless mode), False otherwise.
        """
        return self._stateless

    def add_question(
        self,
        question: str,
        recommended_answers: list[str] | None = None,
        context: str = "",
        branch: str = "",
    ) -> None:
        """Add a question to the grilling queue.

        Args:
            question: The question text to present to the user.
            recommended_answers: Optional list of suggested answers (ordered
                by likelihood). Pass None or empty list for open-ended questions.
            context: Explanation of why this question matters.
            branch: Design tree branch identifier this question explores.
        """
        self._questions.append(
            GrillingQuestion(
                question=question,
                recommended_answers=list(recommended_answers) if recommended_answers else [],
                context=context,
                branch=branch,
            )
        )

    def next_question(self) -> GrillingQuestion | None:
        """Advance to the next question and return it.

        Returns:
            The next GrillingQuestion, or None if all questions are exhausted.
        """
        if self._current_index >= len(self._questions):
            return None
        q = self._questions[self._current_index]
        self._current_index += 1
        return q

    def current_question(self) -> GrillingQuestion | None:
        """Get the current question without advancing the pointer.

        Returns:
            The current GrillingQuestion, or None if the session hasn't
            started or is already complete.
        """
        if self._current_index >= len(self._questions):
            return None
        return self._questions[self._current_index]

    def is_complete(self) -> bool:
        """Check if all questions have been answered.

        Returns:
            True when every question in the session has a non-empty user_answer
            (or an explored_answer that was auto-accepted).
        """
        if not self._questions:
            return True
        return all(q.user_answer or q.explored_answer for q in self._questions)

    def explore_before_ask(self, question: GrillingQuestion) -> str | None:
        """Attempt to find an answer in the codebase before asking the user.

        Uses the CodeKnowledgeGraph (if provided) to search for existing
        symbols or patterns that may answer the question. When the codebase
        provides a clear answer, the user need not be prompted.

        In stateless mode (Matt Pocock grill-me P1-6) the method short-circuits
        and returns ``None`` immediately without touching any code_graph.

        Args:
            question: The GrillingQuestion to explore.

        Returns:
            A string describing the codebase finding if one is found,
            or None when the codebase is silent and the user must be asked.
        """
        if question.explored:
            return question.explored_answer or None
        question.explored = True

        if self._stateless or self._code_graph is None:
            return None

        try:
            query = self._code_graph.query()
        except (AttributeError, RuntimeError):
            return None

        # Extract candidate symbol names from the question text.
        # Look for quoted terms, camelCase/snake_case identifiers.
        candidates = self._extract_search_terms(question.question)
        findings: list[str] = []
        for term in candidates:
            try:
                symbols = query.find_symbol(term)
            except (AttributeError, RuntimeError):
                continue
            if symbols:
                names = [s.name if hasattr(s, "name") else str(s) for s in symbols[:3]]
                findings.append(f"'{term}' found: {', '.join(names)}")

        if findings:
            answer = "; ".join(findings)
            question.explored_answer = answer
            return answer

        return None

    def answer_current(self, answer: str) -> bool:
        """Record the user's answer for the current question and advance.

        Args:
            answer: The user's answer text.

        Returns:
            True if the answer was recorded and the pointer advanced,
            False if there is no current question to answer.
        """
        q = self.current_question()
        if q is None:
            return False
        q.user_answer = answer
        self._current_index += 1
        return True

    def get_summary(self) -> GrillingResult:
        """Get the final grilling result with all questions and explored answers.

        Also auto-extracts glossary term candidates from question text and
        user answers (Matt Pocock grill-with-docs P1-2), populating
        ``GrillingResult.glossary_candidates``.

        Returns:
            GrillingResult containing all questions (with answers filled in),
            a completed flag, a mapping of question text to explored answers,
            and a deduplicated/sorted list of glossary term candidates.
        """
        explored = {
            q.question: q.explored_answer for q in self._questions if q.explored_answer
        }
        return GrillingResult(
            questions=list(self._questions),
            completed=self.is_complete(),
            explored_answers=explored,
            glossary_candidates=self.extract_glossary_candidates(),
        )

    def extract_glossary_candidates(self) -> list[str]:
        """Extract glossary term candidates from all questions and user answers.

        Matt Pocock grill-with-docs principle (P1-2): the grilling interview
        itself is a documentation process. Term candidates are extracted from
        both question text and user_answer text using these rules:

        - CamelCase phrases (e.g., ``DeepModule``, ``CodeKnowledgeGraph``)
        - Hyphenated phrases (e.g., ``red-capable``, ``stateless-mode``)
        - Quoted terms (e.g., ``"seam"``, ``'structlog'``)

        Candidates are deduplicated and sorted alphabetically.

        Returns:
            A deduplicated, alphabetically sorted list of candidate terms.
        """
        candidates: set[str] = set()

        for q in self._questions:
            for source_text in (q.question, q.user_answer):
                if not source_text:
                    continue
                # CamelCase phrases (>= 2 capitalised components)
                for match in re.finditer(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", source_text):
                    candidates.add(match.group(1))
                # Hyphenated phrases (>= 1 hyphen, alphabetic components only)
                for match in re.finditer(r"\b([a-zA-Z]+(?:-[a-zA-Z]+)+)\b", source_text):
                    candidates.add(match.group(1))
                # Quoted terms (single or double quotes)
                for match in re.finditer(r'["\']([A-Za-z_][\w-]*)["\']', source_text):
                    candidates.add(match.group(1))

        return sorted(candidates)

    @staticmethod
    def _extract_search_terms(text: str) -> list[str]:
        """Extract candidate symbol names from question text.

        Looks for:
        - Quoted terms: ``"structlog"`` or ``'logging'``
        - snake_case identifiers: ``my_function``
        - CamelCase identifiers: ``MyClass``

        Args:
            text: Question text to extract terms from.

        Returns:
            List of candidate symbol names (deduplicated, order preserved).
        """
        terms: list[str] = []
        # Quoted terms
        for match in re.finditer(r'["\']([A-Za-z_][\w]*)["\']', text):
            terms.append(match.group(1))
        # snake_case identifiers (length >= 3 to avoid noise)
        for match in re.finditer(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b", text):
            terms.append(match.group(1))
        # CamelCase identifiers
        for match in re.finditer(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", text):
            terms.append(match.group(1))
        # Deduplicate preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for t in terms:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique
