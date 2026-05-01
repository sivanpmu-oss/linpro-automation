"""
Lesson Reels Publisher — publishes 8 PMU course teaser reels to:
  • Instagram @sivan_linor (PRIMARY — required for success)
  • Facebook page "Sivan Linor beauty academy" (BEST-EFFORT — skipped if missing perms)

Schedule: every 3 days at 13:30 IL (peak follower activity).
Idempotent — safe to run hourly.
Exits 0 if IG succeeds, even if FB is skipped.
"""
import json, os, sys, time, requests
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEDULE_FILE = REPO_ROOT / "lessons_schedule.json"
PUBLISHED_FILE = REPO_ROOT / "lessons_published_log.json"
RAW_BASE = "https://raw.githubusercontent.com/sivanpmu-oss/linpro-automation/main"

IG_USER_ID = "17841404776930021"   # @sivan_linor
FB_PAGE_ID = "112225864303013"     # Sivan Linor beauty academy
TOKEN = os.environ["META_ACCESS_TOKEN"]
TZ = ZoneInfo("Asia/Jerusalem")

FB_PERMANENT_ERROR_CODES = (100, 200)
FB_PERMANENT_ERROR_MARKERS = ("pages_manage_posts", "No permission to publish")


def log(msg):
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts} IL] {msg}", flush=True)


def get_page_token(page_id, user_token):
    pages = requests.get(
        "https://graph.facebook.com/v21.0/me/accounts",
        params={"fields": "id,access_token", "access_token": user_token},
        timeout=30,
    ).json()
    for p in pages.get("data", []):
        if p["id"] == page_id:
            return p["access_token"]
    raise RuntimeError(f"Page token not found for {page_id}")


def publish_to_instagram(video_url, caption):
    create = requests.post(
        f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": TOKEN,
        },
        timeout=60,
    ).json()
    if "id" not in create:
        log(f"IG container FAILED: {create}")
        return None
    creation_id = create["id"]
    log(f"  IG container: {creation_id}")
    start = time.time()
    while time.time() - start < 300:
        status = requests.get(
            f"https://graph.facebook.com/v21.0/{creation_id}",
            params={"fields": "status_code", "access_token": TOKEN},
            timeout=30,
        ).json().get("status_code")
        log(f"    IG status: {status}")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            log(f"  IG processing FAILED")
            return None
        time.sleep(15)
    pub = requests.post(
        f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish",
        data={"creation_id": creation_id, "access_token": TOKEN},
        timeout=60,
    ).json()
    return pub.get("id")


def publish_to_facebook(video_url, caption):
    """Returns (post_id, skip_reason). skip_reason is set if a permanent permission error."""
    try:
        page_token = get_page_token(FB_PAGE_ID, TOKEN)
    except RuntimeError as e:
        return None, f"page token unavailable: {e}"
    resp = requests.post(
        f"https://graph.facebook.com/v21.0/{FB_PAGE_ID}/videos",
        data={"file_url": video_url, "description": caption, "access_token": page_token},
        timeout=180,
    ).json()
    if "id" in resp:
        return resp["id"], None
    err = resp.get("error", {})
    code = err.get("code")
    msg = err.get("message", "")
    log(f"  FB publish FAILED: {resp}")
    if code in FB_PERMANENT_ERROR_CODES and any(m in msg for m in FB_PERMANENT_ERROR_MARKERS):
        return None, f"missing pages_manage_posts (code {code})"
    return None, None


# === MAIN ===
now_il = datetime.now(TZ)
il_hour = now_il.hour
today = now_il.strftime("%Y-%m-%d")

schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
matches = [s for s in schedule if s["publish_date"] == today]
if not matches:
    log(f"No lesson scheduled for {today} — exiting cleanly")
    sys.exit(0)

post = matches[0]
scheduled_hour = int(post["publish_time"].split(":")[0])
if 6 < il_hour < scheduled_hour:
    log(f"Hour {il_hour} < scheduled {scheduled_hour} — waiting")
    sys.exit(0)

published = []
if PUBLISHED_FILE.exists():
    published = json.loads(PUBLISHED_FILE.read_text(encoding="utf-8"))
existing = next((p for p in published if p["lesson_num"] == post["lesson_num"]), None)

# Already done if IG was published (FB is best-effort)
if existing and existing.get("ig_post_id"):
    if existing.get("fb_post_id") or existing.get("fb_skip_reason"):
        log(f"Lesson {post['lesson_num']} already complete — exiting")
        sys.exit(0)

video_url = f"{RAW_BASE}/{post['video_file']}"
log(f"Publishing lesson {post['lesson_num']} — {video_url}")

ig_id = (existing or {}).get("ig_post_id")
fb_id = (existing or {}).get("fb_post_id")
fb_skip_reason = (existing or {}).get("fb_skip_reason")

if not ig_id:
    log(">>> Instagram")
    ig_id = publish_to_instagram(video_url, post["caption"])
    if ig_id:
        log(f"  IG PUBLISHED: {ig_id}")

if not fb_id and not fb_skip_reason:
    log(">>> Facebook")
    fb_id, fb_skip_reason = publish_to_facebook(video_url, post["caption"])
    if fb_id:
        log(f"  FB PUBLISHED: {fb_id}")
    elif fb_skip_reason:
        log(f"  FB SKIPPED PERMANENTLY: {fb_skip_reason}")

new_entry = {
    "lesson_num": post["lesson_num"],
    "publish_date": post["publish_date"],
    "ig_post_id": ig_id,
    "fb_post_id": fb_id,
    "published_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
}
if fb_skip_reason:
    new_entry["fb_skip_reason"] = fb_skip_reason

if existing:
    published = [new_entry if p["lesson_num"] == post["lesson_num"] else p for p in published]
else:
    published.append(new_entry)
PUBLISHED_FILE.write_text(
    json.dumps(published, indent=2, ensure_ascii=False), encoding="utf-8"
)
log("Logged to lessons_published_log.json")

# IG is success criterion
if not ig_id:
    log("FAILURE — Instagram did not publish")
    sys.exit(1)

if not fb_id and not fb_skip_reason:
    log("PARTIAL — IG ok, FB transient failure (will retry)")
    sys.exit(0)

log("SUCCESS — IG published" + (" + FB published" if fb_id else " (FB skipped)"))
sys.exit(0)
