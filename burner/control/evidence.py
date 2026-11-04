"""Evidence bundles -> Vultr Object Storage (S3-compatible).

Each scan's full evidence (syscall log, captured requests, report) is uploaded
as one tar.gz; the report links to it with a time-limited URL.
"""
import io
import os
import tarfile
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


def upload(scan_dir, key_prefix):
    """Upload scan_dir as <key_prefix>.tar.gz; return (key, presigned url valid 7 days)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.add(scan_dir, arcname=Path(scan_dir).name)
    key = f"{key_prefix}.tar.gz"
    s3 = _s3()
    s3.put_object(Bucket=BUCKET, Key=key, Body=buf.getvalue(), ContentType="application/gzip")
    url = s3.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=7 * 24 * 3600)
    return key, url, len(buf.getvalue())
