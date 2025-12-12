"""
Stage 4 Resource Provisioning
Functions to create and configure Stage 4 DynamoDB tables with proper indexes
"""

import boto3
import yaml
import time
import logging
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_aws_credentials(config_path: str = 'aws_auth.yaml') -> dict:
    """Load AWS credentials from configuration file."""
    with open(config_path, 'r') as f:
        aws_config = yaml.safe_load(f)
    return aws_config['aws']


def get_aws_client(service_name: str):
    """Get authenticated AWS client."""
    aws_credentials = load_aws_credentials()
    return boto3.client(
        service_name.lower(),
        aws_access_key_id=aws_credentials['access_key_id'],
        aws_secret_access_key=aws_credentials['secret_access_key'],
        region_name=aws_credentials['region']
    )


def provision_stage4_tables():
    """
    Provision all Stage 4 DynamoDB tables with proper schema and indexes.
    
    Creates:
    1. Enhanced image_event table (if doesn't exist, or updates existing)
    2. detection_results table with comprehensive indexes
    
    Returns:
        Dictionary with table ARNs
    """
    dynamodb = get_aws_client('dynamodb')
    
    tables_created = {}
    
    # ============================================
    # Create detection_results table
    # ============================================
    
    print("Provisioning detection_results table...")
    
    try:
        # Check if table exists
        existing_tables = dynamodb.list_tables()['TableNames']
        
        if 'detection_results' not in existing_tables:
            response = dynamodb.create_table(
                TableName='detection_results',
                KeySchema=[
                    {'AttributeName': 'detection_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'detection_id', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'S'},
                    {'AttributeName': 'image_name', 'AttributeType': 'S'},
                    {'AttributeName': 'species', 'AttributeType': 'S'},
                    {'AttributeName': 'camera_id', 'AttributeType': 'S'},
                    {'AttributeName': 'confidence_level', 'AttributeType': 'S'},
                    {'AttributeName': 'geo_hash', 'AttributeType': 'S'},
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'image_name-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'image_name', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'species-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'species', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'camera_id-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'camera_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'confidence_level-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'confidence_level', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'geo_hash-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'geo_hash', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ],
                BillingMode='PROVISIONED',
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                },
                Tags=[
                    {'Key': 'Project', 'Value': 'WildlifeDetection'},
                    {'Key': 'Stage', 'Value': 'Stage4'}
                ]
            )
            
            # Wait for table to be active
            print("Waiting for detection_results table to become active...")
            waiter = dynamodb.get_waiter('table_exists')
            waiter.wait(TableName='detection_results')
            
            tables_created['detection_results'] = response['TableDescription']['TableArn']
            print(f"✓ detection_results table created: {tables_created['detection_results']}")
            
            # Wait for GSIs to be active
            print("Waiting for Global Secondary Indexes to become active...")
            time.sleep(30)  # GSIs take time to activate
            
        else:
            # Table already exists
            response = dynamodb.describe_table(TableName='detection_results')
            tables_created['detection_results'] = response['Table']['TableArn']
            print(f"✓ detection_results table already exists: {tables_created['detection_results']}")
    
    except ClientError as e:
        logger.error(f"Error creating detection_results table: {e}")
        raise
    
    # ============================================
    # Update image_event table (add GSIs if needed)
    # ============================================
    
    print("\nChecking image_event table...")
    
    try:
        # Check if table exists
        existing_tables = dynamodb.list_tables()['TableNames']
        
        if 'image_event' in existing_tables:
            # Check if table has the required GSIs
            response = dynamodb.describe_table(TableName='image_event')
            existing_gsis = [gsi['IndexName'] for gsi in response['Table'].get('GlobalSecondaryIndexes', [])]
            
            required_gsis = [
                'bucket_name-time_stamp-index',
                'processed-time_stamp-index', 
                'camera_id-time_stamp-index'
            ]
            
            missing_gsis = [gsi for gsi in required_gsis if gsi not in existing_gsis]
            
            if missing_gsis:
                print(f"⚠ image_event table exists but missing GSIs: {missing_gsis}")
                print("Note: Adding GSIs to existing tables requires manual update via AWS Console")
                print("Alternative: Delete and recreate table, or use the new enhanced table creation")
            else:
                print("✓ image_event table has all required GSIs")
            
            tables_created['image_event'] = response['Table']['TableArn']
        else:
            print("⚠ image_event table doesn't exist. It should be created by Stage 1 provisioning.")
            print("Run the stage4_metadata_manager.py to create enhanced version.")
    
    except ClientError as e:
        logger.error(f"Error checking image_event table: {e}")
    
    return tables_created


def enable_dynamodb_streams(table_name: str, stream_view_type: str = 'NEW_AND_OLD_IMAGES'):
    """
    Enable DynamoDB Streams for a table (useful for triggering processing).
    
    Args:
        table_name: Name of the DynamoDB table
        stream_view_type: Type of stream view (NEW_IMAGE, OLD_IMAGE, NEW_AND_OLD_IMAGES, KEYS_ONLY)
    """
    dynamodb = get_aws_client('dynamodb')
    
    try:
        response = dynamodb.update_table(
            TableName=table_name,
            StreamSpecification={
                'StreamEnabled': True,
                'StreamViewType': stream_view_type
            }
        )
        
        stream_arn = response['TableDescription']['LatestStreamArn']
        print(f"✓ DynamoDB Stream enabled for {table_name}: {stream_arn}")
        return stream_arn
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException':
            print(f"⚠ Stream may already be enabled for {table_name}")
        else:
            logger.error(f"Error enabling stream: {e}")
        return None


def enable_point_in_time_recovery(table_name: str):
    """
    Enable Point-in-Time Recovery for a DynamoDB table.
    
    Args:
        table_name: Name of the DynamoDB table
    """
    dynamodb = get_aws_client('dynamodb')
    
    try:
        dynamodb.update_continuous_backups(
            TableName=table_name,
            PointInTimeRecoverySpecification={
                'PointInTimeRecoveryEnabled': True
            }
        )
        print(f"✓ Point-in-Time Recovery enabled for {table_name}")
    
    except ClientError as e:
        logger.error(f"Error enabling PITR: {e}")


def configure_table_autoscaling(table_name: str, min_capacity: int = 5, max_capacity: int = 100):
    """
    Configure auto-scaling for a DynamoDB table.
    
    Args:
        table_name: Name of the DynamoDB table
        min_capacity: Minimum capacity units
        max_capacity: Maximum capacity units
    """
    autoscaling = get_aws_client('application-autoscaling')
    
    try:
        # Register table for auto-scaling
        autoscaling.register_scalable_target(
            ServiceNamespace='dynamodb',
            ResourceId=f'table/{table_name}',
            ScalableDimension='dynamodb:table:ReadCapacityUnits',
            MinCapacity=min_capacity,
            MaxCapacity=max_capacity
        )
        
        autoscaling.register_scalable_target(
            ServiceNamespace='dynamodb',
            ResourceId=f'table/{table_name}',
            ScalableDimension='dynamodb:table:WriteCapacityUnits',
            MinCapacity=min_capacity,
            MaxCapacity=max_capacity
        )
        
        # Create scaling policies
        autoscaling.put_scaling_policy(
            PolicyName=f'{table_name}-read-scaling-policy',
            ServiceNamespace='dynamodb',
            ResourceId=f'table/{table_name}',
            ScalableDimension='dynamodb:table:ReadCapacityUnits',
            PolicyType='TargetTrackingScaling',
            TargetTrackingScalingPolicyConfiguration={
                'TargetValue': 70.0,
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'DynamoDBReadCapacityUtilization'
                }
            }
        )
        
        autoscaling.put_scaling_policy(
            PolicyName=f'{table_name}-write-scaling-policy',
            ServiceNamespace='dynamodb',
            ResourceId=f'table/{table_name}',
            ScalableDimension='dynamodb:table:WriteCapacityUnits',
            PolicyType='TargetTrackingScaling',
            TargetTrackingScalingPolicyConfiguration={
                'TargetValue': 70.0,
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'DynamoDBWriteCapacityUtilization'
                }
            }
        )
        
        print(f"✓ Auto-scaling configured for {table_name}")
    
    except ClientError as e:
        logger.error(f"Error configuring auto-scaling: {e}")


def provision_stage4_complete():
    """
    Complete Stage 4 provisioning with all enhancements.
    """
    print("=" * 60)
    print("Stage 4 Complete Provisioning")
    print("=" * 60)
    
    # Create tables
    tables = provision_stage4_tables()
    
    # Enable streams for real-time processing
    print("\nEnabling DynamoDB Streams...")
    enable_dynamodb_streams('detection_results')
    
    # Enable Point-in-Time Recovery
    print("\nEnabling Point-in-Time Recovery...")
    enable_point_in_time_recovery('detection_results')
    
    # Configure auto-scaling
    print("\nConfiguring Auto-scaling...")
    configure_table_autoscaling('detection_results', min_capacity=5, max_capacity=100)
    
    print("\n" + "=" * 60)
    print("Stage 4 Provisioning Complete!")
    print("=" * 60)
    print("\nCreated tables:")
    for table_name, arn in tables.items():
        print(f"  • {table_name}: {arn}")
    
    return tables


if __name__ == "__main__":
    provision_stage4_complete()
