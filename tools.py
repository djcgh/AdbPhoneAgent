"""ADB Tools - Agent 可用的所有工具"""

import subprocess
import base64
import xml.etree.ElementTree as ET
from agents import function_tool
from config import ADB_PATH


def _run(cmd: str, timeout: int = 15) -> str:
    """执行 adb 命令"""
    try:
        r = subprocess.run(
            f"{ADB_PATH} {cmd}",
            shell=True, capture_output=True, text=True, timeout=timeout
        )
        output = r.stdout.strip()
        if r.stderr.strip():
            output += f"\n[stderr] {r.stderr.strip()}"
        return output or "(无输出)"
    except subprocess.TimeoutExpired:
        return "[超时]"
    except Exception as e:
        return f"[错误] {e}"


# ---- 核心执行工具 ----

@function_tool
def adb_shell(command: str) -> str:
    """在手机上执行任意 adb shell 命令。你可以使用所有 Android shell 命令，包括但不限于：

    【触控操作】
    - input tap x y — 点击坐标
    - input swipe x1 y1 x2 y2 duration — 滑动
    - input text "文字" — 输入文字(仅英文和数字)
    - input keyevent KEYCODE_BACK — 按返回键
    - input keyevent KEYCODE_HOME — 按主页键
    - input keyevent KEYCODE_ENTER — 按确认键

    【应用管理】
    - am start -n 包名/Activity — 启动指定Activity
    - monkey -p 包名 -c android.intent.category.LAUNCHER 1 — 启动应用
    - pm list packages — 列出所有应用
    - pm list packages -3 — 列出第三方应用
    - dumpsys package 包名 — 查看应用详情

    【界面信息】
    - dumpsys activity activities | grep mResumedActivity — 当前Activity
    - dumpsys window | grep mCurrentFocus — 当前窗口焦点
    - dumpsys input_method — 输入法状态

    【系统信息】
    - getprop ro.product.model — 手机型号
    - getprop ro.build.version.release — Android版本
    - wm size — 屏幕分辨率
    - wm density — 屏幕密度
    - dumpsys battery — 电池信息
    - dumpsys wifi — WiFi信息
    - settings get system screen_brightness — 屏幕亮度

    【文件操作】
    - ls /sdcard/ — 列出文件
    - cat 文件路径 — 读取文件内容

    【其他】
    - am broadcast — 发送广播
    - content query — 查询ContentProvider
    - settings put/get — 修改/读取系统设置
    - svc wifi enable/disable — 开关WiFi
    - svc data enable/disable — 开关移动数据

    你可以自由组合这些命令来完成任务。"""
    return _run(f"shell {command}")


# ---- 文字输入工具 ----

@function_tool
def input_text(text: str) -> str:
    """在当前焦点输入框中输入文字。支持中文、英文、数字、符号等任意文字。

    使用步骤：
    1. 先用 adb_shell("input tap x y") 点击输入框获取焦点
    2. 等待 0.5 秒让输入框激活
    3. 再调用本工具输入文字

    如果输入没有生效，可能是输入框未获取焦点，请重新点击输入框后再试。"""
    import time

    is_ascii = all(ord(c) < 128 for c in text)

    if is_ascii:
        escaped = text.replace(" ", "%s").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>").replace("'", "\\'").replace('"', '\\"')
        result = _run(f'shell input text "{escaped}"')
        if "error" in result.lower() or "exception" in result.lower():
            return f"ASCII输入失败: {result}"
        return f"已输入: {text}"

    # 中文输入：优先 ADBKeyboard
    check_ime = _run("shell ime list -s")
    if "adbkeyboard" in check_ime.lower():
        _run("shell ime set com.android.adbkeyboard/.AdbIME")
        time.sleep(0.3)
        # 注意：ADBKeyboard 的广播 key 是 msg，不是 text
        result = _run(f"shell am broadcast -a ADB_INPUT_TEXT --es msg '{text}'")
        return f"已通过 ADBKeyboard 输入: {text}"

    # 回退方案：剪贴板
    _run(f"shell am broadcast -a clipper.set -e text '{text}'")
    time.sleep(0.2)
    _run("shell input keyevent 279")  # KEYCODE_PASTE
    return f"已通过剪贴板粘贴: {text}（如果失败，建议安装 ADBKeyboard）"


# ---- 信息获取工具 ----

@function_tool
def get_ui_tree() -> str:
    """获取当前屏幕的完整 UI 结构树（XML解析）。返回所有可见元素的文字、类型、坐标、可点击性等信息。
    这是你理解当前界面的主要方式，比截图识别更快更准确。每次操作后都应该调用来确认结果。

    返回格式: [索引] text="文字" desc="描述" id=资源ID class=类名 bounds=[x1,y1][x2,y2] clickable
    bounds 中的坐标可以用来计算点击位置：中心点 = ((x1+x2)/2, (y1+y2)/2)"""
    _run("shell uiautomator dump /sdcard/ui.xml")
    xml_str = _run("shell cat /sdcard/ui.xml")

    try:
        root = ET.fromstring(xml_str)
    except Exception:
        return f"解析UI失败，原始内容:\n{xml_str[:500]}"

    lines = []
    for i, node in enumerate(root.iter("node")):
        text = node.get("text", "")
        desc = node.get("content-desc", "")
        rid = node.get("resource-id", "")
        cls = node.get("class", "")
        bounds = node.get("bounds", "")
        clickable = node.get("clickable", "false")

        if not text and not desc and clickable == "false":
            continue

        parts = [f"[{i}]"]
        if text:
            parts.append(f'text="{text}"')
        if desc:
            parts.append(f'desc="{desc}"')
        if rid:
            parts.append(f"id={rid.split('/')[-1]}")
        parts.append(f"class={cls.split('.')[-1]}")
        parts.append(f"bounds={bounds}")
        if clickable == "true":
            parts.append("clickable")
        lines.append(" ".join(parts))

    activity = _run("shell dumpsys activity activities | grep mResumedActivity")
    return f"当前Activity: {activity}\n\n界面元素({len(lines)}个):\n" + "\n".join(lines)


@function_tool
def get_screenshot(question: str = "请详细描述当前屏幕上显示的所有内容，包括文字、图标、按钮位置等。") -> str:
    """截取手机屏幕截图，并用视觉模型（VL）分析图片内容。
    当 get_ui_tree 信息不足时使用，比如：
    - WebView 页面内容拿不全
    - 需要理解图片、图标、颜色等视觉信息
    - 自绘UI（游戏、Flutter等）拿不到元素
    - 需要确认界面的视觉布局

    参数 question: 你想了解屏幕上的什么内容，越具体越好。"""
    from openai import OpenAI
    from config import VL_API_KEY, VL_BASE_URL, VL_MODEL

    if not VL_MODEL:
        return "视觉模型未配置。请在 .env 中设置 VL_MODEL（如 qwen-vl-plus）。"

    # 截图
    try:
        result = subprocess.run(
            f"{ADB_PATH} exec-out screencap -p",
            shell=True, capture_output=True, timeout=10
        )
        data = result.stdout
        idx = data.find(b'\x89PNG')
        if idx < 0:
            return "截图失败"
        b64 = base64.b64encode(data[idx:]).decode("utf-8")
    except Exception as e:
        return f"截图失败: {e}"

    # 调用视觉模型
    try:
        vl_client = OpenAI(api_key=VL_API_KEY, base_url=VL_BASE_URL)
        response = vl_client.chat.completions.create(
            model=VL_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": f"这是一个 Android 手机的屏幕截图。{question}\n\n请尽量描述元素的大致位置（顶部/中间/底部，左侧/右侧），方便后续操作定位。"}
                ]
            }],
            max_tokens=1024,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"视觉分析失败: {e}"


@function_tool
def search_installed_apps(keyword: str) -> str:
    """搜索手机上已安装的应用。支持中文名或包名关键词搜索。"""
    # 常见应用中文名 → 包名映射
    APP_ALIASES = {
        "微信": "com.tencent.mm", "支付宝": "com.eg.android.AlipayGphone",
        "抖音": "com.ss.android.ugc.aweme", "今日头条": "com.ss.android.article.news",
        "淘宝": "com.taobao.taobao", "京东": "com.jingdong.app.mall",
        "美团": "com.sankuai.meituan", "饿了么": "me.ele",
        "高德地图": "com.autonavi.minimap", "百度地图": "com.baidu.BaiduMap",
        "网易云音乐": "com.netease.cloudmusic", "QQ音乐": "com.tencent.qqmusic",
        "哔哩哔哩": "tv.danmaku.bili", "B站": "tv.danmaku.bili",
        "小红书": "com.xingin.xhs", "拼多多": "com.xunmeng.pinduoduo",
        "QQ": "com.tencent.mobileqq", "钉钉": "com.alibaba.android.rimet",
        "飞书": "com.ss.android.lark", "企业微信": "com.tencent.wework",
        "百度": "com.baidu.searchbox", "知乎": "com.zhihu.android",
        "微博": "com.sina.weibo", "豆瓣": "com.douban.frodo",
        "闲鱼": "com.taobao.idlefish", "携程": "ctrip.android.view",
        "滴滴": "com.sdu.didi.psnger", "12306": "com.MobileTicket",
        "相机": "com.android.camera", "设置": "com.android.settings",
        "浏览器": "com.android.browser", "计算器": "com.android.calculator2",
        "日历": "com.android.calendar", "时钟": "com.android.deskclock",
        "朴朴": "com.pupumall.customer", "朴朴超市": "com.pupumall.customer",
        "叮咚买菜": "com.yaya.zone", "盒马": "com.wudaokou.hippo",
    }

    # 先查中文名映射
    for name, pkg in APP_ALIASES.items():
        if keyword in name or name in keyword:
            check = _run(f"shell pm list packages {pkg}")
            if pkg in check:
                return f"找到: {name} → {pkg}（已安装）"
            else:
                return f"映射到 {pkg}，但未安装。"

    # 再按包名关键词搜索
    packages = _run("shell pm list packages").splitlines()
    packages = [p.replace("package:", "") for p in packages]
    matches = [p for p in packages if keyword.lower() in p.lower()]
    if matches:
        return f"找到 {len(matches)} 个匹配:\n" + "\n".join(matches[:20])
    return f"未找到包含 '{keyword}' 的应用。可以尝试用英文包名关键词搜索。"


@function_tool
def get_device_info() -> str:
    """获取手机的基本信息，包括型号、Android版本、屏幕分辨率等。"""
    info = {
        "型号": _run("shell getprop ro.product.model"),
        "品牌": _run("shell getprop ro.product.brand"),
        "Android版本": _run("shell getprop ro.build.version.release"),
        "SDK版本": _run("shell getprop ro.build.version.sdk"),
        "屏幕分辨率": _run("shell wm size"),
        "屏幕密度": _run("shell wm density"),
    }
    return "\n".join(f"{k}: {v}" for k, v in info.items())
