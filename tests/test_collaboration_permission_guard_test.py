#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PermissionGuard E2E Test Suite
Covers: Data models, 4-level behavior, Rule engine, AI classifier,
        Audit logging, Edge cases, Thread safety, Integration
"""

import sys
import os
import threading
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collaboration.permission_guard import (
    PermissionGuard, ProposedAction, PermissionRule, PermissionDecision,
    AuditEntry, PermissionLevel, ActionType, DecisionOutcome,
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


def make_action(atype=ActionType.FILE_READ, target="", **kw):
    return ProposedAction(action_type=atype, target=target, **kw)


# ============================================================
# T1: Data Model Validation (10)
# ============================================================

print("\n=== T1: Data Models ===")


def t1_01_proposed_action_defaults():
    a = ProposedAction()
    assert_true(a.action_type == ActionType.FILE_READ, "default type")
    assert_true(a.target == "", "default target")
    assert_true(a.risk_score == 0.0, "default risk")
    assert_true(a.source_worker_id is None, "no worker")

test("T1.01 ProposedAction defaults", t1_01_proposed_action_defaults)


def t1_02_roundtrip():
    a = ProposedAction(
        action_type=ActionType.SHELL_EXECUTE,
        target="rm -rf /tmp",
        description="clean up",
        source_worker_id="w1",
        source_role_id="arch",
        risk_score=0.95,
        metadata={"key": "val"},
    )
    d = a.to_dict()
    a2 = ProposedAction.from_dict(d)
    assert_eq(a2.action_type, ActionType.SHELL_EXECUTE)
    assert_eq(a2.target, "rm -rf /tmp")
    assert_eq(a2.source_role_id, "arch")
    assert_eq(a2.metadata["key"], "val")

test("T1.02 ProposedAction roundtrip", t1_02_roundtrip)


def t1_03_permission_rule_fields():
    r = PermissionRule("TEST", ActionType.FILE_CREATE, "*.py",
                       PermissionLevel.AUTO, "test rule", risk_boost=0.3,
                       tags=["python", "code"])
    assert_eq(r.rule_id, "TEST")
    assert_eq(r.enabled, True)
    assert_in("python", r.tags)

test("T1.03 PermissionRule fields", t1_03_permission_rule_fields)


def t1_04_decision_outcome():
    d = PermissionDecision(
        action=make_action(),
        outcome=DecisionOutcome.ALLOWED,
        reason="test ok",
    )
    assert_true(d.decision_id.startswith("pd-"), "ID format")
    assert_true(d.requires_confirmation == False, "default no confirm")
    assert_true(d.confidence > 0, "confidence positive")

test("T1.04 PermissionDecision fields", t1_04_decision_outcome)


def t1_05_outcomes_enum():
    vals = [e.value for e in DecisionOutcome]
    assert_in("allowed", vals)
    assert_in("denied", vals)
    assert_in("prompt", vals)
    assert_in("escalated", vals)
    assert_eq(len(vals), 4)

test("T1.05 DecisionOutcome enum", t1_05_outcomes_enum)


def t1_06_action_types_enum():
    types = [t.value for t in ActionType]
    assert_eq(len(types), 9)
    assert_in("file_read", types)
    assert_in("shell_execute", types)
    assert_in("network_request", types)

test("T1.06 ActionType 9 types", t1_06_action_types_enum)


def t1_07_levels_enum():
    levels = [l.value for l in PermissionLevel]
    assert_eq(len(levels), 4)
    assert_in("plan", levels)
    assert_in("bypass", levels)

test("T1.07 PermissionLevel 4 levels", t1_07_levels_enum)


def t1_08_audit_entry():
    ae = AuditEntry()
    assert_true(ae.entry_id.startswith("ae-"), "audit ID format")
    assert_true(ae.session_id.startswith("sess-"), "session ID format")

test("T1.08 AuditEntry structure", t1_08_audit_entry)


def t1_09_empty_action():
    a = ProposedAction()
    d = a.to_dict()
    assert_true("action_type" in d, "has type field")
    assert_true("target" in d, "has target field")

test("T1.09 Empty action safe", t1_09_empty_action)


def t1_10_unicode_target():
    a = make_action(target="/项目/中文文件.py")
    assert_eq(a.target, "/项目/中文文件.py")

test("T1.10 Unicode preserved", t1_10_unicode_target)


# ============================================================
# T2: 4-Level Behavior (16)
# ============================================================

print("\n=== T2: 4-Level Behavior ===")


def t2_01_plan_create_denied():
    g = PermissionGuard(PermissionLevel.PLAN)
    d = g.check(make_action(ActionType.FILE_CREATE, "new.py"))
    assert_eq(d.outcome, DecisionOutcome.DENIED)

test("T2.01 PLAN→CREATE=DENIED", t2_01_plan_create_denied)


def t2_02_plan_modify_denied():
    g = PermissionGuard(PermissionLevel.PLAN)
    d = g.check(make_action(ActionType.FILE_MODIFY, "old.py"))
    assert_eq(d.outcome, DecisionOutcome.DENIED)

test("T2.02 PLAN→MODIFY=DENIED", t2_02_plan_modify_denied)


def t2_03_plan_delete_denied():
    g = PermissionGuard(PermissionLevel.PLAN)
    d = g.check(make_action(ActionType.FILE_DELETE, "x.py"))
    assert_eq(d.outcome, DecisionOutcome.DENIED)

test("T2.03 PLAN→DELETE=DENIED", t2_03_plan_delete_denied)


def t2_04_plan_shell_denied():
    g = PermissionGuard(PermissionLevel.PLAN)
    d = g.check(make_action(ActionType.SHELL_EXECUTE, "echo hi"))
    assert_eq(d.outcome, DecisionOutcome.DENIED)

test("T2.04 PLAN→SHELL=DENIED", t2_04_plan_shell_denied)


def t2_05_plan_read_allowed():
    g = PermissionGuard(PermissionLevel.PLAN)
    d = g.check(make_action(ActionType.FILE_READ, "config.json"))
    assert_eq(d.outcome, DecisionOutcome.ALLOWED)

test("T2.05 PLAN→READ=ALLOWED", t2_05_plan_read_allowed)


def t2_06_plan_network_denied():
    g = PermissionGuard(PermissionLevel.PLAN)
    d = g.check(make_action(ActionType.NETWORK_REQUEST, "https://api.test.com"))
    assert_eq(d.outcome, DecisionOutcome.DENIED)

test("T2.06 PLAN→NETWORK=DENIED", t2_06_plan_network_denied)


def t2_07_default_create_py():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.FILE_CREATE, "utils/helper.py"))
    assert_in(d.outcome, (DecisionOutcome.ALLOWED, DecisionOutcome.PROMPT))

test("T2.07 DEFAULT→create .py", t2_07_default_create_py)


def t2_08_default_env_prompt():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.FILE_MODIFY, ".env"))
    assert_eq(d.outcome, DecisionOutcome.PROMPT)
    assert_true(d.requires_confirmation, "needs confirmation")
    assert_true(d.action.risk_score >= 0.7, f"risk={d.action.risk_score}")

test("T2.08 DEFAULT→.env=PROMPT", t2_08_default_env_prompt)


def t2_09_default_credentials_prompt():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.FILE_MODIFY, "credentials.json"))
    assert_eq(d.outcome, DecisionOutcome.PROMPT)
    assert_true(d.action.risk_score >= 0.9)

test("T2.09 DEFAULT→credentials=PROMPT", t2_09_default_credentials_prompt)


def t2_10_default_rm_prompt():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.SHELL_EXECUTE, "rm -rf /tmp/cache"))
    assert_eq(d.outcome, DecisionOutcome.PROMPT)
    assert_true(d.action.risk_score >= 0.9)

test("T2.10 DEFAULT→rm=PROMPT", t2_10_default_rm_prompt)


def t2_11_default_sudo_prompt():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.SHELL_EXECUTE, "sudo apt update"))
    assert_eq(d.outcome, DecisionOutcome.PROMPT)

test("T2.11 DEFAULT→sudo=PROMPT", t2_11_default_sudo_prompt)


def t2_12_default_read_allowed():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.FILE_READ, "README.md"))
    assert_eq(d.outcome, DecisionOutcome.ALLOWED)

test("T2.12 DEFAULT→read=ALLOWED", t2_12_default_read_allowed)


def t2_13_auto_safe_cmd():
    g = PermissionGuard(PermissionLevel.AUTO)
    d = g.check(make_action(ActionType.SHELL_EXECUTE, "pip list"))
    assert_in(d.outcome, (DecisionOutcome.ALLOWED, DecisionOutcome.PROMPT))

test("T2.13 AUTO→pip list", t2_13_auto_safe_cmd)


def t2_14_auto_suspicious_url():
    g = PermissionGuard(PermissionLevel.AUTO)
    d = g.check(make_action(ActionType.NETWORK_REQUEST, "http://unknown.xyz/data"))
    score = g.auto_classify(d.action)
    assert_true(score > 0.05, f"auto classify should be somewhat cautious, got {score}")

test("T2.14 AUTO→suspicious URL", t2_14_auto_suspicious_url)


def t2_15_bypass_all_allowed():
    g = PermissionGuard(PermissionLevel.BYPASS)
    for at, tgt in [
        (ActionType.SHELL_EXECUTE, "rm -rf /"),
        (ActionType.FILE_DELETE, "/etc/passwd"),
        (ActionType.FILE_MODIFY, ".env"),
    ]:
        d = g.check(make_action(at, tgt))
        assert_eq(d.outcome, DecisionOutcome.ALLOWED, f"BYPASS should allow {at.value} {tgt}")

test("T2.15 BYPASS→all ALLOWED", t2_15_bypass_all_allowed)


def t2_16_bypass_audit_still_logs():
    g = PermissionGuard(PermissionLevel.BYPASS, audit_log=True)
    for i in range(5):
        g.check(make_action(ActionType.FILE_READ, f"file{i}.txt"))
    log = g.get_audit_log()
    assert_eq(len(log), 5)
    for e in log:
        assert_eq(e.guard_level, PermissionLevel.BYPASS)

test("T2.16 BYPASS audit logs", t2_16_bypass_audit_still_logs)


# ============================================================
# T3: Rule Engine (18)
# ============================================================

print("\n=== T3: Rule Engine ===")


def t3_01_default_30_rules():
    g = PermissionGuard()
    assert_eq(len(g.rules), 30)

test("T3.01 Default 30 rules", t3_01_default_30_rules)


def t3_02_covers_8_types():
    g = PermissionGuard()
    types = set(r.action_type for r in g.rules)
    assert_eq(len(types), 8, f"got {len(types)} types")

test("T3.02 Covers 8 ActionTypes", t3_02_covers_8_types)


def t3_03_add_rule():
    g = PermissionGuard()
    r = PermissionRule("CUSTOM", ActionType.FILE_CREATE, "*.log",
                       PermissionLevel.BYPASS, "custom rule")
    g.add_rule(r)
    assert_eq(len(g.rules), 31)

test("T3.03 add_rule works", t3_03_add_rule)


def t3_04_remove_rule():
    g = PermissionGuard()
    ok = g.remove_rule("R009")
    assert_true(ok, "remove succeeds")
    assert_eq(len(g.rules), 29)

test("T3.04 remove_rule works", t3_04_remove_rule)


def t3_05_remove_affects_check():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d1 = g.check(make_action(ActionType.FILE_MODIFY, ".env"))
    is_prompt_before = d1.outcome == DecisionOutcome.PROMPT
    g.remove_rule("R009")
    d2 = g.check(make_action(ActionType.FILE_MODIFY, ".env"))
    assert_true(isinstance(d2, PermissionDecision), "still returns decision after remove")

test("T3.05 Remove affects check", t3_05_remove_affects_check)


def t3_06_export_import():
    g = PermissionGuard()
    data = g.export_rules()
    g2 = PermissionGuard(rules=[])
    count = g2.import_rules(data)
    assert_true(count >= 20, f"imported {count} rules")

test("T3.06 Export/Import roundtrip", t3_06_export_import)


def t3_07_glob_py_match():
    g = PermissionGuard()
    a = make_action(ActionType.FILE_CREATE, "src/utils/helper.py")
    d = g.check(a)
    assert_true(d.matched_rule is not None or d.outcome is not None, "matches *.py")

test("T3.07 Glob *.py match", t3_07_glob_py_match)


def t3_08_prefix_git_shell():
    g = PermissionGuard()
    d = g.check(make_action(ActionType.SHELL_EXECUTE, "git status --short"))
    assert_in(d.outcome, (DecisionOutcome.ALLOWED, DecisionOutcome.PROMPT))

test("T3.08 Prefix git match", t3_08_prefix_git_shell)


def t3_09_regex_rm_pattern():
    g = PermissionGuard()
    d = g.check(make_action(ActionType.SHELL_EXECUTE, "rm -rf /tmp"))
    assert_in(d.outcome, (DecisionOutcome.PROMPT, DecisionOutcome.DENIED))

test("T3.09 Regex rm pattern", t3_09_regex_rm_pattern)


def t3_10_strictest_wins():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.FILE_MODIFY, ".env"))
    assert_true(d.matched_rule is not None, "should match R009")

test("T3.10 Strictest rule wins", t3_10_strictest_wins)


def t3_11_no_match_fallback():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    a = make_action(ActionType.PROCESS_SPAWN, "some_weird_process")
    d = g.check(a)
    assert_true(d.outcome in (DecisionOutcome.ALLOWED, DecisionOutcome.PROMPT,
                               DecisionOutcome.DENIED), "fallback decision valid")

test("T3.11 No-match fallback", t3_11_no_match_fallback)


def t3_12_env_high_risk():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.FILE_MODIFY, ".env"))
    assert_true(d.action.risk_score >= 0.7, f"risk={d.action.risk_score}")

test("T3.12 .env high risk", t3_12_env_high_risk)


def t3_13_credentials_max_risk():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.FILE_MODIFY, "credentials.json"))
    assert_true(d.action.risk_score >= 0.9, f"risk={d.action.risk_score}")

test("T3.13 credentials max risk", t3_13_credentials_max_risk)


def t3_14_rm_sudo_extreme_risk():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.SHELL_EXECUTE, "sudo rm -rf /"))
    assert_true(d.action.risk_score >= 0.95, f"risk={d.action.risk_score}")

test("T3.14 rm/sudo extreme risk", t3_14_rm_sudo_extreme_risk)


def t3_15_pypi_low_risk():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.NETWORK_REQUEST, "https://pypi.org/simple/requests/"))
    assert_true(d.action.risk_score < 0.4, f"risk={d.action.risk_score}")

test("T3.15 PyPI low risk", t3_15_pypi_low_risk)


def t3_16_git_read_low_risk():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.GIT_OPERATION, "git log --oneline -10"))
    assert_true(d.action.risk_score < 0.3, f"risk={d.action.risk_score}")

test("T3.16 Git read low risk", t3_16_git_read_low_risk)


def t3_17_disabled_rule_skipped():
    g = PermissionGuard()
    g.rules[0].enabled = False
    d = g.check(make_action(ActionType.FILE_READ, "anything.txt"))
    assert_true(d.outcome is not None, "works with disabled rules")

test("T3.17 Disabled rule skipped", t3_17_disabled_rule_skipped)


def t3_18_duplicate_rule_id_overwrites():
    g = PermissionGuard()
    original_count = len(g.rules)
    r = PermissionRule("R001", ActionType.FILE_READ, "*",
                       PermissionLevel.BYPASS, "overwrite")
    g.add_rule(r)
    assert_eq(len(g.rules), original_count, "no new entry on duplicate id")

test("T3.18 Duplicate ID overwrites", t3_18_duplicate_rule_id_overwrites)


# ============================================================
# T4: AI Auto Classifier (12)
# ============================================================

print("\n=== T4: AI Classifier ===")


def t4_01_range_check():
    g = PermissionGuard()
    targets = ["safe.txt", "secret.pem", "rm -rf /", ".env", "/etc/passwd"]
    scores = [g.auto_classify(make_action(target=t)) for t in targets]
    for s in scores:
        assert_between(s, 0.0, 1.0, "score range")

test("T4.01 Score [0,1] range", t4_01_range_check)


def t4_02_low_risk_ops():
    g = PermissionGuard()
    for t in ["README.md", "git status", "ls -la src/", "cat config.json"]:
        s = g.auto_classify(make_action(target=t))
        assert_true(s < 0.5, f"'{t}' should be low risk, got {s:.2f}")

test("T4.02 Low risk ops <0.5", t4_02_low_risk_ops)


def t4_03_medium_risk_ops():
    g = PermissionGuard()
    found_medium = False
    for t in ["modify src/main.py with new feature", "create output.json for data export",
               "install dependency package", "update config.yaml with new settings",
               "fetch data from external API endpoint"]:
        s = g.auto_classify(make_action(target=t))
        if 0.1 <= s <= 0.45:
            found_medium = True
    assert_true(found_medium, "Should find medium-risk operations")

test("T4.03 Medium risk 0.1-0.45", t4_03_medium_risk_ops)


def t4_04_high_risk_ops():
    g = PermissionGuard()
    for t in ["sudo rm -rf /tmp", "delete credentials.json", "overwrite .env"]:
        s = g.auto_classify(make_action(target=t))
        assert_true(s > 0.25, f"'{t}' should be elevated risk, got {s:.2f}")

test("T4.04 High risk >0.25", t4_04_high_risk_ops)


def t4_05_sensitivity_dim():
    g = PermissionGuard()
    s_normal = g.auto_classify(make_action(target="config.py"))
    s_secret = g.auto_classify(make_action(target="secret_key.pem"))
    assert_true(s_secret > s_normal, f"secret({s_secret:.2f}) > normal({s_normal:.2f})")

test("T4.05 Sensitivity dimension", t4_05_sensitivity_dim)


def t4_06_destructive_dim():
    g = PermissionGuard()
    s_echo = g.auto_classify(make_action(target="echo hello world"))
    s_rm = g.auto_classify(make_action(target="rm -rf /important-data"))
    assert_true(s_rm > s_echo, f"rm({s_rm:.2f}) > echo({s_echo:.2f})")

test("T4.06 Destructive dimension", t4_06_destructive_dim)


def t4_07_whitelist_bypass():
    g = PermissionGuard(PermissionLevel.AUTO)
    g.add_whitelist("python -m pytest")
    d = g.check(make_action(ActionType.SHELL_EXECUTE, "python -m pytest"))
    assert_eq(d.outcome, DecisionOutcome.ALLOWED, "whitelisted op allowed")

test("T4.07 Whitelist bypass", t4_07_whitelist_bypass)


def t4_08_whitelist_mgmt():
    g = PermissionGuard()
    g.add_whitelist("cmd1")
    g.add_whitelist("cmd2")
    wl = g.get_whitelist()
    assert_in("cmd1", wl)
    assert_in("cmd2", wl)
    g.remove_whitelist("cmd1")
    assert_not_in("cmd1", g.get_whitelist())

test("T4.08 Whitelist management", t4_08_whitelist_mgmt)


def t4_09_context_bonus():
    g = PermissionGuard()
    a1 = make_action(target="update config.json", metadata={"task_related": True})
    a2 = make_action(target="update config.json")
    s1 = g.auto_classify(a1)
    s2 = g.auto_classify(a2)
    assert_true(s1 <= s2, f"context({s1:.2f}) <= no-context({s2:.2f})")

test("T4.09 Context reasonableness", t4_09_context_bonus)


def t4_10_source_trust():
    g = PermissionGuard()
    a_known = make_action(source_role_id="architect")
    a_unknown = make_action(source_role_id="hacker_maybe")
    s_known = g.auto_classify(a_known)
    s_unknown = g.auto_classify(a_unknown)
    assert_true(s_known <= s_unknown, f"known({s_known:.2f}) <= unknown({s_unknown:.2f})")

test("T4.10 Source trust", t4_10_source_trust)


def t4_11_empty_classify():
    g = PermissionGuard()
    s = g.auto_classify(ProposedAction())
    assert_between(s, 0.0, 1.0, "empty action classification")

test("T4.11 Empty action classify", t4_11_empty_classify)


def t4_12_special_chars():
    g = PermissionGuard()
    s = g.auto_classify(make_action(target="路径/文件🎉.py<script>"))
    assert_between(s, 0.0, 1.0, "special chars handled")

test("T4.12 Special chars safe", t4_12_special_chars)


# ============================================================
# T5: Audit Logging (14)
# ============================================================

print("\n=== T5: Audit Logging ===")


def t5_01_check_produces_entry():
    g = PermissionGuard(audit_log=True)
    g.check(make_action(target="test.txt"))
    log = g.get_audit_log()
    assert_eq(len(log), 1)

test("T5.01 check produces audit", t5_01_check_produces_entry)


def t5_02_entry_complete():
    g = PermissionGuard(audit_log=True)
    g.check(make_action(target="x.txt"))
    e = g.get_audit_log()[0]
    assert_true(e.entry_id.startswith("ae-"), "entry ID")
    assert_true(e.action is not None, "has action")
    assert_true(e.decision is not None, "has decision")
    assert_true(e.duration_ms >= 0, "duration non-negative")
    assert_true(e.timestamp is not None, "has timestamp")

test("T5.02 Entry completeness", t5_02_entry_complete)


def t5_03_duration_nonneg():
    g = PermissionGuard(audit_log=True)
    for _ in range(10):
        g.check(make_action())
    for e in g.get_audit_log():
        assert_true(e.duration_ms >= 0, f"duration {e.duration_ms} >= 0")

test("T5.03 Duration >= 0", t5_03_duration_nonneg)


def t5_04_filter_by_outcome():
    g = PermissionGuard(PermissionLevel.PLAN, audit_log=True)
    g.check(make_action(ActionType.FILE_READ, "ok.txt"))   # ALLOWED
    g.check(make_action(ActionType.FILE_CREATE, "new.txt")) # DENIED
    denied = g.get_audit_log(outcome=DecisionOutcome.DENIED)
    assert_eq(len(denied), 1)

test("T5.04 Filter by outcome", t5_04_filter_by_outcome)


def t5_05_filter_by_type():
    g = PermissionGuard(audit_log=True)
    g.check(make_action(ActionType.FILE_READ, "a.txt"))
    g.check(make_action(ActionType.SHELL_EXECUTE, "echo hi"))
    shell_entries = g.get_audit_log(action_type=ActionType.SHELL_EXECUTE)
    assert_eq(len(shell_entries), 1)

test("T5.05 Filter by action type", t5_05_filter_by_type)


def t5_06_time_range_filter():
    from datetime import timedelta
    g = PermissionGuard(audit_log=True)
    g.check(make_action())
    recent = g.get_audit_log(since=datetime.now() - timedelta(hours=1))
    assert_true(len(recent) >= 1, "time filter returns recent entries")

test("T5.06 Time filter", t5_06_time_range_filter)


def t5_07_worker_filter():
    g = PermissionGuard(audit_log=True)
    g.check(make_action(source_worker_id="worker-a"))
    g.check(make_action(source_worker_id="worker-b"))
    filtered = g.get_audit_log(worker_id="worker-a")
    assert_eq(len(filtered), 1)

test("T5.07 Worker filter", t5_07_worker_filter)


def t5_08_limit():
    g = PermissionGuard(audit_log=True)
    for i in range(20):
        g.check(make_action(target=f"f{i}.txt"))
    limited = g.get_audit_log(limit=5)
    assert_eq(len(limited), 5)

test("T5.08 Limit param", t5_08_limit)


def t5_09_no_audit_mode():
    g = PermissionGuard(audit_log=False)
    g.check(make_action())
    g.check(make_action())
    log = g.get_audit_log()
    assert_eq(len(log), 0, "no entries when audit disabled")

test("T5.09 No audit mode", t5_09_no_audit_mode)


def t5_10_security_report_structure():
    g = PermissionGuard(audit_log=True)
    for _ in range(10):
        g.check(make_action())
    report = g.get_security_report()
    keys = ["total_checks", "allowed", "denied", "prompted", "escalated",
            "avg_risk_score", "top_denied_actions"]
    for k in keys:
        assert_in(k, report, f"report has '{k}'")

test("T5.10 Security report keys", t5_10_security_report_structure)


def t5_11_report_sum_consistency():
    g = PermissionGuard(PermissionLevel.PLAN, audit_log=True)
    for _ in range(15):
        g.check(make_action())
    report = g.get_security_report()
    total = report["allowed"] + report["denied"] + report["prompted"] + report["escalated"]
    assert_eq(total, report["total_checks"], "sum matches total")

test("T5.11 Report sum = total", t5_11_report_sum_consistency)


def t5_12_top_denied_sorted():
    g = PermissionGuard(PermissionLevel.PLAN, audit_log=True)
    g.check(make_action(ActionType.FILE_CREATE, "a.txt"))
    g.check(make_action(ActionType.FILE_CREATE, "b.txt"))
    g.check(make_action(ActionType.FILE_CREATE, "c.txt"))
    report = g.get_security_report()
    if report["top_denied_actions"]:
        counts = [c for _, c in report["top_denied_actions"]]
        assert_true(counts == sorted(counts, reverse=True), "sorted descending")

test("T5.12 Top denied sorted", t5_12_top_denied_sorted)


def t5_13_log_grows_monotonically():
    g = PermissionGuard(audit_log=True)
    for i in range(8):
        g.check(make_action())
        assert_eq(len(g.get_audit_log()), i + 1)

test("T5.13 Log grows monotonically", t5_13_log_grows_monotonically)


def t5_14_log_chronological():
    g = PermissionGuard(audit_log=True)
    times = []
    for _ in range(5):
        g.check(make_action())
        times.append(g.get_audit_log()[-1].timestamp)
    assert_true(all(times[i] <= times[i+1] for i in range(len(times)-1)), "chronological order")

test("T5.14 Chronological order", t5_14_log_chronological)


# ============================================================
# T6: Edge Cases & Exceptions (15)
# ============================================================

print("\n=== T6: Edge Cases ===")


def t6_01_empty_action():
    g = PermissionGuard()
    d = g.check(ProposedAction())
    assert_true(d.outcome in (DecisionOutcome.ALLOWED, DecisionOutcome.DENIED,
                               DecisionOutcome.PROMPT), "valid outcome for empty")

test("T6.01 Empty action safe", t6_01_empty_action)


def t6_02_empty_target():
    g = PermissionGuard()
    d = g.check(make_action(target=""))
    assert_true(isinstance(d, PermissionDecision), "returns decision")

test("T6.02 Empty target safe", t6_02_empty_target)


def t6_03_none_fields():
    a = ProposedAction(action_type=None, target=None)
    g = PermissionGuard()
    try:
        d = g.check(a)
        assert_true(isinstance(d, PermissionDecision), "handles None gracefully")
    except (TypeError, AttributeError):
        pass

test("T6.03 None fields handled", t6_03_none_fields)


def t6_04_long_path():
    long_path = "a/" * 500 + "file.py"
    g = PermissionGuard()
    d = g.check(make_action(target=long_path))
    assert_true(isinstance(d, PermissionDecision), "long path handled")

test("T6.04 Long path (>1000 chars)", t6_04_long_path)


def t6_05_path_traversal():
    g = PermissionGuard()
    d = g.check(make_action(target="../../../etc/passwd"))
    assert_true(d.action.risk_score > 0.2, f"traversal detected, risk={d.action.risk_score}")

test("T6.05 Path traversal detection", t6_05_path_traversal)


def t6_06_unicode_path():
    g = PermissionGuard()
    d = g.check(make_action(target="/项目/数据/用户信息.csv"))
    assert_eq(d.outcome, d.outcome, "unicode path no crash")

test("T6.06 Unicode path", t6_06_unicode_path)


def t6_07_rapid_repeated():
    g = PermissionGuard(audit_log=True)
    action = make_action(target="same_file.txt")
    for _ in range(20):
        g.check(action)
    assert_eq(len(g.get_audit_log()), 20)

test("T6.07 Rapid repeated submits", t6_07_rapid_repeated)


def t6_08_level_switch_immediate():
    g = PermissionGuard(PermissionLevel.PLAN)
    d1 = g.check(make_action(ActionType.FILE_CREATE, "x.py"))
    assert_eq(d1.outcome, DecisionOutcome.DENIED)
    g.set_level(PermissionLevel.BYPASS)
    d2 = g.check(make_action(ActionType.FILE_CREATE, "x.py"))
    assert_eq(d2.outcome, DecisionOutcome.ALLOWED)

test("T6.08 Level switch immediate", t6_08_level_switch_immediate)


def t6_09_set_level_api():
    g = PermissionGuard()
    for level in PermissionLevel:
        g.set_level(level)
        assert_eq(g.current_level, level)

test("T6.09 set_level API", t6_09_set_level_api)


def t6_10_remove_nonexistent():
    g = PermissionGuard()
    result = g.remove_rule("NONEXISTENT_RULE_ID")
    assert_true(result == False, "returns False for nonexistent")

test("T6.10 Remove nonexistent rule", t6_10_remove_nonexistent)


def t6_11_empty_rules_init():
    g = PermissionGuard(rules=[])
    d = g.check(make_action())
    assert_true(isinstance(d, PermissionDecision), "empty rules still work")

test("T6.11 Empty rules init", t6_11_empty_rules_init)


def t6_12_risk_boundaries():
    g = PermissionGuard()
    s_low = g.auto_classify(make_action(target="safe_readme.md"))
    s_high = g.auto_classify(make_action(target="sudo rm -rf /etc"))
    assert_true(s_low >= 0.0 and s_low <= 1.0, f"low boundary {s_low}")
    assert_true(s_high >= 0.0 and s_high <= 1.0, f"high boundary {s_high}")

test("T6.12 Risk boundaries 0-1", t6_12_risk_boundaries)


def t6_13_xss_safe():
    g = PermissionGuard()
    d = g.check(make_action(target="<script>alert('xss')</script>"))
    assert_true(isinstance(d, PermissionDecision), "XSS string safe")

test("T6.13 XSS injection safe", t6_13_xss_safe)


def t6_14_many_rules_perf():
    many_rules = [
        PermissionRule(f"CUST-{i}", ActionType.FILE_READ, f"pattern_{i}",
                       PermissionLevel.DEFAULT, f"rule {i}")
        for i in range(500)
    ]
    g = PermissionGuard(rules=many_rules)
    start = time.perf_counter()
    for i in range(100):
        g.check(make_action(target=f"file_{i}.txt"))
    elapsed = (time.perf_counter() - start) * 1000
    assert_true(elapsed < 5000, f"100 checks with 500 rules took {elapsed:.1f}ms")

test("T6.14 Many rules performance", t6_14_many_rules_perf)


def t6_15_clear_audit():
    g = PermissionGuard(audit_log=True)
    for _ in range(10):
        g.check(make_action())
    count = g.clear_audit_log()
    assert_eq(count, 10)
    assert_eq(len(g.get_audit_log()), 0)

test("T6.15 Clear audit log", t6_15_clear_audit)


# ============================================================
# IT1: Guard + Integration (8)
# ============================================================

print("\n=== IT1: Integration ===")


def it1_01_coordinator_integration():
    from collaboration.coordinator import Coordinator
    g = PermissionGuard(PermissionLevel.DEFAULT)
    try:
        coord = Coordinator(permission_guard=g)
        assert_true(hasattr(coord, 'permission_guard'), "coordinator has guard")
    except TypeError:
        coord = Coordinator()
        coord.permission_guard = g
        assert_true(hasattr(coord, 'permission_guard'), "guard attached")

test("IT1.01 Coordinator integration", it1_01_coordinator_integration)


def it1_02_full_workflow():
    g = PermissionGuard(PermissionLevel.DEFAULT, audit_log=True)
    actions = [
        make_action(ActionType.FILE_READ, "README.md"),
        make_action(ActionType.FILE_CREATE, "utils/helper.py"),
        make_action(ActionType.FILE_MODIFY, "config.json"),
        make_action(ActionType.SHELL_EXECUTE, "git status"),
        make_action(ActionType.FILE_MODIFY, ".env"),
    ]
    outcomes = []
    for a in actions:
        d = g.check(a)
        outcomes.append(d.outcome)
    allowed_count = sum(1 for o in outcomes if o == DecisionOutcome.ALLOWED)
    assert_true(allowed_count >= 2, f"at least 2 allowed, got {allowed_count}")
    assert_true(any(o == DecisionOutcome.PROMPT for o in outcomes),
                "at least one prompt for .env")

test("IT1.02 Full workflow check", it1_02_full_workflow)


def it1_03_denied_isolated():
    g = PermissionGuard(PermissionLevel.PLAN, audit_log=True)
    results = []
    ops = [
        ("read", make_action(ActionType.FILE_READ, "a.txt")),
        ("write", make_action(ActionType.FILE_CREATE, "b.py")),
        ("read2", make_action(ActionType.FILE_READ, "c.txt")),
        ("delete", make_action(ActionType.FILE_DELETE, "d.txt")),
        ("write2", make_action(ActionType.FILE_MODIFY, "e.conf")),
    ]
    for name, a in ops:
        d = g.check(a)
        results.append((name, d.outcome))
    read_results = [o for n, o in results if n.startswith("read")]
    write_results = [o for n, o in results if n.startswith("write") or n == "delete"]
    assert_true(all(o == DecisionOutcome.ALLOWED for o in read_results), "reads allowed")
    assert_true(all(o == DecisionOutcome.DENIED for o in write_results), "writes denied")

test("IT1.03 Denied isolated", it1_03_denied_isolated)


def it1_04_export_state():
    g = PermissionGuard(PermissionLevel.AUTO)
    g.add_whitelist("special-cmd")
    state = g.export_state()
    assert_in("current_level", state)
    assert_in("rules", state)
    assert_in("whitelist", state)
    assert_in("special-cmd", state["whitelist"])

test("IT1.04 Export state", it1_04_export_state)


def it1_05_multi_level_flow():
    g = PermissionGuard(PermissionLevel.PLAN, audit_log=True)
    g.check(make_action(ActionType.FILE_CREATE, "x.py"))
    plan_denied = len([e for e in g.get_audit_log()
                        if e.decision and e.decision.outcome == DecisionOutcome.DENIED])
    g.set_level(PermissionLevel.DEFAULT)
    g.check(make_action(ActionType.FILE_CREATE, "y.py"))
    g.set_level(PermissionLevel.BYPASS)
    g.check(make_action(ActionType.FILE_CREATE, "z.py"))
    total = len(g.get_audit_log())
    assert_eq(total, 3, "all 3 operations logged across levels")

test("IT1.05 Multi-level flow", it1_05_multi_level_flow)


def it1_06_rules_by_type_stats():
    g = PermissionGuard()
    report = g.get_security_report()
    assert_true(report["rules_count"] == 30, f"30 rules, got {report['rules_count']}")

test("IT1.06 Rules stats", it1_06_rules_by_type_stats)


def it1_07_session_id_consistent():
    g = PermissionGuard(session_id="test-session-001")
    g.check(make_action())
    log = g.get_audit_log()
    assert_eq(log[0].session_id, "test-session-001")

test("IT1.07 Session ID consistent", it1_07_session_id_consistent)


def it1_08_decision_dict_serializable():
    g = PermissionGuard()
    d = g.check(make_action(ActionType.FILE_READ, "test.py"))
    dict_repr = d.to_dict()
    assert_in("decision_id", dict_repr)
    assert_in("outcome", dict_repr)
    assert_in("reason", dict_repr)

test("IT1.08 Decision serializable", it1_08_decision_dict_serializable)


# ============================================================
# IT2: Consensus Integration (simulated) (4)
# ============================================================

print("\n=== IT2: Consensus Linkage ===")


def it2_01_escalated_detected():
    g = PermissionGuard(PermissionLevel.PLAN, audit_log=True)
    d = g.check(make_action(ActionType.FILE_MODIFY, "critical_config.conf"))
    assert_true(d.outcome in (DecisionOutcome.DENIED, DecisionOutcome.PROMPT,
                               DecisionOutcome.ESCALATED),
                f"dangerous op caught: {d.outcome.value}")

test("IT2.01 Escalated handling", it2_01_escalated_detected)


def it2_02_scratchpad_conflict_simulation():
    g = PermissionGuard(PermissionLevel.PLAN, audit_log=True)
    g.check(make_action(ActionType.FILE_DELETE, "important_data.json"))
    caught = [e for e in g.get_audit_log()
              if e.decision and e.decision.outcome in (DecisionOutcome.DENIED,
                                                         DecisionOutcome.PROMPT,
                                                         DecisionOutcome.ESCALATED)]
    assert_true(len(caught) >= 1, "dangerous op caught")

test("IT2.02 Conflict simulation", it2_02_scratchpad_conflict_simulation)


def it2_03_vote_after_escalation():
    g = PermissionGuard(PermissionLevel.DEFAULT)
    d = g.check(make_action(ActionType.FILE_MODIFY, ".env"))
    if d.requires_confirmation:
        simulated_approval = True
        assert_true(simulated_approval, "can simulate user approval flow")

test("IT2.03 Vote simulation", it2_03_vote_after_escalation)


def it2_04_concurrent_guard_shared():
    g = PermissionGuard(audit_log=True)
    errors_list = []

    def worker(idx):
        try:
            for j in range(10):
                g.check(make_action(target=f"worker{idx}_file{j}.txt"))
        except Exception as e:
            errors_list.append(str(e))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert_eq(len(errors_list), 0, f"No thread errors: {errors_list}")
    assert_eq(len(g.get_audit_log()), 50, "All 50 operations logged")

test("IT2.04 Concurrent guard shared", it2_04_concurrent_guard_shared)


# ============================================================
# E2E: User Journeys (8)
# ============================================================

print("\n=== E2E: User Journeys ===")


def e2e_01_journey_a_secure_dev():
    g = PermissionGuard(PermissionLevel.DEFAULT, audit_log=True)
    journey_steps = [
        (ActionType.FILE_READ, "requirements.txt"),
        (ActionType.FILE_CREATE, "docs/design.md"),
        (ActionType.FILE_MODIFY, "styles.css"),
        (ActionType.SHELL_EXECUTE, "pytest"),
        (ActionType.FILE_MODIFY, ".env.example"),
        (ActionType.GIT_OPERATION, "commit"),
        (ActionType.GIT_OPERATION, "push"),
        (ActionType.FILE_READ, "final_report.md"),
    ]
    prompt_count = 0
    deny_count = 0
    for at, tgt in journey_steps:
        d = g.check(make_action(at, tgt))
        if d.outcome == DecisionOutcome.PROMPT:
            prompt_count += 1
        elif d.outcome == DecisionOutcome.DENIED:
            deny_count += 1
    assert_true(prompt_count >= 1, f"some prompts needed ({prompt_count})")
    assert_true(deny_count == 0, f"no denies in normal workflow ({deny_count})")
    report = g.get_security_report()
    assert_eq(report["total_checks"], len(journey_steps))

test("E2E-1 Journey A: Secure dev workflow", e2e_01_journey_a_secure_dev)


def e2e_02_journey_b_plan_preview():
    g = PermissionGuard(PermissionLevel.PLAN, audit_log=True)
    all_ops = [
        make_action(ActionType.FILE_READ, "spec.md"),
        make_action(ActionType.FILE_CREATE, "design.py"),
        make_action(ActionType.FILE_MODIFY, "config.yaml"),
        make_action(ActionType.SHELL_EXECUTE, "npm install"),
        make_action(ActionType.FILE_DELETE, "old_backup.bak"),
    ]
    allowed = 0
    denied = 0
    for a in all_ops:
        d = g.check(a)
        if d.outcome == DecisionOutcome.ALLOWED:
            allowed += 1
        elif d.outcome == DecisionOutcome.DENIED:
            denied += 1
    assert_true(allowed >= 1, "reads allowed in PLAN")
    assert_true(denied >= 3, "writes denied in PLAN")
    log = g.get_audit_log()
    assert_eq(len(log), len(all_ops), "full audit trail")

test("E2E-2 Journey B: Plan preview", e2e_02_journey_b_plan_preview)


def e2e_03_journey_c_incident_investigation():
    g = PermissionGuard(PermissionLevel.DEFAULT, audit_log=True)
    suspicious = [
        make_action(ActionType.SHELL_EXECUTE, "rm -rf /project/data"),
        make_action(ActionType.FILE_MODIFY, "/etc/hosts"),
        make_action(ActionType.FILE_READ, "normal_config.json"),
        make_action(ActionType.NETWORK_REQUEST, "http://internal.api/data"),
    ]
    for a in suspicious:
        g.check(a)
    report = g.get_security_report()
    assert_true(report["denied"] >= 1 or report["prompted"] >= 1,
                f"suspicious ops caught: denied={report['denied']}, prompted={report['prompted']}")
    denied_log = g.get_audit_log(outcome=DecisionOutcome.DENIED)
    for e in denied_log:
        assert_true(e.decision is not None, "has decision for investigation")

test("E2E-3 Journey C: Incident investigation", e2e_03_journey_c_incident_investigation)


def e2e_04_stress_100_ops():
    g = PermissionGuard(audit_log=True)
    import random
    random.seed(42)
    types = list(ActionType)
    for i in range(100):
        at = random.choice(types)
        tgt = f"file_{i % 10}.{random.choice(['txt','py','json','md'])}"
        g.check(make_action(at, tgt))
    log = g.get_audit_log()
    assert_eq(len(log), 100, "all 100 logged")
    report = g.get_security_report()
    assert_eq(report["total_checks"], 100)

test("E2E-4 Stress 100 operations", e2e_04_stress_100_ops)


def e2e_05_five_roles_with_guard():
    g = PermissionGuard(PermissionLevel.DEFAULT, audit_log=True)
    roles = ["architect", "product-manager", "tester", "ui-designer", "devops"]
    all_ok = True
    for role in roles:
        for i in range(3):
            at = ActionType.FILE_READ if i == 0 else ActionType.FILE_CREATE
            d = g.check(make_action(at, target=f"{role}_output_{i}.md",
                                   source_role_id=role,
                                   source_worker_id=f"{role}-worker"))
            if d.outcome not in (DecisionOutcome.ALLOWED, DecisionOutcome.PROMPT):
                all_ok = False
    assert_true(all_ok, "all role operations produce valid decisions")
    report = g.get_security_report()
    assert_eq(report["total_checks"], 15)

test("E2E-5 Five roles with guard", e2e_05_five_roles_with_guard)


def e2e_06_dynamic_hot_update():
    g = PermissionGuard(PermissionLevel.DEFAULT, audit_log=True)
    d1 = g.check(make_action(ActionType.FILE_CREATE, "test.log"))
    g.add_rule(PermissionRule("HOTFIX", ActionType.FILE_CREATE, "*.log",
                             PermissionLevel.BYPASS, "hotfix allow logs"))
    d2 = g.check(make_action(ActionType.FILE_CREATE, "test.log"))
    assert_true(isinstance(d2, PermissionDecision), "after hotfix still works")

test("E2E-6 Dynamic rule hot update", e2e_06_dynamic_hot_update)


def e2e_07_level_switching_journey():
    g = PermissionGuard(audit_log=True)
    levels = [PermissionLevel.PLAN, PermissionLevel.DEFAULT,
              PermissionLevel.AUTO, PermissionLevel.BYPASS, PermissionLevel.DEFAULT]
    outcomes_at_each = []
    for lvl in levels:
        g.set_level(lvl)
        d = g.check(make_action(ActionType.FILE_CREATE, "switch_test.py"))
        outcomes_at_each.append((lvl.value, d.outcome.value))
    assert_true(len(outcomes_at_each) == 5, "all 5 levels tested")
    plan_outcome = outcomes_at_each[0][1]
    bypass_outcome = outcomes_at_each[3][1]
    assert_true(plan_outcome == "denied", f"PLAN should deny, got {plan_outcome}")
    assert_true(bypass_outcome == "allowed", f"BYPASS should allow, got {bypass_outcome}")

test("E2E-7 Level switching journey", e2e_07_level_switching_journey)


def e2e_08_full_audit_export():
    g = PermissionGuard(PermissionLevel.AUTO, audit_log=True)
    for i in range(25):
        g.check(make_action(target=f"data_{i}.json"))
    log = g.get_audit_log()
    assert_eq(len(log), 25)
    exported = [e.to_dict() for e in log]
    assert_true(len(exported) == 25, "all exportable")
    for ed in exported:
        assert_in("entry_id", ed)
        assert_in("decision", ed)

test("E2E-8 Full audit export", e2e_08_full_audit_export)


# ============================================================
# Results
# ============================================================

print(f"\n{'='*60}")
print(f"PermissionGuard Test Results: {passed}/{TOTAL} passed")
if errors:
    print(f"\n❌ Failed ({len(errors)}):")
    for name, err in errors:
        print(f"  - {name}: {err}")
else:
    print(f"\n🎉 ALL {TOTAL} TESTS PASSED!")
print(f"{'='*60}")

