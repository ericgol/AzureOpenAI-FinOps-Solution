// APIM EventHub Logger Bicep Module
// Configures API Management logger to send telemetry events to EventHub

@description('API Management service name')
param apimName string

@description('EventHub name for telemetry logging')
param eventHubName string

@description('EventHub connection string for APIM logger')
param eventHubConnectionString string

@description('Logger name in APIM')
param loggerName string = 'finops-eventhub-logger'

@description('Enable buffered logging for better performance')
param isBuffered bool = true

@description('Common tags for all resources')
param tags object = {}

// Reference to existing APIM service
resource apimService 'Microsoft.ApiManagement/service@2023-05-01-preview' existing = {
  name: apimName
}

// EventHub Logger configuration
resource eventHubLogger 'Microsoft.ApiManagement/service/loggers@2023-05-01-preview' = {
  parent: apimService
  name: loggerName
  properties: {
    loggerType: 'azureEventHub'
    description: 'EventHub logger for FinOps telemetry collection from APIM policies'
    credentials: {
      name: eventHubName
      connectionString: eventHubConnectionString
    }
    isBuffered: isBuffered
    resourceId: null // Not needed for EventHub logger
  }
}

// Outputs
output loggerName string = eventHubLogger.name
output loggerId string = eventHubLogger.id