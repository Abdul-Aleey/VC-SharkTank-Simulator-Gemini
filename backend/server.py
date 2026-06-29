"""
VC Shark Tank Simulator — Google ADK Multi-Agent Backend
=========================================================
Replaces the old Vertex AI proxy with a real multi-agent simulation server.

Each simulation run creates 5 independent ADK agents:
  - FounderAgent       (AI pitch + responses)
  - VincentAgent       (finance focus)
  - MarcusAgent        (tech focus)
  - BeatriceAgent      (branding focus)
  - LeonaAgent         (go-to-market focus)

The SimulationOrchestrator coordinates them and streams typed JSON events
to the frontend over a WebSocket connection.

Usage:
  pip install -r requirements.txt
  uvicorn server:app --host 127.0.0.1 --port 5000
"""

import asyncio
import json
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from simulation.orchestrator import SimulationOrchestrator

load_dotenv(".env.local")

API_BACKEND_PORT = int(os.getenv("API_BACKEND_PORT", "5000"))
API_BACKEND_HOST = os.getenv("API_BACKEND_HOST", "127.0.0.1")

# Vertex AI mode: set GOOGLE_GENAI_USE_VERTEXAI=true in env (Cloud Run service account
# handles auth automatically — no user API key needed).
VERTEX_AI_MODE = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("true", "1", "yes")

app = FastAPI(title="VC Shark Tank — ADK Multi-Agent Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    engine = "Google ADK + Vertex AI" if VERTEX_AI_MODE else "Google ADK"
    return {"status": "ok", "engine": engine}


@app.get("/config")
async def get_config():
    """Frontend calls this on load to know whether to show the API key modal."""
    return {
        "requiresApiKey": not VERTEX_AI_MODE,
        "vertexAI": VERTEX_AI_MODE,
    }


@app.websocket("/ws-simulate")
async def ws_simulate(websocket: WebSocket):
    """
    Main simulation WebSocket.

    Protocol (frontend → backend):
      {"action": "start",             "config": {...}, "apiKey": "AIza..."}
      {"action": "founder_response",  "text": "..."}        # REAL mode only
      {"action": "accept_offer",      "investorId": "..."}
      {"action": "counter_offer",     "text": "...", "investorId": "..."}
      {"action": "walk_away"}

    Protocol (backend → frontend):
      {"type": "pitch",             "sender", "senderName", "text"}
      {"type": "question",          "sender", "senderName", "text", "waitForResponse"}
      {"type": "founder_response",  "sender", "senderName", "text"}
      {"type": "banter",            "sender", "senderName", "text"}
      {"type": "exit_speech",       "sender", "senderName", "text"}
      {"type": "investor_update",   "investorId", "confidence", "trend", "status",
                                    "thoughtBubble", "strengths", "weaknesses",
                                    "risks", "agentState", "isThinking"}
      {"type": "founder_agent_state", "state"}
      {"type": "system_message",    "text"}
      {"type": "offer_speech",      "sender", "senderName", "text", "offer"}
      {"type": "bargaining_start",  "offers": [...]}
      {"type": "report",            "data": {...}}
      {"type": "agent_log",         "agentName", "message", "logType"}
      {"type": "error",             "message"}
    """
    await websocket.accept()

    # ── Wait for the initial "start" message ──────────────────────────────────
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
        msg = json.loads(raw)
    except (asyncio.TimeoutError, json.JSONDecodeError) as exc:
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        await websocket.close()
        return

    if msg.get("action") != "start":
        await websocket.send_text(json.dumps({"type": "error", "message": "Expected action=start"}))
        await websocket.close()
        return

    config  = msg.get("config", {})
    api_key = msg.get("apiKey", "")

    if not VERTEX_AI_MODE and not api_key:
        await websocket.send_text(json.dumps({"type": "error", "message": "No API key provided."}))
        await websocket.close()
        return

    # ── Create orchestrator ───────────────────────────────────────────────────
    orchestrator = SimulationOrchestrator(config=config, api_key=api_key)

    # ── Four concurrent tasks ─────────────────────────────────────────────────
    # 1. run_sim    — drives the ADK agents, pushes events into orchestrator._q
    # 2. send_events — drains _q and sends JSON to the browser
    # 3. recv_msgs  — reads incoming browser messages (responses, offers, etc.)
    # 4. keepalive  — pings every 25 s so proxies/browsers don't drop idle WS

    async def run_sim():
        try:
            await orchestrator.run()
        except Exception as exc:
            await orchestrator.event_queue.put({"type": "error", "message": str(exc)})
        finally:
            # Sentinel so send_events knows to stop
            await orchestrator.event_queue.put({"type": "__done__"})

    async def send_events():
        while True:
            event = await orchestrator.event_queue.get()
            if event.get("type") == "__done__":
                break
            try:
                await websocket.send_text(json.dumps(event))
            except Exception:
                break

    async def recv_msgs():
        try:
            async for raw_msg in websocket.iter_text():
                try:
                    incoming = json.loads(raw_msg)
                except json.JSONDecodeError:
                    continue

                action = incoming.get("action")
                if action == "ping":
                    pass  # keepalive reply — nothing to do
                elif action == "speech_done":
                    await orchestrator.receive_speech_done()
                elif action == "founder_response":
                    await orchestrator.receive_founder_response(incoming.get("text", ""))
                elif action in ("accept_offer", "counter_offer", "walk_away"):
                    if action == "accept_offer":
                        action_payload = {
                            "type":       "accept",
                            "investorId": incoming.get("investorId", ""),
                        }
                    elif action == "counter_offer":
                        action_payload = {
                            "type":       "counter",
                            "text":       incoming.get("text", ""),
                            "investorId": incoming.get("investorId", ""),
                        }
                    else:
                        action_payload = {"type": "walk_away"}
                    await orchestrator.receive_bargain_action(action_payload)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    async def keepalive():
        """Ping every 25 s to prevent proxies and browsers from closing idle connections."""
        try:
            while True:
                await asyncio.sleep(25)
                await websocket.send_text(json.dumps({"type": "ping"}))
        except Exception:
            pass

    run_task  = asyncio.create_task(run_sim())
    send_task = asyncio.create_task(send_events())
    recv_task = asyncio.create_task(recv_msgs())
    ka_task   = asyncio.create_task(keepalive())

    try:
        # Block until the WS is done from either side:
        #   send_task exits when simulation finishes (got __done__) OR WS send fails.
        #   recv_task exits when client disconnects.
        # run_task and ka_task are NOT in this set so a keepalive hiccup or
        # run_task finishing before send_task drains the queue never kills early.
        await asyncio.wait({send_task, recv_task}, return_when=asyncio.FIRST_COMPLETED)
    except Exception as exc:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass
    finally:
        # Cancel everything that is still running.
        for task in (run_task, send_task, recv_task, ka_task):
            task.cancel()
        await asyncio.gather(run_task, send_task, recv_task, ka_task, return_exceptions=True)
        try:
            await websocket.close()
        except Exception:
            pass


# ── Serve the built React frontend (present in production, absent in local dev) ──
# API routes above are matched first. This catch-all handles SPA navigation.
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    # Serve hashed JS/CSS assets
    assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_root():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Serve existing static files (favicon, etc.); fall back to index.html for SPA routes
        candidate = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    print(f"[ADK Server] Starting on http://{API_BACKEND_HOST}:{API_BACKEND_PORT}")
    uvicorn.run(
        "server:app",
        host=API_BACKEND_HOST,
        port=API_BACKEND_PORT,
        reload=False,
        log_level="info",
    )
