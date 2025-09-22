# Quick Start Deployment Guide

This guide will help you deploy the Azure OpenAI FinOps solution in your development environment within 30 minutes.

## Prerequisites

Before you begin, ensure you have:

1. **Azure Subscription** with Contributor access
2. **Azure CLI** installed and authenticated
3. **PowerShell 7+** installed
4. **Azure Functions Core Tools** (optional, for function deployment)
5. **Python 3.9+** (for local development)

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd AzureOpenAI_FinOps_Solution

# Verify directory structure
ls -la
```

## Step 2: Deploy Infrastructure

### Option A: PowerShell Deployment (Recommended)

```powershell
# Navigate to deployment scripts
cd infrastructure/powershell/dev

# Deploy with your subscription ID
./Deploy-DevEnvironment.ps1 -SubscriptionId "YOUR_SUBSCRIPTION_ID"

# For a preview without deployment
./Deploy-DevEnvironment.ps1 -SubscriptionId "YOUR_SUBSCRIPTION_ID" -WhatIf
```

### Option B: Manual Bicep Deployment

```bash
# Login to Azure
az login

# Set your subscription
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Deploy the main template
az deployment sub create \
  --location "East US 2" \
  --template-file infrastructure/bicep/main.bicep \
  --parameters environment=dev \
               projectName=finops-aoai \
               apimSku=Developer \
               enablePrivateNetworking=false
```

## Step 3: Configure Azure OpenAI Integration

After deployment, you need to configure APIM to connect to your Azure OpenAI service:

1. **Get deployment outputs:**
   ```powershell
   # Check deployment outputs file
   cat infrastructure/powershell/dev/deployment-outputs.json
   ```

2. **Configure APIM backend:**
   - Navigate to your APIM service in Azure Portal
   - Go to APIs > OpenAI API > Settings
   - Update the service URL to point to your Azure OpenAI endpoint:
     ```
     https://YOUR-OPENAI-SERVICE.openai.azure.com
     ```

3. **Add your OpenAI API key:**
   - In APIM, go to Named Values
   - Create a new named value: `openai-api-key`
   - Set the value to your Azure OpenAI API key
   - Mark it as secret

## Step 4: Test the Setup

### Test APIM Endpoint

```bash
# Get your APIM gateway URL from deployment outputs
APIM_URL="https://YOUR-APIM-GATEWAY-URL/openai"

# Test with curl (replace with your subscription key)
curl -X POST "$APIM_URL/deployments/gpt-35-turbo/chat/completions?api-version=2024-02-01" \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: YOUR_SUBSCRIPTION_KEY" \
  -H "user-id: test-user-123" \
  -H "store-id: store-456" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello, this is a test message for FinOps tracking."}
    ],
    "max_tokens": 50
  }'
```

### Verify Telemetry Collection

1. **Check Application Insights:**
   - Navigate to your Application Insights resource
   - Go to Logs and run:
     ```kql
     traces 
     | where message contains "FinOpsApiCall"
     | order by timestamp desc
     | take 10
     ```

2. **Check Function App Logs:**
   - Navigate to your Function App
   - Go to Functions > finops_timer_trigger > Monitor
   - Verify the function runs every 6 minutes

## Step 5: Verify Data Flow

After running a few test requests and waiting for the timer function to execute:

1. **Check Storage Account:**
   - Navigate to your Storage Account
   - Check containers: `finops-data`, `raw-telemetry`, `cost-data`
   - Verify data is being stored

2. **Check Log Analytics:**
   - Navigate to your Log Analytics workspace
   - Run queries to verify data collection:
     ```kql
     ApiManagementGatewayLogs
     | where TimeGenerated >= ago(1h)
     | where OperationName != ""
     | take 10
     ```

## Common Issues & Solutions

### Issue: APIM deployment takes too long
**Solution:** APIM deployment can take 30-45 minutes. Use `-WhatIf` first to validate configuration.

### Issue: Function app authentication errors
**Solution:** Verify the managed identity has been assigned proper roles. Check the Bicep templates for role assignments.

### Issue: No telemetry data in Log Analytics
**Solution:** 
1. Verify APIM diagnostic settings are enabled
2. Check that the APIM policy is applied correctly
3. Ensure requests are being made to the correct APIM endpoint

### Issue: Cost data not appearing
**Solution:**
1. Cost data has a delay of 4-8 hours in Azure
2. Verify the Function App has Cost Management Reader role
3. Check the cost management scope configuration

## Next Steps

1. **Configure User/Store Mappings:** Update the user and store ID mapping logic in the Function App
2. **Set up Power BI:** Use the correlated data in storage for Power BI reports
3. **Customize Cost Allocation:** Modify the cost allocation algorithm based on your requirements
4. **Production Deployment:** Follow the production deployment guide for scaling

## Environment Variables Reference

Key environment variables set automatically by deployment:

- `LOG_ANALYTICS_WORKSPACE_ID`: Your Log Analytics workspace
- `COST_MANAGEMENT_SCOPE`: Subscription scope for cost data
- `STORAGE_ACCOUNT_NAME`: Storage account for data persistence
- `DATA_COLLECTION_INTERVAL`: Timer function interval (6 minutes)

## Support

For issues:
1. Check the [troubleshooting guide](troubleshooting.md)
2. Review function app logs in Azure Portal
3. Verify resource permissions and role assignments

## Cost Estimates

**Development Environment:**
- APIM Developer: ~$50/month
- Function App (Consumption): ~$5-10/month
- Storage Account: ~$5/month
- Log Analytics: ~$10-20/month
- **Total: ~$70-85/month**

**Production Environment:**
- APIM Premium: ~$1,000-2,000/month
- Function App (Premium): ~$150-300/month
- Storage Account: ~$20-50/month
- Log Analytics: ~$50-200/month
- **Total: ~$1,220-2,550/month** (depending on usage)