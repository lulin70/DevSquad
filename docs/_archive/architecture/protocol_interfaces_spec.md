# Protocol 接口规范

> **文档类型**：架构设计文档
> 
> **版本**：v1.0
> 
> **创建日期**：2026-05-01
> 
> **负责人**：Architect
> 
> **状态**：待评审

---

## 一、概述

本文档定义 DevSquad v3.5 的核心 Protocol 接口规范，包括：
- CacheProvider：缓存提供者接口
- RetryProvider：重试提供者接口
- MonitorProvider：监控提供者接口
- MemoryProvider：记忆提供者接口（为 CarryMem 预留）

所有 Protocol 遵循以下设计原则：
1. **松耦合**：通过抽象接口而非具体实现依赖
2. **可降级**：提供 `is_available()` 方法支持降级检测
3. **版本化**：提供 `version()` 方法支持接口演进
4. **异常安全**：明确定义异常处理规范

---

## 二、CacheProvider 接口

### 2.1 接口定义

```python
from typing import Protocol, Any, Optional
from datetime import timedelta

class CacheProvider(Protocol):
    """缓存提供者接口
    
    用于缓存 LLM 响应、Agent 执行结果等数据，减少重复计算。
    
    实现要求：
    - 线程安全：支持多线程并发访问
    - 过期策略：支持 TTL（Time To Live）
    - 容量管理：支持 LRU 或其他淘汰策略
    """
    
    def version(self) -> str:
        """返回 Protocol 版本
        
        Returns:
            版本号，遵循语义化版本（Semantic Versioning），如 "1.0.0"
        
        Example:
            >>> cache.version()
            "1.0.0"
        """
        ...
    
    def is_available(self) -> bool:
        """检查缓存是否可用
        
        Returns:
            True 表示缓存可用，False 表示不可用（需要降级）
        
        Note:
            - 实现应该快速返回（< 10ms）
            - 不应抛出异常
            - 可以检查：连接状态、磁盘空间、权限等
        
        Example:
            >>> if cache.is_available():
            ...     value = cache.get("key")
            ... else:
            ...     # 降级到 NullCacheProvider
            ...     value = None
        """
        ...
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值
        
        Args:
            key: 缓存键，建议格式："{namespace}:{identifier}"
                 如 "llm:gpt4:hash_abc123"
        
        Returns:
            缓存值，如果不存在或已过期返回 None
        
        Raises:
            CacheError: 缓存操作失败（如网络错误、权限错误）
        
        Example:
            >>> cache.get("llm:gpt4:hash_abc123")
            {"response": "Hello, world!", "tokens": 10}
        """
        ...
    
    def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值，必须可序列化（JSON、Pickle 等）
            ttl: 过期时间（秒），None 表示使用默认值（86400 秒 = 1 天）
        
        Returns:
            True 表示设置成功，False 表示设置失败
        
        Raises:
            CacheError: 缓存操作失败
            ValueError: value 不可序列化
        
        Example:
            >>> cache.set("llm:gpt4:hash_abc123", {"response": "Hi"}, ttl=3600)
            True
        """
        ...
    
    def delete(self, key: str) -> bool:
        """删除缓存值
        
        Args:
            key: 缓存键
        
        Returns:
            True 表示删除成功，False 表示键不存在
        
        Raises:
            CacheError: 缓存操作失败
        
        Example:
            >>> cache.delete("llm:gpt4:hash_abc123")
            True
        """
        ...
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """清空缓存
        
        Args:
            pattern: 可选的键模式（支持通配符），None 表示清空所有
                     如 "llm:gpt4:*" 清空所有 GPT-4 缓存
        
        Returns:
            删除的键数量
        
        Raises:
            CacheError: 缓存操作失败
        
        Example:
            >>> cache.clear("llm:gpt4:*")
            42
        """
        ...
    
    def exists(self, key: str) -> bool:
        """检查键是否存在
        
        Args:
            key: 缓存键
        
        Returns:
            True 表示存在且未过期，False 表示不存在或已过期
        
        Raises:
            CacheError: 缓存操作失败
        
        Example:
            >>> cache.exists("llm:gpt4:hash_abc123")
            True
        """
        ...
    
    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计信息
        
        Returns:
            统计信息字典，包含：
            - hits: 命中次数
            - misses: 未命中次数
            - hit_rate: 命中率（0-1）
            - size: 当前缓存大小（字节）
            - count: 当前缓存键数量
        
        Example:
            >>> cache.get_stats()
            {
                "hits": 1000,
                "misses": 200,
                "hit_rate": 0.833,
                "size": 1048576,
                "count": 42
            }
        """
        ...
```

### 2.2 异常定义

```python
class CacheError(Exception):
    """缓存操作异常基类"""
    pass

class CacheConnectionError(CacheError):
    """缓存连接异常（如 Redis 连接失败）"""
    pass

class CacheSerializationError(CacheError):
    """缓存序列化异常（如对象不可序列化）"""
    pass

class CachePermissionError(CacheError):
    """缓存权限异常（如磁盘写入权限不足）"""
    pass
```

### 2.3 Null 实现

```python
class NullCacheProvider:
    """空缓存实现——用于降级和测试
    
    特点：
    - is_available() 返回 False
    - 所有操作静默成功，不抛异常
    - get() 总是返回 None
    - set() 总是返回 True
    """
    
    def version(self) -> str:
        return "1.0.0"
    
    def is_available(self) -> bool:
        return False
    
    def get(self, key: str) -> None:
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return True
    
    def delete(self, key: str) -> bool:
        return True
    
    def clear(self, pattern: Optional[str] = None) -> int:
        return 0
    
    def exists(self, key: str) -> bool:
        return False
    
    def get_stats(self) -> dict[str, Any]:
        return {
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
            "size": 0,
            "count": 0
        }
```

---

## 三、RetryProvider 接口

### 3.1 接口定义

```python
from typing import Protocol, Callable, TypeVar, ParamSpec, Any
from dataclasses import dataclass

P = ParamSpec('P')
T = TypeVar('T')

@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3              # 最大重试次数
    initial_delay: float = 1.0         # 初始延迟（秒）
    max_delay: float = 60.0            # 最大延迟（秒）
    exponential_base: float = 2.0      # 指数退避基数
    jitter: bool = True                # 是否添加随机抖动

class RetryProvider(Protocol):
    """重试提供者接口
    
    用于处理 LLM API 调用失败、网络超时等临时性错误。
    
    实现要求：
    - 支持指数退避（Exponential Backoff）
    - 支持随机抖动（Jitter）避免雷鸣群效应
    - 支持自定义重试条件
    """
    
    def version(self) -> str:
        """返回 Protocol 版本"""
        ...
    
    def is_available(self) -> bool:
        """检查重试机制是否可用"""
        ...
    
    def retry(
        self,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs
    ) -> T:
        """执行函数，失败时自动重试
        
        Args:
            func: 要执行的函数
            *args: 函数位置参数
            **kwargs: 函数关键字参数
        
        Returns:
            函数返回值
        
        Raises:
            原函数的异常（重试次数耗尽后）
        
        Example:
            >>> def call_llm(prompt: str) -> str:
            ...     return llm.generate(prompt)
            >>> 
            >>> result = retry.retry(call_llm, "Hello")
        """
        ...
    
    def retry_with_config(
        self,
        func: Callable[P, T],
        config: RetryConfig,
        *args: P.args,
        **kwargs: P.kwargs
    ) -> T:
        """使用自定义配置执行重试
        
        Args:
            func: 要执行的函数
            config: 重试配置
            *args: 函数位置参数
            **kwargs: 函数关键字参数
        
        Returns:
            函数返回值
        
        Example:
            >>> config = RetryConfig(max_attempts=5, initial_delay=2.0)
            >>> result = retry.retry_with_config(call_llm, config, "Hello")
        """
        ...
    
    def should_retry(self, exception: Exception) -> bool:
        """判断异常是否应该重试
        
        Args:
            exception: 捕获的异常
        
        Returns:
            True 表示应该重试，False 表示不应重试
        
        Note:
            - 临时性错误应该重试：网络超时、429 Too Many Requests
            - 永久性错误不应重试：401 Unauthorized、400 Bad Request
        
        Example:
            >>> retry.should_retry(TimeoutError())
            True
            >>> retry.should_retry(ValueError("Invalid input"))
            False
        """
        ...
    
    def get_stats(self) -> dict[str, Any]:
        """获取重试统计信息
        
        Returns:
            统计信息字典，包含：
            - total_attempts: 总尝试次数
            - total_retries: 总重试次数
            - success_rate: 成功率（0-1）
            - avg_attempts: 平均尝试次数
        
        Example:
            >>> retry.get_stats()
            {
                "total_attempts": 1000,
                "total_retries": 150,
                "success_rate": 0.985,
                "avg_attempts": 1.15
            }
        """
        ...
```

### 3.2 Null 实现

```python
class NullRetryProvider:
    """空重试实现——直接执行，不重试"""
    
    def version(self) -> str:
        return "1.0.0"
    
    def is_available(self) -> bool:
        return False
    
    def retry(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        return func(*args, **kwargs)
    
    def retry_with_config(
        self, func: Callable[P, T], config: RetryConfig, *args: P.args, **kwargs: P.kwargs
    ) -> T:
        return func(*args, **kwargs)
    
    def should_retry(self, exception: Exception) -> bool:
        return False
    
    def get_stats(self) -> dict[str, Any]:
        return {
            "total_attempts": 0,
            "total_retries": 0,
            "success_rate": 1.0,
            "avg_attempts": 1.0
        }
```

---

## 四、MonitorProvider 接口

### 4.1 接口定义

```python
from typing import Protocol, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str                          # 指标名称
    duration: float                    # 执行时长（秒）
    success: bool                      # 是否成功
    timestamp: datetime                # 时间戳
    metadata: dict[str, Any]           # 元数据

class MonitorProvider(Protocol):
    """监控提供者接口
    
    用于监控 Agent 执行性能、LLM API 调用延迟等指标。
    
    实现要求：
    - 低开销：监控本身不应显著影响性能（< 1% 开销）
    - 异步记录：不阻塞主流程
    - 聚合统计：支持按时间窗口聚合
    """
    
    def version(self) -> str:
        """返回 Protocol 版本"""
        ...
    
    def is_available(self) -> bool:
        """检查监控是否可用"""
        ...
    
    def track(
        self,
        name: str,
        duration: float,
        success: bool = True,
        metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """记录性能指标
        
        Args:
            name: 指标名称，建议格式："{category}.{operation}"
                  如 "agent.architect.execute"
            duration: 执行时长（秒）
            success: 是否成功
            metadata: 可选的元数据（如 token 数量、错误信息）
        
        Example:
            >>> monitor.track(
            ...     "agent.architect.execute",
            ...     duration=2.5,
            ...     success=True,
            ...     metadata={"tokens": 1500}
            ... )
        """
        ...
    
    def track_context(self, name: str) -> Any:
        """返回上下文管理器，自动记录执行时长
        
        Args:
            name: 指标名称
        
        Returns:
            上下文管理器
        
        Example:
            >>> with monitor.track_context("agent.architect.execute"):
            ...     result = agent.execute(task)
        """
        ...
    
    def get_stats(
        self,
        name: Optional[str] = None,
        window: Optional[int] = None
    ) -> dict[str, Any]:
        """获取统计信息
        
        Args:
            name: 可选的指标名称（支持通配符），None 表示所有指标
            window: 可选的时间窗口（秒），None 表示全部历史
        
        Returns:
            统计信息字典，包含：
            - count: 调用次数
            - success_rate: 成功率（0-1）
            - avg_duration: 平均时长（秒）
            - p50_duration: 50 分位时长
            - p95_duration: 95 分位时长
            - p99_duration: 99 分位时长
        
        Example:
            >>> monitor.get_stats("agent.architect.*", window=3600)
            {
                "count": 100,
                "success_rate": 0.98,
                "avg_duration": 2.3,
                "p50_duration": 2.1,
                "p95_duration": 4.5,
                "p99_duration": 6.2
            }
        """
        ...
    
    def export_metrics(self, format: str = "json") -> str:
        """导出指标数据
        
        Args:
            format: 导出格式，支持 "json"、"csv"、"prometheus"
        
        Returns:
            格式化的指标数据
        
        Example:
            >>> metrics = monitor.export_metrics("json")
            >>> with open("metrics.json", "w") as f:
            ...     f.write(metrics)
        """
        ...
```

### 4.2 Null 实现

```python
from contextlib import contextmanager

class NullMonitorProvider:
    """空监控实现——不记录任何指标"""
    
    def version(self) -> str:
        return "1.0.0"
    
    def is_available(self) -> bool:
        return False
    
    def track(
        self, name: str, duration: float, success: bool = True, metadata: Optional[dict] = None
    ) -> None:
        pass
    
    @contextmanager
    def track_context(self, name: str):
        yield
    
    def get_stats(self, name: Optional[str] = None, window: Optional[int] = None) -> dict:
        return {
            "count": 0,
            "success_rate": 1.0,
            "avg_duration": 0.0,
            "p50_duration": 0.0,
            "p95_duration": 0.0,
            "p99_duration": 0.0
        }
    
    def export_metrics(self, format: str = "json") -> str:
        return "{}" if format == "json" else ""
```

---

## 五、MemoryProvider 接口

### 5.1 接口定义

```python
from typing import Protocol, Any, Optional
from dataclasses import dataclass

@dataclass
class Rule:
    """规则定义"""
    rule_id: str                       # 规则 ID
    role: str                          # 适用角色
    condition: str                     # 触发条件
    action: str                        # 执行动作
    priority: int                      # 优先级（数字越大越优先）
    metadata: dict[str, Any]           # 元数据

class MemoryProvider(Protocol):
    """记忆提供者接口（为 CarryMem 预留）
    
    用于存储和检索个人化规则、历史经验等。
    
    实现要求：
    - 支持规则匹配（基于任务、角色、上下文）
    - 支持经验学习（记录成功/失败案例）
    - 支持规则优先级
    """
    
    def version(self) -> str:
        """返回 Protocol 版本"""
        ...
    
    def is_available(self) -> bool:
        """检查记忆系统是否可用"""
        ...
    
    def match_rules(
        self,
        task: str,
        role: str,
        context: Optional[dict[str, Any]] = None
    ) -> list[Rule]:
        """匹配适用的规则
        
        Args:
            task: 任务描述
            role: Agent 角色（如 "Architect"、"PM"）
            context: 可选的上下文信息
        
        Returns:
            匹配的规则列表，按优先级排序
        
        Example:
            >>> rules = memory.match_rules(
            ...     task="设计 REST API",
            ...     role="Architect",
            ...     context={"language": "Python"}
            ... )
            >>> for rule in rules:
            ...     print(f"{rule.rule_id}: {rule.action}")
        """
        ...
    
    def log_experience(
        self,
        user_id: str,
        task: str,
        role: str,
        outcome: str,
        metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """记录执行经验
        
        Args:
            user_id: 用户 ID
            task: 任务描述
            role: Agent 角色
            outcome: 执行结果（"success"、"failure"）
            metadata: 可选的元数据（如错误信息、性能指标）
        
        Example:
            >>> memory.log_experience(
            ...     user_id="user123",
            ...     task="设计 REST API",
            ...     role="Architect",
            ...     outcome="success",
            ...     metadata={"duration": 2.5, "tokens": 1500}
            ... )
        """
        ...
    
    def get_stats(self, user_id: str) -> dict[str, Any]:
        """获取用户统计信息
        
        Args:
            user_id: 用户 ID
        
        Returns:
            统计信息字典，包含：
            - total_tasks: 总任务数
            - success_rate: 成功率（0-1）
            - active_rules: 活跃规则数
            - last_updated: 最后更新时间
        
        Example:
            >>> memory.get_stats("user123")
            {
                "total_tasks": 100,
                "success_rate": 0.95,
                "active_rules": 15,
                "last_updated": "2026-05-01T12:00:00Z"
            }
        """
        ...
```

### 5.2 Null 实现

```python
class NullMemoryProvider:
    """空记忆实现——不存储任何规则"""
    
    def version(self) -> str:
        return "1.0.0"
    
    def is_available(self) -> bool:
        return False
    
    def match_rules(
        self, task: str, role: str, context: Optional[dict] = None
    ) -> list[Rule]:
        return []
    
    def log_experience(
        self, user_id: str, task: str, role: str, outcome: str, metadata: Optional[dict] = None
    ) -> None:
        pass
    
    def get_stats(self, user_id: str) -> dict[str, Any]:
        return {
            "total_tasks": 0,
            "success_rate": 1.0,
            "active_rules": 0,
            "last_updated": None
        }
```

---

## 六、版本兼容性

### 6.1 版本号规范

所有 Protocol 使用语义化版本（Semantic Versioning）：

- **主版本号（Major）**：不兼容的 API 变更
- **次版本号（Minor）**：向后兼容的功能新增
- **修订号（Patch）**：向后兼容的问题修正

示例：
- `1.0.0` → `1.1.0`：新增方法（向后兼容）
- `1.1.0` → `2.0.0`：修改方法签名（不兼容）

### 6.2 兼容性检查

```python
def check_compatibility(provider: Any, required_version: str) -> bool:
    """检查 Provider 版本是否兼容
    
    Args:
        provider: Provider 实例
        required_version: 要求的最低版本
    
    Returns:
        True 表示兼容，False 表示不兼容
    
    Example:
        >>> cache = LLMCache()
        >>> check_compatibility(cache, "1.0.0")
        True
    """
    from packaging import version
    
    provider_version = provider.version()
    return version.parse(provider_version) >= version.parse(required_version)
```

---

## 七、使用示例

### 7.1 Agent 基类集成

```python
class DevSquadAgent:
    """Agent 基类——支持可选 Provider"""
    
    def __init__(
        self,
        agent_id: str,
        role: str,
        cache: Optional[CacheProvider] = None,
        retry: Optional[RetryProvider] = None,
        monitor: Optional[MonitorProvider] = None,
        memory: Optional[MemoryProvider] = None
    ):
        self.agent_id = agent_id
        self.role = role
        
        # 使用 Null Provider 作为默认值
        self.cache = cache or NullCacheProvider()
        self.retry = retry or NullRetryProvider()
        self.monitor = monitor or NullMonitorProvider()
        self.memory = memory or NullMemoryProvider()
    
    def execute(self, task: str) -> str:
        """执行任务"""
        with self.monitor.track_context(f"agent.{self.role}.execute"):
            # 检查缓存
            cache_key = f"agent:{self.role}:{hash(task)}"
            if self.cache.is_available():
                cached = self.cache.get(cache_key)
                if cached:
                    return cached
            
            # 匹配规则
            rules = self.memory.match_rules(task, self.role)
            
            # 执行任务（带重试）
            result = self.retry.retry(self._do_execute, task, rules)
            
            # 缓存结果
            if self.cache.is_available():
                self.cache.set(cache_key, result, ttl=3600)
            
            return result
    
    def _do_execute(self, task: str, rules: list[Rule]) -> str:
        """实际执行逻辑"""
        # 实现略
        pass
```

### 7.2 配置文件驱动

```yaml
# config/providers.yaml
cache:
  type: "redis"  # 或 "memory"、"null"
  config:
    host: "localhost"
    port: 6379

retry:
  type: "exponential"  # 或 "null"
  config:
    max_attempts: 3
    initial_delay: 1.0

monitor:
  type: "prometheus"  # 或 "null"
  config:
    port: 9090

memory:
  type: "carrymem"  # 或 "null"
  config:
    api_url: "http://localhost:8000"
```

---

## 八、测试策略

### 8.1 Protocol 合规性测试

```python
def test_cache_provider_compliance(provider: CacheProvider):
    """测试 CacheProvider 是否符合 Protocol 规范"""
    # 测试 version()
    assert isinstance(provider.version(), str)
    assert len(provider.version().split(".")) == 3
    
    # 测试 is_available()
    assert isinstance(provider.is_available(), bool)
    
    # 测试 get/set
    key = "test:key"
    value = {"data": "test"}
    assert provider.set(key, value, ttl=60)
    assert provider.get(key) == value
    
    # 测试 delete
    assert provider.delete(key)
    assert provider.get(key) is None
    
    # 测试 get_stats()
    stats = provider.get_stats()
    assert "hits" in stats
    assert "misses" in stats
```

### 8.2 降级测试

```python
def test_graceful_degradation():
    """测试降级机制"""
    # 模拟 Cache 不可用
    cache = MockCacheProvider(available=False)
    agent = DevSquadAgent("test", "Architect", cache=cache)
    
    # 应该自动降级，不影响功能
    result = agent.execute("design API")
    assert result is not None
```

---

## 九、附录

### 9.1 参考实现

- **LLMCache**：基于 SQLite 的缓存实现
- **LLMRetry**：基于指数退避的重试实现
- **PerformanceMonitor**：基于内存的监控实现

### 9.2 第三方集成

- **Redis**：高性能缓存
- **Prometheus**：监控和告警
- **CarryMem**：个人化规则引擎

---

**文档生成时间**：2026-05-01
**作者**：Architect
**版本**：v1.0
