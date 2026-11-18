# Poses

One pose per JSON file. `joints` holds each joint's rotation (degrees, Euler XYZ, relative to the parent joint). Joints left out are 0.

```json
{ "name": "standing", "joints": { "shoulder_r": [0, 6, 0], "elbow_r": [-8, 0, 0] } }
```

The bundled shelf is `src/artgen/poses/`. A work can add its own shelf with `poses = "..."` in `artgen.toml`; it is searched first, so a pose of the same name replaces the bundled one.

- Joints: `pelvis` (whole body), `spine`, `chest`, `neck`, `head`, `shoulder_*`, `elbow_*`, `wrist_*`, `hip_*`, `knee_*`, `ankle_*` (`_r` is the doll's right, `_l` its left).
- The rest pose stands upright with arms down. The doll faces -Y and +X is its left.
- Directions: positive x tilts downward parts (arms, legs) back and upward parts (spine, neck, head) forward. Positive y opens downward parts to the doll's right (outward for the right arm, inward for the left). Positive z turns left seen from above.
- The sword (`hold: sword`) is attached to the right wrist; with the arm down the blade points forward. `wrist_r` x raises or lowers the blade, z turns it sideways.
- Feet are put on the floor automatically (the lower foot touches it).

| File | Pose |
| --- | --- |
| `stand.json` | Standing |
| `sword_guard.json` | Sword at middle guard, right foot forward, both hands |
| `look_back.json` | Looking back over the left shoulder (use with `facing: 180`) |

## External sources (surveyed, not imported yet)

| Source | Terms | How to import |
| --- | --- | --- |
| CMU Graphics Lab Motion Capture Database | Free. May be used in commercial works; the data itself may not be redistributed or sold | Use the BVH conversion (cgspeed). Load with bpy's BVH importer, pick a frame, map each bone's rotation to the joint names here and write JSON |
| Mixamo (Adobe) | Free with an Adobe account. Use in works is allowed; redistributing raw animation data is not. No API; download by hand | Download FBX by hand and map one frame as above |
| Bandai Namco Research Motion Dataset | CC BY-NC-ND 4.0 (non-commercial, no derivatives). Only for private reference; not for underlays of published pictures | BVH, as above |

- When mapping, cancel the difference between the source's rest pose (usually a T-pose) and this doll's (arms down) with shoulder rotations, and match the axes (Y up or Z up).
- Never commit raw source data (that would be redistribution). Only the mapped JSON goes on a shelf.
