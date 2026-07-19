#!/bin/sh

# local-wifiportal-openwrt 2.0 一键部署脚本
# 适用系统: OpenWrt 21.02 / 22.03 及以上版本

set -e

echo "============================================="
echo "   开始部署 local-wifiportal-openwrt 2.0"
echo "============================================="

# 1. 检查运行环境
if [ ! -f /etc/openwrt_release ]; then
    echo "⚠️ 错误: 此脚本仅适用于 OpenWrt 系统！"
    exit 1
fi

# 2. 安装必要依赖包
echo "正在更新包列表并安装依赖 (Python3, nftables)..."
opkg update
opkg install python3 python3-urllib nftables tc-full 2>/dev/null || opkg install python3 python3-urllib nftables tc

# 3. 创建目录结构
echo "正在创建文件夹结构..."
mkdir -p /usr/lib/wifiportal
mkdir -p /etc/wifiportal
mkdir -p /var/log/wifiportal

# 4. 下载最新代码文件
BASE_URL="https://raw.githubusercontent.com/indrachen-sl/local-wifiportal-openwrt/main"

create_code_backup() {
    BACKUP_DIR="/etc/wifiportal/install-backups"
    BACKUP_FILE="$BACKUP_DIR/wifiportal-code-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
    BACKUP_ITEMS=""

    mkdir -p "$BACKUP_DIR"

    [ -f /usr/bin/wifiportal_launcher.py ] && BACKUP_ITEMS="$BACKUP_ITEMS /usr/bin/wifiportal_launcher.py"
    [ -d /usr/lib/wifiportal ] && BACKUP_ITEMS="$BACKUP_ITEMS /usr/lib/wifiportal"
    [ -f /etc/init.d/wifiportal ] && BACKUP_ITEMS="$BACKUP_ITEMS /etc/init.d/wifiportal"
    [ -f /etc/wifiportal/config ] && BACKUP_ITEMS="$BACKUP_ITEMS /etc/wifiportal/config"

    if [ -n "$BACKUP_ITEMS" ]; then
        if tar -czf "$BACKUP_FILE" $BACKUP_ITEMS 2>/dev/null; then
            echo "已备份当前 WiFiPortal 程序到: $BACKUP_FILE"
        else
            echo "⚠️ 当前程序备份失败，继续部署。"
        fi
    fi
}

download_file() {
    DEST="$1"
    URL="$2"
    wget -qO "$DEST" "$URL"
    if [ ! -s "$DEST" ]; then
        echo "❌ 下载失败或文件为空: $URL"
        echo "请检查路由器网络、DNS、GitHub raw 地址是否可访问。"
        exit 1
    fi
}

create_code_backup

echo "正在下载主执行脚本及模块..."
rm -f /usr/lib/wifiportal/wifiportal.py
rm -f /usr/bin/wifiportal.py
download_file /usr/bin/wifiportal_launcher.py "$BASE_URL/wifiportal.py"
download_file /usr/lib/wifiportal/__init__.py "$BASE_URL/wifiportal/__init__.py"
download_file /usr/lib/wifiportal/config.py "$BASE_URL/wifiportal/config.py"
download_file /usr/lib/wifiportal/db.py "$BASE_URL/wifiportal/db.py"
download_file /usr/lib/wifiportal/firewall.py "$BASE_URL/wifiportal/firewall.py"
download_file /usr/lib/wifiportal/server.py "$BASE_URL/wifiportal/server.py"
download_file /usr/lib/wifiportal/templates.py "$BASE_URL/wifiportal/templates.py"
download_file /usr/lib/wifiportal/utils.py "$BASE_URL/wifiportal/utils.py"

echo "正在下载系统服务脚本..."
download_file /etc/init.d/wifiportal "$BASE_URL/init.d/wifiportal"
chmod +x /etc/init.d/wifiportal

echo "正在安装 SSH 诊断命令..."
cat << 'EOF' > /usr/bin/wifiportal-diagnose
#!/bin/sh

echo "============================================="
echo " WiFiPortal Diagnostics"
echo "============================================="
echo "Time: $(date)"
echo "OpenWrt: $(cat /etc/openwrt_release 2>/dev/null | tr '\n' ' ')"
echo ""

section() {
    echo ""
    echo "---- $1 ----"
}

redact() {
    sed \
        -e 's/password_hash[=:][^ ,}]*/password_hash=<redacted>/g' \
        -e 's/password_salt[=:][^ ,}]*/password_salt=<redacted>/g' \
        -e 's/session_secret[=:][^ ,}]*/session_secret=<redacted>/g' \
        -e 's/csrf_token[=:][^ ,}]*/csrf_token=<redacted>/g'
}

section "Service"
/etc/init.d/wifiportal status 2>&1 || true

section "Processes"
ps | grep wifiportal | grep -v grep || true

section "Ports"
netstat -lntp 2>/dev/null | grep -E ':80 |:8080 ' || true

section "Config"
cat /etc/wifiportal/config 2>/dev/null | redact || true

section "uhttpd"
uci show uhttpd 2>/dev/null | redact || true

section "Python Syntax"
python3 -m py_compile \
    /usr/bin/wifiportal_launcher.py \
    /usr/lib/wifiportal/server.py \
    /usr/lib/wifiportal/config.py \
    /usr/lib/wifiportal/db.py \
    /usr/lib/wifiportal/firewall.py \
    /usr/lib/wifiportal/templates.py \
    /usr/lib/wifiportal/utils.py 2>&1 || true

section "Local HTTP"
echo "[Portal /]"
wget -q -T 5 -O- http://127.0.0.1/ 2>&1 | head -c 500 | redact
echo ""
echo "[Admin /admin]"
wget -q -T 5 -O- http://127.0.0.1/admin 2>&1 | head -c 500 | redact
echo ""
echo "[LuCI :8080]"
wget -q -T 5 -O- http://127.0.0.1:8080/ 2>&1 | head -c 500 | redact
echo ""

section "nftables"
nft list table inet wifiportal 2>&1 | head -n 80 || true

section "Disk"
df -h / /tmp /etc 2>&1 || true

section "Memory"
free 2>&1 || true

section "Recent WiFiPortal Logs"
logread 2>/dev/null | grep -i wifiportal | tail -n 120 | redact || true

section "Install Backups"
ls -1 /etc/wifiportal/install-backups/wifiportal-code-backup-*.tar.gz 2>/dev/null | tail -n 10 || true

echo ""
echo "============================================="
echo " End of WiFiPortal Diagnostics"
echo "============================================="
EOF
chmod +x /usr/bin/wifiportal-diagnose

echo "正在安装 SSH 回滚命令..."
cat << 'EOF' > /usr/bin/wifiportal-rollback
#!/bin/sh

BACKUP="$1"

if [ -z "$BACKUP" ]; then
    echo "用法: wifiportal-rollback /etc/wifiportal/install-backups/wifiportal-code-backup-YYYYMMDD-HHMMSS.tar.gz"
    echo ""
    echo "可用备份："
    ls -1 /etc/wifiportal/install-backups/wifiportal-code-backup-*.tar.gz 2>/dev/null || true
    exit 1
fi

case "$BACKUP" in
    /etc/wifiportal/install-backups/wifiportal-code-backup-*.tar.gz)
        ;;
    *)
        echo "❌ 只允许恢复 /etc/wifiportal/install-backups 下的 WiFiPortal 代码备份。"
        exit 1
        ;;
esac

if [ ! -f "$BACKUP" ]; then
    echo "❌ 备份文件不存在: $BACKUP"
    exit 1
fi

if ! tar -tzf "$BACKUP" >/dev/null 2>&1; then
    echo "❌ 备份包无法读取或已损坏: $BACKUP"
    exit 1
fi

echo "准备恢复备份: $BACKUP"
/etc/init.d/wifiportal stop >/dev/null 2>&1 || true

if ! tar -xzf "$BACKUP" -C /; then
    echo "❌ 恢复失败。请检查备份包和磁盘空间。"
    exit 1
fi

[ -f /etc/init.d/wifiportal ] && chmod +x /etc/init.d/wifiportal

echo "正在检查恢复后的 Python 语法..."
python3 -m py_compile \
    /usr/bin/wifiportal_launcher.py \
    /usr/lib/wifiportal/server.py \
    /usr/lib/wifiportal/config.py \
    /usr/lib/wifiportal/db.py \
    /usr/lib/wifiportal/firewall.py \
    /usr/lib/wifiportal/templates.py \
    /usr/lib/wifiportal/utils.py 2>&1 || {
        echo "⚠️ 语法检查失败，仍会尝试启动服务。"
    }

/etc/init.d/wifiportal enable >/dev/null 2>&1 || true
/etc/init.d/wifiportal restart

echo "✅ 回滚完成。建议继续运行: wifiportal-diagnose"
EOF
chmod +x /usr/bin/wifiportal-rollback

# 5. 初始化默认配置文件
if [ ! -f /etc/wifiportal/config ]; then
    echo "正在生成默认配置文件 (/etc/wifiportal/config)..."
    cat << EOF > /etc/wifiportal/config
# WiFiPortal Config
LAN_IP=192.168.10.1
LAN_IF=br-lan
WAN_IF=wan
PORTAL_PORT=80
ENABLE_QOS=1
EOF
fi

echo "正在配置 LuCI 路由器后台到 8080 端口，释放 80 端口给认证页面..."
if command -v uci >/dev/null 2>&1 && [ -f /etc/config/uhttpd ]; then
    UHTTPD_BACKUP="/etc/config/uhttpd.wifiportal-backup-$(date +%Y%m%d-%H%M%S)"
    cp /etc/config/uhttpd "$UHTTPD_BACKUP"
    echo "已备份 LuCI/uhttpd 配置到: $UHTTPD_BACKUP"
    uci -q delete uhttpd.main.listen_http || true
    uci add_list uhttpd.main.listen_http='0.0.0.0:8080'
    uci add_list uhttpd.main.listen_http='[::]:8080'
    uci commit uhttpd
    /etc/init.d/uhttpd restart >/dev/null 2>&1 || true
else
    echo "⚠️ 未找到 uhttpd/uci，跳过 LuCI 端口配置。请确认 80 端口未被其他服务占用。"
fi

echo "正在检查 Python 语法..."
python3 -m py_compile /usr/bin/wifiportal_launcher.py /usr/lib/wifiportal/server.py /usr/lib/wifiportal/config.py /usr/lib/wifiportal/db.py /usr/lib/wifiportal/firewall.py /usr/lib/wifiportal/templates.py /usr/lib/wifiportal/utils.py

# 6. 启用并启动服务
echo "正在启动 WiFiPortal 服务并设置开机自启..."
/etc/init.d/wifiportal enable
/etc/init.d/wifiportal restart

# 7. 设置默认后台管理员密码
echo ""
echo "============================================="
echo "🎁 部署成功！正在设置默认后台管理密码..."
echo "============================================="
python3 -c "import sys; sys.path.append('/usr/lib'); from wifiportal.server import update_admin_password; ok, msg = update_admin_password('admin123456'); print('✅ 后台密码已成功设置为: admin123456' if ok else '❌ 设置失败: ' + msg)"

echo ""
echo "正在执行部署后自检..."
SELF_CHECK_FAILED=0
SELF_CHECK_LOG="/tmp/wifiportal-install-check.log"
: > "$SELF_CHECK_LOG"

wp_check() {
    NAME="$1"
    CMD="$2"
    echo "---- $NAME ----" >> "$SELF_CHECK_LOG"
    echo "$CMD" >> "$SELF_CHECK_LOG"
    if sh -c "$CMD" >/tmp/wifiportal-selfcheck.out 2>&1; then
        echo "✅ $NAME"
        echo "OK" >> "$SELF_CHECK_LOG"
    else
        SELF_CHECK_FAILED=1
        echo "❌ $NAME"
        echo "FAIL" >> "$SELF_CHECK_LOG"
        sed -n '1,8p' /tmp/wifiportal-selfcheck.out 2>/dev/null || true
    fi
    cat /tmp/wifiportal-selfcheck.out >> "$SELF_CHECK_LOG" 2>/dev/null || true
    echo "" >> "$SELF_CHECK_LOG"
}

wp_check "WiFiPortal 服务状态" "/etc/init.d/wifiportal status"
wp_check "80 端口监听" "netstat -lntp 2>/dev/null | grep ':80 '"
wp_check "8080 LuCI 端口监听" "netstat -lntp 2>/dev/null | grep ':8080 '"
wp_check "认证页本机访问" "wget -q -T 5 -O- http://127.0.0.1/ | grep -E 'WiFi|Voucher|Access|认证|兑换' >/dev/null"
wp_check "后台页面本机访问" "wget -q -T 5 -O- http://127.0.0.1/admin | grep -E 'admin|后台|登录|password|密码' >/dev/null"

if [ "$SELF_CHECK_FAILED" -ne 0 ]; then
    echo ""
    echo "⚠️ 部署自检发现异常。请复制下面命令的输出继续排查："
    echo "wifiportal-diagnose"
    echo "cat /tmp/wifiportal-install-check.log"
    echo "/etc/init.d/wifiportal status"
    echo "logread 2>/dev/null | grep -i wifiportal | tail -n 80"
    echo "netstat -lntp 2>/dev/null | grep -E ':80 |:8080 '"
else
    echo "✅ 部署后自检通过。"
fi
echo "自检日志: $SELF_CHECK_LOG"

echo ""
echo "---------------------------------------------"
echo "部署完成！您可以通过以下方式访问后台："
echo "👉 后台地址: http://192.168.10.1/admin"
echo "👉 后台账号: admin"
echo "👉 后台密码: admin123456"
echo "👉 诊断页面: http://192.168.10.1/admin/diagnostics"
echo "👉 SSH 诊断命令: wifiportal-diagnose"
echo "👉 SSH 回滚命令: wifiportal-rollback <备份包路径>"
echo "---------------------------------------------"
