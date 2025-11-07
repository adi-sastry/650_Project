import boto3
from botocore.exceptions import ClientError
import time

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

def delete_dynamodb_table(table_name = str, region ="us-east-1"):
    dynamodb = boto3.client("dynamodb", region_name=region)
    
    try:

        existing_tables = dynamodb.list_tables()['TableNames']
        if table_name not in existing_tables:
            print ("DynamoDB table '{table_name}' not found, nothing to delete.")
            return
        
        waiter_active = dynamodb.get_waiter("table_exists")
        waiter_active.wait(TableName=table_name)      

        print(f"Deleting DynamoDB table '{table_name}' ...")
        dynamodb.delete_table(TableName=table_name)

        waiter = dynamodb.get_waiter("table_not_exists")
        waiter.wait(TableName = table_name)
        print(f"DynamoDB table '{table_name}' deleted successfully.")
    
    except ClientError  as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"Table '{table_name}' not found.")
        elif e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Table '{table_name}' is still being created — retrying shortly...")
            time.sleep(10)
            delete_dynamodb_table(table_name, region) 
        else:
            print(f"Error deleteing DynamoDB Table: {e}")