#!/usr/bin/env python3
"""
Google Cloud Text-to-Speech

Converts text and documents to audio using Google Cloud TTS API.
Supports Neural2, WaveNet, Studio, and Standard voices.

Usage:
    python google_tts.py voices [--language en-US] [--type Neural2] [--json]
    python google_tts.py tts --text "Hello world" --output out.mp3
    python google_tts.py tts --file doc.pdf --output narration.mp3
    python google_tts.py podcast --script script.json --output podcast.mp3

Environment variables:
    GOOGLE_TTS_API_KEY - Google Cloud API key (overrides config.json)
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path


# Configuration
API_BASE_URL = "https://texttospeech.googleapis.com/v1"
DEFAULT_VOICE = "en-US-Neural2-D"
DEFAULT_PODCAST_VOICE1 = "en-US-Neural2-D"   # Male
DEFAULT_PODCAST_VOICE2 = "en-US-Neural2-F"   # Female
DEFAULT_LANGUAGE = "en-US"
DEFAULT_ENCODING = "MP3"
MAX_CHUNK_BYTES = 4800  # API limit is 5000 bytes, leave buffer for UTF-8
SCRIPT_DIR = Path(__file__).parent.parent
CONFIG_LOCATIONS = [
    SCRIPT_DIR / "config.json",
    Path.home() / ".config" / "claude" / "google-tts-config.json",
]

ENCODING_EXTENSIONS = {
    "MP3": ".mp3",
    "LINEAR16": ".wav",
    "OGG_OPUS": ".ogg",
}


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
    """Get Google Cloud API key from env var or config."""
    api_key = os.environ.get("GOOGLE_TTS_API_KEY")
    if api_key:
        return api_key

    if config:
        api_key = config.get("api_key")
        if api_key:
            return api_key

    print("Error: No Google Cloud API key found.", file=sys.stderr)
    print("\nSet it via:", file=sys.stderr)
    print("  1. Environment: export GOOGLE_TTS_API_KEY='your-key'", file=sys.stderr)
    print("  2. Config file: Create config.json with {\"api_key\": \"your-key\"}", file=sys.stderr)
    print("\nEnable Cloud Text-to-Speech API at:", file=sys.stderr)
    print("  https://console.cloud.google.com/apis/library/texttospeech.googleapis.com", file=sys.stderr)
    sys.exit(1)


# --- HTTP Helpers ---

def api_request(method: str, path: str, api_key: str,
                data: bytes | None = None,
                params: dict | None = None) -> dict:
    """Make an authenticated API request to Google Cloud TTS."""
    query_params = {"key": api_key}
    if params:
        query_params.update(params)
    url = f"{API_BASE_URL}{path}?{urllib.parse.urlencode(query_params)}"
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        handle_http_error(e)
    except urllib.error.URLError as e:
        print("=" * 60, file=sys.stderr)
        print("ERROR: Failed to connect to Google Cloud TTS API", file=sys.stderr)
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
            err = error_json.get("error", {})
            error_detail = err.get("message", error_body)
        except json.JSONDecodeError:
            error_detail = error_body

    if e.code == 400:
        print("=" * 60, file=sys.stderr)
        print("ERROR: Invalid request", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\nThe request was rejected by Google Cloud TTS.", file=sys.stderr)
    elif e.code == 401 or e.code == 403:
        print("=" * 60, file=sys.stderr)
        print("ERROR: Authentication failed", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\nYour API key is invalid or the TTS API is not enabled.", file=sys.stderr)
        print("Enable it at: https://console.cloud.google.com/apis/library/texttospeech.googleapis.com", file=sys.stderr)
    elif e.code == 429:
        print("=" * 60, file=sys.stderr)
        print("ERROR: Rate limit exceeded", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\nYou've hit the API rate limit. Wait a moment and try again.", file=sys.stderr)
    elif e.code >= 500:
        print("=" * 60, file=sys.stderr)
        print(f"ERROR: Google Cloud server error (HTTP {e.code})", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\nThe server encountered an error. Try again shortly.", file=sys.stderr)
    else:
        print(f"Error: API request failed with HTTP {e.code}", file=sys.stderr)

    if error_detail:
        print(f"\nAPI message: {error_detail}", file=sys.stderr)

    sys.exit(1)


# --- Text Processing ---

def chunk_text(text: str, max_bytes: int = MAX_CHUNK_BYTES) -> list[str]:
    """Split text into chunks that fit within the API byte limit.

    Tries to split at sentence boundaries first, then falls back to whitespace.
    """
    if len(text.encode("utf-8")) <= max_bytes:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        encoded = remaining.encode("utf-8")
        if len(encoded) <= max_bytes:
            chunks.append(remaining.strip())
            break

        # Find a safe split point within byte limit
        # Start by decoding max_bytes worth of the string
        safe_text = encoded[:max_bytes].decode("utf-8", errors="ignore")

        # Look for sentence boundary
        match = None
        for m in re.finditer(r'[.!?]\s', safe_text):
            match = m

        if match:
            split_at = match.end()
        else:
            # Fall back to last whitespace
            last_space = safe_text.rfind(" ")
            if last_space > 0:
                split_at = last_space + 1
            else:
                split_at = len(safe_text)

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
    """Concatenate multiple audio files using ffmpeg."""
    if len(file_list) == 1:
        shutil.copy2(file_list[0], output)
        return

    if not check_ffmpeg():
        print("Error: ffmpeg is required for multi-chunk audio concatenation.", file=sys.stderr)
        print("Install it with: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)", file=sys.stderr)
        sys.exit(1)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for path in file_list:
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
            print("Error: ffmpeg concatenation failed", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"Error: ffmpeg concatenation timed out after {FFMPEG_TIMEOUT}s", file=sys.stderr)
        sys.exit(1)
    finally:
        os.unlink(list_path)


# --- TTS ---

def synthesize_speech(text: str, voice_name: str, language_code: str,
                      api_key: str, encoding: str = "MP3",
                      speaking_rate: float = 1.0, pitch: float = 0.0) -> bytes:
    """Synthesize speech from text using Google Cloud TTS API.

    Returns raw audio bytes.
    """
    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": language_code,
            "name": voice_name,
        },
        "audioConfig": {
            "audioEncoding": encoding,
            "speakingRate": speaking_rate,
            "pitch": pitch,
        },
    }

    body = json.dumps(payload).encode("utf-8")
    response = api_request("POST", "/text:synthesize", api_key, data=body)

    audio_content = response.get("audioContent")
    if not audio_content:
        print("Error: No audio content in API response", file=sys.stderr)
        sys.exit(1)

    return base64.b64decode(audio_content)


# --- Commands ---

def cmd_voices(args, config: dict):
    """List available Google Cloud TTS voices."""
    api_key = get_api_key(config)

    language = args.language or config.get("default_language", "")
    params = {}
    if language:
        params["languageCode"] = language
    response = api_request("GET", "/voices", api_key, params=params)

    voices = response.get("voices", [])

    # Filter by voice type if specified
    if args.type:
        type_filter = args.type.lower()
        voices = [v for v in voices if type_filter in v.get("name", "").lower()]

    if args.json:
        print(json.dumps(voices, indent=2))
        return

    if not voices:
        print("No voices found.")
        if args.language:
            print(f"Try without --language to see all available voices.")
        return

    # Table output
    print(f"{'Voice Name':<30} {'Gender':<10} {'Language(s)':<15} {'Type'}")
    print("-" * 80)
    for v in voices:
        name = v.get("name", "Unknown")
        gender = v.get("ssmlGender", "").replace("SSML_VOICE_GENDER_", "").title()
        langs = ", ".join(v.get("languageCodes", []))
        # Extract voice type from name
        voice_type = "Standard"
        for vt in ["Neural2", "WaveNet", "Studio", "Polyglot", "News", "Casual"]:
            if vt.lower() in name.lower():
                voice_type = vt
                break
        print(f"{name:<30} {gender:<10} {langs:<15} {voice_type}")

    print(f"\nTotal: {len(voices)} voices")


def cmd_tts(args, config: dict):
    """Convert text or document to speech."""
    api_key = get_api_key(config)
    voice_name = args.voice or config.get("default_voice", DEFAULT_VOICE)
    encoding = args.encoding or config.get("default_encoding", DEFAULT_ENCODING)
    speaking_rate = args.rate if args.rate is not None else config.get("speaking_rate", 1.0)
    pitch = args.pitch if args.pitch is not None else config.get("pitch", 0.0)

    # Derive language code from voice name (e.g., en-US-Neural2-D -> en-US)
    parts = voice_name.split("-")
    if len(parts) >= 2:
        language_code = f"{parts[0]}-{parts[1]}"
    else:
        language_code = config.get("default_language", DEFAULT_LANGUAGE)

    # Get text
    if args.file:
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
        print("Error: ffmpeg is required for documents longer than ~5000 bytes.", file=sys.stderr)
        print("Install: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)", file=sys.stderr)
        sys.exit(1)

    print(f"Voice: {voice_name}")
    print(f"Language: {language_code}")
    print(f"Encoding: {encoding}")
    print(f"Rate: {speaking_rate}x | Pitch: {pitch}")
    print(f"Text: {len(text)} chars in {total_chunks} chunk(s)")
    print()

    # Determine temp file extension
    ext = ENCODING_EXTENSIONS.get(encoding, ".mp3")
    temp_files = []

    try:
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i + 1}/{total_chunks} ({len(chunk)} chars)...")

            audio_bytes = synthesize_speech(
                text=chunk,
                voice_name=voice_name,
                language_code=language_code,
                api_key=api_key,
                encoding=encoding,
                speaking_rate=speaking_rate,
                pitch=pitch,
            )

            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
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
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        print(f"\nSuccess! Audio saved to: {output}")
        print(f"Size: {size_str}")
    else:
        print("Error: Failed to create audio file", file=sys.stderr)
        sys.exit(1)


def cmd_podcast(args, config: dict):
    """Generate a multi-voice podcast from a conversation script."""
    api_key = get_api_key(config)
    encoding = args.encoding or config.get("default_encoding", DEFAULT_ENCODING)
    speaking_rate = args.rate if args.rate is not None else config.get("speaking_rate", 1.0)
    pitch = args.pitch if args.pitch is not None else config.get("pitch", 0.0)

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
    voice1 = args.voice1 or config.get("podcast_voice1", DEFAULT_PODCAST_VOICE1)
    voice2 = args.voice2 or config.get("podcast_voice2", DEFAULT_PODCAST_VOICE2)

    voice_map = {
        "host1": voice1,
        "host2": voice2,
    }

    # Derive language codes from voice names
    def lang_from_voice(name: str) -> str:
        parts = name.split("-")
        return f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else DEFAULT_LANGUAGE

    lang_map = {
        "host1": lang_from_voice(voice1),
        "host2": lang_from_voice(voice2),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    total_segments = len(script)
    total_chars = sum(len(s.get("text", "")) for s in script)

    print(f"Podcast script: {total_segments} segments, {total_chars} total chars")
    print(f"Host 1 voice: {voice1}")
    print(f"Host 2 voice: {voice2}")
    print(f"Encoding: {encoding}")
    print(f"Rate: {speaking_rate}x | Pitch: {pitch}")
    print()

    ext = ENCODING_EXTENSIONS.get(encoding, ".mp3")
    temp_files = []

    try:
        for i, segment in enumerate(script):
            speaker = segment.get("speaker", "host1")
            text = segment.get("text", "")

            if not text.strip():
                continue

            voice_name = voice_map.get(speaker, voice1)
            language_code = lang_map.get(speaker, DEFAULT_LANGUAGE)

            # Chunk long segments
            chunks = chunk_text(text)

            for ci, chunk in enumerate(chunks):
                chunk_label = f" chunk {ci+1}/{len(chunks)}" if len(chunks) > 1 else ""
                print(f"Segment {i + 1}/{total_segments} [{speaker}]{chunk_label} ({len(chunk)} chars)...")

                audio_bytes = synthesize_speech(
                    text=chunk,
                    voice_name=voice_name,
                    language_code=language_code,
                    api_key=api_key,
                    encoding=encoding,
                    speaking_rate=speaking_rate,
                    pitch=pitch,
                )

                tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
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
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        print(f"\nSuccess! Podcast saved to: {output}")
        print(f"Size: {size_str}")
    else:
        print("Error: Failed to create podcast file", file=sys.stderr)
        sys.exit(1)


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Google Cloud Text-to-Speech",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  voices    List available Google Cloud TTS voices
  tts       Convert text or document to speech
  podcast   Generate multi-voice podcast from script

Examples:
  python google_tts.py voices --language en-US --type Neural2
  python google_tts.py tts --text "Hello world" --output hello.mp3
  python google_tts.py tts --file document.pdf --output narration.mp3
  python google_tts.py podcast --script script.json --output podcast.mp3

Environment Variables:
  GOOGLE_TTS_API_KEY    Google Cloud API key (overrides config.json)
        """
    )
    parser.add_argument("--config", "-c", type=Path, help="Path to config.json")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # voices
    voices_parser = subparsers.add_parser("voices", help="List available voices")
    voices_parser.add_argument("--language", "-l", help="Filter by language code (e.g., en-US)")
    voices_parser.add_argument("--type", "-t", help="Filter by voice type (Neural2, WaveNet, Studio, Standard)")
    voices_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # tts
    tts_parser = subparsers.add_parser("tts", help="Text-to-speech conversion")
    tts_group = tts_parser.add_mutually_exclusive_group(required=True)
    tts_group.add_argument("--text", "-t", help="Text to convert")
    tts_group.add_argument("--file", "-f", help="Document file to convert (PDF, DOCX, MD, TXT)")
    tts_parser.add_argument("--output", "-o", required=True, help="Output audio file path")
    tts_parser.add_argument("--voice", "-v", help=f"Voice name (default: {DEFAULT_VOICE})")
    tts_parser.add_argument("--encoding", "-e", choices=["MP3", "LINEAR16", "OGG_OPUS"],
                            help=f"Audio encoding (default: {DEFAULT_ENCODING})")
    tts_parser.add_argument("--rate", "-r", type=float, help="Speaking rate 0.25-4.0 (default: 1.0)")
    tts_parser.add_argument("--pitch", "-p", type=float, help="Pitch -20.0 to 20.0 semitones (default: 0.0)")

    # podcast
    pod_parser = subparsers.add_parser("podcast", help="Multi-voice podcast generation")
    pod_parser.add_argument("--script", "-s", required=True, help="JSON script file path")
    pod_parser.add_argument("--output", "-o", required=True, help="Output audio file path")
    pod_parser.add_argument("--voice1", help=f"Voice for host1 (default: {DEFAULT_PODCAST_VOICE1})")
    pod_parser.add_argument("--voice2", help=f"Voice for host2 (default: {DEFAULT_PODCAST_VOICE2})")
    pod_parser.add_argument("--encoding", "-e", choices=["MP3", "LINEAR16", "OGG_OPUS"],
                            help=f"Audio encoding (default: {DEFAULT_ENCODING})")
    pod_parser.add_argument("--rate", "-r", type=float, help="Speaking rate 0.25-4.0 (default: 1.0)")
    pod_parser.add_argument("--pitch", "-p", type=float, help="Pitch -20.0 to 20.0 semitones (default: 0.0)")

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
