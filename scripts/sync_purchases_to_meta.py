"""
Auto-sync Cardcom purchase emails → Meta CAPI Purchase events.
Runs hourly via GitHub Actions.
"""
import imaplib, email, os, sys, re, hashlib, json, urllib.request, urllib.parse
from email.header import decode_header
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = REPO_ROOT / "synced_purchases.json"
PIXEL_ID = "780612521049558"
SOURCE_URL = "https://linpro.ravpage.co.il/PMCode"

GMAIL_USER = os.environ['GMAIL_USER']
GMAIL_APP_PASSWORD = os.environ['GMAIL_APP_PASSWORD']
TOKEN = os.environ['META_ACCESS_TOKEN']

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)

def decode_h(s):
    if not s: return ""
    out = ""
    for p, enc in decode_header(s):
        if isinstance(p, bytes):
            try: out += p.decode(enc or 'utf-8', errors='replace')
            except: out += p.decode('utf-8', errors='replace')
        else: out += p
    return out

def get_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    cs = part.get_content_charset() or 'utf-8'
                    body += payload.decode(cs, errors='replace')
            elif ct == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    cs = part.get_content_charset() or 'utf-8'
                    html = payload.decode(cs, errors='replace')
                    body = re.sub(r'<[^>]+>', ' ', html)
                    body = re.sub(r'\s+', ' ', body)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            cs = msg.get_content_charset() or 'utf-8'
            body = payload.decode(cs, errors='replace')
    return body

def parse_cardcom_email(body, email_date):
    tx = re.search(r'מספר עסקה פנימי\s+(\d+)', body)
    if not tx: return None
    amt = re.search(r'סהכ חיוב\s+([\d.]+)\s*שקל', body)
    em = re.search(r'דואר\s+([\w.+-]+@[\w-]+\.[\w.-]+)', body)
    ph = re.search(r'טלפון נייד\s+(\d+)', body)
    nm = re.search(r'שם בעל הכרטיס\s+([^\s].+?)(?:\s+ת\.ז\.)', body)
    return {
        "transaction_id": tx.group(1),
        "amount": float(amt.group(1)) if amt else None,
        "customer_email": em.group(1) if em else None,
        "customer_phone": ph.group(1) if ph else None,
        "customer_name": nm.group(1).strip() if nm else None,
        "purchase_time": email_date
    }

def sha256(s):
    return hashlib.sha256(s.lower().strip().encode('utf-8')).hexdigest()

def normalize_phone(p):
    d = re.sub(r'\D', '', p)
    if d.startswith('0'): d = '972' + d[1:]
    return d

def send_to_meta(p):
    ts = int(p['purchase_time'].timestamp())
    user_data = {}
    if p.get('customer_email'): user_data['em'] = [sha256(p['customer_email'])]
    if p.get('customer_phone'): user_data['ph'] = [sha256(normalize_phone(p['customer_phone']))]
    event = [{"event_name":"Purchase","event_time":ts,
              "event_id":f"cardcom_{p['transaction_id']}",
              "action_source":"website","event_source_url":SOURCE_URL,
              "user_data":user_data,
              "custom_data":{"currency":"ILS","value":p['amount'],
                             "content_name":"PMU MASTER CODE - קוד האבחון המקצועי",
                             "content_type":"product","content_ids":["PMCode"]}}]
    data = urllib.parse.urlencode({"data":json.dumps(event),"access_token":TOKEN}).encode()
    req = urllib.request.Request(f"https://graph.facebook.com/v21.0/{PIXEL_ID}/events",
                                  data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return True, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return False, e.read().decode('utf-8', errors='replace')

def main():
    synced = set()
    if STATE_FILE.exists():
        synced = set(json.loads(STATE_FILE.read_text(encoding='utf-8')))
    log(f"=== Sync started — already synced: {len(synced)} ===")

    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    M.select("INBOX")
    since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
    status, data = M.search(None, f'(SINCE {since} FROM "purchase@out.cardcom.co.il")')
    if status != "OK" or not data[0]:
        log("No Cardcom emails in last 7 days")
        M.close(); M.logout()
        return

    msg_ids = data[0].split()
    log(f"Found {len(msg_ids)} Cardcom emails")
    new = []
    for mid in msg_ids:
        s, fdata = M.fetch(mid, "(BODY.PEEK[])")
        if s != "OK": continue
        msg = email.message_from_bytes(fdata[0][1])
        try:
            ed = email.utils.parsedate_to_datetime(msg.get('Date'))
        except:
            ed = datetime.now(timezone.utc)
        body = get_body(msg)
        p = parse_cardcom_email(body, ed)
        if not p or not p.get('amount'): continue
        if p['transaction_id'] in synced: continue
        log(f"  → New: {p['transaction_id']} | {p.get('amount')} ILS | {p.get('customer_email')}")
        ok, res = send_to_meta(p)
        if ok:
            log(f"    ✅ Sent: {res}")
            synced.add(p['transaction_id'])
            new.append(p['transaction_id'])
        else:
            log(f"    ❌ Error: {res[:300]}")

    M.close(); M.logout()
    STATE_FILE.write_text(json.dumps(sorted(synced), indent=2), encoding='utf-8')
    log(f"=== Done — {len(new)} new ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log(f"FATAL: {e}")
        log(traceback.format_exc())
        sys.exit(1)
