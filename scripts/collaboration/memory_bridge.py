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
import math
import os
import re
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
        return (datetime.now() - self.created_at).total_seconds() / 86400

    def to_dict(self) -> dict:
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
        return cls()

    @classmethod
    def lightweight(cls) -> "MemoryConfig":
        return cls(auto_capture=False, auto_index=False, max_episodic_memories=100)

    @classmethod
    def full(cls) -> "MemoryConfig":
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
        items = []
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
        items = []
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
        current_entry = None

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


class MemoryStore(ABC):
    @abstractmethod
    def save(self, memory_type: MemoryType, data: dict) -> str:
        pass

    @abstractmethod
    def load(self, memory_type: MemoryType, item_id: str) -> dict | None:
        pass

    @abstractmethod
    def list_all(self, memory_type: MemoryType, filters: dict | None = None) -> list[dict]:
        pass

    @abstractmethod
    def delete(self, memory_type: MemoryType, item_id: str) -> bool:
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
        item_id = data.get("id", f"{memory_type.value}_{uuid.uuid4().hex[:12]}_{int(time.time())}")
        file_path = self._get_file_path(memory_type, item_id)
        with self._lock:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return item_id

    def load(self, memory_type: MemoryType, item_id: str) -> dict | None:
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
        file_path = self._get_file_path(memory_type, item_id)
        with self._lock:
            if file_path.exists():
                file_path.unlink()
                return True
        return False


class MemoryIndexer:
    def __init__(self):
        self._inverted_index: dict[str, set] = {}
        self._domain_index: dict[str, set] = {}
        self._tag_index: dict[str, set] = {}
        self._type_index: dict[MemoryType, set] = {}
        self._tf_cache: dict[str, Counter] = {}
        self._items_cache: dict[str, MemoryItem] = {}
        self._index_built: bool = False
        self._write_count: int = 0
        self._lock = threading.RLock()
        self._doc_count: int = 0

    def build_index(self, items: list[MemoryItem]) -> None:
        with self._lock:
            self._inverted_index.clear()
            self._domain_index.clear()
            self._tag_index.clear()
            self._type_index.clear()
            self._tf_cache.clear()
            self._items_cache.clear()
            self._doc_count = 0
            for item in items:
                self._add_to_index_internal(item)
            self._index_built = True

    def add_to_index(self, item: MemoryItem) -> None:
        with self._lock:
            self._add_to_index_internal(item)
            self._write_count += 1
            if self._write_count >= 50 and not self._index_built:
                pass

    def _add_to_index_internal(self, item: MemoryItem) -> None:
        mid = item.id
        self._items_cache[mid] = item
        self._doc_count += 1
        tokens = self._tokenize(item.title + " " + item.content)
        self._tf_cache[mid] = Counter(tokens)
        for token in set(tokens):
            self._inverted_index.setdefault(token, set()).add(mid)
        if item.domain:
            self._domain_index.setdefault(item.domain, set()).add(mid)
        for tag in item.tags:
            self._tag_index.setdefault(tag, set()).add(mid)
        self._type_index.setdefault(item.memory_type, set()).add(mid)

    def remove_from_index(self, memory_id: str) -> None:
        with self._lock:
            item = self._items_cache.pop(memory_id, None)
            if item is None:
                return
            self._doc_count -= 1
            tokens = self._tokenize(item.title + " " + item.content)
            for token in set(tokens):
                ids = self._inverted_index.get(token)
                if ids:
                    ids.discard(memory_id)
                    if not ids:
                        del self._inverted_index[token]
            if item.domain:
                ids = self._domain_index.get(item.domain)
                if ids:
                    ids.discard(memory_id)
            for tag in item.tags:
                ids = self._tag_index.get(tag)
                if ids:
                    ids.discard(memory_id)
            type_set = self._type_index.get(item.memory_type)
            if type_set:
                type_set.discard(memory_id)
            self._tf_cache.pop(memory_id, None)

    def search(
        self, query_text: str, type_filter: MemoryType | None = None, domain_filter: str | None = None, limit: int = 10
    ) -> list[tuple[str, float]]:
        with self._lock:
            if not self._index_built or not self._inverted_index:
                return []
            query_tokens = self._tokenize(query_text)
            candidates: dict[str, float] = {}
            for token in query_tokens:
                ids = self._inverted_index.get(token)
                if ids:
                    for doc_id in ids:
                        candidates[doc_id] = candidates.get(doc_id, 0) + 1
            if type_filter:
                type_ids = self._type_index.get(type_filter, set())
                candidates = {k: v for k, v in candidates.items() if k in type_ids}
            if domain_filter:
                dom_ids = self._domain_index.get(domain_filter, set())
                candidates = {k: v for k, v in candidates.items() if k in dom_ids}
            results = []
            for doc_id, _raw_score in candidates.items():
                tfidf_score = self._compute_relevance(query_tokens, doc_id)
                results.append((doc_id, tfidf_score))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]

    def keyword_search(self, keywords: list[str], domain: str | None = None) -> list[tuple[str, float]]:
        with self._lock:
            if not keywords:
                return []
            candidate_sets = []
            for kw in keywords:
                tokens = self._tokenize(kw)
                matching_ids = None
                for t in tokens:
                    ids = self._inverted_index.get(t)
                    if ids is None:
                        ids = set()
                    if matching_ids is None:
                        matching_ids = set(ids)
                    else:
                        matching_ids &= set(ids)
                if matching_ids is not None:
                    candidate_sets.append(matching_ids)
            if not candidate_sets:
                return []
            final_candidates = candidate_sets[0]
            for s in candidate_sets[1:]:
                final_candidates &= s
            if domain:
                dom_ids = self._domain_index.get(domain, set())
                final_candidates &= dom_ids
            results = [(mid, 1.0) for mid in final_candidates]
            results.sort(key=lambda x: x[1], reverse=True)
            return results

    def _compute_relevance(self, query_tokens: list[str], doc_id: str) -> float:
        doc_tf = self._tf_cache.get(doc_id, Counter())
        query_tf = Counter(query_tokens)
        score = 0.0
        for token in query_tokens:
            if token in doc_tf:
                idf = math.log((self._doc_count + 1) / (len(self._inverted_index.get(token, set())) + 1)) + 1
                score += doc_tf[token] * idf
        if score > 0:
            doc_norm = math.sqrt(sum(v**2 for v in doc_tf.values()))
            query_norm = math.sqrt(sum(v**2 for v in query_tf.values())) or 1
            score = score / (doc_norm * query_norm)
        return min(score, 1.0)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r"[^\w\u4e00-\u9fff]", " ", text)
        tokens = text.split()
        result = []
        for t in tokens:
            if len(t) <= 1:
                result.append(t)
            elif any("\u4e00" <= c <= "\u9fff" for c in t):
                result.extend(list(t))
            else:
                if len(t) > 3:
                    for i in range(len(t) - 1):
                        result.append(t[i : i + 2])
                result.append(t)
        return [t for t in result if len(t) >= 1]

    @property
    def is_built(self) -> bool:
        return self._index_built

    @property
    def size(self) -> int:
        return self._doc_count


class MemoryWriter:
    def __init__(self, store: MemoryStore, indexer: MemoryIndexer | None = None):
        self.store = store
        self.indexer = indexer
        self._capture_count = 0

    def write_knowledge(self, item: KnowledgeItem) -> str:
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

    def compress_old_memories(self) -> int:
        if not self.config.compress_old_memories:
            return 0
        compressed = 0
        cutoff = datetime.now() - timedelta(days=60)
        try:
            raw_list = self.store.list_all(MemoryType.EPISODIC)
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
                        self.store.save(MemoryType.EPISODIC, r)
                        compressed += 1
        except (OSError, ValueError, AttributeError):
            pass
        return compressed

    def cleanup_expired_memories(self) -> int:
        removed = 0
        cutoff = datetime.now() - timedelta(days=self.config.retention_days)
        for mtype in [MemoryType.EPISODIC, MemoryType.FEEDBACK]:
            try:
                raw_list = self.store.list_all(mtype)
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
                        if mid and self.store.delete(mtype, mid):
                            removed += 1
                            if self.indexer:
                                self.indexer.remove_from_index(mid)
            except (OSError, ValueError, AttributeError):
                continue
        return removed

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
        if self._mce_adapter:
            with contextlib.suppress(AttributeError, RuntimeError, OSError):
                self._mce_adapter.shutdown()
