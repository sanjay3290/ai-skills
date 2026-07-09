# pywhats API reference

Import surface, methods, events, and worked examples for the unofficial
WhatsApp multi-device client (`pip install pywhats`, version `0.1.x`).

This skill manages a venv at `$PYWHATS_HOME/venv` (default `~/.pywhats/venv`).
Prefer the skill CLI for day-to-day use:

```bash
skills/whatsapp/scripts/wa.py pair
skills/whatsapp/scripts/wa.py send-text 15550001234 "hello"
```

Or run your own scripts with the managed interpreter:

```bash
# print interpreter path (creates venv + installs pywhats on first run)
PY=$(bash skills/whatsapp/scripts/_bootstrap.sh)
"$PY" your_script.py
# or: "$HOME/.pywhats/venv/bin/python" your_script.py
# PYWHATS_HOME defaults to $HOME/.pywhats
```

## Contents
- Imports & JIDs
- Client constructor
- Client methods (send/receive/groups/receipts/presence/media)
- Events & payloads
- Worked examples
- Errors

## Imports & JIDs

```python
from pywhats import Client
from pywhats.binary.jid import parse_jid, jid_to_str

peer  = parse_jid("15550001234@s.whatsapp.net")   # a person: country code + number
group = parse_jid("120363000000000000@g.us")      # a group
```

A `JID` is `user` / `server` / `device`. `s.whatsapp.net` = person (PN),
`g.us` = group, `lid` = the newer "linked ID" addressing (inbound senders
often appear as `<n>@lid` — just compare/echo them, no manual construction
needed).

Bare phone numbers (international format, no `+`) are normalized by the
skill CLI to `<number>@s.whatsapp.net` before `parse_jid`.

## Client constructor

```python
Client(
    session_path: str | None = None,   # file to persist pairing + Signal keys; None = ephemeral
    *,
    ws_url: str | None = None,         # override the WhatsApp WS endpoint (tests only)
    media_http_get=None,               # inject an HTTP GET for media (defaults to stdlib urllib)
    media_http_post=None,              # inject an HTTP POST for media upload
)
```

`session_path="x.session"` also creates `x.session.signal.db` alongside it.
Same path on the next run ⇒ silent login-resume (no QR).

The skill stores sessions at `$PYWHATS_HOME/<NAME>.session`
(default `~/.pywhats/default.session`).

## Client methods

All are `async`. Connection lifecycle:

| Method | Purpose |
|---|---|
| `await client.connect()` | Open WS, run handshake, pair (fresh) or resume (saved session). |
| `await client.wait_closed()` | Block until the connection closes. |
| `await client.disconnect()` | Close cleanly. |
| `client.on(event)` | Decorator registering an **async** handler (see Events). |
| `client.device` | The `DeviceStore` (has `.jid` once paired). |

Messaging (call these from the **main coroutine**, or via
`asyncio.create_task` inside a handler — never bare `await` inside a handler):

| Method | Signature | Notes |
|---|---|---|
| Send text | `send_text(chat: JID, text: str) -> Message` | 1:1 or any chat JID. |
| Send image | `send_image(chat, image_bytes, *, mimetype="image/jpeg", caption="", width=0, height=0) -> Message` | Encrypts + uploads to CDN, sends `ImageMessage`. |
| Send to group | `send_group_text(group: JID, text: str, participants: list[JID]) -> Message` | Pass the member JIDs (get them from `get_group_info`). |
| Group metadata | `get_group_info(group: JID) -> GroupInfo` | Participants + admin ranks over `w:g2`. |
| Mark read | `mark_read(chat: JID, message_ids: list[str], *, sender: JID \| None = None) -> None` | `sender` = participant for group receipts. |
| Global presence | `send_presence(state: str) -> None` | `state`: `"available"` / `"unavailable"`. |
| Subscribe presence | `subscribe_presence(jid: JID) -> None` | Then you get `presence` events for that peer. |
| Typing indicator | `send_chat_presence(jid: JID, state: str, *, media: str \| None = None) -> None` | `state`: `"composing"` / `"paused"`; `media="audio"` for recording. |
| Download media | `download_media(info) -> bytes` | Decrypts an inbound attachment described by a `MediaInfo` (`direct_path`, `media_key`, integrity hashes, `media_type`). Requires an active connection. |

`send_*` block until the server ACKs and return a `Message`. `get_group_info`
and `download_media` block on a server/CDN round-trip — this is exactly why
they deadlock if awaited inside an event handler.

### MediaInfo (inbound download)

```python
from pywhats.media import MediaInfo  # or pywhats.media.download.MediaInfo

# Fields used by download_media:
#   direct_path: str
#   media_key: bytes          # 32-byte key
#   file_sha256: bytes
#   file_enc_sha256: bytes
#   media_type: str           # e.g. WhatsApp Image Keys constant
#   mms_type: str = ""        # optional CDN type hint
```

**Limitation (pywhats 0.1.x):** the live `message` event is **text-only** —
its `Message` payload has just `id, chat, sender, text, timestamp, from_me`
and carries **no** media descriptor, so inbound attachments cannot currently
be auto-downloaded from a `message` event (the `wa.py listen` subcommand does
not attempt it). `download_media(info)` works only if you obtain a
`MediaInfo` by other means; remember to call it via `create_task`, never
bare-`await`, inside a handler.

## Events & payloads

Register with `@client.on("<name>")` on an **async** function. Payload is a
slotted dataclass (fields below).

| Event | Payload | Fields |
|---|---|---|
| `qr` | `str` | the QR text (render/scan it) |
| `paired` | `JID` | our device JID after a fresh link |
| `connected` | *(none)* | login/resume succeeded |
| `message` | `Message` | `id, chat, sender, text, timestamp, from_me` (group msg ⇒ `chat.server=="g.us"`, `sender` = participant) |
| `receipt` | `Receipt` | `from_jid, message_ids, type, timestamp, participant` (`type==""` grey/delivered, `"read"` blue) |
| `presence` | `Presence` | `from_jid, unavailable, last_seen` |
| `chat_presence` | `ChatPresence` | `from_jid, state, media` (typing/recording) |
| `history_sync` | `HistorySync` | `sync_type, progress, chunk_order, conversation_count, message_count, conversation_ids, pushnames` |
| `mute` | `Mute` | `jid, muted, mute_end_timestamp, timestamp` |
| `pin` | `Pin` | `jid, pinned, timestamp` |
| `archive` | `Archive` | `jid, archived, timestamp` |
| `contact` | `Contact` | `jid, first_name, full_name, timestamp` |
| `pushname` | `PushName` | `name, timestamp` |
| `decrypt_error` | `(message_id: str, reason: str)` | a message failed to decrypt |
| `logged_out` | `reason: str` | server rejected/removed the device (401) |
| `disconnected` | *(none)* | connection closed |

`GroupInfo`: `jid, subject, owner, participants, announce, locked`.
`GroupParticipant`: `jid, is_admin, is_super_admin`.

## ⚠️ Never bare-await Client calls inside a handler

Event handlers run **inline on the receive loop**. Awaiting a Client method
that waits on a server reply deadlocks the connection. Always:

```python
asyncio.create_task(client.send_text(msg.chat, "pong"))   # ✅
# await client.send_text(...)                             # ❌ deadlock
```

Awaiting from the main coroutine (outside any handler) is fine.

## Worked examples

### Send an image after connecting

```python
import asyncio
from pathlib import Path
from pywhats import Client
from pywhats.binary.jid import parse_jid

async def main():
    # Session path — skill default is ~/.pywhats/default.session
    client = Client(session_path="wa.session")

    @client.on("qr")                      # only fires if not yet paired
    async def on_qr(qr):
        print("scan:\n", qr)

    await client.connect()
    img = Path("photo.jpg").read_bytes()
    msg = await client.send_image(parse_jid("15550001234@s.whatsapp.net"),
                                  img, mimetype="image/jpeg", caption="hi")
    print("sent", msg.id)
    await client.disconnect()

asyncio.run(main())
```

Every handler **must be an async function** — `Client._emit` awaits each one,
so a plain lambda/sync function raises `TypeError` on every event. Handlers
that only print are fine as `async def`; only handlers that await server
round-trips need `create_task`.

### Receive + reply in a group (handler dispatches off-loop)

```python
@client.on("message")
async def on_message(msg):
    if msg.chat.server != "g.us":
        return
    print("group msg:", msg.text, "from", msg.sender)

    async def reply():
        info = await client.get_group_info(msg.chat)          # safe: we're in a task
        members = [p.jid for p in info.participants]
        await client.send_group_text(msg.chat, "got it", members)
    asyncio.create_task(reply())
```

### Read receipts + presence

```python
@client.on("message")
async def _(msg):
    # sender/participant is group-receipt semantics only — pass None for 1:1.
    sender = msg.sender if msg.chat.server == "g.us" else None
    asyncio.create_task(client.mark_read(msg.chat, [msg.id], sender=sender))

# from the main coroutine:
await client.send_presence("available")
await client.subscribe_presence(parse_jid("15550001234@s.whatsapp.net"))
await client.send_chat_presence(peer, "composing")   # "typing…"
```

### History sync (only on a FRESH pair)

```python
@client.on("history_sync")
async def _(ev):
    print(ev.sync_type, ev.conversation_count, "chats,", ev.message_count, "msgs")
```

The four bootstrap blobs (`INITIAL_BOOTSTRAP`, `INITIAL_STATUS_V3`,
`NON_BLOCKING_DATA`, `PUSH_NAME`) arrive within a few seconds of a *fresh*
link and are downloaded/decrypted automatically. They do **not** re-arrive
on a resume.

### Skill CLI equivalents

`--session NAME` is a global option and goes **before** the subcommand
(e.g. `wa.py --session work pair`).

| Goal | Command |
|---|---|
| Pair | `wa.py [--session NAME] pair` |
| Send text | `wa.py send-text <to> <text>` |
| Send image | `wa.py send-image <to> <path> [--caption C]` (jpg/png/webp, ≤16MB) |
| Group info | `wa.py group-info <gid>` |
| Group send | `wa.py group-send <gid> <text>` |
| Mark read | `wa.py mark-read <chat> <ids...> [--sender JID]` |
| Presence | `wa.py presence available\|unavailable` |
| Typing | `wa.py typing <to> composing\|paused [--media audio]` |
| Listen (JSONL) | `wa.py listen [--read] [--subscribe JID …] [--events LIST]` — presence events require `--subscribe` |

## Errors

- `pywhats.errors.NotConnected` — called a send before `connect()`.
- `pywhats.errors.PairingFailed` — the QR window expired; reconnect to get a
  fresh QR (loop `connect()` on this exception).
- `logged_out` event with reason `401` — device unlinked or reaped (often
  device churn; remove linked devices, wait ~15–20 min, re-pair once).
  Requires pywhats >= 0.1.1, which the skill pins.
