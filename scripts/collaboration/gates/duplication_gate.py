# DevSquad V5.0 - Simplicity Role - DuplicationGate Implementation
# Token-based duplication detection (Python native, no jscpd dependency)

"""
DuplicationGate: Token-based code duplication detector

Uses Python's tokenize module to detect duplicated token sequences.
Faster and simpler than AST-based approaches, suitable for S2 gate.

Thresholds:
- Duplication < 8%: PASS
- 8% ≤ Duplication < 90%: WARNING
- Duplication ≥ 90%: REJECT
"""

import logging
import tokenize
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class DuplicationClone:
    """Duplicated code block"""
    file1: str
    file2: str
    start_line1: int
    start_line2: int
    token_count: int


class DuplicationGate:
    """Token-based duplication gate"""
    
    def __init__(self, threshold: float = 0.08, min_tokens: int = 50) -> None:
        """
        Initialize duplication gate
        
        Args:
            threshold: Duplication rate threshold (default 8%)
            min_tokens: Minimum token sequence length to consider (default 50)
        """
        self.threshold = threshold
        self.min_tokens = min_tokens
        self.warning_threshold = 0.9
    
    def detect_duplication(
        self,
        target_paths: list[Path]
    ) -> tuple[float, list[DuplicationClone]]:
        """
        Detect duplicated token sequences
        
        Args:
            target_paths: List of file paths to analyze
        
        Returns:
            (duplication_rate, clones)
        """
        if not target_paths:
            return 0.0, []
        
        # Tokenize all files
        file_tokens = {}
        total_tokens = 0
        
        for path in target_paths:
            try:
                tokens = self._tokenize_file(path)
                if tokens:
                    file_tokens[str(path)] = tokens
                    total_tokens += len(tokens)
            except Exception as e:
                logger.warning(f"Failed to tokenize {path}: {e}")
                continue
        
        if not file_tokens or total_tokens == 0:
            return 0.0, []
        
        # Find duplicated sequences using sliding window + hashing
        clones = self._find_clones(file_tokens)
        
        # Calculate duplication rate
        duplicated_tokens = sum(clone.token_count for clone in clones)
        duplication_rate = duplicated_tokens / total_tokens if total_tokens > 0 else 0.0
        
        return duplication_rate, clones
    
    def _tokenize_file(self, file_path: Path) -> list[tuple[int, str]]:
        """
        Tokenize a Python file
        
        Returns:
            List of (token_type, token_string) tuples, filtered
        """
        try:
            with open(file_path, 'rb') as f:
                tokens = []
                for tok in tokenize.tokenize(f.readline):
                    # Filter out comments, newlines, encoding, endmarker
                    if tok.type in (tokenize.COMMENT, tokenize.NL, 
                                   tokenize.NEWLINE, tokenize.ENCODING,
                                   tokenize.ENDMARKER, tokenize.INDENT,
                                   tokenize.DEDENT):
                        continue
                    tokens.append((tok.start[0], tok.string))
                return tokens
        except Exception as e:
            logger.error(f"Tokenization error for {file_path}: {e}")
            return []
    
    def _find_clones(
        self,
        file_tokens: dict[str, list[tuple[int, str]]]
    ) -> list[DuplicationClone]:
        """
        Find duplicated token sequences using rolling hash
        
        Args:
            file_tokens: {file_path: [(line, token_string), ...]}
        
        Returns:
            List of DuplicationClone
        """
        clones = []
        seen_pairs = set()
        
        # Build hash index: {token_sequence_hash: [(file, start_idx, line), ...]}
        hash_index = defaultdict(list)
        
        for file_path, tokens in file_tokens.items():
            token_strings = [t[1] for t in tokens]
            
            # Sliding window
            for i in range(len(token_strings) - self.min_tokens + 1):
                window = tuple(token_strings[i:i + self.min_tokens])
                window_hash = hash(window)
                start_line = tokens[i][0] if i < len(tokens) else 0
                hash_index[window_hash].append((file_path, i, start_line))
        
        # Find duplicates (same hash appears > 1 time)
        for window_hash, occurrences in hash_index.items():
            if len(occurrences) < 2:
                continue
            
            # Create clone pairs
            for i in range(len(occurrences)):
                for j in range(i + 1, len(occurrences)):
                    file1, idx1, line1 = occurrences[i]
                    file2, idx2, line2 = occurrences[j]
                    
                    # Create canonical pair key to avoid duplicates
                    pair_key = tuple(sorted([
                        (file1, line1),
                        (file2, line2)
                    ]))
                    
                    if pair_key in seen_pairs:
                        continue
                    
                    seen_pairs.add(pair_key)
                    
                    clones.append(DuplicationClone(
                        file1=file1,
                        file2=file2,
                        start_line1=line1,
                        start_line2=line2,
                        token_count=self.min_tokens
                    ))
        
        return clones
    
    def check(
        self,
        target_paths: list[Path]
    ) -> dict[str, Any]:
        """
        Execute gate check
        
        Returns:
            {
                "status": "PASS" | "WARNING" | "REJECT",
                "duplication_rate": float,
                "clones": list[dict],
                "total_clones": int
            }
        """
        duplication_rate, clones = self.detect_duplication(target_paths)
        
        # Determine status
        if duplication_rate >= self.warning_threshold:
            status = "REJECT"
        elif duplication_rate >= self.threshold:
            status = "WARNING"
        else:
            status = "PASS"
        
        # Serialize clones
        clone_dicts = [
            {
                "file1": clone.file1,
                "file2": clone.file2,
                "line1": clone.start_line1,
                "line2": clone.start_line2,
                "tokens": clone.token_count
            }
            for clone in clones
        ]
        
        return {
            "status": status,
            "duplication_rate": round(duplication_rate, 3),
            "clones": clone_dicts,
            "total_clones": len(clones)
        }
