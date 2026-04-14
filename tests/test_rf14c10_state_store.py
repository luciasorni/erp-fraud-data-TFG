from __future__ import annotations

import io
import json

from src.erp_fraud.storage.state_store import (
    build_state_s3_location,
    read_last_artifact_hash_state,
    write_last_artifact_hash_state,
)


class _FakeClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class _FakeS3Client:
    def __init__(self) -> None:
        self.store: dict[tuple[str, str], bytes] = {}

    def get_object(self, *, Bucket: str, Key: str):
        value = self.store.get((Bucket, Key))
        if value is None:
            raise _FakeClientError("NoSuchKey")
        return {"Body": io.BytesIO(value)}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str | None = None):
        self.store[(Bucket, Key)] = Body
        return {"ETag": "fake"}


def test_rf14c10_build_state_location_by_scope() -> None:
    p2p = build_state_s3_location(process_scope="p2p", s3_state_uri="s3://demo/state/")
    o2c = build_state_s3_location(process_scope="o2c", s3_state_uri="s3://demo/state/")
    both = build_state_s3_location(process_scope="both", s3_state_uri="s3://demo/state/")
    assert p2p["uri"] == "s3://demo/state/p2p/last_artifact_hash.json"
    assert o2c["uri"] == "s3://demo/state/o2c/last_artifact_hash.json"
    assert both["uri"] == "s3://demo/state/both/last_artifact_hash.json"


def test_rf14c10_read_state_existing() -> None:
    fake = _FakeS3Client()
    key = "state/p2p/last_artifact_hash.json"
    fake.store[("demo", key)] = json.dumps(
        {
            "last_artifact_hash": "abc",
            "last_run_id": "run-1",
            "process_scope": "p2p",
            "updated_at": "2026-04-14T00:00:00+00:00",
        }
    ).encode("utf-8")
    out = read_last_artifact_hash_state(
        process_scope="p2p",
        s3_state_uri="s3://demo/state/",
        s3_client=fake,
    )
    assert out is not None
    assert out["last_artifact_hash"] == "abc"


def test_rf14c10_read_state_missing_returns_none() -> None:
    fake = _FakeS3Client()
    out = read_last_artifact_hash_state(
        process_scope="o2c",
        s3_state_uri="s3://demo/state/",
        s3_client=fake,
    )
    assert out is None


def test_rf14c10_write_state_new_and_format() -> None:
    fake = _FakeS3Client()
    payload = write_last_artifact_hash_state(
        last_artifact_hash="hash-1",
        last_run_id="run-1",
        process_scope="both",
        s3_state_uri="s3://demo/state/",
        updated_at="2026-04-14T00:00:00+00:00",
        s3_client=fake,
    )
    assert payload["last_artifact_hash"] == "hash-1"
    assert payload["last_run_id"] == "run-1"
    assert payload["process_scope"] == "both"
    raw = fake.store[("demo", "state/both/last_artifact_hash.json")]
    parsed = json.loads(raw.decode("utf-8"))
    assert set(parsed.keys()) == {"last_artifact_hash", "last_run_id", "process_scope", "updated_at"}


def test_rf14c10_write_state_overwrite_existing() -> None:
    fake = _FakeS3Client()
    write_last_artifact_hash_state(
        last_artifact_hash="hash-old",
        last_run_id="run-old",
        process_scope="p2p",
        s3_state_uri="s3://demo/state/",
        updated_at="2026-04-14T00:00:00+00:00",
        s3_client=fake,
    )
    write_last_artifact_hash_state(
        last_artifact_hash="hash-new",
        last_run_id="run-new",
        process_scope="p2p",
        s3_state_uri="s3://demo/state/",
        updated_at="2026-04-14T01:00:00+00:00",
        s3_client=fake,
    )
    parsed = json.loads(fake.store[("demo", "state/p2p/last_artifact_hash.json")].decode("utf-8"))
    assert parsed["last_artifact_hash"] == "hash-new"
    assert parsed["last_run_id"] == "run-new"
    assert parsed["updated_at"] == "2026-04-14T01:00:00+00:00"

