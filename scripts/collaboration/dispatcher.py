#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V3 Multi-Agent Collaboration Dispatcher (Unified Entry Point)

This is the V3 unified entry point that chains all collaboration components
into a single usable pipeline:

    User Task → [Intent Recognition] → [Role Assignment] → [Coordinator Orchestration]
             → [Parallel Worker Execution] → [Scratchpad Sharing] → [Consensus Decision]
             → [Context Compression] → [Permission Check] → [Memory Capture] → [Result Return]

Integrated Components:
- WarmupManager: Startup warmup to reduce cold-start latency
- Coordinator + Worker + Scratchpad: Multi-agent collaboration core
- BatchScheduler: Parallel/sequential hybrid scheduling
- ConsensusEngine: Weighted voting consensus mechanism with veto power
- ContextCompressor: 4-level context compression to prevent overflow
- PermissionGuard: Permission guard for secure operation checks
- Skillifier: Learns from successful patterns to generate new Skills
- MemoryBridge: Cross-session memory bridge (with MCE + WorkBuddy Claw integration)

Example Usage:
    from scripts.collaboration.dispatcher import MultiAgentDispatcher

    disp = MultiAgentDispatcher()
    result = disp.dispatch("Design a user authentication system")
    print(result.summary)
"""

import os
import sys
import time
import uuid
import json
import re
import logging
import tempfile
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)

from .models import (
    EntryType, EntryStatus, TaskDefinition, ExecutionPlan,
    TaskBatch, BatchMode, ScheduleResult, WorkerResult,
    ConsensusRecord, DecisionOutcome, ROLE_WEIGHTS,
    ROLE_REGISTRY, ROLE_ALIASES, resolve_role_id, get_core_roles, get_planned_roles,
    get_all_role_ids, get_cli_role_list, RoleDefinition,
)
from .scratchpad import Scratchpad, ScratchpadEntry
from .worker import Worker, WorkerFactory
from .consensus import ConsensusEngine
from .coordinator import Coordinator
from .batch_scheduler import BatchScheduler
from .context_compressor import ContextCompressor, Message, MessageType, CompressionLevel
from .permission_guard import (
    PermissionGuard, PermissionLevel, ActionType,
    ProposedAction, PermissionRule,
)
from .skillifier import Skillifier, ExecutionRecord, ExecutionStep, PGActionType
from .warmup_manager import WarmupManager, WarmupConfig, WarmupLayer
from .memory_bridge import (
    MemoryBridge, MemoryConfig as MBConfig,
    MemoryType, MemoryItem, MemoryQuery,
    KnowledgeItem, UserFeedback, EpisodicMemory,
    PersistedPattern, AnalysisCase, ErrorContext,
)
from .test_quality_guard import (
    TestQualityGuard, TestQualityReport,
)
from .usage_tracker import track_usage
from .input_validator import InputValidator
from .user_friendly_error import UserFriendlyError, translate_validation_result, make_user_friendly_error
from .role_matcher import RoleMatcher
from .report_formatter import ReportFormatter
from .concern_pack_loader import ConcernPackLoader


@dataclass
class PerformanceMetric:
    """单次性能指标"""
    timestamp: str
    task_description: str
    total_duration: float
    step_timings: Dict[str, float]
    success: bool
    error_count: int
    role_count: int

    def __post_init__(self):
        if len(self.task_description) > 50:
            self.task_description = self.task_description[:50] + "..."


@dataclass
class PerformanceThresholds:
    """性能阈值配置"""
    total_duration_warning: float = 30.0
    total_duration_critical: float = 60.0
    step_warnings: Dict[str, float] = field(default_factory=lambda: {
        "analyze": 2.0,
        "warmup": 1.0,
        "plan": 3.0,
        "spawn": 1.0,
        "execute": 20.0,
        "collect": 2.0,
        "consensus": 5.0,
        "compress": 1.0,
        "permission": 0.5,
        "memory": 2.0,
        "skillify": 2.0,
    })
    step_criticals: Dict[str, float] = field(default_factory=lambda: {
        "analyze": 5.0,
        "warmup": 3.0,
        "plan": 8.0,
        "spawn": 3.0,
        "execute": 45.0,
        "collect": 5.0,
        "consensus": 10.0,
        "compress": 3.0,
        "permission": 1.0,
        "memory": 5.0,
        "skillify": 5.0,
    })


class PerformanceMonitor:
    """
    性能监控器

    功能：
    - 收集每次调度的性能指标
    - 检测性能异常和回归
    - 维护滑动窗口统计
    - 生成性能报告
    - 触发阈值告警
    """

    def __init__(self, window_size: int = 100, thresholds: Optional[PerformanceThresholds] = None):
        self.window_size = window_size
        self.thresholds = thresholds or PerformanceThresholds()
        self._metrics: deque = deque(maxlen=window_size)
        self._lock = threading.Lock()

    def record(self, metric: PerformanceMetric):
        """记录一次性能指标"""
        with self._lock:
            self._metrics.append(metric)

            # 实时检查阈值
            warnings, criticals = self._check_thresholds(metric)
            if criticals:
                logger.critical("PERFORMANCE CRITICAL: %s", json.dumps(criticals, ensure_ascii=False))
            elif warnings:
                logger.warning("PERFORMANCE WARNING: %s", json.dumps(warnings, ensure_ascii=False))

    def _check_thresholds(self, metric: PerformanceMetric) -> Tuple[List[Dict], List[Dict]]:
        """检查指标是否超过阈值"""
        warnings = []
        criticals = []

        # 总耗时检查
        if metric.total_duration > self.thresholds.total_duration_critical:
            criticals.append({
                "type": "total_duration",
                "value": metric.total_duration,
                "threshold": self.thresholds.total_duration_critical,
                "task": metric.task_description[:50],
            })
        elif metric.total_duration > self.thresholds.total_duration_warning:
            warnings.append({
                "type": "total_duration",
                "value": metric.total_duration,
                "threshold": self.thresholds.total_duration_warning,
            })

        # 各步骤耗时检查
        for step, duration in metric.step_timings.items():
            critical_threshold = self.thresholds.step_criticals.get(step)
            warning_threshold = self.thresholds.step_warnings.get(step)

            if critical_threshold and duration > critical_threshold:
                criticals.append({
                    "type": f"step_{step}",
                    "value": duration,
                    "threshold": critical_threshold,
                })
            elif warning_threshold and duration > warning_threshold:
                warnings.append({
                    "type": f"step_{step}",
                    "value": duration,
                    "threshold": warning_threshold,
                })

        return warnings, criticals

    def get_statistics(self) -> Dict[str, Any]:
        """获取滑动窗口内的统计数据"""
        with self._lock:
            if not self._metrics:
                return {"count": 0}

            metrics_list = list(self._metrics)
            count = len(metrics_list)

            durations = [m.total_duration for m in metrics_list]
            successes = sum(1 for m in metrics_list if m.success)

            stats = {
                "count": count,
                "success_rate": successes / count,
                "duration": {
                    "min": min(durations),
                    "max": max(durations),
                    "avg": sum(durations) / count,
                    "p50": sorted(durations)[int(count * 0.5)],
                    "p95": sorted(durations)[int(count * 0.95)],
                    "p99": sorted(durations)[int(count * 0.99)] if count > 20 else max(durations),
                },
                "errors_per_dispatch_avg": sum(m.error_count for m in metrics_list) / count,
                "roles_per_dispatch_avg": sum(m.role_count for m in metrics_list) / count,
            }

            # 各步骤统计
            step_stats = {}
            all_steps = set()
            for m in metrics_list:
                all_steps.update(m.step_timings.keys())

            for step in all_steps:
                step_durations = [m.step_timings.get(step, 0) for m in metrics_list if step in m.step_timings]
                if step_durations:
                    step_stats[step] = {
                        "avg": sum(step_durations) / len(step_durations),
                        "max": max(step_durations),
                        "min": min(step_durations),
                        "p95": sorted(step_durations)[int(len(step_durations) * 0.95)],
                    }

            stats["steps"] = step_stats

            return stats

    def detect_regression(self, baseline_count: int = 10) -> Optional[Dict[str, Any]]:
        """
        检测性能回归

        对比最近N次与历史平均，检测显著恶化
        """
        with self._lock:
            if len(self._metrics) < baseline_count * 2:
                return None

            metrics_list = list(self._metrics)
            recent = metrics_list[-baseline_count:]
            baseline = metrics_list[:-baseline_count]

            recent_avg = sum(m.total_duration for m in recent) / len(recent)
            baseline_avg = sum(m.total_duration for m in baseline) / len(baseline)

            regression_ratio = (recent_avg - baseline_avg) / baseline_avg if baseline_avg > 0 else 0

            if regression_ratio > 0.2:  # 超过20%视为回归
                return {
                    "detected": True,
                    "regression_ratio": round(regression_ratio, 3),
                    "baseline_avg": round(baseline_avg, 3),
                    "recent_avg": round(recent_avg, 3),
                    "baseline_samples": len(baseline),
                    "recent_samples": len(recent),
                    "severity": "high" if regression_ratio > 0.5 else "medium",
                }

            return None

    def export_metrics(self, output_file: str):
        """导出性能指标到文件"""
        output_path = os.path.abspath(output_file)
        base_dir = os.path.abspath(self.persist_dir)
        if not output_path.startswith(base_dir) and not output_path.startswith("/tmp"):
            logger.warning("Export path outside allowed directories: %s", output_path)
            output_path = os.path.join(base_dir, os.path.basename(output_file))

        with self._lock:
            data = [m.__dict__ for m in self._metrics]

            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info("Exported %d performance metrics to %s", len(data), output_path)

    def clear(self):
        """清除历史数据"""
        with self._lock:
            self._metrics.clear()


# Backward-compatible aliases from models SSOT
ROLE_TEMPLATES = {rid: {"name": rdef.name, "prompt": rdef.prompt, "keywords": rdef.keywords} for rid, rdef in ROLE_REGISTRY.items()}
PLANNED_ROLES = {rid: {"name": rdef.name, "status": rdef.status, "description": rdef.description} for rid, rdef in get_planned_roles().items()}

I18N = {
    "zh": {
        "title": "# 🤖 Multi-Agent 协作结果",
        "task": "**任务**",
        "status_ok": "✅ 成功",
        "status_fail": "❌ 失败",
        "status_label": "状态",
        "duration": "**耗时**",
        "roles": "**参与角色**",
        "summary": "## 📋 执行摘要",
        "output": "## 👥 各角色产出",
        "scratchpad": "## 📝 Scratchpad 共享区",
        "consensus": "## 🗳️ 共识决策",
        "compression": "## 📦 上下文压缩",
        "memory": "## 🧠 记忆系统",
        "permission": "## 🔒 权限检查",
        "skill": "## ⚡ Skill 学习",
        "quality": "## 🛡️ 测试质量审计",
        "errors": "## ⚠️ 错误信息",
        "mock_banner": "> ⚠️ **MOCK 模式** — 这是模拟输出，未调用真实 LLM。",
        "mock_hint": "> 使用 `--backend openai`（或 `anthropic`）并提供有效 API Key 获取真实 AI 分析。",
        "no_output": "*(无输出)*",
        "no_summary": "(无摘要)",
    },
    "en": {
        "title": "# 🤖 Multi-Agent Collaboration Result",
        "task": "**Task**",
        "status_ok": "✅ Success",
        "status_fail": "❌ Failed",
        "status_label": "Status",
        "duration": "**Duration**",
        "roles": "**Roles**",
        "summary": "## 📋 Executive Summary",
        "output": "## 👥 Role Outputs",
        "scratchpad": "## 📝 Scratchpad",
        "consensus": "## 🗳️ Consensus Decisions",
        "compression": "## 📦 Context Compression",
        "memory": "## 🧠 Memory System",
        "permission": "## 🔒 Permission Checks",
        "skill": "## ⚡ Skill Learning",
        "quality": "## 🛡️ Test Quality Audit",
        "errors": "## ⚠️ Errors",
        "mock_banner": "> ⚠️ **MOCK MODE** — This is simulated output. No real LLM was called.",
        "mock_hint": "> Use `--backend openai` (or `anthropic`) with a valid API key for real AI analysis.",
        "no_output": "*(no output)*",
        "no_summary": "(no summary)",
    },
    "ja": {
        "title": "# 🤖 マルチエージェントコラボレーション結果",
        "task": "**タスク**",
        "status_ok": "✅ 成功",
        "status_fail": "❌ 失敗",
        "status_label": "ステータス",
        "duration": "**所要時間**",
        "roles": "**参加ロール**",
        "summary": "## 📋 実行サマリー",
        "output": "## 👥 ロール出力",
        "scratchpad": "## 📝 スクラッチパッド",
        "consensus": "## 🗳️ コンセンサス決定",
        "compression": "## 📦 コンテキスト圧縮",
        "memory": "## 🧠 メモリシステム",
        "permission": "## 🔒 権限チェック",
        "skill": "## ⚡ スキル学習",
        "quality": "## 🛡️ テスト品質監査",
        "errors": "## ⚠️ エラー",
        "mock_banner": "> ⚠️ **モックモード** — これはシミュレーション出力です。実際のLLMは呼び出されていません。",
        "mock_hint": "> 実際のAI分析には `--backend openai`（または `anthropic`）と有効なAPIキーを使用してください。",
        "no_output": "*(出力なし)*",
        "no_summary": "(サマリーなし)",
    },
}


@dataclass
class DispatchResult:
    """调度结果"""
    success: bool
    task_description: str
    matched_roles: List[str] = field(default_factory=list)
    summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    scratchpad_summary: str = ""
    consensus_records: List[Dict[str, Any]] = field(default_factory=list)
    compression_info: Optional[Dict[str, Any]] = None
    memory_stats: Optional[Dict[str, Any]] = None
    permission_checks: List[Dict[str, Any]] = field(default_factory=list)
    skill_proposals: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    worker_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    quality_report: Optional[str] = None
    lang: str = "zh"
    concern_packs: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "task_description": self.task_description,
            "matched_roles": self.matched_roles,
            "summary": self.summary,
            "details": self.details,
            "scratchpad_summary": self.scratchpad_summary,
            "consensus_records": self.consensus_records,
            "compression_info": self.compression_info,
            "memory_stats": self.memory_stats,
            "permission_checks": self.permission_checks,
            "skill_proposals": self.skill_proposals,
            "duration_seconds": round(self.duration_seconds, 2),
            "worker_results": self.worker_results,
            "errors": self.errors,
            "quality_report": self.quality_report,
        }

    def to_markdown(self) -> str:
        t = I18N.get(self.lang, I18N["zh"])
        is_mock = any(
            '[MOCK MODE]' in (wr.get('output', '') or '')
            for wr in (self.worker_results or [])
        )
        lines = []
        if is_mock:
            lines.extend([t["mock_banner"], t["mock_hint"], ""])
        lines.extend([
            t["title"],
            "",
            f"{t['task']}: {self.task_description}",
            f"**{t['status_label']}**: {t['status_ok'] if self.success else t['status_fail']}",
            f"{t['duration']}: {self.duration_seconds:.2f}s",
            f"{t['roles']}: {', '.join(self.matched_roles)}",
            "",
            t["summary"],
            self.summary or t["no_summary"],
        ])
        if self.worker_results:
            lines.append("")
            lines.append(t["output"])
            role_icons = {
                "architect": "🏗️", "product-manager": "📋", "security": "🔒",
                "tester": "🧪", "solo-coder": "💻", "devops": "⚙️", "ui-designer": "🎨",
            }
            for wr in self.worker_results:
                role_id = wr.get('role_id', wr.get('role', 'unknown'))
                role_name = wr.get('role_name', wr.get('role', 'unknown'))
                status_icon = '✅' if wr.get('success') else '❌'
                icon = role_icons.get(role_id, '🤖')
                output = wr.get('output', '') or ''
                lines.append(f"")
                lines.append(f"### {icon} {role_name} [{status_icon}]")
                lines.append(f"---")
                if output:
                    lines.append(output)
                else:
                    lines.append(t["no_output"])
        if self.scratchpad_summary:
            lines.extend(["", t["scratchpad"], self.scratchpad_summary])
        if self.consensus_records:
            lines.append("")
            lines.append(t["consensus"])
            for cr in self.consensus_records:
                icon = '✅' if cr.get('outcome') == 'APPROVED' else '⚠️'
                lines.append(f"- [{icon}] {cr.get('topic', '')}: {cr.get('outcome', '')}")
        if self.compression_info:
            ci = self.compression_info
            lines.extend([
                "",
                t["compression"],
                f"- {t['duration'].replace('**', '')}: {ci.get('level', 'N/A')}",
                f"- {ci.get('original_tokens', 0)} tokens → {ci.get('compressed_tokens', 0)} tokens ({ci.get('reduction_pct', 0)}%)",
            ])
        if self.memory_stats:
            ms = self.memory_stats
            lines.extend([
                "",
                t["memory"],
                f"- Total: {ms.get('total_memories', 0)}",
                f"- Knowledge: {ms.get('knowledge_count', 0)}",
                f"- Episodic: {ms.get('episodic_count', 0)}",
            ])
        if self.permission_checks:
            lines.append("")
            lines.append(t["permission"])
            for pc in self.permission_checks:
                icon = '✅' if pc.get('allowed') else '🚫'
                lines.append(f"- [{icon}] {pc.get('action', '')}: {pc.get('decision', '')}")
        if self.skill_proposals:
            lines.append("")
            lines.append(t["skill"])
            for sp in self.skill_proposals:
                lines.append(f"- 📌 {sp.get('title', 'New Skill')}: {sp.get('confidence', 0):.0%}")
        if self.quality_report:
            lines.extend(["", t["quality"]])
            lines.append(self.quality_report)
        if self.errors:
            lines.extend(["", t["errors"]])
            for e in self.errors:
                lines.append(f"- {e}")
        if self.concern_packs:
            lines.extend(["", "## 🧩 关注点增强包"])
            for cp in self.concern_packs:
                lines.append(f"- **{cp.get('name', '')}**: {cp.get('description', '')}")
        return "\n".join(lines)


class MultiAgentDispatcher:
    """
    V3 统一调度器

    将所有 v3 组件整合为一个易用的高层 API。
    支持单次调用完成完整的多 Agent 协作流程。
    """

    def __init__(self,
                 persist_dir: Optional[str] = None,
                 enable_warmup: bool = True,
                 enable_compression: bool = True,
                 enable_permission: bool = True,
                 enable_memory: bool = True,
                 enable_skillify: bool = True,
                 enable_quality_guard: bool = False,
                 compression_threshold: int = 100000,
                 memory_dir: Optional[str] = None,
                 permission_level: PermissionLevel = PermissionLevel.DEFAULT,
                 mce_adapter=None,
                 llm_backend=None,
                 stream: bool = False,
                 lang: str = "auto"):
        """
        Args:
            persist_dir: Scratchpad persistence directory
            enable_warmup: Whether to enable startup warmup
            enable_compression: Whether to enable context compression
            enable_permission: Whether to enable permission checking
            enable_memory: Whether to enable memory bridge
            enable_skillify: Whether to enable Skill learning
            enable_quality_guard: Whether to enable test quality auto-audit (P1)
            compression_threshold: Compression trigger threshold (token count)
            memory_dir: Memory storage directory
            permission_level: Default permission level
            mce_adapter: MCE memory classification engine adapter (optional, v3.2)
            llm_backend: LLM execution backend (None=MockBackend, returns prompt as-is)
        """
        self.enable_quality_guard = enable_quality_guard
        self.persist_dir = persist_dir or tempfile.mkdtemp(prefix="mas_v3_")
        self.memory_dir = memory_dir or os.path.join(self.persist_dir, "memory")
        self.enable_warmup = enable_warmup
        self.enable_compression = enable_compression
        self.enable_permission = enable_permission
        self.enable_memory = enable_memory
        self.enable_skillify = enable_skillify
        self.compression_threshold = compression_threshold
        self.permission_level = permission_level
        self.llm_backend = llm_backend
        self.stream = stream
        self.lang = lang

        os.makedirs(self.persist_dir, exist_ok=True)
        os.makedirs(self.memory_dir, exist_ok=True)

        self._mce_adapter = mce_adapter
        self._init_components()

    def _init_components(self):
        """初始化所有v3组件"""
        self.scratchpad = Scratchpad(persist_dir=self.persist_dir)

        self.coordinator = Coordinator(
            scratchpad=self.scratchpad,
            persist_dir=self.persist_dir,
            enable_compression=self.enable_compression,
            compression_threshold=self.compression_threshold,
            llm_backend=self.llm_backend,
            stream=self.stream,
        )

        self.batch_scheduler = BatchScheduler()

        self.consensus_engine = ConsensusEngine()

        self.role_matcher = RoleMatcher()
        self.report_formatter = ReportFormatter(lang=self.lang)

        if self.enable_compression:
            self.compressor = ContextCompressor(
                token_threshold=self.compression_threshold
            )
        else:
            self.compressor = None

        if self.enable_permission:
            self.permission_guard = PermissionGuard(
                current_level=self.permission_level,
            )
        else:
            self.permission_guard = None

        if self.enable_warmup:
            warmup_cfg = WarmupConfig(
            cache_enabled=True,
            cache_max_size=50,
            cache_ttl_seconds=3600,
            metrics_enabled=True,
        )
            self.warmup_manager = WarmupManager(config=warmup_cfg)
            try:
                self.warmup_manager.warmup()
            except Exception as e:
                logger.warning("Warmup failed: %s", e)
        else:
            self.warmup_manager = None

        if self.enable_memory:
            self.memory_bridge = MemoryBridge(base_dir=self.memory_dir, mce_adapter=self._mce_adapter)
        else:
            self.memory_bridge = None

        if self.enable_skillify:
            self.skillifier = Skillifier()
        else:
            self.skillifier = None

        if self.enable_quality_guard:
            self.quality_guard = TestQualityGuard("", "")
        else:
            self.quality_guard = None

        self._dispatch_history: List[DispatchResult] = []
        self._max_history = 100
        self._validator = InputValidator()

        # 性能监控初始化
        self._perf_monitor = PerformanceMonitor(window_size=100)

        # 关注点增强包加载器
        self._concern_loader = ConcernPackLoader()

    def analyze_task(self, task_description: str) -> List[Dict[str, str]]:
        """
        分析任务，匹配合适的角色

        Args:
            task_description: 任务描述

        Returns:
            匹配到的角色列表 [{"role_id": "...", "name": "...", "reason": "..."}]
        """
        track_usage("dispatcher.analyze_task")
        return self.role_matcher.analyze_task(task_description)

    def dispatch(self,
                  task_description: str,
                  roles: Optional[List[str]] = None,
                  mode: str = "auto",
                  dry_run: bool = False) -> DispatchResult:
        """
        核心调度方法 - 一键完成多Agent协作

        Args:
            task_description: 任务描述
            roles: 指定角色列表（如 ["architect", "tester"]），None则自动匹配
            mode: 执行模式 ("auto"/"parallel"/"sequential"/"consensus")
            dry_run: 仅模拟执行，不实际运行Worker

        Returns:
            DispatchResult: 完整的调度结果
        """
        track_usage("dispatcher.dispatch", metadata={"mode": mode, "dry_run": dry_run})
        start_time = time.time()
        errors = []

        lang = self.lang
        if lang == "auto":
            import locale
            try:
                try:
                    loc = locale.getlocale()[0] or ""
                except (ValueError, TypeError):
                    loc = ""
                if loc.startswith("ja"):
                    lang = "ja"
                elif loc.startswith("zh"):
                    lang = "zh"
                else:
                    lang = "zh"
            except Exception as e:
                logger.debug("Locale detection failed, using default language: %s", e)
                lang = "zh"

        validator = self._validator
        task_result = validator.validate_task(task_description)
        if not task_result.valid:
            friendly = translate_validation_result(task_result.reason)
            return DispatchResult(
                success=False,
                task_description=task_description,
                matched_roles=[],
                worker_results=[],
                summary=friendly.message,
                errors=[friendly.format()],
                lang=lang,
            )
        task_description = task_result.sanitized_input or task_description

        rule_collection = None
        try:
            from scripts.collaboration.rule_collector import RuleCollector
            if not hasattr(self, '_rule_collector'):
                self._rule_collector = RuleCollector()
            rule_collection = self._rule_collector.process(task_description, lang)
            if rule_collection.rule_detected and not rule_collection.remaining_task:
                return DispatchResult(
                    success=True,
                    task_description=task_description,
                    matched_roles=[],
                    worker_results=[],
                    summary=rule_collection.message,
                    errors=[],
                    lang=lang,
                )
            if rule_collection.rule_detected:
                task_description = rule_collection.remaining_task
        except Exception as e:
            logger.debug("RuleCollector not available: %s", e)

        if roles:
            roles_result = validator.validate_roles(roles)
            if not roles_result.valid:
                friendly = make_user_friendly_error("role_not_found")
                return DispatchResult(
                    success=False,
                    task_description=task_description,
                    matched_roles=[],
                    worker_results=[],
                    summary=friendly.message,
                    errors=[friendly.format()],
                    lang=lang,
                )

        warnings = validator.check_suspicious_patterns(task_description)
        if warnings:
            logger.warning("Suspicious patterns in task: %s", ", ".join(warnings))

        injection_warnings = validator.check_prompt_injection(task_description)
        if injection_warnings:
            logger.warning("Prompt injection patterns detected: %s", ", ".join(injection_warnings))

        try:
            step1_time = time.time()

            matched_roles = self.analyze_task(task_description)

            if roles:
                matched_roles = self.role_matcher.resolve_roles(roles, matched_roles)

            role_ids = [r["role_id"] for r in matched_roles]

            # 匹配关注点增强包
            concern_packs = self._concern_loader.match_packs(task_description)
            concern_enhancements = self._concern_loader.get_all_role_enhancements(concern_packs)

            if concern_packs:
                pack_names = ", ".join(p.name for p in concern_packs)
                logger.info("Concern packs activated: %s", pack_names)

            if dry_run:
                return DispatchResult(
                    success=True,
                    task_description=task_description,
                    matched_roles=role_ids,
                    summary=f"[DRY RUN] 将调度角色: {', '.join(role_ids)}",
                    duration_seconds=time.time() - start_time,
                    lang=lang,
                )

            step2_time = time.time()

            if self.warmup_manager:
                for rid in role_ids:
                    cache_key = f"role-prompt-{rid}"
                    if not self.warmup_manager.is_ready(cache_key):
                        template = ROLE_TEMPLATES.get(rid, {})
                        self.warmup_manager.set_cache(
                            cache_key, template.get("prompt", ""),
                            ttl=1800,
                        )

            step3_time = time.time()

            available_roles = []
            for r in matched_roles:
                template = ROLE_TEMPLATES.get(r["role_id"], {})
                role_prompt = template.get("prompt", "")

                # 注入增强包提示词
                role_id = r["role_id"]
                if role_id in concern_enhancements:
                    enhancement = concern_enhancements[role_id]
                    if enhancement:
                        role_prompt = role_prompt + "\n\n" + enhancement if role_prompt else enhancement

                available_roles.append({
                    "role_id": role_id,
                    "role_prompt": role_prompt,
                    "confidence": r.get("confidence", 0.5),
                })

            plan = self.coordinator.plan_task(
                task_description=task_description,
                available_roles=available_roles,
            )

            step4_time = time.time()

            workers = self.coordinator.spawn_workers(plan)

            step5_time = time.time()

            exec_result = self.coordinator.execute_plan(plan)

            step6_time = time.time()

            worker_results = []
            for r in exec_result.results:
                role_id = r.worker_id.split("-")[0] if "-" in r.worker_id else r.worker_id
                from .models import ROLE_REGISTRY
                rdef = ROLE_REGISTRY.get(role_id)
                role_name = rdef.name if rdef else role_id
                worker_results.append({
                    "worker_id": r.worker_id,
                    "role_id": role_id,
                    "role_name": role_name,
                    "task_id": r.task_id,
                    "success": r.success,
                    "output": (r.output.get("finding_summary", "") if isinstance(r.output, dict) else str(r.output)) if r.output else None,
                    "error": r.error,
                })

            if exec_result.errors:
                errors.extend(exec_result.errors)

            step7_time = time.time()

            collection = self.coordinator.collect_results()
            scratchpad_summary = collection.get("scratchpad", "")

            step8_time = time.time()

            consensus_records = []
            conflicts_count = collection.get("conflicts_count", 0)
            if conflicts_count > 0 or mode == "consensus":
                resolutions = self.coordinator.resolve_conflicts()
                for rec in resolutions:
                    consensus_records.append({
                        "topic": rec.topic,
                        "outcome": rec.outcome.value,
                        "final_decision": rec.final_decision,
                        "votes_for": rec.votes_for,
                        "votes_against": rec.votes_against,
                        "votes_abstain": rec.votes_abstain,
                    })

            step9_time = time.time()

            compression_info = None
            if self.enable_compression and self.compressor:
                stats = self.coordinator.get_compression_stats()
                if stats:
                    compression_info = stats

            step10_time = time.time()

            permission_checks = []
            if self.enable_permission and self.permission_guard:
                test_actions = [
                    ProposedAction(action_type=ActionType.FILE_CREATE,
                                   target="/tmp/test_output.md",
                                   description="生成输出文件"),
                ]
                for action in test_actions:
                    decision = self.permission_guard.check(action)
                    permission_checks.append({
                        "action": f"{action.action_type.value}:{action.target}",
                        "allowed": decision.outcome.value == "ALLOWED",
                        "decision": decision.outcome.value,
                        "reason": decision.reason or "",
                    })

            step11_time = time.time()

            memory_stats = None
            if self.enable_memory and self.memory_bridge:
                try:
                    stats = self.memory_bridge.get_statistics()
                    memory_stats = {
                        "total_memories": stats.total_memories,
                        "by_type_counts": stats.by_type_counts,
                        "index_built": stats.index_built,
                        "total_captures": stats.total_captures,
                    }

                    ep = EpisodicMemory(
                        id=f"epi-{uuid.uuid4().hex[:8]}",
                        task_description=task_description,
                        finding=scratchpad_summary[:500],
                    )
                    self.memory_bridge.capture_execution(
                        execution_record={"task": task_description, "roles": role_ids},
                        scratchpad_entries=[],
                    )
                except (ConnectionError, TimeoutError, OSError) as mem_err:
                    logger.warning("MemoryBridge connection error: %s", mem_err)
                    errors.append(f"MemoryBridge connection error: {type(mem_err).__name__}: {mem_err}")
                except (ValueError, KeyError, AttributeError) as mem_val_err:
                    logger.debug("MemoryBridge data error: %s", mem_val_err)
                    errors.append(f"MemoryBridge data error: {mem_val_err}")
                except Exception as mem_err:
                    logger.warning("Unexpected MemoryBridge error: %s - %s", type(mem_err).__name__, mem_err)
                    errors.append(f"MemoryBridge unexpected error: {type(mem_err).__name__}")

            # [MCE 集成点 v3.2] Dispatcher → MemoryBridge 调用链
            # 已实现: scratchpad → MCE.classify() → typed_metadata → MemoryBridge
            if self._mce_adapter and self._mce_adapter.is_available and scratchpad_summary:
                try:
                    mce_classify_result = self._mce_adapter.classify(
                        scratchpad_summary, context={"task": task_description}, timeout_ms=500
                    )
                    if mce_classify_result:
                        memory_stats = memory_stats or {}
                        memory_stats["mce_classification"] = {
                            "type": mce_classify_result.memory_type,
                            "confidence": round(mce_classify_result.confidence, 3),
                            "tier": mce_classify_result.tier,
                        }
                except (ValueError, TypeError, AttributeError) as mce_type_err:
                    logger.debug("MCE classification data error: %s", mce_type_err)
                    errors.append(f"MCE classify data error: {mce_type_err}")
                except (TimeoutError, ConnectionError) as mce_timeout:
                    logger.warning("MCE classify timeout/connection error: %s", mce_timeout)
                    errors.append(f"MCE classify timeout error: {mce_timeout}")
                except Exception as mce_err:
                    logger.warning("Unexpected MCE classify error: %s - %s", type(mce_err).__name__, mce_err)
                    errors.append(f"MCE classify unexpected error: {type(mce_err).__name__}")

            if self.memory_bridge and self.enable_memory:
                try:
                    ai_news_keywords = [
                        "ai news", "industry trend", "latest progress", "trend",
                        "ai coding", "embodied intelligence", "large model", "llm",
                        "cursor", "claude", "gpt", "deepseek", "anthropic",
                        "\u65b0\u95fb", "\u884c\u4e1a\u52a8\u6001", "\u6700\u65b0\u8fdb\u5c55",
                    ]
                    task_lower = task_description.lower()
                    should_inject = any(kw in task_lower for kw in ai_news_keywords)
                    if should_inject:
                        news_items = self.memory_bridge.get_workbuddy_ai_news(days=3)
                        if news_items:
                            news_summary = "\n".join(
                                f"- [{n.title}] {n.content[:200]}..."
                                for n in news_items[:3]
                            )
                            self.scratchpad.write(
                                ScratchpadEntry(
                                    worker_id="system",
                                    entry_type=EntryType.FINDING,
                                    content=f"[WorkBuddy AI News Feed]\n{news_summary}",
                                    confidence=0.95,
                                    tags=["ai-news", "auto-injected"],
                                )
                            )
                except Exception as inject_err:
                    errors.append(f"AI news inject error: {inject_err}")

            step12_time = time.time()

            skill_proposals = []
            if self.enable_skillify and self.skillifier and exec_result.success:
                try:
                    patterns = self.skillifier.analyze_history()
                    if patterns:
                        for pattern in patterns:
                            if pattern.confidence > 0.3:
                                skill_proposals.append({
                                    "title": pattern.title or "新协作模式",
                                    "confidence": pattern.confidence,
                                    "category": pattern.category.value if hasattr(pattern, 'category') and pattern.category else "general",
                                })
                except Exception as skill_err:
                    errors.append(f"Skillifier error: {skill_err}")

            total_duration = time.time() - start_time

            report = self.coordinator.generate_report()

            result = DispatchResult(
                success=exec_result.success and len(errors) == 0,
                task_description=task_description,
                matched_roles=role_ids,
                summary=self._build_summary(task_description, role_ids, exec_result, scratchpad_summary),
                details={
                    "plan_total_tasks": plan.total_tasks,
                    "completed_tasks": exec_result.completed_tasks,
                    "failed_tasks": exec_result.failed_tasks,
                    "report": report,
                    "timing": {
                        "analyze": round(step2_time - step1_time, 3),
                        "warmup": round(step3_time - step2_time, 3),
                        "plan": round(step4_time - step3_time, 3),
                        "spawn": round(step5_time - step4_time, 3),
                        "execute": round(step6_time - step5_time, 3),
                        "collect": round(step7_time - step6_time, 3),
                        "consensus": round(step8_time - step7_time, 3),
                        "compress": round(step9_time - step8_time, 3),
                        "permission": round(step10_time - step9_time, 3),
                        "memory": round(step11_time - step10_time, 3),
                        "skillify": round(step12_time - step11_time, 3),
                    },
                },
                scratchpad_summary=scratchpad_summary,
                consensus_records=consensus_records,
                compression_info=compression_info,
                memory_stats=memory_stats,
                permission_checks=permission_checks,
                skill_proposals=skill_proposals,
                duration_seconds=total_duration,
                worker_results=worker_results,
                errors=errors,
                lang=lang,
                concern_packs=self._concern_loader.get_pack_info(concern_packs) if concern_packs else [],
            )

            self._dispatch_history.append(result)
            if len(self._dispatch_history) > self._max_history:
                self._dispatch_history = self._dispatch_history[-self._max_history:]

            if self.enable_quality_guard and self.quality_guard:
                try:
                    qreport = self.audit_quality()
                    result.quality_report = qreport.to_markdown()
                except Exception as e:
                    logger.warning("Quality audit failed: %s", e)

            # 记录性能指标
            perf_metric = PerformanceMetric(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                task_description=task_description,
                total_duration=total_duration,
                step_timings=result.details.get("timing", {}),
                success=result.success,
                error_count=len(result.errors),
                role_count=len(role_ids),
            )
            self._perf_monitor.record(perf_metric)

            return result

        except (ValueError, TypeError, AttributeError) as dispatch_err:
            logger.error(
                "Dispatch validation error for task '%s': %s - %s",
                task_description[:50], type(dispatch_err).__name__, dispatch_err,
                exc_info=True
            )
            friendly = make_user_friendly_error("dispatch_failed", original_error=dispatch_err)
            return DispatchResult(
                success=False,
                task_description=task_description,
                matched_roles=[],
                summary=friendly.message,
                errors=[friendly.format()],
                duration_seconds=time.time() - start_time,
                lang=lang,
            )
        except (ImportError, ModuleNotFoundError) as import_err:
            logger.error(
                "Missing dependency during dispatch of task '%s': %s",
                task_description[:50], import_err,
                exc_info=True
            )
            friendly = make_user_friendly_error("backend_unavailable", original_error=import_err)
            return DispatchResult(
                success=False,
                task_description=task_description,
                matched_roles=[],
                summary=friendly.message,
                errors=[friendly.format()],
                duration_seconds=time.time() - start_time,
                lang=lang,
            )
        except Exception as e:
            logger.critical(
                "UNEXPECTED ERROR in dispatch task '%s': %s - %s",
                task_description[:50], type(e).__name__, e,
                exc_info=True
            )
            friendly = make_user_friendly_error("dispatch_failed", original_error=e)
            return DispatchResult(
                success=False,
                task_description=task_description,
                matched_roles=[],
                summary=friendly.message,
                errors=[friendly.format()],
                duration_seconds=time.time() - start_time,
                lang=lang,
            )

    def _build_summary(self, task: str, roles: List[str],
                       exec_result, sp_summary: str) -> str:
        """构建执行摘要"""
        return self.report_formatter.build_summary(task, roles, exec_result, sp_summary)

    def quick_dispatch(self, task: str,
                       output_format: str = "structured",
                       include_action_items: bool = True,
                       include_timing: bool = False) -> 'DispatchResult':
        """
        快速调度 - 返回 DispatchResult，summary 包含格式化报告

        Args:
            task: 任务描述
            output_format: 输出格式 ("structured"/"compact"/"detailed")
                - structured: 结构化报告 (默认, UI Designer推荐)
                - compact: 紧凑格式 (适合终端)
                - detailed: 详细完整报告
            include_action_items: 是否包含行动项建议
            include_timing: 是否包含各步骤耗时分析

        Returns:
            DispatchResult: 调度结果，summary 字段包含格式化报告
        """
        result = self.dispatch(task)

        if output_format == "structured":
            result.summary = self.report_formatter.format_structured_report(result, include_action_items, include_timing)
        elif output_format == "compact":
            result.summary = self.report_formatter.format_compact_report(result)
        else:
            result.summary = result.to_markdown()

        return result

    def _format_structured_report(self, result: 'DispatchResult',
                                   include_action_items: bool = True,
                                   include_timing: bool = False) -> str:
        return self.report_formatter.format_structured_report(result, include_action_items, include_timing)

    def _format_compact_report(self, result: 'DispatchResult') -> str:
        return self.report_formatter.format_compact_report(result)

    def _extract_findings(self, scratchpad_summary: str) -> List[str]:
        return self.report_formatter.extract_findings(scratchpad_summary)

    def _generate_action_items(self, result: 'DispatchResult') -> List[Dict[str, str]]:
        return self.report_formatter.generate_action_items(result)

    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {
            "version": "3.4.0-Prod",
            "persist_dir": self.persist_dir,
            "components": {
                "coordinator": self.coordinator is not None,
                "scratchpad": self.scratchpad is not None,
                "batch_scheduler": self.batch_scheduler is not None,
                "consensus": self.consensus_engine is not None,
                "compressor": self.compressor is not None,
                "permission_guard": self.permission_guard is not None,
                "warmup_manager": self.warmup_manager is not None,
                "memory_bridge": self.memory_bridge is not None,
                "skillifier": self.skillifier is not None,
                "quality_guard": self.quality_guard is not None,
                "performance_monitor": True,
            },
            "dispatch_count": len(self._dispatch_history),
            "scratchpad_stats": self.scratchpad.get_stats() if self.scratchpad else {},
        }

        # 性能监控统计
        try:
            perf_stats = self._perf_monitor.get_statistics()
            status["performance"] = perf_stats

            # 回归检测
            regression = self._perf_monitor.detect_regression()
            if regression:
                status["regression_detected"] = regression
        except Exception as e:
            logger.debug("Performance stats collection failed: %s", e)

        if self.warmup_manager:
            try:
                metrics = self.warmup_manager.get_metrics()
                status["warmup_metrics"] = {
                    "cache_size": metrics.cache_size,
                    "hit_rate": round(metrics.cache_hit_rate, 3) if metrics.cache_hit_rate else 0,
                    "tasks_completed": metrics.tasks_completed,
                    "eager_duration_ms": round(metrics.eager_duration_ms, 2),
                }
            except Exception:
                status["warmup_metrics"] = None

        if self.memory_bridge:
            try:
                mem_stats = self.memory_bridge.get_statistics()
                status["memory_stats"] = {
                    "total_memories": mem_stats.total_memories,
                    "by_type_counts": mem_stats.by_type_counts,
                    "index_built": mem_stats.index_built,
                }
            except Exception:
                status["memory_stats"] = None

        return status

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取调度历史"""
        return [r.to_dict() for r in self._dispatch_history[-limit:]]

    def audit_quality(self, module_path: Optional[str] = None,
                       test_path: Optional[str] = None) -> TestQualityReport:
        """
        执行测试质量审计 (P1 集成)

        Args:
            module_path: 被测模块路径（默认自动检测 collaboration/ 下所有模块）
            test_path: 测试文件路径

        Returns:
            TestQualityReport: 完整质量报告
        """
        if not self.quality_guard:
            self.quality_guard = TestQualityGuard("", "")

        if module_path and test_path:
            return self.quality_guard.__class__(module_path, test_path).audit()

        collab_dir = os.path.dirname(os.path.abspath(__file__))
        reports = []
        for fname in os.listdir(collab_dir):
            if fname.endswith(".py") and not fname.startswith("_") and "test" not in fname:
                mod_name = fname.replace(".py", "")
                test_name = f"{mod_name}_test.py"
                mod_full = os.path.join(collab_dir, fname)
                test_full = os.path.join(collab_dir, test_name)
                if os.path.exists(test_full):
                    try:
                        r = self.quality_guard.__class__(mod_full, test_full).audit()
                        reports.append(r)
                    except Exception as e:
                        logger.warning("Quality guard audit failed for %s: %s", mod_name, e)

        if len(reports) == 1:
            return reports[0]

        combined = TestQualityReport(
            module_name="project",
            test_file=f"{len(reports)} modules",
            source_file=collab_dir,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        combined.total_tests = sum(r.total_tests for r in reports)
        combined.issues = [i for r in reports for i in r.issues]
        combined.test_functions = [tf for r in reports for tf in r.test_functions]
        if reports:
            scores = [r.score.overall for r in reports]
            combined.score.overall = sum(scores) / len(scores) if scores else 0
        combined.audit_time = sum(r.audit_time for r in reports)
        return combined

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return self._perf_monitor.get_statistics()

    def check_performance_regression(self) -> Optional[Dict[str, Any]]:
        """检查是否存在性能回归"""
        return self._perf_monitor.detect_regression()

    def export_performance_metrics(self, output_file: str):
        """导出性能指标到文件"""
        self._perf_monitor.export_metrics(output_file)

    def clear_performance_history(self):
        """清除性能历史数据"""
        self._perf_monitor.clear()
        logger.info("Performance history cleared")

    def shutdown(self):
        """优雅关闭所有组件"""
        if self.warmup_manager:
            try:
                self.warmup_manager.shutdown()
            except Exception as e:
                logger.warning("Warmup shutdown failed: %s", e)

        if self.memory_bridge:
            try:
                self.memory_bridge.cleanup_expired_memories()
            except Exception as e:
                logger.warning("Memory cleanup failed: %s", e)


def create_dispatcher(**kwargs) -> MultiAgentDispatcher:
    """工厂函数 - 创建并初始化调度器实例"""
    return MultiAgentDispatcher(**kwargs)


def quick_collaborate(task: str, **kwargs) -> DispatchResult:
    """便捷函数 - 单次调用完成协作"""
    disp = create_dispatcher(**kwargs)
    result = disp.dispatch(task)
    disp.shutdown()
    return result
