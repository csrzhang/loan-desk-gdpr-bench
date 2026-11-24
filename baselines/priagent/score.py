"""Score already saved predictions offline. No provider client or credentials are used."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
AUDIT=HERE.parents[1]
sys.path.insert(0,str(AUDIT))
from evidence import screen, source_lines

def read(p):
    return json.loads(p.read_text())
def write(p,obj):
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def jsonl(p,rows):
    p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=HERE/'runs/flash-01')
    parser.add_argument('--out',type=Path,default=HERE/'results/flash-01')
    args=parser.parse_args()
    manifest=read(args.run/'manifest.json')
    refs=read(AUDIT/'reference/manifest.json')['projects']
    predictions=[]
    screens=[]
    aggregates={}
    wrong=[]
    calls=Counter()
    tokens=Counter()
    models=set()
    missing=[]
    for version,ref in refs.items():
        project=AUDIT/'projects'/version
        for file,digest in ref['files'].items():
            if hashlib.sha256((project/file).read_bytes()).hexdigest()!=digest:
                raise ValueError(f'{version}/{file}: source changed')
        sources=source_lines(project)
        counts=Counter()
        for row in read(AUDIT/'reference'/version/'audit.json')['records']:
            case=row['case_id']
            directory=args.run/'cases'/case
            counts['scheduled']+=1
            for stage in sorted((directory/'stages').glob('*.json')):
                receipt=read(stage)
                calls['completed_stages']+=1
                calls['invocations_in_saved_stages']+=receipt['invocations']
                for response in receipt['responses']:
                    model=response.get('model')
                    if model:models.add(model)
                    for key in ('input_tokens','output_tokens'):
                        tokens[key]+=response['usage'].get(key,0)
            if not (directory/'prediction.json').exists():
                missing.append(case)
                continue
            prediction=read(directory/'prediction.json')
            result=screen(row,prediction,sources)
            predictions.append(prediction)
            result.update(reference_verdict=row['verdict'],predicted_verdict=prediction['verdict'])
            screens.append(result)
            counts['valid_predictions']+=int(not result['citation_errors'])
            counts['correct_verdict']+=int(result['verdict_correct'])
            counts['located_known_route']+=int(bool(result['localized_routes']))
            counts['contradictions']+=int(row['verdict']=='CONTRADICTED')
            counts['detected']+=int(row['verdict']==prediction['verdict']=='CONTRADICTED')
            counts['false_alarm']+=int(prediction['verdict']=='CONTRADICTED' and row['verdict']=='SUPPORTED')
            if not result['verdict_correct']:
                wrong.append((case,row['verdict'],prediction['verdict']))
        aggregates[version]=dict(counts)
    if set(manifest['cases'])!={r['case_id'] for r in predictions}|set(missing):
        raise ValueError('Run and audit inventory differ')
    out=args.out
    out.mkdir(parents=True,exist_ok=True)
    jsonl(out/'predictions.jsonl',predictions)
    jsonl(out/'evidence-screen.jsonl',screens)
    total=sum((Counter(v) for v in aggregates.values()),Counter())
    matrix=Counter((s['reference_verdict'],s['predicted_verdict']) for s in screens)
    summary=dict(run_config=manifest,reported_models=sorted(models),calls=dict(calls),tokens=dict(tokens),
                 counts=dict(total),by_project=aggregates,missing=missing,
                 confusion=[dict(reference=a,prediction=b,count=n) for (a,b),n in sorted(matrix.items())])
    write(out/'summary.json',summary)
    lines=['# Loan Desk · PriAgent regulatory-v2', '',
           f"DeepSeek model requested: `{manifest['model']}`. Four production files per snapshot; one scoped GDPR case per prediction.",
           '', '| Project | Valid / scheduled | Correct verdict | Violations found / reference violations in completed cases | False alarms | Complete registered evidence route |',
           '|---|---:|---:|---:|---:|---:|']
    if missing:
        lines[2:2]=[f"**Incomplete run.** {len(predictions)} of {len(manifest['cases'])} cases returned a prediction. Missing cases are excluded from agreement and evidence screening. See [execution notes](../../README.md#verification-and-result-boundaries).", '']
    for version, counts in [*aggregates.items(),('Total',total)]:
        c=Counter(counts)
        lines.append(f"| {version} | {c['valid_predictions']} / {c['scheduled']} | {c['correct_verdict']} | {c['detected']} / {c['contradictions']} | {c['false_alarm']} | {c['located_known_route']} |")
    lines+=['','## Verdict disagreements','']
    lines.extend([f'- {case}: reference {gold}, model {pred}.' for case,gold,pred in wrong] or ['All completed verdicts matched their references.'])
    lines+=['','## Coverage and interpretation','',
            f"{len(predictions)} predictions, {len(missing)} missing. Completed stages recorded {calls['invocations_in_saved_stages']} model invocations, {tokens['input_tokens']:,} input tokens and {tokens['output_tokens']:,} output tokens. SDK-level HTTP retries are not counted as separate model invocations.",
            '', 'Exact quotations are materialized from model-selected coordinates. The evidence column measures full location coverage of at least one registered route. It is a screening measure; semantic sufficiency, alternative routes, and relevance require review. Each project is a derivative of one Loan Desk application.',
            '', '[Predictions](predictions.jsonl) · [Per-case evidence screening](evidence-screen.jsonl) · [Run configuration and counts](summary.json)']
    (out/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(f"{len(predictions)}/65 predictions, {total['correct_verdict']} correct; {len(missing)} missing")
if __name__=='__main__':main()
