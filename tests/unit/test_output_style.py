"""Unit tests for OutputStyle (V4.5.0 — PRD 10.1.1).

8 tests covering the three Iron Rules:
1. test_prompt_dials_has_output_style — Happy (field exists, default="detailed")
2. test_invalid_output_style_raises — Boundary (invalid value → ValueError)
3. test_action_first_leads_with_actions — Happy (first section is "Next Actions")
4. test_action_first_caps_lists — Side-Effect (lists capped at 5 items)
5. test_action_first_no_preamble — Side-Effect (no "Here is" / "In summary" / "To summarize")
6. test_detailed_backward_compat — Backward-Compat (output_style="detailed" == existing)
7. test_compact_mode — Happy (output_style="compact" shorter than detailed)
8. test_call_counter_er — Anti-Ghost (_call_counter_er > 0)

Uses REAL PromptDials, ReportFormatter, and DispatchResult (no Mock) per
V4.5.0 implementation rules.
"""

from __future__ import annotations

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration import report_formatter as rf_module  # noqa: E402
from scripts.collaboration.dispatch_models import DispatchResult  # noqa: E402
from scripts.collaboration.prompt_dials import PromptDials  # noqa: E402
from scripts.collaboration.report_formatter import ReportFormatter  # noqa: E402

pytestmark = [pytest.mark.unit]


def _make_result() -> DispatchResult:
    """Build a real DispatchResult exercising all action_first code paths.

    - architect worker output has 7 numbered findings → triggers the 5-cap
      (overflow → "and 2 more").
    - tester worker output has 2 findings → no overflow.
    - errors + failed worker + unresolved consensus → action items.
    - suggested_next_steps → Next Step section content.
    """
    return DispatchResult(
        success=True,
        task_description="Implement OutputStyle feature for DevSquad V4.5.0",
        matched_roles=["architect", "tester", "security"],
        summary="Multi-agent collaboration completed.",
        scratchpad_summary=(
            "1. Scratchpad finding one\n"
            "2. Scratchpad finding two\n"
            "3. Scratchpad finding three\n"
            "4. Scratchpad finding four\n"
            "5. Scratchpad finding five\n"
            "6. Scratchpad finding six"
        ),
        worker_results=[
            {
                "role": "architect",
                "role_id": "architect",
                "success": True,
                "output": (
                    "1. Arch finding A1\n"
                    "2. Arch finding A2\n"
                    "3. Arch finding A3\n"
                    "4. Arch finding A4\n"
                    "5. Arch finding A5\n"
                    "6. Arch finding A6\n"
                    "7. Arch finding A7"
                ),
            },
            {
                "role": "tester",
                "role_id": "tester",
                "success": False,
                "output": "1. Test finding T1\n2. Test finding T2",
            },
            {
                "role": "security",
                "role_id": "security",
                "success": True,
                "output": "1. Sec finding S1\n2. Sec finding S2",
            },
        ],
        consensus_records=[
            {"topic": "auth approach", "outcome": "SPLIT"},
            {"topic": "data layout", "outcome": "ESCALATED"},
            {"topic": "test plan", "outcome": "TIMEOUT"},
        ],
        errors=["Worker timeout on tester role"],
        memory_stats={"total_memories": 5, "knowledge_count": 2, "episodic_count": 3},
        skill_proposals=[{"title": "OutputStyleSkill", "confidence": 0.82}],
        suggested_next_steps=["Review the action_first report format with the team."],
        duration_seconds=1.23,
    )


def test_prompt_dials_has_output_style() -> None:
    """PromptDials exposes output_style field; default is 'detailed'."""
    dials = PromptDials()
    assert "output_style" in PromptDials.__dataclass_fields__
    assert dials.output_style == "detailed"


def test_invalid_output_style_raises() -> None:
    """Invalid output_style value raises ValueError in __post_init__."""
    with pytest.raises(ValueError):
        PromptDials(output_style="invalid_style")
    with pytest.raises(ValueError):
        PromptDials(output_style="")


def test_action_first_leads_with_actions() -> None:
    """action_first report's first section header is '## Next Actions'."""
    formatter = ReportFormatter()
    result = _make_result()
    report = formatter.format_report(result, output_style="action_first")
    first_line = report.lstrip().split("\n", 1)[0]
    assert first_line == "## Next Actions", f"Expected '## Next Actions' first, got: {first_line!r}"


def test_action_first_caps_lists() -> None:
    """All numbered lists in action_first mode have ≤5 items; overflow noted.

    PRD 10.1.1: "capped at 5 items per role" — so the cap applies per-role
    block within Key Findings, and per-section elsewhere.
    """
    formatter = ReportFormatter()
    result = _make_result()
    report = formatter.format_report(result, output_style="action_first")

    # Split into blocks delimited by '## ' headers AND '**Role**:' role lines
    # (the Key Findings section groups findings per role). Each block's
    # numbered list must stay within the 5-item cap.
    blocks = _split_blocks(report)
    assert blocks, "Report should contain at least one block"
    for block in blocks:
        numbered = _count_numbered_items(block)
        assert numbered <= 5, (
            f"action_first block exceeds 5-item cap ({numbered} items):\n{block}"
        )

    # architect worker had 7 findings → must be capped with "and 2 more".
    assert "and 2 more" in report, (
        "Expected 'and 2 more' overflow marker for architect (7 findings → 5 shown)."
    )


def test_action_first_no_preamble() -> None:
    """action_first report contains no preamble/recap/closers."""
    formatter = ReportFormatter()
    result = _make_result()
    report = formatter.format_report(result, output_style="action_first")
    for forbidden in ("Here is", "In summary", "To summarize"):
        assert forbidden not in report, f"action_first must not contain '{forbidden}'"


def test_detailed_backward_compat() -> None:
    """output_style='detailed' produces identical output to existing renderer."""
    formatter = ReportFormatter()
    result = _make_result()
    via_style = formatter.format_report(result, output_style="detailed")
    existing = formatter.format_structured_report(result)
    assert via_style == existing, (
        "output_style='detailed' must preserve existing format_structured_report output 100%"
    )


def test_compact_mode() -> None:
    """output_style='compact' produces a shorter report than 'detailed'."""
    formatter = ReportFormatter()
    result = _make_result()
    compact = formatter.format_report(result, output_style="compact")
    detailed = formatter.format_report(result, output_style="detailed")
    assert len(compact) < len(detailed), (
        f"compact ({len(compact)} chars) should be shorter than "
        f"detailed ({len(detailed)} chars)"
    )


def test_call_counter_er() -> None:
    """Anti-ghost: module-level _call_counter_er > 0 after format_report calls."""
    # The other tests already call format_report, but exercise it again here
    # to make this test self-contained.
    formatter = ReportFormatter()
    result = _make_result()
    formatter.format_report(result, output_style="action_first")
    assert rf_module._call_counter_er > 0, (
        "_call_counter_er must be > 0 after format_report dispatch (anti-ghost)"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_blocks(report: str) -> list[str]:
    """Split a report into blocks for per-list cap checking.

    Blocks are delimited by either a ``## `` section header or a
    ``**RoleName**:`` role header (the Key Findings section groups findings
    per role). This lets the cap assertion honor PRD 10.1.1's
    "capped at 5 items per role" semantics rather than treating the whole
    Key Findings section as one list.
    """
    import re

    parts = re.split(r"(?=^(?:## |\*\*[^\n*]+\*\*:))", report, flags=re.MULTILINE)
    return [p for p in parts if p.strip()]


def _count_numbered_items(section: str) -> int:
    """Count Markdown numbered list items (lines starting with 'N.') in a section."""
    import re

    return len(re.findall(r"^\s*\d+\.\s", section, flags=re.MULTILINE))
