#!/usr/bin/env python3
"""定位 add_init_script 失效原因"""
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

        # 测试1: 极简 init_script
        await context.add_init_script("window.__MINI_TEST__ = 'hello-123';")
        page = await context.new_page()
        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        mini = await page.evaluate("window.__MINI_TEST__")
        print(f"测试1 极简 init_script: {mini!r} ({'✅生效' if mini == 'hello-123' else '❌失效'})")

        # 测试2: 极简 defineProperty
        await context.add_init_script("Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});")
        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        p1 = await page.evaluate("navigator.platform")
        print(f"测试2 defineProperty init_script: {p1!r} ({'✅生效' if p1 == 'MacIntel' else '❌失效'})")

        # 测试3: 完整 STEALTH_SCRIPT via context.add_init_script
        await context.add_init_script(STEALTH_SCRIPT)
        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        p2 = await page.evaluate("navigator.platform")
        print(f"测试3 完整 stealth via context: {p2!r} ({'✅生效' if p2 == 'MacIntel' else '❌失效'})")

        # 测试4: page.add_init_script（页面级）
        page2 = await context.new_page()
        await page2.add_init_script(STEALTH_SCRIPT)
        await page2.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        p3 = await page2.evaluate("navigator.platform")
        print(f"测试4 完整 stealth via page: {p3!r} ({'✅生效' if p3 == 'MacIntel' else '❌失效'})")

        # 测试5: page.evaluate（验证基础路径没问题）
        await page.evaluate(STEALTH_SCRIPT)
        p4 = await page.evaluate("navigator.platform")
        print(f"测试5 page.evaluate: {p4!r} ({'✅生效' if p4 == 'MacIntel' else '❌失效'})")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
