#!/usr/bin/env python3
"""WhatsApp CLI dispatcher powered by the pywhats linked-device client.

Portable launcher: if ``pywhats`` (or ``qrcode``) is not importable under the
current interpreter, this script re-executes itself under the managed venv at
``$PYWHATS_HOME/venv`` (default ``~/.pywhats/venv``), building it first via
``_bootstrap.sh`` when needed. Calling ``python3 wa.py ...`` therefore works
on a fresh machine without a manual venv activate step. Bootstrap progress
streams to stderr so a first run is visibly installing, not hung.

Usage examples (after first pair)::

    wa.py pair
    wa.py send-text 15550001234 "hello"
    wa.py listen --read
    wa.py --session work send-text 15550001234 "hi"   # named session
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Bootstrap re-exec: ensure we are running under the managed pywhats venv.
# Staged via _WA_BOOTSTRAP_STAGE to guarantee termination:
#   stage 0 → blind execv into an existing venv python (fast path, no subprocess)
#   stage 1 → run _bootstrap.sh (creates/repairs the venv), execv its interpreter
#   stage 2 → still broken after bootstrap: hard error
# ---------------------------------------------------------------------------
import os
import pathlib
import subprocess
import sys


def _ensure_pywhats() -> None:
    try:
        import pywhats  # noqa: F401
        import qrcode  # noqa: F401  (ASCII QR for `pair`; guaranteed in the venv)

        return
    except ImportError:
        pass

    stage = os.environ.get("_WA_BOOTSTRAP_STAGE", "0")
    home = pathlib.Path(os.environ.get("PYWHATS_HOME", pathlib.Path.home() / ".pywhats"))
    venv_python = home / "venv" / "bin" / "python"
    script = os.path.abspath(__file__)

    if stage == "0" and venv_python.is_file():
        os.environ["_WA_BOOTSTRAP_STAGE"] = "1"
        os.execv(str(venv_python), [str(venv_python), script, *sys.argv[1:]])

    if stage in ("0", "1"):
        bootstrap = os.path.join(os.path.dirname(script), "_bootstrap.sh")
        if not os.path.isfile(bootstrap):
            print(f"error: pywhats not installed and bootstrap missing: {bootstrap}", file=sys.stderr)
            raise SystemExit(1)
        print("setting up the pywhats environment (a first run may take a minute)…", file=sys.stderr)
        # stdout carries the interpreter path; stderr (pip progress) streams through.
        result = subprocess.run(["bash", bootstrap], stdout=subprocess.PIPE, text=True)
        lines = [ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip()]
        if result.returncode != 0 or not lines or not os.path.isfile(lines[-1]):
            print("error: bootstrap failed — see messages above.", file=sys.stderr)
            raise SystemExit(1)
        os.environ["_WA_BOOTSTRAP_STAGE"] = "2"
        os.execv(lines[-1], [lines[-1], script, *sys.argv[1:]])

    print(
        "error: pywhats still not importable after bootstrap. "
        f"Remove {home / 'venv'} and re-run to rebuild.",
        file=sys.stderr,
    )
    raise SystemExit(1)


_ensure_pywhats()

# ---------------------------------------------------------------------------
# Real CLI (runs only after pywhats is importable).
# ---------------------------------------------------------------------------
import argparse
import asyncio
import contextlib
import json
import mimetypes
from typing import Any

from pywhats import Client
from pywhats.binary.jid import jid_to_str, parse_jid
from pywhats.errors import PairingFailed

# WhatsApp does not render image/gif ImageMessages (GIFs go out as video),
# so only these are accepted by send-image.
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 16 * 1024 * 1024

ALL_EVENTS = (
    "qr",
    "message",
    "receipt",
    "presence",
    "chat_presence",
    "history_sync",
    "mute",
    "pin",
    "archive",
    "contact",
    "pushname",
    "decrypt_error",
    "logged_out",
    "disconnected",
    "paired",
    "connected",
)

MAX_QR_WINDOWS = 5  # ~1 min each; unattended `pair` must not spin forever


class SessionDead(Exception):
    """Raised when the server logs the device out mid-command."""


def _pywhats_home() -> pathlib.Path:
    return pathlib.Path(os.environ.get("PYWHATS_HOME", pathlib.Path.home() / ".pywhats"))


def _session_path(name: str) -> pathlib.Path:
    home = _pywhats_home()
    home.mkdir(parents=True, exist_ok=True)
    return home / f"{name}.session"


def _to_jid(target: str) -> Any:
    """Accept a full JID, or a bare international number (leading '+' ok)."""
    t = target.strip()
    if "@" in t:
        return parse_jid(t)
    t = t.lstrip("+")
    if not t.isdigit():
        print(
            f"error: invalid recipient {target!r} — use an international number "
            "without '+' (e.g. 15550001234) or a full JID (...@s.whatsapp.net / ...@g.us)",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return parse_jid(f"{t}@s.whatsapp.net")


def _dm_jid(target: str) -> Any:
    jid = _to_jid(target)
    if jid.server == "g.us":
        print("error: that is a group JID — use group-send / group-info instead.", file=sys.stderr)
        raise SystemExit(2)
    return jid


def _group_jid(gid: str) -> Any:
    jid = _to_jid(gid)
    if jid.server != "g.us":
        print(f"error: group commands need a full group JID ending in @g.us (got {gid!r}).", file=sys.stderr)
        raise SystemExit(2)
    return jid


def _jid_field(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return jid_to_str(value)
    except Exception:  # noqa: BLE001
        return str(value)


def _pair_hint(session_name: str) -> str:
    # NOTE: --session is a global option and must come BEFORE the subcommand.
    return f"wa.py --session {session_name} pair"


def _logged_out_message(session_name: str, reason: str) -> None:
    print(
        f"LOGGED OUT (reason={reason}) — the linked device was removed; the session "
        f"is dead. Delete {_session_path(session_name)} (and .signal.db) and re-pair: "
        f"{_pair_hint(session_name)}",
        file=sys.stderr,
    )


def _delete_session(session: pathlib.Path) -> None:
    for p in (session, pathlib.Path(str(session) + ".signal.db")):
        with contextlib.suppress(OSError):
            p.unlink()


def _load_paired_client(session: pathlib.Path, session_name: str) -> Client:
    """Build the one Client for this command; exit 1 with guidance if unusable."""
    if not session.is_file():
        print(f"error: no session at {session}. Run: {_pair_hint(session_name)}", file=sys.stderr)
        raise SystemExit(1)
    try:
        client = Client(session_path=str(session))
    except Exception as exc:  # noqa: BLE001  (store corrupt / bad permissions)
        print(
            f"error: could not load session {session}: {exc}\n"
            f"Delete it and re-pair: {_pair_hint(session_name)}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    dev = client.device
    if dev is None or dev.jid is None:
        print(f"error: session {session} is not paired. Run: {_pair_hint(session_name)}", file=sys.stderr)
        raise SystemExit(1)
    return client


def _print_qr(qr_text: str, session: pathlib.Path) -> None:
    print("\n=== Scan this in WhatsApp → Linked Devices → Link a Device ===\n")
    png = pathlib.Path(str(session) + ".qr.png")
    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(qr_text)
        qr.make(fit=True)
        with contextlib.suppress(Exception):  # PNG fallback for unscannable terminals
            qr.make_image().save(png)
            print(f"(QR also saved to {png})")
        with contextlib.suppress(Exception):
            qr.print_ascii(invert=True)
            return
        with contextlib.suppress(Exception):
            qr.print_tty()
            return
    except Exception:  # noqa: BLE001
        pass
    print(qr_text)  # last resort: raw payload


@contextlib.asynccontextmanager
async def _connected(session: pathlib.Path, session_name: str):
    """Shared command scaffold: one Client, logout watch, clean disconnect.

    Yields ``(client, run)``. ``run(coro)`` races the operation against a
    ``logged_out`` event so a dead session fails fast with guidance instead of
    hanging until the ack timeout.
    """
    client = _load_paired_client(session, session_name)
    logout = asyncio.Event()

    @client.on("logged_out")
    async def _on_logged_out(reason: str) -> None:
        _logged_out_message(session_name, reason)
        logout.set()

    async def run(coro: Any) -> Any:
        op = asyncio.ensure_future(coro)
        watcher = asyncio.ensure_future(logout.wait())
        done, _ = await asyncio.wait({op, watcher}, return_when=asyncio.FIRST_COMPLETED)
        if op in done:
            watcher.cancel()
            return op.result()
        op.cancel()
        with contextlib.suppress(BaseException):
            await op
        raise SessionDead()

    await client.connect()
    try:
        yield client, run
    finally:
        with contextlib.suppress(Exception):
            await client.disconnect()


# ---- subcommands ----------------------------------------------------------


async def cmd_pair(session: pathlib.Path, session_name: str) -> int:
    if session.is_file():
        with contextlib.suppress(Exception):
            dev = Client(session_path=str(session)).device
            if dev is not None and dev.jid is not None:
                print(f"already paired as {jid_to_str(dev.jid)} (session={session})")
                print(
                    "If this session is actually dead (device removed on the phone), "
                    f"delete {session} and {session}.signal.db, then re-run pair."
                )
                return 0

    client: Client | None = None
    paired = asyncio.Event()
    dead = asyncio.Event()
    logout_reason: list[str] = []

    for _attempt in range(MAX_QR_WINDOWS):
        client = Client(session_path=str(session))
        paired = asyncio.Event()  # fresh per attempt: no state leaks across retries
        dead = asyncio.Event()
        logout_reason = []

        @client.on("qr")
        async def on_qr(qr: str) -> None:
            _print_qr(qr, session)

        @client.on("paired")
        async def on_paired(jid: object, _paired: asyncio.Event = paired) -> None:
            print(f"PAIRED as {_jid_field(jid)}")
            _paired.set()

        @client.on("connected")
        async def on_connected(_paired: asyncio.Event = paired) -> None:
            print("connected.")
            _paired.set()

        @client.on("history_sync")
        async def on_history(ev: object) -> None:
            print(
                f"history_sync: {ev.sync_type} "
                f"({ev.conversation_count} chats, {ev.message_count} msgs)"
            )

        @client.on("logged_out")
        async def on_logged_out(
            reason: str,
            _dead: asyncio.Event = dead,
            _reasons: list[str] = logout_reason,
        ) -> None:
            _reasons.append(reason)
            _dead.set()

        @client.on("disconnected")
        async def on_disconnected(_dead: asyncio.Event = dead) -> None:
            _dead.set()

        try:
            await client.connect()
        except PairingFailed:
            print("QR window expired; regenerating a fresh QR — keep the phone ready.", file=sys.stderr)
            with contextlib.suppress(Exception):
                await client.disconnect()
            continue
        break
    else:
        print(
            f"error: nothing scanned after {MAX_QR_WINDOWS} QR windows; "
            "run pair again when the phone is ready.",
            file=sys.stderr,
        )
        return 1

    assert client is not None
    try:
        await asyncio.wait_for(paired.wait(), timeout=180)
    except TimeoutError:
        print("error: pairing timed out after 180s", file=sys.stderr)
        with contextlib.suppress(Exception):
            await client.disconnect()
        return 1

    dev = client.device
    if dev is not None and dev.jid is not None:
        print(f"device JID: {jid_to_str(dev.jid)}")
    print("waiting ~8s for history-sync settle…")
    dropped = False
    try:
        await asyncio.wait_for(dead.wait(), timeout=8)
        dropped = True
    except TimeoutError:
        pass
    with contextlib.suppress(Exception):
        await client.disconnect()

    if dropped and logout_reason:
        # Definitive: the server logged the fresh device out (device-churn reaping).
        _delete_session(session)
        print(
            f"\nERROR: WhatsApp logged this device out during settle (reason "
            f"{logout_reason[-1]}) — the new device was reaped. The dead session "
            "was deleted. This is account-state device churn, not a skill bug. To recover:\n"
            "  1. Phone → WhatsApp → Linked Devices → remove ALL pywhats entries.\n"
            "  2. Wait 15-20 min without pairing.\n"
            f"  3. Run {_pair_hint(session_name)} once and don't unpair it.",
            file=sys.stderr,
        )
        return 1
    if dropped:
        # Ambiguous: connection fell over without a logout — often just network.
        print(
            "\nWARNING: the connection dropped during settle without a logout. "
            "The session was kept — test it with send-text. If commands report "
            f"LOGGED OUT, delete {session} and follow the churn recovery steps "
            "(remove linked devices, wait 15-20 min, pair once).",
            file=sys.stderr,
        )
        return 1

    print(f"session saved: {session}")
    print(
        "note: WhatsApp sometimes removes a fresh device within ~1 min (churn). "
        "If the next command reports LOGGED OUT, re-pair: " + _pair_hint(session_name)
    )
    return 0


async def cmd_send_text(session: pathlib.Path, session_name: str, target: str, text: str) -> int:
    chat = _dm_jid(target)
    async with _connected(session, session_name) as (client, run):
        msg = await run(client.send_text(chat, text))
        print(msg.id)
    return 0


async def cmd_send_image(
    session: pathlib.Path, session_name: str, target: str, image_path: str, caption: str
) -> int:
    chat = _dm_jid(target)
    path = pathlib.Path(image_path)
    if not path.is_file():
        print(f"error: no such file: {image_path}", file=sys.stderr)
        return 2
    mimetype, _ = mimetypes.guess_type(path.name)
    if mimetype not in ALLOWED_IMAGE_TYPES:
        hint = " (WhatsApp renders GIFs as video, which pywhats 0.1.x cannot send)" if mimetype == "image/gif" else ""
        print(
            f"error: unsupported image type {mimetype or 'unknown'} for {path.name} — "
            f"supported: jpg, jpeg, png, webp{hint}",
            file=sys.stderr,
        )
        return 2
    if path.stat().st_size > MAX_IMAGE_BYTES:
        print(
            f"error: {path.name} is {path.stat().st_size // (1024 * 1024)}MB; "
            f"images are limited to {MAX_IMAGE_BYTES // (1024 * 1024)}MB",
            file=sys.stderr,
        )
        return 2
    data = path.read_bytes()
    async with _connected(session, session_name) as (client, run):
        msg = await run(client.send_image(chat, data, mimetype=mimetype, caption=caption))
        print(msg.id)
    return 0


async def cmd_group_info(session: pathlib.Path, session_name: str, gid: str) -> int:
    group = _group_jid(gid)
    async with _connected(session, session_name) as (client, run):
        info = await run(client.get_group_info(group))
        print(
            json.dumps(
                {
                    "subject": info.subject,
                    "owner": _jid_field(info.owner),
                    "announce": bool(info.announce),
                    "locked": bool(info.locked),
                    "participants": [
                        {
                            "jid": _jid_field(p.jid),
                            "is_admin": bool(p.is_admin),
                            "is_super_admin": bool(p.is_super_admin),
                        }
                        for p in info.participants
                    ],
                },
                ensure_ascii=False,
            )
        )
    return 0


async def cmd_group_send(session: pathlib.Path, session_name: str, gid: str, text: str) -> int:
    group = _group_jid(gid)
    async with _connected(session, session_name) as (client, run):
        info = await run(client.get_group_info(group))
        msg = await run(client.send_group_text(group, text, [p.jid for p in info.participants]))
        print(msg.id)
    return 0


async def cmd_mark_read(
    session: pathlib.Path, session_name: str, chat: str, ids: list[str], sender: str | None
) -> int:
    chat_jid = _to_jid(chat)
    sender_jid = _to_jid(sender) if sender else None
    async with _connected(session, session_name) as (client, run):
        await run(client.mark_read(chat_jid, ids, sender=sender_jid))
        print(f"marked read: {ids}")
    return 0


async def cmd_presence(session: pathlib.Path, session_name: str, state: str) -> int:
    async with _connected(session, session_name) as (client, run):
        await run(client.send_presence(state))
        print(f"presence={state}")
    return 0


async def cmd_typing(
    session: pathlib.Path, session_name: str, target: str, state: str, media: str | None
) -> int:
    jid = _to_jid(target)
    async with _connected(session, session_name) as (client, run):
        await run(client.send_chat_presence(jid, state, media=media))
        print(f"typing {state}" + (f" media={media}" if media else "") + f" → {target}")
    return 0


def _event_payload(name: str, args: tuple[Any, ...]) -> dict[str, Any]:
    """One JSON-serializable dict per pywhats event (fields per pywhats.events)."""
    out: dict[str, Any] = {"event": name}
    if not args:
        return out
    if name == "qr":
        out["qr"] = args[0]
    elif name == "paired":
        out["jid"] = _jid_field(args[0])
    elif name == "logged_out":
        out["reason"] = args[0]
    elif name == "decrypt_error":
        out["message_id"], out["reason"] = args[0], args[1] if len(args) > 1 else ""
    elif name == "message":
        m = args[0]
        out.update(
            id=m.id, chat=_jid_field(m.chat), sender=_jid_field(m.sender),
            text=m.text, timestamp=int(m.timestamp), from_me=m.from_me,
        )
    elif name == "receipt":
        r = args[0]
        out.update(
            from_jid=_jid_field(r.from_jid), message_ids=list(r.message_ids),
            type=r.type, timestamp=int(r.timestamp), participant=_jid_field(r.participant),
        )
    elif name == "presence":
        p = args[0]
        out.update(
            from_jid=_jid_field(p.from_jid), unavailable=p.unavailable,
            last_seen=int(p.last_seen) if p.last_seen is not None else None,
        )
    elif name == "chat_presence":
        p = args[0]
        out.update(from_jid=_jid_field(p.from_jid), state=p.state, media=p.media)
    elif name == "history_sync":
        h = args[0]
        out.update(
            sync_type=h.sync_type, progress=int(h.progress), chunk_order=int(h.chunk_order),
            conversation_count=int(h.conversation_count), message_count=int(h.message_count),
            conversation_ids=list(h.conversation_ids),
            pushnames=[list(p) if isinstance(p, (list, tuple)) else p for p in h.pushnames],
        )
    elif name == "mute":
        e = args[0]
        out.update(
            jid=_jid_field(e.jid), muted=e.muted,
            mute_end_timestamp=int(e.mute_end_timestamp), timestamp=int(e.timestamp),
        )
    elif name in ("pin", "archive"):
        e = args[0]
        key = "pinned" if name == "pin" else "archived"
        out.update({"jid": _jid_field(e.jid), key: getattr(e, key), "timestamp": int(e.timestamp)})
    elif name == "contact":
        e = args[0]
        out.update(
            jid=_jid_field(e.jid), first_name=e.first_name,
            full_name=e.full_name, timestamp=int(e.timestamp),
        )
    elif name == "pushname":
        e = args[0]
        out.update(name=e.name, timestamp=int(e.timestamp))
    else:
        out["payload"] = str(args[0])
    return out


async def cmd_listen(
    session: pathlib.Path,
    session_name: str,
    auto_read: bool,
    subscribe: list[str],
    event_allow: set[str] | None,
) -> int:
    client = _load_paired_client(session, session_name)
    logged_out: list[str] = []
    tasks: set[asyncio.Task] = set()  # keep refs: unreferenced tasks can be GC'd

    def _emit(name: str, *args: Any) -> None:
        if event_allow is None or name in event_allow:
            print(json.dumps(_event_payload(name, args), ensure_ascii=False), flush=True)

    def _spawn(coro: Any) -> None:
        t = asyncio.create_task(coro)
        tasks.add(t)
        t.add_done_callback(tasks.discard)

    async def _auto_read(msg: Any) -> None:
        # sender/participant is group-receipt semantics only; never for 1:1.
        sender = msg.sender if msg.chat.server == "g.us" else None
        try:
            await client.mark_read(msg.chat, [msg.id], sender=sender)
        except Exception as exc:  # noqa: BLE001 — surface, don't crash the stream
            print(
                json.dumps({"event": "error", "op": "mark_read", "id": msg.id, "error": str(exc)}),
                flush=True,
            )

    def _forwarder(name: str):
        async def handler(*args: Any) -> None:
            _emit(name, *args)

        return handler

    for name in ALL_EVENTS:
        if name not in ("message", "logged_out"):
            client.on(name)(_forwarder(name))

    @client.on("message")
    async def on_message(msg: Any) -> None:
        _emit("message", msg)
        # Auto blue-tick via create_task (never bare-await client calls in a
        # handler); skip our own messages and status broadcasts.
        if auto_read and not msg.from_me and msg.chat.server != "broadcast":
            _spawn(_auto_read(msg))

    @client.on("logged_out")
    async def on_logged_out(reason: str) -> None:
        _emit("logged_out", reason)
        logged_out.append(reason)
        _logged_out_message(session_name, reason)

    await client.connect()
    if subscribe:
        # Presence events only flow after announcing availability + subscribing.
        await client.send_presence("available")
        for target in subscribe:
            await client.subscribe_presence(_to_jid(target))
    try:
        await client.wait_closed()
    finally:
        with contextlib.suppress(Exception):
            await client.disconnect()
    return 1 if logged_out else 0


# ---- argparse -------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wa.py",
        description=(
            "Portable WhatsApp CLI via pywhats (unofficial linked-device client). "
            "Not the official WhatsApp Business/Cloud API. "
            "Global options like --session go BEFORE the subcommand."
        ),
    )
    parser.add_argument(
        "--session",
        default=os.environ.get("PYWHATS_SESSION", "default"),
        help="Session name (file: $PYWHATS_HOME/<NAME>.session). "
        "Default: env PYWHATS_SESSION or 'default'.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("pair", help="Pair a new linked device via QR (ASCII + PNG)")
    p.set_defaults(make=lambda a, s, n: cmd_pair(s, n))

    p = sub.add_parser("send-text", help="Send a 1:1 text message")
    p.add_argument("to", help="Phone (intl, '+' optional) or full JID")
    p.add_argument("text", help="Message text")
    p.set_defaults(make=lambda a, s, n: cmd_send_text(s, n, a.to, a.text))

    p = sub.add_parser("send-image", help="Send an image (1:1; jpg/png/webp, ≤16MB)")
    p.add_argument("to", help="Phone (intl, '+' optional) or full JID")
    p.add_argument("path", help="Path to image file")
    p.add_argument("--caption", default="", help="Optional caption")
    p.set_defaults(make=lambda a, s, n: cmd_send_image(s, n, a.to, a.path, a.caption))

    p = sub.add_parser("group-info", help="Fetch group metadata as JSON")
    p.add_argument("gid", help="Group JID (required form: ...@g.us)")
    p.set_defaults(make=lambda a, s, n: cmd_group_info(s, n, a.gid))

    p = sub.add_parser("group-send", help="Send text to a group")
    p.add_argument("gid", help="Group JID (required form: ...@g.us)")
    p.add_argument("text", help="Message text")
    p.set_defaults(make=lambda a, s, n: cmd_group_send(s, n, a.gid, a.text))

    p = sub.add_parser("mark-read", help="Blue-tick one or more message ids")
    p.add_argument("chat", help="Chat JID or phone number")
    p.add_argument("ids", nargs="+", help="Message id(s)")
    p.add_argument("--sender", default=None, help="Original sender JID (group receipts only)")
    p.set_defaults(make=lambda a, s, n: cmd_mark_read(s, n, a.chat, a.ids, a.sender))

    p = sub.add_parser("presence", help="Set global presence")
    p.add_argument("state", choices=("available", "unavailable"))
    p.set_defaults(make=lambda a, s, n: cmd_presence(s, n, a.state))

    p = sub.add_parser("typing", help="Send typing/recording chat presence")
    p.add_argument("to", help="Chat JID or phone number")
    p.add_argument("state", choices=("composing", "paused"))
    p.add_argument("--media", default=None, choices=("audio",), help="composing + media=audio = recording")
    p.set_defaults(make=lambda a, s, n: cmd_typing(s, n, a.to, a.state, a.media))

    p = sub.add_parser("listen", help="Long-running event stream (JSON lines on stdout)")
    p.add_argument("--read", action="store_true", help="Auto mark-read inbound messages")
    p.add_argument(
        "--subscribe",
        action="append",
        default=[],
        metavar="JID_OR_PHONE",
        help="Subscribe to a peer's presence (repeatable); required for presence events, "
        "also marks this device available",
    )
    p.add_argument(
        "--events",
        default=None,
        help=f"Comma-separated event allowlist (default: all). Known: {','.join(ALL_EVENTS)}",
    )
    p.set_defaults(make=lambda a, s, n: cmd_listen(s, n, a.read, a.subscribe, a.event_allow))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    session_name: str = args.session
    session = _session_path(session_name)

    if args.command == "listen":
        args.event_allow = None
        if args.events:
            allow = {e.strip() for e in args.events.split(",") if e.strip()}
            unknown = allow - set(ALL_EVENTS)
            if unknown:
                parser.error(
                    f"unknown event(s): {', '.join(sorted(unknown))} "
                    f"(known: {','.join(ALL_EVENTS)})"
                )
            args.event_allow = allow

    try:
        return asyncio.run(args.make(args, session, session_name))
    except SessionDead:
        return 1  # guidance already printed by the logged_out handler
    except TimeoutError:
        print(
            "error: the server did not acknowledge in time — the connection may be "
            f"dead. If this persists, re-pair: {_pair_hint(session_name)}",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 130  # clean disconnects already ran via finally blocks


if __name__ == "__main__":
    raise SystemExit(main())
