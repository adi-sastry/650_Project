import json
import boto3
import csv
import io
import re

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("image_event")

METADATA = {}
METADATA_BUCKET = "wildlife-metadata"
METADATA_KEY = "observations.csv"

def load_metadata():
    """
    Loads the CSV from S3 on first Lambda cold start only.
    Builds a dictionary: id -> metadata fields.
    """
    global METADATA
    if METADATA:
        return METADATA  

    logger.info("Loading metadata CSV from S3...")

    obj = s3.get_object(Bucket=METADATA_BUCKET, Key=METADATA_KEY)
    csv_data = obj["Body"].read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(csv_data))

    MAX_ROWS = 500  
    count = 0

    for row in reader:
        if count >= MAX_ROWS:
            logger.warning(f"Loaded only first {MAX_ROWS} metadata rows (demo mode).")
            break

        obs_id = row["id"]
        METADATA[obs_id] = {
            "lat": safe_float(row.get("latitude")),
            "long": safe_float(row.get("longitude")),
            "positional_accuracy": safe_float(row.get("positional_accuracy")),
            "elevation": safe_float(row.get("elevation")),
            "image_capture_time": row.get("local_time_observed_at"),
        }
    
        count += 1


    logger.info(f"Loaded {len(METADATA)} metadata records.")
    return METADATA

def safe_float(x):
    try:
        return float(x)
    except:
        return None

def extract_numeric_id(s3_key):
    """
    Extract numeric prefix (e.g. 3594728 from 3594728_a.jpg)
    """
    match = re.match(r".*?([0-9]+)", s3_key)
    return match.group(1) if match else None


def lambda_handler(event, context):
    logger.info(f"Lambda invoked with event: {json.dumps(event)}")

    metadata_index = load_metadata()

    for record in event["Records"]:
        s3_info = record["s3"]
        bucket = s3_info["bucket"]["name"]
        key = s3_info["object"]["key"]

        logger.info(f"Processing file: s3://{bucket}/{key}")

        numeric_id = extract_numeric_id(key)

        if not numeric_id:
            logger.warning(f"Could not extract ID from filename: {key}")
            continue

        logger.info(f"Extracted ID {numeric_id} — checking metadata…")

        meta = metadata_index.get(numeric_id)

        if meta:
            logger.info(f"Metadata found for {numeric_id}: {meta}")
        else:
            logger.warning(f"No metadata found for ID {numeric_id}, inserting basic record.")
            meta = {}

        item = {
            "event_id": context.aws_request_id,
            "bucket_name": bucket,
            "object_key": key,
            "time_stamp": int(context.get_remaining_time_in_millis()),

        
            "lat": meta.get("lat"),
            "long": meta.get("long"),
            "positional_accuracy": meta.get("positional_accuracy"),
            "elevation": meta.get("elevation"),
            "image_capture_time": meta.get("image_capture_time"),
            "raw_metadata": meta,

            "processed": False,
            "classification_complete": False,
            "notify_pending": False,
        }

        table.put_item(Item=item)
        logger.info(f"Inserted item into DynamoDB: {item}")

    logger.info("Ingestion Logger Lambda function execution completed")
    return {"status": "ok"}
