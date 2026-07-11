# P2-3: workflow_engine 测试补充计划

> **创建时间**: 2026-07-11
> **当前版本**: V4.0.1
> **目标版本**: V4.0.2
> **前置文档**: [P2_P3_PLAN.md](P2_P3_PLAN.md) §2.3

---

## 一、测试范围

### 源文件清单（6 个文件，1247 行）

| # | 文件 | 行数 | 已有测试 | 本次新增 |
|---|------|------|----------|----------|
| 1 | `workflow_engine_base.py` | 439 | 无 | ✅ 新建 |
| 2 | `workflow_engine_lifecycle_mixin.py` | 282 | 无 | ✅ 新建 |
| 3 | `workflow_engine_state_mixin.py` | 156 | 无 | ✅ 新建 |
| 4 | `workflow_engine_transition_mixin.py` | 145 | 无 | ✅ 新建 |
| 5 | `workflow_engine_persistence_mixin.py` | 122 | ✅ 16 测试 | 无需补充 |
| 6 | `workflow_engine.py` | 103 | 无 | ✅ 新建 |

### 已有测试文件

- `test_workflow_persistence_coverage.py` — 16 个测试覆盖 persistence mixin（_save_checkpoint / resume_from_checkpoint / handoff）

---

## 二、测试文件结构

### 2.1 `test_workflow_engine_base.py` — 基类与数据模型

**测试目标**: enums、dataclass 序列化/反序列化、模板常量完整性、WorkflowEngineBase stubs

| 测试类 | 测试方法 | 覆盖路径 |
|--------|----------|----------|
| TestWorkflowStatusEnum | test_all_statuses_exist | 6 个状态值 |
| TestStepStatusEnum | test_all_statuses_exist | 5 个状态值 |
| TestNodeTypeEnum | test_all_types_exist | 3 个节点类型 |
| TestWorkflowStepSerialization | test_to_dict_round_trip | to_dict + from_dict 往返 |
| | test_to_dict_status_enum_to_string | status 枚举转字符串 |
| | test_to_dict_node_type_enum_to_string | node_type 枚举转字符串 |
| | test_from_dict_invalid_status_falls_back_to_pending | 无效 status 回退 PENDING |
| | test_from_dict_invalid_node_type_falls_back_to_hybrid | 无效 node_type 回退 HYBRID |
| | test_from_dict_missing_node_type_defaults_hybrid | 缺失 node_type 默认 HYBRID |
| | test_from_dict_status_already_enum | status 已是枚举不转换 |
| | test_from_dict_node_type_already_enum | node_type 已是枚举不转换 |
| TestWorkflowStepProperties | test_is_deterministic | DETERMINISTIC 返回 True |
| | test_is_llm | LLM 返回 True |
| | test_requires_llm_llm | LLM requires_llm=True |
| | test_requires_llm_hybrid | HYBRID requires_llm=True |
| | test_requires_llm_deterministic | DETERMINISTIC requires_llm=False |
| | test_default_node_type_is_hybrid | 默认 node_type=HYBRID |
| TestWorkflowDefinition | test_to_dict_serializes_steps | to_dict 包含 steps 列表 |
| | test_to_dict_includes_metadata | to_dict 包含 metadata |
| | test_default_workflow_id_format | 默认 ID 格式 wf-xxxxxxxx |
| TestWorkflowInstance | test_default_values | 默认值验证 |
| TestRequirementChange | test_default_values | 默认值验证 |
| TestPhaseTemplates | test_all_phases_have_required_keys | P1-P11 必须字段完整 |
| | test_phase_ids_sequential | P1-P11 连续 |
| | test_dependencies_reference_valid_phases | 依赖引用有效阶段 |
| TestLifecycleTemplates | test_all_templates_reference_valid_phases | 5 模板引用有效阶段 |
| | test_full_template_has_all_11_phases | full 模板 11 阶段 |
| | test_minimal_template_has_5_phases | minimal 模板 5 阶段 |
| TestWorkflowEngineBase | test_save_checkpoint_raises_not_implemented | stub 抛 NotImplementedError |
| | test_classify_steps_raises_not_implemented | stub 抛 NotImplementedError |

**预估**: ~25 个测试

### 2.2 `test_workflow_engine_lifecycle.py` — 生命周期创建 mixin

**测试目标**: create_workflow_from_task、_split_task_into_steps、create_lifecycle、submit_change_request

| 测试类 | 测试方法 | 覆盖路径 |
|--------|----------|----------|
| TestCreateWorkflowFromTask | test_creates_definition_with_metadata | 创建+元数据 |
| | test_registers_in_definitions | 注册到 definitions |
| | test_empty_description | 空描述 |
| | test_with_target_agent | target_agent 元数据 |
| TestSplitTaskIntoSteps | test_product_keywords | 需求关键词 → Requirements Analysis |
| | test_architecture_keywords | 架构关键词 → Architecture Design |
| | test_security_keywords | 安全关键词 → Security Review |
| | test_ui_keywords | UI 关键词 → UI Design |
| | test_testing_keywords | 测试关键词 → Test Design |
| | test_development_keywords | 开发关键词 → Development |
| | test_testing_and_development_adds_test_execution | 测试+开发 → Test Execution |
| | test_deployment_keywords | 部署关键词 → Deployment |
| | test_chinese_keywords | 中文关键词 |
| | test_no_keywords_fallback | 无关键词 → Task Execution 回退 |
| | test_step_ids_sequential | step_id 递增 |
| TestCreateLifecycle | test_full_template | full 模板 11 阶段 |
| | test_backend_template | backend 模板 |
| | test_frontend_template | frontend 模板 |
| | test_internal_tool_template | internal_tool 模板 |
| | test_minimal_template | minimal 模板 |
| | test_invalid_template_raises_value_error | 无效模板抛 ValueError |
| | test_node_type_propagation | node_type 从模板传播 |
| | test_invalid_node_type_falls_back_hybrid | 无效 node_type 回退 HYBRID |
| TestSubmitChangeRequest | test_instance_not_found_returns_none | 实例不存在 |
| | test_wrong_status_returns_none | COMPLETED/FAILED 状态拒绝 |
| | test_running_status_allows | RUNNING 状态允许 |
| | test_paused_status_allows | PAUSED 状态允许 |
| | test_no_definition_returns_none | 无定义返回 None |
| | test_affected_phases_excludes_completed | 影响阶段排除已完成 |
| | test_rollback_to_is_earliest_uncompleted | rollback_to 为最早未完成 |
| | test_description_sanitized_truncated | 描述截断 500 字符 |
| | test_reason_sanitized_truncated | 原因截断 500 字符 |
| | test_requested_by_sanitized_truncated | 请求者截断 100 字符 |

**预估**: ~35 个测试

### 2.3 `test_workflow_engine_state.py` — 状态查询 mixin

**测试目标**: get_workflow_status、register_executor、classify_steps、get_step_summary

| 测试类 | 测试方法 | 覆盖路径 |
|--------|----------|----------|
| TestGetWorkflowStatus | test_instance_not_found_returns_none | 实例不存在 |
| | test_with_definition | 有定义：progress/completion_rate |
| | test_without_definition | 无定义：total_steps=0 |
| | test_zero_steps_completion_rate_zero | 零步骤 completion_rate=0 |
| | test_has_checkpoint_flag | checkpoint_id 存在/不存在 |
| | test_failed_steps_included | failed_steps 包含 |
| TestRegisterExecutor | test_register_and_use | 注册后可使用 |
| TestClassifySteps | test_none_workflow_id_empty_definitions | None+空定义 → empty_result |
| | test_none_workflow_id_uses_latest | None+有定义 → 最近定义 |
| | test_workflow_id_not_found | 不存在 → empty_result |
| | test_mixed_node_types | 混合类型分类 |
| | test_all_deterministic | 全 DETERMINISTIC |
| | test_all_llm | 全 LLM |
| | test_all_hybrid | 全 HYBRID |
| | test_empty_steps | 空步骤 → empty_result |
| | test_by_step_list | by_step 列表结构 |
| | test_percentages_sum_100 | 百分比合计 100 |
| TestGetStepSummary | test_summary_delegates_to_classify | 委托 classify_steps |
| | test_summary_counts | 计数正确 |

**预估**: ~20 个测试

### 2.4 `test_workflow_engine_transition.py` — 状态转换 mixin

**测试目标**: start_workflow、execute_step、_default_step_executor、_get_next_step

| 测试类 | 测试方法 | 覆盖路径 |
|--------|----------|----------|
| TestStartWorkflow | test_definition_not_found_returns_none | 定义不存在 |
| | test_creates_running_instance | 创建 RUNNING 实例 |
| | test_sets_current_step_to_first | current_step=首步 |
| | test_no_steps_current_step_none | 无步骤 current_step=None |
| | test_variables_passed_through | 变量传递 |
| | test_instance_registered | 实例注册 |
| TestExecuteStep | test_instance_not_found_returns_none | 实例不存在 |
| | test_definition_not_found_returns_none | 定义不存在 |
| | test_current_step_not_found_returns_none | 当前步骤不存在 |
| | test_success_with_step_executor | 自定义执行器成功 |
| | test_success_with_registered_executor | 注册执行器成功 |
| | test_success_with_default_executor_dispatcher | 默认执行器+dispatcher |
| | test_success_with_default_executor_no_dispatcher | 默认执行器无 dispatcher |
| | test_checkpoint_interval_trigger | 检查点间隔触发 |
| | test_completion_no_next_step | 完成无下一步 |
| | test_failure_runtime_error | RuntimeError 失败处理 |
| | test_failure_value_error | ValueError 失败处理 |
| | test_failure_attribute_error | AttributeError 失败处理 |
| | test_failure_type_error | TypeError 失败处理 |
| | test_step_marked_completed | 步骤标记 COMPLETED |
| | test_advances_to_next_step | 推进到下一步 |
| TestDefaultStepExecutor | test_with_dispatcher | 有 dispatcher |
| | test_without_dispatcher | 无 dispatcher |
| | test_dispatcher_result_summary_truncated | summary 截断 200 字符 |
| TestGetNextStep | test_returns_next_step | 返回下一步 |
| | test_current_is_last_returns_none | 最后一步返回 None |
| | test_current_not_in_definition_returns_none | 当前步不在定义中 |

**预估**: ~30 个测试

### 2.5 `test_workflow_engine.py` — 主类初始化

**测试目标**: WorkflowEngine.__init__

| 测试类 | 测试方法 | 覆盖路径 |
|--------|----------|----------|
| TestWorkflowEngineInit | test_creates_storage_path | storage_path 目录创建 |
| | test_initializes_attributes | 属性初始化 |
| | test_checkpoint_manager_created | checkpoint_manager 创建 |
| | test_default_checkpoint_interval | checkpoint_interval=2 |
| | test_coordinator_and_dispatcher_none | 默认 None |

**预估**: ~5 个测试

---

## 三、测试策略

### 3.1 真实组件优先（遵循用户测试哲学）

- **CheckpointManager**: 使用真实文件系统（tempdir），不 Mock
- **WorkflowEngine**: 使用真实 WorkflowEngine 实例，不 Mock
- **dispatcher**: 仅在 _default_step_executor 测试中 Mock（因其依赖外部 dispatcher 对象）

### 3.2 Mixin 测试方式

对于 mixin，创建最小化具体子类（参考已有 `test_workflow_persistence_coverage.py` 的 `_Engine` 模式）：

```python
class _Engine(WorkflowEngineLifecycleMixin, WorkflowEngineStateMixin, ...):
    def __init__(self, storage_path):
        self.storage_path = Path(storage_path)
        self.definitions = {}
        self.instances = {}
        self.executors = {}
        self.checkpoint_manager = CheckpointManager(storage_path=storage_path)
        self.checkpoint_interval = 2
        self.coordinator = None
        self.dispatcher = None
```

### 3.3 覆盖率目标

- **workflow_engine_base.py**: ≥95%（仅排除 NotImplementedError 行）
- **workflow_engine_lifecycle_mixin.py**: ≥95%
- **workflow_engine_state_mixin.py**: ≥95%
- **workflow_engine_transition_mixin.py**: ≥95%
- **workflow_engine.py**: 100%（仅 __init__）
- **workflow_engine_persistence_mixin.py**: 维持现有覆盖率

---

## 四、验证方法

```bash
# 1. ruff 检查
ruff check tests/test_workflow_engine_base.py tests/test_workflow_engine_lifecycle.py tests/test_workflow_engine_state.py tests/test_workflow_engine_transition.py tests/test_workflow_engine.py

# 2. mypy 类型检查
mypy tests/test_workflow_engine_base.py tests/test_workflow_engine_lifecycle.py tests/test_workflow_engine_state.py tests/test_workflow_engine_transition.py tests/test_workflow_engine.py

# 3. 单模块测试
pytest tests/test_workflow_engine_base.py tests/test_workflow_engine_lifecycle.py tests/test_workflow_engine_state.py tests/test_workflow_engine_transition.py tests/test_workflow_engine.py -v

# 4. 覆盖率报告
pytest tests/test_workflow_engine*.py --cov=scripts.collaboration.workflow_engine --cov-report=term-missing

# 5. 全量回归
pytest --cov -q
```

---

## 五、预估总测试数

| 文件 | 预估测试数 |
|------|-----------|
| test_workflow_engine_base.py | ~25 |
| test_workflow_engine_lifecycle.py | ~35 |
| test_workflow_engine_state.py | ~20 |
| test_workflow_engine_transition.py | ~30 |
| test_workflow_engine.py | ~5 |
| **总计** | **~115** |

**预估覆盖率提升**: +1% (71.89% → ~73%)

---

*文档创建: 2026-07-11 | 版本: v4.0.1 | 状态: 执行中*
