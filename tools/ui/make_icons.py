"""Draws the resource icons (coin, wheat, ingot, crystal, bubble) used by the HUD and map bubbles.
Supersampled 4x and downsampled for smooth edges. Run: python3 tools/ui/make_icons.py game/assets/ui"""
import sys, math, os
from PIL import Image, ImageDraw, ImageFilter

S = 512  # work size; saved at 128
OUT = sys.argv[1] if len(sys.argv) > 1 else "game/assets/ui"


def save(img, name):
    img.resize((128, 128), Image.LANCZOS).save(os.path.join(OUT, name + ".png"))


def shadowed(draw_fn):
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(sh), shadow=True)
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    base.alpha_composite(Image.eval(sh, lambda v: v).point(lambda v: v), (0, 10))
    draw_fn(ImageDraw.Draw(base), shadow=False)
    return base


def coin(d, shadow):
    if shadow:
        d.ellipse((70, 70, 442, 442), fill=(0, 0, 0, 120)); return
    d.ellipse((60, 60, 452, 452), fill=(150, 95, 10, 255))
    d.ellipse((80, 72, 440, 432), fill=(236, 170, 30, 255))
    d.ellipse((120, 110, 400, 392), fill=(255, 205, 60, 255))
    d.ellipse((140, 130, 380, 372), outline=(200, 130, 20, 255), width=14)
    # crown-ish R mark
    d.polygon([(205, 330), (205, 180), (300, 180), (330, 215), (300, 250), (250, 250), (320, 330), (280, 330), (225, 262), (225, 330)], fill=(190, 120, 15, 255))
    d.ellipse((150, 120, 250, 190), fill=(255, 240, 170, 200))


def wheat(d, shadow):
    col = (0, 0, 0, 110) if shadow else None
    stalk = col or (150, 110, 30, 255)
    for dx, ang in ((-70, -0.28), (0, 0.0), (70, 0.28)):
        x0, y0 = 256 + dx * 0.4, 460
        x1, y1 = 256 + dx + math.sin(ang) * 40, 150
        d.line((x0, y0, x1, y1), fill=stalk, width=22)
        for k in range(5):
            t = 0.15 + k * 0.16
            cx, cy = x0 + (x1 - x0) * (1 - t), y0 + (y1 - y0) * (1 - t)
            cy = y1 + (y0 - y1) * (k * 0.13)
            cx = x1 + (x0 - x1) * (k * 0.13)
            for side in (-1, 1):
                gx, gy = cx + side * 34, cy + 10
                fill = col or (240, 190, 60, 255)
                d.ellipse((gx - 26, gy - 40, gx + 26, gy + 40), fill=fill)
                if not shadow:
                    d.ellipse((gx - 12, gy - 30, gx + 4, gy), fill=(255, 230, 140, 255))
        top = col or (245, 200, 70, 255)
        d.ellipse((x1 - 24, y1 - 60, x1 + 24, y1 + 20), fill=top)


def ingot(d, shadow):
    if shadow:
        d.polygon([(70, 380), (442, 380), (380, 220), (132, 220)], fill=(0, 0, 0, 120)); return
    d.polygon([(60, 390), (452, 390), (452, 420), (60, 420)], fill=(70, 78, 92, 255))
    d.polygon([(60, 390), (452, 390), (385, 215), (127, 215)], fill=(150, 162, 180, 255))
    d.polygon([(127, 215), (385, 215), (360, 170), (152, 170)], fill=(205, 215, 230, 255))
    d.polygon([(152, 170), (360, 170), (385, 215), (127, 215)], fill=(222, 230, 242, 255))
    d.line((150, 250, 300, 250), fill=(240, 245, 255, 255), width=12)


def crystal(d, shadow):
    pts = [(256, 50), (420, 200), (256, 470), (92, 200)]
    if shadow:
        d.polygon(pts, fill=(0, 0, 0, 120)); return
    d.polygon(pts, fill=(40, 120, 230, 255))
    d.polygon([(256, 50), (420, 200), (256, 200)], fill=(110, 190, 255, 255))
    d.polygon([(256, 50), (92, 200), (256, 200)], fill=(70, 160, 250, 255))
    d.polygon([(92, 200), (256, 200), (256, 470)], fill=(30, 95, 200, 255))
    d.polygon([(150, 170), (210, 110), (230, 130)], fill=(220, 240, 255, 230))


def oil_drop(d, shadow):
    pts = [(256, 40), (420, 300)] + [(256 + 165 * math.cos(math.radians(k)), 300 + 165 * math.sin(math.radians(k))) for k in range(0, 181, 10)] + [(92, 300)]
    if shadow:
        d.polygon(pts, fill=(0, 0, 0, 120)); return
    d.polygon(pts, fill=(28, 24, 40, 255))
    inner = [(256, 90), (380, 300)] + [(256 + 125 * math.cos(math.radians(k)), 300 + 125 * math.sin(math.radians(k))) for k in range(0, 181, 10)] + [(132, 300)]
    d.polygon(inner, fill=(58, 48, 86, 255))
    d.ellipse((165, 250, 225, 350), fill=(160, 140, 220, 220))
    d.ellipse((180, 190, 205, 230), fill=(200, 190, 240, 200))


def hammer(d, shadow):
    c1 = (0, 0, 0, 110) if shadow else (150, 100, 50, 255)
    c2 = (0, 0, 0, 110) if shadow else (170, 180, 195, 255)
    d.line((150, 430, 330, 200), fill=c1, width=46)
    d.polygon([(250, 110), (420, 250), (380, 300), (210, 160)], fill=c2)
    if not shadow:
        d.polygon([(250, 110), (420, 250), (405, 268), (235, 128)], fill=(225, 232, 242, 255))


def bubble(d, shadow):
    if shadow:
        d.ellipse((40, 50, 472, 482), fill=(0, 0, 0, 90)); return
    d.ellipse((30, 30, 482, 482), fill=(255, 255, 255, 250))
    d.ellipse((30, 30, 482, 482), outline=(250, 205, 60, 255), width=26)


os.makedirs(OUT, exist_ok=True)
for name, fn in [("coin", coin), ("food", wheat), ("metal", ingot), ("raivite", crystal), ("oil", oil_drop), ("builder", hammer), ("bubble", bubble)]:
    save(shadowed(fn), name)
print("icons ->", OUT)
