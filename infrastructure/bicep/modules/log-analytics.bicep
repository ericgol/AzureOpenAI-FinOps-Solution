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

// Custom tables for FinOps data
resource finOpsApiCallsTable 'Microsoft.OperationalInsights/workspaces/tables@2022-10-01' = {
  parent: logAnalyticsWorkspace
  name: 'FinOpsApiCalls_CL'
  properties: {
    plan: 'Analytics'
    schema: {
      name: 'FinOpsApiCalls_CL'
      columns: [
        {
          name: 'TimeGenerated'
          type: 'datetime'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'deviceId'
          type: 'string'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'storeNumber'
          type: 'string'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'ApiName'
          type: 'string'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'RequestId'
          type: 'string'
          isDefaultDisplay: false
          isHidden: false
        }
        {
          name: 'ResponseTime'
          type: 'int'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'StatusCode'
          type: 'int'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'TokensUsed'
          type: 'int'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'ResourceId'
          type: 'string'
          isDefaultDisplay: false
          isHidden: false
        }
      ]
    }
  }
}

resource finOpsCostDataTable 'Microsoft.OperationalInsights/workspaces/tables@2022-10-01' = {
  parent: logAnalyticsWorkspace
  name: 'FinOpsCostData_CL'
  properties: {
    plan: 'Analytics'
    schema: {
      name: 'FinOpsCostData_CL'
      columns: [
        {
          name: 'TimeGenerated'
          type: 'datetime'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'Date'
          type: 'datetime'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'ResourceId'
          type: 'string'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'ResourceName'
          type: 'string'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'Cost'
          type: 'real'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'Currency'
          type: 'string'
          isDefaultDisplay: false
          isHidden: false
        }
        {
          name: 'deviceId'
          type: 'string'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'storeNumber'
          type: 'string'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'AllocatedCost'
          type: 'real'
          isDefaultDisplay: true
          isHidden: false
        }
        {
          name: 'UsageShare'
          type: 'real'
          isDefaultDisplay: false
          isHidden: false
        }
      ]
    }
  }
}

// Saved queries for common FinOps analysis
resource apiUsageQuery 'Microsoft.OperationalInsights/workspaces/savedSearches@2020-08-01' = {
  parent: logAnalyticsWorkspace
  name: 'FinOpsApiUsageAnalysis'
  properties: {
    category: 'FinOps'
    displayName: 'API Usage Analysis'
    query: '''
FinOpsApiCalls_CL
| where TimeGenerated >= ago(1d)
| summarize 
    TotalCalls = count(),
    AvgResponseTime = avg(ResponseTime),
    TotalTokens = sum(TokensUsed),
    SuccessRate = countif(StatusCode < 400) * 100.0 / count()
    by deviceId, storeNumber, ApiName
| order by TotalCalls desc
'''
    version: 2
  }
}

resource costAllocationQuery 'Microsoft.OperationalInsights/workspaces/savedSearches@2020-08-01' = {
  parent: logAnalyticsWorkspace
  name: 'FinOpsCostAllocation'
  properties: {
    category: 'FinOps'
    displayName: 'Cost Allocation by User/Store'
    query: '''
FinOpsCostData_CL
| where TimeGenerated >= ago(7d)
| summarize 
    TotalAllocatedCost = sum(AllocatedCost),
    AvgDailyCost = avg(AllocatedCost)
    by deviceId, storeNumber, bin(Date, 1d)
| order by Date desc, TotalAllocatedCost desc
'''
    version: 2
  }
}

// Outputs
output workspaceId string = logAnalyticsWorkspace.id
output workspaceName string = logAnalyticsWorkspace.name
output customerId string = logAnalyticsWorkspace.properties.customerId
