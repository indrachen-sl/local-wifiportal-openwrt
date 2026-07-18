# local-wifiportal-openwrt 2.0

基于 OpenWrt 的高性能、模块化本地 WiFi 兑换码认证 Portal 系统（Local Captive Portal）。

---

## 🌟 核心功能 (Key Features)

### 1. 认证拦截与 Portal (Captive Portal)
*   **无感知重定向**：采用高效的 `nftables` 规则，自动拦截未认证客户端的 HTTP 请求，并流畅重定向至 Portal 登录页面。
*   **自适应双模板**：内置 **Polished 现代极简版** 和 **Easy 自适应响应式版** 登录界面，完美适配手机、平板及 PC。
*   **状态自助查询**：客户端提供快捷查询页面（`/check`），用户可实时查看自己的在线状态、剩余可用时长及已连接设备数。

### 2. 兑换码管理系统 (Voucher System)
*   **多元限制参数**：支持为兑换码设置可用分钟数（支持永久有效）、最大绑定设备数、下载/上传速率限制以及备注信息。
*   **批量自定义前缀生成**：管理员可以在后台一次性批量生成最多 1000 个兑换码，并支持指定分类前缀（如 `VIP-`、`DAY-`），便于卡券分级管理。
*   **自动填充与扫码登录**：支持通过 URL 参数自动填入（如 `http://192.168.10.1/?code=VIP-ABCDEF`），结合打印卡片实现“扫码免输代码，一键连接”。

### 3. 排版网格卡片打印 (Printable Grid Cards)
*   **打印专属排版**：后台集成专用打印卡片生成页面，采用网格虚线布局，专为 A4 纸张排版裁切优化，打印时自动隐藏后台控制栏。
*   **离线扫码二维码**：每张卡片均内嵌该卡券专属的一键登录二维码。手机摄像头扫描即可自动跳转并预填券码。

### 4. QoS 智能流量限速 (Traffic Control)
*   **设备级上下行限速**：使用 Linux 内核 `tc` (Traffic Control) 和 HTB (Hierarchical Token Bucket) 队列实现精细化的上下行速度限制。
*   **模块自检与优雅降级**：初始化时自动检测路由器是否支持 `tc` 命令及相关内核模块。若不兼容，系统将优雅退避降级，保证核心认证功能不受影响。

### 5. 性能与安全性加固 (Performance & Security)
*   **nftables 内存状态缓存**：在内存中缓存防火墙表的初始化状态，消除频繁执行 `nft` 子进程带来的 CPU 性能损耗，极大提升低端路由器的并发吞吐。
*   **Flash 闪存擦写保护**：将后台暴力破解判定的锁定计数文件从 `/etc` 转移至系统运行内存目录 `/tmp`，避免高频日志写入导致物理 Flash 闪存芯片磨损老化。
*   **管理后台安全审计**：支持管理员登录失败爆破防护锁定、后台操作安全审计日志，保护系统管理安全。

### 6. 数据灾备与自愈机制 (Database Backup & Self-Healing)
*   **防断电原子写入**：所有数据读写（`vouchers.json`）均采用临时文件替换的原子保存技术，防止路由器突发断电导致数据库损坏。
*   **自动备份与旧备份清理**：系统在运行中会自动保存历史数据库备份，并定期清理 7 天前的历史备份。
*   **损坏数据库自动修复**：若主数据库文件受损，系统启动时会自动扫描备份文件并恢复至最近的健康状态。

---

## 📦 项目文件结构 (Directory Structure)

```text
├── wifiportal.py             # 极简服务启动器（兼容 /etc/init.d 服务脚本调用）
├── wifiportal/               # 核心业务 Python 包
│   ├── __init__.py           # 包初始化入口
│   ├── config.py             # 全局常量、路径及环境变量加载
│   ├── utils.py              # 时间格式化、MAC正则化、HTML转义等工具库
│   ├── db.py                 # 原子读写、损坏自愈、备份机制
│   ├── firewall.py           # nftables 拦截、QoS 限速命令封装
│   ├── templates.py          # 后台、客户端及打印卡片 HTML 模板
│   └── server.py             # 核心路由分发、API 接口与业务 Handler
├── init.d/
│   └── wifiportal            # OpenWrt procd 开机自启服务管理脚本
├── install.sh                # 一键部署与环境配置 Shell 脚本
├── README.md                 # 说明文档
└── .gitignore                # 敏感数据库与本地配置排除列表
```

---

## 📥 一键部署命令 (One-Click Deployment)

SSH 登录您的 OpenWrt 路由器，然后运行以下命令即可完成环境配置、依赖安装及自启动部署：

```bash
wget -qO- https://raw.githubusercontent.com/indrachen-sl/local-wifiportal-openwrt/main/install.sh | sh
```

---

## ⚙️ 配置文件说明 (`/etc/wifiportal/config`)

您可以通过修改路由器上的 `/etc/wifiportal/config` 文件调整核心参数：
*   `LAN_IP`：路由器 LAN 口 IP 地址（Portal 重定向的目标地址，默认为 `192.168.10.1`）。
*   `LAN_IF`：内网桥接接口（默认为 `br-lan`）。
*   `WAN_IF`：外网出口接口（用于设定转发策略，默认为 `wan`）。
*   `PORTAL_PORT`：Portal 服务监听端口（默认为 `80`）。
*   `ENABLE_QOS`：是否启用 QoS 限速（`1` 为启用，`0` 为停用）。

---

## 🔑 管理员账号与密码重置

*   **后台地址**：`http://您的路由器LAN_IP/admin`（例如：`http://192.168.10.1/admin`）
*   **用户名**：`admin`
*   **密码设置/重置**：一键部署脚本结束时会引导您设置密码。如需重置，可通过 SSH 登录路由器，运行以下命令：
    ```bash
    python3 -c "import sys; sys.path.append('/usr/lib'); from wifiportal.server import update_admin_password; ok, msg = update_admin_password('新密码'); print('重置成功' if ok else msg)"
    ```

---

## ⚠️ 安全与隐私声明 (Disclaimer)

为了保护隐私，请勿将生成并在运行中的生产文件（如包含真实券码和客户端历史的 `vouchers.json`、系统密钥 `settings.json` 等）提交至公共代码仓库。本地的 `.gitignore` 已配置自动忽略此类敏感信息。
