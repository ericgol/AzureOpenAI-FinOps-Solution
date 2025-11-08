"""
Telemetry Collector for FinOps Solution

Collects APIM and Application Insights telemetry data from Azure Log Analytics.
Implements Step 3 of the FinOps solution: Fetch Telemetry from Log Analytics.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from azure.core.exceptions import HttpResponseError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import pandas as pd
from .config import FinOpsConfig


class TelemetryCollector:
    """
    Collects telemetry data from Azure Log Analytics workspace.
    
    Retrieves APIM gateway logs and Application Insights request data
    with custom user and store identifiers for cost allocation.
    """
    
    def __init__(self, config: FinOpsConfig, credential: DefaultAzureCredential):
        """
        Initialize telemetry collector.
        
        Args:
            config: FinOps configuration
            credential: Azure credential for authentication
        """
        self.config = config
        self.credential = credential
        self.logger = logging.getLogger(__name__)
        
        # Initialize Log Analytics client
        try:
            self.logs_client = LogsQueryClient(credential)
            self.logger.info("Initialized Log Analytics client")
        except Exception as e:
            self.logger.error(f"Failed to initialize Log Analytics client: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpResponseError)
    )
    def collect_apim_logs(self) -> List[Dict[str, Any]]:
        """
        Collect APIM gateway logs from Log Analytics.
        
        Returns:
            List of APIM telemetry records
        """
        self.logger.info("Starting APIM logs collection")
        
        try:
            # Get KQL query for APIM logs
            queries = self.config.get_kql_queries()
            query = queries["apim_logs"].format(lookback_hours=self.config.lookback_hours)
            
            self.logger.debug(f"Executing KQL query: {query}")
            
            # Execute query
            response = self.logs_client.query_workspace(
                workspace_id=self.config.log_analytics_workspace_id,
                query=query,
                timespan=timedelta(hours=self.config.lookback_hours)
            )
            
            if response.status == LogsQueryStatus.PARTIAL:
                self.logger.warning("Query returned partial results")
                # Log partial failure details
                if hasattr(response, 'partial_error'):
                    self.logger.warning(f"Partial error: {response.partial_error}")
            
            elif response.status == LogsQueryStatus.FAILURE:
                self.logger.error("Query failed completely")
                if hasattr(response, 'partial_error'):
                    self.logger.error(f"Query error: {response.partial_error}")
                return []
            
            # Convert to list of dictionaries
            telemetry_data = []
            if response.tables and len(response.tables) > 0:
                table = response.tables[0]
                
                # Convert table data to list of dictionaries
                # Handle both string columns and column objects
                columns = [col if isinstance(col, str) else col.name for col in table.columns]
                
                for row in table.rows:
                    record = {}
                    for i, value in enumerate(row):
                        record[columns[i]] = value
                    
                    # Post-process the record
                    processed_record = self._process_apim_record(record)
                    telemetry_data.append(processed_record)
                
                self.logger.info(f"Collected {len(telemetry_data)} APIM telemetry records")
            else:
                self.logger.warning("No APIM data found in specified time range")
            
            return telemetry_data
            
        except HttpResponseError as e:
            self.logger.error(f"Log Analytics query error: {e}")
            # Check if it's a permissions error
            if "InsufficientAccessError" in str(e):
                self.logger.error(
                    "The function's managed identity lacks permissions to query Log Analytics. "
                    "Grant 'Log Analytics Reader' role to the function app's managed identity."
                )
            raise
        except Exception as e:
            self.logger.error(f"Error collecting APIM logs: {e}", exc_info=True)
            return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpResponseError)
    )
    def collect_app_insights_traces(self) -> List[Dict[str, Any]]:
        """
        Collect Application Insights traces with FinOps telemetry data.
        
        Returns:
            List of Application Insights trace records with parsed FinOps data
        """
        self.logger.info("Starting Application Insights traces collection")
        
        try:
            # Get KQL query for Application Insights traces
            queries = self.config.get_kql_queries()
            query = queries["app_insights_traces"].format(lookback_hours=self.config.lookback_hours)
            
            self.logger.debug(f"Executing App Insights traces KQL query: {query}")
            
            # Execute query
            response = self.logs_client.query_workspace(
                workspace_id=self.config.log_analytics_workspace_id,
                query=query,
                timespan=timedelta(hours=self.config.lookback_hours)
            )
            
            if response.status == LogsQueryStatus.PARTIAL:
                self.logger.warning("App Insights traces query returned partial results")
            elif response.status == LogsQueryStatus.FAILURE:
                self.logger.error("App Insights traces query failed completely")
                return []
            
            # Convert to list of dictionaries
            telemetry_data = []
            if response.tables and len(response.tables) > 0:
                table = response.tables[0]
                # Handle both string columns and column objects
                columns = [col if isinstance(col, str) else col.name for col in table.columns]
                
                for row in table.rows:
                    record = {}
                    for i, value in enumerate(row):
                        record[columns[i]] = value
                    
                    # Post-process the record
                    processed_record = self._process_apim_record(record)
                    telemetry_data.append(processed_record)
                
                self.logger.info(f"Collected {len(telemetry_data)} App Insights trace records")
            else:
                self.logger.info("No Application Insights traces found in specified time range")
            
            return telemetry_data
            
        except HttpResponseError as e:
            self.logger.error(f"Application Insights traces query error: {e}")
            if "InsufficientAccessError" in str(e):
                self.logger.error(
                    "The function's managed identity lacks permissions to query Log Analytics."
                )
            return []
        except Exception as e:
            self.logger.error(f"Error collecting App Insights traces: {e}", exc_info=True)
            return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpResponseError)
    )
    def collect_app_insights_data(self) -> List[Dict[str, Any]]:
        """
        Collect Application Insights request data.
        
        Returns:
            List of Application Insights telemetry records
        """
        self.logger.info("Starting Application Insights data collection")
        
        try:
            # Get KQL query for Application Insights
            queries = self.config.get_kql_queries()
            query = queries["app_insights_requests"].format(lookback_hours=self.config.lookback_hours)
            
            self.logger.debug(f"Executing App Insights KQL query: {query}")
            
            # Execute query
            response = self.logs_client.query_workspace(
                workspace_id=self.config.log_analytics_workspace_id,
                query=query,
                timespan=timedelta(hours=self.config.lookback_hours)
            )
            
            if response.status == LogsQueryStatus.PARTIAL:
                self.logger.warning("App Insights query returned partial results")
            elif response.status == LogsQueryStatus.FAILURE:
                self.logger.error("App Insights query failed completely")
                return []
            
            # Convert to list of dictionaries
            telemetry_data = []
            if response.tables and len(response.tables) > 0:
                table = response.tables[0]
                # Handle both string columns and column objects
                columns = [col if isinstance(col, str) else col.name for col in table.columns]
                
                for row in table.rows:
                    record = {}
                    for i, value in enumerate(row):
                        record[columns[i]] = value
                    
                    # Post-process the record
                    processed_record = self._process_app_insights_record(record)
                    telemetry_data.append(processed_record)
                
                self.logger.info(f"Collected {len(telemetry_data)} App Insights telemetry records")
            else:
                self.logger.info("No Application Insights data found in specified time range")
            
            return telemetry_data
            
        except HttpResponseError as e:
            self.logger.error(f"Application Insights query error: {e}")
            if "InsufficientAccessError" in str(e):
                self.logger.error(
                    "The function's managed identity lacks permissions to query Log Analytics."
                )
            return []
        except Exception as e:
            self.logger.error(f"Error collecting App Insights data: {e}", exc_info=True)
            return []
    
    def collect_combined_telemetry(self) -> List[Dict[str, Any]]:
        """
        Collect telemetry from both APIM and Application Insights.
        
        Returns:
            Combined list of telemetry records
        """
        self.logger.info("Collecting combined telemetry data")
        
        # Collect from both sources
        apim_data = self.collect_apim_logs()
        app_insights_data = self.collect_app_insights_data()
        
        # Combine and deduplicate
        combined_data = apim_data + app_insights_data
        
        # Remove duplicates based on RequestId and TimeGenerated
        if combined_data:
            df = pd.DataFrame(combined_data)
            
            # Remove duplicates
            df_dedup = df.drop_duplicates(subset=['RequestId', 'TimeGenerated'], keep='first')
            
            combined_data = df_dedup.to_dict('records')
            
            self.logger.info(f"Combined telemetry: {len(apim_data)} APIM + {len(app_insights_data)} App Insights = {len(combined_data)} total (after deduplication)")
        
        return combined_data
    
    def _process_apim_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and normalize APIM record.
        
        Args:
            record: Raw APIM record
            
        Returns:
            Processed record
        """
        processed = {
            'Source': 'APIM',
            'TimeGenerated': record.get('TimeGenerated'),
            'RequestId': record.get('RequestId', ''),
            'deviceId': record.get('deviceId', 'unknown'),
            'storeNumber': record.get('storeNumber', 'unknown'),
            'ApiName': record.get('ApiName', ''),
            'Method': record.get('Method', ''),
            'Url': record.get('Url', ''),
            'StatusCode': int(record.get('StatusCode', 0)),
            'ResponseTime': int(record.get('ResponseTime', 0)),
            'TokensUsed': int(record.get('TokensUsed', 0)) if record.get('TokensUsed') else 0,
            'ResourceId': record.get('ResourceId', '')
        }
        
        # Ensure user and store IDs are not empty
        if not processed['deviceId'] or processed['deviceId'] in ['', 'null', 'None']:
            processed['deviceId'] = 'unknown'
        if not processed['storeNumber'] or processed['storeNumber'] in ['', 'null', 'None']:
            processed['storeNumber'] = 'unknown'
        
        return processed
    
    def _process_app_insights_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and normalize Application Insights record.
        
        Args:
            record: Raw Application Insights record
            
        Returns:
            Processed record
        """
        processed = {
            'Source': 'ApplicationInsights',
            'TimeGenerated': record.get('TimeGenerated'),
            'RequestId': record.get('RequestId', ''),
            'deviceId': record.get('deviceId', 'unknown'),
            'storeNumber': record.get('storeNumber', 'unknown'),
            'ApiName': record.get('ApiName', ''),
            'Method': record.get('Method', 'POST'),
            'Url': record.get('Url', ''),
            'StatusCode': int(record.get('StatusCode', 0)),
            'ResponseTime': float(record.get('ResponseTime', 0)),
            'TokensUsed': int(record.get('TokensUsed', 0)) if record.get('TokensUsed') else 0,
            'ResourceId': record.get('ResourceId', '')
        }
        
        # Ensure user and store IDs are not empty
        if not processed['deviceId'] or processed['deviceId'] in ['', 'null', 'None']:
            processed['deviceId'] = 'unknown'
        if not processed['storeNumber'] or processed['storeNumber'] in ['', 'null', 'None']:
            processed['storeNumber'] = 'unknown'
        
        return processed
    
    def get_telemetry_summary(self, telemetry_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics for telemetry data.
        
        Args:
            telemetry_data: List of telemetry records
            
        Returns:
            Summary statistics
        """
        if not telemetry_data:
            return {
                'total_records': 0,
                'unique_users': 0,
                'unique_stores': 0,
                'total_api_calls': 0,
                'avg_response_time': 0,
                'total_tokens': 0,
                'success_rate': 0
            }
        
        df = pd.DataFrame(telemetry_data)
        
        summary = {
            'total_records': len(telemetry_data),
            'unique_users': df['deviceId'].nunique(),
            'unique_stores': df['storeNumber'].nunique(),
            'total_api_calls': len(telemetry_data),
            'avg_response_time': df['ResponseTime'].mean(),
            'total_tokens': df['TokensUsed'].sum(),
            'success_rate': (df['StatusCode'] < 400).mean() * 100,
            'time_range': {
                'start': df['TimeGenerated'].min(),
                'end': df['TimeGenerated'].max()
            }
        }
        
        return summary