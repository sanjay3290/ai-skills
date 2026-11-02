#!/usr/bin/env python3
"""
ElevenLabs Text-to-Speech & Podcast Generation

Converts text and documents to audio using ElevenLabs TTS API.
Supports single-voice narration and multi-voice podcast generation.

Usage:
    python elevenlabs.py voices [--json]
    python elevenlabs.py tts --text "Hello world" --output out.mp3
    python elevenlabs.py tts --file doc.pdf --output narration.mp3
    python elevenlabs.py podcast --script script.json --output podcast.mp3

Environment variables:
    ELEVENLABS_API_KEY (optional) - Overrides config.json API key
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path


# Configuration
API_BASE_URL = "https://api.elevenlabs.io"
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # George
MAX_CHUNK_CHARS = 4000
SCRIPT_DIR = Path(__file__).parent.parent
CONFIG_LOCATIONS = [
    SCRIPT_DIR / "config.json",
    Path.home() / ".config" / "claude" / "elevenlabs-config.json",
]


# --- Config & Auth ---

def find_config() -> Path | None:
    """Search for config.json in known locations."""
    for path in CONFIG_LOCATIONS:
        if path.exists():
            return path
    return None


def load_config(config_path: Path | None = None) -> dict:
    """Load configuration from JSON file."""
    path = config_path or find_config()
    if not path:
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Failed to read config from {path}: {e}", file=sys.stderr)
        return {}


def get_api_key(config: dict | None = None) -> str:
    """Get ElevenLabs API key from env var or config."""
    # Env var takes priority
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if api_key:
        return api_key

    # Fall back to config
    if config:
        api_key = config.get("api_key")
        if api_key:
            return api_key

    print("Error: No ElevenLabs API key found.", file=sys.stderr)
    print("\nSet it via:", file=sys.stderr)
    print("  1. Config file: Create config.json with {\"api_key\": \"your-key\"}", file=sys.stderr)
    print("  2. Environment: export ELEVENLABS_API_KEY='your-key'", file=sys.stderr)
    print("\nGet a key at: https://elevenlabs.io/", file=sys.stderr)
    sys.exit(1)


# --- HTTP Helpers ---

def api_request(method: str, path: str, api_key: str,
                data: bytes | None = None, content_type: str = "application/json",
                stream: bool = False):
    """Make an authenticated API request to ElevenLabs."""
    url = f"{API_BASE_URL}{path}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": content_type,
    }

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            body = response.read()
            if stream:
                return body
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        handle_http_error(e)
    except urllib.error.URLError as e:
        print("=" * 60, file=sys.stderr)
        print("ERROR: Failed to connect to ElevenLabs API", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"\nConnection error: {e.reason}", file=sys.stderr)
        print("\nCheck your internet connection and try again.", file=sys.stderr)
        sys.exit(1)


def handle_http_error(e: urllib.error.HTTPError):
    """Handle HTTP errors with user-friendly messages."""
    error_body = e.read().decode("utf-8") if e.fp else ""
    error_detail = ""

    if error_body:
        try:
            error_json = json.loads(error_body)
            detail = error_json.get("detail")
            if isinstance(detail, dict):
                error_detail = detail.get("message", str(detail))
            elif isinstance(detail, str):
                error_detail = detail
            else:
                error_detail = error_body
        except json.JSONDecodeError:
            error_detail = error_body

    if e.code == 401:
        print("=" * 60, file=sys.stderr)
        print("ERROR: Invalid ElevenLabs API key", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\nYour API key is invalid or expired.", file=sys.stderr)
        print("Verify your key at: https://elevenlabs.io/app/settings/api-keys", file=sys.stderr)
    elif e.code == 429:
        print("=" * 60, file=sys.stderr)
        print("ERROR: ElevenLabs rate limit exceeded", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\nYou've hit the API rate limit or character quota.", file=sys.stderr)
        print("Wait a moment and try again, or check your plan limits.", file=sys.stderr)
    elif e.code == 422:
        print("=" * 60, file=sys.stderr)
        print("ERROR: Invalid request", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\nThe request parameters were rejected.", file=sys.stderr)
    elif e.code >= 500:
        print("=" * 60, file=sys.stderr)
        print(f"ERROR: ElevenLabs server error (HTTP {e.code})", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\nThe server encountered an error. Try again shortly.", file=sys.stderr)
    else:
        print(f"Error: API request failed with HTTP {e.code}", file=sys.stderr)

    if error_detail:
        print(f"\nAPI message: {error_detail}", file=sys.stderr)

    sys.exit(1)


# --- Text Processing ---

def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks at sentence boundaries.

    Tries to split at sentence endings (. ! ?) first, then falls back to
    any whitespace if no sentence boundary is found within the limit.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining.strip())
            break

        # Look for sentence boundary within the limit
        window = remaining[:max_chars]
        # Find last sentence-ending punctuation followed by space or end
        match = None
        for m in re.finditer(r'[.!?]\s', window):
            match = m

        if match:
            split_at = match.end()
        else:
            # Fall back to last whitespace
            last_space = window.rfind(" ")
            if last_space > 0:
                split_at = last_space + 1
            else:
                # No good split point - force at max_chars
                split_at = max_chars

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:]

    return chunks


# --- Audio Processing ---

# Stream-copy concat is normally near-instant; this only guards against a hung ffmpeg.
FFMPEG_TIMEOUT = 300  # seconds


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


def concat_audio(file_list: list[str], output: str):
    """Concatenate multiple audio files using ffmpeg concat demuxer."""
    if len(file_list) == 1:
        shutil.copy2(file_list[0], output)
        return

    if not check_ffmpeg():
        print("Error: ffmpeg is required for multi-chunk audio concatenation.", file=sys.stderr)
        print("Install it with: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)", file=sys.stderr)
        sys.exit(1)

    # Create concat list file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for path in file_list:
            # Escape single quotes in path for ffmpeg
            escaped = path.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
        list_path = f.name

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
             "-c", "copy", output],
            capture_output=True, text=True, timeout=FFMPEG_TIMEOUT
        )
        if result.returncode != 0:
            print(f"Error: ffmpeg concatenation failed", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"Error: ffmpeg concatenation timed out after {FFMPEG_TIMEOUT}s", file=sys.stderr)
        sys.exit(1)
    finally:
        os.unlink(list_path)


# --- TTS ---

def text_to_speech(text: str, voice_id: str, api_key: str,
                   model_id: str = DEFAULT_MODEL,
                   previous_request_ids: list[str] | None = None,
                   stability: float | None = None,
                   similarity_boost: float | None = None):
    """Convert text to speech using ElevenLabs API.

    Returns:
        Tuple of (audio_bytes, request_id) where request_id can be passed
        to subsequent calls for voice continuity.
    """
    payload = {
        "text": text,
        "model_id": model_id,
    }

    if previous_request_ids:
        payload["previous_request_ids"] = previous_request_ids[-3:]  # API supports max 3

    voice_settings = {}
    if stability is not None:
        voice_settings["stability"] = stability
    if similarity_boost is not None:
        voice_settings["similarity_boost"] = similarity_boost
    if voice_settings:
        payload["voice_settings"] = voice_settings

    body = json.dumps(payload).encode("utf-8")
    path = f"/v1/text-to-speech/{voice_id}"

    url = f"{API_BASE_URL}{path}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            audio_bytes = response.read()
            request_id = response.headers.get("request-id")
            return audio_bytes, request_id
    except urllib.error.HTTPError as e:
        handle_http_error(e)
    except urllib.error.URLError as e:
        print(f"Error: Connection failed: {e.reason}", file=sys.stderr)
        sys.exit(1)


# --- Commands ---

def cmd_voices(args, config: dict):
    """List available ElevenLabs voices."""
    api_key = get_api_key(config)
    response = api_request("GET", "/v1/voices", api_key)

    voices = response.get("voices", [])

    if args.json:
        print(json.dumps(voices, indent=2))
        return

    if not voices:
        print("No voices found.")
        return

    # Table output
    print(f"{'Name':<25} {'Voice ID':<25} {'Category':<15} {'Labels'}")
    print("-" * 90)
    for v in voices:
        name = v.get("name", "Unknown")
        vid = v.get("voice_id", "")
        category = v.get("category", "")
        labels = v.get("labels", {})
        label_str = ", ".join(f"{k}: {val}" for k, val in labels.items()) if labels else ""
        print(f"{name:<25} {vid:<25} {category:<15} {label_str}")

    print(f"\nTotal: {len(voices)} voices")


def cmd_tts(args, config: dict):
    """Convert text or document to speech."""
    api_key = get_api_key(config)
    voice_id = args.voice or config.get("default_voice", DEFAULT_VOICE)
    model_id = args.model or config.get("default_model", DEFAULT_MODEL)

    # Get text
    if args.file:
        # Import extract module
        sys.path.insert(0, str(Path(__file__).parent))
        from extract import extract_text
        text = extract_text(args.file)
        print(f"Extracted {len(text)} characters from {args.file}")
    elif args.text:
        text = args.text
    else:
        print("Error: Provide --text or --file", file=sys.stderr)
        sys.exit(1)

    if not text.strip():
        print("Error: No text to convert", file=sys.stderr)
        sys.exit(1)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Chunk text
    chunks = chunk_text(text)
    total_chunks = len(chunks)

    if total_chunks > 1 and not check_ffmpeg():
        print("Error: ffmpeg is required for documents longer than ~4000 characters.", file=sys.stderr)
        print("Install: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)", file=sys.stderr)
        sys.exit(1)

    print(f"Voice: {voice_id}")
    print(f"Model: {model_id}")
    print(f"Text: {len(text)} chars in {total_chunks} chunk(s)")
    print()

    temp_files = []
    previous_request_ids = []

    try:
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i + 1}/{total_chunks} ({len(chunk)} chars)...")

            audio_bytes, request_id = text_to_speech(
                text=chunk,
                voice_id=voice_id,
                api_key=api_key,
                model_id=model_id,
                previous_request_ids=previous_request_ids,
            )

            if request_id:
                previous_request_ids.append(request_id)

            # Save chunk to temp file
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.write(audio_bytes)
            tmp.close()
            temp_files.append(tmp.name)

        # Concatenate
        if total_chunks > 1:
            print(f"\nConcatenating {total_chunks} audio chunks...")

        concat_audio(temp_files, str(output))

    finally:
        for tmp in temp_files:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    # Report
    if output.exists() and output.stat().st_size > 0:
        size = output.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
        print(f"\nSuccess! Audio saved to: {output}")
        print(f"Size: {size_str}")
    else:
        print(f"Error: Failed to create audio file", file=sys.stderr)
        sys.exit(1)


def cmd_podcast(args, config: dict):
    """Generate a multi-voice podcast from a conversation script."""
    api_key = get_api_key(config)
    model_id = args.model or config.get("default_model", DEFAULT_MODEL)

    # Load script
    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: Script file not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(script_path) as f:
            script = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in script file: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(script, list) or not script:
        print("Error: Script must be a non-empty JSON array of segments", file=sys.stderr)
        print('Format: [{"speaker": "host1", "text": "..."}, ...]', file=sys.stderr)
        sys.exit(1)

    # Resolve voices
    voice1 = args.voice1 or config.get("podcast_voice1", DEFAULT_VOICE)
    voice2 = args.voice2 or config.get("podcast_voice2", "EXAVITQu4vr4xnSDxMaL")  # Sarah

    voice_map = {
        "host1": voice1,
        "host2": voice2,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    total_segments = len(script)
    total_chars = sum(len(s.get("text", "")) for s in script)

    print(f"Podcast script: {total_segments} segments, {total_chars} total chars")
    print(f"Host 1 voice: {voice1}")
    print(f"Host 2 voice: {voice2}")
    print(f"Model: {model_id}")
    print()

    temp_files = []
    # Track previous_request_ids per voice for continuity
    voice_history: dict[str, list[str]] = {"host1": [], "host2": []}

    try:
        for i, segment in enumerate(script):
            speaker = segment.get("speaker", "host1")
            text = segment.get("text", "")

            if not text.strip():
                continue

            voice_id = voice_map.get(speaker, voice1)
            prev_ids = voice_history.get(speaker, [])

            print(f"Segment {i + 1}/{total_segments} [{speaker}] ({len(text)} chars)...")

            audio_bytes, request_id = text_to_speech(
                text=text,
                voice_id=voice_id,
                api_key=api_key,
                model_id=model_id,
                previous_request_ids=prev_ids,
            )

            if request_id and speaker in voice_history:
                voice_history[speaker].append(request_id)

            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.write(audio_bytes)
            tmp.close()
            temp_files.append(tmp.name)

        if not temp_files:
            print("Error: No audio segments generated", file=sys.stderr)
            sys.exit(1)

        if len(temp_files) > 1:
            if not check_ffmpeg():
                print("Error: ffmpeg is required for podcast concatenation.", file=sys.stderr)
                print("Install: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)", file=sys.stderr)
                sys.exit(1)
            print(f"\nConcatenating {len(temp_files)} segments...")

        concat_audio(temp_files, str(output))

    finally:
        for tmp in temp_files:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    # Report
    if output.exists() and output.stat().st_size > 0:
        size = output.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
        print(f"\nSuccess! Podcast saved to: {output}")
        print(f"Size: {size_str}")
    else:
        print(f"Error: Failed to create podcast file", file=sys.stderr)
        sys.exit(1)


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="ElevenLabs Text-to-Speech & Podcast Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  voices    List available ElevenLabs voices
  tts       Convert text or document to speech
  podcast   Generate multi-voice podcast from script

Examples:
  python elevenlabs.py voices
  python elevenlabs.py tts --text "Hello world" --output hello.mp3
  python elevenlabs.py tts --file document.pdf --output narration.mp3
  python elevenlabs.py podcast --script script.json --voice1 ID1 --voice2 ID2 --output podcast.mp3

Environment Variables:
  ELEVENLABS_API_KEY    API key (overrides config.json)
        """
    )
    parser.add_argument("--config", "-c", type=Path, help="Path to config.json")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # voices
    voices_parser = subparsers.add_parser("voices", help="List available voices")
    voices_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # tts
    tts_parser = subparsers.add_parser("tts", help="Text-to-speech conversion")
    tts_group = tts_parser.add_mutually_exclusive_group(required=True)
    tts_group.add_argument("--text", "-t", help="Text to convert")
    tts_group.add_argument("--file", "-f", help="Document file to convert (PDF, DOCX, MD, TXT)")
    tts_parser.add_argument("--output", "-o", required=True, help="Output MP3 file path")
    tts_parser.add_argument("--voice", "-v", help="Voice ID (default: from config or George)")
    tts_parser.add_argument("--model", "-m", help=f"Model ID (default: {DEFAULT_MODEL})")

    # podcast
    pod_parser = subparsers.add_parser("podcast", help="Multi-voice podcast generation")
    pod_parser.add_argument("--script", "-s", required=True, help="JSON script file path")
    pod_parser.add_argument("--output", "-o", required=True, help="Output MP3 file path")
    pod_parser.add_argument("--voice1", help="Voice ID for host1")
    pod_parser.add_argument("--voice2", help="Voice ID for host2")
    pod_parser.add_argument("--model", "-m", help=f"Model ID (default: {DEFAULT_MODEL})")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)

    if args.command == "voices":
        cmd_voices(args, config)
    elif args.command == "tts":
        cmd_tts(args, config)
    elif args.command == "podcast":
        cmd_podcast(args, config)


if __name__ == "__main__":
    main()
