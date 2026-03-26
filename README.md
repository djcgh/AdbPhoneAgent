中文 | [English](./README_EN.md)

# 📱 ADB Phone Agent

用自然语言控制你的 Android 手机。基于 ADB 原生指令 + LLM Agent，通过 UI 结构树解析实现快速精准的手机操控。支持 TTS 语音播报，面向视障用户提供无障碍使用体验。

## ✨ 核心特点

### 🌲 UI 树优先，截图辅助

与传统的"截图 → 图像识别 → 操作"方案不同，ADB Phone Agent 采用 **结构化优先** 的策略：

| | 传统方案（如 AutoGLM） | ADB Phone Agent |
|---|---|---|
| 界面理解 | 截图 → 视觉模型识别 | **XML UI 树解析**（uiautomator dump） |
| 元素定位 | 模型预测坐标（可能偏移） | **精确 bounds 坐标**（像素级准确） |
| 操作执行 | 坐标点击 | **ADB 原生命令**（tap/swipe/input/am/pm...） |
| 速度 | 慢（每步需要视觉推理） | **快**（XML 解析毫秒级） |
| 视觉理解 | 主要依赖 | **辅助手段**（WebView/自绘UI 时启用） |

**核心思路**：Android 的 `uiautomator dump` 能直接拿到界面的完整结构树——每个控件的文字、类型、坐标、可点击性一目了然。LLM 读结构化文本比"看图说话"准确得多。只有在 UI 树信息不足时（WebView、Flutter、游戏等），才调用视觉模型截图分析作为补充。

### 🤖 真正的 Agent 架构

基于 [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)，不是简单的 prompt → action 映射：

- **观察-思考-行动循环**：Agent 自主决定每一步操作
- **通用 adb_shell 工具**：LLM 本身就懂 Android 的数百个 shell 命令，不需要穷举
- **function calling**：通过标准的 tool calling 协议与 LLM 交互
- **streaming 输出**：实时展示 Agent 的思考和操作过程

### 🔊 无障碍语音播报

内置 TTS 语音播报能力，面向视障用户设计：

- **操作播报**：每一步操作实时语音播报（"正在打开微信"、"正在点击屏幕"）
- **结果播报**：任务完成后语音播报结果（"你有3条未读消息，第一条是..."）
- **口语化输出**：Agent 回复经过优化，简洁自然，适合听觉理解
- **基于 edge-tts**：免费、高质量中文语音，支持多种音色
- **可开关**：通过 `TTS_ENABLED=false` 关闭播报

### 💬 多轮对话上下文

Agent 支持连续对话，记住之前的操作和结果：

- 保留最近 20 轮对话历史
- 支持追问："刚才那个应用再打开一下"、"第二条消息说了什么"
- 提供清空历史接口，开始全新对话

### ⏹️ 任务停止控制

执行过程中可以随时停止当前操作：

- PC 控制台和手机端都有停止按钮
- 点击后立即中断 Agent 执行循环
- 语音播报"已停止操作"

### 🔌 多模型支持

通过 LiteLLM 适配层，支持任何 OpenAI 兼容 API：

| 模型 | BASE_URL | MODEL |
|---|---|---|
| Qwen (通义千问) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.5-plus` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Ollama (本地) | `http://localhost:11434/v1` | `qwen2.5:14b` |
| 其他兼容 API | 自定义 | 自定义 |

## 🚀 快速开始

### 1. 环境准备

- Python 3.10+
- ADB 已安装并配置到 PATH（`adb devices` 能识别到手机）
- Android 手机已开启 USB 调试

### 2. 安装

```bash
git clone https://github.com/djcgh/AdbPhoneAgent.git
cd adbPhoneAgent
pip install -r requirements.txt
```

### 3. 配置

```bash
cp .env.example .env
```

编辑 `.env` 填入你的 LLM API 密钥：

```env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.5-plus

# 可选：视觉模型（用于截图理解）
VL_MODEL=qwen-vl-plus

# TTS 语音播报（默认开启）
TTS_ENABLED=true
TTS_VOICE=zh-CN-XiaoxiaoNeural
```

### 4. 中文输入支持（推荐）

安装 [ADBKeyboard](https://github.com/nickel8448/ADBKeyboard) 以获得完美的中文输入支持：

```bash
# 下载并安装
adb install ADBKeyboard.apk

# 启用输入法
adb shell ime enable com.android.adbkeyboard/.AdbIME
```

项目启动时会自动切换到 ADBKeyboard。不安装也能用，Agent 会自动回退到剪贴板粘贴方式。

### 5. 启动

```bash
python server.py
```

### 6. 使用

- **PC 控制台**：打开 `http://localhost:8000/monitor`
  - 左侧实时手机画面
  - 右侧操作日志 + 指令输入 + 停止按钮
- **手机端**：打开 `http://你的电脑IP:8000/mobile`
  - 轻量指令输入页面

## 🛠️ Agent 工具集

| 工具 | 说明 |
|---|---|
| `adb_shell` | 万能工具，执行任意 Android shell 命令 |
| `input_text` | 智能文字输入（统一使用 ADBKeyboard，自动回退剪贴板） |
| `get_ui_tree` | 获取界面 XML 结构树（Agent 的"眼睛"） |
| `get_screenshot` | 截图 + 视觉模型分析（辅助理解） |
| `search_installed_apps` | 搜索已安装应用的包名 |
| `get_device_info` | 获取设备基本信息 |

## 📝 使用示例

```
> 打开设置，找到关于手机，告诉我系统版本
> 打开微信，找到文件传输助手，发一条消息
> 帮我把屏幕亮度调到最低
> 手机里哪个应用占存储空间最大
> 打开浏览器搜索今天天气
> 刚才那个应用再打开一下（多轮对话）
```

## 🏗️ 架构

```
用户输入自然语言指令（文字 / 未来支持语音）
        ↓
   OpenAI Agents SDK (function calling)
        ↓
   ┌─── Agent 循环 ───────────────────┐
   │ get_ui_tree() → XML结构树        │ ← 主要感知
   │ get_screenshot() → 视觉模型分析   │ ← 辅助感知
   │ adb_shell() → 执行操作           │ ← 行动
   │ TTS 播报每步操作                  │ ← 无障碍
   │ ... 循环直到任务完成              │
   └──────────────────────────────────┘
        ↓
   结果返回 + 语音播报 + 实时日志推送
```

## 🗺️ Roadmap

### 🔊 语音交互闭环

- **语音输入**：通过语音识别（STT）接收指令，解放双手和眼睛
- **页面朗读**：操作完成后，自动总结当前页面内容并语音播报
- **对话式交互**：支持连续对话，追问细节（"第二条消息说了什么？"）

### 📱 多设备支持

- 同时管理多台 Android 设备
- 通过设备 ID 切换控制目标

## 📄 License

MIT
