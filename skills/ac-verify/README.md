# ac-verify

Verify Azure DevOps acceptance criteria and linked test cases against a local implementation or PR. Reports connect each requirement to code and execution evidence, with a verdict, confidence, and remaining gaps.

## Setup

Install this skill using the repository's normal skill installation method. For API access, also install/configure [azure-devops](../azure-devops/README.md), or provide an available Azure DevOps connector. A local checkout is recommended for reading actual code and running relevant tests. Credentials remain in the integration's existing authentication store.

Read access is needed for work items, relevant test cases, code and any test results used. Work item comment write access is needed only when posting. This skill does not require permissions to approve PRs, deploy builds, or modify requirements.

## Usage

Ask your agent:

> Use ac-verify to check work item 123 in MyOrganization/MyProject against PR 42 in my-repo. Report locally without changing anything.

Or invoke the skill where your agent supports it:

```text
/ac-verify https://dev.azure.com/MyOrganization/MyProject/_workitems/edit/123 --pr 42
/ac-verify https://dev.azure.com/MyOrganization/MyProject/_workitems/edit/123 --pr 42 --post
```

These are agent prompts, not shell commands. Provide repository context when a PR number is ambiguous. `--post` requests a table comment on the specified work item; otherwise no external write is made. Posting depends on a connector/API operation with a supported comment format. If unavailable, the agent keeps a local report and explains the limitation.

## Meaning of results

- **Met:** demonstrated behavior at the inspected version, within stated coverage.
- **Partially met:** a demonstrated subset works, with a concrete unmet part.
- **Not met:** evidence demonstrates a violation.
- **Not verifiable:** evidence is missing, ambiguous, stale, or limited to unexecuted implementation.

Confidence describes support for a behavioral conclusion; it is N/A for an unverified outcome. A passing build alone does not prove every requirement. The report does not replace QA or release approval.

See [evaluation scenarios](references/evaluation.md) for synthetic checks and [the report contract](references/report.md) for output fields. No live Azure DevOps validation or posting is claimed by these fixtures.
