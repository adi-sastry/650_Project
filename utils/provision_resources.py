import boto3
import json
import time

#Create S3 Bucket Function

def create_s3_bucket(bucket_name:str, region:str= "us-east-1")-> None:
    s3 = boto3.client("s3", region_name = region)

    print(f"Creating S3 bucket: {bucket_name}")
    if region == "us-east-1":
        s3.create_bucket(Bucket=bucket_name)
    else:
        s3.create_bucket(Bucket = bucket_name,
                        CreateBucketConfiguration={"LocationConstraint": region}
         )
    print(f"Bucket {bucket_name} created successfully in {region}")
    time.sleep(5)

def get_iam_client():
    return boto3.client("iam")

#Create IAM Policy Function to be used as template for specific policies (like read-write, or read only, etc.)

def create_iam_policy(iam_client, policy_name, user_name, policy_document, description=""):
    response = iam_client.create_policy(
        PolicyName = policy_name,
        PolicyDocument = json.dumps(policy_document),
        Description = description
    )

    policy_arn = response["Policy"]["Arn"]
    iam_client.attach_user_policy(UserName = user_name, PolicyArn = policy_arn)
    return policy_arn

#Attach IAM Polcy to user
def attach_policy_user (iam_client, policy_arn, user_name):
    iam_client.attach_user_policy(UserName=user_name, PolicyArn=policy_arn)

#IAM Policy for from-camera-trap bucket
def create_image_camera_trap_policy_for_bucket(bucket_name: str, user_name:str, allow_delete: bool = True):
    iam = boto3.client("iam")
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


