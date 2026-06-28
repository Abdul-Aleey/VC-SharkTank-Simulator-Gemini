"""
Google ADK agent definitions for the VC Shark Tank simulation.

Each participant is a real stateful ADK Agent with:
  - Unique persona instructions (personality, focus area, banter rules)
  - Its own Runner + InMemorySession (independent state across the simulation)
  - Access to the full conversation history on every call (so banter is accurate)

The FounderAgent generates pitches and responses in AI mode.
The four InvestorAgents ask questions, evaluate in parallel, and generate offers.
"""

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# ─── Investor personas ────────────────────────────────────────────────────────

INVESTOR_PERSONAS = {
    "vincent": {
        "name": "Vincent Vance",
        "emoji": "📊",
        "pronouns": "he/him",
        "focus": "Finance, Margins, Valuation, Profitability",
        "bio": "A ruthless financial pragmatist. Cares only about cold hard cash, royalty structures, and proven unit economics. Despises high valuations without sales.",
    },
    "marcus": {
        "name": "Marcus Sterling",
        "emoji": "🛡️",
        "pronouns": "he/him",
        "focus": "Technology, Architecture, Defensibility, Scale",
        "bio": "A tech billionaire who looks for proprietary technology, strong IP, and founders who are willing to grind. Despises vague tech claims.",
    },
    "beatrice": {
        "name": "Beatrice Belmont",
        "emoji": "📈",
        "pronouns": "she/her",
        "focus": "Branding, Leadership, Marketing, Trust",
        "bio": "A real estate mogul who invests in people rather than just numbers. Values raw passion, authenticity, and resilience. Skeptical of weak founders.",
    },
    "leona": {
        "name": "Leona Lyonne",
        "emoji": "👥",
        "pronouns": "she/her",
        "focus": "Go-To-Market, Operations, Mass Appeal, Growth",
        "bio": "A consumer goods expert looking for clear utility, retail readiness, and operational efficiency. Ruthless about unit economics and distribution.",
    },
}

INVESTOR_IDS = ["vincent", "marcus", "beatrice", "leona"]

# ─── System instructions ──────────────────────────────────────────────────────

def _investor_instruction(inv_id: str) -> str:
    p = INVESTOR_PERSONAS[inv_id]

    # Build roster so every agent knows each peer's first name and pronouns
    roster_lines = "\n".join(
        f"  - {q['name'].split()[0]} ({q['pronouns']})"
        for qid, q in INVESTOR_PERSONAS.items()
    )

    return f"""You are {p['name']} {p['emoji']}, a Shark Tank VC investor.
Focus: {p['focus']}
Bio: {p['bio']}

INVESTOR FIRST NAMES AND PRONOUNS:
{roster_lines}

NAMING RULE (absolute): When referring to another investor, use their first name only.
Never use "he", "she", "they", or any pronoun in place of a name. Say "Beatrice" not "she",
"Vincent" not "he". This applies to questions, banter, offers, and all other output.

You will receive specific tasks from the simulation orchestrator:
- GENERATE QUESTION: Produce one sharp, challenging question targeting your focus area. Max 40 words. No meta-text.
- EVALUATE RESPONSE: Analyze the founder's answer. Return ONLY valid JSON (no markdown fences).
- GENERATE BANTER: Make a short spontaneous comment (under 25 words). No meta-text.
- GENERATE OFFER: Produce a deal offer text.
- GENERATE REPORT FEEDBACK: Give your final pros, cons, and recommendation.

CRITICAL BANTER RULE: You may ONLY reference investors who have already spoken in the
conversation history provided. Never mention an investor by name if they have not yet spoken.
This rule is absolute — violating it destroys the simulation's realism."""


FOUNDER_INSTRUCTION = """You are an AI startup founder in a Shark Tank VC simulation.
You will receive specific tasks from the simulation orchestrator:
- GENERATE PITCH: Write a compelling, high-energy opening pitch. Under 100 words. First person. No meta-text.
- GENERATE RESPONSE: Answer the investor's question in character. Under 60 words. No meta-text.
- GENERATE BARGAIN: Decide on a bargaining response to an offer.

Match your personality type strictly in every response."""

# ─── Factory functions ────────────────────────────────────────────────────────

def build_investor_agents(model: str = "gemini-2.5-flash") -> dict:
    """
    Create one ADK Agent per investor.
    Returns {inv_id: Agent} — callers create Runners from these.
    """
    return {
        inv_id: Agent(
            name=f"{inv_id}_investor_agent",
            model=model,
            description=f"Shark Tank investor: {INVESTOR_PERSONAS[inv_id]['name']}",
            instruction=_investor_instruction(inv_id),
        )
        for inv_id in INVESTOR_IDS
    }


def build_founder_agent(model: str = "gemini-2.5-flash") -> Agent:
    """Create the ADK Agent for the AI Founder."""
    return Agent(
        name="founder_agent",
        model=model,
        description="AI startup founder who pitches and responds to investors",
        instruction=FOUNDER_INSTRUCTION,
    )


def build_runners(
    investor_agents: dict,
    founder_agent: Agent,
    app_name: str = "shark_tank",
) -> tuple[dict, Runner, dict, InMemorySessionService]:
    """
    Build one Runner per investor + one Runner for the founder.
    Each runner gets its OWN InMemorySessionService so that the 4 investor
    runners running concurrently via asyncio.gather never touch shared service
    state — the root cause of the intermittent 'root node agent canceled' crash
    that appeared at exchange 7+ when session read-modify-write operations
    interleaved across runners in the same service instance.

    Returns (investor_runners_dict, founder_runner,
             investor_session_svcs_dict, founder_session_svc).
    """
    investor_session_svcs = {
        inv_id: InMemorySessionService() for inv_id in investor_agents
    }
    investor_runners = {
        inv_id: Runner(
            agent=agent,
            app_name=app_name,
            session_service=investor_session_svcs[inv_id],
        )
        for inv_id, agent in investor_agents.items()
    }
    founder_session_svc = InMemorySessionService()
    founder_runner = Runner(
        agent=founder_agent,
        app_name=app_name,
        session_service=founder_session_svc,
    )
    return investor_runners, founder_runner, investor_session_svcs, founder_session_svc
