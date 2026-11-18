# TODO

Top to bottom. Mark done items with [x] and the date.

## ComfyUI and models

- [x] Upgrade ComfyUI to v0.44 or later (needed for P-H3-Image) and re-pin the custom nodes (2026-11-18: v0.45.6, torch 2.14.1 cu130, Impact-Pack 8.31, Subpack 1.3.4; T4 test run passed)
- [ ] Bump the Modal image builder version in the workspace settings so debian_slim (and Python 3.12) build again
- [ ] Styles: `styles/<name>.toml` (e.g. `anime-cel`, `lightnovel`) selectable from a preset or `[gen]`, so the painting style is not fixed per work
- [ ] Models and LoRAs declared by the work (`[[model]]`, `[[lora]]` with source, strength, trigger words) and placed on the volume on first use
- [ ] Compare generation models (Illustrious / NoobAI family, Krea 2, FLUX.2 klein) on the same character

## Workflows

- [ ] `img2img`: redraw a given image at a chosen denoise
- [ ] `underlay`: depth and OpenPose underlays through ControlNet
- [ ] `inpaint`: repaint a masked area
- [ ] `edit`: instruction-based edit with P-H3-Image (quantized: Pruna INT8 or GGUF via ComfyUI-GGUF); `artgen edit <image> "instruction"`. Try T4 first, L4 if it does not fit
- [ ] `rembg`: background removal (BiRefNet) to a transparent PNG
- [ ] `upscale`: model upscale for final candidates

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
