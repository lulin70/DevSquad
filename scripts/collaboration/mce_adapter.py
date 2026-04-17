#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCEAdapter — Memory Classification Engine 适配器

v3.2 MVP Line-B: 将本地 MCE (memory-classification-engine) 集成到 TraeMultiAgentSkill

设计原则:
  - 不修改 MCE 源码 —— 它是独立项目
  - MCE 作为可选依赖 —— import 失败时自动降级为无 MCE 模式
  - 所有调用 try/except 包裹 —— 零侵入，不影响主流程
  - 懒加载 (lazy init) —— 不影响冷启动速度

接入方式: Facade 直接 import (不用 HTTP SDK)
集成点: Phase A (capture_execution) 优先, Phase B/C 可选后续迭代

使用示例:
    adapter = MCEAdapter(enable=True)
    if adapter.is_available:
        result = adapter.classify("用户成功登录系统")
        print(result)  # {'type': 'decision', 'confidence': 0.92, ...}
    else:
        print("MCE 不可用, 使用默认分类")
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ============================================================
# 数据模型
# ============================================================

@dataclass
class MCEResult:
    """MCE 分类结果"""
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
    """MCE 适配器状态"""
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
    MCE 记忆分类引擎适配器

    通过 Facade 模式封装 memory_classification_engine,
    提供统一的 classify / store / retrieve 接口。
    当 MCE 不可用时优雅降级（返回 None 或默认值）。

    与现有组件的集成点:
      Phase A: memory_bridge.capture_execution() → adapter.classify(output) → 带类型存储
      Phase B: memory_bridge.recall() → adapter.retrieve_memories() → 类型过滤
      Phase C: scratchpad.write() → adapter.classify(content) → 条目带类型标注
      Dispatcher: dispatch() 内存沉淀步骤 → adapter 作为可选增强

    使用示例:
        adapter = MCEAdapter(enable=True)
        result = adapter.classify("用户完成了登录操作")
        if result:
            print(f"类型: {result.memory_type}, 置信度: {result.confidence}")
        else:
            print("MCE 不可用，使用默认处理")

    线程安全: 所有公共方法都是线程安全的（内部 RLock 保护）
    """

    _instance = None
    _lock = None

    def __init__(self, enable: bool = False):
        """
        初始化 MCE 适配器

        Args:
            enable: 是否启用 MCE (False 则跳过所有初始化)
        """
        import threading
        self._lock = threading.RLock()
        self._status = MCEStatus()
        self._facade = None

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
        强制重新初始化（用于配置变更后）

        先关闭旧连接，再尝试重新初始化。
        """
        self.shutdown()
        self._try_init()

    @staticmethod
    def _normalize_result(raw: Any) -> MCEResult:
        """
        标准化 MCE 返回值为 MCEResult

        兼容多种可能的返回格式:
        - Dict 含 'type' 字段
        - Dict 含 'memory_type' 字段
        - 字符串
        - 其他格式 → 默认值

        Args:
            raw: MCE classify_message 的原始返回值

        Returns:
            MCEResult: 标准化的分类结果
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
