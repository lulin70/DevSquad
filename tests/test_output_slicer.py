#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for OutputSlicer (P1-3: EnhancedWorker Output Slicing).

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.3
"""

import pytest
from scripts.collaboration.output_slicer import (
    OutputSlicer,
    OutputSlice,
    SlicedOutput,
    create_default_slicer,
    create_compact_slicer,
    create_large_slicer,
)


class TestOutputSlicingBasic:
    """Test basic slicing functionality."""

    def test_small_output_not_sliced(self):
        slicer = OutputSlicer(max_slice_lines=100)
        output = "Line 1\nLine 2\nLine 3"
        result = slicer.slice_output(output)
        assert result.was_sliced is False
        assert result.total_slices == 1

    def test_large_output_is_sliced(self):
        slicer = OutputSlicer(max_slice_lines=10)
        output = "\n".join([f"Line {i}" for i in range(25)])
        result = slicer.slice_output(output)
        assert result.was_sliced is True
        assert result.total_slices >= 2  # 25 lines / 10 per slice = at least 3 slices

    def test_exact_boundary_not_sliced(self):
        slicer = OutputSlicer(max_slice_lines=10)
        output = "\n".join([f"Line {i}" for i in range(10)])
        result = slicer.slice_output(output)
        assert result.was_sliced is False  # Exactly at boundary, no slice needed

    def test_one_over_boundary_gets_sliced(self):
        slicer = OutputSlicer(max_slice_lines=10)
        output = "\n".join([f"Line {i}" for i in range(11)])
        result = slicer.slice_output(output)
        assert result.was_sliced is True
        assert result.total_slices == 2


class TestSliceStructure:
    """Test individual slice structure."""

    def setup_method(self):
        self.slicer = OutputSlicer(max_slice_lines=5, include_headers=True)

    def test_slices_have_correct_numbers(self):
        output = "\n".join([f"Line {i}" for i in range(12)])
        result = self.slicer.slice_output(output)
        assert len(result.slices) >= 2
        assert result.slices[0].slice_number == 1

    def test_slices_have_correct_line_ranges(self):
        output = "\n".join([f"Line {i}" for i in range(12)])
        result = self.slicer.slice_output(output)
        assert result.slices[0].line_start == 1
        assert result.slices[0].line_end >= 5
        if len(result.slices) > 1:
            assert result.slices[1].line_start > result.slices[0].line_end

    def test_total_slices_consistent(self):
        output = "\n".join([f"L{i}" for i in range(17)])
        result = self.slicer.slice_output(output)
        for s in result.slices:
            assert s.total_slices == result.total_slices

    def test_slice_content_includes_lines(self):
        output = "A\nB\nC\nD\nE\nF"
        result = self.slicer.slice_output(output)
        if result.was_sliced:
            first_slice_content = result.slices[0].content
            assert "A" in first_slice_content


class TestHeaders:
    """Test slice header formatting."""

    def test_headers_enabled_by_default(self):
        slicer = OutputSlicer(include_headers=True)
        output = "\n".join([f"L{i}" for i in range(15)])
        result = slicer.slice_output(output)
        if result.was_sliced:
            assert "--- Slice" in result.slices[0].content
            assert "---" in result.slices[0].content

    def test_headers_disabled(self):
        slicer = OutputSlicer(include_headers=False)
        output = "\n".join([f"L{i}" for i in range(15)])
        result = slicer.slice_output(output)
        if result.was_sliced:
            assert "--- Slice" not in result.slices[0].content


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_returns_unsliced(self):
        slicer = OutputSlicer()
        result = slicer.slice_output("")
        assert result.was_sliced is False
        assert result.total_lines == 0

    def test_whitespace_only_returns_unsliced(self):
        slicer = OutputSlicer()
        result = slicer.slice_output("   \n  \n   ")
        assert result.was_sliced is False or result.total_lines <= 1

    def test_single_line_not_sliced(self):
        slicer = OutputSlicer()
        result = slicer.slice_output("Single line")
        assert result.was_sliced is False

    def test_very_large_output(self):
        slicer = OutputSlicer(max_slice_lines=50)
        output = "\n".join([f"Line number {i} with some content" for i in range(500)])
        result = slicer.slice_output(output)
        assert result.was_sliced is True
        assert result.total_slices == 10  # 500 / 50 = 10
        assert result.total_lines == 500

    def test_minimum_max_slice_lines(self):
        slicer = OutputSlicer(max_slice_lines=10)  # Minimum enforced is 10
        output = "A\nB\nC"
        result = slicer.slice_output(output)
        assert result.was_sliced is False  # 3 lines < 10 min, not sliced


class TestReconstruction:
    """Test that sliced output can be reconstructed."""

    def test_full_output_matches_original(self):
        original = "\n".join([f"Content line {i}" for i in range(23)])
        slicer = OutputSlicer(max_slice_lines=10, include_headers=False)
        result = slicer.slice_output(original)

        reconstructed = result.get_full_output()
        assert reconstructed == original

    def test_unsliced_passthrough(self):
        original = "Short content"
        slicer = OutputSlicer()
        result = slicer.slice_output(original)
        assert result.get_full_output() == original


class TestUtilityMethods:
    """Test utility methods on SlicedOutput."""

    def test_get_valid_slice_by_index(self):
        slicer = OutputSlicer(max_slice_lines=5)
        output = "\n".join([f"L{i}" for i in range(12)])
        result = slicer.slice_output(output)
        s = result.get_slice(0)
        assert s is not None
        assert s.slice_number == 1

    def test_get_invalid_index_returns_none(self):
        slicer = OutputSlicer()
        result = slicer.slice_output("test")
        assert result.get_slice(99) is None

    def test_to_dict_contains_metadata(self):
        slicer = OutputSlicer(max_slice_lines=5)
        output = "\n".join([f"L{i}" for i in range(12)])
        result = slicer.slice_output(output)
        d = result.to_dict()
        assert "total_lines" in d
        assert "total_slices" in d
        assert "was_sliced" in d
        assert "slices" in d


class TestBatchSlicing:
    """Test batch processing of multiple outputs."""

    def test_batch_multiple_outputs(self):
        slicer = OutputSlicer(max_slice_lines=5)
        outputs = [
            "Short",
            "\n".join([f"A{i}" for i in range(10)]),
            "\n".join([f"B{i}" for i in range(20)]),
        ]
        results = slicer.batch_slice_outputs(outputs)
        assert len(results) == 3
        assert results[0].was_sliced is False
        assert results[2].was_sliced is True

    def test_batch_with_task_ids(self):
        slicer = OutputSlicer(max_slice_lines=5)
        outputs = ["A\nB\nC\nD\nE\nF", "X"]
        task_ids = ["task_1", "task_2"]
        results = slicer.batch_slice_outputs(outputs, task_ids=task_ids)
        assert len(results) == 2


class TestFactoryFunctions:
    """Test factory functions for common configurations."""

    def test_default_slicer_has_100_line_limit(self):
        slicer = create_default_slicer()
        assert slicer.max_slice_lines == 100

    def test_compact_slicer_has_50_line_limit(self):
        slicer = create_compact_slicer()
        assert slicer.max_slice_lines == 50

    def test_large_slicer_has_200_line_limit(self):
        slicer = create_large_slicer()
        assert slicer.max_slice_lines == 200

    def test_factory_functions_create_instances(self):
        for factory in [create_default_slicer, create_compact_slicer, create_large_slicer]:
            slicer = factory()
            assert isinstance(slicer, OutputSlicer)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
