import json
import boto3
import os
import logging
import base64
from decimal import Decimal

#Setting up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

#Setting Environment Variables
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
TABLE_NAME = os.environ['DYNAMODB_TABLE']

# DynamoDB does not suppor native float types, but supports Number (N) type via Decimal from decimal module
def convert_floats_to_decimal(obj):
    if isinstance(obj,list):
        return[convert_floats_to_decimal(i)for i in obj]
    elif isinstance(obj,dict):
        return{k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj,float):
        return Decimal(str(obj))
    else:
        return obj

#Creating Sagemaker Client
try:
    sagemaker = boto3.client("sagemaker-runtime")
    logger.info(f"Successfully created Sagemaker Client")
except Exception as e:
    logger.error("Failed to create Sagemaker Client")
    raise e

#Creating Dynamodb Resource
try:
    dynamodb=boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)    
    logger.info(f"DynamoDB successfully pointing to: {table}")
except Exception as e:
    logger.error(f"Failed to initialize DynamoDB table: {e}")
    raise e

#Creating S3 Client
try:
    s3 = boto3.client("s3")
    logger.info(f"Successfully created S3 Client")
except Exception as e:
    logger.error("Failed to create S3 Client")
    raise e


def lambda_handler(event, context):
    for record in event['Records']:
        # iterates through records and skips DB events that are not INSERTS or MODIFY
        event_name = record["eventName"]
        if event_name not in ("INSERT", "MODIFY"):
            logger.info(f"Not a INSERT or MODIFY event. Skipping: {record['eventName']}")
            continue
        try:
            #Skips image if it has already been classified
            new_image = record["dynamodb"]["NewImage"]
            if new_image.get("classification_complete", {}).get("BOOL") is True:
                continue

            bucket = new_image['bucket_name']['S']
            key = new_image['object_key']['S']
            event_id = new_image["event_id"]["S"]

            logger.info(f"Processing DDB insert/modification: event_id={event_id}, s3://{bucket}/{key}")

            #fetching image from camera trap s3 bucket
            try:
                obj = s3.get_object(Bucket=bucket, Key=key)
                image_bytes = obj['Body'].read()
                logger.info("Successfully read image from S3")
            except Exception as e:
                logger.error(f"Failed reading image from S3: {e}")
                # continuing to process other records
                continue


            #images are encoded as base64 as payload for sagemaker
            try:
                payload = {"image":base64.b64encode(image_bytes).decode("utf-8")}
                logger.info(f"Payload sample: {str(payload)[:100]}")

                #invoke sagemaker endpoint
                response = sagemaker.invoke_endpoint(
                EndpointName =ENDPOINT_NAME,
                ContentType="application/json",
                Body=json.dumps(payload)
                )
                logger.info("SageMaker endpoint invoked successfully")
            except Exception as e:
                logger.error(f"Error invoking SageMaker endpoint: {e}")
                continue

            # Parsing YOLO response from sagemaker endpoint
            try:
                response_body = response['Body'].read().decode('utf-8')
                logger.info(f"SageMaker raw response: {response_body}")

                result = json.loads(response_body)
                predictions = result.get("predictions",[])
                logger.info(f"Detections received. {len(predictions)} objects detected.")

                if predictions:
                    logger.info(f"First Prediction: {predictions[0]}")
                else:
                    logger.warning(f"No predictions returned for this image.")

            except Exception as e:
                logger.error(f"Failed to parse YOLO response: {e}")
                continue

            #Converts float predictions to decimal for dynamoDB & updates records with classification results
            predictions_decimal = convert_floats_to_decimal(predictions)
            try:
                table.update_item(
                    Key={"event_id":event_id},
                    UpdateExpression="""
                        SET classification_complete = :c,
                        predictions = :p,
                        notify_pending = :n
                    """,
                    ExpressionAttributeValues={
                        ":c": True,
                        ":p": predictions_decimal,
                        ":n": True
                        }
                    )
                
                logger.info(f"DDB record updated successfully for {event_id}")
            except Exception as e:
                logger.error(f"Failed updating DynamoDB for {event_id}: {e}")
                continue
        except Exception as e:
            logger.error(f"Unhandled error processing record: {e}")
    return {'statusCode': 200}
