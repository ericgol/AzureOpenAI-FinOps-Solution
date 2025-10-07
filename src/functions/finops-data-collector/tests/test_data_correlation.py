"""
Unit tests for FinOps data correlation components.

Tests the correlation engine, cost allocation methods, and edge cases.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import json
import tempfile
from typing import List, Dict, Any

# Import the classes we want to test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from config import FinOpsConfig
from data_correlator import DataCorrelator, AllocationMethod, CorrelationSettings
from advanced_correlator import AdvancedCorrelator, DeviceUsagePattern


class TestDataCorrelator:
    """Test cases for DataCorrelator class."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = Mock(spec=FinOpsConfig)
        config.default_allocation_method = "proportional"
        config.enable_user_mapping = True
        config.enable_store_mapping = True
        return config
    
    @pytest.fixture
    def correlator(self, mock_config):
        """Create DataCorrelator instance for testing."""
        return DataCorrelator(mock_config)
    
    @pytest.fixture
    def sample_telemetry_data(self):
        """Sample telemetry data for testing."""
        return [
            {
                'TimeGenerated': '2024-01-15T10:30:00Z',
                'RequestId': 'req-001',
                'deviceId': 'device-001',
                'storeNumber': 'store-001',
                'ApiName': 'chat/completions',
                'Method': 'POST',
                'StatusCode': 200,
                'ResponseTime': 150,
                'TokensUsed': 500,
                'ResourceId': '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.CognitiveServices/accounts/openai-1'
            },
            {
                'TimeGenerated': '2024-01-15T10:35:00Z',
                'RequestId': 'req-002', 
                'deviceId': 'device-002',
                'storeNumber': 'store-001',
                'ApiName': 'chat/completions',
                'Method': 'POST',
                'StatusCode': 200,
                'ResponseTime': 200,
                'TokensUsed': 300,
                'ResourceId': '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.CognitiveServices/accounts/openai-1'
            },
            {
                'TimeGenerated': '2024-01-15T10:40:00Z',
                'RequestId': 'req-003',
                'deviceId': 'device-001',
                'storeNumber': 'store-002',
                'ApiName': 'chat/completions',
                'Method': 'POST',
                'StatusCode': 200,
                'ResponseTime': 180,
                'TokensUsed': 400,
                'ResourceId': '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.CognitiveServices/accounts/openai-1'
            }
        ]
    
    @pytest.fixture
    def sample_cost_data(self):
        """Sample cost data for testing."""
        return [
            {
                'ResourceId': '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.CognitiveServices/accounts/openai-1',
                'ResourceType': 'Microsoft.CognitiveServices/accounts',
                'ServiceName': 'Azure OpenAI',
                'MeterName': 'GPT-4 Input Tokens',
                'UsageDate': '2024-01-15T10:00:00Z',
                'Cost': 10.50,
                'UsageQuantity': 1000,
                'Currency': 'USD',
                'CostType': 'Input Tokens',
                'ModelFamily': 'GPT-4',
                'IsTokenBased': True
            }
        ]
    
    def test_correlate_data_basic(self, correlator, sample_telemetry_data, sample_cost_data):
        """Test basic data correlation."""
        result = correlator.correlate_data(sample_telemetry_data, sample_cost_data)
        
        assert len(result) > 0
        assert all('DeviceId' in record for record in result)
        assert all('StoreNumber' in record for record in result)
        assert all('AllocatedCost' in record for record in result)
        assert all(record['AllocatedCost'] > 0 for record in result)
    
    def test_correlate_data_empty_inputs(self, correlator):
        """Test correlation with empty inputs."""
        result = correlator.correlate_data([], [])
        assert result == []
        
        result = correlator.correlate_data([{'test': 'data'}], [])
        assert result == []
        
        result = correlator.correlate_data([], [{'test': 'data'}])
        assert result == []
    
    def test_allocation_methods(self, mock_config, sample_telemetry_data, sample_cost_data):
        """Test different allocation methods."""
        methods = [AllocationMethod.EQUAL, AllocationMethod.PROPORTIONAL, 
                  AllocationMethod.TOKEN_BASED, AllocationMethod.USAGE_BASED]
        
        for method in methods:
            mock_config.default_allocation_method = method.value
            correlator = DataCorrelator(mock_config)
            
            result = correlator.correlate_data(sample_telemetry_data, sample_cost_data)
            assert len(result) > 0
            assert all(record['AllocationMethod'] == method.value for record in result)
    
    def test_unknown_devices_handling(self, correlator, sample_cost_data):
        """Test handling of unknown devices."""
        unknown_telemetry = [
            {
                'TimeGenerated': '2024-01-15T10:30:00Z',
                'RequestId': 'req-001',
                'deviceId': 'unknown',
                'storeNumber': 'unknown',
                'TokensUsed': 500,
                'StatusCode': 200,
                'ResourceId': '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.CognitiveServices/accounts/openai-1'
            }
        ]
        
        result = correlator.correlate_data(unknown_telemetry, sample_cost_data)
        assert len(result) > 0
        assert all(record['IsUnknownDevice'] for record in result)
        assert all(record['IsUnknownStore'] for record in result)
        assert all(not record['HasCompleteAttribution'] for record in result)
    
    def test_cost_allocation_validation(self, correlator, sample_telemetry_data, sample_cost_data):
        """Test that total allocated costs match original costs."""
        result = correlator.correlate_data(sample_telemetry_data, sample_cost_data)
        
        total_allocated = sum(record['AllocatedCost'] for record in result)
        original_total = sum(cost['Cost'] for cost in sample_cost_data)
        
        # Should be equal within tolerance
        tolerance = 0.01
        assert abs(total_allocated - original_total) / original_total <= tolerance
    
    def test_correlation_summary(self, correlator, sample_telemetry_data, sample_cost_data):
        """Test correlation summary generation."""
        result = correlator.correlate_data(sample_telemetry_data, sample_cost_data)
        summary = correlator.get_correlation_summary(result)
        
        assert 'total_records' in summary
        assert 'total_allocated_cost' in summary
        assert 'unique_devices' in summary
        assert 'unique_stores' in summary
        assert 'avg_confidence' in summary
        assert summary['total_records'] == len(result)


class TestAdvancedCorrelator:
    """Test cases for AdvancedCorrelator class."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = Mock(spec=FinOpsConfig)
        return config
    
    @pytest.fixture
    def advanced_correlator(self, mock_config):
        """Create AdvancedCorrelator instance for testing."""
        return AdvancedCorrelator(mock_config)
    
    @pytest.fixture
    def sample_historical_data(self):
        """Sample historical data for pattern analysis."""
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        data = []
        
        for i in range(24):  # 24 hours of data
            for j in range(3):  # 3 records per hour
                data.append({
                    'TimeGenerated': (base_time + timedelta(hours=i, minutes=j*20)).isoformat() + 'Z',
                    'deviceId': f'device-{(j % 2) + 1:03d}',
                    'storeNumber': 'store-001',
                    'TokensUsed': 100 + (i * 10) + (j * 5),  # Varying token usage
                    'StatusCode': 200,
                    'ResourceId': '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.CognitiveServices/accounts/openai-1'
                })
        
        return data
    
    def test_device_usage_pattern_analysis(self, advanced_correlator, sample_historical_data):
        """Test device usage pattern analysis."""
        patterns = advanced_correlator.analyze_device_usage_patterns(sample_historical_data, lookback_days=1)
        
        assert len(patterns) > 0
        for pattern in patterns:
            assert isinstance(pattern, DeviceUsagePattern)
            assert pattern.device_id.startswith('device-')
            assert pattern.store_number == 'store-001'
            assert pattern.avg_tokens_per_hour > 0
            assert pattern.avg_api_calls_per_hour > 0
            assert 0 <= pattern.usage_consistency_score <= 1
            assert 0 <= pattern.cost_efficiency_score <= 1
    
    def test_predictive_cost_allocation(self, advanced_correlator):
        """Test predictive cost allocation."""
        historical_data = [
            {
                'DeviceId': 'device-001',
                'StoreNumber': 'store-001',
                'TokensUsed': 1000,
                'ApiCalls': 10,
                'Hour': 10,
                'AllocatedCost': 5.0
            },
            {
                'DeviceId': 'device-001',
                'StoreNumber': 'store-001',
                'TokensUsed': 1200,
                'ApiCalls': 12,
                'Hour': 11,
                'AllocatedCost': 6.0
            }
        ]
        
        current_usage = [
            {
                'deviceId': 'device-001',
                'storeNumber': 'store-001',
                'TokensUsed': 1100,
                'ApiCalls': 11
            }
        ]
        
        predictions = advanced_correlator.predictive_cost_allocation(historical_data, current_usage)
        
        assert len(predictions) > 0
        assert 'device-001_store-001' in predictions
        assert predictions['device-001_store-001'] > 0
    
    def test_anomaly_detection(self, advanced_correlator):
        """Test usage anomaly detection."""
        # Create normal patterns
        patterns = [
            DeviceUsagePattern(
                device_id='device-001',
                store_number='store-001',
                avg_tokens_per_hour=1000,
                avg_api_calls_per_hour=10,
                peak_hours=[9, 10, 11],
                usage_consistency_score=0.8,
                cost_efficiency_score=0.7
            )
        ]
        
        # Create anomalous current usage (3x normal)
        current_usage = [
            {
                'TimeGenerated': '2024-01-15T10:00:00Z',
                'deviceId': 'device-001',
                'storeNumber': 'store-001',
                'TokensUsed': 3000,  # 3x normal
                'StatusCode': 200
            }
        ]
        
        anomalies = advanced_correlator.detect_usage_anomalies(current_usage, patterns)
        
        assert len(anomalies) > 0
        anomaly = anomalies[0]
        assert anomaly['device_id'] == 'device-001'
        assert anomaly['anomaly_type'] == 'usage_spike'
        assert anomaly['severity'] in ['medium', 'high']
    
    def test_optimization_recommendations(self, advanced_correlator):
        """Test allocation method optimization."""
        # Test high token variance scenario
        high_variance_telemetry = [
            {'deviceId': 'device-001', 'storeNumber': 'store-001', 'TokensUsed': 100},
            {'deviceId': 'device-002', 'storeNumber': 'store-001', 'TokensUsed': 5000},
            {'deviceId': 'device-003', 'storeNumber': 'store-001', 'TokensUsed': 200}
        ]
        
        cost_data = [{'Cost': 100}]
        
        recommendation = advanced_correlator.optimize_allocation_method(high_variance_telemetry, cost_data)
        assert recommendation == AllocationMethod.TOKEN_BASED
        
        # Test unknown devices scenario
        unknown_devices_telemetry = [
            {'deviceId': 'unknown', 'storeNumber': 'store-001', 'TokensUsed': 100},
            {'deviceId': 'unknown', 'storeNumber': 'store-002', 'TokensUsed': 200}
        ]
        
        recommendation = advanced_correlator.optimize_allocation_method(unknown_devices_telemetry, cost_data)
        assert recommendation == AllocationMethod.EQUAL


class TestAllocationMethods:
    """Test specific allocation method calculations."""
    
    @pytest.fixture
    def correlator_config(self):
        """Configuration for allocation testing."""
        config = Mock(spec=FinOpsConfig)
        config.enable_user_mapping = True
        config.enable_store_mapping = True
        return config
    
    def test_proportional_allocation(self, correlator_config):
        """Test proportional allocation calculation."""
        correlator_config.default_allocation_method = "proportional"
        correlator = DataCorrelator(correlator_config)
        
        telemetry_data = [
            {
                'TimeGenerated': '2024-01-15T10:30:00Z',
                'deviceId': 'device-001',
                'storeNumber': 'store-001',
                'TokensUsed': 600,  # 60% of total tokens
                'StatusCode': 200,
                'ResourceId': '/test/resource'
            },
            {
                'TimeGenerated': '2024-01-15T10:30:00Z',
                'deviceId': 'device-002',
                'storeNumber': 'store-001',
                'TokensUsed': 400,  # 40% of total tokens
                'StatusCode': 200,
                'ResourceId': '/test/resource'
            }
        ]
        
        cost_data = [
            {
                'ResourceId': '/test/resource',
                'UsageDate': '2024-01-15T10:30:00Z',
                'Cost': 10.0,
                'UsageQuantity': 1000,
                'CostType': 'Input Tokens'
            }
        ]
        
        result = correlator.correlate_data(telemetry_data, cost_data)
        
        # Find allocations for each device
        device1_cost = next(r['AllocatedCost'] for r in result if r['DeviceId'] == 'device-001')
        device2_cost = next(r['AllocatedCost'] for r in result if r['DeviceId'] == 'device-002')
        
        # Should be allocated proportionally to token usage
        total_cost = device1_cost + device2_cost
        assert abs(total_cost - 10.0) < 0.01  # Total should match original cost
        assert device1_cost > device2_cost  # Device 1 used more tokens
        assert abs(device1_cost / total_cost - 0.6) < 0.1  # ~60% allocation
    
    def test_equal_allocation(self, correlator_config):
        """Test equal allocation calculation."""
        correlator_config.default_allocation_method = "equal"
        correlator = DataCorrelator(correlator_config)
        
        telemetry_data = [
            {
                'TimeGenerated': '2024-01-15T10:30:00Z',
                'deviceId': 'device-001',
                'storeNumber': 'store-001',
                'TokensUsed': 900,  # Much higher usage
                'StatusCode': 200,
                'ResourceId': '/test/resource'
            },
            {
                'TimeGenerated': '2024-01-15T10:30:00Z',
                'deviceId': 'device-002',
                'storeNumber': 'store-001',
                'TokensUsed': 100,  # Much lower usage
                'StatusCode': 200,
                'ResourceId': '/test/resource'
            }
        ]
        
        cost_data = [
            {
                'ResourceId': '/test/resource',
                'UsageDate': '2024-01-15T10:30:00Z',
                'Cost': 10.0,
                'UsageQuantity': 1000,
                'CostType': 'Input Tokens'
            }
        ]
        
        result = correlator.correlate_data(telemetry_data, cost_data)
        
        # Find allocations for each device
        device1_cost = next(r['AllocatedCost'] for r in result if r['DeviceId'] == 'device-001')
        device2_cost = next(r['AllocatedCost'] for r in result if r['DeviceId'] == 'device-002')
        
        # Should be allocated equally regardless of usage
        assert abs(device1_cost - device2_cost) < 0.01  # Should be equal
        assert abs(device1_cost - 5.0) < 0.01  # Each should get $5


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_zero_cost_allocation(self):
        """Test handling of zero cost scenarios."""
        config = Mock(spec=FinOpsConfig)
        config.default_allocation_method = "proportional"
        config.enable_user_mapping = True
        config.enable_store_mapping = True
        correlator = DataCorrelator(config)
        
        telemetry_data = [
            {
                'TimeGenerated': '2024-01-15T10:30:00Z',
                'deviceId': 'device-001',
                'storeNumber': 'store-001',
                'TokensUsed': 100,
                'StatusCode': 200,
                'ResourceId': '/test/resource'
            }
        ]
        
        cost_data = [
            {
                'ResourceId': '/test/resource',
                'UsageDate': '2024-01-15T10:30:00Z',
                'Cost': 0.0,  # Zero cost
                'UsageQuantity': 0,
                'CostType': 'Input Tokens'
            }
        ]
        
        result = correlator.correlate_data(telemetry_data, cost_data)
        
        # Should handle gracefully
        assert len(result) >= 0  # Should not crash
        if result:
            assert all(record['AllocatedCost'] == 0.0 for record in result)
    
    def test_mismatched_time_windows(self):
        """Test handling of mismatched time windows."""
        config = Mock(spec=FinOpsConfig)
        config.default_allocation_method = "proportional"
        config.enable_user_mapping = True
        config.enable_store_mapping = True
        correlator = DataCorrelator(config)
        
        # Telemetry from one time window
        telemetry_data = [
            {
                'TimeGenerated': '2024-01-15T10:30:00Z',
                'deviceId': 'device-001',
                'storeNumber': 'store-001',
                'TokensUsed': 100,
                'StatusCode': 200,
                'ResourceId': '/test/resource'
            }
        ]
        
        # Cost from completely different time window
        cost_data = [
            {
                'ResourceId': '/test/resource',
                'UsageDate': '2024-01-16T15:30:00Z',  # Different day
                'Cost': 10.0,
                'UsageQuantity': 1000,
                'CostType': 'Input Tokens'
            }
        ]
        
        result = correlator.correlate_data(telemetry_data, cost_data)
        
        # Should handle gracefully (might result in no correlations)
        assert isinstance(result, list)
        # This might be empty if no time windows match


if __name__ == "__main__":
    pytest.main([__file__, "-v"])