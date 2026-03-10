中文 | [English](./README_EN.md)

# 📱 ADB Phone Agent

用自然语言控制你的 Android 手机。基于 ADB 原生指令 + LLM Agent，通过 UI 结构树解析实现快速精准的手机操控。

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
```

### 4. 中文输入支持（推荐）

安装 [ADBKeyboard](https://github.com/nickel8448/ADBKeyboard) 以获得完美的中文输入支持：

```bash
# 下载并安装
adb install ADBKeyboard.apk

# 启用输入法
adb shell ime enable com.android.adbkeyboard/.AdbIME
adb shell ime set com.android.adbkeyboard/.AdbIME
```

不安装也能用，Agent 会自动回退到剪贴板粘贴方式，但 ADBKeyboard 更稳定。

### 4. 启动

```bash
python server.py
```

### 5. 使用

- **PC 控制台**：打开 `http://localhost:8000/monitor`
  - 左侧实时手机画面
  - 右侧操作日志 + 指令输入
- **手机端**：打开 `http://你的电脑IP:8000/mobile`
  - 轻量指令输入页面

## 🛠️ Agent 工具集

| 工具 | 说明 |
|---|---|
| `adb_shell` | 万能工具，执行任意 Android shell 命令 |
| `input_text` | 智能文字输入，自动处理中英文（支持 ADBKeyboard / 剪贴板回退） |
| `get_ui_tree` | 获取界面 XML 结构树（Agent 的"眼睛"） |
| `get_screenshot` | 截图 + 视觉模型分析（辅助理解） |
| `search_installed_apps` | 搜索已安装应用的包名 |
| `get_device_info` | 获取设备基本信息 |

Agent 通过 `adb_shell` 可以执行所有 Android 命令，包括触控操作、应用管理、系统设置、文件操作等。LLM 本身就具备 Android shell 命令的知识，无需穷举。

## 📝 使用示例

```
> 打开设置，找到关于手机，告诉我系统版本
> 打开微信，找到文件传输助手，发一条消息
> 帮我把屏幕亮度调到最低
> 手机里哪个应用占存储空间最大
> 打开浏览器搜索今天天气
```

## 🏗️ 架构

```
用户输入自然语言指令
        ↓
   OpenAI Agents SDK (function calling)
        ↓
   ┌─── Agent 循环 ───────────────────┐
   │ get_ui_tree() → XML结构树        │ ← 主要感知
   │ get_screenshot() → 视觉模型分析   │ ← 辅助感知
   │ adb_shell() → 执行操作           │ ← 行动
   │ ... 循环直到任务完成              │
   └──────────────────────────────────┘
        ↓
   结果返回 + 实时日志推送
```

## 🗺️ Roadmap

### 🔊 无障碍模式（Accessibility Mode）

项目的长期目标是成为视障用户的手机操控助手：

- **语音输入**：通过语音识别（STT）接收指令，解放双手和眼睛
- **步骤播报**：Agent 每执行一步操作，通过语音合成（TTS）实时播报
- **页面朗读**：操作完成后，自动总结当前页面内容并语音播报
- **对话式交互**：支持连续对话，追问细节（"第二条消息说了什么？"）

```
用户说: "帮我看看微信有没有新消息"
    ↓
🎤 语音识别 → 文字指令
    ↓
🤖 Agent: "正在打开微信..." (语音播报)
🤖 Agent: "已进入微信首页..." (语音播报)
🤖 Agent: "你有3条未读消息，张三说：明天下午开会..." (语音播报)
```

UI 树解析在无障碍场景下优势更大——结构化数据天然适合语音播报，比图像识别的描述更精准、更高效。

## 📄 License

MIT
