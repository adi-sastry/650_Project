<div align="center">
  
# Wildlife Detection using YOLOv8 for Analytics with Amazon Location Services
  
  ## Group 10
  
  ### Aditya Sastry • Prakhar Tiwari • Vivek Ediga • Yajat Uppal • Ateeq Ur Rehman

</div>

# Motivation & Problem Statement

As inhabitants of Earth, we have long observed numerous changes affecting our planet.  Warmer temperatures, rising sea levels, and extreme weather events are becoming more prevalent. However, we must not forget that we are not the only species being impacted. Since the 1970s, thousands of wildlife populations and Earth’s overall biodiversity have declined due to these environmental changes, as well as human-driven activities such as deforestation, urban development, and pollution (Ritchie, 2022).

Conserving all of Earth’s biodiversity is essential to our survival. Wildlife supports healthy and resilient ecosystems, which in turn sustain human health (Shaw, 2024). One of the most effective ways to support biodiversity conservation is by understanding where species live and how they are distributed. This knowledge allows us to identify key habitats for protection and support resource management (NatureServe).

Species distribution data often comes from occurrence records, which can be captured using edge devices such as trail cameras. However, these devices often have limitations with storage capacity and vulnerability to data loss through damage or tampering.  Latency is another major concern, as significant events could go unnoticed for days (Yu, 2024). These events might include rare wildlife behavior or the presence of poachers and other anthropogenic threats to wildlife.

To ensure all data is reliably captured and available to support species distribution, conservation planning, and protection, a more robust and resilient data pipeline must be established. Therefore, we are proposing a cloud-based pipeline that facilitates the ingestion and offloading of data from edge-devices, such as trail cameras, for wildlife or threat detection, analytics, and visualization.

# High-Level Approach & Architecture

## Stage 1: Simulted Ingestion
## Stage 2: Data Processing & Object Detection
## Stage 3: Alerts & Notifications
## Stage 4: Storage & Metadata Management
## Stage 5 : Visualization & Analysis

# How To Use

## File Structure & Scripts

### Model
This contains files and scripts related to Object Detection using Yolov8.

### src
1. **s3_loader.py**
2. **simulate_image_streaming.py** simulates edge-device behavior of camera-trap sending data directly to an S3 Bucket. The images sent are all from the Spatiotemporal Wildlfe Dataset.
### files
This contains PDFs of written project deliverables such as the project Proposal and Interim report.
### utils
1. **download_dataset.py** downloads the Spatiotemporal Wildlfe Dataset from Kaggle using its API. *Ensure you have generated your kaggle API token before running anything!*
2. **provision_resources.py** contains all the function used to provision AWS resources required for all five stages of the architecture.
3. **clean_up.py** contains all functions used to "clean up" after ourselves after resources have been provisioned. As we are using the Free-tier of AWS, this ensures that we are not charged for extended use of provisioned resources
### config.yaml
This config file is used to populate different parameters in variables within `main()`. **NOTE:** `USER_INFO` *must be filled out with **your** user name, region, and preferred email for SNS notifications*
### main
Contains all function calls in the logical order to provision resources and run the simulation. If you would like the resources to be deleted after the program runs, then you must ensure `delete_resources` is not commented out.
## How to Use
1. **Generate Kaggle API Token** - If you haven't done so yet, go to Kaggle and create a new API token to ensure the dataset can be downloaded. This should download a `kaggle.json` file. Ensure the Kaggle CLI is installed (`pip install kaggle`). Make a new folder in your under your user profile called **.kaggle** (if windows: `mkdir <insert-user-profile>\.kaggle`).
2. **Create AWS Authentication .yaml** Create a .yaml file and name it `aws_auth.yaml`. This file will be used within our scripts to authenticate and utilize the AWS CLI and boto3. Be sure to add your `access_key_id`, `secret_key_id`, and `region`. It is not in our seen in our repo as it is mentioned in our `.gitignore`.
3. **Adjust User information in config.yaml** - in `config.yaml`, adjust the `USER_INFO`, to be your user name, region, and preferred email for SNS notifications.
4. **Run main()** - Now that you have completed the steps above, you should be able to run `main()` to provison resources and run the simulation! **NOTE**: If you want resources to be cleaned up after the simulation completes, ensure that `delete_resources` is not commented out.
