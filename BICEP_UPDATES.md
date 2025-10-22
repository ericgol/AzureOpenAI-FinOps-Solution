# Bicep Infrastructure Updates for Python 3.12

**Update Date:** 2025-10-22  
**Python Version:** 3.11 → 3.12  
**Affected Resources:** Both Azure Function Apps

---

## 📋 Summary

Updated both Function App Bicep deployment modules to use **Python 3.12** instead of Python 3.11, ensuring infrastructure-as-code matches the application code migration.

---

## 🔧 Changes Made

### 1. **finops-data-collector Function App**

**File:** `infrastructure/bicep/modules/function-app.bicep`

**Change:**
```diff
@description('Python version')
- param pythonVersion string = '3.11'
+ param pythonVersion string = '3.12'
```

**Impact:**
- Default Python version parameter changed from 3.11 to 3.12
- `linuxFxVersion` will use `Python|3.12` during deployment
- Affects line 27 in the Bicep file

---

### 2. **eventhub-to-appinsights Function App**

**File:** `infrastructure/bicep/modules/eventhub-function-app.bicep`

**Changes:**

#### Change 1: linuxFxVersion
```diff
siteConfig: {
-   linuxFxVersion: 'Python|3.11'
+   linuxFxVersion: 'Python|3.12'
```
**Line:** 57

#### Change 2: pythonVersion property
```diff
use32BitWorkerProcess: false
- pythonVersion: '3.11'
+ pythonVersion: '3.12'
```
**Line:** 117

**Impact:**
- Both `linuxFxVersion` and `pythonVersion` properties updated
- Ensures consistent Python 3.12 runtime configuration

---

## ✅ Verification

### Configuration Alignment

| Component | Python Version | Status |
|-----------|---------------|--------|
| **Code Base** | | |
| ├─ function_app.py (finops) | 3.12 | ✅ |
| ├─ function_app.py (eventhub) | 3.12 | ✅ |
| └─ requirements.txt (both) | 3.12 compatible | ✅ |
| **Infrastructure** | | |
| ├─ function-app.bicep | 3.12 | ✅ |
| └─ eventhub-function-app.bicep | 3.12 | ✅ |
| **Runtime Configuration** | | |
| ├─ Extension Bundle | 4.x | ✅ |
| └─ Functions Runtime | ~4 | ✅ |

All components now aligned to Python 3.12! ✅

---

## 🚀 Deployment Instructions

### Option 1: Deploy with Azure CLI

```bash
# Set subscription
az account set --subscription "your-subscription-id"

# Deploy to dev environment
az deployment sub create \
  --location "East US 2" \
  --template-file infrastructure/bicep/main.bicep \
  --parameters environment=dev \
               projectName=finops-aoai \
               apimSku=Developer \
               enablePrivateNetworking=false

# Deploy to prod environment
az deployment sub create \
  --location "East US 2" \
  --template-file infrastructure/bicep/main.bicep \
  --parameters environment=prod \
               projectName=finops-aoai \
               apimSku=Premium \
               enablePrivateNetworking=true
```

### Option 2: Deploy with PowerShell Script

```powershell
# Navigate to PowerShell deployment scripts
cd infrastructure/powershell/dev

# Deploy complete environment
./Deploy-DevEnvironment.ps1 -SubscriptionId "your-subscription-id"

# Preview deployment (WhatIf)
./Deploy-DevEnvironment.ps1 -SubscriptionId "your-subscription-id" -WhatIf
```

---

## 🔍 Post-Deployment Verification

### 1. Verify Python Version in Azure Portal

1. Navigate to Function App in Azure Portal
2. Go to **Configuration** → **General settings**
3. Verify: **Stack** = Python, **Major version** = 3.12

### 2. Verify via Azure CLI

```bash
# Check finops-data-collector function app
az functionapp config show \
  --name <finops-function-app-name> \
  --resource-group <resource-group-name> \
  --query "linuxFxVersion"
# Expected output: "Python|3.12"

# Check eventhub-to-appinsights function app
az functionapp config show \
  --name <eventhub-function-app-name> \
  --resource-group <resource-group-name> \
  --query "linuxFxVersion"
# Expected output: "Python|3.12"
```

### 3. Verify Runtime Configuration

```bash
# Get app settings
az functionapp config appsettings list \
  --name <function-app-name> \
  --resource-group <resource-group-name> \
  --query "[?name=='FUNCTIONS_EXTENSION_VERSION' || name=='FUNCTIONS_WORKER_RUNTIME'].{name:name, value:value}" \
  --output table

# Expected output:
# Name                          Value
# ----------------------------  -------
# FUNCTIONS_EXTENSION_VERSION   ~4
# FUNCTIONS_WORKER_RUNTIME      python
```

---

## 📦 Function App Configuration

Both function apps will be deployed with these Python 3.12 compatible settings:

### Core Settings
```json
{
  "linuxFxVersion": "Python|3.12",
  "FUNCTIONS_EXTENSION_VERSION": "~4",
  "FUNCTIONS_WORKER_RUNTIME": "python",
  "ENABLE_ORYX_BUILD": "true",
  "SCM_DO_BUILD_DURING_DEPLOYMENT": "true"
}
```

### Runtime Configuration
- **Extension Bundle Version:** `[4.*, 5.0.0)` (supports Python 3.12)
- **Function Runtime:** v4
- **Build System:** Oryx (automatic dependency installation)
- **Platform:** Linux (required for Python)

---

## 🔄 Updating Existing Deployments

If you have existing Function Apps deployed with Python 3.11, you have two options:

### Option 1: Redeploy Infrastructure (Recommended)

```bash
# Redeploy with updated Bicep templates
az deployment sub create \
  --location "East US 2" \
  --template-file infrastructure/bicep/main.bicep \
  --parameters environment=dev

# Function Apps will be updated in-place to Python 3.12
```

### Option 2: Manual Update via CLI

```bash
# Update finops-data-collector
az functionapp config set \
  --name <finops-function-app-name> \
  --resource-group <resource-group-name> \
  --linux-fx-version "Python|3.12"

# Update eventhub-to-appinsights
az functionapp config set \
  --name <eventhub-function-app-name> \
  --resource-group <resource-group-name> \
  --linux-fx-version "Python|3.12"

# Restart both function apps
az functionapp restart --name <finops-function-app-name> --resource-group <resource-group-name>
az functionapp restart --name <eventhub-function-app-name> --resource-group <resource-group-name>
```

---

## ⚠️ Important Notes

### 1. **Deployment Order**
The main.bicep handles deployment order automatically:
1. Storage Account created first
2. Function Apps deployed (Python 3.12 runtime)
3. Network restrictions applied last (if enabled)

### 2. **File Share Compatibility**
Python 3.12 is fully compatible with Azure File Share storage used by Function Apps. No changes needed to storage configuration.

### 3. **Extension Bundle**
Extension Bundle v4 (`[4.*, 5.0.0)`) fully supports Python 3.12. This was already configured correctly in the Bicep files.

### 4. **Managed Identity**
No changes to managed identity configuration needed. Python 3.12 works seamlessly with Azure managed identity authentication.

### 5. **VNet Integration**
Python 3.12 is compatible with VNet integration. No networking changes required.

---

## 🧪 Testing Checklist

After deployment, verify:

- [ ] Function Apps show Python 3.12 in portal
- [ ] Function Apps successfully start
- [ ] Timer trigger executes (finops-data-collector)
- [ ] EventHub trigger processes events (eventhub-to-appinsights)
- [ ] Application Insights receives telemetry
- [ ] No runtime errors in Function App logs
- [ ] Dependencies install successfully during deployment
- [ ] Managed identity authentication works

---

## 📚 Related Documentation

- [MIGRATION_SUMMARY.md](./MIGRATION_SUMMARY.md) - Complete Python code migration details
- [VERIFICATION_REPORT.md](./VERIFICATION_REPORT.md) - Code and dependency validation
- [WARP.md](./WARP.md) - Project overview and development guide

---

## 🎯 Summary

**All Bicep templates updated to Python 3.12:**

- ✅ finops-data-collector: Default parameter `pythonVersion = '3.12'`
- ✅ eventhub-to-appinsights: Hardcoded `linuxFxVersion = 'Python|3.12'`
- ✅ main.bicep: No changes needed (uses module defaults)
- ✅ Extension bundles: Already v4 (Python 3.12 compatible)
- ✅ All configuration aligned with Python 3.12 code migration

**Infrastructure is now fully aligned with application code!** 🚀

---

**Updated by:** Warp AI Assistant  
**Date:** 2025-10-22  
**Status:** ✅ COMPLETE
