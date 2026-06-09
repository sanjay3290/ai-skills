#!/usr/bin/env python3
"""
TTS/STT providers behind a common interface.

Two backends:
  - ElevenLabsProvider: POST /v1/text-to-speech/{voice}, xi-api-key auth.
    Returns raw MP3 bytes; supports request-id continuity across chunks.
  - SixtyDBProvider: api.60db.ai, Bearer auth. Returns base64-in-JSON audio;
    also supports HTTP streaming (NDJSON), WebSocket streaming, and STT.

The CLI (elevenlabs.py) talks only to this interface. Unified 0-100
`VoiceSettings` are translated to each provider's native scale here.
"""

import base64
import json
import urllib.error
import uuid
import wave

import common
from common import VoiceSettings, http_request, handle_http_error, handle_url_error, die


# --- Base interface ---

class TTSProvider:
    """Common interface. Unsupported capabilities raise a friendly error."""

    name = "base"
    # Capability flags consulted by the CLI before dispatching.
    supports_stream = False
    supports_websocket = False
    supports_stt = False
    # Per-request character ceiling used to chunk long inputs.
    MAX_CHUNK_CHARS = 4000

    def __init__(self, api_key: str, config: dict):
        self.api_key = api_key
        self.config = config

    # -- to override --

    def list_voices(self) -> list[dict]:
        """Return normalized voices: {voice_id, name, category, labels, model}."""
        raise NotImplementedError

    def synthesize(self, text: str, voice_id: str, settings: VoiceSettings,
                   model_id: str | None = None,
                   previous_request_ids: list[str] | None = None):
        """Return (audio_bytes, request_id_or_None) for one chunk."""
        raise NotImplementedError

    def audio_extension(self, settings: VoiceSettings) -> str:
        """File extension (no dot) for audio this provider returns."""
        return "mp3"

    def stream(self, text: str, voice_id: str, settings: VoiceSettings):
        """Yield audio byte chunks as they arrive."""
        self._unsupported("HTTP streaming")

    def websocket_tts(self, text: str, voice_id: str, settings: VoiceSettings,
                      audio_encoding: str, sample_rate: int):
        """Return (audio_bytes, sample_rate, encoding) via WebSocket."""
        self._unsupported("WebSocket TTS")

    def transcribe(self, file_path: str, params: dict) -> dict:
        """Transcribe an audio file. Return the parsed JSON response."""
        self._unsupported("speech-to-text")

    # -- helpers --

    def _unsupported(self, feature: str):
        die(f"Error: provider '{self.name}' does not support {feature}.",
            "Use --provider 60db for this command.")


# --- ElevenLabs ---

class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"
    BASE_URL = "https://api.elevenlabs.io"
    DEFAULT_MODEL = "eleven_multilingual_v2"

    def _headers(self, accept: str = "application/json") -> dict:
        return {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": accept,
        }

    def list_voices(self) -> list[dict]:
        try:
            _, _, body = http_request("GET", f"{self.BASE_URL}/v1/voices",
                                      self._headers())
        except urllib.error.HTTPError as e:
            handle_http_error(e, self.name)
        except urllib.error.URLError as e:
            handle_url_error(e)
        data = json.loads(body.decode("utf-8"))
        out = []
        for v in data.get("voices", []):
            out.append({
                "voice_id": v.get("voice_id", ""),
                "name": v.get("name", "Unknown"),
                "category": v.get("category", ""),
                "labels": v.get("labels", {}) or {},
                "model": "",
            })
        return out

    def synthesize(self, text, voice_id, settings, model_id=None,
                   previous_request_ids=None):
        payload = {
            "text": text,
            "model_id": model_id or self.config.get("default_model",
                                                    self.DEFAULT_MODEL),
        }
        if previous_request_ids:
            payload["previous_request_ids"] = previous_request_ids[-3:]  # API max 3

        vs = {}
        if settings.stability is not None:
            vs["stability"] = settings.stability / 100.0      # 0-100 -> 0.0-1.0
        if settings.similarity is not None:
            vs["similarity_boost"] = settings.similarity / 100.0
        if settings.speed is not None:
            vs["speed"] = settings.speed
        if vs:
            payload["voice_settings"] = vs

        body = json.dumps(payload).encode("utf-8")
        url = f"{self.BASE_URL}/v1/text-to-speech/{voice_id}"
        try:
            _, headers, audio = http_request(
                "POST", url, self._headers(accept="audio/mpeg"), data=body)
        except urllib.error.HTTPError as e:
            handle_http_error(e, self.name)
        except urllib.error.URLError as e:
            handle_url_error(e)
        return audio, headers.get("request-id")


# --- 60db ---

class SixtyDBProvider(TTSProvider):
    name = "60db"
    BASE_URL = "https://api.60db.ai"
    WS_URL = "wss://api.60db.ai/ws/tts"
    supports_stream = True
    supports_websocket = True
    supports_stt = True
    MAX_CHUNK_CHARS = 5000

    def _headers(self, content_type: str | None = "application/json") -> dict:
        h = {"Authorization": f"Bearer {self.api_key}"}
        if content_type:
            h["Content-Type"] = content_type
        return h

    def audio_extension(self, settings: VoiceSettings) -> str:
        return settings.output_format or self.config.get(
            "default_output_format", "mp3")

    def _tts_body(self, text, voice_id, settings: VoiceSettings) -> dict:
        body = {"text": text}
        if voice_id:
            body["voice_id"] = voice_id
        if settings.enhance is not None:
            body["enhance"] = settings.enhance
        if settings.speed is not None:
            body["speed"] = settings.speed
        if settings.stability is not None:
            body["stability"] = settings.stability       # already 0-100
        if settings.similarity is not None:
            body["similarity"] = settings.similarity      # already 0-100
        fmt = settings.output_format or self.config.get("default_output_format")
        if fmt:
            body["output_format"] = fmt
        return body

    def list_voices(self) -> list[dict]:
        try:
            _, _, body = http_request("GET", f"{self.BASE_URL}/myvoices",
                                      self._headers())
        except urllib.error.HTTPError as e:
            handle_http_error(e, self.name)
        except urllib.error.URLError as e:
            handle_url_error(e)
        data = json.loads(body.decode("utf-8"))
        out = []
        for v in data.get("data", []):
            out.append({
                "voice_id": v.get("voice_id", ""),
                "name": v.get("name", "Unknown"),
                "category": v.get("category", ""),
                "labels": v.get("labels", {}) or {},
                "model": v.get("model", ""),
            })
        return out

    def synthesize(self, text, voice_id, settings, model_id=None,
                   previous_request_ids=None):
        # 60db has no request-id continuity; previous_request_ids/model ignored.
        body = json.dumps(self._tts_body(text, voice_id, settings)).encode("utf-8")
        try:
            _, _, resp = http_request(
                "POST", f"{self.BASE_URL}/tts-synthesize", self._headers(),
                data=body)
        except urllib.error.HTTPError as e:
            handle_http_error(e, self.name)
        except urllib.error.URLError as e:
            handle_url_error(e)

        data = json.loads(resp.decode("utf-8"))
        if not data.get("success", True):
            die(f"Error: 60db TTS failed: {data.get('message', 'unknown error')}")
        b64 = data.get("audio_base64")
        if not b64:
            die("Error: 60db response contained no audio_base64.")
        return base64.b64decode(b64), None

    def stream(self, text, voice_id, settings):
        """Stream synthesis: POST /tts-stream returns NDJSON lines."""
        body = json.dumps(self._tts_body(text, voice_id, settings)).encode("utf-8")
        import urllib.request
        req = urllib.request.Request(
            f"{self.BASE_URL}/tts-stream", data=body,
            headers=self._headers(), method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            handle_http_error(e, self.name)
        except urllib.error.URLError as e:
            handle_url_error(e)

        with resp:
            for raw in resp:                       # iterate NDJSON line by line
                line = raw.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                mtype = msg.get("type")
                if mtype == "chunk":
                    audio_b64 = (msg.get("result") or {}).get("audioContent")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)
                elif mtype == "complete":
                    return
                elif mtype == "error":
                    die(f"Error: 60db stream error: {msg.get('message', 'unknown')}")

    def transcribe(self, file_path, params):
        """POST /stt as multipart/form-data."""
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            die(f"Error: audio file not found: {path}")

        boundary = f"----60db{uuid.uuid4().hex}"
        parts = []
        # text fields
        for key, value in params.items():
            if value is None:
                continue
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            parts.append(f"{value}\r\n".encode())
        # file field
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="file"; '
            f'filename="{path.name}"\r\n'.encode())
        parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
        parts.append(path.read_bytes())
        parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)

        headers = self._headers(content_type=None)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        try:
            _, _, resp = http_request(
                "POST", f"{self.BASE_URL}/stt", headers, data=body, timeout=300)
        except urllib.error.HTTPError as e:
            handle_http_error(e, self.name)
        except urllib.error.URLError as e:
            handle_url_error(e)
        return json.loads(resp.decode("utf-8"))

    def websocket_tts(self, text, voice_id, settings, audio_encoding, sample_rate):
        """Connect over WebSocket, synthesize one text, return audio bytes.

        For LINEAR16/PCM the returned bytes are raw PCM (the caller wraps them
        in a WAV container). For OGG_OPUS each chunk is a self-contained file.
        """
        try:
            import websocket  # websocket-client
        except ImportError:
            die("Error: WebSocket TTS requires the 'websocket-client' package.",
                "Install it with: pip install websocket-client")

        url = f"{self.WS_URL}?apiKey={self.api_key}"
        context_id = f"cli-{uuid.uuid4().hex[:12]}"
        audio = bytearray()

        try:
            ws = websocket.create_connection(url, timeout=60)
        except Exception as e:  # noqa: BLE001 - surface any connect failure
            die(f"Error: failed to open WebSocket to 60db: {e}")

        def send(obj):
            ws.send(json.dumps(obj))

        try:
            send({"create_context": {
                "context_id": context_id,
                "voice_id": voice_id,
                "audio_config": {
                    "audio_encoding": audio_encoding,
                    "sample_rate_hertz": sample_rate,
                },
                **({"speed": settings.speed} if settings.speed is not None else {}),
                **({"stability": settings.stability}
                   if settings.stability is not None else {}),
                **({"similarity": settings.similarity}
                   if settings.similarity is not None else {}),
            }})
            send({"send_text": {"context_id": context_id, "text": text}})
            send({"flush_context": {"context_id": context_id}})

            closed = False
            while not closed:
                raw = ws.recv()
                if not raw:
                    break
                msg = json.loads(raw)
                if "audio_chunk" in msg:
                    b64 = msg["audio_chunk"].get("audioContent")
                    if b64:
                        audio.extend(base64.b64decode(b64))
                elif "flush_completed" in msg:
                    send({"close_context": {"context_id": context_id}})
                elif "context_closed" in msg:
                    closed = True
                elif "error" in msg:
                    die(f"Error: 60db WebSocket error: "
                        f"{msg['error'].get('message', 'unknown')}")
        finally:
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass

        return bytes(audio), sample_rate, audio_encoding


# --- Factory ---

_PROVIDERS = {
    "elevenlabs": ElevenLabsProvider,
    "60db": SixtyDBProvider,
}


def get_provider(name: str, api_key: str, pconfig: dict) -> TTSProvider:
    cls = _PROVIDERS.get(name)
    if not cls:
        die(f"Error: unknown provider '{name}'.")
    return cls(api_key, pconfig)


def write_wav(pcm_bytes: bytes, path: str, sample_rate: int,
              channels: int = 1, sampwidth: int = 2):
    """Wrap raw 16-bit PCM bytes in a WAV container."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
