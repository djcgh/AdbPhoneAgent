"""项目配置 - 从环境变量或 .env 文件加载"""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM 配置 - 支持任何 OpenAI 兼容 API（Qwen / DeepSeek / OpenAI / Ollama 等）
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# 视觉模型配置（用于截图理解辅助，可选）
VL_API_KEY = os.getenv("VL_API_KEY", LLM_API_KEY)
VL_BASE_URL = os.getenv("VL_BASE_URL", LLM_BASE_URL)
VL_MODEL = os.getenv("VL_MODEL", "")

# ADB
ADB_PATH = os.getenv("ADB_PATH", "adb")

# 服务
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
