#!/usr/bin/env python3
import argparse, yaml, boto3, os
from sagemaker.pytorch import PyTorchModel
import sagemaker
from botocore.exceptions import ClientError

def load_cfg(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)
    
def make_session(cfg):
    return boto3.Session(
        aws_access_key_id=cfg["aws"]["access_key_id"],
        aws_secret_access_key=cfg["aws"]["secret_access_key"],
        region_name=cfg["aws"]["region"]
    )

def deploy_model (cfg, auth):
    endpoint_name = cfg["sagemaker"]["endpoint_name"]
    model_path = cfg["sagemaker"]["model_data_s3"]
    role_arn = cfg["sagemaker"]["role_arn"]
    framework_version = cfg["sagemaker"]["framework_version"]
    py_version = cfg["sagemaker"]["py_version"]
    instance_type = cfg["sagemaker"]["instance_type"]
    entry_point ="inference.py"

    session = make_session(auth)
    sm_session =sagemaker.Session(boto_session=session)
    
    
    pytorch_model = PyTorchModel(
        model_data=model_path,
        role=role_arn,
        entry_point=entry_point,
        framework_version=framework_version,
        py_version=py_version,
        predictor_cls=None,
        sagemaker_session=sm_session
    )

    print(f"Deploying endpoint {endpoint_name}...")
    predictor = pytorch_model.deploy(
        initial_instance_count=1,
        instance_type=instance_type,
        endpoint_name=endpoint_name
    )

    print(f"[SUCCESS] Endpoint deployed: {endpoint_name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="stage2_yolov8/config.yaml")
    ap.add_argument("--auth", default="aws_auth.yaml")
    args = ap.parse_args()

    auth = load_cfg(args.auth)
    cfg = load_cfg(args.config)

    deploy_model(cfg,auth)

if __name__ == "__main__":
    main()
