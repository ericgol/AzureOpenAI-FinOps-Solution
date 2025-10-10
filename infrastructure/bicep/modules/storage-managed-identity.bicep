// Storage Account Managed Identity Role Assignments
@description('Storage account resource ID')
param storageAccountId string

@description('Function App principal ID')
param functionAppPrincipalId string


// Get reference to existing storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: split(storageAccountId, '/')[8] // Extract storage account name from resource ID
}

// Storage Blob Data Contributor role for Function App managed identity
resource storageBlobDataContributor 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
}

resource functionAppBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccountId, functionAppPrincipalId, storageBlobDataContributor.id)
  properties: {
    roleDefinitionId: storageBlobDataContributor.id
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Table Data Contributor role for Function App managed identity
resource storageTableDataContributor 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3' // Storage Table Data Contributor
}

resource functionAppTableRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccountId, functionAppPrincipalId, storageTableDataContributor.id)
  properties: {
    roleDefinitionId: storageTableDataContributor.id
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage File Data SMB Share Contributor for Function App content share
resource storageFileDataContributor 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '0c867c2a-1d8c-454a-a3db-ab2ea1bdc8bb' // Storage File Data SMB Share Contributor
}

resource functionAppFileRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccountId, functionAppPrincipalId, storageFileDataContributor.id)
  properties: {
    roleDefinitionId: storageFileDataContributor.id
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output blobRoleAssignmentId string = functionAppBlobRoleAssignment.id
output tableRoleAssignmentId string = functionAppTableRoleAssignment.id
output fileRoleAssignmentId string = functionAppFileRoleAssignment.id