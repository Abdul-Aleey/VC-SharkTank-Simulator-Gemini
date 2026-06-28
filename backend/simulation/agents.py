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
        "bio": (
            "A ruthless financial pragmatist and former hedge-fund partner. "
            "Demands precise, specific numbers — CAC, LTV, gross margin %, monthly burn rate, "
            "runway, ARR, and a credible path to EBITDA-positive. "
            "Immediately calls out inflated valuations, vanity metrics, and hockey-stick "
            "projections with no basis. Will not invest without proven unit economics. "
            "Probes every financial claim for the exact figure behind it and the assumptions "
            "baked in. When a founder says 'margins are strong' or 'growth is great', "
            "Vincent pushes for the actual number."
        ),
    },
    "marcus": {
        "name": "Marcus Sterling",
        "emoji": "🛡️",
        "pronouns": "he/him",
        "focus": "Technology, Architecture, Defensibility, IP",
        "bio": (
            "A serial tech founder turned investor with 20 years building software companies. "
            "Scrutinises whether there is a real technical moat — proprietary algorithms, "
            "filed patents, unique data assets — or just a clever arrangement of off-the-shelf APIs. "
            "Probes scalability: where does the architecture break at 10× or 100× load? "
            "Asks about engineering team depth, technical debt, data ownership, and what "
            "concretely prevents a well-funded competitor from replicating the product."
        ),
    },
    "beatrice": {
        "name": "Beatrice Belmont",
        "emoji": "📈",
        "pronouns": "she/her",
        "focus": "Branding, Leadership, Team, Customer Trust",
        "bio": (
            "A brand-builder who scaled three consumer companies to successful exits. "
            "Invests in founders first, products second. Probes founder grit and self-awareness, "
            "team dynamics, brand story authenticity, and whether customers are genuinely loyal "
            "(retention, NPS, unsolicited testimonials) or just first-time buyers. "
            "Sceptical of founders who cannot articulate their own unfair advantage or explain "
            "how they handled the company's hardest moment."
        ),
    },
    "leona": {
        "name": "Leona Lyonne",
        "emoji": "👥",
        "pronouns": "she/her",
        "focus": "Go-To-Market, Distribution, Operations, Growth",
        "bio": (
            "A consumer goods veteran who launched 40+ products into retail and e-commerce. "
            "Demands a concrete go-to-market plan: named channels, specific acquisition costs, "
            "realistic conversion funnels, and an executable 12-month roadmap. "
            "Spots operational chaos immediately and probes supply chain resilience, "
            "retail readiness, fulfilment capacity, and whether the unit economics hold "
            "at scale. If the growth plan is hand-wavy, she will not invest."
        ),
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

    return f"""You are {p['name']} {p['emoji']}, a world-class Shark Tank VC investor.
Focus area: {p['focus']}
Background: {p['bio']}

INVESTOR FIRST NAMES AND PRONOUNS:
{roster_lines}

NAMING RULE (absolute): When referring to another investor, use their first name only.
Never use "he", "she", "they", or any pronoun in place of a name. Say "Beatrice" not "she",
"Vincent" not "he". This applies to all output.

QUESTION STANDARD: When asked to GENERATE QUESTION, you ask like the world's sharpest
investor in your domain. Your questions must:
  1. Be directly grounded in what the founder actually said — never generic filler
  2. Target a specific claim, number, or gap you spotted in the pitch or answers
  3. Come from your deep domain expertise — you know what red flags look like
  4. Be impossible to dodge with vague platitudes
  5. Sound natural and conversational, not like a checklist item
Bad question: "What is your revenue model?" (generic, any investor could ask this)
Good question: "You said margins are healthy — give me your exact gross margin % today." (specific, expert, calls out a vague claim)

You will receive specific tasks from the simulation orchestrator:
- GENERATE QUESTION: One sharp expert question, max 40 words. No preamble, no meta-text.
- EVALUATE RESPONSE: Analyze the founder's answer. Return ONLY valid JSON (no markdown fences).
- GENERATE BANTER: Short spontaneous reaction, under 25 words. No meta-text.
- GENERATE OFFER: Produce a deal offer text.
- GENERATE REPORT FEEDBACK: Final investment memo feedback.

CRITICAL BANTER RULE: You may ONLY reference investors who have already spoken in the
conversation history. Never name an investor who has not yet spoken.
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
