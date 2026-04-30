"""Diagnostic test for Rav-Messer (Responder) API V2.0 — OAuth Bearer flow."""
import hashlib
import json
import os
import requests


def fp(s):
    if not s:
        return "<empty>"
    return f"sha256:{hashlib.sha256(s.encode()).hexdigest()[:8]} chars-count:{len(s):03d}"


def main():
    c_id = os.environ.get("RAV_CLIENT_ID", "")
    c_secret = os.environ.get("RAV_CLIENT_SECRET", "")
    u_token = os.environ.get("RAV_USER_TOKEN", "")
    # RAV_CLIENT_NAME is the connection identifier — not used in V2 OAuth flow

    print("=== Rav-Messer V2 OAuth test ===")
    print(f"RAV_CLIENT_ID:     {fp(c_id)}")
    print(f"RAV_CLIENT_SECRET: {fp(c_secret)}")
    print(f"RAV_USER_TOKEN:    {fp(u_token)}")

    if not all([c_id, c_secret, u_token]):
        print("ERROR: missing one or more secrets")
        return 2

    base = "https://graph.responder.live/v2"

    payload = {
        "grant_type": "client_credentials",
        "scope": "*",
        "client_id": int(c_id),
        "client_secret": c_secret,
        "user_token": u_token,
    }

    print(f"\n--- POST {base}/oauth/token (JSON body) ---")
    try:
        r = requests.post(
            f"{base}/oauth/token",
            json=payload,
            headers={"Accept": "application/json"},
            timeout=20,
        )
    except requests.RequestException as e:
        print(f"network error: {e}")
        return 1
    print(f"status: {r.status_code}")
    body = r.text
    if len(body) > 2000:
        body = body[:2000] + "...[truncated]"
    print(f"body: {body!r}")

    if r.status_code != 200:
        # Try form-encoded as fallback
        print(f"\n--- POST {base}/oauth/token (form-encoded body) ---")
        r2 = requests.post(
            f"{base}/oauth/token",
            data=payload,
            headers={"Accept": "application/json"},
            timeout=20,
        )
        print(f"status: {r2.status_code}")
        body2 = r2.text
        if len(body2) > 2000:
            body2 = body2[:2000] + "...[truncated]"
        print(f"body: {body2!r}")
        if r2.status_code == 200:
            r = r2

    if r.status_code != 200:
        print("\n=== AUTH FAILED ===")
        return 1

    data = r.json()
    access_token = data.get("token")
    if not access_token:
        print("ERROR: no 'token' field in response")
        print(f"response keys: {list(data.keys())}")
        return 1

    print(f"\n✅ Got access_token (length={len(access_token)}, sha8={hashlib.sha256(access_token.encode()).hexdigest()[:8]})")
    print(f"account info — name: {data.get('name')}, username: {data.get('username')}")

    # Try /me and /lists with Bearer token
    bearer_headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    for ep in ["/me", "/lists"]:
        url = base + ep
        print(f"\n--- GET {url} ---")
        try:
            r = requests.get(url, headers=bearer_headers, timeout=20)
        except requests.RequestException as e:
            print(f"network error: {e}")
            continue
        print(f"status: {r.status_code}")
        body = r.text
        if len(body) > 800:
            body = body[:800] + "...[truncated]"
        print(f"body: {body!r}")

    print("\n=== AUTH OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
