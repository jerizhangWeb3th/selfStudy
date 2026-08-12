# 抖音创作者中心扫码登录 — v8-win 跨平台高匿名版

基于你的 dy-mcp 登录逻辑，融合小红书登录的 macOS 指纹伪装方案，实现高匿名性抖音登录。

## ✨ 核心特性

| 特性 | 说明 |
|:---|:---|
| 🖥️ **跨平台** | Windows / macOS / Linux 自动检测 Chrome 路径 |
| 🍎 **MAC 伪装** | UA/platform/UA-data/WebGL 全伪装成 Mac Chrome 150（借鉴小红书方案） |
| 🕵️ **反自动化** | 真 Chrome + patchright（非标准 playwright），swiftshader GPU |
| 🚫 **不自动 reload** | 扫码后保持页面状态，避免打断登录确认（关键修复！） |
| 🧹 **自动清旧码** | 每次生成新二维码自动删除旧码，杜绝发旧码 |

## 📦 安装

```bash
# 1. 安装 Python 依赖
pip install patchright

# 2. 安装/指定 Chrome
#    Windows: 安装 Google Chrome（默认路径自动检测）
#    或运行: patchright install chrome
```

## 🚀 用法

```bash
# 直接运行（会弹出 Chrome 窗口显示抖音登录页）
python douyin_login_v8_win.py
```

### 运行流程
1. 自动打开 Chrome → 抖音创作者中心
2. 点击「我是创作者」→ 二维码渲染
3. 二维码保存到 `./qr/douyin_qr_最新时间.png`（**目录里永远只有最新一张**）
4. **用抖音 APP 扫一扫** → 手机上点「确认登录」
5. 登录成功 → cookie 自动保存到 `./cookies/douyin_douyin_main.json`

### 登录成功检测（双条件）
- URL 跳转到 `creator-micro`（创作者工作台）
- 或页面出现「退出」按钮

## ⚙️ 环境变量

| 变量 | 默认 | 说明 |
|:---|:---|:---|
| `DOUYIN_REFRESH` | 300 | 等待二维码超时自动重载秒数（不打断已扫码） |

## 📁 输出文件

```
./qr/douyin_qr_*.png           # 最新二维码（自动清理旧码）
./qr_latest.txt                # 最新二维码路径
./login_state.txt              # 登录状态 (QR_READY / SUCCESS)
./cookies/douyin_douyin_main.json  # 登录 cookie（给 dy-mcp 上传用）
```

## 🔧 上传视频

cookie 生成后，你的 `server.py` 上传逻辑可直接复用：
```python
context = await browser.new_context(storage_state=account_file)
```
把 `account_file` 指向 `./cookies/douyin_douyin_main.json` 即可。
