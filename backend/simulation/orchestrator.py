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
    build_session_service,
)

APP_NAME = "shark_tank"

# Confidence thresholds (mirror the frontend constants)
CONFIDENCE_OUT    = 25
CONFIDENCE_INVEST = 85


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

        # Build ADK agents & runners (each investor gets its own session)
        self._session_svc      = build_session_service()
        self._investor_agents  = build_investor_agents(self.model)
        self._founder_agent    = build_founder_agent(self.model)
        self._investor_runners, self._founder_runner = build_runners(
            self._investor_agents, self._founder_agent, self._session_svc, APP_NAME
        )

        # Per-investor simulation state (not in ADK session — kept here for clarity)
        self.investor_states: dict = {
            inv_id: {
                "confidence":    50,
                "status":        "ACTIVE",
                "questionsAsked": 0,
                "strengths":     [],
                "weaknesses":    [],
                "risks":         [],
                "trend":         0,
                "thoughtBubble": "",
                "agentState":    "IDLE",
                "isThinking":    False,
            }
            for inv_id in INVESTOR_IDS
        }

        # Shared conversation history (what's been said, by whom)
        self.chat_history: list[dict] = []

        # Queues for inter-coroutine communication
        self._q:                asyncio.Queue  = asyncio.Queue()   # events → WS
        self._founder_response: asyncio.Queue  = asyncio.Queue()   # REAL mode: typed text
        self._bargain_action:   asyncio.Queue  = asyncio.Queue()   # accept/counter/walk-away

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

            for inv_id in active:
                if self.investor_states[inv_id]["status"] != "ACTIVE":
                    continue

                # Investor asks a question
                question = await self._generate_question(inv_id)
                self._add_to_history(inv_id, question)
                await self._emit("question", {
                    "sender":          inv_id,
                    "senderName":      INVESTOR_PERSONAS[inv_id]["name"],
                    "text":            question,
                    "waitForResponse": self.mode == "real",
                })

                # Founder responds
                if self.mode == "ai":
                    response = await self._generate_founder_response(question, inv_id)
                else:
                    response = await self._founder_response.get()

                self._add_to_history("founder", response)
                await self._emit("founder_response", {
                    "sender":     "founder",
                    "senderName": self.config.get("founderName", "Founder"),
                    "text":       response,
                })

                # All active investors evaluate in parallel
                await self._parallel_evaluate(response)

                # Banter (25 % chance, only references speakers already in history)
                await self._maybe_banter()

                self.investor_states[inv_id]["questionsAsked"] += 1

        await self._phase_bargaining()

    async def receive_founder_response(self, text: str):
        """Called by the WS handler when the user submits their answer (REAL mode)."""
        await self._founder_response.put(text)

    async def receive_bargain_action(self, action: dict):
        """Called by the WS handler when the user accepts / counters / walks away."""
        await self._bargain_action.put(action)

    @property
    def event_queue(self) -> asyncio.Queue:
        return self._q

    # ─── Session initialisation ───────────────────────────────────────────────

    async def _init_sessions(self):
        for inv_id in INVESTOR_IDS:
            session = await self._session_svc.create_session(
                app_name=APP_NAME,
                user_id=f"{inv_id}_user",
            )
            self._investor_sessions[inv_id] = session

        self._founder_session = await self._session_svc.create_session(
            app_name=APP_NAME,
            user_id="founder_user",
        )

    # ─── Pitch phase ──────────────────────────────────────────────────────────

    async def _phase_pitch(self):
        await self._log("Founder Agent", "Generating opening pitch via Google ADK...", "info")

        await self._set_founder_agent_state("PITCHING")

        if self.mode == "ai":
            pitch = await self._run_founder_agent(
                f"""GENERATE PITCH
Startup: {self.config.get('startupName')} ({self.config.get('sector')})
Founder: {self.config.get('founderName')}
Description: {self.config.get('description')}
Ask: {self.config.get('askAmount')} for {self.config.get('askEquity')}% equity
Personality: {self.config.get('personality', 'excellent')}
Language: {'Japanese' if self.is_ja else 'English'}"""
            )
        else:
            cfg = self.config
            if self.is_ja:
                pitch = (f"こんにちは投資家の皆さん。私は{cfg.get('founderName')}です。"
                         f"本日は{cfg.get('startupName')}のピッチを行います。"
                         f"{cfg.get('description')}。"
                         f"希望条件は{cfg.get('askAmount')}、株式{cfg.get('askEquity')}%です。")
            else:
                pitch = (f"Hello Sharks! I am {cfg.get('founderName')}, "
                         f"founder of {cfg.get('startupName')}. "
                         f"We are pitching {cfg.get('description')}. "
                         f"We are seeking {cfg.get('askAmount')} for {cfg.get('askEquity')}% equity.")

        self._add_to_history("founder", pitch)
        await self._set_founder_agent_state("IDLE")

        await self._log("Founder Agent", "Pitch delivered to the panel.", "success")
        await self._emit("pitch", {
            "sender":     "founder",
            "senderName": self.config.get("founderName", "Founder"),
            "text":       pitch,
        })

    # ─── Question generation ──────────────────────────────────────────────────

    async def _generate_question(self, inv_id: str) -> str:
        name = INVESTOR_PERSONAS[inv_id]["name"]
        await self._log(f"{name} Agent", "Formulating strategic question via ADK...", "info")

        self.investor_states[inv_id]["agentState"] = "ASKING"
        await self._emit_investor_update(inv_id)

        history_str = self._history_str(last=10)
        prompt = f"""GENERATE QUESTION
Startup: {self.config.get('startupName')} ({self.config.get('sector')})
Ask: {self.config.get('askAmount')} for {self.config.get('askEquity')}%
Description: {self.config.get('description')}

Recent conversation:
{history_str}

One sharp question targeting your focus area. Max 40 words. No meta-text.
Language: {'Japanese' if self.is_ja else 'English'}"""

        text = await self._run_investor_agent(inv_id, prompt)
        self.investor_states[inv_id]["agentState"] = "IDLE"
        await self._emit_investor_update(inv_id)
        return text.strip()

    # ─── Founder response ─────────────────────────────────────────────────────

    async def _generate_founder_response(self, question: str, questioner_id: str) -> str:
        await self._log("Founder Agent", "Generating response via ADK...", "info")
        await self._set_founder_agent_state("PITCHING")

        history_str = self._history_str(last=8)
        prompt = f"""GENERATE RESPONSE
You are: {self.config.get('founderName')}, founder of {self.config.get('startupName')}
Personality: {self.config.get('personality', 'excellent')}
Question from {INVESTOR_PERSONAS[questioner_id]['name']}: "{question}"

Conversation so far:
{history_str}

Reply in character matching your personality. Under 60 words. No meta-text.
Language: {'Japanese' if self.is_ja else 'English'}"""

        text = await self._run_founder_agent(prompt)
        await self._set_founder_agent_state("IDLE")
        return text.strip()

    # ─── Parallel evaluation (core multi-agent feature) ───────────────────────

    async def _parallel_evaluate(self, founder_response: str):
        """
        All active investor agents evaluate the founder's response simultaneously.
        This is the true multi-agent parallelism: 4 independent ADK agents,
        each with their own session, running concurrently via asyncio.gather().
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
        tasks   = [self._evaluate_single_investor(inv_id, founder_response) for inv_id in active]
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
            elif new_conf >= CONFIDENCE_INVEST:
                state["status"]     = "INVEST"
                state["agentState"] = "INVESTED"
            else:
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
            exit_texts = await asyncio.gather(*exit_tasks)

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

    async def _evaluate_single_investor(self, inv_id: str, founder_response: str) -> dict:
        """One investor agent evaluates — this runs in parallel with the other 3."""
        state       = self.investor_states[inv_id]
        history_str = self._history_str(last=10)

        prompt = f"""EVALUATE RESPONSE
You are evaluating as {INVESTOR_PERSONAS[inv_id]['name']}.

Founder said: "{founder_response}"
Startup: {self.config.get('startupName')} ({self.config.get('sector')})
Ask: {self.config.get('askAmount')} for {self.config.get('askEquity')}%
Your current confidence: {state['confidence']}%
Round: {state['questionsAsked'] + 1} of {self.rounds}

Conversation history:
{history_str}

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
        return self._parse_json(raw, {
            "confidence":    state["confidence"],
            "thoughtBubble": "Processing...",
            "strengths":     [],
            "weaknesses":    [],
            "risks":         [],
        })

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

        prompt = f"""GENERATE BANTER
You are {INVESTOR_PERSONAS[speaker]['name']} reacting spontaneously to the pitch.

CRITICAL: You may ONLY reference investors who have already spoken.
Investors you may reference: {referenceable}
Do NOT mention any other investor by name.

Recent conversation:
{history_str}

One punchy comment (under 25 words). No quotes, no meta-text.
Language: {'Japanese' if self.is_ja else 'English'}"""

        await self._log(
            f"{INVESTOR_PERSONAS[speaker]['name']} Agent",
            "Generating spontaneous banter...",
            "warning",
        )
        text = await self._run_investor_agent(speaker, prompt)
        text = text.strip().strip('"').strip("'")
        if not text:
            return

        self.investor_states[speaker]["agentState"] = "BANTERING"
        await self._emit_investor_update(speaker)
        self._add_to_history(speaker, text)
        await self._emit("banter", {
            "sender":     speaker,
            "senderName": INVESTOR_PERSONAS[speaker]["name"],
            "text":       text,
        })
        self.investor_states[speaker]["agentState"] = "IDLE"
        await self._emit_investor_update(speaker)

    # ─── Bargaining phase ─────────────────────────────────────────────────────

    async def _phase_bargaining(self):
        qualifying = [
            i for i in INVESTOR_IDS
            if self.investor_states[i]["confidence"] >= 26
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

        offers = self._build_offers(qualifying)

        # Present each offer with speech
        for offer in offers:
            rep_id   = offer["investors"][0]
            rep_name = INVESTOR_PERSONAS[rep_id]["name"]
            if self.is_ja:
                offer_speech = f"私は{offer['cash']}を株式{offer['equity']}%でオファーします。条件：{offer['terms']}"
            else:
                offer_speech = f"I am offering {offer['cash']} for {offer['equity']}% equity. Terms: {offer['terms']}"

            self._add_to_history(rep_id, offer_speech)
            await self._log(
                f"{rep_name} Agent",
                f"Presenting offer: {offer['cash']} for {offer['equity']}%",
                "success",
            )
            await self._emit("offer_speech", {
                "sender":     rep_id,
                "senderName": rep_name,
                "text":       offer_speech,
                "offer":      offer,
            })

        await self._emit("bargaining_start", {"offers": offers})

        # Wait for the frontend to send an action
        action = await self._bargain_action.get()
        action_type = action.get("type")

        if action_type == "accept":
            offer_id     = action.get("offerId")
            accepted     = next((o for o in offers if o["id"] == offer_id), offers[0])
            rep_name     = INVESTOR_PERSONAS[accepted["investors"][0]]["name"]
            success_text = (
                f"素晴らしい！{rep_name}と{accepted['cash']}（株式{accepted['equity']}%）で合意しました！"
                if self.is_ja else
                f"Fantastic! Deal sealed with {rep_name} for {accepted['cash']} at {accepted['equity']}% equity!"
            )
            await self._emit("system_message", {"text": success_text})
            await self._generate_report(deal=accepted)

        elif action_type == "counter":
            counter_text = action.get("text", "")
            founder_counter = f"{'カウンターオファー' if self.is_ja else 'Counter-offer'}: {counter_text}"
            self._add_to_history("founder", founder_counter)
            await self._emit("founder_response", {
                "sender":     "founder",
                "senderName": self.config.get("founderName", "Founder"),
                "text":       founder_counter,
            })
            # 50 % chance investors accept
            if random.random() < 0.5 and offers:
                accepted = offers[0]
                accept_text = (
                    "カウンターオファーが承認されました！" if self.is_ja
                    else "Counter-offer accepted! Congratulations!"
                )
                await self._emit("system_message", {"text": accept_text})
                await self._generate_report(deal=accepted)
            else:
                reject_text = (
                    "残念ながら、その条件では合意できません。" if self.is_ja
                    else "Unfortunately we cannot agree to those terms."
                )
                await self._emit("system_message", {"text": reject_text})
                await self._generate_report(deal=None)

        else:  # walk_away
            cfg = self.config
            walk_text = (
                "起業家はすべてのオファーを辞退し、手ぶらで立ち去りました。"
                if self.is_ja else
                "The entrepreneur declined all offers and walked away empty-handed."
            )
            await self._emit("system_message", {"text": walk_text})
            snark = (
                "君はただのマネー・インシネレーターだ。泣きながら家に帰るんだね。"
                if self.is_ja else
                "You are just a cash incinerator. Go home and cry to your mother."
            )
            self._add_to_history("vincent", snark)
            await self._emit("banter", {
                "sender":     "vincent",
                "senderName": INVESTOR_PERSONAS["vincent"]["name"],
                "text":       snark,
            })
            await self._generate_report(deal=None)

    def _build_offers(self, qualifying: list) -> list:
        offers       = []
        joint_taken  = set()
        cfg          = self.config

        # Optional joint offer between two high-confidence investors
        eligible_joint = [
            i for i in qualifying
            if 75 <= self.investor_states[i]["confidence"] <= 90
        ]
        if len(eligible_joint) >= 2 and random.random() < 0.3:
            j0, j1       = eligible_joint[0], eligible_joint[1]
            joint_taken  = {j0, j1}
            names        = f"{INVESTOR_PERSONAS[j0]['name']} & {INVESTOR_PERSONAS[j1]['name']}"
            offers.append({
                "id":        f"joint_{random.randint(1000, 9999)}",
                "investors": [j0, j1],
                "cash":      cfg.get("askAmount"),
                "equity":    round(int(cfg.get("askEquity", 10)) * 1.5),
                "terms":     (f"{names}による共同投資。両者のネットワークをフル活用。"
                              if self.is_ja else
                              f"Joint investment by {names}. Full access to both networks."),
                "isJoint":   True,
            })

        for inv_id in qualifying:
            if inv_id in joint_taken:
                continue
            conf = self.investor_states[inv_id]["confidence"]
            ask_equity = int(cfg.get("askEquity", 10))

            if conf >= 85:
                equity = ask_equity
                terms  = ("希望通りの条件で投資します。" if self.is_ja
                          else "Offering the exact terms requested.")
            elif conf >= 70:
                equity = round(ask_equity * 1.2)
                terms  = (f"株式{equity}%とロイヤリティ付きで投資します。" if self.is_ja
                          else f"Offering {cfg.get('askAmount')} for {equity}% plus royalty until I recoup 120%.")
            else:
                equity = min(49, round(ask_equity * 2.5))
                terms  = (f"バリュエーションが高すぎます。株式{equity}%を要求します。" if self.is_ja
                          else f"Your valuation is unacceptable. Demanding {equity}% equity.")

            offers.append({
                "id":        f"{inv_id}_{random.randint(1000, 9999)}",
                "investors": [inv_id],
                "cash":      cfg.get("askAmount"),
                "equity":    equity,
                "terms":     terms,
                "isJoint":   False,
            })

        return offers

    # ─── Report generation ────────────────────────────────────────────────────

    async def _generate_report(self, deal: dict | None):
        await self._log(
            "Google ADK Orchestrator",
            "Generating final evaluation report — querying all 4 investor agents...",
            "info",
        )

        history_str      = self._history_str(last=15)
        investor_summary = "; ".join(
            f"{INVESTOR_PERSONAS[i]['name']}: status={self.investor_states[i]['status']}, "
            f"confidence={self.investor_states[i]['confidence']}%"
            for i in INVESTOR_IDS
        )

        # Run feedback generation for all 4 investor agents in parallel
        feedback_tasks = [
            self._generate_investor_feedback(inv_id, history_str, investor_summary)
            for inv_id in INVESTOR_IDS
        ]
        feedbacks_list  = await asyncio.gather(*feedback_tasks)
        detailed_feedback = dict(zip(INVESTOR_IDS, feedbacks_list))

        # Generate overall report using Vincent (financial expert) as lead analyst
        report_prompt = f"""GENERATE REPORT FEEDBACK
You are acting as a senior VC analyst, compiling a final investment memo.

Startup: {self.config.get('startupName')} ({self.config.get('sector')})
Founder: {self.config.get('founderName')}
Ask: {self.config.get('askAmount')} for {self.config.get('askEquity')}%
Investor outcomes: {investor_summary}

Recent conversation:
{history_str}

Return ONLY valid JSON, no markdown fences:
{{
  "readinessScore": <integer 1-10>,
  "verdict": "<Angel|Accelerator|Seed|Series A|Institutional VC|Rejected>",
  "executiveSummary": "<2-3 sentence summary>",
  "risks": [{{"flag": "<risk>", "weight": "<High|Medium|Low>"}}],
  "strengths": ["<strength>"],
  "roadmap": ["1. <step>", "2. <step>"]
}}
Language: {'Japanese' if self.is_ja else 'English'}"""

        raw   = await self._run_investor_agent("vincent", report_prompt)
        report = self._parse_json(raw, {
            "readinessScore":  5,
            "verdict":         "Seed",
            "executiveSummary": "Simulation concluded.",
            "risks":           [{"flag": "Market risk", "weight": "Medium"}],
            "strengths":       ["Clear vision"],
            "roadmap":         ["1. Build MVP", "2. Find customers"],
        })

        # Clamp readiness score
        score = report.get("readinessScore", 5)
        if score > 10:
            score = round(score / 10)
        report["readinessScore"] = max(1, min(10, int(score)))

        report["detailedSharkFeedback"] = detailed_feedback

        # Attach agreed term sheet
        if deal:
            report["agreedTermSheet"] = deal
        else:
            invested = [i for i in INVESTOR_IDS if self.investor_states[i]["status"] == "INVEST"]
            if invested:
                report["agreedTermSheet"] = {
                    "id":        "auto_deal",
                    "investors": invested,
                    "cash":      self.config.get("askAmount"),
                    "equity":    int(self.config.get("askEquity", 10)) + 5,
                    "terms":     ("マイルストーン達成を条件とする。" if self.is_ja
                                  else "Subject to milestone reviews."),
                    "isJoint":   len(invested) > 1,
                }
            else:
                report["agreedTermSheet"] = None

        await self._log("Google ADK Orchestrator", "Report generated. Simulation complete.", "success")
        await self._emit("report", {"data": report})

    async def _generate_investor_feedback(
        self, inv_id: str, history_str: str, investor_summary: str
    ) -> dict:
        """Generate pros/cons/recommendation from one investor (run in parallel)."""
        state = self.investor_states[inv_id]
        prompt = f"""GENERATE REPORT FEEDBACK
You are {INVESTOR_PERSONAS[inv_id]['name']} providing your final verdict.

Startup: {self.config.get('startupName')} ({self.config.get('sector')})
Your final confidence: {state['confidence']}%
Your status: {state['status']}

Conversation excerpt:
{history_str}

Return ONLY valid JSON, no markdown fences:
{{
  "pros": "<what impressed you>",
  "cons": "<what concerned you>",
  "recommendation": "<your final recommendation>"
}}
Language: {'Japanese' if self.is_ja else 'English'}"""

        raw = await self._run_investor_agent(inv_id, prompt)
        return self._parse_json(raw, {
            "pros":           "N/A",
            "cons":           "N/A",
            "recommendation": "N/A",
        })

    # ─── ADK agent execution helpers ─────────────────────────────────────────

    async def _run_investor_agent(self, inv_id: str, prompt: str) -> str:
        runner  = self._investor_runners[inv_id]
        session = self._investor_sessions[inv_id]
        return await self._run_agent(runner, f"{inv_id}_user", session.id, prompt)

    async def _run_founder_agent(self, prompt: str) -> str:
        return await self._run_agent(
            self._founder_runner,
            "founder_user",
            self._founder_session.id,
            prompt,
        )

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

    def _add_to_history(self, sender: str, text: str):
        name_map = {
            **{i: INVESTOR_PERSONAS[i]["name"] for i in INVESTOR_IDS},
            "founder": self.config.get("founderName", "Founder"),
            "system":  "System",
        }
        self.chat_history.append({
            "sender":     sender,
            "senderName": name_map.get(sender, sender),
            "text":       text,
        })

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
        text = text.strip()

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
