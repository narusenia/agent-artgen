"""Keeps Modal apps from piling up, and lets an agent wait for a generation started in the background."""

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

APP = "artgen"
LIVE = ("ephemeral", "deployed", "initializing", "running")


def modal_apps() -> list[dict]:
    """artgen apps on the Modal account that are still up, wherever they were started."""
    out = subprocess.run([sys.executable, "-m", "modal", "app", "list", "--json"], capture_output=True, text=True, check=True).stdout
    return [a for a in json.loads(out) if a["description"] == APP and a["state"] in LIVE]


def guard(max_apps: int) -> None:
    live = modal_apps()
    if len(live) >= max_apps:
        ids = ", ".join(a["app_id"] for a in live)
        raise SystemExit(f"{len(live)} artgen app(s) already up ({ids}); wait for them (artgen wait) or stop them (artgen stop)")


def stop_all() -> list[str]:
    ids = [a["app_id"] for a in modal_apps()]
    for i in ids:
        subprocess.run([sys.executable, "-m", "modal", "app", "stop", i], check=True)
    return ids


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextmanager
def marker(out: Path, info: dict):
    """<out>/.runs/<pid>.json while generating, renamed to <pid>.done at exit for `wait` to collect."""
    d = out / ".runs"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{os.getpid()}.json"
    info = {"pid": os.getpid(), "started": time.time(), "dests": [], **info}
    f.write_text(json.dumps(info))
    try:
        yield lambda dest: (info["dests"].append(str(dest)), f.write_text(json.dumps(info)))
    finally:
        info["finished"] = time.time()
        f.write_text(json.dumps(info))
        f.replace(d / f"{os.getpid()}.done")


def running(out: Path) -> list[dict]:
    """Runs still in progress; markers left by a crashed process are removed."""
    found = []
    for f in sorted((out / ".runs").glob("*.json")):
        try:
            info = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if alive(info["pid"]):
            found.append(info)
        else:
            f.unlink(missing_ok=True)
    return found


def wait(out: Path, timeout: float, poll: float = 5) -> list[str]:
    """Blocks until no run is in progress under `out`, then returns (and clears) the output folders of finished runs."""
    deadline = time.time() + timeout
    while runs := running(out):
        if time.time() > deadline:
            raise SystemExit(f"still running after {timeout:.0f}s: pids {[r['pid'] for r in runs]}")
        time.sleep(poll)
    dests = []
    for f in sorted((out / ".runs").glob("*.done")):
        dests += json.loads(f.read_text())["dests"]
        f.unlink()
    return dests
