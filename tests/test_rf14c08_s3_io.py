from __future__ import annotations

from pathlib import Path

import pytest

from src.erp_fraud.storage.s3_io import (
    download_s3_prefix_to_local_dir,
    parse_s3_uri,
    upload_local_dir_to_s3_prefix,
)


class _FakePaginator:
    def __init__(self, store: dict[tuple[str, str], bytes]) -> None:
        self._store = store

    def paginate(self, *, Bucket: str, Prefix: str = ""):
        contents = []
        for (bucket, key), payload in sorted(self._store.items()):
            if bucket != Bucket:
                continue
            if Prefix and not key.startswith(Prefix):
                continue
            contents.append({"Key": key, "Size": len(payload)})
        yield {"Contents": contents}


class _FakeS3Client:
    def __init__(self) -> None:
        self.store: dict[tuple[str, str], bytes] = {}

    def get_paginator(self, name: str):
        assert name == "list_objects_v2"
        return _FakePaginator(self.store)

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.store[(bucket, key)] = Path(filename).read_bytes()

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        payload = self.store[(bucket, key)]
        out = Path(filename)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(payload)

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:
        self.store[(Bucket, Key)] = Body


def test_rf14c08_parse_s3_uri_valid() -> None:
    bucket, prefix = parse_s3_uri("s3://my-bucket/path/to/prefix/")
    assert bucket == "my-bucket"
    assert prefix == "path/to/prefix/"


def test_rf14c08_parse_s3_uri_invalid() -> None:
    with pytest.raises(ValueError, match="S3 URI inválida"):
        parse_s3_uri("http://my-bucket/path")


def test_rf14c08_upload_local_dir_to_s3_preserves_relative_paths(tmp_path: Path) -> None:
    local_dir = tmp_path / "local"
    (local_dir / "a").mkdir(parents=True, exist_ok=True)
    (local_dir / "a" / "f1.txt").write_text("uno", encoding="utf-8")
    (local_dir / "b.txt").write_text("dos", encoding="utf-8")
    fake = _FakeS3Client()

    out = upload_local_dir_to_s3_prefix(
        local_dir=local_dir,
        s3_uri="s3://demo-bucket/runs/run-1/",
        s3_client=fake,
    )

    assert out["uploaded_count"] == 2
    assert "runs/run-1/a/f1.txt" in out["uploaded_keys"]
    assert "runs/run-1/b.txt" in out["uploaded_keys"]
    assert fake.store[("demo-bucket", "runs/run-1/a/f1.txt")] == b"uno"
    assert fake.store[("demo-bucket", "runs/run-1/b.txt")] == b"dos"


def test_rf14c08_download_s3_prefix_to_local_preserves_relative_paths(tmp_path: Path) -> None:
    fake = _FakeS3Client()
    fake.put_object(Bucket="demo-bucket", Key="inputs/dir/file1.csv", Body=b"f1")
    fake.put_object(Bucket="demo-bucket", Key="inputs/file2.csv", Body=b"f2")
    fake.put_object(Bucket="demo-bucket", Key="other/file3.csv", Body=b"x")
    local_dir = tmp_path / "download"

    out = download_s3_prefix_to_local_dir(
        s3_uri="s3://demo-bucket/inputs/",
        local_dir=local_dir,
        s3_client=fake,
    )

    assert out["downloaded_count"] == 2
    assert (local_dir / "dir" / "file1.csv").read_bytes() == b"f1"
    assert (local_dir / "file2.csv").read_bytes() == b"f2"
    assert not (local_dir / "other" / "file3.csv").exists()


def test_rf14c08_prefix_empty_behavior(tmp_path: Path) -> None:
    bucket, prefix = parse_s3_uri("s3://demo-bucket")
    assert bucket == "demo-bucket"
    assert prefix == ""

    local_dir = tmp_path / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "x.txt").write_text("x", encoding="utf-8")
    fake = _FakeS3Client()
    upload_out = upload_local_dir_to_s3_prefix(
        local_dir=local_dir,
        s3_uri="s3://demo-bucket",
        s3_client=fake,
    )
    assert upload_out["uploaded_keys"] == ["x.txt"]

    download_dir = tmp_path / "down"
    download_out = download_s3_prefix_to_local_dir(
        s3_uri="s3://demo-bucket",
        local_dir=download_dir,
        s3_client=fake,
    )
    assert download_out["downloaded_count"] == 1
    assert (download_dir / "x.txt").read_text(encoding="utf-8") == "x"
