# PriAgent regulatory-v2 for Loan Desk

This adaptation audits one frozen source snapshot against one scoped GDPR requirement at a time. Five snapshots and 13 requirements yield 65 possible cases. The archived CLI batch has a [coverage report](results/flash-01/RESULTS.md) and [saved predictions](results/flash-01/predictions.jsonl). Audit Studio also has separate recorded runs.

## Components and provenance

| Component | Source in the reference implementation | Role here |
|---|---|---|
| [regulatory.py](regulatory.py) | agents/regulatory_auditor.py | Five stage prompts, structured checks, four verdicts, numbered source and exact quotations. |
| [graph.py](graph.py) | workflow/regulatory_graph.py and agents/regulatory_compliance_arbiter.py | LangGraph connects obligation interpretation, source localization, control verification, counterexample review and adjudication. A failed anchor check permits one repair preserving the verdict. |
| [llm.py](llm.py) and [config.py](config.py) | llm.py and config.py | DeepSeek's Anthropic-compatible endpoint, constrained tool output, schema validation and parsing fallback. Stage receipts record model response metadata, tokens and duration. |
| [run.py](run.py) and [score.py](score.py) | Loan Desk adapter | Build an isolated input packet, cache stages, write predictions and score them offline. |

The reference PriAgent worktree was at commit `b4b863d022a4226cac2a41292f9d3cba1348b356` during migration. Its regulatory adaptation files were untracked. The run manifest records hashes of the migrated implementation. Cite this method as **PriAgent regulatory-v2 (Loan Desk adaptation)**. The Android taint workflow in the original research has a different input and output contract.

Each stage receives the four complete production files, one rule from [scope.json](../../scope.json), its article, scenario and [technical requirement](requirements-by-rule.json). The sources fit within the model context. Opaque case IDs conceal the variant name. The evaluator has no access to patches, test outcomes or reviewed verdicts and evidence. The arbiter selects source ranges, the local checker extracts verbatim lines and the adapter produces verdict, evidence and explanation.

## Environment and execution

From this directory, create the local environment used by the CLI and Studio:

```sh
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

For live inference, set `PRIAGENT_ENV_FILE` to your own external dotenv file, or export `DEEPSEEK_API_KEY`. When a file is specified, credentials are read only from that file. Supported key names in precedence order are `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY` and `LLM_API_KEY`. Without a file, the same ordering applies to the process environment. The model selected in Studio overrides the file's model setting. The adapter supports DeepSeek Flash and Pro. Archived results use Flash.

```sh
.venv/bin/python -B run.py --pilot --out runs/my-flash-run
.venv/bin/python -B run.py --workers 2 --out runs/my-flash-run
.venv/bin/python -B score.py --run runs/my-flash-run --out results/my-flash-run
```

The default CLI archive is `runs/flash-01`. Use a fresh output directory for a different model or configuration. On resume, completed predictions and stages with matching inputs can be reused. A fresh full benchmark requires at least 325 model stages; retries, output repairs and provider retries may incur additional charges. The runner starts with one pending case, then submits small batches, backs off on rate limits, and stops scheduling after billing or authentication failures. `latest-attempt.json` records the current attempt and `failures.json` contains earlier errors where available.

## Verification and result boundaries

```sh
.venv/bin/python -B -m unittest -v test_port
```

The offline tests check file allowlists, line coordinates and opaque IDs for all 65 inputs. They replay the saved provider response for the first complete case and reconstruct its prediction. The scorer checks saved predictions against registered evidence routes. Alternative evidence chains, overbroad citations and explanation quality require semantic review.

On November 20, 2026, the first batch completed one prediction and subsequently encountered HTTP 429 and 402. The earlier loader selected an inherited credential associated with an unavailable balance. The explicitly configured file selected a funded account. After the precedence fix, Studio completed a five-stage Flash audit of v04 GDPR01 using the selected credential. Only cases with saved predictions contribute to the reported agreement. [DeepSeek API documentation](https://api-docs.deepseek.com/guides/anthropic_api/)
