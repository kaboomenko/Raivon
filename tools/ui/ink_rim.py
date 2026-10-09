"""Bakes the INK rim round a rendered UI icon (docs/ui_style.md §3.5), so 3D icons sit in the outlined UI.

Usage: python3 -I tools/ui/ink_rim.py IN.png OUT.png [--px N] [--ss K]

- N (rim width in px of IN) defaults to round(3 * W / 128): 3 px on a 128 px icon.
- The shape: mask = alpha > 127, dilated by a disc of radius N, filled with INK #1B2140 (opaque); the original is
  alpha-composited over it. The canvas size is kept.
- The mask is worked at K× (default 4) and box-filtered back, so the rim's outer edge is anti-aliased and its
  corners are round (a square MaxFilter would give square corners and a thicker rim on diagonals).
- If an opaque pixel lies within N px of the canvas edge, the rim would be clipped there: a WARNING is printed and the
  exit status is 2 (the icon must be framed smaller; tools/blender/icon_assets.py frames every icon to fit).

Pillow only (12.x), no numpy.
"""
import sys

from PIL import Image

INK = (0x1B, 0x21, 0x40)


def _disc_offsets(r):
    out = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r + r * 0.5:  # a slightly generous disc: no lone tips on the axes
                out.append((dx, dy))
    return out


def _dilate(mask, r):
    """Binary dilation of an L mask (0/255) by a disc of radius r, without wrap-around at the edges."""
    w, h = mask.size
    out = Image.new("L", (w, h), 0)
    # pasting a solid 255 through the mask at every offset of the disc = the union of the shifted masks
    rows = {}
    for dx, dy in _disc_offsets(r):
        rows.setdefault(dy, []).append(dx)
    for dy, dxs in rows.items():
        # one row of the disc is a horizontal run: dilate horizontally once, then shift vertically
        lo, hi = min(dxs), max(dxs)
        row = Image.new("L", (w, h), 0)
        for dx in range(lo, hi + 1):
            row.paste(255, (dx, 0, dx + w, h), mask)
        out.paste(255, (0, dy, w, dy + h), row)
    return out


def edge_clearance(im, n):
    """The smallest distance (px) from an opaque pixel (alpha > 127) to the canvas edge, or None if none is opaque."""
    a = im.getchannel("A").point(lambda v: 255 if v > 127 else 0)
    box = a.getbbox()
    if box is None:
        return None
    w, h = im.size
    return min(box[0], box[1], w - box[2], h - box[3])


def rim(im, n=None, ss=4):
    im = im.convert("RGBA")
    w, h = im.size
    if n is None:
        n = max(1, round(3 * w / 128))
    alpha = im.getchannel("A")
    big = alpha.resize((w * ss, h * ss), Image.BILINEAR).point(lambda v: 255 if v > 127 else 0)
    # halve the work: dilate by the radius in two passes of half the radius each (disc ⊕ disc = disc of the sum)
    r = n * ss
    r1 = r // 2
    d = _dilate(big, r1)
    d = _dilate(d, r - r1)
    rim_a = d.resize((w, h), Image.BOX)
    base = Image.new("RGBA", (w, h), INK + (0,))
    base.putalpha(rim_a)
    base.alpha_composite(im)
    return base, n


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) if "=" in a else (a[2:], None) for a in argv if a.startswith("--"))
    # also accept "--px N" with a space
    for flag in ("px", "ss"):
        if flag in opts and opts[flag] is None:
            i = argv.index("--" + flag)
            opts[flag] = argv[i + 1]
            args.remove(argv[i + 1])
    if len(args) != 2:
        print(__doc__)
        return 1
    src, dst = args
    im = Image.open(src).convert("RGBA")
    n = int(opts["px"]) if opts.get("px") else None
    out, n = rim(im, n, int(opts.get("ss") or 4))
    out.save(dst)
    c = edge_clearance(im, n)
    if c is not None and c < n:
        print("WARNING: %s: an opaque pixel lies %d px from the edge, the %d px rim is clipped" % (src, c, n))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
