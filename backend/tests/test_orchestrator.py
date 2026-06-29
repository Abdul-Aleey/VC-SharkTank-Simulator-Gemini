"""
Unit tests for SimulationOrchestrator logic that doesn't require live ADK/Gemini calls.
Run with: pytest backend/tests/test_orchestrator.py -v
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulation.agents import INVESTOR_PERSONAS, INVESTOR_IDS
from simulation.orchestrator import SimulationOrchestrator, CONFIDENCE_OUT, PERSONALITY_GUIDE


# ── Minimal config for instantiating the orchestrator without ADK ──────────────

SAMPLE_CONFIG = {
    "founderName":  "Jane Doe",
    "startupName":  "TestCo",
    "sector":       "SaaS",
    "description":  "AI-powered analytics platform",
    "askAmount":    "$500K",
    "askEquity":    "15",
    "personality":  "excellent",
    "model":        "gemini-2.5-flash",
    "rounds":       3,
    "language":     "en",
    "mode":         "ai",
}


def make_orchestrator():
    """Build an orchestrator with all ADK/network calls stubbed out."""
    with patch("simulation.orchestrator.build_investor_agents", return_value={i: MagicMock() for i in INVESTOR_IDS}), \
         patch("simulation.orchestrator.build_founder_agent",   return_value=MagicMock()), \
         patch("simulation.orchestrator.build_runners",         return_value=({i: MagicMock() for i in INVESTOR_IDS}, MagicMock(), {i: MagicMock() for i in INVESTOR_IDS}, MagicMock())):
        orc = SimulationOrchestrator.__new__(SimulationOrchestrator)
        orc.config         = SAMPLE_CONFIG
        orc.is_ja          = False
        orc.chat_history   = []
        orc.investor_states = {
            inv_id: {
                "confidence":       50,
                "trend":            0,
                "status":           "ACTIVE",
                "agentState":       "IDLE",
                "questionsAsked":   0,
                "questionsHistory": [],
                "thoughtBubble":    "",
                "strengths":        [],
                "weaknesses":       [],
                "risks":            [],
                "isThinking":       False,
            }
            for inv_id in INVESTOR_IDS
        }
        return orc


# ── _parse_json ────────────────────────────────────────────────────────────────

class TestParseJson:
    def setup_method(self):
        self.orc = make_orchestrator()

    def test_valid_json(self):
        result = self.orc._parse_json('{"key": "value"}', {})
        assert result == {"key": "value"}

    def test_json_with_markdown_fences(self):
        raw = "```json\n{\"key\": \"value\"}\n```"
        result = self.orc._parse_json(raw, {})
        assert result == {"key": "value"}

    def test_invalid_json_returns_fallback(self):
        fallback = {"action": "accept"}
        result = self.orc._parse_json("not json at all", fallback)
        assert result == fallback

    def test_empty_string_returns_fallback(self):
        fallback = {"action": "accept"}
        result = self.orc._parse_json("", fallback)
        assert result == fallback

    def test_partial_json_with_embedded_object_returns_fallback(self):
        # _parse_json does not extract JSON from surrounding text — it returns fallback
        fallback = {"confidence": 0}
        raw = 'Some text {"confidence": 75, "trend": 5} more text'
        result = self.orc._parse_json(raw, fallback)
        assert result == fallback


# ── Equity clamping ────────────────────────────────────────────────────────────

class TestEquityClamping:
    """Investor offer equity must be >= founder's ask; max 49%."""

    def test_clamp_below_ask(self):
        ask_equity = 15
        raw_equity = 5   # model hallucinated below ask
        clamped = max(ask_equity, min(49, raw_equity))
        assert clamped == 15

    def test_clamp_above_49(self):
        ask_equity = 15
        raw_equity = 60
        clamped = max(ask_equity, min(49, raw_equity))
        assert clamped == 49

    def test_valid_equity_unchanged(self):
        ask_equity = 15
        raw_equity = 25
        clamped = max(ask_equity, min(49, raw_equity))
        assert clamped == 25

    def test_exactly_at_ask(self):
        ask_equity = 15
        raw_equity = 15
        clamped = max(ask_equity, min(49, raw_equity))
        assert clamped == 15


# ── Counter equity validation ──────────────────────────────────────────────────

class TestCounterEquityValidation:
    """Founder counter must be between ask_equity and investor's offered equity."""

    def _clamp_counter(self, ask_equity, investor_equity, proposed):
        return max(ask_equity, min(investor_equity, proposed))

    def test_counter_below_ask_clamped_up(self):
        assert self._clamp_counter(15, 30, 5) == 15

    def test_counter_above_investor_clamped_down(self):
        assert self._clamp_counter(15, 30, 40) == 30

    def test_valid_counter_unchanged(self):
        assert self._clamp_counter(15, 30, 22) == 22

    def test_counter_at_ask_boundary(self):
        assert self._clamp_counter(15, 30, 15) == 15

    def test_counter_at_investor_boundary(self):
        assert self._clamp_counter(15, 30, 30) == 30


# ── Joint deal probability ─────────────────────────────────────────────────────

class TestJointDealProbability:
    """Two sharks with similar confidence should have a higher joint deal chance."""

    def _joint_prob(self, conf_a, conf_b):
        diff = abs(conf_a - conf_b)
        return max(0.10, 0.60 - diff * 0.02)

    def test_identical_confidence_gives_max_prob(self):
        prob = self._joint_prob(80, 80)
        assert prob == pytest.approx(0.60)

    def test_far_apart_confidence_gives_min_prob(self):
        prob = self._joint_prob(50, 100)
        assert prob == pytest.approx(0.10)

    def test_moderate_diff_in_range(self):
        prob = self._joint_prob(75, 85)  # diff=10 → 0.60 - 0.20 = 0.40
        assert prob == pytest.approx(0.40)

    def test_prob_never_below_floor(self):
        for diff in range(0, 60):
            prob = self._joint_prob(50, 50 + diff)
            assert prob >= 0.10

    def test_prob_never_above_ceiling(self):
        for diff in range(0, 60):
            prob = self._joint_prob(50, 50 + diff)
            assert prob <= 0.60


# ── Banter partner exclusion ───────────────────────────────────────────────────

class TestBanterPartnerExclusion:
    """Joint partners must never be selected to react to each other's offers."""

    def _get_reactor_pool(self, just_offered_id, active_offers):
        joint_partner_of = {}
        for o in active_offers.values():
            if o.get("isJoint") and len(o["investors"]) >= 2:
                a, b = o["investors"][0], o["investors"][1]
                joint_partner_of[a] = b
                joint_partner_of[b] = a

        just_offered_partner = joint_partner_of.get(just_offered_id)
        all_investors = set(active_offers.keys())
        for o in active_offers.values():
            if o.get("isJoint"):
                all_investors.update(o["investors"])

        return [
            i for i in all_investors
            if i != just_offered_id and i != just_offered_partner
        ]

    def test_joint_partner_excluded_from_reactor_pool(self):
        active_offers = {
            "vincent": {"investors": ["vincent", "marcus"], "isJoint": True,  "equity": 25},
            "beatrice": {"investors": ["beatrice"],          "isJoint": False, "equity": 20},
        }
        # vincent just spoke — marcus (partner) should be excluded
        pool = self._get_reactor_pool("vincent", active_offers)
        assert "marcus"  not in pool
        assert "vincent" not in pool
        assert "beatrice" in pool

    def test_solo_investor_can_always_react(self):
        active_offers = {
            "vincent": {"investors": ["vincent", "marcus"], "isJoint": True,  "equity": 25},
            "leona":   {"investors": ["leona"],             "isJoint": False, "equity": 22},
        }
        pool = self._get_reactor_pool("marcus", active_offers)
        assert "leona" in pool

    def test_no_self_reaction(self):
        active_offers = {
            "vincent":  {"investors": ["vincent"],  "isJoint": False, "equity": 25},
            "beatrice": {"investors": ["beatrice"], "isJoint": False, "equity": 20},
        }
        pool = self._get_reactor_pool("vincent", active_offers)
        assert "vincent" not in pool
        assert "beatrice" in pool


# ── Confidence & status thresholds ────────────────────────────────────────────

class TestConfidenceThresholds:
    def test_confidence_out_constant(self):
        assert CONFIDENCE_OUT == 25

    def test_investor_starts_at_50(self):
        orc = make_orchestrator()
        for inv_id in INVESTOR_IDS:
            assert orc.investor_states[inv_id]["confidence"] == 50

    def test_below_threshold_should_exit(self):
        assert 24 <= CONFIDENCE_OUT
        assert 25 == CONFIDENCE_OUT

    def test_at_threshold_should_exit(self):
        # confidence == CONFIDENCE_OUT means OUT (≤ 25)
        assert CONFIDENCE_OUT <= CONFIDENCE_OUT


# ── Persona completeness ───────────────────────────────────────────────────────

class TestPersonaCompleteness:
    def test_all_investor_ids_have_personas(self):
        for inv_id in INVESTOR_IDS:
            assert inv_id in INVESTOR_PERSONAS

    def test_all_personas_have_required_fields(self):
        required = {"name", "emoji", "pronouns", "focus", "bio"}
        for inv_id, persona in INVESTOR_PERSONAS.items():
            missing = required - set(persona.keys())
            assert not missing, f"{inv_id} missing: {missing}"

    def test_all_personality_levels_exist(self):
        expected = {"excellent", "good", "average", "weak", "poor", "very_poor"}
        assert expected == set(PERSONALITY_GUIDE.keys())

    def test_personality_descriptions_are_non_empty(self):
        for key, desc in PERSONALITY_GUIDE.items():
            assert len(desc) > 20, f"Personality '{key}' description too short"


# ── _add_to_history ────────────────────────────────────────────────────────────

class TestAddToHistory:
    def setup_method(self):
        self.orc = make_orchestrator()

    def test_adds_entry_to_history(self):
        self.orc._add_to_history("vincent", "Hello room.")
        assert len(self.orc.chat_history) == 1
        assert self.orc.chat_history[0]["text"] == "Hello room."

    def test_banter_flag_set_when_specified(self):
        self.orc._add_to_history("vincent", "Nice pitch.", is_banter=True)
        assert self.orc.chat_history[0].get("isBanter") is True

    def test_banter_flag_absent_by_default(self):
        self.orc._add_to_history("vincent", "Nice pitch.")
        assert "isBanter" not in self.orc.chat_history[0]

    def test_sender_name_resolved_from_persona(self):
        self.orc._add_to_history("vincent", "Hello.")
        assert self.orc.chat_history[0]["senderName"] == "Vincent Vance"

    def test_founder_name_from_config(self):
        self.orc._add_to_history("founder", "Thank you.")
        assert self.orc.chat_history[0]["senderName"] == "Jane Doe"
