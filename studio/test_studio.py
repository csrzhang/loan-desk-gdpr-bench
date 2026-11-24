"""Offline contract checks for the UI projections and live-run adapter."""
import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import live_worker
import server
from studio_data import AUDIT, FILES, RULES, SNAPS, STAGES, catalog, read, recording_dir, report, write


class StudioChecks(unittest.TestCase):
    def test_all_reference_reports_bind_to_frozen_source(self):
        for snapshot in SNAPS:
            for oid in RULES:
                with self.subTest(snapshot=snapshot, oid=oid):
                    case = report(snapshot, oid, "reference")
                    self.assertTrue(case["requirement"] and case["explanation"] and case["observed"])
                    for entry in case["evidence"]:
                        self.assertIn(entry["path"], FILES)
                        lines = (AUDIT / "projects" / snapshot / entry["path"]).read_text().splitlines()
                        excerpt = lines[entry["start_line"]-1:entry["end_line"]]
                        self.assertEqual("\n".join(excerpt), entry["quote"])

    def test_saved_and_missing_model_records(self):
        saved = report("base", "GDPR01", "flash-01")
        self.assertEqual(tuple(s["stage"] for s in saved["stages"]), STAGES)
        self.assertEqual(saved["model"], "deepseek-flash")
        self.assertEqual(saved["reference_verdict"], "SUPPORTED")
        self.assertEqual(saved["evidence_check"]["errors"], 0)
        self.assertGreater(saved["evidence_check"]["covered"], 0)
        self.assertNotIn("observed", saved)
        self.assertIn({"snapshot": "base", "oid": "GDPR01", "archive": "flash-01",
                       "model": "deepseek-flash"}, catalog()["recordings"])
        with self.assertRaises(FileNotFoundError):
            report("v03", "GDPR13", "flash-01")

    def test_repeated_runs_keep_separate_results_and_scope(self):
        with tempfile.TemporaryDirectory() as temp, patch("studio_data.RUNS", Path(temp)):
            for time, verdict in [(1, "SUPPORTED"), (2, "INSUFFICIENT")]:
                folder = Path(temp) / f"{time:016x}"
                write(folder / "manifest.json", dict(created=time, snapshot="v04", obligations=["GDPR01","GDPR04"],
                                                     model="deepseek-flash"))
                write(folder / "cases/v04-GDPR01/prediction.json", {"verdict": verdict})
            newer, older, imported = catalog()["runs"]
            self.assertNotEqual(older["id"], newer["id"])
            self.assertEqual(newer["findings"], [dict(snapshot="v04", oid="GDPR01", verdict="INSUFFICIENT",
                                                      reference="SUPPORTED")])
            self.assertEqual(older["findings"][0]["verdict"], "SUPPORTED")
            self.assertEqual((len(newer["plan"]), newer["status"]), (2, "partial"))
            self.assertEqual((len(imported["plan"]), imported["created"]), (65, None))

    def test_worker_replays_saved_provider_outputs_through_real_graph(self):
        archive = recording_dir("flash-01") / "cases/base-GDPR01"

        class RecordedAgents(live_worker.baseline.Agents):
            def call(self, stage, schema, context):
                return schema.model_validate(read(archive / "stages" / (stage + ".json"))["output"])

        with tempfile.TemporaryDirectory() as temp, patch.object(live_worker.baseline, "Agents", RecordedAgents):
            folder = self.prepare_run(temp)
            with patch.object(live_worker.baseline.config, "LLM_API_KEY", "offline-fixture"):
                live_worker.work(folder)
            state = read(folder / "state.json")
            self.assertEqual((state["status"], state["completed"]), ("complete", ["GDPR01"]))
            self.assertEqual([(e["stage"], e["status"]) for e in state["events"]],
                             [(stage, status) for stage in STAGES for status in ("running", "done")])
            self.assertEqual(read(folder / "cases/base-GDPR01/prediction.json"), read(archive / "prediction.json"))

    @staticmethod
    def prepare_run(temp):
        folder = Path(temp)
        write(folder / "manifest.json", {"snapshot": "base", "obligations": ["GDPR01"], "model": "deepseek-flash"})
        write(folder / "state.json", {"status": "running", "events": [], "completed": []})
        return folder

    def test_provider_error_preserves_incomplete_status(self):
        class PaymentError(Exception):
            status_code = 402
        with tempfile.TemporaryDirectory() as temp:
            folder = self.prepare_run(temp)
            with patch.object(live_worker.baseline.config, "LLM_API_KEY", "offline-fixture"), \
                 patch.object(live_worker.baseline.Agents, "call", side_effect=PaymentError):
                live_worker.work(folder)
            state = read(folder / "state.json")
            self.assertEqual(state["status"], "failed")
            self.assertIn("insufficient balance", state["error"])
            self.assertEqual(state["completed"], [])
            self.assertFalse(list(folder.rglob("prediction.json")))

    def test_local_post_passes_selected_model_and_cases(self):
        handler = server.Server.__new__(server.Server)
        handler.path = "/api/live?"
        handler.server = SimpleNamespace(server_port=8770)
        host = "127.0.0.1:8770"
        handler.headers = Message()
        handler.headers["Host"] = host
        handler.headers["Origin"] = "http://" + host
        handler.headers["Content-Type"] = "application/json"
        request = {"model": "deepseek-v4-pro", "snapshot": "v03", "obligations": ["GDPR09", "GDPR13"]}
        body = json.dumps(request).encode()
        handler.headers["Content-Length"] = str(len(body))
        handler.rfile = io.BytesIO(body)
        handler.send = Mock()
        with tempfile.TemporaryDirectory() as tmp, patch.object(server, "RUNS", Path(tmp)), \
             patch.object(server, "workers", {}), patch.object(server.subprocess, "Popen") as spawn:
            handler.do_POST()
            status, result = handler.send.call_args.args
            self.assertEqual(status, 201)
            self.assertEqual(spawn.call_args.kwargs["env"]["LLM_MODEL"], request["model"])
            self.assertEqual(read(Path(tmp) / result["id"] / "manifest.json")["obligations"], request["obligations"])
            for name, preview in [("app", "Retail Rewards"), ("law", "PDPO"), ("model", "anthropic")]:
                body = json.dumps({**request, name: preview}).encode()
                handler.headers.replace_header("Content-Length", str(len(body)))
                handler.rfile = io.BytesIO(body)
                handler.do_POST()
                self.assertEqual(handler.send.call_args.args[0], 400)
            handler.headers.replace_header("Origin", "https://example.org")
            handler.do_POST()
            self.assertEqual(handler.send.call_args.args[0], 403)
            self.assertEqual(spawn.call_count, 1)


if __name__ == "__main__":
    unittest.main()
