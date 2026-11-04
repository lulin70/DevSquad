# DevSquad V5.0 - Simplicity Role - SimplicityConfig Unit Tests
# P8 Implementation Phase - Test-Driven Development
# Based on P3 Technical Design v1.1 - Section 1.4

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, Mock


class TestDeploymentDateStore:
    """Test DeploymentDateStore (A-002: anti-tampering mechanism)"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Create temporary directory for each test"""
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = Path(self.temp_dir) / ".deployment_date.json"
        yield
        shutil.rmtree(self.temp_dir)
    
    def test_config_001_initialize_deployment_date(self):
        """
        test_config_001: Initialize deployment date
        
        Given: No existing deployment date file
        When: DeploymentDateStore.initialize() is called
        Then: File is created with HMAC-SHA256 signature
        """
        from scripts.collaboration.simplicity_config import DeploymentDateStore
        
        deployment_date = datetime(2026, 11, 3, 0, 0, 0)
        
        with patch('scripts.collaboration.simplicity_config.DEPLOYMENT_DATE_FILE', self.store_path):
            DeploymentDateStore.initialize(deployment_date)
            
            assert self.store_path.exists()
            
            # Reload and verify
            loaded_date = DeploymentDateStore.load()
            assert loaded_date.date() == deployment_date.date()
    
    def test_config_002_load_with_valid_signature(self):
        """
        test_config_002: Load deployment date with valid HMAC signature
        
        Given: Existing file with valid signature
        When: DeploymentDateStore.load() is called
        Then: Returns deployment date without error
        """
        from scripts.collaboration.simplicity_config import DeploymentDateStore
        
        deployment_date = datetime(2026, 11, 1, 0, 0, 0)
        
        with patch('scripts.collaboration.simplicity_config.DEPLOYMENT_DATE_FILE', self.store_path):
            DeploymentDateStore.initialize(deployment_date)
            loaded_date = DeploymentDateStore.load()
            
            assert loaded_date.date() == deployment_date.date()
    
    def test_config_003_load_with_tampered_signature(self):
        """
        test_config_003: Detect tampered deployment date
        
        Given: File with invalid/tampered HMAC signature
        When: DeploymentDateStore.load() is called
        Then: Raises ValueError
        """
        from scripts.collaboration.simplicity_config import DeploymentDateStore
        import json
        
        # Create valid file first
        deployment_date = datetime(2026, 11, 1, 0, 0, 0)
        
        with patch('scripts.collaboration.simplicity_config.DEPLOYMENT_DATE_FILE', self.store_path):
            DeploymentDateStore.initialize(deployment_date)
            
            # Tamper with the file
            with open(self.store_path, 'r') as f:
                data = json.load(f)
            
            data['date'] = '2026-12-01T00:00:00'  # Change date without updating signature
            
            with open(self.store_path, 'w') as f:
                json.dump(data, f)
            
            # Should raise ValueError
            with pytest.raises(ValueError, match="HMAC signature verification failed"):
                DeploymentDateStore.load()
    
    def test_config_004_load_when_not_initialized(self):
        """
        test_config_004: Load when file does not exist
        
        Given: No deployment date file
        When: DeploymentDateStore.load() is called
        Then: Raises FileNotFoundError
        """
        from scripts.collaboration.simplicity_config import DeploymentDateStore
        
        with patch('scripts.collaboration.simplicity_config.DEPLOYMENT_DATE_FILE', self.store_path):
            with pytest.raises(FileNotFoundError):
                DeploymentDateStore.load()


class TestSimplicityConfig:
    """Test SimplicityConfig main interface"""
    
    def test_config_005_get_deployment_date(self):
        """
        test_config_005: Get deployment date via SimplicityConfig
        
        Given: DeploymentDateStore is initialized
        When: SimplicityConfig.get_deployment_date() is called
        Then: Returns the stored deployment date
        """
        from scripts.collaboration.simplicity_config import SimplicityConfig, DeploymentDateStore
        
        deployment_date = datetime(2026, 11, 3, 0, 0, 0)
        
        with patch.object(DeploymentDateStore, 'load', return_value=deployment_date):
            result = SimplicityConfig.get_deployment_date()
            assert result == deployment_date
    
    def test_config_006_get_current_mode_shadow(self):
        """
        test_config_006: Get current mode (Shadow: Day 0-6)
        
        Given: Deployment date is 5 days ago
        When: SimplicityConfig.get_current_mode() is called
        Then: Returns "shadow"
        """
        from scripts.collaboration.simplicity_config import SimplicityConfig
        
        deployment_date = datetime.now() - timedelta(days=5)
        
        with patch('scripts.collaboration.simplicity_config.SimplicityConfig.get_deployment_date', return_value=deployment_date):
            mode = SimplicityConfig.get_current_mode()
            assert mode == "shadow"
    
    def test_config_007_get_current_mode_soft(self):
        """
        test_config_007: Get current mode (Soft: Day 7-13)
        
        Given: Deployment date is 10 days ago
        When: SimplicityConfig.get_current_mode() is called
        Then: Returns "soft"
        """
        from scripts.collaboration.simplicity_config import SimplicityConfig
        
        deployment_date = datetime.now() - timedelta(days=10)
        
        with patch('scripts.collaboration.simplicity_config.SimplicityConfig.get_deployment_date', return_value=deployment_date):
            mode = SimplicityConfig.get_current_mode()
            assert mode == "soft"
    
    def test_config_008_get_current_mode_full(self):
        """
        test_config_008: Get current mode (Full: Day 14+)
        
        Given: Deployment date is 20 days ago
        When: SimplicityConfig.get_current_mode() is called
        Then: Returns "full"
        """
        from scripts.collaboration.simplicity_config import SimplicityConfig
        
        deployment_date = datetime.now() - timedelta(days=20)
        
        with patch('scripts.collaboration.simplicity_config.SimplicityConfig.get_deployment_date', return_value=deployment_date):
            mode = SimplicityConfig.get_current_mode()
            assert mode == "full"
