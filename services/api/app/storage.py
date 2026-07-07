"""S3-compatible evidence storage access (MinIO locally).

Two clients are kept because presigned URLs embed the host in the signature:
- an internal client (service network address) for bucket administration
- a presigning client bound to the browser-reachable public endpoint
"""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from urllib.parse import urlparse

from minio import Minio

from app.config import get_settings

settings = get_settings()


def _client_for(endpoint: str) -> Minio:
    parsed = urlparse(endpoint)
    secure = parsed.scheme == "https"
    host = parsed.netloc or parsed.path
    return Minio(
        host,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=secure,
        # Pin the region so presigned URL generation is pure local signing.
        # Without it the SDK probes the endpoint for its region — and the
        # presign client points at the browser-facing endpoint, which is not
        # reachable from inside the API container.
        region=settings.minio_region,
    )


@lru_cache
def internal_client() -> Minio:
    return _client_for(settings.minio_endpoint)


@lru_cache
def presign_client() -> Minio:
    return _client_for(settings.minio_public_endpoint)


def ensure_bucket() -> None:
    client = internal_client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def presign_get_url(object_key: str, ttl_seconds: int | None = None) -> str:
    ttl = ttl_seconds or settings.evidence_url_ttl_seconds
    return presign_client().presigned_get_object(
        settings.minio_bucket,
        object_key,
        expires=timedelta(seconds=ttl),
    )
