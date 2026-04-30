import os
import requests

TOKEN = os.environ["META_ACCESS_TOKEN"]
FB_PAGE_ID = "112225864303013"

print("=== Token info ===")
r = requests.get("https://graph.facebook.com/v21.0/debug_token",
                 params={"input_token": TOKEN, "access_token": TOKEN}, timeout=20).json()
print(f"app_id: {r.get('data',{}).get('app_id')}")
print(f"is_valid: {r.get('data',{}).get('is_valid')}")
print(f"expires_at: {r.get('data',{}).get('expires_at')}")
print(f"scopes: {r.get('data',{}).get('scopes')}")
print(f"data_access_expires_at: {r.get('data',{}).get('data_access_expires_at')}")

print("\n=== /me/accounts (page list) ===")
pages = requests.get("https://graph.facebook.com/v21.0/me/accounts",
                     params={"fields": "id,name,access_token,tasks", "access_token": TOKEN},
                     timeout=20).json()
for p in pages.get("data", []):
    print(f"page: {p['name']}  id={p['id']}  tasks={p.get('tasks',[])}")

print("\n=== Direct FB page debug ===")
page = next((p for p in pages.get("data", []) if p["id"] == FB_PAGE_ID), None)
if not page:
    print(f"❌ FB_PAGE_ID {FB_PAGE_ID} NOT FOUND in /me/accounts")
else:
    print(f"✓ Found page: {page['name']}")
    print(f"  tasks: {page.get('tasks')}")
    page_token = page["access_token"]
    # Debug page token scopes
    r = requests.get("https://graph.facebook.com/v21.0/debug_token",
                     params={"input_token": page_token, "access_token": TOKEN}, timeout=20).json()
    print(f"  page token scopes: {r.get('data',{}).get('scopes')}")
    print(f"  page token type: {r.get('data',{}).get('type')}")

    # Try a "test post" with a tiny text-only post to see what works
    print("\n=== Try text-only post (should work if posting permission) ===")
    r = requests.post(f"https://graph.facebook.com/v21.0/{FB_PAGE_ID}/feed",
                      data={"message": "(test - will delete)", "access_token": page_token, "published": "false"},
                      timeout=30).json()
    print(f"  text post response: {r}")
