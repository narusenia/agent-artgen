# artgen

[日本語](README.ja.md)

A command-line image pipeline for character sheets and composition references. It drives ComfyUI on a [Modal](https://modal.com) GPU and renders pose underlays with Blender on the local CPU. It is not tied to any one work: each work describes itself in an `artgen.toml`.

## Install

Python 3.13 is required (bpy 5.2 LTS ships for 3.13 only).

With mise, add this to the work's `mise.toml` and run `mise install`:

```toml
[tools]
"pipx:git+ssh://git@github.com/narusenia/modal-artgen.git" = { version = "latest", uvx_args = "--python 3.13" }
```

Or with uv directly:

```bash
uv tool install --python 3.13 git+ssh://git@github.com/narusenia/modal-artgen.git
```

Then, once per machine:

```bash
artgen auth    # log in to Modal (interactive)
artgen check   # rent a T4 for a few seconds to confirm access
```

## Commands

| Command | What it does |
| --- | --- |
| `artgen gen` | Generate with ComfyUI on Modal, or on a local ComfyUI with `--backend local`. `--preset <who>/<name>`, `--prompt`, or `--jobs <file.json>` for many jobs in one session. `--dry-run` prints the expanded jobs |
| `artgen edit <image> "<instruction>"` | Edit a picture by an instruction with P-H3-Image (`ph3_edit`). `--images` adds pictures the instruction calls `<Picture 2>`, … Downloads about 20 GB of weights once. On a T4, `--megapixels 1` takes about 3.5 minutes |
| `artgen wait` | Block until `gen` runs started in the background finish, then print their output folders. For agents |
| `artgen stop` | Stop every artgen app still up on the Modal account |
| `artgen underlay <shot.json>` | Render depth and OpenPose underlays from a shot (local CPU) |
| `artgen sheet <sheet.toml>` | Lay a title, callouts, a spec table and a palette over sheet pictures |
| `artgen show <path>...` | Open images or folders in the system viewer |
| `artgen auth` / `artgen check` | Modal login / GPU check |
| `artgen skill [--install DIR]` | Print the agent skill, or write it to `DIR/artgen/SKILL.md` (e.g. `.claude/skills`) |

`artgen <command> --help` lists every option.

## Project config

artgen looks for `artgen.toml` in the current directory and its parents. Paths are relative to that file. Every key is optional.

```toml
out = "art/out"            # generated images
prompts = "art/prompts"    # adopted presets: _style.toml and <who>.toml
poses = "art/poses"        # extra pose shelf, searched before the bundled one

[comfy]
backend = "modal"          # "modal" or "local" (a ComfyUI you already run)
url = "http://127.0.0.1:8188"  # the local ComfyUI

[modal]
gpu = "T4"                 # default GPU
gpus = ["T4", "L4"]        # GPUs allowed with --gpu or a preset's gpu
max_apps = 1               # artgen apps allowed up at once on the Modal account
timeout = 900              # seconds per ComfyUI container
scaledown = 30             # seconds an idle container stays up

[gen]                      # defaults for `artgen gen`; the command line wins
workflow = "sdxl_txt2img"  # or sdxl_hires_detailer
width = 832
height = 1216
n = 2
negative = ""
```

`max_apps` counts apps started from any machine or work. When the limit is reached, `gen` and `check` refuse to start; use `artgen wait` or `artgen stop`.

### Local ComfyUI

With `backend = "local"` (or `--backend local`), `gen` sends the workflows to the ComfyUI at `url` and uses no Modal app. That ComfyUI needs the custom nodes of the Modal image (`src/artgen/remote.py`) and, in its model folders, the files the run uses under the names in the model list below.

### Models

The bundled model list is [src/artgen/models.toml](src/artgen/models.toml). Workflows refer to a model by key (`$checkpoint`), so a work changes a model, or adds one, with a `[[model]]` of that key in its `artgen.toml`:

```toml
[[model]]
key = "checkpoint"                       # replaces the bundled checkpoint
folder = "checkpoints"                   # ComfyUI model folder type
repo = "OnomaAIResearch/Illustrious-XL-v2.0"
file = "Illustrious-XL-v2.0.safetensors"
# rev = "<commit>"                       # pin; or url = "https://…" with sha256 = "…"
```

On Modal, each run downloads only the models its workflows use, once, to `/models/<folder>/<file>` on the `artgen-models` volume.

## Job keys

A job (from `--jobs`, a preset or the command line) takes these keys besides the prompt, size and seed:

| Key | What it does |
| --- | --- |
| `ref`, `ref_*` | IP-Adapter reference image |
| `image`, `denoise` | img2img: redraw `image` at `denoise` (default 0.55) |
| `mask` | Inpaint inside `image`; white is repainted (`denoise` default 0.9) |
| `control` | Underlays: `[{image, type = "depth" \| "openpose", strength, start_at, end_at}]` |
| `upscale` | Enlarge the result by this factor with the upscaler model |
| `rembg` | Remove the background (transparent PNG) |
| `images`, `megapixels` | `ph3_edit` only: extra pictures, and the size of the edit (default 4) |

The `post` workflow only loads `image` and applies `upscale` and `rembg`: `artgen gen --workflow post --image a.png --upscale 2 --rembg`.

## Examples

[examples/](examples/) has a sample of every file: `artgen.toml`, `prompts/_style.toml`, `prompts/<who>.toml`, a jobs file, a shot and a sheet.

## Presets

An adopted prompt is saved so it can be generated again. `<prompts>/_style.toml` holds what every character shares, and `<prompts>/<who>.toml` holds one `[[preset]]` per adopted picture:

```toml
[[preset]]
name = "stance"
uses = ["uniform.female"]      # extra tables from _style.toml, joined after `style`
positive = "1girl, standing"   # only the character's part
negative = "..."
seeds = [1234]
width = 832
height = 1216
workflow = "sdxl_hires_detailer"
ref = "art/refs/uniform.png"   # optional IP-Adapter reference
note = "what was adopted and why"
```

`artgen gen --preset <who>/stance` runs one job per seed. A non-zero `--seed` replaces the seeds.

## Formats

- Shots (underlays): [docs/shots.md](docs/shots.md)
- Poses: [docs/poses.md](docs/poses.md)
- Character sheets: [docs/sheets.md](docs/sheets.md)

## Cost

Modal bills per second. The defaults stay cheap: T4, short timeouts, idle containers stopped after 30 seconds, weights kept on the `artgen-models` volume and downloaded once. Set a monthly limit in the Modal workspace settings.

## Development

```bash
mise run setup   # uv sync
mise run test    # unit tests
uv run artgen …  # run from the checkout
```

Plans are in [TODO.md](TODO.md). Rules for agents working on this repository are in [AGENTS.md](AGENTS.md).
