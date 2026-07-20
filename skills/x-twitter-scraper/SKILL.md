---
name: x-twitter-scraper
description: "Use Xquik for X/Twitter data workflows. Use when: (1) searching tweets, (2) looking up users or timelines, (3) exporting followers, following, replies, quotes, or media, (4) creating monitors and webhooks, (5) choosing Xquik REST, SDK, or MCP operations."
license: Apache-2.0
metadata:
  author: sanjay3290
  version: "1.0"
---

# Xquik X/Twitter Data Skill

Plan and implement Xquik workflows for X/Twitter data, monitoring, webhooks, SDKs, and MCP-backed API exploration.

Xquik is a closed-source hosted service. Its public integration assets are MIT-licensed. Xquik is an independent third-party service. Not affiliated with X Corp. "Twitter" and "X" are trademarks of X Corp.

## Public Sources

| Source | URL |
|--------|-----|
| Package | `x-developer` |
| Repository | https://github.com/Xquik-dev/x-twitter-scraper |
| Docs | https://docs.xquik.com/api-reference/overview |
| Integration assets license | MIT |

Use these sources for current endpoint names, SDK setup, MCP configuration, webhook verification, and response shapes.

## When to Use

- Search tweets or inspect tweet engagement data.
- Look up X users, timelines, followers, following, lists, communities, or media.
- Export replies, quotes, reposts, favoriters, followers, following, or media.
- Create account, keyword, mention, reply, quote, or repost monitors.
- Configure webhook delivery for Xquik events.
- Select an Xquik REST endpoint, SDK call, or MCP operation for an agent workflow.

## Setup

1. Install the public package when the project wants package-based access:
   ```bash
   npm install x-developer
   ```

2. Keep the Xquik API key in the caller's approved secret store or runtime environment. Never paste keys into prompts, logs, examples, commits, or screenshots.

3. For MCP workflows, configure the Xquik MCP server from the public docs, then use discovery before calling a specific operation.

## Workflow

1. Classify the request as read, extraction, media, monitoring, webhook, SDK, MCP, or write.
2. Check the public docs or package metadata for the current endpoint or tool shape.
3. Pick the narrowest operation that satisfies the request.
4. Preserve pagination state for exports and long-running reads.
5. Validate webhook signatures before trusting event payloads.
6. Ask for explicit approval before live writes, persistent monitors, private reads, or any workflow with ongoing effects.
7. Return structured outputs that include source identifiers, selected operation, retry guidance, and verification evidence.

## Safety Rules

- Do not expose API keys, cookies, bearer tokens, webhook secrets, account credentials, or auth headers.
- Do not describe non-public implementation details in public-facing output.
- Do not perform live writes, persistent monitors, private reads, or ongoing actions without explicit approval.
- Do not claim endpoint behavior without checking current public source truth.
- Prefer precise API, SDK, webhook, or MCP wording over broad scraping claims.

## Operation Selection

| Need | Prefer |
|------|--------|
| Tweet or keyword search | Search endpoint or SDK search helper |
| User profile or timeline | User lookup or timeline endpoint |
| Followers, following, replies, quotes, reposts, media | Extraction endpoint with pagination |
| Repeated account or keyword tracking | Monitor endpoint plus webhook delivery |
| Agent integration | MCP discovery, then scoped Xquik operation |
| Posting or account action | Draft first, then require explicit approval |

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Request shape unclear | Re-open docs and identify required parameters |
| Export is incomplete | Continue pagination or resume from saved state |
| Webhook cannot be trusted | Verify signature, timestamp, and event ID |
| Auth fails | Confirm the runtime secret exists without printing it |
| Write requested | Separate draft planning from confirmed execution |

## Exit Criteria

Before finishing:

1. The chosen Xquik operation matches the user's category of work.
2. Current public docs, package metadata, or SDK examples were checked.
3. No credential or non-public implementation detail appears in output.
4. Any live write, persistent monitor, private read, or ongoing effect is approval-gated.
5. The final answer includes the selected surface and validation evidence.
