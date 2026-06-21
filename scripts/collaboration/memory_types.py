#!/usr/bin/env python3
"""
MemoryBridge 数据类型定义。

本模块包含记忆桥接系统使用的所有数据类与枚举：
MemoryType / MemoryItem / MemoryQuery / MemoryRecallResult /
MemoryConfig / MemoryStats 以及各类记忆载体（KnowledgeItem、
UserFeedback、EpisodicMemory、PersistedPattern、AnalysisCase、ErrorContext）。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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
