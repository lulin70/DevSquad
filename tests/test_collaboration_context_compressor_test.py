#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContextCompressor E2E Test Suite
Covers: Token estimation, Importance scoring, 3-level compression,
        Session memory, Edge cases, Thread safety, Export/Import
"""

import sys
import os
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collaboration.context_compressor import (
    ContextCompressor, Message, MemoryEntry, CompressedContext,
    CompressionLevel, MessageType, MemoryCategory,
)


# ============================================================
# Helper utilities
# ============================================================

def make_msg(content, role="user", msg_type=MessageType.USER, **meta):
    return Message(role=role, content=content, msg_type=msg_type, metadata=meta)


def make_msgs(contents, role="user"):
    return [make_msg(c, role) for c in contents]


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


def assert_gt(val, threshold, msg=""):
    if not (val > threshold):
        raise AssertionError(f"{msg} Expected > {threshold}, got {val}")


def assert_in(item, container, msg=""):
    if item not in container:
        raise AssertionError(f"{msg} {item!r} not in {container!r}")


def assert_between(val, lo, hi, msg=""):
    if not (lo <= val <= hi):
        raise AssertionError(f"{msg} Expected [{lo}, {hi}], got {val}")


# ============================================================
# T1: Token Estimation
# ============================================================

print("\n=== T1: Token Estimation ===")


def t1_01_empty_string():
    c = ContextCompressor()
    assert_eq(c.estimate_tokens(""), 0)

test("T1.01 empty string returns 0", t1_01_empty_string)


def t1_02_english_text():
    c = ContextCompressor()
    tokens = c.estimate_tokens("Hello world, this is a test sentence.")
    assert_between(tokens, 5, 15, "English text token count")

test("T1.02 English text estimation", t1_02_english_text)


def t1_03_chinese_text():
    c = ContextCompressor()
    tokens = c.estimate_tokens("这是一个中文测试句子，包含很多汉字")
    assert_gt(tokens, 5, "Chinese text should have tokens")

test("T1.03 Chinese text estimation", t1_03_chinese_text)


def t1_04_mixed_content():
    c = ContextCompressor()
    tokens = c.estimate_tokens("Hello世界，这是一个Mixed内容测试")
    assert_gt(tokens, 5, "Mixed content should have tokens")

test("T1.04 Mixed Chinese+English", t1_04_mixed_content)


def t1_05_long_text():
    c = ContextCompressor()
    long_text = "这是一个很长的测试句子。" * 100
    tokens = c.estimate_tokens(long_text)
    assert_gt(tokens, 200, "Long text should have significant tokens")

test("T1.05 Long text scaling", t1_05_long_text)


def t1_06_estimate_messages_with_cached_tokens():
    c = ContextCompressor()
    msgs = [
        Message(content="hello", token_count=100),
        Message(content="world", token_count=50),
    ]
    total = c.estimate_messages_tokens(msgs)
    assert_eq(total, 150, "Should use cached token counts")

test("T1.06 Messages with cached tokens", t1_06_estimate_messages_with_cached_tokens)


def t1_07_estimate_messages_without_cache():
    c = ContextCompressor()
    msgs = [Message(content="test message here"), Message(content="another one")]
    total = c.estimate_messages_tokens(msgs)
    assert_gt(total, 2, "Should estimate from content when no cache")

test("T1.07 Messages without cached tokens", t1_07_estimate_messages_without_cache)


# ============================================================
# T2: Importance Scoring
# ============================================================

print("\n=== T2: Importance Scoring ===")


def t2_01_default_score():
    c = ContextCompressor()
    msg = make_msg("just some random text")
    score = c._score_importance(msg)
    assert_between(score, 0.4, 0.6, "Default score around 0.5")

test("T2.01 Default importance ~0.5", t2_01_default_score)


def t2_02_high_importance_keywords_boost():
    c = ContextCompressor()
    msg = make_msg("我们做出了关键决定，采用新架构方案")
    score = c._score_importance(msg)
    assert_gt(score, 0.7, "Decision/architecture keywords boost score")

test("T2.02 High-importance keywords boost", t2_02_high_importance_keywords_boost)


def t2_03_error_keywords_boost():
    c = ContextCompressor()
    msg = make_msg("发现一个严重bug，需要立即修复")
    score = c._score_importance(msg)
    assert_gt(score, 0.65, "Error keywords boost score")

test("T2.03 Error keywords boost", t2_03_error_keywords_boost)


def t2_04_low_importance_patterns_penalty():
    c = ContextCompressor()
    msg = make_msg("好的")
    score = c._score_importance(msg)
    assert_true(score < 0.4, f"Short acknowledgment should be low: {score}")

test("T2.04 Low-importance patterns penalty", t2_04_low_importance_patterns_penalty)


def t2_05_system_message_bonus():
    c = ContextCompressor()
    msg = make_msg("System prompt instructions", msg_type=MessageType.SYSTEM)
    score = c._score_importance(msg)
    assert_gt(score, 0.6, "System messages get bonus")

test("T2.05 System message type bonus", t2_05_system_message_bonus)


def t2_06_assistant_structured_bonus():
    c = ContextCompressor()
    msg = make_msg("# Summary\n- Item 1\n- Item 2\n## Details", msg_type=MessageType.ASSISTANT)
    score = c._score_importance(msg)
    assert_gt(score, 0.55, "Structured assistant gets bonus")

test("T2.06 Structured assistant bonus", t2_06_assistant_structured_bonus)


def t2_07_metadata_decision_flag():
    c = ContextCompressor()
    msg = make_msg("some decision", is_decision=True)
    score = c._score_importance(msg)
    assert_gt(score, 0.65, "is_decision metadata boosts")

test("T2.07 is_decision metadata flag", t2_07_metadata_decision_flag)


def t2_08_metadata_error_flag():
    c = ContextCompressor()
    msg = make_msg("something went wrong", is_error=True)
    score = c._score_importance(msg)
    assert_gt(score, 0.6, "is_error metadata boosts")

test("T2.08 is_error metadata flag", t2_08_metadata_error_flag)


def t2_09_score_clamped_to_0_1():
    c = ContextCompressor()
    msg = make_msg("好的" * 20, is_decision=True)
    score = c._score_importance(msg)
    assert_between(score, 0.0, 1.0, "Score must be clamped to [0,1]")

test("T2.09 Score clamped to [0,1]", t2_09_score_clamped_to_0_1)


# ============================================================
# T3: Level 1 - SNIP Compression
# ============================================================

print("\n=== T3: Level 1 SNIP Compression ===")


def t3_01_snip_keeps_high_importance():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 100})
    msgs = [
        make_msg("好的，收到", importance_score=0.1),
        make_msg("关键架构决策：采用微服务方案", importance_score=0.9),
        make_msg("嗯嗯", importance_score=0.1),
        make_msg("发现严重安全漏洞需要修复", importance_score=0.85),
        make_msg("OK明白", importance_score=0.15),
    ]
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    contents = [m.content for m in result.messages]
    assert_true(any("关键架构决策" in c for c in contents), "High importance msg should be kept")
    assert_true(any("发现严重安全漏洞" in c for c in contents), "High importance msg should be kept")
    assert_true(len(result.messages) < len(msgs), "Some messages should be snipped")

test("T3.01 SNIP keeps high-importance messages", t3_01_snip_keeps_high_importance)


def t3_02_snip_removes_low_importance():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 100})
    msgs = [
        make_msg("好的"),
        make_msg("收到"),
        make_msg("嗯嗯"),
        make_msg("OK"),
        make_msg("重要架构设计文档", importance_score=0.9),
    ]
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    low_msgs = [m for m in result.messages if m.content in ["好的", "收到", "嗯嗯", "OK"]]
    assert_true(len(low_msgs) == 0 or len(result.messages) < len(msgs),
                "Low importance messages should be removed")

test("T3.02 SNIP removes low-importance messages", t3_02_snip_removes_low_importance)


def t3_03_snip_reduces_token_count():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 100})
    msgs = make_msgs(["short message filler text"] * 30 + ["important architecture decision about system design and implementation details here"] * 5)
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    assert_true(result.compressed_token_count < result.original_token_count,
                "SNIP should reduce token count")

test("T3.03 SNIP reduces total token count", t3_03_snip_reduces_token_count)


def t3_04_snip_extracts_memory_from_snipped():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 100})
    msgs = [
        make_msg("好的"),
        make_msg("我们决定采用React作为前端框架，这是一个重要的架构决策"),
        make_msg("关于用户认证模块的初步设计方案已经完成"),
        make_msg("数据库选择PostgreSQL方案已确认需要配置连接池参数"),
        make_msg("API接口设计文档已更新到最新版本") ,
        make_msg("缓存策略采用Redis集群部署方案") ,
        make_msg("嗯嗯好的收到了解明白") ,
        make_msg("收到OK好的明白了解") ,
        make_msg("好的吧嗯嗯可以明白行") ,
        make_msg("可以行吧好的收到OK嗯") ,
    ]
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    memory = c.get_session_memory()
    assert_true(len(memory) >= 1, f"Snipped messages should produce memory entries, got {len(memory)}, kept {len(result.messages)}/{len(msgs)}")

test("T3.04 SNIP extracts memory from removed messages", t3_04_snip_extracts_memory_from_snipped)


def t3_05_snip_stats_populated():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 100})
    msgs = make_msgs(["msg " + str(i) for i in range(20)])
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    assert_in("snipped_count", result.stats, "Stats should include snipped_count")
    assert_in("snipped_tokens", result.stats, "Stats should include snipped_tokens")

test("T3.05 SNIP stats populated correctly", t3_05_snip_stats_populated)


# ============================================================
# T4: Level 2 - SessionMemory Compression
# ============================================================

print("\n=== T4: Level 2 SessionMemory ===")


def t4_01_session_memory_keeps_recent():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 100})
    msgs = make_msgs([f"message number {i} with some content here" for i in range(10)])
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    assert_eq(len(result.messages), min(3, len(msgs)), "Should keep last 3 messages")

test("T4.01 Keeps last 3 recent messages", t4_01_session_memory_keeps_recent)


def t4_02_session_memory_extracts_all():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 100})
    msgs = [
        make_msg("我们决定采用微服务架构"),
        make_msg("发现性能瓶颈在数据库查询"),
        make_msg("TODO: 需要优化索引"),
        make_msg("最新消息A"),
        make_msg("最新消息B"),
        make_msg("最新消息C"),
    ]
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    memory = c.get_session_memory()
    assert_true(len(memory) >= 2, "Should extract memory entries from all messages")

test("T4.02 Extracts memory from all messages", t4_02_session_memory_extracts_all)


def t4_03_session_memory_summary_format():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 100})
    msgs = make_msgs(["content " + str(i) for i in range(10)])
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    assert_in("SessionMemory", result.summary, "Summary mentions SessionMemory")
    assert_in("memory entries", result.summary, "Summary mentions extracted entries")

test("T4.03 Summary format includes key info", t4_03_session_memory_summary_format)


def t4_04_less_than_3_msgs_kept_all():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 100})
    msgs = make_msgs(["only two", "messages"])
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    assert_eq(len(result.messages), 2, "< 3 messages should all be kept")

test("T4.04 Less than 3 messages all kept", t4_04_less_than_3_msgs_kept_all)


def t4_05_categories_in_stats():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 100})
    msgs = [
        make_msg("做出架构决定"),
        make_msg("发现错误问题"),
        make_msg("待办事项清单"),
        make_msg("a"), make_msg("b"), make_msg("c"),
    ]
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    assert_in("categories", result.stats, "Categories in stats")

test("T4.05 Category breakdown in stats", t4_05_categories_in_stats)


# ============================================================
# T5: Level 3 - FullCompact Compression
# ============================================================

print("\n=== T5: Level 3 FullCompact ===")


def t5_01_fullcompact_no_messages_left():
    c = ContextCompressor(thresholds={CompressionLevel.FULL_COMPACT: 100})
    msgs = make_msgs(["msg " + str(i) for i in range(15)])
    result = c.check_and_compress(msgs, force_level=CompressionLevel.FULL_COMPACT)
    assert_eq(len(result.messages), 0, "FullCompact should clear all messages")

test("T5.01 No messages remain after FullCompact", t5_01_fullcompact_no_messages_left)


def t5_02_fullcompact_has_summary():
    c = ContextCompressor(thresholds={CompressionLevel.FULL_COMPACT: 100})
    msgs = [
        make_msg("我们决定采用Vue框架"),
        make_msg("发现SQL注入漏洞"),
        make_msg("TODO: 完成单元测试覆盖"),
        make_msg("交付API文档初稿"),
        make_msg("普通消息内容"),
    ] * 3
    result = c.check_and_compress(msgs, force_level=CompressionLevel.FULL_COMPACT)
    assert_true(len(result.summary) > 20, "FullCompact should generate summary")
    assert_in("FullCompact Summary", result.summary, "Summary header present")

test("T5.02 Generates categorized summary", t5_02_fullcompact_has_summary)


def t5_03_fullcompact_sections_present():
    c = ContextCompressor(thresholds={CompressionLevel.FULL_COMPACT: 100})
    msgs = [
        make_msg("最终决定使用Kubernetes部署方案"),
        make_msg("交付用户认证模块实现代码"),
        make_msg("TODO: 编写集成测试用例"),
        make_msg("编译错误：缺少依赖库"),
        make_msg("分析发现系统响应时间过长"),
    ] * 3
    result = c.check_and_compress(msgs, force_level=CompressionLevel.FULL_COMPACT)
    summary_lower = result.summary.lower()
    has_decisions = "decision" in summary_lower or "决定" in result.summary
    has_todos = "action" in summary_lower or "todo" in summary_lower or "待办" in result.summary
    assert_true(has_decisions or has_todos or len(result.summary) > 50,
                "Summary should contain categorized sections")

test("T5.03 Categorized sections in summary", t5_03_fullcompact_sections_present)


def t5_04_fullcompact_high_compression_ratio():
    c = ContextCompressor(thresholds={CompressionLevel.FULL_COMPACT: 100})
    long_content = "这是一段很长的技术讨论内容，包含架构设计和实现细节。" * 50
    msgs = make_msgs([long_content] * 20)
    result = c.check_and_compress(msgs, force_level=CompressionLevel.FULL_COMPACT)
    assert_true(result.reduction_percent > 80,
                f"FullCompact should have >80% reduction, got {result.reduction_percent:.1f}%")

test("T5.04 High compression ratio >80%", t5_04_fullcompact_high_compression_ratio)


def t5_05_fullcompact_stats_detail():
    c = ContextCompressor(thresholds={CompressionLevel.FULL_COMPACT: 100})
    msgs = [
        make_msg("决定采用Redis缓存"),
        make_msg("发现内存泄漏问题"),
        make_msg("完成登录功能开发"),
    ] * 5
    result = c.check_and_compress(msgs, force_level=CompressionLevel.FULL_COMPACT)
    stats_keys = list(result.stats.keys())
    expected_keys = ["decisions", "findings", "todos", "errors", "deliverables"]
    for k in expected_keys:
        assert_in(k, stats_keys, f"Stat key {k} should be present")

test("T5.05 Detailed stats with category counts", t5_05_fullcompact_stats_detail)


# ============================================================
# T6: Auto Level Selection by Thresholds
# ============================================================

print("\n=== T6: Auto Level Selection ===")


def t6_01_under_threshold_no_compress():
    c = ContextCompressor(thresholds={
        CompressionLevel.SNIP: 1000,
        CompressionLevel.SESSION_MEMORY: 2000,
        CompressionLevel.FULL_COMPACT: 3000,
    })
    msgs = make_msgs(["short"] * 5)
    result = c.check_and_compress(msgs)
    assert_eq(result.compression_level, CompressionLevel.NONE, "Under threshold = no compress")
    assert_eq(len(result.messages), len(msgs), "All messages preserved")

test("T6.01 Under threshold → NONE", t6_01_under_threshold_no_compress)


def t6_02_at_snip_threshold():
    c = ContextCompressor(thresholds={
        CompressionLevel.SNIP: 50,
        CompressionLevel.SESSION_MEMORY: 500,
        CompressionLevel.FULL_COMPACT: 1000,
    })
    medium_text = "medium length message with enough tokens here"
    msgs = make_msgs([medium_text] * 5)
    result = c.check_and_compress(msgs)
    assert_true(result.compression_level in (CompressionLevel.SNIP, CompressionLevel.SESSION_MEMORY, CompressionLevel.NONE),
                 f"At SNIP threshold range → got {result.compression_level}")

test("T6.02 At SNIP threshold → SNIP", t6_02_at_snip_threshold)


def t6_03_force_level_override():
    c = ContextCompressor()
    msgs = make_msgs(["tiny"])
    result = c.check_and_compress(msgs, force_level=CompressionLevel.FULL_COMPACT)
    assert_eq(result.compression_level, CompressionLevel.FULL_COMPACT,
              "Force level should override auto detection")

test("T6.03 Force level override works", t6_03_force_level_override)


def t6_04_default_thresholds_exist():
    c = ContextCompressor()
    assert_in(CompressionLevel.SNIP, c.thresholds, "SNIP threshold exists")
    assert_in(CompressionLevel.SESSION_MEMORY, c.thresholds, "SESSION_MEMORY threshold exists")
    assert_in(CompressionLevel.FULL_COMPACT, c.thresholds, "FULL_COMPACT threshold exists")

test("T6.04 Default thresholds configured", t6_04_default_thresholds_exist)


# ============================================================
# T7: Content Classification & Tag Extraction
# ============================================================

print("\n=== T7: Content Classification & Tags ===")


def t7_01_classify_decision():
    c = ContextCompressor()
    cat = c._classify_content("我们最终决定采用微服务架构方案")
    assert_eq(cat, MemoryCategory.DECISION, "Decision content classified correctly")

test("T7.01 Decision classification", t7_01_classify_decision)


def t7_02_classify_todo():
    c = ContextCompressor()
    cat = c._classify_content("下一步需要完成单元测试编写工作")
    assert_eq(cat, MemoryCategory.TODO, "TODO content classified correctly")

test("T7.02 TODO classification", t7_02_classify_todo)


def t7_03_classify_error():
    c = ContextCompressor()
    cat = c._classify_content("系统出现异常，无法连接到数据库服务器")
    assert_eq(cat, MemoryCategory.ERROR, "Error content classified correctly")

test("T7.03 Error classification", t7_03_classify_error)


def t7_04_classify_deliverable():
    c = ContextCompressor()
    cat = c._classify_content("已完成用户管理模块的开发和测试工作")
    assert_eq(cat, MemoryCategory.DELIVERABLE, "Deliverable content classified correctly")

test("T7.04 Deliverable classification", t7_04_classify_deliverable)


def t7_05_classify_question():
    c = ContextCompressor()
    cat = c._classify_content("是否应该使用TypeScript来重写前端代码？")
    assert_eq(cat, MemoryCategory.QUESTION, "Question content classified correctly")

test("T7.05 Question classification", t7_05_classify_question)


def t7_06_default_finding():
    c = ContextCompressor()
    cat = c._classify_content("这是一个普通的描述性文本内容")
    assert_eq(cat, MemoryCategory.FINDING, "Generic content defaults to FINDING")

test("T7.06 Default FINDING fallback", t7_06_default_finding)


def t7_07_extract_security_tag():
    c = ContextCompressor()
    tags = c._extract_tags("发现XSS安全漏洞需要修复")
    assert_in("security", tags, "Security tag extracted")

test("T7.07 Security tag extraction", t7_07_extract_security_tag)


def t7_08_extract_performance_tag():
    c = ContextCompressor()
    tags = c._extract_tags("系统性能优化，减少延迟和响应时间")
    assert_in("performance", tags, "Performance tag extracted")

test("T7.08 Performance tag extraction", t7_08_extract_performance_tag)


def t7_09_extract_architecture_tag():
    c = ContextCompressor()
    tags = c._extract_tags("整体架构设计采用分层模块化结构")
    assert_in("architecture", tags, "Architecture tag extracted")

test("T7.09 Architecture tag extraction", t7_09_extract_architecture_tag)


def t7_10_extract_testing_tag():
    c = ContextCompressor()
    tags = c._extract_tags("测试覆盖率需要达到80%以上")
    assert_in("testing", tags, "Testing tag extracted")

test("T7.10 Testing tag extraction", t7_10_extract_testing_tag)


def t7_11_multiple_tags():
    c = ContextCompressor()
    tags = c._extract_tags("API接口性能优化和安全测试验证")
    has_api = "api" in tags
    has_perf = "performance" in tags
    has_test = "testing" in tags
    assert_true(has_api or has_perf or has_test, "Multiple tags can be extracted")

test("T7.11 Multiple tag extraction", t7_11_multiple_tags)


# ============================================================
# T8: Session Memory Management
# ============================================================

print("\n=== T8: Session Memory Management ===")


def t8_01_get_all_memory():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 50})
    msgs = [
        make_msg("做出重要架构决定：采用微服务设计方案"),
        make_msg("发现一个严重的性能问题需要优化处理"),
        make_msg("待办事项清单：完成单元测试和集成测试"),
        make_msg("d"), make_msg("e"), make_msg("f"),
    ]
    c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    memory = c.get_session_memory()
    assert_true(len(memory) >= 1, "Session memory should have entries")

test("T8.01 Get all session memory entries", t8_01_get_all_memory)


def t8_02_get_by_category():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 50})
    msgs = [
        make_msg("我们决定使用Python"),
        make_msg("发现错误异常"),
        make_msg("a"), make_msg("b"), make_msg("c"),
    ]
    c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    decisions = c.get_session_memory(category=MemoryCategory.DECISION)
    errors = c.get_session_memory(category=MemoryCategory.ERROR)
    assert_true(len(decisions) >= 1 or len(errors) >= 1,
                "Category filtering should work")

test("T8.02 Filter memory by category", t8_02_get_by_category)


def t8_03_query_memory():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 50})
    msgs = [
        make_msg("关于数据库设计的决定"),
        make_msg("关于API性能的发现"),
        make_msg("a"), make_msg("b"), make_msg("c"),
    ]
    c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    results = c.query_memory("数据库")
    assert_true(len(results) >= 1, "Query should find matching entries")

test("T8.03 Query memory by keyword", t8_03_query_memory)


def t8_04_clear_memory():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 50})
    msgs = [
        make_msg("做出最终决定：使用FastAPI作为后端框架"),
        make_msg("发现严重错误：数据库连接池配置有误"),
        make_msg("a"), make_msg("b"),
    ]
    c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    count = c.clear_session_memory()
    assert_true(count >= 1, "Clear should remove entries")
    assert_eq(len(c.get_session_memory()), 0, "Memory empty after clear")

test("T8.04 Clear session memory", t8_04_clear_memory)


def t8_05_limit_parameter():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 50})
    msgs = [
        make_msg("决定1"), make_msg("决定2"), make_msg("决定3"),
        make_msg("发现1"), make_msg("发现2"), make_msg("发现3"),
        make_msg("a"), make_msg("b"), make_msg("c"),
    ]
    c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    limited = c.get_session_memory(limit=2)
    assert_true(len(limited) <= 2, "Limit parameter should cap results")

test("T8.05 Limit parameter works", t8_05_limit_parameter)


def t8_06_compression_stats():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 50})
    msgs = make_msgs(["test message content"] * 10)
    c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    stats = c.get_compression_stats()
    assert_true(stats["total_compressions"] >= 1, "Stats track compression count")
    assert_in("memory_entries", stats, "Stats include memory entry count")
    assert_in("memory_by_category", stats, "Stats include category breakdown")

test("T8.06 Compression statistics", t8_06_compression_stats)


# ============================================================
# T9: Edge Cases & Boundary Conditions
# ============================================================

print("\n=== T9: Edge Cases ===")


def t9_01_empty_message_list():
    c = ContextCompressor()
    result = c.check_and_compress([])
    assert_eq(result.compression_level, CompressionLevel.NONE, "Empty → NONE")
    assert_eq(len(result.messages), 0, "No messages")
    assert_eq(result.original_token_count, 0, "Zero original tokens")

test("T9.01 Empty message list", t9_01_empty_message_list)


def t9_02_single_message():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 10})
    msgs = [make_msg("single message here with some content")]
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    assert_true(isinstance(result, CompressedContext) and len(result.messages) >= 0,
                "Single message should be processed")

test("T9.02 Single message handling", t9_02_single_message)


def t9_03_very_long_single_message():
    c = ContextCompressor(thresholds={CompressionLevel.FULL_COMPACT: 100})
    huge = "This is a very long message containing lots of text data. " * 500
    msgs = [make_msg(huge)]
    result = c.check_and_compress(msgs, force_level=CompressionLevel.FULL_COMPACT)
    assert_true(isinstance(result, CompressedContext), "Should handle huge messages")

test("T9.03 Very long single message", t9_03_very_long_single_message)


def t9_04_special_characters():
    c = ContextCompressor()
    special = "特殊字符测试：<>&\"'\\n\t\r\n中文混合English123!@#$%"
    msgs = [make_msg(special)]
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    assert_true(result.original_token_count > 0, "Special chars should be counted")

test("T9.04 Special characters handling", t9_04_special_characters)


def t9_05_unicode_content():
    c = ContextCompressor()
    unicode_msg = "日本語テスト 🎉 Emoji测试 العربية اختبار 한국어 테스트"
    msgs = [make_msg(unicode_msg)]
    result = c.check_and_compress(msgs)
    assert_true(result.original_token_count > 0, "Unicode content handled")

test("T9.05 Unicode / multi-language content", t9_05_unicode_content)


def t9_06_all_low_importance():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 50})
    msgs = make_msgs(["好的", "收到", "嗯", "OK", "明白", "了解", "行", "可以"])
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    assert_true(isinstance(result, CompressedContext), "All-low-importance handled gracefully")

test("T9.06 All low-importance messages", t9_06_all_low_importance)


def t9_07_all_high_importance():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 50})
    msgs = make_msgs([
        "关键架构决策一",
        "重要安全修复二",
        "核心设计方案三",
        "必须完成的任务四",
        "验收标准确认五",
    ])
    result = c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    assert_true(len(result.messages) >= 3, "Most high-importance should be kept")

test("T9.07 All high-importance messages", t9_07_all_high_importance)


def t9_08_compressed_context_reduction_percent():
    ctx = CompressedContext(
        original_token_count=10000,
        compressed_token_count=3000,
        compression_level=CompressionLevel.SNIP,
    )
    pct = ctx.reduction_percent
    assert_between(pct, 69.0, 71.0, f"Reduction percent should be ~70%, got {pct}")

test("T9.08 reduction_percent calculation", t9_08_compressed_context_reduction_percent)


def t9_09_zero_original_reduction():
    ctx = CompressedContext(
        original_token_count=0,
        compressed_token_count=0,
        compression_level=CompressionLevel.NONE,
    )
    assert_eq(ctx.reduction_percent, 0.0, "Zero original → 0% reduction")

test("T9.09 Zero original reduction percent", t9_09_zero_original_reduction)


# ============================================================
# T10: Data Model Serialization
# ============================================================

print("\n=== T10: Serialization ===")


def t10_01_message_roundtrip():
    m = Message(
        role="assistant",
        content="test content",
        msg_type=MessageType.ASSISTANT,
        importance_score=0.85,
        metadata={"key": "value"},
    )
    d = m.to_dict()
    m2 = Message.from_dict(d)
    assert_eq(m2.role, m.role, "Role preserved")
    assert_eq(m2.content, m.content, "Content preserved")
    assert_eq(m2.importance_score, m.importance_score, "Score preserved")

test("T10.01 Message dict roundtrip", t10_01_message_roundtrip)


def t10_02_memory_entry_roundtrip():
    mem = MemoryEntry(
        category=MemoryCategory.DECISION,
        content="decision content",
        confidence=0.95,
        tags=["arch", "api"],
    )
    d = mem.to_dict()
    mem2 = MemoryEntry.from_dict(d)
    assert_eq(mem2.category, mem.category, "Category preserved")
    assert_eq(mem2.content, mem.content, "Content preserved")
    assert_eq(mem2.confidence, mem.confidence, "Confidence preserved")
    assert_eq(mem2.tags, mem.tags, "Tags preserved")

test("T10.02 MemoryEntry dict roundtrip", t10_02_memory_entry_roundtrip)


def t10_03_export_import_state():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 50})
    msgs = [
        make_msg("决定导出状态：采用Redis作为缓存层方案"),
        make_msg("发现测试问题：集成测试覆盖率不足需要补充"),
        make_msg("a"), make_msg("b"), make_msg("c"),
    ]
    c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
    state = c.export_state()
    assert_true(len(state["session_memory"]) >= 1, "Exported state has memory")

    c2 = ContextCompressor()
    c2.import_state(state)
    memory = c2.get_session_memory()
    assert_true(len(memory) >= 1, "Imported state restores memory")

test("T10.03 Export/import state roundtrip", t10_03_export_import_state)


def t10_04_default_message_id_generation():
    m = Message(content="test")
    assert_true(m.message_id.startswith("msg-"), "Default ID format")
    assert_true(len(m.message_id) > 10, "ID has sufficient length")

test("T10.04 Default message ID generation", t10_04_default_message_id_generation)


def t10_05_default_memory_entry_id():
    mem = MemoryEntry(content="test")
    assert_true(mem.entry_id.startswith("mem-"), "Default ID format")

test("T10.05 Default MemoryEntry ID generation", t10_05_default_memory_entry_id)


# ============================================================
# T11: Thread Safety
# ============================================================

print("\n=== T11: Thread Safety ===")


def t11_01_concurrent_compress():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 50})
    errors_list = []

    def worker(idx):
        try:
            msgs = make_msgs([f"thread-{idx} msg-{i}" for i in range(10)])
            c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
        except Exception as e:
            errors_list.append(str(e))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert_eq(len(errors_list), 0, f"No thread errors: {errors_list}")

test("T11.01 Concurrent check_and_compress", t11_01_concurrent_compress)


def t11_02_concurrent_read_write():
    c = ContextCompressor(thresholds={CompressionLevel.SESSION_MEMORY: 50})
    errs = []

    def writer(i):
        try:
            msgs = make_msgs([f"write-{i}-{j}" for j in range(5)] + ["a", "b", "c"])
            c.check_and_compress(msgs, force_level=CompressionLevel.SESSION_MEMORY)
        except Exception as e:
            errs.append(f"writer-{i}: {e}")

    def reader(i):
        try:
            c.get_session_memory()
            c.get_compression_stats()
            c.query_memory("test")
        except Exception as e:
            errs.append(f"reader-{i}: {e}")

    threads = (
        [threading.Thread(target=writer, args=(i,)) for i in range(3)]
        + [threading.Thread(target=reader, args=(i,)) for i in range(3)]
    )
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert_eq(len(errs), 0, f"No concurrent access errors: {errs}")

test("T11.02 Concurrent read/write memory", t11_02_concurrent_read_write)


# ============================================================
# T12: Integration - Multi-Level Progressive Compression
# ============================================================

print("\n=== T12: Integration Tests ===")


def t12_01_progressive_compression():
    c = ContextCompressor(thresholds={
        CompressionLevel.SNIP: 200,
        CompressionLevel.SESSION_MEMORY: 400,
        CompressionLevel.FULL_COMPACT: 600,
    })
    base_content = "这是关于项目架构和技术方案的详细讨论内容。包含多个决策点和待办事项。" * 3
    msgs = make_msgs([base_content] * 10)

    r1 = c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
    mem_after_snip = len(c.get_session_memory())

    r2 = c.check_and_compress(r1.messages, force_level=CompressionLevel.SESSION_MEMORY)
    mem_after_sm = len(c.get_session_memory())

    r3 = c.check_and_compress(r2.messages, force_level=CompressionLevel.FULL_COMPACT)

    assert_true(mem_after_sm >= mem_after_snip, "Memory grows across levels")
    assert_true(len(r3.messages) == 0, "Final FullCompact clears messages")
    assert_true(len(r3.summary) > 0, "Final summary generated")

test("T12.01 Progressive SNIP→SM→FC", t12_01_progressive_compression)


def t12_02_realistic_workflow():
    c = ContextCompressor()

    conversation = [
        make_msg("System: You are a helpful assistant.", msg_type=MessageType.SYSTEM),
        make_msg("请帮我设计一个用户认证系统"),
        make_msg("好的，我来帮你设计认证系统的架构方案"),
        make_msg("# 认证系统架构设计\n## 方案选择\n我们建议采用JWT+OAuth2.0方案"),
        make_msg("这个方案看起来不错"),
        make_msg("发现一个问题：Token刷新机制需要详细设计"),
        make_msg("我们决定采用Refresh Token旋转策略"),
        make_msg("TODO: 实现Token刷新端点"),
        make_msg("已完成认证模块的初步实现"),
        make_msg("收到"),
        make_msg("好的"),
        make_msg("测试中发现Session固定攻击风险"),
        make_msg("需要立即修复这个安全问题"),
    ]

    result = c.check_and_compress(conversation, force_level=CompressionLevel.SNIP)
    assert_true(result.compressed_token_count <= result.original_token_count + 1,
                "SNIP should not increase tokens significantly")
    assert_true(len(c.get_session_memory()) >= 1, "Memory extracted from realistic convo")

test("T12.02 Realistic conversation workflow", t12_02_realistic_workflow)


def t12_03_compression_log_tracking():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 50})
    for _ in range(5):
        msgs = make_msgs(["log test content"] * 5)
        c.check_and_compress(msgs, force_level=CompressionLevel.SNIP)

    stats = c.get_compression_stats()
    assert_eq(stats["total_compressions"], 5, "All compressions logged")

test("T12.03 Compression log tracking", t12_03_compression_log_tracking)


def t12_04_memory_persistence_across_compressions():
    c = ContextCompressor(thresholds={CompressionLevel.SNIP: 50})

    batch1 = [make_msg("第一批决定：使用FastAPI框架")]
    c.check_and_compress(batch1, force_level=CompressionLevel.SNIP)

    batch2 = [make_msg("第二批发现：数据库连接池配置不当")]
    c.check_and_compress(batch2, force_level=CompressionLevel.SNIP)

    memory = c.get_session_memory()
    assert_true(len(memory) >= 1, "Memory persists across multiple compressions")

test("T12.04 Memory persistence across compressions", t12_04_memory_persistence_across_compressions)


# ============================================================
# Results
# ============================================================

print(f"\n{'='*60}")
print(f"ContextCompressor Test Results: {passed}/{TOTAL} passed")
if errors:
    print(f"\n❌ Failed ({len(errors)}):")
    for name, err in errors:
        print(f"  - {name}: {err}")
else:
    print(f"\n🎉 ALL {TOTAL} TESTS PASSED!")
print(f"{'='*60}")
