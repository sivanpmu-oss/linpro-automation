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

    print(f"\n--- POST {base}/oauth/token ---")
    r = requests.post(f"{base}/oauth/token", json=payload, timeout=20)
    print(f"status: {r.status_code}")
    if r.status_code != 200:
        print(f"body: {r.text!r}")
        print("=== AUTH FAILED ===")
        return 1

    data = r.json()
    access_token = data.get("token")
    print(f"✅ Got access_token sha8={hashlib.sha256(access_token.encode()).hexdigest()[:8]} expires_at_epoch={data.get('expire')}")

    bearer = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    print(f"\n--- GET {base}/lists (full output) ---")
    r = requests.get(f"{base}/lists", headers=bearer, timeout=20)
    print(f"status: {r.status_code}")
    if r.status_code == 200:
        lists = r.json().get("data", [])
        print(f"\nרשימות זמינות ({len(lists)}):")
        for L in lists:
            print(f"  ID {L.get('id')} — {L.get('name')!r}  (created {L.get('created')})")
    else:
        print(f"body: {r.text!r}")

    print(f"\n--- GET {base}/tag (account-level tags) ---")
    r = requests.get(f"{base}/tag", headers=bearer, timeout=20)
    print(f"status: {r.status_code}")
    if r.status_code == 200:
        print(f"body: {r.text[:1000]!r}")

    print("\n=== AUTH OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
