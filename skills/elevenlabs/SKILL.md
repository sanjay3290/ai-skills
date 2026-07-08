---
name: elevenlabs
description: |
  Convert documents and text to audio using ElevenLabs or 60db text-to-speech,
  and transcribe audio with 60db speech-to-text. Use this skill when the user
  wants to create a podcast, narrate a document, read aloud text, generate audio
  from a file, stream synthesized speech, or transcribe audio to text.
license: Apache-2.0
metadata:
  author: sanjay3290
  version: "2.0"
---

# ElevenLabs + 60db — Text-to-Speech, Podcast & Speech-to-Text Skill

## Overview

This skill converts text and documents into high-quality audio, and (via 60db)
transcribes audio back into text. It supports **two providers** behind a single,
consistent CLI:

| Provider | TTS | Streaming | WebSocket | Speech-to-Text |
|----------|-----|-----------|-----------|----------------|
| `elevenlabs` (default) | ✅ | — | — | — |
| `60db` | ✅ | ✅ | ✅ | ✅ |

Pick the provider per-command with `--provider elevenlabs|60db`, or set a default
in config. Voice settings (`--stability`, `--similarity`) use a **unified 0–100
scale** that each provider translates to its own native representation.

## When to Use This Skill

Activate when the user mentions:
- "create podcast", "generate podcast", "podcast from document"
- "narrate document", "narrate this file", "read aloud"
- "text to speech", "TTS", "convert to audio"
- "stream audio", "real-time speech", "websocket TTS"
- "transcribe", "speech to text", "STT", "audio to text"

## Setup

Config at `skills/elevenlabs/config.json` (multi-provider schema):
```json
{
  "provider": "elevenlabs",
  "elevenlabs": {
    "api_key": "your-elevenlabs-api-key",
    "default_voice": "JBFqnCBsd6RMkjVDRZzb",
    "default_model": "eleven_multilingual_v2",
    "podcast_voice1": "JBFqnCBsd6RMkjVDRZzb",
    "podcast_voice2": "EXAVITQu4vr4xnSDxMaL"
  },
  "60db": {
    "api_key": "your-60db-api-key",
    "default_voice": "your-60db-voice-id",
    "default_output_format": "mp3"
  }
}
```

The legacy flat schema (`{"api_key": "...", "default_voice": "..."}`) is still
accepted and is treated as the ElevenLabs block.

API keys can also come from env vars (these override config):
- `ELEVENLABS_API_KEY`
- `SIXTYDB_API_KEY`

Dependencies:
- `pip install PyPDF2 python-docx` — only for PDF/DOCX inputs
- `pip install websocket-client` — only for the `ws` (WebSocket) command
- `ffmpeg` — for multi-chunk narration and podcasts

## Provider differences (reference)

| | ElevenLabs | 60db |
|---|---|---|
| Base URL | `api.elevenlabs.io` | `api.60db.ai` |
| Auth | `xi-api-key` header | `Authorization: Bearer` (HTTP) / `?apiKey=` (WS) |
| TTS response | raw MP3 bytes | JSON `audio_base64` |
| Chunk limit | ~4000 chars | 5000 chars |
| Continuity | `previous_request_ids` | WebSocket contexts |
| Output formats | mp3 | mp3, wav, ogg, flac (`--output-format`) |

## Commands

### List Voices

```bash
python skills/elevenlabs/scripts/elevenlabs.py voices --provider 60db
python skills/elevenlabs/scripts/elevenlabs.py voices --provider elevenlabs --json
```

Use this to find voice IDs for the user.

### Single-Voice TTS (non-streaming)

```bash
# From text (ElevenLabs default)
python skills/elevenlabs/scripts/elevenlabs.py tts --text "Hello world" --output ~/Downloads/hello.mp3

# From a document, using 60db with a wav output
python skills/elevenlabs/scripts/elevenlabs.py tts --file doc.pdf --provider 60db \
  --output-format wav --output ~/Downloads/narration.wav

# With voice + unified settings (0-100)
python skills/elevenlabs/scripts/elevenlabs.py tts --file doc.md --voice VOICE_ID \
  --stability 60 --similarity 80 --output out.mp3
```

The script handles text extraction, chunking at sentence boundaries
(provider-specific limit), TTS per chunk (with ElevenLabs voice continuity),
and ffmpeg concatenation automatically.

### Streaming TTS (60db)

```bash
python skills/elevenlabs/scripts/elevenlabs.py stream --text "Hello" \
  --provider 60db --output ~/Downloads/out.mp3
```

Streams NDJSON audio chunks to the output file as they arrive (lower latency).

### WebSocket TTS (60db)

```bash
python skills/elevenlabs/scripts/elevenlabs.py ws --text "Hello" --provider 60db \
  --voice VOICE_ID --encoding LINEAR16 --sample-rate 24000 --output ~/Downloads/out.wav
```

Opens a `wss` context, synthesizes, and writes a WAV (for `LINEAR16`/`PCM`).
Requires `websocket-client`. A `--voice` is required (60db needs a `voice_id`).

### Speech-to-Text (60db)

```bash
python skills/elevenlabs/scripts/elevenlabs.py stt --file recording.mp3 \
  --provider 60db --diarize --language auto
python skills/elevenlabs/scripts/elevenlabs.py stt --file call.wav --provider 60db --json
```

Uploads audio (multipart) and prints the transcript. `--json` prints the full
response (segments, words, timestamps, confidence).

### Podcast Generation

Podcast mode requires a JSON script file with conversation segments:

```json
[
  {"speaker": "host1", "text": "Welcome to our podcast! Today we're diving into..."},
  {"speaker": "host2", "text": "That's right! I found the section on..."},
  {"speaker": "host1", "text": "Let's break that down..."}
]
```

```bash
python skills/elevenlabs/scripts/elevenlabs.py podcast --script /tmp/script.json \
  --voice1 ID1 --voice2 ID2 --output ~/Downloads/podcast.mp3
```

Works with either provider via `--provider`.

## Podcast Workflow (for Claude)

When the user asks to create a podcast from a document:

1. **Extract the document text**:
   ```bash
   python skills/elevenlabs/scripts/extract.py /path/to/document.pdf
   ```

2. **Generate a two-host conversation script** from the extracted text. Follow these guidelines:
   - Write as a natural, engaging discussion between two hosts
   - Host 1 typically leads/introduces topics, Host 2 adds analysis and reactions
   - Start with a brief intro welcoming listeners and stating the topic
   - End with a summary/outro
   - Keep each turn under 3000 characters
   - Vary turn lengths - mix short reactions with longer explanations
   - Use conversational language: "That's a great point", "What I found interesting was..."
   - Reference specific details from the source document
   - Avoid reading the document verbatim - discuss and interpret it

3. **Write the script** as a JSON array to a temp file (`/tmp/podcast_script.json`).

4. **Generate the podcast**:
   ```bash
   python skills/elevenlabs/scripts/elevenlabs.py podcast --script /tmp/podcast_script.json --output ~/Downloads/podcast.mp3
   ```

5. **Clean up** the temp script file.

## Tips

- Run `voices` first to let the user pick voices they like (per provider).
- For podcasts, suggest voice pairs with contrasting qualities (e.g., one deep, one bright).
- Default output to `~/Downloads/` unless the user specifies otherwise.
- For large documents, warn the user about character usage on their plan.
- Settings are unified 0–100: ElevenLabs gets `value/100` (0.0–1.0); 60db gets the value as-is.
