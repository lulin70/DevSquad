#!/usr/bin/env python3
"""
MemoryBridge - 记忆桥接系统 (Re-export Hub)

将协作系统（Coordinator/Skillifier/Scratchpad）与持久记忆层（memory-bank）连接，
实现跨会话的知识复用、经验捕获、反馈闭环和模式持久化。

本模块已按职责拆分为多个子模块，此处保留 MemoryBridge 核心类与存储层，
并做向后兼容的 re-export：

- memory_types.py: 数据类与枚举定义
- memory_serializer.py: MemoryWriter + 序列化/捕获方法 (MemorySerializerMixin)
- memory_query.py: MemoryReader + 查询/检索方法 (MemoryQueryMixin)
- memory_index.py: MemoryIndexer
- memory_forgetting.py: 遗忘曲线 / 压缩 / 清理
- memory_claw_source.py: WorkBuddyClawSource

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
import threading
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

# WorkBuddyClawSource moved to memory_claw_source.py (backward-compatible re-export)
from .memory_claw_source import WorkBuddyClawSource  # noqa: F401

# Forgetting helpers moved to memory_forgetting.py
from .memory_forgetting import (  # noqa: F401
    cleanup_expired_memories as _cleanup_expired_memories,
)
from .memory_forgetting import (  # noqa: F401
    compress_old_memories as _compress_old_memories,
)
from .memory_forgetting import (  # noqa: F401
    forgetting_weight as _forgetting_weight,
)

# MemoryIndexer moved to memory_index.py (backward-compatible re-export)
from .memory_index import MemoryIndexer  # noqa: F401
from .memory_query import (
    MemoryQueryMixin,
    MemoryReader,  # noqa: F401
)

# Re-export MemoryWriter and MemoryReader for backward compatibility
# Re-export serializer/query mixins (used by MemoryBridge below)
from .memory_serializer import (
    MemorySerializerMixin,
    MemoryWriter,  # noqa: F401
)

# Re-export data types for backward compatibility
from .memory_types import (  # noqa: F401
    AnalysisCase,
    EpisodicMemory,
    ErrorContext,
    KnowledgeItem,
    MemoryConfig,
    MemoryItem,
    MemoryQuery,
    MemoryRecallResult,
    MemoryStats,
    MemoryType,
    PersistedPattern,
    UserFeedback,
)


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
        return item_id  # type: ignore[no-any-return]

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
                    return json.load(f)  # type: ignore[no-any-return]
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
        results: list[dict] = []
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


class MemoryBridge(MemorySerializerMixin, MemoryQueryMixin):
    def __init__(self, base_dir: str | None = None, config: MemoryConfig | None = None, mce_adapter: Any = None):
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

    def shutdown(self) -> None:
        """Release external resources, closing the MCE adapter if one is attached."""
        if self._mce_adapter:
            with contextlib.suppress(AttributeError, RuntimeError, OSError):
                self._mce_adapter.shutdown()
