"""artgen command line."""

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

from artgen import gen, project


def cmd_gen(a: argparse.Namespace) -> None:
    p = project.load()
    keys = ("prompt", "negative", "width", "height", "n", "workflow", "image", "mask", "denoise", "upscale")
    base = p.gen | {k: v for k in keys if (v := getattr(a, k)) is not None} | ({"rembg": True} if a.rembg else {})
    base |= {k: str(Path(base[k]).resolve()) for k in ("image", "mask") if k in base}
    # On the command line a non-zero seed and a tag win over the preset.
    job = ({"preset": a.preset} if a.preset else {}) | ({"seed": a.seed} if a.seed else {}) | ({"tag": a.tag} if a.tag else {})
    todo = gen.plan(p, base, job, a.jobs)
    if a.dry_run:
        print(json.dumps(todo, ensure_ascii=False, indent=2))
        return
    gen.run(p, todo, a.gpu or p.modal["gpu"], a.out, a.backend)


def cmd_edit(a: argparse.Namespace) -> None:
    p = project.load()
    job = p.gen | {"workflow": "ph3_edit", "prompt": a.instruction, "image": str(a.image.resolve()), "seed": a.seed, "tag": a.tag,
                   "images": [str(i.resolve()) for i in a.images], "megapixels": a.megapixels}
    job |= {k: v for k in ("upscale",) if (v := getattr(a, k)) is not None} | ({"rembg": True} if a.rembg else {})
    if a.dry_run:
        print(json.dumps(job, ensure_ascii=False, indent=2))
        return
    gen.run(p, [job], a.gpu or p.modal["gpu"], a.out, a.backend)


def cmd_underlay(a: argparse.Namespace) -> None:
    from artgen import underlay  # bpy is slow to import

    p = project.load()
    shot = json.loads(a.shot.read_text())
    for f in underlay.render(shot, a.out or p.out / "underlay", [p.poses] if p.poses else []):
        print(f)


def cmd_sheet(a: argparse.Namespace) -> None:
    from artgen import sheet

    print(sheet.build(a.sheet, a.out or project.load().out / "sheets" / f"{a.sheet.stem}.png"))


def cmd_show(a: argparse.Namespace) -> None:
    subprocess.run(["open" if platform.system() == "Darwin" else "xdg-open", *map(str, a.paths)], check=True)


def cmd_auth(_: argparse.Namespace) -> None:
    subprocess.run([sys.executable, "-m", "modal", "token", "new"], check=True)


def cmd_check(_: argparse.Namespace) -> None:
    import modal

    from artgen import remote, runs

    runs.guard(project.load().modal["max_apps"])
    with modal.enable_output(), remote.app.run():
        out = remote.gpu_info.remote()
    if "GPU" not in out:
        raise SystemExit(out)
    print(out.strip())


def cmd_wait(a: argparse.Namespace) -> None:
    from artgen import runs

    for d in runs.wait(project.load().out, a.timeout):
        print(d)


def cmd_stop(_: argparse.Namespace) -> None:
    from artgen import runs

    for i in runs.stop_all():
        print("stopped", i)


def cmd_skill(a: argparse.Namespace) -> None:
    from importlib.resources import files

    text = files("artgen").joinpath("skill", "SKILL.md").read_text()
    if not a.install:
        print(text, end="")
        return
    dest = a.install / "artgen" / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)
    print(dest)


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="artgen", description=__import__("artgen").__doc__)
    sub = ap.add_subparsers(required=True, metavar="command")

    g = sub.add_parser("gen", help="generate images with ComfyUI on Modal")
    g.add_argument("--preset", default="", help="<who>/<name> from the prompts directory")
    g.add_argument("--jobs", type=Path, help="JSON list of jobs, run in one session")
    g.add_argument("--prompt")
    g.add_argument("--negative")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--width", type=int)
    g.add_argument("--height", type=int)
    g.add_argument("--n", type=int, help="images per job")
    g.add_argument("--tag", default="", help="suffix of the output folder name")
    g.add_argument("--workflow", help="sdxl_txt2img, sdxl_hires_detailer, or post (only --upscale / --rembg on --image)")
    g.add_argument("--image", help="img2img source (redrawn at --denoise), or the picture for post")
    g.add_argument("--mask", help="inpaint mask for --image; white is repainted")
    g.add_argument("--denoise", type=float, help="default 0.55, or 0.9 with --mask")
    g.add_argument("--upscale", type=float, help="enlarge the result by this factor with the upscaler model")
    g.add_argument("--rembg", action="store_true", help="remove the background (transparent PNG)")
    g.add_argument("--gpu", choices=project.MODAL_GPUS, help="default: [modal] gpu of artgen.toml")
    g.add_argument("--backend", choices=project.BACKENDS, help="default: [comfy] backend of artgen.toml")
    g.add_argument("--out", type=Path, help="default: out of artgen.toml")
    g.add_argument("--dry-run", action="store_true", help="print the expanded jobs and stop")
    g.set_defaults(func=cmd_gen)

    e = sub.add_parser("edit", help="edit a picture by an instruction with P-H3-Image")
    e.add_argument("image", type=Path)
    e.add_argument("instruction", help="what to change; other pictures are <Picture 2>, <Picture 3>, ...")
    e.add_argument("--images", type=Path, nargs="*", default=[], help="pictures the instruction refers to")
    e.add_argument("--megapixels", type=float, default=4.0, help="size of the edit (default 4)")
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--tag", default="edit")
    e.add_argument("--upscale", type=float)
    e.add_argument("--rembg", action="store_true")
    e.add_argument("--gpu", choices=project.MODAL_GPUS)
    e.add_argument("--backend", choices=project.BACKENDS)
    e.add_argument("--out", type=Path)
    e.add_argument("--dry-run", action="store_true")
    e.set_defaults(func=cmd_edit)

    u = sub.add_parser("underlay", help="render depth and OpenPose underlays from a shot JSON (local CPU)")
    u.add_argument("shot", type=Path)
    u.add_argument("-o", "--out", type=Path, help="default: <out>/underlay")
    u.set_defaults(func=cmd_underlay)

    s = sub.add_parser("sheet", help="lay text, callouts and a palette over sheet pictures")
    s.add_argument("sheet", type=Path)
    s.add_argument("-o", "--out", type=Path, help="default: <out>/sheets/<name>.png")
    s.set_defaults(func=cmd_sheet)

    sh = sub.add_parser("show", help="open images or folders in the system viewer")
    sh.add_argument("paths", type=Path, nargs="+")
    sh.set_defaults(func=cmd_show)

    w = sub.add_parser("wait", help="block until background gen runs in this project finish; print their output folders")
    w.add_argument("--timeout", type=float, default=1800, help="seconds (default 1800)")
    w.set_defaults(func=cmd_wait)
    sub.add_parser("stop", help="stop every artgen app still up on the Modal account").set_defaults(func=cmd_stop)

    sk = sub.add_parser("skill", help="print the agent skill, or install it into a skills directory")
    sk.add_argument("--install", type=Path, metavar="DIR", help="e.g. .claude/skills; writes DIR/artgen/SKILL.md")
    sk.set_defaults(func=cmd_skill)

    sub.add_parser("auth", help="log in to Modal (interactive)").set_defaults(func=cmd_auth)
    sub.add_parser("check", help="check that a Modal GPU can be rented").set_defaults(func=cmd_check)
    return ap


def main() -> None:
    a = parser().parse_args()
    a.func(a)
