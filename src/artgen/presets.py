"""Adopted prompts: `<prompts>/_style.toml` shared by every character, plus one `<who>.toml` per character."""

import tomllib

from artgen.project import Project

# Keys copied from a preset into a job as they are.
JOB_KEYS = ("width", "height", "steps", "cfg", "sampler", "workflow", "gpu",
            "ref_model", "ref_weight", "ref_end_at", "ref_weight_type", "ref_embeds_scaling", "ref_hires",
            "denoise", "upscale", "rembg", "megapixels", "loras", "style")


def style(project: Project, job: dict) -> dict:
    """Puts the painting style (<prompts>/styles/<name>.toml: positive, negative, loras) in front of the job's own text."""
    if not job.get("style"):
        return job
    f = project.prompts / "styles" / f"{job['style']}.toml"
    if not f.is_file():
        raise SystemExit(f"no style {job['style']!r} ({f})")
    s = tomllib.loads(f.read_text(encoding="utf-8"))
    join = lambda *xs: ", ".join(x for x in xs if x)
    return job | {"prompt": join(s.get("positive", ""), job["prompt"]), "negative": join(s.get("negative", ""), job["negative"]),
                  "loras": [*s.get("loras", []), *job.get("loras", [])]}


def load(project: Project, spec: str) -> list[dict]:
    """Turns `<who>/<name>` into jobs, one per adopted seed."""
    who, name = spec.split("/")
    style = tomllib.loads((project.prompts / "_style.toml").read_text(encoding="utf-8"))
    presets = tomllib.loads((project.prompts / f"{who}.toml").read_text(encoding="utf-8"))["preset"]
    p = next((p for p in presets if p["name"] == name), None)
    if p is None:
        raise SystemExit(f"no preset {name!r} in {who}.toml")
    parts = []
    for use in ["style", *(u for u in p.get("uses", []) if u != "style")]:
        t = style
        for k in use.split("."):  # dotted path into _style.toml, e.g. "uniform.female"
            t = t[k]
        parts.append(t)
    parts.append(p)
    job = {k: p[k] for k in JOB_KEYS if k in p}
    for k in ("positive", "negative"):
        s = ", ".join(x[k] for x in parts if x.get(k))
        for old, new in p.get("replace", []):
            if old not in s and k == "positive":
                raise SystemExit(f"replace target not found: {old}")
            s = s.replace(old, new)
        job["prompt" if k == "positive" else k] = s
    for k in ("ref", "ref_mask", "image", "mask"):
        if k in p:
            job[k] = str(project.resolve(p[k]))
    if "images" in p:
        job["images"] = [str(project.resolve(i)) for i in p["images"]]
    if "control" in p:
        job["control"] = [c | {"image": str(project.resolve(c["image"]))} for c in p["control"]]
    job["tag"] = f"{who}_{name}"
    return [job | {"seed": s} for s in p.get("seeds", [0])]
