# TODO

Top to bottom. Mark done items with [x] and the date.

## ComfyUI and models

- [x] Upgrade ComfyUI to v0.44 or later (needed for P-H3-Image) and re-pin the custom nodes (2026-11-18: v0.45.6, torch 2.14.1 cu130, Impact-Pack 8.31, Subpack 1.3.4; T4 test run passed)
- [ ] Bump the Modal image builder version in the workspace settings so debian_slim (and Python 3.12) build again
- [x] Styles: `styles/<name>.toml` (e.g. `anime-cel`, `lightnovel`) selectable from a preset or `[gen]`, so the painting style is not fixed per work
- [x] Models declared by the work (`[[model]]`, bundled list in `models.toml`) and placed on the volume on first use (2026-11-18)
- [x] LoRAs declared by the work, as `[[model]]` with `folder = "loras"` and `trigger`, used by job key `loras` (2026-11-18; not yet run with a real LoRA)
- [ ] Compare generation models (Illustrious / NoobAI family, Krea 2, FLUX.2 klein) on the same character

## Workflows

- [x] `img2img`: redraw a given image at a chosen denoise (2026-11-18, job keys `image`, `denoise`)
- [x] `underlay`: depth and OpenPose underlays through ControlNet (2026-11-18, job key `control`)
- [x] `inpaint`: repaint a masked area (2026-11-18, job key `mask`)
- [x] `edit`: instruction-based edit with P-H3-Image, `artgen edit <image> "instruction"` (2026-11-18: w4a8 set, no prompt upsampler; T4 at 1 MP in 211 s)
- [x] `edit` at 4 MP (2026-11-18: L4, 68 s of sampling; the run took 1157 s, mostly start-up)
- [ ] `edit`: the prompt upsampler (another 10–19 GB)
- [x] Find the `KeyError: 'default'` printed at ComfyUI start (2026-11-18: Impact-Pack's missing ini; an empty one is baked into the image)
- [x] `rembg`: background removal (BiRefNet) to a transparent PNG (2026-11-18)
- [x] `upscale`: model upscale for final candidates (2026-11-18, RealESRGAN x4plus anime 6B)

## Underlays (Blender)

- [ ] Run Blender as a Modal CPU function (`render()` as is)
- [ ] Replace the doll with MPFB2 (joint names and shots stay the same)
- [ ] Count props (swords etc.) in the framing; try scenes with several figures
- [ ] Narrow the depth range if ControlNet reads it as too flat
- [ ] Pose shelf: import Mixamo / CMU motion capture poses; record each source's terms in `docs/poses.md`

## Consistency and parts

- [ ] Train character LoRAs on Modal from adopted sheets
- [ ] Regional prompts for scenes with several characters
- [ ] `parts`: figure (transparent), line art, effects, background and underlay as separate layers plus a PSD

## Fallback

- [ ] Run the same workflows on RunPod and switch when the Modal limit is near
