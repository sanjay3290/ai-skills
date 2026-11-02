# Report contract

Use Markdown locally and an explicitly supported table format for Azure DevOps posting. Keep a complete local copy if the API payload limit requires a shortened comment. Do not upload attachments without authorization.

## Header

- Work item URL/ID, title, revision and retrieval timestamp.
- Repository, PR URL/ID or local comparison, base/head SHAs, merge base where applicable, dirty working tree inclusion.
- Report timestamp and evidence environment.
- Summary counts for Met, Partially met, Not met, Not verifiable. Count parent AC once; show subcriteria in the details. Do not treat Not verifiable as passed.

## Tables

Create an **Acceptance criteria** table with these columns:

`ID | Requirement | Verdict | Implementation evidence | Execution evidence | Confidence and reason | Gap / next check`

Include every active criterion, even those covered by linked test cases. Retain source wording or a faithful excerpt with its conditions. Long evidence may be placed in numbered notes referenced from cells.

Create a separate **Linked test cases** table when cases exist:

`TC ID | Steps / expected result | AC mapping | Verdict | Evidence / tested version | Gap`

Record unmapped cases and uncovered AC explicitly. If no cases were linked, say so; do not invent test cases. If case retrieval failed, distinguish that from having no linked cases.

For each evidence reference, use verified file paths and line numbers at the inspected version or a test run/result link. Local file references are not clickable to Azure DevOps readers: include repository-relative paths and the commit SHA, or verified repository links. Never invent line numbers or URLs.

## Status presentation

In local HTML reports, show verdicts as labeled badges with consistent colors:

- Green: `✅ Met` — dark green text `#14532d` on pale green `#dcfce7`.
- Red: `❌ Not met` — dark red text `#7f1d1d` on pale red `#fee2e2`.
- Amber: `⚠️ Partially met` — dark amber text `#78350f` on pale amber `#fef3c7`.
- Gray: `➖ Not verifiable` — dark gray text `#374151` on pale gray `#e5e7eb`.

Use the same gray treatment for a separate `➖ Not covered by linked tests` label. Coverage is independent of verdict: a requirement can have behavioral evidence without a linked test case. Missing linked coverage must not replace the verdict or imply failure. Retrieval errors mean coverage is unknown, not absent.

Keep readable status text and symbols alongside color in each result row. Omit a separate status legend above the table. Do not rely on color alone or change confidence to match a status. Do not add demonstration rows for verdicts absent from the actual findings.

For Markdown or Azure DevOps comments, retain explicit status labels and symbols even when custom colors are unsupported. Use supported styling only; do not assume inline CSS will survive sanitization. Verify rendering when possible and disclose when it is unverified.

## Footer

List commands actually run and outcomes; evidence not available; excluded struck-through requirements; assumptions; unresolved questions; and manual/runtime checks required. Avoid claims about environments or commits that were not inspected.

For posting, include an audit label such as `ac-verify: WI 123 rev 7; base abc; head def` and timestamp. It is a deduplication aid, not authorization to edit existing comments.
