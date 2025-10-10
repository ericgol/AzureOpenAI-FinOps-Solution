// Event Hub Bicep Module for APIM Telemetry Collection
// Creates EventHub namespace and hub for receiving telemetry from APIM policy

@description('Event Hub namespace name')
param eventHubNamespaceName string

@description('Event Hub name')
param eventHubName string = 'finops-telemetry'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Common tags for all resources')
param tags object = {}

@description('EventHub SKU')
@allowed(['Basic', 'Standard', 'Premium'])
param eventHubSku string = 'Standard'

@description('EventHub capacity (throughput units)')
@minValue(1)
@maxValue(20)
param eventHubCapacity int = 1

@description('Message retention in days')
@minValue(1)
@maxValue(7)
param messageRetentionInDays int = 1

@description('Number of partitions')
@minValue(1)
@maxValue(32)
param partitionCount int = 2

@description('Environment (dev, staging, prod)')
param environment string

// EventHub Namespace
// Note: maximumThroughputUnits can only be set when isAutoInflateEnabled is true
resource eventHubNamespace 'Microsoft.EventHub/namespaces@2023-01-01-preview' = {
  name: eventHubNamespaceName
  location: location
  tags: tags
  sku: {
    name: eventHubSku
    tier: eventHubSku
    capacity: eventHubCapacity
  }
  properties: union(
    {
      minimumTlsVersion: '1.2'
      publicNetworkAccess: 'Enabled'
      disableLocalAuth: false
      zoneRedundant: environment == 'prod'
      isAutoInflateEnabled: environment == 'prod'
    },
    environment == 'prod' ? {
      maximumThroughputUnits: 10
    } : {}
  )
}

// EventHub
resource eventHub 'Microsoft.EventHub/namespaces/eventhubs@2023-01-01-preview' = {
  parent: eventHubNamespace
  name: eventHubName
  properties: {
    messageRetentionInDays: messageRetentionInDays
    partitionCount: partitionCount
    status: 'Active'
  }
}

// Consumer Group for Function App
// Note: Consumer Groups require Standard tier or above (not supported in Basic tier)
resource consumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2023-01-01-preview' = {
  parent: eventHub
  name: 'finops-function-app'
}

// Authorization rule for APIM (Send permission)
resource apimAuthRule 'Microsoft.EventHub/namespaces/eventhubs/authorizationRules@2023-01-01-preview' = {
  parent: eventHub
  name: 'APIMSendRule'
  properties: {
    rights: [
      'Send'
    ]
  }
}

// Authorization rule for Function App (Listen permission)
resource functionAuthRule 'Microsoft.EventHub/namespaces/eventhubs/authorizationRules@2023-01-01-preview' = {
  parent: eventHub
  name: 'FunctionListenRule'
  properties: {
    rights: [
      'Listen'
    ]
  }
}

// Outputs
output eventHubNamespaceName string = eventHubNamespace.name
output eventHubName string = eventHub.name
output eventHubId string = eventHub.id
@secure()
output apimConnectionString string = apimAuthRule.listKeys().primaryConnectionString
@secure()
output functionConnectionString string = functionAuthRule.listKeys().primaryConnectionString
output eventHubEndpoint string = eventHubNamespace.properties.serviceBusEndpoint
