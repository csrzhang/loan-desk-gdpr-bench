"""Read-only projections of frozen cases and recorded model findings."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AUDIT = ROOT.parent
sys.path.append(str(AUDIT))
from evidence import screen, source_lines
PRI = AUDIT / "baselines/priagent"
RUNS = ROOT / ".local/runs"
SNAPS = ("base", "v01", "v02", "v03", "v04")
FILES = ("app.py", "store.py", "views.py", "style.css")
STAGES = ("policy_scan", "locus_finder", "control_verifier", "counterexample_review", "regulatory_arbiter")
MODELS = ("deepseek-flash", "deepseek-v4-pro")
APP = "Loan Desk"
LAW = "GDPR"
BASELINE = "PriAgent regulatory-v2"


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False))
    temporary.replace(path)


RULES = {rule["obligation_id"]: rule for rule in read(AUDIT / "scope.json")["obligations"]}
REQUIREMENTS = read(PRI / "requirements-by-rule.json")


def recording_dir(key):
    if key == "flash-01":
        return PRI / "runs/flash-01"
    if re.fullmatch("[0-9a-f]{16}", key):
        return RUNS / key
    raise ValueError("Unknown recording")


def catalog():
    saved = []
    history = []
    references = {}
    for snap in SNAPS:
        records = read(AUDIT / "reference" / snap / "audit.json")["records"]
        references[snap] = {r["obligation_id"]: r["verdict"] for r in records}
    archives = [PRI / "runs/flash-01", *RUNS.glob("*/")]
    for folder in archives:
        manifest = folder / "manifest.json"
        if not manifest.is_file():
            continue
        meta = read(manifest)
        if "snapshot" in meta:
            plan = [(meta["snapshot"], oid) for oid in meta["obligations"]]
        else:
            plan = [key.split("-", 1) for key in meta["cases"]]
        findings = []
        for file in sorted(folder.glob("cases/*/prediction.json")):
            snapshot, oid = file.parent.name.split("-")
            saved.append(dict(archive=folder.name, model=meta["model"], snapshot=snapshot, oid=oid))
            findings.append(dict(snapshot=snapshot, oid=oid, verdict=read(file)["verdict"],
                                 reference=references[snapshot][oid]))
        state_path = folder / "state.json"
        state = read(state_path) if state_path.is_file() else {}
        status = state.get("status") or ("complete" if len(findings) == len(plan) else "partial")
        history.append(dict(id=folder.name, created=meta.get("created"), model=meta["model"],
                            app=meta.get("app", APP), law=meta.get("law", LAW), baseline=meta.get("baseline", BASELINE),
                            status=status, plan=[dict(snapshot=s, oid=o) for s, o in plan], findings=findings))
    history.sort(key=lambda run: run["created"] or 0, reverse=True)
    return dict(rules=list(RULES.values()), snapshots=list(SNAPS), recordings=saved, runs=history, references=references)


def stage_note(stage, output):
    if stage == "policy_scan":
        return f"{len(output['required_controls'])} required controls identified"
    if stage == "locus_finder":
        return f"{len(output['loci'])} source ranges located"
    if stage == "control_verifier":
        return f"{len(output['checks'])} control checks recorded"
    if stage == "counterexample_review":
        return "Counterexample review completed"
    if stage == "anchor_repair":
        return "Source coordinates rechecked"
    return "Decision and evidence saved"


def report(snapshot, oid, archive):
    if snapshot not in SNAPS or oid not in RULES:
        raise ValueError("Unknown case")
    timing = []
    records = read(AUDIT / "reference" / snapshot / "audit.json")["records"]
    reference = next(record for record in records if record["obligation_id"] == oid)
    if archive == "reference":
        result = {key: reference[key] for key in ("verdict", "evidence", "explanation")}
        result.update(observed=reference["runtime_evidence"]["observed"], model=None)
    else:
        folder = recording_dir(archive)
        case = folder / "cases" / f"{snapshot}-{oid}"
        result = read(case / "prediction.json")
        meta = read(folder / "manifest.json")
        result.update(model=meta["model"], baseline=meta.get("baseline", BASELINE), created=meta.get("created"),
                      reference_verdict=reference["verdict"])
        checked = screen(reference, result, source_lines(AUDIT / "projects" / snapshot))
        result["evidence_check"] = dict(errors=len(checked["citation_errors"]),
                                        covered=len(checked["localized_routes"]), routes=len(checked["route_details"]))
        for stage in (*STAGES, "anchor_repair"):
            receipt_path = case / "stages" / (stage + ".json")
            if receipt_path.is_file():
                receipt = read(receipt_path)
                timing.append(dict(stage=stage, seconds=receipt["seconds"], note=stage_note(stage, receipt["output"])))
    result.update(snapshot=snapshot, rule=RULES[oid], requirement=REQUIREMENTS[oid], archive=archive, stages=timing)
    return result
