#!/usr/bin/env python3
"""
List S3 objects under a prefix → write CSV of image names → create SageMaker manifest.jsonl → (optionally) upload both.
Config file: aws_list_to_manifest.yaml
"""

from __future__ import annotations
import csv, json, os, sys, urllib.parse, logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, List, Dict

import boto3
from botocore.exceptions import ClientError

try:
    import yaml
except Exception as e:
    raise RuntimeError("pyyaml is required (pip install pyyaml)") from e

LOG = logging.getLogger("list_to_manifest")
if not LOG.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    LOG.addHandler(h)
LOG.setLevel(logging.INFO)


# ---------------- Config ----------------
@dataclass
class Cfg:
    region: str
    profile: Optional[str]
    akid: Optional[str]
    secret: Optional[str]
    token: Optional[str]
    bucket: str
    prefix: str
    exts: List[str]
    csv_local: Path
    manifest_local: Path
    csv_s3: Optional[str]
    manifest_s3: Optional[str]
    url_encode: bool
    rw_from: Optional[str]
    rw_to: Optional[str]

def load_cfg(path: str = "aws_list_to_manifest.yaml") -> Cfg:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}

    aws = doc.get("aws") or {}
    s3c = doc.get("s3") or {}
    out = doc.get("outputs") or {}
    opt = doc.get("options") or {}
    rw  = (opt.get("rewrite_prefix") or {}) if isinstance(opt, dict) else {}

    region = aws.get("region") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if not region:
        raise ValueError("Region is required. Set aws.region in config.")

    prefix = s3c.get("prefix") or ""
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    return Cfg(
        region=region,
        profile=aws.get("profile"),
        akid=aws.get("access_key_id"),
        secret=aws.get("secret_access_key"),
        token=aws.get("session_token"),
        bucket=s3c["bucket"],
        prefix=prefix,
        exts=[e.lower() for e in (s3c.get("include_extensions") or [])],
        csv_local=Path(out.get("csv_local", "images_index.csv")),
        manifest_local=Path(out.get("manifest_local", "manifest.jsonl")),
        csv_s3=out.get("csv_s3"),
        manifest_s3=out.get("manifest_s3"),
        url_encode=bool(opt.get("url_encode_keys_in_manifest", True)),
        rw_from=rw.get("from"),
        rw_to=rw.get("to"),
    )


def mk_session(cfg: Cfg) -> boto3.Session:
    if cfg.profile:
        LOG.info("Using AWS profile=%s region=%s", cfg.profile, cfg.region)
        return boto3.Session(profile_name=cfg.profile, region_name=cfg.region)
    if cfg.akid and cfg.secret:
        LOG.info("Using explicit AWS keys (session_token=%s, region=%s)", "yes" if cfg.token else "no", cfg.region)
        return boto3.Session(
            aws_access_key_id=cfg.akid,
            aws_secret_access_key=cfg.secret,
            aws_session_token=cfg.token,
            region_name=cfg.region,
        )
    LOG.info("Using default AWS provider chain (region=%s)", cfg.region)
    return boto3.Session(region_name=cfg.region)


# ---------------- S3 listing ----------------
def list_s3_images(s3, bucket: str, prefix: str, exts: List[str]) -> Iterable[Dict]:
    """
    Yields dicts: {key,size,last_modified,etag}
    If exts is empty, returns all objects under prefix.
    """
    paginator = s3.get_paginator("list_objects_v2")
    page_iter = paginator.paginate(Bucket=bucket, Prefix=prefix)

    total = 0
    for page in page_iter:
        contents = page.get("Contents", [])
        for obj in contents:
            key = obj["Key"]
            if not key or key.endswith("/"):
                continue
            if exts:
                low = key.lower()
                if not any(low.endswith(e) for e in exts):
                    continue
            yield {
                "key": key,
                "size": obj.get("Size"),
                "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
                "etag": obj.get("ETag"),
            }
            total += 1
        LOG.debug("Scanned page, cumulative objects matched: %d", total)
    LOG.info("Total objects matched: %d", total)


# ---------------- Writers ----------------
def write_csv(rows: Iterable[Dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key", "size", "last_modified", "etag"])
        w.writeheader()
        for row in rows:
            w.writerow(row)
            count += 1
    return count


def rewrite_key(key: str, rw_from: Optional[str], rw_to: Optional[str]) -> str:
    if rw_from and rw_to and key.startswith(rw_from):
        return rw_to + key[len(rw_from):]
    return key


def write_manifest(bucket: str, keys: Iterable[str], path: Path, url_encode: bool) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for k in keys:
            k2 = urllib.parse.quote(k, safe="/") if url_encode else k
            f.write(json.dumps({"source": f"s3://{bucket}/{k2}"}) + "\n")
            n += 1
    return n


def upload_file(session: boto3.Session, local_path: Path, s3_uri: str):
    if not s3_uri:
        return
    assert s3_uri.startswith("s3://"), "Destination must be s3://bucket/key"
    _, rest = s3_uri.split("s3://", 1)
    bucket, key = rest.split("/", 1)
    session.client("s3").upload_file(str(local_path), bucket, key)
    LOG.info("Uploaded %s → s3://%s/%s", local_path, bucket, key)


# ---------------- Main ----------------
def main():
    cfg = load_cfg()
    session = mk_session(cfg)
    s3 = session.client("s3")

    # Check List permission early (clear error if denied)
    try:
        s3.list_objects_v2(Bucket=cfg.bucket, Prefix=cfg.prefix, MaxKeys=1)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in {"AccessDenied"}:
            raise PermissionError(
                f"Access denied listing s3://{cfg.bucket}/{cfg.prefix}. "
                "The identity running this script needs s3:ListBucket on the bucket (scoped to this prefix)."
            ) from e
        raise

    # 1) List → rows
    rows = list(list_s3_images(s3, cfg.bucket, cfg.prefix, cfg.exts))
    if not rows:
        LOG.warning("No objects matched prefix='%s' and extensions=%s", cfg.prefix, cfg.exts)

    # 2) Write CSV
    csv_count = write_csv(rows, cfg.csv_local)
    LOG.info("Wrote %d rows → %s", csv_count, cfg.csv_local)

    # 3) Build manifest keys (with optional prefix rewrite)
    keys = [rewrite_key(r["key"], cfg.rw_from, cfg.rw_to) for r in rows]

    # 4) Write manifest
    man_count = write_manifest(cfg.bucket, keys, cfg.manifest_local, cfg.url_encode)
    LOG.info("Wrote %d lines → %s", man_count, cfg.manifest_local)

    # 5) Optional uploads
    if cfg.csv_s3:
        upload_file(session, cfg.csv_local, cfg.csv_s3)
    if cfg.manifest_s3:
        upload_file(session, cfg.manifest_local, cfg.manifest_s3)

    LOG.info("Done.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        LOG.error(str(e))
        raise
