"""Generation: expands jobs and presets, runs them on Modal in one app session, saves the images."""

import json
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from artgen import presets, runs, workflow
from artgen.project import Project


def expand(project: Project, base: dict, job: dict) -> list[dict]:
    """A job may name a preset; the job's own keys win over it, and a given seed replaces the preset's seeds."""
    if not job.get("preset"):
        return [base | job]
    found = presets.load(project, job["preset"])
    if "seed" in job:
        found = found[:1]
    return [base | p | {k: v for k, v in job.items() if k != "preset"} for p in found]


def plan(project: Project, base: dict, job: dict, jobs_file: Path | None = None) -> list[dict]:
    """Jobs from a JSON list file, or the single job given on the command line."""
    jobs = json.loads(jobs_file.read_text()) if jobs_file else [job]
    todo = [x for j in jobs for x in expand(project, base, j)]
    if not all(j["prompt"] for j in todo):
        raise SystemExit("prompt is required (give --prompt, --preset or --jobs)")
    return todo


def save(dest: Path, seed: int, images: list[tuple[str, bytes]], wf: dict) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    finals = 0
    for name, data in images:
        if name.startswith("artgen"):  # the final SaveImage; stage outputs keep their own prefix
            (dest / f"{seed}_{finals}.png").write_bytes(data)
            finals += 1
        else:
            (dest / f"{seed}_{name}").write_bytes(data)
    (dest / "workflow.json").write_text(json.dumps(wf, ensure_ascii=False, indent=2))


def run(project: Project, todo: list[dict], gpu: str, out: Path | None = None, backend: str | None = None) -> None:
    out = out or project.out
    backend = backend or project.comfy["backend"]
    if backend == "modal":
        project.check_gpu(gpu)
        if any(j.get("gpu", gpu) != gpu for j in todo):
            raise SystemExit(f"a preset asks for a different gpu than {gpu}")
    built = [(j, *workflow.build(j)) for j in todo]  # fail on a bad job before paying for a GPU

    with runs.marker(out, {"jobs": len(built)}) as record, _session(project, gpu, backend) as call:
        t0 = time.time()
        for j, wf, inputs in built:
            t = time.time()
            images = call(wf, inputs)
            dest = out / (datetime.now().strftime("%Y%m%d-%H%M%S") + (f"_{j['tag']}" if j["tag"] else ""))
            save(dest, j["seed"], images, wf)
            record(dest)
            print(f"{len(images)} images in {time.time() - t:.0f}s on {gpu if backend == 'modal' else project.comfy['url']} -> {dest}")
        print(f"total {time.time() - t0:.0f}s")


@contextmanager
def _session(project: Project, gpu: str, backend: str):
    """Yields call(workflow, inputs) -> images. A local ComfyUI must already have the models in models.ALL."""
    if backend == "local":
        from artgen import comfy

        yield lambda wf, inputs: comfy.run(project.comfy["url"], wf, inputs)
        return
    import modal

    from artgen import remote

    runs.guard(project.modal["max_apps"])
    with modal.enable_output(), remote.app.run():
        print("models:", remote.fetch_models.remote())
        m = project.modal
        c = remote.ComfyUI.with_options(gpu=gpu, timeout=m["timeout"], scaledown_window=m["scaledown"])()
        yield c.run.remote
