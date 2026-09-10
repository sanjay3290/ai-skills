#!/usr/bin/env python3
"""
Imagen - Google Gemini Image Generation Script

Cross-platform image generation using Google Gemini API.
Works on Windows, macOS, and Linux.

Usage:
    python generate_image.py "prompt" [output_path]

Environment variables:
    GEMINI_API_KEY (required) - Your Google Gemini API key
    IMAGE_SIZE (optional) - Image size: "512", "1K" (default), or "2K"
    GEMINI_MODEL (optional) - Model ID (default: gemini-3-pro-image-preview)
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


# Configuration
DEFAULT_MODEL_ID = "gemini-3-pro-image-preview"
API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_IMAGE_SIZE = "1K"
VALID_SIZES = {"512", "1K", "2K"}
ATLAS_API_BASE_URL = "https://api.atlascloud.ai"
DEFAULT_ATLAS_MODEL_ID = "google/nano-banana-2-lite/text-to-image-developer"
VALID_ASPECT_RATIOS = {
    "auto", "1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4",
    "9:16", "16:9", "21:9", "4:1", "1:4", "8:1", "1:8",
}


def get_api_endpoint(model_id: str) -> str:
    """Build the API endpoint URL for the given model."""
    # Use streamGenerateContent for image generation models
    return f"{API_BASE_URL}/{model_id}:streamGenerateContent"


def get_api_key() -> str:
    """Get the Gemini API key from environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        print("\nTo set it:", file=sys.stderr)
        print("  Windows (PowerShell): $env:GEMINI_API_KEY = 'your-key'", file=sys.stderr)
        print("  Windows (CMD): set GEMINI_API_KEY=your-key", file=sys.stderr)
        print("  macOS/Linux: export GEMINI_API_KEY='your-key'", file=sys.stderr)
        print("\nGet a free key at: https://aistudio.google.com/", file=sys.stderr)
        sys.exit(1)
    return api_key


def get_atlas_api_key() -> str:
    """Get the Atlas Cloud API key from the environment."""
    api_key = os.environ.get("ATLASCLOUD_API_KEY")
    if not api_key:
        print("Error: ATLASCLOUD_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    return api_key


def request_atlas_json(method: str, path: str, api_key=None, payload=None) -> dict:
    """Make one Atlas Cloud JSON request without automatic retries."""
    headers = {
        "Accept": "application/json",
        "User-Agent": "ai-skills-imagen/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{ATLAS_API_BASE_URL}{path}", data=data, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise RuntimeError("Atlas Cloud returned a non-object response")
    return result


def iter_objects(value):
    """Yield nested JSON objects from the Atlas Cloud catalog."""
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from iter_objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_objects(item)


def validate_atlas_model(model_id: str) -> None:
    """Confirm that an Atlas Cloud model is present and enabled."""
    catalog = request_atlas_json("GET", "/api/v1/models")
    model = next(
        (
            item for item in iter_objects(catalog)
            if (item.get("model") or item.get("id")) == model_id
        ),
        None,
    )
    if model is None:
        raise RuntimeError(f"Atlas Cloud model not found: {model_id}")
    if model.get("display_console") is not True:
        raise RuntimeError(f"Atlas Cloud model is not enabled: {model_id}")


def poll_atlas_prediction(api_key: str, prediction_id: str, timeout=180) -> str:
    """Poll an Atlas prediction, retrying transient GET failures at most three times."""
    deadline = time.monotonic() + timeout
    transient_errors = 0
    while time.monotonic() < deadline:
        try:
            result = request_atlas_json(
                "GET", f"/api/v1/model/prediction/{prediction_id}", api_key
            )
            transient_errors = 0
        except (urllib.error.URLError, TimeoutError):
            transient_errors += 1
            if transient_errors > 3:
                raise
            time.sleep(2 ** (transient_errors - 1))
            continue

        data = result.get("data") or {}
        status = str(data.get("status") or "").lower()
        if status in {"completed", "succeeded"}:
            outputs = data.get("outputs") or []
            if not outputs or not isinstance(outputs[0], str):
                raise RuntimeError("Atlas Cloud completed without an output URL")
            return outputs[0]
        if status in {"failed", "timeout", "canceled", "cancelled"}:
            raise RuntimeError(data.get("error") or f"Atlas generation ended with {status}")
        time.sleep(3)
    raise TimeoutError(f"Atlas prediction {prediction_id} did not finish in time")


def download_atlas_output(url: str, output_path: Path) -> None:
    """Download the generated image to the requested path."""
    if not url.startswith(("https://", "http://")):
        raise RuntimeError("Atlas Cloud returned an unsupported output URL")
    with urllib.request.urlopen(url, timeout=120) as response:
        output_path.write_bytes(response.read())


def generate_atlas_image(
    prompt: str, output_path: Path, api_key: str, model_id: str, aspect_ratio: str
) -> None:
    """Generate one image with the optional Atlas Cloud provider."""
    validate_atlas_model(model_id)
    # Do not retry this billable POST. Only prediction GET requests retry.
    result = request_atlas_json(
        "POST",
        "/api/v1/model/generateImage",
        api_key,
        {
            "model": model_id,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": "1k",
        },
    )
    prediction_id = str((result.get("data") or {}).get("id") or "")
    if not prediction_id:
        raise RuntimeError(result.get("message") or "Atlas Cloud returned no prediction ID")
    output_url = poll_atlas_prediction(api_key, prediction_id)
    download_atlas_output(output_url, output_path)


def validate_image_size(size: str) -> str:
    """Validate and return the image size."""
    if size not in VALID_SIZES:
        print(f"Warning: Invalid IMAGE_SIZE '{size}'. Using default '{DEFAULT_IMAGE_SIZE}'", file=sys.stderr)
        return DEFAULT_IMAGE_SIZE
    return size


def create_output_dir(output_path: Path) -> None:
    """Create output directory if it doesn't exist."""
    output_dir = output_path.parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)


def build_request_body(prompt: str, image_size: str) -> bytes:
    """Build the JSON request body for the API."""
    request_data = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "imageConfig": {
                "image_size": image_size
            }
        }
    }
    return json.dumps(request_data).encode("utf-8")


def make_api_request(api_key: str, model_id: str, request_body: bytes) -> dict:
    """Make the API request and return the response."""
    endpoint = get_api_endpoint(model_id)
    url = f"{endpoint}?key={api_key}"

    headers = {
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, data=request_body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        error_detail = ""

        # Try to extract error message from response
        if error_body:
            try:
                error_json = json.loads(error_body)
                error_detail = error_json.get("error", {}).get("message", "")
            except json.JSONDecodeError:
                error_detail = error_body

        # Provide user-friendly messages for common errors
        if e.code == 429:
            print("=" * 60, file=sys.stderr)
            print("ERROR: Gemini API quota exhausted", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print("\nYou've exceeded your Gemini API usage limits.", file=sys.stderr)
            print("\nWhat to do:", file=sys.stderr)
            print("  1. Wait for your quota to reset (usually resets daily)", file=sys.stderr)
            print("  2. Check your usage at: https://aistudio.google.com/", file=sys.stderr)
            print("  3. Consider upgrading your API plan if needed", file=sys.stderr)
            if error_detail:
                print(f"\nAPI message: {error_detail}", file=sys.stderr)
        elif e.code == 403:
            print("=" * 60, file=sys.stderr)
            print("ERROR: Gemini API access denied", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print("\nYour API key is invalid or lacks required permissions.", file=sys.stderr)
            print("\nWhat to do:", file=sys.stderr)
            print("  1. Verify your API key at: https://aistudio.google.com/", file=sys.stderr)
            print("  2. Ensure the Gemini API is enabled for your project", file=sys.stderr)
            print("  3. Check that your key has image generation permissions", file=sys.stderr)
            if error_detail:
                print(f"\nAPI message: {error_detail}", file=sys.stderr)
        elif e.code == 400:
            print("=" * 60, file=sys.stderr)
            print("ERROR: Invalid request to Gemini API", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print("\nThe request was rejected by the API.", file=sys.stderr)
            print("\nPossible causes:", file=sys.stderr)
            print("  - Prompt may contain blocked content", file=sys.stderr)
            print("  - Prompt format may be invalid", file=sys.stderr)
            print("  - Image generation may not be available for this prompt", file=sys.stderr)
            if error_detail:
                print(f"\nAPI message: {error_detail}", file=sys.stderr)
        elif e.code >= 500:
            print("=" * 60, file=sys.stderr)
            print("ERROR: Gemini API server error", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print(f"\nThe Gemini API returned a server error (HTTP {e.code}).", file=sys.stderr)
            print("\nWhat to do:", file=sys.stderr)
            print("  1. Wait a few minutes and try again", file=sys.stderr)
            print("  2. Check Gemini API status if the issue persists", file=sys.stderr)
            if error_detail:
                print(f"\nAPI message: {error_detail}", file=sys.stderr)
        else:
            print(f"Error: API request failed with HTTP status {e.code}", file=sys.stderr)
            if error_detail:
                print(f"API message: {error_detail}", file=sys.stderr)
            elif error_body:
                print(f"Response: {error_body}", file=sys.stderr)

        sys.exit(1)
    except urllib.error.URLError as e:
        print("=" * 60, file=sys.stderr)
        print("ERROR: Failed to connect to Gemini API", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"\nConnection error: {e.reason}", file=sys.stderr)
        print("\nWhat to do:", file=sys.stderr)
        print("  1. Check your internet connection", file=sys.stderr)
        print("  2. Verify the API endpoint is accessible", file=sys.stderr)
        print("  3. Check if a firewall or proxy is blocking the request", file=sys.stderr)
        sys.exit(1)


def extract_image_data(response: dict) -> str:
    """Extract base64 image data from the API response."""
    try:
        # Handle both streaming array and single object responses
        if isinstance(response, list):
            candidates = response[0].get("candidates", [])
        else:
            candidates = response.get("candidates", [])

        if not candidates:
            raise ValueError("No candidates in response")

        parts = candidates[0].get("content", {}).get("parts", [])

        for part in parts:
            if "inlineData" in part:
                return part["inlineData"].get("data", "")

        raise ValueError("No image data found in response parts")
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error: Failed to parse response: {e}", file=sys.stderr)
        print(f"Response: {json.dumps(response, indent=2)}", file=sys.stderr)
        sys.exit(1)


def save_image(image_data: str, output_path: Path) -> None:
    """Decode and save the base64 image data."""
    try:
        image_bytes = base64.b64decode(image_data)
        output_path.write_bytes(image_bytes)
    except Exception as e:
        print(f"Error: Failed to save image: {e}", file=sys.stderr)
        sys.exit(1)


def get_file_size(path: Path) -> str:
    """Get human-readable file size."""
    size = path.stat().st_size
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using Google Gemini AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_image.py "A sunset over mountains"
  python generate_image.py "An app icon" ./icons/app.png
  python generate_image.py --size 2K "High-res landscape" ./wallpaper.png
  python generate_image.py --model gemini-3-pro-image-preview "A logo" ./logo.png

Environment Variables:
  GEMINI_API_KEY    Your Google Gemini API key (required)
  IMAGE_SIZE        Image size: 512, 1K (default), or 2K
  GEMINI_MODEL      Model ID for image generation
        """
    )
    parser.add_argument("prompt", help="Text description of the image to generate")
    parser.add_argument("output", nargs="?", default="./generated-image.png",
                        help="Output file path (default: ./generated-image.png)")
    parser.add_argument("--size", choices=["512", "1K", "2K"],
                        help="Image size (overrides IMAGE_SIZE env var)")
    parser.add_argument("--model", "-m",
                        help="Provider model ID")
    parser.add_argument("--provider", choices=["gemini", "atlas"],
                        default=os.environ.get("IMAGE_PROVIDER", "gemini"),
                        help="Image provider (default: gemini)")
    parser.add_argument("--aspect", default="1:1", choices=sorted(VALID_ASPECT_RATIOS),
                        help="Aspect ratio for Atlas Cloud (default: 1:1)")

    args = parser.parse_args()

    # Get configuration
    image_size = args.size or os.environ.get("IMAGE_SIZE", DEFAULT_IMAGE_SIZE)
    image_size = validate_image_size(image_size)
    output_path = Path(args.output)

    # Create output directory
    create_output_dir(output_path)

    # Display info
    print(f"Generating image with prompt: \"{args.prompt}\"")
    print(f"Provider: {args.provider}")
    print(f"Image size: {image_size}")
    print(f"Output path: {output_path}")
    print()

    if args.provider == "atlas":
        if image_size != "1K":
            print("Error: the default Atlas Cloud model currently supports IMAGE_SIZE=1K only", file=sys.stderr)
            sys.exit(1)
        model_id = args.model or os.environ.get("ATLAS_IMAGE_MODEL", DEFAULT_ATLAS_MODEL_ID)
        print(f"Model: {model_id}")
        try:
            generate_atlas_image(
                args.prompt, output_path, get_atlas_api_key(), model_id, args.aspect
            )
        except (RuntimeError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)
    else:
        api_key = get_api_key()
        model_id = args.model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL_ID)
        print(f"Model: {model_id}")
        request_body = build_request_body(args.prompt, image_size)
        response = make_api_request(api_key, model_id, request_body)
        image_data = extract_image_data(response)
        if not image_data:
            print("Error: No image data received from API", file=sys.stderr)
            sys.exit(1)
        save_image(image_data, output_path)

    # Verify and report success
    if output_path.exists() and output_path.stat().st_size > 0:
        file_size = get_file_size(output_path)
        print("Success! Image generated and saved.")
        print(f"File: {output_path}")
        print(f"Size: {file_size}")
    else:
        print(f"Error: Failed to save image to {output_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
