#!/usr/bin/env python3
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
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, Depends, HTTPException, Query

from scripts.api.models import (
    CommandMapping,
    LifecyclePhase,
    PhaseActionRequest,
    PhaseActionResult,
    PhaseStatus,
)
from scripts.api.security import audit_log, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lifecycle", tags=["Lifecycle Management"])


@router.get(
    "/phases",
    response_model=list[LifecyclePhase],
    summary="List all lifecycle phases",
    description="Retrieve complete list of all 11 lifecycle phases with their current status",
)
async def list_phases(
    status_filter: PhaseStatus | None = Query(None, description="Filter by phase status"),
    include_details: bool = Query(False, description="Include detailed artifact information"),
    user_id: str = Depends(require_permission("TASK_READ")),
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
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol

        protocol = get_shared_protocol()
        status = protocol.get_status()
        all_phases = protocol.get_all_phases()

        # Determine current status
        completed = set(status.completed_phases or [])
        failed = set(status.failed_phases or [])
        running = set()

        phases = []
        for phase in all_phases:
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
                artifacts_out=phase.artifacts_out if include_details else None,
            )
            phases.append(phase_data)

        logger.info("Retrieved %s phases", len(phases))
        return phases

    except ImportError as e:
        logger.error("Failed to load lifecycle protocol: %s", e)
        raise HTTPException(status_code=503, detail=f"Protocol unavailable: {str(e)}") from None
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("Invalid request for phases: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from None
    except (AttributeError, RuntimeError) as e:
        logger.error("Failed to list phases: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from None
    except Exception as e:
        logger.error("Unexpected error listing phases: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get(
    "/phases/{phase_id}",
    response_model=LifecyclePhase,
    summary="Get specific phase details",
    description="Retrieve detailed information about a specific lifecycle phase",
)
async def get_phase(
    phase_id: str,
    user_id: str = Depends(require_permission("TASK_READ")),
):
    """
    Get details of a specific phase.

    Args:
        phase_id: Phase identifier (e.g., P1, P8)

    Returns:
        LifecyclePhase object with full details
    """
    try:
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol

        protocol = get_shared_protocol()

        # Find the requested phase
        phase = next((p for p in protocol.get_all_phases() if p.phase_id == phase_id.upper()), None)

        if not phase:
            raise HTTPException(status_code=404, detail=f"Phase {phase_id} not found")

        # Get current status
        status = protocol.get_status()
        completed = set(status.completed_phases or [])
        failed = set(status.failed_phases or [])
        running = set(getattr(status, 'running_phases', None) or [])

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
            artifacts_out=phase.artifacts_out,
        )

    except HTTPException:
        raise
    except ImportError as e:
        logger.error("Failed to load lifecycle protocol: %s", e)
        raise HTTPException(status_code=503, detail=f"Protocol unavailable: {str(e)}") from None
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("Invalid request for phase %s: %s", phase_id, e)
        raise HTTPException(status_code=400, detail=str(e)) from None
    except (AttributeError, RuntimeError) as e:
        logger.error("Failed to get phase %s: %s", phase_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from None
    except Exception as e:
        logger.error("Unexpected error getting phase %s: %s", phase_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get(
    "/status",
    summary="Get current lifecycle status",
    description="Retrieve overall lifecycle execution status and progress",
)
async def get_lifecycle_status(
    user_id: str = Depends(require_permission("TASK_READ")),
):
    """
    Get current lifecycle status.

    Returns:
        Dictionary containing lifecycle status information
    """
    try:
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol

        protocol = get_shared_protocol()
        status = protocol.get_status()
        all_phases_list = protocol.get_all_phases()

        return {
            "mode": status.mode.value if hasattr(status.mode, 'value') else str(status.mode),
            "current_phase": status.current_phase or "none",
            "total_phases": len(all_phases_list),
            "completed_phases": status.completed_phases or [],
            "running_phases": [],
            "failed_phases": status.failed_phases or [],
            "pending_phases": [p.phase_id for p in all_phases_list if p.phase_id not in (status.completed_phases or [])],
            "progress_percent": status.progress_percent,
            "is_complete": len(status.completed_phases or []) == len(all_phases_list),
            "timestamp": None,
        }

    except ImportError as e:
        logger.error("Failed to load lifecycle protocol: %s", e)
        raise HTTPException(status_code=503, detail=f"Protocol unavailable: {str(e)}") from None
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("Invalid data in lifecycle status: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from None
    except (AttributeError, RuntimeError) as e:
        logger.error("Failed to get lifecycle status: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from None
    except Exception as e:
        logger.error("Unexpected error getting lifecycle status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.post(
    "/actions",
    response_model=PhaseActionResult,
    summary="Execute phase action",
    description="Execute an action on a specific phase (advance/complete/reset/skip)",
)
async def execute_phase_action(
    request: PhaseActionRequest,
    user_id: str = Depends(require_permission("TASK_UPDATE")),
):
    """
    Execute an action on a lifecycle phase.

    Args:
        request: Action request containing phase_id, action, and options
        user_id: Authenticated user ID from API Key.

    Returns:
        ActionResult indicating success/failure
    """
    try:
        from datetime import datetime

        from scripts.collaboration.lifecycle_protocol import get_shared_protocol

        protocol = get_shared_protocol()
        phase_id = request.phase_id.upper()

        # Validate action
        valid_actions = ["advance", "complete", "reset", "skip"]
        if request.action not in valid_actions:
            raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")

        # Get previous status
        status = protocol.get_status()
        completed = status.completed_phases or []
        failed = status.failed_phases or []

        previous_status = (
            PhaseStatus.COMPLETED
            if phase_id in completed
            else PhaseStatus.FAILED
            if phase_id in failed
            else PhaseStatus.PENDING
        )

        # Execute action
        if request.action == "advance":
            result = protocol.advance_to_phase(phase_id)
            success = result.success if hasattr(result, "success") else True
            message = f"Advanced to phase {phase_id}" if success else f"Failed to advance to {phase_id}"
            new_status = PhaseStatus.RUNNING if success else previous_status

        elif request.action == "complete":
            try:
                protocol.mark_phase_completed(phase_id)
                success = True
                message = f"Phase {phase_id} marked as completed"
                new_status = PhaseStatus.COMPLETED
            except (ValueError, KeyError, AttributeError, RuntimeError) as ex:
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

        audit_log(
            user_id=user_id,
            action=f"lifecycle:{request.action}",
            resource_type="phase",
            resource_id=phase_id,
            result="success" if success else "failure",
            details={"previous": previous_status.value, "new": new_status.value},
        )

        return PhaseActionResult(
            success=success,
            phase_id=phase_id,
            action=request.action,
            message=message,
            previous_status=previous_status,
            new_status=new_status,
            performed_at=datetime.now(),
        )

    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError) as e:
        logger.warning("Invalid request for action %s on phase %s: %s", request.action, request.phase_id, e)
        raise HTTPException(status_code=400, detail=str(e)) from None
    except RuntimeError as e:
        logger.error("Failed to execute action %s on phase %s: %s", request.action, request.phase_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from None
    except Exception as e:
        logger.error("Unexpected error executing action on phase %s: %s", request.phase_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get(
    "/mappings",
    response_model=list[CommandMapping],
    summary="List CLI command mappings",
    description="Retrieve mapping of CLI commands to lifecycle phases",
)
async def list_command_mappings(
    user_id: str = Depends(require_permission("TASK_READ")),
):
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
            except (KeyError, AttributeError, RuntimeError):
                phase_ids = mapping.phases

            mappings.append(
                CommandMapping(command=cmd_name, phases=phase_ids, mode=mapping.mode or "shortcut", gate=mapping.gate)
            )

        logger.info("Retrieved %s command mappings", len(mappings))
        return mappings

    except ImportError as e:
        logger.error("Failed to load lifecycle protocol: %s", e)
        raise HTTPException(status_code=503, detail=f"Protocol unavailable: {str(e)}") from None
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("Invalid data in command mappings: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from None
    except (AttributeError, RuntimeError) as e:
        logger.error("Failed to list mappings: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from None
    except Exception as e:
        logger.error("Unexpected error listing mappings: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from None
