"""
Storage Manager for FinOps Solution

Manages Azure Storage operations for correlated data with Power BI optimized structure.
Implements Step 6 of the FinOps solution: Data Storage with partitioned schema.
"""

import logging
import json
import os
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional
import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .config import FinOpsConfig


class StorageManager:
    """
    Manages Azure Storage operations for FinOps solution data.
    
    Handles:
    - Partitioned data storage (YYYY/MM/DD structure)
    - Power BI optimized schema
    - Raw and processed data management
    - Data lifecycle and retention
    """
    
    def __init__(self, config: FinOpsConfig, credential: DefaultAzureCredential):
        """
        Initialize storage manager.
        
        Args:
            config: FinOps configuration
            credential: Azure credential for authentication
        """
        self.config = config
        self.credential = credential
        self.logger = logging.getLogger(__name__)
        
        # Initialize Blob Service Client
        try:
            if config.storage_account_key:
                # Use account key if provided
                connection_string = config.get_storage_connection_string()
                self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            else:
                # Use managed identity
                account_url = f"https://{config.storage_account_name}.blob.core.windows.net"
                self.blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
            
            self.logger.info("Initialized Azure Storage client")
        except Exception as e:
            self.logger.error(f"Failed to initialize Storage client: {e}")
            raise
        
        # Ensure containers exist
        self._ensure_containers_exist()
    
    def _ensure_containers_exist(self):
        """Ensure all required containers exist."""
        containers = [
            self.config.finops_data_container,
            self.config.raw_telemetry_container,
            self.config.cost_data_container
        ]
        
        for container_name in containers:
            try:
                container_client = self.blob_service_client.get_container_client(container_name)
                if not container_client.exists():
                    container_client.create_container()
                    self.logger.info(f"Created container: {container_name}")
            except ResourceExistsError:
                self.logger.debug(f"Container already exists: {container_name}")
            except Exception as e:
                self.logger.error(f"Error ensuring container {container_name}: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception)
    )
    def store_correlated_data(self, correlated_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Store correlated data with Power BI optimized partitioning.
        
        Args:
            correlated_data: List of correlated device/store records
            
        Returns:
            Dictionary with storage paths and metadata
        """
        if not correlated_data:
            self.logger.warning("No correlated data to store")
            return {}
        
        self.logger.info(f"Storing {len(correlated_data)} correlated records")
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(correlated_data)
        
        # Add partitioning columns
        df['ProcessingDate'] = pd.to_datetime(df['ProcessingDate'])
        df['Year'] = df['ProcessingDate'].dt.year
        df['Month'] = df['ProcessingDate'].dt.month.apply(lambda x: f"{x:02d}")
        df['Day'] = df['ProcessingDate'].dt.day.apply(lambda x: f"{x:02d}")
        
        # Group by date for partitioned storage
        storage_paths = {}
        
        for (year, month, day), group in df.groupby(['Year', 'Month', 'Day']):
            # Create partition path
            partition_path = f"{year}/{month}/{day}"
            
            # Generate timestamp for unique file naming
            timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
            
            # Store in multiple formats for different use cases
            paths = self._store_partition_data(group, partition_path, timestamp)
            storage_paths[partition_path] = paths
            
            self.logger.info(f"Stored {len(group)} records for partition {partition_path}")
        
        # Store aggregated summary data
        summary_path = self._store_summary_data(df)
        storage_paths['summary'] = summary_path
        
        return storage_paths
    
    def _store_partition_data(self, df: pd.DataFrame, partition_path: str, timestamp: str) -> Dict[str, str]:
        """
        Store partitioned data in multiple formats.
        
        Args:
            df: DataFrame with partition data
            partition_path: Partition path (YYYY/MM/DD)
            timestamp: Timestamp for file naming
            
        Returns:
            Dictionary with file paths
        """
        paths = {}
        
        # Prepare data for storage (clean up internal columns)
        storage_df = df.drop(columns=['Year', 'Month', 'Day'], errors='ignore')
        
        # Store as JSON (for debugging and flexibility)
        json_blob_name = f"{partition_path}/correlated-data-{timestamp}.json"
        json_data = storage_df.to_dict('records')
        paths['json'] = self._upload_json_data(self.config.finops_data_container, json_blob_name, json_data)
        
        # Store as Parquet (for Power BI performance)
        parquet_blob_name = f"{partition_path}/correlated-data-{timestamp}.parquet"
        paths['parquet'] = self._upload_parquet_data(self.config.finops_data_container, parquet_blob_name, storage_df)
        
        # Store as CSV (for easy inspection)
        csv_blob_name = f"{partition_path}/correlated-data-{timestamp}.csv"
        paths['csv'] = self._upload_csv_data(self.config.finops_data_container, csv_blob_name, storage_df)
        
        return paths
    
    def _store_summary_data(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Store summary/aggregated data for quick analytics.
        
        Args:
            df: Full DataFrame
            
        Returns:
            Dictionary with summary file paths
        """
        now_utc = datetime.now(timezone.utc)
        processing_date = now_utc.strftime("%Y-%m-%d")
        timestamp = now_utc.strftime("%H%M%S")
        
        # Device summary
        device_summary = df.groupby(['DeviceId', 'StoreNumber']).agg({
            'AllocatedCost': ['sum', 'count'],
            'TokensUsed': 'sum',
            'ApiCalls': 'sum',
            'AvgResponseTime': 'mean',
            'DeviceUtilizationScore': 'mean'
        }).reset_index()
        
        device_summary.columns = ['DeviceId', 'StoreNumber', 'TotalCost', 'RecordCount', 
                                 'TotalTokens', 'TotalApiCalls', 'AvgResponseTime', 'AvgUtilization']
        device_summary['ProcessingDate'] = processing_date
        
        # Store device summary
        device_summary_path = f"summaries/device-summary-{processing_date}-{timestamp}.parquet"
        device_path = self._upload_parquet_data(self.config.finops_data_container, device_summary_path, device_summary)
        
        # Store summary
        store_summary = df.groupby('StoreNumber').agg({
            'AllocatedCost': ['sum', 'count'],
            'TokensUsed': 'sum',
            'ApiCalls': 'sum',
            'DeviceId': 'nunique'
        }).reset_index()
        
        store_summary.columns = ['StoreNumber', 'TotalCost', 'RecordCount', 
                               'TotalTokens', 'TotalApiCalls', 'UniqueDevices']
        store_summary['ProcessingDate'] = processing_date
        
        # Store store summary
        store_summary_path = f"summaries/store-summary-{processing_date}-{timestamp}.parquet"
        store_path = self._upload_parquet_data(self.config.finops_data_container, store_summary_path, store_summary)
        
        return {
            'device_summary': device_path,
            'store_summary': store_path
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry_if_exception_type(Exception)
    )
    def store_raw_data(self, telemetry_data: List[Dict[str, Any]], cost_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Store raw telemetry and cost data for backup and debugging.
        
        Args:
            telemetry_data: Raw telemetry records
            cost_data: Raw cost records
            
        Returns:
            Dictionary with storage paths
        """
        self.logger.info(f"Storing raw data: {len(telemetry_data)} telemetry, {len(cost_data)} cost records")
        
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        paths = {}
        
        # Store raw telemetry data
        if telemetry_data:
            telemetry_blob_name = f"raw-data/{timestamp}/telemetry-data.json"
            paths['telemetry'] = self._upload_json_data(self.config.raw_telemetry_container, telemetry_blob_name, telemetry_data)
        
        # Store raw cost data
        if cost_data:
            cost_blob_name = f"raw-data/{timestamp}/cost-data.json"
            paths['cost'] = self._upload_json_data(self.config.cost_data_container, cost_blob_name, cost_data)
        
        return paths
    
    def _upload_json_data(self, container_name: str, blob_name: str, data: Any) -> str:
        """Upload JSON data to blob storage."""
        try:
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            json_content = json.dumps(data, indent=2, default=str)
            blob_client.upload_blob(json_content, overwrite=True)
            
            blob_url = blob_client.url
            self.logger.debug(f"Uploaded JSON data to {blob_url}")
            return blob_url
        except Exception as e:
            self.logger.error(f"Error uploading JSON data to {blob_name}: {e}")
            raise
    
    def _upload_parquet_data(self, container_name: str, blob_name: str, df: pd.DataFrame) -> str:
        """Upload Parquet data to blob storage."""
        try:
            import io
            
            # Convert to Parquet in memory
            parquet_buffer = io.BytesIO()
            df.to_parquet(parquet_buffer, engine='pyarrow', index=False)
            parquet_buffer.seek(0)
            
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            blob_client.upload_blob(parquet_buffer.read(), overwrite=True)
            
            blob_url = blob_client.url
            self.logger.debug(f"Uploaded Parquet data to {blob_url}")
            return blob_url
        except Exception as e:
            self.logger.error(f"Error uploading Parquet data to {blob_name}: {e}")
            raise
    
    def _upload_csv_data(self, container_name: str, blob_name: str, df: pd.DataFrame) -> str:
        """Upload CSV data to blob storage."""
        try:
            import io
            
            # Convert to CSV in memory
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()
            
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            blob_client.upload_blob(csv_content, overwrite=True)
            
            blob_url = blob_client.url
            self.logger.debug(f"Uploaded CSV data to {blob_url}")
            return blob_url
        except Exception as e:
            self.logger.error(f"Error uploading CSV data to {blob_name}: {e}")
            raise
    
    def get_partition_data(self, partition_path: str, file_format: str = 'parquet') -> pd.DataFrame:
        """
        Retrieve data for a specific partition.
        
        Args:
            partition_path: Partition path (YYYY/MM/DD)
            file_format: File format to retrieve (parquet, json, csv)
            
        Returns:
            DataFrame with partition data
        """
        try:
            container_client = self.blob_service_client.get_container_client(self.config.finops_data_container)
            
            # List blobs in partition
            blobs = container_client.list_blobs(name_starts_with=partition_path)
            
            # Find the latest file of the requested format
            matching_blobs = [blob for blob in blobs if blob.name.endswith(f'.{file_format}')]
            
            if not matching_blobs:
                self.logger.warning(f"No {file_format} files found for partition {partition_path}")
                return pd.DataFrame()
            
            # Get the latest file
            latest_blob = max(matching_blobs, key=lambda b: b.last_modified)
            
            # Download and read the data
            blob_client = self.blob_service_client.get_blob_client(
                container=self.config.finops_data_container, 
                blob=latest_blob.name
            )
            
            if file_format == 'parquet':
                import io
                blob_data = blob_client.download_blob().readall()
                return pd.read_parquet(io.BytesIO(blob_data))
            elif file_format == 'json':
                blob_content = blob_client.download_blob().content_as_text()
                data = json.loads(blob_content)
                return pd.DataFrame(data)
            elif file_format == 'csv':
                import io
                blob_content = blob_client.download_blob().content_as_text()
                return pd.read_csv(io.StringIO(blob_content))
            
        except Exception as e:
            self.logger.error(f"Error retrieving partition data {partition_path}: {e}")
            return pd.DataFrame()
    
    def list_partitions(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[str]:
        """
        List available data partitions.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of partition paths
        """
        try:
            container_client = self.blob_service_client.get_container_client(self.config.finops_data_container)
            
            # Get all blobs and extract unique partition paths
            blobs = container_client.list_blobs()
            partitions = set()
            
            for blob in blobs:
                # Extract partition path (YYYY/MM/DD) from blob name
                path_parts = blob.name.split('/')
                if len(path_parts) >= 3:
                    partition_path = '/'.join(path_parts[:3])
                    
                    # Apply date filters if provided
                    if start_date or end_date:
                        try:
                            partition_date = datetime.strptime(partition_path, '%Y/%m/%d').date()
                            if start_date and partition_date < start_date:
                                continue
                            if end_date and partition_date > end_date:
                                continue
                        except ValueError:
                            continue
                    
                    partitions.add(partition_path)
            
            return sorted(list(partitions))
            
        except Exception as e:
            self.logger.error(f"Error listing partitions: {e}")
            return []
    
    def get_storage_metrics(self) -> Dict[str, Any]:
        """
        Get storage utilization metrics.
        
        Returns:
            Dictionary with storage metrics
        """
        metrics = {
            'containers': {},
            'total_size_bytes': 0,
            'total_blob_count': 0
        }
        
        containers = [
            self.config.finops_data_container,
            self.config.raw_telemetry_container,
            self.config.cost_data_container
        ]
        
        for container_name in containers:
            try:
                container_client = self.blob_service_client.get_container_client(container_name)
                
                if container_client.exists():
                    blobs = list(container_client.list_blobs())
                    container_size = sum(blob.size for blob in blobs if blob.size)
                    blob_count = len(blobs)
                    
                    metrics['containers'][container_name] = {
                        'size_bytes': container_size,
                        'blob_count': blob_count,
                        'size_mb': round(container_size / (1024 * 1024), 2)
                    }
                    
                    metrics['total_size_bytes'] += container_size
                    metrics['total_blob_count'] += blob_count
                
            except Exception as e:
                self.logger.warning(f"Error getting metrics for container {container_name}: {e}")
                metrics['containers'][container_name] = {'error': str(e)}
        
        metrics['total_size_mb'] = round(metrics['total_size_bytes'] / (1024 * 1024), 2)
        
        return metrics
    
    def cleanup_old_data(self, retention_days: int = 90) -> Dict[str, int]:
        """
        Clean up old data based on retention policy.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Dictionary with cleanup statistics
        """
        self.logger.info(f"Starting data cleanup with {retention_days} day retention")
        
        cutoff_date = datetime.now(timezone.utc) - pd.Timedelta(days=retention_days)
        cleanup_stats = {
            'deleted_blobs': 0,
            'freed_bytes': 0
        }
        
        containers = [
            self.config.finops_data_container,
            self.config.raw_telemetry_container,
            self.config.cost_data_container
        ]
        
        for container_name in containers:
            try:
                container_client = self.blob_service_client.get_container_client(container_name)
                
                if container_client.exists():
                    blobs = container_client.list_blobs()
                    
                    for blob in blobs:
                        if blob.last_modified < cutoff_date:
                            try:
                                blob_client = container_client.get_blob_client(blob.name)
                                blob_size = blob.size or 0
                                blob_client.delete_blob()
                                
                                cleanup_stats['deleted_blobs'] += 1
                                cleanup_stats['freed_bytes'] += blob_size
                                
                                self.logger.debug(f"Deleted old blob: {blob.name}")
                            except Exception as e:
                                self.logger.warning(f"Error deleting blob {blob.name}: {e}")
                
            except Exception as e:
                self.logger.error(f"Error during cleanup in container {container_name}: {e}")
        
        cleanup_stats['freed_mb'] = round(cleanup_stats['freed_bytes'] / (1024 * 1024), 2)
        
        self.logger.info(f"Cleanup completed: {cleanup_stats['deleted_blobs']} blobs deleted, {cleanup_stats['freed_mb']} MB freed")
        return cleanup_stats