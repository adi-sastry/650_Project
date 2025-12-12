import utils.provision_resources as pr
#import utils.clean_up as cu
import src.simulate_image_streaming as simulate_image_streaming
import os
import sys
import yaml

def load_config(config_path: str= 'config.yaml') -> dict:
  with open(config_path, 'r') as f:
    config_data = yaml.safe_load(f)
  return config_data

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
 
 #----------------------------Begin Simulation----------------------------#

 #Simulation of streaming camera trap data directly into from-camera-trap s3 Bucket. These are images from validation set from data folder.
 #topic_arn = pr.create_sns_topic("ImageIngestionTopic") # Commented this out becuase I already created topic after running once
 #pr.add_email_to_sns(topic_arn,cfg['USER_INFO']['email'])
 print("Begining simulation of images from camera trap...\n")
 simulate_image_streaming.simulation(cfg['CAMERA_TRAP']['root_dir'], cfg['CAMERA_TRAP']['bucket_name'], cfg['CAMERA_TRAP']['val_meta'])
 
if __name__ =="__main__":
 main()