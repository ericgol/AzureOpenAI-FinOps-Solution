#!/usr/bin/env pwsh

<#
.SYNOPSIS
    Cleans up failed deployments and prepares environment for fresh deployment.

.DESCRIPTION
    This script removes partially deployed resources from failed deployments
    to ensure a clean state before attempting a new deployment.

.PARAMETER SubscriptionId
    The Azure subscription ID where resources will be cleaned up.

.PARAMETER TenantId
    The Azure AD tenant ID for authentication.

.PARAMETER ResourceGroupName
    The resource group name to clean up. Defaults to 'pike-finops-dev-rg'.

.PARAMETER Force
    Skip confirmation prompts and force cleanup.

.EXAMPLE
    ./Clean-FailedDeployments.ps1 -SubscriptionId "12345678-1234-1234-1234-123456789012" -TenantId "87654321-4321-4321-4321-210987654321"

.EXAMPLE
    ./Clean-FailedDeployments.ps1 -SubscriptionId "12345678-1234-1234-1234-123456789012" -TenantId "87654321-4321-4321-4321-210987654321" -Force
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
    [string]$ResourceGroupName = "pike-finops-dev-rg",
    
    [Parameter(Mandatory = $false)]
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "🧹 Starting cleanup of failed deployments" -ForegroundColor Green
Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor Yellow
Write-Host "Subscription: $SubscriptionId" -ForegroundColor Yellow

# Authenticate
Write-Host "🔐 Setting up Azure context..." -ForegroundColor Blue
try {
    $context = Get-AzContext
    if (-not $context -or $context.Subscription.Id -ne $SubscriptionId -or $context.Tenant.Id -ne $TenantId) {
        Write-Host "Authenticating to Azure..." -ForegroundColor Yellow
        Connect-AzAccount -TenantId $TenantId -SubscriptionId $SubscriptionId
    }
    
    Set-AzContext -SubscriptionId $SubscriptionId -TenantId $TenantId | Out-Null
    Write-Host "✅ Successfully authenticated" -ForegroundColor Green
}
catch {
    Write-Error "Failed to authenticate: $_"
    exit 1
}

# Check if resource group exists
try {
    $rg = Get-AzResourceGroup -Name $ResourceGroupName -ErrorAction Stop
    Write-Host "📋 Found resource group: $($rg.ResourceGroupName)" -ForegroundColor Green
}
catch {
    Write-Host "❌ Resource group '$ResourceGroupName' not found. Nothing to clean up." -ForegroundColor Yellow
    exit 0
}

# Get list of resources in the resource group
Write-Host "🔍 Checking resources in resource group..." -ForegroundColor Blue
$resources = Get-AzResource -ResourceGroupName $ResourceGroupName

if ($resources.Count -eq 0) {
    Write-Host "✅ Resource group is already empty. Nothing to clean up." -ForegroundColor Green
    exit 0
}

Write-Host "📊 Found $($resources.Count) resources to potentially clean up:" -ForegroundColor Yellow
foreach ($resource in $resources) {
    $status = "Unknown"
    try {
        # Try to get detailed resource info to check status
        $detailResource = Get-AzResource -ResourceId $resource.ResourceId -ErrorAction SilentlyContinue
        if ($detailResource -and $detailResource.Properties -and $detailResource.Properties.provisioningState) {
            $status = $detailResource.Properties.provisioningState
        }
    }
    catch {
        # Ignore errors when checking status
    }
    
    $color = switch ($status) {
        "Succeeded" { "Green" }
        "Failed" { "Red" }
        "Running" { "Yellow" }
        "Canceled" { "Magenta" }
        default { "White" }
    }
    
    Write-Host "  - $($resource.Name) ($($resource.ResourceType)) - Status: $status" -ForegroundColor $color
}

# Ask for confirmation unless Force is specified
if (-not $Force) {
    Write-Host ""
    $confirmation = Read-Host "Do you want to delete the entire resource group '$ResourceGroupName' and all resources? This cannot be undone. (yes/no)"
    if ($confirmation -ne "yes") {
        Write-Host "❌ Cleanup canceled by user." -ForegroundColor Yellow
        exit 0
    }
}

# Delete the resource group
Write-Host "🗑️  Deleting resource group '$ResourceGroupName'..." -ForegroundColor Red
Write-Host "⚠️  This may take several minutes..." -ForegroundColor Yellow

try {
    Remove-AzResourceGroup -Name $ResourceGroupName -Force -AsJob | Out-Null
    
    # Wait for deletion to complete
    do {
        Start-Sleep -Seconds 10
        Write-Host "⏳ Still deleting..." -ForegroundColor Yellow
        $rgExists = $null
        try {
            $rgExists = Get-AzResourceGroup -Name $ResourceGroupName -ErrorAction SilentlyContinue
        }
        catch {
            # Resource group doesn't exist, which means deletion succeeded
        }
    } while ($rgExists)
    
    Write-Host "✅ Resource group '$ResourceGroupName' has been successfully deleted!" -ForegroundColor Green
}
catch {
    Write-Error "Failed to delete resource group: $_"
    Write-Host "You may need to manually clean up some resources in the Azure portal." -ForegroundColor Yellow
    exit 1
}

# Clean up failed subscription-level deployments
Write-Host "🧹 Cleaning up failed subscription-level deployments..." -ForegroundColor Blue

try {
    $failedDeployments = az deployment sub list --query "[?contains(name, 'finops') && properties.provisioningState == 'Failed'].name" -o tsv
    
    if ($failedDeployments) {
        foreach ($deploymentName in $failedDeployments) {
            Write-Host "🗑️  Deleting failed deployment: $deploymentName" -ForegroundColor Yellow
            az deployment sub delete --name $deploymentName
        }
        Write-Host "✅ Cleaned up failed subscription deployments" -ForegroundColor Green
    } else {
        Write-Host "ℹ️  No failed subscription deployments found" -ForegroundColor Cyan
    }
}
catch {
    Write-Warning "Could not clean up subscription-level deployments: $_"
}

Write-Host ""
Write-Host "✅ Cleanup completed successfully!" -ForegroundColor Green
Write-Host "🚀 You can now run a fresh deployment." -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 Next steps:" -ForegroundColor Yellow
Write-Host "1. Run the deployment script: ./Deploy-DevEnvironment.ps1" -ForegroundColor White
Write-Host "2. Monitor the deployment progress in Azure portal" -ForegroundColor White
Write-Host "3. Verify all resources are created successfully" -ForegroundColor White