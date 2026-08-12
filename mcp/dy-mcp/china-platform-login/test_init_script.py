#!/usr/bin/env python3
"""验证 add_init_script 在 new_page 之前注入的正确性"""
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
        # ★ 正确顺序：先 add_init_script，再 new_page
        await context.add_init_script(STEALTH_SCRIPT)
        page = await context.new_page()
        await page.goto("https://creator.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)

        # 检查（不二次 evaluate，纯 init_script 效果）
        result = await page.evaluate("""() => ({
            platform: navigator.platform,
            chromeApp: !!(window.chrome && window.chrome.app),
            uaDataPlatform: (navigator.userAgentData || {}).platform,
            webdriver: String(navigator.webdriver),
            pluginsLen: navigator.plugins.length,
            webglVendor: (() => {
                try {
                    const c = document.createElement('canvas');
                    const gl = c.getContext('webgl');
                    return gl ? gl.getParameter(gl.VENDOR) : null;
                } catch(e) { return 'ERR'; }
            })()
        })""")
        print("=== add_init_script(在 new_page 前) 效果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # 再导航一次（确认 init_script 在后续导航仍生效）
        await page.goto("https://www.baidu.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        result2 = await page.evaluate("() => ({platform: navigator.platform, webdriver: String(navigator.webdriver)})")
        print("\n=== 导航后（无重注入）===")
        print(json.dumps(result2, indent=2, ensure_ascii=False))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
