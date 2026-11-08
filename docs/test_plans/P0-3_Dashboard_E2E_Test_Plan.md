# P0-3: Dashboard UI E2E Test Plan

## 执行概要

**优先级**: Medium  
**预估工作量**: 6-8 小时  
**当前状态**: In Progress  
**负责人**: Tester + UI Designer  
**审查人**: Architect, Product Manager

## 背景

Dashboard 是 DevSquad 的关键用户界面，需要确保完整的 E2E 测试覆盖，以保证生产环境的可用性和用户体验质量。

## 现有测试资产分析

### 1. 已有测试文件

| 文件 | 覆盖范围 | 状态 | 测试数量 |
|------|---------|------|---------|
| `tests/test_dashboard_ui_e2e.py` | 组件级 UI 测试 (AppTest) | ✅ 存在 | ~10+ |
| `tests/e2e/test_dashboard_browser_e2e.py` | 浏览器级 E2E (AppTest) | ✅ 存在 | ~5+ |
| `tests/e2e/test_dashboard_subprocess.py` | 子进程启动测试 | ✅ 存在 | ~3+ |
| `tests/integration/test_v442_dashboard_visibility.py` | V4.4.2 可见性测试 | ✅ 存在 | ~5+ |
| `tests/test_dashboard_v43_panels.py` | V4.3 面板测试 | ✅ 存在 | ~8+ |
| `tests/test_dashboard_split.py` | 拆分功能测试 | ✅ 存在 | ~4+ |

**总计**: 约 35+ 个测试用例覆盖 Dashboard

### 2. 现有测试覆盖维度

**已覆盖**:
- ✅ 页面加载 (不崩溃)
- ✅ 基础导航 (sidebar radio)
- ✅ Header/Footer 渲染
- ✅ RBAC (Viewer/Operator/Admin 角色)
- ✅ 组件可见性 (markdown, buttons, forms)
- ✅ 多语言支持 (中英日文档)

**部分覆盖**:
- ⚠️ 用户交互流程 (点击、填表、提交)
- ⚠️ 数据展示正确性 (dispatch history, phase timeline)
- ⚠️ 实时更新 (长轮询, WebSocket)
- ⚠️ 性能 (latency < 100ms 门禁)
- ⚠️ 错误处理 (后端 API 失败场景)

**未覆盖 (Gap)**:
- ❌ 完整用户旅程 (login → dispatch → view result → logout)
- ❌ 跨页面状态一致性
- ❌ Dashboard + API + LLM 集成测试
- ❌ 移动端响应式布局
- ❌ 浏览器兼容性 (Chrome/Safari/Firefox)
- ❌ 性能基准测试 (P50/P95/P99)

## 测试覆盖 Gap 分析

### Gap 1: 完整用户旅程测试

**当前问题**: 现有测试多为单页面或单功能测试，缺少端到端用户旅程验证。

**需要覆盖的旅程**:
1. **新用户首次使用**:
   - 访问 Dashboard URL
   - 看到登录页面
   - 输入凭证登录
   - 进入 Overview 页面
   - 浏览各个 Tab (Phases/Gates/Performance)
   - 退出登录
   
2. **Operator 发起 Dispatch**:
   - 登录为 Operator
   - 导航到 Dispatch 页面
   - 填写任务描述
   - 选择角色 (architect, security)
   - 提交任务
   - 等待结果 (显示 loading spinner)
   - 查看结果报告
   - 下载 Markdown 报告

3. **Admin 管理用户**:
   - 登录为 Admin
   - 导航到 Settings 页面
   - 查看用户列表
   - 添加新用户
   - 修改权限
   - 删除用户
   - 查看审计日志

**测试方法**: Streamlit AppTest 模拟完整会话流

### Gap 2: 跨页面状态一致性

**当前问题**: 未验证 session_state 在页面切换时的一致性。

**需要验证的场景**:
- Dispatch 参数在 Phases → Dispatch 切换后保留
- 用户角色在所有页面保持一致
- 选中的 dispatch session 在切换页面后仍可访问
- Filter 设置跨页面保持

**测试方法**: AppTest 切换页面后检查 session_state

### Gap 3: Dashboard + API + LLM 集成测试

**当前问题**: 现有测试使用 Mock Backend，未验证真实 LLM 集成。

**需要验证的场景**:
- Dashboard 通过 API 调用 real LLM (OpenAI/Moka)
- LLM 超时时 Dashboard 正确显示错误
- LLM 返回流式输出时 Dashboard 实时更新
- API rate limit 时 Dashboard 显示友好提示

**测试方法**: 
- 使用 `MOKA_TIMEOUT=5` 模拟超时
- 使用真实 Moka API 进行烟雾测试
- 注入 API 错误响应验证错误处理

### Gap 4: 性能基准测试

**当前问题**: 现有 latency gate (< 100ms) 但缺少系统性能能基准。

**需要测量的指标**:
- 页面首次加载时间 (P50/P95/P99)
- 页面切换延迟
- Dispatch 提交响应时间
- Dashboard 刷新频率
- 内存占用 (长时间运行)

**测试方法**: 
- Locust 或 pytest-benchmark 压测
- 记录 5 次运行的中位数 (防止抖动)

### Gap 5: 移动端和浏览器兼容性

**当前问题**: 未验证移动端体验和跨浏览器兼容性。

**需要验证的平台**:
- macOS: Chrome 120+, Safari 17+, Firefox 121+
- Windows: Chrome, Edge
- iOS: Safari (responsive)
- Android: Chrome (responsive)

**测试方法**: Playwright 跨浏览器测试 (如果需要真实浏览器)

## 优先级排序

根据生产影响和实现难度，优先级如下:

| 优先级 | Gap | 预估工作量 | 理由 |
|-------|-----|----------|------|
| **P0** | Gap 1: 完整用户旅程 | 3-4h | 生产关键路径，必须覆盖 |
| **P1** | Gap 2: 跨页面状态一致性 | 1-2h | 影响用户体验，较易实现 |
| **P1** | Gap 3: LLM 集成测试 | 1-2h | 已有 Moka 配置，复用即可 |
| **P2** | Gap 4: 性能基准测试 | 2-3h | 重要但非阻塞 |
| **P3** | Gap 5: 浏览器兼容性 | 3-4h | 理想状态，资源允许时做 |

**P0-3 任务范围**: 专注于 P0 + P1 (共 5-8h)，P2/P3 作为后续任务。

## 测试实施计划

### 阶段 1: 完整用户旅程测试 (P0, 3-4h)

**任务 1.1: 新用户首次使用旅程** (1h)
```python
# tests/e2e/test_dashboard_user_journey.py


def test_new_user_first_visit():
    """Journey: New user visits, logs in, explores, logs out."""
    app = AppTest.from_file(str(DASHBOARD_APP))

    # Step 1: Not authenticated, see login page
    app.run()
    assert "Login" in str(app.title)

    # Step 2: Enter credentials and login
    app.text_input[0].set_value("test_viewer").run()
    app.text_input[1].set_value("password123").run()
    app.button[0].click().run()

    # Step 3: Authenticated, see Overview page
    assert "Overview" in str(app.markdown)

    # Step 4: Navigate to Phases tab
    app.radio[0].set_value("Phases").run()
    assert "P0-P11" in str(app.markdown)

    # Step 5: Logout
    app.button["Logout"].click().run()
    assert "Login" in str(app.title)
```

**任务 1.2: Operator 发起 Dispatch 旅程** (1.5h)
```python
def test_operator_dispatch_journey():
    """Journey: Operator dispatches a task and views result."""
    app = _run_dashboard(role="operator")
    
    # Step 1: Navigate to Dispatch page
    app.radio[0].set_value("Dispatch").run()
    assert "Task Description" in str(app.text_area)
    
    # Step 2: Fill form and submit
    app.text_area[0].set_value("Design auth system").run()
    app.multiselect[0].set_value(["architect", "security"]).run()
    app.button["Submit"].click().run()
    
    # Step 3: Loading indicator appears
    assert "spinner" in str(app) or "progress" in str(app)
    
    # Step 4: Result renders
    assert "Architect" in str(app.markdown) or "Security" in str(app.markdown)
    
    # Step 5: Download button available
    download_btn = [b for b in app.button if "Download" in b.label]
    assert len(download_btn) > 0
```

**任务 1.3: Admin 管理用户旅程** (0.5h)
```python
def test_admin_user_management_journey():
    """Journey: Admin manages users."""
    app = _run_dashboard(role="admin")
    
    # Step 1: Navigate to Settings
    app.radio[0].set_value("Settings").run()
    assert "User Management" in str(app.markdown)
    
    # Step 2: View user list
    user_table = app.dataframe[0]  # Assuming st.dataframe shows users
    assert len(user_table.value) >= 1  # At least admin user
    
    # Step 3: Add user button exists
    add_user_btn = [b for b in app.button if "Add User" in b.label]
    assert len(add_user_btn) > 0
```

### 阶段 2: 跨页面状态一致性测试 (P1, 1h)

**任务 2.1: Session State 持久化** (0.5h)
```python
def test_session_state_persists_across_pages():
    """Verify session_state maintains consistency across page navigation."""
    app = _run_dashboard(role="operator")
    
    # Set state on Dispatch page
    app.radio[0].set_value("Dispatch").run()
    app.text_area[0].set_value("Test task").run()
    initial_task = app.session_state.get("task_description")
    
    # Navigate to Overview and back
    app.radio[0].set_value("Overview").run()
    app.radio[0].set_value("Dispatch").run()
    
    # Verify state preserved
    final_task = app.session_state.get("task_description")
    assert initial_task == final_task, "Task description lost across navigation"
```

**任务 2.2: 用户角色一致性** (0.5h)
```python
def test_user_role_consistent_across_pages():
    """Verify user role remains consistent across all pages."""
    app = _run_dashboard(role="viewer")
    
    pages = ["Overview", "Phases", "Gates", "Performance"]
    for page in pages:
        app.radio[0].set_value(page).run()
        user = app.session_state.get("user")
        assert user.role == UserRole.VIEWER, f"Role changed on {page} page"
```

### 阶段 3: LLM 集成测试 (P1, 1-2h)

**任务 3.1: Moka LLM 超时处理** (0.5h)
```python
@pytest.mark.skipif(not os.getenv("MOKA_API_KEY"), reason="Moka key not configured")
def test_dashboard_handles_llm_timeout():
    """Dashboard gracefully handles LLM timeout."""
    # Set short timeout to trigger timeout
    os.environ["MOKA_TIMEOUT"] = "1"
    
    app = _run_dashboard(role="operator")
    app.radio[0].set_value("Dispatch").run()
    app.text_area[0].set_value("Complex reasoning task").run()
    app.button["Submit"].click().run()
    
    # Verify error message shown
    error_found = any("timeout" in str(m).lower() for m in app.error)
    assert error_found, "Timeout error not displayed to user"
```

**任务 3.2: Real LLM 烟雾测试** (0.5h)
```python
@pytest.mark.skipif(not os.getenv("MOKA_API_KEY"), reason="Moka key not configured")
def test_dashboard_real_llm_smoke():
    """Dashboard successfully dispatches with real Moka LLM."""
    app = _run_dashboard(role="operator")
    app.radio[0].set_value("Dispatch").run()
    app.text_area[0].set_value("Explain JWT").run()
    app.multiselect[0].set_value(["architect"]).run()
    app.button["Submit"].click().run()
    
    # Verify result rendered (not mock)
    result_text = " ".join(str(m) for m in app.markdown)
    assert "JWT" in result_text
    assert "[MOCK MODE]" not in result_text
```

**任务 3.3: API Rate Limit 处理** (0.5h)
```python
def test_dashboard_handles_api_rate_limit():
    """Dashboard shows friendly message on API rate limit."""
    # Mock rate limit response
    with patch("scripts.collaboration.moka_backend.MokaAIBackend.generate") as mock_gen:
        mock_gen.side_effect = RuntimeError("Rate limit exceeded")
        
        app = _run_dashboard(role="operator")
        app.radio[0].set_value("Dispatch").run()
        app.text_area[0].set_value("Test").run()
        app.button["Submit"].click().run()
        
        # Verify friendly error message
        error_text = " ".join(str(e) for e in app.error)
        assert "rate limit" in error_text.lower()
```

### 阶段 4: 性能基准测试 (P2, 后续任务)

**任务 4.1: 页面加载性能** (1h)
- 使用 `pytest-benchmark` 测量页面加载时间
- 记录 5 次运行的 P50/P95/P99
- 设置性能回归门禁 (P95 < 150ms)

**任务 4.2: Dashboard 内存泄漏测试** (1h)
- 长时间运行 Dashboard (模拟 100 次 dispatch)
- 监控内存占用变化
- 确保无明显内存泄漏 (<5% 增长)

## 验收标准

### 最小可接受标准 (P0-3 完成)

- [ ] **旅程测试**: 3 个完整用户旅程测试通过 (新用户/Operator/Admin)
- [ ] **状态一致性**: 2 个跨页面状态测试通过
- [ ] **LLM 集成**: 3 个 LLM 集成测试通过 (超时/真实 API/rate limit)
- [ ] **CI 集成**: 新增测试纳入 `.github/workflows/test.yml`
- [ ] **文档更新**: 更新 `docs/reference/MODULE_REFERENCE.md` 测试覆盖表

### 理想标准 (P2 完成)

- [ ] 性能基准测试建立并通过
- [ ] 测试覆盖率 > 85% (Dashboard 相关代码)
- [ ] 跨浏览器兼容性验证 (Chrome/Safari/Firefox)

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Streamlit AppTest 限制 (不支持某些交互) | High | 使用 Playwright 作为后备方案 |
| Moka API 配额限制 | Medium | 优先使用 Mock，关键路径使用真实 API |
| 测试执行时间过长 (>10min) | Medium | 使用 pytest marker 分离慢速测试 |
| CI 环境无法启动 Streamlit | High | 添加 skip marker，本地必须通过 |

## 实施时间表

| 任务 | 预估工作量 | 依赖 | 计划完成日期 |
|------|----------|------|------------|
| 阶段 1: 用户旅程测试 | 3-4h | 无 | Day 1 |
| 阶段 2: 状态一致性测试 | 1h | 无 | Day 1 |
| 阶段 3: LLM 集成测试 | 1-2h | Moka 配置完成 | Day 2 |
| CI 集成与文档更新 | 0.5h | 以上全部 | Day 2 |
| **P0-3 总计** | **5.5-7.5h** | | **Day 2 完成** |

## 后续任务 (不在 P0-3 范围)

- **P2-7**: 性能基准测试 (2-3h, 独立任务)
- **P3-X**: 浏览器兼容性测试 (3-4h, 独立任务)
- **P3-Y**: 移动端响应式测试 (2-3h, 独立任务)

## 参考文档

- [DevSquad SKILL.md](../../SKILL.md): 项目概述与架构
- [Dashboard Module Reference](../reference/MODULE_REFERENCE.md): Dashboard 模块详情
- [Moka Tuning Guide](../MOKA_TUNING_GUIDE.md): Moka LLM 调优指南
- [CI Workflow](.github/workflows/test.yml): CI 测试配置

---

**创建日期**: 2026-11-05  
**最后更新**: 2026-11-05  
**版本**: 1.0
