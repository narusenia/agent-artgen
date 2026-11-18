# Character sheets (TOML)

Pictures are generated without text; `artgen sheet <sheet.toml>` lays the name, callouts and palette over them. Output defaults to `<out>/sheets/<name>.png`.

Fonts (Noto Sans JP / Noto Serif JP, SIL OFL 1.1) are downloaded once into `~/.cache/artgen/fonts/` and checked against bundled checksums.

All coordinates are pixels with the origin at the top left. `pos` and `label` are on the canvas; only `at` is in the source picture's pixels. Paths are relative to the sheet file.

| Section | Key | Meaning |
| --- | --- | --- |
| `[canvas]` | `size` `margin` `background` | Size `[w, h]` (default `[2400, 1400]`), margin (64), background (`#ffffff`) |
| | `font` `text_size` `note_size` | Body face `sans` / `serif`, body and callout text size (28 / 30) |
| `[title]` | `name` `ruby` `subtitle` | Title, ruby (centred above it), Latin subtitle, stacked at the top left |
| | `font` `size` | Title face (`serif`) and size (64) |
| `[[image]]` | `path` `pos` `width` | A picture. Only the width is set; the aspect is kept. Any number |
| `[[note]]` | `text` `at` `label` `image` | A callout. `at` is `[x, y]` or `[[x, y], …]` (one line per point). `label` is the text's top left. `image` is which picture (from 0, default 0). Lines start from the text's right edge when the text is left of the point, otherwise from its left edge |
| `[table]` | `pos` `width` `heading` `items` | Spec table. `items = [["Age", "16"], …]` in order; values wrap at `width` |
| `[palette]` | `pos` `heading` `swatch` `colors` | Palette. `colors = [["#3a4566", "navy (jacket)"], …]`, swatch side (64) |
| `[memo]` | `pos` `width` `heading` `text` | A short note, wrapped at `width` |

- Every section is optional. Fit `at` while looking at a downscaled picture.
- When a picture is replaced, measure `at` again.
