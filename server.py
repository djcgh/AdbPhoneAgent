"""主服务 - FastAPI + WebSocket"""

import asyncio
import json
import base64
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
import adb_controller as adb
import llm_agent
from config import HOST, PORT

BASE_DIR = Path(__file__).parent

app = FastAPI(title="ADB Phone Agent")

monitor_clients: list[WebSocket] = []
mobile_clients: list[WebSocket] = []


async def broadcast_to_monitors(msg: dict):
    """向所有 PC 监控端推送消息"""
    data = json.dumps(msg, ensure_ascii=False)
    for ws in monitor_clients[:]:
        try:
            await ws.send_text(data)
        except Exception:
            monitor_clients.remove(ws)


async def screenshot_loop():
    """连续截图推送，在线程池中执行避免阻塞"""
    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()

    def capture_jpeg():
        """截图并压缩为 JPEG"""
        raw = adb.screenshot_raw()
        if not raw:
            return None
        try:
            from io import BytesIO
            from PIL import Image
            img = Image.open(BytesIO(raw))
            img = img.resize((img.width // 2, img.height // 2), Image.NEAREST)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception:
            return base64.b64encode(raw).decode("utf-8")

    while True:
        if monitor_clients:
            b64 = await loop.run_in_executor(executor, capture_jpeg)
            if b64:
                await broadcast_to_monitors({"type": "screenshot", "data": b64})
        else:
            await asyncio.sleep(0.5)


@app.on_event("startup")
async def startup():
    # 启动时自动切换到 ADBKeyboard
    import subprocess
    from config import ADB_PATH
    try:
        subprocess.run(f"{ADB_PATH} shell ime set com.android.adbkeyboard/.AdbIME",
                       shell=True, capture_output=True, timeout=5)
        print("[启动] 已切换到 ADBKeyboard 输入法")
    except Exception as e:
        print(f"[启动] ADBKeyboard 切换失败: {e}，中文输入将回退到剪贴板方式")

    # 注册 TTS 音频推送回调
    from tts import set_audio_callback

    async def push_audio(audio_b64: str):
        await broadcast_to_monitors({"type": "audio", "data": audio_b64})

    set_audio_callback(push_audio)

    asyncio.create_task(screenshot_loop())


# ---- 页面路由 ----

@app.get("/", response_class=HTMLResponse)
async def index():
    return """<html><body style="text-align:center;padding:40px;font-family:sans-serif;background:#0a0a0a;color:#e0e0e0">
    <h2 style="color:#4fc3f7">📱 ADB Phone Agent</h2>
    <p><a href="/mobile" style="color:#4fc3f7">📱 手机控制端</a></p>
    <p><a href="/monitor" style="color:#4fc3f7">🖥️ PC 控制台</a></p>
    </body></html>"""


@app.get("/mobile", response_class=HTMLResponse)
async def mobile_page():
    content = (BASE_DIR / "static/mobile.html").read_text()
    return Response(content=content, media_type="text/html",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.post("/clear_history")
async def clear_history():
    """清空对话历史"""
    llm_agent.clear_history()
    return {"status": "ok"}


@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page():
    content = (BASE_DIR / "static/monitor.html").read_text()
    return Response(content=content, media_type="text/html",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


# ---- WebSocket 端点 ----

@app.websocket("/ws/mobile")
async def ws_mobile(ws: WebSocket):
    await ws.accept()
    mobile_clients.append(ws)
    current_task: asyncio.Task | None = None
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            # 停止当前任务
            if msg.get("action") == "stop":
                llm_agent.cancel_current_task()
                if current_task and not current_task.done():
                    current_task.cancel()
                await ws.send_text(json.dumps({"type": "result", "data": "已停止"}, ensure_ascii=False))
                await broadcast_to_monitors({"type": "result", "data": "已停止"})
                continue

            instruction = msg.get("instruction", "")
            if not instruction:
                continue

            await broadcast_to_monitors({"type": "instruction", "data": instruction})
            await ws.send_text(json.dumps({"type": "status", "data": "正在执行..."}, ensure_ascii=False))

            async def log_cb(log_msg):
                await broadcast_to_monitors({"type": "log", "data": log_msg})
                await ws.send_text(json.dumps({"type": "log", "data": log_msg}, ensure_ascii=False))

            async def run_task():
                result = await llm_agent.process_instruction(instruction, log_callback=log_cb)
                await ws.send_text(json.dumps({"type": "result", "data": result}, ensure_ascii=False))
                await broadcast_to_monitors({"type": "result", "data": result})

            current_task = asyncio.create_task(run_task())
    except WebSocketDisconnect:
        mobile_clients.remove(ws)


@app.websocket("/ws/monitor")
async def ws_monitor(ws: WebSocket):
    await ws.accept()
    monitor_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        monitor_clients.remove(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=HOST, port=PORT, reload=True)
