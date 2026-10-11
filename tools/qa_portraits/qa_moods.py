"""P-A4 moods differ where they are shown (docs/art_direction.md §7.9, §7.14). numpy + Pillow.

Usage: python3 -I tools/qa_portraits/qa_moods.py PORTRAIT_DIR [--strict]

Each pair of moods of one character is composited on a neutral plate (#9AA3AD), downscaled the way the game shows it
(premultiplied Lanczos) to two widths: 138 px (the leader seal, head ~77 px) and 80 px (the dialog row, head ~44 px),
and compared inside the face box (x 25-80 %, y 33-70 % of the frame; the same fractions on 512 and 256 masters).
Score = share of face-box pixels whose colour moved by dE76 > 12.
Gate: >= 4 % at 138 px and >= 3.5 % at 80 px for every pair: leaders 10 pairs each (calm, angry, cunning, smile,
tired); commanders calm vs smile in each era. Calibration (2026-10-11): the research prototype's five moods, which
read at 64 px, score 4.3-9.0 %; the shipped set scored 0.3-6 %. This smoke test only catches moods that barely
change; the ID-pass mood bands (portrait_qa.py) and the blind sort sheet (qa_sheets.py) say whether the change is
the right one. A folder that holds only some of the 150 names is fine.
"""
import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
import qa_common as Q  # noqa: E402

PLATE = Q.hex_rgb("#9AA3AD")
GATES = {138: 0.04, 80: 0.035}


def face(d, name, width):
    im = Q.resize_rgba(Q.load(Q.path_of(d, name)), width)
    rgb = Q.over_plate(im, PLATE)
    h, w = rgb.shape[:2]
    return Q.srgb_to_lab(rgb[int(h * 0.33):int(h * 0.70), int(w * 0.25):int(w * 0.80)])


def score(d, a, b, width):
    fa, fb = face(d, a, width), face(d, b, width)
    return float((np.sqrt(((fa - fb) ** 2).sum(-1)) > 12).mean())


def groups():
    out = [["ldr_" + x + m for m in Q.LEADER_MOODS] for x in Q.LEADERS]
    out += [["cmd_%s%s" % (c, e), "cmd_%s%s_smile" % (c, e)] for c in Q.COMMANDERS for e in Q.ERAS]
    return out


def main():
    pos, opts = Q.parse(sys.argv[1:])
    d = pos[0]
    Q.report_missing(d)
    fails = 0
    allp = []
    for g in groups():
        g = [n for n in g if Q.path_of(d, n)]
        for a, b in itertools.combinations(g, 2):
            s = {wd: score(d, a, b, wd) for wd in GATES}
            bad = [wd for wd in GATES if s[wd] < GATES[wd]]
            allp.append((s[80], a, b, s[138]))
            if bad:
                fails += 1
            if bad or a.startswith("cmd_"):
                print("%-22s vs %-22s  138px %.3f  80px %.3f%s" % (a, b, s[138], s[80], "  FAIL" if bad else ""))
    allp.sort()
    print("pairs: %d, failing: %d" % (len(allp), fails))
    if allp:
        print("weakest 5 pairs at 80 px:")
        for s80, a, b, s138 in allp[:5]:
            print("  %-22s %-22s 138px %.3f 80px %.3f" % (a, b, s138, s80))
    print("RESULT", "FAIL" if fails else "PASS", fails)
    sys.exit(1 if fails and "strict" in opts else 0)


if __name__ == "__main__":
    main()
