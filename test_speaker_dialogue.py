"""
test_speaker_dialogue.py - Unit test suite for Rule 230: Speaker Recognition, Acknowledgment, and Conversational Dialogue.
"""

import json
import re
import unittest

import speaker_recognition_tools
import master_audio_ducking
import agent_tuning_timer
import langchain_separation
import web_billboard


class TestSpeakerDialogue(unittest.TestCase):

    def setUp(self):
        # Reset dialogue state and ducking before each test
        speaker_recognition_tools.close_speaker_dialogue(reason="Test setup reset")
        master_audio_ducking.stop_master_talk(reason="Test setup reset")
        agent_tuning_timer.reset_tuning_timer_state()

    def tearDown(self):
        speaker_recognition_tools.close_speaker_dialogue(reason="Test teardown")
        master_audio_ducking.stop_master_talk(reason="Test teardown")
        agent_tuning_timer.reset_tuning_timer_state()

    def test_greeting_detection(self):
        """Test speaker greeting regex matches required greeting phrases."""
        greetings = [
            "hello",
            "HELLO",
            "Hello there",
            "can you hear me",
            "CAN YOU HEAR ME",
            "hey can you hear me now?",
            "can you hear this",
            "hey",
            "hi",
            "test mic",
            "mic check",
            "is anyone there",
            "are you there",
        ]
        for g in greetings:
            self.assertTrue(
                speaker_recognition_tools.is_speaker_greeting(g),
                f"Expected '{g}' to be recognized as greeting."
            )

        non_greetings = [
            "random sentence about crypto",
            "turn up the bass",
            "playing the soundtrack",
            "good morning sunshine",
        ]
        for ng in non_greetings:
            self.assertFalse(
                speaker_recognition_tools.is_speaker_greeting(ng),
                f"Expected '{ng}' to NOT be recognized as greeting."
            )

    def test_acknowledge_speaker_and_audio_ducking(self):
        """Test acknowledging speaker ducks audio and registers intent."""
        # Acknowledge "can you hear me"
        res = speaker_recognition_tools.acknowledge_speaker(
            text="Can you hear me?",
            speaker="host_speaker"
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["recognized"])
        self.assertTrue(res["is_greeting"])
        self.assertTrue(res["dialogue_active"])
        self.assertTrue(res["duck_active"])
        self.assertEqual(res["rule"], 230)
        self.assertIn("Yes, I hear you loud and clear", res["acknowledgement"])

        # Verify master audio ducking is engaged (Rule 228)
        duck_state = master_audio_ducking.get_ducking_state()
        self.assertTrue(duck_state["is_master_talking"])
        self.assertAlmostEqual(duck_state["current_volume"], 0.18, places=2)

        # Verify intent was registered in tuning timer (Rule 229)
        timer_status = agent_tuning_timer.get_tuning_timer_status()
        intent_agents = [item["agent_id"] for item in timer_status["speaking_intent_queue"]]
        self.assertIn("host_speaker", intent_agents)

        # Check dialogue state retrieval
        state = speaker_recognition_tools.get_speaker_dialogue_state()
        self.assertTrue(state["dialogue_active"])
        self.assertEqual(state["last_recognized_text"], "Can you hear me?")
        self.assertGreaterEqual(len(state["conversation_history"]), 1)

    def test_acknowledge_speaker_hello(self):
        """Test acknowledging 'hello' returns warm listening response."""
        res = speaker_recognition_tools.acknowledge_speaker("Hello room!")
        self.assertTrue(res["ok"])
        self.assertIn("Hello! I am here and listening", res["acknowledgement"])

    def test_dialogue_exchange(self):
        """Test interactive two-way conversation exchange."""
        speaker_recognition_tools.acknowledge_speaker("Hello")
        
        reply = speaker_recognition_tools.exchange_speaker_dialogue(
            message="What is the current status of the broadcast?",
            speaker="host_speaker"
        )
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["speaker"], "host_speaker")
        self.assertIn("Acknowledged:", reply["system_reply"])
        self.assertEqual(reply["rule"], 230)

        # Empty message should be rejected
        bad_reply = speaker_recognition_tools.exchange_speaker_dialogue("")
        self.assertFalse(bad_reply["ok"])
        self.assertIn("error", bad_reply)

    def test_close_speaker_dialogue_and_unduck(self):
        """Test closing speaker dialogue restores full audio volume."""
        # First engage
        speaker_recognition_tools.acknowledge_speaker("Hello")
        duck_state = master_audio_ducking.get_ducking_state()
        self.assertTrue(duck_state["is_master_talking"])

        # Now close
        close_res = speaker_recognition_tools.close_speaker_dialogue(reason="User closed overlay")
        self.assertTrue(close_res["ok"])
        self.assertFalse(close_res["dialogue_active"])
        self.assertFalse(close_res["duck_active"])

        # Verify audio restored to 1.00
        duck_state_after = master_audio_ducking.get_ducking_state()
        self.assertFalse(duck_state_after["is_master_talking"])
        self.assertAlmostEqual(duck_state_after["current_volume"], 1.0, places=2)

    def test_langchain_tools_and_catalog(self):
        """Test LangChain structured tools and registration in analysis tools catalog."""
        tools = speaker_recognition_tools.SPEAKER_DIALOGUE_TOOLS
        self.assertEqual(len(tools), 4)

        # Run acknowledge tool
        ack_tool = speaker_recognition_tools.acknowledge_speaker_tool
        out_ack = ack_tool.run({"text": "can you hear me", "speaker": "host_speaker"})
        parsed_ack = json.loads(out_ack)
        self.assertTrue(parsed_ack["ok"])
        self.assertTrue(parsed_ack["dialogue_active"])

        # Run exchange tool
        exch_tool = speaker_recognition_tools.speaker_dialogue_exchange_tool
        out_exch = exch_tool.run({"message": "Testing transmission", "speaker": "host_speaker"})
        parsed_exch = json.loads(out_exch)
        self.assertTrue(parsed_exch["ok"])

        # Run close tool
        close_tool = speaker_recognition_tools.close_speaker_dialogue_tool
        out_close = close_tool.run({"reason": "Finished"})
        parsed_close = json.loads(out_close)
        self.assertTrue(parsed_close["ok"])
        self.assertFalse(parsed_close["dialogue_active"])

        # Catalog validation
        catalog = langchain_separation.list_available_analysis_tools()
        dialogue_tools = [t for t in catalog if t["rule"] == 230]
        self.assertGreaterEqual(len(dialogue_tools), 4)
        self.assertEqual(dialogue_tools[0]["category"], "speaker_recognition_dialogue")

    def test_flask_api_endpoints(self):
        """Test Flask web API routes for speaker dialogue."""
        client = web_billboard.app.test_client()

        # 1. POST /api/speaker/acknowledge
        resp = client.post("/api/speaker/acknowledge", json={"text": "hello", "speaker": "host_speaker"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["dialogue_active"])

        # 2. GET /api/speaker/dialogue
        resp_get = client.get("/api/speaker/dialogue")
        self.assertEqual(resp_get.status_code, 200)
        state = resp_get.get_json()
        self.assertTrue(state["dialogue_active"])

        # 3. POST /api/speaker/dialogue
        resp_post = client.post("/api/speaker/dialogue", json={"message": "Good evening", "speaker": "host_speaker"})
        self.assertEqual(resp_post.status_code, 200)
        post_data = resp_post.get_json()
        self.assertTrue(post_data["ok"])
        self.assertIn("Good evening", post_data["system_reply"])

        # 4. POST /api/speaker/dialogue/close
        resp_close = client.post("/api/speaker/dialogue/close", json={"reason": "Close button clicked"})
        self.assertEqual(resp_close.status_code, 200)
        close_data = resp_close.get_json()
        self.assertTrue(close_data["ok"])
        self.assertFalse(close_data["dialogue_active"])

    def test_contiguous_rules_1_to_230(self):
        """Verify rules 1 to 230 are strictly contiguous in word_segment.py."""
        with open("word_segment.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = [int(m) for m in re.findall(r'\"(\d+)\.\s', content)]
        self.assertGreaterEqual(max(found), 230)
        missing = [i for i in range(1, max(found) + 1) if i not in found]
        self.assertEqual(missing, [], f"Missing contiguous rules: {missing}")


if __name__ == "__main__":
    unittest.main()
