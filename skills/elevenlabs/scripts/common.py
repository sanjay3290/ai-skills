#!/usr/bin/env python3
"""
Shared utilities for the multi-provider TTS skill (ElevenLabs + 60db).

Holds everything provider-agnostic: config loading, the unified VoiceSettings
model, low-level HTTP helpers over urllib, text chunking, ffmpeg concatenation,
and friendly error reporting. Provider-specific request shaping lives in
providers.py; the CLI lives in elevenlabs.py.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


# --- Constants ---

DEFAULT_CHUNK_CHARS = 4000

SCRIPT_DIR = Path(__file__).parent.parent
CONFIG_LOCATIONS = [
    SCRIPT_DIR / "config.json",
    Path.home() / ".config" / "claude" / "elevenlabs-config.json",
]

# Per-provider environment variable for the API key.
ENV_KEYS = {
    "elevenlabs": "ELEVENLABS_API_KEY",
    "60db": "SIXTYDB_API_KEY",
}


# --- Output helpers ---

def die(*lines: str, code: int = 1):
    """Print error lines to stderr and exit."""
    for line in lines:
        print(line, file=sys.stderr)
    sys.exit(code)


# --- Unified voice settings ---

@dataclass
class VoiceSettings:
    """Provider-agnostic synthesis settings.

    `stability` and `similarity` use a unified 0-100 scale across providers.
    Each provider translates them to its own native representation
    (e.g. ElevenLabs expects 0.0-1.0). `speed`, `enhance`, and `output_format`
    are passed through where the provider supports them.
    """
    stability: float | None = None       # 0-100
    similarity: float | None = None       # 0-100
    speed: float | None = None            # 0.5-2.0
    enhance: bool | None = None           # 60db only
    output_format: str | None = None      # 60db only (mp3, wav, ogg, flac)


# --- Config & Auth ---

def find_config() -> Path | None:
    """Search for config.json in known locations."""
    for path in CONFIG_LOCATIONS:
        if path.exists():
            return path
    return None


def load_config(config_path: Path | None = None) -> dict:
    """Load configuration from JSON file. Returns {} if none found."""
    path = config_path or find_config()
    if not path:
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Failed to read config from {path}: {e}", file=sys.stderr)
        return {}


def provider_config(config: dict, provider: str) -> dict:
    """Extract the settings block for a given provider.

    Supports both the nested schema:
        {"elevenlabs": {"api_key": ...}, "60db": {"api_key": ...}}
    and the legacy flat schema (treated as ElevenLabs):
        {"api_key": ..., "default_voice": ...}
    """
    block = dict(config.get(provider) or {})
    # Legacy flat keys apply to ElevenLabs only, without clobbering nested ones.
    if provider == "elevenlabs":
        for legacy in ("api_key", "default_voice", "default_model",
                       "podcast_voice1", "podcast_voice2"):
            if legacy in config and legacy not in block:
                block[legacy] = config[legacy]
    return block


def resolve_provider(config: dict, cli_provider: str | None) -> str:
    """Pick the active provider: CLI flag > config 'provider' > 'elevenlabs'."""
    provider = cli_provider or config.get("provider") or "elevenlabs"
    if provider not in ENV_KEYS:
        die(f"Error: Unknown provider '{provider}'. "
            f"Choose one of: {', '.join(ENV_KEYS)}")
    return provider


def get_api_key(provider: str, pconfig: dict) -> str:
    """Get an API key for a provider from its env var or its config block."""
    env_var = ENV_KEYS.get(provider)
    if env_var:
        api_key = os.environ.get(env_var)
        if api_key:
            return api_key

    api_key = pconfig.get("api_key")
    if api_key:
        return api_key

    die(
        f"Error: No {provider} API key found.",
        "",
        "Set it via:",
        f'  1. Config file: add {{"{provider}": {{"api_key": "your-key"}}}}',
        f"  2. Environment: set {env_var}=your-key",
    )


# --- HTTP ---

def http_request(method: str, url: str, headers: dict,
                 data: bytes | None = None, timeout: int = 120):
    """Make an HTTP request. Returns (status, response_headers, body_bytes).

    Raises urllib.error.HTTPError / URLError to the caller for handling.
    """
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.status, response.headers, response.read()


def handle_http_error(e: urllib.error.HTTPError, provider: str):
    """Map an HTTP error to a friendly message, then exit.

    Understands both ElevenLabs ({"detail": ...}) and 60db
    ({"message": ...} / {"error": ...}) error envelopes.
    """
    error_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
    error_detail = _extract_error_detail(error_body)

    bar = "=" * 60
    if e.code == 401:
        die(bar, f"ERROR: Invalid {provider} API key", bar,
            "", "Your API key is invalid or expired.",
            *( [f"\nAPI message: {error_detail}"] if error_detail else [] ))
    elif e.code == 429:
        die(bar, f"ERROR: {provider} rate limit / quota exceeded", bar,
            "", "Wait a moment and try again, or check your plan limits.",
            *( [f"\nAPI message: {error_detail}"] if error_detail else [] ))
    elif e.code == 422:
        die(bar, "ERROR: Invalid request", bar,
            "", "The request parameters were rejected.",
            *( [f"\nAPI message: {error_detail}"] if error_detail else [] ))
    elif e.code >= 500:
        die(bar, f"ERROR: {provider} server error (HTTP {e.code})", bar,
            "", "The server encountered an error. Try again shortly.",
            *( [f"\nAPI message: {error_detail}"] if error_detail else [] ))
    else:
        die(f"Error: API request failed with HTTP {e.code}",
            *( [f"API message: {error_detail}"] if error_detail else [] ))


def _extract_error_detail(error_body: str) -> str:
    """Pull a human message out of a JSON error envelope, if present."""
    if not error_body:
        return ""
    try:
        data = json.loads(error_body)
    except json.JSONDecodeError:
        return error_body
    # ElevenLabs: {"detail": {"message": ...}} or {"detail": "..."}
    detail = data.get("detail")
    if isinstance(detail, dict):
        return detail.get("message", json.dumps(detail))
    if isinstance(detail, str):
        return detail
    # 60db: {"message": ...} / {"error": ...}
    for key in ("message", "error"):
        val = data.get(key)
        if isinstance(val, str):
            return val
    return error_body


def handle_url_error(e: urllib.error.URLError):
    """Report a connection-level failure, then exit."""
    bar = "=" * 60
    die(bar, "ERROR: Failed to connect to the TTS API", bar,
        f"\nConnection error: {e.reason}",
        "\nCheck your internet connection and try again.")


# --- Text chunking ---

def chunk_text(text: str, max_chars: int = DEFAULT_CHUNK_CHARS) -> list[str]:
    """Split text into chunks at sentence boundaries.

    Tries to split at sentence endings (. ! ?) first, then falls back to
    any whitespace, then a hard cut at max_chars.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining.strip())
            break

        window = remaining[:max_chars]
        match = None
        for m in re.finditer(r'[.!?]\s', window):
            match = m

        if match:
            split_at = match.end()
        else:
            last_space = window.rfind(" ")
            split_at = last_space + 1 if last_space > 0 else max_chars

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:]

    return chunks


# --- Audio (ffmpeg) ---

def check_ffmpeg() -> bool:
    """Check if ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def require_ffmpeg(reason: str):
    """Exit with install instructions if ffmpeg is missing."""
    if not check_ffmpeg():
        die(f"Error: ffmpeg is required for {reason}.",
            "Install: https://ffmpeg.org/download.html",
            "  macOS: brew install ffmpeg",
            "  Linux: apt install ffmpeg",
            "  Windows: winget install Gyan.FFmpeg")


def concat_audio(file_list: list[str], output: str):
    """Concatenate audio files using the ffmpeg concat demuxer (stream copy).

    A single input is copied directly without invoking ffmpeg.
    """
    if len(file_list) == 1:
        shutil.copy2(file_list[0], output)
        return

    require_ffmpeg("multi-chunk audio concatenation")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for path in file_list:
            escaped = path.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
        list_path = f.name

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
             "-c", "copy", output],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            die("Error: ffmpeg concatenation failed",
                *( [result.stderr] if result.stderr else [] ))
    finally:
        os.unlink(list_path)


def format_size(num_bytes: int) -> str:
    """Human-readable byte size."""
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"
