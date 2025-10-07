"""
Configuration management for FinOps solution.

Handles environment variables, settings, and configuration validation.
"""

import os
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field, validator
import logging


class FinOpsConfig(BaseSettings):
    """
    Configuration class for FinOps solution.
    
    Uses environment variables with fallback defaults.
    """
    
    # Azure Authentication
    azure_client_id: Optional[str] = Field(default=None, env="AZURE_CLIENT_ID")
    azure_tenant_id: Optional[str] = Field(default=None, env="AZURE_TENANT_ID")
    
    # Log Analytics
    log_analytics_workspace_id: str = Field(..., env="LOG_ANALYTICS_WORKSPACE_ID")
    log_analytics_workspace_key: Optional[str] = Field(default=None, env="LOG_ANALYTICS_WORKSPACE_KEY")
    
    # Cost Management
    cost_management_scope: str = Field(..., env="COST_MANAGEMENT_SCOPE")
    
    # Storage Account
    storage_account_name: str = Field(..., env="STORAGE_ACCOUNT_NAME")
    storage_account_key: Optional[str] = Field(default=None, env="STORAGE_ACCOUNT_KEY")
    
    # Container names
    finops_data_container: str = Field(default="finops-data", env="FINOPS_DATA_CONTAINER")
    raw_telemetry_container: str = Field(default="raw-telemetry", env="RAW_TELEMETRY_CONTAINER")
    cost_data_container: str = Field(default="cost-data", env="COST_DATA_CONTAINER")
    
    # Data collection settings
    data_collection_interval_minutes: int = Field(default=6, env="DATA_COLLECTION_INTERVAL_MINUTES")
    lookback_hours: int = Field(default=1, env="LOOKBACK_HOURS")
    max_retry_attempts: int = Field(default=3, env="MAX_RETRY_ATTEMPTS")
    
    # Environment
    environment: str = Field(default="dev", env="ENVIRONMENT")
    
    # Application Insights
    appinsights_connection_string: Optional[str] = Field(default=None, env="APPLICATIONINSIGHTS_CONNECTION_STRING")
    
    # Key Vault (optional)
    key_vault_url: Optional[str] = Field(default=None, env="KEY_VAULT_URL")
    
    # APIM settings
    apim_name: Optional[str] = Field(default=None, env="APIM_NAME")
    apim_resource_group: Optional[str] = Field(default=None, env="APIM_RESOURCE_GROUP")
    
    # Cost allocation settings
    default_allocation_method: str = Field(default="proportional", env="DEFAULT_ALLOCATION_METHOD")
    enable_user_mapping: bool = Field(default=True, env="ENABLE_USER_MAPPING")
    enable_store_mapping: bool = Field(default=True, env="ENABLE_STORE_MAPPING")
    
    # Performance settings
    batch_size: int = Field(default=1000, env="BATCH_SIZE")
    max_concurrent_requests: int = Field(default=10, env="MAX_CONCURRENT_REQUESTS")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    enable_debug_logging: bool = Field(default=False, env="ENABLE_DEBUG_LOGGING")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()
    
    @validator("default_allocation_method")
    def validate_allocation_method(cls, v):
        """Validate cost allocation method."""
        valid_methods = ["proportional", "equal", "usage-based", "token-based"]
        if v.lower() not in valid_methods:
            raise ValueError(f"Invalid allocation method: {v}. Must be one of {valid_methods}")
        return v.lower()
    
    def get_storage_connection_string(self) -> str:
        """
        Get storage account connection string.
        
        Returns:
            Storage connection string
        """
        if self.storage_account_key:
            return f"DefaultEndpointsProtocol=https;AccountName={self.storage_account_name};AccountKey={self.storage_account_key};EndpointSuffix=core.windows.net"
        else:
            # Use managed identity if no key provided
            return f"DefaultEndpointsProtocol=https;AccountName={self.storage_account_name};EndpointSuffix=core.windows.net"
    
    def get_log_analytics_config(self) -> Dict[str, Any]:
        """
        Get Log Analytics configuration.
        
        Returns:
            Log Analytics configuration dictionary
        """
        return {
            "workspace_id": self.log_analytics_workspace_id,
            "workspace_key": self.log_analytics_workspace_key,
            "lookback_hours": self.lookback_hours
        }
    
    def get_cost_management_config(self) -> Dict[str, Any]:
        """
        Get Cost Management configuration.
        
        Returns:
            Cost Management configuration dictionary
        """
        return {
            "scope": self.cost_management_scope,
            "lookback_hours": self.lookback_hours
        }
    
    def configure_logging(self) -> None:
        """Configure logging based on settings."""
        log_level = getattr(logging, self.log_level)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        if self.enable_debug_logging:
            logging.getLogger("azure").setLevel(logging.DEBUG)
            logging.getLogger("azure.storage").setLevel(logging.DEBUG)
            logging.getLogger("azure.monitor").setLevel(logging.DEBUG)
        else:
            # Suppress verbose Azure SDK logging
            logging.getLogger("azure").setLevel(logging.WARNING)
            logging.getLogger("azure.storage").setLevel(logging.WARNING)
            logging.getLogger("azure.monitor").setLevel(logging.WARNING)
            logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    def validate_required_config(self) -> None:
        """
        Validate that all required configuration is present.
        
        Raises:
            ValueError: If required configuration is missing
        """
        required_fields = [
            "log_analytics_workspace_id",
            "cost_management_scope",
            "storage_account_name"
        ]
        
        missing_fields = []
        for field in required_fields:
            if not getattr(self, field):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")
    
    def get_kql_queries(self) -> Dict[str, str]:
        """
        Get KQL queries for different data collection scenarios.
        
        Returns:
            Dictionary of KQL queries
        """
        return {
            "apim_logs": """
                ApiManagementGatewayLogs
                | where TimeGenerated >= ago({lookback_hours}h)
                | where OperationName != ""
                | extend deviceId = tostring(RequestHeaders["device-id"])
                | extend storeNumber = tostring(RequestHeaders["store-number"])
                | project 
                    TimeGenerated,
                    RequestId = CorrelationId,
                    deviceId = iif(deviceId == "", "unknown", deviceId),
                    storeNumber = iif(storeNumber == "", "unknown", storeNumber),
                    ApiName = OperationName,
                    Method = RequestMethod,
                    Url = RequestUri,
                    StatusCode = ResponseCode,
                    ResponseTime = DurationMs,
                    TokensUsed = toint(ResponseHeaders["x-ratelimit-remaining-tokens"]),
                    ResourceId = ResourceId
                | where StatusCode > 0
                | order by TimeGenerated desc
            """,
            
            "app_insights_requests": """
                requests
                | where timestamp >= ago({lookback_hours}h)
                | where name contains "openai"
                | extend deviceId = tostring(customDimensions["device-id"])
                | extend storeNumber = tostring(customDimensions["store-number"])
                | project 
                    TimeGenerated = timestamp,
                    RequestId = operation_Id,
                    deviceId = iif(deviceId == "", "unknown", deviceId),
                    storeNumber = iif(storeNumber == "", "unknown", storeNumber),
                    ApiName = name,
                    Method = "POST",
                    Url = url,
                    StatusCode = resultCode,
                    ResponseTime = duration,
                    TokensUsed = toint(customMeasurements["tokens_used"]),
                    ResourceId = cloud_RoleInstance
                | order by TimeGenerated desc
            """
        }


# Global configuration instance
_config_instance: Optional[FinOpsConfig] = None


def get_config() -> FinOpsConfig:
    """
    Get singleton configuration instance.
    
    Returns:
        FinOpsConfig instance
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = FinOpsConfig()
        _config_instance.validate_required_config()
        _config_instance.configure_logging()
    
    return _config_instance