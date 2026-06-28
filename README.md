# VC Shark Tank Multi-Agent Simulator

A real-time Shark Tank pitch simulation powered by Google ADK. Five independent AI agents (one founder, four investors) run concurrently over WebSocket, each driven by Gemini. Every investor thinks, evaluates, and decides for themselves.

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
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

## Overview

You pitch your startup to four venture capitalists. They ask sharp, domain-specific questions based on your actual pitch. You answer (or the AI founder answers for you in autopilot mode). Their confidence meters shift in real time based on how well you performed in their area of expertise.

After all rounds finish, any investor above the confidence threshold moves to the offer round. Each shark generates their own deal terms using ADK: equity stake, royalty percentage on net sales, recoupment multiple, interest rate, board seat, whatever fits their style. When a deal is accepted, the full agreed terms go into the final investment memo.

The backend is Python FastAPI with Google ADK. The frontend is React with TypeScript. Speech synthesis gives every character a distinct voice, and the text and audio stay in sync through a serialised queue.

## How It Works

**Q&A phase:** Each round, the four investors take turns asking questions in randomised order. Questions come from each investor's own ADK agent, grounded in what was actually said in the pitch. After every answer, all active investors evaluate in parallel. Investors at or below 25% confidence drop out and deliver an exit speech; the rest continue.

**Offer phase:** Once all rounds finish, investors above the threshold enter the offer round. Each investor's ADK agent decides their own deal structure from scratch: no template, no hardcoded multipliers. Royalty is always expressed as a percentage on net sales. Recoupment is always a multiple of the investment. The offer card for each investor appears on screen only after their speech finishes.

**Bargaining:** In Real mode you can accept, counter, or walk away per shark. Counter-offers go to that specific shark's ADK agent, who responds in character. If they revise their terms, the card updates immediately. If they reject, their card disappears.

**Report:** The final memo generates after the deal is finalised and the founder's acceptance speech completes. The agreed term sheet in the memo includes the full structure: equity, royalty, recoupment multiple, interest rate, and any other conditions the shark included.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI orchestration | Google ADK (Agent Development Kit) v2.x |
| Language models | Gemini 2.5 Flash / 2.5 Pro / 3.5 Flash |
| Backend | Python 3.11, FastAPI, uvicorn, WebSocket |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Speech | Web Speech API (SpeechSynthesis + SpeechRecognition) |
| Deployment | Docker (multi-stage), Google Cloud Run, Cloud Build |

## Project Structure

```
vc-shark-tank-multi-agent-simulator/
├── Dockerfile                   # Multi-stage: Node builds React, Python serves both
├── cloudbuild.yaml              # Cloud Build config for automated Cloud Run deploys
│
├── backend/
│   ├── server.py                # FastAPI app, WebSocket handler, static file serving
│   ├── requirements.txt
│   ├── .env.local               # Local overrides (not committed)
│   └── simulation/
│       ├── orchestrator.py      # Full simulation logic: pitch, Q&A, bargaining, report
│       └── agents.py            # ADK agent definitions, personas, runner/session setup
│
└── frontend/
    ├── App.tsx                  # Root: state, speech queue, WebSocket event handlers
    ├── types.ts                 # TypeScript interfaces and enums
    ├── constants.ts             # Investor profiles, translations, presets
    └── components/
    │   ├── SimulationScreen.tsx # Live view: investor cards, chat, input, offer panel
    │   ├── InvestorCard.tsx     # Confidence bar, status, thought bubble
    │   ├── ReportScreen.tsx     # Final VC memo with full term sheet and shark feedback
    │   ├── SetupScreen.tsx      # Config form and investor preview
    │   ├── Header.tsx
    │   └── ApiKeyModal.tsx
    └── services/
        ├── simulationService.ts # WebSocket client
        └── geminiService.ts     # API key verification
```

## Investor Personas

| Name | Focus |
|------|-------|
| Vincent Vance | Finance, margins, valuation, unit economics |
| Marcus Sterling | Technology, architecture, IP, defensibility |
| Beatrice Belmont | Branding, leadership, team, customer retention |
| Leona Lyonne | Go-to-market, distribution, operations, growth |

Each investor runs as an independent ADK agent with its own session. Their state, memory, and decisions are fully isolated.

## Simulation Modes

**Real Entrepreneur:** You play the founder. After each question finishes speaking, the input unlocks. Type your answer or use voice:

- Click **Speak** to activate the microphone. It stays active until you click Speak again or click Send.
- Click **Send** to stop the mic and submit what you spoke or typed.

You can also just type and click Send without using the mic.

**AI Autopilot:** The AI founder agent handles everything. Useful for demos or watching how the investors respond to different startup profiles without typing.

## Model Selection

Three Gemini models are available:

| Model | Notes |
|-------|-------|
| `gemini-2.5-flash` | Default. Fast and cost-effective. |
| `gemini-2.5-pro` | Best reasoning and dialogue depth. |
| `gemini-3.5-flash` | Frontier model. Falls back to 2.5 Flash on Vertex AI if unavailable. |

When a fallback happens, the backend notifies the frontend and the model badge updates automatically.

## Prerequisites

- Python 3.11+
- Node.js 20+
- A Gemini API key from Google AI Studio (for local dev), or a Google Cloud project with Vertex AI enabled (for Cloud Run)

## Local Development

**1. Clone and install**

```bash
git clone https://github.com/Abdul-Aleey/VC-SharkTank-Simulator-Gemini.git
cd vc-shark-tank-multi-agent-simulator
```

**2. Backend**

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env.local`:

```
API_BACKEND_PORT=5000
GOOGLE_API_KEY=AIza...your-key-here
```

Start it:

```bash
uvicorn server:app --host 127.0.0.1 --port 5000 --reload
```

**3. Frontend**

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```
VITE_BACKEND_URL=http://localhost:5000
```

Start it:

```bash
npm run dev
```

Open `http://localhost:5173`. The API key modal will appear on first load.

## Environment Variables

**Backend**

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BACKEND_PORT` | `5000` | Port for local uvicorn |
| `API_BACKEND_HOST` | `127.0.0.1` | Host for local uvicorn |
| `GOOGLE_API_KEY` | | Gemini API key (local mode) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` | Set to `true` for Cloud Run / Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | | GCP region, e.g. `asia-northeast1` |
| `PORT` | `8080` | Injected by Cloud Run automatically |

**Frontend**

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_BACKEND_URL` | same origin | Backend URL. Leave unset in unified Cloud Run deployment. |

## Deployment to Cloud Run

The project runs as a single Cloud Run service: one Docker image, one URL, serving both the React frontend and the FastAPI backend.

**Step 1: Enable APIs in your GCP project**

Cloud Run API, Cloud Build API, Vertex AI API, Artifact Registry API.

**Step 2: Grant the service account permissions**

Find `PROJECT_NUMBER-compute@developer.gserviceaccount.com` in IAM and grant it the **Agent Platform Express User** role.

**Step 3: Create the Cloud Run service**

1. Cloud Run > Create Service > Continuously deploy from a repository
2. Connect to the GitHub repo
3. Set build configuration to use `cloudbuild.yaml`
4. Region: `asia-northeast1` or your preference
5. Set environment variables:
   ```
   GOOGLE_GENAI_USE_VERTEXAI=true
   GOOGLE_CLOUD_PROJECT=your-project-id
   GOOGLE_CLOUD_LOCATION=asia-northeast1
   ```
6. Memory: 1 GiB minimum
7. Concurrency: 10, Min instances: 1, Max: 5
8. Allow unauthenticated invocations

**Step 4: Verify**

```bash
curl https://your-service.run.app/health
# {"status": "ok", "engine": "Google ADK + Vertex AI"}

curl https://your-service.run.app/config
# {"requiresApiKey": false, "vertexAI": true}
```

## WebSocket Protocol

All simulation traffic runs over a single WebSocket at `/ws-simulate`.

**Client to server:**

| Action | Payload | When |
|--------|---------|------|
| `start` | `{config, apiKey}` | First message on connect |
| `founder_response` | `{text}` | Real mode: founder's answer |
| `speech_done` | `{}` | After founder TTS ends (or immediately in Real mode) |
| `accept_offer` | `{investorId}` | Bargaining phase |
| `counter_offer` | `{text, investorId}` | Bargaining phase |
| `walk_away` | `{}` | Bargaining phase |

**Server to client:**

| Type | Key fields | Notes |
|------|-----------|-------|
| `model_update` | `model` | Actual model in use, sent at start |
| `pitch` | `sender, text` | Founder's opening pitch |
| `question` | `sender, text, waitForResponse` | Investor question |
| `founder_response` | `sender, text` | Founder's answer |
| `banter` | `sender, text` | Short investor reaction, never a question |
| `exit_speech` | `sender, text` | Departure speech when confidence drops out |
| `investor_update` | `investorId, confidence, trend, status, ...` | After every evaluation |
| `system_message` | `text` | Round info, deal results, etc. |
| `phase_change` | `phase` | ONGOING / BARGAINING / DONE |
| `offer_speech` | `sender, text, offer` | Investor's spoken offer; card appears after TTS |
| `bargaining_start` | `offers[], isRevision` | Initial panel or updated offers after counter |
| `report` | `data` | Final memo, only after phase is DONE and all TTS drains |
| `agent_log` | `agentName, message` | Backend debug log |
| `error` | `message` | Unrecoverable error |

## Troubleshooting

**Simulation stuck at initialising**

Check Cloud Run logs for Python exceptions. The most common cause is a missing IAM role or an environment variable not set correctly. Verify `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, and `GOOGLE_CLOUD_LOCATION` are all present.

**API key modal shows up in Vertex AI mode**

The `/config` endpoint is returning `requiresApiKey: true`. This means `GOOGLE_GENAI_USE_VERTEXAI` is not being picked up. Re-deploy after confirming the env var is set in the Cloud Run service configuration.

**Gemini 3.5 Flash not working on Vertex AI**

Expected. The backend falls back to `gemini-2.5-flash` automatically and sends a `model_update` event. The badge in the frontend updates to show what model is actually running.

**Speech not playing**

Web Speech API needs a user gesture to initialise on some browsers. Click anywhere on the page before the simulation starts.

**UnicodeEncodeError on Windows**

Avoid non-ASCII characters in Python log/print statements when running locally on Windows.
