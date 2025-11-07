import boto3

session = boto3.Session(
    aws_access_key_id='AKIAZ5J3R6MVME2U4MMW',
    aws_secret_access_key='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',
    region_name='us-east-2'
)
s3 = session.client('s3')
print("Listing buckets:", s3.list_buckets())