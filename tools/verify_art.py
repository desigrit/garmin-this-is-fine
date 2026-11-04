"""Check the shipping bitmap assets at native resolution. Optional: --sheet FILE."""
import argparse
import math
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw
from prepare_art import ART, FONTS, MOVING, OCCLUSION, OUT, SKY, STATIC


@lru_cache(maxsize=None)
def mark(name):
    return Image.open(OUT/(name+".png")).convert("RGBA")


@lru_cache(maxsize=None)
def room(mode, pose):
    im = Image.new("RGBA",(260,260))
    for label, (x,y,_,_) in STATIC.items():
        im.paste(mark(mode+label), (x,y))
    for side, (x,y,_,_) in MOVING.items():
        im.paste(mark(mode+side+str(pose)),(x,y))
    assert im.getchannel("A").getextrema() == (255,255)
    return im


def sun_y(b):
    if b <= SKY["cutoff"]:
        return None
    # Round to the nearest row, like the firmware and the design pane.
    lo, hi, a, z = (50,100,SKY["halfY"],SKY["y"]) if b>=50 else (SKY["cutoff"]+1,50,SKY["lastY"],SKY["halfY"])
    return math.floor(a+(z-a)*(b-lo)/(hi-lo)+.5)


def sky(mode, pose, charge):
    im = room(mode,pose).copy()
    if mode == "Day":
        y = sun_y(charge)
        if y is None:
            return im
        pic = mark("Sun")
        im.alpha_composite(pic, (SKY["x"]-pic.width//2, y-pic.height//2))
    else:
        pen=ImageDraw.Draw(im)
        for x,y in ((53,100),(91,99),(56,111)):
            pen.rectangle((x,y,x+1,y+1), fill=(170,170,255))
        if not charge:
            return im
        r = SKY["radius"]
        for i in range(2*r):
            half = math.floor(math.sqrt(r*r-(i+.5-r)**2)+.5)
            width = max(1 if i in (8,9) else 0, (2*half*charge+50)//100)
            if width:
                x,y = SKY["x"]-half, SKY["y"]-r+i
                pen.rectangle((x,y,x+width-1,y), fill=(255,255,170))
    im.alpha_composite(mark(mode+"Fore"+str(pose)), OCCLUSION[:2])
    return im


@lru_cache(maxsize=None)
def get_font(name):
    fnt = (FONTS/(name+".fnt")).read_text()
    pix = Image.open(FONTS/(name+".png")).convert("RGBA").getchannel("A")
    chars = {}
    for line in fnt.splitlines():
        if not line.startswith("char "): continue
        n = {k:int(v) for k,v in re.findall(r"(\w+)=(-?\d+)",line)}
        chars[chr(n["id"])] = (pix.crop((n["x"],n["y"],n["x"]+n["width"],n["y"]+n["height"])),n["yoffset"],n["xadvance"])
    return int(re.search(r"lineHeight=(\d+)",fnt)[1]), chars


def text(im, name, msg, cx, cy):
    h, glyphs = get_font(name)
    x = cx-sum(glyphs[c][2] for c in msg)//2
    for ch in msg:
        glyph,offset,advance=glyphs[ch]
        im.paste((0,0,0,255), (x,cy-h//2+offset,x+glyph.width,cy-h//2+offset+glyph.height), glyph)
        x += advance


def draw_face(mode, pose, charge, clock, temp, alarm, phone, line=None):
    im = sky(mode,pose,charge)
    if line:
        ink=mark(line); im.alpha_composite(ink,(130-ink.width//2,55-ink.height//2))
        return im
    compact=len(clock)==5
    text(im, "ClockCompact" if compact else "ClockWide", clock, 115 if compact else 116, 55)
    text(im, "WeatherSmall", temp, 178, 45)
    if alarm:
        im.alpha_composite(mark("Alarm"),(163,54))
    im.alpha_composite(mark("Receiver" if phone else "ReceiverOff"),(180 if alarm else 171,54))
    return im


def verify():
    # Test the actual pixels exposed above the four native occlusion bitmaps.
    for p in range(4):
        base=room("Day",p).convert("RGB")
        mask = Image.open(ART/"window-atlas.png").convert("RGBA").getchannel("A").crop((260*p,0,260*(p+1),260))
        for b in range(101):
            im=sky("Day",p,b).convert("RGB")
            diff=ImageChops.difference(im,base).convert("L").point(lambda v: 255 if v else 0)
            assert not ImageChops.subtract(diff,mask).getbbox(), (p,b,"sun painted over fire")
            exposed = sum(px==(255,255,85) and old!=px for px,old in
                          zip(im.crop(OCCLUSION).get_flattened_data(),base.crop(OCCLUSION).get_flattened_data()))
            assert (exposed == 0 if b<=5 else exposed>=10), (p,b,exposed)
            if b in (6,20,100):
                print(f"pose {p}, charge {b}: {exposed} yellow sun pixels")
        moon0 = sky("Night",p,0).convert("RGB")
        prev=0
        for b in range(101):
            diff=ImageChops.difference(sky("Night",p,b).convert("RGB"),moon0).convert("L")
            bounds=diff.getbbox()
            n=sum(v!=0 for v in diff.get_flattened_data()) if bounds else 0
            assert n>=prev and (bool(bounds)==bool(b)), (b,bounds)
            if bounds: assert 62<=bounds[0]<=82 and 96<=bounds[1]<114 and bounds[3]<=114
            prev=n
        assert sky("Night",p,100).crop((62,95,82,115)).tobytes() == sky("Night",0,100).crop((62,95,82,115)).tobytes()

    # Every real clock label must fit to the left of the status block.
    for hour in range(24):
        for minute in range(60):
            for label in (f"{hour:02}:{minute:02}", f"{hour%12 or 12}:{minute:02}"):
                compact=len(label)==5
                _, chars = get_font("ClockCompact" if compact else "ClockWide")
                advance=sum(chars[c][2] for c in label)
                x=(115 if compact else 116)-advance//2
                width=advance-chars[label[-1]][2]+chars[label[-1]][0].width
                assert x+width<=160 and x>=65, (label,x,width)
    # Keep the ink bounds stable for both one- and two-digit hours.
    for label, target in (("8:08", (80,28)), ("10:03", (86,26))):
        im=Image.new("RGB",(260,90),"white").convert("RGBA")
        compact=len(label)==5
        text(im,"ClockCompact" if compact else "ClockWide",label,115 if compact else 116,55)
        x,y,r,b=im.convert("L").point(lambda v: 255 if v<96 else 0).getbbox()
        assert abs(r-x-target[0])<=1 and abs(b-y-target[1])<=1, (label,(r-x,b-y),target)
    for line in ("ThisIsFine","SendCoffee"):
        ink=mark(line)
        assert ink.getchannel("A").getbbox()
        assert ink.width<=142
    assert ImageChops.difference(mark("Receiver").getchannel("A"),mark("ReceiverOff").getchannel("A")).getbbox()

    # Conservative pixel storage, including per-row padding on 4 bpp tiles.
    for mode in ("Day","Night"):
        bitmaps=[e for e in ET.parse(OUT/"drawables.xml").getroot() if e.get("id").startswith(mode)
                 or not e.get("id").startswith(("Day","Night","Launcher"))]
        raw=0
        for node in bitmaps:
            palette=node.find("palette")
            count=len(palette)+(palette.get("disableTransparency")!="true")
            assert count<=16
            pic=mark(node.get("id"))
            raw+= ((pic.width+7)//8)*4*pic.height+64
        assert raw<78*1024, (mode,raw)
        print(f"{mode}: at most {raw:,} bytes of drawable pixels and palettes for all poses.")
    print("Native artwork checks passed.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--sheet",type=Path)
    options=parser.parse_args()
    verify()
    if options.sheet:
        im=Image.new("RGB",(3*260,260),(0,0,0))
        for i, spec in enumerate([("Day",0,100,"8:08","64°",True,True,None),
                                  ("Day",1,6,"12:45","--°",False,False,"ThisIsFine"),
                                  ("Night",0,26,"22:36","-3°",False,False,None)]):
            im.paste(draw_face(*spec).convert("RGB"),(i*260,0))
        options.sheet.parent.mkdir(parents=True,exist_ok=True)
        im.save(options.sheet,optimize=True)
