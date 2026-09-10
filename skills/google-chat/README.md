# Google Chat Skill

An AI agent skill for interacting with Google Chat - send, read, edit and react to messages, share files, and manage spaces and DMs. Works with Claude Code, Gemini CLI, Cursor, OpenAI Codex, Goose, and other AI clients supporting the [Agent Skills Standard](https://agentskills.io).

## Features

- **List & Find Spaces** - View or search the spaces you're a member of
- **Send Messages** - Post to any space, or DM a user directly
- **Read Messages** - Compact conversation history, ~14x smaller than raw API output
- **Edit & Delete** - Fix or remove messages you sent
- **Reactions** - React to any message with an emoji
- **Threads** - Reply inside an existing thread
- **Media** - Send images, PDFs and other files, several at once
- **Members** - List who is in a space
- **Aliases** - Optional short names for the people and spaces you use daily
- **Dry Run** - Preview any write as a request, without sending it
- **Create Spaces** - Set up new spaces with members

Lightweight alternative to the full [Google Workspace MCP server](https://github.com/gemini-cli-extensions/workspace).

> **⚠️ Requires Google Workspace account.** Personal Gmail accounts are not supported.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Authenticate

```bash
python scripts/auth.py login
```

This opens a browser for Google OAuth. Tokens are stored securely in your system keyring.

### 3. Test connection

```bash
python scripts/auth.py status
```

## Usage Examples

```bash
# Read a space (compact output; add --raw for full JSON)
python scripts/chat.py get-messages spaces/AAAA123 --limit 10

# Send a message, then fix it
python scripts/chat.py send-message spaces/AAAA123 "Hello team!"
python scripts/chat.py edit-message spaces/AAAA123/messages/XYZ "Hello team - corrected."

# React, reply in a thread, delete
python scripts/chat.py add-reaction spaces/AAAA123/messages/XYZ 👍
python scripts/chat.py reply-in-thread spaces/AAAA123 spaces/AAAA123/threads/T "Following up."
python scripts/chat.py delete-message spaces/AAAA123/messages/XYZ

# Share files
python scripts/chat.py send-media spaces/AAAA123 "Latest mocks" --file a.png --file b.png

# Direct messages
python scripts/chat.py send-dm user@example.com "Hey, quick question..."

# Preview without sending
python scripts/chat.py --dry-run send-message spaces/AAAA123 "Not sent."
```

## Command Reference

Global flags: `--raw` (full JSON instead of compact output), `--dry-run` (print the request instead of sending it).

| Command | Description | Arguments |
|---------|-------------|-----------|
| `list-spaces` | List all spaces | - |
| `find-space <name>` | Find spaces by name (punctuation-insensitive) | space name |
| `list-members <space>` | List members of a space | space |
| `get-messages <space>` | Get messages from space | space, `--limit`, `--page-token` |
| `get-message <message>` | Get one message | message name |
| `list-threads <space>` | List threads | space, `--limit` |
| `send-message <space> <text>` | Send message | space, text, `--file` |
| `send-media <space> [text]` | Send files with optional caption | space, `--file` (repeatable) |
| `send-dm <email> <text>` | Send direct message | user email, text, `--file` |
| `reply-in-thread <space> <thread> <text>` | Reply in a thread | space, thread, text |
| `edit-message <message> <text>` | Edit a message you sent | message name, new text |
| `delete-message <message>` | Delete a message you sent | message name, `--force` |
| `add-reaction <message> <emoji>` | React to a message | message name, emoji |
| `find-dm <email>` | Find/create DM space | user email |
| `setup-space <name> [emails...]` | Create space | name, member emails |

## Space and Message Name Formats

Google Chat uses `spaces/AAAA123` for spaces and `spaces/AAAA123/messages/XYZ` for messages. Get space names from `list-spaces` or `find-space`; message names are returned by the send commands and listed by `get-messages`.

## Optional Aliases

Copy `directory.example.json` to `directory.json` to map short names to the people and spaces you use daily:

```json
{
  "users":  { "alex": "alex@example.com" },
  "spaces": { "team": { "id": "spaces/AAAAxxxxxxx", "name": "My Team" } }
}
```

`send-message team "Deploying now"` and `send-dm alex "..."` then resolve locally with no API call. `directory.json` is personal and gitignored; the feature is optional and full emails and IDs keep working without it.

## Attachment Behaviour

Google Chat only accepts multiple attachments on a single message when all of them are images or videos. `send-media` splits a mixed batch (say a PNG and a PDF) into one message per file automatically, putting the caption on the first.

## Token Management

Tokens stored securely using the system keyring:
- **macOS**: Keychain
- **Windows**: Windows Credential Locker
- **Linux**: Secret Service API (GNOME Keyring, KDE Wallet)

Service name: `google-chat-skill-oauth`

## Troubleshooting

### "Failed to get access token"
Run `python scripts/auth.py login` to authenticate.

### "Space not found"
Verify the space ID format (`spaces/AAAA123`). Use `list-spaces` to get valid IDs.

### "Permission denied"
You may not be a member of the space. Check your Google Chat membership.

### "You cannot edit/delete this message"
Only messages sent by the authenticated user can be edited or deleted.

### "Can't create a message that contains multiple attachments..."
Chat allows several attachments on one message only when all are media. `send-media` handles this by splitting the batch; if you hit this calling the API directly, send the non-media files separately.

## License

Apache 2.0
