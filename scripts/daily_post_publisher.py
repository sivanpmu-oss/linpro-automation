"""
Daily post publisher — runs from GitHub Actions at 22:00 Israel time.
Reads posts_schedule.json, finds today's post, publishes to @linpro.code.
Uses environment variables for secrets (set via GitHub Secrets).
"""
import json, os, sys, time, requests
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image

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

today_il = datetime.now(TZ).strftime('%Y-%m-%d')
schedule = json.loads(SCHEDULE_FILE.read_text(encoding='utf-8'))
todays = [p for p in schedule if p['publish_date'] == today_il]

if not todays:
    log(f"No post scheduled for {today_il} — exiting cleanly")
    sys.exit(0)

post = todays[0]
log(f"Found post #{post['post_num']} for {today_il}")

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

# Resize to 1080×1350 (4:5 portrait)
img = Image.open(img_local).convert('RGB')
w, h = img.size
target = 4/5
if w/h > target:
    new_w = int(h*target); left = (w-new_w)//2
    cropped = img.crop((left, 0, left+new_w, h))
elif h > 0 and w/h < target:
    new_h = int(w/target); top = max(0, (h-new_h)//4)
    cropped = img.crop((0, top, w, top+new_h)) if h > new_h else img
else:
    cropped = img
resized = cropped.resize((1080, 1350), Image.LANCZOS)
out = "/tmp/daily_post.jpg" if os.name != 'nt' else "C:/temp/daily_post.jpg"
Path(out).parent.mkdir(exist_ok=True, parents=True)
resized.save(out, "JPEG", quality=95)

# Get Page Access Token
r = requests.get(f"https://graph.facebook.com/v21.0/{FB_PAGE_ID}",
                 params={"fields":"access_token","access_token":TOKEN})
PAGE_TOKEN = r.json().get('access_token')
if not PAGE_TOKEN:
    log(f"FAILED: No page token: {r.json()}")
    sys.exit(1)

# Upload to Catbox
with open(out, 'rb') as f:
    r = requests.post('https://catbox.moe/user/api.php',
                      files={'fileToUpload':('post.jpg', f, 'image/jpeg')},
                      data={'reqtype':'fileupload'}, timeout=60)
    public_url = r.text.strip()
    if not public_url.startswith('http'):
        log(f"FAILED: Catbox: {r.text[:200]}")
        sys.exit(1)
log(f"Image hosted: {public_url}")

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
