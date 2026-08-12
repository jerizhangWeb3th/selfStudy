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

# 融合版指纹伪装（70+ 检测点）：goofish 60+ 点 + 小红书 UA-data
try:
    from dy_stealth import STEALTH_SCRIPT
    print("✅ 加载融合 stealth (70+ 检测点)", flush=True)
except Exception:
    # fallback: 小红书 MAC 伪装（旧方案）
    STEALTH_SCRIPT = "(" + r"""
() => {
  try { Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel', configurable: true }); } catch(e) {}
  try { Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0, configurable: true }); } catch(e) {}
  try { Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true }); } catch(e) {}
  try { Object.defineProperty(navigator, 'deviceMemory', { get: () => 8, configurable: true }); } catch(e) {}
  try { Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US'], configurable: true }); } catch(e) {}
  try { Object.defineProperty(screen, 'width', { get: () => 1440, configurable: true }); } catch(e) {}
  try { Object.defineProperty(screen, 'height', { get: () => 900, configurable: true }); } catch(e) {}
  try { Object.defineProperty(window, 'devicePixelRatio', { get: () => 2, configurable: true }); } catch(e) {}
  return 'mac-applied';
}
""" + ")"

MAC_OVERRIDE_SCRIPT = STEALTH_SCRIPT


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
    # 导航后必须重新注入 stealth（add_init_script 在此环境不生效，需 page.evaluate）
    try:
        await page.evaluate(MAC_OVERRIDE_SCRIPT)
        print("✅ 导航后重新注入 stealth", flush=True)
    except Exception as e:
        print(f"⚠️ stealth 注入失败: {str(e)[:60]}")
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
            args=LAUNCH_ARGS,
        )
        if chrome:
            launch_kwargs["executable_path"] = chrome

        browser = await pw.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            device_scale_factor=2,
            user_agent=MAC_UA,
        )
        # MAC 指纹覆盖（页面加载前）
        await context.add_init_script(MAC_OVERRIDE_SCRIPT)
        page = await context.new_page()
        await page.evaluate(MAC_OVERRIDE_SCRIPT)  # 页面加载后再打一次

        while True:
            state = await goto_login(page)
            if state == "ALREADY_LOGGED":
                print("🎉 已登录！", flush=True)
                await context.storage_state(path=str(ACCOUNT_FILE))
                write_state("SUCCESS", str(ACCOUNT_FILE))
                await context.close()
                await browser.close()
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

            # 等待登录成功，处理扫脸/手机号验证
            login_result = await wait_for_login(page, context, browser)
            if login_result == "SUCCESS":
                return
            # 其他情况（如验证失败需重新扫码）则继续外层循环
            print("⚠️ 验证未通过，重新获取二维码...", flush=True)
            await asyncio.sleep(3)


async def check_logged_in(page) -> bool:
    """检查是否已登录成功"""
    url = page.url
    if "creator-micro" in url:
        return True
    try:
        logout_btn = await page.query_selector("text=退出")
        if logout_btn:
            return True
    except Exception:
        pass
    return False


async def save_login_success(page, context, browser) -> str:
    """登录成功后保存 cookie 和截图"""
    print(f"🎉 登录成功! URL={page.url[:80]}", flush=True)
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
    await browser.close()
    return "SUCCESS"


async def click_face_verify(page) -> bool:
    """自动点击「手机刷脸验证」

    扫码后 #uc-second-verify 下出现验证方式选择，点击「手机刷脸验证」
    返回是否成功点击
    """
    print("🔍 检测 #uc-second-verify 验证方式选择...", flush=True)

    # 策略1: 精确匹配 #uc-second-verify 下含「手机刷脸验证」的元素
    try:
        el = page.locator("#uc-second-verify").locator("text=手机刷脸验证").first
        if await el.count() > 0 and await el.is_visible():
            await el.click(timeout=5000)
            print("✅ 已点击「手机刷脸验证」(#uc-second-verify)", flush=True)
            write_state("FACE_CLICKED", "已选择手机刷脸验证")
            return True
    except Exception:
        pass

    # 策略2: 直接点击 #uc-second-verify 内可点击的子元素
    try:
        container = page.locator("#uc-second-verify")
        if await container.count() > 0 and await container.is_visible():
            # 点击容器内含刷脸文字的元素
            items = container.locator("div, span, a, button, li, p, label")
            count = await items.count()
            for i in range(count):
                item = items.nth(i)
                text = await item.text_content()
                if text and ("刷脸" in text or "人脸" in text):
                    await item.click(timeout=3000)
                    print(f"✅ 已点击「{text.strip()}」(#uc-second-verify 子元素)", flush=True)
                    write_state("FACE_CLICKED", "已选择手机刷脸验证")
                    return True
    except Exception:
        pass

    # 策略3: 文本匹配兜底
    fallback_selectors = [
        "text=手机刷脸验证",
        "text=刷脸验证",
        "text=人脸识别",
        "text=扫脸验证",
    ]
    for sel in fallback_selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                await el.click(timeout=3000)
                print(f"✅ 已点击验证选项(选择器: {sel})", flush=True)
                write_state("FACE_CLICKED", "已选择刷脸验证")
                return True
        except Exception:
            continue

    # 策略4: JS fallback 点击含刷脸文字的元素
    try:
        clicked = await page.evaluate("""() => {
            // 优先在 #uc-second-verify 内查找
            const container = document.querySelector('#uc-second-verify');
            if (container) {
                const all = container.querySelectorAll('div, span, a, button, li, p, label');
                for (const el of all) {
                    const text = el.innerText || el.textContent || '';
                    if ((text.includes('手机刷脸') || text.includes('刷脸验证') ||
                         text.includes('人脸识别') || text.includes('扫脸验证')) &&
                         el.offsetParent !== null) {
                        el.click();
                        return true;
                    }
                }
            }
            // 全局 fallback
            const all = document.querySelectorAll('div, span, a, button, li, p, label');
            for (const el of all) {
                const text = el.innerText || el.textContent || '';
                if ((text.includes('手机刷脸') || text.includes('刷脸验证') ||
                     text.includes('人脸识别') || text.includes('扫脸验证')) &&
                     el.offsetParent !== null) {
                    el.click();
                    return true;
                }
            }
            return false;
        }""")
        if clicked:
            print("✅ 已点击「手机刷脸验证」(JS fallback)", flush=True)
            write_state("FACE_CLICKED", "已选择刷脸验证")
            return True
    except Exception:
        pass

    return False


async def extract_face_qr(page) -> str:
    """提取人脸验证二维码截图

    点击人脸识别后约5秒出现新二维码，截图保存
    """
    print("⏳ 等待人脸验证二维码出现...", flush=True)
    # 等待5秒让二维码渲染
    await asyncio.sleep(5)

    stamp = time.strftime("%H%M%S")
    out = str(QR_DIR / f"douyin_face_qr_{stamp}.png")

    # 先尝试提取 base64 图片
    info = await page.evaluate("""() => {
        const imgs = document.querySelectorAll('img');
        for (const img of imgs) {
            const src = String(img.src || '');
            if (src.startsWith('data:image') && img.getBoundingClientRect().width > 80) return src;
        }
        return '';
    }""")
    if info.startswith("data:image"):
        b64 = info.split(",", 1)[1]
        with open(out, "wb") as f:
            f.write(base64.b64decode(b64))
        print(f"✅ 人脸验证二维码(base64): {out}", flush=True)
    else:
        # fallback: 截取页面中间区域
        await page.screenshot(path=out, clip={"x": 570, "y": 180, "width": 300, "height": 300})
        print(f"✅ 人脸验证二维码(截图): {out}", flush=True)

    write_latest(out)
    write_state("FACE_QR_READY", out)
    return out


async def wait_for_login(page, context, browser) -> str:
    """等待登录完成，自动处理验证流程

    简化逻辑：
    1. 循环检测：URL 变了 → 登录成功；#uc-second-verify 出现 → 二次校验
    2. 检测到 #uc-second-verify → 自动点击「手机刷脸验证」
    3. 点击后等5秒 → 截图保存人脸二维码
    4. 用户完成人脸识别 → 登录成功

    返回值:
        "SUCCESS" - 登录成功
        "RETRY" - 需要重新扫码
    """
    face_clicked = False        # 是否已点击刷脸验证
    face_qr_saved = False       # 是否已保存人脸二维码
    face_scan_wait_start = 0    # 人脸扫描等待开始时间

    while True:
        # ---- 1. URL 变了 → 登录成功 ----
        if await check_logged_in(page):
            return await save_login_success(page, context, browser)

        # ---- 2. 检测 #uc-second-verify → 二次校验 ----
        try:
            uc_verify = page.locator("#uc-second-verify")
            if await uc_verify.count() > 0 :
                print("🔒 检测到 #uc-second-verify 二次校验!", flush=True)
                clicked = await click_face_verify(page)
                if clicked:
                    face_clicked = True
                else:
                    print("⚠️ 未找到刷脸验证选项，可能需要手动操作", flush=True)
                    face_clicked = True
        except Exception:
            pass

        # ---- 3. 点击刷脸验证后，提取人脸二维码截图 ----
        if face_clicked and not face_qr_saved:
            face_qr_path = await extract_face_qr(page)
            face_qr_saved = True
            face_scan_wait_start = time.monotonic()
            print(f"📱 请用抖音 APP 扫描人脸验证二维码: {face_qr_path}", flush=True)
            print(f"   ⏳ 等待人脸验证完成...", flush=True)

        # ---- 4. 人脸二维码已保存，等待登录 ----
        if face_qr_saved and face_scan_wait_start > 0:
            elapsed = time.monotonic() - face_scan_wait_start
            if elapsed >= 10:
                if await check_logged_in(page):
                    return await save_login_success(page, context, browser)
                if elapsed >= 120:
                    print("⚠️ 人脸验证超时，需要重新扫码", flush=True)
                    write_state("FACE_TIMEOUT", "人脸验证超时")
                    return "RETRY"

        # ---- 5. 检测二维码过期/验证失败 ----
        try:
            expired = await page.evaluate("""() => {
                const text = document.body.innerText;
                return text.includes('二维码已过期') || text.includes('二维码失效') ||
                       text.includes('验证失败') || text.includes('验证过期') ||
                       text.includes('重新扫码') || text.includes('刷新二维码');
            }""")
            if expired:
                print("⚠️ 二维码已过期或验证失败，需要重新扫码!", flush=True)
                write_state("EXPIRED", "二维码过期")
                return "RETRY"
        except Exception:
            pass

        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
