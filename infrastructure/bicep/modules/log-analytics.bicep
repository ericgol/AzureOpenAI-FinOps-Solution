// Log Analytics Workspace for FinOps solution
@description('Log Analytics workspace name')
param workspaceName string

@description('Location for the workspace')
param location string

@description('Resource tags')
param tags object = {}

@description('Data retention in days')
param retentionInDays int = 30

@description('Daily quota in GB')
param dailyQuotaGb int = 1

// Log Analytics Workspace
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
    workspaceCapping: {
      dailyQuotaGb: dailyQuotaGb
    }
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

// Note: Custom tables and saved queries will be created later via deployment scripts
// or when the Function Apps first send data. This avoids workspace activation timing issues.
// The workspace needs to be fully provisioned and active before child resources can be created.

// Outputs
output workspaceId string = logAnalyticsWorkspace.id
output workspaceName string = logAnalyticsWorkspace.name
output customerId string = logAnalyticsWorkspace.properties.customerId
