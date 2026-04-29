"""Discover FB Page IDs connected to each Instagram account so we can cross-post."""
import os, requests, json

TOKEN = os.environ["META_ACCESS_TOKEN"]

print("=== All FB pages I have access to ===")
pages = requests.get(
    "https://graph.facebook.com/v21.0/me/accounts",
    params={"fields": "id,name,instagram_business_account{id,username}", "access_token": TOKEN, "limit": 50},
    timeout=30,
).json()
print(json.dumps(pages, ensure_ascii=False, indent=2))

print()
print("=== Mapped: FB Page <-> IG account ===")
target_igs = {
    "17841404776930021": "@sivan_linor",
    "17841426368120567": "@linpro.code",
}
for p in pages.get("data", []):
    ig = p.get("instagram_business_account") or {}
    ig_id = ig.get("id")
    label = target_igs.get(ig_id, "")
    print(f"FB page: {p.get('name')!r} (id={p.get('id')})")
    if ig_id:
        print(f"   linked IG: {ig.get('username')} (id={ig_id}) {label}")
    print()
