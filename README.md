<div align="center">
  
# Wildlife Detection using YOLOv8 for Analytics with Amazon Location Services
  
  ## Group 10
  
  ### Aditya Sastry • Prakhar Tiwari • Vivek Ediga • Yajat Uppal • Ateeq Ur Rehman

</div>

# How To Use
1. **Generate Kaggle API Token** - If you haven't done so yet, go to Kaggle and create a new API token to ensure the dataset can be downloaded. This should download a `kaggle.json` file. Ensure the Kaggle CLI is installed (`pip install kaggle`). Make a new folder in your under your user profile called **.kaggle** (if windows: `mkdir <insert-user-profile>\.kaggle`). Link to Kaggle Dataset: [Spatiotemporal Wildlife Dataset]("https://www.kaggle.com/datasets/travisdaws/spatiotemporal-wildlife-dataset?resource=download&select=images"). In `config.yaml`, it will be pointing to images for a small set of images for the African Forest Elephant (loxodonta cyclotis) for testing at first. If you want to try a larger set of images, you can switch the folder to point to images for the African Bush Elephant (loxodonta africana). Once Your token has been set up. Run download_dataset.py under the utils folder. This will download the dataset

https://www.kaggle.com/datasets/travisdaws/spatiotemporal-wildlife-dataset?resource=download&select=images

3. **Edit AWS Authentication .yaml** - Edit the (or create your own)  `aws.yaml` file. This file will be used within our scripts to authenticate and utilize the AWS CLI and boto3. Be sure to add your `access_key_id`, `secret_key_id`, and `region`. Access keys to the project_reviewer user will be attached to our final submission.

<pre>
aws:
  access_key_id: INSERT YOUR ACCESS KEY ID
  secret_access_key: "INSERT YOUR SECRET ACCESS KEY ID"
  region: "us-east-1" # <- or whatever region you are in
</pre>

3. **Adjust User information in config.yaml** - in `config.yaml`, adjust the `USER_INFO`, to be your user name of the given account (project_reviewer), region, and preferred email for SNS notifications.
<pre>
USER_INFO:
  user_name: 'INSERT AWS USER NAME'
  region: 'us-east-1'
  email: 'INSERT PREFERED EMAIL ADDRESS'

</pre>

4. **Getting Console Ready** - In the AWS Console Check that images from previous runs are deleted from the from-camera-trap-1 S3 bucket and that all **items** are deleted from image_event DynamoDB table. If you don't delete them, you may have duplicate results. DO **NOT** DELETE THE image_event TABLE ITSELF JUST THE ITEMS.

5.  In Amazon EventBridge --> Rules, ensure the following rules are **endabled**: BatchNotifierRule, IngestionLoggerRule, and CreateGeoJSON.

6. In Amazon SageMaker AI, Under "Deployments & Inference" --> Endpoints --> Create Endpoint. Name the Endpoint "yolov8s". For Enddpoint Configuration choose "yolov8-prod-config". Press Create Endpoint and wait for a couple of minutes for the endpoint to be created.

7. **Run main()** - Now that you have completed the steps above, you should be able to run `main()` to run the simulation! You will get a email to confirm your SNS subscription. Accept it so you can get notifications of image uploads and classifications.

8. **Viewing Results** - As the script runs, you should be able to see the following:
  - from-camera-trap-1 S3 bucket fill up with images from dataset. Each image will have associated metadata.
  - DynamoDB will be populating with extracted metadata and prediction results from Yolov8s
  - Notifications will be sent to the email used in `config.yaml`
  - artifacts-for-report will have two files:
    - `wildlife_predictions_FLATTENED.json` -> this is use for QuickSight/Power BI to ingest the longitudes and latitudes of where images were taken. Ideally, it would have been in QuickSight, as we were having access issues we pivoted to Power BI. A Power BI file of result will be includd in repo to download and view within your own PowerBI desktop application. Will also include an image of resulting report in the repo.
    - `wildlife_predictions.geojson` -> this used for a web map


9. **IMPORTANT - Clean Up** - After you are done testing the pipeline, go back to Amazon SageMaker AI go to Deployments & Inference --> Endpoints and delete the endpoint you created. This is a provisioned sagemaker endpoint so it cost money to leave up an running. **Be sure to delete it after you are done with your viewing or testing of the pipeline**. ENSURE YOU LEAVE ENDPOINT CONFIGURATIONS AND DEPLOYABLE MODELS AS IS. DO NOT TOUCH.




