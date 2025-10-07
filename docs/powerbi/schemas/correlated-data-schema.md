# Correlated Data Schema

This document describes the schema for the main correlated data table that Power BI connects to.

## Table: CorrelatedData

**Primary Fact Table**: Contains device/store cost allocations with full correlation details.

### Core Identity Fields
| Field Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| `DeviceId` | String | Device identifier from APIM telemetry | `"device-001"` |
| `StoreNumber` | String | Store identifier from APIM telemetry | `"store-123"` |
| `DeviceStoreKey` | String | Composite key for device-store combination | `"device-001_store-123"` |
| `ResourceId` | String | Azure OpenAI resource ID | `"/subscriptions/.../openai-001"` |
| `ResourceName` | String | Name of the OpenAI resource | `"openai-001"` |
| `ResourceGroup` | String | Azure resource group name | `"rg-openai"` |

### Cost and Usage Metrics
| Field Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| `AllocatedCost` | Decimal | Cost allocated to this device/store | `5.25` |
| `TotalCost` | Decimal | Total cost for the time window | `21.00` |
| `TokensUsed` | Integer | Number of tokens used by this device | `1200` |
| `ApiCalls` | Integer | Number of API calls made by this device | `15` |
| `AvgResponseTime` | Float | Average response time in milliseconds | `185.5` |
| `Currency` | String | Cost currency | `"USD"` |

### Cost Analysis Fields
| Field Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| `CostType` | String | Type of cost (Input Tokens, Output Tokens, etc.) | `"Input Tokens"` |
| `ModelFamily` | String | AI model family (GPT-5, GPT-4, GPT-3.5, etc.) | `"GPT-5"` |
| `MeterName` | String | Azure meter name | `"GPT-4 Input Tokens"` |
| `AllocationMethod` | String | Method used for cost allocation | `"proportional"` |
| `CostPerToken` | Decimal | Cost per token for this allocation | `0.004375` |
| `CostPerApiCall` | Decimal | Cost per API call for this allocation | `0.35` |

### Share and Proportion Fields  
| Field Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| `TokenShare` | Float | Proportion of total tokens (0-1) | `0.571` |
| `ApiCallShare` | Float | Proportion of total API calls (0-1) | `0.600` |

### Time and Temporal Fields
| Field Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| `TimeWindow` | DateTime | Time window for correlation | `2024-01-15T10:00:00Z` |
| `CorrelationTimestamp` | DateTime | When correlation was performed | `2024-01-15T10:05:23Z` |
| `ProcessingDate` | Date | Date when data was processed | `2024-01-15` |
| `Hour` | Integer | Hour of day (0-23) | `10` |
| `DayOfWeek` | String | Day name | `"Monday"` |

### Operational Context Fields
| Field Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| `ShiftCategory` | String | Work shift (Morning, Evening, Night) | `"Morning"` |
| `IsBusinessHours` | Boolean | Whether during business hours (9-17) | `true` |
| `IsWeekday` | Boolean | Whether on a weekday | `true` |

### Attribution Quality Fields
| Field Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| `IsUnknownDevice` | Boolean | Whether device ID is unknown | `false` |
| `IsUnknownStore` | Boolean | Whether store number is unknown | `false` |
| `HasCompleteAttribution` | Boolean | Whether both device and store are known | `true` |
| `CorrelationConfidence` | Float | Confidence score (0-1) | `0.95` |
| `AllocationAccuracy` | Float | Allocation accuracy score (0-1) | `0.90` |
| `DeviceUtilizationScore` | Float | Device utilization score (0-1) | `0.82` |

## Data Quality Notes

### Required Fields
All records must have:
- `DeviceId` (may be "unknown")
- `StoreNumber` (may be "unknown") 
- `TimeWindow`
- `AllocatedCost` (≥ 0)

### Data Validation Rules
- `AllocatedCost` ≥ 0
- `TokensUsed` ≥ 0
- `ApiCalls` ≥ 0
- `CorrelationConfidence` between 0 and 1
- `AllocationAccuracy` between 0 and 1
- Sum of `AllocatedCost` should equal `TotalCost` for each time window

### Performance Considerations
- Primary partitioning by `ProcessingDate` (YYYY/MM/DD folder structure)
- Secondary sorting by `TimeWindow` 
- Indexed on `DeviceId`, `StoreNumber`, and `TimeWindow` for efficient querying

## Sample Record

```json
{
    "DeviceId": "device-001",
    "StoreNumber": "store-123", 
    "DeviceStoreKey": "device-001_store-123",
    "ResourceId": "/subscriptions/abc123/resourceGroups/rg-openai/providers/Microsoft.CognitiveServices/accounts/openai-001",
    "ResourceName": "openai-001",
    "ResourceGroup": "rg-openai",
    "AllocatedCost": 5.25,
    "TotalCost": 21.00,
    "TokensUsed": 1200,
    "ApiCalls": 15,
    "AvgResponseTime": 185.5,
    "Currency": "USD",
    "CostType": "Input Tokens",
    "ModelFamily": "GPT-5",
    "MeterName": "GPT-5 Input Tokens",
    "AllocationMethod": "proportional",
    "CostPerToken": 0.004375,
    "CostPerApiCall": 0.35,
    "TokenShare": 0.571,
    "ApiCallShare": 0.600,
    "TimeWindow": "2024-01-15T10:00:00Z",
    "CorrelationTimestamp": "2024-01-15T10:05:23Z",
    "ProcessingDate": "2024-01-15",
    "Hour": 10,
    "DayOfWeek": "Monday",
    "ShiftCategory": "Morning",
    "IsBusinessHours": true,
    "IsWeekday": true,
    "IsUnknownDevice": false,
    "IsUnknownStore": false, 
    "HasCompleteAttribution": true,
    "CorrelationConfidence": 0.95,
    "AllocationAccuracy": 0.90,
    "DeviceUtilizationScore": 0.82
}
```