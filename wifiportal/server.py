from wifiportal.config import CONFIG_FILE, CONFIG, LAN_IP, LAN_IF, WAN_IF, PORTAL_PORT, DB_FILE, SETTINGS_FILE, LOG_FILE, SESSION_SECRET, QOS_IFB
from wifiportal.utils import now, esc, format_time, kbps_to_mbps, format_duration, normalize_mac
from wifiportal.db import load_json, save_json, load_settings, save_settings, load_db, save_db, append_log, create_backup, list_backups, cleanup_old_backups, restore_backup_file
from wifiportal.firewall import run_command, check_nft_table_exists, nft_available, nft_delete_table, nft_init_table, nft_add_element, nft_delete_element, nft_allow_device, nft_kick_device, nft_add_whitelist, nft_delete_whitelist, nft_add_blacklist, nft_delete_blacklist, restore_firewall_sessions, cleanup_expired_and_firewall, firewall_status_text, auto_backup_if_needed, qos_enabled, qos_tc, qos_ip, qos_class_id, qos_prio_id, qos_rate, qos_run, qos_clear, qos_init, qos_remove_device, qos_apply_device, qos_restore_sessions, qos_status_text, safe_qos_apply_device, safe_qos_remove_device
from wifiportal.templates import admin_page, _wp_customer_page_polished, _wp_customer_v2_page, print_vouchers_page

#!/usr/bin/env python3
import hashlib
import html
import http.cookies
import json
import os
import shutil
import secrets
import subprocess
import time
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer




























































































































































































































































































































































def password_hash(password, salt):
    raw = (salt + ":" + password).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_admin_password(password):
    settings = load_settings()
    admin = settings.get("admin", {})
    salt = admin.get("password_salt", "")
    saved_hash = admin.get("password_hash", "")
    if not salt or not saved_hash:
        return False
    return password_hash(password, salt) == saved_hash


def update_admin_password(new_password):
    if len(new_password) < 8:
        return False, "新密码至少需要 8 位"
    settings = load_settings()
    settings.setdefault("admin", {})
    salt = secrets.token_hex(16)
    settings["admin"]["password_salt"] = salt
    settings["admin"]["password_hash"] = password_hash(new_password, salt)
    save_settings(settings)
    append_log("ADMIN", "后台密码已修改")
    return True, "后台密码已修改，请重新登录"


def read_dhcp_leases():
    leases = {}
    for path in ["/tmp/dhcp.leases", "/var/dhcp.leases"]:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as file:
                for line in file:
                    parts = line.split()
                    if len(parts) >= 4:
                        mac = parts[1].lower()
                        ip = parts[2]
                        hostname = parts[3] if parts[3] != "*" else "Unknown Device"
                        leases[ip] = {"mac": mac, "hostname": hostname}
        except Exception:
            pass
    return leases


def get_client_identity(ip):
    leases = read_dhcp_leases()
    if ip in leases:
        return leases[ip].get("mac", ""), leases[ip].get("hostname", "Unknown Device")

    try:
        with open("/proc/net/arp", "r", encoding="utf-8") as file:
            for line in file.readlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == ip:
                    mac = parts[3].lower()
                    if mac != "00:00:00:00:00:00":
                        return mac, "Unknown Device"
    except Exception:
        pass

    return "", "Unknown Device"
















def get_file_size(path):
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


# AUDIT_LOG_ENHANCED_V1
def append_admin_audit(handler, action, detail="", result="OK", voucher_code="", mac=""):
    try:
        admin_ip = ""
        try:
            if handler is not None and getattr(handler, "client_address", None):
                admin_ip = handler.client_address[0]
        except Exception:
            admin_ip = ""

        message = "后台操作：" + str(action)
        if detail:
            message += "；" + str(detail)

        append_log(
            "AUDIT",
            message,
            result=result,
            voucher_code=voucher_code,
            mac=mac,
            ip=admin_ip
        )
    except Exception:
        pass



def get_auto_backup_status():
    status = {
        "script_exists": False,
        "cron_exists": False,
        "cron_running": False,
        "cron_line": "",
        "log_exists": False,
        "log_text": "",
        "last_backup_time": 0,
        "last_backup_text": "-",
        "last_backup_name": "",
        "summary": "未配置",
        "ok": False,
        "warn": True,
    }

    script_path = "/usr/bin/wifiportal_auto_backup.sh"
    cron_path = "/etc/crontabs/root"
    log_path = "/tmp/wifiportal_auto_backup.log"

    try:
        status["script_exists"] = os.path.exists(script_path)
    except Exception:
        status["script_exists"] = False

    try:
        if os.path.exists(cron_path):
            with open(cron_path, "r", encoding="utf-8", errors="ignore") as file:
                cron_text = file.read()
            for line in cron_text.splitlines():
                if "wifiportal_auto_backup.sh" in line and not line.strip().startswith("#"):
                    status["cron_exists"] = True
                    status["cron_line"] = line.strip()
                    break
    except Exception:
        pass

    try:
        cron_ps = os.popen("ps | grep '[c]ron' 2>/dev/null").read().strip()
        status["cron_running"] = bool(cron_ps)
    except Exception:
        status["cron_running"] = False

    try:
        if os.path.exists(log_path):
            status["log_exists"] = True
            with open(log_path, "r", encoding="utf-8", errors="ignore") as file:
                lines = file.read().splitlines()
            status["log_text"] = "\n".join(lines[-18:])
    except Exception as error:
        status["log_text"] = "读取自动备份日志失败：" + str(error)

    try:
        backup_dir = "/etc/wifiportal/backup"
        newest_path = ""
        newest_mtime = 0
        if os.path.isdir(backup_dir):
            for name in os.listdir(backup_dir):
                full_path = os.path.join(backup_dir, name)
                if not os.path.isfile(full_path):
                    continue
                mtime = int(os.path.getmtime(full_path))
                if mtime > newest_mtime:
                    newest_mtime = mtime
                    newest_path = full_path

        if newest_mtime > 0:
            status["last_backup_time"] = newest_mtime
            status["last_backup_text"] = format_time(newest_mtime)
            status["last_backup_name"] = os.path.basename(newest_path)
    except Exception:
        pass

    ok = status["script_exists"] and status["cron_exists"] and status["cron_running"]
    status["ok"] = bool(ok)
    status["warn"] = not bool(ok)

    if ok:
        status["summary"] = "已启用，每天 03:07 自动备份"
    elif not status["script_exists"]:
        status["summary"] = "自动备份脚本不存在"
    elif not status["cron_exists"]:
        status["summary"] = "cron 自动任务不存在"
    elif not status["cron_running"]:
        status["summary"] = "cron 服务未运行"
    else:
        status["summary"] = "自动备份状态未知"

    return status


def get_last_backup_time():
    backup_dir = "/etc/wifiportal/backup"
    latest = 0
    try:
        for name in os.listdir(backup_dir):
            full_path = os.path.join(backup_dir, name)
            if os.path.isfile(full_path):
                latest = max(latest, int(os.path.getmtime(full_path)))
    except Exception:
        pass
    return latest


def check_nft_table_exists():
    code, out, err = run_command(["/usr/sbin/nft", "list", "table", "inet", "wifiportal"])
    return code == 0


def get_uptime_text():
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as file:
            seconds = int(float(file.read().split()[0]))
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        return f"{days}天 {hours}小时 {minutes}分钟"
    except Exception:
        return "-"


def get_speed_plans():
    settings = load_settings()
    plans = settings.setdefault("speed_plans", [])
    if not plans:
        plans.extend([
            {"name": "Day Plan 5M", "minutes": 1440, "max_devices": 1, "download_mbps": "5", "upload_mbps": "2", "note": "一天卡"},
            {"name": "Permanent Unlimited", "minutes": 0, "max_devices": 1, "download_mbps": "0", "upload_mbps": "0", "note": "永久不限速"}
        ])
        save_settings(settings)
    return plans


def get_plan_by_index(index_value):
    plans = get_speed_plans()
    try:
        index = int(index_value)
    except Exception:
        index = 0
    if index < 0 or index >= len(plans):
        index = 0
    return plans[index]


def get_all_seen_clients():
    clients = {}

    leases = read_dhcp_leases()
    for ip, item in leases.items():
        mac = normalize_mac(item.get("mac", ""))
        if mac:
            clients[mac] = {"mac": mac, "ip": ip, "hostname": item.get("hostname", "Unknown Device")}

    try:
        with open("/proc/net/arp", "r", encoding="utf-8") as file:
            for line in file.readlines()[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    ip = parts[0]
                    mac = normalize_mac(parts[3])
                    if mac and mac != "00:00:00:00:00:00":
                        clients.setdefault(mac, {"mac": mac, "ip": ip, "hostname": "Unknown Device"})
                        if not clients[mac].get("ip"):
                            clients[mac]["ip"] = ip
    except Exception:
        pass

    return clients


def build_device_mac_options(db):
    # 白名单 / 黑名单 MAC 下拉只显示 iw station dump 当前真实在线 WiFi 设备。
    # 不使用 DHCP leases / ARP，因为它们会保留大量历史或残留设备。
    wifi_macs = []
    wifi_info = {}

    code, out, err = run_command(["/usr/sbin/iw", "dev"])
    if code != 0:
        code, out, err = run_command(["/sbin/iw", "dev"])

    wifi_ifaces = []
    if code == 0:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Interface "):
                parts = line.split()
                if len(parts) >= 2:
                    wifi_ifaces.append(parts[1])

    for iface in wifi_ifaces:
        code2, out2, err2 = run_command(["/usr/sbin/iw", "dev", iface, "station", "dump"])
        if code2 != 0:
            code2, out2, err2 = run_command(["/sbin/iw", "dev", iface, "station", "dump"])
        if code2 != 0:
            continue

        current_mac = ""
        for line in out2.splitlines():
            line = line.strip()
            if line.startswith("Station "):
                parts = line.split()
                if len(parts) >= 2:
                    current_mac = normalize_mac(parts[1])
                    if current_mac:
                        wifi_macs.append(current_mac)
                        wifi_info.setdefault(current_mac, {"iface": iface, "inactive_ms": "", "signal": ""})
                continue

            if not current_mac:
                continue

            if line.startswith("inactive time:"):
                wifi_info[current_mac]["inactive_ms"] = line.split(":", 1)[1].strip()
            elif line.startswith("signal:"):
                wifi_info[current_mac]["signal"] = line.split(":", 1)[1].strip()

    seen_clients = get_all_seen_clients()
    options = []

    for mac in sorted(set(wifi_macs)):
        item = seen_clients.get(mac, {})
        device = db.get("devices", {}).get(mac, {})

        hostname = device.get("hostname") or item.get("hostname") or "Unknown Device"
        ip = item.get("ip") or device.get("ip", "")
        voucher_code = device.get("voucher_code", "")
        online = bool(device.get("online"))

        if mac in db.get("blacklist", {}):
            status = "黑名单"
        elif mac in db.get("whitelist", {}):
            status = "白名单"
        elif online:
            status = "当前在线 / 已登录"
        else:
            status = "当前在线 / 未登录兑换码"

        label_parts = []
        label_parts.append(str(hostname))
        if ip:
            label_parts.append(str(ip))
        label_parts.append(status)
        if voucher_code:
            label_parts.append("兑换码 " + str(voucher_code))

        info = wifi_info.get(mac, {})
        if info.get("iface"):
            label_parts.append("WiFi " + str(info.get("iface")))
        if info.get("signal"):
            label_parts.append("信号 " + str(info.get("signal")))

        label = " | ".join(label_parts)
        options.append(f'<option value="{esc(mac)}" label="{esc(label)}">{esc(label)}</option>')

    return "\\n".join(options)


def customer_page(title, body):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>
body{{margin:0;font-family:Arial,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0f172a;color:#e5e7eb}}
.wrap{{max-width:560px;margin:0 auto;padding:28px 16px}}
.card{{background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;margin:14px 0;box-shadow:0 12px 36px #0005}}
h1{{margin-top:0;font-size:28px}}
.info{{white-space:pre-wrap;line-height:1.55;color:#cbd5e1}}
input,button{{width:100%;box-sizing:border-box;font-size:18px;border-radius:12px;border:1px solid #475569;padding:13px;margin:8px 0}}
input{{background:#020617;color:#e5e7eb}}
button,.btn{{background:#2563eb;color:white;border:0;cursor:pointer;text-align:center;text-decoration:none;display:block}}
.muted{{color:#94a3b8;font-size:14px}}
.ok{{color:#22c55e}}.bad{{color:#f87171}}
.row{{display:flex;justify-content:space-between;border-bottom:1px solid #334155;padding:9px 0;gap:12px}}

/* CUSTOMER_RESPONSIVE_OVERLAY_V2 */
html {{ min-height:100%; }}
body {{ min-height:100vh; }}
.wrap {{ width:100%; max-width:620px; padding:clamp(14px,4vw,32px) !important; }}
.card {{ width:100%; border-radius:clamp(14px,3vw,22px) !important; }}
.card h1 {{ font-size:clamp(24px,7vw,34px) !important; line-height:1.15 !important; }}
input,button,.btn {{ min-height:48px; }}
@media(max-width:520px) {{
  .wrap {{ padding:14px !important; }}
  .card {{ margin:10px 0 !important; padding:18px !important; }}
  .info {{ font-size:15px !important; }}
}}


/* CUSTOMER_COMPACT_FIX_V2 */
.wrap {{
  max-width:480px !important;
  padding:18px 14px !important;
}}

.card {{
  padding:16px !important;
  margin:10px 0 !important;
  border-radius:16px !important;
}}

h1 {{
  font-size:24px !important;
  line-height:1.18 !important;
}}

.info {{
  font-size:14px !important;
  line-height:1.45 !important;
}}

input, button, .btn {{
  font-size:16px !important;
  min-height:44px !important;
  padding:11px !important;
}}

@media(min-width:900px) {{
  .wrap {{
    max-width:460px !important;
    padding-top:34px !important;
  }}
}}

@media(max-width:520px) {{
  .wrap {{
    max-width:none !important;
    padding:10px !important;
  }}

  .card {{
    padding:14px !important;
    margin:8px 0 !important;
  }}

  h1 {{
    font-size:22px !important;
  }}
}}


/* CUSTOMER_NOTICE_PLAN_HIGHLIGHT_V1 */
.notice-box {{
  background:linear-gradient(135deg,rgba(250,204,21,.18),rgba(251,191,36,.08)) !important;
  border:1px solid rgba(250,204,21,.55) !important;
  color:#fde68a !important;
  font-size:16px !important;
  font-weight:800 !important;
  line-height:1.65 !important;
  padding:14px 15px !important;
  border-radius:14px !important;
  box-shadow:0 10px 24px rgba(250,204,21,.08) !important;
}}

.notice-box:before {{
  content:"Notice";
  display:block;
  color:#facc15;
  font-size:12px;
  font-weight:900;
  letter-spacing:.12em;
  text-transform:uppercase;
  margin-bottom:6px;
}}

.plan-box {{
  background:linear-gradient(135deg,rgba(37,99,235,.28),rgba(14,165,233,.10)) !important;
  border:1px solid rgba(96,165,250,.60) !important;
  color:#dbeafe !important;
  font-size:18px !important;
  font-weight:900 !important;
  line-height:1.75 !important;
  padding:16px 15px !important;
  border-radius:16px !important;
  text-align:center !important;
  box-shadow:0 12px 28px rgba(37,99,235,.16) !important;
}}

.plan-box:before {{
  content:"WiFi Plan";
  display:block;
  color:#93c5fd;
  font-size:12px;
  font-weight:900;
  letter-spacing:.14em;
  text-transform:uppercase;
  margin-bottom:6px;
}}

@media(max-width:520px) {{
  .notice-box {{
    font-size:15px !important;
    padding:13px !important;
  }}

  .plan-box {{
    font-size:17px !important;
    padding:14px !important;
  }}
}}


/* CUSTOMER_PLAN_CONTACT_HIGHLIGHT_V1 */
.plan-box {{
  background:linear-gradient(135deg,rgba(37,99,235,.30),rgba(14,165,233,.12)) !important;
  border:1px solid rgba(96,165,250,.70) !important;
  color:#dbeafe !important;
  font-size:18px !important;
  font-weight:900 !important;
  line-height:1.75 !important;
  padding:16px 15px !important;
  border-radius:16px !important;
  text-align:center !important;
  box-shadow:0 12px 28px rgba(37,99,235,.18) !important;
}}

.plan-box:before {{
  content:"WiFi Plan";
  display:block;
  color:#93c5fd;
  font-size:12px;
  font-weight:900;
  letter-spacing:.14em;
  text-transform:uppercase;
  margin-bottom:7px;
}}

.contact-box {{
  background:linear-gradient(135deg,rgba(34,197,94,.22),rgba(16,185,129,.10)) !important;
  border:1px solid rgba(74,222,128,.65) !important;
  color:#dcfce7 !important;
  font-size:16px !important;
  font-weight:800 !important;
  line-height:1.7 !important;
  padding:15px !important;
  border-radius:16px !important;
  box-shadow:0 12px 28px rgba(34,197,94,.12) !important;
}}

.contact-box:before {{
  content:"Contact";
  display:block;
  color:#86efac;
  font-size:12px;
  font-weight:900;
  letter-spacing:.14em;
  text-transform:uppercase;
  margin-bottom:7px;
}}

@media(max-width:520px) {{
  .plan-box {{
    font-size:17px !important;
    padding:14px !important;
  }}

  .contact-box {{
    font-size:15px !important;
    padding:14px !important;
  }}
}}


/* CUSTOMER_MOBILE_SCALE_FIX_V3 */
* {{
  box-sizing:border-box !important;
}}

html {{
  -webkit-text-size-adjust:100% !important;
  text-size-adjust:100% !important;
}}

body {{
  font-size:14px !important;
  overflow-x:hidden !important;
}}

.wrap {{
  width:100% !important;
  max-width:430px !important;
  margin:0 auto !important;
  padding:8px 10px !important;
}}

.card {{
  width:100% !important;
  max-width:100% !important;
  padding:12px !important;
  margin:7px 0 !important;
  border-radius:13px !important;
  box-shadow:0 6px 18px rgba(0,0,0,.22) !important;
}}

h1, .card h1 {{
  font-size:20px !important;
  line-height:1.18 !important;
  margin:0 0 8px 0 !important;
}}

.info {{
  font-size:13px !important;
  line-height:1.38 !important;
}}

.notice-box,
.plan-box,
.contact-box {{
  font-size:13px !important;
  line-height:1.42 !important;
  padding:10px !important;
  border-radius:12px !important;
  font-weight:700 !important;
}}

.notice-box:before,
.plan-box:before,
.contact-box:before {{
  font-size:10px !important;
  margin-bottom:4px !important;
}}

input,
button,
.btn {{
  font-size:16px !important;
  min-height:40px !important;
  padding:9px 10px !important;
  margin:6px 0 !important;
  border-radius:10px !important;
}}

.muted {{
  font-size:12px !important;
  line-height:1.35 !important;
}}

@media(max-width:420px) {{
  .wrap {{
    max-width:none !important;
    padding:7px 8px !important;
  }}

  .card {{
    padding:10px !important;
    margin:6px 0 !important;
  }}

  h1, .card h1 {{
    font-size:19px !important;
  }}

  .notice-box,
  .plan-box,
  .contact-box {{
    font-size:12.5px !important;
    padding:9px !important;
  }}
}}


/* CUSTOMER_CHECK_V2 */
.customer-check-hero h1 {{
  margin-bottom:12px !important;
}}

.customer-check-status {{
  border-radius:18px !important;
  padding:14px !important;
  border:1px solid rgba(255,255,255,.18) !important;
  background:rgba(255,255,255,.10) !important;
}}

.customer-check-status span {{
  display:block !important;
  color:#bfdbfe !important;
  font-size:13px !important;
  font-weight:800 !important;
  margin-bottom:4px !important;
}}

.customer-check-status b {{
  display:block !important;
  font-size:28px !important;
  line-height:1.1 !important;
}}

.customer-check-status p {{
  margin:9px 0 0 0 !important;
  color:#dbeafe !important;
  line-height:1.45 !important;
}}

.customer-check-status.ok b {{
  color:#86efac !important;
}}

.customer-check-status.bad b {{
  color:#fecaca !important;
}}

.customer-check-countdown {{
  margin-top:12px !important;
  border-radius:18px !important;
  padding:14px !important;
  background:rgba(15,23,42,.35) !important;
  border:1px solid rgba(255,255,255,.14) !important;
  text-align:center !important;
}}

.customer-check-countdown span {{
  display:block !important;
  color:#bfdbfe !important;
  font-size:13px !important;
  font-weight:800 !important;
  margin-bottom:5px !important;
}}

.customer-check-countdown b {{
  display:block !important;
  color:#ffffff !important;
  font-size:30px !important;
  line-height:1.1 !important;
}}

@media(max-width:480px) {{
  .customer-check-status b {{
    font-size:24px !important;
  }}

  .customer-check-countdown b {{
    font-size:26px !important;
  }}

  .row {{
    gap:8px !important;
  }}

  .row span {{
    font-size:12px !important;
  }}

  .row b {{
    font-size:13px !important;
    word-break:break-word !important;
  }}
}}

</style>
</head>
<body><div class="wrap">{body}</div></body>
</html>"""











































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































def mbps_to_kbps(value):
    try:
        value = str(value).strip()
        if value == "":
            return 0
        number = float(value)
        if number <= 0:
            return 0
        return int(number * 1024)
    except Exception:
        return 0


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


def voucher_status(voucher):
    if not voucher.get("enabled", True):
        return "已禁用"
    if int(voucher.get("minutes", 0)) == 0:
        if voucher.get("devices"):
            return "永久 / 使用中"
        return "永久 / 未使用"
    expire_at = int(voucher.get("expire_at", 0))
    first_used_at = int(voucher.get("first_used_at", 0))
    if first_used_at <= 0:
        return "未使用"
    if expire_at > 0 and expire_at <= now():
        return "已过期"
    return "使用中"


def remaining_text(voucher):
    minutes = int(voucher.get("minutes", 0))
    if minutes == 0:
        return "永久"
    expire_at = int(voucher.get("expire_at", 0))
    if expire_at <= 0:
        return "-"
    remain = expire_at - now()
    if remain <= 0:
        return "已过期"
    days = remain // 86400
    hours = (remain % 86400) // 3600
    mins = (remain % 3600) // 60
    if days > 0:
        return f"{days}天 {hours}小时 {mins}分钟"
    if hours > 0:
        return f"{hours}小时 {mins}分钟"
    return f"{mins}分钟"


def generate_voucher_code(length, mode, prefix, existing):
    length = max(3, min(24, int(length)))
    prefix = str(prefix or "").strip().upper()
    if len(prefix) >= length:
        prefix = prefix[:max(0, length - 1)]

    if mode == "mixed":
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    else:
        alphabet = "0123456789"

    body_length = max(1, length - len(prefix))
    for _ in range(10000):
        code = prefix + "".join(secrets.choice(alphabet) for _ in range(body_length))
        if code not in existing:
            return code
    raise RuntimeError("无法生成唯一兑换码，请增加长度或减少前缀")


def normalize_code(code):
    return str(code or "").strip().upper()


def create_voucher_record(code, minutes, max_devices, download_mbps, upload_mbps, speed_name, note):
    minutes = max(0, int(minutes))
    max_devices = max(1, int(max_devices))
    download_kbps = mbps_to_kbps(download_mbps)
    upload_kbps = mbps_to_kbps(upload_mbps)
    return {
        "code": code,
        "minutes": minutes,
        "max_devices": max_devices,
        "enabled": True,
        "note": str(note or ""),
        "created_at": now(),
        "first_used_at": 0,
        "expire_at": 0,
        "download_kbps": download_kbps,
        "upload_kbps": upload_kbps,
        "speed_profile_name": str(speed_name or "").strip() or "Default Plan",
        "devices": {}
    }





















def lock_status_text(lock):
    unlock_at = int(lock.get("unlock_at", 0))
    if unlock_at > now():
        return "锁定中"
    return "未锁定"


def lock_remaining_text(lock):
    unlock_at = int(lock.get("unlock_at", 0))
    remain = unlock_at - now()
    if remain <= 0:
        return "-"
    hours = remain // 3600
    minutes = (remain % 3600) // 60
    seconds = remain % 60
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def add_security_failure(mac, ip, reason):
    settings = load_settings()
    security = settings.get("security", {})
    if not security.get("enable_brute_force_protection", True):
        return

    db = load_db()
    key = mac if mac else ip
    if not key:
        return
    locks = db.setdefault("security_locks", {})
    item = locks.setdefault(key, {
        "mac": mac,
        "ip": ip,
        "failed_count": 0,
        "last_failed_at": 0,
        "unlock_at": 0,
        "reason": ""
    })
    item["mac"] = mac
    item["ip"] = ip
    item["failed_count"] = int(item.get("failed_count", 0)) + 1
    item["last_failed_at"] = now()
    item["reason"] = reason

    try:
        max_failed = int(security.get("max_failed_attempts", 5))
    except Exception:
        max_failed = 5
    try:
        lock_seconds = int(security.get("lock_seconds", 300))
    except Exception:
        lock_seconds = 300

    if max_failed < 1:
        max_failed = 1
    if lock_seconds < 10:
        lock_seconds = 10

    if item["failed_count"] >= max_failed:
        item["unlock_at"] = now() + lock_seconds

    save_db(db)


def clear_security_success(mac, ip):
    db = load_db()
    key = mac if mac else ip
    if key and key in db.get("security_locks", {}):
        del db["security_locks"][key]
        save_db(db)


def is_security_locked(mac, ip):
    settings = load_settings()
    security = settings.get("security", {})
    if not security.get("enable_brute_force_protection", True):
        return False, ""

    db = load_db()
    key = mac if mac else ip
    if not key:
        return False, ""
    lock = db.get("security_locks", {}).get(key)
    if not lock:
        return False, ""
    unlock_at = int(lock.get("unlock_at", 0))
    if unlock_at > now():
        return True, lock_remaining_text(lock)
    return False, ""


































































    return True, "备份已恢复"


def get_voucher_by_device(db, mac):
    if not mac:
        return "", None, None
    for code, voucher in db.get("vouchers", {}).items():
        devices = voucher.get("devices", {})
        if mac in devices:
            return code, voucher, devices[mac]
    return "", None, None


def is_voucher_expired(voucher):
    if not voucher:
        return True
    if int(voucher.get("minutes", 0)) == 0:
        return False
    expire_at = int(voucher.get("expire_at", 0))
    if expire_at <= 0:
        return False
    return expire_at <= now()


def active_device_count(voucher):
    count = 0
    for mac, device in voucher.get("devices", {}).items():
        if int(voucher.get("minutes", 0)) == 0:
            count += 1
            continue
        expire_at = int(device.get("expire_at", voucher.get("expire_at", 0)))
        if expire_at == 0 or expire_at > now():
            count += 1
    return count


def replace_offline_old_device_for_random_mac(db, voucher, new_mac):
    """
    随机 MAC 兼容模式：
    当兑换码设备数已满时，只允许用当前不在线的旧 MAC 名额替换成新 MAC。
    不绕过兑换码登录，不改变套餐时间，不扩大设备数。
    """
    new_mac = normalize_mac(new_mac)
    if not new_mac:
        return False, ""

    devices = voucher.setdefault("devices", {})
    if new_mac in devices:
        return False, ""

    try:
        realtime_clients = _wp_collect_current_wifi_clients_12h()
    except Exception:
        realtime_clients = {}

    if not isinstance(realtime_clients, dict):
        realtime_clients = {}

    realtime_macs = set(realtime_clients.keys())
    candidates = []

    for old_mac, old_device in list(devices.items()):
        fixed_old_mac = normalize_mac(old_mac)
        if not fixed_old_mac or fixed_old_mac == new_mac:
            continue

        # 旧 MAC 当前还连着 WiFi，不允许顶掉。
        if fixed_old_mac in realtime_macs:
            continue

        if not isinstance(old_device, dict):
            old_device = {}

        expire_at = int(old_device.get("expire_at", voucher.get("expire_at", 0)) or 0)

        # 已过期的旧记录不算有效占用，这里不优先处理。
        if expire_at > 0 and expire_at <= now():
            continue

        last_seen = int(old_device.get("last_seen", 0) or 0)
        login_at = int(old_device.get("login_at", 0) or 0)

        # 优先顶掉最久没出现的旧 MAC。
        candidates.append((last_seen, login_at, fixed_old_mac))

    if not candidates:
        return False, ""

    candidates.sort()
    old_mac = candidates[0][2]

    try:
        if old_mac in devices:
            del devices[old_mac]
    except Exception:
        return False, ""

    try:
        if old_mac in db.get("devices", {}):
            db["devices"][old_mac]["online"] = False
            db["devices"][old_mac]["last_seen"] = now()
    except Exception:
        pass

    try:
        nft_kick_device(old_mac)
    except Exception:
        pass

    try:
        safe_qos_remove_device(old_mac)
    except Exception:
        pass

    return True, old_mac


def mark_device_offline(db, mac):
    if mac in db.get("devices", {}):
        db["devices"][mac]["online"] = False
        db["devices"][mac]["last_seen"] = now()


def cleanup_expired_and_firewall():
    db = load_db()
    changed = False
    for code, voucher in db.get("vouchers", {}).items():
        if int(voucher.get("minutes", 0)) == 0:
            continue
        expire_at = int(voucher.get("expire_at", 0))
        if expire_at > 0 and expire_at <= now():
            for mac in list(voucher.get("devices", {}).keys()):
                mark_device_offline(db, mac)
                if mac in voucher.get("devices", {}):
                    voucher["devices"][mac]["online"] = False
            changed = True
    if changed:
        save_db(db)



# AUTH_HARD_DEVICE_LIMIT_V1
# Hard rule:
# - Authentication commits are serialized by a process/file lock.
# - For every voucher, voucher.devices must never exceed max_devices.
# - current_mac always wins; old extra devices are removed from DB, nft and QoS.
def _wp_enforce_voucher_device_limit(db, code, current_mac, reason="auth_hard_device_limit"):
    try:
        code = normalize_code(code)
        current_mac = normalize_mac(current_mac)
        vouchers = db.setdefault("vouchers", {})
        voucher = vouchers.get(code)
        if not isinstance(voucher, dict):
            return []

        devices = voucher.setdefault("devices", {})
        if not isinstance(devices, dict):
            devices = {}
            voucher["devices"] = devices

        try:
            max_devices = max(1, int(voucher.get("max_devices", 1) or 1))
        except Exception:
            max_devices = 1

        normalized_devices = {}
        for raw_mac, raw_device in list(devices.items()):
            mac = normalize_mac(raw_mac)
            if not mac:
                continue
            if not isinstance(raw_device, dict):
                raw_device = {}
            raw_device["mac"] = mac
            normalized_devices[mac] = raw_device
        voucher["devices"] = devices = normalized_devices

        rows = []
        for mac, device in devices.items():
            if not isinstance(device, dict):
                device = {}
            login_at = int(device.get("login_at", 0) or 0)
            last_seen = int(device.get("last_seen", 0) or 0)
            first_seen = int(device.get("first_seen", 0) or 0)
            ts = login_at if login_at > 0 else last_seen if last_seen > 0 else first_seen if first_seen > 0 else 0
            rows.append((mac == current_mac, ts, mac))

        keep = set()
        if current_mac and current_mac in devices:
            keep.add(current_mac)

        others = [row for row in rows if row[2] != current_mac]
        others.sort(key=lambda row: (row[1], row[2]), reverse=True)

        for _, _, mac in others:
            if len(keep) >= max_devices:
                break
            keep.add(mac)

        removed = []
        for mac in list(devices.keys()):
            if mac in keep:
                continue
            removed.append(mac)
            try:
                del devices[mac]
            except Exception:
                pass

            top = db.setdefault("devices", {}).get(mac)
            if isinstance(top, dict) and str(top.get("voucher_code", "") or "") == str(code):
                top["online"] = False
                top["last_seen"] = now()
                top["blocked_reason"] = reason

            try:
                nft_kick_device(mac)
            except Exception:
                pass

            try:
                safe_qos_remove_device(mac)
            except Exception:
                pass

            try:
                append_log("AUTH", "硬性设备数限制踢掉旧设备 " + str(mac), voucher_code=code, mac=current_mac, result="OK")
            except Exception:
                pass

        return removed
    except Exception as error:
        try:
            append_log("AUTH", "硬性设备数限制执行失败 " + str(error), voucher_code=code, mac=current_mac, result="WARN")
        except Exception:
            pass
        return []


def authenticate_voucher(code, client_ip):
    lock_file = None
    try:
        lock_file = open("/tmp/wifiportal_auth_commit.lock", "a+")
        try:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass
        return _authenticate_voucher_inner(code, client_ip)
    finally:
        try:
            if lock_file is not None:
                try:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                lock_file.close()
        except Exception:
            pass


def _authenticate_voucher_inner(code, client_ip):
    code = normalize_code(code)
    mac, hostname = get_client_identity(client_ip)

    if not mac:
        append_log("AUTH", "设备 MAC 识别失败", voucher_code=code, ip=client_ip, result="FAIL")
        return False, "Unable to identify your device. Please reconnect to WiFi and try again.", "", "", 0

    db = load_db()

    if mac in db.get("blacklist", {}):
        append_log("AUTH", "黑名单设备拒绝认证", voucher_code=code, mac=mac, ip=client_ip, result="FAIL")
        return False, "This device is blocked. Please contact the administrator.", mac, hostname, 0

    locked, remain = is_security_locked(mac, client_ip)
    if locked:
        settings = load_settings()
        security = settings.get("security", {})
        lock_message = str(security.get("lock_message", "Too many failed attempts. Please try again in {remain}.") or "")
        if not lock_message:
            lock_message = "Too many failed attempts. Please try again in {remain}."
        lock_message = lock_message.replace("{remain}", remain)
        append_log("AUTH", "设备因失败次数过多被锁定", voucher_code=code, mac=mac, ip=client_ip, result="FAIL")
        return False, lock_message, mac, hostname, 0

    if mac in db.get("whitelist", {}):
        item = db["whitelist"][mac]
        db.setdefault("devices", {})[mac] = {
            "mac": mac,
            "ip": client_ip,
            "hostname": item.get("device_name") or hostname,
            "voucher_code": "WHITELIST",
            "login_at": now(),
            "expire_at": 0,
            "last_seen": now(),
            "online": True,
            "download_kbps": 0,
            "upload_kbps": 0,
            "download_mbps": "Unlimited",
            "upload_mbps": "Unlimited",
            "speed_profile_name": "Whitelist"
        }
        save_db(db)
        if check_nft_table_exists():
            nft_add_whitelist(mac)
        safe_qos_remove_device(mac)
        clear_security_success(mac, client_ip)
        append_log("AUTH", "白名单设备允许", voucher_code="WHITELIST", mac=mac, ip=client_ip)
        return True, "Authentication successful. You are now connected.", mac, item.get("device_name") or hostname, 0

    if len(code) < 3:
        add_security_failure(mac, client_ip, "empty_or_short_code")
        append_log("AUTH", "兑换码格式错误", voucher_code=code, mac=mac, ip=client_ip, result="FAIL")
        return False, "Invalid voucher code.", mac, hostname, 0

    voucher = db.get("vouchers", {}).get(code)
    if not voucher:
        add_security_failure(mac, client_ip, "voucher_not_found")
        append_log("AUTH", "兑换码不存在", voucher_code=code, mac=mac, ip=client_ip, result="FAIL")
        return False, "Invalid voucher code.", mac, hostname, 0

    if not voucher.get("enabled", True):
        add_security_failure(mac, client_ip, "voucher_disabled")
        append_log("AUTH", "兑换码已禁用", voucher_code=code, mac=mac, ip=client_ip, result="FAIL")
        return False, "This voucher is disabled.", mac, hostname, 0

    minutes = int(voucher.get("minutes", 0))
    devices = voucher.setdefault("devices", {})

    if minutes != 0 and int(voucher.get("expire_at", 0)) > 0 and int(voucher.get("expire_at", 0)) <= now():
        add_security_failure(mac, client_ip, "voucher_expired")
        append_log("AUTH", "兑换码已过期", voucher_code=code, mac=mac, ip=client_ip, result="FAIL")
        return False, "This voucher has expired.", mac, hostname, 0

    if mac not in devices:
        # LAST_DEVICE_WINS_V1
        # Rules:
        # - max_devices == 1: new device replaces old device, old device is kicked offline.
        # - max_devices > 1: allow multiple devices up to max_devices, then reject.
        # - Same MAC can always reuse the voucher.
        try:
            max_devices = max(1, int(voucher.get("max_devices", 1) or 1))
        except Exception:
            max_devices = 1

        active_macs = []
        for bound_mac, bound_device in list(devices.items()):
            bound_mac = normalize_mac(bound_mac)
            if not bound_mac:
                continue
            if not isinstance(bound_device, dict):
                bound_device = {}

            if minutes == 0:
                active_macs.append(bound_mac)
                continue

            bound_expire_at = int(bound_device.get("expire_at", voucher.get("expire_at", 0)) or 0)
            if bound_expire_at == 0 or bound_expire_at > now():
                active_macs.append(bound_mac)

        active_macs = sorted(set(active_macs))

        if len(active_macs) >= max_devices:
            if max_devices == 1:
                # 普通码：新设备顶替旧设备
                for old_mac in list(active_macs):
                    old_mac = normalize_mac(old_mac)
                    if not old_mac or old_mac == mac:
                        continue

                    if old_mac in devices:
                        try:
                            del devices[old_mac]
                        except Exception:
                            pass

                    if old_mac in db.get("devices", {}) and isinstance(db["devices"].get(old_mac), dict):
                        db["devices"][old_mac]["online"] = False
                        db["devices"][old_mac]["last_seen"] = now()
                        db["devices"][old_mac]["blocked_reason"] = "replaced_by_new_device"

                    try:
                        nft_kick_device(old_mac)
                    except Exception:
                        pass

                    try:
                        safe_qos_remove_device(old_mac)
                    except Exception:
                        pass

                    append_log("AUTH", "普通码新设备顶替旧设备 " + str(old_mac), voucher_code=code, mac=mac, ip=client_ip, result="OK")
            else:
                # VIP_REPLACE_OLDEST_V1
                # VIP/多设备码满员后：新设备顶掉最早登录的旧设备。
                candidates = []
                for old_mac in list(active_macs):
                    old_mac = normalize_mac(old_mac)
                    if not old_mac or old_mac == mac:
                        continue

                    old_device = devices.get(old_mac, {})
                    if not isinstance(old_device, dict):
                        old_device = {}

                    login_at = int(old_device.get("login_at", 0) or 0)
                    first_seen = int(old_device.get("first_seen", 0) or 0)
                    last_seen = int(old_device.get("last_seen", 0) or 0)

                    sort_key = login_at if login_at > 0 else first_seen if first_seen > 0 else last_seen if last_seen > 0 else 9999999999
                    candidates.append((sort_key, old_mac))

                if not candidates:
                    add_security_failure(mac, client_ip, "vip_device_limit_reached_no_candidate")
                    append_log("AUTH", "VIP/多设备兑换码设备数已满且没有可顶替设备", voucher_code=code, mac=mac, ip=client_ip, result="FAIL")
                    return False, "Device limit reached for this voucher.", mac, hostname, 0

                candidates.sort(key=lambda x: (x[0], x[1]))
                old_mac = candidates[0][1]

                if old_mac in devices:
                    try:
                        del devices[old_mac]
                    except Exception:
                        pass

                if old_mac in db.get("devices", {}) and isinstance(db["devices"].get(old_mac), dict):
                    db["devices"][old_mac]["online"] = False
                    db["devices"][old_mac]["last_seen"] = now()
                    db["devices"][old_mac]["blocked_reason"] = "vip_replaced_by_new_device"

                try:
                    nft_kick_device(old_mac)
                except Exception:
                    pass

                try:
                    safe_qos_remove_device(old_mac)
                except Exception:
                    pass

                append_log("AUTH", "VIP/多设备码新设备顶替最早设备 " + str(old_mac), voucher_code=code, mac=mac, ip=client_ip, result="OK")

    first_used_at = int(voucher.get("first_used_at", 0))
    if first_used_at <= 0:
        first_used_at = now()
        voucher["first_used_at"] = first_used_at
        if minutes == 0:
            voucher["expire_at"] = 0
        else:
            voucher["expire_at"] = first_used_at + minutes * 60

    expire_at = int(voucher.get("expire_at", 0))
    remaining_seconds = 0 if expire_at == 0 else max(0, expire_at - now())

    device_record = {
        "mac": mac,
        "ip": client_ip,
        "hostname": hostname,
        "voucher_code": code,
        "login_at": now(),
        "expire_at": expire_at,
        "last_seen": now(),
        "online": True,
        "download_kbps": int(voucher.get("download_kbps", 0)),
        "upload_kbps": int(voucher.get("upload_kbps", 0)),
        "download_mbps": kbps_to_mbps(voucher.get("download_kbps", 0)),
        "upload_mbps": kbps_to_mbps(voucher.get("upload_kbps", 0)),
        "speed_profile_name": voucher.get("speed_profile_name", "Default Plan")
    }

    # AUTH_COMMIT_VERIFY_NFT_V1
    #
    # Important:
    # Multiple devices can authenticate at the same time. If we save an old db snapshot,
    # another request can overwrite this device's online=True state. Therefore reload
    # the latest DB immediately before final commit and update only this voucher/device.
    latest_db = load_db()
    latest_vouchers = latest_db.setdefault("vouchers", {})
    latest_voucher = latest_vouchers.get(code)

    if not isinstance(latest_voucher, dict):
        append_log("AUTH", "认证提交失败：兑换码在保存前丢失", voucher_code=code, mac=mac, ip=client_ip, result="FAIL")
        return False, "Authentication failed. Please try again.", mac, hostname, 0

    # AUTH_FINAL_COMMIT_CLEAN_BINDINGS_V1
    # Final commit must be based on latest_db, not the earlier db snapshot.
    # Rules:
    # 1. A MAC can belong to only one current voucher.
    # 2. If this voucher is full, remove the oldest bound device(s) from latest_db.
    # 3. Removed devices are kicked from nft/QoS and marked offline.
    # 4. Then add the new/current MAC and save.
    latest_devices = latest_voucher.setdefault("devices", {})
    if not isinstance(latest_devices, dict):
        latest_devices = {}
        latest_voucher["devices"] = latest_devices

    latest_top_devices = latest_db.setdefault("devices", {})

    # Remove this MAC from all other voucher bindings.
    for other_code, other_voucher in latest_vouchers.items():
        if other_code == code or not isinstance(other_voucher, dict):
            continue
        other_devices = other_voucher.get("devices", {})
        if isinstance(other_devices, dict) and mac in other_devices:
            try:
                del other_devices[mac]
                append_log("AUTH", "清理设备旧兑换码绑定 " + str(other_code), voucher_code=code, mac=mac, ip=client_ip, result="OK")
            except Exception:
                pass

    try:
        final_max_devices = max(1, int(latest_voucher.get("max_devices", 1) or 1))
    except Exception:
        final_max_devices = 1

    # Build current active list from latest voucher before adding current MAC.
    final_rows = []
    for old_mac, old_device in list(latest_devices.items()):
        old_mac = normalize_mac(old_mac)
        if not old_mac or old_mac == mac:
            continue

        if not isinstance(old_device, dict):
            old_device = {}

        if minutes == 0:
            active = True
        else:
            old_expire_at = int(old_device.get("expire_at", latest_voucher.get("expire_at", 0)) or 0)
            active = (old_expire_at == 0 or old_expire_at > now())

        if not active:
            continue

        old_login_at = int(old_device.get("login_at", 0) or 0)
        old_first_seen = int(old_device.get("first_seen", 0) or 0)
        old_last_seen = int(old_device.get("last_seen", 0) or 0)
        sort_key = old_login_at if old_login_at > 0 else old_first_seen if old_first_seen > 0 else old_last_seen if old_last_seen > 0 else 9999999999
        final_rows.append((sort_key, old_mac))

    # New device wins. If full, remove oldest devices until there is room.
    final_rows.sort(key=lambda x: (x[0], x[1]))
    while len(final_rows) >= final_max_devices:
        _, remove_mac = final_rows.pop(0)
        remove_mac = normalize_mac(remove_mac)
        if not remove_mac or remove_mac == mac:
            continue

        if remove_mac in latest_devices:
            try:
                del latest_devices[remove_mac]
            except Exception:
                pass

        if remove_mac in latest_top_devices and isinstance(latest_top_devices.get(remove_mac), dict):
            if str(latest_top_devices[remove_mac].get("voucher_code", "") or "") == str(code):
                latest_top_devices[remove_mac]["online"] = False
                latest_top_devices[remove_mac]["last_seen"] = now()
                latest_top_devices[remove_mac]["blocked_reason"] = "replaced_by_new_device_final_commit"

        try:
            nft_kick_device(remove_mac)
        except Exception:
            pass

        try:
            safe_qos_remove_device(remove_mac)
        except Exception:
            pass

        append_log("AUTH", "最终提交阶段踢掉旧设备 " + str(remove_mac), voucher_code=code, mac=mac, ip=client_ip, result="OK")

    latest_devices[mac] = device_record
    latest_top_devices[mac] = device_record

    _wp_enforce_voucher_device_limit(latest_db, code, mac, "auth_commit_hard_device_limit")

    latest_voucher["first_used_at"] = voucher.get("first_used_at", first_used_at)
    latest_voucher["expire_at"] = voucher.get("expire_at", expire_at)

    save_db(latest_db)

    ok_fw, fw_msg = nft_init_table()
    if not ok_fw:
        append_log("AUTH", "认证失败：防火墙初始化失败 " + str(fw_msg), voucher_code=code, mac=mac, ip=client_ip, result="FAIL")
        return False, "Authentication failed: firewall is not ready. Please try again.", mac, hostname, 0

    try:
        restore_firewall_sessions()
    except Exception as error:
        append_log("AUTH", "认证警告：恢复防火墙会话失败 " + str(error), voucher_code=code, mac=mac, ip=client_ip, result="WARN")

    allow_ok = nft_allow_device(mac, remaining_seconds)
    if not allow_ok:
        allow_ok = nft_allow_device(mac, remaining_seconds)

    ruleset_text = ""
    try:
        code_check, out_check, err_check = run_command(["/usr/sbin/nft", "list", "set", "inet", "wifiportal", "authed_macs"])
        if code_check == 0:
            ruleset_text = out_check.lower()
    except Exception:
        ruleset_text = ""

    if (not allow_ok) or (normalize_mac(mac) not in ruleset_text):
        latest_db = load_db()
        if mac in latest_db.get("devices", {}):
            latest_db["devices"][mac]["online"] = False
            latest_db["devices"][mac]["last_seen"] = now()
            save_db(latest_db)

        append_log(
            "AUTH",
            "认证失败：nft放行校验失败 allow_ok=" + str(allow_ok),
            voucher_code=code,
            mac=mac,
            ip=client_ip,
            result="FAIL"
        )
        return False, "Authentication failed: network access was not applied. Please try again.", mac, hostname, 0

    # Final DB verification after nft allow.
    latest_db = load_db()
    latest_device = latest_db.setdefault("devices", {}).get(mac, {})
    if not isinstance(latest_device, dict):
        latest_device = {}

    latest_device.update(device_record)
    latest_device["online"] = True
    latest_device["last_seen"] = now()
    latest_device["ip"] = client_ip
    latest_db["devices"][mac] = latest_device

    latest_voucher = latest_db.setdefault("vouchers", {}).setdefault(code, voucher)
    latest_voucher.setdefault("devices", {})[mac] = latest_device
    save_db(latest_db)

    safe_qos_apply_device(
        mac,
        client_ip,
        voucher.get("download_kbps", 0),
        voucher.get("upload_kbps", 0)
    )

    clear_security_success(mac, client_ip)
    append_log("AUTH", "认证成功并已校验放行", voucher_code=code, mac=mac, ip=client_ip)

    return True, "Authentication successful. You are now connected.", mac, hostname, remaining_seconds































































































































































































































































































































































































































































































































































































class Handler(BaseHTTPRequestHandler):
    server_version = "local-wifiportal-openwrt/2.0"

    def show_admin_devices(self):
        cleanup_expired_and_firewall()
        db = load_db()
        known_clients = get_all_seen_clients()

        for mac, device in db.get("devices", {}).items():
            known_clients.setdefault(mac, {"mac": mac, "ip": device.get("ip", ""), "hostname": device.get("hostname", "Unknown Device")})
            if device.get("ip"):
                known_clients[mac]["ip"] = device.get("ip", "")
            if device.get("hostname"):
                known_clients[mac]["hostname"] = device.get("hostname", "Unknown Device")

        rows = []
        for mac, client in sorted(known_clients.items(), key=lambda x: (x[1].get("ip", ""), x[0])):
            device = db.get("devices", {}).get(mac, {})
            hostname = device.get("hostname") or client.get("hostname") or "Unknown Device"
            ip = client.get("ip") or device.get("ip", "")
            voucher_code = device.get("voucher_code", "")
            online = bool(device.get("online"))
            expire_at = int(device.get("expire_at", 0) or 0)

            if expire_at > 0 and expire_at <= now():
                online = False

            if mac in db.get("blacklist", {}):
                status = "黑名单"
            elif mac in db.get("whitelist", {}):
                status = "白名单/已放行"
            elif online:
                status = "已登录"
            else:
                status = "未登录"

            if not voucher_code:
                voucher_code = "-"

            if expire_at == 0 and online:
                remaining = "永久"
                expire_text = "永久"
            elif expire_at > 0 and online:
                seconds = max(0, expire_at - now())
                remaining = f"{seconds // 3600}小时 {(seconds % 3600) // 60}分钟"
                expire_text = format_time(expire_at)
            else:
                remaining = "-"
                expire_text = "-"

            download = device.get("download_mbps", "-")
            upload = device.get("upload_mbps", "-")
            plan_name = device.get("speed_profile_name", "-")
            speed = f"{esc(download)} ↓ / {esc(upload)} ↑ Mbps"

            operation_html = f"""
<form method="post" action="/admin/blacklist-add" style="display:inline" onsubmit="return confirm('确认加入黑名单？')">
<input type="hidden" name="mac" value="{esc(mac)}">
<input type="hidden" name="device_name" value="{esc(hostname)}">
<input type="hidden" name="reason" value="Blocked from devices page">
<button class="danger" type="submit">拉黑</button>
</form>
"""

            if mac in db.get("devices", {}):
                operation_html = f"""
<form method="post" action="/admin/device-kick" style="display:inline"><input type="hidden" name="mac" value="{esc(mac)}"><button type="submit">踢下线</button></form>
<form method="post" action="/admin/device-unbind" style="display:inline" onsubmit="return confirm('确认解绑这个设备？')"><input type="hidden" name="mac" value="{esc(mac)}"><button class="danger" type="submit">解绑</button></form>
""" + operation_html

            rows.append(f"""
<tr>
<td>{esc(hostname)}</td>
<td><code>{esc(mac)}</code></td>
<td>{esc(ip)}</td>
<td><code>{esc(voucher_code)}</code></td>
<td>{speed}<br><span class="muted">{esc(plan_name)}</span></td>
<td>{esc(format_time(device.get("login_at", 0)))}</td>
<td>{esc(expire_text)}</td>
<td>{esc(remaining)}</td>
<td><b>{esc(status)}</b></td>
<td>{operation_html}</td>
</tr>
""")

        body = f"""
<div class="card">
<h1>在线 / 已连接设备</h1>
<p class="muted">这里会显示 DHCP/ARP 里看到的所有已连接 WiFi/LAN 设备。未输入兑换码的设备会显示“未登录”。</p>
</div>

<div class="card">
<table>
<tr><th>设备名</th><th>MAC</th><th>IP</th><th>兑换码</th><th>套餐网速</th><th>登录时间</th><th>到期时间</th><th>剩余时间</th><th>状态</th><th>操作</th></tr>
{''.join(rows) if rows else '<tr><td colspan="10" class="muted">暂无设备记录</td></tr>'}
</table>
</div>
"""
        self.send_html(admin_page("在线设备", body))

    def log_message(self, fmt, *args):
        print("[%s] %s - %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), self.client_address[0], fmt % args), flush=True)

    # QUIET_CLIENT_DISCONNECT_V1
    def send_html(self, content, status=200, headers=None):
        try:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            if headers:
                for key, value in headers.items():
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            # Mobile captive-portal WebView / browser closed the socket early.
            # This is harmless and should not pollute logs.
            return

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def read_form(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8", "ignore")
        return {key: values[-1] for key, values in urllib.parse.parse_qs(raw).items()}

    def get_cookie(self, name):
        cookie = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        if name in cookie:
            return cookie[name].value
        return ""

    def is_admin(self):
        return self.get_cookie("wp_admin") == SESSION_SECRET

    def require_admin(self):
        if self.is_admin():
            return True
        self.redirect("/admin/login")
        return False

    def do_GET(self):
        if self.path.startswith("/admin/api/devices-realtime"):
            self.admin_devices_realtime_api()
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        queries = urllib.parse.parse_qs(parsed.query)
        default_code = queries.get("code", [""])[0].strip()

        if path in ["/", "/generate_204", "/gen_204", "/hotspot-detect.html", "/library/test/success.html", "/ncsi.txt", "/connecttest.txt"]:
            self.show_customer_login(default_code)
            return

        if path == "/check":
            self.show_customer_check()
            return

        if path.startswith("/admin"):
            self.handle_admin_get(path)
            return

        self.show_customer_login(default_code)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/auth":
            self.show_auth_placeholder()
            return

        if path.startswith("/admin"):
            self.handle_admin_post(path)
            return

        self.send_html(customer_page("Not Found", "<div class='card'><h1>Not Found</h1></div>"), 404)

    def show_customer_login(self, default_code=""):
        settings = load_settings()
        portal = settings.get("portal_page", {})
        title = portal.get("title", "WiFi Authentication")
        notice = portal.get("notice", "Please enter your voucher code to access the Internet.")
        plan_text = portal.get("plan_text", "")
        contact_text = portal.get("contact_text", "")
        footer_text = portal.get("footer_text", "")

        body = f"""
<div class="card">
<h1>{esc(title)}</h1>
<div class="info">{esc(notice)}</div>
</div>

<div class="card">
<div class="info plan-box">{esc(plan_text)}</div>
</div>

<div class="card">
<form method="post" action="/auth">
<input name="code" value="{esc(default_code)}" placeholder="Voucher Code" autocomplete="off" autofocus required>
<button type="submit">Connect</button>
</form>
<p class="muted"><a style="color:#93c5fd" href="http://{esc(LAN_IP)}/check">Check device status</a></p>
</div>

<div class="card">
<div class="info contact-box">{esc(contact_text)}</div>
<p class="muted">{esc(footer_text)}</p>
</div>
"""
        self.send_html(customer_page(title, body))

    def show_customer_check(self):
        # CHECK_PAGE_FAST_NO_GLOBAL_CLEANUP_V1
        #
        # /check is a customer status page and must be fast.
        # Global expired-voucher cleanup can take several seconds because it may
        # scan all vouchers and touch nft/qos. That cleanup already runs in the
        # background worker every 60 seconds, so do not run it on every /check.
        ip = self.client_address[0]
        mac, hostname = get_client_identity(ip)
        db = load_db()
        settings = load_settings()
        portal = settings.get("portal_page", {})

        device = db.get("devices", {}).get(mac, {}) if mac else {}
        if device.get("hostname") and device.get("hostname") != "Unknown Device":
            hostname = device.get("hostname")

        voucher_code = device.get("voucher_code", "-")
        online = bool(device.get("online"))
        expire_at_raw = int(device.get("expire_at", 0) or 0)
        login_at_raw = int(device.get("login_at", 0) or 0)

        if expire_at_raw > 0 and expire_at_raw <= now():
            online = False

        status = "Connected" if online else "Not Connected"
        status_class = "ok" if online else "bad"
        status_hint = "Your device is authenticated and can access the Internet." if online else "Your device is not authenticated or your session has expired."

        plan = device.get("speed_profile_name", "-")
        download = device.get("download_mbps", "-")
        upload = device.get("upload_mbps", "-")
        login_at = format_time(login_at_raw)
        expire_at = "Permanent" if expire_at_raw == 0 and online else format_time(expire_at_raw)

        remaining_seconds = 0
        if not online:
            remaining = "-"
        elif expire_at_raw == 0:
            remaining = "Permanent"
        else:
            remaining_seconds = max(0, expire_at_raw - now())
            days = remaining_seconds // 86400
            hours = (remaining_seconds % 86400) // 3600
            minutes = (remaining_seconds % 3600) // 60
            if days > 0:
                remaining = f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                remaining = f"{hours}h {minutes}m"
            else:
                remaining = f"{minutes}m"

        contact_text = portal.get("contact_text", "")
        footer_text = portal.get("footer_text", "")

        voucher_display = voucher_code if voucher_code else "-"
        mac_display = mac or "-"

        if online:
            action_buttons = f"""
<a class="btn" href="/check">Check Connection</a>
<a class="btn" href="/check">Refresh Status</a>
"""
        else:
            action_buttons = f"""
<a class="btn" href="/">Enter Voucher Code</a>
<a class="btn" href="/check">Refresh Status</a>
"""

        countdown_html = ""
        if online and remaining_seconds > 0:
            countdown_html = f"""
<div class="customer-check-countdown">
  <span>Live Countdown</span>
  <b id="check-countdown" data-seconds="{remaining_seconds}">{esc(remaining)}</b>
</div>
<script>
(function(){{
  var el = document.getElementById("check-countdown");
  if (!el) return;
  var seconds = parseInt(el.getAttribute("data-seconds") || "0", 10);
  function formatRemain(s) {{
    if (s <= 0) return "Expired";
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    if (d > 0) return d + "d " + h + "h " + m + "m";
    if (h > 0) return h + "h " + m + "m " + sec + "s";
    return m + "m " + sec + "s";
  }}
  setInterval(function(){{
    seconds -= 1;
    el.textContent = formatRemain(seconds);
    if (seconds <= 0) {{
      el.className = "bad";
    }}
  }}, 1000);
}})();
</script>
"""

        body = f"""
<div class="card customer-check-hero">
<h1>Device Status</h1>
<div class="customer-check-status {status_class}">
  <div>
    <span>Status</span>
    <b>{esc(status)}</b>
  </div>
  <p>{esc(status_hint)}</p>
</div>
{countdown_html}
</div>

<div class="card">
<h2>Access Information</h2>
<div class="row"><span>Voucher Code</span><b>{esc(voucher_display)}</b></div>
<div class="row"><span>Speed Plan</span><b>{esc(plan)}</b></div>
<div class="row"><span>Download Speed</span><b>{esc(download)} Mbps</b></div>
<div class="row"><span>Upload Speed</span><b>{esc(upload)} Mbps</b></div>
<div class="row"><span>Remaining Time</span><b>{esc(remaining)}</b></div>
<div class="row"><span>Login Time</span><b>{esc(login_at)}</b></div>
<div class="row"><span>Expire Time</span><b>{esc(expire_at)}</b></div>
</div>

<div class="card">
<h2>Device Information</h2>
<div class="row"><span>Device Name</span><b>{esc(hostname or 'Unknown Device')}</b></div>
<div class="row"><span>Device MAC</span><b>{esc(mac_display)}</b></div>
<div class="row"><span>Device IP</span><b>{esc(ip)}</b></div>
</div>

<div class="card">
<h2>Actions</h2>
<p>{action_buttons}</p>
<p class="muted">If the status is wrong, reconnect WiFi and refresh this page.</p>
</div>

<div class="card">
<h2>Support</h2>
<div class="info contact-box">{esc(contact_text) if contact_text else 'Please contact the WiFi administrator if you need help.'}</div>
<p class="muted">{esc(footer_text)}</p>
</div>
"""
        self.send_html(customer_page("Device Status", body))

    def show_auth_placeholder(self):
        form = self.read_form()
        code = form.get("code", "")
        ok, message, mac, hostname, remaining_seconds = authenticate_voucher(code, self.client_address[0])

        if ok:
            if remaining_seconds == 0:
                remain_text = "Permanent or unlimited access"
            else:
                remain_minutes = max(0, remaining_seconds // 60)
                remain_text = f"Remaining time: {remain_minutes} minutes"

            body = f"""
<div class="card success-card">
<h1 class="ok">Connected Successfully</h1>
<p>{esc(message)}</p>

<div class="info" style="text-align:center">
<div style="font-size:13px;opacity:.85;margin-bottom:6px">Checking connection in</div>
<div id="success-countdown" style="font-size:42px;font-weight:900;line-height:1">3</div>
<div style="font-size:13px;opacity:.85;margin-top:6px">seconds</div>
</div>

<p class="muted">Device Name: {esc(hostname)}</p>
<p class="muted">Device MAC: {esc(mac)}</p>
<p class="muted">{esc(remain_text)}</p>

<a class="btn" href="/check">Check Connection Now</a>
<a class="btn" href="http://{esc(LAN_IP)}/check" style="margin-top:8px;background:#0f766e">Check Device Status</a>

<p class="muted" style="text-align:center">If the Internet is already working, you can close this page.</p>
</div>

<script>
(function() {{
  var seconds = 3;
  var el = document.getElementById("success-countdown");
  function tick() {{
    if (el) {{ el.textContent = seconds; }}
    if (seconds <= 0) {{
      window.location.href = "/check";
      return;
    }}
    seconds -= 1;
    setTimeout(tick, 1000);
  }}
  tick();
}})();
</script>
"""
            self.send_html(customer_page("Connected Successfully", body))
            return

        popup_script = ""
        settings = load_settings()
        security = settings.get("security", {})
        lock_message_template = str(security.get("lock_message", "") or "")
        if lock_message_template and mac:
            locked_now, remain_now = is_security_locked(mac, self.client_address[0])
            if locked_now:
                popup_text = message
                popup_script = "<script>alert(" + json.dumps(popup_text) + ");</script>"

        locked_now_for_page = False
        if mac:
            locked_now_for_page, remain_now_for_page = is_security_locked(mac, self.client_address[0])

        if locked_now_for_page:
            failed_title = "Device Temporarily Locked"
            failed_hint = "Please wait for the lock time to expire, or contact the administrator."
            button_text = "Back to Login"
        else:
            failed_title = "Authentication Failed"
            failed_hint = "Please check your voucher code and try again."
            button_text = "Try Again"

        body = f"""
<div class="card failed-card">
<h1 class="bad">{esc(failed_title)}</h1>

<div class="info" style="text-align:center;border-color:rgba(248,113,113,.45);background:rgba(127,29,29,.22)">
<div style="font-size:13px;opacity:.85;margin-bottom:6px">Message</div>
<div style="font-size:20px;font-weight:900;line-height:1.25">{esc(message)}</div>
</div>

<p class="muted" style="text-align:center">{esc(failed_hint)}</p>

<div class="card" style="box-shadow:none;margin-top:10px;background:rgba(15,23,42,.55)">
<p class="muted">Device Name: {esc(hostname or 'Unknown Device')}</p>
<p class="muted">Device MAC: {esc(mac or '-')}</p>
</div>

<a class="btn" href="/">{esc(button_text)}</a>
<p class="muted" style="text-align:center">Contact admin if you believe this is a mistake.</p>
</div>
{popup_script}
"""
        self.send_html(customer_page(failed_title, body))

    def handle_admin_get(self, path):
        if path == "/admin/login":
            body = """
<div class="card" style="max-width:460px;margin:80px auto">
<h1>后台登录</h1>
<form method="post" action="/admin/login">
<p><input name="username" placeholder="用户名" value="admin" required style="width:100%;box-sizing:border-box"></p>
<p><input name="password" type="password" placeholder="密码" required style="width:100%;box-sizing:border-box"></p>
<p><button type="submit" style="width:100%">登录</button></p>
</form>
</div>
"""
            self.send_html(admin_page("后台登录", body, logged_in=False))
            return

        if path == "/admin/logout":
            self.send_html(
                admin_page("退出登录", "<div class='card'><h1>已退出登录</h1><a class='btn' href='/admin/login'>重新登录</a></div>", logged_in=False),
                headers={"Set-Cookie": "wp_admin=; Path=/; Max-Age=0"}
            )
            return

        if not self.require_admin():
            return
        if path == "/admin/plan-add":
            self.admin_plan_add()
            return

        if path == "/admin/plan-delete":
            self.admin_plan_delete()
            return

        if path == "/admin/plan-edit-save":
            self.admin_plan_edit_save()
            return


        if path == "/admin":
            self.show_admin_dashboard()
            return

        if path == "/admin/health":
            self.show_admin_health()
            return

        if path == "/admin/maintenance":
            self.show_admin_maintenance()
            return

        if path == "/admin/help":
            self.show_admin_help()
            return

        if path == "/admin/db-check":
            self.show_admin_db_check()
            return

        if path == "/admin/db-fix":
            self.show_admin_db_fix()
            return

        if path == "/admin/settings":
            self.show_admin_settings()
            return

        if path == "/admin/password":
            self.show_admin_password()
            return

        if path == "/admin/vouchers":
            self.show_admin_vouchers()
            return

        if path == "/admin/expiring":
            self.show_admin_expiring_vouchers()
            return

        if path == "/admin/voucher-detail":
            self.show_admin_voucher_detail()
            return

        if path == "/admin/voucher-edit":
            self.show_admin_voucher_edit()
            return

        if path == "/admin/export-unused":
            self.show_export_unused()
            return

        if path == "/admin/vouchers-print" or path == "/admin/vouchers/print":
            self.show_admin_vouchers_print()
            return

        if path == "/admin/api/devices-realtime":
            self.admin_devices_realtime_api()
            return

        if path == "/admin/devices":
            self.show_admin_devices()
            return

        if path == "/admin/whitelist":
            self.show_admin_whitelist()
            return

        if path == "/admin/blacklist":
            self.show_admin_blacklist()
            return

        if path == "/admin/security":
            self.show_admin_security()
            return

        if path == "/admin/logs":
            self.show_admin_logs()
            return

        if path == "/admin/backup":
            self.show_admin_backup()
            return

        if path == "/admin/firewall":
            self.show_admin_firewall()
            return

        if path == "/admin/qos":
            self.show_admin_qos()
            return

        self.send_html(admin_page("未找到", "<div class='card'><h1>页面不存在</h1></div>"), 404)

    def handle_admin_post(self, path):
        if path == "/admin/login":
            form = self.read_form()
            username = form.get("username", "")
            password = form.get("password", "")
            if username == "admin" and verify_admin_password(password):
                append_log("ADMIN", "后台登录成功", ip=self.client_address[0])
                append_admin_audit(self, "后台登录成功")
                self.send_html(
                    admin_page("登录成功", "<div class='card'><h1>登录成功</h1><p>正在进入后台...</p></div>", logged_in=False),
                    headers={
                        "Set-Cookie": f"wp_admin={SESSION_SECRET}; Path=/; HttpOnly; SameSite=Lax",
                        "Refresh": "0; url=/admin"
                    }
                )
                return
            append_log("ADMIN", "后台登录失败", ip=self.client_address[0], result="FAIL")
            append_admin_audit(self, "后台登录失败", result="FAIL")
            self.send_html(admin_page("登录失败", "<div class='card'><h1 class='bad'>用户名或密码错误</h1><a class='btn' href='/admin/login'>返回</a></div>", logged_in=False))
            return

        if not self.require_admin():
            return

        if path == "/admin/settings":
            form = self.read_form()
            settings = load_settings()
            settings.setdefault("portal_page", {})
            settings["portal_page"]["title"] = form.get("title", "")
            settings["portal_page"]["notice"] = form.get("notice", "")
            settings["portal_page"]["plan_text"] = form.get("plan_text", "")
            settings["portal_page"]["contact_text"] = form.get("contact_text", "")
            settings["portal_page"]["footer_text"] = form.get("footer_text", "")
            save_settings(settings)
            append_log("ADMIN", "页面设置已保存")
            self.send_html(admin_page("设置已保存", "<div class='card'><h1 class='ok'>页面设置已保存</h1><a class='btn' href='/admin/settings'>返回</a></div>"))
            return

        if path == "/admin/password":
            form = self.read_form()
            current_password = form.get("current_password", "")
            new_password = form.get("new_password", "")
            confirm_password = form.get("confirm_password", "")
            if not verify_admin_password(current_password):
                self.send_html(admin_page("修改失败", "<div class='card'><h1 class='bad'>当前密码错误</h1><a class='btn' href='/admin/password'>返回</a></div>"))
                return
            if new_password != confirm_password:
                self.send_html(admin_page("修改失败", "<div class='card'><h1 class='bad'>两次输入的新密码不一致</h1><a class='btn' href='/admin/password'>返回</a></div>"))
                return
            ok, message = update_admin_password(new_password)
            if not ok:
                self.send_html(admin_page("修改失败", f"<div class='card'><h1 class='bad'>{esc(message)}</h1><a class='btn' href='/admin/password'>返回</a></div>"))
                return
            self.send_html(
                admin_page("修改成功", f"<div class='card'><h1 class='ok'>{esc(message)}</h1><a class='btn' href='/admin/login'>重新登录</a></div>", logged_in=False),
                headers={"Set-Cookie": "wp_admin=; Path=/; Max-Age=0"}
            )
            return

        if path == "/admin/plan-add":
            self.admin_plan_add()
            return

        if path == "/admin/plan-delete":
            self.admin_plan_delete()
            return

        if path == "/admin/plan-edit-save":
            self.admin_plan_edit_save()
            return

        if path == "/admin/voucher-add":
            self.admin_voucher_add()
            return

        if path == "/admin/voucher-generate":
            self.admin_voucher_generate()
            return

        if path == "/admin/voucher-reset":
            self.admin_voucher_reset()
            return

        if path == "/admin/voucher-extend":
            self.admin_voucher_extend()
            return

        if path == "/admin/voucher-toggle":
            self.admin_voucher_toggle()
            return

        if path == "/admin/voucher-delete":
            self.admin_voucher_delete()
            return

        if path == "/admin/voucher-bulk-delete":
            self.admin_voucher_bulk_delete()
            return

        if path == "/admin/voucher-delete-expired":
            self.admin_voucher_delete_expired()
            return

        if path == "/admin/voucher-device-unbind":
            self.admin_voucher_device_unbind()
            return

        if path == "/admin/voucher-edit-save":
            self.admin_voucher_edit_save()
            return

        if path == "/admin/whitelist-add":
            self.admin_whitelist_add()
            return

        if path == "/admin/whitelist-delete":
            self.admin_whitelist_delete()
            return

        if path == "/admin/blacklist-add":
            self.admin_blacklist_add()
            return

        if path == "/admin/blacklist-delete":
            self.admin_blacklist_delete()
            return

        if path == "/admin/security-save":
            self.admin_security_save()
            return

        if path == "/admin/security-unlock":
            self.admin_security_unlock()
            return

        if path == "/admin/security-clear-all":
            self.admin_security_clear_all()
            return

        if path == "/admin/logs-clear":
            self.admin_logs_clear()
            return

        if path == "/admin/backup-create":
            self.admin_backup_create()
            return

        if path == "/admin/backup-clean":
            self.admin_backup_clean()
            return

        if path == "/admin/backup-restore":
            self.admin_backup_restore()
            return

        if path == "/admin/backup-download":
            self.admin_backup_download()
            return

        if path == "/admin/device-kick":
            self.admin_device_kick()
            return

        if path == "/admin/device-unbind":
            self.admin_device_unbind()
            return

        if path == "/admin/firewall-enable":
            self.admin_firewall_enable()
            return

        if path == "/admin/firewall-disable":
            self.admin_firewall_disable()
            return

        if path == "/admin/firewall-restore-sessions":
            self.admin_firewall_restore_sessions()
            return

        if path == "/admin/qos-init":
            self.admin_qos_init()
            return

        if path == "/admin/qos-clear":
            self.admin_qos_clear()
            return

        if path == "/admin/qos-restore":
            self.admin_qos_restore()
            return

        if path == "/admin/maintenance-restart":
            self.admin_maintenance_restart()
            return

        if path == "/admin/db-fix-run":
            self.admin_db_fix_run()
            return

        self.send_html(admin_page("未找到", "<div class='card'><h1>操作不存在</h1></div>"), 404)





    def show_admin_db_fix(self):
        body = """
<div class="card">
<h1>数据库一键修复</h1>
<p class="muted">这个功能会先自动创建备份，然后只修复低风险数据问题。</p>
<div class="grid">
<div class="stat">修复模式<b>安全修复</b></div>
<div class="stat">修复前备份<b>自动创建</b></div>
<div class="stat">认证逻辑<b>不修改</b></div>
<div class="stat">兑换码删除<b>不会删除</b></div>
</div>
</div>

<div class="card">
<h2>会修复的问题</h2>
<p>1. 补齐缺失的数据库顶层字段。</p>
<p>2. 补齐兑换码缺失的默认字段。</p>
<p>3. 修复异常的 <code>voucher.devices</code> 字段。</p>
<p>4. 清理兑换码里绑定但设备表不存在的孤儿 MAC。</p>
<p>5. 清理设备引用不存在兑换码的错误绑定。</p>
<p>6. 将已过期但仍标记在线的设备改为离线，并清理放行/限速。</p>
<p>7. 同步设备限速参数到兑换码当前限速参数。</p>
<p>8. 规范化黑白名单 MAC 格式。</p>
<p>9. 兼容化非标准日志格式。</p>
</div>

<div class="card">
<h2>不会做的事</h2>
<p class="muted">不会删除兑换码、不会删除设备历史、不会清空日志、不会恢复备份、不会关闭防火墙。</p>
<p class="muted">如果修复后有问题，可以到备份恢复页面恢复自动创建的修复前备份。</p>
</div>

<div class="card">
<h2>执行修复</h2>
<form method="post" action="/admin/db-fix-run" onsubmit="return confirm('确认执行一键修复？系统会先自动创建备份，然后修复低风险数据问题。')">
<button class="danger" type="submit">先备份并执行一键修复</button>
<a class="btn" href="/admin/db-check">返回数据检查</a>
<a class="btn" href="/admin/backup">先去备份</a>
</form>
</div>
"""
        self.send_html(admin_page("数据库一键修复", body))

    def admin_db_fix_run(self):
        actions = []
        warnings = []
        backup_file = ""

        def add_action(text):
            actions.append(str(text))

        def add_warning(text):
            warnings.append(str(text))

        try:
            backup_file = create_backup()
            add_action("修复前已自动创建备份：" + str(backup_file))
        except Exception as error:
            self.send_html(admin_page("修复失败", f"""
<div class="card">
<h1 class="bad">无法创建备份，已停止修复</h1>
<p>错误：{esc(str(error))}</p>
<p class="muted">为避免风险，备份失败时不会执行任何修复。</p>
<p><a class="btn" href="/admin/db-fix">返回</a></p>
</div>
"""))
            return

        try:
            db = load_db()
            if not isinstance(db, dict):
                raise Exception("数据库根对象不是 dict")
        except Exception as error:
            self.send_html(admin_page("修复失败", f"""
<div class="card">
<h1 class="bad">数据库读取失败，已停止修复</h1>
<p>错误：{esc(str(error))}</p>
<p>已创建备份：<code>{esc(str(backup_file))}</code></p>
<p><a class="btn" href="/admin/backup">去备份恢复</a></p>
</div>
"""))
            return

        changed_db = False

        # 顶层字段
        if not isinstance(db.get("vouchers"), dict):
            db["vouchers"] = {}
            changed_db = True
            add_action("修复顶层字段 vouchers")
        if not isinstance(db.get("devices"), dict):
            db["devices"] = {}
            changed_db = True
            add_action("修复顶层字段 devices")
        if not isinstance(db.get("logs"), list):
            db["logs"] = []
            changed_db = True
            add_action("修复顶层字段 logs")
        if not isinstance(db.get("whitelist"), dict):
            db["whitelist"] = {}
            changed_db = True
            add_action("修复顶层字段 whitelist")
        if not isinstance(db.get("blacklist"), dict):
            db["blacklist"] = {}
            changed_db = True
            add_action("修复顶层字段 blacklist")
        if not isinstance(db.get("security_locks"), dict):
            db["security_locks"] = {}
            changed_db = True
            add_action("修复顶层字段 security_locks")
        if not isinstance(db.get("security_failures"), dict):
            db["security_failures"] = {}
            changed_db = True
            add_action("修复顶层字段 security_failures")

        vouchers = db.get("vouchers", {})
        devices = db.get("devices", {})

        # 兑换码字段修复
        for code, voucher in list(vouchers.items()):
            if not isinstance(voucher, dict):
                add_warning(f"兑换码 {code} 不是 dict，已跳过。")
                continue

            changed_voucher = False

            defaults = {
                "created_at": now(),
                "first_used_at": 0,
                "expire_at": 0,
                "minutes": 1440,
                "max_devices": 1,
                "download_kbps": 0,
                "upload_kbps": 0,
                "speed_profile_name": "Default Plan",
                "note": "",
                "enabled": True,
            }

            for field, value in defaults.items():
                if field not in voucher:
                    voucher[field] = value
                    changed_voucher = True

            if not isinstance(voucher.get("devices"), dict):
                voucher["devices"] = {}
                changed_voucher = True
                add_action(f"修复兑换码 {code} 的 devices 字段")

            if changed_voucher:
                changed_db = True
                add_action(f"补齐兑换码 {code} 缺失字段")

        # 清理 voucher.devices 里设备表不存在的 MAC，并规范 MAC key
        for code, voucher in list(vouchers.items()):
            if not isinstance(voucher, dict):
                continue
            bound = voucher.get("devices", {})
            if not isinstance(bound, dict):
                voucher["devices"] = {}
                changed_db = True
                add_action(f"重置兑换码 {code} 异常 devices 字段")
                continue

            new_bound = {}
            removed = 0
            normalized = 0

            for mac, info in list(bound.items()):
                mac_norm = normalize_mac(mac)
                if not mac_norm:
                    removed += 1
                    continue

                device = devices.get(mac_norm) or devices.get(mac)
                if not device:
                    removed += 1
                    continue

                if mac_norm != mac:
                    normalized += 1

                if not isinstance(info, dict):
                    info = {}

                new_bound[mac_norm] = info

            if new_bound != bound:
                voucher["devices"] = new_bound
                changed_db = True
                if removed:
                    add_action(f"清理兑换码 {code} 孤儿绑定 {removed} 个")
                if normalized:
                    add_action(f"规范化兑换码 {code} 绑定 MAC {normalized} 个")

        # 设备引用修复、过期在线修复、限速同步
        kicked_macs = []

        for mac, device in list(devices.items()):
            if not isinstance(device, dict):
                add_warning(f"设备 {mac} 不是 dict，已跳过。")
                continue

            mac_norm = normalize_mac(mac)
            if not mac_norm:
                add_warning(f"设备 MAC 异常：{mac}，已跳过。")
                continue

            code = normalize_code(device.get("voucher_code", ""))

            if code and code not in vouchers:
                device["voucher_code"] = ""
                device["online"] = False
                device["last_seen"] = now()
                changed_db = True
                kicked_macs.append(mac_norm)
                add_action(f"清理设备 {mac_norm} 指向不存在兑换码 {code}")

            if code and code in vouchers:
                voucher = vouchers.get(code, {})
                if isinstance(voucher, dict):
                    # 确保 voucher.devices 里有当前设备
                    if isinstance(voucher.get("devices"), dict) and mac_norm not in voucher["devices"]:
                        voucher["devices"][mac_norm] = {
                            "ip": device.get("ip", ""),
                            "hostname": device.get("hostname", ""),
                            "login_at": device.get("login_at", 0),
                            "last_seen": device.get("last_seen", 0),
                        }
                        changed_db = True
                        add_action(f"补齐兑换码 {code} 的设备绑定 {mac_norm}")

                    # 同步限速字段
                    for field in ["download_kbps", "upload_kbps", "speed_profile_name"]:
                        old_value = device.get(field)
                        new_value = voucher.get(field, old_value)
                        if old_value != new_value:
                            device[field] = new_value
                            changed_db = True
                            add_action(f"同步设备 {mac_norm} 字段 {field}")

            online = bool(device.get("online", False))
            expire_at = int(device.get("expire_at", 0) or 0)
            if online and expire_at > 0 and expire_at <= now():
                device["online"] = False
                device["last_seen"] = now()
                changed_db = True
                kicked_macs.append(mac_norm)
                add_action(f"修复过期仍在线设备 {mac_norm}")

        # 规范化 devices 顶层 MAC key
        normalized_devices = {}
        normalized_device_count = 0
        for mac, device in list(devices.items()):
            mac_norm = normalize_mac(mac)
            if mac_norm and mac_norm != mac:
                normalized_device_count += 1
                if mac_norm not in normalized_devices:
                    normalized_devices[mac_norm] = device
            else:
                normalized_devices[mac] = device

        if normalized_device_count:
            db["devices"] = normalized_devices
            devices = db["devices"]
            changed_db = True
            add_action(f"规范化 devices MAC key {normalized_device_count} 个")

        # 黑白名单 MAC 规范化
        for list_name in ["whitelist", "blacklist"]:
            source = db.get(list_name, {})
            if not isinstance(source, dict):
                db[list_name] = {}
                changed_db = True
                add_action(f"重置异常 {list_name}")
                continue

            normalized = {}
            changed_list = False
            for mac, value in source.items():
                mac_norm = normalize_mac(mac)
                if mac_norm:
                    normalized[mac_norm] = value
                    if mac_norm != mac:
                        changed_list = True
                else:
                    changed_list = True

            if changed_list:
                db[list_name] = normalized
                changed_db = True
                add_action(f"规范化 {list_name} MAC 格式")

        # 日志格式兼容化
        logs = db.get("logs", [])
        if isinstance(logs, list):
            new_logs = []
            log_fixed = 0
            for item in logs:
                if isinstance(item, dict):
                    fixed = dict(item)
                    if "time" not in fixed:
                        fixed["time"] = now()
                        log_fixed += 1
                    if "type" not in fixed:
                        fixed["type"] = "LOG"
                        log_fixed += 1
                    if "result" not in fixed:
                        fixed["result"] = "OK"
                        log_fixed += 1
                    if "message" not in fixed:
                        fixed["message"] = ""
                        log_fixed += 1
                    if "voucher_code" not in fixed:
                        fixed["voucher_code"] = ""
                    if "mac" not in fixed:
                        fixed["mac"] = ""
                    if "ip" not in fixed:
                        fixed["ip"] = ""
                    new_logs.append(fixed)
                else:
                    new_logs.append({
                        "time": now(),
                        "type": "RAW",
                        "result": "OK",
                        "message": str(item),
                        "voucher_code": "",
                        "mac": "",
                        "ip": "",
                    })
                    log_fixed += 1

            if log_fixed:
                db["logs"] = new_logs[-500:]
                changed_db = True
                add_action(f"兼容化日志格式 {log_fixed} 处")

        # 保存并处理踢下线/限速清理
        if changed_db:
            save_db(db)
            add_action("数据库已保存")
        else:
            add_action("未发现需要自动修复的数据问题")

        kicked_unique = sorted(set([m for m in kicked_macs if m]))
        for mac in kicked_unique:
            try:
                nft_kick_device(mac)
            except Exception:
                pass
            try:
                safe_qos_remove_device(mac)
            except Exception:
                pass

        if kicked_unique:
            add_action(f"已清理异常在线设备放行/限速 {len(kicked_unique)} 台")

        try:
            append_log("DB_FIX", f"数据库一键修复完成，动作 {len(actions)} 个，警告 {len(warnings)} 个")
        except Exception:
            pass

        try:
            append_admin_audit(self, "数据库一键修复", f"actions={len(actions)} warnings={len(warnings)} backup={backup_file}")
        except Exception:
            pass

        action_rows = []
        for item in actions:
            action_rows.append(f"<tr><td class='ok'>OK</td><td>{esc(item)}</td></tr>")

        warning_rows = []
        for item in warnings:
            warning_rows.append(f"<tr><td class='bad'>WARN</td><td>{esc(item)}</td></tr>")

        body = f"""
<div class="card">
<h1 class="ok">一键修复完成</h1>
<p>修复前备份：<code>{esc(str(backup_file))}</code></p>
<div class="grid">
<div class="stat">修复动作<b>{len(actions)}</b></div>
<div class="stat">警告数量<b>{len(warnings)}</b></div>
<div class="stat">清理设备<b>{len(set(kicked_macs))}</b></div>
</div>
<p>
<a class="btn" href="/admin/db-check">重新检查数据</a>
<a class="btn" href="/admin/backup">备份恢复</a>
<a class="btn" href="/admin/maintenance">系统维护</a>
</p>
</div>

<div class="card">
<h2>修复动作</h2>
<table class="dbfix-table">
<tr><th>状态</th><th>内容</th></tr>
{''.join(action_rows) if action_rows else '<tr><td colspan="2" class="muted">没有修复动作</td></tr>'}
</table>
</div>

<div class="card">
<h2>警告</h2>
<table class="dbfix-table">
<tr><th>级别</th><th>内容</th></tr>
{''.join(warning_rows) if warning_rows else '<tr><td colspan="2" class="muted">无警告</td></tr>'}
</table>
</div>
"""
        self.send_html(admin_page("一键修复完成", body))


    def show_admin_db_check(self):
        check_rows = []
        issue_rows = []
        ok_count = 0
        warn_count = 0
        bad_count = 0

        def badge(level):
            if level == "ok":
                return '<span class="dbcheck-badge dbcheck-ok">正常</span>'
            if level == "warn":
                return '<span class="dbcheck-badge dbcheck-warn">注意</span>'
            return '<span class="dbcheck-badge dbcheck-bad">异常</span>'

        def add_check(name, level, detail, suggestion="-"):
            nonlocal ok_count, warn_count, bad_count
            if level == "ok":
                ok_count += 1
            elif level == "warn":
                warn_count += 1
            else:
                bad_count += 1

            check_rows.append(f"""
<tr>
<td><b>{esc(name)}</b></td>
<td>{badge(level)}</td>
<td>{esc(detail)}</td>
<td>{esc(suggestion)}</td>
</tr>
""")

        def add_issue(level, category, detail, suggestion="-"):
            issue_rows.append(f"""
<tr>
<td>{badge(level)}</td>
<td><b>{esc(category)}</b></td>
<td>{esc(detail)}</td>
<td>{esc(suggestion)}</td>
</tr>
""")

        db = {}
        db_loaded = False
        db_error = ""

        try:
            db = load_db()
            db_loaded = isinstance(db, dict)
        except Exception as error:
            db_error = str(error)
            db_loaded = False
            db = {}

        if db_loaded:
            add_check("数据库读取", "ok", "数据库可以正常读取。")
        else:
            add_check("数据库读取", "bad", "数据库读取失败：" + db_error, "检查 /etc/wifiportal/vouchers.json 或从备份恢复。")
            body = f"""
<div class="card">
<h1>数据库一致性检查</h1>
<p class="muted">只读检查，不会修改任何数据。</p>
<div class="grid">
<div class="stat">总体状态<b class="bad">异常</b></div>
<div class="stat">正常项目<b>{ok_count}</b></div>
<div class="stat">注意项目<b>{warn_count}</b></div>
<div class="stat">异常项目<b>{bad_count}</b></div>
</div>
</div>
<div class="card">
<h2>检查结果</h2>
<table class="dbcheck-table">
<tr><th>项目</th><th>状态</th><th>详情</th><th>建议</th></tr>
{''.join(check_rows)}
</table>
</div>
"""
            self.send_html(admin_page("数据库一致性检查", body))
            return

        vouchers = db.get("vouchers", {})
        devices = db.get("devices", {})
        logs = db.get("logs", [])
        whitelist = db.get("whitelist", {})
        blacklist = db.get("blacklist", {})

        if isinstance(vouchers, dict):
            add_check("vouchers 格式", "ok", f"兑换码表正常，共 {len(vouchers)} 个。")
        else:
            add_check("vouchers 格式", "bad", "vouchers 不是 dict。", "需要从备份恢复或修复数据库。")
            vouchers = {}

        if isinstance(devices, dict):
            add_check("devices 格式", "ok", f"设备表正常，共 {len(devices)} 个。")
        else:
            add_check("devices 格式", "bad", "devices 不是 dict。", "需要从备份恢复或修复数据库。")
            devices = {}

        if isinstance(logs, list):
            add_check("logs 格式", "ok", f"日志表正常，共 {len(logs)} 条。")
        else:
            add_check("logs 格式", "warn", "logs 不是 list。", "日志格式异常，建议备份后清理日志。")
            logs = []

        if isinstance(whitelist, dict):
            add_check("whitelist 格式", "ok", f"白名单正常，共 {len(whitelist)} 个。")
        else:
            add_check("whitelist 格式", "warn", "whitelist 不是 dict。", "建议检查白名单数据。")
            whitelist = {}

        if isinstance(blacklist, dict):
            add_check("blacklist 格式", "ok", f"黑名单正常，共 {len(blacklist)} 个。")
        else:
            add_check("blacklist 格式", "warn", "blacklist 不是 dict。", "建议检查黑名单数据。")
            blacklist = {}

        issue_count = 0

        def issue(level, category, detail, suggestion="-"):
            nonlocal issue_count
            issue_count += 1
            add_issue(level, category, detail, suggestion)

        required_voucher_fields = ["minutes", "max_devices", "download_kbps", "upload_kbps", "devices", "enabled"]
        voucher_missing_count = 0
        voucher_devices_bad_count = 0

        for code, voucher in vouchers.items():
            if not isinstance(voucher, dict):
                issue("bad", "兑换码格式", f"{code} 的数据不是 dict。", "建议备份后修复该兑换码。")
                continue

            for field in required_voucher_fields:
                if field not in voucher:
                    voucher_missing_count += 1
                    issue("warn", "兑换码字段缺失", f"{code} 缺少字段 {field}。", "后续可用一键修复补齐默认字段。")

            if "devices" in voucher and not isinstance(voucher.get("devices", {}), dict):
                voucher_devices_bad_count += 1
                issue("bad", "兑换码 devices 异常", f"{code} 的 devices 不是 dict。", "需要修复 devices 字段。")

            try:
                max_devices = int(voucher.get("max_devices", 1) or 1)
                used_devices = len(voucher.get("devices", {}) or {})
                if used_devices > max_devices:
                    issue("warn", "设备数超过限制", f"{code} 已绑定 {used_devices} 台，限制 {max_devices} 台。", "可在详情页解绑多余设备。")
            except Exception:
                issue("warn", "设备数检查失败", f"{code} 的 max_devices 无法解析。", "建议编辑该兑换码。")

        if voucher_missing_count == 0 and voucher_devices_bad_count == 0:
            add_check("兑换码字段完整性", "ok", "兑换码基础字段未发现明显缺失。")
        else:
            add_check("兑换码字段完整性", "warn", f"字段缺失 {voucher_missing_count} 处，devices 异常 {voucher_devices_bad_count} 处。", "建议备份后修复。")

        # voucher.devices -> devices 一致性
        missing_device_ref = 0
        mismatch_device_code = 0

        for code, voucher in vouchers.items():
            if not isinstance(voucher, dict):
                continue
            bound_devices = voucher.get("devices", {}) or {}
            if not isinstance(bound_devices, dict):
                continue

            for mac in bound_devices.keys():
                mac_norm = normalize_mac(mac)
                device = devices.get(mac_norm) or devices.get(mac)
                if not device:
                    missing_device_ref += 1
                    issue("warn", "兑换码绑定设备缺失", f"兑换码 {code} 绑定了 {mac}，但 devices 表没有这个设备。", "可在后续一键修复中清理孤儿绑定。")
                    continue

                device_code = normalize_code(device.get("voucher_code", ""))
                if device_code and device_code != normalize_code(code):
                    mismatch_device_code += 1
                    issue("warn", "绑定关系不一致", f"兑换码 {code} 绑定 {mac}，但设备表 voucher_code={device_code}。", "建议检查该设备当前使用的兑换码。")

        if missing_device_ref == 0 and mismatch_device_code == 0:
            add_check("兑换码到设备绑定", "ok", "voucher.devices 与 devices 表未发现明显冲突。")
        else:
            add_check("兑换码到设备绑定", "warn", f"缺失设备 {missing_device_ref} 个，绑定冲突 {mismatch_device_code} 个。", "建议备份后修复绑定关系。")

        # devices -> vouchers 一致性
        missing_voucher_ref = 0
        online_expired_count = 0
        speed_mismatch_count = 0

        for mac, device in devices.items():
            if not isinstance(device, dict):
                issue("bad", "设备格式", f"{mac} 的设备数据不是 dict。", "建议备份后修复该设备。")
                continue

            code = normalize_code(device.get("voucher_code", ""))
            if code:
                voucher = vouchers.get(code)
                if not voucher:
                    missing_voucher_ref += 1
                    issue("warn", "设备引用不存在兑换码", f"设备 {mac} 指向兑换码 {code}，但该兑换码不存在。", "可解绑设备或恢复兑换码。")
                else:
                    try:
                        if int(device.get("download_kbps", 0) or 0) != int(voucher.get("download_kbps", 0) or 0):
                            speed_mismatch_count += 1
                            issue("warn", "下载限速不一致", f"设备 {mac} 与兑换码 {code} 下载限速不同。", "可在维护页重建在线设备限速。")
                        if int(device.get("upload_kbps", 0) or 0) != int(voucher.get("upload_kbps", 0) or 0):
                            speed_mismatch_count += 1
                            issue("warn", "上传限速不一致", f"设备 {mac} 与兑换码 {code} 上传限速不同。", "可在维护页重建在线设备限速。")
                    except Exception:
                        issue("warn", "限速检查失败", f"设备 {mac} 或兑换码 {code} 限速字段无法解析。", "建议编辑兑换码。")

            online = bool(device.get("online", False))
            expire_at = int(device.get("expire_at", 0) or 0)
            if online and expire_at > 0 and expire_at <= now():
                online_expired_count += 1
                issue("warn", "过期设备仍标记在线", f"设备 {mac} 已过期但 online=True。", "可运行健康维护或等待清理任务。")

        if missing_voucher_ref == 0 and online_expired_count == 0 and speed_mismatch_count == 0:
            add_check("设备到兑换码绑定", "ok", "devices 表未发现明显引用异常。")
        else:
            add_check("设备到兑换码绑定", "warn", f"不存在兑换码引用 {missing_voucher_ref} 个，过期仍在线 {online_expired_count} 个，限速不一致 {speed_mismatch_count} 处。", "建议备份后修复或重建限速。")

        # 黑白名单 MAC 格式
        bad_white_mac = 0
        bad_black_mac = 0

        for mac in whitelist.keys():
            if normalize_mac(mac) != mac.lower():
                bad_white_mac += 1
                issue("warn", "白名单 MAC 格式", f"白名单 MAC 格式可能异常：{mac}", "建议统一为 aa:bb:cc:dd:ee:ff 格式。")

        for mac in blacklist.keys():
            if normalize_mac(mac) != mac.lower():
                bad_black_mac += 1
                issue("warn", "黑名单 MAC 格式", f"黑名单 MAC 格式可能异常：{mac}", "建议统一为 aa:bb:cc:dd:ee:ff 格式。")

        if bad_white_mac == 0 and bad_black_mac == 0:
            add_check("黑白名单 MAC 格式", "ok", "黑白名单 MAC 格式未发现明显异常。")
        else:
            add_check("黑白名单 MAC 格式", "warn", f"白名单异常 {bad_white_mac} 个，黑名单异常 {bad_black_mac} 个。", "建议备份后统一格式。")

        # 日志格式检查
        bad_log_count = 0
        missing_log_field_count = 0
        for index, item in enumerate(logs[-500:]):
            if not isinstance(item, dict):
                bad_log_count += 1
                if bad_log_count <= 5:
                    issue("warn", "日志格式", f"第 {index} 条日志不是 dict。", "日志页已兼容显示，但建议后续清理。")
                continue
            for field in ["time", "type", "result", "message"]:
                if field not in item:
                    missing_log_field_count += 1
                    if missing_log_field_count <= 5:
                        issue("warn", "日志字段缺失", f"日志缺少字段 {field}：{str(item)[:120]}", "日志页已兼容显示。")

        if bad_log_count == 0 and missing_log_field_count == 0:
            add_check("日志结构", "ok", "最近日志结构正常。")
        else:
            add_check("日志结构", "warn", f"非标准日志 {bad_log_count} 条，缺失字段 {missing_log_field_count} 处。", "不影响认证，可后续做日志清理。")


        # DB_CHECK_VOUCHER_DISPLAY_V1
        try:
            voucher_count_for_display = len(vouchers) if isinstance(vouchers, dict) else 0
            if voucher_count_for_display > 0:
                add_check(
                    "兑换码页面显示检查",
                    "ok",
                    f"数据库存在 {voucher_count_for_display} 个兑换码。请同时打开 /admin/vouchers 确认页面显示正常。",
                    "如果页面不显示，使用兑换码管理页的兜底列表或清空筛选。"
                )
            else:
                add_check(
                    "兑换码页面显示检查",
                    "warn",
                    "数据库中当前没有兑换码。",
                    "如果你认为应该有兑换码，请检查是否恢复了错误备份。"
                )
        except Exception as error:
            add_check("兑换码页面显示检查", "warn", "检查失败：" + str(error), "打开 /admin/vouchers 手动确认。")

        # 文件大小和备份建议
        try:
            db_size = get_file_size(DB_FILE)
            if db_size > 1024 * 1024 * 2:
                add_check("数据库大小", "warn", f"数据库大小 {db_size} bytes。", "较大时建议清理旧日志并创建备份。")
            else:
                add_check("数据库大小", "ok", f"数据库大小 {db_size} bytes。")
        except Exception as error:
            add_check("数据库大小", "warn", "读取数据库大小失败：" + str(error), "检查数据库文件。")

        if issue_count == 0:
            total_state = "正常"
            total_class = "ok"
            issue_table = '<tr><td colspan="4" class="muted">未发现需要处理的数据一致性问题。</td></tr>'
        else:
            total_state = "注意" if bad_count == 0 else "异常"
            total_class = "bad" if bad_count > 0 else ""
            issue_table = ''.join(issue_rows)

        body = f"""
<div class="card">
<h1>数据库一致性检查</h1>
<p class="muted">只读检查，不会修改数据库、不踢设备、不清理限速。发现问题后，建议先备份，再考虑修复。</p>
<div class="grid">
<div class="stat">总体状态<b class="{total_class}">{total_state}</b></div>
<div class="stat">正常项目<b>{ok_count}</b></div>
<div class="stat">注意项目<b>{warn_count}</b></div>
<div class="stat">异常项目<b>{bad_count}</b></div>
<div class="stat">问题数量<b>{issue_count}</b></div>
<div class="stat">检查时间<b>{esc(format_time(now()))}</b></div>
</div>
<p>
<a class="btn" href="/admin/db-check">重新检查</a>
<a class="btn" href="/admin/backup">先去备份</a>
<a class="btn" href="/admin/db-fix">一键修复</a>
<a class="btn" href="/admin/maintenance">系统维护</a>
</p>
</div>

<div class="card">
<h2>检查项目</h2>
<table class="dbcheck-table">
<tr><th>项目</th><th>状态</th><th>详情</th><th>建议</th></tr>
{''.join(check_rows)}
</table>
</div>

<div class="card">
<h2>问题详情</h2>
<table class="dbcheck-table">
<tr><th>级别</th><th>分类</th><th>详情</th><th>建议</th></tr>
{issue_table}
</table>
</div>

<div class="card">
<h2>说明</h2>
<p>这个页面是只读检查，不会自动修复。</p>
<p>如果只有黄色“注意”，通常不影响当前认证；如果有红色“异常”，建议先创建备份，再处理。</p>
<p>下一步可以做“一键修复页面”，但必须先确认这里列出来的问题类型。</p>
</div>
"""
        self.send_html(admin_page("数据库一致性检查", body))



    def show_admin_help(self):
        body = f"""
<div class="card">
<h1>后台帮助 / 运维手册</h1>
<p class="muted">这是本地 WiFi Portal 收费系统的维护说明。此页面只读，不会修改任何配置。</p>
<div class="grid">
<div class="stat">后台地址<b>http://{esc(LAN_IP)}/admin</b></div>
<div class="stat">客户认证页<b>http://{esc(LAN_IP)}</b></div>
<div class="stat">客户自查页<b>http://{esc(LAN_IP)}/check</b></div>
<div class="stat">LuCI 地址<b>http://{esc(LAN_IP)}:8080</b></div>
</div>
</div>

<div class="card">
<h2>后台常用入口</h2>
<div class="help-link-grid">
<a href="/admin">系统总览</a>
<a href="/admin/vouchers">兑换码管理</a>
<a href="/admin/devices">设备管理</a>
<a href="/admin/expiring">到期管理</a>
<a href="/admin/logs">系统日志</a>
<a href="/admin/health">一键健康检查</a>
<a href="/admin/maintenance">一键系统维护</a>
<a href="/admin/backup">备份恢复</a>
<a href="/admin/db-check">数据检查</a>
<a href="/admin/db-fix">数据修复</a>
<a href="/admin/qos">限速模块</a>
<a href="/admin/firewall">防火墙拦截</a>
</div>
</div>

<div class="card">
<h2>常用 SSH 命令</h2>
<p class="muted">这些命令只用于维护。复制前请确认自己正在 SSH 路由器。</p>
<pre class="help-code"># 查看认证服务进程
ps | grep wifiportal | grep -v grep

# 查看 80 端口是否监听
netstat -lntp 2&gt;/dev/null | grep ':80 '

# 重启认证服务
/etc/init.d/wifiportal restart

# 查看程序语法
python3 -m py_compile /usr/lib/wifiportal/wifiportal.py &amp;&amp; echo "syntax ok"

# 手动创建自动备份
/usr/bin/wifiportal_auto_backup.sh

# 查看自动备份日志
cat /tmp/wifiportal_auto_backup.log

# 查看最近备份文件
ls -lh /etc/wifiportal/backup | tail

# 查看系统日志
logread 2&gt;/dev/null | tail -n 80</pre>
</div>

<div class="card">
<h2>推荐故障排查顺序</h2>
<div class="help-steps">
<p><b>第 1 步：</b>打开 <a href="/admin/health">一键健康检查</a>，先看红色异常。</p>
<p><b>第 2 步：</b>打开 <a href="/admin/logs?date=today&result=FAIL">今日失败日志</a>，看失败原因。</p>
<p><b>第 3 步：</b>打开 <a href="/admin/maintenance">一键系统维护</a>，先创建备份。</p>
<p><b>第 4 步：</b>如果改过限速，点击“重建在线设备限速”。</p>
<p><b>第 5 步：</b>如果认证放行异常，点击“恢复已认证会话”。</p>
<p><b>第 6 步：</b>最后才重启认证服务。</p>
</div>
</div>

<div class="card">
<h2>哪些操作会影响用户上网</h2>
<table class="help-table">
<tr><th>操作</th><th>影响</th><th>建议</th></tr>
<tr><td>查看页面 / 筛选日志 / 数据检查</td><td>不影响</td><td>可以随时操作</td></tr>
<tr><td>创建备份</td><td>通常不影响</td><td>推荐先备份再维护</td></tr>
<tr><td>重建在线设备限速</td><td>可能有短暂速度波动</td><td>用户少时执行</td></tr>
<tr><td>恢复已认证会话</td><td>通常不影响，可能短暂规则波动</td><td>认证异常时执行</td></tr>
<tr><td>重启认证服务</td><td>后台/认证页短暂不可用，已认证设备通常不断网</td><td>最后手段</td></tr>
<tr><td>禁用/删除兑换码</td><td>对应设备会被踢下线</td><td>确认后再操作</td></tr>
<tr><td>恢复备份</td><td>会覆盖当前数据</td><td>必须确认备份时间</td></tr>
</table>
</div>

<div class="card">
<h2>备份和恢复</h2>
<p>备份页面：<a class="btn" href="/admin/backup">打开备份恢复</a></p>
<p>自动备份默认每天凌晨 <b>03:07</b> 执行，保留最近 7 个备份。</p>
<p>恢复备份会覆盖当前兑换码、设备、日志、黑白名单、安全记录和页面设置。</p>
<p class="muted">如果刚做过一键修复，系统会自动创建修复前备份；恢复时请选择修复前的那个备份文件。</p>
</div>

<div class="card">
<h2>当前系统功能清单</h2>
<table class="help-table">
<tr><th>功能</th><th>说明</th></tr>
<tr><td>本地兑换码认证</td><td>客户连接 WiFi 后输入兑换码上网。</td></tr>
<tr><td>兑换码管理</td><td>新增、批量生成、编辑、禁用、删除、重置、延长。</td></tr>
<tr><td>设备绑定详情</td><td>查看兑换码绑定设备，并可单独解绑。</td></tr>
<tr><td>限时和限速</td><td>支持时长、最大设备数、下载/上传限速。</td></tr>
<tr><td>客户自查页</td><td>客户可查看套餐、剩余时间、设备状态。</td></tr>
<tr><td>运营日志筛选</td><td>按类型、结果、时间、兑换码、MAC、IP、关键词筛选。</td></tr>
<tr><td>健康检查</td><td>检查服务、端口、数据库、防火墙、限速、备份、日志异常。</td></tr>
<tr><td>自动备份</td><td>每天自动备份并保留最近 7 个。</td></tr>
<tr><td>数据检查 / 修复</td><td>检查并修复低风险数据库一致性问题。</td></tr>
<tr><td>手机端后台</td><td>底部快捷导航、移动端表格优化、维护入口。</td></tr>
</table>
</div>

<div class="card">
<h2>重要提醒</h2>
<p>1. 大改功能前先创建备份。</p>
<p>2. 不要手动运行 <code>/usr/bin/python3 /usr/lib/wifiportal/wifiportal.py</code>，因为服务模式已经占用 80 端口。</p>
<p>3. 如果看到 <code>Address in use</code>，通常表示服务已经在运行，不一定是坏了。</p>
<p>4. 如果后台打不开，先 SSH 执行 <code>ps | grep wifiportal | grep -v grep</code> 和 <code>netstat -lntp | grep ':80 '</code>。</p>
<p>5. 遇到无法判断的问题，先不要继续打补丁，先备份并检查日志。</p>
</div>
"""
        self.send_html(admin_page("后台帮助 / 运维手册", body))


    def show_admin_maintenance(self):
        db = load_db()
        vouchers = db.get("vouchers", {})
        devices = db.get("devices", {})
        logs = db.get("logs", [])

        try:
            online_devices = _wp_collect_current_wifi_clients_12h()
        except Exception:
            online_devices = {}

        today_fail = 0
        try:
            local_now = time.localtime(now())
            today_start = int(time.mktime((local_now.tm_year, local_now.tm_mon, local_now.tm_mday, 0, 0, 0, 0, 0, -1)))
            for item in logs:
                if not isinstance(item, dict):
                    continue
                if int(item.get("time", 0) or 0) >= today_start and str(item.get("result", "") or "OK").upper() == "FAIL":
                    today_fail += 1
        except Exception:
            today_fail = 0

        try:
            auto_backup = get_auto_backup_status()
            auto_backup_text = auto_backup.get("summary", "未知")
            auto_backup_class = "ok" if auto_backup.get("ok") else "bad"
        except Exception:
            auto_backup_text = "读取失败"
            auto_backup_class = "bad"

        body = f"""
<div class="card">
<h1>一键系统维护</h1>
<p class="muted">这里集中放置常用维护操作。危险操作都有确认提示，建议先创建备份再执行维护。</p>
<div class="grid">
<div class="stat">认证服务<b class="ok">运行中</b></div>
<div class="stat">兑换码总数<b>{len(vouchers)}</b></div>
<div class="stat">历史设备<b>{len(devices)}</b></div>
<div class="stat">实时在线<b>{len(online_devices)}</b></div>
<div class="stat">今日失败日志<b>{today_fail}</b></div>
<div class="stat">自动备份<b class="{auto_backup_class}">{esc(auto_backup_text)}</b></div>
</div>
</div>

<div class="card">
<h2>常用检查</h2>
<div class="maintenance-grid">
<a class="maintenance-action" href="/admin/health">
  <b>一键健康检查</b>
  <span>检查服务、端口、防火墙、限速、备份、日志。</span>
</a>

<a class="maintenance-action" href="/admin/help">
  <b>运维手册</b>
  <span>查看后台地址、常用命令、恢复步骤和影响说明。</span>
</a>

<a class="maintenance-action" href="/admin/logs?date=today&result=FAIL">
  <b>今日失败日志</b>
  <span>快速查看今天所有失败记录。</span>
</a>

<a class="maintenance-action" href="/admin/backup">
  <b>备份恢复</b>
  <span>查看手动备份、自动备份状态、恢复备份。</span>
</a>

<a class="maintenance-action" href="/admin/db-check">
  <b>数据库一致性检查</b>
  <span>只读检查兑换码、设备、日志、黑白名单是否存在异常。</span>
</a>

<a class="maintenance-action" href="/admin/db-fix">
  <b>数据库一键修复</b>
  <span>先自动备份，再修复低风险数据一致性问题。</span>
</a>

<a class="maintenance-action" href="/admin/expiring">
  <b>即将到期</b>
  <span>查看 1 小时内、今天、3 天内到期兑换码。</span>
</a>
</div>
</div>

<div class="card">
<h2>安全维护操作</h2>
<div class="maintenance-grid">
<form method="post" action="/admin/backup-create" class="maintenance-form">
  <button type="submit" class="maintenance-action-button">
    <b>立即创建备份</b>
    <span>保存当前兑换码、设备、日志、设置。</span>
  </button>
</form>

<form method="post" action="/admin/qos-restore" class="maintenance-form" onsubmit="return confirm('确认重建在线设备限速？不会删除兑换码。')">
  <button type="submit" class="maintenance-action-button">
    <b>重建在线设备限速</b>
    <span>修改过套餐速度后，用这个让在线设备应用新速度。</span>
  </button>
</form>

<form method="post" action="/admin/firewall-restore-sessions" class="maintenance-form" onsubmit="return confirm('确认恢复已认证会话？')">
  <button type="submit" class="maintenance-action-button">
    <b>恢复已认证会话</b>
    <span>防火墙重启或规则异常时，恢复当前有效设备放行。</span>
  </button>
</form>

<form method="post" action="/admin/maintenance-restart" class="maintenance-form" onsubmit="return confirm('确认重启认证服务？手机后台会短暂断开几秒。')">
  <button type="submit" class="maintenance-action-button danger">
    <b>重启认证服务</b>
    <span>仅重启 wifiportal Web 服务，不重启路由器。</span>
  </button>
</form>
</div>
</div>

<div class="card">
<h2>建议维护顺序</h2>
<p>1. 先点击 <b>立即创建备份</b>。</p>
<p>2. 再点击 <b>一键健康检查</b>。</p>
<p>3. 如果改过速度套餐，点击 <b>重建在线设备限速</b>。</p>
<p>4. 如果认证放行异常，点击 <b>恢复已认证会话</b>。</p>
<p>5. 最后才使用 <b>重启认证服务</b>。</p>
</div>
"""
        self.send_html(admin_page("一键系统维护", body))

    def admin_maintenance_restart(self):
        append_admin_audit(self, "重启认证服务", "from=/admin/maintenance")
        self.send_html(admin_page("正在重启", """
<div class="card">
<h1 class="ok">认证服务正在重启</h1>
<p>页面可能会短暂断开，请 5-10 秒后重新打开后台。</p>
<p><a class="btn" href="/admin">返回首页</a></p>
<script>
setTimeout(function(){ location.href='/admin'; }, 7000);
</script>
</div>
"""))
        try:
            os.system("(sleep 1; /etc/init.d/wifiportal restart) >/tmp/wifiportal_maintenance_restart.log 2>&1 &")
        except Exception:
            pass


    def show_admin_health(self):
        db_ok = True
        db_error = ""
        try:
            db = load_db()
        except Exception as error:
            db_ok = False
            db_error = str(error)
            db = {}

        vouchers = db.get("vouchers", {}) if isinstance(db, dict) else {}
        devices = db.get("devices", {}) if isinstance(db, dict) else {}
        logs = db.get("logs", []) if isinstance(db, dict) else []

        try:
            local_now = time.localtime(now())
            today_start = int(time.mktime((local_now.tm_year, local_now.tm_mon, local_now.tm_mday, 0, 0, 0, 0, 0, -1)))
        except Exception:
            today_start = now() - 86400

        def status_badge(ok, warn=False):
            if ok and not warn:
                return '<span class="health-badge health-ok">正常</span>'
            if warn:
                return '<span class="health-badge health-warn">注意</span>'
            return '<span class="health-badge health-bad">异常</span>'

        def add_row(rows, name, ok, detail, suggestion="", warn=False):
            rows.append(f"""
<tr>
<td><b>{esc(name)}</b></td>
<td>{status_badge(ok, warn)}</td>
<td>{esc(detail)}</td>
<td>{esc(suggestion or "-")}</td>
</tr>
""")

        rows = []
        ok_count = 0
        warn_count = 0
        bad_count = 0

        def record(name, ok, detail, suggestion="", warn=False):
            nonlocal ok_count, warn_count, bad_count
            if ok and not warn:
                ok_count += 1
            elif warn:
                warn_count += 1
            else:
                bad_count += 1
            add_row(rows, name, ok, detail, suggestion, warn)

        # 服务本身能打开此页面，说明 Python Web 主程序正在运行。
        record("认证 Web 服务", True, "当前后台页面可访问，Python 主程序正在响应。")

        # 进程检查
        try:
            proc_text = os.popen("ps | grep wifiportal | grep -v grep 2>/dev/null").read().strip()
            proc_ok = bool(proc_text)
            record("wifiportal 进程", proc_ok, proc_text[:180] if proc_text else "未发现 wifiportal 进程", "执行 /etc/init.d/wifiportal restart" if not proc_ok else "")
        except Exception as error:
            record("wifiportal 进程", False, str(error), "SSH 检查 ps | grep wifiportal")

        # 80 端口监听
        try:
            net_text = os.popen("netstat -lntp 2>/dev/null | grep ':80 '").read().strip()
            port_ok = bool(net_text)
            record("80 端口监听", port_ok, net_text[:180] if net_text else "未发现 80 端口监听", "执行 /etc/init.d/wifiportal restart" if not port_ok else "")
        except Exception as error:
            record("80 端口监听", False, str(error), "SSH 检查 netstat -lntp")

        # LuCI 8080
        try:
            luci_text = os.popen("netstat -lntp 2>/dev/null | grep ':8080 '").read().strip()
            luci_ok = bool(luci_text)
            record("LuCI 8080", luci_ok, luci_text[:180] if luci_text else "未发现 8080 端口监听", "检查 uhttpd 服务" if not luci_ok else "", warn=not luci_ok)
        except Exception as error:
            record("LuCI 8080", False, str(error), "SSH 检查 uhttpd", warn=True)

        # 数据库
        record("数据库读取", db_ok, "数据库读取正常" if db_ok else db_error, "检查 /etc/wifiportal/vouchers.json" if not db_ok else "")

        try:
            db_size = get_file_size(DB_FILE)
            db_exists = os.path.exists(DB_FILE)
            record("数据库文件", db_exists, f"{DB_FILE} / {db_size} bytes" if db_exists else f"{DB_FILE} 不存在", "检查数据库文件是否丢失" if not db_exists else "")
        except Exception as error:
            record("数据库文件", False, str(error), "检查数据库路径")

        # 兑换码状态
        unused = active = expired = disabled = 0
        for voucher in vouchers.values():
            status = voucher_status(voucher)
            if status == "已禁用":
                disabled += 1
            elif status == "已过期":
                expired += 1
            elif "未使用" in status:
                unused += 1
            else:
                active += 1

        record("兑换码数据", True, f"总数 {len(vouchers)}，未使用 {unused}，使用中 {active}，已过期 {expired}，已禁用 {disabled}")

        # 设备数据
        try:
            realtime_clients = _wp_collect_current_wifi_clients_12h()
        except Exception:
            realtime_clients = {}
        record("设备数据", True, f"历史设备 {len(devices)}，实时 WiFi 在线 {len(realtime_clients)}")

        # 防火墙
        try:
            fw_text = firewall_status_text()
            fw_ok = "已启用" in fw_text or "启用" in fw_text or "运行" in fw_text
            record("防火墙拦截", fw_ok, fw_text, "如需要认证拦截，请到防火墙页面启用" if not fw_ok else "", warn=not fw_ok)
        except Exception as error:
            record("防火墙拦截", False, str(error), "检查防火墙模块", warn=True)

        # 限速模块
        try:
            qos_text = qos_status_text()
            qos_switch = qos_enabled()
            qos_ok = bool(qos_switch)
            record("限速模块", qos_ok, f"开关：{'已启用' if qos_switch else '未启用'}；状态：{qos_text}", "如需要限速，请到限速模块初始化/启用" if not qos_ok else "", warn=not qos_ok)
        except Exception as error:
            record("限速模块", False, str(error), "检查限速模块", warn=True)

        # 自动启动
        try:
            rc_files = []
            if os.path.isdir("/etc/rc.d"):
                for name in os.listdir("/etc/rc.d"):
                    if "wifiportal" in name:
                        rc_files.append(name)
            auto_ok = bool(rc_files)
            record("开机自启", auto_ok, ", ".join(rc_files) if rc_files else "未发现 /etc/rc.d/*wifiportal*", "执行 /etc/init.d/wifiportal enable" if not auto_ok else "", warn=not auto_ok)
        except Exception as error:
            record("开机自启", False, str(error), "检查 /etc/rc.d", warn=True)

        # 最近备份
        try:
            last_backup = get_last_backup_time()
            if last_backup > 0:
                age_hours = max(0, (now() - int(last_backup)) // 3600)
                backup_warn = age_hours > 72
                record("最近备份", not backup_warn, f"{format_time(last_backup)}，约 {age_hours} 小时前", "建议创建新备份" if backup_warn else "", warn=backup_warn)
            else:
                record("最近备份", False, "暂无备份", "建议立即创建备份", warn=True)
        except Exception as error:
            record("最近备份", False, str(error), "检查备份页面", warn=True)

        # 日志异常 + 失败原因统计
        today_logs = 0
        today_fail = 0
        fail_reason_count = {}
        fail_type_count = {}
        recent_fail_messages = []

        for item in logs:
            log_time = int(item.get("time", 0) or 0)
            if log_time < today_start:
                continue

            today_logs += 1

            if str(item.get("result", "") or "OK").upper() != "FAIL":
                continue

            today_fail += 1

            fail_type = str(item.get("type", "") or "UNKNOWN").upper()
            fail_type_count[fail_type] = fail_type_count.get(fail_type, 0) + 1

            message = str(item.get("message", "") or "未知失败").strip()
            if not message:
                message = "未知失败"

            # 去掉太细碎的动态内容，避免同类错误被拆散。
            reason = message
            if "兑换码格式错误" in reason:
                reason = "兑换码格式错误"
            elif "后台登录失败" in reason:
                reason = "后台登录失败"
            elif "兑换码不存在" in reason:
                reason = "兑换码不存在"
            elif "兑换码已过期" in reason:
                reason = "兑换码已过期"
            elif "兑换码已禁用" in reason:
                reason = "兑换码已禁用"
            elif "设备数" in reason or "设备数量" in reason or "设备已满" in reason:
                reason = "设备数已满"
            elif "安全锁定" in reason or "锁定" in reason:
                reason = "安全锁定"
            elif "黑名单" in reason:
                reason = "黑名单拦截"
            elif len(reason) > 32:
                reason = reason[:32] + "..."

            fail_reason_count[reason] = fail_reason_count.get(reason, 0) + 1

            if len(recent_fail_messages) < 5:
                fail_mac = str(item.get("mac", "") or "")
                fail_code = str(item.get("voucher_code", "") or "")
                short_message = reason
                if fail_code:
                    short_message += f" / 码:{fail_code}"
                if fail_mac:
                    short_message += f" / MAC:{fail_mac}"
                recent_fail_messages.append(short_message)

        fail_rate = 0
        if today_logs > 0:
            fail_rate = round(today_fail * 100 / today_logs, 1)

        reason_top = sorted(fail_reason_count.items(), key=lambda x: x[1], reverse=True)[:8]
        type_top = sorted(fail_type_count.items(), key=lambda x: x[1], reverse=True)[:5]

        reason_text = "；".join([f"{name} {count}次" for name, count in reason_top]) if reason_top else "无"
        type_text = "；".join([f"{name} {count}次" for name, count in type_top]) if type_top else "无"
        recent_text = " | ".join(recent_fail_messages) if recent_fail_messages else "无"

        log_warn = today_fail >= 30 or fail_rate >= 15
        log_bad = today_fail >= 100 or fail_rate >= 35

        fail_detail = (
            f"今日日志 {today_logs} 条，失败 {today_fail} 条，失败率 {fail_rate}%"
            f"；原因排行：{reason_text}"
            f"；类型排行：{type_text}"
            f"；最近失败：{recent_text}"
        )

        if log_bad:
            record("今日失败日志", False, fail_detail, "失败明显偏高，建议立即打开日志筛选查看")
        else:
            record("今日失败日志", not log_warn, fail_detail, "失败偏多，建议打开日志筛选查看" if log_warn else "", warn=log_warn)

        # 磁盘空间
        try:
            statvfs = os.statvfs("/")
            total = statvfs.f_frsize * statvfs.f_blocks
            free = statvfs.f_frsize * statvfs.f_bavail
            free_mb = free // 1024 // 1024
            total_mb = total // 1024 // 1024
            disk_warn = free_mb < 10
            record("磁盘空间", not disk_warn, f"剩余 {free_mb} MB / 总计 {total_mb} MB", "空间不足，建议清理旧备份/日志" if disk_warn else "", warn=disk_warn)
        except Exception as error:
            record("磁盘空间", False, str(error), "SSH 检查 df -h", warn=True)

        # 配置地址
        lan_ok = bool(LAN_IP)
        record("LAN 地址配置", lan_ok, f"LAN IP: {LAN_IP}；客户页 http://{LAN_IP}；后台 http://{LAN_IP}/admin", "检查 LAN_IP 配置" if not lan_ok else "")

        health_title = "正常" if bad_count == 0 and warn_count == 0 else ("注意" if bad_count == 0 else "异常")
        health_class = "ok" if health_title == "正常" else ("bad" if health_title == "异常" else "")

        body = f"""
<div class="card">
<h1>一键健康检查</h1>
<p class="muted">只读检查，不会修改兑换码、设备、防火墙或限速规则。</p>
<div class="grid">
<div class="stat">总体状态<b class="{health_class}">{health_title}</b></div>
<div class="stat">正常项目<b>{ok_count}</b></div>
<div class="stat">注意项目<b>{warn_count}</b></div>
<div class="stat">异常项目<b>{bad_count}</b></div>
<div class="stat">检查时间<b>{esc(format_time(now()))}</b></div>
</div>
<p>
<a class="btn" href="/admin/health">重新检查</a>
<a class="btn" href="/admin/logs?date=today&result=FAIL">查看今日失败日志</a>
<a class="btn" href="/admin/backup">备份恢复</a>
<a class="btn" href="/admin/maintenance">系统维护</a>
<a class="btn" href="/admin/expiring">查看即将到期</a>
</p>
</div>

<div class="card">
<h2>检查结果</h2>
<table class="health-check-table">
<tr><th>项目</th><th>状态</th><th>详情</th><th>建议</th></tr>
{''.join(rows)}
</table>
</div>
"""
        self.send_html(admin_page("一键健康检查", body))


    def show_admin_dashboard(self):
        db = load_db()
        vouchers = db.get("vouchers", {})
        devices = db.get("devices", {})
        logs = db.get("logs", [])

        # 实时在线设备数量：只按 iw station dump 当前 WiFi 连接判断。
        # db["devices"][mac]["online"] 只代表认证仍有效，不代表设备当前在线。
        try:
            online_devices = _wp_collect_current_wifi_clients_12h()
        except Exception:
            online_devices = {}

        service_status = "运行中"
        firewall_status = firewall_status_text()
        database_size = get_file_size(DB_FILE)
        last_backup = get_last_backup_time()

        # DASHBOARD_ALERTS_V1
        dashboard_alert_rows = []

        def add_dashboard_alert(level, title, detail, link="", link_text="查看"):
            if link:
                action_html = f'<a class="btn dashboard-alert-btn" href="{esc(link)}">{esc(link_text)}</a>'
            else:
                action_html = '<span class="muted">-</span>'

            dashboard_alert_rows.append(f"""
<div class="dashboard-alert-item dashboard-alert-{esc(level)}">
  <div>
    <b>{esc(title)}</b>
    <p>{esc(detail)}</p>
  </div>
  <div>{action_html}</div>
</div>
""")

        try:
            logs_for_alert = db.get("logs", [])
            local_now_alert = time.localtime(now())
            today_start_alert = int(time.mktime((local_now_alert.tm_year, local_now_alert.tm_mon, local_now_alert.tm_mday, 0, 0, 0, 0, 0, -1)))

            today_logs_alert = 0
            today_fail_alert = 0
            for item in logs_for_alert:
                if not isinstance(item, dict):
                    continue
                log_time = int(item.get("time", 0) or 0)
                if log_time < today_start_alert:
                    continue
                today_logs_alert += 1
                if str(item.get("result", "") or "OK").upper() == "FAIL":
                    today_fail_alert += 1

            fail_rate_alert = 0
            if today_logs_alert > 0:
                fail_rate_alert = round(today_fail_alert * 100 / today_logs_alert, 1)

            if today_fail_alert >= 100 or fail_rate_alert >= 35:
                add_dashboard_alert("bad", "今日失败日志异常", f"今日失败 {today_fail_alert} 条，失败率 {fail_rate_alert}%。", "/admin/logs?date=today&result=FAIL", "查看失败")
            elif today_fail_alert >= 30 or fail_rate_alert >= 15:
                add_dashboard_alert("warn", "今日失败日志偏多", f"今日失败 {today_fail_alert} 条，失败率 {fail_rate_alert}%。", "/admin/logs?date=today&result=FAIL", "查看失败")
        except Exception:
            pass

        try:
            expiring_soon_alert = 0
            expired_alert = 0
            current_time_alert = now()

            for voucher in vouchers.values():
                if not voucher.get("enabled", True):
                    continue
                if int(voucher.get("minutes", 0) or 0) == 0:
                    continue
                if int(voucher.get("first_used_at", 0) or 0) <= 0:
                    continue

                expire_at_alert = int(voucher.get("expire_at", 0) or 0)
                if expire_at_alert <= 0:
                    continue

                if expire_at_alert <= current_time_alert:
                    expired_alert += 1
                elif expire_at_alert <= current_time_alert + 86400:
                    expiring_soon_alert += 1

            if expiring_soon_alert > 0:
                add_dashboard_alert("warn", "有兑换码 24 小时内到期", f"{expiring_soon_alert} 个兑换码将在 24 小时内到期。", "/admin/expiring", "查看到期")
            if expired_alert > 0:
                add_dashboard_alert("warn", "存在已过期兑换码", f"{expired_alert} 个兑换码已过期。", "/admin/vouchers?status=expired", "查看过期")
        except Exception:
            pass

        try:
            fw_text_alert = firewall_status_text()
            if not ("已启用" in fw_text_alert or "启用" in fw_text_alert or "运行" in fw_text_alert):
                add_dashboard_alert("warn", "防火墙拦截可能未启用", fw_text_alert, "/admin/firewall", "检查防火墙")
        except Exception:
            pass

        try:
            if not qos_enabled():
                add_dashboard_alert("warn", "限速模块未启用", "如果需要按兑换码限速，请检查限速模块。", "/admin/qos", "检查限速")
        except Exception:
            pass

        try:
            auto_backup_alert = get_auto_backup_status()
            if not auto_backup_alert.get("ok"):
                add_dashboard_alert("warn", "自动备份异常", auto_backup_alert.get("summary", "自动备份状态异常"), "/admin/backup", "检查备份")
        except Exception:
            pass

        try:
            if last_backup and last_backup > 0:
                backup_age_hours_alert = max(0, (now() - int(last_backup)) // 3600)
                if backup_age_hours_alert > 72:
                    add_dashboard_alert("warn", "最近备份较旧", f"最近备份约 {backup_age_hours_alert} 小时前。", "/admin/backup", "立即备份")
            else:
                add_dashboard_alert("warn", "暂无备份", "当前没有发现备份文件。", "/admin/backup", "立即备份")
        except Exception:
            pass

        try:
            statvfs_alert = os.statvfs("/")
            free_alert = statvfs_alert.f_frsize * statvfs_alert.f_bavail
            free_mb_alert = free_alert // 1024 // 1024
            if free_mb_alert < 10:
                add_dashboard_alert("bad", "磁盘空间不足", f"剩余空间约 {free_mb_alert} MB。", "/admin/backup", "清理备份")
        except Exception:
            pass



        if dashboard_alert_rows:
            alert_html = f"""
<div class="card dashboard-alert-card">
<h2>异常提醒</h2>
<p class="muted">这里显示需要优先关注的问题，均为只读提醒。</p>
{''.join(dashboard_alert_rows)}
</div>
"""
        else:
            alert_html = """
<div class="card dashboard-alert-card">
<h2>异常提醒</h2>
<div class="dashboard-alert-item dashboard-alert-ok">
  <div>
    <b>当前没有明显异常</b>
    <p>失败日志、备份、到期、磁盘空间等基础检查暂未发现需要立即处理的问题。</p>
  </div>
  <div><a class="btn dashboard-alert-btn" href="/admin/health">健康检查</a></div>
</div>
</div>
"""

        try:
            local_now = time.localtime(now())
            today_start = int(time.mktime((local_now.tm_year, local_now.tm_mon, local_now.tm_mday, 0, 0, 0, 0, 0, -1)))
        except Exception:
            today_start = now() - 86400

        today_new_vouchers = 0
        today_used_vouchers = 0
        today_expired_vouchers = 0
        unused_vouchers = 0
        active_vouchers = 0
        expired_vouchers = 0
        disabled_vouchers = 0

        for code, voucher in vouchers.items():
            if int(voucher.get("created_at", 0) or 0) >= today_start:
                today_new_vouchers += 1

            first_used_at = int(voucher.get("first_used_at", 0) or 0)
            if first_used_at >= today_start:
                today_used_vouchers += 1

            expire_at = int(voucher.get("expire_at", 0) or 0)
            if expire_at >= today_start and expire_at <= now() and int(voucher.get("minutes", 0) or 0) != 0:
                today_expired_vouchers += 1

            status = voucher_status(voucher)
            if status == "已禁用":
                disabled_vouchers += 1
            elif status == "已过期":
                expired_vouchers += 1
            elif "未使用" in status:
                unused_vouchers += 1
            else:
                active_vouchers += 1

        today_login_devices = 0
        today_active_device_macs = set()
        for mac, device in devices.items():
            login_at = int(device.get("login_at", 0) or 0)
            last_seen = int(device.get("last_seen", 0) or 0)
            if login_at >= today_start:
                today_login_devices += 1
            if last_seen >= today_start or login_at >= today_start:
                today_active_device_macs.add(mac)

        today_log_count = 0
        today_fail_count = 0
        today_auth_ok_count = 0
        today_auth_fail_count = 0

        for item in logs:
            log_time = int(item.get("time", 0) or 0)
            if log_time < today_start:
                continue

            today_log_count += 1
            result = str(item.get("result", "") or "OK").upper()
            log_type = str(item.get("type", "") or "").upper()

            if result == "FAIL":
                today_fail_count += 1

            if log_type == "AUTH" and result == "OK":
                today_auth_ok_count += 1

            if log_type == "AUTH" and result == "FAIL":
                today_auth_fail_count += 1

        body = f"""
{alert_html}
<div class="card">
<h1>系统总览</h1>
<div class="grid">
<div class="stat">认证服务状态<b class="ok">{esc(service_status)}</b></div>
<div class="stat" onclick="location.href='/admin/firewall'" style="cursor:pointer">防火墙拦截状态<b>{esc(firewall_status)}</b></div>
<div class="stat" onclick="location.href='/admin/qos'" style="cursor:pointer">限速模块状态<b>{esc(qos_status_text())}</b></div>
<div class="stat">数据库大小<b>{database_size} bytes</b></div>
<div class="stat" onclick="location.href='/admin/backup'" style="cursor:pointer">最近备份时间<b>{esc(format_time(last_backup))}</b></div>
<div class="stat">系统运行时间<b>{esc(get_uptime_text())}</b></div>
<div class="stat">路由器时间<b>{esc(format_time(now()))}</b></div>
<div class="stat">LAN IP<b>{esc(LAN_IP)}</b></div>
<div class="stat">WAN 接口<b>{esc(WAN_IF)}</b></div>
<div class="stat" onclick="location.href='/admin/vouchers'" style="cursor:pointer">兑换码总数<b>{len(vouchers)}</b></div>
<div class="stat" onclick="location.href='/admin/devices?view=online'" style="cursor:pointer">实时在线设备<b>{len(online_devices)}</b></div>
<div class="stat" onclick="location.href='/admin/whitelist'" style="cursor:pointer">白名单设备<b>{len(db.get("whitelist", {}))}</b></div>
<div class="stat" onclick="location.href='/admin/blacklist'" style="cursor:pointer">黑名单设备<b>{len(db.get("blacklist", {}))}</b></div>
<div class="stat" onclick="location.href='/admin/health'" style="cursor:pointer">系统健康状态<b>立即检查</b></div>
<div class="stat" onclick="location.href='/admin/maintenance'" style="cursor:pointer">系统维护中心<b>打开</b></div>
<div class="stat" onclick="location.href='/admin/help'" style="cursor:pointer">后台帮助文档<b>查看</b></div>
<div class="stat" onclick="location.href='/admin/db-check'" style="cursor:pointer">数据一致性<b>检查</b></div>
</div>
</div>

<div class="card">
<h2>今日运营统计</h2>
<p class="muted">统计范围：今天 00:00 至当前路由器时间。点击部分卡片可跳转查看详情。</p>
<div class="grid">
<div class="stat" onclick="location.href='/admin/vouchers?status=all'" style="cursor:pointer">今日新增兑换码<b>{today_new_vouchers}</b></div>
<div class="stat" onclick="location.href='/admin/vouchers?status=active'" style="cursor:pointer">今日使用兑换码<b>{today_used_vouchers}</b></div>
<div class="stat" onclick="location.href='/admin/devices'" style="cursor:pointer">今日登录设备<b>{today_login_devices}</b></div>
<div class="stat" onclick="location.href='/admin/devices'" style="cursor:pointer">今日活跃设备<b>{len(today_active_device_macs)}</b></div>
<div class="stat" onclick="location.href='/admin/logs'" style="cursor:pointer">今日日志数量<b>{today_log_count}</b></div>
<div class="stat" onclick="location.href='/admin/logs'" style="cursor:pointer">今日失败次数<b>{today_fail_count}</b></div>
<div class="stat" onclick="location.href='/admin/logs'" style="cursor:pointer">今日认证成功<b>{today_auth_ok_count}</b></div>
<div class="stat" onclick="location.href='/admin/logs'" style="cursor:pointer">今日认证失败<b>{today_auth_fail_count}</b></div>
<div class="stat" onclick="location.href='/admin/vouchers?status=expired'" style="cursor:pointer">今日过期兑换码<b>{today_expired_vouchers}</b></div>
</div>
</div>

<div class="card">
<h2>兑换码状态</h2>
<div class="grid">
<div class="stat" onclick="location.href='/admin/vouchers?status=unused'" style="cursor:pointer">未使用<b>{unused_vouchers}</b></div>
<div class="stat" onclick="location.href='/admin/vouchers?status=active'" style="cursor:pointer">使用中<b>{active_vouchers}</b></div>
<div class="stat" onclick="location.href='/admin/vouchers?status=expired'" style="cursor:pointer">已过期<b>{expired_vouchers}</b></div>
<div class="stat" onclick="location.href='/admin/expiring'" style="cursor:pointer">即将到期兑换码<b>查看</b></div>
<div class="stat" onclick="location.href='/admin/vouchers?status=disabled'" style="cursor:pointer">已禁用<b>{disabled_vouchers}</b></div>
</div>
</div>

<div class="card">
<h2>当前状态</h2>
<p>客户认证页：<code>http://{esc(LAN_IP)}</code></p>
<p>客户自查页：<code>http://{esc(LAN_IP)}/check</code></p>
<p>路由器 LuCI：<code>http://{esc(LAN_IP)}:8080</code></p>
<p class="muted">后台已经支持本地兑换码认证、设备管理、安全锁定、限速、备份和移动端管理。</p>
</div>
"""
        self.send_html(admin_page("系统总览", body))

    def show_admin_settings(self):
        settings = load_settings()
        portal = settings.get("portal_page", {})
        body = f"""
<div class="card">
<h1>页面设置</h1>
<p class="muted">这里设置客户英文认证页面的信息框、套餐介绍和联系方式。</p>
<form method="post" action="/admin/settings">
<p>认证页标题</p>
<input name="title" value="{esc(portal.get("title", ""))}" style="width:100%;box-sizing:border-box">

<p>通知文本</p>
<textarea name="notice">{esc(portal.get("notice", ""))}</textarea>

<p>套餐介绍</p>
<textarea name="plan_text">{esc(portal.get("plan_text", ""))}</textarea>

<p>联系方式</p>
<textarea name="contact_text">{esc(portal.get("contact_text", ""))}</textarea>

<p>底部说明</p>
<textarea name="footer_text">{esc(portal.get("footer_text", ""))}</textarea>

<p><button type="submit">保存设置</button></p>
</form>
</div>
"""
        self.send_html(admin_page("页面设置", body))

    def show_admin_logs(self):
        db = load_db()
        raw_logs = db.get("logs", [])
        if not isinstance(raw_logs, list):
            raw_logs = []

        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        type_filter = str(query.get("type", ["all"])[0] or "all").strip().upper()
        result_filter = str(query.get("result", ["all"])[0] or "all").strip().upper()
        voucher_filter = str(query.get("voucher", [""])[0] or "").strip().upper()
        mac_filter = str(query.get("mac", [""])[0] or "").strip().lower()
        ip_filter = str(query.get("ip", [""])[0] or "").strip()
        keyword_filter = str(query.get("q", [""])[0] or "").strip()
        date_filter = str(query.get("date", ["all"])[0] or "all").strip().lower()

        if type_filter in ["", "ALL"]:
            type_filter = "all"
        if result_filter in ["", "ALL"]:
            result_filter = "all"
        if date_filter == "":
            date_filter = "all"

        if result_filter not in ["all", "OK", "FAIL"]:
            result_filter = "all"

        try:
            local_now = time.localtime(now())
            today_start = int(time.mktime((local_now.tm_year, local_now.tm_mon, local_now.tm_mday, 0, 0, 0, 0, 0, -1)))
        except Exception:
            today_start = now() - 86400

        def normalize_log_item(item):
            if isinstance(item, dict):
                log_time = int(item.get("time", 0) or 0)
                log_type = str(item.get("type", "") or "LOG")
                log_result = str(item.get("result", "") or "OK").upper()
                if log_result not in ["OK", "FAIL"]:
                    log_result = "OK"
                return {
                    "time": log_time,
                    "type": log_type,
                    "result": log_result,
                    "message": str(item.get("message", "") or ""),
                    "voucher_code": str(item.get("voucher_code", "") or ""),
                    "mac": str(item.get("mac", "") or ""),
                    "ip": str(item.get("ip", "") or "")
                }

            return {
                "time": 0,
                "type": "RAW",
                "result": "OK",
                "message": str(item),
                "voucher_code": "",
                "mac": "",
                "ip": ""
            }

        logs = [normalize_log_item(item) for item in raw_logs]

        type_set = sorted(set(item["type"].upper() for item in logs if item.get("type")))
        type_options = ['<option value="all">全部类型</option>']
        for item_type in type_set:
            selected = " selected" if type_filter == item_type else ""
            type_options.append(f'<option value="{esc(item_type)}"{selected}>{esc(item_type)}</option>')

        result_options = []
        for value, label in [("all", "全部结果"), ("OK", "成功 OK"), ("FAIL", "失败 FAIL")]:
            selected = " selected" if result_filter == value else ""
            result_options.append(f'<option value="{value}"{selected}>{label}</option>')

        date_options = []
        for value, label in [("all", "全部时间"), ("today", "今天"), ("24h", "最近24小时"), ("7d", "最近7天")]:
            selected = " selected" if date_filter == value else ""
            date_options.append(f'<option value="{value}"{selected}>{label}</option>')

        filtered = []
        for item in logs:
            log_time = int(item.get("time", 0) or 0)
            log_type = str(item.get("type", "") or "LOG").upper()
            log_result = str(item.get("result", "") or "OK").upper()
            log_voucher = str(item.get("voucher_code", "") or "").upper()
            log_mac = str(item.get("mac", "") or "").lower()
            log_ip = str(item.get("ip", "") or "")
            log_message = str(item.get("message", "") or "")

            if type_filter != "all" and log_type != type_filter:
                continue

            if result_filter != "all" and log_result != result_filter:
                continue

            if voucher_filter and voucher_filter not in log_voucher:
                continue

            if mac_filter and mac_filter not in log_mac:
                continue

            if ip_filter and ip_filter not in log_ip:
                continue

            if date_filter == "today" and log_time > 0 and log_time < today_start:
                continue

            if date_filter == "24h" and log_time > 0 and log_time < now() - 86400:
                continue

            if date_filter == "7d" and log_time > 0 and log_time < now() - 86400 * 7:
                continue

            if keyword_filter:
                blob = " ".join([
                    log_type,
                    log_result,
                    log_message,
                    log_voucher,
                    log_mac,
                    log_ip,
                    format_time(log_time)
                ]).lower()
                if keyword_filter.lower() not in blob:
                    continue

            filtered.append(item)

        filtered.sort(key=lambda x: int(x.get("time", 0) or 0), reverse=True)
        shown_logs = filtered[:300]

        today_count = 0
        fail_count = 0
        auth_ok_count = 0
        auth_fail_count = 0

        for item in logs:
            log_time = int(item.get("time", 0) or 0)
            if log_time <= 0 or log_time < today_start:
                continue

            today_count += 1
            log_type = str(item.get("type", "") or "").upper()
            log_result = str(item.get("result", "") or "OK").upper()

            if log_result == "FAIL":
                fail_count += 1
            if log_type == "AUTH" and log_result == "OK":
                auth_ok_count += 1
            if log_type == "AUTH" and log_result == "FAIL":
                auth_fail_count += 1

        rows = []
        for item in shown_logs:
            log_result = str(item.get("result", "OK") or "OK").upper()
            result_class = "ok" if log_result == "OK" else "bad"
            result_badge = f'<span class="log-result-badge {result_class}">{esc(log_result)}</span>'

            log_time = int(item.get("time", 0) or 0)
            time_text = format_time(log_time) if log_time > 0 else "-"

            rows.append(f"""
<tr>
<td>{esc(time_text)}</td>
<td><b>{esc(item.get("type", ""))}</b></td>
<td>{result_badge}</td>
<td>{esc(item.get("message", ""))}</td>
<td><code>{esc(item.get("voucher_code", ""))}</code></td>
<td><code>{esc(item.get("mac", ""))}</code></td>
<td>{esc(item.get("ip", ""))}</td>
</tr>
""")

        active_filters = []
        if type_filter != "all":
            active_filters.append("类型=" + type_filter)
        if result_filter != "all":
            active_filters.append("结果=" + result_filter)
        if date_filter != "all":
            active_filters.append("时间=" + date_filter)
        if voucher_filter:
            active_filters.append("兑换码=" + voucher_filter)
        if mac_filter:
            active_filters.append("MAC=" + mac_filter)
        if ip_filter:
            active_filters.append("IP=" + ip_filter)
        if keyword_filter:
            active_filters.append("关键词=" + keyword_filter)

        active_filter_text = "；".join(active_filters) if active_filters else "无"

        body = f"""
<div class="card">
<h1>系统日志</h1>
<p class="muted">数据库最多保留最近 500 条；当前筛选后显示前 300 条。</p>
<div class="grid">
<div class="stat">日志总数<b>{len(logs)}</b></div>
<div class="stat">筛选结果<b>{len(filtered)}</b></div>
<div class="stat">当前显示<b>{len(shown_logs)}</b></div>
<div class="stat">今日日志<b>{today_count}</b></div>
<div class="stat">今日失败<b>{fail_count}</b></div>
<div class="stat">今日认证成功<b>{auth_ok_count}</b></div>
<div class="stat">今日认证失败<b>{auth_fail_count}</b></div>
</div>
</div>

<div class="card">
<h2>筛选日志</h2>
<form method="get" action="/admin/logs">
<div class="grid">
<div>
<p>日志类型</p>
<select name="type">{''.join(type_options)}</select>
</div>
<div>
<p>结果</p>
<select name="result">{''.join(result_options)}</select>
</div>
<div>
<p>时间范围</p>
<select name="date">{''.join(date_options)}</select>
</div>
<div>
<p>兑换码</p>
<input name="voucher" value="{esc(voucher_filter)}" placeholder="输入兑换码">
</div>
<div>
<p>MAC</p>
<input name="mac" value="{esc(mac_filter)}" placeholder="输入 MAC">
</div>
<div>
<p>IP</p>
<input name="ip" value="{esc(ip_filter)}" placeholder="输入 IP">
</div>
<div>
<p>关键词</p>
<input name="q" value="{esc(keyword_filter)}" placeholder="内容关键词">
</div>
</div>
<p>
<button type="submit">筛选</button>
<a class="btn" href="/admin/logs">清空筛选</a>
<a class="btn" href="/admin/logs?date=today&result=FAIL">今日失败</a>
<a class="btn" href="/admin/logs?result=FAIL">全部失败</a>
</p>
</form>
<p class="muted">当前筛选：{esc(active_filter_text)}</p>
<form method="post" action="/admin/logs-clear" onsubmit="return confirm('确认清空全部日志？')">
<button class="danger" type="submit">清空日志</button>
</form>
</div>

<div class="card">
<h2>日志列表</h2>
<table class="logs-filter-table">
<tr><th>时间</th><th>类型</th><th>结果</th><th>内容</th><th>兑换码</th><th>MAC</th><th>IP</th></tr>
{''.join(rows) if rows else '<tr><td colspan="7" class="muted">没有符合条件的日志</td></tr>'}
</table>
</div>
"""
        self.send_html(admin_page("系统日志", body))

    def show_admin_backup(self):
        backups = list_backups()
        rows = []
        for item in backups:
            rows.append(f"""
<tr>
<td><code>{esc(item["name"])}</code></td>
<td>{esc(item["size"])} bytes</td>
<td>{esc(format_time(item["mtime"]))}</td>
<td>
<form method="post" action="/admin/backup-download" style="display:inline">
<input type="hidden" name="name" value="{esc(item["name"])}">
<button type="submit">下载</button>
</form>
<form method="post" action="/admin/backup-restore" style="display:inline" onsubmit="return confirm('确认恢复这个备份？当前数据库和设置会被覆盖。')">
<input type="hidden" name="name" value="{esc(item["name"])}">
<button class="danger" type="submit">恢复</button>
</form>
</td>
</tr>
""")

        auto_backup = get_auto_backup_status()
        auto_class = "ok" if auto_backup.get("ok") else "bad"
        auto_log = esc(auto_backup.get("log_text", "") or "暂无自动备份日志")
        auto_cron_line = esc(auto_backup.get("cron_line", "") or "-")
        auto_last_backup = esc(auto_backup.get("last_backup_text", "-"))
        auto_last_name = esc(auto_backup.get("last_backup_name", ""))

        body = f"""
<div class="card">
<h1>备份恢复</h1>
<p class="muted">备份包含兑换码、设备、白名单、黑名单、安全记录、日志和页面设置。</p>
<form method="post" action="/admin/backup-create" style="display:inline">
<button type="submit">立即创建备份</button>
</form>
<form method="post" action="/admin/backup-clean" style="display:inline" onsubmit="return confirm('确认只保留最近 7 个备份？')">
<button class="danger" type="submit">清理旧备份</button>
</form>
</div>

<div class="card">
<h2>自动备份状态</h2>
<div class="grid">
<div class="stat">状态<b class="{auto_class}">{esc(auto_backup.get("summary", ""))}</b></div>
<div class="stat">脚本文件<b>{'存在' if auto_backup.get("script_exists") else '不存在'}</b></div>
<div class="stat">Cron 任务<b>{'存在' if auto_backup.get("cron_exists") else '不存在'}</b></div>
<div class="stat">Cron 服务<b>{'运行中' if auto_backup.get("cron_running") else '未运行'}</b></div>
<div class="stat">执行时间<b>每天 03:07</b></div>
<div class="stat">最近备份<b>{auto_last_backup}</b></div>
</div>
<p>任务行：<code>{auto_cron_line}</code></p>
<p>最近备份文件：<code>{auto_last_name or '-'}</code></p>
<p class="muted">手动测试命令：<code>/usr/bin/wifiportal_auto_backup.sh</code></p>
<details>
<summary>查看最近自动备份日志</summary>
<pre class="auto-backup-log">{auto_log}</pre>
</details>
</div>

<div class="card">
<h2>备份文件</h2>
<table>
<tr><th>文件名</th><th>大小</th><th>时间</th><th>操作</th></tr>
{''.join(rows) if rows else '<tr><td colspan="4" class="muted">暂无备份文件</td></tr>'}
</table>
</div>
"""
        self.send_html(admin_page("备份恢复", body))

    def admin_logs_clear(self):
        db = load_db()
        count = len(db.get("logs", []))
        db["logs"] = []
        save_db(db)
        append_log("LOG", f"管理员清空日志 {count} 条")
        append_admin_audit(self, "清空系统日志", f"count={count}")
        self.redirect("/admin/logs")

    def admin_backup_create(self):
        backup_file = create_backup()
        append_log("BACKUP", f"创建备份 {os.path.basename(backup_file)}")
        append_admin_audit(self, "创建备份", os.path.basename(backup_file))
        self.redirect("/admin/backup")

    def admin_backup_clean(self):
        deleted = cleanup_old_backups(7)
        append_log("BACKUP", f"清理旧备份 {len(deleted)} 个")
        append_admin_audit(self, "清理旧备份", f"count={len(deleted)}")
        self.redirect("/admin/backup")

    def admin_backup_restore(self):
        form = self.read_form()
        name = form.get("name", "")
        ok, message = restore_backup_file(name)
        if ok:
            append_log("BACKUP", f"恢复备份 {name}")
            append_admin_audit(self, "恢复备份", name)
            self.send_html(admin_page("恢复成功", f"<div class='card'><h1 class='ok'>{esc(message)}</h1><p>请重新检查系统数据。</p><a class='btn' href='/admin'>返回总览</a></div>"))
        else:
            self.send_html(admin_page("恢复失败", f"<div class='card'><h1 class='bad'>{esc(message)}</h1><a class='btn' href='/admin/backup'>返回</a></div>"))

    def admin_backup_download(self):
        form = self.read_form()
        name = os.path.basename(form.get("name", ""))
        backup_path = os.path.join("/etc/wifiportal/backup", name)

        if not name or not os.path.exists(backup_path):
            self.send_html(admin_page("下载失败", "<div class='card'><h1 class='bad'>备份文件不存在</h1><a class='btn' href='/admin/backup'>返回</a></div>"))
            return

        with open(backup_path, "rb") as file:
            content = file.read()

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def show_admin_qos(self):
        db = load_db()
        devices = db.get("devices", {})

        code1, br_class, _ = qos_run(["/sbin/tc", "class", "show", "dev", LAN_IF])
        code2, ifb_class, _ = qos_run(["/sbin/tc", "class", "show", "dev", QOS_IFB])
        br_class_text = br_class or ""
        ifb_class_text = ifb_class or ""

        rows = []
        limited_count = 0
        unlimited_count = 0
        online_count = 0

        for mac, device in sorted(devices.items()):
            online = bool(device.get("online"))
            expire_at = int(device.get("expire_at", 0) or 0)
            if expire_at > 0 and expire_at <= now():
                online = False

            download_kbps = int(device.get("download_kbps", 0) or 0)
            upload_kbps = int(device.get("upload_kbps", 0) or 0)
            cid = str(qos_class_id(mac))

            if online:
                online_count += 1

            if download_kbps <= 0 and upload_kbps <= 0:
                qos_state = "不限速"
                unlimited_count += 1
            elif not online:
                qos_state = "设备未在线"
            else:
                has_download_rule = f"1:{cid}" in br_class_text if download_kbps > 0 else True
                has_upload_rule = f"1:{cid}" in ifb_class_text if upload_kbps > 0 else True

                if has_download_rule and has_upload_rule:
                    qos_state = "已应用"
                    limited_count += 1
                else:
                    qos_state = "未应用/需重建"

            if download_kbps <= 0:
                download_text = "不限速"
            else:
                download_text = f"{kbps_to_mbps(download_kbps)} Mbps"

            if upload_kbps <= 0:
                upload_text = "不限速"
            else:
                upload_text = f"{kbps_to_mbps(upload_kbps)} Mbps"

            rows.append(f"""
<tr>
<td>{esc(device.get("hostname", "Unknown Device"))}</td>
<td><code>{esc(mac)}</code></td>
<td>{esc(device.get("ip", ""))}</td>
<td><code>{esc(device.get("voucher_code", ""))}</code></td>
<td>{esc(device.get("speed_profile_name", ""))}</td>
<td>{esc(download_text)}</td>
<td>{esc(upload_text)}</td>
<td>{esc("在线" if online else "离线")}</td>
<td><b>{esc(qos_state)}</b></td>
</tr>
""")

        body = f"""
<div class="card">
<h1>限速模块</h1>
<div class="grid">
<div class="stat">限速开关<b>{'已启用' if qos_enabled() else '未启用'}</b></div>
<div class="stat">模块状态<b>{esc(qos_status_text())}</b></div>
<div class="stat">在线设备<b>{online_count}</b></div>
<div class="stat">已限速设备<b>{limited_count}</b></div>
<div class="stat">不限速设备<b>{unlimited_count}</b></div>
<div class="stat">LAN 接口<b>{esc(LAN_IF)}</b></div>
<div class="stat">IFB 接口<b>{esc(QOS_IFB)}</b></div>
</div>
<p class="muted">这里显示的是中文可读状态，不需要看 tc 原始规则。速度填 0 表示不限速。</p>
</div>

<div class="card">
<h2>操作</h2>
<form method="post" action="/admin/qos-init" style="display:inline">
<button type="submit">初始化限速模块</button>
</form>
<form method="post" action="/admin/qos-restore" style="display:inline">
<button type="submit">重建在线设备限速</button>
</form>
<form method="post" action="/admin/qos-clear" style="display:inline" onsubmit="return confirm('确认清空全部限速规则？认证放行不受影响。')">
<button class="danger" type="submit">清空限速规则</button>
</form>
</div>

<div class="card">
<h2>设备限速状态</h2>
<table>
<tr>
<th>设备名</th>
<th>MAC</th>
<th>IP</th>
<th>兑换码</th>
<th>套餐</th>
<th>下载限速</th>
<th>上传限速</th>
<th>在线状态</th>
<th>限速状态</th>
</tr>
{''.join(rows) if rows else '<tr><td colspan="9" class="muted">暂无设备记录</td></tr>'}
</table>
</div>

<div class="card">
<h2>状态说明</h2>
<p><b>已应用：</b>当前在线设备已经套用了对应兑换码的下载/上传限速。</p>
<p><b>不限速：</b>这个设备对应兑换码下载和上传都填了 0，不限制速度。</p>
<p><b>未应用/需重建：</b>设备在线，但限速规则没有检测到，点击“重建在线设备限速”即可。</p>
<p><b>设备未在线：</b>设备当前不在线，不需要限速规则。</p>
</div>
"""
        self.send_html(admin_page("限速模块", body))

    def admin_qos_init(self):
        ok, message = qos_init()
        if ok:
            self.send_html(admin_page("限速已初始化", f"<div class='card'><h1 class='ok'>限速模块已初始化</h1><p>{esc(message)}</p><a class='btn' href='/admin/qos'>返回</a></div>"))
        else:
            self.send_html(admin_page("限速初始化失败", f"<div class='card'><h1 class='bad'>初始化失败</h1><p>{esc(message)}</p><a class='btn' href='/admin/qos'>返回</a></div>"))

    def admin_qos_clear(self):
        qos_clear()
        self.redirect("/admin/qos")

    def admin_qos_restore(self):
        qos_restore_sessions()
        append_log("QOS", "管理员重建在线设备限速")
        append_admin_audit(self, "重建在线设备限速")
        self.redirect("/admin/qos")

    def show_admin_firewall(self):
        enabled = check_nft_table_exists()
        code, out, err = run_command(["/usr/sbin/nft", "list", "table", "inet", "wifiportal"])
        rules_preview = out if out else err

        body = f"""
<div class="card">
<h1>防火墙认证拦截</h1>
<div class="grid">
<div class="stat">当前状态<b>{'已启用' if enabled else '未启用'}</b></div>
<div class="stat">LAN 接口<b>{esc(LAN_IF)}</b></div>
<div class="stat">WAN 接口<b>{esc(WAN_IF)}</b></div>
<div class="stat">认证页面<b>http://{esc(LAN_IP)}</b></div>
</div>
<p class="muted">启用后，未认证设备会被拦截外网，HTTP 会跳到认证页面。你的 LuCI 管理仍在 http://{esc(LAN_IP)}:8080。</p>
</div>

<div class="card">
<h2>操作</h2>
<form method="post" action="/admin/firewall-enable" style="display:inline" onsubmit="return confirm('确认启用认证拦截？未认证设备将不能直接上网。')">
<button type="submit">启用认证拦截</button>
</form>
<form method="post" action="/admin/firewall-disable" style="display:inline" onsubmit="return confirm('确认关闭认证拦截？所有设备将恢复正常上网。')">
<button class="danger" type="submit">关闭认证拦截</button>
</form>
<form method="post" action="/admin/firewall-restore-sessions" style="display:inline">
<button type="submit">恢复已认证会话</button>
</form>
</div>

<div class="card">
<h2>当前 nftables 规则</h2>
<pre style="white-space:pre-wrap;background:#0f172a;color:#e5e7eb;padding:12px;border-radius:10px;overflow:auto">{esc(rules_preview[:8000] if rules_preview else 'No wifiportal table')}</pre>
</div>
"""
        self.send_html(admin_page("防火墙认证拦截", body))

    def admin_firewall_enable(self):
        ok, message = nft_init_table()
        if ok:
            restore_firewall_sessions()
            append_log("FIREWALL", "管理员启用认证拦截")
            append_admin_audit(self, "启用认证拦截")
            self.send_html(admin_page("已启用", f"<div class='card'><h1 class='ok'>认证拦截已启用</h1><p>{esc(message)}</p><a class='btn' href='/admin/firewall'>返回</a></div>"))
        else:
            append_log("FIREWALL", f"启用认证拦截失败：{message}", result="FAIL")
            append_admin_audit(self, "启用认证拦截失败", message, result="FAIL")
            self.send_html(admin_page("启用失败", f"<div class='card'><h1 class='bad'>启用失败</h1><p>{esc(message)}</p><a class='btn' href='/admin/firewall'>返回</a></div>"))

    def admin_firewall_disable(self):
        nft_delete_table()
        append_log("FIREWALL", "管理员关闭认证拦截")
        append_admin_audit(self, "关闭认证拦截")
        self.send_html(admin_page("已关闭", "<div class='card'><h1 class='ok'>认证拦截已关闭</h1><p>所有设备恢复正常转发。</p><a class='btn' href='/admin/firewall'>返回</a></div>"))

    def admin_firewall_restore_sessions(self):
        restore_firewall_sessions()
        qos_restore_sessions()
        append_log("FIREWALL", "管理员恢复已认证会话")
        append_admin_audit(self, "恢复已认证会话")
        self.redirect("/admin/firewall")

    def show_admin_password(self):
        body = """
<div class="card" style="max-width:560px">
<h1>修改后台密码</h1>
<form method="post" action="/admin/password">
<p>当前密码</p>
<input name="current_password" type="password" required style="width:100%;box-sizing:border-box">
<p>新密码</p>
<input name="new_password" type="password" required style="width:100%;box-sizing:border-box">
<p>确认新密码</p>
<input name="confirm_password" type="password" required style="width:100%;box-sizing:border-box">
<p class="muted">新密码至少 8 位。修改成功后需要重新登录。</p>
<p><button type="submit">修改密码</button></p>
</form>
</div>
"""
        self.send_html(admin_page("修改密码", body))


    def show_admin_expiring_vouchers(self):
        db = load_db()
        vouchers = db.get("vouchers", {})
        current_time = now()

        one_hour = []
        today = []
        three_days = []
        expired = []

        try:
            local_now = time.localtime(current_time)
            today_end = int(time.mktime((local_now.tm_year, local_now.tm_mon, local_now.tm_mday, 23, 59, 59, 0, 0, -1)))
        except Exception:
            today_end = current_time + 86400

        for code, voucher in vouchers.items():
            if not voucher.get("enabled", True):
                continue

            minutes = int(voucher.get("minutes", 0) or 0)
            if minutes == 0:
                continue

            first_used_at = int(voucher.get("first_used_at", 0) or 0)
            expire_at = int(voucher.get("expire_at", 0) or 0)

            if first_used_at <= 0 or expire_at <= 0:
                continue

            item = {
                "code": code,
                "voucher": voucher,
                "expire_at": expire_at,
                "remain": expire_at - current_time,
            }

            if expire_at <= current_time:
                expired.append(item)
            elif expire_at <= current_time + 3600:
                one_hour.append(item)
            elif expire_at <= today_end:
                today.append(item)
            elif expire_at <= current_time + 86400 * 3:
                three_days.append(item)

        one_hour.sort(key=lambda x: x["expire_at"])
        today.sort(key=lambda x: x["expire_at"])
        three_days.sort(key=lambda x: x["expire_at"])
        expired.sort(key=lambda x: x["expire_at"], reverse=True)

        def remain_label(item):
            remain = int(item.get("remain", 0) or 0)
            if remain <= 0:
                ago = abs(remain)
                days = ago // 86400
                hours = (ago % 86400) // 3600
                mins = (ago % 3600) // 60
                if days > 0:
                    return f"已过期 {days}天 {hours}小时"
                if hours > 0:
                    return f"已过期 {hours}小时 {mins}分钟"
                return f"已过期 {mins}分钟"

            days = remain // 86400
            hours = (remain % 86400) // 3600
            mins = (remain % 3600) // 60
            if days > 0:
                return f"{days}天 {hours}小时 {mins}分钟"
            if hours > 0:
                return f"{hours}小时 {mins}分钟"
            return f"{mins}分钟"

        def build_rows(items, empty_text):
            rows = []
            for item in items:
                code = item["code"]
                voucher = item["voucher"]
                code_q = urllib.parse.quote(str(code))
                used_count = len(voucher.get("devices", {}) or {})
                max_devices = voucher.get("max_devices", 1)
                speed = f"{kbps_to_mbps(voucher.get('download_kbps', 0))}↓/{kbps_to_mbps(voucher.get('upload_kbps', 0))}↑"
                rows.append(f"""
<tr>
<td><code>{esc(code)}</code></td>
<td>
  <b>
    <span class="expiring-countdown" data-expire-at="{int(item.get("expire_at", 0) or 0)}">
      {esc(remain_label(item))}
    </span>
  </b>
</td>
<td>{esc(format_time(item.get("expire_at", 0)))}</td>
<td>{esc(voucher.get("speed_profile_name", ""))}<br><span class="muted">{esc(speed)} Mbps</span></td>
<td>{used_count}/{esc(max_devices)}</td>
<td>{esc(voucher.get("note", "")) or '<span class="muted">无</span>'}</td>
<td>
<a class="btn expiring-mini-btn" href="/admin/voucher-detail?code={code_q}">详情</a>
<a class="btn expiring-mini-btn" href="/admin/voucher-edit?code={code_q}">编辑</a>
<a class="btn expiring-mini-btn" href="/admin/logs?voucher={code_q}">日志</a>
</td>
</tr>
""")
            return "".join(rows) if rows else f'<tr><td colspan="7" class="muted">{esc(empty_text)}</td></tr>'

        body = f"""
<div class="card">
<h1>即将到期兑换码</h1>
<p class="muted">这里只显示已经开始使用、非永久、未禁用的兑换码。此页面只读，不会自动删除或踢人。</p>
<div class="grid">
<div class="stat">1小时内到期<b>{len(one_hour)}</b></div>
<div class="stat">今天到期<b>{len(today)}</b></div>
<div class="stat">3天内到期<b>{len(three_days)}</b></div>
<div class="stat">已过期<b>{len(expired)}</b></div>
</div>
<p>
<a class="btn" href="/admin/vouchers">兑换码管理</a>
<a class="btn" href="/admin/vouchers?status=expired">查看全部过期</a>
<a class="btn" href="/admin/logs?date=today&type=AUTH">今日认证日志</a>
</p>
</div>

<div class="card">
<h2>1 小时内到期</h2>
<table class="expiring-table">
<tr><th>兑换码</th><th>剩余时间</th><th>到期时间</th><th>套餐/网速</th><th>设备</th><th>备注</th><th>操作</th></tr>
{build_rows(one_hour, "暂无 1 小时内到期兑换码")}
</table>
</div>

<div class="card">
<h2>今天到期</h2>
<table class="expiring-table">
<tr><th>兑换码</th><th>剩余时间</th><th>到期时间</th><th>套餐/网速</th><th>设备</th><th>备注</th><th>操作</th></tr>
{build_rows(today, "暂无今天到期兑换码")}
</table>
</div>

<div class="card">
<h2>3 天内到期</h2>
<table class="expiring-table">
<tr><th>兑换码</th><th>剩余时间</th><th>到期时间</th><th>套餐/网速</th><th>设备</th><th>备注</th><th>操作</th></tr>
{build_rows(three_days, "暂无 3 天内到期兑换码")}
</table>
</div>

<div class="card">
<h2>已过期</h2>
<table class="expiring-table">
<tr><th>兑换码</th><th>状态</th><th>到期时间</th><th>套餐/网速</th><th>设备</th><th>备注</th><th>操作</th></tr>
{build_rows(expired[:100], "暂无已过期兑换码")}
</table>
<p class="muted">已过期区域最多显示最近 100 个，完整过期列表请到兑换码管理里筛选“已过期”。</p>
</div>

<script>
(function() {{
  function formatRemain(expireAt) {{
    var nowSec = Math.floor(Date.now() / 1000);
    var remain = Math.floor(expireAt - nowSec);

    if (remain <= 0) {{
      var ago = Math.abs(remain);
      var agoDays = Math.floor(ago / 86400);
      var agoHours = Math.floor((ago % 86400) / 3600);
      var agoMinutes = Math.floor((ago % 3600) / 60);
      var agoSeconds = ago % 60;

      if (agoDays > 0) {{
        return '已过期 ' + agoDays + '天 ' + agoHours + '小时 ' + agoMinutes + '分钟 ' + agoSeconds + '秒';
      }}
      if (agoHours > 0) {{
        return '已过期 ' + agoHours + '小时 ' + agoMinutes + '分钟 ' + agoSeconds + '秒';
      }}
      if (agoMinutes > 0) {{
        return '已过期 ' + agoMinutes + '分钟 ' + agoSeconds + '秒';
      }}
      return '已过期 ' + agoSeconds + '秒';
    }}

    var days = Math.floor(remain / 86400);
    var hours = Math.floor((remain % 86400) / 3600);
    var minutes = Math.floor((remain % 3600) / 60);
    var seconds = remain % 60;

    if (days > 0) {{
      return days + '天 ' + hours + '小时 ' + minutes + '分钟 ' + seconds + '秒';
    }}
    if (hours > 0) {{
      return hours + '小时 ' + minutes + '分钟 ' + seconds + '秒';
    }}
    if (minutes > 0) {{
      return minutes + '分钟 ' + seconds + '秒';
    }}
    return seconds + '秒';
  }}

  function wpExpiringCountdownTick() {{
    var items = document.querySelectorAll('.expiring-countdown');
    for (var i = 0; i < items.length; i++) {{
      var el = items[i];
      var expireAt = parseInt(el.getAttribute('data-expire-at') || '0', 10);
      if (expireAt > 0) {{
        el.textContent = formatRemain(expireAt);
      }}
    }}
  }}

  wpExpiringCountdownTick();
  setInterval(wpExpiringCountdownTick, 1000);
}})();
</script>
"""
        self.send_html(admin_page("即将到期兑换码", body))


    def show_admin_vouchers(self):
        db = load_db()
        plans = get_speed_plans()

        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        search_text = str(query.get("q", [""])[0] or "").strip()
        status_filter = str(query.get("status", ["all"])[0] or "all").strip()
        if status_filter not in ["all", "unused", "active", "expired", "disabled"]:
            status_filter = "all"

        def voucher_filter_key(voucher):
            status = voucher_status(voucher)
            if status == "已禁用":
                return "disabled"
            if status == "已过期":
                return "expired"
            if "未使用" in status:
                return "unused"
            return "active"

        def status_badge_html(status, key):
            if key in ["disabled", "expired"]:
                cls = "dense-badge-danger"
            elif key == "unused":
                cls = "dense-badge-blue"
            else:
                cls = "dense-badge-green"
            return '<span class="dense-badge ' + cls + '">' + esc(status) + '</span>'

        all_vouchers = db.get("vouchers", {})
        stats = {
            "all": len(all_vouchers),
            "unused": 0,
            "active": 0,
            "expired": 0,
            "disabled": 0
        }

        for item in all_vouchers.values():
            key = voucher_filter_key(item)
            stats[key] = stats.get(key, 0) + 1

        plan_options = []
        for index, plan in enumerate(plans):
            label = f"{plan.get('name', 'Plan')} | {format_duration(plan.get('minutes', 1440))} | {plan.get('download_mbps', '0')}M↓/{plan.get('upload_mbps', '0')}M↑ | {plan.get('max_devices', 1)}台"
            plan_options.append(f'<option value="{index}">{esc(label)}</option>')

        filter_labels = {
            "all": "全部",
            "unused": "未使用",
            "active": "使用中",
            "expired": "已过期",
            "disabled": "已禁用"
        }

        def filter_link(key):
            active_class = " dense-filter-active" if status_filter == key else ""
            q_part = urllib.parse.quote(search_text)
            return f'<a class="btn dense-filter-btn{active_class}" href="/admin/vouchers?status={key}&q={q_part}">{filter_labels[key]} <b>{stats.get(key, 0)}</b></a>'

        filter_buttons = " ".join([
            filter_link("all"),
            filter_link("unused"),
            filter_link("active"),
            filter_link("expired"),
            filter_link("disabled")
        ])

        # EXPORT_UNUSED_VISIBLE_V1
        export_unused_notice = ""
        if status_filter == "unused":
            export_unused_notice = f"""
<div class="card export-unused-notice">
<h2>未使用兑换码导出</h2>
<p class="muted">当前正在查看未使用兑换码，共 <b>{stats.get("unused", 0)}</b> 个。</p>
<p>
<a class="btn export-unused-main-btn" href="/admin/export-unused">一键导出未使用兑换码</a>
</p>
</div>
"""

        voucher_rows = []
        shown_count = 0

        for code, voucher in sorted(all_vouchers.items()):
            status = voucher_status(voucher)
            filter_key = voucher_filter_key(voucher)

            if status_filter != "all" and filter_key != status_filter:
                continue

            search_blob = " ".join([
                str(code),
                str(status),
                str(voucher.get("note", "")),
                str(voucher.get("speed_profile_name", "")),
                str(format_duration(voucher.get("minutes", 0))),
                str(remaining_text(voucher))
            ]).lower()

            if search_text and search_text.lower() not in search_blob:
                continue

            shown_count += 1

            used_count = len(voucher.get("devices", {}))
            max_devices = voucher.get("max_devices", 1)
            duration = format_duration(voucher.get("minutes", 0))
            remaining = remaining_text(voucher)
            plan_name = voucher.get("speed_profile_name", "")
            speed = f"{kbps_to_mbps(voucher.get('download_kbps', 0))}↓/{kbps_to_mbps(voucher.get('upload_kbps', 0))}↑"
            first_time = format_time(voucher.get("first_used_at", 0))
            expire_time = format_time(voucher.get("expire_at", 0))
            note_text = str(voucher.get("note", "") or "").strip()
            note_html = esc(note_text) if note_text else "<span class='muted'>无</span>"
            copy_js = json.dumps(str(code))
            code_q = urllib.parse.quote(str(code))
            status_badge = status_badge_html(status, filter_key)

            if voucher.get("enabled", True):
                toggle_text = "禁用"
                toggle_class = ""
            else:
                toggle_text = "启用"
                toggle_class = " dense-good"

            voucher_rows.append(f"""
<tr>
<td class="dense-select-col">
  <input type="checkbox" class="voucher-select-box" value="{esc(code)}">
</td>
<td class="dense-code-col">
  <code>{esc(code)}</code>
  <button type="button" class="dense-mini-btn dense-good" onclick="navigator.clipboard.writeText({copy_js});this.textContent='已复制'">复制</button>
  <a class="btn dense-mini-btn" href="/admin/voucher-detail?code={code_q}">详情</a>
  <a class="btn dense-mini-btn" href="/admin/voucher-edit?code={code_q}">编辑</a>
</td>
<td class="dense-status-col">
  {status_badge}
  <div class="dense-sub">剩余：{esc(remaining)}</div>
</td>
<td>
  <b>{esc(plan_name)}</b>
  <div class="dense-sub">{esc(speed)} Mbps</div>
</td>
<td>
  <b>{used_count}/{esc(max_devices)}</b>
  <div class="dense-sub">{esc(duration)}</div>
</td>
<td>
  <b>{esc(expire_time)}</b>
  <div class="dense-sub">首次：{esc(first_time)}</div>
</td>
<td class="dense-note-col">{note_html}</td>
<td class="dense-actions-col">
  <div class="dense-actions-main">
    <form method="post" action="/admin/voucher-toggle">
      <input type="hidden" name="code" value="{esc(code)}">
      <button type="submit" class="dense-mini-btn{toggle_class}">{toggle_text}</button>
    </form>

    <form method="post" action="/admin/voucher-extend">
      <input type="hidden" name="code" value="{esc(code)}">
      <select name="minutes" class="dense-mini-select">
        <option value="60">+1h</option>
        <option value="1440" selected>+1d</option>
        <option value="10080">+7d</option>
        <option value="43200">+30d</option>
      </select>
      <button type="submit" class="dense-mini-btn">延长</button>
    </form>

    <details class="dense-more">
      <summary>更多</summary>
      <form method="post" action="/admin/voucher-reset" onsubmit="return confirm('确认重置这个兑换码？会踢掉已绑定设备。')">
        <input type="hidden" name="code" value="{esc(code)}">
        <button type="submit" class="dense-mini-btn">重置</button>
      </form>
      <form method="post" action="/admin/voucher-delete" onsubmit="return confirm('确认永久删除这个兑换码？此操作不可恢复。')">
        <input type="hidden" name="code" value="{esc(code)}">
        <button class="danger dense-mini-btn" type="submit">删除</button>
      </form>
    </details>
  </div>
</td>
</tr>
""")

        plan_rows = []
        for index, plan in enumerate(plans):
            plan_rows.append(f"""
<tr>
<td>
  <b>{esc(plan.get("name", ""))}</b>
  <br><span class="muted">{esc(plan.get("note", ""))}</span>
</td>
<td>{esc(format_duration(plan.get("minutes", 0)))}</td>
<td>{esc(plan.get("max_devices", 1))}</td>
<td>{esc(plan.get("download_mbps", "0"))} Mbps</td>
<td>{esc(plan.get("upload_mbps", "0"))} Mbps</td>
<td class="dense-actions-col">
  <details class="dense-more plan-edit-details">
    <summary>编辑</summary>
    <form method="post" action="/admin/plan-edit-save" class="plan-edit-form">
      <input type="hidden" name="index" value="{index}">
      <p>套餐名称</p>
      <input name="name" value="{esc(plan.get("name", ""))}" required>
      <p>时长分钟</p>
      <input name="minutes" type="number" min="0" value="{esc(plan.get("minutes", 0))}">
      <p>允许设备数</p>
      <input name="max_devices" type="number" min="1" value="{esc(plan.get("max_devices", 1))}">
      <p>下载 Mbps</p>
      <input name="download_mbps" value="{esc(plan.get("download_mbps", "0"))}">
      <p>上传 Mbps</p>
      <input name="upload_mbps" value="{esc(plan.get("upload_mbps", "0"))}">
      <p>备注</p>
      <input name="note" value="{esc(plan.get("note", ""))}">
      <p><button type="submit" class="dense-mini-btn dense-good">保存套餐</button></p>
    </form>
  </details>

  <form method="post" action="/admin/plan-delete" onsubmit="return confirm('确认删除这个套餐？已有兑换码不受影响。')" style="display:inline">
    <input type="hidden" name="index" value="{index}">
    <button class="danger dense-mini-btn" type="submit">删除</button>
  </form>
</td>
</tr>
""")



        # VOUCHER_DISPLAY_GUARD_V1
        voucher_display_warning = ""
        voucher_fallback_rows = ""

        if len(all_vouchers) > 0 and shown_count == 0:
            voucher_display_warning = f"""
<div class="card" style="border:1px solid #facc15;background:#fffbeb">
<h2>显示提醒</h2>
<p>数据库里有 <b>{len(all_vouchers)}</b> 个兑换码，但当前筛选结果为 0。</p>
<p class="muted">可能原因：搜索条件、状态筛选、旧页面参数、或兑换码页面渲染异常。</p>
<p><a class="btn" href="/admin/vouchers">清空筛选并刷新</a></p>
</div>
"""

            fallback = []
            for raw_code, raw_voucher in sorted(all_vouchers.items()):
                try:
                    raw_status = voucher_status(raw_voucher)
                except Exception:
                    raw_status = "状态读取失败"

                try:
                    raw_remaining = remaining_text(raw_voucher)
                except Exception:
                    raw_remaining = "-"

                try:
                    raw_used = len(raw_voucher.get("devices", {}) or {}) if isinstance(raw_voucher, dict) else 0
                except Exception:
                    raw_used = 0

                try:
                    raw_max = raw_voucher.get("max_devices", 1) if isinstance(raw_voucher, dict) else 1
                except Exception:
                    raw_max = 1

                code_q = urllib.parse.quote(str(raw_code))
                note = ""
                plan = ""
                if isinstance(raw_voucher, dict):
                    note = str(raw_voucher.get("note", "") or "")
                    plan = str(raw_voucher.get("speed_profile_name", "") or "")

                fallback.append(f"""
<tr>
<td><code>{esc(raw_code)}</code></td>
<td>{esc(raw_status)}</td>
<td>{esc(raw_remaining)}</td>
<td>{raw_used}/{esc(raw_max)}</td>
<td>{esc(plan)}</td>
<td>{esc(note)}</td>
<td>
<a class="btn dense-mini-btn" href="/admin/voucher-detail?code={code_q}">详情</a>
<a class="btn dense-mini-btn" href="/admin/voucher-edit?code={code_q}">编辑</a>
</td>
</tr>
""")

            voucher_fallback_rows = f"""
<div class="card">
<h2>兜底兑换码列表</h2>
<p class="muted">这是备用显示模式，用来防止兑换码真实存在但主列表不显示。</p>
<table class="voucher-display-guard-table">
<tr><th>兑换码</th><th>状态</th><th>剩余</th><th>设备</th><th>套餐</th><th>备注</th><th>操作</th></tr>
{''.join(fallback)}
</table>
</div>
"""


        # VOUCHER_TOOLS_NO_EXPAND_UI_V6
        voucher_top_tools_html = f"""
<div class="card dense-list-card voucher-tools-no-expand-card">
<h2>兑换码操作</h2>
<p class="muted">紧凑操作模式：不用展开按钮，操作直接放在标题下面。</p>

<table class="voucher-dense-table voucher-tools-no-expand-table">
<tr>
<th>功能</th>
<th>操作</th>
</tr>

<tr>
<td class="voucher-tools-title-cell">
  <b>新增单个兑换码</b>
  <div class="dense-sub">手动添加指定兑换码</div>
</td>
<td>
  <form method="post" action="/admin/voucher-add" class="voucher-tools-direct-form">
    <div class="voucher-tools-direct-grid">
      <div>
        <p>兑换码</p>
        <input name="code" placeholder="例如 000381 / DAY001" required>
      </div>
      <div>
        <p>套餐</p>
        <select name="plan_index">{''.join(plan_options)}</select>
      </div>
      <div class="voucher-tools-submit-cell">
        <p>&nbsp;</p>
        <button type="submit" class="dense-mini-btn dense-good">新增兑换码</button>
      </div>
    </div>
  </form>
</td>
</tr>

<tr>
<td class="voucher-tools-title-cell">
  <b>批量生成兑换码</b>
  <div class="dense-sub">一次生成多个兑换码</div>
</td>
<td>
  <form method="post" action="/admin/voucher-generate" class="voucher-tools-direct-form">
    <div class="voucher-tools-direct-grid voucher-tools-direct-grid-6">
      <div>
        <p>数量</p>
        <input name="quantity" value="10" type="number" min="1" max="1000">
      </div>
      <div>
        <p>长度</p>
        <input name="length" value="6" type="number" min="3" max="24">
      </div>
      <div>
        <p>前缀</p>
        <input name="prefix" value="" placeholder="如 VIP-" type="text" style="width:100%">
      </div>
      <div>
        <p>模式</p>
        <select name="mode">
          <option value="numeric">纯数字</option>
          <option value="mixed">数字 + 字母</option>
        </select>
      </div>
      <div>
        <p>套餐</p>
        <select name="plan_index">{''.join(plan_options)}</select>
      </div>
      <div class="voucher-tools-submit-cell">
        <p>&nbsp;</p>
        <button type="submit" class="dense-mini-btn dense-good">批量生成</button>
      </div>
    </div>
  </form>
</td>
</tr>

<tr>
<td class="voucher-tools-title-cell">
  <b>自定义套餐管理</b>
  <div class="dense-sub">添加、编辑、删除套餐</div>
  <div class="dense-sub">当前 {len(plans)} 个套餐</div>
</td>
<td>
  <div class="voucher-tools-plan-direct">
    <div class="voucher-tools-plan-add-direct">
      <b>添加新套餐</b>
      <form method="post" action="/admin/plan-add" class="voucher-tools-direct-form">
        <div class="voucher-tools-direct-grid voucher-tools-direct-grid-6">
          <div>
            <p>名称</p>
            <input name="name" placeholder="例如 VIP / 1 Day 5M" required>
          </div>
          <div>
            <p>分钟</p>
            <input name="minutes" value="1440" type="number" min="0">
          </div>
          <div>
            <p>设备</p>
            <input name="max_devices" value="1" type="number" min="1">
          </div>
          <div>
            <p>下载</p>
            <input name="download_mbps" value="5">
          </div>
          <div>
            <p>上传</p>
            <input name="upload_mbps" value="2">
          </div>
          <div>
            <p>备注</p>
            <input name="note" placeholder="备注">
          </div>
          <div class="voucher-tools-submit-cell">
            <p>&nbsp;</p>
            <button type="submit" class="dense-mini-btn dense-good">添加套餐</button>
          </div>
        </div>
      </form>
    </div>

    <div class="voucher-tools-plan-list-direct">
      <b>已有套餐</b>
      <table class="voucher-dense-table voucher-plan-table voucher-tools-plan-direct-table">
        <tr>
          <th>套餐</th>
          <th>时长</th>
          <th>设备</th>
          <th>下载</th>
          <th>上传</th>
          <th>操作</th>
        </tr>
        {''.join(plan_rows) if plan_rows else '<tr><td colspan="6" class="muted">暂无套餐</td></tr>'}
      </table>
      <p class="muted">编辑套餐只影响以后新增/批量生成的兑换码，不会修改已经生成的兑换码。</p>
    </div>
  </div>
</td>
</tr>

<tr>
<td class="voucher-tools-title-cell">
  <b>导出未使用兑换码</b>
  <div class="dense-sub">导出 CSV，保留前导 0</div>
</td>
<td>
  <a class="btn dense-mini-btn dense-good" href="/admin/export-unused">立即导出未使用兑换码</a>
  <span class="dense-sub">当前未使用：{stats.get("unused", 0)} 个</span>
</td>
</tr>

<tr>
<td class="voucher-tools-title-cell">
  <b>打印兑换码卡片</b>
  <div class="dense-sub">生成排版好的打印卡片</div>
</td>
<td>
  <a class="btn dense-mini-btn dense-good" href="/admin/vouchers-print" target="_blank">批量打印未使用兑换码</a>
  <span class="dense-sub">自动生成一键登录二维码</span>
</td>
</tr>

<tr>
<td class="voucher-tools-title-cell">
  <b>删除过期兑换码</b>
  <div class="dense-sub">批量清理过期码</div>
</td>
<td>
  <form method="post" action="/admin/voucher-delete-expired" onsubmit="return confirm('确认批量删除所有已过期兑换码？永久码和使用中兑换码不会删除。')" class="voucher-tools-direct-form">
    <button class="danger dense-mini-btn" type="submit">删除过期兑换码</button>
    <span class="dense-sub">当前过期：{stats.get("expired", 0)} 个</span>
  </form>
</td>
</tr>

</table>
</div>
"""

        body = f"""
{voucher_display_warning}
{export_unused_notice}
<div class="card dense-top-card">
<h1>兑换码管理</h1>
<p class="muted">紧凑总览模式：一行一个兑换码，更方便观察整体状态。</p>
<div class="dense-stat-row">
<a class="dense-stat" href="/admin/vouchers?status=all&q={esc(urllib.parse.quote(search_text))}">总数<b>{stats.get("all", 0)}</b></a>
<a class="dense-stat" href="/admin/vouchers?status=unused&q={esc(urllib.parse.quote(search_text))}">未使用<b>{stats.get("unused", 0)}</b></a>
<a class="dense-stat export-unused-stat" href="/admin/export-unused">导出未使用<b>CSV</b></a>
<a class="dense-stat" href="/admin/vouchers?status=active&q={esc(urllib.parse.quote(search_text))}">使用中<b>{stats.get("active", 0)}</b></a>
<a class="dense-stat" href="/admin/vouchers?status=expired&q={esc(urllib.parse.quote(search_text))}">已过期<b>{stats.get("expired", 0)}</b></a>
<a class="dense-stat" href="/admin/vouchers?status=disabled&q={esc(urllib.parse.quote(search_text))}">已禁用<b>{stats.get("disabled", 0)}</b></a>
<a class="dense-stat" href="#">显示<b>{shown_count}</b></a>
</div>
</div>

{voucher_top_tools_html}

<div class="card dense-search-card">
<form method="get" action="/admin/vouchers" class="dense-search-form">
<input type="hidden" name="status" value="{esc(status_filter)}">
<input name="q" value="{esc(search_text)}" placeholder="搜索兑换码、套餐、备注、状态">
<button type="submit">搜索</button>
<a class="btn" href="/admin/vouchers">清空</a>
</form>
<div class="dense-filter-row">{filter_buttons}</div>
<div class="dense-tool-row">
<a class="btn" href="/admin/export-unused">导出未使用</a>
<a class="btn" href="/admin/vouchers-print?status={esc(status_filter)}&q={esc(urllib.parse.quote(search_text))}" target="_blank">打印当前筛选列表</a>
<form method="post" action="/admin/voucher-delete-expired" onsubmit="return confirm('确认批量删除所有已过期兑换码？永久码和使用中兑换码不会删除。')">
<button class="danger" type="submit">删除过期</button>
</form>
</div>
</div>

<div class="card dense-list-card">
<h2>兑换码列表</h2>
<p class="muted">筛选：{esc(filter_labels.get(status_filter, "全部"))}；搜索：{esc(search_text or "无")}；当前显示 {shown_count} 条。</p>
<div class="voucher-bulk-bar-v2">
  <button type="button" class="btn dense-mini-btn" onclick="wpVoucherSelectAllV2(true)">全选</button>
  <button type="button" class="btn dense-mini-btn" onclick="wpVoucherSelectAllV2(false)">取消选择</button>

  <form method="post" action="/admin/voucher-bulk-delete" id="voucherBulkDeleteFormV2" onsubmit="return wpVoucherBulkDeleteConfirmV2()">
    <input type="hidden" name="codes" id="voucherBulkDeleteCodesV2">
    <button class="danger dense-mini-btn" type="submit">批量删除所选</button>
  </form>

  <span class="muted">只删除当前列表中勾选的兑换码</span>
</div>

<table class="voucher-dense-table">
<tr>
<th class="dense-select-col"><input type="checkbox" onclick="wpVoucherSelectAllV2(this.checked)"></th>
<th>兑换码</th>
<th>状态</th>
<th>套餐 / 网速</th>
<th>设备 / 时长</th>
<th>到期 / 首次</th>
<th>备注</th>
<th>操作</th>
</tr>
{''.join(voucher_rows) if voucher_rows else '<tr><td colspan="8" class="muted">没有符合条件的兑换码</td></tr>'}
</table>

<script>
function wpVoucherSelectedCodesV2() {{
  var boxes = document.querySelectorAll('.voucher-select-box:checked');
  var codes = [];
  for (var i = 0; i < boxes.length; i++) {{
    codes.push(boxes[i].value);
  }}
  return codes;
}}

function wpVoucherSelectAllV2(checked) {{
  var boxes = document.querySelectorAll('.voucher-select-box');
  for (var i = 0; i < boxes.length; i++) {{
    boxes[i].checked = checked;
  }}
}}

function wpVoucherBulkDeleteConfirmV2() {{
  var codes = wpVoucherSelectedCodesV2();

  if (codes.length < 1) {{
    alert('请先选择要删除的兑换码');
    return false;
  }}

  document.getElementById('voucherBulkDeleteCodesV2').value = codes.join('\\n');

  return confirm('确认批量删除所选 ' + codes.length + ' 个兑换码？如果包含已使用兑换码，会踢掉绑定设备。');
}}
</script>
</div>

"""
        body = body + voucher_fallback_rows

        self.send_html(admin_page("兑换码管理", body))


    def show_admin_voucher_detail(self):
        db = load_db()
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = normalize_code(query.get("code", [""])[0])
        voucher = db.get("vouchers", {}).get(code)

        if not code or not voucher:
            self.send_html(admin_page("兑换码不存在", "<div class='card'><h1 class='bad'>兑换码不存在</h1><a class='btn' href='/admin/vouchers'>返回兑换码管理</a></div>"))
            return

        devices = db.get("devices", {})
        bound_devices = voucher.get("devices", {}) or {}

        status = voucher_status(voucher)
        used_count = len(bound_devices)
        max_devices = voucher.get("max_devices", 1)
        speed = f"{kbps_to_mbps(voucher.get('download_kbps', 0))} Mbps ↓ / {kbps_to_mbps(voucher.get('upload_kbps', 0))} Mbps ↑"
        code_q = urllib.parse.quote(str(code))

        rows = []
        for mac, bind_info in sorted(bound_devices.items()):
            device = devices.get(mac, {})
            hostname = device.get("hostname") or bind_info.get("hostname") or "Unknown Device"
            ip = device.get("ip") or bind_info.get("ip") or ""
            login_at = int(device.get("login_at", 0) or bind_info.get("login_at", 0) or 0)
            last_seen = int(device.get("last_seen", 0) or bind_info.get("last_seen", 0) or 0)
            expire_at = int(device.get("expire_at", 0) or voucher.get("expire_at", 0) or 0)
            online = bool(device.get("online", False))

            if expire_at > 0 and expire_at <= now():
                online = False

            if online:
                online_text = "<b class='ok'>认证有效</b>"
            else:
                online_text = "<b class='bad'>离线/无效</b>"

            remaining = "-"
            if online and expire_at == 0:
                remaining = "永久"
            elif online and expire_at > 0:
                seconds = max(0, expire_at - now())
                days = seconds // 86400
                hours = (seconds % 86400) // 3600
                mins = (seconds % 3600) // 60
                if days > 0:
                    remaining = f"{days}天 {hours}小时 {mins}分钟"
                elif hours > 0:
                    remaining = f"{hours}小时 {mins}分钟"
                else:
                    remaining = f"{mins}分钟"

            rows.append(f"""
<tr>
<td><b>{esc(hostname)}</b></td>
<td><code>{esc(mac)}</code></td>
<td>{esc(ip)}</td>
<td>{online_text}<br><span class="muted">剩余：{esc(remaining)}</span></td>
<td>{esc(format_time(login_at))}</td>
<td>{esc(format_time(last_seen))}</td>
<td>{esc("永久" if expire_at == 0 and online else format_time(expire_at))}</td>
<td>
<form method="post" action="/admin/voucher-device-unbind" onsubmit="return confirm('确认从这个兑换码解绑该设备？设备会被踢下线。')">
<input type="hidden" name="code" value="{esc(code)}">
<input type="hidden" name="mac" value="{esc(mac)}">
<button class="danger" type="submit">解绑设备</button>
</form>
</td>
</tr>
""")

        body = f"""
<div class="card">
<h1>兑换码绑定详情</h1>
<p>
<a class="btn" href="/admin/vouchers">返回兑换码管理</a>
<a class="btn" href="/admin/logs?voucher={code_q}">查看该兑换码日志</a>
</p>
<div class="grid">
<div class="stat">兑换码<b><code>{esc(code)}</code></b></div>
<div class="stat">状态<b>{esc(status)}</b></div>
<div class="stat">绑定设备<b>{used_count}/{esc(max_devices)}</b></div>
<div class="stat">剩余时间<b>{esc(remaining_text(voucher))}</b></div>
<div class="stat">套餐<b>{esc(voucher.get("speed_profile_name", ""))}</b></div>
<div class="stat">网速<b>{esc(speed)}</b></div>
<div class="stat">首次使用<b>{esc(format_time(voucher.get("first_used_at", 0)))}</b></div>
<div class="stat">到期时间<b>{esc(format_time(voucher.get("expire_at", 0)))}</b></div>
</div>
</div>

<div class="card">
<h2>绑定设备列表</h2>
<p class="muted">这里显示该兑换码已经绑定过的设备。解绑会删除绑定关系，并踢掉该设备当前认证放行和限速。</p>
<table class="voucher-device-detail-table">
<tr>
<th>设备名</th>
<th>MAC</th>
<th>IP</th>
<th>状态</th>
<th>登录时间</th>
<th>最后在线</th>
<th>到期时间</th>
<th>操作</th>
</tr>
{''.join(rows) if rows else '<tr><td colspan="8" class="muted">这个兑换码还没有绑定设备</td></tr>'}
</table>
</div>
"""
        self.send_html(admin_page("兑换码绑定详情", body))

    def admin_voucher_device_unbind(self):
        form = self.read_form()
        code = normalize_code(form.get("code", ""))
        mac = normalize_mac(form.get("mac", ""))
        db = load_db()

        voucher = db.get("vouchers", {}).get(code)
        if voucher and mac:
            if mac in voucher.get("devices", {}):
                del voucher["devices"][mac]

            device = db.get("devices", {}).get(mac)
            if device and normalize_code(device.get("voucher_code", "")) == code:
                device["online"] = False
                device["last_seen"] = now()
                device["voucher_code"] = ""

            save_db(db)
            nft_kick_device(mac)
            safe_qos_remove_device(mac)
            append_log("VOUCHER", f"兑换码 {code} 解绑设备 {mac}", voucher_code=code, mac=mac)
            append_admin_audit(self, "解绑兑换码设备", f"code={code} mac={mac}", voucher_code=code, mac=mac)

        self.redirect("/admin/voucher-detail?code=" + urllib.parse.quote(code))



    def show_admin_voucher_edit(self):
        db = load_db()
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = normalize_code(query.get("code", [""])[0])
        voucher = db.get("vouchers", {}).get(code)

        if not code or not voucher:
            self.send_html(admin_page("兑换码不存在", "<div class='card'><h1 class='bad'>兑换码不存在</h1><a class='btn' href='/admin/vouchers'>返回兑换码管理</a></div>"))
            return

        enabled_checked = " checked" if voucher.get("enabled", True) else ""
        minutes = int(voucher.get("minutes", 0) or 0)
        max_devices = int(voucher.get("max_devices", 1) or 1)
        download_mbps = kbps_to_mbps(voucher.get("download_kbps", 0))
        upload_mbps = kbps_to_mbps(voucher.get("upload_kbps", 0))
        if download_mbps == "Unlimited":
            download_mbps = "0"
        if upload_mbps == "Unlimited":
            upload_mbps = "0"

        status = voucher_status(voucher)
        used_count = len(voucher.get("devices", {}) or {})
        code_q = urllib.parse.quote(str(code))

        body = f"""
<div class="card">
<h1>编辑兑换码</h1>
<p>
<a class="btn" href="/admin/vouchers">返回兑换码管理</a>
<a class="btn" href="/admin/voucher-detail?code={code_q}">查看绑定设备</a>
<a class="btn" href="/admin/logs?voucher={code_q}">查看日志</a>
</p>
<div class="grid">
<div class="stat">兑换码<b><code>{esc(code)}</code></b></div>
<div class="stat">当前状态<b>{esc(status)}</b></div>
<div class="stat">已绑定设备<b>{used_count}/{esc(max_devices)}</b></div>
<div class="stat">剩余时间<b>{esc(remaining_text(voucher))}</b></div>
</div>
</div>

<div class="card">
<h2>编辑参数</h2>
<form method="post" action="/admin/voucher-edit-save">
<input type="hidden" name="code" value="{esc(code)}">

<div class="grid">
<div>
<p>备注</p>
<input name="note" value="{esc(voucher.get("note", ""))}" placeholder="例如 客户名 / 日期 / 用途">
</div>

<div>
<p>套餐名称</p>
<input name="speed_profile_name" value="{esc(voucher.get("speed_profile_name", ""))}" placeholder="例如 Day Plan 5M">
</div>

<div>
<p>时长分钟</p>
<input name="minutes" type="number" min="0" value="{minutes}">
<p class="muted">0 表示永久。</p>
</div>

<div>
<p>最大设备数</p>
<input name="max_devices" type="number" min="1" value="{max_devices}">
<p class="muted">如果小于已绑定数量，不会自动踢设备，只会限制新设备。</p>
</div>

<div>
<p>下载 Mbps</p>
<input name="download_mbps" value="{esc(download_mbps)}">
<p class="muted">0 表示不限速。</p>
</div>

<div>
<p>上传 Mbps</p>
<input name="upload_mbps" value="{esc(upload_mbps)}">
<p class="muted">0 表示不限速。</p>
</div>
</div>

<div class="card" style="box-shadow:none;background:#f8fafc">
<h3>高级选项</h3>
<label style="display:block;margin:8px 0">
<input type="checkbox" name="enabled" value="1"{enabled_checked}>
启用这个兑换码
</label>

<label style="display:block;margin:8px 0">
<input type="checkbox" name="apply_expire" value="1">
按新时长重新计算到期时间
</label>
<p class="muted">
说明：如果兑换码已经使用，勾选后会根据首次使用时间 + 新时长重新计算到期时间。
如果不勾选，只修改兑换码时长配置，不改变当前到期时间。
</p>
</div>

<p>
<button type="submit">保存修改</button>
<a class="btn" href="/admin/vouchers">取消</a>
</p>
</form>
</div>

<div class="card">
<h2>安全说明</h2>
<p class="muted">修改备注、套餐名、设备数、时长、速度不会删除设备绑定。</p>
<p class="muted">如果把兑换码改为禁用，系统会踢掉该兑换码已绑定设备，并清理限速。</p>
<p class="muted">如果修改限速后已有设备在线，建议到“限速模块”点击“重建在线设备限速”，让新速度立即生效。</p>
</div>
"""
        self.send_html(admin_page("编辑兑换码", body))

    def admin_voucher_edit_save(self):
        form = self.read_form()
        code = normalize_code(form.get("code", ""))
        db = load_db()
        voucher = db.get("vouchers", {}).get(code)

        if not code or not voucher:
            self.send_html(admin_page("保存失败", "<div class='card'><h1 class='bad'>兑换码不存在</h1><a class='btn' href='/admin/vouchers'>返回兑换码管理</a></div>"))
            return

        old_enabled = bool(voucher.get("enabled", True))

        try:
            minutes = max(0, int(form.get("minutes", voucher.get("minutes", 0)) or 0))
        except Exception:
            minutes = int(voucher.get("minutes", 0) or 0)

        try:
            max_devices = max(1, int(form.get("max_devices", voucher.get("max_devices", 1)) or 1))
        except Exception:
            max_devices = int(voucher.get("max_devices", 1) or 1)

        download_kbps = mbps_to_kbps(form.get("download_mbps", "0"))
        upload_kbps = mbps_to_kbps(form.get("upload_mbps", "0"))
        speed_profile_name = str(form.get("speed_profile_name", "") or "").strip() or "Default Plan"
        note = str(form.get("note", "") or "").strip()
        enabled = form.get("enabled", "") == "1"
        apply_expire = form.get("apply_expire", "") == "1"

        voucher["minutes"] = minutes
        voucher["max_devices"] = max_devices
        voucher["download_kbps"] = download_kbps
        voucher["upload_kbps"] = upload_kbps
        voucher["speed_profile_name"] = speed_profile_name
        voucher["note"] = note
        voucher["enabled"] = enabled

        if apply_expire:
            first_used_at = int(voucher.get("first_used_at", 0) or 0)
            if minutes == 0:
                voucher["expire_at"] = 0
            elif first_used_at > 0:
                voucher["expire_at"] = first_used_at + minutes * 60
            else:
                voucher["expire_at"] = 0

        bound_macs = set((voucher.get("devices", {}) or {}).keys())

        for mac, device in db.get("devices", {}).items():
            if normalize_code(device.get("voucher_code", "")) == code:
                bound_macs.add(mac)

        for mac in list(bound_macs):
            device = db.get("devices", {}).get(mac)
            if not device:
                continue

            device["download_kbps"] = download_kbps
            device["upload_kbps"] = upload_kbps
            device["speed_profile_name"] = speed_profile_name

            if apply_expire:
                device["expire_at"] = int(voucher.get("expire_at", 0) or 0)

        if old_enabled and not enabled:
            for mac in list(bound_macs):
                nft_kick_device(mac)
                safe_qos_remove_device(mac)
                if mac in db.get("devices", {}):
                    db["devices"][mac]["online"] = False
                    db["devices"][mac]["last_seen"] = now()

        save_db(db)
        append_log("VOUCHER", f"编辑兑换码 {code}", voucher_code=code)
        append_admin_audit(self, "编辑兑换码", f"code={code} minutes={minutes} max_devices={max_devices} down={download_kbps}kbps up={upload_kbps}kbps enabled={enabled}", voucher_code=code)

        body = f"""
<div class="card">
<h1 class="ok">保存成功</h1>
<p>兑换码 <code>{esc(code)}</code> 已更新。</p>
<p class="muted">如果修改了限速，并且该兑换码已有在线设备，建议到限速模块重建在线设备限速。</p>
<p>
<a class="btn" href="/admin/vouchers">返回兑换码管理</a>
<a class="btn" href="/admin/voucher-edit?code={esc(urllib.parse.quote(code))}">继续编辑</a>
<a class="btn" href="/admin/qos">打开限速模块</a>
</p>
</div>
"""
        self.send_html(admin_page("编辑成功", body))


    def show_export_unused(self):
        db = load_db()

        def csv_cell(value):
            text = str(value if value is not None else "")
            return '"' + text.replace('"', '""') + '"'

        def excel_text_cell(value):
            text = str(value if value is not None else "")
            text = text.replace('"', '""')
            return '"=""' + text + '"""'

        lines = ["Voucher Code,Duration Minutes,Device Limit,Download Mbps,Upload Mbps,Speed Plan,Note,Created Time"]

        for code, voucher in sorted(db.get("vouchers", {}).items()):
            if voucher.get("first_used_at", 0):
                continue
            if not voucher.get("enabled", True):
                continue

            lines.append(",".join([
                excel_text_cell(code),
                csv_cell(voucher.get("minutes", 0)),
                csv_cell(voucher.get("max_devices", 1)),
                csv_cell(kbps_to_mbps(voucher.get("download_kbps", 0))),
                csv_cell(kbps_to_mbps(voucher.get("upload_kbps", 0))),
                csv_cell(voucher.get("speed_profile_name", "")),
                csv_cell(voucher.get("note", "")),
                csv_cell(format_time(voucher.get("created_at", 0)))
            ]))

        csv_text = "\ufeff" + "\n".join(lines) + "\n"
        filename = "unused-vouchers-" + time.strftime("%Y%m%d-%H%M%S") + ".csv"
        content = csv_text.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

        append_log("VOUCHER", "导出未使用兑换码 CSV，保留前导零")


    def show_admin_vouchers_print(self):
        db = load_db()
        settings = load_settings()
        portal = settings.get("portal_page", {})
        title = portal.get("title", "WiFi Access")

        parsed = urllib.parse.urlparse(self.path)
        queries = urllib.parse.parse_qs(parsed.query)
        status_filter = queries.get("status", ["unused"])[0].strip()
        q = queries.get("q", [""])[0].strip().upper()

        vouchers_list = []
        for code, voucher in sorted(db.get("vouchers", {}).items(), key=lambda x: x[0]):
            if q and q not in code:
                continue

            used = bool(voucher.get("first_used_at", 0))
            enabled = bool(voucher.get("enabled", True))
            expired = False
            
            # calculate expired
            if not used:
                expire_at = int(voucher.get("expire_at", 0) or 0)
                if expire_at > 0 and expire_at <= now():
                    expired = True

            if status_filter == "unused" and (used or not enabled or expired):
                continue
            elif status_filter == "active" and (not used or expired):
                continue
            elif status_filter == "expired" and not expired:
                continue
            elif status_filter == "disabled" and enabled:
                continue

            vouchers_list.append(voucher)

        self.send_html(print_vouchers_page(vouchers_list, LAN_IP, title))


    def admin_plan_add(self):
        form = self.read_form()
        name = str(form.get("name", "")).strip()
        if not name:
            self.send_html(admin_page("添加失败", "<div class='card'><h1 class='bad'>套餐名称不能为空</h1><a class='btn' href='/admin/vouchers'>返回</a></div>"))
            return

        settings = load_settings()
        plans = settings.setdefault("speed_plans", [])
        plans.append({
            "name": name,
            "minutes": max(0, int(form.get("minutes", 1440) or 0)),
            "max_devices": max(1, int(form.get("max_devices", 1) or 1)),
            "download_mbps": str(form.get("download_mbps", "0")).strip() or "0",
            "upload_mbps": str(form.get("upload_mbps", "0")).strip() or "0",
            "note": str(form.get("note", "")).strip()
        })
        save_settings(settings)
        append_log("PLAN", f"新增套餐 {name}")
        self.redirect("/admin/vouchers")

    def admin_plan_delete(self):
        form = self.read_form()
        settings = load_settings()
        plans = settings.setdefault("speed_plans", [])
        try:
            index = int(form.get("index", -1))
        except Exception:
            index = -1

        if 0 <= index < len(plans):
            name = plans[index].get("name", "")
            del plans[index]
            save_settings(settings)
            append_log("PLAN", f"删除套餐 {name}")

        self.redirect("/admin/vouchers")

    def admin_plan_edit_save(self):
        form = self.read_form()

        try:
            index = int(form.get("index", -1))
        except Exception:
            index = -1

        name = str(form.get("name", "")).strip()
        if not name:
            self.send_html(admin_page("编辑失败", "<div class='card'><h1 class='bad'>套餐名称不能为空</h1><a class='btn' href='/admin/vouchers'>返回</a></div>"))
            return

        try:
            minutes = max(0, int(form.get("minutes", 1440) or 0))
        except Exception:
            minutes = 1440

        try:
            max_devices = max(1, int(form.get("max_devices", 1) or 1))
        except Exception:
            max_devices = 1

        download_mbps = str(form.get("download_mbps", "0")).strip() or "0"
        upload_mbps = str(form.get("upload_mbps", "0")).strip() or "0"
        note = str(form.get("note", "")).strip()

        settings = load_settings()
        plans = settings.setdefault("speed_plans", [])

        if not isinstance(plans, list):
            self.send_html(admin_page("编辑失败", "<div class='card'><h1 class='bad'>套餐数据结构异常</h1><a class='btn' href='/admin/vouchers'>返回</a></div>"))
            return

        if 0 <= index < len(plans):
            old_name = plans[index].get("name", "")
            plans[index] = {
                "name": name,
                "minutes": minutes,
                "max_devices": max_devices,
                "download_mbps": download_mbps,
                "upload_mbps": upload_mbps,
                "note": note
            }
            save_settings(settings)

            # PLAN_SPEED_SYNC_V1
            # When a plan is edited, synchronize matching vouchers/devices.
            # Special merge rule:
            #   "1 days", "1Day Plan", "1 Day Plan" are treated as the same plan
            #   and normalized to "1 Day Plan".
            try:
                def _plan_sync_norm(value):
                    return str(value or "").strip().lower().replace(" ", "")

                canonical_name = name
                plan_aliases = set([str(old_name or "").strip(), str(name or "").strip()])

                one_day_alias_norms = set(["1days", "1dayplan"])
                if _plan_sync_norm(old_name) in one_day_alias_norms or _plan_sync_norm(name) in one_day_alias_norms:
                    canonical_name = "1 Day Plan"
                    plan_aliases.update(["1 days", "1Day Plan", "1 Day Plan"])

                plan_aliases = set([x for x in plan_aliases if x])

                download_kbps = mbps_to_kbps(download_mbps)
                upload_kbps = mbps_to_kbps(upload_mbps)

                db = load_db()
                vouchers = db.setdefault("vouchers", {})
                devices = db.setdefault("devices", {})

                synced_vouchers = 0
                synced_devices = 0
                matched_codes = set()

                for voucher_code, voucher in vouchers.items():
                    if not isinstance(voucher, dict):
                        continue

                    voucher_plan_name = str(voucher.get("speed_profile_name", "") or "").strip()
                    if voucher_plan_name in plan_aliases:
                        voucher["speed_profile_name"] = canonical_name
                        voucher["download_kbps"] = download_kbps
                        voucher["upload_kbps"] = upload_kbps
                        synced_vouchers += 1
                        matched_codes.add(str(voucher_code))

                        voucher_devices = voucher.get("devices", {})
                        if isinstance(voucher_devices, dict):
                            for mac in voucher_devices.keys():
                                if mac in devices and isinstance(devices.get(mac), dict):
                                    device = devices[mac]
                                    device["speed_profile_name"] = canonical_name
                                    device["download_kbps"] = download_kbps
                                    device["upload_kbps"] = upload_kbps
                                    device["download_mbps"] = str(download_mbps)
                                    device["upload_mbps"] = str(upload_mbps)
                                    synced_devices += 1

                for mac, device in devices.items():
                    if not isinstance(device, dict):
                        continue

                    device_plan_name = str(device.get("speed_profile_name", "") or "").strip()
                    device_voucher_code = str(device.get("voucher_code", "") or "").strip()

                    if device_plan_name in plan_aliases or device_voucher_code in matched_codes:
                        device["speed_profile_name"] = canonical_name
                        device["download_kbps"] = download_kbps
                        device["upload_kbps"] = upload_kbps
                        device["download_mbps"] = str(download_mbps)
                        device["upload_mbps"] = str(upload_mbps)
                        synced_devices += 1

                save_db(db)

                try:
                    qos_restore_sessions()
                except Exception as qos_error:
                    append_log("QOS", f"套餐同步后重建在线限速失败：{qos_error}", result="FAIL")

                append_log(
                    "PLAN",
                    f"编辑套餐 {old_name} -> {canonical_name}，同步兑换码 {synced_vouchers} 个，设备 {synced_devices} 台"
                )
                try:
                    append_admin_audit(
                        self,
                        "编辑套餐并同步兑换码",
                        f"index={index} old={old_name} new={canonical_name} vouchers={synced_vouchers} devices={synced_devices}"
                    )
                except Exception:
                    pass
            except Exception as sync_error:
                append_log("PLAN", f"编辑套餐 {old_name} -> {name}，但同步兑换码失败：{sync_error}", result="FAIL")
                try:
                    append_admin_audit(self, "编辑套餐同步失败", f"index={index} old={old_name} new={name} error={sync_error}", result="FAIL")
                except Exception:
                    pass

        self.redirect("/admin/vouchers")


    def admin_voucher_add(self):
        form = self.read_form()
        code = normalize_code(form.get("code", ""))
        if len(code) < 3 or len(code) > 24:
            self.send_html(admin_page("新增失败", "<div class='card'><h1 class='bad'>兑换码长度必须是 3-24 位</h1><a class='btn' href='/admin/vouchers'>返回</a></div>"))
            return

        plan = get_plan_by_index(form.get("plan_index", 0))
        db = load_db()
        if code in db.get("vouchers", {}):
            self.send_html(admin_page("新增失败", "<div class='card'><h1 class='bad'>兑换码已存在</h1><a class='btn' href='/admin/vouchers'>返回</a></div>"))
            return

        db["vouchers"][code] = create_voucher_record(code, plan.get("minutes", 1440), plan.get("max_devices", 1), plan.get("download_mbps", 0), plan.get("upload_mbps", 0), plan.get("name", "Default Plan"), plan.get("note", ""))
        save_db(db)
        append_log("VOUCHER", f"新增兑换码 {code}", voucher_code=code)
        self.redirect("/admin/vouchers")

    def admin_voucher_generate(self):
        form = self.read_form()
        quantity = max(1, min(1000, int(form.get("quantity", 10))))
        length = max(3, min(24, int(form.get("length", 6))))
        prefix = str(form.get("prefix", "") or "").strip().upper()
        mode = form.get("mode", "numeric")
        plan = get_plan_by_index(form.get("plan_index", 0))

        db = load_db()
        created = []
        for _ in range(quantity):
            code = generate_voucher_code(length, mode, prefix, db["vouchers"])
            db["vouchers"][code] = create_voucher_record(code, plan.get("minutes", 1440), plan.get("max_devices", 1), plan.get("download_mbps", 0), plan.get("upload_mbps", 0), plan.get("name", "Default Plan"), plan.get("note", ""))
            created.append(code)

        save_db(db)
        append_log("VOUCHER", f"批量生成 {len(created)} 个兑换码")
        body = f"""
<div class='card'>
<h1 class='ok'>批量生成成功</h1>
<p>已生成 {len(created)} 个兑换码，套餐：{esc(plan.get("name", "Default Plan"))}</p>
<textarea style='width:100%;height:260px;font-family:monospace'>{esc(chr(10).join(created))}</textarea>
<p><a class='btn' href='/admin/vouchers'>返回兑换码管理</a></p>
</div>
"""
        self.send_html(admin_page("批量生成成功", body))

    def admin_voucher_reset(self):
        form = self.read_form()
        code = normalize_code(form.get("code", ""))
        db = load_db()
        voucher = db.get("vouchers", {}).get(code)
        if voucher:
            voucher["first_used_at"] = 0
            voucher["expire_at"] = 0
            for mac in list(voucher.get("devices", {}).keys()):
                nft_kick_device(mac)
                safe_qos_remove_device(mac)
                if mac in db.get("devices", {}):
                    db["devices"][mac]["online"] = False
            voucher["devices"] = {}
            save_db(db)
            append_log("VOUCHER", f"重置兑换码 {code}", voucher_code=code)
            append_admin_audit(self, "重置兑换码", f"code={code}", voucher_code=code)
        self.redirect("/admin/vouchers")

    def admin_voucher_extend(self):
        form = self.read_form()
        code = normalize_code(form.get("code", ""))
        add_minutes = max(1, int(form.get("minutes", 0)))
        db = load_db()
        voucher = db.get("vouchers", {}).get(code)
        if voucher and int(voucher.get("minutes", 0)) != 0:
            current_expire = int(voucher.get("expire_at", 0))
            base = max(now(), current_expire)
            voucher["expire_at"] = base + add_minutes * 60
            save_db(db)
            append_log("VOUCHER", f"兑换码 {code} 延长 {add_minutes} 分钟", voucher_code=code)
            append_admin_audit(self, "延长兑换码", f"code={code} add_minutes={add_minutes}", voucher_code=code)
        self.redirect("/admin/vouchers")

    def admin_voucher_toggle(self):
        form = self.read_form()
        code = normalize_code(form.get("code", ""))
        db = load_db()
        voucher = db.get("vouchers", {}).get(code)
        if voucher:
            voucher["enabled"] = not voucher.get("enabled", True)
            if not voucher.get("enabled", True):
                for mac in list(voucher.get("devices", {}).keys()):
                    nft_kick_device(mac)
                    if mac in db.get("devices", {}):
                        db["devices"][mac]["online"] = False
            save_db(db)
            append_log("VOUCHER", f"切换兑换码启用状态 {code}", voucher_code=code)
            append_admin_audit(self, "切换兑换码启用状态", f"code={code} enabled={voucher.get('enabled', True)}", voucher_code=code)
        self.redirect("/admin/vouchers")


    def admin_voucher_bulk_delete(self):
        form = self.read_form()
        raw_codes = str(form.get("codes", "") or "")

        codes = []
        seen = set()

        for part in raw_codes.replace("\r", "\n").replace(",", "\n").split("\n"):
            code = normalize_code(part)
            if code and code not in seen:
                seen.add(code)
                codes.append(code)

        db = load_db()
        deleted = []
        kicked_devices = 0

        for code in codes:
            if code not in db.get("vouchers", {}):
                continue

            voucher = db["vouchers"][code]

            for mac in list(voucher.get("devices", {}).keys()):
                try:
                    nft_kick_device(mac)
                except Exception:
                    pass

                try:
                    safe_qos_remove_device(mac)
                except Exception:
                    pass

                if mac in db.get("devices", {}):
                    db["devices"][mac]["online"] = False
                    db["devices"][mac]["last_seen"] = now()
                    db["devices"][mac]["voucher_code"] = ""

                kicked_devices += 1

            del db["vouchers"][code]
            deleted.append(code)

        if deleted:
            # BULK_DELETE_INTENTIONAL_SAVE_V1
            # Admin explicitly selected vouchers for batch deletion.
            # Save directly after backup, otherwise save_db shrink guard may block
            # intentional large deletions such as 182 -> 27.
            import os
            import shutil
            import time as _time

            backup_name = "bulk-delete-intentional-" + _time.strftime("%Y%m%d-%H%M%S")
            backup_dir = "/etc/wifiportal/admin-backups/" + backup_name
            os.makedirs(backup_dir, exist_ok=True)
            try:
                shutil.copy2(DB_FILE, os.path.join(backup_dir, "vouchers.json.before-bulk-delete.bak"))
                if os.path.exists(DB_FILE + ".last-good"):
                    shutil.copy2(DB_FILE + ".last-good", os.path.join(backup_dir, "vouchers.json.last-good.before-bulk-delete.bak"))
            except Exception:
                pass

            db.setdefault("meta", {})
            db["meta"]["updated_at"] = now()
            db["meta"]["last_bulk_delete_backup"] = backup_dir
            db["meta"]["last_bulk_delete_count"] = len(deleted)

            save_json(DB_FILE, db)

            # After an intentional admin deletion, refresh last-good to the new valid database.
            # Otherwise future normal saves may still compare against the old larger baseline.
            try:
                save_json(DB_FILE + ".last-good", db)
            except Exception:
                pass

            append_log("VOUCHER", f"批量删除所选兑换码 {len(deleted)} 个，备份 {backup_dir}")
            try:
                append_admin_audit(self, "批量删除所选兑换码", f"count={len(deleted)} backup={backup_dir} codes={','.join(deleted[:30])}")
            except Exception:
                pass

        body = f"""
<div class="card">
<h1 class="ok">批量删除完成</h1>
<p>已删除 <b>{len(deleted)}</b> 个兑换码。</p>
<p>处理绑定设备 <b>{kicked_devices}</b> 台。</p>
<p class="muted">没有勾选的兑换码不会受到影响。</p>
<p><a class="btn" href="/admin/vouchers">返回兑换码管理</a></p>
</div>
"""
        self.send_html(admin_page("批量删除所选兑换码", body))

    def admin_voucher_delete(self):
        form = self.read_form()
        code = normalize_code(form.get("code", ""))
        db = load_db()
        if code in db.get("vouchers", {}):
            voucher = db["vouchers"][code]
            for mac in list(voucher.get("devices", {}).keys()):
                nft_kick_device(mac)
                safe_qos_remove_device(mac)
                if mac in db.get("devices", {}):
                    db["devices"][mac]["online"] = False
            del db["vouchers"][code]
            save_db(db)
            append_log("VOUCHER", f"删除兑换码 {code}", voucher_code=code)
            append_admin_audit(self, "删除兑换码", f"code={code}", voucher_code=code)
        self.redirect("/admin/vouchers")

    def admin_voucher_delete_expired(self):
        # DELETE_EXPIRED_SAFE_UNUSED_ONLY_V1
        # Only delete expired vouchers that have never bound any device.
        # Permanent vouchers are kept. Used/connected/history vouchers are kept.
        import os
        import shutil
        import time as _time

        backup_name = "delete-expired-safe-" + _time.strftime("%Y%m%d-%H%M%S")
        backup_dir = "/etc/wifiportal/admin-backups/" + backup_name
        try:
            os.makedirs(backup_dir, exist_ok=True)
            shutil.copy2(DB_FILE, os.path.join(backup_dir, "vouchers.json.bak"))
        except Exception as error:
            body = f"""
<div class="card">
<h1 class="bad">删除失败</h1>
<p>备份数据库失败：{esc(str(error))}</p>
<p><a class="btn" href="/admin/vouchers">返回兑换码管理</a></p>
</div>
"""
            self.send_html(admin_page("删除失败", body))
            return

        try:
            db = load_db()
            vouchers = db.setdefault("vouchers", {})
            deleted = []
            skipped_used = []
            skipped_permanent = []
            skipped_not_expired = []

            for code, voucher in list(vouchers.items()):
                if not isinstance(voucher, dict):
                    continue

                try:
                    minutes = int(voucher.get("minutes", 0) or 0)
                except Exception:
                    minutes = 0

                if minutes == 0:
                    skipped_permanent.append(code)
                    continue

                if voucher_status(voucher) != "已过期":
                    skipped_not_expired.append(code)
                    continue

                devices = voucher.get("devices", {})
                used_count = len(devices) if isinstance(devices, dict) else 0

                # Keep all vouchers that have device history/bindings.
                # This matches the UI promise: 使用中兑换码不会删除.
                if used_count > 0:
                    skipped_used.append(code)
                    continue

                deleted.append(code)
                del vouchers[code]

            # This is an intentional admin deletion after backup.
            # Use save_json directly to avoid false "suspicious shrink" blocks.
            db.setdefault("meta", {})
            db["meta"]["updated_at"] = now()
            db["meta"]["last_delete_expired_backup"] = backup_dir
            save_json(DB_FILE, db)

            try:
                save_json(DB_FILE + ".last-good", db)
            except Exception:
                pass

            append_log("VOUCHER", "安全删除过期未使用兑换码 " + str(len(deleted)) + " 个，跳过已使用 " + str(len(skipped_used)) + " 个")
            append_admin_audit(
                self,
                "安全删除过期兑换码",
                "deleted=" + str(len(deleted)) + " skipped_used=" + str(len(skipped_used)) + " backup=" + backup_dir
            )

            body = f"""
<div class="card">
<h1 class="ok">删除完成</h1>
<p>已删除过期且未使用兑换码：<b>{len(deleted)}</b> 个。</p>
<p>跳过已使用/有设备记录的过期兑换码：<b>{len(skipped_used)}</b> 个。</p>
<p>跳过永久兑换码：<b>{len(skipped_permanent)}</b> 个。</p>
<p>备份目录：<code>{esc(backup_dir)}</code></p>
<p><a class="btn" href="/admin/vouchers">返回兑换码管理</a></p>
</div>
"""
            self.send_html(admin_page("安全删除过期兑换码", body))

        except Exception as error:
            append_log("VOUCHER", "安全删除过期兑换码失败 " + str(error), result="FAIL")
            body = f"""
<div class="card">
<h1 class="bad">删除失败</h1>
<p>{esc(str(error))}</p>
<p>数据库已提前备份：<code>{esc(backup_dir)}</code></p>
<p><a class="btn" href="/admin/vouchers">返回兑换码管理</a></p>
</div>
"""
            self.send_html(admin_page("删除失败", body))

    def show_admin_devices_placeholder(self):
        cleanup_expired_and_firewall()
        db = load_db()
        devices = db.get("devices", {})

        rows = []
        for mac, device in sorted(devices.items()):
            online = bool(device.get("online"))
            expire_at = int(device.get("expire_at", 0) or 0)
            if expire_at > 0 and expire_at <= now():
                online = False

            if not online:
                status = "离线/未认证"
            else:
                status = "在线"

            if expire_at == 0 and online:
                remaining = "永久"
            elif expire_at > 0 and online:
                seconds = max(0, expire_at - now())
                remaining = f"{seconds // 3600}小时 {(seconds % 3600) // 60}分钟"
            else:
                remaining = "-"

            speed = f"{esc(device.get('download_mbps', '-'))} ↓ / {esc(device.get('upload_mbps', '-'))} ↑ Mbps"

            rows.append(f"""
<tr>
<td>{esc(device.get("hostname", "Unknown Device"))}</td>
<td><code>{esc(mac)}</code></td>
<td>{esc(device.get("ip", ""))}</td>
<td><code>{esc(device.get("voucher_code", ""))}</code></td>
<td>{speed}<br><span class="muted">{esc(device.get("speed_profile_name", ""))}</span></td>
<td>{esc(format_time(device.get("login_at", 0)))}</td>
<td>{esc("永久" if expire_at == 0 and online else format_time(expire_at))}</td>
<td>{esc(remaining)}</td>
<td>{esc(status)}</td>
<td>
<form method="post" action="/admin/device-kick" style="display:inline">
<input type="hidden" name="mac" value="{esc(mac)}">
<button type="submit">踢下线</button>
</form>
<form method="post" action="/admin/device-unbind" style="display:inline" onsubmit="return confirm('确认解绑这个设备？')">
<input type="hidden" name="mac" value="{esc(mac)}">
<button class="danger" type="submit">解绑</button>
</form>
<form method="post" action="/admin/blacklist-add" style="display:inline" onsubmit="return confirm('确认加入黑名单？')">
<input type="hidden" name="mac" value="{esc(mac)}">
<input type="hidden" name="device_name" value="{esc(device.get("hostname", ""))}">
<input type="hidden" name="reason" value="Blocked from online devices">
<button class="danger" type="submit">拉黑</button>
</form>
</td>
</tr>
""")

        body = f"""
<div class="card">
<h1>在线 / 历史设备</h1>
<p class="muted">这里显示已经认证过或白名单允许过的设备。启用防火墙拦截后，踢下线会同时清理防火墙放行。</p>
</div>

<div class="card">
<table>
<tr>
<th>设备名</th>
<th>MAC</th>
<th>IP</th>
<th>兑换码</th>
<th>套餐网速</th>
<th>登录时间</th>
<th>到期时间</th>
<th>剩余时间</th>
<th>状态</th>
<th>操作</th>
</tr>
{''.join(rows) if rows else '<tr><td colspan="10" class="muted">暂无设备记录</td></tr>'}
</table>
</div>
"""
        self.send_html(admin_page("在线设备", body))


    def admin_device_kick(self):
        # ADMIN_DEVICE_KICK_STRONG_V1
        form = self.read_form()
        mac = normalize_mac(form.get("mac", ""))
        db = load_db()

        ip = ""
        if mac in db.get("devices", {}) and isinstance(db["devices"].get(mac), dict):
            ip = str(db["devices"][mac].get("ip", "") or "")
            db["devices"][mac]["online"] = False
            db["devices"][mac]["last_seen"] = now()
            db["devices"][mac]["blocked_reason"] = "admin_kicked"

        for voucher in db.get("vouchers", {}).values():
            if not isinstance(voucher, dict):
                continue
            if mac in voucher.get("devices", {}):
                try:
                    voucher["devices"][mac]["online"] = False
                    voucher["devices"][mac]["last_seen"] = now()
                except Exception:
                    pass

        save_db(db)

        nft_kick_device(mac)
        safe_qos_remove_device(mac)

        # Try to clear existing conntrack flows so current connections stop faster.
        if ip:
            for cmd in [
                ["/usr/sbin/conntrack", "-D", "-s", ip],
                ["/usr/sbin/conntrack", "-D", "-d", ip],
                ["conntrack", "-D", "-s", ip],
                ["conntrack", "-D", "-d", ip],
            ]:
                try:
                    run_command(cmd)
                except Exception:
                    pass

        append_log("DEVICE", f"强制踢设备下线 {mac} ip={ip}", mac=mac)
        self.redirect("/admin/devices")

    def admin_device_unbind(self):
        form = self.read_form()
        mac = normalize_mac(form.get("mac", ""))
        db = load_db()

        if mac in db.get("devices", {}):
            del db["devices"][mac]

        for voucher in db.get("vouchers", {}).values():
            if mac in voucher.get("devices", {}):
                del voucher["devices"][mac]

        save_db(db)
        nft_kick_device(mac)
        safe_qos_remove_device(mac)
        append_log("DEVICE", f"解绑设备 {mac}", mac=mac)
        self.redirect("/admin/devices")

    def show_admin_whitelist(self):
        db = load_db()
        device_options = build_device_mac_options(db)
        rows = []
        for mac, item in sorted(db.get("whitelist", {}).items()):
            rows.append(f"""
<tr>
<td><code>{esc(mac)}</code></td>
<td>{esc(item.get("device_name", ""))}</td>
<td>{esc(item.get("note", ""))}</td>
<td>{esc(format_time(item.get("created_at", 0)))}</td>
<td>
<form method="post" action="/admin/whitelist-delete" onsubmit="return confirm('确认删除这个白名单设备？')">
<input type="hidden" name="mac" value="{esc(mac)}">
<button class="danger" type="submit">删除</button>
</form>
</td>
</tr>
""")

        body = f"""
<div class="card">
<h1>白名单</h1>
<p class="muted">白名单设备不需要兑换码，后续启用认证拦截后会直接允许上网。黑名单优先级高于白名单。</p>
</div>

<div class="card">
<h2>添加白名单设备</h2>
<form method="post" action="/admin/whitelist-add">
<p>设备 MAC</p>
<input name="mac" list="whitelist-device-macs" placeholder="可以手动输入，也可以从在线/历史设备选择" required>
<datalist id="whitelist-device-macs">
{device_options}
</datalist>
<p class="muted">可直接输入 MAC，也可以点击输入框从在线/历史设备中选择。</p>
<p>设备名</p>
<input name="device_name" placeholder="老板手机 / 收银机 / 监控">
<p>备注</p>
<input name="note" placeholder="说明">
<p><button type="submit">添加白名单</button></p>
</form>
</div>

<div class="card">
<h2>白名单列表</h2>
<table>
<tr><th>MAC</th><th>设备名</th><th>备注</th><th>创建时间</th><th>操作</th></tr>
{''.join(rows) if rows else '<tr><td colspan="5" class="muted">暂无白名单设备</td></tr>'}
</table>
</div>
"""
        self.send_html(admin_page("白名单", body))

    def show_admin_blacklist(self):
        db = load_db()
        device_options = build_device_mac_options(db)
        rows = []
        for mac, item in sorted(db.get("blacklist", {}).items()):
            rows.append(f"""
<tr>
<td><code>{esc(mac)}</code></td>
<td>{esc(item.get("device_name", ""))}</td>
<td>{esc(item.get("reason", ""))}</td>
<td>{esc(format_time(item.get("created_at", 0)))}</td>
<td>
<form method="post" action="/admin/blacklist-delete" onsubmit="return confirm('确认移出黑名单？')">
<input type="hidden" name="mac" value="{esc(mac)}">
<button type="submit">移出黑名单</button>
</form>
</td>
</tr>
""")

        body = f"""
<div class="card">
<h1>黑名单</h1>
<p class="muted">黑名单设备即使输入正确兑换码也会被拒绝。黑名单优先级最高。</p>
</div>

<div class="card">
<h2>添加黑名单设备</h2>
<form method="post" action="/admin/blacklist-add">
<p>设备 MAC</p>
<input name="mac" list="blacklist-device-macs" placeholder="可以手动输入，也可以从在线/历史设备选择" required>
<datalist id="blacklist-device-macs">
{device_options}
</datalist>
<p class="muted">可直接输入 MAC，也可以点击输入框从在线/历史设备中选择。</p>
<p>设备名</p>
<input name="device_name" placeholder="设备名称">
<p>拉黑原因</p>
<input name="reason" placeholder="恶意尝试 / 欠费 / 禁止接入">
<p><button class="danger" type="submit">加入黑名单</button></p>
</form>
</div>

<div class="card">
<h2>黑名单列表</h2>
<table>
<tr><th>MAC</th><th>设备名</th><th>原因</th><th>创建时间</th><th>操作</th></tr>
{''.join(rows) if rows else '<tr><td colspan="5" class="muted">暂无黑名单设备</td></tr>'}
</table>
</div>
"""
        self.send_html(admin_page("黑名单", body))

    def show_admin_security(self):
        db = load_db()
        settings = load_settings()
        security = settings.get("security", {})
        locks = db.get("security_locks", {})

        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        sort_by = str(query.get("sort", ["last_failed"])[0] or "last_failed").strip()
        if sort_by not in ["key", "mac", "ip", "failed", "status", "remain", "last_failed", "reason"]:
            sort_by = "last_failed"

        sort_dir = str(query.get("dir", ["desc"])[0] or "desc").strip()
        if sort_dir not in ["asc", "desc"]:
            sort_dir = "desc"

        def security_lock_values(key, item):
            if not isinstance(item, dict):
                item = {}

            try:
                unlock_at = int(item.get("unlock_at", 0) or 0)
            except Exception:
                unlock_at = 0

            try:
                failed_count = int(item.get("failed_count", 0) or 0)
            except Exception:
                failed_count = 0

            try:
                last_failed_at = int(item.get("last_failed_at", 0) or 0)
            except Exception:
                last_failed_at = 0

            remain = max(0, unlock_at - now())
            locked = 1 if remain > 0 else 0

            return {
                "key": str(key),
                "mac": str(item.get("mac", "") or ""),
                "ip": str(item.get("ip", "") or ""),
                "failed": failed_count,
                "status": locked,
                "remain": remain,
                "last_failed": last_failed_at,
                "reason": str(item.get("reason", "") or ""),
            }

        def security_sort_key(entry):
            key, item = entry
            values = security_lock_values(key, item)
            primary = values.get(sort_by, "")
            return (primary, values.get("last_failed", 0), values.get("failed", 0), str(key))

        reverse_sort = sort_dir == "desc"

        def security_sort_link(field, label):
            next_dir = "asc"
            marker = ""
            if sort_by == field:
                if sort_dir == "asc":
                    next_dir = "desc"
                    marker = " ▲"
                else:
                    next_dir = "asc"
                    marker = " ▼"

            return (
                '<a class="security-sort-link" href="/admin/security?sort='
                + urllib.parse.quote(field)
                + '&dir='
                + urllib.parse.quote(next_dir)
                + '">'
                + esc(label + marker)
                + '</a>'
            )

        rows = []
        for key, item in sorted(locks.items(), key=security_sort_key, reverse=reverse_sort):
            if not isinstance(item, dict):
                item = {}
            rows.append(f"""
<tr>
<td><code>{esc(key)}</code></td>
<td>{esc(item.get("mac", ""))}</td>
<td>{esc(item.get("ip", ""))}</td>
<td>{esc(item.get("failed_count", 0))}</td>
<td>{esc(lock_status_text(item))}</td>
<td>
  <span class="security-lock-countdown" data-unlock-at="{int(item.get("unlock_at", 0) or 0)}">
    {esc(lock_remaining_text(item))}
  </span>
</td>
<td>{esc(format_time(item.get("last_failed_at", 0)))}</td>
<td>{esc(item.get("reason", ""))}</td>
<td>
<form method="post" action="/admin/security-unlock">
<input type="hidden" name="key" value="{esc(key)}">
<button type="submit">解锁/清除</button>
</form>
</td>
</tr>
""")

        enabled_checked = "checked" if security.get("enable_brute_force_protection", True) else ""
        lock_message_value = security.get("lock_message", "Too many failed attempts. Please try again in {remain}.")
        lock_message_preview = str(lock_message_value).replace("{remain}", "2m 5s")
        body = f"""
<div class="card">
<h1>安全锁定</h1>
<div class="grid">
<div class="stat">防暴力猜码<b>{'已启用' if security.get('enable_brute_force_protection', True) else '未启用'}</b></div>
<div class="stat">最大失败次数<b>{esc(security.get('max_failed_attempts', 5))}</b></div>
<div class="stat">锁定时间<b>{esc(security.get('lock_seconds', 300))} 秒</b></div>
<div class="stat">当前记录<b>{len(locks)}</b></div>
</div>
</div>

<div class="card">
<h2>锁定设置</h2>
<form method="post" action="/admin/security-save">
<label><input type="checkbox" name="enable_brute_force_protection" value="1" {enabled_checked}> 启用防暴力猜码锁定</label>
<p>最大失败次数</p>
<input name="max_failed_attempts" type="number" min="1" max="100" value="{esc(security.get('max_failed_attempts', 5))}">
<p>锁定时间，单位：秒</p>
<input name="lock_seconds" type="number" min="10" max="86400" value="{esc(security.get('lock_seconds', 300))}">
<p>客户端锁定提示语</p>
<textarea name="lock_message" style="min-height:90px">{esc(lock_message_value)}</textarea>
<p class="muted">可以使用 {{remain}} 表示剩余锁定时间，例如：Too many failed attempts. Please try again in {{remain}}.</p>
<p><button type="submit">保存安全设置</button></p>
</form>
</div>

<div class="card">
<h2>客户端弹窗提示预览</h2>
<p class="muted">下面是用户设备被锁定时看到的提示示例，剩余时间示例为 2m 5s。</p>
<div class="info">{esc(lock_message_preview)}</div>
</div>

<div class="card">
<h2>锁定 / 失败记录</h2>
<p class="muted">点击表头可排序；再次点击同一个表头可切换正序 / 倒序。当前排序：{esc(sort_by)} / {esc(sort_dir)}</p>
<style>
.security-sort-link {{
  color:#0f172a !important;
  text-decoration:none !important;
  font-weight:900 !important;
  display:inline-block !important;
  white-space:nowrap !important;
}}
.security-sort-link:hover {{
  text-decoration:underline !important;
}}
</style>
<form method="post" action="/admin/security-clear-all" onsubmit="return confirm('确认清空所有安全锁定和失败次数？')">
<button class="danger" type="submit">清空所有失败记录</button>
</form>
<table>
<tr>
<th>{security_sort_link("key", "识别键")}</th>
<th>{security_sort_link("mac", "MAC")}</th>
<th>{security_sort_link("ip", "IP")}</th>
<th>{security_sort_link("failed", "失败次数")}</th>
<th>{security_sort_link("status", "状态")}</th>
<th>{security_sort_link("remain", "剩余锁定")}</th>
<th>{security_sort_link("last_failed", "最后失败")}</th>
<th>{security_sort_link("reason", "原因")}</th>
<th>操作</th>
</tr>
{''.join(rows) if rows else '<tr><td colspan="9" class="muted">暂无失败记录</td></tr>'}
</table>
</div>

<script>
(function() {{
  function formatRemain(unlockAt) {{
    var nowSec = Math.floor(Date.now() / 1000);
    var remain = Math.floor(unlockAt - nowSec);

    if (!unlockAt || remain <= 0) {{
      return '-';
    }}

    var hours = Math.floor(remain / 3600);
    var minutes = Math.floor((remain % 3600) / 60);
    var seconds = remain % 60;

    if (hours > 0) {{
      return hours + 'h ' + minutes + 'm ' + seconds + 's';
    }}
    if (minutes > 0) {{
      return minutes + 'm ' + seconds + 's';
    }}
    return seconds + 's';
  }}

  function wpSecurityLockCountdownTick() {{
    var items = document.querySelectorAll('.security-lock-countdown');
    for (var i = 0; i < items.length; i++) {{
      var el = items[i];
      var unlockAt = parseInt(el.getAttribute('data-unlock-at') || '0', 10);
      el.textContent = formatRemain(unlockAt);
    }}
  }}

  wpSecurityLockCountdownTick();
  setInterval(wpSecurityLockCountdownTick, 1000);
}})();
</script>
"""
        self.send_html(admin_page("安全锁定", body))

    def admin_whitelist_add(self):
        form = self.read_form()
        mac = normalize_mac(form.get("mac", ""))
        if not mac:
            self.send_html(admin_page("添加失败", "<div class='card'><h1 class='bad'>MAC 地址格式错误</h1><a class='btn' href='/admin/whitelist'>返回</a></div>"))
            return
        db = load_db()
        db.setdefault("whitelist", {})[mac] = {
            "mac": mac,
            "device_name": form.get("device_name", ""),
            "note": form.get("note", ""),
            "created_at": now()
        }
        save_db(db)
        nft_add_whitelist(mac)
        append_log("WHITELIST", f"添加白名单 {mac}", mac=mac)
        self.redirect("/admin/whitelist")

    def admin_whitelist_delete(self):
        form = self.read_form()
        mac = normalize_mac(form.get("mac", ""))
        db = load_db()
        if mac in db.get("whitelist", {}):
            del db["whitelist"][mac]
            save_db(db)
            nft_delete_whitelist(mac)
            append_log("WHITELIST", f"删除白名单 {mac}", mac=mac)
        self.redirect("/admin/whitelist")

    def admin_blacklist_add(self):
        form = self.read_form()
        mac = normalize_mac(form.get("mac", ""))
        if not mac:
            self.send_html(admin_page("添加失败", "<div class='card'><h1 class='bad'>MAC 地址格式错误</h1><a class='btn' href='/admin/blacklist'>返回</a></div>"))
            return
        db = load_db()
        db.setdefault("blacklist", {})[mac] = {
            "mac": mac,
            "device_name": form.get("device_name", ""),
            "reason": form.get("reason", ""),
            "created_at": now()
        }
        save_db(db)
        nft_add_blacklist(mac)
        append_log("BLACKLIST", f"添加黑名单 {mac}", mac=mac)
        self.redirect("/admin/blacklist")

    def admin_blacklist_delete(self):
        form = self.read_form()
        mac = normalize_mac(form.get("mac", ""))
        db = load_db()
        if mac in db.get("blacklist", {}):
            del db["blacklist"][mac]
            save_db(db)
            nft_delete_blacklist(mac)
            append_log("BLACKLIST", f"移出黑名单 {mac}", mac=mac)
        self.redirect("/admin/blacklist")

    def admin_security_save(self):
        form = self.read_form()
        settings = load_settings()
        security = settings.setdefault("security", {})

        security["enable_brute_force_protection"] = form.get("enable_brute_force_protection", "") == "1"

        try:
            max_failed = int(form.get("max_failed_attempts", 5))
        except Exception:
            max_failed = 5
        if max_failed < 1:
            max_failed = 1
        if max_failed > 100:
            max_failed = 100

        try:
            lock_seconds = int(form.get("lock_seconds", 300))
        except Exception:
            lock_seconds = 300
        if lock_seconds < 10:
            lock_seconds = 10
        if lock_seconds > 86400:
            lock_seconds = 86400

        lock_message = str(form.get("lock_message", "") or "").strip()
        if not lock_message:
            lock_message = "Too many failed attempts. Please try again in {remain}."

        security["max_failed_attempts"] = max_failed
        security["lock_seconds"] = lock_seconds
        security["lock_message"] = lock_message

        save_settings(settings)
        append_log("SECURITY", "管理员保存安全锁定设置")
        self.redirect("/admin/security")

    def admin_security_unlock(self):
        form = self.read_form()
        key = str(form.get("key", "")).strip()
        db = load_db()
        if key in db.get("security_locks", {}):
            del db["security_locks"][key]
            save_db(db)
            append_log("SECURITY", f"管理员清除安全锁定 {key}")
        self.redirect("/admin/security")

    def admin_security_clear_all(self):
        db = load_db()
        count = len(db.get("security_locks", {}))
        db["security_locks"] = {}
        save_db(db)
        append_log("SECURITY", f"管理员清空全部失败记录 {count} 条")
        self.redirect("/admin/security")


# CONNECTED_DEVICES_OVERRIDE_V2
def _wp_collect_connected_clients_v2():
    clients = {}

    def add_client(mac, ip="", hostname="Unknown Device", source=""):
        mac = normalize_mac(mac)
        if not mac or mac == "00:00:00:00:00:00":
            return
        item = clients.setdefault(mac, {"mac": mac, "ip": "", "hostname": "Unknown Device", "source": ""})
        if ip:
            item["ip"] = ip
        if hostname and hostname != "*":
            item["hostname"] = hostname
        if source:
            current = item.get("source", "")
            if not current:
                item["source"] = source
            elif source not in current:
                item["source"] = current + "," + source

    for lease_path in ["/tmp/dhcp.leases", "/var/dhcp.leases"]:
        try:
            with open(lease_path, "r", encoding="utf-8") as file:
                for line in file:
                    parts = line.split()
                    if len(parts) >= 4:
                        add_client(parts[1], parts[2], parts[3], "DHCP")
        except Exception:
            pass

    try:
        with open("/proc/net/arp", "r", encoding="utf-8") as file:
            for line in file.readlines()[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    add_client(parts[3], parts[0], "", "ARP")
    except Exception:
        pass

    code, out, err = run_command(["/usr/sbin/iw", "dev"])
    if code != 0:
        code, out, err = run_command(["/sbin/iw", "dev"])

    if code == 0:
        wifi_ifaces = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Interface "):
                parts = line.split()
                if len(parts) >= 2:
                    wifi_ifaces.append(parts[1])

        for iface in wifi_ifaces:
            code2, out2, err2 = run_command(["/usr/sbin/iw", "dev", iface, "station", "dump"])
            if code2 != 0:
                code2, out2, err2 = run_command(["/sbin/iw", "dev", iface, "station", "dump"])
            if code2 == 0:
                for line in out2.splitlines():
                    line = line.strip()
                    if line.startswith("Station "):
                        parts = line.split()
                        if len(parts) >= 2:
                            add_client(parts[1], "", "", "WiFi")

    return clients


def _wp_collect_current_wifi_clients_12h():
    clients = {}

    def add_client(mac, iface="", inactive_ms="", signal=""):
        mac = normalize_mac(mac)
        if not mac:
            return
        clients[mac] = {
            "mac": mac,
            "ip": "",
            "hostname": "Unknown Device",
            "source": "WiFi在线",
            "iface": iface,
            "inactive_ms": inactive_ms,
            "signal": signal,
            "rx_bytes": "",
            "tx_bytes": ""
        }

    code, out, err = run_command(["/usr/sbin/iw", "dev"])
    if code != 0:
        code, out, err = run_command(["/sbin/iw", "dev"])

    wifi_ifaces = []
    if code == 0:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Interface "):
                parts = line.split()
                if len(parts) >= 2:
                    wifi_ifaces.append(parts[1])

    for iface in wifi_ifaces:
        code2, out2, err2 = run_command(["/usr/sbin/iw", "dev", iface, "station", "dump"])
        if code2 != 0:
            code2, out2, err2 = run_command(["/sbin/iw", "dev", iface, "station", "dump"])
        if code2 != 0:
            continue

        current_mac = ""
        for line in out2.splitlines():
            line = line.strip()
            if line.startswith("Station "):
                parts = line.split()
                current_mac = normalize_mac(parts[1]) if len(parts) >= 2 else ""
                if current_mac:
                    add_client(current_mac, iface=iface)
                continue

            if not current_mac or current_mac not in clients:
                continue

            if line.startswith("inactive time:"):
                clients[current_mac]["inactive_ms"] = line.split(":", 1)[1].strip()
            elif line.startswith("rx bytes:"):
                clients[current_mac]["rx_bytes"] = line.split(":", 1)[1].strip()
            elif line.startswith("tx bytes:"):
                clients[current_mac]["tx_bytes"] = line.split(":", 1)[1].strip()
            elif line.startswith("signal:"):
                clients[current_mac]["signal"] = line.split(":", 1)[1].strip()

    # 用 DHCP/ARP 只补 IP 和主机名，不用它判断在线。
    seen = get_all_seen_clients()
    for mac, item in seen.items():
        mac = normalize_mac(mac)
        if mac in clients:
            if item.get("ip"):
                clients[mac]["ip"] = item.get("ip", "")
            if item.get("hostname") and item.get("hostname") != "Unknown Device":
                clients[mac]["hostname"] = item.get("hostname", "Unknown Device")

    return clients


def _wp_int_from_text(value):
    try:
        return int(str(value).strip().split()[0])
    except Exception:
        return 0


def _wp_get_realtime_wifi_speeds(clients):
    # AP 视角：
    # rx_bytes = AP 从客户端收到的数据，约等于客户端上传
    # tx_bytes = AP 发给客户端的数据，约等于客户端下载
    # 使用 time.time() 小数秒，避免 1 秒 Ajax 刷新时因为整数秒相同导致“刷新后显示”。
    cache_file = "/tmp/wifiportal_realtime_speed.json"
    current_time = time.time()

    previous = {}
    try:
        previous = load_json(cache_file, {})
    except Exception:
        previous = {}

    result = {}
    snapshot = {"time": current_time, "clients": {}}

    try:
        previous_time = float(previous.get("time", 0) or 0)
    except Exception:
        previous_time = 0.0

    elapsed = current_time - previous_time
    previous_clients = previous.get("clients", {}) if isinstance(previous.get("clients", {}), dict) else {}

    for mac, item in clients.items():
        mac = normalize_mac(mac)
        if not mac:
            continue

        rx_bytes = _wp_int_from_text(item.get("rx_bytes", 0))
        tx_bytes = _wp_int_from_text(item.get("tx_bytes", 0))

        snapshot["clients"][mac] = {
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes
        }

        old_item = previous_clients.get(mac, {}) if isinstance(previous_clients, dict) else {}
        old_rx = int(old_item.get("rx_bytes", 0) or 0)
        old_tx = int(old_item.get("tx_bytes", 0) or 0)

        down_mbps = 0.0
        up_mbps = 0.0

        # elapsed 太小、第一次没有缓存、设备刚连接、计数器重置时，都显示 0.00 Mbps，不再显示“刷新后显示”。
        if elapsed >= 0.2 and rx_bytes >= old_rx and tx_bytes >= old_tx and old_rx > 0 and old_tx > 0:
            up_mbps = ((rx_bytes - old_rx) * 8) / elapsed / 1000000
            down_mbps = ((tx_bytes - old_tx) * 8) / elapsed / 1000000

        # 防止异常尖峰显示过大；这里不影响限速，只影响页面显示。
        if down_mbps < 0:
            down_mbps = 0.0
        if up_mbps < 0:
            up_mbps = 0.0

        result[mac] = {
            "download": "%.2f Mbps" % down_mbps,
            "upload": "%.2f Mbps" % up_mbps
        }

    try:
        save_json(cache_file, snapshot)
    except Exception:
        pass

    return result


def _wp_show_admin_devices_v2(self):
    cleanup_expired_and_firewall()
    db = load_db()

    history_seconds = 12 * 60 * 60
    current_time = now()

    query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
    view_filter = query.get("view", ["all"])[0]
    if view_filter not in ["all", "online", "history"]:
        view_filter = "all"
    partial_refresh = query.get("partial", ["0"])[0] == "1"

    clients = _wp_collect_current_wifi_clients_12h()
    current_online_macs = set(clients.keys())

    try:
        realtime_speeds = _wp_get_realtime_wifi_speeds(clients)
    except Exception:
        realtime_speeds = {}

    # 历史认证设备：只保留 12 小时内 last_seen 的记录。
    for mac, device in db.get("devices", {}).items():
        mac = normalize_mac(mac)
        if not mac:
            continue

        last_seen = int(device.get("last_seen", 0) or 0)
        is_current_online = mac in current_online_macs
        is_recent_history = last_seen > 0 and (current_time - last_seen) <= history_seconds

        if not is_current_online and not is_recent_history:
            continue

        item = clients.setdefault(mac, {
            "mac": mac,
            "ip": "",
            "hostname": "Unknown Device",
            "source": "12小时历史",
            "iface": "",
            "inactive_ms": "",
            "signal": "",
            "rx_bytes": "",
            "tx_bytes": ""
        })

        if device.get("ip"):
            item["ip"] = device.get("ip", "")
        if device.get("hostname"):
            item["hostname"] = device.get("hostname", "Unknown Device")

        if is_current_online:
            item["source"] = "WiFi在线"
        elif is_recent_history:
            item["source"] = "12小时历史"

    rows = []
    for mac, client in sorted(clients.items(), key=lambda x: (x[1].get("ip", ""), x[0])):
        device = db.get("devices", {}).get(mac, {})
        hostname = device.get("hostname") or client.get("hostname") or "Unknown Device"
        ip = client.get("ip") or device.get("ip", "")
        source = client.get("source", "")
        voucher_code = device.get("voucher_code", "") or "未登录兑换码"
        auth_active = bool(device.get("online"))
        is_realtime_online = mac in current_online_macs
        expire_at = int(device.get("expire_at", 0) or 0)
        last_seen = int(device.get("last_seen", 0) or 0)

        if expire_at > 0 and expire_at <= now():
            auth_active = False

        if mac in db.get("blacklist", {}):
            status = "黑名单"
        elif mac in db.get("whitelist", {}):
            status = "实时在线 / 白名单" if is_realtime_online else "历史 / 白名单"
        elif is_realtime_online and auth_active:
            status = "实时在线 / 已登录"
        elif is_realtime_online:
            status = "实时在线 / 未登录兑换码"
        elif auth_active:
            status = "历史记录 / 认证仍有效 / 当前不在线"
        else:
            status = "历史记录 / 未登录兑换码 / 当前不在线"

        if view_filter == "online" and not is_realtime_online:
            continue
        if view_filter == "history" and is_realtime_online:
            continue

        if expire_at == 0 and auth_active:
            remaining = "永久"
            expire_text = "永久"
        elif expire_at > 0 and auth_active:
            seconds = max(0, expire_at - now())
            remaining = str(seconds // 3600) + "小时 " + str((seconds % 3600) // 60) + "分钟"
            expire_text = format_time(expire_at)
        else:
            remaining = "-"
            expire_text = "-"

        download = device.get("download_mbps", "-")
        upload = device.get("upload_mbps", "-")
        plan_name = device.get("speed_profile_name", "-")
        speed = esc(download) + " ↓ / " + esc(upload) + " ↑ Mbps"

        if is_realtime_online:
            speed_item = realtime_speeds.get(mac, {})
            realtime_speed = "下载 " + esc(speed_item.get("download", "刷新后显示")) + " / 上传 " + esc(speed_item.get("upload", "刷新后显示"))
        else:
            realtime_speed = "当前不在线"

        extra = []
        if client.get("iface"):
            extra.append("接口 " + str(client.get("iface")))
        if client.get("signal"):
            extra.append("信号 " + str(client.get("signal")))
        if client.get("inactive_ms"):
            extra.append("空闲 " + str(client.get("inactive_ms")))
        if last_seen:
            extra.append("最后出现 " + format_time(last_seen))
        extra_text = " / ".join(extra)

        operation_html = (
            '<form method="post" action="/admin/blacklist-add" style="display:inline" onsubmit="return confirm(\'确认加入黑名单？\')">'
            '<input type="hidden" name="mac" value="' + esc(mac) + '">'
            '<input type="hidden" name="device_name" value="' + esc(hostname) + '">'
            '<input type="hidden" name="reason" value="Blocked from devices page">'
            '<button class="danger" type="submit">拉黑</button>'
            '</form>'
        )

        if mac in db.get("devices", {}):
            operation_html = (
                '<form method="post" action="/admin/device-kick" style="display:inline">'
                '<input type="hidden" name="mac" value="' + esc(mac) + '">'
                '<button type="submit">踢下线</button>'
                '</form>'
                '<form method="post" action="/admin/device-unbind" style="display:inline" onsubmit="return confirm(\'确认解绑这个设备？\')">'
                '<input type="hidden" name="mac" value="' + esc(mac) + '">'
                '<button class="danger" type="submit">解绑</button>'
                '</form>'
            ) + operation_html

        rows.append(
            "<tr>"
            "<td>" + esc(hostname) + "<br><span class='muted'>" + esc(source) + "</span></td>"
            "<td><code>" + esc(mac) + "</code></td>"
            "<td>" + esc(ip) + "</td>"
            "<td><code>" + esc(voucher_code) + "</code></td>"
            "<td>" + speed + "<br><span class='muted'>" + esc(plan_name) + "</span></td>"
            "<td>" + realtime_speed + "</td>"
            "<td>" + esc(format_time(device.get("login_at", 0))) + "</td>"
            "<td>" + esc(expire_text) + "</td>"
            "<td>" + esc(remaining) + "</td>"
            "<td><b>" + esc(status) + "</b><br><span class='muted'>" + esc(extra_text) + "</span></td>"
            "<td>" + operation_html + "</td>"
            "</tr>"
        )

    table_rows = "".join(rows)
    if not table_rows:
        table_rows = "<tr><td colspan='11' class='muted'>暂无设备记录。当前没有 WiFi 在线设备，也没有 12 小时内历史认证记录。</td></tr>"

    # Ajax 局部刷新：只返回 tbody 里面的 tr，不返回整页。
    if partial_refresh:
        self.send_html(table_rows)
        return

    body = (
        "<div class='card'>"
        "<h1>在线 / 历史设备</h1>"
        "<p class='muted'>实时在线只按 WiFi station 判断；历史设备只显示 12 小时内记录。实时网速每 1 秒局部更新表格，不刷新整页。</p>"
        "<p>"
        "<a class='btn' href='/admin/devices?view=online'>在线</a> "
        "<a class='btn' href='/admin/devices?view=history'>历史设备</a> "
        "<a class='btn' href='/admin/devices'>全部</a> "
        "<span class='muted' id='devices-refresh-status'>等待更新</span>"
        "</p>"
        "<script>"
        "function refreshDevicesTable(){"
        "  var url = new URL(window.location.href);"
        "  url.searchParams.set('partial','1');"
        "  fetch(url.toString(), {cache:'no-store', credentials:'same-origin'})"
        "    .then(function(r){ return r.text(); })"
        "    .then(function(html){"
        "      var body = document.getElementById('devices-table-body');"
        "      if(body){ body.innerHTML = html; }"
        "      var s = document.getElementById('devices-refresh-status');"
        "      if(s){ s.textContent = '已更新 ' + new Date().toLocaleTimeString(); }"
        "    })"
        "    .catch(function(){"
        "      var s = document.getElementById('devices-refresh-status');"
        "      if(s){ s.textContent = '更新失败'; }"
        "    });"
        "}"
        "setInterval(refreshDevicesTable, 1000);"
        "setTimeout(refreshDevicesTable, 1000);"
        "</script>"
        "</div>"
        "<div class='card'>"
        "<table>"
        "<tr><th>设备名/来源</th><th>MAC</th><th>IP</th><th>兑换码</th><th>套餐网速</th><th>实时网速</th><th>登录时间</th><th>到期时间</th><th>剩余时间</th><th>状态</th><th>操作</th></tr>"
        "<tbody id='devices-table-body'>"
        + table_rows +
        "</tbody>"
        "</table>"
        "</div>"
    )
    self.send_html(admin_page("在线设备", body))



def _wp_show_admin_devices_v3(self):
    db = load_db()
    query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    status_filter = str(query.get("status", ["online"])[0] or "online").strip()
    if status_filter not in ["online", "offline", "all"]:
        status_filter = "online"

    search_text = str(query.get("q", [""])[0] or "").strip().lower()

    devices = db.get("devices", {})
    if not isinstance(devices, dict):
        devices = {}

    now_ts = now()

    normalized_rows = []
    total_count = 0
    online_count = 0
    offline_count = 0

    for mac, device in sorted(devices.items(), key=lambda x: (
        0 if isinstance(x[1], dict) and x[1].get("online") else 1,
        str(x[1].get("ip", "")) if isinstance(x[1], dict) else "",
        str(x[0])
    )):
        if not isinstance(device, dict):
            continue

        total_count += 1

        hostname = device.get("hostname") or "Unknown Device"
        ip = device.get("ip") or "-"
        voucher_code = device.get("voucher_code") or "-"
        online = bool(device.get("online", False))
        expire_at = int(device.get("expire_at", 0) or 0)

        if expire_at > 0 and expire_at <= now_ts:
            online = False

        if online:
            online_count += 1
        else:
            offline_count += 1

        if status_filter == "online" and not online:
            continue
        if status_filter == "offline" and online:
            continue

        search_blob = " ".join([
            str(hostname),
            str(ip),
            str(mac),
            str(voucher_code),
            str(device.get("speed_profile_name", "")),
        ]).lower()

        if search_text and search_text not in search_blob:
            continue

        if mac in db.get("blacklist", {}):
            status_text = "黑名单"
            status_class = "device-bad"
        elif mac in db.get("whitelist", {}):
            status_text = "白名单"
            status_class = "device-good"
        elif online:
            status_text = "在线"
            status_class = "device-good"
        else:
            status_text = "离线"
            status_class = "device-muted"

        if online and expire_at == 0:
            remaining = "永久"
            expire_text = "永久"
        elif online and expire_at > 0:
            seconds = max(0, expire_at - now_ts)
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            minutes = (seconds % 3600) // 60
            if days > 0:
                remaining = f"{days}天 {hours}小时"
            elif hours > 0:
                remaining = f"{hours}小时 {minutes}分钟"
            else:
                remaining = f"{minutes}分钟"
            expire_text = format_time(expire_at)
        else:
            remaining = "-"
            expire_text = "-"

        login_text = format_time(device.get("login_at", 0))
        last_text = format_time(device.get("last_seen", 0))

        down = device.get("download_mbps", "")
        up = device.get("upload_mbps", "")
        if not down:
            down = kbps_to_mbps(device.get("download_kbps", 0))
        if not up:
            up = kbps_to_mbps(device.get("upload_kbps", 0))

        plan_name = device.get("speed_profile_name") or "-"
        speed_text = f"{down}↓/{up}↑ Mbps"

        actions = f"""
<form method="post" action="/admin/device-kick" class="device-inline-form">
<input type="hidden" name="mac" value="{esc(mac)}">
<button type="submit" class="device-mini-btn">踢下线</button>
</form>
<form method="post" action="/admin/device-unbind" class="device-inline-form" onsubmit="return confirm('确认解绑这个设备？')">
<input type="hidden" name="mac" value="{esc(mac)}">
<button type="submit" class="device-mini-btn danger">解绑</button>
</form>
<form method="post" action="/admin/blacklist-add" class="device-inline-form" onsubmit="return confirm('确认加入黑名单？')">
<input type="hidden" name="mac" value="{esc(mac)}">
<input type="hidden" name="device_name" value="{esc(hostname)}">
<input type="hidden" name="reason" value="Blocked from devices page">
<button type="submit" class="device-mini-btn danger">拉黑</button>
</form>
"""

        normalized_rows.append(f"""
<tr>
<td>
  <b>{esc(hostname)}</b>
  <div class="device-sub">{esc(ip)}</div>
</td>
<td>
  <code>{esc(mac)}</code>
</td>
<td>
  <code>{esc(voucher_code)}</code>
  <div class="device-sub">{esc(plan_name)}</div>
</td>
<td>
  <span class="device-badge {status_class}">{esc(status_text)}</span>
</td>
<td>
  <b>{esc(remaining)}</b>
  <div class="device-sub">到期：{esc(expire_text)}</div>
</td>
<td>
  <b>{esc(speed_text)}</b>
</td>
<td>
  <span>{esc(last_text)}</span>
  <div class="device-sub">登录：{esc(login_text)}</div>
</td>
<td class="device-action-cell">
  {actions}
</td>
</tr>
""")

    def device_filter_link(key, label, count):
        active = " device-filter-active" if status_filter == key else ""
        q = urllib.parse.quote(search_text)
        return f'<a class="btn device-filter-btn{active}" href="/admin/devices?status={key}&q={q}">{label} <b>{count}</b></a>'

    filter_links = " ".join([
        device_filter_link("online", "在线", online_count),
        device_filter_link("offline", "离线", offline_count),
        device_filter_link("all", "全部", total_count),
    ])

    body = f"""
<div class="card device-compact-top">
<h1>在线设备</h1>
<p class="muted">默认只显示在线设备，方便观察当前正在使用网络的客户。</p>
<div class="grid">
<div class="stat">在线设备<b>{online_count}</b></div>
<div class="stat">离线设备<b>{offline_count}</b></div>
<div class="stat">全部记录<b>{total_count}</b></div>
<div class="stat">当前显示<b>{len(normalized_rows)}</b></div>
</div>
</div>

<div class="card device-filter-card">
<form method="get" action="/admin/devices" class="device-search-form">
<input type="hidden" name="status" value="{esc(status_filter)}">
<input name="q" value="{esc(search_text)}" placeholder="搜索设备名、IP、MAC、兑换码、套餐">
<button type="submit">搜索</button>
<a class="btn dense-reset-filter-btn" href="/admin/devices">重置筛选</a>
</form>
<div class="device-filter-row">{filter_links}</div>
</div>

<div class="card device-compact-card">
<h2>设备列表</h2>
<p class="muted">筛选：{esc(status_filter)}；搜索：{esc(search_text or "无")}。</p>
<table class="device-compact-table">
<tr>
<th>设备 / IP</th>
<th>MAC</th>
<th>兑换码 / 套餐</th>
<th>状态</th>
<th>剩余 / 到期</th>
<th>限速</th>
<th>最后在线 / 登录</th>
<th>操作</th>
</tr>
{''.join(normalized_rows) if normalized_rows else '<tr><td colspan="8" class="muted">暂无符合条件的设备</td></tr>'}
</table>
</div>
"""
    self.send_html(admin_page("在线设备", body))




def _wp_show_admin_devices_v4(self):
    db = load_db()
    query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    status_filter = str(query.get("status", ["online"])[0] or "online").strip()
    if status_filter not in ["online", "offline", "all"]:
        status_filter = "online"

    search_text = str(query.get("q", [""])[0] or "").strip().lower()

    devices = db.get("devices", {})
    if not isinstance(devices, dict):
        devices = {}

    now_ts = now()
    total_count = 0
    online_count = 0
    offline_count = 0
    cards = []

    sorted_devices = sorted(
        devices.items(),
        key=lambda x: (
            0 if isinstance(x[1], dict) and x[1].get("online") else 1,
            str(x[1].get("ip", "")) if isinstance(x[1], dict) else "",
            str(x[0])
        )
    )

    for mac, device in sorted_devices:
        if not isinstance(device, dict):
            continue

        total_count += 1

        hostname = device.get("hostname") or "Unknown Device"
        ip = device.get("ip") or "-"
        voucher_code = device.get("voucher_code") or "-"
        online = bool(device.get("online", False))
        expire_at = int(device.get("expire_at", 0) or 0)

        if expire_at > 0 and expire_at <= now_ts:
            online = False

        if online:
            online_count += 1
        else:
            offline_count += 1

        if status_filter == "online" and not online:
            continue
        if status_filter == "offline" and online:
            continue

        search_blob = " ".join([
            str(hostname),
            str(ip),
            str(mac),
            str(voucher_code),
            str(device.get("speed_profile_name", "")),
        ]).lower()

        if search_text and search_text not in search_blob:
            continue

        if mac in db.get("blacklist", {}):
            status_text = "黑名单"
            status_class = "dev4-bad"
        elif mac in db.get("whitelist", {}):
            status_text = "白名单"
            status_class = "dev4-good"
        elif online:
            status_text = "在线"
            status_class = "dev4-good"
        else:
            status_text = "离线"
            status_class = "dev4-muted"

        if online and expire_at == 0:
            remaining = "永久"
        elif online and expire_at > 0:
            seconds = max(0, expire_at - now_ts)
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if hours > 0:
                remaining = f"{hours}小时{minutes}分"
            else:
                remaining = f"{minutes}分钟"
        else:
            remaining = "-"

        last_seen = format_time(device.get("last_seen", 0))
        plan_name = device.get("speed_profile_name") or "-"

        down = device.get("download_mbps", "")
        up = device.get("upload_mbps", "")
        if not down:
            down = kbps_to_mbps(device.get("download_kbps", 0))
        if not up:
            up = kbps_to_mbps(device.get("upload_kbps", 0))

        speed_text = f"{down}↓/{up}↑"

        cards.append(f"""
<div class="dev4-card">
  <div class="dev4-head">
    <div class="dev4-name">{esc(hostname)}</div>
    <span class="dev4-badge {status_class}">{esc(status_text)}</span>
  </div>

  <div class="dev4-main">
    <div><span>IP</span><b>{esc(ip)}</b></div>
    <div><span>兑换码</span><b>{esc(voucher_code)}</b></div>
    <div><span>剩余</span><b>{esc(remaining)}</b></div>
    <div><span>限速</span><b>{esc(speed_text)}</b></div>
  </div>

  <div class="dev4-sub">
    <span>套餐：{esc(plan_name)}</span>
    <span>MAC：{esc(mac)}</span>
    <span>最后：{esc(last_seen)}</span>
  </div>

  <div class="dev4-actions">
    <form method="post" action="/admin/device-kick">
      <input type="hidden" name="mac" value="{esc(mac)}">
      <button type="submit">踢下线</button>
    </form>

    <form method="post" action="/admin/device-unbind" onsubmit="return confirm('确认解绑这个设备？')">
      <input type="hidden" name="mac" value="{esc(mac)}">
      <button class="danger" type="submit">解绑</button>
    </form>

    <form method="post" action="/admin/blacklist-add" onsubmit="return confirm('确认加入黑名单？')">
      <input type="hidden" name="mac" value="{esc(mac)}">
      <input type="hidden" name="device_name" value="{esc(hostname)}">
      <input type="hidden" name="reason" value="Blocked from devices page">
      <button class="danger" type="submit">拉黑</button>
    </form>
  </div>
</div>
""")

    def link(key, label, count):
        active = " dev4-filter-active" if status_filter == key else ""
        q = urllib.parse.quote(search_text)
        return f'<a class="btn dev4-filter{active}" href="/admin/devices?status={key}&q={q}">{label} <b>{count}</b></a>'

    filter_html = " ".join([
        link("online", "在线", online_count),
        link("offline", "离线", offline_count),
        link("all", "全部", total_count),
    ])

    body = f"""
<div class="card dev4-top">
<h1>在线设备</h1>
<div class="dev4-stats">
  <div>在线<b>{online_count}</b></div>
  <div>离线<b>{offline_count}</b></div>
  <div>全部<b>{total_count}</b></div>
  <div>显示<b>{len(cards)}</b></div>
</div>
</div>

<div class="card dev4-filter-card">
<form method="get" action="/admin/devices" class="dev4-search">
<input type="hidden" name="status" value="{esc(status_filter)}">
<input name="q" value="{esc(search_text)}" placeholder="搜索设备名/IP/MAC/兑换码">
<button type="submit">搜索</button>
<a class="btn" href="/admin/devices">清空</a>
</form>
<div class="dev4-filter-row">{filter_html}</div>
</div>

<div class="dev4-list">
{''.join(cards) if cards else '<div class="card"><p class="muted">暂无符合条件的设备</p></div>'}
</div>
"""
    self.send_html(admin_page("在线设备", body))




def _wp_show_admin_devices_v5(self):
    db = load_db()
    query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    status_filter = str(query.get("status", ["online"])[0] or "online").strip()
    if status_filter not in ["online", "offline", "all"]:
        status_filter = "online"

    search_text = str(query.get("q", [""])[0] or "").strip()
    search_lower = search_text.lower()

    devices = db.get("devices", {})
    if not isinstance(devices, dict):
        devices = {}

    now_ts = now()

    total_count = 0
    online_count = 0
    offline_count = 0
    shown_count = 0
    rows = []

    def device_filter_link(key, label, count):
        active_class = " dense-filter-active" if status_filter == key else ""
        q_part = urllib.parse.quote(search_text)
        return f'<a class="btn dense-filter-btn{active_class}" href="/admin/devices?status={key}&q={q_part}">{label} <b>{count}</b></a>'

    def device_status_badge(status_text, status_key):
        if status_key == "online":
            cls = "dense-badge-green"
        elif status_key == "offline":
            cls = "dense-badge-blue"
        else:
            cls = "dense-badge-danger"
        return '<span class="dense-badge ' + cls + '">' + esc(status_text) + '</span>'

    prepared = []

    for mac, device in devices.items():
        if not isinstance(device, dict):
            continue

        hostname = device.get("hostname") or "Unknown Device"
        ip = device.get("ip") or "-"
        voucher_code = device.get("voucher_code") or "-"
        online = bool(device.get("online", False))
        expire_at = int(device.get("expire_at", 0) or 0)

        if expire_at > 0 and expire_at <= now_ts:
            online = False

        if mac in db.get("blacklist", {}):
            status_text = "黑名单"
            status_key = "blocked"
        elif mac in db.get("whitelist", {}):
            status_text = "白名单"
            status_key = "online" if online else "offline"
        elif online:
            status_text = "在线"
            status_key = "online"
        else:
            status_text = "离线"
            status_key = "offline"

        total_count += 1
        if online:
            online_count += 1
        else:
            offline_count += 1

        prepared.append({
            "mac": mac,
            "device": device,
            "hostname": hostname,
            "ip": ip,
            "voucher_code": voucher_code,
            "online": online,
            "expire_at": expire_at,
            "status_text": status_text,
            "status_key": status_key,
        })

    filter_buttons = " ".join([
        device_filter_link("online", "在线", online_count),
        device_filter_link("offline", "离线", offline_count),
        device_filter_link("all", "全部", total_count),
    ])

    for item in sorted(prepared, key=lambda x: (
        0 if x["online"] else 1,
        str(x["ip"]),
        str(x["mac"])
    )):
        mac = item["mac"]
        device = item["device"]
        hostname = item["hostname"]
        ip = item["ip"]
        voucher_code = item["voucher_code"]
        online = item["online"]
        expire_at = item["expire_at"]
        status_text = item["status_text"]
        status_key = item["status_key"]

        if status_filter == "online" and not online:
            continue
        if status_filter == "offline" and online:
            continue

        plan_name = device.get("speed_profile_name") or "-"
        search_blob = " ".join([
            str(hostname),
            str(ip),
            str(mac),
            str(voucher_code),
            str(plan_name),
            str(status_text),
        ]).lower()

        if search_lower and search_lower not in search_blob:
            continue

        shown_count += 1

        if online and expire_at == 0:
            remaining = "永久"
            expire_text = "永久"
        elif online and expire_at > 0:
            seconds = max(0, expire_at - now_ts)
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            minutes = (seconds % 3600) // 60
            if days > 0:
                remaining = f"{days}天 {hours}小时"
            elif hours > 0:
                remaining = f"{hours}小时 {minutes}分钟"
            else:
                remaining = f"{minutes}分钟"
            expire_text = format_time(expire_at)
        else:
            remaining = "-"
            expire_text = "-"

        login_text = format_time(device.get("login_at", 0))
        last_text = format_time(device.get("last_seen", 0))

        down = device.get("download_mbps", "")
        up = device.get("upload_mbps", "")
        if down == "":
            down = kbps_to_mbps(device.get("download_kbps", 0))
        if up == "":
            up = kbps_to_mbps(device.get("upload_kbps", 0))

        speed_text = f"{down}↓/{up}↑"

        status_badge = device_status_badge(status_text, status_key)

        rows.append(f"""
<tr>
<td class="dense-code-col">
  <b>{esc(hostname)}</b>
  <div class="dense-sub">{esc(ip)}</div>
</td>
<td>
  <code>{esc(mac)}</code>
</td>
<td>
  <code>{esc(voucher_code)}</code>
  <div class="dense-sub">{esc(plan_name)}</div>
</td>
<td class="dense-status-col">
  {status_badge}
  <div class="dense-sub">剩余：{esc(remaining)}</div>
</td>
<td>
  <b>{esc(speed_text)}</b>
  <div class="dense-sub">Mbps</div>
</td>
<td>
  <b>{esc(expire_text)}</b>
  <div class="dense-sub">登录：{esc(login_text)}</div>
</td>
<td>
  <b>{esc(last_text)}</b>
</td>
<td class="dense-actions-col">
  <div class="dense-actions-main">
    <form method="post" action="/admin/device-kick">
      <input type="hidden" name="mac" value="{esc(mac)}">
      <button type="submit" class="dense-mini-btn">踢下线</button>
    </form>

    <form method="post" action="/admin/device-unbind" onsubmit="return confirm('确认解绑这个设备？')">
      <input type="hidden" name="mac" value="{esc(mac)}">
      <button type="submit" class="danger dense-mini-btn">解绑</button>
    </form>

    <details class="dense-more">
      <summary>更多</summary>
      <form method="post" action="/admin/blacklist-add" onsubmit="return confirm('确认加入黑名单？')">
        <input type="hidden" name="mac" value="{esc(mac)}">
        <input type="hidden" name="device_name" value="{esc(hostname)}">
        <input type="hidden" name="reason" value="Blocked from devices page">
        <button type="submit" class="danger dense-mini-btn">拉黑</button>
      </form>
    </details>
  </div>
</td>
</tr>
""")

    filter_label = {
        "online": "在线",
        "offline": "离线",
        "all": "全部",
    }.get(status_filter, "在线")

    body = f"""
<div class="card dense-top-card">
<h1>在线设备</h1>
<p class="muted">紧凑总览模式：一行一个设备，样式与兑换码列表一致。</p>
<div class="dense-stat-row">
<a class="dense-stat" href="/admin/devices?status=online&q={esc(urllib.parse.quote(search_text))}">在线<b>{online_count}</b></a>
<a class="dense-stat" href="/admin/devices?status=offline&q={esc(urllib.parse.quote(search_text))}">离线<b>{offline_count}</b></a>
<a class="dense-stat" href="/admin/devices?status=all&q={esc(urllib.parse.quote(search_text))}">全部<b>{total_count}</b></a>
<a class="dense-stat" href="#">显示<b>{shown_count}</b></a>
</div>
</div>

<div class="card dense-search-card">
<form method="get" action="/admin/devices" class="dense-search-form">
<input type="hidden" name="status" value="{esc(status_filter)}">
<input name="q" value="{esc(search_text)}" placeholder="搜索设备名、IP、MAC、兑换码、套餐、状态">
<button type="submit">搜索</button>
<a class="btn" href="/admin/devices">清空</a>
</form>
<div class="dense-filter-row">{filter_buttons}</div>
</div>

<div class="card dense-list-card">
<h2>设备列表</h2>
<p class="muted">筛选：{esc(filter_label)}；搜索：{esc(search_text or "无")}；当前显示 {shown_count} 台。</p>
<table class="voucher-dense-table">
<tr>
<th>设备 / IP</th>
<th>MAC</th>
<th>兑换码 / 套餐</th>
<th>状态 / 剩余</th>
<th>限速</th>
<th>到期 / 登录</th>
<th>最后在线</th>
<th>操作</th>
</tr>
{''.join(rows) if rows else '<tr><td colspan="8" class="muted">暂无符合条件的设备</td></tr>'}
</table>
</div>
"""
    self.send_html(admin_page("在线设备", body))




def _wp_show_admin_devices_v6(self):
    db = load_db()
    query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    status_filter = str(query.get("status", ["online"])[0] or "online").strip()
    if status_filter not in ["online", "offline", "all", "online_authed", "online_guest"]:
        status_filter = "online"

    search_text = str(query.get("q", [""])[0] or "").strip()
    search_lower = search_text.lower()

    plan_filter = str(query.get("plan", ["all"])[0] or "all").strip()
    if not plan_filter:
        plan_filter = "all"

    devices = db.get("devices", {})
    if not isinstance(devices, dict):
        devices = {}

    now_ts = now()

    try:
        realtime_clients = _wp_collect_current_wifi_clients_12h()
    except Exception:
        realtime_clients = {}

    if not isinstance(realtime_clients, dict):
        realtime_clients = {}

    realtime_online_macs = set(realtime_clients.keys())

    try:
        realtime_speeds = _wp_get_realtime_wifi_speeds(realtime_clients)
    except Exception:
        realtime_speeds = {}

    if not isinstance(realtime_speeds, dict):
        realtime_speeds = {}

    total_count = 0
    online_count = 0
    offline_count = 0
    online_authed_count = 0
    online_guest_count = 0
    realtime_count = len(realtime_online_macs)
    shown_count = 0
    plan_counts = {}
    rows = []

    def device_filter_link(key, label, count):
        active_class = " dense-filter-active" if status_filter == key else ""
        q_part = urllib.parse.quote(search_text)
        plan_part = urllib.parse.quote(plan_filter)
        return f'<a class="btn dense-filter-btn{active_class}" href="/admin/devices?status={key}&plan={plan_part}&q={q_part}">{label} <b>{count}</b></a>'

    def plan_filter_link(plan_name, label, count):
        active_class = " dense-filter-active" if plan_filter == plan_name else ""
        q_part = urllib.parse.quote(search_text)
        plan_part = urllib.parse.quote(plan_name)
        return f'<a class="btn dense-filter-btn{active_class}" href="/admin/devices?status={status_filter}&plan={plan_part}&q={q_part}">{esc(label)} <b>{count}</b></a>'

    def device_status_badge(status_text, status_key):
        if status_key == "online":
            cls = "dense-badge-green"
        elif status_key == "offline":
            cls = "dense-badge-blue"
        else:
            cls = "dense-badge-danger"
        return '<span class="dense-badge ' + cls + '">' + esc(status_text) + '</span>'

    prepared = []

    for mac, device in devices.items():
        if not isinstance(device, dict):
            continue

        hostname = device.get("hostname") or "Unknown Device"
        ip = device.get("ip") or "-"

        # ADMIN_V6_EXPIRED_HISTORY_DISPLAY_FIX_V1
        #
        # A device can be realtime-online while its old voucher history remains in DB.
        # If the voucher is expired/invalid, do not display it as the current package.
        # Otherwise the "在线未登录" page looks like the device has a valid voucher.
        raw_voucher_code = str(device.get("voucher_code", "") or "").strip()
        voucher_obj = db.get("vouchers", {}).get(raw_voucher_code) if raw_voucher_code else None
        voucher_exists = isinstance(voucher_obj, dict)
        unauthenticated_realtime = False

        expire_at = int(device.get("expire_at", 0) or 0)
        if expire_at <= 0 and voucher_exists:
            expire_at = int(voucher_obj.get("expire_at", 0) or 0)

        has_valid_voucher = bool(
            raw_voucher_code
            and voucher_exists
            and (expire_at == 0 or expire_at > now_ts)
        )

        if device.get("voucher_code") == "WHITELIST":
            voucher_code = "WHITELIST"
            plan_name = "Whitelist"
            expire_at = 0
            has_valid_voucher = True
        elif has_valid_voucher:
            voucher_code = raw_voucher_code
            plan_name = device.get("speed_profile_name") or voucher_obj.get("speed_profile_name") or "-"
        elif raw_voucher_code and voucher_exists:
            voucher_code = "未登录"
            plan_name = "历史兑换码已过期"
            unauthenticated_realtime = True
        else:
            voucher_code = "未登录"
            plan_name = "未登录"
            expire_at = -1
            unauthenticated_realtime = True

        realtime_online = mac in realtime_online_macs

        # DEVICE_VALID_VOUCHER_CLASSIFY_V1
        # For the UI, a realtime device with a valid voucher should be treated as logged-in,
        # even if db["devices"][mac]["online"] was stale/False after DB self-heal or firewall reload.
        auth_online = bool(has_valid_voucher)
        # DEVICE_LIST_AUTH_ONLINE_ONLY_V1
        # "在线" means authenticated network access, not just WiFi association.
        # A kicked device may still be associated to WiFi, but it must be shown as 在线未登录.
        visible_online = bool(auth_online)

        if mac in db.get("blacklist", {}):
            status_text = "黑名单"
            status_key = "blocked"
        elif mac in db.get("whitelist", {}):
            status_text = "实时在线 / 白名单" if realtime_online else "白名单"
            status_key = "online" if visible_online else "offline"
        elif realtime_online and auth_online:
            status_text = "实时在线 / 已登录"
            status_key = "online"
        elif realtime_online:
            status_text = "WiFi在线 / 未登录"
            status_key = "guest"
        elif auth_online:
            status_text = "认证有效 / 当前不在线"
            status_key = "offline"
        else:
            status_text = "离线"
            status_key = "offline"

        total_count += 1
        filter_online = (status_key == "online")
        if filter_online:
            online_count += 1
        else:
            offline_count += 1

        if realtime_online and auth_online:
            online_authed_count += 1
        elif realtime_online and not auth_online:
            online_guest_count += 1

        prepared.append({
            "mac": mac,
            "device": device,
            "hostname": hostname,
            "ip": ip,
            "voucher_code": voucher_code,
            "plan_name": plan_name,
            "online": visible_online,
            "filter_online": filter_online,
            "auth_online": auth_online,
            "realtime_online": realtime_online,
            "expire_at": expire_at,
            "status_text": status_text,
            "status_key": status_key,
            "guest": False,
        })

    for mac, client in realtime_clients.items():
        if mac in devices:
            continue
        if not isinstance(client, dict):
            client = {}

        hostname = client.get("hostname") or "Unknown Device"
        ip = client.get("ip") or "-"
        voucher_code = "未登录"
        plan_name = "未登录"
        status_text = "实时在线 / 未登录"
        status_key = "online"

        total_count += 1
        online_count += 1
        online_guest_count += 1

        prepared.append({
            "mac": mac,
            "device": {
                "mac": mac,
                "ip": ip,
                "hostname": hostname,
                "voucher_code": voucher_code,
                "login_at": 0,
                "expire_at": -1,
                "last_seen": now_ts,
                "online": False,
                "download_kbps": 0,
                "upload_kbps": 0,
                "download_mbps": "-",
                "upload_mbps": "-",
                "speed_profile_name": plan_name,
            },
            "hostname": hostname,
            "ip": ip,
            "voucher_code": voucher_code,
            "plan_name": plan_name,
            "online": True,
            "filter_online": True,
            "auth_online": False,
            "realtime_online": True,
            "expire_at": -1,
            "status_text": status_text,
            "status_key": status_key,
            "guest": True,
        })

    plan_counts = {}
    plan_scope_total = 0
    for item in prepared:
        item_filter_online = bool(item.get("filter_online", False))
        item_auth_online = bool(item.get("auth_online", False))
        item_realtime_online = bool(item.get("realtime_online", False))

        if status_filter == "online" and not item_filter_online:
            continue
        if status_filter == "offline" and item_filter_online:
            continue
        if status_filter == "online_authed" and not (item_realtime_online and item_auth_online):
            continue
        if status_filter == "online_guest" and not (item_realtime_online and not item_auth_online):
            continue

        item_plan = str(item.get("plan_name") or "-")
        plan_counts[item_plan] = int(plan_counts.get(item_plan, 0)) + 1
        plan_scope_total += 1

    if plan_filter != "all" and plan_filter not in plan_counts:
        plan_filter = "all"

    filter_buttons = " ".join([
        device_filter_link("online", "在线", online_count),
        device_filter_link("offline", "离线", offline_count),
        device_filter_link("all", "全部", total_count),
        device_filter_link("online_authed", "在线已登录", online_authed_count),
        device_filter_link("online_guest", "在线未登录", online_guest_count),
    ])

    plan_options = []
    plan_options.append('<option value="all"' + (' selected' if plan_filter == 'all' else '') + '>套餐：全部 (' + str(plan_scope_total) + ')</option>')
    for plan_name in sorted(plan_counts.keys()):
        selected = " selected" if plan_filter == plan_name else ""
        plan_options.append('<option value="' + esc(plan_name) + '"' + selected + '>套餐：' + esc(plan_name) + ' (' + str(plan_counts.get(plan_name, 0)) + ')</option>')

    plan_select_html = '<select name="plan" class="dense-plan-select" onchange="this.form.submit()">' + "".join(plan_options) + '</select>'

    for item in sorted(prepared, key=lambda x: (
        0 if x["realtime_online"] else 1,
        0 if x["online"] else 1,
        str(x["ip"]),
        str(x["mac"])
    )):
        mac = item["mac"]
        device = item["device"]
        hostname = item["hostname"]
        ip = item["ip"]
        voucher_code = item["voucher_code"]
        plan_name = item["plan_name"]
        visible_online = item["online"]
        filter_online = item["filter_online"]
        realtime_online = item["realtime_online"]
        expire_at = item["expire_at"]
        status_text = item["status_text"]
        status_key = item["status_key"]
        guest = bool(item.get("guest", False))

        item_auth_online = bool(item.get("auth_online", False))
        item_realtime_online = bool(item.get("realtime_online", False))

        if status_filter == "online" and not filter_online:
            continue
        if status_filter == "offline" and filter_online:
            continue
        if status_filter == "online_authed" and not (item_realtime_online and item_auth_online):
            continue
        if status_filter == "online_guest" and not (item_realtime_online and not item_auth_online):
            continue
        if plan_filter != "all" and plan_name != plan_filter:
            continue

        search_blob = " ".join([
            str(hostname),
            str(ip),
            str(mac),
            str(voucher_code),
            str(plan_name),
            str(status_text),
        ]).lower()

        if search_lower and search_lower not in search_blob:
            continue

        shown_count += 1

        has_valid_voucher = bool(item.get("auth_online", False))

        if guest or not has_valid_voucher:
            remaining = "-"
            expire_text = "-"
        elif visible_online and expire_at == 0:
            remaining = "永久"
            expire_text = "永久"
        elif visible_online and expire_at > 0:
            seconds = max(0, expire_at - now_ts)
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            minutes = (seconds % 3600) // 60
            if days > 0:
                remaining = f"{days}天 {hours}小时"
            elif hours > 0:
                remaining = f"{hours}小时 {minutes}分钟"
            else:
                remaining = f"{minutes}分钟"
            expire_text = format_time(expire_at)
        else:
            remaining = "-"
            expire_text = "-"

        login_text = format_time(device.get("login_at", 0))
        last_text = format_time(device.get("last_seen", 0))

        down = device.get("download_mbps", "")
        up = device.get("upload_mbps", "")
        if down == "":
            down = kbps_to_mbps(device.get("download_kbps", 0))
        if up == "":
            up = kbps_to_mbps(device.get("upload_kbps", 0))

        limit_speed_text = f"{down}↓/{up}↑"

        if realtime_online:
            speed_item = realtime_speeds.get(mac, {})
            realtime_download = speed_item.get("download", "刷新后显示")
            realtime_upload = speed_item.get("upload", "刷新后显示")
            realtime_speed_text = f"{realtime_download}↓ / {realtime_upload}↑"
        else:
            realtime_speed_text = "当前不在线"

        status_badge = device_status_badge(status_text, status_key)

        rows.append(f"""
<tr data-device-row="{esc(mac)}" data-expire-at="{int(expire_at or 0)}">
<td class="dense-code-col">
  <b>{esc(hostname)}</b>
  <div class="dense-sub">{esc(ip)}</div>
</td>
<td>
  <code>{esc(mac)}</code>
</td>
<td>
  <code>{esc(voucher_code)}</code>
  <div class="dense-sub">{esc(plan_name)}</div>
</td>
<td class="dense-status-col">
  {status_badge}
  <div class="dense-sub">剩余：<span class="device-countdown" data-countdown-mac="{esc(mac)}" data-expire-at="{int(expire_at or 0)}" data-online="{1 if (visible_online and not guest and bool(item.get("auth_online", False))) else 0}">{esc(remaining)}</span></div>
</td>
<td>
  <b class="device-realtime-speed" data-speed-mac="{esc(mac)}">{esc(realtime_speed_text)}</b>
  <div class="dense-sub">实时下载 / 上传</div>
</td>
<td>
  <b>{esc(limit_speed_text)}</b>
  <div class="dense-sub">套餐限速 Mbps</div>
</td>
<td>
  <b>{esc(expire_text)}</b>
  <div class="dense-sub">倒计时：<span class="device-expire-countdown" data-expire-countdown-mac="{esc(mac)}" data-expire-at="{int(expire_at or 0)}" data-online="{1 if (visible_online and not guest and bool(item.get("auth_online", False))) else 0}">{esc(remaining)}</span></div>
  <div class="dense-sub">登录：{esc(login_text)}</div>
</td>
<td>
  <b>{esc(last_text)}</b>
</td>
<td class="dense-actions-col">
  <div class="dense-actions-main">
    <form method="post" action="/admin/device-kick">
      <input type="hidden" name="mac" value="{esc(mac)}">
      <button type="submit" class="dense-mini-btn">踢下线</button>
    </form>

    <form method="post" action="/admin/device-unbind" onsubmit="return confirm('确认解绑这个设备？')">
      <input type="hidden" name="mac" value="{esc(mac)}">
      <button type="submit" class="danger dense-mini-btn">解绑</button>
    </form>

    <details class="dense-more">
      <summary>更多</summary>
      <form method="post" action="/admin/blacklist-add" onsubmit="return confirm('确认加入黑名单？')">
        <input type="hidden" name="mac" value="{esc(mac)}">
        <input type="hidden" name="device_name" value="{esc(hostname)}">
        <input type="hidden" name="reason" value="Blocked from devices page">
        <button type="submit" class="danger dense-mini-btn">拉黑</button>
      </form>
    </details>
  </div>
</td>
</tr>
""")

    filter_label = {
        "online": "在线",
        "offline": "离线",
        "all": "全部",
        "online_authed": "在线已登录",
        "online_guest": "在线未登录",
    }.get(status_filter, "在线")

    plan_label = "全部" if plan_filter == "all" else plan_filter

    body = f"""
<div class="card dense-top-card">
<h1>在线设备</h1>
<p class="muted">紧凑总览模式：一行一个设备，样式与兑换码列表一致，并显示实时网速。</p>
<div class="dense-stat-row">
<a class="dense-stat" href="/admin/devices?status=online&plan={esc(urllib.parse.quote(plan_filter))}&q={esc(urllib.parse.quote(search_text))}">在线<b>{online_count}</b></a>
<a class="dense-stat" href="/admin/devices?status=offline&plan={esc(urllib.parse.quote(plan_filter))}&q={esc(urllib.parse.quote(search_text))}">离线<b>{offline_count}</b></a>
<a class="dense-stat" href="/admin/devices?status=all&plan={esc(urllib.parse.quote(plan_filter))}&q={esc(urllib.parse.quote(search_text))}">全部<b>{total_count}</b></a>
<a class="dense-stat" href="#">实时<b>{realtime_count}</b></a>
<a class="dense-stat" href="#">显示<b>{shown_count}</b></a>
</div>
</div>

<div class="card dense-search-card">
<form method="get" action="/admin/devices" class="dense-search-form">
<input type="hidden" name="status" value="{esc(status_filter)}">
{plan_select_html}
<input name="q" value="{esc(search_text)}" placeholder="搜索设备名、IP、MAC、兑换码、套餐、状态">
<button type="submit">搜索</button>
<a class="btn dense-reset-filter-btn" href="/admin/devices">重置筛选</a>
</form>
<div class="dense-filter-row">{filter_buttons}</div>
</div>

<style>
.dense-search-form .dense-reset-filter-btn {{
  width: auto !important;
  max-width: 96px !important;
  min-width: 76px !important;
  padding: 8px 12px !important;
  white-space: nowrap !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  justify-self: start !important;
  flex: 0 0 auto !important;
}}

@media(max-width:760px) {{
  .dense-search-form .dense-reset-filter-btn {{
    width: auto !important;
    max-width: 96px !important;
    min-width: 76px !important;
    justify-self: start !important;
  }}
}}

.dense-plan-select {{
  min-width: 180px;
  height: 38px;
  border-radius: 10px;
  border: 1px solid rgba(120,120,120,.35);
  padding: 0 10px;
  font-weight: 700;
}}
</style>

<div class="card dense-list-card">
<h2>设备列表</h2>
<p class="muted">筛选：{esc(filter_label)}；套餐：{esc(plan_label)}；搜索：{esc(search_text or "无")}；当前显示 {shown_count} 台。</p>
<table class="voucher-dense-table">
<tr>
<th>设备 / IP</th>
<th>MAC</th>
<th>兑换码 / 套餐</th>
<th>状态 / 剩余</th>
<th>实时网速</th>
<th>套餐限速</th>
<th>到期 / 登录</th>
<th>最后在线</th>
<th>操作</th>
</tr>
{''.join(rows) if rows else '<tr><td colspan="9" class="muted">暂无符合条件的设备</td></tr>'}
</table>
<script>
(function() {{
  function formatSeconds(seconds) {{
    seconds = Math.max(0, Math.floor(seconds || 0));
    var days = Math.floor(seconds / 86400);
    var hours = Math.floor((seconds % 86400) / 3600);
    var minutes = Math.floor((seconds % 3600) / 60);
    var secs = seconds % 60;

    if (days > 0) {{
      return days + '天 ' + hours + '小时 ' + minutes + '分钟 ' + secs + '秒';
    }}
    if (hours > 0) {{
      return hours + '小时 ' + minutes + '分钟 ' + secs + '秒';
    }}
    if (minutes > 0) {{
      return minutes + '分钟 ' + secs + '秒';
    }}
    return secs + '秒';
  }}

  function updateCountdowns() {{
    var nowSec = Math.floor(Date.now() / 1000);

    var items = document.querySelectorAll('.device-countdown, .device-expire-countdown');
    for (var i = 0; i < items.length; i++) {{
      var el = items[i];
      var expireAt = parseInt(el.getAttribute('data-expire-at') || '0', 10);
      var online = el.getAttribute('data-online') === '1';

      if (!online) {{
        el.textContent = '-';
        continue;
      }}

      if (expireAt === 0) {{
        el.textContent = '永久';
        continue;
      }}

      var left = expireAt - nowSec;
      if (left <= 0) {{
        el.textContent = '已过期';
      }} else {{
        el.textContent = formatSeconds(left);
      }}
    }}
  }}

  function updateRealtimeSpeeds() {{
    fetch('/admin/api/devices-realtime?ts=' + Date.now(), {{
      cache: 'no-store',
      credentials: 'same-origin'
    }})
    .then(function(resp) {{
      if (!resp.ok) {{
        throw new Error('HTTP ' + resp.status);
      }}
      return resp.json();
    }})
    .then(function(data) {{
      if (!data || !data.devices) {{
        return;
      }}

      var speedEls = document.querySelectorAll('.device-realtime-speed');
      for (var i = 0; i < speedEls.length; i++) {{
        var el = speedEls[i];
        var mac = el.getAttribute('data-speed-mac');
        var item = data.devices[mac];

        if (!item || !item.realtime_online) {{
          el.textContent = '当前不在线';
          continue;
        }}

        var download = item.download || '0.00 Mbps';
        var upload = item.upload || '0.00 Mbps';
        el.textContent = download + '↓ / ' + upload + '↑';
      }}
    }})
    .catch(function() {{
      // 静默失败，避免影响后台页面使用
    }});
  }}

  updateCountdowns();
  updateRealtimeSpeeds();

  setInterval(updateCountdowns, 1000);
  setInterval(updateRealtimeSpeeds, 2000);
}})();
</script>
</div>
"""
    self.send_html(admin_page("在线设备", body))



def _wp_admin_devices_realtime_api(self):
    try:
        db = load_db()
    except Exception:
        db = {}

    devices = db.get("devices", {}) if isinstance(db, dict) else {}
    if not isinstance(devices, dict):
        devices = {}

    try:
        realtime_clients = _wp_collect_current_wifi_clients_12h()
    except Exception:
        realtime_clients = {}

    if not isinstance(realtime_clients, dict):
        realtime_clients = {}

    try:
        realtime_speeds = _wp_get_realtime_wifi_speeds(realtime_clients)
    except Exception:
        realtime_speeds = {}

    if not isinstance(realtime_speeds, dict):
        realtime_speeds = {}

    now_ts = now()
    result_devices = {}

    all_macs = set()
    all_macs.update(devices.keys())
    all_macs.update(realtime_clients.keys())

    for mac in all_macs:
        device = devices.get(mac, {}) if isinstance(devices.get(mac, {}), dict) else {}
        client = realtime_clients.get(mac, {}) if isinstance(realtime_clients.get(mac, {}), dict) else {}
        speed = realtime_speeds.get(mac, {}) if isinstance(realtime_speeds.get(mac, {}), dict) else {}

        expire_at = int(device.get("expire_at", 0) or 0)
        auth_online = bool(device.get("online", False))
        if expire_at > 0 and expire_at <= now_ts:
            auth_online = False

        realtime_online = mac in realtime_clients
        visible_online = bool(auth_online or realtime_online)

        result_devices[mac] = {
            "mac": mac,
            "ip": client.get("ip") or device.get("ip") or "",
            "hostname": client.get("hostname") or device.get("hostname") or "Unknown Device",
            "realtime_online": realtime_online,
            "auth_online": auth_online,
            "visible_online": visible_online,
            "expire_at": expire_at,
            "download": speed.get("download", "0.00 Mbps") if realtime_online else "",
            "upload": speed.get("upload", "0.00 Mbps") if realtime_online else "",
        }

    payload = {
        "ok": True,
        "now": now_ts,
        "count": len(result_devices),
        "realtime_count": len(realtime_clients),
        "devices": result_devices,
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    self.send_response(200)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Cache-Control", "no-store")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)


Handler.admin_devices_realtime_api = _wp_admin_devices_realtime_api


Handler.show_admin_devices = _wp_show_admin_devices_v6



# QUIET_SERVER_CLIENT_DISCONNECT_V1
class QuietThreadingHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        import sys
        error_type, error_value, _ = sys.exc_info()
        if error_type in (BrokenPipeError, ConnectionResetError):
            return
        try:
            if isinstance(error_value, (BrokenPipeError, ConnectionResetError)):
                return
        except Exception:
            pass
        return super().handle_error(request, client_address)

# FAST_START_HTTP_FIRST_V1
# Start HTTP listener first, then restore nft/firewall/QoS in background.
# This avoids long restart windows where 127.0.0.1:80 returns Errno 111.

def _wp_startup_network_restore_background():
    try:
        ok, message = nft_init_table()
        if ok:
            restore_firewall_sessions()
            qos_restore_sessions()
            print("WiFi Portal firewall/QoS initialized in background", flush=True)
            try:
                append_log("SYSTEM", "防火墙和限速已在后台恢复")
            except Exception:
                pass
        else:
            print(f"WiFi Portal firewall init failed: {message}", flush=True)
            try:
                append_log("SYSTEM", f"防火墙初始化失败：{message}", result="FAIL")
            except Exception:
                pass
    except Exception as error:
        print(f"WiFi Portal background network restore failed: {error}", flush=True)
        try:
            append_log("SYSTEM", f"后台恢复防火墙/限速失败：{error}", result="FAIL")
        except Exception:
            pass


def main():
    print(f"WiFi Portal Web starting on 0.0.0.0:{PORTAL_PORT}", flush=True)

    worker = threading.Thread(target=background_worker, daemon=True)
    worker.start()

    network_worker = threading.Thread(target=_wp_startup_network_restore_background, daemon=True)
    network_worker.start()

    try:
        append_log("SYSTEM", "认证系统启动")
    except Exception as error:
        print(f"WiFi Portal startup log failed: {error}", flush=True)

    httpd = QuietThreadingHTTPServer(("0.0.0.0", PORTAL_PORT), Handler)
    print(f"WiFi Portal Web listening on 0.0.0.0:{PORTAL_PORT}", flush=True)
    httpd.serve_forever()



# MAINTENANCE_TOOLS_V1
# Local admin maintenance page: health check, cleanup expired history, repair DB/nft mismatch.

def _wp_maintenance_escape(value):
    try:
        return esc(value)
    except Exception:
        import html
        return html.escape(str(value))


def _wp_maintenance_collect_state():
    import subprocess
    import time

    report = {
        "ok": True,
        "now": now(),
        "service": {},
        "counts": {},
        "issues": {
            "valid_online_missing_nft": [],
            "nft_authed_but_db_offline": [],
            "expired_still_online": [],
            "realtime_guest_with_expired_history": [],
        },
        "warnings": [],
    }

    try:
        db = load_db()
    except Exception as error:
        report["ok"] = False
        report["warnings"].append("load_db failed: " + str(error))
        db = {}

    devices = db.get("devices", {}) if isinstance(db.get("devices", {}), dict) else {}
    vouchers = db.get("vouchers", {}) if isinstance(db.get("vouchers", {}), dict) else {}

    try:
        realtime = _wp_collect_current_wifi_clients_12h()
    except Exception as error:
        realtime = {}
        report["warnings"].append("collect realtime clients failed: " + str(error))

    if not isinstance(realtime, dict):
        realtime = {}

    try:
        nft_authed = subprocess.getoutput("nft list set inet wifiportal authed_macs 2>/dev/null").lower()
    except Exception:
        nft_authed = ""

    try:
        nft_black = subprocess.getoutput("nft list set inet wifiportal blacklist_macs 2>/dev/null").lower()
    except Exception:
        nft_black = ""

    try:
        nft_white = subprocess.getoutput("nft list set inet wifiportal whitelist_macs 2>/dev/null").lower()
    except Exception:
        nft_white = ""

    now_ts = now()
    db_online_count = 0
    valid_voucher_count = 0

    for mac, device in devices.items():
        if not isinstance(device, dict):
            continue

        code = str(device.get("voucher_code", "") or "").strip()
        voucher = vouchers.get(code) if code else None
        voucher_exists = isinstance(voucher, dict)

        expire_at = int(device.get("expire_at", 0) or 0)
        if expire_at <= 0 and voucher_exists:
            expire_at = int(voucher.get("expire_at", 0) or 0)

        voucher_valid = bool(code and voucher_exists and (expire_at == 0 or expire_at > now_ts))
        db_online = bool(device.get("online"))
        mac_in_nft = str(mac).lower() in nft_authed
        realtime_online = mac in realtime

        if db_online:
            db_online_count += 1

        if voucher_valid:
            valid_voucher_count += 1

        if db_online and not voucher_valid and code != "WHITELIST":
            report["issues"]["expired_still_online"].append({
                "mac": mac,
                "ip": device.get("ip", ""),
                "voucher": code,
                "remain": expire_at - now_ts,
            })

        if voucher_valid and db_online and not mac_in_nft and code != "WHITELIST":
            report["issues"]["valid_online_missing_nft"].append({
                "mac": mac,
                "ip": device.get("ip", ""),
                "voucher": code,
                "remain": "permanent" if expire_at == 0 else expire_at - now_ts,
            })

        if mac_in_nft and (not db_online) and code != "WHITELIST":
            report["issues"]["nft_authed_but_db_offline"].append({
                "mac": mac,
                "ip": device.get("ip", ""),
                "voucher": code,
                "remain": "permanent" if expire_at == 0 else expire_at - now_ts,
            })

        if realtime_online and code and voucher_exists and not voucher_valid and not mac_in_nft:
            report["issues"]["realtime_guest_with_expired_history"].append({
                "mac": mac,
                "ip": realtime.get(mac, {}).get("ip") or device.get("ip", ""),
                "hostname": realtime.get(mac, {}).get("hostname") or device.get("hostname", ""),
                "voucher": code,
                "remain": expire_at - now_ts,
            })

    report["counts"] = {
        "devices": len(devices),
        "vouchers": len(vouchers),
        "realtime_wifi_clients": len(realtime),
        "db_online_devices": db_online_count,
        "valid_voucher_devices": valid_voucher_count,
        "nft_authed_rough_count": nft_authed.count(":") // 5,
        "blacklist_nft_present": bool(nft_black),
        "whitelist_nft_present": bool(nft_white),
    }

    try:
        code, out, err = run_command(["/bin/sh", "-c", "ps | grep wifiportal | grep -v grep | head -n 3"])
        report["service"]["process"] = out.strip()
    except Exception:
        report["service"]["process"] = ""

    try:
        code, out, err = run_command(["/bin/sh", "-c", "netstat -lntp 2>/dev/null | grep ':80 ' | head -n 3"])
        report["service"]["listen80"] = out.strip()
    except Exception:
        report["service"]["listen80"] = ""

    try:
        report["service"]["firewall"] = firewall_status_text()
    except Exception:
        report["service"]["firewall"] = "未知"

    total_issue_count = sum(len(v) for v in report["issues"].values() if isinstance(v, list))
    report["ok"] = total_issue_count == 0 and not report["warnings"]

    return report


def _wp_maintenance_cleanup_expired_history():
    import subprocess

    db = load_db()
    devices = db.get("devices", {}) if isinstance(db.get("devices", {}), dict) else {}
    vouchers = db.get("vouchers", {}) if isinstance(db.get("vouchers", {}), dict) else {}

    try:
        realtime = _wp_collect_current_wifi_clients_12h()
    except Exception:
        realtime = {}

    if not isinstance(realtime, dict):
        realtime = {}

    try:
        nft_authed = subprocess.getoutput("nft list set inet wifiportal authed_macs 2>/dev/null").lower()
    except Exception:
        nft_authed = ""

    now_ts = now()
    cleaned = []

    for mac, device in list(devices.items()):
        if not isinstance(device, dict):
            continue

        code = str(device.get("voucher_code", "") or "").strip()
        if not code or code == "WHITELIST":
            continue

        voucher = vouchers.get(code)
        if not isinstance(voucher, dict):
            continue

        expire_at = int(device.get("expire_at", 0) or 0)
        if expire_at <= 0:
            expire_at = int(voucher.get("expire_at", 0) or 0)

        expired = bool(expire_at > 0 and expire_at <= now_ts)
        mac_in_nft = str(mac).lower() in nft_authed
        db_online = bool(device.get("online"))

        # Safety: only clean stale history if it is not an active authenticated session.
        if expired and (not db_online) and (not mac_in_nft):
            old_code = code
            old_plan = str(device.get("speed_profile_name", "") or "")

            device["voucher_code"] = ""
            device["speed_profile_name"] = ""
            device["download_kbps"] = 0
            device["upload_kbps"] = 0
            device["download_mbps"] = "-"
            device["upload_mbps"] = "-"
            device["expire_at"] = 0
            device["login_at"] = 0
            device["online"] = False
            device["last_seen"] = now_ts

            try:
                if isinstance(voucher.get("devices", {}), dict) and mac in voucher["devices"]:
                    voucher["devices"][mac]["online"] = False
                    voucher["devices"][mac]["last_seen"] = now_ts
            except Exception:
                pass

            cleaned.append({
                "mac": mac,
                "ip": device.get("ip", ""),
                "old_voucher": old_code,
                "old_plan": old_plan,
            })

    if cleaned:
        save_db(db)
        append_log("MAINTENANCE", "清理过期历史设备记录 " + str(len(cleaned)) + " 条")

    return cleaned


def _wp_maintenance_repair_state():
    import subprocess

    db = load_db()
    devices = db.get("devices", {}) if isinstance(db.get("devices", {}), dict) else {}
    vouchers = db.get("vouchers", {}) if isinstance(db.get("vouchers", {}), dict) else {}

    now_ts = now()

    try:
        nft_authed = subprocess.getoutput("nft list set inet wifiportal authed_macs 2>/dev/null").lower()
    except Exception:
        nft_authed = ""

    repaired = {
        "allowed_missing_nft": [],
        "kicked_expired_online": [],
        "kicked_nft_without_db_online": [],
        "whitelist_restored": [],
    }

    for mac, device in devices.items():
        if not isinstance(device, dict):
            continue

        code = str(device.get("voucher_code", "") or "").strip()
        voucher = vouchers.get(code) if code else None
        voucher_exists = isinstance(voucher, dict)

        expire_at = int(device.get("expire_at", 0) or 0)
        if expire_at <= 0 and voucher_exists:
            expire_at = int(voucher.get("expire_at", 0) or 0)

        voucher_valid = bool(code and voucher_exists and (expire_at == 0 or expire_at > now_ts))
        db_online = bool(device.get("online"))
        mac_in_nft = str(mac).lower() in nft_authed

        if code == "WHITELIST":
            nft_add_whitelist(mac)
            repaired["whitelist_restored"].append(mac)
            continue

        if db_online and not voucher_valid:
            nft_kick_device(mac)
            safe_qos_remove_device(mac)
            device["online"] = False
            device["last_seen"] = now_ts
            repaired["kicked_expired_online"].append(mac)
            continue

        if voucher_valid and db_online and not mac_in_nft:
            remaining = 0 if expire_at == 0 else max(1, expire_at - now_ts)
            nft_allow_device(mac, remaining)
            repaired["allowed_missing_nft"].append(mac)
            continue

        if mac_in_nft and not db_online:
            nft_kick_device(mac)
            safe_qos_remove_device(mac)
            repaired["kicked_nft_without_db_online"].append(mac)

    save_db(db)
    append_log("MAINTENANCE", "执行 DB/nft 状态修复")
    return repaired




def _wp_maintenance_table(title, items):
    if not items:
        return "<p class='muted' style='margin:6px 0'>无异常</p>"

    rows = []
    for item in items[:200]:
        if isinstance(item, dict):
            if not rows:
                heads = "".join("<th>" + _wp_maintenance_escape(k) + "</th>" for k in item.keys())
                rows.append("<tr>" + heads + "</tr>")
            cells = "".join("<td>" + _wp_maintenance_escape(v) + "</td>" for v in item.values())
            rows.append("<tr>" + cells + "</tr>")
        else:
            rows.append("<tr><td>" + _wp_maintenance_escape(item) + "</td></tr>")

    return "<div style='overflow:auto;max-height:220px'><table class='dense-table'>" + "".join(rows) + "</table></div>"


def _wp_maintenance_issue_card(title, items):
    count = len(items) if isinstance(items, list) else 0
    badge_color = "#16a34a" if count == 0 else "#dc2626"
    return f"""
<div class="card maintenance-mini-card">
  <div class="maintenance-line-title">
    <h2>{_wp_maintenance_escape(title)}</h2>
    <b style="background:{badge_color}">{count}</b>
  </div>
  {_wp_maintenance_table(title, items)}
</div>
"""


def _wp_maintenance_page(self, notice=""):
    # MAINTENANCE_ORIGINAL_COMPACT_UI_V1
    report = _wp_maintenance_collect_state()
    counts = report.get("counts", {})
    issues = report.get("issues", {})

    valid_missing = issues.get("valid_online_missing_nft", [])
    nft_db_offline = issues.get("nft_authed_but_db_offline", [])
    expired_online = issues.get("expired_still_online", [])
    expired_history = issues.get("realtime_guest_with_expired_history", [])
    warnings = report.get("warnings", [])

    total_issue_count = (
        len(valid_missing)
        + len(nft_db_offline)
        + len(expired_online)
        + len(expired_history)
        + len(warnings)
    )

    status_text = "健康" if total_issue_count == 0 else "需要处理"
    status_color = "#16a34a" if total_issue_count == 0 else "#dc2626"

    notice_html = ""
    if notice:
        notice_html = f"""
<div class="card maintenance-compact-card">
  <div class="info" style="margin:0">{_wp_maintenance_escape(notice)}</div>
</div>
"""

    body = f"""
<style>
.maintenance-compact-wrap .card {{
  margin: 8px 0;
  padding: 12px;
}}

.maintenance-compact-wrap h1 {{
  margin: 0 0 4px;
  font-size: 22px;
}}

.maintenance-compact-wrap h2 {{
  margin: 0;
  font-size: 15px;
}}

.maintenance-compact-wrap .muted {{
  font-size: 12px;
}}

.maintenance-top {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}}

.maintenance-status-badge {{
  display: inline-block;
  color: #fff;
  border-radius: 999px;
  padding: 5px 12px;
  font-weight: 800;
  font-size: 13px;
}}

.maintenance-stats {{
  display: grid;
  grid-template-columns: repeat(6, minmax(100px, 1fr));
  gap: 8px;
  margin-top: 10px;
}}

.maintenance-stats .stat {{
  margin: 0;
  min-height: auto;
  padding: 8px 10px;
}}

.maintenance-stats .stat b {{
  font-size: 20px;
  line-height: 1.1;
}}

.maintenance-actions {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}}

.maintenance-actions form {{
  margin: 0;
}}

.maintenance-actions button,
.maintenance-actions .btn {{
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.1;
}}

.maintenance-grid {{
  display: grid;
  grid-template-columns: repeat(2, minmax(280px, 1fr));
  gap: 8px;
}}

.maintenance-mini-card {{
  margin: 0 !important;
}}

.maintenance-line-title {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}}

.maintenance-line-title b {{
  color: #fff;
  min-width: 26px;
  text-align: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
}}

.dense-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}}

.dense-table th,
.dense-table td {{
  padding: 5px 7px;
  border-bottom: 1px solid rgba(148,163,184,.18);
  white-space: nowrap;
}}

.dense-table th {{
  text-align: left;
  color: #cbd5e1;
  font-weight: 800;
}}

.maintenance-service-table td:first-child {{
  width: 130px;
  color: #94a3b8;
}}

@media (max-width: 900px) {{
  .maintenance-stats {{
    grid-template-columns: repeat(2, minmax(100px, 1fr));
  }}
  .maintenance-grid {{
    grid-template-columns: 1fr;
  }}
}}
</style>

<div class="maintenance-compact-wrap">
{notice_html}

<div class="card maintenance-compact-card">
  <div class="maintenance-top">
    <div>
      <h1>维护工具</h1>
      <p class="muted" style="margin:0">检查和修复 DB / nft / 实时在线状态。建议先检查，再修复。</p>
    </div>
    <span class="maintenance-status-badge" style="background:{status_color}">{_wp_maintenance_escape(status_text)} · 异常 {total_issue_count}</span>
  </div>

  <div class="maintenance-stats">
    <div class="stat">实时在线<b>{counts.get('realtime_wifi_clients', 0)}</b></div>
    <div class="stat">DB 在线<b>{counts.get('db_online_devices', 0)}</b></div>
    <div class="stat">nft 放行<b>{counts.get('nft_authed_rough_count', 0)}</b></div>
    <div class="stat">有效设备<b>{counts.get('valid_voucher_devices', 0)}</b></div>
    <div class="stat">设备记录<b>{counts.get('devices', 0)}</b></div>
    <div class="stat">兑换码<b>{counts.get('vouchers', 0)}</b></div>
  </div>
</div>

<div class="card maintenance-compact-card">
  <div class="maintenance-top">
    <h2>操作</h2>
    <div class="maintenance-actions">
      <form method="post" action="/admin/maintenance/run">
        <input type="hidden" name="action" value="health">
        <button type="submit">一键健康检查</button>
      </form>

      <form method="post" action="/admin/maintenance/run">
        <input type="hidden" name="action" value="cleanup_history">
        <button type="submit" onclick="return confirm('确认清理过期历史设备记录？不会影响有效在线用户。')">清理过期历史</button>
      </form>

      <form method="post" action="/admin/maintenance/run">
        <input type="hidden" name="action" value="repair_state">
        <button type="submit" onclick="return confirm('确认修复 DB/nft 状态不一致？会重新放行有效在线设备，并踢掉异常过期放行。')">修复 DB/nft</button>
      </form>
    </div>
  </div>
  <p class="muted" style="margin:8px 0 0">清理历史只处理已过期且未在线放行的旧记录；修复 DB/nft 会处理异常放行状态。</p>
</div>

<div class="maintenance-grid">
  {_wp_maintenance_issue_card("有效在线但缺少 nft 放行", valid_missing)}
  {_wp_maintenance_issue_card("nft 已放行但 DB 不在线", nft_db_offline)}
  {_wp_maintenance_issue_card("已过期但仍在线", expired_online)}
  {_wp_maintenance_issue_card("实时在线但只剩过期历史兑换码", expired_history)}
</div>

<div class="card maintenance-compact-card">
  <div class="maintenance-line-title">
    <h2>服务状态</h2>
  </div>
  <table class="dense-table maintenance-service-table">
    <tr><td>防火墙</td><td>{_wp_maintenance_escape(report.get('service', {}).get('firewall', '未知'))}</td></tr>
    <tr><td>80 端口</td><td><code>{_wp_maintenance_escape(report.get('service', {}).get('listen80', ''))}</code></td></tr>
    <tr><td>进程</td><td><code>{_wp_maintenance_escape(report.get('service', {}).get('process', ''))}</code></td></tr>
  </table>
</div>
"""

    if warnings:
        body += f"""
<div class="card maintenance-compact-card">
  <div class="maintenance-line-title"><h2>警告</h2><b style="background:#dc2626">{len(warnings)}</b></div>
  {_wp_maintenance_table("warnings", warnings)}
</div>
"""

    body += "</div>"

    self.send_html(admin_page("维护工具", body))

def _wp_maintenance_post(self):
    form = self.read_form()
    action = str(form.get("action", "") or "").strip()
    notice = ""

    if action == "health":
        notice = "健康检查已完成。"
    elif action == "cleanup_history":
        cleaned = _wp_maintenance_cleanup_expired_history()
        notice = "已清理过期历史设备记录：" + str(len(cleaned)) + " 条。"
    elif action == "repair_state":
        repaired = _wp_maintenance_repair_state()
        total = 0
        for value in repaired.values():
            if isinstance(value, list):
                total += len(value)
        notice = "DB/nft 状态修复完成，处理：" + str(total) + " 项。"
    else:
        notice = "未知操作。"

    try:
        append_admin_audit(self, "维护工具", "action=" + action + " notice=" + notice)
    except Exception:
        pass

    _wp_maintenance_page(self, notice)


_wp_old_handle_admin_get_maintenance_v1 = Handler.handle_admin_get
_wp_old_handle_admin_post_maintenance_v1 = Handler.handle_admin_post


def _wp_handle_admin_get_maintenance_v1(self, path):
    if path in ["/admin/maintenance", "/admin/maintenance-tools"]:
        if not self.require_admin():
            return
        _wp_maintenance_page(self)
        return
    return _wp_old_handle_admin_get_maintenance_v1(self, path)


def _wp_handle_admin_post_maintenance_v1(self, path):
    if path == "/admin/maintenance/run":
        if not self.require_admin():
            return
        _wp_maintenance_post(self)
        return
    return _wp_old_handle_admin_post_maintenance_v1(self, path)


Handler.handle_admin_get = _wp_handle_admin_get_maintenance_v1
Handler.handle_admin_post = _wp_handle_admin_post_maintenance_v1





# ADMIN_BACKUP_RESTORE_TOOLS_V1
# Local backup/restore tools for WiFiPortal admin.

def _wp_backup_dir():
    return "/etc/wifiportal/admin-backups"


def _wp_safe_backup_name(value):
    value = str(value or "").strip()
    allow = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    value = "".join(ch for ch in value if ch in allow)
    if not value.endswith(".tar.gz"):
        return ""
    if "/" in value or ".." in value:
        return ""
    return value


def _wp_list_admin_backups():
    import os
    backup_dir = _wp_backup_dir()
    try:
        names = []
        for name in os.listdir(backup_dir):
            safe = _wp_safe_backup_name(name)
            if not safe:
                continue
            path = os.path.join(backup_dir, safe)
            try:
                st = os.stat(path)
            except Exception:
                continue
            names.append({
                "name": safe,
                "path": path,
                "size": st.st_size,
                "mtime": int(st.st_mtime),
            })
        names.sort(key=lambda x: x.get("mtime", 0), reverse=True)
        return names
    except Exception:
        return []


def _wp_create_admin_backup(reason="manual"):
    import os
    import tarfile
    import time

    backup_dir = _wp_backup_dir()
    os.makedirs(backup_dir, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = "wifiportal-backup-" + stamp + ".tar.gz"
    out_path = os.path.join(backup_dir, name)
    tmp_path = out_path + ".tmp"

    files = [
        ("/usr/lib/wifiportal/wifiportal.py", "wifiportal.py"),
        ("/etc/wifiportal/vouchers.json", "vouchers.json"),
        ("/etc/wifiportal/settings.json", "settings.json"),
        ("/etc/config/network", "openwrt-network"),
        ("/etc/config/firewall", "openwrt-firewall"),
        ("/etc/config/dhcp", "openwrt-dhcp"),
        ("/etc/init.d/wifiportal", "init.d-wifiportal"),
    ]

    manifest = {
        "created_at": int(time.time()),
        "reason": str(reason or "manual"),
        "files": [src for src, arc in files],
    }

    import json
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

    with tarfile.open(tmp_path, "w:gz") as tar:
        import io
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest_bytes)
        info.mtime = int(time.time())
        tar.addfile(info, io.BytesIO(manifest_bytes))

        for src, arc in files:
            if os.path.exists(src):
                tar.add(src, arcname=arc)

    os.rename(tmp_path, out_path)

    append_log("BACKUP", "创建后台备份 " + name)
    try:
        append_admin_audit(None, "创建备份", "name=" + name + " reason=" + str(reason or "manual"))
    except Exception:
        pass

    return {
        "name": name,
        "path": out_path,
        "size": os.path.getsize(out_path),
    }


def _wp_prune_admin_backups(keep=7):
    import os
    backups = _wp_list_admin_backups()
    removed = []
    for item in backups[int(keep):]:
        path = item.get("path", "")
        name = item.get("name", "")
        try:
            os.remove(path)
            removed.append(name)
        except Exception:
            pass

    if removed:
        append_log("BACKUP", "清理旧备份 " + str(len(removed)) + " 个")

    return removed


def _wp_restore_admin_backup(name):
    import os
    import tarfile
    import shutil
    import time

    safe = _wp_safe_backup_name(name)
    if not safe:
        raise ValueError("非法备份文件名")

    backup_path = os.path.join(_wp_backup_dir(), safe)
    if not os.path.exists(backup_path):
        raise FileNotFoundError("备份不存在：" + safe)

    restore_safety = _wp_create_admin_backup("before-restore-" + safe)

    tmp_dir = "/tmp/wifiportal-restore-" + str(int(time.time()))
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        with tarfile.open(backup_path, "r:gz") as tar:
            for member in tar.getmembers():
                member_name = str(member.name or "")
                if member_name.startswith("/") or ".." in member_name.split("/"):
                    raise ValueError("备份包包含不安全路径：" + member_name)
            tar.extractall(tmp_dir)

        mapping = [
            ("wifiportal.py", "/usr/lib/wifiportal/wifiportal.py"),
            ("vouchers.json", "/etc/wifiportal/vouchers.json"),
            ("settings.json", "/etc/wifiportal/settings.json"),
            ("openwrt-network", "/etc/config/network"),
            ("openwrt-firewall", "/etc/config/firewall"),
            ("openwrt-dhcp", "/etc/config/dhcp"),
            ("init.d-wifiportal", "/etc/init.d/wifiportal"),
        ]

        restored = []
        for src_name, dst in mapping:
            src_path = os.path.join(tmp_dir, src_name)
            if not os.path.exists(src_path):
                continue
            dst_tmp = dst + ".restore-tmp"
            shutil.copyfile(src_path, dst_tmp)
            os.rename(dst_tmp, dst)
            restored.append(dst)

        append_log("BACKUP", "恢复后台备份 " + safe)
        return {
            "backup": safe,
            "restored": restored,
            "safety_backup": restore_safety.get("name", ""),
        }
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


def _wp_format_bytes(n):
    try:
        n = int(n)
    except Exception:
        return str(n)
    if n < 1024:
        return str(n) + " B"
    if n < 1024 * 1024:
        return "%.1f KB" % (n / 1024.0)
    return "%.1f MB" % (n / 1024.0 / 1024.0)


def _wp_backup_panel_html():
    import time

    backups = _wp_list_admin_backups()
    rows = []

    if backups:
        for item in backups[:20]:
            name = item.get("name", "")
            size = _wp_format_bytes(item.get("size", 0))
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(item.get("mtime", 0) or 0)))

            rows.append(f"""
<tr>
  <td><code>{esc(name)}</code></td>
  <td>{esc(size)}</td>
  <td>{esc(mtime)}</td>
  <td>
    <a class="btn" href="/admin/backup/download?name={urllib.parse.quote(name)}">下载</a>
    <form method="post" action="/admin/backup/restore" style="display:inline" onsubmit="return confirm('确认恢复这个备份？系统会先自动创建当前状态安全备份，然后重启服务。')">
      <input type="hidden" name="name" value="{esc(name)}">
      <button type="submit">恢复</button>
    </form>
  </td>
</tr>
""")
    else:
        rows.append("<tr><td colspan='4' class='muted'>暂无备份</td></tr>")

    return f"""
<div class="card maintenance-compact-card">
  <div class="maintenance-top">
    <h2>备份与恢复</h2>
    <div class="maintenance-actions">
      <form method="post" action="/admin/backup/create">
        <button type="submit">立即创建备份</button>
      </form>
      <form method="post" action="/admin/backup/prune" onsubmit="return confirm('确认清理旧备份？只保留最近 7 份。')">
        <button type="submit">清理旧备份</button>
      </form>
    </div>
  </div>
  <p class="muted" style="margin:8px 0">备份包含程序、兑换码数据库、设置文件、OpenWrt network/firewall/dhcp 配置和 wifiportal 启动脚本。</p>
  <div style="overflow:auto;max-height:260px">
    <table class="dense-table">
      <tr><th>备份文件</th><th>大小</th><th>时间</th><th>操作</th></tr>
      {''.join(rows)}
    </table>
  </div>
</div>
"""


_wp_old_maintenance_page_backup_v1 = _wp_maintenance_page


def _wp_maintenance_page_backup_v1(self, notice=""):
    _wp_old_maintenance_page_backup_v1(self, notice)


def _wp_send_backup_file(self, name):
    import os

    safe = _wp_safe_backup_name(name)
    if not safe:
        self.send_error(400, "Bad backup name")
        return

    path = os.path.join(_wp_backup_dir(), safe)
    if not os.path.exists(path):
        self.send_error(404, "Backup not found")
        return

    try:
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/gzip")
        self.send_header("Content-Disposition", "attachment; filename=" + safe)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    except Exception as error:
        self.send_error(500, str(error))


def _wp_inject_backup_panel_into_maintenance_html(original_html):
    panel = _wp_backup_panel_html()
    marker = '<div class="card maintenance-compact-card">\n  <div class="maintenance-line-title">\n    <h2>服务状态</h2>'
    if marker in original_html:
        return original_html.replace(marker, panel + "\n" + marker, 1)

    marker2 = "</div>"
    idx = original_html.rfind(marker2)
    if idx >= 0:
        return original_html[:idx] + panel + original_html[idx:]

    return original_html + panel


class _WpMaintenanceHtmlCapture:
    def __init__(self):
        self.value = ""

    def __call__(self, title, body):
        try:
            return admin_page(title, body)
        except Exception:
            return body


def _wp_maintenance_page_with_backup_panel(self, notice=""):
    # Capture by temporarily wrapping self.send_html because the existing page builds full html internally.
    old_send_html = self.send_html
    captured = {}

    def fake_send_html(html):
        captured["html"] = html

    try:
        self.send_html = fake_send_html
        _wp_old_maintenance_page_backup_v1(self, notice)
    finally:
        self.send_html = old_send_html

    html = captured.get("html", "")
    if not html:
        _wp_old_maintenance_page_backup_v1(self, notice)
        return

    html = _wp_inject_backup_panel_into_maintenance_html(html)
    self.send_html(html)


_wp_old_handle_admin_get_backup_v1 = Handler.handle_admin_get
_wp_old_handle_admin_post_backup_v1 = Handler.handle_admin_post


def _wp_handle_admin_get_backup_v1(self, path):
    if path.startswith("/admin/backup/download"):
        if not self.require_admin():
            return
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = str(query.get("name", [""])[0] or "")
        _wp_send_backup_file(self, name)
        return

    return _wp_old_handle_admin_get_backup_v1(self, path)


def _wp_handle_admin_post_backup_v1(self, path):
    if path == "/admin/backup/create":
        if not self.require_admin():
            return
        result = _wp_create_admin_backup("manual-admin")
        _wp_prune_admin_backups(7)
        _wp_maintenance_page_with_backup_panel(self, "已创建备份：" + result.get("name", ""))
        return

    if path == "/admin/backup/prune":
        if not self.require_admin():
            return
        removed = _wp_prune_admin_backups(7)
        _wp_maintenance_page_with_backup_panel(self, "已清理旧备份：" + str(len(removed)) + " 个")
        return

    if path == "/admin/backup/restore":
        if not self.require_admin():
            return
        form = self.read_form()
        name = str(form.get("name", "") or "")
        try:
            result = _wp_restore_admin_backup(name)
            append_log("BACKUP", "后台恢复备份完成 " + name)
            # Restart after response is safer for browser UX, but here we do direct restart after rendering.
            _wp_maintenance_page_with_backup_panel(
                self,
                "已恢复备份：" + result.get("backup", "") + "；恢复前安全备份：" + result.get("safety_backup", "") + "。服务将重启。"
            )
            try:
                import threading
                def later_restart():
                    import time, subprocess
                    time.sleep(1)
                    subprocess.call(["/etc/init.d/wifiportal", "restart"])
                threading.Thread(target=later_restart, daemon=True).start()
            except Exception:
                pass
            return
        except Exception as error:
            _wp_maintenance_page_with_backup_panel(self, "恢复失败：" + str(error))
            return

    return _wp_old_handle_admin_post_backup_v1(self, path)


_wp_maintenance_page = _wp_maintenance_page_with_backup_panel
Handler.handle_admin_get = _wp_handle_admin_get_backup_v1
Handler.handle_admin_post = _wp_handle_admin_post_backup_v1





# VOUCHER_EXPORT_CLEANUP_TOOLS_V1
# Admin voucher export and cleanup tools.

def _wp_voucher_tools_safe_text(value):
    try:
        return esc(value)
    except Exception:
        import html
        return html.escape(str(value))


def _wp_voucher_tools_now_text(ts):
    import time
    try:
        ts = int(ts or 0)
    except Exception:
        ts = 0
    if ts <= 0:
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _wp_voucher_tools_csv_cell(value):
    value = str(value if value is not None else "")
    value = value.replace('"', '""')
    return '"' + value + '"'


def _wp_voucher_tools_get_voucher_devices(voucher):
    devices = voucher.get("devices", {}) if isinstance(voucher, dict) else {}
    if isinstance(devices, dict):
        return devices
    return {}


def _wp_voucher_tools_voucher_is_unused(voucher):
    devices = _wp_voucher_tools_get_voucher_devices(voucher)
    return len(devices) == 0


def _wp_voucher_tools_voucher_expire_at(voucher):
    if not isinstance(voucher, dict):
        return 0
    try:
        return int(voucher.get("expire_at", 0) or 0)
    except Exception:
        return 0


def _wp_voucher_tools_voucher_is_expired(voucher, now_ts=None):
    if now_ts is None:
        now_ts = now()
    expire_at = _wp_voucher_tools_voucher_expire_at(voucher)
    return bool(expire_at > 0 and expire_at <= int(now_ts))


def _wp_voucher_tools_voucher_has_active_device(code, db, nft_authed_text=""):
    devices = db.get("devices", {}) if isinstance(db.get("devices", {}), dict) else {}
    now_ts = now()

    for mac, device in devices.items():
        if not isinstance(device, dict):
            continue

        device_code = str(device.get("voucher_code", "") or "").strip()
        if device_code != str(code):
            continue

        device_online = bool(device.get("online"))
        mac_in_nft = str(mac).lower() in str(nft_authed_text).lower()

        device_expire_at = 0
        try:
            device_expire_at = int(device.get("expire_at", 0) or 0)
        except Exception:
            device_expire_at = 0

        device_not_expired = bool(device_expire_at == 0 or device_expire_at > now_ts)

        if device_online and device_not_expired:
            return True

        if mac_in_nft and device_not_expired:
            return True

    voucher = db.get("vouchers", {}).get(code)
    if isinstance(voucher, dict):
        voucher_devices = _wp_voucher_tools_get_voucher_devices(voucher)
        for mac, item in voucher_devices.items():
            if not isinstance(item, dict):
                continue
            item_online = bool(item.get("online"))
            mac_in_nft = str(mac).lower() in str(nft_authed_text).lower()
            if item_online or mac_in_nft:
                return True

    return False


def _wp_voucher_tools_safety_backup(reason):
    try:
        if "_wp_create_admin_backup" in globals():
            return _wp_create_admin_backup(reason)
    except Exception:
        pass

    import os
    import shutil
    import time

    backup_dir = "/etc/wifiportal/voucher-tools-safety-backup"
    os.makedirs(backup_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    code_path = backup_dir + "/wifiportal-before-" + stamp + ".py"
    db_path = backup_dir + "/vouchers-before-" + stamp + ".json"

    try:
        shutil.copyfile("/usr/lib/wifiportal/wifiportal.py", code_path)
    except Exception:
        code_path = ""

    try:
        shutil.copyfile("/etc/wifiportal/vouchers.json", db_path)
    except Exception:
        db_path = ""

    return {
        "name": "manual-safety-" + stamp,
        "code": code_path,
        "db": db_path,
    }


def _wp_voucher_tools_build_csv(mode="unused"):
    import time

    db = load_db()
    vouchers = db.get("vouchers", {}) if isinstance(db.get("vouchers", {}), dict) else {}
    now_ts = now()

    headers = [
        "code",
        "status",
        "enabled",
        "used",
        "expired",
        "expire_at",
        "expire_time",
        "minutes",
        "max_devices",
        "device_count",
        "speed_profile_name",
        "download_kbps",
        "upload_kbps",
        "created_at",
        "created_time",
    ]

    rows = [headers]

    for code in sorted(vouchers.keys()):
        voucher = vouchers.get(code, {})
        if not isinstance(voucher, dict):
            continue

        unused = _wp_voucher_tools_voucher_is_unused(voucher)
        expired = _wp_voucher_tools_voucher_is_expired(voucher, now_ts)

        if mode == "unused" and not unused:
            continue

        if mode == "expired" and not expired:
            continue

        enabled = bool(voucher.get("enabled", True))
        expire_at = _wp_voucher_tools_voucher_expire_at(voucher)
        created_at = int(voucher.get("created_at", 0) or 0) if str(voucher.get("created_at", 0) or "0").isdigit() else 0
        device_count = len(_wp_voucher_tools_get_voucher_devices(voucher))

        if expired:
            status = "expired"
        elif unused:
            status = "unused"
        else:
            status = "used"

        rows.append([
            code,
            status,
            "1" if enabled else "0",
            "0" if unused else "1",
            "1" if expired else "0",
            str(expire_at),
            _wp_voucher_tools_now_text(expire_at),
            str(voucher.get("minutes", "")),
            str(voucher.get("max_devices", "")),
            str(device_count),
            str(voucher.get("speed_profile_name", "")),
            str(voucher.get("download_kbps", "")),
            str(voucher.get("upload_kbps", "")),
            str(created_at),
            _wp_voucher_tools_now_text(created_at),
        ])

    lines = []
    for row in rows:
        lines.append(",".join(_wp_voucher_tools_csv_cell(cell) for cell in row))

    return "\n".join(lines) + "\n"


def _wp_voucher_tools_send_csv(self, mode):
    import time

    if mode not in ["unused", "all", "expired"]:
        mode = "unused"

    csv_text = _wp_voucher_tools_build_csv(mode)
    body = csv_text.encode("utf-8-sig")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    filename = "wifiportal-vouchers-" + mode + "-" + stamp + ".csv"

    self.send_response(200)
    self.send_header("Content-Type", "text/csv; charset=utf-8")
    self.send_header("Content-Disposition", "attachment; filename=" + filename)
    self.send_header("Cache-Control", "no-store")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)


def _wp_voucher_tools_delete_expired_unused():
    import subprocess

    backup = _wp_voucher_tools_safety_backup("before-delete-expired-vouchers")

    db = load_db()
    vouchers = db.get("vouchers", {}) if isinstance(db.get("vouchers", {}), dict) else {}
    devices = db.get("devices", {}) if isinstance(db.get("devices", {}), dict) else {}

    try:
        nft_authed = subprocess.getoutput("nft list set inet wifiportal authed_macs 2>/dev/null").lower()
    except Exception:
        nft_authed = ""

    now_ts = now()
    deleted = []
    skipped_active = []

    for code in list(vouchers.keys()):
        voucher = vouchers.get(code, {})
        if not isinstance(voucher, dict):
            continue

        expired = _wp_voucher_tools_voucher_is_expired(voucher, now_ts)
        if not expired:
            continue

        active = _wp_voucher_tools_voucher_has_active_device(code, db, nft_authed)
        if active:
            skipped_active.append(code)
            continue

        # Clear device references pointing to this expired voucher before deleting the voucher.
        for mac, device in devices.items():
            if not isinstance(device, dict):
                continue
            if str(device.get("voucher_code", "") or "").strip() != str(code):
                continue

            mac_in_nft = str(mac).lower() in nft_authed
            if bool(device.get("online")) or mac_in_nft:
                skipped_active.append(code)
                active = True
                break

            device["voucher_code"] = ""
            device["speed_profile_name"] = ""
            device["download_kbps"] = 0
            device["upload_kbps"] = 0
            device["download_mbps"] = "-"
            device["upload_mbps"] = "-"
            device["expire_at"] = 0
            device["login_at"] = 0
            device["online"] = False
            device["last_seen"] = now_ts

        if active:
            continue

        del vouchers[code]
        deleted.append(code)

    save_db(db)

    if deleted:
        append_log("VOUCHER", "批量删除过期兑换码 " + str(len(deleted)) + " 个")

    return {
        "backup": backup,
        "deleted": deleted,
        "skipped_active": sorted(list(set(skipped_active))),
    }


def _wp_voucher_tools_cleanup_history_bindings():
    import subprocess

    backup = _wp_voucher_tools_safety_backup("before-cleanup-voucher-history")

    db = load_db()
    vouchers = db.get("vouchers", {}) if isinstance(db.get("vouchers", {}), dict) else {}
    devices = db.get("devices", {}) if isinstance(db.get("devices", {}), dict) else {}

    try:
        nft_authed = subprocess.getoutput("nft list set inet wifiportal authed_macs 2>/dev/null").lower()
    except Exception:
        nft_authed = ""

    now_ts = now()
    cleaned = []

    for mac, device in devices.items():
        if not isinstance(device, dict):
            continue

        code = str(device.get("voucher_code", "") or "").strip()
        if not code or code == "WHITELIST":
            continue

        voucher = vouchers.get(code)
        voucher_exists = isinstance(voucher, dict)

        expire_at = 0
        try:
            expire_at = int(device.get("expire_at", 0) or 0)
        except Exception:
            expire_at = 0

        if expire_at <= 0 and voucher_exists:
            expire_at = _wp_voucher_tools_voucher_expire_at(voucher)

        expired = bool(expire_at > 0 and expire_at <= now_ts)
        missing_voucher = bool(not voucher_exists)

        mac_in_nft = str(mac).lower() in nft_authed
        db_online = bool(device.get("online"))

        if (expired or missing_voucher) and (not db_online) and (not mac_in_nft):
            old_code = code
            old_plan = str(device.get("speed_profile_name", "") or "")

            device["voucher_code"] = ""
            device["speed_profile_name"] = ""
            device["download_kbps"] = 0
            device["upload_kbps"] = 0
            device["download_mbps"] = "-"
            device["upload_mbps"] = "-"
            device["expire_at"] = 0
            device["login_at"] = 0
            device["online"] = False
            device["last_seen"] = now_ts

            if voucher_exists:
                try:
                    voucher_devices = _wp_voucher_tools_get_voucher_devices(voucher)
                    if mac in voucher_devices:
                        voucher_devices[mac]["online"] = False
                        voucher_devices[mac]["last_seen"] = now_ts
                except Exception:
                    pass

            cleaned.append({
                "mac": mac,
                "ip": device.get("ip", ""),
                "old_voucher": old_code,
                "old_plan": old_plan,
                "reason": "expired" if expired else "missing_voucher",
            })

    if cleaned:
        save_db(db)
        append_log("VOUCHER", "清理过期历史设备绑定 " + str(len(cleaned)) + " 条")

    return {
        "backup": backup,
        "cleaned": cleaned,
    }


def _wp_voucher_tools_panel_html():
    db = load_db()
    vouchers = db.get("vouchers", {}) if isinstance(db.get("vouchers", {}), dict) else {}
    devices = db.get("devices", {}) if isinstance(db.get("devices", {}), dict) else {}

    now_ts = now()

    total = len(vouchers)
    unused = 0
    expired = 0
    expired_unused = 0
    used = 0

    for code, voucher in vouchers.items():
        if not isinstance(voucher, dict):
            continue

        is_unused = _wp_voucher_tools_voucher_is_unused(voucher)
        is_expired = _wp_voucher_tools_voucher_is_expired(voucher, now_ts)

        if is_unused:
            unused += 1
        else:
            used += 1

        if is_expired:
            expired += 1

        if is_expired and is_unused:
            expired_unused += 1

    historical_bindings = 0
    for mac, device in devices.items():
        if not isinstance(device, dict):
            continue

        code = str(device.get("voucher_code", "") or "").strip()
        if not code or code == "WHITELIST":
            continue

        voucher = vouchers.get(code)
        voucher_exists = isinstance(voucher, dict)

        expire_at = int(device.get("expire_at", 0) or 0)
        if expire_at <= 0 and voucher_exists:
            expire_at = _wp_voucher_tools_voucher_expire_at(voucher)

        expired_binding = bool(expire_at > 0 and expire_at <= now_ts)
        missing_voucher = bool(not voucher_exists)

        if (expired_binding or missing_voucher) and not bool(device.get("online")):
            historical_bindings += 1

    return f"""
<div class="card maintenance-compact-card">
  <div class="maintenance-top">
    <h2>兑换码工具</h2>
    <div class="maintenance-actions">
      <a class="btn" href="/admin/voucher-tools/export?mode=unused">导出未使用 CSV</a>
      <a class="btn" href="/admin/voucher-tools/export?mode=all">导出全部 CSV</a>
      <a class="btn" href="/admin/voucher-tools/export?mode=expired">导出过期 CSV</a>
    </div>
  </div>

  <div class="maintenance-stats" style="grid-template-columns:repeat(5,minmax(100px,1fr));margin-top:8px">
    <div class="stat">全部兑换码<b>{total}</b></div>
    <div class="stat">未使用<b>{unused}</b></div>
    <div class="stat">已使用<b>{used}</b></div>
    <div class="stat">已过期<b>{expired}</b></div>
    <div class="stat">历史绑定<b>{historical_bindings}</b></div>
  </div>

  <div class="maintenance-actions" style="margin-top:10px">
    <form method="post" action="/admin/voucher-tools/delete-expired" onsubmit="return confirm('确认删除已过期且未在线使用的兑换码？操作前会自动创建备份。')">
      <button type="submit">删除过期未在线兑换码</button>
    </form>

    <form method="post" action="/admin/voucher-tools/cleanup-history" onsubmit="return confirm('确认清理设备表里的过期历史兑换码绑定？不会影响有效在线用户。')">
      <button type="submit">清理历史设备绑定</button>
    </form>
  </div>

  <p class="muted" style="margin:8px 0 0">
    删除只处理 expire_at 已过期且没有在线/nft 放行设备使用的兑换码；清理历史绑定只清理已过期或缺失兑换码的离线设备记录。
  </p>
</div>
"""


def _wp_voucher_tools_inject_panel(original_html):
    panel = _wp_voucher_tools_panel_html()

    backup_marker = '<div class="card maintenance-compact-card">\n  <div class="maintenance-top">\n    <h2>备份与恢复</h2>'
    if backup_marker in original_html:
        return original_html.replace(backup_marker, panel + "\n" + backup_marker, 1)

    service_marker = '<div class="card maintenance-compact-card">\n  <div class="maintenance-line-title">\n    <h2>服务状态</h2>'
    if service_marker in original_html:
        return original_html.replace(service_marker, panel + "\n" + service_marker, 1)

    idx = original_html.rfind("</div>")
    if idx >= 0:
        return original_html[:idx] + panel + original_html[idx:]

    return original_html + panel


_wp_old_maintenance_page_voucher_tools_v1 = _wp_maintenance_page


def _wp_maintenance_page_voucher_tools_v1(self, notice=""):
    old_send_html = self.send_html
    captured = {}

    def fake_send_html(html):
        captured["html"] = html

    try:
        self.send_html = fake_send_html
        _wp_old_maintenance_page_voucher_tools_v1(self, notice)
    finally:
        self.send_html = old_send_html

    html = captured.get("html", "")
    if not html:
        _wp_old_maintenance_page_voucher_tools_v1(self, notice)
        return

    html = _wp_voucher_tools_inject_panel(html)
    self.send_html(html)


_wp_old_handle_admin_get_voucher_tools_v1 = Handler.handle_admin_get
_wp_old_handle_admin_post_voucher_tools_v1 = Handler.handle_admin_post


def _wp_handle_admin_get_voucher_tools_v1(self, path):
    if path.startswith("/admin/voucher-tools/export"):
        if not self.require_admin():
            return
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        mode = str(query.get("mode", ["unused"])[0] or "unused").strip()
        _wp_voucher_tools_send_csv(self, mode)
        return

    return _wp_old_handle_admin_get_voucher_tools_v1(self, path)


def _wp_handle_admin_post_voucher_tools_v1(self, path):
    if path == "/admin/voucher-tools/delete-expired":
        if not self.require_admin():
            return
        try:
            result = _wp_voucher_tools_delete_expired_unused()
            deleted_count = len(result.get("deleted", []))
            skipped_count = len(result.get("skipped_active", []))
            backup_name = ""
            backup = result.get("backup", {})
            if isinstance(backup, dict):
                backup_name = str(backup.get("name", "") or "")
            notice = "已删除过期未在线兑换码：" + str(deleted_count) + " 个；跳过在线使用：" + str(skipped_count) + " 个；备份：" + backup_name
            try:
                append_admin_audit(self, "删除过期兑换码", notice)
            except Exception:
                pass
            _wp_maintenance_page_voucher_tools_v1(self, notice)
            return
        except Exception as error:
            _wp_maintenance_page_voucher_tools_v1(self, "删除失败：" + str(error))
            return

    if path == "/admin/voucher-tools/cleanup-history":
        if not self.require_admin():
            return
        try:
            result = _wp_voucher_tools_cleanup_history_bindings()
            cleaned_count = len(result.get("cleaned", []))
            backup_name = ""
            backup = result.get("backup", {})
            if isinstance(backup, dict):
                backup_name = str(backup.get("name", "") or "")
            notice = "已清理历史设备绑定：" + str(cleaned_count) + " 条；备份：" + backup_name
            try:
                append_admin_audit(self, "清理历史设备绑定", notice)
            except Exception:
                pass
            _wp_maintenance_page_voucher_tools_v1(self, notice)
            return
        except Exception as error:
            _wp_maintenance_page_voucher_tools_v1(self, "清理失败：" + str(error))
            return

    return _wp_old_handle_admin_post_voucher_tools_v1(self, path)


_wp_maintenance_page = _wp_maintenance_page_voucher_tools_v1
Handler.handle_admin_get = _wp_handle_admin_get_voucher_tools_v1
Handler.handle_admin_post = _wp_handle_admin_post_voucher_tools_v1





# ADMIN_SECURITY_HARDENING_V1
# Admin login failure lock, session timeout and login audit.
# This only hardens /admin authentication. It does not change customer voucher auth.

def _wp_admin_security_state_path():
    return "/tmp/wifiportal_admin_security.json"


def _wp_admin_security_load():
    import json
    try:
        with open(_wp_admin_security_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("login_failures", {})
            return data
    except Exception:
        pass
    return {"login_failures": {}}


def _wp_admin_security_save(data):
    import json
    import os

    path = _wp_admin_security_state_path()
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

    os.rename(tmp, path)


def _wp_admin_security_get_config():
    try:
        settings = load_settings()
    except Exception:
        settings = {}

    admin = settings.get("admin", {}) if isinstance(settings.get("admin", {}), dict) else {}

    try:
        session_timeout = int(admin.get("session_timeout_seconds", 3600) or 3600)
    except Exception:
        session_timeout = 3600

    if session_timeout < 300:
        session_timeout = 300

    return {
        "max_failures": 5,
        "lock_seconds": 600,
        "session_timeout_seconds": session_timeout,
    }


def _wp_admin_security_client_ip(handler):
    try:
        return str(handler.client_address[0] or "")
    except Exception:
        return "unknown"


def _wp_admin_security_lock_info(ip):
    data = _wp_admin_security_load()
    failures = data.get("login_failures", {})
    item = failures.get(ip, {}) if isinstance(failures.get(ip, {}), dict) else {}

    cfg = _wp_admin_security_get_config()
    now_ts = now()

    locked_until = int(item.get("locked_until", 0) or 0)
    count = int(item.get("count", 0) or 0)

    if locked_until > now_ts:
        return {
            "locked": True,
            "remaining": locked_until - now_ts,
            "count": count,
            "max_failures": cfg["max_failures"],
        }

    return {
        "locked": False,
        "remaining": 0,
        "count": count,
        "max_failures": cfg["max_failures"],
    }


def _wp_admin_security_record_failed_login(ip):
    data = _wp_admin_security_load()
    failures = data.setdefault("login_failures", {})

    cfg = _wp_admin_security_get_config()
    now_ts = now()

    item = failures.get(ip, {}) if isinstance(failures.get(ip, {}), dict) else {}
    locked_until = int(item.get("locked_until", 0) or 0)

    if locked_until > now_ts:
        item["last_failed_at"] = now_ts
        failures[ip] = item
        _wp_admin_security_save(data)
        return _wp_admin_security_lock_info(ip)

    count = int(item.get("count", 0) or 0) + 1
    item["count"] = count
    item["last_failed_at"] = now_ts

    if count >= cfg["max_failures"]:
        item["locked_until"] = now_ts + cfg["lock_seconds"]
    else:
        item["locked_until"] = 0

    failures[ip] = item
    _wp_admin_security_save(data)
    return _wp_admin_security_lock_info(ip)


def _wp_admin_security_clear_failed_login(ip):
    data = _wp_admin_security_load()
    failures = data.setdefault("login_failures", {})
    if ip in failures:
        del failures[ip]
        _wp_admin_security_save(data)


def _wp_admin_security_cookie_header():
    cfg = _wp_admin_security_get_config()
    timeout = int(cfg.get("session_timeout_seconds", 3600) or 3600)
    ts = str(now())

    # One Set-Cookie header can only safely set one cookie, so we set wp_admin_ts
    # through a lightweight JavaScript fallback on the success page too.
    return {
        "Set-Cookie": f"wp_admin={SESSION_SECRET}; Path=/; Max-Age={timeout}; HttpOnly; SameSite=Lax",
        "Refresh": "0; url=/admin",
    }


def _wp_admin_security_set_ts_script():
    cfg = _wp_admin_security_get_config()
    timeout = int(cfg.get("session_timeout_seconds", 3600) or 3600)
    ts = str(now())
    return f"""
<script>
document.cookie = "wp_admin_ts={ts}; Path=/; Max-Age={timeout}; SameSite=Lax";
setTimeout(function(){{ location.href="/admin"; }}, 200);
</script>
"""


_wp_old_is_admin_security_v1 = Handler.is_admin
_wp_old_require_admin_security_v1 = Handler.require_admin
_wp_old_handle_admin_get_security_v1 = Handler.handle_admin_get
_wp_old_handle_admin_post_security_v1 = Handler.handle_admin_post


def _wp_is_admin_security_v1(self):
    if self.get_cookie("wp_admin") != SESSION_SECRET:
        return False

    cfg = _wp_admin_security_get_config()
    timeout = int(cfg.get("session_timeout_seconds", 3600) or 3600)

    ts_raw = self.get_cookie("wp_admin_ts")
    if not ts_raw:
        # Compatibility: allow old admin cookie created before this patch.
        # New logins will have wp_admin_ts and will be timeout-controlled.
        return True

    try:
        login_ts = int(ts_raw)
    except Exception:
        return False

    if login_ts <= 0:
        return False

    if now() - login_ts > timeout:
        return False

    return True


def _wp_require_admin_security_v1(self):
    if _wp_is_admin_security_v1(self):
        return True

    # Clear possibly expired cookies.
    self.send_response(302)
    self.send_header("Location", "/admin/login")
    self.send_header("Set-Cookie", "wp_admin=; Path=/; Max-Age=0")
    self.send_header("Set-Cookie", "wp_admin_ts=; Path=/; Max-Age=0")
    self.end_headers()
    return False


def _wp_admin_login_page_security_v1(self, message="", bad=False):
    ip = _wp_admin_security_client_ip(self)
    lock = _wp_admin_security_lock_info(ip)

    lock_html = ""
    if lock.get("locked"):
        minutes = max(1, int(lock.get("remaining", 0)) // 60)
        lock_html = f"<div class='info bad'>登录失败次数过多，请约 {minutes} 分钟后再试。</div>"
    elif message:
        cls = "bad" if bad else "ok"
        lock_html = f"<div class='info {cls}'>{esc(message)}</div>"

    cfg = _wp_admin_security_get_config()
    timeout_min = int(cfg.get("session_timeout_seconds", 3600)) // 60

    body = f"""
<div class="card">
<h1>后台登录</h1>
{lock_html}
<form method="post" action="/admin/login">
<input type="hidden" name="username" value="admin">
<p><input name="password" type="password" placeholder="密码" required style="width:100%;box-sizing:border-box"></p>
<p><button type="submit" style="width:100%">登录</button></p>
</form>
<p class="muted">连续输错 5 次会锁定 10 分钟；会话有效期约 {timeout_min} 分钟。</p>
</div>
"""
    self.send_html(admin_page("后台登录", body, logged_in=False))


def _wp_handle_admin_get_security_v1(self, path):
    if path == "/admin/login":
        _wp_admin_login_page_security_v1(self)
        return

    if path == "/admin/logout":
        self.send_html(
            admin_page("退出登录", "<div class='card'><h1>已退出登录</h1><a class='btn' href='/admin/login'>重新登录</a></div>", logged_in=False),
            headers={"Set-Cookie": "wp_admin=; Path=/; Max-Age=0"}
        )
        return

    return _wp_old_handle_admin_get_security_v1(self, path)


def _wp_handle_admin_post_security_v1(self, path):
    if path == "/admin/login":
        ip = _wp_admin_security_client_ip(self)
        lock = _wp_admin_security_lock_info(ip)

        if lock.get("locked"):
            append_log("ADMIN", "后台登录被锁定拦截", ip=ip, result="FAIL")
            try:
                append_admin_audit(self, "后台登录被锁定拦截", result="FAIL")
            except Exception:
                pass
            _wp_admin_login_page_security_v1(self, "登录失败次数过多，请稍后再试。", bad=True)
            return

        form = self.read_form()
        username = form.get("username", "admin") or "admin"
        password = form.get("password", "")

        if username == "admin" and verify_admin_password(password):
            _wp_admin_security_clear_failed_login(ip)
            append_log("ADMIN", "后台登录成功", ip=ip)
            try:
                append_admin_audit(self, "后台登录成功")
            except Exception:
                pass

            success_body = """
<div class="card">
<h1 class="ok">登录成功</h1>
<p>正在进入后台...</p>
</div>
""" + _wp_admin_security_set_ts_script()

            self.send_html(
                admin_page("登录成功", success_body, logged_in=False),
                headers=_wp_admin_security_cookie_header()
            )
            return

        info = _wp_admin_security_record_failed_login(ip)
        remaining_try = max(0, int(info.get("max_failures", 5)) - int(info.get("count", 0)))

        append_log("ADMIN", "后台登录失败", ip=ip, result="FAIL")
        try:
            append_admin_audit(self, "后台登录失败", "remaining_try=" + str(remaining_try), result="FAIL")
        except Exception:
            pass

        if info.get("locked"):
            _wp_admin_login_page_security_v1(self, "登录失败次数过多，已锁定 10 分钟。", bad=True)
        else:
            _wp_admin_login_page_security_v1(self, "用户名或密码错误，剩余尝试次数：" + str(remaining_try), bad=True)
        return

    return _wp_old_handle_admin_post_security_v1(self, path)


Handler.is_admin = _wp_is_admin_security_v1
Handler.require_admin = _wp_require_admin_security_v1
Handler.handle_admin_get = _wp_handle_admin_get_security_v1
Handler.handle_admin_post = _wp_handle_admin_post_security_v1





# CUSTOMER_PAGE_POLISH_V1
# English customer page UI polish. Does not change authentication/firewall logic.

def _wp_customer_seconds_text(seconds):
    try:
        seconds = int(seconds or 0)
    except Exception:
        seconds = 0

    if seconds <= 0:
        return "Permanent or unlimited access"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        return str(days) + "d " + str(hours) + "h " + str(minutes) + "m"
    if hours > 0:
        return str(hours) + "h " + str(minutes) + "m"
    return str(minutes) + "m"





























































































































































































































































































































def _wp_show_customer_login_polished(self, default_code=""):
    settings = load_settings()
    portal = settings.get("portal_page", {})

    title = str(portal.get("title", "WiFi Authentication") or "WiFi Authentication")
    notice = str(portal.get("notice", "Please enter your voucher code to access the Internet.") or "")
    plan_text = str(portal.get("plan_text", "") or "")
    contact_text = str(portal.get("contact_text", "") or "")
    footer_text = str(portal.get("footer_text", "") or "")

    plan_html = ""
    if plan_text.strip():
        plan_html = f"""
<div class="card">
  <div class="plan-box">{esc(plan_text)}</div>
</div>
"""

    contact_html = ""
    if contact_text.strip() or footer_text.strip():
        contact_html = f"""
<div class="card">
  <div class="contact-box">{esc(contact_text) if contact_text.strip() else "Please contact the WiFi administrator if you need help."}</div>
  <p class="muted" style="margin:9px 0 0">{esc(footer_text)}</p>
</div>
"""

    body = f"""
<div class="card hero-card">
  <div class="brand-pill">Local WiFi Access</div>
  <h1>{esc(title)}</h1>
  <div class="notice-text">{esc(notice)}</div>
</div>

{plan_html}

<div class="card">
  <form class="voucher-form" method="post" action="/auth">
    <input class="voucher-input" name="code" value="{esc(default_code)}" placeholder="Voucher Code" autocomplete="off" autocapitalize="characters" autofocus required>
    <button type="submit">Connect Now</button>
  </form>
  <p class="muted" style="text-align:center;margin:10px 0 0">
    Already connected? <a class="link" href="http://{esc(LAN_IP)}/check">Check device status</a>
  </p>
</div>

{contact_html}
"""

    self.send_html(_wp_customer_page_polished(title, body))


def _wp_show_customer_check_polished(self):
    ip = self.client_address[0]
    mac, hostname = get_client_identity(ip)
    db = load_db()
    settings = load_settings()
    portal = settings.get("portal_page", {})

    device = db.get("devices", {}).get(mac, {}) if mac else {}
    if device.get("hostname") and device.get("hostname") != "Unknown Device":
        hostname = device.get("hostname")

    voucher_code = device.get("voucher_code", "-")
    online = bool(device.get("online"))
    expire_at_raw = int(device.get("expire_at", 0) or 0)
    login_at_raw = int(device.get("login_at", 0) or 0)

    if expire_at_raw > 0 and expire_at_raw <= now():
        online = False

    status = "Connected" if online else "Not Connected"
    status_icon = "✓" if online else "!"
    status_class = "status-ok" if online else "status-bad"
    status_hint = "Your device is authenticated and can access the Internet." if online else "Your device is not authenticated or your session has expired."

    plan = device.get("speed_profile_name", "-") if online else "-"
    download = device.get("download_mbps", "-") if online else "-"
    upload = device.get("upload_mbps", "-") if online else "-"
    login_at = format_time(login_at_raw) if online else "-"
    expire_at = "Permanent" if expire_at_raw == 0 and online else (format_time(expire_at_raw) if online else "-")

    remaining_seconds = 0
    if not online:
        remaining = "-"
    elif expire_at_raw == 0:
        remaining = "Permanent"
    else:
        remaining_seconds = max(0, expire_at_raw - now())
        remaining = _wp_customer_seconds_text(remaining_seconds)

    contact_text = str(portal.get("contact_text", "") or "")
    footer_text = str(portal.get("footer_text", "") or "")

    voucher_display = voucher_code if online and voucher_code else "-"
    mac_display = mac or "-"

    if online:
        action_buttons = f"""
<a class="btn" href="/check">Check Connection</a>
<a class="btn secondary" href="/check">Refresh Status</a>
"""
    else:
        action_buttons = f"""
<a class="btn" href="/">Enter Voucher Code</a>
<a class="btn soft" href="/check">Refresh Status</a>
"""

    countdown_html = ""
    if online and remaining_seconds > 0:
        countdown_html = f"""
<div class="countdown-box">
  <span>Remaining Time</span>
  <b id="check-countdown" data-seconds="{remaining_seconds}">{esc(remaining)}</b>
</div>
<script>
(function(){{
  var el = document.getElementById("check-countdown");
  if (!el) return;
  var seconds = parseInt(el.getAttribute("data-seconds") || "0", 10);
  function formatRemain(s) {{
    if (s <= 0) return "Expired";
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    if (d > 0) return d + "d " + h + "h " + m + "m";
    if (h > 0) return h + "h " + m + "m " + sec + "s";
    return m + "m " + sec + "s";
  }}
  setInterval(function(){{
    seconds -= 1;
    el.textContent = formatRemain(seconds);
    if (seconds <= 0) {{
      el.className = "bad";
    }}
  }}, 1000);
}})();
</script>
"""

    support_html = ""
    if contact_text.strip() or footer_text.strip():
        support_html = f"""
<div class="card">
  <h2>Support</h2>
  <div class="contact-box">{esc(contact_text) if contact_text.strip() else 'Please contact the WiFi administrator if you need help.'}</div>
  <p class="muted" style="margin:9px 0 0">{esc(footer_text)}</p>
</div>
"""

    body = f"""
<div class="card status-card">
  <div class="status-icon {status_class}">{esc(status_icon)}</div>
  <h1>Device Status</h1>
  <h2 class="{ 'ok' if online else 'bad' }">{esc(status)}</h2>
  <p class="muted">{esc(status_hint)}</p>
  {countdown_html}
</div>

<div class="card">
  <h2>Access</h2>
  <div class="row"><span>Voucher</span><b>{esc(voucher_display)}</b></div>
  <div class="row"><span>Plan</span><b>{esc(plan)}</b></div>
  <div class="row"><span>Download</span><b>{esc(download)} Mbps</b></div>
  <div class="row"><span>Upload</span><b>{esc(upload)} Mbps</b></div>
  <div class="row"><span>Remaining</span><b>{esc(remaining)}</b></div>
  <div class="row"><span>Login</span><b>{esc(login_at)}</b></div>
  <div class="row"><span>Expire</span><b>{esc(expire_at)}</b></div>
</div>

<div class="card">
  <h2>Device</h2>
  <div class="row"><span>Name</span><b>{esc(hostname or 'Unknown Device')}</b></div>
  <div class="row"><span>MAC</span><b>{esc(mac_display)}</b></div>
  <div class="row"><span>IP</span><b>{esc(ip)}</b></div>
</div>

<div class="card">
  <h2>Actions</h2>
  {action_buttons}
  <p class="muted" style="text-align:center;margin:9px 0 0">If the status is wrong, reconnect WiFi and refresh this page.</p>
</div>

{support_html}
"""

    self.send_html(_wp_customer_page_polished("Device Status", body))


def _wp_show_auth_placeholder_polished(self):
    form = self.read_form()
    code = str(form.get("code", "") or "").strip().upper()
    ok, message, mac, hostname, remaining_seconds = authenticate_voucher(code, self.client_address[0])

    if ok:
        remain_text = _wp_customer_seconds_text(remaining_seconds)

        body = f"""
<div class="card status-card">
  <div class="status-icon status-ok">✓</div>
  <h1>Connected Successfully</h1>
  <p class="muted">{esc(message)}</p>

  <div class="countdown-box">
    <span>Checking connection in</span>
    <b id="success-countdown">3</b>
  </div>

  <div class="card" style="box-shadow:none;background:rgba(2,6,23,.36);margin-top:12px">
    <div class="row"><span>Device</span><b>{esc(hostname or 'Unknown Device')}</b></div>
    <div class="row"><span>MAC</span><b>{esc(mac or '-')}</b></div>
    <div class="row"><span>Access Time</span><b>{esc(remain_text)}</b></div>
  </div>

  <a class="btn" href="/check">Check Connection Now</a>
  <a class="btn secondary" href="http://{esc(LAN_IP)}/check">Check Device Status</a>
  <p class="muted" style="text-align:center">If the Internet is already working, you can close this page.</p>
</div>

<script>
(function() {{
  var seconds = 3;
  var el = document.getElementById("success-countdown");
  function tick() {{
    if (el) {{ el.textContent = seconds; }}
    if (seconds <= 0) {{
      window.location.href = "/check";
      return;
    }}
    seconds -= 1;
    setTimeout(tick, 1000);
  }}
  tick();
}})();
</script>
"""
        self.send_html(_wp_customer_page_polished("Connected Successfully", body))
        return

    popup_script = ""
    settings = load_settings()
    security = settings.get("security", {})
    lock_message_template = str(security.get("lock_message", "") or "")
    if lock_message_template and mac:
        locked_now, remain_now = is_security_locked(mac, self.client_address[0])
        if locked_now:
            popup_script = "<script>alert(" + json.dumps(message) + ");</script>"

    locked_now_for_page = False
    if mac:
        locked_now_for_page, remain_now_for_page = is_security_locked(mac, self.client_address[0])

    if locked_now_for_page:
        failed_title = "Device Temporarily Locked"
        failed_hint = "Please wait for the lock time to expire, or contact the administrator."
        button_text = "Back to Login"
    else:
        failed_title = "Authentication Failed"
        failed_hint = "Please check your voucher code and try again."
        button_text = "Try Again"

    body = f"""
<div class="card status-card">
  <div class="status-icon status-bad">!</div>
  <h1>{esc(failed_title)}</h1>
  <p class="muted">{esc(failed_hint)}</p>

  <div class="countdown-box" style="border-color:rgba(248,113,113,.35);background:rgba(127,29,29,.22)">
    <span>Message</span>
    <b style="font-size:22px;line-height:1.2">{esc(message)}</b>
  </div>

  <div class="card" style="box-shadow:none;background:rgba(2,6,23,.36);margin-top:12px">
    <div class="row"><span>Device</span><b>{esc(hostname or 'Unknown Device')}</b></div>
    <div class="row"><span>MAC</span><b>{esc(mac or '-')}</b></div>
  </div>

  <a class="btn" href="/">{esc(button_text)}</a>
  <p class="muted" style="text-align:center">Contact admin if you believe this is a mistake.</p>
</div>
{popup_script}
"""
    self.send_html(_wp_customer_page_polished(failed_title, body))


Handler.show_customer_login = _wp_show_customer_login_polished
Handler.show_customer_check = _wp_show_customer_check_polished
Handler.show_auth_placeholder = _wp_show_auth_placeholder_polished
customer_page = _wp_customer_page_polished





# CUSTOMER_EASY_USE_V2
# Mobile-first customer login/check page. English customer UI only.
# Does not change voucher authentication, firewall, nft, qos, or admin logic.

def _wp_customer_v2_seconds_text(seconds):
    try:
        seconds = int(seconds or 0)
    except Exception:
        seconds = 0

    if seconds <= 0:
        return "Permanent"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m"
    return str(max(0, seconds)) + "s"


def _wp_customer_v2_speed_text(value):
    value = str(value if value is not None else "-").strip()
    if not value or value == "-":
        return "-"
    lower = value.lower()
    if "mbps" in lower or "kbps" in lower:
        return value
    return value + " Mbps"













































































































































































































































































































































































































































































































def _wp_show_customer_login_easy_v2(self, default_code=""):
    settings = load_settings()
    portal = settings.get("portal_page", {})

    title = str(portal.get("title", "24 Hours WiFi") or "24 Hours WiFi")
    notice = str(portal.get("notice", "Enter your voucher code to access the Internet.") or "Enter your voucher code to access the Internet.")
    plan_text = str(portal.get("plan_text", "") or "")
    contact_text = str(portal.get("contact_text", "") or "")
    footer_text = str(portal.get("footer_text", "") or "")

    plan_html = ""
    if plan_text.strip():
        plan_html = f"""
<div class="card plan-card">
  <div class="round-icon">◆</div>
  <div>
    <span class="label">WiFi Plan</span>
    <b>{esc(plan_text)}</b>
  </div>
</div>
"""

    help_html = ""
    if contact_text.strip() or footer_text.strip():
        help_html = f"""
<div class="card help-card">
  <div class="round-icon" style="background:rgba(6,78,59,.52);border-color:rgba(52,211,153,.38);color:#dcfce7">☎</div>
  <div>
    <span class="help-label">NEED HELP?</span>
    <b>{esc(contact_text) if contact_text.strip() else 'Please contact the WiFi administrator if you need help.'}</b>
  </div>
</div>
<p class="footer-note">{esc(footer_text)}</p>
"""

    body = f"""
<div class="card hero-card">
  <span class="pill">Local WiFi Access</span>
  <h1>{esc(title)}</h1>
  <p class="sub">{esc(notice)}</p>
</div>

{plan_html}

<div class="card login-card">
  <div class="login-title">Enter Voucher Code</div>
  <form method="post" action="/auth" style="margin:0">
    <div class="voucher-input-wrap">
      <span class="voucher-input-icon">▱</span>
      <input class="voucher-input" name="code" value="{esc(default_code)}" placeholder="Enter voucher code" autocomplete="off" autocapitalize="characters" autofocus required>
    </div>
    <button type="submit">Connect Now</button>
  </form>
  <div class="small-link-line">Already connected? <a class="link" href="http://{esc(LAN_IP)}/check">Check device status</a></div>
</div>"""

{help_html}
"""

    self.send_html(_wp_customer_v2_page(title, body))


def _wp_show_customer_check_easy_v2(self):
    ip = self.client_address[0]
    mac, hostname = get_client_identity(ip)
    db = load_db()
    settings = load_settings()
    portal = settings.get("portal_page", {})

    device = db.get("devices", {}).get(mac, {}) if mac else {}
    if device.get("hostname") and device.get("hostname") != "Unknown Device":
        hostname = device.get("hostname")

    voucher_code = str(device.get("voucher_code", "") or "").strip()
    online = bool(device.get("online"))
    expire_at_raw = int(device.get("expire_at", 0) or 0)
    login_at_raw = int(device.get("login_at", 0) or 0)

    if expire_at_raw > 0 and expire_at_raw <= now():
        online = False

    if online:
        status = "Connected"
        status_message = "Your device is authenticated and can access the Internet."
        status_icon = "✓"
        status_icon_class = "ok"
        status_text_class = "status-text-ok"
    else:
        status = "Not Connected"
        status_message = "Your device is not authenticated or your session has expired."
        status_icon = "!"
        status_icon_class = "bad"
        status_text_class = "status-text-bad"

    if online:
        plan = str(device.get("speed_profile_name", "-") or "-")
        download = _wp_customer_v2_speed_text(device.get("download_mbps", "-"))
        upload = _wp_customer_v2_speed_text(device.get("upload_mbps", "-"))
        voucher_display = voucher_code if voucher_code else "-"
        login_at = format_time(login_at_raw)
        expire_at = "Permanent" if expire_at_raw == 0 else format_time(expire_at_raw)

        if expire_at_raw == 0:
            remaining_seconds = 0
            remaining = "Permanent"
        else:
            remaining_seconds = max(0, expire_at_raw - now())
            remaining = _wp_customer_v2_seconds_text(remaining_seconds)
    else:
        plan = "-"
        download = "-"
        upload = "-"
        voucher_display = "-"
        login_at = "-"
        expire_at = "-"
        remaining_seconds = 0
        remaining = "-"

    mac_display = mac or "-"
    contact_text = str(portal.get("contact_text", "") or "")
    footer_text = str(portal.get("footer_text", "") or "")

    countdown_html = ""
    if online and remaining_seconds > 0:
        countdown_html = f"""
<div class="countdown-box">
  <span>Live Remaining Time</span>
  <b id="check-countdown" data-seconds="{remaining_seconds}">{esc(remaining)}</b>
</div>
<script>
(function(){{
  var el = document.getElementById("check-countdown");
  if (!el) return;
  var seconds = parseInt(el.getAttribute("data-seconds") || "0", 10);
  function formatRemain(s) {{
    if (s <= 0) return "Expired";
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    if (d > 0) return d + "d " + h + "h " + m + "m";
    if (h > 0) return h + "h " + m + "m " + sec + "s";
    if (m > 0) return m + "m " + sec + "s";
    return sec + "s";
  }}
  setInterval(function(){{
    seconds -= 1;
    el.textContent = formatRemain(seconds);
    if (seconds <= 0) {{
      el.style.color = "#f87171";
    }}
  }}, 1000);
}})();
</script>
"""

    if online:
        action_buttons = f"""
<a class="btn" href="/check">Check Connection</a>
<a class="btn green" href="/check">Refresh Status</a>
"""
    else:
        action_buttons = f"""
<a class="btn" href="/">Enter Voucher Code</a>
<a class="btn dark" href="/check">Refresh Status</a>
"""

    help_html = ""
    if contact_text.strip() or footer_text.strip():
        help_html = f"""
<div class="card help-card">
  <div class="round-icon" style="background:rgba(6,78,59,.52);border-color:rgba(52,211,153,.38);color:#dcfce7">☎</div>
  <div>
    <span class="help-label">NEED HELP?</span>
    <b>{esc(contact_text) if contact_text.strip() else "Please contact the WiFi administrator if you need help."}</b>
  </div>
</div>
<p class="footer-note">{esc(footer_text)}</p>
"""

    body = f"""
<div class="card status-hero">
  <div class="big-status-icon {status_icon_class}">{esc(status_icon)}</div>
  <div>
    <h1>Device Status</h1>
    <div class="{status_text_class}">{esc(status)}</div>
    <p class="sub" style="margin-top:8px">{esc(status_message)}</p>
  </div>
</div>

<div class="card summary-card">
  <div class="summary-item">
    <span class="summary-label">Voucher</span>
    <b class="summary-value">{esc(voucher_display)}</b>
  </div>
  <div class="summary-item">
    <span class="summary-label">Plan</span>
    <b class="summary-value">{esc(plan)}</b>
  </div>
  <div class="summary-item">
    <span class="summary-label">Remaining</span>
    <b class="summary-value good">{esc(remaining)}</b>
  </div>
</div>

{countdown_html}

<div class="card">
  <div class="section-title"><div class="square-icon">▣</div><h2>Access Details</h2></div>
  <div class="row"><span>Voucher</span><b>{esc(voucher_display)}</b></div>
  <div class="row"><span>Plan</span><b>{esc(plan)}</b></div>
  <div class="row"><span>Download</span><b>{esc(download)}</b></div>
  <div class="row"><span>Upload</span><b>{esc(upload)}</b></div>
  <div class="row"><span>Login</span><b>{esc(login_at)}</b></div>
  <div class="row"><span>Expire</span><b>{esc(expire_at)}</b></div>
</div>

<div class="card">
  <div class="section-title"><div class="square-icon">▯</div><h2>Device</h2></div>
  <div class="row"><span>Name</span><b>{esc(hostname or 'Unknown Device')}</b></div>
  <div class="row"><span>MAC</span><b>{esc(mac_display)}</b></div>
  <div class="row"><span>IP</span><b>{esc(ip)}</b></div>
</div>

<div class="card">
  <div class="section-title"><div class="square-icon">⚡</div><h2>Actions</h2></div>
  {action_buttons}
</div>

{help_html}
"""

    self.send_html(_wp_customer_v2_page("Device Status", body))


def _wp_show_auth_placeholder_easy_v2(self):
    form = self.read_form()
    code = str(form.get("code", "") or "").strip().upper()
    ok, message, mac, hostname, remaining_seconds = authenticate_voucher(code, self.client_address[0])

    if ok:
        remain_text = _wp_customer_v2_seconds_text(remaining_seconds)

        body = f"""
<div class="card status-hero">
  <div class="big-status-icon ok">✓</div>
  <div>
    <h1>Connected Successfully</h1>
    <div class="status-text-ok">Connected</div>
    <p class="sub" style="margin-top:8px">{esc(message)}</p>
  </div>
</div>

<div class="card summary-card">
  <div class="summary-item">
    <span class="summary-label">Device</span>
    <b class="summary-value">{esc(hostname or 'Unknown Device')}</b>
  </div>
  <div class="summary-item">
    <span class="summary-label">MAC</span>
    <b class="summary-value">{esc(mac or '-')}</b>
  </div>
  <div class="summary-item">
    <span class="summary-label">Remaining</span>
    <b class="summary-value good">{esc(remain_text)}</b>
  </div>
</div>

<div class="card">
  <div class="countdown-box" style="margin-top:0">
    <span>Checking connection in</span>
    <b id="success-countdown">3</b>
  </div>
  <a class="btn" href="/check">Check Connection Now</a>
  <a class="btn green" href="http://{esc(LAN_IP)}/check">Check Device Status</a>
  <p class="footer-note" style="margin-bottom:0">If the Internet is already working, you can close this page.</p>
</div>

<script>
(function() {{
  var seconds = 3;
  var el = document.getElementById("success-countdown");
  function tick() {{
    if (el) {{ el.textContent = seconds; }}
    if (seconds <= 0) {{
      window.location.href = "/check";
      return;
    }}
    seconds -= 1;
    setTimeout(tick, 1000);
  }}
  tick();
}})();
</script>
"""
        self.send_html(_wp_customer_v2_page("Connected Successfully", body))
        return

    popup_script = ""
    settings = load_settings()
    security = settings.get("security", {})
    lock_message_template = str(security.get("lock_message", "") or "")
    if lock_message_template and mac:
        locked_now, remain_now = is_security_locked(mac, self.client_address[0])
        if locked_now:
            popup_script = "<script>alert(" + json.dumps(message) + ");</script>"

    locked_now_for_page = False
    if mac:
        locked_now_for_page, remain_now_for_page = is_security_locked(mac, self.client_address[0])

    if locked_now_for_page:
        failed_title = "Device Temporarily Locked"
        failed_hint = "Please wait for the lock time to expire, or contact the administrator."
        button_text = "Back to Login"
    else:
        failed_title = "Authentication Failed"
        failed_hint = "Please check your voucher code and try again."
        button_text = "Try Again"

    body = f"""
<div class="card status-hero">
  <div class="big-status-icon bad">!</div>
  <div>
    <h1>{esc(failed_title)}</h1>
    <div class="status-text-bad">Failed</div>
    <p class="sub" style="margin-top:8px">{esc(failed_hint)}</p>
  </div>
</div>

<div class="card">
  <div class="countdown-box" style="margin-top:0;border-color:rgba(248,113,113,.38);background:rgba(127,29,29,.22)">
    <span>Message</span>
    <b style="font-size:22px;line-height:1.22">{esc(message)}</b>
  </div>
  <div class="row"><span>Device</span><b>{esc(hostname or 'Unknown Device')}</b></div>
  <div class="row"><span>MAC</span><b>{esc(mac or '-')}</b></div>
  <a class="btn" href="/">{esc(button_text)}</a>
  <p class="footer-note" style="margin-bottom:0">Contact admin if you believe this is a mistake.</p>
</div>
{popup_script}
"""
    self.send_html(_wp_customer_v2_page(failed_title, body))


Handler.show_customer_login = _wp_show_customer_login_easy_v2
Handler.show_customer_check = _wp_show_customer_check_easy_v2
Handler.show_auth_placeholder = _wp_show_auth_placeholder_easy_v2
customer_page = _wp_customer_v2_page

if __name__ == "__main__":
    main()
