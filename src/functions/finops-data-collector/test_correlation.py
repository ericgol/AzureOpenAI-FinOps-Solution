#!/usr/bin/env python3
"""
Simple test script for data correlation functionality.
"""
import sys
sys.path.insert(0, '.')

from shared.config import FinOpsConfig
from shared.data_correlator import DataCorrelator, AllocationMethod

def main():
    print("🔍 Testing Azure OpenAI FinOps Data Correlation...")
    
    # Create configuration
    config = FinOpsConfig(
        LOG_ANALYTICS_WORKSPACE_ID='test-workspace-id',
        COST_MANAGEMENT_SCOPE='/subscriptions/test-sub-id',
        STORAGE_ACCOUNT_NAME='teststorageaccount',
        DEFAULT_ALLOCATION_METHOD='proportional'
    )
    print("✓ Configuration created successfully")
    
    # Create correlator
    correlator = DataCorrelator(config)
    print("✓ Data correlator created successfully")
    
    # Sample telemetry data
    telemetry_data = [
        {
            'TimeGenerated': '2024-01-15T10:30:00Z',
            'RequestId': 'req-001',
            'deviceId': 'device-001',
            'storeNumber': 'store-001',
            'ApiName': 'chat/completions',
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
            'StatusCode': 200,
            'ResponseTime': 200,
            'TokensUsed': 300,
            'ResourceId': '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.CognitiveServices/accounts/openai-1'
        }
    ]
    
    # Sample cost data
    cost_data = [
        {
            'ResourceId': '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.CognitiveServices/accounts/openai-1',
            'ResourceType': 'Microsoft.CognitiveServices/accounts',
            'ServiceName': 'Azure OpenAI',
            'UsageDate': '2024-01-15T10:00:00Z',
            'Cost': 10.00,
            'UsageQuantity': 800,
            'Currency': 'USD',
            'IsTokenBased': True
        }
    ]
    
    try:
        # Test correlation
        print("🔄 Correlating data...")
        result = correlator.correlate_data(telemetry_data, cost_data)
        
        print(f"✓ Correlated {len(result)} records")
        print(f"✓ Total allocated cost: ${sum(r['AllocatedCost'] for r in result):.2f}")
        print(f"✓ Unique devices: {len(set(r['DeviceId'] for r in result))}")
        print(f"✓ Unique stores: {len(set(r['StoreNumber'] for r in result))}")
        
        # Test summary
        summary = correlator.get_correlation_summary(result)
        print(f"✓ Summary contains {len(summary)} metrics")
        
        # Show allocation methods available
        methods = [m.value for m in AllocationMethod]
        print(f"✓ Available allocation methods: {methods}")
        
        print("✅ All tests passed! Data correlation is working correctly.")
        
        # Show sample result
        if result:
            print("\n📊 Sample correlated record:")
            sample_record = result[0]
            for key, value in sample_record.items():
                print(f"   {key}: {value}")
        
    except Exception as e:
        print(f"❌ Error during correlation: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())