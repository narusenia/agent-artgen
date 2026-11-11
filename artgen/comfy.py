"""Modal 上の ComfyUI に API 形式のワークフローを投げ、画像を手元に保存する。

uv run --project tools/artgen modal run tools/artgen/artgen/comfy.py --prompt "..." --n 4
参考: modal-labs/modal-examples@c7c0e3f の 06_gpu_and_ml/comfyui
"""

import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import modal

MODEL_REPO = "Laxhar/noobai-XL-1.1"
MODEL_FILE = "NoobAI-XL-v1.1.safetensors"
COMFY_DIR = "/root/comfy/ComfyUI"
CKPT_DIR = f"{COMFY_DIR}/models/checkpoints"

# 重みは Volume に一度だけ置き、起動時に ComfyUI の checkpoints へ symlink する
MODELS = "/models"
vol = modal.Volume.from_name("artgen-models", create_if_missing=True)

# ビルドは GPU なしで済む。comfy-cli 1.5.3 は古い版を探せないので git と pip で直接入れる
comfy_image = (
    # debian_slim は bullseye になり security リポジトリが 404 になるため bookworm を明示
    modal.Image.from_registry("python:3.11-slim-bookworm")
    .apt_install("git")
    .run_commands(f"git clone --depth 1 --branch v0.3.71 https://github.com/comfyanonymous/ComfyUI {COMFY_DIR}")
    .pip_install("torch==2.6.0", "torchvision==0.21.0", "torchaudio==2.6.0", index_url="https://download.pytorch.org/whl/cu124")
    # requests は requirements に無いが server が使う。transformers 5 系は当時の ComfyUI で未検証なので 4 系に留める
    .run_commands(f"pip install -r {COMFY_DIR}/requirements.txt requests 'transformers<5'")
)
dl_image = modal.Image.debian_slim(python_version="3.11").uv_pip_install("huggingface-hub[hf_xet]==0.36.0")

app = modal.App("artgen-comfy")


@app.function(image=dl_image, volumes={MODELS: vol}, timeout=1200)
def fetch_model() -> str:
    """CPU で重みを Volume に落とす。既にあれば何もしない。"""
    if (Path(MODELS) / MODEL_FILE).exists():
        return "cached"
    from huggingface_hub import hf_hub_download

    hf_hub_download(MODEL_REPO, MODEL_FILE, local_dir=MODELS)
    vol.commit()
    return "downloaded"


@app.cls(image=comfy_image, gpu="T4", volumes={MODELS: vol}, timeout=600, scaledown_window=10, max_containers=1)
class ComfyUI:
    @modal.enter()
    def start(self):
        Path(CKPT_DIR, MODEL_FILE).symlink_to(Path(MODELS, MODEL_FILE))
        # PYTHONPATH の /root/comfy.py（このファイル）が ComfyUI の名前空間パッケージ comfy を隠すので外す
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        subprocess.Popen(["python", "main.py", "--port", "8188"], cwd=COMFY_DIR, env=env)
        for _ in range(120):
            try:
                urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=2)
                return
            except OSError:
                time.sleep(1)
        raise RuntimeError("ComfyUI did not start")

    @modal.method()
    def run(self, workflow: dict) -> list[bytes]:
        """ワークフローを実行し、SaveImage の出力を PNG のバイト列で返す。"""
        base = "http://127.0.0.1:8188"
        req = urllib.request.Request(f"{base}/prompt", json.dumps({"prompt": workflow}).encode(), {"Content-Type": "application/json"})
        pid = json.load(urllib.request.urlopen(req))["prompt_id"]
        deadline = time.time() + 540
        while time.time() < deadline:
            hist = json.load(urllib.request.urlopen(f"{base}/history/{pid}"))
            if pid in hist:
                break
            time.sleep(2)
        else:
            raise TimeoutError("ComfyUI did not finish")
        entry = hist[pid]
        if entry.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(entry["status"], ensure_ascii=False)[:2000])
        out = Path(COMFY_DIR, "output")
        return [
            (out / img.get("subfolder", "") / img["filename"]).read_bytes()
            for node in entry["outputs"].values()
            for img in node.get("images", [])
        ]


@app.local_entrypoint()
def main(prompt: str = "", negative: str = "", seed: int = 0, width: int = 832, height: int = 1216, n: int = 2, work: str = "yohakuroku", tag: str = "", jobs: str = ""):
    """jobs に JSON（[{tag, prompt, negative, seed, width, height, n}, ...]）を渡すと、一度の起動でまとめて流す。"""
    here = Path(__file__).resolve()  # 手元でだけ評価する（コンテナ内は /root/comfy.py で親が無い）
    base = dict(prompt=prompt, negative=negative, seed=seed, width=width, height=height, n=n, tag=tag)
    todo = [base | j for j in json.loads(Path(jobs).read_text())] if jobs else [base]
    assert all(j["prompt"] for j in todo), "prompt is required"
    print("model:", fetch_model.remote())
    template = (here.parents[1] / "workflows" / "sdxl_txt2img.json").read_text()
    comfy = ComfyUI()
    t0 = time.time()
    for j in todo:
        wf = json.loads(template)
        wf["6"]["inputs"]["text"] = j["prompt"]
        wf["7"]["inputs"]["text"] = j["negative"]
        wf["3"]["inputs"]["seed"] = j["seed"]
        wf["5"]["inputs"].update(width=j["width"], height=j["height"], batch_size=j["n"])

        t = time.time()
        images = comfy.run.remote(wf)
        name = datetime.now().strftime("%Y%m%d-%H%M%S") + (f"_{j['tag']}" if j["tag"] else "")
        dest = here.parents[3] / "packages" / work / "art" / "out" / name
        dest.mkdir(parents=True, exist_ok=True)
        for i, b in enumerate(images):
            (dest / f"{j['seed']}_{i}.png").write_bytes(b)
        (dest / "workflow.json").write_text(json.dumps(wf, ensure_ascii=False, indent=2))
        print(f"{len(images)} images in {time.time() - t:.0f}s -> {dest}")
    print(f"total {time.time() - t0:.0f}s")
