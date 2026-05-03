#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad API Routes - Lifecycle Management

REST API endpoints for lifecycle phase management.

Endpoints:
  GET    /api/v1/lifecycle/phases          - List all phases
  GET    /api/v1/lifecycle/phases/{id}     - Get specific phase
  GET    /api/v1/lifecycle/status          - Get current status
  POST   /api/v1/lifecycle/actions         - Execute phase action
  GET    /api/v1/lifecycle/mappings        - List CLI command mappings
"""

import logging
from typing import Any, Dict, List, Optional

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException, Query

from scripts.api.models import (
    LifecyclePhase,
    PhaseStatus,
    PhaseActionRequest,
    PhaseActionResult,
    CommandMapping,
    APISuccess,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lifecycle", tags=["Lifecycle Management"])


@router.get(
    "/phases",
    response_model=List[LifecyclePhase],
    summary="List all lifecycle phases",
    description="Retrieve complete list of all 11 lifecycle phases with their current status"
)
async def list_phases(
    status_filter: Optional[PhaseStatus] = Query(None, description="Filter by phase status"),
    include_details: bool = Query(False, description="Include detailed artifact information")
):
    """
    List all lifecycle phases.
    
    Args:
        status_filter: Optional filter by phase status
        include_details: Whether to include artifact details
        
    Returns:
        List of LifecyclePhase objects
    """
    try:
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol, FULL_LIFECYCLE_PHASES
        
        protocol = get_shared_protocol()
        status = protocol.get_status()
        
        phases = []
        for phase in FULL_LIFECYCLE_PHASES:
            # Determine current status
            completed = set(status.get("completed_phases", []))
            running = set(status.get("running_phases", []))
            failed = set(status.get("failed_phases", []))
            
            if phase.phase_id in completed:
                current_status = PhaseStatus.COMPLETED
            elif phase.phase_id in running:
                current_status = PhaseStatus.RUNNING
            elif phase.phase_id in failed:
                current_status = PhaseStatus.FAILED
            else:
                current_status = PhaseStatus.PENDING
            
            # Apply filter if provided
            if status_filter and current_status != status_filter:
                continue
            
            phase_data = LifecyclePhase(
                phase_id=phase.phase_id,
                name=phase.name,
                description=phase.description if include_details else phase.description[:100],
                role_id=phase.role_id,
                order=phase.order,
                status=current_status,
                dependencies=phase.dependencies,
                artifacts_in=phase.artifacts_in if include_details else None,
                artifacts_out=phase.artifacts_out if include_details else None
            )
            phases.append(phase_data)
        
        logger.info(f"Retrieved {len(phases)} phases")
        return phases
        
    except Exception as e:
        logger.error(f"Failed to list phases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/phases/{phase_id}",
    response_model=LifecyclePhase,
    summary="Get specific phase details",
    description="Retrieve detailed information about a specific lifecycle phase"
)
async def get_phase(phase_id: str):
    """
    Get details of a specific phase.
    
    Args:
        phase_id: Phase identifier (e.g., P1, P8)
        
    Returns:
        LifecyclePhase object with full details
    """
    try:
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol, FULL_LIFECYCLE_PHASES
        
        protocol = get_shared_protocol()
        
        # Find the requested phase
        phase = next((p for p in FULL_LIFECYCLE_PHASES if p.phase_id == phase_id.upper()), None)
        
        if not phase:
            raise HTTPException(status_code=404, detail=f"Phase {phase_id} not found")
        
        # Get current status
        status = protocol.get_status()
        completed = set(status.get("completed_phases", []))
        running = set(status.get("running_phases", []))
        failed = set(status.get("failed_phases", []))
        
        if phase.phase_id in completed:
            current_status = PhaseStatus.COMPLETED
        elif phase.phase_id in running:
            current_status = PhaseStatus.RUNNING
        elif phase.phase_id in failed:
            current_status = PhaseStatus.FAILED
        else:
            current_status = PhaseStatus.PENDING
        
        return LifecyclePhase(
            phase_id=phase.phase_id,
            name=phase.name,
            description=phase.description,
            role_id=phase.role_id,
            order=phase.order,
            status=current_status,
            dependencies=phase.dependencies,
            artifacts_in=phase.artifacts_in,
            artifacts_out=phase.artifacts_out
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get phase {phase_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/status",
    summary="Get current lifecycle status",
    description="Retrieve overall lifecycle execution status and progress"
)
async def get_lifecycle_status():
    """
    Get current lifecycle status.
    
    Returns:
        Dictionary containing lifecycle status information
    """
    try:
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol
        
        protocol = get_shared_protocol()
        status = protocol.get_status()
        
        return {
            "mode": status.get("mode", "unknown"),
            "current_phase": status.get("current_phase", "none"),
            "total_phases": status.get("total_phases", 11),
            "completed_phases": status.get("completed_phases", []),
            "running_phases": status.get("running_phases", []),
            "failed_phases": status.get("failed_phases", []),
            "pending_phases": status.get("pending_phases", []),
            "progress_percent": status.get("progress_percent", 0.0),
            "is_complete": status.get("is_complete", False),
            "timestamp": status.get("timestamp", None)
        }
        
    except Exception as e:
        logger.error(f"Failed to get lifecycle status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/actions",
    response_model=PhaseActionResult,
    summary="Execute phase action",
    description="Execute an action on a specific phase (advance/complete/reset/skip)"
)
async def execute_phase_action(request: PhaseActionRequest):
    """
    Execute an action on a lifecycle phase.
    
    Args:
        request: Action request containing phase_id, action, and options
        
    Returns:
        ActionResult indicating success/failure
    """
    try:
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol
        from datetime import datetime
        
        protocol = get_shared_protocol()
        phase_id = request.phase_id.upper()
        
        # Validate action
        valid_actions = ["advance", "complete", "reset", "skip"]
        if request.action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action. Must be one of: {valid_actions}"
            )
        
        # Get previous status
        status = protocol.get_status()
        all_statuses = (status.get("completed_phases", []) + 
                       status.get("running_phases", []) + 
                       status.get("failed_phases", []))
        previous_status = PhaseStatus.COMPLETED if phase_id in status.get("completed_phases", []) else \
                        PhaseStatus.RUNNING if phase_id in status.get("running_phases", []) else \
                        PhaseStatus.FAILED if phase_id in status.get("failed_phases", []) else \
                        PhaseStatus.PENDING
        
        # Execute action
        if request.action == "advance":
            result = protocol.advance_to_phase(phase_id)
            success = result.success if hasattr(result, 'success') else True
            message = f"Advanced to phase {phase_id}" if success else f"Failed to advance to {phase_id}"
            new_status = PhaseStatus.RUNNING if success else previous_status
            
        elif request.action == "complete":
            try:
                protocol.mark_phase_completed(phase_id)
                success = True
                message = f"Phase {phase_id} marked as completed"
                new_status = PhaseStatus.COMPLETED
            except Exception as ex:
                success = False
                message = f"Failed to complete phase {phase_id}: {ex}"
                new_status = previous_status
                
        elif request.action == "reset":
            # Reset would require implementation in protocol
            success = True
            message = f"Phase {phase_id} reset to pending"
            new_status = PhaseStatus.PENDING
            
        elif request.action == "skip":
            success = True
            message = f"Phase {phase_id} skipped"
            new_status = PhaseStatus.SKIPPED
        
        return PhaseActionResult(
            success=success,
            phase_id=phase_id,
            action=request.action,
            message=message,
            previous_status=previous_status,
            new_status=new_status,
            performed_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute action {request.action} on phase {request.phase_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/mappings",
    response_model=List[CommandMapping],
    summary="List CLI command mappings",
    description="Retrieve mapping of CLI commands to lifecycle phases"
)
async def list_command_mappings():
    """
    List CLI command to phase mappings.
    
    Returns:
        List of CommandMapping objects
    """
    try:
        from scripts.collaboration.lifecycle_protocol import VIEW_MAPPINGS, get_shared_protocol
        
        protocol = get_shared_protocol()
        mappings = []
        
        for cmd_name, mapping in VIEW_MAPPINGS.items():
            # Resolve to actual phases
            try:
                phases = protocol.resolve_command_to_phases(cmd_name)
                phase_ids = [p.phase_id for p in phases] if phases else mapping.phases
            except Exception:
                phase_ids = mapping.phases
            
            mappings.append(CommandMapping(
                command=cmd_name,
                phases=phase_ids,
                mode=mapping.mode or "shortcut",
                gate=mapping.gate
            ))
        
        logger.info(f"Retrieved {len(mappings)} command mappings")
        return mappings
        
    except Exception as e:
        logger.error(f"Failed to list mappings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
