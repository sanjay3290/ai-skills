---
name: google-chat
description: |
  Interact with Google Chat - send, read, edit, delete and react to messages, share images
  and files, reply in threads, and manage spaces and DMs. Use when user asks to: send a
  message on Google Chat, read chat messages, list chat spaces, find a chat room, send a DM,
  share a screenshot or file, edit or delete something already sent, or create a new space.
  Lightweight alternative to full Google Workspace MCP server with standalone OAuth authentication.
license: Apache-2.0
metadata:
  author: sanjay3290
  version: "1.1"
---

# Google Chat

Lightweight Google Chat integration with standalone OAuth authentication. No MCP server required.

> **⚠️ Requires Google Workspace account.** Personal Gmail accounts are not supported.

Everything is sent as the authenticated user, so treat write commands as outward-facing:
confirm the exact text with the user before posting to a space, and never send to a channel
the user did not name.

## First-Time Setup

```bash
pip install -r requirements.txt
python scripts/auth.py login     # opens browser
python scripts/auth.py status    # verify
python scripts/auth.py logout
```

## Commands

All operations via `scripts/chat.py`. Auto-authenticates on first use if not logged in.

### Reading

```bash
python scripts/chat.py get-messages spaces/AAAA123 --limit 10
python scripts/chat.py get-messages spaces/AAAA123 --limit 10 --raw   # full JSON
python scripts/chat.py get-message spaces/AAAA123/messages/XYZ
python scripts/chat.py list-threads spaces/AAAA123
python scripts/chat.py list-spaces
python scripts/chat.py find-space "Project Alpha"    # ignores punctuation/spacing
python scripts/chat.py list-members spaces/AAAA123
```

Read output is compact by default — one block per message with its timestamp, sender, text
and resource name. That is roughly 14x smaller than the raw API payload, which matters when
an agent is paying for every token it reads. Use `--raw` when you need the full JSON.

### Writing

```bash
python scripts/chat.py send-message spaces/AAAA123 "Hello team!"
python scripts/chat.py send-dm user@example.com "Hey, quick question..."
python scripts/chat.py reply-in-thread spaces/AAAA123 spaces/AAAA123/threads/T "Following up."
python scripts/chat.py send-media spaces/AAAA123 "Latest mocks" --file a.png --file b.png
python scripts/chat.py edit-message spaces/AAAA123/messages/XYZ "Corrected text."
python scripts/chat.py delete-message spaces/AAAA123/messages/XYZ
python scripts/chat.py delete-message spaces/AAAA123/messages/XYZ --force   # has thread replies
python scripts/chat.py add-reaction spaces/AAAA123/messages/XYZ 👍
python scripts/chat.py setup-space "New Project" user1@example.com user2@example.com
python scripts/chat.py find-dm user@example.com
```

Add `--dry-run` to any write command to print the request instead of sending it. Use it when
wiring up or testing a flow so nothing lands in a real channel. (For `send-dm` it reports the
resolved recipient rather than the DM space, since resolving that needs a live call.)

## Editing and deleting

`send-message`, `send-dm` and `send-media` return the created message's `name`
(`spaces/X/messages/Y`) — that is what `edit-message`, `delete-message` and `add-reaction`
take. You can only edit or delete messages **you** sent. To fix an older message, find its
name with `get-messages` first.

## Attachments

`send-media` takes a repeatable `--file`. Google Chat accepts several attachments on one
message only when every attachment is media (image or video); a mixed batch is split
automatically into one message per file, with the caption on the first. `--attachment` is
still accepted as an alias for a single `--file`.

## Optional aliases

Typing full email addresses and `spaces/AAAA...` IDs is tedious, and having an agent call
`list-spaces` to find a channel it uses daily is slow. Copy `directory.example.json` to
`directory.json` and map short names:

```json
{
  "users":  { "alex": "alex@example.com" },
  "spaces": { "team": { "id": "spaces/AAAAxxxxxxx", "name": "My Team" } }
}
```

Then `send-message team "Deploying now"` and `send-dm alex "..."` both resolve locally, with
no API call. Full emails and `spaces/...` names keep working everywhere.

`directory.json` is personal and gitignored. It is entirely optional — without it every
command still works, and an unresolvable alias fails immediately with the list of valid ones
rather than silently falling back to a scan.

## Message formatting

Chat supports `*bold*`, `_italic_`, `~strike~`, `` `code` ``, triple-backtick code blocks, and
`<url|label>` links. It does **not** support Markdown headings, tables, or `[](  )` links —
they render literally.

## Token Management

Tokens stored securely using the system keyring:
- **macOS**: Keychain
- **Windows**: Windows Credential Locker
- **Linux**: Secret Service API (GNOME Keyring, KDE Wallet, etc.)

Service name: `google-chat-skill-oauth`. Expired tokens refresh automatically.
