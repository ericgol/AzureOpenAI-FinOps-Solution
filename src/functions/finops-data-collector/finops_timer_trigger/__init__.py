"""
FinOps Timer Trigger Function

This Azure Function runs every 6 minutes to collect and correlate:
1. APIM telemetry from Log Analytics
2. Cost data from Azure Cost Management API
3. Correlates the data and stores results in Azure Storage

Author: FinOps Team
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.monitor.query import LogsQueryClient
from azure.mgmt.costmanagement import CostManagementClient
import pandas as pd
from ..shared.config import FinOpsConfig
from ..shared.telemetry_collector import TelemetryCollector
from ..shared.cost_collector import CostCollector
from ..shared.data_correlator import DataCorrelator
from ..shared.storage_manager import StorageManager


def main(mytimer: func.TimerRequest) -> None:
    """
    Main entry point for the FinOps timer trigger function.
    
    Args:
        mytimer: Timer trigger context
    """
    utc_timestamp = datetime.utcnow().replace(tzinfo=None).isoformat()
    
    logging.info(f'FinOps data collection started at: {utc_timestamp}')
    
    # Initialize configuration
    config = FinOpsConfig()
    
    # Initialize Azure credential
    credential = DefaultAzureCredential()
    
    try:
        # Step 1: Collect telemetry data from Log Analytics
        logging.info("Step 1: Collecting telemetry data from Log Analytics")
        telemetry_collector = TelemetryCollector(config, credential)
        telemetry_data = telemetry_collector.collect_apim_logs()
        logging.info(f"Collected {len(telemetry_data)} telemetry records")
        
        # Step 2: Collect cost data from Cost Management API
        logging.info("Step 2: Collecting cost data from Cost Management API")
        cost_collector = CostCollector(config, credential)
        cost_data = cost_collector.collect_cost_data()
        logging.info(f"Collected {len(cost_data)} cost records")
        
        # Step 3: Correlate telemetry and cost data
        logging.info("Step 3: Correlating telemetry and cost data")
        data_correlator = DataCorrelator(config)
        correlated_data = data_correlator.correlate_data(telemetry_data, cost_data)
        logging.info(f"Generated {len(correlated_data)} correlated records")
        
        # Step 4: Store correlated data in Azure Storage
        logging.info("Step 4: Storing correlated data in Azure Storage")
        storage_manager = StorageManager(config, credential)
        storage_manager.store_correlated_data(correlated_data)
        
        # Store raw data for backup and debugging
        storage_manager.store_raw_data(telemetry_data, cost_data)
        
        logging.info("FinOps data collection completed successfully")
        
        # Log summary statistics
        log_summary_stats(telemetry_data, cost_data, correlated_data)
        
    except Exception as e:
        logging.error(f"Error in FinOps data collection: {str(e)}", exc_info=True)
        raise e


def log_summary_stats(telemetry_data: List[Dict], cost_data: List[Dict], correlated_data: List[Dict]) -> None:
    """
    Log summary statistics for monitoring and debugging.
    
    Args:
        telemetry_data: Raw telemetry data
        cost_data: Raw cost data
        correlated_data: Correlated data results
    """
    try:
        # Telemetry stats
        if telemetry_data:
            telemetry_df = pd.DataFrame(telemetry_data)
            unique_users = telemetry_df['deviceId'].nunique() if 'deviceId' in telemetry_df.columns else 0
            unique_stores = telemetry_df['storeNumber'].nunique() if 'storeNumber' in telemetry_df.columns else 0
            total_api_calls = len(telemetry_data)
            
            logging.info(f"Telemetry Summary - Users: {unique_users}, Stores: {unique_stores}, API Calls: {total_api_calls}")
        
        # Cost stats
        if cost_data:
            cost_df = pd.DataFrame(cost_data)
            total_cost = cost_df['Cost'].sum() if 'Cost' in cost_df.columns else 0
            unique_resources = cost_df['ResourceId'].nunique() if 'ResourceId' in cost_df.columns else 0
            
            logging.info(f"Cost Summary - Total Cost: ${total_cost:.2f}, Resources: {unique_resources}")
        
        # Correlation stats
        if correlated_data:
            corr_df = pd.DataFrame(correlated_data)
            allocated_cost = corr_df['AllocatedCost'].sum() if 'AllocatedCost' in corr_df.columns else 0
            
            logging.info(f"Correlation Summary - Allocated Cost: ${allocated_cost:.2f}, Records: {len(correlated_data)}")
            
    except Exception as e:
        logging.warning(f"Error generating summary stats: {str(e)}")


# Function configuration (function.json is generated automatically by Azure Functions)
# Timer trigger runs every 6 minutes: "0 */6 * * * *"