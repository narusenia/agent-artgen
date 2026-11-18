"""Character sheet TOML -> a PNG with the pictures, a title, callouts, a spec table and a palette laid over them.

Sheet format: docs/sheets.md.
"""

import tomllib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from artgen import fonts

FACES = {"sans": "NotoSansJP", "serif": "NotoSerifJP"}
INK = "#2b2b2b"
SUB = "#6b6b6b"


def font(face: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = fonts.path(f"{FACES[face]}-{'Bold' if bold else 'Regular'}.otf")
    return ImageFont.truetype(str(path), size)


def wrap(text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    # Japanese has no spaces between words, so wrap character by character
    lines = []
    for para in text.splitlines() or [""]:
        line = ""
        for ch in para:
            # keep punctuation and closing brackets off the start of a line
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

    # title: ruby, name, then the Latin subtitle, stacked from the top left
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

    # pictures: width only, aspect kept; remember the image -> canvas transform for callouts
    places = []
    for img in spec.get("image", []):
        src = Image.open(base / img["path"]).convert("RGB")
        s = img["width"] / src.width
        im.paste(src.resize((img["width"], round(src.height * s)), Image.LANCZOS), tuple(img["pos"]))
        places.append((img["pos"], s))

    # callouts: lines with a white edge so they read on navy and on black
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

    # spec table
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

    # palette
    if pl := spec.get("palette"):
        x, y = pl["pos"]
        y = heading(x, y, pl.get("heading", "配色"))
        sw = pl.get("swatch", 64)
        for code, label in pl["colors"]:
            d.rectangle([x, y, x + sw, y + sw], fill=code, outline="#9a9a9a", width=1)
            d.text((x + sw + 20, y + sw / 2), label, font=body, fill=INK, anchor="ls")
            d.text((x + sw + 20, y + sw / 2 + 8), code, font=font("sans", body.size * 2 // 3), fill=SUB, anchor="lt")
            y += sw + 18

    # memo
    if mo := spec.get("memo"):
        x, y = mo["pos"]
        y = heading(x, y, mo.get("heading", "メモ"))
        for line in wrap(mo["text"], body, mo.get("width", 600)):
            d.text((x, y), line, font=body, fill=INK)
            y += body.size + 14
    return im


def build(sheet: Path, out: Path) -> Path:
    spec = tomllib.loads(sheet.read_text(encoding="utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    render(spec, sheet.resolve().parent).save(out)
    return out
