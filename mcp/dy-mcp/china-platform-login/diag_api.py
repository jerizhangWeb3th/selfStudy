#!/usr/bin/env python3
"""抓取 bot.incolumitas.com 检测 API 的原始 JSON（含具体 FAIL 原因）"""
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
        page = await context.new_page()
        await page.goto("https://bot.incolumitas.com/", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(4)
        await page.evaluate(STEALTH_SCRIPT)
        await asyncio.sleep(3)

        # 抓取所有请求响应
        responses = []
        page.on("response", lambda r: responses.append(r) if "api" in r.url or "json" in r.url else None)

        # 等待检测完成（页面自动调用 API）
        await asyncio.sleep(8)

        # 主动调检测 API（页面已知端点）
        try:
            api_result = await page.evaluate("""async () => {
                try {
                    const r = await fetch('/api/bot-detection', {method: 'GET'});
                    const t = await r.text();
                    return t.substring(0, 5000);
                } catch(e) { return 'ERR:' + e.message; }
            }""")
            print("API 尝试:", api_result[:1000])
        except Exception as e:
            print(f"API 调用失败: {str(e)[:100]}")

        # 检查所有响应
        print(f"\n捕获响应 {len(responses)} 个")
        for r in responses[:15]:
            try:
                url = r.url
                if "api" in url or "json" in url or "detect" in url:
                    body = await r.text()
                    if body and len(body) > 50:
                        print(f"\n--- {url[:80]} ---")
                        print(body[:1500])
            except Exception:
                pass

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
