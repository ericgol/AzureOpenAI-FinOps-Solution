// Azure Function App for FinOps data collection
@description('Function App name')
param functionAppName string

@description('Location for Function App')
param location string

@description('Resource tags')
param tags object = {}

@description('Storage account name for Function App')
param storageAccountName string

@description('Application Insights instrumentation key')
param appInsightsInstrumentationKey string

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string

@description('Cost Management scope')
param costManagementScope string

@description('Environment name')
param environment string

@description('Subnet ID for private networking')
param subnetId string = ''

@description('Python version')
param pythonVersion string = '3.11'

@description('Enable VNet integration')
param enableVnetIntegration bool = false


@description('Enable managed identity for storage')
param useManagedIdentity bool = false

// App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${functionAppName}-plan'
  location: location
  tags: tags
  sku: {
    name: environment == 'prod' ? 'P1v3' : 'Y1'
    tier: environment == 'prod' ? 'PremiumV3' : 'Dynamic'
  }
  properties: {
    reserved: true
  }
  kind: 'linux'
}

// Function App
resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    reserved: true
    siteConfig: {
      linuxFxVersion: 'Python|${pythonVersion}'
      alwaysOn: environment == 'prod'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      http20Enabled: true
      functionAppScaleLimit: environment == 'prod' ? 20 : 10
      minimumElasticInstanceCount: environment == 'prod' ? 1 : 0
      appSettings: union([
        // Core Function App settings
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(functionAppName)
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: 'InstrumentationKey=${appInsightsInstrumentationKey};IngestionEndpoint=https://${location}.in.applicationinsights.azure.com/;LiveEndpoint=https://${location}.livediagnostics.monitor.azure.com/'
        }
        {
          name: 'LOG_ANALYTICS_WORKSPACE_ID'
          value: logAnalyticsWorkspaceId
        }
        {
          name: 'COST_MANAGEMENT_SCOPE'
          value: costManagementScope
        }
        {
          name: 'STORAGE_ACCOUNT_NAME'
          value: storageAccountName
        }
        {
          name: 'DATA_COLLECTION_INTERVAL'
          value: '0 */6 * * * *'
        }
        {
          name: 'ENVIRONMENT'
          value: environment
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'BUILD_FLAGS'
          value: 'UseExpressBuild'
        }
        {
          name: 'XDG_CACHE_HOME'
          value: '/tmp/.cache'
        }
      ], useManagedIdentity ? [
        // Managed identity storage settings
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccountName
        }
        {
          name: 'AzureWebJobsStorage__credential'
          value: 'managedidentity'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING__accountName'
          value: storageAccountName
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING__credential'
          value: 'managedidentity'
        }
      ] : [
        // Legacy connection string settings (fallback)
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=${az.environment().suffixes.storage};AccountKey=${listKeys(resourceId('Microsoft.Storage/storageAccounts', storageAccountName), '2023-01-01').keys[0].value}'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=${az.environment().suffixes.storage};AccountKey=${listKeys(resourceId('Microsoft.Storage/storageAccounts', storageAccountName), '2023-01-01').keys[0].value}'
        }
      ])
      vnetRouteAllEnabled: enableVnetIntegration // Route all traffic through VNet
    }
    httpsOnly: true
    publicNetworkAccess: enableVnetIntegration ? 'Disabled' : 'Enabled'
    virtualNetworkSubnetId: enableVnetIntegration ? subnetId : null
    vnetContentShareEnabled: useManagedIdentity // Use VNet for file share when using managed identity
  }
}

// Diagnostic settings for Function App
// Note: Diagnostic settings depend on Log Analytics workspace being active
resource functionAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: functionApp
  name: 'finops-function-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
        retentionPolicy: {
          enabled: true
          days: environment == 'prod' ? 730 : 90
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: true
          days: environment == 'prod' ? 730 : 90
        }
      }
    ]
  }
}

// Role assignments are handled in the main template to avoid scope conflicts

// Outputs
output functionAppName string = functionApp.name
output functionAppId string = functionApp.id
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output functionAppPrincipalId string = functionApp.identity.principalId
output appServicePlanId string = appServicePlan.id