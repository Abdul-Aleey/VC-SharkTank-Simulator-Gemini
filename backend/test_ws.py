"""Quick WebSocket smoke test for the ADK backend."""
import asyncio
import json
import websockets


async def test_bad_key():
    uri = "ws://127.0.0.1:5000/ws-simulate"
    async with websockets.connect(uri) as ws:
        config = {
            "mode": "ai", "rounds": 1, "language": "en",
            "startupName": "TestCo", "founderName": "Alex",
            "sector": "Tech", "askAmount": "1M USD", "askEquity": 10,
            "description": "AI-powered test startup", "personality": "excellent",
            "customTraits": ""
        }
        await ws.send(json.dumps({
            "action": "start",
            "config": config,
            "apiKey": "FAKE_KEY_SHOULD_FAIL"
        }))

        print("Waiting for events...")
        events = []
        try:
            for _ in range(15):
                msg = await asyncio.wait_for(ws.recv(), timeout=20)
                data = json.loads(msg)
                events.append(data["type"])
                info = (data.get("message") or data.get("text") or
                        data.get("state") or data.get("agentName") or "")
                print(f"  [{data['type']}] {str(info)[:100]}")
                if data["type"] in ("error", "report"):
                    break
        except asyncio.TimeoutError:
            print("  Timeout - no more events in 20s")

        print(f"\nEvents received: {events}")
        if "error" in events:
            print("PASS - bad key error caught and returned to client correctly")
        else:
            print("INFO - unexpected event sequence")


async def test_no_key():
    uri = "ws://127.0.0.1:5000/ws-simulate"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"action": "start", "config": {}, "apiKey": ""}))
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        assert data["type"] == "error", f"Expected error, got {data['type']}"
        assert "No API key" in data["message"]
        print("PASS - empty key rejected correctly")


async def test_health():
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:5000/health") as r:
            body = json.loads(r.read())
            assert body["engine"] == "Google ADK"
            print("PASS - health endpoint returns Google ADK engine")
    except Exception as e:
        print(f"FAIL - health: {e}")


if __name__ == "__main__":
    print("=== ADK Backend Tests ===\n")
    print("[1] Health endpoint")
    asyncio.run(test_health())
    print("\n[2] Empty API key")
    asyncio.run(test_no_key())
    print("\n[3] Invalid API key (should reach ADK agents then fail)")
    asyncio.run(test_bad_key())
    print("\nAll tests complete.")
