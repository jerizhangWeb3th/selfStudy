#!/usr/bin/env python3
"""测试 CDP Page.addScriptToEvaluateOnNewDocument 注入 stealth"""
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

        # ★ CDP 注入（document 创建时执行，早于任何页面脚本）
        cdp = await context.new_cdp_session(page)
        await cdp.send("Page.enable")
        await cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": STEALTH_SCRIPT})

        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        result = await page.evaluate("""() => ({
            platform: navigator.platform,
            chromeApp: !!(window.chrome && window.chrome.app),
            uaDataPlatform: (navigator.userAgentData || {}).platform,
            webdriver: String(navigator.webdriver),
            pluginsLen: navigator.plugins.length,
            mini: window.__MINI_TEST__ || 'n/a',
            webglVendor: (() => {
                try {
                    const c = document.createElement('canvas');
                    const gl = c.getContext('webgl');
                    return gl ? gl.getParameter(gl.VENDOR) : null;
                } catch(e) { return 'ERR'; }
            })()
        })""")
        print("=== CDP 注入效果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
