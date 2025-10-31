import os
import time
import random
import boto3
import pandas as pd

def simulation(ROOT_DIRECTORY, BUCKET_NAME, VALIDATION_METATA):
    s3 =boto3.client("s3")
    
    #Crawling through Images and extracting Occurence ID and Directory into Dataframe
    image_info = []
    for root, dirs, files in os.walk(ROOT_DIRECTORY):
        for file in files:
            if file.lower().endswith(('.jpg','.jpeg')):
                occurence_id = os.path.splitext(file)[0].split('_')[0]
                image_info.append({'id':occurence_id, 'path': os.path.join(root,file)})

    #Combining image path with metadata records using id
    image_df = pd.DataFrame(image_info)
    image_df['id'] = image_df['id'].astype(int)
    image_df['path'] = image_df['path'].astype(str)
    metadata_df = pd.read_csv(VALIDATION_METATA)
    merged_df = pd.merge(image_df, metadata_df, on='id', how='left')

    #Iterating through dataframe to to upload Images to S3 with certain metadata fields
    for _, row in merged_df.iterrows():
        file_path = row['path']
        file_name = os.path.basename(file_path)
    
        #simulating network delay
        delay = random.expovariate(1/3)
        print(f"Waiting {delay:.2f}s before next upload...")
        time.sleep(delay)

        #Metadata fields to be sent over to S3
        metadata = {
            'lat': str(row['latitude']),
            'long': str(row['longitude']),
            'positional_accuracy': str(row['positional_accuracy']),
            'temperature': str(row['temperature_2m']),
            'elevation': str(row['elevation']),
            'time': str(row['time'])
        }

        #simulating upload failures and retries
        retries = 3

        for attempt in range (1, retries + 1):
            try:
                if random.random()< 0.3:
                    raise Exception("Simulated network failure")
            
                s3_key = f"images/{file_name}" 
                s3.upload_file(file_path, 
                            BUCKET_NAME, 
                            s3_key,
                            ExtraArgs={'Metadata': metadata})
                print(f"Uploaded {file_name} to s3://{BUCKET_NAME}/{s3_key}")
                break

            except Exception as e:
                print(f"Attempt {attempt} failed for {file_name}: {e}")
                if attempt < retries:
                    time.sleep(1)  # wait before retrying
                else:
                    print(f"Failed to upload {file_name} after {retries} attempts")        


