// EventHub to Application Insights Function App - Flex Consumption Plan
// Deploys a Python Function App using Flex Consumption that processes EventHub telemetry

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

@description('Maximum instance count for Flex Consumption')
param maxInstanceCount int = environment == 'prod' ? 100 : 40

@description('Instance memory size in MB (2048, 4096)')
param instanceMemoryMB int = 2048

// Get reference to existing storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

// Flex Consumption Plan
resource flexPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${functionAppName}-flex-plan'
  location: location
  tags: tags
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  kind: 'functionapp'
  properties: {
    reserved: true // Required for Linux
  }
}

// Function App on Flex Consumption
resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: flexPlan.id
    reserved: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storageAccount.properties.primaryEndpoints.blob}deployments'
          authentication: {
            type: 'SystemAssignedIdentity'
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: maxInstanceCount
        instanceMemoryMB: instanceMemoryMB
      }
      runtime: {
        name: 'python'
        version: '3.12'
      }
    }
    siteConfig: {
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccountName
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
          name: 'EventHubConnection__fullyQualifiedNamespace'
          value: split(split(eventHubConnectionString, 'Endpoint=sb://')[1], '/')[0]
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
      ]
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      use32BitWorkerProcess: false
    }
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
  }
}

// Assign Storage Blob Data Contributor role to Function App for deployment storage
resource storageBlobContributorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
}

resource functionAppStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, functionApp.id, storageBlobContributorRole.id)
  properties: {
    roleDefinitionId: storageBlobContributorRole.id
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output functionAppName string = functionApp.name
output functionAppPrincipalId string = functionApp.identity.principalId
output functionAppDefaultHostname string = functionApp.properties.defaultHostName
output flexPlanId string = flexPlan.id
