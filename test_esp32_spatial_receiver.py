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
        """Test LangChain StructuredTools for Rule 233 & Rule 234."""
        self.assertEqual(len(esp32_spatial_receiver.ESP32_SPATIAL_TOOLS), 6)

        # 1. get status tool (Rule 233)
        raw_st = esp32_spatial_receiver.get_spatial_tracking_status_tool.invoke({})
        st = json.loads(raw_st)
        self.assertTrue(st["ok"])
        self.assertEqual(st["rule"], 233)

        # 2. simulate tool (Rule 233)
        raw_sim = esp32_spatial_receiver.simulate_esp32_spatial_packet_tool.invoke({
            "pos_x": 0.33,
            "pos_y": 0.44,
            "pos_z": 0.55,
            "motion_state": "CARRIED"
        })
        sim_data = json.loads(raw_sim)
        self.assertTrue(sim_data["ok"])
        self.assertEqual(sim_data["telemetry"]["position"]["x"], 0.33)

        # 3. calibrate tool (Rule 233)
        raw_cal = esp32_spatial_receiver.calibrate_spatial_tracker_tool.invoke({
            "zero_position": True,
            "zero_orientation": True
        })
        cal_data = json.loads(raw_cal)
        self.assertTrue(cal_data["ok"])

        # 4. get wifi ack stream tool (Rule 234)
        raw_ack = esp32_spatial_receiver.get_wifi_ack_stream_tool.invoke({})
        ack_data = json.loads(raw_ack)
        self.assertTrue(ack_data["ok"])
        self.assertEqual(ack_data["rule"], 234)
        self.assertIn("wifi_ack_stream", ack_data)

        # 5. get ar video status tool (Rule 234)
        raw_vid = esp32_spatial_receiver.get_ar_video_stream_status_tool.invoke({})
        vid_data = json.loads(raw_vid)
        self.assertTrue(vid_data["ok"])
        self.assertEqual(vid_data["rule"], 234)
        self.assertEqual(vid_data["color_scheme"]["primary_yellow"], "#ffdd00")

        # 6. Check catalog registration
        catalog = langchain_separation.list_available_analysis_tools()
        rule233_tools = [t for t in catalog if t["rule"] == 233]
        self.assertEqual(len(rule233_tools), 4)
        rule234_tools = [t for t in catalog if t["rule"] == 234]
        self.assertEqual(len(rule234_tools), 2)
        for t in rule234_tools:
            self.assertEqual(t["category"], "wifi_ack_ar_streaming")

    def test_wifi_ack_stream_and_video_renderer(self):
        """Test Rule 234 Wi-Fi ACK stream processing and yellow AR video renderer."""
        # 1. Simulate packet with wifi_ack payload
        res = esp32_spatial_receiver.ingest_spatial_packet({
            "static_ip": "192.168.1.150",
            "pos_x": 0.8,
            "pos_y": 1.2,
            "pos_z": 0.95,
            "motion_state": "MOVING",
            "wifi_ack": {
                "ack_seq": 1042,
                "rssi_dbm": -48,
                "delta_us": 195,
                "channel": 6,
                "rate_mbps": 54.0,
                "status": "ACK_CONFIRMED"
            }
        })
        self.assertTrue(res["ok"])

        # 2. Verify Wi-Fi ACK stream
        ack_stream = esp32_spatial_receiver.get_wifi_ack_stream()
        self.assertTrue(ack_stream["ok"])
        self.assertEqual(ack_stream["rule"], 234)
        was = ack_stream["wifi_ack_stream"]
        self.assertEqual(was["last_ack_seq"], 1042)
        self.assertEqual(was["last_rssi_dbm"], -48)
        self.assertEqual(was["last_delta_us"], 195)
        self.assertGreater(was["estimated_distance_m"], 0.0)

        # 3. Test AR Video Renderer (PIL MJPEG Frame)
        renderer = esp32_spatial_receiver.ARVideoRenderer(width=320, height=240)
        jpeg_bytes = renderer.render_ar_frame_jpeg(quality=70)
        self.assertTrue(jpeg_bytes.startswith(b"\xff\xd8\xff"))  # JPEG SOI magic bytes
        self.assertGreater(len(jpeg_bytes), 1000)

        # 4. Verify video stream status and yellow palette
        vid_status = esp32_spatial_receiver.get_ar_video_stream_status()
        self.assertTrue(vid_status["ok"])
        palette = vid_status["color_scheme"]
        self.assertEqual(palette["primary_yellow"], "#ffdd00")
        self.assertEqual(palette["highlight_yellow"], "#ffee55")
        self.assertEqual(palette["amber_warning"], "#ffaa00")
        self.assertEqual(palette["obsidian_backdrop"], "#0b0902")
        self.assertEqual(palette["hazard_impact"], "#ff003c")

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
        self.assertIn("/api/spatial/video_feed", sum_data["endpoints"])
        self.assertIn("/api/spatial/acks", sum_data["endpoints"])

        # 5. GET /api/spatial/acks (Rule 234)
        res_acks = self.client.get("/api/spatial/acks")
        self.assertEqual(res_acks.status_code, 200)
        self.assertTrue(res_acks.get_json()["ok"])

        # 6. GET /api/spatial/video_status (Rule 234)
        res_vst = self.client.get("/api/spatial/video_status")
        self.assertEqual(res_vst.status_code, 200)
        self.assertTrue(res_vst.get_json()["ok"])

        # 7. GET /spatial/ar and /ar (Rule 234 Mobile Viewing Interface)
        res_ar = self.client.get("/spatial/ar")
        self.assertEqual(res_ar.status_code, 200)
        self.assertIn(b"YELLOW AR SCHEME", res_ar.data)
        self.assertIn(b"--ar-primary", res_ar.data)


if __name__ == "__main__":
    unittest.main()
