#!/usr/bin/env python3
"""
Test script to query Azure Cost Management API for OpenAI costs.

This mimics the cost collection logic used in the FinOps data collector function.
"""

from datetime import datetime, timedelta, timezone
from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryDefinition,
    QueryDataset,
    QueryAggregation,
    QueryGrouping,
    QueryTimePeriod
)
import json

# Configuration
SUBSCRIPTION_ID = "f97772c2-6385-4f23-8cda-22295a1ad20b"
SCOPE = f"/subscriptions/{SUBSCRIPTION_ID}"
LOOKBACK_DAYS = 60  # Query last 60 days

def create_cost_query(start_time: datetime, end_time: datetime) -> QueryDefinition:
    """Create cost management query definition."""
    
    # Define aggregations
    aggregations = {
        "totalCost": QueryAggregation(name="PreTaxCost", function="Sum"),
        "usageQuantity": QueryAggregation(name="UsageQuantity", function="Sum")
    }
    
    # Define groupings for detailed breakdown
    groupings = [
        QueryGrouping(type="Dimension", name="ResourceId"),
        QueryGrouping(type="Dimension", name="ResourceType"),
        QueryGrouping(type="Dimension", name="ServiceName"),
        QueryGrouping(type="Dimension", name="Meter")
    ]
    
    # Create dataset with filter for OpenAI resources
    dataset = QueryDataset(
        granularity="Daily",
        aggregation=aggregations,
        grouping=groupings,
        filter={
            "dimensions": {
                "name": "ServiceName",
                "operator": "In",
                "values": ["Azure OpenAI", "Cognitive Services"]
            }
        }
    )
    
    # Create time period
    time_period = QueryTimePeriod(
        from_property=start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        to=end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    
    return QueryDefinition(
        type="Usage",
        timeframe="Custom",
        time_period=time_period,
        dataset=dataset
    )

def main():
    print("=" * 70)
    print("Azure Cost Management API Test Query")
    print("=" * 70)
    
    # Initialize credential
    print("\n1. Initializing Azure credential...")
    credential = DefaultAzureCredential()
    print("   ✓ Credential initialized")
    
    # Initialize Cost Management client
    print("\n2. Initializing Cost Management client...")
    cost_client = CostManagementClient(credential)
    print("   ✓ Client initialized")
    
    # Calculate time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=LOOKBACK_DAYS)
    
    print(f"\n3. Query parameters:")
    print(f"   Scope: {SCOPE}")
    print(f"   Start: {start_time.isoformat()}")
    print(f"   End: {end_time.isoformat()}")
    print(f"   Lookback: {LOOKBACK_DAYS} days")
    print(f"   Note: Cost data typically has 4-8 hour delay")
    
    # Create query
    print("\n4. Creating query definition...")
    query_def = create_cost_query(start_time, end_time)
    print("   ✓ Query definition created")
    
    # Execute query
    print("\n5. Executing Cost Management API query...")
    print("   (This may take 10-30 seconds...)")
    
    try:
        result = cost_client.query.usage(
            scope=SCOPE,
            parameters=query_def
        )
        print("   ✓ Query executed successfully")
        
        # Process results
        print("\n6. Processing results...")
        
        if not result or not hasattr(result, 'rows') or not result.rows:
            print("   ⚠️  No cost data returned (this is normal if no OpenAI usage in time period)")
            return
        
        # Get column names
        columns = [col.name for col in result.columns] if result.columns else []
        print(f"   Columns: {', '.join(columns)}")
        
        # Convert to list of dictionaries
        cost_records = []
        for row in result.rows:
            record = {}
            for i, value in enumerate(row):
                if i < len(columns):
                    record[columns[i]] = value
            cost_records.append(record)
        
        print(f"   ✓ Found {len(cost_records)} cost records")
        
        # Display summary
        print("\n7. Cost Summary:")
        print("   " + "-" * 66)
        
        if cost_records:
            total_cost = sum(float(r.get('totalCost', 0)) for r in cost_records)
            total_usage = sum(float(r.get('usageQuantity', 0)) for r in cost_records)
            
            print(f"   Total Cost: ${total_cost:.4f}")
            print(f"   Total Usage Quantity: {total_usage:.2f}")
            print(f"   Number of Resources: {len(set(r.get('ResourceId', '') for r in cost_records))}")
            
            # Show sample records
            print("\n8. Sample Records (first 3):")
            print("   " + "-" * 66)
            for i, record in enumerate(cost_records[:3], 1):
                print(f"\n   Record {i}:")
                print(f"      Service: {record.get('ServiceName', 'N/A')}")
                print(f"      Meter: {record.get('Meter', 'N/A')}")
                print(f"      Cost: ${float(record.get('totalCost', 0)):.4f}")
                print(f"      Usage: {float(record.get('usageQuantity', 0)):.2f}")
                resource_id = record.get('ResourceId', '')
                if resource_id:
                    resource_name = resource_id.split('/')[-1] if '/' in resource_id else resource_id
                    print(f"      Resource: {resource_name}")
            
            # Export to JSON
            output_file = "cost-query-results.json"
            with open(output_file, 'w') as f:
                json.dump(cost_records, f, indent=2, default=str)
            print(f"\n9. Full results exported to: {output_file}")
        
        print("\n" + "=" * 70)
        print("✓ Test completed successfully")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n   ✗ Error: {e}")
        
        if "429" in str(e) or "Too many requests" in str(e):
            print("\n   ⚠️  Rate Limit Hit:")
            print("   The Cost Management API has strict throttling limits.")
            print("   This is expected if the FinOps function ran recently.")
            print("   Wait a few minutes and try again.")
        elif "RBACAccessDenied" in str(e) or "authorization" in str(e).lower():
            print("\n   ⚠️  Permission Error:")
            print("   Your Azure account needs 'Cost Management Reader' role.")
            print("   Run this command to assign it:")
            print(f"   az role assignment create \\")
            print(f"     --assignee $(az ad signed-in-user show --query id -o tsv) \\")
            print(f"     --role \"Cost Management Reader\" \\")
            print(f"     --scope \"{SCOPE}\"")
        
        raise

if __name__ == "__main__":
    main()
