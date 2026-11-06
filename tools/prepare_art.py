"""Build the native MIP artwork and fonts for the 260 px display. Requires Pillow."""
from collections import Counter
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET
from PIL import Image, ImageChops, ImageDraw

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


# Pen strokes in a 20 by 28 px grid. Each tuple is one cubic Bezier.
STROKES = {
    "1": [[(6,8),(8,6,10,4,12,3),(12,9,11.5,21,12,25)]],
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
    for c, sample, x, x2 in [("8",day,0,38), ("0",day,59,95), ("3",night,115,148)]:
        glyphs[c] = sample.crop((x, 0, x2, sample.height))
    return {c: im.crop(im.point(lambda v: 255 if v >= 40 else 0).getbbox()) for c, im in glyphs.items()}


def clock_mask(digit, master, width, height):
    # Lighten the stroke at its final screen size. Overscan keeps the outer
    # dimensions steady while opening up the counters of 0, 6, 8 and 9.
    scale = 6
    ink_width = round(height * .41) if digit == "1" else width
    w, h = ink_width * scale, height * scale
    pad = 2 * scale
    spread = 5  # five sixths of one display pixel on each side
    canvas = Image.new("L", (w + 2*pad, h + 2*pad))
    enlarged = master.resize((w + 2*spread, h + 2*spread), LANCZOS)
    canvas.paste(enlarged, (pad-spread, pad-spread))
    # Use a round nib so diagonals stay as legible as vertical stems.
    thinned = canvas
    for dx, dy in [(5,0),(-5,0),(0,5),(0,-5),(4,4),(4,-4),(-4,4),(-4,-4)]:
        thinned = ImageChops.darker(thinned, ImageChops.offset(canvas, dx, dy))
    ink = thinned.crop((pad,pad,pad+w,pad+h)).resize((ink_width,height), LANCZOS)
    cell = Image.new("L",(width,height))
    cell.paste(ink,((width-ink_width)//2,0))
    return cell


def clock_colon(height):
    scale = 8
    mask = Image.new("L",(5*scale,height*scale))
    pen = ImageDraw.Draw(mask)
    for center in (height*.29, height*.71):
        pen.ellipse(((2.5-1.8)*scale,(center-1.8)*scale,
                     (2.5+1.8)*scale,(center+1.8)*scale),fill=255)
    return mask.resize((5,height), LANCZOS)


def bmfont(name, height, entries):
    # Garmin reads glyph coverage from grayscale intensity, not PNG alpha.
    # White RGBA glyphs with alpha-only edges become ragged solid ink on MIP.
    page = Image.new("L", (256, 32), 0)
    lines = []; cursor = 0
    for ch, mask, offset, advance in sorted(entries):
        w, h = mask.size
        page.paste(mask, (cursor, 0))
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
            w = normal_w-3 if c == "1" else normal_w
            if c == "0" and name == "ClockCompact":
                w += 1
            entries.append((c, clock_mask(c, im, w, height), 0, w+gap))
        entries.append((":", clock_colon(height), 0, 5+gap))
        bmfont(name, height, entries)
    entries = []
    for c, master in glyphs.items():
        width = 5 if c == "1" else 7
        entries.append((c, master.resize((width,11),LANCZOS), 0, width+1))
    minus = Image.new("L",(4,1),255)
    degree = Image.new("L",(32,32))
    ImageDraw.Draw(degree).ellipse((1,1,30,30), outline=255, width=8)
    entries.extend([("-",minus,5,5),("°",degree.resize((4,4),LANCZOS),0,5)])
    bmfont("WeatherSmall", 11, entries)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True); FONTS.mkdir(parents=True, exist_ok=True)
    build_scene(); build_marks(); build_fonts()
    ET.indent(XML)
    ET.ElementTree(XML).write(OUT / "drawables.xml", encoding="utf-8", xml_declaration=True)
