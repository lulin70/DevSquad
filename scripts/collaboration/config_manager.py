#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration Manager

Centralized configuration management for LLM optimization modules.
Supports YAML configuration files with validation and defaults.

Features:
- YAML configuration loading
- Environment variable overrides
- Configuration validation
- Default values
- Hot reload support

Usage:
    from scripts.collaboration import get_config
    
    config = get_config()
    cache_ttl = config.get("cache.ttl_seconds", 86400)
    max_retries = config.get("retry.max_retries", 3)
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Configuration manager with YAML support and validation.
    """
    
    # Default configuration
    DEFAULT_CONFIG = {
        "cache": {
            "enabled": True,
            "cache_dir": "data/llm_cache",
            "ttl_seconds": 86400,  # 24 hours
            "max_memory_entries": 1000,
            "disk_cache_enabled": True
        },
        "retry": {
            "enabled": True,
            "max_retries": 3,
            "initial_delay": 1.0,
            "max_delay": 60.0,
            "exponential_base": 2.0,
            "jitter": True
        },
        "circuit_breaker": {
            "enabled": True,
            "failure_threshold": 5,
            "timeout_seconds": 60,
            "half_open_max_calls": 3
        },
        "performance": {
            "monitoring_enabled": True,
            "max_history": 10000,
            "bottleneck_threshold_ms": 1000.0,
            "export_interval_seconds": 300
        },
        "backends": {
            "primary": "openai",
            "fallback_order": ["anthropic", "cohere"],
            "timeout_seconds": 30
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": None  # None = console only
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to YAML configuration file (optional)
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = self.DEFAULT_CONFIG.copy()
        
        # Load from file if provided
        if config_path and Path(config_path).exists():
            self.load_from_file(config_path)
        
        # Override with environment variables
        self._load_from_env()
        
        logger.info(f"ConfigManager initialized (config_path: {config_path})")
    
    def load_from_file(self, config_path: str):
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to YAML file
        """
        try:
            with open(config_path, 'r') as f:
                file_config = yaml.safe_load(f)
            
            if file_config:
                self._merge_config(self.config, file_config)
                logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            raise
    
    def _merge_config(self, base: Dict, override: Dict):
        """Recursively merge override config into base config"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Cache settings
        if os.getenv("LLM_CACHE_ENABLED"):
            self.config["cache"]["enabled"] = os.getenv("LLM_CACHE_ENABLED").lower() == "true"
        if os.getenv("LLM_CACHE_TTL"):
            self.config["cache"]["ttl_seconds"] = int(os.getenv("LLM_CACHE_TTL"))
        if os.getenv("LLM_CACHE_DIR"):
            self.config["cache"]["cache_dir"] = os.getenv("LLM_CACHE_DIR")
        
        # Retry settings
        if os.getenv("LLM_MAX_RETRIES"):
            self.config["retry"]["max_retries"] = int(os.getenv("LLM_MAX_RETRIES"))
        if os.getenv("LLM_RETRY_DELAY"):
            self.config["retry"]["initial_delay"] = float(os.getenv("LLM_RETRY_DELAY"))
        
        # Backend settings
        if os.getenv("LLM_PRIMARY_BACKEND"):
            self.config["backends"]["primary"] = os.getenv("LLM_PRIMARY_BACKEND")
        if os.getenv("LLM_FALLBACK_BACKENDS"):
            backends = os.getenv("LLM_FALLBACK_BACKENDS").split(",")
            self.config["backends"]["fallback_order"] = [b.strip() for b in backends]
        
        # Logging
        if os.getenv("LLM_LOG_LEVEL"):
            self.config["logging"]["level"] = os.getenv("LLM_LOG_LEVEL")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.
        
        Args:
            key: Configuration key (e.g., "cache.ttl_seconds")
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        Set configuration value by dot-notation key.
        
        Args:
            key: Configuration key (e.g., "cache.ttl_seconds")
            value: Value to set
        """
        keys = key.split(".")
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.
        
        Args:
            section: Section name (e.g., "cache", "retry")
        
        Returns:
            Configuration section dictionary
        """
        return self.config.get(section, {}).copy()
    
    def reload(self):
        """Reload configuration from file"""
        if self.config_path and Path(self.config_path).exists():
            self.config = self.DEFAULT_CONFIG.copy()
            self.load_from_file(self.config_path)
            self._load_from_env()
            logger.info("Configuration reloaded")
    
    def save_to_file(self, output_path: str):
        """
        Save current configuration to YAML file.
        
        Args:
            output_path: Path to output YAML file
        """
        try:
            with open(output_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Configuration saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save config to {output_path}: {e}")
            raise
    
    def validate(self) -> bool:
        """
        Validate configuration values.
        
        Returns:
            True if valid, raises ValueError if invalid
        """
        # Validate cache settings
        if self.config["cache"]["ttl_seconds"] <= 0:
            raise ValueError("cache.ttl_seconds must be positive")
        if self.config["cache"]["max_memory_entries"] <= 0:
            raise ValueError("cache.max_memory_entries must be positive")
        
        # Validate retry settings
        if self.config["retry"]["max_retries"] < 0:
            raise ValueError("retry.max_retries must be non-negative")
        if self.config["retry"]["initial_delay"] <= 0:
            raise ValueError("retry.initial_delay must be positive")
        if self.config["retry"]["max_delay"] <= 0:
            raise ValueError("retry.max_delay must be positive")
        
        # Validate circuit breaker
        if self.config["circuit_breaker"]["failure_threshold"] <= 0:
            raise ValueError("circuit_breaker.failure_threshold must be positive")
        if self.config["circuit_breaker"]["timeout_seconds"] <= 0:
            raise ValueError("circuit_breaker.timeout_seconds must be positive")
        
        # Validate performance
        if self.config["performance"]["max_history"] <= 0:
            raise ValueError("performance.max_history must be positive")
        
        logger.info("Configuration validation passed")
        return True
    
    def export_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        return self.config.copy()
    
    def __repr__(self) -> str:
        return f"ConfigManager(config_path={self.config_path})"


# Global configuration instance
_global_config: Optional[ConfigManager] = None


def get_config(config_path: Optional[str] = None) -> ConfigManager:
    """
    Get global configuration manager instance (singleton).
    
    Args:
        config_path: Path to YAML configuration file (optional, only used on first call)
    
    Returns:
        ConfigManager instance
    """
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager(config_path)
    return _global_config


def reset_config():
    """Reset global configuration instance"""
    global _global_config
    _global_config = None


def create_default_config(output_path: str = "llm_optimization_config.yaml"):
    """
    Create a default configuration file.
    
    Args:
        output_path: Path to output YAML file
    """
    config = ConfigManager()
    config.save_to_file(output_path)
    print(f"Default configuration created: {output_path}")


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "create":
        # Create default config file
        output = sys.argv[2] if len(sys.argv) > 2 else "llm_optimization_config.yaml"
        create_default_config(output)
    else:
        # Demo configuration usage
        config = get_config()
        
        print("=== Configuration Demo ===")
        print(f"Cache TTL: {config.get('cache.ttl_seconds')}s")
        print(f"Max Retries: {config.get('retry.max_retries')}")
        print(f"Primary Backend: {config.get('backends.primary')}")
        print(f"Fallback Backends: {config.get('backends.fallback_order')}")
        
        # Validate
        config.validate()
        print("\n✓ Configuration is valid")
