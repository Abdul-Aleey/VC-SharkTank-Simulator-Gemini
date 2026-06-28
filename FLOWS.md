# Flow Diagrams — VC Shark Tank Multi-Agent Simulator

All diagrams are written in [Mermaid](https://mermaid.js.org/) and render natively on GitHub.

---

## Multi-Agent System Architecture

How the 5 ADK agents are wired together. Each agent has its own isolated ADK `Runner` and `InMemorySession` — they share no state. The orchestrator is the only component that knows about all five.

```mermaid
graph TB
    WS["server.py\nWebSocket handler\n/ws-simulate"]

    subgraph ORC["SimulationOrchestrator — the brain"]
        direction TB
        EQ["asyncio.Queue\nevent_queue\n→ streams events to WebSocket"]
        BQ["_bargain_action Queue\nREAL mode: waits for user\nbargain choice"]
        FRQ["_founder_response Queue\nREAL mode: waits for user\ntyped answer"]
    end

    subgraph FA["FounderAgent  (AI mode only)"]
        FAG["ADK Agent\nInstruction: pitch writer,\nresponder, negotiator"]
        FAS["InMemorySession\nfounder_user\nisolated history"]
        FAR["Runner\napp=shark_tank"]
        FAG --- FAS
        FAG --- FAR
    end

    subgraph VA["VincentAgent"]
        VAG["ADK Agent\nFocus: Finance · Valuation\nMargins · Profitability"]
        VAS["InMemorySession\nvincent_user"]
        VAR["Runner"]
        VAG --- VAS
        VAG --- VAR
    end

    subgraph MA["MarcusAgent"]
        MAG["ADK Agent\nFocus: Tech · Architecture\nDefensibility · Scale"]
        MAS["InMemorySession\nmarcus_user"]
        MAR["Runner"]
        MAG --- MAS
        MAG --- MAR
    end

    subgraph BA["BeatriceAgent"]
        BAG["ADK Agent\nFocus: Brand · Leadership\nMarketing · Trust"]
        BAS["InMemorySession\nbeatrice_user"]
        BAR["Runner"]
        BAG --- BAS
        BAG --- BAR
    end

    subgraph LA["LeonaAgent"]
        LAG["ADK Agent\nFocus: GTM · Operations\nGrowth · Mass Appeal"]
        LAS["InMemorySession\nleona_user"]
        LAR["Runner"]
        LAG --- LAS
        LAG --- LAR
    end

    WS <-->|"send actions\nreceive events"| ORC

    ORC -->|"_run_founder_agent()\nsequential"| FA
    FA -->|"pitch / response /\nacceptance speech"| ORC

    ORC -->|"asyncio.gather()\n4 agents in parallel"| VA
    ORC -->|"asyncio.gather()\n4 agents in parallel"| MA
    ORC -->|"asyncio.gather()\n4 agents in parallel"| BA
    ORC -->|"asyncio.gather()\n4 agents in parallel"| LA

    VA -->|"JSON: confidence\nthoughtBubble strengths\nweaknesses risks"| ORC
    MA -->|"JSON: confidence\nthoughtBubble strengths\nweaknesses risks"| ORC
    BA -->|"JSON: confidence\nthoughtBubble strengths\nweaknesses risks"| ORC
    LA -->|"JSON: confidence\nthoughtBubble strengths\nweaknesses risks"| ORC

    ORC -->|"typed events\npitch · question ·\nfounder_response · banter ·\nexit_speech · investor_update ·\nbargaining_start · report"| EQ
    EQ -->|"JSON frames\nover WebSocket"| WS

    style FA fill:#1e3a5f,stroke:#3b82f6,color:#e2e8f0
    style VA fill:#1a3a2a,stroke:#22c55e,color:#e2e8f0
    style MA fill:#3a1a1a,stroke:#ef4444,color:#e2e8f0
    style BA fill:#2d1a3a,stroke:#a855f7,color:#e2e8f0
    style LA fill:#3a2a1a,stroke:#f59e0b,color:#e2e8f0
    style ORC fill:#1e2a3a,stroke:#64748b,color:#e2e8f0
```

**Key design decisions this diagram illustrates:**
- Each agent has a completely isolated `InMemorySession` — Vincent has no idea what Marcus remembers
- `asyncio.gather()` runs all 4 investor evaluations simultaneously (true parallelism, not sequential)
- The orchestrator never lets agents talk to each other directly — all coordination goes through Python code
- FounderAgent is only invoked in AI mode; REAL mode uses `_founder_response` queue instead
- One event queue serialises all output regardless of which agent produced it

---

## Table of Contents

1. [Application Screen Flow](#1-application-screen-flow)
2. [Authentication Flow](#2-authentication-flow)
3. [Simulation Initialisation Flow](#3-simulation-initialisation-flow)
4. [Model Selection & Fallback Flow](#4-model-selection--fallback-flow)
5. [Pitch Phase Flow](#5-pitch-phase-flow)
6. [Q&A Round Flow (Full Round)](#6-qa-round-flow-full-round)
7. [Parallel Investor Evaluation Flow](#7-parallel-investor-evaluation-flow)
8. [Confidence & Status Update Flow](#8-confidence--status-update-flow)
9. [Exit Speech Generation Flow](#9-exit-speech-generation-flow)
10. [Banter Generation Flow](#10-banter-generation-flow)
11. [Bargaining Phase Flow](#11-bargaining-phase-flow)
12. [Report Generation Flow](#12-report-generation-flow)
13. [Frontend Speech Queue Flow](#13-frontend-speech-queue-flow)
14. [Real Mode Input Unlock/Lock Cycle](#14-real-mode-input-unlocklok-cycle)
15. [WebSocket Connection & Event Protocol](#15-websocket-connection--event-protocol)
16. [Cloud Build & Cloud Run Deployment Flow](#16-cloud-build--cloud-run-deployment-flow)
17. [Full End-to-End Flow](#17-full-end-to-end-flow)

---

## 1. Application Screen Flow

High-level navigation between the three screens.

```mermaid
flowchart TD
    A([Browser Opens]) --> B[App mounts\nfetch /config]
    B --> C{Vertex AI\nmode?}
    C -->|Yes| D[setApiConnected true\nskip API key modal]
    C -->|No| E{Key in\nlocalStorage?}
    E -->|Yes| F[Verify key\non mount]
    E -->|No| G[Show ApiKeyModal]
    F -->|Valid| D
    F -->|Invalid| G
    G -->|Key saved| D
    D --> H[SetupScreen\nConfigure startup & mode]
    H -->|Launch Simulation| I[SimulationScreen\nLive pitch]
    I -->|report event received| J[ReportScreen\nVC Evaluation Memo]
    J -->|Restart| H
    I -->|Restart button| H
```

---

## 2. Authentication Flow

How the app decides whether to show the API key modal and how it routes auth to the backend.

```mermaid
flowchart TD
    A([App Mount]) --> B[GET /config]
    B --> C{vertexAI: true?}

    C -->|Yes — Vertex AI mode| D[Hide API key modal\nsetApiConnected = true\nsetVertexAIMode = true]
    C -->|No — API key mode| E{Key in\nlocalStorage?}

    E -->|Yes| F[verifyApiKey\ntest generateContent call\nvia browser SDK]
    E -->|No| G[Show ApiKeyModal]

    F -->|200 OK| H[setApiConnected = true\nProceed to SetupScreen]
    F -->|Error| G

    G -->|User submits key| I[verifyApiKey\ntest call]
    I -->|Valid| J[localStorage.setItem\nsetApiConnected = true\nClose modal]
    I -->|Invalid / quota| K[Show error message\nStay in modal]
    K --> G

    D --> L[WS start message\napiKey: empty string]
    H --> L
    J --> L
    L --> M{Backend auth check}
    M -->|GOOGLE_GENAI_USE_VERTEXAI=true| N[Use ADC service account\nNo API key needed]
    M -->|api_key provided| O[os.environ GOOGLE_API_KEY = api_key]
    M -->|Neither| P[Raise ValueError\nSend error event]
```

---

## 3. Simulation Initialisation Flow

From WebSocket connect to first pitch event.

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant WS as server.py
    participant ORC as Orchestrator
    participant ADK as ADK / Gemini

    FE->>WS: WebSocket connect
    FE->>WS: {action:"start", config:{...}, apiKey:"..."}
    WS->>ORC: SimulationOrchestrator(config, api_key)

    note over ORC: __init__
    ORC->>ORC: self.model = config["model"]
    ORC->>ORC: Auth block (Vertex AI or API key)
    ORC->>ORC: self._model_fallback check
    ORC->>ORC: build_investor_agents(model)
    ORC->>ORC: build_founder_agent(model)
    ORC->>ORC: build_runners(agents, session_svc)

    WS->>WS: asyncio.gather(run_sim, send_events, recv_msgs)

    ORC->>ADK: create_session() × 5
    ADK-->>ORC: session objects (vincent, marcus, beatrice, leona, founder)

    ORC->>FE: {type:"model_update", model:"gemini-2.5-flash"}
    ORC->>FE: {type:"agent_log", message:"Initializing..."}
```

---

## 4. Model Selection & Fallback Flow

How the model choice travels from the UI selector to the actual ADK agent, including Vertex AI fallback.

```mermaid
flowchart TD
    A[User selects model\nin SetupScreen] --> B[config.model set\ne.g. gemini-3.5-flash]
    B --> C[WS start message\nconfig.model included]

    C --> D[Orchestrator __init__]
    D --> E[self.model = config.get model]
    E --> F{GOOGLE_GENAI_\nUSE_VERTEXAI?}

    F -->|Yes| G{self.model ==\ngemini-3.5-flash?}
    G -->|Yes| H[self.model = gemini-2.5-flash\nself._model_fallback = True]
    G -->|No| I[self._model_fallback = False]
    F -->|No| I

    H --> J[build_investor_agents\nmodel=gemini-2.5-flash]
    I --> J
    J --> K[All 5 ADK agents use\nthe resolved model]

    K --> L[run: emit model_update\nmodel=self.model]
    L --> M{_model_fallback?}
    M -->|Yes| N[emit agent_log warning\nfallback occurred]
    M -->|No| O[Continue normally]

    L --> P[Frontend receives model_update]
    P --> Q[setConfig prev =\n...prev model: event.model]
    Q --> R[SimulationScreen badge\nand footer update\nto show actual model]
```

---

## 5. Pitch Phase Flow

The opening pitch — different paths for AI Autopilot and Real Entrepreneur modes.

```mermaid
flowchart TD
    A[_phase_pitch called] --> B[emit agent_log:\nGenerating opening pitch]
    B --> C[_set_founder_agent_state PITCHING]
    C --> D{mode?}

    D -->|AI| E[_run_founder_agent\nGENERATE PITCH prompt\nwith startup details\npersonality type\nlanguage]
    E --> F[ADK FounderAgent\nrun_async]
    F --> G[Gemini generates\ncompelling pitch text]
    G --> H[pitch text returned]

    D -->|REAL| I[Build static pitch\nfrom config fields:\nfounderName startupName\ndescription askAmount\naskEquity]
    I --> H

    H --> J[_add_to_history\nfounder pitch]
    J --> K[_set_founder_agent_state IDLE]
    K --> L[emit pitch event\nsender: founder\ntext: pitch]
    L --> M[Frontend: queueMessage\ntext appears + speech plays]
```

---

## 6. Q&A Round Flow (Full Round)

One complete round: question order is randomised, each investor asks in sequence, all evaluate in parallel.

```mermaid
flowchart TD
    A[Start Round N] --> B[emit agent_log:\nStarting Round N of M]
    B --> C[active = investors\nwith status ACTIVE]
    C --> D{active\nempty?}
    D -->|Yes| E[Skip to Bargaining]
    D -->|No| F[random.shuffle active]

    F --> G[For each inv_id\nin shuffled order]

    G --> H{investor still\nACTIVE?}
    H -->|No — dropped out\nduring this round| I[Skip this investor]
    H -->|Yes| J[_generate_question\ninv_id]

    J --> K[Set agentState = ASKING\nemit investor_update]
    K --> L[Build question prompt\nwith chat history last 10]
    L --> M[ADK InvestorAgent\nrun_async]
    M --> N[Gemini returns\nsharp question\n≤40 words]
    N --> O[Set agentState = IDLE\nemit investor_update]
    O --> P[_add_to_history\ninv_id question]
    P --> Q[emit question event\nwaitForResponse: mode==real]

    Q --> R{mode?}
    R -->|REAL| S[Frontend unlocks input\nafter speech ends\nonAfter callback]
    S --> T[User types or\ndictates response\nclicks Submit]
    T --> U[WS: founder_response action]
    U --> V[receive_founder_response\nqueue.put text]
    V --> W[response = queue.get]

    R -->|AI| X[_generate_founder_response\nFounderAgent run_async]
    X --> W

    W --> Y[_add_to_history\nfounder response]
    Y --> Z[emit founder_response event]
    Z --> AA[_parallel_evaluate response]
    AA --> AB[_maybe_banter]
    AB --> AC[questionsAsked += 1]
    AC --> G

    I --> G
    G -->|All investors done| AD[Round complete\nnext round or bargaining]
```

---

## 7. Parallel Investor Evaluation Flow

The core multi-agent feature: all active investors evaluate simultaneously.

```mermaid
flowchart TD
    A[_parallel_evaluate\nfounder_response] --> B[active = ACTIVE investors]
    B --> C[Set all active:\nagentState=EVALUATING\nisThinking=true]
    C --> D[emit investor_update × N\nall show thinking spinner]

    D --> E[Build evaluation tasks]
    E --> F[asyncio.gather\n_evaluate_single_investor × N]

    F --> G1[VincentAgent\nrun_async\nfinance lens]
    F --> G2[MarcusAgent\nrun_async\ntech lens]
    F --> G3[BeatriceAgent\nrun_async\nbranding lens]
    F --> G4[LeonaAgent\nrun_async\nGTM lens]

    G1 --> H1[Returns JSON\nconfidence trend\nthoughtBubble\nstrengths weaknesses risks]
    G2 --> H2[Returns JSON]
    G3 --> H3[Returns JSON]
    G4 --> H4[Returns JSON]

    H1 & H2 & H3 & H4 --> I[All results collected]

    I --> J[For each result]
    J --> K[Update confidence\ntrend thoughtBubble\naccumulate strengths\nweaknesses risks\nisThinking=false]

    K --> L{confidence\n≤ 25?}
    L -->|Yes| M[status = OUT\nagentState = OUT\nadd to exit_speeches list]
    L -->|No| N{confidence\n≥ 85?}
    N -->|Yes| O[status = INVEST\nagentState = INVESTED]
    N -->|No| P[status = ACTIVE\nagentState = IDLE]

    M & O & P --> Q[emit investor_update\nfor all investors]

    Q --> R{exit_speeches\nnot empty?}
    R -->|Yes| S[asyncio.gather\n_generate_exit_speech × departing]
    R -->|No| T[Done]
    S --> T
```

---

## 8. Confidence & Status Update Flow

How a single investor's state transitions across the simulation. INVEST status is only set **after all rounds complete** — investors stay ACTIVE during Q&A no matter how high confidence goes.

```mermaid
stateDiagram-v2
    [*] --> ACTIVE : Simulation starts\nconfidence = 50

    ACTIVE --> ASKING : _generate_question called
    ASKING --> ACTIVE : Question emitted\nagentState → IDLE

    ACTIVE --> EVALUATING : _parallel_evaluate called\nisThinking = true (immediate)

    EVALUATING --> ACTIVE : new_conf > 25\nagentState → IDLE\n(even if conf ≥ 85, stays ACTIVE\nuntil all rounds done)
    EVALUATING --> OUT : new_conf ≤ 25\nagentState → OUT\nstatus → OUT\nexit speech generated

    ACTIVE --> BANTERING : _maybe_banter triggered\n25% chance
    BANTERING --> ACTIVE : Banter emitted\nagentState → IDLE

    note right of ACTIVE
        confidence keeps adjusting
        every round but no offer
        is made mid-simulation
    end note

    ACTIVE --> INVESTED : _phase_bargaining starts\nconf > 25 AND not OUT\nstatus → INVEST (set here)
    INVESTED --> INVESTED : Presents offer\nWaits for founder decision

    OUT --> [*] : No further participation
```

---

## 9. Exit Speech Generation Flow

Dynamic exit speeches grounded in actual conversation history.

```mermaid
flowchart TD
    A[Investor confidence ≤ 25\nstatus = OUT] --> B[Add inv_id to\nexit_speeches list]

    B --> C[After all evaluations\ncomplete for this exchange]
    C --> D{Multiple investors\nexiting?}

    D -->|Yes| E[asyncio.gather\n_generate_exit_speech × N\nall in parallel]
    D -->|No| F[_generate_exit_speech\nsingle call]

    E & F --> G[For each departing investor]

    G --> H[state = investor_states inv_id\nname = INVESTOR_PERSONAS name\nhistory_str = last 8 messages]
    H --> I[concerns = weaknesses list\nlast 3 items]
    I --> J[Build EXIT SPEECH prompt\nwith name confidence\nconcerns history\npersona focus area]

    J --> K[ADK InvestorAgent\nrun_async — that investor's\nown session]
    K --> L[Gemini generates\ncontextual speech\n≤35 words]

    L --> M{Response\nvalid?\n1–300 chars}
    M -->|Yes| N[Use generated speech]
    M -->|No — empty or too long| O[Use hardcoded fallback\nper investor per language]

    N & O --> P[_add_to_history\ninv_id exit speech]
    P --> Q[emit exit_speech event\nsender senderName text]
    Q --> R[emit system_message\nNAME is OUT]
    R --> S[Frontend: queue exit speech\nfor serialised audio+text]
```

---

## 10. Banter Generation Flow

Spontaneous investor comments with the hallucination guard.

```mermaid
flowchart TD
    A[_maybe_banter called\nafter each exchange] --> B{At least 2\nACTIVE investors?}
    B -->|No| Z[Return — no banter]
    B -->|Yes| C{random.random\n≤ 0.25?}
    C -->|No — 75% chance| Z
    C -->|Yes| D[speaker = random.choice\nactive investors]

    D --> E[already_spoke = set of\ninvestors in chat_history\nwho are NOT the speaker]
    E --> F{already_spoke\nempty?}
    F -->|Yes — no one else\nhas spoken yet| Z
    F -->|No| G[referenceable = names\nof already_spoke investors]

    G --> H[Build BANTER prompt\nwith speaker name\nreferenceable list\nlast 6 history messages\nCRITICAL: only mention\nreferenceable investors]
    H --> I[ADK InvestorAgent\nrun_async for speaker]
    I --> J[Gemini generates\npunchy comment ≤25 words]

    J --> K{Response\nnot empty?}
    K -->|No| Z
    K -->|Yes| L[Strip quotes\nSet agentState = BANTERING\nemit investor_update]
    L --> M[_add_to_history\nspeaker banter]
    M --> N[emit banter event]
    N --> O[Set agentState = IDLE\nemit investor_update]
```

---

## 11. Bargaining Phase Flow

Multi-round negotiation loop — AI mode runs autonomously; REAL mode waits for user each iteration.

```mermaid
flowchart TD
    A[_phase_bargaining\nafter all rounds] --> B[qualifying = conf > 25\nAND not OUT]
    B --> C{any qualifying?}
    C -->|No| D[emit no-deal message\n_generate_report None]

    C -->|Yes| E[Set status=INVEST\nfor all qualifying\nemit investor_updates]
    E --> F[_build_offers qualifying\nactive_offers dict keyed\nby lead investor id]
    F --> G[Each shark speaks\ntheir offer one by one\nemit offer_speech per shark]
    G --> H[emit bargaining_start\nall current offers\nqueued after speeches]

    H --> I{mode?}
    I -->|AI| J[_ai_founder_decide_action\nFounderAgent evaluates ALL offers\nreturns action + speech]
    J --> JA[Founder speaks\nnegotiation strategy\nemit founder_response]
    I -->|REAL| K[Wait for user\nbargain_action.get blocks\noffer panel shows buttons]

    JA & K --> L{action.type?}

    L -->|accept| M[_close_deal offer\n_generate_acceptance_speech\nFounderAgent names shark]
    M --> MA[emit founder_response\nfounder speaks acceptance]
    MA --> MB[emit system_message\nDeal sealed!]
    MB --> MC[_generate_report deal]

    L -->|counter| N[target = action.investorId\nREAL: founder states counter\nAI: already spoke above]
    N --> O[_evaluate_counter_offer\nTARGET shark ADK agent\nevaluates in character]
    O --> P[Shark speaks result\nemit banter own voice]
    P --> Q{result?}
    Q -->|accepted=true| M
    Q -->|counter_offer not null| R[Shark counter-countered\nUpdate active_offers\nemit bargaining_start\nwith revised terms]
    R --> I
    Q -->|hard reject| S[Remove shark's offer\nfrom active_offers]
    S --> T{any offers\nremaining?}
    T -->|Yes| U[emit bargaining_start\nremaining offers only]
    U --> I
    T -->|No| V[emit negotiation\nbroke down\n_generate_report None]

    L -->|walk_away| W[emit walked away\nVincent delivers snark]
    W --> V

    I -->|AI max 4 rounds hit| X[Accept lowest-equity\nremaining offer\n_close_deal best]
    X --> MC
```

---

## 12. Report Generation Flow

Parallel feedback collection and final memo compilation.

```mermaid
flowchart TD
    A[_generate_report deal] --> B[emit agent_log:\nGenerating final report]
    B --> C[history_str = last 15 messages]
    C --> D[investor_summary = all 4\nstatus + confidence strings]

    D --> E[asyncio.gather\n_generate_investor_feedback × 4\nall in parallel]

    E --> F1[VincentAgent\nfeedback prompt\npros cons recommendation]
    E --> F2[MarcusAgent\nfeedback prompt]
    E --> F3[BeatriceAgent\nfeedback prompt]
    E --> F4[LeonaAgent\nfeedback prompt]

    F1 & F2 & F3 & F4 --> G[feedbacks_list collected\ndict: investorId → feedback]

    G --> H[Vincent runs again\nas senior VC analyst\nGENERATE REPORT FEEDBACK\nreturns overall JSON]

    H --> I[Parse report JSON\nreadinessScore verdict\nexecutiveSummary risks\nstrengths roadmap]

    I --> J{readinessScore\n> 10?}
    J -->|Yes — agent returned\nout-of-range e.g. 75| K[score = round score/10\nclamp 1–10]
    J -->|No| L[clamp 1–10]

    K & L --> M[report.detailedSharkFeedback\n= feedbacks_list]

    M --> N{deal provided?}
    N -->|Yes| O[report.agreedTermSheet = deal]
    N -->|No| P{Any investors\nwith status INVEST?}
    P -->|Yes| Q[Auto term sheet:\nthose investors\nask amount\naskEquity + 5%]
    P -->|No| R[agreedTermSheet = null]

    O & Q & R --> S[emit report event\ndata: full report object]
    S --> T[Frontend: setReport\nsetStep REPORT\nwsRef disconnect]
```

---

## 13. Frontend Speech Queue Flow

How text and audio stay in sync using a serialised Promise chain.

```mermaid
flowchart TD
    A[WebSocket event arrives] --> B{Event type?}

    B -->|pitch founder_response\nbanter exit_speech offer_speech| C[queueMessage\nmsg speakerId]
    B -->|question| D{waitForResponse\ntrue?}
    D -->|Yes — REAL mode| E[queueMessage\nmsg speakerId\nonAfter: setIsProcessing false]
    D -->|No — AI mode| C
    B -->|system_message| F[queueSystemMessage\ntext]
    B -->|investor_update\nfounder_agent_state\nagent_log etc| G[setInvestors / setState\nImmediate — no queue]

    C & E --> H[Chain onto\nspeechQueueRef.current]
    F --> H

    H --> I[speechQueueRef.current\n= prev.then async =>\n  setChat add msg\n  await speakText\n  onAfter?]

    I --> J{isMuted?}
    J -->|Yes| K[speakText returns\nPromise.resolve\nimmediately]
    J -->|No| L[SpeechSynthesisUtterance\nset voice pitch rate\nby speakerId]

    L --> M[window.speechSynthesis.speak]
    M --> N[utterance.onend fires\nor safety timeout]
    N --> O[cleanUp resolve Promise]
    K --> O

    O --> P[onAfter fires\ne.g. setIsProcessing false]
    P --> Q[Next queued message\nstarts automatically]

    subgraph Restart
        R[handleRestart] --> S[speechTokenRef.current++]
        S --> T[speechQueueRef.current\n= Promise.resolve]
        T --> U[All in-flight speakText\nchecks token mismatch\nresolves immediately\nqueue drains instantly]
    end
```

---

## 14. Real Mode Input Unlock/Lock Cycle

The precise sequence that gates founder input in Real Entrepreneur mode.

```mermaid
sequenceDiagram
    participant FE as Frontend UI
    participant Q as Speech Queue
    participant WS as WebSocket
    participant BE as Backend

    Note over FE: isProcessing = true (set on sim start)
    Note over FE: Input textarea disabled

    BE->>FE: {type:"question", waitForResponse:true}
    FE->>Q: queueMessage(questionMsg, investorId, onAfter: ()=>setIsProcessing(false))

    Note over Q: Waits for previous speech to finish
    Q->>FE: setChat — question text appears in chat
    Q->>Q: speakText(question) — audio plays
    Q->>Q: Speech ends (onend / safety timeout)
    Q->>FE: onAfter() → setIsProcessing(false)

    Note over FE: Input textarea ENABLED
    Note over FE: User types or dictates answer

    FE->>FE: handleResponseSubmit()
    FE->>FE: setInputText('')
    FE->>FE: setIsProcessing(true)
    FE->>FE: stop mic if isListening

    Note over FE: Input textarea disabled again

    FE->>WS: {action:"founder_response", text:"..."}
    WS->>BE: receive_founder_response(text)
    BE->>FE: {type:"founder_response"}
    BE->>FE: {type:"investor_update" × N}  (immediate, not queued)
    BE->>FE: {type:"question", waitForResponse:true}  ← next round

    Note over FE: Cycle repeats
```

---

## 15. WebSocket Connection & Event Protocol

Complete protocol from connect to disconnect.

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant SV as server.py
    participant ORC as Orchestrator

    FE->>SV: WebSocket upgrade request /ws-simulate
    SV->>FE: 101 Switching Protocols

    FE->>SV: JSON {action:"start", config:{...}, apiKey:"..."}
    Note over SV: 30s timeout waiting for start

    SV->>ORC: new SimulationOrchestrator(config, api_key)
    SV->>SV: asyncio.gather(run_sim, send_events, recv_msgs)

    loop Simulation running
        ORC-->>SV: _q.put(event)
        SV-->>FE: JSON event frame
    end

    Note over FE,SV: REAL mode only
    FE->>SV: {action:"founder_response", text:"..."}
    SV->>ORC: receive_founder_response(text)

    Note over FE,SV: Bargaining phase
    FE->>SV: {action:"accept_offer", offerId:"..."}
    SV->>ORC: receive_bargain_action({type:"accept"})

    FE->>SV: {action:"counter_offer", text:"..."}
    SV->>ORC: receive_bargain_action({type:"counter"})

    FE->>SV: {action:"walk_away"}
    SV->>ORC: receive_bargain_action({type:"walk_away"})

    ORC-->>SV: _q.put({type:"report", data:{...}})
    SV-->>FE: {type:"report"}
    ORC-->>SV: _q.put({type:"__done__"})
    SV->>SV: send_events loop exits
    SV->>FE: WebSocket close
    FE->>FE: wsRef.disconnect()
```

---

## 16. Cloud Build & Cloud Run Deployment Flow

From a git push to a live Cloud Run service.

```mermaid
flowchart TD
    A[git push\nto GitHub main] --> B[Cloud Build trigger\nfires automatically]

    B --> C[Clone repo\nto /workspace]

    C --> D[Step 1: docker build\n-f Dockerfile\nbuild context = .]

    D --> E[Stage 1: node:20-slim\nWORKDIR /app/frontend\nnpm install\nnpm run build\nOutput: /app/frontend/dist]

    E --> F[Stage 2: python:3.11-slim\nCOPY backend/ .\nCOPY dist → ./static\npip install requirements]

    F --> G[Image tagged\ngcr.io/PROJECT/vc-shark-tank-backend:COMMIT_SHA]

    G --> H[Step 2: docker push\nto Artifact Registry]

    H --> I[Step 3: gcloud run deploy\nvc-sharktank-simulator-gemini\n--image ...COMMIT_SHA\n--region asia-northeast1\n--memory 1Gi\n--min-instances 1\n--max-instances 5\n--timeout 300]

    I --> J[Cloud Run pulls image\nfrom Artifact Registry]

    J --> K[New revision deployed\nTraffic shifted to new revision]

    K --> L[Health check\nGET /health]
    L --> M{200 OK?}
    M -->|Yes| N[Deployment complete\nService live]
    M -->|No| O[Rollback to\nprevious revision]

    subgraph Runtime
        N --> P[Request arrives\nat Cloud Run URL]
        P --> Q{Path?}
        Q -->|/health /config /ws-simulate| R[FastAPI routes]
        Q -->|/assets/*| S[StaticFiles\ndist/assets]
        Q -->|/ or SPA route| T[FileResponse\ndist/index.html]
    end
```

---

## 17. Full End-to-End Flow

The complete journey from page load through simulation completion.

```mermaid
flowchart TD
    A([User opens URL]) --> B[React SPA loads\nfrom /index.html]
    B --> C[Fetch /config\ndetermine auth mode]
    C --> D{Vertex AI?}
    D -->|Yes| E[Skip API modal\nShow SetupScreen]
    D -->|No| F[Show API key modal\nor load from localStorage]
    F --> E

    E --> G[User fills in:\nStartup details\nFounder mode AI/REAL\nModel selection\nRound count]
    G --> H[Click Launch Simulation]

    H --> I[setStep SIMULATION\nsetIsProcessing true\nconnect WebSocket]
    I --> J[Send start message]

    J --> K[Backend: init 5 ADK agents\ncreate sessions]
    K --> L[emit model_update\nFE updates config.model]

    L --> M[PITCH PHASE\nFounder pitches\nemit pitch event]
    M --> N[FE: queue pitch\ntext + speech play]

    N --> O[ROUND LOOP\nFor each round 1..N]
    O --> P[Shuffle investor order]

    P --> Q[For each active investor\nin random order]
    Q --> R[Investor question\nemit question]
    R --> S[FE: queue question\nspeech ends → unlock input]

    S --> T{Founder mode?}
    T -->|REAL| U[User types answer\nclicks Submit\nWS: founder_response]
    T -->|AI| V[FounderAgent\ngenerates answer]

    U & V --> W[emit founder_response\nFE: queue response]
    W --> X[Parallel evaluation\nasyncio.gather × 4 agents\nemit investor_update × 4]

    X --> Y{Any investor\nconf ≤ 25?}
    Y -->|Yes| Z[Parallel exit speeches\nemit exit_speech × N]
    Y -->|No| AA[Continue]
    Z --> AA

    AA --> BB{Banter\n25% chance?}
    BB -->|Yes| CC[Investor banter\nemit banter]
    BB -->|No| DD[Next investor in round]
    CC --> DD

    DD --> Q
    Q -->|Round complete| EE{More rounds?}
    EE -->|Yes| O
    EE -->|No| FF[BARGAINING PHASE]

    FF --> GG[Build offers\nemit offer_speech × N\nemit bargaining_start]
    GG --> HH[FE: show offer cards\nclear on any action]

    HH --> II{User action?}
    II -->|Accept| JJ[WS: accept_offer]
    II -->|Counter| KK[WS: counter_offer]
    II -->|Walk Away| LL[WS: walk_away]

    JJ & KK & LL --> MM[REPORT PHASE\nParallel investor feedback × 4\nOverall report via Vincent analyst]
    MM --> NN[emit report event]
    NN --> OO[FE: setStep REPORT\ndisconnect WS]

    OO --> PP[ReportScreen\nScore verdict summary\nPer-shark feedback\nDownload HTML memo]
    PP --> QQ{Restart?}
    QQ -->|Yes| E
    QQ -->|No| RR([Done])
```

---

> All diagrams render on GitHub. To view locally, paste any diagram block into [mermaid.live](https://mermaid.live).
