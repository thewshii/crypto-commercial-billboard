"""
test_esp32_spatial_receiver.py - Unit test suite for Rule 233:
ESP32 Mobile Spatial Tracking Over Local Wi-Fi, Static IP Socket Receiver, and Stationary Terminal Integration.
"""

import json
import os
import shutil
import tempfile
import unittest

import esp32_spatial_receiver
import langchain_separation
import web_billboard


class TestEsp32SpatialReceiver(unittest.TestCase):

    def setUp(self):
        # Reset spatial state for testing
        esp32_spatial_receiver.stop_spatial_receiver()
        with esp32_spatial_receiver._LOCK:
            esp32_spatial_receiver._SPATIAL_STATE["total_packets_received"] = 0
            esp32_spatial_receiver._SPATIAL_STATE["last_packet_timestamp"] = 0
            esp32_spatial_receiver._SPATIAL_STATE["connected_client"] = None
            esp32_spatial_receiver._SPATIAL_STATE["calibration_offset"] = {
                "x": 0.0, "y": 0.0, "z": 0.0,
                "roll": 0.0, "pitch": 0.0, "yaw": 0.0
            }
            esp32_spatial_receiver._SPATIAL_STATE["history"] = []

        web_billboard.app.config["TESTING"] = True
        self.client = web_billboard.app.test_client()

    def tearDown(self):
        esp32_spatial_receiver.stop_spatial_receiver()

    def test_spatial_receiver_start_and_stop(self):
        """Test starting and stopping the UDP socket receiver."""
        res_start = esp32_spatial_receiver.start_spatial_receiver(host="127.0.0.1", port=8889)
        self.assertTrue(res_start["ok"])
        st = esp32_spatial_receiver.get_spatial_tracking_status()
        self.assertTrue(st["receiver_active"])
        self.assertEqual(st["listen_port"], 8889)

        res_stop = esp32_spatial_receiver.stop_spatial_receiver()
        self.assertTrue(res_stop["ok"])
        st2 = esp32_spatial_receiver.get_spatial_tracking_status()
        self.assertFalse(st2["receiver_active"])

    def test_process_spatial_packet(self):
        """Test parsing, calibration, and telemetry integration of ESP32 packet."""
        packet_dict = {
            "device_id": "esp32_test_node",
            "seq": 101,
            "uptime_ms": 42000,
            "static_ip": "192.168.1.150",
            "accel": {"x": 0.02, "y": -0.01, "z": 9.81},
            "gyro": {"x": 0.5, "y": -0.2, "z": 0.0},
            "orientation": {"roll": 5.0, "pitch": -2.0, "yaw": 45.0},
            "position": {"x": 1.25, "y": 0.75, "z": 1.10},
            "velocity": {"x": 0.05, "y": 0.0, "z": 0.0},
            "motion_state": "MOVING",
            "impact_detected": False,
            "battery_v": 3.98,
            "rssi_dbm": -50
        }
        raw_bytes = json.dumps(packet_dict).encode("utf-8")
        res = esp32_spatial_receiver.process_spatial_packet(raw_bytes, ("192.168.1.150", 5544))
        self.assertTrue(res["ok"])

        # Check telemetry state
        tel = res["telemetry"]
        self.assertEqual(tel["seq"], 101)
        self.assertEqual(tel["static_ip"], "192.168.1.150")
        self.assertTrue(tel["static_ip_verified"])
        self.assertEqual(tel["position"]["x"], 1.25)
        self.assertEqual(tel["motion_state"], "MOVING")

        st = esp32_spatial_receiver.get_spatial_tracking_status()
        self.assertEqual(st["total_packets_received"], 1)
        self.assertEqual(len(st["telemetry"]), len(tel))

    def test_zero_calibration(self):
        """Test zero-calibrating the reference origin offsets."""
        esp32_spatial_receiver.simulate_esp32_packet(
            static_ip="192.168.1.150",
            pos_x=2.0, pos_y=3.0, pos_z=1.0,
            roll=10.0, pitch=5.0, yaw=90.0
        )
        # Calibrate
        cal_res = esp32_spatial_receiver.calibrate_spatial_tracker(zero_position=True, zero_orientation=True)
        self.assertTrue(cal_res["ok"])
        self.assertEqual(cal_res["calibration_offset"]["x"], 2.0)
        self.assertEqual(cal_res["calibration_offset"]["roll"], 10.0)

        # Next packet should be relative to calibrated origin
        res2 = esp32_spatial_receiver.simulate_esp32_packet(
            static_ip="192.168.1.150",
            pos_x=2.5, pos_y=3.0, pos_z=1.0,
            roll=12.0, pitch=5.0, yaw=90.0
        )
        tel = res2["telemetry"]
        self.assertAlmostEqual(tel["position"]["x"], 0.5, places=2)
        self.assertAlmostEqual(tel["orientation"]["roll"], 2.0, places=2)

    def test_impact_triggers_inventory_integration(self):
        """Test that high-G drop impact packet triggers Game Inventory integration (Rule 232/233)."""
        import game_inventory_loop
        inv = game_inventory_loop.MatrixGameInventory()
        # Ensure we have an item on person to drop
        inv.pickup_item("comms_phone", target_reach="on_person", new_label="Left Pocket")
        
        # Simulate high-G impact
        res = esp32_spatial_receiver.simulate_esp32_packet(
            static_ip="192.168.1.150",
            pos_x=0.42, pos_y=0.88, pos_z=0.08,
            impact=True
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["telemetry"]["impact_detected"])

        # Check inventory summary to see dropped item
        audit = inv.get_inventory_summary()
        self.assertGreaterEqual(audit["dropped_count"], 1)

    def test_langchain_tools(self):
        """Test LangChain StructuredTools for Rule 233."""
        self.assertEqual(len(esp32_spatial_receiver.ESP32_SPATIAL_TOOLS), 4)

        # 1. get status tool
        raw_st = esp32_spatial_receiver.get_spatial_tracking_status_tool.invoke({})
        st = json.loads(raw_st)
        self.assertTrue(st["ok"])
        self.assertEqual(st["rule"], 233)

        # 2. simulate tool
        raw_sim = esp32_spatial_receiver.simulate_esp32_spatial_packet_tool.invoke({
            "pos_x": 0.33,
            "pos_y": 0.44,
            "pos_z": 0.55,
            "motion_state": "CARRIED"
        })
        sim_data = json.loads(raw_sim)
        self.assertTrue(sim_data["ok"])
        self.assertEqual(sim_data["telemetry"]["position"]["x"], 0.33)

        # 3. calibrate tool
        raw_cal = esp32_spatial_receiver.calibrate_spatial_tracker_tool.invoke({
            "zero_position": True,
            "zero_orientation": True
        })
        cal_data = json.loads(raw_cal)
        self.assertTrue(cal_data["ok"])

        # 4. Check catalog registration
        catalog = langchain_separation.list_available_analysis_tools()
        rule233_tools = [t for t in catalog if t["rule"] == 233]
        self.assertEqual(len(rule233_tools), 4)
        for t in rule233_tools:
            self.assertEqual(t["category"], "esp32_spatial_tracking")

    def test_web_billboard_spatial_endpoints(self):
        """Test Web Billboard REST endpoints for spatial tracking."""
        # 1. GET /api/spatial/status
        res_st = self.client.get("/api/spatial/status")
        self.assertEqual(res_st.status_code, 200)
        data_st = res_st.get_json()
        self.assertTrue(data_st["ok"])
        self.assertEqual(data_st["rule"], 233)

        # 2. POST /api/spatial/simulate
        res_sim = self.client.post("/api/spatial/simulate", json={
            "static_ip": "192.168.1.150",
            "pos_x": 1.1,
            "pos_y": 2.2,
            "pos_z": 0.9,
            "motion_state": "MOVING"
        })
        self.assertEqual(res_sim.status_code, 200)
        data_sim = res_sim.get_json()
        self.assertTrue(data_sim["ok"])
        self.assertEqual(data_sim["telemetry"]["position"]["x"], 1.1)

        # 3. POST /api/spatial/calibrate
        res_cal = self.client.post("/api/spatial/calibrate", json={
            "zero_position": True,
            "zero_orientation": True
        })
        self.assertEqual(res_cal.status_code, 200)
        self.assertTrue(res_cal.get_json()["ok"])

        # 4. GET /api/summary includes /api/spatial endpoints
        res_sum = self.client.get("/api/summary")
        self.assertEqual(res_sum.status_code, 200)
        sum_data = res_sum.get_json()
        self.assertIn("/api/spatial/status", sum_data["endpoints"])
        self.assertIn("/api/spatial/simulate", sum_data["endpoints"])


if __name__ == "__main__":
    unittest.main()
