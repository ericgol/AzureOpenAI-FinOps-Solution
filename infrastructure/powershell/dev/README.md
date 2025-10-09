# Azure OpenAI FinOps Solution - Development Deployment

This directory contains the PowerShell deployment script for the Azure OpenAI FinOps solution development environment.

## Prerequisites

- Azure PowerShell module (`Az`)
- Azure CLI (for tenant ID discovery)
- Appropriate Azure permissions (Contributor or Owner on the subscription)
- Valid Azure AD account with access to the target tenant and subscription

## Script Updates - MFA Support

The deployment script has been updated to **require a Tenant ID** and support **Multi-Factor Authentication (MFA)** during Azure login.

### Key Changes

1. **Mandatory TenantId Parameter**: The script now requires a `-TenantId` parameter for authentication
2. **MFA Support**: Interactive browser-based authentication supports MFA requirements
3. **Enhanced Validation**: Both SubscriptionId and TenantId are validated as proper GUIDs
4. **Better Error Messages**: Clear guidance when authentication fails
5. **Fallback Authentication**: Device code authentication if browser login fails

## Usage

### Basic Usage

```powershell
./Deploy-DevEnvironment.ps1 -SubscriptionId "12345678-1234-1234-1234-123456789012" -TenantId "87654321-4321-4321-4321-210987654321"
```

### Find Your Tenant ID

If you don't know your Tenant ID, use one of these methods:

**Method 1: Azure CLI**
```bash
az account show --query tenantId -o tsv
```

**Method 2: Azure Portal**
1. Navigate to Azure Active Directory
2. Go to Properties
3. Copy the Tenant ID value

**Method 3: PowerShell**
```powershell
$tenantId = az account show --query tenantId -o tsv
./Deploy-DevEnvironment.ps1 -SubscriptionId "your-subscription-id" -TenantId $tenantId
```

### Additional Parameters

```powershell
./Deploy-DevEnvironment.ps1 `
    -SubscriptionId "12345678-1234-1234-1234-123456789012" `
    -TenantId "87654321-4321-4321-4321-210987654321" `
    -Location "West US 2" `
    -ProjectName "my-finops" `
    -Environment "dev" `
    -WhatIf
```

## Authentication Flow

1. **Context Check**: Script checks if you're already authenticated to the correct tenant/subscription
2. **Interactive Login**: If authentication is needed, opens browser for login (MFA supported)
3. **Fallback**: If browser fails, falls back to device code authentication
4. **Validation**: Confirms successful authentication to the target tenant and subscription

## Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| `SubscriptionId` | Yes | Azure subscription ID (GUID format) | - |
| `TenantId` | Yes | Azure AD tenant ID (GUID format) | - |
| `Location` | No | Azure region for deployment | "East US 2" |
| `ProjectName` | No | Project name prefix for resources | "finops-aoai" |
| `Environment` | No | Environment name | "dev" |
| `ResourceGroupName` | No | Custom resource group name | `{ProjectName}-{Environment}-rg` |
| `SkipInfrastructure` | No | Skip infrastructure, deploy functions only | False |
| `WhatIf` | No | Preview changes without deployment | False |

## MFA Considerations

### When MFA is Required
- Your organization enforces MFA for Azure access
- You're accessing Azure from a new device or location
- Your authentication token has expired
- You're switching between different tenants

### Authentication Experience
1. Script will open your default browser
2. Navigate to the Azure login page
3. Complete MFA challenge (SMS, app notification, etc.)
4. Return to PowerShell for deployment continuation

### Troubleshooting MFA Issues

**Browser doesn't open:**
- The script will automatically fall back to device code authentication
- Follow the on-screen instructions to complete authentication

**MFA prompt doesn't appear:**
- Ensure your browser allows pop-ups from Microsoft domains
- Try running the script in an elevated PowerShell session
- Clear your browser's Azure-related cookies and try again

**Authentication fails:**
- Verify the TenantId is correct for your organization
- Ensure your account has access to the specified subscription
- Check that your account has the required permissions (Contributor/Owner)

## Error Messages

The script provides detailed error messages for common issues:

- **Invalid GUID format**: TenantId or SubscriptionId not in proper GUID format
- **Tenant mismatch**: Your account doesn't have access to the specified tenant
- **Subscription not found**: Subscription doesn't exist or you lack access
- **Permission denied**: Insufficient permissions for deployment

## Security Notes

- The script uses interactive authentication - no credentials are stored
- Authentication tokens are managed by Azure PowerShell module
- MFA requirements are respected and enforced
- Tenant and subscription validation prevents accidental deployments

## Deployment Process

1. **Prerequisites Validation**: Checks for required tools and modules
2. **Authentication**: Interactive login with MFA support
3. **Parameter File Creation**: Generates deployment parameters
4. **Infrastructure Deployment**: Deploys Bicep templates to Azure
5. **Function Code Deployment**: Publishes Azure Functions code

## Next Steps

After successful deployment:

1. Configure Azure OpenAI service endpoints in API Management
2. Update APIM policies with your specific requirements
3. Test API endpoints with sample requests
4. Set up Power BI reports for cost analysis

For detailed documentation, see: `/docs/`

## Support

For issues with the deployment script:

1. Verify all prerequisites are installed
2. Check Azure permissions for your account
3. Ensure TenantId and SubscriptionId are correct
4. Review error messages for specific guidance
5. Try running with `-WhatIf` first to validate parameters