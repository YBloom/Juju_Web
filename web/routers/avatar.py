from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
import os
import time
import uuid

from web.dependencies import get_current_user as get_current_user_info

router = APIRouter(prefix="/avatar", tags=["Avatar"])

class UploadSignResponse(BaseModel):
    upload_url: str
    public_url: str
    key: str

@router.get("/upload-url", response_model=UploadSignResponse)
async def generate_upload_url(
    filename: str = Query(..., min_length=1, max_length=100),
    content_type: str = Query("image/webp", pattern=r"^image/(jpeg|png|webp|svg\+xml)$"),
    user: dict = Depends(get_current_user_info)
):
    """
    Generate a presigned URL for uploading an avatar to S3.
    """
    if "user_id" not in user and "qq_id" not in user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    uid = user.get("user_id") or user.get("qq_id")
    
    # Configuration
    BUCKET = os.getenv("AWS_BUCKET_NAME")
    PREFIX = os.getenv("S3_PREFIX", "avatars/")
    ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
    SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    REGION = os.getenv("AWS_REGION", "us-east-1")
    
    if not all([BUCKET, ACCESS_KEY, SECRET_KEY]):
        raise HTTPException(status_code=500, detail="Server S3 configuration missing")

    s3_client = boto3.client(
        's3',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION
    )

    # Generate unique key
    if content_type == "image/svg+xml":
        ext = "svg"
    else:
        ext = content_type.split("/")[-1]
        
    object_key = f"{PREFIX}{uid}_{int(time.time())}.{ext}"
    
    try:
        # Generate presigned URL for PUT
        upload_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET,
                'Key': object_key,
                'ContentType': content_type
                # 'ACL': 'public-read' # Not enabled by default on many buckets, rely on bucket policy
            },
            ExpiresIn=300 # 5 minutes
        )
        
        # Construct public URL (Assuming standard AWS domain or custom domain if configured)
        # Here we use standard S3 virtual-hosted style URL
        public_url = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{object_key}"
        
        return UploadSignResponse(
            upload_url=upload_url,
            public_url=public_url,
            key=object_key
        )
        
    except ClientError as e:
        print(f"S3 Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate upload signature")
