#!/usr/bin/env pwsh

<#
.SYNOPSIS
    Deploys the Azure OpenAI FinOps solution to a development environment.

.DESCRIPTION
    This script deploys the complete FinOps solution infrastructure using Azure Bicep templates.
    It's optimized for development environments with minimal cost and resources.
    
    The script supports interactive authentication with MFA through browser-based login.
    A valid Azure AD Tenant ID is required for authentication.

.PARAMETER SubscriptionId
    The Azure subscription ID where resources will be deployed.

.PARAMETER TenantId
    The Azure AD tenant ID for authentication. Required for MFA-enabled accounts.
    You can find your Tenant ID in the Azure Portal under Azure Active Directory > Properties > Tenant ID.
    Alternatively, run: az account show --query tenantId -o tsv

.PARAMETER Location
    The Azure region where resources will be deployed. Defaults to 'East US 2'.

.PARAMETER ProjectName
    The project name prefix for resource naming. Defaults to 'finops-aoai'.

.PARAMETER Environment
    The environment name. Defaults to 'dev'.

.PARAMETER ResourceGroupName
    The resource group name. If not provided, it will be generated based on project name and environment.

.PARAMETER SkipInfrastructure
    Skip infrastructure deployment and only deploy function code.

.PARAMETER WhatIf
    Preview what resources would be created without actually deploying them.

.EXAMPLE
    ./Deploy-DevEnvironment.ps1 -SubscriptionId "12345678-1234-1234-1234-123456789012" -TenantId "87654321-4321-4321-4321-210987654321"

.EXAMPLE
    ./Deploy-DevEnvironment.ps1 -SubscriptionId "12345678-1234-1234-1234-123456789012" -TenantId "87654321-4321-4321-4321-210987654321" -Location "West US 2" -WhatIf

.EXAMPLE
    # Find your Tenant ID first, then deploy
    $tenantId = az account show --query tenantId -o tsv
    ./Deploy-DevEnvironment.ps1 -SubscriptionId "12345678-1234-1234-1234-123456789012" -TenantId $tenantId
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')]
    [string]$TenantId,
    
    [Parameter(Mandatory = $false)]
    [string]$Location = "East US 2",
    
    [Parameter(Mandatory = $false)]
    [string]$ProjectName = "finops-aoai",
    
    [Parameter(Mandatory = $false)]
    [string]$Environment = "dev",
    
    [Parameter(Mandatory = $false)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory = $false)]
    [switch]$SkipInfrastructure,
    
    [Parameter(Mandatory = $false)]
    [switch]$WhatIf
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Set script location
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$rootDir = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptDir))

Write-Host "🚀 Starting Azure OpenAI FinOps Solution Deployment" -ForegroundColor Green
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Location: $Location" -ForegroundColor Yellow
Write-Host "Subscription: $SubscriptionId" -ForegroundColor Yellow
Write-Host "Tenant: $TenantId" -ForegroundColor Yellow

# Validate prerequisites
Write-Host "📋 Validating prerequisites..." -ForegroundColor Blue

# Check if Azure CLI is installed
if (-not (Get-Command "az" -ErrorAction SilentlyContinue)) {
    Write-Error "Azure CLI is not installed or not in PATH. Please install Azure CLI first."
    exit 1
}

# Check if Azure PowerShell is installed
if (-not (Get-Module -ListAvailable -Name Az.Resources)) {
    Write-Host "Installing Azure PowerShell modules..." -ForegroundColor Yellow
    Install-Module -Name Az.Resources, Az.Storage, Az.KeyVault, Az.CostManagement -Force -AllowClobber
}

# Login and set subscription
Write-Host "🔐 Setting up Azure context..." -ForegroundColor Blue
try {
    $context = Get-AzContext
    $needsAuthentication = $false
    
    # Check if we need to authenticate
    if (-not $context) {
        Write-Host "No Azure context found. Authentication required." -ForegroundColor Yellow
        $needsAuthentication = $true
    }
    elseif ($context.Subscription.Id -ne $SubscriptionId) {
        Write-Host "Current subscription ($($context.Subscription.Id)) does not match target subscription ($SubscriptionId)." -ForegroundColor Yellow
        $needsAuthentication = $true
    }
    elseif ($context.Tenant.Id -ne $TenantId) {
        Write-Host "Current tenant ($($context.Tenant.Id)) does not match target tenant ($TenantId)." -ForegroundColor Yellow
        $needsAuthentication = $true
    }
    
    if ($needsAuthentication) {
        Write-Host "Connecting to Azure with Tenant ID: $TenantId" -ForegroundColor Yellow
        Write-Host "This will open an interactive browser window for authentication (MFA supported)." -ForegroundColor Cyan
        
        # Use interactive authentication with TenantId - this supports MFA
        $connectParams = @{
            TenantId = $TenantId
            SubscriptionId = $SubscriptionId
        }
        
        # Try browser-based authentication first (better UX for MFA)
        try {
            Write-Host "Attempting browser-based authentication..." -ForegroundColor Cyan
            Connect-AzAccount @connectParams
        }
        catch {
            # Fallback to device authentication if browser auth fails
            Write-Host "Browser authentication failed. Falling back to device authentication..." -ForegroundColor Yellow
            Write-Host "You will need to visit a URL and enter a device code." -ForegroundColor Cyan
            $connectParams.UseDeviceAuthentication = $true
            Connect-AzAccount @connectParams
        }
    }
    
    # Ensure we're in the correct subscription and tenant context
    $finalContext = Set-AzContext -SubscriptionId $SubscriptionId -TenantId $TenantId
    
    if ($finalContext.Subscription.Id -ne $SubscriptionId) {
        throw "Failed to set subscription context to $SubscriptionId"
    }
    
    if ($finalContext.Tenant.Id -ne $TenantId) {
        throw "Failed to set tenant context to $TenantId"
    }
    
    Write-Host "✅ Successfully authenticated to:" -ForegroundColor Green
    Write-Host "  Tenant: $($finalContext.Tenant.Id) ($($finalContext.Tenant.Directory))" -ForegroundColor White
    Write-Host "  Subscription: $($finalContext.Subscription.Id) ($($finalContext.Subscription.Name))" -ForegroundColor White
    Write-Host "  Account: $($finalContext.Account.Id)" -ForegroundColor White
}
catch {
    Write-Error "Failed to authenticate with Azure: $_"
    Write-Host "Please ensure:" -ForegroundColor Yellow
    Write-Host "  1. The TenantId ($TenantId) is correct" -ForegroundColor White
    Write-Host "  2. The SubscriptionId ($SubscriptionId) exists in this tenant" -ForegroundColor White
    Write-Host "  3. Your account has appropriate permissions" -ForegroundColor White
    Write-Host "  4. You have completed MFA if required" -ForegroundColor White
    exit 1
}

# Generate resource group name if not provided
if (-not $ResourceGroupName) {
    $ResourceGroupName = "$ProjectName-$Environment-rg"
}

# Set deployment parameters
$deploymentName = "finops-deployment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$bicepFile = Join-Path $rootDir "infrastructure/bicep/main.bicep"
$parametersFile = Join-Path $rootDir "infrastructure/bicep/parameters/dev-parameters.json"

# Create parameters file if it doesn't exist
if (-not (Test-Path $parametersFile)) {
    Write-Host "📝 Creating parameters file..." -ForegroundColor Blue
    
    $parametersDir = Split-Path -Parent $parametersFile
    if (-not (Test-Path $parametersDir)) {
        New-Item -ItemType Directory -Path $parametersDir -Force | Out-Null
    }
    
    $parameters = @{
        '$schema' = "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#"
        contentVersion = "1.0.0.0"
        parameters = @{
            environment = @{ value = $Environment }
            location = @{ value = $Location }
            projectName = @{ value = $ProjectName }
            apimSku = @{ value = "Developer" }
            enablePrivateNetworking = @{ value = $false }
            costManagementScope = @{ value = "/subscriptions/$SubscriptionId" }
        }
    }
    
    $parameters | ConvertTo-Json -Depth 10 | Out-File -FilePath $parametersFile -Encoding UTF8
}

if (-not $SkipInfrastructure) {
    # Deploy infrastructure
    Write-Host "🏗️  Deploying infrastructure..." -ForegroundColor Blue
    
    $deploymentParams = @{
        Name = $deploymentName
        Location = $Location
        TemplateFile = $bicepFile
        TemplateParameterFile = $parametersFile
        Verbose = $true
    }
    
    if ($WhatIf) {
        $deploymentParams.Add("WhatIf", $true)
        Write-Host "🔍 Running WhatIf deployment..." -ForegroundColor Cyan
    }
    
    try {
        $deployment = New-AzSubscriptionDeployment @deploymentParams
        
        if (-not $WhatIf) {
            if ($deployment.ProvisioningState -eq "Succeeded") {
                Write-Host "✅ Infrastructure deployment completed successfully!" -ForegroundColor Green
                
                # Extract deployment outputs
                $outputs = $deployment.Outputs
                $resourceGroupName = $outputs.resourceGroupName.Value
                $functionAppName = $outputs.functionAppName.Value
                $apimName = $outputs.apimName.Value
                $storageAccountName = $outputs.storageAccountName.Value
                
                Write-Host "📊 Deployment Results:" -ForegroundColor Yellow
                Write-Host "  Resource Group: $resourceGroupName" -ForegroundColor White
                Write-Host "  Function App: $functionAppName" -ForegroundColor White
                Write-Host "  API Management: $apimName" -ForegroundColor White
                Write-Host "  Storage Account: $storageAccountName" -ForegroundColor White
                
                # Store outputs for function deployment
                $outputsFile = Join-Path $scriptDir "deployment-outputs.json"
                $outputs | ConvertTo-Json -Depth 5 | Out-File -FilePath $outputsFile -Encoding UTF8
            }
            else {
                Write-Error "Infrastructure deployment failed with state: $($deployment.ProvisioningState)"
                exit 1
            }
        }
    }
    catch {
        Write-Error "Infrastructure deployment failed: $_"
        exit 1
    }
}

# Deploy function app code
if (-not $WhatIf -and -not $SkipInfrastructure) {
    Write-Host "📦 Deploying Function App code..." -ForegroundColor Blue
    
    # Check if func core tools is available
    if (-not (Get-Command "func" -ErrorAction SilentlyContinue)) {
        Write-Warning "Azure Functions Core Tools not found. Please install it to deploy function code."
        Write-Host "Run: npm install -g azure-functions-core-tools@4 --unsafe-perm true" -ForegroundColor Yellow
    }
    else {
        $functionDir = Join-Path $rootDir "src/functions/finops-data-collector"
        
        if (Test-Path $functionDir) {
            Push-Location $functionDir
            try {
                Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
                python -m pip install -r requirements.txt
                
                Write-Host "Publishing function app..." -ForegroundColor Yellow
                func azure functionapp publish $functionAppName --python
                
                Write-Host "✅ Function app deployed successfully!" -ForegroundColor Green
            }
            catch {
                Write-Warning "Function app deployment failed: $_"
            }
            finally {
                Pop-Location
            }
        }
        else {
            Write-Warning "Function app source code not found at $functionDir"
        }
    }
}

Write-Host "🎉 Deployment completed!" -ForegroundColor Green

if (-not $WhatIf) {
    Write-Host ""
    Write-Host "📝 Next steps:" -ForegroundColor Yellow
    Write-Host "1. Configure your Azure OpenAI service URL in APIM" -ForegroundColor White
    Write-Host "2. Update APIM policies with your specific requirements" -ForegroundColor White  
    Write-Host "3. Test the API endpoint with sample requests" -ForegroundColor White
    Write-Host "4. Set up Power BI reports using the stored data" -ForegroundColor White
    Write-Host ""
    Write-Host "📚 Documentation: $rootDir/docs/" -ForegroundColor Cyan
    Write-Host "🔧 Configuration: $rootDir/src/configs/" -ForegroundColor Cyan
}

Write-Host "🏁 Script completed successfully!" -ForegroundColor Green