"""
Daily Post Checker — runs hourly from 23:00 IL via GitHub Actions.
Verifies today's posts went up on both IG accounts and emails Sivan ONCE per day.
"""
import os, sys, json, smtplib, ssl, requests
from pathlib import Path
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECK_LOG = REPO_ROOT / "check_log.json"

TOKEN = os.environ['META_ACCESS_TOKEN']
GMAIL_USER = os.environ['GMAIL_USER']
GMAIL_APP_PASSWORD = os.environ['GMAIL_APP_PASSWORD']
TZ = ZoneInfo("Asia/Jerusalem")

# Idempotency — only send once per day
today_il = datetime.now(TZ).strftime('%Y-%m-%d')
il_hour = int(datetime.now(TZ).strftime('%H'))

# Skip if before 23:00 IL (we want late-day report)
if il_hour < 23 and il_hour > 5:
    print(f"IL hour {il_hour} — skipping, will run later", flush=True)
    sys.exit(0)

sent_log = []
if CHECK_LOG.exists():
    sent_log = json.loads(CHECK_LOG.read_text(encoding='utf-8'))
if any(e.get('date') == today_il for e in sent_log):
    print(f"Email already sent today ({today_il}) — skipping", flush=True)
    sys.exit(0)

ACCOUNTS = {
    "@sivan_linor (Hebrew)": "17841404776930021",
    "@linpro.code (English)": "17841426368120567",
}

today = datetime.now(TZ).date()
report_lines = [f"📊 דוח יומי — {today.strftime('%d/%m/%Y')}", "=" * 50]
posts_today = {}

for name, ig_id in ACCOUNTS.items():
    try:
        r = requests.get(f"https://graph.facebook.com/v21.0/{ig_id}/media",
                        params={"fields":"id,caption,timestamp,permalink",
                                "limit":5, "access_token":TOKEN}, timeout=30)
        data = r.json().get('data', [])
        today_posts = [p for p in data if p.get('timestamp','')[:10] == today.strftime('%Y-%m-%d')]
        posts_today[name] = today_posts
        report_lines.append(f"\n{name}:")
        if today_posts:
            for p in today_posts:
                cap = (p.get('caption','') or '')[:60]
                report_lines.append(f"  ✅ עלה: {cap}...")
                report_lines.append(f"     🔗 {p.get('permalink')}")
        else:
            report_lines.append(f"  ⚠️ אין פוסטים מהיום!")
    except Exception as e:
        report_lines.append(f"\n{name}: ❌ שגיאה: {e}")
        posts_today[name] = []

total = sum(len(v) for v in posts_today.values())
if total > 0:
    subject = f"✅ {total} פוסט/ים עלה היום — תזכורת להעלות לפייסבוק"
    extra = "\n\n📌 תזכורת — צריך להעלות ידנית לפייסבוק!\n\n"
    for name, posts in posts_today.items():
        if posts:
            fb_page = "Sivan Linor beauty academy" if "sivan_linor" in name else "LIN PRO"
            extra += f"• דף Facebook: {fb_page}\n"
            for p in posts:
                extra += f"  → {p.get('permalink')}\n"
else:
    subject = "⚠️ לא עלו פוסטים היום — לבדוק!"
    extra = "\n\n⚠️ לא נמצאו פוסטים מהיום באף חשבון. בדקי את GitHub Actions."

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
sent_log.append({"date": today_il, "subject": subject, "sent_at": datetime.now(TZ).isoformat()})
CHECK_LOG.write_text(json.dumps(sent_log, indent=2, ensure_ascii=False), encoding='utf-8')
