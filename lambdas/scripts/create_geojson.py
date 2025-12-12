import json
import boto3
import os
import logging
from decimal import Decimal

# setting up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

#Setting Environment Variables
TABLE_NAME = os.environ["DYNAMODB_TABLE"]
S3_BUCKET = os.environ["S3_BUCKET"]
S3_KEY_FLAT = "wildlife_predictions_FLATTENED.json"
S3_KEY_GEOJSON = "wildlife_predictions.geojson"

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
    s3=boto3.client("s3")  
    logger.info(f"S3 Client successfully created")
except Exception as e:
    logger.error(f"Failed to create S3 Client")
    raise e

# helper function assist with conversion of dynamo db decimal to float
def convert_decimal_to_float(value):
    if isinstance(value, list):
        return[convert_decimal_to_float(i)for i in value]
    
    elif isinstance(value,dict):
        return{k: convert_decimal_to_float(v) for k, v in value.items()}
    
    elif isinstance(value,Decimal):
        return float(value)
    else:
        return value

def lambda_handler(event, context):

    #scan all items in the dynamo db
    results = []
    scan_params ={}

    while True:
        response = table.scan(**scan_params)
        results.extend(response.get("Items",[]))

        if "LastEvaluatedKey" not in response:
            break
        scan_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    # creating two outputs:

    # Flattened features of predictions as json for Power BI  & Normal geojson for mapper
    flat_features =[]
    geojson_features=[]
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

            geojson_features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties":{
                    "event_id": event_id,
                    "class": None,
                    "confidence" : None
                }
            })
            continue
        # for multiple predictions, each will become its own point
        for pred in predictions:
            pred = convert_decimal_to_float(pred)
                  
            flat_features.append({
                "event_id" : event_id,
                "class" : pred.get("class"),
                "confidence" : pred.get("confidence"),
                "latitude" : lat,
                "longitude" : lon
            })

            geojson_features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties":{
                    "event_id": event_id,
                    "class": pred.get("class"),
                    "confidence" : pred.get("confidence")
                }
                
            })
    # create geojson feature collection
    geojson_feature_collection ={
        "type":"FeatureCollection",
        "features": geojson_features
    }

    #writing flattened json to S3
    s3.put_object(
        Bucket = S3_BUCKET,
        Key = S3_KEY_FLAT,
        Body = json.dumps(flat_features),
        ContentType="application/json"
    )

    #writing flattened geojson to S3
    s3.put_object(
        Bucket = S3_BUCKET,
        Key = S3_KEY_GEOJSON,
        Body = json.dumps(geojson_feature_collection),
        ContentType="application/json"
    )
    
            
    logger.info(f"{len(flat_features)} rows written to s3://{S3_BUCKET}/{S3_KEY_FLAT}.")
    logger.info(f"{len(geojson_feature_collection)} rows written to s3://{S3_BUCKET}/{S3_KEY_GEOJSON}.")

    return {"statusCode": 200}

       
       
