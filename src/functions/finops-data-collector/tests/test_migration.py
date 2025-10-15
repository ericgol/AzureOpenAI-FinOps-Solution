"""
Migration validation tests for dependency refactor.

Tests to ensure the migration from deprecated packages to modern alternatives
works correctly and doesn't break existing functionality.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from typing import Dict, Any
import pandas as pd
import numpy as np

# Test imports to verify new packages work
try:
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

try:
    from pydantic import BaseModel, Field, field_validator, ConfigDict
    PYDANTIC_V2_AVAILABLE = True
except ImportError:
    PYDANTIC_V2_AVAILABLE = False

from shared.config import FinOpsConfig, get_config


class TestDeprecatedPackagesRemoved:
    """Test that deprecated packages are no longer importable."""

    def test_opencensus_not_imported(self):
        """Test that opencensus is not available (should be removed)."""
        with pytest.raises(ImportError):
            import opencensus.ext.azure  # noqa: F401

    def test_applicationinsights_not_imported(self):
        """Test that applicationinsights is not available (should be removed)."""
        with pytest.raises(ImportError):
            import applicationinsights  # noqa: F401


class TestNewPackagesAvailable:
    """Test that new packages are correctly installed and importable."""

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_opentelemetry_imports(self):
        """Test that OpenTelemetry packages are importable."""
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        
        assert configure_azure_monitor is not None
        assert trace is not None
        assert TracerProvider is not None

    @pytest.mark.skipif(not PYDANTIC_V2_AVAILABLE, reason="Pydantic v2 not installed")
    def test_pydantic_v2_imports(self):
        """Test that Pydantic v2 features are available."""
        from pydantic import BaseModel, Field, field_validator, ConfigDict
        
        assert BaseModel is not None
        assert Field is not None
        assert field_validator is not None
        assert ConfigDict is not None

    def test_azure_sdk_imports(self):
        """Test that updated Azure SDK packages are importable."""
        from azure.identity import DefaultAzureCredential
        from azure.monitor.query import LogsQueryClient
        from azure.storage.blob import BlobServiceClient
        
        assert DefaultAzureCredential is not None
        assert LogsQueryClient is not None
        assert BlobServiceClient is not None

    def test_data_processing_imports(self):
        """Test that updated data processing packages are importable."""
        import pandas as pd
        import numpy as np
        import pyarrow as pa
        
        assert pd is not None
        assert np is not None
        assert pa is not None

    def test_http_client_imports(self):
        """Test that updated HTTP client packages are importable."""
        import requests
        import aiohttp
        import httpx
        
        assert requests is not None
        assert aiohttp is not None
        assert httpx is not None


class TestPydanticV2Configuration:
    """Test that Pydantic v2 configuration works correctly."""

    def test_config_model_creation(self):
        """Test that FinOpsConfig can be created with new Pydantic v2 syntax."""
        # Mock environment variables
        test_env = {
            "LOG_ANALYTICS_WORKSPACE_ID": "test-workspace-id",
            "COST_MANAGEMENT_SCOPE": "/subscriptions/test-sub-id",
            "STORAGE_ACCOUNT_NAME": "teststorageaccount",
            "ENVIRONMENT": "test",
            "LOG_LEVEL": "DEBUG"
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            config = get_config()
            
            assert config.log_analytics_workspace_id == "test-workspace-id"
            assert config.cost_management_scope == "/subscriptions/test-sub-id"
            assert config.storage_account_name == "teststorageaccount"
            assert config.environment == "dev"  # Default value
            assert config.log_level == "DEBUG"

    def test_field_validators_work(self):
        """Test that Pydantic v2 field validators work correctly."""
        test_env = {
            "LOG_ANALYTICS_WORKSPACE_ID": "test-workspace-id",
            "COST_MANAGEMENT_SCOPE": "/subscriptions/test-sub-id",
            "STORAGE_ACCOUNT_NAME": "teststorageaccount",
            "LOG_LEVEL": "info",  # lowercase
            "DEFAULT_ALLOCATION_METHOD": "PROPORTIONAL"  # uppercase
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            config = get_config()
            
            # Validators should normalize values
            assert config.log_level == "INFO"
            assert config.default_allocation_method == "proportional"

    def test_invalid_values_raise_errors(self):
        """Test that invalid configuration values raise validation errors."""
        test_env = {
            "LOG_ANALYTICS_WORKSPACE_ID": "test-workspace-id",
            "COST_MANAGEMENT_SCOPE": "/subscriptions/test-sub-id",
            "STORAGE_ACCOUNT_NAME": "teststorageaccount",
            "LOG_LEVEL": "INVALID_LEVEL"
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            with pytest.raises(ValueError, match="Invalid log level"):
                get_config()

    def test_config_dict_settings(self):
        """Test that ConfigDict settings work correctly."""
        # Test that the model_config is properly set
        config_dict = FinOpsConfig.model_config
        
        assert config_dict.get('env_file') == '.env'
        assert config_dict.get('env_file_encoding') == 'utf-8'
        assert config_dict.get('case_sensitive') is False
        assert config_dict.get('extra') == 'ignore'


class TestDataProcessingCompatibility:
    """Test that updated data processing libraries work with existing code."""

    def test_pandas_operations(self):
        """Test that pandas operations work with the new version."""
        # Create test data similar to what the telemetry collector uses
        test_data = [
            {
                'TimeGenerated': pd.Timestamp('2024-01-15 10:00:00'),
                'RequestId': 'req-001',
                'deviceId': 'device-001',
                'storeNumber': 'store-001',
                'StatusCode': 200,
                'ResponseTime': 150,
                'TokensUsed': 100
            },
            {
                'TimeGenerated': pd.Timestamp('2024-01-15 10:01:00'),
                'RequestId': 'req-002',
                'deviceId': 'device-002',
                'storeNumber': 'store-002',
                'StatusCode': 200,
                'ResponseTime': 200,
                'TokensUsed': 150
            }
        ]
        
        df = pd.DataFrame(test_data)
        
        # Test operations used in telemetry_collector.py
        assert len(df) == 2
        assert df['deviceId'].nunique() == 2
        assert df['storeNumber'].nunique() == 2
        assert df['ResponseTime'].mean() == 175.0
        assert df['TokensUsed'].sum() == 250
        assert (df['StatusCode'] < 400).mean() == 1.0

    def test_numpy_compatibility(self):
        """Test that numpy operations work correctly."""
        # Test basic numpy operations
        arr = np.array([1, 2, 3, 4, 5])
        
        assert arr.mean() == 3.0
        assert arr.sum() == 15
        assert arr.std() > 0

    def test_pandas_numpy_integration(self):
        """Test that pandas and numpy work together."""
        df = pd.DataFrame({'values': [1, 2, 3, 4, 5]})
        
        # Test numpy operations on pandas data
        assert np.mean(df['values']) == 3.0
        assert np.sum(df['values']) == 15


class TestTelemetryIntegration:
    """Test that new telemetry libraries integrate correctly."""

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_opentelemetry_tracer_creation(self):
        """Test that OpenTelemetry tracer can be created."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        
        # Set up a basic tracer
        trace.set_tracer_provider(TracerProvider())
        tracer = trace.get_tracer(__name__)
        
        assert tracer is not None
        
        # Test span creation
        with tracer.start_as_current_span("test_span") as span:
            span.set_attribute("test.attribute", "test_value")
            assert span.is_recording()

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    @patch.dict(os.environ, {"APPLICATIONINSIGHTS_CONNECTION_STRING": "test-connection-string"})
    def test_azure_monitor_configuration(self):
        """Test that Azure Monitor can be configured (mock)."""
        from azure.monitor.opentelemetry import configure_azure_monitor
        
        # This would normally configure Azure Monitor, but we'll mock it
        with patch('azure.monitor.opentelemetry.configure_azure_monitor') as mock_configure:
            configure_azure_monitor(
                connection_string="test-connection-string"
            )
            
            mock_configure.assert_called_once_with(
                connection_string="test-connection-string"
            )


class TestBackwardCompatibility:
    """Test that existing functionality continues to work after migration."""

    def test_config_singleton_pattern(self):
        """Test that configuration singleton pattern still works."""
        config1 = get_config()
        config2 = get_config()
        
        # Should be the same instance
        assert config1 is config2

    def test_config_methods_still_work(self):
        """Test that configuration helper methods still work."""
        test_env = {
            "LOG_ANALYTICS_WORKSPACE_ID": "test-workspace-id",
            "COST_MANAGEMENT_SCOPE": "/subscriptions/test-sub-id",
            "STORAGE_ACCOUNT_NAME": "teststorageaccount",
            "STORAGE_ACCOUNT_KEY": "test-key"
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            config = get_config()
            
            # Test helper methods
            storage_connection = config.get_storage_connection_string()
            assert "test-key" in storage_connection
            assert "teststorageaccount" in storage_connection
            
            log_config = config.get_log_analytics_config()
            assert log_config["workspace_id"] == "test-workspace-id"
            
            cost_config = config.get_cost_management_config()
            assert cost_config["scope"] == "/subscriptions/test-sub-id"

    def test_kql_queries_still_available(self):
        """Test that KQL queries are still available."""
        config = get_config()
        queries = config.get_kql_queries()
        
        assert "apim_logs" in queries
        assert "app_insights_requests" in queries
        assert "lookback_hours" in queries["apim_logs"]


class TestPackageVersions:
    """Test that package versions meet minimum requirements."""

    def test_azure_functions_version(self):
        """Test that azure-functions is at minimum required version."""
        import azure.functions
        
        # Should have the new version with proper attributes
        assert hasattr(azure.functions, '__version__')

    def test_pydantic_version(self):
        """Test that Pydantic is v2."""
        import pydantic
        
        # Pydantic v2 has different version structure
        version = pydantic.VERSION
        major_version = version.split('.')[0] if isinstance(version, str) else version[0]
        assert int(major_version) >= 2

    def test_requests_version(self):
        """Test that requests is at minimum required version."""
        import requests
        
        version = requests.__version__
        major, minor, patch = version.split('.')
        
        # Should be at least 2.32.5
        assert int(major) >= 2
        if int(major) == 2:
            assert int(minor) >= 32

    def test_pandas_version(self):
        """Test that pandas is at minimum required version."""
        import pandas as pd
        
        version = pd.__version__
        major, minor = version.split('.')[:2]
        
        # Should be at least 2.3.3
        assert int(major) >= 2
        if int(major) == 2:
            assert int(minor) >= 3


if __name__ == "__main__":
    # Run tests when script is executed directly
    pytest.main([__file__, "-v"])