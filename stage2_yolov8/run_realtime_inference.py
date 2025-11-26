#!/usr/bin/env python3
import argparse, json, time, yaml, boto3
from datetime import datetime
from urllib.parse import urlparse

def load_cfg(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def make_session(cfg):
    return boto3.Session(
        aws_access_key_id=cfg["aws"]["access_key_id"],
        aws_secret_access_key=cfg["aws"]["secret_access_key"],
        region_name=cfg["aws"]["region"]
    )

def parse_s3(uri):
    p = urlparse(uri)
    return p.netloc, p.path.lstrip("/")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="stage2_yolov8/config.yaml")
    ap.add_argument("--auth", default="aws_auth.yaml")
    args = ap.parse_args()

    auth = load_cfg(args.auth)
    session = make_session(auth)
    sm = session.client("sagemaker")
    cfg = load_cfg(args.config)
    s3 = session.client("s3")
    smrt = session.client("sagemaker-runtime")
    ddb = session.client("dynamodb")

    csv_path = cfg["io"]["images_csv"]
    endpoint = cfg["sagemaker"]["endpoint_name"]
    table = cfg["dynamodb"]["table_name"]
    score_thresh = cfg["io"]["score_threshold"]

    with open(csv_path) as f:
        uris = [x.strip() for x in f if x.strip()]

    print(f"[INFO] Found {len(uris)} images")

    for i, uri in enumerate(uris, 1):
        print(f"[{i}/{len(uris)}] → {uri}")
        bucket, key = parse_s3(uri)

        # Download image
        img_bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()

        # Invoke inference
        resp = smrt.invoke_endpoint(
            EndpointName=endpoint,
            ContentType="application/x-image",
            Body=img_bytes
        )
        result = json.loads(resp["Body"].read())
        dets = [
            d for d in result.get("detections", [])
            if d.get("score", 0) >= score_thresh
        ]

        # Prepare DynamoDB item
        timestamp = datetime.utcnow().isoformat() + "Z"
        item = {
            "image_name": {"S": key.split("/")[-1]},
            "timestamp": {"S": timestamp},
            "s3_uri": {"S": uri},
            "detections": {"S": json.dumps(dets)},
            "raw_response": {"S": json.dumps(result)}
        }

        ddb.put_item(TableName=table, Item=item)
        print(f"Saved {len(dets)} detections → DynamoDB\n")

        time.sleep(0.05)

    print("[DONE] All images processed.")

if __name__ == "__main__":
    main()
