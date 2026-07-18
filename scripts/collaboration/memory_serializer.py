#!/usr/bin/env python3
"""
MemoryBridge 序列化与捕获模块。

本模块包含：
- MemoryWriter: 将各类记忆载体写入存储并更新索引
- MemorySerializerMixin: MemoryBridge 的捕获/序列化方法组
  （capture_execution / record_feedback / persist_pattern / learn_from_mistake）

MemorySerializerMixin 通过 mixin 模式被 MemoryBridge 继承，
方法内部通过 self 访问 writer / config / _mce_adapter 等属性。
"""

import json
import re
import time
import uuid
from datetime import datetime
from typing import Any, cast

from .memory_types import (
    AnalysisCase,
    EpisodicMemory,
    ErrorContext,
    KnowledgeItem,
    MemoryItem,
    MemoryType,
    PersistedPattern,
    UserFeedback,
)


class MemoryWriter:
    def __init__(self, store: Any, indexer: Any = None) -> None:
        self.store = store
        self.indexer = indexer
        self._capture_count = 0

    def write_knowledge(self, item: KnowledgeItem) -> str:
        """Persist a knowledge item and add it to the index.

        Args:
            item: KnowledgeItem to store.

        Returns:
            The identifier of the stored knowledge entry.
        """
        data = {
            "id": item.id,
            "domain": item.domain,
            "title": item.title,
            "content": item.content,
            "tags": item.tags,
            "source": item.source,
            "created_at": item.created_at or datetime.now().isoformat(),
        }
        item_id = self.store.save(MemoryType.KNOWLEDGE, data)
        if self.indexer:
            mem_item = MemoryItem(
                id=item_id,
                memory_type=MemoryType.KNOWLEDGE,
                title=item.title,
                content=item.content,
                domain=item.domain,
                tags=item.tags,
                source=item.source,
            )
            self.indexer.add_to_index(mem_item)
        return cast(str, item_id)

    def write_episodic(self, memory: EpisodicMemory) -> str:
        """Persist an episodic memory and add it to the index.

        Args:
            memory: EpisodicMemory to store.

        Returns:
            The identifier of the stored episodic entry.
        """
        data = {
            "id": memory.id,
            "task_description": memory.task_description,
            "finding": memory.finding,
            "worker_id": memory.worker_id,
            "confidence": memory.confidence,
            "tags": memory.tags,
            "created_at": memory.created_at or datetime.now().isoformat(),
        }
        item_id = self.store.save(MemoryType.EPISODIC, data)
        if self.indexer:
            mem_item = MemoryItem(
                id=item_id,
                memory_type=MemoryType.EPISODIC,
                title=memory.finding[:60],
                content=memory.finding,
                tags=memory.tags,
                source=memory.worker_id,
                metadata={"confidence": memory.confidence},
            )
            self.indexer.add_to_index(mem_item)
        self._capture_count += 1
        return cast(str, item_id)

    def write_feedback(self, feedback: UserFeedback) -> str:
        """Persist user feedback and add it to the index.

        Args:
            feedback: UserFeedback to store.

        Returns:
            The identifier of the stored feedback entry.
        """
        data = {
            "id": feedback.id,
            "user_id": feedback.user_id,
            "type": feedback.feedback_type,
            "content": feedback.content,
            "rating": feedback.rating,
            "context": feedback.context,
            "created_at": feedback.created_at or datetime.now().isoformat(),
            "status": feedback.status,
        }
        item_id = self.store.save(MemoryType.FEEDBACK, data)
        if self.indexer:
            mem_item = MemoryItem(
                id=item_id,
                memory_type=MemoryType.FEEDBACK,
                title=f"[{feedback.feedback_type}] {feedback.content[:40]}",
                content=feedback.content,
                tags=[feedback.feedback_type],
                metadata={"rating": feedback.rating},
            )
            self.indexer.add_to_index(mem_item)
        return cast(str, item_id)

    def write_pattern(self, pattern: PersistedPattern) -> str:
        """Persist a pattern and add it to the index.

        Args:
            pattern: PersistedPattern to store.

        Returns:
            The identifier of the stored pattern entry.
        """
        data = {
            "id": pattern.id,
            "name": pattern.name,
            "slug": pattern.slug,
            "category": pattern.category,
            "trigger_keywords": pattern.trigger_keywords,
            "steps_template": pattern.steps_template,
            "confidence": pattern.confidence,
            "quality_score": pattern.quality_score,
            "created_at": pattern.created_at or datetime.now().isoformat(),
        }
        item_id = self.store.save(MemoryType.PATTERN, data)
        if self.indexer:
            mem_item = MemoryItem(
                id=item_id,
                memory_type=MemoryType.PATTERN,
                title=pattern.name,
                content=json.dumps(pattern.steps_template, ensure_ascii=False)[:500],
                domain=pattern.category,
                tags=pattern.trigger_keywords,
                metadata={"quality_score": pattern.quality_score, "confidence": pattern.confidence},
            )
            self.indexer.add_to_index(mem_item)
        return cast(str, item_id)

    def write_analysis(self, analysis: AnalysisCase) -> str:
        """Persist an analysis case (problem/root-cause/solutions) into the memory store.

        Args:
            analysis: AnalysisCase to persist.

        Returns:
            Identifier of the stored analysis memory item.
        """
        data = {
            "id": analysis.id,
            "problem": analysis.problem,
            "context": analysis.context,
            "root_cause": analysis.root_cause,
            "solutions": analysis.solutions,
            "status": analysis.status,
            "created_at": analysis.created_at or datetime.now().isoformat(),
        }
        item_id = self.store.save(MemoryType.ANALYSIS, data)
        if self.indexer:
            mem_item = MemoryItem(
                id=item_id,
                memory_type=MemoryType.ANALYSIS,
                title=analysis.problem[:60],
                content=analysis.root_cause,
                tags=self._extract_tags(analysis.problem),
                metadata={"solutions_count": len(analysis.solutions)},
            )
            self.indexer.add_to_index(mem_item)
        return cast(str, item_id)

    def batch_write(self, items: list[MemoryItem]) -> int:
        """Persist multiple memory items, skipping any that fail to save.

        Args:
            items: List of MemoryItem instances to persist.

        Returns:
            Number of items successfully written.
        """
        success = 0
        for item in items:
            data = item.to_dict()
            try:
                self.store.save(item.memory_type, data)
                if self.indexer:
                    self.indexer.add_to_index(item)
                success += 1
            except (OSError, ValueError, AttributeError, KeyError):
                pass
        return success

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        words = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", text)
        return list(set(words))[:10]


class MemorySerializerMixin:
    """Mixin providing capture/serialization methods for MemoryBridge.

    These methods rely on the host class (MemoryBridge) providing:
    - self.config (MemoryConfig)
    - self.writer (MemoryWriter)
    - self._mce_enabled (bool)
    - self._mce_adapter (optional)
    - self._stats (MemoryStats)
    """

    # Class-level type annotations for attributes provided by the host
    # class (MemoryBridge) via mixin composition.
    config: Any
    writer: Any
    _mce_enabled: bool
    _mce_adapter: Any
    _stats: Any

    def capture_execution(self, execution_record: Any = None, scratchpad_entries: Any = None) -> str | None:
        """
        [MCE 集成点 Phase A] Worker 执行结果 → 记忆沉淀

        当前行为: 手动判断 entry_type=="FINDING" → 存为 EPISODIC 类型
        MCE 就绪后:
            1. 将 scratchpad_entry.content 传入 MCE.process_message()
            2. 用返回的 type/correction/preference/decision 标签替代手动类型推断
            3. 用 MCE 的 confidence 替代默认 0.8
            4. 示例: "我选择了方案B因为A太复杂了"
               → MCE 返回 {type: correction, conf: 0.89, tier: episodic}
               → MemoryBridge 直接用此分类写入，无需 AI 猜测

        接口预留: mce_engine 参数 (Optional[MemoryClassificationEngine])
                     enable_mce_classify: bool = False (配置开关)
        """
        if not self.config.auto_capture or scratchpad_entries is None:
            return None
        captured_id = None
        for entry in scratchpad_entries:
            if not self._is_capturable_finding(entry):
                continue
            confidence = getattr(entry, "confidence", 0.8) or 0.8
            content = getattr(entry, "content", "") or ""
            if len(content) > 5000:
                content = content[:5000] + "...[TRUNCATED]"
            task_desc = getattr(execution_record, "task_description", "") or ""
            worker_id = getattr(execution_record, "worker_id", "") or ""

            mce_memory_type, mce_confidence = self._mce_classify(content, confidence)
            tags = self._extract_tags(task_desc + " " + content)
            captured_id = self._write_captured_memory(
                mce_memory_type, content, task_desc, worker_id, tags, mce_confidence
            )
        return captured_id

    @staticmethod
    def _is_capturable_finding(entry: Any) -> bool:
        """Return True only for FINDING entries with sufficient confidence."""
        entry_type = getattr(entry, "entry_type", None)
        entry_type_val = getattr(entry_type, "value", None)
        if not entry_type_val:
            entry_type_val = str(entry_type)
        if entry_type_val != "FINDING":
            return False
        confidence = getattr(entry, "confidence", 0.8) or 0.8
        return confidence >= 0.7

    def _mce_classify(self, content: str, confidence: float) -> tuple[str | None, float]:
        """Run MCE classification when enabled, returning (memory_type, confidence)."""
        mce_memory_type: str | None = None
        mce_confidence = confidence
        if not (self._mce_enabled and self._mce_adapter and content):
            return mce_memory_type, mce_confidence
        try:
            mce_result = self._mce_adapter.classify(content, timeout_ms=500)
            if mce_result:
                mce_confidence = max(confidence, mce_result.confidence)
                if mce_result.memory_type:
                    type_hint_map = {
                        "preference": "FEEDBACK",
                        "decision": "EPISODIC",
                        "correction": "EPISODIC",
                        "fact": "KNOWLEDGE",
                    }
                    mce_memory_type = type_hint_map.get(mce_result.memory_type.lower())
        except (ValueError, AttributeError, RuntimeError):
            pass
        return mce_memory_type, mce_confidence

    def _write_captured_memory(
        self,
        mce_memory_type: str | None,
        content: str,
        task_desc: str,
        worker_id: str,
        tags: list[str],
        mce_confidence: float,
    ) -> str | None:
        """Persist the captured memory using the appropriate writer, returning its id."""
        if mce_memory_type == "KNOWLEDGE":
            knowledge = KnowledgeItem(
                id=f"know_{uuid.uuid4().hex[:12]}_{int(time.time())}",
                domain=task_desc[:100] if task_desc else "general",
                title=content[:100] if content else "untitled",
                content=content,
                source=worker_id or "multi-agent",
                tags=tags,
                created_at=datetime.now().isoformat(),
            )
            self.writer.write_knowledge(knowledge)
            return knowledge.id
        if mce_memory_type == "FEEDBACK":
            feedback = UserFeedback(
                id=f"feed_{uuid.uuid4().hex[:12]}_{int(time.time())}",
                user_id=worker_id or "user",
                feedback_type="preference",
                content=content,
                created_at=datetime.now().isoformat(),
            )
            self.writer.write_feedback(feedback)
            return feedback.id
        episodic = EpisodicMemory(
            id=f"epi_{uuid.uuid4().hex[:12]}_{int(time.time())}",
            task_description=task_desc[:200],
            finding=content,
            worker_id=worker_id,
            confidence=mce_confidence,
            tags=tags,
            created_at=datetime.now().isoformat(),
        )
        captured_id = self.writer.write_episodic(episodic)
        self._stats.total_captures += 1
        return str(captured_id) if captured_id is not None else None

    def record_feedback(self, feedback: UserFeedback) -> str:
        """
        [MCE 集成点 Phase A] 用户反馈记录

        当前行为: 直接写入 FEEDBACK 类型
        MCE 就绪后: 对 feedback.content 做 sentiment + intent 分类
            → 自动标记正面/负面/中性情绪
            → 关联到相关 decision/correction 记忆

        接口预留: mce_engine 参数
        """
        if feedback.id == "":
            feedback.id = f"fb_{uuid.uuid4().hex[:12]}_{int(time.time())}"
        if not feedback.created_at:
            feedback.created_at = datetime.now().isoformat()
        return cast(str, self.writer.write_feedback(feedback))

    def persist_pattern(self, pattern: Any) -> str | None:
        """
        [MCE 集成点 Phase D] Skillifier 生成的 Skill 模式持久化

        当前行为: 直接写入 PATTERN 类型
        MCE 就绪后: 对 pattern.name + steps_template 做 decision 分类
            → 标记哪些步骤是关键决策点
            → 关联到历史 correction/decision 记忆
            → Skillifier 学习素材增强: 用 MCE 标记提取"什么导致了成功"

        接口预留: mce_engine 参数
        """
        if not hasattr(pattern, "name") or not hasattr(pattern, "steps_template"):
            return None
        quality = getattr(pattern, "confidence", 0) or 0
        if isinstance(quality, (int, float)) and quality < 0.7:
            return None
        qs = getattr(pattern, "quality_score", quality * 100) or (quality * 100 if quality else 0)
        if qs < 70:
            return None
        slug = getattr(pattern, "pattern_id", pattern.name.lower().replace(" ", "-")) or ""
        persisted = PersistedPattern(
            id=f"pat_{uuid.uuid4().hex[:12]}_{int(time.time())}",
            name=pattern.name,
            slug=slug,
            category=getattr(pattern, "category", "auto-generated"),
            trigger_keywords=getattr(pattern, "trigger_keywords", []) or [],
            steps_template=[
                s.to_dict() if hasattr(s, "to_dict") else s for s in getattr(pattern, "steps_template", []) or []
            ],
            confidence=float(getattr(pattern, "confidence", quality))
            if getattr(pattern, "confidence", None) is not None
            else quality,
            quality_score=qs,
            created_at=datetime.now().isoformat(),
        )
        return cast(str, self.writer.write_pattern(persisted))

    def learn_from_mistake(self, error_context: ErrorContext) -> str:
        """Convert an error context into a persisted analysis case for future reference.

        Args:
            error_context: ErrorContext describing the failure (message, task, worker, timestamp).

        Returns:
            Identifier of the stored analysis memory item.
        """
        analysis = AnalysisCase(
            id=f"anal_{uuid.uuid4().hex[:12]}_{int(time.time())}",
            problem=error_context.error_message[:200],
            context={
                "task": error_context.task_description[:200],
                "worker": error_context.worker_id,
                "timestamp": error_context.timestamp,
            },
            root_cause=f"Error during execution: {error_context.error_message[:100]}",
            solutions=[
                f"Review the error context: {error_context.error_message[:100]}",
                "Check input parameters and dependencies",
                "Add validation to prevent recurrence",
                "Document the solution for future reference",
            ],
            status="completed",
            created_at=datetime.now().isoformat(),
        )
        return cast(str, self.writer.write_analysis(analysis))

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        words = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", text)
        return list(set(words))[:10]
