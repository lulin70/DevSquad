#!/usr/bin/env python3
"""
MemoryForgetting - 遗忘曲线 + 过期清理逻辑

实现基于 Ebbinghaus 遗忘曲线的记忆衰减权重计算，
以及对陈旧记忆的压缩与清理策略。

- forgetting_weight(): 根据记忆年龄和访问频率计算保留权重
- compress_old_memories(): 压缩 60 天以上的情景记忆
- cleanup_expired_memories(): 清理超过保留期的记忆

从 memory_bridge.py 拆分而来，MemoryBridge 的对应方法会委托到此处。
"""

import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from .memory_types import MemoryItem, MemoryType

if TYPE_CHECKING:
    from .memory_bridge import JsonMemoryStore, MemoryConfig, MemoryIndexer


def forgetting_weight(memory: MemoryItem) -> float:
    """
    Compute forgetting weight based on Ebbinghaus-style decay.

    Weight is influenced by memory age and access frequency:
    - < 7 days: 1.0 (full retention)
    - 7-30 days: 0.8 * (access_factor / (access_factor + 1))
    - 30-60 days: 0.5 * (access_factor / (access_factor + 2))
    - > 60 days: 0.3 * (access_factor / (access_factor + 3))

    Args:
        memory: MemoryItem to compute weight for.

    Returns:
        Float weight in [0, 1].
    """
    age_days = memory.age_days
    access_factor = math.log(memory.access_count + 1)
    if age_days < 7:
        return 1.0
    elif age_days < 30:
        return 0.8 * (access_factor / (access_factor + 1))
    elif age_days < 60:
        return 0.5 * (access_factor / (access_factor + 2))
    else:
        return 0.3 * (access_factor / (access_factor + 3))


def compress_old_memories(
    store: "JsonMemoryStore",
    config: "MemoryConfig",
) -> int:
    """
    Compress episodic memories older than 60 days by truncating content.

    Args:
        store: JsonMemoryStore instance for persistence.
        config: MemoryConfig controlling compression behavior.

    Returns:
        Number of memories compressed.
    """
    if not config.compress_old_memories:
        return 0
    compressed = 0
    cutoff = datetime.now() - timedelta(days=60)
    try:
        raw_list = store.list_all(MemoryType.EPISODIC)
        for r in raw_list:
            created_str = r.get("created_at", "")
            if not created_str:
                continue
            try:
                created = datetime.fromisoformat(created_str)
            except (ValueError, TypeError):
                continue
            if created < cutoff and not r.get("metadata", {}).get("compressed"):
                content = r.get("finding", "") or r.get("content", "")
                summary = content[:200] + "...[COMPRESSED]"
                r["content"] = summary
                r["finding"] = summary
                r.setdefault("metadata", {})["compressed"] = True
                r["metadata"]["original_length"] = len(content)
                r["metadata"]["compressed_at"] = datetime.now().isoformat()
                mid = r.get("id", "")
                if mid:
                    store.save(MemoryType.EPISODIC, r)
                    compressed += 1
    except (OSError, ValueError, AttributeError):
        pass
    return compressed


def cleanup_expired_memories(
    store: "JsonMemoryStore",
    config: "MemoryConfig",
    indexer: "MemoryIndexer | None" = None,
) -> int:
    """
    Delete memories older than config.retention_days.

    Only EPISODIC and FEEDBACK types are subject to expiry.

    Args:
        store: JsonMemoryStore instance for persistence.
        config: MemoryConfig providing retention_days.
        indexer: Optional MemoryIndexer to keep index in sync.

    Returns:
        Number of memories removed.
    """
    removed = 0
    cutoff = datetime.now() - timedelta(days=config.retention_days)
    for mtype in [MemoryType.EPISODIC, MemoryType.FEEDBACK]:
        try:
            raw_list = store.list_all(mtype)
            for r in raw_list:
                created_str = r.get("created_at", "")
                if not created_str:
                    continue
                try:
                    created = datetime.fromisoformat(created_str)
                except (ValueError, TypeError):
                    continue
                if created < cutoff:
                    mid = r.get("id", "")
                    if mid and store.delete(mtype, mid):
                        removed += 1
                        if indexer:
                            indexer.remove_from_index(mid)
        except (OSError, ValueError, AttributeError):
            continue
    return removed
