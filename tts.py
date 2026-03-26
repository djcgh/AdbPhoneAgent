"""TTS 语音播报模块 - 生成音频推送到前端浏览器播放"""

import asyncio
import tempfile
import os
import base64

# TTS 配置
TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
TTS_ENABLED = os.getenv("TTS_ENABLED", "true").lower() == "true"

# 播报队列
_speak_queue: asyncio.Queue | None = None
_worker_task: asyncio.Task | None = None

# 音频推送回调（由 server.py 注册）
_audio_callback = None


def set_audio_callback(callback):
    """注册音频推送回调"""
    global _audio_callback
    _audio_callback = callback


async def _generate_audio(text: str) -> str | None:
    """生成音频并返回 base64 编码的 mp3"""
    try:
        import edge_tts

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()

        communicate = edge_tts.Communicate(text, TTS_VOICE)
        await communicate.save(tmp_path)

        with open(tmp_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        os.unlink(tmp_path)
        return audio_b64
    except ImportError:
        print("[TTS] edge-tts 未安装，请运行: pip install edge-tts")
    except Exception as e:
        print(f"[TTS] 生成失败: {e}")
    return None


async def _worker():
    """后台播报 worker，串行消费队列"""
    while True:
        text = await _speak_queue.get()
        # 队列有积压就只播最新的一条
        while not _speak_queue.empty():
            try:
                text = _speak_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # 文本太长截断，避免生成耗时过久
        if len(text) > 100:
            text = text[:100]

        audio_b64 = await _generate_audio(text)
        if audio_b64 and _audio_callback:
            await _audio_callback(audio_b64)


def _ensure_worker():
    """确保后台 worker 已启动"""
    global _speak_queue, _worker_task
    if _speak_queue is None:
        _speak_queue = asyncio.Queue()
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker())


async def speak(text: str):
    """将文本加入播报队列"""
    if not TTS_ENABLED or not text.strip():
        return
    _ensure_worker()
    await _speak_queue.put(text)


async def speak_nonblocking(text: str):
    """同 speak，保持接口兼容"""
    await speak(text)


async def interrupt():
    """清空队列并通知前端停止播放"""
    if _speak_queue:
        while not _speak_queue.empty():
            try:
                _speak_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
    if _audio_callback:
        await _audio_callback("__stop__")
