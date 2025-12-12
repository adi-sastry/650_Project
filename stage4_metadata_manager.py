"""
Stage 4: Storage & Metadata Management
Comprehensive metadata tracking and storage management for wildlife detection system
"""

import boto3
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MetadataManager:
    """
    Manages metadata storage and retrieval for wildlife detection system.
    Handles two DynamoDB tables:
    1. image_event - Tracks image ingestion events
    2. detection_results - Stores ML detection results with rich metadata
    """
    
    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize the metadata manager with AWS clients.
        
        Args:
            region: AWS region for DynamoDB tables
        """
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        self.region = region
        
        # Table references (will be initialized when tables are created)
        self.image_event_table = None
        self.detection_results_table = None
        
        logger.info(f"MetadataManager initialized for region: {region}")
    
    def create_enhanced_image_event_table(self, table_name: str = 'image_event') -> None:
        """
        Creates or updates the image_event table with additional indexes for querying.
        
        Schema:
        - Primary Key: event_id (String)
        - GSI1: bucket_name-time_stamp-index (for time-based queries)
        - GSI2: processed-time_stamp-index (for finding unprocessed images)
        - GSI3: camera_id-time_stamp-index (for camera-specific queries)
        
        Args:
            table_name: Name of the DynamoDB table
        """
        try:
            # Check if table exists
            existing_tables = self.dynamodb.meta.client.list_tables()['TableNames']
            
            if table_name in existing_tables:
                logger.info(f"Table {table_name} already exists. Using existing table.")
                self.image_event_table = self.dynamodb.Table(table_name)
                return
            
            # Create table with enhanced schema
            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'event_id', 'KeyType': 'HASH'}  # Partition key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'event_id', 'AttributeType': 'S'},
                    {'AttributeName': 'bucket_name', 'AttributeType': 'S'},
                    {'AttributeName': 'time_stamp', 'AttributeType': 'N'},
                    {'AttributeName': 'processed', 'AttributeType': 'S'},  # Changed to String for GSI
                    {'AttributeName': 'camera_id', 'AttributeType': 'S'},
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'bucket_name-time_stamp-index',
                        'KeySchema': [
                            {'AttributeName': 'bucket_name', 'KeyType': 'HASH'},
                            {'AttributeName': 'time_stamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'processed-time_stamp-index',
                        'KeySchema': [
                            {'AttributeName': 'processed', 'KeyType': 'HASH'},
                            {'AttributeName': 'time_stamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'camera_id-time_stamp-index',
                        'KeySchema': [
                            {'AttributeName': 'camera_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'time_stamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ],
                BillingMode='PROVISIONED',
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            
            # Wait for table to be created
            table.wait_until_exists()
            self.image_event_table = table
            logger.info(f"Table {table_name} created successfully with GSIs")
            
        except Exception as e:
            logger.error(f"Error creating table {table_name}: {e}")
            raise
    
    def create_detection_results_table(self, table_name: str = 'detection_results') -> None:
        """
        Creates the detection_results table for storing ML detection outputs.
        
        Schema:
        - Primary Key: detection_id (String)
        - Sort Key: timestamp (String)
        - GSI1: image_name-timestamp-index (for image-based queries)
        - GSI2: species-timestamp-index (for species-based queries)
        - GSI3: camera_id-timestamp-index (for camera-based queries)
        - GSI4: confidence_level-timestamp-index (for confidence filtering)
        - LSI1: geo_hash-timestamp-index (for geographic queries)
        
        Args:
            table_name: Name of the DynamoDB table
        """
        try:
            # Check if table exists
            existing_tables = self.dynamodb.meta.client.list_tables()['TableNames']
            
            if table_name in existing_tables:
                logger.info(f"Table {table_name} already exists. Using existing table.")
                self.detection_results_table = self.dynamodb.Table(table_name)
                return
            
            # Create table
            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'detection_id', 'KeyType': 'HASH'},  # Partition key
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}     # Sort key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'detection_id', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'S'},
                    {'AttributeName': 'image_name', 'AttributeType': 'S'},
                    {'AttributeName': 'species', 'AttributeType': 'S'},
                    {'AttributeName': 'camera_id', 'AttributeType': 'S'},
                    {'AttributeName': 'confidence_level', 'AttributeType': 'S'},
                    {'AttributeName': 'geo_hash', 'AttributeType': 'S'},
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'image_name-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'image_name', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'species-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'species', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'camera_id-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'camera_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'confidence_level-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'confidence_level', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'geo_hash-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'geo_hash', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ],
                BillingMode='PROVISIONED',
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            
            # Wait for table to be created
            table.wait_until_exists()
            self.detection_results_table = table
            logger.info(f"Table {table_name} created successfully with GSIs")
            
        except Exception as e:
            logger.error(f"Error creating table {table_name}: {e}")
            raise
    
    def store_detection_result(self, detection_data: Dict[str, Any]) -> bool:
        """
        Store detection results with comprehensive metadata.
        
        Args:
            detection_data: Dictionary containing detection information
                Required fields:
                - image_name: Name of the image file
                - s3_uri: S3 URI of the image
                - detections: List of detection objects from YOLOv8
                - camera_id: ID of the camera trap
                - latitude: Geographic latitude
                - longitude: Geographic longitude
                
                Optional fields:
                - temperature: Temperature at capture time
                - elevation: Elevation in meters
                - capture_time: Original capture timestamp
                - image_resolution: Image dimensions
                - file_size_bytes: File size
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.detection_results_table:
                self.detection_results_table = self.dynamodb.Table('detection_results')
            
            # Generate unique detection ID
            import uuid
            detection_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat() + 'Z'
            
            # Calculate geo_hash for geographic queries (simplified geohash)
            geo_hash = self._calculate_geo_hash(
                detection_data.get('latitude', 0),
                detection_data.get('longitude', 0)
            )
            
            # Determine confidence level category
            avg_confidence = 0
            species_list = []
            if detection_data.get('detections'):
                confidences = [d.get('score', 0) for d in detection_data['detections']]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                species_list = list(set([d.get('class', 'unknown') for d in detection_data['detections']]))
            
            confidence_level = self._categorize_confidence(avg_confidence)
            
            # Prepare item for DynamoDB
            item = {
                'detection_id': detection_id,
                'timestamp': timestamp,
                'image_name': detection_data['image_name'],
                's3_uri': detection_data['s3_uri'],
                'camera_id': detection_data.get('camera_id', 'unknown'),
                'species': species_list[0] if species_list else 'none',  # Primary species for indexing
                'all_species': species_list,  # All detected species
                'confidence_level': confidence_level,
                'average_confidence': Decimal(str(avg_confidence)),
                'detection_count': len(detection_data.get('detections', [])),
                'detections': json.dumps(detection_data.get('detections', [])),
                'geo_hash': geo_hash,
                'latitude': Decimal(str(detection_data.get('latitude', 0))),
                'longitude': Decimal(str(detection_data.get('longitude', 0))),
                'temperature': Decimal(str(detection_data.get('temperature', 0))) if detection_data.get('temperature') else None,
                'elevation': Decimal(str(detection_data.get('elevation', 0))) if detection_data.get('elevation') else None,
                'capture_time': detection_data.get('capture_time', timestamp),
                'image_resolution': detection_data.get('image_resolution', ''),
                'file_size_bytes': detection_data.get('file_size_bytes', 0),
                'processed_timestamp': timestamp,
                'metadata': json.dumps(detection_data.get('additional_metadata', {}))
            }
            
            # Remove None values
            item = {k: v for k, v in item.items() if v is not None}
            
            # Store in DynamoDB
            self.detection_results_table.put_item(Item=item)
            logger.info(f"Stored detection result: {detection_id} for image: {detection_data['image_name']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing detection result: {e}")
            return False
    
    def get_detections_by_species(self, species: str, start_date: Optional[str] = None, 
                                  end_date: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Query all detections for a specific species.
        
        Args:
            species: Species name to query
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            limit: Maximum number of results
        
        Returns:
            List of detection records
        """
        try:
            if not self.detection_results_table:
                self.detection_results_table = self.dynamodb.Table('detection_results')
            
            # Build query parameters
            query_params = {
                'IndexName': 'species-timestamp-index',
                'KeyConditionExpression': Key('species').eq(species),
                'Limit': limit,
                'ScanIndexForward': False  # Most recent first
            }
            
            # Add date range if provided
            if start_date and end_date:
                query_params['KeyConditionExpression'] &= Key('timestamp').between(start_date, end_date)
            elif start_date:
                query_params['KeyConditionExpression'] &= Key('timestamp').gte(start_date)
            elif end_date:
                query_params['KeyConditionExpression'] &= Key('timestamp').lte(end_date)
            
            response = self.detection_results_table.query(**query_params)
            results = response.get('Items', [])
            
            logger.info(f"Found {len(results)} detections for species: {species}")
            return results
            
        except Exception as e:
            logger.error(f"Error querying detections by species: {e}")
            return []
    
    def get_detections_by_date_range(self, start_date: str, end_date: str, limit: int = 100) -> List[Dict]:
        """
        Get all detections within a date range.
        
        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            limit: Maximum number of results
        
        Returns:
            List of detection records
        """
        try:
            if not self.detection_results_table:
                self.detection_results_table = self.dynamodb.Table('detection_results')
            
            # Use scan with filter for date range (less efficient but comprehensive)
            response = self.detection_results_table.scan(
                FilterExpression=Attr('timestamp').between(start_date, end_date),
                Limit=limit
            )
            
            results = response.get('Items', [])
            
            # Handle pagination if needed
            while 'LastEvaluatedKey' in response and len(results) < limit:
                response = self.detection_results_table.scan(
                    FilterExpression=Attr('timestamp').between(start_date, end_date),
                    ExclusiveStartKey=response['LastEvaluatedKey'],
                    Limit=limit - len(results)
                )
                results.extend(response.get('Items', []))
            
            logger.info(f"Found {len(results)} detections between {start_date} and {end_date}")
            return results
            
        except Exception as e:
            logger.error(f"Error querying detections by date range: {e}")
            return []
    
    def get_unprocessed_images(self, limit: int = 100) -> List[Dict]:
        """
        Get all unprocessed images from image_event table.
        
        Args:
            limit: Maximum number of results
        
        Returns:
            List of unprocessed image records
        """
        try:
            if not self.image_event_table:
                self.image_event_table = self.dynamodb.Table('image_event')
            
            response = self.image_event_table.query(
                IndexName='processed-time_stamp-index',
                KeyConditionExpression=Key('processed').eq('false'),
                Limit=limit,
                ScanIndexForward=True  # Oldest first
            )
            
            results = response.get('Items', [])
            logger.info(f"Found {len(results)} unprocessed images")
            return results
            
        except Exception as e:
            logger.error(f"Error querying unprocessed images: {e}")
            return []
    
    def get_detections_by_camera(self, camera_id: str, start_date: Optional[str] = None,
                                end_date: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Get all detections from a specific camera.
        
        Args:
            camera_id: Camera identifier
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            limit: Maximum number of results
        
        Returns:
            List of detection records
        """
        try:
            if not self.detection_results_table:
                self.detection_results_table = self.dynamodb.Table('detection_results')
            
            query_params = {
                'IndexName': 'camera_id-timestamp-index',
                'KeyConditionExpression': Key('camera_id').eq(camera_id),
                'Limit': limit,
                'ScanIndexForward': False
            }
            
            if start_date and end_date:
                query_params['KeyConditionExpression'] &= Key('timestamp').between(start_date, end_date)
            elif start_date:
                query_params['KeyConditionExpression'] &= Key('timestamp').gte(start_date)
            elif end_date:
                query_params['KeyConditionExpression'] &= Key('timestamp').lte(end_date)
            
            response = self.detection_results_table.query(**query_params)
            results = response.get('Items', [])
            
            logger.info(f"Found {len(results)} detections for camera: {camera_id}")
            return results
            
        except Exception as e:
            logger.error(f"Error querying detections by camera: {e}")
            return []
    
    def get_detections_by_geographic_region(self, lat_min: float, lat_max: float,
                                           lon_min: float, lon_max: float, limit: int = 100) -> List[Dict]:
        """
        Get detections within a geographic bounding box.
        
        Args:
            lat_min: Minimum latitude
            lat_max: Maximum latitude
            lon_min: Minimum longitude
            lon_max: Maximum longitude
            limit: Maximum number of results
        
        Returns:
            List of detection records
        """
        try:
            if not self.detection_results_table:
                self.detection_results_table = self.dynamodb.Table('detection_results')
            
            # Use scan with geographic filter
            response = self.detection_results_table.scan(
                FilterExpression=Attr('latitude').between(Decimal(str(lat_min)), Decimal(str(lat_max))) &
                                Attr('longitude').between(Decimal(str(lon_min)), Decimal(str(lon_max))),
                Limit=limit
            )
            
            results = response.get('Items', [])
            
            # Handle pagination
            while 'LastEvaluatedKey' in response and len(results) < limit:
                response = self.detection_results_table.scan(
                    FilterExpression=Attr('latitude').between(Decimal(str(lat_min)), Decimal(str(lat_max))) &
                                    Attr('longitude').between(Decimal(str(lon_min)), Decimal(str(lon_max))),
                    ExclusiveStartKey=response['LastEvaluatedKey'],
                    Limit=limit - len(results)
                )
                results.extend(response.get('Items', []))
            
            logger.info(f"Found {len(results)} detections in geographic region")
            return results
            
        except Exception as e:
            logger.error(f"Error querying detections by geographic region: {e}")
            return []
    
    def get_high_confidence_detections(self, min_confidence: float = 0.8, limit: int = 100) -> List[Dict]:
        """
        Get all high-confidence detections.
        
        Args:
            min_confidence: Minimum confidence threshold (0.0 - 1.0)
            limit: Maximum number of results
        
        Returns:
            List of high-confidence detection records
        """
        try:
            if not self.detection_results_table:
                self.detection_results_table = self.dynamodb.Table('detection_results')
            
            # Query high confidence level
            response = self.detection_results_table.query(
                IndexName='confidence_level-timestamp-index',
                KeyConditionExpression=Key('confidence_level').eq('high'),
                FilterExpression=Attr('average_confidence').gte(Decimal(str(min_confidence))),
                Limit=limit,
                ScanIndexForward=False
            )
            
            results = response.get('Items', [])
            logger.info(f"Found {len(results)} high-confidence detections")
            return results
            
        except Exception as e:
            logger.error(f"Error querying high-confidence detections: {e}")
            return []
    
    def update_s3_metadata(self, bucket: str, key: str, metadata: Dict[str, str]) -> bool:
        """
        Update metadata for an S3 object (copy object with new metadata).
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            metadata: Dictionary of metadata key-value pairs
        
        Returns:
            bool: True if successful
        """
        try:
            # S3 requires copying object to update metadata
            copy_source = {'Bucket': bucket, 'Key': key}
            
            self.s3_client.copy_object(
                Bucket=bucket,
                Key=key,
                CopySource=copy_source,
                Metadata=metadata,
                MetadataDirective='REPLACE'
            )
            
            logger.info(f"Updated metadata for s3://{bucket}/{key}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating S3 metadata: {e}")
            return False
    
    def mark_image_as_processed(self, event_id: str) -> bool:
        """
        Mark an image event as processed.
        
        Args:
            event_id: Event ID from image_event table
        
        Returns:
            bool: True if successful
        """
        try:
            if not self.image_event_table:
                self.image_event_table = self.dynamodb.Table('image_event')
            
            self.image_event_table.update_item(
                Key={'event_id': event_id},
                UpdateExpression='SET processed = :val, processed_timestamp = :ts',
                ExpressionAttributeValues={
                    ':val': 'true',
                    ':ts': datetime.utcnow().isoformat() + 'Z'
                }
            )
            
            logger.info(f"Marked event {event_id} as processed")
            return True
            
        except Exception as e:
            logger.error(f"Error marking image as processed: {e}")
            return False
    
    def get_detection_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about detections.
        
        Returns:
            Dictionary with statistics including:
            - total_detections
            - species_counts
            - camera_counts
            - average_confidence
            - date_range
        """
        try:
            if not self.detection_results_table:
                self.detection_results_table = self.dynamodb.Table('detection_results')
            
            # Scan entire table (use cautiously in production)
            response = self.detection_results_table.scan()
            items = response.get('Items', [])
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.detection_results_table.scan(
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend(response.get('Items', []))
            
            # Calculate statistics
            species_counts = {}
            camera_counts = {}
            total_confidence = 0
            timestamps = []
            
            for item in items:
                # Species count
                species = item.get('species', 'unknown')
                species_counts[species] = species_counts.get(species, 0) + 1
                
                # Camera count
                camera_id = item.get('camera_id', 'unknown')
                camera_counts[camera_id] = camera_counts.get(camera_id, 0) + 1
                
                # Confidence
                total_confidence += float(item.get('average_confidence', 0))
                
                # Timestamps
                timestamps.append(item.get('timestamp', ''))
            
            stats = {
                'total_detections': len(items),
                'species_counts': species_counts,
                'unique_species': len(species_counts),
                'camera_counts': camera_counts,
                'unique_cameras': len(camera_counts),
                'average_confidence': total_confidence / len(items) if items else 0,
                'earliest_detection': min(timestamps) if timestamps else None,
                'latest_detection': max(timestamps) if timestamps else None
            }
            
            logger.info(f"Generated statistics for {len(items)} detections")
            return stats
            
        except Exception as e:
            logger.error(f"Error generating statistics: {e}")
            return {}
    
    # Helper methods
    
    def _calculate_geo_hash(self, lat: float, lon: float, precision: int = 4) -> str:
        """
        Calculate a simplified geohash for geographic indexing.
        
        Args:
            lat: Latitude
            lon: Longitude
            precision: Geohash precision (number of characters)
        
        Returns:
            Geohash string
        """
        # Simplified geohash implementation (for production, use geohash library)
        lat_range = [-90, 90]
        lon_range = [-180, 180]
        geohash = []
        
        for _ in range(precision):
            lat_mid = (lat_range[0] + lat_range[1]) / 2
            lon_mid = (lon_range[0] + lon_range[1]) / 2
            
            if lat >= lat_mid and lon >= lon_mid:
                geohash.append('1')
                lat_range[0] = lat_mid
                lon_range[0] = lon_mid
            elif lat >= lat_mid and lon < lon_mid:
                geohash.append('2')
                lat_range[0] = lat_mid
                lon_range[1] = lon_mid
            elif lat < lat_mid and lon >= lon_mid:
                geohash.append('3')
                lat_range[1] = lat_mid
                lon_range[0] = lon_mid
            else:
                geohash.append('4')
                lat_range[1] = lat_mid
                lon_range[1] = lon_mid
        
        return ''.join(geohash)
    
    def _categorize_confidence(self, confidence: float) -> str:
        """
        Categorize confidence score into levels.
        
        Args:
            confidence: Confidence score (0.0 - 1.0)
        
        Returns:
            Confidence level: 'high', 'medium', or 'low'
        """
        if confidence >= 0.8:
            return 'high'
        elif confidence >= 0.5:
            return 'medium'
        else:
            return 'low'


# Standalone functions for integration

def initialize_stage4_tables(region: str = 'us-east-1') -> MetadataManager:
    """
    Initialize all Stage 4 DynamoDB tables.
    
    Args:
        region: AWS region
    
    Returns:
        MetadataManager instance
    """
    manager = MetadataManager(region=region)
    
    # Create tables
    logger.info("Creating image_event table...")
    manager.create_enhanced_image_event_table()
    
    logger.info("Creating detection_results table...")
    manager.create_detection_results_table()
    
    logger.info("Stage 4 tables initialized successfully")
    return manager


if __name__ == "__main__":
    # Example usage
    print("Stage 4: Metadata Management System")
    print("=" * 50)
    
    # Initialize tables
    manager = initialize_stage4_tables()
    
    # Example: Store a detection result
    sample_detection = {
        'image_name': 'cheetah_001.jpg',
        's3_uri': 's3://from-camera-trap-1/images/cheetah_001.jpg',
        'camera_id': 'CAM_001',
        'latitude': -1.292066,
        'longitude': 36.821945,
        'temperature': 28.5,
        'elevation': 1795,
        'capture_time': '2024-11-30T10:30:00Z',
        'image_resolution': '1920x1080',
        'file_size_bytes': 2456789,
        'detections': [
            {
                'class': 'cheetah',
                'score': 0.95,
                'bbox': [100, 150, 400, 450]
            }
        ]
    }
    
    print("\nStoring sample detection...")
    manager.store_detection_result(sample_detection)
    
    print("\nStage 4 setup complete!")
