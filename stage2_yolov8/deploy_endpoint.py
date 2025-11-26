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
    ap.add_argument("--config", default="stage2_yolov8/config.yaml")
    ap.add_argument("--auth", default="aws_auth.yaml")
    args = ap.parse_args()

    auth = load_cfg(args.auth)
    session = make_session(auth)
    sm_session = sagemaker.Session(boto_session=session)

    cfg = load_cfg(args.config)
    sagemaker_cfg = cfg["sagemaker"]
    endpoint_name = sagemaker_cfg["endpoint_name"]

    model_path = sagemaker_cfg["model_data_s3"]

    pytorch_model = PyTorchModel(
        model_data=model_path,
        role=sagemaker_cfg["role_arn"],
        entry_point="inference.py",
        source_dir="stage2_yolov8",
        framework_version=sagemaker_cfg["framework_version"],
        py_version=sagemaker_cfg["py_version"],
        predictor_cls=None,
        sagemaker_session=sm_session
    )

    predictor = pytorch_model.deploy(
        initial_instance_count=1,
        instance_type=sagemaker_cfg["instance_type"],
        endpoint_name=endpoint_name
    )

    print("[SUCCESS] Endpoint deployed:", endpoint_name)

if __name__ == "__main__":
    main()
