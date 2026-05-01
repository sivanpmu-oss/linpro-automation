"""
Daily post publisher — publishes to:
  • Instagram @linpro.code (PRIMARY — required for success)
  • Facebook page "LIN PRO" (BEST-EFFORT — skipped if permissions missing)

Runs from GitHub Actions, idempotent via published_log.json.
Exits 0 if IG succeeds, even if FB is skipped/fails (IG is the priority channel).
Exits 1 only if IG fails — that's a real problem worth alerting on.
"""
import json, os, sys, time, requests
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEDULE_FILE = REPO_ROOT / "posts_schedule.json"
PUBLISHED_FILE = REPO_ROOT / "published_log.json"
IG_USER_ID = "17841426368120567"   # @linpro.code
FB_PAGE_ID = "1147869965069116"    # LIN PRO
GITHUB_REPO = "sivanpmu-oss/linpro-automation"

TOKEN = os.environ['META_ACCESS_TOKEN']
TZ = ZoneInfo("Asia/Jerusalem")

# Permission errors that mean "FB will never work until Sivan re-auths"
FB_PERMANENT_ERROR_CODES = (100, 200)
FB_PERMANENT_ERROR_MARKERS = ("pages_manage_posts", "No permission to publish")


def log(msg):
    ts = datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts} IL] {msg}", flush=True)


def get_page_token(page_id, user_token):
    r = requests.get(
        "https://graph.facebook.com/v21.0/me/accounts",
        params={"fields": "id,access_token", "access_token": user_token, "limit": 100},
        timeout=30,
    ).json()
    for p in r.get("data", []):
        if p["id"] == page_id:
            return p["access_token"]
    raise RuntimeError(f"Page token not found for {page_id}")


def publish_to_instagram(public_url, caption, page_token):
    r = requests.post(
        f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
        data={"image_url": public_url, "caption": caption, "access_token": page_token},
        timeout=60,
    ).json()
    if "id" not in r:
        log(f"  IG container FAILED: {r}")
        return None
    log(f"  IG container: {r['id']}")
    time.sleep(5)
    pub = requests.post(
        f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish",
        data={"creation_id": r["id"], "access_token": page_token},
        timeout=60,
    ).json()
    if "id" not in pub:
        log(f"  IG publish FAILED: {pub}")
        return None
    return pub["id"]


def publish_to_facebook(public_url, caption, page_token):
    """Returns (post_id, skip_reason). post_id is None on failure.
    skip_reason is set to a permanent marker if the failure is a permission issue
    that won't fix itself on retry — caller should stop trying for that post.
    """
    r = requests.post(
        f"https://graph.facebook.com/v21.0/{FB_PAGE_ID}/photos",
        data={"url": public_url, "caption": caption, "access_token": page_token},
        timeout=60,
    ).json()
    if "id" in r:
        return r["id"], None
    err = r.get("error", {})
    code = err.get("code")
    msg = err.get("message", "")
    log(f"  FB publish FAILED: {r}")
    if code in FB_PERMANENT_ERROR_CODES and any(m in msg for m in FB_PERMANENT_ERROR_MARKERS):
        return None, f"missing pages_manage_posts (code {code})"
    return None, None


# === MAIN ===
now_il = datetime.now(TZ)
il_hour = now_il.hour

if il_hour >= 22:
    target_date = now_il.strftime('%Y-%m-%d')
    log(f"Prime window (hour={il_hour}) — target {target_date}")
elif il_hour < 6:
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

published = []
if PUBLISHED_FILE.exists():
    published = json.loads(PUBLISHED_FILE.read_text(encoding='utf-8'))
existing = next((e for e in published if e['post_num'] == post['post_num']), None)

# Already done if IG was published — FB is best-effort and may be permanently skipped
if existing and existing.get("ig_post_id"):
    if existing.get("fb_post_id") or existing.get("fb_skip_reason"):
        log(f"Post #{post['post_num']} already complete (IG done, FB done or skipped) — exiting")
        sys.exit(0)

img_local = REPO_ROOT / post['image_local']
if not img_local.exists():
    log(f"FATAL: Image not found: {img_local}")
    sys.exit(1)

public_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{post['image_local']}"
log(f"Image URL: {public_url}")

page_token = get_page_token(FB_PAGE_ID, TOKEN)

ig_id = (existing or {}).get("ig_post_id")
fb_id = (existing or {}).get("fb_post_id")
fb_skip_reason = (existing or {}).get("fb_skip_reason")

if not ig_id:
    log(">>> Instagram")
    ig_id = publish_to_instagram(public_url, post["caption"], page_token)
    if ig_id:
        log(f"  IG PUBLISHED: {ig_id}")

if not fb_id and not fb_skip_reason:
    log(">>> Facebook")
    fb_id, fb_skip_reason = publish_to_facebook(public_url, post["caption"], page_token)
    if fb_id:
        log(f"  FB PUBLISHED: {fb_id}")
    elif fb_skip_reason:
        log(f"  FB SKIPPED PERMANENTLY: {fb_skip_reason}")

new_entry = {
    "post_num": post['post_num'],
    "publish_date": post['publish_date'],
    "ig_post_id": ig_id,
    "fb_post_id": fb_id,
    "published_at": datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S'),
}
if fb_skip_reason:
    new_entry["fb_skip_reason"] = fb_skip_reason
if existing:
    published = [new_entry if e['post_num'] == post['post_num'] else e for e in published]
else:
    published.append(new_entry)
PUBLISHED_FILE.write_text(json.dumps(published, indent=2, ensure_ascii=False), encoding='utf-8')
log("Logged to published_log.json")

# IG is the success criterion. FB is best-effort.
if not ig_id:
    log("FAILURE — Instagram did not publish. This is a real failure.")
    sys.exit(1)

if not fb_id and not fb_skip_reason:
    # Transient FB failure (not permission). Retry on next run.
    log("PARTIAL — IG ok, FB transient failure (will retry next run)")
    sys.exit(0)  # IG succeeded — don't email failure

log("SUCCESS — IG published" + (" + FB published" if fb_id else " (FB skipped)"))
sys.exit(0)
