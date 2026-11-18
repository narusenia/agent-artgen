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

from artgen import comfy, models

COMFY_DIR = "/root/comfy/ComfyUI"
VOLUME = "/models"
PORT = 8188
TORCH = "torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0"
CU124 = "https://download.pytorch.org/whl/cu124"

# Weights go on the volume once and are symlinked into ComfyUI's model folders at start.
vol = modal.Volume.from_name("artgen-models", create_if_missing=True)

# Building needs no GPU. comfy-cli cannot find old releases, so ComfyUI is installed with git and pip.
comfy_image = (
    # debian_slim resolves to bullseye on this image builder version and its security repo 404s
    modal.Image.from_registry("python:3.11-slim-bookworm")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .run_commands(f"git clone --depth 1 --branch v0.3.71 https://github.com/comfyanonymous/ComfyUI {COMFY_DIR}")
    .pip_install(*TORCH.split(), index_url=CU124)
    # The server imports requests without listing it. transformers 5 is untested with this ComfyUI.
    .run_commands(f"pip install -r {COMFY_DIR}/requirements.txt requests 'transformers<5'")
    .run_commands(
        # Impact-Pack (FaceDetailer) pinned to the ComfyUI release's era, without letting it upgrade torch
        f"git clone --depth 1 --branch 8.28 https://github.com/ltdrdata/ComfyUI-Impact-Pack {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Pack",
        f"git clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Subpack"
        f" && git -C {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Subpack checkout 50c7b71a6a224734cc9b21963c6d1926816a97f1",
        f"pip install -r {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Pack/requirements.txt -r {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Subpack/requirements.txt"
        f" ultralytics==8.3.162 {TORCH} 'transformers<5' --extra-index-url {CU124}",
        # IPAdapter_plus has been in maintenance mode since 2025-04; pinned to its last commit
        f"git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus {COMFY_DIR}/custom_nodes/ComfyUI_IPAdapter_plus"
        f" && git -C {COMFY_DIR}/custom_nodes/ComfyUI_IPAdapter_plus checkout a0f451a5113cf9becb0847b92884cb10cbdec0ef",
    )
    .add_local_python_source("artgen")
)
dl_image = modal.Image.debian_slim(python_version="3.11").uv_pip_install("huggingface-hub[hf_xet]==0.36.0").add_local_python_source("artgen")

app = modal.App("artgen")


@app.function(image=dl_image, volumes={VOLUME: vol}, timeout=1200, max_containers=1)
def fetch_models() -> str:
    """Downloads missing weights to the volume on a CPU."""
    from huggingface_hub import hf_hub_download

    missing = [m for m in models.ALL if not Path(VOLUME, m[2], m[1]).exists()]
    for repo, file, sub, rev in missing:
        hf_hub_download(repo, file, local_dir=f"{VOLUME}/{sub}", revision=rev)
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
        m = Path(COMFY_DIR, "models")
        Path(m, "checkpoints", models.CHECKPOINT[1]).symlink_to(Path(VOLUME, models.CHECKPOINT[1]))
        Path(m, "ultralytics").symlink_to(Path(VOLUME, "ultralytics"))
        Path(m, "ipadapter").symlink_to(Path(VOLUME, "ipadapter"))
        Path(m, "clip_vision", "ipa").symlink_to(Path(VOLUME, "clip_vision"))
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
