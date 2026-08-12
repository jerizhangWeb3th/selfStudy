#!/usr/bin/env python3
"""最小实验：route 注入的 script 是否真的执行"""
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

        async def inject(route):
            resp = await route.fetch()
            ct = resp.headers.get("content-type", "")
            if "text/html" in ct:
                body = await resp.text()
                test = """<script>
window.__INJECTED__ = 'yes';
Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});
try { document.title = 'INJ-OK'; } catch(e) {}
</script>"""
                if "<head>" in body:
                    body = body.replace("<head>", "<head>" + test, 1)
                else:
                    body = test + body
                await route.fulfill(status=resp.status, headers={**resp.headers, "content-type": "text/html; charset=utf-8"}, body=body)
            else:
                await route.fulfill(response=resp)

        await context.route("**/*", inject)
        page = await context.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(f"PAGEERROR: {e}"))
        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        r = await page.evaluate("""() => ({
            injected: window.__INJECTED__,
            platform: navigator.platform,
            title: document.title
        })""")
        print("=== 最小实验 ===")
        print(json.dumps(r, indent=2))
        print("errors:", errs[:5] if errs else "无")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
