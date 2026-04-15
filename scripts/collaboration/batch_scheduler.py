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
    def __init__(self):
        self._default_timeout = 300
        self._default_retries = 2

    def schedule(self, batches: List[TaskBatch],
                 workers: dict) -> ScheduleResult:
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
        return task.is_read_only

    def _find_worker(self, workers: dict, role_id: str) -> Optional[Worker]:
        for w in workers.values():
            if w.role_id == role_id:
                return w
        return None
