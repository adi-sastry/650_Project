#!/usr/bin/env python3
import argparse, yaml, boto3, os
from sagemaker.pytorch import PyTorchModel
import sagemaker

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
    ap.add_argument("--config", required=True)
    ap.add_argument("--auth", required=True)
    args = ap.parse_args()

    # load authentication
    auth = load_cfg(args.auth)
    session = make_session(auth)
    sm_session = sagemaker.Session(boto_session=session)

    # load config
    cfg = load_cfg(args.config)
    sm_cfg = cfg["sagemaker"]

    model_path = sm_cfg["model_data_s3"]
    role_arn = sm_cfg["role_arn"]
    endpoint_name = sm_cfg["endpoint_name"]

        # VERY IMPORTANT — use the small 'serve' folder, not the whole project
    script_dir = os.path.dirname(os.path.abspath(__file__))   # ...\stage2_yolov8
    source_dir = os.path.join(script_dir, "serve")            # ...\stage2_yolov8\serve
    print("Using source directory:", source_dir)

    pytorch_model = PyTorchModel(
        model_data=model_path,
        role=role_arn,
        entry_point="inference.py",  # this file lives inside 'serve'
        source_dir=source_dir,
        framework_version=sm_cfg["framework_version"],
        py_version=sm_cfg["py_version"],
        sagemaker_session=sm_session
    )


    predictor = pytorch_model.deploy(
        initial_instance_count=1,
        instance_type=sm_cfg["instance_type"],
        endpoint_name=endpoint_name
    )

    print("\n[SUCCESS] Endpoint deployed:", endpoint_name)

if __name__ == "__main__":
    main()
