"""LLM Agent - 基于 OpenAI Agents SDK，支持多种 LLM"""

import os
import asyncio
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"
os.environ["OPENAI_API_KEY"] = "sk-placeholder"  # litellm 需要，实际用 LitellmModel 的 api_key

from agents import Agent, Runner, ModelSettings
from agents.extensions.models.litellm_model import LitellmModel
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from tools import adb_shell, input_text, get_ui_tree, get_screenshot, search_installed_apps, get_device_info

INSTRUCTIONS = """你是一个 Android 手机操控 Agent。用户给你自然语言指令，你通过工具来操控手机完成任务。

## 工作流程
1. 先用 get_ui_tree 观察当前界面状态
2. 分析界面元素，决定下一步操作
3. 用 adb_shell 执行具体命令
4. 再次用 get_ui_tree 确认操作结果
5. 重复直到任务完成

## 核心原则
- 你的首要目标是完成用户的指令，一切操作围绕这个目标展开
- adb_shell 是你的万能工具，所有 Android shell 命令都可以通过它执行
- get_ui_tree 是你的眼睛，每次操作后都应该看一下界面变化
- 优先通过 UI 元素的 bounds 坐标计算点击位置，比盲猜坐标准确
- 点击元素时，用 bounds 的中心点: x=(x1+x2)/2, y=(y1+y2)/2
- 不确定包名就用 search_installed_apps 搜索
- 每步操作后等待 0.5-1 秒让界面更新

## 弹窗处理（重要）
- 遇到任何弹窗、广告、升级提示、权限请求、活动推广等，第一时间关闭，不要犹豫
- 常见关闭方式：点击"关闭"、"取消"、"跳过"、"以后再说"、"X"按钮、按返回键
- 如果弹窗有"同意"/"允许"类权限请求（如定位、通知），且与当前任务相关则同意，无关则拒绝
- 不要被弹窗打断操作流程，快速处理后继续执行用户的指令
- 如果连续出现多个弹窗，逐个关闭，直到回到正常界面

## 视觉辅助
- 当 get_ui_tree 返回的元素很少或信息不全时（如 WebView、自绘UI），用 get_screenshot 截图分析
- get_screenshot 会调用视觉模型来"看"屏幕，告诉你界面上有什么
- 你可以通过 question 参数指定想了解的内容，比如"搜索按钮在哪里"
- 结合 UI 树 + 视觉分析，可以更准确地理解和操作界面

## 无障碍播报
- 你的回复会被语音播报给视障用户，所以最终回复必须简洁、口语化、适合听觉理解
- 不要输出坐标、XML、技术细节等视觉信息，只说"做了什么"和"结果是什么"
- 好的例子："已打开微信，你有3条未读消息，第一条是张三发的：明天下午开会"
- 不好的例子："点击了坐标(540,1200)的元素，bounds=[0,1100][1080,1300]"

## 注意事项
- 禁止用 adb_shell 输入文字！不要用 input text、am broadcast ADB_INPUT_TEXT 等命令。所有文字输入必须用 input_text 工具
- 输入文字前必须先用 adb_shell("input tap x y") 点击输入框获取焦点，等 0.5 秒后再调 input_text
- 点击输入框时，从 get_ui_tree 的 bounds 计算中心坐标：x=(x1+x2)/2, y=(y1+y2)/2
- 不要在 adb_shell 中使用 && 或 ; 连接多个命令，每个命令单独调用
- 某些操作可能需要多步完成，耐心逐步执行
- 如果操作没有效果，尝试换一种方式
"""

phone_agent = Agent(
    name="PhoneAgent",
    instructions=INSTRUCTIONS,
    model=LitellmModel(
        model=f"openai/{LLM_MODEL}",
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    ),
    tools=[adb_shell, input_text, get_ui_tree, get_screenshot, search_installed_apps, get_device_info],
    model_settings=ModelSettings(temperature=0.1),
)

# 对话历史管理
_conversation_history: list[dict] = []
MAX_HISTORY_TURNS = 20  # 保留最近 20 轮，防止 token 爆炸

# 任务取消控制
_current_cancel_event: asyncio.Event | None = None


def clear_history():
    """清空对话历史"""
    _conversation_history.clear()


def cancel_current_task():
    """取消当前正在执行的任务"""
    global _current_cancel_event
    if _current_cancel_event:
        _current_cancel_event.set()


def _trim_history():
    """裁剪历史，只保留最近的轮次"""
    if len(_conversation_history) > MAX_HISTORY_TURNS * 2:
        del _conversation_history[:-MAX_HISTORY_TURNS * 2]


def _narrate_tool_call(name: str, args: str) -> str:
    """将工具调用翻译成口语化的播报文本，只播报关键操作"""
    import json
    try:
        parsed = json.loads(args) if args else {}
    except Exception:
        parsed = {}

    # 高频低价值的操作不播报
    if name in ("get_ui_tree", "get_device_info"):
        return ""
    elif name == "get_screenshot":
        return "正在截图分析"
    elif name == "search_installed_apps":
        kw = parsed.get("keyword", "")
        return f"正在搜索{kw}" if kw else ""
    elif name == "input_text":
        text = parsed.get("text", "")
        return f"正在输入文字：{text}" if text else "正在输入文字"
    elif name == "adb_shell":
        cmd = parsed.get("command", "")
        if "input tap" in cmd:
            return "正在点击屏幕"
        elif "input swipe" in cmd:
            return "正在滑动屏幕"
        elif "input keyevent" in cmd:
            if "BACK" in cmd:
                return "正在按返回键"
            elif "HOME" in cmd:
                return "正在回到主页"
            elif "ENTER" in cmd:
                return "正在按确认键"
            return "正在按键操作"
        elif "am start" in cmd or "monkey" in cmd:
            return "正在打开应用"
        elif "pm list" in cmd:
            return "正在查看已安装应用"
        elif "settings" in cmd:
            return "正在修改系统设置"
        return "正在执行操作"
    return ""


async def process_instruction(instruction: str, log_callback=None) -> str:
    """处理用户指令，使用 streaming 模式实时输出过程"""
    from agents.stream_events import RunItemStreamEvent
    from agents.items import (
        ToolCallItem,
        ToolCallOutputItem,
        MessageOutputItem,
        ReasoningItem,
    )

    from tts import speak, speak_nonblocking, TTS_ENABLED, interrupt as tts_interrupt

    global _current_cancel_event
    _current_cancel_event = asyncio.Event()
    cancelled = False

    if log_callback:
        await log_callback("[Agent] 开始处理指令...")

    try:
        # 构建带历史的输入
        _trim_history()
        messages = _conversation_history + [{"role": "user", "content": instruction}]

        result = Runner.run_streamed(phone_agent, input=messages, max_turns=50)
        final_output = ""

        async for event in result.stream_events():
            # 检查是否被取消
            if _current_cancel_event.is_set():
                cancelled = True
                if log_callback:
                    await log_callback("[中断] 任务已停止")
                if TTS_ENABLED:
                    await tts_interrupt()
                    await speak("已停止操作")
                break

            if isinstance(event, RunItemStreamEvent):
                item = event.item

                if isinstance(item, ToolCallItem):
                    name = item.raw_item.name if hasattr(item.raw_item, 'name') else "unknown"
                    args = item.raw_item.arguments if hasattr(item.raw_item, 'arguments') else ""
                    if len(args) > 150:
                        args = args[:150] + "..."
                    if log_callback:
                        await log_callback(f"[调用] {name}({args})")
                    # 播报每步操作
                    if TTS_ENABLED:
                        narration = _narrate_tool_call(name, args)
                        if narration:
                            await speak_nonblocking(narration)

                elif isinstance(item, ToolCallOutputItem):
                    output = item.output if isinstance(item.output, str) else str(item.output)
                    if len(output) > 200:
                        output = output[:200] + "..."
                    if log_callback:
                        await log_callback(f"[结果] {output}")

                elif isinstance(item, MessageOutputItem):
                    text = ""
                    for part in item.raw_item.content:
                        if hasattr(part, 'text'):
                            text += part.text
                    if text:
                        final_output = text
                        if TTS_ENABLED:
                            await speak(text)

                elif isinstance(item, ReasoningItem):
                    if log_callback:
                        await log_callback("[思考中...]")

        if cancelled:
            final_output = "任务已被用户停止"

        if not final_output:
            final_output = result.final_output if hasattr(result, 'final_output') else "任务完成"

        # 保存对话历史
        _conversation_history.append({"role": "user", "content": instruction})
        _conversation_history.append({"role": "assistant", "content": final_output})

        if log_callback:
            await log_callback(f"[完成] {final_output[:100]}")

        return final_output

    except Exception as e:
        error_msg = f"执行失败: {e}"
        if log_callback:
            await log_callback(f"[错误] {error_msg}")
        return error_msg
    finally:
        _current_cancel_event = None
