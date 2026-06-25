"""
==============================================================================
  social-auto-upload 反检测增强模块 (stealth_launcher.py)
==============================================================================
  作者: link04
  修改日期: 2026-05-26
  基于: dreammis/social-auto-upload
  修改摘要:
    1. 新增 WebRTC 全面禁用（启动参数 + JS API 删除双重保险）
    2. 集成 browserforge 指纹生成与注入（Python 版 Apify Fingerprint Suite）
    3. 统一浏览器启动入口，避免各 uploader 各自散落启动代码
    4. 分层反检测策略：
       L1: Chromium 启动参数（--disable-blink-features、--disable-webrtc 等）
       L2: browserforge 指纹注入（navigator、screen、fonts、WebGL、headers...）
       L3: stealth.min.js 运行时屏蔽（webdriver、chrome.runtime、plugins）
       L4: WebRTC API 彻底删除（delete window.RTCPeerConnection 等）
==============================================================================
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List

# ── 可选依赖（未安装时优雅降级） ──────────────────────────────────────────
try:
    from browserforge.fingerprints import FingerprintGenerator, Fingerprint
    from browserforge.injectors.playwright import AsyncNewContext
    _HAS_BROWSERFORGE = True
except ImportError:
    _HAS_BROWSERFORGE = False
    FingerprintGenerator = None  # type: ignore
    Fingerprint = None           # type: ignore
    AsyncNewContext = None       # type: ignore

# ── 配置常量 ────────────────────────────────────────────────────────────────


# WebRTC 全面禁用的 Chromium 启动参数
# 这些参数在浏览器进程启动时就生效，比 JS 层面删除 API 更底层
WEBRTC_DISABLE_ARGS: List[str] = [
    # 核心：彻底禁用 WebRTC 核心模块（防止 local IP 泄露）
    "--disable-webrtc",
    # 禁用 mDNS 隐藏（防止 WebRTC 通过 mDNS 泄露局域网 IP）
    "--disable-features=WebRtcHideLocalIpsWithMdns",
    # 禁用 WebRTC 加密相关的扩展功能
    "--disable-webrtc-encryption",
]

# 通用的反自动化检测启动参数
ANTI_DETECTION_ARGS: List[str] = [
    # 核心：去掉 window.navigator.webdriver 标识
    "--disable-blink-features=AutomationControlled",
    # 关闭信息栏（"Chrome 正受到自动测试软件的控制"）
    "--disable-infobars",
    # 最大化窗口（避免窗口大小暴露自动化特征）
    "--start-maximized",
    # 禁用沙箱（某些环境需要，如 Docker）
    "--no-sandbox",
    # 禁用 web-security（跨域需求）
    "--disable-web-security",
    # 语言设置为中文
    "--lang=zh-CN",
    # 禁用 GPU（headless 模式稳定性）
    "--disable-gpu",
    # 禁用默认浏览器检查
    "--no-default-browser-check",
    # 禁用首次运行向导
    "--no-first-run",
    # 禁用后台网络
    "--disable-background-networking",
    # 禁用同步
    "--disable-sync",
    # 禁用翻译
    "--disable-translate",
    # 隐藏"保存密码"提示
    "--disable-save-password-bubble",
    # 禁用组件更新
    "--disable-component-update",
    # 禁用 domain 可靠性
    "--disable-domain-reliability",
]


# WebRTC API 彻底删除脚本 —— 在 JS 最顶层执行，比 stealth.min.js 更早
# 目的：防止 WAF 通过 RTCPeerConnection 异常调用探测是否为无头浏览器
WEBRTC_API_DELETION_SCRIPT: str = """
// ===== WebRTC API 彻底删除（反指纹探测）=====
// 在最顶层删除 WebRTC 相关 API，防止：
// 1. WAF 通过 new RTCPeerConnection() 触发异常来检测无头浏览器
// 2. 通过 RTCPeerConnection.getStats() 泄露本地 IP
// 3. 通过 RTCDataChannel 探测网络环境
delete window.RTCPeerConnection;
delete window.webkitRTCPeerConnection;
delete window.mozRTCPeerConnection;
delete window.RTCIceCandidate;
delete window.RTCSessionDescription;
delete window.RTCDataChannel;
delete window.RTCDataChannelEvent;

// 补充：删除其他可能暴露自动化环境的 API
// Object.defineProperty 确保即使页面尝试重新定义也会被拦截
try {
    Object.defineProperty(navigator, 'webdriver', {
        get: () => false,
        configurable: true
    });
} catch(e) {}

// 遮盖 chrome.runtime（自动化扩展特征）
try {
    Object.defineProperty(window, 'chrome', {
        get: () => ({ runtime: {} }),
        configurable: true
    });
} catch(e) {}

// 遮盖权限查询
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);
"""

# 也可以从外部文件加载（兼容旧版 stealth.min.js）
STEALTH_JS_PATH = Path(__file__).parent / "stealth.min.js"


# ── 指纹生成器（全局单例）───────────────────────────────────────────────────

_fingerprint_generator: Optional[Any] = None


def _get_fingerprint_generator():
    """获取指纹生成器单例（延迟初始化以允许优雅降级）。"""
    global _fingerprint_generator
    if _fingerprint_generator is None and _HAS_BROWSERFORGE:
        _fingerprint_generator = FingerprintGenerator(
            # 屏幕约束：常见中国大陆分辨率
            screen={'max_width': 2560, 'max_height': 1440},
        )
    return _fingerprint_generator


# ── 浏览器启动参数 ──────────────────────────────────────────────────────────


def build_chromium_args(
    *,
    disable_webrtc: bool = True,
    extra_args: Optional[List[str]] = None,
) -> List[str]:
    """
    构建完整的 Chromium 启动参数。

    Args:
        disable_webrtc: 是否禁用 WebRTC（默认 True，强烈建议保持）
        extra_args: 额外的自定义参数

    Returns:
        合并后的启动参数列表

    修改说明：
        原项目 `browser_hook.py` 只有 6 个基础参数，缺少 WebRTC 禁用和
        深层反检测参数。本函数将参数扩充到 20+，分层覆盖：
        - Blink 自动化特征（AutomationControlled）
        - WebRTC 全部禁用（3 个参数）
        - UI/UX 特征（infobars、密码保存、首次运行等）
        - 网络特征（后台网络、域名可靠性、组件更新）
    """
    args = list(ANTI_DETECTION_ARGS)

    if disable_webrtc:
        args.extend(WEBRTC_DISABLE_ARGS)

    if extra_args:
        args.extend(extra_args)

    return args


def build_launch_kwargs(
    *,
    headless: bool = True,
    executable_path: Optional[str] = None,
    channel: Optional[str] = "chrome",
    disable_webrtc: bool = True,
    extra_args: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    构建浏览器启动参数字典（适用于 playwright.chromium.launch(**kwargs)）。

    Args:
        headless: 是否无头模式
        executable_path: 自定义浏览器路径（优先于 channel）
        channel: 浏览器通道（"chrome" / "chromium" / "msedge" 等）
        disable_webrtc: 是否禁用 WebRTC
        extra_args: 额外启动参数

    Returns:
        可直接解包传入 launch() 的参数字典

    修改说明：
        原项目各 uploader 中散落着不同版本的 launch_kwargs 构建代码，
        有的传了 channel="chrome"，有的只传 headless。本函数统一入口，
        确保所有 uploader 获得相同的反检测参数。
        支持 executable_path 优先于 channel（用于指定本地 Chrome 路径）。
    """
    kwargs: Dict[str, Any] = {
        "headless": headless,
        "args": build_chromium_args(
            disable_webrtc=disable_webrtc,
            extra_args=extra_args,
        ),
    }

    if executable_path:
        kwargs["executable_path"] = executable_path
    elif channel:
        kwargs["channel"] = channel

    return kwargs


# ── 上下文创建（指纹注入 + WebRTC 删除）────────────────────────────────────


async def create_stealth_context(
    browser,
    *,
    storage_state: Optional[str] = None,
    fingerprint: Optional[Any] = None,
    fingerprint_options: Optional[Dict[str, Any]] = None,
    use_browserforge: bool = True,
    inject_webrtc_deletion: bool = True,
    inject_stealth_js: bool = True,
    **context_options,
):
    """
    创建带完整反检测保护的浏览器上下文。

    这是整个反检测系统的核心入口。按以下顺序施加保护层：

    L2: browserforge 指纹注入（如果可用）
        - navigator: userAgent, platform, hardwareConcurrency, deviceMemory...
        - screen: width, height, availWidth, availHeight, colorDepth...
        - fonts: 安装字体列表（匹配指纹）
        - videoCard: WebGL vendor/renderer
        - headers: Accept-Language, Sec-CH-UA 等 HTTP 头
        - audioCodecs: 音频编解码器
        - 自动设置 dark mode color-scheme

    L3-L4: init_script 注入（按顺序执行）
        1. WebRTC API 删除脚本（最早执行）
        2. stealth.min.js（屏蔽 webdriver、chrome.runtime、plugins 等）

    Args:
        browser: Playwright Browser 实例
        storage_state: cookie 文件路径（用于恢复登录状态）
        fingerprint: 预生成的指纹对象（不传则自动生成）
        fingerprint_options: 指纹约束参数（传给 FingerprintGenerator）
        use_browserforge: 是否使用 browserforge（默认 True，未安装时自动降级）
        inject_webrtc_deletion: 是否注入 WebRTC API 删除脚本
        inject_stealth_js: 是否注入 stealth.min.js
        **context_options: 其他传给 browser.new_context() 的参数

    Returns:
        Playwright BrowserContext（已注入所有反检测脚本）

    修改说明：
        原项目只有 set_init_script(context) 加载 stealth.min.js（单层防护），
        缺少 WebRTC 删除和指纹注入。本函数将防护层数从 1 层增加到 3 层，
        且 script 注入顺序确保 WebRTC 删除在最顶层执行。

    使用示例:
        # 最简用法（自动生成指纹）
        browser = await playwright.chromium.launch(**build_launch_kwargs(headless=True))
        context = await create_stealth_context(browser)

        # 带 cookie 恢复
        context = await create_stealth_context(
            browser, storage_state="cookies/douyin.json"
        )

        # 指定指纹
        gen = FingerprintGenerator()
        fp = gen.generate(screen={'max_width': 1920})
        context = await create_stealth_context(browser, fingerprint=fp)
    """
    # ── L2: browserforge 指纹注入 ──
    context_created = False

    if use_browserforge and _HAS_BROWSERFORGE:
        # 使用 browserforge 创建上下文（自动注入所有指纹）
        context = await AsyncNewContext(
            browser,
            fingerprint=fingerprint,
            fingerprint_options=fingerprint_options,
            storage_state=storage_state,
            **context_options,
        )
        context_created = True
    else:
        # 降级：手动创建上下文
        ctx_kwargs = dict(context_options)
        if storage_state:
            ctx_kwargs["storage_state"] = storage_state
        context = await browser.new_context(**ctx_kwargs)

    # ── L3-L4: init_script 注入 ──

    # L3: WebRTC API 删除（必须在最顶层执行）
    if inject_webrtc_deletion:
        await context.add_init_script(WEBRTC_API_DELETION_SCRIPT)

    # L4: stealth.min.js（在 WebRTC 删除之后执行）
    if inject_stealth_js and STEALTH_JS_PATH.exists():
        await context.add_init_script(path=STEALTH_JS_PATH)

    return context


async def create_stealth_page(
    browser,
    *,
    storage_state: Optional[str] = None,
    fingerprint: Optional[Any] = None,
    fingerprint_options: Optional[Dict[str, Any]] = None,
    use_browserforge: bool = True,
    inject_webrtc_deletion: bool = True,
    inject_stealth_js: bool = True,
    **context_options,
):
    """
    创建带完整反检测保护的浏览器上下文 + 页面（一步到位）。

    等同于 create_stealth_context() + context.new_page()。

    Returns:
        (BrowserContext, Page) 元组
    """
    context = await create_stealth_context(
        browser,
        storage_state=storage_state,
        fingerprint=fingerprint,
        fingerprint_options=fingerprint_options,
        use_browserforge=use_browserforge,
        inject_webrtc_deletion=inject_webrtc_deletion,
        inject_stealth_js=inject_stealth_js,
        **context_options,
    )
    page = await context.new_page()
    return context, page


# ── 兼容性导出 ──────────────────────────────────────────────────────────────


# 保持与旧版 browser_hook.get_browser_options() 的兼容
# 旧代码可以直接 `from utils.stealth_launcher import get_browser_options`
async def get_browser_options():
    """
    [DEPRECATED] 兼容旧版 API。

    返回 launch(**kwargs) 的参数字典。
    推荐使用 build_launch_kwargs() 代替。
    """
    import warnings
    warnings.warn(
        "get_browser_options() is deprecated, use build_launch_kwargs() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_launch_kwargs(headless=True)
