#!/usr/bin/env python3
"""检查 fpscanner WEBDRIVER 检测的具体失败项（在 bot 页面加载时）"""
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

from stealth_core import MAC_UA, LAUNCH_ARGS, STEALTH_SCRIPT, find_chrome, ensure_display, goto_with_stealth  # noqa: E402

# fpscanner 检测的变量列表（从源码抓取）
DOC_KEYS = [
    "__webdriver_evaluate", "__selenium_evaluate", "__webdriver_script_function",
    "__webdriver_script_func", "__webdriver_script_fn", "__fxdriver_evaluate",
    "__driver_unwrapped", "__webdriver_unwrapped", "__driver_evaluate",
    "__selenium_unwrapped", "__fxdriver_unwrapped", "webdriver",
    "_Selenium_IDE_Recorder", "_selenium", "calledSelenium",
    "_WEBDRIVER_ELEM_CACHE", "ChromeDriverw", "driver-evaluate",
    "webdriver-evaluate", "selenium-evaluate", "webdriverCommand",
    "webdriver-evaluate-response", "__webdriverFunc", "__webdriver_script_fn",
    "__$webdriverAsyncExecutor", "__lastWatirAlert", "__lastWatirConfirm",
    "__lastWatirPrompt", "$chrome_asyncScriptInfo", "$cdc_asdjflasutopfhvcZLmcfl_",
]
WIN_KEYS = ["_phantom", "__nightmare", "_selenium", "callPhantom", "callSelenium", "_Selenium_IDE_Recorder"]


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
        await asyncio.sleep(5)

        # 模拟 fpscanner 检测逻辑
        result = await page.evaluate(f"""() => {{
            const docKeys = {json.dumps(DOC_KEYS)};
            const winKeys = {json.dumps(WIN_KEYS)};
            const out = {{}};
            // window 检测
            const winFound = [];
            for (const k of winKeys) {{
                if (window[k]) winFound.push(k);
            }}
            out.windowFound = winFound;
            // document 检测
            const docFound = [];
            for (const k of docKeys) {{
                if (window['document'][k]) docFound.push(k);
            }}
            out.documentFound = docFound;
            // $[a-z]dc_ 模式
            const ddc = [];
            for (const k of Object.keys(document)) {{
                if (k.match(/\\$[a-z]dc_/) && document[k] && document[k]['cache_']) ddc.push(k);
            }}
            out.dollarDc = ddc;
            // external
            out.external = window.external ? String(window.external).substring(0, 80) : 'null';
            out.externalSequentum = window.external && window.external.toString && window.external.toString().indexOf('Sequentum') != -1;
            // getAttribute
            out.htmlSelenium = document.documentElement.getAttribute('selenium');
            out.htmlWebdriver = document.documentElement.getAttribute('webdriver');
            out.htmlDriver = document.documentElement.getAttribute('driver');
            return out;
        }}""")
        print("=== fpscanner 检测模拟 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
