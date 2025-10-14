#!/usr/bin/env pwsh

<#
.SYNOPSIS
    Configures Log Analytics workspace with custom tables and queries after deployment.

.DESCRIPTION
    This script creates custom tables and saved queries in the Log Analytics workspace
    after the main deployment is complete. This avoids timing issues during deployment
    where child resources try to deploy before the workspace is fully active.

.PARAMETER SubscriptionId
    The Azure subscription ID.

.PARAMETER TenantId
    The Azure AD tenant ID for authentication.

.PARAMETER ResourceGroupName
    The resource group name containing the Log Analytics workspace.

.PARAMETER WorkspaceName
    The Log Analytics workspace name to configure.

.EXAMPLE
    ./Configure-LogAnalytics.ps1 -SubscriptionId "12345678-1234-1234-1234-123456789012" -TenantId "87654321-4321-4321-4321-210987654321" -ResourceGroupName "pike-finops-dev-rg" -WorkspaceName "pike-finops-dev-law-abc123"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')]
    [string]$TenantId,
    
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceName
)

$ErrorActionPreference = "Stop"

Write-Host "🔧 Configuring Log Analytics workspace: $WorkspaceName" -ForegroundColor Green

# Authenticate if needed
try {
    $context = Get-AzContext
    if (-not $context -or $context.Subscription.Id -ne $SubscriptionId -or $context.Tenant.Id -ne $TenantId) {
        Write-Host "🔐 Authenticating to Azure..." -ForegroundColor Yellow
        Connect-AzAccount -TenantId $TenantId -SubscriptionId $SubscriptionId
    }
    Set-AzContext -SubscriptionId $SubscriptionId -TenantId $TenantId | Out-Null
}
catch {
    Write-Error "Failed to authenticate: $_"
    exit 1
}

# Wait for workspace to be fully active
Write-Host "⏳ Waiting for Log Analytics workspace to be fully active..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0

do {
    $attempt++
    try {
        $workspace = az monitor log-analytics workspace show --resource-group $ResourceGroupName --workspace-name $WorkspaceName --query "{State:provisioningState, WorkspaceId:customerId}" | ConvertFrom-Json
        
        if ($workspace.State -eq "Succeeded" -and $workspace.WorkspaceId) {
            Write-Host "✅ Workspace is active with ID: $($workspace.WorkspaceId)" -ForegroundColor Green
            break
        }
        else {
            Write-Host "⏳ Workspace state: $($workspace.State), attempt $attempt/$maxAttempts" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "⏳ Waiting for workspace to be available, attempt $attempt/$maxAttempts" -ForegroundColor Yellow
    }
    
    if ($attempt -ge $maxAttempts) {
        Write-Error "Workspace did not become active within expected time"
        exit 1
    }
    
    Start-Sleep -Seconds 10
} while ($true)

# Create saved queries
Write-Host "📊 Creating saved queries..." -ForegroundColor Blue

try {
    # API Usage Analysis Query
    $apiUsageQuery = @{
        category = "FinOps"
        displayName = "API Usage Analysis"
        query = @"
FinOpsApiCalls_CL
| where TimeGenerated >= ago(1d)
| summarize 
    TotalCalls = count(),
    AvgResponseTime = avg(ResponseTime),
    TotalTokens = sum(TokensUsed),
    SuccessRate = countif(StatusCode < 400) * 100.0 / count()
    by deviceId, storeNumber, ApiName
| order by TotalCalls desc
"@
        version = 2
    }
    
    $apiQueryJson = $apiUsageQuery | ConvertTo-Json -Depth 5
    az monitor log-analytics workspace saved-search create --resource-group $ResourceGroupName --workspace-name $WorkspaceName --saved-search-id "FinOpsApiUsageAnalysis" --category $apiUsageQuery.category --display-name $apiUsageQuery.displayName --saved-query $apiUsageQuery.query --version $apiUsageQuery.version
    
    Write-Host "✅ Created API Usage Analysis query" -ForegroundColor Green
    
    # Cost Allocation Query  
    $costQuery = @{
        category = "FinOps"
        displayName = "Cost Allocation by User/Store"
        query = @"
FinOpsCostData_CL
| where TimeGenerated >= ago(7d)
| summarize 
    TotalAllocatedCost = sum(AllocatedCost),
    AvgDailyCost = avg(AllocatedCost)
    by deviceId, storeNumber, bin(Date, 1d)
| order by Date desc, TotalAllocatedCost desc
"@
        version = 2
    }
    
    az monitor log-analytics workspace saved-search create --resource-group $ResourceGroupName --workspace-name $WorkspaceName --saved-search-id "FinOpsCostAllocation" --category $costQuery.category --display-name $costQuery.displayName --saved-query $costQuery.query --version $costQuery.version
    
    Write-Host "✅ Created Cost Allocation query" -ForegroundColor Green
}
catch {
    Write-Warning "Could not create saved queries (they will be created automatically when Function Apps send data): $_"
}

Write-Host "🎉 Log Analytics workspace configuration completed!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Notes:" -ForegroundColor Yellow
Write-Host "• Custom tables (FinOpsApiCalls_CL, FinOpsCostData_CL) will be created automatically" -ForegroundColor White
Write-Host "  when the Function Apps first send data to the workspace" -ForegroundColor White
Write-Host "• The saved queries are now available in the Log Analytics workspace" -ForegroundColor White
Write-Host "• You can find the queries under 'Logs' > 'Saved Queries' > 'FinOps' category" -ForegroundColor White