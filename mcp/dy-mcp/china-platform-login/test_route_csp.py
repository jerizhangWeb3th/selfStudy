#!/usr/bin/env python3
"""route 注入 stealth + 放宽 CSP 响应头（抖音场景）"""
import asyncio
import json
import os
import re
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

        injected = [0]
        async def inject_stealth(route):
            resp = await route.fetch()
            ct = resp.headers.get("content-type", "")
            headers = {k: v for k, v in resp.headers.items()}
            # 放宽 CSP：允许 inline script（关键！抖音 CSP 阻止内联脚本）
            if "content-security-policy" in headers:
                old = headers["content-security-policy"]
                # 把 script-src 允许 unsafe-inline
                new = re.sub(r"script-src[^;]*", r"script-src 'unsafe-inline' 'unsafe-eval' * data: blob:;", old)
                headers["content-security-policy"] = new
                print(f"  [csp] 已放宽: {old[:40]}... -> {new[:40]}...")
            if "text/html" in ct:
                body = await resp.text()
                script_tag = "<script>%s</script>" % STEALTH_SCRIPT
                if "<head>" in body:
                    body = body.replace("<head>", "<head>" + script_tag, 1)
                else:
                    body = script_tag + body
                injected[0] += 1
                await route.fulfill(status=resp.status, headers=headers, body=body)
            else:
                await route.fulfill(response=resp)

        await context.route("**/*", inject_stealth)
        page = await context.new_page()
        await page.goto("https://creator.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(6)

        result = await page.evaluate("""() => ({
            platform: navigator.platform,
            chromeApp: !!(window.chrome && window.chrome.app),
            uaDataPlatform: (navigator.userAgentData || {}).platform,
            webdriver: String(navigator.webdriver),
            pluginsLen: navigator.plugins.length
        })""")
        print(f"注入 HTML 数: {injected[0]}")
        print("=== 抖音页面 route+CSP 注入效果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
