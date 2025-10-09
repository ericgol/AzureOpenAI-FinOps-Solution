# EventHub to Application Insights Function Migration Summary

## Overview
This document summarizes the migration from the deprecated Application Insights Python SDK (v0.11.10) to the Azure Monitor OpenTelemetry package, as recommended by Microsoft.

## Migration Scope
**Function:** `eventhub-to-appinsights`  
**Migration Date:** 2025-10-09  
**Migration Type:** Full refactor from Application Insights SDK to OpenTelemetry

## Changes Made

### 1. Dependencies Updated (`requirements.txt`)

#### Before (Deprecated)
```
applicationinsights==0.11.10
opencensus-ext-azure==1.1.13
azure-monitor-opentelemetry==1.2.0
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
```

#### After (Modern OpenTelemetry)
```
azure-monitor-opentelemetry-exporter==1.0.0b26
opentelemetry-api==1.25.0
opentelemetry-sdk==1.25.0
opentelemetry-instrumentation==0.46b0
opentelemetry-exporter-otlp==1.25.0
```

### 2. Code Changes

#### Import Updates
**Before:**
```python
from applicationinsights import TelemetryClient
from applicationinsights.channel import TelemetryChannel
from applicationinsights.extensibility import TelemetryProcessor
```

**After:**
```python
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter, AzureMonitorMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.trace import Status, StatusCode
```

#### Telemetry Client Replacement
**Before:**
```python
def get_telemetry_client() -> TelemetryClient:
    connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
    client = TelemetryClient(connection_string)
    # Configure telemetry channel
    return client
```

**After:**
```python
def setup_opentelemetry() -> tuple:
    connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": "eventhub-to-appinsights",
        "service.version": "1.0.0",
        "service.instance.id": os.environ.get('WEBSITE_INSTANCE_ID', 'local')
    })
    
    # Set up trace and metrics providers with Azure Monitor exporters
    # ... (detailed setup code)
    
    return tracer, meter
```

#### Telemetry Data Structure
**Before:**
```python
def create_trace_telemetry(telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
    # Created trace properties and custom dimensions for Application Insights
    return {
        'trace_props': trace_props,
        'custom_dimensions': custom_dimensions
    }
```

**After:**
```python
def create_span_attributes(telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
    # Creates OpenTelemetry span attributes with proper semantic conventions
    attributes = {
        'event.type': event_type,
        'http.status_code': status_code,
        'ai.tokens.used': tokens_used,
        # ... structured attributes following OpenTelemetry semantic conventions
    }
    return cleaned_attributes
```

#### Telemetry Sending
**Before:**
```python
telemetry_client.track_trace(
    message=telemetry['trace_props']['message'],
    severity=telemetry['trace_props']['severity'],
    properties=telemetry['custom_dimensions']
)

telemetry_client.track_metric(
    name='EventHub.ProcessedEvents',
    value=processed_count,
    properties={'FunctionName': 'eventhub_to_appinsights'}
)

telemetry_client.track_exception()
telemetry_client.flush()
```

**After:**
```python
# Create structured spans with attributes
with tracer.start_as_current_span("eventhub_batch_processing") as batch_span:
    batch_span.set_attribute("eventhub.batch_size", len(events))
    
    for event in events:
        with tracer.start_as_current_span(span_name) as event_span:
            # Set span attributes
            for key, value in attributes.items():
                event_span.set_attribute(key, value)
            
            # Set span status
            event_span.set_status(Status(StatusCode.OK))
            
            # Add events to spans
            event_span.add_event("apim_telemetry_processed", attributes={...})

# Use OpenTelemetry metrics
processed_events_counter.add(processed_count, {"function.name": "eventhub_to_appinsights"})

# Exception handling with spans
error_span.record_exception(e)
```

## Key Improvements

### 1. **Modern Telemetry Standards**
- Uses OpenTelemetry semantic conventions for attributes
- Structured span hierarchy for better traceability
- Standardized attribute naming (e.g., `http.status_code`, `ai.tokens.used`)

### 2. **Better Performance**
- Batch span processing with Azure Monitor exporter
- Automatic resource detection and tagging
- Optimized telemetry export intervals

### 3. **Enhanced Observability**
- Hierarchical spans for batch and individual event processing
- Proper span status tracking (OK, ERROR)
- Rich span events for detailed tracking
- Exception recording in spans

### 4. **Future-Proof Architecture**
- Uses Microsoft's recommended telemetry approach
- Compatible with OpenTelemetry ecosystem
- Better integration with Azure Monitor features

### 5. **Improved Error Handling**
- Proper span status codes for errors
- Exception recording in telemetry
- Graceful degradation on telemetry failures

## Backwards Compatibility

### Environment Variables
✅ **No changes required** - Still uses `APPLICATIONINSIGHTS_CONNECTION_STRING`

### Function Configuration
✅ **No changes required** - `host.json`, `function.json` remain unchanged

### Data Schema
✅ **Compatible** - All original telemetry data points are preserved with OpenTelemetry semantic attribute names

## Deployment Notes

1. **Package Updates**: Ensure the new requirements.txt is deployed with updated OpenTelemetry packages
2. **Connection String**: No changes to Application Insights connection string
3. **Monitoring**: Telemetry data will appear in Azure Monitor with improved structure
4. **Testing**: Use the provided `validate_refactor.py` script to verify functionality

## Validation

The migration has been validated with:
- ✅ Core function syntax compilation
- ✅ Event parsing functionality
- ✅ Span attribute creation
- ✅ Error handling scenarios
- ✅ Empty value filtering

## Support

For issues related to this migration:
1. Check Azure Monitor OpenTelemetry documentation
2. Verify OpenTelemetry package versions
3. Ensure Application Insights connection string is properly configured
4. Review span data in Azure Monitor for proper structure

---

**Migration Status:** ✅ **COMPLETE**  
**Validation Status:** ✅ **PASSED**  
**Ready for Deployment:** ✅ **YES**