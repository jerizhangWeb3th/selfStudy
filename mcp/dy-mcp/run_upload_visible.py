#!/usr/bin/env python3
"""可见浏览器上传视频到抖音"""
import asyncio
import sys
import os
from pathlib import Path

# 添加 dy-mcp 路径
sys.path.insert(0, str(Path(__file__).parent))

from server_streamable_http import DouYinVideo, generate_schedule_time_next_day, BASE_DIR
from datetime import datetime

# 视频文件夹
VIDEO_DIR = Path("/Users/link04/dy-mcp/upload_test")
account_file = Path(BASE_DIR) / "account.json"

# 获取 mp4 文件
files = list(VIDEO_DIR.glob("*.mp4"))
if not files:
    print("文件夹中没有 MP4 文件")
    sys.exit(1)

video_path = files[0]
title = "Hermes AI 自动发布测试"
tags = ["AI", "测试", "抖音"]
publish_date = generate_schedule_time_next_day(1, 1, daily_times=[16])[0]

print(f"准备上传视频: {video_path}")
print(f"标题: {title}")
print(f"标签: {tags}")
print(f"发布时间: {publish_date}")
print(f"账户文件: {account_file}")
print(f"账户文件存在: {account_file.exists()}")

async def main():
    app = DouYinVideo(
        title=title,
        file_path=str(video_path),
        tags=tags,
        publish_date=publish_date,
        account_file=str(account_file)
    )
    await app.main()
    print("上传完成!")

asyncio.run(main())
