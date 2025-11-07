"""
Shared module for FinOps Data Collector Function App.

This module contains reusable components for:
- Configuration management
- Telemetry data collection
- Cost data collection  
- Data correlation and allocation
- Storage management
"""

__version__ = "1.0.0"

# Import key classes for easier access
from .config import get_config, FinOpsConfig
from .telemetry_collector import TelemetryCollector
from .cost_collector import CostCollector
from .data_correlator import DataCorrelator
from .storage_manager import StorageManager

__all__ = [
    "get_config",
    "FinOpsConfig",
    "TelemetryCollector",
    "CostCollector",
    "DataCorrelator",
    "StorageManager",
]
