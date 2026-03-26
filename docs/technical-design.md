# ADB Phone Agent 技术实现方案

## 1. 项目概述

ADB Phone Agent 是一个基于 ADB + LLM Agent 的 Android 手机自然语言操控系统。用户通过自然语言下达指令，AI Agent 自主规划并执行手机操作，同时支持 TTS 语音播报，面向视障用户提供无障碍使用体验。

### 1.1 核心定位

- 自然语言 → 手机操控的 AI Agent
- UI 结构树优先、截图视觉辅助的双通道感知
- 面向无障碍场景的语音播报能力

### 1.2 技术栈

| 层级 | 技术选型 |
|---|---|
| Agent 框架 | OpenAI Agents SDK + LiteLLM |
| LLM | 任意 OpenAI 兼容 API（Qwen / DeepSeek / GPT-4o / Ollama） |
| 视觉模型 | Qwen-VL / GPT-4o 等多模态模型 |
| 设备控制 | ADB（Android Debug Bridge） |
| 语音合成 | edge-tts（微软 TTS） |
| Web 服务 | FastAPI + WebSocket |
| 前端 | 原生 HTML/JS，WebSocket 实时通信 |

## 2. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    用户层                             │
│  ┌──────────────┐          ┌──────────────────┐      │
│  │  PC 控制台    │          │  手机端轻量页面    │      │
│  │  /monitor    │          │  /mobile          │      │
│  └──────┬───────┘          └────────┬─────────┘      │
│         │ WebSocket                  │ WebSocket      │
├─────────┴────────────────────────────┴───────────────┤
│                   服务层 (server.py)                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ WebSocket   │  │  截图推送     │  │  任务管理    │  │
│  │ 路由管理     │  │  screenshot  │  │  停止/历史   │  │
│  └─────────────┘  └──────────────┘  └─────────────┘  │
├──────────────────────────────────────────────────────┤
│                   Agent 层 (llm_agent.py)             │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ OpenAI      │  │  对话历史     │  │  任务取消    │  │
│  │ Agents SDK  │  │  管理         │  │  控制        │  │
│  └──────┬──────┘  └──────────────┘  └─────────────┘  │
│         │ function calling                            │
├─────────┴────────────────────────────────────────────┤
│                   工具层 (tools.py)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐  │
│  │adb_shell │ │input_text│ │get_ui_   │ │get_     │  │
│  │          │ │          │ │tree      │ │screenshot│  │
│  └──────────┘ └──────────┘ └──────────┘ └─────────┘  │
├──────────────────────────────────────────────────────┤
│                   设备层 (adb_controller.py)           │
│  ┌──────────────────────────────────────────────┐     │
│  │  ADB 命令封装 / 截图 / UI dump / 坐标解析     │     │
│  └──────────────────────┬───────────────────────┘     │
│                         │ USB / ADB                    │
├─────────────────────────┴────────────────────────────┤
│                   TTS 层 (tts.py)                     │
│  ┌──────────────────────────────────────────────┐     │
│  │  edge-tts 语音合成 → 本地播放（afplay/mpv）    │     │
│  └──────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

## 3. 核心模块详解

### 3.1 感知系统：UI 树优先 + 视觉辅助

这是本项目与传统方案（如 AutoGLM）的核心差异。

**主通道：UI 结构树解析**

```python
# tools.py - get_ui_tree()
adb shell uiautomator dump /sdcard/ui.xml
adb shell cat /sdcard/ui.xml
```

通过 Android 原生的 `uiautomator dump` 获取完整的界面 XML 结构树，解析后提取每个控件的：
- `text`：显示文字
- `content-desc`：无障碍描述
- `resource-id`：资源 ID
- `class`：控件类型
- `bounds`：精确像素坐标 `[x1,y1][x2,y2]`
- `clickable`：是否可点击

输出格式示例：
```
[3] text="微信" class=TextView bounds=[0,200][540,280] clickable
[5] text="发现" desc="发现页" id=tab_discover class=TextView bounds=[270,2300][540,2400] clickable
```

LLM 直接读取结构化文本，比"看图说话"准确得多。点击坐标通过 bounds 中心点计算，像素级精准。

**辅助通道：视觉模型截图分析**

当 UI 树信息不足时（WebView、Flutter、游戏等自绘 UI），调用视觉模型：

```python
# tools.py - get_screenshot()
adb exec-out screencap -p  # 截图
→ base64 编码 → 发送给 VL 模型（如 qwen-vl-plus）
→ 返回界面描述文本
```

**两种方案对比：**

| 维度 | UI 树（主） | 截图视觉（辅） |
|---|---|---|
| 速度 | 毫秒级 | 秒级（需要模型推理） |
| 精度 | 像素级精确坐标 | 模型预测坐标（可能偏移） |
| 适用场景 | 原生 UI | WebView / 自绘 UI / 图片内容 |
| Token 消耗 | 低（结构化文本） | 高（图片编码） |

### 3.2 Agent 架构

基于 OpenAI Agents SDK 构建，核心是 **观察-思考-行动** 循环：

```python
# llm_agent.py
phone_agent = Agent(
    name="PhoneAgent",
    instructions=INSTRUCTIONS,  # 系统提示词
    model=LitellmModel(         # 通过 LiteLLM 适配任意模型
        model=f"openai/{LLM_MODEL}",
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    ),
    tools=[adb_shell, input_text, get_ui_tree, get_screenshot, ...],
)
```

**执行流程：**

1. 用户输入自然语言指令
2. Agent 调用 `get_ui_tree()` 观察当前界面
3. LLM 分析界面状态，决定下一步操作
4. 通过 `adb_shell()` 执行操作（点击/滑动/启动应用等）
5. 再次调用 `get_ui_tree()` 确认操作结果
6. 循环直到任务完成，最多 50 轮

**关键设计：通用 adb_shell 工具**

不同于为每个操作定义独立工具，本项目提供一个通用的 `adb_shell` 工具，让 LLM 自由组合 Android shell 命令。LLM 本身就具备 Android 命令知识，无需穷举。

同时在 `adb_shell` 内部做了文字输入拦截：如果 LLM 尝试用 `input text` 命令输入文字，会自动重定向到 ADBKeyboard 广播方式，避免中文输入问题。

### 3.3 文字输入方案

统一使用 ADBKeyboard 广播方式，中英文通吃：

```python
# tools.py - _input_text_impl()
adb shell am broadcast -a ADB_INPUT_TEXT --es msg '要输入的文字'
```

服务启动时自动切换输入法：
```python
# server.py - startup()
adb shell ime set com.android.adbkeyboard/.AdbIME
```

回退方案：ADBKeyboard 不可用时，通过剪贴板粘贴。

### 3.4 对话历史管理

Agent 支持多轮对话上下文：

```python
# llm_agent.py
_conversation_history: list[dict] = []
MAX_HISTORY_TURNS = 20

# 每次调用时带上历史
messages = _conversation_history + [{"role": "user", "content": instruction}]
result = Runner.run_streamed(phone_agent, input=messages, max_turns=50)

# 完成后追加到历史
_conversation_history.append({"role": "user", "content": instruction})
_conversation_history.append({"role": "assistant", "content": final_output})
```

- 保留最近 20 轮对话，防止 token 超限
- 支持追问："刚才那个应用再打开一下"、"第二条消息说了什么"
- 提供 `POST /clear_history` 接口清空历史

### 3.5 任务取消机制

通过 `asyncio.Event` 实现协作式取消：

```python
# llm_agent.py
_current_cancel_event: asyncio.Event | None = None

def cancel_current_task():
    if _current_cancel_event:
        _current_cancel_event.set()

# 在 Agent 事件循环中检查
async for event in result.stream_events():
    if _current_cancel_event.is_set():
        cancelled = True
        break
```

前端发送 `{"action": "stop"}` → server 调用 `cancel_current_task()` → Agent 循环检测到取消信号 → 中断执行。

### 3.6 TTS 语音播报（无障碍模式）

基于 edge-tts 实现，采用队列化播报 + 前端浏览器播放的架构，不阻塞 Agent 执行：

**架构：**

```
Agent 调用 speak(text)
    ↓
播报队列（asyncio.Queue）
    ↓
后台 worker 串行消费
    ↓
edge-tts 生成 mp3 → base64 编码
    ↓
WebSocket 推送到前端
    ↓
浏览器 Audio API 播放
```

**关键设计：**

- **队列化非阻塞**：`speak()` 将文本丢入队列立即返回，不等待音频生成和播放，Agent 继续执行下一步操作
- **队列积压跳过**：如果 Agent 跑得比播报快，worker 会跳过中间积压的旧播报，只播最新的，避免越来越滞后
- **前端浏览器播放**：音频通过 WebSocket 推送到前端，由浏览器 Audio API 播放，支持录屏软件直接捕获应用音频
- **打断机制**：任务取消时清空队列并通知前端停止播放

```python
# tts.py - 核心流程
async def _worker():
    while True:
        text = await _speak_queue.get()
        # 队列积压时跳过旧的
        while not _speak_queue.empty():
            text = _speak_queue.get_nowait()
        audio_b64 = await _generate_audio(text)
        if audio_b64 and _audio_callback:
            await _audio_callback(audio_b64)  # 推送到前端
```

**播报时机：**

| 时机 | 内容 | 示例 |
|---|---|---|
| 收到指令 | 确认提示 | "收到，正在处理" |
| 工具调用 | 操作描述 | "正在查看当前界面"、"正在点击屏幕" |
| Agent 回复 | 口语化结果 | "已打开微信，你有3条未读消息" |
| 任务取消 | 停止提示 | "已停止操作" |

工具调用的播报通过 `_narrate_tool_call()` 将技术操作翻译成口语：

```python
def _narrate_tool_call(name, args):
    if name == "get_ui_tree": return "正在查看当前界面"
    if "input tap" in cmd: return "正在点击屏幕"
    if "input swipe" in cmd: return "正在滑动屏幕"
    if "am start" in cmd: return "正在打开应用"
    ...
```

同时在 Agent 的 system prompt 中要求 LLM 输出口语化、适合听觉理解的内容，不输出坐标等技术细节。

### 3.7 弹窗自动处理

Agent 的 system prompt 中明确要求遇到任何弹窗、广告、升级提示、权限请求等，第一时间关闭：

- 常见关闭方式：点击"关闭"、"取消"、"跳过"、"以后再说"、"X"按钮、按返回键
- 与当前任务相关的权限请求（如定位）则同意，无关则拒绝
- 连续多个弹窗逐个关闭，直到回到正常界面
- 核心原则：不被弹窗打断操作流程，快速处理后继续执行用户指令

### 3.8 ADBKeyboard 自动切换

服务启动时自动将输入法切换到 ADBKeyboard：

```python
# server.py - startup()
adb shell ime set com.android.adbkeyboard/.AdbIME
```

所有文字输入（中英文）统一通过 ADBKeyboard 广播方式，不再区分 ASCII 和非 ASCII：

```python
# tools.py - _input_text_impl()
adb shell am broadcast -a ADB_INPUT_TEXT --es msg '要输入的文字'
```

ADBKeyboard 不可用时自动回退到剪贴板粘贴方式。

### 3.9 实时通信架构

```
PC 控制台 ←──WebSocket(/ws/monitor)──→ Server ←──WebSocket(/ws/mobile)──→ 手机端/PC端
                                         │
                                    截图推送循环
                                    (screenshot_loop)
```

- **截图推送**：后台线程持续截图，压缩为 JPEG 后通过 WebSocket 推送给所有 monitor 客户端
- **指令执行**：mobile 端发送指令 → server 创建异步任务 → Agent 执行 → 实时推送日志和结果
- **双端同步**：mobile 端的操作日志同步推送到 monitor 端

## 4. 文件结构

```
adbPhoneAgent/
├── server.py           # FastAPI 主服务，WebSocket 路由，截图推送
├── llm_agent.py        # Agent 定义，对话历史，任务取消，TTS 接入
├── tools.py            # Agent 工具集（adb_shell, get_ui_tree, input_text 等）
├── adb_controller.py   # ADB 底层封装（截图、UI dump、坐标解析）
├── tts.py              # TTS 语音播报模块（edge-tts）
├── config.py           # 配置管理（.env 加载）
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量模板
└── static/
    ├── monitor.html    # PC 控制台（手机画面 + 操作日志 + 指令输入）
    └── mobile.html     # 手机端轻量页面（指令输入 + 日志）
```

## 5. 配置说明

通过 `.env` 文件配置，支持以下参数：

```env
# LLM 配置
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.5-plus

# 视觉模型（可选）
VL_MODEL=qwen-vl-plus

# TTS 语音播报
TTS_ENABLED=true
TTS_VOICE=zh-CN-XiaoxiaoNeural

# 服务
HOST=0.0.0.0
PORT=8000
```

## 6. 后续规划

### 6.1 语音输入（STT）
- 接入语音识别，实现完整的语音交互闭环
- 用户说话 → STT 转文字 → Agent 执行 → TTS 播报结果

### 6.2 更智能的无障碍播报
- 页面自动摘要：进入新页面后自动总结内容并播报
- 对话式追问："第二条消息说了什么？"

### 6.3 多设备支持
- 同时管理多台 Android 设备
- 通过设备 ID 切换控制目标
