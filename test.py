import asyncio
import websockets

async def test_ws():
    wsurl = "wss://api.engagexai.io/ws/socket_server/?session_id=739&room_name=board_room_1&ai_questions_enabled=true"
    try:
        async with websockets.connect(wsurl) as ws:
            print("Connected OK")
    except Exception as e:
        print("WS connection failed:", e)

asyncio.run(test_ws())