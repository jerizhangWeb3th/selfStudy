# 🛡️ 反检测增强说明 (STEALTH_ENHANCEMENTS.md)

> 基于 [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload) 修改
> 修改日期: 2026-05-26
> 修改者: link04

---

## 修改背景

原项目在浏览器反检测方面存在以下不足：

1. **启动参数过于简单** — 仅 6 个基础参数，缺少 WebRTC 禁用
2. **无 WebRTC 防护** — WebRTC 会泄露本地 IP，可被 WAF 用于探测无头浏览器
3. **无指纹伪装** — 未集成 fingerprint-injector / fingerprint-generator
4. **防护单层** — 仅靠 `stealth.min.js` 一层防护
5. **启动代码分散** — 各 uploader 各自实现浏览器启动，难以统一维护

---

## 修改内容

### ✅ 1. 新增 `utils/stealth_launcher.py` — 统一反检测入口

核心模块，提供四层反检测：

| 层级 | 机制 | 说明 |
|---|---|---|
| **L1** | Chromium 启动参数 | `--disable-blink-features=AutomationControlled`, `--disable-webrtc`, `--disable-features=WebRtcHideLocalIpsWithMdns` 等 20+ 参数 |
| **L2** | `browserforge` 指纹注入 | 自动生成并注入 navigator、screen、fonts、WebGL、headers 等完整指纹 |
| **L3** | WebRTC API 删除 | 在 JS 最顶层执行 `delete window.RTCPeerConnection` 等，防止 WAF 探测 |
| **L4** | `stealth.min.js` | 屏蔽 `webdriver`、`chrome.runtime`、`plugins` 等自动化特征 |

**关键函数：**

```python
from utils.stealth_launcher import (
    build_launch_kwargs,       # 构建浏览器启动参数
    create_stealth_context,    # 创建带完整反检测的上下文
    create_stealth_page,       # 一步创建上下文+页面
)

# 最简用法
browser = await playwright.chromium.launch(**build_launch_kwargs(headless=True))
context = await create_stealth_context(browser, storage_state="cookies/xxx.json")
page = await context.new_page()
```

### ✅ 2. 增强 `utils/base_social_media.py`

`set_init_script()` 现在注入**两层**脚本：
- `stealth.min.js`（原有一层）
- WebRTC API 删除脚本（新增）

### ✅ 3. 重写 `utils/browser_hook.py`

改为委托给 `stealth_launcher.py`，保持向后兼容。

### ✅ 4. 新增 `browserforge` 依赖

```bash
pip install browserforge
```

`browserforge` 是 Python 版的 Apify Fingerprint Suite，等价于 npm 的
`fingerprint-injector` + `fingerprint-generator`。

### ✅ 5. WebRTC 禁用细节

**L1 启动参数（3 个）：**
```python
"--disable-webrtc",                             # 禁用 WebRTC 核心
"--disable-features=WebRtcHideLocalIpsWithMdns", # 禁用 mDNS 隐藏
"--disable-webrtc-encryption",                   # 禁用 WebRTC 加密
```

**L3 JS 删除（7 个 API）：**
```javascript
delete window.RTCPeerConnection;
delete window.webkitRTCPeerConnection;
delete window.mozRTCPeerConnection;
delete window.RTCIceCandidate;
delete window.RTCSessionDescription;
delete window.RTCDataChannel;
delete window.RTCDataChannelEvent;
```

### ✅ 6. 扩容启动参数（6 → 20+）

| 参数 | 作用 |
|---|---|
| `--disable-blink-features=AutomationControlled` | 去掉 `navigator.webdriver` ⚠️ |
| `--disable-webrtc` | 禁用 WebRTC 核心 🆕 |
| `--disable-features=WebRtcHideLocalIpsWithMdns` | 禁用 mDNS 隐藏 🆕 |
| `--disable-webrtc-encryption` | 禁用 WebRTC 加密 🆕 |
| `--disable-infobars` | 去掉自动化提示条 |
| `--start-maximized` | 最大化窗口 |
| `--no-sandbox` | 禁用沙箱（Docker） |
| `--disable-web-security` | 禁用跨域限制 |
| `--disable-gpu` | 禁用 GPU（headless） 🆕 |
| `--no-default-browser-check` | 跳过默认浏览器检查 🆕 |
| `--no-first-run` | 跳过首次运行向导 🆕 |
| `--disable-background-networking` | 禁用后台网络 🆕 |
| `--disable-sync` | 禁用同步 🆕 |
| `--disable-save-password-bubble` | 隐藏保存密码提示 🆕 |
| `--disable-component-update` | 禁用组件更新 🆕 |
| `--disable-domain-reliability` | 禁用域名可靠性 🆕 |

---

## 使用建议

### 新代码

```python
from patchright.async_api import async_playwright
from utils.stealth_launcher import build_launch_kwargs, create_stealth_context

async with async_playwright() as p:
    browser = await p.chromium.launch(**build_launch_kwargs(headless=True))
    context = await create_stealth_context(
        browser,
        storage_state="cookies/account.json",
        inject_webrtc_deletion=True,
    )
    page = await context.new_page()
```

### 迁移旧代码

旧代码：
```python
browser = await playwright.chromium.launch(headless=True, channel="chrome")
context = await browser.new_context(storage_state=account_file)
context = await set_init_script(context)
```

新代码（两种方式）：

**A. 最小改动** — 只改 launch + set_init_script（set_init_script 已自动包含 WebRTC 删除）：
```python
browser = await playwright.chromium.launch(**build_launch_kwargs(headless=True))
context = await browser.new_context(storage_state=account_file)
context = await set_init_script(context)  # 已增强，自动包含 WebRTC 删除
```

**B. 完整改动** — 使用 create_stealth_context（额外获得指纹注入）：
```python
browser = await playwright.chromium.launch(**build_launch_kwargs(headless=True))
context = await create_stealth_context(browser, storage_state=account_file)
```
