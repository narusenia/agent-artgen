"""Talks to a running ComfyUI server over HTTP. Used inside the Modal container and against a local ComfyUI.

Standard library only: the containers import this module.
"""

import json
import time
import urllib.parse
import urllib.request
import uuid


def _upload(base: str, name: str, data: bytes) -> None:
    boundary = uuid.uuid4().hex
    body = b"".join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n".encode(),
        data,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(f"{base}/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    urllib.request.urlopen(req).read()


def run(base: str, workflow: dict, inputs: dict[str, bytes] | None = None, timeout: float = 840, poll: float = 2) -> list[tuple[str, bytes]]:
    """Runs a workflow and returns every SaveImage output as (file name, PNG bytes)."""
    base = base.rstrip("/")
    for name, data in (inputs or {}).items():
        _upload(base, name, data)
    req = urllib.request.Request(f"{base}/prompt", json.dumps({"prompt": workflow}).encode(), {"Content-Type": "application/json"})
    pid = json.load(urllib.request.urlopen(req))["prompt_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        hist = json.load(urllib.request.urlopen(f"{base}/history/{pid}"))
        if pid in hist:
            break
        time.sleep(poll)
    else:
        raise TimeoutError("ComfyUI did not finish")
    entry = hist[pid]
    if entry.get("status", {}).get("status_str") == "error":
        raise RuntimeError(json.dumps(entry["status"], ensure_ascii=False)[:2000])
    return [
        (img["filename"], urllib.request.urlopen(f"{base}/view?" + urllib.parse.urlencode(
            {"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")})).read())
        for node in entry["outputs"].values()
        for img in node.get("images", [])
        if img.get("type", "output") == "output"  # skip PreviewImage temps
    ]
