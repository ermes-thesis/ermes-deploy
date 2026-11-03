#!/usr/bin/env python3
import hashlib
import hmac
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone


def signing_key(secret, date, region="us-east-1", service="s3"):
    key = hmac.new(("AWS4" + secret).encode(), date.encode(), hashlib.sha256).digest()
    key = hmac.new(key, region.encode(), hashlib.sha256).digest()
    key = hmac.new(key, service.encode(), hashlib.sha256).digest()
    return hmac.new(key, b"aws4_request", hashlib.sha256).digest()


def create_bucket(endpoint, access_key, secret_key, bucket):
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.netloc
    path = "/" + bucket
    payload_hash = hashlib.sha256(b"").hexdigest()
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    headers = {
        "Host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_headers = "".join(
        f"{name}:{headers[name]}\n" for name in signed_headers.split(";")
    )
    canonical_request = "\n".join(
        ["PUT", path, "", canonical_headers, signed_headers, payload_hash]
    )
    scope = f"{date}/us-east-1/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    signature = hmac.new(
        signing_key(secret_key, date),
        string_to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()
    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    request = urllib.request.Request(
        endpoint + path, data=b"", headers=headers, method="PUT"
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status not in (200, 201, 204):
                raise RuntimeError(f"unexpected status {response.status}")
    except urllib.error.HTTPError as error:
        if error.code != 409:
            raise


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: initialize-minio-buckets.py ENDPOINT ACCESS_KEY SECRET_KEY"
        )
    endpoint, access_key, secret_key = sys.argv[1:]
    last_error = None
    for _ in range(30):
        try:
            for bucket in ("functions", "templates"):
                create_bucket(endpoint, access_key, secret_key, bucket)
            return
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as error:
            last_error = error
            time.sleep(2)
    raise RuntimeError(f"could not initialize MinIO buckets: {last_error}")


if __name__ == "__main__":
    main()
