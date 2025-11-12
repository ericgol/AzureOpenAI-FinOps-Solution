"""
EventHub to Application Insights Telemetry Forwarder - Simplified Version

Uses Azure Functions' built-in logging integration with Application Insights.
Custom properties are logged as structured JSON which Application Insights
automatically parses into customDimensions.
"""

import logging
import json
from typing import List, Dict, Any, Optional

import azure.functions as func

# Initialize function app
app = func.FunctionApp()


def parse_telemetry_event(event_data: str) -> Optional[Dict[str, Any]]:
    """Parse and validate telemetry event from EventHub."""
    try:
        data = json.loads(event_data)
        
        if not isinstance(data, dict):
            logging.warning(f"Invalid event data format: expected dict, got {type(data)}")
            return None
            
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
    
    Logs structured data that Azure Functions automatically sends to Application Insights
    with custom dimensions.
    """
    event_count = len(events)
    logging.info(f'EventHub to AppInsights function triggered with {event_count} events')
    
    if not events:
        logging.info('No events to process')
        return
    
    processed_count = 0
    error_count = 0
    
    for event_index, event in enumerate(events):
        try:
            # Get event body
            event_body = event.get_body().decode('utf-8')
            
            # Parse telemetry event
            parsed_data = parse_telemetry_event(event_body)
            if not parsed_data:
                error_count += 1
                continue
            
            # Extract all fields for logging
            telemetry_record = {
                # Core FinOps fields
                "event_type": parsed_data.get('eventType', 'Unknown'),
                "device_id": parsed_data.get('deviceId', 'unknown'),
                "store_number": parsed_data.get('storeNumber', 'unknown'),
                "correlation_id": parsed_data.get('correlationId', ''),
                
                # Token usage
                "tokens_used": parsed_data.get('tokensUsed', 0),
                "prompt_tokens": parsed_data.get('promptTokens', 0),
                "completion_tokens": parsed_data.get('completionTokens', 0),
                
                # API details
                "api_name": parsed_data.get('apiName', ''),
                "operation_name": parsed_data.get('operationName', ''),
                "model": parsed_data.get('model', ''),
                "api_version": parsed_data.get('apiVersion', ''),
                "deployment_id": parsed_data.get('deploymentId', ''),
                
                # Request/Response details
                "method": parsed_data.get('method', ''),
                "url": parsed_data.get('url', ''),
                "status_code": parsed_data.get('statusCode', 0),
                "response_time_ms": parsed_data.get('responseTime', 0),
                
                # Azure context
                "subscription_id": parsed_data.get('subscriptionId', ''),
                "product_id": parsed_data.get('productId', ''),
                "resource_region": parsed_data.get('resourceRegion', ''),
                "resource_id": parsed_data.get('resourceId', ''),
                
                # Timestamp
                "event_timestamp": parsed_data.get('timestamp', '')
            }
            
            # Remove empty/zero values to reduce noise
            telemetry_record = {k: v for k, v in telemetry_record.items() if v not in (None, '', 0, 'unknown')}
            
            # Log as structured JSON - Azure Functions will parse this into customDimensions
            log_entry = {
                "message": "FinOpsApiCall",
                "customDimensions": telemetry_record
            }
            
            # Use INFO level for normal calls, ERROR for errors
            if telemetry_record.get('event_type') == 'FinOpsApiError':
                logging.error(json.dumps(log_entry))
            else:
                logging.info(json.dumps(log_entry))
            
            processed_count += 1
            
            # Log summary for first few events
            if processed_count <= 3:
                device_id = telemetry_record.get('device_id', 'unknown')
                store_number = telemetry_record.get('store_number', 'unknown')
                tokens = telemetry_record.get('tokens_used', 0)
                model = telemetry_record.get('model', '')
                logging.info(
                    f'Processed event {processed_count}: '
                    f'DeviceId={device_id}, StoreNumber={store_number}, '
                    f'Tokens={tokens}, Model={model}'
                )
            
        except Exception as e:
            error_count += 1
            logging.error(f'Error processing event {event_index}: {str(e)}', exc_info=True)
            continue
    
    # Log summary
    logging.info(
        json.dumps({
            "message": "FinOpsBatchCompleted",
            "customDimensions": {
                "batch_size": event_count,
                "processed_count": processed_count,
                "error_count": error_count
            }
        })
    )
