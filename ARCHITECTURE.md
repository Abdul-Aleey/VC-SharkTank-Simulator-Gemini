# Architecture — VC Shark Tank Multi-Agent Simulator

This document describes the system architecture, agent design, data flow, event protocol, and deployment topology of the simulator.

---

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [Multi-Agent Design](#multi-agent-design)
  - [Agent Inventory](#agent-inventory)
  - [Why Independent Sessions?](#why-independent-sessions)
  - [Parallelism Strategy](#parallelism-strategy)
- [Backend Internals](#backend-internals)
  - [SimulationOrchestrator](#simulationorchestrator)
  - [Simulation Phases](#simulation-phases)
  - [Confidence & Status Model](#confidence--status-model)
  - [Banter Guard](#banter-guard)
  - [Exit Speech Generation](#exit-speech-generation)
  - [Bargaining Logic](#bargaining-logic)
  - [Report Generation](#report-generation)
- [Frontend Internals](#frontend-internals)
  - [Component Tree](#component-tree)
  - [State Ownership](#state-ownership)
  - [Speech Queue System](#speech-queue-system)
  - [Real Mode Input Flow](#real-mode-input-flow)
  - [Model Fallback Sync](#model-fallback-sync)
- [WebSocket Event Flow](#websocket-event-flow)
  - [Full Sequence Diagram](#full-sequence-diagram)
- [Auth & Configuration](#auth--configuration)
  - [API Key Mode (Local/Standalone)](#api-key-mode-localstandalone)
  - [Vertex AI Mode (Cloud Run)](#vertex-ai-mode-cloud-run)
  - [/config Endpoint](#config-endpoint)
- [Deployment Architecture](#deployment-architecture)
  - [Unified Docker Image](#unified-docker-image)
  - [Cloud Build Pipeline](#cloud-build-pipeline)
  - [Cloud Run Service Layout](#cloud-run-service-layout)
- [Key Design Decisions](#key-design-decisions)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (React SPA)                       │
│                                                                  │
│  SetupScreen → SimulationScreen → ReportScreen                  │
│                     │        ▲                                   │
│          WebSocket  │        │  Events (JSON)                   │
│          (ws://…/ws-simulate)                                    │
└──────────────────── │ ───────│──────────────────────────────────┘
                       │        │
┌──────────────────── ▼ ───────│──────────────────────────────────┐
│                    FastAPI Backend (server.py)                    │
│                                                                  │
│   /health   /config   /ws-simulate   /assets   / (SPA fallback) │
│                           │                                      │
│              ┌────────────▼────────────┐                        │
│              │  SimulationOrchestrator │                        │
│              │  (orchestrator.py)      │                        │
│              └──┬──────────────────────┘                        │
│                 │                                                │
│    ┌────────────┼────────────────────────────┐                  │
│    ▼            ▼            ▼               ▼                  │
│ FounderAgent VincentAgent MarcusAgent BeatriceAgent LeonaAgent  │
│ (ADK Agent)  (ADK Agent)  (ADK Agent)  (ADK Agent)  (ADK Agent)│
│    │              │            │              │           │      │
│    └──────────────┴────────────┴──────────────┴───────────┘     │
│                         InMemorySessionService                   │
│                         (one session per agent)                  │
│                                                                  │
│              ┌──────────────────────────────┐                   │
│              │  Gemini API / Vertex AI       │                   │
│              │  (gemini-2.5-flash / pro /    │                   │
│              │   gemini-3.5-flash)           │                   │
│              └──────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Multi-Agent Design

### Agent Inventory

| Agent | Count | Purpose | Session |
|-------|-------|---------|---------|
| FounderAgent | 1 | Generates opening pitch and answers investor questions (AI Autopilot mode only) | `founder_user` |
| VincentAgent | 1 | Asks finance-focused questions, evaluates responses, generates exit speech if needed | `vincent_user` |
| MarcusAgent | 1 | Asks tech/IP questions, evaluates independently | `marcus_user` |
| BeatriceAgent | 1 | Asks branding/leadership questions, evaluates independently | `beatrice_user` |
| LeonaAgent | 1 | Asks go-to-market questions, evaluates independently | `leona_user` |

Every agent is a `google.adk.agents.Agent` instance with:
- A unique `name` (used as identifier in ADK internals)
- A model string (same Gemini model for all 5 agents in a session, set by user choice)
- A `description` and `instruction` (persona definition)

Each agent has its own `Runner` and its own `InMemorySession`. This means each investor accumulates independent memory and state across the simulation — they do not share a session with each other.

### Why Independent Sessions?

ADK sessions carry conversation history and state for a single agent. If all investors shared one session, their memories would bleed into each other — Vincent would "remember" questions Beatrice asked as if he asked them. Separate sessions keep each investor's perspective isolated and authentic.

### Parallelism Strategy

The orchestrator uses several layers of parallelism with per-investor session locks to prevent concurrent ADK session corruption:

**1. Parallel Investor Evaluation (after every founder response)**
```python
tasks   = [self._evaluate_single_investor(inv_id, response, round_num) for inv_id in active]
results = await asyncio.gather(*tasks)
```
All active investor agents run their evaluation prompts simultaneously via `asyncio.gather`. `round_num` is passed explicitly (not derived from per-investor `questionsAsked`) so every agent sees the same correct round context regardless of ask order within the round.

**2. Parallel Banter + Next-Question Prefetch**
```python
_, prefetched_q = await asyncio.gather(
    self._maybe_banter(),
    self._generate_question(next_asker),
)
```
After evaluation, the next investor's question is generated in parallel with banter generation. `_investor_locks` (one `asyncio.Lock` per investor) serialise any case where banter randomly picks the same investor as `next_asker`, preventing concurrent session access. The prefetched question is used immediately at the start of the next exchange, eliminating a sequential ADK call from the hot path.

**3. Parallel Exit Speech Generation (when multiple investors drop out)**
```python
exit_tasks = [self._generate_exit_speech(inv_id) for inv_id in exit_speeches]
exit_texts = await asyncio.gather(*exit_tasks)
```
When multiple investors hit the confidence threshold simultaneously, their exit speeches are generated in parallel, then emitted to the frontend sequentially.

**4. Parallel Offer Term Generation (bargaining phase)**
```python
results = await asyncio.gather(
    *[self._generate_single_offer_terms(inv_id, conf, ask_amount, ask_equity)
      for inv_id in solo_investors],
    return_exceptions=True,
)
```
All individual investor offer terms are generated in parallel. `return_exceptions=True` means one investor's ADK failure doesn't cancel the others — each failure falls back to the founder's original ask equity. Offer *speeches* are generated and emitted sequentially after this (one at a time, so they arrive in order).

**Sequential operations (intentional):**
- Questions: each investor asks one at a time (structured turn-taking)
- Founder responses: one at a time (single speaker)
- Evaluate → banter+prefetch: evaluate must complete before banter starts so exit decisions are known before picking banter speaker
- Report feedback: collected in parallel (`asyncio.gather`) but merged into a single report object

**Session safety:**
Every `_run_investor_agent` call acquires `_investor_locks[inv_id]` before using that investor's `Runner` and `InMemorySession`. This prevents `asyncio.gather` from sending two concurrent prompts to the same session, which would corrupt session history. All ADK calls also have a 45 s `asyncio.wait_for` timeout so a hung Gemini API call surfaces as a warning log rather than a silent freeze.

---

## Backend Internals

### SimulationOrchestrator

`backend/simulation/orchestrator.py` — one instance per WebSocket connection.

**Initialisation order** (critical — `self.model` must be assigned before the auth block):
```
1. self.config, self.language, self.mode, self.rounds, self.model   ← assigned first
2. Auth block: Vertex AI env var or GOOGLE_API_KEY                  ← reads self.model
3. self._model_fallback flag set (if vertex + 3.5-flash selected)
4. Build ADK agents + runners + session service
5. investor_states dict initialised (confidence=50 for all 4)
6. Asyncio queues created: _q (events), _founder_response, _bargain_action
```

**Three concurrent tasks per WebSocket connection:**
```
asyncio.gather(
    run_sim(),      # orchestrator.run() → pushes events into _q
    send_events(),  # drains _q → sends JSON frames over WebSocket
    recv_msgs(),    # reads incoming WebSocket messages → routes to orchestrator
)
```

### Simulation Phases

```
run()
  ├─ _init_sessions()              # await create_session() for each of 5 agents
  ├─ emit("model_update", model)   # tells frontend the actual model (after any fallback)
  ├─ _phase_pitch()                # founder delivers opening pitch
  │
  ├─ for round in 1..N:
  │   ├─ active = [investors with status==ACTIVE]
  │   ├─ random.shuffle(active)    # randomise question order each round
  │   ├─ prefetched_questions = {}
  │   │
  │   └─ for idx, inv_id in enumerate(active):
  │       ├─ use prefetched_questions[inv_id] OR _generate_question(inv_id)
  │       │     (question history injected into prompt to prevent repetition)
  │       ├─ emit("question")
  │       ├─ wait for founder response   (AI: _generate_founder_response | REAL: queue.get())
  │       ├─ emit("founder_response")
  │       ├─ _wait_for_speech_done()             # blocks until frontend TTS complete (omitted on LAST exchange so bargaining starts immediately)
  │       ├─ _parallel_evaluate(response, round_num)   → all active agents evaluate concurrently
  │       │   ├─ asyncio.gather(*[_evaluate_single_investor(inv, response, round_num)])
  │       │   ├─ update confidence, trend, thoughtBubble, strengths, weaknesses, risks
  │       │   ├─ check OUT threshold (≤25) → _generate_exit_speech() in parallel
  │       │   └─ emit investor_update for all
  │       └─ asyncio.gather(_maybe_banter(), _generate_question(next_asker))
  │             # prefetch next question in parallel with banter (session-locked)
  │
  └─ _phase_bargaining()
      ├─ _build_offers(qualifying investors)
      ├─ emit offer_speech + bargaining_start
      ├─ wait for bargain_action (accept / counter / walk_away)
      └─ _generate_report()
          ├─ asyncio.gather(*[_generate_investor_feedback()])  # all 4 in parallel
          └─ emit("report")
```

### Confidence & Status Model

Each investor starts at `confidence = 50` and updates after every founder response.

| Threshold | When | Effect |
|-----------|------|--------|
| `confidence ≤ 25` | During rounds | `status = OUT`, exit speech generated, investor stops participating |
| `confidence > 25` | After all rounds | `status = INVEST` set in `_phase_bargaining()` before offer generation |
| `25 < confidence` | During rounds | `status = ACTIVE`, investor keeps asking questions every round |

Critically, **INVEST status is never set during Q&A rounds**. Investors whose confidence exceeds 85 mid-round stay ACTIVE and keep asking questions. Only after all rounds complete does `_phase_bargaining()` scan for qualifying investors (confidence > 25, not OUT) and set their status to INVEST before generating offers. This ensures all rounds always complete in full before the offer phase begins.

The confidence value is set entirely by the investor's own ADK agent — the orchestrator asks each agent to return a JSON object including a `confidence` integer. The agent decides how convincing the founder's answer was relative to their focus area.

`trend` is derived locally: `new_confidence - old_confidence`. A positive trend (green arrow) means the investor liked the last answer; negative means it hurt.

### Speech-Done Synchronisation

After the backend emits `founder_response`, it blocks on `_wait_for_speech_done()` before running investor evaluation. The frontend sends `{action: "speech_done"}` after TTS finishes (AI mode) or immediately after displaying the text (Real mode, no TTS). This ensures all investor agents evaluate only after they have "heard" the full answer.

`_speech_done_q` is an `asyncio.Queue` (not an Event). Signals are enqueued and consumed in order — so a `speech_done` that arrives while the backend is processing evaluate/banter/prefetch is never lost. A 60 s timeout prevents permanent block if the frontend disconnects mid-simulation.

### Simulation Phase State Machine

The backend tracks `_sim_phase` (`ONGOING` → `BARGAINING` → `DONE`) and emits `phase_change` events at each transition:

| Phase | When set | Effect |
|-------|----------|--------|
| `ONGOING` | Simulation start | Report generation blocked |
| `BARGAINING` | After all Q&A rounds complete | Offer phase begins |
| `DONE` | At start of `_generate_report()` | Report emitted to frontend |

The frontend stores the phase in `simPhaseRef` and ignores any `report` event that arrives before `DONE`, preventing a premature end-of-simulation screen.

### Founder Personality System

The user selects one of six personality levels in the Setup screen. The selection is stored in `config.personality` and sent to the backend in the WebSocket `start` message.

The backend defines `PERSONALITY_GUIDE` — a dict mapping each level to a full behavioral description. This description is injected directly into every founder prompt (pitch, Q&A response, bargaining) so Gemini receives explicit behavioral instructions rather than just a label:

| Level | Behavioral description injected |
|-------|--------------------------------|
| `excellent` | Flawless, high-energy, exact metrics — CAC, LTV, MRR, margins, runway. Handles pressure confidently, pre-empts follow-ups. |
| `good` | Strong and strategic. Solid metrics, clear reasoning. Minor gaps only under very deep probing. |
| `average` | Covers basics without standout data. Handles easy questions, gets vague under expert pressure. |
| `weak` | Fumbles specifics, gives ranges instead of exact figures. Gets flustered by follow-ups. |
| `poor` | Defensive, avoids direct answers, contradicts earlier claims, sounds unprepared. |
| `very_poor` | Panics, forgets numbers already stated, uses wrong terminology, rambles without landing a point. |

The same description is used in the pitch, Q&A response, and AI-mode bargaining prompts — so personality is consistent across the entire simulation.

### Question Deduplication

Each investor tracks all questions it has previously asked in `investor_states[inv_id]["questionsHistory"]`. The full list is injected into every subsequent `GENERATE QUESTION` prompt with an explicit instruction to ask about a completely different angle. This prevents repetitive questioning in long simulations (8–10 rounds).

### Banter Guard

Banter (spontaneous investor comments) has a 25% trigger probability per exchange. Two constraints apply:

1. **Speaker guard** — prevents agents from hallucinating references to investors who haven't spoken yet
2. **No-question rule** — banter is always a comment, reaction, joke, or observation; never a question. The prompt includes: "Do NOT ask a question. No '?' marks. This is a side comment, never an inquiry."

```python
already_spoke = {
    m["sender"]
    for m in self.chat_history
    if m["sender"] in INVESTOR_IDS and m["sender"] != speaker
}
if not already_spoke:
    return  # No one to reference yet
```

The prompt explicitly lists only the investors in `already_spoke` and instructs the agent not to mention anyone else by name. This prevents the classic hallucination where an investor refers to what "Marcus said" when Marcus hasn't spoken yet.

### Exit Speech Generation

When an investor's confidence drops to ≤ 25, a contextual exit speech is generated by that investor's own ADK agent:

```python
prompt = f"""GENERATE EXIT SPEECH
You are {name}, and you have decided to drop out.
Your specific concerns: {concerns}   ← pulled from accumulated weaknesses[]
Recent conversation: {history_str}   ← last 8 exchanges

Write a brief, sharp exit speech (under 35 words) that:
1. References 1-2 specific things from the conversation above
2. States your exit clearly
3. Sounds like YOUR voice — {persona['focus']}"""
```

The speech is grounded in `chat_history`, so every departure is unique to what was actually said in that pitch session. A fallback hardcoded line is used if the ADK response is empty or unexpectedly long (>300 chars).

### Bargaining Logic

After all rounds complete, `_phase_bargaining()` determines qualifying investors (confidence > 25, not OUT), sets their `status = INVEST`, emits investor updates, then announces which investors are making offers.

**Offer term generation** — `_build_offers()` is async. For each qualifying investor, `_generate_single_offer_terms()` calls that investor's own ADK agent and asks it to propose deal terms. The agent decides equity %, royalty as a percentage on net sales, recoupment as a multiple of the investment (any multiple it chooses), interest rate, milestone conditions, board seat, or any other structure it considers appropriate for the risk. No multipliers or percentages are hardcoded anywhere in this path. Equity is safety-clamped to 1–49% in case of a model hallucination.

**Offer speech** — `_generate_offer_speech()` then gives the same investor its own terms and asks it to present them in its own voice. The card for that investor appears on the frontend only after the TTS for that speech finishes (via `onAfter` callback in the speech queue).

The bargaining phase runs as a negotiation loop, fully personality-driven, no hardcoded outcomes:

**AI mode**: `_ai_founder_decide_action()` feeds the FounderAgent all current offers, and the agent decides: accept the best offer, counter a specific shark, or walk away. The agent speaks its reasoning to the room first. The backend runs the entire loop autonomously (max 4 rounds).

**REAL mode**: Offer cards show Accept / Counter / Walk Away buttons per shark. Counter opens a modal for that specific shark.

**Counter-counter flow**: `_evaluate_counter_offer()` sends the founder's counter to the targeted shark's ADK agent. Three outcomes:
- `{accepted: true}` — deal closes immediately
- `{counter_offer: {cash, equity, terms}}` — shark revises; `bargaining_start` is re-emitted with `isRevision: true`, frontend replaces the card immediately
- `{accepted: false, counter_offer: null}` — hard reject; offer removed from table, `bargaining_start` re-emitted with `isRevision: true` showing remaining offers

`isRevision: false` on the initial `bargaining_start` tells the frontend to leave card reveal to the `offer_speech` `onAfter` callbacks. `isRevision: true` on subsequent emits tells the frontend to replace `activeOffers` immediately.

If all offers are rejected or withdrawn, negotiation breaks down and the report generates with no deal.

**Acceptance**: `_close_deal()` generates an acceptance speech, emits it as `founder_response`, then calls `_generate_report(deal=offer)`. The full accepted offer (equity, terms, investors) is saved in `report.agreedTermSheet` and displayed in the final memo.

### Report Generation

The final memo is compiled in two parallel steps:

1. **Per-investor feedback** — all 4 investor agents run simultaneously, each producing `{pros, cons, recommendation}` JSON
2. **Overall report** — Vincent's agent runs as "senior VC analyst", producing `{readinessScore, verdict, executiveSummary, risks[], strengths[], roadmap[]}`

Both steps use `asyncio.gather()`. The results are merged into a single `report` event payload.

The `readinessScore` is clamped to 1–10 with a guard for agents that return values like `75` (out-of-range) — it's divided by 10 and rounded if above 10.

**Per-shark verdict in `ReportScreen`** distinguishes actual investment from offers that weren't taken:

| Investor status | In `agreedTermSheet.investors`? | Label shown |
|-----------------|--------------------------------|-------------|
| `OUT` | — | Out |
| `INVEST` | Yes | Deal Closed |
| `INVEST` | No | Offer Made — Not Accepted |
| `ACTIVE` | — | Interested |

This matters because all qualifying investors get `status = INVEST` once the offer round begins, regardless of whether the founder ultimately chose their deal.

---

## Frontend Internals

### Component Tree

```
App (root state + WebSocket)
├── Header (language, API status, restart)
├── ApiKeyModal (key entry + verification)
├── SetupScreen (config form, model picker, investor preview)
├── SimulationScreen
│   ├── InvestorCard × 4 (confidence bar, agent state, thought bubble)
│   ├── Chat window (message list with per-speaker avatars)
│   ├── Input dock
│   │   ├── [REAL mode] textarea + Speak button (continuous mic) + Send button
│   │   └── [AI mode] "AI Autopilot Active" status display
│   ├── Bargaining panel (offer cards revealed one-by-one after each TTS, counter-offer modal)
│   └── ADK System Logs panel
└── ReportScreen (score, verdict, per-shark feedback, roadmap, download)
```

### State Ownership

All simulation state lives in `App.tsx` and is passed down as props. No external state library is used.

| State | Type | Description |
|-------|------|-------------|
| `step` | `SETUP \| SIMULATION \| REPORT` | Which screen is shown |
| `config` | `SimulationConfig` | User's configuration + selected model |
| `investors` | `Record<InvestorId, InvestorState>` | Per-investor confidence, status, agentState |
| `chat` | `Message[]` | Ordered conversation history |
| `agentLogs` | `AgentLog[]` | ADK orchestrator debug log (last 30 entries) |
| `activeOffers` | `Offer[]` | Cleared immediately when any bargaining action is taken |
| `isProcessing` | `boolean` | Locks the founder input between submission and next question |
| `isMuted` | `boolean` | When true, `speakText()` returns `Promise.resolve()` immediately |
| `vertexAIMode` | `boolean` | Set from `/config` on mount; hides API key modal when true |

### Speech Queue System

This is the most important frontend design decision. Naively calling `window.speechSynthesis.speak()` and `setChat()` as events arrive would cause all messages to appear at once (React batches state updates) and audio to cancel itself (each `speak()` call cancels the previous one).

**Investor confidence updates** are also routed through the queue. When evaluation results arrive, confidence meters only update after the associated dialogue has been spoken — so the user hears the question and answer before seeing the meter change. The exception is the "thinking" state (isThinking=true): thinking spinners appear immediately when evaluation starts, so the user can see investors are evaluating while the dialogue speech plays.

**Offer cards** appear one-by-one in sync with each shark's spoken offer. Each `offer_speech` event is queued with an `onAfter` callback — when that shark's TTS finishes, their offer card is added to `activeOffers`. This creates the live "card-reveal as speech ends" effect rather than all cards appearing at once.

**Bargaining panel unlock** — the initial `bargaining_start` (`isRevision: false`) does NOT immediately set `isProcessing = false`. It chains `setIsProcessing(false)` onto the tail of `speechQueueRef.current` so the Accept/Counter/Walk Away buttons only become active after all Q&A and offer speeches have finished playing. Revision `bargaining_start` events (`isRevision: true`) update `activeOffers` and unlock immediately since no speeches are pending at that point.

**Final report** is also queued behind all TTS — when the backend sends `report`, the frontend chains `setStep('REPORT')` onto the tail of `speechQueueRef.current`. The report screen only appears after the founder's acceptance speech and all offer speeches have fully played out.

The fix is a **serialised Promise chain**:

```typescript
const speechQueueRef = useRef<Promise<void>>(Promise.resolve());

const queueMessage = (msg, speakerId, onAfter?) => {
  speechQueueRef.current = speechQueueRef.current.then(async () => {
    setChat(prev => [...prev, msg]);       // text appears exactly when it's this message's turn
    await speakText(msg.text, speakerId);  // audio plays; Promise resolves when speech ends
    onAfter?.();                           // e.g. unlock input after question is read aloud
  });
};
```

Every incoming WebSocket event chains onto the tail of `speechQueueRef.current`. This guarantees:
- Text appears in chat exactly when it's that message's turn to be spoken
- Audio never overlaps or cancels a previous utterance
- `onAfter` callbacks fire strictly after the speech for that message ends

**System messages** (non-spoken) also pass through the queue so they appear in the correct position relative to spoken messages around them.

**Queue reset on restart**: `speechTokenRef.current++` increments a token that every in-flight `speakText()` promise checks. Stale promises see a mismatched token and resolve immediately without speaking, draining the queue instantly.

### Real Mode Input Flow

```
[question event arrives]
  → queueMessage(questionMsg, investorId, onAfter: () => setIsProcessing(false))
  → text appears in chat
  → speech plays
  → speech ends → setIsProcessing(false)   ← input unlocks HERE

[user clicks "Speak"]
  → startListening()
  → SpeechRecognition starts (continuous=true, interimResults=false)
  → each final transcript appended to inputText state
  → onend auto-restarts recognition while isListeningRef.current is true
  → clicking "Speak" again toggles mic OFF (without submitting)

[user clicks "Send"]
  → handleResponseSubmit()
  → isListeningRef.current = false (stops mic auto-restart)
  → recognitionRef.current?.stop()
  → setIsProcessing(true)   ← input locks again
  → ws.sendFounderResponse(text)
  
[backend sends founder_response event back]
  → queueMessage(founderMsg, 'founder')    ← text + speech queued
  
[backend sends investor evaluation events]
  → setInvestors() called immediately (no speech)
  
[backend sends next question event]
  → queueMessage(..., onAfter: () => setIsProcessing(false))
  → cycle repeats
```

When **muted**: `speakText()` returns `Promise.resolve()` immediately, so `onAfter` fires right after the text appears — the input unlocks without waiting for any audio.

### Model Fallback Sync

```
Backend __init__:
  self.model = config.get("model")     ← e.g. "gemini-3.5-flash"
  if vertex_ai and self.model == "gemini-3.5-flash":
      self.model = "gemini-2.5-flash"  ← fallback applied
      self._model_fallback = True

Backend run():
  await self._emit("model_update", {"model": self.model})   ← sent immediately

Frontend handleSimEvent:
  case 'model_update':
    setConfig(prev => ({ ...prev, model: event.model }))    ← config.model updated

Result:
  SimulationScreen badge:  config.model.split('-').map(...).join(' ')  → "Gemini 2.5 Flash"
  App footer:              same expression                              → "Gemini 2.5 Flash"
```

Both the badge and footer derive their label from `config.model` dynamically, so they update automatically when `model_update` arrives.

---

## WebSocket Event Flow

### Full Sequence Diagram

```
Frontend                    Backend (server.py)         Orchestrator          ADK Agents
   │                               │                         │                    │
   │──── WS connect ──────────────►│                         │                    │
   │──── {action:"start", config}─►│                         │                    │
   │                               │── create orchestrator ─►│                    │
   │                               │                         │── _init_sessions() │
   │                               │                         │── create_session() ►│ (×5)
   │                               │                         │◄─ session objects ──│
   │◄── {type:"model_update"} ─────│◄────────────────────────│                    │
   │                               │                         │                    │
   │  ─ ─ ─ ─ ─ PITCH PHASE ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │                    │
   │◄── {type:"agent_log"} ────────│◄────────────────────────│                    │
   │                               │                         │── AI mode: run_founder_agent()
   │                               │                         │                   ►│FounderAgent
   │                               │                         │◄──── pitch text ───│
   │◄── {type:"pitch"} ────────────│◄────────────────────────│                    │
   │                               │                         │                    │
   │  ─ ─ ─ ─ ─ ROUND 1 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │                    │
   │                               │     [random order]      │                    │
   │◄── {type:"question",          │◄────────────────────────│◄── VincentAgent ───│
   │     waitForResponse:true} ────│                         │                    │
   │                               │                         │                    │
   │  [REAL: user types answer]    │                         │                    │
   │──── {action:"founder_response"}►│                       │                    │
   │                               │── orchestrator.receive_founder_response() ──►│
   │◄── {type:"founder_response"} ─│◄────────────────────────│                    │
   │                               │                         │                    │
   │  [parallel evaluation]        │                         │                    │
   │◄── {type:"agent_log"} ────────│◄────────────────────────│  asyncio.gather()  │
   │                               │                         │──►VincentAgent ────►│
   │                               │                         │──►MarcusAgent ─────►│
   │                               │                         │──►BeatriceAgent ───►│
   │                               │                         │──►LeonaAgent ──────►│
   │                               │                         │◄── 4 JSON results ─│
   │◄── {type:"investor_update"} ──│◄──────── ×4 ────────────│                    │
   │                               │                         │                    │
   │  [if investor drops out]      │                         │                    │
   │◄── {type:"exit_speech"} ──────│◄────────────────────────│◄── InvestorAgent ──│
   │◄── {type:"system_message"} ───│◄────────────────────────│                    │
   │                               │                         │                    │
   │  [25% banter chance]          │                         │                    │
   │◄── {type:"banter"} ───────────│◄────────────────────────│◄── InvestorAgent ──│
   │                               │                         │                    │
   │  ─ ─ ─ [rounds repeat] ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │                    │
   │                               │                         │                    │
   │  ─ ─ ─ ─ BARGAINING ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │                    │
   │◄── {type:"offer_speech"} ─────│◄────────────────────────│                    │
   │◄── {type:"bargaining_start",  │◄────────────────────────│                    │
   │     isRevision:false} ─────────│                         │                    │
   │                               │                         │                    │
   │──── {action:"accept_offer"} ──►│                        │                    │
   │                               │── receive_bargain_action() ────────────────►│
   │◄── {type:"system_message"} ───│◄────────────────────────│                    │
   │                               │                         │                    │
   │  ─ ─ ─ ─ REPORT ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │                    │
   │                               │                         │  asyncio.gather()  │
   │                               │                         │──► ×4 investor feedback
   │                               │                         │──► Vincent as analyst
   │◄── {type:"report"} ───────────│◄────────────────────────│                    │
   │── WS close ────────────────── │                         │                    │
```

---

## Auth & Configuration

### API Key Mode (Local/Standalone)

The user enters a Gemini API key in the browser. The frontend verifies it by making a test `generateContent` call via `@google/genai` (browser SDK). If valid, the key is stored in `localStorage` and sent in the WebSocket `start` message:

```json
{"action": "start", "config": {...}, "apiKey": "AIza..."}
```

The backend sets `os.environ["GOOGLE_API_KEY"] = api_key` in the orchestrator `__init__`, which the ADK picks up automatically.

### Vertex AI Mode (Cloud Run)

When `GOOGLE_GENAI_USE_VERTEXAI=true` is set in the Cloud Run environment:

- The backend sets `os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"` in the orchestrator
- ADK uses Application Default Credentials from the Cloud Run service account
- No API key is needed or accepted from the frontend
- The `/config` endpoint returns `{"requiresApiKey": false, "vertexAI": true}`
- The frontend skips the API key modal entirely

Required Cloud Run environment variables:
```
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=asia-northeast1
```

Required IAM role on the service account: **Agent Platform Express User**

### /config Endpoint

On mount, the frontend fetches `/config`:
```typescript
fetch(`${BACKEND_HTTP_URL}/config`)
  .then(r => r.json())
  .then(cfg => {
    setVertexAIMode(cfg.vertexAI);
    if (!cfg.requiresApiKey) {
      setApiConnected(true);   // skip modal
    } else {
      // show modal unless key already in localStorage
    }
  });
```

This single endpoint drives the entire auth UX — no hardcoded environment detection in the frontend.

---

## Deployment Architecture

### Unified Docker Image

A single multi-stage Dockerfile eliminates the need for separate frontend and backend services:

```dockerfile
# Stage 1 — build React SPA
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build                    # outputs to /app/frontend/dist

# Stage 2 — Python backend + bundled frontend
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=frontend-builder /app/frontend/dist ./static   # ← frontend lives here

ENV PORT=8080
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
```

**Request routing in server.py:**
```
/health          → FastAPI route (JSON)
/config          → FastAPI route (JSON)
/ws-simulate     → FastAPI WebSocket route
/assets/*        → StaticFiles(directory="static/assets")
/               → FileResponse("static/index.html")
/{any}           → FileResponse(static/any) or fallback to index.html (SPA routing)
```

API routes are defined before the static file mounts, so they always take priority.

### Cloud Build Pipeline

`cloudbuild.yaml` at the repo root:

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/vc-shark-tank-backend:$COMMIT_SHA',
           '-f', 'Dockerfile', '.']          ← build context = repo root (needs frontend/ + backend/)

  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/vc-shark-tank-backend:$COMMIT_SHA']

  - name: 'gcr.io/cloud-builders/gcloud'
    args: ['run', 'deploy', 'vc-sharktank-simulator-gemini',
           '--image', 'gcr.io/$PROJECT_ID/vc-shark-tank-backend:$COMMIT_SHA',
           '--region', 'asia-northeast1',
           '--set-env-vars', 'GOOGLE_GENAI_USE_VERTEXAI=true,...']
```

Every push to the connected GitHub repository triggers a new build and rolling deployment.

### Cloud Run Service Layout

```
Cloud Run Service: vc-sharktank-simulator-gemini
  Region:         asia-northeast1
  Memory:         1 GiB
  CPU:            1
  Concurrency:    10 (WebSocket sessions per instance)
  Min instances:  1 (prevents cold starts)
  Max instances:  5
  Timeout:        300s (covers full multi-round simulation)
  Auth:           Allow unauthenticated
  
  Environment:
    GOOGLE_GENAI_USE_VERTEXAI=true
    GOOGLE_CLOUD_PROJECT=...
    GOOGLE_CLOUD_LOCATION=asia-northeast1
    PORT=8080 (injected by Cloud Run automatically)
```

**Important**: Each WebSocket connection spawns a `SimulationOrchestrator` instance with 5 ADK agent runners. With concurrency=10, up to 10 simultaneous simulations can run on a single instance, each with its own isolated set of agents and sessions.

---

## Key Design Decisions

### 1. WebSocket over HTTP polling
The simulation is inherently a long-running streaming process (3–10+ minutes depending on rounds and speech). WebSocket is the natural fit — it avoids timeout limitations of HTTP, supports bidirectional messages (founder responses, bargain actions), and allows the backend to push events as they happen without the frontend polling.

### 2. Speech queue as a Promise chain
`speechQueueRef.current` is a Promise that always points to the tail of the current speech queue. Chaining `.then()` onto it guarantees sequential execution without blocking the main thread. The design handles mute (immediate resolution), restart (token increment to drain the queue), and `onAfter` callbacks for REAL mode input synchronisation.

### 3. One orchestrator instance per WebSocket connection
State is not shared between users. Each connection gets its own orchestrator, its own 5 ADK agents, and its own session service. This is stateless horizontally — multiple Cloud Run instances can serve different connections without any shared storage.

### 4. Confidence computed by the agents, not the backend
The orchestrator does not apply a scoring formula. Each investor agent returns a new `confidence` integer in its evaluation JSON. The agent's LLM reasoning determines how the founder's answer affected that investor's conviction, making the simulation genuinely emergent rather than rule-based.

### 5. `model_update` event for fallback transparency
Rather than silently running on a different model than selected, the backend always emits `model_update` at the start of `run()` with the actual model in use. This ensures the frontend badge and footer are always accurate, especially when Gemini 3.5 Flash falls back to 2.5 Flash on Vertex AI.

### 6. `config` state updated from the server
`config.model` in the frontend is a React state value derived initially from user selection but overridable by `model_update` events from the server. This single source of truth avoids the frontend and backend being out of sync about which model is running.
