// Apply FinOps telemetry policy to APIM API
// This module applies the policy after both APIM service and EventHub logger are configured

@description('API Management service name')
param apimName string

@description('OpenAI API name within APIM')
param apiName string = 'openai-api'

// Reference to existing APIM service
resource apimService 'Microsoft.ApiManagement/service@2023-05-01-preview' existing = {
  name: apimName
}

// Reference to existing OpenAI API
resource openAiApi 'Microsoft.ApiManagement/service/apis@2023-05-01-preview' existing = {
  parent: apimService
  name: apiName
}

// Apply the comprehensive FinOps telemetry policy that logs to EventHub
resource finOpsTelemetryPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-05-01-preview' = {
  parent: openAiApi
  name: 'policy'
  properties: {
    value: loadTextContent('../../../src/apim-policies/finops-telemetry-policy.xml')
  }
}

// Outputs
output policyApplied bool = true
output policyName string = finOpsTelemetryPolicy.name