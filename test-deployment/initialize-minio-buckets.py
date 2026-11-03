
#!/usr/bin/env python3

import hashlib
import hmac
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime, timezone


BUCKETS = ("functions", "templates")
DEFAULT_REGION = "us-east-1"

MAX_RETRIES = 10
RETRY_DELAY = 2
REQUEST_TIMEOUT = 5


class RetryableError(RuntimeError):
    """An error that may disappear when the service becomes available."""


def signing_key(secret, date, region=DEFAULT_REGION, service="s3"):
    key = hmac.new(
        ("AWS4" + secret).encode("utf-8"),
        date.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    key = hmac.new(key, region.encode("utf-8"), hashlib.sha256).digest()
    key = hmac.new(key, service.encode("utf-8"), hashlib.sha256).digest()

    return hmac.new(key, b"aws4_request", hashlib.sha256).digest()


def sign_request(method, path, host, access_key, secret_key, region):
    """Build AWS Signature V4 authentication headers."""

    payload_hash = hashlib.sha256(b"").hexdigest()

    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")

    # Canonical header names must be lowercase.
    canonical_headers_map = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }

    signed_headers = ";".join(sorted(canonical_headers_map))

    canonical_headers = "".join(
        f"{name}:{canonical_headers_map[name].strip()}\n"
        for name in sorted(canonical_headers_map)
    )

    canonical_request = "\n".join([
        method,
        path,
        "",
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    scope = f"{date}/{region}/s3/aws4_request"

    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        scope,
        hashlib.sha256(
            canonical_request.encode("utf-8")
        ).hexdigest(),
    ])

    signature = hmac.new(
        signing_key(secret_key, date, region),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "Host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        ),
    }


def request_s3(endpoint, access_key, secret_key, region, method, bucket):
    """Execute a signed S3 request and return its status and response."""

    parsed = urllib.parse.urlsplit(endpoint)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(
            "ENDPOINT must be a valid HTTP or HTTPS URL"
        )

    if parsed.username or parsed.password:
        raise ValueError(
            "Do not include credentials in the endpoint URL"
        )

    if parsed.query or parsed.fragment:
        raise ValueError(
            "ENDPOINT must not contain a query string or fragment"
        )

    host = parsed.netloc

    # Preserve a possible reverse-proxy path prefix.
    base_path = parsed.path.rstrip("/")
    raw_path = f"{base_path}/{bucket}"

    # Encode the URI consistently for both the signature and request.
    path = urllib.parse.quote(
        urllib.parse.unquote(raw_path),
        safe="/-_.~",
    )

    headers = sign_request(
        method,
        path,
        host,
        access_key,
        secret_key,
        region,
    )

    url = f"{parsed.scheme}://{host}{path}"

    request = urllib.request.Request(
        url,
        data=b"" if method == "PUT" else None,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            body = response.read().decode(
                "utf-8", errors="replace"
            )
            return response.status, body

    except urllib.error.HTTPError as error:
        body = error.read().decode(
            "utf-8", errors="replace"
        )
        return error.code, body

    except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
        raise RetryableError(
            f"{method} {bucket}: connection error: {error}"
        ) from error


def check_response(status, body, operation):
    """Raise an appropriate error for an unsuccessful S3 response."""

    message = (
        f"{operation} failed with HTTP {status}: "
        f"{body.strip() or 'no response body'}"
    )

    if status in (408, 429) or 500 <= status <= 599:
        raise RetryableError(message)

    raise RuntimeError(message)


def create_bucket(endpoint, access_key, secret_key, bucket, region):
    """Create a bucket if it does not already exist."""

    # First check whether the bucket already exists.
    status, body = request_s3(
        endpoint,
        access_key,
        secret_key,
        region,
        "HEAD",
        bucket,
    )

    if status == 200:
        print(f"Bucket '{bucket}' already exists.")
        return

    if status == 404:
        print(f"Bucket '{bucket}' does not exist. Creating it...")
    else:
        check_response(
            status,
            body,
            f"Checking bucket '{bucket}'",
        )

    # Create the bucket.
    status, body = request_s3(
        endpoint,
        access_key,
        secret_key,
        region,
        "PUT",
        bucket,
    )

    if status in (200, 201, 204):
        print(f"Bucket '{bucket}' successfully created.")
        return

    # A 409 can happen if another process created the bucket
    # between our HEAD and PUT requests.
    if status == 409:
        check_status, check_body = request_s3(
            endpoint,
            access_key,
            secret_key,
            region,
            "HEAD",
            bucket,
        )

        if check_status == 200:
            print(f"Bucket '{bucket}' already exists.")
            return

        raise RuntimeError(
            f"Bucket '{bucket}' creation returned HTTP 409, "
            f"and subsequent verification failed: "
            f"HTTP {check_status}: {check_body.strip()}"
        )

    check_response(
        status,
        body,
        f"Creating bucket '{bucket}'",
    )


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "Usage: initialize-minio-buckets.py "
            "ENDPOINT ACCESS_KEY SECRET_KEY"
        )

    endpoint, access_key, secret_key = sys.argv[1:]

    region = os.environ.get(
        "AWS_REGION",
        os.environ.get("AWS_DEFAULT_REGION", DEFAULT_REGION),
    )

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            for bucket in BUCKETS:
                create_bucket(
                    endpoint,
                    access_key,
                    secret_key,
                    bucket,
                    region,
                )

            print("Bucket initialization completed successfully.")
            return

        except RetryableError as error:
            last_error = error

            print(
                f"Attempt {attempt}/{MAX_RETRIES} failed: {error}",
                file=sys.stderr,
            )

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        except (RuntimeError, ValueError) as error:
            raise SystemExit(str(error)) from error

    raise SystemExit(
        f"Could not initialize buckets after "
        f"{MAX_RETRIES} attempts: {last_error}"
    )


if __name__ == "__main__":
    main()
