"""Provider-neutral media storage adapters.

The adapters store validated image bytes only. Authorization, image decoding,
metadata persistence and object lifecycle orchestration belong to the API layer.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import quote


_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_STORAGE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$")
_DEFAULT_READ_URL_TTL_SECONDS = 900
_MAX_READ_URL_TTL_SECONDS = 900


class MediaStorageConfigurationError(ValueError):
    """Raised when media storage environment configuration is incomplete or invalid."""


class MediaStorage(Protocol):
    def put_bytes(self, key: str, body: bytes, content_type: str) -> None: ...

    def delete(self, key: str) -> None: ...

    def create_read_url(self, key: str) -> str: ...


def _validate_key(key: str) -> tuple[str, ...]:
    if not isinstance(key, str) or not _STORAGE_KEY_PATTERN.fullmatch(key):
        raise ValueError("Invalid media storage key")
    parts = tuple(key.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Invalid media storage key")
    return parts


def _validate_payload(body: bytes, content_type: str) -> None:
    if not isinstance(body, bytes) or not body:
        raise ValueError("Media payload must be non-empty bytes")
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported media content type")


def _validate_ttl(ttl_seconds: int) -> None:
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
        raise ValueError("Read URL TTL must be an integer")
    if not 1 <= ttl_seconds <= _MAX_READ_URL_TTL_SECONDS:
        raise ValueError(
            f"Read URL TTL must be between 1 and {_MAX_READ_URL_TTL_SECONDS} seconds"
        )


class LocalFileMediaStorage:
    """Filesystem adapter for local development and temporary-directory tests."""

    def __init__(
        self,
        root: str | Path,
        read_url_prefix: str = "/api/media/local",
    ) -> None:
        prefix = read_url_prefix.rstrip("/")
        if not prefix.startswith("/") or "?" in prefix or "#" in prefix:
            raise ValueError("Local media read URL prefix must be an absolute URL path")
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.read_url_prefix = prefix

    def _resolve_path(self, key: str) -> Path:
        parts = _validate_key(key)
        target = self.root.joinpath(*parts).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Media storage key escapes the configured root") from exc
        return target

    def put_bytes(self, key: str, body: bytes, content_type: str) -> None:
        _validate_payload(body, content_type)
        target = self._resolve_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        # Exclusive creation prevents a key collision from silently overwriting an object.
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(body)
                output.flush()
                os.fsync(output.fileno())
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def read_bytes(self, key: str) -> bytes:
        """Read bytes for the API's authorization-checked local media route."""
        return self._resolve_path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._resolve_path(key).unlink(missing_ok=True)

    def create_read_url(self, key: str) -> str:
        self._resolve_path(key)
        return f"{self.read_url_prefix}/{quote(key, safe='/')}"


class S3MediaStorage:
    """S3-compatible adapter used for the hosted Cloudflare R2 implementation."""

    def __init__(
        self,
        client: Any,
        bucket_name: str,
        read_url_ttl_seconds: int = _DEFAULT_READ_URL_TTL_SECONDS,
    ) -> None:
        if not bucket_name or not bucket_name.strip():
            raise ValueError("Media S3 bucket name is required")
        _validate_ttl(read_url_ttl_seconds)
        self.client = client
        self.bucket_name = bucket_name.strip()
        self.read_url_ttl_seconds = read_url_ttl_seconds

    def put_bytes(self, key: str, body: bytes, content_type: str) -> None:
        _validate_key(key)
        _validate_payload(body, content_type)
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    def delete(self, key: str) -> None:
        _validate_key(key)
        self.client.delete_object(Bucket=self.bucket_name, Key=key)

    def create_read_url(self, key: str) -> str:
        _validate_key(key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": key},
            ExpiresIn=self.read_url_ttl_seconds,
            HttpMethod="GET",
        )


def create_media_storage(
    environ: Mapping[str, str] | None = None,
) -> MediaStorage:
    """Create the configured adapter without exposing credentials to callers."""
    env = os.environ if environ is None else environ
    backend = env.get("MEDIA_STORAGE_BACKEND", "local").strip().lower()

    if backend == "local":
        configured_root = env.get("MEDIA_LOCAL_ROOT", "").strip()
        root = Path(configured_root).expanduser() if configured_root else Path(__file__).resolve().parent / ".media"
        if not root.is_absolute():
            root = Path(__file__).resolve().parent / root
        prefix = env.get("MEDIA_LOCAL_READ_URL_PREFIX", "/api/media/local")
        return LocalFileMediaStorage(root=root, read_url_prefix=prefix)

    if backend not in {"s3", "r2"}:
        raise MediaStorageConfigurationError(
            "MEDIA_STORAGE_BACKEND must be 'local', 's3' or 'r2'"
        )

    required = (
        "MEDIA_S3_ENDPOINT_URL",
        "MEDIA_S3_BUCKET",
        "MEDIA_S3_ACCESS_KEY_ID",
        "MEDIA_S3_SECRET_ACCESS_KEY",
    )
    missing = [name for name in required if not env.get(name, "").strip()]
    if missing:
        raise MediaStorageConfigurationError(
            "Missing media storage settings: " + ", ".join(missing)
        )

    try:
        ttl_seconds = int(env.get("MEDIA_READ_URL_TTL_SECONDS", str(_DEFAULT_READ_URL_TTL_SECONDS)))
        _validate_ttl(ttl_seconds)
    except (TypeError, ValueError) as exc:
        raise MediaStorageConfigurationError(str(exc)) from exc

    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise MediaStorageConfigurationError(
            "Install backend requirements to use the S3 media storage adapter"
        ) from exc

    endpoint_url = env["MEDIA_S3_ENDPOINT_URL"].strip()
    if not endpoint_url.startswith("https://"):
        raise MediaStorageConfigurationError("MEDIA_S3_ENDPOINT_URL must use HTTPS")

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=env.get("MEDIA_S3_REGION", "auto").strip() or "auto",
        aws_access_key_id=env["MEDIA_S3_ACCESS_KEY_ID"],
        aws_secret_access_key=env["MEDIA_S3_SECRET_ACCESS_KEY"],
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )
    return S3MediaStorage(
        client=client,
        bucket_name=env["MEDIA_S3_BUCKET"],
        read_url_ttl_seconds=ttl_seconds,
    )
