"""Adds the title to the rendered key art → splash / loading screen and store art.
Run: python3 tools/ui/compose_keyart.py RENDER.png OUT.png [--subtitle "Territory Wars"]"""
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

src, out = sys.argv[1], sys.argv[2]
subtitle = sys.argv[sys.argv.index("--subtitle") + 1] if "--subtitle" in sys.argv else "TERRITORY WARS"
im = Image.open(src).convert("RGBA")
W, H = im.size
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# soft dark gradient at the top so the title reads over the sky
grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(grad)
for y in range(int(H * 0.36)):
    a = int(150 * (1 - y / (H * 0.36)) ** 1.6)
    gd.line([(0, y), (W, y)], fill=(8, 16, 40, a))
im = Image.alpha_composite(im, grad)


def text_layer(txt, size, fill, outline, y, spacing=0):
    font = ImageFont.truetype(BOLD, size)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # letter-spaced width
    widths = [d.textlength(ch, font=font) for ch in txt]
    total = sum(widths) + spacing * (len(txt) - 1)
    x = (W - total) / 2
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    cx = x
    for ch, w in zip(txt, widths):
        sd.text((cx + 6, y + 10), ch, font=font, fill=(0, 0, 0, 170))
        d.text((cx, y), ch, font=font, fill=fill, stroke_width=max(3, size // 14), stroke_fill=outline)
        cx += w + spacing
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    return Image.alpha_composite(shadow, layer)


title = text_layer("RAIVON", int(W * 0.2), (255, 214, 92, 255), (92, 44, 6, 255), int(H * 0.06), spacing=int(W * 0.012))
# vertical gold gradient on the title letters
mask = title.split()[3]
grad2 = Image.new("RGBA", (W, H))
g2 = ImageDraw.Draw(grad2)
y0, y1 = int(H * 0.06), int(H * 0.06 + W * 0.24)
for y in range(H):
    t = min(1, max(0, (y - y0) / max(1, y1 - y0)))
    g2.line([(0, y), (W, y)], fill=(int(255 - 20 * t), int(236 - 80 * t), int(140 - 110 * t), 255))
im = Image.alpha_composite(im, title)
sub = text_layer(subtitle.upper(), int(W * 0.062), (235, 242, 255, 255), (20, 40, 90, 255), int(H * 0.06 + W * 0.25), spacing=int(W * 0.01))
im = Image.alpha_composite(im, sub)
im.convert("RGB").save(out)
print(out)
