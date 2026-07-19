# local-wifiportal-openwrt

OpenWrt 本地 WiFi 兑换码认证 Portal。它把路由器的 80 端口作为用户认证页面和 WiFiPortal 管理后台，把 OpenWrt/LuCI 路由器后台移动到 8080 端口。

## 默认访问入口

部署完成后的默认入口如下：

| 用途 | 地址 | 说明 |
| --- | --- | --- |
| 用户认证页面 | `http://192.168.10.1/` | 客户端输入兑换码上网 |
| 用户状态查询 | `http://192.168.10.1/check` | 查看当前设备认证状态、剩余时间、套餐速度 |
| WiFiPortal 管理后台 | `http://192.168.10.1/admin` | 管理兑换码、设备、限速、防火墙、备份等 |
| OpenWrt/LuCI 路由器后台 | `http://192.168.10.1:8080/` | 原路由器后台，部署脚本会自动挪到 8080 |

## 默认后台账号密码

| 项目 | 默认值 |
| --- | --- |
| 后台地址 | `http://192.168.10.1/admin` |
| 密码 | `admin123456` |

一键部署脚本会自动设置默认密码 `admin123456`，部署完成时也会直接显示账号和密码。

如需在路由器 SSH 中重置后台密码：

```sh
python3 -c "import sys; sys.path.append('/usr/lib'); from wifiportal.server import update_admin_password; ok, msg = update_admin_password('admin123456'); print('重置成功' if ok else msg)"
```

密码长度规则：至少 8 位。

## 一键部署

SSH 登录 OpenWrt 后执行：

```sh
wget -qO- https://raw.githubusercontent.com/indrachen-sl/local-wifiportal-openwrt/main/install.sh | sh
```

部署脚本会自动完成：

- 安装依赖：`python3`、`python3-urllib`、`nftables`、`tc-full` 或 `tc`
- 覆盖程序前备份当前启动器、模块、服务脚本和配置到 `/etc/wifiportal/install-backups`
- 下载程序到 `/usr/lib/wifiportal`
- 下载启动器到 `/usr/bin/wifiportal_launcher.py`
- 检查下载文件不为空，避免网络异常导致空文件覆盖程序
- 安装 procd 服务脚本到 `/etc/init.d/wifiportal`
- 安装 SSH 诊断命令 `/usr/bin/wifiportal-diagnose`
- 安装 SSH 回滚命令 `/usr/bin/wifiportal-rollback`
- 生成默认配置 `/etc/wifiportal/config`
- 备份 `/etc/config/uhttpd`，再把 LuCI/uhttpd HTTP 监听端口改为 `8080`
- 检查 Python 语法
- 启用并启动 WiFiPortal 服务
- 设置默认后台密码 `admin123456`
- 运行部署后自检，检查服务、80/8080 端口、认证页和后台页，并保存结果到 `/tmp/wifiportal-install-check.log`

## 快速更新

只更新主程序：

```sh
wget -qO /usr/lib/wifiportal/server.py https://raw.githubusercontent.com/indrachen-sl/local-wifiportal-openwrt/main/wifiportal/server.py
/etc/init.d/wifiportal restart
```

只更新启动器：

```sh
wget -qO /usr/bin/wifiportal_launcher.py https://raw.githubusercontent.com/indrachen-sl/local-wifiportal-openwrt/main/wifiportal.py
/etc/init.d/wifiportal restart
```

重新完整部署：

```sh
wget -qO- https://raw.githubusercontent.com/indrachen-sl/local-wifiportal-openwrt/main/install.sh | sh
```

## 主要功能

### 1. 用户认证 Portal

- 未认证设备访问 HTTP 时会被 nftables 重定向到认证页面。
- 用户在 `http://192.168.10.1/` 输入兑换码即可认证上网。
- 支持通过 URL 预填兑换码，例如：`http://192.168.10.1/?code=VIP-ABCDEF`。
- 用户可打开 `/check` 查看在线状态、剩余时间、绑定兑换码、套餐速度等。

### 2. 兑换码管理

后台入口：`/admin/vouchers`

- 新增单个兑换码
- 批量生成兑换码
- 设置兑换码批次名
- 按批次筛选兑换码
- 批次改名或清空批次名
- 设置有效时长，支持永久码
- 设置最大绑定设备数
- 设置下载/上传限速
- 启用、禁用、删除兑换码
- 延长时间、重置使用状态
- 查看兑换码绑定设备和使用日志
- 导出未使用兑换码 CSV，包含批次名
- 打印当前筛选兑换码、当前批次或勾选的兑换码

### 3. 设备管理

后台入口：`/admin/devices`

- 查看在线设备和历史设备
- 按在线/离线状态筛选
- 搜索 MAC、IP、主机名、兑换码
- 踢下线设备
- 解绑设备和兑换码
- 加入黑名单
- 查看设备当前限速、登录时间、到期时间

### 4. 白名单和黑名单

后台入口：

- 白名单：`/admin/whitelist`
- 黑名单：`/admin/blacklist`

白名单设备可直接放行。黑名单设备会被禁止或限制访问。后台支持手动输入 MAC，也支持从设备记录中选择。

### 5. 防火墙拦截

后台入口：`/admin/firewall`

- 使用 nftables 管理认证放行列表
- 未认证设备 HTTP 流量重定向到 Portal
- 支持恢复已认证会话
- 支持查看防火墙状态
- 服务停止时会清理 WiFiPortal 相关 nftables 表

### 6. QoS 限速

后台入口：`/admin/qos`

- 使用 Linux `tc` 对设备做下载/上传限速
- 按兑换码套餐应用速率
- 支持恢复在线设备限速规则
- 支持清理 QoS 规则
- 设备或系统不支持时可降级，不影响基础认证

### 7. 页面设置

后台入口：`/admin/settings`

可配置用户认证页显示内容，包括标题、公告、套餐说明、联系信息、页脚等。

### 8. 安全设置

后台入口：`/admin/security`

- 后台登录失败次数限制
- 登录失败锁定
- 清空锁定记录
- 登录审计日志
- 修改后台密码：`/admin/password`
- 后台 POST 操作 CSRF 防护，避免登录状态下被外部页面诱导执行管理操作
- 后台会话密钥会持久保存，服务重启不会无故退出；修改密码时会自动轮换会话密钥并要求重新登录

### 9. 日志、健康检查和维护

后台入口：

- 日志：`/admin/logs`
- 健康检查：`/admin/health`
- 系统诊断：`/admin/diagnostics`
- 纯文本诊断：`/admin/diagnostics.txt`
- 系统维护：`/admin/maintenance`
- 更新与安装备份：`/admin/install-backups`
- 帮助：`/admin/help`

可查看认证、后台登录、设备操作、防火墙、QoS、备份等日志。健康检查会检查服务进程、80 端口、LuCI 8080、数据文件、防火墙和 QoS 状态。系统诊断页面是只读排查页，会汇总服务状态、端口监听、本机访问、Python 语法、nftables、磁盘、内存、最近系统日志和最近安装备份，并提供一键复制按钮，方便后台或认证页无法访问时复制给维护人员。`/admin/diagnostics.txt` 会输出同样内容的纯文本版本。诊断输出会对密码哈希、会话密钥和 CSRF token 做脱敏处理。

### 10. 备份和恢复

后台入口：`/admin/backup`

- 创建管理备份
- 下载备份
- 恢复备份
- 清理旧备份
- 自动备份兑换码和设置数据
- 数据库写入使用临时文件替换，降低断电损坏风险

更新与安装备份入口：`/admin/install-backups`

- 查看 install.sh 覆盖程序前自动创建的代码备份
- 下载安装备份包
- 复制 SSH 回滚命令 `wifiportal-rollback <备份包路径>`
- 从 GitHub main 分支触发一键更新
- 查看最近一键更新日志 `/tmp/wifiportal-admin-update.log`

## 配置文件

主配置文件：`/etc/wifiportal/config`

常用配置项：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `LAN_IP` | `192.168.10.1` | 路由器 LAN 地址，也是 Portal 访问地址 |
| `LAN_IF` | `br-lan` | 内网桥接接口 |
| `WAN_IF` | `wan` | 外网出口接口 |
| `PORTAL_PORT` | `80` | WiFiPortal 监听端口 |
| `DB_FILE` | `/etc/wifiportal/vouchers.json` | 兑换码和设备数据库 |
| `SETTINGS_FILE` | `/etc/wifiportal/settings.json` | 页面和后台设置 |
| `LOG_FILE` | `/var/log/wifiportal/wifiportal.log` | 日志文件 |
| `ENABLE_QOS` | `1` | 是否启用 QoS 限速 |
| `MAX_FAILED_ATTEMPTS` | `5` | 后台登录最大失败次数 |
| `LOCK_SECONDS` | `300` | 后台登录失败锁定秒数 |

修改配置后重启服务：

```sh
/etc/init.d/wifiportal restart
```

## 服务管理命令

```sh
/etc/init.d/wifiportal start
/etc/init.d/wifiportal stop
/etc/init.d/wifiportal restart
/etc/init.d/wifiportal status
/etc/init.d/wifiportal enable
/etc/init.d/wifiportal disable
```

查看监听端口：

```sh
netstat -lntp | grep -E ':80 |:8080 '
```

正常情况应看到：

```text
0.0.0.0:80    LISTEN  python3
0.0.0.0:8080  LISTEN  uhttpd
:::8080       LISTEN  uhttpd
```

## 排查命令

一键导出诊断信息：

```sh
wifiportal-diagnose
```

查看服务状态：

```sh
/etc/init.d/wifiportal status
```

查看 WiFiPortal 相关系统日志：

```sh
logread -e wifiportal | tail -120
```

检查 Python 语法：

```sh
python3 -m py_compile /usr/bin/wifiportal_launcher.py /usr/lib/wifiportal/server.py /usr/lib/wifiportal/config.py /usr/lib/wifiportal/db.py /usr/lib/wifiportal/firewall.py /usr/lib/wifiportal/templates.py /usr/lib/wifiportal/utils.py
```

检查本机页面是否响应。OpenWrt 精简版 `wget` 不支持 `-S`，请使用：

```sh
wget -O- http://127.0.0.1/ 2>&1 | head -40
wget -O- http://127.0.0.1/admin 2>&1 | head -60
wget -O- http://192.168.10.1/ 2>&1 | head -40
wget -O- http://192.168.10.1/admin 2>&1 | head -60
```

如果服务显示 running，但浏览器打不开，优先贴这些输出：

```sh
wifiportal-diagnose
cat /tmp/wifiportal-install-check.log
/etc/init.d/wifiportal status
logread -e wifiportal | tail -120
netstat -lntp | grep -E ':80 |:8080 '
cat /etc/wifiportal/config
uci show uhttpd
```

安装脚本修改 LuCI 端口前会备份原始配置，备份文件路径类似：

```sh
/etc/config/uhttpd.wifiportal-backup-20260720-153000
```

每次部署覆盖程序前也会创建代码备份，路径类似：

```sh
/etc/wifiportal/install-backups/wifiportal-code-backup-20260720-153000.tar.gz
```

如果更新后需要恢复上一版程序，可以先列出备份，再指定一个备份包回滚：

```sh
ls -1 /etc/wifiportal/install-backups/wifiportal-code-backup-*.tar.gz
wifiportal-rollback /etc/wifiportal/install-backups/wifiportal-code-backup-20260720-153000.tar.gz
wifiportal-diagnose
```

## 项目结构

```text
.
├── wifiportal.py              # 启动器，OpenWrt 服务从这里导入 wifiportal.server:main
├── wifiportal/
│   ├── __init__.py            # Python 包入口
│   ├── config.py              # 配置加载和路径常量
│   ├── db.py                  # JSON 数据读写、备份、自愈
│   ├── firewall.py            # nftables 和 QoS/tc 操作
│   ├── server.py              # HTTP 路由、后台功能、认证逻辑
│   ├── templates.py           # 页面模板
│   └── utils.py               # 时间、MAC、HTML 转义等工具
├── init.d/
│   └── wifiportal             # OpenWrt procd 服务脚本
├── install.sh                 # 一键部署脚本
├── README.md                  # 项目说明
└── .gitignore                 # 忽略本地生成和敏感文件
```

## 安全提示

默认密码 `admin123456` 方便首次部署。正式使用时建议登录后台后到 `/admin/password` 修改为更强密码；如果仍使用默认密码，后台会显示安全提醒。


