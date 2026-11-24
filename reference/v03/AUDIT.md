# Loan Desk · v03

Scoped reference judgments for the frozen source. Each item links the behavior to its supporting code and records the observed execution. See [common scope](../../scope.json) and [test receipts](run.json).

Source SHA-256: `d46e7b40a66a06625a38937bd1e377a4d0f703bdc9289086c4a3f8523669f606`

## GDPR01 · Application field minimization

**SUPPORTED** · Article 5(1)(c)

Submit a loan application using email for delivery, amount and term for the requested offer, and income band for assessment. A hobby has no business purpose in this fixture.

The form takes the defined inputs. Submission validates the field set before persistence, and the indexed summary uses only amount and term. The application succeeds without the hobby; submitting it as an additional field leaves the case count at one.

**Reviewed source evidence**

- The collection form asks for the four business fields and an optional route choice. [views.py L31–32](../../projects/v03/views.py#L31)
- Submission rejects fields outside the declared input set. [store.py L67–67](../../projects/v03/store.py#L67)
- The stored payload and business summary select only scoped fields. [store.py L77–79](../../projects/v03/store.py#L77)

**Runtime** · `test_GDPR01_minimum_application_fields` · PASS

```json
{
  "after_extra_field": 1,
  "eligible_application": "/case/1"
}
```

## GDPR02 · Purpose limitation

**SUPPORTED** · Article 5(1)(b), 6(4)

An opted-in subscriber has a partner-confirmed income band for underwriting. There is no compatible marketing purpose or new legal basis for targeting with that band.

Income confirmation changes the EUR 9,000 decision from the declared high-band outcome to a low-band refusal. Audience selection reads owner, case eligibility and preferences. SQLite read tracing during campaign selection confirms that declared and verified income do not enter that selection. The eligible promotion is still delivered.

**Reviewed source evidence**

- The imported confirmation is used for underwriting. [store.py L159–159](../../projects/v03/store.py#L159), [store.py L131–134](../../projects/v03/store.py#L131)
- Campaign selection uses case eligibility and purpose-specific choices, including inside its preference helper. [store.py L102–103](../../projects/v03/store.py#L102), [store.py L89–90](../../projects/v03/store.py#L89), [store.py L107–109](../../projects/v03/store.py#L107)
- The actual promotion delivery uses that selection and contains no underwriting field. [store.py L140–141](../../projects/v03/store.py#L140)

**Runtime** · `test_GDPR02_underwriting_and_campaign_inputs` · PASS

```json
{
  "decisions": [
    "Automatic declined. Amount 9000 compared with low limit 5000."
  ],
  "promotions": 1
}
```

## GDPR03 · Purpose-specific opt-in

**SUPPORTED** · Article 6(1)(a), 7(1), 7(2), 7(4)

An adult uses the core application with optional repayment insights initially off. Marketing permission does not authorize private insights.

The core loan can be submitted independently. The insights choice is separately presented and recorded with a version. The report entry point rejects an absent insights choice even when promotions are enabled. A later affirmative choice makes a report possible.

**Reviewed source evidence**

- Core submission is separate from the optional, purpose-specific positive choice. [views.py L33–36](../../projects/v03/views.py#L33), [store.py L67–67](../../projects/v03/store.py#L67)
- Absence defaults to off; an affirmative versioned choice is recorded by owner and purpose. [store.py L89–90](../../projects/v03/store.py#L89), [store.py L94–95](../../projects/v03/store.py#L94)
- Requesting a report requires current insights permission, and a queued report produces an actual output. [store.py L167–168](../../projects/v03/store.py#L167), [store.py L171–171](../../projects/v03/store.py#L171), [store.py L137–138](../../projects/v03/store.py#L137)

**Runtime** · `test_GDPR03_specific_optional_choice` · PASS

```json
{
  "after_opt_in": 1,
  "before_opt_in": 0,
  "choice_version": "2026-11-v1"
}
```

## GDPR04 · Withdrawal before execution

**CONTRADICTED** · Article 7(3)

Two borrowers opt in and queue reports. One withdraws before execution. The queue is reopened and drained twice; the other borrower remains eligible.

Withdrawal is recorded, but cancellation covers promotions only. The earlier insights check is made when work is queued; report execution no longer reads current consent. The withdrawing borrower receives one new report after restart, just like the eligible control.

**Reviewed source evidence**

- Recording withdrawal leaves queued reports pending; only promotions are cancelled. [store.py L94–98](../../projects/v03/store.py#L94)
- A pending report reaches an unconditional-with-respect-to-consent output. [store.py L126–126](../../projects/v03/store.py#L126), [store.py L137–138](../../projects/v03/store.py#L137)

**Runtime** · `test_GDPR04_withdraw_after_enqueue_and_retry` · FAIL

```json
{
  "control_reports": 1,
  "withdrawn_job": "done",
  "withdrawn_reports": 1
}
```

## GDPR05 · Notice at collection and partner import

**SUPPORTED** · Article 12(1), 13(1)–(2), 14(1)–(3)

Direct application plus a synthetic Income Registry import. No prior outward disclosure or Art. 14(5) exception. The applicant may open the case immediately or leave it unopened.

The loan form exposes the processing notice before data entry. Import writes a source-specific notice to the case inbox in the same transaction as the confirmed band. The notice exists at import in both tested timelines, including when there is no later visit. The timing finding uses immediate local inbox delivery.

**Reviewed source evidence**

- The shared notice supplies the information for the scoped direct and indirect collection. [store.py L9–9](../../projects/v03/store.py#L9)
- The notice is rendered at direct collection before the inputs. [views.py L24–25](../../projects/v03/views.py#L24), [views.py L31–31](../../projects/v03/views.py#L31)
- Import records a source-specific notice with the confirmed value immediately. [store.py L157–160](../../projects/v03/store.py#L157)
- The notice event is available through the case inbox. [views.py L76–76](../../projects/v03/views.py#L76), [views.py L79–79](../../projects/v03/views.py#L79)

**Runtime** · `test_GDPR05_direct_and_indirect_notice` · PASS

```json
{
  "direct_notice_before_input": true,
  "source_named": true
}
```

## GDPR06 · Subject access copy

**SUPPORTED** · Article 15(1), 15(3), 15(4)

The authenticated applicant requests the copy of one specified case, including derived decision, source, linked activities and processing information. Another applicant has separate data.

The route scopes the case and the download to its owner. The response contains the case, processing information, source-import and decision events, jobs and that owner’s preference history. The control customer cannot obtain the same case copy.

**Reviewed source evidence**

- The access endpoint binds the authenticated subject to the requested case and selects the personal access response. [store.py L55–58](../../projects/v03/store.py#L55), [app.py L94–95](../../projects/v03/app.py#L94), [app.py L105–106](../../projects/v03/app.py#L105)
- The response supplies the case and processing information, with case-scoped events/jobs and owner-scoped choices. [store.py L9–9](../../projects/v03/store.py#L9), [store.py L119–122](../../projects/v03/store.py#L119)
- The event stream actually contains the indirect source and the derived decision. [store.py L160–160](../../projects/v03/store.py#L160), [store.py L135–135](../../projects/v03/store.py#L135)

**Runtime** · `test_GDPR06_access_inventory_and_owner` · PASS

```json
{
  "confirmed_income": "low",
  "copy_sections": [
    "application",
    "jobs",
    "preferences",
    "processing_information",
    "timeline"
  ],
  "event_kinds": [
    "application",
    "partner notice",
    "decision"
  ]
}
```

## GDPR07 · Rectification and subsequent use

**SUPPORTED** · Article 16

The borrower corrects a contact email. After reopening the database the next offer must use the corrected address. A separate live case is unaffected.

The correction updates the case row. A subsequent download reloads that row and constructs the offer from its current email. After restart the stored email and the next offer both contain new@example.test.

**Reviewed source evidence**

- The correction writes the new address to the targeted case. [store.py L172–173](../../projects/v03/store.py#L172)
- A fresh case read feeds the offer download, which uses that row’s email. [store.py L55–58](../../projects/v03/store.py#L55), [app.py L94–95](../../projects/v03/app.py#L94), [app.py L101–103](../../projects/v03/app.py#L101), [store.py L111–112](../../projects/v03/store.py#L111)

**Runtime** · `test_GDPR07_correct_and_regenerate_offer` · PASS

```json
{
  "next_offer": "new@example.test",
  "original": "person@example.test",
  "receipt": [
    "Contact email updated."
  ],
  "requested": "new@example.test",
  "stored": "new@example.test"
}
```

## GDPR08 · Erasure of an abandoned case

**SUPPORTED** · Article 17(1)(a), 17(3)

An abandoned application is no longer necessary. There is no mandatory retention, prior external disclosure or other exception in this fixture. An active case remains necessary.

The stage guard admits the abandoned case. Foreign-key enforcement cascades deletion to its summary, events and jobs. After restart all four row counts are zero, the old job cannot run, and the other case remains available.

**Reviewed source evidence**

- Only an abandoned case is eligible and its primary row is deleted. [store.py L210–212](../../projects/v03/store.py#L210)
- Deleting the parent actually cascades to all three required internal copies, including the pending job. [store.py L26–26](../../projects/v03/store.py#L26), [store.py L39–41](../../projects/v03/store.py#L39), [store.py L43–44](../../projects/v03/store.py#L43)

**Runtime** · `test_GDPR08_erase_main_copies_jobs_and_replay` · PASS

```json
{
  "active_visible": true,
  "rows_after_restart": {
    "cases": 0,
    "events": 0,
    "jobs": 0,
    "summaries": 0
  }
}
```

## GDPR09 · Restrict ordinary use of disputed data

**CONTRADICTED** · Article 18(1)(a), 18(2), 18(3)

Accuracy of the partner income band is disputed before a queued score runs. The record is retained for verification. None of the exceptions for ordinary scoring applies.

The case is still restricted and the low income confirmation remains disputed. The worker exempts scoring jobs from its hold, reads that band and issues an automatic refusal before verification or release. The observed restriction flag is 1 when the decision already exists.

**Reviewed source evidence**

- The disputed file is put under restriction. [store.py L175–177](../../projects/v03/store.py#L175)
- The hold explicitly exempts pending scoring jobs, which then use the disputed band to set an effective lending outcome. [store.py L126–129](../../projects/v03/store.py#L126), [store.py L131–134](../../projects/v03/store.py#L131)

**Runtime** · `test_GDPR09_dispute_pause_notify_then_resume` · FAIL

```json
{
  "decision_events": [
    "Automatic declined. Amount 9000 compared with low limit 5000."
  ],
  "disputed_band": "low",
  "effective_stage": "declined",
  "restriction": 1
}
```

## GDPR10 · Portable contract fields

**SUPPORTED** · Article 20(1)(a)–(b), 20(2), 20(4)

Automated processing of a current contract. The borrower supplied email, amount, term and income. They download those fields and request direct transfer to the feasible local receiver.

The accepted-contract projection includes all four subject-provided fields and excludes inferred decisions. Download and requested transfer use the same projection. Both received JSON objects contain the original 12-month term and the other three values.

**Reviewed source evidence**

- The contract projection selects exactly the four subject-provided fields. [store.py L114–116](../../projects/v03/store.py#L114)
- The subject receives this projection through the structured download. [app.py L104–109](../../projects/v03/app.py#L104)
- The requested transfer delivers the same projection to the designated receiver. [store.py L201–203](../../projects/v03/store.py#L201)

**Runtime** · `test_GDPR10_portable_contract_and_receiver` · PASS

```json
{
  "download": {
    "amount": 9000,
    "email": "person@example.test",
    "income": "medium",
    "term": 12
  },
  "provided_term": 12,
  "received": {
    "amount": 9000,
    "email": "person@example.test",
    "income": "medium",
    "term": 12
  }
}
```

## GDPR11 · Objection to direct marketing

**SUPPORTED** · Article 21(2)–(3)

A borrower with active marketing permission objects after a campaign is queued. Another subscribed borrower has no objection. Service decisions remain necessary.

Objection cancels pending promotions. New campaigns and delivery consult the objection independently of the earlier marketing opt-in. The objector receives zero promotions and one service decision. The subscribed control receives one of each.

**Reviewed source evidence**

- Objection is recorded by owner and purpose; eligibility reads the current choices. [store.py L94–95](../../projects/v03/store.py#L94), [store.py L89–90](../../projects/v03/store.py#L89), [store.py L102–103](../../projects/v03/store.py#L102)
- New campaigns queue only eligible subjects. [store.py L107–109](../../projects/v03/store.py#L107)
- The worker rechecks eligibility for previously queued promotions. [store.py L140–141](../../projects/v03/store.py#L140)
- The separate service decision still reaches the case timeline. [store.py L131–135](../../projects/v03/store.py#L131)

**Runtime** · `test_GDPR11_object_to_marketing_keep_service` · PASS

```json
{
  "objector": {
    "decisions": 1,
    "promotions": 0
  },
  "subscriber": {
    "decisions": 1,
    "promotions": 1
  }
}
```

## GDPR12 · Case and offer confidentiality

**SUPPORTED** · Article 25(1)–(2), 32(1)

The selected risk is disclosure of a synthetic case or offer via its ordinary case and download routes. The permitted principals are the owner and the assigned officer.

The authenticated session supplies the principal to a case lookup constrained by owner or assigned officer. Both protected routes consume that lookup. In the four-role matrix the two permitted principals receive 200 on each route, while the other borrower and unassigned officer each receive 404.

**Reviewed source evidence**

- The principal comes from the authenticated session. [app.py L62–65](../../projects/v03/app.py#L62), [app.py L47–47](../../projects/v03/app.py#L47)
- Both resource routes resolve the same case through an owner-or-assigned-officer predicate and deny missing matches. [app.py L92–96](../../projects/v03/app.py#L92), [store.py L55–58](../../projects/v03/store.py#L55)
- The offer and the case page consume that authorized result. [app.py L100–103](../../projects/v03/app.py#L100), [app.py L110–112](../../projects/v03/app.py#L110)

**Runtime** · `test_GDPR12_case_and_document_isolation` · PASS

```json
{
  "responses": {
    "assigned": [
      200,
      200
    ],
    "other": [
      404,
      404
    ],
    "owner": [
      200,
      200
    ],
    "unassigned": [
      404,
      404
    ]
  },
  "routes": [
    "case",
    "offer"
  ]
}
```

## GDPR13 · Effective human intervention after automatic refusal

**CONTRADICTED** · Article 22(1), 22(2)(c), 22(3)

Assume a qualifying significant automatic credit refusal and valid separate explicit consent under Art. 22(2)(c). The applicant contests, submits their view and an authorized officer approves. Manual selection and pre-decision withdrawal are also exercised.

The officer records an approval after reading the appeal. For contested cases the update writes the previous contested stage back to the case. The borrower receives HTTP 409 at the offer endpoint despite the approval in their timeline. The ordinary manual route is a separate path and cannot deliver this reversal.

**Reviewed source evidence**

- On review of a contested case the officer’s new result is logged while the case retains its previous stage. [store.py L191–196](../../projects/v03/store.py#L191)
- The offer download rejects a case left contested. [app.py L101–103](../../projects/v03/app.py#L101)

**Runtime** · `test_GDPR13_real_decision_appeal_and_manual_alternative` · FAIL

```json
{
  "download_status": 409,
  "offer_amount": null,
  "review_log": "morgan reviewed: offered. Documents reviewed.",
  "stage": "contested"
}
```
