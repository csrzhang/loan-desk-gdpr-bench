"""Publish progress around the existing PriAgent graph in an isolated process."""
import sys
import time

from studio_data import AUDIT, PRI, REQUIREMENTS, RULES, RUNS, read, stage_note, write

sys.path.insert(0, str(PRI))
import run as baseline


def work(folder):
    manifest = read(folder / "manifest.json")
    state = read(folder / "state.json")
    original_agents = baseline.Agents

    def publish():
        write(folder / "state.json", state)

    def event(stage, status, note, **fields):
        state["events"].append(dict(oid=state["current"], stage=stage, status=status,
                                    note=note, at=time.time(), **fields))
        publish()

    class ObservableAgents(original_agents):
        def call(self, stage, schema, context):
            event(stage, "running", "Waiting for the model")
            started = time.monotonic()
            output = super().call(stage, schema, context)
            event(stage, "done", stage_note(stage, output.model_dump()),
                  seconds=round(time.monotonic() - started, 3))
            return output

    try:
        state["credential_source"] = baseline.config.LLM_KEY_SOURCE
        if not baseline.config.LLM_API_KEY:
            state.update(status="failed", error=f"No DeepSeek API key was found in {baseline.config.LLM_KEY_SOURCE}.")
            return
        baseline.Agents = ObservableAgents
        scope = read(AUDIT / "scope.json")
        snapshot = manifest["snapshot"]
        identity = baseline.fingerprint(manifest)
        for oid in manifest["obligations"]:
            state["current"] = oid
            publish()
            case = baseline.packet(snapshot, RULES[oid], scope, REQUIREMENTS[oid])
            baseline.evaluate((snapshot, oid, case), folder, identity)
            state["completed"].append(oid)
            publish()
        state["status"] = "complete"
    except Exception as exc:
        errors = {401: "DeepSeek rejected the API key.",
                  402: f"DeepSeek reported insufficient balance (HTTP 402) for the key from {baseline.config.LLM_KEY_SOURCE}.",
                  429: "DeepSeek rate limit reached."}
        message = errors.get(getattr(exc, "status_code", None),
                             f"Live audit stopped ({type(exc).__name__}).")
        state.update(status="failed", error=message)
    finally:
        baseline.Agents = original_agents
        publish()


if __name__ == "__main__":
    work(RUNS / sys.argv[1])
