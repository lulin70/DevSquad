#!/usr/bin/env python3
"""check_skill_contract.py — V4.5.20 W1-0: contract drift gate.

``SKILL.md`` and ``docs/reference/DETERMINISTIC_CONTRACT.md`` state commitments
that the deterministic layer makes to its callers: the named filter gates, the
four-layer rule chain, the coverage exit-code contract, the zero-token preview,
and the zero-key delegation boundary. Those statements are the spec for
W1-1 .. W1-7 and were written *before* the implementation, by maintainer ruling.

Two things can go wrong with a spec like that, and this gate covers only the
first:

1. **Drift** — the code moves, the document does not. The document then describes
   a system that no longer exists, which is the defect class recorded as F1/F4 in
   ``docs/prd/V4.5.20_ocr-learnings_PRD.md``. Covered here: every clause id, its
   keywords, and its ``Effective`` token must still be present, and every wave
   named in ``Effective`` must still exist in the PRD, so an annotation cannot be
   left pointing at a wave that was renamed or dropped. The ``Effective`` token is
   read from the clause's **own index row**, not from the document at large: a
   document-wide search would accept a blanked cell whenever any other row carried
   the same wave, which is exactly the failure this gate exists to catch.
2. **Over-promising** — the document describes behaviour the code does not have.
   **Not covered here.** A keyword grep cannot prove semantics; a green run means
   "the contract has not drifted", never "the contract is honoured". The clause's
   own ``Proven by`` tests are the evidence for behaviour. Do not cite this gate
   as proof that a clause works.

This is deliberately a separate script rather than another rule inside
``check_version_consistency.py`` (PRD E7): that gate owns version numbers, this
one owns the contract. Mixing them would make a contract failure look like a
release-version failure.

Usage:
    python scripts/check_skill_contract.py
    python scripts/check_skill_contract.py --root .
    python scripts/check_skill_contract.py --quiet

Exit codes:
    0 = all clauses and commitments present, all effective waves resolvable
    1 = at least one clause, keyword, or effective-wave annotation is missing
    2 = a required document could not be read
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILL_DOC = "SKILL.md"
CONTRACT_DOC = "docs/reference/DETERMINISTIC_CONTRACT.md"
PRD_DOC = "docs/prd/V4.5.20_ocr-learnings_PRD.md"
BREAK_VULN_MODULE = "scripts/collaboration/review_taxonomy.py"
BREAK_VULN_CHECKERS = "scripts/collaboration/review_checkers.py"
LIFECYCLE_MODEL = "scripts/collaboration/models_lifecycle.py"
LIFECYCLE_BREAK_VULN = "scripts/collaboration/lifecycle_break_vuln.py"
LIFECYCLE_PROTOCOL = "scripts/collaboration/lifecycle_protocol.py"
LIFECYCLE_PRODUCERS = "scripts/collaboration/lifecycle_finding_producers.py"
LIFECYCLE_SCANNER = "scripts/collaboration/document_scanner.py"
LIFECYCLE_REMEDIATION = "scripts/collaboration/remediation.py"
LIFECYCLE_EVIDENCE = "scripts/collaboration/lifecycle_evidence.py"

# A wave token such as ``W1-3`` must appear in the PRD as a standalone token,
# not as a prefix of a longer identifier.
WAVE_RE_TEMPLATE = r"(?<![\w-]){token}(?![\w-])"


@dataclass(frozen=True)
class Clause:
    """One contract clause: an id, the words that carry its meaning, its wave."""

    id: str
    keywords: tuple[str, ...]
    effective: str

    @property
    def is_wave(self) -> bool:
        """True when ``effective`` names a future wave rather than a shipped version."""
        return self.effective.startswith("W")


@dataclass(frozen=True)
class Commitment:
    """A user-facing commitment that must stay visible in ``SKILL.md``."""

    id: str
    keywords: tuple[str, ...]


# The contract itself. Keywords are chosen to be meaning-bearing and stable: a
# passing check must mean the sentence is still there, not that some word is.
# Note when adding one: keywords are matched against raw markdown, so a phrase
# that straddles an emphasis span (``**no** API-key``) will not match — pick a
# span that survives formatting, or the check reports drift that is not there.
CONTRACT_CLAUSES: tuple[Clause, ...] = (
    Clause(
        "gate.secret_exclude_priority",
        ("secret_exclude", "cannot be overridden by", "include", "fail open"),
        "W1-3",
    ),
    Clause(
        "gate.named_exclusion_reasons",
        (
            "eight",
            "secret_exclude",
            "binary",
            "unsupported_ext",
            "too_large",
            "user_exclude",
            "user_include",
            "default_path",
            "deleted",
        ),
        "W1-3",
    ),
    Clause("gate.exports_are_not_gates", ("kept + dropped", "deliberately listed"), "W1-3"),
    Clause(
        "rule.four_layer_chain",
        (
            "--rule <path>",
            ".devsquad/rule.json",
            "~/.devsquad/rule.json",
            "system_rules.json",
            "RuleConfigError",
            "right-anchored",
        ),
        "W1-1",
    ),
    Clause("rule.first_match_wins", ("wins", "no merge", "no override", "file order"), "W1-1"),
    Clause(
        "rule.system_layer_always_exists",
        ("always present", "no rule found", "system default"),
        "W1-1",
    ),
    Clause(
        "rule.security_exemption_hardcoded",
        ("hardcoded", "cannot be overridden", "attack surfaces"),
        "W1-1",
    ),
    Clause("rule.explain_command", ("devsquad rules check <path>", "winning layer"), "W1-2"),
    Clause(
        "coverage.nonzero_exit",
        ("non-zero", "exits 0", "DispatchResult.success"),
        "shipped in V4.5.20 W1",
    ),
    Clause(
        "coverage.named_failed_roles",
        ("by name", "which", "role_id", "role_name"),
        "shipped in V4.5.20 W1",
    ),
    Clause("preview.zero_llm_calls", ("zero LLM calls", "httpx", "MockBackend"), "W1-4"),
    Clause("preview.summary_by_default", ("counts per gate", "--verbose"), "W1-4"),
    Clause("preview.path_redaction", ("redacted", ".env.production"), "W1-4"),
    Clause(
        "delegate.zero_api_key",
        ("API-key environment variable", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "MOKA_API_KEY", "unset"),
        "shipped in V4.5.10",
    ),
    Clause(
        "delegate.strict_marker_fail_closed",
        ("seven-field marker", "Fail-closed"),
        "shipped in V4.5.10",
    ),
    Clause(
        "delegate.degradation_ladder",
        ("auto-fallback", "visible to the user"),
        "shipped in V4.5.20 W1-6",
    ),
    Clause(
        "delegate.no_silent_mock_fallback",
        ("never quietly falls back", "MockBackend"),
        "shipped in V4.5.20 W1-6",
    ),
    Clause(
        "review.multifile_input_contract",
        ("diff or multiple files", "unchanged"),
        "shipped in V4.5.20 W1-5",
    ),
    Clause(
        "failure.failure_taxonomy",
        (
            "failure_class",
            "product_failed",
            "environment_blocked",
            "exits `1`",
            "`2` for `environment_blocked`",
            "fail-closed",
        ),
        "shipped in V4.6.0 W1",
    ),
    Clause(
        "review.break_vuln_taxonomy",
        (
            "BREAK-1",
            "BREAK-5",
            "VULN-1",
            "VULN-4",
            "critical",
            "warning",
            "applicable",
            "unparseable",
            "changeset",
            "line_range",
        ),
        "shipped in V4.7.0 W1",
    ),
    Clause(
        "lifecycle.break_vuln_findings",
        (
            "LifecycleFinding",
            "BREAK_VULN_PHASES",
            "ReviewFinding",
            "lifecycle_findings",
            "SU/SFD",
            "black-box",
        ),
        "shipped in V4.7.0 W1",
    ),
    Clause(
        "lifecycle.phase_finding_producers",
        (
            "PHASE_PRODUCERS",
            "P1-P11",
            "artifacts",
            "no LLM",
            "lifecycle_findings",
            "SU",
            "SFD",
            "black-box",
        ),
        "shipped in V4.7.0 W1",
    ),
    Clause(
        "lifecycle.document_scan",
        (
            "DocumentScanResult",
            "scan_document",
            "scan_phase_documents",
            "read-only",
            "no SU/SFD",
        ),
        "shipped in V4.7.0 W1",
    ),
    Clause(
        "lifecycle.remediation_proposal",
        (
            "RemediationProposal",
            "proposal_from_finding",
            "approval_required",
            "explicit approval",
            "no auto-fix",
        ),
        "shipped in V4.7.0 W1",
    ),
)

# R9 split: SKILL.md carries only what a caller must know before choosing a mode.
# The 21 clauses above stay in docs/reference/ so SKILL.md does not grow without
# bound.
SKILL_COMMITMENTS: tuple[Commitment, ...] = (
    Commitment("skill.delegate_zero_key", ("no API key", "MOKA_API_KEY")),
    Commitment("skill.coverage_nonzero_exit", ("non-zero",)),
    Commitment("skill.preview_zero_tokens", ("zero LLM calls",)),
    Commitment("skill.contract_pointer", ("docs/reference/DETERMINISTIC_CONTRACT.md",)),
)


def _read(root: Path, relative: str) -> str:
    """Read a repo file as text, raising ``FileNotFoundError`` when absent."""
    return (root / relative).read_text(encoding="utf-8")


def _missing_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    """Return the keywords absent from ``text`` (case-insensitive)."""
    haystack = text.casefold()
    return [word for word in keywords if word.casefold() not in haystack]


def _declared_effective(clause_id: str, contract_text: str) -> str | None:
    """Return the ``Effective`` cell of ``clause_id``'s index row, or ``None``.

    Row-scoped on purpose: searching the whole document would let a blanked cell
    pass whenever another clause happened to name the same wave (found by the W1-0
    negative pass — N2 blanked C1's cell and the gate stayed green).
    """
    for line in contract_text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 4 and clause_id in cells[1]:
            return cells[3]
    return None


def check_clause(clause: Clause, contract_text: str, prd_text: str) -> list[str]:
    """Return the problems found for one clause; empty means it is intact."""
    problems: list[str] = []
    if clause.id not in contract_text:
        problems.append(f"[{clause.id}] clause id is missing from {CONTRACT_DOC}")
    for word in _missing_keywords(contract_text, clause.keywords):
        problems.append(f"[{clause.id}] keyword {word!r} is missing from {CONTRACT_DOC}")
    declared = _declared_effective(clause.id, contract_text)
    if declared is None:
        problems.append(f"[{clause.id}] has no row in the clause index of {CONTRACT_DOC}")
    elif declared != clause.effective:
        problems.append(
            f"[{clause.id}] clause index row declares Effective {declared!r}, expected {clause.effective!r}"
        )
    if clause.is_wave and not _wave_exists_in_prd(clause.effective, prd_text):
        problems.append(
            f"[{clause.id}] effective wave {clause.effective!r} is not defined in {PRD_DOC} (dangling annotation)"
        )
    return problems


def _wave_exists_in_prd(wave: str, prd_text: str) -> bool:
    """True when ``wave`` appears in the PRD as a standalone token."""
    pattern = WAVE_RE_TEMPLATE.format(token=re.escape(wave))
    return re.search(pattern, prd_text) is not None


def check_commitment(commitment: Commitment, skill_text: str) -> list[str]:
    """Return the problems found for one SKILL.md commitment."""
    return [
        f"[{commitment.id}] keyword {word!r} is missing from {SKILL_DOC}"
        for word in _missing_keywords(skill_text, commitment.keywords)
    ]


def check_lifecycle_break_vuln_implementation(
    model_text: str, mapping_text: str, protocol_text: str, producer_text: str
) -> list[str]:
    """Return missing implementation symbols for the lifecycle BREAK/VULN contract."""
    problems: list[str] = []
    for symbol in ("class LifecycleFinding",):
        if symbol not in model_text:
            problems.append(
                f"[lifecycle.break_vuln_findings] implementation symbol {symbol!r} is missing from {LIFECYCLE_MODEL}"
            )
    for symbol in (
        "BREAK_VULN_PHASES",
        "lifecycle_finding_from_review",
        "review_finding_from_lifecycle",
        "map_findings_to_phase",
    ):
        if symbol not in mapping_text:
            problems.append(
                f"[lifecycle.break_vuln_findings] implementation symbol {symbol!r} is missing from {LIFECYCLE_BREAK_VULN}"
            )
    if "lifecycle_findings" not in protocol_text:
        problems.append(
            f"[lifecycle.break_vuln_findings] implementation symbol 'lifecycle_findings' is missing from {LIFECYCLE_PROTOCOL}"
        )
    for symbol in (
        "PHASE_PRODUCERS",
        "produce_phase_findings",
        "produce_p1_findings",
        "produce_p11_findings",
    ):
        if symbol not in producer_text:
            problems.append(
                f"[lifecycle.phase_finding_producers] implementation symbol {symbol!r} is missing from {LIFECYCLE_PRODUCERS}"
            )
    return problems


def check_lifecycle_document_implementation(
    scanner_text: str, remediation_text: str, protocol_text: str, evidence_text: str
) -> list[str]:
    """Return missing implementation symbols for C23/C24 and W4 evidence."""
    problems: list[str] = []
    scanner_symbols = ("DocumentScanResult", "scan_document", "scan_phase_documents", "read_text")
    for symbol in scanner_symbols:
        if symbol not in scanner_text:
            problems.append(
                f"[lifecycle.document_scan] implementation symbol {symbol!r} is missing from {LIFECYCLE_SCANNER}"
            )
    for phrase in ("no SU/SFD", "read-only"):
        if phrase not in scanner_text:
            problems.append(f"[lifecycle.document_scan] boundary {phrase!r} is missing from {LIFECYCLE_SCANNER}")
    remediation_symbols = (
        "RemediationProposal",
        "proposal_from_finding",
        "approval_required",
        "ApprovalRecord",
        "create_patch_preview",
        "apply_approved_patch",
        "resolve_finding_after_verification",
    )
    for symbol in remediation_symbols:
        if symbol not in remediation_text:
            problems.append(
                f"[lifecycle.remediation_proposal] implementation symbol {symbol!r} is missing from {LIFECYCLE_REMEDIATION}"
            )
    for phrase in ("explicit approval", "no auto-fix"):
        if phrase not in remediation_text:
            problems.append(
                f"[lifecycle.remediation_proposal] boundary {phrase!r} is missing from {LIFECYCLE_REMEDIATION}"
            )
    for symbol in ("findings_from_junit_xml", "findings_from_runtime_evidence"):
        if symbol not in evidence_text:
            problems.append(
                f"[lifecycle.evidence] implementation symbol {symbol!r} is missing from {LIFECYCLE_EVIDENCE}"
            )
    for symbol in (
        "DocumentScanResult",
        "scan_document",
        "scan_phase_documents",
        "RemediationProposal",
        "proposal_from_finding",
        "render_proposals_json",
        "ApprovalRecord",
        "create_patch_preview",
        "apply_approved_patch",
        "resolve_finding_after_verification",
    ):
        if symbol not in protocol_text:
            problems.append(f"[lifecycle.protocol] re-export {symbol!r} is missing from {LIFECYCLE_PROTOCOL}")
    return problems


def run(root: Path) -> list[str]:
    """Run every check and return all problems (empty means pass)."""
    contract_text = _read(root, CONTRACT_DOC)
    prd_text = _read(root, PRD_DOC)
    skill_text = _read(root, SKILL_DOC)
    taxonomy_text = _read(root, BREAK_VULN_MODULE)
    checker_text = _read(root, BREAK_VULN_CHECKERS)
    lifecycle_model_text = _read(root, LIFECYCLE_MODEL)
    lifecycle_break_vuln_text = _read(root, LIFECYCLE_BREAK_VULN)
    lifecycle_protocol_text = _read(root, LIFECYCLE_PROTOCOL)
    lifecycle_producer_text = _read(root, LIFECYCLE_PRODUCERS)
    lifecycle_scanner_text = _read(root, LIFECYCLE_SCANNER)
    lifecycle_remediation_text = _read(root, LIFECYCLE_REMEDIATION)
    lifecycle_evidence_text = _read(root, LIFECYCLE_EVIDENCE)

    problems: list[str] = []
    for clause in CONTRACT_CLAUSES:
        problems.extend(check_clause(clause, contract_text, prd_text))
    for commitment in SKILL_COMMITMENTS:
        problems.extend(check_commitment(commitment, skill_text))

    if "BV_CATEGORIES" not in taxonomy_text or "_RULE_TABLE" not in taxonomy_text:
        problems.append(
            f"[review.break_vuln_taxonomy] closed category table or rule registry is missing from {BREAK_VULN_MODULE}"
        )
    for code in (
        "BREAK-1",
        "BREAK-2",
        "BREAK-3",
        "BREAK-4",
        "BREAK-5",
        "VULN-1",
        "VULN-2",
        "VULN-3",
        "VULN-4",
        "VULN-5",
    ):
        if code not in taxonomy_text:
            problems.append(f"[review.break_vuln_taxonomy] category {code} is missing from {BREAK_VULN_MODULE}")
    if "_check_break_vuln" not in checker_text or "check_break_vuln" not in checker_text:
        problems.append(f"[review.break_vuln_taxonomy] Stage 2 wiring is missing from {BREAK_VULN_CHECKERS}")
    problems.extend(
        check_lifecycle_break_vuln_implementation(
            lifecycle_model_text,
            lifecycle_break_vuln_text,
            lifecycle_protocol_text,
            lifecycle_producer_text,
        )
    )
    problems.extend(
        check_lifecycle_document_implementation(
            lifecycle_scanner_text,
            lifecycle_remediation_text,
            lifecycle_protocol_text,
            lifecycle_evidence_text,
        )
    )
    return problems


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. ``argv`` is injectable so tests need no subprocess."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root")
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        problems = run(root)
    except FileNotFoundError as exc:
        print(f"ERROR: cannot read contract source: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        clauses = len(CONTRACT_CLAUSES)
        commitments = len(SKILL_COMMITMENTS)
        print(f"skill-contract: {clauses} clauses, {commitments} SKILL.md commitments")

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"\n{len(problems)} problem(s) — the contract has drifted from the document.")
        print("Fix the document (or the clause table) together with any code change; never leave the two out of step.")
        return 1

    if not args.quiet:
        waves = sorted({c.effective for c in CONTRACT_CLAUSES if c.is_wave})
        print(f"PASS: all clauses intact; future waves resolved: {', '.join(waves)}")
        print("NOTE: presence only — this is a drift alarm, not proof of behaviour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
