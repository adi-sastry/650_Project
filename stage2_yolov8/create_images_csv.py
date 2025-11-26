#!/usr/bin/env python3
import argparse, os, yaml, boto3

def load_cfg(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def make_session(cfg):
    return boto3.Session(
        aws_access_key_id=cfg["aws"]["access_key_id"],
        aws_secret_access_key=cfg["aws"]["secret_access_key"],
        region_name=cfg["aws"]["region"]
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="stage2_yolov8/config.yaml")
    ap.add_argument("--auth", default="aws_auth.yaml")
    args = ap.parse_args()

    auth = load_cfg(args.auth)
    session = make_session(auth)
    s3 = session.client("s3")

    cfg = load_cfg(args.config)
    bucket = cfg["s3"]["bucket"]
    prefix = cfg["s3"]["images_prefix"]
    csv_path = cfg["io"]["images_csv"]
    max_images = cfg["io"].get("max_images")

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    exts = (".jpg", ".jpeg", ".png")
    count = 0

    with open(csv_path, "w") as f:
        for page in pages:
            for obj in page.get("Contents", []):
                key = obj["Key"].lower()
                if key.endswith(exts):
                    f.write(f"s3://{bucket}/{obj['Key']}\n")
                    count += 1
                    if max_images and count >= max_images:
                        break
            if max_images and count >= max_images:
                break

    print(f"[INFO] Wrote {count} paths → {csv_path}")

if __name__ == "__main__":
    main()
