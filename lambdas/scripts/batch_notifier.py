import boto3
import os
import time
from boto3.dynamodb.conditions import Attr, Or
import logging

#Setting up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

#Creating Dynamodb Resource
try:
    dynamodb=boto3.resource("dynamodb")
    logger.info(f"DynamoDB resource successfully created")
except Exception as e:
    logger.error(f"Creation of DynamoDB resource failed")
    raise e

#Creating SNS Client
try:
    sns = boto3.client("sns")
    logger.info(f"SNS Client successfully created")
except Exception as e:
    logger.error(f"Creation of SNS Client failed")
    raise e


def lambda_handler(event, context):
    logger.info("Batch notifier running...")

    table_name = os.environ["TABLE_NAME"]
    sns_topic_arn = os.environ["SNS_TOPIC_ARN"]
    logger.info(f"Point to DynamoDB table: {table_name}")
    logger.info(f"SNS Topic ARN: {sns_topic_arn}")
    
    try:
        table = dynamodb.Table(table_name)
        logger.info(f"DynamoDB successfully pointing to: {table}")
    except Exception as e:
        logger.error(f"Failed to point to DynamoDB {table_name} table: {e}", exc_info=True)
        raise e

    try:
        #setting  5-min window lookback
        now = int(time.time())
        five_min_ago = now - 300
        logger.info(f"Scanning for unprocessed items since timestamp >= {five_min_ago} ({time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(five_min_ago))} UTC)")

        #Query for for records
        filter_expression = Or(
            Attr("processed").eq(False),
            (Attr("classification_complete").eq(True) & Attr("notify_pending").eq(True))
        ) & Attr("time_stamp").gte(five_min_ago)

        # Scan unprocessed items OR newly classified items pending notificaiton
        items = []
        response = table.scan(
            FilterExpression=filter_expression)
        items.extend(response.get("Items",[]))
        logger.info(f"Initial scan returned {len(response.get('Items', []))} items")
    except Exception as e:
        logger.error(f"Intital scan failed: {e}")
        raise e

    # Continuing sacn for more matching items
    while "LastEvaluatedKey" in response:
        try:
            logger.info("Continuing scan for more items...")
            response = table.scan(
                FilterExpression=filter_expression,
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
    
    #Creates message to account for images uploaded and classified within 5 min window
    uploaded_images_lines = []
    classified_images_lines = []

    for i in items:
        line = f"  - {i['bucket_name']}/{i['object_key']}"
        if i.get("classification_complete") and "predictions" in i:
            line += f" | Predictions: {i['predictions']}"
        if i.get("processed") is False:
            uploaded_images_lines.append(line)
        if i.get("classification_complete") and i.get("notify_pending"):
            classified_images_lines.append(line)
    
    # setting up lines in email
    message_lines = []
    if uploaded_images_lines:
        message_lines.append(f"New uploads ({len(uploaded_images_lines)} images):")
        message_lines.extend(uploaded_images_lines)
    if classified_images_lines:
        message_lines.append(f"\nNewly classified images ({len(classified_images_lines)} images):")
        message_lines.extend(classified_images_lines)
        
    message = "\n".join(message_lines)
    logger.info("SNS message prepared:")
    logger.info(message)

    # Publish SNS
    try:
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject="ALERT - Camera Trap Batch Update",
            Message=message
        )
        logger.info("SNS message published successfully.")
    except Exception as e:
        logger.error(f"Error publishing to SNS: {e}", exc_info=True)
        raise e


    # Updating Flags in DynamoDB
    logger.info("Updating items as processed=True")

    try:
        with table.batch_writer() as batch:
            for i in items:
                if i.get("processed") is False:
                    i["processed"] = True
                if i.get("classification_complete") and i.get("notify_pending"):
                    i["notify_pending"] = False
                batch.put_item(Item=i)
        logger.info(f"Updated {len(items)} items in DynamoDB.")
    except Exception as e:
        logger.error("Error updating items to processed=True", exc_info=True)
        raise e
    
    logger.info("Batch notifier Lambda completed successfully.")
    return {"statusCode": 200}