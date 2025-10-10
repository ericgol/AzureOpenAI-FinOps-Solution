// Private DNS Zones for Private Endpoints
@description('Virtual network ID to link DNS zones to')
param vnetId string

@description('Location for DNS zones')
param location string = 'global'

@description('Resource tags')
param tags object = {}

// DNS zone for Storage Account blob endpoints
resource storageBlobDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.blob.${az.environment().suffixes.storage}'
  location: location
  tags: tags
}

resource storageBlobDnsZoneVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: storageBlobDnsZone
  name: 'storage-blob-vnet-link'
  location: location
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

// DNS zone for Storage Account file endpoints
resource storageFileDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.file.${az.environment().suffixes.storage}'
  location: location
  tags: tags
}

resource storageFileDnsZoneVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: storageFileDnsZone
  name: 'storage-file-vnet-link'
  location: location
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

// DNS zone for Storage Account table endpoints
resource storageTableDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.table.${az.environment().suffixes.storage}'
  location: location
  tags: tags
}

resource storageTableDnsZoneVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: storageTableDnsZone
  name: 'storage-table-vnet-link'
  location: location
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

// DNS zone for Key Vault endpoints
resource keyVaultDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: location
  tags: tags
}

resource keyVaultDnsZoneVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: keyVaultDnsZone
  name: 'keyvault-vnet-link'
  location: location
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

// Outputs
output storageBlobDnsZoneId string = storageBlobDnsZone.id
output storageFileDnsZoneId string = storageFileDnsZone.id
output storageTableDnsZoneId string = storageTableDnsZone.id
output keyVaultDnsZoneId string = keyVaultDnsZone.id