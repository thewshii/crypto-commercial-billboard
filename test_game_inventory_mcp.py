"""
test_game_inventory_mcp.py - Unit test suite for Rule 232:
Game Inventory Loop Model Context Protocol (MCP), LangChain Tools, and Web Billboard Interface.
"""

import json
import os
import shutil
import tempfile
import unittest

import game_inventory_loop
import langchain_separation
import web_billboard


class TestGameInventoryMCP(unittest.TestCase):

    def setUp(self):
        # Create a temporary state file for isolated testing
        self.test_dir = tempfile.mkdtemp()
        self.test_state_file = os.path.join(self.test_dir, "test_inventory_state.json")
        self.inv = game_inventory_loop.MatrixGameInventory(state_file=self.test_state_file)
        self.inv.save_state()
        self.server = game_inventory_loop.GameInventoryMCPServer(inv=self.inv)
        
        # Configure test Flask client
        web_billboard.app.config["TESTING"] = True
        self.client = web_billboard.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_inventory_summary_and_audit(self):
        """Test getting inventory summary and rule 232 metadata."""
        summary = self.inv.get_inventory_summary()
        self.assertEqual(summary["rule"], 232)
        self.assertGreaterEqual(summary["on_person_count"], 1)
        self.assertGreaterEqual(summary["within_reach_count"], 1)
        self.assertEqual(summary["dropped_count"], 0)
        self.assertIn("labels_registry", summary)

    def test_drop_audit_and_dialogue(self):
        """Test dropping an item runs audit, dialogue, and persistent labeling."""
        res = self.inv.trigger_drop(
            "comms_phone",
            landing_description="Hardwood floor by desk corner",
            dialogue_notes=["Agent Alpha: Phone fell.", "Agent Beta: Verified location."],
            final_label="Dropped: Near desk corner"
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["dropped_item"]["id"], "comms_phone")
        self.assertEqual(res["assigned_label"], "Dropped: Near desk corner")
        self.assertEqual(len(res["discussion"]), 2)
        self.assertEqual(res["inventory_audit"]["dropped_count"], 1)

        # Check pickup
        pickup_res = self.inv.pickup_item("comms_phone", target_reach="on_person", new_label="Left Coat Pocket")
        self.assertTrue(pickup_res["ok"])
        self.assertEqual(pickup_res["moved_to"], "on_person")
        self.assertEqual(pickup_res["new_label"], "Left Coat Pocket")
        self.assertEqual(pickup_res["inventory_audit"]["dropped_count"], 0)

    def test_deliberate_label(self):
        """Test relabeling an item updates state and registry."""
        res = self.inv.deliberate_label("water_flask", "Center Desk Coaster", discussion_text="Placed on coaster")
        self.assertTrue(res["ok"])
        self.assertEqual(res["new_label"], "Center Desk Coaster")
        item = self.inv.find_item("water_flask")
        self.assertIsNotNone(item)
        self.assertEqual(item["item"]["label"], "Center Desk Coaster")

    def test_langchain_structured_tools(self):
        """Test all 6 LangChain StructuredTools for inventory loop."""
        self.assertEqual(len(game_inventory_loop.GAME_INVENTORY_TOOLS), 6)

        # 1. audit tool
        audit_raw = game_inventory_loop.audit_game_inventory_tool.invoke({"include_discussions": True})
        audit = json.loads(audit_raw)
        self.assertIn("on_person", audit)
        self.assertEqual(audit.get("rule"), 232)

        # 2. find tool
        find_raw = game_inventory_loop.find_game_item_tool.invoke({"query": "access_card"})
        find_data = json.loads(find_raw)
        self.assertTrue(find_data["ok"])
        self.assertEqual(find_data["match"]["item"]["id"], "access_card")

        # 3. drop tool
        drop_raw = game_inventory_loop.drop_game_item_tool.invoke({
            "item_id": "matrix_keyring",
            "landing_description": "Carpet near radiator",
            "final_label": "Dropped: Radiator floor"
        })
        drop_data = json.loads(drop_raw)
        self.assertTrue(drop_data["ok"])

        # 4. pickup tool
        pick_raw = game_inventory_loop.pickup_game_item_tool.invoke({
            "item_id": "matrix_keyring",
            "target_reach": "within_reach",
            "new_label": "Radiator Shelf"
        })
        pick_data = json.loads(pick_raw)
        self.assertTrue(pick_data["ok"])

        # 5. label tool
        lbl_raw = game_inventory_loop.label_game_item_tool.invoke({
            "item_id": "matrix_keyring",
            "new_label": "Metal Hook near door"
        })
        lbl_data = json.loads(lbl_raw)
        self.assertTrue(lbl_data["ok"])

        # 6. loop tick tool
        tick_raw = game_inventory_loop.inventory_loop_tick_tool.invoke({"action": "audit"})
        tick_data = json.loads(tick_raw)
        self.assertTrue(tick_data["ok"])
        self.assertEqual(tick_data["tick_action"], "audit")

    def test_langchain_separation_network_catalog(self):
        """Test that Rule 232 tools are present in LangChain tools catalog."""
        catalog = langchain_separation.list_available_analysis_tools()
        rule232_tools = [t for t in catalog if t["rule"] == 232]
        self.assertEqual(len(rule232_tools), 6)
        for t in rule232_tools:
            self.assertEqual(t["category"], "game_inventory_mcp")

        # Test execution through langchain_separation dispatcher
        res = langchain_separation.execute_langchain_tool("audit_game_inventory_tool", {})
        self.assertTrue(res["ok"])
        self.assertIn("on_person", res["result"])

    def test_mcp_jsonrpc_protocol(self):
        """Test Model Context Protocol (MCP) JSON-RPC 2.0 handshake and methods."""
        # 1. initialize
        init_req = {"jsonrpc": "2.0", "id": 101, "method": "initialize", "params": {}}
        init_res = self.server.handle_jsonrpc(init_req)
        self.assertEqual(init_res["jsonrpc"], "2.0")
        self.assertEqual(init_res["id"], 101)
        self.assertEqual(init_res["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(init_res["result"]["serverInfo"]["name"], "game-inventory-mcp")

        # 2. ping
        ping_res = self.server.handle_jsonrpc({"jsonrpc": "2.0", "id": 102, "method": "ping"})
        self.assertEqual(ping_res["result"], {})

        # 3. tools/list
        tools_res = self.server.handle_jsonrpc({"jsonrpc": "2.0", "id": 103, "method": "tools/list"})
        tools = tools_res["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("game_inventory_audit", tool_names)
        self.assertIn("game_inventory_drop", tool_names)
        self.assertIn("game_inventory_pickup", tool_names)
        self.assertIn("game_inventory_label", tool_names)
        self.assertIn("game_inventory_find", tool_names)
        self.assertIn("game_inventory_loop_tick", tool_names)

        # 4. tools/call
        call_res = self.server.handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 104,
            "method": "tools/call",
            "params": {
                "name": "game_inventory_audit",
                "arguments": {"include_discussions": True}
            }
        })
        self.assertFalse(call_res["result"]["isError"])
        content_text = call_res["result"]["content"][0]["text"]
        self.assertIn("on_person", content_text)

        # 5. resources/list and resources/read
        res_list = self.server.handle_jsonrpc({"jsonrpc": "2.0", "id": 105, "method": "resources/list"})
        uris = [r["uri"] for r in res_list["result"]["resources"]]
        self.assertIn("inventory://state", uris)
        self.assertIn("inventory://audit", uris)

        res_read = self.server.handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 106,
            "method": "resources/read",
            "params": {"uri": "inventory://state"}
        })
        self.assertIn("on_person", res_read["result"]["contents"][0]["text"])

        # 6. prompts/list and prompts/get
        prompts_res = self.server.handle_jsonrpc({"jsonrpc": "2.0", "id": 107, "method": "prompts/list"})
        prompt_names = [p["name"] for p in prompts_res["result"]["prompts"]]
        self.assertIn("inventory_audit_report", prompt_names)
        self.assertIn("inventory_drop_analysis", prompt_names)

        prompt_get = self.server.handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 108,
            "method": "prompts/get",
            "params": {"name": "inventory_audit_report"}
        })
        self.assertIn("messages", prompt_get["result"])

        # 7. notifications/initialized (returns None)
        notif_res = self.server.handle_jsonrpc({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })
        self.assertIsNone(notif_res)

        # 8. invalid method error
        err_res = self.server.handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 109,
            "method": "unknown_method_xyz"
        })
        self.assertEqual(err_res["error"]["code"], -32601)

    def test_web_billboard_mcp_endpoints(self):
        """Test Web Billboard HTTP endpoints for MCP gateway and inventory management."""
        # 1. POST /api/mcp (JSON-RPC)
        rpc_payload = {
            "jsonrpc": "2.0",
            "id": 201,
            "method": "tools/list",
            "params": {}
        }
        res = self.client.post("/api/mcp", json=rpc_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["id"], 201)
        self.assertIn("tools", data["result"])

        # 2. GET /api/mcp/inventory/status
        res_status = self.client.get("/api/mcp/inventory/status")
        self.assertEqual(res_status.status_code, 200)
        st_data = res_status.get_json()
        self.assertTrue(st_data["ok"])
        self.assertEqual(st_data["mcp_server"], "game-inventory-mcp")
        self.assertEqual(st_data["protocol_version"], "2024-11-05")
        self.assertEqual(st_data["rule"], 232)

        # 3. POST /api/mcp/inventory/tick
        res_tick = self.client.post("/api/mcp/inventory/tick", json={"action": "audit"})
        self.assertEqual(res_tick.status_code, 200)
        tick_data = res_tick.get_json()
        self.assertTrue(tick_data["ok"])

        # 4. GET /api/mcp/sse
        res_sse = self.client.get("/api/mcp/sse")
        self.assertEqual(res_sse.status_code, 200)
        self.assertIn("text/event-stream", res_sse.content_type)
        self.assertIn(b"event: endpoint", res_sse.data)

        # 5. POST /api/mcp/messages
        res_msg = self.client.post("/api/mcp/messages", json={
            "jsonrpc": "2.0",
            "id": 202,
            "method": "ping"
        })
        self.assertEqual(res_msg.status_code, 200)
        msg_data = res_msg.get_json()
        self.assertEqual(msg_data["id"], 202)

        # 6. GET /api/summary includes /api/mcp
        res_sum = self.client.get("/api/summary")
        self.assertEqual(res_sum.status_code, 200)
        sum_data = res_sum.get_json()
        self.assertIn("/api/mcp", sum_data["endpoints"])
        self.assertIn("/api/mcp/inventory/status", sum_data["endpoints"])


if __name__ == "__main__":
    unittest.main()
