"""
Lesson Reels Publisher — publishes the 8 PMU course teaser reels to @sivan_linor
on schedule (every 3 days at 20:30 IL).

Reel publishing flow (Meta Graph API):
  1. POST /{ig_user_id}/media with media_type=REELS + video_url + caption
  2. Poll the creation_id status until it's FINISHED
  3. POST /{ig_user_id}/media_publish with creation_id

Idempotent — safe to run hourly. Skip if already published.
"""
import json, os, sys, time, requests
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEDULE_FILE = REPO_ROOT / "lessons_schedule.json"
PUBLISHED_FILE = REPO_ROOT / "lessons_published_log.json"
RAW_BASE = "https://raw.githubusercontent.com/sivanpmu-oss/linpro-automation/main"

IG_USER_ID = "17841404776930021"  # @sivan_linor (Hebrew)
TOKEN = os.environ["META_ACCESS_TOKEN"]
TZ = ZoneInfo("Asia/Jerusalem")


def log(msg):
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts} IL] {msg}", flush=True)


now_il = datetime.now(TZ)
il_hour = now_il.hour
today = now_il.strftime("%Y-%m-%d")

schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))

# Find lesson scheduled for today
matches = [s for s in schedule if s["publish_date"] == today]
if not matches:
    log(f"No lesson scheduled for {today} — exiting cleanly")
    sys.exit(0)

post = matches[0]
scheduled_hour = int(post["publish_time"].split(":")[0])

# Publish window: from scheduled hour through 06:00 IL the next day
# If we're before scheduled hour AND after 06:00 (i.e., daylight) — wait
if 6 < il_hour < scheduled_hour:
    log(f"Hour {il_hour} < scheduled {scheduled_hour} — waiting")
    sys.exit(0)

# Idempotency
published = []
if PUBLISHED_FILE.exists():
    published = json.loads(PUBLISHED_FILE.read_text(encoding="utf-8"))
if any(p["lesson_num"] == post["lesson_num"] for p in published):
    log(f"Lesson {post['lesson_num']} already published — exiting")
    sys.exit(0)

video_url = f"{RAW_BASE}/{post['video_file']}"
log(f"Publishing lesson {post['lesson_num']} for @sivan_linor")
log(f"Video URL: {video_url}")

# Step 1: Create media container (REELS type)
create_resp = requests.post(
    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
    data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": post["caption"],
        "share_to_feed": "true",
        "access_token": TOKEN,
    },
    timeout=60,
)
create_data = create_resp.json()
if "id" not in create_data:
    log(f"Container creation FAILED: {create_data}")
    sys.exit(1)

creation_id = create_data["id"]
log(f"Container created: {creation_id}")

# Step 2: Poll status until FINISHED (Meta needs time to process video)
max_wait = 300  # 5 min
start = time.time()
while time.time() - start < max_wait:
    status_resp = requests.get(
        f"https://graph.facebook.com/v21.0/{creation_id}",
        params={"fields": "status_code", "access_token": TOKEN},
        timeout=30,
    )
    status = status_resp.json().get("status_code")
    log(f"  status: {status}")
    if status == "FINISHED":
        break
    if status in ("ERROR", "EXPIRED"):
        log(f"Processing failed: {status_resp.json()}")
        sys.exit(1)
    time.sleep(15)
else:
    log("Timed out waiting for video processing")
    sys.exit(1)

# Step 3: Publish
publish_resp = requests.post(
    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish",
    data={"creation_id": creation_id, "access_token": TOKEN},
    timeout=60,
)
pub_data = publish_resp.json()
if "id" not in pub_data:
    log(f"Publish FAILED: {pub_data}")
    sys.exit(1)

ig_post_id = pub_data["id"]
log(f"PUBLISHED — IG post id: {ig_post_id}")

# Log it
published.append({
    "lesson_num": post["lesson_num"],
    "publish_date": post["publish_date"],
    "ig_post_id": ig_post_id,
    "published_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
})
PUBLISHED_FILE.write_text(
    json.dumps(published, indent=2, ensure_ascii=False), encoding="utf-8"
)
log("Logged to lessons_published_log.json")
