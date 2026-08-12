#!/usr/bin/env python3
"""诊断 patchright 1.61.2 add_init_script 注入链路"""
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

import importlib.metadata as md
print("patchright:", md.version("patchright"))

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

        # 监听所有请求看 inject route 是否触发
        reqs = []
        context.on("request", lambda r: reqs.append(r.url) if "patchright" in r.url or "internal" in r.url else None)

        await context.add_init_script("window.__MINI_TEST__ = 'hello-123';")
        page = await context.new_page()
        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        mini = await page.evaluate("window.__MINI_TEST__")
        print(f"init_script 结果: {mini!r} ({'✅' if mini == 'hello-123' else '❌'})")

        # 检查特殊请求
        print(f"特殊请求 ({len(reqs)}):", reqs[:5] if reqs else "无")

        # 检查页面 HTML 是否含注入标记
        html = await page.evaluate("document.documentElement.outerHTML")
        has_mini = "MINI_TEST" in html or "hello-123" in html
        print(f"HTML 含注入脚本: {has_mini}")

        # 查看 head 里的 script
        scripts = await page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('script').forEach((s, i) => {
                out.push({i, src: s.src || '(inline)', len: (s.textContent||'').length, head: (s.textContent||'').substring(0, 60)});
            });
            return out;
        }""")
        print(f"页面 scripts ({len(scripts)}):")
        for s in scripts:
            print("  ", s)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
