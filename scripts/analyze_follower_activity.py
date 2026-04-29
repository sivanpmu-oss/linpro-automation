"""
One-shot analysis: when are @sivan_linor's followers most active?
Pulls online_followers hourly metric from IG Business Insights API.

Output: a clear ranking of the BEST hours to post + day-of-week analysis.
"""
import os, requests, json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

IG_USER_ID = "17841404776930021"  # @sivan_linor
TOKEN = os.environ["META_ACCESS_TOKEN"]
TZ = ZoneInfo("Asia/Jerusalem")


def banner(msg):
    print()
    print("=" * 60)
    print(msg)
    print("=" * 60)


banner("Account info")
acct = requests.get(
    f"https://graph.facebook.com/v21.0/{IG_USER_ID}",
    params={"fields": "username,followers_count,media_count", "access_token": TOKEN},
    timeout=30,
).json()
print(json.dumps(acct, ensure_ascii=False, indent=2))


banner("ONLINE FOLLOWERS — last 30 days, hourly")
# Note: online_followers metric was deprecated in some IG API versions; we'll try and fall back.
since_ts = int((datetime.now(timezone.utc) - timedelta(days=29)).timestamp())
until_ts = int(datetime.now(timezone.utc).timestamp())

resp = requests.get(
    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/insights",
    params={
        "metric": "online_followers",
        "period": "lifetime",
        "since": since_ts,
        "until": until_ts,
        "access_token": TOKEN,
    },
    timeout=60,
)
data = resp.json()
print(f"HTTP {resp.status_code}")
print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])

# Aggregate hourly buckets across days
hour_totals = [0] * 24
hour_counts = [0] * 24

if "data" in data and data["data"]:
    for series in data["data"]:
        for v in series.get("values", []):
            value_dict = v.get("value")
            end_time = v.get("end_time")
            if isinstance(value_dict, dict) and end_time:
                for hour_str, count in value_dict.items():
                    h = int(hour_str)
                    hour_totals[h] += count
                    hour_counts[h] += 1

if any(hour_counts):
    avg_per_hour = [
        hour_totals[h] / hour_counts[h] if hour_counts[h] else 0
        for h in range(24)
    ]
    banner("Average online followers by HOUR (UTC, then converted to IL)")
    print(f"{'UTC':>4} {'IL':>4} {'avg':>8} {'bar':<40}")
    max_avg = max(avg_per_hour) or 1
    # Convert UTC to IL summer time (+3) — for late April
    pairs = [(h, (h + 3) % 24, avg_per_hour[h]) for h in range(24)]
    # Sort by IL hour for a more readable layout
    by_il = sorted(pairs, key=lambda x: x[1])
    for utc_h, il_h, avg in by_il:
        bar = "#" * int(40 * avg / max_avg)
        print(f"{utc_h:>4} {il_h:02d}:00 {avg:>8.1f} {bar}")

    # Top 5 IL hours
    by_avg = sorted(pairs, key=lambda x: x[2], reverse=True)
    banner("TOP 5 BEST HOURS TO POST (Israel time)")
    for i, (utc_h, il_h, avg) in enumerate(by_avg[:5], 1):
        print(f"  #{i}: {il_h:02d}:00 IL  →  {avg:.0f} followers online (avg)")
else:
    print("\n(No online_followers data — metric may be deprecated for this account or no data)")


banner("AUDIENCE LOCATION (top countries) — for context")
loc = requests.get(
    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/insights",
    params={
        "metric": "follower_demographics",
        "period": "lifetime",
        "metric_type": "total_value",
        "breakdown": "country",
        "access_token": TOKEN,
    },
    timeout=30,
).json()
print(json.dumps(loc, ensure_ascii=False, indent=2)[:1500])


banner("AUDIENCE AGE & GENDER — for context")
ag = requests.get(
    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/insights",
    params={
        "metric": "follower_demographics",
        "period": "lifetime",
        "metric_type": "total_value",
        "breakdown": "age,gender",
        "access_token": TOKEN,
    },
    timeout=30,
).json()
print(json.dumps(ag, ensure_ascii=False, indent=2)[:1500])
