import json
import boto3
import os
import logging
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ["DYNAMODB_TABLE"]
S3_BUCKET = os.environ["S3_BUCKET"]
S3_KEY = "wildlife_predictions.json"

#Creating Dynamodb Resource
try:
    dynamodb=boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)    
    logger.info(f"DynamoDB successfully pointing to: {table}")
except Exception as e:
    logger.error(f"Failed to initialize DynamoDB table: {e}")
    raise e

try:
    s3=boto3.client("s3")  
    logger.info(f"S3 Client successfully created")
except Exception as e:
    logger.error(f"Failed to create S3 Client")
    raise e

def decimal_to_float(value):
    if isinstance(value, list):
        return[decimal_to_float(i)for i in value]
    
    elif isinstance(value,dict):
        return{k: decimal_to_float(v) for k, v in value.items()}
    
    elif isinstance(value,Decimal):
        return float(value)
    else:
        return value

def lambda_handler(event, context):

    results = []
    scan_params ={}

    while True:
        response = table.scan(**scan_params)
        results.extend(response.get("Items",[]))

        if "LastEvaluatedKey" not in response:
            break
        scan_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    flat_features =[]
    for item in results:
        event_id = item["event_id"]
        lat = float(item["lat"])
        lon = float(item["long"])

        predictions = item.get("predictions",[])
        
        # if no predictions fill in properties with None
        if not predictions:
            flat_features.append({
                "event_id" : event_id,
                "class" : None,
                "confidence" : None,
                "latitude" : lat,
                "longitude" : lon
            })
            continue
        # for multiple predictions, each will become its own point
        for pred in predictions:
            pred = decimal_to_float(pred)
                  
            flat_features.append({
                "event_id" : event_id,
                "class" : pred.get("class"),
                "confidence" : pred.get("confidence"),
                "latitude" : lat,
                "longitude" : lon
            })
    s3.put_object(
        Bucket = S3_BUCKET,
        Key = S3_KEY,
        Body = json.dumps(flat_features),
        ContentType="application/json"
    )
            
    logger.info(f"{len(flat_features)} rows written to s3://{S3_BUCKET}/{S3_KEY}.")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": f"Written {len(flat_features)} rows to S3"})
    }

       
       
