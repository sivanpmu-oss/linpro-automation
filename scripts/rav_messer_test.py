"""Count subscribers per Rav-Messer list."""
import hashlib
import os
import requests


def main():
    c_id = os.environ["RAV_CLIENT_ID"]
    c_secret = os.environ["RAV_CLIENT_SECRET"]
    u_token = os.environ["RAV_USER_TOKEN"]
    base = "https://graph.responder.live/v2"

    r = requests.post(f"{base}/oauth/token", json={
        "grant_type": "client_credentials", "scope": "*",
        "client_id": int(c_id), "client_secret": c_secret, "user_token": u_token,
    }, timeout=20)
    r.raise_for_status()
    token = r.json()["token"]
    bearer = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    lists = requests.get(f"{base}/lists", headers=bearer, timeout=20).json().get("data", [])
    print(f"\n=== Subscriber counts ({len(lists)} lists) ===\n")

    rows = []
    for L in lists:
        lid = L["id"]
        name = L["name"]
        # First call to discover pagination metadata
        r = requests.get(f"{base}/lists/{lid}/subscribers", headers=bearer, timeout=20)
        if r.status_code != 200:
            rows.append((lid, name, f"ERROR {r.status_code}: {r.text[:100]}"))
            continue
        body = r.json()
        # Look for total count fields commonly present
        candidates = ['total', 'count', 'total_count', 'totalRecords', 'totalCount', 'subscribers_count']
        total = None
        for k in candidates:
            if k in body:
                total = body[k]
                break
        # Also check pagination object
        if total is None and 'pagination' in body:
            for k in ['total', 'total_count', 'count', 'records']:
                if k in body['pagination']:
                    total = body['pagination'][k]
                    break
        # Else count items in data
        data_len = len(body.get('data', []))
        rows.append((lid, name, total, data_len, list(body.keys())))

    print(f"{'ID':<8} {'Total':<8} {'Page':<6} {'Name'}")
    for r in rows:
        if len(r) == 3:
            print(f"{r[0]:<8} {r[2]}")
        else:
            lid, name, total, data_len, keys = r
            t = total if total is not None else "?"
            print(f"{lid:<8} {str(t):<8} {data_len:<6} {name}")

    # Also print full top-level keys of one response so we can see structure
    if rows:
        print(f"\nResponse top-level keys for first list: {rows[0][4] if len(rows[0]) > 4 else 'N/A'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
