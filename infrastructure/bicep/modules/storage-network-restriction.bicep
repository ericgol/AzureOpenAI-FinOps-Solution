// Storage Account Network Restriction Update
// This module uses a deployment script to update storage account networking rules after Function App deployment

@description('Storage account name')
param storageAccountName string

@description('Location for deployment script')
param location string

@description('Enable private endpoint restrictions')
param enablePrivateEndpoint bool = false

@description('Function subnet ID for VNet rule')
param functionSubnetId string = ''

@description('APIM subnet ID for VNet rule')
param apimSubnetId string = ''

@description('Resource group name')
param resourceGroupName string

// Managed Identity for deployment script
resource scriptIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${storageAccountName}-script-identity'
  location: location
}

// Role assignment for storage account modification
resource storageContributorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '17d1049b-9a84-46fb-8f53-869881c3d3ab' // Storage Account Contributor
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, scriptIdentity.id, storageContributorRole.id)
  properties: {
    roleDefinitionId: storageContributorRole.id
    principalId: scriptIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Deployment script to update storage account network rules
resource updateStorageNetworkScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = if (enablePrivateEndpoint) {
  name: '${storageAccountName}-network-update'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${scriptIdentity.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.45.0'
    timeout: 'PT30M'
    retentionInterval: 'PT1H'
    scriptContent: '''
      echo "Updating storage account network rules..."
      echo "Storage Account: $STORAGE_ACCOUNT_NAME"
      echo "Resource Group: $RESOURCE_GROUP_NAME"
      
      # Update storage account to disable public access and add VNet rules
      az storage account update \
        --name "$STORAGE_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --public-network-access Disabled \
        --default-action Deny \
        --bypass AzureServices
      
      echo "Updated storage account public access and default action"
      
      # Add VNet rules for function and APIM subnets
      if [ -n "$FUNCTION_SUBNET_ID" ]; then
        echo "Adding function subnet rule: $FUNCTION_SUBNET_ID"
        az storage account network-rule add \
          --account-name "$STORAGE_ACCOUNT_NAME" \
          --resource-group "$RESOURCE_GROUP_NAME" \
          --subnet "$FUNCTION_SUBNET_ID"
      fi
      
      if [ -n "$APIM_SUBNET_ID" ]; then
        echo "Adding APIM subnet rule: $APIM_SUBNET_ID"
        az storage account network-rule add \
          --account-name "$STORAGE_ACCOUNT_NAME" \
          --resource-group "$RESOURCE_GROUP_NAME" \
          --subnet "$APIM_SUBNET_ID"
      fi
      
      echo "Storage network rules updated successfully"
    '''
    environmentVariables: [
      {
        name: 'STORAGE_ACCOUNT_NAME'
        value: storageAccountName
      }
      {
        name: 'RESOURCE_GROUP_NAME'
        value: resourceGroupName
      }
      {
        name: 'FUNCTION_SUBNET_ID'
        value: functionSubnetId
      }
      {
        name: 'APIM_SUBNET_ID'
        value: apimSubnetId
      }
    ]
  }
  dependsOn: [
    roleAssignment
  ]
}

// Outputs
output storageAccountName string = storageAccountName
output networkAclsApplied bool = enablePrivateEndpoint
output scriptIdentityId string = scriptIdentity.id
