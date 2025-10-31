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
  cu.delete_all_objects_in_s3(cfg['CAMERA_TRAP']['bucket_name'],cfg['CAMERA_TRAP']['region'])
  cu.delete_s3_bucket(cfg['CAMERA_TRAP']['bucket_name'],cfg['CAMERA_TRAP']['region'])
  cu.delete_iam_policy(iam_client,ct_policy_arn, cfg['CAMERA_TRAP']['user_name'])
  print(f"Bucket {cfg['CAMERA_TRAP']['bucket_name']} and policy {ct_policy_arn} deleted successfully.\n")

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

 #Provisioning from-camera-trap S3 Bucket and Policy
 pr.create_s3_bucket(cfg['CAMERA_TRAP']['bucket_name'], 
                     cfg['CAMERA_TRAP']['region'])
 
 ct_policy_arn = pr.create_image_camera_trap_policy_for_bucket(
   cfg['CAMERA_TRAP']['bucket_name'], 
   cfg['CAMERA_TRAP']['user_name'],
   cfg['CAMERA_TRAP']['allow_delete'])
 
 iam_client = pr.get_iam_client()

 pr.attach_policy_user(
   iam_client,ct_policy_arn, 
   cfg['CAMERA_TRAP']['user_name'])
 
 print(f"Bucket {cfg['CAMERA_TRAP']['bucket_name']} and policy {ct_policy_arn} created successfully.\n")

#----------------------------Begin Simulation----------------------------#

 #Simulation of streaming camera trap data directly into from-camera-trap s3 Bucket. These are images from validation set from data folder.
 print("Begining simulation of images from camera trap...\n")
 simulate_image_streaming.simulation(cfg['CAMERA_TRAP']['root_dir'], cfg['CAMERA_TRAP']['bucket_name'], cfg['CAMERA_TRAP']['val_meta'])

 #----------------------------Pipeline complete. Delete resources to avoid charges----------------------------#
 delete_resources(cfg, iam_client, ct_policy_arn)

if __name__ =="__main__":
 main()