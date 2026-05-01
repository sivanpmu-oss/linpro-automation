"""Compare every live IG caption against every schedule caption to find duplicates."""
import os, json, requests
from pathlib import Path
from difflib import SequenceMatcher

TOKEN = os.environ["META_ACCESS_TOKEN"]
IG_USER_ID = "17841426368120567"  # @linpro.code

# Get FULL captions
r = requests.get(
    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
    params={"fields": "id,caption,timestamp", "limit": 50, "access_token": TOKEN},
    timeout=30,
).json()
live = r.get("data", [])
print(f"Live posts on @linpro.code: {len(live)}")

# Load schedule
schedule = json.loads(Path("posts_schedule.json").read_text(encoding="utf-8"))
print(f"Scheduled posts: {len(schedule)}")
print()

def first_n(s, n=120):
    return (s or "").replace("\n"," ").strip()[:n]

def similarity(a, b):
    return SequenceMatcher(None, a or "", b or "").ratio()

# For each schedule entry, find best match among live posts
print("=== Duplicate detection (similarity > 0.6 = likely duplicate) ===")
duplicates = []
for s in schedule[:15]:  # check first 15
    sched_cap = s.get("caption","")
    best_match = None
    best_score = 0
    for L in live:
        sc = similarity(first_n(sched_cap, 200), first_n(L.get("caption",""), 200))
        if sc > best_score:
            best_score = sc
            best_match = L
    flag = "🚨 DUPLICATE" if best_score > 0.6 else "  unique" if best_score < 0.3 else "  ?"
    print(f"\npost #{s.get('post_num')} ({s.get('publish_date')}): score={best_score:.2f} {flag}")
    print(f"  schedule: {first_n(sched_cap, 100)!r}")
    if best_match and best_score > 0.4:
        print(f"  live    : {first_n(best_match.get('caption',''), 100)!r}")
        print(f"  live ID : {best_match['id']}  date: {best_match['timestamp']}")
    if best_score > 0.6:
        duplicates.append({
            "post_num": s.get("post_num"),
            "publish_date": s.get("publish_date"),
            "live_ig_id": best_match["id"],
            "live_date": best_match["timestamp"],
            "similarity": round(best_score, 2),
        })

print()
print("=== DUPLICATES SUMMARY ===")
print(json.dumps(duplicates, indent=2, ensure_ascii=False))
print()
print(f"Total duplicates found: {len(duplicates)}")
