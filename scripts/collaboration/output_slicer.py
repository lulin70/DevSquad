#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EnhancedWorker Output Slicing (P1-3)

Adds incremental output capability to EnhancedWorker:
  - Splits large outputs into configurable slices
  - Writes intermediate slices to scratchpad for real-time monitoring
  - Provides progress tracking during long-running tasks

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.3
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OutputSlice:
    """A single slice of output with metadata."""
    slice_number: int
    total_slices: int
    content: str
    line_start: int
    line_end: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slice_number": self.slice_number,
            "total_slices": self.total_slices,
            "line_range": f"{self.line_start}-{self.line_end}",
            "content_length": len(self.content),
            "timestamp": self.timestamp,
        }


@dataclass
class SlicedOutput:
    """Complete sliced output result."""
    original_output: str
    slices: List[OutputSlice] = field(default_factory=list)
    total_lines: int = 0
    total_slices: int = 0
    was_sliced: bool = False

    def get_full_output(self) -> str:
        if not self.was_sliced:
            return self.original_output
        return "\n".join(s.content for s in self.slices)

    def get_slice(self, index: int) -> Optional[OutputSlice]:
        if 0 <= index < len(self.slices):
            return self.slices[index]
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_lines": self.total_lines,
            "total_slices": self.total_slices,
            "was_sliced": self.was_sliced,
            "slices": [s.to_dict() for s in self.slices],
        }


class OutputSlicer:
    """
    Splits large outputs into manageable slices.

    Usage:
        slicer = OutputSlicer(max_slice_lines=100)
        result = slicer.slice_output(large_text)
        print(f"Total: {result.total_slices} slices")
        for s in result.slices:
            print(s.content)
    """

    DEFAULT_MAX_SLICE_LINES = 100
    SLICE_HEADER_TEMPLATE = "\n--- Slice {current}/{total} (lines {start}-{end}) ---\n"

    def __init__(
        self,
        max_slice_lines: int = DEFAULT_MAX_SLICE_LINES,
        include_headers: bool = True,
        write_to_scratchpad: bool = False,
        scratchpad=None,
    ):
        """
        Initialize output slicer.

        Args:
            max_slice_lines: Maximum lines per slice (default: 100)
            include_headers: Add slice headers to each slice
            write_to_scratchpad: Write intermediate slices to scratchpad
            scratchpad: Scratchpad instance for writing slices
        """
        self.max_slice_lines = max(max_slice_lines, 10)  # Minimum 10 lines
        self.include_headers = include_headers
        self.write_to_scratchpad = write_to_scratchpad
        self._scratchpad = scratchpad

    def slice_output(
        self,
        output: str,
        task_id: Optional[str] = None,
        role_id: Optional[str] = None,
    ) -> SlicedOutput:
        """
        Split output into slices if it exceeds max_slice_lines.

        Args:
            output: The full output text to potentially slice
            task_id: Optional task identifier for scratchpad keys
            role_id: Optional role identifier for scratchpad keys

        Returns:
            SlicedOutput with all metadata
        """
        if not output or not output.strip():
            return SlicedOutput(
                original_output=output,
                total_lines=0,
                total_slices=0,
                was_sliced=False,
            )

        lines = output.split('\n')
        total_lines = len(lines)

        if total_lines <= self.max_slice_lines:
            return SlicedOutput(
                original_output=output,
                total_lines=total_lines,
                total_slices=1,
                was_sliced=False,
            )

        # Calculate number of slices needed
        total_slices = (total_lines + self.max_slice_lines - 1) // self.max_slice_lines

        slices = []
        for i in range(0, total_lines, self.max_slice_lines):
            slice_num = i // self.max_slice_lines + 1
            line_start = i + 1
            line_end = min(i + self.max_slice_lines, total_lines)
            slice_lines = lines[i:i + self.max_slice_lines]

            if self.include_headers:
                header = self.SLICE_HEADER_TEMPLATE.format(
                    current=slice_num,
                    total=total_slices,
                    start=line_start,
                    end=line_end,
                )
                content = header + '\n'.join(slice_lines)
            else:
                content = '\n'.join(slice_lines)

            output_slice = OutputSlice(
                slice_number=slice_num,
                total_slices=total_slices,
                content=content,
                line_start=line_start,
                line_end=line_end,
            )
            slices.append(output_slice)

            # Write to scratchpad if enabled
            if self.write_to_scratchpad and self._scratchpad is not None:
                try:
                    key = f"{role_id or 'unknown'}/slice_{slice_num}"
                    if task_id:
                        key = f"{task_id}/{key}"
                    self._scratchpad.write(key, content)
                except Exception as e:
                    logger.debug("Failed to write slice %d to scratchpad: %s", slice_num, e)

        return SlicedOutput(
            original_output=output,
            slices=slices,
            total_lines=total_lines,
            total_slices=total_slices,
            was_sliced=True,
        )

    def batch_slice_outputs(
        self,
        outputs: List[str],
        task_ids: Optional[List[str]] = None,
    ) -> List[SlicedOutput]:
        """
        Slice multiple outputs at once.

        Args:
            outputs: List of output strings to slice
            task_ids: Optional list of task IDs (must match outputs length)

        Returns:
            List of SlicedOutput results
        """
        results = []
        for i, output in enumerate(outputs):
            tid = task_ids[i] if task_ids and i < len(task_ids) else None
            result = self.slice_output(output, task_id=tid)
            results.append(result)
        return results


def create_default_slicer() -> OutputSlicer:
    """Create slicer with default settings (100 lines per slice)."""
    return OutputSlicer()


def create_compact_slicer() -> OutputSlicer:
    """Create compact slicer for small context windows (50 lines)."""
    return OutputSlicer(max_slice_lines=50)


def create_large_slicer() -> OutputSlicer:
    """Create large slicer for detailed outputs (200 lines)."""
    return OutputSlicer(max_slice_lines=200)
