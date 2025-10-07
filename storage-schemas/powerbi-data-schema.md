# Power BI Data Schema for FinOps Solution

This document describes the data schema stored in Azure Storage for Power BI consumption.

## Correlated FinOps Data Schema

The main dataset for Power BI reporting is stored in the `finops-data` container with the following schema:

### Table: FinOpsCorrelatedData

| Column Name | Data Type | Description | Example |
|-------------|-----------|-------------|---------|
| **TimeGenerated** | DateTime | Timestamp when the API call was made | 2024-01-15T10:30:00Z |
| **Date** | Date | Date of the API call (for daily aggregation) | 2024-01-15 |
| **deviceId** | String | User identifier from API headers | user123, test-user-456 |
| **storeNumber** | String | Store identifier from API headers | store001, location-nyc |
| **ApiName** | String | Name of the API operation | chat/completions, embeddings |
| **ModelName** | String | OpenAI model used | gpt-35-turbo, gpt-4 |
| **TokensUsed** | Integer | Total tokens consumed | 150, 2500 |
| **PromptTokens** | Integer | Tokens in the prompt/input | 50, 200 |
| **CompletionTokens** | Integer | Tokens in the response/output | 100, 300 |
| **ResponseTime** | Integer | Response time in milliseconds | 250, 1500 |
| **StatusCode** | Integer | HTTP status code | 200, 400, 500 |
| **ResourceId** | String | Azure resource identifier | /subscriptions/.../resourceGroups/... |
| **ResourceName** | String | Name of the Azure resource | myopenai-eastus2 |
| **DailyCost** | Decimal | Total daily cost for the resource | 45.67, 123.45 |
| **AllocatedCost** | Decimal | Cost allocated to this user/store | 0.45, 2.34 |
| **UsageShare** | Decimal | Percentage of usage (0.0-1.0) | 0.025, 0.15 |
| **Currency** | String | Cost currency | USD, EUR |
| **Environment** | String | Environment (dev/prod/staging) | dev, prod |
| **Region** | String | Azure region | eastus2, westeurope |

## Usage Patterns for Power BI

### 1. Cost per User Dashboard
```dax
UserCost = SUM(FinOpsCorrelatedData[AllocatedCost])
UserTokens = SUM(FinOpsCorrelatedData[TokensUsed])
CostPerToken = DIVIDE([UserCost], [UserTokens], 0)
```

### 2. Store Performance Analysis
```dax
StoreCost = 
    CALCULATE(
        SUM(FinOpsCorrelatedData[AllocatedCost]),
        FinOpsCorrelatedData[storeNumber] <> "unknown"
    )

StoreAPICount = 
    CALCULATE(
        COUNTROWS(FinOpsCorrelatedData),
        FinOpsCorrelatedData[storeNumber] <> "unknown"
    )
```

### 3. Daily Trend Analysis
```dax
DailyCostTrend = 
    CALCULATE(
        SUM(FinOpsCorrelatedData[AllocatedCost]),
        DATESINPERIOD(
            FinOpsCorrelatedData[Date],
            MAX(FinOpsCorrelatedData[Date]),
            -30,
            DAY
        )
    )
```

### 4. Model Usage Distribution
```dax
ModelCostShare = 
    DIVIDE(
        SUM(FinOpsCorrelatedData[AllocatedCost]),
        CALCULATE(
            SUM(FinOpsCorrelatedData[AllocatedCost]),
            ALL(FinOpsCorrelatedData[ModelName])
        )
    )
```

## Data Refresh Configuration

### Power BI Service
- **Refresh Frequency**: Every 2-4 hours
- **Data Source**: Azure Blob Storage (finops-data container)
- **Authentication**: Service Principal or Managed Identity
- **File Format**: Parquet (recommended) or JSON

### Connection String Template
```
Azure Blob Storage:
Account Name: [STORAGE_ACCOUNT_NAME]
Container: finops-data
Authentication: Service Principal
```

## Recommended Visualizations

### 1. Executive Dashboard
- **Cost Overview Card**: Total monthly cost
- **User Activity Card**: Active users count
- **Store Performance Card**: Top performing stores
- **Daily Trend Line**: Cost over time

### 2. User Analysis Page
- **Top Users Table**: Users by cost and usage
- **User Cost Distribution**: Pie chart of cost per user
- **User Activity Heatmap**: API calls by user and hour
- **Cost per Token Scatter**: Efficiency analysis

### 3. Store Operations Page
- **Store Comparison Bar**: Cost by store
- **Geographic Map**: Store locations and costs (if geo data available)
- **Store Trend Lines**: Usage patterns over time
- **Model Usage by Store**: Preferred models per location

### 4. Model Performance Page
- **Model Cost Breakdown**: Pie chart of cost by model
- **Token Usage Comparison**: Tokens per model type
- **Response Time Analysis**: Performance metrics
- **Model Efficiency Metrics**: Cost per token by model

## Data Preparation Steps

### 1. Power Query Transformations
```powerquery
// Remove unknown users/stores for analysis
= Table.SelectRows(Source, each ([deviceId] <> "unknown" and [storeNumber] <> "unknown"))

// Add calculated columns
= Table.AddColumn(PreviousStep, "CostPerToken", each [AllocatedCost] / [TokensUsed])
= Table.AddColumn(PreviousStep, "Month", each Date.StartOfMonth([Date]))
= Table.AddColumn(PreviousStep, "Week", each Date.StartOfWeek([Date]))
```

### 2. Hierarchies Setup
```
Date Hierarchy:
├── Year
├── Quarter  
├── Month
└── Day

Geography Hierarchy (if available):
├── Region
├── Store Group
└── Store ID

User Hierarchy:
├── Business Unit
├── Department
└── User ID
```

## Performance Optimization

### 1. Data Model Optimization
- Use star schema with fact table (FinOpsCorrelatedData)
- Create dimension tables for Users, Stores, Models
- Implement date table for time intelligence
- Use appropriate data types (avoid text for numbers)

### 2. Storage Optimization
- Partition data by date (monthly partitions)
- Use Parquet format for better compression
- Implement incremental refresh in Power BI
- Archive old data to reduce dataset size

### 3. Query Optimization
- Create appropriate indexes in storage
- Use column store indexes where possible
- Implement aggregation tables for common queries
- Cache frequently accessed data

## Sample Power BI Template

A Power BI template file (`.pbit`) is available at:
`/powerbi-templates/FinOps-Dashboard-Template.pbit`

This template includes:
- Pre-configured data connections
- Sample visualizations
- DAX measures and calculations
- Recommended page layouts
- Color schemes and formatting

## Troubleshooting

### Common Issues:
1. **Data Refresh Failures**: Check storage account permissions
2. **Slow Performance**: Implement recommended optimizations
3. **Missing Data**: Verify Function App execution logs
4. **Authentication Errors**: Update service principal credentials

### Data Quality Checks:
- Verify no duplicate records by RequestId + TimeGenerated
- Ensure cost data aligns with Azure billing
- Check for missing deviceId/storeNumber patterns
- Validate token counts against API responses