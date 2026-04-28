"""
Daily post publisher — runs from GitHub Actions at 22:00 Israel time.
Reads posts_schedule.json, finds today's post, publishes to @linpro.code.
Uses environment variables for secrets (set via GitHub Secrets).
"""
import json, os, sys, time, requests
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEDULE_FILE = REPO_ROOT / "posts_schedule.json"
PUBLISHED_FILE = REPO_ROOT / "published_log.json"
IG_USER_ID = "17841426368120567"  # @linpro.code
FB_PAGE_ID = "1147869965069116"   # LIN PRO

TOKEN = os.environ['META_ACCESS_TOKEN']
TZ = ZoneInfo("Asia/Jerusalem")

def log(msg):
    ts = datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts} IL] {msg}", flush=True)

now_il = datetime.now(TZ)
il_hour = now_il.hour

# Publishing window: 22:00-23:59 IL (prime), or 00:00-05:59 IL (recovery for delayed cron)
# Outside this window → wait
if il_hour >= 22:
    # Prime window — target today's post
    target_date = now_il.strftime('%Y-%m-%d')
    log(f"Prime window (hour={il_hour}) — target {target_date}")
elif il_hour < 6:
    # Recovery window — target yesterday's post (in case 22:00 cron was delayed past midnight)
    yesterday = now_il.replace(hour=12) - timedelta(days=1)
    target_date = yesterday.strftime('%Y-%m-%d')
    log(f"Recovery window (hour={il_hour}) — target {target_date}")
else:
    log(f"Outside publishing window (hour={il_hour}) — waiting for 22:00 IL")
    sys.exit(0)

schedule = json.loads(SCHEDULE_FILE.read_text(encoding='utf-8'))
matches = [p for p in schedule if p['publish_date'] == target_date]

if not matches:
    log(f"No post scheduled for {target_date} — exiting cleanly")
    sys.exit(0)

post = matches[0]
log(f"Found post #{post['post_num']} for {target_date}")

# Check if already published today (idempotency)
published = []
if PUBLISHED_FILE.exists():
    published = json.loads(PUBLISHED_FILE.read_text(encoding='utf-8'))
if any(e['post_num'] == post['post_num'] for e in published):
    log(f"Post #{post['post_num']} already published — exiting")
    sys.exit(0)

img_local = REPO_ROOT / post['image_local']
if not img_local.exists():
    log(f"FATAL: Image not found: {img_local}")
    sys.exit(1)

# Image is pre-resized to 1080×1350 in the repo. Use raw GitHub URL directly.
GITHUB_REPO = "sivanpmu-oss/linpro-automation"
public_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{post['image_local']}"
log(f"Image URL: {public_url}")

# Get Page Access Token
r = requests.get(f"https://graph.facebook.com/v21.0/{FB_PAGE_ID}",
                 params={"fields":"access_token","access_token":TOKEN})
PAGE_TOKEN = r.json().get('access_token')
if not PAGE_TOKEN:
    log(f"FAILED: No page token: {r.json()}")
    sys.exit(1)

# Create IG container
r = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
                  data={"image_url": public_url, "caption": post['caption'],
                        "access_token": PAGE_TOKEN}, timeout=60)
ig_create = r.json()
if 'id' not in ig_create:
    log(f"FAILED: Container: {ig_create}")
    sys.exit(1)
log(f"Container: {ig_create['id']}")
time.sleep(5)

# Publish
r = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish",
                  data={"creation_id": ig_create['id'], "access_token": PAGE_TOKEN}, timeout=60)
res = r.json()
if 'id' not in res:
    log(f"FAILED: Publish: {res}")
    sys.exit(1)

log(f"SUCCESS: Post #{post['post_num']} → @linpro.code. ID: {res['id']}")

# Record success
published.append({
    "post_num": post['post_num'],
    "publish_date": post['publish_date'],
    "ig_post_id": res['id'],
    "published_at": datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
})
PUBLISHED_FILE.write_text(json.dumps(published, indent=2, ensure_ascii=False), encoding='utf-8')
log(f"Logged to published_log.json")
