#!/usr/bin/env python3
"""
DevSquad API Routes - Task Dispatch

REST API endpoints for multi-agent task dispatch.

Endpoints:
  POST   /api/v1/tasks/dispatch    - Full task dispatch interface
  POST   /api/v1/tasks/quick       - Quick dispatch interface
  GET    /api/v1/tasks/history     - Get dispatch history
  GET    /api/v1/roles             - List available roles
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException, Query

from scripts.api.models import (
    AnchorResult,
    DispatchHistoryResponse,
    DispatchResponse,
    FiveAxisResult,
    IntentMatchInfo,
    QuickDispatchRequest,
    RoleInfo,
    RolesListResponse,
    TaskDispatchRequest,
    WorkerResultItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Task Dispatch"])

_global_dispatcher = None


def _get_dispatcher():
    """Get or create the global MultiAgentDispatcher instance."""
    global _global_dispatcher
    if _global_dispatcher is None:
        try:
            from scripts.collaboration.dispatcher import MultiAgentDispatcher

            _global_dispatcher = MultiAgentDispatcher(
                enable_warmup=True,
                enable_compression=True,
                enable_permission=True,
                enable_memory=True,
                enable_skillify=True,
                enable_quality_guard=False,
            )
            logger.info("MultiAgentDispatcher initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MultiAgentDispatcher: {e}")
            raise HTTPException(status_code=503, detail=f"Dispatcher initialization failed: {str(e)}")
    return _global_dispatcher


def _convert_dispatch_result(result) -> dict[str, Any]:
    """Convert DispatchResult to API response dict."""
    worker_results = []
    for wr in result.worker_results or []:
        worker_results.append(
            WorkerResultItem(
                worker_id=wr.get("worker_id"),
                role_id=wr.get("role_id", "unknown"),
                role_name=wr.get("role_name", "Unknown"),
                task_id=wr.get("task_id"),
                success=wr.get("success", False),
                output=wr.get("output"),
                error=wr.get("error"),
            ).model_dump()
        )

    intent_match = None
    if result.intent_match:
        intent_match = IntentMatchInfo(
            intent_type=result.intent_match.get("intent_type"),
            workflow_chain=result.intent_match.get("workflow_chain"),
            confidence=result.intent_match.get("confidence"),
        ).model_dump()

    five_axis_result = None
    if result.five_axis_result:
        five_axis_result = FiveAxisResult(
            verdict=result.five_axis_result.get("verdict"),
            overall_consensus=result.five_axis_result.get("overall_consensus"),
            axis_consensus=result.five_axis_result.get("axis_consensus"),
            action_items=result.five_axis_result.get("action_items"),
        ).model_dump()

    anchor_result = None
    if result.anchor_result:
        anchor_result = AnchorResult(
            aligned=result.anchor_result.get("aligned"),
            coverage=result.anchor_result.get("coverage"),
            drift_score=result.anchor_result.get("drift_score"),
            severity=result.anchor_result.get("severity"),
            recommendation=result.anchor_result.get("recommendation"),
        ).model_dump()

    return {
        "success": result.success,
        "task_description": result.task_description,
        "matched_roles": result.matched_roles or [],
        "summary": result.summary or "",
        "duration_seconds": round(result.duration_seconds, 2),
        "worker_results": worker_results,
        "errors": result.errors or [],
        "intent_match": intent_match,
        "five_axis_result": five_axis_result,
        "anchor_result": anchor_result,
        "scratchpad_summary": result.scratchpad_summary,
        "consensus_records": result.consensus_records,
        "compression_info": result.compression_info,
        "memory_stats": result.memory_stats,
        "permission_checks": result.permission_checks,
        "skill_proposals": result.skill_proposals,
        "quality_report": result.quality_report,
        "retrospective_report": result.retrospective_report,
        "details": result.details,
        "timestamp": datetime.now().isoformat(),
    }


@router.post(
    "/api/v1/tasks/dispatch",
    response_model=DispatchResponse,
    summary="Full Task Dispatch / 完整任务调度",
    description="""
    Execute a complete multi-agent task dispatch.
    
    执行完整的多Agent任务调度，支持指定角色、执行模式、LLM后端等参数。
    
    This is the core dispatch interface that orchestrates multiple AI agents
    to collaborate on a complex task.
    
    **Features:**
    - Automatic role matching based on task content
    - Parallel or sequential execution modes
    - Intent detection and workflow mapping
    - Consensus-based decision making
    - Context compression for long conversations
    - Memory bridge for cross-session learning
    """,
)
async def dispatch_task(request: TaskDispatchRequest):
    """
    Full task dispatch endpoint.

    Args:
        request: Task dispatch request with task, roles, mode, etc.

    Returns:
        DispatchResponse with complete results from all workers
    """
    try:
        dispatcher = _get_dispatcher()

        llm_backend = None
        if request.backend and request.backend.lower() not in ("none", "mock", ""):
            try:
                from scripts.collaboration.llm_backend import create_llm_backend

                llm_backend = create_llm_backend(request.backend.lower())
                logger.info(f"Using LLM backend: {request.backend}")
            except Exception as backend_err:
                logger.warning(f"Failed to create LLM backend '{request.backend}': {backend_err}, using default")
                pass

        result = dispatcher.dispatch(
            task_description=request.task,
            roles=request.roles,
            mode=request.mode,
            dry_run=request.dry_run,
        )

        response_data = _convert_dispatch_result(result)
        return DispatchResponse(**response_data)

    except HTTPException:
        raise
    except ImportError as e:
        logger.error(f"Missing dependency during dispatch: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: Missing dependency - {str(e)}")
    except Exception as e:
        logger.error(f"Dispatch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dispatch failed: {str(e)}")


@router.post(
    "/api/v1/tasks/quick",
    response_model=DispatchResponse,
    summary="Quick Task Dispatch / 快速任务调度",
    description="""
    Quick dispatch with simplified parameters.
    
    快速调度接口，使用简化的参数，自动选择最优配置。
    
    Ideal for simple tasks where you just want to get results quickly
    without configuring all options.
    """,
)
async def quick_dispatch(request: QuickDispatchRequest):
    """
    Quick dispatch endpoint.

    Args:
        request: Quick dispatch request with task and format options

    Returns:
        DispatchResponse with formatted summary
    """
    try:
        dispatcher = _get_dispatcher()

        result = dispatcher.quick_dispatch(
            task=request.task,
            output_format=request.output_format,
            include_action_items=request.include_action_items,
            include_timing=request.include_timing,
        )

        response_data = _convert_dispatch_result(result)
        return DispatchResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quick dispatch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Quick dispatch failed: {str(e)}")


@router.get(
    "/api/v1/tasks/history",
    response_model=DispatchHistoryResponse,
    summary="Get Dispatch History / 获取调度历史",
    description="""
    Retrieve recent task dispatch history.
    
    获取最近的任务调度历史记录。
    
    Returns the N most recent dispatch records from the in-memory history.
    """,
)
async def get_dispatch_history(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return / 最大返回记录数"),
):
    """
    Get dispatch history.

    Args:
        limit: Maximum number of records to return (1-100)

    Returns:
        DispatchHistoryResponse with list of historical dispatches
    """
    try:
        dispatcher = _get_dispatcher()
        history = dispatcher.get_history(limit=limit)

        return DispatchHistoryResponse(
            history=history,
            total=len(history),
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dispatch history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")


@router.get(
    "/api/v1/roles",
    response_model=RolesListResponse,
    summary="List Available Roles / 列出可用角色",
    description="""
    List all available agent roles with their information.
    
    列出所有可用的AI Agent角色及其详细信息。
    
    Includes core roles (architect, product-manager, security, tester,
    solo-coder, devops, ui-designer) and any planned/extended roles.
    """,
)
async def list_roles():
    """
    List all available roles.

    Returns:
        RolesListResponse with role information
    """
    try:
        from scripts.collaboration.models import (
            ROLE_REGISTRY,
            get_core_roles,
            get_planned_roles,
        )

        roles = []
        for role_id, role_def in ROLE_REGISTRY.items():
            roles.append(
                RoleInfo(
                    role_id=role_id,
                    name=role_def.name,
                    description=role_def.description,
                    keywords=getattr(role_def, "keywords", None),
                    status=getattr(role_def, "status", "active"),
                ).model_dump()
            )

        core_role_ids = [r.role_id for r in get_core_roles().values()]
        planned_role_ids = list(get_planned_roles().keys())

        return RolesListResponse(
            roles=roles,
            total=len(roles),
            core_roles=core_role_ids,
            planned_roles=planned_role_ids,
        )

    except Exception as e:
        logger.error(f"Failed to list roles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve roles: {str(e)}")
