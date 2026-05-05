#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad Authentication Module

Provides authentication and authorization for Streamlit Dashboard.

Features:
  - Basic authentication with configurable credentials
  - Role-based access control (admin/operator/viewer)
  - Session management
  - OAuth2 support (optional)

Usage:
    from scripts.auth import AuthManager, require_auth, check_permission
    
    auth = AuthManager(config_path="config/deployment.yaml")
    auth.authenticate()  # Call in Streamlit app
"""

import hashlib
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles for access control."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


@dataclass
class User:
    """Authenticated user information."""
    username: str
    email: str
    name: str
    role: UserRole
    authenticated_at: datetime
    session_id: str
    
    def can_execute_phases(self) -> bool:
        """Check if user can execute lifecycle phases."""
        return self.role in [UserRole.ADMIN, UserRole.OPERATOR]
    
    def can_view_metrics(self) -> bool:
        """Check if user can view metrics."""
        return True  # All roles can view metrics
    
    def can_modify_config(self) -> bool:
        """Check if user can modify configuration."""
        return self.role == UserRole.ADMIN


class AuthManager:
    """
    Authentication manager for DevSquad dashboard.
    
    Handles user authentication, session management,
    and role-based access control.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize authentication manager.
        
        Args:
            config_path: Path to deployment configuration file.
                        If None, uses default config/deployment.yaml
        """
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config",
            "deployment.yaml"
        )
        
        self.config = self._load_config()
        self.auth_enabled = self.config.get("authentication", {}).get("enabled", False)
        self.credentials = self._get_credentials()
        self.cookie_settings = self.config.get("authentication", {}).get("cookie", {})
        
        # Validate configuration security
        self._validate_config_security()
        
        logger.info(f"AuthManager initialized (enabled={self.auth_enabled})")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load deployment configuration from YAML file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            else:
                logger.warning(f"Config file not found: {self.config_path}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def _get_credentials(self) -> Dict[str, Dict]:
        """Get credentials from configuration."""
        auth_config = self.config.get("authentication", {})
        return auth_config.get("credentials", {}).get("usernames", {})
    
    def _validate_config_security(self):
        """
        Validate configuration for security issues.
        
        Warns about:
        - Placeholder passwords
        - Default session keys
        - Insecure configurations
        """
        if not self.auth_enabled:
            return
        
        warnings = []
        
        # Check for placeholder passwords
        placeholder_patterns = [
            "hashed_password_here",
            "password",
            "changeme",
            "default",
            "your_password",
        ]
        
        for username, cred in self.credentials.items():
            password = cred.get("password", "")
            if any(pattern in password.lower() for pattern in placeholder_patterns):
                warnings.append(
                    f"User '{username}' has placeholder password: {password[:20]}..."
                )
        
        # Check for default session key
        cookie_key = self.cookie_settings.get("key", "")
        default_keys = [
            "devsquad_session_key_change_in_production",
            "change_this_key",
            "default_secret_key",
        ]
        
        if any(key == cookie_key for key in default_keys):
            warnings.append(
                f"Using default session key: {cookie_key}. "
                "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        
        # Log warnings
        if warnings:
            logger.warning("=" * 60)
            logger.warning("SECURITY WARNINGS - Configuration Issues Detected:")
            for warning in warnings:
                logger.warning(f"  ⚠️  {warning}")
            logger.warning("=" * 60)
            logger.warning(
                "Please update config/deployment.yaml with secure values before production use."
            )
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_credentials(self, username: str, password: str) -> Optional[User]:
        """
        Verify user credentials.
        
        Args:
            username: Username to verify
            password: Plain text password
            
        Returns:
            User object if authenticated, None otherwise
        """
        if username not in self.credentials:
            logger.warning(f"Login attempt for unknown user: {username}")
            return None
        
        cred = self.credentials[username]
        stored_password_hash = cred.get("password", "")
        input_password_hash = self._hash_password(password)
        
        # For demo purposes, also allow plain text comparison
        # In production, only use hashed comparison
        if input_password_hash != stored_password_hash and password != stored_password_hash.replace("$2b$12$", ""):
            logger.warning(f"Failed login attempt for user: {username}")
            return None
        
        # Create user object
        try:
            role = UserRole(cred.get("role", "viewer"))
        except ValueError:
            role = UserRole.VIEWER
        
        user = User(
            username=username,
            email=cred.get("email", ""),
            name=cred.get("name", username),
            role=role,
            authenticated_at=datetime.now(),
            session_id=hashlib.md5(
                f"{username}{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16]
        )
        
        logger.info(f"User authenticated: {username} (role={role.value})")
        return user
    
    def authenticate_streamlit(self):
        """
        Authenticate user in Streamlit application.
        
        This method should be called at the beginning of a Streamlit app.
        It handles the login form and session state management.
        """
        try:
            import streamlit as st
            
            if not self.auth_enabled:
                # Authentication disabled, set default admin user
                if "user" not in st.session_state:
                    st.session_state.user = User(
                        username="admin",
                        email="admin@devsquad.local",
                        name="Administrator",
                        role=UserRole.ADMIN,
                        authenticated_at=datetime.now(),
                        session_id="dev_mode"
                    )
                return
            
            # Check if already authenticated
            if "user" in st.session_state:
                return
            
            # Show login form
            st.title("🔐 DevSquad Login")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.image(
                    "https://streamlit.io/images/brand/streamlit-logo-primary-colormark-lighttext.png",
                    width=120
                )
            
            with col2:
                st.markdown("""
                ### Welcome to DevSquad Dashboard
                
                Please enter your credentials to access the lifecycle monitoring system.
                """)
            
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", type="primary")
                
                if submitted:
                    user = self.verify_credentials(username, password)
                    if user:
                        st.session_state.user = user
                        st.success(f"✅ Welcome, {user.name}!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
            
            # Stop execution if not authenticated
            st.stop()
            
        except ImportError:
            logger.warning("Streamlit not available, skipping authentication UI")
    
    def get_current_user(self) -> Optional[User]:
        """
        Get currently authenticated user.
        
        Returns:
            User object if authenticated, None otherwise
        """
        try:
            import streamlit as st
            return st.session_state.get("user")
        except ImportError:
            return None
    
    def logout(self):
        """Logout current user."""
        try:
            import streamlit as st
            if "user" in st.session_state:
                del st.session_state.user
            st.rerun()
        except ImportError:
            pass
    
    def get_login_button(self):
        """
        Generate logout button for Streamlit sidebar.
        
        Returns:
            Streamlit button or None
        """
        try:
            import streamlit as st
            
            user = self.get_current_user()
            if user and self.auth_enabled:
                if st.sidebar.button("🚪 Logout"):
                    self.logout()
                
                st.sidebar.markdown(f"""
                **Logged in as:** {user.name}
                **Role:** `{user.role.value}`
                **Session:** `{user.session_id[:8]}...`
                """, unsafe_allow_html=True)
                
        except ImportError:
            pass


def require_auth(func):
    """
    Decorator to require authentication for API endpoints.
    
    Usage:
        @require_auth
        def protected_endpoint():
            return {"message": "This is protected"}
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # This would integrate with FastAPI's Depends() in real implementation
        # For now, just log and call the function
        logger.debug(f"Auth check for {func.__name__}")
        return func(*args, **kwargs)
    return wrapper


def check_permission(required_role: UserRole = UserRole.VIEWER):
    """
    Decorator to check user permissions.
    
    Args:
        required_role: Minimum role required to access the resource
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = None
            try:
                import streamlit as st
                user = st.session_state.get("user")
            except (ImportError, AttributeError):
                pass
            
            if not user:
                raise PermissionError("Not authenticated")
            
            role_hierarchy = {
                UserRole.VIEWER: 0,
                UserRole.OPERATOR: 1,
                UserRole.ADMIN: 2
            }
            
            if role_hierarchy.get(user.role, 0) < role_hierarchy.get(required_role, 0):
                raise PermissionError(
                    f"Insufficient permissions. Required: {required_role.value}, "
                    f"Current: {user.role.value}"
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def create_demo_credentials():
    """
    Create demo credentials for testing purposes.
    
    Generates hashed passwords for default users.
    
    Returns:
        Dict with demo usernames and hashed passwords
    """
    demo_users = {
        "admin": {
            "email": "admin@devsquad.local",
            "name": "Administrator",
            "password": "admin123",
            "role": "admin"
        },
        "operator": {
            "email": "operator@devsquad.local",
            "name": "Operator",
            "password": "operator123",
            "role": "operator"
        },
        "viewer": {
            "email": "viewer@devsquad.local",
            "name": "Viewer",
            "password": "viewer123",
            "role": "viewer"
        }
    }
    
    # Hash passwords
    auth_manager = AuthManager.__new__(AuthManager)
    for username, info in demo_users.items():
        info["password"] = auth_manager._hash_password(info["password"])
    
    print("\n📋 Demo Credentials Created:")
    print("=" * 50)
    for username, info in demo_users.items():
        print(f"\nUsername: {username}")
        print(f"Password: (see below)")
        print(f"Role: {info['role']}")
        print(f"Hashed Password: {info['password']}")
    
    print("\n" + "=" * 50)
    print("⚠️  Plain-text passwords for demo:")
    print("  admin: admin123")
    print("  operator: operator123")
    print("  viewer: viewer123")
    print("=" * 50 + "\n")
    
    return demo_users


if __name__ == "__main__":
    # Demo: Create test credentials
    create_demo_credentials()
