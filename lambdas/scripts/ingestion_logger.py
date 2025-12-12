import json
import boto3
import uuid
import time
import os
import logging

#Setting up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

#Creating S3 Client
try:
    s3_client = boto3.client("s3")
    logger.info(f"Successfully created S3 Client")
except Exception as e:
    logger.error("Failed to create S3 Client")
    raise e

#Creating Dynamodb Resource
try:
    dynamodb=boto3.resource("dynamodb")
    table = dynamodb.Table(os.environ["TABLE_NAME"])    
    logger.info(f"DynamoDB successfully pointing to: {table}")
except Exception as e:
    logger.error(f"Failed to initialize DynamoDB table: {e}")
    raise e

#Lambda Handler function
def lambda_handler(event, context):
    logger.info(f"Lambda invoked with event: {json.dumps(event)}")
    
    if "Records" not in event:
        logger.warning("No Records found in event")
        return {"statusCode": 400, "body": "No records were found in event to process."}
    
    for record in event["Records"]:
        try:
            bucket = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]
            logger.info(f"Processing file: s3://{bucket}/{key}")

            # Fetch metadata
            try:
                response = s3_client.head_object(Bucket=bucket, Key=key)
                metadata = response.get("Metadata", {})
                logger.info(f"Metadata received: {metadata}")
            except Exception as e:
                logger.error(f"Failed to retrieve metadata for {key}: {e}")
                metadata = {}
            
            #Metadata extraction into item dict to be inserted into dynamo db
            item={
                    "event_id": str(uuid.uuid4()),
                    "bucket_name": bucket,
                    "object_key": key,
                    "time_stamp": int(time.time()),
                    
                    #Metadata data fields sent over with images from simulation
                    "lat":metadata.get("lat"),
                    "long":metadata.get("long"),
                    "positional_accuracy":metadata.get("positional_accuracy"),
                    "temperature":metadata.get("temperature"),
                    "elevation":metadata.get("elevation"),
                    "image_capture_time":metadata.get("time"),
                    "raw_metadata" : metadata,
                    
                    # Flags
                    "processed":False,
                    "classification_complete" : False,
                    "notify_pending": False
                }
            
            table.put_item(Item=item)
            logger.info(f"Inserted the following item into DynamoDB: {item}")
        except Exception as e:
            logger.error(f"Failed to process the following record {record}: {e}")
    logger.info("Ingestion Logger Lambda function execution completed")
    return {"statusCode": 200}