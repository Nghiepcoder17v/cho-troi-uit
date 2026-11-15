import pytest

from media_storage import (
    LocalFileMediaStorage,
    MediaStorageConfigurationError,
    S3MediaStorage,
    create_media_storage,
)


class FakeS3Client:
    def __init__(self):
        self.put_calls = []
        self.delete_calls = []
        self.presign_calls = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)

    def delete_object(self, **kwargs):
        self.delete_calls.append(kwargs)

    def generate_presigned_url(self, operation, **kwargs):
        self.presign_calls.append((operation, kwargs))
        return "https://r2.example.test/signed-object"


def test_local_storage_writes_reads_and_returns_api_url(tmp_path):
    storage = LocalFileMediaStorage(tmp_path)
    key = "products/123/cover-image.webp"
    payload = b"normalized-image-bytes"

    storage.put_bytes(key, payload, "image/webp")

    assert storage.read_bytes(key) == payload
    assert storage.create_read_url(key) == f"/api/media/local/{key}"


def test_local_storage_quotes_url_path_segments(tmp_path):
    storage = LocalFileMediaStorage(tmp_path)
    key = "products/123/image-name.webp"
    storage.put_bytes(key, b"image", "image/webp")

    assert storage.create_read_url(key) == "/api/media/local/products/123/image-name.webp"


def test_local_storage_does_not_overwrite_existing_key(tmp_path):
    storage = LocalFileMediaStorage(tmp_path)
    key = "avatars/123/avatar.png"
    storage.put_bytes(key, b"first", "image/png")

    with pytest.raises(FileExistsError):
        storage.put_bytes(key, b"second", "image/png")

    assert storage.read_bytes(key) == b"first"


def test_local_storage_delete_is_idempotent(tmp_path):
    storage = LocalFileMediaStorage(tmp_path)
    key = "products/123/cover.jpg"
    storage.put_bytes(key, b"image", "image/jpeg")

    storage.delete(key)
    storage.delete(key)

    assert not (tmp_path / key).exists()


@pytest.mark.parametrize(
    "key",
    [
        "../outside.png",
        "products/../outside.png",
        "/absolute/path.png",
        "products//image.png",
        "products/./image.png",
        r"products\..\outside.png",
    ],
)
def test_storage_rejects_unsafe_keys(tmp_path, key):
    storage = LocalFileMediaStorage(tmp_path)

    with pytest.raises(ValueError):
        storage.create_read_url(key)


def test_local_storage_rejects_symlink_escape(tmp_path):
    storage_root = tmp_path / "storage"
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    storage = LocalFileMediaStorage(storage_root)
    link = storage_root / "external"
    try:
        link.symlink_to(outside_root, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks are unavailable in this test environment")

    with pytest.raises(ValueError):
        storage.put_bytes("external/secret.png", b"image", "image/png")


@pytest.mark.parametrize(
    ("payload", "content_type"),
    [
        (b"", "image/png"),
        (b"image", "image/svg+xml"),
        (b"image", "text/html"),
    ],
)
def test_storage_rejects_empty_or_unsupported_payload(tmp_path, payload, content_type):
    storage = LocalFileMediaStorage(tmp_path)

    with pytest.raises(ValueError):
        storage.put_bytes("products/1/image.png", payload, content_type)


def test_s3_storage_uses_private_object_and_short_lived_get_url():
    client = FakeS3Client()
    storage = S3MediaStorage(client, "cho-troi-uit-media", read_url_ttl_seconds=900)
    key = "products/123/550e8400-e29b-41d4-a716-446655440000.webp"

    storage.put_bytes(key, b"image", "image/webp")
    url = storage.create_read_url(key)
    storage.delete(key)

    assert url == "https://r2.example.test/signed-object"
    assert client.put_calls == [
        {
            "Bucket": "cho-troi-uit-media",
            "Key": key,
            "Body": b"image",
            "ContentType": "image/webp",
        }
    ]
    assert client.presign_calls == [
        (
            "get_object",
            {
                "Params": {"Bucket": "cho-troi-uit-media", "Key": key},
                "ExpiresIn": 900,
                "HttpMethod": "GET",
            },
        )
    ]
    assert client.delete_calls == [{"Bucket": "cho-troi-uit-media", "Key": key}]


def test_s3_storage_rejects_read_url_lifetime_over_15_minutes():
    with pytest.raises(ValueError):
        S3MediaStorage(FakeS3Client(), "media", read_url_ttl_seconds=901)


def test_local_storage_is_the_default_factory_backend(tmp_path):
    storage = create_media_storage(
        {
            "MEDIA_STORAGE_BACKEND": "local",
            "MEDIA_LOCAL_ROOT": str(tmp_path / "media"),
        }
    )

    assert isinstance(storage, LocalFileMediaStorage)


def test_s3_factory_requires_credentials_without_echoing_secrets():
    with pytest.raises(MediaStorageConfigurationError) as error:
        create_media_storage({"MEDIA_STORAGE_BACKEND": "s3"})

    message = str(error.value)
    assert "MEDIA_S3_ACCESS_KEY_ID" in message
    assert "MEDIA_S3_SECRET_ACCESS_KEY" in message
    assert "secret" not in message.lower()


def test_factory_rejects_unknown_backend():
    with pytest.raises(MediaStorageConfigurationError):
        create_media_storage({"MEDIA_STORAGE_BACKEND": "minio"})
