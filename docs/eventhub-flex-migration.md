# Migrating EventHub Function to Flex Consumption Plan

## Overview

The EventHub to Application Insights function can now be deployed on either:
- **Linux Consumption Plan** (default) - Traditional serverless, cold start delays
- **Flex Consumption Plan** (recommended) - Better performance, faster cold starts, more control

## Benefits of Flex Consumption

1. **Better Performance**: Faster cold starts and more consistent execution
2. **Cost Efficiency**: Pay per execution with better resource utilization
3. **Scalability**: Configure max instances (up to 1000)
4. **Memory Control**: Choose 2GB or 4GB per instance
5. **Identity-based Auth**: Uses managed identity for storage (more secure)

## Migration Steps

### Option 1: New Deployment with Flex Consumption

Deploy a new environment with Flex enabled:

```bash
az deployment sub create \
  --location "East US 2" \
  --template-file infrastructure/bicep/main.bicep \
  --parameters environment=dev \
               projectName=finops-aoai \
               useFlexConsumptionForEventHub=true
```

### Option 2: Update Existing Deployment

**Step 1: Backup current configuration**
```bash
# Export current function app settings
az functionapp config appsettings list \
  --name pike-dev-ehfunc-6v5sbjvrgatqy \
  --resource-group pike-dev-rg \
  --output json > eventhub-function-settings-backup.json
```

**Step 2: Delete existing function app (preserves data)**
```bash
# The function app must be deleted to change hosting plans
az functionapp delete \
  --name pike-dev-ehfunc-6v5sbjvrgatqy \
  --resource-group pike-dev-rg
```

**Step 3: Redeploy with Flex Consumption**
```bash
az deployment sub create \
  --location "East US 2" \
  --template-file infrastructure/bicep/main.bicep \
  --parameters environment=dev \
               projectName=finops-aoai \
               useFlexConsumptionForEventHub=true
```

**Step 4: Redeploy function code**
```bash
cd src/functions/eventhub-to-appinsights
func azure functionapp publish pike-dev-ehfunc-6v5sbjvrgatqy --python --build remote
```

## Configuration Differences

### Linux Consumption (Traditional)
```bicep
sku: {
  name: 'Y1'
  tier: 'Dynamic'
}
```
- Uses connection strings for EventHub
- Requires `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING`
- Cold start: 1-3 seconds

### Flex Consumption
```bicep
sku: {
  name: 'FC1'
  tier: 'FlexConsumption'
}
```
- Uses managed identity for EventHub (more secure)
- No file share required
- Cold start: <1 second
- Configurable: `maximumInstanceCount`, `instanceMemoryMB`

## Connection String Changes

### Before (Consumption)
```
EventHubConnection=Endpoint=sb://...;SharedAccessKeyName=...;SharedAccessKey=...
```

### After (Flex)
```
EventHubConnection__fullyQualifiedNamespace=your-namespace.servicebus.windows.net
```

Flex Consumption uses identity-based connections - the function's managed identity must have:
- **Azure Event Hubs Data Receiver** role on the EventHub namespace

## Monitoring

Both plans send telemetry to Application Insights. Check function health:

```bash
# View function logs
az monitor app-insights query \
  --app pike-dev-ai-6v5sbjvrgatqy \
  --resource-group pike-dev-rg \
  --analytics-query "requests | where cloud_RoleName contains 'ehfunc' | where timestamp >= ago(1h) | order by timestamp desc"
```

## Cost Comparison

### Consumption Plan
- $0.20 per million executions
- $0.000016/GB-s memory
- 400,000 GB-s free/month

### Flex Consumption  
- $0.18 per million executions (10% cheaper)
- Better resource utilization
- No free tier, but typically cheaper at scale

## Rollback Plan

If issues occur, redeploy with the original plan:

```bash
az deployment sub create \
  --location "East US 2" \
  --template-file infrastructure/bicep/main.bicep \
  --parameters environment=dev \
               projectName=finops-aoai \
               useFlexConsumptionForEventHub=false
```

## Validation

After migration, verify:

1. **Function is running**
   ```bash
   az functionapp show --name pike-dev-ehfunc-6v5sbjvrgatqy --resource-group pike-dev-rg --query state
   ```

2. **EventHub messages are being processed**
   ```kql
   traces 
   | where cloud_RoleName contains "ehfunc"
   | where message contains "FinOpsApiCall"
   | order by timestamp desc
   | take 10
   ```

3. **No errors in logs**
   ```kql
   exceptions
   | where cloud_RoleName contains "ehfunc"
   | where timestamp >= ago(1h)
   ```

## Troubleshooting

### Issue: Function not starting
- Verify storage account role assignment (Storage Blob Data Contributor)
- Check that deployment container exists in storage account

### Issue: EventHub connection errors  
- Verify managed identity has "Azure Event Hubs Data Receiver" role
- Check `EventHubConnection__fullyQualifiedNamespace` setting

### Issue: High latency
- Increase `instanceMemoryMB` from 2048 to 4096
- Increase `maximumInstanceCount` for better parallelism

## References

- [Azure Functions Flex Consumption Plan](https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan)
- [Identity-based connections](https://learn.microsoft.com/azure/azure-functions/functions-reference#configure-an-identity-based-connection)
