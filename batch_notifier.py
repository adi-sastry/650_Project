import boto3
import os
import time
from boto3.dynamodb.conditions import Attr
import logging

#Setting up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb=boto3.resource("dynamodb")
sns = boto3.client("sns")

def lambda_handler(event, context):
    logger.info("Batch notifier running...")

    table_name = os.environ["TABLE_NAME"]
    sns_topic_arn = os.environ["SNS_TOPIC_ARN"]
    logger.info(f"Using DynamoDB table: {table_name}")
    logger.info(f"SNS Topic ARN: {sns_topic_arn}")
    
    try:
        table = dynamodb.Table(table_name)
        logger.info(f"DynamoDB successfully pointing to: {table}")
    except Exception as e:
        logger.error(f"Failed to initialize DynamoDB table: {e}", exc_info=True)
        raise e

    try:
        now = int(time.time())
        five_min_ago = now - 300
        logger.info(f"Scanning for unprocessed items since timestamp >= {five_min_ago} ({time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(five_min_ago))} UTC)")


        # Scan unprocessed items
        items = []
        response = table.scan(
            FilterExpression=Attr("processed").eq(False) & Attr("time_stamp").gte(five_min_ago))
        items.extend(response.get("Items",[]))
        logger.info(f"Initial scan returned {len(response.get('Items', []))} items")
    except Exception as e:
        logger.error(f"Intital scan failed: {e}")
        raise e

    # Scanning for more images within 5 minute window
    while "LastEvaluatedKey" in response:
        try:
            logger.info("Continuing scan...")
            response = table.scan(
                FilterExpression=Attr("processed").eq(False) & Attr("time_stamp").gte(five_min_ago),
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )

            items.extend(response.get("Items", []))
            logger.info(f"Follow-up scan returned {len(response.get('Items', []))} items")
    
        except Exception as e:
            logger.error(f"Error scanning DynamoDB batch starting at {response.get('LastEvaluatedKey')}: {e}", exc_info=True)
            break

    if not items:
        return {"statusCode": 200}
    logger.info(f"Total unprocessed items found: {len(items)}")
    
    #Creates message to account for images uploaded within 5 min window
    message_lines = [f"Detection Occured! {len(items)} new images uploaded. Another batch MAY be uploaded so be on the look out:"]
    for i in items:
        message_lines.append(f"  - {i['bucket_name']}/{i['object_key']}")
    message = "\n".join(message_lines)
    logger.info("SNS message prepared:")
    logger.info(message)

    # Publish SNS
    try:
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject="DETECTION OCCURED - Camera Trap Batch Upload",
            Message=message
        )
        logger.info("SNS message published successfully.")
    except Exception as e:
        logger.error(f"Error publishing to SNS: {e}", exc_info=True)
        raise e


    # Mark all items as processed=True to indicate that it went thru lambda
    logger.info("Updating items as processed=True")

    try:
        with table.batch_writer() as batch:
            for i in items:
                i["processed"] = True
                batch.put_item(Item=i)
        logger.info(f"Marked {len(items)} items as processed.")
    except Exception as e:
        logger.error("Error updating items to processed=True", exc_info=True)
        raise e
    
    logger.info("Batch notifier Lambda completed successfully.")
    return {"statusCode": 200}