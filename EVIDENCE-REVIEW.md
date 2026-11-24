# Annotating and scoring source evidence

## Review of the 65 findings

The review compared each finding with its frozen source, scenario and execution receipt. Earlier audits quoted 60 ranges and 326 lines per snapshot. Contradicted findings often inherited the entire implementation chain from the supported case. Each updated `audit.json` now gives a preferred evidence set and reviewed alternatives in `evidence_review.routes`. Each route names the facts and anchors that establish the conclusion. The Markdown reports reflect those changes. Explanations can also include corroborating observations.

| Snapshot | Preferred cited lines, summed by case | Registered sufficient routes |
|---|---:|---:|
| Base | 201 | 14 |
| v01 | 190 | 14 |
| v02 | 166 | 14 |
| v03 | 158 | 13 |
| v04 | 180 | 15 |
| Total | 895 | 70 |

The revised references cite 895 lines, down from 1,630. Splitting broad spans around unrelated code increased the range count from 300 to 342. A line cited in different cases counts once in each case. Across the 70 routes, 361 leave-one-range-out checks confirmed irreducibility at the registered range granularity under the fixed scenarios. Semantic sufficiency, substitutions and potentially shorter arguments still require judgment. Independent two-reviewer adjudication is pending.

## Annotation procedure

1. Fix the snapshot, model-visible inputs, actors, timing, downstream effect, applicable exceptions and permissible alternatives. Treat stipulated facts as given. A provided loan term can be assumed when the scenario states it. The actual use of a corrected email must be established. Private runtime receipts calibrate labels; a source-only evaluator can infer the effect from code.
2. For SUPPORTED, enumerate the jointly necessary conditions and allow different routes to prove them. For CONTRADICTED, identify a reachable failure of a necessary condition and consider alternative controls that could prevent it. After one sufficient counterexample, additional failing outputs can serve as alternative routes.
3. Hide each range and ask which fact can still be established. Remove redundant citations and identify the fact lost when a necessary citation is hidden. For an absent write or control, inspect the branch, delegated functions and downstream consumers. Cite the variant's own source to substantiate its behavior.
4. Look for alternative exits, implementations and controls. Retain enough context to identify the relevant statement or branch. A correct alternative can have different line numbers or length.
5. For formal comparisons, two reviewers should draft their shortest defensible chains independently, replay disputes against the same snapshot, then escalate or mark unresolved cases. Version newly accepted routes with a rationale and rescore all models consistently. Report disagreements and outstanding judgments.

## Worked examples

**Base, GDPR04.** Withdrawal must be easy and effective after a report is queued. One route persists the changed preference and reads it again at execution. Another cancels pending reports on withdrawal and consumes only queued jobs. Both need to account for a consenting control user and repeated execution. Independently disabling the two controls produced these report counts. [Base audit](reference/base/AUDIT.md#gdpr04--withdrawal-before-execution)

| Cancel on withdrawal | Reread at execution | Withdrawn user / control |
|---|---|---|
| Yes | Yes | 0 / 1 |
| Yes | No | 0 / 1 |
| No | Yes | 0 / 1 |
| No | No | 1 / 1 |

Disabling a control tests business behavior. Removing a citation tests the reader's remaining evidence.

**v01, GDPR10.** The contract portability projection omits `term`. Connecting it to the recipient's use of `portable(c)` establishes one counterexample. The download route serializes the same projection and also establishes the failure. A front-end download link alone cannot establish the omitted field. A field list needs evidence that it feeds the actual output. [v01 audit](reference/v01/AUDIT.md#gdpr10--portable-contract-fields)

## Scoring other models

Blind the model identity, check file ownership, coordinates and exact quotes, and compare the factual claims proved. Keep all cited parts of a counterexample tied to the same case.

| Submission | Treatment |
|---|---|
| Split or merged ranges, or nearby equivalent lines | Verify the text and credit the same established facts. |
| A different registered route | Any complete sufficient route can earn full sufficiency credit. |
| A new route or partial chain | Review whether all necessary facts follow. Register valid new routes and rescore the batch. Identify missing facts for incomplete chains. |
| A valid chain plus a whole file or unrelated login code | Credit sufficiency separately. Classify extra material as relevant but redundant, irrelevant or pending review. Record errors in extra claims. |
| Correct verdict with a fabricated quote or conflicting explanation | Score the verdict separately. Exclude invalid evidence from support and check the explanation against source behavior. |

Report verdict agreement, evidence sufficiency, citation accuracy and concision, and joint correctness separately. For sufficiency, the fraction of required facts proved on the best accepted route is informative. Deduplicate equivalent facts. For semantic precision, divide correct relevant claims by submitted distinct citation claims, including fabricated and irrelevant claims in the denominator. An empty evidence set has undefined semantic precision. Report irrelevant and repeated lines and additional valid routes separately. Joint correctness requires a matching verdict, sufficient evidence and an accurate explanation of trigger and effect.

## Offline screening

Use the [prediction schema](prediction.schema.json) and a case ID such as `v01-GDPR10`. From the repository root run:

```sh
python3 -B evidence.py prediction.json
python3 -B verify.py --operators
python3 -B -m unittest discover -s validation -p 'test_evidence_review.py' -v
python3 -B -m unittest discover -s validation -p 'test_withdrawal_routes.py' -v
```

The screener unions validated source lines. `localized_routes` lists fully located registered routes and `route_details` identifies missing locations. `registered_line_fraction` measures location overlap. `valid_lines_outside_registered_routes` identifies lines to review, `overlapping_valid_lines` records duplication and `valid_lines_beyond_shortest_completed_route` measures extra span, including multiple complete routes. Invalid citations are reported separately. Semantic precision, alternative proofs and the accuracy of an explanation require review.
