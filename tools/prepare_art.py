"""Build the native MIP artwork and fonts for the 260 px display. Requires Pillow."""
from collections import Counter
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ART, OUT, FONTS = ROOT / "art", ROOT / "resources/drawables", ROOT / "resources/fonts"
XML = ET.Element("drawables")
SKY = json.loads((ART / "geometry.json").read_text())
SIZE = 260
STATIC = {"Top": (0, 0, 260, 42), "Wall": (104, 42, 188, 155), "Floor": (0, 155, 260, 260)}
MOVING = {"Left": (0, 42, 104, 155), "Right": (188, 42, 260, 155)}
OCCLUSION = (61, 94, 83, 153)
LANCZOS = Image.Resampling.LANCZOS


def distance(a, b):
    return sum(w * (x-y)**2 for x, y, w in zip(a, b, (3, 4, 2)))


def reduce_colors(pictures, limit):
    """Choose real MIP colors, and use the same mapping for every pose in a tile."""
    counts = Counter()
    for pic in pictures:
        counts.update({c: n for n, c in pic.convert("RGB").getcolors(1 << 20)})
    active = dict(counts)
    while len(active) > limit:
        # Remove the least costly color and give its weight to its closest match.
        _, removed, keep = min((active[a] * distance(a, b), a, b)
                               for a in active for b in active if a != b)
        active[keep] += active.pop(removed)
    cols = sorted(active)
    nearest = {color: min(cols, key=lambda c: distance(c, color)) for color in counts}
    return [remap(im, nearest) for im in pictures]


def remap(im, mapping):
    rgb = im.convert("RGB")
    value = Image.new("RGB", im.size)
    value.putdata([mapping[p] for p in rgb.get_flattened_data()])
    return value


def write_bitmap(name, im, *, compress=True):
    im = im.convert("RGBA")
    colors = sorted({(r, g, b) for r, g, b, a in im.get_flattened_data() if a})
    opaque = im.getchannel("A").getextrema()[0] == 255
    assert len(colors) + (not opaque) <= 16, (name, len(colors))
    filename = name + ".png"
    im.save(OUT / filename, optimize=True)
    bitmap = ET.SubElement(XML, "bitmap", id=name, filename=filename, dithering="none",
                           compress=str(compress).lower())
    pal = ET.SubElement(bitmap, "palette", disableTransparency=str(opaque).lower())
    for c in colors:
        ET.SubElement(pal, "color").text = "".join(f"{ch:02X}" for ch in c)
    return im


def quant_ink(image):
    """A transparent background and three opaque shades for antialiased black lettering."""
    flat = Image.new("RGB", image.size, "white")
    flat.paste(image, mask=image.getchannel("A"))
    result = Image.new("RGBA", image.size)
    def ink(p):
        value = 85*round(sum(p)/3/85)
        return (value, value, value, 255 if value != 255 else 0)
    result.putdata([ink(p) for p in flat.get_flattened_data()])
    return result


def build_scene():
    atlas = Image.open(ART / "scene-compact.png").convert("RGB")
    masks = Image.open(ART / "window-atlas.png").convert("RGBA").getchannel("A")
    disk = Image.new("L", (SIZE, SIZE))
    ImageDraw.Draw(disk).ellipse((2, 2, 257, 257), fill=255)
    for mode, offset in [("Day", 0), ("Night", SIZE)]:
        poses = [Image.composite(atlas.crop((p*SIZE, offset, (p+1)*SIZE, offset+SIZE)),
                                 Image.new("RGB", disk.size), disk) for p in range(4)]
        for label, rect in STATIC.items():
            tile = poses[0].crop(rect)
            assert all(im.crop(rect).tobytes() == tile.tobytes() for im in poses)
            write_bitmap(mode+label, reduce_colors([tile], 16)[0])
        for side, rect in MOVING.items():
            tiles = reduce_colors([im.crop(rect) for im in poses], 16)
            for i, tile in enumerate(tiles):
                write_bitmap(f"{mode}{side}{i}", tile)
                if side == "Left":
                    x, y, x2, y2 = OCCLUSION
                    front = tile.crop((x, y-rect[1], x2, y2-rect[1])).convert("RGBA")
                    mask = masks.crop((x+i*SIZE, y, x2+i*SIZE, y2))
                    front.putalpha(mask.point(lambda v: 255-v))
                    write_bitmap(f"{mode}Fore{i}", front)
    head = atlas.crop((84, 112, 162, 190)).resize((40, 40), LANCZOS)
    # Keep launcher colors on the device palette as well.
    head = head.point(lambda v: 85*round(v/85))
    write_bitmap("LauncherIcon", reduce_colors([head], 16)[0])


def build_marks():
    for name, file in [("ThisIsFine", "fine"), ("SendCoffee", "coffee")]:
        im = Image.open(ART / (file+".png")).convert("RGBA")
        write_bitmap(name, quant_ink(im.resize(tuple(round(n*.86) for n in im.size), LANCZOS)))
    icons = Image.open(ART / "status-icons.png").convert("RGBA")
    for idx, name in enumerate(["Alarm", "Receiver", "ReceiverOff"]):
        tile = icons.crop((idx*72, 0, (idx+1)*72, 72)).resize((14, 14), LANCZOS)
        # The fēnix 6 cannot load these 14 px status icons with RLE compression.
        write_bitmap(name, quant_ink(tile), compress=False)
    r = SKY["sunRadius"]
    pad = math.ceil(r)
    im = Image.new("RGBA", (2*pad, 2*pad))
    pixels = []
    for y in range(im.height):
        for x in range(im.width):
            d = math.hypot(x+.5-pad, y+.5-pad)
            pixels.append((255, 255, 85, 255) if d <= r-1.2 else
                          (85, 85, 0, 255) if d <= r else (0, 0, 0, 0))
    im.putdata(pixels)
    write_bitmap("Sun", im)
    # Pixel spans for an orthographic moon on the original, fixed 18 px disk.
    moon_r = SKY["radius"]
    halfwidths = [math.floor(math.sqrt(moon_r**2-(y+.5-moon_r)**2)+.5)
                  for y in range(2*moon_r)]
    (ROOT / "source/Sky.mc").write_text(
        "// Generated by tools/prepare_art.py from art/geometry.json.\nmodule Sky {\n" +
        "".join(f"    const {key} = {val};\n" for key, val in
                [("X", SKY["x"]), ("Y", SKY["y"]), ("HALF_Y", SKY["halfY"]),
                 ("LAST_Y", SKY["lastY"]), ("CUTOFF", SKY["cutoff"]), ("SUN_PAD", pad),
                 ("MOON_R", moon_r), ("HALF_WIDTHS", halfwidths)]) + "}\n", encoding="utf8")


# Strokes for the six remaining clock digits.
# Coordinates are in a 20 by 28 px pen grid. Each tuple is one cubic Bezier.
STROKES = {
    "2": [[(3,7),(6,0,17,1,17,8),(17,13,6,19,3,25),(6,25,13,25,17,25)]],
    "4": [[(13,3),(10,7,6,12,2,18),(7,18,12,18,18,18)],[(14,3),(14,9,14,20,14,25)]],
    "5": [[(16,3),(12,3,7,3,5,3),(5,7,5,10,4,13),(9,10,17,11,17,18),(18,26,8,28,3,23)]],
    "6": [[(15,3),(8,1,2,12,3,19),(4,27,16,28,17,20),(19,11,9,9,4,16)]],
    "7": [[(3,3),(7,3,14,3,17,3),(15,9,9,18,7,25)]],
    "9": [[(16,12),(13,19,3,17,3,10),(3,2,12,0,16,6),(20,12,15,22,9,25)]],
}


def pen(paths):
    scale = 8
    im = Image.new("L", (20*scale, 28*scale))
    draw = ImageDraw.Draw(im)
    for seq in paths:
        x, y = seq[0]
        points = [(x*scale, y*scale)]
        for x1, y1, x2, y2, x3, y3 in seq[1:]:
            for k in range(1, 25):
                t = k/24; u = 1-t
                points.append((scale*(u**3*x+3*u*u*t*x1+3*u*t*t*x2+t**3*x3),
                               scale*(u**3*y+3*u*u*t*y1+3*u*t*t*y2+t**3*y3)))
            x, y = x3, y3
        width = 4.5*scale
        draw.line(points, fill=255, width=round(width), joint="curve")
        for x, y in (points[0], points[-1]):
            draw.ellipse((x-width/2, y-width/2, x+width/2, y+width/2), fill=255)
    return im


def clock_glyphs():
    day = Image.open(ART / "day-clock.png").getchannel("A")
    night = Image.open(ART / "night-clock.png").getchannel("A")
    glyphs = {c: pen(paths) for c, paths in STROKES.items()}
    for c, sample, x, x2 in [("8",day,0,38), (":",day,41,57), ("0",day,59,95),
                              ("1",night,0,28), ("3",night,115,148)]:
        glyphs[c] = sample.crop((x, 0, x2, sample.height))
    return {c: im.crop(im.point(lambda v: 255 if v >= 40 else 0).getbbox()) for c, im in glyphs.items()}


TINY = {
    "0": ("0110","1001","1001","1001","1001","1001","0110"),
    "1": ("0010","0110","0010","0010","0010","0010","0111"),
    "2": ("0110","1001","0001","0010","0100","1000","1111"),
    "3": ("1110","0001","0001","0110","0001","0001","1110"),
    "4": ("0010","0110","1010","1010","1111","0010","0010"),
    "5": ("1111","1000","1000","1110","0001","0001","1110"),
    "6": ("0110","1000","1000","1110","1001","1001","0110"),
    "7": ("1111","0001","0010","0010","0100","0100","0100"),
    "8": ("0110","1001","1001","0110","1001","1001","0110"),
    "9": ("0110","1001","1001","0111","0001","0001","0110"),
    "-": ("000","000","000","111","000","000","000"),
    "°": ("010","101","010","000","000","000","000"),
}


def bmfont(name, height, entries):
    page = Image.new("RGBA", (256, 32), (255,255,255,0))
    lines = []; cursor = 0
    for ch, mask, offset, advance in sorted(entries):
        w, h = mask.size
        glyph = Image.new("RGBA", mask.size, (255,255,255,255)); glyph.putalpha(mask)
        page.paste(glyph, (cursor, 0))
        lines.append(f"char id={ord(ch)} x={cursor} y=0 width={w} height={h} xoffset=0 yoffset={offset} xadvance={advance} page=0 chnl=15")
        cursor += w+1
    assert cursor <= page.width
    page.save(FONTS / (name+".png"), optimize=True)
    header = [f'info face="{name}" size={height} bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 padding=0,0,0,0 spacing=1,1',
              f'common lineHeight={height} base={height} scaleW=256 scaleH=32 pages=1 packed=0',
              f'page id=0 file="{name}.png"', f'chars count={len(lines)}']
    (FONTS / (name+".fnt")).write_text("\n".join(header+lines)+"\n", encoding="utf8")


def build_fonts():
    glyphs = clock_glyphs()
    for name, height, normal_w, gap in [("ClockWide", 28, 20, 5), ("ClockCompact", 26, 18, 3)]:
        entries = []
        for c, im in glyphs.items():
            w = 5 if c == ":" else normal_w-3 if c == "1" else normal_w
            if c == "0" and name == "ClockCompact":
                w += 1
            h = round(height*.60) if c == ":" else height
            entries.append((c, im.resize((w,h), LANCZOS), (height-h)//2, w+gap))
        bmfont(name, height, entries)
    entries = []
    for c, rows in TINY.items():
        mask = Image.new("L",(len(rows[0]),len(rows)))
        mask.putdata([255 if v=="1" else 0 for row in rows for v in row])
        entries.append((c, mask, 0, mask.width+1))
    bmfont("WeatherSmall", 7, entries)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True); FONTS.mkdir(parents=True, exist_ok=True)
    build_scene(); build_marks(); build_fonts()
    ET.indent(XML)
    ET.ElementTree(XML).write(OUT / "drawables.xml", encoding="utf-8", xml_declaration=True)
