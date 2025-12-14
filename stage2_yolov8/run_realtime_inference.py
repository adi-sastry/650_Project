#!/usr/bin/env python3
import argparse
import json
import time
import yaml
import boto3

from datetime import datetime
from urllib.parse import urlparse

from botocore.config import Config
from botocore.exceptions import ReadTimeoutError, ClientError


def load_cfg(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def make_session(cfg):
    return boto3.Session(
        aws_access_key_id=cfg["aws"]["access_key_id"],
        aws_secret_access_key=cfg["aws"]["secret_access_key"],
        region_name=cfg["aws"]["region"],
    )


def parse_s3(uri: str):
    p = urlparse(uri)
    return p.netloc, p.path.lstrip("/")


def main():
    ap = argparse.ArgumentParser()
    # NOTE: when running from project root, we pass these explicitly
    ap.add_argument("--config", default="stage2_yolov8/config.yaml")
    ap.add_argument("--auth", default="aws_auth.yaml")
    args = ap.parse_args()

    # 1. AWS session + high-timeout runtime client
    auth = load_cfg(args.auth)
    session = make_session(auth)

    # Increase read timeout so YOLO cold-start has enough time
    runtime_config = Config(
        read_timeout=300,      # up to 5 minutes
        connect_timeout=10,
        retries={"max_attempts": 3, "mode": "standard"},
    )

    smrt = session.client("sagemaker-runtime", config=runtime_config)
    s3 = session.client("s3")
    ddb = session.client("dynamodb")

    cfg = load_cfg(args.config)

    csv_path = cfg["io"]["images_csv"]
    endpoint = cfg["sagemaker"]["endpoint_name"]
    table = cfg["dynamodb"]["table_name"]
    score_thresh = cfg["io"]["score_threshold"]

    # 2. Load image list
    with open(csv_path, "r") as f:
        uris = [line.strip() for line in f if line.strip()]

    max_images = cfg["io"].get("max_images")
    if max_images is not None:
        uris = uris[: int(max_images)]

    print(f"[INFO] Found {len(uris)} images to process")

    # 3. Process each image with retry on timeout / model errors
    for i, uri in enumerate(uris, 1):
        print(f"[{i}/{len(uris)}] → {uri}")
        bucket, key = parse_s3(uri)

        # Download image from S3
        obj = s3.get_object(Bucket=bucket, Key=key)
        img_bytes = obj["Body"].read()

        # Retry logic around invoke_endpoint
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                resp = smrt.invoke_endpoint(
                    EndpointName=endpoint,
                    ContentType="application/x-image",
                    Body=img_bytes,
                )
                # If we get here, call succeeded
                break

            except ReadTimeoutError as e:
                print(
                    f"  [WARN] ReadTimeout on attempt {attempt}/{max_attempts} "
                    f"for {key}: {e}"
                )
                if attempt == max_attempts:
                    print("  [ERROR] Giving up on this image due to repeated timeouts.\n")
                    resp = None
                    break
                # small backoff
                time.sleep(5 * attempt)

            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "Unknown")
                print(
                    f"  [WARN] ClientError ({code}) on attempt {attempt}/{max_attempts} "
                    f"for {key}"
                )
                if attempt == max_attempts:
                    print("  [ERROR] Giving up on this image due to repeated ClientErrors.\n")
                    resp = None
                    break
                time.sleep(5 * attempt)

        # If all attempts failed, skip storing to DynamoDB but continue loop
        if resp is None:
            continue

        # 4. Parse model response
        body = resp["Body"].read()
        try:
            result = json.loads(body)
        except json.JSONDecodeError:
            print("  [ERROR] Could not decode JSON from model response, skipping.\n")
            continue

        dets = [
            d for d in result.get("detections", [])
            if d.get("confidence", 0.0) >= score_thresh
        ]

        # 5. Write to DynamoDB
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).isoformat()
        item = {
            "image_name": {"S": key.split("/")[-1]},
            "timestamp": {"S": timestamp},
            "s3_uri": {"S": uri},
            "detections": {"S": json.dumps(dets)},
            "raw_response": {"S": json.dumps(result)},
        }

        ddb.put_item(TableName=table, Item=item)
        print(f"  Saved {len(dets)} detections → DynamoDB\n")


        # Stage 3: Alert when detections exist
        if len(dets) > 0:
            sns = session.client("sns")
            topic_arn = cfg.get("sns", {}).get("topic_arn")
            if topic_arn:
                message = {
                    "image_name": key.split("/")[-1],
                    "timestamp": timestamp,
                    "s3_uri": uri,
                    "num_detections": len(dets),
                    "detections": dets[:5],
                }
        sns.publish(
            TopicArn=topic_arn,
            Subject="Wildlife Detection Alert",
            Message=json.dumps(message, indent=2),
        )
        print("  [ALERT] Sent SNS email\n")
        #   else:
        #     print("  No detections → no alert\n")




        # tiny sleep to not hammer the endpoint
        time.sleep(0.1)

    print("[DONE] All images processed (with retries).")


if __name__ == "__main__":
    main()
