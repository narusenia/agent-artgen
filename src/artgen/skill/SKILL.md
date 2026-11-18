---
name: artgen
description: Generate and edit character art, sheets and pose underlays with the artgen CLI (ComfyUI on Modal, Blender locally). Use when asked to draw, generate, redo or vary a character picture, build a character sheet, render a pose underlay, or re-run an adopted prompt preset in a project that has an artgen.toml.
---

# artgen

`artgen` is a CLI. Run it from inside the work; it finds `artgen.toml` by walking up from the current directory and resolves every path against that file. Read the work's own art docs (style, characters, rules) before writing prompts: artgen itself knows nothing about the work.

## Before generating

1. `artgen gen --dry-run …` to see the expanded jobs (prompt, seed, size, workflow, GPU). Fix mistakes here; a dry run costs nothing.
2. Search cheaply: few images (`--n 1`–`2`), the default T4, `sdxl_txt2img`. Use `sdxl_hires_detailer` and higher resolution only for candidates the author liked.
3. If `artgen.toml` has `[comfy] backend = "local"`, `gen` uses the author's own ComfyUI: no Modal app, no GPU choice, no `max_apps`. If it cannot connect, ask the author to start ComfyUI.
4. Never pick a GPU outside `[modal] gpus`, and ask the author before anything larger than L4.

## Generating

Start generation in the background and wait for it, so a long run does not block the session:

```bash
artgen gen --preset <who>/<name> --n 2      # run this in the background
artgen wait --timeout 1800                  # blocks, then prints the output folders
```

- Many pictures: write a jobs file (`[{"preset": "...", "seed": 1}, {"prompt": "...", "tag": "..."}]`) and pass `--jobs`; one Modal session runs them all.
- Each output folder holds `<seed>_<i>.png` and the `workflow.json` that made them.
- Only `[modal] max_apps` apps may be up at once (default 1). If `gen` refuses to start, another run is still going: `artgen wait`. If a run was interrupted and an app is left up, `artgen stop`.

## Showing results

- Open results for the author with `artgen show <folder>` and get a yes or no, with what to change, before the next step.
- To check images yourself, look at downscaled copies, not full-size PNGs.
- When the author adopts a picture, add a `[[preset]]` to `<prompts>/<who>.toml` (name, adopted date, positive/negative without the shared style, size, workflow, seeds, note with the output folder name).

## Other commands

| Command | Use |
| --- | --- |
| `artgen underlay <shot.json>` | Depth and OpenPose underlays from a shot (local CPU, no cost). Format: `docs/shots.md` in the artgen repo |
| `artgen sheet <sheet.toml>` | Text, callouts and palette over sheet pictures (local). Format: `docs/sheets.md` |
| `artgen check` | Confirms a Modal GPU can be rented (a few seconds of T4) |
| `artgen auth` | Interactive Modal login; ask the author to run it as `! artgen auth` |

## When something fails

- `prompt is required`: give `--prompt`, `--preset` or `--jobs`.
- `gpu … is not in [modal] gpus`: use an allowed GPU or ask the author to change `artgen.toml`.
- `artgen app(s) already up`: `artgen wait`, or `artgen stop` if nothing of yours is running.
- Modal auth errors: the author runs `! artgen auth`.
