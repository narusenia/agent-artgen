# 設定画の型紙（TOML）

絵は文字なしで生成し、名前・注記・配色は `artgen/sheet.py` が後から重ねる。見本は `packages/yohakuroku/art/sheets/uniform_female.toml`。

```bash
sh tools/artgen/fonts/fetch.sh   # 初回だけ。Noto Sans JP / Noto Serif JP（OFL）
uv run --project tools/artgen python tools/artgen/artgen/sheet.py <型紙.toml> [-o 出力.png]
# → 既定は <型紙のフォルダ>/../out/sheets/<型紙の名前>.png
```

座標はすべて左上が原点の画素。`pos`・`label` はキャンバス上、`at` だけ元の絵の画素。パスは型紙のある所から。

| 節 | キー | 中身 |
| --- | --- | --- |
| `[canvas]` | `size` `margin` `background` | 大きさ `[幅, 高さ]`（既定 `[2400, 1400]`）、余白（64）、背景色（`#ffffff`） |
| | `font` `text_size` `note_size` | 本文の書体 `sans`／`serif`、本文と注記の文字の大きさ（28・30） |
| `[title]` | `name` `ruby` `subtitle` | 見出し、ルビ（見出しの上に中央寄せ）、英字の副題。左上に積む |
| | `font` `size` | 見出しの書体（`serif`）と大きさ（64） |
| `[[image]]` | `path` `pos` `width` | 絵。幅だけ決め、縦横比は保つ。いくつでも置ける |
| `[[note]]` | `text` `at` `label` `image` | 注記。`at` は `[x, y]` か `[[x, y], …]`（指す所が複数なら線も複数）。`label` は文字の左上。`image` は何枚目の絵か（0 から、既定 0）。文字が指す所より左なら文字の右端から、それ以外は左端から線を引く |
| `[table]` | `pos` `width` `heading` `items` | 項目表。`items = [["年齢", "16"], …]` の順に並べ、値は `width` で折り返す |
| `[palette]` | `pos` `heading` `swatch` `colors` | 配色見本。`colors = [["#3a4566", "紺（上着）"], …]`、色見本の一辺（64） |
| `[memo]` | `pos` `width` `heading` `text` | 一言。`width` で折り返す |

- 節はどれも省ける。注記の `at` は、絵を縮小して見てから合わせる。
- 絵を差し替えたら、`at` を測り直す。
