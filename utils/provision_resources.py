import boto3
import json
import time
import yaml
from botocore.exceptions import ClientError
from read_yaml import read_yaml
#Create S3 Bucket Function

def load_aws_credentials(config_path: str= 'aws_auth.yaml') -> dict:
    with open(config_path, 'r') as f:
        aws_config = yaml.safe_load(f)
    return aws_config['aws']

def get_s3_iam_client():
    aws_credentials = load_aws_credentials()
    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_credentials['access_key_id'],
        aws_secret_access_key=aws_credentials['secret_access_key'],
        region_name=aws_credentials['region']
    )

    iam = boto3.client(
        "iam",
        aws_access_key_id=aws_credentials['access_key_id'],
        aws_secret_access_key=aws_credentials['secret_access_key'],
        region_name=aws_credentials['region']
    )
    return s3, iam

def create_s3_bucket(bucket_name:str, region:str= "us-east-1")-> None:
    s3,_ = get_s3_iam_client()

    print(f"Creating S3 bucket: {bucket_name}")
    if region == "us-east-1":
        s3.create_bucket(Bucket=bucket_name)
    else:
        s3.create_bucket(Bucket = bucket_name,
                        CreateBucketConfiguration={"LocationConstraint": region}
         )
    print(f"Bucket {bucket_name} created successfully in {region}")
    time.sleep(5)


#Create IAM Policy Function to be used as template for specific policies (like read-write, or read only, etc.)

def create_iam_policy(iam_client, policy_name, user_name, policy_document, description=""):
    try:
        response = iam_client.create_policy(
        PolicyName = policy_name,
        PolicyDocument = json.dumps(policy_document),
        Description = description
        )

        policy_arn = response["Policy"]["Arn"]
        print(f"[OK] created New Policy: {policy_name} witrh ARN: {policy_arn}")

    except ClientError as e:
        creds = load_aws_credentials()
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"[WARN] Policy {policy_name} already exists. Retrieving existing policy ARN.")
            acc_id = creds['account_id']
            response = iam_client.get_policy(PolicyArn=f"arn:aws:iam::{acc_id}:policy/{policy_name}")
            policy_arn = response['Policy']['Arn']
        else:
            raise e

    iam_client.attach_user_policy(UserName = user_name, PolicyArn = policy_arn)

    print("-------------")
    print(f'[SUCCESS] Attached Policy: {policy_name} to User: {user_name}')
    print("-------------")
    return policy_arn

#Attach IAM Polcy to user
def attach_policy_user (iam_client, policy_arn, user_name):
    iam_client.attach_user_policy(UserName=user_name, PolicyArn=policy_arn)

#IAM Policy for from-camera-trap bucket
def create_image_camera_trap_policy_for_bucket(bucket_name: str, user_name:str, allow_delete: bool = True):
    _, iam = get_s3_iam_client()
    policy_name = f"{bucket_name}-policy"

    print(f"Creating IAM policy: {policy_name}")
    
    actions = ["s3:GetObject", "s3:PutObject"]

    if allow_delete:
        actions.append("s3:DeleteObject")
    
    policy_doc = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": f"arn:aws:s3:::{bucket_name}"},
            {"Effect": "Allow", "Action": actions, "Resource": f"arn:aws:s3:::{bucket_name}/*"}
        ]
    }

    return create_iam_policy(iam, policy_name, user_name, policy_doc, f"Read/write access to {bucket_name}")


