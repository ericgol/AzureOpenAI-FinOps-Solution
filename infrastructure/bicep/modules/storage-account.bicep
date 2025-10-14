// Storage Account for FinOps solution
@description('Storage account name')
param storageAccountName string

@description('Location for storage account')
param location string

@description('Resource tags')
param tags object = {}

@description('Environment name')
param environment string

@description('Enable private endpoint')
param enablePrivateEndpoint bool = false

@description('Private endpoint subnet ID')
param privateEndpointSubnetId string = ''

// Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: environment == 'prod' ? 'Standard_ZRS' : 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true // Keep enabled for Function App compatibility during transition
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    // Keep public access enabled during initial deployment
    // This will be restricted later by the storage-network-restriction module
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices,Logging,Metrics'
    }
    encryption: {
      services: {
        blob: {
          enabled: true
          keyType: 'Account'
        }
        file: {
          enabled: true
          keyType: 'Account'
        }
        table: {
          enabled: true
          keyType: 'Account'
        }
        queue: {
          enabled: true
          keyType: 'Account'
        }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

// Blob container for FinOps correlated data
resource finOpsDataContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/finops-data'
  properties: {
    publicAccess: 'None'
    metadata: {
      purpose: 'FinOps correlated cost and usage data'
      retention: environment == 'prod' ? '2years' : '90days'
    }
  }
}

// Container for raw telemetry data
resource rawTelemetryContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/raw-telemetry'
  properties: {
    publicAccess: 'None'
    metadata: {
      purpose: 'Raw telemetry data from APIM and Application Insights'
      retention: '30days'
    }
  }
}

// Container for cost data
resource costDataContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/cost-data'
  properties: {
    publicAccess: 'None'
    metadata: {
      purpose: 'Cost Management API data'
      retention: environment == 'prod' ? '2years' : '90days'
    }
  }
}

// Table for configuration and metadata
resource configTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageAccount.name}/default/configuration'
  properties: {}
}

// Table for user/store mappings
resource userMappingsTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageAccount.name}/default/usermappings'
  properties: {}
}

// Private endpoint for blob storage
resource blobPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-09-01' = if (enablePrivateEndpoint) {
  name: '${storageAccount.name}-blob-pe'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${storageAccount.name}-blob-connection'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: ['blob']
        }
      }
    ]
  }
}

// Private endpoint for file storage
resource filePrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-09-01' = if (enablePrivateEndpoint) {
  name: '${storageAccount.name}-file-pe'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${storageAccount.name}-file-connection'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: ['file']
        }
      }
    ]
  }
}

// Private endpoint for table storage
resource tablePrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-09-01' = if (enablePrivateEndpoint) {
  name: '${storageAccount.name}-table-pe'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${storageAccount.name}-table-connection'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: ['table']
        }
      }
    ]
  }
}

// Role assignments are handled separately in main template after Function App is created

// Outputs
output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output primaryEndpoints object = storageAccount.properties.primaryEndpoints
output finOpsDataContainerName string = 'finops-data'
output rawTelemetryContainerName string = 'raw-telemetry'
output costDataContainerName string = 'cost-data'