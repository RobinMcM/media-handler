import os
import boto3
from pathlib import Path
from typing import Optional
from botocore.exceptions import ClientError


# Load configuration from environment
SPACES_BUCKET = os.getenv("SPACES_BUCKET")
SPACES_ENDPOINT = os.getenv("SPACES_ENDPOINT")
SPACES_ACCESS_KEY_ID = os.getenv("SPACES_ACCESS_KEY_ID")
SPACES_SECRET_ACCESS_KEY = os.getenv("SPACES_SECRET_ACCESS_KEY")
SPACES_PUBLIC_BASE_URL = os.getenv("SPACES_PUBLIC_BASE_URL")


def _get_s3_client():
    """
    Create and return boto3 S3 client configured for DigitalOcean Spaces.
    Raises RuntimeError if required environment variables are missing.
    """
    if not all([SPACES_BUCKET, SPACES_ENDPOINT, SPACES_ACCESS_KEY_ID, SPACES_SECRET_ACCESS_KEY]):
        missing = []
        if not SPACES_BUCKET:
            missing.append("SPACES_BUCKET")
        if not SPACES_ENDPOINT:
            missing.append("SPACES_ENDPOINT")
        if not SPACES_ACCESS_KEY_ID:
            missing.append("SPACES_ACCESS_KEY_ID")
        if not SPACES_SECRET_ACCESS_KEY:
            missing.append("SPACES_SECRET_ACCESS_KEY")
        raise RuntimeError(f"Missing required Spaces environment variables: {', '.join(missing)}")
    
    session = boto3.session.Session()
    client = session.client(
        's3',
        region_name='us-east-1',  # Required by boto3 but not used by Spaces
        endpoint_url=SPACES_ENDPOINT,
        aws_access_key_id=SPACES_ACCESS_KEY_ID,
        aws_secret_access_key=SPACES_SECRET_ACCESS_KEY
    )
    
    return client


def download_key_to_path(spaces_key: str, local_path: str) -> None:
    """
    Download object from DigitalOcean Spaces to local file path.
    
    Args:
        spaces_key: Path/key in Spaces bucket (e.g., "videos/input.mp4")
        local_path: Local filesystem path to save the file
        
    Raises:
        RuntimeError: If Spaces configuration is missing
        ClientError: If download fails (object not found, permission denied, etc.)
    """
    client = _get_s3_client()
    
    # Ensure parent directory exists
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        client.download_file(SPACES_BUCKET, spaces_key, local_path)
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404' or error_code == 'NoSuchKey':
            raise RuntimeError(f"Object not found in Spaces: {spaces_key}")
        else:
            raise RuntimeError(f"Failed to download from Spaces: {error_code}")


def upload_path_to_key(local_path: str, spaces_key: str, content_type: Optional[str] = None) -> None:
    """
    Upload local file to DigitalOcean Spaces.
    
    Args:
        local_path: Local filesystem path of file to upload
        spaces_key: Destination path/key in Spaces bucket (e.g., "videos/output.mp4")
        content_type: Optional Content-Type header (e.g., "video/mp4")
        
    Raises:
        RuntimeError: If Spaces configuration is missing or upload fails
        FileNotFoundError: If local file doesn't exist
    """
    client = _get_s3_client()
    
    if not Path(local_path).exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")
    
    try:
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        client.upload_file(local_path, SPACES_BUCKET, spaces_key, ExtraArgs=extra_args if extra_args else None)
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        raise RuntimeError(f"Failed to upload to Spaces: {error_code}")


def get_public_url(spaces_key: str) -> Optional[str]:
    """
    Get public URL for a Spaces object if SPACES_PUBLIC_BASE_URL is configured.
    
    Args:
        spaces_key: Path/key in Spaces bucket
        
    Returns:
        Public URL string if SPACES_PUBLIC_BASE_URL is set, None otherwise
    """
    if not SPACES_PUBLIC_BASE_URL:
        return None
    
    # Remove leading slash from spaces_key if present
    clean_key = spaces_key.lstrip('/')
    
    # Combine base URL with key
    base = SPACES_PUBLIC_BASE_URL.rstrip('/')
    return f"{base}/{clean_key}"
