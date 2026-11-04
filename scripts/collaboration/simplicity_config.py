# DevSquad V5.0 - Simplicity Role - Configuration Management
# DeploymentDateStore: Anti-tampering mechanism (A-002)
# SimplicityConfig: Progressive release mode management

"""
Simplicity Configuration Management

DeploymentDateStore:
- Stores deployment date with HMAC-SHA256 signature
- Prevents tampering with deployment timeline

SimplicityConfig:
- Progressive release modes:
  - Shadow (Day 0-6): REJECT → ADVISORY
  - Soft (Day 7-13): REJECT → CONDITIONAL
  - Full (Day 14+): Enforce REJECT
- Auto-downgrade on high false positive rate (>10%)
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


# Default storage path (can be overridden in tests)
DEPLOYMENT_DATE_FILE = Path.home() / ".devsquad" / ".deployment_date.json"
HMAC_SECRET = os.getenv("DEVSQUAD_HMAC_SECRET", "devsquad-simplicity-v5.0").encode()


class DeploymentDateStore:
    """
    Deployment date storage with HMAC-SHA256 signature
    
    A-002: Prevents tampering with deployment timeline
    """
    
    @classmethod
    def initialize(cls, deployment_date: datetime) -> None:
        """
        Initialize deployment date (only called once)
        
        Args:
            deployment_date: Deployment timestamp
        
        Raises:
            FileExistsError: If already initialized
        """
        if DEPLOYMENT_DATE_FILE.exists():
            raise FileExistsError(
                f"Deployment date already initialized at {DEPLOYMENT_DATE_FILE}"
            )
        
        # Ensure parent directory exists
        DEPLOYMENT_DATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Serialize date
        date_str = deployment_date.isoformat()
        
        # Calculate HMAC signature
        signature = hmac.new(
            HMAC_SECRET,
            date_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Write to file
        data = {
            "date": date_str,
            "signature": signature,
            "version": "1.0"
        }
        
        with open(DEPLOYMENT_DATE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Deployment date initialized: {deployment_date}")
    
    @classmethod
    def load(cls) -> datetime:
        """
        Load deployment date with HMAC verification
        
        Returns:
            Deployment datetime
        
        Raises:
            FileNotFoundError: If not initialized
            ValueError: If HMAC signature verification fails
        """
        if not DEPLOYMENT_DATE_FILE.exists():
            raise FileNotFoundError(
                f"Deployment date not initialized. Run: devsquad init --deployment-date"
            )
        
        with open(DEPLOYMENT_DATE_FILE, 'r') as f:
            data = json.load(f)
        
        date_str = data["date"]
        stored_signature = data["signature"]
        
        # Verify HMAC signature
        calculated_signature = hmac.new(
            HMAC_SECRET,
            date_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(calculated_signature, stored_signature):
            raise ValueError(
                "HMAC signature verification failed. Deployment date may have been tampered with."
            )
        
        return datetime.fromisoformat(date_str)


class SimplicityConfig:
    """Simplicity Role configuration management"""
    
    @classmethod
    def get_deployment_date(cls) -> datetime:
        """Get deployment date from anti-tampering store"""
        return DeploymentDateStore.load()
    
    @classmethod
    def get_current_mode(cls) -> str:
        """
        Determine current progressive release mode
        
        Returns:
            "shadow" | "soft" | "full"
        
        Logic:
            - Day 0-6: shadow (REJECT → ADVISORY)
            - Day 7-13: soft (REJECT → CONDITIONAL)
            - Day 14+: full (enforce REJECT)
        """
        try:
            deployment_date = cls.get_deployment_date()
        except FileNotFoundError:
            logger.warning("Deployment date not initialized, defaulting to 'shadow' mode")
            return "shadow"
        
        days_since_deployment = (datetime.now() - deployment_date).days
        
        if days_since_deployment < 7:
            return "shadow"
        elif days_since_deployment < 14:
            return "soft"
        else:
            return "full"
    
    @classmethod
    def check_false_positive_rate(cls) -> float:
        """
        Check false positive rate from WorkflowTrace
        
        Returns:
            False positive rate (0.0 - 1.0)
        
        Formula: human_overrides / total_simplicity_rejects
        
        Note: Placeholder implementation - will integrate with WorkflowTrace in P8-007
        """
        # TODO: Query WorkflowTrace for simplicity_reject events
        # For now, return 0.0 (no false positives)
        return 0.0
    
    @classmethod
    def auto_downgrade_if_needed(cls) -> str:
        """
        Auto-downgrade if false positive rate > 10%
        
        Returns:
            Adjusted mode ("shadow", "soft", or "full")
        """
        current_mode = cls.get_current_mode()
        false_positive_rate = cls.check_false_positive_rate()
        
        if false_positive_rate > 0.1:
            logger.warning(
                f"False positive rate {false_positive_rate:.1%} exceeds 10%. "
                f"Downgrading from '{current_mode}' to 'soft'"
            )
            return "soft"
        
        return current_mode
