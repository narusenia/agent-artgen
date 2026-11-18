"""Model weights: the bundled models.toml, overridden by the work's [[model]] entries.

Workflows name a model as "$<key>"; `resolve` swaps in the name ComfyUI sees and reports what a run must download.
Standard library only: the containers import this module.
"""

import tomllib
from importlib.resources import files

FIELDS = {"key", "folder", "file", "name", "repo", "rev", "url", "sha256", "scale", "trigger", "strip"}


def _check(m: dict, where: str) -> dict:
    if unknown := set(m) - FIELDS:
        raise SystemExit(f"{where}: unknown keys in [[model]] {m.get('key')!r}: {sorted(unknown)}")
    if missing := {"key", "folder", "file"} - set(m):
        raise SystemExit(f"{where}: [[model]] {m.get('key')!r} needs {sorted(missing)}")
    if bool(m.get("repo")) == bool(m.get("url")):
        raise SystemExit(f"{where}: [[model]] {m['key']!r} needs exactly one of repo and url")
    if m.get("url") and not m.get("sha256"):
        raise SystemExit(f"{where}: [[model]] {m['key']!r} with a url needs sha256")
    return m


def catalog(overrides: list[dict] | None = None, where: str = "artgen.toml") -> dict[str, dict]:
    """key -> model entry. A work's entry replaces the bundled one with the same key."""
    bundled = tomllib.loads(files("artgen").joinpath("models.toml").read_text())["model"]
    out = {m["key"]: _check(m, "models.toml") for m in bundled}
    return out | {m.get("key"): _check(m, where) for m in overrides or []}


def stored(m: dict) -> str:
    """Path under the folder once downloaded: with `strip`, the weights are renamed and kept as .safetensors."""
    return m["file"].rsplit(".", 1)[0] + ".safetensors" if m.get("strip") else m["file"]


def name(m: dict) -> str:
    return m.get("name", stored(m))


def resolve(workflow: dict, cat: dict[str, dict]) -> list[dict]:
    """Replaces every "$key" input in place with the model's ComfyUI name; returns the models used."""
    used = {}
    for node in workflow.values():
        for k, v in node["inputs"].items():
            if isinstance(v, str) and v.startswith("$"):
                if v[1:] not in cat:
                    raise SystemExit(f"workflow refers to unknown model {v}; declare it with [[model]]")
                used[v[1:]] = cat[v[1:]]
                node["inputs"][k] = name(cat[v[1:]])
    return list(used.values())
