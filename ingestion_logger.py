import json
import boto3
import uuid
import yaml
import time
import logging

#Setting up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

#loading config to get table name
try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    logger.info("Config loaded successfully")
except Exception as e:
    logger.error(f"Failed  to load config.yaml:{e}")
    raise e

#Creating Dynamodb client
try:
    dynamodb=boto3.resource("dynamodb")
    table=dynamodb.Table(config['IMG_EVENT_TBL']['table_name'])
    logger.info(f"DynamoDB successfully pointing to: {config['IMG_EVENT_TBL']['table_name']}")
except Exception as e:
    logger.error(f"Failed to initialize DynamoDB table: {e}")
    raise e

#Lambda Handler function
def lambda_handler(event, context):
    logger.info(f"Lambda invoked with event: {json.dumps(event)}")
    
    if "Records" not in event:
        logger.warning("No Records found in event")
        return {"statusCode": 400, "body": "No records to process"}
    
    for record in event["Records"]:
        try:
            bucket = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]
            logger.info(f"Processing file: s3://{bucket}/{key}")

            item={
                    "event_id": str(uuid.uuid4()),
                    "bucket_name": bucket,
                    "object_key": key,
                    "time_stamp": int(time.time()),
                    "processed":False
                }
            
            table.put_item(Item=item)
            logger.info(f"Inserted item into DynamoDB: {item}")
        except Exception as e:
            logger.error(f"Failed to process record {record}: {e}")
    logger.info("Ingestion Logger Lambda function execution completed")
    return {"statusCode": 200}