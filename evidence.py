"""Screen a Loan Desk prediction against previously reviewed source routes (Python 3.9+)."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = ('app.py', 'store.py', 'views.py', 'style.css')
VERDICTS = ('SUPPORTED', 'CONTRADICTED', 'INSUFFICIENT', 'NOT_APPLICABLE')


def source_lines(project):
    return {name: (project/name).read_text().splitlines() for name in SOURCES}


def location(anchor, sources, require_quote=False):
    """Require allowlisted, in-bounds ranges. Preserve exact indentation and line text."""
    if not isinstance(anchor, dict):
        raise ValueError('Expected an evidence object')
    path = anchor.get('path')
    a, b = anchor.get('start_line'), anchor.get('end_line')
    if not isinstance(path, str) or path not in sources or type(a) is not int or type(b) is not int:
        raise ValueError('Invalid file or line number')
    if not 1 <= a <= b <= len(sources[path]):
        raise ValueError('Source range is out of bounds')
    if require_quote and anchor.get('quote') != '\n'.join(sources[path][a-1:b]):
        raise ValueError('Quoted text differs from the frozen snapshot')
    return {(path, i) for i in range(a, b+1)}


def route_requirements(row, sources):
    routes = {}
    for route in row['evidence_review']['routes']:
        facts = []
        for fact in route['facts']:
            if not fact['claim'].strip() or not fact['anchors']:
                raise ValueError('Empty fact or source chain')
            required = set().union(*(location(a, sources) for a in fact['anchors']))
            facts.append((fact['claim'], required))
        if not facts or route['name'] in routes:
            raise ValueError('Empty or duplicate route')
        routes[route['name']] = facts
    return routes


def check_reference(row, sources):
    """Deletion check across all registered routes; semantic sufficiency is reviewed separately."""
    routes = route_requirements(row, sources)
    complete = [set().union(*(lines for _, lines in facts)) for facts in routes.values()]
    primary = row['evidence_review']['routes'][0]['facts']
    anchors = [a for fact in primary for a in fact['anchors']]
    canonical = [{k: a[k] for k in ('path','start_line','end_line')} for a in row['evidence']]
    if canonical != anchors or len(set(map(frozenset, complete))) != len(complete):
        raise ValueError(f"{row['case_id']}: inconsistent canonical or duplicate routes")
    for route in row['evidence_review']['routes']:
        parts = [location(a,sources) for f in route['facts'] for a in f['anchors']]
        for i in range(len(parts)):
            remaining = set().union(*parts[:i], *parts[i+1:])
            if any(chain <= remaining for chain in complete):
                raise ValueError(f"{row['case_id']}: redundant span in {route['name']}")


def screen(row, prediction, sources):
    if prediction.get('case_id') != row['case_id']:
        raise ValueError('Prediction and reference case IDs differ')
    if prediction.get('verdict') not in VERDICTS:
        raise ValueError('Invalid verdict')
    if (not isinstance(prediction.get('evidence'), list)
            or not isinstance(prediction.get('explanation'), str)
            or not prediction['explanation'].strip()):
        raise ValueError('Expected evidence and explanation')
    cited = set()
    errors = []
    overlap = 0
    for number, anchor in enumerate(prediction['evidence'],1):
        try:
            lines = location(anchor, sources, require_quote=True)
            if not isinstance(anchor.get('supports'),str) or not anchor['supports'].strip():
                raise ValueError('Missing claim for citation')
        except ValueError as err:
            errors.append(dict(index=number, issue=str(err)))
            continue
        overlap += len(lines & cited)
        cited |= lines
    if prediction['verdict'] in ('SUPPORTED','CONTRADICTED') and not prediction['evidence']:
        errors.append(dict(issue='Missing source evidence'))
    routes = route_requirements(row,sources)
    matches = []
    details = {}
    mapped = set()
    completed_sizes = []
    for name, facts in routes.items():
        missing = [claim for claim, required in facts if not required <= cited]
        all_lines = set().union(*(required for _, required in facts))
        mapped |= all_lines
        if not missing:
            matches.append(name)
            completed_sizes.append(len(all_lines))
        details[name] = dict(facts_localized=len(facts)-len(missing),facts_total=len(facts),
                             missing_registered_locations_for=missing)
    return dict(case_id=row['case_id'],verdict_correct=prediction['verdict']==row['verdict'],
                citation_errors=errors,localized_routes=matches,route_details=details,
                valid_unique_lines=len(cited),overlapping_valid_lines=overlap,
                valid_lines_outside_registered_routes=len(cited-mapped),
                valid_lines_beyond_shortest_completed_route=len(cited)-min(completed_sizes) if matches else None,
                registered_line_fraction=len(cited & mapped)/len(cited) if cited else None,
                review_status='INVALID_CITATION' if errors else
                ('CHECK_CLAIMS_AND_EXPLANATION' if matches else 'REVIEW_FOR_ALTERNATIVE_OR_MISSING_FACTS'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prediction',type=Path,help='One JSON prediction with case_id, verdict, evidence and explanation')
    args = parser.parse_args()
    prediction = json.loads(args.prediction.read_text())
    version, _, oid = prediction['case_id'].partition('-')
    manifest = json.loads((ROOT/'reference/manifest.json').read_text())
    if version not in manifest['projects']:
        parser.error('Unknown version')
    project = ROOT/'projects'/version
    for path, expected in manifest['projects'][version]['files'].items():
        if hashlib.sha256((project/path).read_bytes()).hexdigest() != expected:
            parser.error('Snapshot digest mismatch')
    rows = json.loads((ROOT/'reference'/version/'audit.json').read_text())['records']
    row = next((r for r in rows if r['obligation_id']==oid), None)
    if row is None:
        parser.error('Unknown obligation')
    print(json.dumps(screen(row,prediction,source_lines(project)),indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
