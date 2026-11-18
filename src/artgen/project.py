"""The work that uses artgen, described by an `artgen.toml` found by walking up from the current directory.

    out = "art/out"            # generated images (paths are relative to artgen.toml)
    prompts = "art/prompts"    # adopted presets: _style.toml and <who>.toml
    poses = "art/poses"        # extra pose shelf, searched before the bundled one

    [comfy]
    backend = "modal"          # "modal": ComfyUI on a Modal GPU; "local": a ComfyUI already running at url
    url = "http://127.0.0.1:8188"

    [modal]
    gpu = "T4"                 # default GPU
    gpus = ["T4", "L4"]        # GPUs allowed with --gpu or a preset's gpu
    max_apps = 1               # artgen apps allowed up at once on the Modal account
    timeout = 900              # seconds per ComfyUI container
    scaledown = 30             # seconds an idle container stays up

    [gen]                      # defaults for `artgen gen`; the command line wins
    style = ""                 # painting style: <prompts>/styles/<name>.toml
    workflow = "sdxl_txt2img"
    width = 832
    height = 1216
    n = 2
    negative = ""
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG = "artgen.toml"
MODAL_GPUS = ("T4", "L4", "A10G", "L40S", "A100", "H100")  # what Modal offers; a project narrows it with `gpus`
MODAL_DEFAULTS = {"gpu": "T4", "gpus": ["T4", "L4"], "max_apps": 1, "timeout": 900, "scaledown": 30}
COMFY_DEFAULTS = {"backend": "modal", "url": "http://127.0.0.1:8188"}
GEN_DEFAULTS = {"style": "", "prompt": "", "negative": "", "seed": 0, "width": 832, "height": 1216, "n": 2, "tag": "", "workflow": "sdxl_txt2img"}
TOP_KEYS = {"out", "prompts", "poses", "comfy", "modal", "gen", "model"}
BACKENDS = ("modal", "local")


@dataclass(frozen=True)
class Project:
    root: Path  # directory holding artgen.toml; relative paths in presets and jobs resolve against it
    out: Path
    prompts: Path
    poses: Path | None
    comfy: dict = field(default_factory=lambda: dict(COMFY_DEFAULTS))
    modal: dict = field(default_factory=lambda: dict(MODAL_DEFAULTS))
    gen: dict = field(default_factory=lambda: dict(GEN_DEFAULTS))
    models: list = field(default_factory=list)  # [[model]] entries; see models.toml

    def resolve(self, p: str | Path) -> Path:
        return (self.root / p).resolve()

    def check_gpu(self, gpu: str) -> str:
        if gpu not in self.modal["gpus"]:
            raise SystemExit(f"gpu {gpu} is not in [modal] gpus {self.modal['gpus']} of {self.root / CONFIG}")
        return gpu


def find(start: Path | None = None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    return next((d / CONFIG for d in (here, *here.parents) if (d / CONFIG).is_file()), None)


def _section(c: dict, name: str, defaults: dict, where: Path | None) -> dict:
    s = c.get(name, {})
    if unknown := set(s) - set(defaults):
        raise SystemExit(f"{where}: unknown keys in [{name}]: {sorted(unknown)}")
    return defaults | s


def load(config: Path | None = None) -> Project:
    """Reads the project config; without one, works in the current directory with defaults."""
    config = config or find()
    root = config.parent.resolve() if config else Path.cwd().resolve()
    c = tomllib.loads(config.read_text(encoding="utf-8")) if config else {}
    if unknown := set(c) - TOP_KEYS:
        raise SystemExit(f"{config}: unknown keys {sorted(unknown)}")
    comfy = _section(c, "comfy", COMFY_DEFAULTS, config)
    if comfy["backend"] not in BACKENDS:
        raise SystemExit(f"{config}: [comfy] backend must be one of {BACKENDS}")
    modal = _section(c, "modal", MODAL_DEFAULTS, config)
    if bad := set(modal["gpus"]) - set(MODAL_GPUS):
        raise SystemExit(f"{config}: unknown GPUs {sorted(bad)}; Modal offers {MODAL_GPUS}")
    p = Project(
        root=root,
        out=root / c.get("out", "out"),
        prompts=root / c.get("prompts", "prompts"),
        poses=root / c["poses"] if "poses" in c else None,
        comfy=comfy,
        modal=modal,
        gen=_section(c, "gen", GEN_DEFAULTS, config),
        models=c.get("model", []),
    )
    p.check_gpu(modal["gpu"])
    return p
