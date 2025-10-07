// EventHub to Application Insights Function App Bicep Module
// Deploys a Python Function App that processes EventHub telemetry and forwards to AppInsights

@description('Function App name')
param functionAppName string

@description('Location for all resources')
param location string = resourceGroup().location

@description('Common tags for all resources')
param tags object = {}

@description('Storage Account name for function app')
param storageAccountName string

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('EventHub connection string')
param eventHubConnectionString string

@description('EventHub name')
param eventHubName string = 'finops-telemetry'

@description('Environment (dev, staging, prod)')
param environment string

@description('Virtual network subnet ID for function app (optional)')
param subnetId string = ''

@description('Enable private networking')
param enablePrivateNetworking bool = false

// App Service Plan for Function App
resource appServicePlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: '${functionAppName}-plan'
  location: location
  tags: tags
  sku: {
    name: environment == 'prod' ? 'EP1' : 'Y1'
    tier: environment == 'prod' ? 'ElasticPremium' : 'Dynamic'
  }
  kind: 'functionapp'
  properties: {
    reserved: true // Required for Linux
  }
}

// Function App
resource functionApp 'Microsoft.Web/sites@2022-09-01' = {
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
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=${az.environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'EventHubConnection'
          value: eventHubConnectionString
        }
        {
          name: 'EventHubName'
          value: eventHubName
        }
        {
          name: 'ENVIRONMENT'
          value: environment
        }
        {
          name: 'LOG_LEVEL'
          value: environment == 'prod' ? 'WARNING' : 'INFO'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=${az.environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(functionAppName)
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
      ]
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      cors: {
        allowedOrigins: [
          'https://portal.azure.com'
        ]
      }
      use32BitWorkerProcess: false
      pythonVersion: '3.11'
    }
    httpsOnly: true
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
  }
}

// Configure VNET integration if private networking is enabled
resource vnetIntegration 'Microsoft.Web/sites/networkConfig@2022-09-01' = if (enablePrivateNetworking && !empty(subnetId)) {
  parent: functionApp
  name: 'virtualNetwork'
  properties: {
    subnetResourceId: subnetId
    swiftSupported: true
  }
}

// Get reference to existing storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

// Outputs
output functionAppName string = functionApp.name
output functionAppPrincipalId string = functionApp.identity.principalId
output functionAppDefaultHostname string = functionApp.properties.defaultHostName