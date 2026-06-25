"""
==============================================================================
  social-auto-upload 配置文件
==============================================================================
  修改日期: 2026-05-26
  修改说明:
    - 新增 STEALTH_DISABLE_WEBRTC: WebRTC 禁用开关
    - 新增 STEALTH_USE_BROWSERFORGE: browserforge 指纹注入开关
    - 新增 STEALTH_FINGERPRINT_OPTIONS: 指纹约束选项
==============================================================================
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
XHS_SERVER = "http://127.0.0.1:11901"  # only used by xhs-related flows
LOCAL_CHROME_PATH = ""  # optional, e.g. C:/Program Files/Google/Chrome/Application/chrome.exe
LOCAL_CHROME_HEADLESS = True  # default headless behavior for uploader/examples
DEBUG_MODE = True  # default debug behavior

# ── 反检测配置（2026-05-26 新增） ──────────────────────────────────────────

# 是否禁用 WebRTC（强烈建议保持 True）
# WebRTC 会泄露本地 IP，是 WAF 探测无头浏览器的常见入口
STEALTH_DISABLE_WEBRTC = True

# 是否使用 browserforge 注入真实浏览器指纹（需 pip install browserforge）
# browserforge 自动注入 navigator、screen、fonts、WebGL 等完整指纹
# 未安装时自动降级为仅使用启动参数 + stealth.min.js
STEALTH_USE_BROWSERFORGE = True

# browserforge 指纹约束选项（可选）
# 不配置则随机生成。可选字段: screen, headers, navigator, videoCard 等
# 参考: https://github.com/daijro/browserforge
STEALTH_FINGERPRINT_OPTIONS = {
    # 'screen': {'max_width': 1920, 'max_height': 1080},
}
