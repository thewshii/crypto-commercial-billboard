"""
test_rdp_screen.py - Unit test suite for Rule 231: Remote Desktop (RDP) Screen Acknowledgment and Display Sync.
"""

import json
import re
import unittest

import rdp_screen_manager
import master_audio_ducking
import agent_tuning_timer
import langchain_separation
import web_billboard


class TestRdpScreen(unittest.TestCase):

    def setUp(self):
        rdp_screen_manager.reset_rdp_screen_state()
        master_audio_ducking.stop_master_talk(reason="Test setup reset")
        agent_tuning_timer.reset_tuning_timer_state()

    def tearDown(self):
        rdp_screen_manager.reset_rdp_screen_state()
        master_audio_ducking.stop_master_talk(reason="Test teardown")
        agent_tuning_timer.reset_tuning_timer_state()

    def test_acknowledge_rdp_screen(self):
        """Test acknowledging RDP screen visibility updates state and engages audio ducking."""
        res = rdp_screen_manager.acknowledge_rdp_screen(
            resolution="2560x1440",
            client_info="Test FreeRDP Client"
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["acknowledged"])
        self.assertTrue(res["screen_visible"])
        self.assertEqual(res["display_resolution"], "2560x1440")
        self.assertEqual(res["rule"], 231)
        self.assertIn("Remote desktop connection acknowledged", res["speech"])

        # Check telemetry state
        status = rdp_screen_manager.get_rdp_screen_status()
        self.assertTrue(status["screen_acknowledged"])
        self.assertTrue(status["screen_visible"])
        self.assertEqual(status["display_resolution"], "2560x1440")
        self.assertEqual(status["total_acknowledgements"], 1)
        self.assertEqual(len(status["history"]), 1)

        # Check audio ducking was engaged (Rule 228)
        duck_state = master_audio_ducking.get_ducking_state()
        self.assertTrue(duck_state["is_master_talking"])

        # Check intent queue in tuning timer (Rule 229)
        timer_st = agent_tuning_timer.get_tuning_timer_status()
        intent_agents = [item["agent_id"] for item in timer_st["speaking_intent_queue"]]
        self.assertIn("rdp_display_sync", intent_agents)

    def test_toggle_rdp_screen_visibility(self):
        """Test toggling RDP screen visibility."""
        res_off = rdp_screen_manager.toggle_rdp_screen_visibility(visible=False)
        self.assertTrue(res_off["ok"])
        self.assertFalse(res_off["screen_visible"])

        res_on = rdp_screen_manager.toggle_rdp_screen_visibility(visible=True)
        self.assertTrue(res_on["ok"])
        self.assertTrue(res_on["screen_visible"])

        # Toggle without param
        res_toggle = rdp_screen_manager.toggle_rdp_screen_visibility()
        self.assertFalse(res_toggle["screen_visible"])

    def test_langchain_tools_and_catalog(self):
        """Test LangChain structured tools and registration in analysis catalog."""
        tools = rdp_screen_manager.RDP_SCREEN_TOOLS
        self.assertEqual(len(tools), 3)

        # 1. Acknowledge tool run
        ack_tool = rdp_screen_manager.acknowledge_rdp_screen_tool
        out_ack = ack_tool.run({"resolution": "1920x1080", "client_info": "Agentic LangChain Runner"})
        parsed_ack = json.loads(out_ack)
        self.assertTrue(parsed_ack["ok"])
        self.assertTrue(parsed_ack["acknowledged"])

        # 2. Status tool run
        status_tool = rdp_screen_manager.get_rdp_screen_status_tool
        out_status = status_tool.run({})
        parsed_status = json.loads(out_status)
        self.assertTrue(parsed_status["screen_acknowledged"])

        # 3. Toggle tool run
        toggle_tool = rdp_screen_manager.toggle_rdp_screen_visibility_tool
        out_toggle = toggle_tool.run({"visible": True})
        parsed_toggle = json.loads(out_toggle)
        self.assertTrue(parsed_toggle["screen_visible"])

        # 4. Analysis catalog check
        catalog = langchain_separation.list_available_analysis_tools()
        rdp_tools = [t for t in catalog if t["rule"] == 231]
        self.assertGreaterEqual(len(rdp_tools), 3)
        self.assertEqual(rdp_tools[0]["category"], "rdp_screen_sync")

    def test_flask_api_endpoints(self):
        """Test Flask web API routes for RDP screen."""
        client = web_billboard.app.test_client()

        # 1. POST /api/game/rdp/acknowledge
        resp_ack = client.post("/api/game/rdp/acknowledge", json={
            "resolution": "1920x1080",
            "client_info": "Test Web Browser"
        })
        self.assertEqual(resp_ack.status_code, 200)
        data_ack = resp_ack.get_json()
        self.assertTrue(data_ack["ok"])
        self.assertTrue(data_ack["acknowledged"])
        self.assertEqual(data_ack["rule"], 231)

        # 2. GET /api/game/rdp/status
        resp_status = client.get("/api/game/rdp/status")
        self.assertEqual(resp_status.status_code, 200)
        data_status = resp_status.get_json()
        self.assertTrue(data_status["screen_acknowledged"])
        self.assertEqual(data_status["display_resolution"], "1920x1080")

        # 3. POST /api/game/rdp/toggle
        resp_toggle = client.post("/api/game/rdp/toggle", json={"visible": True})
        self.assertEqual(resp_toggle.status_code, 200)
        data_toggle = resp_toggle.get_json()
        self.assertTrue(data_toggle["ok"])
        self.assertTrue(data_toggle["screen_visible"])

    def test_contiguous_rules_1_to_231(self):
        """Verify rules 1 to 231 are strictly contiguous in word_segment.py."""
        with open("word_segment.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = [int(m) for m in re.findall(r'\"(\d+)\.\s', content)]
        self.assertGreaterEqual(max(found), 231)
        missing = [i for i in range(1, max(found) + 1) if i not in found]
        self.assertEqual(missing, [], f"Missing contiguous rules: {missing}")


if __name__ == "__main__":
    unittest.main()
