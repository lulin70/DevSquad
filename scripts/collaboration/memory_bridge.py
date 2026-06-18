#!/usr/bin/env python3
"""
MemoryBridge - 记忆桥接系统

将协作系统（Coordinator/Skillifier/Scratchpad）与持久记忆层（memory-bank）连接，
实现跨会话的知识复用、经验捕获、反馈闭环和模式持久化。

核心能力:
- recall(): 任务前召回相关历史经验
- capture_execution(): 执行后自动捕获洞察
- record_feedback(): 用户反馈记录
- persist_pattern(): Skillifier 模式跨会话保留
- search_knowledge(): 知识库关键词搜索
- 生命周期: 遗忘曲线 / 自动压缩 / 清理

使用示例:
    from collaboration.memory_bridge import MemoryBridge, MemoryConfig

    bridge = MemoryBridge(config=MemoryConfig.default())
    result = bridge.recall(MemoryQuery(query_text="微服务架构设计"))
    for mem in result.memories:
        print(f"[{mem.memory_type.value}] {mem.title}: {mem.content[:80]}")
"""

import contextlib
import json
import os
import re
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class MemoryType(Enum):
    KNOWLEDGE = "knowledge"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    FEEDBACK = "feedback"
    PATTERN = "pattern"
    ANALYSIS = "analysis"
    CORRECTION = "correction"


@dataclass
class MemoryItem:
    id: str
    memory_type: MemoryType
    title: str
    content: str
    domain: str | None = None
    tags: list[str] = field(default_factory=list)
    source: str = ""
    relevance_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_days(self) -> float:
        """Return the age of this memory in days since creation.

        Returns:
            Elapsed days between creation time and now as a float.
        """
        return (datetime.now() - self.created_at).total_seconds() / 86400

    def to_dict(self) -> dict:
        """Serialize the memory item to a dictionary.

        Returns:
            Dictionary with all fields, including ISO-formatted timestamps.
        """
        return {
            "id": self.id,
            "memory_type": self.memory_type.value,
            "title": self.title,
            "content": self.content,
            "domain": self.domain,
            "tags": self.tags,
            "source": self.source,
            "relevance_score": self.relevance_score,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryItem":
        """Reconstruct a MemoryItem from a dictionary.

        Args:
            d: Dictionary produced by to_dict(). Must contain id, memory_type,
                title, and content keys.

        Returns:
            A new MemoryItem instance with fields populated from the dictionary.
        """
        return cls(
            id=d["id"],
            memory_type=MemoryType(d["memory_type"]),
            title=d["title"],
            content=d["content"],
            domain=d.get("domain"),
            tags=d.get("tags", []),
            source=d.get("source", ""),
            relevance_score=d.get("relevance_score", 0.0),
            created_at=datetime.fromisoformat(d["created_at"])
            if isinstance(d.get("created_at"), str)
            else datetime.now(),
            last_accessed=datetime.fromisoformat(d["last_accessed"])
            if isinstance(d.get("last_accessed"), str)
            else datetime.now(),
            access_count=d.get("access_count", 0),
            metadata=d.get("metadata", {}),
        )


@dataclass
class MemoryQuery:
    query_text: str = ""
    domain: str | None = None
    memory_type: MemoryType | None = None
    limit: int = 5
    min_relevance: float = 0.3
    time_range: tuple[datetime, datetime] | None = None


@dataclass
class MemoryRecallResult:
    memories: list[MemoryItem] = field(default_factory=list)
    total_found: int = 0
    query_time_ms: float = 0.0
    hit_memory_types: dict[str, int] = field(default_factory=dict)


@dataclass
class MemoryConfig:
    enabled: bool = True
    base_dir: str | None = None
    auto_capture: bool = True
    auto_index: bool = True
    max_episodic_memories: int = 1000
    max_knowledge_items: int = 5000
    index_rebuild_threshold: int = 50
    relevance_threshold: float = 0.3
    retention_days: int = 90
    compress_old_memories: bool = True
    enable_semantic_search: bool = False

    @classmethod
    def default(cls) -> "MemoryConfig":
        """Return the default memory configuration.

        Returns:
            A MemoryConfig instance with default field values.
        """
        return cls()

    @classmethod
    def lightweight(cls) -> "MemoryConfig":
        """Return a lightweight memory configuration for low-overhead usage.

        Returns:
            A MemoryConfig with auto-capture and auto-index disabled and a
            smaller episodic memory cap.
        """
        return cls(auto_capture=False, auto_index=False, max_episodic_memories=100)

    @classmethod
    def full(cls) -> "MemoryConfig":
        """Return a full-featured memory configuration for maximum recall.

        Returns:
            A MemoryConfig with larger memory caps and semantic search enabled.
        """
        return cls(max_episodic_memories=5000, max_knowledge_items=20000, enable_semantic_search=True)


@dataclass
class MemoryStats:
    total_memories: int = 0
    by_type_counts: dict[str, int] = field(default_factory=dict)
    oldest_memory: str | None = None
    newest_memory: str | None = None
    storage_size_kb: float = 0.0
    index_built: bool = False
    last_index_time: str | None = None
    total_captures: int = 0
    total_recalls: int = 0
    claw_enabled: bool = False
    claw_item_count: int = 0


@dataclass
class KnowledgeItem:
    id: str
    domain: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    source: str = ""


@dataclass
class UserFeedback:
    id: str
    user_id: str = "default"
    feedback_type: str = "suggestion"
    content: str = ""
    rating: int | None = None
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    status: str = "pending"


@dataclass
class EpisodicMemory:
    id: str
    task_description: str
    finding: str
    worker_id: str = ""
    confidence: float = 0.0
    tags: list[str] = field(default_factory=list)
    created_at: str = ""


@dataclass
class PersistedPattern:
    id: str
    name: str
    slug: str
    category: str
    trigger_keywords: list[str] = field(default_factory=list)
    steps_template: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    quality_score: float = 0.0
    created_at: str = ""


@dataclass
class AnalysisCase:
    id: str
    problem: str
    context: dict[str, Any] = field(default_factory=dict)
    root_cause: str = ""
    solutions: list[str] = field(default_factory=list)
    status: str = "completed"
    created_at: str = ""


@dataclass
class ErrorContext:
    error_message: str
    task_description: str = ""
    worker_id: str = ""
    stack_trace: str = ""
    timestamp: str = ""


# WorkBuddyClawSource moved to memory_claw_source.py (backward-compatible re-export below)
from .memory_claw_source import WorkBuddyClawSource  # noqa: E402

# Forgetting helpers moved to memory_forgetting.py
from .memory_forgetting import (  # noqa: E402
    cleanup_expired_memories as _cleanup_expired_memories,
)
from .memory_forgetting import (  # noqa: E402
    compress_old_memories as _compress_old_memories,
)
from .memory_forgetting import (  # noqa: E402
    forgetting_weight as _forgetting_weight,
)

# MemoryIndexer moved to memory_index.py (backward-compatible re-export below)
from .memory_index import MemoryIndexer  # noqa: E402


class MemoryStore(ABC):
    @abstractmethod
    def save(self, memory_type: MemoryType, data: dict) -> str:
        """Persist a memory entry of the given type.

        Args:
            memory_type: Type of memory to store.
            data: Dictionary payload to persist.

        Returns:
            The identifier of the stored memory entry.
        """
        pass

    @abstractmethod
    def load(self, memory_type: MemoryType, item_id: str) -> dict | None:
        """Load a memory entry by type and ID.

        Args:
            memory_type: Type of memory to load.
            item_id: Identifier of the entry to load.

        Returns:
            The stored dictionary, or None when not found.
        """
        pass

    @abstractmethod
    def list_all(self, memory_type: MemoryType, filters: dict | None = None) -> list[dict]:
        """List all stored entries of a given memory type.

        Args:
            memory_type: Type of memory to list.
            filters: Optional dictionary of field-value pairs to filter by.

        Returns:
            List of matching entry dictionaries.
        """
        pass

    @abstractmethod
    def delete(self, memory_type: MemoryType, item_id: str) -> bool:
        """Delete a memory entry by type and ID.

        Args:
            memory_type: Type of memory to delete.
            item_id: Identifier of the entry to delete.

        Returns:
            True when the entry existed and was removed, False otherwise.
        """
        pass


class JsonMemoryStore(MemoryStore):
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self._lock = threading.RLock()
        self._type_dirs = {
            MemoryType.KNOWLEDGE: self.base_dir / "knowledge_base" / "domains",
            MemoryType.FEEDBACK: self.base_dir / "user_experience" / "feedback",
            MemoryType.PATTERN: self.base_dir / "persisted_patterns",
            MemoryType.ANALYSIS: self.base_dir / "analysis_cases",
            MemoryType.EPISODIC: self.base_dir / "episodic",
            MemoryType.SEMANTIC: self.base_dir / "semantic",
            MemoryType.CORRECTION: self.base_dir / "corrections",
        }

    def _get_file_path(self, mtype: MemoryType, item_id: str) -> Path:
        if ".." in item_id or "/" in item_id or "\\" in item_id:
            raise ValueError(f"Invalid item_id (path traversal): {item_id}")
        dir_path = self._type_dirs.get(mtype, self.base_dir / "other")
        if mtype == MemoryType.KNOWLEDGE:
            domain = "general"
            path = dir_path / domain / f"{item_id}.json"
        else:
            path = dir_path / f"{item_id}.json"
        if not path.resolve().is_relative_to(self.base_dir.resolve()):
            raise ValueError(f"Path traversal detected: {item_id}")
        return path

    def save(self, memory_type: MemoryType, data: dict) -> str:
        """Persist a memory entry to a JSON file on disk.

        Args:
            memory_type: Type of memory to store.
            data: Dictionary payload to persist. An "id" is generated when absent.

        Returns:
            The identifier of the stored memory entry.
        """
        item_id = data.get("id", f"{memory_type.value}_{uuid.uuid4().hex[:12]}_{int(time.time())}")
        file_path = self._get_file_path(memory_type, item_id)
        with self._lock:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return item_id

    def load(self, memory_type: MemoryType, item_id: str) -> dict | None:
        """Load a memory entry from a JSON file on disk.

        Args:
            memory_type: Type of memory to load.
            item_id: Identifier of the entry to load.

        Returns:
            The stored dictionary, or None when the file is missing or invalid.
        """
        file_path = self._get_file_path(memory_type, item_id)
        with self._lock:
            if not file_path.exists():
                return None
            try:
                with open(file_path, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                return None

    def list_all(self, memory_type: MemoryType, filters: dict | None = None) -> list[dict]:
        """List all stored JSON entries of a given memory type.

        Args:
            memory_type: Type of memory to list.
            filters: Optional dictionary of field-value pairs to filter by.

        Returns:
            List of matching entry dictionaries, sorted by file name.
        """
        results = []
        dir_path = self._type_dirs.get(memory_type, self.base_dir / "other")
        with self._lock:
            if not dir_path.exists():
                return results
            pattern = "**/*.json"
            for json_file in sorted(dir_path.glob(pattern)):
                try:
                    with open(json_file, encoding="utf-8") as f:
                        data = json.load(f)
                    if filters:
                        match = True
                        for k, v in filters.items():
                            if data.get(k) != v:
                                match = False
                                break
                        if not match:
                            continue
                    results.append(data)
                except (OSError, json.JSONDecodeError):
                    continue
        return results

    def delete(self, memory_type: MemoryType, item_id: str) -> bool:
        """Delete a memory entry's JSON file from disk.

        Args:
            memory_type: Type of memory to delete.
            item_id: Identifier of the entry to delete.

        Returns:
            True when the file existed and was removed, False otherwise.
        """
        file_path = self._get_file_path(memory_type, item_id)
        with self._lock:
            if file_path.exists():
                file_path.unlink()
                return True
        return False


class MemoryWriter:
    def __init__(self, store: MemoryStore, indexer: MemoryIndexer | None = None):
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
        return item_id

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
        return item_id

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
        return item_id

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
        return item_id

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
        return item_id

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


class MemoryReader:
    def __init__(self, store: MemoryStore):
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

    def read_feedback(self, status: str | None = None, feedback_type: str | None = None) -> list[UserFeedback]:
        """Load user feedback memories, optionally filtered by status and type.

        Args:
            status: Optional status filter (e.g. "pending", "resolved").
            feedback_type: Optional feedback type filter (e.g. "suggestion", "bug").

        Returns:
            List of UserFeedback reconstructed from stored records.
        """
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

    def read_patterns(self, category: str | None = None) -> list[PersistedPattern]:
        """Load persisted skill patterns, optionally filtered by category.

        Args:
            category: Optional category filter (e.g. "auto-generated", "manual").

        Returns:
            List of PersistedPattern reconstructed from stored records.
        """
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

    def read_analysis_cases(self, status: str | None = None) -> list[AnalysisCase]:
        """Load analysis cases, optionally filtered by status.

        Args:
            status: Optional status filter (e.g. "completed", "open").

        Returns:
            List of AnalysisCase reconstructed from stored records.
        """
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


class MemoryBridge:
    def __init__(self, base_dir: str | None = None, config: MemoryConfig | None = None, mce_adapter=None):
        """
        初始化记忆桥接器

        Args:
            base_dir: 记忆存储根目录 (默认: data/memory-bank)
            config: 记忆配置项 (MemoryConfig, 默认使用默认配置)
            mce_adapter: MCE 记忆分类引擎适配器 (可选, v3.2 集成)
                传入后自动启用以下增强:
                - capture_execution(): 自动用 MCE 分类 scratchpad 内容,
                  preference→FEEDBACK, decision→EPISODIC, fact→KNOWLEDGE
                - recall(): 自动用 MCE 对查询文本做意图分类并过滤结果
                - shutdown(): 联动关闭 MCE 连接
        """
        self.config = config or MemoryConfig.default()
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "memory-bank")
        self.base_dir = os.path.abspath(base_dir)
        self.store: JsonMemoryStore = JsonMemoryStore(self.base_dir)
        self.indexer: MemoryIndexer = MemoryIndexer()
        self.writer: MemoryWriter = MemoryWriter(self.store, self.indexer)
        self.reader: MemoryReader = MemoryReader(self.store)
        self._stats = MemoryStats(total_captures=0, total_recalls=0)
        self._inner_lock = threading.RLock()

        self._mce_adapter = mce_adapter
        self._mce_enabled = mce_adapter is not None and getattr(mce_adapter, "is_available", False)

        self._claw_source: WorkBuddyClawSource | None = None
        self._claw_enabled = False
        try:
            self._claw_source = WorkBuddyClawSource()
            if self._claw_source.is_available:
                self._claw_enabled = True
        except (OSError, AttributeError):
            pass

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
                        effective_type_filter = mapped_type
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

    def capture_execution(self, execution_record=None, scratchpad_entries=None) -> str | None:
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
            entry_type = getattr(entry, "entry_type", None)
            entry_type_val = entry_type.value if hasattr(entry_type, "value") else str(entry_type)
            if entry_type_val != "FINDING":
                continue
            confidence = getattr(entry, "confidence", 0.8) or 0.8
            if confidence < 0.7:
                continue
            content = getattr(entry, "content", "") or ""
            if len(content) > 5000:
                content = content[:5000] + "...[TRUNCATED]"
            task_desc = getattr(execution_record, "task_description", "") or ""
            worker_id = getattr(execution_record, "worker_id", "") or ""

            mce_memory_type = None
            mce_confidence = confidence
            if self._mce_enabled and self._mce_adapter and content:
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

            tags = self._extract_tags(task_desc + " " + content)

            if mce_memory_type == "KNOWLEDGE":
                knowledge = KnowledgeMemory(  # noqa: F821
                    id=f"know_{uuid.uuid4().hex[:12]}_{int(time.time())}",
                    domain=task_desc[:100] if task_desc else "general",
                    fact=content,
                    source=worker_id or "multi-agent",
                    confidence=mce_confidence,
                    tags=tags,
                    created_at=datetime.now().isoformat(),
                )
                self.writer.write_knowledge(knowledge)
                captured_id = knowledge.id
            elif mce_memory_type == "FEEDBACK":
                feedback = FeedbackMemory(  # noqa: F821
                    id=f"feed_{uuid.uuid4().hex[:12]}_{int(time.time())}",
                    category="preference",
                    content=content,
                    source=worker_id or "user",
                    severity="info",
                    tags=tags,
                    created_at=datetime.now().isoformat(),
                )
                self.writer.write_feedback(feedback)
                captured_id = feedback.id
            else:
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
        return captured_id

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
        return self.writer.write_feedback(feedback)

    def persist_pattern(self, pattern) -> str | None:
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
        return self.writer.write_pattern(persisted)

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
        return self.writer.write_analysis(analysis)

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

    def get_statistics(self) -> MemoryStats:
        """Compute aggregate statistics about the memory store and bridges.

        Returns:
            MemoryStats populated with capture/recall counters, per-type counts,
            index status, and WorkBuddy (Claw) bridge information.
        """
        stats = MemoryStats(
            total_captures=self._stats.total_captures,
            total_recalls=self._stats.total_recalls,
            index_built=self.indexer.is_built,
            last_index_time=datetime.now().isoformat() if self.indexer.is_built else None,
        )
        type_counts: dict[str, int] = {}
        all_items = []
        for mtype in MemoryType:
            try:
                raw = self.store.list_all(mtype)
                type_counts[mtype.value] = len(raw)
                all_items.extend(raw)
            except (OSError, ValueError, AttributeError):
                type_counts[mtype.value] = 0
        stats.by_type_counts = type_counts
        stats.total_memories = sum(type_counts.values())
        if all_items:
            dates = [r.get("created_at", "") for r in all_items if r.get("created_at")]
            if dates:
                stats.newest_memory = max(dates)
                stats.oldest_memory = min(dates)
        stats.claw_enabled = self._claw_enabled
        if self._claw_source and self._claw_enabled:
            try:
                core_count = sum(
                    1 for f in self._claw_source.CORE_FILE_MAPPING if (self._claw_source._memory_dir / f).exists()
                )
                daily_count = (
                    min(30, sum(1 for _ in self._claw_source._wb_memory_dir.glob("2026-*.md")))
                    if self._claw_source._wb_memory_dir.exists()
                    else 0
                )
                stats.claw_item_count = core_count + daily_count
            except (OSError, AttributeError):
                stats.claw_item_count = 0
        else:
            stats.claw_item_count = 0
        return stats

    def get_recent_history(self, n: int = 10) -> list[EpisodicMemory]:
        """Return the N most recent episodic memories.

        Args:
            n: Maximum number of recent episodic memories to return (default 10).

        Returns:
            List of EpisodicMemory ordered by recency.
        """
        return self.reader.read_episodic(limit=n)

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
            return self._claw_source.get_latest_ai_news(days)
        except (OSError, AttributeError, ValueError):
            return []

    def rebuild_index(self) -> None:
        """Rebuild the in-memory search index from all persisted memory items."""
        all_items: list[MemoryItem] = []
        for mtype in MemoryType:
            try:
                raw_list = self.store.list_all(mtype)
                for r in raw_list:
                    try:
                        item = MemoryItem.from_dict(r)
                        all_items.append(item)
                    except (ValueError, KeyError, AttributeError):
                        continue
            except (OSError, ValueError, AttributeError):
                continue
        self.indexer.build_index(all_items)

    def print_diagnostics(self) -> str:
        """Build a human-readable diagnostics report for the memory bridge.

        Returns:
            Multi-line string summarizing memory counts, index status, and Claw bridge state.
        """
        s = self.get_statistics()
        lines = [
            "=== MemoryBridge Diagnostics ===",
            f"Total Memories: {s.total_memories}",
            f"By Type: {s.by_type_counts}",
            f"Index Built: {'Yes' if s.index_built else 'No'}",
            f"Captures: {s.total_captures} | Recalls: {s.total_recalls}",
            f"Index Size: {self.indexer.size} documents",
            "--- Memory Types ---",
        ]
        for t, count in sorted(s.by_type_counts.items()):
            lines.append(f"  {t}: {count}")
        lines.append("--- WorkBuddy (Claw) Bridge ---")
        lines.append(f"  Available: {'Yes' if s.claw_enabled else 'No'}")
        if self._claw_source:
            all_claw = self._claw_source.load_all_memories()
            lines.append(
                f"  Items: {len(all_claw)} ({sum(1 for a in all_claw if a.memory_type == MemoryType.EPISODIC)} episodic)"
            )
        return "\n".join(lines)

    def forgetting_weight(self, memory: MemoryItem) -> float:
        """Compute the forgetting weight for a memory item.

        Args:
            memory: MemoryItem whose forgetting weight is requested.

        Returns:
            Float weight in [0, 1]; lower means more likely to be forgotten.
        """
        return _forgetting_weight(memory)

    def compress_old_memories(self) -> int:
        """Compress aged memory items according to the configured policy.

        Returns:
            Number of memory items compressed.
        """
        return _compress_old_memories(self.store, self.config)

    def cleanup_expired_memories(self) -> int:
        """Remove memory items that have exceeded their retention window.

        Returns:
            Number of memory items removed.
        """
        return _cleanup_expired_memories(self.store, self.config, self.indexer)

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
            return data
        for mtype in MemoryType:
            if mtype != guessed:
                data = self.store.load(mtype, memory_id)
                if data is not None:
                    if "memory_type" not in data:
                        data["memory_type"] = mtype.value
                    return data
        return None

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        words = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", text)
        return list(set(words))[:10]

    def shutdown(self) -> None:
        """Release external resources, closing the MCE adapter if one is attached."""
        if self._mce_adapter:
            with contextlib.suppress(AttributeError, RuntimeError, OSError):
                self._mce_adapter.shutdown()
