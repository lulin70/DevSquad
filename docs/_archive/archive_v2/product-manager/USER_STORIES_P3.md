# Phase 3: WarmupManager 启动优化 - 用户故事 (USER_STORIES)

**版本**: v1.0
**日期**: 2026-04-16
**作者**: PM (产品经理角色)
**基于设计文档**: [v3-phase3-warmup-design.md](../architecture/v3-phase3-warmup-design.md)

---

## Epic 概览

| Epic ID | 名称 | 用户价值 | 优先级 | 故事数 |
|---------|------|---------|--------|-------|
| E1 | **快速启动体验** | 用户 `import collaboration` 后立即可用，无需等待 1.7s | P0 | 3 |
| E2 | **智能预热管理** | 系统自动预加载高频资源，首次 API 调用 < 50ms | P0 | 3 |
| E3 | **进程级缓存** | 多次调用共享缓存，避免重复加载 | P1 | 2 |
| E4 | **可观测性** | 开发者可查看预热状态、性能指标、诊断信息 | P1 | 2 |
| E5 | **弹性与降级** | 预热失败不影响核心功能，支持多级降级 | P2 | 2 |

**总计: 12 个用户故事 | 预计验收标准: ~50+ AC**

---

## E1: 快速启动体验

### US-3.01: 作为开发者，我希望 import collaboration 时只阻塞 < 100ms

**背景**: 当前 `from collaboration import Coordinator` 需要 ~1.7s（9个模块 eager import + PromptRegistry 同步读文件），严重影响开发体验和脚本启动速度。

**验收标准 (AC)**:
- AC-01: `import collaboration` 的 `__init__.py` 执行时间 < 100ms（仅 L1 Eager 层）
- AC-02: import 完成后，`WarmupManager.instance()` 已就绪且单例可用
- AC-03: import 期间不触发任何文件 I/O（PromptRegistry 等延后到 Async）
- AC-04: import 失败时给出清晰的错误信息（而非静默失败）
- AC-05: 即使 WarmupConfig.disabled=True，import 也应成功（只是跳过预热）

**边界场景**:
- B1: 首次 import vs 第 N 次 import 行为一致
- B2: 多线程并发 import 不死锁
- B3: 磁盘 I/O 极慢（如网络文件系统）时不阻塞 import

**用户旅程片段**:
```
开发者打开 Python REPL
  → 输入: from collaboration import Coordinator
  → 期望: < 100ms 内返回（当前是 ~1700ms）
  → 可立即开始使用
```

---

### US-3.02: 作为开发者，我希望重型模块按需懒加载

**背景**: 当前 __init__.py 导入 Scratchpad/Worker/Coordinator/ConsensusEngine/BatchScheduler/ContextCompressor/PermissionGuard/Skillifier 全部同步执行。实际上用户可能只用其中 1-2 个模块。

**验收标准 (AC)**:
- AC-01: `from collaboration import Coordinator` 首次访问时才真正 import coordinator.py
- AC-02: 懒加载对用户透明 — 用法不变，`isinstance(obj, Coordinator)` 正常工作
- AC-03: 懒加载后符号被缓存到 `globals()`，后续访问无额外开销
- AC-04: 访问不存在的属性时抛出 `AttributeError`（含模块名提示）
- AC-05: 数据模型类（EntryType/TaskDefinition 等）保持 eager import（轻量纯 dataclass）

**边界场景**:
- B1: 同时访问多个懒加载模块时的竞态条件
- B2: 懒加载模块自身 import 失败时的错误传播
- B3: `dir(collaboration)` 能看到所有可用符号（含懒加载的）

---

### US-3.03: 作为开发者，我希望可以选择预热模式

**背景**: 不同场景对启动速度要求不同：
- CLI 脚本：越快越好（fast 模式）
- Web 服务：可以接受稍慢但更全（full 模式）
- 单元测试：最小化依赖（disabled 或 fast 模式）

**验收标准 (AC)**:
- AC-01: 提供 `WarmupConfig.fast()` 配置：仅执行 core-models 预热（< 20ms）
- AC-02: 提供 `WarmupConfig.full()` 配置：全量预热所有层级
- AC-03: 提供 `WarmupConfig.default()` 配置：平衡模式（Eager+Async）
- AC-04: 支持 `WARMUP_MODE` 环境变量控制（`FAST`/`FULL`/`DEFAULT`/`DISABLED`）
- AC-05: 配置在首次 `instance()` 调用时生效，后续调用忽略新配置

**边界场景**:
- B1: 环境变量值非法时回退到 DEFAULT
- B2: 代码配置与环境变量冲突时以代码为准
- B3: 测试中可调用 `WarmupManager.reset()` 重置单例切换配置

---

## E2: 智能预热管理

### US-3.04: 作为系统，我希望自动识别并预加载 Top-N 高频资源

**背景**: 统计显示 80% 的任务只使用 3 个角色（architect/product-manager/solo-coder），但当前加载全部 5 个角色 + 8 个阶段。

**验收标准 (AC)**:
- AC-01: 默认预加载 Top 3 高频角色的完整提示词内容
- AC-02: Top 3 角色基于 ROLE_METADATA.priority 排序（10/9/8 → PM/Architect/SoloCoder）
- AC-03: 支持通过 WarmupConfig.preload_roles 自定义预加载列表
- AC-04: 预加载的角色提示词可通过 `wm.get("role_prompt:architect")` 直接获取
- AC-05: 未预加载的角色首次访问时走 LAZY 路径（< 100ms 加载）

**边界场景**:
- B1: preload_roles 为空列表时跳过角色预加载
- B2: preload_roles 包含不存在的 role_id 时跳过该角色并记录警告
- B3: 角色文件缺失时标记该任务 ERROR 但不阻塞其他任务

---

### US-3.05: 作为系统，我希望异步预热不阻塞主线程

**背景**: L2 Async 预热涉及文件 I/O（PromptRegistry 加载 ~150ms），如果在主线程执行会阻塞用户代码。

**验收标准 (AC)**:
- AC-01: `warmup_async()` 立即返回，不等待后台任务完成
- AC-02: 后台线程使用 ThreadPoolExecutor（默认 4 workers）
- AC-03: 异步任务间按依赖关系排序（registry-instance 依赖 role-metadata）
- AC-04: 单个异步任务超时时标记 TIMEOUT 并停止重试（默认 5s）
- AC-05: 所有异步任务完成或超后，`is_fully_warmed()` 返回 True

**边界场景**:
- B1: 异步任务抛出未预期异常时不崩溃主线程
- B2: 多次调用 `warmup_async()` 只执行一次（幂等）
- B3: 主线程退出时异步线程可优雅终止（shutdown）

---

### US-3.06: 作为开发者，我希望预热后的首次 API 调用 < 50ms

**背景**: 这是最终用户体验指标。无论底层做了多少优化，用户感知的是"从 import 到第一次有用操作"的总耗时。

**验收标准 (AC)**:
- AC-01: 预热完成后，`Coordinator(scratchpad=Scratchpad())` 创建耗时 < 50ms
- AC-02: 预热完成后，`PermissionGuard().check(action)` 首次调用 < 10ms（规则已预编译）
- AC-03: 预热完成后，`Skillifier().analyze_history([])` 创建耗时 < 30ms
- AC-04: 若某资源未预热完成，走 LAZY 路径的总耗时 < 200ms
- AC-05: 以上指标在 `benchmark(5)` 的 p95 分位内稳定满足

**边界场景**:
- B1: 首次调用时异步预热仍在进行（竞态）→ 应等待或返回部分可用状态
- B2: 缓存被 invalidate 后的首次调用（等同冷启动）
- B3: 连续 100 次创建 Coordinator 无内存泄漏

---

## E3: 进程级缓存

### US-3.07: 作为系统，我希望同一进程内的多次调用共享缓存

**背景**: 在 Web 服务或长运行进程中，可能多次创建 Coordinator/PermissionGuard 等。每次都重新初始化是浪费。

**验收标准 (AC)**:
- AC-01: `WarmupManager.instance()` 在同一进程内始终返回同一对象（`is` 相等）
- AC-02: 缓存的 PromptRegistry 对象多次 `get("prompt_registry")` 返回同一实例
- AC-03: 缓存条目记录 `access_count` 和 `last_accessed` 时间戳
- AC-04: 缓存命中时直接返回，不重新执行 loader 函数
- AC-05: 进程内缓存不持久化到磁盘（重启即丢失）

**边界场景**:
- B1: 多线程同时 `instance()` 不创建多个对象（线程安全单例）
- B2: `reset()` 后重新 `instance()` 创建全新对象（测试友好）
- B3: 缓存对象被外部修改后（如 mutability），下次 get 返回同一被修改对象

---

### US-3.08: 作为系统，我希望缓存有 TTL 过期和 LRU 淘汰机制

**背景**: 长时间运行的进程可能积累大量缓存条目，需要自动清理防止内存泄漏。

**验收标准 (AC)**:
- AC-01: 缓存条目支持 TTL（默认 3600 秒），过期后 `get()` 返回 None
- AC-02: 当缓存数量超过 `cache_max_size`（默认 200）时触发 LRU 淘汰
- AC-03: LRU 淘汰优先淘汰最久未访问的条目（非最早创建）
- AC-04: TTL 淘汰优先于 LRU 淘汰（先清过期再清空间）
- AC-05: 淘汰过程不影响正在进行的 get/set 操作（原子性）

**边界场景**:
- B1: cache_max_size=0 表示禁用缓存
- B2: TTL=0 表示永不过期
- B3: 并发淘汰和并发访问时的数据一致性

---

## E4: 可观测性

### US-3.09: 作为开发者，我希望随时查看预热状态和报告

**背景**: 当遇到性能问题时，需要知道哪些资源已预热、哪些还在进行、哪些失败了。

**验收标准 (AC)**:
- AC-01: `get_report()` 返回完整的 WarmupReport（总任务数/成功/失败/缓存命中/耗时）
- AC-02: `is_ready(task_id)` 可查询单个任务是否已完成
- AC-03: `is_fully_warmed()` 返回布尔值表示全部任务是否完成
- AC-04: 报告包含每个任务的 task_id/name/status/duration_ms/error
- AC-05: 报告包含生成时间戳

**边界场景**:
- B1: 尚未调用 warmup() 时报告显示 all PENDING
- B2: 部分 ASYNC 任务仍在进行时报告正确反映混合状态
- B3: 空任务列表时报告显示 0/0 完成

---

### US-3.10: 作为开发者，我希望获得详细的性能诊断信息

**背景**: 优化需要数据支撑。需要知道每个任务的精确耗时、缓存命中率、内存占用等。

**验收标准 (AC)**:
- AC-01: `print_diagnostics()` 输出格式化的诊断面板（类似 docker stats）
- AC-02: 诊断信息包含：startup_time/eager_duration/async_duration/cache_hit_rate/cache_size/memory_usage_mb
- AC-03: 诊断信息包含每个任务的 ✅/❌ 状态和毫秒级耗时
- AC-04: `get_metrics()` 返回结构化的 WarmupMetrics 对象（便于程序化处理）
- AC-05: Metrics 包含 lazy_loads_triggered 计数（了解 LAZY 路径使用频率）

**边界场景**:
- B1: metrics_enabled=False 时 get_metrics() 返回空/零值
- B2: 诊断输出宽度适配终端（不过宽也不过窄）
- B3: 含 Unicode 字符的系统正常显示 ✅❌ 图标

---

### US-3.11: 作为开发者，我希望可以运行基准测试对比性能

**背景**: 需要量化优化效果，对比优化前后的启动性能差异。

**验收标准 (AC)**:
- AC-01: `benchmark(iterations=5)` 执行多次预热并统计结果
- AC-02: 输出包含 mean/min/max/p50/p95 统计量（单位 ms）
- AC-03: 每次 benchmark 迭代会先 invalidate_all() 确保冷启动条件
- AC-04: benchmark 结果可作为回归检测基线保存
- AC-05: iterations=1 时仍能正常工作（快速单次测试）

---

## E5: 弹性与降级

### US-3.12: 作为系统，我希望预热失败时优雅降级

**背景**: 文件系统异常、权限问题、磁盘满等可能导致预热失败。系统不应因此不可用。

**验收标准 (AC)**:
- AC-01: Eager 任务失败时记录错误但不抛异常（标记 ERROR 状态）
- AC-02: Async 任务失败时自动重试 1 次，仍失败则标记 ERROR
- AC-03: 标记 ERROR 的任务在后续 `get()` 时走 LAZY 路径重新尝试
- AC-04: 全部 Eager 任务失败时，系统仍可基本使用（只是没有预热加速）
- AC-05: 降级路径写入日志（方便排查根因）

**边界场景**:
- B1: PromptRegistry 文件全部缺失 → registry-instance 标记 ERROR → 首次使用时再尝试加载
- B2: 网络文件系统暂时不可用 → 超时 → 降级
- B3: 内存不足导致缓存分配失败 → 回退到无缓存模式

---

### US-3.13: 作为开发者，我希望可以手动清除缓存和重新预热

**背景**: 开发过程中修改了提示词文件后，需要使缓存失效以加载最新版本。

**验收标准 (AC)**:
- AC-01: `invalidate(key)` 使单个缓存条目失效
- AC-02: `invalidate_all()` 清空全部缓存
- AC-03: invalidate 后重新 `warmup()` 可正常重新预热
- AC-04: invalidate 不会影响正在进行的异步任务（只清理缓存）
- AC-05: `shutdown()` 关闭线程池并释放资源（进程退出前调用）

**边界场景**:
- B1: invalidate 不存在的 key 不报错（no-op）
- B2: shutdown 后再次调用 get() 返回默认值（优雅降级）
- B3: shutdown 后再次 warmup() 重新创建线程池（恢复能力）

---

## 总结

### 验收标准矩阵

| Epic | 故事数 | AC 数量 | 核心指标 |
|------|--------|---------|---------|
| E1 快速启动 | 3 | 15 | import < 100ms |
| E2 智能预热 | 3 | 17 | 首次 API < 50ms |
| E3 进程缓存 | 2 | 10 | 单例一致性 |
| E4 可观测性 | 3 | 16 | 诊断完整性 |
| E5 弹性降级 | 2 | 10 | 优雅降级 |
| **合计** | **12** | **~68** | **启动 < 1s, 首次API < 50ms** |

### 边界场景清单

| # | 场景 | 影响 Epic | 风险等级 |
|---|------|----------|---------|
| B1 | 多线程并发安全 | E1/E3/E5 | 中 |
| B2 | 文件系统异常 | E2/E5 | 中 |
| B3 | 内存压力 | E3/E5 | 低 |
| B4 | 循环依赖 | E2 | 低 |
| B5 | 环境变量配置 | E1 | 低 |
| B6 | 缓存 mutability | E3 | 低 |
| B7 | Unicode 兼容性 | E4 | 低 |

### 用户旅程示例

#### 旅程 A: 典型 Web 服务启动
```
1. Web 框架启动 → import collaboration (~15ms, L1 only)
2. 应用初始化 → WarmupManager.instance().warmup() (L1+L2)
3. 首次请求到达 → Coordinator 创建 (< 50ms, 缓存命中)
4. 持续服务 → 所有组件复用缓存
```

#### 旅程 B: CLI 脚本快速执行
```
1. WARMUP_MODE=FAST python script.py
2. import collaboration (~10ms, minimal)
3. 执行任务（LAZY 按需加载所需模块）
4. 脚本退出 → 自动 cleanup
```
