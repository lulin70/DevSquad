# Phase 3: WarmupManager 启动优化系统 - 设计文档

**版本**: v1.0
**日期**: 2026-04-16
**状态**: 设计完成
**依赖**: Phase 1 (Coordinator) ✅, Phase 1-b (ContextCompressor) ✅, Phase 2-a (PermissionGuard) ✅, Phase 2-b (Skillify) ✅

---

## 1. 背景与动机

### 1.1 现状问题

当前 DevSquad v3 的启动流程存在以下性能瓶颈：

| # | 瓶颈点 | 当前行为 | 影响评估 |
|---|--------|---------|---------|
| B1 | **Eager Module Import** | `__init__.py` 同步导入 9 个模块（models→scratchpad→worker→consensus→coordinator→batch_scheduler→context_compressor→permission_guard→skillifier） | 🔴 高：~800ms 纯 import 开销 |
| B2 | **PromptRegistry 同步 I/O** | 构造时同步读取 5(roles) + 8(stages) + N(gates) + N(templates) 个 Markdown 文件 | 🟠 中：~300ms 文件 I/O |
| B3 | **Coordinator 即时创建** | 每次实例化立即创建 Scratchpad + ConsensusEngine + ContextCompressor | 🟡 中：~200ms 对象初始化 |
| B4 | **无预热机制** | 首次调用任何 API 时才触发实际资源加载（冷启动惩罚） | 🟡 中：~400ms 首次调用延迟 |
| B5 | **重复加载** | 每次 new PromptRegistry() 都重新读磁盘，无进程级缓存 | 🟢 低：可避免的重复 I/O |

**估算总冷启动时间**: ~1.7s → 目标 < 1.0s（减少 40%+）

### 1.2 设计目标

| 指标 | v3.0 当前基线 | v3.1 目标 | 测量方式 |
|------|-------------|----------|---------|
| 冷启动时间（import + 初始化） | ~1.7s | **< 1.0s** | `time.perf_counter()` 包裹 |
| 首次 API 调用延迟 | ~400ms | **< 50ms** | 预热后首次调用计时 |
| 内存占用增量 | 基准 | **< 15MB** | `tracemalloc` |
| 预热覆盖率 | 0% | **> 90%** 热路径资源 | 监控 cache hit rate |

### 1.3 核心策略

采用 **"分层异步预热 + 懒加载 + 进程级缓存"** 三合一策略：

```
┌─────────────────────────────────────────────────────┐
│                  WarmupManager                       │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ L1: Eager    │  │ L2: Async    │  │ L3: Lazy   │ │
│  │ 预热 (同步)   │  │ 预热 (后台)   │  │ 按需加载   │ │
│  ├──────────────┤  ├──────────────┤  ├────────────┤ │
│  │ • 核心数据模型│  │ • PromptRegistry│ │ • 低频角色 │ │
│  │ • 元数据映射  │  │   全量加载     │ │ • 冷门技能 │ │
│  │ • 常量定义    │  │ • Skill索引    │ │ • 扩展模块 │ │
│  │ (~50ms)      │  │ • 权限规则缓存 │ │            │ │
│  │              │  │ (~300ms)      │ │            │ │
│  └──────────────┘  └──────────────┘  └────────────┘ │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │           ProcessCache (进程级单例缓存)           │ │
│  │  • PromptRegistry 实例                           │ │
│  │  • 已解析的 RolePromptInfo / StagePromptInfo     │ │
│  │  • SkillLibrary 索引                            │ │
│  │  • PermissionRule 预编译正则                     │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 2. 架构设计

### 2.1 核心组件

#### 2.1.1 WarmupManager（预热管理器）

```python
@dataclass
class WarmupTask:
    task_id: str
    name: str
    priority: int              # 0=关键, 1=高, 2=中, 3=低
    layer: WarmupLayer         # EAGER / ASYNC / LAZY
    dependencies: List[str]    # 依赖的其他 task_id
    executor: Callable         # 实际执行的函数
    timeout_ms: int = 5000
    retry_count: int = 1

@dataclass
class WarmupResult:
    task_id: str
    status: WarmupStatus       # SUCCESS / TIMEOUT / ERROR / SKIPPED
    duration_ms: float
    error: Optional[str] = None
    cache_hit: bool = False

@dataclass
class WarmupReport:
    total_tasks: int
    completed: int
    failed: int
    cached: int
    total_duration_ms: float
    tasks: List[WarmupResult]
    timestamp: datetime

class WarmupLayer(Enum):
    EAGER = "eager"     # 同步阻塞，导入时立即执行
    ASYNC = "async"     # 后台线程异步执行
    LAZY = "lazy"       # 首次访问时按需触发

class WarmupStatus(Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"
    PENDING = "pending"

class WarmupManager:
    """启动预热管理器 - 分层预热 + 进程级缓存"""

    _instance: ClassVar[Optional['WarmupManager']] = None
    _lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self, config: Optional[WarmupConfig] = None):
        self.config = config or WarmupConfig.default()
        self._tasks: Dict[str, WarmupTask] = {}
        self._results: Dict[str, WarmupResult] = {}
        self._cache: Dict[str, Any] = {}          # 进程级缓存
        self._ready_flags: Dict[str, threading.Event] = {}
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._start_time: float = 0
        self._is_warming_up: bool = False

    def register_task(self, task: WarmupTask) -> None:
        """注册预热任务"""

    def warmup(self, layers: Optional[List[WarmupLayer]] = None) -> WarmupReport:
        """执行预热（按层级顺序）"""

    def warmup_eager(self) -> List[WarmupResult]:
        """L1: 同步执行关键任务"""

    def warmup_async(self) -> None:
        """L2: 后台异步执行高优任务"""

    def get(self, key: str, default: Any = None) -> Any:
        """从缓存获取预热的资源"""

    def get_or_load(self, key: str, loader: Callable[[], Any], layer: WarmupLayer = WarmupLayer.LAZY) -> Any:
        """获取缓存或按需加载"""

    def is_ready(self, task_id: str) -> bool:
        """检查特定任务是否已完成"""

    def is_fully_warmed(self) -> bool:
        """检查是否全部预热完成"""

    def get_report(self) -> WarmupReport:
        """获取预热报告"""

    def invalidate(self, key: str) -> None:
        """使缓存失效"""

    def invalidate_all(self) -> None:
        """清空所有缓存"""

    @classmethod
    def instance(cls) -> 'WarmupManager':
        """进程级单例"""

    def shutdown(self) -> None:
        """关闭资源"""
```

#### 2.1.2 WarmupConfig（配置）

```python
@dataclass
class WarmupConfig:
    enabled: bool = True
    eager_timeout_ms: int = 200          # L1 超时
    async_timeout_ms: int = 5000         # L2 超时
    async_workers: int = 4               # 异步线程数
    cache_enabled: bool = True
    cache_max_size: int = 200             # 最大缓存条目
    cache_ttl_seconds: int = 3600        # 缓存过期时间(秒)
    preload_roles: List[str] = None      # 预加载的角色列表(None=auto top3)
    preload_stages: List[str] = None     # 预加载的阶段列表(None=auto current)
    lazy_load_threshold: int = 3         # 访问N次后才考虑预热
    metrics_enabled: bool = False        # 是否收集性能指标

    @classmethod
    def default(cls) -> 'WarmupConfig':
        ...

    @classmethod
    def fast(cls) -> 'WarmupConfig':
        """快速模式：最小预热"""

    @classmethod
    def full(cls) -> 'WarmupConfig':
        """全量模式：最大化预热"""
```

#### 2.1.3 CacheEntry（缓存条目）

```python
@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: float           # time.time()
    last_accessed: float
    access_count: int = 0
    size_bytes: int = 0
    ttl_seconds: float = 3600
    source: str = ""            # 标识来源（便于调试）

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at
```

### 2.2 内置预热任务清单

WarmupManager 内置以下预热任务（按优先级排序）：

| Task ID | 名称 | 层级 | 依赖 | 预估耗时 | 缓存 Key |
|---------|------|------|------|---------|----------|
| `core-models` | 核心数据模型导入 | EAGER | 无 | ~10ms | `__models_loaded__` |
| `role-metadata` | 角色元数据（不含 prompt 内容） | EAGER | core-models | ~5ms | `role_metadata_map` |
| `registry-instance` | PromptRegistry 单例 | ASYNC | role-metadata | ~150ms | `prompt_registry` |
| `top-role-prompts` | Top3 角色提示词内容 | ASYNC | registry-instance | ~50ms | `role_prompt:{id}` |
| `current-stage` | 当前阶段模板 | ASYNC | registry-instance | ~30ms | `stage_prompt:{id}` |
| `permission-rules` | 权限规则预编译 | ASYNC | core-models | ~20ms | `permission_rules_compiled` |
| `skill-index` | 技能库索引 | ASYNC | registry-instance | ~40ms | `skill_library_index` |
| `coordinator-template` | Coordinator 快速初始化模板 | LAZY | registry-instance | ~100ms | `coordinator_template` |
| `compressor-config` | Compressor 配置预加载 | LAZY | 无 | ~5ms | `compressor_config` |

### 2.3 执行流程

```
用户调用 import collaboration
        │
        ▼
   ┌─────────────────────┐
   │  WarmupManager.instance() │  ← 单例创建（首次）
   │  注册内置任务列表       │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  L1: warmup_eager()  │  ← 同步阻塞
   │  • core-models       │
   │  • role-metadata     │
   │  耗时: ~15ms         │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  L2: warmup_async()  │  ← 后台线程（非阻塞）
   │  • registry-instance │
   │  • top-role-prompts  │
   │  • current-stage     │
   │  • permission-rules  │
   │  • skill-index       │
   │  耗时: ~300ms (异步) │
   └──────────┬──────────┘
              │
              ▼
   import 完成，控制权返回用户
   （总阻塞时间: ~15ms 而非 ~1.7s）
       
       ... 后台继续 ...
              │
              ▼
   L2 任务陆续完成 → 写入缓存
   用户首次调用 API 时：
   ├── 缓存命中 → 直接返回 (< 1ms)
   └── 缓存未命中 → 触发 LAZY 加载 → 返回
```

---

## 3. 详细设计

### 3.1 进程级单例模式

```python
class WarmupManager:
    _instance: ClassVar[Optional['WarmupManager']] = None
    _lock: ClassVar[threading.RLock] = threading.RLock()

    @classmethod
    def instance(cls, config: Optional[WarmupConfig] = None) -> 'WarmupManager':
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(config=config)
                cls._instance._register_builtin_tasks()
            elif config is not None:
                pass  # 已存在则忽略新配置（首次有效）
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """测试用：重置单例"""
        with cls._lock:
            if cls._instance:
                cls._instance.shutdown()
            cls._instance = None
```

### 3.2 L1 Eager 预热实现

```python
def warmup_eager(self) -> List[WarmupResult]:
    """同步执行所有 EAGER 层级任务（按依赖拓扑排序）"""
    eager_tasks = [t for t in self._tasks.values() if t.layer == WarmupLayer.EAGER]
    sorted_tasks = self._topological_sort(eager_tasks)
    results = []

    for task in sorted_tasks:
        start = time.perf_counter()
        try:
            result = task.executor()
            duration = (time.perf_counter() - start) * 1000
            self._cache[task.task_id] = CacheEntry(
                key=task.task_id, value=result,
                created_at=time.time(), last_accessed=time.time(),
                source=f"eager:{task.name}"
            )
            results.append(WarmupResult(
                task_id=task.task_id, status=WarmupStatus.SUCCESS,
                duration_ms=duration
            ))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            results.append(WarmupResult(
                task_id=task.task_id, status=WarmupStatus.ERROR,
                duration_ms=duration, error=str(e)
            ))

    self._start_time = time.perf_counter()
    return results
```

### 3.3 L2 Async 预热实现

```python
def warmup_async(self) -> None:
    """后台异步执行 ASYNC 层级任务"""
    if self._executor is not None:
        return  # 已经在预热中

    async_tasks = [t for t in self._tasks.values() if t.layer == WarmupLayer.ASYNC]
    sorted_tasks = self._topological_sort(async_tasks)

    self._executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=self.config.async_workers,
        thread_name_prefix="warmup"
    )
    self._is_warming_up = True

    futures = {}
    for task in sorted_tasks:
        future = self._executor.submit(self._execute_task, task)
        futures[future] = task

    def on_done(future):
        task = futures.pop(future, None)
        if task:
            try:
                future.result(timeout=task.timeout_ms / 1000)
            except Exception:
                pass

    for future in futures:
        future.add_done_callback(on_done)
```

### 3.4 缓存管理

```python
def get(self, key: str, default: Any = None) -> Any:
    """从缓存获取"""
    entry = self._cache.get(key)
    if entry is None:
        return default
    if entry.is_expired:
        del self._cache[key]
        return default
    entry.last_accessed = time.time()
    entry.access_count += 1
    return entry.value

def get_or_load(self, key: str, loader: Callable[[], Any],
                layer: WarmupLayer = WarmupLayer.LAZY) -> Any:
    """获取或按需加载（带防抖动）"""
    value = self.get(key)
    if value is not None:
        return value

    if key not in self._ready_flags:
        self._ready_flags[key] = threading.Event()

    if not self._ready_flags[key].is_set():
        with self._lock:
            if not self._ready_flags[key].is_set():
                result = loader()
                self._cache[key] = CacheEntry(
                    key=key, value=result,
                    created_at=time.time(), last_accessed=time.time(),
                    source=f"lazy:{key}"
                )
                self._ready_flags[key].set()

    self._ready_flags[key].wait(timeout=30)
    return self.get(key)

def _evict_if_needed(self) -> None:
    """LRU + TTL 淘汰策略"""
    if len(self._cache) <= self.config.cache_max_size:
        return
    now = time.time()
    expired = [k for k, v in self._cache.items() if v.is_expired]
    for k in expired:
        del self._cache[k]

    if len(self._cache) > self.config.cache_max_size:
        sorted_by_lru = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )
        excess = len(self._cache) - self.config.cache_max_size
        for k, _ in sorted_by_lru[:excess]:
            del self._cache[k]
```

### 3.5 依赖解析（拓扑排序）

```python
def _topological_sort(self, tasks: List[WarmupTask]) -> List[WarmupTask]:
    """基于依赖关系的拓扑排序（Kahn 算法）"""
    task_map = {t.task_id: t for t in tasks}
    in_degree = {t.task_id: 0 for t in tasks}
    adj = {t.task_id: [] for t in tasks}

    for task in tasks:
        for dep in task.dependencies:
            if dep in in_degree:
                adj[dep].append(task.task_id)
                in_degree[task.task_id] += 1

    queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
    result = []

    while queue:
        tid = queue.popleft()
        if tid in task_map:
            result.append(task_map[tid])
        for neighbor in adj[tid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(tasks):
        remaining = [t.name for t in tasks if t not in result]
        raise ValueError(f"循环依赖检测: {remaining}")

    return result
```

---

## 4. 与现有系统集成

### 4.1 __init__.py 改造

改造前（当前 — 全部 eager import）：
```python
from .models import (...)          # ~80ms
from .scratchpad import Scratchpad  # ~30ms
from .worker import Worker, ...     # ~50ms
from .consensus import ConsensusEngine  # ~40ms
from .coordinator import Coordinator    # ~100ms
from .batch_scheduler import BatchScheduler  # ~30ms
from .context_compressor import (...)  # ~60ms
from .permission_guard import (...)   # ~120ms
from .skillifier import (...)         # ~150ms
# 总计: ~660ms 纯 import 时间
```

改造后（Warmup 管理）：
```python
import time
from .warmup_manager import WarmupManager, WarmupConfig

_wm = WarmupManager.instance()
_wm.warmup(layers=[WarmupLayer.EAGER])   # ~15ms 同步

# 类型注解级别的 import（轻量）
from .models import (
    EntryType, EntryStatus, ...,  # 数据模型（纯 dataclass，快）
)

# 重型模块延迟导出
def __getattr__(name):
    """懒加载重型模块"""
    _lazy_modules = {
        'Scratchpad': ('.scratchpad', 'Scratchpad'),
        'Worker': ('.worker', 'Worker'),
        'Coordinator': ('.coordinator', 'Coordinator'),
        'ConsensusEngine': ('.consensus', 'ConsensusEngine'),
        'BatchScheduler': ('.batch_scheduler', 'BatchScheduler'),
        'ContextCompressor': ('.context_compressor', 'ContextCompressor'),
        'PermissionGuard': ('.permission_guard', 'PermissionGuard'),
        'Skillifier': ('.skillifier', 'Skillifier'),
        # ... 其他符号
    }
    if name in _lazy_modules:
        mod_path, attr = _lazy_modules[name]
        import importlib
        mod = importlib.import_module(mod_path, package=__package__)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name}")
```

### 4.2 PromptRegistry 集成

```python
# WarmupManager 内置任务: registry-instance
def _load_registry():
    from prompts.registry import PromptRegistry
    registry = PromptRegistry()
    return registry

task = WarmupTask(
    task_id="registry-instance",
    name="PromptRegistry 全量加载",
    priority=1,
    layer=WarmupLayer.ASYNC,
    dependencies=["role-metadata"],
    executor=_load_registry,
    timeout_ms=5000,
)
```

### 4.3 Coordinator 快速路径

```python
# 预热后的 Coordinator 创建（复用已缓存的组件）
def create_coordinator_fast(scratchpad=None):
    wm = WarmupManager.instance()
    registry = wm.get("prompt_registry")
    compressor_config = wm.get("compressor_config")

    coordinator = Coordinator(
        scratchpad=scratchpad,
        enable_compression=True,
        compression_threshold=compressor_config.get("threshold", 100000),
    )
    return coordinator
```

---

## 5. 性能指标与监控

### 5.1 内置 Metrics 收集

```python
@dataclass
class WarmupMetrics:
    startup_time_ms: float
    eager_duration_ms: float
    async_duration_ms: float
    cache_hit_rate: float
    cache_size: int
    memory_usage_mb: float
    tasks_completed: int
    tasks_failed: int
    lazy_loads_triggered: int

class WarmupManager:
    def get_metrics(self) -> WarmupMetrics:
        """收集当前性能指标"""
        total_hits = sum(e.access_count for e in self._cache.values())
        total_misses = sum(1 for e in self._cache.values() if e.access_count == 0)
        hit_rate = total_hits / (total_hits + max(total_misses, 1))

        return WarmupMetrics(
            startup_time_ms=(time.perf_counter() - self._start_time) * 1000,
            eager_duration=sum(r.duration_ms for r in self._results.values()
                             if r.task_id in self._eager_task_ids),
            async_duration=...,
            cache_hit_rate=hit_rate,
            cache_size=len(self._cache),
            memory_usage_mb=self._estimate_memory(),
            tasks_completed=sum(1 for r in self._results.values()
                               if r.status == WarmupStatus.SUCCESS),
            tasks_failed=sum(1 for r in self._results.values()
                            if r.status in (WarmupStatus.ERROR, WarmupStatus.TIMEOUT)),
            lazy_loads_triggered=self._lazy_load_count,
        )

    def print_diagnostics(self) -> str:
        """输出诊断信息（用于调试和调优）"""
        m = self.get_metrics()
        lines = [
            f"=== WarmupManager Diagnostics ===",
            f"Startup: {m.startup_time_ms:.1f}ms",
            f"Eager: {m.eager_duration_ms:.1f}ms | Async: {m.async_duration_ms:.1f}ms",
            f"Cache: {m.cache_size} entries | Hit Rate: {m.cache_hit_rate:.1%}",
            f"Memory: {m.memory_usage_mb:.1f}MB",
            f"Tasks: {m.tasks_completed}/{m.tasks_completed+m.tasks_failed}",
            f"Lazy loads triggered: {m.lazy_loads_triggered}",
        ]
        for rid, result in sorted(self._results.items()):
            status_icon = "✅" if result.status == WarmupStatus.SUCCESS else "❌"
            lines.append(f"  {status_icon} {rid}: {result.duration_ms:.1f}ms")
        return "\n".join(lines)
```

### 5.2 性能基准测试接口

```python
class WarmupManager:
    def benchmark(self, iterations: int = 5) -> Dict[str, Any]:
        """运行性能基准测试"""
        times = []
        for _ in range(iterations):
            self.invalidate_all()
            self._results.clear()
            start = time.perf_counter()
            self.warmup()
            while not self.is_fully_warmed():
                time.sleep(0.01)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        return {
            "mean_ms": statistics.mean(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "p50_ms": statistics.median(times),
            "p95_ms": sorted(times)[int(len(times) * 0.95)],
            "iterations": iterations,
        }
```

---

## 6. 边界情况与错误处理

### 6.1 异常处理矩阵

| 场景 | 处理策略 | 行为 |
|------|---------|------|
| Eager 任务超时 | 记录错误，跳过，标记 TIMEOUT | 不阻塞启动 |
| Async 任务失败 | 重试 1 次，仍失败则标记 ERROR | 后续走 LAZY 路径 |
| 循环依赖检测 | 拓扑排序阶段抛出 ValueError | 启动时明确报错 |
| 缓存内存溢出 | LRU + TTL 淘汰 | 自动清理最久未访问条目 |
| 单例重复创建 | 忽略后续配置 | 使用首次配置 |
| shutdown 后访问 | 返回默认值/重新创建 | 优雅降级 |
| 并发 get_or_load | Event 锁防抖动 | 只执行一次 loader |

### 6.2 降级策略

当预热失败时的降级路径：

```
EASY 模式 (config.fast()):
  └── 只执行 core-models，其余全部 LAZY

正常模式 (config.default()):
  └── L1+Eager + L2+Async，失败项降级为 LAZY

FULL 模式 (config.full()):
  └── 全量预热 + 更长超时 + 更多重试
```

---

## 7. 测试策略

### 7.1 测试分层

| 层级 | 范围 | 用例数估计 | 重点 |
|------|------|-----------|------|
| T1 | 数据模型 (Config/CacheEntry/Result) | ~10 | 序列化、默认值、验证 |
| T2 | WarmupManager 核心逻辑 | ~18 | 注册/执行/缓存/单例 |
| T3 | L1 Eager 预热 | ~8 | 同步执行、超时、依赖排序 |
| T4 | L2 Async 预热 | ~10 | 并发、回调、线程安全 |
| T5 | 缓存管理 | ~12 | TTL/LRU淘汰、命中率、并发读写 |
| T6 | 依赖解析 | ~6 | 拓扑排序、循环检测、空依赖 |
| T7 | 性能 & Metrics | ~8 | 基准测试、诊断输出、内存估算 |
| T8 | 边界情况 | ~10 | 降级、shutdown、空任务、重复注册 |
| IT1 | 与 Coordinator 集成 | ~6 | 预热后快速创建 |
| IT2 | 与 PromptRegistry 集成 | ~4 | 缓存的 Registry 复用 |
| **合计** | | **~92** | |

### 7.2 关键验收标准

- AC-01: `import collaboration` 总耗时 < 100ms（L1 only）
- AC-02: 异步预热在 500ms 内完成 L2 全部任务
- AC-03: 预热后首次 `Coordinator()` 创建 < 50ms
- AC-04: 缓存命中率达到 > 85%（模拟典型工作流）
- AC-05: 进程内多次 `WarmupManager.instance()` 返回同一对象
- AC-06: 循环依赖正确检测并抛出异常
- AC-07: `invalidate_all()` 后重新预热可正常工作
- AC-08: `benchmark()` 输出包含 mean/min/max/p50/p95

---

## 8. 文件结构

```
scripts/collaboration/
├── warmup_manager.py          # ★ 新增：核心模块 (~500行)
├── warmup_manager_test.py     # ★ 新增：测试 (~92 cases)
├── __init__.py                # 修改：集成 Warmup 入口
├── models.py                  # 已有
├── scratchpad.py              # 已有
├── worker.py                  # 已有
├── consensus.py               # 已有
├── coordinator.py             # 已有
├── batch_scheduler.py         # 已有
├── context_compressor.py      # 已有
├── permission_guard.py        # 已有 (P2-a)
└── skillifier.py              # 已有 (P2-b)
```

---

## 9. 实施检查清单

- [ ] **C1**: 实现 WarmupTask/WarmupResult/WarmupReport/WarmupConfig/CacheEntry 数据模型
- [ ] **C2**: 实现 WarmupManager 核心类（单例、注册、执行、缓存）
- [ ] **C3**: 实现 L1 Eager 预热（同步、拓扑排序、超时处理）
- [ ] **C4**: 实现 L2 Async 预热（ThreadPoolExecutor、回调、Future）
- [ ] **C5**: 实现 LAZY 按需加载（get_or_load、Event 防抖动）
- [ ] **C6**: 实现缓存管理（TTL、LRU淘汰、容量限制）
- [ ] **C7**: 实现依赖解析（拓扑排序、循环检测）
- [ ] **C8**: 实现 Metrics 收集和 Diagnostics 输出
- [ ] **C9**: 实现 benchmark() 基准测试方法
- [ ] **C10**: 集成到 __init__.py（条件性懒加载）
- [ ] **C11**: 编写测试用例（目标 92+ cases）
- [ ] **C12]: 全量回归测试（389 + 新增 = ~481+）
