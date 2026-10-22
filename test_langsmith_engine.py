"""
test_langsmith_engine.py - Unit test suite for Rule 227 LangSmith Engine,
Evidence Tracing, Issue Diagnosis, and Offline Evaluation Datasets.
"""

import os
import json
import re
import unittest
import langsmith_engine_tools
import langchain_separation
import word_segment


class TestLangSmithEngineSuite(unittest.TestCase):
    def setUp(self):
        # Ensure fresh state or clean run
        pass

    def test_record_and_load_traces(self):
        tr = langsmith_engine_tools.record_trace(
            name="test_probe_tool",
            run_type="tool",
            inputs={"channel": 6, "ssid": "TestAP"},
            outputs={"status": "ok", "rssi_dbm": -45},
            duration_ms=12.5,
            degree=1,
            project_name="crypto-agent"
        )
        self.assertIn("id", tr)
        self.assertEqual(tr["name"], "test_probe_tool")
        self.assertEqual(tr["run_type"], "tool")
        self.assertEqual(tr["degree"], 1)

        recent = langsmith_engine_tools.load_recent_traces(limit=10, project_name="crypto-agent")
        self.assertTrue(any(t["id"] == tr["id"] for t in recent))

    def test_issue_scanner_and_evidence(self):
        # 1. Record a silent tool failure trace
        failed_tr = langsmith_engine_tools.record_trace(
            name="test_failing_sensor_tool",
            run_type="tool",
            inputs={"sensor_id": 99},
            outputs={"ok": False, "error": "Hardware timeout on bus 0"},
            duration_ms=45.0,
            degree=2,
            project_name="crypto-agent"
        )

        # 2. Record a paradox tension trace
        paradox_tr = langsmith_engine_tools.record_trace(
            name="paradox_tension_detector",
            run_type="chain",
            inputs={"input": "Expand to 1000 words while making it zero words"},
            outputs={
                "is_paradoxical": True,
                "opposing_forces": ["expansion vs zero words"],
                "suggested_clarification": "Resolve length constraint."
            },
            duration_ms=8.0,
            degree=1,
            project_name="crypto-agent"
        )

        # Run engine scan
        scan_res = langsmith_engine_tools.scan_traces_for_issues(project_name="crypto-agent", window=50)
        self.assertTrue(scan_res["ok"])
        self.assertGreaterEqual(scan_res["total_issues"], 2)

        # Check silent error issue
        issues = langsmith_engine_tools.list_project_issues(project_name="crypto-agent")
        silent_iss = next((i for i in issues if "test_failing_sensor_tool" in i["issue_id"]), None)
        self.assertIsNotNone(silent_iss)
        self.assertEqual(silent_iss["category"], "SILENT_TOOL_ERROR")
        self.assertEqual(silent_iss["priority"], "high")
        self.assertIn("Hardware timeout", silent_iss["diagnosis"])

        # Check evidence review
        ev_res = langsmith_engine_tools.review_evidence(silent_iss["issue_id"])
        self.assertTrue(ev_res["ok"])
        self.assertGreater(ev_res["evidence_count"], 0)
        self.assertTrue(any(e["trace_id"] == failed_tr["id"] for e in ev_res["evidence"]))

    def test_issue_lifecycle_and_feedback(self):
        # Record a test trace and scan to guarantee an issue exists
        langsmith_engine_tools.record_trace(
            name="lifecycle_test_tool",
            run_type="tool",
            inputs={"op": "test"},
            outputs={"ok": False, "error": "Simulated lifecycle error"},
            project_name="crypto-agent"
        )
        langsmith_engine_tools.scan_traces_for_issues(project_name="crypto-agent")
        issues = langsmith_engine_tools.list_project_issues(project_name="crypto-agent")
        self.assertGreater(len(issues), 0)

        target = issues[0]
        iid = target["issue_id"]

        # Close issue with feedback
        res_close = langsmith_engine_tools.update_issue_status(
            iid, status="closed", reason="Handled by retry wrapper in LangChain"
        )
        self.assertTrue(res_close["ok"])
        self.assertEqual(res_close["status"], "closed")

        # Reopen issue
        res_reopen = langsmith_engine_tools.update_issue_status(
            iid, status="open", priority="high", reason="Failure pattern observed again"
        )
        self.assertTrue(res_reopen["ok"])
        self.assertEqual(res_reopen["status"], "open")
        self.assertEqual(res_reopen["priority"], "high")

    def test_offline_evaluation_dataset_creation(self):
        # Find an issue with evidence
        issues = langsmith_engine_tools.list_project_issues(project_name="crypto-agent")
        target = next((i for i in issues if len(i.get("evidence", [])) > 0), None)
        self.assertIsNotNone(target)

        ev = target["evidence"][0]
        res_ds = langsmith_engine_tools.add_offline_example(
            issue_id=target["issue_id"],
            trace_id=ev["trace_id"],
            ground_truth_output={"expected": "graceful_recovery_mode", "status": "ok"},
            notes="Offline golden benchmark test case",
            dataset_name="agent-eval-golden"
        )
        self.assertTrue(res_ds["ok"])
        self.assertIn("example_id", res_ds)

        datasets = langsmith_engine_tools.list_offline_datasets(dataset_name="agent-eval-golden")
        self.assertTrue(any(d["example_id"] == res_ds["example_id"] for d in datasets))

    def test_langchain_tool_execution_auto_tracing(self):
        # Execute any LangChain tool through execute_langchain_tool
        res = langchain_separation.execute_langchain_tool("measure_agent_separation_tool", {
            "source_agent": "primary_agent",
            "target_agent": "hawkes_process_observer"
        })
        self.assertTrue(res["ok"])

        # Check trace log to verify an execution trace was automatically recorded
        traces = langsmith_engine_tools.load_recent_traces(limit=10, project_name="crypto-agent")
        matching = [t for t in traces if t["name"] == "measure_agent_separation_tool"]
        self.assertGreater(len(matching), 0)
        self.assertEqual(matching[-1]["run_type"], "tool")

    def test_langsmith_structured_tools(self):
        # Test langsmith scan tool invocation
        raw_scan = langsmith_engine_tools.langsmith_scan_issues_tool.invoke({
            "project_name": "crypto-agent",
            "window": 50
        })
        parsed_scan = json.loads(raw_scan)
        self.assertTrue(parsed_scan["ok"])

        # Test langsmith list tool invocation
        raw_list = langsmith_engine_tools.langsmith_list_issues_tool.invoke({
            "project_name": "crypto-agent"
        })
        parsed_list = json.loads(raw_list)
        self.assertIn("issues", parsed_list)

        # Test available analysis tools catalog includes LangSmith Engine Rule 227
        catalog = langchain_separation.list_available_analysis_tools()
        ls_tools = [t for t in catalog if t["rule"] == 227]
        self.assertGreaterEqual(len(ls_tools), 5)
        self.assertEqual(ls_tools[0]["category"], "langsmith_engine")

    def test_contiguous_rules_1_to_227(self):
        with open("word_segment.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = [int(m) for m in re.findall(r'\"(\d+)\.\s', content)]
        self.assertGreaterEqual(max(found), 227)
        missing = [i for i in range(1, max(found) + 1) if i not in found]
        self.assertEqual(missing, [], f"Missing contiguous rules: {missing}")


if __name__ == "__main__":
    unittest.main()
