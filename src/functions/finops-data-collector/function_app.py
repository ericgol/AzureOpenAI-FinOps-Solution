"""
FinOps Data Collection Function App

Azure Function using Python v2 programming model to collect and correlate:
1. APIM telemetry from Log Analytics
2. Cost data from Azure Cost Management API
3. Correlates the data and stores results in Azure Storage

This function runs every 6 minutes on a timer schedule.

Author: FinOps Team
"""

import logging
import azure.functions as func
from datetime import datetime, timezone
from typing import Dict, List
import pandas as pd
from azure.identity import DefaultAzureCredential
from shared.config import FinOpsConfig
from shared.telemetry_collector import TelemetryCollector
from shared.cost_collector import CostCollector
from shared.data_correlator import DataCorrelator
from shared.storage_manager import StorageManager

# Initialize function app
app = func.FunctionApp()


@app.function_name(name="finops_timer_trigger")
@app.schedule(
    schedule="0 */6 * * * *",  # Run every 6 minutes
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=True
)
def finops_timer_trigger(mytimer: func.TimerRequest) -> None:
    """
    Timer-triggered function that collects and correlates FinOps data.
    
    Schedule: Every 6 minutes (0 */6 * * * *)
    
    Args:
        mytimer: Timer trigger context with schedule information
    """
    # Use timezone-aware datetime (Python 3.12+ best practice)
    utc_timestamp = datetime.now(timezone.utc).isoformat()
    
    logging.info(f'FinOps data collection started at: {utc_timestamp}')
    
    # Log timer schedule information if available
    if mytimer.past_due:
        logging.warning('Timer trigger is running late!')
    
    # Initialize configuration
    config = FinOpsConfig()
    
    # Initialize Azure credential with managed identity
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
        raise


def log_summary_stats(
    telemetry_data: List[Dict], 
    cost_data: List[Dict], 
    correlated_data: List[Dict]
) -> None:
    """
    Log summary statistics for monitoring and debugging.
    
    Args:
        telemetry_data: Raw telemetry data from Log Analytics
        cost_data: Raw cost data from Cost Management API
        correlated_data: Correlated data results
    """
    try:
        # Telemetry stats
        if telemetry_data:
            telemetry_df = pd.DataFrame(telemetry_data)
            unique_users = telemetry_df['deviceId'].nunique() if 'deviceId' in telemetry_df.columns else 0
            unique_stores = telemetry_df['storeNumber'].nunique() if 'storeNumber' in telemetry_df.columns else 0
            total_api_calls = len(telemetry_data)
            
            logging.info(
                f"Telemetry Summary - Users: {unique_users}, "
                f"Stores: {unique_stores}, API Calls: {total_api_calls}"
            )
        
        # Cost stats
        if cost_data:
            cost_df = pd.DataFrame(cost_data)
            total_cost = cost_df['Cost'].sum() if 'Cost' in cost_df.columns else 0
            unique_resources = cost_df['ResourceId'].nunique() if 'ResourceId' in cost_df.columns else 0
            
            logging.info(
                f"Cost Summary - Total Cost: ${total_cost:.2f}, "
                f"Resources: {unique_resources}"
            )
        
        # Correlation stats
        if correlated_data:
            corr_df = pd.DataFrame(correlated_data)
            allocated_cost = corr_df['AllocatedCost'].sum() if 'AllocatedCost' in corr_df.columns else 0
            
            logging.info(
                f"Correlation Summary - Allocated Cost: ${allocated_cost:.2f}, "
                f"Records: {len(correlated_data)}"
            )
            
    except Exception as e:
        logging.warning(f"Error generating summary stats: {str(e)}")
