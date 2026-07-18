import os
import subprocess
import time
from wifiportal.config import CONFIG, LAN_IF, WAN_IF, QOS_IFB
from wifiportal.utils import now, normalize_mac
from wifiportal.db import load_db, save_db, append_log, load_settings, create_backup, cleanup_old_backups

def run_command(command):
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as error:
        return 999, "", str(error)

_nft_table_initialized = False

def check_nft_table_exists():
    global _nft_table_initialized
    if _nft_table_initialized:
        return True
    code, out, err = run_command(["/usr/sbin/nft", "list", "table", "inet", "wifiportal"])
    if code == 0:
        _nft_table_initialized = True
        return True
    return False

def nft_available():
    code, out, err = run_command(["/usr/sbin/nft", "--version"])
    return code == 0

def nft_delete_table():
    global _nft_table_initialized
    _nft_table_initialized = False
    run_command(["/usr/sbin/nft", "delete", "table", "inet", "wifiportal"])

def nft_init_table():
    global _nft_table_initialized
    if not nft_available():
        return False, "nftables not available"

    nft_delete_table()

    rules = f"""
table inet wifiportal {{
  set authed_macs {{
    type ether_addr
    flags timeout
  }}

  set whitelist_macs {{
    type ether_addr
  }}

  set blacklist_macs {{
    type ether_addr
  }}

  chain portal_dns_redirect {{
    type nat hook prerouting priority dstnat - 20; policy accept;
    iifname "{LAN_IF}" udp dport 53 redirect to :53
    iifname "{LAN_IF}" tcp dport 53 redirect to :53
  }}

  chain portal_http_redirect {{
    type nat hook prerouting priority dstnat - 10; policy accept;
    iifname "{LAN_IF}" ether saddr @blacklist_macs tcp dport 80 redirect to :80
    iifname "{LAN_IF}" ether saddr != @authed_macs ether saddr != @whitelist_macs tcp dport 80 redirect to :80
  }}

  chain portal_forward_guard {{
    type filter hook forward priority -10; policy accept;
    iifname "{LAN_IF}" oifname "{WAN_IF}" ether saddr @blacklist_macs reject
    iifname "{LAN_IF}" oifname "{WAN_IF}" ether saddr @whitelist_macs accept
    iifname "{LAN_IF}" oifname "{WAN_IF}" ether saddr @authed_macs accept
    iifname "{LAN_IF}" oifname "{WAN_IF}" reject
  }}
}}
"""
    result = subprocess.run(
        ["/usr/sbin/nft", "-f", "-"],
        input=rules,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=8
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or "nft init failed"

    _nft_table_initialized = True

    db = load_db()
    for mac in db.get("whitelist", {}).keys():
        nft_add_whitelist(mac)

    append_log("FIREWALL", "防火墙认证拦截已初始化")
    return True, "firewall initialized"

def nft_add_element(set_name, mac, timeout_seconds=0):
    mac = normalize_mac(mac)
    if not mac:
        return False

    if timeout_seconds and timeout_seconds > 0:
        element = "{ %s timeout %ss }" % (mac, int(timeout_seconds))
    else:
        element = "{ %s }" % mac

    code, out, err = run_command(["/usr/sbin/nft", "add", "element", "inet", "wifiportal", set_name, element])
    if code == 0:
        return True

    run_command(["/usr/sbin/nft", "delete", "element", "inet", "wifiportal", set_name, "{ %s }" % mac])
    code, out, err = run_command(["/usr/sbin/nft", "add", "element", "inet", "wifiportal", set_name, element])
    return code == 0

def nft_delete_element(set_name, mac):
    mac = normalize_mac(mac)
    if not mac:
        return
    run_command(["/usr/sbin/nft", "delete", "element", "inet", "wifiportal", set_name, "{ %s }" % mac])

def nft_allow_device(mac, seconds=0):
    if not check_nft_table_exists():
        return False
    return nft_add_element("authed_macs", mac, seconds)

def nft_kick_device(mac):
    if not check_nft_table_exists():
        return
    nft_delete_element("authed_macs", mac)

def nft_add_whitelist(mac):
    if not check_nft_table_exists():
        return False
    return nft_add_element("whitelist_macs", mac, 0)

def nft_delete_whitelist(mac):
    if not check_nft_table_exists():
        return
    nft_delete_element("whitelist_macs", mac)

def nft_add_blacklist(mac):
    if not check_nft_table_exists():
        return False
    if check_nft_table_exists():
        nft_delete_element("authed_macs", mac)
        nft_delete_element("whitelist_macs", mac)
    return nft_add_element("blacklist_macs", mac, 0)

def nft_delete_blacklist(mac):
    if not check_nft_table_exists():
        return
    nft_delete_element("blacklist_macs", mac)

def restore_firewall_sessions():
    if not check_nft_table_exists():
        return

    db = load_db()
    t = now()

    for mac in db.get("whitelist", {}).keys():
        nft_add_whitelist(mac)

    for mac in db.get("blacklist", {}).keys():
        nft_add_blacklist(mac)

    for mac, device in db.get("devices", {}).items():
        if not device.get("online"):
            continue
        if device.get("voucher_code") == "WHITELIST":
            nft_add_whitelist(mac)
            continue

        expire_at = int(device.get("expire_at", 0) or 0)
        if expire_at == 0:
            nft_allow_device(mac, 0)
        elif expire_at > t:
            nft_allow_device(mac, expire_at - t)

def cleanup_expired_and_firewall():
    db = load_db()
    changed = False
    t = now()

    for code, voucher in db.get("vouchers", {}).items():
        if int(voucher.get("minutes", 0)) == 0:
            continue

        expire_at = int(voucher.get("expire_at", 0) or 0)
        if not (expire_at > 0 and expire_at <= t):
            continue

        voucher_devices = voucher.get("devices", {})
        if not isinstance(voucher_devices, dict):
            continue

        for mac in list(voucher_devices.keys()):
            current_device = db.get("devices", {}).get(mac, {})
            current_code = ""
            if isinstance(current_device, dict):
                current_code = str(current_device.get("voucher_code", "") or "").strip()

            if current_code == str(code):
                nft_kick_device(mac)
                safe_qos_remove_device(mac)
                if mac in db.get("devices", {}):
                    db["devices"][mac]["online"] = False
                    db["devices"][mac]["last_seen"] = t
                changed = True

            try:
                voucher_devices[mac]["online"] = False
            except Exception:
                pass

    if changed:
        save_db(db)
        append_log("CLEANUP", "清理过期设备和防火墙放行：仅踢仍使用过期兑换码的设备")

def firewall_status_text():
    if check_nft_table_exists():
        return "已启用"
    return "未启用"

def auto_backup_if_needed():
    backup_dir = "/etc/wifiportal/backup"
    os.makedirs(backup_dir, exist_ok=True)

    today = time.strftime("%Y%m%d")
    marker = os.path.join(backup_dir, f".auto-backup-{today}")

    if os.path.exists(marker):
        return

    backup_file = create_backup()
    cleanup_old_backups(7)

    with open(marker, "w", encoding="utf-8") as file:
        file.write(str(now()))

    append_log("BACKUP", f"自动备份 {os.path.basename(backup_file)}")

_qos_init_failed_cached = False

def qos_enabled():
    global _qos_init_failed_cached
    if _qos_init_failed_cached:
        return False
    return str(CONFIG.get("ENABLE_QOS", "1")) == "1"

def qos_tc():
    if os.path.exists("/sbin/tc"):
        return "/sbin/tc"
    return "/usr/sbin/tc"

def qos_ip():
    if os.path.exists("/sbin/ip"):
        return "/sbin/ip"
    return "/usr/sbin/ip"

def qos_class_id(mac):
    mac = normalize_mac(mac)
    if not mac:
        return "100"
    value = 0
    for ch in mac.replace(":", ""):
        value = (value * 16 + int(ch, 16)) % 50000
    minor = 100 + value
    return format(minor, "x")

def qos_prio_id(mac):
    mac = normalize_mac(mac)
    if not mac:
        return "100"
    value = 0
    for ch in mac.replace(":", ""):
        value = (value * 16 + int(ch, 16)) % 50000
    return str(100 + value)

def qos_rate(kbps):
    try:
        kbps = int(kbps)
    except Exception:
        kbps = 0
    if kbps <= 0:
        return ""
    return f"{kbps}kbit"

def qos_run(command):
    return run_command(command)

def qos_clear():
    tc = qos_tc()
    ip = qos_ip()
    qos_run([tc, "qdisc", "del", "dev", LAN_IF, "root"])
    qos_run([tc, "qdisc", "del", "dev", LAN_IF, "ingress"])
    qos_run([tc, "qdisc", "del", "dev", QOS_IFB, "root"])
    qos_run([ip, "link", "set", QOS_IFB, "down"])
    qos_run([ip, "link", "delete", QOS_IFB])
    append_log("QOS", "清空限速规则")

def qos_init():
    global _qos_init_failed_cached
    if _qos_init_failed_cached:
        return False, "QoS disabled due to previous initialization failure"
    if not qos_enabled():
        return False, "QoS disabled"

    tc = qos_tc()
    ip = qos_ip()

    if not os.path.exists(tc):
        _qos_init_failed_cached = True
        try:
            append_log("QOS", "初始化限速模块失败：未找到 tc 工具，QoS 将自动禁用", result="FAIL")
        except Exception:
            pass
        return False, "tc not found"

    code, out, err = qos_run([tc, "-V"])
    if code != 0:
        _qos_init_failed_cached = True
        try:
            append_log("QOS", f"初始化限速模块失败：无法执行 tc 命令 ({err})，QoS 将自动禁用", result="FAIL")
        except Exception:
            pass
        return False, f"tc execution check failed: {err}"

    qos_run([ip, "link", "add", QOS_IFB, "type", "ifb"])
    qos_run([ip, "link", "set", QOS_IFB, "up"])

    qos_run([tc, "qdisc", "replace", "dev", LAN_IF, "root", "handle", "1:", "htb", "default", "9999"])
    qos_run([tc, "class", "replace", "dev", LAN_IF, "parent", "1:", "classid", "1:1", "htb", "rate", "1000mbit", "ceil", "1000mbit"])
    qos_run([tc, "class", "replace", "dev", LAN_IF, "parent", "1:1", "classid", "1:9999", "htb", "rate", "1000mbit", "ceil", "1000mbit"])

    qos_run([tc, "qdisc", "replace", "dev", LAN_IF, "ingress"])
    qos_run([
        tc, "filter", "replace", "dev", LAN_IF,
        "parent", "ffff:", "protocol", "ip", "prio", "1",
        "matchall", "action", "mirred", "egress", "redirect", "dev", QOS_IFB
    ])

    qos_run([tc, "qdisc", "replace", "dev", QOS_IFB, "root", "handle", "1:", "htb", "default", "9999"])
    qos_run([tc, "class", "replace", "dev", QOS_IFB, "parent", "1:", "classid", "1:1", "htb", "rate", "1000mbit", "ceil", "1000mbit"])
    qos_run([tc, "class", "replace", "dev", QOS_IFB, "parent", "1:1", "classid", "1:9999", "htb", "rate", "1000mbit", "ceil", "1000mbit"])

    append_log("QOS", "初始化限速模块")
    return True, "QoS initialized"

def qos_remove_device(mac):
    if not qos_enabled():
        return

    mac = normalize_mac(mac)
    if not mac:
        return

    tc = qos_tc()
    cid = str(qos_class_id(mac))
    prio = str(qos_prio_id(mac))

    qos_run([tc, "filter", "del", "dev", LAN_IF, "protocol", "ip", "parent", "1:", "prio", prio])
    qos_run([tc, "class", "del", "dev", LAN_IF, "classid", f"1:{cid}"])

    qos_run([tc, "filter", "del", "dev", QOS_IFB, "protocol", "ip", "parent", "1:", "prio", prio])
    qos_run([tc, "class", "del", "dev", QOS_IFB, "classid", f"1:{cid}"])

def qos_apply_device(mac, ip_addr, download_kbps, upload_kbps):
    if not qos_enabled():
        return True

    mac = normalize_mac(mac)
    if not mac or not ip_addr:
        return False

    try:
        download_kbps = int(download_kbps)
        upload_kbps = int(upload_kbps)
    except Exception:
        return False

    if download_kbps <= 0 and upload_kbps <= 0:
        qos_remove_device(mac)
        return True

    ok, message = qos_init()
    if not ok:
        append_log("QOS", f"限速初始化失败：{message}", mac=mac, ip=ip_addr, result="FAIL")
        return False

    qos_remove_device(mac)

    tc = qos_tc()
    cid = str(qos_class_id(mac))
    prio = str(qos_prio_id(mac))

    if download_kbps > 0:
        rate = qos_rate(download_kbps)
        code, out, err = qos_run([tc, "class", "replace", "dev", LAN_IF, "parent", "1:1", "classid", f"1:{cid}", "htb", "rate", rate, "ceil", rate])
        if code != 0:
            append_log("QOS", f"下载 class 创建失败：{err}", mac=mac, ip=ip_addr, result="FAIL")
        code, out, err = qos_run([
            tc, "filter", "replace", "dev", LAN_IF,
            "protocol", "ip", "parent", "1:", "prio", prio,
            "u32", "match", "ip", "dst", f"{ip_addr}/32",
            "flowid", f"1:{cid}"
        ])
        if code != 0:
            append_log("QOS", f"下载 filter 创建失败：{err}", mac=mac, ip=ip_addr, result="FAIL")

    if upload_kbps > 0:
        rate = qos_rate(upload_kbps)
        code, out, err = qos_run([tc, "class", "replace", "dev", QOS_IFB, "parent", "1:1", "classid", f"1:{cid}", "htb", "rate", rate, "ceil", rate])
        if code != 0:
            append_log("QOS", f"上传 class 创建失败：{err}", mac=mac, ip=ip_addr, result="FAIL")
        code, out, err = qos_run([
            tc, "filter", "replace", "dev", QOS_IFB,
            "protocol", "ip", "parent", "1:", "prio", prio,
            "u32", "match", "ip", "src", f"{ip_addr}/32",
            "flowid", f"1:{cid}"
        ])
        if code != 0:
            append_log("QOS", f"上传 filter 创建失败：{err}", mac=mac, ip=ip_addr, result="FAIL")

    append_log("QOS", f"应用限速 {ip_addr} {download_kbps}k/{upload_kbps}k", mac=mac, ip=ip_addr)
    return True

def qos_restore_sessions():
    if not qos_enabled():
        return

    qos_init()
    db = load_db()
    for mac, device in db.get("devices", {}).items():
        if not device.get("online"):
            continue
        if device.get("voucher_code") == "WHITELIST":
            safe_qos_remove_device(mac)
            continue

        expire_at = int(device.get("expire_at", 0) or 0)
        if expire_at > 0 and expire_at <= now():
            continue

        safe_qos_apply_device(
            mac,
            device.get("ip", ""),
            device.get("download_kbps", 0),
            device.get("upload_kbps", 0)
        )

def qos_status_text():
    if not qos_enabled():
        return "未启用"
    code, out, err = qos_run(["/sbin/tc", "qdisc", "show", "dev", LAN_IF])
    if code == 0 and "htb" in out:
        return "已启用"
    return "未初始化"

def safe_qos_apply_device(mac, ip, download_kbps, upload_kbps):
    try:
        return qos_apply_device(mac, ip, download_kbps, upload_kbps)
    except Exception as error:
        try:
            append_log("QOS", f"应用限速失败：{error}", mac=mac, ip=ip, result="FAIL")
        except Exception:
            pass
        return False

def safe_qos_remove_device(mac):
    try:
        qos_remove_device(mac)
    except Exception as error:
        try:
            append_log("QOS", f"清理限速失败：{error}", mac=mac, result="FAIL")
        except Exception:
            pass
