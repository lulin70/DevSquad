#!/usr/bin/env python3
"""
PerformanceFingerprint - V3.7.0 Execution Performance Fingerprint Aggregation

Unified execution fingerprint that fuses 4 data sources:
- FeatureUsageTracker (invocation counts)
- PerformanceMonitor (P95/P99 latency)
- CheckpointManager (state snapshots)
- RetrospectiveEngine (retrospective deviations)

Design Principles:
- Pure Python TF-IDF implementation (no sklearn/numpy)
- Thread-safe with RLock
- JSON persistence to .devsquad_data/fingerprints/
- Graceful degradation on cold start (no historical data)
"""

import hashlib
import json
import logging
import math
import os
import re
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PerformanceFingerprint:
    """
    Unified execution fingerprint recording and retrieval.

    Usage:
        fp = PerformanceFingerprint()
        fid = fp.record_execution(
            task="Implement user authentication",
            result=dispatch_result,
            timing={"total": 12.5, "planning": 2.0, "coding": 8.0, "review": 2.5},
            roles_used=["architect", "coder", "tester"],
            intent="feature_implementation",
        )
        similar = fp.find_similar("Add login page")
        stats = fp.get_stats()
    """

    def __init__(self, persist_dir: str = ".devsquad_data/fingerprints"):
        self._persist_dir = persist_dir
        self._fingerprints: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        os.makedirs(persist_dir, exist_ok=True)
        self._load()

    def record_execution(
        self,
        task: str,
        result: Any,
        timing: dict[str, float],
        roles_used: list[str],
        intent: str | None = None,
        mode: str = "auto",
    ) -> str:
        """
        Record an execution fingerprint.

        Args:
            task: Task description text.
            result: DispatchResult-like object with success/error info.
            timing: Timing dict {"total": 1.23, "step1": 0.1, ...}.
            roles_used: List of role names used in this execution.
            intent: Optional intent classification string.
            mode: Execution mode ("auto", "manual", etc.).

        Returns:
            fingerprint_id: Unique identifier for this record.
        """
        fingerprint_id = f"fp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._hash_task(task)[:8]}"

        success = getattr(result, "success", True) if result else True
        error_msg = getattr(result, "error_message", None) if result else None
        error_type = getattr(result, "error_type", None) if result else None

        fingerprint = {
            "fingerprint_id": fingerprint_id,
            "task": task,
            "task_hash": self._hash_task(task),
            "success": success,
            "error_message": error_msg,
            "error_type": error_type,
            "timing": timing,
            "total_duration": timing.get("total", sum(timing.values())),
            "roles_used": sorted(roles_used),
            "role_combo": tuple(sorted(roles_used)),
            "intent": intent,
            "mode": mode,
            "error_patterns": self._extract_error_patterns(result) if not success else [],
            "created_at": datetime.now().isoformat(),
        }

        with self._lock:
            self._fingerprints.append(fingerprint)
            self._persist()

        logger.info("Recorded fingerprint %s for task (success=%s)", fingerprint_id, success)
        return fingerprint_id

    def find_similar(self, task: str, top_k: int = 3) -> list[dict[str, Any]]:
        """
        Find historically similar cases based on TF-IDF similarity.

        Args:
            task: Query task description.
            top_k: Number of similar cases to return.

        Returns:
            List of similar fingerprints sorted by similarity (descending).
            Empty list on cold start or no matches.
        """
        with self._lock:
            if not self._fingerprints:
                return []

            scored = []
            for fp in self._fingerprints:
                sim = self._tfidf_similarity(task, fp["task"])
                if sim > 0:
                    scored.append({**fp, "similarity": round(sim, 4)})

            scored.sort(key=lambda x: x["similarity"], reverse=True)
            return scored[:top_k]

    def get_success_pattern(self, role_combo: tuple) -> dict[str, Any]:
        """
        Extract success pattern for a specific role combination.

        Args:
            role_combo: Tuple of sorted role names, e.g., ("architect", "coder").

        Returns:
            Dict with success_rate, avg_duration, common_intents, count.
        """
        role_tuple = tuple(sorted(role_combo)) if isinstance(role_combo, list) else role_combo

        with self._lock:
            matching = [fp for fp in self._fingerprints if fp["role_combo"] == role_tuple]

            if not matching:
                return {
                    "role_combo": role_tuple,
                    "count": 0,
                    "success_rate": 0.0,
                    "avg_duration": 0.0,
                    "common_intents": [],
                    "sample_size": 0,
                }

            total = len(matching)
            successes = sum(1 for fp in matching if fp["success"])
            durations = [fp["total_duration"] for fp in matching]
            intents = [fp["intent"] for fp in matching if fp.get("intent")]
            intent_counts = Counter(intents).most_common(5)

            return {
                "role_combo": role_tuple,
                "count": total,
                "success_rate": round(successes / total, 4),
                "avg_duration": round(sum(durations) / len(durations), 2),
                "common_intents": [{"intent": i, "count": c} for i, c in intent_counts],
                "sample_size": total,
            }

    def get_failure_patterns(self) -> list[dict[str, Any]]:
        """
        Extract all failure patterns from history.

        Returns:
            List of failure pattern dicts with pattern, count, recent examples.
        """
        with self._lock:
            failures = [fp for fp in self._fingerprints if not fp["success"]]

            if not failures:
                return []

            pattern_counter: Counter = Counter()
            pattern_examples: dict[str, list[dict]] = {}

            for fp in failures:
                patterns = fp.get("error_patterns", [])
                for p in patterns:
                    pattern_counter[p] += 1
                    if p not in pattern_examples:
                        pattern_examples[p] = []
                    if len(pattern_examples[p]) < 3:
                        pattern_examples[p].append(
                            {
                                "task": fp["task"][:80],
                                "created_at": fp["created_at"],
                                "error_message": fp.get("error_message", "")[:100],
                            }
                        )

            result = []
            for pattern, count in pattern_counter.most_common(10):
                result.append(
                    {
                        "pattern": pattern,
                        "count": count,
                        "recent": pattern_examples.get(pattern, []),
                    }
                )

            return result

    def get_stats(self) -> dict[str, Any]:
        """
        Get overall statistics of all fingerprints.

        Returns:
            Dict with total, success_rate, avg_duration, top_roles, top_intents.
        """
        with self._lock:
            total = len(self._fingerprints)
            if total == 0:
                return {
                    "total": 0,
                    "success_rate": 0.0,
                    "avg_duration": 0.0,
                    "top_roles": [],
                    "top_intents": [],
                    "failure_count": 0,
                    "unique_role_combos": 0,
                }

            successes = sum(1 for fp in self._fingerprints if fp["success"])
            durations = [fp["total_duration"] for fp in self._fingerprints]
            all_roles: Counter = Counter()
            intents: Counter = Counter()
            role_combos: set = set()

            for fp in self._fingerprints:
                for role in fp["roles_used"]:
                    all_roles[role] += 1
                if fp.get("intent"):
                    intents[fp["intent"]] += 1
                role_combos.add(fp["role_combo"])

            return {
                "total": total,
                "success_rate": round(successes / total, 4),
                "avg_duration": round(sum(durations) / len(durations), 2),
                "top_roles": [{"role": r, "count": c} for r, c in all_roles.most_common(10)],
                "top_intents": [{"intent": i, "count": c} for i, c in intents.most_common(10)],
                "failure_count": total - successes,
                "unique_role_combos": len(role_combos),
            }

    def _hash_task(self, task: str) -> str:
        """Generate SHA256 hash (first 12 chars) for task text."""
        return hashlib.sha256(task.encode("utf-8")).hexdigest()[:12]

    def _tfidf_similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute TF-IDF cosine similarity between two texts.

        Pure Python implementation without external dependencies.
        Supports both English (word-level) and Chinese (character-level n-grams).
        """
        tokens_a = self._tokenize(text_a)
        tokens_b = self._tokenize(text_b)

        if not tokens_a or not tokens_b:
            return 0.0

        vocab = set(tokens_a) | set(tokens_b)
        n_docs = 2

        tf_a = Counter(tokens_a)
        tf_b = Counter(tokens_b)

        tfidf_a = {}
        tfidf_b = {}

        for term in vocab:
            tf_a_val = tf_a.get(term, 0) / len(tokens_a)
            tf_b_val = tf_b.get(term, 0) / len(tokens_b)

            df = (1 if term in tf_a else 0) + (1 if term in tf_b else 0)
            idf = math.log((1 + n_docs) / (1 + df)) + 1

            tfidf_a[term] = tf_a_val * idf
            tfidf_b[term] = tf_b_val * idf

        dot_product = sum(tfidf_a[t] * tfidf_b[t] for t in vocab)
        norm_a = math.sqrt(sum(v**2 for v in tfidf_a.values()))
        norm_b = math.sqrt(sum(v**2 for v in tfidf_b.values()))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text into terms for TF-IDF.

        - English: split by whitespace/punctuation, keep words >= 2 chars
        - Chinese: extract character bigrams
        - Normalize to lowercase
        """
        text = text.lower()

        english_tokens = re.findall(r"[a-z]{2,}", text)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        chinese_bigrams = [chinese_chars[i] + chinese_chars[i + 1] for i in range(len(chinese_chars) - 1)]

        return english_tokens + chinese_bigrams

    def _extract_error_patterns(self, result: Any) -> list[str]:
        """
        Extract error keyword patterns from a result object.

        Returns list of normalized error pattern strings.
        """
        patterns = []
        if result is None:
            return patterns

        error_msg = getattr(result, "error_message", None) or ""
        error_type = getattr(result, "error_type", None) or ""

        combined = f"{error_type} {error_msg}".lower()

        known_patterns = [
            (r"timeout|timed out", "timeout"),
            (r"connection.*refused|network.*error", "connection_error"),
            (r"permission|denied|forbidden|unauthorized", "permission_error"),
            (r"not found|404|missing", "not_found"),
            (r"invalid.*input|validation.*fail|bad request", "validation_error"),
            (r"resource.*exhausted|rate.?limit|quota", "rate_limit"),
            (r"memory|out of space|heap", "resource_exhaustion"),
            (r"syntax.*error|parse.*error|unexpected", "syntax_error"),
            (r"type.*error|type mismatch", "type_error"),
            (r"key.*error|index.*error", "lookup_error"),
            (r"assertion|assert.*fail", "assertion_error"),
            (r"interrupt|cancel|abort", "interrupted"),
            (r"dependenc.*missing|import.*error", "dependency_error"),
        ]

        for regex, label in known_patterns:
            if re.search(regex, combined):
                patterns.append(label)

        if not patterns and combined.strip():
            patterns.append("unknown_error")

        return patterns

    def _persist(self):
        """Persist fingerprints to JSON file."""
        try:
            target_path = Path(self._persist_dir) / "fingerprints.json"
            data = {
                "version": "3.8.0",
                "updated_at": datetime.now().isoformat(),
                "count": len(self._fingerprints),
                "fingerprints": self._fingerprints,
            }
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            logger.debug("Persisted %d fingerprints to %s", len(self._fingerprints), target_path)
        except (OSError, TypeError, ValueError) as e:
            logger.warning("Failed to persist fingerprints: %s", e)

    def _load(self):
        """Load fingerprints from JSON file."""
        try:
            target_path = Path(self._persist_dir) / "fingerprints.json"
            if target_path.exists():
                with open(target_path, encoding="utf-8") as f:
                    data = json.load(f)
                loaded = data.get("fingerprints", [])
                with self._lock:
                    self._fingerprints = loaded
                logger.info("Loaded %d fingerprints from %s", len(loaded), target_path)
        except (json.JSONDecodeError, OSError, KeyError, TypeError) as e:
            logger.warning("Failed to load fingerprints: %s", e)
            self._fingerprints = []

    def clear(self):
        """Clear all fingerprints (useful for testing)."""
        with self._lock:
            self._fingerprints.clear()
            self._persist()

    def get_fingerprint_count(self) -> int:
        """Return current number of stored fingerprints."""
        with self._lock:
            return len(self._fingerprints)

    def get_all_fingerprints(self) -> list[dict[str, Any]]:
        """Return a copy of all fingerprints (for advanced queries)."""
        with self._lock:
            return list(self._fingerprints)
