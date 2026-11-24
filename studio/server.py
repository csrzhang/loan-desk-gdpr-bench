"""Loopback-only Audit Studio with local playback and opt-in live inference."""
import argparse
import json
import os
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from studio_data import APP, AUDIT, BASELINE, FILES, LAW, MODELS, PRI, ROOT, RULES, RUNS, SNAPS, catalog, read, recording_dir, report, write

lock = threading.Lock()
workers = {}
ASSETS = {"/": ("index.html", "text/html"), "/studio.css": ("studio.css", "text/css"),
          "/presentation.mjs": ("presentation.mjs", "text/javascript"),
          "/studio.js": ("studio.js", "text/javascript")}


class Server(BaseHTTPRequestHandler):
    def send(self, code, body, content_type="application/json"):
        if content_type == "application/json":
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; "
                         "style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def local_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in (f"localhost:{port}", f"127.0.0.1:{port}")

    def do_GET(self):
        if not self.local_host():
            return self.send(403, {"error": "Local requests only."})
        url = urlsplit(self.path)
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ASSETS:
                filename, content_type = ASSETS[url.path]
                return self.send(200, (ROOT / "dist" / filename).read_bytes(), content_type)
            if url.path == "/api/catalog":
                return self.send(200, catalog())
            if url.path == "/api/report":
                return self.send(200, report(query["snapshot"], query["oid"], query["archive"]))
            if url.path == "/api/source" and query["snapshot"] in SNAPS and query["path"] in FILES:
                source = AUDIT / "projects" / query["snapshot"] / query["path"]
                return self.send(200, {"lines": source.read_text().splitlines()})
            if url.path == "/api/status":
                return self.send(200, self.run_status(query["id"]))
            self.send(404, {"error": "Page unavailable."})
        except (ValueError, KeyError, FileNotFoundError, StopIteration):
            self.send(404, {"error": "This report or resource is unavailable."})

    def run_status(self, key):
        state_path = recording_dir(key) / "state.json"
        with lock:
            process = workers.get(key)
            ended = process is None or process.poll() is not None
            state = read(state_path)
            if state["status"] == "running" and ended:
                state.update(status="failed", error="The live worker stopped. Completed reports are in the library.")
        return state

    def do_POST(self):
        if urlsplit(self.path).path != "/api/live":
            return self.send(404, {"error": "Unknown action."})
        origin = "http://" + self.headers.get("Host", "")
        if not self.local_host() or self.headers.get("Origin") != origin or self.headers.get_content_type() != "application/json":
            return self.send(403, {"error": "Start a live run from the local workspace."})
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size < 4096:
                raise ValueError
            body = json.loads(self.rfile.read(size))
            if (body.get("app", APP), body.get("law", LAW), body.get("baseline", BASELINE)) != (APP, LAW, BASELINE):
                raise ValueError
            snapshot, model, ids = body["snapshot"], body["model"], body["obligations"]
            if snapshot not in SNAPS or model not in MODELS:
                raise ValueError
            if not isinstance(ids, list) or not 1 <= len(ids) <= 13 or len(set(ids)) != len(ids) or not all(i in RULES for i in ids):
                raise ValueError
        except (AttributeError, KeyError, ValueError, TypeError):
            return self.send(400, {"error": "Invalid audit selection."})
        interpreter = PRI / ".venv/bin/python"
        if not interpreter.is_file():
            return self.send(503, {"error": "Set up the PriAgent virtual environment to run live inference."})
        with lock:
            if any(p.poll() is None for p in workers.values()):
                return self.send(409, {"error": "A live run is already in progress."})
            workers.clear()
            key = secrets.token_hex(8)
            folder = RUNS / key
            write(folder / "manifest.json", dict(app=APP, law=LAW, baseline=BASELINE, model=model,
                                                 snapshot=snapshot, obligations=ids, created=time.time()))
            state = dict(id=key, status="running", completed=[], current=ids[0], events=[])
            write(folder / "state.json", state)
            env = {**os.environ, "LLM_MODEL": model}
            try:
                workers[key] = subprocess.Popen([str(interpreter), "-B", str(ROOT / "live_worker.py"), key],
                                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                state.update(status="failed", error="The live inference worker could not start.")
                write(folder / "state.json", state)
                return self.send(503, {"error": state["error"]})
        self.send(201, {"id": key})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Server) as server:
        print(f"Audit Studio at http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            for child in workers.values():
                if child.poll() is None:
                    child.terminate()
