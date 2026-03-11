"""
Object Storage Abstraction - MinIO and IBM COS

Provides a unified interface for object storage using the S3 API protocol.
Supported: MinIO (local), IBM Cloud Object Storage. No AWS S3.
Switch providers by changing config (endpoint, credentials).
"""

from __future__ import annotations

from io import BytesIO
from typing import IO, Protocol

import structlog

logger = structlog.get_logger(__name__)


class ObjectStorageBackend(Protocol):
    """Protocol for object storage - MinIO, IBM COS (S3 API)."""

    def upload(
        self,
        key: str,
        data: bytes | IO[bytes],
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload data. Returns object key/URI."""
        ...

    def download(self, key: str) -> bytes:
        """Download object content."""
        ...

    def exists(self, key: str) -> bool:
        """Check if object exists."""
        ...

    def delete(self, key: str) -> None:
        """Delete object."""
        ...

    def list_objects(self, prefix: str) -> list[str]:
        """List object keys with given prefix."""
        ...

    def get_object_metadata(self, key: str) -> dict[str, str]:
        """Return lightweight object metadata (etag/size/last_modified)."""
        ...

    def ensure_bucket_exists(self) -> None:
        """Create bucket if it does not exist."""
        ...


class S3CompatibleStorage:
    """
    Object storage for MinIO and IBM COS (S3 API protocol).

    Configure via:
    - OBJECT_STORAGE_ENDPOINT: e.g. http://minio:9000 (MinIO) or
      https://s3.us-south.cloud-object-storage.appdomain.cloud (IBM COS)
    - OBJECT_STORAGE_ACCESS_KEY, OBJECT_STORAGE_SECRET_KEY
    - OBJECT_STORAGE_BUCKET
    - OBJECT_STORAGE_REGION: for IBM COS; MinIO typically uses us-east-1
    - OBJECT_STORAGE_USE_SSL: true for IBM COS, false for local MinIO
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.region = region
        self._client = None

    def _get_client(self):
        """Lazy-init S3 client."""
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as e:
                raise ImportError(
                    "boto3 is required for object storage. Install with: uv add boto3"
                ) from e

            client_kwargs = {
                "aws_access_key_id": self.access_key,
                "aws_secret_access_key": self.secret_key,
                "region_name": self.region,
                "config": Config(signature_version="s3v4"),
            }
            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url
            self._client = boto3.client("s3", **client_kwargs)
            logger.info(
                "object_storage_initialized",
                endpoint=self.endpoint_url or "default",
                bucket=self.bucket,
            )
        return self._client

    def ensure_bucket_exists(self) -> None:
        """Create bucket if it does not exist."""
        client = self._get_client()
        try:
            client.head_bucket(Bucket=self.bucket)
            logger.debug("bucket_exists", bucket=self.bucket)
        except client.exceptions.NoSuchBucket:
            client.create_bucket(Bucket=self.bucket)
            logger.info("bucket_created", bucket=self.bucket)
        except Exception as e:
            # For MinIO, NoSuchBucket may manifest differently
            try:
                client.create_bucket(Bucket=self.bucket)
                logger.info("bucket_created", bucket=self.bucket)
            except Exception as create_err:
                logger.warning(
                    "bucket_check_failed",
                    bucket=self.bucket,
                    error=str(create_err),
                )
                raise

    def upload(
        self,
        key: str,
        data: bytes | IO[bytes],
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload data. Returns object key."""
        client = self._get_client()
        body = data if isinstance(data, bytes) else data.read()
        client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        logger.debug("object_uploaded", key=key, bucket=self.bucket)
        return key

    def download(self, key: str) -> bytes:
        """Download object content."""
        client = self._get_client()
        response = client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        """Check if object exists."""
        try:
            self._get_client().head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        """Delete object."""
        self._get_client().delete_object(Bucket=self.bucket, Key=key)
        logger.debug("object_deleted", key=key)

    def list_objects(self, prefix: str) -> list[str]:
        """List object keys with given prefix."""
        client = self._get_client()
        paginator = client.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    def get_object_metadata(self, key: str) -> dict[str, str]:
        """Return object metadata without downloading the object."""
        client = self._get_client()
        head = client.head_object(Bucket=self.bucket, Key=key)
        etag = str(head.get("ETag", "")).strip('"')
        size = str(head.get("ContentLength", ""))
        last_modified = str(head.get("LastModified", ""))
        return {
            "etag": etag,
            "size": size,
            "last_modified": last_modified,
        }


def create_object_storage(
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    region: str = "us-east-1",
) -> ObjectStorageBackend:
    """Create object storage client (MinIO / IBM COS)."""
    return S3CompatibleStorage(
        endpoint_url=endpoint_url,
        access_key=access_key,
        secret_key=secret_key,
        bucket=bucket,
        region=region,
    )


def get_object_storage_from_config() -> ObjectStorageBackend | None:
    """
    Create object storage from application config.
    Returns None if object storage is not configured (endpoint empty).
    """
    try:
        from config import get_settings

        s = get_settings()
        if not s.object_storage_endpoint:
            return None
        storage = create_object_storage(
            endpoint_url=s.object_storage_endpoint,
            access_key=s.object_storage_access_key,
            secret_key=s.object_storage_secret_key,
            bucket=s.object_storage_bucket,
            region=s.object_storage_region,
        )
        storage.ensure_bucket_exists()
        return storage
    except Exception as e:
        logger.warning("object_storage_init_failed", error=str(e))
        return None
