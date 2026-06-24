#!/usr/bin/env python3
"""
MemoryBridge 查询与检索模块。

本模块包含：
- MemoryReader: 从存储中读取各类记忆载体并重建为数据类
- MemoryQueryMixin: MemoryBridge 的查询/检索方法组
  （recall / search_knowledge / get_recent_history / get_workbuddy_ai_news /
   _guess_type / _load_any_type）

MemoryQueryMixin 通过 mixin 模式被 MemoryBridge 继承，
方法内部通过 self 访问 indexer / store / reader / _claw_source 等属性。
"""

import contextlib
import time
from datetime import datetime
from typing import Any

from .memory_types import (
    EpisodicMemory,
    KnowledgeItem,
    MemoryItem,
    MemoryQuery,
    MemoryRecallResult,
    MemoryType,
)


class MemoryReader:
    def __init__(self, store: Any) -> None:
        self.store = store

    def read_knowledge(self, domain: str | None = None) -> list[KnowledgeItem]:
        """Load knowledge memories, optionally filtered by domain.

        Args:
            domain: Optional domain filter (e.g. "general", "frontend").

        Returns:
            List of KnowledgeItem reconstructed from stored records.
        """
        filters = {"domain": domain} if domain else None
        raw_list = self.store.list_all(MemoryType.KNOWLEDGE, filters)
        return [
            KnowledgeItem(
                id=r.get("id", ""),
                domain=r.get("domain", "general"),
                title=r.get("title", ""),
                content=r.get("content", ""),
                tags=r.get("tags", []),
                created_at=r.get("created_at", ""),
                source=r.get("source", ""),
            )
            for r in raw_list
        ]

    def read_episodic(self, limit: int = 50, since: datetime | None = None) -> list[EpisodicMemory]:
        """Load episodic memories, optionally filtered by recency.

        Args:
            limit: Maximum number of items to return (default 50).
            since: Optional datetime; only items created at/after this time are returned.

        Returns:
            List of EpisodicMemory reconstructed from stored records.
        """
        raw_list = self.store.list_all(MemoryType.EPISODIC)
        if since:
            raw_list = [r for r in raw_list if r.get("created_at", "") >= since.isoformat()]
        raw_list = raw_list[:limit]
        return [
            EpisodicMemory(
                id=r.get("id", ""),
                task_description=r.get("task_description", ""),
                finding=r.get("finding", ""),
                worker_id=r.get("worker_id", ""),
                confidence=r.get("confidence", 0.0),
                tags=r.get("tags", []),
                created_at=r.get("created_at", ""),
            )
            for r in raw_list
        ]

    def read_feedback(self, status: str | None = None, feedback_type: str | None = None) -> list[Any]:
        """Load user feedback memories, optionally filtered by status and type.

        Args:
            status: Optional status filter (e.g. "pending", "resolved").
            feedback_type: Optional feedback type filter (e.g. "suggestion", "bug").

        Returns:
            List of UserFeedback reconstructed from stored records.
        """
        from .memory_types import UserFeedback

        filters = {}
        if status:
            filters["status"] = status
        if feedback_type:
            filters["type"] = feedback_type
        raw_list = self.store.list_all(MemoryType.FEEDBACK, filters if filters else None)
        return [
            UserFeedback(
                id=r.get("id", ""),
                user_id=r.get("user_id", "default"),
                feedback_type=r.get("type", "suggestion"),
                content=r.get("content", ""),
                rating=r.get("rating"),
                context=r.get("context", {}),
                created_at=r.get("created_at", ""),
                status=r.get("status", "pending"),
            )
            for r in raw_list
        ]

    def read_patterns(self, category: str | None = None) -> list[Any]:
        """Load persisted skill patterns, optionally filtered by category.

        Args:
            category: Optional category filter (e.g. "auto-generated", "manual").

        Returns:
            List of PersistedPattern reconstructed from stored records.
        """
        from .memory_types import PersistedPattern

        raw_list = self.store.list_all(MemoryType.PATTERN)
        if category:
            raw_list = [r for r in raw_list if r.get("category") == category]
        return [
            PersistedPattern(
                id=r.get("id", ""),
                name=r.get("name", ""),
                slug=r.get("slug", ""),
                category=r.get("category", ""),
                trigger_keywords=r.get("trigger_keywords", []),
                steps_template=r.get("steps_template", []),
                confidence=r.get("confidence", 0.0),
                quality_score=r.get("quality_score", 0.0),
                created_at=r.get("created_at", ""),
            )
            for r in raw_list
        ]

    def read_analysis_cases(self, status: str | None = None) -> list[Any]:
        """Load analysis cases, optionally filtered by status.

        Args:
            status: Optional status filter (e.g. "completed", "open").

        Returns:
            List of AnalysisCase reconstructed from stored records.
        """
        from .memory_types import AnalysisCase

        filters = {"status": status} if status else None
        raw_list = self.store.list_all(MemoryType.ANALYSIS, filters)
        return [
            AnalysisCase(
                id=r.get("id", ""),
                problem=r.get("problem", ""),
                context=r.get("context", {}),
                root_cause=r.get("root_cause", ""),
                solutions=r.get("solutions", []),
                status=r.get("status", "completed"),
                created_at=r.get("created_at", ""),
            )
            for r in raw_list
        ]


class MemoryQueryMixin:
    """Mixin providing query/retrieval methods for MemoryBridge.

    These methods rely on the host class (MemoryBridge) providing:
    - self.config (MemoryConfig)
    - self.indexer (MemoryIndexer)
    - self.store (JsonMemoryStore)
    - self.reader (MemoryReader)
    - self._claw_enabled (bool)
    - self._claw_source (optional WorkBuddyClawSource)
    - self._mce_enabled (bool)
    - self._mce_adapter (optional)
    - self._stats (MemoryStats)
    """

    # Class-level type annotations for attributes provided by the host
    # class (MemoryBridge) via mixin composition.
    config: Any
    indexer: Any
    store: Any
    reader: Any
    _claw_enabled: bool
    _claw_source: Any
    _mce_enabled: bool
    _mce_adapter: Any
    _stats: Any

    def recall(self, query: MemoryQuery) -> MemoryRecallResult:
        """
        [MCE 集成点 Phase B] 跨会话记忆召回

        当前行为: TF-IDF 全文检索 → 按相关性排序返回
        MCE 就绪后:
            1. 先用 MCE 对 query.query_text 做意图分类
               → 确定用户要找什么类型的记忆 (user_preference/decision/correction)
            2. 用分类结果设置 MemoryQuery.memory_type 过滤
            3. 精确召回，噪声过滤率提升 60%+
            4. 示例: recall("用户偏好") → MCE 分类为 user_preference
               → 只搜索 memory_type=FEEDBACK 的记忆

        接口预留: mce_engine 参数 (Optional[MemoryClassificationEngine])
                     enable_mce_recall_filter: bool = False
        """
        start = time.perf_counter()
        self._stats.total_recalls += 1
        if not self.config.enabled or not query.query_text.strip():
            return MemoryRecallResult(
                query_time_ms=(time.perf_counter() - start) * 1000,
            )

        effective_type_filter = query.memory_type

        if self._mce_enabled and self._mce_adapter and not query.memory_type:
            try:
                mce_result = self._mce_adapter.classify(query.query_text, timeout_ms=300)
                if mce_result and mce_result.memory_type:
                    type_mapping = {
                        "preference": "FEEDBACK",
                        "decision": "EPISODIC",
                        "correction": "EPISODIC",
                        "fact": "KNOWLEDGE",
                        "task": "EPISODIC",
                    }
                    mapped_type = type_mapping.get(mce_result.memory_type.lower())
                    if mapped_type:
                        effective_type_filter = mapped_type  # type: ignore[assignment]
            except (ValueError, AttributeError, RuntimeError):
                pass

        claw_items: list[MemoryItem] = []
        if self._claw_enabled and self._claw_source:
            with contextlib.suppress(OSError, AttributeError, ValueError):
                claw_items = self._claw_source.search_by_index(query.query_text, limit=query.limit // 2)

        search_results = self.indexer.search(
            query.query_text,
            type_filter=effective_type_filter,
            domain_filter=query.domain,
            limit=query.limit * 3,
        )
        memories = []
        hit_types: dict[str, int] = {}
        for mid, score in search_results:
            if score < query.min_relevance:
                continue
            item_data = self._load_any_type(mid)
            if item_data is None:
                continue
            item = MemoryItem.from_dict(item_data)
            item.relevance_score = score
            item.last_accessed = datetime.now()
            item.access_count += 1
            memories.append(item)
            mt = item.memory_type.value
            hit_types[mt] = hit_types.get(mt, 0) + 1
            if len(memories) >= query.limit:
                break
        elapsed = (time.perf_counter() - start) * 1000
        if claw_items:
            for ci in claw_items:
                ci.last_accessed = datetime.now()
                memories.append(ci)
                mt = ci.memory_type.value
                hit_types[mt] = hit_types.get(mt, 0) + 1
            memories.sort(key=lambda x: x.relevance_score, reverse=True)
            memories = memories[: query.limit]
        return MemoryRecallResult(
            memories=memories,
            total_found=len(memories),
            query_time_ms=elapsed,
            hit_memory_types=hit_types,
        )

    def search_knowledge(self, keywords: list[str], domain: str | None = None) -> list[KnowledgeItem]:
        """Search knowledge memories by keywords via the indexer.

        Args:
            keywords: List of keyword strings to match.
            domain: Optional domain filter.

        Returns:
            List of KnowledgeItem matching the keywords; empty list if no keywords given.
        """
        if not keywords:
            return []
        results = self.indexer.keyword_search(keywords, domain=domain)
        items = []
        for mid, _score in results:
            data = self.store.load(MemoryType.KNOWLEDGE, mid)
            if data:
                items.append(
                    KnowledgeItem(
                        id=data.get("id", ""),
                        domain=data.get("domain", "general"),
                        title=data.get("title", ""),
                        content=data.get("content", ""),
                        tags=data.get("tags", []),
                        created_at=data.get("created_at", ""),
                        source=data.get("source", ""),
                    )
                )
        return items

    def get_recent_history(self, n: int = 10) -> list[EpisodicMemory]:
        """Return the N most recent episodic memories.

        Args:
            n: Maximum number of recent episodic memories to return (default 10).

        Returns:
            List of EpisodicMemory ordered by recency.
        """
        return self.reader.read_episodic(limit=n)  # type: ignore[no-any-return]

    def get_workbuddy_ai_news(self, days: int = 7) -> list[MemoryItem]:
        """
        Plan B: Retrieve WorkBuddy daily AI news feed.

        Used by Coordinator to auto-inject latest AI industry information
        as context when analyzing technology trends or industry dynamics tasks.

        Args:
            days: Number of days to look back (default 7).

        Returns:
            List[MemoryItem]: News entries in reverse chronological order,
            metadata contains sources/topics/status fields.
        """
        if not self._claw_enabled or not self._claw_source:
            return []
        try:
            return self._claw_source.get_latest_ai_news(days)  # type: ignore[no-any-return]
        except (OSError, AttributeError, ValueError):
            return []

    def _guess_type(self, memory_id: str) -> MemoryType:
        prefix_map = {
            "know_": MemoryType.KNOWLEDGE,
            "fb_": MemoryType.FEEDBACK,
            "epi_": MemoryType.EPISODIC,
            "pat_": MemoryType.PATTERN,
            "anal_": MemoryType.ANALYSIS,
        }
        for prefix, mtype in prefix_map.items():
            if memory_id.startswith(prefix):
                return mtype
        for mtype in MemoryType:
            data = self.store.load(mtype, memory_id)
            if data is not None:
                return mtype
        return MemoryType.KNOWLEDGE

    def _load_any_type(self, memory_id: str) -> dict | None:
        guessed = self._guess_type(memory_id)
        data = self.store.load(guessed, memory_id)
        if data is not None:
            if "memory_type" not in data:
                data["memory_type"] = guessed.value
            return data  # type: ignore[no-any-return]
        for mtype in MemoryType:
            if mtype != guessed:
                data = self.store.load(mtype, memory_id)
                if data is not None:
                    if "memory_type" not in data:
                        data["memory_type"] = mtype.value
                    return data  # type: ignore[no-any-return]
        return None
