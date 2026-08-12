#!/usr/bin/env python3
"""从页面抓 fpscanner 完整检测函数"""
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

        # 找页面所有 script 里含 fpscanner 的
        found = await page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('script').forEach((s, i) => {
                const t = s.textContent || '';
                if (t.includes('fpscanner') || (t.includes('WEBDRIVER') && t.includes('FINGERPRINT'))) {
                    out.push({i, len: t.length, head: t.substring(0, 200)});
                }
            });
            return out;
        }""")
        print("含 fpscanner 的 script:", json_dumps(found))

        # 抓完整源码存文件
        full = await page.evaluate("""() => {
            const parts = [];
            document.querySelectorAll('script').forEach((s, i) => {
                const t = s.textContent || '';
                if (t.includes('fpscanner') || t.includes('WEBDRIVER')) {
                    parts.push(`/* script ${i} len=${t.length} */\\n` + t);
                }
            });
            return parts.join('\\n\\n');
        }""")
        with open("/tmp/fpscanner_src.js", "w") as f:
            f.write(full)
        print(f"\n源码已保存: /tmp/fpscanner_src.js ({len(full)} 字符)")

        # 直接提取 WEBDRIVER 检测函数体
        idx = full.find("WEBDRIVER")
        while idx != -1 and idx < len(full):
            # 找它前面的函数定义
            seg_start = max(0, idx - 3000)
            seg = full[seg_start:idx + 100]
            if "FAIL" in seg:
                print(f"\n=== WEBDRIVER 检测附近 ({idx}) ===")
                print(seg[-3000:])
                break
            idx = full.find("WEBDRIVER", idx + 1)
        await browser.close()


import json
json_dumps = json.dumps

if __name__ == "__main__":
    asyncio.run(main())
