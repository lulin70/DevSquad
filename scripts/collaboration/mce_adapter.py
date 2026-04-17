#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCEAdapter — Memory Classification Engine Adapter

V3.2 MVP Line-B: Integrates local MCE (memory-classification-engine) into MultiAgentSkill.
Updated for MCE v0.4 with tenant management and permission checking support.

Design Principles:
  - Never modify MCE source code — it is an independent project
  - MCE as optional dependency — auto-degrade on import failure
  - All calls wrapped in try/except — zero intrusion, no impact on main flow
  - Lazy initialization (lazy init) — no impact on cold start speed

Integration Method: Facade direct import (not HTTP SDK)
Integration Points: Phase A (capture_execution) priority, Phase B/C optional future iterations

MCE Version Compatibility:
  - v0.1.0: Initial integration (process_message, store_memory, retrieve_memories)
  - v0.4.0: Current — adds tenant management, check_permission, analyze_sensitivity

Example Usage:
    adapter = MCEAdapter(enable=True)
    if adapter.is_available:
        result = adapter.classify("User successfully logged in")
        print(result)  # MCEResult(memory_type='decision', confidence=0.92, ...)
        permitted = adapter.check_permission("sensitive_data_query")
        print(permitted)  # True/False
    else:
        print("MCE unavailable, using default classification")
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ============================================================
# 数据模型
# ============================================================

@dataclass
class MCEResult:
    """
    MCE 分类结果数据模型

    封装 MCE 引擎返回的标准化分类结果。

    Attributes:
        memory_type: 记忆类型标签 (preference/decision/correction/fact/task/general)
        confidence: 分类置信度 (0.0~1.0)
        tier: 存储层级 (tier2/tier3/tier4/episodic/knowledge)
        metadata: 额外元数据 (引擎原始返回中的其他字段)
    """
    memory_type: str = ""
    confidence: float = 0.0
    tier: str = "tier2"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """
        序列化为字典格式

        Returns:
            Dict: 包含 type/confidence/tier/metadata 的字典
        """
        return {
            "type": self.memory_type,
            "confidence": round(self.confidence, 4),
            "tier": self.tier,
            "metadata": self.metadata,
        }


@dataclass
class MCEStatus:
    """
    MCE 适配器运行状态快照

    Attributes:
        available: MCE 引擎是否可用 (初始化成功为 True)
        version: MCE 引擎版本号
        init_error: 初始化失败时的错误信息 (成功时为 None)
        classify_count: 成功分类调用次数
        classify_fail_count: 分类失败/超时次数
    """
    available: bool = False
    version: str = ""
    init_error: Optional[str] = None
    classify_count: int = 0
    classify_fail_count: int = 0


# ============================================================
# 核心适配器
# ============================================================

class MCEAdapter:
    """
    Memory Classification Engine Adapter

    Wraps memory_classification_engine via Facade pattern,
    providing unified classify / store / retrieve interfaces.
    Gracefully degrades (returns None or defaults) when MCE is unavailable.

    Integration Points with Existing Components:
      Phase A: memory_bridge.capture_execution() → adapter.classify(output) → typed storage
      Phase B: memory_bridge.recall() → adapter.retrieve_memories() → type filtering
      Phase C: scratchpad.write() → adapter.classify(content) → entry type annotation
      Dispatcher: dispatch() memory capture step → adapter as optional enhancement

    Example Usage:
        adapter = MCEAdapter(enable=True)
        if adapter.is_available:
            result = adapter.classify("User preference: dark mode")
            print(result.memory_type)  # "preference"

    Thread Safety: All public methods are thread-safe (internal RLock protection)
    """

    _instance = None
    _lock = None

    def __init__(self, enable: bool = False):
        """
        Initialize MCE adapter

        Args:
            enable: Whether to enable MCE (False skips all initialization)
        """
        import threading
        self._lock = threading.RLock()
        self._status = MCEStatus()
        self._facade = None
        self._tenant_id: Optional[str] = "default"

        if enable:
            self._try_init()

    def _try_init(self):
        """
        尝试初始化 MCE Facade

        只在首次调用或显式 reinit 时执行。
        ImportError 或任何异常都会被捕获，不传播给调用方。
        """
        with self._lock:
            try:
                from memory_classification_engine import (
                    MemoryClassificationEngineFacade,
                )
                from memory_classification_engine.utils.helpers import MEMORY_TYPES

                self._facade = MemoryClassificationEngineFacade()
                self._status.available = True

                version = getattr(
                    __import__('memory_classification_engine'),
                    '__version__',
                    'unknown'
                )
                self._status.version = str(version)

            except ImportError as e:
                self._status.available = False
                self._status.init_error = f"ImportError: {e}"
            except Exception as e:
                self._status.available = False
                self._status.init_error = f"{type(e).__name__}: {e}"

    @property
    def is_available(self) -> bool:
        """
        MCE 是否可用

        Returns:
            bool: True 表示 MCE 已成功初始化并可正常调用
        """
        return self._status.available

    @property
    def status(self) -> MCEStatus:
        """
        获取当前状态快照

        Returns:
            MCEStatus: 包含 available/version/error/统计信息
        """
        with self._lock:
            s = MCEStatus(
                available=self._status.available,
                version=self._status.version,
                init_error=self._status.init_error,
                classify_count=self._status.classify_count,
                classify_fail_count=self._status.classify_fail_count,
            )
            return s

    def classify(self, text: str,
                  context: Optional[Dict] = None,
                  timeout_ms: int = 500) -> Optional[MCEResult]:
        """
        分类文本为记忆类型

        调用 MCE 的 classify_message 接口，
        将返回结果标准化为 MCEResult。

        Args:
            text: 待分类的文本内容
            context: 可选的上下文信息（传递给 MCE）
            timeout_ms: 超时时间（毫秒），超时返回 None

        Returns:
            MCEResult: 分类结果（包含 type/confidence/tier/metadata）
                       MCE 不可用时返回 None
        """
        with self._lock:
            if not self.is_available or not self._facade:
                self._status.classify_fail_count += 1
                return None

            try:
                start = __import__('time').time()
                raw_result = self._facade.classify_message(text, context)
                elapsed_ms = (time.time() - start) * 1000

                if elapsed_ms > timeout_ms:
                    self._status.classify_fail_count += 1
                    return None

                result = self._normalize_result(raw_result)
                self._status.classify_count += 1
                return result

            except Exception as e:
                self._status.classify_fail_count += 1
                return None

    def classify_batch(self,
                        texts: List[str],
                        context: Optional[Dict] = None) -> List[Optional[MCEResult]]:
        """
        批量分类多个文本

        Args:
            texts: 待分类文本列表
            context: 共享上下文

        Returns:
            List[Optional[MCEResult]]: 与输入等长的结果列表
        """
        return [self.classify(t, context) for t in texts]

    def store_memory(self, memory_data: Dict) -> bool:
        """
        存储一条记忆到 MCE

        Args:
            memory_data: 记忆数据字典（需符合 MCE 的 schema）

        Returns:
            bool: 是否成功存储
        """
        with self._lock:
            if not self.is_available or not self._facade:
                return False
            try:
                return self._facade.store_memory(memory_data)
            except Exception:
                return False

    def retrieve_memories(self,
                           query: str,
                           tier: str = "tier2",
                           limit: int = 20,
                           memory_type: Optional[str] = None) -> List[Dict]:
        """
        从 MCE 检索相关记忆

        Args:
            query: 查询关键词
            tier: 存储层级 (tier2/tier3/tier4)
            limit: 最大返回数
            memory_type: 可选的类型过滤

        Returns:
            List[Dict]: 匹配的记忆列表
        """
        with self._lock:
            if not self.is_available or not self._facade:
                return []
            try:
                results = self._facade.retrieve_memories(
                    query=query, tier=tier, limit=limit,
                    memory_type=memory_type,
                )
                return results if isinstance(results, list) else []
            except Exception:
                return []

    def shutdown(self):
        """
        关闭 MCE 连接（释放资源）

        应在程序退出或 MemoryBridge.shutdown() 时调用。
        """
        with self._lock:
            if self._facade and hasattr(self._facade, 'shutdown'):
                try:
                    self._facade.shutdown()
                except Exception:
                    pass
            self._facade = None
            self._status.available = False

    def force_reinit(self):
        """
        Force re-initialization (for use after config changes)

        Closes old connection first, then attempts re-initialization.
        """
        self.shutdown()
        self._try_init()

    def set_tenant(self, tenant_id: str) -> bool:
        """
        Set active tenant for MCE v0.4 multi-tenant support.

        Args:
            tenant_id: Tenant identifier string

        Returns:
            bool: True if tenant was set successfully, False otherwise
        """
        with self._lock:
            if not self.is_available or not self._facade:
                return False
            try:
                if hasattr(self._facade, 'create_tenant'):
                    self._facade.create_tenant(tenant_id)
                self._tenant_id = tenant_id
                return True
            except Exception:
                return False

    def check_permission(self, text: str) -> bool:
        """
        Check permission/sensitivity of text via MCE v0.4 privacy service.

        Uses MCE's check_permission or analyze_sensitivity method to determine
        if a text contains sensitive information that should be handled carefully.

        Args:
            text: Text content to check for sensitivity

        Returns:
            bool: True if text passes permission check (not sensitive), False if blocked
        """
        with self._lock:
            if not self.is_available or not self._facade:
                return True  # Default: allow when MCE unavailable
            try:
                if hasattr(self._facade, 'check_permission'):
                    result = self._facade.check_permission(text)
                    return bool(result) if result is not None else True
                elif hasattr(self._facade, 'analyze_sensitivity'):
                    result = self._facade.analyze_sensitivity(text)
                    if isinstance(result, dict):
                        return result.get('allowed', True)
                    return True
                return True  # No privacy service available, allow by default
            except Exception:
                return True  # Graceful degrade: allow on error

    @staticmethod
    def _normalize_result(raw: Any) -> MCEResult:
        """
        Normalize MCE return value to MCEResult format.

        Handles multiple possible return formats:
        - Dict with 'type' field
        - Dict with 'memory_type' field
        - String value
        - Other formats → default values

        Args:
            raw: Raw return value from MCE classify_message

        Returns:
            MCEResult: Normalized classification result
        """
        if raw is None:
            return MCEResult()

        if isinstance(raw, dict):
            mt = raw.get('type') or raw.get('memory_type') or raw.get('category', 'general')
            conf = raw.get('confidence', raw.get('score', 0.0))
            if isinstance(conf, (int, float)):
                conf = min(max(float(conf), 0.0), 1.0)
            else:
                try:
                    conf = float(str(conf))
                except (ValueError, TypeError):
                    conf = 0.5
            tier = raw.get('tier', 'tier2')
            meta = {k: v for k, v in raw.items()
                     if k not in ('type', 'memory_type', 'category',
                                'confidence', 'score', 'tier')}
            return MCEResult(
                memory_type=str(mt),
                confidence=conf,
                tier=str(tier),
                metadata=meta,
            )

        if isinstance(raw, str):
            return MCEResult(memory_type=raw)

        return MCEResult(metadata={"raw": str(raw)[:200]})


def get_global_mce_adapter(enable: bool = False) -> MCEAdapter:
    """
    获取全局单例 MCEAdapter

    进程级别单例——多次调用返回同一实例。

    Args:
        enable: 是否启用 MCE

    Returns:
        MCEAdapter: 全局单例实例
    """
    if MCEAdapter._instance is None:
        MCEAdapter._instance = MCEAdapter(enable=enable)
    return MCEAdapter._instance
