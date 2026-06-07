# DevSquad 优化指南

> ⚠️ **此文档为历史记录** — 部分内容可能已过时。
> 当前状态：27 modules, 7 core roles, 99 unit tests。请以 README.md / SKILL.md 为准。

本指南介绍如何使用 DevSquad 的性能优化模块来提升系统效率和可靠性。

## 目录

- [快速开始](#快速开始)
- [模块介绍](#模块介绍)
- [使用示例](#使用示例)
- [最佳实践](#最佳实践)
- [性能指标](#性能指标)
- [故障排查](#故障排查)

## 快速开始

### 安装依赖

```bash
pip install psutil  # 性能监控需要
```

### 基本使用

```python
from scripts.collaboration.llm_cache import get_llm_cache
from scripts.collaboration.llm_retry import retry_with_fallback
from scripts.collaboration.performance_monitor import monitor_performance

# 1. 启用缓存
cache = get_llm_cache()

# 2. 添加重试和监控装饰器
@monitor_performance("my_llm_call")
@retry_with_fallback(max_retries=3, fallback_backends=["openai", "anthropic"])
def call_llm(prompt: str, backend: str = "openai"):
    # 检查缓存
    cached = cache.get(prompt, backend, "gpt-4")
    if cached:
        return cached
    
    # 调用 API
    response = your_api_call(prompt)
    
    # 保存到缓存
    cache.set(prompt, response, backend, "gpt-4")
    return response
```

## 模块介绍

### 1. LLM 缓存模块 (llm_cache.py)

**功能：**
- 内存 + 磁盘双层缓存
- TTL 过期机制
- LRU 淘汰策略
- 命中率统计

**优势：**
- 减少 60-80% API 调用成本
- 提升 90% 响应速度（缓存命中时）
- 支持离线测试

**配置：**

```python
from scripts.collaboration.llm_cache import LLMCache

cache = LLMCache(
    cache_dir="data/llm_cache",  # 缓存目录
    ttl_seconds=86400,           # 24 小时过期
    max_memory_entries=1000      # 内存最多保存 1000 条
)
```

**API：**

```python
# 获取缓存
response = cache.get(prompt, backend, model)

# 设置缓存
cache.set(prompt, response, backend, model)

# 获取统计
stats = cache.get_stats()
print(f"命中率: {stats['hit_rate_percent']}")

# 清除缓存
cache.clear()  # 清除所有
cache.clear(older_than_hours=24)  # 清除 24 小时前的

# 使缓存失效
cache.invalidate(prompt, backend, model)

# 导出报告
report = cache.export_stats_report()
```

### 2. 重试与故障转移模块 (llm_retry.py)

**功能：**
- 指数退避重试
- 多后端故障转移
- 熔断器保护
- 速率限制检测

**优势：**
- 自动处理临时故障
- 提升系统可用性
- 防止雪崩效应

**使用装饰器：**

```python
from scripts.collaboration.llm_retry import retry_with_fallback

@retry_with_fallback(
    max_retries=3,              # 最多重试 3 次
    initial_delay=1.0,          # 初始延迟 1 秒
    max_delay=60.0,             # 最大延迟 60 秒
    fallback_backends=["openai", "anthropic", "zhipu"]  # 故障转移后端
)
def call_llm(prompt: str, backend: str = "openai"):
    return api_call(prompt, backend)
```

**手动使用：**

```python
from scripts.collaboration.llm_retry import get_retry_manager, RetryConfig

manager = get_retry_manager()
config = RetryConfig(max_retries=3, initial_delay=1.0)

result = manager.retry_with_fallback(
    func=your_function,
    args=(arg1, arg2),
    kwargs={"backend": "openai"},
    config=config,
    fallback_backends=["anthropic", "zhipu"],
    current_backend="openai"
)
```

**获取统计：**

```python
from scripts.collaboration.llm_retry import get_retry_manager

manager = get_retry_manager()
stats = manager.get_stats()

print(f"成功率: {stats['success_rate']}")
print(f"重试次数: {stats['retries']}")
print(f"故障转移次数: {stats['fallbacks']}")
print(f"熔断次数: {stats['circuit_breaks']}")
```

**手动重置熔断器：**

```python
manager.reset_circuit_breaker("openai")
```

### 3. 性能监控模块 (performance_monitor.py)

**功能：**
- 自动追踪执行时间
- 监控 CPU 和内存使用
- 计算 P95/P99 响应时间
- 检测性能瓶颈

**优势：**
- 实时性能可见性
- 快速定位瓶颈
- 数据驱动优化

**使用装饰器：**

```python
from scripts.collaboration.performance_monitor import monitor_performance

@monitor_performance("function_name")
def my_function():
    # Your code
    pass
```

**获取统计：**

```python
from scripts.collaboration.performance_monitor import get_monitor

monitor = get_monitor()

# 获取特定函数统计
stats = monitor.get_stats("function_name")
print(f"平均耗时: {stats['avg_duration_ms']:.1f}ms")
print(f"P95 耗时: {stats['p95_duration_ms']:.1f}ms")
print(f"成功率: {stats['success_rate']}")

# 获取所有函数统计
all_stats = monitor.get_stats()

# 获取最慢的函数
slowest = monitor.get_slowest_functions(limit=10)

# 检测性能瓶颈
bottlenecks = monitor.get_bottlenecks(threshold_ms=1000)

# 获取最近的错误
errors = monitor.get_recent_errors(limit=10)

# 导出报告
report = monitor.export_report()
```

## 使用示例

### 示例 1：基本集成

```python
from scripts.collaboration.llm_cache import get_llm_cache
from scripts.collaboration.llm_retry import retry_with_fallback
from scripts.collaboration.performance_monitor import monitor_performance

@monitor_performance("llm_call")
@retry_with_fallback(max_retries=3, fallback_backends=["openai", "anthropic"])
def call_llm(prompt: str, backend: str = "openai", model: str = "gpt-4"):
    cache = get_llm_cache()
    
    # 尝试缓存
    cached = cache.get(prompt, backend, model)
    if cached:
        return cached
    
    # 调用 API
    response = your_api_call(prompt, backend, model)
    
    # 保存缓存
    cache.set(prompt, response, backend, model)
    return response
```

### 示例 2：批量处理

```python
def process_batch(prompts: list):
    results = []
    
    for prompt in prompts:
        try:
            result = call_llm(prompt)
            results.append(result)
        except Exception as e:
            print(f"Error processing {prompt}: {e}")
            results.append(None)
    
    # 获取统计
    cache = get_llm_cache()
    stats = cache.get_stats()
    print(f"缓存命中率: {stats['hit_rate_percent']}")
    
    return results
```

### 示例 3：定期清理

```python
import schedule
import time

def cleanup_old_cache():
    """清理 7 天前的缓存"""
    cache = get_llm_cache()
    cache.clear(older_than_hours=168)  # 7 * 24 = 168 小时
    print("Old cache cleaned")

# 每天凌晨 2 点清理
schedule.every().day.at("02:00").do(cleanup_old_cache)

while True:
    schedule.run_pending()
    time.sleep(3600)
```

### 示例 4：性能报告

```python
def generate_daily_report():
    """生成每日性能报告"""
    from datetime import datetime
    
    # 缓存报告
    cache = get_llm_cache()
    cache_re cache.export_stats_report()
    
    # 性能报告
    monitor = get_monitor()
    perf_report = monitor.export_report()
    
    # 重试统计
    retry_manager = get_retry_manager()
    retry_stats = retry_manager.get_stats()
    
    # 合并报告
    timestamp = datetime.now().strftime("%Y-%m-%d")
    with open(f"reports/daily_report_{timestamp}.md", "w") as f:
        f.write("# DevSquad Daily Performance Report\n\n")
        f.write(cache_report)
        f.write("\n\n")
        f.write(perf_report)
        f.write("\n\n## Retry Statn\n")
        f.write(f"- Success Rate: {retry_stats['success_rate']}\n")
        f.write(f"- Total Retries: {retry_stats['retries']}\n")
        f.write(f"- Fallbacks: {retry_stats['fallbacks']}\n")
```

## 最佳实践

### 1. 缓存策略

**DO ✓**
- 对相同的 prompt 使用缓存
- 设置合理的 TTL（根据内容更新频率）
- 定期清理过期缓存
- 监控缓存命中率

**DON'T ✗**
- 不要缓存包含敏感信息的响应
- 不要设置过长的 TTL（可能返回过时内容）
- 不要在缓存目录满时继续写入

### 2. 重试策略

**DO ✓**
- 对网络错误、超时、5xx 错误重试
- 使用指数退避避免压垮服务
- 配置多个故障转移后端
- 监控熔断器状态

**DON'T ✗**
- 不要对 4xx 客户端错误重试
- 不要无限重试
- 不要在所有后端都故障时继续重试

### 3. 性能监控

**DO ✓**
- 监控关键路径函数
- 设置性能阈值告警
- 定期分析 P9599 指标
- 追踪性能趋势

**DON'T ✗**
- 不要监控所有函数（开销大）
- 不要忽略性能瓶颈警告
- 不要只看平均值（忽略长尾）

### 4. 资源管理

```python
# 定期清理资源
def cleanup():
    # 清理旧缓存
    cache = get_llm_cache()
    cache.clear(older_than_hours=168)
    
    # 重置熔断器（如果需要）
    retry_manager = get_retry_manager()
    # retry_manager.reset_circuit_breaker("backend_name")
    
    # 导出报告后可以重置监控器（可选）
    # from scripts.collaboration.performance_monitor import reset_monitor
    # reset_monitor()
```

## 性能指标

### 缓存效果

| 指标 | 目标值 | 说明 |
|------|-----|
| 命中率 | > 60% | 缓存命中率 |
| 响应时间（命中） | < 10ms | 缓存命中时的响应时间 |
| 响应时间（未命中） | < 2s | API 调用响应时间 |
| 内存使用 | < 500MB | 缓存占用内存 |

### 重试效果

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 成功率 | > 99% | 最终成功率（含重试） |
| 平均重试次数 | < 0.5 | 每次调用的平均重试次数 |
| 故障转移率 | < 5% | 需要故障转移的比例 |
| 熔断触发率 | < 1% | 熔断器打开的比例 |

### 性能基准

| 操作 | P50 | P95 | P99 |
|------|-----|-----|-----|
| 缓存命中 | < 5ms | < 10ms | < 20ms |
| API 调用 | < 1s | < 2s | < 5s |
| 重试调用 | < 3s | < 10s | < 30s |

## 故障排查

### 问题 1：缓存命中率低

**可能原因：**
- Prompt 变化太大（即使语义相同）
- TTL 设置过短
- 缓存被频繁清理

**解决方案：**
```python
# 1. 标准化 prompt
def normalize_prompt(prompt: str) -> str:
    return prompt.strip().lower()

# 2. 增加 TTL
cache = LLMCache(ttl_seconds=86400 * 7)  # 7 天

# 3. 检查缓存统计
stats = cache.get_stats()
print(f"Expirations: {stats['expirations']}")
```

### 问题 2：重试次数过多

**可能原因：**
- 后端服务不稳定
- 网络问题
- 速率限制

**解决方案：**
```python
# 1. 检查重试统计
manager = get_retry_manager()
stats = manager.get_stats()
print(f"Retries: {stats['retries']}")
print(f"Circuit breakers: {stats['circuit_breakers']}")

# 2. 增加延迟
@ret_fallback(
    max_retries=3,
    initial_delay=2.0,  # 增加初始延迟
    max_delay=120.0     # 增加最大延迟
)

# 3. 添加更多故障转移后端
@retry_with_fallback(
    fallback_backends=["openai", "anthropic", "zhipu", "cohere"]
)
```

### 问题 3：性能瓶颈

**可能原因：**
- 某些函数执行时间过长
- 资源竞争
- 外部依赖慢

**解决方案：**
```python
# 1. 识别瓶颈
monitor = get_monitor()
bottlenecks = monitor.get_bottlenecks(threshold_ms=1000)
for b in bottlenecks:
    print(f"{b['name']}: {b['avg_duration_ms']:.1f}ms ({b['severity']})")

# 2. 分析慢函数
slowest = monitor.get_slowest_functions(limit=5)

# 3. 优化或异步化慢函数
import asyncio

async def async_call_llm(prompt: str):
    # 异步实现
    pass
```

### 问题 4：内存使用过高

**可能原因：**
- 缓存条目过多
- 监控历史记录过多
- 内存泄漏

**解决方案：**
```python
# 1. 限制缓存大小
cache = LLMCache(max_memory_entries=500)

# 2. 限制监控历史
monitor = PerformanceMonitor(max_history=500)

# 3. 定期清理
cache.clear(older_than_hours=24)
```

## 进阶配置

### 自定义缓存键

```python
import hashlib

def custom_cache_key(prompt: str, **kwargs) -> str:
    """自定义缓存键生成"""
    # 只考虑 prompt 的语义，忽略格式差异
    normalized = prompt.strip().lower()
    key = f"{normalized}:{kwargs.get('model', 'default')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

### 条件重试

```python
def should_retry(error: Exception) -> bool:
    """自定义重试条件"""
    error_msg = str(error).lower()
    # 只对特定错误重试
    return any(pattern in error_msg for pattern in [
        "timeout", "connection", "503", "502"
    ])
```

### 自定义监控指标

```python
from scripts.collaboration.performance_monitor import get_monitor

monitor = get_monitor()

# 添加自定义指标
def track_custom_metric(name: str, value: float):
    # 实现自定义指标追踪
    pass
```

## 总结

通过合理使用这三个优化模块，您可以：

1. **降低成本**：缓存减少 60-80% API 调用
2. **提升性能**：缓存命中提升 90% 响应速度
3. **增强可靠性**：和故障转移
4. **提高可见性**：实时性能监控和报告

建议从基本集成开始，逐步根据实际情况调整配置和策略。
