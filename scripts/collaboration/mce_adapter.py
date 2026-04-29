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

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
    _lock = None

    def __init__(self, enable: bool = False):
        import threading
        self._lock = threading.RLock()
        self._status = MCEStatus()
        self._carrymem = None

        if enable:
            self._try_init()

    def _try_init(self):
        with self._lock:
            try:
                from memory_classification_engine import CarryMem
                self._carrymem = CarryMem()
                self._status.available = True

                version = getattr(
                    __import__('memory_classification_engine'),
                    '__version__',
                    'unknown'
                )
                self._status.version = str(version)

            except ImportError as e:
                self._status.available = False
                self._status.init_error = f"CarryMem not installed: {e}"
            except Exception as e:
                self._status.available = False
                self._status.init_error = f"{type(e).__name__}: {e}"

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

            except Exception:
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
            except Exception:
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
            except Exception:
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
        MCEAdapter._instance = MCEAdapter(enable=enable)
    return MCEAdapter._instance
