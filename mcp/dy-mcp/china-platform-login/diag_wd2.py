#!/usr/bin/env python3
"""深度检查 fpscanner WEBDRIVER 检测途径（about:blank 环境）"""
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
        await page.goto("about:blank")
        await page.evaluate(STEALTH_SCRIPT)
        await asyncio.sleep(1)

        check = await page.evaluate("""() => {
            const out = {};
            out.navigatorWd = navigator.webdriver;
            out.desc = JSON.stringify(Object.getOwnPropertyDescriptor(navigator, 'webdriver'));
            // 全局变量
            out.windowWebdriver = typeof window.webdriver;
            // Object.getOwnPropertyNames(window) 中可疑项
            const names = Object.getOwnPropertyNames(window);
            const susp = names.filter(n => /webdriver|selenium|cdc_|chrome_|domAutomation/i.test(n));
            out.suspiciousGlobals = susp;
            // Element.prototype.getAttribute 的原生性
            const ga = Element.prototype.getAttribute.toString();
            out.getAttrNative = ga.includes('[native code]');
            out.getAttrStr = ga;
            // navigator.toJSON 之类的检测
            out.wdType = typeof navigator.webdriver;
            return out;
        }""")
        print(json.dumps(check, indent=2, ensure_ascii=False))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
