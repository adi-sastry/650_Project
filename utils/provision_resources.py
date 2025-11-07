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

def create_database(table_name, attribute_def, key_schema):
    dynamodb = boto3.client("dynamodb")

    dynamodb.create_table(
        TableName = table_name,
        AttributeDefinitions= attribute_def,
        KeySchema=key_schema,
        BillingMode = "PAY_PER_REQUEST"
    )

def create_eventBridge_rule(name, rate):
    events_client = boto3.client("events")

    rule = events_client(
        Name=name,
        ScheduleExpression=rate,
        State="ENABLED"
    )
    
    return rule

def give_eventBridge_permission(func_name, statement_id, action, principal, rule):
    lambda_client = boto3.client("lambda")
    lambda_client.add_permission(
        FunctionName=func_name,  # Lambda function name in AWS
        StatementId=statement_id,
        Action=action,
        Principal=principal,
        SourceArn=rule["RuleArn"]
    )

def attach_lambda_targets(rule_name, func_arn):
    events_client = boto3.client("events")
    events_client.put_targets(
        Rule = rule_name,
        Targets= [
            {
                "Id": "Target0",
                "Arn": func_arn
            }
        ]
    )

def deploy_lambda_batch_notifier(role_arn):
    lambda_client = boto3.client("lambda", region_name ="us-east-1")

    with open("batch_notifier.zip", "rb") as f:
        zipped_code = f.read()
    
    response = lambda_client.create_function(
        FunctionName="BatchNotifier",
        Runtime="python3.11",
        Role=role_arn,
        Handler="batch_notifer.lambda_handler",
        Code={"ZipFile": zipped_code},
        Timeout=30,
        MemorySize=128
    )

    print(response)
    return(response['FunctionArn'])

def create_iam_lambda_role():
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }

    iam =get_iam_client()
    role_name = "lambda-execution-role"

    response = iam.create_role(
        RoleName = role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),        
        Description="IAM role for Lambda to access AWS services like CloudWatch, S3, etc."
        )
    
    iam.attach_role_policy(
        RoleName = role_name,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"        
    )
    
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
    )

    iam.attach_role_policy(
    RoleName=role_name,
    PolicyArn="arn:aws:iam::aws:policy/AmazonSNSFullAccess"
    )

    print("Created role ARN:", response["Role"]["Arn"])

    return(response["Role"]["Arn"])