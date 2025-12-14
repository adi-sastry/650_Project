import os
import json
import boto3
import yaml

ENDPOINT_NAME = "yolov8-camera-trap-endpoint"  # your endpoint name

# ---------- helpers to reuse your aws_auth.yaml ---------- #
def load_cfg(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def make_session(cfg):
    return boto3.Session(
        aws_access_key_id=cfg["aws"]["access_key_id"],
        aws_secret_access_key=cfg["aws"]["secret_access_key"],
        region_name=cfg["aws"]["region"],
    )

def main():
    # 1) Load AWS creds from aws_auth.yaml (same as deploy script)
    auth = load_cfg("aws_auth.yaml")
    session = make_session(auth)
    region = auth["aws"]["region"]

    runtime = session.client("sagemaker-runtime", region_name=region)

    # 2) Folder with validation images (from your config.yaml)
    folder = r".\data\images\species_validate\acinonyx_jubatus"

    if not os.path.isdir(folder):
        raise FileNotFoundError(f"Folder not found: {folder}")

    # 3) Pick the first image file in that folder
    candidates = [
        f for f in os.listdir(folder)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if not candidates:
        raise FileNotFoundError(f"No .jpg/.jpeg/.png images found in {folder}")

    filename = candidates[0]
    image_path = os.path.join(folder, filename)
    print(f"Using test image: {image_path}")

    # 4) Read image bytes
    with open(image_path, "rb") as f:
        body = f.read()

    # 5) Call the SageMaker endpoint
    response = runtime.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType="application/x-image",
        Body=body,
    )

    result = response["Body"].read().decode("utf-8")
    print("\nRaw response from endpoint:")
    print(result)

    # 6) Pretty-print detections if JSON
    try:
        data = json.loads(result)
        print("\nParsed detections:")
        for det in data.get("detections", []):
            print(det)
    except Exception as e:
        print("\nCould not parse JSON response:", e)

if __name__ == "__main__":
    main()
