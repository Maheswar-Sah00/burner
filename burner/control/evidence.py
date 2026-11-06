"""Evidence bundles -> Vultr Object Storage (S3-compatible).

Each scan's full evidence (syscall log, captured requests, report) is sealed with a
manifest.json (every file's size and SHA-256) and uploaded as one tar.gz; the report carries
the manifest's hash and links to the bundle with a time-limited URL. The final report JSON is
stored next to it (<prefix>.report.json).
"""
import datetime
import hashlib
import io
import json
import os
import tarfile
import time
from pathlib import Path

from . import vultr

BUCKET = os.environ.get("BURNER_BUCKET", "burner-evidence")
_client = None


def _s3():
    global _client
    if _client is None:
        import boto3
        host, ak, sk = (os.environ.get(k) for k in ("VULTR_S3_HOST", "VULTR_S3_ACCESS_KEY", "VULTR_S3_SECRET_KEY"))
        if not (host and ak and sk):
            sub = next(o for o in vultr._call("GET", "/object-storage").get("object_storages", [])
                       if o["label"] == "burner-evidence" and o["status"] == "active")
            host, ak, sk = sub["s3_hostname"], sub["s3_access_key"], sub["s3_secret_key"]
        _client = boto3.client("s3", endpoint_url=f"https://{host}", aws_access_key_id=ak,
                               aws_secret_access_key=sk, region_name="us-east-1")
        try:
            _client.head_bucket(Bucket=BUCKET)
        except Exception:
            _client.create_bucket(Bucket=BUCKET)
    return _client


MANIFEST = "manifest.json"


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(scan_dir, scan_id=None, verdict=None, vm_id=None, started_at=None, finished_at=None):
    """Every evidence file in scan_dir with its size and SHA-256 (manifest.json itself excluded)."""
    root = Path(scan_dir)
    files = [{"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size, "sha256": _sha256_file(p)}
             for p in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())
             if p.is_file() and p.relative_to(root).as_posix() != MANIFEST]
    iso = lambda t: (datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat(timespec="seconds")
                     if isinstance(t, (int, float)) else t)
    return {"schema": "burner-evidence-manifest/1", "scan_id": scan_id or root.name, "verdict": verdict,
            "vm_id": vm_id, "started_at": iso(started_at), "finished_at": iso(finished_at),
            "sealed_at": iso(time.time()), "hash": "sha256", "file_count": len(files),
            "total_bytes": sum(f["bytes"] for f in files), "files": files}


def write_manifest(scan_dir, **meta):
    """Write <scan_dir>/manifest.json; return (manifest, sha256 of the exact bytes written)."""
    manifest = build_manifest(scan_dir, **meta)
    raw = json.dumps(manifest, indent=1, sort_keys=True).encode()
    (Path(scan_dir) / MANIFEST).write_bytes(raw)
    return manifest, hashlib.sha256(raw).hexdigest()


def verify_manifest(scan_dir):
    """Files whose size/hash no longer match manifest.json (missing files included). [] = intact."""
    root = Path(scan_dir)
    bad = []
    for f in json.loads((root / MANIFEST).read_text())["files"]:
        p = root / f["path"]
        if not p.is_file() or p.stat().st_size != f["bytes"] or _sha256_file(p) != f["sha256"]:
            bad.append(f["path"])
    return bad


def upload(scan_dir, key_prefix, **meta):
    """Seal scan_dir with manifest.json, upload it as <key_prefix>.tar.gz.

    Returns a dict for report["evidence"]: key, presigned url (7 days), bytes, sha256 of the tarball,
    manifest_sha256 and a summary of the files. The final report can't be inside the bundle it describes
    (it carries the bundle's hash), so the bundle holds the report as it was when sealed; the final one is
    uploaded next to it by upload_report().
    """
    manifest, manifest_sha = write_manifest(scan_dir, **meta)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.add(scan_dir, arcname=Path(scan_dir).name)
    body = buf.getvalue()
    key = f"{key_prefix}.tar.gz"
    _s3().put_object(Bucket=BUCKET, Key=key, Body=body, ContentType="application/gzip")
    return {"bucket": BUCKET, "key": key, "url": presign(key), "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(), "manifest_sha256": manifest_sha,
            "file_count": manifest["file_count"], "total_bytes": manifest["total_bytes"],
            "files": [{k: f[k] for k in ("path", "bytes", "sha256")} for f in manifest["files"]]}


def upload_report(report, key_prefix):
    """Store the final report JSON next to the bundle (<key_prefix>.report.json) so it outlives every VM."""
    key = f"{key_prefix}.report.json"
    _s3().put_object(Bucket=BUCKET, Key=key, Body=json.dumps(report, indent=1, default=list).encode(),
                     ContentType="application/json")
    return key


def put_json(key, obj):
    _s3().put_object(Bucket=BUCKET, Key=key, Body=json.dumps(obj, default=list).encode(),
                     ContentType="application/json")


def get_json(key):
    """The stored JSON object, or None if it doesn't exist."""
    try:
        return json.loads(_s3().get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except Exception as e:
        if type(e).__name__ in ("NoSuchKey", "ClientError"):
            return None
        raise


def presign(key, secs=7 * 24 * 3600):
    """A fresh download link (S3 caps presigned links at 7 days, so the web app re-signs on every click)."""
    return _s3().generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=secs)
