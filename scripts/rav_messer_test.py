"""Diagnostic test for Rav-Messer (Responder) API auth."""
import hashlib
import os
import time
import uuid
import requests


def fp(s: str) -> str:
    """Hash-based fingerprint — won't be masked by GitHub Actions."""
    if not s:
        return "<empty>"
    h = hashlib.sha256(s.encode()).hexdigest()[:8]
    return f"sha256:{h} chars-count:{len(s):03d}"


def auth_header(c_id, c_secret, u_key, u_token):
    nonce = str(uuid.uuid4())
    ts = str(int(time.time()))
    c_md5 = hashlib.md5((c_secret + nonce).encode()).hexdigest()
    u_md5 = hashlib.md5((u_token + nonce).encode()).hexdigest()
    return (f"c_key={c_id},c_secret={c_md5},"
            f"u_key={u_key},u_secret={u_md5},"
            f"nonce={nonce},timestamp={ts}")


def main():
    c_id = os.environ.get("RAV_CLIENT_ID", "")
    c_secret = os.environ.get("RAV_CLIENT_SECRET", "")
    u_key = os.environ.get("RAV_CLIENT_NAME", "")
    u_token = os.environ.get("RAV_USER_TOKEN", "")

    print("=== Rav-Messer auth test ===")
    print(f"RAV_CLIENT_ID:     {fp(c_id)}")
    print(f"RAV_CLIENT_SECRET: {fp(c_secret)}")
    print(f"RAV_CLIENT_NAME:   {fp(u_key)}")
    print(f"RAV_USER_TOKEN:    {fp(u_token)}")

    expected = os.environ.get("EXPECTED_SECRET_SHA8", "")
    if expected:
        actual = hashlib.sha256(c_secret.encode()).hexdigest()[:8]
        print(f"expected_sha8: {expected}  actual_sha8: {actual}  match: {expected == actual}")

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
        body = r.text
        if len(body) > 1500:
            body = body[:1500] + "...[truncated]"
        print(f"body-len: {len(r.text)}")
        print(f"body: {body!r}")
        if r.status_code == 200:
            overall_ok = True

    print("\n=== result ===")
    print("AUTH OK" if overall_ok else "AUTH FAILED on all endpoints")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
