"""
Advanced Correlation Algorithms for FinOps Solution

Provides sophisticated correlation methods for enhanced device/store cost attribution,
including time-weighted allocation, device usage patterns, and predictive analytics.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

from .config import FinOpsConfig
from .data_correlator import AllocationMethod


@dataclass
class DeviceUsagePattern:
    """Represents usage patterns for a specific device."""
    device_id: str
    store_number: str
    avg_tokens_per_hour: float
    avg_api_calls_per_hour: float
    peak_hours: List[int]
    usage_consistency_score: float
    cost_efficiency_score: float


class AdvancedCorrelator:
    """
    Advanced correlation algorithms for sophisticated device/store cost attribution.
    
    Provides:
    - Time-weighted cost allocation
    - Device usage pattern analysis
    - Predictive cost allocation
    - Anomaly detection in usage patterns
    - Cross-device cost spillover analysis
    """
    
    def __init__(self, config: FinOpsConfig):
        """
        Initialize advanced correlator.
        
        Args:
            config: FinOps configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def time_weighted_correlation(self, telemetry_df: pd.DataFrame, cost_df: pd.DataFrame, 
                                weight_decay_hours: float = 2.0) -> pd.DataFrame:
        """
        Perform time-weighted correlation where more recent usage gets higher weight.
        
        Args:
            telemetry_df: Telemetry DataFrame
            cost_df: Cost DataFrame
            weight_decay_hours: Hours over which weight decays to 50%
            
        Returns:
            DataFrame with time-weighted correlations
        """
        self.logger.info("Performing time-weighted correlation analysis")
        
        # Ensure we have timestamps
        if 'TimeGenerated' not in telemetry_df.columns or 'UsageDate' not in cost_df.columns:
            self.logger.warning("Missing timestamp columns for time-weighted correlation")
            return pd.DataFrame()
        
        # Convert to datetime
        telemetry_df['TimeGenerated'] = pd.to_datetime(telemetry_df['TimeGenerated'])
        cost_df['UsageDate'] = pd.to_datetime(cost_df['UsageDate'])
        
        # Calculate time weights (exponential decay)
        current_time = datetime.now(timezone.utc)
        
        # Calculate time weights for telemetry
        telemetry_df['TimeWeight'] = self._calculate_time_weight(
            telemetry_df['TimeGenerated'], current_time, weight_decay_hours
        )
        
        # Calculate time weights for cost data
        cost_df['TimeWeight'] = self._calculate_time_weight(
            cost_df['UsageDate'], current_time, weight_decay_hours
        )
        
        # Apply weighted aggregations
        weighted_telemetry = self._apply_weighted_aggregation(telemetry_df)
        weighted_cost = self._apply_weighted_aggregation(cost_df)
        
        # Merge weighted data
        correlated_df = self._merge_weighted_data(weighted_telemetry, weighted_cost)
        
        self.logger.info(f"Time-weighted correlation generated {len(correlated_df)} records")
        return correlated_df
    
    def _calculate_time_weight(self, timestamps: pd.Series, current_time: datetime, 
                              decay_hours: float) -> pd.Series:
        """Calculate exponential time weights."""
        hours_diff = (current_time - timestamps).dt.total_seconds() / 3600
        # Exponential decay: weight = exp(-hours_diff / decay_hours)
        weights = np.exp(-hours_diff / decay_hours)
        return weights
    
    def _apply_weighted_aggregation(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply weighted aggregation to data."""
        if 'deviceId' in df.columns:
            # Telemetry data
            grouped = df.groupby(['deviceId', 'storeNumber']).apply(
                lambda x: pd.Series({
                    'WeightedTokens': (x['TokensUsed'] * x['TimeWeight']).sum(),
                    'WeightedApiCalls': (x['StatusCode'].count() * x['TimeWeight']).sum(),
                    'TotalWeight': x['TimeWeight'].sum(),
                    'LatestTime': x['TimeGenerated'].max()
                })
            ).reset_index()
        else:
            # Cost data
            grouped = df.groupby('ResourceId').apply(
                lambda x: pd.Series({
                    'WeightedCost': (x['Cost'] * x['TimeWeight']).sum(),
                    'WeightedUsage': (x['UsageQuantity'] * x['TimeWeight']).sum(),
                    'TotalWeight': x['TimeWeight'].sum(),
                    'LatestTime': x['UsageDate'].max()
                })
            ).reset_index()
        
        return grouped
    
    def _merge_weighted_data(self, telemetry_df: pd.DataFrame, cost_df: pd.DataFrame) -> pd.DataFrame:
        """Merge weighted telemetry and cost data."""
        # Create time windows for merging
        telemetry_df['TimeWindow'] = pd.to_datetime(telemetry_df['LatestTime']).dt.floor('H')
        cost_df['TimeWindow'] = pd.to_datetime(cost_df['LatestTime']).dt.floor('H')
        
        # Merge on time window (simplified - could be more sophisticated)
        merged = pd.merge(
            telemetry_df,
            cost_df,
            on='TimeWindow',
            how='inner',
            suffixes=('_telemetry', '_cost')
        )
        
        return merged
    
    def analyze_device_usage_patterns(self, telemetry_data: List[Dict[str, Any]], 
                                    lookback_days: int = 7) -> List[DeviceUsagePattern]:
        """
        Analyze usage patterns for each device to optimize cost allocation.
        
        Args:
            telemetry_data: Historical telemetry data
            lookback_days: Days of history to analyze
            
        Returns:
            List of device usage patterns
        """
        self.logger.info(f"Analyzing device usage patterns over {lookback_days} days")
        
        if not telemetry_data:
            return []
        
        df = pd.DataFrame(telemetry_data)
        df['TimeGenerated'] = pd.to_datetime(df['TimeGenerated'])
        df['Hour'] = df['TimeGenerated'].dt.hour
        
        # Filter to lookback period
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        df = df[df['TimeGenerated'] >= cutoff_date]
        
        patterns = []
        
        # Analyze each device
        for (device_id, store_number), group in df.groupby(['deviceId', 'storeNumber']):
            if device_id == 'unknown' or store_number == 'unknown':
                continue
            
            pattern = self._analyze_single_device_pattern(device_id, store_number, group)
            patterns.append(pattern)
        
        self.logger.info(f"Analyzed patterns for {len(patterns)} devices")
        return patterns
    
    def _analyze_single_device_pattern(self, device_id: str, store_number: str, 
                                     device_df: pd.DataFrame) -> DeviceUsagePattern:
        """Analyze usage pattern for a single device."""
        # Calculate hourly averages
        hourly_stats = device_df.groupby('Hour').agg({
            'TokensUsed': ['count', 'sum', 'mean'],
            'StatusCode': 'count'
        })
        
        # Flatten column names
        hourly_stats.columns = ['TokenCount', 'TotalTokens', 'AvgTokens', 'ApiCalls']
        
        # Calculate key metrics
        total_hours = len(device_df['TimeGenerated'].dt.floor('H').unique())
        avg_tokens_per_hour = device_df['TokensUsed'].sum() / max(total_hours, 1)
        avg_api_calls_per_hour = len(device_df) / max(total_hours, 1)
        
        # Identify peak hours (top 20% of usage)
        peak_threshold = hourly_stats['TotalTokens'].quantile(0.8)
        peak_hours = hourly_stats[hourly_stats['TotalTokens'] >= peak_threshold].index.tolist()
        
        # Calculate consistency score (1 - coefficient of variation)
        token_cv = hourly_stats['TotalTokens'].std() / (hourly_stats['TotalTokens'].mean() + 1)
        usage_consistency_score = max(0, 1 - token_cv)
        
        # Calculate cost efficiency score (tokens per API call)
        avg_tokens_per_call = device_df['TokensUsed'].sum() / max(len(device_df), 1)
        # Normalize to 0-1 scale (assuming 1000 tokens per call is highly efficient)
        cost_efficiency_score = min(avg_tokens_per_call / 1000.0, 1.0)
        
        return DeviceUsagePattern(
            device_id=device_id,
            store_number=store_number,
            avg_tokens_per_hour=avg_tokens_per_hour,
            avg_api_calls_per_hour=avg_api_calls_per_hour,
            peak_hours=peak_hours,
            usage_consistency_score=usage_consistency_score,
            cost_efficiency_score=cost_efficiency_score
        )
    
    def predictive_cost_allocation(self, historical_data: List[Dict[str, Any]], 
                                 current_usage: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Use historical patterns to predict and allocate costs more accurately.
        
        Args:
            historical_data: Historical correlated data
            current_usage: Current usage data without cost allocation
            
        Returns:
            Dictionary with device predictions
        """
        self.logger.info("Performing predictive cost allocation")
        
        if not historical_data or not current_usage:
            return {}
        
        # Build prediction models for each device
        device_models = self._build_device_cost_models(historical_data)
        
        # Apply models to current usage
        predictions = {}
        current_df = pd.DataFrame(current_usage)
        
        for (device_id, store_number), group in current_df.groupby(['deviceId', 'storeNumber']):
            device_key = f"{device_id}_{store_number}"
            
            if device_key in device_models:
                predicted_cost = self._predict_device_cost(device_models[device_key], group)
                predictions[device_key] = predicted_cost
        
        return predictions
    
    def _build_device_cost_models(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Build simple linear models for device cost prediction."""
        df = pd.DataFrame(historical_data)
        models = {}
        
        for (device_id, store_number), group in df.groupby(['DeviceId', 'StoreNumber']):
            if len(group) < 5:  # Need minimum data points
                continue
            
            device_key = f"{device_id}_{store_number}"
            
            # Simple linear relationship: cost ~ tokens + api_calls + time_factors
            X = group[['TokensUsed', 'ApiCalls', 'Hour']].fillna(0)
            y = group['AllocatedCost'].fillna(0)
            
            if len(X) > 0 and y.std() > 0:
                # Calculate simple coefficients
                token_coeff = np.corrcoef(X['TokensUsed'], y)[0, 1] if len(X) > 1 else 0
                call_coeff = np.corrcoef(X['ApiCalls'], y)[0, 1] if len(X) > 1 else 0
                
                models[device_key] = {
                    'token_coefficient': token_coeff,
                    'call_coefficient': call_coeff,
                    'avg_cost_per_token': y.sum() / max(X['TokensUsed'].sum(), 1),
                    'avg_cost_per_call': y.sum() / max(X['ApiCalls'].sum(), 1),
                    'historical_avg': y.mean()
                }
        
        return models
    
    def _predict_device_cost(self, model: Dict[str, Any], usage_data: pd.DataFrame) -> float:
        """Predict cost for a device based on its model."""
        total_tokens = usage_data['TokensUsed'].sum()
        total_calls = len(usage_data)
        
        # Use the most reliable predictor
        if model['token_coefficient'] > 0.5:
            prediction = total_tokens * model['avg_cost_per_token']
        elif model['call_coefficient'] > 0.5:
            prediction = total_calls * model['avg_cost_per_call']
        else:
            # Fall back to historical average
            prediction = model['historical_avg']
        
        return max(prediction, 0)
    
    def detect_usage_anomalies(self, current_usage: List[Dict[str, Any]], 
                             device_patterns: List[DeviceUsagePattern]) -> List[Dict[str, Any]]:
        """
        Detect anomalous usage patterns that might indicate cost allocation issues.
        
        Args:
            current_usage: Current usage data
            device_patterns: Historical device patterns
            
        Returns:
            List of detected anomalies
        """
        self.logger.info("Detecting usage anomalies")
        
        anomalies = []
        current_df = pd.DataFrame(current_usage)
        
        # Create pattern lookup
        pattern_lookup = {
            f"{p.device_id}_{p.store_number}": p for p in device_patterns
        }
        
        for (device_id, store_number), group in current_df.groupby(['deviceId', 'storeNumber']):
            device_key = f"{device_id}_{store_number}"
            
            if device_key not in pattern_lookup:
                continue
            
            pattern = pattern_lookup[device_key]
            current_tokens_per_hour = group['TokensUsed'].sum() / len(group.groupby(group['TimeGenerated'].dt.floor('H')))
            current_calls_per_hour = len(group) / len(group.groupby(group['TimeGenerated'].dt.floor('H')))
            
            # Check for significant deviations
            token_deviation = abs(current_tokens_per_hour - pattern.avg_tokens_per_hour) / max(pattern.avg_tokens_per_hour, 1)
            call_deviation = abs(current_calls_per_hour - pattern.avg_api_calls_per_hour) / max(pattern.avg_api_calls_per_hour, 1)
            
            if token_deviation > 2.0 or call_deviation > 2.0:  # 200% deviation threshold
                anomalies.append({
                    'device_id': device_id,
                    'store_number': store_number,
                    'anomaly_type': 'usage_spike' if current_tokens_per_hour > pattern.avg_tokens_per_hour else 'usage_drop',
                    'token_deviation': token_deviation,
                    'call_deviation': call_deviation,
                    'current_tokens_per_hour': current_tokens_per_hour,
                    'expected_tokens_per_hour': pattern.avg_tokens_per_hour,
                    'severity': 'high' if max(token_deviation, call_deviation) > 5.0 else 'medium'
                })
        
        self.logger.info(f"Detected {len(anomalies)} usage anomalies")
        return anomalies
    
    def cross_device_spillover_analysis(self, correlated_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze potential cost spillover between devices in the same store.
        
        Args:
            correlated_data: Correlated device/store data
            
        Returns:
            Spillover analysis results
        """
        self.logger.info("Performing cross-device spillover analysis")
        
        if not correlated_data:
            return {}
        
        df = pd.DataFrame(correlated_data)
        spillover_analysis = {}
        
        # Group by store to analyze device interactions
        for store_number, store_group in df.groupby('StoreNumber'):
            if len(store_group) < 2:  # Need at least 2 devices for spillover analysis
                continue
            
            devices_in_store = store_group['DeviceId'].unique()
            
            # Calculate correlation matrix for devices in the store
            device_costs = {}
            device_usage = {}
            
            for device_id in devices_in_store:
                device_data = store_group[store_group['DeviceId'] == device_id]
                device_costs[device_id] = device_data['AllocatedCost'].values
                device_usage[device_id] = device_data['TokensUsed'].values
            
            # Find potential spillover patterns
            spillover_pairs = []
            for i, device1 in enumerate(devices_in_store):
                for device2 in devices_in_store[i+1:]:
                    if len(device_costs[device1]) > 1 and len(device_costs[device2]) > 1:
                        correlation = np.corrcoef(device_costs[device1], device_costs[device2])[0, 1]
                        
                        if abs(correlation) > 0.7:  # Strong correlation threshold
                            spillover_pairs.append({
                                'device1': device1,
                                'device2': device2,
                                'correlation': correlation,
                                'relationship': 'positive' if correlation > 0 else 'negative'
                            })
            
            if spillover_pairs:
                spillover_analysis[store_number] = {
                    'device_count': len(devices_in_store),
                    'spillover_pairs': spillover_pairs,
                    'total_store_cost': store_group['AllocatedCost'].sum(),
                    'avg_device_cost': store_group.groupby('DeviceId')['AllocatedCost'].sum().mean()
                }
        
        return spillover_analysis
    
    def optimize_allocation_method(self, telemetry_data: List[Dict[str, Any]], 
                                 cost_data: List[Dict[str, Any]]) -> AllocationMethod:
        """
        Analyze data characteristics to recommend the optimal allocation method.
        
        Args:
            telemetry_data: Telemetry data
            cost_data: Cost data
            
        Returns:
            Recommended allocation method
        """
        self.logger.info("Analyzing data to optimize allocation method")
        
        if not telemetry_data or not cost_data:
            return AllocationMethod.EQUAL
        
        telem_df = pd.DataFrame(telemetry_data)
        
        # Analyze token usage patterns
        token_variance = telem_df['TokensUsed'].var()
        token_mean = telem_df['TokensUsed'].mean()
        token_cv = token_variance / max(token_mean, 1)
        
        # Analyze API call patterns
        call_counts = telem_df.groupby(['deviceId', 'storeNumber']).size()
        call_variance = call_counts.var()
        call_mean = call_counts.mean()
        call_cv = call_variance / max(call_mean, 1)
        
        # Analyze device distribution
        unique_devices = telem_df['deviceId'].nunique()
        unknown_device_ratio = (telem_df['deviceId'] == 'unknown').sum() / len(telem_df)
        
        # Decision logic
        if unknown_device_ratio > 0.5:
            # Too many unknowns, use equal allocation
            recommendation = AllocationMethod.EQUAL
            reason = "High ratio of unknown devices"
        elif token_cv > 2.0 and token_mean > 0:
            # High token variance, token-based allocation is best
            recommendation = AllocationMethod.TOKEN_BASED
            reason = "High token usage variance between devices"
        elif call_cv > 1.5:
            # High call variance, usage-based allocation
            recommendation = AllocationMethod.USAGE_BASED
            reason = "High API call variance between devices"
        elif unique_devices > 10:
            # Many devices, proportional works well
            recommendation = AllocationMethod.PROPORTIONAL
            reason = "Large number of devices with moderate variance"
        else:
            # Default to proportional
            recommendation = AllocationMethod.PROPORTIONAL
            reason = "Balanced usage patterns"
        
        self.logger.info(f"Recommended allocation method: {recommendation.value} ({reason})")
        return recommendation