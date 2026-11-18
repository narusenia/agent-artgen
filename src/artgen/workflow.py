"""Fills a bundled ComfyUI workflow (API format) with one job's values."""

import json
from importlib.resources import files
from pathlib import Path

from artgen import models

# Node ids shared by the bundled workflows.
CKPT, LATENT, POS, NEG, SAMPLER, HIRES_SAMPLER = "4", "5", "6", "7", "3", "13"
STAGE1_DECODE, STAGE2_DECODE = "10", "14"


def names() -> list[str]:
    return sorted(p.name.removesuffix(".json") for p in files("artgen").joinpath("workflows").iterdir() if p.name.endswith(".json"))


def build(job: dict) -> tuple[dict, dict[str, bytes]]:
    """Returns the workflow and the images its LoadImage nodes read (name -> bytes).

    A reference image (ref) drives IP-Adapter on the first sampler only, up to ref_end_at (default 0.6).
    ref_hires=true adds it to the second pass too; running it to the end, or into the second pass,
    left the reference's ground colour and flat shading in, like an unfinished drawing.
    """
    if job["workflow"] not in names():
        raise SystemExit(f"unknown workflow {job['workflow']!r}; choose from {names()}")
    wf = json.loads(files("artgen").joinpath("workflows", f"{job['workflow']}.json").read_text())
    wf[POS]["inputs"]["text"] = job["prompt"]
    wf[NEG]["inputs"]["text"] = job["negative"]
    wf[LATENT]["inputs"].update(width=job["width"], height=job["height"], batch_size=job["n"])
    if "steps" in job:  # first pass only; the second pass and the detailer keep the workflow's value
        wf[SAMPLER]["inputs"]["steps"] = job["steps"]
    for node in wf.values():
        i = node["inputs"]
        if "seed" in i:  # one seed for both passes and the detailer
            i["seed"] = job["seed"]
        for key, jk in (("cfg", "cfg"), ("sampler_name", "sampler")):
            if key in i and jk in job:
                i[key] = job[jk]

    inputs = {}
    if job.get("ref"):
        ref = Path(job["ref"])
        inputs[ref.name] = ref.read_bytes()
        wf["20"] = {"class_type": "LoadImage", "inputs": {"image": ref.name}}
        wf["21"] = {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": models.IPA_MODELS[job.get("ref_model", "plus")]}}
        wf["22"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": models.CLIP_VISION_NAME}}
        wf["23"] = {"class_type": "IPAdapterAdvanced", "inputs": {
            "model": [CKPT, 0], "ipadapter": ["21", 0], "image": ["20", 0], "clip_vision": ["22", 0],
            "weight": job.get("ref_weight", 0.6), "weight_type": job.get("ref_weight_type", "linear"), "combine_embeds": "concat",
            "start_at": 0.0, "end_at": job.get("ref_end_at", 0.6), "embeds_scaling": job.get("ref_embeds_scaling", "V only")}}
        if job.get("ref_mask"):  # white is where the reference applies
            mask = Path(job["ref_mask"])
            inputs[mask.name] = mask.read_bytes()
            wf["24"] = {"class_type": "LoadImageMask", "inputs": {"image": mask.name, "channel": "red"}}
            wf["23"]["inputs"]["attn_mask"] = ["24", 0]
        wf[SAMPLER]["inputs"]["model"] = ["23", 0]
        if job.get("ref_hires") and HIRES_SAMPLER in wf:
            wf[HIRES_SAMPLER]["inputs"]["model"] = ["23", 0]
    if job.get("stages") and STAGE2_DECODE in wf:  # keep both passes to see where a picture went wrong
        wf["30"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "stage1", "images": [STAGE1_DECODE, 0]}}
        wf["31"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "stage2", "images": [STAGE2_DECODE, 0]}}
    return wf, inputs
