# DevSquad V3.7-V4.0 发展路线图

> ⚠️ Note: The "97% maturity" claim in this document has been re-evaluated. See docs/MATURITY_ASSESSMENT.md for the current honest assessment (72% as of V3.8.0).

> ✅ **V3.8.0 Completed (2026-06-21)**: 6 new modules (TwoStageReviewGate, SeverityRouter, JudgeAgent, MicroTaskPlanner, ContentCache + NodeType/JitterStrategy enhancements) + 226 new tests + 2339 total tests passing. Maturity 65% → 72%. See CHANGELOG.md [3.8.0] for details.

> **文档类型**: 战略规划文档 (Strategic Roadmap)
> **版本**: V1.0.0
> **基于版本**: DevSquad V3.6.1 (94% Production-Ready)
> **目标成熟度**: 97% Enterprise 级
> **创建日期**: 2026-05-20
> **预计周期**: 2026 Q2-Q3 (8-12 周)

---

## 目录索引

1. [执行摘要](#1-执行摘要)
2. [总体目标与里程碑](#2-总体目标与里程碑)
3. [Phase 6: 测试覆盖率提升](#3-phase-6-测试覆盖率提升)
4. [Phase 7: 性能优化](#4-phase-7-性能优化)
5. [Phase 8: 可观测性增强](#5-phase-8-可观测性增强)
6. [Phase 9: 企业级特性](#6-phase-9-企业级特性)
7. [跨 Phase 依赖关系](#7-cross-phase-dependencies)
8. [风险管理与缓解策略](#8-风险管理与缓解策略)
9. [资源需求与时间线](#9-资源需求与时间线)
10. [成功指标与验收标准](#10-成功指标与验收标准)

---

## 1. 执行摘要

### 1.1 当前状态评估

| 维度 | V3.6.1 当前值 | V4.0 目标值 | 差距 | 改进幅度 |
|------|---------------|-------------|------|----------|
| **整体成熟度** | 94% (Production) | **97% (Enterprise)** | +3% | 企业级 |
| **测试覆盖率** | 57.04% | **≥80%** | +23% | 关键 |
| **API 延迟 P99** | ~15s (OpenAI) | **≤7.5s** | -50% | 性能 |
| **可观测性** | 基础日志 | **Prometheus+Tracing** | 生产级 | 运维 |
| **安全合规** | 4级权限 | **RBAC+Audit+Compliance** | 企业级 | 安全 |

### 1.2 战略优先级矩阵

```
高影响 ┃ ┌──────────┐ ┌──────────┐
       ┃ │ Phase 6   │ │ Phase 9   │  ← 高优先级
       ┃ │ 测试覆盖  │ │ 企业级    │
影响   ┃ ├──────────┤ ├──────────┤
程度   ┃ │ Phase 7   │ │ Phase 8   │  ← 中优先级
       ┃ │ 性能优化  │ │ 可观测性  │
低影响 ┃ └──────────┘ └──────────┘
       ┗━━━━━━━━━━━━━┻━━━━━━━━━━━━━┛
            低紧急度        高紧急度
                    紧急程度 →
```

### 1.3 核心价值主张

通过 Phase 6-9 的系统性提升，DevSquad 将从 **"生产可用"** 升级为 **"企业推荐"**：

- ✅ **质量保证**: 覆盖率从 57% 提升至 80%，缺陷检出能力增强 40%
- ✅ **性能突破**: API 响应延迟降低 50%，吞吐量提升 2x
- ✅ **运维友好**: Prometheus + Grafana + Alerting 全链路监控
- ✅ **安全可信**: RBAC + Audit Log + SOC2/GDPR 就绪

---

## 2. 总体目标与里程碑

### 2.1 总体时间线

```
2026 Q2-Q3 Roadmap Timeline
│
├── May 2026 (Week 1-2)     ← Phase 6 启动
│   ├── Week 1: 测试基础设施升级
│   └── Week 2: 核心模块测试补充
│
├── June 2026 (Week 3-5)     ← Phase 6 收尾 + Phase 7 启动
│   ├── Week 3-4: 边缘模块测试 + 性能基线
│   └── Week 5: asyncio 改造
│
├── July 2026 (Week 6-8)     ← Phase 7 收尾 + Phase 8 启动
│   ├── Week 6-7: 缓存优化 + Redis 集成
│   └── Week 8: 可观测性基础
│
├── August 2026 (Week 9-11)  ← Phase 8 收尾 + Phase 9 启动
│   ├── Week 9-10: 监控完善 + RBAC 设计
│   └── Week 11: 审计日志 + 合规
│
└── September 2026 (Week 12) ← Phase 9 收尾 + V4.0 发布准备
    ├── Week 12: 集成测试 + 文档更新
    └── Milestone: V4.0 Beta → Enterprise Ready
```

### 2.2 里程碑定义

| 里程碑 | 计划日期 | 交付物 | 成熟度 | 验收标准 |
|--------|----------|--------|--------|----------|
| **M0: V3.8.0 Code Review & Planning** | 2026-06-21 ✅ | 6 new modules + 226 tests + 5 planning docs | 72% | ✅ TwoStageReviewGate + SeverityRouter + JudgeAgent + MicroTaskPlanner + ContentCache + NodeType/JitterStrategy |
| **M1: 质量基石** | 2026-06-07 | Phase 6 完成 | 96% Stable | 覆盖率 ≥70%, 新增 300+ 测试 |
| **M2: 性能飞跃** | 2026-06-28 | Phase 7 完成 | 96% Stable | P99 延迟降低 50%, QPS 提升 2x |
| **M3: 可观测生产** | 2026-07-19 | Phase 8 完成 | 96% Stable | Prometheus 采集正常, Tracing 可用 |
| **M4: 企业就绪** | 2026-08-30 | Phase 9 完成 | **97% Enterprise** | RBAC+Audit+Compliance 通过 |
| **M5: V4.0 Release** | 2026-09-13 | 全部完成 + 发布 | **97% Enterprise** | 所有 Phase 验收通过 |

### 2.3 V3.8.0 已完成里程碑详情 (2026-06-21)

V3.8.0 是一个独立的代码审查与任务规划增强版本，不在原 Phase 6-9 计划内，但为 V4.0 目标提供了重要基础：

| 增强项 | 模块 | 测试数 | 灵感来源 |
|--------|------|--------|----------|
| #2 Two-Stage Code Review Gate | `two_stage_review_gate.py` | 40 | Superpowers |
| #3 Severity Router + Auto-Fix Loop | `severity_router.py` | 51 | NodeGuard |
| #4 Judge Agent + History Learning | `judge_agent.py` | 33 | Qodo PR-Agent |
| #6 Deterministic vs LLM Step Separation | `NodeType` enum in `WorkflowStep` | 14 | RepoReviewer |
| #7 Micro-Task Planner | `micro_task_planner.py` | 47 | Superpowers |
| #9 Content Cache + Jitter Strategies | `content_cache.py` + `JitterStrategy` | 41 | NodeGuard |

**V3.8.0 关键成果**:
- ✅ 6 个新模块 + 2 个现有模块增强
- ✅ 226 个新测试，总计 2339 passed, 18 skipped
- ✅ 所有新模块 ruff clean，无安全问题
- ✅ 5 个 V3.8 规划文档（2482 行）
- ✅ 成熟度从 65% 提升至 72%（诚实评估）

---

## 3. Phase 6: 测试覆盖率提升

### 3.1 Phase 概览

| 属性 | 值 |
|------|-----|
| **Phase 名称** | 测试覆盖率提升工程 |
| **当前覆盖率** | 57.04% (1680 tests) |
| **第一阶段目标** | **≥70%** (+13%) |
| **最终目标 (V4.0)** | **≥80%** (+23%) |
| **预计新增测试数** | **400-600 个** |
| **预计工作量** | **8-12 小时** |
| **优先级** | 🔴 **P0 - 最高优先级** |
| **依赖项** | 无 (可立即启动) |

### 3.2 覆盖率差距分析

#### 当前零覆盖/低覆盖模块 (Priority Matrix)

| 优先级 | 模块文件 | 当前行数 | 当前覆盖率 | 目标覆盖率 | 预估提升 | 复杂度 |
|--------|----------|----------|------------|------------|----------|--------|
| **P0-Critical** | `dashboard.py` | ~500 lines | **0%** | 60% | +0.6% | 高 (Streamlit) |
| **P0-Critical** | `mcp_server.py` | ~300 lines | **0%** | 75% | +0.4% | 中 (MCP协议) |
| **P0-Critical** | `api_server.py` | ~200 lines | **~10%** | 70% | +0.5% | 中 (FastAPI) |
| **P1-High** | `role_template_market.py` | ~280 lines | **28%** | 65% | +0.6% | 中 |
| **P1-High** | `rule_collector.py` | **400 lines** | **36%** | 60% | +1.0% | 高 |
| **P1-High** | `llm_cache_async.py` | ~180 lines | **45%** | 75% | +0.5% | 中 |
| **P2-Medium** | `cli.py` | ~600 lines | **27%** | 55% | +1.5% | 高 |
| **P2-Medium** | `auth.py` | ~250 lines | **40%** | 70% | +0.5% | 低 |
| **P2-Medium** | `history_manager.py` | ~200 lines | **38%** | 70% | +0.5% | 低 |

**预估总覆盖率提升**: +6.5% (从这些关键模块)

#### 核心模块补强 (已有基础)

| 模块文件 | 当前覆盖率 | 目标覆盖率 | 预估新增测试数 | 优先级 |
|----------|------------|------------|----------------|--------|
| `coordinator.py` | 67% | 82% | +40 tests | P1 |
| `dispatcher.py` | 63% | 78% | +35 tests | P1 |
| `consensus.py` | 70% | 85% | +25 tests | P1 |
| `permission_guard.py` | 73% | 88% | +30 tests | P1 |
| `llm_backend.py` | 72% | 87% | +35 tests | P2 |
| `anchor_checker.py` | 65% | 80% | +25 tests | P2 |
| `retrospective.py` | 60% | 78% | +30 tests | P2 |
| `input_validator.py` | 68% | 85% | +35 tests | P2 |

**预估总覆盖率提升**: +6.5% (从核心模块补强)

### 3.3 新增测试文件清单 (至少 12 个新文件)

#### Tier 1: 零覆盖模块测试 (必须新增)

| # | 测试文件名 | 目标模块 | 预估测试数 | 预估行数 | 测试类型 | 复杂度 |
|---|-----------|----------|------------|----------|----------|--------|
| 1 | `tests/test_dashboard_integration.py` | dashboard.py | **35** | 800 | Integration | ⭐⭐⭐ |
| 2 | `tests/test_mcp_server_integration.py` | mcp_server.py | **40** | 900 | Integration | ⭐⭐ |
| 3 | `tests/test_api_server_routes.py` | api_server.py | **45** | 1000 | Unit+Integration | ⭐⭐ |
| 4 | `tests/test_api_models.py` | api/models.py | **25** | 550 | Unit | ⭐ |
| 5 | `tests/test_auth_manager.py` | auth.py | **30** | 650 | Unit+Integration | ⭐⭐ |

**Tier 1 小计**: **175 tests**, **3900 lines**

#### Tier 2: 低覆盖模块补强 (重要)

| # | 测试文件名 | 目标模块 | 预估测试数 | 预估行数 | 测试类型 | 复杂度 |
|---|-----------|----------|------------|----------|----------|--------|
| 6 | `tests/test_role_template_market.py` | role_template_market.py | **35** | 750 | Unit | ⭐⭐ |
| 7 | `tests/test_rule_collector.py` | rule_collector.py | **40** | 850 | Unit | ⭐⭐⭐ |
| 8 | `tests/test_cli_comprehensive.py` | cli.py | **50** | 1100 | Unit+Integration | ⭐⭐⭐ |
| 9 | `tests/test_llm_cache_async.py` | llm_cache_async.py | **30** | 650 | Unit+Async | ⭐⭐ |
| 10 | `tests/test_history_manager.py` | history_manager.py | **25** | 550 | Unit | ⭐ |

**Tier 2 小计**: **180 tests**, **3900 lines**

#### Tier 3: 核心模块深度测试 (质量提升)

| # | 测试文件名 | 目标模块 | 预估测试数 | 预估行数 | 测试类型 | 复杂度 |
|---|-----------|----------|------------|----------|----------|--------|
| 11 | `tests/test_coordinator_deep.py` | coordinator.py | **40** | 900 | Integration | ⭐⭐⭐ |
| 12 | `tests/test_dispatcher_edge_cases.py` | dispatcher.py | **35** | 800 | Unit | ⭐⭐ |
| 13 | `tests/test_consensus_boundary.py` | consensus.py | **30** | 700 | Unit | ⭐⭐ |
| 14 | `tests/test_permission_guard_extended.py` | permission_guard.py | **35** | 750 | Unit+Integration | ⭐⭐ |
| 15 | `tests/test_anchor_retrospective_integration.py` | anchor+retrospective | **30** | 700 | Integration | ⭐⭐ |

**Tier 3 小计**: **170 tests**, **3850 lines**

#### Tier 4: 辅助模块测试 (完整性)

| # | 测试文件名 | 目标模块 | 预估测试数 | 预估行数 | 测试类型 | 复杂度 |
|---|-----------|----------|------------|----------|----------|--------|
| 16 | `tests/test_code_quality_tool.py` | code_quality.py | **20** | 450 | Unit | ⭐ |
| 18 | `tests/test_feature_usage_tracker.py` | feature_usage_tracker.py | **25** | 550 | Unit | ⭐ |

**Tier 4 小计**: **70 tests**, **1550 lines**

#### 📊 测试文件汇总统计

| Tier | 文件数 | 测试数 | 代码行 | 覆盖率贡献 |
|------|--------|--------|--------|------------|
| **Tier 1 (Critical)** | 5 | 175 | 3,900 | +1.5% |
| **Tier 2 (Important)** | 5 | 180 | 3,900 | +2.5% |
| **Tier 3 (Deep)** | 5 | 170 | 3,850 | +4.5% |
| **Tier 4 (Complete)** | 3 | 70 | 1,550 | +1.5% |
| **总计** | **18 files** | **595 tests** | **13,200 lines** | **+10%** |

### 3.4 详细 WBS (Work Breakdown Structure)

```
Phase 6: Test Coverage Enhancement
│
├── 6.1 测试基础设施升级 (2h)
│   ├── 6.1.1 pytest 配置优化 (.coveragerc, conftest 增强)
│   ├── 6.1.2 Mock/Fixture 工厂模式统一
│   ├── 6.1.3 CI Pipeline 集成 (coverage gate)
│   └── 6.1.4 测试数据生成器 (factory_boy 或自定义)
│
├── 6.2 零覆盖模块攻坚 (4h)
│   ├── 6.2.1 Dashboard E2E 测试框架搭建 (Streamlit testing)
│   │   ├── 安装 streamlit-testing 或 playwright
│   │   ├── 编写组件交互测试
│   │   └── 验证 UI 渲染和数据绑定
│   ├── 6.2.2 MCP Server 集成测试
│   │   ├── MCP Client mock 创建
│   │   ├── Tool 调用/响应验证
│   │   └── 错误处理路径测试
│   └── 6.2.3 API Server FastAPI TestClient 测试
│       ├── 所有端点 request/response 验证
│       ├── 认证中间件测试
│       └── 错误码和异常场景
│
├── 6.3 低覆盖模块补强 (3h)
│   ├── 6.3.1 CLI 参数解析边界测试
│   ├── 6.3.2 Role Template Market 全路径覆盖
│   ├── 6.3.3 Rule Collector 规则匹配矩阵
│   └── 6.3.4 Async LLM Cache 并发安全测试
│
├── 6.4 核心模块深度测试 (2h)
│   ├── 6.4.1 Coordinator 异常恢复路径
│   ├── 6.4.2 Consensus 投票边界条件
│   ├── 6.4.3 Permission Guard 权限矩阵完整验证
│   └── 6.4.4 Anchor Checker 偏移检测精度
│
└── 6.5 验证与收尾 (1h)
    ├── 6.5.1 覆盖率报告生成 (--cov-report=html)
    ├── 6.5.2 缺失分支识别和补充
    ├── 6.5.3 CI Gate 调整 (cov-fail-under=70)
    └── 6.5.4 文档更新 (TESTING.md)
```

### 3.5 技术方案选择

#### Dashboard 测试方案

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **Playwright E2E** | 真实浏览器测试 | 依赖浏览器环境 | ⭐⭐⭐ 推荐 |
| **streamlit-testing** | Streamlit 原生支持 | 库较新，生态不成熟 | ⭐⭐ 备选 |
| **Component Mock** | 快速，无 UI 依赖 | 不测试真实渲染 | ⭐ 辅助 |

**推荐策略**: Playwright for critical paths + Component Mock for unit logic

```python
# 示例: test_dashboard_integration.py
import pytest
from playwright.sync_api import sync_playwright

class TestDashboardE2E:
    """Dashboard 端到端测试"""

    def test_lifecycle_page_renders(self):
        """验证生命周期页面正确渲染"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto("http://localhost:8501")
            # 验证核心元素存在
            expect(page.locator("#lifecycle-status")).to_be_visible()
            browser.close()

    def test_dispatch_button_click(self):
        """验证调度按钮交互"""
        # 测试表单提交和结果展示
        ...
```

#### MCP Server 测试方案

```python
# 示例: test_mcp_server_integration.py
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class TestMCPServerIntegration:
    """MCP Server 集成测试"""

    @pytest.fixture
    def mcp_client(self):
        server_params = StdioServerParameters(
            command="python",
            args=["scripts/mcp_server.py"]
        )
        with stdio_client(server_params) as (read, write):
            with ClientSession(read, write) as session:
                yield session

    async def test_multiagent_dispatch_tool(self, mcp_client):
        """验证 dispatch tool 正确执行"""
        result = await mcp_client.call_tool("multiagent_dispatch", {
            "task": "test task",
            "roles": ["architect"],
            "mode": "auto"
        })
        assert len(result.content) > 0
        assert "finding" in result.content[0].text.lower()

    async def test_multiagent_roles_tool(self, mcp_client):
        """验证 roles tool 返回所有角色"""
        result = await mcp_client.call_tool("multiagent_roles")
        assert "architect" in result.content[0].text
```

#### API Server 测试方案

```python
# 示例: test_api_server_routes.py
from fastapi.testclient import TestClient
from scripts.api_server import app

client = TestClient(app)

class TestAPIRoutes:
    """FastAPI 路由测试"""

    def test_health_check(self):
        """健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_dispatch_endpoint(self):
        """调度端点完整流程"""
        response = client.post("/api/v1/dispatch", json={
            "task": "test task",
            "roles": ["architect"],
            "mode": "auto",
            "backend": "mock"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data

    def test_lifecycle_phases(self):
        """生命周期阶段查询"""
        response = client.get("/api/v1/lifecycle/phases")
        assert response.status_code == 200
        phases = response.json()
        assert len(phases) >= 6  # 至少 6 个主要阶段

    def test_metrics_endpoint(self):
        """指标端点返回有效数据"""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        metrics = response.json()
        assert "dispatch_count" in metrics
```

### 3.6 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Streamlit 测试环境搭建困难 | 中 | 高 | 使用 Playwright 替代，或降低 coverage 目标至 40% |
| MCP SDK 版本兼容性问题 | 低 | 中 | 固定版本号，使用 virtual environment |
| 测试运行时间过长 (>5min) | 中 | 低 | 并行测试 (pytest-xdist), 分离 slow markers |
| Mock 数据与真实行为偏差 | 中 | 中 | 定期对照真实 LLM 后端验证 |
| 覆盖率目标未达 70% | 低 | 高 | 优先保证 P0 模块，调整 P3/P4 范围 |

### 3.7 验收标准

- [ ] **主指标**: `pytest --cov` 报告总体覆盖率 ≥ **70%**
- [ ] **新增测试**: ≥ **400 个新测试用例**通过
- [ ] **通过率**: ≥ **99%** (允许 ≤4 个已知边界失败)
- [ ] **零覆盖模块**: `dashboard.py`, `mcp_server.py`, `api_server.py` 覆盖率 > **40%**
- [ ] **CI 集成**: GitHub Actions 自动运行并报告覆盖率
- [ ] **代码质量**: Ruff/Mypy 无新增 errors
- [ ] **文档**: 更新 TEST_STRATEGY.md 和 CONTRIBUTING.md

---

## 4. Phase 7: 性能优化

### 4.1 Phase 概览

| 属性 | 值 |
|------|-----|
| **Phase 名称** | Performance Optimization & Async Migration |
| **当前瓶颈** | 同步阻塞 I/O, 单进程缓存, GIL 限制 |
| **性能目标** | **吞吐量 2x, 延迟 -50%** |
| **预计工作量** | **6-8 小时** |
| **优先级** | 🟠 **P1 - 高优先级** |
| **依赖项** | Phase 6 (可选但建议先完成) |

### 4.2 性能基线建立

#### 当前性能基准 (需在优化前测量)

```bash
# 性能基准测试脚本 (scripts/generate_benchmark_report.py)
python scripts/generate_benchmark_report.py --output baseline_v361.json
```

**基线指标采集点**:

| 场景 | 指标 | 当前值 (估计) | 测量方法 |
|------|------|---------------|----------|
| Single Task (Mock) | Latency P50 | ~50ms | time.perf_counter() |
| Single Task (Mock) | Latency P99 | ~100ms | time.perf_counter() |
| Single Task (OpenAI) | Latency P50 | ~3-5s | OpenAI API timing |
| Single Task (OpenAI) | Latency P99 | ~15s | OpenAI API timing |
| 3-Role Parallel | Total Time | ~5-12s | Coordinator timer |
| 7-Role Consensus | Total Time | ~15-30s | ConsensusEngine timer |
| Throughput (Mock) | QPS | ~20 req/s | Load test script |
| Memory Usage | RSS | ~150-500MB | psutil.Process |

#### Benchmark 自动化脚本设计

```python
# scripts/perf_benchmark.py
"""Performance Benchmark Suite for DevSquad V3.7+"""

import asyncio
import time
import statistics
from dataclasses import dataclass
from typing import List

@dataclass
class BenchmarkResult:
    scenario: str
    iterations: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float
    throughput_qps: float
    memory_mb: float

class PerformanceBenchmark:
    """自动化性能基准测试"""

    SCENARIOS = [
        "single_task_mock",
        "single_task_openai",
        "parallel_3_roles",
        "consensus_7_roles",
        "batch_dispatch_10",
        "cache_hit_path",
        "cache_miss_path",
    ]

    async def run_scenario(self, scenario: str, iterations: int = 100) -> BenchmarkResult:
        """运行单个基准场景"""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            await self._execute_scenario(scenario)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        times.sort()
        return BenchmarkResult(
            scenario=scenario,
            iterations=iterations,
            p50_ms=times[len(times)//2],
            p95_ms=times[int(len(times)*0.95)],
            p99_ms=times[int(len(times)*0.99)] if len(times) > 1 else times[-1],
            mean_ms=statistics.mean(times),
            min_ms=min(times),
            max_ms=max(times),
            throughput_qps=iterations / (sum(times)/1000),
            memory_mb=self._get_memory_usage(),
        )

    def generate_report(self, results: List[BenchmarkResult]) -> str:
        """生成 Markdown 格式的基准报告"""
        ...
```

### 4.3 asyncio 改造计划

#### 需要异步化的模块 (按优先级)

| 优先级 | 模块 | 当前状态 | 改造内容 | 预期收益 | 复杂度 |
|--------|------|----------|----------|----------|--------|
| **P0** | `llm_backend.py` | 同步 HTTP | `aiohttp` / `httpx.AsyncClient` | **延迟 -50%** | ⭐⭐⭐ |
| **P0** | `llm_retry.py` | 同步重试 | `asyncio.sleep` + 异步重试 | **可靠性 ↑** | ⭐⭐ |
| **P1** | `coordinator.py` | 串行编排 | `asyncio.gather` 并行 Worker | **吞吐量 2x** | ⭐⭐⭐ |
| **P1** | `dispatcher.py` | 同步入口 | `async dispatch()` API | **接口现代化** | ⭐⭐ |
| **P2** | `batch_scheduler.py` | ThreadPool | `asyncio.Semaphore` 并发控制 | **资源效率 ↑** | ⭐⭐ |
| **P2** | `scratchpad.py` | 内存操作 | `asyncio.Lock` 保护并发写入 | **线程安全** | ⭐ |
| **P3** | `api_server.py` | FastAPI sync | 原生 async endpoints | **QPS ↑** | ⭐ |

#### 异步改造架构设计

```
Async Architecture (V3.7+)
│
├── Layer 1: Async LLM Backend
│   ├── class AsyncLLMBackend(LLMBackend)
│   │   ├── async call_async(prompt: str) -> str
│   │   ├── async batch_call_async(prompts: list) -> list[str]
│   │   └── Connection pool (aiohttp.TCPConnector)
│   │
│   └── Backward Compatibility Layer
│       ├── sync_call() → asyncio.run(async version)
│       └── DeprecationWarning for sync methods
│
├── Layer 2: Async Coordinator
│   ├── class AsyncCoordinator(Coordinator)
│   │   ├── async plan_task_async() -> ExecutionPlan
│   │   ├── async execute_plan_async() -> ScheduleResult
│   │   └── async gather_results(workers) -> list[WorkerResult]
│   │
│   └── Concurrency Control
│       ├── max_concurrency = os.cpu_count() * 2
│       ├── semaphore = asyncio.Semaphore(max_concurrency)
│       └── timeout_handler per task
│
└── Layer 3: Async API Layer
    ├── @app.post("/api/v1/dispatch")  # native async
    ├── async def dispatch_endpoint(request: DispatchRequest):
    │   result = await async_dispatcher.dispatch_async(...)
    │   return JSONResponse(result)
    │
    └── Streaming support (optional, SSE/WebSocket)
```

#### 核心异步改造示例

```python
# scripts/collaboration/llm_backend_async.py (NEW FILE)
"""Asynchronous LLM Backend for V3.7+ Performance Optimization."""

import asyncio
from typing import Any
import aiohttp
from scripts.collaboration.llm_backend import LLMBackend, LLMResponse

class AsyncLLMBackend:
    """High-performance async LLM backend using aiohttp.

    Features:
    - Connection pooling (default: 10 connections)
    - Automatic retry with exponential backoff
    - Request queuing and concurrency limiting
    - Timeout handling per-request
    """

    def __init__(
        self,
        backend_type: str = "openai",
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        max_connections: int = 10,
        timeout_seconds: float = 120.0,
    ):
        self.backend_type = backend_type
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.max_connections = max_connections
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session: aiohttp.ClientSession | None = None
        self._stats = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "total_latency_ms": 0.0,
        }

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=self.max_connections,
            limit_per_host=self.max_connections,
            enable_cleanup_closed=True,
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def call_async(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """Async LLM call with connection pooling.

        Args:
            prompt: User message
            system_prompt: System context
            temperature: Sampling temperature
            max_tokens: Max response tokens

        Returns:
            LLMResponse with content and metadata
        """
        start_time = asyncio.get_event_loop().time()
        self._stats["requests_total"] += 1

        try:
            if self.backend_type == "openai":
                response = await self._call_openai_async(
                    prompt, system_prompt, temperature, max_tokens
                )
            elif self.backend_type == "anthropic":
                response = await self._call_anthropic_async(
                    prompt, system_prompt, temperature, max_tokens
                )
            else:
                raise ValueError(f"Unsupported backend: {self.backend_type}")

            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            self._stats["requests_success"] += 1
            self._stats["total_latency_ms"] += latency_ms
            response.latency_ms = latency_ms
            return response

        except Exception as e:
            self._stats["requests_failed"] += 1
            raise

    async def _call_openai_async(self, prompt, system_prompt, temp, max_tok):
        """OpenAI async API call."""
        url = f"{self.base_url or 'https://api.openai.com'}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model or "gpt-4",
            "messages": [
                {"role": "system", "content": system_prompt or ""},
                {"role": "user", "content": prompt},
            ],
            "temperature": temp,
            "max_tokens": max_tok,
        }

        async with self._session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                usage=data.get("usage", {}),
            )

    async def batch_call_async(
        self,
        prompts: list[str],
        concurrency: int = 5,
    ) -> list[LLMResponse]:
        """Batch async calls with controlled concurrency.

        Args:
            prompts: List of prompts to process
            concurrency: Max parallel requests

        Returns:
            List of LLMResponses in order
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _bounded_call(prompt: str) -> LLMResponse:
            async with semaphore:
                return await self.call_async(prompt)

        tasks = [_bounded_call(p) for p in prompts]
        return await asyncio.gather(*tasks)

    def get_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        stats = self._stats.copy()
        if stats["requests_success"] > 0:
            stats["avg_latency_ms"] = (
                stats["total_latency_ms"] / stats["requests_success"]
            )
        return stats
```

### 4.4 Redis/Memcached 缓存后端集成

#### 缓存架构升级

```
Cache Architecture Evolution (V3.6 → V3.7)
│
├── Current (V3.6.1): In-Memory + File-based
│   ├── L1 Cache: dict[str, str] (process-local)
│   ├── L2 Cache: JSON files on disk
│   └── Limitations:
│       ├── No cross-process sharing
│       ├── Memory unbounded growth
│       └── No TTL eviction policy
│
└── Target (V3.7+): Multi-tier Distributed Cache
    ├── L1 Cache: dict[str, str] (process-local, fast path)
    │   └── TTL: 5 minutes, max 10K entries
    │
    ├── L2 Cache: Redis (shared, persistent)
    │   ├── Host: configurable (localhost / cluster)
    │   ├── TTL: 1 hour default
    │   ├── Max memory: 256MB (configurable)
    │   └── Eviction: allkeys-lru
    │
    └── Fallback Chain:
        └── L1 miss → L2 (Redis) → L2 miss → LLM Call → Store to L1+L2
```

#### Redis 集成实现

```python
# scripts/collaboration/redis_cache.py (NEW FILE)
"""Redis-backed distributed cache for V3.7+."""

import json
import hashlib
from typing import Any, Optional
import redis.asyncio as aioredis

class RedisCacheBackend:
    """Redis cache backend with async support.

    Features:
    - Async operations (aioredis)
    - Automatic serialization/deserialization
    - Key namespace isolation
    - TTL management
    - Statistics tracking
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "devsquad:",
        default_ttl: int = 3600,
        max_memory_mb: int = 256,
    ):
        self.redis_url = redis_url
        self.prefix = prefix
       .default_ttl = default_ttl
        self.max_memory_mb = max_memory_mb
        self._redis: Optional[aioredis.Redis] = None
        self._stats = {"hits": 0, "misses": 0, "sets": 0}

    async def connect(self):
        """Establish Redis connection."""
        self._redis = aioredis.from_url(
            self.redis_url,
            decode_responses=True,
            max_connections=20,
        )
        # Test connection
        await self._redis.ping()

    async def disconnect(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

    def _make_key(self, cache_key: str) -> str:
        """Generate namespaced cache key."""
        hash_prefix = hashlib.sha256(cache_key.encode()).hexdigest()[:12]
        return f"{self.prefix}{hash_prefix}:{cache_key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        redis_key = self._make_key(key)
        value = await self._redis.get(redis_key)
        if value is not None:
            self._stats["hits"] += 1
            return json.loads(value)
        self._stats["misses"] += 1
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set value in cache with TTL."""
        redis_key = self._make_key(key)
        serialized = json.dumps(value, default=str)
        ttl = ttl or self.default_ttl
        result = await self._redis.setex(redis_key, ttl, serialized)
        if result:
            self._stats["sets"] += 1
        return result

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        redis_key = self._make_key(key)
        return await self._redis.delete(redis_key) > 0

    async def clear_namespace(self) -> int:
        """Clear all keys with our prefix."""
        keys = await self._redis.keys(f"{self.prefix}*}")
        if keys:
            return await self._redis.delete(*keys)
        return 0

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        return {
            **self._stats,
            "hit_rate": self._stats["hits"] / total if total > 0 else 0,
            "total_requests": total,
        }
```

#### 缓存配置集成

```yaml
# config/cache_config.yaml (NEW FILE)
# V3.7+ Cache Configuration

cache:
  # L1: In-memory (fast, local)
  l1:
    enabled: true
    max_entries: 10000
    ttl_seconds: 300  # 5 minutes

  # L2: Redis (distributed, shared)
  l2:
    enabled: true
    backend: "redis"  # redis | memcached | none
    url: "${REDIS_URL:-redis://localhost:6379/0}"
    prefix: "devsquad:v3:"
    default_ttl_seconds: 3600  # 1 hour
    max_memory_mb: 256
    connection_pool_size: 20

  # Fallback behavior
  fallback_on_error: true  # If Redis down, skip cache (don't block)
```

### 4.5 连接池优化

#### HTTP 连接池配置

```python
# Optimal connection pool settings for different backends
CONNECTION_POOL_CONFIG = {
    "openai": {
        "limit": 20,           # Max connections
        "limit_per_host": 10,  # Per-host limit
        "ttl_dns_cache": 300,  # DNS cache TTL
        "enable_cleanup_closed": True,
    },
    "anthropic": {
        "limit": 15,
        "limit_per_host": 8,
        "ttl_dns_cache": 300,
        "enable_cleanup_closed": True,
    },
}
```

### 4.6 WBS 与时间估算

```
Phase 7: Performance Optimization
│
├── 7.1 性能基线建立 (1h)
│   ├── 7.1.1 编写 benchmark 脚本
│   ├── 7.1.2 采集当前性能数据
│   └── 7.1.3 建立基线报告 (baseline_v361.json)
│
├── 7.2 asyncio 核心改造 (3h)
│   ├── 7.2.1 AsyncLLMBackend 实现 (aiohttp)
│   ├── 7.2.2 AsyncCoordinator 并行化
│   ├── 7.2.3 向后兼容层 (sync wrapper)
│   └── 7.2.4 API 层 async endpoints
│
├── 7.3 缓存系统升级 (2h)
│   ├── 7.3.1 RedisCacheBackend 实现
│   ├── 7.3.2 多级缓存协调器 (L1→L2→LLM)
│   ├── 7.3.3 Docker Compose Redis 服务
│   └── 7.3.4 缓存失效策略
│
├── 7.4 性能调优 (1h)
│   ├── 7.4.1 连接池参数调优
│   ├── 7.4.2 并发控制 (Semaphore)
│   └── 7.4.3 内存优化 (对象池)
│
└── 7.5 验证与回归 (1h)
    ├── 7.5.1 运行 benchmark 对比
    ├── 7.5.2 性能报告生成
    ├── 7.5.3 回归测试 (功能不受影响)
    └── 7.5.4 文档更新 (PERFORMANCE.md)
```

### 4.7 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| asyncio 改造引入新 bug | 中 | 高 | 充分单元测试，保持同步兼容层 |
| Redis 单点故障 | 低 | 高 | fallback_on_error=True，降级到 L1 |
| 性能提升未达 2x | 中 | 中 | 调整目标为 1.5x，重点优化热点路径 |
| 向后兼容性破坏 | 低 | 高 | 渐进式迁移，deprecation warning |
| 内存泄漏 (连接池) | 低 | 中 | 使用 context manager，定期清理 |

### 4.8 验收标准

- [ ] **延迟指标**: P99 延迟降低 **≥50%** (对比基线)
- [ ] **吞吐量指标**: QPS 提升 **≥2x** (Mock 模式)
- [ ] **缓存命中率**: L1+L2 综合命中率 **≥60%**
- [ ] **稳定性**: 1000 次连续请求无内存泄漏
- [ ] **向后兼容**: 现有同步 API 正常工作 (deprecation warning only)
- [ ] **Redis 集成**: 可选启用，禁用时功能正常
- [ ] **Benchmark 报告**: 生成 before/after 对比报告

---

## 5. Phase 8: 可观测性增强

### 5.1 Phase 概览

| 属性 | 值 |
|------|-----|
| **Phase 名称** | Observability Enhancement (Production-Grade Monitoring) |
| **当前状态** | 基础 logging (print→logging), 手动 metrics |
| **目标状态** | **结构化 JSON logging + Prometheus + OpenTelemetry Tracing** |
| **预计工作量** | **4-6 小时** |
| **优先级** | 🟡 **P2 - 中优先级** (依赖 Phase 7 性能优化) |
| **依赖项** | Phase 6 (可选), Phase 7 (推荐) |

### 5.2 结构化 JSON Logging

#### 日志格式标准化

```json
{
  "timestamp": "2026-05-20T14:30:00.000Z",
  "level": "INFO",
  "logger": "scripts.collaboration.dispatcher",
  "message": "Task dispatched successfully",
  "context": {
    "task_id": "task-abc123",
    "roles": ["architect", "coder"],
    "mode": "parallel",
    "duration_ms": 5234.5,
    "worker_count": 2
  },
  "trace_id": "abc-def-123-456",
  "span_id": "span-789",
  "environment": "production",
  "version": "3.7.0"
}
```

#### Logging 实现方案

```python
# scripts/collaboration/structured_logger.py (NEW FILE)
"""Structured JSON Logger for V3.7+ Observability."""

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter.

    Outputs logs in machine-parseable JSON format for ELK/Loki/Promtail.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "context": getattr(record, "context", {}),
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
            "environment": getattr(record, "environment", "development"),
            "version": "3.7.0",
        }

        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "stacktrace": traceback.format_exc(),
            }

        if record.args:
            log_entry["args"] = {k: str(v) for k, v in record._args.items()} if hasattr(record, '_args') else {}

        return json.dumps(log_entry, ensure_ascii=False)


def setup_structured_logging(
    level: str = "INFO",
    format: str = "json",  # "json" | "text"
    output: str = "stdout",  # "stdout" | "file"
    file_path: Optional[str] = None,
) -> logging.Logger:
    """Configure structured logging for the application.

    Args:
        level: Log level (DEBUG/INFO/WARNING/ERROR)
        format: Output format
        output: Output destination
        file_path: Path for file output (if output="file")

    Returns:
        Configured root logger
    """
    logger = logging.getLogger("devsquad")
    logger.setLevel(getattr(logging, level.upper()))

    if format == "json":
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    if output == "file" and file_path:
        handler = logging.FileHandler(file_path)
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
```

### 5.3 Prometheus Metrics Endpoint

#### 指标设计

```python
# scripts/api/routes/prometheus_metrics.py (NEW FILE)
"""Prometheus metrics endpoint for V3.7+."""

import time
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Response
from fastapi.routing import APIRouter

router = APIRouter(prefix="/metrics", tags=["monitoring"])

# ===== Business Metrics =====

dispatch_total = Counter(
    "devsquad_dispatch_total",
    "Total number of task dispatches",
    ["mode", "backend", "status"],  # labels
)

dispatch_duration_seconds = Histogram(
    "devsquad_dispatch_duration_seconds",
    "Time spent on task dispatch",
    ["mode", "backend"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 15, 30, 60, 120],
)

consensus_rounds_total = Counter(
    "devsquad_consensus_rounds_total",
    "Total number of consensus voting rounds",
    ["outcome"],  # approved/rejected/split/escalated
)

# ===== Resource Metrics =====

active_workers = Gauge(
    "devsquad_active_workers",
    "Number of currently active workers",
)

queue_depth = Gauge(
    "devsquad_queue_depth",
    "Current task queue depth",
)

memory_usage_bytes = Gauge(
    "devsquad_memory_usage_bytes",
    "Current memory usage in bytes",
)

cpu_usage_percent = Gauge(
    "devsquad_cpu_usage_percent",
    "Current CPU usage percentage",
)

# ===== Quality Metrics =====

cache_hits_total = Counter(
    "devsquad_cache_hits_total",
    "Total cache hits",
    ["cache_level"],  # l1 | l2
)

cache_misses_total = Counter(
    "devsquad_cache_misses_total",
    "Total cache misses",
    ["cache_level"],
)

conflicts_detected_total = Counter(
    "devsquad_conflicts_detected_total",
    "Total conflicts detected between workers",
)

escalations_total = Counter(
    "devsquad_escalations_total",
    "Total escalations to human intervention",
)

# ===== System Info =====

app_info = Info(
    "devsquad_application",
    "DevSquad application information",
)

app_info.info({
    "version": "3.7.0",
    "environment": "production",
})


@router.get("")
async def get_metrics():
    """Expose Prometheus metrics endpoint.

    Access at: GET /metrics
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@router.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes liveness probe."""
    return {"status": "healthy", "timestamp": time.time()}


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint for Kubernetes readiness probe."""
    # Check dependencies (Redis, etc.)
    ready = True
    # TODO: Add actual dependency checks
    return {"status": "ready" if ready else "not_ready"}
```

#### Grafana Dashboard 配置建议

```yaml
# config/grafana_dashboard.json (参考配置)
{
  "dashboard": {
    "title": "DevSquad Monitoring Dashboard",
    "panels": [
      {
        "title": "Dispatch Rate (req/min)",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(devsquad_dispatch_total[5m]) * 60",
            "legendFormat": "{{mode}}-{{backend}}"
          }
        ]
      },
      {
        "title": "Dispatch Latency (P99)",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(devsquad_dispatch_duration_seconds_bucket[5m]))",
            "legendFormat": "{{mode}}"
          }
        ]
      },
      {
        "title": "Success Rate (%)",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(rate(devsquad_dispatch_total{status=\"success\"}[5m])) / sum(rate(devsquad_dispatch_total[5m])) * 100",
            "legendFormat": "Success Rate"
          }
        ]
      },
      {
        "title": "Active Workers",
        "type": "gauge",
        "targets": [
          {
            "expr": "devsquad_active_workers",
            "legendFormat": "Workers"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(rate(devsquad_cache_hits_total[5m])) / (sum(rate(devsquad_cache_hits_total[5m])) + sum(rate(devsquad_cache_misses_total[5m]))) * 100",
            "legendFormat": "Hit Rate %"
          }
        ]
      }
    ]
  }
}
```

### 5.4 OpenTelemetry Distributed Tracing

#### 集成方案

```python
# scripts/collaboration/tracing.py (NEW FILE)
"""OpenTelemetry tracing integration for V3.7+."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.aiohttp_client import AiohttpInstrumentor
from opentelemetry.semconv.resource import ResourceAttributes

def setup_tracing(
    service_name: str = "devsquad-api",
    otlp_endpoint: str = "http://localhost:4317",
    environment: str = "production",
):
    """Initialize OpenTelemetry tracing.

    Args:
        service_name: Service name for tracing
        otlp_endpoint: OTLP collector endpoint
        environment: Environment tag (dev/staging/prod)
    """
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: environment,
        ResourceAttributes.SERVICE_VERSION: "3.7.0",
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI and aiohttp
    FastAPIInstrumentor().instrument()
    AiohttpInstrumentor().instrument()


# Usage example in dispatcher
tracer = trace.get_tracer(__name__)

async def traced_dispatch(task: str, roles: list[str]):
    """Traced dispatch function."""
    with tracer.start_as_current_span("dispatch") as span:
        span.set_attribute("task.length", len(task))
        span.set_attribute("roles.count", len(roles))

        with tracer.start_as_current_span("plan_task"):
            plan = await coordinator.plan_task_async(task, roles)

        with tracer.start_as_current_span("execute_plan"):
            result = await coordinator.execute_plan_async(plan)

        span.set_attribute("result.success", result.success)
        return result
```

### 5.5 Alert Rules 定义

```yaml
# config/alerts.yaml (Enhanced for V3.7+)
groups:
  - name: devsquad_critical
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(devsquad_dispatch_total{status="error"}[5m]) / rate(devsquad_dispatch_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "DevSquad error rate > 5%"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: HighLatencyP99
        expr: histogram_quantile(0.99, rate(devsquad_dispatch_duration_seconds_bucket[5m])) > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "DevSquad P99 latency > 30s"
          description: "P99 latency is {{ $value }}s"

      - alert: LowCacheHitRate
        expr: |
          sum(rate(devsquad_cache_hits_total[5m]))
          /
          (sum(rate(devsquad_cache_hits_total[5m])) + sum(rate(devsquad_cache_misses_total[5m])))
          < 0.3
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate < 30%"
          description: "Consider checking cache configuration"

      - alert: HighMemoryUsage
        expr: devsquad_memory_usage_bytes / 1024 / 1024 / 1024 > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Memory usage > 2GB"
          description: "Current usage: {{ $value }}GB"

      - alert: NoDispatches
        expr: rate(devsquad_dispatch_total[10m]) == 0
        for: 15m
        labels:
          severity: info
        annotations:
          summary: "No dispatches in last 15 minutes"
          description: "System may be idle or experiencing issues"
```

### 5.6 WBS 与时间估算

```
Phase 8: Observability Enhancement
│
├── 8.1 结构化日志 (1.5h)
│   ├── 8.1.1 StructuredFormatter 实现
│   ├── 8.1.2 全局 logging 配置
│   ├── 8.1.3 敏感信息脱敏 (passwords, keys)
│   └── 8.1.4 日志轮转配置 (RotatingFileHandler)
│
├── 8.2 Prometheus 集成 (2h)
│   ├── 8.2.1 Metrics 定义 (Counter/Histogram/Gauge)
│   ├── 8.2.2 /metrics endpoint 实现
│   ├── 8.2.3 业务逻辑埋点 (dispatch/consensus/cache)
│   └── 8.2.4 Grafana dashboard JSON 导出
│
├── 8.3 分布式追踪 (1.5h)
│   ├── 8.3.1 OpenTelemetry SDK 集成
│   ├── 8.3.2 关键路径 Span 注入
│   ├── 8.3.3 FastAPI auto-instrumentation
│   └── 8.3.4 Jaeger/Zipkin exporter 配置
│
└── 8.4 告警系统 (0.5h)
    ├── 8.4.1 Alert rules 定义 (YAML)
    ├── 8.4.2 Slack/PagerDuty webhook 配置
    └── 8.4.3 告警静默规则 (维护窗口)
```

### 5.7 验收标准

- [ ] **日志格式**: 所有日志输出为 **结构化 JSON**
- [ ] **Prometheus**: `/metrics` 端点暴露 **≥15 个指标**
- [ ] **Grafana**: 提供 **即用型 dashboard** JSON
- [ ] **Tracing**: 关键路径 (dispatch→plan→execute) **完整 trace**
- [ ] **告警**: ≥ **5 条 alert rules** 生效
- [ ] **性能开销**: Logging/Tracing 开销 **<5% CPU**

---

## 6. Phase 9: 企业级特性

### 6.1 Phase 概览

| 属性 | 值 |
|------|-----|
| **Phase 名称** | Enterprise-Grade Security & Compliance |
| **当前权限模型** | PermissionGuard (4级: READONLY/OPERATOR/ADMIN/SUPERADMIN) |
| **目标模型** | **RBAC + Audit Log + Multi-tenancy + Compliance** |
| **最终成熟度** | **97% Enterprise** |
| **预计工作量** | **8-10 小时** |
| **优先级** | 🔴 **P0 (与 Phase 6 并列)** |
| **依赖项** | Phase 6 (测试保障), Phase 8 (审计日志需要) |

### 6.2 RBAC 细粒度权限设计

#### 权限模型扩展 (基于现有 PermissionGuard)

```
Permission Model Evolution (V3.6 → V4.0)
│
├── Current (V3.6.1): Coarse-grained 4-level
│   ├── Level 1: READONLY (只读)
│   ├── Level 2: OPERATOR (操作员)
│   ├── Level 3: ADMIN (管理员)
│   └── Level 4: SUPERADMIN (超级管理员)
│   Limitation: 粒度过粗，无法精确控制单个操作
│
└── Target (V4.0): Fine-grained RBAC
    ├── Roles (角色)
    │   ├── viewer: 只读访问
    │   ├── operator: 执行任务
    │   ├── analyst: 查看报告和指标
    │   ├── admin: 用户和配置管理
    │   └── super_admin: 全部权限
    │
    ├── Permissions (权限点)
    │   ├── dispatch:create / dispatch:read / dispatch:delete
    │   ├── lifecycle:advance / lifecycle:block
    │   ├── config:read / config:write
    │   ├── user:create / user:read / user:update / user:delete
    │   ├── audit:read
    │   └── system:shutdown / system:backup
    │
    └── Policies (策略)
        ├── Role-Permission Binding
        ├── Resource-level ACL (特定任务的访问控制)
        ├── Time-based restrictions (工作时间限制)
        └── IP whitelist/blacklist
```

#### RBAC 数据模型

```python
# scripts/auth/rbac_model.py (NEW FILE)
"""Enterprise RBAC Model for V4.0."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Set, Optional
from datetime import datetime


class Permission(Enum):
    """Fine-grained permission points."""

    # Dispatch permissions
    DISPATCH_CREATE = "dispatch:create"
    DISPATCH_READ = "dispatch:read"
    DISPATCH_CANCEL = "dispatch:cancel"

    # Lifecycle permissions
    LIFECYCLE_ADVANCE = "lifecycle:advance"
    LIFECYCLE_BLOCK = "lifecycle:block"
    LIFECYCLE_VIEW = "lifecycle:view"

    # Configuration permissions
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"

    # User management permissions
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # Audit permissions
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # System permissions
    SYSTEM_SHUTDOWN = "system:shutdown"
    SYSTEM_BACKUP = "system:backup"


class UserRole(Enum):
    """User roles with hierarchical inheritance."""

    VIEWER = "viewer"
    OPERATOR = "operator"
    ANALYST = "analyst"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


# Role-Permission Mapping (RBAC Matrix)
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.VIEWER: {
        Permission.DISPATCH_READ,
        Permission.LIFECYCLE_VIEW,
        Permission.CONFIG_READ,
        Permission.USER_READ,
        Permission.AUDIT_READ,
    },
    UserRole.OPERATOR: {
        *ROLE_PERMISSIONS[UserRole.VIEWER],
        Permission.DISPATCH_CREATE,
        Permission.LIFECYCLE_ADVANCE,
    },
    UserRole.ANALYST: {
        *ROLE_PERMISSIONS[UserRole.VIEWER],
        Permission.AUDIT_EXPORT,
        Permission.CONFIG_READ,
    },
    UserRole.ADMIN: {
        *ROLE_PERMISSIONS[UserRole.OPERATOR],
        Permission.USER_CREATE,
        Permission.USER_UPDATE,
        Permission.CONFIG_WRITE,
        Permission.DISPATCH_CANCEL,
        Permission.LIFECYCLE_BLOCK,
    },
    UserRole.SUPER_ADMIN: {
        *Permission,  # All permissions
        Permission.SYSTEM_SHUTDOWN,
        Permission.SYSTEM_BACKUP,
        Permission.USER_DELETE,
    },
}


@dataclass
class User:
    """Enterprise user with RBAC attributes."""

    user_id: str
    username: str
    email: str
    role: UserRole
    tenant_id: str = "default"  # For multi-tenancy
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has specific permission."""
        return permission in ROLE_PERMISSIONS.get(self.role, set())

    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """Check if user has any of the specified permissions."""
        return any(self.has_permission(p) for p in permissions)


@dataclass
class AuditLogEntry:
    """Audit log entry for compliance tracking."""

    entry_id: str
    timestamp: datetime
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    details: Dict[str, any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict:
        """Serialize for storage/export."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "success": self.success,
            "error_message": self.error_message,
        }


class RBACEngine:
    """Enterprise RBAC enforcement engine."""

    def __init__(self, audit_log: "AuditLogger"):
        self._audit_log = audit_log

    def check_access(
        self,
        user: User,
        permission: Permission,
        resource_id: Optional[str] = None,
    ) -> bool:
        """Check if user has access to perform action.

        Also records audit log entry.
        """
        has_access = user.has_permission(permission)

        # Record audit trail
        self._audit_log.record(
            user=user,
            action=f"check:{permission.value}",
            resource_type="permission",
            resource_id=resource_id or "N/A",
            details={"granted": has_access},
            success=True,
        )

        return has_access

    def require_permission(self, user: User, permission: Permission):
        """Raise exception if permission denied."""
        if not self.check_access(user, permission):
            raise PermissionDeniedError(
                f"User '{user.username}' lacks permission: {permission.value}"
            )
```

### 6.3 Audit Log 审计日志系统

#### 设计要求

| 要求 | 描述 | 实现方式 |
|------|------|----------|
| **不可篡改** | Append-only, no delete/update | Write-ahead log + SHA256 chain |
| **完整记录** | Who/When/What/Where/Result | 5W1H 模型 |
| **高效检索** | By user/time/action/type | Index + Query API |
| **合规导出** | CSV/JSON/SYSLOG 格式 | Export API |
| **保留策略** | Configurable retention (90d/1y/7y) | Rotation + Archive |

#### 审计日志实现

```python
# scripts/auth/audit_logger.py (NEW FILE)
"""Enterprise Audit Log System for V4.0 Compliance."""

import csv
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from dataclasses import asdict
from scripts.auth.rbac_model import AuditLogEntry, User


class AuditLogger:
    """Thread-safe audit logger with integrity verification.

    Features:
    - Append-only log file (JSON Lines format)
    - Cryptographic chain (each entry hashes previous)
    - Automatic rotation by size/date
    - Query interface for compliance reporting
    - Multiple export formats
    """

    def __init__(
        self,
        log_dir: str = ".devsquad_data/audit",
        max_file_size_mb: int = 100,
        retention_days: int = 90,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.retention_days = retention_days
        self._current_file = self._get_current_log_file()
        self._last_hash: Optional[str] = None

    def _get_current_log_file(self) -> Path:
        """Get current active log file (create if not exists)."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"audit_{date_str}.jsonl"

    def record(
        self,
        user: User,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> AuditLogEntry:
        """Record an audit event.

        Args:
            user: The user performing the action
            action: Action identifier (e.g., "dispatch:create")
            resource_type: Type of resource affected
            resource_id: ID of the resource
            details: Additional context
            ip_address: Client IP address
            user_agent: Client user agent string
            success: Whether action succeeded
            error_message: Error message if failed

        Returns:
            Created AuditLogEntry
        """
        entry = AuditLogEntry(
            entry_id=f"audit-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hashlib.md5(action.encode()).hexdigest()[:8]}",
            timestamp=datetime.now(),
            user_id=user.user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )

        # Add cryptographic chain link
        entry_dict = asdict(entry)
        entry_dict["prev_hash"] = self._last_hash
        entry_hash = hashlib.sha256(
            json.dumps(entry_dict, sort_keys=True).encode()
        ).hexdigest()
        entry_dict["hash"] = entry_hash
        self._last_hash = entry_hash

        # Write to log file (append-only)
        self._write_entry(entry_dict)

        return entry

    def _write_entry(self, entry_dict: dict):
        """Append entry to current log file."""
        line = json.dumps(entry_dict, ensure_ascii=False) + "\n"
        with open(self._current_file, "a", encoding="utf-8") as f:
            f.write(line)

        # Rotate if file too large
        if self._current_file.stat().st_size > self.max_file_size:
            self._rotate_log()

    def query(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """Query audit log entries.

        Args:
            user_id: Filter by user ID
            action: Filter by action type
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum results to return

        Returns:
            List of matching audit entries
        """
        results = []
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        for log_file in sorted(self.log_dir.glob("audit_*.jsonl"), reverse=True):
            if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff:
                continue

            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry_data = json.loads(line.strip())
                        ts = datetime.fromisoformat(entry_data["timestamp"])

                        if ts < cutoff:
                            continue
                        if start_time and ts < start_time:
                            continue
                        if end_time and ts > end_time:
                            continue
                        if user_id and entry_data.get("user_id") != user_id:
                            continue
                        if action and entry_data.get("action") != action:
                            continue

                        results.append(AuditLogEntry(**entry_data))
                        if len(results) >= limit:
                            return results
                    except (json.JSONDecodeError, TypeError):
                        continue

        return results

    def export_csv(
        self,
        output_path: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> str:
        """Export audit log to CSV for compliance reporting.

        Args:
            output_path: Output CSV file path
            start_time: Start of export range
            end_time: End of export range

        Returns:
            Path to exported file
        """
        entries = self.query(start_time=start_time, end_time=end_time, limit=100000)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "entry_id", "timestamp", "user_id", "action",
                "resource_type", "resource_id", "success",
                "ip_address", "details"
            ])
            writer.writeheader()
            for entry in entries:
                row = asdict(entry)
                row["details"] = json.dumps(row["details"])
                writer.writerow(row)

        return output_path

    def verify_integrity(self) -> tuple[bool, List[str]]:
        """Verify cryptographic chain integrity.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        prev_hash = None

        for log_file in sorted(self.log_dir.glob("audit_*.jsonl")):
            with open(log_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry = json.loads(line.strip())
                        if prev_hash and entry.get("prev_hash") != prev_hash:
                            issues.append(
                                f"Chain broken at {log_file.name}:{line_num}"
                            )
                        prev_hash = entry.get("hash")
                    except (json.JSONDecodeError, KeyError):
                        issues.append(f"Invalid entry at {log_file.name}:{line_num}")

        return (len(issues) == 0, issues)

    def cleanup_old_logs(self):
        """Remove logs older than retention period."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for log_file in self.log_dir.glob("audit_*.jsonl"):
            if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff:
                log_file.unlink()

    def _rotate_log(self):
        """Rotate current log file."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        archived_name = self._current_file.with_suffix(f".{timestamp}.archived")
        self._current_file.rename(archived_name)
        self._current_file = self._get_current_log_file()
        self.cleanup_old_logs()
```

### 6.4 Multi-tenancy 多租户支持

#### 租户隔离模型

```python
# scripts/auth/tenant_manager.py (NEW FILE)
"""Multi-tenant support for V4.0."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class TenantIsolation(Enum):
    """Tenant isolation levels."""

    SHARED_DATABASE = "shared_database"  # Same DB, row-level isolation
    SCHEMA_PER_TENANT = "schema_per_tenant"  # Separate schema per tenant
    DATABASE_PER_TENANT = "database_per_tenant"  # Fully isolated


@dataclass
class Tenant:
    """Tenant (organization) definition."""

    tenant_id: str
    name: str
    domain: str  # e.g., "company.com"
    plan: str  # "free" | "pro" | "enterprise"
    max_users: int = 10
    max_dispatches_per_day: int = 100
    features: Dict[str, bool] = None
    created_at: str = ""
    is_active: bool = True

    def __post_init__(self):
        if self.features is None:
            self.features = {
                "rbac": True,
                "audit_log": True,
                "custom_roles": self.plan == "enterprise",
                "sso": self.plan in ("pro", "enterprise"),
            }


class TenantManager:
    """Multi-tenant isolation manager."""

    def __init__(self, isolation_level: TenantIsolation = TenantIsolation.SHARED_DATABASE):
        self.isolation_level = isolation_level
        self._tenants: Dict[str, Tenant] = {}
        self._default_tenant = Tenant(
            tenant_id="default",
            name="Default",
            domain="localhost",
            plan="free",
        )

    def create_tenant(self, tenant: Tenant) -> Tenant:
        """Create a new tenant."""
        if tenant.tenant_id in self._tenants:
            raise ValueError(f"Tenant already exists: {tenant.tenant_id}")
        self._tenants[tenant.tenant_id] = tenant
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant:
        """Get tenant by ID."""
        return self._tenants.get(tenant_id, self._default_tenant)

    def isolate_data_query(self, tenant_id: str, query) -> str:
        """Add tenant isolation clause to query.

        For shared database mode, adds WHERE tenant_id = ?
        """
        if self.isolation_level == TenantIsolation.SHARED_DATABASE:
            return f"{query} AND tenant_id = '{tenant_id}'"
        return query

    def check_quota(self, tenant_id: str, resource: str) -> bool:
        """Check if tenant has quota remaining."""
        tenant = self.get_tenant(tenant_id)
        # TODO: Implement actual quota checking against usage store
        return True
```

### 6.5 Compliance 合规性检查

#### SOC2 Type II 就绪检查清单

| 类别 | 控制项 | DevSquad 实现 | 状态 |
|------|--------|----------------|------|
| **Access Control** | CC6.1-6.8 | RBAC + MFA + Password Policy | ✅ Phase 9 |
| **Change Management** | CC7.1-7.3 | Git workflow + Approval gates | ✅ Existing |
| **Risk Assessment** | CC2.1-2.3 | Threat modeling (security role) | ✅ Existing |
| **Monitoring** | CC8.1-8.2 | Prometheus + Alerting | ✅ Phase 8 |
| **Data Backup** | CC9.1-9.2 | Checkpoint manager + Persistence | ✅ Existing |
| **Incident Response** | CC10.1-10.3 | Alerting + Runbook | 🔄 Phase 8 |
| **Vendor Management** | CC11.1-11.3 | Dependency scanning (Dependabot) | ✅ Existing |
| **Audit Trail** | CC3.1-3.3 | Audit Logger (immutable) | ✅ Phase 9 |

#### GDPR 合规要点

| 要求 | 实现方式 | 状态 |
|------|----------|------|
| **数据最小化** | 仅收集必要字段 | ✅ |
| **目的限制** | 明确声明数据用途 | ✅ Privacy Policy |
| **存储限制** | Retention policy (90d) | ✅ Phase 9 |
| **被遗忘权** | 用户数据删除 API | 🔄 Phase 9 |
| **数据可移植性** | Export CSV/JSON | ✅ Phase 9 |
| **知情同意** | Cookie/ToS banner | 🔄 UI Update |
| **数据保护** | Encryption at rest/transit | ✅ Existing |
| ** breach通知** | Incident response <72h | 🔄 Phase 8 |

### 6.6 WBS 与时间估算

```
Phase 9: Enterprise-Grade Features
│
├── 9.1 RBAC 实现 (3h)
│   ├── 9.1.1 Permission 枚举定义 (15+ 权限点)
│   ├── 9.1.2 Role-Permission 矩阵 (5 角色)
│   ├── 9.1.3 RBACEngine 权限检查器
│   ├── 9.1.4 API 层权限装饰器 (@require_permission)
│   └── 9.1.5 向后兼容 (旧 4 级映射到新 RBAC)
│
├── 9.2 审计日志系统 (2.5h)
│   ├── 9.2.1 AuditLogger 核心实现
│   ├── 9.2.2 密码学完整性链 (SHA256)
│   ├── 9.2.3 查询和导出 API
│   ├── 9.2.4 日志轮转和归档
│   └── 9.2.5 完整性验证工具
│
├── 9.3 多租户支持 (1.5h)
│   ├── 9.3.1 Tenant 数据模型
│   ├── 9.3.2 数据隔离中间件
│   ├── 9.3.3 Quota 管理器
│   └── 9.3.4 私有化部署选项
│
├── 9.4 合规性工具 (1.5h)
│   ├── 9.4.1 SOC2 Checklist 自动化检查
│   ├── 9.4.2 GDPR Data Processing Agreement 模板
│   ├── 9.4.3 安全扫描集成 (Bandit/Semgrep)
│   └── 9.4.4 Penetration Testing Guide
│
└── 9.5 文档与培训 (1.5h)
    ├── 9.5.1 SECURITY.md 更新
    ├── 9.5.2 Admin 操作指南
    ├── 9.5.3 Compliance Report 模板
    └── 9.5.4 Enterprise Onboarding Guide
```

### 6.7 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| RBAC 过于复杂影响易用性 | 中 | 中 | 提供 Simple Mode (旧 4 级) + Advanced Mode |
| 审计日志性能开销大 | 低 | 中 | 异步写入，批量 flush |
| 多租户数据泄露 | 低 | 高 | 强制隔离测试，渗透测试 |
| 合规认证成本高 | 中 | 低 | 先做"ready"，后续正式认证 |
| 向后兼容性破坏 | 低 | 高 | 渐进迁移，双轨并行 |

### 6.8 验收标准

- [ ] **RBAC**: ≥ **15 个细粒度权限点**，5 种角色
- [ ] **审计日志**: 100% 操作可追溯，**完整性验证通过**
- [ ] **多租户**: 数据隔离生效，Quota 限制工作
- [ ] **SOC2 就绪**: 通过 **SOC2 Type II Readiness Checklist** (≥90%)
- [ ] **GDPR 就绪**: 通过 **GDPR Gap Analysis** (≥85%)
- [ ] **安全审计**: 无 **Critical/High** 漏洞 (OWASP ZAP)
- [ ] **文档**: SECURITY.md + Admin Guide + Compliance Report

---

## 7. Cross-Phase Dependencies

### 7.1 依赖关系图

```
Phase Dependencies (V3.7-V4.0)
│
Phase 6 (Test Coverage) ──────┐
                              │
Phase 7 (Performance) ────────┼──→ Phase 8 (Observability)
                              │         │
                              │         ↓
Phase 9 (Enterprise) ◄────────┘──→ V4.0 Release
    (可与 Phase 6 并行)
```

### 7.2 并行执行策略

| 时间窗口 | 可并行执行的 Phase | 说明 |
|----------|-------------------|------|
| **Week 1-2** | Phase 6 + Phase 9 (部分) | 测试 + RBAC 设计可并行 |
| **Week 3-4** | Phase 6 (续) + Phase 7 (启动) | 测试补强 + asyncio 改造 |
| **Week 5-6** | Phase 7 (续) + Phase 8 (启动) | 性能优化 + 可观测性 |
| **Week 7-8** | Phase 8 (续) + Phase 9 (续) | 监控完善 + 企业特性 |
| **Week 9-12** | 全部集成 + 回归测试 | 最终验收 |

---

## 8. 风险管理与缓解策略

### 8.1 风险登记册

| ID | 风险描述 | 概率 | 影响 | 评分 | 缓解措施 | 负责人 |
|----|----------|------|------|------|----------|--------|
| R01 | 资源不足 (时间/人力) | 中 | 高 | **高** | 优先保证 P0 Phase，P3 可延后 | PM |
| R02 | 技术债务阻碍重构 | 中 | 中 | 中 | Phase 6 先补测试，再重构 | Tech Lead |
| R03 | 第三方依赖 breaking change | 低 | 高 | 中 | 锁定版本号，定期 review | Dev |
| R04 | 性能优化引入 regression | 中 | 高 | **高** | 充分回归测试，canary deploy | QA |
| R05 | 安全漏洞被发现 | 低 | **极高** | **极高** | Phase 9 优先，安全审计 | Security |
| R06 | 文档滞后于代码 | 高 | 低 | 中 | 文档先行原则 (用户规则) | Writer |

### 8.2 应急预案

| 触发条件 | 应急行动 | 决策者 |
|----------|----------|--------|
| Phase 6 覆盖率未达 70% | 降低目标至 65%，调整范围 | Tech Lead |
| Phase 7 性能未达 2x | 接受 1.5x，继续优化 | Architect |
| Phase 8 Prometheus 无法部署 | 降级为基础 metrics API | DevOps |
| Phase 9 RBAC 过于复杂 | 提供 Simple/Advanced 双模式 | PM |
| 任何 Phase 严重延期 | Scope reduction，MVP first | PM |

---

## 9. 资源需求与时间线

### 9.1 资源需求估算

| 资源类型 | Phase 6 | Phase 7 | Phase 8 | Phase 9 | **总计** |
|----------|---------|---------|---------|---------|----------|
| **开发时间** | 8-12h | 6-8h | 4-6h | 8-10h | **26-36h** |
| **测试时间** | 4h | 3h | 2h | 4h | **13h** |
| **文档时间** | 2h | 1.5h | 1.5h | 2h | **7h** |
| **Review 时间** | 2h | 1.5h | 1h | 2h | **6.5h** |
| **Buffer (20%)** | 3.2h | 2.2h | 1.7h | 3.6h | **10.7h** |
| **合计** | **19.2h** | **13.2h** | **10.2h** | **19.6h** | **62.2h** |

### 9.2 甘特图 (简化)

```
Week:    1   2   3   4   5   6   7   8   9   10  11  12
─────────────────────────────────────────────────────────
Phase 6  ████░░████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
Phase 7  ░░░░░░░░░░░████░░████░░░░░░░░░░░░░░░░░░░░░░░░░
Phase 8  ░░░░░░░░░░░░░░░░░░░░████░░████░░░░░░░░░░░░░░░░
Phase 9  ████░░████░░████░░░░░░░░░░████░░████░░░░░░░░░░
Integration              ░░░░░░░░░░░░░░░░░░░░░░░██████████
Documentation             ░░░░░░░░░░░░░░░░░░░░░░░░░░░░████
Buffer                    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### 9.3 里程碑交付物

| 里程碑 | 交付物 | 格式 | 位置 |
|--------|--------|------|------|
| **M1** | 测试覆盖率报告 | HTML + JSON | `htmlcov/`, `coverage.json` |
| **M2** | 性能对比报告 | Markdown | `docs/reports/benchmark_v37.md` |
| **M3** | Grafana Dashboard | JSON | `config/grafana_dashboard.json` |
| **M4** | 安全合规报告 | PDF/Markdown | `docs/compliance_report_v40.md` |
| **M5** | V4.0 Release Notes | Markdown | `CHANGELOG.md` (V4.0 section) |

---

## 10. 成功指标与验收标准

### 10.1 KPI Dashboard

| 维度 | 指标 | V3.6.1 Baseline | V4.0 Target | 测量方法 |
|------|------|-----------------|-------------|----------|
| **质量** | Test Coverage | 57% | **≥80%** | pytest-cov |
| **质量** | Tests Count | 1680 | **≥2300** | pytest --co |
| **质量** | Pass Rate | 99.87% | **≥99.5%** | CI pipeline |
| **性能** | P99 Latency | ~15s | **≤7.5s** | Benchmark script |
| **性能** | QPS (Mock) | ~20 | **≥40** | Load test |
| **性能** | Cache Hit Rate | N/A | **≥60%** | Redis INFO stats |
| **可观测性** | Metrics Count | ~5 | **≥15** | /metrics endpoint |
| **可观测性** | Trace Coverage | 0% | **Core paths** | Jaeger UI |
| **安全性** | Permission Points | 4 (coarse) | **≥15** (fine-grained) | RBAC matrix |
| **安全性** | Audit Coverage | 0% | **100% actions** | Audit log query |
| **合规性** | SOC2 Readiness | ~60% | **≥90%** | Checklist |
| **合规性** | GDPR Readiness | ~50% | **≥85%** | Gap analysis |

### 10.2 最终验收 Checklists

#### Phase 6 验收
- [ ] `pytest --cov` 报告覆盖率 ≥ **70%**
- [ ] 新增 ≥ **400 测试**全部通过
- [ ] `dashboard.py`, `mcp_server.py`, `api_server.py` 覆盖率 > **40%**
- [ ] CI 自动运行测试并上报覆盖率

#### Phase 7 验收
- [ ] Benchmark 报告显示 P99 延迟降低 **≥50%**
- [ ] Mock 模式 QPS 提升 **≥2x**
- [ ] Redis 缓存可选启用且稳定
- [ ] 异步 API (`async dispatch`) 可用

#### Phase 8 验收
- [ ] `/metrics` 端点返回 **≥15 个 Prometheus 指标**
- [ ] 日志输出为 **结构化 JSON** 格式
- [ ] 关键路径可在 **Jaeger/Zipkin** 查看 trace
- [ ] ≥ **5 条 Alert rules** 在 Prometheus 生效

#### Phase 9 验收
- [ ] RBAC 矩阵定义 **≥15 个权限点** + **5 种角色**
- [ ] 审计日志 **100% 覆盖**写操作
- [ ] 审计日志 **完整性验证**通过
- [ ] SOC2 Readiness Checklist **≥90%**
- [ ] GDPR Gap Analysis **≥85%**
- [ ] OWASP ZAP **无 Critical/High** 漏洞

### 10.3 V4.0 发布标准

所有以下条件满足时，方可发布 V4.0：

```
✅ Phase 6-9 全部验收通过
✅ 总体覆盖率 ≥ 75% (允许渐进提升至 80%)
✅ 性能基线对比报告完成
✅ 安全审计无 Critical 漏洞
✅ 文档更新 (SPEC.md, CHANGELOG.md, README*.md)
✅ EN/CN/JP 三语文档版本一致
✅ pyproject.toml 版本号 = 4.0.0
✅ CI/CD 绿色 (全分支通过)
✅ License 检查通过 (无新增 GPL 依赖)
✅ Changelog 完整记录所有变更
```

---

## 附录 A: 技术选型决策记录 (ADR)

| 决策 | 选择 | 替代方案 | 理由 |
|------|------|----------|------|
| 异步框架 | asyncio + aiohttp | trio, curio | 生态最成熟，FastAPI 原生支持 |
| 缓存后端 | Redis | Memcached, etcd | 功能丰富，持久化，社区活跃 |
| 监控栈 | Prometheus + Grafana | Datadog, New Relic | 开源，云原生标准，成本可控 |
| Tracing | OpenTelemetry | Jaeger SDK, Zipkin SDK | Vendor-neutral，CNCF 毕业 |
| 日志格式 | JSON (structured) | Plaintext, CEE | 机器可解析，ELK/Loki 友好 |
| 审计存储 | JSON Lines (append-only) | SQLite, PostgreSQL | 零依赖，简单可靠，易于导出 |
| RBAC 实现 | 自研 (基于 Enum) | Casbin, OPA | 轻量级，无需额外依赖，完全可控 |

---

## 附录 B: 术语表

| 术语 | 定义 |
|------|------|
| **RBAC** | Role-Based Access Control，基于角色的访问控制 |
| **Audit Log** | 审计日志，记录所有操作的不可篡改日志 |
| **Multi-tenancy** | 多租户，一套系统服务多个独立客户 |
| **SOC2** | Service Organization Control 2，服务组织控制报告 |
| **GDPR** | General Data Protection Regulation，通用数据保护条例 |
| **HIPAA** | Health Insurance Portability and Accountability Act |
| **OpenTelemetry** | CNCF 可观测性标准（Tracing + Metrics + Logs） |
| **Prometheus** | 云原生监控系统，Pull 模式时序数据库 |
| **Grafana** | 开源可视化平台，用于展示 Prometheus 数据 |
| **SLA** | Service Level Agreement，服务等级协议 |
| **P99** | 99th percentile latency，99% 的请求在此时间内完成 |
| **QPS** | Queries Per Second，每秒查询率/吞吐量 |
| **WBS** | Work Breakdown Structure，工作分解结构 |
| **ADR** | Architecture Decision Record，架构决策记录 |

---

**文档结束**

> **版本**: V1.0.0  
> **创建日期**: 2026-05-20  
> **作者**: AI Planning Agent (based on MATURITY_REPORT_V3.6.1 analysis)  
> **审核状态**: 待团队审核  
> **下次更新**: Phase 6 开始前或根据实际进展调整  
> **反馈渠道**: https://github.com/lulin70/DevSquad/issues
