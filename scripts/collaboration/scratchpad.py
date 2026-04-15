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
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import OrderedDict

from .models import (
    ScratchpadEntry,
    EntryType,
    EntryStatus,
    ReferenceType,
    Reference,
)


MAX_ENTRIES_DEFAULT = 1000


class Scratchpad:
    def __init__(self, scratchpad_id: Optional[str] = None, persist_dir: Optional[str] = None):
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
        with self._lock:
            if len(self._entries) >= self._max_entries:
                self._evict_oldest(count=len(self._entries) - self._max_entries + 1)

            existing = self._entries.get(entry.entry_id)
            if existing and existing.version >= entry.version:
                entry.version = existing.version + 1

            self._entries[entry.entry_id] = entry
            self._write_count += 1
            self._persist_entry(entry)
            return entry.entry_id

    def read(self, query: str = "", since: Optional[datetime] = None,
             entry_type: Optional[EntryType] = None,
             status: Optional[EntryStatus] = None,
             worker_id: Optional[str] = None,
             tags: Optional[List[str]] = None,
             limit: int = 50) -> List[ScratchpadEntry]:
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
            return list(reversed(results))

    def resolve(self, entry_id: str, resolution: str = ""):
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.status = EntryStatus.RESOLVED
                if resolution:
                    entry.content = f"{entry.content}\n\n[RESOLVED] {resolution}"
                entry.version += 1
                self._persist_entry(entry)

    def get_conflicts(self) -> List[ScratchpadEntry]:
        return self.read(
            entry_type=EntryType.CONFLICT,
            status=EntryStatus.ACTIVE,
        )

    def get_summary(self, for_role: Optional[str] = None,
                     max_entries: int = 20) -> str:
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
            pass

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
            pass

    def clear(self):
        with self._lock:
            self._entries.clear()

    def export_json(self) -> str:
        with self._lock:
            entries = [e.to_dict() for e in self._entries.values()]
            return json.dumps(entries, ensure_ascii=False, indent=2)


MAX_ENTRIES_DEFAULT = 1000
