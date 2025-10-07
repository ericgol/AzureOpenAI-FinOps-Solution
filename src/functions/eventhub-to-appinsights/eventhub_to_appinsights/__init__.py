"""
EventHub to Application Insights Telemetry Forwarder

This Azure Function receives telemetry events from EventHub (originated from APIM policy)
and forwards them to Application Insights for analysis and correlation with cost data.

The function processes batches of events from EventHub and sends them to Application Insights
as structured trace telemetry with all the custom properties needed for FinOps analysis.

Author: FinOps Team
"""

import logging
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

import azure.functions as func
from applicationinsights import TelemetryClient
from applicationinsights.channel import TelemetryChannel
from applicationinsights.extensibility import TelemetryProcessor

# Initialize Application Insights client
def get_telemetry_client() -> TelemetryClient:
    """
    Initialize and return Application Insights telemetry client.
    
    Returns:
        TelemetryClient: Configured Application Insights client
    """
    connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
    if not connection_string:
        raise ValueError("APPLICATIONINSIGHTS_CONNECTION_STRING environment variable is required")
    
    # Create telemetry client with connection string
    client = TelemetryClient(connection_string)
    
    # Configure telemetry channel for better performance
    channel = TelemetryChannel()
    channel.context.application.ver = '1.0.0'
    channel.context.application.id = 'eventhub-to-appinsights'
    client.channel = channel
    
    return client


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


def create_trace_telemetry(telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create Application Insights trace telemetry from parsed event data.
    
    Args:
        telemetry_data: Parsed telemetry data from EventHub
        
    Returns:
        Dictionary with trace properties and custom dimensions
    """
    event_type = telemetry_data.get('eventType', 'Unknown')
    
    # Base trace properties
    trace_props = {
        'message': f'APIM Telemetry - {event_type}',
        'severity': 'Information' if event_type == 'FinOpsApiCall' else 'Error',
        'timestamp': telemetry_data.get('timestamp', datetime.utcnow().isoformat())
    }
    
    # Custom dimensions for FinOps analysis
    custom_dimensions = {
        'eventType': event_type,
        'correlationId': telemetry_data.get('correlationId', ''),
        'deviceId': telemetry_data.get('deviceId', 'unknown'),
        'storeNumber': telemetry_data.get('storeNumber', 'unknown'),
        'apiName': telemetry_data.get('apiName', ''),
        'operationName': telemetry_data.get('operationName', ''),
        'method': telemetry_data.get('method', ''),
        'url': telemetry_data.get('url', ''),
        'statusCode': str(telemetry_data.get('statusCode', '')),
        'responseTime': str(telemetry_data.get('responseTime', '')),
        'tokensUsed': str(telemetry_data.get('tokensUsed', 0)),
        'promptTokens': str(telemetry_data.get('promptTokens', 0)),
        'completionTokens': str(telemetry_data.get('completionTokens', 0)),
        'modelName': telemetry_data.get('modelName', ''),
        'apiVersion': telemetry_data.get('apiVersion', ''),
        'deploymentId': telemetry_data.get('deploymentId', ''),
        'subscriptionId': telemetry_data.get('subscriptionId', ''),
        'productId': telemetry_data.get('productId', ''),
        'resourceRegion': telemetry_data.get('resourceRegion', ''),
        'requestSize': str(telemetry_data.get('requestSize', 0)),
        'responseSize': str(telemetry_data.get('responseSize', 0))
    }
    
    # Add error-specific properties if present
    if event_type == 'FinOpsApiError':
        custom_dimensions.update({
            'errorMessage': telemetry_data.get('errorMessage', ''),
            'errorSource': telemetry_data.get('errorSource', '')
        })
    
    # Remove empty values to reduce telemetry size
    custom_dimensions = {k: v for k, v in custom_dimensions.items() if v}
    
    return {
        'trace_props': trace_props,
        'custom_dimensions': custom_dimensions
    }


def main(events: List[str]) -> None:
    """
    Main entry point for the EventHub trigger function.
    
    Args:
        events: List of event data strings from EventHub
    """
    logging.info(f'EventHub to AppInsights function triggered with {len(events)} events')
    
    if not events:
        logging.info('No events to process')
        return
    
    try:
        # Initialize Application Insights client
        telemetry_client = get_telemetry_client()
        
        processed_count = 0
        error_count = 0
        
        # Process each event in the batch
        for event_data in events:
            try:
                # Parse the telemetry event
                parsed_data = parse_telemetry_event(event_data)
                if not parsed_data:
                    error_count += 1
                    continue
                
                # Create trace telemetry
                telemetry = create_trace_telemetry(parsed_data)
                
                # Send trace to Application Insights
                telemetry_client.track_trace(
                    message=telemetry['trace_props']['message'],
                    severity=telemetry['trace_props']['severity'],
                    properties=telemetry['custom_dimensions']
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
                continue
        
        # Flush telemetry to ensure delivery
        telemetry_client.flush()
        
        # Log processing summary
        logging.info(f'Batch processing completed - Processed: {processed_count}, Errors: {error_count}')
        
        # Track custom metric for monitoring
        telemetry_client.track_metric(
            name='EventHub.ProcessedEvents',
            value=processed_count,
            properties={'FunctionName': 'eventhub_to_appinsights'}
        )
        
        if error_count > 0:
            telemetry_client.track_metric(
                name='EventHub.ProcessingErrors',
                value=error_count,
                properties={'FunctionName': 'eventhub_to_appinsights'}
            )
        
    except Exception as e:
        logging.error(f'Critical error in EventHub to AppInsights function: {str(e)}', exc_info=True)
        
        # Try to send error telemetry if client is available
        try:
            if 'telemetry_client' in locals():
                telemetry_client.track_exception()
                telemetry_client.flush()
        except:
            pass  # Avoid nested exceptions
        
        raise  # Re-raise to trigger function retry if configured