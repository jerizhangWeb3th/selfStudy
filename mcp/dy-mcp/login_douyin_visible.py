#!/usr/bin/env python3
"""抖音登录脚本 - 等待手动登录"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).parent.resolve()
account_file = BASE_DIR / "account.json"

async def main():
    print("=" * 50)
    print("抖音登录脚本")
    print("=" * 50)
    print("将打开浏览器窗口，请在页面扫码登录抖音")
    print("登录成功后会自动保存 Cookie")
    print("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            executable_path="/Users/link04/Library/Caches/ms-playwright/chromium-1124/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
        )
        context = await browser.new_context(viewport={"width": 1200, "height": 800})
        page = await context.new_page()

        await page.goto("https://creator.douyin.com/", timeout=30000)
        print("浏览器已打开，请在页面扫码登录抖音...")

        # 等待登录成功：检测到用户名元素或 URL 变化
        try:
            # 等待 URL 变成创作者后台（说明登录成功）
            await page.wait_for_url("**/creator-micro/**", timeout=0)  # 不阻塞
        except:
            pass

        # 轮询检测是否已登录（通过检查页面是否有用户信息）
        login_success = False
        for _ in range(120):  # 最多等120秒
            await asyncio.sleep(1)
            try:
                # 检查是否跳转到登录后的页面
                url = page.url
                if "creator.douyin.com/creator-micro" in url:
                    print("✅ 检测到登录成功！")
                    login_success = True
                    break
                # 也检查页面中是否有退出按钮等登录状态的元素
                logout_btn = await page.query_selector('text=退出')
                if logout_btn:
                    print("✅ 检测到已登录状态！")
                    login_success = True
                    break
            except:
                pass
            print(".", end="", flush=True)

        if login_success:
            await context.storage_state(path=account_file)
            print(f"\n✅ Cookie 已保存到: {account_file}")
        else:
            print("\n⚠️ 等待超时，请手动关闭浏览器窗口")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
