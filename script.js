import ws from "k6/ws";
import http from "k6/http";
import { check, sleep } from "k6";
import encoding from "k6/encoding";

export const options = {
  scenarios: {
    ramp_up_sessions: {
      executor: 'ramping-arrival-rate',
      startRate: 2,
      timeUnit: '1s',
      preAllocatedVUs: 300,
      maxVUs: 300,
      gracefulStop: '180s',
      stages: [
        { target: 2, duration: '150s' },
        { target: 0, duration: '1s' },
      ],
    },
  },
};

const API_BASE_URL = "https://api.engagexai.io";
const AUTH_TOKEN = "21de7e46e6861f7671a8af3b9a2e74a84fdac780";
const CHUNKS_TO_SEND = 7;
const CHUNK_INTERVAL = 9;

const videoChunk = open('test.webm', 'b');
const base64Chunk = encoding.b64encode(videoChunk);
const getBase64Chunk = () => base64Chunk;

function getRandomRoom() {
  const ROOMS = ["conference_room", "board_room_1", "board_room_2"];
  return ROOMS[Math.floor(Math.random() * ROOMS.length)];
}

export default function () {
  const room = getRandomRoom();
  const sessionName = `Test ${__VU}`;

  const createSessionRes = http.post(`${API_BASE_URL}/sessions/sessions/`, JSON.stringify({
    session_name: sessionName,
    session_type: "public",
    virtual_environment: room,
    goals: ["Testing"]
  }), {
    headers: {
      "Authorization": `Token ${AUTH_TOKEN}`,
      "Content-Type": "application/json",
    },
  });

  console.log(`[VU ${__VU}] Create session response: ${createSessionRes.status}`);
  console.log(`[VU ${__VU}] Response body: ${createSessionRes.body}`);

  check(createSessionRes, {
    "created session": (res) => res.status === 201,
  });

  const sessionId = createSessionRes.json("id");

  if (!sessionId) {
    console.log(`[VU ${__VU}] ❌ No sessionId returned — skipping this VU.`);
    return;
  }

  const url = `${API_BASE_URL.replace("http", "ws")}/ws/socket_server/?session_id=${sessionId}&room_name=${room}&ai_questions_enabled=true`;

  let chunksSent = 0;
  let chunkLoopEntered = false;
  const start = Date.now();

  console.log(`[VU ${__VU}] ⚙️ Starting WebSocket connection...`);

  const res = ws.connect(url, {}, function (socket) {
    console.log(`[VU ${__VU}] 🟢 Entered WebSocket handler`);

    socket.on("open", () => {
      console.log(`[VU ${__VU}] ✅ WebSocket connected to ${url}`);
    });

    socket.on("message", (msg) => {
      console.log(`[VU ${__VU}] 📩 Received: ${msg}`);
    });

    socket.on("error", (e) => {
      console.log(`[VU ${__VU}] ❌ WebSocket error: ${e && e.error ? e.error() : "unknown error"}`);
    });

    socket.on("close", (code, reason) => {
      if (chunksSent === 0) {
        console.log(`[VU ${__VU}] ❌ WebSocket closed — no chunks were sent`);
      } else {
        console.log(`[VU ${__VU}] 🔌 WebSocket closed after sending ${chunksSent} chunks. Code: ${code}, Reason: ${reason || "none"}`);
      }
    });

    for (let i = 0; i < CHUNKS_TO_SEND; i++) {
      chunkLoopEntered = true;
      try {
        const chunk = {
          type: "media",
          data: getBase64Chunk(),
          session_id: sessionId,
        };

        socket.send(JSON.stringify(chunk));
        chunksSent++;
        console.log(`[VU ${__VU}] ✅ Sent chunk ${i + 1}/${CHUNKS_TO_SEND} at ${Date.now() - start}ms`);
      } catch (err) {
        console.log(`[VU ${__VU}] ❌ Failed to send chunk ${i + 1}: ${err.message}`);
      }

      if (i === 2 || i === 5) {
        try {
          const question = {
            type: "audience_question",
            question: "How would you clarify your main idea?",
            session_id: sessionId,
          };
          socket.send(JSON.stringify(question));
          console.log(`[VU ${__VU}] 🎤 Sent audience question`);
        } catch (err) {
          console.log(`[VU ${__VU}] ❌ Failed to send audience question: ${err.message}`);
        }
      }

      if (i === Math.floor(CHUNKS_TO_SEND / 2)) {
        console.log(`[VU ${__VU}] ⏳ Halfway through sending chunks.`);
      }

      sleep(CHUNK_INTERVAL);
    }

    if (!chunkLoopEntered) {
      console.log(`[VU ${__VU}] ⚠️ Chunk loop never entered — possible early socket failure.`);
    }

    sleep(1); // Let everything flush
    socket.close();
  });

  if (!res || res.status !== 101) {
    console.log(`[VU ${__VU}] ❌ WebSocket connection failed or not upgraded. Status: ${res && res.status}`);
  }

  check(res, { "websocket connected": (r) => r && r.status === 101 });

  const duration = CHUNKS_TO_SEND * CHUNK_INTERVAL;
  const reportRes = http.post(`${API_BASE_URL}/sessions/sessions-report/${sessionId}/`, JSON.stringify({
    duration: duration
  }), {
    headers: {
      "Authorization": `Token ${AUTH_TOKEN}`,
      "Content-Type": "application/json",
    },
  });

  check(reportRes, {
    "report posted": (r) => r.status === 200 || r.status === 201,
  });

  console.log(`[VU ${__VU}] 📝 Final session report sent for session ${sessionId}`);
}
