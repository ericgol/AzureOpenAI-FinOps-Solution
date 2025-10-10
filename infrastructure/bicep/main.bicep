// Main deployment template for Azure OpenAI FinOps Solution
targetScope = 'subscription'

@description('Environment name (dev, staging, prod)')
param environment string = 'dev'

@description('Primary Azure region')
param location string = 'East US 2'

@description('Project name prefix')
param projectName string = 'finops-aoai'

@description('Unique suffix for resource names')
param uniqueSuffix string = uniqueString(subscription().subscriptionId, projectName, environment)

// Storage account name must be 3-24 chars, lowercase letters and numbers only
// Transform: 'finops-aoai' + 'dev' + 'sa' + 'uniqueHash' → 'finopsaoaidevsa' + first10chars(hash)
var cleanProjectName = replace(replace(projectName, '-', ''), '_', '')
var storageAccountName = take('${cleanProjectName}${environment}sa${take(uniqueSuffix, 10)}', 24)

@description('Resource group name')
param resourceGroupName string = '${projectName}-${environment}-rg'

@description('Tags to apply to all resources')
param tags object = {
  Environment: environment
  Project: 'Azure-OpenAI-FinOps'
  ManagedBy: 'Bicep'
  CostCenter: 'IT-FinOps'
}

@description('APIM SKU (Developer or Premium)')
@allowed(['Developer', 'Premium'])
param apimSku string = 'Developer'

@description('Enable private networking (required for enterprise compliance)')
param enablePrivateNetworking bool = true

@description('Cost Management scope (subscription or resource group)')
param costManagementScope string = subscription().id

// Create resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// Deploy Log Analytics Workspace
module logAnalytics 'modules/log-analytics.bicep' = {
  scope: rg
  name: 'deploy-log-analytics'
  params: {
    workspaceName: '${projectName}-${environment}-law-${uniqueSuffix}'
    location: location
    tags: tags
    retentionInDays: environment == 'prod' ? 90 : 30
    dailyQuotaGb: environment == 'prod' ? 10 : 1
  }
}

// Deploy Application Insights
module appInsights 'modules/application-insights.bicep' = {
  scope: rg
  name: 'deploy-app-insights'
  params: {
    appInsightsName: '${projectName}-${environment}-ai-${uniqueSuffix}'
    location: location
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
  }
}

// Deploy Storage Account
module storage 'modules/storage-account.bicep' = {
  scope: rg
  name: 'deploy-storage'
  params: {
    storageAccountName: storageAccountName
    location: location
    tags: tags
    environment: environment
    enablePrivateEndpoint: enablePrivateNetworking
    functionSubnetId: networking.outputs.functionSubnetId
    apimSubnetId: networking.outputs.apimSubnetId
    privateEndpointSubnetId: networking.outputs.privateEndpointSubnetId
  }
}

// Deploy Virtual Network (always deployed for enterprise compliance)
module networking 'modules/networking.bicep' = {
  scope: rg
  name: 'deploy-networking'
  params: {
    vnetName: '${projectName}-${environment}-vnet-${uniqueSuffix}'
    location: location
    tags: tags
  }
}

// Deploy Private DNS Zones
module privateDnsZones 'modules/private-dns-zones.bicep' = {
  scope: rg
  name: 'deploy-private-dns-zones'
  params: {
    vnetId: networking.outputs.vnetId
    location: 'global'
    tags: tags
  }
}

// Deploy API Management
module apim 'modules/api-management.bicep' = {
  scope: rg
  name: 'deploy-apim'
  params: {
    apimName: '${projectName}-${environment}-apim-${uniqueSuffix}'
    location: location
    tags: tags
    sku: apimSku
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    appInsightsInstrumentationKey: appInsights.outputs.instrumentationKey
    subnetId: networking.outputs.apimSubnetId
    enablePrivateNetworking: enablePrivateNetworking
  }
}

// Deploy Azure Function App
module functionApp 'modules/function-app.bicep' = {
  scope: rg
  name: 'deploy-function-app'
  params: {
    functionAppName: '${projectName}-${environment}-func-${uniqueSuffix}'
    location: location
    tags: tags
    storageAccountName: storage.outputs.storageAccountName
    appInsightsInstrumentationKey: appInsights.outputs.instrumentationKey
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    costManagementScope: costManagementScope
    environment: environment
    subnetId: networking.outputs.functionSubnetId
    enableVnetIntegration: enablePrivateNetworking
    useManagedIdentity: enablePrivateNetworking
  }
}

// Role assignments for Function App managed identity
// Cost Management Reader role for accessing cost data (subscription scope)
resource costManagementReaderRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '72fafb9e-0641-4937-9268-a91bfd8191a4' // Cost Management Reader
}

resource costManagementRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().id, functionApp.name, costManagementReaderRole.id)
  properties: {
    roleDefinitionId: costManagementReaderRole.id
    principalId: functionApp.outputs.functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Deploy storage account managed identity role assignments
module storageManagedIdentity 'modules/storage-managed-identity.bicep' = {
  scope: rg
  name: 'deploy-storage-managed-identity'
  params: {
    storageAccountId: storage.outputs.storageAccountId
    functionAppPrincipalId: functionApp.outputs.functionAppPrincipalId
  }
}

// Deploy resource group scoped role assignments
module functionAppRoleAssignments 'modules/role-assignments.bicep' = {
  scope: rg
  name: 'deploy-function-role-assignments'
  params: {
    functionAppPrincipalId: functionApp.outputs.functionAppPrincipalId
    functionAppName: functionApp.outputs.functionAppName
  }
}

// Deploy EventHub for APIM telemetry
module eventHub 'modules/event-hub.bicep' = {
  scope: rg
  name: 'deploy-event-hub'
  params: {
    eventHubNamespaceName: '${projectName}-${environment}-eh-${uniqueSuffix}'
    eventHubName: 'finops-telemetry'
    location: location
    tags: tags
    eventHubSku: environment == 'prod' ? 'Standard' : 'Basic'
    eventHubCapacity: environment == 'prod' ? 2 : 1
    environment: environment
  }
}

// Deploy EventHub to Application Insights Function App
module eventHubFunctionApp 'modules/eventhub-function-app.bicep' = {
  scope: rg
  name: 'deploy-eventhub-function-app'
  params: {
    functionAppName: '${projectName}-${environment}-ehfunc-${uniqueSuffix}'
    location: location
    tags: tags
    storageAccountName: storage.outputs.storageAccountName
    appInsightsConnectionString: appInsights.outputs.connectionString
    eventHubConnectionString: eventHub.outputs.functionConnectionString
    eventHubName: eventHub.outputs.eventHubName
    environment: environment
    subnetId: networking.outputs.functionSubnetId
    enablePrivateNetworking: enablePrivateNetworking
  }
}

// Configure APIM EventHub Logger
module apimEventHubLogger 'modules/apim-eventhub-logger.bicep' = {
  scope: rg
  name: 'deploy-apim-eventhub-logger'
  params: {
    apimName: apim.outputs.apimName
    eventHubName: eventHub.outputs.eventHubName
    eventHubConnectionString: eventHub.outputs.apimConnectionString
    loggerName: 'finops-eventhub-logger'
    isBuffered: true
  }
}

// Deploy Key Vault for secrets management
module keyVault 'modules/key-vault.bicep' = {
  scope: rg
  name: 'deploy-key-vault'
  params: {
    keyVaultName: '${projectName}-${environment}-kv-${uniqueSuffix}'
    location: location
    tags: tags
    functionAppPrincipalId: functionApp.outputs.functionAppPrincipalId
    enablePrivateEndpoint: enablePrivateNetworking
    subnetId: networking.outputs.privateEndpointSubnetId
  }
}

// Outputs for reference by other deployments or scripts
output resourceGroupName string = rg.name
output logAnalyticsWorkspaceId string = logAnalytics.outputs.workspaceId
output logAnalyticsWorkspaceName string = logAnalytics.outputs.workspaceName
output appInsightsInstrumentationKey string = appInsights.outputs.instrumentationKey
output apimName string = apim.outputs.apimName
output apimGatewayUrl string = apim.outputs.gatewayUrl
output functionAppName string = functionApp.outputs.functionAppName
output eventHubFunctionAppName string = eventHubFunctionApp.outputs.functionAppName
output eventHubNamespace string = eventHub.outputs.eventHubNamespaceName
output eventHubName string = eventHub.outputs.eventHubName
@secure()
output eventHubApimConnectionString string = eventHub.outputs.apimConnectionString
output apimLoggerName string = apimEventHubLogger.outputs.loggerName
output storageAccountName string = storage.outputs.storageAccountName
output keyVaultName string = keyVault.outputs.keyVaultName
output environment string = environment
output location string = location

// Debug output to verify storage account naming
output debugStorageAccountName string = storageAccountName
