from wifiportal.utils import esc

def admin_page(title, body, logged_in=True):
    nav = ""
    if logged_in:
        nav = """
<div class="nav">
<a href="/admin">总览</a>
<a href="/admin/vouchers">兑换码</a>
<a href="/admin/expiring">到期</a>
<a href="/admin/devices">在线设备</a>
<a href="/admin/settings">页面设置</a>
<a href="/admin/whitelist">白名单</a>
<a href="/admin/blacklist">黑名单</a>
<a href="/admin/security">安全</a>
<a href="/admin/db-check">数据检查</a>
<a href="/admin/db-fix">数据修复</a>
<a href="/admin/maintenance">维护</a>
<a href="/admin/help">帮助</a>
<a href="/admin/health">健康检查</a>
<a href="/admin/logs">日志</a>
<a href="/admin/backup">备份恢复</a>
<a href="/admin/firewall">防火墙</a>
<a href="/admin/qos">限速</a>
<a href="/admin/password">修改密码</a>
<a href="/admin/logout">退出</a>
</div>
"""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>
body{{margin:0;font-family:Arial,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f1f5f9;color:#0f172a}}
.wrap{{max-width:1180px;margin:0 auto;padding:22px 14px}}
.card{{background:white;border:1px solid #cbd5e1;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 6px 20px #0001}}
.nav{{background:#0f172a;padding:12px 14px;border-radius:14px;margin-bottom:14px}}
.nav a{{color:white;text-decoration:none;margin-right:16px;display:inline-block;padding:6px 0}}
input,textarea,select,button{{font-size:16px;border-radius:9px;border:1px solid #94a3b8;padding:9px;margin:5px 0}}
textarea{{width:100%;box-sizing:border-box;min-height:120px}}
button,.btn{{background:#2563eb;color:white;border:0;cursor:pointer;text-decoration:none;display:inline-block}}
.danger{{background:#dc2626}}.ok{{color:#16a34a}}.bad{{color:#dc2626}}.muted{{color:#64748b}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
.stat{{background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:14px}}
.stat b{{display:block;font-size:24px;margin-top:8px}}
table{{width:100%;border-collapse:collapse;background:white}}td,th{{border-bottom:1px solid #e2e8f0;text-align:left;padding:9px;vertical-align:top}}
code{{background:#e2e8f0;padding:2px 5px;border-radius:5px}}

/* WIFI_PORTAL_ADMIN_UI_OVERLAY_V3 */
:root {{
  --ui-bg:#eef2f7;
  --ui-text:#0f172a;
  --ui-muted:#64748b;
  --ui-border:#dbe3ef;
  --ui-blue:#2563eb;
  --ui-blue2:#1d4ed8;
  --ui-red:#dc2626;
  --ui-green:#16a34a;
  --ui-shadow:0 12px 34px rgba(15,23,42,.08);
  --ui-radius:18px;
}}

body {{
  background:linear-gradient(135deg,#f8fafc 0%,var(--ui-bg) 100%) !important;
  color:var(--ui-text) !important;
}}

.wrap {{
  max-width:1320px !important;
  padding:22px 14px 50px !important;
}}

.nav {{
  background:linear-gradient(135deg,#0f172a,#111827) !important;
  border-radius:0 0 22px 22px !important;
  padding:16px !important;
  margin:-22px -14px 18px !important;
  box-shadow:0 14px 38px rgba(15,23,42,.22) !important;
}}

.nav:before {{
  content:"WiFi Portal  ·  本地兑换码认证系统";
  display:block;
  color:#fff;
  font-size:19px;
  font-weight:900;
  margin:0 0 12px 2px;
}}

.nav a {{
  color:#e5e7eb !important;
  background:rgba(255,255,255,.08) !important;
  text-decoration:none !important;
  padding:9px 12px !important;
  border-radius:12px !important;
  margin:4px !important;
  display:inline-block !important;
  font-size:14px !important;
}}

.nav a:hover {{
  background:rgba(255,255,255,.16) !important;
}}

.card {{
  background:rgba(255,255,255,.94) !important;
  border:1px solid var(--ui-border) !important;
  border-radius:var(--ui-radius) !important;
  padding:20px !important;
  margin:16px 0 !important;
  box-shadow:var(--ui-shadow) !important;
}}

.card h1 {{
  margin:0 0 14px !important;
  font-size:28px !important;
  letter-spacing:-.4px !important;
}}

.card h2 {{
  margin:0 0 14px !important;
  font-size:20px !important;
}}

.card p {{
  line-height:1.65 !important;
}}

.grid {{
  display:grid !important;
  grid-template-columns:repeat(auto-fit,minmax(210px,1fr)) !important;
  gap:14px !important;
}}

.stat {{
  position:relative !important;
  overflow:hidden !important;
  background:linear-gradient(135deg,#ffffff,#f8fafc) !important;
  border:1px solid var(--ui-border) !important;
  border-radius:16px !important;
  padding:16px !important;
  min-height:96px !important;
}}

.stat b {{
  display:block !important;
  font-size:24px !important;
  margin-top:10px !important;
  word-break:break-word !important;
}}

input, textarea, select {{
  font-size:15px !important;
  border-radius:12px !important;
  border:1px solid #cbd5e1 !important;
  padding:10px 12px !important;
  margin:6px 0 !important;
  background:white !important;
  color:var(--ui-text) !important;
  outline:none !important;
}}

input:focus, textarea:focus, select:focus {{
  border-color:var(--ui-blue) !important;
  box-shadow:0 0 0 4px rgba(37,99,235,.12) !important;
}}

textarea {{
  width:100% !important;
  min-height:120px !important;
  resize:vertical !important;
}}

button, .btn {{
  font-size:15px !important;
  border-radius:12px !important;
  border:0 !important;
  padding:10px 14px !important;
  margin:5px 3px 5px 0 !important;
  background:linear-gradient(135deg,var(--ui-blue),var(--ui-blue2)) !important;
  color:white !important;
  cursor:pointer !important;
  text-decoration:none !important;
  display:inline-block !important;
  font-weight:700 !important;
  box-shadow:0 8px 18px rgba(37,99,235,.22) !important;
}}

.danger {{
  background:linear-gradient(135deg,var(--ui-red),#b91c1c) !important;
}}

.ok {{
  color:var(--ui-green) !important;
  font-weight:800 !important;
}}

.bad {{
  color:var(--ui-red) !important;
  font-weight:800 !important;
}}

.muted {{
  color:var(--ui-muted) !important;
}}

table {{
  width:100% !important;
  border-collapse:separate !important;
  border-spacing:0 !important;
  overflow:hidden !important;
  background:white !important;
  border:1px solid var(--ui-border) !important;
  border-radius:15px !important;
}}

th {{
  background:#f8fafc !important;
  color:#334155 !important;
  font-size:13px !important;
  white-space:nowrap !important;
}}

td, th {{
  border-bottom:1px solid #e5eaf2 !important;
  text-align:left !important;
  padding:11px 10px !important;
  vertical-align:top !important;
}}

tr:hover td {{
  background:#f8fafc !important;
}}

code {{
  background:#eef2ff !important;
  color:#1e3a8a !important;
  padding:3px 7px !important;
  border-radius:8px !important;
  font-family:monospace !important;
  font-size:13px !important;
  word-break:break-all !important;
}}

pre {{
  border-radius:14px !important;
}}

form {{
  margin:0 !important;
}}

@media(max-width:760px) {{
  .wrap {{
    padding:14px 10px 36px !important;
  }}

  .nav {{
    margin:-14px -10px 14px !important;
    display:block !important;
  }}

  .nav a {{
    width:calc(50% - 8px) !important;
    text-align:center !important;
  }}

  .grid {{
    grid-template-columns:1fr !important;
  }}

  table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
  }}

  button, .btn {{
    width:100% !important;
    text-align:center !important;
  }}
}}


/* LOGIN_CENTER_FIX_V2 */
.card form[action="/admin/login"] {{
  display:block !important;
}}

.card:has(form[action="/admin/login"]) {{
  max-width:420px !important;
  margin:12vh auto 0 !important;
  padding:24px !important;
}}

.card:has(form[action="/admin/login"]) h1 {{
  text-align:center !important;
}}

.card:has(form[action="/admin/login"]) input,
.card:has(form[action="/admin/login"]) button {{
  width:100% !important;
}}

@media(max-width:560px) {{
  .card:has(form[action="/admin/login"]) {{
    margin:8vh 12px 0 !important;
  }}
}}


/* VOUCHER_LIST_COMPACT_V1 */
.voucher-table-compact {{
  font-size:13px !important;
}}

.voucher-table-compact th,
.voucher-table-compact td {{
  padding:7px 8px !important;
  vertical-align:top !important;
  line-height:1.32 !important;
}}

.voucher-code-cell {{
  font-size:14px !important;
  font-weight:800 !important;
  line-height:1.2 !important;
  margin-bottom:3px !important;
}}

.voucher-code-cell code {{
  font-size:14px !important;
  padding:2px 5px !important;
}}

.voucher-status-badge {{
  display:inline-block !important;
  padding:2px 7px !important;
  border-radius:999px !important;
  border:1px solid !important;
  font-size:12px !important;
  font-weight:800 !important;
  line-height:1.25 !important;
  white-space:nowrap !important;
}}

.voucher-table-compact .muted {{
  font-size:12px !important;
}}

.voucher-table-compact button,
.voucher-table-compact .btn,
.voucher-small-btn {{
  font-size:12px !important;
  padding:4px 7px !important;
  margin:2px !important;
  border-radius:7px !important;
  line-height:1.2 !important;
}}

.voucher-actions {{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:3px !important;
}}

.voucher-extend-form {{
  margin-top:4px !important;
  white-space:nowrap !important;
}}

.voucher-extend-form input {{
  width:64px !important;
  font-size:12px !important;
  padding:4px 5px !important;
  margin:2px !important;
}}

.voucher-extend-form button {{
  font-size:12px !important;
  padding:4px 7px !important;
}}

@media(max-width:760px) {{
  .voucher-table-compact {{
    font-size:12px !important;
  }}

  .voucher-table-compact th,
  .voucher-table-compact td {{
    padding:6px 6px !important;
  }}

  .voucher-code-cell,
  .voucher-code-cell code {{
    font-size:13px !important;
  }}
}}


/* VOUCHER_CARD_UI_V2 */
.voucher-search-row {{
  display:grid !important;
  grid-template-columns:minmax(240px,1fr) auto auto !important;
  gap:8px !important;
  align-items:center !important;
}}

.voucher-filter-row {{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:7px !important;
  margin-top:10px !important;
}}

.voucher-filter-btn {{
  padding:7px 11px !important;
  border-radius:999px !important;
  font-size:13px !important;
}}

.voucher-filter-active {{
  background:#0f766e !important;
}}

.voucher-tool-row {{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:8px !important;
  align-items:center !important;
  margin-top:12px !important;
}}

.voucher-tool-row form {{
  margin:0 !important;
}}

.voucher-card-list {{
  display:grid !important;
  grid-template-columns:1fr !important;
  gap:10px !important;
}}

.voucher-card-item {{
  border:1px solid #dbe3ef !important;
  border-radius:14px !important;
  background:#ffffff !important;
  padding:12px !important;
  box-shadow:0 6px 16px rgba(15,23,42,.05) !important;
}}

.voucher-card-main {{
  display:flex !important;
  align-items:flex-start !important;
  justify-content:space-between !important;
  gap:12px !important;
  border-bottom:1px solid #e5eaf1 !important;
  padding-bottom:9px !important;
}}

.voucher-code-title code {{
  font-size:18px !important;
  font-weight:900 !important;
  letter-spacing:.5px !important;
  padding:3px 7px !important;
}}

.voucher-card-sub {{
  margin-top:6px !important;
  display:flex !important;
  flex-wrap:wrap !important;
  gap:7px !important;
  align-items:center !important;
}}

.voucher-badge {{
  display:inline-block !important;
  padding:3px 8px !important;
  border-radius:999px !important;
  font-size:12px !important;
  font-weight:900 !important;
  line-height:1.25 !important;
}}

.voucher-badge-danger {{
  background:#fee2e2 !important;
  color:#991b1b !important;
  border:1px solid #fecaca !important;
}}

.voucher-badge-blue {{
  background:#eff6ff !important;
  color:#1d4ed8 !important;
  border:1px solid #bfdbfe !important;
}}

.voucher-badge-green {{
  background:#dcfce7 !important;
  color:#166534 !important;
  border:1px solid #bbf7d0 !important;
}}

.voucher-info-grid {{
  display:grid !important;
  grid-template-columns:repeat(auto-fit,minmax(135px,1fr)) !important;
  gap:8px !important;
  margin-top:10px !important;
}}

.voucher-info-grid div {{
  background:#f8fafc !important;
  border:1px solid #e2e8f0 !important;
  border-radius:10px !important;
  padding:7px 8px !important;
}}

.voucher-info-grid span {{
  display:block !important;
  color:#64748b !important;
  font-size:12px !important;
  margin-bottom:3px !important;
}}

.voucher-info-grid b {{
  font-size:13px !important;
  color:#0f172a !important;
}}

.voucher-note-row {{
  margin-top:9px !important;
  font-size:13px !important;
  color:#334155 !important;
  background:#f8fafc !important;
  border-radius:10px !important;
  padding:7px 8px !important;
}}

.voucher-note-row span {{
  color:#64748b !important;
}}

.voucher-actions-row {{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:7px !important;
  align-items:center !important;
  margin-top:10px !important;
}}

.voucher-actions-row form {{
  margin:0 !important;
}}

.voucher-action-btn {{
  font-size:13px !important;
  padding:6px 10px !important;
  border-radius:9px !important;
  margin:0 !important;
}}

.voucher-action-good {{
  background:#0f766e !important;
}}

.voucher-copy-area {{
  flex:0 0 auto !important;
}}

.voucher-extend-inline {{
  display:flex !important;
  gap:6px !important;
  align-items:center !important;
}}

.voucher-extend-inline select {{
  width:auto !important;
  min-width:120px !important;
  font-size:13px !important;
  padding:6px 8px !important;
  margin:0 !important;
  border-radius:9px !important;
}}

.voucher-danger-details {{
  display:inline-block !important;
  margin-left:auto !important;
}}

.voucher-danger-details summary {{
  cursor:pointer !important;
  color:#64748b !important;
  font-size:13px !important;
  padding:6px 8px !important;
}}

.voucher-danger-details form {{
  margin-top:6px !important;
}}

.voucher-summary {{
  cursor:pointer !important;
  font-size:18px !important;
  font-weight:900 !important;
  padding:4px 0 !important;
}}

.voucher-empty {{
  padding:22px !important;
  text-align:center !important;
  color:#64748b !important;
  background:#f8fafc !important;
  border-radius:12px !important;
  border:1px dashed #cbd5e1 !important;
}}

@media(max-width:760px) {{
  .voucher-search-row {{
    grid-template-columns:1fr !important;
  }}

  .voucher-card-main {{
    flex-direction:column !important;
  }}

  .voucher-copy-area {{
    width:100% !important;
  }}

  .voucher-copy-area button {{
    width:100% !important;
  }}

  .voucher-info-grid {{
    grid-template-columns:1fr 1fr !important;
  }}

  .voucher-actions-row {{
    flex-direction:column !important;
    align-items:stretch !important;
  }}

  .voucher-actions-row form,
  .voucher-actions-row button,
  .voucher-extend-inline,
  .voucher-extend-inline select {{
    width:100% !important;
  }}

  .voucher-danger-details {{
    margin-left:0 !important;
    width:100% !important;
  }}
}}


/* VOUCHER_DENSE_TABLE_V3 */
.dense-stat-row {{
  display:grid !important;
  grid-template-columns:repeat(auto-fit,minmax(100px,1fr)) !important;
  gap:8px !important;
}}

.dense-stat {{
  background:#f8fafc !important;
  border:1px solid #dbe3ef !important;
  border-radius:10px !important;
  padding:8px 9px !important;
  text-decoration:none !important;
  color:#334155 !important;
  font-size:13px !important;
}}

.dense-stat b {{
  display:block !important;
  font-size:19px !important;
  color:#0f172a !important;
  margin-top:3px !important;
}}

.dense-search-form {{
  display:grid !important;
  grid-template-columns:minmax(240px,1fr) auto auto !important;
  gap:7px !important;
  align-items:center !important;
}}

.dense-filter-row,
.dense-tool-row {{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:6px !important;
  align-items:center !important;
  margin-top:8px !important;
}}

.dense-tool-row form {{
  margin:0 !important;
}}

.dense-filter-btn {{
  padding:6px 10px !important;
  border-radius:999px !important;
  font-size:13px !important;
}}

.dense-filter-active {{
  background:#0f766e !important;
}}

.voucher-dense-table {{
  font-size:13px !important;
  table-layout:auto !important;
}}

.voucher-dense-table th,
.voucher-dense-table td {{
  padding:6px 7px !important;
  vertical-align:middle !important;
  line-height:1.25 !important;
}}

.voucher-dense-table th {{
  white-space:nowrap !important;
  font-size:12px !important;
  color:#475569 !important;
  background:#f8fafc !important;
}}

.dense-code-col {{
  white-space:nowrap !important;
}}

.dense-code-col code {{
  font-size:14px !important;
  font-weight:900 !important;
  padding:2px 5px !important;
}}

.dense-status-col {{
  min-width:86px !important;
}}

.dense-badge {{
  display:inline-block !important;
  padding:2px 7px !important;
  border-radius:999px !important;
  font-size:12px !important;
  font-weight:900 !important;
  white-space:nowrap !important;
}}

.dense-badge-danger {{
  background:#fee2e2 !important;
  color:#991b1b !important;
  border:1px solid #fecaca !important;
}}

.dense-badge-blue {{
  background:#eff6ff !important;
  color:#1d4ed8 !important;
  border:1px solid #bfdbfe !important;
}}

.dense-badge-green {{
  background:#dcfce7 !important;
  color:#166534 !important;
  border:1px solid #bbf7d0 !important;
}}

.dense-sub {{
  color:#64748b !important;
  font-size:11px !important;
  margin-top:2px !important;
  white-space:nowrap !important;
}}

.dense-note-col {{
  max-width:140px !important;
  color:#334155 !important;
  font-size:12px !important;
}}

.dense-actions-col {{
  min-width:230px !important;
}}

.dense-actions-main {{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:4px !important;
  align-items:center !important;
}}

.dense-actions-main form {{
  margin:0 !important;
}}

.dense-mini-btn {{
  font-size:12px !important;
  padding:4px 7px !important;
  border-radius:7px !important;
  margin:0 !important;
  line-height:1.15 !important;
}}

.dense-good {{
  background:#0f766e !important;
}}

.dense-mini-select {{
  font-size:12px !important;
  padding:4px 6px !important;
  border-radius:7px !important;
  margin:0 !important;
  width:auto !important;
}}

.dense-more {{
  display:inline-block !important;
  position:relative !important;
}}

.dense-more summary {{
  cursor:pointer !important;
  font-size:12px !important;
  color:#64748b !important;
  padding:4px 6px !important;
}}

.dense-more form {{
  display:inline-block !important;
  margin-left:4px !important;
}}

.dense-summary {{
  cursor:pointer !important;
  font-size:17px !important;
  font-weight:900 !important;
}}

@media(max-width:760px) {{
  .dense-search-form {{
    grid-template-columns:1fr !important;
  }}

  .voucher-dense-table {{
    font-size:12px !important;
  }}

  .voucher-dense-table th,
  .voucher-dense-table td {{
    padding:5px !important;
  }}

  .dense-code-col code {{
    font-size:13px !important;
  }}

  .dense-actions-col {{
    min-width:180px !important;
  }}

  .dense-mini-btn,
  .dense-mini-select {{
    font-size:11px !important;
    padding:3px 5px !important;
  }}

  .dense-note-col {{
    max-width:90px !important;
  }}
}}


/* ADMIN_MOBILE_UI_V1 */
@media(max-width:760px) {{
  html, body {{
    width:100% !important;
    max-width:100% !important;
    overflow-x:hidden !important;
    -webkit-text-size-adjust:100% !important;
  }}

  body {{
    font-size:14px !important;
    background:#eef2f7 !important;
  }}

  .wrap {{
    width:100% !important;
    max-width:100% !important;
    box-sizing:border-box !important;
    padding:8px !important;
    margin:0 !important;
  }}

  .nav {{
    position:sticky !important;
    top:6px !important;
    z-index:50 !important;
    display:flex !important;
    flex-wrap:nowrap !important;
    gap:8px !important;
    overflow-x:auto !important;
    overflow-y:hidden !important;
    -webkit-overflow-scrolling:touch !important;
    padding:9px 10px !important;
    margin:0 0 9px 0 !important;
    border-radius:13px !important;
    white-space:nowrap !important;
  }}

  .nav::-webkit-scrollbar {{
    display:none !important;
  }}

  .nav a {{
    flex:0 0 auto !important;
    margin:0 !important;
    padding:6px 9px !important;
    border-radius:999px !important;
    background:rgba(255,255,255,.10) !important;
    font-size:13px !important;
    line-height:1.2 !important;
  }}

  .card {{
    margin:8px 0 !important;
    padding:11px !important;
    border-radius:13px !important;
    box-shadow:0 4px 14px rgba(15,23,42,.08) !important;
  }}

  .card h1 {{
    font-size:21px !important;
    line-height:1.2 !important;
    margin-bottom:8px !important;
  }}

  .card h2 {{
    font-size:17px !important;
    line-height:1.25 !important;
    margin-bottom:8px !important;
  }}

  .card p {{
    margin:6px 0 !important;
    line-height:1.45 !important;
  }}

  .muted {{
    font-size:12px !important;
    line-height:1.35 !important;
  }}

  .grid {{
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
    gap:7px !important;
  }}

  .stat {{
    padding:9px !important;
    border-radius:11px !important;
    min-width:0 !important;
  }}

  .stat b {{
    font-size:18px !important;
    margin-top:4px !important;
    word-break:break-word !important;
  }}

  input, textarea, select, button, .btn {{
    font-size:16px !important;
    max-width:100% !important;
    box-sizing:border-box !important;
  }}

  input, textarea, select {{
    width:100% !important;
    padding:8px 9px !important;
    margin:4px 0 !important;
    border-radius:10px !important;
  }}

  button, .btn {{
    padding:8px 10px !important;
    margin:3px 2px !important;
    border-radius:10px !important;
    line-height:1.2 !important;
  }}

  form {{
    max-width:100% !important;
  }}

  table {{
    display:block !important;
    width:100% !important;
    max-width:100% !important;
    overflow-x:auto !important;
    -webkit-overflow-scrolling:touch !important;
    white-space:nowrap !important;
    border-radius:10px !important;
  }}

  tbody, thead, tr {{
    width:max-content !important;
  }}

  th, td {{
    padding:6px 7px !important;
    font-size:12px !important;
    line-height:1.25 !important;
  }}

  code {{
    font-size:12px !important;
    word-break:break-all !important;
  }}

  details.card {{
    padding:10px 11px !important;
  }}

  details summary,
  .dense-summary,
  .voucher-summary {{
    display:block !important;
    padding:8px 2px !important;
    font-size:16px !important;
    line-height:1.25 !important;
    cursor:pointer !important;
  }}

  .dense-stat-row {{
    grid-template-columns:repeat(3,minmax(0,1fr)) !important;
    gap:6px !important;
  }}

  .dense-stat {{
    padding:7px !important;
    font-size:12px !important;
    border-radius:10px !important;
  }}

  .dense-stat b {{
    font-size:17px !important;
    margin-top:2px !important;
  }}

  .dense-search-form {{
    grid-template-columns:1fr !important;
    gap:5px !important;
  }}

  .dense-filter-row,
  .dense-tool-row {{
    gap:5px !important;
    margin-top:7px !important;
  }}

  .dense-filter-btn {{
    font-size:12px !important;
    padding:6px 8px !important;
  }}

  .voucher-dense-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .voucher-dense-table th,
  .voucher-dense-table td {{
    padding:5px 6px !important;
    font-size:12px !important;
  }}

  .dense-code-col code {{
    font-size:13px !important;
  }}

  .dense-sub {{
    font-size:10px !important;
  }}

  .dense-badge {{
    font-size:11px !important;
    padding:2px 6px !important;
  }}

  .dense-actions-col {{
    min-width:190px !important;
  }}

  .dense-actions-main {{
    gap:3px !important;
  }}

  .dense-mini-btn,
  .dense-mini-select {{
    font-size:11px !important;
    padding:4px 5px !important;
    border-radius:7px !important;
    width:auto !important;
  }}

  .dense-mini-select {{
    min-width:72px !important;
  }}

  .dense-note-col {{
    max-width:110px !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
  }}

  .dense-more summary {{
    font-size:11px !important;
    padding:4px 5px !important;
  }}
}}

@media(max-width:420px) {{
  .wrap {{
    padding:6px !important;
  }}

  .card {{
    padding:9px !important;
    margin:7px 0 !important;
  }}

  .grid {{
    grid-template-columns:1fr 1fr !important;
    gap:6px !important;
  }}

  .dense-stat-row {{
    grid-template-columns:repeat(3,minmax(0,1fr)) !important;
  }}

  .dense-stat {{
    font-size:11px !important;
    padding:6px !important;
  }}

  .dense-stat b {{
    font-size:16px !important;
  }}

  .nav a {{
    font-size:12px !important;
    padding:6px 8px !important;
  }}

  .card h1 {{
    font-size:19px !important;
  }}

  .card h2 {{
    font-size:16px !important;
  }}
}}


/* ADMIN_MOBILE_BOTTOM_NAV_V1 */
.admin-mobile-bottom-nav {{
  display:none;
}}

@media(max-width:760px) {{
  body {{
    padding-bottom:72px !important;
  }}

  .wrap {{
    padding-bottom:82px !important;
  }}

  .admin-mobile-bottom-nav {{
    position:fixed !important;
    left:8px !important;
    right:8px !important;
    bottom:8px !important;
    z-index:9999 !important;
    display:grid !important;
    grid-template-columns:repeat(5,1fr) !important;
    gap:4px !important;
    background:rgba(15,23,42,.94) !important;
    border:1px solid rgba(255,255,255,.12) !important;
    border-radius:18px !important;
    padding:7px 6px !important;
    box-shadow:0 12px 32px rgba(15,23,42,.35) !important;
    backdrop-filter:blur(12px) !important;
    -webkit-backdrop-filter:blur(12px) !important;
  }}

  .admin-mobile-bottom-nav a {{
    display:flex !important;
    flex-direction:column !important;
    align-items:center !important;
    justify-content:center !important;
    gap:2px !important;
    min-width:0 !important;
    padding:5px 2px !important;
    color:#e5e7eb !important;
    text-decoration:none !important;
    border-radius:13px !important;
    line-height:1.05 !important;
  }}

  .admin-mobile-bottom-nav a:active {{
    background:rgba(255,255,255,.14) !important;
  }}

  .admin-mobile-bottom-nav span {{
    display:block !important;
    font-size:17px !important;
    line-height:1 !important;
    font-weight:900 !important;
  }}

  .admin-mobile-bottom-nav b {{
    display:block !important;
    font-size:11px !important;
    line-height:1.1 !important;
    font-weight:800 !important;
    white-space:nowrap !important;
  }}
}}

@media(max-width:380px) {{
  .admin-mobile-bottom-nav {{
    left:5px !important;
    right:5px !important;
    bottom:5px !important;
    padding:6px 4px !important;
    border-radius:16px !important;
  }}

  .admin-mobile-bottom-nav span {{
    font-size:16px !important;
  }}

  .admin-mobile-bottom-nav b {{
    font-size:10px !important;
  }}
}}


/* LOGS_FILTER_UI_V1 */
.logs-filter-table {{
  font-size:13px !important;
}}

.logs-filter-table th,
.logs-filter-table td {{
  padding:7px 8px !important;
  line-height:1.3 !important;
}}

.log-result-badge {{
  display:inline-block !important;
  padding:2px 7px !important;
  border-radius:999px !important;
  font-size:12px !important;
  font-weight:900 !important;
  white-space:nowrap !important;
}}

.log-result-badge.ok {{
  background:#dcfce7 !important;
  color:#166534 !important;
  border:1px solid #bbf7d0 !important;
}}

.log-result-badge.bad {{
  background:#fee2e2 !important;
  color:#991b1b !important;
  border:1px solid #fecaca !important;
}}

@media(max-width:760px) {{
  .logs-filter-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .logs-filter-table th,
  .logs-filter-table td {{
    padding:5px 6px !important;
    font-size:12px !important;
  }}

  .log-result-badge {{
    font-size:11px !important;
    padding:2px 6px !important;
  }}
}}


/* VOUCHER_DEVICE_DETAIL_V1 */
.voucher-device-detail-table {{
  font-size:13px !important;
}}

.voucher-device-detail-table th,
.voucher-device-detail-table td {{
  padding:7px 8px !important;
  line-height:1.3 !important;
}}

@media(max-width:760px) {{
  .voucher-device-detail-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .voucher-device-detail-table th,
  .voucher-device-detail-table td {{
    padding:5px 6px !important;
    font-size:12px !important;
  }}
}}


/* VOUCHER_EDIT_UI_V1 */
@media(max-width:760px) {{
  .card input[type="checkbox"] {{
    width:auto !important;
    margin-right:6px !important;
  }}
}}


/* ADMIN_HEALTH_PAGE_V1 */
.health-check-table {{
  font-size:13px !important;
}}

.health-check-table th,
.health-check-table td {{
  padding:8px 9px !important;
  line-height:1.35 !important;
}}

.health-badge {{
  display:inline-block !important;
  padding:3px 8px !important;
  border-radius:999px !important;
  font-size:12px !important;
  font-weight:900 !important;
  white-space:nowrap !important;
}}

.health-ok {{
  background:#dcfce7 !important;
  color:#166534 !important;
  border:1px solid #bbf7d0 !important;
}}

.health-warn {{
  background:#fef3c7 !important;
  color:#92400e !important;
  border:1px solid #fde68a !important;
}}

.health-bad {{
  background:#fee2e2 !important;
  color:#991b1b !important;
  border:1px solid #fecaca !important;
}}

@media(max-width:760px) {{
  .health-check-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .health-check-table th,
  .health-check-table td {{
    padding:6px 7px !important;
    font-size:12px !important;
  }}

  .health-badge {{
    font-size:11px !important;
    padding:2px 6px !important;
  }}
}}


/* LOGS_FILTER_UI_V2_SAFE */
.logs-filter-table {{
  font-size:13px !important;
}}

.logs-filter-table th,
.logs-filter-table td {{
  padding:7px 8px !important;
  line-height:1.3 !important;
}}

.log-result-badge {{
  display:inline-block !important;
  padding:2px 7px !important;
  border-radius:999px !important;
  font-size:12px !important;
  font-weight:900 !important;
  white-space:nowrap !important;
}}

.log-result-badge.ok {{
  background:#dcfce7 !important;
  color:#166534 !important;
  border:1px solid #bbf7d0 !important;
}}

.log-result-badge.bad {{
  background:#fee2e2 !important;
  color:#991b1b !important;
  border:1px solid #fecaca !important;
}}

@media(max-width:760px) {{
  .logs-filter-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .logs-filter-table th,
  .logs-filter-table td {{
    padding:5px 6px !important;
    font-size:12px !important;
  }}
}}


/* AUTO_BACKUP_STATUS_UI_V1 */
.auto-backup-log {{
  background:#0f172a !important;
  color:#e5e7eb !important;
  padding:10px !important;
  border-radius:10px !important;
  overflow:auto !important;
  white-space:pre-wrap !important;
  font-size:12px !important;
  line-height:1.45 !important;
}}

@media(max-width:760px) {{
  .auto-backup-log {{
    font-size:11px !important;
    padding:8px !important;
    max-height:260px !important;
  }}
}}


/* EXPIRING_VOUCHERS_PAGE_V1 */
.expiring-table {{
  font-size:13px !important;
}}

.expiring-table th,
.expiring-table td {{
  padding:7px 8px !important;
  line-height:1.3 !important;
}}

.expiring-mini-btn {{
  font-size:12px !important;
  padding:4px 7px !important;
  border-radius:8px !important;
  margin:2px !important;
}}

@media(max-width:760px) {{
  .expiring-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .expiring-table th,
  .expiring-table td {{
    padding:5px 6px !important;
    font-size:12px !important;
  }}

  .expiring-mini-btn {{
    font-size:11px !important;
    padding:4px 6px !important;
  }}
}}


/* DASHBOARD_ALERTS_UI_V1 */
.dashboard-alert-card h2 {{
  margin-bottom:6px !important;
}}

.dashboard-alert-item {{
  display:grid !important;
  grid-template-columns:1fr auto !important;
  gap:10px !important;
  align-items:center !important;
  padding:10px 11px !important;
  margin:8px 0 !important;
  border-radius:13px !important;
  border:1px solid #e5e7eb !important;
  background:#f8fafc !important;
}}

.dashboard-alert-item b {{
  display:block !important;
  font-size:15px !important;
  margin-bottom:3px !important;
}}

.dashboard-alert-item p {{
  margin:0 !important;
  color:#475569 !important;
  line-height:1.35 !important;
}}

.dashboard-alert-ok {{
  background:#f0fdf4 !important;
  border-color:#bbf7d0 !important;
}}

.dashboard-alert-ok b {{
  color:#166534 !important;
}}

.dashboard-alert-warn {{
  background:#fffbeb !important;
  border-color:#fde68a !important;
}}

.dashboard-alert-warn b {{
  color:#92400e !important;
}}

.dashboard-alert-bad {{
  background:#fef2f2 !important;
  border-color:#fecaca !important;
}}

.dashboard-alert-bad b {{
  color:#991b1b !important;
}}

.dashboard-alert-btn {{
  white-space:nowrap !important;
  font-size:12px !important;
  padding:6px 9px !important;
}}

@media(max-width:760px) {{
  .dashboard-alert-item {{
    grid-template-columns:1fr !important;
    gap:7px !important;
    padding:9px !important;
  }}

  .dashboard-alert-item b {{
    font-size:14px !important;
  }}

  .dashboard-alert-item p {{
    font-size:12px !important;
  }}

  .dashboard-alert-btn {{
    width:100% !important;
    text-align:center !important;
    display:block !important;
  }}
}}


/* MAINTENANCE_PAGE_V1 */
.maintenance-grid {{
  display:grid !important;
  grid-template-columns:repeat(2,minmax(0,1fr)) !important;
  gap:10px !important;
}}

.maintenance-action,
.maintenance-action-button {{
  display:block !important;
  width:100% !important;
  box-sizing:border-box !important;
  text-align:left !important;
  padding:13px !important;
  border-radius:14px !important;
  border:1px solid #e5e7eb !important;
  background:#f8fafc !important;
  color:#0f172a !important;
  text-decoration:none !important;
  cursor:pointer !important;
  margin:0 !important;
  min-height:86px !important;
}}

.maintenance-action:hover,
.maintenance-action-button:hover {{
  background:#eef2ff !important;
  border-color:#c7d2fe !important;
}}

.maintenance-action b,
.maintenance-action-button b {{
  display:block !important;
  font-size:15px !important;
  margin-bottom:5px !important;
}}

.maintenance-action span,
.maintenance-action-button span {{
  display:block !important;
  font-size:12px !important;
  color:#475569 !important;
  line-height:1.35 !important;
}}

.maintenance-form {{
  margin:0 !important;
}}

.maintenance-action-button.danger {{
  background:#fef2f2 !important;
  border-color:#fecaca !important;
}}

.maintenance-action-button.danger b {{
  color:#991b1b !important;
}}

@media(max-width:760px) {{
  .maintenance-grid {{
    grid-template-columns:1fr !important;
    gap:8px !important;
  }}

  .maintenance-action,
  .maintenance-action-button {{
    min-height:0 !important;
    padding:11px !important;
  }}

  .maintenance-action b,
  .maintenance-action-button b {{
    font-size:14px !important;
  }}

  .maintenance-action span,
  .maintenance-action-button span {{
    font-size:12px !important;
  }}
}}


/* DB_CHECK_READONLY_V1 */
.dbcheck-table {{
  font-size:13px !important;
}}

.dbcheck-table th,
.dbcheck-table td {{
  padding:8px 9px !important;
  line-height:1.35 !important;
  vertical-align:top !important;
}}

.dbcheck-badge {{
  display:inline-block !important;
  padding:3px 8px !important;
  border-radius:999px !important;
  font-size:12px !important;
  font-weight:900 !important;
  white-space:nowrap !important;
}}

.dbcheck-ok {{
  background:#dcfce7 !important;
  color:#166534 !important;
  border:1px solid #bbf7d0 !important;
}}

.dbcheck-warn {{
  background:#fef3c7 !important;
  color:#92400e !important;
  border:1px solid #fde68a !important;
}}

.dbcheck-bad {{
  background:#fee2e2 !important;
  color:#991b1b !important;
  border:1px solid #fecaca !important;
}}

@media(max-width:760px) {{
  .dbcheck-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .dbcheck-table th,
  .dbcheck-table td {{
    padding:6px 7px !important;
    font-size:12px !important;
  }}

  .dbcheck-badge {{
    font-size:11px !important;
    padding:2px 6px !important;
  }}
}}


/* DB_FIX_PAGE_V1 */
.dbfix-table {{
  font-size:13px !important;
}}

.dbfix-table th,
.dbfix-table td {{
  padding:8px 9px !important;
  line-height:1.35 !important;
  vertical-align:top !important;
}}

@media(max-width:760px) {{
  .dbfix-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .dbfix-table th,
  .dbfix-table td {{
    padding:6px 7px !important;
    font-size:12px !important;
  }}
}}


/* ADMIN_HELP_PAGE_V1 */
.help-link-grid {{
  display:grid !important;
  grid-template-columns:repeat(3,minmax(0,1fr)) !important;
  gap:8px !important;
}}

.help-link-grid a {{
  display:block !important;
  padding:10px !important;
  border-radius:12px !important;
  background:#f8fafc !important;
  border:1px solid #e5e7eb !important;
  color:#0f172a !important;
  text-decoration:none !important;
  font-weight:800 !important;
  text-align:center !important;
}}

.help-link-grid a:hover {{
  background:#eef2ff !important;
  border-color:#c7d2fe !important;
}}

.help-code {{
  background:#0f172a !important;
  color:#e5e7eb !important;
  padding:12px !important;
  border-radius:12px !important;
  overflow:auto !important;
  white-space:pre-wrap !important;
  font-size:12px !important;
  line-height:1.45 !important;
}}

.help-table {{
  font-size:13px !important;
}}

.help-table th,
.help-table td {{
  padding:8px 9px !important;
  line-height:1.35 !important;
  vertical-align:top !important;
}}

.help-steps p {{
  padding:8px 9px !important;
  margin:7px 0 !important;
  background:#f8fafc !important;
  border:1px solid #e5e7eb !important;
  border-radius:10px !important;
}}

@media(max-width:760px) {{
  .help-link-grid {{
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
    gap:7px !important;
  }}

  .help-link-grid a {{
    padding:9px 7px !important;
    font-size:12px !important;
  }}

  .help-code {{
    font-size:11px !important;
    padding:9px !important;
    max-height:320px !important;
  }}

  .help-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .help-table th,
  .help-table td {{
    padding:6px 7px !important;
    font-size:12px !important;
  }}
}}


/* VOUCHER_DISPLAY_GUARD_V1 */
.voucher-display-guard-table {{
  font-size:13px !important;
}}

.voucher-display-guard-table th,
.voucher-display-guard-table td {{
  padding:7px 8px !important;
  line-height:1.3 !important;
}}

@media(max-width:760px) {{
  .voucher-display-guard-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .voucher-display-guard-table th,
  .voucher-display-guard-table td {{
    padding:5px 6px !important;
    font-size:12px !important;
  }}
}}



/* ADMIN_DEVICES_SUPER_COMPACT_V4 */
.dev4-top {{
  padding:12px !important;
}}

.dev4-top h1 {{
  margin-bottom:8px !important;
}}

.dev4-stats {{
  display:grid !important;
  grid-template-columns:repeat(4,minmax(0,1fr)) !important;
  gap:7px !important;
}}

.dev4-stats div {{
  background:#f8fafc !important;
  border:1px solid #e5e7eb !important;
  border-radius:10px !important;
  padding:8px !important;
  font-size:12px !important;
  color:#64748b !important;
}}

.dev4-stats b {{
  display:block !important;
  font-size:18px !important;
  color:#0f172a !important;
  margin-top:2px !important;
}}

.dev4-search {{
  display:flex !important;
  gap:7px !important;
  align-items:center !important;
  flex-wrap:wrap !important;
}}

.dev4-search input {{
  flex:1 !important;
  min-width:160px !important;
  height:34px !important;
  font-size:13px !important;
}}

.dev4-search button,
.dev4-search .btn {{
  padding:8px 10px !important;
  font-size:12px !important;
}}

.dev4-filter-row {{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:6px !important;
  margin-top:8px !important;
}}

.dev4-filter {{
  padding:7px 10px !important;
  font-size:12px !important;
}}

.dev4-filter-active {{
  background:#2563eb !important;
  color:#fff !important;
}}

.dev4-list {{
  display:grid !important;
  grid-template-columns:repeat(2,minmax(0,1fr)) !important;
  gap:8px !important;
}}

.dev4-card {{
  background:#fff !important;
  border:1px solid #e5e7eb !important;
  border-radius:14px !important;
  padding:10px !important;
  box-shadow:0 4px 16px rgba(15,23,42,.05) !important;
}}

.dev4-head {{
  display:flex !important;
  justify-content:space-between !important;
  align-items:center !important;
  gap:8px !important;
  margin-bottom:8px !important;
}}

.dev4-name {{
  font-size:14px !important;
  font-weight:900 !important;
  color:#0f172a !important;
  overflow:hidden !important;
  text-overflow:ellipsis !important;
  white-space:nowrap !important;
}}

.dev4-badge {{
  flex:0 0 auto !important;
  border-radius:999px !important;
  padding:3px 7px !important;
  font-size:11px !important;
  font-weight:900 !important;
}}

.dev4-good {{
  background:#dcfce7 !important;
  color:#166534 !important;
}}

.dev4-bad {{
  background:#fee2e2 !important;
  color:#991b1b !important;
}}

.dev4-muted {{
  background:#e5e7eb !important;
  color:#374151 !important;
}}

.dev4-main {{
  display:grid !important;
  grid-template-columns:repeat(4,minmax(0,1fr)) !important;
  gap:6px !important;
}}

.dev4-main div {{
  background:#f8fafc !important;
  border-radius:9px !important;
  padding:6px !important;
  min-width:0 !important;
}}

.dev4-main span {{
  display:block !important;
  color:#64748b !important;
  font-size:10px !important;
  margin-bottom:2px !important;
}}

.dev4-main b {{
  display:block !important;
  color:#0f172a !important;
  font-size:12px !important;
  overflow:hidden !important;
  text-overflow:ellipsis !important;
  white-space:nowrap !important;
}}

.dev4-sub {{
  margin-top:7px !important;
  color:#64748b !important;
  font-size:10px !important;
  line-height:1.35 !important;
  display:flex !important;
  gap:8px !important;
  flex-wrap:wrap !important;
}}

.dev4-actions {{
  margin-top:8px !important;
  display:flex !important;
  gap:5px !important;
  flex-wrap:wrap !important;
}}

.dev4-actions form {{
  display:inline-block !important;
  margin:0 !important;
}}

.dev4-actions button {{
  padding:5px 7px !important;
  font-size:11px !important;
  border-radius:8px !important;
}}

@media(max-width:760px) {{
  .dev4-list {{
    grid-template-columns:1fr !important;
    gap:7px !important;
  }}

  .dev4-card {{
    padding:8px !important;
    border-radius:12px !important;
  }}

  .dev4-main {{
    grid-template-columns:repeat(4,minmax(0,1fr)) !important;
    gap:4px !important;
  }}

  .dev4-main div {{
    padding:5px 4px !important;
  }}

  .dev4-main span {{
    font-size:9px !important;
  }}

  .dev4-main b {{
    font-size:11px !important;
  }}

  .dev4-stats {{
    grid-template-columns:repeat(4,minmax(0,1fr)) !important;
    gap:5px !important;
  }}

  .dev4-stats div {{
    padding:6px 4px !important;
    font-size:10px !important;
    text-align:center !important;
  }}

  .dev4-stats b {{
    font-size:16px !important;
  }}

  .dev4-sub {{
    font-size:9px !important;
  }}
}}


/* EXPORT_UNUSED_VISIBLE_V1 */
.export-unused-notice {{
  border:2px solid #22c55e !important;
  background:#f0fdf4 !important;
}}

.export-unused-main-btn {{
  background:#16a34a !important;
  color:#fff !important;
  font-weight:900 !important;
  padding:10px 14px !important;
  border-radius:12px !important;
}}

.export-unused-stat {{
  background:#dcfce7 !important;
  border-color:#86efac !important;
}}

.export-unused-stat b {{
  color:#166534 !important;
}}


/* VOUCHER_TOP_TOOLS_PLAN_EDIT_V1 */
.voucher-top-tools {{
  margin-top:10px !important;
  display:grid !important;
  grid-template-columns:repeat(3,minmax(0,1fr)) !important;
  gap:8px !important;
}}

.voucher-top-tool {{
  background:#f8fafc !important;
  border:1px solid #e5e7eb !important;
  border-radius:12px !important;
  padding:10px !important;
}}

.voucher-top-tool summary {{
  font-weight:900 !important;
  cursor:pointer !important;
  color:#0f172a !important;
}}

.voucher-plan-table {{
  font-size:13px !important;
}}

.voucher-plan-table th,
.voucher-plan-table td {{
  padding:7px 8px !important;
  line-height:1.3 !important;
  vertical-align:top !important;
}}

.plan-edit-details {{
  display:inline-block !important;
  margin-right:4px !important;
}}

.plan-edit-form {{
  margin-top:8px !important;
  padding:8px !important;
  border:1px solid #e5e7eb !important;
  border-radius:10px !important;
  background:#fff !important;
  min-width:220px !important;
}}

.plan-edit-form p {{
  margin:5px 0 3px !important;
  font-size:12px !important;
  color:#64748b !important;
}}

.plan-edit-form input {{
  width:100% !important;
  height:30px !important;
  font-size:12px !important;
  padding:5px 7px !important;
}}

@media(max-width:760px) {{
  .voucher-top-tools {{
    grid-template-columns:1fr !important;
    gap:7px !important;
  }}

  .voucher-top-tool {{
    padding:8px !important;
  }}

  .voucher-plan-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .voucher-plan-table th,
  .voucher-plan-table td {{
    padding:6px 7px !important;
    font-size:12px !important;
  }}
}}


/* VOUCHER_TOP_UI_STEP2 */
.voucher-top-ui2 {{
  margin-top:12px !important;
  padding:12px !important;
  background:#f8fafc !important;
  border:1px solid #e5e7eb !important;
  border-radius:14px !important;
}}

.voucher-top-ui2-head {{
  display:flex !important;
  justify-content:space-between !important;
  align-items:flex-start !important;
  gap:12px !important;
  margin-bottom:10px !important;
}}

.voucher-top-ui2-head h2 {{
  margin:0 0 3px !important;
  font-size:18px !important;
  color:#0f172a !important;
}}

.voucher-top-ui2-head p {{
  margin:0 !important;
}}

.voucher-top-ui2-actions {{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:8px !important;
  justify-content:flex-end !important;
}}

.voucher-top-ui2-actions form {{
  margin:0 !important;
}}

.voucher-top-ui2-grid {{
  display:grid !important;
  grid-template-columns:1fr 1fr !important;
  gap:10px !important;
}}

.voucher-top-ui2-box {{
  background:#fff !important;
  border:1px solid #e5e7eb !important;
  border-radius:12px !important;
  padding:0 !important;
  overflow:hidden !important;
}}

.voucher-top-ui2-box summary {{
  list-style:none !important;
  cursor:pointer !important;
  padding:12px !important;
  display:flex !important;
  flex-direction:column !important;
  gap:3px !important;
  border-bottom:1px solid transparent !important;
}}

.voucher-top-ui2-box summary::-webkit-details-marker {{
  display:none !important;
}}

.voucher-top-ui2-box summary b {{
  font-size:15px !important;
  color:#0f172a !important;
}}

.voucher-top-ui2-box summary span {{
  font-size:12px !important;
  color:#64748b !important;
}}

.voucher-top-ui2-box[open] summary {{
  border-bottom-color:#e5e7eb !important;
  background:#f9fafb !important;
}}

.voucher-top-ui2-box form,
.voucher-plan-add-panel,
.voucher-plan-list-panel {{
  padding:12px !important;
}}

.voucher-top-ui2-plan {{
  grid-column:1 / -1 !important;
}}

.voucher-plan-add-panel {{
  background:#f8fafc !important;
  border-bottom:1px solid #e5e7eb !important;
}}

.voucher-plan-add-panel h3,
.voucher-plan-list-panel h3 {{
  margin:0 0 8px !important;
  font-size:14px !important;
  color:#0f172a !important;
}}

.voucher-plan-table {{
  width:100% !important;
  font-size:13px !important;
}}

.voucher-plan-table th,
.voucher-plan-table td {{
  padding:7px 8px !important;
  line-height:1.35 !important;
  vertical-align:top !important;
}}

.plan-edit-details {{
  display:inline-block !important;
  margin-right:5px !important;
}}

.plan-edit-form {{
  margin-top:8px !important;
  padding:8px !important;
  border:1px solid #e5e7eb !important;
  border-radius:10px !important;
  background:#fff !important;
  min-width:230px !important;
}}

.plan-edit-form p {{
  margin:5px 0 3px !important;
  font-size:12px !important;
  color:#64748b !important;
}}

.plan-edit-form input {{
  width:100% !important;
  height:30px !important;
  font-size:12px !important;
  padding:5px 7px !important;
}}

@media(max-width:760px) {{
  .voucher-top-ui2 {{
    padding:9px !important;
  }}

  .voucher-top-ui2-head {{
    display:block !important;
  }}

  .voucher-top-ui2-actions {{
    justify-content:flex-start !important;
    margin-top:8px !important;
  }}

  .voucher-top-ui2-grid {{
    grid-template-columns:1fr !important;
    gap:8px !important;
  }}

  .voucher-top-ui2-box summary {{
    padding:10px !important;
  }}

  .voucher-top-ui2-box form,
  .voucher-plan-add-panel,
  .voucher-plan-list-panel {{
    padding:10px !important;
  }}

  .voucher-plan-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
    font-size:12px !important;
  }}

  .voucher-plan-table th,
  .voucher-plan-table td {{
    padding:6px 7px !important;
    font-size:12px !important;
  }}
}}


/* VOUCHER_COMPACT_TOOLS_UI_V3 */
.voucher-compact-tools {{
  margin-top:10px !important;
  padding:8px !important;
  background:#f8fafc !important;
  border:1px solid #e5e7eb !important;
  border-radius:12px !important;
}}

.voucher-compact-row {{
  display:flex !important;
  flex-wrap:wrap !important;
  align-items:center !important;
  gap:7px !important;
}}

.voucher-compact-row form {{
  margin:0 !important;
}}

.voucher-compact-menu {{
  position:relative !important;
  display:inline-block !important;
}}

.voucher-compact-menu summary {{
  list-style:none !important;
  cursor:pointer !important;
  user-select:none !important;
  padding:7px 11px !important;
  border-radius:10px !important;
  border:1px solid #cbd5e1 !important;
  background:#fff !important;
  color:#0f172a !important;
  font-size:13px !important;
  font-weight:800 !important;
  line-height:1.2 !important;
}}

.voucher-compact-menu summary::-webkit-details-marker {{
  display:none !important;
}}

.voucher-compact-menu[open] summary {{
  background:#e0f2fe !important;
  border-color:#38bdf8 !important;
}}

.voucher-compact-panel {{
  position:absolute !important;
  z-index:50 !important;
  top:38px !important;
  left:0 !important;
  width:320px !important;
  max-width:calc(100vw - 34px) !important;
  padding:10px !important;
  background:#fff !important;
  border:1px solid #cbd5e1 !important;
  border-radius:12px !important;
  box-shadow:0 12px 28px rgba(15,23,42,.16) !important;
}}

.voucher-compact-panel-wide {{
  width:520px !important;
}}

.voucher-compact-panel-plan {{
  width:760px !important;
  max-height:70vh !important;
  overflow:auto !important;
}}

.voucher-compact-grid {{
  display:grid !important;
  grid-template-columns:repeat(2,minmax(0,1fr)) !important;
  gap:7px !important;
}}

.voucher-compact-form-row {{
  display:flex !important;
  flex-direction:column !important;
  gap:3px !important;
}}

.voucher-compact-form-row label {{
  font-size:12px !important;
  color:#64748b !important;
  font-weight:700 !important;
}}

.voucher-compact-form-row input,
.voucher-compact-form-row select {{
  height:31px !important;
  font-size:13px !important;
  padding:5px 7px !important;
  border-radius:8px !important;
}}

.voucher-compact-panel button {{
  margin-top:8px !important;
  padding:7px 11px !important;
  font-size:13px !important;
}}

.voucher-compact-btn {{
  padding:7px 11px !important;
  border-radius:10px !important;
  font-size:13px !important;
  font-weight:800 !important;
  line-height:1.2 !important;
}}

.voucher-compact-plan-add {{
  padding-bottom:10px !important;
  border-bottom:1px solid #e5e7eb !important;
  margin-bottom:10px !important;
}}

.voucher-compact-plan-add > b,
.voucher-compact-plan-list > b {{
  display:block !important;
  margin-bottom:7px !important;
  font-size:13px !important;
  color:#0f172a !important;
}}

.voucher-compact-plan-table {{
  font-size:12px !important;
}}

.voucher-compact-plan-table th,
.voucher-compact-plan-table td {{
  padding:6px 7px !important;
  line-height:1.25 !important;
  vertical-align:top !important;
}}

.plan-edit-details {{
  display:inline-block !important;
  margin-right:4px !important;
}}

.plan-edit-details summary {{
  padding:5px 8px !important;
  font-size:12px !important;
}}

.plan-edit-form {{
  margin-top:6px !important;
  padding:8px !important;
  border:1px solid #e5e7eb !important;
  border-radius:10px !important;
  background:#f8fafc !important;
  min-width:220px !important;
}}

.plan-edit-form p {{
  margin:4px 0 2px !important;
  font-size:12px !important;
  color:#64748b !important;
}}

.plan-edit-form input {{
  width:100% !important;
  height:29px !important;
  font-size:12px !important;
  padding:5px 7px !important;
}}

@media(max-width:760px) {{
  .voucher-compact-tools {{
    padding:7px !important;
  }}

  .voucher-compact-row {{
    gap:6px !important;
  }}

  .voucher-compact-menu summary,
  .voucher-compact-btn {{
    font-size:12px !important;
    padding:7px 9px !important;
  }}

  .voucher-compact-panel,
  .voucher-compact-panel-wide,
  .voucher-compact-panel-plan {{
    position:fixed !important;
    left:10px !important;
    right:10px !important;
    top:92px !important;
    width:auto !important;
    max-width:none !important;
    max-height:72vh !important;
    overflow:auto !important;
  }}

  .voucher-compact-grid {{
    grid-template-columns:1fr !important;
  }}

  .voucher-compact-plan-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
  }}
}}


/* VOUCHER_TOOLS_BELOW_CARD_V4 */
.voucher-tools-card-v4 {{
  margin-top:12px !important;
}}

.voucher-tools-head-v4 {{
  display:flex !important;
  justify-content:space-between !important;
  align-items:flex-start !important;
  gap:12px !important;
  margin-bottom:10px !important;
}}

.voucher-tools-head-v4 h2 {{
  margin:0 0 3px !important;
  font-size:18px !important;
  color:#0f172a !important;
}}

.voucher-tools-head-v4 p {{
  margin:0 !important;
}}

.voucher-tools-head-actions-v4 {{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:8px !important;
  justify-content:flex-end !important;
}}

.voucher-tools-head-actions-v4 form {{
  margin:0 !important;
}}

.voucher-tools-grid-v4 {{
  display:grid !important;
  grid-template-columns:1fr 1fr !important;
  gap:10px !important;
}}

.voucher-tool-box-v4 {{
  border:1px solid #e5e7eb !important;
  border-radius:12px !important;
  background:#f8fafc !important;
  overflow:hidden !important;
}}

.voucher-tool-box-v4 summary {{
  cursor:pointer !important;
  padding:10px 12px !important;
  display:flex !important;
  justify-content:space-between !important;
  align-items:center !important;
  gap:10px !important;
  list-style:none !important;
}}

.voucher-tool-box-v4 summary::-webkit-details-marker {{
  display:none !important;
}}

.voucher-tool-box-v4 summary b {{
  font-size:14px !important;
  color:#0f172a !important;
}}

.voucher-tool-box-v4 summary span {{
  font-size:12px !important;
  color:#64748b !important;
  text-align:right !important;
}}

.voucher-tool-box-v4[open] summary {{
  background:#eef6ff !important;
  border-bottom:1px solid #e5e7eb !important;
}}

.voucher-tool-body-v4 {{
  padding:10px 12px !important;
  background:#fff !important;
}}

.voucher-plan-box-v4 {{
  grid-column:1 / -1 !important;
}}

.voucher-form-grid-v4 {{
  display:grid !important;
  grid-template-columns:repeat(2,minmax(0,1fr)) !important;
  gap:8px !important;
}}

.voucher-form-grid-v4 p {{
  margin:0 0 3px !important;
  font-size:12px !important;
  color:#64748b !important;
  font-weight:700 !important;
}}

.voucher-form-grid-v4 input,
.voucher-form-grid-v4 select {{
  width:100% !important;
  height:32px !important;
  font-size:13px !important;
  padding:5px 7px !important;
  border-radius:8px !important;
}}

.voucher-tool-body-v4 button {{
  margin-top:8px !important;
}}

.voucher-plan-add-v4 {{
  padding-bottom:10px !important;
  border-bottom:1px solid #e5e7eb !important;
  margin-bottom:10px !important;
}}

.voucher-plan-add-v4 h3,
.voucher-plan-list-v4 h3 {{
  margin:0 0 8px !important;
  font-size:14px !important;
  color:#0f172a !important;
}}

.voucher-plan-table-v4 {{
  width:100% !important;
  font-size:13px !important;
}}

.voucher-plan-table-v4 th,
.voucher-plan-table-v4 td {{
  padding:7px 8px !important;
  line-height:1.35 !important;
  vertical-align:top !important;
}}

.plan-edit-details {{
  display:inline-block !important;
  margin-right:5px !important;
}}

.plan-edit-form {{
  margin-top:8px !important;
  padding:8px !important;
  border:1px solid #e5e7eb !important;
  border-radius:10px !important;
  background:#f8fafc !important;
  min-width:230px !important;
}}

.plan-edit-form p {{
  margin:5px 0 3px !important;
  font-size:12px !important;
  color:#64748b !important;
}}

.plan-edit-form input {{
  width:100% !important;
  height:30px !important;
  font-size:12px !important;
  padding:5px 7px !important;
}}

@media(max-width:760px) {{
  .voucher-tools-head-v4 {{
    display:block !important;
  }}

  .voucher-tools-head-actions-v4 {{
    justify-content:flex-start !important;
    margin-top:8px !important;
  }}

  .voucher-tools-grid-v4 {{
    grid-template-columns:1fr !important;
  }}

  .voucher-tool-box-v4 summary {{
    display:block !important;
  }}

  .voucher-tool-box-v4 summary span {{
    display:block !important;
    text-align:left !important;
    margin-top:3px !important;
  }}

  .voucher-form-grid-v4 {{
    grid-template-columns:1fr !important;
  }}

  .voucher-plan-table-v4 {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
  }}
}}


/* VOUCHER_TOOLS_DENSE_TABLE_UI_V5 */
.voucher-tools-dense-card {{
  margin-top:12px !important;
}}

.voucher-tools-dense-card h2 {{
  margin-bottom:4px !important;
}}

.voucher-tools-dense-table {{
  margin-top:8px !important;
}}

.voucher-tools-dense-table th,
.voucher-tools-dense-table td {{
  font-size:13px !important;
  padding:8px 9px !important;
  vertical-align:top !important;
}}

.voucher-tools-row-detail {{
  display:inline-block !important;
  position:relative !important;
}}

.voucher-tools-row-detail > summary {{
  display:inline-block !important;
  padding:6px 10px !important;
  border-radius:9px !important;
  background:#f8fafc !important;
  border:1px solid #cbd5e1 !important;
  font-weight:800 !important;
  cursor:pointer !important;
  list-style:none !important;
}}

.voucher-tools-row-detail > summary::-webkit-details-marker {{
  display:none !important;
}}

.voucher-tools-row-detail[open] > summary {{
  background:#e0f2fe !important;
  border-color:#38bdf8 !important;
}}

.voucher-tools-inline-form {{
  margin-top:8px !important;
  padding:10px !important;
  background:#fff !important;
  border:1px solid #e5e7eb !important;
  border-radius:12px !important;
  min-width:360px !important;
  box-shadow:0 8px 22px rgba(15,23,42,.10) !important;
}}

.voucher-tools-form-grid {{
  display:grid !important;
  grid-template-columns:repeat(2,minmax(0,1fr)) !important;
  gap:8px !important;
}}

.voucher-tools-form-grid p {{
  margin:0 0 3px !important;
  font-size:12px !important;
  color:#64748b !important;
  font-weight:700 !important;
}}

.voucher-tools-form-grid input,
.voucher-tools-form-grid select {{
  width:100% !important;
  height:31px !important;
  font-size:13px !important;
  padding:5px 7px !important;
  border-radius:8px !important;
}}

.voucher-tools-plan-detail {{
  display:block !important;
}}

.voucher-tools-plan-detail .voucher-tools-inline-form {{
  box-shadow:none !important;
  min-width:0 !important;
}}

.voucher-tools-plan-section {{
  margin-top:9px !important;
  padding:9px !important;
  background:#f8fafc !important;
  border:1px solid #e5e7eb !important;
  border-radius:12px !important;
}}

.voucher-tools-plan-section > b {{
  display:block !important;
  margin-bottom:7px !important;
  color:#0f172a !important;
}}

.voucher-tools-plan-table {{
  font-size:12px !important;
  margin-top:6px !important;
}}

.voucher-tools-plan-table th,
.voucher-tools-plan-table td {{
  font-size:12px !important;
  padding:6px 7px !important;
}}

@media(max-width:760px) {{
  .voucher-tools-dense-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
  }}

  .voucher-tools-dense-table th,
  .voucher-tools-dense-table td {{
    font-size:12px !important;
    padding:7px 8px !important;
  }}

  .voucher-tools-inline-form {{
    min-width:260px !important;
    max-width:calc(100vw - 50px) !important;
  }}

  .voucher-tools-form-grid {{
    grid-template-columns:1fr !important;
  }}

  .voucher-tools-plan-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
  }}
}}


/* VOUCHER_TOOLS_NO_EXPAND_UI_V6 */
.voucher-tools-no-expand-card {{
  margin-top:12px !important;
}}

.voucher-tools-no-expand-card h2 {{
  margin-bottom:4px !important;
}}

.voucher-tools-no-expand-table {{
  margin-top:8px !important;
}}

.voucher-tools-no-expand-table th,
.voucher-tools-no-expand-table td {{
  font-size:13px !important;
  padding:8px 9px !important;
  vertical-align:top !important;
}}

.voucher-tools-title-cell {{
  width:190px !important;
  min-width:170px !important;
}}

.voucher-tools-title-cell b {{
  color:#0f172a !important;
}}

.voucher-tools-direct-form {{
  margin:0 !important;
}}

.voucher-tools-direct-grid {{
  display:grid !important;
  grid-template-columns:1.1fr 1.7fr auto !important;
  gap:7px !important;
  align-items:end !important;
}}

.voucher-tools-direct-grid-5 {{
  grid-template-columns:.7fr .7fr 1fr 1.6fr auto !important;
}}

.voucher-tools-direct-grid-6 {{
  grid-template-columns:1.2fr .75fr .75fr .75fr .75fr 1.2fr auto !important;
}}

.voucher-tools-direct-grid p {{
  margin:0 0 3px !important;
  font-size:12px !important;
  color:#64748b !important;
  font-weight:700 !important;
}}

.voucher-tools-direct-grid input,
.voucher-tools-direct-grid select {{
  width:100% !important;
  height:30px !important;
  font-size:12px !important;
  padding:5px 7px !important;
  border-radius:8px !important;
  box-sizing:border-box !important;
}}

.voucher-tools-submit-cell {{
  white-space:nowrap !important;
}}

.voucher-tools-submit-cell button {{
  height:30px !important;
}}

.voucher-tools-plan-direct {{
  display:grid !important;
  gap:9px !important;
}}

.voucher-tools-plan-add-direct,
.voucher-tools-plan-list-direct {{
  background:#f8fafc !important;
  border:1px solid #e5e7eb !important;
  border-radius:12px !important;
  padding:8px !important;
}}

.voucher-tools-plan-add-direct > b,
.voucher-tools-plan-list-direct > b {{
  display:block !important;
  margin-bottom:7px !important;
  color:#0f172a !important;
  font-size:13px !important;
}}

.voucher-tools-plan-direct-table {{
  font-size:12px !important;
}}

.voucher-tools-plan-direct-table th,
.voucher-tools-plan-direct-table td {{
  font-size:12px !important;
  padding:6px 7px !important;
}}

.plan-edit-details {{
  display:inline-block !important;
  margin-right:4px !important;
}}

.plan-edit-details summary {{
  padding:5px 8px !important;
  font-size:12px !important;
}}

.plan-edit-form {{
  margin-top:6px !important;
  padding:8px !important;
  border:1px solid #e5e7eb !important;
  border-radius:10px !important;
  background:#fff !important;
  min-width:220px !important;
}}

.plan-edit-form p {{
  margin:4px 0 2px !important;
  font-size:12px !important;
  color:#64748b !important;
}}

.plan-edit-form input {{
  width:100% !important;
  height:29px !important;
  font-size:12px !important;
  padding:5px 7px !important;
}}

@media(max-width:760px) {{
  .voucher-tools-no-expand-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
  }}

  .voucher-tools-no-expand-table th,
  .voucher-tools-no-expand-table td {{
    font-size:12px !important;
    padding:7px 8px !important;
  }}

  .voucher-tools-title-cell {{
    width:150px !important;
    min-width:150px !important;
  }}

  .voucher-tools-direct-grid,
  .voucher-tools-direct-grid-5,
  .voucher-tools-direct-grid-6 {{
    grid-template-columns:1fr !important;
    min-width:260px !important;
  }}

  .voucher-tools-plan-direct-table {{
    display:block !important;
    overflow-x:auto !important;
    white-space:nowrap !important;
  }}
}}


/* VOUCHER_BULK_SELECT_DELETE_V2 */
.voucher-bulk-bar-v2 {{
  display:flex !important;
  flex-wrap:wrap !important;
  align-items:center !important;
  gap:8px !important;
  margin:8px 0 10px !important;
  padding:8px !important;
  background:#f8fafc !important;
  border:1px solid #e5e7eb !important;
  border-radius:12px !important;
}}

.voucher-bulk-bar-v2 form {{
  display:inline-block !important;
  margin:0 !important;
}}

.dense-select-col {{
  width:34px !important;
  min-width:34px !important;
  text-align:center !important;
}}

.voucher-select-box {{
  width:16px !important;
  height:16px !important;
  cursor:pointer !important;
}}

@media(max-width:760px) {{
  .voucher-bulk-bar-v2 {{
    gap:6px !important;
    padding:7px !important;
  }}

  .voucher-bulk-bar-v2 .btn,
  .voucher-bulk-bar-v2 button {{
    font-size:12px !important;
    padding:6px 8px !important;
  }}
}}

</style>
</head>
<body><div class="wrap">{nav}{body}</div>
<div class="admin-mobile-bottom-nav">
  <a href="/admin"><span>⌂</span><b>首页</b></a>
  <a href="/admin/vouchers"><span>▣</span><b>兑换码</b></a>
  <a href="/admin/devices"><span>◎</span><b>设备</b></a>
  <a href="/admin/maintenance"><span>⚙</span><b>维护</b></a>
  <a href="/admin/logout"><span>↩</span><b>退出</b></a>
</div>
</body>
</html>"""


def _wp_customer_page_polished(title, body):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>{esc(title)}</title>
<style>
* {{
  box-sizing:border-box;
}}

html {{
  -webkit-text-size-adjust:100%;
  text-size-adjust:100%;
}}

body {{
  margin:0;
  min-height:100vh;
  font-family:Arial,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:
    radial-gradient(circle at top left, rgba(37,99,235,.30), transparent 36%),
    radial-gradient(circle at bottom right, rgba(14,165,233,.16), transparent 32%),
    #0f172a;
  color:#e5e7eb;
}}

.wrap {{
  width:100%;
  max-width:460px;
  margin:0 auto;
  padding:18px 12px 28px;
}}

.card {{
  background:rgba(15,23,42,.86);
  border:1px solid rgba(148,163,184,.26);
  border-radius:18px;
  padding:15px;
  margin:10px 0;
  box-shadow:0 12px 30px rgba(0,0,0,.24);
  backdrop-filter:blur(10px);
}}

.hero-card {{
  padding:18px 16px;
  text-align:center;
}}

.brand-pill {{
  display:inline-block;
  padding:5px 10px;
  border-radius:999px;
  color:#93c5fd;
  background:rgba(37,99,235,.18);
  border:1px solid rgba(147,197,253,.35);
  font-size:12px;
  font-weight:900;
  letter-spacing:.12em;
  text-transform:uppercase;
  margin-bottom:10px;
}}

h1 {{
  margin:0;
  font-size:27px;
  line-height:1.12;
  letter-spacing:-.03em;
}}

h2 {{
  margin:0 0 8px;
  font-size:16px;
  line-height:1.2;
}}

.info {{
  white-space:pre-wrap;
  line-height:1.48;
  color:#cbd5e1;
  font-size:14px;
}}

.notice-text {{
  margin-top:10px;
  color:#cbd5e1;
  font-size:14px;
  line-height:1.48;
}}

.plan-box {{
  text-align:center;
  background:linear-gradient(135deg,rgba(37,99,235,.28),rgba(14,165,233,.12));
  border:1px solid rgba(96,165,250,.58);
  border-radius:16px;
  padding:14px;
  color:#dbeafe;
  font-weight:900;
  font-size:18px;
  line-height:1.55;
}}

.plan-box:before {{
  content:"WiFi Plan";
  display:block;
  color:#93c5fd;
  font-size:12px;
  font-weight:900;
  letter-spacing:.13em;
  text-transform:uppercase;
  margin-bottom:6px;
}}

.contact-box {{
  background:linear-gradient(135deg,rgba(34,197,94,.18),rgba(16,185,129,.08));
  border:1px solid rgba(74,222,128,.48);
  border-radius:15px;
  padding:13px;
  color:#dcfce7;
  font-weight:700;
  line-height:1.55;
}}

.contact-box:before {{
  content:"Need help?";
  display:block;
  color:#86efac;
  font-size:12px;
  font-weight:900;
  letter-spacing:.13em;
  text-transform:uppercase;
  margin-bottom:6px;
}}

.voucher-form {{
  margin:0;
}}

.voucher-input {{
  width:100%;
  height:54px;
  border-radius:15px;
  border:1px solid rgba(148,163,184,.42);
  background:#020617;
  color:#f8fafc;
  font-size:22px;
  font-weight:900;
  letter-spacing:.08em;
  text-align:center;
  padding:12px;
  outline:none;
  text-transform:uppercase;
}}

.voucher-input:focus {{
  border-color:#60a5fa;
  box-shadow:0 0 0 4px rgba(37,99,235,.25);
}}

button,
.btn {{
  width:100%;
  min-height:48px;
  border:0;
  border-radius:15px;
  background:linear-gradient(135deg,#2563eb,#0ea5e9);
  color:white;
  cursor:pointer;
  text-align:center;
  text-decoration:none;
  display:block;
  font-size:16px;
  font-weight:900;
  padding:13px;
  margin:9px 0 0;
}}

.btn.secondary {{
  background:rgba(15,118,110,.95);
}}

.btn.soft {{
  background:rgba(30,41,59,.88);
  border:1px solid rgba(148,163,184,.28);
}}

.muted {{
  color:#94a3b8;
  font-size:13px;
  line-height:1.45;
}}

.link {{
  color:#93c5fd;
  text-decoration:none;
  font-weight:800;
}}

.row {{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  gap:12px;
  border-bottom:1px solid rgba(148,163,184,.18);
  padding:8px 0;
  font-size:13px;
}}

.row:last-child {{
  border-bottom:0;
}}

.row span {{
  color:#94a3b8;
}}

.row b {{
  text-align:right;
  color:#f8fafc;
  word-break:break-word;
}}

.status-card {{
  text-align:center;
}}

.status-icon {{
  width:58px;
  height:58px;
  border-radius:999px;
  display:flex;
  align-items:center;
  justify-content:center;
  margin:0 auto 10px;
  font-size:30px;
  font-weight:900;
}}

.status-ok {{
  color:#86efac;
  background:rgba(22,101,52,.35);
  border:1px solid rgba(134,239,172,.35);
}}

.status-bad {{
  color:#fecaca;
  background:rgba(127,29,29,.35);
  border:1px solid rgba(252,165,165,.35);
}}

.countdown-box {{
  margin-top:12px;
  padding:14px;
  border-radius:16px;
  background:rgba(2,6,23,.42);
  border:1px solid rgba(148,163,184,.18);
  text-align:center;
}}

.countdown-box span {{
  display:block;
  color:#94a3b8;
  font-size:12px;
  margin-bottom:5px;
}}

.countdown-box b {{
  display:block;
  font-size:38px;
  line-height:1;
}}

.customer-grid {{
  display:grid;
  grid-template-columns:1fr;
  gap:10px;
}}

@media(max-width:420px) {{
  .wrap {{
    padding:10px 9px 22px;
  }}

  .card {{
    padding:13px;
    margin:8px 0;
    border-radius:16px;
  }}

  h1 {{
    font-size:24px;
  }}

  .voucher-input {{
    height:52px;
    font-size:20px;
  }}

  button,
  .btn {{
    min-height:46px;
    font-size:15px;
  }}
}}
</style>
</head>
<body>
<div class="wrap">
{body}
</div>
</body>
</html>"""


def _wp_customer_v2_page(title, body):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>{esc(title)}</title>
<style>
* {{
  box-sizing: border-box;
}}

html {{
  min-height: 100%;
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
}}

body {{
  margin: 0;
  min-height: 100vh;
  font-family: Arial, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #f8fafc;
  background:
    radial-gradient(circle at 0% 12%, rgba(37, 99, 235, .28), transparent 34%),
    radial-gradient(circle at 100% 100%, rgba(14, 165, 233, .20), transparent 34%),
    linear-gradient(180deg, #071633 0%, #0b1228 48%, #081226 100%);
  overflow-x: hidden;
}}

.wrap {{
  width: 100%;
  max-width: 430px;
  margin: 0 auto;
  padding: 12px 10px 26px;
}}

.card {{
  position: relative;
  overflow: hidden;
  background: rgba(8, 18, 42, .78);
  border: 1px solid rgba(96, 165, 250, .24);
  border-radius: 18px;
  padding: 15px;
  margin: 9px 0;
  box-shadow: 0 14px 34px rgba(0, 0, 0, .25);
}}

.card-soft {{
  background: rgba(8, 18, 42, .62);
}}

.hero-card {{
  min-height: 128px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  padding: 20px 16px;
  border-color: rgba(96, 165, 250, .32);
}}

.hero-card:after {{
  content: "◜";
  position: absolute;
  right: 20px;
  top: 48px;
  font-size: 82px;
  line-height: 1;
  color: rgba(37, 99, 235, .13);
  transform: rotate(45deg);
}}

.pill {{
  display: inline-block;
  align-self: center;
  padding: 5px 12px;
  border-radius: 999px;
  color: #dbeafe;
  background: linear-gradient(135deg, rgba(37, 99, 235, .75), rgba(30, 64, 175, .72));
  border: 1px solid rgba(147, 197, 253, .32);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: .13em;
  text-transform: uppercase;
  margin-bottom: 11px;
}}

h1 {{
  margin: 0;
  font-size: 31px;
  line-height: 1.06;
  letter-spacing: -.04em;
}}

h2 {{
  margin: 0 0 10px;
  font-size: 17px;
  line-height: 1.18;
}}

p {{
  margin: 0;
}}

.sub {{
  color: #cbd5e1;
  font-size: 14px;
  line-height: 1.45;
  margin-top: 10px;
}}

.plan-card {{
  display: grid;
  grid-template-columns: 58px 1fr;
  gap: 12px;
  align-items: center;
  padding: 16px;
}}

.round-icon {{
  width: 54px;
  height: 54px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(37, 99, 235, .24);
  border: 1px solid rgba(96, 165, 250, .35);
  color: #bfdbfe;
  font-size: 25px;
  font-weight: 900;
}}

.plan-card .label,
.summary-label {{
  display: block;
  color: #60a5fa;
  font-size: 13px;
  font-weight: 900;
  margin-bottom: 4px;
}}

.plan-card b {{
  display: block;
  color: #f8fafc;
  font-size: 18px;
  line-height: 1.25;
}}

.login-card {{
  padding: 18px 16px;
}}

.login-title {{
  font-size: 19px;
  font-weight: 900;
  margin: 0 0 12px;
}}

.voucher-input-wrap {{
  position: relative;
}}

.voucher-input-icon {{
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
  font-size: 19px;
  pointer-events: none;
}}

.voucher-input {{
  width: 100%;
  height: 58px;
  border-radius: 15px;
  border: 2px solid rgba(56, 189, 248, .75);
  outline: none;
  background: rgba(2, 6, 23, .58);
  color: #f8fafc;
  font-size: 20px;
  font-weight: 900;
  letter-spacing: .06em;
  padding: 12px 14px 12px 46px;
  text-transform: uppercase;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .04);
}}

.voucher-input::placeholder {{
  color: #94a3b8;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: none;
}}

.voucher-input:focus {{
  border-color: #38bdf8;
  box-shadow: 0 0 0 4px rgba(14, 165, 233, .22);
}}

button,
.btn {{
  width: 100%;
  min-height: 52px;
  border: 0;
  border-radius: 15px;
  display: block;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
  color: white;
  background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
  box-shadow: 0 10px 24px rgba(14, 165, 233, .25);
  font-size: 17px;
  font-weight: 900;
  padding: 14px;
  margin-top: 12px;
}}

.btn.green {{
  background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
  box-shadow: 0 10px 24px rgba(20, 184, 166, .18);
}}

.btn.dark {{
  background: rgba(30, 41, 59, .92);
  border: 1px solid rgba(148, 163, 184, .22);
  box-shadow: none;
}}

.small-link-line {{
  margin-top: 13px;
  text-align: center;
  color: #cbd5e1;
  font-size: 14px;
}}

.link {{
  color: #38bdf8;
  font-weight: 900;
  text-decoration: underline;
  text-underline-offset: 3px;
}}

.help-card {{
  display: grid;
  grid-template-columns: 58px 1fr;
  gap: 12px;
  align-items: center;
  border-color: rgba(34, 197, 94, .34);
  background: linear-gradient(135deg, rgba(6, 78, 59, .45), rgba(8, 18, 42, .72));
}}

.help-label {{
  color: #34d399;
  display: block;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: .13em;
  margin-bottom: 6px;
}}

.help-card b {{
  display: block;
  font-size: 16px;
  line-height: 1.38;
}}

.footer-note {{
  color: #94a3b8;
  text-align: center;
  font-size: 13px;
  line-height: 1.45;
  margin: 14px 8px 0;
}}

.status-hero {{
  display: grid;
  grid-template-columns: 86px 1fr;
  gap: 14px;
  align-items: center;
  padding: 18px 16px;
}}

.big-status-icon {{
  width: 76px;
  height: 76px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 44px;
  font-weight: 900;
}}

.big-status-icon.ok {{
  color: #34d399;
  background: rgba(6, 78, 59, .52);
  border: 1px solid rgba(52, 211, 153, .58);
}}

.big-status-icon.bad {{
  color: #fecaca;
  background: rgba(127, 29, 29, .40);
  border: 1px solid rgba(252, 165, 165, .46);
}}

.status-hero h1 {{
  font-size: 28px;
}}

.status-text-ok {{
  color: #34d399;
  font-size: 21px;
  font-weight: 900;
  margin-top: 4px;
}}

.status-text-bad {{
  color: #f87171;
  font-size: 21px;
  font-weight: 900;
  margin-top: 4px;
}}

.summary-card {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
  text-align: center;
  padding: 14px 8px;
}}

.summary-item {{
  padding: 0 6px;
  border-right: 1px solid rgba(96, 165, 250, .24);
}}

.summary-item:last-child {{
  border-right: 0;
}}

.summary-value {{
  display: block;
  color: #f8fafc;
  font-size: 16px;
  font-weight: 900;
  word-break: break-word;
}}

.summary-value.good {{
  color: #34d399;
}}

.section-title {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}}

.square-icon {{
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: rgba(37, 99, 235, .24);
  border: 1px solid rgba(96, 165, 250, .28);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bfdbfe;
  font-size: 19px;
}}

.section-title h2 {{
  margin: 0;
}}

.row {{
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(148, 163, 184, .16);
  font-size: 14px;
}}

.row:last-child {{
  border-bottom: 0;
}}

.row span {{
  color: #cbd5e1;
}}

.row b {{
  color: #f8fafc;
  text-align: right;
  word-break: break-word;
}}

.countdown-box {{
  margin-top: 12px;
  padding: 13px;
  border-radius: 15px;
  text-align: center;
  background: rgba(2, 6, 23, .42);
  border: 1px solid rgba(148, 163, 184, .18);
}}

.countdown-box span {{
  display: block;
  color: #94a3b8;
  font-size: 12px;
  margin-bottom: 4px;
}}

.countdown-box b {{
  display: block;
  font-size: 34px;
  line-height: 1;
}}

@media(max-width:420px) {{
  .wrap {{
    max-width: none;
    padding: 9px 8px 22px;
  }}

  .card {{
    border-radius: 16px;
    padding: 13px;
    margin: 8px 0;
  }}

  h1 {{
    font-size: 28px;
  }}

  .hero-card {{
    min-height: 120px;
  }}

  .plan-card,
  .help-card {{
    grid-template-columns: 50px 1fr;
  }}

  .round-icon {{
    width: 48px;
    height: 48px;
    font-size: 22px;
  }}

  .voucher-input {{
    height: 56px;
    font-size: 19px;
  }}

  button,
  .btn {{
    min-height: 50px;
    font-size: 16px;
  }}

  .status-hero {{
    grid-template-columns: 76px 1fr;
  }}

  .big-status-icon {{
    width: 68px;
    height: 68px;
    font-size: 38px;
  }}

  .summary-value {{
    font-size: 15px;
  }}
}}
</style>
</head>
<body>
<div class="wrap">
{body}
</div>
</body>
</html>"""

def print_vouchers_page(vouchers, lan_ip, portal_title="WiFi Access"):
    card_htmls = []
    import urllib.parse
    for v in vouchers:
        code = v.get("code", "")
        plan = v.get("speed_profile_name", "Default Plan")
        minutes = int(v.get("minutes", 0))

        if minutes == 0:
            duration = "永久"
        elif minutes >= 1440:
            duration = f"{minutes // 1440} 天"
        elif minutes >= 60:
            duration = f"{minutes // 60} 小时"
        else:
            duration = f"{minutes} 分钟"

        max_devices = v.get("max_devices", 1)
        device_text = f"限 {max_devices} 台设备" if max_devices > 1 else "仅限 1 台设备"

        target_url = f"http://{lan_ip}/?code={code}"
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=130x130&data={urllib.parse.quote(target_url)}"

        card_htmls.append(f"""
<div class="voucher-card">
  <div class="card-header">
    <span class="wifi-icon">📶</span> <b>{esc(portal_title)}</b>
  </div>
  <div class="card-body">
    <div class="qr-container">
      <img src="{qr_url}" alt="QR Code" width="110" height="110">
    </div>
    <div class="info-container">
      <div class="voucher-code">{esc(code)}</div>
      <div class="plan-name">套餐: {esc(plan)} ({esc(duration)})</div>
      <div class="device-limit">{esc(device_text)}</div>
    </div>
  </div>
  <div class="card-footer">
    扫码自动连接 或 访问 http://{esc(lan_ip)} 输入兑换码
  </div>
</div>
""")

    cards_joined = "\n".join(card_htmls)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>打印兑换码 - WiFi Portal</title>
<style>
body {{
  font-family: system-ui, -apple-system, sans-serif;
  margin: 0;
  padding: 20px;
  background: #f8fafc;
  color: #1e293b;
}}
.no-print {{
  background: white;
  padding: 15px 20px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  margin-bottom: 25px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.btn {{
  background: #2563eb;
  color: white;
  border: 0;
  padding: 10px 20px;
  font-size: 15px;
  font-weight: bold;
  border-radius: 8px;
  cursor: pointer;
}}
.btn:hover {{
  background: #1d4ed8;
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}}
.voucher-card {{
  background: white;
  border: 2px dashed #cbd5e1;
  border-radius: 12px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  page-break-inside: avoid;
}}
.card-header {{
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 8px;
  margin-bottom: 10px;
  font-size: 15px;
  display: flex;
  align-items: center;
}}
.wifi-icon {{
  margin-right: 6px;
}}
.card-body {{
  display: flex;
  align-items: center;
  gap: 12px;
}}
.qr-container img {{
  border: 1px solid #f1f5f9;
  border-radius: 6px;
  display: block;
}}
.info-container {{
  flex: 1;
}}
.voucher-code {{
  font-size: 22px;
  font-weight: 900;
  letter-spacing: 1px;
  color: #0f172a;
  margin-bottom: 6px;
  font-family: monospace;
}}
.plan-name {{
  font-size: 13px;
  font-weight: bold;
  color: #2563eb;
  margin-bottom: 4px;
}}
.device-limit {{
  font-size: 12px;
  color: #64748b;
}}
.card-footer {{
  margin-top: 10px;
  border-top: 1px dotted #e2e8f0;
  padding-top: 8px;
  font-size: 10px;
  color: #64748b;
  text-align: center;
}}
@media print {{
  body {{
    background: white;
    padding: 0;
  }}
  .no-print {{
    display: none;
  }}
  .grid {{
    gap: 15px;
  }}
  .voucher-card {{
    border-color: #94a3b8;
  }}
}}
</style>
</head>
<body>
<div class="no-print">
  <div>
    <h2 style="margin:0 0 5px;font-size:18px">打印预览</h2>
    <span style="font-size:13px;color:#64748b">系统已准备好 {len(vouchers)} 张兑换码卡片。建议使用 A4 纸张打印。</span>
  </div>
  <button class="btn" onclick="window.print()">立即打印</button>
</div>
<div class="grid">
{cards_joined}
</div>
</body>
</html>"""
