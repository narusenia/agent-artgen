"""The Modal side: ComfyUI on a GPU, the weight volume, and a GPU check.

Run through `artgen gen` / `artgen check`, which start this app for the duration of one call.
Based on modal-labs/modal-examples@c7c0e3f, 06_gpu_and_ml/comfyui.
Keep this module free of local-only imports (bpy, PIL): the containers import it.
"""

import subprocess
import time
import urllib.request
from pathlib import Path

import modal

from artgen import comfy

COMFY_DIR = "/root/comfy/ComfyUI"
VOLUME = "/models"
PORT = 8188
# ComfyUI asks for a cu130 build on 20-series GPUs and later (T4 is one)
TORCH = "torch==2.14.1 torchvision==0.29.1"
CU130 = "https://download.pytorch.org/whl/cu130"

# Weights go on the volume once, at /models/<ComfyUI folder type>/<file>; ComfyUI reads them through extra_model_paths.yaml.
vol = modal.Volume.from_name("artgen-models", create_if_missing=True)

# Building needs no GPU. comfy-cli cannot find old releases, so ComfyUI is installed with git and pip.
comfy_image = (
    # debian_slim resolves to bullseye on the workspace's image builder version and its security repo 404s
    modal.Image.from_registry("python:3.11-slim-bookworm")
    .apt_install("git", "libgl1", "libglib2.0-0", "gcc")  # gcc: Triton builds the int8 kernels at run time
    .run_commands(f"git clone --depth 1 --branch v0.45.6 https://github.com/comfyanonymous/ComfyUI {COMFY_DIR}")
    .pip_install(*TORCH.split(), index_url=CU130)
    .run_commands(f"pip install -r {COMFY_DIR}/requirements.txt")
    .run_commands(
        # Impact-Pack (FaceDetailer) pinned to the ComfyUI release's era, without letting it upgrade torch
        f"git clone --depth 1 --branch 8.31 https://github.com/ltdrdata/ComfyUI-Impact-Pack {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Pack",
        f"git clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Subpack"
        f" && git -C {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Subpack checkout c8e70fea548ff8e04dfb59a5835048211cf23caf",
        f"pip install -r {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Pack/requirements.txt -r {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Subpack/requirements.txt"
        f" ultralytics==8.3.162 {TORCH} --extra-index-url {CU130}",
        # IPAdapter_plus has been in maintenance mode since 2025-04; pinned to its last commit
        f"git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus {COMFY_DIR}/custom_nodes/ComfyUI_IPAdapter_plus"
        f" && git -C {COMFY_DIR}/custom_nodes/ComfyUI_IPAdapter_plus checkout a0f451a5113cf9becb0847b92884cb10cbdec0ef",
    )
    # Impact-Pack logs a KeyError traceback on every fresh container when its ini is missing
    .run_commands(f"printf '[default]\\n' > {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Pack/impact-pack.ini")
    .add_local_python_source("artgen")
)
dl_image = (
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install("huggingface-hub[hf_xet]==0.36.0", "safetensors==0.5.3")
    .pip_install("torch==2.14.1", index_url="https://download.pytorch.org/whl/cpu")  # only to rewrite `strip` weights
    .add_local_python_source("artgen")
)

app = modal.App("artgen")


def _strip(src: Path, prefix: str, dest: Path) -> None:
    """Training checkpoints keep wrapper prefixes (module._orig_mod.) that ComfyUI does not recognise."""
    import torch
    from safetensors.torch import save_file

    sd = torch.load(src, map_location="cpu", weights_only=True)
    save_file({k.removeprefix(prefix): v.contiguous() for k, v in sd.items() if torch.is_tensor(v)}, dest)
    src.unlink()


@app.function(image=dl_image, volumes={VOLUME: vol}, timeout=1800, max_containers=1)
def fetch_models(wanted: list[dict]) -> str:
    """Downloads the missing ones of `wanted` (models.toml entries) to /models/<folder>/<file> on a CPU."""
    import hashlib

    from huggingface_hub import hf_hub_download

    from artgen.models import stored

    missing = [m for m in wanted if not Path(VOLUME, m["folder"], stored(m)).exists()]
    for m in missing:
        dest = Path(VOLUME, m["folder"], m["file"])
        if m.get("url"):
            data = urllib.request.urlopen(m["url"]).read()
            if hashlib.sha256(data).hexdigest() != m["sha256"]:
                raise RuntimeError(f"sha256 mismatch for {m['url']}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        else:
            hf_hub_download(m["repo"], m["file"], local_dir=f"{VOLUME}/{m['folder']}", revision=m.get("rev"))
        if m.get("strip"):
            _strip(dest, m["strip"], Path(VOLUME, m["folder"], stored(m)))
    if missing:
        vol.commit()
    return f"downloaded {len(missing)}" if missing else "cached"


@app.function(image=dl_image, gpu="T4", timeout=120, max_containers=1)
def gpu_info() -> str:
    return subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, check=True).stdout


@app.cls(image=comfy_image, gpu="T4", volumes={VOLUME: vol}, timeout=900, scaledown_window=30, max_containers=1)
class ComfyUI:
    @modal.enter()
    def start(self):
        # Every folder on the volume is a ComfyUI model folder type (checkpoints, controlnet, ipadapter, ...)
        folders = sorted(d.name for d in Path(VOLUME).iterdir() if d.is_dir())
        Path(COMFY_DIR, "extra_model_paths.yaml").write_text(
            f"artgen:\n  base_path: {VOLUME}\n" + "".join(f"  {f}: {f}\n" for f in folders))
        subprocess.Popen(["python", "main.py", "--port", str(PORT)], cwd=COMFY_DIR)
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/system_stats", timeout=2)
                return
            except OSError:
                time.sleep(1)
        raise RuntimeError("ComfyUI did not start")

    @modal.method()
    def run(self, workflow: dict, inputs: dict[str, bytes] | None = None) -> list[tuple[str, bytes]]:
        return comfy.run(f"http://127.0.0.1:{PORT}", workflow, inputs)
