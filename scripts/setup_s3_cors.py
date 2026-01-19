import boto3
import csv
import os
from botocore.exceptions import ClientError

def setup_cors():
    # Path to credentials: keys/yyj-yaobii-com-s3-operator_accessKeys.csv
    # Assuming script is in scripts/ directory, so we go up one level
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    key_file = os.path.join(base_dir, 'keys', 'yyj-yaobii-com-s3-operator_accessKeys.csv')
    
    print(f"Reading credentials from: {key_file}")
    
    try:
        with open(key_file, 'r') as f:
            reader = csv.reader(f)
            header = next(reader) # Skip header
            row = next(reader)
            access_key = row[0]
            secret_key = row[1]
    except Exception as e:
        print(f"Error reading credentials from {key_file}: {e}")
        return

    bucket_name = "yyj-yaobii-com"

    print(f"Configuring CORS for bucket: {bucket_name}")

    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='us-east-1'
        )

        cors_configuration = {
            'CORSRules': [{
                'AllowedHeaders': ['*'],
                'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
                'AllowedOrigins': ['*'],
                'ExposeHeaders': ['ETag', 'x-amz-server-side-encryption', 'x-amz-request-id', 'x-amz-id-2']
            }]
        }

        s3.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors_configuration)
        print(f"Successfully set CORS configuration for bucket: {bucket_name}")
        
    except ClientError as e:
        print(f"Error setting CORS configuration: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    setup_cors()
