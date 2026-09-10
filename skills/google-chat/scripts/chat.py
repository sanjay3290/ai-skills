#!/usr/bin/env python3
"""
Google Chat API operations.
Aliases for users and spaces live in ../directory.json.
"""

import argparse
import json
import mimetypes
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional

from auth import get_valid_access_token

CHAT_API_BASE = "https://chat.googleapis.com/v1"
CHAT_UPLOAD_BASE = "https://chat.googleapis.com/upload/v1"

DIRECTORY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "directory.json"
)

DRY_RUN = False


def load_directory() -> dict:
    """
    Load optional aliases from directory.json.

    The file is personal to each user and is not shipped with the skill; without
    it every command still works, you just pass full emails and 'spaces/...' names.
    """
    if not os.path.isfile(DIRECTORY_PATH):
        return {"users": {}, "spaces": {}}

    try:
        with open(DIRECTORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise SystemExit("Could not read " + DIRECTORY_PATH + ": " + str(e))

    return {"users": data.get("users") or {}, "spaces": data.get("spaces") or {}}


DIRECTORY = load_directory()
USER_EMAIL_ALIASES = DIRECTORY["users"]
KNOWN_SPACES = DIRECTORY["spaces"]


def resolve_user(identifier: str) -> str:
    """Resolve a teammate name alias to an email address."""
    normalized = identifier.strip()
    if "@" in normalized:
        return normalized
    return USER_EMAIL_ALIASES.get(normalized.lower(), normalized)


def resolve_space(identifier: str) -> str:
    """Resolve a space shorthand to a space resource name."""
    normalized = identifier.strip()
    if normalized.startswith("spaces/"):
        return normalized
    entry = KNOWN_SPACES.get(normalized.lower())
    if entry:
        return entry["id"]

    if not KNOWN_SPACES:
        raise SystemExit(
            "Expected a 'spaces/...' name, got '" + identifier + "'.\n"
            "Find one with: chat.py find-space \"<display name>\"\n"
            "To use short aliases instead, copy directory.example.json to directory.json."
        )

    known = ", ".join(sorted(KNOWN_SPACES))
    raise SystemExit(
        "Unknown space '" + identifier + "'. Use a full 'spaces/...' name, or one of: " + known
        + "\nTo look one up: chat.py find-space \"<display name>\""
    )


def resolve_message(identifier: str) -> str:
    """Validate a message resource name (spaces/X/messages/Y)."""
    normalized = identifier.strip()
    parts = normalized.split("/")
    if len(parts) == 4 and parts[0] == "spaces" and parts[2] == "messages":
        return normalized
    raise SystemExit(
        "Invalid message name '" + identifier + "'. Expected 'spaces/<space>/messages/<message>'."
        "\nsend-message prints this name; get-messages lists it for each message."
    )


def api_request(
    method: str,
    endpoint: str,
    data: Optional[dict] = None,
    params: Optional[dict] = None,
) -> dict:
    """Make an authenticated request to the Google Chat API."""
    url = CHAT_API_BASE + "/" + endpoint
    if params:
        url += "?" + urllib.parse.urlencode(params)

    if DRY_RUN and method != "GET":
        return {"dryRun": True, "method": method, "url": url, "body": data}

    token = get_valid_access_token()
    if not token:
        return {"error": "Failed to get access token"}

    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data else None

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        return {"error": "HTTP " + str(e.code) + ": " + error_body}
    except urllib.error.URLError as e:
        return {"error": "Request failed: " + str(e.reason)}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response"}


# =============================================================================
# Media
# =============================================================================


def is_media(path: str) -> bool:
    mime_type = mimetypes.guess_type(path)[0] or ""
    return mime_type.startswith("image/") or mime_type.startswith("video/")


def upload_files(space_name: str, file_paths: list, text: str = "") -> dict:
    """
    Send uploaded files to a space.

    Chat only accepts several attachments on one message when every attachment
    is media (image/video). Anything else goes out as one message per file,
    with the caption on the first.
    """
    for path in file_paths:
        if not os.path.isfile(path):
            return {"error": "File not found: " + path}

    if len(file_paths) > 1 and not all(is_media(p) for p in file_paths):
        results = []
        for index, path in enumerate(file_paths):
            result = upload_batch(space_name, [path], text if index == 0 else "")
            if "error" in result:
                return {"error": result["error"], "sent": results}
            results.append(result)
        return {"messages": results}

    return upload_batch(space_name, file_paths, text)


def upload_batch(space_name: str, file_paths: list, text: str = "") -> dict:
    """Send exactly one message carrying the given files."""
    import requests as req_lib

    if DRY_RUN:
        return {
            "dryRun": True,
            "method": "POST",
            "url": CHAT_API_BASE + "/" + space_name + "/messages",
            "attachments": [os.path.basename(p) for p in file_paths],
            "text": text,
        }

    token = get_valid_access_token()
    if not token:
        return {"error": "Failed to get access token"}

    headers = {"Authorization": "Bearer " + token}
    attachments = []

    for path in file_paths:
        mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        filename = os.path.basename(path)

        with open(path, "rb") as f:
            upload_resp = req_lib.post(
                CHAT_UPLOAD_BASE + "/" + space_name + "/attachments:upload",
                headers=headers,
                files={
                    "metadata": ("metadata", json.dumps({"filename": filename}), "application/json"),
                    "file": (filename, f, mime_type),
                },
                params={"uploadType": "multipart"},
                timeout=120,
            )

        if upload_resp.status_code != 200:
            return {
                "error": "Upload of " + filename + " failed HTTP "
                + str(upload_resp.status_code) + ": " + upload_resp.text
            }

        token_ref = upload_resp.json().get("attachmentDataRef", {}).get("attachmentUploadToken")
        if not token_ref:
            return {"error": "Upload of " + filename + " returned no attachment token"}

        attachments.append({
            "contentName": filename,
            "contentType": mime_type,
            "attachmentDataRef": {"attachmentUploadToken": token_ref},
        })

    msg_resp = req_lib.post(
        CHAT_API_BASE + "/" + space_name + "/messages",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        data=json.dumps({"text": text, "attachment": attachments}),
        timeout=60,
    )

    if msg_resp.status_code != 200:
        return {"error": "Send failed HTTP " + str(msg_resp.status_code) + ": " + msg_resp.text}

    return msg_resp.json()


# =============================================================================
# Spaces
# =============================================================================


def list_spaces() -> dict:
    result = api_request("GET", "spaces")
    return {"spaces": result.get("spaces", [])} if "spaces" in result else result


def squash(value: str) -> str:
    """Lowercase and drop everything but letters and digits, so punctuation and
    spacing differences ('Health Frontend' vs 'Health - Frontend') still match."""
    return "".join(c for c in (value or "").lower() if c.isalnum())


def find_space_by_name(display_name: str) -> dict:
    result = list_spaces()
    if "error" in result:
        return result

    needle = squash(display_name)
    matching = [s for s in result["spaces"] if needle in squash(s.get("displayName"))]
    if matching:
        return {"spaces": matching}
    return {"error": "No space found matching: " + display_name}


def list_members(space_name: str) -> dict:
    return api_request("GET", space_name + "/members", params={"pageSize": 100})


def setup_space(display_name: str, user_emails: list) -> dict:
    memberships = [
        {"member": {"name": "users/" + resolve_user(email), "type": "HUMAN"}}
        for email in user_emails
    ]
    return api_request("POST", "spaces:setup", data={
        "space": {"spaceType": "SPACE", "displayName": display_name},
        "memberships": memberships,
    })


def find_dm(user: str) -> dict:
    return api_request("POST", "spaces:setup", data={
        "space": {"spaceType": "DIRECT_MESSAGE"},
        "memberships": [{"member": {"name": "users/" + resolve_user(user), "type": "HUMAN"}}],
    })


# =============================================================================
# Messages
# =============================================================================


def get_messages(space_name: str, page_size: int = 25, page_token: Optional[str] = None) -> dict:
    params = {"pageSize": page_size, "orderBy": "createTime desc"}
    if page_token:
        params["pageToken"] = page_token
    return api_request("GET", space_name + "/messages", params=params)


def get_message(message_name: str) -> dict:
    return api_request("GET", message_name)


def send_message(space_name: str, text: str, files: Optional[list] = None) -> dict:
    if files:
        return upload_files(space_name, files, text)
    return api_request("POST", space_name + "/messages", data={"text": text})


def reply_in_thread(space_name: str, thread: str, text: str) -> dict:
    thread_name = thread if thread.startswith("spaces/") else space_name + "/threads/" + thread
    return api_request(
        "POST",
        space_name + "/messages",
        data={"text": text, "thread": {"name": thread_name}},
        params={"messageReplyOption": "REPLY_MESSAGE_OR_FAIL"},
    )


def edit_message(message_name: str, text: str) -> dict:
    return api_request("PATCH", message_name, data={"text": text}, params={"updateMask": "text"})


def delete_message(message_name: str, force: bool = False) -> dict:
    params = {"force": "true"} if force else None
    result = api_request("DELETE", message_name, params=params)
    return {"deleted": message_name} if result == {} else result


def add_reaction(message_name: str, emoji: str) -> dict:
    return api_request("POST", message_name + "/reactions", data={"emoji": {"unicode": emoji}})


def send_dm(user: str, text: str, files: Optional[list] = None) -> dict:
    if DRY_RUN:
        # Resolving the DM space needs a live spaces:setup call, so report intent instead.
        return {
            "dryRun": True,
            "method": "POST",
            "url": "<DM space with " + resolve_user(user) + ">/messages",
            "body": {"text": text},
            "attachments": [os.path.basename(p) for p in (files or [])],
        }

    space_result = find_dm(user)
    if "error" in space_result:
        return space_result

    space_name = space_result.get("name")
    if not space_name:
        return {"error": "Failed to open DM space with " + resolve_user(user)}

    return send_message(space_name, text, files)


def list_threads(space_name: str, page_size: int = 25) -> dict:
    result = get_messages(space_name, page_size)
    if "error" in result:
        return result

    seen = set()
    threads = []
    for msg in result.get("messages", []):
        thread_name = msg.get("thread", {}).get("name")
        if thread_name and thread_name not in seen:
            threads.append(msg)
            seen.add(thread_name)

    return {"messages": threads, "nextPageToken": result.get("nextPageToken")}


# =============================================================================
# Output
# =============================================================================


def format_compact(result: dict) -> Optional[str]:
    """Render known shapes as compact text. Returns None if there is no compact form."""
    if "error" in result or "dryRun" in result:
        return None

    if "messages" in result:
        lines = []
        for msg in result["messages"]:
            sender = msg.get("sender", {})
            who = sender.get("displayName") or sender.get("name", "unknown")
            when = (msg.get("createTime") or "")[:19].replace("T", " ")
            text = (msg.get("text") or "").strip() or "(no text)"
            if msg.get("attachment"):
                names = ", ".join(a.get("contentName", "file") for a in msg["attachment"])
                text = text + "  [attached: " + names + "]"
            edited = " (edited)" if msg.get("lastUpdateTime") and msg.get("lastUpdateTime") != msg.get("createTime") else ""
            lines.append(when + "  " + who + edited + "\n  " + text + "\n  " + msg.get("name", ""))
        if result.get("nextPageToken"):
            lines.append("\n(more: --page-token " + result["nextPageToken"] + ")")
        return "\n".join(lines) if lines else "(no messages)"

    if "spaces" in result:
        lines = []
        for s in result["spaces"]:
            label = s.get("displayName") or "(DM)"
            lines.append(label.ljust(40) + " " + s.get("name", "") + "  [" + s.get("spaceType", "") + "]")
        return "\n".join(lines) if lines else "(no spaces)"

    if "memberships" in result:
        lines = []
        for m in result["memberships"]:
            member = m.get("member", {})
            label = member.get("displayName") or "(unknown)"
            lines.append(label.ljust(30) + " " + member.get("name", "") + "  [" + m.get("role", "") + "]")
        return "\n".join(lines) if lines else "(no members)"

    return None


def main():
    # Chat messages routinely contain em-dashes, arrows and emoji; Windows stdout
    # defaults to cp1252 and would raise UnicodeEncodeError when printing them.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Google Chat API operations")
    parser.add_argument("--raw", action="store_true", help="Print full JSON instead of compact output")
    parser.add_argument("--dry-run", action="store_true", help="Print the request for write ops instead of sending")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add(name, help_text):
        return subparsers.add_parser(name, help=help_text)

    add("list-spaces", "List all spaces")

    p = add("find-space", "Find spaces by display name (substring match)")
    p.add_argument("name")

    p = add("list-members", "List members of a space")
    p.add_argument("space")

    p = add("get-messages", "Get recent messages from a space")
    p.add_argument("space")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--page-token")

    p = add("get-message", "Get a single message by resource name")
    p.add_argument("message")

    p = add("send-message", "Send a message to a space")
    p.add_argument("space")
    p.add_argument("text", nargs="?", default="")
    p.add_argument("--file", action="append", dest="files", help="Attach a file (repeatable)")
    p.add_argument("--attachment", dest="attachment", help="Deprecated alias for --file")

    p = add("send-media", "Send one or more files to a space with an optional caption")
    p.add_argument("space")
    p.add_argument("text", nargs="?", default="")
    p.add_argument("--file", action="append", dest="files", required=True, help="File to send (repeatable)")

    p = add("send-dm", "Send a direct message")
    p.add_argument("user", help="Teammate name alias or email")
    p.add_argument("text", nargs="?", default="")
    p.add_argument("--file", action="append", dest="files")
    p.add_argument("--attachment", dest="attachment", help="Deprecated alias for --file")

    p = add("find-dm", "Find or create a DM space")
    p.add_argument("user")

    p = add("reply-in-thread", "Reply inside an existing thread")
    p.add_argument("space")
    p.add_argument("thread", help="Thread resource name, or just the thread id")
    p.add_argument("text")

    p = add("edit-message", "Edit the text of a message you sent")
    p.add_argument("message")
    p.add_argument("text")

    p = add("delete-message", "Delete a message you sent")
    p.add_argument("message")
    p.add_argument("--force", action="store_true", help="Also delete threaded replies under this message")

    p = add("add-reaction", "React to a message with an emoji")
    p.add_argument("message")
    p.add_argument("emoji")

    p = add("list-threads", "List distinct threads in a space")
    p.add_argument("space")
    p.add_argument("--limit", type=int, default=25)

    p = add("setup-space", "Create a new space with members")
    p.add_argument("name")
    p.add_argument("emails", nargs="+")

    args = parser.parse_args()

    global DRY_RUN
    DRY_RUN = args.dry_run

    files = list(getattr(args, "files", None) or [])
    if getattr(args, "attachment", None):
        files.append(args.attachment)

    c = args.command
    if c == "list-spaces":
        result = list_spaces()
    elif c == "find-space":
        result = find_space_by_name(args.name)
    elif c == "list-members":
        result = list_members(resolve_space(args.space))
    elif c == "get-messages":
        result = get_messages(resolve_space(args.space), args.limit, args.page_token)
    elif c == "get-message":
        result = get_message(resolve_message(args.message))
    elif c == "send-message":
        result = send_message(resolve_space(args.space), args.text, files)
    elif c == "send-media":
        result = upload_files(resolve_space(args.space), files, args.text)
    elif c == "send-dm":
        result = send_dm(args.user, args.text, files)
    elif c == "find-dm":
        result = find_dm(args.user)
    elif c == "reply-in-thread":
        result = reply_in_thread(resolve_space(args.space), args.thread, args.text)
    elif c == "edit-message":
        result = edit_message(resolve_message(args.message), args.text)
    elif c == "delete-message":
        result = delete_message(resolve_message(args.message), args.force)
    elif c == "add-reaction":
        result = add_reaction(resolve_message(args.message), args.emoji)
    elif c == "list-threads":
        result = list_threads(resolve_space(args.space), args.limit)
    elif c == "setup-space":
        result = setup_space(args.name, args.emails)
    else:
        result = {"error": "Unknown command: " + c}

    compact = None if args.raw else format_compact(result)
    if compact is not None:
        print(compact)
    else:
        print(json.dumps(result, indent=2))

    if isinstance(result, dict) and "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
