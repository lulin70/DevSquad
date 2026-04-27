#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scratchpad - 共享黑板实现

设计决策（门禁1解决）：
- 并发写入策略：时间戳排序 + 版本号 + 最后写入胜出（LWW）
- 对于发现类数据（FINDING/QUESTION），覆盖是可接受的
- 对于决策类数据（DECISION），需要 Consensus 机制保护
- 容量上限：默认 1000 条，LRU 淘汰最旧的非 RESOLVED 条目
- 存储选型（门禁3）：内存主存储 + JSON 文件持久化备份
"""

import os
import json
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import OrderedDict

logger = logging.getLogger(__name__)

from .models import (
    ScratchpadEntry,
    EntryType,
    EntryStatus,
    ReferenceType,
    Reference,
)
from .usage_tracker import track_usage


MAX_ENTRIES_DEFAULT = 1000


class Scratchpad:
    """
    共享黑板 - 多 Worker 协作的信息交换中心

    所有 Worker 通过 Scratchpad 共享发现、决策、问题和冲突。
    采用 LWW (Last-Writer-Wins) 并发策略 + 版本号机制处理并发写入。

    核心能力:
    - write(): 写入条目（自动版本递增、容量管理、持久化）
    - read(): 多维查询（关键词/类型/状态/Worker/标签/时间）
    - resolve(): 标记冲突/问题为已解决
    - get_summary(): 生成 Markdown 格式的全局摘要

    设计特点:
    - 容量上限: 默认 1000 条，LRU 淘汰最旧的非 RESOLVED 条目
    - 持久化: JSONL 追加写模式，支持断点恢复
    - 线程安全: RLock 保护所有读写操作

    使用示例:
        sp = Scratchpad(persist_dir="/tmp/sp_data")
        entry = ScratchpadEntry(worker_id="w1", role_id="architect",
                                entry_type=EntryType.FINDING,
                                content="建议使用微服务架构")
        sp.write(entry)
        findings = sp.read(entry_type=EntryType.FINDING)
    """

    def __init__(self, scratchpad_id: Optional[str] = None, persist_dir: Optional[str] = None):
        """
        初始化共享黑板

        Args:
            scratchpad_id: 黑板唯一标识（自动生成时间戳ID如未提供）
            persist_dir: 持久化目录路径（为空则不持久化，纯内存模式）
        """
        self.scratchpad_id = scratchpad_id or f"scratchpad-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.persist_dir = persist_dir

        self._entries: OrderedDict[str, ScratchpadEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._max_entries: int = MAX_ENTRIES_DEFAULT
        self._write_count: int = 0
        self._read_count: int = 0

        if self.persist_dir:
            os.makedirs(self.persist_dir, exist_ok=True)
            self._load_from_disk()

    def write(self, entry: ScratchpadEntry) -> str:
        """
        [MCE 集成点 Phase C] Worker 写入共享黑板

        当前行为: 直接存储原始 ScratchpadEntry (type/content/confidence)
        MCE 就绪后: 每个 entry 写入前经过 MCE 分类标注
            → [decision] "我们决定用微服务架构"
            → [correction] "数据库从Mongo改为PostgreSQL"
            → [user_pref] "团队习惯TDD开发模式"
            → [relationship] "Alice负责后端API"
        后续 Worker 读取时看到带类型的结构化发现，而非纯文本

        接口预留: mce_engine 参数, enable_mce_annotate: bool
        """
        with self._lock:
            if len(self._entries) >= self._max_entries:
                self._evict_oldest(count=len(self._entries) - self._max_entries + 1)

            existing = self._entries.get(entry.entry_id)
            if existing and existing.version >= entry.version:
                entry.version = existing.version + 1

            self._entries[entry.entry_id] = entry
            self._write_count += 1
            self._persist_entry(entry)
            track_usage("scratchpad.write", success=True, metadata={
                "entry_type": entry.entry_type.value
            })
            return entry.entry_id

    def read(self, query: str = "", since: Optional[datetime] = None,
             entry_type: Optional[EntryType] = None,
             status: Optional[EntryStatus] = None,
             worker_id: Optional[str] = None,
             tags: Optional[List[str]] = None,
             limit: int = 50) -> List[ScratchpadEntry]:
        """
        多维查询黑板条目

        支持按关键词、时间、类型、状态、Worker、标签等多维度组合过滤。
        返回结果按时间倒序（最新的在前）。

        Args:
            query: 关键词模糊匹配（在 content 和 tags 中搜索）
            since: 起始时间（只返回此之后的条目）
            entry_type: 按条目类型过滤 (FINDING/QUESTION/DECISION/CONFLICT)
            status: 按状态过滤 (ACTIVE/RESOLVED)
            worker_id: 按 Worker ID 过滤
            tags: 标签列表（任一匹配即返回）
            limit: 最大返回条数

        Returns:
            List[ScratchpadEntry]: 匹配的条目列表（时间倒序）
        """
        with self._lock:
            results = []
            for entry in reversed(self._entries.values()):
                if since and entry.timestamp < since:
                    continue
                if entry_type and entry.entry_type != entry_type:
                    continue
                if status and entry.status != status:
                    continue
                if worker_id and entry.worker_id != worker_id:
                    continue
                if tags and not any(t in entry.tags for t in tags):
                    continue
                if query:
                    q_lower = query.lower()
                    if (q_lower not in entry.content.lower() and
                        not any(q_lower in t.lower() for t in entry.tags)):
                        continue
                results.append(entry)
                if len(results) >= limit:
                    break
            self._read_count += 1
            track_usage("scratchpad.read", success=True, metadata={
                "results_count": len(results),
                "has_query": bool(query)
            })
            return list(reversed(results))

    def resolve(self, entry_id: str, resolution: str = ""):
        """
        将条目标记为已解决

        修改条目状态为 RESOLVED，并可选地附加解决方案说明。
        解决方案会追加到原内容末尾。

        Args:
            entry_id: 要解决的条目 ID
            resolution: 解决方案描述（追加到原内容后）
        """
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.status = EntryStatus.RESOLVED
                if resolution:
                    entry.content = f"{entry.content}\n\n[RESOLVED] {resolution}"
                entry.version += 1
                self._persist_entry(entry)

    def get_conflicts(self) -> List[ScratchpadEntry]:
        """
        获取所有活跃冲突

        快捷方法，等价于 read(entry_type=CONFLICT, status=ACTIVE)

        Returns:
            List[ScratchpadEntry]: 当前未解决的冲突列表
        """
        return self.read(
            entry_type=EntryType.CONFLICT,
            status=EntryStatus.ACTIVE,
        )

    def get_summary(self, for_role: Optional[str] = None,
                     max_entries: int = 20) -> str:
        """
        生成黑板全局摘要（Markdown格式）

        包含: 总览统计、活跃冲突列表、最近决策、关键发现。

        Args:
            for_role: 为指定角色定制摘要（预留参数）
            max_entries: 各类别的最大展示条数

        Returns:
            str: Markdown 格式的摘要文本
        """
        active_findings = self.read(
            entry_type=EntryType.FINDING,
            status=EntryStatus.ACTIVE,
            limit=max_entries,
        )
        decisions = self.read(
            entry_type=EntryType.DECISION,
            status=EntryStatus.ACTIVE,
            limit=max_entries // 2,
        )
        conflicts = self.get_conflicts()

        lines = [f"# Scratchpad Summary ({self.scratchpad_id})"]
        lines.append(f"**Total entries**: {len(self._entries)} | **Active findings**: {len(active_findings)} | **Conflicts**: {len(conflicts)}")
        lines.append("")

        if conflicts:
            lines.append(f"## ⚠️ Active Conflicts ({len(conflicts)})")
            for c in conflicts[:5]:
                role_tag = f"[{c.role_id}]"
                conf_str = f"- {role_tag} {c.content[:100]}"
                lines.append(conf_str)
            lines.append("")

        if decisions:
            lines.append(f"## ✅ Recent Decisions ({len(decisions)})")
            for d in decisions[:10]:
                role_tag = f"[{d.role_id}]"
                dec_str = f"- {role_tag} {d.content[:120]} (confidence: {d.confidence:.0%})"
                lines.append(dec_str)
            lines.append("")

        if active_findings:
            lines.append(f"## 🔍 Key Findings ({len(active_findings)})")
            for f in active_findings[:15]:
                role_tag = f"[{f.worker_id}/{f.role_id}]"
                find_str = f"- {role_tag} {f.content[:120]} (confidence: {f.confidence:.0%})"
                lines.append(find_str)

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取黑板详细统计信息

        Returns:
            Dict[str, Any]: 统计字典，包含:
                - scratchpad_id: 黑板标识
                - total_entries: 总条目数
                - by_type: 按类型分布
                - by_status: 按状态分布
                - by_worker: 按 Worker 分布
                - write_count/read_count: 读写计数
                - max_entries: 容量上限
        """
        with self._lock:
            by_type = {}
            by_status = {}
            by_worker = {}
            for e in self._entries.values():
                by_type[e.entry_type.value] = by_type.get(e.entry_type.value, 0) + 1
                by_status[e.status.value] = by_status.get(e.status.value, 0) + 1
                by_worker[e.worker_id] = by_worker.get(e.worker_id, 0) + 1
            return {
                "scratchpad_id": self.scratchpad_id,
                "total_entries": len(self._entries),
                "by_type": by_type,
                "by_status": by_status,
                "by_worker": by_worker,
                "write_count": self._write_count,
                "read_count": self._read_count,
                "max_entries": self._max_entries,
            }

    def _evict_oldest(self, count: int = 1):
        to_evict = []
        for eid, entry in self._entries.items():
            if entry.status == EntryStatus.RESOLVED:
                to_evict.append((eid, entry.timestamp))
                if len(to_evict) >= count:
                    break
        if not to_evict:
            to_evict = [(eid, e.timestamp) for eid, e in list(self._entries.items())[:count]]
        to_evict.sort(key=lambda x: x[1])
        for eid, _ in to_evict:
            del self._entries[eid]

    def _persist_entry(self, entry: ScratchpadEntry):
        if not self.persist_dir:
            return
        filepath = os.path.join(self.persist_dir, f"{self.scratchpad_id}.jsonl")
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to persist scratchpad entry %s: %s", entry.entry_id, e)

    def _load_from_disk(self):
        if not self.persist_dir:
            return
        filepath = os.path.join(self.persist_dir, f"{self.scratchpad_id}.jsonl")
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    entry = ScratchpadEntry.from_dict(data)
                    self._entries[entry.entry_id] = entry
        except Exception as e:
            logger.warning("Failed to load scratchpad from %s: %s", filepath, e)

    def clear(self):
        """清空所有黑板条目（仅内存，不影响已持久化的文件）"""
        with self._lock:
            self._entries.clear()

    def export_json(self) -> str:
        """
        导出所有条目为 JSON 字符串

        Returns:
            str: JSON 格式的完整数据快照
        """
        with self._lock:
            entries = [e.to_dict() for e in self._entries.values()]
            return json.dumps(entries, ensure_ascii=False, indent=2)


MAX_ENTRIES_DEFAULT = 1000
