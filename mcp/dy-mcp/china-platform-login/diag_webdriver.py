#!/usr/bin/env python3
"""读取 bot.incolumitas.com 的 fpscanner WEBDRIVER 检测源码"""
import asyncio
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
        await page.goto("https://bot.incolumitas.com/", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(4)
        await page.evaluate(STEALTH_SCRIPT)
        await asyncio.sleep(2)

        # 1. 查看 navigator.webdriver 的 descriptor
        desc = await page.evaluate("""() => {
            const d = Object.getOwnPropertyDescriptor(navigator, 'webdriver');
            return d ? JSON.stringify(d) : '无';
        }""")
        print("navigator.webdriver descriptor:", desc)

        # 2. 找页面里 fpscanner 检测代码
        scripts = await page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('script').forEach(s => {
                const t = s.textContent || '';
                if (t.includes('WEBDRIVER') && t.includes('fpscanner') || t.includes('fpscanner')) {
                    out.push(t.substring(0, 3000));
                }
            });
            return out;
        }""")
        for s in scripts:
            if "WEBDRIVER" in s:
                idx = s.find("WEBDRIVER")
                print("\n=== fpscanner 检测源码 (WEBDRIVER 附近) ===")
                print(s[max(0, idx-800):idx+400])
                break
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
