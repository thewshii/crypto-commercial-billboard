"""
test_rtl8812au_usb_controller.py - Unit test suite for Rule 235:
Realtek RTL8812AU Userspace USB Wi-Fi Controller, Endpoints, and LangChain Tools.
"""

import unittest
import json
import rtl8812au_usb_controller
import langchain_separation
import web_billboard


class TestRTL8812AUUsbController(unittest.TestCase):
    """Test suite for RTL8812AU USB Controller."""

    def setUp(self):
        self.app = web_billboard.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_controller_initialization_and_status(self):
        """Test controller creation and status dictionary schema."""
        ctrl = rtl8812au_usb_controller.RTL8812AUController(fd=None)
        st = ctrl.get_status()
        self.assertTrue(st["ok"])
        self.assertEqual(st["device"]["chipset"], "Realtek RTL8812AU")
        self.assertEqual(st["device"]["vid"], "0x0bda")
        self.assertEqual(st["device"]["pid"], "0x8812")
        self.assertIn("endpoints", st)
        self.assertEqual(st["endpoints"]["bulk_rx"], "0x81")
        self.assertEqual(st["endpoints"]["bulk_tx_norm"], "0x03")

    def test_module_status_function(self):
        """Test get_rtl8812au_usb_status function."""
        status = rtl8812au_usb_controller.get_rtl8812au_usb_status()
        self.assertTrue(status["ok"])
        self.assertEqual(status["rule"], 235)
        self.assertEqual(status["device"]["chipset"], "Realtek RTL8812AU")

    def test_langchain_tools_and_catalog(self):
        """Test LangChain StructuredTools for Rule 235."""
        self.assertEqual(len(rtl8812au_usb_controller.RTL8812AU_USB_TOOLS), 3)

        # 1. get status tool
        raw_st = rtl8812au_usb_controller.get_rtl8812au_usb_status_tool.invoke({})
        st = json.loads(raw_st)
        self.assertTrue(st["ok"])
        self.assertEqual(st["rule"], 235)

        # 2. read register tool
        raw_reg = rtl8812au_usb_controller.read_rtl8812au_register_tool.invoke({"reg_hex": "0x00F0", "length": 4})
        reg_data = json.loads(raw_reg)
        self.assertTrue(reg_data["ok"])
        self.assertEqual(reg_data["rule"], 235)

        # 3. capture packets tool
        raw_cap = rtl8812au_usb_controller.capture_rtl8812au_packets_tool.invoke({"duration_sec": 0.1, "max_packets": 5})
        cap_data = json.loads(raw_cap)
        self.assertTrue(cap_data["ok"])
        self.assertEqual(cap_data["rule"], 235)

        # 4. Catalog verification in langchain_separation
        catalog = langchain_separation.list_available_analysis_tools()
        rule235_tools = [t for t in catalog if t["rule"] == 235]
        self.assertEqual(len(rule235_tools), 3)
        for t in rule235_tools:
            self.assertEqual(t["category"], "rtl8812au_usb_controller")

    def test_web_billboard_endpoints(self):
        """Test Web Billboard REST API endpoints for RTL8812AU controller."""
        # 1. GET /api/usb/wifi/status
        res_st = self.client.get("/api/usb/wifi/status")
        self.assertEqual(res_st.status_code, 200)
        data_st = res_st.get_json()
        self.assertTrue(data_st["ok"])
        self.assertEqual(data_st["rule"], 235)
        self.assertEqual(data_st["device"]["chipset"], "Realtek RTL8812AU")

        # 2. GET /api/usb/wifi/capture
        res_cap = self.client.get("/api/usb/wifi/capture?duration=0.1")
        self.assertEqual(res_cap.status_code, 200)
        data_cap = res_cap.get_json()
        self.assertTrue(data_cap["ok"])
        self.assertEqual(data_cap["rule"], 235)

        # 3. GET /api/summary includes /api/usb/wifi/status
        res_sum = self.client.get("/api/summary")
        self.assertEqual(res_sum.status_code, 200)
        sum_data = res_sum.get_json()
        self.assertIn("/api/usb/wifi/status", sum_data["endpoints"])
        self.assertIn("/api/usb/wifi/capture", sum_data["endpoints"])


if __name__ == "__main__":
    unittest.main()
