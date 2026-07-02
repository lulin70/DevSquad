#!/usr/bin/env python3
"""
ContextCompressor - 3-Level Context Compression Strategy

Based on Claude Code's context management approach:
  Level 1: SNIP - Fine-grained pruning of old conversation segments
  Level 2: SessionMemory - Extract key info to structured memory, clear window
  Level 3: FullCompact - LLM-style summary generation (simulated)

Trigger thresholds:
  < 60K tokens  → No compression
  60K - 80K     → Level 1 SNIP
  80K - 100K    → Level 2 SessionMemory
  > 100K        → Level 3 FullCompact
"""

from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from .content_crusher import ContentRouter, SmartCrusher

if TYPE_CHECKING:
    from .ccr_store import CCRStore


class CompressionLevel(Enum):
    NONE = 0
    SNIP = 1
    SESSION_MEMORY = 2
    FULL_COMPACT = 3
    SMART = 4  # V3.10.0: structure-aware via ContentRouter + SmartCrusher


class MessageType(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class MemoryCategory(Enum):
    DECISION = "decision"
    FINDING = "finding"
    DELIVERABLE = "deliverable"
    TODO = "todo"
    ERROR = "error"
    CONSTRAINT = "constraint"
    QUESTION = "question"


@dataclass
class Message:
    message_id: str = field(default_factory=lambda: f"msg-{hashlib.md5(str(datetime.now()).encode(), usedforsecurity=False).hexdigest()[:12]}")
    role: str = "user"
    content: str = ""
    msg_type: MessageType = MessageType.USER
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0
    importance_score: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize the message to a dictionary.

        Returns:
            Dictionary with all message fields, including ISO-formatted timestamp.
        """
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "msg_type": self.msg_type.value,
            "timestamp": self.timestamp.isoformat(),
            "token_count": self.token_count,
            "importance_score": self.importance_score,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Message:
        """Reconstruct a Message from a dictionary.

        Args:
            d: Dictionary produced by to_dict().

        Returns:
            A new Message instance with fields populated from the dictionary.
        """
        ts = d.get("timestamp")
        return cls(
            message_id=d.get("message_id", ""),
            role=d.get("role", "user"),
            content=d.get("content", ""),
            msg_type=MessageType(d.get("msg_type", "user")),
            timestamp=datetime.fromisoformat(ts) if ts else datetime.now(),
            token_count=d.get("token_count", 0),
            importance_score=d.get("importance_score", 0.5),
            metadata=d.get("metadata", {}),
        )


@dataclass
class MemoryEntry:
    entry_id: str = field(default_factory=lambda: f"mem-{hashlib.md5(str(datetime.now()).encode(), usedforsecurity=False).hexdigest()[:12]}")
    category: MemoryCategory = MemoryCategory.FINDING
    content: str = ""
    source_message_ids: list[str] = field(default_factory=list)
    confidence: float = 0.8
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Serialize the memory entry to a dictionary.

        Returns:
            Dictionary with all entry fields, including ISO-formatted timestamps.
        """
        return {
            "entry_id": self.entry_id,
            "category": self.category.value,
            "content": self.content,
            "source_message_ids": self.source_message_ids,
            "confidence": self.confidence,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> MemoryEntry:
        """Reconstruct a MemoryEntry from a dictionary.

        Args:
            d: Dictionary produced by to_dict().

        Returns:
            A new MemoryEntry instance with fields populated from the dictionary.
        """
        ca = d.get("created_at")
        la = d.get("last_accessed")
        return cls(
            entry_id=d.get("entry_id", ""),
            category=MemoryCategory(d.get("category", "finding")),
            content=d.get("content", ""),
            source_message_ids=d.get("source_message_ids", []),
            confidence=d.get("confidence", 0.8),
            tags=d.get("tags", []),
            created_at=datetime.fromisoformat(ca) if ca else datetime.now(),
            last_accessed=datetime.fromisoformat(la) if la else datetime.now(),
        )


@dataclass
class CompressedContext:
    original_token_count: int = 0
    compressed_token_count: int = 0
    compression_level: CompressionLevel = CompressionLevel.NONE
    messages: list[Message] = field(default_factory=list)
    session_memory: list[MemoryEntry] = field(default_factory=list)
    summary: str = ""
    compression_ratio: float = 0.0
    compressed_at: datetime = field(default_factory=datetime.now)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def reduction_percent(self) -> float:
        """Compute the percentage of tokens removed by compression.

        Returns:
            Reduction percentage between 0 and 100; 0.0 when the original
            token count is zero.
        """
        if self.original_token_count == 0:
            return 0.0
        return (1.0 - self.compressed_token_count / self.original_token_count) * 100


# Token estimation: ~4 chars per token for English, ~1.5 for Chinese mixed
_TOKEN_CHARS_RATIO = {
    "default": 4.0,
    "chinese": 1.5,
}

# Importance keywords that boost score
_HIGH_IMPORTANCE_KEYWORDS = [
    "决定",
    "结论",
    "方案",
    "架构",
    "设计",
    "关键",
    "decision",
    "conclusion",
    "architecture",
    "design",
    "critical",
    "错误",
    "修复",
    "问题",
    "bug",
    "error",
    "fix",
    "issue",
    "必须",
    "要求",
    "验收",
    "标准",
    "must",
    "requirement",
    "acceptance",
    "TODO",
    "待办",
    "下一步",
    "action item",
    "next step",
]

_LOW_IMPORTANCE_PATTERNS = [
    r"^(好的|OK|明白|了解|收到|嗯|哦|啊|哈|呵呵)",
    r"^((是的|对|没错|正确|确实|确实如此)[，。！？]?)$",
    r"^((谢谢|感谢|多谢|辛苦了|好的吧|行吧)[，。！？])?$",
]


class ContextCompressor:
    """3-Level Context Compressor"""

    DEFAULT_THRESHOLDS = {
        CompressionLevel.SNIP: 60000,
        CompressionLevel.SESSION_MEMORY: 80000,
        CompressionLevel.FULL_COMPACT: 100000,
    }

    def __init__(
        self,
        token_threshold: int = 100000,
        thresholds: dict[CompressionLevel, int] | None = None,
        ccr_store: CCRStore | None = None,
    ):
        self.token_threshold = token_threshold
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self._session_memory: list[MemoryEntry] = []
        self._compression_log: list[dict] = []
        self._lock = threading.RLock()
        self._crusher = SmartCrusher(ccr_store=ccr_store)
        self._router = ContentRouter()
        self._ccr_store = ccr_store

    def estimate_tokens(self, text: str) -> int:
        """Estimate the token count for a piece of text.

        Uses separate char-to-token ratios for Chinese characters and other
        text to better approximate tokenizer behavior on mixed-language input.

        Args:
            text: Input text to estimate.

        Returns:
            Estimated number of tokens; 0 for empty input.
        """
        if not text:
            return 0
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        other_chars = len(text) - chinese_chars
        chinese_tokens = int(chinese_chars / _TOKEN_CHARS_RATIO["chinese"])
        other_tokens = int(other_chars / _TOKEN_CHARS_RATIO["default"])
        return chinese_tokens + other_tokens

    def estimate_messages_tokens(self, messages: list[Message]) -> int:
        """Estimate the total token count across a list of messages.

        Args:
            messages: List of Message objects (or objects with content/token_count).

        Returns:
            Sum of token estimates for all messages.
        """
        total = 0
        for m in messages:
            if hasattr(m, "token_count") and getattr(m, "token_count", 0) > 0:
                total += m.token_count
            elif hasattr(m, "content"):
                est = self.estimate_tokens(m.content)
                m.token_count = est
                total += est
            else:
                total += self.estimate_tokens(str(m))
        return total

    def check_and_compress(
        self, messages: list[Message], force_level: CompressionLevel | None = None
    ) -> CompressedContext:
        """Compress the message list when its token count exceeds thresholds.

        Args:
            messages: List of Message objects to compress.
            force_level: Optional compression level to apply regardless of
                token count. When None, the level is chosen from thresholds.

        Returns:
            CompressedContext containing the (possibly compressed) messages,
            session memory, summary, and statistics.
        """
        with self._lock:
            total_tokens = self.estimate_messages_tokens(messages)

            if force_level is not None:
                level = force_level
            elif total_tokens >= self.thresholds.get(CompressionLevel.FULL_COMPACT, 100000):
                level = CompressionLevel.FULL_COMPACT
            elif total_tokens >= self.thresholds.get(CompressionLevel.SESSION_MEMORY, 80000):
                level = CompressionLevel.SESSION_MEMORY
            elif total_tokens >= self.thresholds.get(CompressionLevel.SNIP, 60000):
                level = CompressionLevel.SNIP
            else:
                level = CompressionLevel.NONE

            result = CompressedContext(
                original_token_count=total_tokens,
                compression_level=level,
            )

            if level == CompressionLevel.NONE:
                result.messages = list(messages)
                result.compressed_token_count = total_tokens
                result.stats["reason"] = "under_threshold"
            elif level == CompressionLevel.SNIP:
                result = self._level1_snip(messages, result)
            elif level == CompressionLevel.SESSION_MEMORY:
                result = self._level2_session_memory(messages, result)
            elif level == CompressionLevel.FULL_COMPACT:
                result = self._level3_full_compact(messages, result)
            elif level == CompressionLevel.SMART:
                result = self._level4_smart(messages, result)

            result.session_memory = list(self._session_memory)
            result.stats["original_message_count"] = len(messages)
            result.stats["remaining_message_count"] = len(result.messages)
            result.stats["memory_entries"] = len(result.session_memory)

            self._log_compression(result)
            return result

    def _score_importance(self, message: Message) -> float:
        score = 0.5
        content_lower = message.content.lower()

        for kw in _HIGH_IMPORTANCE_KEYWORDS:
            if kw in content_lower:
                score += 0.15
            if kw in message.content:
                score += 0.10

        for pattern in _LOW_IMPORTANCE_PATTERNS:
            if re.match(pattern, message.content.strip()):
                score -= 0.30

        if message.msg_type == MessageType.SYSTEM:
            score += 0.20
        elif message.msg_type == MessageType.ASSISTANT:
            lines = message.content.strip().split("\n")
            if len(lines) <= 2:
                score -= 0.10
            else:
                has_structure = any(c in message.content for c in ["#", "*", "-", "1.", "2."])
                if has_structure:
                    score += 0.15

        if message.metadata.get("is_error") or message.metadata.get("error"):
            score += 0.20
        if message.metadata.get("is_decision"):
            score += 0.25
        if message.metadata.get("is_deliverable"):
            score += 0.20

        return max(0.0, min(1.0, score))

    def _level1_snip(self, messages: list[Message], ctx: CompressedContext) -> CompressedContext:
        scored = [(m, self._score_importance(m)) for m in messages]
        scored.sort(key=lambda x: x[1], reverse=True)

        target_ratio = 0.65
        total_tokens = sum(m.token_count or self.estimate_tokens(m.content) for m, _ in scored)
        keep_budget = int(total_tokens * target_ratio)

        kept = []
        kept_tokens = 0
        snipped = []
        snipped_tokens = 0

        for msg, score in scored:
            tokens = msg.token_count or self.estimate_tokens(msg.content)
            if kept_tokens + tokens <= keep_budget or score >= 0.6:
                kept.append(msg)
                kept_tokens += tokens
            else:
                snipped.append(msg)
                snipped_tokens += tokens

                mem_entry = self._extract_memory_from_message(msg)
                if mem_entry:
                    self._session_memory.append(mem_entry)

        ctx.messages = kept
        ctx.compressed_token_count = kept_tokens
        ctx.summary = f"SNIP: Kept {len(kept)}/{len(messages)} msgs ({kept_tokens}/{total_tokens} tokens)"
        ctx.stats["snipped_count"] = len(snipped)
        ctx.stats["snipped_tokens"] = snipped_tokens
        ctx.stats["avg_kept_importance"] = sum(s for _, s in scored[: len(kept)]) / max(1, len(kept)) if kept else 0
        return ctx

    def _level2_session_memory(self, messages: list[Message], ctx: CompressedContext) -> CompressedContext:
        for msg in messages:
            mem = self._extract_memory_from_message(msg)
            if mem:
                self._session_memory.append(mem)

        recent_msgs = messages[-3:] if len(messages) > 3 else list(messages)
        ctx.messages = recent_msgs
        ctx.compressed_token_count = self.estimate_messages_tokens(recent_msgs)
        ctx.summary = (
            f"SessionMemory: Extracted {len(self._session_memory)} memory entries, "
            f"kept {len(recent_msgs)} recent messages"
        )
        ctx.stats["memory_extracted"] = len(self._session_memory)
        ctx.stats["categories"] = self._get_memory_category_counts()
        return ctx

    def _level3_full_compact(self, messages: list[Message], ctx: CompressedContext) -> CompressedContext:
        for msg in messages:
            mem = self._extract_memory_from_message(msg)
            if mem:
                self._session_memory.append(mem)

        decisions = [m for m in self._session_memory if m.category == MemoryCategory.DECISION]
        findings = [m for m in self._session_memory if m.category == MemoryCategory.FINDING]
        todos = [m for m in self._session_memory if m.category == MemoryCategory.TODO]
        errors = [m for m in self._session_memory if m.category == MemoryCategory.ERROR]
        deliverables = [m for m in self._session_memory if m.category == MemoryCategory.DELIVERABLE]

        summary_lines = ["=== FullCompact Summary ==="]
        summary_lines.append(f"Total messages processed: {len(messages)}")
        summary_lines.append(f"Memory entries extracted: {len(self._session_memory)}")

        if decisions:
            summary_lines.append(f"\n## Key Decisions ({len(decisions)})")
            for d in decisions[:8]:
                summary_lines.append(f"- [{d.category.value}] {d.content[:120]}")

        if deliverables:
            summary_lines.append(f"\n## Deliverables ({len(deliverables)})")
            for d in deliverables[:6]:
                summary_lines.append(f"- {d.content[:120]}")

        if todos:
            summary_lines.append(f"\n## Action Items ({len(todos)})")
            for t in todos[:6]:
                summary_lines.append(f"- [ ] {t.content[:120]}")

        if errors:
            summary_lines.append(f"\n## Errors/Issues ({len(errors)})")
            for e in errors[:4]:
                summary_lines.append(f"- {e.content[:120]}")

        if findings:
            summary_lines.append(f"\n## Key Findings ({len(findings)})")
            for f in findings[:5]:
                summary_lines.append(f"- {f.content[:120]}")

        ctx.messages = []
        ctx.compressed_token_count = self.estimate_tokens("\n".join(summary_lines))
        ctx.summary = "\n".join(summary_lines)
        ctx.stats["decisions"] = len(decisions)
        ctx.stats["findings"] = len(findings)
        ctx.stats["todos"] = len(todos)
        ctx.stats["errors"] = len(errors)
        ctx.stats["deliverables"] = len(deliverables)
        return ctx

    def _level4_smart(self, messages: list[Message], ctx: CompressedContext) -> CompressedContext:
        """Level 4: Structure-aware compression via ContentRouter + SmartCrusher.

        Unlike levels 1-3 which prune or summarize messages, SMART preserves
        all messages but compresses each message's content using structure-aware
        crushers (JSON array → representative subset, log → error+boundary lines).
        Short messages (<=200 chars) are returned unchanged by the crusher.

        Args:
            messages: Original message list.
            ctx: CompressedContext to populate with compressed messages.

        Returns:
            Updated ctx with compressed messages and token count.
        """
        compressed_msgs: list[Message] = []
        crush_count = 0
        for m in messages:
            crushed = self._crusher.crush(m.content)
            if crushed != m.content:
                new_m = Message(
                    message_id=m.message_id,
                    role=m.role,
                    content=crushed,
                    msg_type=m.msg_type,
                    timestamp=m.timestamp,
                    token_count=self.estimate_tokens(crushed),
                    importance_score=m.importance_score,
                    metadata={**m.metadata, "smart_crushed": True},
                )
                compressed_msgs.append(new_m)
                crush_count += 1
            else:
                compressed_msgs.append(m)
        ctx.messages = compressed_msgs
        ctx.compressed_token_count = self.estimate_messages_tokens(compressed_msgs)
        ctx.stats["smart_crush_applied"] = crush_count
        ctx.stats["smart_crush_total"] = len(messages)
        return ctx

    def _extract_memory_from_message(self, msg: Message) -> MemoryEntry | None:
        content = msg.content.strip()
        if not content or len(content) < 10:
            return None

        score = self._score_importance(msg)
        if score < 0.35:
            return None

        category = self._classify_content(content)
        if category is None:
            return None

        tags = self._extract_tags(content)

        return MemoryEntry(
            category=category,
            content=content[:500],
            source_message_ids=[msg.message_id],
            confidence=min(1.0, score),
            tags=tags,
        )

    def _classify_content(self, content: str) -> MemoryCategory | None:
        content_lower = content.lower()

        decision_patterns = [
            "决定",
            "选择",
            "采用",
            "确认",
            "批准",
            "方案",
            "decision",
            "choose",
            "adopt",
            "confirm",
            "approve",
        ]
        todo_patterns = ["todo", "待办", "需要", "下一步", "计划", "后续", "need to", "next step", "plan", "follow-up"]
        error_patterns = [
            "错误",
            "失败",
            "异常",
            "bug",
            "问题",
            "无法",
            "error",
            "fail",
            "exception",
            "issue",
            "cannot",
        ]
        deliverable_patterns = [
            "交付",
            "产出",
            "完成",
            "实现",
            "输出",
            "结果",
            "deliverable",
            "output",
            "complete",
            "implement",
            "result",
        ]
        question_patterns = ["?", "是否", "如何", "为什么", "什么", "能否"]

        for p in decision_patterns:
            if p in content_lower:
                return MemoryCategory.DECISION
        for p in todo_patterns:
            if p in content_lower:
                return MemoryCategory.TODO
        for p in error_patterns:
            if p in content_lower:
                return MemoryCategory.ERROR
        for p in deliverable_patterns:
            if p in content_lower:
                return MemoryCategory.DELIVERABLE
        for p in question_patterns:
            if p in content:
                return MemoryCategory.QUESTION

        if _msg_type_hint := getattr(self, "_last_msg_type", None):
            pass  # intentional no-op: msg type hint reserved for future category override

        return MemoryCategory.FINDING

    def _extract_tags(self, content: str) -> list[str]:
        tags = []
        tag_patterns = {
            "security": ["安全", "安全漏洞", "注入", "xss", "csrf", "权限"],
            "performance": ["性能", "优化", "慢", "延迟", "瓶颈", "缓存"],
            "architecture": ["架构", "模块", "设计", "接口", "组件"],
            "testing": ["测试", "用例", "覆盖", "验证"],
            "data": ["数据", "数据库", "schema", "模型"],
            "api": ["api", "接口", "endpoint", "rest", "graphql"],
        }
        for tag_name, patterns in tag_patterns.items():
            for p in patterns:
                if p in content.lower():
                    tags.append(tag_name)
                    break
        return tags

    def get_session_memory(self, category: MemoryCategory | None = None, limit: int = 50) -> list[MemoryEntry]:
        """Return session memory entries, optionally filtered by category.

        Args:
            category: Optional category to filter by.
            limit: Maximum number of entries to return. Defaults to 50.

        Returns:
            List of MemoryEntry objects (at most `limit`).
        """
        with self._lock:
            if category:
                return [m for m in self._session_memory if m.category == category][:limit]
            return list(self._session_memory)[:limit]

    def query_memory(self, query: str, limit: int = 20) -> list[MemoryEntry]:
        """Search session memory for entries matching the query.

        Matching is case-insensitive against entry content and tags. Matched
        entries have their last_accessed timestamp updated.

        Args:
            query: Search query string.
            limit: Maximum number of entries to return. Defaults to 20.

        Returns:
            List of matching MemoryEntry objects sorted by recency of access.
        """
        query_lower = query.lower()
        results = []
        for entry in self._session_memory:
            if query_lower in entry.content.lower() or query_lower in " ".join(entry.tags):
                entry.last_accessed = datetime.now()
                results.append(entry)
        results.sort(key=lambda e: e.last_accessed, reverse=True)
        return results[:limit]

    def clear_session_memory(self) -> int:
        """Clear all session memory entries.

        Returns:
            The number of entries that were removed.
        """
        with self._lock:
            count = len(self._session_memory)
            self._session_memory.clear()
            return count

    def get_compression_stats(self) -> dict[str, Any]:
        """Return statistics about compression history and session memory.

        Returns:
            Dictionary with total_compressions, memory_entries,
            memory_by_category, and the 5 most recent compression log entries.
        """
        with self._lock:
            return {
                "total_compressions": len(self._compression_log),
                "memory_entries": len(self._session_memory),
                "memory_by_category": self._get_memory_category_counts(),
                "recent_compressions": self._compression_log[-5:] if self._compression_log else [],
            }

    def _get_memory_category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for m in self._session_memory:
            cat = m.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _log_compression(self, result: CompressedContext) -> None:
        self._compression_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "level": result.compression_level.value,
                "original_tokens": result.original_token_count,
                "compressed_tokens": result.compressed_token_count,
                "reduction_pct": round(result.reduction_percent, 1),
                "summary": result.summary[:200] if result.summary else "",
            }
        )
        if len(self._compression_log) > 100:
            self._compression_log = self._compression_log[-50:]

    def export_state(self) -> dict:
        """Export the compressor's state for persistence.

        Returns:
            Dictionary with session_memory entries, the last 20 compression
            log entries, thresholds, and token_threshold.
        """
        with self._lock:
            return {
                "session_memory": [m.to_dict() for m in self._session_memory],
                "compression_log": self._compression_log[-20:],
                "thresholds": self.thresholds,
                "token_threshold": self.token_threshold,
            }

    def import_state(self, state: dict) -> None:
        """Restore the compressor's state from a previously exported dictionary.

        Args:
            state: Dictionary produced by export_state().
        """
        with self._lock:
            self._session_memory = [MemoryEntry.from_dict(m) for m in state.get("session_memory", [])]
            self._compression_log = state.get("compression_log", [])
            self.thresholds = state.get("thresholds", self.DEFAULT_THRESHOLDS)
            self.token_threshold = state.get("token_threshold", 100000)
