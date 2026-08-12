#!/usr/bin/env python3
"""
第三方指纹检测网站验证 — bot.incolumitas.com
"""
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
    print(f"Chrome: {chrome}")

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
        await asyncio.sleep(5)

        # 读取检测结果
        text = await page.evaluate("document.body ? document.body.innerText : ''")
        print("=" * 60)
        print("bot.incolumitas.com 检测结果:")
        print("=" * 60)
        print(text[:3000])

        # 保存截图
        shot = str(BASE_DIR / "qr" / "bot_test.png")
        try:
            await page.screenshot(path=shot, full_page=False)
            print(f"\n📸 截图: {shot}")
        except Exception:
            pass
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
