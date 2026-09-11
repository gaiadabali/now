from __future__ import annotations

import boto3
from botocore.client import Config as BotoConfig

from .config import MirrorConfig


def garage_client(config: MirrorConfig):
    return boto3.client(
        "s3",
        endpoint_url=config.garage_s3_endpoint,
        aws_access_key_id=config.garage_access_key_id,
        aws_secret_access_key=config.garage_secret_access_key,
        region_name=config.garage_region,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def object_key(city: str, sha256_hex: str, ext: str) -> str:
    """Content-addressed key: dedups byte-identical images (common — the
    same photo is reused across articles/sizes) and is stable regardless of
    the original filename or host variant. The ledger keeps the original
    URL -> key mapping needed for the later body_blocks.media_ref rewrite.
    """
    return f"media/{city}/{sha256_hex[:2]}/{sha256_hex}.{ext}"


def put_object(client, bucket: str, key: str, body: bytes, content_type: str) -> None:
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)


def object_exists(client, bucket: str, key: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return False
        raise
