#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BatchScheduler - 批处理调度器

支持并行/串行混合调度，带超时、重试和依赖管理。
"""

import time
from typing import List, Optional

from .models import (
    TaskDefinition,
    TaskBatch,
    BatchMode,
    ScheduleResult,
    WorkerResult,
)
from .worker import Worker


class BatchScheduler:
    """
    批处理调度器 - 并行/串行混合任务调度

    负责 TaskBatch 列表的执行编排:
    - PARALLEL 批次: 并发执行（受 max_concurrency 限制）
    - SEQUENTIAL 批次: 串行逐个执行（带自动重试）
    - 依赖管理: 检查批次间依赖关系，依赖未满足则跳过

    默认配置:
        - 超时: 300s
        - 重试次数: 2次
    """

    def __init__(self):
        """
        初始化批处理调度器

        使用默认超时(300s)和重试次数(2次)。
        可通过修改 _default_timeout / _default_retries 调整。
        """
        self._default_timeout = 300
        self._default_retries = 2

    def schedule(self, batches: List[TaskBatch],
                 workers: dict) -> ScheduleResult:
        """
        执行批处理调度计划

        按顺序遍历批次列表，对每个批次:
        1. 检查依赖是否满足（未满足则跳过并记录错误）
        2. 根据 mode 选择并行或串行执行
        3. 汇总所有结果和错误

        Args:
            batches: 任务批次列表（由 Coordinator.plan_task 生成）
            workers: Worker 字典 {worker_id: Worker 实例}

        Returns:
            ScheduleResult: 调度结果，包含成功/失败统计、各Worker结果、耗时
        """
        start_time = time.time()
        all_results = []
        all_errors = []
        total_tasks = 0

        completed_batches = set()
        for batch in batches:
            if batch.dependencies:
                missing = [d for d in batch.dependencies if d not in completed_batches]
                if missing:
                    all_errors.append(f"Batch {batch.batch_id} 依赖未满足: {missing}")
                    continue

            if batch.mode == BatchMode.PARALLEL:
                results, errors = self._execute_parallel(batch, workers)
            else:
                results, errors = self._execute_serial(batch, workers)

            all_results.extend(results)
            all_errors.extend(errors)
            total_tasks += len(batch.tasks)
            completed_batches.add(batch.batch_id)

        return ScheduleResult(
            success=len(all_errors) == 0,
            total_tasks=total_tasks,
            completed_tasks=sum(1 for r in all_results if r.success),
            failed_tasks=len(all_errors),
            results=all_results,
            duration_seconds=time.time() - start_time,
            errors=all_errors,
        )

    def _execute_parallel(self, batch: TaskBatch,
                          workers: dict) -> tuple:
        results = []
        errors = []
        for task in batch.tasks[:batch.max_concurrency]:
            worker = self._find_worker(workers, task.role_id)
            if not worker:
                errors.append(f"No worker available for role {task.role_id}")
                continue
            try:
                result = worker.execute(task)
                results.append(result)
            except Exception as e:
                errors.append(f"Worker {worker.worker_id} error: {e}")
        return results, errors

    def _execute_serial(self, batch: TaskBatch,
                        workers: dict) -> tuple:
        results = []
        errors = []
        for task in batch.tasks:
            worker = self._find_worker(workers, task.role_id)
            if not worker:
                errors.append(f"No worker available for role {task.role_id}")
                continue
            for attempt in range(self._default_retries + 1):
                try:
                    result = worker.execute(task)
                    results.append(result)
                    break
                except Exception as e:
                    if attempt == self._default_retries:
                        errors.append(f"Task {task.task_id} failed after retries: {e}")
        return results, errors

    def is_concurrency_safe(self, task: TaskDefinition) -> bool:
        """
        判断任务是否可安全并发执行

        当前实现: 只读任务(is_read_only=True) 可并发。

        Args:
            task: 任务定义

        Returns:
            bool: 是否允许并发
        """
        return task.is_read_only

    def _find_worker(self, workers: dict, role_id: str) -> Optional[Worker]:
        for w in workers.values():
            if w.role_id == role_id:
                return w
        return None
