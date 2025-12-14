import utils.provision_resources as pr
import utils.clean_up as cu
import src.simulate_image_streaming as simulate_image_streaming
import os
import sys
import yaml

from botocore.exceptions import ClientError


def load_config(config_path: str = 'config.yaml') -> dict:
  with open(config_path, 'r') as f:
    config_data = yaml.safe_load(f)
  return config_data


def delete_resources(cfg: dict, ct_policy_arn: str, topic_arn: str) -> None:
  print("Begining Clean-Up of AWS Reaources...\n")

  #Delete from-camera-trap s3 bucket and IAM policy (Comment out if we want to retain resources)
  cu.delete_all_objects_in_s3(cfg['CAMERA_TRAP']['bucket_name'], cfg['USER_INFO']['region'])
  cu.delete_s3_bucket(cfg['CAMERA_TRAP']['bucket_name'])
  cu.delete_iam_policy(ct_policy_arn, cfg['USER_INFO']['user_name'])
  print(f"Bucket {cfg['CAMERA_TRAP']['bucket_name']} and policy {ct_policy_arn} deleted successfully.\n")

  #deleting image_even table
  cu.delete_dynamodb_table(cfg['IMG_EVENT_TBL']['table_name'])
  print(f"{cfg['IMG_EVENT_TBL']['table_name']} DynamoDB table deleted successfully.\n")

  # deleting eventbridge rules
  cu.delete_eventbridge_rule("IngestionLoggerRule")
  cu.delete_eventbridge_rule("BatchNotifierRule")

  # deleting Cloud Watch Log Groups
  cu.delete_cw_log_group("IngestionLogger")
  cu.delete_cw_log_group("BatchNotifier")

  # deleteing ingestion Logger and Batch notifier lambda functions
  cu.delete_lambda("IngestionLogger")
  cu.delete_lambda("BatchNotifier")

  cu.delete_sns_topic(topic_arn)
  cu.delete_iam_role("lambda-execution-role")


def main() -> None:
  #----------------------------Load Configuration----------------------------#
  cfg = load_config('config.yaml')

  #----------------------------Verifying dataset was downloaded from Kaggle---------------------------#
  marker_path = os.path.join("data", ".download_complete")
  if not os.path.exists(marker_path):
    print("Dataset was not downloaded. Please run the Kaggle download script first.")
    sys.exit(1)
  else:
    print("Dataset is present and is ready to be used. Proceed...")

  #----------------------------Provisioning Resources----------------------------#   
  print("Begining creation of AWS Reaources...\n")

  #================================ Stage 1 Resources ================================#
  print("Provisioning Stage 1 AWS Reaources...\n")
 
  #Provisioning from-camera-trap S3 Bucket and Policy
  pr.create_s3_bucket(cfg['CAMERA_TRAP']['bucket_name'], cfg['USER_INFO']['region'])

  ct_policy_arn = pr.create_image_camera_trap_policy_for_bucket(
    cfg['CAMERA_TRAP']['bucket_name'],
    cfg['USER_INFO']['user_name'],
    cfg['CAMERA_TRAP']['allow_delete']
  )
 
  iam_client = pr.get_aws_client("iam")
  pr.attach_policy_user(iam_client, ct_policy_arn, cfg['USER_INFO']['user_name'])
  print(f"Bucket {cfg['CAMERA_TRAP']['bucket_name']} and policy {ct_policy_arn} created successfully.\n")

  #Creating dynamoDB table to store metadata of upload (timestamp, file_name, processed flag)
  attribute_definitions = [
    {"AttributeName": attr["attributeName"], "AttributeType": attr["attributeType"]}
    for attr in cfg['IMG_EVENT_TBL']['attr_def']
  ]
  Key_schema = [
    {"AttributeName": key["attributeName"], "KeyType": key["keyType"]}
    for key in cfg['IMG_EVENT_TBL']['key_schema']
  ]

  # Handle case where table already exists (ResourceInUseException)
  try:
    pr.create_database(cfg['IMG_EVENT_TBL']['table_name'], attribute_definitions, Key_schema)
    print(f" {cfg['IMG_EVENT_TBL']['table_name']} DynamoDB table created successfully.\n")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
      print(f"DynamoDB table {cfg['IMG_EVENT_TBL']['table_name']} already exists. Skipping creation.\n")
    else:
      # Any other error, re-raise so you see it
      raise
 
  #Setting up Lambda Functions and EventBridge Rules
  try:
    lambda_role_iam_arn = pr.create_iam_lambda_role(iam_client)
    print("Created new IAM role: lambda-execution-role")
  except ClientError as e:
    if e.response["Error"]["Code"] == "EntityAlreadyExists":
      print("IAM role lambda-execution-role already exists. Using existing role ARN.")
      existing_role = iam_client.get_role(RoleName="lambda-execution-role")
      lambda_role_iam_arn = existing_role["Role"]["Arn"]
    else:
      # Any other error, re-raise so you can see it
      raise

  pr.attach_passrole_policy(cfg['USER_INFO']['user_name'])
  print(lambda_role_iam_arn)

  ##IngestionLoggger
  function_name, function_arn = pr.deploy_lambda_ingestion_logger(
    lambda_role_iam_arn,
    cfg['IMG_EVENT_TBL']['table_name']
  )
  rule_logger = pr.create_eventBridge_rule("IngestionLoggerRule", "rate(5 minutes)")
  # give EventBridge permission; handle case where permission already exists
  try:
    pr.give_eventBridge_permission(
      function_name,
      "EventBridgeInvoke",
      "lambda:InvokeFunction",
      "events.amazonaws.com",
      rule_logger["RuleArn"]
    )
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceConflictException":
      print("Permission 'EventBridgeInvoke' already exists on Lambda 'IngestionLogger'. Skipping add_permission.\n")
    else:
      raise

  pr.attach_lambda_targets("IngestionLoggerRule", function_arn)

  # S3 → Lambda trigger; handle case where S3InvokePermission already exists
  try:
    pr.create_s3_lambda_trigger(cfg['CAMERA_TRAP']['bucket_name'], function_arn, function_name)
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceConflictException":
      print("Permission 'S3InvokePermission' already exists for IngestionLogger. Skipping S3 trigger creation.\n")
    else:
      raise
 
  ## BatchNotifier
  topic_arn = pr.create_sns_topic("ImageIngestionTopic")
  pr.add_email_to_sns(topic_arn, cfg['USER_INFO']['email'])
  function_name, function_arn = pr.deploy_lambda_batch_notifier(
    lambda_role_iam_arn,
    topic_arn,
    cfg['IMG_EVENT_TBL']['table_name']
  )
  rule_notifier = pr.create_eventBridge_rule("BatchNotifierRule", "rate(5 minutes)")
  try:
    pr.give_eventBridge_permission(
      function_name,
      "EventBridgeInvoke",
      "lambda:InvokeFunction",
      "events.amazonaws.com",
      rule_notifier["RuleArn"]
    )
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceConflictException":
      print("Permission 'EventBridgeInvoke' already exists on Lambda 'BatchNotifier'. Skipping add_permission.\n")
    else:
      raise

  pr.attach_lambda_targets("BatchNotifierRule", function_arn)
 
  #----------------------------Begin Simulation----------------------------#
  #Simulation of streaming camera trap data directly into from-camera-trap s3 Bucket. These are images from validation set from data folder.
  print("Begining simulation of images from camera trap...\n")
  simulate_image_streaming.simulation(
    cfg['CAMERA_TRAP']['root_dir'],
    cfg['CAMERA_TRAP']['bucket_name'],
    cfg['CAMERA_TRAP']['val_meta']
  )
 
  #----------------------------Pipeline complete. Delete resources to avoid charges----------------------------#
  with open('aws_auth.yaml', 'r') as auth_file:
    auth_cfg = yaml.safe_load(auth_file)

  os.environ['AWS_ACCESS_KEY_ID'] = auth_cfg['aws']['access_key_id']
  os.environ['AWS_SECRET_ACCESS_KEY'] = auth_cfg['aws']['secret_access_key']
  os.environ['AWS_DEFAULT_REGION'] = auth_cfg['aws']['region']

  # Now safely delete everything
  # delete_resources(cfg, ct_policy_arn, topic_arn)


if __name__ == "__main__":
  main()
