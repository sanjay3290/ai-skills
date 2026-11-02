# `gemini-api` CLI reference

Behaviors below were verified against **`gemini-api` 0.4.5** (released 2026-10-30) on
macOS. The CLI is beta; when the binary disagrees with this file, the binary is right.
Re-check with `gemini-api <cmd> --help`.

Upstream: <https://github.com/google-gemini/gemini-api-cli> (Apache-2.0, Google;
not accepting external pull requests).

## Install and verify

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/google-gemini/gemini-api-cli/main/scripts/install.sh | bash
# Windows PowerShell
iwr -useb https://raw.githubusercontent.com/google-gemini/gemini-api-cli/main/scripts/install.ps1 | iex
# Go
go install github.com/google-gemini/gemini-api-cli/cmd/gemini-api@latest
```

The install script puts the binary in `~/.local/bin`. Prebuilt archives for macOS, Linux,
and Windows are on GitHub Releases. Pin a release tag in CI.

```bash
gemini-api version   # "gemini-api 0.4.5" + build timestamp
gemini-api whoami    # config file, credential source, global parameters, preferences
```

## Authentication

Resolution order is flag, then environment, then keychain/config.

| Source | How |
|---|---|
| Env var | `export GEMINI_API_KEY="..."` |
| OS keychain | `gemini-api configure --api-key "..."` (macOS Keychain, Linux Secret Service, Windows Credential Manager) |
| Config file | `~/.config/gemini-api/config.yaml`, used when `--no-keyring` is set |
| Per call | `--api-key`, or `--access-token` for an OAuth bearer token |

`whoami` prints the key masked (first and last characters only) and names the source in
brackets. Every global flag
has a `GEMINI_`-prefixed env var; `gemini-api --help-global` lists them.

Create a key in AI Studio: <https://ai.google.dev/gemini-api/docs/api-key>

## Global flags that matter

| Flag | Effect |
|---|---|
| `-o, --output-format` | `pretty` (default), `json`, `yaml`, `table`, `toon` |
| `-q, --jq <expr>` | jq filter over the response; works without `-o json` |
| `--raw-output` | strings print unquoted; **on by default** |
| `--dry-run` | validate and preview; no network, no keychain read |
| `--agent-mode` | structured JSON errors on stderr **and** TOON stdout by default. No env var sets it. `-o json` alone gives the same error envelope |
| `--no-interactive` | never prompt, never open a TUI form — set this in scripts and hooks |
| `--usage` | whole command tree, flags, defaults, env vars, config keys, as KDL |
| `--timeout`, `-H/--header`, `-d/--debug` | network and diagnostics |

Exit codes: `0` success · `1` runtime or API failure · `2` invalid usage or validation ·
`3` authentication/authorization.

## Commands

### `generate` — text and multimodal

```bash
gemini-api generate "Explain this trade-off in one paragraph"
gemini-api generate "Review this" -i design.md --system "You are a staff engineer"
echo "$DIFF" | gemini-api generate --stdin "Spot the bug"
```

Flags: `-m/--model`, `-i/--input` (repeatable: local path, `files/<id>`, or YouTube URL),
`--stdin`, `--system`, `--stream` (default true), `--previous-interaction-id`, `--body`,
`--schema`, `--mime-type`.

Streams text deltas to stdout by default. Thinking models such as `gemini-3.8-flash` may
hold their output and emit it in a burst; `gemini-flash-lite-latest` streams visibly.

### `image` — generate and edit

```bash
gemini-api image "a lighthouse at sunset" --out ./assets/hero.jpg
gemini-api image "product shot, white bg" --aspect-ratio 16:9 --image-size 2K --out shots/
gemini-api image "make the sky stormy" --previous-interaction-id "$PRIOR_ID"
```

Flags: `-m/--model`, `--aspect-ratio` (`1:1`, `2:3`, `3:2`, `3:4`, `16:9`, …),
`--image-size` (`512`, `1K`, `2K`, `4K`), `--out`, `--output-mime-type`, `-i/--input`,
`--previous-interaction-id`, `--raw-response`, `--body`, `--schema`.

Default output path: `./gemini-image-{timestamp}-{rand}.{ext}`. Editing is conversational:
take the prior turn's ID (`--jq .response_id` when `--out` is used, or `--raw-response
--jq .id`) and pass it as `--previous-interaction-id`.

### `tts` — speech

```bash
gemini-api tts "Welcome. Let's build something." --out ./assets/welcome.wav
gemini-api tts -f script.txt --voice Puck --out out.wav
gemini-api tts "Alice: Hi there. Bob: Hello." --multi-speaker "Alice=Kore,Bob=Puck"
```

Flags: `-f/--file`, `--stdin`, `-v/--voice` (default `Kore`; also `Puck`, `Zephyr`,
`Charon`, `Fenrir`, `Aoede`), `--multi-speaker`, `--language` (BCP-47), `--out`, `-m`.

**Always 24 kHz mono WAV.** `--out foo.mp3` is still written as WAV. Multi-speaker scripts
must label every turn (`Alice: …`). Not stored server-side.

### `music`

```bash
gemini-api music "warm ambient bed for a product walkthrough" --out ./assets/
```

Flags: `-f/--file`, `--stdin`, `--out`, `-m` (`lyria-3.5` default, `lyria-3-pro-preview`
for full songs, `lyria-3-clip-preview` for short clips), `--raw-response`, `--body`.

### `video`

```bash
gemini-api video "a slow pan through a sunlit workshop" --resolution 1080p --out clips/
gemini-api video "a timelapse of a city at night" --async      # → interaction ID
gemini-api video --resume "$ID" --out clips/city.mp4
```

Flags: `--aspect-ratio`, `--resolution` (`360p`, `720p` default, `1080p`, `4k`), `--async`,
`--resume`, `--poll-interval`, `--poll-timeout`, `-i/--input`,
`--previous-interaction-id`, `--out`, `--raw-response`, `--body`.

Synchronously it polls `agent status` with backoff until the video is done, then writes
the file. Long jobs belong behind `--async`.

### `analyze` — ask about files

```bash
gemini-api analyze -i report.pdf "Summarize the key findings"
gemini-api analyze -i before.png -i after.png "What changed?"
gemini-api analyze -i https://youtu.be/VIDEO_ID "What happens at 1:00?"
gemini-api analyze -i files/abc123 "List every speaker with timestamps"
```

Flags: `-i/--input` (**required**, repeatable), `--stdin`, `--system`, `-m`, `--mime-type`.
Default question is "Describe this file in detail." Prints only the answer. Not stored.

### `transcribe`

```bash
gemini-api transcribe -i interview.mp3                       # Markdown
gemini-api transcribe -i call.wav --format srt --out call.srt
gemini-api transcribe -i a.mp3 -i b.mp3 --out ./transcripts/
```

Flags: `-i/--input` (**required**, repeatable), `--format` (`md` default, `text`, `json`,
`srt`/`captions`), `--out`, `--no-speakers`, `--no-timestamps`, `-m`.

Speakers and timestamps are on by default. Model is `gemini-3.5-transcribe`, except video
inputs, which use `gemini-3.8-flash`. Prints one absolute path per line. With several
inputs, `--out` must name a directory.

### `files` — reuse and large media

```bash
URI=$(gemini-api files upload interview.mp4 --wait --jq '.name')   # → files/abc123
gemini-api analyze -i "$URI" "List the action items with timestamps"
gemini-api files list
gemini-api files delete "$URI"
```

Subcommands: `upload`, `list`, `get`, `generated-files-list`, `register`, `delete`.
`upload` flags: `--display-name`, `--mime-type`, `--wait`, `--wait-timeout` (default 5m).

Limits: inline requests are capped at 20 MB base64-encoded, roughly **14 MB of media** —
above that, upload first. The service accepts 2 GB per file (50 MB for PDFs), 20 GB per
project, and **deletes uploads after 48 hours**.

### `agent` — models, managed agents, background runs

```bash
# Background managed-agent run
ID=$(gemini-api agent run "Research solid-state battery suppliers, cite sources" \
  --agent deep-research-preview-04-2026 --background --jq '.id')
gemini-api agent status "$ID" -o json --jq '.status'
gemini-api agent status "$ID" --stream          # replay/stream events
gemini-api agent cancel "$ID"
```

Subcommands: `run`, `status`, `cancel`, `delete-interaction`, `create`, `list`, `get`,
`delete`.

`run` flags: `--agent` **or** `-m/--model` (the two variants' flags cannot be mixed),
`--background`, `--stream` (default true), `-i/--input`, `--previous-interaction-id`,
`--body`, `--schema`.

Built-in managed agents, as advertised by `agent run --help` in 0.4.5:
`deep-research-preview-04-2026`, `deep-research-pro-preview-12-2025`,
`deep-research-max-preview-04-2026`, `antigravity-preview-05-2026`.

`status` flags: `-i/--id` (or positional), `-s/--stream`, `-l/--last-event-id`,
`--include-input`.

### `models`

```bash
gemini-api models              # curated offline catalog, grouped by capability
gemini-api models list --all   # live models for this key, auto-paginated
gemini-api models get gemini-3.8-flash
```

`models` (bare) needs no network. Model names drift between releases — read the catalog
instead of hardcoding a name from memory or from this file.

### Advanced, server-side state

`environments` (sandboxes and their files), `credentials` (tokens agents inject into
outgoing requests), `webhooks` (endpoints, signing secrets, `ping`,
`rotate-signing-secret`), `triggers` (cron schedules for managed agents, `run`,
`list-executions`). These create and delete resources on the user's project: confirm
before mutating.

`environments connect`, `environments poll`, and `environments serve` turn the local
machine into a sandbox worker that executes managed-agent interactions. That hands
remote-dispatched work a shell on this machine — never start one without the user asking
for it explicitly.

## Output shapes

A non-streaming interaction (`--stream=false -o json`) is one object:

```json
{
  "id": "v1_Chd...",
  "status": "completed",
  "model": "gemini-3.1-flash-lite",
  "object": "interaction",
  "created": "2026-11-02T16:28:16Z",
  "usage": { "total_tokens": 7, "total_input_tokens": 6, "total_output_tokens": 1 },
  "steps": [
    { "type": "thought", "signature": "..." },
    { "type": "model_output", "content": [ { "type": "text", "text": "ok" } ] }
  ]
}
```

The reply text is **not** at a top-level key. Extract it:

```bash
gemini-api generate "..." --stream=false \
  --jq '[.steps[] | select(.type=="model_output") | .content[].text] | join("")'
```

`usage` gives token counts per call — useful for reporting cost back to the user.

Media commands with `-o json` return artifact metadata instead of a bare path:

```json
{ "kind": "image", "mime_type": "image/jpeg", "path": "/abs/path/hero.jpg",
  "size_bytes": 2914159, "status": "completed" }
```

`--dry-run -o json` returns the resolved request with credentials omitted:

```json
{ "dry_run": true, "request": { "method": "POST",
  "url": "https://generativelanguage.googleapis.com/v1beta/interactions",
  "headers": { "Accept": ["text/event-stream"], "Content-Type": ["application/json"] },
  "body": { "input": "hi", "model": "gemini-3.8-flash", "stream": true } } }
```

## `--schema` to `--body`

Short flags cover the common cases; `--body` reaches the whole Interactions API request
while keeping the CLI's file writing and error handling.

```bash
gemini-api image --schema > image-schema.json      # JSON Schema draft 2020-12

cat > hero.json <<'JSON'
{
  "model": "gemini-nano-banana-2.1",
  "input": "A robot mascot in a sunlit workshop, space on the left for a headline. No text.",
  "response_format": { "type": "image", "aspect_ratio": "16:9", "image_size": "2K" },
  "store": false,
  "stream": false
}
JSON

gemini-api image --body @hero.json --out ./assets/hero.jpg --dry-run -o json
gemini-api image --body @hero.json --out ./assets/hero.jpg -o json
```

`--body` accepts inline JSON, `@path`, or `@-` for stdin. It merges with the short flags
and **rejects duplicate keys** — and the positional prompt counts as `input`, while `-m`
counts as `model`:

```
gemini-api generate "hi" --body '{"input":"x"}'   # exit 2: "input" set by both
gemini-api generate "hi" --body '{"store":false}' # fine, merges
```

So a full `--body @req.json` payload takes no positional prompt. Adding one orthogonal
key next to the short flags is the common case and works.

`--body` and `--schema` exist on `generate`, `image`, `music`, `video`, and `agent run`
only. `tts`, `analyze`, and `transcribe` reject both flags. The schema is a
`oneOf` over interaction variants. `ModelInteraction` includes `input`, `model`,
`system_instruction`, `tools`, `response_format`, `response_modalities`,
`safety_settings`, `generation_config`, `store`, `stream`, `background`, `service_tier`,
`previous_interaction_id`, `cached_content`, `continuation_token`, `labels`,
`webhook_config`, `environment`, `environment_id`, `response_mime_type`, plus read-only
`id`, `status`, `created`, `updated`. Read the schema rather than this list.

Multi-turn state lives on the server. Keep the ID, pass `previous_interaction_id`:

```bash
T1=$(gemini-api generate "Propose 3 indexing strategies for a time-series table." \
  --stream=false --jq '.id')
gemini-api generate "Compare #2 and #3 for write-heavy loads." \
  --previous-interaction-id "$T1" --stream=false
```

## Gotchas

Only things not already stated above.

- **Piped stdin is parsed as the JSON request body.** `echo text | gemini-api generate
  "hi"` exits 2 with "failed to parse stdin as JSON". Pass `--stdin` to send piped text
  as the prompt. The most likely first-run failure, and it also bites any harness that
  hands the process a non-empty pipe.
- **`--body` collides with the positional prompt (`input`) and `-m` (`model`)**, not just
  with other `--body` keys. See the section above.
- **`agent list` lists *your* agent definitions, not the built-in managed agents.** On a
  fresh project it returns `{"agents":[]}`. Built-in agent IDs come from
  `gemini-api agent run --help`.
- **Agent IDs and interaction IDs are different resources.** `agent status` takes an
  *interaction* ID; `agent get` takes an *agent* ID.
- **`-o json` while streaming gives the raw NDJSON event stream**, not one object. Pair
  `-o json` and `--jq` with `--stream=false`.
- **`generate`, `image`, `music`, `video`, and `agent run` store the interaction and it
  stays retrievable by ID** (verified: `agent status` on a finished `generate` returns its
  status and model). `tts`, `analyze`, and `transcribe` send `store:false` themselves
  (verified by dry-run).
- **Progress chatter goes to stderr, payload to stdout** (verified: `analyze` prints
  "Analyzing 1 input(s)…" on stderr and only the answer on stdout). Command substitution
  captures the clean value; dropping stderr hides real errors.
- **`tts` ignores the extension you ask for.** Output is WAV whatever `--out` says.
- **Default output paths land in the working directory** — `gemini-<kind>-<ts>-<rand>.<ext>`,
  except `transcribe`, which uses `transcript-<ts>-<rand>.<ext>`. Always pass `--out`.
- **Interactive prompting is off by default** (`--interactive` defaults to false), so a
  script does not need `--no-interactive` to avoid a hang. Just never pass `--interactive`
  from one; off a TTY its forms fall back to blocking line prompts on stdin.
- **With no credential the CLI still makes the call** and maps the 403 to exit 3, with a
  hint telling the agent to stop and ask the user rather than run `configure` itself.
- **Beta, breaking changes between releases.** Pin a version in CI.
