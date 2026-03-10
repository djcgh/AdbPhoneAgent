"""LLM Agent - 基于 OpenAI Agents SDK，支持多种 LLM"""

import os
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
- adb_shell 是你的万能工具，所有 Android shell 命令都可以通过它执行
- get_ui_tree 是你的眼睛，每次操作后都应该看一下界面变化
- 优先通过 UI 元素的 bounds 坐标计算点击位置，比盲猜坐标准确
- 点击元素时，用 bounds 的中心点: x=(x1+x2)/2, y=(y1+y2)/2
- 不确定包名就用 search_installed_apps 搜索
- 每步操作后等待 0.5-1 秒让界面更新

## 视觉辅助
- 当 get_ui_tree 返回的元素很少或信息不全时（如 WebView、自绘UI），用 get_screenshot 截图分析
- get_screenshot 会调用视觉模型来"看"屏幕，告诉你界面上有什么
- 你可以通过 question 参数指定想了解的内容，比如"搜索按钮在哪里"
- 结合 UI 树 + 视觉分析，可以更准确地理解和操作界面

## 注意事项
- 输入文字统一用 input_text 工具，它自动处理中英文
- 重要：输入文字前必须先用 adb_shell("input tap x y") 点击输入框获取焦点，等 0.5 秒后再调 input_text
- 点击输入框时，从 get_ui_tree 的 bounds 计算中心坐标：x=(x1+x2)/2, y=(y1+y2)/2
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


async def process_instruction(instruction: str, log_callback=None) -> str:
    """处理用户指令，使用 streaming 模式实时输出过程"""
    from agents.stream_events import RunItemStreamEvent
    from agents.items import (
        ToolCallItem,
        ToolCallOutputItem,
        MessageOutputItem,
        ReasoningItem,
    )

    if log_callback:
        await log_callback("[Agent] 开始处理指令...")

    try:
        result = Runner.run_streamed(phone_agent, input=instruction, max_turns=50)
        final_output = ""

        async for event in result.stream_events():
            if isinstance(event, RunItemStreamEvent):
                item = event.item

                if isinstance(item, ToolCallItem):
                    name = item.raw_item.name if hasattr(item.raw_item, 'name') else "unknown"
                    args = item.raw_item.arguments if hasattr(item.raw_item, 'arguments') else ""
                    if len(args) > 150:
                        args = args[:150] + "..."
                    if log_callback:
                        await log_callback(f"[调用] {name}({args})")

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

                elif isinstance(item, ReasoningItem):
                    if log_callback:
                        await log_callback("[思考中...]")

        if not final_output:
            final_output = result.final_output if hasattr(result, 'final_output') else "任务完成"

        if log_callback:
            await log_callback(f"[完成] {final_output[:100]}")

        return final_output

    except Exception as e:
        error_msg = f"执行失败: {e}"
        if log_callback:
            await log_callback(f"[错误] {error_msg}")
        return error_msg
