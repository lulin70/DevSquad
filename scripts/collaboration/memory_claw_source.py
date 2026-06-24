#!/usr/bin/env python3
"""
WorkBuddyClawSource - WorkBuddy (Claw) 记忆数据源只读桥接

从 /Users/lin/WorkBuddy/Claw/.memory/ 和 .workbuddy/memory/ 目录读取
结构化记忆文件，转换为标准 MemoryItem 列表。

数据映射规则:
  .memory/SOUL.md       -> MemoryType.SEMANTIC (personality matrix)
  .memory/USER.md       -> MemoryType.KNOWLEDGE (user profile)
  .memory/MEMORY.md     -> MemoryType.KNOWLEDGE (core knowledge)
  .memory/INDEX.md      -> used for retrieval acceleration (not returned directly)
  .memory/PROMPT.md     -> MemoryType.PATTERN (prompt optimization rules)
  .memory/EXP.md        -> MemoryType.EPISODIC (experience system)

设计约束:
  - Read-only access, never writes to Claw directory
  - Path hardcoded to /Users/lin/WorkBuddy/Claw (overridable via constructor)
  - Caches INDEX.md parsing results to avoid repeated IO
  - All exceptions caught internally, never affects main flow

从 memory_bridge.py 拆分而来，保持向后兼容的 re-export。
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .memory_types import MemoryItem, MemoryType


class WorkBuddyClawSource:
    """
    Read-only bridge for WorkBuddy (Claw) memory data source.

    Reads structured memory files from /Users/lin/WorkBuddy/Claw/.memory/
    and .workbuddy/memory/ directories, converting them into standard
    MemoryItem lists.

    Data mapping rules:
      .memory/SOUL.md       -> MemoryType.SEMANTIC (personality matrix)
      .memory/USER.md       -> MemoryType.KNOWLEDGE (user profile)
      .memory/MEMORY.md     -> MemoryType.KNOWLEDGE (core knowledge)
      .memory/INDEX.md      -> used for retrieval acceleration (not returned directly)
      .memory/PROMPT.md     -> MemoryType.PATTERN (prompt optimization rules)
      .memory/EXP.md        -> MemoryType.EPISODIC (experience system)

    Design constraints:
      - Read-only access, never writes to Claw directory
      - Path hardcoded to /Users/lin/WorkBuddy/Claw (overridable via constructor)
      - Caches INDEX.md parsing results to avoid repeated IO
      - All exceptions caught internally, never affects main flow
    """

    CLAW_BASE_PATH = os.environ.get("WORKBUDDY_CLAW_PATH", "/Users/lin/WorkBuddy/Claw")
    MEMORY_DIR = ".memory"
    WORKBUDDY_MEMORY_DIR = ".workbuddy/memory"

    CORE_FILE_MAPPING = {
        "SOUL.md": ("AI Personality Matrix (OCEAN model)", MemoryType.SEMANTIC),
        "USER.md": ("User Profile (background/preferences/channels)", MemoryType.KNOWLEDGE),
        "MEMORY.md": ("Core Knowledge Base (lessons/decisions)", MemoryType.KNOWLEDGE),
        "EXP.md": ("Experience System", MemoryType.EPISODIC),
        "PROMPT.md": ("Prompt Optimization Rules", MemoryType.PATTERN),
        "HEALTH.md": ("Health Monitoring Status", MemoryType.SEMANTIC),
    }

    def __init__(self, base_path: str | None = None):
        """
        Initialize the Claw source with optional custom base path.

        Args:
            base_path: Custom path to Claw directory. Defaults to CLAW_BASE_PATH.
        """
        self.base_path = Path(base_path or self.CLAW_BASE_PATH)
        self._memory_dir = self.base_path / self.MEMORY_DIR
        self._wb_memory_dir = self.base_path / self.WORKBUDDY_MEMORY_DIR
        self._index_cache: dict[str, list[str]] | None = None

    @property
    def is_available(self) -> bool:
        """Check if the Claw directory exists and is accessible."""
        return self.base_path.exists() and self._memory_dir.exists()

    def load_all_memories(self) -> list[MemoryItem]:
        """
        Load all available memories from Claw directories.

        Returns:
            List[MemoryItem]: Combined list of core + daily memories,
            each tagged with source='workbuddy-claw'.
        """
        items: list[MemoryItem] = []
        if not self.is_available:
            return items
        items.extend(self._load_core_memories())
        items.extend(self._load_workbuddy_daily_memories())
        for item in items:
            item.source = "workbuddy-claw"
        return items

    def _load_core_memories(self) -> list[MemoryItem]:
        """Load core memory files from .memory/ directory."""
        items = []
        for filename, (title, mtype) in self.CORE_FILE_MAPPING.items():
            filepath = self._memory_dir / filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                items.append(
                    MemoryItem(
                        id=f"wb-core-{filename.replace('.md', '')}",
                        memory_type=mtype,
                        title=title,
                        content=content,
                        domain="user-profile" if "USER" in filename else "claw-core",
                        tags=self._extract_tags(content),
                        source="workbuddy-claw",
                    )
                )
        return items

    def _load_workbuddy_daily_memories(self) -> list[MemoryItem]:
        """Load daily work memories from .workbuddy/memory/ directory."""
        items: list[MemoryItem] = []
        if not self._wb_memory_dir.exists():
            return items

        md_files = sorted(
            self._wb_memory_dir.glob("2026-*.md"),
            key=lambda p: p.name,
            reverse=True,
        )
        for filepath in md_files[:30]:
            date_str = filepath.stem
            content = filepath.read_text(encoding="utf-8")
            items.append(
                MemoryItem(
                    id=f"wb-daily-{date_str}",
                    memory_type=MemoryType.EPISODIC,
                    title=f"Work Log {date_str}",
                    content=content,
                    domain="daily-log",
                    tags=["workbuddy", "daily", date_str] + self._extract_tags(content),
                    source="workbuddy-claw",
                )
            )
        return items

    def search_by_index(self, query: str, limit: int = 5) -> list[MemoryItem]:
        """
        Fast search using Claw INDEX.md keyword inverted index.

        INDEX.md format example:
          | Keyword | Location |
          | Fudan/Education | USER.md#Background |
          | QQ/WeChat | USER.md#Channels |

        Performance:
          - Index hit: O(1) lookup + 1 file read
          - Index miss: fallback to full-text scan

        Args:
            query: Search query string.
            limit: Maximum number of results to return.

        Returns:
            List[MemoryItem]: Matched memories sorted by relevance.
        """
        index_path = self._memory_dir / "INDEX.md"
        if not index_path.exists():
            return self._fallback_search(query, limit)

        if self._index_cache is None:
            self._index_cache = self._parse_index(index_path)

        query_tokens = set(query.lower().split())
        matched_files = set()
        for token in query_tokens:
            if token in self._index_cache:
                for entry in self._index_cache[token]:
                    matched_files.add(entry)

        results = []
        for file_ref in list(matched_files)[:limit]:
            item = self._load_memory_by_index_ref(file_ref)
            if item:
                results.append(item)
        return results

    def _parse_index(self, index_path: Path) -> dict[str, list[str]]:
        """
        Parse INDEX.md table into {keyword: [file_ref]} dictionary.

        Args:
            index_path: Path to INDEX.md file.

        Returns:
            Dict mapping lowercase keywords to lists of file references.
        """
        result: dict[str, list[str]] = {}
        lines = index_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("|---"):
                continue
            if line.startswith("|"):
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2 and parts[0] and parts[0] != "\u5173\u952e\u8bcd":
                    keywords = parts[0]
                    file_ref = parts[1] if len(parts) > 1 else ""
                    if file_ref and file_ref != "\u4f4d\u7f6e":
                        for kw in keywords.split("/"):
                            kw = kw.strip().lower()
                            if kw:
                                result.setdefault(kw, []).append(file_ref)
        return result

    def _load_memory_by_index_ref(self, ref: str) -> MemoryItem | None:
        """
        Load a memory fragment based on an INDEX reference.

        Supports both 'filename.md' and 'filename.md#section' formats.

        Args:
            ref: File reference from INDEX.md (e.g., USER.md#Background).

        Returns:
            MemoryItem for the referenced content, or None if not found.
        """
        if "#" in ref:
            filename, section = ref.split("#", 1)
        else:
            filename, section = ref, None

        filepath = self._memory_dir / filename
        if not filepath.exists():
            return None

        content = filepath.read_text(encoding="utf-8")
        if section:
            extracted = self._extract_section(content, section)
            content = extracted if extracted is not None else content[:500]

        type_map = {
            "SOUL": MemoryType.SEMANTIC,
            "USER": MemoryType.KNOWLEDGE,
            "MEMORY": MemoryType.KNOWLEDGE,
            "EXP": MemoryType.EPISODIC,
            "PROMPT": MemoryType.PATTERN,
        }
        mtype = next((t for k, t in type_map.items() if k in filename.upper()), MemoryType.KNOWLEDGE)

        return MemoryItem(
            id=f"wb-index-{filename.replace('.md', '').replace('/', '-')}",
            memory_type=mtype,
            title=f"[Claw] {ref}",
            content=content,
            source="workbuddy-claw",
            relevance_score=0.9,
        )

    @staticmethod
    def _extract_section(content: str, anchor: str) -> str | None:
        """
        Extract a markdown section by its heading anchor text.

        Args:
            content: Full markdown text to search in.
            anchor: Section heading text to find.

        Returns:
            Extracted section text, or None if anchor not found.
        """
        pattern = rf"(?:^|\n)#+\s*.*{re.escape(anchor)}"
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        if not match:
            return None
        start = match.start()
        next_heading = re.search(r"\n#+\s+", content[start + 1 :])
        end = (next_heading.start() + start + 1) if next_heading else len(content)
        return content[start:end].strip()

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        """
        Extract meaningful words as tags from text content.

        Extracts Chinese words (>=2 chars) and English words (>=3 chars).

        Args:
            text: Source text to extract tags from.

        Returns:
            List of unique tag strings (max 15).
        """
        words = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", text)
        return list(set(words))[:15]

    def _fallback_search(self, query: str, limit: int = 5) -> list[MemoryItem]:
        """
        Fallback full-text search when INDEX.md is unavailable.

        Scores results by title match (+0.5), content match (+0.3),
        and tag overlap (+0.2).

        Args:
            query: Search query string.
            limit: Maximum results.

        Returns:
            Scored and ranked MemoryItem list.
        """
        all_items = self.load_all_memories()
        query_lower = query.lower()
        scored = []
        for item in all_items:
            score = 0.0
            if query_lower in item.title.lower():
                score += 0.5
            if query_lower in item.content.lower():
                score += 0.3
            if any(q in t.lower() for q in query_lower.split() for t in item.tags):
                score += 0.2
            if score > 0:
                item.relevance_score = min(score, 1.0)
                scored.append(item)
        scored.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored[:limit]

    # ========== Plan B: Automation News Feed Consumer ==========

    def get_latest_ai_news(self, days: int = 7) -> list[MemoryItem]:
        """
        Read daily AI news automation task execution records.

        Data source: .codebuddy/automations/ai/memory.md
        Returns: Recent N days of news entries, each date block as a MemoryItem.

        Each MemoryItem.metadata contains:
          - sources: List of information sources
          - topics: List of core topics
          - status: Execution status string

        Args:
            days: Number of days to look back (default 7).

        Returns:
            List of MemoryItems representing AI news entries.
        """
        ai_memory_path = self.base_path / ".codebuddy" / "automations" / "ai" / "memory.md"
        if not ai_memory_path.exists():
            return []

        content = ai_memory_path.read_text(encoding="utf-8")
        entries = self._parse_automation_log(content)

        items = []
        cutoff = datetime.now() - timedelta(days=days)
        for entry in entries:
            if entry["date"] >= cutoff:
                items.append(
                    MemoryItem(
                        id=f"wb-news-{entry['date'].strftime('%Y%m%d')}",
                        memory_type=MemoryType.EPISODIC,
                        title=f"AI News {entry['date'].strftime('%Y-%m-%d')}",
                        content=entry["content"],
                        domain="ai-news",
                        tags=["ai-news", "daily-push", "automation"] + self._extract_tags(entry["content"]),
                        source="workbuddy-claw-automation",
                        metadata={
                            "sources": entry.get("sources", []),
                            "core_topics": entry.get("topics", []),
                            "status": entry.get("status", ""),
                        },
                    )
                )
        return items

    def _parse_automation_log(self, content: str) -> list[dict]:
        """
        Parse automation memory.md log format into structured entries.

        Input format:
          ## YYYY-MM-DD HH:MM
          **Status**: Success
          **Sources**: source1, source2
          **Push Count**: N
          **Core Topics**:
          - topic1
          - topic2
          **Notes**: additional notes

        Output:
          [{date: datetime, content: str, sources: [], topics: [], status: str}, ...]

        Args:
            content: Raw markdown content from automation memory.md.

        Returns:
            List of parsed entry dictionaries.
        """
        entries = []
        date_pattern = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
        current_entry: dict[str, Any] | None = None

        for line in content.splitlines():
            date_match = date_pattern.match(line)
            if date_match:
                if current_entry:
                    entries.append(current_entry)
                try:
                    current_entry = {
                        "date": datetime.strptime(date_match.group(1), "%Y-%m-%d"),
                        "content": "",
                        "sources": [],
                        "topics": [],
                        "status": "",
                    }
                except ValueError:
                    continue
            elif current_entry is not None:
                current_entry["content"] += line + "\n"

                src_match = re.match(r"\*\*\u4fe1\u606f\u6765\u6e90\*\*:\s*(.+)", line)
                if src_match:
                    current_entry["sources"].append(src_match.group(1))

                topics_match = re.match(r"\*\*\u6838\u5fc3\u4e3b\u9898\*\*:\s*(.+)", line)
                if topics_match:
                    current_entry["topics"].append(topics_match.group(1))

                status_match = re.match(r"\*\*\u6267\u884c\u72b6\u6001\*\*:\s*(\S+)", line)
                if status_match:
                    current_entry["status"] = status_match.group(1)

        if current_entry:
            entries.append(current_entry)

        return entries
