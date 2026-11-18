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


def _load(inputs: dict[str, bytes], path: str) -> str:
    p = Path(path)
    inputs[p.name] = p.read_bytes()
    return p.name


def _final(wf: dict) -> dict:
    """The SaveImage node that writes the finished picture."""
    return next(n for n in wf.values() if n["class_type"] == "SaveImage" and n["inputs"]["filename_prefix"] == "artgen")


def build(job: dict, cat: dict[str, dict] | None = None) -> tuple[dict, dict[str, bytes]]:
    """Returns the workflow, with models still as "$key" (see models.resolve), and the images its LoadImage nodes read.

    A reference image (ref) drives IP-Adapter on the first sampler only, up to ref_end_at (default 0.6).
    ref_hires=true adds it to the second pass too; running it to the end, or into the second pass,
    left the reference's ground colour and flat shading in, like an unfinished drawing.

    Other job keys: image (img2img at denoise), mask (inpaint inside image; white is repainted),
    control (underlays through ControlNet), loras ([{model, strength}], models declared with folder "loras"),
    upscale (factor) and rembg (transparent background).
    The post workflow only loads image and applies upscale and rembg.
    ph3_edit edits image by the instruction in prompt with P-H3-Image; images adds pictures the instruction
    calls <Picture 2>, <Picture 3>, ...; megapixels sets the size of the edit (default 4).
    """
    if job["workflow"] not in names():
        raise SystemExit(f"unknown workflow {job['workflow']!r}; choose from {names()}")
    wf = json.loads(files("artgen").joinpath("workflows", f"{job['workflow']}.json").read_text())
    cat = cat or models.catalog()
    scale = cat["upscaler"].get("scale", 4)
    inputs: dict[str, bytes] = {}
    if job["workflow"] == "ph3_edit":
        if not job.get("image"):
            raise SystemExit("ph3_edit needs image")
        wf["40"]["inputs"]["image"] = _load(inputs, job["image"])
        wf["31"]["inputs"]["megapixels"] = job.get("megapixels", 4.0)
        wf["30"]["inputs"]["prompt"] = job["prompt"]
        wf["33"]["inputs"]["noise_seed"] = job["seed"]
        for i, extra in enumerate(job.get("images", []), start=2):  # shortcut: n is ignored (one edit per job); repeat jobs for more
            wf[str(80 + i)] = {"class_type": "LoadImage", "inputs": {"image": _load(inputs, extra)}}
            wf["30"]["inputs"][f"images.image_{i}"] = [str(80 + i), 0]
        _post(wf, job, scale)
        return wf, inputs
    if job["workflow"] == "post":
        if not job.get("image"):
            raise SystemExit("the post workflow needs image")
        wf["40"]["inputs"]["image"] = _load(inputs, job["image"])
        _post(wf, job, scale)
        return wf, inputs

    loras = job.get("loras", [])
    for lo in loras:
        if lo["model"] not in cat:
            raise SystemExit(f"unknown lora {lo['model']!r}; declare it with [[model]]")
    triggers = [cat[lo["model"]]["trigger"] for lo in loras if cat[lo["model"]].get("trigger")]
    wf[POS]["inputs"]["text"] = ", ".join([job["prompt"], *triggers])
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

    if job.get("image"):  # the picture is redrawn at the image's own size; width and height are ignored
        wf["40"] = {"class_type": "LoadImage", "inputs": {"image": _load(inputs, job["image"])}}
        wf["41"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["40", 0], "vae": [CKPT, 2]}}
        latent = ["41", 0]
        if job.get("mask"):
            wf["43"] = {"class_type": "LoadImageMask", "inputs": {"image": _load(inputs, job["mask"]), "channel": "red"}}
            wf["44"] = {"class_type": "SetLatentNoiseMask", "inputs": {"samples": latent, "mask": ["43", 0]}}
            latent = ["44", 0]
        wf["42"] = {"class_type": "RepeatLatentBatch", "inputs": {"samples": latent, "amount": job["n"]}}
        wf[SAMPLER]["inputs"]["latent_image"] = ["42", 0]
        wf[SAMPLER]["inputs"]["denoise"] = job.get("denoise", 0.9 if job.get("mask") else 0.55)
        del wf[LATENT]
    elif job.get("mask"):
        raise SystemExit("mask needs image")

    if job.get("ref"):
        wf["20"] = {"class_type": "LoadImage", "inputs": {"image": _load(inputs, job["ref"])}}
        wf["21"] = {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": f"$ipadapter_{job.get('ref_model', 'plus')}"}}
        wf["22"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "$clip_vision"}}
        wf["23"] = {"class_type": "IPAdapterAdvanced", "inputs": {
            "model": [CKPT, 0], "ipadapter": ["21", 0], "image": ["20", 0], "clip_vision": ["22", 0],
            "weight": job.get("ref_weight", 0.6), "weight_type": job.get("ref_weight_type", "linear"), "combine_embeds": "concat",
            "start_at": 0.0, "end_at": job.get("ref_end_at", 0.6), "embeds_scaling": job.get("ref_embeds_scaling", "V only")}}
        if job.get("ref_mask"):  # white is where the reference applies
            wf["24"] = {"class_type": "LoadImageMask", "inputs": {"image": _load(inputs, job["ref_mask"]), "channel": "red"}}
            wf["23"]["inputs"]["attn_mask"] = ["24", 0]
        wf[SAMPLER]["inputs"]["model"] = ["23", 0]
        if job.get("ref_hires") and HIRES_SAMPLER in wf:
            wf[HIRES_SAMPLER]["inputs"]["model"] = ["23", 0]

    pos, neg = [POS, 0], [NEG, 0]
    for i, c in enumerate(job.get("control", [])):  # each underlay chains onto the conditioning of every sampler
        img, loader, apply = (str(50 + 3 * i + k) for k in range(3))
        wf[img] = {"class_type": "LoadImage", "inputs": {"image": _load(inputs, c["image"])}}
        wf[loader] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": f"$controlnet_{c.get('type', 'depth')}"}}
        wf[apply] = {"class_type": "ControlNetApplyAdvanced", "inputs": {
            "positive": pos, "negative": neg, "control_net": [loader, 0], "image": [img, 0], "vae": [CKPT, 2],
            "strength": c.get("strength", 0.7), "start_percent": c.get("start_at", 0.0), "end_percent": c.get("end_at", 0.8)}}
        pos, neg = [apply, 0], [apply, 1]
    for node in wf.values():
        if node["class_type"] in ("KSampler", "FaceDetailer"):
            node["inputs"].update(positive=pos, negative=neg)

    if loras:  # chain the LoRAs after the checkpoint and move everything that read the checkpoint onto the last one
        for node in wf.values():
            for k, v in node["inputs"].items():
                if v in ([CKPT, 0], [CKPT, 1]):
                    node["inputs"][k] = [str(90 + len(loras) - 1), v[1]]
        prev = CKPT
        for i, lo in enumerate(loras):
            s = lo.get("strength", 0.8)
            wf[str(90 + i)] = {"class_type": "LoraLoader", "inputs": {"model": [prev, 0], "clip": [prev, 1],
                               "lora_name": f"${lo['model']}", "strength_model": s, "strength_clip": lo.get("strength_clip", s)}}
            prev = str(90 + i)

    if job.get("stages") and STAGE2_DECODE in wf:  # keep both passes to see where a picture went wrong
        wf["30"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "stage1", "images": [STAGE1_DECODE, 0]}}
        wf["31"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "stage2", "images": [STAGE2_DECODE, 0]}}
    _post(wf, job, scale)
    return wf, inputs


def _post(wf: dict, job: dict, scale: float) -> None:
    """Upscale, then cut out, right before the final SaveImage."""
    save = _final(wf)
    if factor := job.get("upscale"):
        wf["60"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": "$upscaler"}}
        wf["61"] = {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["60", 0], "image": save["inputs"]["images"]}}
        wf["62"] = {"class_type": "ImageScaleBy", "inputs": {"image": ["61", 0], "upscale_method": "lanczos", "scale_by": factor / scale}}
        save["inputs"]["images"] = ["62", 0]
    if job.get("rembg"):
        wf["70"] = {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "$birefnet"}}
        wf["71"] = {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["70", 0], "image": save["inputs"]["images"]}}
        wf["72"] = {"class_type": "InvertMask", "inputs": {"mask": ["71", 0]}}  # JoinImageWithAlpha inverts it back
        wf["73"] = {"class_type": "JoinImageWithAlpha", "inputs": {"image": save["inputs"]["images"], "alpha": ["72", 0]}}
        save["inputs"]["images"] = ["73", 0]
