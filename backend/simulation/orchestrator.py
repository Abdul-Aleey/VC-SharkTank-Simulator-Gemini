"""
SimulationOrchestrator — runs the full VC Shark Tank pitch using Google ADK agents.

Architecture
------------
  FounderAgent       — 1 ADK Agent with its own session (AI mode only)
  InvestorAgents[4]  — 4 ADK Agents, each with their own session (independent state)
  Parallel Eval      — asyncio.gather() runs all 4 investor evaluations concurrently
  Banter Fix         — agents receive only the speakers already in chat_history,
                       so cross-shark references are always accurate

Flow
----
  1. FounderAgent pitches (AI) or uses static text (REAL)
  2. For each round:
       a. Each active investor asks one question (sequential ADK calls)
       b. Founder responds (FounderAgent in AI, wait for WS message in REAL)
       c. All active investors evaluate in parallel (asyncio.gather on 4 ADK agents)
       d. Update confidence, drop outs, check investments
       e. Maybe generate banter (only from/about investors who have spoken)
  3. Bargaining phase — generate offers, wait for frontend accept/counter/walk-away
  4. Report — parallel feedback from all 4 investor agents, merged into final memo

Events are streamed to the frontend via an asyncio.Queue consumed by the WebSocket handler.
"""

import asyncio
import json
import os
import random
from google.genai import types as genai_types

from .agents import (
    INVESTOR_IDS,
    INVESTOR_PERSONAS,
    build_founder_agent,
    build_investor_agents,
    build_runners,
)

APP_NAME = "shark_tank"

# Confidence threshold below which an investor drops out
CONFIDENCE_OUT = 25

# Founder personality — pitch style and Q&A behaviour injected into every prompt
PERSONALITY_GUIDE = {
    "excellent": (
        "You are a flawless, elite-level founder. "
        "Your pitch is high-energy and packed with precise metrics — exact gross margin %, CAC, LTV, MRR, runway, TAM. "
        "Under questioning you give specific numbers instantly, handle pressure with confidence, and pre-empt follow-ups."
    ),
    "good": (
        "You are a strong, strategic founder. "
        "Your pitch is well-structured with solid business metrics and a clear narrative. "
        "You know your numbers and give clear reasoning, with only minor gaps under very deep probing."
    ),
    "average": (
        "You are an average founder — prepared but unremarkable. "
        "Your pitch covers the basics without standout data or a compelling hook. "
        "You answer easy questions adequately but get vague when experts press on specifics."
    ),
    "weak": (
        "You are a weak founder who struggles under pressure. "
        "Your pitch is vague — you mention numbers but fumble the specifics. "
        "When questioned you give ranges instead of exact figures ('around 40%'), get flustered by expert follow-ups, and stumble when pressed."
    ),
    "poor": (
        "You are a poorly prepared founder. "
        "Your pitch wanders, misses core metrics, and sounds unconfident. "
        "Under questioning you get defensive, dodge direct answers, pivot to unrelated points, and sometimes contradict what you said earlier."
    ),
    "very_poor": (
        "You are a completely unprepared, panicking founder. "
        "Your pitch is incoherent — you forget key financial basics, give contradictory numbers, and fail to articulate a clear ask. "
        "Under questioning you panic visibly, forget figures you already mentioned, use wrong terminology, and ramble without landing a point."
    ),
}


class SimulationOrchestrator:
    """
    One instance per WebSocket connection / simulation run.
    Streams typed events into `self._q` (asyncio.Queue);
    the WebSocket handler drains that queue and sends JSON to the browser.
    """

    def __init__(self, config: dict, api_key: str = ""):
        self.config   = config
        self.language = config.get("language", "en")
        self.is_ja    = self.language == "ja"
        self.mode     = config.get("mode", "real")
        self.rounds   = int(config.get("rounds", 3))
        self.model    = config.get("model", "gemini-2.5-flash")

        # Auth: Vertex AI (Cloud Run service account) or Google AI Studio (user API key)
        _vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("true", "1", "yes")
        if _vertex:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
            # gemini-3.5-flash may not be on Vertex AI yet — fall back to 2.5-flash
            if self.model == "gemini-3.5-flash":
                self.model = "gemini-2.5-flash"
                self._model_fallback = True
            else:
                self._model_fallback = False
        elif api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
            self._model_fallback = False
        else:
            raise ValueError("No auth: set GOOGLE_GENAI_USE_VERTEXAI=true or provide an API key")

        # Build ADK agents & runners.
        # Each runner gets its own InMemorySessionService — no shared state between
        # the 4 investor runners that execute concurrently via asyncio.gather.
        # A shared service caused intermittent session corruption at exchange 7+
        # (read-modify-write operations interleaved at asyncio yield points).
        self._investor_agents  = build_investor_agents(self.model)
        self._founder_agent    = build_founder_agent(self.model)
        (
            self._investor_runners,
            self._founder_runner,
            self._investor_session_svcs,
            self._founder_session_svc,
        ) = build_runners(self._investor_agents, self._founder_agent, APP_NAME)

        # Per-investor simulation state (not in ADK session — kept here for clarity)
        self.investor_states: dict = {
            inv_id: {
                "confidence":      50,
                "status":          "ACTIVE",
                "questionsAsked":  0,
                "questionsHistory": [],   # every question this investor has asked
                "strengths":       [],
                "weaknesses":      [],
                "risks":           [],
                "trend":           0,
                "thoughtBubble":   "",
                "agentState":      "IDLE",
                "isThinking":      False,
            }
            for inv_id in INVESTOR_IDS
        }

        # Shared conversation history (what's been said, by whom)
        self.chat_history: list[dict] = []

        # Queues for inter-coroutine communication
        self._q:                asyncio.Queue  = asyncio.Queue()   # events → WS
        self._founder_response: asyncio.Queue  = asyncio.Queue()   # REAL mode: typed text
        self._bargain_action:   asyncio.Queue  = asyncio.Queue()   # accept/counter/walk-away

        # Per-investor mutex — prevents concurrent ADK session use for the same investor.
        # Needed when banter and next-question generation run in parallel and the banter
        # speaker happens to be the same investor as the next asker.
        self._investor_locks: dict[str, asyncio.Lock] = {
            inv_id: asyncio.Lock() for inv_id in INVESTOR_IDS
        }

        # Speech-done signal: backend waits here after emitting founder_response so
        # investor evaluation only starts AFTER the frontend has finished playing TTS.
        # Frontend sends {action:"speech_done"} when audio (or silent display) completes.
        # Queue instead of Event: signals accumulate and are consumed in order, so a
        # signal that arrives while the backend is processing (evaluate/banter/prefetch)
        # is not lost — the next wait consumes it immediately instead of timing out.
        self._speech_done_q: asyncio.Queue = asyncio.Queue()

        # Phase state — strictly controls when reports can be generated.
        # ONGOING → BARGAINING → DONE
        self._sim_phase: str = "ONGOING"

        # ADK sessions — created lazily in run()
        self._investor_sessions: dict = {}
        self._founder_session = None

    # ─── Public interface ─────────────────────────────────────────────────────

    async def run(self):
        """Entry point — call once per simulation. Drive the full flow."""
        await self._init_sessions()
        await self._emit("model_update", {"model": self.model})
        if self._model_fallback:
            await self._log(
                "Google ADK Orchestrator",
                "gemini-3.5-flash is not yet available on Vertex AI. Falling back to gemini-2.5-flash.",
                "warning",
            )
        await self._phase_pitch()

        for round_num in range(1, self.rounds + 1):
            await self._log(
                "Google ADK Orchestrator",
                f"Starting Round {round_num} of {self.rounds}...",
                "info",
            )
            active = [i for i in INVESTOR_IDS if self.investor_states[i]["status"] == "ACTIVE"]
            if not active:
                break
            random.shuffle(active)

            # Pre-generated questions: keyed by investor id, filled at end of each
            # exchange so the next investor's question is ready the moment they're called.
            prefetched_questions: dict[str, str] = {}

            for idx, inv_id in enumerate(active):
                if self.investor_states[inv_id]["status"] != "ACTIVE":
                    continue

                # Use prefetched question if available, otherwise generate now
                if inv_id in prefetched_questions:
                    question = prefetched_questions.pop(inv_id)
                else:
                    question = await self._generate_question(inv_id)

                self._add_to_history(inv_id, question)
                await self._emit("question", {
                    "sender":          inv_id,
                    "senderName":      INVESTOR_PERSONAS[inv_id]["name"],
                    "text":            question,
                    "waitForResponse": self.mode == "real",
                })

                # Compute who asks next up-front so both modes can start prefetching early.
                next_asker_pre = next(
                    (a for a in active[idx + 1:] if self.investor_states[a]["status"] == "ACTIVE"),
                    None,
                )
                early_q: str | None = None

                # Founder responds — mode-specific path + question prefetch
                if self.mode == "ai":
                    response = await self._generate_founder_response(question, inv_id)

                    self._add_to_history("founder", response)
                    await self._emit("founder_response", {
                        "sender":     "founder",
                        "senderName": self.config.get("founderName", "Founder"),
                        "text":       response,
                    })

                    # AI mode: run evaluate AND next question gen concurrently with TTS
                    # (~10-15 s window).  Evaluate (~5-8 s) and question gen (~3-5 s) both
                    # finish before TTS ends → gap after speech_done drops to ~0-5 s (banter
                    # only), down from ~12-15 s (serial evaluate + question).
                    if next_asker_pre:
                        results = await asyncio.gather(
                            self._wait_for_speech_done(),
                            self._generate_question(next_asker_pre),
                            self._parallel_evaluate(response, round_num),
                            return_exceptions=True,
                        )
                        early_q = results[1] if isinstance(results[1], str) else None
                    else:
                        # No next asker: evaluate only — do NOT block on speech_done.
                        # Bargaining starts as soon as evaluate finishes; the offer
                        # panel appears immediately while the last TTS is still playing
                        # (bargaining_start is handled immediately by the frontend).
                        await self._parallel_evaluate(response, round_num)

                else:
                    # REAL mode: generate next question while user reads and types (~30-60 s).
                    # silent=True prevents the next investor flashing "ASKING" while the user
                    # is still answering the current question.
                    if next_asker_pre:
                        real_results = await asyncio.gather(
                            self._founder_response.get(),
                            self._generate_question(next_asker_pre, silent=True),
                            return_exceptions=True,
                        )
                        response = real_results[0] if isinstance(real_results[0], str) else ""
                        early_q = real_results[1] if isinstance(real_results[1], str) else None
                    else:
                        response = await self._founder_response.get()

                    self._add_to_history("founder", response)
                    await self._emit("founder_response", {
                        "sender":     "founder",
                        "senderName": self.config.get("founderName", "Founder"),
                        "text":       response,
                    })
                    # REAL mode: speech_done fires immediately; evaluate runs after.
                    await self._wait_for_speech_done()
                    await self._parallel_evaluate(response, round_num)

                # Post-evaluate: find actual next asker (status may have changed)
                next_asker = next(
                    (a for a in active[idx + 1:] if self.investor_states[a]["status"] == "ACTIVE"),
                    None,
                )

                if early_q is not None and next_asker == next_asker_pre:
                    # Early prefetch is valid — store it and just run banter
                    prefetched_questions[next_asker] = early_q
                    await self._maybe_banter()
                elif next_asker:
                    # No valid early prefetch — generate question + banter in parallel
                    # (original approach; also handles REAL mode and rare drop-out cases)
                    gathered = await asyncio.gather(
                        self._maybe_banter(),
                        self._generate_question(next_asker),
                        return_exceptions=True,
                    )
                    q_result = gathered[1]
                    prefetched_questions[next_asker] = q_result if isinstance(q_result, str) else ""
                else:
                    await self._maybe_banter()

                self.investor_states[inv_id]["questionsAsked"] += 1

        # All rounds complete — transition to BARGAINING phase
        rounds_done_text = (
            f"全{self.rounds}ラウンドのピッチが終了しました。オファーフェーズに移行します。"
            if self.is_ja else
            f"All {self.rounds} pitch rounds complete. Moving to the offer phase."
        )
        await self._emit("system_message", {"text": rounds_done_text})

        self._sim_phase = "BARGAINING"
        await self._emit("phase_change", {"phase": "BARGAINING"})

        await self._phase_bargaining()

    async def receive_founder_response(self, text: str):
        """Called by the WS handler when the user submits their answer (REAL mode)."""
        await self._founder_response.put(text)

    async def receive_bargain_action(self, action: dict):
        """Called by the WS handler when the user accepts / counters / walks away."""
        await self._bargain_action.put(action)

    async def receive_speech_done(self):
        """Called by the WS handler when frontend confirms TTS playback finished.
        Unblocks _wait_for_speech_done() so investor evaluation can begin."""
        await self._speech_done_q.put(True)

    @property
    def event_queue(self) -> asyncio.Queue:
        return self._q

    # ─── Session initialisation ───────────────────────────────────────────────

    async def _init_sessions(self):
        for inv_id in INVESTOR_IDS:
            session = await self._investor_session_svcs[inv_id].create_session(
                app_name=APP_NAME,
                user_id=f"{inv_id}_user",
            )
            self._investor_sessions[inv_id] = session

        self._founder_session = await self._founder_session_svc.create_session(
            app_name=APP_NAME,
            user_id="founder_user",
        )

    # ─── Pitch phase ──────────────────────────────────────────────────────────

    async def _phase_pitch(self):
        await self._set_founder_agent_state("PITCHING")

        if self.mode == "ai":
            await self._log("Founder Agent", "Generating opening pitch via Google ADK...", "info")
            personality_key = self.config.get('personality', 'excellent')
            personality_desc = PERSONALITY_GUIDE.get(personality_key, PERSONALITY_GUIDE["excellent"])
            pitch = await self._run_founder_agent(
                f"""GENERATE PITCH
Startup: {self.config.get('startupName')} ({self.config.get('sector')})
Founder: {self.config.get('founderName')}
Description: {self.config.get('description')}
Ask: {self.config.get('askAmount')} for {self.config.get('askEquity')}% equity
Founder personality: {personality_desc}
Language: {'Japanese' if self.is_ja else 'English'}"""
            )
        else:
            # REAL mode: the human founder delivers their own pitch.
            # Prompt them via a moderator question, then wait for their input.
            await self._set_founder_agent_state("IDLE")
            await self._emit("question", {
                "sender":          "system",
                "senderName":      "Moderator",
                "text":            (
                    "あなたの出番です！シャークたちにスタートアップのピッチを行ってください。"
                    if self.is_ja else
                    "The floor is yours — pitch your startup to the sharks!"
                ),
                "waitForResponse": True,
            })
            pitch = await self._founder_response.get()

        self._add_to_history("founder", pitch)
        await self._set_founder_agent_state("IDLE")
        await self._log("Founder Agent", "Pitch delivered to the panel.", "success")
        await self._emit("pitch", {
            "sender":     "founder",
            "senderName": self.config.get("founderName", "Founder"),
            "text":       pitch,
        })

    # ─── Question generation ──────────────────────────────────────────────────

    async def _generate_question(self, inv_id: str, *, silent: bool = False) -> str:
        """Generate an investor question via ADK.

        silent=True suppresses agentState UI updates — used when prefetching
        a question in the background while the user is still typing their
        current answer, so the next investor doesn't flash "ASKING" prematurely.
        """
        name = INVESTOR_PERSONAS[inv_id]["name"]
        if not silent:
            await self._log(f"{name} Agent", "Formulating strategic question via ADK...", "info")
            self.investor_states[inv_id]["agentState"] = "ASKING"
            await self._emit_investor_update(inv_id)

        history_str   = self._history_str(last=10)
        founder_first = self.config.get('founderName', 'Founder').split()[0]

        prev_qs = self.investor_states[inv_id]["questionsHistory"]
        if prev_qs:
            avoid_block = (
                "\nTopics you have ALREADY asked about (do not repeat or rephrase these):\n"
                + "\n".join(f"  - {q}" for q in prev_qs)
                + "\nAsk about a completely different angle.\n"
            )
        else:
            avoid_block = ""

        focus = INVESTOR_PERSONAS[inv_id]["focus"]
        prompt = f"""GENERATE QUESTION
You are the world's sharpest investor in: {focus}

Startup: {self.config.get('startupName')} ({self.config.get('sector')})
Ask: {self.config.get('askAmount')} for {self.config.get('askEquity')}%
Description: {self.config.get('description')}
Founder's first name: {founder_first}
{avoid_block}
Conversation so far:
{history_str}

Ask ONE expert-level question that:
- Pinpoints a specific claim, number, or gap from what the founder said above
- Uses your deep expertise in {focus} to expose something most investors would miss
- Cannot be answered with vague platitudes
- Is under 40 words, direct, conversational — no preamble or meta-text
- Do NOT use the founder's name in the question. Ask directly without addressing them by name.
Language: {'Japanese' if self.is_ja else 'English'}"""

        text = await self._run_investor_agent(inv_id, prompt)
        question = self._strip_md(text)

        # Record so future rounds avoid repeating this topic
        self.investor_states[inv_id]["questionsHistory"].append(question)

        if not silent:
            self.investor_states[inv_id]["agentState"] = "IDLE"
            await self._emit_investor_update(inv_id)
        return question

    # ─── Founder response ─────────────────────────────────────────────────────

    async def _generate_founder_response(self, question: str, questioner_id: str) -> str:
        await self._log("Founder Agent", "Generating response via ADK...", "info")
        await self._set_founder_agent_state("PITCHING")

        history_str = self._history_str(last=8)
        personality_key  = self.config.get('personality', 'excellent')
        personality_desc = PERSONALITY_GUIDE.get(personality_key, PERSONALITY_GUIDE["excellent"])
        prompt = f"""GENERATE RESPONSE
You are: {self.config.get('founderName')}, founder of {self.config.get('startupName')}
Founder personality: {personality_desc}
Question from {INVESTOR_PERSONAS[questioner_id]['name']}: "{question}"

Conversation so far:
{history_str}

Answer as a real founder under pressure — direct, confident, specific about facts and numbers.
Do not open with compliments about the question (no "Great question", "Excellent question", etc.) — go straight to the answer.
Use the investor's name only if it sounds natural, not in every sentence.
Under 60 words. No meta-text.
Language: {'Japanese' if self.is_ja else 'English'}"""

        text = await self._run_founder_agent(prompt)
        await self._set_founder_agent_state("IDLE")
        return text.strip()

    # ─── Parallel evaluation (core multi-agent feature) ───────────────────────

    async def _parallel_evaluate(self, founder_response: str, round_num: int = 1):
        """
        All active investor agents evaluate the founder's response simultaneously.
        This is the true multi-agent parallelism: 4 independent ADK agents,
        each with their own session, running concurrently via asyncio.gather().
        round_num is the actual outer-loop round so every agent sees the same
        round context regardless of how many questions they personally have asked.
        """
        active = [i for i in INVESTOR_IDS if self.investor_states[i]["status"] == "ACTIVE"]

        # Set all active investors to EVALUATING
        for inv_id in active:
            self.investor_states[inv_id]["agentState"]  = "EVALUATING"
            self.investor_states[inv_id]["isThinking"]  = True
        await self._emit_all_investor_updates()

        agent_names = ", ".join(INVESTOR_PERSONAS[i]["name"] for i in active)
        await self._log(
            "Google ADK Orchestrator",
            f"Dispatching evaluation to {len(active)} investor agents in parallel: {agent_names}",
            "info",
        )

        # Run all evaluations concurrently — each is a separate ADK agent call
        tasks   = [self._evaluate_single_investor(inv_id, founder_response, round_num) for inv_id in active]
        results = await asyncio.gather(*tasks)
        result_map = dict(zip(active, results))

        # Apply results
        exit_speeches = []
        for inv_id, result in result_map.items():
            state       = self.investor_states[inv_id]
            new_conf    = result.get("confidence", state["confidence"])
            trend       = new_conf - state["confidence"]

            await self._log(
                f"{INVESTOR_PERSONAS[inv_id]['name']} Agent",
                f"Evaluation complete. Confidence: {new_conf}%  ({'+' if trend>=0 else ''}{trend}%)",
                "success",
            )

            state["confidence"]    = new_conf
            state["trend"]         = trend
            state["thoughtBubble"] = result.get("thoughtBubble", "")
            state["strengths"]    += result.get("strengths", [])
            state["weaknesses"]   += result.get("weaknesses", [])
            state["risks"]        += result.get("risks", [])
            state["isThinking"]    = False

            if new_conf <= CONFIDENCE_OUT:
                state["status"]     = "OUT"
                state["confidence"] = 0
                state["agentState"] = "OUT"
                exit_speeches.append(inv_id)
            else:
                # Confidence can exceed 85 during rounds but INVEST status is only
                # determined after all rounds complete — investors keep asking questions
                state["agentState"] = "IDLE"

        await self._emit_all_investor_updates()

        # Generate all exit speeches in parallel (each is a real ADK agent call)
        if exit_speeches:
            await self._log(
                "Google ADK Orchestrator",
                f"Generating exit speeches for: {', '.join(INVESTOR_PERSONAS[i]['name'] for i in exit_speeches)}",
                "warning",
            )
            exit_tasks = [self._generate_exit_speech(inv_id) for inv_id in exit_speeches]
            exit_texts_raw = await asyncio.gather(*exit_tasks, return_exceptions=True)
            exit_texts = [t if isinstance(t, str) else "" for t in exit_texts_raw]

            for inv_id, exit_txt in zip(exit_speeches, exit_texts):
                name = INVESTOR_PERSONAS[inv_id]["name"]
                self._add_to_history(inv_id, exit_txt)
                await self._emit("exit_speech", {
                    "sender":     inv_id,
                    "senderName": name,
                    "text":       exit_txt,
                })
                await self._emit("system_message", {
                    "text": f"{name} is OUT" if not self.is_ja else f"{name}が脱落しました",
                })

    async def _evaluate_single_investor(
        self, inv_id: str, founder_response: str, round_num: int = 1
    ) -> dict:
        """One investor agent evaluates — this runs in parallel with the other 3."""
        state    = self.investor_states[inv_id]
        name     = INVESTOR_PERSONAS[inv_id]["name"]
        fallback = {
            "confidence":    state["confidence"],
            "thoughtBubble": "Processing...",
            "strengths":     [],
            "weaknesses":    [],
            "risks":         [],
        }
        try:
            history_str   = self._history_str(last=10)
            founder_first = self.config.get('founderName', 'Founder').split()[0]
            focus = INVESTOR_PERSONAS[inv_id]["focus"]
            prompt = f"""EVALUATE RESPONSE
You are {name}, a sharp investor focused on: {focus}.

Founder ({founder_first}) said: "{founder_response}"
Startup: {self.config.get('startupName')} ({self.config.get('sector')})
Ask: {self.config.get('askAmount')} for {self.config.get('askEquity')}%
Your current confidence: {state['confidence']}%
Round: {round_num} of {self.rounds}
NAMING RULE: In thoughtBubble text use "{founder_first}" not "he/she/the founder".

Conversation history:
{history_str}

CONFIDENCE RULES — you MUST adjust the number, never echo it back unchanged:
- Strong, specific answer with real metrics → increase by 8–18
- Solid answer but vague on details → increase by 3–7
- Neutral / no new info → decrease by 2–5
- Weak, evasive, or contradictory answer → decrease by 8–15
- Serious red flag or direct lie → decrease by 15–25
Base the change on YOUR focus area ({focus}). The new value must be 0–100.

Return ONLY valid JSON, no markdown fences:
{{
  "confidence": <integer 0-100>,
  "thoughtBubble": "<internal thought, max 15 words>",
  "strengths": ["<one strength>"],
  "weaknesses": ["<one weakness>"],
  "risks": ["<one risk>"]
}}
Language for text fields: {'Japanese' if self.is_ja else 'English'}"""

            raw = await self._run_investor_agent(inv_id, prompt)
            return self._parse_json(raw, fallback)
        except Exception as exc:
            await self._log(name, f"Evaluation skipped ({exc.__class__.__name__}) — holding current confidence.", "warning")
            return fallback

    # ─── Banter (bug-fixed: only references speakers in chat_history) ─────────

    async def _maybe_banter(self):
        active = [i for i in INVESTOR_IDS if self.investor_states[i]["status"] == "ACTIVE"]
        if len(active) < 2 or random.random() > 0.25:
            return

        speaker = random.choice(active)

        # KEY FIX: only include investors who have actually spoken
        already_spoke = {
            m["sender"]
            for m in self.chat_history
            if m["sender"] in INVESTOR_IDS and m["sender"] != speaker
        }
        if not already_spoke:
            return  # No other investor has spoken yet — no valid banter target

        referenceable = ", ".join(
            INVESTOR_PERSONAS[i]["name"] for i in already_spoke
        )
        history_str   = self._history_str(last=6)

        founder_first = self.config.get('founderName', 'Founder').split()[0]
        prompt = f"""GENERATE BANTER
You are {INVESTOR_PERSONAS[speaker]['name']} reacting spontaneously to the pitch.

CRITICAL: You may ONLY reference investors who have already spoken.
Investors you may reference (first names only): {referenceable}
Do NOT mention any other investor by name.

NAMING RULE: Use first names only — never pronouns ("he", "she", "they") for any person.
When referring to the founder, use "{founder_first}", not "he", "she", or "the founder".

Recent conversation:
{history_str}

One punchy reaction (under 25 words) — a comment, observation, witty remark, or friendly dig.
RULE: Do NOT ask a question. No "?" marks. This is a side comment, never an inquiry.
No quotes, no meta-text.
Language: {'Japanese' if self.is_ja else 'English'}"""

        await self._log(
            f"{INVESTOR_PERSONAS[speaker]['name']} Agent",
            "Generating spontaneous banter...",
            "warning",
        )
        text = await self._run_investor_agent(speaker, prompt)
        text = self._strip_md(text).strip('"').strip("'")
        if not text:
            return

        self.investor_states[speaker]["agentState"] = "BANTERING"
        await self._emit_investor_update(speaker)
        self._add_to_history(speaker, text, is_banter=True)
        await self._emit("banter", {
            "sender":     speaker,
            "senderName": INVESTOR_PERSONAS[speaker]["name"],
            "text":       text,
        })
        self.investor_states[speaker]["agentState"] = "IDLE"
        await self._emit_investor_update(speaker)

    async def _joint_partner_endorsement(self, partner_id: str, lead_id: str, offer: dict):
        """The non-lead joint partner adds their own angle after the lead presents the terms.
        They don't repeat the numbers — they pitch the specific value THEY personally bring."""
        partner_p = INVESTOR_PERSONAS[partner_id]
        lead_name = INVESTOR_PERSONAS[lead_id]["name"]
        founder_first = self.config.get("founderName", "Founder").split()[0]

        prompt = f"""JOINT OFFER CO-PITCH
You are {partner_p['name']} — {partner_p['bio']}
Your expertise: {partner_p['focus']}

{lead_name} just presented the joint offer terms. Now it's your turn to speak.
Open by briefly acknowledging the partnership — e.g. "I'm joining {lead_name} on this deal" or
"We're coming in together on this." Then in 1-2 sentences (under 35 words total), tell {founder_first}
specifically what YOU personally bring that makes this joint deal stronger than any solo offer.
Be concrete about your expertise and network. Do NOT repeat the equity or dollar amounts.
Sound natural and confident. No meta-text. No quotes.
Language: {'Japanese' if self.is_ja else 'English'}"""

        text = await self._run_investor_agent(partner_id, prompt)
        text = self._strip_md(text).strip('"').strip("'")
        if not text:
            return

        self._add_to_history(partner_id, text)
        await self._emit("banter", {
            "sender":     partner_id,
            "senderName": partner_p["name"],
            "text":       text,
        })
        # Banter events are fire-and-forget — frontend does not send speech_done for banter.

    async def _maybe_offer_banter(self, just_offered_id: str, offer: dict, active_offers: dict):
        """After a shark presents their offer, a rival reacts — pitching their own value or
        their combined joint-deal strength. 35% chance. Joint partners never undercut each other."""

        # Build joint-partnership map: investor_id → partner_id (if in a joint deal)
        joint_partner_of: dict[str, str] = {}
        for o in active_offers.values():
            if o.get("isJoint") and len(o["investors"]) >= 2:
                a, b = o["investors"][0], o["investors"][1]
                joint_partner_of[a] = b
                joint_partner_of[b] = a

        # Reactor pool: all lead investors + non-lead joint partners, minus the one who just spoke
        # and minus anyone who is a joint partner of the just-offered investor (same team).
        just_offered_partner = joint_partner_of.get(just_offered_id)
        all_investors_in_play = set(active_offers.keys())
        for o in active_offers.values():
            if o.get("isJoint"):
                all_investors_in_play.update(o["investors"])

        others = [
            i for i in all_investors_in_play
            if i != just_offered_id and i != just_offered_partner
        ]
        if not others or random.random() > 0.35:
            return

        reactor       = random.choice(others)
        reactor_p     = INVESTOR_PERSONAS[reactor]
        reactor_partner = joint_partner_of.get(reactor)
        offerer_name  = INVESTOR_PERSONAS[just_offered_id]["name"]
        founder_first = self.config.get("founderName", "Founder").split()[0]
        startup_name  = self.config.get("startupName", "this startup")
        history_str   = self._history_str(last=8)

        # Build reactor identity section — solo vs joint changes how they pitch themselves
        if reactor_partner:
            partner_p = INVESTOR_PERSONAS[reactor_partner]
            identity_block = (
                f"You are {reactor_p['name']} — making a JOINT offer with {partner_p['name']}.\n"
                f"Your expertise: {reactor_p['focus']}\n"
                f"{partner_p['name']}'s expertise: {partner_p['focus']}\n"
                f"Together you cover: {reactor_p['focus']} + {partner_p['focus']}"
            )
            pitch_angle = (
                f"Pitch the COMBINED power of you and {partner_p['name']} as a team. "
                f"Explain what the two of you can do together for {startup_name} that no single investor can. "
                f"NEVER say anything negative about {partner_p['name']} — you are partners."
            )
        else:
            identity_block = (
                f"You are {reactor_p['name']} — {reactor_p['bio']}\n"
                f"Your investment focus: {reactor_p['focus']}"
            )
            pitch_angle = (
                f"Be specific about what YOU bring beyond the money — your network, domain expertise, "
                f"or strategic value that {offerer_name} simply cannot offer {startup_name}."
            )

        prompt = f"""OFFER PHASE REACTION
{identity_block}

{offerer_name} just presented: {offer['cash']} for {offer['equity']}% equity. Terms: {offer.get('terms', 'standard equity')}.

React in one punchy line (under 28 words). {pitch_angle}
Sound like a real shark — confident, sharp, direct. Appeal to {founder_first} by name if it flows naturally.

RULES: No "?" marks. No questions. No quotes or meta-text. First names only for other investors.
Language: {'Japanese' if self.is_ja else 'English'}

Recent room context:
{history_str}"""

        text = await self._run_investor_agent(reactor, prompt)
        text = self._strip_md(text).strip('"').strip("'")
        if not text:
            return

        self._add_to_history(reactor, text, is_banter=True)
        await self._emit("banter", {
            "sender":     reactor,
            "senderName": reactor_p["name"],
            "text":       text,
        })

        # ~15% chance the founder briefly acknowledges the banter — a light remark,
        # a gracious nod, or a dry comment. Keeps them present in the room, not silent.
        if random.random() < 0.15:
            reactor_name     = reactor_p["name"]
            founderName      = self.config.get("founderName", "Founder")
            personality_key  = self.config.get("personality", "excellent")
            personality_desc = PERSONALITY_GUIDE.get(personality_key, PERSONALITY_GUIDE["excellent"])
            reply_prompt     = f"""FOUNDER BANTER REPLY
You are {founderName}, founder of {self.config.get('startupName')} ({self.config.get('sector', '')}).
Founder personality: {personality_desc}

You are in the middle of an offer negotiation. {reactor_name} just said something to pitch themselves.
Their comment: "{text}"

Reply in one short line (under 20 words) — stay true to your personality above.
Respond naturally to the room — you are not committing to anything, just present and engaged.
No questions. No meta-text. No quotes.
Language: {'Japanese' if self.is_ja else 'English'}"""

            reply = self._strip_md(await self._run_founder_agent(reply_prompt)).strip('"').strip("'")
            if reply:
                self._add_to_history("founder", reply)
                await self._emit("banter", {
                    "sender":     "founder",
                    "senderName": founderName,
                    "text":       reply,
                })

    # ─── Bargaining phase ─────────────────────────────────────────────────────

    async def _phase_bargaining(self):
        # Drain any stale speech_done signals left over from the Q&A phase.
        # When the last Q&A round has no next asker, the backend skips _wait_for_speech_done()
        # but the frontend still sends one after TTS ends. Without this drain, the stale signal
        # would be consumed by the first offer_speech wait, causing it to resolve before TTS finishes.
        while not self._speech_done_q.empty():
            self._speech_done_q.get_nowait()

        qualifying = [
            i for i in INVESTOR_IDS
            if self.investor_states[i]["confidence"] > CONFIDENCE_OUT
            and self.investor_states[i]["status"] != "OUT"
        ]

        if not qualifying:
            no_deal_text = (
                "オファー基準を満たす投資家がいません。評価レポートへ移行します。"
                if self.is_ja else
                "No investors met the offer threshold. Proceeding to the evaluation report."
            )
            await self._emit("system_message", {"text": no_deal_text})
            await self._generate_report(deal=None)
            return

        # All rounds done — mark qualifying investors as INVEST
        for inv_id in qualifying:
            self.investor_states[inv_id]["status"]     = "INVEST"
            self.investor_states[inv_id]["agentState"] = "INVESTED"
        await self._emit_all_investor_updates()

        investor_names = ", ".join(INVESTOR_PERSONAS[i]["name"] for i in qualifying)
        await self._emit("system_message", {
            "text": (
                f"オファーフェーズ開始。{investor_names}がオファーを提示します。"
                if self.is_ja else
                f"Offer phase begins. {investor_names} will now present their terms."
            )
        })

        # Build mutable offers dict keyed by lead investor id (ADK-generated terms)
        try:
            offers_list = await self._build_offers(qualifying)
        except Exception as exc:
            await self._log("Google ADK Orchestrator", f"Offer generation failed: {exc}", "error")
            await self._generate_report(deal=None)
            return
        active_offers = {o["investors"][0]: o for o in offers_list}

        # Each investor speaks their offer one at a time; wait for speech_done so cards
        # reveal one-by-one in sync with each shark's spoken offer.
        offers_so_far = []
        for lead_id, offer in active_offers.items():
            rep_name    = INVESTOR_PERSONAS[lead_id]["name"]
            offer_speech = await self._generate_offer_speech(lead_id, offer)
            self._add_to_history(lead_id, offer_speech)
            # Flush any stale speech_done that arrived late during the previous banter
            # (banter TTS can outlast the 60 s timeout and send its signal mid-loop).
            while not self._speech_done_q.empty():
                self._speech_done_q.get_nowait()
            await self._emit("offer_speech", {
                "sender": lead_id, "senderName": rep_name,
                "text": offer_speech, "offer": offer,
            })
            await self._wait_for_speech_done()

            # Joint offer: partner (j1) adds their angle after j0 presents the terms
            if offer.get("isJoint") and len(offer["investors"]) >= 2:
                partner_id = offer["investors"][1]
                await self._joint_partner_endorsement(partner_id, lead_id, offer)

            offers_so_far.append((lead_id, offer))
            # Rivals react after each offer — but skip banter after the last one so
            # the negotiation phase starts promptly without extra TTS queuing up.
            is_last_offer = len(offers_so_far) == len(active_offers)
            if not is_last_offer:
                await self._maybe_offer_banter(lead_id, offer, active_offers)

        # Drain any speech_done signals that arrived late (banter TTS finished after the
        # 60 s timeout fired). Without this, stale signals bleed into the negotiation loop
        # and cause _wait_for_speech_done calls there to resolve instantly on wrong events.
        while not self._speech_done_q.empty():
            self._speech_done_q.get_nowait()

        # Emit panel marker — queued behind TTS on frontend so bargaining buttons
        # only unlock after all offer speeches have finished playing.
        await self._emit("bargaining_start", {"offers": list(active_offers.values()), "isRevision": False})

        # ── Negotiation loop ────────────────────────────────────────────────
        # REAL mode: unbounded — the human decides when to stop (accept/walk away).
        # AI mode: capped at 4 rounds then force-accepts best remaining offer.
        # Every terminal path calls `return`; the loop only continues when
        # a shark counter-counters or an offer is rejected but others remain.
        MAX_AI_ROUNDS = 4
        neg_round     = 0

        while active_offers:
            neg_round += 1

            # AI-only safety: after 4 rounds, force a final decision (accept or walk away)
            # — prevents infinite counter loops while still respecting the founder's judgement.
            if self.mode == "ai" and neg_round > MAX_AI_ROUNDS:
                await self._emit("system_message", {
                    "text": ("交渉ラウンドが終了しました。起業家が最終判断を下します。"
                             if self.is_ja else
                             "Negotiation rounds complete. The founder makes their final call.")
                })
                decision    = await self._ai_founder_decide_action(active_offers)
                action_type = decision.get("action", "accept")
                # Counter is no longer allowed at this point — collapse it to accept
                if action_type == "counter":
                    action_type = "accept"
                target_id = decision.get("investorId", min(active_offers, key=lambda i: active_offers[i]["equity"]))
                if target_id not in active_offers:
                    target_id = min(active_offers, key=lambda i: active_offers[i]["equity"])
                speech = decision.get("speech", "")
                if speech:
                    self._add_to_history("founder", speech)
                    await self._emit("founder_response", {
                        "sender": "founder",
                        "senderName": self.config.get("founderName", "Founder"),
                        "text": speech,
                    })
                if action_type == "walk_away":
                    await self._emit("system_message", {
                        "text": ("起業家はすべてのオファーを辞退し、タンクを去りました。"
                                 if self.is_ja else
                                 "The entrepreneur walked away from all offers.")
                    })
                    await self._generate_report(deal=None)
                else:
                    await self._close_deal(active_offers[target_id])
                return

            # ── Get next action ────────────────────────────────────────────
            if self.mode == "ai":
                decision     = await self._ai_founder_decide_action(active_offers)
                action_type  = decision.get("action", "accept")
                target_id    = decision.get("investorId", list(active_offers.keys())[0])
                counter_text = decision.get("counterText", "")

                # Founder speaks their reasoning to the room
                speech = self._strip_md(decision.get("speech", ""))
                if speech:
                    self._add_to_history("founder", speech)
                    await self._set_founder_agent_state("PITCHING")
                    await self._emit("founder_response", {
                        "sender":     "founder",
                        "senderName": self.config.get("founderName", "Founder"),
                        "text":       speech,
                    })
                    # Consume the speech_done the frontend sends after TTS so it
                    # doesn't leak into the next _wait_for_speech_done (revised offer).
                    await self._wait_for_speech_done()
                    await self._set_founder_agent_state("IDLE")
            else:
                # REAL mode — block until the user sends an action
                payload      = await self._bargain_action.get()
                action_type  = payload.get("type")
                target_id    = payload.get("investorId", list(active_offers.keys())[0])
                counter_text = payload.get("text", "")

            # Guard: target must exist in active offers
            if target_id not in active_offers:
                target_id = list(active_offers.keys())[0]

            # ── Process action ─────────────────────────────────────────────
            if action_type == "accept":
                await self._close_deal(active_offers[target_id])
                return  # ← terminates

            elif action_type == "counter":
                target_offer = active_offers[target_id]
                target_name  = INVESTOR_PERSONAS[target_id]["name"]

                # REAL mode: announce counter (AI mode already spoke above)
                if self.mode == "real":
                    fc = (f"{target_name}へのカウンターオファー：{counter_text}"
                          if self.is_ja else
                          f"Counter-offer to {target_name}: {counter_text}")
                    self._add_to_history("founder", fc)
                    await self._set_founder_agent_state("PITCHING")
                    await self._emit("founder_response", {
                        "sender":     "founder",
                        "senderName": self.config.get("founderName", "Founder"),
                        "text":       fc,
                    })
                    await self._set_founder_agent_state("IDLE")

                await self._emit("system_message", {
                    "text": (f"{target_name}がカウンターを検討しています..."
                             if self.is_ja else
                             f"{target_name} is evaluating your counter...")
                })

                result = await self._evaluate_counter_offer(
                    target_id, counter_text, target_offer
                )

                # Shark speaks their response in their own voice
                speech_text = self._strip_md(result.get("speech", ""))
                self._add_to_history(target_id, speech_text)
                await self._emit("banter", {
                    "sender":     target_id,
                    "senderName": target_name,
                    "text":       speech_text,
                })

                if result["accepted"]:
                    await self._close_deal(target_offer)
                    return  # ← terminates

                elif result.get("counter_offer"):
                    # Shark counter-countered — have them speak the revised offer,
                    # then update the card after their speech completes.
                    cc      = result["counter_offer"]
                    updated = {
                        **target_offer,
                        "cash":    cc.get("cash",   target_offer["cash"]),
                        "equity":  cc.get("equity", target_offer["equity"]),
                        "terms":   cc.get("terms",  target_offer["terms"]),
                        "revised": True,
                    }
                    active_offers[target_id] = updated
                    revised_speech = await self._generate_offer_speech(target_id, updated)
                    self._add_to_history(target_id, revised_speech)
                    # Drain any stale speech_done from the founder's negotiation speech
                    # (AI mode sends speech_done after founder_response TTS; nobody waits for it
                    # in the negotiation path, so it would incorrectly satisfy this wait).
                    while not self._speech_done_q.empty():
                        self._speech_done_q.get_nowait()
                    await self._emit("offer_speech", {
                        "sender": target_id, "senderName": target_name,
                        "text": revised_speech, "offer": updated,
                    })
                    await self._wait_for_speech_done()
                    # Sync full panel state after speech completes
                    await self._emit("bargaining_start",
                                     {"offers": list(active_offers.values()), "isRevision": True})

                else:
                    # Hard reject — remove this offer from the table
                    del active_offers[target_id]
                    await self._emit("system_message", {
                        "text": (f"{target_name}はオファーを撤回しました。"
                                 if self.is_ja else
                                 f"{target_name} withdrew their offer.")
                    })
                    if not active_offers:
                        await self._emit("system_message", {
                            "text": ("交渉決裂。残りのオファーがありません。"
                                     if self.is_ja else
                                     "Negotiation broke down. No remaining offers.")
                        })
                        await self._generate_report(deal=None)
                        return  # ← terminates
                    # Show remaining offers after withdrawal; loop continues
                    await self._emit("bargaining_start",
                                     {"offers": list(active_offers.values()), "isRevision": True})

            else:  # walk_away — founder declines all offers
                await self._emit("system_message", {
                    "text": ("起業家はすべてのオファーを辞退し、タンクを去りました。"
                             if self.is_ja else
                             "The entrepreneur walked away from all offers.")
                })
                await self._generate_report(deal=None)
                return  # ← terminates

        # Safety net: active_offers emptied without an explicit return above
        await self._generate_report(deal=None)

    async def _generate_offer_speech(self, inv_id: str, offer: dict) -> str:
        """Generate a natural, personality-driven offer announcement via ADK."""
        name  = INVESTOR_PERSONAS[inv_id]["name"]
        focus = INVESTOR_PERSONAS[inv_id]["focus"]

        # Joint-offer note
        if offer.get("isJoint") and len(offer.get("investors", [])) > 1:
            partner_id   = [i for i in offer["investors"] if i != inv_id]
            partner_name = INVESTOR_PERSONAS[partner_id[0]]["name"] if partner_id else ""
            joint_note   = (
                f"This is a joint offer. Refer to yourself as 'I' and your co-investor as '{partner_name}'. "
                f"Say something like '{partner_name} and I are offering...' or 'I'm teaming up with {partner_name}...'"
            )
        else:
            joint_note = ""

        royalty_hint = (
            "Mention the royalty percentage and that it is calculated on net sales."
            if "royalty" in offer.get("terms", "").lower() else ""
        )

        prompt = f"""GENERATE OFFER
You are {name}. Investment focus: {focus}.
You have decided to make an offer. Here are the exact terms you are offering:
- Amount: {offer['cash']}
- Equity: {offer['equity']}%
- Full deal structure: {offer['terms']}
{joint_note}

Deliver your offer in your own voice — the way YOU would say it on Shark Tank.
Do NOT introduce yourself by name. You are already speaking; just make the offer.
{royalty_hint}
State the amount, equity %, and any royalty or special conditions clearly and specifically.
Under 60 words. No preamble, no meta-text.
Language: {'Japanese' if self.is_ja else 'English'}"""

        await self._log(f"{name} Agent",
                        f"Generating offer speech: {offer['cash']} for {offer['equity']}%", "success")
        text = await self._run_investor_agent(inv_id, prompt)
        text = self._strip_md(text)
        if not text:
            if self.is_ja:
                text = f"{offer['cash']}、株式{offer['equity']}%でオファーします。条件：{offer['terms']}"
            else:
                text = f"I'm in for {offer['cash']} at {offer['equity']}% equity. {offer['terms']}"
        return text

    async def _close_deal(self, offer: dict):
        """Founder accepts an offer: speaks acceptance, emits deal confirmation, generates report."""
        acceptance = await self._generate_acceptance_speech(offer)
        self._add_to_history("founder", acceptance)
        await self._set_founder_agent_state("PITCHING")
        await self._emit("founder_response", {
            "sender": "founder",
            "senderName": self.config.get("founderName", "Founder"),
            "text": acceptance,
        })
        await self._set_founder_agent_state("IDLE")

        investors_str = (" & " if not self.is_ja else "と").join(
            INVESTOR_PERSONAS[i]["name"] for i in offer["investors"]
        )
        await self._emit("system_message", {
            "text": (
                f"成立！{investors_str}と{offer['cash']}（株式{offer['equity']}%）で合意！"
                if self.is_ja else
                f"Deal sealed with {investors_str} — {offer['cash']} for {offer['equity']}% equity!"
            )
        })
        await self._generate_report(deal=offer)

    async def _ai_founder_decide_action(self, active_offers: dict) -> dict:
        """FounderAgent evaluates all current offers and decides negotiation strategy."""
        cfg = self.config
        ask_equity       = int(cfg.get('askEquity', 10))
        personality_key  = cfg.get('personality', 'excellent')
        personality_desc = PERSONALITY_GUIDE.get(personality_key, PERSONALITY_GUIDE["excellent"])

        # Each offer shown with the shark's background so the founder can match expertise to need
        offers_summary = "\n".join(
            f"- {INVESTOR_PERSONAS[inv_id]['name']} ({inv_id}): "
            f"{o['cash']} for {o['equity']}% equity. Terms: {o.get('terms', 'none')} | "
            f"Their expertise: {INVESTOR_PERSONAS[inv_id]['focus']}"
            for inv_id, o in active_offers.items()
        )

        # Investor value pitches from offer-phase banter — what each shark said they bring
        banter_pitches = [
            f"- {INVESTOR_PERSONAS[m['sender']]['name']}: \"{m['text']}\""
            for m in self.chat_history[-20:]
            if m.get("sender") in INVESTOR_IDS and m.get("isBanter")
        ]
        pitch_block = (
            "\nWhat sharks said they bring beyond the money:\n" + "\n".join(banter_pitches)
            if banter_pitches else ""
        )

        prompt = f"""NEGOTIATE as founder
You are {cfg.get('founderName')}, founder of {cfg.get('startupName')} — {cfg.get('description', '')}
Sector: {cfg.get('sector', '')}
Original ask: {cfg.get('askAmount')} for {ask_equity}% equity.
Founder personality: {personality_desc}

Offers on the table (with each investor's domain expertise):
{offers_summary}
{pitch_block}

Recent negotiation:
{self._history_str(last=8)}

Think like a strategic founder: what does {cfg.get('startupName')} need MOST right now to succeed?
Is it financial discipline, tech credibility, brand building, or distribution muscle?
Match that need against the sharks' expertise — then decide who to partner with and how hard to push.
A founder who counters too aggressively risks losing the deal; one who folds too fast leaves value behind.
Pick the move that serves your company, not just your ego.

WALK AWAY: If every offer on the table is a bad deal — equity too high, wrong expertise, terms that would cripple the company — walk away. A bad deal is worse than no deal. Use walk_away if no offer comes close to your original ask and no counter would fix it.

Valid investor IDs: {', '.join(active_offers.keys())}

COUNTER RULE (absolute): If you counter, your equity % MUST be between {ask_equity}% (your original ask) and the investor's offered equity %. The investment amount stays {cfg.get('askAmount')}. Never go below {ask_equity}%.

Return ONLY valid JSON, no markdown fences:
{{
  "action": "accept" | "counter" | "walk_away",
  "investorId": "<exact investor id — required for accept/counter, omit if walk_away>",
  "counterEquity": <integer equity % you are countering with — required if action is counter, must be between {ask_equity} and the investor's offered equity>,
  "speech": "<what you say to the room, 25-40 words — if walk_away, state clearly why you are declining and what was wrong with the offers; if accept/counter, name the investor and your reasoning>",
  "counterText": "<your counter-proposal in plain English — required if action is counter>"
}}
Language: {'Japanese' if self.is_ja else 'English'}"""

        raw     = await self._run_founder_agent(prompt)
        best_id = min(active_offers.keys(), key=lambda i: active_offers[i]["equity"])
        fallback = {
            "action": "accept",
            "investorId": best_id,
            "speech": (f"{INVESTOR_PERSONAS[best_id]['name']}のオファーを受け入れます。"
                       if self.is_ja else
                       f"I'll accept {INVESTOR_PERSONAS[best_id]['name']}'s offer. Let's make this happen."),
            "counterEquity": None,
            "counterText": "",
        }
        result = self._parse_json(raw, fallback)

        # Validate investorId
        if result.get("investorId") not in active_offers:
            result["investorId"] = best_id

        # Server-side clamp counterEquity — never trust the model alone
        if result.get("action") == "counter":
            target_id     = result["investorId"]
            investor_eq   = active_offers[target_id]["equity"]
            raw_ce        = result.get("counterEquity")
            try:
                counter_eq = int(float(str(raw_ce).replace("%", "").strip()))
            except (ValueError, TypeError):
                counter_eq = ask_equity  # fallback to founder's original ask
            # Clamp: must be >= ask_equity and <= investor's offered equity
            counter_eq = max(ask_equity, min(investor_eq, counter_eq))
            result["counterEquity"] = counter_eq
            # counterText stays as the founder's natural phrasing — the validated counterEquity
            # integer is the authoritative source; the shark agent evaluates the proposal in context.

        return result

    async def _generate_acceptance_speech(self, accepted_offer: dict) -> str:
        """Founder speaks their acceptance, naming the shark(s) explicitly."""
        sep = "と" if self.is_ja else " and "
        investors_str = sep.join(
            INVESTOR_PERSONAS[i]["name"] for i in accepted_offer["investors"]
        )

        if self.mode == "ai":
            prompt = f"""GENERATE ACCEPTANCE SPEECH
You are {self.config.get('founderName')}, founder of {self.config.get('startupName')}.
You have just accepted an offer from {investors_str}.
Deal: {accepted_offer['cash']} for {accepted_offer['equity']}% equity.
Terms: {accepted_offer['terms']}

Write a genuine, excited acceptance speech (under 40 words).
Name {investors_str} explicitly. Express what this partnership means for your startup.
No meta-text.
Language: {'Japanese' if self.is_ja else 'English'}"""
            text = self._strip_md(await self._run_founder_agent(prompt))
            if text:
                return text

        if self.is_ja:
            return (f"ありがとうございます、{investors_str}！喜んでお受けします。"
                    f"{self.config.get('startupName')}の未来のために一緒に頑張りましょう！")
        return (f"Thank you, {investors_str}! I'm thrilled to accept. "
                f"This is a huge moment for {self.config.get('startupName')} — "
                f"let's build something incredible together!")

    async def _evaluate_counter_offer(
        self, inv_id: str, counter_text: str, current_offer: dict
    ) -> dict:
        """
        The specific shark's ADK agent evaluates a counter-offer in character.
        Returns: accepted=True, OR counter_offer with revised terms, OR hard reject (both False/None).
        """
        name    = INVESTOR_PERSONAS[inv_id]["name"]
        persona = INVESTOR_PERSONAS[inv_id]
        prompt = f"""NEGOTIATE as {name}
You are {name}. Investment focus: {persona['focus']}.
You offered {current_offer['cash']} for {current_offer['equity']}% equity.
The founder countered: "{counter_text}"

Act in character based on your personality. Options:
- Accept if terms are reasonable
- Counter back with a revised offer (adjust equity ±3-8%, modify conditions)
- Hard reject if the counter is too far from your position (no deal)

Return ONLY valid JSON, no markdown fences:
{{
  "accepted": true or false,
  "speech": "<your response in your voice, 20-30 words>",
  "counter_offer": {{
    "cash": "<dollar amount e.g. $1.5M>",
    "equity": <integer percentage>,
    "terms": "<full deal conditions — include ALL financial structure: royalties, interest rate, milestone triggers, board seat, convertible note details, etc. Be specific and complete.>"
  }} or null
}}
Rules:
- If accepted=true: counter_offer must be null
- If counter_offer is set: accepted must be false
- Hard reject (too far apart): accepted=false AND counter_offer=null
Language: {'Japanese' if self.is_ja else 'English'}"""

        raw = await self._run_investor_agent(inv_id, prompt)
        fallback_speech = (
            "その条件では合意できません。" if self.is_ja
            else "Those terms don't work for me."
        )
        return self._parse_json(raw, {
            "accepted": False,
            "speech": fallback_speech,
            "counter_offer": None,
        })

    async def _generate_single_offer_terms(
        self, inv_id: str, conf: int,
        ask_amount: str, ask_equity: int, joint_partner: str = "",
    ) -> tuple[int, str]:
        """Ask the investor's ADK agent to propose their own equity % and deal terms."""
        name    = INVESTOR_PERSONAS[inv_id]["name"]
        focus   = INVESTOR_PERSONAS[inv_id]["focus"]
        startup = self.config.get("startupName", "the startup")
        sector  = self.config.get("sector", "tech")

        # Confidence tier hint — guides aggression without hardcoding numbers
        if conf >= 85:
            tier_hint = "You are very enthusiastic. Your terms should be fair and close to what the founder asked."
        elif conf >= 70:
            tier_hint = "You are interested but want a better deal. Negotiate for more equity, or add a royalty or other structure."
        else:
            tier_hint = "You are lukewarm. You need significantly better terms to justify the risk — push harder on equity or add protective structures."

        joint_note = (
            f"This is a joint offer with {joint_partner}. Structure the terms to reflect a combined investment."
            if joint_partner else ""
        )

        prompt = f"""GENERATE OFFER TERMS
You are {name}. Investment focus: {focus}.
Startup: {startup} ({sector})
Founder's ask: {ask_amount} for {ask_equity}% equity.
Your confidence: {conf}%.
{tier_hint}
{joint_note}

Decide your deal terms. Let your personality and focus area shape the structure.
You may propose: equity stake, royalty (as X% on net sales), loan/debt structure,
interest rate, milestone conditions, board seat — whatever fits your style.

EQUITY RULE (absolute): Your equity demand MUST be >= {ask_equity}% (the founder's ask). You are the investor — you always ask for equal or more equity than the founder offered. The investment amount stays {ask_amount}. Never go below {ask_equity}%.

Return ONLY valid JSON, no markdown fences:
{{
  "equity": <integer — your equity % demand, must be >= {ask_equity}>,
  "terms": "<full deal conditions in one sentence. If you use a royalty structure, write it as 'X% royalty on net sales until recouping N× my investment' — both the percentage AND the multiple must appear together. For any other structure: state interest rate % annually, milestone trigger, board seat, etc. Never omit the percentage when mentioning recoupment>"
}}
Language: {'Japanese' if self.is_ja else 'English'}"""

        await self._log(f"{name} Agent", f"Generating offer terms (confidence {conf}%)...", "info")
        raw    = await self._run_investor_agent(inv_id, prompt)
        result = self._parse_json(raw, {"equity": ask_equity, "terms": ""})

        raw_equity = result.get("equity", ask_equity)
        try:
            equity = int(float(str(raw_equity).replace("%", "").strip()))
        except (ValueError, TypeError):
            equity = ask_equity
        equity = max(ask_equity, min(49, equity))  # clamp: must be >= founder's ask, max 49%
        terms  = result.get("terms", "").strip()
        if not terms:
            terms = f"{ask_amount} for {equity}% equity." if not self.is_ja else f"{ask_amount}で株式{equity}%。"
        return equity, terms

    async def _build_offers(self, qualifying: list) -> list:
        """Build offer list — each shark's ADK agent decides their own terms."""
        offers      = []
        joint_taken = set()
        cfg         = self.config
        ask_amount  = cfg.get("askAmount", "$500K")
        ask_equity  = int(cfg.get("askEquity", 10))

        # Joint offer: two sharks with similar confidence levels are more likely to team up.
        # Probability scales with how close their scores are — nearly identical = ~60% chance,
        # far apart = ~10% chance. Any confidence level can qualify (not just mid-tier).
        best_pair, best_prob = None, 0.0
        for idx, a in enumerate(qualifying):
            for b in qualifying[idx + 1:]:
                conf_a = self.investor_states[a]["confidence"]
                conf_b = self.investor_states[b]["confidence"]
                diff   = abs(conf_a - conf_b)
                # Closer confidence → higher base probability (10%–60%)
                prob = max(0.10, 0.60 - diff * 0.02)
                if prob > best_prob:
                    best_prob, best_pair = prob, (a, b)

        eligible_joint = []
        if best_pair and random.random() < best_prob:
            eligible_joint = list(best_pair)

        if len(eligible_joint) >= 2:
            j0, j1  = eligible_joint[0], eligible_joint[1]
            joint_taken = {j0, j1}
            avg_conf = (self.investor_states[j0]["confidence"] + self.investor_states[j1]["confidence"]) // 2
            names    = f"{INVESTOR_PERSONAS[j0]['name']} & {INVESTOR_PERSONAS[j1]['name']}"
            equity, terms = await self._generate_single_offer_terms(
                j0, avg_conf, ask_amount, ask_equity,
                joint_partner=INVESTOR_PERSONAS[j1]["name"],
            )
            offers.append({
                "id":        f"joint_{random.randint(1000, 9999)}",
                "investors": [j0, j1],
                "cash":      ask_amount,
                "equity":    equity,
                "terms":     terms,
                "isJoint":   True,
                "revised":   False,
            })

        # Individual offers — all generated in parallel (one ADK call per investor)
        solo_investors = [i for i in qualifying if i not in joint_taken]
        if solo_investors:
            results = await asyncio.gather(
                *[self._generate_single_offer_terms(
                    inv_id,
                    self.investor_states[inv_id]["confidence"],
                    ask_amount, ask_equity,
                ) for inv_id in solo_investors],
                return_exceptions=True,
            )
            for inv_id, result in zip(solo_investors, results):
                if isinstance(result, Exception):
                    equity, terms = ask_equity, ""
                else:
                    equity, terms = result
                offers.append({
                    "id":        f"{inv_id}_{random.randint(1000, 9999)}",
                    "investors": [inv_id],
                    "cash":      ask_amount,
                    "equity":    equity,
                    "terms":     terms,
                    "isJoint":   False,
                    "revised":   False,
                })

        return offers

    # ─── Report generation ────────────────────────────────────────────────────

    async def _wait_for_speech_done(self):
        """Block until frontend signals TTS complete, with a 60 s safety timeout.
        Called after every founder_response emit so evaluation only starts once
        the investors have 'heard' the full answer."""
        try:
            await asyncio.wait_for(self._speech_done_q.get(), timeout=60.0)
        except asyncio.TimeoutError:
            await self._log(
                "Google ADK Orchestrator",
                "speech_done timeout (60 s) — proceeding with evaluation.",
                "warning",
            )

    async def _generate_report(self, deal: dict | None):
        # Guard: only generate a report once the simulation is truly finished.
        if self._sim_phase == "ONGOING":
            await self._log(
                "Google ADK Orchestrator",
                "Report generation blocked — simulation still ONGOING.",
                "warning",
            )
            return

        self._sim_phase = "DONE"
        await self._emit("phase_change", {"phase": "DONE"})

        await self._log(
            "Google ADK Orchestrator",
            "Generating investment memo — collecting all four investor perspectives in parallel...",
            "info",
        )

        history_str      = self._history_str(last=15)
        investor_summary = "; ".join(
            f"{INVESTOR_PERSONAS[i]['name']}: status={self.investor_states[i]['status']}, "
            f"confidence={self.investor_states[i]['confidence']}%"
            for i in INVESTOR_IDS
        )

        # ── Step 1: Parallel per-investor feedback (all 4 agents) ────────────
        feedback_tasks = [
            self._generate_investor_feedback(inv_id, history_str, investor_summary)
            for inv_id in INVESTOR_IDS
        ]
        feedbacks_raw  = await asyncio.gather(*feedback_tasks, return_exceptions=True)
        feedbacks_list = [
            f if isinstance(f, dict) else {"pros": "N/A", "cons": "N/A", "recommendation": "N/A"}
            for f in feedbacks_raw
        ]
        detailed_feedback = dict(zip(INVESTOR_IDS, feedbacks_list))

        await self._log(
            "Google ADK Orchestrator",
            "Investor feedback collected. Synthesising final memo...",
            "info",
        )

        # ── Step 3: Synthesis — all 4 perspectives → narrative fields ──────────
        if deal:
            deal_investors = ", ".join(
                INVESTOR_PERSONAS[i]["name"] for i in deal.get("investors", []) if i in INVESTOR_PERSONAS
            )
            deal_context = (
                f"DEAL CLOSED: {deal_investors} invested {deal.get('cash')} "
                f"for {deal.get('equity')}% equity. "
                f"Full terms: {deal.get('terms', 'standard equity deal')}"
            )
        else:
            deal_context = "NO DEAL: Founder walked away or all offers were rejected."

        # Format each investor's feedback for the synthesis prompt
        feedback_lines = "\n".join(
            f"{INVESTOR_PERSONAS[inv_id]['name']} ({INVESTOR_PERSONAS[inv_id]['focus']}):\n"
            f"  Pros: {fb.get('pros', 'N/A')}\n"
            f"  Cons: {fb.get('cons', 'N/A')}\n"
            f"  Recommendation: {fb.get('recommendation', 'N/A')}"
            for inv_id, fb in detailed_feedback.items()
        )

        synthesis_prompt = f"""SYNTHESISE INVESTMENT MEMO
You are a neutral senior analyst compiling a final VC investment memo from four independent investor perspectives.

Startup: {self.config.get('startupName')} ({self.config.get('sector')})
Founder: {self.config.get('founderName')}
Ask: {self.config.get('askAmount')} for {self.config.get('askEquity')}%
Deal outcome: {deal_context}

Four investor verdicts:
{feedback_lines}

Based on ALL four perspectives above, produce a balanced memo that reflects the panel's collective view.
Do NOT favour any single investor's angle. Identify patterns: what multiple sharks agreed on as strengths,
what multiple sharks flagged as risks, and what the roadmap should look like given the panel's combined expertise.

Return ONLY valid JSON, no markdown fences:
{{
  "verdict": "<Angel|Accelerator|Seed|Series A|Institutional VC|Rejected>",
  "executiveSummary": "<2-3 sentence synthesis of the panel's collective view>",
  "risks": [{{"flag": "<risk agreed on by multiple investors>", "weight": "<High|Medium|Low>"}}],
  "strengths": ["<strength multiple investors highlighted>"],
  "roadmap": ["1. <step>", "2. <step>", "3. <step>"]
}}
Language: {'Japanese' if self.is_ja else 'English'}"""

        raw    = await self._run_founder_agent(synthesis_prompt)
        report = self._parse_json(raw, {
            "verdict":          "Seed",
            "executiveSummary": "Simulation concluded.",
            "risks":            [{"flag": "Market risk", "weight": "Medium"}],
            "strengths":        ["Clear vision"],
            "roadmap":          ["1. Build MVP", "2. Find customers"],
        })

        # Average readiness scores — each agent rates 1-10 from their own lens
        raw_scores = [
            fb["readinessScore"] for fb in feedbacks_list
            if isinstance(fb.get("readinessScore"), (int, float))
        ]
        if raw_scores:
            report["readinessScore"] = max(1, min(10, round(sum(raw_scores) / len(raw_scores))))
        # If no agent returned a score, leave it absent — the frontend shows N/A

        report["detailedSharkFeedback"] = detailed_feedback

        # ── Attach agreed term sheet ───────────────────────────────────────────
        if deal:
            report["agreedTermSheet"] = deal
        else:
            invested = [i for i in INVESTOR_IDS if self.investor_states[i]["status"] == "INVEST"]
            if invested:
                report["agreedTermSheet"] = {
                    "id":        "auto_deal",
                    "investors": invested,
                    "cash":      self.config.get("askAmount"),
                    "equity":    int(self.config.get("askEquity", 10)),
                    "terms":     "",
                    "isJoint":   len(invested) > 1,
                }
            else:
                report["agreedTermSheet"] = None

        await self._log("Google ADK Orchestrator", "Investment memo complete. Simulation finished.", "success")
        await self._emit("report", {"data": report})

    async def _generate_investor_feedback(
        self, inv_id: str, history_str: str, investor_summary: str
    ) -> dict:
        """Generate pros/cons/recommendation + readiness score from one investor (run in parallel)."""
        state  = self.investor_states[inv_id]
        name   = INVESTOR_PERSONAS[inv_id]["name"]
        focus  = INVESTOR_PERSONAS[inv_id]["focus"]
        prompt = f"""GENERATE REPORT FEEDBACK
You are {name}. Your investment focus: {focus}.
Provide your final verdict on this startup from YOUR specific angle.

Startup: {self.config.get('startupName')} ({self.config.get('sector')})
Your final confidence: {state['confidence']}%
Your status: {state['status']}
All investors: {investor_summary}

Conversation excerpt:
{history_str}

Rate this startup's investor-readiness from YOUR lens only. You MUST give a score — never omit it.
readinessScore MUST be a whole integer between 1 and 10, nothing else:
  1-3  Not ready. Fundamental gaps in your focus area.
  4-6  Shows promise but significant work needed.
  7-8  Strong. Ready with minor gaps.
  9-10 Exceptional. You would write the cheque today.

Return ONLY valid JSON, no markdown fences:
{{
  "readinessScore": <REQUIRED integer 1-10>,
  "pros": "<what impressed you, from your {focus} perspective>",
  "cons": "<what concerned you, from your {focus} perspective>",
  "recommendation": "<your final recommendation in 1-2 sentences>"
}}
Language: {'Japanese' if self.is_ja else 'English'}"""

        raw    = await self._run_investor_agent(inv_id, prompt)
        result = self._parse_json(raw, {
            "pros":           "N/A",
            "cons":           "N/A",
            "recommendation": "N/A",
        })
        # Clamp score to 1-10 integer; if model returned e.g. 75 treat as 7
        s = result.get("readinessScore")
        if isinstance(s, (int, float)):
            s = int(s)
            if s > 10:
                s = round(s / 10)
            result["readinessScore"] = max(1, min(10, s))
        return result

    # ─── ADK agent execution helpers ─────────────────────────────────────────

    async def _run_investor_agent(self, inv_id: str, prompt: str) -> str:
        async with self._investor_locks[inv_id]:
            runner  = self._investor_runners[inv_id]
            session = self._investor_sessions[inv_id]
            name    = INVESTOR_PERSONAS[inv_id]["name"]
            try:
                return await asyncio.wait_for(
                    self._run_agent(runner, f"{inv_id}_user", session.id, prompt),
                    timeout=45.0,
                )
            except asyncio.TimeoutError:
                await self._log(name, "ADK call timed out (45 s) — skipping turn.", "warning")
                return ""
            except Exception as exc:
                await self._log(name, f"ADK call failed ({exc.__class__.__name__}) — skipping turn.", "warning")
                return ""

    async def _run_founder_agent(self, prompt: str) -> str:
        try:
            return await asyncio.wait_for(
                self._run_agent(
                    self._founder_runner,
                    "founder_user",
                    self._founder_session.id,
                    prompt,
                ),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            await self._log("Founder Agent", "ADK call timed out (45 s) — skipping turn.", "warning")
            return ""
        except Exception as exc:
            await self._log("Founder Agent", f"ADK call failed ({exc.__class__.__name__}) — skipping turn.", "warning")
            return ""

    @staticmethod
    async def _run_agent(runner, user_id: str, session_id: str, prompt: str) -> str:
        """Execute one ADK agent turn and return the final text response."""
        content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=prompt)],
        )
        text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    text = event.content.parts[0].text or ""
        return text

    # ─── Event / state helpers ────────────────────────────────────────────────

    async def _emit(self, event_type: str, payload: dict):
        await self._q.put({"type": event_type, **payload})

    async def _log(self, agent_name: str, message: str, log_type: str = "info"):
        await self._emit("agent_log", {
            "agentName": agent_name,
            "message":   message,
            "logType":   log_type,
        })

    async def _emit_investor_update(self, inv_id: str):
        s = self.investor_states[inv_id]
        await self._emit("investor_update", {
            "investorId":    inv_id,
            "confidence":    s["confidence"],
            "trend":         s["trend"],
            "status":        s["status"],
            "thoughtBubble": s["thoughtBubble"],
            "strengths":     s["strengths"],
            "weaknesses":    s["weaknesses"],
            "risks":         s["risks"],
            "agentState":    s["agentState"],
            "isThinking":    s["isThinking"],
        })

    async def _emit_all_investor_updates(self):
        for inv_id in INVESTOR_IDS:
            await self._emit_investor_update(inv_id)

    async def _set_founder_agent_state(self, state: str):
        self._founder_agent_state = state
        await self._emit("founder_agent_state", {"state": state})

    def _add_to_history(self, sender: str, text: str, is_banter: bool = False):
        name_map = {
            **{i: INVESTOR_PERSONAS[i]["name"] for i in INVESTOR_IDS},
            "founder": self.config.get("founderName", "Founder"),
            "system":  "System",
        }
        entry: dict = {
            "sender":     sender,
            "senderName": name_map.get(sender, sender),
            "text":       text,
        }
        if is_banter:
            entry["isBanter"] = True
        self.chat_history.append(entry)

    def _history_str(self, last: int = 10) -> str:
        return "\n".join(
            f"{m['senderName']}: {m['text']}"
            for m in self.chat_history[-last:]
        )

    async def _generate_exit_speech(self, inv_id: str) -> str:
        """
        Each departing investor generates their own exit speech via their ADK agent.
        The speech is grounded in the actual conversation — specific concerns they raised,
        exact things the founder said — making every departure unique and contextual.
        Falls back to a generic line if the ADK call fails.
        """
        state       = self.investor_states[inv_id]
        name        = INVESTOR_PERSONAS[inv_id]["name"]
        history_str = self._history_str(last=8)

        # Surface the specific weaknesses this investor accumulated
        concerns = "; ".join(state["weaknesses"][-3:]) if state["weaknesses"] else "multiple unresolved concerns"

        prompt = f"""GENERATE EXIT SPEECH
You are {name}, and you have decided to drop out of this investment deal.
Your final confidence fell to {state['confidence']}% — below your minimum threshold.
Your specific concerns about this startup: {concerns}

Recent conversation that led to your decision:
{history_str}

Write a brief, sharp exit speech (under 35 words) that:
1. Directly references 1-2 specific things from the conversation above that killed your confidence
2. States your exit clearly (end with a phrase like "I'm out" or the equivalent)
3. Sounds like YOUR voice — {INVESTOR_PERSONAS[inv_id]['focus']}

No meta-text. No formatting. Just the speech.
Language: {'Japanese' if self.is_ja else 'English'}"""

        await self._log(f"{name} Agent", "Generating contextual exit speech...", "warning")
        text = await self._run_investor_agent(inv_id, prompt)
        text = self._strip_md(text)

        # Fallback if response is empty or too long
        if not text or len(text) > 300:
            fallbacks = {
                "en": {
                    "vincent":  "The numbers don't work for me. For that reason, I'm out.",
                    "marcus":   "I can't get comfortable with the tech risk here. I'm out.",
                    "beatrice": "I don't believe in this enough to write a check. I'm out.",
                    "leona":    "The go-to-market isn't there yet. I'm out.",
                },
                "ja": {
                    "vincent":  "この数字では投資できません。今回は見送ります。",
                    "marcus":   "技術リスクが高すぎます。今回は見送ります。",
                    "beatrice": "十分な確信が持てません。今回は見送ります。",
                    "leona":    "市場開拓の準備がまだできていません。今回は見送ります。",
                },
            }
            lang = "ja" if self.is_ja else "en"
            text = fallbacks[lang][inv_id]

        return text

    @staticmethod
    def _strip_md(text: str) -> str:
        """Remove markdown formatting characters that TTS would read literally."""
        import re
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'_(.*?)_', r'\1', text)
        text = re.sub(r'`([^`]*)`', r'\1', text)
        text = re.sub(r'[*_`#~]', '', text)
        return text.strip()

    @staticmethod
    def _parse_json(raw: str, fallback: dict) -> dict:
        try:
            text = raw.strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                parts = text.split("```")
                text  = parts[1] if len(parts) > 1 else text
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception:
            return fallback
