---
name: whatsapp
description: "Send and receive WhatsApp messages via the unofficial linked-device client pywhats (pip install pywhats) — pair with QR, send text/images, group chat, read receipts, presence/typing, and a long-running JSON event stream. Use when the user wants to script WhatsApp as a linked companion device (like WhatsApp Web), pair a device, send a WhatsApp from Python, or listen for inbound messages. Triggers: 'whatsapp', 'send whatsapp', 'pair whatsapp', 'pywhats', 'linked device', 'whatsapp web client'. NOT the official WhatsApp Business/Cloud API."
---

# WhatsApp (pywhats)

Drive a WhatsApp account as a **linked companion device** (like WhatsApp Web)
from async Python via [`pywhats`](https://pypi.org/project/pywhats/) (pre-alpha,
text/image only). This is an **unofficial** multi-device client — **not** the
official WhatsApp Business / Cloud API.

CLI entrypoint: `scripts/wa.py` (auto-bootstraps a managed venv on first run).

## Mental model

- **Pairing = one-time QR scan.** `wa.py pair` shows an ASCII QR; scan it in
  WhatsApp → Linked Devices. Credentials persist to
  `$PYWHATS_HOME/<session>.session` (+ `.signal.db`).
- **Resuming = silent.** Later commands reconnect with the same session — no QR.
- **JIDs address chats.** Bare phone `15550001234` → `15550001234@s.whatsapp.net`;
  groups use `...@g.us`.
- **Events are how you receive.** `wa.py listen` prints one JSON object per event.

## ⚠️ Never bare-await Client calls inside a handler

Event handlers run **inline on the receive loop**. Awaiting `send_*`,
`mark_read`, `get_group_info`, `download_media`, etc. inside a handler
**deadlocks** the connection. Always `asyncio.create_task(...)`. The `listen`
subcommand already does this for `--read`.

## Commands

```bash
scripts/wa.py pair                                          # one-time QR pair
scripts/wa.py send-text 15550001234 "hello"                 # 1:1 text
scripts/wa.py send-image 15550001234 photo.jpg --caption hi # 1:1 image
scripts/wa.py group-info 120363000000000000@g.us            # group metadata JSON
scripts/wa.py group-send 120363000000000000@g.us "hi all"   # group text
scripts/wa.py mark-read 15550001234 MSGID [--sender JID]    # blue ticks
scripts/wa.py presence available                            # global presence
scripts/wa.py typing 15550001234 composing [--media audio]  # typing indicator
scripts/wa.py listen --read --events message,receipt        # JSONL event stream
scripts/wa.py --session work send-text 15550001234 "hi"     # named session
```

| Command | Behavior |
|---------|----------|
| `pair` | Fresh link via ASCII QR; idempotent if already paired |
| `send-text <to> <text>` | Send 1:1 text; print message id |
| `send-image <to> <path> [--caption C]` | Send image (jpg/png/webp, ≤16MB); print id |
| `group-info <gid>` | Print group JSON (subject, owner, participants, …) |
| `group-send <gid> <text>` | Resolve members then send group text; print id |
| `mark-read <chat> <ids...>` | Blue-tick; `--sender` for groups |
| `presence <available\|unavailable>` | Global presence |
| `typing <to> <composing\|paused>` | Chat presence; optional `--media audio` |
| `listen` | Long-running JSON lines; `--read`, `--events`, `--subscribe JID` (required for presence events) |

Global: `--session NAME` (default `default`, or env `PYWHATS_SESSION`) —
goes **before** the subcommand: `wa.py --session work pair`.

## Sessions / multi-account

```
$PYWHATS_HOME/                 # default: ~/.pywhats
  venv/                        # managed Python + pywhats
  default.session              # --session default
  default.session.signal.db
  work.session                 # --session work
```

Override home with `PYWHATS_HOME`. Unpaired / logged-out sessions print a clear
message to re-run `wa.py --session <name> pair`.

If `pair` reports the device was logged out right after scanning, that is
WhatsApp device-churn reaping, not a failure of the skill — the dead session is
deleted automatically; follow the recovery steps it prints (remove linked
devices, wait 15–20 min, pair once).

## Full reference

[references/api.md](references/api.md) — every `Client` method, every event
payload, JID construction, and the `download_media` note.
