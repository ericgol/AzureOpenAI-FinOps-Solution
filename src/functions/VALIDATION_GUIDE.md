# FinOps Function Apps - Validation Guide

This guide provides practical methods to validate the functionality of both Azure Function apps in the FinOps solution.

## Overview

The FinOps solution consists of two function apps:

1. **EventHub to AppInsights** (`pike-dev-ehfunc-*`) - Forwards APIM telemetry from EventHub to Application Insights as traces
2. **FinOps Data Collector** (`pike-dev-func-*`) - Collects telemetry from AppTraces and cost data, correlates them, and stores results

---

## Prerequisites

### Required RBAC Permissions

The **finops-data-collector** function app requires the following Azure RBAC role assignments on its system-assigned managed identity:

| Role | Scope | Purpose | Command |
|------|-------|---------|---------|
| **Cost Management Reader** | Subscription | Query Azure Cost Management API for cost data | `az role assignment create --assignee <principal-id> --role "Cost Management Reader" --scope "/subscriptions/<subscription-id>"` |
| **Log Analytics Reader** | Resource Group or Workspace | Query Log Analytics for Application Insights telemetry | `az role assignment create --assignee <principal-id> --role "Log Analytics Reader" --scope "/subscriptions/<subscription-id>/resourceGroups/<rg-name>"` |
| **Storage Blob Data Contributor** | Storage Account | Write correlated FinOps data to Azure Storage | `az role assignment create --assignee <principal-id> --role "Storage Blob Data Contributor" --scope "/subscriptions/<subscription-id>/resourceGroups/<rg-name>/providers/Microsoft.Storage/storageAccounts/<storage-account-name>"` |

### Get Managed Identity Principal ID

```bash
az functionapp identity show \
  --name pike-dev-func-6v5sbjvrgatqy \
  --resource-group pike-dev-rg \
  --query principalId \
  --output tsv
```

### Verify Role Assignments

```bash
PRINCIPAL_ID=$(az functionapp identity show \
  --name pike-dev-func-6v5sbjvrgatqy \
  --resource-group pike-dev-rg \
  --query principalId \
  --output tsv)

az role assignment list \
  --all \
  --assignee $PRINCIPAL_ID \
  --query "[].{Role:roleDefinitionName,Scope:scope}" \
  --output table
```

---

## 1. EventHub to AppInsights Function Validation

### A. Send Test Event to EventHub

```bash
# Install azure-eventhub if needed
pip install azure-eventhub

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
    "customDimensions": {
        "correlation_id": "test-correlation-001",
        "device_id": "test-device-123",
        "store_number": "store-456",
        "operation_name": "openai-api/chat/completions",
        "method": "POST",
        "url": "https://api.openai.example.com/chat/completions",
        "status_code": 200,
        "response_time_ms": 250,
        "tokens_used": 150,
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "model_name": "gpt-4",
        "api_version": "2024-02-01",
        "resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.CognitiveServices/accounts/test-openai",
        "request_id": "test-request-001"
    },
    "timestamp": datetime.now(timezone.utc).isoformat()
}

event_data_batch = producer.create_batch()
event_data_batch.add(EventData(json.dumps(test_event)))

producer.send_batch(event_data_batch)
producer.close()

print("✓ Test event sent to EventHub")
print(f"  Device ID: {test_event['customDimensions']['device_id']}")
print(f"  Store Number: {test_event['customDimensions']['store_number']}")
print(f"  Correlation ID: {test_event['customDimensions']['correlation_id']}")
EOF
```

### B. Verify Event Processing in Application Insights

```bash
# Wait for processing (EventHub batch processing may take a few seconds)
echo "Waiting 15 seconds for event processing..."
sleep 15

# Get Log Analytics workspace ID
LOG_WORKSPACE=$(az monitor log-analytics workspace list \
  --resource-group pike-dev-rg \
  --query "[0].customerId" -o tsv)

# Query Application Insights traces for the test event
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated > ago(5m)
    | where Message contains 'test-device-123' or Message contains 'FinOpsApiCall'
    | extend parsedMessage = parse_json(Message)
    | extend customDims = parsedMessage.customDimensions
    | project TimeGenerated, AppRoleName, Message, customDims
    | order by TimeGenerated desc
    | take 10" \
  --output table
```

### C. Check Function Execution Status

```bash
# Check recent function invocations using AppRequests
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppRequests
    | where TimeGenerated > ago(10m)
    | where AppRoleName contains 'ehfunc'
    | project TimeGenerated, Name, Success, DurationMs, ResultCode
    | order by TimeGenerated desc
    | take 10" \
  --output table
```

### D. Stream Live Function Logs

```bash
# Stream logs in real-time (useful during testing)
az webapp log tail \
  --name pike-dev-ehfunc-6v5sbjvrgatqy \
  --resource-group pike-dev-rg
```

### Expected Results

✅ **Success indicators:**
- Test event sent successfully to EventHub
- Function invocation appears in AppRequests with Success=true
- Trace with device ID `test-device-123` appears in AppTraces
- No errors in function logs
- Custom dimensions include `device_id`, `store_number`, `tokens_used`

❌ **Troubleshooting:**
- If no traces appear: Check EventHub connection string in function app settings (`EventHubConnection`)
- If function doesn't trigger: Verify EventHub consumer group is configured (`$Default`)
- If errors occur: Check function app logs for Python exceptions
- If connection fails: Verify managed identity or connection string authentication

---

## 2. FinOps Data Collector Function Validation

### A. Check Configuration

```bash
# Verify required environment variables
az functionapp config appsettings list \
  --name pike-dev-func-6v5sbjvrgatqy \
  --resource-group pike-dev-rg \
  --query "[?starts_with(name, 'LOG_ANALYTICS') || starts_with(name, 'COST_MANAGEMENT') || starts_with(name, 'STORAGE_ACCOUNT') || name=='ENVIRONMENT'].{Name:name, Value:value}" \
  --output table
```

### B. Monitor Scheduled Execution

The function runs automatically every 6 minutes. Monitor the logs:

```bash
# Stream function logs to watch execution steps
az webapp log tail \
  --name pike-dev-func-6v5sbjvrgatqy \
  --resource-group pike-dev-rg

# Look for these key messages:
# - "FinOps data collection started"
# - "Step 1: Collecting telemetry data from Application Insights traces"
# - "Collected X telemetry records"
# - "Step 2: Collecting cost data from Cost Management API"
# - "Collected Y cost records" (or "Skipping cost collection due to rate limit")
# - "Step 3: Correlating telemetry and cost data"
# - "Step 4: Storing correlated data in Azure Storage"
# - "FinOps data collection completed successfully"
```

### C. Query Function Execution History

```bash
# Get Log Analytics workspace ID
LOG_WORKSPACE=$(az monitor log-analytics workspace list \
  --resource-group pike-dev-rg \
  --query "[0].customerId" -o tsv)

# Check recent executions and their outcomes
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated > ago(30m)
    | where AppRoleName contains 'pike-dev-func'
    | where Message contains 'FinOps' or Message contains 'Step' or Message contains 'Collected'
    | project TimeGenerated, Message, SeverityLevel
    | order by TimeGenerated desc
    | take 50" \
  --output table
```

### D. Verify Telemetry Collection

```bash
# Check that telemetry data is being queried successfully
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated > ago(1h)
    | where AppRoleName contains 'pike-dev-func'
    | where Message contains 'Collected' and Message contains 'telemetry records'
    | project TimeGenerated, Message
    | order by TimeGenerated desc
    | take 10" \
  --output table
```

### E. Verify Data Storage

```bash
# Get storage account name
STORAGE_ACCOUNT=$(az storage account list \
  --resource-group pike-dev-rg \
  --query "[?starts_with(name, 'pikedevsa')].name" -o tsv)

# List recent correlated data files (today's partition)
az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name finops-data \
  --prefix "$(date -u +%Y/%m/%d)" \
  --auth-mode login \
  --query "[].{Name:name, Size:properties.contentLength, Modified:properties.lastModified}" \
  --output table

# Download a sample file for inspection (if files exist)
LATEST_BLOB=$(az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name finops-data \
  --prefix "$(date -u +%Y/%m/%d)" \
  --auth-mode login \
  --query "[-1].name" -o tsv)

if [ ! -z "$LATEST_BLOB" ]; then
  az storage blob download \
    --account-name $STORAGE_ACCOUNT \
    --container-name finops-data \
    --name "$LATEST_BLOB" \
    --file sample-correlated-data.json \
    --auth-mode login

  # View the downloaded file
  cat sample-correlated-data.json | jq '.[0]' 2>/dev/null || cat sample-correlated-data.json | head -20
else
  echo "No correlated data files found for today"
fi
```

### F. Check Raw Data Storage

```bash
# Check raw telemetry data
az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name raw-telemetry \
  --auth-mode login \
  --query "[?properties.lastModified > '$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)'].{Name:name, Size:properties.contentLength}" \
  --output table

# Check raw cost data
az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name cost-data \
  --auth-mode login \
  --query "[?properties.lastModified > '$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)'].{Name:name, Size:properties.contentLength}" \
  --output table
```

### G. Check for Errors or Warnings

```bash
# Look for errors in recent executions
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated > ago(1h)
    | where AppRoleName contains 'pike-dev-func'
    | where SeverityLevel >= 3
    | project TimeGenerated, Message, SeverityLevel
    | order by TimeGenerated desc
    | take 20" \
  --output table

# Check specifically for rate limit warnings (expected with 6-minute schedule)
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated > ago(1h)
    | where AppRoleName contains 'pike-dev-func'
    | where Message contains '429' or Message contains 'rate limit'
    | project TimeGenerated, Message
    | order by TimeGenerated desc" \
  --output table
```

### Expected Results

✅ **Success indicators:**
- Function executes every 6 minutes automatically
- "Collected X telemetry records" where X > 0 (if you have API traffic)
- "Collected Y cost records" OR "Skipping cost collection due to rate limit (will retry next run)"
- All 4 steps complete without critical errors
- Correlated data files appear in `finops-data` container
- Raw data appears in `raw-telemetry` and `cost-data` containers

⚠️ **Expected Warnings:**
- "Cost Management API rate limit hit (429)" - This is normal with 6-minute schedule; function will retry on next run
- "No Application Insights traces found" - Normal if no API calls have been made recently

❌ **Critical Errors to Fix:**
- **"RBACAccessDenied"**: Missing required role assignments (see Prerequisites section)
- **"'str' object has no attribute 'name'"**: Outdated code, redeploy function
- **"Invalid dataset grouping"**: Cost API query issue, redeploy function
- **"Failed to resolve table or column expression named 'traces'"**: Query using wrong table, should use `AppTraces`

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

# Get workspace ID
LOG_WORKSPACE=$(az monitor log-analytics workspace list \
  --resource-group pike-dev-rg \
  --query "[0].customerId" -o tsv)

# 1. Check if event reached EventHub function and was logged
echo -e "\n=== Step 1: EventHub Function Processing ==="
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated > ago(2m)
    | where Message contains 'e2e-validation-device-001'
    | project TimeGenerated, AppRoleName, Message
    | order by TimeGenerated desc" \
  --output table

# 2. Check if event appears in AppTraces (Application Insights)
echo -e "\n=== Step 2: Application Insights Traces ==="
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated > ago(5m)
    | where Message contains 'FinOpsApiCall'
    | extend parsedMessage = parse_json(Message)
    | extend customDims = parsedMessage.customDimensions
    | extend device_id = tostring(customDims.device_id)
    | where device_id == 'e2e-validation-device-001'
    | project TimeGenerated, device_id, customDims
    | take 5" \
  --output table

# 3. Wait for FinOps collector to run (runs every 6 minutes)
echo -e "\n=== Step 3: Wait for FinOps Data Collector ===="
echo "Next execution in ~6 minutes... (or manually trigger)"

# 4. After collector runs, check correlated data
echo -e "\n=== Step 4: Verify Correlated Data (run after collector executes) ==="
STORAGE_ACCOUNT=$(az storage account list \
  --resource-group pike-dev-rg \
  --query "[?starts_with(name, 'pikedevsa')].name" -o tsv)

az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name finops-data \
  --prefix "$(date -u +%Y/%m/%d)" \
  --auth-mode login \
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

# Get Log Analytics workspace ID
LOG_WORKSPACE=$(az monitor log-analytics workspace list \
  --resource-group $RG \
  --query "[0].customerId" -o tsv)

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
az monitor log-analytics query --workspace $LOG_WORKSPACE \
  --analytics-query "AppRequests 
    | where TimeGenerated > ago(1h)
    | where AppRoleName contains '$EHFUNC'
    | summarize Count=count(), Successes=countif(Success==true), Failures=countif(Success==false)" \
  --output table

echo -e "\n2. FinOps Collector Function Invocations:"
az monitor log-analytics query --workspace $LOG_WORKSPACE \
  --analytics-query "AppRequests 
    | where TimeGenerated > ago(1h)
    | where AppRoleName contains '$FINOPS_FUNC'
    | summarize Count=count(), Successes=countif(Success==true), Failures=countif(Success==false)" \
  --output table

echo -e "\n🔍 Recent Errors (Last Hour):"
echo "─────────────────────────────────────────────────────────────"

ERROR_COUNT=$(az monitor log-analytics query --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces 
    | where TimeGenerated > ago(1h) 
    | where SeverityLevel >= 3 
    | where AppRoleName contains '$EHFUNC' or AppRoleName contains '$FINOPS_FUNC'
    | count" \
  --query "tables[0].rows[0][0]" -o tsv)

if [ "$ERROR_COUNT" -gt 0 ]; then
  echo "⚠️  Found $ERROR_COUNT errors:"
  az monitor log-analytics query --workspace $LOG_WORKSPACE \
    --analytics-query "AppTraces 
      | where TimeGenerated > ago(1h) 
      | where SeverityLevel >= 3 
      | where AppRoleName contains '$EHFUNC' or AppRoleName contains '$FINOPS_FUNC'
      | project TimeGenerated, AppRoleName, Message
      | order by TimeGenerated desc
      | take 5" \
    --output table
else
  echo "✅ No errors found"
fi

echo -e "\n💾 Recent Data Storage Activity:"
echo "─────────────────────────────────────────────────────────────"

STORAGE_ACCOUNT=$(az storage account list --resource-group $RG --query "[?starts_with(name, 'pikedevsa')].name" -o tsv)

echo -e "\nCorrelated data files (today):"
BLOB_COUNT=$(az storage blob list \
  --account-name $STORAGE_ACCOUNT \
  --container-name finops-data \
  --prefix "$(date -u +%Y/%m/%d)" \
  --auth-mode login \
  --query "length(@)" -o tsv 2>/dev/null || echo "0")

if [ "$BLOB_COUNT" -gt 0 ]; then
  echo "✅ Found $BLOB_COUNT correlated data files"
  az storage blob list \
    --account-name $STORAGE_ACCOUNT \
    --container-name finops-data \
    --prefix "$(date -u +%Y/%m/%d)" \
    --auth-mode login \
    --query "[-3:].{Name:name, Size:properties.contentLength, Modified:properties.lastModified}" \
    --output table
else
  echo "ℹ️  No correlated data files found for today"
fi

echo -e "\n📊 Telemetry Collection Stats (Last Hour):"
echo "─────────────────────────────────────────────────────────────"
az monitor log-analytics query --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated > ago(1h)
    | where AppRoleName contains '$FINOPS_FUNC'
    | where Message contains 'Collected' and Message contains 'telemetry records'
    | project TimeGenerated, Message
    | order by TimeGenerated desc
    | take 5" \
  --output table

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
# 1. Verify RBAC permissions (see Prerequisites section)
# 2. Send test event to EventHub (Section 1A)
# 3. Verify event processing in AppTraces (Section 1B)
# 4. Wait for FinOps collector to run automatically (every 6 min)
# 5. Monitor execution (Section 2B)
# 6. Verify data storage (Section 2E)
```

### Scenario 2: Daily Operations Monitoring

```bash
# Run health check
./health-check.sh

# Review any errors
# Check data freshness in storage
# Monitor Cost API rate limit warnings (expected)
```

### Scenario 3: Troubleshooting No Telemetry Data

```bash
# Get workspace ID
LOG_WORKSPACE=$(az monitor log-analytics workspace list \
  --resource-group pike-dev-rg \
  --query "[0].customerId" -o tsv)

# 1. Verify AppTraces table has data
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated > ago(1h)
    | where Message contains 'FinOpsApiCall'
    | summarize count() by bin(TimeGenerated, 5m)
    | order by TimeGenerated desc" \
  --output table

# 2. Check EventHub message count
az eventhubs eventhub show \
  --resource-group pike-dev-rg \
  --namespace-name pike-dev-eh-6v5sbjvrgatqy \
  --name finops-telemetry \
  --query "{MessageRetention:messageRetentionInDays, PartitionCount:partitionCount}" \
  --output table

# 3. Verify function app settings
az functionapp config appsettings list \
  --name pike-dev-func-6v5sbjvrgatqy \
  --resource-group pike-dev-rg \
  --query "[?name=='LOG_ANALYTICS_WORKSPACE_ID' || name=='COST_MANAGEMENT_SCOPE'].{Name:name, Value:value}" \
  --output table

# 4. Test the AppTraces query directly
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated >= ago(1h)
    | where Message contains 'FinOpsApiCall' or Message has_cs 'device_id'
    | extend parsedMessage = parse_json(Message)
    | extend customDims = parsedMessage.customDimensions
    | extend device_id = tostring(customDims.device_id)
    | project TimeGenerated, device_id, customDims
    | take 5" \
  --output table
```

### Scenario 4: Troubleshooting Cost Management API Rate Limits

```bash
# Check frequency of rate limit warnings
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE \
  --analytics-query "AppTraces
    | where TimeGenerated > ago(4h)
    | where AppRoleName contains 'pike-dev-func'
    | where Message contains '429' or Message contains 'rate limit'
    | summarize RateLimitHits=count() by bin(TimeGenerated, 10m)
    | order by TimeGenerated desc" \
  --output table

# Expected: Rate limits are normal with 6-minute schedule
# Function will skip cost collection and retry on next run
# Telemetry collection continues unaffected
```

---

## 6. Key Metrics to Monitor

### EventHub Function
- **Invocation count**: Should match EventHub message batches
- **Success rate**: Should be >95%
- **Average duration**: Typically <500ms per batch
- **Custom dimensions captured**: `device_id`, `store_number`, `tokens_used`

### FinOps Data Collector
- **Execution frequency**: Every 6 minutes (automatic)
- **Success rate**: Should be 100% (warnings about rate limits are OK)
- **Average duration**: 30 seconds to 2 minutes depending on data volume
- **Data outputs**: Files in `finops-data`, `raw-telemetry`, `cost-data` containers
- **Rate limit behavior**: May skip cost collection on some runs due to API throttling (normal behavior)

---

## 7. Understanding Cost Management API Rate Limits

The Azure Cost Management API has strict throttling limits:
- **Read operations**: ~30 calls per minute at subscription scope
- **6-minute schedule**: May hit rate limits frequently

**Expected Behavior:**
- ✅ Telemetry collection always succeeds
- ⚠️ Cost collection may be skipped with warning: "Cost Management API rate limit hit (429)"
- 🔄 Function will retry cost collection on next run (6 minutes later)
- ✅ No data loss - telemetry is stored regardless of cost API status

**This is by design** to ensure continuous telemetry tracking while respecting Azure API limits.

---

## Support and Troubleshooting

For detailed troubleshooting, refer to:
- [WARP.md](../../WARP.md) - Development commands and architecture
- Azure Portal → Function App → Monitor → Logs
- Log Analytics Workspace → Logs → Custom queries using AppTraces/AppRequests
- Storage Account → Containers → Blob inspection

Common issues and solutions:

| Issue | Solution |
|-------|----------|
| **"RBACAccessDenied"** | Assign required roles to function's managed identity (see Prerequisites) |
| **"Failed to resolve table 'traces'"** | Query should use `AppTraces` not `traces` for workspace-based Application Insights |
| **"429 Too many requests"** | Expected behavior with 6-minute schedule; function will retry |
| **"'str' object has no attribute 'name'"** | Code bug fixed; redeploy function |
| **"Invalid dataset grouping: 'MeterName'"** | Use 'Meter' not 'MeterName'; redeploy function |
| **No telemetry data** | Verify EventHub function is running and APIM is sending traffic |
| **Access denied to storage** | Assign Storage Blob Data Contributor role to managed identity |

---

## Quick Reference: Important Table Names

When querying **workspace-based Application Insights** through **Log Analytics**:

| Data Type | Table Name | Use Case |
|-----------|------------|----------|
| Traces | `AppTraces` | Function logs, custom telemetry from EventHub function |
| Requests | `AppRequests` | Function invocations, HTTP requests |
| Dependencies | `AppDependencies` | External calls (EventHub, Storage, APIs) |
| Exceptions | `AppExceptions` | Unhandled errors |

**Note:** Do NOT use `traces`, `requests`, etc. - those are for native Application Insights queries, not Log Analytics queries.
