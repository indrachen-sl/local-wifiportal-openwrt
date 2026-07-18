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

echo "正在下载主执行脚本及模块..."
rm -f /usr/lib/wifiportal/wifiportal.py
wget -qO /usr/bin/wifiportal.py "$BASE_URL/wifiportal.py"
wget -qO /usr/lib/wifiportal/__init__.py "$BASE_URL/wifiportal/__init__.py"
wget -qO /usr/lib/wifiportal/config.py "$BASE_URL/wifiportal/config.py"
wget -qO /usr/lib/wifiportal/db.py "$BASE_URL/wifiportal/db.py"
wget -qO /usr/lib/wifiportal/firewall.py "$BASE_URL/wifiportal/firewall.py"
wget -qO /usr/lib/wifiportal/server.py "$BASE_URL/wifiportal/server.py"
wget -qO /usr/lib/wifiportal/templates.py "$BASE_URL/wifiportal/templates.py"
wget -qO /usr/lib/wifiportal/utils.py "$BASE_URL/wifiportal/utils.py"

echo "正在下载系统服务脚本..."
wget -qO /etc/init.d/wifiportal "$BASE_URL/init.d/wifiportal"
chmod +x /etc/init.d/wifiportal

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

# 6. 启用并启动服务
echo "正在启动 WiFiPortal 服务并设置开机自启..."
/etc/init.d/wifiportal enable
/etc/init.d/wifiportal restart

# 7. 引导设置后台管理员密码
echo ""
echo "============================================="
echo "🎁 部署成功！请输入您的后台管理密码 (至少8位):"
echo "============================================="
while true; do
    read -r password
    if [ ${#password} -lt 8 ]; then
        echo "⚠️ 密码过短，至少需要 8 位，请重新输入:"
    else
        python3 -c "import sys; sys.path.append('/usr/lib'); from wifiportal.server import update_admin_password; ok, msg = update_admin_password('$password'); print('✅ 后台密码已成功设置为: ' + '$password' if ok else '❌ 设置失败: ' + msg)"
        break
    fi
done

echo ""
echo "---------------------------------------------"
echo "部署完成！您可以通过以下方式访问后台："
echo "👉 后台地址: http://192.168.10.1/admin"
echo "👉 后台账号: admin"
echo "---------------------------------------------"
