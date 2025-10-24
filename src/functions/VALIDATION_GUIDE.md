# FinOps Function Apps - Validation Guide

This guide provides practical methods to validate the functionality of both Azure Function apps in the FinOps solution.

## Overview

The FinOps solution consists of two function apps:

1. **EventHub to AppInsights** (`pike-dev-ehfunc-*`) - Forwards APIM telemetry from EventHub to Application Insights
2. **FinOps Data Collector** (`pike-dev-func-*`) - Collects telemetry and cost data, correlates them, and stores results

---

## 1. EventHub to AppInsights Function Validation

### Prerequisites

```bash
# Install azure-eventhub Python package if not already installed
pip install azure-eventhub
```

### A. Send Test Event to EventHub

```bash
# Get EventHub connection string
EH_CONN_STRING=$(az eventhubs namespace authorization-rule keys list \
  --resource-group pike-dev-rg \
  --namespace-name pike-dev-eh-6v5sbjvrgatqy \
  --name RootManageSharedAccessKey \
  --query "primaryConnectionString" -o tsv)

# Send test telemetry event
python3 << 'EOF'
from azure.eventhub import EventHubProducerClient, EventData
import json
import os
from datetime import datetime, timezone

connection_str = os.environ['EH_CONN_STRING']
eventhub_name = "finops-telemetry"

producer = EventHubProducerClient.from_connection_string(
    connection_str, eventhub_name=eventhub_name
)

# Create test telemetry event matching APIM policy format
test_event = {
    "eventType": "FinOpsApiCall",
    "correlationId": "test-correlation-001",
    "deviceId": "test-device-123",
    "storeNumber": "store-456",
    "apiName": "openai-api",
    "operationName": "chat/completions",
    "method": "POST",
    "url": "https://api.openai.example.com/chat/completions",
    "statusCode": 200,
    "responseTime": 250,
    "tokensUsed": 150,
    "promptTokens": 100,
    "completionTokens": 50,
    "modelName": "gpt-4",
    "apiVersion": "2024-02-01",
    "subscriptionId": "test-subscription",
    "productId": "openai-product",
    "resourceRegion": "eastus",
    "timestamp": datetime.now(timezone.utc).isoformat()
}

event_data_batch = producer.create_batch()
event_data_batch.add(EventData(json.dumps(test_event)))

producer.send_batch(event_data_batch)
producer.close()

print("✓ Test event sent to EventHub")
print(f"  Device ID: {test_event['deviceId']}")
print(f"  Store Number: {test_event['storeNumber']}")
print(f"  Correlation ID: {test_event['correlationId']}")
EOF
```

### B. Verify Event Processing in Application Insights

```bash
# Wait for processing (EventHub batch processing may take a few seconds)
echo "Waiting 15 seconds for event processing..."
sleep 15

# Query Application Insights for the test event
az monitor app-insights query \
  --app 40d0fa38-5d08-4f22-a0c4-a386b9dc0a2c \
  --analytics-query "traces 
    | where cloud_RoleName == 'pike-dev-ehfunc-6v5sbjvrgatqy'
    | where timestamp > ago(5m)
    | where message contains 'test-device-123' or message contains 'EventHub to AppInsights'
    | project timestamp, message, severityLevel, customDimensions
    | order by timestamp desc
    | take 10" \
  --output table
```

### C. Check Function Execution Status

```bash
# Check recent function invocations
az monitor app-insights query \
  --app 40d0fa38-5d08-4f22-a0c4-a386b9dc0a2c \
  --analytics-query "requests 
    | where cloud_RoleName == 'pike-dev-ehfunc-6v5sbjvrgatqy'
    | where timestamp > ago(10m)
    | project timestamp, name, success, duration, resultCode
    | order by timestamp desc
    | take 10" \
  --output table
```

### D. Stream Live Function Logs

```bash
# Stream logs in real-time (useful during testing)
az functionapp log tail \
  --name pike-dev-ehfunc-6v5sbjvrgatqy \
  --resource-group pike-dev-rg
```

### Expected Results

✅ **Success indicators:**
- Test event sent successfully to EventHub
- Function invocation appears in Application Insights requests
- Trace with device ID `test-device-123` appears in Application Insights
- No errors in function logs
- Custom dimensions include `device.id`, `store.number`, `ai.tokens.used`

❌ **Troubleshooting:**
- If no traces appear: Check EventHub connection string in function app settings
- If function doesn't trigger: Verify EventHub consumer group is configured (`$Default`)
- If errors occur: Check function app logs for Python exceptions

---

## 2. FinOps Data Collector Function Validation

### A. Manually Trigger Function (Recommended)

```bash
# Trigger the timer function manually (easiest way to test)
az functionapp function keys list \
  --name pike-dev-func-6v5sbjvrgatqy \
  --resource-group pike-dev-rg \
  --function-name finops_timer_trigger \
  --query "default" -o tsv | \
xargs -I {} curl -X POST \
  "https://pike-dev-func-6v5sbjvrgatqy.azurewebsites.net/admin/functions/finops_timer_trigger" \
  -H "x-functions-key: {}"

echo "✓ Function triggered manually"
```

Alternative using Azure CLI:

```bash
# Direct invocation (if supported by your Azure CLI version)
az rest --method post \
  --uri "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/pike-dev-rg/providers/Microsoft.Web/sites/pike-dev-func-6v5sbjvrgatqy/functions/finops_timer_trigger/invoke?api-version=2022-03-01"
```

### B. Monitor Execution in Real-Time

```bash
# Stream function logs to watch execution steps
az functionapp log tail \
  --name pike-dev-func-6v5sbjvrgatqy \
  --resource-group pike-dev-rg

# Look for these key messages:
# - "FinOps data collection started"
# - "Step 1: Collecting telemetry data from Log Analytics"
# - "Step 2: Collecting cost data from Cost Management API"
# - "Step 3: Correlating telemetry and cost data"
# - "Step 4: Storing correlated data in Azure Storage"
# - "FinOps data collection completed successfully"
```

### C. Query Function Execution History

```bash
# Check recent executions and their outcomes
az monitor app-insights query \
  --app 40d0fa38-5d08-4f22-a0c4-a386b9dc0a2c \
  --analytics-query "traces 
    | where cloud_RoleName == 'pike-dev-func-6v5sbjvrgatqy'
    | where timestamp > ago(30m)
    | where message contains 'FinOps' or message contains 'Step'
    | project timestamp, message, severityLevel
    | order by timestamp desc
    | take 50" \
  --output table
```

### D. Verify Data Storage

```bash
# Get storage account name
STORAGE_ACCOUNT=$(az storage account list \
  --resource-group pike-dev-rg \
  --query "[0].name" -o tsv)

# List recent correlated data files (today's partition)
az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name finops-data \
  --prefix "$(date -u +%Y/%m/%d)" \
  --query "[].{Name:name, Size:properties.contentLength, Modified:properties.lastModified}" \
  --output table

# Download a sample file for inspection
az storage blob download \
  --account-name $STORAGE_ACCOUNT \
  --container-name finops-data \
  --name "<blob-name-from-above>" \
  --file sample-correlated-data.json

# View the downloaded file
cat sample-correlated-data.json | jq '.[0]' 2>/dev/null || cat sample-correlated-data.json | head -20
```

### E. Check Raw Data Storage

```bash
# Check raw telemetry data
az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name raw-telemetry \
  --query "[?properties.lastModified > '$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)'].{Name:name, Size:properties.contentLength}" \
  --output table

# Check raw cost data
az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name cost-data \
  --query "[?properties.lastModified > '$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)'].{Name:name, Size:properties.contentLength}" \
  --output table
```

### F. Check for Errors or Warnings

```bash
# Look for errors in recent executions
az monitor app-insights query \
  --app 40d0fa38-5d08-4f22-a0c4-a386b9dc0a2c \
  --analytics-query "traces 
    | where cloud_RoleName == 'pike-dev-func-6v5sbjvrgatqy'
    | where timestamp > ago(1h)
    | where severityLevel >= 3
    | project timestamp, message, severityLevel
    | order by timestamp desc
    | take 20" \
  --output table
```

### Expected Results

✅ **Success indicators:**
- Function execution completes with "FinOps data collection completed successfully"
- All 4 steps complete without errors
- Correlated data files appear in `finops-data` container
- Raw data appears in `raw-telemetry` and `cost-data` containers
- Summary statistics show counts for telemetry records, cost records, and correlated records

❌ **Troubleshooting:**
- **No telemetry data collected**: Ensure APIM has been called with custom headers recently
- **No cost data**: Verify Cost Management Reader role is assigned to function's managed identity
- **Correlation errors**: Check that Log Analytics Workspace ID is correct in function settings
- **Storage errors**: Verify Storage Blob Data Contributor role for function's managed identity

---

## 3. End-to-End Validation

Test the complete flow from API call through APIM to data correlation.

### A. Make Test API Call via APIM

```bash
# Get APIM details
APIM_GATEWAY=$(az apim show \
  --name pike-dev-apim-6v5sbjvrgatqy \
  --resource-group pike-dev-rg \
  --query "gatewayUrl" -o tsv)

APIM_KEY=$(az apim subscription list \
  --resource-group pike-dev-rg \
  --service-name pike-dev-apim-6v5sbjvrgatqy \
  --query "[0].primaryKey" -o tsv)

# Make test API call with custom FinOps headers
curl -X POST "${APIM_GATEWAY}/openai/deployments/gpt-4/chat/completions?api-version=2024-02-01" \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: ${APIM_KEY}" \
  -H "device-id: e2e-validation-device-001" \
  -H "store-number: e2e-validation-store-999" \
  -d '{
    "messages": [{"role": "user", "content": "Test message for FinOps end-to-end validation"}],
    "max_tokens": 20
  }'
```

### B. Track Event Through the Pipeline

```bash
# Wait for processing through the pipeline
echo "Waiting 30 seconds for event processing..."
sleep 30

# 1. Check if event reached EventHub function
echo -e "\n=== Step 1: EventHub Function Processing ==="
az monitor app-insights query \
  --app 40d0fa38-5d08-4f22-a0c4-a386b9dc0a2c \
  --analytics-query "traces 
    | where timestamp > ago(2m)
    | where message contains 'e2e-validation-device-001'
    | project timestamp, cloud_RoleName, message
    | order by timestamp desc" \
  --output table

# 2. Check if event appears in Log Analytics (APIM logs)
echo -e "\n=== Step 2: APIM Gateway Logs ==="
LOG_WORKSPACE=$(az monitor log-analytics workspace list \
  --resource-group pike-dev-rg \
  --query "[0].customerId" -o tsv)

az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "ApiManagementGatewayLogs
    | where TimeGenerated > ago(5m)
    | extend deviceId = tostring(parse_json(BackendRequestHeaders)['device-id'])
    | where deviceId == 'e2e-validation-device-001'
    | project TimeGenerated, OperationName, ResponseCode, deviceId
    | take 5" \
  --output table

# 3. Trigger FinOps collector to process the data
echo -e "\n=== Step 3: Triggering FinOps Data Collector ==="
# (Use manual trigger command from section 2A)

# 4. Check correlated data
echo -e "\n=== Step 4: Verify Correlated Data ==="
STORAGE_ACCOUNT=$(az storage account list \
  --resource-group pike-dev-rg \
  --query "[0].name" -o tsv)

az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name finops-data \
  --prefix "$(date -u +%Y/%m/%d)" \
  --query "[-1].{Name:name, Size:properties.contentLength, Modified:properties.lastModified}" \
  --output table
```

---

## 4. Health Check Script

Save this as `health-check.sh` for quick validation:

```bash
#!/bin/bash
set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         FinOps Function Apps - Health Check                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# Configuration
RG="pike-dev-rg"
EHFUNC="pike-dev-ehfunc-6v5sbjvrgatqy"
FINOPS_FUNC="pike-dev-func-6v5sbjvrgatqy"
APP_INSIGHTS_ID="40d0fa38-5d08-4f22-a0c4-a386b9dc0a2c"

echo -e "\n📊 Function App Status:"
echo "─────────────────────────────────────────────────────────────"

echo -e "\n1. EventHub Function App:"
az functionapp show --name $EHFUNC --resource-group $RG \
  --query "{State:state, Runtime:siteConfig.linuxFxVersion, LastModified:lastModifiedTimeUtc}" \
  --output table

echo -e "\n2. FinOps Data Collector Function App:"
az functionapp show --name $FINOPS_FUNC --resource-group $RG \
  --query "{State:state, Runtime:siteConfig.linuxFxVersion, LastModified:lastModifiedTimeUtc}" \
  --output table

echo -e "\n📈 Recent Function Invocations (Last Hour):"
echo "─────────────────────────────────────────────────────────────"

echo -e "\n1. EventHub Function Invocations:"
az monitor app-insights query --app $APP_INSIGHTS_ID \
  --analytics-query "requests 
    | where cloud_RoleName == '$EHFUNC' 
    | where timestamp > ago(1h) 
    | summarize Count=count(), Successes=countif(success==true), Failures=countif(success==false)" \
  --output table

echo -e "\n2. FinOps Collector Function Invocations:"
az monitor app-insights query --app $APP_INSIGHTS_ID \
  --analytics-query "requests 
    | where cloud_RoleName == '$FINOPS_FUNC' 
    | where timestamp > ago(1h) 
    | summarize Count=count(), Successes=countif(success==true), Failures=countif(success==false)" \
  --output table

echo -e "\n🔍 Recent Errors (Last Hour):"
echo "─────────────────────────────────────────────────────────────"

ERROR_COUNT=$(az monitor app-insights query --app $APP_INSIGHTS_ID \
  --analytics-query "traces 
    | where timestamp > ago(1h) 
    | where severityLevel >= 3 
    | where cloud_RoleName in ('$EHFUNC', '$FINOPS_FUNC')
    | count" \
  --query "tables[0].rows[0][0]" -o tsv)

if [ "$ERROR_COUNT" -gt 0 ]; then
  echo "⚠️  Found $ERROR_COUNT errors:"
  az monitor app-insights query --app $APP_INSIGHTS_ID \
    --analytics-query "traces 
      | where timestamp > ago(1h) 
      | where severityLevel >= 3 
      | where cloud_RoleName in ('$EHFUNC', '$FINOPS_FUNC')
      | project timestamp, cloud_RoleName, message
      | order by timestamp desc
      | take 5" \
    --output table
else
  echo "✅ No errors found"
fi

echo -e "\n💾 Recent Data Storage Activity:"
echo "─────────────────────────────────────────────────────────────"

STORAGE_ACCOUNT=$(az storage account list --resource-group $RG --query "[0].name" -o tsv)

echo -e "\nCorrelated data files (today):"
BLOB_COUNT=$(az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name finops-data \
  --prefix "$(date -u +%Y/%m/%d)" \
  --query "length(@)" -o tsv 2>/dev/null || echo "0")

if [ "$BLOB_COUNT" -gt 0 ]; then
  echo "✅ Found $BLOB_COUNT correlated data files"
  az storage blob list \
    --account-name $STORAGE_ACCOUNT \
    --container-name finops-data \
    --prefix "$(date -u +%Y/%m/%d)" \
    --query "[-3:].{Name:name, Size:properties.contentLength, Modified:properties.lastModified}" \
    --output table
else
  echo "ℹ️  No correlated data files found for today"
fi

echo -e "\n╔══════════════════════════════════════════════════════════════╗"
echo "║                    Health Check Complete                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
```

Make it executable:

```bash
chmod +x health-check.sh
./health-check.sh
```

---

## 5. Common Validation Scenarios

### Scenario 1: First-Time Setup Validation

After initial deployment, run this sequence:

```bash
# 1. Send test event to EventHub (Section 1A)
# 2. Verify event processing (Section 1B)
# 3. Manually trigger FinOps collector (Section 2A)
# 4. Monitor execution (Section 2B)
# 5. Verify data storage (Section 2D)
```

### Scenario 2: Daily Operations Monitoring

```bash
# Run health check
./health-check.sh

# Review any errors
# Check data freshness in storage
```

### Scenario 3: Troubleshooting No Data

```bash
# 1. Verify APIM is receiving traffic
LOG_WORKSPACE=$(az monitor log-analytics workspace list --resource-group pike-dev-rg --query "[0].customerId" -o tsv)

az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "ApiManagementGatewayLogs
    | where TimeGenerated > ago(1h)
    | summarize count() by bin(TimeGenerated, 5m)
    | order by TimeGenerated desc" \
  --output table

# 2. Check EventHub message count
az eventhubs eventhub show \
  --resource-group pike-dev-rg \
  --namespace-name pike-dev-eh-6v5sbjvrgatqy \
  --name finops-telemetry \
  --query "{IncomingMessages:messageRetentionInDays, PartitionCount:partitionCount}" \
  --output table

# 3. Verify function app settings
az functionapp config appsettings list \
  --name pike-dev-func-6v5sbjvrgatqy \
  --resource-group pike-dev-rg \
  --query "[?name=='LOG_ANALYTICS_WORKSPACE_ID' || name=='COST_MANAGEMENT_SCOPE'].{Name:name, Value:value}" \
  --output table
```

---

## 6. Key Metrics to Monitor

### EventHub Function
- **Invocation count**: Should match EventHub message batches
- **Success rate**: Should be >95%
- **Average duration**: Typically <500ms per batch
- **Custom dimensions captured**: `device.id`, `store.number`, `ai.tokens.used`

### FinOps Data Collector
- **Execution frequency**: Every 6 minutes (or when manually triggered)
- **Success rate**: Should be 100% (failures indicate data source issues)
- **Average duration**: 1-3 minutes depending on data volume
- **Data outputs**: Files in `finops-data`, `raw-telemetry`, `cost-data` containers

---

## Support and Troubleshooting

For detailed troubleshooting, refer to:
- [WARP.md](../../WARP.md) - Development commands and architecture
- Azure Portal → Function App → Monitor → Logs
- Application Insights → Logs → Custom queries
- Storage Account → Containers → Blob inspection

Common issues:
- **"No matching distribution found"**: Update requirements.txt with correct package versions
- **"ServiceUnavailable"**: Function app is cold-starting, retry after 30 seconds
- **"Access denied to storage"**: Check managed identity role assignments
- **"No telemetry data"**: Verify APIM diagnostic settings and EventHub connection
