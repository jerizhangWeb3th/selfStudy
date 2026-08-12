#!/usr/bin/env python3
"""
抖音创作者中心扫码登录 — Windows/macOS/Linux 跨平台版 (v8-win)

【核心特性】
- 跨平台：自动检测 Chrome 路径（Windows / macOS / Linux）
- 高匿名性：MAC 伪装（UA/platform/UA-data/WebGL 全部伪装成 Mac Chrome 150）
  —— 借鉴小红书登录方案，大幅降低被识别为自动化浏览器的概率
- 真 Chrome + patchright（非标准 playwright，无 automation 特征）
- 登录逻辑：打开 creator.douyin.com → 点「我是创作者」→ 提取二维码 →
  扫码后保持页面等待登录成功（URL 跳转 creator-micro 或出现「退出」按钮）→ 保存 cookie
- 不自动 reload：扫码后绝不刷新页面，避免打断登录确认流程
- 自动清理旧二维码文件：每次生成新码自动删除旧码，杜绝发旧码

【依赖安装】
    pip install patchright
    patchright install chrome

【用法】
    python douyin_login_v8_win.py
    # 二维码自动保存到 ./qr/douyin_qr_*.png（最新一张）
    # 扫码成功后 cookie 保存到 ./cookies/douyin_douyin_main.json

【环境变量】
    DOUYIN_REFRESH=300    # 等待二维码超时后自动重载的秒数（默认 300，避免打断扫码）
"""
import asyncio
import os
import sys
import time
import base64
from pathlib import Path

from patchright.async_api import async_playwright

BASE_DIR = Path(__file__).parent.resolve()
QR_DIR = BASE_DIR / "qr"
COOKIE_DIR = BASE_DIR / "cookies"
ACCOUNT_FILE = COOKIE_DIR / "douyin_douyin_main.json"
QR_LATEST_FILE = BASE_DIR / "qr_latest.txt"
STATE_FILE = BASE_DIR / "login_state.txt"

QR_DIR.mkdir(exist_ok=True)
COOKIE_DIR.mkdir(exist_ok=True)

# ============================================================
# 小红书匿名性方案（内联，不依赖外部模块）
# ============================================================
MAC_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"

LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--use-gl=swiftshader",
    "--enable-unsafe-swiftshader",
    "--ignore-gpu-blocklist",
    "--lang=zh-CN",
]

MAC_OVERRIDE_SCRIPT = """() => {
  try { Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel', configurable: true }); } catch(e) {}
  try { Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0, configurable: true }); } catch(e) {}
  try { Object.defineProperty(navigator, 'deviceMemory', { get: () => 8, configurable: true }); } catch(e) {}
  try { Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US'], configurable: true }); } catch(e) {}
  try { Object.defineProperty(navigator, 'language', { get: () => 'zh-CN', configurable: true }); } catch(e) {}
  try { Object.defineProperty(screen, 'width', { get: () => 1440, configurable: true }); } catch(e) {}
  try { Object.defineProperty(screen, 'height', { get: () => 900, configurable: true }); } catch(e) {}
  try { Object.defineProperty(screen, 'availWidth', { get: () => 1440, configurable: true }); } catch(e) {}
  try { Object.defineProperty(screen, 'availHeight', { get: () => 877, configurable: true }); } catch(e) {}
  try { Object.defineProperty(window, 'devicePixelRatio', { get: () => 2, configurable: true }); } catch(e) {}
  try { Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true }); } catch(e) {}
  try {
    const uaData = {
      brands: [
        {brand: 'Chromium', version: '150'},
        {brand: 'Not(A:Brand', version: '24'},
        {brand: 'Google Chrome', version: '150'}
      ],
      mobile: false, platform: 'macOS', architecture: 'x86', bitness: '64',
      model: '', platformVersion: '10.15.7',
      fullVersionList: [
        {brand: 'Chromium', version: '150.0.7871.128'},
        {brand: 'Not(A:Brand', version: '24.0.0.0'},
        {brand: 'Google Chrome', version: '150.0.7871.128'}
      ],
      getHighEntropyValues: () => Promise.resolve({
        architecture: 'x86', bitness: '64', model: '',
        platform: 'macOS', platformVersion: '10.15.7',
        uaFullVersion: '150.0.7871.128',
        fullVersionList: [
          {brand: 'Chromium', version: '150.0.7871.128'},
          {brand: 'Not(A:Brand', version: '24.0.0.0'},
          {brand: 'Google Chrome', version: '150.0.7871.128'}
        ]
      }),
      toJSON: () => ({
        brands: [
          {brand: 'Chromium', version: '150'},
          {brand: 'Not(A:Brand', version: '24'},
          {brand: 'Google Chrome', version: '150'}
        ],
        mobile: false, platform: 'macOS'
      })
    };
    Object.defineProperty(navigator, 'userAgentData', { get: () => uaData, configurable: true });
  } catch(e) {}
  try {
    const origGetParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
      if (param === 0x9245) return 'Apple Inc.';
      if (param === 0x9246) return 'Apple M1';
      if (param === 0x1F00) return 'WebKit';
      if (param === 0x1F01) return 'WebKit WebGL';
      return origGetParam.call(this, param);
    };
  } catch(e) {}
  return 'mac-applied';
}"""


def find_chrome() -> str:
    """跨平台查找 Chrome 可执行文件"""
    candidates = []
    if sys.platform == "win32":
        candidates = [
            os.environ.get("LOCALAPPDATA", "") + r"\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.environ.get("PROGRAMFILES", "") + r"\Google\Chrome\Application\chrome.exe",
            os.environ.get("PROGRAMFILES(X86)", "") + r"\Google\Chrome\Application\chrome.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:  # linux
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def write_latest(path: str):
    """写最新二维码路径 + 清理旧码"""
    try:
        for old in QR_DIR.glob("douyin_qr_*.png"):
            if str(old) != path:
                old.unlink(missing_ok=True)
        print("🧹 已清除旧二维码文件", flush=True)
    except Exception:
        pass
    QR_LATEST_FILE.write_text(path)
    print(f"📡 最新二维码: {path}", flush=True)


def write_state(state: str, payload: str = ""):
    STATE_FILE.write_text(f"{state} {payload}".strip())
    print(f"STATE:{state} {payload}", flush=True)


async def extract_qr(page) -> str:
    """提取二维码 base64 存 PNG"""
    stamp = time.strftime("%H%M%S")
    info = await page.evaluate("""() => {
        const scan = document.querySelector('#douyin_login_comp_scan_code');
        if (scan) {
            const img = scan.querySelector('img');
            if (img && img.src.startsWith('data:image')) return img.src;
        }
        const imgs = document.querySelectorAll('img');
        for (const img of imgs) {
            const src = String(img.src || '');
            if (src.startsWith('data:image') && img.getBoundingClientRect().width > 100) return src;
        }
        return '';
    }""")
    out = str(QR_DIR / f"douyin_qr_{stamp}.png")
    if info.startswith("data:image"):
        b64 = info.split(",", 1)[1]
        with open(out, "wb") as f:
            f.write(base64.b64decode(b64))
        print(f"✅ 二维码(base64): {out}", flush=True)
        return out
    # fallback 裁剪
    await page.screenshot(path=out, clip={"x": 737, "y": 282, "width": 329, "height": 305})
    print(f"✅ 二维码(裁剪): {out}", flush=True)
    return out


async def goto_login(page):
    """进入我是创作者登录页"""
    await page.goto("https://creator.douyin.com/", wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(3)
    if "creator-micro" in page.url:
        return "ALREADY_LOGGED"
    try:
        await page.get_by_text("我是创作者", exact=True).first.click(timeout=10000)
        print("✅ 点击「我是创作者」", flush=True)
    except Exception as e:
        print(f"⚠️ 点击失败(继续尝试): {str(e)[:60]}", flush=True)
    # 等二维码渲染（最多 25 秒）
    for _ in range(12):
        await asyncio.sleep(2)
        has_qr = await page.evaluate("""() => {
            const scan = document.querySelector('#douyin_login_comp_scan_code');
            if (scan) {
                const img = scan.querySelector('img');
                return !!(img && img.src.startsWith('data:image'));
            }
            return false;
        }""")
        if has_qr:
            return "QR_READY"
    return "NO_QR"


async def main():
    refresh = int(os.environ.get("DOUYIN_REFRESH", "300"))
    print("=" * 56)
    print("抖音创作者中心 扫码登录 (v8-win 跨平台高匿名版)")
    print("=" * 56)

    chrome = find_chrome()
    if chrome:
        print(f"Chrome: {chrome}")
    else:
        print("⚠️ 未找到 Chrome，使用 patchright 内置浏览器 (匿名性降低)")
        print("   建议安装 Chrome: https://www.google.com/chrome/")
        print("   然后运行: patchright install chrome")

    async with async_playwright() as pw:
        launch_kwargs = dict(
            headless=False,
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            device_scale_factor=2,
            user_agent=MAC_UA,
            args=LAUNCH_ARGS,
        )
        if chrome:
            launch_kwargs["executable_path"] = chrome

        context = await pw.chromium.launch(**launch_kwargs)
        # MAC 指纹覆盖（页面加载前）
        await context.add_init_script("(" + MAC_OVERRIDE_SCRIPT + ")()")
        page = await context.new_page()
        await page.evaluate(MAC_OVERRIDE_SCRIPT)  # 页面加载后再打一次

        while True:
            state = await goto_login(page)
            if state == "ALREADY_LOGGED":
                print("🎉 已登录！", flush=True)
                await context.storage_state(path=str(ACCOUNT_FILE))
                write_state("SUCCESS", str(ACCOUNT_FILE))
                await context.close()
                return
            if state != "QR_READY":
                print("⚠️ 二维码未出现，重载", flush=True)
                await asyncio.sleep(3)
                continue

            qr_path = await extract_qr(page)
            write_latest(qr_path)
            write_state("QR_READY", qr_path)
            print(f"⏳ 等待扫码...（不自动 reload，避免打断登录确认）", flush=True)
            print(f"   📱 用抖音 APP 扫一扫二维码: {qr_path}", flush=True)
            print(f"   💡 提示: 扫码后请在手机上点「确认登录」", flush=True)

            # 无限等待登录成功（不 reload！）
            last_scan_log = 0
            while True:
                url = page.url
                logged = "creator-micro" in url
                if not logged:
                    try:
                        logout_btn = await page.query_selector("text=退出")
                        if logout_btn:
                            logged = True
                    except Exception:
                        pass
                if logged:
                    print(f"🎉 登录成功! URL={url[:80]}", flush=True)
                    await asyncio.sleep(3)
                    await context.storage_state(path=str(ACCOUNT_FILE))
                    print(f"✅ cookie 已保存: {ACCOUNT_FILE}", flush=True)
                    stamp = time.strftime("%H%M%S")
                    shot = str(QR_DIR.parent / f"douyin_logged_{stamp}.png")
                    try:
                        await page.screenshot(path=shot, full_page=False)
                        print(f"📸 登录成功截图: {shot}", flush=True)
                    except Exception:
                        pass
                    write_state("SUCCESS", f"cookie={ACCOUNT_FILE}")
                    await context.close()
                    return

                # 检测扫码确认提示
                now = time.monotonic()
                if now - last_scan_log > 10:
                    last_scan_log = now
                    try:
                        scanned = await page.evaluate("""() => {
                            const text = document.body.innerText;
                            if (text.includes('扫码成功') || text.includes('确认登录') ||
                                text.includes('扫描成功') || text.includes('请在手机上')) return true;
                            return false;
                        }""")
                        if scanned:
                            print(f"📱 检测到扫码确认提示! ({time.strftime('%H:%M:%S')})", flush=True)
                    except Exception:
                        pass

                await asyncio.sleep(3)

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
