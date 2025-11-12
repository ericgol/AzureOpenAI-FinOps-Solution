# ResourceId Correlation Troubleshooting Guide

## Problem
Blank `ResourceId` fields in telemetry records prevent cost correlation between usage data and Azure Cost Management data.

## Root Cause
The APIM policy was not capturing the backend Azure OpenAI resource identifier, which is essential for correlating API usage telemetry with cost data.

## Solution Overview

### Changes Made

#### 1. APIM Policy (`src/apim-policies/finops-telemetry-policy.xml`)
- **Added ResourceId extraction** from APIM backend service URL in the `<outbound>` section
- Extracts the Azure OpenAI resource name from `context.Api.ServiceUrl`
- Format: `https://{resource-name}.openai.azure.com/...` → extracts `{resource-name}`
- Includes the `resourceId` field in the EventHub telemetry payload

#### 2. EventHub Function (`src/functions/eventhub-to-appinsights/function_app.py`)
- **Added `resource_id` field** to telemetry forwarding
- Ensures ResourceId flows from EventHub to Application Insights custom dimensions

#### 3. Data Correlation (`src/functions/finops-data-collector/shared/data_correlator.py`)
- Already has ResourceId normalization logic (`_normalize_resource_id`)
- Correlates telemetry with cost data by matching `ResourceId` and `TimeWindow`

## Deployment Steps

### Step 1: Update APIM Policy

```bash
# Navigate to Azure portal → API Management → APIs → OpenAI API → All operations
# Select the operation with your FinOps policy applied
# Click "Code view" (</>)
# Replace the policy XML with the updated version from:
#   src/apim-policies/finops-telemetry-policy.xml
```

**Important**: Ensure your API's backend service URL is correctly configured:
- Go to APIM → APIs → OpenAI API → Settings
- Verify "Web service URL" is set to your Azure OpenAI resource URL:
  ```
  https://your-openai-resource.openai.azure.com
  ```

### Step 2: Deploy Updated EventHub Function

```bash
cd src/functions/eventhub-to-appinsights

# Deploy function
func azure functionapp publish <your-eventhub-function-app-name> --python

# Verify deployment
az functionapp logs tail --name <your-eventhub-function-app-name> --resource-group <your-rg>
```

### Step 3: Test the Flow

#### Test 1: Make an API Call

```bash
curl -X POST "https://your-apim-gateway.azure-api.net/openai/deployments/gpt-4/chat/completions?api-version=2024-02-01" \
  -H "Content-Type: application/json" \
  -H "api-key: your-subscription-key" \
  -H "device-id: test-device-001" \
  -H "store-number: store-456" \
  -d '{
    "messages": [{"role": "user", "content": "Test ResourceId tracking"}],
    "max_tokens": 50
  }'
```

#### Test 2: Check APIM Response Headers

The response should include:
```
x-finops-device-id: test-device-001
x-finops-store-number: store-456
x-finops-correlation-id: <guid>
x-finops-tokens-used: <number>
```

#### Test 3: Verify EventHub Telemetry

```bash
# Check EventHub function logs
az functionapp logs tail --name <your-eventhub-function-app-name> --resource-group <your-rg>

# Look for log entries showing:
# "resource_id": "your-openai-resource"
```

#### Test 4: Query Application Insights

```kql
AppTraces
| where TimeGenerated >= ago(30m)
| where Message contains "FinOpsApiCall"
| extend parsedMessage = parse_json(Message)
| extend customDims = parsedMessage.customDimensions
| extend resource_id = tostring(customDims.resource_id)
| extend device_id = tostring(customDims.device_id)
| extend store_number = tostring(customDims.store_number)
| extend tokens_used = toint(customDims.tokens_used)
| project TimeGenerated, resource_id, device_id, store_number, tokens_used
| order by TimeGenerated desc
```

**Expected Result**: `resource_id` column should show your OpenAI resource name (e.g., `my-openai-eastus`), not "unknown" or blank.

#### Test 5: Verify FinOps Data Collector

```bash
# Manually trigger the FinOps data collector function
az functionapp function show \
  --resource-group <your-rg> \
  --name <your-finops-function-app-name> \
  --function-name finops_timer_trigger

# Check logs for correlation
az functionapp logs tail --name <your-finops-function-app-name> --resource-group <your-rg>
```

Look for log messages indicating:
```
Telemetry ResourceIds: ['your-openai-resource']
Cost ResourceIds: ['your-openai-resource']
Found X time window correlations for device/store combinations
```

### Step 4: Validate Cost Correlation

```kql
// Check correlated data in storage (after function runs)
// Query from Power BI or examine storage directly
```

## Common Issues and Solutions

### Issue 1: ResourceId Still Shows "unknown"

**Possible Causes:**
1. **APIM backend URL not configured properly**
   - Solution: Verify API backend service URL in APIM portal
   - Should be: `https://<resource-name>.openai.azure.com`

2. **Policy not deployed to correct operation**
   - Solution: Ensure policy is applied to ALL operations that need tracking
   - Check: APIM → APIs → Operations → Policy code view

3. **EventHub function not updated**
   - Solution: Redeploy function with `--python` flag
   - Verify deployment with `az functionapp show`

### Issue 2: No Correlation Despite Valid ResourceId

**Check TimeWindow Alignment:**

```kql
// Check telemetry time windows
AppTraces
| where Message contains "FinOpsApiCall"
| extend customDims = parse_json(Message).customDimensions
| summarize 
    Count=count(), 
    MinTime=min(TimeGenerated), 
    MaxTime=max(TimeGenerated) 
    by resource_id = tostring(customDims.resource_id)
```

**Check Cost Data Availability:**
- Azure Cost Management has 4-8 hour delay
- Adjust `LOOKBACK_HOURS` environment variable if needed
- Default is 1 hour - increase to 12 or 24 for testing

### Issue 3: Multiple OpenAI Resources

If you have multiple Azure OpenAI resources behind APIM (round-robin/load balancing):

1. **Option A: Named Backend Pools**
   - Configure APIM backends with descriptive names
   - Update policy to use `context.Backend?.Name`

2. **Option B: Dynamic Backend Selection**
   - Use APIM backend pools feature
   - Update policy to extract from `context.Backend?.Url`

## Validation Checklist

- [ ] APIM policy updated with ResourceId extraction logic
- [ ] APIM API backend service URL configured correctly
- [ ] EventHub function deployed with resource_id field
- [ ] Test API call returns non-blank x-finops-* headers
- [ ] Application Insights traces show valid resource_id values
- [ ] FinOps data collector logs show matching ResourceIds
- [ ] Cost correlation generates non-zero correlated records
- [ ] Power BI dashboard shows cost data per device/store

## Monitoring ResourceId Health

### Daily Check Query

```kql
let lookbackPeriod = 24h;
AppTraces
| where TimeGenerated >= ago(lookbackPeriod)
| where Message contains "FinOpsApiCall"
| extend customDims = parse_json(Message).customDimensions
| extend resource_id = tostring(customDims.resource_id)
| summarize 
    TotalCalls = count(),
    UnknownResourceCalls = countif(resource_id == "unknown" or isempty(resource_id)),
    ValidResourceCalls = countif(resource_id != "unknown" and isnotempty(resource_id))
| extend HealthScore = round(100.0 * ValidResourceCalls / TotalCalls, 2)
| project 
    TotalCalls,
    ValidResourceCalls,
    UnknownResourceCalls,
    HealthScore,
    Status = iff(HealthScore >= 95, "✅ Healthy", iff(HealthScore >= 80, "⚠️ Warning", "❌ Critical"))
```

**Target**: Health Score should be **≥95%**

## Architecture Flow with ResourceId

```
API Call with Headers
  ↓
APIM Gateway
  ├── Extracts: device-id, store-number
  ├── Extracts: ResourceId from context.Api.ServiceUrl
  └── Logs to EventHub with resourceId field
      ↓
EventHub
  ↓
EventHub Function (eventhub-to-appinsights)
  ├── Parses: resourceId from event
  └── Forwards to Application Insights with resource_id dimension
      ↓
Application Insights (Log Analytics)
  ├── Stores traces with customDimensions.resource_id
  └── Available for querying
      ↓
FinOps Data Collector (Timer Function)
  ├── Queries Application Insights for telemetry (with ResourceId)
  ├── Queries Cost Management API for costs (with ResourceId)
  ├── Normalizes ResourceId format on both sides
  ├── Correlates by [TimeWindow + ResourceId]
  └── Allocates costs to [DeviceId + StoreNumber]
      ↓
Azure Storage (finops-data container)
  ↓
Power BI Reports
```

## Next Steps

After confirming ResourceId correlation works:

1. **Adjust Lookback Window**: Set `LOOKBACK_HOURS` to match your reporting needs
2. **Monitor Cost Delay**: Track when cost data becomes available for recent usage
3. **Set Up Alerts**: Create alerts for ResourceId health score drops below 95%
4. **Power BI Refresh**: Configure incremental refresh for daily cost reports
5. **Documentation**: Update operational runbooks with ResourceId validation steps

## Related Documentation

- [APIM Policy Reference](../development/apim-policy-development.md)
- [Cost Correlation Logic](../architecture/cost-correlation.md)
- [Testing Guide](../testing/end-to-end-testing.md)
