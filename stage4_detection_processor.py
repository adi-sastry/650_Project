"""
Stage 2 to Stage 4 Integration
Processes images through YOLOv8 and stores results in detection_results table
"""

import json
import time
import yaml
import boto3
from datetime import datetime
from typing import Dict, List, Optional
from stage4_metadata_manager import MetadataManager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DetectionProcessor:
    """
    Processes detection results from SageMaker and stores them with metadata.
    """
    
    def __init__(self, config_path: str = 'config.yaml', auth_path: str = 'aws_auth.yaml'):
        """
        Initialize the detection processor.
        
        Args:
            config_path: Path to configuration file
            auth_path: Path to AWS authentication file
        """
        self.config = self._load_config(config_path)
        self.auth = self._load_config(auth_path)
        
        # Initialize AWS clients
        self.session = self._create_session()
        self.s3_client = self.session.client('s3')
        self.sagemaker_runtime = self.session.client('sagemaker-runtime')
        self.dynamodb = self.session.resource('dynamodb')
        
        # Initialize metadata manager
        self.metadata_manager = MetadataManager(region=self.auth['aws']['region'])
        
        # Get tables
        self.image_event_table = self.dynamodb.Table('image_event')
        
        logger.info("DetectionProcessor initialized successfully")
    
    def _load_config(self, path: str) -> dict:
        """Load YAML configuration file."""
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    def _create_session(self) -> boto3.Session:
        """Create authenticated boto3 session."""
        return boto3.Session(
            aws_access_key_id=self.auth['aws']['access_key_id'],
            aws_secret_access_key=self.auth['aws']['secret_access_key'],
            region_name=self.auth['aws']['region']
        )
    
    def process_unprocessed_images(self, batch_size: int = 10, endpoint_name: Optional[str] = None) -> Dict:
        """
        Process all unprocessed images through YOLOv8 and store results.
        
        Args:
            batch_size: Number of images to process in this run
            endpoint_name: SageMaker endpoint name (optional, uses config if not provided)
        
        Returns:
            Dictionary with processing statistics
        """
        # Get endpoint name from config if not provided
        if not endpoint_name:
            endpoint_name = self.config.get('sagemaker', {}).get('endpoint_name', 'yolov8-camera-trap-endpoint')
        
        # Get unprocessed images
        unprocessed_images = self.metadata_manager.get_unprocessed_images(limit=batch_size)
        
        if not unprocessed_images:
            logger.info("No unprocessed images found")
            return {
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'detections_stored': 0
            }
        
        logger.info(f"Processing {len(unprocessed_images)} unprocessed images")
        
        stats = {
            'total_processed': len(unprocessed_images),
            'successful': 0,
            'failed': 0,
            'detections_stored': 0
        }
        
        for image_event in unprocessed_images:
            try:
                # Extract image information
                bucket = image_event['bucket_name']
                key = image_event['object_key']
                event_id = image_event['event_id']
                camera_id = image_event.get('camera_id', 'unknown')
                
                logger.info(f"Processing: {bucket}/{key}")
                
                # Download image
                img_bytes = self.s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()
                
                # Run inference
                response = self.sagemaker_runtime.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType="application/x-image",
                    Body=img_bytes
                )
                
                # Parse results
                result = json.loads(response["Body"].read())
                detections = result.get("detections", [])
                
                # Get image metadata
                s3_metadata = self._get_s3_object_metadata(bucket, key)
                
                # Prepare detection data
                detection_data = {
                    'image_name': key.split('/')[-1],
                    's3_uri': f's3://{bucket}/{key}',
                    'camera_id': camera_id,
                    'detections': detections,
                    'latitude': float(image_event.get('latitude', 0)),
                    'longitude': float(image_event.get('longitude', 0)),
                    'temperature': float(image_event.get('temperature', 0)) if image_event.get('temperature') else None,
                    'elevation': float(image_event.get('elevation', 0)) if image_event.get('elevation') else None,
                    'capture_time': image_event.get('capture_time', ''),
                    'image_resolution': s3_metadata.get('image_resolution', ''),
                    'file_size_bytes': image_event.get('file_size_bytes', 0),
                    'additional_metadata': {
                        'positional_accuracy': image_event.get('positional_accuracy', ''),
                        'content_type': image_event.get('content_type', ''),
                        'event_id': event_id,
                        'ingestion_timestamp': image_event.get('ingestion_timestamp', 0)
                    }
                }
                
                # Store detection results
                success = self.metadata_manager.store_detection_result(detection_data)
                
                if success:
                    # Mark image as processed
                    self.metadata_manager.mark_image_as_processed(event_id)
                    stats['successful'] += 1
                    stats['detections_stored'] += len(detections)
                    logger.info(f"Successfully processed {key} with {len(detections)} detections")
                else:
                    stats['failed'] += 1
                    logger.error(f"Failed to store detection results for {key}")
                
                # Small delay to avoid throttling
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing image {image_event.get('object_key', 'unknown')}: {e}", exc_info=True)
                stats['failed'] += 1
        
        logger.info(f"Processing complete. Stats: {stats}")
        return stats
    
    def process_single_image(self, bucket: str, key: str, endpoint_name: Optional[str] = None) -> bool:
        """
        Process a single image through the detection pipeline.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            endpoint_name: SageMaker endpoint name
        
        Returns:
            bool: True if successful
        """
        if not endpoint_name:
            endpoint_name = self.config.get('sagemaker', {}).get('endpoint_name', 'yolov8-camera-trap-endpoint')
        
        try:
            # Download image
            img_bytes = self.s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()
            
            # Run inference
            response = self.sagemaker_runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="application/x-image",
                Body=img_bytes
            )
            
            result = json.loads(response["Body"].read())
            detections = result.get("detections", [])
            
            # Get metadata
            s3_metadata = self._get_s3_object_metadata(bucket, key)
            
            # Extract camera ID
            camera_id = key.split('/')[-1].split('_')[0]
            
            detection_data = {
                'image_name': key.split('/')[-1],
                's3_uri': f's3://{bucket}/{key}',
                'camera_id': camera_id,
                'detections': detections,
                'latitude': float(s3_metadata.get('lat', 0)),
                'longitude': float(s3_metadata.get('long', 0)),
                'temperature': float(s3_metadata.get('temperature', 0)) if s3_metadata.get('temperature') else None,
                'elevation': float(s3_metadata.get('elevation', 0)) if s3_metadata.get('elevation') else None,
                'capture_time': s3_metadata.get('time', ''),
                'file_size_bytes': s3_metadata.get('file_size_bytes', 0)
            }
            
            return self.metadata_manager.store_detection_result(detection_data)
            
        except Exception as e:
            logger.error(f"Error processing single image {bucket}/{key}: {e}")
            return False
    
    def _get_s3_object_metadata(self, bucket: str, key: str) -> dict:
        """Get S3 object metadata and attributes."""
        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=key)
            
            metadata = response.get('Metadata', {})
            metadata['file_size_bytes'] = response.get('ContentLength', 0)
            metadata['last_modified'] = response.get('LastModified', '').isoformat() if response.get('LastModified') else ''
            
            return metadata
        except Exception as e:
            logger.error(f"Error getting S3 metadata: {e}")
            return {}
    
    def get_processing_statistics(self) -> Dict:
        """
        Get comprehensive statistics about the processing pipeline.
        
        Returns:
            Dictionary with statistics
        """
        try:
            # Get detection statistics
            detection_stats = self.metadata_manager.get_detection_statistics()
            
            # Get unprocessed image count
            unprocessed = self.metadata_manager.get_unprocessed_images(limit=1000)
            
            # Get processed image count
            response = self.image_event_table.query(
                IndexName='processed-time_stamp-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('processed').eq('true'),
                Select='COUNT'
            )
            
            processed_count = response.get('Count', 0)
            
            stats = {
                'total_images_ingested': processed_count + len(unprocessed),
                'processed_images': processed_count,
                'unprocessed_images': len(unprocessed),
                'processing_rate': f"{(processed_count / (processed_count + len(unprocessed)) * 100):.2f}%" if (processed_count + len(unprocessed)) > 0 else "0%",
                **detection_stats
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting processing statistics: {e}")
            return {}


def main():
    """
    Main function to run the detection processor.
    """
    print("=" * 60)
    print("Stage 2 to Stage 4 Integration: Detection Processor")
    print("=" * 60)
    
    # Initialize processor
    processor = DetectionProcessor()
    
    # Process unprocessed images
    print("\nProcessing unprocessed images...")
    stats = processor.process_unprocessed_images(batch_size=50)
    
    print(f"\nProcessing Results:")
    print(f"  Total Processed: {stats['total_processed']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Detections Stored: {stats['detections_stored']}")
    
    # Get overall statistics
    print("\nGetting pipeline statistics...")
    pipeline_stats = processor.get_processing_statistics()
    
    print(f"\nPipeline Statistics:")
    print(f"  Total Images Ingested: {pipeline_stats.get('total_images_ingested', 0)}")
    print(f"  Processed Images: {pipeline_stats.get('processed_images', 0)}")
    print(f"  Unprocessed Images: {pipeline_stats.get('unprocessed_images', 0)}")
    print(f"  Processing Rate: {pipeline_stats.get('processing_rate', '0%')}")
    print(f"  Total Detections: {pipeline_stats.get('total_detections', 0)}")
    print(f"  Unique Species: {pipeline_stats.get('unique_species', 0)}")
    print(f"  Average Confidence: {pipeline_stats.get('average_confidence', 0):.2f}")
    
    print("\nDetection processing complete!")


if __name__ == "__main__":
    main()
