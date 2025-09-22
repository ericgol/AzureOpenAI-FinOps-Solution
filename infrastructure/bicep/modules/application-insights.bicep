// Application Insights for FinOps solution
@description('Application Insights name')
param appInsightsName string

@description('Location for Application Insights')
param location string

@description('Resource tags')
param tags object = {}

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string

// Application Insights
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceId
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// Outputs
output appInsightsName string = applicationInsights.name
output appInsightsId string = applicationInsights.id
output instrumentationKey string = applicationInsights.properties.InstrumentationKey
output connectionString string = applicationInsights.properties.ConnectionString