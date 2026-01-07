# quake_ntfy.py
# ---------------------------------------
# QuakeGuard : USGS → ntfy notifier
# แจ้งเตือนแผ่นดินไหวทั่วโลก (M ≥ 2.0)
# รันทุกชั่วโมงด้วย GitHub Actions
# ---------------------------------------

import os
import requests
from datetime import datetime, timezone, timedelta

# ===== CONFIG =====
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
NTFY_TOPIC_URL = os.getenv("NTFY_TOPIC_URL")  # ตั้งใน GitHub Secrets
MIN_MAG = float(os.getenv("MIN_MAG", "2.0"))
WINDOW_MINUTES = int(os.getenv("WINDOW_MINUTES", "60"))

# ==================

def fetch_earthquakes():
    """ดึงข้อมูลแผ่นดินไหวจาก USGS"""
    r = requests.get(USGS_URL, timeout=20)
    r.raise_for_status()
    return r.json().get("features", [])

def is_recent(event_time_ms):
    """ตรวจว่าอยู่ในช่วงเวลาที่กำหนดหรือไม่"""
    event_time = datetime.fromtimestamp(event_time_ms / 1000, tz=timezone.utc)
    return datetime.now(timezone.utc) - event_time <= timedelta(minutes=WINDOW_MINUTES)

def build_message(events):
    """สร้างข้อความแจ้งเตือน"""
    lines = [
        "🌍 QuakeGuard Alert",
        f"⏰ ช่วงเวลา: {WINDOW_MINUTES} นาทีล่าสุด",
        f"📏 Magnitude ≥ {MIN_MAG}",
        "",
    ]

    for e in events:
        prop = e["properties"]
        mag = prop.get("mag", 0)
        place = prop.get("place", "Unknown location")
        t = datetime.fromtimestamp(prop["time"] / 1000, tz=timezone.utc)
        url = prop.get("url", "")
        lines.append(f"📍 {place}")
        lines.append(f"   • M{mag:.1f} | {t.strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append(f"   🔗 {url}")
        lines.append("")

    return "\n".join(lines)

def send_ntfy(message):
    """ส่งข้อความไป ntfy"""
    if not NTFY_TOPIC_URL:
        raise RuntimeError("NTFY_TOPIC_URL not set")

    requests.post(
        NTFY_TOPIC_URL,
        data=message.encode("utf-8"),
        headers={
            "Title": "Earthquake Notification",
            "Priority": "4",
            "Tags": "earthquake,alert"
        },
        timeout=15
    )

def main():
    events = fetch_earthquakes()

    # คัดกรองเหตุที่เข้าเงื่อนไข
    filtered = [
        e for e in events
        if e["properties"].get("mag", 0) >= MIN_MAG
        and is_recent(e["properties"]["time"])
    ]

    if not filtered:
        print("No earthquakes matching criteria.")
        return

    msg = build_message(filtered)
    send_ntfy(msg)
    print(f"Notified {len(filtered)} events.")

if __name__ == "__main__":
    main()
