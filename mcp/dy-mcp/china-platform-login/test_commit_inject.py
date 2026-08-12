#!/usr/bin/env python3
"""测试 commit 时机注入（尽量早于页面脚本）"""
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

        # 方法A: commit 时立即 evaluate（不等待 domcontentloaded）
        try:
            await page.goto("https://creator.douyin.com/", wait_until="commit", timeout=60000)
            await page.evaluate(STEALTH_SCRIPT)  # 在 document 刚创建时注入
            await page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            print(f"commit注入异常: {str(e)[:120]}")
            await page.goto("https://creator.douyin.com/", wait_until="domcontentloaded", timeout=60000)
            await page.evaluate(STEALTH_SCRIPT)
        await asyncio.sleep(5)

        result = await page.evaluate("""() => ({
            platform: navigator.platform,
            chromeApp: !!(window.chrome && window.chrome.app),
            uaDataPlatform: (navigator.userAgentData || {}).platform,
            webdriver: String(navigator.webdriver),
            pluginsLen: navigator.plugins.length
        })""")
        print("=== commit 时机注入 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
