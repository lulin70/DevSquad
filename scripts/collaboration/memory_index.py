#!/usr/bin/env python3
"""
MemoryIndexer - 倒排索引 + TF-IDF 检索

为 MemoryBridge 提供基于倒排索引的全文检索能力：
- build_index(): 全量构建索引
- add_to_index() / remove_from_index(): 增量维护
- search(): TF-IDF 相关性检索
- keyword_search(): 关键词交集检索

从 memory_bridge.py 拆分而来，保持向后兼容的 re-export。
"""

import math
import re
import threading
from collections import Counter

from .memory_types import MemoryItem, MemoryType


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
        """Build the full inverted index from a list of memory items.

        Args:
            items: List of MemoryItem objects to index.
        """
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
        """Add a single memory item to the index incrementally.

        Args:
            item: MemoryItem to add.
        """
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
        """Remove a memory item from all indexes by ID.

        Args:
            memory_id: Identifier of the memory item to remove.
        """
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
        """Search the index using TF-IDF relevance scoring.

        Args:
            query_text: Query string to search for.
            type_filter: Optional memory type to filter results by.
            domain_filter: Optional domain to filter results by.
            limit: Maximum number of results to return.

        Returns:
            List of (memory_id, relevance_score) tuples sorted by score
            descending; empty when the index is not built.
        """
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
        """Search the index for documents containing all keywords (AND semantics).

        Args:
            keywords: List of keyword strings; each keyword's tokens must all
                match within a document for it to be considered.
            domain: Optional domain to filter results by.

        Returns:
            List of (memory_id, 1.0) tuples for documents matching all
            keywords; empty when no keywords are provided or no matches exist.
        """
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
        """Check whether the index has been built.

        Returns:
            True once build_index() has completed; False otherwise.
        """
        return self._index_built

    @property
    def size(self) -> int:
        """Return the number of documents currently in the index.

        Returns:
            Document count maintained across add/remove operations.
        """
        return self._doc_count
