from __future__ import annotations

import importlib.util
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_image.py"
SPEC = importlib.util.spec_from_file_location("generate_image", SCRIPT)
assert SPEC and SPEC.loader
generate_image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_image)


class AtlasProviderTests(unittest.TestCase):
    def test_generation_submits_once_and_downloads_output(self):
        calls = []

        def fake_request(method, path, api_key=None, payload=None):
            calls.append((method, path))
            if path == "/api/v1/models":
                return {
                    "data": [{"model": "atlas/model", "display_console": True}]
                }
            if method == "POST":
                self.assertEqual(api_key, "secret")
                self.assertEqual(payload["aspect_ratio"], "16:9")
                return {"data": {"id": "prediction-1"}}
            return {
                "data": {
                    "status": "completed",
                    "outputs": ["https://example.com/image.png"],
                }
            }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "image.png"
            with (
                mock.patch.object(generate_image, "request_atlas_json", side_effect=fake_request),
                mock.patch.object(
                    generate_image,
                    "download_atlas_output",
                    side_effect=lambda _url, path: path.write_bytes(b"png"),
                ),
            ):
                generate_image.generate_atlas_image(
                    "prompt", output, "secret", "atlas/model", "16:9"
                )

            self.assertEqual(output.read_bytes(), b"png")
            self.assertEqual(sum(method == "POST" for method, _path in calls), 1)
            self.assertEqual([method for method, _path in calls], ["GET", "POST", "GET"])

    def test_prediction_get_retries_transient_failures(self):
        responses = [
            urllib.error.URLError("temporary"),
            {"data": {"status": "processing"}},
            {"data": {"status": "completed", "outputs": ["https://example.com/image.png"]}},
        ]
        with (
            mock.patch.object(generate_image, "request_atlas_json", side_effect=responses),
            mock.patch.object(generate_image.time, "sleep"),
        ):
            output = generate_image.poll_atlas_prediction("secret", "prediction-1", timeout=30)
        self.assertEqual(output, "https://example.com/image.png")

    def test_model_must_be_enabled(self):
        with mock.patch.object(
            generate_image,
            "request_atlas_json",
            return_value={"data": [{"model": "atlas/model", "display_console": False}]},
        ):
            with self.assertRaisesRegex(RuntimeError, "not enabled"):
                generate_image.validate_atlas_model("atlas/model")

    def test_failed_prediction_surfaces_provider_error(self):
        with mock.patch.object(
            generate_image,
            "request_atlas_json",
            return_value={"data": {"status": "failed", "error": "rejected"}},
        ):
            with self.assertRaisesRegex(RuntimeError, "rejected"):
                generate_image.poll_atlas_prediction("secret", "prediction-1", timeout=30)


if __name__ == "__main__":
    unittest.main()
