"""
test_agent_tuning_timer.py - Unit test suite for Rule 229 Tuning Timer System,
Turn-Taking Intent Queue, and Ranked Speaker Consensus (Most to Least).
"""

import json
import re
import unittest
import agent_tuning_timer
import langchain_separation


class TestAgentTuningTimerSuite(unittest.TestCase):
    def setUp(self):
        # Configure standard slot duration and tempo
        agent_tuning_timer.configure_tuning_timer(slot_duration_sec=30.0, tempo_bpm=72, tuning_frequency_hz=432.0)

    def test_get_timer_status(self):
        st = agent_tuning_timer.get_tuning_timer_status()
        self.assertTrue(st["ok"])
        self.assertTrue(st["timer_active"])
        self.assertGreater(st["time_remaining_sec"], 0.0)
        self.assertEqual(st["tuning_frequency_hz"], 432.0)
        self.assertEqual(st["tempo_bpm"], 72)
        self.assertIn("current_speaker", st)
        self.assertIn("consensus_ranking", st)

    def test_register_speaking_intent(self):
        # Register intent for motherly_voice
        res = agent_tuning_timer.register_speaking_intent(
            agent_id="motherly_voice",
            urgency=4,
            topic="Frequency and comfort alignment"
        )
        self.assertTrue(res["ok"])
        q = res["speaking_intent_queue"]
        item = next((i for i in q if i["agent_id"] == "motherly_voice"), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["urgency"], 4)
        self.assertEqual(item["topic"], "Frequency and comfort alignment")

    def test_cast_speaker_ranking_vote(self):
        # Cast a ranked ballot from most to least
        ballot = ["motherly_voice", "letta_memgpt", "tension_sentinel", "adam_voice"]
        res = agent_tuning_timer.cast_speaker_ranking_vote(
            voter_agent_id="primary_agent",
            ranked_candidates=ballot,
            reason="Prioritizing stabilization"
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["voter_agent_id"], "primary_agent")
        ranking = res["consensus_ranking"]
        self.assertGreater(len(ranking), 0)

        # First choice in ballot should have high Borda points
        top = ranking[0]
        self.assertGreater(top["borda_points"], 0)

    def test_simulate_multi_agent_vote(self):
        sim = agent_tuning_timer.simulate_multi_agent_vote(topic="Dynamic room consensus")
        self.assertTrue(sim["ok"])
        self.assertGreaterEqual(len(sim["participating_agents"]), 6)

        ranking = sim["consensus_ranking"]
        self.assertGreaterEqual(len(ranking), 6)
        # Verify order is strictly sorted by borda points descending
        points = [r["borda_points"] for r in ranking]
        self.assertEqual(points, sorted(points, reverse=True))
        self.assertEqual(ranking[0]["rank"], 1)

    def test_advance_speaker_turn(self):
        # Set up a known vote where motherly_voice is top
        agent_tuning_timer.cast_speaker_ranking_vote(
            voter_agent_id="test_agent",
            ranked_candidates=["motherly_voice", "letta_memgpt", "tension_sentinel"]
        )
        # Advance turn
        adv = agent_tuning_timer.advance_speaker_turn(reason="Test transition")
        self.assertTrue(adv["ok"])
        self.assertEqual(adv["current_speaker"], "motherly_voice")
        self.assertGreater(adv["total_turns_completed"], 0)

    def test_configure_tuning_timer(self):
        c = agent_tuning_timer.configure_tuning_timer(slot_duration_sec=45.0, tempo_bpm=80)
        self.assertEqual(c["slot_duration_sec"], 45.0)
        self.assertEqual(c["tempo_bpm"], 80)

        # Clamping
        c_low = agent_tuning_timer.configure_tuning_timer(slot_duration_sec=1.0)
        self.assertEqual(c_low["slot_duration_sec"], 5.0)

    def test_langchain_tuning_timer_tools(self):
        # 1. Status Tool
        raw_st = agent_tuning_timer.get_tuning_timer_status_tool.invoke({})
        parsed_st = json.loads(raw_st)
        self.assertTrue(parsed_st["ok"])

        # 2. Intent Tool
        raw_intent = agent_tuning_timer.register_speaking_intent_tool.invoke({
            "agent_id": "letta_memgpt",
            "urgency": 3,
            "topic": "Context retention audit"
        })
        parsed_intent = json.loads(raw_intent)
        self.assertTrue(parsed_intent["ok"])

        # 3. Simulate Vote Tool
        raw_vote = agent_tuning_timer.simulate_multi_agent_vote_tool.invoke({"topic": "Tool test"})
        parsed_vote = json.loads(raw_vote)
        self.assertTrue(parsed_vote["ok"])

        # 4. Catalog Check
        catalog = langchain_separation.list_available_analysis_tools()
        timer_tools = [t for t in catalog if t["rule"] == 229]
        self.assertGreaterEqual(len(timer_tools), 5)
        self.assertEqual(timer_tools[0]["category"], "tuning_timer_voting")

    def test_contiguous_rules_1_to_229(self):
        with open("word_segment.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = [int(m) for m in re.findall(r'\"(\d+)\.\s', content)]
        self.assertEqual(max(found), 229)
        missing = [i for i in range(1, 230) if i not in found]
        self.assertEqual(missing, [], f"Missing contiguous rules: {missing}")


if __name__ == "__main__":
    unittest.main()
