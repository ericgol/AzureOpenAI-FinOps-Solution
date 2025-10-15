// Azure API Management for OpenAI Gateway
@description('API Management service name')
param apimName string

@description('Location for API Management')
param location string

@description('Resource tags')
param tags object = {}

@description('APIM SKU')
@allowed(['Developer', 'Premium'])
param sku string = 'Developer'

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string

@description('Application Insights instrumentation key')
param appInsightsInstrumentationKey string

@description('Application Insights resource ID')
param appInsightsResourceId string = ''

@description('Subnet ID for private networking')
param subnetId string = ''

@description('Enable private networking')
param enablePrivateNetworking bool = false

@description('Publisher email')
param publisherEmail string = 'admin@contoso.com'

@description('Publisher name')
param publisherName string = 'FinOps Admin'

// API Management Service
resource apiManagement 'Microsoft.ApiManagement/service@2023-05-01-preview' = {
  name: apimName
  location: location
  tags: tags
  sku: {
    name: sku
    capacity: 1
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
    virtualNetworkConfiguration: enablePrivateNetworking ? {
      subnetResourceId: subnetId
    } : null
    virtualNetworkType: enablePrivateNetworking ? 'Internal' : 'None'
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Logger for Application Insights
// Note: resourceId must be the full Application Insights resource ID, not derived from instrumentationKey
resource appInsightsLogger 'Microsoft.ApiManagement/service/loggers@2023-05-01-preview' = {
  parent: apiManagement
  name: 'applicationinsights'
  properties: {
    loggerType: 'applicationInsights'
    credentials: {
      instrumentationKey: appInsightsInstrumentationKey
    }
    isBuffered: true
    resourceId: appInsightsResourceId != '' ? appInsightsResourceId : null
  }
}

// Diagnostic settings for APIM
// Note: Retention policies are no longer supported in newer API versions
// Log Analytics workspace handles retention based on its own settings
resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: apiManagement
  name: 'finops-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Named value for storing configuration
resource logAnalyticsWorkspaceIdNamedValue 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  parent: apiManagement
  name: 'log-analytics-workspace-id'
  properties: {
    displayName: 'LogAnalyticsWorkspaceID'
    value: logAnalyticsWorkspaceId
    secret: false
  }
}

// OpenAI API Product
resource openAiProduct 'Microsoft.ApiManagement/service/products@2023-05-01-preview' = {
  parent: apiManagement
  name: 'openai-finops'
  properties: {
    displayName: 'OpenAI FinOps APIs'
    description: 'Azure OpenAI APIs with FinOps telemetry collection'
    subscriptionRequired: true
    approvalRequired: false
    state: 'published'
  }
}

// OpenAI API
resource openAiApi 'Microsoft.ApiManagement/service/apis@2023-05-01-preview' = {
  parent: apiManagement
  name: 'openai-api'
  properties: {
    displayName: 'OpenAI API'
    description: 'Azure OpenAI Service API with FinOps tracking'
    serviceUrl: 'https://your-openai-service.openai.azure.com'
    path: 'openai'
    protocols: ['https']
    subscriptionKeyParameterNames: {
      header: 'api-key'
      query: 'api-key'
    }
  }
}

// Link API to Product
resource productApi 'Microsoft.ApiManagement/service/products/apis@2023-05-01-preview' = {
  parent: openAiProduct
  name: openAiApi.name
}

// Chat completions operation
resource chatCompletionsOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: openAiApi
  name: 'chat-completions'
  properties: {
    displayName: 'Chat Completions'
    method: 'POST'
    urlTemplate: '/deployments/{deployment-id}/chat/completions'
    templateParameters: [
      {
        name: 'deployment-id'
        type: 'string'
        required: true
        description: 'Deployment ID of the model'
      }
    ]
    description: 'Creates a model response for the given chat conversation. Custom headers (device_id, store_number) are handled by the FinOps policy.'
    request: {
      queryParameters: [
        {
          name: 'api-version'
          type: 'string'
          required: true
          defaultValue: '2024-02-01'
        }
      ]
headers: [
        {
          name: 'Content-Type'
          type: 'string'
          defaultValue: 'application/json'
          required: true
        }
      ]
    }
    responses: [
      {
        statusCode: 200
        description: 'OK'
        representations: [
          {
            contentType: 'application/json'
          }
        ]
      }
    ]
  }
}

// FinOps telemetry collection policy for the API
// Note: Variable names use camelCase to avoid APIM policy validation errors with hyphens
resource finOpsTelemetryPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-05-01-preview' = {
  parent: openAiApi
  name: 'policy'
  properties: {
    value: '''<policies>
  <inbound>
    <base />
    <set-variable name="deviceId" value="@(context.Request.Headers.GetValueOrDefault(&quot;device_id&quot;, &quot;unknown&quot;))" />
    <set-variable name="storeNumber" value="@(context.Request.Headers.GetValueOrDefault(&quot;store_number&quot;, &quot;unknown&quot;))" />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>'''
  }
}

// Subscription for testing
resource testSubscription 'Microsoft.ApiManagement/service/subscriptions@2023-05-01-preview' = {
  parent: apiManagement
  name: 'test-subscription'
  properties: {
    displayName: 'Test Subscription'
    state: 'active'
    scope: '/products/${openAiProduct.id}'
  }
}

// Outputs
output apimName string = apiManagement.name
output apimId string = apiManagement.id
output gatewayUrl string = apiManagement.properties.gatewayUrl
output managementApiUrl string = apiManagement.properties.managementApiUrl
output principalId string = apiManagement.identity.principalId
@secure()
output testSubscriptionKey string = testSubscription.listSecrets().primaryKey
