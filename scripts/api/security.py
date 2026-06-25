#!/usr/bin/env python3
"""API Security infrastructure — API Key auth, RBAC, Audit logging.

Provides FastAPI dependencies for securing REST API endpoints:
  - require_api_key: Extract and verify X-API-Key header
  - require_permission: Factory for permission-specific dependencies
  - get_audit_logger: Singleton AuditLogger for write operations

Design doc: docs/spec/API_SECURITY_DESIGN.md
Issue: https://github.com/lulin70/DevSquad/issues/4
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from typing import Any, Callable, Awaitable

from fastapi import Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports (avoid circular imports and optional dependency issues)
# ---------------------------------------------------------------------------

_rbac_engine: Any = None  # RBACEngine | None
_audit_logger: Any = None  # AuditLogger | None
_api_key_store: APIKeyStore | None = None
_init_lock = threading.Lock()


def _get_rbac_engine() -> Any:
    """Get or create singleton RBACEngine."""
    global _rbac_engine
    if _rbac_engine is None:
        with _init_lock:
            if _rbac_engine is None:
                from scripts.collaboration.rbac_engine import RBACEngine

                _rbac_engine = RBACEngine()
                _load_api_keys_into_rbac(_rbac_engine)
    return _rbac_engine


def get_audit_logger() -> Any:
    """Get or create singleton AuditLogger.

    Returns None if AuditLogger cannot be initialized (graceful degradation).
    """
    global _audit_logger
    if _audit_logger is None:
        with _init_lock:
            if _audit_logger is None:
                try:
                    from scripts.collaboration.audit_logger import AuditLogger

                    audit_dir = os.environ.get(
                        "DEVSQUAD_AUDIT_DIR",
                        os.path.join(os.getcwd(), ".devsquad_data", "audit"),
                    )
                    _audit_logger = AuditLogger(log_dir=audit_dir)
                    logger.info("AuditLogger initialized at %s", audit_dir)
                except (ImportError, OSError, RuntimeError) as e:
                    logger.warning("AuditLogger initialization failed: %s", e)
                    _audit_logger = None
    return _audit_logger


# ---------------------------------------------------------------------------
# API Key Store
# ---------------------------------------------------------------------------


class APIKeyStore:
    """Manages API Key to user_id mapping.

    Loads API keys from config/deployment.yaml under api_security.api_keys.
    Keys are stored as SHA-256 hashes; plaintext is never persisted.
    """

    def __init__(self) -> None:
        self._key_to_user: dict[str, str] = {}  # sha256_hash -> user_id
        self._load_config()

    def _load_config(self) -> None:
        """Load API keys from config/deployment.yaml."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config",
            "deployment.yaml",
        )

        if not os.path.exists(config_path):
            logger.debug("No deployment.yaml at %s, API Key auth disabled", config_path)
            return

        try:
            import yaml

            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            api_security = config.get("api_security", {})
            if not api_security.get("enabled", False):
                logger.info("API security disabled in config")
                return

            api_keys = api_security.get("api_keys", [])
            for entry in api_keys:
                key_hash = entry.get("key_hash", "")
                user_id = entry.get("user_id", "")
                active = entry.get("active", True)

                if not key_hash or not user_id or not active:
                    continue

                # Normalize: strip "sha256:" prefix if present
                if key_hash.startswith("sha256:"):
                    key_hash = key_hash[7:]

                self._key_to_user[key_hash] = user_id

            logger.info("Loaded %d API keys from config", len(self._key_to_user))

        except (OSError, ValueError, KeyError, ImportError) as e:
            logger.warning("Failed to load API keys from config: %s", e)

    def verify(self, api_key: str) -> str | None:
        """Verify an API key and return the associated user_id.

        Args:
            api_key: Plaintext API key from X-API-Key header.

        Returns:
            user_id if valid, None if invalid.
        """
        if not api_key:
            return None

        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        return self._key_to_user.get(key_hash)

    def has_keys(self) -> bool:
        """Check if any API keys are configured."""
        return len(self._key_to_user) > 0


def _get_api_key_store() -> APIKeyStore:
    """Get or create singleton APIKeyStore."""
    global _api_key_store
    if _api_key_store is None:
        with _init_lock:
            if _api_key_store is None:
                _api_key_store = APIKeyStore()
    return _api_key_store


def _load_api_keys_into_rbac(engine: Any) -> None:
    """Load users from config into RBACEngine.

    Reads api_security.api_keys and creates RBACUser entries with
    the specified roles.
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config",
        "deployment.yaml",
    )

    if not os.path.exists(config_path):
        return

    try:
        import yaml

        from scripts.collaboration.rbac_engine import RBACUser, UserRole

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        api_security = config.get("api_security", {})
        if not api_security.get("enabled", False):
            return

        api_keys = api_security.get("api_keys", [])
        for entry in api_keys:
            user_id = entry.get("user_id", "")
            roles_str = entry.get("roles", [])
            active = entry.get("active", True)

            if not user_id or not active:
                continue

            # Convert role strings to UserRole enum
            # Accept both enum name (e.g., "SUPER_ADMIN") and value (e.g., "super_admin")
            roles: set[Any] = set()
            for role_str in roles_str:
                try:
                    # Try by value first (e.g., "super_admin")
                    roles.add(UserRole(role_str))
                except ValueError:
                    try:
                        # Try by name (e.g., "SUPER_ADMIN")
                        roles.add(UserRole[role_str])
                    except KeyError:
                        logger.warning("Unknown role '%s' for user %s", role_str, user_id)

            if not roles:
                roles = {UserRole.VIEWER}  # Default to VIEWER

            user = RBACUser(
                user_id=user_id,
                username=user_id.split("@")[0] if "@" in user_id else user_id,
                roles=roles,
                is_active=True,
            )
            engine.add_user(user)
            logger.info("Registered RBAC user %s with roles %s", user_id, roles)

    except (OSError, ValueError, KeyError, ImportError) as e:
        logger.warning("Failed to load RBAC users from config: %s", e)


# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------


def _is_auth_disabled() -> bool:
    """Check if auth is disabled via environment variable (dev/test mode)."""
    return os.environ.get("DEVSQUAD_API_AUTH_DISABLED", "").lower() in ("1", "true", "yes")


async def require_api_key(request: Request) -> str:
    """FastAPI dependency: extract and verify X-API-Key header.

    Returns:
        user_id of the authenticated user.

    Raises:
        HTTPException 401 if API key is missing or invalid.
        HTTPException 403 if auth is disabled but no keys configured.
    """
    # Dev/test mode: skip auth entirely
    if _is_auth_disabled():
        return "dev-user"

    api_key = request.headers.get("X-API-Key", "")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header. Set DEVSQUAD_API_AUTH_DISABLED=1 for dev mode.",
        )

    store = _get_api_key_store()
    user_id = store.verify(api_key)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return user_id


def require_permission(permission: Any) -> Callable[..., Awaitable[str]]:
    """Factory: create a FastAPI dependency that checks a specific permission.

    Usage:
        @router.post("/dispatch")
        async def dispatch(
            user_id: str = Depends(require_permission("TASK_EXECUTE")),
        ):
            ...

    Args:
        permission: A Permission enum value or permission name string (e.g., "TASK_EXECUTE").

    Returns:
        FastAPI dependency function that returns user_id or raises 403.
    """

    async def _check_permission(user_id: str = Depends(require_api_key)) -> str:
        """Check if user has the required permission.

        Chains require_api_key as a sub-dependency: FastAPI will call
        require_api_key first to authenticate, then pass user_id here.
        """
        # Dev/test mode: require_api_key already returned "dev-user";
        # skip RBAC check entirely (no user exists in RBAC engine)
        if _is_auth_disabled():
            return user_id

        engine = _get_rbac_engine()

        # Convert string permission to Permission enum if needed
        perm = permission
        if isinstance(permission, str):
            from scripts.collaboration.rbac_engine import Permission

            try:
                perm = Permission[permission]
            except KeyError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Unknown permission: {permission}",
                ) from None

        if not engine.check_permission(user_id, perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires {perm.value}",
            )

        return user_id

    return _check_permission


def audit_log(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str = "",
    result: str = "success",
    details: dict | None = None,
) -> None:
    """Convenience function to write an audit log entry.

    Silently skips if AuditLogger is not available (graceful degradation).
    """
    al = get_audit_logger()
    if al is None:
        return

    try:
        al.log(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            result=result,
        )
    except (ValueError, RuntimeError, OSError) as e:
        logger.warning("Audit log write failed: %s", e)


# ---------------------------------------------------------------------------
# Status reporting (for startup logs)
# ---------------------------------------------------------------------------


def get_security_status() -> dict:
    """Get current security configuration status for startup logging."""
    auth_disabled = _is_auth_disabled()
    store = _get_api_key_store()

    return {
        "auth_enabled": not auth_disabled,
        "api_keys_configured": store.has_keys(),
        "api_key_count": len(store._key_to_user) if hasattr(store, "_key_to_user") else 0,
        "audit_logger_available": get_audit_logger() is not None,
        "rbac_engine_available": _get_rbac_engine() is not None,
    }
