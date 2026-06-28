# VC Shark Tank Multi-Agent Simulator

A real-time Shark Tank pitch simulation powered by Google ADK (Agent Development Kit) with five independent AI agents — one founder and four investor personas — communicating over WebSocket and driven by Gemini language models.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Investor Personas](#investor-personas)
- [Simulation Modes](#simulation-modes)
- [Model Selection](#model-selection)
- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Environment Variables](#environment-variables)
- [Deployment to Cloud Run](#deployment-to-cloud-run)
- [WebSocket Protocol](#websocket-protocol)
- [Troubleshooting](#troubleshooting)

---

## Overview

This simulator puts you (or an AI autopilot) in front of four ruthless venture capitalists. You pitch your startup, field sharp questions from each investor, watch their confidence meters rise and fall in real time, negotiate term sheets, and receive a final VC evaluation memo — all powered by five simultaneously running Gemini agents.

The backend is a Python FastAPI server that orchestrates Google ADK agents. The frontend is a React + TypeScript SPA that visualises the simulation over a WebSocket connection. Both are packaged into a single Docker image for unified deployment to Cloud Run.

---

## Features

- **5 independent ADK agents** — each investor and the AI founder run in separate sessions with isolated state
- **Parallel evaluation** — all active investors evaluate the founder's response simultaneously using `asyncio.gather()`
- **Dynamic exit speeches** — departing investors generate contextual exit lines from actual conversation history, not hardcoded text
- **Random question order** — question sequence is shuffled each round so no investor always goes first
- **Real-time speech synthesis** — each character has a distinct voice; text and audio advance together via a serialised Promise queue
- **Two founder modes** — you type/speak your own answers (Real Entrepreneur) or let the AI founder handle everything (AI Autopilot)
- **Bargaining phase** — after all rounds complete, qualifying investors present their offers one by one. Accept, counter-offer (routed to that specific shark's ADK agent who evaluates in their own voice), or walk away
- **Founder acceptance speech** — the founder's ADK agent generates an acceptance line naming the shark when a deal is sealed
- **Final evaluation memo** — detailed VC report with readiness score, verdict, risk grid, and per-investor feedback
- **Bilingual** — full English and Japanese support throughout
- **Gemini model selector** — choose between Gemini 2.5 Flash, 2.5 Pro, or 3.5 Flash per session
- **Dual auth modes** — Gemini API key (local dev / standalone) or Vertex AI service account (Cloud Run / GCP)
- **Automatic model fallback** — if Gemini 3.5 Flash is unavailable on Vertex AI, the backend silently falls back to 2.5 Flash and notifies the frontend
- **Unified deployment** — single Docker image serves both the React frontend and the FastAPI backend

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI orchestration | [Google ADK](https://google.github.io/adk-docs/) (Agent Development Kit) v2.x |
| Language models | Gemini 2.5 Flash / 2.5 Pro / 3.5 Flash via Vertex AI or AI Studio |
| Backend | Python 3.11, FastAPI, uvicorn, WebSocket |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, lucide-react |
| Speech | Web Speech API (SpeechSynthesis + SpeechRecognition) |
| Deployment | Docker (multi-stage), Google Cloud Run, Cloud Build |
| Auth (production) | Vertex AI via Cloud Run service account (ADC) |
| Auth (local) | Gemini API key via `GOOGLE_API_KEY` |

---

## Project Structure

```
vc-shark-tank-multi-agent-simulator/
├── Dockerfile                   # Multi-stage: Node builds React, Python serves both
├── cloudbuild.yaml              # Cloud Build config for automated Cloud Run deploys
├── .gitignore
│
├── backend/
│   ├── server.py                # FastAPI app: /health, /config, /ws-simulate, static files
│   ├── requirements.txt         # Python dependencies
│   ├── .env.local               # Local overrides (not committed)
│   └── simulation/
│       ├── __init__.py
│       ├── orchestrator.py      # SimulationOrchestrator: drives the full pitch flow
│       └── agents.py            # ADK Agent definitions, personas, Runner/session builders
│
└── frontend/
    ├── index.html
    ├── index.tsx                # React entry point
    ├── App.tsx                  # Root component: state, speech queue, WebSocket handlers
    ├── types.ts                 # TypeScript enums and interfaces
    ├── constants.ts             # Investor profiles, translations, presets
    ├── vite.config.ts
    ├── package.json
    ├── .env                     # Local dev: VITE_BACKEND_URL=http://localhost:5000
    ├── .env.cloud               # Cloud Run URL override
    └── components/
    │   ├── Header.tsx           # Top bar: language toggle, API status, restart
    │   ├── ApiKeyModal.tsx      # Gemini API key entry and verification modal
    │   ├── SetupScreen.tsx      # Simulation config form + investor preview panel
    │   ├── SimulationScreen.tsx # Live pitch view: investor cards, chat, input dock
    │   ├── InvestorCard.tsx     # Individual investor: confidence bar, status, thought bubble
    │   └── ReportScreen.tsx     # Final VC evaluation memo with download
    └── services/
        ├── simulationService.ts # WebSocket client (SimulationWebSocket class)
        └── geminiService.ts     # Browser-side: API key verification only
```

---

## Investor Personas

| ID | Name | Emoji | Focus |
|----|------|-------|-------|
| `vincent` | Vincent Vance | 📊 | Finance, Margins, Valuation, Profitability |
| `marcus` | Marcus Sterling | 🛡️ | Technology, Architecture, Defensibility, Scale |
| `beatrice` | Beatrice Belmont | 📈 | Branding, Leadership, Marketing, Trust |
| `leona` | Leona Lyonne | 👥 | Go-To-Market, Operations, Mass Appeal, Growth |

Each investor runs as an independent ADK `Agent` with its own `InMemorySession`, so their state, memory, and investment logic are completely isolated from one another.

---

## Simulation Modes

### Real Entrepreneur Mode
You play the founder. After each investor question is read aloud, the input field unlocks and you type (or dictate via microphone) your response. The simulation waits for your input before continuing.

### AI Autopilot Mode
An ADK-powered Founder Agent generates all pitches and responses automatically. You watch the full simulation unfold without typing anything. Useful for demos or exploring how the investors react to different startup profiles.

---

## Model Selection

Three Gemini models are available at setup:

| Model | Badge | Vertex AI | Notes |
|-------|-------|-----------|-------|
| `gemini-2.5-flash` | Balanced | ✅ | Default. Fast, cost-effective. |
| `gemini-2.5-pro` | Highest Quality | ✅ | Best reasoning and dialogue depth. |
| `gemini-3.5-flash` | Latest | ⚠️ | Frontier model. Backend auto-falls back to 2.5 Flash on Vertex AI if unavailable. |

When a fallback occurs, the backend emits a `model_update` event so the badge and footer in the frontend update automatically to show the actual model in use.

---

## Prerequisites

- **Python 3.11+** with `pip`
- **Node.js 20+** with `npm`
- One of:
  - A **Gemini API key** from [Google AI Studio](https://aistudio.google.com/) (local dev)
  - A **Google Cloud project** with Vertex AI API enabled (Cloud Run deployment)

---

## Local Development

### 1. Clone and install

```bash
git clone https://github.com/Abdul-Aleey/VC-SharkTank-Simulator-Gemini.git
cd vc-shark-tank-multi-agent-simulator
```

### 2. Backend setup

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env.local`:
```env
API_BACKEND_PORT=5000
GOOGLE_API_KEY=AIza...your-key-here...
```

Start the backend:
```bash
uvicorn server:app --host 127.0.0.1 --port 5000 --reload
```

The backend starts at `http://localhost:5000`. Test it:
```bash
curl http://localhost:5000/health
curl http://localhost:5000/config
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

Create `frontend/.env`:
```env
VITE_BACKEND_URL=http://localhost:5000
```

Start the dev server:
```bash
npm run dev
```

Open `http://localhost:5173` in your browser.

### 4. Running the simulation

1. The API key modal appears on first load (Vertex AI mode skips this)
2. Enter your Gemini API key — it is verified with a test call before being saved
3. Configure your startup: name, sector, funding ask, equity offer, description
4. Choose founder mode (Real or AI Autopilot) and number of Q&A rounds
5. Select a Gemini model
6. Click **Launch Simulation**

---

## Environment Variables

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BACKEND_PORT` | `5000` | Port for local uvicorn server |
| `API_BACKEND_HOST` | `127.0.0.1` | Host for local uvicorn server |
| `GOOGLE_API_KEY` | — | Gemini API key (local / standalone mode) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` | Set to `true` to use Vertex AI (Cloud Run) |
| `GOOGLE_CLOUD_PROJECT` | — | GCP project ID (required when Vertex AI enabled) |
| `GOOGLE_CLOUD_LOCATION` | — | GCP region, e.g. `asia-northeast1` |
| `PORT` | `8080` | Cloud Run injects this automatically |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_BACKEND_URL` | `window.location.origin` | Backend base URL. Omit in unified Cloud Run deployment (same origin). |

---

## Deployment to Cloud Run

The project deploys as a **single unified Cloud Run service** — one Docker image, one URL, serving both the React frontend and the FastAPI backend.

### Step 1 — Enable APIs

In your GCP project, enable:
- Cloud Run API
- Cloud Build API
- Vertex AI API
- Artifact Registry API

### Step 2 — Grant IAM permissions

The Cloud Run service account needs:
- **Agent Platform Express User** role (for Vertex AI / ADK access)

In Cloud Console → IAM → find the service account `PROJECT_NUMBER-compute@developer.gserviceaccount.com` and grant the role.

### Step 3 — Deploy via Cloud Run Connect Repository

1. Go to **Cloud Run → Create Service**
2. Choose **Continuously deploy from a repository**
3. Connect to GitHub repo `Abdul-Aleey/VC-SharkTank-Simulator-Gemini`
4. Set **Build configuration** to use the `cloudbuild.yaml` at repo root
5. Region: `asia-northeast1` (or your preferred region)
6. Set environment variables:
   ```
   GOOGLE_GENAI_USE_VERTEXAI=true
   GOOGLE_CLOUD_PROJECT=your-project-id
   GOOGLE_CLOUD_LOCATION=asia-northeast1
   ```
7. Memory: **1 GiB** minimum (ADK agents need headroom)
8. Concurrency: `10`, Min instances: `1`, Max instances: `5`
9. Allow unauthenticated invocations

### Step 4 — Verify

```bash
curl https://your-service.run.app/health
# → {"status": "ok", "engine": "Google ADK + Vertex AI"}

curl https://your-service.run.app/config
# → {"requiresApiKey": false, "vertexAI": true}
```

The frontend at the root URL (`/`) should load without an API key modal.

### Build process (cloudbuild.yaml)

```
Stage 1 (Node 20): npm install + npm run build → /app/frontend/dist
Stage 2 (Python 3.11): pip install requirements → copy backend → copy dist as static/
CMD: uvicorn server:app --host 0.0.0.0 --port $PORT
```

---

## WebSocket Protocol

The simulation runs over a single WebSocket connection at `/ws-simulate`.

### Client → Server

| Action | Payload | When |
|--------|---------|------|
| `start` | `{config, apiKey}` | On connect, always first |
| `founder_response` | `{text}` | Real mode: after each investor question |
| `speech_done` | `{}` | After founder-response TTS finishes (or immediately in Real mode); unblocks investor evaluation |
| `accept_offer` | `{investorId}` | Bargaining phase |
| `counter_offer` | `{text, investorId}` | Bargaining phase — routed to that specific shark's agent |
| `walk_away` | `{}` | Bargaining phase |

### Server → Client (event types)

| Type | Key fields | Description |
|------|-----------|-------------|
| `model_update` | `model` | Actual model in use (sent at simulation start, reflects any fallback) |
| `pitch` | `sender, senderName, text` | Founder's opening pitch |
| `question` | `sender, senderName, text, waitForResponse` | Investor question; `waitForResponse=true` in Real mode |
| `founder_response` | `sender, senderName, text` | Founder's answer |
| `banter` | `sender, senderName, text` | Spontaneous investor comment (25% chance per exchange) |
| `exit_speech` | `sender, senderName, text` | Dynamic departure speech when confidence ≤ 25 |
| `investor_update` | `investorId, confidence, trend, status, agentState, thoughtBubble, …` | Full investor state after every evaluation |
| `founder_agent_state` | `state` | PITCHING / IDLE |
| `system_message` | `text` | Narrative messages (round start, deal result, etc.) |
| `phase_change` | `phase` | Simulation phase transition: `ONGOING` → `BARGAINING` → `DONE` |
| `offer_speech` | `sender, senderName, text, offer` | Investor presents term sheet |
| `bargaining_start` | `offers[]` | All term sheets ready, waiting for user action |
| `report` | `data` | Final evaluation memo; only emitted after phase reaches `DONE` |
| `agent_log` | `agentName, message, logType` | ADK orchestrator debug log |
| `error` | `message` | Unrecoverable error |

---

## Troubleshooting

### `SimulationOrchestrator object has no attribute model`
Ensure you are on the latest code — this was a bug where `self.model` was referenced in the `__init__` auth block before it was assigned. Fixed by moving the assignment above the auth block.

### Simulation stuck at "Initializing 5-agent multi-agent system"
1. Check Cloud Run logs for Python exceptions
2. Verify `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, and `GOOGLE_CLOUD_LOCATION` are set in the service's environment variables
3. Confirm the service account has the **Agent Platform Express User** IAM role

### Frontend shows API key modal even in Vertex AI mode
`/config` is returning `{"requiresApiKey": true, "vertexAI": false}`. This means `GOOGLE_GENAI_USE_VERTEXAI` is not being read. Re-deploy after verifying the env var is set in Cloud Run.

### `UnicodeEncodeError` on Windows
Avoid non-ASCII characters (e.g. em dashes `—`) in terminal print statements in Python. Use plain ASCII hyphens in log messages.

### Gemini 3.5 Flash not working on Vertex AI
Expected behaviour. The backend falls back to `gemini-2.5-flash` automatically and emits a `model_update` event. The frontend badge updates to reflect the actual model.

### Speech not playing in browser
Web Speech API requires a user gesture to initialise on some browsers. Click anywhere on the page before the simulation starts, or toggle the mute button once to initialise the audio context.
