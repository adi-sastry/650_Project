import boto3

def delete_all_objects_in_s3(bucket_name,region="us-east-1"):
    s3=boto3.resource("s3",region_name = region)
    bucket = s3.Bucket(bucket_name)
    bucket.objects.all().delete()
    print(f"Deleted all objects in bucket {bucket_name}")

def delete_s3_bucket(bucket_name,region="us-east-1"):
    s3_client = boto3.client("s3", region_name=region)
    s3_client.delete_bucket(Bucket=bucket_name)
    print(f"Deleted bucket {bucket_name}")

def delete_iam_policy(iam_client, policy_arn, user_name):
    iam_client.detach_user_policy(UserName=user_name, PolicyArn=policy_arn)
    iam_client.delete_policy(PolicyArn=policy_arn)
