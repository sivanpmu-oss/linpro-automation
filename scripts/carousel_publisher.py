"""
Daily CAROUSEL publisher for @linpro.code (runs from GitHub Actions).
Reads carousels_schedule.json, publishes today's carousel (multi-image) at 22:00 IL.
Idempotent via carousels_published_log.json. Images hosted via raw.githubusercontent.
"""
import json, os, sys, time, requests
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEDULE_FILE = REPO_ROOT / "carousels_schedule.json"
PUBLISHED_FILE = REPO_ROOT / "carousels_published_log.json"
IG_USER_ID = "17841426368120567"   # @linpro.code
FB_PAGE_ID = "1147869965069116"
GITHUB_REPO = "sivanpmu-oss/linpro-automation"
TOKEN = os.environ["META_ACCESS_TOKEN"]
TZ = ZoneInfo("Asia/Jerusalem")


def log(m):
    print(f"[{datetime.now(TZ):%Y-%m-%d %H:%M:%S} IL] {m}", flush=True)


def get_page_token():
    r = requests.get("https://graph.facebook.com/v21.0/me/accounts",
                     params={"fields": "id,access_token", "access_token": TOKEN, "limit": 100},
                     timeout=30).json()
    for p in r.get("data", []):
        if p["id"] == FB_PAGE_ID:
            return p["access_token"]
    raise RuntimeError("page token not found")


def post_retry(url, data, what, tries=6):
    for i in range(tries):
        r = requests.post(url, data=data, timeout=60).json()
        if "id" in r:
            return r
        err = r.get("error", {})
        if err.get("is_transient") or err.get("code") in (1, 2):
            log(f"  {what} transient (try {i+1}), waiting"); time.sleep(8); continue
        raise RuntimeError(f"{what} failed: {r}")
    raise RuntimeError(f"{what} still failing after {tries}")


now = datetime.now(TZ)
if now.hour >= 22:
    target = now.strftime("%Y-%m-%d")
elif now.hour < 6:
    target = (now.replace(hour=12) - timedelta(days=1)).strftime("%Y-%m-%d")
else:
    log(f"Outside window (hour={now.hour}) — exit"); sys.exit(0)

schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
todays = [p for p in schedule if p["publish_date"] == target]
if not todays:
    log(f"No carousel for {target} — exit"); sys.exit(0)
post = todays[0]

published = json.loads(PUBLISHED_FILE.read_text(encoding="utf-8")) if PUBLISHED_FILE.exists() else []
if any(e["post_num"] == post["post_num"] and e.get("ig_post_id") for e in published):
    log(f"Carousel #{post['post_num']} already published — exit"); sys.exit(0)

log(f"Publishing carousel #{post['post_num']} ({len(post['images'])} slides) for {target}")
PT = get_page_token()

children = []
for img in post["images"]:
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{img}"
    r = post_retry(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
                   {"image_url": url, "is_carousel_item": "true", "access_token": PT},
                   f"child {img}")
    children.append(r["id"])
    time.sleep(2)

parent = post_retry(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
                    {"media_type": "CAROUSEL", "caption": post["caption"],
                     "children": ",".join(children), "access_token": PT}, "parent")["id"]
time.sleep(12)
res = post_retry(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish",
                 {"creation_id": parent, "access_token": PT}, "publish")
log(f"SUCCESS: carousel #{post['post_num']} -> {res['id']}")

published.append({"post_num": post["post_num"], "publish_date": target,
                  "ig_post_id": res["id"],
                  "published_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")})
PUBLISHED_FILE.write_text(json.dumps(published, indent=2, ensure_ascii=False), encoding="utf-8")
log("Logged.")
