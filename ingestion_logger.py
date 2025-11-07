import json
import boto3
import uuid
import yaml
import time


with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

dynamodb=boto3.resource("dynamodb")
table=dynamodb.Table(config['IMG_EVENT_TBL']['table_name'])

def lambda_handler(event, context):
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        table.put_item(Item={
            "event_id": str(uuid.uuid4()),
            "bucket_name": bucket,
            "object_key": key,
            "time_stamp": int(time.time()),
            "processed":False
        })
    return {"statusCode": 200}