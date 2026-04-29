"""Check what permissions the current Meta token has."""
import os, requests, json

TOKEN = os.environ["META_ACCESS_TOKEN"]

# Get all permissions
perms = requests.get(
    "https://graph.facebook.com/v21.0/me/permissions",
    params={"access_token": TOKEN},
    timeout=30,
).json()
print("=== Current token permissions ===")
print(json.dumps(perms, indent=2))

print()
print("=== Token info (debug) ===")
debug = requests.get(
    f"https://graph.facebook.com/v21.0/debug_token",
    params={"input_token": TOKEN, "access_token": TOKEN},
    timeout=30,
).json()
print(json.dumps(debug, indent=2)[:2000])

print()
print("=== Page tokens — try posting tiny test to FB ===")
pages = requests.get(
    "https://graph.facebook.com/v21.0/me/accounts",
    params={"fields": "id,name,access_token,perms,tasks", "access_token": TOKEN, "limit": 50},
    timeout=30,
).json()
for p in pages.get("data", []):
    name = p.get("name")
    print(f"\nPage: {name} (id={p.get('id')})")
    print(f"  perms: {p.get('perms', [])}")
    print(f"  tasks: {p.get('tasks', [])}")
