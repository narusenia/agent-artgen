# Shots (underlay input)

One JSON file per picture, read by `artgen underlay <shot.json>`. Outputs go to `<out>/underlay/` unless `-o` is given.

```json
{
  "id": "hero_stance",
  "note": "The hero stands with a sword raised. Strong low angle and tilt, full body",
  "size": [832, 1216],
  "camera": { "mood": "dynamic", "shot": "full", "lens": 28, "pitch": 22, "yaw": 25, "roll": 10 },
  "figures": [
    { "name": "hero", "pose": "sword_guard", "position": [0, 0], "facing": -20, "height": 1.55, "hold": "sword" }
  ]
}
```

| Key | Meaning |
| --- | --- |
| `id` / `note` | Prefix of the output files (`<id>_depth.png`, `<id>_openpose.png`) / one line about the scene |
| `size` | Width and height in px. Portrait 832x1216, landscape 1216x832 |
| `camera.mood` | A set of defaults: `dynamic` (default) or `calm`. Values written below win |
| `camera.shot` | Framing: `full`, `knee`, `waist`, `bust`, `face` |
| `camera.lens` | Focal length (mm, 35mm format). 24–35 is wide and exaggerates depth, 50 is neutral, 85 flattens |
| `camera.pitch` | Vertical angle in degrees. Positive looks up from below, negative looks down |
| `camera.yaw` | Direction around the main figure in degrees. 0 is the figure's front; positive moves to the figure's left |
| `camera.roll` | Tilt in degrees (Dutch angle). Positive tips the horizon down to the right |
| `camera.place` | Where the centre of the main figure's bounds (with props) lands, `[x, y]`, 0 at top left and 1 at bottom right. 0.33 / 0.67 for thirds. Never pushed past the frame |
| `camera.fill` | Share of the frame the main figure fills (the larger of width and height). The rest is margin |
| `camera.fit_props` | Whether props are fitted into the frame too. `false` fits the body only and lets props run off |
| `figures[].pose` / `adjust` | A pose from the shelves (see `poses.md`) and optional per-joint rotation overrides |
| `figures[].position` / `facing` | Floor position `[x, y]` in metres (main figure at `[0, 0]`) / direction in degrees (0 faces the camera's yaw 0 side; positive turns left) |
| `figures[].height` / `hold` | Height in metres (default 1.55, 6.5 heads) / prop (optional; `sword`, held in the right hand, about 1 m long) |

Camera distance and position are not written: they follow from direction, lens and framing so that the main figure fills `fill` of the frame.

## Mood defaults

| | lens | pitch | yaw | roll | fill | place | Suits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `dynamic` (default) | 28 | 20 | 25 | 8 | 0.88 | [0.5, 0.5] | action, key art |
| `calm` | 50 | 0 | 0 | 0 | 0.88 | [0.5, 0.5] | conversation, quiet scenes, reference sheets |

Ways to add movement:

- A strong low angle (pitch 20–30) or high angle (pitch -25 to -40), combined with a wide lens (24–28) so the near side grows and the far side shrinks.
- A tilt (roll 5–12, negative for the other way) to put the body or a sword on the frame's diagonal.
- Off-centre placement (`place` x of 0.33 / 0.67), leaving room on the side the gaze or blade points to.
- A big foreground object: put the camera near the prop's line (e.g. looking down from the sword tip) with a wide lens.

Light, gaze and space for text are added at the generation stage, not in the underlay.
