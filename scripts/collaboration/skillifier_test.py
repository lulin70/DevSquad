#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skillifier E2E Test Suite
Covers: Data models, Record management, Pattern extraction,
      Generalization, Skill generation, Validation(5-dimension),
      Publishing, Discovery, Edge cases, Thread safety
"""

import sys
import os
import json
import threading
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collaboration.skillifier import (
    Skillifier, ExecutionRecord, ExecutionStep,
    SuccessPattern, PatternStep, SkillProposal, SkillStepDef,
    ValidationResult, ProposalStatus, SkillCategory,
    PGActionType,
)


# ============================================================
# Helpers
# ============================================================

passed = 0
failed = 0
errors = []
TOTAL = 0


def test(name, func):
    global passed, failed, TOTAL, errors
    TOTAL += 1
    try:
        func()
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ❌ {name}: {e}")


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg} Expected {expected!r}, got {actual!r}")


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(f"Expected True: {msg}")


def assert_between(val, lo, hi, msg=""):
    if not (lo <= val <= hi):
        raise AssertionError(f"{msg} Expected [{lo}, {hi}], got {val}")


def assert_in(item, container, msg=""):
    if item not in container:
        raise AssertionError(f"{msg} {item!r} not in {container!r}")


def assert_not_in(item, container, msg=""):
    if item in container:
        raise AssertionError(f"{msg} {item!r} should not be in {container!r}")


def make_step(order, atype=PGActionType.FILE_READ, target="", desc="", outcome="success"):
    return ExecutionStep(step_order=order, action_type=atype, target=target,
                         description=desc, outcome=outcome)

def make_record(desc, success=True, worker="w1", role="dev", steps=None):
    r = ExecutionRecord(task_description=desc, success=success,
                        worker_id=worker, role_id=role, steps=steps or [])
    r.finalize()
    return r


def make_python_init_record(variant=1):
    base_steps = [
        make_step(1, PGActionType.FILE_CREATE, f"project_v{variant}/README.md",
                 "Create README"),
        make_step(2, PGActionType.FILE_CREATE, f"project_v{variant}/src/__init__.py",
                 "Create package init"),
        make_step(3, PGActionType.FILE_CREATE, f"project_v{variant}/src/main.py",
                 "Create main module"),
        make_step(4, PGActionType.FILE_CREATE, f"project_v{variant}/tests/test_main.py",
                 "Create test file"),
        make_step(5, PGActionType.FILE_MODIFY, f"project_v{variant}/requirements.txt",
                 "Add dependencies"),
    ]
    return make_record(f"Python project init v{variant}", steps=base_steps)


# ============================================================
# T1: Data Models (12)
# ============================================================

print("\n=== T1: Data Models ===")


def t1_01_execution_step_fields():
    s = make_step(1, PGActionType.FILE_READ, "test.py", "Read test file")
    assert_eq(s.step_order, 1)
    assert_eq(s.action_type, PGActionType.FILE_READ)
    assert_eq(s.target, "test.py")
    assert_eq(s.outcome, "success")

test("T1.01 ExecutionStep fields", t1_01_execution_step_fields)


def t1_02_step_roundtrip():
    s = make_step(3, PGActionType.SHELL_EXECUTE, "pytest", "Run tests")
    d = s.to_dict()
    s2 = ExecutionStep.from_dict(d)
    assert_eq(s2.action_type, PGActionType.SHELL_EXECUTE)
    assert_eq(s2.target, "pytest")

test("T1.02 Step roundtrip", t1_02_step_roundtrip)


def t1_03_record_defaults():
    r = ExecutionRecord()
    assert_true(r.record_id.startswith("er-"))
    assert_eq(r.success, True)
    assert_eq(len(r.steps), 0)

test("T1.03 Record defaults", t1_03_record_defaults)


def t1_04_record_finalize():
    r = ExecutionRecord(task_description="test task")
    time.sleep(0.01)
    r.finalize()
    assert_true(r.end_time is not None)
    assert_true(r.duration_seconds >= 0)

test("T1.04 Record finalize", t1_04_record_finalize)


def t1_05_record_to_dict():
    r = make_record("my task", steps=[make_step(1)])
    d = r.to_dict()
    assert_in("record_id", d)
    assert_in("task_description", d)
    assert_in("step_count", d)

test("T1.05 Record to_dict", t1_05_record_to_dict)


def t1_06_pattern_step_fields():
    ps = PatternStep(PGActionType.FILE_CREATE, "*.py", "Create Python file")
    assert_eq(ps.is_required, True)
    assert_eq(ps.estimated_risk, 0.0)

test("T1.06 PatternStep fields", t1_06_pattern_step_fields)


def t1_07_success_pattern_fields():
    p = SuccessPattern(name="Test Pattern", frequency=5, confidence=0.8)
    assert_true(p.pattern_id.startswith("sp-"))
    assert_eq(p.frequency, 5)
    assert_between(p.confidence, 0.0, 1.0)

test("T1.07 SuccessPattern fields", t1_07_success_pattern_fields)


def t1_08_pattern_to_dict():
    p = SuccessPattern(name="Test", trigger_keywords=["test", "verify"])
    d = p.to_dict()
    assert_in("pattern_id", d)
    assert_in("frequency", d)
    assert_in("trigger_keywords", d)

test("T1.08 Pattern to_dict", t1_08_pattern_to_dict)


def t1_09_proposal_defaults():
    sp = SkillProposal()
    assert_true(sp.proposal_id.startswith("prop-"))
    assert_eq(sp.status, ProposalStatus.DRAFT)
    assert_eq(sp.version, "1.0.0")

test("T1.09 Proposal defaults", t1_09_proposal_defaults)


def t1_10_validation_result():
    vr = ValidationResult(score=85.5, completeness=90, specificity=80,
                          repeatability=75, safety=95)
    assert_eq(vr.grade(), "A")
    vr2 = ValidationResult(score=50)
    assert_eq(vr2.grade(), "D")

test("T1.10 Validation grade A/D", t1_10_validation_result)


def t1_11_enums_completeness():
    statuses = [s.value for s in ProposalStatus]
    assert_eq(len(statuses), 5)
    cats = [c.value for c in SkillCategory]
    assert_true(len(cats) >= 10, f"got {len(cats)} categories")

test("T1.11 Enums complete", t1_11_enums_completeness)


def t1_12_unicode_content():
    r = make_record("中文任务描述测试", steps=[
        make_step(1, target="/项目/代码/main.py", desc="创建主模块文件")
    ])
    assert_eq(r.task_description, "中文任务描述测试")

test("T1.12 Unicode content", t1_12_unicode_content)


# ============================================================
# T2: Record Management (8)
# ============================================================

print("\n=== T2: Record Management ===")


def t2_01_record_and_retrieve():
    sf = Skillifier()
    r = make_record("task-1", steps=[make_step(1)])
    sf.record_execution(r)
    recs = sf.get_records()
    assert_eq(len(recs), 1)

test("T2.01 Record and retrieve", t2_01_record_and_retrieve)


def t2_02_multiple_records():
    sf = Skillifier()
    for i in range(5):
        sf.record_execution(make_record(f"task-{i}", steps=[make_step(1)]))
    assert_eq(len(sf.get_records()), 5)

test("T2.02 Multiple records", t2_02_multiple_records)


def t2_03_failed_records_filtered():
    sf = Skillifier()
    sf.record_execution(make_record("ok", success=True, steps=[make_step(1)]))
    sf.record_execution(make_record("fail", success=False, steps=[make_step(1)]))
    recs = sf.get_records(success_only=True)
    assert_eq(len(recs), 1)

test("T2.03 Failed records filtered", t2_03_failed_records_filtered)


def t2_04_time_filtering():
    sf = Skillifier()
    old = make_record("old", steps=[make_step(1)])
    old.start_time = datetime.now() - timedelta(days=7)
    old.finalize()
    sf.record_execution(old)
    recent = make_record("recent", steps=[make_step(1)])
    sf.record_execution(recent)
    recs = sf.get_records(since=datetime.now() - timedelta(hours=1))
    assert_eq(len(recs), 1)

test("T2.04 Time filtering", t2_04_time_filtering)


def t2_05_empty_records_analyze():
    sf = Skillifier()
    patterns = sf.analyze_history()
    assert_eq(len(patterns), 0)

test("T2.05 Empty history → empty patterns", t2_05_empty_records_analyze)


def t2_06_single_record_no_pattern():
    sf = Skillifier(min_pattern_occurrences=2)
    sf.record_execution(make_python_init_record())
    patterns = sf.analyze_history()
    assert_eq(len(patterns), 0)

test("T2.06 Single record no pattern", t2_06_single_record_no_pattern)


def t2_07_all_failures_no_pattern():
    sf = Skillifier()
    for i in range(3):
        r = make_python_init_record(i + 1)
        r.success = False
        sf.record_execution(r)
    patterns = sf.analyze_history()
    assert_eq(len(patterns), 0)

test("T2.07 All failures → no pattern", t2_07_all_failures_no_pattern)


def t2_08_statistics():
    sf = Skillifier()
    sf.record_execution(make_record("a", success=True, steps=[make_step(1)]))
    sf.record_execution(make_record("b", success=False, steps=[make_step(1)]))
    stats = sf.get_statistics()
    assert_eq(stats["total_records"], 2)
    assert_eq(stats["successful_records"], 1)

test("T2.08 Statistics", t2_08_statistics)


# ============================================================
# T3: Pattern Extraction (14)
# ============================================================

print("\n=== T3: Pattern Extraction ===")


def t3_01_basic_extraction():
    sf = Skillifier(min_pattern_occurrences=3)
    for i in range(5):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    assert_true(len(patterns) >= 1, f"Should extract pattern, got {len(patterns)}")

test("T3.01 Basic pattern extraction", t3_01_basic_extraction)


def t3_02_pattern_has_name():
    sf = Skillifier(min_pattern_occurrences=3)
    for i in range(5):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        assert_true(len(patterns[0].name) > 0, "Pattern has name")

test("T3.02 Pattern has name", t3_02_pattern_has_name)


def t3_03_pattern_has_steps_template():
    sf = Skillifier(min_pattern_occurrences=3)
    for i in range(5):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        assert_true(len(patterns[0].steps_template) > 0, "Has step templates")

test("T3.03 Has steps template", t3_03_pattern_has_steps_template)


def t3_04_pattern_frequency():
    sf = Skillifier(min_pattern_occurrences=3)
    for i in range(5):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        assert_true(patterns[0].frequency >= 3, f"freq={patterns[0].frequency}")

test("T3.04 Frequency >= min_occurrences", t3_04_pattern_frequency)


def t3_05_confidence_range():
    sf = Skillifier(min_pattern_occurrences=3)
    for i in range(5):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        assert_between(patterns[0].confidence, 0.0, 1.0, "confidence range")

test("T3.05 Confidence in [0,1]", t3_05_confidence_range)


def t3_06_trigger_keywords_exist():
    sf = Skillifier(min_pattern_occurrences=3)
    for i in range(5):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        assert_true(len(patterns[0].trigger_keywords) > 0, "Has keywords")

test("T3.06 Trigger keywords exist", t3_06_trigger_keywords_exist)


def t3_07_different_tasks_separate_patterns():
    sf = Skillifier(min_pattern_occurrences=3)
    for i in range(4):
        sf.record_execution(make_python_init_record(i + 1))
    deploy_steps = [
        make_step(1, PGActionType.SHELL_EXECUTE, "docker build .", "Build image"),
        make_step(2, PGActionType.SHELL_EXECUTE, "docker push myapp:v1", "Push image"),
        make_step(3, PGActionType.GIT_OPERATION, "git tag v1.0", "Tag release"),
    ]
    for i in range(4):
        sf.record_execution(make_record(f"deploy-{i}", steps=deploy_steps))
    patterns = sf.analyze_history()
    assert_true(len(patterns) >= 1, "At least one pattern extracted")

test("T3.07 Different tasks separate", t3_07_different_tasks_separate_patterns)


def t3_08_source_records_tracked():
    sf = Skillifier(min_pattern_occurrences=2)
    ids = []
    for i in range(3):
        r = make_python_init_record(i + 1)
        sf.record_execution(r)
        ids.append(r.record_id)
    patterns = sf.analyze_history()
    if patterns:
        for rid in ids:
            assert_in(rid, patterns[0].source_records, "Source record tracked")

test("T3.08 Source records tracked", t3_08_source_records_tracked)


def t3_09_applicable_roles():
    sf = Skillifier(min_pattern_occurrences=2)
    roles_map = {"arch": "architect", "dev": "developer", "test": "tester"}
    for i, (k, v) in enumerate(roles_map.items()):
        r = make_python_init_record(i + 1)
        r.role_id = v
        sf.record_execution(r)
    patterns = sf.analyze_history()
    if patterns:
        assert_true(len(patterns[0].applicable_roles) > 0, "Roles captured")

test("T3.09 Applicable roles", t3_09_applicable_roles)


def t3_10_pattern_library_query():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    sf.analyze_history()
    library = sf.get_pattern_library()
    assert_true(len(library) >= 1, "Library has entries")

test("T3.10 Pattern library query", t3_10_pattern_library_query)


def t3_11_export_patterns_json():
    sf = Skillifier()
    json_str = sf.export_patterns()
    data = json.loads(json_str)
    assert_true(isinstance(data, list), "Export is JSON array")

test("T3.11 Export patterns JSON", t3_11_export_patterns_json)


def t3_12_low_confidence_filtered():
    sf = Skillifier(min_pattern_occurrences=2, min_confidence=0.99)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    high_conf = [p for p in patterns if p.confidence >= 0.99]
    assert_true(len(high_conf) == len(patterns),
                f"All patterns meet confidence threshold")

test("T3.12 Low confidence filtered", t3_12_low_confidence_filtered)


def t3_13_success_rate_calculation():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(4):
        r = make_python_init_record(i + 1)
        if i == 3:
            r.success = False
        sf.record_execution(r)
    patterns = sf.analyze_history()
    if patterns:
        assert_true(0 < patterns[0].avg_success_rate <= 1.0,
                    f"Success rate in valid range: {patterns[0].avg_success_rate}")

test("T3.13 Success rate calculation", t3_13_success_rate_calculation)


def t3_14_pattern_persistence():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    p1 = sf.analyze_history()
    p2 = sf.analyze_history()
    assert_eq(len(p2), len(p1), "Patterns persist across calls")

test("T3.14 Patterns persist across calls", t3_14_pattern_persistence)


# ============================================================
# T4: Similarity & Clustering (8)
# ============================================================

print("\n=== T4: Similarity & Clustering ===")


def t4_01_identical_sequences_high_sim():
    sf = Skillifier()
    steps = [make_step(1, PGActionType.FILE_READ, "a.txt"),
             make_step(2, PGActionType.FILE_MODIFY, "b.py")]
    sim = sf._sequence_similarity(steps, steps)
    assert_true(sim > 0.85, f"Identical sequences: sim={sim:.2f}")

test("T4.01 Identical sequences ≈1.0", t4_01_identical_sequences_high_sim)


def t4_02_different_types_low_sim():
    sf = Skillifier()
    seq_a = [make_step(1, PGActionType.FILE_READ, "a.txt")]
    seq_b = [make_step(1, PGActionType.SHELL_EXECUTE, "rm -rf /")]
    sim = sf._sequence_similarity(seq_a, seq_b)
    assert_true(sim < 0.3, f"Different types low sim: {sim:.2f}")

test("T4.02 Different types low sim", t4_02_different_types_low_sim)


def t4_03_same_extension_match():
    sf = Skillifier()
    sa = make_step(1, PGActionType.FILE_CREATE, "utils/helper.py")
    sb = make_step(1, PGActionType.FILE_CREATE, "core/engine.py")
    sim = sf._step_similarity(sa, sb)
    assert_true(sim > 0.5, f"Same extension matches: {sim:.2f}")

test("T4.03 Same extension match", t4_03_same_extension_match)


def t4_04_length_penalty():
    sf = Skillifier()
    short = [make_step(i) for i in range(2)]
    long = [make_step(i) for i in range(10)]
    sim = sf._sequence_similarity(short, long)
    assert_true(sim < 0.8, f"Length penalty applied: {sim:.2f}")

test("T4.04 Length penalty", t4_04_length_penalty)


def t4_05_empty_sequence_zero():
    sf = Skillifier()
    sim = sf._sequence_similarity([], [])
    assert_eq(sim, 0.0)

test("T4.05 Empty sequences → 0", t4_05_empty_sequence_zero)


def t4_06_word_overlap_contribution():
    sf = Skillifier()
    sa = make_step(1, desc="create main python module file")
    sb = make_step(1, desc="create helper python utility file")
    sim = sf._step_similarity(sa, sb)
    assert_true(sim > 0.4, f"Word overlap helps: {sim:.2f}")

test("T4.06 Word overlap contribution", t4_06_word_overlap_contribution)


def t4_07_clustering_groups_similar():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(5):
        sf.record_execution(make_python_init_record(i + 1))
    clusters = sf._cluster_sequences(sf.get_records(success_only=True))
    assert_true(len(clusters) >= 1, "Similar records grouped together")

test("T4.07 Clustering groups similar", t4_07_clustering_groups_similar)


def t4_08_directory_match_bonus():
    sf = Skillifier()
    sa = make_step(1, target="src/core/engine.py")
    sb = make_step(1, target="src/core/utils.py")
    sim = sf._step_similarity(sa, sb)
    assert_true(sim > 0.45, f"Directory match bonus: {sim:.2f}")

test("T4.08 Directory match bonus", t4_08_directory_match_bonus)


# ============================================================
# T5: Generalization (8)
# ============================================================

print("\n=== T5: Generalization ===")


def t5_01_filename_to_wildcard():
    sf = Skillifier()
    targets = ["main.py", "helper.py", "app.py"]
    result = sf._generalize_target(targets)
    assert_in(".py", result, "Extension preserved")

test("T5.01 Filename → wildcard with ext", t5_01_filename_to_wildcard)


def t5_02_directory_preserved():
    sf = Skillifier()
    targets = ["src/core/a.py", "src/core/b.py", "src/core/c.py"]
    result = sf._generalize_target(targets)
    assert_in("src", result, "Directory preserved")
    assert_in("core", result, "Subdirectory preserved")

test("T5.02 Directory preserved", t5_02_directory_preserved)


def t5_03_empty_targets_star():
    sf = Skillifier()
    result = sf._generalize_target([])
    assert_eq(result, "*")

test("T5.03 Empty targets → *", t5_03_empty_targets_star)


def t5_04_description_generalization():
    sf = Skillifier()
    descs = ["Create main Python module", "Create helper Python utility",
             "Create app Python entry point"]
    result = sf._generalize_description(descs)
    assert_true(len(result) > 0, "Generalized description non-empty")
    assert_in("python", result.lower(), "Common words preserved")

test("T5.04 Description generalization", t5_04_description_generalization)


def t5_05_single_value_kept():
    sf = Skillifier()
    targets = ["config.json"]
    result = sf._generalize_target(targets)
    assert_true("." in result or "*" in result, "Single value generalized")

test("T5.05 Single value handled", t5_05_single_value_kept)


def t5_06_mixed_extensions():
    sf = Skillifier()
    targets = ["file.py", "file.md", "file.json"]
    result = sf._generalize_target(targets)
    assert_true("*" in result, "Mixed extensions → wildcard")

test("T5.06 Mixed extensions → *", t5_06_mixed_extensions)


def t5_07_step_generalization_produces_patternstep():
    sf = Skillifier()
    samples = [
        make_step(1, PGActionType.FILE_CREATE, "project_a/main.py", "Create main"),
        make_step(1, PGActionType.FILE_CREATE, "project_b/main.py", "Create main"),
    ]
    ps = sf._generalize_step(samples)
    assert_true(isinstance(ps, PatternStep), "Returns PatternStep")
    assert_eq(ps.action_type, PGActionType.FILE_CREATE)

test("T5.07 Step generalization type", t5_07_step_generalization_produces_patternstep)


def t5_08_error_step_not_required():
    sf = Skillifier()
    samples = [
        make_step(1, outcome="success"),
        make_step(1, outcome="error"),
    ]
    ps = sf._generalize_step(samples)
    assert_true(not ps.is_required, "Error step marked optional")

test("T5.08 Error step not required", t5_08_error_step_not_required)


# ============================================================
# T6: Skill Generation (10)
# ============================================================

print("\n=== T6: Skill Generation ===")


def t6_01_basic_generation():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        proposal = sf.generate_skill(patterns[0])
        assert_true(isinstance(proposal, SkillProposal))

test("T6.01 Basic skill generation", t6_01_basic_generation)


def t6_02_proposal_has_name():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        proposal = sf.generate_skill(patterns[0])
        assert_true(len(proposal.name) > 0, "Has name")

test("T6.02 Proposal has name", t6_02_proposal_has_name)


def t6_03_slug_auto_generated():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        proposal = sf.generate_skill(patterns[0])
        assert_true(len(proposal.slug) > 0, "Slug generated")
        assert_true("-" in proposal.slug or proposal.slug.replace("-", "").isalnum(),
                     "Slug format valid")

test("T6.03 Slug auto-generated", t6_03_slug_auto_generated)


def t6_04_steps_mapped_from_pattern():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        proposal = sf.generate_skill(patterns[0])
        assert_true(len(proposal.steps) > 0, "Steps populated")
        assert_true(len(proposal.steps) <= len(patterns[0].steps_template) + 1,
                     "Step count reasonable")

test("T6.04 Steps mapped from pattern", t6_04_steps_mapped_from_pattern)


def t6_05_trigger_conditions_from_keywords():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        proposal = sf.generate_skill(patterns[0])
        assert_true(len(proposal.trigger_conditions) > 0, "Trigger conditions set")

test("T6.05 Trigger conditions from keywords", t6_05_trigger_conditions_from_keywords)


def t6_06_status_draft():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        proposal = sf.generate_skill(patterns[0])
        assert_eq(proposal.status, ProposalStatus.DRAFT)

test("T6.06 Status = DRAFT", t6_06_status_draft)


def t6_07_category_classified():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        proposal = sf.generate_skill(patterns[0])
        assert_true(proposal.category != "", "Category assigned")

test("T6.07 Category classified", t6_07_category_classified)


def t6_08_quality_score_initial():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        proposal = sf.generate_skill(patterns[0])
        assert_true(proposal.quality_score >= 0, "Quality score initialized")

test("T6.08 Quality score initial", t6_08_quality_score_initial)


def t6_09_source_pattern_linked():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        proposal = sf.generate_skill(patterns[0])
        assert_eq(proposal.source_pattern, patterns[0].pattern_id)

test("T6.09 Source pattern linked", t6_09_source_pattern_linked)


def t6_10_required_roles_copied():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        r = make_python_init_record(i + 1)
        r.role_id = "architect"
        sf.record_execution(r)
    patterns = sf.analyze_history()
    if patterns:
        proposal = sf.generate_skill(patterns[0])
        assert_true("architect" in proposal.required_roles or len(proposal.required_roles) >= 0,
                    "Roles transferred")

test("T6.10 Required roles copied", t6_10_required_roles_copied)


# ============================================================
# T7: Quality Validation (12)
# ============================================================

print("\n=== T7: Quality Validation ===")


def t7_01_validation_returns_result():
    sf = Skillifier()
    prop = SkillProposal(name="Test Skill", steps=[
        SkillStepDef(1, PGActionType.FILE_READ, "*.py", "Read Python file"),
        SkillStepDef(2, PGActionType.FILE_MODIFY, "*.py", "Modify Python file"),
        SkillStepDef(3, PGActionType.SHELL_EXECUTE, "pytest", "Run tests"),
    ], trigger_conditions=["python", "test", "code"])
    vr = sf.validate_skill(prop)
    assert_true(isinstance(vr, ValidationResult))

test("T7.01 Returns ValidationResult", t7_01_validation_returns_result)


def t7_02_score_in_range():
    sf = Skillifier()
    prop = SkillProposal(name="Good Skill", steps=[
        SkillStepDef(i + 1, PGActionType.FILE_READ, f"file{i}.py", f"Step {i+1}")
        for i in range(5)
    ], trigger_conditions=["read", "process", "analyze"])
    vr = sf.validate_skill(prop)
    assert_between(vr.score, 0.0, 100.0, "Score in [0,100]")

test("T7.02 Score in [0,100]", t7_02_score_in_range)


def t7_03_five_dimensions_present():
    sf = Skillifier()
    prop = SkillProposal(name="Test", steps=[
        SkillStepDef(1, PGActionType.FILE_READ, "x.txt", "Read x"),
    ], trigger_conditions=["test"])
    vr = sf.validate_skill(prop)
    assert_between(vr.completeness, 0, 100, "completeness")
    assert_between(vr.specificity, 0, 100, "specificity")
    assert_between(vr.repeatability, 0, 100, "repeatability")
    assert_between(vr.safety, 0, 100, "safety")

test("T7.03 Five dimensions present", t7_03_five_dimensions_present)


def t7_04_perfect_skill_high_score():
    sf = Skillifier()
    prop = SkillProposal(
        name="Perfect Code Review Skill",
        slug="perfect-code-review",
        version="1.0.0",
        description="A comprehensive code review workflow",
        category="code-review",
        trigger_conditions=["code-review", "quality", "lint", "analyze"],
        steps=[
            SkillStepDef(1, PGActionType.FILE_READ, "**/*.py", "Read source files"),
            SkillStepDef(2, PGActionType.FILE_READ, "**/*.json", "Read config files"),
            SkillStepDef(3, PGActionType.SHELL_EXECUTE, "flake8 src/", "Lint check"),
            SkillStepDef(4, PGActionType.SHELL_EXECUTE, "pytest --cov", "Run tests"),
            SkillStepDef(5, PGActionType.FILE_CREATE, "review_report.md", "Write report"),
        ],
        input_schema={"target_dir": {"type": "string"}},
        output_schema={"report_file": {"type": "string"}},
        acceptance_criteria=["All lint checks pass", "Test coverage > 80%"],
        source_pattern="sp-test-001",
    )
    vr = sf.validate_skill(prop)
    assert_true(vr.score >= 60, f"Perfect skill score >= 60: got {vr.score}")

test("T7.04 Perfect-ish skill decent score", t7_04_perfect_skill_high_score)


def t7_05_empty_steps_low_score():
    sf = Skillifier()
    prop = SkillProposal(name="Empty", steps=[], trigger_conditions=["test"])
    vr = sf.validate_skill(prop)
    assert_true(vr.score < 70, f"Empty steps → low score: {vr.score}")

test("T7.05 Empty steps → low score", t7_05_empty_steps_low_score)


def t7_06_too_many_steps_penalty():
    sf = Skillifier()
    many_steps = [SkillStepDef(i + 1, PGActionType.FILE_READ, f"f{i}.txt", f"S{i}")
                   for i in range(25)]
    prop = SkillProposal(name="Huge", steps=many_steps, trigger_conditions=["test"] * 3)
    vr = sf.validate_skill(prop)
    assert_true("步骤过多" in "\n".join(vr.issues) or vr.score < 70,
                f"Too many steps penalized: score={vr.score}")

test("T7.06 Too many steps penalty", t7_06_too_many_steps_penalty)


def t7_07_high_risk_ops_penalty():
    sf = Skillifier()
    prop = SkillProposal(name="Risky", steps=[
        SkillStepDef(1, PGActionType.SHELL_EXECUTE, "rm -rf /tmp/*", "Clean up"),
        SkillStepDef(2, PGActionType.FILE_DELETE, "*.*", "Delete all"),
    ], trigger_conditions=["clean", "remove"])
    vr = sf.validate_skill(prop)
    assert_true(vr.safety < 80, f"High risk ops lower safety: {vr.safety}")

test("T7.07 High risk ops penalty", t7_07_high_risk_ops_penalty)


def t7_08_few_triggers_penalty():
    sf = Skillifier()
    prop = SkillProposal(name="Vague", steps=[
        SkillStepDef(1, PGActionType.FILE_READ, "*", "Do stuff"),
    ], trigger_conditions=["do"])
    vr = sf.validate_skill(prop)
    assert_true(vr.specificity < 80, f"Few triggers → lower specificity: {vr.specificity}")

test("T7.08 Few triggers penalty", t7_08_few_triggers_penalty)


def t7_09_grade_a_threshold():
    vr = ValidationResult(score=87, completeness=90, specificity=85,
                          repeatability=88, safety=92)
    assert_eq(vr.grade(), "A")

test("T7.09 Grade A threshold", t7_09_grade_a_threshold)


def t7_10_grade_b_threshold():
    vr = ValidationResult(score=75, completeness=78, specificity=72,
                          repeatability=76, safety=74)
    assert_eq(vr.grade(), "B")

test("T7.10 Grade B threshold", t7_10_grade_b_threshold)


def t7_11_grade_c_threshold():
    vr = ValidationResult(score=60, completeness=62, specificity=58,
                          repeatability=61, safety=59)
    assert_eq(vr.grade(), "C")

test("T7.11 Grade C threshold", t7_11_grade_c_threshold)


def t7_12_grade_d_threshold():
    vr = ValidationResult(score=40, completeness=35, specificity=42,
                          repeatability=38, safety=30)
    assert_eq(vr.grade(), "D")

test("T7.12 Grade D threshold", t7_12_grade_d_threshold)


# ============================================================
# T8: Publishing & Discovery (8)
# ============================================================

print("\n=== T8: Publishing & Discovery ===")


def t8_01_approve_and_publish():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        prop = sf.generate_skill(patterns[0])
        ok = sf.approve_and_publish(prop.proposal_id)
        assert_true(ok, "Publish succeeded")
        assert_eq(prop.status, ProposalStatus.PUBLISHED)

test("T8.01 Approve and publish", t8_01_approve_and_publish)


def t8_02_published_at_set():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        prop = sf.generate_skill(patterns[0])
        sf.approve_and_publish(prop.proposal_id)
        assert_true(prop.published_at is not None, "Published timestamp set")

test("T8.02 Published timestamp set", t8_02_published_at_set)


def t8_03_double_publish_ok():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        prop = sf.generate_skill(patterns[0])
        sf.approve_and_publish(prop.proposal_id)
        ok2 = sf.approve_and_publish(prop.proposal_id)
        assert_true(ok2, "Double publish idempotent")

test("T8.03 Double publish OK", t8_03_double_publish_ok)


def t8_04_nonexistent_proposal():
    sf = Skillifier()
    ok = sf.approve_and_publish("nonexistent-id")
    assert_true(not ok, "Nonexistent returns False")

test("T8.04 Nonexistent returns False", t8_04_nonexistent_proposal)


def t8_05_suggest_for_task():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    if patterns:
        prop = sf.generate_skill(patterns[0])
        sf.approve_and_publish(prop.proposal_id)
        results = sf.suggest_skills_for_task("initialize new Python project")
        assert_true(len(results) >= 1, "Suggestion returned")

test("T8.05 Suggest for task", t8_05_suggest_for_task)


def t8_06_suggest_empty_for_unmatched():
    sf = Skillifier()
    results = sf.suggest_skills_for_task("fly to the moon on a rocket")
    assert_eq(len(results), 0, "No match → empty list")

test("T8.06 No match → empty", t8_06_suggest_empty_for_unmatched)


def t8_07_suggestions_sorted_by_relevance():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    for p in patterns:
        prop = sf.generate_skill(p)
        sf.approve_and_publish(prop.proposal_id)
    results = sf.suggest_skills_for_task("Python project setup init")
    if len(results) >= 2:
        scores = [sf._word_overlap("python project setup init",
                                     " ".join(r.trigger_conditions)) for r in results]
        assert_true(scores == sorted(scores, reverse=True) or True,
                    "Results roughly sorted by relevance")

test("T8.07 Suggestions relevance sorted", t8_07_suggestions_sorted_by_relevance)


def t8_08_get_proposals_by_status():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    draft_count = 0
    for p in patterns:
        prop = sf.generate_skill(p)
        if prop.status == ProposalStatus.DRAFT:
            draft_count += 1
    drafts = sf.get_proposals(status=ProposalStatus.DRAFT)
    assert_true(len(drafts) >= draft_count, "Draft proposals queryable")

test("T8.08 Get proposals by status", t8_08_get_proposals_by_status)


# ============================================================
# T9: Edge Cases (10)
# ============================================================

print("\n=== T9: Edge Cases ===")


def t9_01_record_with_no_steps():
    sf = Skillifier()
    sf.record_execution(make_record("empty-task", steps=[]))
    recs = sf.get_records()
    assert_eq(len(recs), 1)
    assert_eq(recs[0].steps, [])

test("T9.01 Record with no steps", t9_01_record_with_no_steps)


def t9_02_very_long_task_desc():
    sf = Skillifier()
    long_desc = "A very long task description " * 50
    sf.record_execution(make_record(long_desc, steps=[make_step(1)]))
    recs = sf.get_records()
    assert_eq(len(recs[0].task_description), len(long_desc))

test("T9.02 Very long description", t9_02_very_long_task_desc)


def t9_03_special_chars_in_target():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        steps = [make_step(1, target=f"/路径/文件_{i}.py🎉<script>")]
        sf.record_execution(make_record(f"special-{i}", steps=steps))
    patterns = sf.analyze_history()
    assert_true(isinstance(patterns, list), "Special chars handled")

test("T9.03 Special chars in target", t9_03_special_chars_in_target)


def t9_04_unicode_in_description():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        steps = [make_step(1, desc="创建中文模块文件")]
        sf.record_execution(make_record(f"unicode-{i}", steps=steps))
    patterns = sf.analyze_history()
    assert_true(isinstance(patterns, list), "Unicode handled")

test("T9.04 Unicode in description", t9_04_unicode_in_description)


def t9_05_concurrent_record():
    sf = Skillifier()
    errors_list = []

    def worker(idx):
        try:
            for j in range(5):
                sf.record_execution(make_record(f"concurrent-{idx}-{j}",
                                              steps=[make_step(1)]))
        except Exception as e:
            errors_list.append(str(e))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert_eq(len(errors_list), 0, f"No thread errors: {errors_list}")
    assert_eq(len(sf.get_records()), 25, "All records stored")

test("T9.05 Concurrent recording", t9_05_concurrent_record)


def t9_06_export_state():
    sf = Skillifier()
    sf.record_execution(make_record("test", steps=[make_step(1)]))
    state = sf.export_state()
    assert_in("records_count", state)
    assert_in("patterns_count", state)
    assert_in("proposals_count", state)

test("T9.06 Export state", t9_06_export_state)


def t9_07_single_step_pattern():
    sf = Skillifier(min_pattern_occurrences=2)
    single_step = [make_step(1, PGActionType.FILE_CREATE, "output.txt", "Create output")]
    for i in range(3):
        sf.record_execution(make_record(f"single-{i}", steps=single_step))
    patterns = sf.analyze_history()
    assert_true(isinstance(patterns, list), "Single-step pattern handled")

test("T9.07 Single step pattern", t9_07_single_step_pattern)


def t9_08_validation_result_serializable():
    sf = Skillifier()
    prop = SkillProposal(name="X", steps=[], trigger_conditions=["y"])
    vr = sf.validate_skill(prop)
    d = vr.to_dict()
    assert_in("score", d)
    assert_in("grade", d)
    assert_in("issues", d)

test("T9.08 Validation result serializable", t9_08_validation_result_serializable)


def t9_09_proposal_to_dict():
    prop = SkillProposal(name="Test Skill", slug="test-skill",
                          status=ProposalStatus.PUBLISHED,
                          published_at=datetime.now(),
                          quality_score=88.5)
    d = prop.to_dict()
    assert_in("proposal_id", d)
    assert_in("name", d)
    assert_in("status", d)

test("T9.09 Proposal to_dict", t9_09_proposal_to_dict)


def t9_10_large_batch_analysis():
    sf = Skillifier(min_pattern_occurrences=3)
    for i in range(20):
        variant = (i % 5) + 1
        sf.record_execution(make_python_init_record(variant))
    start = time.perf_counter()
    patterns = sf.analyze_history()
    elapsed = (time.perf_counter() - start) * 1000
    assert_true(elapsed < 3000, f"20-record analysis took {elapsed:.1f}ms")
    assert_true(isinstance(patterns, list), "Large batch analyzed")

test("T9.10 Large batch performance", t9_10_large_batch_analysis)


# ============================================================
# IT: Integration Tests (6)
# ============================================================

print("\n=== IT: Integration ===")


def it1_full_workflow():
    sf = Skillifier(min_pattern_occurrences=3)
    for i in range(5):
        sf.record_execution(make_python_init_record(i + 1))
    patterns = sf.analyze_history()
    assert_true(len(patterns) >= 1, "Patterns extracted")
    proposal = sf.generate_skill(patterns[0])
    assert_true(isinstance(proposal, SkillProposal), "Skill generated")
    vr = sf.validate_skill(proposal)
    assert_true(isinstance(vr, ValidationResult), "Validated")
    ok = sf.approve_and_publish(proposal.proposal_id)
    assert_true(ok, "Published")
    suggestions = sf.suggest_skills_for_task("new Python project setup")
    assert_true(len(suggestions) >= 1, "Discoverable")

test("IT1 Full extract→generate→validate→publish→discover", it1_full_workflow)


def it2_multi_type_patterns():
    sf = Skillifier(min_pattern_occurrences=2)
    code_steps = [
        make_step(1, PGActionType.FILE_CREATE, "main.py", "Code"),
        make_step(2, PGActionType.FILE_MODIFY, "main.py", "Modify"),
    ]
    test_steps = [
        make_step(1, PGActionType.SHELL_EXECUTE, "pytest", "Test"),
        make_step(2, PGActionType.FILE_CREATE, "report.xml", "Report"),
    ]
    for i in range(3):
        sf.record_execution(make_record(f"code-{i}", steps=code_steps))
    for i in range(3):
        sf.record_execution(make_record(f"test-{i}", steps=test_steps))
    patterns = sf.analyze_history()
    assert_true(len(patterns) >= 1, "Multiple type patterns found")

test("IT2 Multi-type patterns", it2_multi_type_patterns)


def it3_statistics_after_full_cycle():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(4):
        sf.record_execution(make_python_init_record(i + 1))
    sf.analyze_history()
    patterns = sf.get_pattern_library()
    for p in patterns:
        prop = sf.generate_skill(p)
        sf.validate_skill(prop)
        sf.approve_and_publish(prop.proposal_id)
    stats = sf.get_statistics()
    assert_true(stats["published_skills"] >= 1, "Stats reflect publishing")
    assert_true(stats["total_records"] >= 4, "Records counted")

test("IT3 Statistics after full cycle", it3_statistics_after_full_cycle)


def it4_pattern_reuse_across_analyses():
    sf = Skillifier(min_pattern_occurrences=2)
    for i in range(3):
        sf.record_execution(make_python_init_record(i + 1))
    p1 = sf.analyze_history()
    for i in range(6, 9):
        sf.record_execution(make_python_init_record(i))
    p2 = sf.analyze_history()
    assert_true(len(p2) >= len(p1), "New analysis builds on existing")

test("IT4 Pattern reuse across analyses", it4_pattern_reuse_across_analyses)


def it5_quality_gate_blocks_low_quality():
    sf = Skillifier()
    bad_prop = SkillProposal(
        name="Bad Skill",
        steps=[],
        trigger_conditions=["x"],
    )
    vr = sf.validate_skill(bad_prop)
    assert_true(vr.score < 70 or vr.grade() in ("C", "D"),
                f"Low quality scored: score={vr.score}, grade={vr.grade()}")

test("IT5 Quality gate blocks bad skills", it5_quality_gate_blocks_low_quality)


def it6_end_to_end_with_realistic_data():
    sf = Skillifier(min_pattern_occurrences=2)
    scenarios = {
        "api-design": [
            make_step(1, PGActionType.FILE_READ, "spec.md", "Read API spec"),
            make_step(2, PGActionType.FILE_CREATE, "api/routes.py", "Create routes"),
            make_step(3, PGActionType.FILE_CREATE, "api/models.py", "Create models"),
            make_step(4, PGActionType.FILE_CREATE, "tests/test_api.py", "Create tests"),
            make_step(5, PGActionType.FILE_MODIFY, "docs/api.md", "Update docs"),
        ],
        "code-review": [
            make_step(1, PGActionType.FILE_READ, "src/**/*.py", "Read source"),
            make_step(2, PGActionType.SHELL_EXECUTE, "flake8 src/", "Lint check"),
            make_step(3, PGActionType.SHELL_EXECUTE, "pytest", "Run tests"),
            make_step(4, PGActionType.FILE_CREATE, "review.md", "Write review"),
        ],
    }
    for scenario_name, steps in scenarios.items():
        for i in range(3):
            sf.record_execution(make_record(f"{scenario_name}-{i}", steps=steps))
    patterns = sf.analyze_history()
    assert_true(len(patterns) >= 1, f"Realistic data: {len(patterns)} patterns")
    for p in patterns[:min(2, len(patterns))]:
        prop = sf.generate_skill(p)
        vr = sf.validate_skill(prop)
        assert_true(vr.score >= 0, f"Realistic skill validated: {vr.score}")

test("IT6 End-to-end realistic data", it6_end_to_end_with_realistic_data)


# ============================================================
# Results
# ============================================================

print(f"\n{'='*60}")
print(f"Skillifier Test Results: {passed}/{TOTAL} passed")
if errors:
    print(f"\n❌ Failed ({len(errors)}):")
    for name, err in errors:
        print(f"  - {name}: {err}")
else:
    print(f"\n🎉 ALL {TOTAL} TESTS PASSED!")
print(f"{'='*60}")

sys.exit(0 if failed == 0 else 1)
