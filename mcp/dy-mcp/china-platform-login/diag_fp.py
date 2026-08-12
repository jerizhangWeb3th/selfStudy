#!/usr/bin/env python3
"""读取 fingerprintjs 的完整检测结果"""
import asyncio
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
        await asyncio.sleep(6)

        # 读取 #fp 元素（fingerprintjs 完整结果）
        fp = await page.evaluate("""() => {
            const el = document.getElementById('fp');
            return el ? el.innerText : '无 #fp';
        }""")
        print("=== fingerprintjs 结果 ===")
        print(fp[:2500])

        # 找 fpscanner 库源码（外部 JS）
        fpsrc = await page.evaluate("""() => {
            const scripts = Array.from(document.querySelectorAll('script'));
            const externals = [];
            scripts.forEach(s => {
                if (s.src) externals.push(s.src);
            });
            return externals;
        }""")
        print("\n=== 外部脚本 ===")
        for s in fpsrc:
            print(" ", s)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
