# Power BI Setup Guide for Azure OpenAI FinOps Solution

This guide walks you through setting up Power BI to visualize your Azure OpenAI cost data with device/store attribution.

## 📊 **Data Architecture Overview**

The FinOps solution stores data in Azure Blob Storage with a Power BI-optimized structure:

```
Storage Account: [your-storage-account]
├── Container: finops-data/
│   ├── 2024/01/15/correlated-data-103045.parquet    # Daily partitions
│   ├── 2024/01/16/correlated-data-103045.parquet
│   └── summaries/
│       ├── device-summary-2024-01-15-103045.parquet
│       └── store-summary-2024-01-15-103045.parquet
├── Container: raw-telemetry/                        # Raw data backups
└── Container: cost-data/                            # Raw cost data
```

## 🔧 **Prerequisites**

### **1. Azure Access Requirements**
- **Storage Account Access**: Reader role on the storage account
- **Service Principal** (recommended for production) or **Personal Account**
- **Storage Account Name** and **Access Key** (or managed identity)

### **2. Power BI Requirements**
- Power BI Pro or Premium license
- Power BI Desktop (latest version)
- Access to Power BI Service (online)

---

## 📋 **Step 1: Configure Data Sources**

### **Option A: Azure Blob Storage Connector (Recommended)**

1. **Open Power BI Desktop**
2. **Get Data** → **Azure** → **Azure Blob Storage**
3. **Enter Storage Account URL**:
   ```
   https://[your-storage-account-name].blob.core.windows.net
   ```
4. **Authentication Method**:
   - **Account Key**: Use storage account access key
   - **Organizational Account**: Use Azure AD authentication
   - **Shared Access Signature (SAS)**: If using SAS tokens

### **Option B: Azure Data Lake Storage Gen2 (Advanced)**
If your storage account has hierarchical namespaces enabled:

1. **Get Data** → **Azure** → **Azure Data Lake Storage Gen2**
2. **Enter URL**: Same as above
3. **Authentication**: Same options as Blob Storage

---

## 🗂️ **Step 2: Connect to Main Data Tables**

### **A. Primary Fact Table: Correlated Data**

1. **Navigate to Container**: `finops-data`
2. **Select Folder Pattern**: `2024/` (or current year)
3. **File Type**: **Parquet** (best performance)
4. **Load Method**: **Combine Files** across all date folders

**Power Query M Code Example**:
```m
let
    Source = AzureStorage.Blobs("https://yourstorageaccount.blob.core.windows.net/finops-data"),
    #"Filtered Rows" = Table.SelectRows(Source, each Text.StartsWith([Name], "2024/")),
    #"Filtered Parquet" = Table.SelectRows(#"Filtered Rows", each Text.EndsWith([Name], ".parquet")),
    #"Added Custom" = Table.AddColumn(#"Filtered Parquet", "Transform File", each Parquet.Document([Content])),
    #"Expanded Table" = Table.ExpandTableColumn(#"Added Custom", "Transform File", {"DeviceId", "StoreNumber", "AllocatedCost", "TokensUsed", "ApiCalls", "TimeWindow", "ModelFamily", "CostType", "ShiftCategory", "IsBusinessHours"})
in
    #"Expanded Table"
```

### **B. Device Summary Table**

1. **Navigate to**: `finops-data/summaries/`
2. **Filter**: Files starting with `device-summary-`
3. **Combine Files**: All device summary Parquet files

### **C. Store Summary Table**

1. **Navigate to**: `finops-data/summaries/`  
2. **Filter**: Files starting with `store-summary-`
3. **Combine Files**: All store summary Parquet files

---

## 🔄 **Step 3: Data Refresh Configuration**

### **Incremental Refresh Setup**

1. **Select Table**: Correlated Data table
2. **Home Tab** → **Manage Parameters**
3. **Create Parameters**:
   ```
   RangeStart = #datetime(2024, 1, 1, 0, 0, 0) [DateTime]
   RangeEnd = #datetime(2024, 12, 31, 23, 59, 59) [DateTime]
   ```

4. **Filter by Date**:
   ```m
   #"Filtered Rows" = Table.SelectRows(Source, 
       each [TimeWindow] >= RangeStart and [TimeWindow] < RangeEnd)
   ```

5. **Configure Incremental Refresh**:
   - **Archive data starting**: 2 years before refresh date
   - **Incrementally refresh data starting**: 7 days before refresh date
   - **Detect data changes**: Yes
   - **Refresh frequency**: Every 30 minutes

### **Scheduled Refresh (Power BI Service)**

1. **Publish Report** to Power BI Service
2. **Dataset Settings** → **Scheduled Refresh**
3. **Configure Schedule**:
   - **Frequency**: Every 30 minutes (aligns with function execution)
   - **Time Zone**: Your local time zone
   - **Failure Notifications**: Enable

---

## 📊 **Step 4: Data Model Design**

### **Relationships**

Create relationships between tables:

```
CorrelatedData[DeviceId] → DevicesSummary[DeviceId] (Many-to-One)
CorrelatedData[StoreNumber] → StoresSummary[StoreNumber] (Many-to-One)
CorrelatedData[TimeWindow] → DateTable[Date] (Many-to-One)
```

### **Date Table**

Create a comprehensive date table:

```dax
DateTable = 
GENERATE(
    CALENDAR(DATE(2024, 1, 1), DATE(2025, 12, 31)),
    VAR CurrentDate = [Date]
    RETURN ROW(
        "Year", YEAR(CurrentDate),
        "Month", MONTH(CurrentDate),
        "MonthName", FORMAT(CurrentDate, "MMMM"),
        "Quarter", "Q" & QUARTER(CurrentDate),
        "Weekday", WEEKDAY(CurrentDate),
        "WeekdayName", FORMAT(CurrentDate, "dddd"),
        "IsBusinessDay", WEEKDAY(CurrentDate, 2) <= 5,
        "DayOfMonth", DAY(CurrentDate)
    )
)
```

### **Calculated Measures**

```dax
-- Total Cost Allocated
Total Cost = SUM(CorrelatedData[AllocatedCost])

-- Total Tokens
Total Tokens = SUM(CorrelatedData[TokensUsed])

-- Average Cost Per Token
Cost Per Token = DIVIDE([Total Cost], [Total Tokens], 0)

-- Cost Variance from Previous Period
Cost Variance = 
VAR CurrentCost = [Total Cost]
VAR PreviousCost = CALCULATE([Total Cost], DATEADD(DateTable[Date], -1, MONTH))
RETURN CurrentCost - PreviousCost

-- Top Devices by Cost
Top Devices = 
RANKX(
    ALL(CorrelatedData[DeviceId]),
    [Total Cost],
    ,
    DESC
)

-- Business Hours vs Non-Business Hours
Business Hours Cost = 
CALCULATE([Total Cost], CorrelatedData[IsBusinessHours] = TRUE)

Non-Business Hours Cost = 
CALCULATE([Total Cost], CorrelatedData[IsBusinessHours] = FALSE)

-- Shift Analysis
Morning Shift Cost = 
CALCULATE([Total Cost], CorrelatedData[ShiftCategory] = "Morning")

Evening Shift Cost = 
CALCULATE([Total Cost], CorrelatedData[ShiftCategory] = "Evening")

Night Shift Cost = 
CALCULATE([Total Cost], CorrelatedData[ShiftCategory] = "Night")
```

---

## 📈 **Step 5: Report Templates**

### **Executive Dashboard**

**Key Visuals**:
1. **Cost Trend** (Line Chart): Total cost over time
2. **Store Performance** (Map): Cost by store location
3. **Model Usage** (Pie Chart): Cost breakdown by AI model (GPT-4, GPT-3.5)
4. **Top Devices** (Bar Chart): Highest cost devices
5. **KPI Cards**: Total cost, total tokens, cost per token

### **Operational Dashboard**

**Key Visuals**:
1. **Shift Analysis** (Stacked Column): Cost by shift category
2. **Device Utilization** (Scatter Plot): Usage vs. cost efficiency
3. **Store Comparison** (Matrix): Detailed store metrics
4. **Anomaly Detection** (Line Chart): Unusual usage patterns
5. **Real-time Metrics** (Gauge): Current period performance

### **Device Deep Dive**

**Key Visuals**:
1. **Device Performance Matrix**: All devices with key metrics
2. **Usage Patterns** (Heat Map): Hourly usage by device
3. **Cost Allocation** (Waterfall): How costs are allocated
4. **Device Trends** (Small Multiples): Individual device trends

---

## 🔄 **Step 6: Advanced Features**

### **Row-Level Security (RLS)**

For multi-tenant scenarios:

```dax
-- Create role: Store Manager
[StoreNumber] = USERNAME() 

-- Or for device-specific access
[DeviceId] IN VALUES(UserDeviceMapping[DeviceId])
```

### **Automatic Anomaly Detection**

```dax
-- Detect unusual cost spikes
Cost Anomaly = 
VAR AvgCost = AVERAGE(CorrelatedData[AllocatedCost])
VAR StdDev = STDEV.S(CorrelatedData[AllocatedCost])
VAR CurrentCost = MAX(CorrelatedData[AllocatedCost])
RETURN 
IF(CurrentCost > AvgCost + (2 * StdDev), "High", 
   IF(CurrentCost < AvgCost - (2 * StdDev), "Low", "Normal"))
```

### **Predictive Analytics**

```dax
-- Forecast next month's cost based on trends
Forecasted Cost = 
VAR LastThreeMonths = 
    CALCULATE(
        [Total Cost],
        DATESINPERIOD(DateTable[Date], LASTDATE(DateTable[Date]), -3, MONTH)
    )
VAR GrowthRate = 
    DIVIDE(
        [Total Cost] - CALCULATE([Total Cost], DATEADD(DateTable[Date], -1, MONTH)),
        CALCULATE([Total Cost], DATEADD(DateTable[Date], -1, MONTH))
    )
RETURN [Total Cost] * (1 + GrowthRate)
```

---

## 🚀 **Step 7: Performance Optimization**

### **Query Optimization**

1. **Use Parquet Format**: Always prefer Parquet over JSON/CSV
2. **Partition Elimination**: Filter by date ranges in queries
3. **Column Selection**: Only import needed columns
4. **Data Types**: Ensure optimal data types (DateTime, Decimal, etc.)

### **Model Optimization**

1. **Disable Auto-Relationships**: Manually create relationships
2. **Mark Date Tables**: Mark your date table as a date table
3. **Optimize Measures**: Use DIVIDE() instead of division operator
4. **Remove Unused Columns**: Remove unnecessary columns from model

### **Refresh Optimization**

1. **Incremental Refresh**: Essential for large datasets
2. **Parallel Processing**: Enable parallel refresh where possible
3. **Compression**: Enable dataset compression
4. **Memory Usage**: Monitor and optimize memory usage

---

## 🔍 **Step 8: Testing & Validation**

### **Data Validation Checklist**

- [ ] **Cost totals match** Azure Cost Management reports
- [ ] **Device attribution** covers all API calls
- [ ] **Time zones** are consistent across data sources
- [ ] **Refresh timing** aligns with function execution
- [ ] **Performance** meets user requirements (< 5 second load times)

### **User Acceptance Testing**

1. **Create test scenarios** with known cost amounts
2. **Validate drill-down paths** work correctly
3. **Test filtering and slicing** across all dimensions
4. **Verify mobile responsiveness** if mobile access needed

---

## 🛠️ **Troubleshooting Guide**

### **Common Issues**

**1. Data Source Connection Fails**
```
Solution: Check storage account permissions and network access
- Verify storage account key/SAS token
- Check firewall rules
- Confirm container names match configuration
```

**2. Incremental Refresh Not Working**
```
Solution: Verify parameter setup and date filtering
- Ensure RangeStart/RangeEnd parameters exist
- Check date filter logic in Power Query
- Verify incremental refresh policy settings
```

**3. Performance Issues**
```
Solution: Optimize data model and queries
- Enable query folding where possible
- Reduce unnecessary columns
- Check relationship cardinality
- Monitor memory usage
```

**4. Data Latency**
```
Solution: Align refresh schedules
- Function runs every 6 minutes
- Power BI refresh every 30 minutes
- Consider real-time streaming for critical metrics
```

---

## 📋 **Best Practices Summary**

### **✅ Do's**
- Use Parquet files for best performance
- Implement incremental refresh for large datasets
- Create proper relationships between tables
- Use calculated measures instead of calculated columns
- Test with realistic data volumes
- Document your data model and relationships

### **❌ Don'ts**
- Don't use DirectQuery unless absolutely necessary
- Don't import all historical data at once
- Don't create circular relationships
- Don't ignore data refresh failures
- Don't skip testing with end users
- Don't forget to optimize for mobile viewing

---

## 📞 **Support & Resources**

### **Data Schema Reference**
- [Correlated Data Schema](./schemas/correlated-data-schema.md)
- [Device Summary Schema](./schemas/device-summary-schema.md)
- [Store Summary Schema](./schemas/store-summary-schema.md)

### **Sample Reports**
- [Executive Dashboard Template](./templates/executive-dashboard.pbix)
- [Operational Dashboard Template](./templates/operational-dashboard.pbix)
- [Device Deep Dive Template](./templates/device-deep-dive.pbix)

### **Power BI Resources**
- [Power BI Documentation](https://docs.microsoft.com/power-bi/)
- [DAX Reference](https://docs.microsoft.com/dax/)
- [Power Query M Reference](https://docs.microsoft.com/powerquery-m/)

This setup provides a robust, scalable Power BI solution that grows with your Azure OpenAI usage and provides actionable insights for cost optimization and operational efficiency.