# Loan Desk GDPR Benchmark

Audit a runnable consumer-loan application against 13 scoped GDPR obligations. The benchmark contains one original snapshot, four multi-defect variants and 65 reference findings. Each finding binds a particular version, obligation and business scenario to source evidence and an observed outcome.

## Explore the benchmark

From the repository root, run Audit Studio with Python 3.9 or later. The offline walkthrough and recorded model runs use the standard library.

```sh
python3 -B studio/server.py --port 8770
```

Open [Audit Studio](http://127.0.0.1:8770/). For a short demonstration, compare the human-review outcome for Base and v03 under GDPR13. To inspect a saved model evaluation, open the v04 run in the report library. See the [Studio guide](studio/README.md) and [PriAgent baseline](baselines/priagent/README.md).

| Snapshot | Confirmed contradictions | Supported / contradicted | Reference audit | Machine-readable |
|---|---|---|---|---|
| [Base](projects/base/) | None | 13 / 0 | [Report](reference/base/AUDIT.md) | [JSON](reference/base/audit.json) |
| [v01](projects/v01/) | GDPR04 withdrawal, GDPR10 portability | 11 / 2 | [Report](reference/v01/AUDIT.md) | [JSON](reference/v01/audit.json) |
| [v02](projects/v02/) | GDPR07 rectification, GDPR13 human intervention | 11 / 2 | [Report](reference/v02/AUDIT.md) | [JSON](reference/v02/audit.json) |
| [v03](projects/v03/) | GDPR04 withdrawal, GDPR09 restriction, GDPR13 human intervention | 10 / 3 | [Report](reference/v03/AUDIT.md) | [JSON](reference/v03/audit.json) |
| [v04](projects/v04/) | GDPR07 rectification, GDPR09 restriction, GDPR10 portability | 10 / 3 | [Report](reference/v04/AUDIT.md) | [JSON](reference/v04/audit.json) |

The five snapshots share one application lineage. The 55 supported and 10 contradicted findings cover five defect mechanisms. Each reference directory includes a `run.json` with the contract test, assertion outcome and business observations collected using fresh databases.

## Mutation operators

Each patch applies independently to Base. Each composite snapshot is also built directly from Base.

| Patch | Change | Observed consequence |
|---|---|---|
| [Check consent only at enqueue time](reference/operators/enqueue-only-consent.patch) | Pending insights reports survive withdrawal, and the worker relies on the original consent check. | After restart and repeated execution, the withdrawn and control users receive 1/1 reports. Base produces 0/1. |
| [Acknowledge without updating](reference/operators/acknowledge-only-correction.patch) | Validate a corrected email and log success while skipping the case update. | After restart, the stored address and the new offer still carry the old email despite a success receipt. |
| [Score during restriction](reference/operators/score-during-restriction.patch) | Exempt scoring jobs from the pause while retaining the restriction flag. | Base stays pending. The variant rejects a EUR 9,000 application using disputed income while the restriction is active. |
| [Omit the portable term](reference/operators/omit-portable-term.patch) | Remove the borrower-provided term from the projection shared by download and direct transfer. | Both outputs remain valid JSON and delivery succeeds. Both omit the expected 12-month term. |
| [Record a reversal only in the log](reference/operators/record-only-reversal.patch) | Write the previous contested state back after review while recording the officer's approval. | Both logs record an offer. Base delivers the EUR 9,000 offer; the variant remains contested and returns HTTP 409. |

## Reading a finding

- **Verdict.** SUPPORTED means the implementation and runtime observations support the scoped behavior. CONTRADICTED means a reachable business outcome conflicts with a necessary condition. The [scope](scope.json) defines the legal references, assumptions and scenarios.
- **Evidence.** Each citation contains the snapshot-relative path, inclusive one-based line range, exact source text and claim. Runtime observations record outcomes such as delivery, persisted state or rejection. The preferred citations and reviewed alternative routes are documented in the [evidence review](EVIDENCE-REVIEW.md).
- **Explanation.** The rationale connects the trigger, implementation and consequence. v01 can pass the initial consent scenario and fail withdrawal after enqueue. The automated-decision and disputed-income scenarios in v03 use separate cases so that one rejection cannot mask another defect.

For blind evaluation, supply the four production files, one scoped requirement and its public scenario under an opaque case ID. Keep references, patches, tests and receipts on the evaluation side. The [prediction schema](prediction.schema.json) defines the output. See the [archived Flash evaluation](baselines/priagent/results/flash-01/RESULTS.md) for the CLI batch's actual coverage.

## Run a snapshot and reproduce the references

```sh
python3 -B projects/v03/app.py --port 8768
```

Open [Loan Desk](http://127.0.0.1:8768/). On first launch the application creates local demo credentials in its own data directory. Sign in as borrower Alice to apply or appeal, and as assigned officer Morgan to review the case. Return as Alice to download the offer. Each snapshot has its own data directory.

```sh
python3 -B verify.py
python3 -B verify.py --operators
```

The verifier runs 13 frozen contract tests and 13 supplemental observations for each snapshot in isolated databases. It checks source hashes, all 65 verdicts and their citations. The extended check also needs the command-line `patch` utility. The November 20, 2026 run reproduced all five snapshots. Each isolated mutation failed its targeted contract and passed the other 12. Combining patches reconstructed the four variants byte for byte. [Integrity manifest](reference/manifest.json)

## Interpretation

GDPR01–GDPR13 are project identifiers for scenarios citing 15 distinct GDPR articles. The fixtures assume a private EU controller, synthetic adult borrowers and specified legal bases and exceptions. GDPR05 covers direct collection and an in-app import notice. GDPR12 covers access to ordinary case and offer routes. GDPR13 assumes a significant automated decision and valid explicit consent under Article 22(2)(c). Local code and test observations establish scoped technical behavior. Real-world consent, substantive human review and an independent legal assessment require additional evidence. [GDPR article directory](https://gdpr.eu/tag/gdpr/) · [Frozen legal source and bindings](scope.json)
