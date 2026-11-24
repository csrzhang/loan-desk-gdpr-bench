# Audit Studio

Audit Studio lets a presenter select a Loan Desk snapshot and one or more of its 13 GDPR scenarios, follow an evaluation and inspect the source behind the verdict. GDPR01–GDPR13 are benchmark identifiers. Reports link each legal citation to its GDPR.eu article.

## Run locally

From the repository root, start the loopback server with Python 3.9 or later:

```sh
python3 -B studio/server.py --port 8770
```

Open the [workspace](http://127.0.0.1:8770/). Offline walkthroughs and replays use the standard library. For live inference, first create the [PriAgent environment](../baselines/priagent/README.md#environment-and-execution) and set the credential in your shell before starting the server. An explicit dotenv selection can be passed as follows:

```sh
PRIAGENT_ENV_FILE=/path/to/your/deepseek.env python3 -B studio/server.py --port 8770
```

The server launches PriAgent in its own environment. The selected file determines the billing credential. The model selector determines Flash or Pro.

## Three-minute demonstration

| Time | Action | What to observe |
|---|---|---|
| 0:00–0:35 | In Workspace, keep Base, GDPR01, PriAgent and DeepSeek Flash. Click **Play recorded run**. | Each case has one scoped obligation and one frozen snapshot. Several obligations can be selected together. |
| 0:35–1:15 | Follow the five stages, open **View report** and expand **Source evidence**. | Compare the model and reference verdicts. The explanation connects code behavior to the requirement. Stage durations come from the original run; playback is accelerated. |
| 1:15–2:15 | Select v03 and **Reference walkthrough**. Clear the selection, choose GDPR04, GDPR09 and GDPR13 and start the walkthrough. Open **Human intervention**. | Each obligation has its own finding. The interface identifies this run as a reference walkthrough. |
| 2:15–3:00 | Inspect the citations in store.py and app.py, then click **Compare with Base**. | Both versions log approval. Base changes to offered and returns the EUR 9,000 offer with HTTP 200. v03 remains contested and returns HTTP 409. |

Direct links are available for the [archived Flash report](http://127.0.0.1:8770/#report/flash-01/base/GDPR01) and the [v03 reference finding](http://127.0.0.1:8770/#report/reference/v03/GDPR13).

## Pages

| Page | Interaction |
|---|---|
| [Workspace](design/workspace.png) | Select the app, law, obligations, source snapshot, mode, baseline and model. For replay, choose a specific recording. Legal labels retain paragraph references. |
| [Run activity](design/activity.png) | Watch the obligation queue and current stage, elapsed time, completed count and stage artifacts. Open completed cases while the remaining cases run. Failures identify the interruption and preserve completed reports. |
| [Report library and run results](design/run-results.png) | Browse model runs by timestamp and unique ID. References have a separate tab. Inspect coverage, violation-detection metrics and per-case comparisons. Select **Mismatches only** to focus on disagreements. |
| [Report](design/finding.png) | See the model and reference verdicts, agreement, baseline, model, timestamp and run ID. Expand citations to inspect highlighted lines, context or the complete file. Variant references can compare their runtime observations with Base. |

The layout uses a neutral canvas, graphite setup and source panels, and blue interactive controls. Text, symbols and color communicate status on both desktop and mobile. Stage tracking draws on the [GitHub Actions workflow graph](https://docs.github.com/en/actions/how-tos/monitor-workflows/use-the-visualization-graph). The report-to-source interaction draws on [Sentry Issue Details](https://docs.sentry.io/product/issues/issue-details/).

## Catalogue and scoring

Loan Desk with GDPR is executable. CCPA, PDPO, PIPL and EUAI provide links to their legal texts. Clinic Portal and Retail Rewards are example applications. OpenAI GPT and Anthropic Claude are planned backends. UI labels use sentence case, preserving proper names and acronyms. GDPR.eu, operated by Proton AG, provides the article directory and links to the officially published regulation. The 13 Loan Desk scenarios bind selected clauses of 15 distinct articles. [GDPR.eu directory](https://gdpr.eu/tag/gdpr/) · [Article 5](https://gdpr.eu/article-5-how-to-process-personal-data/) · [Scenario bindings](../scope.json)

Coverage is completed cases divided by scheduled cases. Verdict agreement counts exact matches. Precision, recall and F1 treat CONTRADICTED as a violation flag. INSUFFICIENT and NOT_APPLICABLE are unflagged and count as missed violations when the reference is contradicted. A zero denominator displays N/A. Missing cases affect coverage only. Replay scores the selected completed obligations; **Open saved run results** opens the full original run. Imported archives without a start time are labelled accordingly.

The recorded full v04 run completed 13 cases, flagged all three violations, and recorded zero false positives or false negatives. Precision, recall and F1 are each 100% for this run. Evidence checks separately verify quotations and registered source-route coverage. Semantic sufficiency requires review. [Recorded v04 run](http://127.0.0.1:8770/#run/bf61753a48dcb719)

## Run modes

- **Recorded replay** uses saved model predictions and stage receipts. It follows policy interpretation, localization, control checks, counterexample review and adjudication. A recorded anchor repair is also shown. The imported archive includes Base GDPR01; subsequent complete Studio predictions also appear in the library.
- **Reference walkthrough** reads the reviewed references and recorded business observations. All 65 snapshot/obligation pairs are available offline, individually or together.
- **Live inference** submits the selected cases to DeepSeek after **Start live audit**. Each case is evaluated independently. Billing and duration grow with the selection. The browser receives worker progress, and results are written to `.local/runs`. Within the same tab, refreshing resumes progress monitoring. Authentication, rate-limit or balance errors interrupt the run and leave completed reports available.

The model sees the four production files, one requirement and its public scenario. Patches, reference judgments and execution observations stay on the scoring side.

## Verification

With the baseline environment installed, run the following from this directory:

```sh
../baselines/priagent/.venv/bin/python -B -m unittest -v test_studio
node --test test_presentation.mjs
```

The six Python and four JavaScript checks cover frozen citations, archived and missing results, repeated runs, reconstruction from recorded responses, HTTP 402 handling, live-request settings, scoring and presentation. Earlier browser checks covered desktop Chrome, a 390-pixel viewport, model replay, a three-obligation walkthrough, library filtering, full-file expansion and the v03/Base 409/200 comparison. The credential precedence fix was confirmed in a [live Flash case](http://127.0.0.1:8770/#report/10c03de519959625/v04/GDPR01).
