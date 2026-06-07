#!/usr/bin/env python3
"""
PerformanceMonitor Protocol 兼容性测试

测试 PerformanceMonitor 是否正确实现 MonitorProvider Protocol。
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def monitor():
    """创建 PerformanceMonitor 实例"""
    from scripts.collaboration.performance_monitor import PerformanceMonitor, reset_monitor

    # 重置全局监控器
    reset_monitor()

    # 创建新实例
    mon = PerformanceMonitor()
    yield mon

    # 清理
    reset_monitor()


def test_monitor_implements_monitor_provider(monitor):
    """测试 PerformanceMonitor 实现 MonitorProvider Protocol"""
    from scripts.collaboration.protocols import MonitorProvider

    # 可以赋值给 MonitorProvider 类型
    mon: MonitorProvider = monitor

    # 验证所有方法都存在
    assert hasattr(mon, "record_llm_call")
    assert hasattr(mon, "record_agent_execution")
    assert hasattr(mon, "generate_report")
    assert hasattr(mon, "is_available")
    assert hasattr(mon, "get_stats")


def test_monitor_record_llm_call(monitor):
    """测试 PerformanceMonitor.record_llm_call()"""
    # 记录 LLM 调用
    monitor.record_llm_call(backend="openai", model="gpt-4", duration=1.5, token_count=1000, success=True)

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_llm_calls"] == 1
    assert stats["avg_llm_duration"] == 1.5


def test_monitor_record_llm_call_with_metadata(monitor):
    """测试 PerformanceMonitor.record_llm_call() 支持 metadata"""
    # 记录失败的 LLM 调用
    monitor.record_llm_call(
        backend="openai", model="gpt-4", duration=2.0, token_count=500, success=False, metadata={"error": "timeout"}
    )

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_llm_calls"] == 1


def test_monitor_record_multiple_llm_calls(monitor):
    """测试 PerformanceMonitor 记录多个 LLM 调用"""
    # 记录多个调用
    monitor.record_llm_call("openai", "gpt-4", 1.0, 1000, True)
    monitor.record_llm_call("openai", "gpt-4", 2.0, 1500, True)
    monitor.record_llm_call("anthropic", "claude", 1.5, 1200, True)

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_llm_calls"] == 3
    assert stats["avg_llm_duration"] == (1.0 + 2.0 + 1.5) / 3


def test_monitor_record_agent_execution(monitor):
    """测试 PerformanceMonitor.record_agent_execution()"""
    # 记录 Agent 执行
    monitor.record_agent_execution(agent_role="Architect", task="Design API", duration=3.0, success=True)

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_agent_executions"] == 1
    assert stats["avg_agent_duration"] == 3.0


def test_monitor_record_agent_execution_with_metadata(monitor):
    """测试 PerformanceMonitor.record_agent_execution() 支持 metadata"""
    # 记录失败的 Agent 执行
    monitor.record_agent_execution(
        agent_role="Developer", task="Implement feature", duration=5.0, success=False, metadata={"error": "bug in code"}
    )

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_agent_executions"] == 1


def test_monitor_record_multiple_agent_executions(monitor):
    """测试 PerformanceMonitor 记录多个 Agent 执行"""
    # 记录多个执行
    monitor.record_agent_execution("Architect", "Design", 3.0, True)
    monitor.record_agent_execution("Developer", "Implement", 5.0, True)
    monitor.record_agent_execution("Tester", "Test", 2.0, True)

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_agent_executions"] == 3
    assert stats["avg_agent_duration"] == (3.0 + 5.0 + 2.0) / 3


def test_monitor_generate_report(monitor):
    """测试 PerformanceMonitor.generate_report()"""
    # 记录一些数据
    monitor.record_llm_call("openai", "gpt-4", 1.5, 1000, True)
    monitor.record_agent_execution("Architect", "Design", 3.0, True)

    # 生成报告
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        output_path = f.name

    try:
        monitor.generate_report(output_path)

        # 验证报告文件存在
        assert Path(output_path).exists()

        # 验证报告内容
        content = Path(output_path).read_text()
        assert "Performance Monitoring Report" in content
        assert "Overall Statistics" in content
    finally:
        Path(output_path).unlink()


def test_monitor_generate_report_io_error():
    """测试 PerformanceMonitor.generate_report() 处理 IO 错误"""
    from scripts.collaboration.performance_monitor import PerformanceMonitor

    monitor = PerformanceMonitor()

    # 尝试写入无效路径
    with pytest.raises(IOError):
        monitor.generate_report("/invalid/path/report.md")


def test_monitor_is_available(monitor):
    """测试 PerformanceMonitor.is_available() 返回 True"""
    assert monitor.is_available() == True


def test_monitor_get_stats_structure(monitor):
    """测试 PerformanceMonitor.get_stats() 返回正确的结构"""
    stats = monitor.get_stats()

    # 验证 Protocol 要求的字段
    assert "total_llm_calls" in stats
    assert "total_agent_executions" in stats
    assert "avg_llm_duration" in stats
    assert "avg_agent_duration" in stats
    assert "total_tokens" in stats

    # 验证类型
    assert isinstance(stats["total_llm_calls"], int)
    assert isinstance(stats["total_agent_executions"], int)
    assert isinstance(stats["avg_llm_duration"], float)
    assert isinstance(stats["avg_agent_duration"], float)
    assert isinstance(stats["total_tokens"], int)


def test_monitor_get_stats_initial_values(monitor):
    """测试 PerformanceMonitor.get_stats() 初始值"""
    stats = monitor.get_stats()

    # 初始状态
    assert stats["total_llm_calls"] == 0
    assert stats["total_agent_executions"] == 0
    assert stats["avg_llm_duration"] == 0.0
    assert stats["avg_agent_duration"] == 0.0
    assert stats["total_tokens"] == 0


def test_monitor_get_stats_with_data(monitor):
    """测试 PerformanceMonitor.get_stats() 返回正确的值"""
    # 记录 LLM 调用
    monitor.record_llm_call("openai", "gpt-4", 1.0, 1000, True)
    monitor.record_llm_call("openai", "gpt-4", 2.0, 1500, True)

    # 记录 Agent 执行
    monitor.record_agent_execution("Architect", "Design", 3.0, True)
    monitor.record_agent_execution("Developer", "Implement", 5.0, True)

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_llm_calls"] == 2
    assert stats["total_agent_executions"] == 2
    assert stats["avg_llm_duration"] == 1.5  # (1.0 + 2.0) / 2
    assert stats["avg_agent_duration"] == 4.0  # (3.0 + 5.0) / 2


def test_monitor_decorator(monitor):
    """测试 PerformanceMonitor.monitor() 装饰器"""

    @monitor.monitor("test_function")
    def test_func():
        return "success"

    # 调用函数
    result = test_func()
    assert result == "success"

    # 验证监控记录
    stats = monitor.get_stats("test_function")
    assert stats["call_count"] == 1
    assert stats["success_count"] == 1


def test_monitor_decorator_with_exception(monitor):
    """测试 PerformanceMonitor.monitor() 装饰器处理异常"""

    @monitor.monitor("failing_function")
    def failing_func():
        raise ValueError("Test error")

    # 调用函数（应该抛出异常）
    with pytest.raises(ValueError):
        failing_func()

    # 验证监控记录
    stats = monitor.get_stats("failing_function")
    assert stats["call_count"] == 1
    assert stats["failure_count"] == 1


def test_monitor_get_slowest_functions(monitor):
    """测试 PerformanceMonitor.get_slowest_functions()"""
    # 记录不同速度的函数
    monitor.record_llm_call("openai", "gpt-4", 1.0, 1000, True)
    monitor.record_llm_call("anthropic", "claude", 3.0, 1500, True)
    monitor.record_agent_execution("Architect", "Design", 2.0, True)

    # 获取最慢的函数
    slowest = monitor.get_slowest_functions(limit=3)

    # 验证排序（最慢的在前）
    assert len(slowest) == 3
    assert slowest[0]["avg_duration_ms"] >= slowest[1]["avg_duration_ms"]
    assert slowest[1]["avg_duration_ms"] >= slowest[2]["avg_duration_ms"]


def test_monitor_get_bottlenecks(monitor):
    """测试 PerformanceMonitor.get_bottlenecks()"""
    # 记录一个慢函数（超过阈值）
    monitor.record_llm_call("openai", "gpt-4", 2.0, 1000, True)  # 2000ms

    # 记录一个快函数（低于阈值）
    monitor.record_agent_execution("Tester", "Test", 0.5, True)  # 500ms

    # 获取瓶颈（阈值 1000ms）
    bottlenecks = monitor.get_bottlenecks(threshold_ms=1000)

    # 验证只返回慢函数
    assert len(bottlenecks) == 1
    assert bottlenecks[0]["avg_duration_ms"] > 1000


def test_monitor_get_recent_errors(monitor):
    """测试 PerformanceMonitor.get_recent_errors()"""
    # 记录成功和失败的调用
    monitor.record_llm_call("openai", "gpt-4", 1.0, 1000, True)
    monitor.record_llm_call("openai", "gpt-4", 2.0, 1000, False, {"error": "timeout"})
    monitor.record_agent_execution("Developer", "Implement", 3.0, False, {"error": "bug"})

    # 获取最近的错误
    errors = monitor.get_recent_errors(limit=10)

    # 验证只返回失败的调用
    assert len(errors) == 2
    for error in errors:
        assert error["success"] == False
        assert error["error"] is not None


def test_monitor_export_report(monitor):
    """测试 PerformanceMonitor.export_report()"""
    # 记录一些数据
    monitor.record_llm_call("openai", "gpt-4", 1.5, 1000, True)
    monitor.record_agent_execution("Architect", "Design", 3.0, True)

    # 导出报告
    report = monitor.export_report()

    # 验证报告内容
    assert "Performance Monitoring Report" in report
    assert "Overall Statistics" in report
    assert "llm_call:openai:gpt-4" in report
    assert "agent:Architect" in report


def test_monitor_concurrent_recording(monitor):
    """测试 PerformanceMonitor 并发记录（线程安全）"""
    import threading

    def worker(i):
        monitor.record_llm_call(f"backend_{i}", "model", 1.0, 1000, True)
        monitor.record_agent_execution(f"agent_{i}", "task", 2.0, True)

    # 创建多个线程
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]

    # 启动所有线程
    for t in threads:
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join()

    # 验证所有记录都成功
    stats = monitor.get_stats()
    assert stats["total_llm_calls"] == 10
    assert stats["total_agent_executions"] == 10


def test_monitor_different_backends(monitor):
    """测试 PerformanceMonitor 区分不同的后端"""
    # 记录不同后端的调用
    monitor.record_llm_call("openai", "gpt-4", 1.0, 1000, True)
    monitor.record_llm_call("anthropic", "claude", 2.0, 1500, True)

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_llm_calls"] == 2

    # 验证可以区分不同的后端
    assert "llm_call:openai:gpt-4" in stats["functions"]
    assert "llm_call:anthropic:claude" in stats["functions"]


def test_monitor_different_agents(monitor):
    """测试 PerformanceMonitor 区分不同的 Agent"""
    # 记录不同 Agent 的执行
    monitor.record_agent_execution("Architect", "Design", 3.0, True)
    monitor.record_agent_execution("Developer", "Implement", 5.0, True)

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_agent_executions"] == 2

    # 验证可以区分不同的 Agent
    assert "agent:Architect" in stats["functions"]
    assert "agent:Developer" in stats["functions"]


def test_monitor_long_task_name(monitor):
    """测试 PerformanceMonitor 处理长任务名"""
    # 记录长任务名
    long_task = "A" * 200  # 200 字符
    monitor.record_agent_execution("Agent", long_task, 1.0, True)

    # 验证统计信息（任务名应该被截断）
    stats = monitor.get_stats()
    assert stats["total_agent_executions"] == 1


def test_monitor_zero_duration(monitor):
    """测试 PerformanceMonitor 处理零时长"""
    # 记录零时长的调用
    monitor.record_llm_call("openai", "gpt-4", 0.0, 1000, True)

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_llm_calls"] == 1
    assert stats["avg_llm_duration"] == 0.0


def test_monitor_large_token_count(monitor):
    """测试 PerformanceMonitor 处理大 token 数"""
    # 记录大 token 数
    monitor.record_llm_call("openai", "gpt-4", 1.0, 1000000, True)

    # 验证统计信息
    stats = monitor.get_stats()
    assert stats["total_llm_calls"] == 1


def test_monitor_get_stats_specific_function(monitor):
    """测试 PerformanceMonitor.get_stats() 获取特定函数统计"""
    # 记录多个函数
    monitor.record_llm_call("openai", "gpt-4", 1.0, 1000, True)
    monitor.record_agent_execution("Architect", "Design", 3.0, True)

    # 获取特定函数的统计
    llm_stats = monitor.get_stats("llm_call:openai:gpt-4")
    assert llm_stats["call_count"] == 1

    agent_stats = monitor.get_stats("agent:Architect")
    assert agent_stats["call_count"] == 1

    # 获取不存在的函数
    empty_stats = monitor.get_stats("non_existent")
    assert empty_stats == {}


def test_monitor_performance_decorator_function():
    """测试 monitor_performance() 装饰器函数"""
    from scripts.collaboration.performance_monitor import get_monitor, monitor_performance, reset_monitor

    # 重置监控器
    reset_monitor()

    @monitor_performance("decorated_function")
    def test_func():
        return "success"

    # 调用函数
    result = test_func()
    assert result == "success"

    # 验证监控记录
    mon = get_monitor()
    stats = mon.get_stats("decorated_function")
    assert stats["call_count"] == 1

    # 清理
    reset_monitor()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
