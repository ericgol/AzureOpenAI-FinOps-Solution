# Power BI Quick Connection Guide

## 🚀 **5-Minute Setup**

### **Step 1: Get Your Storage Details**
```bash
# Get these values from your deployment:
STORAGE_ACCOUNT_NAME="your-finops-storage-account" 
CONTAINER_NAME="finops-data"
```

### **Step 2: Connect in Power BI Desktop**

1. **Open Power BI Desktop**
2. **Get Data** → **More** → **Azure** → **Azure Blob Storage**
3. **URL**: `https://[STORAGE_ACCOUNT_NAME].blob.core.windows.net`
4. **Authentication**: Choose Account Key or Azure AD

### **Step 3: Navigate Data Structure**

```
📁 finops-data/
├── 📁 2024/01/15/     ← Daily partitions
│   └── 📄 correlated-data-*.parquet
├── 📁 2024/01/16/ 
├── 📁 summaries/      ← Pre-aggregated data
│   ├── 📄 device-summary-*.parquet
│   └── 📄 store-summary-*.parquet
```

### **Step 4: Key Power Query Code**

**Main Data Connection**:
```m
let
    Source = AzureStorage.Blobs("https://yourstorageaccount.blob.core.windows.net/finops-data"),
    FilteredParquet = Table.SelectRows(Source, each Text.EndsWith([Name], ".parquet") and Text.StartsWith([Name], "2024/")),
    CombinedData = Table.Combine(Table.AddColumn(FilteredParquet, "Data", each Parquet.Document([Content]))[Data])
in
    CombinedData
```

**Filter by Date Range (Performance)**:
```m
Table.SelectRows(Source, each [TimeWindow] >= #datetime(2024, 1, 1, 0, 0, 0))
```

---

## 📊 **Essential DAX Measures**

```dax
// Core Metrics
Total Cost = SUM(CorrelatedData[AllocatedCost])
Total Tokens = SUM(CorrelatedData[TokensUsed])
Cost Per Token = DIVIDE([Total Cost], [Total Tokens])

// Time Intelligence  
Cost vs Last Month = [Total Cost] - CALCULATE([Total Cost], DATEADD('Date'[Date], -1, MONTH))

// Device Analytics
Top Device Cost = CALCULATE([Total Cost], TOPN(1, VALUES(CorrelatedData[DeviceId]), [Total Cost]))

// Store Analytics
Store Count = DISTINCTCOUNT(CorrelatedData[StoreNumber])
```

---

## ⚡ **Performance Tips**

### **Data Loading**
- ✅ Use **Parquet files** (fastest)
- ✅ Load only **needed columns**
- ✅ Filter by **date range** early
- ❌ Avoid loading all JSON/CSV files

### **Refresh Setup**
- **Frequency**: Every 30 minutes
- **Incremental Refresh**: 7 days sliding window  
- **Archive**: Keep 2 years historical

### **Model Optimization**
- Set `TimeWindow` as Date table relationship
- Mark date tables properly
- Use `DIVIDE()` instead of `/` operator

---

## 📈 **Ready-Made Visuals**

### **Executive KPIs**
```
📊 Card: Total Cost This Month
📊 Card: Cost Per Token  
📊 Card: Active Devices
📈 Line Chart: Daily Cost Trend
🥧 Pie Chart: Cost by Model (GPT-4 vs GPT-3.5)
```

### **Operational Dashboard**
```
📊 Bar Chart: Top 10 Devices by Cost
🗺️ Map: Cost by Store Location  
📈 Column Chart: Hourly Usage Patterns
📋 Matrix: Device Performance Grid
⚠️ Table: Cost Anomalies (>2 std dev)
```

---

## 🔧 **Troubleshooting**

| Issue | Quick Fix |
|-------|-----------|
| **"Cannot connect to storage"** | Check storage account key/permissions |
| **"No data showing"** | Verify date filters and container names |  
| **"Slow refresh"** | Enable incremental refresh, use Parquet only |
| **"Charts empty"** | Check measure definitions and relationships |

---

## 💡 **Pro Tips**

1. **Start Simple**: Connect to daily summaries first, then add detailed data
2. **Test with Sample**: Use 1-2 days of data initially 
3. **Bookmark Queries**: Save your working M queries for reuse
4. **Monitor Refresh**: Set up email alerts for refresh failures
5. **Document Changes**: Track modifications for team collaboration

---

## 📞 **Quick Help**

**Data not loading?** Check:
- Storage account exists and accessible
- Container names match deployment (`finops-data`)
- Files exist in expected folder structure (`YYYY/MM/DD/`)

**Performance slow?** Try:
- Reduce date range filter
- Load summaries instead of detailed data
- Check your internet connection

**Need help?** Reference the full [Power BI Setup Guide](./PowerBI-Setup-Guide.md) for detailed instructions.