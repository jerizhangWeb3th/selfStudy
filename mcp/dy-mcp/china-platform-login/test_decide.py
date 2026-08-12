#!/usr/bin/env python3
"""决定性测试：bot 页面上 stealth 注入后 navigator.platform 的真实值"""
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

from stealth_core import MAC_UA, LAUNCH_ARGS, STEALTH_SCRIPT, find_chrome, ensure_display, goto_with_stealth  # noqa: E402


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
        await goto_with_stealth(page, "https://bot.incolumitas.com/", timeout=45000)
        await asyncio.sleep(4)

        # 1. 直接检查 navigator 值
        r1 = await page.evaluate("""() => ({
            platform: navigator.platform,
            plugins: navigator.plugins.length,
            pluginNames: Array.from(navigator.plugins).map(p => p.name).join('|'),
            uaDataPlatform: (navigator.userAgentData || {}).platform,
            chromeApp: !!(window.chrome && window.chrome.app)
        })""")
        print("=== evaluate 检查 ===")
        print(json.dumps(r1, indent=2, ensure_ascii=False))

        # 2. 在页面内重新执行 fpCollect 采集，看是否仍是真实值
        r2 = await page.evaluate("""async () => {
            try {
                const fp = await fpCollect.generateFingerprint();
                return {
                    platform: fp.platform,
                    pluginsCount: fp.plugins.length,
                    videoCard: fp.videoCard ? fp.videoCard[0] : null,
                };
            } catch(e) {
                return {error: String(e)};
            }
        }""")
        print("\n=== 页面内重新采集 fpCollect ===")
        print(json.dumps(r2, indent=2, ensure_ascii=False))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
