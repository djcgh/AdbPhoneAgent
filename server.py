"""主服务 - FastAPI + WebSocket"""

import asyncio
import json
import base64
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
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

    while True:
        if monitor_clients:
            raw = await loop.run_in_executor(executor, adb.screenshot_raw)
            if raw:
                try:
                    from io import BytesIO
                    from PIL import Image
                    img = Image.open(BytesIO(raw))
                    img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=60)
                    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                except Exception:
                    b64 = base64.b64encode(raw).decode("utf-8")
                await broadcast_to_monitors({"type": "screenshot", "data": b64})
        else:
            await asyncio.sleep(0.5)


@app.on_event("startup")
async def startup():
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
    return (BASE_DIR / "static/mobile.html").read_text()


@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page():
    return (BASE_DIR / "static/monitor.html").read_text()


# ---- WebSocket 端点 ----

@app.websocket("/ws/mobile")
async def ws_mobile(ws: WebSocket):
    await ws.accept()
    mobile_clients.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            instruction = msg.get("instruction", "")

            await broadcast_to_monitors({"type": "instruction", "data": instruction})
            await ws.send_text(json.dumps({"type": "status", "data": "正在执行..."}, ensure_ascii=False))

            async def log_cb(log_msg):
                await broadcast_to_monitors({"type": "log", "data": log_msg})
                await ws.send_text(json.dumps({"type": "log", "data": log_msg}, ensure_ascii=False))

            result = await llm_agent.process_instruction(instruction, log_callback=log_cb)

            await ws.send_text(json.dumps({"type": "result", "data": result}, ensure_ascii=False))
            await broadcast_to_monitors({"type": "result", "data": result})
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
