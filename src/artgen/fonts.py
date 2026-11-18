"""Fonts for sheet text (Noto Sans JP 2.004 / Noto Serif JP 2.003, SIL OFL 1.1), fetched once into the user cache."""

import hashlib
import os
import subprocess
from importlib.resources import files
from pathlib import Path

BASE = "https://raw.githubusercontent.com/notofonts/noto-cjk"
SOURCES = {
    **{f"NotoSansJP-{w}.otf": f"{BASE}/Sans2.004/Sans/SubsetOTF/JP/NotoSansJP-{w}.otf" for w in ("Regular", "Bold")},
    **{f"NotoSerifJP-{w}.otf": f"{BASE}/Serif2.003/Serif/SubsetOTF/JP/NotoSerifJP-{w}.otf" for w in ("Regular", "Bold")},
    "OFL.txt": f"{BASE}/Sans2.004/LICENSE",
}
SHA256 = dict(line.split()[::-1] for line in files("artgen").joinpath("fonts.sha256").read_text().splitlines() if line)


def cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "artgen" / "fonts"


def path(name: str) -> Path:
    """Returns the cached font, downloading and checking it (and the licence) on first use."""
    d = cache_dir()
    for n in (name, "OFL.txt"):
        p = d / n
        if p.exists():
            continue
        d.mkdir(parents=True, exist_ok=True)
        # curl uses the system trust store; some Python builds cannot find one
        data = subprocess.run(["curl", "-fsSL", SOURCES[n]], capture_output=True, check=True).stdout
        if hashlib.sha256(data).hexdigest() != SHA256[n]:
            raise SystemExit(f"checksum mismatch for {n}")
        p.write_bytes(data)
    return d / name
