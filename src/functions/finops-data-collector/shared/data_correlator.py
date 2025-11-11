"""
Data Correlator for FinOps Solution

Correlates telemetry data with cost data using device and store-based allocation.
Implements Step 5 of the FinOps solution: Data Correlation and Cost Allocation.

This correlator focuses on deviceId (devices in stores used by shift workers) 
and storeNumber for cost attribution rather than individual user tracking.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from .config import FinOpsConfig


class AllocationMethod(Enum):
    """Cost allocation methods for device/store attribution."""
    PROPORTIONAL = "proportional"
    EQUAL = "equal"
    USAGE_BASED = "usage-based"
    TOKEN_BASED = "token-based"
    TIME_WEIGHTED = "time-weighted"


@dataclass
class CorrelationSettings:
    """Settings for data correlation."""
    allocation_method: AllocationMethod
    time_window_minutes: int = 60
    enable_device_attribution: bool = True
    enable_store_attribution: bool = True
    min_confidence_threshold: float = 0.7
    handle_unknown_devices: bool = True
    cost_distribution_strategy: str = "proportional"


class DataCorrelator:
    """
    Correlates telemetry data with cost data for accurate cost allocation to devices and stores.
    
    Supports multiple allocation strategies focusing on:
    - deviceId: Physical devices in stores used by shift workers
    - storeNumber: Store locations for geographical cost analysis
    """
    
    def __init__(self, config: FinOpsConfig):
        """
        Initialize data correlator.
        
        Args:
            config: FinOps configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Set up correlation settings
        self.settings = CorrelationSettings(
            allocation_method=AllocationMethod(config.default_allocation_method),
            enable_device_attribution=config.enable_user_mapping,  # Reuse for device mapping
            enable_store_attribution=config.enable_store_mapping
        )
    
    def correlate_data(self, telemetry_data: List[Dict[str, Any]], cost_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Main correlation function that combines telemetry and cost data.
        
        Args:
            telemetry_data: List of telemetry records with deviceId and storeNumber
            cost_data: List of cost records
            
        Returns:
            List of correlated records with allocated costs per device/store
        """
        self.logger.info(f"Starting device/store correlation with {len(telemetry_data)} telemetry and {len(cost_data)} cost records")
        
        if not telemetry_data or not cost_data:
            self.logger.warning("No data to correlate")
            return []
        
        # Convert to DataFrames for easier manipulation
        telemetry_df = pd.DataFrame(telemetry_data)
        cost_df = pd.DataFrame(cost_data)
        
        # Preprocess data
        telemetry_df = self._preprocess_telemetry_data(telemetry_df)
        cost_df = self._preprocess_cost_data(cost_df)
        
        # Perform time-based correlation
        correlated_records = self._correlate_by_time_window(telemetry_df, cost_df)
        
        # Apply cost allocation method
        allocated_records = self._allocate_costs(correlated_records)
        
        # Post-process and enrich results
        final_records = self._enrich_correlated_data(allocated_records)
        
        self.logger.info(f"Generated {len(final_records)} correlated device/store records")
        return final_records
    
    def _preprocess_telemetry_data(self, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess telemetry data for device/store correlation.
        
        Args:
            telemetry_df: Telemetry DataFrame
            
        Returns:
            Preprocessed DataFrame
        """
        self.logger.debug("Preprocessing telemetry data for device/store correlation")
        
        # Ensure timestamps are datetime objects with UTC timezone
        if 'TimeGenerated' in telemetry_df.columns:
            telemetry_df['TimeGenerated'] = pd.to_datetime(telemetry_df['TimeGenerated'], utc=True)
        
        # Clean and normalize device/store identifiers
        telemetry_df['deviceId'] = telemetry_df['deviceId'].fillna('unknown').astype(str)
        telemetry_df['storeNumber'] = telemetry_df['storeNumber'].fillna('unknown').astype(str)
        
        # Create device-store composite key for easier tracking
        telemetry_df['DeviceStoreKey'] = telemetry_df['deviceId'] + '_' + telemetry_df['storeNumber']
        
        # Add time-based grouping columns
        telemetry_df['TimeWindow'] = telemetry_df['TimeGenerated'].dt.floor(f'{self.settings.time_window_minutes}min')
        telemetry_df['HourOfDay'] = telemetry_df['TimeGenerated'].dt.hour
        telemetry_df['DayOfWeek'] = telemetry_df['TimeGenerated'].dt.day_name()
        
        # Ensure numeric fields
        numeric_fields = ['StatusCode', 'ResponseTime', 'TokensUsed']
        for field in numeric_fields:
            if field in telemetry_df.columns:
                telemetry_df[field] = pd.to_numeric(telemetry_df[field], errors='coerce').fillna(0)
        
        # Normalize ResourceId for correlation
        if 'ResourceId' in telemetry_df.columns:
            telemetry_df['ResourceId'] = telemetry_df['ResourceId'].apply(self._normalize_resource_id)
        
        return telemetry_df
    
    def _preprocess_cost_data(self, cost_df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess cost data for correlation.
        
        Args:
            cost_df: Cost DataFrame
            
        Returns:
            Preprocessed DataFrame
        """
        self.logger.debug("Preprocessing cost data")
        
        # Ensure timestamps are datetime objects with UTC timezone
        if 'UsageDate' in cost_df.columns:
            cost_df['UsageDate'] = pd.to_datetime(cost_df['UsageDate'], utc=True)
            # Create hourly time windows for better correlation
            cost_df['TimeWindow'] = cost_df['UsageDate'].dt.floor(f'{self.settings.time_window_minutes}min')
        
        # Ensure numeric fields
        numeric_fields = ['Cost', 'UsageQuantity', 'CostPerUnit']
        for field in numeric_fields:
            if field in cost_df.columns:
                cost_df[field] = pd.to_numeric(cost_df[field], errors='coerce').fillna(0)
        
        # Normalize ResourceId for correlation
        if 'ResourceId' in cost_df.columns:
            cost_df['ResourceId'] = cost_df['ResourceId'].apply(self._normalize_resource_id)
        
        return cost_df
    
    def _normalize_resource_id(self, resource_id: str) -> str:
        """
        Normalize ResourceId to a consistent format for correlation.
        
        Handles both full Azure resource IDs and OpenAI URLs.
        Extracts the resource name as the common identifier.
        
        Args:
            resource_id: Resource identifier (Azure resource ID or URL)
            
        Returns:
            Normalized resource identifier
        """
        if not resource_id or resource_id == 'unknown':
            return 'unknown'
        
        resource_id = str(resource_id).lower().strip()
        
        # If it's a full Azure resource ID, extract the resource name (last segment)
        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{name}
        if resource_id.startswith('/subscriptions/'):
            parts = resource_id.split('/')
            if len(parts) >= 2:
                # Return the last part which is the resource name
                return parts[-1]
        
        # If it's a URL, extract the hostname's first segment (resource name)
        # Format: https://{resource-name}.openai.azure.com/...
        if resource_id.startswith('http'):
            try:
                from urllib.parse import urlparse
                parsed = urlparse(resource_id)
                hostname = parsed.hostname or ''
                # Extract resource name from hostname (first part before first dot)
                resource_name = hostname.split('.')[0] if hostname else 'unknown'
                return resource_name
            except Exception:
                pass
        
        # Return as-is if it's already a simple identifier
        return resource_id
    
    def _correlate_by_time_window(self, telemetry_df: pd.DataFrame, cost_df: pd.DataFrame) -> pd.DataFrame:
        """
        Correlate telemetry and cost data within time windows, grouped by device/store combinations.
        
        Args:
            telemetry_df: Preprocessed telemetry DataFrame
            cost_df: Preprocessed cost DataFrame
            
        Returns:
            DataFrame with correlated records
        """
        self.logger.debug("Correlating data by time windows for device/store combinations")
        
        # Group telemetry data by time windows, resources, and device/store combinations
        telemetry_grouped = telemetry_df.groupby(['TimeWindow', 'ResourceId', 'deviceId', 'storeNumber']).agg({
            'TokensUsed': 'sum',
            'StatusCode': 'count',  # API call count
            'ResponseTime': 'mean',
            'DeviceStoreKey': 'first'
        }).reset_index()
        
        # Rename columns for clarity
        telemetry_grouped.columns = ['TimeWindow', 'ResourceId', 'DeviceId', 'StoreNumber', 'TotalTokens', 'ApiCalls', 'AvgResponseTime', 'DeviceStoreKey']
        
        # Debug logging for correlation
        self.logger.info(f"Telemetry: {len(telemetry_grouped)} grouped records")
        if len(telemetry_grouped) > 0:
            self.logger.debug(f"Telemetry ResourceIds: {telemetry_grouped['ResourceId'].unique().tolist()}")
            self.logger.debug(f"Telemetry TimeWindows: {telemetry_grouped['TimeWindow'].min()} to {telemetry_grouped['TimeWindow'].max()}")
        
        self.logger.info(f"Cost data: {len(cost_df)} records")
        if len(cost_df) > 0:
            self.logger.debug(f"Cost ResourceIds: {cost_df['ResourceId'].unique().tolist()}")
            self.logger.debug(f"Cost TimeWindows: {cost_df['TimeWindow'].min()} to {cost_df['TimeWindow'].max()}")
            self.logger.info(f"Total cost in data: ${cost_df['Cost'].sum():.2f}")
        
        # Merge with cost data on time window and resource
        merged_df = pd.merge(
            telemetry_grouped,
            cost_df,
            on=['TimeWindow', 'ResourceId'],
            how='inner'
        )
        
        self.logger.info(f"Found {len(merged_df)} time window correlations for device/store combinations")
        if len(merged_df) == 0 and len(telemetry_grouped) > 0 and len(cost_df) > 0:
            self.logger.warning("No correlations found despite having both telemetry and cost data. Check ResourceId and TimeWindow alignment.")
        
        return merged_df
    
    def _allocate_costs(self, correlated_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Allocate costs to device/store combinations based on the configured method.
        
        Args:
            correlated_df: DataFrame with correlated records
            
        Returns:
            List of records with allocated costs per device/store
        """
        self.logger.debug(f"Allocating costs to devices/stores using method: {self.settings.allocation_method.value}")
        
        allocated_records = []
        
        # Group by time window and resource to handle multiple device/store combinations
        for (time_window, resource_id), group in correlated_df.groupby(['TimeWindow', 'ResourceId']):
            total_cost = group['Cost'].iloc[0]  # Cost is the same for all records in this group
            total_tokens_across_devices = group['TotalTokens'].sum()
            total_api_calls_across_devices = group['ApiCalls'].sum()
            
            # Get resource-level information (same for all records in group)
            resource_info = group.iloc[0]
            
            for _, row in group.iterrows():
                device_id = row['DeviceId']
                store_number = row['StoreNumber']
                device_tokens = row['TotalTokens']
                device_api_calls = row['ApiCalls']
                
                # Calculate allocated cost for this device/store combination
                allocated_cost = self._calculate_device_allocated_cost(
                    total_cost, 
                    total_tokens_across_devices, 
                    total_api_calls_across_devices,
                    device_tokens, 
                    device_api_calls,
                    len(group)  # Number of device/store combinations in this time window
                )
                
                # Create allocated record
                allocated_record = {
                    'TimeWindow': time_window,
                    'ResourceId': resource_id,
                    'ResourceName': resource_info.get('ResourceName', ''),
                    'ResourceGroup': resource_info.get('ResourceGroup', ''),
                    'DeviceId': device_id,
                    'StoreNumber': store_number,
                    'DeviceStoreKey': row['DeviceStoreKey'],
                    'AllocatedCost': allocated_cost,
                    'TotalCost': total_cost,
                    'AllocationMethod': self.settings.allocation_method.value,
                    'TokensUsed': device_tokens,
                    'ApiCalls': device_api_calls,
                    'AvgResponseTime': row['AvgResponseTime'],
                    'CostType': resource_info.get('CostType', 'Unknown'),
                    'ModelFamily': resource_info.get('ModelFamily', 'Unknown'),
                    'MeterName': resource_info.get('MeterName', ''),
                    'Currency': resource_info.get('Currency', 'USD'),
                    'TokenShare': device_tokens / total_tokens_across_devices if total_tokens_across_devices > 0 else 0,
                    'ApiCallShare': device_api_calls / total_api_calls_across_devices if total_api_calls_across_devices > 0 else 0
                }
                
                allocated_records.append(allocated_record)
        
        return allocated_records
    
    def _calculate_device_allocated_cost(self, total_cost: float, total_tokens: int, total_api_calls: int,
                                       device_tokens: int, device_api_calls: int, device_count: int) -> float:
        """
        Calculate allocated cost for a specific device/store combination.
        
        Args:
            total_cost: Total cost to allocate
            total_tokens: Total tokens used across all devices
            total_api_calls: Total API calls across all devices
            device_tokens: Tokens used by this specific device
            device_api_calls: API calls made by this specific device
            device_count: Number of devices in this time window
            
        Returns:
            Allocated cost amount for this device
        """
        if total_cost <= 0:
            return 0.0
        
        if self.settings.allocation_method == AllocationMethod.EQUAL:
            # Equal distribution across all devices
            return total_cost / device_count if device_count > 0 else 0.0
        
        elif self.settings.allocation_method == AllocationMethod.PROPORTIONAL or self.settings.allocation_method == AllocationMethod.TOKEN_BASED:
            # Allocate based on token usage proportion
            if total_tokens > 0 and device_tokens > 0:
                return (device_tokens / total_tokens) * total_cost
            else:
                # Fall back to equal allocation if no tokens
                return total_cost / device_count if device_count > 0 else 0.0
        
        elif self.settings.allocation_method == AllocationMethod.USAGE_BASED:
            # Based on API call frequency
            if total_api_calls > 0 and device_api_calls > 0:
                return (device_api_calls / total_api_calls) * total_cost
            else:
                # Fall back to equal allocation if no API calls
                return total_cost / device_count if device_count > 0 else 0.0
        
        else:
            # Default to proportional allocation
            if total_tokens > 0 and device_tokens > 0:
                return (device_tokens / total_tokens) * total_cost
            else:
                return total_cost / device_count if device_count > 0 else 0.0
    
    def _enrich_correlated_data(self, allocated_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich correlated data with additional device/store metadata and analytics.
        
        Args:
            allocated_records: List of allocated records
            
        Returns:
            Enriched records
        """
        self.logger.debug("Enriching correlated device/store data")
        
        for record in allocated_records:
            # Add timestamps
            now_utc = datetime.now(timezone.utc)
            record['CorrelationTimestamp'] = now_utc.isoformat()
            record['ProcessingDate'] = now_utc.date().isoformat()
            
            # Add device/store categorization
            record['IsUnknownDevice'] = record['DeviceId'] == 'unknown'
            record['IsUnknownStore'] = record['StoreNumber'] == 'unknown'
            record['HasCompleteAttribution'] = not (record['IsUnknownDevice'] or record['IsUnknownStore'])
            
            # Add cost analytics
            record['CostPerToken'] = record['AllocatedCost'] / record['TokensUsed'] if record['TokensUsed'] > 0 else 0
            record['CostPerApiCall'] = record['AllocatedCost'] / record['ApiCalls'] if record['ApiCalls'] > 0 else 0
            
            # Add time-based attributes
            time_window = pd.to_datetime(record['TimeWindow'])
            record['Hour'] = time_window.hour
            record['DayOfWeek'] = time_window.strftime('%A')
            record['IsBusinessHours'] = 9 <= time_window.hour <= 17
            record['IsWeekday'] = time_window.weekday() < 5
            
            # Add shift-based categorization (common for retail/store operations)
            hour = time_window.hour
            if 6 <= hour < 14:
                record['ShiftCategory'] = 'Morning'
            elif 14 <= hour < 22:
                record['ShiftCategory'] = 'Evening'
            else:
                record['ShiftCategory'] = 'Night'
            
            # Add quality metrics
            record['CorrelationConfidence'] = self._calculate_correlation_confidence(record)
            record['AllocationAccuracy'] = self._calculate_allocation_accuracy(record)
            
            # Add device utilization metrics
            record['DeviceUtilizationScore'] = self._calculate_device_utilization_score(record)
        
        return allocated_records
    
    def _calculate_correlation_confidence(self, record: Dict[str, Any]) -> float:
        """
        Calculate confidence score for the device/store correlation.
        
        Args:
            record: Correlated record
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 1.0
        
        # Reduce confidence for unknown attribution
        if record['IsUnknownDevice']:
            confidence *= 0.6  # Lower confidence for unknown devices
        if record['IsUnknownStore']:
            confidence *= 0.8  # Store unknown is less critical than device
        
        # Reduce confidence if no tokens tracked
        if record['TokensUsed'] == 0:
            confidence *= 0.5
        
        # Boost confidence for complete device/store attribution
        if record['HasCompleteAttribution']:
            confidence *= 1.1
        
        # Boost confidence for significant token usage (indicates real usage)
        if record['TokensUsed'] > 100:
            confidence *= 1.05
        
        return min(confidence, 1.0)
    
    def _calculate_allocation_accuracy(self, record: Dict[str, Any]) -> float:
        """
        Calculate accuracy score for cost allocation to device/store.
        
        Args:
            record: Allocated record
            
        Returns:
            Accuracy score (0.0 to 1.0)
        """
        accuracy = 1.0
        
        # High accuracy for token-based allocation when tokens are available
        if self.settings.allocation_method == AllocationMethod.TOKEN_BASED and record['TokensUsed'] > 0:
            accuracy = 0.95
        # Medium-high accuracy for proportional allocation
        elif self.settings.allocation_method == AllocationMethod.PROPORTIONAL:
            accuracy = 0.90
        # Medium accuracy for usage-based allocation
        elif self.settings.allocation_method == AllocationMethod.USAGE_BASED:
            accuracy = 0.80
        # Lower accuracy for equal allocation
        elif self.settings.allocation_method == AllocationMethod.EQUAL:
            accuracy = 0.70
        
        # Adjust based on attribution completeness
        if record['IsUnknownDevice']:
            accuracy *= 0.7  # Device unknown significantly impacts accuracy
        if record['IsUnknownStore']:
            accuracy *= 0.9  # Store unknown less impactful
        
        return accuracy
    
    def _calculate_device_utilization_score(self, record: Dict[str, Any]) -> float:
        """
        Calculate device utilization score based on activity.
        
        Args:
            record: Device record
            
        Returns:
            Utilization score (0.0 to 1.0)
        """
        # Base score on API calls and tokens
        api_call_factor = min(record['ApiCalls'] / 10.0, 1.0)  # Normalize to max of 10 calls
        token_factor = min(record['TokensUsed'] / 1000.0, 1.0)  # Normalize to max of 1000 tokens
        
        # Combine factors
        utilization_score = (api_call_factor + token_factor) / 2.0
        
        return utilization_score
    
    def get_correlation_summary(self, correlated_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics for device/store correlation results.
        
        Args:
            correlated_data: List of correlated device/store records
            
        Returns:
            Summary statistics
        """
        if not correlated_data:
            return {
                'total_records': 0,
                'total_allocated_cost': 0,
                'unique_devices': 0,
                'unique_stores': 0,
                'unique_device_store_combinations': 0,
                'avg_confidence': 0,
                'allocation_method': self.settings.allocation_method.value
            }
        
        df = pd.DataFrame(correlated_data)
        
        summary = {
            'total_records': len(correlated_data),
            'total_allocated_cost': df['AllocatedCost'].sum(),
            'unique_devices': df['DeviceId'].nunique(),
            'unique_stores': df['StoreNumber'].nunique(),
            'unique_device_store_combinations': df['DeviceStoreKey'].nunique(),
            'unknown_device_percentage': (df['IsUnknownDevice'].sum() / len(df)) * 100,
            'unknown_store_percentage': (df['IsUnknownStore'].sum() / len(df)) * 100,
            'avg_confidence': df['CorrelationConfidence'].mean(),
            'avg_accuracy': df['AllocationAccuracy'].mean(),
            'avg_utilization_score': df['DeviceUtilizationScore'].mean(),
            'allocation_method': self.settings.allocation_method.value,
            'cost_by_device': df.groupby('DeviceId')['AllocatedCost'].sum().to_dict(),
            'cost_by_store': df.groupby('StoreNumber')['AllocatedCost'].sum().to_dict(),
            'cost_by_model': df.groupby('ModelFamily')['AllocatedCost'].sum().to_dict(),
            'cost_by_shift': df.groupby('ShiftCategory')['AllocatedCost'].sum().to_dict(),
            'top_devices_by_cost': df.groupby('DeviceId')['AllocatedCost'].sum().sort_values(ascending=False).head(10).to_dict(),
            'top_stores_by_cost': df.groupby('StoreNumber')['AllocatedCost'].sum().sort_values(ascending=False).head(10).to_dict()
        }
        
        return summary
    
    def validate_correlation_results(self, original_cost_total: float, allocated_cost_total: float, tolerance: float = 0.01) -> bool:
        """
        Validate that allocated costs match original costs within tolerance.
        
        Args:
            original_cost_total: Total original cost
            allocated_cost_total: Total allocated cost
            tolerance: Acceptable variance percentage
            
        Returns:
            True if costs match within tolerance
        """
        if original_cost_total == 0:
            return allocated_cost_total == 0
        
        variance = abs(original_cost_total - allocated_cost_total) / original_cost_total
        is_valid = variance <= tolerance
        
        if not is_valid:
            self.logger.warning(f"Device/store cost allocation validation failed: Original=${original_cost_total:.2f}, Allocated=${allocated_cost_total:.2f}, Variance={variance:.2%}")
        else:
            self.logger.info(f"Device/store cost allocation validated: Original=${original_cost_total:.2f}, Allocated=${allocated_cost_total:.2f}")
        
        return is_valid
    
    def get_device_analytics(self, correlated_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate device-specific analytics for store operations insights.
        
        Args:
            correlated_data: List of correlated device/store records
            
        Returns:
            Device analytics
        """
        if not correlated_data:
            return {}
        
        df = pd.DataFrame(correlated_data)
        
        # Device performance analysis
        device_stats = df.groupby('DeviceId').agg({
            'AllocatedCost': ['sum', 'mean', 'count'],
            'TokensUsed': ['sum', 'mean'],
            'ApiCalls': ['sum', 'mean'],
            'AvgResponseTime': 'mean',
            'DeviceUtilizationScore': 'mean',
            'StoreNumber': 'first'  # Assuming devices are tied to specific stores
        }).round(4)
        
        device_stats.columns = ['_'.join(col).strip() for col in device_stats.columns.values]
        
        # Store performance analysis
        store_stats = df.groupby('StoreNumber').agg({
            'AllocatedCost': ['sum', 'mean', 'count'],
            'TokensUsed': ['sum', 'mean'],
            'ApiCalls': ['sum', 'mean'],
            'DeviceId': 'nunique',
            'DeviceUtilizationScore': 'mean'
        }).round(4)
        
        store_stats.columns = ['_'.join(col).strip() for col in store_stats.columns.values]
        
        return {
            'device_performance': device_stats.to_dict('index'),
            'store_performance': store_stats.to_dict('index'),
            'shift_analysis': df.groupby('ShiftCategory')['AllocatedCost'].sum().to_dict(),
            'business_hours_split': {
                'business_hours': df[df['IsBusinessHours']]['AllocatedCost'].sum(),
                'non_business_hours': df[~df['IsBusinessHours']]['AllocatedCost'].sum()
            }
        }