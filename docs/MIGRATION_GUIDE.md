# Migration Guide: Deprecated Dependencies Refactor

## Overview

This migration guide covers the refactoring of deprecated and outdated Python dependencies in the FinOps solution. The changes include replacing deprecated monitoring libraries and updating all packages to their latest stable versions.

## Critical Changes: Deprecated Packages Replaced

### 1. OpenCensus → OpenTelemetry Migration

**DEPRECATED**: `opencensus-ext-azure==1.1.13`
**REPLACEMENT**: `azure-monitor-opentelemetry>=1.6.0`

#### Breaking Changes:
- **Import statements**: All `from opencensus.ext.azure` imports must be replaced
- **Configuration**: Different configuration approach for Azure Monitor
- **API changes**: New OpenTelemetry API patterns

#### Code Changes Required:

**Before (deprecated):**
```python
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure import trace_exporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer

# Setup
handler = AzureLogHandler(connection_string=connection_string)
tracer = Tracer(
    exporter=trace_exporter.AzureExporter(connection_string=connection_string),
    sampler=ProbabilitySampler(1.0),
)
```

**After (modern):**
```python
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
import logging

# Setup
configure_azure_monitor(connection_string=connection_string)
tracer = trace.get_tracer(__name__)

# Use structured logging instead of custom handlers
logger = logging.getLogger(__name__)
```

### 2. ApplicationInsights Library Removal

**DEPRECATED**: `applicationinsights==0.11.10` (no longer maintained by Microsoft)
**REPLACEMENT**: Use Azure Monitor OpenTelemetry or native Azure SDK logging

#### Migration Strategy:
- Replace custom telemetry tracking with OpenTelemetry spans
- Use structured logging for application insights
- Leverage Azure Functions built-in telemetry

## Updated Dependencies

### Major Version Updates

| Package | Old Version | New Version | Breaking Changes |
|---------|------------|-------------|------------------|
| `azure-functions` | 1.18.0 | 1.24.0 | None expected |
| `azure-identity` | 1.15.0 | 1.25.1 | None expected |
| `pydantic` | 2.5.2 | 2.12.2 | Minor API improvements |
| `requests` | 2.31.0 | 2.32.5 | Security fixes |
| `pandas` | 2.1.4 | 2.3.3 | Performance improvements |
| `numpy` | 1.25.2 | 1.26.0* | Compatible with pandas 2.3.3 |

*Note: numpy 2.3.4 is available but we're using 1.26.0 for better pandas compatibility.

### New Semantic Versioning

All dependencies now use semantic ranges (e.g., `>=1.24.0,<2.0.0`) to:
- Allow automatic security updates
- Prevent breaking changes from major versions
- Follow Python packaging best practices

## Code Migration Steps

### 1. Pydantic v1 → v2 API Updates

**Key Changes:**
- `BaseSettings` → `BaseModel` with `ConfigDict`
- `@validator` → `@field_validator` 
- `env` parameter → `validation_alias`

**Before:**
```python
from pydantic import BaseSettings, Field, validator

class Config(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    
    @validator("database_url")
    def validate_url(cls, v):
        return v.lower()
    
    class Config:
        env_file = ".env"
```

**After:**
```python
from pydantic import BaseModel, Field, field_validator, ConfigDict

class Config(BaseModel):
    model_config = ConfigDict(env_file=".env", case_sensitive=False)
    
    database_url: str = Field(validation_alias="DATABASE_URL")
    
    @field_validator("database_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return v.lower()
```

### 2. Monitoring and Telemetry Updates

If your code currently uses the deprecated packages, update as follows:

**Remove imports:**
```python
# DELETE these deprecated imports
from opencensus.ext.azure import trace_exporter
from opencensus.trace.tracer import Tracer
from applicationinsights import TelemetryClient
```

**Add new imports:**
```python
# ADD these modern imports
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
import logging
```

**Update initialization:**
```python
# Modern setup
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
)

# Get tracer for this module
tracer = trace.get_tracer(__name__)

# Use with context manager for tracing
with tracer.start_as_current_span("operation_name") as span:
    span.set_attribute("custom.attribute", "value")
    # Your code here
```

### 3. Configuration Updates

Update your environment variables and configuration:

**Function App Settings:**
- Keep existing `APPLICATIONINSIGHTS_CONNECTION_STRING`
- OpenTelemetry will automatically use this variable
- Remove any custom OpenCensus configuration

**Local Development:**
Update your `local.settings.json`:
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "your-connection-string",
    "LOG_ANALYTICS_WORKSPACE_ID": "your-workspace-id",
    "COST_MANAGEMENT_SCOPE": "/subscriptions/your-subscription-id",
    "STORAGE_ACCOUNT_NAME": "your-storage-account"
  }
}
```

## Testing the Migration

### 1. Unit Tests
Run the existing unit tests to ensure no regressions:

```bash
cd src/functions/finops-data-collector
python -m pytest tests/unit/ -v
```

### 2. Integration Testing
Test the complete data flow:

```bash
# Test telemetry collection
func start --functions finops_timer_trigger

# Check Application Insights for telemetry
# Monitor function execution logs
```

### 3. Validation Checklist

- [ ] All deprecated packages removed
- [ ] Modern OpenTelemetry telemetry working
- [ ] Pydantic v2 configuration loading correctly
- [ ] Azure Functions deploying successfully
- [ ] Telemetry appearing in Application Insights
- [ ] Cost data collection still functioning
- [ ] Storage operations working

## Rollback Plan

If issues occur during migration:

1. **Immediate rollback**: Revert to previous `requirements.txt` files
2. **Partial rollback**: Keep package updates but revert telemetry changes
3. **Configuration rollback**: Restore old Pydantic v1 patterns if needed

## Performance Improvements Expected

- **OpenTelemetry**: Better performance and lower overhead than OpenCensus
- **Latest Azure SDKs**: Improved reliability and performance
- **Pydantic v2**: Faster validation and serialization
- **Updated pandas/numpy**: Better memory usage and performance

## Security Benefits

- **Updated requests**: Latest security patches
- **Modern Azure SDKs**: Latest security features and authentication
- **Eliminated deprecated packages**: Remove potential security vulnerabilities

## Support and Documentation

- **OpenTelemetry**: https://opentelemetry.io/docs/
- **Azure Monitor OpenTelemetry**: https://docs.microsoft.com/azure/azure-monitor/app/opentelemetry-enable
- **Pydantic v2**: https://docs.pydantic.dev/latest/migration/