#!/usr/bin/env python3
"""
Worker - Agent Execution Framework

Each Worker is an independent Agent instance that executes tasks
and exchanges information with other Workers via Scratchpad.
"""

import sys
import threading
import time
from typing import Any, Dict, List, Optional

from scripts.collaboration import get_logger

logger = get_logger(__name__)

from .models import (
    EntryType,
    ScratchpadEntry,
    TaskDefinition,
    TaskNotification,
    WorkerResult,
)
from .scratchpad import Scratchpad
from .usage_tracker import track_usage


class Worker:
    """
    Worker Agent Instance - Execution Unit for Multi-Role Collaboration

    Each Worker represents a specific role (architect/tester/developer, etc.),
    independently executes assigned tasks, and exchanges information with
    other Workers via Scratchpad.

    Core Capabilities:
    - execute(): Execute TaskDefinition, produce WorkerResult
    - write_finding/question/conflict(): Write different types of info to shared scratchpad
    - send_notification(): Send cross-role messages to other Workers
    - vote_on_proposal(): Participate in consensus voting

    Lifecycle:
        Create -> Receive Task -> Read Context -> Execute Work -> Write Results -> Send Notifications

    Relationships with Other Components:
    - Scratchpad: Shared data exchange medium (read/write)
    - ConsensusEngine: Participate in consensus via vote_on_proposal
    - Coordinator: Created and managed by Coordinator.spawn_workers()

    Usage Example:
        worker = Worker(
            worker_id="arch-abc123",
            role_id="architect",
            role_prompt="You are a system architect...",
            scratchpad=scratchpad,
        )
        result = worker.execute(task_definition)
    """

    def __init__(
        self,
        worker_id: str,
        role_id: str,
        role_prompt: str,
        scratchpad: Scratchpad,
        llm_backend: Any = None,
        stream: bool = False,
    ) -> None:
        """
        Initialize Worker instance.

        Args:
            worker_id: Unique worker identifier (format: "{role_id}-{hex}")
            role_id: Role identifier (e.g., "architect", "tester", "solo-coder")
            role_prompt: Role system prompt / instruction template
            scratchpad: Associated shared scratchpad instance
            llm_backend: LLM execution backend (None=MockBackend, returns assembled prompt)
        """
        self.worker_id = worker_id
        self.role_id = role_id
        self.role_prompt = role_prompt
        self.scratchpad = scratchpad
        self.llm_backend = llm_backend
        self.stream = stream
        self._notifications_outbox: List[TaskNotification] = []
        self._notifications_lock = threading.Lock()
        self._entries_written_count = 0
        self._last_assembled_prompt: Optional[Any] = None

    def execute(self, task: TaskDefinition) -> WorkerResult:
        """
        Execute assigned task.

        Full execution flow:
        1. Build execution context (read relevant findings from Scratchpad)
        2. Call _do_work() to generate work output
        3. Write output as FINDING to Scratchpad
        4. Return WorkerResult with output and statistics

        Args:
            task: Task definition containing description, role ID, phase ID, etc.

        Returns:
            WorkerResult: Execution result containing:
                - success: Whether successful
                - output: Output content dictionary
                - error: Error message (on failure)
                - scratchpad_entries_written: Number of entries written
                - notifications_sent: Number of notifications sent
                - duration_seconds: Execution duration

        Note:
            Even if _do_work() returns an empty string, execute still returns
            success=True, just with empty output.finding_summary. Only marks
            as failed when an exception is raised.
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
                "finding_summary": finding,
            }

            result = WorkerResult(
                worker_id=self.worker_id,
                task_id=task.task_id,
                success=True,
                output=output,
                scratchpad_entries_written=self._entries_written_count,
                notifications_sent=len(self._notifications_outbox),
                duration_seconds=time.time() - start_time,
            )
            track_usage(
                f"worker.{self.role_id}.execute",
                success=True,
                metadata={"task_id": task.task_id, "duration": round(time.time() - start_time, 2)},
            )
            return result
        except Exception as e:
            logger.error("  [Worker %s] Error: %s", self.worker_id, e)
            track_usage(
                f"worker.{self.role_id}.execute",
                success=False,
                metadata={"task_id": task.task_id, "error": str(e)[:100]},
            )
            return WorkerResult(
                worker_id=self.worker_id,
                task_id=task.task_id,
                success=False,
                output={
                    "worker_id": self.worker_id,
                    "role_id": self.role_id,
                    "task_id": task.task_id,
                    "error_detail": "Execution failed",
                },
                error=str(e),
                duration_seconds=time.time() - start_time,
            )

    def read_scratchpad(self, query: str = "", since: Any = None, limit: int = 20) -> List[ScratchpadEntry]:
        """
        Read relevant entries from shared scratchpad.

        Args:
            query: Keyword query (fuzzy match in content and tags)
            since: Start time filter (only return entries after this time)
            limit: Maximum number of entries to return

        Returns:
            List[ScratchpadEntry]: Matching entries, sorted by time descending
        """
        return self.scratchpad.read(
            query=query,
            since=since,
            limit=limit,
        )

    def write_finding(self, finding: ScratchpadEntry) -> str:
        """
        Write a finding (FINDING type) to Scratchpad.

        Automatically sets worker_id and role_id to current Worker identity,
        and increments internal write counter.

        Args:
            finding: Finding entry to write (ScratchpadEntry instance)

        Returns:
            str: entry_id after writing
        """
        finding.worker_id = self.worker_id
        finding.role_id = self.role_id
        eid = self.scratchpad.write(finding)
        self._entries_written_count += 1
        return eid

    def write_question(self, question: str, to_roles: Optional[List[str]] = None, tags: Optional[List[str]] = None) -> str:
        """
        Write a question to Scratchpad and optionally notify other roles.

        Creates a QUESTION type entry and writes to scratchpad. If to_roles
        is specified, also generates TaskNotification for target role Workers.

        Args:
            question: Question content text
            to_roles: Target role ID list (e.g., ["architect", "tester"]), empty means no notification
            tags: Optional tag list

        Returns:
            str: entry_id after writing
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
                action_required="Please answer this question",
            )
            self.send_notification(notification)
        return eid

    def write_conflict(self, conflict: str, conflicting_entry_id: str, reason: str = "") -> str:
        """
        Write a conflict record (CONFLICT type) to Scratchpad.

        Called when contradiction with another Worker's output is detected.
        Conflicts trigger subsequent Coordinator.resolve_conflicts() consensus flow.

        Args:
            conflict: Conflict description text
            conflicting_entry_id: Conflicting peer entry ID
            reason: Conflict reason explanation

        Returns:
            str: entry_id after writing
        """
        entry = ScratchpadEntry(
            worker_id=self.worker_id,
            role_id=self.role_id,
            entry_type=EntryType.CONFLICT,
            content=f"{conflict}\n\n[Conflict reason] {reason}",
            confidence=0.8,
            tags=["conflict", conflicting_entry_id],
        )
        eid = self.scratchpad.write(entry)
        self._entries_written_count += 1
        return eid

    def send_notification(self, notification: TaskNotification) -> None:
        """
        Send cross-Worker notification.

        Places notification in internal outbox, waiting for Coordinator
        to collect via get_pending_notifications() and forward to target Workers.

        Args:
            notification: Notification object containing sender, recipient list, summary, etc.
        """
        with self._notifications_lock:
            self._notifications_outbox.append(notification)

    def get_pending_notifications(self) -> List[TaskNotification]:
        """
        Get and clear pending notification queue.

        Called by Coordinator during collect_results(),
        retrieves all accumulated notifications and clears internal buffer.

        Returns:
            List[TaskNotification]: Pending notification list (queue is empty after call)
        """
        with self._notifications_lock:
            notifications = list(self._notifications_outbox)
            self._notifications_outbox.clear()
            return notifications

    def get_last_prompt(self) -> Optional[Any]:
        """
        Get the most recent _do_work() prompt assembly result.

        Generated by PromptAssembler, contains metadata such as
        complexity/variant/token estimate. Can be used for Skillify
        feedback loop: feed successful prompt variants back to the system.

        Returns:
            Optional[AssembledPrompt]: Most recent assembly result, None if never executed
        """
        return self._last_assembled_prompt

    def vote_on_proposal(
        self, proposal_id: str, decision: bool, reason: str = "", weight: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Vote on a consensus proposal.

        Creates a Vote object and wraps it in standard return format.
        Weight defaults from ROLE_WEIGHTS global config by role.

        Args:
            proposal_id: Consensus proposal ID
            decision: Vote decision (True=approve, False=reject)
            reason: Vote reason explanation
            weight: Vote weight (None uses role default weight)

        Returns:
            Dict[str, Any]: Dictionary containing proposal_id and Vote object
                - proposal_id: Proposal ID
                - vote: Vote data object
        """
        from .models import ROLE_WEIGHTS, Vote

        w = weight or ROLE_WEIGHTS.get(self.role_id, 1.0)
        vote = Vote(
            voter_id=self.worker_id,
            voter_role=self.role_id,
            decision=decision,
            reason=reason,
            weight=w,
        )
        return {"proposal_id": proposal_id, "vote": vote}

    def _build_execution_context(self, task: TaskDefinition, compression_level: Any = None) -> Dict[str, Any]:
        """
        Build execution context (including prompt assembly).

        Reads relevant findings from Scratchpad and performs dynamic prompt
        trimming via PromptAssembler (based on task complexity and compression level).

        Args:
            task: Task definition
            compression_level: ContextCompressor compression level (optional, affects prompt style)

        Returns:
            Dict[str, Any]: Execution context containing task/role_prompt/related_findings/
                             worker_id/compression_level
        """
        related = self.read_scratchpad(
            query=task.description[:50],
            limit=10,
        )
        return {
            "task": task,
            "role_prompt": self.role_prompt,
            "related_findings": [f.content for f in related[:8]],
            "worker_id": self.worker_id,
            "compression_level": compression_level,
        }

    def _do_work(self, context: dict[str, Any]) -> str:
        """
        Execute core work - dynamically assemble prompt via PromptAssembler, then execute via LLMBackend.

        Assembly flow:
        1. Extract task description, related findings, compression level from context
        2. Auto-detect complexity via PromptAssembler.detect_complexity()
        3. Select template variant by complexity (compact/standard/enhanced)
        4. Apply compression level override (if any)
        5. Output final work instruction
        6. If LLMBackend is configured, call LLM; otherwise return assembled instruction

        Args:
            context: Execution context built by _build_execution_context()

        Returns:
            str: LLM response text (with backend) or assembled work instruction text (without backend)
        """
        from .llm_backend import MockBackend
        from .prompt_assembler import PromptAssembler

        task = context["task"]
        assembler = PromptAssembler(role_id=self.role_id, base_prompt=context["role_prompt"])

        result = assembler.assemble(
            task_description=task.description,
            related_findings=context.get("related_findings", []),
            task_id=task.task_id,
            compression_level=context.get("compression_level"),
        )

        self._last_assembled_prompt = result

        backend = self.llm_backend or MockBackend()
        if isinstance(backend, MockBackend):
            from .models import ROLE_REGISTRY

            rdef = ROLE_REGISTRY.get(self.role_id)
            role_name = rdef.name if rdef else self.role_id
            return backend.generate(
                result.instruction,
                role_name=role_name,
                task_description=task.description,
            )

        from .models import ROLE_REGISTRY as _RR

        _rdef = _RR.get(self.role_id)
        _rname = _rdef.name if _rdef else self.role_id

        try:
            from .llm_cache import get_llm_cache

            cache = get_llm_cache()
            cached = cache.get(result.instruction, "backend", getattr(backend, "model", "unknown"))
            if cached:
                logger.debug("  [%s] Cache hit.", _rname)
                return cached
        except Exception:
            cache = None

        logger.info("  [%s] Calling LLM backend...", _rname)
        try:
            if self.stream and hasattr(backend, "generate_stream"):
                logger.debug("  [%s] Streaming...", _rname)
                chunks = []
                for chunk in backend.generate_stream(result.instruction):
                    sys.stderr.write(chunk)
                    sys.stderr.flush()
                    chunks.append(chunk)
                sys.stderr.write("\n")
                sys.stderr.flush()
                response = "".join(chunks)
            else:
                response = backend.generate(result.instruction)
            logger.debug("  [%s] Response received.", _rname)

            if cache and response:
                try:
                    cache.set(result.instruction, response, "backend", getattr(backend, "model", "unknown"))
                except Exception:
                    logger.debug("Cache set failed for instruction: %s", result.instruction[:80])

            return response
        except Exception as e:
            logger.error("  [%s] LLM call failed: %s", _rname, e)
            raise


class WorkerFactory:
    """
    Factory class - batch creation of Worker instances.

    Provides create() and create_batch() creation methods,
    encapsulating Worker instantiation details so callers
    don't need to know internal construction logic.

    Usage Example:
        single = WorkerFactory.create("w-1", "architect", prompt, scratchpad)
        batch = WorkerFactory.create_batch([
            {"worker_id": "w-1", "role_id": "architect", ...},
            {"worker_id": "w-2", "role_id": "tester", ...},
        ], scratchpad)
    """

    @staticmethod
    def create(
        worker_id: str, role_id: str, role_prompt: str, scratchpad: Scratchpad, llm_backend: Any = None, stream: bool = False
    ) -> Worker:
        """
        Create a single Worker instance.

        Args:
            worker_id: Unique worker identifier
            role_id: Role identifier
            role_prompt: Role prompt
            scratchpad: Shared scratchpad instance
            llm_backend: LLM execution backend
            stream: Whether to enable streaming output

        Returns:
            Worker: Newly created Worker instance
        """
        return Worker(worker_id, role_id, role_prompt, scratchpad, llm_backend, stream=stream)

    @staticmethod
    def create_batch(workers_config: List[Dict[str, str]], scratchpad: Scratchpad, llm_backend: Any = None) -> List[Worker]:
        """
        Batch create Worker instances.

        Iterates through config list, creating a Worker for each entry.
        worker_id is auto-generated if not provided (format: "w-{index}").

        Args:
            workers_config: Worker config list, each entry contains:
                - worker_id (optional): Worker ID
                - role_id (required): Role identifier
                - role_prompt (optional): Role prompt
            scratchpad: Shared Scratchpad instance for all Workers

        Returns:
            List[Worker]: List of created Worker instances
        """
        workers: List[Worker] = []
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
