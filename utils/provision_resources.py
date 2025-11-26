import boto3
import json
import time
import yaml
from botocore.exceptions import ClientError

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

#Create S3 Bucket
def create_s3_bucket(bucket_name:str, region:str= "us-east-1")-> None:
    s3 = get_aws_client("s3")

    print(f"Creating S3 bucket: {bucket_name}")
    if region == "us-east-1":
        s3.create_bucket(Bucket=bucket_name)
    else:
        s3.create_bucket(Bucket = bucket_name,
                        CreateBucketConfiguration={"LocationConstraint": region}
         )
    print(f"Bucket {bucket_name} created successfully in {region}")
    time.sleep(5)

#Create IAM Policy to be used as template for specific policies (like read-write, or read only, etc.)

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
    iam= get_aws_client("iam")
    policy_name = f"{bucket_name}-policy"
    actions = ["s3:GetObject", "s3:PutObject"]
    
    print(f"Creating IAM policy: {policy_name}")

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

# Create DynamoDB Database

def create_database(table_name, attribute_def, key_schema):
    dynamodb = get_aws_client("dynamodb")
    dynamodb.create_table(
        TableName = table_name,
        AttributeDefinitions= attribute_def,
        KeySchema=key_schema,
        BillingMode = "PAY_PER_REQUEST"
    )

# Creates a Role for executing Lambda Functions

def create_iam_lambda_role(iam_client):
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

    role_name = "lambda-execution-role"

    response = iam_client.create_role(
        RoleName = role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),        
        Description="IAM role for Lambda to access AWS services like CloudWatch, S3, etc."
        )
    
    policies = [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess",
        "arn:aws:iam::aws:policy/AmazonSNSFullAccess"
        ]
    
    # Attaches policies above to new lambda role
    for policy_arn in policies:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        time.sleep(15)

    #wait_for_iam_role_propagation(iam_client,role_name, timeout=120)
    role_arn = response["Role"]["Arn"]
    wait_for_role_assumable()
    print(f"Role ready: {role_arn}")
    return role_arn

# Function that waits for role to become fully assumable to actually deploy lambdas. Creates a fake function to test against

def wait_for_role_assumable(timeout=120, delay=5):
    lambda_client = get_aws_client("lambda")
    start = time.time()
    fake_function = "FakeLambdaRoleAssumeTest"
    print(f"Waiting for role to become assumable by Lambda...")
    
    while time.time() - start < timeout:
        try:
            lambda_client.get_function(FunctionName=fake_function)
        except lambda_client.exceptions.ResourceNotFoundException:
            # This triggers Lambda's trust-policy check internally
            try:
                lambda_client.get_function_configuration(FunctionName=fake_function)
            except lambda_client.exceptions.ResourceNotFoundException:
                # Role is actually assumable (meaning trust policy OK), function just doesn't exist
                print("Role is assumable by Lambda.")
                return
            except lambda_client.exceptions.InvalidParameterValueException as e:
                if "cannot be assumed" in str(e):
                    print("Role not yet assumable, waiting...")
                else:
                    print("Role assumable (other error).")
                    return
        except lambda_client.exceptions.InvalidParameterValueException as e:
            if "cannot be assumed" in str(e):
                print("Role not yet assumable, waiting...")
            else:
                print("Role assumable (other error).")
                return
        except Exception as e:
            print(f"Unexpected error: {e}")
            # assuming role is ready if we hit unknown errors
            return
        time.sleep(delay)
    raise TimeoutError("Role did not become assumable by Lambda")

# attaches PassRole to current user so that they can pass the lambda execution role to other AWS services.
# Done using an inline polcy so that it is embedded in the current user

def attach_passrole_policy(user_name: str):
    iam= get_aws_client("iam")
    sts= get_aws_client("sts")
    account_id = sts.get_caller_identity()["Account"]
    region = load_aws_credentials()['region']

    policy_document = {
    "Version": "2012-10-17",
    "Statement": [
        {
        "Effect": "Allow",
        "Action": [
            "iam:CreateRole",
            "iam:AttachRolePolicy",
            "iam:GetRole",
            "iam:PassRole",
            "sts:AssumeRole" 
        ],
        "Resource": f"arn:aws:iam::{account_id}:role/lambda-execution-role"
        },
        {
        "Effect": "Allow",
        "Action": [
            "lambda:CreateFunction",
            "lambda:UpdateFunctionConfiguration",
            "lambda:InvokeFunction"
        ],
        "Resource": f"arn:aws:lambda:{region}:{account_id}:function/*"
        }
    ]
    }

    try:
        iam.put_user_policy(
            UserName=user_name,
            PolicyName='LambdaRoleCreationPolicy',
            PolicyDocument=json.dumps(policy_document)
        )
        print(f"Attached in-line policy 'LambdaRoleCreationPolicy' to user: {user_name}")
    except ClientError as e:
        print(f"Failed to attach policy: {e}")

# Deploys Ingestion Logger Lambda Function for Stage 1
# logs the ingestion of images into S3 into a database

def deploy_lambda_ingestion_logger(role_arn,table_name):
    lambda_client = get_aws_client("lambda")

    with open("ingestion_logger.zip", "rb") as f:
        zipped_code = f.read()
    
    response = lambda_client.create_function(
        FunctionName="IngestionLogger",
        Runtime="python3.12",
        Role=role_arn,
        Handler="ingestion_logger.lambda_handler",
        Code={"ZipFile": zipped_code},
        Timeout=30,
        MemorySize=128,
        Environment ={
            "Variables": {
                "TABLE_NAME": table_name
            }
        }
    )

    print(response)
    return(response['FunctionName'],response['FunctionArn'])

def create_s3_lambda_trigger(bucket_name, function_arn, function_name):
    s3 = get_aws_client("s3")
    sts =get_aws_client("sts")
    account_id = sts.get_caller_identity()["Account"]
    lambda_client = get_aws_client("lambda")

    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId=f"S3InvokePermission",
        Action="lambda:InvokeFunction",
        Principal="s3.amazonaws.com",
        SourceArn=f"arn:aws:s3:::{bucket_name}",
        SourceAccount=account_id
        )
    
    time.sleep(5)
    
    notification_config = {
        "LambdaFunctionConfigurations": [
            {
                "LambdaFunctionArn": function_arn,
                "Events": ["s3:ObjectCreated:*"]
            }
        ]
    }

    s3.put_bucket_notification_configuration(
        Bucket=bucket_name,
        NotificationConfiguration=notification_config
    )
    print(f"S3 bucket {bucket_name} is now configured to invoke Lambda '{function_name}'")

#Create SNS Topic

def create_sns_topic(topic_name):
    sns = get_aws_client("sns")
    response = sns.create_topic(Name=topic_name)
    topic_arn = response["TopicArn"]
    print(f"SNS topic created:{topic_arn}")

    return topic_arn

def add_email_to_sns(topic_arn, email_address):
    sns = get_aws_client("sns")
    response=sns.subscribe(
        TopicArn = topic_arn,
        Protocol="email",
        Endpoint=email_address
    )

    print(f"Email subscription created. Account holder of {email_address} must confirm subscription")

# Deploys Batch notifier Lambda Function for Stage 1
# Notifies users the images that were uploaded to bucket within a 5 min window

def deploy_lambda_batch_notifier(role_arn, sns_topic_arn, table_name):
    lambda_client = get_aws_client("lambda")

    with open("batch_notifier.zip", "rb") as f:
        zipped_code = f.read()
    
    response = lambda_client.create_function(
        FunctionName="BatchNotifier",
        Runtime="python3.12",
        Role=role_arn,
        Handler="batch_notifier.lambda_handler",
        Code={"ZipFile": zipped_code},
        Timeout=30,
        MemorySize=128,
        Environment ={
            "Variables": {
                "SNS_TOPIC_ARN":sns_topic_arn,
                "TABLE_NAME": table_name
            }
        }
        )

    print(response)
    return(response['FunctionName'],response['FunctionArn'])



#Creates EventBridge Rule

def create_eventBridge_rule(name, rate):
    events_client = get_aws_client("events")
    rule = events_client.put_rule(
        Name=name,
        ScheduleExpression=rate,
        State="ENABLED"
    )
    return rule

#Gives the EventBridge Role permissions to invoke a Lambda function

def give_eventBridge_permission(lambda_func_name, statement_id, action, principal, rule):
    lambda_client = get_aws_client("lambda")
    lambda_client.add_permission(
        FunctionName=lambda_func_name,
        StatementId=statement_id,
        Action=action,
        Principal=principal,
        SourceArn=rule["RuleArn"]
    )

# Attaches the lambda target to the EventBridge Rule

def attach_lambda_targets(rule_name, func_arn):
    events_client = get_aws_client("events")
    events_client.put_targets(
        Rule = rule_name,
        Targets= [
            {
                "Id": "Target0",
                "Arn": func_arn
            }
        ]
    )







