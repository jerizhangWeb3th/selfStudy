#!/usr/bin/env python3
"""精细实验：route 注入脚本各标记生效情况"""
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
window.__A__ = 'A-value';
globalThis.__B__ = 'B-value';
try { document.title = 'INJ-OK'; } catch(e) {}
try { Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'}); } catch(e) {}
window.__C__ = window.__A__;
</script>"""
                body = body.replace("<head>", "<head>" + test, 1)
                await route.fulfill(status=resp.status, headers={**resp.headers, "content-type": "text/html; charset=utf-8"}, body=body)
            else:
                await route.fulfill(response=resp)

        await context.route("**/*", inject)
        page = await context.new_page()
        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        r = await page.evaluate("""() => ({
            A: window.__A__,
            B: window.__B__,
            C: window.__C__,
            platform: navigator.platform,
            title: document.title
        })""")
        print("=== 标记检查 ===")
        print(json.dumps(r, indent=2))

        # 打印注入后的完整 HTML 看 script 是否完整
        html = await page.evaluate("document.documentElement.outerHTML")
        idx = html.find("__A__")
        # 手动执行同样的代码（对比）
        r2 = await page.evaluate("""() => {
            window.__A__ = 'A-value';
            globalThis.__B__ = 'B-value';
            Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});
            return {A: window.__A__, B: window.__B__, platform: navigator.platform};
        }""")
        print("\n=== evaluate 手动执行 ===")
        print(json.dumps(r2, indent=2))

        # 检查 head 里 script 是否真的存在且完整
        script_html = await page.evaluate("""() => {
            const s = document.head ? document.head.querySelector('script') : null;
            return s ? s.textContent.substring(0, 150) : '无script';
        }""")
        print("\nhead 第一个 script:", script_html)

        print(f"\nHTML 里 script 位置: {idx}")
        if idx > 0:
            print("script 上下文:", html[max(0, idx-100):idx+200])
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
