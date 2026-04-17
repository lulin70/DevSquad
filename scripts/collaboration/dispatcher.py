#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V3 Multi-Agent 协作调度器 (Dispatcher)

这是 v3.0 的统一入口，将所有协作组件串联为一条可用的流水线：

    用户任务 → [意图识别] → [角色分配] → [Coordinator编排]
           → [Worker并行执行] → [Scratchpad共享] → [共识决策]
           → [上下文压缩] → [权限检查] → [记忆沉淀] → [结果返回]

集成组件：
- WarmupManager: 启动预热，减少冷启动延迟
- Coordinator + Worker + Scratchpad: 多Agent协作核心
- BatchScheduler: 并行/串行混合调度
- ConsensusEngine: 共识决策机制
- ContextCompressor: 上下文压缩，防止溢出
- PermissionGuard: 权限守卫，安全操作检查
- Skillifier: 从成功模式中学习，生成新Skill
- MemoryBridge: 跨会话记忆桥接

使用示例:
    from scripts.collaboration.dispatcher import MultiAgentDispatcher

    disp = MultiAgentDispatcher()
    result = disp.dispatch("设计一个用户认证系统")
    print(result.summary)
"""

import os
import sys
import time
import uuid
import json
import re
import tempfile
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from .models import (
    EntryType, EntryStatus, TaskDefinition, ExecutionPlan,
    TaskBatch, BatchMode, ScheduleResult, WorkerResult,
    ConsensusRecord, DecisionOutcome, ROLE_WEIGHTS,
)
from .scratchpad import Scratchpad
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


ROLE_TEMPLATES = {
    "architect": {
        "name": "架构师",
        "prompt": """你是系统架构师。负责：
1. 系统架构设计（分层、模块化、接口定义）
2. 技术选型和评估
3. 性能、安全、可扩展性设计
4. 输出：架构文档、技术方案、模块设计""",
        "keywords": ["架构", "设计", "选型", "性能", "模块", "接口", "部署", "微服务"],
    },
    "product-manager": {
        "name": "产品经理",
        "prompt": """你是产品经理。负责：
1. 需求分析和PRD编写
2. 用户故事和验收标准
3. 竞品分析
4. 输出：需求文档、用户故事、功能规格""",
        "keywords": ["需求", "PRD", "用户故事", "竞品", "验收", "体验", "功能"],
    },
    "tester": {
        "name": "测试专家",
        "prompt": """你是测试专家。负责：
1. 测试策略和用例设计
2. 自动化测试方案
3. 质量评估和缺陷追踪
4. 输出：测试计划、测试用例、质量报告""",
        "keywords": ["测试", "质量", "验收", "自动化", "性能测试", "缺陷", "门禁"],
    },
    "solo-coder": {
        "name": "独立开发者",
        "prompt": """你是全栈开发者。负责：
1. 功能实现和代码编写
2. 单元测试和文档
3. 代码重构和优化
4. Bug修复
5. 输出：源代码、测试、技术文档""",
        "keywords": ["实现", "开发", "代码", "修复", "优化", "重构", "单元测试"],
    },
    "ui-designer": {
        "name": "UI设计师",
        "prompt": """你是UI/UX设计师。负责：
1. 界面设计和交互原型
2. 设计系统和组件规范
3. 视觉稿和设计交付
4. 输出：设计稿、原型、设计规范""",
        "keywords": ["UI", "界面", "前端", "视觉", "交互", "原型", "设计"],
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
        lines = [
            f"# 🤖 Multi-Agent 协作结果",
            "",
            f"**任务**: {self.task_description}",
            f"**状态**: {'✅ 成功' if self.success else '❌ 失败'}",
            f"**耗时**: {self.duration_seconds:.2f}s",
            f"**参与角色**: {', '.join(self.matched_roles)}",
            "",
            "## 📋 执行摘要",
            self.summary or "(无摘要)",
        ]
        if self.worker_results:
            lines.append("")
            lines.append("## 👥 各角色产出")
            for wr in self.worker_results:
                role_name = wr.get('role', 'unknown')
                status_icon = '✅' if wr.get('success') else '❌'
                output_preview = (wr.get('output', '') or '')[:300]
                lines.append(f"- [{status_icon}] **{role_name}**: {output_preview}")
        if self.scratchpad_summary:
            lines.extend(["", "## 📝 Scratchpad 共享区", self.scratchpad_summary])
        if self.consensus_records:
            lines.append("")
            lines.append("## 🗳️ 共识决策")
            for cr in self.consensus_records:
                icon = '✅' if cr.get('outcome') == 'APPROVED' else '⚠️'
                lines.append(f"- [{icon}] {cr.get('topic', '')}: {cr.get('outcome', '')}")
        if self.compression_info:
            ci = self.compression_info
            lines.extend([
                "",
                "## 📦 上下文压缩",
                f"- 级别: {ci.get('level', 'N/A')}",
                f"- 原始: {ci.get('original_tokens', 0)} tokens",
                f"- 压缩后: {ci.get('compressed_tokens', 0)} tokens",
                f"- 节省: {ci.get('reduction_pct', 0)}%",
            ])
        if self.memory_stats:
            ms = self.memory_stats
            lines.extend([
                "",
                "## 🧠 记忆系统",
                f"- 总记忆数: {ms.get('total_memories', 0)}",
                f"- 知识条目: {ms.get('knowledge_count', 0)}",
                f"- 情节记录: {ms.get('episodic_count', 0)}",
            ])
        if self.permission_checks:
            lines.append("")
            lines.append("## 🔒 权限检查")
            for pc in self.permission_checks:
                icon = '✅' if pc.get('allowed') else '🚫'
                lines.append(f"- [{icon}] {pc.get('action', '')}: {pc.get('decision', '')}")
        if self.skill_proposals:
            lines.append("")
            lines.append("## ⚡ Skill 学习")
            for sp in self.skill_proposals:
                lines.append(f"- 📌 {sp.get('title', '新Skill')}: {sp.get('confidence', 0):.0%}")
        if self.quality_report:
            lines.extend(["", "## 🛡️ 测试质量审计"])
            lines.append(self.quality_report)
        if self.errors:
            lines.extend(["", "## ⚠️ 错误信息"])
            for e in self.errors:
                lines.append(f"- {e}")
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
                 mce_adapter=None):
        """
        Args:
            persist_dir: Scratchpad 持久化目录
            enable_warmup: 是否启用启动预热
            enable_compression: 是否启用上下文压缩
            enable_permission: 是否启用权限检查
            enable_memory: 是否启用记忆桥接
            enable_skillify: 是否启用Skill学习
            enable_quality_guard: 是否启用测试质量自动审计 (P1)
            compression_threshold: 压缩触发阈值(token数)
            memory_dir: 记忆存储目录
            permission_level: 默认权限级别
            mce_adapter: MCE 记忆分类引擎适配器 (可选, v3.2)
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
        )

        self.batch_scheduler = BatchScheduler()

        self.consensus_engine = ConsensusEngine()

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
            except Exception:
                pass
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

    def analyze_task(self, task_description: str) -> List[Dict[str, str]]:
        """
        分析任务，匹配合适的角色

        Args:
            task_description: 任务描述

        Returns:
            匹配到的角色列表 [{"role_id": "...", "name": "...", "reason": "..."}]
        """
        task_lower = task_description.lower()
        matched = []

        for role_id, role_info in ROLE_TEMPLATES.items():
            score = 0
            matched_keywords = []
            for kw in role_info["keywords"]:
                if kw in task_lower:
                    score += 1
                    matched_keywords.append(kw)

            if score > 0:
                confidence = min(score / len(role_info["keywords"]), 1.0)
                matched.append({
                    "role_id": role_id,
                    "name": role_info["name"],
                    "confidence": confidence,
                    "matched_keywords": matched_keywords,
                    "reason": f"匹配关键词: {', '.join(matched_keywords)}",
                })

        matched.sort(key=lambda x: x["confidence"], reverse=True)

        if not matched:
            matched.append({
                "role_id": "solo-coder",
                "name": "独立开发者",
                "confidence": 0.5,
                "matched_keywords": [],
                "reason": "默认角色：无明确关键词匹配",
            })

        return matched

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
        start_time = time.time()
        errors = []

        try:
            step1_time = time.time()

            matched_roles = self.analyze_task(task_description)

            if roles:
                role_ids_set = set(roles)
                matched_roles = [r for r in matched_roles if r["role_id"] in role_ids_set]
                for rid in roles:
                    if not any(r["role_id"] == rid for r in matched_roles):
                        template = ROLE_TEMPLATES.get(rid, {"name": rid, "prompt": ""})
                        matched_roles.append({
                            "role_id": rid,
                            "name": template.get("name", rid),
                            "confidence": 1.0,
                            "matched_keywords": [],
                            "reason": "用户指定",
                        })

            role_ids = [r["role_id"] for r in matched_roles]

            if dry_run:
                return DispatchResult(
                    success=True,
                    task_description=task_description,
                    matched_roles=role_ids,
                    summary=f"[DRY RUN] 将调度角色: {', '.join(role_ids)}",
                    duration_seconds=time.time() - start_time,
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
                available_roles.append({
                    "role_id": r["role_id"],
                    "role_prompt": template.get("prompt", ""),
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
                worker_results.append({
                    "worker_id": r.worker_id,
                    "role": r.worker_id.split("-")[0] if "-" in r.worker_id else r.worker_id,
                    "task_id": r.task_id,
                    "success": r.success,
                    "output": str(r.output)[:500] if r.output else None,
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
                except Exception as mem_err:
                    errors.append(f"MemoryBridge error: {mem_err}")

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
                except Exception as mce_err:
                    errors.append(f"MCE classify error: {mce_err}")

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
            )

            self._dispatch_history.append(result)

            if self.enable_quality_guard and self.quality_guard:
                try:
                    qreport = self.audit_quality()
                    result.quality_report = qreport.to_markdown()
                except Exception:
                    pass

            return result

        except Exception as e:
            return DispatchResult(
                success=False,
                task_description=task_description,
                matched_roles=[],
                summary=f"调度异常: {e}",
                errors=[str(e)],
                duration_seconds=time.time() - start_time,
            )

    def _build_summary(self, task: str, roles: List[str],
                       exec_result: ScheduleResult, sp_summary: str) -> str:
        """构建执行摘要"""
        role_names = [ROLE_TEMPLATES.get(r, {}).get("name", r) for r in roles]
        parts = [
            f"任务「{task[:80]}」已完成多Agent协作。",
            f"参与角色: {', '.join(role_names)} ({len(roles)}个)",
        ]
        if exec_result.results:
            done = sum(1 for r in exec_result.results if r.success)
            parts.append(f"执行结果: {done}/{len(exec_result.results)} 个Worker成功")
        if exec_result.duration_seconds:
            parts.append(f"协作耗时: {exec_result.duration_seconds:.2f}s")
        if sp_summary:
            parts.append(f"Scratchpad关键发现: {sp_summary[:200]}")
        return "\n".join(parts)

    def quick_dispatch(self, task: str,
                       output_format: str = "structured",
                       include_action_items: bool = True,
                       include_timing: bool = False) -> str:
        """
        快速调度 - 返回结构化 Markdown 报告

        Args:
            task: 任务描述
            output_format: 输出格式 ("structured"/"compact"/"detailed")
                - structured: 结构化报告 (默认, UI Designer推荐)
                - compact: 紧凑格式 (适合终端)
                - detailed: 详细完整报告
            include_action_items: 是否包含行动项建议
            include_timing: 是否包含各步骤耗时分析

        Returns:
            str: 格式化的 Markdown 报告
        """
        result = self.dispatch(task)

        if output_format == "structured":
            return self._format_structured_report(result, include_action_items, include_timing)
        elif output_format == "compact":
            return self._format_compact_report(result)
        elif output_format == "detailed":
            return result.to_markdown()
        else:
            return result.to_markdown()

    def _format_structured_report(self, result: 'DispatchResult',
                                   include_action_items: bool = True,
                                   include_timing: bool = False) -> str:
        """
        生成结构化报告 (v3.2 UI Designer 规范)

        报告层次: 摘要卡片 → 角色分配 → 关键发现 → 冲突解决 → 行动项

        Args:
            result: DispatchResult 调度结果
            include_action_items: 是否包含行动项
            include_timing: 是否包含耗时分析

        Returns:
            str: 结构化 Markdown 报告
        """
        lines = []
        status_icon = "✅" if result.success else "❌"
        status_text = "协作完成" if result.success else "协作异常"

        lines.append(f"# {status_icon} Multi-Agent 协作报告")
        lines.append("")

        # === 1. 任务摘要卡片 ===
        lines.append("---")
        lines.append(f"## 📋 任务摘要")
        lines.append("")
        lines.append(f"| 项目 | 内容 |")
        lines.append(f"|------|------|")
        lines.append(f"| **任务** | {result.task_description[:100]} |")
        lines.append(f"| **状态** | {status_text} |")
        lines.append(f"| **参与角色** | {len(result.matched_roles)} 个 ({', '.join(result.matched_roles)}) |")
        lines.append(f"| **总耗时** | {result.duration_seconds:.2f}s |")

        if result.worker_results:
            success_count = sum(1 for w in result.worker_results if w.get('success'))
            total_count = len(result.worker_results)
            lines.append(f"| **执行成功率** | {success_count}/{total_count} ({success_count/total_count*100:.0f}%) |")

        if result.errors:
            lines.append(f"| **错误数** | {len(result.errors)} |")
        lines.append("")
        lines.append("---")
        lines.append("")

        # === 2. 角色分配与产出表 ===
        if result.worker_results:
            lines.append("## 👥 角色分配与产出")
            lines.append("")
            lines.append("| 角色 | 状态 | 核心产出 (预览) |")
            lines.append("|------|------|----------------|")

            for wr in result.worker_results:
                role_name = wr.get('role', 'unknown')
                role_display = ROLE_TEMPLATES.get(role_name, {}).get('name', role_name)
                status_icon = '✅' if wr.get('success') else '❌'
                output_preview = (wr.get('output') or '(无输出)')[:80].replace('\n', ' ')
                lines.append(f"| **{role_display}** | {status_icon} | {output_preview} |")

            lines.append("")
            lines.append("---")
            lines.append("")

        # === 3. 关键发现 (从 Scratchpad 提取) ===
        if result.scratchpad_summary:
            lines.append("## 🔍 关键发现")
            lines.append("")
            findings = self._extract_findings(result.scratchpad_summary)
            if findings:
                for i, finding in enumerate(findings[:8], 1):
                    lines.append(f"{i}. {finding}")
            else:
                lines.append(f"> {result.scratchpad_summary[:300]}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # === 4. 冲突解决徽章 ===
        if result.consensus_records:
            lines.append("## 🗳️ 共识决策与冲突解决")
            lines.append("")

            for cr in result.consensus_records:
                topic = cr.get('topic', '未知议题')
                outcome = cr.get('outcome', '')
                decision = cr.get('final_decision', '')

                if outcome == 'APPROVED':
                    badge = "🟢 通过"
                elif outcome == 'REJECTED':
                    badge = "🔴 否决"
                elif outcome == 'SPLIT':
                    badge = "🟡 分歧"
                elif outcome == 'ESCALATED':
                    badge = "🔵 升级"
                else:
                    badge = "⏪ 超时"

                votes_for = cr.get('votes_for', 0)
                votes_against = cr.get('votes_against', 0)
                votes_abstain = cr.get('votes_abstain', 0)

                lines.append(f"- **{topic}** `{badge}`")
                lines.append(f"  - 投票: ✅{votes_for} ❌{votes_against} ⚪{votes_abstain}")
                if decision:
                    lines.append(f"  - 决策: {decision[:100]}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # === 5. 行动项建议 ===
        if include_action_items:
            action_items = self._generate_action_items(result)
            if action_items:
                lines.append("## 📌 行动项建议")
                lines.append("")
                for i, item in enumerate(action_items, 1):
                    priority = item.get('priority', 'M')
                    priority_badge = {'H': '🔴高', 'M': '🟡中', 'L': '🟢低'}.get(priority, '⚪')
                    lines.append(f"{i}. [{priority_badge}] {item['text']}")
                lines.append("")

        # === 6. 扩展信息 (可选) ===
        ext_sections = []

        if result.compression_info:
            ci = result.compression_info
            ext_sections.append(
                f"**上下文压缩**: 级别={ci.get('level','N/A')} | "
                f"{ci.get('original_tokens',0)}→{ci.get('compressed_tokens',0)} tokens | "
                f"节省 {ci.get('reduction_pct',0)}%"
            )

        if result.memory_stats:
            ms = result.memory_stats
            ext_sections.append(
                f"**记忆系统**: 总记忆={ms.get('total_memories',0)} | "
                f"捕获次数={ms.get('total_captures',0)}"
            )

        if result.skill_proposals and len(result.skill_proposals) > 0:
            proposals = [f"{p.get('title','')}({p.get('confidence',0):.0%})" for p in result.skill_proposals[:3]]
            ext_sections.append(f"**技能提案**: {', '.join(proposals)}")

        if result.permission_checks:
            allowed = sum(1 for pc in result.permission_checks if pc.get('allowed'))
            total_pc = len(result.permission_checks)
            ext_sections.append(f"**权限检查**: {allowed}/{total_pc} 通过")

        if ext_sections:
            lines.append("---")
            lines.append("")
            lines.append("> **系统信息**")
            for section in ext_sections:
                lines.append(f"> {section}")
            lines.append("")

        # === 7. 耗时分析 (可选) ===
        if include_timing and result.details.get('timing'):
            timing = result.details['timing']
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>⏱️ 各阶段耗时详情</summary>")
            lines.append("")
            lines.append("| 阶段 | 耗时(s) |")
            lines.append("|------|---------|")
            for stage, duration in timing.items():
                if duration > 0.001:
                    lines.append(f"| {stage} | {duration:.3f} |")
            lines.append("")
            lines.append("</details>")
            lines.append("")

        # 错误汇总
        if result.errors:
            lines.append("")
            lines.append("> ⚠️ **错误/警告**:")
            for err in result.errors[:5]:
                lines.append(f"> - {err[:150]}")

        return "\n".join(lines)

    def _format_compact_report(self, result: 'DispatchResult') -> str:
        """
        生成紧凑格式报告 (适合终端快速查看)

        Args:
            result: DispatchResult 调度结果

        Returns:
            str: 紧凑格式的文本报告
        """
        status = "✅" if result.success else "❌"
        roles_str = ", ".join(result.matched_roles) if result.matched_roles else "无"

        parts = [
            f"[{status}] 任务: {result.task_description[:60]}",
            f"角色: {roles_str} ({len(result.matched_roles)}个)",
            f"耗时: {result.duration_seconds:.2f}s",
        ]

        if result.worker_results:
            done = sum(1 for w in result.worker_results if w.get('success'))
            parts.append(f"Worker: {done}/{len(result.worker_results)} 成功")

        if result.scratchpad_summary:
            parts.append(f"发现: {result.scratchpad_summary[:120]}")

        if result.consensus_records:
            approved = sum(1 for c in result.consensus_records if c.get('outcome') == 'APPROVED')
            parts.append(f"共识: {approved}/{len(result.consensus_records)} 通过")

        if result.errors:
            parts.append(f"错误: {len(result.errors)} 个")

        return "\n".join(parts)

    def _extract_findings(self, scratchpad_summary: str) -> List[str]:
        """
        从 Scratchpad 摘要中提取关键发现条目

        支持的格式:
        - 编号列表: "1. xxx", "2. xxx"
        - 符号列表: "- xxx", "* xxx"
        - 分号分隔: "xxx; yyy; zzz"
        - 句子分割: 按"。", ".", "!" 分割长文本

        Args:
            scratchpad_summary: Scratchpad 共享区摘要文本

        Returns:
            List[str]: 关键发现列表
        """
        if not scratchpad_summary:
            return []

        findings = []
        text = scratchpad_summary.strip()

        # 尝试编号列表
        numbered = re.findall(r'(?:^|\n)\s*(\d+)[\.\、\)]\s*(.+?)(?=\n\s*\d+[\.\、\)]|\Z)', text, re.MULTILINE)
        if numbered and len(numbered) >= 2:
            findings = [item.strip() for _, item in numbered]
            return [f for f in findings if f]

        # 尝试符号列表
        bulleted = re.findall(r'(?:^|\n)\s*[-*•]\s*(.+?)(?=\n\s*[-*•]|\Z)', text, re.MULTILINE)
        if bulleted and len(bulleted) >= 2:
            findings = [item.strip() for item in bulleted]
            return [f for f in findings if f]

        # 尝试分号分隔
        if ';' in text and text.count(';') >= 2:
            findings = [f.strip() for f in text.split(';') if f.strip()]
            return findings[:10]

        # 最后手段: 按句子分割
        sentences = re.split(r'[。！？.!?\n]+', text)
        findings = [s.strip() for s in sentences if len(s.strip()) >= 10]
        return findings[:8]

    def _generate_action_items(self, result: 'DispatchResult') -> List[Dict[str, str]]:
        """
        基于调度结果自动生成行动项建议

        生成规则:
        - 有错误 → 高优先级修复建议
        - 有冲突未解决 → 中优先级人工审核
        - 全部成功 → 低优先级后续优化
        - 有记忆数据 → 建议回顾历史决策

        Args:
            result: DispatchResult 调度结果

        Returns:
            List[Dict]: 行动项列表, 每项包含 priority(H/M/L) 和 text
        """
        items = []

        # 错误处理建议
        if result.errors:
            items.append({
                'priority': 'H',
                'text': f"修复 {len(result.errors)} 个执行错误，首要关注: {result.errors[0][:80]}"
            })

        # 冲突处理建议
        unresolved = [c for c in result.consensus_records
                      if c.get('outcome') in ('SPLIT', 'ESCALATED', 'TIMEOUT')]
        if unresolved:
            items.append({
                'priority': 'H' if len(unresolved) > 2 else 'M',
                'text': f"人工审核 {len(unresolved)} 个未决共识议题: {', '.join([u.get('topic','') for u in unresolved[:3]])}"
            })

        # Worker 失败处理
        failed_workers = [w for w in result.worker_results if not w.get('success')]
        if failed_workers:
            roles_failed = [ROLE_TEMPLATES.get(w.get('role',''), {}).get('name', w.get('role','')) for w in failed_workers]
            items.append({
                'priority': 'M',
                'text': f"排查以下角色执行失败原因: {', '.join(roles_failed[:3])}"
            })

        # 成功后的优化建议
        if result.success and not result.errors:
            if result.memory_stats and result.memory_stats.get('total_memories', 0) > 0:
                items.append({
                    'priority': 'L',
                    'text': f"回顾历史记忆 (共{result.memory_stats['total_memories']}条)，提取可复用经验"
                })

            if result.skill_proposals and len(result.skill_proposals) > 0:
                top_proposal = result.skill_proposals[0]
                items.append({
                    'priority': 'L',
                    'text': f"评估新技能提案「{top_proposal.get('title','')}」(置信度{top_proposal.get('confidence',0):.0%})是否值得固化"
                })

            items.append({
                'priority': 'L',
                'text': "任务已完成，可归档此协作记录供未来参考"
            })

        # 无明确行动项时的默认建议
        if not items:
            items.append({
                'priority': 'M',
                'text': "审查各角色产出内容，确认是否符合预期"
            })

        return items[:6]

    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {
            "version": "3.0",
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
            },
            "dispatch_count": len(self._dispatch_history),
            "scratchpad_stats": self.scratchpad.get_stats() if self.scratchpad else {},
        }

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
                    except Exception:
                        pass

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
        combined.test_functions = [tf for r in reports for r in r.test_functions for tf in r.test_functions]
        if reports:
            scores = [r.score.overall for r in reports]
            combined.score.overall = sum(scores) / len(scores) if scores else 0
        combined.audit_time = sum(r.audit_time for r in reports)
        return combined

    def shutdown(self):
        """优雅关闭所有组件"""
        if self.warmup_manager:
            try:
                self.warmup_manager.shutdown()
            except Exception:
                pass

        if self.memory_bridge:
            try:
                self.memory_bridge.cleanup_expired_memories()
            except Exception:
                pass


def create_dispatcher(**kwargs) -> MultiAgentDispatcher:
    """工厂函数 - 创建并初始化调度器实例"""
    return MultiAgentDispatcher(**kwargs)


def quick_collaborate(task: str, **kwargs) -> DispatchResult:
    """便捷函数 - 单次调用完成协作"""
    disp = create_dispatcher(**kwargs)
    result = disp.dispatch(task)
    disp.shutdown()
    return result
