"""
Daily post publisher — publishes to:
  • Instagram @linpro.code (PRIMARY — required for success)
  • Facebook page "LIN PRO" (BEST-EFFORT — skipped if permissions missing)

Runs from GitHub Actions. Idempotent via published_log.json.
Pre-publish guard: refuses to post if caption is >=70% similar to any of the
  last 30 live IG posts. This catches schedule/manual content overlaps.
Email alert sent on guard hit or IG failure.
"""
import json, os, sys, time, smtplib, ssl, requests
from email.message import EmailMessage
from difflib import SequenceMatcher
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

GMAIL_USER = os.environ.get('GMAIL_USER', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')

SIMILARITY_THRESHOLD = 0.70   # Block publish if caption is >=70% similar to existing
SIMILARITY_LOOKBACK = 30       # Check last 30 live posts

FB_PERMANENT_ERROR_CODES = (100, 200)
FB_PERMANENT_ERROR_MARKERS = ("pages_manage_posts", "No permission to publish")


def log(msg):
    ts = datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts} IL] {msg}", flush=True)


def alert_sivan(subject, body):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        log(f"[ALERT — would email] {subject}")
        return
    try:
        msg = EmailMessage()
        msg['From'] = GMAIL_USER
        msg['To'] = "sivanpmu@gmail.com"
        msg['Subject'] = subject
        msg.set_content(body)
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
            s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            s.send_message(msg)
        log(f"  Alert email sent: {subject}")
    except Exception as e:
        log(f"  Alert email FAILED: {e}")


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


def fetch_recent_captions(limit=SIMILARITY_LOOKBACK):
    r = requests.get(
        f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
        params={"fields": "id,caption,timestamp", "limit": limit, "access_token": TOKEN},
        timeout=30,
    ).json()
    return [(p.get("id"), p.get("caption") or "", p.get("timestamp")) for p in r.get("data", [])]


def caption_similarity_check(new_caption):
    """Returns (max_score, matching_post_id, matching_timestamp) or (0, None, None)."""
    try:
        recent = fetch_recent_captions()
    except Exception as e:
        log(f"  Could not fetch recent captions ({e}) — skipping guard")
        return 0, None, None
    log(f"  Comparing against {len(recent)} recent live posts")
    best = (0, None, None)
    new_norm = (new_caption or "")[:500].strip()
    for pid, cap, ts in recent:
        existing_norm = (cap or "")[:500].strip()
        score = SequenceMatcher(None, new_norm, existing_norm).ratio()
        if score > best[0]:
            best = (score, pid, ts)
    return best


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

# Already done if IG was published OR explicitly skipped
if existing:
    if existing.get("skip_reason"):
        log(f"Post #{post['post_num']} marked as skipped: {existing['skip_reason']} — exiting")
        sys.exit(0)
    if existing.get("ig_post_id") and (existing.get("fb_post_id") or existing.get("fb_skip_reason")):
        log(f"Post #{post['post_num']} already complete — exiting")
        sys.exit(0)

img_local = REPO_ROOT / post['image_local']
if not img_local.exists():
    log(f"FATAL: Image not found: {img_local}")
    sys.exit(1)

public_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{post['image_local']}"
log(f"Image URL: {public_url}")

# === SIMILARITY GUARD ===
ig_id = (existing or {}).get("ig_post_id")
if not ig_id:
    log(f">>> Pre-publish similarity check (threshold {SIMILARITY_THRESHOLD})")
    score, dup_id, dup_ts = caption_similarity_check(post["caption"])
    log(f"  highest similarity: {score:.2f} (vs post {dup_id} at {dup_ts})")
    if score >= SIMILARITY_THRESHOLD:
        log(f"  🚨 BLOCKED — caption is {score*100:.0f}% similar to existing post {dup_id}")
        # Mark in log so we don't retry
        new_entry = {
            "post_num": post['post_num'],
            "publish_date": post['publish_date'],
            "ig_post_id": None,
            "fb_post_id": None,
            "skip_reason": f"duplicate of live post {dup_id} ({score*100:.0f}% match, posted {dup_ts})",
            "blocked_at": datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S'),
        }
        if existing:
            published = [new_entry if e['post_num'] == post['post_num'] else e for e in published]
        else:
            published.append(new_entry)
        PUBLISHED_FILE.write_text(
            json.dumps(published, indent=2, ensure_ascii=False), encoding='utf-8'
        )
        alert_sivan(
            subject=f"⚠️ Post #{post['post_num']} blocked — looks like a duplicate",
            body=(
                f"שלום סיון,\n\n"
                f"חסמתי את הפרסום של פוסט #{post['post_num']} שהיה מתוזמן ל-{target_date}.\n\n"
                f"הסיבה: ה-caption דומה {score*100:.0f}% לפוסט שכבר קיים על העמוד שלך:\n"
                f"  ID: {dup_id}\n"
                f"  פורסם ב: {dup_ts}\n\n"
                f"אם זה כפילות אמיתית — לא צריך לעשות שום דבר. הפוסט יידלג גם בעתיד.\n"
                f"אם זה לא כפילות (רק caption דומה במקרה) — תכתבי לי וניתן לפרסם בכל זאת.\n\n"
                f"caption שלא פורסם:\n{post.get('caption','')[:500]}\n"
            ),
        )
        log("  Logged skip + alert sent. Exiting cleanly.")
        sys.exit(0)
    log(f"  ✓ caption is unique enough — proceeding")

page_token = get_page_token(FB_PAGE_ID, TOKEN)

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

if not ig_id:
    log("FAILURE — Instagram did not publish. Real failure.")
    alert_sivan(
        subject=f"🚨 Post #{post['post_num']} FAILED to publish to Instagram",
        body=f"Post #{post['post_num']} for {target_date} failed to publish to @linpro.code IG.\n\nCheck workflow logs for details.",
    )
    sys.exit(1)

if not fb_id and not fb_skip_reason:
    log("PARTIAL — IG ok, FB transient failure (will retry next run)")
    sys.exit(0)

log("SUCCESS — IG published" + (" + FB published" if fb_id else " (FB skipped)"))
sys.exit(0)
