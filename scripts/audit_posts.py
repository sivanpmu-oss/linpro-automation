"""Audit @linpro.code IG posts vs published_log vs schedule."""
import os, json, requests
from pathlib import Path

TOKEN = os.environ["META_ACCESS_TOKEN"]
IG_USER_ID = "17841426368120567"  # @linpro.code

# 1. Fetch live IG posts (last 30)
print("=== LIVE @linpro.code posts (newest first) ===")
r = requests.get(
    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
    params={
        "fields": "id,caption,timestamp,permalink,media_type",
        "limit": 30,
        "access_token": TOKEN,
    },
    timeout=30,
).json()
posts = r.get("data", [])
print(f"Found {len(posts)} live posts on IG")
print()
for p in posts:
    caption = (p.get("caption") or "")[:80].replace("\n"," ")
    print(f"  {p['timestamp']}  ID={p['id']}  type={p.get('media_type')}")
    print(f"     caption: {caption!r}")
print()

# 2. Compare to published_log
log = json.loads(Path(".").glob("published_log.json").__next__().read_text(encoding="utf-8"))
print("=== published_log.json says ===")
for e in log:
    print(f"  post #{e.get('post_num')}  {e.get('publish_date')}  IG={e.get('ig_post_id')}")
print()

# 3. Cross-check: which logged posts are still live?
live_ids = {p["id"] for p in posts}
print("=== Cross-check: are logged posts still live? ===")
for e in log:
    ig = e.get("ig_post_id")
    if ig in live_ids:
        print(f"  ✓ post #{e.get('post_num')} (IG={ig}) — STILL LIVE")
    else:
        print(f"  ✗ post #{e.get('post_num')} (IG={ig}) — NOT LIVE (deleted or different)")
print()

# 4. Check schedule for upcoming
print("=== Upcoming schedule ===")
schedule = json.loads(Path(".").glob("posts_schedule.json").__next__().read_text(encoding="utf-8"))
for s in schedule[:10]:
    pn = s.get("post_num")
    pd = s.get("publish_date")
    cap_preview = (s.get("caption") or "")[:60].replace("\n"," ")
    img = s.get("image_local","")
    print(f"  post #{pn}  {pd}  img={img}  cap: {cap_preview!r}")
