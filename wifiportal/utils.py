import time
import html

def now():
    return int(time.time())

def esc(value):
    return html.escape(str(value), quote=True)

def format_time(timestamp):
    try:
        timestamp = int(timestamp)
    except Exception:
        return "-"
    if timestamp <= 0:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

def kbps_to_mbps(value):
    try:
        value = int(value)
        if value <= 0:
            return "Unlimited"
        mbps = value / 1024
        if mbps == int(mbps):
            return str(int(mbps))
        return "%.2f" % mbps
    except Exception:
        return "Unlimited"

def format_duration(minutes):
    try:
        minutes = int(minutes)
    except Exception:
        minutes = 0
    if minutes == 0:
        return "永久"
    if minutes == 1440:
        return "1440 分钟 / 1 天"
    if minutes % 1440 == 0:
        return f"{minutes} 分钟 / {minutes // 1440} 天"
    if minutes % 60 == 0:
        return f"{minutes} 分钟 / {minutes // 60} 小时"
    return f"{minutes} 分钟"

def normalize_mac(mac):
    mac = str(mac or "").strip().lower().replace("-", ":")
    parts = mac.split(":")
    if len(parts) != 6:
        return ""
    fixed = []
    for part in parts:
        if len(part) == 1:
            part = "0" + part
        if len(part) != 2:
            return ""
        try:
            int(part, 16)
        except Exception:
            return ""
        fixed.append(part)
    return ":".join(fixed)
