#!/usr/bin/env python3
"""
Multi-provider Text-to-Speech & Podcast / Speech-to-Text CLI.

Supports two backends behind a single, consistent interface:
  --provider elevenlabs  (default)  ElevenLabs TTS
  --provider 60db                    60db TTS + streaming + WebSocket + STT

Voice settings use a unified 0-100 scale (--stability / --similarity) that each
provider translates to its native representation.

Usage:
    python elevenlabs.py voices [--provider P] [--json]
    python elevenlabs.py tts --text "Hello" --output out.mp3 [--provider P]
    python elevenlabs.py tts --file doc.pdf --output narration.mp3
    python elevenlabs.py podcast --script script.json --output podcast.mp3
    python elevenlabs.py stream --text "Hi" --output out.mp3 --provider 60db
    python elevenlabs.py ws --text "Hi" --output out.wav --provider 60db
    python elevenlabs.py stt --file audio.mp3 --provider 60db

Environment variables:
    ELEVENLABS_API_KEY    ElevenLabs key (overrides config)
    SIXTYDB_API_KEY       60db key (overrides config)
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import common
import providers
from common import (VoiceSettings, chunk_text, concat_audio, check_ffmpeg,
                    require_ffmpeg, format_size, die)


# --- Shared setup ---

def build_provider(args, config: dict, require: str | None = None):
    """Resolve the active provider and instantiate its client.

    If `require` names a capability flag (e.g. 'supports_stt'), it is checked
    against the provider class *before* an API key is demanded, so an
    unsupported-provider error is reported clearly rather than masked by a
    missing-key error.
    """
    name = common.resolve_provider(config, args.provider)
    cls = providers._PROVIDERS.get(name)
    if require and cls is not None and not getattr(cls, require, False):
        feature = require.replace("supports_", "").replace("_", " ")
        die(f"Error: provider '{name}' does not support {feature}.",
            "Use --provider 60db for this command.")
    pconfig = common.provider_config(config, name)
    api_key = common.get_api_key(name, pconfig)
    return providers.get_provider(name, api_key, pconfig), pconfig


def settings_from_args(args) -> VoiceSettings:
    """Build unified VoiceSettings from common CLI flags (absent -> None)."""
    return VoiceSettings(
        stability=getattr(args, "stability", None),
        similarity=getattr(args, "similarity", None),
        speed=getattr(args, "speed", None),
        enhance=getattr(args, "enhance", None),
        output_format=getattr(args, "output_format", None),
    )


def load_input_text(args) -> str:
    """Resolve text from --text or --file (with document extraction)."""
    if getattr(args, "file", None):
        sys.path.insert(0, str(Path(__file__).parent))
        from extract import extract_text
        text = extract_text(args.file)
        print(f"Extracted {len(text)} characters from {args.file}")
    elif getattr(args, "text", None):
        text = args.text
    else:
        die("Error: Provide --text or --file")
    if not text.strip():
        die("Error: No text to convert")
    return text


def report_output(output: Path, label: str = "Audio"):
    if output.exists() and output.stat().st_size > 0:
        print(f"\nSuccess! {label} saved to: {output}")
        print(f"Size: {format_size(output.stat().st_size)}")
    else:
        die(f"Error: Failed to create {label.lower()} file")


# --- Commands ---

def cmd_voices(args, config):
    provider, _ = build_provider(args, config)
    voices = provider.list_voices()

    if args.json:
        print(json.dumps(voices, indent=2))
        return
    if not voices:
        print("No voices found.")
        return

    print(f"{'Name':<25} {'Voice ID':<38} {'Category':<13} {'Model':<12} Labels")
    print("-" * 110)
    for v in voices:
        labels = v.get("labels", {})
        label_str = ", ".join(f"{k}: {val}" for k, val in labels.items())
        print(f"{v['name']:<25} {v['voice_id']:<38} "
              f"{v.get('category', ''):<13} {v.get('model', ''):<12} {label_str}")
    print(f"\nTotal: {len(voices)} voices ({provider.name})")


def cmd_tts(args, config):
    provider, pconfig = build_provider(args, config)
    voice_id = args.voice or pconfig.get("default_voice")
    if not voice_id and provider.name == "elevenlabs":
        voice_id = "JBFqnCBsd6RMkjVDRZzb"  # George
    settings = settings_from_args(args)

    text = load_input_text(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    chunks = chunk_text(text, max_chars=provider.MAX_CHUNK_CHARS)
    total = len(chunks)
    if total > 1 and not check_ffmpeg():
        require_ffmpeg(f"documents longer than ~{provider.MAX_CHUNK_CHARS} characters")

    print(f"Provider: {provider.name}")
    print(f"Voice: {voice_id or '(provider default)'}")
    print(f"Text: {len(text)} chars in {total} chunk(s)\n")

    ext = provider.audio_extension(settings)
    temp_files, prev_ids = [], []
    try:
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i + 1}/{total} ({len(chunk)} chars)...")
            audio, req_id = provider.synthesize(
                chunk, voice_id, settings,
                model_id=getattr(args, "model", None),
                previous_request_ids=prev_ids)
            if req_id:
                prev_ids.append(req_id)
            tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
            tmp.write(audio)
            tmp.close()
            temp_files.append(tmp.name)

        if total > 1:
            print(f"\nConcatenating {total} audio chunks...")
        concat_audio(temp_files, str(output))
    finally:
        _cleanup(temp_files)

    report_output(output)


def cmd_podcast(args, config):
    provider, pconfig = build_provider(args, config)
    settings = settings_from_args(args)

    script_path = Path(args.script)
    if not script_path.exists():
        die(f"Error: Script file not found: {script_path}")
    try:
        with open(script_path) as f:
            script = json.load(f)
    except json.JSONDecodeError as e:
        die(f"Error: Invalid JSON in script file: {e}")
    if not isinstance(script, list) or not script:
        die("Error: Script must be a non-empty JSON array of segments",
            'Format: [{"speaker": "host1", "text": "..."}, ...]')

    voice1 = args.voice1 or pconfig.get("podcast_voice1") or pconfig.get("default_voice")
    voice2 = args.voice2 or pconfig.get("podcast_voice2")
    if provider.name == "elevenlabs":
        voice1 = voice1 or "JBFqnCBsd6RMkjVDRZzb"   # George
        voice2 = voice2 or "EXAVITQu4vr4xnSDxMaL"   # Sarah
    if not voice1 or not voice2:
        die("Error: Two voices are required for a podcast.",
            "Pass --voice1 and --voice2, or set them in config.")
    voice_map = {"host1": voice1, "host2": voice2}

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    total = len(script)
    total_chars = sum(len(s.get("text", "")) for s in script)
    print(f"Provider: {provider.name}")
    print(f"Podcast: {total} segments, {total_chars} total chars")
    print(f"Host 1: {voice1}\nHost 2: {voice2}\n")

    ext = provider.audio_extension(settings)
    temp_files = []
    history = {"host1": [], "host2": []}
    try:
        for i, seg in enumerate(script):
            speaker = seg.get("speaker", "host1")
            text = seg.get("text", "")
            if not text.strip():
                continue
            voice_id = voice_map.get(speaker, voice1)
            print(f"Segment {i + 1}/{total} [{speaker}] ({len(text)} chars)...")
            audio, req_id = provider.synthesize(
                text, voice_id, settings,
                previous_request_ids=history.get(speaker, []))
            if req_id and speaker in history:
                history[speaker].append(req_id)
            tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
            tmp.write(audio)
            tmp.close()
            temp_files.append(tmp.name)

        if not temp_files:
            die("Error: No audio segments generated")
        if len(temp_files) > 1:
            require_ffmpeg("podcast concatenation")
            print(f"\nConcatenating {len(temp_files)} segments...")
        concat_audio(temp_files, str(output))
    finally:
        _cleanup(temp_files)

    report_output(output, "Podcast")


def cmd_stream(args, config):
    provider, pconfig = build_provider(args, config, require="supports_stream")
    voice_id = args.voice or pconfig.get("default_voice")
    settings = settings_from_args(args)
    text = load_input_text(args)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Provider: {provider.name} (streaming)")
    print(f"Voice: {voice_id or '(provider default)'}")
    print(f"Text: {len(text)} chars\n")

    total = 0
    with open(output, "wb") as f:
        for i, audio_chunk in enumerate(provider.stream(text, voice_id, settings)):
            f.write(audio_chunk)
            total += len(audio_chunk)
            print(f"  received chunk {i + 1} ({format_size(len(audio_chunk))})")
    report_output(output)


def cmd_ws(args, config):
    provider, pconfig = build_provider(args, config, require="supports_websocket")
    voice_id = args.voice or pconfig.get("default_voice")
    if not voice_id:
        die("Error: --voice is required for WebSocket TTS (60db needs a voice_id).")
    settings = settings_from_args(args)
    text = load_input_text(args)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Provider: {provider.name} (websocket)")
    print(f"Voice: {voice_id}")
    print(f"Encoding: {args.encoding} @ {args.sample_rate} Hz\n")

    audio, sample_rate, encoding = provider.websocket_tts(
        text, voice_id, settings, args.encoding, args.sample_rate)

    if not audio:
        die("Error: WebSocket returned no audio.")

    if encoding in ("LINEAR16", "PCM"):
        providers.write_wav(audio, str(output), sample_rate)
    else:
        # MULAW/ULAW raw or OGG_OPUS self-contained: write bytes as-is.
        with open(output, "wb") as f:
            f.write(audio)
    report_output(output)


def cmd_stt(args, config):
    provider, _ = build_provider(args, config, require="supports_stt")

    params = {
        "language": args.language,
        "diarize": str(args.diarize).lower() if args.diarize else None,
        "return_timestamps": args.timestamps,
        "context": args.context,
        "keywords": args.keywords,
    }
    print(f"Provider: {provider.name} (speech-to-text)")
    print(f"File: {args.file}\n")

    result = provider.transcribe(args.file, params)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    text = result.get("text", "")
    lang = result.get("language_name") or result.get("language") or "?"
    dur = result.get("duration_sec")
    print(f"Language: {lang}")
    if dur is not None:
        print(f"Duration: {dur}s")
    print("\nTranscript:\n")
    print(text or "(empty)")


def _cleanup(temp_files):
    for tmp in temp_files:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# --- Argument parsing ---

def add_common_settings(p):
    """Unified, provider-agnostic synthesis flags."""
    p.add_argument("--provider", "-p", choices=["elevenlabs", "60db"],
                   help="TTS provider (default: config or elevenlabs)")
    p.add_argument("--voice", "-v", help="Voice ID")
    p.add_argument("--stability", type=float,
                   help="Stability 0-100 (expressiveness vs consistency)")
    p.add_argument("--similarity", type=float,
                   help="Similarity 0-100 (source voice matching)")
    p.add_argument("--speed", type=float, help="Speed 0.5-2.0 (60db; EL where supported)")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Multi-provider TTS / STT (ElevenLabs + 60db)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  voices    List available voices
  tts       Convert text or document to speech (non-streaming)
  podcast   Generate a multi-voice podcast from a script
  stream    Stream synthesis to file        (60db)
  ws        WebSocket synthesis to WAV       (60db)
  stt       Transcribe audio to text         (60db)

Examples:
  python elevenlabs.py voices --provider 60db
  python elevenlabs.py tts --text "Hello" --output hello.mp3 --provider 60db
  python elevenlabs.py stream --file doc.md --output out.mp3 --provider 60db
  python elevenlabs.py ws --text "Hi" --output out.wav --voice VOICE_ID --provider 60db
  python elevenlabs.py stt --file recording.mp3 --provider 60db --diarize
        """)
    parser.add_argument("--config", "-c", type=Path, help="Path to config.json")
    sub = parser.add_subparsers(dest="command")

    # voices
    sp = sub.add_parser("voices", help="List available voices")
    sp.add_argument("--provider", "-p", choices=["elevenlabs", "60db"])
    sp.add_argument("--json", action="store_true", help="Output as JSON")

    # tts
    sp = sub.add_parser("tts", help="Text-to-speech (non-streaming)")
    grp = sp.add_mutually_exclusive_group(required=True)
    grp.add_argument("--text", "-t", help="Text to convert")
    grp.add_argument("--file", "-f", help="Document (PDF, DOCX, MD, TXT)")
    sp.add_argument("--output", "-o", required=True, help="Output audio path")
    sp.add_argument("--model", "-m", help="Model ID (ElevenLabs)")
    sp.add_argument("--enhance", action=argparse.BooleanOptionalAction,
                    default=None, help="Audio enhancement (60db)")
    sp.add_argument("--output-format", choices=["mp3", "wav", "ogg", "flac"],
                    help="Audio format (60db)")
    add_common_settings(sp)

    # podcast
    sp = sub.add_parser("podcast", help="Multi-voice podcast from a script")
    sp.add_argument("--script", "-s", required=True, help="JSON script file")
    sp.add_argument("--output", "-o", required=True, help="Output audio path")
    sp.add_argument("--voice1", help="Voice ID for host1")
    sp.add_argument("--voice2", help="Voice ID for host2")
    sp.add_argument("--output-format", choices=["mp3", "wav", "ogg", "flac"])
    add_common_settings(sp)

    # stream
    sp = sub.add_parser("stream", help="Stream synthesis to file (60db)")
    grp = sp.add_mutually_exclusive_group(required=True)
    grp.add_argument("--text", "-t")
    grp.add_argument("--file", "-f")
    sp.add_argument("--output", "-o", required=True)
    sp.add_argument("--output-format", choices=["mp3", "wav", "ogg", "flac"])
    sp.add_argument("--enhance", action=argparse.BooleanOptionalAction, default=None)
    add_common_settings(sp)

    # ws
    sp = sub.add_parser("ws", help="WebSocket synthesis to WAV (60db)")
    grp = sp.add_mutually_exclusive_group(required=True)
    grp.add_argument("--text", "-t")
    grp.add_argument("--file", "-f")
    sp.add_argument("--output", "-o", required=True)
    sp.add_argument("--encoding", default="LINEAR16",
                    choices=["LINEAR16", "PCM", "MULAW", "ULAW", "OGG_OPUS"],
                    help="Audio encoding (default: LINEAR16 -> WAV)")
    sp.add_argument("--sample-rate", type=int, default=24000,
                    choices=[8000, 16000, 24000, 48000])
    add_common_settings(sp)

    # stt
    sp = sub.add_parser("stt", help="Speech-to-text transcription (60db)")
    sp.add_argument("--file", "-f", required=True, help="Audio file to transcribe")
    sp.add_argument("--provider", "-p", choices=["elevenlabs", "60db"])
    sp.add_argument("--language", help="ISO 639-1 code, or 'auto'")
    sp.add_argument("--diarize", action="store_true", help="Speaker identification")
    sp.add_argument("--timestamps", choices=["none", "word"], help="Timestamp detail")
    sp.add_argument("--context", help="Domain/speaker context hint")
    sp.add_argument("--keywords", help="CSV vocabulary boost")
    sp.add_argument("--json", action="store_true", help="Full JSON output")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = common.load_config(args.config)

    dispatch = {
        "voices": cmd_voices,
        "tts": cmd_tts,
        "podcast": cmd_podcast,
        "stream": cmd_stream,
        "ws": cmd_ws,
        "stt": cmd_stt,
    }
    dispatch[args.command](args, config)


if __name__ == "__main__":
    main()
