"""
Alternative EventHub to Application Insights forwarder using direct logging

This version uses Azure Functions' built-in Application Insights integration
instead of OpenTelemetry to ensure custom dimensions are properly logged.
"""

import logging
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

import azure.functions as func

# Initialize function app
app = func.FunctionApp()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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


@app.function_name(name="eventhub_to_appinsights_direct")
@app.event_hub_message_trigger(
    arg_name="events",
    event_hub_name="%EventHubName%",
    connection="EventHubConnection",
    consumer_group="$Default",
    cardinality=func.Cardinality.MANY,
    data_type=func.DataType.STRING
)
def eventhub_to_appinsights_direct(events: List[func.EventHubEvent]) -> None:
    """
    EventHub-triggered function that logs telemetry to Application Insights.
    
    Uses Azure Functions' built-in Application Insights integration with
    custom properties to ensure data appears in customDimensions.
    """
    event_count = len(events)
    logging.info(f'EventHub function triggered with {event_count} events')
    
    if not events:
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
            
            # Extract key fields
            event_type = parsed_data.get('eventType', 'Unknown')
            device_id = parsed_data.get('deviceId', 'unknown')
            store_number = parsed_data.get('storeNumber', 'unknown')
            correlation_id = parsed_data.get('correlationId', '')
            tokens_used = parsed_data.get('tokensUsed', 0)
            model = parsed_data.get('model', '')
            
            # Log with structured data - this should appear in customDimensions
            extra_props = {
                'event_type': event_type,
                'device_id': device_id,
                'store_number': store_number,
                'correlation_id': correlation_id,
                'tokens_used': tokens_used,
                'prompt_tokens': parsed_data.get('promptTokens', 0),
                'completion_tokens': parsed_data.get('completionTokens', 0),
                'model': model,
                'api_name': parsed_data.get('apiName', ''),
                'operation_name': parsed_data.get('operationName', ''),
                'status_code': parsed_data.get('statusCode', 0),
                'response_time': parsed_data.get('responseTime', 0),
                'api_version': parsed_data.get('apiVersion', ''),
                'deployment_id': parsed_data.get('deploymentId', ''),
                'subscription_id': parsed_data.get('subscriptionId', ''),
                'resource_region': parsed_data.get('resourceRegion', ''),
                'timestamp': parsed_data.get('timestamp', ''),
                'url': parsed_data.get('url', '')
            }
            
            # Log as JSON string which Application Insights will parse into customDimensions
            log_message = f"FinOpsApiCall: {json.dumps(extra_props)}"
            
            if event_type == 'FinOpsApiError':
                logging.error(log_message, extra={'custom_dimensions': extra_props})
            else:
                logging.info(log_message, extra={'custom_dimensions': extra_props})
            
            processed_count += 1
            
            # Log first few for debugging
            if processed_count <= 3:
                logging.info(
                    f'Processed event {processed_count}: '
                    f'DeviceId={device_id}, StoreNumber={store_number}, '
                    f'Tokens={tokens_used}, Model={model}'
                )
            
        except Exception as e:
            error_count += 1
            logging.error(f'Error processing event {event_index}: {str(e)}', exc_info=True)
            continue
    
    logging.info(f'Batch completed - Processed: {processed_count}, Errors: {error_count}')
