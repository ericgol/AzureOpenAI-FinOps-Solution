# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is an Azure OpenAI FinOps (Financial Operations) solution that tracks and analyzes costs of Azure OpenAI services accessed through Azure API Management (APIM). The solution correlates API telemetry with cost data to enable per-user and per-store cost analysis and reporting.

## Architecture Overview

The solution follows a **7-step data pipeline architecture**:

1. **APIM Telemetry Collection** → Log Analytics workspace captures gateway logs with custom attributes
2. **Timer-triggered Azure Function** → Python function runs every 6 minutes to orchestrate data collection  
3. **Telemetry Retrieval** → Queries Log Analytics for APIM call records using KQL
4. **Cost Data Collection** → Retrieves cost records via Azure Cost Management API
5. **Data Correlation** → Joins datasets and allocates costs proportionally based on usage
6. **Data Storage** → Stores correlated data in Azure Storage for persistence
7. **Power BI Reporting** → Leverages stored data for business intelligence dashboards

### Key Components

- **Azure Function App** (`src/functions/finops-data-collector/`) - Core Python data processing engine for cost correlation
- **EventHub Function App** (`src/functions/eventhub-to-appinsights/`) - Python function that forwards APIM telemetry from EventHub to Application Insights
- **APIM Policy** (`src/apim-policies/finops-telemetry-policy.xml`) - Captures custom attributes (device-id, store-number) and logs telemetry to EventHub
- **APIM EventHub Logger** (`infrastructure/bicep/modules/apim-eventhub-logger.bicep`) - Configures APIM logger to send events to EventHub
- **EventHub** - Receives telemetry events from APIM policy for real-time processing
- **Bicep Infrastructure** (`infrastructure/bicep/`) - Modular IaC templates for all Azure resources
- **Power BI Integration** - Pre-defined schema and dashboard templates for cost visualization

### Data Flow Architecture

```
API Calls → APIM Gateway → EventHub → EventHub Function → Application Insights
                ↓              ↓              ↓                    ↓
        Custom Headers    Real-time     Telemetry           Structured Traces
                ↓         Processing      Forward                  ↓
        Log Analytics → Timer Function → Cost Management → Storage → Power BI
                ↓              ↓                ↓              ↓
           KQL Queries    Cost Correlation    Data Storage   Reports
```

## Common Development Commands

### Infrastructure Deployment

**Development Environment (Quick Start):**
```bash
# Deploy complete dev environment
cd infrastructure/powershell/dev
./Deploy-DevEnvironment.ps1 -SubscriptionId "your-subscription-id"

# Preview deployment without applying changes
./Deploy-DevEnvironment.ps1 -SubscriptionId "your-subscription-id" -WhatIf
```

**Manual Bicep Deployment:**
```bash
# Set subscription and deploy main template
az account set --subscription "your-subscription-id"
az deployment sub create \
  --location "East US 2" \
  --template-file infrastructure/bicep/main.bicep \
  --parameters environment=dev \
               projectName=finops-aoai \
               apimSku=Developer \
               enablePrivateNetworking=false
```

### Azure Functions Development

**Local Development:**
```bash
cd src/functions/finops-data-collector

# Install Python dependencies
python -m pip install -r requirements.txt

# Run function locally (requires local.settings.json)
func start

# Test individual function
func start --functions finops_timer_trigger
```

**Function Deployment:**
```bash
# Deploy FinOps data collector function
func azure functionapp publish your-finops-function-app-name --python

# Deploy EventHub to AppInsights function
cd src/functions/eventhub-to-appinsights
func azure functionapp publish your-eventhub-function-app-name --python

# Deploy with remote build (recommended for production)
func azure functionapp publish your-function-app-name --python --build remote
```

### Testing and Validation

**Test APIM Endpoint:**
```bash
# Replace with your actual APIM gateway URL and subscription key
# Test GPT-5 endpoint (when available)
curl -X POST "https://your-apim-gateway/openai/deployments/gpt-5/chat/completions?api-version=2024-02-01" \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: your-subscription-key" \
  -H "device-id: test-device-001" \
  -H "store-number: store-456" \
  -d '{
    "messages": [{"role": "user", "content": "Test GPT-5 for FinOps cost tracking."}],
    "max_tokens": 50
  }'

# Test GPT-4 endpoint
curl -X POST "https://your-apim-gateway/openai/deployments/gpt-4/chat/completions?api-version=2024-02-01" \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: your-subscription-key" \
  -H "device-id: test-device-001" \
  -H "store-number: store-456" \
  -d '{
    "messages": [{"role": "user", "content": "Test GPT-4 for FinOps cost tracking."}],
    "max_tokens": 50
  }'

# Test GPT-3.5-Turbo endpoint  
curl -X POST "https://your-apim-gateway/openai/deployments/gpt-35-turbo/chat/completions?api-version=2024-02-01" \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: your-subscription-key" \
  -H "device-id: test-user-123" \
  -H "store-number: store-456" \
  -d '{
    "messages": [{"role": "user", "content": "Hello, this is a test message for FinOps tracking."}],
    "max_tokens": 50
  }'
```

**Query Log Analytics (KQL):**
```kql
# Check APIM telemetry collection
ApiManagementGatewayLogs
| where TimeGenerated >= ago(1h)
| where OperationName != ""
| take 10

# Verify Application Insights telemetry
traces 
| where message contains "FinOpsApiCall"
| order by timestamp desc
| take 10
```

**Validate Function Execution:**
```bash
# Check FinOps data collector function logs
az functionapp logs tail --name your-finops-function-app-name --resource-group your-resource-group

# Check EventHub to AppInsights function logs
az functionapp logs tail --name your-eventhub-function-app-name --resource-group your-resource-group

# Monitor specific function execution
az monitor log-analytics query \
  --workspace your-log-analytics-workspace-id \
  --analytics-query "FunctionAppLogs | where FunctionName == 'finops_timer_trigger' | order by TimeGenerated desc | take 10"

# Monitor EventHub function execution
az monitor log-analytics query \
  --workspace your-log-analytics-workspace-id \
  --analytics-query "FunctionAppLogs | where FunctionName == 'eventhub_to_appinsights' | order by TimeGenerated desc | take 10"
```

### Data Analysis and Debugging

**Check Storage Data:**
```bash
# List containers and verify data presence
az storage container list --account-name your-storage-account

# Download sample data for inspection
az storage blob download \
  --account-name your-storage-account \
  --container-name finops-data \
  --name "2024/01/15/correlated-data.json" \
  --file sample-data.json
```

**Python Development and Testing:**
```bash
# Run unit tests
cd src/functions/finops-data-collector
python -m pytest tests/unit/ -v

# Run with coverage
python -m pytest tests/unit/ --cov=shared --cov-report=html

# Format code
black shared/ finops_timer_trigger/
flake8 shared/ finops_timer_trigger/

# Type checking
mypy shared/ finops_timer_trigger/
```

## Key Configuration Patterns

### Environment Variables (Function App)

The solution uses environment-based configuration through the `FinOpsConfig` class:

```python
# Required variables
LOG_ANALYTICS_WORKSPACE_ID="workspace-guid"
COST_MANAGEMENT_SCOPE="/subscriptions/sub-id"
STORAGE_ACCOUNT_NAME="storageaccount"

# Optional but recommended
ENVIRONMENT="dev|staging|prod"
DATA_COLLECTION_INTERVAL_MINUTES="6"
LOOKBACK_HOURS="1"
DEFAULT_ALLOCATION_METHOD="proportional|equal|usage-based|token-based"
```

### APIM Policy Customization

The telemetry policy captures custom attributes from headers or query parameters and sends them to EventHub:

```xml
<!-- Extract device-id from multiple possible sources -->
<set-variable name="device-id" value="@{
    var deviceId = context.Request.Headers.GetValueOrDefault("device-id", "");
    if (string.IsNullOrEmpty(deviceId)) {
        deviceId = context.Request.Url.Query.GetValueOrDefault("device-id", "");
    }
    return string.IsNullOrEmpty(deviceId) ? "unknown" : deviceId;
}" />

<!-- Log to EventHub using configured logger -->
<log-to-eventhub logger-id="finops-eventhub-logger" partition-id="0">
    @{
        var telemetryData = new JObject(
            new JProperty("eventType", "FinOpsApiCall"),
            new JProperty("deviceId", context.Variables["device-id"]),
            new JProperty("storeNumber", context.Variables["store-number"])
            // ... other properties
        );
        return telemetryData.ToString();
    }
</log-to-eventhub>
```

**Important**: The `logger-id` in the policy must match the logger name configured in the Bicep template (`finops-eventhub-logger`).

### Cost Allocation Logic

The solution supports multiple cost allocation methods configured via environment variables:

- **proportional**: Allocates cost based on token usage ratio
- **equal**: Equal distribution among users/stores  
- **usage-based**: Based on API call frequency
- **token-based**: Direct token count correlation

## Development Workflow

### Making Infrastructure Changes

1. **Modify Bicep templates** in `infrastructure/bicep/modules/`
2. **Test changes locally** using `az deployment sub what-if`
3. **Deploy to dev environment** using the PowerShell script
4. **Validate resources** in Azure portal
5. **Update parameters** for staging/prod as needed

### Function Development

**FinOps Data Collector Function:**
1. **Set up local environment** with `local.settings.json` (see template in `src/configs/`)
2. **Install dependencies** with `pip install -r requirements.txt`
3. **Develop and test locally** using Azure Functions Core Tools
4. **Run unit tests** with pytest
5. **Deploy and validate** in dev environment

**EventHub to AppInsights Function:**
1. **Set up local environment** with `local.settings.json.template` in `src/functions/eventhub-to-appinsights/`
2. **Configure EventHub connection** string and Application Insights connection string
3. **Install dependencies** with `pip install -r requirements.txt`
4. **Test locally** with `func start` (requires EventHub access)
5. **Deploy and monitor** telemetry flow

### Adding New Data Sources

To extend the solution for additional telemetry sources:

1. **Create new collector class** in `src/functions/finops-data-collector/shared/`
2. **Implement data collection interface** following existing patterns
3. **Update correlation logic** in `data_correlator.py`
4. **Add KQL queries** to `config.py`
5. **Test end-to-end** with sample data

## Power BI Integration

The solution stores data in Azure Storage following a predefined schema optimized for Power BI:

### Key Data Tables
- **FinOpsCorrelatedData**: Main fact table with allocated costs
- **Partition Structure**: Organized by date (`YYYY/MM/DD/`) for incremental refresh
- **File Formats**: Supports both JSON and Parquet (recommended for performance)

### Connecting Power BI
1. Use Azure Blob Storage connector
2. Point to `finops-data` container
3. Set up incremental refresh for daily partitions
4. Apply transformations to remove "unknown" users/stores

## Troubleshooting Common Issues

### Function App Authentication Errors
- Verify managed identity has proper RBAC roles
- Check Cost Management Reader role assignment
- Validate Log Analytics Reader permissions

### Missing Telemetry Data
- Confirm APIM diagnostic settings are enabled
- Verify policy is applied to correct operations
- Check Application Insights connection string

### Cost Data Delays
- Azure cost data has 4-8 hour delay
- Adjust `LOOKBACK_HOURS` for data freshness requirements
- Monitor Cost Management API rate limits

### Storage Connection Issues
- Verify storage account permissions for managed identity
- Check container names match configuration
- Validate network access (private endpoints if configured)

## Security Considerations

- **Managed Identity**: All Azure service authentication uses managed identity
- **Private Networking**: Production deployments support VNET integration
- **Key Vault Integration**: Sensitive configuration can be stored in Key Vault
- **RBAC**: Principle of least privilege for all service permissions
- **Data Encryption**: All data encrypted at rest and in transit

## Performance Optimization

### Function App
- **Consumption Plan**: Suitable for dev/light workloads (6-minute timer)
- **Premium Plan**: Recommended for production with consistent load
- **Batch Processing**: Configurable batch sizes for large datasets
- **Concurrency**: Adjustable concurrent request limits

### Data Storage
- **Partitioning**: Date-based partitions for efficient querying
- **File Formats**: Parquet recommended for large datasets
- **Compression**: Built-in compression reduces storage costs
- **Retention**: Configurable data lifecycle policies