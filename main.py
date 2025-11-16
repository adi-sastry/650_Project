import utils.provision_resources as pr
import utils.clean_up as cu
import src.simulate_image_streaming as simulate_image_streaming
import os
import sys
import yaml

def load_config(config_path: str= 'config.yaml') -> dict:
  with open(config_path, 'r') as f:
    config_data = yaml.safe_load(f)
  return config_data

def delete_resources(cfg:dict, iam_client, ct_policy_arn):
  print("Begining Clean-Up of AWS Reaources...\n")

 #Delete from-camera-trap s3 bucket and IAM policy (Comment out if we want to retain resources)
  cu.delete_all_objects_in_s3(cfg['CAMERA_TRAP']['bucket_name'],cfg['USER_INFO']['region'])
  cu.delete_s3_bucket(cfg['CAMERA_TRAP']['bucket_name'],cfg['USER_INFO']['region'])
  cu.delete_iam_policy(iam_client,ct_policy_arn, cfg['USER_INFO']['user_name'])
  print(f"Bucket {cfg['CAMERA_TRAP']['bucket_name']} and policy {ct_policy_arn} deleted successfully.\n")

  cu.delete_dynamodb_table(cfg['IMG_EVENT_TBL']['table_name'])
  print(f"{cfg['IMG_EVENT_TBL']['table_name']} DynamoDB table deleted successfully.\n")

def main():
 
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
   cfg['CAMERA_TRAP']['bucket_name'], cfg['USER_INFO']['user_name'],cfg['CAMERA_TRAP']['allow_delete'])
 
 iam_client = pr.get_aws_client("iam")

 pr.attach_policy_user( iam_client,ct_policy_arn,cfg['USER_INFO']['user_name'])
 
 print(f"Bucket {cfg['CAMERA_TRAP']['bucket_name']} and policy {ct_policy_arn} created successfully.\n")

 #Creating dynamoDB table to store metadata of upload (timestamp, file_name, processed flag)
 attribute_definitions  = [
    {"AttributeName":attr["attributeName"], "AttributeType": attr["attributeType"]}
    for attr in cfg['IMG_EVENT_TBL']['attr_def']
  ]
 Key_schema  = [
    {"AttributeName": key["attributeName"], "KeyType": key["keyType"]}
    for key in cfg['IMG_EVENT_TBL']['key_schema']
  ]
 pr.create_database(cfg['IMG_EVENT_TBL']['table_name'],attribute_definitions, Key_schema)
 print(f" {cfg['IMG_EVENT_TBL']['table_name']} DynamoDB table created successfully.\n")
 
 #Setting up Lambda Functions and EventBridge Rules
 lambda_role_iam_arn= pr.create_iam_lambda_role(iam_client)
 pr.attach_passrole_policy(cfg['USER_INFO']['user_name'])
 print(lambda_role_iam_arn)

 ##IngestionLoggger
 function_name, function_arn=pr.deploy_lambda_ingestion_logger(lambda_role_iam_arn)
 rule_logger = pr.create_eventBridge_rule("IngestionLoggerRule", "rate(5 minutes)")
 pr.give_eventBridge_permission(function_name, "EventBridgeInvoke", "lambda:InvokeFunction","events.amazonaws.com", rule_logger)
 pr.attach_lambda_targets("IngestionLoggerRule", function_arn)
 pr.create_s3_lambda_trigger(cfg['CAMERA_TRAP']['bucket_name'], function_arn, function_name)
 
 #----------------------------Begin Simulation----------------------------#

 #Simulation of streaming camera trap data directly into from-camera-trap s3 Bucket. These are images from validation set from data folder.
 print("Begining simulation of images from camera trap...\n")
 simulate_image_streaming.simulation(cfg['CAMERA_TRAP']['root_dir'], cfg['CAMERA_TRAP']['bucket_name'], cfg['CAMERA_TRAP']['val_meta'])

 
 ## BatchNotifier
"""  function_name, function_arn=pr.deploy_lambda_batch_notifier(lambda_role_iam_arn)
 rule_notifier = pr.create_eventBridge_rule("BatchNotifierRule", "rate(5 minutes)")
 pr.give_eventBridge_permission(function_name, "EventBridgeInvoke", "lambda:InvokeFunction","events.amazonaws.com", rule_notifier)
 pr.attach_lambda_targets("BatchNotifierRule", function_arn) """



 #----------------------------Pipeline complete. Delete resources to avoid charges----------------------------#
 #delete_resources(cfg, iam_client, ct_policy_arn)

if __name__ =="__main__":
 main()