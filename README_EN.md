[中文](./README.md) | English

# 📱 ADB Phone Agent

Control your Android phone with natural language. An AI Agent powered by ADB native commands + UI XML tree parsing for fast and precise phone automation. Built-in TTS voice narration for accessibility.

## ✨ Key Features

### 🌲 UI Tree First, Screenshot as Fallback

Unlike traditional "screenshot → vision model → action" approaches, ADB Phone Agent uses a **structure-first** strategy:

| | Traditional (e.g. AutoGLM) | ADB Phone Agent |
|---|---|---|
| UI Understanding | Screenshot → Vision model | **XML UI tree parsing** (uiautomator dump) |
| Element Locating | Model-predicted coordinates (may drift) | **Precise bounds coordinates** (pixel-level) |
| Action Execution | Coordinate-based tap | **ADB native commands** (tap/swipe/input/am/pm...) |
| Speed | Slow (vision inference per step) | **Fast** (XML parsing in milliseconds) |
| Vision | Primary | **Fallback** (only for WebView/custom UI) |

**Core idea**: Android's `uiautomator dump` provides the complete UI structure tree — every element's text, type, coordinates, and clickability in plain structured data. LLMs read structured text far more accurately than "looking at pictures". Vision models are only called when the UI tree is insufficient (WebView, Flutter, games, etc.).

### 🤖 Real Agent Architecture

Built on [OpenAI Agents SDK](https://github.com/openai/openai-agents-python), not a simple prompt → action mapping:

- **Observe-Think-Act loop**: Agent autonomously decides each step
- **Universal adb_shell tool**: LLMs already know hundreds of Android shell commands — no need to enumerate
- **Function calling**: Standard tool calling protocol with LLM
- **Streaming output**: Real-time display of Agent's thinking and actions

### 🔊 Accessibility Voice Narration

Built-in TTS for visually impaired users:

- **Step narration**: Real-time voice feedback for each action ("Opening WeChat", "Tapping screen")
- **Result narration**: Voice summary when task completes ("You have 3 unread messages, the first one is...")
- **Natural language output**: Agent responses optimized for listening — concise and conversational
- **Powered by edge-tts**: Free, high-quality Chinese voice synthesis with multiple voice options
- **Toggleable**: Disable with `TTS_ENABLED=false`

### 💬 Multi-turn Conversation

Agent remembers previous operations and results:

- Retains last 20 conversation turns
- Supports follow-ups: "Open that app again", "What did the second message say?"
- Clear history endpoint for fresh conversations

### ⏹️ Task Stop Control

Stop any running operation at any time:

- Stop button on both PC console and mobile page
- Immediately interrupts the Agent execution loop
- Voice feedback: "Operation stopped"

### 🔌 Multi-Model Support

Supports any OpenAI-compatible API via LiteLLM adapter:

| Model | BASE_URL | MODEL |
|---|---|---|
| Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.5-plus` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Ollama (local) | `http://localhost:11434/v1` | `qwen2.5:14b` |
| Any compatible API | Custom | Custom |

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10+
- ADB installed and in PATH (`adb devices` can detect your phone)
- Android phone with USB debugging enabled

### 2. Install

```bash
git clone https://github.com/djcgh/AdbPhoneAgent.git
cd AdbPhoneAgent
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` with your LLM API key:

```env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.5-plus

# Optional: Vision model for screenshot understanding
VL_MODEL=qwen-vl-plus

# TTS voice narration (enabled by default)
TTS_ENABLED=true
TTS_VOICE=zh-CN-XiaoxiaoNeural
```

### 4. Chinese Input Support (Recommended)

Install [ADBKeyboard](https://github.com/nickel8448/ADBKeyboard) for reliable Chinese/Unicode text input:

```bash
adb install ADBKeyboard.apk
adb shell ime enable com.android.adbkeyboard/.AdbIME
```

The server automatically switches to ADBKeyboard on startup. Without it, the Agent falls back to clipboard paste.

### 5. Run

```bash
python server.py
```

### 6. Use

- **PC Console**: Open `http://localhost:8000/monitor`
  - Left: Real-time phone screen
  - Right: Action logs + command input + stop button
- **Mobile**: Open `http://your-pc-ip:8000/mobile`
  - Lightweight command input page

## 🛠️ Agent Tools

| Tool | Description |
|---|---|
| `adb_shell` | Universal tool — execute any Android shell command |
| `input_text` | Smart text input (unified ADBKeyboard, clipboard fallback) |
| `get_ui_tree` | Get UI XML structure tree (Agent's "eyes") |
| `get_screenshot` | Screenshot + vision model analysis (fallback) |
| `search_installed_apps` | Search installed app package names |
| `get_device_info` | Get device basic info |

## 📝 Usage Examples

```
> Open Settings, find About Phone, tell me the system version
> Open WeChat, find File Transfer, send a message
> Turn screen brightness to minimum
> Which app takes the most storage space
> Open browser and search for today's weather
> Open that app again (multi-turn conversation)
```

## 🏗️ Architecture

```
User inputs natural language command (text / voice in future)
        ↓
   OpenAI Agents SDK (function calling)
        ↓
   ┌─── Agent Loop ───────────────────┐
   │ get_ui_tree() → XML structure    │ ← Primary perception
   │ get_screenshot() → Vision model  │ ← Fallback perception
   │ adb_shell() → Execute action     │ ← Action
   │ TTS narrates each step           │ ← Accessibility
   │ ... loop until task complete     │
   └──────────────────────────────────┘
        ↓
   Result + voice narration + real-time log streaming
```

## 🗺️ Roadmap

### 🔊 Full Voice Interaction

- **Voice input**: Receive commands via speech recognition (STT)
- **Page reading**: Auto-summarize and read aloud current screen content
- **Conversational**: Support follow-up questions ("What did the second message say?")

### 📱 Multi-device Support

- Manage multiple Android devices simultaneously
- Switch control target by device ID

## 📄 License

MIT
