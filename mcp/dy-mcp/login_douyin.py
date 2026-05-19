#!/usr/bin/env python3
"""抖音登录脚本 - 自动保存 cookie"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).parent.resolve()
account_file = BASE_DIR / "account.json"

async def main():
    print("=" * 50)
    print("抖音登录脚本")
    print("=" * 50)
    print(f"将打开浏览器窗口...")
    print(f"登录后 cookie 会自动保存到: {account_file}")
    print("登录完成后，关闭浏览器窗口即可")
    print("=" * 50)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            executable_path="/Users/link04/Library/Caches/ms-playwright/chromium-1124/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://creator.douyin.com/")
        print("浏览器已打开，请在页面中扫码登录抖音...")
        
        # 等待浏览器关闭
        await context.storage_state(path=account_file)
        print(f"✅ Cookie 已保存到: {account_file}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
