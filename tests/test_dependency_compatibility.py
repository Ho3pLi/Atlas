"""Dependency compatibility checks using synthetic data and no external APIs."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import certifi
import httpx
from PIL import Image
from atlas import fileHandler, screenshot


def text_pdf():
    """A one-page fixture with real cross-reference offsets."""
    stream = b"BT /F1 12 Tf 72 720 Td (Atlas compatibility test) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    data, offsets = b"%PDF-1.4\n", []
    for number, value in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(number).encode() + b" 0 obj\n" + value + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    return data + b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"


class DependencyCompatibilityTests(unittest.TestCase):
    def test_native_speech_backend_can_report_cpu_types(self):
        import ctranslate2
        from faster_whisper import WhisperModel

        self.assertTrue(callable(WhisperModel))
        self.assertIn("float32", ctranslate2.get_supported_compute_types("cpu"))

    def test_pdf_extraction_uses_updated_pdf_stack(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.pdf"
            path.write_bytes(text_pdf())
            self.assertIn("Atlas compatibility test", fileHandler.readFileContent(str(path)))

    def test_screenshot_and_vision_without_real_capture_or_api(self):
        with tempfile.TemporaryDirectory() as folder, Image.new("RGBA", (16, 12), "red") as synthetic:
            path = str(Path(folder) / "synthetic.png")
            with patch("PIL.ImageGrab.grab", return_value=synthetic), \
                    patch.object(screenshot.config.app, "screenshot_path", path):
                self.assertEqual(screenshot.takeScreenshot()["status"], "ok")
            with Image.open(path) as image:
                self.assertEqual((image.mode, image.size), ("RGB", (16, 12)))
            with patch.object(screenshot.config, "get_gemini_model") as model:
                model.return_value.generate_content.return_value = SimpleNamespace(text="synthetic description")
                self.assertEqual(screenshot.visionPrompt("synthetic prompt", path), "synthetic description")
                image = model.return_value.generate_content.call_args.args[0][1]
                self.assertIsInstance(image, Image.Image)
                image.close()

    def test_http_stack_and_ca_bundle_on_loopback(self):
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                body = b"synthetic response"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        context = ssl.create_default_context(cafile=certifi.where())
        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with httpx.Client(trust_env=False, timeout=5) as client:
                    response = client.get(f"http://127.0.0.1:{server.server_port}/synthetic")
                self.assertEqual((response.status_code, response.text), (200, "synthetic response"))
            finally:
                server.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
