[中文](./README.md) | English

# 📱 ADB Phone Agent

Control your Android phone with natural language. An AI Agent powered by ADB native commands + UI XML tree parsing for fast and precise phone automation.

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
```

### 4. Run

```bash
python server.py
```

### 5. Use

- **PC Console**: Open `http://localhost:8000/monitor`
  - Left: Real-time phone screen
  - Right: Action logs + command input
- **Mobile**: Open `http://your-pc-ip:8000/mobile`
  - Lightweight command input page

## 🛠️ Agent Tools

| Tool | Description |
|---|---|
| `adb_shell` | Universal tool — execute any Android shell command |
| `get_ui_tree` | Get UI XML structure tree (Agent's "eyes") |
| `get_screenshot` | Screenshot + vision model analysis (fallback) |
| `search_installed_apps` | Search installed app package names |
| `get_device_info` | Get device basic info |

The Agent can execute all Android commands through `adb_shell`, including touch operations, app management, system settings, file operations, etc. The LLM inherently knows Android shell commands — no enumeration needed.

## 📝 Usage Examples

```
> Open Settings, find About Phone, tell me the system version
> Open WeChat, find File Transfer, send a message
> Turn screen brightness to minimum
> Which app takes the most storage space
> Open browser and search for today's weather
```

## 🏗️ Architecture

```
User inputs natural language command
        ↓
   OpenAI Agents SDK (function calling)
        ↓
   ┌─── Agent Loop ───────────────────┐
   │ get_ui_tree() → XML structure    │ ← Primary perception
   │ get_screenshot() → Vision model  │ ← Fallback perception
   │ adb_shell() → Execute action     │ ← Action
   │ ... loop until task complete     │
   └──────────────────────────────────┘
        ↓
   Result + real-time log streaming
```

## 🗺️ Roadmap

### 🔊 Accessibility Mode

The long-term goal is to become a phone control assistant for visually impaired users:

- **Voice input**: Receive commands via speech recognition (STT)
- **Step narration**: TTS playback for each Agent action in real-time
- **Page reading**: Auto-summarize and read aloud current screen content after operations
- **Conversational**: Support follow-up questions ("What did the second message say?")

```
User says: "Check if I have new WeChat messages"
    ↓
🎤 Speech recognition → Text command
    ↓
🤖 Agent: "Opening WeChat..." (voice)
🤖 Agent: "Entered WeChat home..." (voice)
🤖 Agent: "You have 3 unread messages. Zhang San says: Meeting tomorrow..." (voice)
```

UI tree parsing has an even greater advantage in accessibility — structured data is naturally suited for voice narration, more precise and efficient than image recognition descriptions.

## 📄 License

MIT
