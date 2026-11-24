# Loan Desk · PriAgent regulatory-v2

**Incomplete run.** 1 of 65 cases returned a prediction. Missing cases are excluded from agreement and evidence screening. See [execution notes](../../README.md#verification-and-result-boundaries).

DeepSeek model requested: `deepseek-flash`. Four production files per snapshot; one scoped GDPR case per prediction.

| Project | Valid / scheduled | Correct verdict | Violations found / reference violations in completed cases | False alarms | Complete registered evidence route |
|---|---:|---:|---:|---:|---:|
| base | 1 / 13 | 1 | 0 / 0 | 0 | 1 |
| v01 | 0 / 13 | 0 | 0 / 0 | 0 | 0 |
| v02 | 0 / 13 | 0 | 0 / 0 | 0 | 0 |
| v03 | 0 / 13 | 0 | 0 / 0 | 0 | 0 |
| v04 | 0 / 13 | 0 | 0 / 0 | 0 | 0 |
| Total | 1 / 65 | 1 | 0 / 0 | 0 | 1 |

## Verdict disagreements

All completed verdicts matched their references.

## Coverage and interpretation

1 predictions, 64 missing. Completed stages recorded 20 model invocations, 208,872 input tokens and 16,725 output tokens. SDK-level HTTP retries are not counted as separate model invocations.

Exact quotations are materialized from model-selected coordinates. The evidence column measures full location coverage of at least one registered route. It is a screening measure; semantic sufficiency, alternative routes, and relevance require review. Each project is a derivative of one Loan Desk application.

[Predictions](predictions.jsonl) · [Per-case evidence screening](evidence-screen.jsonl) · [Run configuration and counts](summary.json)
