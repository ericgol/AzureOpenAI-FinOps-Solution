// Role assignments module for Function App managed identity
@description('Function App Principal ID')
param functionAppPrincipalId string

@description('Function App Name for GUID generation')
param functionAppName string

// Log Analytics Reader role for querying workspace  
resource logAnalyticsReaderRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '73c42c96-874c-492b-b04d-ab87fe914b4a' // Log Analytics Reader
}

resource logAnalyticsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, functionAppName, logAnalyticsReaderRole.id)
  properties: {
    roleDefinitionId: logAnalyticsReaderRole.id
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Blob Data Contributor role for writing correlated data
resource storageBlobDataContributorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
}

resource storageBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, functionAppName, storageBlobDataContributorRole.id)
  properties: {
    roleDefinitionId: storageBlobDataContributorRole.id
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output logAnalyticsRoleAssignmentId string = logAnalyticsRoleAssignment.id
output storageBlobRoleAssignmentId string = storageBlobRoleAssignment.id