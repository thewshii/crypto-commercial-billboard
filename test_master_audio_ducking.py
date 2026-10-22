"""
test_master_audio_ducking.py - Unit test suite for Rule 228 Master Voice Audio Ducking,
LangGraph State Machine, and Tool-Gated Attenuation.
"""

import json
import re
import unittest
import master_audio_ducking
import langchain_separation
import music_playback_tools


class TestMasterAudioDuckingSuite(unittest.TestCase):
    def setUp(self):
        # Reset state before each test
        master_audio_ducking.stop_master_talk(reason="Test setUp reset")

    def tearDown(self):
        master_audio_ducking.stop_master_talk(reason="Test tearDown cleanup")

    def test_start_and_stop_master_talk(self):
        # Initial state should be not talking
        s0 = master_audio_ducking.get_ducking_state()
        self.assertFalse(s0["is_master_talking"])
        self.assertEqual(s0["current_volume"], 1.0)

        # Start master talking
        s1 = master_audio_ducking.start_master_talk(master_source="test_host", duck_level=0.15, reason="Testing start")
        self.assertTrue(s1["is_master_talking"])
        self.assertEqual(s1["current_volume"], 0.15)
        self.assertEqual(s1["duck_level"], 0.15)

        # Check ledger record
        now_state = music_playback_tools.get_now_playing()
        self.assertEqual(now_state["volume"], 0.15)

        # Stop master talking
        s2 = master_audio_ducking.stop_master_talk(reason="Testing stop")
        self.assertFalse(s2["is_master_talking"])
        self.assertEqual(s2["current_volume"], 1.0)

        now_state2 = music_playback_tools.get_now_playing()
        self.assertEqual(now_state2["volume"], 1.0)

    def test_toggle_master_talk(self):
        t1 = master_audio_ducking.toggle_master_talk()
        self.assertTrue(t1["is_master_talking"])

        t2 = master_audio_ducking.toggle_master_talk()
        self.assertFalse(t2["is_master_talking"])

    def test_duck_level_clamping(self):
        master_audio_ducking.set_ducking_level(-0.5)
        s_low = master_audio_ducking.get_ducking_state()
        self.assertEqual(s_low["duck_level"], 0.0)

        master_audio_ducking.set_ducking_level(1.5)
        s_high = master_audio_ducking.get_ducking_state()
        self.assertEqual(s_high["duck_level"], 1.0)

        master_audio_ducking.set_ducking_level(0.18)
        s_norm = master_audio_ducking.get_ducking_state()
        self.assertEqual(s_norm["duck_level"], 0.18)

    def test_master_talk_context_manager(self):
        self.assertFalse(master_audio_ducking.get_ducking_state()["is_master_talking"])
        with master_audio_ducking.master_talk_context(duck_level=0.12, reason="In context"):
            self.assertTrue(master_audio_ducking.get_ducking_state()["is_master_talking"])
            self.assertEqual(master_audio_ducking.get_ducking_state()["current_volume"], 0.12)
        # Exited context, volume must be restored
        self.assertFalse(master_audio_ducking.get_ducking_state()["is_master_talking"])
        self.assertEqual(master_audio_ducking.get_ducking_state()["current_volume"], 1.0)

    def test_langgraph_workflow_master_speech(self):
        res = master_audio_ducking.run_langgraph_master_talk(
            user_input="Testing master priority announcement through LangGraph",
            speaker="master",
            duck_level=0.15
        )
        self.assertIn("response", res)
        self.assertIn("[VOICE: MASTER]", res["response"])
        self.assertEqual(res["stage"], "completed")
        self.assertTrue(any("ducking engaged" in log for log in res.get("logs", [])))
        self.assertTrue(any("ducking released" in log for log in res.get("logs", [])))

    def test_langgraph_workflow_non_master_speech(self):
        res = master_audio_ducking.run_langgraph_master_talk(
            user_input="Secondary agent chatter",
            speaker="agent",
            duck_level=0.18
        )
        self.assertIn("response", res)
        self.assertTrue(any("Standard utterance" in log for log in res.get("logs", [])))

    def test_langchain_master_ducking_tools(self):
        # 1. Start Tool
        raw_start = master_audio_ducking.master_talk_start_tool.invoke({
            "master_source": "operator",
            "duck_level": 0.2,
            "reason": "Tool invocation"
        })
        parsed_start = json.loads(raw_start)
        self.assertTrue(parsed_start["is_master_talking"])

        # 2. Status Tool
        raw_status = master_audio_ducking.master_ducking_status_tool.invoke({})
        parsed_status = json.loads(raw_status)
        self.assertTrue(parsed_status["is_master_talking"])
        self.assertEqual(parsed_status["rule"], 228)

        # 3. Stop Tool
        raw_stop = master_audio_ducking.master_talk_stop_tool.invoke({"reason": "Tool invocation stop"})
        parsed_stop = json.loads(raw_stop)
        self.assertFalse(parsed_stop["is_master_talking"])

        # 4. Catalog Check
        catalog = langchain_separation.list_available_analysis_tools()
        duck_tools = [t for t in catalog if t["rule"] == 228]
        self.assertGreaterEqual(len(duck_tools), 5)
        self.assertEqual(duck_tools[0]["category"], "master_ducking_langgraph")

    def test_contiguous_rules_1_to_228(self):
        with open("word_segment.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = [int(m) for m in re.findall(r'\"(\d+)\.\s', content)]
        self.assertEqual(max(found), 228)
        missing = [i for i in range(1, 229) if i not in found]
        self.assertEqual(missing, [], f"Missing contiguous rules: {missing}")


if __name__ == "__main__":
    unittest.main()
