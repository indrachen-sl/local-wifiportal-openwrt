import os
import secrets

CONFIG_FILE = "/etc/wifiportal/config"

def load_shell_config(path=CONFIG_FILE):
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data

CONFIG = load_shell_config()
LAN_IP = CONFIG.get("LAN_IP", "192.168.10.1")
LAN_IF = CONFIG.get("LAN_IF", "br-lan")
WAN_IF = CONFIG.get("WAN_IF", "wan")
PORTAL_PORT = int(CONFIG.get("PORTAL_PORT", "80"))
DB_FILE = CONFIG.get("DB_FILE", "/etc/wifiportal/vouchers.json")
SETTINGS_FILE = CONFIG.get("SETTINGS_FILE", "/etc/wifiportal/settings.json")
LOG_FILE = CONFIG.get("LOG_FILE", "/var/log/wifiportal/wifiportal.log")

SESSION_SECRET = secrets.token_hex(32)
QOS_IFB = "ifb-wifiportal"
