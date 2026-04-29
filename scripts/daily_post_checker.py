"""
Daily Post Checker — runs hourly during the publish window via GitHub Actions.
Source of truth: published_log.json (written by daily_post_publisher.py).
Sends ONE summary email per day.
"""
import os, sys, json, smtplib, ssl, requests
from pathlib import Path
from email.message import EmailMessage
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECK_LOG = REPO_ROOT / "check_log.json"
SCHEDULE_FILE = REPO_ROOT / "posts_schedule.json"
PUBLISHED_FILE = REPO_ROOT / "published_log.json"

TOKEN = os.environ['META_ACCESS_TOKEN']
GMAIL_USER = os.environ['GMAIL_USER']
GMAIL_APP_PASSWORD = os.environ['GMAIL_APP_PASSWORD']
TZ = ZoneInfo("Asia/Jerusalem")

now_il = datetime.now(TZ)
today_il_str = now_il.strftime('%Y-%m-%d')
il_hour = now_il.hour

# Mirror the publisher's window logic so we verify the right day:
# 22:00-23:59 IL → today (publish window just opened)
# 00:00-05:59 IL → yesterday (recovery window — yesterday's publish window is closing)
# Otherwise → skip (no point reporting)
if il_hour >= 22:
    target_date = today_il_str
elif il_hour < 6:
    target_date = (now_il - timedelta(days=1)).strftime('%Y-%m-%d')
else:
    print(f"IL hour {il_hour} — outside report window, skipping", flush=True)
    sys.exit(0)

print(f"Verifying posts for target_date={target_date}", flush=True)

# Idempotency — only send one email per IL calendar day
sent_log = []
if CHECK_LOG.exists():
    sent_log = json.loads(CHECK_LOG.read_text(encoding='utf-8'))
if any(e.get('date') == today_il_str for e in sent_log):
    print(f"Email already sent today ({today_il_str}) — skipping", flush=True)
    sys.exit(0)

# Load schedule and published log
schedule = json.loads(SCHEDULE_FILE.read_text(encoding='utf-8'))
published = []
if PUBLISHED_FILE.exists():
    published = json.loads(PUBLISHED_FILE.read_text(encoding='utf-8'))

# Did the post for target_date publish?
scheduled_for_target = next((p for p in schedule if p['publish_date'] == target_date), None)
published_for_target = next((p for p in published if p['publish_date'] == target_date), None)

# Also check ALL past expected posts (catch any earlier day that silently failed)
expected_past = [p for p in schedule if p['publish_date'] <= target_date]
published_nums = {p['post_num'] for p in published}
missing_past = [p for p in expected_past if p['post_num'] not in published_nums]

# Build report
date_pretty = datetime.strptime(target_date, '%Y-%m-%d').strftime('%d/%m/%Y')
report_lines = [f"📊 דוח פרסום — {date_pretty}", "=" * 50]

if not scheduled_for_target:
    # Nothing was scheduled for this date — probably end of campaign
    report_lines.append(f"\n📭 אין פוסט מתוזמן ל-{date_pretty}")
    if not missing_past:
        report_lines.append("✅ כל הפוסטים הקודמים פורסמו בהצלחה")
    subject = f"📭 אין פוסט מתוזמן — {date_pretty}"
    extra = ""
elif published_for_target:
    # Success! Today's post is up
    ig_id = published_for_target.get('ig_post_id')
    permalink = None
    if ig_id:
        try:
            r = requests.get(
                f"https://graph.facebook.com/v21.0/{ig_id}",
                params={"fields": "permalink", "access_token": TOKEN},
                timeout=30,
            )
            permalink = r.json().get('permalink')
        except Exception as e:
            print(f"Permalink fetch failed: {e}", flush=True)
    report_lines.append(f"\n✅ פוסט #{published_for_target['post_num']} עלה ל-@linpro.code")
    report_lines.append(f"   נרשם בלוג: {published_for_target.get('published_at', 'unknown')}")
    if permalink:
        report_lines.append(f"   🔗 {permalink}")
    subject = f"✅ פוסט #{published_for_target['post_num']} עלה — {date_pretty}"
    extra = ""
    if permalink:
        extra = f"\n\n📌 רוצה להעתיק ל-Facebook (LIN PRO)? הנה הקישור:\n   {permalink}\n"
else:
    # Alert! Today's post should have published but didn't
    report_lines.append(f"\n⚠️ פוסט #{scheduled_for_target['post_num']} לא עלה!")
    report_lines.append(f"   היה אמור להתפרסם ב-{scheduled_for_target['publish_time']}")
    report_lines.append(f"   GitHub Actions: https://github.com/sivanpmu-oss/linpro-automation/actions")
    subject = f"⚠️ פוסט #{scheduled_for_target['post_num']} לא עלה — {date_pretty}"
    extra = ""

# Add older missing posts (excluding current target — already reported above)
older_missing = [p for p in missing_past if p['publish_date'] != target_date]
if older_missing:
    report_lines.append("\n⚠️ פוסטים קודמים חסרים בלוג:")
    for p in older_missing:
        report_lines.append(f"   • #{p['post_num']} ({p['publish_date']})")

body = "\n".join(report_lines) + extra + "\n\n— Claude (מנהלת הסושיאל שלך)"

msg = EmailMessage()
msg['From'] = GMAIL_USER
msg['To'] = GMAIL_USER
msg['Subject'] = subject
msg.set_content(body)

with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), local_hostname="localhost") as server:
    server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    server.send_message(msg)

print(f"Email sent: {subject}", flush=True)
print(body, flush=True)

# Record send to prevent re-send same day
sent_log.append({"date": today_il_str, "subject": subject, "sent_at": now_il.isoformat()})
CHECK_LOG.write_text(json.dumps(sent_log, indent=2, ensure_ascii=False), encoding='utf-8')
