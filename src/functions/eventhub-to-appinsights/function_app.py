"""
EventHub to Application Insights Telemetry Forwarder

Azure Function using Python v2 programming model that receives telemetry events from EventHub 
(originated from APIM policy) and forwards them to Application Insights for analysis and 
correlation with cost data.

The function processes batches of events from EventHub and sends them to Application Insights
as structured trace telemetry with all the custom properties needed for FinOps analysis.

Author: FinOps Team
"""

import logging
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

import azure.functions as func
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter, AzureMonitorMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.trace import Status, StatusCode, Tracer
from opentelemetry.metrics import Meter

# Initialize function app
app = func.FunctionApp()

# Global OpenTelemetry components (initialized once, reused across invocations)
_tracer: Optional[Tracer] = None
_meter: Optional[Meter] = None


def get_or_create_opentelemetry() -> Tuple[Tracer, Meter]:
    """
    Get or create OpenTelemetry tracer and meter providers.
    
    This function implements a singleton pattern to avoid reinitializing
    OpenTelemetry on every function invocation (Python v2 best practice).
    
    Returns:
        Tuple[Tracer, Meter]: Configured OpenTelemetry tracer and meter
        
    Raises:
        ValueError: If APPLICATIONINSIGHTS_CONNECTION_STRING is not configured
    """
    global _tracer, _meter
    
    # Return cached instances if already initialized
    if _tracer is not None and _meter is not None:
        return _tracer, _meter
    
    connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
    if not connection_string:
        raise ValueError("APPLICATIONINSIGHTS_CONNECTION_STRING environment variable is required")
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": "eventhub-to-appinsights",
        "service.version": "2.0.0",
        "service.instance.id": os.environ.get('WEBSITE_INSTANCE_ID', 'local'),
        "deployment.environment": os.environ.get('ENVIRONMENT', 'dev')
    })
    
    # Set up trace provider with Azure Monitor exporter
    trace_provider = TracerProvider(resource=resource)
    trace_exporter = AzureMonitorTraceExporter(connection_string=connection_string)
    trace_processor = BatchSpanProcessor(trace_exporter)
    trace_provider.add_span_processor(trace_processor)
    trace.set_tracer_provider(trace_provider)
    
    # Set up metrics provider with Azure Monitor exporter
    metric_exporter = AzureMonitorMetricExporter(connection_string=connection_string)
    metric_reader = PeriodicExportingMetricReader(
        exporter=metric_exporter,
        export_interval_millis=60000  # Export every 60 seconds
    )
    metrics_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(metrics_provider)
    
    # Cache tracer and meter instances
    _tracer = trace.get_tracer(__name__, "2.0.0")
    _meter = metrics.get_meter(__name__, "2.0.0")
    
    logging.info("OpenTelemetry providers initialized successfully")
    
    return _tracer, _meter


def parse_telemetry_event(event_data: str) -> Optional[Dict[str, Any]]:
    """
    Parse and validate telemetry event from EventHub.
    
    Args:
        event_data: Raw event data string from EventHub
        
    Returns:
        Parsed telemetry data or None if parsing fails
    """
    try:
        data = json.loads(event_data)
        
        # Validate required fields
        if not isinstance(data, dict):
            logging.warning(f"Invalid event data format: expected dict, got {type(data)}")
            return None
            
        # Extract and validate event type
        event_type = data.get('eventType')
        if event_type not in ['FinOpsApiCall', 'FinOpsApiError']:
            logging.warning(f"Unknown event type: {event_type}")
            return None
            
        return data
        
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON event data: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error parsing event data: {e}")
        return None


def create_span_attributes(telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create OpenTelemetry span attributes from parsed event data.
    
    Args:
        telemetry_data: Parsed telemetry data from EventHub
        
    Returns:
        Dictionary with span attributes for OpenTelemetry
    """
    event_type = telemetry_data.get('eventType', 'Unknown')
    
    # Core FinOps attributes for cost analysis
    attributes = {
        'event.type': event_type,
        'correlation.id': telemetry_data.get('correlationId', ''),
        'device.id': telemetry_data.get('deviceId', 'unknown'),
        'store.number': telemetry_data.get('storeNumber', 'unknown'),
        'api.name': telemetry_data.get('apiName', ''),
        'operation.name': telemetry_data.get('operationName', ''),
        'http.method': telemetry_data.get('method', ''),
        'http.url': telemetry_data.get('url', ''),
        'http.status_code': telemetry_data.get('statusCode', 0),
        'http.response_time_ms': telemetry_data.get('responseTime', 0),
        'ai.tokens.used': telemetry_data.get('tokensUsed', 0),
        'ai.tokens.prompt': telemetry_data.get('promptTokens', 0),
        'ai.tokens.completion': telemetry_data.get('completionTokens', 0),
        'ai.model.name': telemetry_data.get('modelName', ''),
        'api.version': telemetry_data.get('apiVersion', ''),
        'deployment.id': telemetry_data.get('deploymentId', ''),
        'subscription.id': telemetry_data.get('subscriptionId', ''),
        'product.id': telemetry_data.get('productId', ''),
        'resource.region': telemetry_data.get('resourceRegion', ''),
        'request.size_bytes': telemetry_data.get('requestSize', 0),
        'response.size_bytes': telemetry_data.get('responseSize', 0)
    }
    
    # Add error-specific attributes if present
    if event_type == 'FinOpsApiError':
        attributes.update({
            'error.message': telemetry_data.get('errorMessage', ''),
            'error.source': telemetry_data.get('errorSource', '')
        })
    
    # Remove empty values to reduce telemetry size and convert to proper types
    cleaned_attributes = {}
    for k, v in attributes.items():
        if v is not None and v != '' and v != 0:
            # Convert numeric strings to appropriate types
            if isinstance(v, str) and v.isdigit():
                cleaned_attributes[k] = int(v)
            elif isinstance(v, str) and v.replace('.', '', 1).isdigit():
                cleaned_attributes[k] = float(v)
            else:
                cleaned_attributes[k] = v
    
    return cleaned_attributes


@app.function_name(name="eventhub_to_appinsights")
@app.event_hub_message_trigger(
    arg_name="events",
    event_hub_name="%EventHubName%",
    connection="EventHubConnection",
    consumer_group="$Default",
    cardinality=func.Cardinality.MANY,
    data_type=func.DataType.STRING
)
def eventhub_to_appinsights(events: List[func.EventHubEvent]) -> None:
    """
    EventHub-triggered function that forwards telemetry to Application Insights.
    
    This function processes batches of telemetry events from EventHub (sent by APIM policy)
    and forwards them to Application Insights using OpenTelemetry for structured tracing.
    
    Args:
        events: List of EventHub events containing APIM telemetry data
    """
    event_count = len(events)
    logging.info(f'EventHub to AppInsights function triggered with {event_count} events')
    
    if not events:
        logging.info('No events to process')
        return
    
    try:
        # Initialize OpenTelemetry tracer and meter (singleton pattern)
        tracer, meter = get_or_create_opentelemetry()
        
        # Create metrics instruments
        processed_events_counter = meter.create_counter(
            name="eventhub.processed_events",
            description="Number of successfully processed events",
            unit="1"
        )
        
        error_events_counter = meter.create_counter(
            name="eventhub.processing_errors",
            description="Number of events that failed processing",
            unit="1"
        )
        
        processed_count = 0
        error_count = 0
        
        # Create a span for the entire batch processing
        with tracer.start_as_current_span("eventhub_batch_processing") as batch_span:
            batch_span.set_attribute("eventhub.batch_size", event_count)
            batch_span.set_attribute("function.name", "eventhub_to_appinsights")
            batch_span.set_attribute("function.version", "2.0.0")
            
            # Process each event in the batch
            for event_index, event in enumerate(events):
                try:
                    # Get event body as string
                    event_body = event.get_body().decode('utf-8')
                    
                    # Parse the telemetry event
                    parsed_data = parse_telemetry_event(event_body)
                    if not parsed_data:
                        error_count += 1
                        continue
                    
                    # Create span attributes
                    attributes = create_span_attributes(parsed_data)
                    event_type = parsed_data.get('eventType', 'Unknown')
                    
                    # Create a span for each event
                    span_name = f"process_event_{event_type.lower()}"
                    with tracer.start_as_current_span(span_name) as event_span:
                        # Set span attributes
                        for key, value in attributes.items():
                            event_span.set_attribute(key, value)
                        
                        # Set span status based on event type
                        if event_type == 'FinOpsApiError':
                            event_span.set_status(Status(StatusCode.ERROR, "API Error event"))
                        else:
                            event_span.set_status(Status(StatusCode.OK))
                        
                        # Add an event to the span
                        event_span.add_event(
                            name="apim_telemetry_processed",
                            attributes={
                                "message": f"APIM Telemetry - {event_type}",
                                "event.index": event_index,
                                "timestamp": parsed_data.get('timestamp', datetime.now(timezone.utc).isoformat())
                            }
                        )
                    
                    processed_count += 1
                    
                    # Log successful processing (only for first few events to avoid log spam)
                    if processed_count <= 5:
                        correlation_id = parsed_data.get('correlationId', 'N/A')
                        device_id = parsed_data.get('deviceId', 'unknown')
                        logging.info(f'Processed event - CorrelationId: {correlation_id}, DeviceId: {device_id}')
                    
                except Exception as e:
                    error_count += 1
                    logging.error(f'Error processing individual event: {str(e)}')
                    
                    # Create error span
                    with tracer.start_as_current_span("process_event_error") as error_span:
                        error_span.set_status(Status(StatusCode.ERROR, str(e)))
                        error_span.set_attribute("error.type", type(e).__name__)
                        error_span.set_attribute("error.message", str(e))
                        error_span.set_attribute("event.index", event_index)
                    
                    continue
            
            # Update batch span with final counts
            batch_span.set_attribute("eventhub.processed_count", processed_count)
            batch_span.set_attribute("eventhub.error_count", error_count)
            
            # Record metrics
            processed_events_counter.add(processed_count, {"function.name": "eventhub_to_appinsights"})
            if error_count > 0:
                error_events_counter.add(error_count, {"function.name": "eventhub_to_appinsights"})
        
        # Log processing summary
        logging.info(f'Batch processing completed - Processed: {processed_count}, Errors: {error_count}')
        
    except Exception as e:
        logging.error(f'Critical error in EventHub to AppInsights function: {str(e)}', exc_info=True)
        
        # Try to create error span if tracer is available
        try:
            if _tracer is not None:
                with _tracer.start_as_current_span("critical_error") as error_span:
                    error_span.set_status(Status(StatusCode.ERROR, str(e)))
                    error_span.set_attribute("error.type", type(e).__name__)
                    error_span.set_attribute("error.message", str(e))
                    error_span.record_exception(e)
        except Exception:
            pass  # Avoid nested exceptions
        
        raise  # Re-raise to trigger function retry if configured
