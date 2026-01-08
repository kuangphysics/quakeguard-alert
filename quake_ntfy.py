# quake_ntfy.py
# ---------------------------------------
# QuakeGuard : USGS → ntfy notifier
# แจ้งเตือนแผ่นดินไหวทั่วโลก (M ≥ 2.0)
# รันทุกชั่วโมงด้วย GitHub Actions
#
# ✅ ปรับปรุงจากโค้ดเดิม:
# 1) ตรวจผลการส่ง ntfy (status code) + raise_for_status() ให้ฟ้อง error ชัดเจนใน GitHub Actions log
# 2) โหมด Debug: ถ้าไม่มีเหตุเข้าเงื่อนไข ให้ส่งข้อความ "no earthquakes" ได้ (เปิด/ปิดด้วย env DEBUG_NOTIFY)
# ---------------------------------------

import os
import requests
from datetime import datetime, timezone, timedelta

# ===== CONFIG =====
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"

NTFY_TOPIC_URL = os.getenv("NTFY_TOPIC_URL")  # ตั้งใน GitHub Secrets
MIN_MAG = float(os.getenv("MIN_MAG", "2.0"))
WINDOW_MINUTES = int(os.getenv("WINDOW_MINUTES", "60"))

# Debug mode: ถ้า True จะส่งแจ้งเตือนแม้ไม่มีเหตุเข้าเงื่อนไข
# ตั้งใน GitHub Actions env: DEBUG_NOTIFY: "true"
DEBUG_NOTIFY = os.getenv("DEBUG_NOTIFY", "false").strip().lower() in ("1", "true", "yes", "y", "on")
# ==================


def fetch_earthquakes():
    """ดึงข้อมูลแผ่นดินไหวจาก USGS"""
    r = requests.get(USGS_URL, timeout=20)
    r.raise_for_status()
    return r.json().get("features", [])


def is_recent(event_time_ms: int) -> bool:
    """ตรวจว่าอยู่ในช่วงเวลาที่กำหนดหรือไม่ (UTC)"""
    event_time = datetime.fromtimestamp(event_time_ms / 1000, tz=timezone.utc)
    return datetime.now(timezone.utc) - event_time <= timedelta(minutes=WINDOW_MINUTES)


def build_message(events):
    """สร้างข้อความแจ้งเตือน (เหตุการณ์หลายรายการ)"""
    lines = [
        "🌍 QuakeGuard Alert",
        f"⏰ ช่วงเวลา: {WINDOW_MINUTES} นาทีล่าสุด",
        f"📏 Magnitude ≥ {MIN_MAG}",
        "",
    ]

    for e in events:
        prop = e.get("properties", {})
        mag = prop.get("mag", 0) or 0
        place = prop.get("place", "Unknown location")
        t = datetime.fromtimestamp(prop.get("time", 0) / 1000, tz=timezone.utc) if prop.get("time") else None
        url = prop.get("url", "")

        lines.append(f"📍 {place}")
        if t:
            lines.append(f"   • M{float(mag):.1f} | {t.strftime('%Y-%m-%d %H:%M UTC')}")
        else:
            lines.append(f"   • M{float(mag):.1f}")
        if url:
            lines.append(f"   🔗 {url}")
        lines.append("")

    return "\n".join(lines).strip()


def send_ntfy(message: str):
    """ส่งข้อความไป ntfy (พร้อมแสดงสถานะใน log)"""
    if not NTFY_TOPIC_URL:
        raise RuntimeError("NTFY_TOPIC_URL not set (check GitHub Secrets and workflow env)")

    resp = requests.post(
        NTFY_TOPIC_URL,
        data=message.encode("utf-8"),
        headers={
            "Title": "Earthquake Notification",
            "Priority": "4",
            "Tags": "earthquake,alert",
        },
        timeout=15,
    )

    # ให้ GitHub Actions log เห็นชัด ๆ ว่าส่งสำเร็จไหม
    print("ntfy status:", resp.status_code)
    if resp.text:
        print("ntfy response (first 200 chars):", resp.text[:200])

    resp.raise_for_status()


def main():
    print("DEBUG_NOTIFY:", DEBUG_NOTIFY)
    print("MIN_MAG:", MIN_MAG, "WINDOW_MINUTES:", WINDOW_MINUTES)
    print("NTFY_TOPIC_URL set:", bool(NTFY_TOPIC_URL))

    events = fetch_earthquakes()
    print("Fetched events:", len(events))

    # คัดกรองเหตุที่เข้าเงื่อนไข
    filtered = [
        e for e in events
        if (e.get("properties", {}).get("mag", 0) or 0) >= MIN_MAG
        and is_recent(e.get("properties", {}).get("time", 0))
    ]

    if not filtered:
        msg = f"ℹ️ QuakeGuard check: no earthquakes ≥ {MIN_MAG} in last {WINDOW_MINUTES} minutes"
        print("No earthquakes matching criteria.")
        if DEBUG_NOTIFY:
            send_ntfy(msg)
            print("Debug notification sent.")
        return

    msg = build_message(filtered)
    send_ntfy(msg)
    print(f"Notified {len(filtered)} events.")


if __name__ == "__main__":
    main()
