"""
==============================================================================
  social-auto-upload 浏览器启动配置（向后兼容层）
==============================================================================
  修改日期: 2026-05-26
  修改说明:
    原文件仅包含 6 个基础启动参数，缺少 WebRTC 禁用和指纹注入。
    现已重构，所有反检测逻辑集中在 utils/stealth_launcher.py。
    本文件保留向后兼容，实际逻辑委托给 stealth_launcher。

  如需完整反检测功能，请直接使用:
    from utils.stealth_launcher import (
        build_launch_kwargs,
        create_stealth_context,
        create_stealth_page,
    )
==============================================================================
"""

from utils.stealth_launcher import build_launch_kwargs as _build_kwargs


async def get_browser_options():
    """
    获取浏览器启动配置（向后兼容旧版 API）。

    返回可用于 playwright.chromium.launch(**options) 的参数字典。
    新代码推荐直接使用 build_launch_kwargs()。
    """
    return _build_kwargs(headless=True)
