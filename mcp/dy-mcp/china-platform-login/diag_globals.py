#!/usr/bin/env python3
"""检查 fpscanner 检测的全局变量是否残留"""
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

# fpscanner 检测的变量列表
VARS = [
    "__webdriver_evaluate", "__selenium_evaluate", "__lastWatirAlert",
    "__webdriver_script_fn", "__driver_evaluate", "__webdriver_script_func",
    "__fxdriver_evaluate", "__driver_unwrapped", "__webdriver_unwrapped",
    "__webdriver_wrapper", "__selenium_unwrapped", "__fxdriver_unwrapped",
    "_Selenium_IDE_Recorder", "_selenium", "calledSelenium",
    "_WEBDRIVER_ELEM_CACHE", "ChromeDriverw", "webdriverCommand",
    "__webdriverFunc", "__$webdriverAsyncExecutor", "domAutomation",
    "domAutomationController", "webdriver", "cdc_", "$cdc_", "$chrome_",
    "callSelenium", "__webdriver_wrapper",
]


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
        await page.goto("https://creator.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)
        await page.evaluate(STEALTH_SCRIPT)
        await asyncio.sleep(2)

        # 检查每个变量
        result = await page.evaluate(f"""() => {{
            const vars = {json_dumps(VARS)};
            const found = [];
            const wKeys = Object.keys(window);
            for (const v of vars) {{
                // 直接属性
                if (v in window) found.push('direct:' + v);
                // 前缀匹配 cdc_
                if (v.startsWith('$cdc_') || v.startsWith('$chrome_')) {{
                    const match = wKeys.filter(k => k.includes('cdc_') || k.includes('chrome_'));
                    if (match.length) found.push('prefix:' + match.join(','));
                }}
            }}
            return found;
        }}""")
        print("残留变量:", result if result else "✅ 无残留")

        # 检查 document 上的属性
        doc_result = await page.evaluate(f"""() => {{
            const vars = {json_dumps(VARS)};
            const found = [];
            for (const v of vars) {{
                if (v in document) found.push(v);
            }}
            return found;
        }}""")
        print("document 残留:", doc_result if doc_result else "✅ 无残留")


        # 深度检查：getAttribute 途径
        attr_result = await page.evaluate("""() => {
            const out = {};
            out.htmlAttr = document.documentElement.getAttribute('webdriver');
            out.bodyAttr = document.body ? document.body.getAttribute('webdriver') : null;
            out.descNavigator = JSON.stringify(Object.getOwnPropertyDescriptor(navigator, 'webdriver'));
            // 原型链上的 webdriver
            out.protoWebdriver = navigator.__proto__.webdriver;
            // 检查 iframe
            out.frames = window.frames.length;
            // 检查所有 element 的 webdriver 属性
            const els = document.querySelectorAll('[webdriver]');
            out.elementsWithAttr = els.length;
            // performance entries 里的异常
            out.resourceCount = 'skip';
            return out;
        }""")
        print("\n深度检查:", attr_result)
        await browser.close()

import json
json_dumps = json.dumps

if __name__ == "__main__":
    asyncio.run(main())
