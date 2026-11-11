"""Modal 上の ComfyUI に API 形式のワークフローを投げ、画像を手元に保存する。

uv run --project tools/artgen modal run tools/artgen/artgen/comfy.py --prompt "..." --n 4
参考: modal-labs/modal-examples@c7c0e3f の 06_gpu_and_ml/comfyui
"""

import json
import os
import subprocess
import time
import tomllib
import urllib.request
from datetime import datetime
from pathlib import Path

import modal

MODEL_REPO = "Laxhar/noobai-XL-1.1"
MODEL_FILE = "NoobAI-XL-v1.1.safetensors"
DETECTOR_REPO = "Bingsu/adetailer"
DETECTORS = ["face_yolov8m.pt", "hand_yolov8s.pt"]  # sdxl_hires_detailer.json の顔・手の修正で使う
# IP-Adapter（参照画像を効かせる）。PLUS の SDXL 版と、対応する ViT-H の画像エンコーダ
IPA_REPO = "h94/IP-Adapter"
IPA_FILE = "sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"
CLIPV_FILE = "models/image_encoder/model.safetensors"
# NoobAI で学習した IP-Adapter（kataragi、ViT-H で動く）。版はコミットで固定
NOOB_IPA_REPO, NOOB_IPA_REV = "kataragi/Noob_ipadapter", "8e2c039824185add88e917e7dfd350e8188f42b3"
NOOB_IPA_FILE = "ip_adapter_Noobtest_800000.bin"
IPA_MODELS = {"plus": IPA_FILE, "noob": f"noob/{NOOB_IPA_FILE}"}  # jobs の ref_model で選ぶ
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
    # 顔・手の修正（FaceDetailer）。版は ComfyUI 0.3.71 と同じ時期に固定し、torch は上げさせない
    .apt_install("libgl1", "libglib2.0-0")
    .run_commands(
        f"git clone --depth 1 --branch 8.28 https://github.com/ltdrdata/ComfyUI-Impact-Pack {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Pack",
        f"git clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Subpack"
        f" && git -C {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Subpack checkout 50c7b71a6a224734cc9b21963c6d1926816a97f1",
        f"pip install -r {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Pack/requirements.txt -r {COMFY_DIR}/custom_nodes/ComfyUI-Impact-Subpack/requirements.txt"
        " ultralytics==8.3.162 torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 'transformers<5'"
        " --extra-index-url https://download.pytorch.org/whl/cu124",
        # IPAdapter_plus は 2025-04 から保守モード。最後のコミットに固定（追加の依存なし）
        f"git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus {COMFY_DIR}/custom_nodes/ComfyUI_IPAdapter_plus"
        f" && git -C {COMFY_DIR}/custom_nodes/ComfyUI_IPAdapter_plus checkout a0f451a5113cf9becb0847b92884cb10cbdec0ef",
    )
)
dl_image = modal.Image.debian_slim(python_version="3.11").uv_pip_install("huggingface-hub[hf_xet]==0.36.0")

app = modal.App("artgen-comfy")


@app.function(image=dl_image, volumes={MODELS: vol}, timeout=1200)
def fetch_model() -> str:
    """CPU で重みを Volume に落とす。既にあれば何もしない。"""
    from huggingface_hub import hf_hub_download

    want = [(MODEL_REPO, MODEL_FILE, MODELS)] + [(DETECTOR_REPO, f, f"{MODELS}/ultralytics/bbox") for f in DETECTORS]
    want += [(IPA_REPO, IPA_FILE, f"{MODELS}/ipadapter"), (IPA_REPO, CLIPV_FILE, f"{MODELS}/clip_vision")]
    want = [(*w, None) for w in want] + [(NOOB_IPA_REPO, NOOB_IPA_FILE, f"{MODELS}/ipadapter/noob", NOOB_IPA_REV)]
    missing = [w for w in want if not Path(w[2], w[1]).exists()]
    for repo, f, d, rev in missing:
        hf_hub_download(repo, f, local_dir=d, revision=rev)
    if missing:
        vol.commit()
    return f"downloaded {len(missing)}" if missing else "cached"


@app.cls(image=comfy_image, gpu="T4", volumes={MODELS: vol}, timeout=900, scaledown_window=30, max_containers=1)
class ComfyUI:
    @modal.enter()
    def start(self):
        Path(CKPT_DIR, MODEL_FILE).symlink_to(Path(MODELS, MODEL_FILE))
        Path(COMFY_DIR, "models", "ultralytics").symlink_to(Path(MODELS, "ultralytics"))
        Path(COMFY_DIR, "models", "ipadapter").symlink_to(Path(MODELS, "ipadapter"))
        Path(COMFY_DIR, "models", "clip_vision", "ipa").symlink_to(Path(MODELS, "clip_vision"))
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
    def run(self, workflow: dict, inputs: dict[str, bytes] | None = None) -> list[tuple[str, bytes]]:
        """ワークフローを実行し、SaveImage の出力を PNG のバイト列で返す。inputs は LoadImage が読む画像（名前→中身）。"""
        for name, data in (inputs or {}).items():
            Path(COMFY_DIR, "input", name).write_bytes(data)
        base = "http://127.0.0.1:8188"
        req = urllib.request.Request(f"{base}/prompt", json.dumps({"prompt": workflow}).encode(), {"Content-Type": "application/json"})
        pid = json.load(urllib.request.urlopen(req))["prompt_id"]
        deadline = time.time() + 840
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
            (img["filename"], (out / img.get("subfolder", "") / img["filename"]).read_bytes())
            for node in entry["outputs"].values()
            for img in node.get("images", [])
        ]


PRESET_KEYS = ("width", "height", "steps", "cfg", "sampler", "workflow", "gpu", "ref_model", "ref_weight", "ref_end_at", "ref_weight_type", "ref_embeds_scaling", "ref_hires")


def load_preset(pkg: Path, spec: str) -> list[dict]:
    """<人物>/<name> の preset（art/prompts/<人物>.toml）を、_style.toml と合わせて jobs の形にする。seed ごとに一件。"""
    who, name = spec.split("/")
    d = pkg / "art" / "prompts"
    style = tomllib.loads((d / "_style.toml").read_text())
    p = next(p for p in tomllib.loads((d / f"{who}.toml").read_text())["preset"] if p["name"] == name)
    parts = []
    for u in ["style"] + [u for u in p.get("uses", []) if u != "style"]:
        t = style
        for k in u.split("."):
            t = t[k]
        parts.append(t)
    parts.append(p)
    job = {k: p[k] for k in PRESET_KEYS if k in p}
    for k in ("positive", "negative"):
        s = ", ".join(x[k] for x in parts if x.get(k))
        for old, new in p.get("replace", []):
            assert old in s or k == "negative", f"replace target not found: {old}"
            s = s.replace(old, new)
        job["prompt" if k == "positive" else k] = s
    for k in ("ref", "ref_mask"):
        if k in p:
            job[k] = str(pkg / p[k])
    job["tag"] = f"{who}_{name}"
    return [job | {"seed": s} for s in p.get("seeds", [0])]


@app.local_entrypoint()
def main(prompt: str = "", negative: str = "", seed: int = 0, width: int = 832, height: int = 1216, n: int = 2, work: str = "yohakuroku", tag: str = "", jobs: str = "", workflow: str = "sdxl_txt2img", gpu: str = "T4", preset: str = ""):
    """jobs に JSON（[{tag, prompt, negative, seed, width, height, n, workflow, ref, ref_weight}, ...]）を渡すと、一度の起動でまとめて流す。

    preset は <人物>/<name>（packages/<work>/art/prompts/<人物>.toml の [[preset]]）。jobs の各項目にも "preset" を書ける（項目の値が優先）。
    コマンド行の --seed（0 以外）・--n・--tag は preset より優先する。

    ref は参照画像のパス（手元）。指定すると IP-Adapter を一段目の KSampler に、ref_end_at（既定 0.6）までだけ掛ける。
    ref_hires=true で二段目にも掛ける。最後まで・二段目まで掛けると参照の地色と平板な塗りが残り、描きかけのような絵になった。
    ref_model は plus（SDXL 用 PLUS、既定）か noob（NoobAI 用）。ref_weight_type・ref_embeds_scaling は IPAdapterAdvanced の値をそのまま渡す。
    ref_mask は効かせる範囲の白黒画像（手元のパス、白が効く所）。
    stages=true で一段目（stage1）と二段目（stage2）の画像も保存する（切り分け用）。

    workflow は workflows/ のファイル名（sdxl_txt2img か sdxl_hires_detailer）。gpu は T4 か L4（費用の決まりでそれより上は使わない）。
    """
    assert gpu in ("T4", "L4"), gpu
    here = Path(__file__).resolve()  # 手元でだけ評価する（コンテナ内は /root/comfy.py で親が無い）
    base = dict(prompt=prompt, negative=negative, seed=seed, width=width, height=height, n=n, tag=tag, workflow=workflow)
    pkg = here.parents[3] / "packages" / work

    def expand(j: dict) -> list[dict]:
        if not j.get("preset"):
            return [base | j]
        pjs = load_preset(pkg, j["preset"])
        if "seed" in j:  # seed を指定したら preset の seeds は使わない
            pjs = pjs[:1]
        return [base | pj | {k: v for k, v in j.items() if k != "preset"} for pj in pjs]

    if jobs:
        todo = [x for j in json.loads(Path(jobs).read_text()) for x in expand(j)]
    else:
        todo = expand({"preset": preset} | ({"seed": seed} if seed else {}) | ({"tag": tag} if tag else {}))
    assert all(j["prompt"] for j in todo), "prompt is required"
    assert all(j.get("gpu", gpu) == gpu for j in todo), f"preset gpu differs from --gpu {gpu}"
    print("model:", fetch_model.remote())
    comfy = ComfyUI.with_options(gpu=gpu)()
    t0 = time.time()
    for j in todo:
        wf = json.loads((here.parents[1] / "workflows" / f"{j['workflow']}.json").read_text())
        wf["6"]["inputs"]["text"] = j["prompt"]
        wf["7"]["inputs"]["text"] = j["negative"]
        for node in wf.values():  # 一段目・二段目・顔と手の修正のシードを揃える
            if "seed" in node["inputs"]:
                node["inputs"]["seed"] = j["seed"]
        wf["5"]["inputs"].update(width=j["width"], height=j["height"], batch_size=j["n"])
        if "steps" in j:  # 一段目だけ。二段目と修正は workflow の値のまま
            wf["3"]["inputs"]["steps"] = j["steps"]
        for node in wf.values():
            for k, jk in (("cfg", "cfg"), ("sampler_name", "sampler")):
                if k in node["inputs"] and jk in j:
                    node["inputs"][k] = j[jk]
        inputs = {}
        if j.get("ref"):
            ref = Path(j["ref"])
            inputs[ref.name] = ref.read_bytes()
            wf["20"] = {"class_type": "LoadImage", "inputs": {"image": ref.name}}
            wf["21"] = {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": IPA_MODELS[j.get("ref_model", "plus")]}}
            wf["22"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": f"ipa/{CLIPV_FILE}"}}
            wf["23"] = {"class_type": "IPAdapterAdvanced", "inputs": {
                "model": ["4", 0], "ipadapter": ["21", 0], "image": ["20", 0], "clip_vision": ["22", 0],
                "weight": j.get("ref_weight", 0.6), "weight_type": j.get("ref_weight_type", "linear"), "combine_embeds": "concat",
                "start_at": 0.0, "end_at": j.get("ref_end_at", 0.6), "embeds_scaling": j.get("ref_embeds_scaling", "V only")}}
            if j.get("ref_mask"):
                mask = Path(j["ref_mask"])
                inputs[mask.name] = mask.read_bytes()
                wf["24"] = {"class_type": "LoadImageMask", "inputs": {"image": mask.name, "channel": "red"}}
                wf["23"]["inputs"]["attn_mask"] = ["24", 0]
            wf["3"]["inputs"]["model"] = ["23", 0]
            if j.get("ref_hires") and "13" in wf:
                wf["13"]["inputs"]["model"] = ["23", 0]
        if j.get("stages") and "14" in wf:
            wf["30"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "stage1", "images": ["10", 0]}}
            wf["31"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "stage2", "images": ["14", 0]}}

        t = time.time()
        images = comfy.run.remote(wf, inputs)
        name = datetime.now().strftime("%Y%m%d-%H%M%S") + (f"_{j['tag']}" if j["tag"] else "")
        dest = here.parents[3] / "packages" / work / "art" / "out" / name
        dest.mkdir(parents=True, exist_ok=True)
        finals = 0
        for fname, b in images:
            if fname.startswith("artgen"):
                (dest / f"{j['seed']}_{finals}.png").write_bytes(b)
                finals += 1
            else:
                (dest / f"{j['seed']}_{fname}").write_bytes(b)
        (dest / "workflow.json").write_text(json.dumps(wf, ensure_ascii=False, indent=2))
        print(f"{len(images)} images in {time.time() - t:.0f}s on {gpu} -> {dest}")
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":  # 自己チェック: uv run --project tools/artgen python tools/artgen/artgen/comfy.py
    j = load_preset(Path(__file__).resolve().parents[3] / "packages" / "yohakuroku", "seres/uniform_stance_ipa")[0]
    assert j["prompt"].startswith("masterpiece") and "1girl" in j["prompt"] and "loli" in j["negative"], j
    assert j["seed"] == 7000 and j["tag"] == "seres_uniform_stance_ipa" and Path(j["ref"]).exists() and Path(j["ref_mask"]).exists(), j
    print("ok")
