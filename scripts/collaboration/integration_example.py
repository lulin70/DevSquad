#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration Example: LLM Cache + Retry + Performance Monitoring

Demonstrates how to use all three optimization modules together
for robust, efficient, and monitored LLM API calls.

Usage:
    python scripts/collaboration/integration_example.py
"""

import time
import random
from typing import Optional

# Import optimization modules
from llm_cache import get_llm_cache
from llm_retry import retry_with_fallback, get_retry_manager
from performance_monitor import monitor_performance, get_monitor


# Simulated LLM API call (replace with real API)
def _mock_llm_api(prompt: str, backend: str, model: str) -> str:
    """模拟 LLM API 调用"""
    # Simulate network delay
    time.sleep(random.uniform(0.1, 0.3))
    
    # Simulate occasional failures (10% chance)
    if random.random() < 0.1:
        raise Exception(f"API Error: {backend} temporarily unavailable")
    
    return f"[{backend}:{model}] Response to: {prompt[:50]}..."


@monitor_performance("optimized_llm_call")
@retry_with_fallback(
    max_retries=3,
    initial_delay=1.0,
    fallback_backends=["openai", "anthropic", "zhipu"]
)
def optimized_llm_call(
    prompt: str,
    backend: str = "openai",
    model: str = "gpt-4"
) -> str:
    """
    优化的 LLM 调用函数
    
    集成了：
    1. 缓存机制 - 避免重复调用
    2. 重试机制 - 处理临时故障
    3. 性能监控 - 追踪性能指标
    
    Args:
        prompt: 提示词
        backend: 后端服务
        model: 模型名称
    
    Returns:
        LLM 响应
    """
    cache = get_llm_cache()
    
    # 1. 尝试从缓存获取
    cached_response = cache.get(prompt, backend, model)
    if cached_response:
        print(f"✓ Cache hit for: {prompt[:30]}...")
        return cached_response
    
    print(f"✗ Cache miss, calling API: {backend}:{model}")
    
    # 2. 调用 API（带重试和故障转移）
    response = _mock_llm_api(prompt, backend, model)
    
    # 3. 保存到缓存
    cache.set(prompt, response, backend, model)
    
    return response


def demo_basic_usage():
    """演示基本用法"""
    print("\n" + "="*60)
    print("Demo 1: Basic Usage")
    print("="*60)
    
    prompts = [
        "What is Python?",
        "Explain machine learning",
        "What is Python?",  # 重复，应该命中缓存
        "How does AI work?",
    ]
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\n[{i}/{len(prompts)}] Calling: {prompt}")
        try:
            response = optimized_llm_call(prompt)
            print(f"Response: {response[:80]}...")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(0.5)


def demo_cache_performance():
    """演示缓存性能提升"""
    print("\n" + "="*60)
    print("Demo 2: Cache Performance")
    print("="*60)
    
    prompt = "Explain quantum computing"
    
    # 第一次调用（无缓存）
    print("\nFirst call (no cache):")
    start = time.time()
    response1 = optimized_llm_call(prompt)
    duration1 = time.time() - start
    print(f"Duration: {duration1*1000:.0f}ms")
    
    # 第二次调用（有缓存）
    print("\nSecond call (with cache):")
    start = time.time()
    response2 = optimized_llm_call(prompt)
    duration2 = time.time() - start
    print(f"Duration: {duration2*1000:.0f}ms")
    
    # 性能提升
    speedup = duration1 / duration2 if duration2 > 0 else 0
    print(f"\n✓ Speed improvement: {speedup:.1f}x faster")
    print(f"✓ Time saved: {(duration1 - duration2)*1000:.0f}ms")


def demo_retry_fallback():
    """演示重试和故障转移"""
    print("\n" + "="*60)
    print("Demo 3: Retry and Fallback")
    print("="*60)
    
    # 模拟主后端故障
    print("\nSimulating backend failures...")
    
    for i in range(3):
        try:
            prompt = f"Test prompt {i+1}"
            response = optimized_llm_call(prompt, backend="openai")
            print(f"✓ Call {i+1} succeeded")
        except Exception as e:
            print(f"✗ Call {i+1} failed: {e}")
        time.sleep(0.5)


def demo_performance_monitoring():
    """演示性能监控"""
    print("\n" + "="*60)
    print("Demo 4: Performance Monitoring")
    print("="*60)
    
    # 执行多次调用
    print("\nExecuting multiple calls...")
    prompts = [
        "What is AI?",
        "Explain neural networks",
        "What is deep learning?",
        "What is AI?",  # 重复
        "How does NLP work?",
    ]
    
    for prompt in prompts:
        try:
            optimized_llm_call(prompt)
        except:
            pass
        time.sleep(0.3)
    
    # 获取性能统计
    monitor = get_monitor()
    stats = monitor.get_stats("optimized_llm_call")
    
    print("\n📊 Performance Statistics:")
    print(f"  Total calls: {stats['call_count']}")
    print(f"  Success rate: {stats['success_rate']}")
    print(f"  Avg duration: {stats['avg_duration_ms']:.1f}ms")
    print(f"  Min duration: {stats['min_duration_ms']:.1f}ms")
    print(f"  Max duration: {stats['max_duration_ms']:.1f}ms")
    print(f"  P95 duration: {stats['p95_duration_ms']:.1f}ms")
    print(f"  P99 duration: {stats['p99_duration_ms']:.1f}ms")


def demo_comprehensive_stats():
    """演示综合统计信息"""
    print("\n" + "="*60)
    print("Demo 5: Comprehensive Statistics")
    print("="*60)
    
    # 缓存统计
    cache = get_llm_cache()
    cache_stats = cache.get_stats()
    
    print("\n📦 Cache Statistics:")
    print(f"  Hit rate: {cache_stats['hit_rate_percent']}")
    print(f"  Total requests: {cache_stats['total_requests']}")
    print(f"  Hits: {cache_stats['hits']}")
    print(f"  Misses: {cache_stats['misses']}")
    print(f"  Memory entries: {cache_stats['memory_entries']}")
    print(f"  Disk entries: {cache_stats['disk_entries']}")
    
    # 重试统计
    retry_manager = get_retry_manager()
    retry_stats = retry_manager.get_stats()
    
    print("\n🔄 Retry Statistics:")
    print(f"  Success rate: {retry_stats['success_rate']}")
    print(f"  Total calls: {retry_stats['total_calls']}")
    print(f"  Successful: {retry_stats['successful_calls']}")
    print(f"  Failed: {retry_stats['failed_calls']}")
    print(f"  Retries: {retry_stats['retries']}")
    print(f"  Fallbacks: {retry_stats['fallbacks']}")
    print(f"  Circuit breaks: {retry_stats['circuit_breaks']}")
    
    # 性能监控统计
    monitor = get_monitor()
    perf_stats = monitor.get_stats()
    
    print("\n⚡ Performance Statistics:")
    print(f"  Uptime: {perf_stats['uptime_seconds']:.0f}s")
    print(f"  Total metrics: {perf_stats['total_metrics']}")
    print(f"  Monitored functions: {len(perf_stats['functions'])}")


def demo_export_reports():
    """演示导出报告"""
    print("\n" + "="*60)
    print("Demo 6: Export Reports")
    print("="*60)
    
    # 导出缓存报告
    cache = get_llm_cache()
    cache_report = cache.export_stats_report()
    
    cache_file = "data/cache_report.md"
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(cache_report)
    print(f"\n✓ Cache report exported to: {cache_file}")
    
    # 导出性能报告
    monitor = get_monitor()
    perf_report = monitor.export_report()
    
    perf_file = "data/performance_report.md"
    with open(perf_file, "w", encoding="utf-8") as f:
        f.write(perf_report)
    print(f"✓ Performance report exported to: {perf_file}")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("LLM Optimization Integration Demo")
    print("="*60)
    print("\nThis demo showcases:")
    print("  1. LLM Response Caching")
    print("  2. Retry with Fallback")
    print("  3. Performance Monitoring")
    
    try:
        # 运行所有演示
        demo_basic_usage()
        demo_cache_performance()
        demo_retry_fallback()
        demo_performance_monitoring()
        demo_comprehensive_stats()
        demo_export_reports()
        
        print("\n" + "="*60)
        print("✓ All demos completed successfully!")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\n✗ Demo interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
