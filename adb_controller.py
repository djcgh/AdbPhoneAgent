"""ADB 控制层 - 封装所有与手机的交互"""

import subprocess
import base64
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from config import ADB_PATH


@dataclass
class UIElement:
    text: str
    resource_id: str
    class_name: str
    bounds: str
    clickable: bool
    content_desc: str


def run_adb(cmd: str, timeout: int = 10) -> str:
    """执行 adb 命令并返回输出"""
    try:
        result = subprocess.run(
            f"{ADB_PATH} {cmd}",
            shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[timeout]"
    except Exception as e:
        return f"[error] {e}"


def run_shell(cmd: str, timeout: int = 10) -> str:
    """执行 adb shell 命令"""
    return run_adb(f"shell {cmd}", timeout)


def screenshot_raw() -> bytes:
    """截屏并返回原始 PNG 字节"""
    try:
        result = subprocess.run(
            f"{ADB_PATH} exec-out screencap -p",
            shell=True, capture_output=True, timeout=5
        )
        data = result.stdout
        idx = data.find(b'\x89PNG')
        if idx >= 0:
            return data[idx:]
    except Exception:
        pass
    return b""


def screenshot_base64() -> str:
    """截屏并返回 base64 编码的 PNG"""
    raw = screenshot_raw()
    if raw:
        return base64.b64encode(raw).decode("utf-8")
    return ""


def get_screen_size() -> tuple[int, int]:
    """获取屏幕分辨率"""
    output = run_shell("wm size")
    try:
        size = output.split(":")[-1].strip()
        w, h = size.split("x")
        return int(w), int(h)
    except Exception:
        return 1080, 2400


def dump_ui() -> list[UIElement]:
    """获取当前界面的 UI 结构树"""
    run_shell("uiautomator dump /sdcard/ui.xml")
    xml_str = run_shell("cat /sdcard/ui.xml")
    elements = []
    try:
        root = ET.fromstring(xml_str)
        for node in root.iter("node"):
            elements.append(UIElement(
                text=node.get("text", ""),
                resource_id=node.get("resource-id", ""),
                class_name=node.get("class", ""),
                bounds=node.get("bounds", ""),
                clickable=node.get("clickable", "false") == "true",
                content_desc=node.get("content-desc", ""),
            ))
    except Exception:
        pass
    return elements


def ui_to_description(elements: list[UIElement]) -> str:
    """将 UI 元素转为 LLM 可理解的文本描述"""
    lines = []
    for i, el in enumerate(elements):
        if not el.text and not el.content_desc and not el.clickable:
            continue
        parts = [f"[{i}]"]
        if el.text:
            parts.append(f'text="{el.text}"')
        if el.content_desc:
            parts.append(f'desc="{el.content_desc}"')
        if el.resource_id:
            parts.append(f"id={el.resource_id.split('/')[-1]}")
        parts.append(f"class={el.class_name.split('.')[-1]}")
        parts.append(f"bounds={el.bounds}")
        if el.clickable:
            parts.append("clickable")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def parse_bounds(bounds_str: str) -> tuple[int, int]:
    """从 bounds 字符串解析中心坐标"""
    import re
    nums = re.findall(r"\d+", bounds_str)
    if len(nums) == 4:
        x1, y1, x2, y2 = map(int, nums)
        return (x1 + x2) // 2, (y1 + y2) // 2
    return 0, 0
