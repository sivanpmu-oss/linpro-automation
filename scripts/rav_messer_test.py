"""Diagnostic test for Rav-Messer (Responder) API auth.

Tries GET /main/lists with HMAC-MD5 auth scheme and prints the full
response so we can see if the new client_secret resolved the prior 500.
Does NOT print secret values — only fingerprints (length + first/last 2 chars).
"""
import hashlib
import os
import time
import uuid
import requests


def fp(s: str) -> str:
    if not s:
        return "<empty>"
    if len(s) < 6:
        return f"len={len(s)}"
    return f"len={len(s)} {s[:2]}..{s[-2:]}"


def auth_header(c_id: str, c_secret: str, u_key: str, u_token: str) -> str:
    nonce = str(uuid.uuid4())
    ts = str(int(time.time()))
    c_md5 = hashlib.md5((c_secret + nonce).encode()).hexdigest()
    u_md5 = hashlib.md5((u_token + nonce).encode()).hexdigest()
    return (
        f"c_key={c_id},c_secret={c_md5},"
        f"u_key={u_key},u_secret={u_md5},"
        f"nonce={nonce},timestamp={ts}"
    )


def main() -> int:
    c_id = os.environ.get("RAV_CLIENT_ID", "")
    c_secret = os.environ.get("RAV_CLIENT_SECRET", "")
    u_key = os.environ.get("RAV_CLIENT_NAME", "")
    u_token = os.environ.get("RAV_USER_TOKEN", "")

    print("=== Rav-Messer auth test ===")
    print(f"RAV_CLIENT_ID:     {fp(c_id)}")
    print(f"RAV_CLIENT_SECRET: {fp(c_secret)}")
    print(f"RAV_CLIENT_NAME:   {fp(u_key)}")
    print(f"RAV_USER_TOKEN:    {fp(u_token)}")

    if not all([c_id, c_secret, u_key, u_token]):
        print("ERROR: missing one or more secrets")
        return 2

    base = "https://api.responder.co.il/main"
    endpoints = ["/lists", "/Messages", "/PersonalFields"]

    overall_ok = False
    for ep in endpoints:
        url = base + ep
        header = auth_header(c_id, c_secret, u_key, u_token)
        print(f"\n--- GET {url} ---")
        try:
            r = requests.get(
                url,
                headers={"Authorization": header, "Accept": "application/json"},
                timeout=20,
            )
        except requests.RequestException as e:
            print(f"network error: {e}")
            continue
        print(f"status: {r.status_code}")
        print(f"resp headers: {dict(r.headers)}")
        body = r.text
        if len(body) > 1500:
            body = body[:1500] + "...[truncated]"
        print(f"body: {body!r}")
        if r.status_code == 200:
            overall_ok = True

    print("\n=== result ===")
    print("AUTH OK" if overall_ok else "AUTH FAILED on all endpoints")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
