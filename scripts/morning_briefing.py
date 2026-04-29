"""
Morning briefing — sent every day at 07:00 IL by email.
Tells Sivan whether today is a posting day or not for ANY of her accounts,
so she can avoid manually posting and creating duplicates.
"""
import os, json, smtplib, ssl
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS = REPO_ROOT / "lessons_schedule.json"
LINPRO = REPO_ROOT / "posts_schedule.json"
LESSONS_LOG = REPO_ROOT / "lessons_published_log.json"
LINPRO_LOG = REPO_ROOT / "published_log.json"

GMAIL_USER = os.environ['GMAIL_USER']
GMAIL_APP_PASSWORD = os.environ['GMAIL_APP_PASSWORD']
TZ = ZoneInfo("Asia/Jerusalem")


def load(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


now = datetime.now(TZ)
today_str = now.strftime("%Y-%m-%d")
day_name_he = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"][now.weekday()]
date_pretty = now.strftime("%d/%m/%Y")

# Lookups
lessons = load(LESSONS)
linpro = load(LINPRO)
lessons_log = load(LESSONS_LOG)
linpro_log = load(LINPRO_LOG)

# What's scheduled for today
lesson_today = next((s for s in lessons if s["publish_date"] == today_str), None)
linpro_today = next((s for s in linpro if s["publish_date"] == today_str), None)

# Build the briefing
lines = []
lines.append(f"☀️ בוקר טוב סיון! יום {day_name_he}, {date_pretty}")
lines.append("=" * 50)
lines.append("")

# @sivan_linor lessons
if lesson_today:
    n = lesson_today["lesson_num"]
    titles = {
        1: "מבנה העור", 2: "המגן המקצועי", 3: "סוגי עור",
        4: "גווני עור (Fitzpatrick)", 5: "תורת הצבעים",
        6: "קאברים — אומנות הנטרול", 7: "מאסטר פיגמנט שפתיים",
        8: "סדר פעולות בעבודה",
    }
    lines.append(f"📱 @sivan_linor:  ✅ יש פוסט היום!")
    lines.append(f"   ריל #{n} — {titles.get(n, '')} יעלה אוטומטית ב-{lesson_today['publish_time']}")
    lines.append(f"   ⚠️ אל תעלי משהו ידנית באותו יום — תיווצר כפילות")
else:
    lines.append(f"📱 @sivan_linor:  🔇 אין פוסט היום")
    lines.append(f"   את חופשייה לפרסם משהו ידני אם תרצי")

lines.append("")

# @linpro.code daily
if linpro_today:
    lines.append(f"📱 @linpro.code:  ✅ יש פוסט היום (יעלה ב-22:00)")
    lines.append(f"   פוסט #{linpro_today['post_num']} — אוטומטי, אל תעלי במקביל")
else:
    lines.append(f"📱 @linpro.code:  🔇 אין פוסט מתוזמן היום")

lines.append("")

# Upcoming next 7 days
lines.append("=" * 50)
lines.append("📅 השבוע הקרוב:")
from datetime import timedelta
for i in range(1, 8):
    d = now + timedelta(days=i)
    ds = d.strftime("%Y-%m-%d")
    pretty = d.strftime("%d/%m %a")
    lesson_d = next((s for s in lessons if s["publish_date"] == ds), None)
    linpro_d = next((s for s in linpro if s["publish_date"] == ds), None)
    items = []
    if lesson_d:
        items.append(f"@sivan_linor ריל #{lesson_d['lesson_num']}")
    if linpro_d:
        items.append(f"@linpro.code פוסט #{linpro_d['post_num']}")
    if items:
        lines.append(f"  {pretty}: " + " + ".join(items))
    else:
        lines.append(f"  {pretty}: ולא כלום אוטומטי — את חופשייה")

lines.append("")
lines.append("— Claude")

body = "\n".join(lines)
subject_emoji = "✅" if (lesson_today or linpro_today) else "🔇"
subject = f"{subject_emoji} {date_pretty} — {'יש פוסט היום' if (lesson_today or linpro_today) else 'אין פוסט אוטומטי היום'}"

msg = EmailMessage()
msg["From"] = GMAIL_USER
msg["To"] = GMAIL_USER
msg["Subject"] = subject
msg.set_content(body)

with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), local_hostname="localhost") as s:
    s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    s.send_message(msg)

print(f"Sent: {subject}")
print(body)
