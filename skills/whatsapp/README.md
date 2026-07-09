# WhatsApp Skill (pywhats)

An AI agent skill for sending and receiving WhatsApp messages via the
**unofficial** linked-device client [`pywhats`](https://pypi.org/project/pywhats/)
— pair with a QR code, send text and images, message groups, mark read, set
presence/typing, and stream inbound events as JSON lines. Works with Claude
Code, Gemini CLI, Cursor, OpenAI Codex, Goose, and other AI clients supporting
the [Agent Skills Standard](https://agentskills.io).

> **Not** the official WhatsApp Business / Cloud API. This links as a companion
> device (like WhatsApp Web) to a personal WhatsApp account.

## Features

- **Pair** — One-time QR link; ASCII QR printed in the terminal
- **Send text / image** — 1:1 chats; images: jpg/png/webp up to 16MB
- **Groups** — Fetch metadata (JSON) and send group text
- **Receipts** — Blue-tick messages (`mark-read`); optional auto-read in `listen`
- **Presence / typing** — Global available/unavailable; composing/paused/recording
- **Listen** — Long-running JSONL event stream for every pywhats event
- **Managed venv** — Auto-creates `$PYWHATS_HOME/venv` and installs `pywhats` on first run

## Requirements

- Python 3.11+
- `bash` (for the bootstrap script)
- Network access to WhatsApp + PyPI on first bootstrap
- A phone with WhatsApp to scan the pair QR

## Caveats

`pywhats` is a young library (0.1.x, text/image only) and an **unofficial**
client. Automating a personal account can violate WhatsApp's ToS and risk a
ban — use a personal/test number, not production.

In testing we found WhatsApp sometimes removes freshly linked devices within
a minute or so if the account has seen rapid pair/unpair cycles. The `pair`
command detects this and prints recovery steps (remove linked devices on the
phone, wait ~15–20 minutes, pair once).

## Quick Start

### 1. Pair a device

```bash
skills/whatsapp/scripts/wa.py pair
```

On first run this will:

1. Create `$HOME/.pywhats/venv` (or `$PYWHATS_HOME/venv`), streaming progress
2. `pip install "pywhats>=0.1.1,<0.2"`
3. Print an ASCII QR code (also saved as `<session>.qr.png` for terminals
   where the ASCII render isn't scannable)

On your phone: **WhatsApp → Linked Devices → Link a Device** and scan the QR.
When pairing succeeds the CLI prints the device JID, waits briefly for history
sync, saves the session, and exits.

Re-running `pair` on an already-paired session is a no-op (exits 0).

### 2. Send a message

```bash
skills/whatsapp/scripts/wa.py send-text 15550001234 "hello from the skill"
skills/whatsapp/scripts/wa.py send-image 15550001234 ./photo.jpg --caption "hi"
```

`<to>` accepts a bare international number without `+`, or a full JID
(`...@s.whatsapp.net` / `...@g.us`).

### 3. Listen for events

```bash
skills/whatsapp/scripts/wa.py listen --read
# one JSON object per line, e.g.
# {"event":"message","id":"...","chat":"...","text":"hi",...}
```

## Command Reference

| Command | Description | Key options |
|---------|-------------|-------------|
| `pair` | Link a new companion device (ASCII QR) | `--session NAME` |
| `send-text <to> <text>` | Send 1:1 text; prints message id | `--session` |
| `send-image <to> <path>` | Send image; prints message id | `--caption`, `--session` |
| `group-info <gid>` | Group metadata as JSON | `--session` |
| `group-send <gid> <text>` | Group text (resolves participants) | `--session` |
| `mark-read <chat> <ids...>` | Blue-tick message ids | `--sender` (groups), `--session` |
| `presence <available\|unavailable>` | Global presence | `--session` |
| `typing <to> <composing\|paused>` | Chat presence / typing | `--media audio`, `--session` |
| `listen` | Stream events as JSON lines until Ctrl-C | `--read`, `--subscribe JID` (presence), `--events LIST`, `--session` |

Global options (go **before** the subcommand, e.g. `wa.py --session work pair`):

- `--session NAME` — session file `$PYWHATS_HOME/<NAME>.session` (default
  `default`, or env `PYWHATS_SESSION`)

Presence events only flow after subscribing: `wa.py listen --subscribe 15550001234
--events presence` (this also marks the linked device "available").

Exit codes: `0` success, `1` error / unpaired / logged out, `2` usage error,
`130` interrupted (Ctrl-C).

## Runtime layout

| Path | Purpose |
|------|---------|
| `$PYWHATS_HOME` | Default `$HOME/.pywhats` |
| `$PYWHATS_HOME/venv` | Managed Python venv with `pywhats` |
| `$PYWHATS_HOME/<NAME>.session` | Pairing credentials |
| `$PYWHATS_HOME/<NAME>.session.signal.db` | Signal ratchet / keys |

Bootstrap script: `scripts/_bootstrap.sh` — creates the venv if needed, ensures
`pywhats` + `qrcode` are importable, prints the absolute path to the venv
python as its last stdout line. `wa.py` re-execs under that interpreter when
started with a system `python3` that lacks pywhats.

## Multi-account

```bash
wa.py --session personal pair
wa.py --session work pair
wa.py --session work send-text 15550001234 "from work session"
export PYWHATS_SESSION=work   # default for subsequent commands
```

## Claude Code / agent usage

When the agent needs to message you on WhatsApp:

```bash
# after a one-time pair
skills/whatsapp/scripts/wa.py send-text "$MY_PHONE" "Deploy finished ✅"
```

For full method/event docs when writing custom Python against pywhats, see
[references/api.md](references/api.md).

## Security notes

- A paired session file is equivalent to a logged-in WhatsApp Web session —
  protect `$PYWHATS_HOME` (filesystem permissions, backups).
- `pywhats` is an unofficial reimplementation of the protocol — do not rely
  on it for sensitive traffic.
- Prefer a secondary/test WhatsApp number for automation.

## License

Apache 2.0 (skill packaging). `pywhats` is separately licensed on PyPI.
