import base64
import json
import os
import time
import threading
import random
import requests
from locust import User, task, between, events
import websockets
import asyncio

API_BASE_URL = "http://engagex-1162743864.us-west-1.elb.amazonaws.com" # "https://api.engagexai.io"
AUTH_TOKEN = "21de7e46e6861f7671a8af3b9a2e74a84fdac780"
SAMPLE_WEBM_FILE = os.getenv("LOCUST_SAMPLE_WEBM", "sample-chunk.webm")
CHUNKS_TO_SEND = int(os.getenv("LOCUST_NUM_CHUNKS", 20))
CHUNK_INTERVAL = float(os.getenv("LOCUST_CHUNK_INTERVAL", 7))
ROOMS = ['conference_room', 'board_room_1', 'board_room_2']

def get_ws_protocol():
    return "ws" if API_BASE_URL.startswith("http://") else "wss"

def random_room():
    return random.choice(ROOMS)

def get_base64_chunk():
    try:
        with open(SAMPLE_WEBM_FILE, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return base64.b64encode(os.urandom(48000)).decode()

class MyWebSocketUser(User):
    wait_time = between(1, 2)
    # Add a class-level counter for unique session names
    instance_counter = 0

    def on_start(self):
        # Atomic increment for uniqueness in distributed (multi-process) Locust
        MyWebSocketUser.instance_counter += 1
        self.my_instance_num = MyWebSocketUser.instance_counter

        room = random_room()
        # Unique session name per user
        session_name = f"LoadTestSession {self.my_instance_num} {random.randint(100000, 999999)}" # extra random to be safe!
        headers = {'Content-Type': 'application/json', 'Authorization': f'Token {AUTH_TOKEN}'}
        resp = requests.post(
            f"{API_BASE_URL}/sessions/sessions/",
            json={
                "session_name": session_name,
                "session_type": "public",
                "virtual_environment": room,
                "goals": ["Testing"]
            },
            headers=headers
        )
        if resp.status_code != 201:
            raise Exception(f"Failed to create session: {resp.status_code} {resp.text}")
        self.session_id = resp.json()["id"]
        self.session_name = session_name
        self.room = room
        self.aiq = True
        self.start_time = time.time()

    @task
    def run_ws_session(self):
        thread = threading.Thread(target=self._run_ws_thread, daemon=True)
        thread.start()
        thread.join(timeout=(CHUNKS_TO_SEND * CHUNK_INTERVAL + 20))  # Enough timeout for full flow

    def _run_ws_thread(self):
        try:
            asyncio.run(self._ws_test_flow())
        except Exception as e:
            print(f"[Thread] Exception in asyncio.run: {e}")

    async def _ws_test_flow(self):
        ws_protocol = get_ws_protocol()
        ws_url = (
            f"{ws_protocol}://{API_BASE_URL.split('://')[1]}/ws/socket_server/"
            f"?session_id={self.session_id}&room_name={self.room}&ai_questions_enabled={str(self.aiq).lower()}"
        )
        print(f"[LocustUser {self.my_instance_num}] WebSocket connecting to: {ws_url}")
        try:
            async with websockets.connect(ws_url) as ws:
                print(f"[LocustUser {self.my_instance_num}] Connected OK")
                await self._websocket_flow(ws)
        except Exception as e:
            print(f"[LocustUser {self.my_instance_num}] WebSocket connection error: {e}")

    async def _websocket_flow(self, ws):
        b64chunk = get_base64_chunk()
        for i in range(CHUNKS_TO_SEND):
            to_send = {
                "type": "media",
                "data": b64chunk,
                "session_id": self.session_id
            }
            await ws.send(json.dumps(to_send))
            print(f"[LocustUser {self.my_instance_num}] Sent chunk {i+1}/{CHUNKS_TO_SEND}")
            # Optionally receive and print any responses
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                # print(f"[LocustUser {self.my_instance_num}] Received: {msg}")
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                pass

            # Occasionally send audience question
            if i == 2 or i == 5:
                question_msg = {
                    "type": "audience_question",
                    "question": "How would you clarify your main idea?",
                    "session_id": self.session_id
                }
                await ws.send(json.dumps(question_msg))
                print(f"[LocustUser {self.my_instance_num}] Sent audience question at chunk {i+1}")
            await asyncio.sleep(CHUNK_INTERVAL)
        await ws.close()
        print(f"[LocustUser {self.my_instance_num}] WebSocket session closed.")
        time.sleep(2)

        # Simulate report generation after disconnect
        self._trigger_report()

    def _trigger_report(self):
        duration = int(time.time() - self.start_time)
        print(f"[LocustUser {self.my_instance_num}] Posting session report for session_id={self.session_id} duration={duration}s")
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Token {AUTH_TOKEN}'
        }
        url = f"{API_BASE_URL}/sessions/sessions-report/{self.session_id}/"
        payload = {"duration": duration}
        try:
            resp = requests.post(url, headers=headers, json=payload)
            print(f"[LocustUser {self.my_instance_num}] Report POST status code: {resp.status_code}")
            try:
                report_data = resp.json()
            except Exception:
                report_data = resp.text
            print(f"[LocustUser {self.my_instance_num}] Report response: {json.dumps(report_data, indent=2) if isinstance(report_data, dict) else report_data}")
        except Exception as e:
            print(f"[LocustUser {self.my_instance_num}] Error posting report: {e}")