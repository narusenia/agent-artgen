"""設定画の型紙（TOML）から、絵に文字・注記・配色見本を重ねた PNG を作る。

    uv run --project tools/artgen python tools/artgen/artgen/sheet.py <型紙.toml> [-o 出力.png]

型紙の書式は tools/artgen/sheets.schema.md。出力の既定は <型紙のある所>/../out/sheets/<型紙の名前>.png。
"""

import argparse
import sys
import tomllib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parent.parent / "fonts"
FACES = {"sans": "NotoSansJP", "serif": "NotoSerifJP"}
INK = "#2b2b2b"
SUB = "#6b6b6b"


def font(face: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONTS / f"{FACES[face]}-{'Bold' if bold else 'Regular'}.otf"
    if not path.exists():
        sys.exit(f"フォントがない: {path}\n先に sh tools/artgen/fonts/fetch.sh を実行する")
    return ImageFont.truetype(str(path), size)


def wrap(text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    # 日本語は語の切れ目に空白がないので、一字ずつ詰めて折る
    lines = []
    for para in text.splitlines() or [""]:
        line = ""
        for ch in para:
            # 句読点・閉じ括弧は行頭に送らず、前の行にぶら下げる
            if line and f.getlength(line + ch) > width and ch not in "、。，．）」』":
                lines.append(line)
                line = ""
            line += ch
        lines.append(line)
    return lines


def render(spec: dict, base: Path) -> Image.Image:
    cv = spec.get("canvas", {})
    W, H = cv.get("size", [2400, 1400])
    m = cv.get("margin", 64)
    face = cv.get("font", "sans")
    im = Image.new("RGB", (W, H), cv.get("background", "#ffffff"))
    d = ImageDraw.Draw(im)

    # 見出し: ルビ → 名前 → 英字の副題、の順に左上から積む
    t = spec.get("title", {})
    y = m
    name_f = font(t.get("font", "serif"), t.get("size", 64), bold=True)
    if t.get("ruby"):
        ruby_f = font(t.get("font", "serif"), t.get("size", 64) // 3)
        rw = ruby_f.getlength(t["ruby"])
        nw = name_f.getlength(t.get("name", ""))
        d.text((m + max(0, (nw - rw) / 2), y), t["ruby"], font=ruby_f, fill=SUB)
        y += ruby_f.size + 8
    if t.get("name"):
        d.text((m, y), t["name"], font=name_f, fill=INK)
        y = d.textbbox((m, y), t["name"], font=name_f)[3] + 12
    if t.get("subtitle"):
        sub_f = font("serif", t.get("size", 64) * 2 // 5)
        d.text((m, y), t["subtitle"], font=sub_f, fill=SUB)
        y = d.textbbox((m, y), t["subtitle"], font=sub_f)[3]
    d.line([(m, y + 20), (W - m, y + 20)], fill="#cfcac0", width=2)

    # 絵: 幅だけ指定して縦横比は保つ。注記のため、元画像→キャンバスの変換を覚えておく
    places = []
    for img in spec.get("image", []):
        src = Image.open(base / img["path"]).convert("RGB")
        s = img["width"] / src.width
        im.paste(src.resize((img["width"], round(src.height * s)), Image.LANCZOS), tuple(img["pos"]))
        places.append((img["pos"], s))

    # 注記: 白い縁取りの線で、紺の上でも黒い背景でも見える
    nf = font(face, cv.get("note_size", 30), bold=True)
    for n in spec.get("note", []):
        (ox, oy), s = places[n.get("image", 0)]
        pts = n["at"] if isinstance(n["at"][0], list) else [n["at"]]
        pts = [(ox + px * s, oy + py * s) for px, py in pts]
        lx, ly = n["label"]
        box = d.textbbox((lx, ly), n["text"], font=nf)
        left_of = all(px > box[2] for px, _ in pts)
        start = (box[2] + 10, (box[1] + box[3]) / 2) if left_of else (box[0] - 10, (box[1] + box[3]) / 2)
        for p in pts:
            d.line([start, p], fill="white", width=6)
        for p in pts:
            d.line([start, p], fill=INK, width=2)
            d.ellipse([p[0] - 7, p[1] - 7, p[0] + 7, p[1] + 7], fill=INK, outline="white", width=3)
        d.text((lx, ly), n["text"], font=nf, fill=INK)

    body = font(face, cv.get("text_size", 28))
    head = font(face, cv.get("text_size", 28), bold=True)

    def heading(x, y, text):
        d.text((x, y), text, font=head, fill=SUB)
        return y + head.size + 16

    # 項目表
    if tb := spec.get("table"):
        x, y = tb["pos"]
        y = heading(x, y, tb.get("heading", "項目")) if tb.get("heading", "項目") else y
        kw = max(head.getlength(k) for k, _ in tb["items"]) + 32
        for k, v in tb["items"]:
            d.text((x, y), k, font=head, fill=INK)
            for line in wrap(v, body, tb.get("width", 600) - kw):
                d.text((x + kw, y), line, font=body, fill=INK)
                y += body.size + 12
            y += 6

    # 配色見本
    if pl := spec.get("palette"):
        x, y = pl["pos"]
        y = heading(x, y, pl.get("heading", "配色"))
        sw = pl.get("swatch", 64)
        for code, label in pl["colors"]:
            d.rectangle([x, y, x + sw, y + sw], fill=code, outline="#9a9a9a", width=1)
            d.text((x + sw + 20, y + sw / 2), label, font=body, fill=INK, anchor="ls")
            d.text((x + sw + 20, y + sw / 2 + 8), code, font=font("sans", body.size * 2 // 3), fill=SUB, anchor="lt")
            y += sw + 18

    # 一言
    if mo := spec.get("memo"):
        x, y = mo["pos"]
        y = heading(x, y, mo.get("heading", "メモ"))
        for line in wrap(mo["text"], body, mo.get("width", 600)):
            d.text((x, y), line, font=body, fill=INK)
            y += body.size + 14
    return im


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sheet", type=Path, help="型紙の TOML")
    ap.add_argument("-o", "--out", type=Path, help="出力の PNG")
    a = ap.parse_args()
    spec = tomllib.loads(a.sheet.read_text(encoding="utf-8"))
    out = a.out or a.sheet.resolve().parent.parent / "out" / "sheets" / f"{a.sheet.stem}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    render(spec, a.sheet.resolve().parent).save(out)
    print(out)


if __name__ == "__main__":
    main()
