"""
Cost Collector for FinOps Solution

Collects cost data from Azure Cost Management API.
Implements Step 4 of the FinOps solution: Retrieve Cost Data.
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from decimal import Decimal
from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import QueryDefinition, QueryDataset, QueryAggregation, QueryGrouping, QueryTimePeriod
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import pandas as pd
from .config import FinOpsConfig


class CostCollector:
    """
    Collects cost data from Azure Cost Management API.
    
    Retrieves OpenAI-specific cost data with resource-level granularity
    for correlation with telemetry data.
    """
    
    def __init__(self, config: FinOpsConfig, credential: DefaultAzureCredential):
        """
        Initialize cost collector.
        
        Args:
            config: FinOps configuration
            credential: Azure credential for authentication
        """
        self.config = config
        self.credential = credential
        self.logger = logging.getLogger(__name__)
        
        # Initialize Cost Management client
        try:
            self.cost_client = CostManagementClient(credential)
            self.logger.info("Initialized Cost Management client")
        except Exception as e:
            self.logger.error(f"Failed to initialize Cost Management client: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception)
    )
    def collect_cost_data(self) -> List[Dict[str, Any]]:
        """
        Collect cost data from Azure Cost Management API.
        
        Returns:
            List of cost records with resource-level details
        """
        self.logger.info("Starting cost data collection")
        
        try:
            # Calculate time range
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=self.config.lookback_hours)
            
            # Create query definition
            query_def = self._create_cost_query(start_time, end_time)
            
            self.logger.debug(f"Executing cost query for period: {start_time} to {end_time}")
            
            # Execute cost query
            result = self.cost_client.query.usage(
                scope=self.config.cost_management_scope,
                parameters=query_def
            )
            
            # Process results
            cost_data = self._process_cost_results(result)
            
            self.logger.info(f"Collected {len(cost_data)} cost records")
            return cost_data
            
        except Exception as e:
            self.logger.error(f"Error collecting cost data: {e}", exc_info=True)
            return []
    
    def _create_cost_query(self, start_time: datetime, end_time: datetime) -> QueryDefinition:
        """
        Create cost management query definition.
        
        Args:
            start_time: Query start time
            end_time: Query end time
            
        Returns:
            QueryDefinition for cost management API
        """
        # Define aggregations
        aggregations = {
            "totalCost": QueryAggregation(name="PreTaxCost", function="Sum"),
            "usageQuantity": QueryAggregation(name="UsageQuantity", function="Sum")
        }
        
        # Define groupings for detailed breakdown
        groupings = [
            QueryGrouping(type="Dimension", name="ResourceId"),
            QueryGrouping(type="Dimension", name="ResourceType"),
            QueryGrouping(type="Dimension", name="ServiceName"),
            QueryGrouping(type="Dimension", name="MeterName"),
            QueryGrouping(type="Dimension", name="UsageDate")
        ]
        
        # Create dataset with filters for OpenAI resources
        dataset = QueryDataset(
            granularity="Daily",
            aggregation=aggregations,
            grouping=groupings,
            filter={
                "and": [
                    {
                        "dimensions": {
                            "name": "ServiceName",
                            "operator": "In",
                            "values": ["Azure OpenAI", "Cognitive Services"]
                        }
                    },
                    {
                        "dimensions": {
                            "name": "MeterName",
                            "operator": "In", 
                            "values": [
                                "Standard Input Tokens",
                                "Standard Output Tokens", 
                                "PTU Hours",
                                "Fine-tuning Training Hours",
                                "Fine-tuning Inference",
                                "GPT-4 Input Tokens",
                                "GPT-4 Output Tokens",
                                "GPT-4o Input Tokens",
                                "GPT-4o Output Tokens",
                                "GPT-4 Turbo Input Tokens",
                                "GPT-4 Turbo Output Tokens",
                                "GPT-3.5-Turbo Input Tokens",
                                "GPT-3.5-Turbo Output Tokens",
                                "GPT-5 Input Tokens",
                                "GPT-5 Output Tokens",
                                "GPT-5-Turbo Input Tokens",
                                "GPT-5-Turbo Output Tokens",
                                "GPT-5-Preview Input Tokens",
                                "GPT-5-Preview Output Tokens"
                            ]
                        }
                    }
                ]
            }
        )
        
        # Create time period
        time_period = QueryTimePeriod(
            from_property=start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            to=end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        
        return QueryDefinition(
            type="Usage",
            timeframe="Custom",
            time_period=time_period,
            dataset=dataset
        )
    
    def _process_cost_results(self, result) -> List[Dict[str, Any]]:
        """
        Process cost management query results.
        
        Args:
            result: Cost management query result
            
        Returns:
            List of processed cost records
        """
        cost_data = []
        
        if not result or not hasattr(result, 'rows') or not result.rows:
            self.logger.warning("No cost data returned from query")
            return cost_data
        
        # Get column names
        columns = [col.name for col in result.columns] if result.columns else []
        
        for row in result.rows:
            try:
                # Create record dictionary
                record = {}
                for i, value in enumerate(row):
                    if i < len(columns):
                        record[columns[i]] = value
                
                # Process and normalize the record
                processed_record = self._normalize_cost_record(record)
                cost_data.append(processed_record)
                
            except Exception as e:
                self.logger.warning(f"Error processing cost record: {e}")
                continue
        
        return cost_data
    
    def _normalize_cost_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and enrich cost record.
        
        Args:
            record: Raw cost record
            
        Returns:
            Normalized cost record
        """
        # Extract key fields with defaults
        resource_id = record.get('ResourceId', '')
        cost = float(record.get('totalCost', 0))
        usage_quantity = float(record.get('usageQuantity', 0))
        usage_date = record.get('UsageDate', datetime.now(timezone.utc).date())
        
        # Normalize resource information
        normalized = {
            'ResourceId': resource_id,
            'ResourceType': record.get('ResourceType', 'Unknown'),
            'ServiceName': record.get('ServiceName', 'Azure OpenAI'),
            'MeterName': record.get('MeterName', 'Unknown'),
            'UsageDate': usage_date,
            'Cost': cost,
            'UsageQuantity': usage_quantity,
            'Currency': record.get('Currency', 'USD'),
            'BillingPeriod': record.get('BillingPeriod', ''),
            'SubscriptionId': self._extract_subscription_from_resource_id(resource_id),
            'ResourceGroup': self._extract_resource_group_from_resource_id(resource_id),
            'ResourceName': self._extract_resource_name_from_resource_id(resource_id)
        }
        
        # Add cost categorization
        normalized.update(self._categorize_cost(normalized))
        
        return normalized
    
    def _extract_subscription_from_resource_id(self, resource_id: str) -> str:
        """Extract subscription ID from resource ID."""
        try:
            parts = resource_id.split('/')
            sub_index = parts.index('subscriptions')
            return parts[sub_index + 1] if sub_index + 1 < len(parts) else ''
        except (ValueError, IndexError):
            return ''
    
    def _extract_resource_group_from_resource_id(self, resource_id: str) -> str:
        """Extract resource group from resource ID."""
        try:
            parts = resource_id.split('/')
            rg_index = parts.index('resourceGroups')
            return parts[rg_index + 1] if rg_index + 1 < len(parts) else ''
        except (ValueError, IndexError):
            return ''
    
    def _extract_resource_name_from_resource_id(self, resource_id: str) -> str:
        """Extract resource name from resource ID."""
        try:
            # Resource name is typically the last part of the resource ID
            return resource_id.split('/')[-1] if resource_id else ''
        except (ValueError, IndexError):
            return ''
    
    def _categorize_cost(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Categorize cost record for better analysis.
        
        Args:
            record: Cost record
            
        Returns:
            Additional categorization fields
        """
        meter_name = record.get('MeterName', '').lower()
        
        # Determine cost type
        cost_type = 'Unknown'
        token_type = None
        
        if 'input' in meter_name and 'token' in meter_name:
            cost_type = 'Input Tokens'
            token_type = 'Input'
        elif 'output' in meter_name and 'token' in meter_name:
            cost_type = 'Output Tokens'
            token_type = 'Output'
        elif 'ptu' in meter_name or 'provisioned' in meter_name:
            cost_type = 'Provisioned Throughput'
        elif 'fine-tuning' in meter_name:
            cost_type = 'Fine-tuning'
        elif 'training' in meter_name:
            cost_type = 'Training'
        
        # Determine model family (check most specific first)
        model_family = 'Unknown'
        if 'gpt-5' in meter_name:
            if 'preview' in meter_name:
                model_family = 'GPT-5-Preview'
            elif 'turbo' in meter_name:
                model_family = 'GPT-5-Turbo'
            else:
                model_family = 'GPT-5'
        elif 'gpt-4' in meter_name:
            if 'gpt-4o' in meter_name:
                model_family = 'GPT-4o'
            elif 'turbo' in meter_name:
                model_family = 'GPT-4-Turbo'
            else:
                model_family = 'GPT-4'
        elif 'gpt-3.5' in meter_name or 'gpt-35' in meter_name:
            model_family = 'GPT-3.5-Turbo'
        elif 'davinci' in meter_name:
            model_family = 'Davinci'
        elif 'curie' in meter_name:
            model_family = 'Curie'
        elif 'ada' in meter_name:
            model_family = 'Ada'
        elif 'babbage' in meter_name:
            model_family = 'Babbage'
        
        return {
            'CostType': cost_type,
            'TokenType': token_type,
            'ModelFamily': model_family,
            'IsTokenBased': token_type is not None,
            'CostPerUnit': record['Cost'] / record['UsageQuantity'] if record['UsageQuantity'] > 0 else 0
        }
    
    def get_cost_summary(self, cost_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics for cost data.
        
        Args:
            cost_data: List of cost records
            
        Returns:
            Summary statistics
        """
        if not cost_data:
            return {
                'total_cost': 0,
                'total_usage': 0,
                'unique_resources': 0,
                'cost_by_type': {},
                'cost_by_model': {},
                'avg_cost_per_request': 0
            }
        
        df = pd.DataFrame(cost_data)
        
        summary = {
            'total_cost': df['Cost'].sum(),
            'total_usage': df['UsageQuantity'].sum(),
            'unique_resources': df['ResourceId'].nunique(),
            'cost_by_type': df.groupby('CostType')['Cost'].sum().to_dict(),
            'cost_by_model': df.groupby('ModelFamily')['Cost'].sum().to_dict(),
            'date_range': {
                'start': df['UsageDate'].min(),
                'end': df['UsageDate'].max()
            }
        }
        
        return summary
    
    def filter_costs_by_resources(self, cost_data: List[Dict[str, Any]], resource_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Filter cost data to specific resources.
        
        Args:
            cost_data: List of cost records
            resource_ids: List of resource IDs to filter by
            
        Returns:
            Filtered cost data
        """
        if not resource_ids:
            return cost_data
        
        filtered_data = [
            record for record in cost_data 
            if record.get('ResourceId', '') in resource_ids
        ]
        
        self.logger.info(f"Filtered {len(cost_data)} cost records to {len(filtered_data)} for {len(resource_ids)} resources")
        return filtered_data