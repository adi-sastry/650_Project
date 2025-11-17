import boto3
import yaml
from botocore.exceptions import ClientError
import time

#load aws credentials and clients using credentials
def load_aws_credentials(config_path: str= 'aws_auth.yaml') -> dict:
    with open(config_path, 'r') as f:
        aws_config = yaml.safe_load(f)
    return aws_config['aws']

def get_aws_client(service_name: str):
    aws_credentials = load_aws_credentials()
    return boto3.client(
        service_name.lower(),  # boto3 service names are lowercase
        aws_access_key_id=aws_credentials['access_key_id'],
        aws_secret_access_key=aws_credentials['secret_access_key'],
        region_name=aws_credentials['region']
    )

def delete_all_objects_in_s3(bucket_name,region="us-east-1"):
    s3=boto3.resource("s3",region_name = region)
    bucket = s3.Bucket(bucket_name)
    bucket.objects.all().delete()
    print(f"Deleted all objects in bucket {bucket_name}")

def delete_s3_bucket(bucket_name):
    s3_client = get_aws_client("s3")
    s3_client.delete_bucket(Bucket=bucket_name)
    print(f"Deleted bucket {bucket_name}")

""" def delete_iam_policy(iam_client, policy_arn, user_name):
    iam_client.detach_user_policy(UserName=user_name, PolicyArn=policy_arn)
    iam_client.delete_policy(PolicyArn=policy_arn) """

def delete_iam_policy(policy_arn, user_name):
    iam_client = get_aws_client("iam")
    iam_client.detach_user_policy(UserName=user_name, PolicyArn=policy_arn)
    iam_client.delete_policy(PolicyArn=policy_arn)

def delete_dynamodb_table(table_name = str, region ="us-east-1"):
    dynamodb = get_aws_client("dynamodb")
    
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

def delete_lambda(function_name):
    lambda_client = get_aws_client("lambda")

    try:
        response=lambda_client.delete_function(
            FunctionName = function_name
        )
        
        print(f"Lambda function '{function_name}' deleted successfully.")
        return response
    
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"Lambda function '{function_name}' does not exist.")
    except ClientError as e:
        print(f"Error deleting Lambda: {e}")

def delete_sns_topic(topic_arn: str):
    sns = get_aws_client("sns")

    try:
        response = sns.delete_topic(
            TopicArn = topic_arn
        )
        print(f"SNS topic '{topic_arn}' deleted successfully.")
        return response
    
    except sns.exceptions.NotFoundException:
        print(f"SNS topic '{topic_arn}' does not exist.")
    except ClientError as e:
        print(f"Error deleting SNS topic: {e}")
        raise

def delete_eventbridge_rule(rule_name):
    events = get_aws_client("events")

    try:
        targets = events.list_targets_by_rule(Rule=rule_name)

        if targets.get("Targets"):
            target_ids = [t["Id"] for t in targets["Targets"]]
            events.remove_targets(Rule=rule_name, Ids=target_ids)
            print(f"Removed targets from rule '{rule_name}': {target_ids}")
        
        events.delete_rule(Name=rule_name, Force=True)
        print(f"EventBridge rule '{rule_name}' deleted successfully.")

    except Exception as e:
        print(f"Error deleting EventBridge rule: {e}")

def delete_cw_log_group(function_name):
    logs= get_aws_client("logs")
    log_group_name = f"/aws/lambda/{function_name}"

    try:
        logs.delete_log_group(logGroupName=log_group_name)
        print(f"Deleted log group: {log_group_name}")
    except Exception as e:
        print(f"Error deleting log group {log_group_name}: {e}")

def delete_iam_role(role_name: str):
    iam_client = get_aws_client("iam")
    
    try:
        print(f"Cleaning up role: {role_name}")

        # Deleting any managed policies
        attached = iam_client.list_attached_role_policies(RoleName=role_name)
        for policy in attached["AttachedPolicies"]:
            iam_client.detach_role_policy(RoleName=role_name,PolicyArn=policy["PolicyArn"])
            print(f"Detached policy: {policy['PolicyArn']}")
        
        # Deleting any inline policies
        inline = iam_client.list_role_policies(RoleName=role_name)
        for policy_name in inline["PolicyNames"]:
            iam_client.delete_role_policy(RoleName=role_name,PolicyName=policy_name)
            print(f"Deleted inline policy: {policy_name}")

        # Deleting any Instance Profiles
        profiles = iam_client.list_instance_profiles_for_role(RoleName=role_name)
        for profile in profiles["InstanceProfiles"]:
            iam_client.remove_role_from_instance_profile(InstanceProfileName=profile["InstanceProfileName"],RoleName=role_name)
            print(f"Removed from instance profile: {profile['InstanceProfileName']}")
        
        # Delete Role
        iam_client.delete_role(RoleName=role_name)
        print(f"Role deleted: {role_name}")

    except Exception as e:
        print(f"Failed to delete role {role_name}: {e}")