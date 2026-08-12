#!/usr/bin/env python3
"""正确顺序的 CDP 注入：先注册 Page.addScriptToEvaluateOnNewDocument，再 goto"""
import asyncio
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))
_sau = str(Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages")
if _sau not in sys.path:
    sys.path.insert(0, _sau)

from stealth_core import MAC_UA, LAUNCH_ARGS, STEALTH_SCRIPT, find_chrome, ensure_display  # noqa: E402


async def main():
    ensure_display()
    chrome = find_chrome()

    from patchright.async_api import async_playwright

    async with async_playwright() as pw:
        launch_kwargs = dict(headless=False, args=LAUNCH_ARGS)
        if chrome:
            launch_kwargs["executable_path"] = chrome

        browser = await pw.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900}, locale="zh-CN",
            timezone_id="Asia/Shanghai", device_scale_factor=2,
            user_agent=MAC_UA,
        )
        page = await context.new_page()

        # ★ 正确顺序：先注册 CDP 脚本，再导航
        cdp = await context.new_cdp_session(page)
        await cdp.send("Page.enable")
        r = await cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": STEALTH_SCRIPT})
        print("CDP 注册结果:", r)

        await page.goto("https://creator.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        result = await page.evaluate("""() => ({
            platform: navigator.platform,
            chromeApp: !!(window.chrome && window.chrome.app),
            uaDataPlatform: (navigator.userAgentData || {}).platform,
            webdriver: String(navigator.webdriver),
            pluginsLen: navigator.plugins.length
        })""")
        print("=== CDP 先注册后导航 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # 再导航一次（确认持续生效）
        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)
        result2 = await page.evaluate("() => ({platform: navigator.platform})")
        print("导航后:", result2)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
