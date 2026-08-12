#!/usr/bin/env python3
"""测试 route 拦截 HTML 注入 stealth 到 <head>"""
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

        # ★ route 拦截：HTML 响应注入 stealth 到 <head>
        injected_count = [0]
        async def inject_stealth(route):
            resp = await route.fetch()
            print(f"  [route] {route.request.url[:60]} ct={resp.headers.get('content-type','')[:30]}")
            content_type = resp.headers.get("content-type", "")
            if "text/html" in content_type:
                body = await resp.text()
                print(f"  [html] len={len(body)} head存在={'<head>' in body.lower()}")
                script_tag = "<script>%s</script>" % STEALTH_SCRIPT
                if "<head>" in body.lower():
                    body = body.replace("<head>", "<head>" + script_tag, 1)
                else:
                    body = script_tag + body
                injected_count[0] += 1
                await route.fulfill(
                    status=resp.status,
                    headers={**resp.headers, "content-type": "text/html; charset=utf-8"},
                    body=body,
                )
            else:
                await route.fulfill(response=resp)

        await context.route("**/*", inject_stealth)
        page = await context.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(f"PAGEERROR: {e}"))
        page.on("console", lambda m: errs.append(f"[{m.type}] {m.text[:150]}") if m.type == "error" else None)
        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

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
        print(f"注入 HTML 数: {injected_count[0]}")
        print(f"console/pageerror ({len(errs)}):")
        for e in errs[:10]:
            print("  ", e)
        # 检查页面里是否有我们的 stealth
        has_stealth = await page.evaluate("document.documentElement.outerHTML.includes('Stealth')")
        print(f"页面含 stealth 标记: {has_stealth}")
        head_html = await page.evaluate("document.head ? document.head.innerHTML.substring(0, 300) : '无head'")
        print(f"head 开头: {head_html[:200]}")
        print("=== route 注入效果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
