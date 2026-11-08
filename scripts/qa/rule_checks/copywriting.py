"""UX writing (copywriting) rule checks (5).

Button text clarity, error message clarity, form label clarity,
link text descriptiveness and heading descriptiveness detectors.
Each check accepts ``(probes, dials, context)`` and returns ``list[UIUXIssue]``.
"""

from __future__ import annotations

from typing import Any

from ..models import UIUXIssue
from ..taste_dials import TasteDials
from .common import SEVERITY_INFO, SEVERITY_WARNING, _safe_get


def _check_ux_button_text_clarity(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check button text is actionable (not 'Click Here' / 'Submit')."""
    buttons = _safe_get(probes, "interaction", "buttons", default=[])
    if not buttons:
        return []
    vague = {"click here", "submit", "ok", "click", "here", "tap", "go"}
    issues = []
    for btn in buttons:
        text = str(btn.get("text", "")).lower().strip()
        if text in vague:
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="ux_antipattern",
                    rule="ux_button_text_clarity",
                    element=btn.get("text", "")[:20],
                    message=f"Vague button text: '{text}'",
                    fix="Use action-oriented text (e.g. 'Save Changes', 'Delete Account').",
                    metric={"text": text},
                )
            )
    return issues


def _check_ux_error_message_clarity(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check error messages are helpful (not just 'Error')."""
    errors = _safe_get(probes, "ux", "error_messages", default=[])
    if not errors:
        return []
    unhelpful = {"error", "failed", "invalid", "wrong", "error!", "oops"}
    issues = []
    for err in errors:
        text = str(err.get("text", "")).lower().strip()
        if text in unhelpful:
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="ux_antipattern",
                    rule="ux_error_message_clarity",
                    element=err.get("text", "")[:20],
                    message=f"Unhelpful error message: '{text}'",
                    fix="Explain what went wrong and how to fix it.",
                    metric={"text": text},
                )
            )
    return issues


def _check_ux_form_label_clarity(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
    """Check form labels are clear (not just 'Field 1')."""
    inputs = _safe_get(probes, "a11y", "inputs", default=[])
    if not inputs:
        return []
    issues = []
    for inp in inputs:
        label = str(inp.get("label_text", "")).lower().strip()
        if label.startswith("field ") or label in {"input", "text", "value"}:
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="ux_antipattern",
                    rule="ux_form_label_clarity",
                    element=inp.get("id", "input"),
                    message=f"Unclear form label: '{label}'",
                    fix="Use descriptive labels (e.g. 'Email Address', not 'Field 1').",
                    metric={"label": label},
                )
            )
    return issues


def _check_ux_link_text_descriptive(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check link text is descriptive (not 'click here' / 'read more')."""
    links = _safe_get(probes, "ux", "links", default=[])
    if not links:
        return []
    vague = {"click here", "read more", "more", "here", "link", "learn more"}
    issues = []
    for link in links:
        text = str(link.get("text", "")).lower().strip()
        if text in vague:
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="ux_antipattern",
                    rule="ux_link_text_descriptive",
                    element=link.get("text", "")[:20],
                    message=f"Vague link text: '{text}'",
                    fix="Use descriptive link text (e.g. 'Read API Guide').",
                    metric={"text": text},
                )
            )
    return issues


def _check_ux_heading_descriptive(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check headings are descriptive (not just 'Heading' or 'Title')."""
    headings = _safe_get(probes, "typography", "headings", default=[])
    if not headings:
        return []
    vague = {"heading", "title", "section", "block", "untitled", ""}
    issues = []
    for h in headings:
        text = str(h.get("text", "")).lower().strip()
        if text in vague:
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="ux_antipattern",
                    rule="ux_heading_descriptive",
                    element=f"h{h.get('level', '?')}",
                    message=f"Vague heading: '{text}'",
                    fix="Use descriptive headings that convey content meaning.",
                    metric={"text": text},
                )
            )
    return issues
