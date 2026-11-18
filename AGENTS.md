# artgen — agent guide

artgen is a command-line image pipeline: ComfyUI on Modal for generation and editing, Blender on the local CPU for pose underlays, Pillow for character sheets. It serves several works; nothing in this repository may name or assume a particular work.

## Layout

- `src/artgen/cli.py` — commands; `project.py` — `artgen.toml`; `gen.py` — job expansion and the Modal session; `workflow.py` — fills workflow JSON; `comfy.py` — the ComfyUI HTTP client (Modal and local); `remote.py` — the Modal app (images, volume, ComfyUI class); `models.py` + `models.toml` — the model list a work can override with `[[model]]`; `runs.py` — app limit, `wait`, `stop`; `underlay.py`, `sheet.py`, `fonts.py`
- `src/artgen/workflows/` — ComfyUI workflows in API format; `src/artgen/poses/` — bundled pose shelf
- `examples/` — a sample of every file a work writes; keep it loading in the tests
- `docs/` — file formats (shots, poses, sheets)
- `TODO.md` — plans, top to bottom

## Rules

- **Language**: code, comments, commit messages, docs and `AGENTS.md` in English. The README exists in English (`README.md`) and Japanese (`README.ja.md`); change both together.
- **No work-specific content**: style rules, characters, age limits and composition rules belong to the work (its `artgen.toml`, prompts and docs), not here.
- **`remote.py` is imported inside the containers**: keep it free of local-only imports (bpy, PIL) and import it lazily from the CLI.
- **Cost**: start with the cheapest GPU (T4), then L4. Ask the author before using anything larger. Short timeouts, no idle containers left running, weights downloaded to the volume once, many images per call, low resolution and few images while searching. Never raise `max_apps` or start a second app to go faster.
- **Pinned versions**: ComfyUI, custom nodes and model revisions are pinned by tag or commit. Change a pin only with a test run.
- **Show images**: after generating, open the images for the author with `artgen show` and get a yes or no before going on. When checking images yourself, look at downscaled copies.
- **Background runs**: start `artgen gen` in the background and use `artgen wait` to get the output folders. If a run is interrupted, check `modal app list` and use `artgen stop` rather than leaving apps up.
- **Tests**: `mise run test`. New non-trivial logic gets a unit test that runs without Modal.
