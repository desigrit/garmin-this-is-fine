"""Rebuild the three moving poses from the resting day, night and window artwork."""
from pathlib import Path
import math
from PIL import Image, ImageFilter

ART = Path(__file__).resolve().parents[1] / "art"
SIZE = 260
# Tip position, area of influence, sideways travel and rise, in display pixels.
# Adjacent tongues lean in different directions. Their bases stay planted.
TIPS = (
    (19, 70, 19, 32,  6,  7),
    (40, 88, 15, 26, -6,  8),
    (31,116, 16, 22, -5, -5),
    (58,122, 16, 23,  6,  8),
    (73,131, 13, 15, -3, -3),
    (95,111, 15, 21, -7,  9),
    (52,146, 15, 17, -5,  5),
    (203,107, 18, 24, -7,  9),
    (216,132, 15, 20,  5, -6),
    (245, 83, 22, 34,  7, -8),
    (236,116, 15, 25, -7,  8),
)
POSES = ((0,0), (1,1), (-.2,-.82), (-1,.35))


def ramp(value):
    value = min(1, max(0, value))
    return value*value*(3-2*value)


def brush(x, y, cx, cy, rx, ry):
    return max(0, 1-((x-cx)/rx)**2-((y-cy)/ry)**2)**2


def offsets(area):
    points = []
    for y in range(43, 155):
        for x in (*range(104), *range(189, 260)):
            edge = min(y-42,155-y,104-x if x<104 else x-188)
            weight = area[x,y]/255 * ramp(edge/8)
            if not weight:
                continue
            dx = dy = 0
            for cx,cy,rx,ry,sway,rise in TIPS:
                amount = brush(x,y,cx,cy,rx,ry)
                dx += sway*amount
                dy += rise*amount
            if x < 104:
                # Keep the low-charge rim visible in every pose.
                weight *= 1-.90*brush(x,y,72,135,15,15)
                if x > 91:
                    weight *= ramp((142-y)/9)
            elif 194 < x < 235:
                # The lip of the coffee mug is in front of the fire.
                weight *= ramp((145-y)/8)
            if weight and (dx or dy):
                points.append((x,y,dx*weight,dy*weight))
    return points


def behind_fire(x, y):
    # The clear strip at row 100 supplies the sky and both vertical window
    # edges. Elsewhere a retreating flame reveals the plain wall.
    if 43 <= x <= 106 and y >= 90:
        return x, min(y,100)
    return 130,10


def build():
    scene_path, mask_path = ART/"scene-compact.png", ART/"window-atlas.png"
    atlas = Image.open(scene_path).convert("RGB")
    mask_atlas = Image.open(mask_path).convert("RGBA")
    day = atlas.crop((0,0,SIZE,SIZE))
    night = atlas.crop((0,SIZE,SIZE,2*SIZE))
    window = mask_atlas.crop((0,0,SIZE,SIZE)).getchannel("A")
    fire = Image.new("L",day.size)
    fire.putdata([255 if r>=170 and g>=85 and b==0 else 0 for r,g,b in day.get_flattened_data()])
    area = fire.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(2))
    points = offsets(area.load())
    day_pixels, night_pixels, sky_pixels = day.load(), night.load(), window.load()
    rim = fire.filter(ImageFilter.MaxFilter(7)).load()
    foreground = Image.new("L",day.size)
    foreground.putdata([
        255 if rim[x,y] and day_pixels[x,y] != day_pixels[behind_fire(x,y)] else 0
        for y in range(SIZE) for x in range(SIZE)
    ])
    moving = foreground.load()
    for pose, (sway, rise) in enumerate(POSES[1:], 1):
        images = [im.copy() for im in (day,night,window)]
        day_out, night_out, sky_out = (im.load() for im in images)
        for x,y,dx,dy in points:
            sx = min(258.999, max(0, x+dx*sway))
            sy = min(258.999, max(0, y+dy*rise))
            u,v = math.floor(sx), math.floor(sy)
            a,b = sx-u,sy-v
            taps = ((u,v,(1-a)*(1-b)), (u+1,v,a*(1-b)), (u,v+1,(1-a)*b), (u+1,v+1,a*b))
            # Move only the foreground fire and its ink. Sampling the window
            # itself at a displaced coordinate would bend or duplicate its frame.
            backdrop = behind_fire(x,y) if moving[x,y] else (x,y)
            taps = [(i,j,w) if moving[i,j] else (*backdrop,w) for i,j,w in taps]
            for src, dest in ((day_pixels,day_out),(night_pixels,night_out)):
                dest[x,y] = tuple(85*round(sum(src[i,j][k]*w for i,j,w in taps)/85) for k in range(3))
            sky_out[x,y] = 255 if sum(sky_pixels[i,j]*w for i,j,w in taps)>=127.5 else 0
        atlas.paste(images[0],(pose*SIZE,0))
        atlas.paste(images[1],(pose*SIZE,SIZE))
        mask = Image.new("RGBA",day.size,"white")
        mask.putalpha(images[2])
        mask_atlas.paste(mask,(pose*SIZE,0))
    atlas.save(scene_path,optimize=True)
    mask_atlas.save(mask_path,optimize=True)


if __name__ == "__main__":
    build()
