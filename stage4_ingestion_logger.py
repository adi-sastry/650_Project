"""
Enhanced Ingestion Logger Lambda Function for Stage 4
Logs image ingestion events with comprehensive metadata extraction
"""

import json
import boto3
import uuid
import time
import os
import logging
from urllib.parse import unquote_plus

# Setting up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Creating DynamoDB client
try:
    dynamodb = boto3.resource("dynamodb")
    s3_client = boto3.client("s3")
    table = dynamodb.Table(os.environ["TABLE_NAME"])    
    logger.info(f"DynamoDB successfully pointing to: {table}")
except Exception as e:
    logger.error(f"Failed to initialize DynamoDB table: {e}")
    raise e


def extract_camera_id_from_key(key: str) -> str:
    """
    Extract camera ID from S3 key.
    Assumes format: images/{camera_id}_{timestamp}_{image_name}.jpg
    Or defaults to filename prefix before first underscore.
    
    Args:
        key: S3 object key
    
    Returns:
        Camera ID string
    """
    try:
        # Get filename from key
        filename = key.split('/')[-1]
        
        # Remove extension
        name_without_ext = filename.rsplit('.', 1)[0]
        
        # Extract camera ID (first part before underscore)
        camera_id = name_without_ext.split('_')[0]
        
        return camera_id if camera_id else 'unknown'
    except Exception as e:
        logger.warning(f"Could not extract camera_id from key {key}: {e}")
        return 'unknown'


def get_s3_metadata(bucket: str, key: str) -> dict:
    """
    Retrieve metadata from S3 object.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
    
    Returns:
        Dictionary of metadata
    """
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        
        metadata = response.get('Metadata', {})
        
        # Also get object information
        additional_info = {
            'file_size_bytes': response.get('ContentLength', 0),
            'content_type': response.get('ContentType', ''),
            'last_modified': response.get('LastModified', '').isoformat() if response.get('LastModified') else '',
            'etag': response.get('ETag', '').strip('"')
        }
        
        # Merge metadata and additional info
        metadata.update(additional_info)
        
        return metadata
    except Exception as e:
        logger.error(f"Error retrieving S3 metadata for {bucket}/{key}: {e}")
        return {}


def lambda_handler(event, context):
    """
    Enhanced Lambda handler for image ingestion logging.
    Extracts and stores comprehensive metadata from S3 events.
    
    Args:
        event: S3 event notification
        context: Lambda context
    
    Returns:
        Status code dictionary
    """
    logger.info(f"Lambda invoked with event: {json.dumps(event)}")
    
    if "Records" not in event:
        logger.warning("No Records found in event")
        return {"statusCode": 400, "body": "No records to process"}
    
    successful_records = 0
    failed_records = 0
    
    for record in event["Records"]:
        try:
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])  # URL decode the key
            size = record["s3"]["object"].get("size", 0)
            
            logger.info(f"Processing file: s3://{bucket}/{key}")
            
            # Extract camera ID from key
            camera_id = extract_camera_id_from_key(key)
            
            # Get additional metadata from S3
            s3_metadata = get_s3_metadata(bucket, key)
            
            # Create comprehensive item for DynamoDB
            item = {
                "event_id": str(uuid.uuid4()),
                "bucket_name": bucket,
                "object_key": key,
                "time_stamp": int(time.time()),
                "processed": "false",  # Changed to string for GSI compatibility
                "camera_id": camera_id,
                "file_size_bytes": s3_metadata.get('file_size_bytes', size),
                "content_type": s3_metadata.get('content_type', 'image/jpeg'),
                "etag": s3_metadata.get('etag', ''),
                
                # Environmental metadata from S3 object metadata
                "latitude": s3_metadata.get('lat', '0'),
                "longitude": s3_metadata.get('long', '0'),
                "positional_accuracy": s3_metadata.get('positional_accuracy', ''),
                "temperature": s3_metadata.get('temperature', ''),
                "elevation": s3_metadata.get('elevation', ''),
                "capture_time": s3_metadata.get('time', ''),
                
                # Ingestion metadata
                "ingestion_timestamp": int(time.time()),
                "s3_uri": f"s3://{bucket}/{key}",
                "event_source": record.get("eventSource", "aws:s3"),
                "event_name": record.get("eventName", "ObjectCreated:Put")
            }
            
            # Remove empty string values to save space
            item = {k: v for k, v in item.items() if v != ''}
            
            # Store in DynamoDB
            table.put_item(Item=item)
            logger.info(f"Successfully inserted item into DynamoDB: {item['event_id']}")
            successful_records += 1
            
        except Exception as e:
            logger.error(f"Failed to process record {record}: {e}", exc_info=True)
            failed_records += 1
    
    logger.info(f"Ingestion Logger Lambda execution completed. Success: {successful_records}, Failed: {failed_records}")
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Processing complete",
            "successful": successful_records,
            "failed": failed_records
        })
    }
