"""P-A1 silhouettes (docs/art_direction.md §7.14). numpy + Pillow.

Usage: python3 -I tools/qa_portraits/qa_silhouette.py PORTRAIT_DIR [--px=48] [--strict]

Masks: alpha of each era-1 calm file, area-downscaled to PX wide (aspect kept, so files of any size compare),
threshold 0.5. "head IoU" is taken over the head zone (top 70 % of the frame: hair, hats, props, beards): every bust
shares shoulders that leave the bottom edge, so a full-frame IoU is high for everyone and is printed only as INFO.
Gates (§7.14 P-A1):
- every commander pair <= 0.85 and the median of the commander pairs <= 0.78;
- every leader-commander pair <= 0.85; every leader pair <= 0.85 (the ruler is reported, not gated);
- era identity: the head zone of each era 2/3/4 file vs the same commander's era 1 >= 0.70;
- identification: every era 2/3/4 head mask is nearer (higher IoU) to its own commander's era 1 than to any other
  commander's era 1 (36 checks when the folder is complete).
Runs on a folder that holds only some of the 150 names: missing files are listed and the gates use what exists.
Exit 1 with --strict when a gate fails.
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
from qa_common import COMMANDERS, ERAS, LEADERS, alpha_mask, iou, load, parse, path_of, report_missing  # noqa: E402

HEAD_ROWS = 0.70


def main():
    pos, opts = parse(sys.argv[1:])
    d = pos[0]
    px = int(opts.get("px", 48))
    report_missing(d)

    def masks(name):
        p = path_of(d, name)
        if not p:
            return None
        m = alpha_mask(load(p), px)
        return m, m[: int(m.shape[0] * HEAD_ROWS)]

    ids = ["cmd_" + c for c in COMMANDERS] + ["ldr_" + x for x in LEADERS] + ["ruler"]
    M = {i: masks(i) for i in ids}
    M = {k: v for k, v in M.items() if v}
    fails = []

    print("== pairs by head IoU (top 12; leader pairs included) ==")
    rows = []
    for a, b in itertools.combinations(M, 2):
        rows.append((iou(M[a][1], M[b][1]), iou(M[a][0], M[b][0]), a, b))
    rows.sort(reverse=True)
    for h, f, a, b in rows[:12]:
        gated = "ruler" not in (a, b)
        print("%-14s %-14s head %.3f  full %.3f%s" % (a, b, h, f, "  FAIL" if gated and h > 0.85 else ""))
    bad = [r for r in rows if r[0] > 0.85 and "ruler" not in (r[2], r[3])]
    fails += bad
    cc = [r for r in rows if r[2].startswith("cmd_") and r[3].startswith("cmd_")]
    lc = [r for r in rows if r[2].startswith("cmd_") != r[3].startswith("cmd_") and "ruler" not in (r[2], r[3])]
    ll = [r for r in rows if r[2].startswith("ldr_") and r[3].startswith("ldr_")]
    for tag, grp in (("commander-commander", cc), ("leader-commander", lc), ("leader-leader", ll)):
        if grp:
            hs = sorted(r[0] for r in grp)
            print("%-20s pairs %3d  max %.3f  median %.3f  > 0.85: %d" % (tag, len(hs), hs[-1], hs[len(hs) // 2],
                                                                       sum(h > 0.85 for h in hs)))
    if cc:
        hs = sorted(r[0] for r in cc)
        med = hs[len(hs) // 2]
        print("commander median %.3f (gate <= 0.78)%s" % (med, "  FAIL" if med > 0.78 else ""))
        if med > 0.78:
            fails.append((med, 0, "median", ""))

    print("\n== same commander across eras (head IoU vs era 1; gate >= 0.70) ==")
    for c in COMMANDERS + ["ruler"]:
        base = "cmd_" + c if c != "ruler" else "ruler"
        if base not in M:
            continue
        vals = []
        for e in ERAS[1:]:
            m = masks(base + e)
            if m:
                vals.append(iou(M[base][1], m[1]))
        if vals:
            lo = min(vals)
            print("%-10s min %.3f  (%s)%s" % (c, lo, " ".join("%.2f" % v for v in vals), "  FAIL" if lo < 0.70 else ""))
            if lo < 0.70:
                fails.append((lo, 0, base, "eras"))

    print("\n== identification: is each era nearest to its own era 1? ==")
    ok = tot = 0
    for c in COMMANDERS:
        for e in ERAS[1:]:
            m = masks("cmd_" + c + e)
            if not m or "cmd_" + c not in M:
                continue
            tot += 1
            best = max((iou(m[1], M["cmd_" + o][1]), o) for o in COMMANDERS if "cmd_" + o in M)
            if best[1] == c:
                ok += 1
            else:
                print("  cmd_%s%s looks most like %s (%.3f)" % (c, e, best[1], best[0]))
    print("identified %d of %d%s" % (ok, tot, "" if ok == tot else "  FAIL"))
    if ok < tot:
        fails.append((ok, tot, "identification", ""))
    print("RESULT", "FAIL" if fails else "PASS", len(fails))
    sys.exit(1 if fails and "strict" in opts else 0)


if __name__ == "__main__":
    main()
