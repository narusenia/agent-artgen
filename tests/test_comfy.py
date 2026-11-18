import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from artgen import comfy


class Stub(BaseHTTPRequestHandler):
    """Just enough of the ComfyUI API: upload, prompt, history, view."""

    uploads: list[bytes] = []
    status = "success"

    def log_message(self, *a):
        pass

    def _send(self, body: bytes, ctype="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/upload/image":
            Stub.uploads.append(body)
            self._send(b"{}")
        else:
            assert json.loads(body)["prompt"] == {"1": {}}
            self._send(b'{"prompt_id": "p1"}')

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/history/p1":
            images = [{"filename": "artgen_00001_.png", "subfolder": "", "type": "output"}, {"filename": "tmp.png", "type": "temp"}]
            self._send(json.dumps({"p1": {"status": {"status_str": Stub.status}, "outputs": {"9": {"images": images}}}}).encode())
        elif u.path == "/view":
            self._send(("png:" + parse_qs(u.query)["filename"][0]).encode(), "image/png")


class RunTest(unittest.TestCase):
    def setUp(self):
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_port}/"
        Stub.uploads, Stub.status = [], "success"

    def tearDown(self):
        self.srv.shutdown()

    def test_uploads_inputs_and_returns_outputs_only(self):
        out = comfy.run(self.base, {"1": {}}, {"ref.png": b"REFDATA"}, poll=0)
        self.assertEqual(out, [("artgen_00001_.png", b"png:artgen_00001_.png")])
        self.assertIn(b'filename="ref.png"', Stub.uploads[0])
        self.assertIn(b"REFDATA", Stub.uploads[0])

    def test_error_status_raises(self):
        Stub.status = "error"
        with self.assertRaises(RuntimeError):
            comfy.run(self.base, {"1": {}}, poll=0)


if __name__ == "__main__":
    unittest.main()
