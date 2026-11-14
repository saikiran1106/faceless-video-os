"""Cloudflare R2 storage helper for the video pipeline.

R2 is the durable source of truth for produced media (videos, thumbnails,
audio, keyframes). Objects are stored/retrieved as raw bytes — nothing is ever
re-encoded, so downloads are byte-identical to what was produced.

Auth comes from env vars (loaded from .env if not already exported):
  R2_ENDPOINT           https://<account_id>.r2.cloudflarestorage.com
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET             default: my-media-bucket
  R2_ACCOUNT_ID         (optional; derived from endpoint if absent)

CLI:
  python tools/storage/r2.py selftest          # upload→presign→download→verify byte-exact
  python tools/storage/r2.py put <local> <key>
  python tools/storage/r2.py url <key> [ttl]
  python tools/storage/r2.py download-url <key> <filename> [ttl]
  python tools/storage/r2.py ls [prefix]
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_BUCKET = "my-media-bucket"

_EXTRA_MIME = {
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".json": "application/json", ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}


def _load_env() -> None:
    """Populate os.environ from .env for any R2_* keys not already set."""
    if os.environ.get("R2_ACCESS_KEY_ID") and os.environ.get("R2_ENDPOINT"):
        return
    env_file = REPO / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def _cfg() -> dict[str, str]:
    _load_env()
    endpoint = os.environ.get("R2_ENDPOINT") or os.environ.get("S3_endpoint", "")
    if endpoint and not endpoint.startswith("http"):
        endpoint = "https://" + endpoint
    cfg = {
        "endpoint": endpoint,
        "access_key": os.environ.get("R2_ACCESS_KEY_ID") or os.environ.get("Access_Key_ID", ""),
        "secret_key": os.environ.get("R2_SECRET_ACCESS_KEY") or os.environ.get("Secret_Access_Key", ""),
        "bucket": os.environ.get("R2_BUCKET", DEFAULT_BUCKET),
    }
    missing = [k for k in ("endpoint", "access_key", "secret_key") if not cfg[k]]
    if missing:
        raise RuntimeError(f"R2 config missing: {missing}. Set R2_ENDPOINT/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY.")
    return cfg


_client_cache: dict[str, Any] = {}


def client():
    """Cached boto3 S3 client pointed at R2 (SigV4)."""
    if "c" not in _client_cache:
        import boto3
        from botocore.config import Config
        c = _cfg()
        _client_cache["c"] = boto3.client(
            "s3",
            endpoint_url=c["endpoint"],
            aws_access_key_id=c["access_key"],
            aws_secret_access_key=c["secret_key"],
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
        )
        _client_cache["bucket"] = c["bucket"]
    return _client_cache["c"]


def bucket() -> str:
    client()
    return _client_cache["bucket"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _content_type(path: Path) -> str:
    ext = path.suffix.lower()
    return _EXTRA_MIME.get(ext) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def put_file(local: str | Path, key: str, content_type: str | None = None) -> dict[str, Any]:
    """Upload a file to R2 byte-for-byte. Returns metadata (r2_key, bytes, sha256, content_type)."""
    local = Path(local)
    if not local.exists():
        raise FileNotFoundError(local)
    ct = content_type or _content_type(local)
    digest = sha256_file(local)
    client().upload_file(
        str(local), bucket(), key,
        ExtraArgs={"ContentType": ct, "Metadata": {"sha256": digest}},
    )
    return {"r2_key": key, "bytes": local.stat().st_size, "sha256": digest, "content_type": ct}


def object_exists(key: str) -> bool:
    from botocore.exceptions import ClientError
    try:
        client().head_object(Bucket=bucket(), Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def presign_get(key: str, ttl: int = 900, download_name: str | None = None) -> str:
    """Presigned GET URL (default 15 min). download_name → attachment download."""
    params: dict[str, Any] = {"Bucket": bucket(), "Key": key}
    if download_name:
        params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'
    return client().generate_presigned_url("get_object", Params=params, ExpiresIn=ttl)


def list_prefix(prefix: str = "") -> list[dict[str, Any]]:
    paginator = client().get_paginator("list_objects_v2")
    out: list[dict[str, Any]] = []
    for page in paginator.paginate(Bucket=bucket(), Prefix=prefix):
        for o in page.get("Contents", []):
            out.append({"key": o["Key"], "bytes": o["Size"]})
    return out


def delete(key: str) -> None:
    client().delete_object(Bucket=bucket(), Key=key)


def sync_dir(local_dir: str | Path, prefix: str) -> list[dict[str, Any]]:
    """Upload every file under local_dir to <prefix>/<relative-path>."""
    local_dir = Path(local_dir)
    results = []
    for p in sorted(local_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(local_dir).as_posix()
            results.append(put_file(p, f"{prefix.rstrip('/')}/{rel}"))
    return results


def _selftest() -> int:
    import tempfile
    import urllib.request
    c = _cfg()
    print(f">> R2 endpoint: {c['endpoint']}  bucket: {c['bucket']}")
    key = "_selftest/roundtrip.bin"
    payload = os.urandom(64 * 1024)  # 64 KB random
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "up.bin"
        src.write_bytes(payload)
        meta = put_file(src, key, content_type="application/octet-stream")
        print(f">> uploaded {meta['bytes']} bytes, sha256={meta['sha256'][:12]}…")
        assert object_exists(key), "head_object says missing after upload"
        url = presign_get(key, ttl=300)
        print(f">> presigned URL ok (len {len(url)})")
        with urllib.request.urlopen(url, timeout=30) as r:
            got = r.read()
        dl_sha = hashlib.sha256(got).hexdigest()
        print(f">> downloaded {len(got)} bytes, sha256={dl_sha[:12]}…")
        assert got == payload, "BYTE MISMATCH — download != upload"
        assert dl_sha == meta["sha256"], "sha256 mismatch"
        delete(key)
        assert not object_exists(key), "delete failed"
    print(">> ✅ R2 selftest passed — byte-exact upload/presign/download/delete all work.")
    return 0


def _main(argv: list[str]) -> int:
    if not argv or argv[0] == "selftest":
        return _selftest()
    cmd = argv[0]
    if cmd == "put" and len(argv) >= 3:
        print(put_file(argv[1], argv[2]))
        return 0
    if cmd == "url" and len(argv) >= 2:
        ttl = int(argv[2]) if len(argv) >= 3 else 900
        print(presign_get(argv[1], ttl=ttl))
        return 0
    if cmd == "download-url" and len(argv) >= 3:
        ttl = int(argv[3]) if len(argv) >= 4 else 900
        print(presign_get(argv[1], ttl=ttl, download_name=argv[2]))
        return 0
    if cmd == "ls":
        for o in list_prefix(argv[1] if len(argv) >= 2 else ""):
            print(f"{o['bytes']:>12}  {o['key']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
