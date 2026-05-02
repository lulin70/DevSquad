#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuleCollector — Natural Language Rule Collection Module

Intercepts user input to detect rule-storing intent, extracts structured
rule data, sanitizes content, and stores via CarryMem or local JSON fallback.

Integration point: Called by MultiAgentDispatcher.dispatch() before role matching.

Pipeline:
    User Input → IntentDetector → RuleExtractor → RuleSanitizer → RuleStorage
                 (detect intent)   (extract rule)  (security check)  (persist)

Author: DevSquad Team
Version: 3.4.0
"""

import os
import re
import json
import uuid
import time
import logging
import threading
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

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
    {"id": "EXT-01", "regex": r"记住.*规则[:：]\s*(.+?)(?:时|前|后|的时候|情况下)[，,]?\s*(.+)", "trigger_group": 1, "action_group": 2},
    {"id": "EXT-02", "regex": r"添加规则[:：]\s*(.+?)(?:前必须|时必须|后必须|前要|时要|后要)\s*(.+)", "trigger_group": 1, "action_group": 2},
    {"id": "EXT-03", "regex": r"我的偏好[:：]\s*(.+?)(?:而不是|而非|而不是用)\s*(.+)", "trigger_group": 2, "action_group": 1},
    {"id": "EXT-04", "regex": r"(禁止|不要|不能)\s*(.+?)(?:时|的时候|中)\s*(.+)", "trigger_group": 2, "action_group": 3},
    {"id": "EXT-05", "regex": r"(总是|必须|应该)\s*(.+?)(?:当|在)\s*(.+?)(?:时|的时候)", "trigger_group": 3, "action_group": 2},
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
]

_RULE_PARTICLE_RE = re.compile(
    r"(?:记住.*规则[:：]|添加规则[:：]|我的偏好[:：]|团队规范[:：])"
    r".+?(?:。|$|\n)",
    re.IGNORECASE,
)


@dataclass
class IntentResult:
    is_detected: bool = False
    pattern_id: Optional[str] = None
    confidence: float = 0.0
    matched_span: Optional[Tuple[int, int]] = None
    type_hint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleData:
    trigger: str = ""
    action: str = ""
    type: str = "always"
    confidence: float = 0.0
    source: str = "natural_language"
    raw_text: str = ""
    rule_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    success: bool = False
    rule_data: Optional[RuleData] = None
    alternatives: List[RuleData] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class StoreResult:
    success: bool = False
    rule_id: Optional[str] = None
    storage_method: str = ""
    timestamp: str = ""
    message: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass
class CollectionResult:
    rule_detected: bool = False
    rule_result: Optional[StoreResult] = None
    remaining_task: str = ""
    list_rules: Optional[List[Dict[str, Any]]] = None
    delete_result: Optional[bool] = None
    message: str = ""


class IntentDetector:
    """Detect rule-storing intent from user input using regex patterns."""

    def __init__(self, sensitivity: float = 0.85):
        self.patterns = INTENT_PATTERNS
        self.sensitivity = sensitivity
        self._compiled = [
            {"id": p["id"], "regex": re.compile(p["regex"], re.IGNORECASE),
             "weight": p["weight"], "type_hint": p["type_hint"]}
            for p in self.patterns
        ]

    def detect(self, text: str) -> IntentResult:
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

        return IntentResult(
            is_detected=True,
            pattern_id=best_pattern["id"],
            confidence=best_score,
            matched_span=(best_match.start(), best_match.end()),
            type_hint=best_pattern["type_hint"],
        )


class RuleExtractor:
    """Extract structured rule data from natural language input."""

    def __init__(self):
        self.extraction_patterns = EXTRACTION_PATTERNS
        self._compiled = [
            {"id": p["id"], "regex": re.compile(p["regex"], re.IGNORECASE),
             "trigger_group": p["trigger_group"], "action_group": p["action_group"]}
            for p in self.extraction_patterns
        ]

    def extract(self, text: str, intent: IntentResult) -> ExtractionResult:
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
                if p["trigger_group"] is not None:
                    trigger = m.group(p["trigger_group"]).strip()
                else:
                    trigger = ""
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

    def _infer_type(self, text: str, hint: Optional[str]) -> str:
        if hint and hint in VALID_RULE_TYPES:
            return hint

        for rule_type, keywords in TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return rule_type

        return "always"

    def _calculate_confidence(self, trigger: str, action: str,
                              rule_type: str, intent_conf: float) -> float:
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
    def sanitize(rule: RuleData) -> Tuple[RuleData, List[str]]:
        warnings = []

        for pat in DANGEROUS_PATTERNS:
            if pat.search(rule.action):
                warnings.append(f"Dangerous pattern detected in rule action")
                rule.action = re.sub(pat.pattern, "[REDACTED]", rule.action)

        for pat in DANGEROUS_PATTERNS:
            if pat.search(rule.trigger):
                warnings.append(f"Dangerous pattern detected in rule trigger")
                rule.trigger = re.sub(pat.pattern, "[REDACTED]", rule.trigger)

        for pat in PROMPT_INJECTION_PATTERNS:
            if pat.search(rule.action):
                warnings.append("Prompt injection pattern detected in rule action")
                rule.action = re.sub(pat.pattern, "[REDACTED]", rule.action)

        for pat in PROMPT_INJECTION_PATTERNS:
            if pat.search(rule.trigger):
                warnings.append("Prompt injection pattern detected in rule trigger")
                rule.trigger = re.sub(pat.pattern, "[REDACTED]", rule.trigger)

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

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "data", "rules")
            os.makedirs(data_dir, exist_ok=True)
            storage_path = os.path.join(data_dir, "rules_local.json")
        self.storage_path = storage_path
        self._lock = threading.RLock()
        self._cache: Optional[dict] = None
        self._cache_time: float = 0.0
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.storage_path):
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({"_metadata": {"version": "1.0", "created": datetime.now().isoformat()},
                           "rules": {}}, f, ensure_ascii=False, indent=2)

    def store(self, rule: RuleData) -> StoreResult:
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
                    success=True, rule_id=rule_id,
                    storage_method="local_json",
                    timestamp=datetime.now().isoformat(),
                    message=f"Rule stored: {rule_id}",
                )
            except Exception as e:
                logger.error("LocalRuleStorage store failed: %s", e)
                return StoreResult(success=False, message=str(e))

    def list_rules(self, user_id: str = "default") -> List[Dict[str, Any]]:
        with self._lock:
            data = self._read_data()
            return [{"rule_id": k, **v} for k, v in data.get("rules", {}).items() if v.get("active", True)]

    def delete_rule(self, rule_id: str) -> bool:
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

    def query(self, trigger_keywords: Optional[List[str]] = None,
              rule_type: Optional[str] = None,
              min_confidence: float = 0.0) -> List[Dict[str, Any]]:
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
                if trigger_keywords:
                    if not any(kw in r.get("trigger", "") or kw in r.get("action", "")
                               for kw in trigger_keywords):
                        continue
                results.append({"rule_id": rid, **r})
            results.sort(key=lambda x: RULE_TYPE_PRIORITY.get(x.get("type", "prefer"), 0), reverse=True)
            return results

    def _read_data(self) -> dict:
        now = time.time()
        if self._cache is not None and (now - self._cache_time) < self._CACHE_TTL:
            return self._cache
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cache = data
                self._cache_time = now
                return data
        return {"_metadata": {}, "rules": {}}

    def _write_data(self, data: dict):
        tmp_path = self.storage_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.storage_path)


class RuleStorage:
    """Unified rule storage with CarryMem primary + local JSON fallback."""

    def __init__(self, carrymem_config: Optional[dict] = None):
        self.carrymem_available = False
        self._carrymem = None
        self._local = LocalRuleStorage()
        self._init_carrymem(carrymem_config)

    def _init_carrymem(self, config):
        try:
            from scripts.collaboration.mce_adapter import get_global_mce_adapter
            adapter = get_global_mce_adapter(enable=False)
            if adapter and adapter.is_available:
                self._carrymem = adapter
                self.carrymem_available = True
        except Exception as e:
            logger.info("CarryMem not available for RuleStorage: %s", e)

    def store(self, rule: RuleData) -> StoreResult:
        if self.carrymem_available and self._carrymem:
            try:
                result = self._store_to_carrymem(rule)
                if result.success:
                    return result
            except Exception as e:
                logger.warning("CarryMem store failed, using fallback: %s", e)

        return self._local.store(rule)

    def list_rules(self, user_id: str = "default") -> List[Dict[str, Any]]:
        return self._local.list_rules(user_id)

    def delete_rule(self, rule_id: str) -> bool:
        return self._local.delete_rule(rule_id)

    def query(self, **kwargs) -> List[Dict[str, Any]]:
        return self._local.query(**kwargs)

    def _store_to_carrymem(self, rule: RuleData) -> StoreResult:
        if hasattr(self._carrymem, "add_rule"):
            result = self._carrymem.add_rule(
                trigger=rule.trigger, action=rule.action,
                rule_type=rule.type, confidence=rule.confidence,
            )
            if result:
                return StoreResult(
                    success=True, rule_id=result.get("rule_id", ""),
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
        intent = self._detector.detect(text)

        if not intent.is_detected:
            return CollectionResult(rule_detected=False, remaining_task=text)

        if intent.type_hint == "_list":
            rules = self._storage.list_rules()
            msg = self._format_list_response(rules, lang)
            return CollectionResult(
                rule_detected=True, list_rules=rules,
                remaining_task="", message=msg,
            )

        if intent.type_hint == "_delete":
            remaining = self._strip_rule_particle(text)
            delete_ok = self._handle_delete(text, lang)
            return CollectionResult(
                rule_detected=True, delete_result=delete_ok,
                remaining_task=remaining,
                message="Rule deleted" if delete_ok else "Rule not found",
            )

        extraction = self._extractor.extract(text, intent)
        if not extraction.success or extraction.rule_data is None:
            remaining = self._strip_rule_particle(text)
            msg = self._format_failure_response(lang)
            return CollectionResult(
                rule_detected=True, remaining_task=remaining, message=msg,
            )

        rule, sanitize_warnings = self._sanitizer.sanitize(extraction.rule_data)

        if rule.confidence < 0.5:
            remaining = self._strip_rule_particle(text)
            msg = self._format_low_confidence_response(rule, lang)
            return CollectionResult(
                rule_detected=True, remaining_task=remaining, message=msg,
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

    def _handle_delete(self, text: str, lang: str) -> bool:
        rule_id_match = re.search(r"(RULE-[\w-]+)", text)
        if rule_id_match:
            return self._storage.delete_rule(rule_id_match.group(1))
        return False

    def _format_success_response(self, rule: RuleData, result: StoreResult,
                                  lang: str) -> str:
        if lang == "en":
            return (f"Rule stored: {rule.action} ({result.rule_id})\n"
                    f"  Type: {rule.type} | Trigger: {rule.trigger or 'general'}")
        elif lang == "ja":
            return (f"ルール保存: {rule.action} ({result.rule_id})\n"
                    f"  タイプ: {rule.type} | トリガー: {rule.trigger or '一般'}")
        else:
            return (f"已记住规则: {rule.action} ({result.rule_id})\n"
                    f"  类型: {rule.type} | 触发条件: {rule.trigger or '通用'}")

    def _format_failure_response(self, lang: str) -> str:
        if lang == "en":
            return ("Could not fully understand your rule. Try: "
                    "'Remember rule: [when] [do what]'")
        elif lang == "ja":
            return ("ルールを完全に理解できませんでした。次の形式をお試しください: "
                    "'ルールを覚えて: [いつ] [何をする]'")
        else:
            return ("无法完全理解您的规则，请尝试以下格式: "
                    "'记住规则: [何时][做什么]'")

    def _format_low_confidence_response(self, rule: RuleData, lang: str) -> str:
        pct = int(rule.confidence * 100)
        if lang == "en":
            return f"Rule recorded with low confidence ({pct}%). Consider using standard format."
        elif lang == "ja":
            return f"ルールを記録しましたが、信頼度が低いです({pct}%)。標準形式の使用をお勧めします。"
        else:
            return f"已记录您的偏好 (置信度: {pct}%)。建议使用标准格式以获得更高准确率。"

    def _format_list_response(self, rules: List[Dict[str, Any]],
                               lang: str) -> str:
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
                lines.append(f"  {rid} [{rtype}] {trigger+' → ' if trigger else ''}{action}")
            else:
                lines.append(f"  {rid} [{rtype}] {trigger+' -> ' if trigger else ''}{action}")

        header = "Stored Rules:" if lang == "en" else "保存済みルール:" if lang == "ja" else "已存储规则:"
        return f"{header}\n" + "\n".join(lines)
