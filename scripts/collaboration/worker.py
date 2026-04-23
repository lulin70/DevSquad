#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Worker - 工作者执行框架

每个 Worker 是一个独立的 Agent 实例，执行具体任务，
通过 Scratchpad 与其他 Worker 交换信息。
"""

import time
import sys
import os
from typing import List, Optional, Any, Dict

from .models import (
    TaskDefinition,
    WorkerResult,
    TaskNotification,
    ScratchpadEntry,
    EntryType,
    EntryStatus,
)
from .scratchpad import Scratchpad


class Worker:
    """
    工作者 Agent 实例 - 多角色协作的执行单元

    每个 Worker 代表一个特定角色（架构师/测试专家/开发者等），
    独立执行分配的任务，通过 Scratchpad 与其他 Worker 交换信息。

    核心能力:
    - execute(): 执行 TaskDefinition，产出 WorkerResult
    - write_finding/question/conflict(): 向共享黑板写入不同类型的信息
    - send_notification(): 向其他 Worker 发送跨角色消息
    - vote_on_proposal(): 参与共识投票

    生命周期:
        创建 → 接收任务 → 读取相关上下文 → 执行工作 → 写入结果 → 发送通知

    与其他组件的关系:
    - Scratchpad: 共享数据交换媒介（读写）
    - ConsensusEngine: 通过 vote_on_proposal 参与共识
    - Coordinator: 由 Coordinator.spawn_workers() 创建和管理

    使用示例:
        worker = Worker(
            worker_id="arch-abc123",
            role_id="architect",
            role_prompt="你是系统架构师...",
            scratchpad=scratchpad,
        )
        result = worker.execute(task_definition)
    """

    def __init__(self, worker_id: str, role_id: str, role_prompt: str,
                 scratchpad: Scratchpad, llm_backend=None):
        """
        初始化 Worker 实例

        Args:
            worker_id: Worker 唯一标识符（格式建议: "{role_id}-{hex}"）
            role_id: 角色标识（如 "architect", "tester", "solo-coder"）
            role_prompt: 角色的系统提示词/指令模板
            scratchpad: 关联的共享黑板实例
            llm_backend: LLM执行后端（None=MockBackend，返回组装的prompt）
        """
        self.worker_id = worker_id
        self.role_id = role_id
        self.role_prompt = role_prompt
        self.scratchpad = scratchpad
        self.llm_backend = llm_backend
        self._notifications_outbox: List[TaskNotification] = []
        self._entries_written_count = 0
        self._last_assembled_prompt = None

    def execute(self, task: TaskDefinition) -> WorkerResult:
        """
        执行分配的任务

        完整执行流程:
        1. 构建执行上下文（读取 Scratchpad 中相关发现）
        2. 调用 _do_work() 生成工作产出
        3. 将产出作为 FINDING 写入 Scratchpad
        4. 返回包含输出和统计信息的 WorkerResult

        Args:
            task: 任务定义，包含描述、角色ID、阶段ID等

        Returns:
            WorkerResult: 执行结果，包含:
                - success: 是否成功
                - output: 输出内容字典
                - error: 错误信息（失败时）
                - scratchpad_entries_written: 写入条目数
                - notifications_sent: 发送通知数
                - duration_seconds: 执行耗时

        Note:
            即使 _do_work() 返回空字符串，execute 仍会返回 success=True，
            只是 output.finding_summary 为空。仅在抛出异常时才标记为失败。
        """
        start_time = time.time()
        try:
            context = self._build_execution_context(task)

            finding = self._do_work(context)
            if finding:
                entry = ScratchpadEntry(
                    worker_id=self.worker_id,
                    role_id=self.role_id,
                    entry_type=EntryType.FINDING,
                    content=finding,
                    confidence=0.7,
                    tags=[task.task_id, task.stage_id or "", "auto"],
                )
                self.write_finding(entry)

            output = {
                "worker_id": self.worker_id,
                "role_id": self.role_id,
                "task_id": task.task_id,
                "finding_summary": finding[:500] if finding else "",
            }

            return WorkerResult(
                worker_id=self.worker_id,
                task_id=task.task_id,
                success=True,
                output=output,
                scratchpad_entries_written=self._entries_written_count,
                notifications_sent=len(self._notifications_outbox),
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            return WorkerResult(
                worker_id=self.worker_id,
                task_id=task.task_id,
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time,
            )

    def read_scratchpad(self, query: str = "",
                         since=None, limit: int = 20) -> List[ScratchpadEntry]:
        """
        从共享黑板读取相关条目

        Args:
            query: 关键词查询（在 content 和 tags 中模糊匹配）
            since: 起始时间过滤（只返回此时间之后的条目）
            limit: 最大返回条数

        Returns:
            List[ScratchpadEntry]: 匹配的条目列表，按时间倒序
        """
        return self.scratchpad.read(
            query=query, since=since, limit=limit,
        )

    def write_finding(self, finding: ScratchpadEntry) -> str:
        """
        向 Scratchpad 写入一条发现（FINDING 类型）

        会自动设置 worker_id 和 role_id 为当前 Worker 的身份，
        并递增内部写入计数器。

        Args:
            finding: 要写入的发现条目（ScratchpadEntry 实例）

        Returns:
            str: 写入后的 entry_id
        """
        finding.worker_id = self.worker_id
        finding.role_id = self.role_id
        eid = self.scratchpad.write(finding)
        self._entries_written_count += 1
        return eid

    def write_question(self, question: str, to_roles: List[str] = None,
                       tags: List[str] = None) -> str:
        """
        向 Scratchpad 写入问题并可选地通知其他角色

        创建 QUESTION 类型条目写入黑板。如指定了 to_roles，
        会同时生成 TaskNotification 发送给目标角色的 Worker。

        Args:
            question: 问题内容文本
            to_roles: 目标角色ID列表（如 ["architect", "tester"]），为空则不发送通知
            tags: 可选的标签列表

        Returns:
            str: 写入后的 entry_id
        """
        entry = ScratchpadEntry(
            worker_id=self.worker_id,
            role_id=self.role_id,
            entry_type=EntryType.QUESTION,
            content=question,
            confidence=0.5,
            tags=tags or [],
        )
        eid = self.scratchpad.write(entry)
        self._entries_written_count += 1

        if to_roles:
            notification = TaskNotification(
                from_worker=self.worker_id,
                to_workers=to_roles,
                notification_type="question",
                summary=question[:100],
                details=question,
                action_required="请回答此问题",
            )
            self.send_notification(notification)
        return eid

    def write_conflict(self, conflict: str, conflicting_entry_id: str,
                        reason: str = "") -> str:
        """
        向 Scratchpad 写入冲突记录（CONFLICT 类型）

        当检测到与其他 Worker 的产出存在矛盾时调用。
        冲突会触发后续 Coordinator.resolve_conflicts() 共识流程。

        Args:
            conflict: 冲突描述文本
            conflicting_entry_id: 产生冲突的对端条目 ID
            reason: 冲突原因说明

        Returns:
            str: 写入后的 entry_id
        """
        entry = ScratchpadEntry(
            worker_id=self.worker_id,
            role_id=self.role_id,
            entry_type=EntryType.CONFLICT,
            content=f"{conflict}\n\n[冲突原因] {reason}",
            confidence=0.8,
            tags=["conflict", conflicting_entry_id],
        )
        eid = self.scratchpad.write(entry)
        self._entries_written_count += 1
        return eid

    def send_notification(self, notification: TaskNotification):
        """
        发送跨 Worker 通知

        将通知放入内部发件箱（outbox），等待 Coordinator 通过
        get_pending_notifications() 收取并转发给目标 Worker。

        Args:
            notification: 通知对象，包含发送方、接收方列表、摘要等
        """
        self._notifications_outbox.append(notification)

    def get_pending_notifications(self) -> List[TaskNotification]:
        """
        获取并清空待发送的通知队列

        由 Coordinator 在 collect_results() 时调用，
        取出所有累积的通知后清空内部缓冲区。

        Returns:
            List[TaskNotification]: 待处理通知列表（调用后队列为空）
        """
        notifications = list(self._notifications_outbox)
        self._notifications_outbox.clear()
        return notifications

    def get_last_prompt(self) -> Optional[Any]:
        """
        获取最近一次 _do_work() 的提示词组装结果

        由 PromptAssembler 生成，包含复杂度/变体/token估算等元数据。
        可用于 Skillify 闭环：将成功的 prompt 变体反馈回系统。

        Returns:
            Optional[AssembledPrompt]: 最近一次组装结果，未执行过则返回 None
        """
        return self._last_assembled_prompt

    def vote_on_proposal(self, proposal_id: str, decision: bool,
                          reason: str = "", weight: float = None) -> Dict[str, Any]:
        """
        对共识提案进行投票

        创建 Vote 对象并包装为标准返回格式。
        权重默认从 ROLE_WEIGHTS 全局配置中按角色获取。

        Args:
            proposal_id: 共识提案 ID
            decision: 投票决定 (True=赞成, False=反对)
            reason: 投票理由说明
            weight: 投票权重（None 则使用角色默认权重）

        Returns:
            Dict[str, Any]: 包含 proposal_id 和 Vote 对象的字典
                - proposal_id: 提案ID
                - vote: Vote 数据对象
        """
        from .models import Vote, ROLE_WEIGHTS
        w = weight or ROLE_WEIGHTS.get(self.role_id, 1.0)
        vote = Vote(
            voter_id=self.worker_id,
            voter_role=self.role_id,
            decision=decision,
            reason=reason,
            weight=w,
        )
        return {"proposal_id": proposal_id, "vote": vote}

    def _build_execution_context(self, task: TaskDefinition,
                                   compression_level=None) -> Dict[str, Any]:
        """
        构建执行上下文（含提示词组装）

        读取 Scratchpad 中与任务相关的发现，并通过 PromptAssembler
        进行动态提示词裁剪（按任务复杂度和压缩级别）。

        Args:
            task: 任务定义
            compression_level: ContextCompressor 压缩级别（可选，影响 prompt 风格）

        Returns:
            Dict[str, Any]: 执行上下文，包含 task/role_prompt/related_findings/
                             worker_id/compression_level
        """
        related = self.read_scratchpad(
            query=task.description[:50], limit=10,
        )
        return {
            "task": task,
            "role_prompt": self.role_prompt,
            "related_findings": [f.content for f in related[:8]],
            "worker_id": self.worker_id,
            "compression_level": compression_level,
        }

    def _do_work(self, context: Dict[str, Any]) -> str:
        """
        执行核心工作 - 通过 PromptAssembler 动态组装提示词，然后通过 LLMBackend 执行

        组装流程:
        1. 从 context 提取任务描述、相关发现、压缩级别
        2. 通过 PromptAssembler.detect_complexity() 自动判断复杂度
        3. 按复杂度选择模板变体 (compact/standard/enhanced)
        4. 应用压缩级别覆盖（如有）
        5. 输出最终工作指令
        6. 如果配置了 LLMBackend，调用 LLM 执行；否则返回组装的指令

        Args:
            context: 由 _build_execution_context() 构建的执行上下文

        Returns:
            str: LLM 响应文本（有后端时）或组装后的工作指令文本（无后端时）
        """
        from .prompt_assembler import PromptAssembler
        from .llm_backend import MockBackend

        task = context["task"]
        assembler = PromptAssembler(role_id=self.role_id,
                                    base_prompt=context["role_prompt"])

        result = assembler.assemble(
            task_description=task.description,
            related_findings=context.get("related_findings", []),
            task_id=task.task_id,
            compression_level=context.get("compression_level"),
        )

        self._last_assembled_prompt = result

        backend = self.llm_backend or MockBackend()
        if isinstance(backend, MockBackend):
            return result.instruction

        return backend.generate(result.instruction)


class WorkerFactory:
    """
    工厂类 - 批量创建 Worker 实例

    提供 create() 和 create_batch() 两种创建方式，
    封装 Worker 实例化的细节，使调用方无需关心内部构造逻辑。

    使用示例:
        single = WorkerFactory.create("w-1", "architect", prompt, scratchpad)
        batch = WorkerFactory.create_batch([
            {"worker_id": "w-1", "role_id": "architect", ...},
            {"worker_id": "w-2", "role_id": "tester", ...},
        ], scratchpad)
    """

    @staticmethod
    def create(worker_id: str, role_id: str, role_prompt: str,
               scratchpad: Scratchpad, llm_backend=None) -> Worker:
        """
        创建单个 Worker 实例

        Args:
            worker_id: Worker 唯一标识
            role_id: 角色标识
            role_prompt: 角色提示词
            scratchpad: 共享黑板实例

        Returns:
            Worker: 新创建的 Worker 实例
        """
        return Worker(worker_id, role_id, role_prompt, scratchpad, llm_backend)

    @staticmethod
    def create_batch(workers_config: List[Dict[str, str]],
                     scratchpad: Scratchpad, llm_backend=None) -> List[Worker]:
        """
        批量创建 Worker 实例

        遍历配置列表，为每项配置创建一个 Worker。
        worker_id 如未提供则自动生成（格式: "w-{index}"）。

        Args:
            workers_config: Worker 配置列表，每项包含:
                - worker_id (可选): Worker ID
                - role_id (必需): 角色标识
                - role_prompt (可选): 角色提示词
            scratchpad: 所有 Worker 共享的 Scratchpad 实例

        Returns:
            List[Worker]: 创建的 Worker 实例列表
        """
        workers = []
        for cfg in workers_config:
            w = WorkerFactory.create(
                worker_id=cfg.get("worker_id", f"w-{len(workers)}"),
                role_id=cfg["role_id"],
                role_prompt=cfg.get("role_prompt", ""),
                scratchpad=scratchpad,
                llm_backend=llm_backend,
            )
            workers.append(w)
        return workers
