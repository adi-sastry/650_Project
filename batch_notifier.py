import boto3
import os
import time
import yaml
from datetime import datetime, timedelta

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

dynamodb=boto3.resource("dynamodb")
sns = boto3.client("sns")

table=dynamodb.Table(config['IMG_EVENT_TBL']['table_name'])

def lambda_handler(event, context):
    print("Batch notifier running...")
    now = int(time.time())
    five_min_ago = now - 300

    # Scan unprocessed items from last 5 min
    response = table.scan(
        FilterExpression="processed = :p AND #t >= :t",
        ExpressionAttributeValues={":p": False, ":t": five_min_ago},
        ExpressionAttributeNames={"#t": "timestamp"}
    )

    items = response.get("Items", [])
    if not items:
        print("No new images in last 5 min")
        return
    
    #Creates message to account for images uploaded within 5 min window
    message_lines = [f"{len(items)} new images uploaded:"]
    for i in items:
        message_lines.append(f"  - {i['bucket_name']}/{i['object_key']}")
    message = "\n".join(message_lines)

    # Publish SNS
    sns.publish(
        TopicArn=os.environ["SNS_TOPIC_ARN"],
        Subject="Camera Trap Batch Upload",
        Message=message
    )

    # Mark all items as processed=True to indicate that it went thru lambda
    with table.batch_writer() as batch:
        for i in items:
            batch.put_item(Item={
                **i,
                "processed": True
            })

    return {"statusCode": 200}