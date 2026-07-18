# local-wifiportal-openwrt 2.0

Local voucher captive portal for OpenWrt.

This package includes:

- wifiportal.py (lightweight launcher)
- wifiportal/ (core python modules)
- init.d/wifiportal (procd service manager)
- install.sh (one-click installation script)
- README.md
- .gitignore

## One-Click Deployment (一键部署命令)

Log in to your OpenWrt router via SSH, and run the following command:

```bash
wget -qO- https://raw.githubusercontent.com/indrachen-sl/local-wifiportal-openwrt/main/install.sh | sh
```

> [!WARNING]
> Do not upload production data such as vouchers.json, settings.json, config, admin_security.json, backups, or runtime database files to public repositories.
