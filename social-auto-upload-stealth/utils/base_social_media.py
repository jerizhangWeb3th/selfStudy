"""
==============================================================================
  social-auto-upload 通用配置模块
==============================================================================
  修改日期: 2026-05-26
  修改说明:
    - set_init_script() 增强：新增 WebRTC API 删除脚本注入
    - 建议新代码使用 utils.stealth_launcher.create_stealth_context()
      获得完整的 L2+L3+L4 分层反检测保护
==============================================================================
"""

from pathlib import Path
from typing import List

from conf import BASE_DIR

SOCIAL_MEDIA_DOUYIN = "douyin"
SOCIAL_MEDIA_TENCENT = "tencent"
SOCIAL_MEDIA_TIKTOK = "tiktok"
SOCIAL_MEDIA_BILIBILI = "bilibili"
SOCIAL_MEDIA_KUAISHOU = "kuaishou"


def get_supported_social_media() -> List[str]:
    return [SOCIAL_MEDIA_DOUYIN, SOCIAL_MEDIA_TENCENT, SOCIAL_MEDIA_TIKTOK, SOCIAL_MEDIA_KUAISHOU]


def get_cli_action() -> List[str]:
    return ["upload", "login", "watch"]


async def set_init_script(context):
    """
    为浏览器上下文注入反检测脚本。

    修改说明（2026-05-26）：
      原版只注入 stealth.min.js，缺少 WebRTC 删除。
      现在追加注入 WebRTC API 删除脚本，防止 WAF 通过
      RTCPeerConnection 等 API 探测无头浏览器环境。

    注入顺序：
      1. stealth.min.js（屏蔽 webdriver、chrome.runtime、plugins）
      2. WebRTC API 删除（delete RTCPeerConnection / RTCIceCandidate 等）

    如需完整的 L1-L4 反检测（启动参数 + 指纹注入 + init_script），
    请使用 utils.stealth_launcher.create_stealth_context()。
    """
    from utils.stealth_launcher import WEBRTC_API_DELETION_SCRIPT

    # 1. 加载 stealth.min.js（原项目已有）
    stealth_js_path = Path(BASE_DIR / "utils/stealth.min.js")
    await context.add_init_script(path=stealth_js_path)

    # 2. 注入 WebRTC API 删除脚本（新增）
    await context.add_init_script(WEBRTC_API_DELETION_SCRIPT)

    return context
