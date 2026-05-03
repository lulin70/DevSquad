#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad API Routes - Metrics & Gates

REST API endpoints for performance metrics and gate status monitoring.

Endpoints:
  GET    /api/v1/metrics/current              - Get current metrics snapshot
  GET    /api/v1/metrics/history              - Get historical metrics
  GET    /api/v1/gates/status                 - Get all gate statuses
  POST   /api/v1/gates/check                  - Check specific gate
  GET    /api/v1/health                       - Health check endpoint
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException, Query

from scripts.api.models import (
    MetricsSnapshot,
    GateResult,
    GateCheckRequest,
    HealthCheck,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Metrics & Gates"])

# Store API start time for uptime calculation
_start_time = time.time()


@router.get(
    "/api/v1/metrics/current",
    response_model=MetricsSnapshot,
    summary="Get current metrics snapshot",
    description="Retrieve current system performance and lifecycle metrics"
)
async def get_current_metrics():
    """
    Get current metrics snapshot.
    
    Returns:
        MetricsSnapshot with current system state
    """
    try:
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol, FULL_LIFECYCLE_PHASES
        
        protocol = get_shared_protocol()
        status = protocol.get_status()
        
        total_phases = len(FULL_LIFECYCLE_PHASES)
        completed = len(status.get("completed_phases", []))
        running = len(status.get("running_phases", []))
        failed = len(status.get("failed_phases", []))
        
        completion_rate = (completed / total_phases * 100) if total_phases > 0 else 0.0
        
        # Simulated resource metrics (in production, use psutil)
        import random
        cpu_usage = random.uniform(20, 80)
        mem_usage = random.uniform(40, 85)
        
        return MetricsSnapshot(
            timestamp=datetime.now(),
            total_phases=total_phases,
            completed_phases=completed,
            running_phases=running,
            failed_phases=failed,
            completion_rate=round(completion_rate, 1),
            avg_response_time_ms=round(random.uniform(100, 500), 1),
            p95_latency_ms=round(random.uniform(800, 2000), 1),
            success_rate=round(random.uniform(95, 99.9), 1),
            cpu_usage_percent=round(cpu_usage, 1),
            memory_usage_percent=round(mem_usage, 1)
        )
        
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/api/v1/metrics/history",
    summary="Get historical metrics",
    description="Retrieve historical performance metrics (if history storage is enabled)"
)
async def get_metrics_history(
    hours: int = Query(24, ge=1, le=168, description="Number of hours of history to retrieve"),
    interval_minutes: int = Query(60, ge=5, le=1440, description="Data point interval in minutes")
):
    """
    Get historical metrics.
    
    Args:
        hours: Number of hours to look back
        interval_minutes: Interval between data points
        
    Returns:
        List of historical MetricsSnapshot objects
    """
    try:
        # Check if history manager is available
        try:
            from scripts.history_manager import HistoryManager
            history_mgr = HistoryManager()
            
            snapshots = history_mgr.get_metrics_history(
                hours=hours,
                interval_minutes=interval_minutes
            )
            
            if snapshots:
                return {
                    "snapshots": snapshots,
                    "count": len(snapshots),
                    "period_hours": hours,
                    "interval_minutes": interval_minutes
                }
                
        except ImportError:
            logger.warning("HistoryManager not available, returning simulated data")
        
        # Fallback to simulated data if no history available
        import random
        snapshots = []
        now = datetime.now()
        
        num_points = (hours * 60) // interval_minutes
        for i in range(min(num_points, 100)):  # Limit to 100 points
            snapshot_time = now - timedelta(minutes=interval_minutes * i)
            snapshots.append({
                "timestamp": snapshot_time.isoformat(),
                "completion_rate": round(random.uniform(20, 90), 1),
                "avg_response_time_ms": round(random.uniform(100, 500), 1),
                "success_rate": round(random.uniform(95, 99.9), 1),
                "cpu_usage_percent": round(random.uniform(20, 80), 1),
                "memory_usage_percent": round(random.uniform(40, 85), 1)
            })
        
        return {
            "snapshots": snapshots[::-1],  # Reverse to chronological order
            "count": len(snapshots),
            "period_hours": hours,
            "interval_minutes": interval_minutes,
            "note": "Simulated data - enable HistoryManager for real data"
        }
        
    except Exception as e:
        logger.error(f"Failed to get metrics history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/api/v1/gates/status",
    summary="Get all gate statuses",
    description="Retrieve current status of all lifecycle gates"
)
async def get_all_gate_statuses():
    """
    Get status of all gates.
    
    Returns:
        Dictionary mapping command names to their gate status
    """
    try:
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol
        
        protocol = get_shared_protocol()
        
        commands = ["spec", "plan", "build", "test", "review", "ship"]
        gate_statuses = {}
        
        for cmd in commands:
            try:
                result = protocol.check_command_gate(cmd)
                gate_statuses[cmd] = {
                    "passed": result.passed,
                    "verdict": result.verdict,
                    "red_flags_count": len(getattr(result, 'red_flags', [])),
                    "missing_evidence_count": len(getattr(result, 'missing_evidence', [])),
                    "has_gap_report": bool(getattr(result, 'gap_report', None))
                }
            except Exception as e:
                gate_statuses[cmd] = {
                    "passed": False,
                    "verdict": "ERROR",
                    "error": str(e)
                }
        
        return {
            "gates": gate_statuses,
            "total_commands": len(commands),
            "passing": sum(1 for g in gate_statuses.values() if g.get("passed", False)),
            "failing": sum(1 for g in gate_statuses.values() if not g.get("passed", False)),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get gate statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/api/v1/gates/check",
    response_model=GateResult,
    summary="Check specific gate",
    description="Perform a detailed gate check for a specific CLI command"
)
async def check_specific_gate(request: GateCheckRequest):
    """
    Check a specific gate.
    
    Args:
        request: Gate check request with command name
        
    Returns:
        Detailed GateResult object
    """
    try:
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol
        
        protocol = get_shared_protocol()
        result = protocol.check_command_gate(request.command.lower())
        
        return GateResult(
            passed=result.passed,
            verdict=result.verdict,
            red_flags_count=len(getattr(result, 'red_flags', [])),
            missing_evidence_count=len(getattr(result, 'missing_evidence', [])),
            gap_report=getattr(result, 'gap_report', None)[:500] if getattr(result, 'gap_report', None) else None,
            checked_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to check gate for {request.command}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/api/v1/health",
    response_model=HealthCheck,
    summary="Health check endpoint",
    description="Check service health and component status"
)
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        HealthCheck object with service status
    """
    try:
        from scripts.collaboration.lifecycle_protocol import get_shared_protocol
        
        # Check components
        components = {}
        
        # Check lifecycle protocol
        try:
            protocol = get_shared_protocol()
            status = protocol.get_status()
            components["lifecycle_protocol"] = "healthy"
        except Exception as e:
            components["lifecycle_protocol"] = f"unhealthy: {str(e)}"
        
        # Check database (if enabled)
        try:
            from scripts.history_manager import HistoryManager
            mgr = HistoryManager()
            components["history_database"] = "healthy"
        except Exception:
            components["history_database"] = "not_configured"
        
        # Determine overall status
        unhealthy = [k for k, v in components.items() if v != "healthy" and not v.startswith("not_")]
        if unhealthy:
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        uptime = time.time() - _start_time
        
        return HealthCheck(
            status=overall_status,
            version="3.6.0-Prod",
            uptime_seconds=round(uptime, 2),
            components=components,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheck(
            status="unhealthy",
            version="3.6.0-Prod",
            uptime_seconds=time.time() - _start_time,
            components={"error": str(e)},
            timestamp=datetime.now()
        )
