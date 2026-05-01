import os, json, requests
TOKEN = os.environ["META_ACCESS_TOKEN"]
IG_USER_ID = "17841426368120567"
r = requests.get(
    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
    params={"fields": "id,caption,timestamp,permalink", "limit": 30, "access_token": TOKEN},
    timeout=30,
).json()
out = []
for p in r.get("data", []):
    out.append({
        "id": p["id"],
        "timestamp": p["timestamp"],
        "permalink": p.get("permalink"),
        "caption_first_300": (p.get("caption") or "")[:300],
    })
print(json.dumps(out, indent=2, ensure_ascii=False))
