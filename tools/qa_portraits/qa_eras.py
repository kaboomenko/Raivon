"""P-A9 eras and distinctness, P-A8 era details, the leader module lint (docs/art_direction.md §7.7, §7.8, §7.14).
numpy + Pillow.

Usage: python3 -I tools/qa_portraits/qa_eras.py PORTRAIT_DIR [--strict]

Needs the kit's sidecars (portrait_assets.py --sidecars=PORTRAIT_DIR): ids/<name>.png (part-ID pass) and
meta/<name>.json. Checks, on the calm files of each era present (a folder with only some of the 150 names is fine):
- main colour: the median CIE Lab of the beauty render over the largest clothes group of the ID pass (costume /
  costume:<id>; details and metal excluded; MAIN_GROUP names it where the largest is not the §7.6 main colour,
  Olm's E1 apron over the shirt) — E1 vs EN of one commander (and the ruler) dE76 <= 22; between any two
  commanders in E3 and in E4 dE76 >= 12 (§7.7);
- face mask: skin, eyes, brows, lashes, nose, lips and mouth inside the head box down to the chin, E1 vs EN changed
  share <= 2 % (pixels under a hat, glass or detail in either file left out, §7.7 "вне перекрытия убором");
- headgear table per era (meta "headgear"): no headgear twice in one era among the commanders (§7.6);
- P-A8 era details: Vance's aiguillette from E2 (>= its threshold), Seir's tricorns in E1–E2, Vik's raven line in every
  era (raven -> message tube -> clockwork -> drone, the "raven" detail), Kort's fur in every era;
- E4 glow budget: emissive strips (detail:glow*) <= 3 % of the opaque pixels (§7.4);
- leader lint (meta "modules"): no leader, nor the ruler, uses a module locked to a commander (§7.8 rule 1).
Exit 1 with --strict when a gate fails.
"""
import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
import qa_common as Q  # noqa: E402

LOCKED = dict(hair={"kerchief": "Lira", "ponytail": "Irma", "bun": "Vance", "bob": "Vega", "flattop": "Frey",
                    "fringe": "Vik"},
              beard={"pear": "Bram", "long": "Rai", "walrus": "Kort", "thin": "Hawk", "chops": "Olm"},
              headgear={"hood": "Vik", "circlet": "Rai", "aviator": "Hawk", "kerchief": "Lira"},
              props={"raven": "Vik", "scarf": "Hawk", "queen": "Vance", "spoon": "Bram", "spyglass": "Seir"})
FACE = ("skin", "sclera", "iris", "pupil", "catch", "lash", "brow", "nose", "lip", "mouth", "teeth", "tongue", "eye")
COVER = ("hat", "glass")


# the main colour's group where the largest clothes group is not it (§7.6 palette, the first colour named): Olm's E1
# shirt is "inside the apron" (#E8DCC0), his main colour the apron's leather #7A4E2D
MAIN_GROUP = {"cmd_olm": "detail:apron",     # (the apron is a P-A8 detail group in the ID pass)
              # Frey's E2-E3 green uniform under the steel cuirass (the cuirass is the larger group; §7.6 names the
              # green first and the steel as trim), Rai's white robe under the blue stole (§7.6: "белое одеяние" first)
              "cmd_frey_e2": "costume", "cmd_frey_e3": "costume",
              "cmd_rai": "costume", "cmd_rai_e2": "costume", "cmd_rai_e3": "costume",
              # Rai's E4 silver plates under the E1-E3 cloak and stole (§7.6 "бело-серебряные пластины" first)
              "cmd_rai_e4": "costume:plate"}


def clothes_lab(rgba, masks, prefer=None):
    groups = {k: v for k, v in masks.items() if k == "costume" or k.startswith("costume:")}
    if not groups:
        return None, None
    if prefer in masks:
        k, m = prefer, masks[prefer]
    else:
        k, m = max(groups.items(), key=lambda kv: kv[1].sum())
    m = m & (rgba[..., 3] > 0.9)
    if m.sum() < 50:
        return None, k
    lab = Q.srgb_to_lab(rgba[..., :3][m])
    return np.median(lab, axis=0), k


def face_mask(masks, meta):
    h, w = next(iter(masks.values())).shape
    face = np.zeros((h, w), bool)
    cover = np.zeros((h, w), bool)
    for k, v in masks.items():
        if k in FACE:
            face |= v
        if k in COVER or k.startswith("detail:"):
            cover |= v
    box = np.zeros((h, w), bool)
    hb = meta.get("head_box") or [0, 0, w, h]
    y1 = int(min(h, meta.get("chin_y", hb[3])))
    box[max(0, int(hb[1])):y1, max(0, int(hb[0])):min(w, int(hb[2]) + 1)] = True
    return face & box, cover


def main():
    pos, opts = Q.parse(sys.argv[1:])
    d = pos[0]
    Q.report_missing(d)
    fails = []
    ids = ["cmd_" + c for c in Q.COMMANDERS] + ["ruler"]
    data = {}
    for base in ids:
        for e in Q.ERAS:
            n = base + e
            p = Q.path_of(d, n)
            masks, _ = Q.ids(d, n)
            meta = Q.meta(d, n)
            if p is None or masks is None or meta is None:
                continue
            rgba = Q.load(p)
            lab, grp = clothes_lab(rgba, masks, MAIN_GROUP.get(n))
            fm, cov = face_mask(masks, meta)
            data[n] = dict(lab=lab, grp=grp, face=fm, cover=cov, meta=meta, masks=masks, rgba=rgba)
    print("== main colour (median Lab of the largest clothes group) E1 vs EN: dE76 <= 22 ==")
    for base in ids:
        if base not in data or data[base]["lab"] is None:
            continue
        row = []
        for e in Q.ERAS[1:]:
            n = base + e
            if n in data and data[n]["lab"] is not None:
                de = float(Q.de76(data[base]["lab"], data[n]["lab"]))
                row.append("%s %.1f (%s)" % (e[1:], de, data[n]["grp"]))
                if de > 22:
                    fails.append(("main colour", n, de))
        print("%-10s E1 %s  %s%s" % (base, data[base]["grp"], "  ".join(row),
                                    "  FAIL" if any(f[1].startswith(base + "_") for f in fails if f[0] == "main colour") else ""))
    for e in ("_e3", "_e4"):
        labs = {c: data["cmd_" + c + e]["lab"] for c in Q.COMMANDERS if "cmd_" + c + e in data and
                data["cmd_" + c + e]["lab"] is not None}
        pairs = sorted((float(Q.de76(labs[a], labs[b])), a, b) for a, b in itertools.combinations(labs, 2))
        bad = [p for p in pairs if p[0] < 12]
        if pairs:
            print("era %s: %d commander pairs, min dE76 %.1f (%s/%s), %d under 12%s" % (
                e[1:], len(pairs), pairs[0][0], pairs[0][1], pairs[0][2], len(bad), "  FAIL" if bad else ""))
            for p in bad[:8]:
                print("   %s - %s dE76 %.1f" % (p[1], p[2], p[0]))
        fails += [("era dE", e + ":" + p[1] + "/" + p[2], p[0]) for p in bad]
    print("\n== face mask E1 vs EN (head box, chin up; under hats / glass / details left out): <= 2 % ==")
    for base in ids:
        if base not in data:
            continue
        row = []
        for e in Q.ERAS[1:]:
            n = base + e
            if n not in data or data[n]["face"].shape != data[base]["face"].shape:
                continue
            keep = ~(data[base]["cover"] | data[n]["cover"])
            a, b = data[base]["face"] & keep, data[n]["face"] & keep
            u = (a | b).sum()
            ch = float((a ^ b).sum()) / u if u else 0.0
            row.append("%s %.2f%%" % (e[1:], ch * 100))
            if ch > 0.02:
                fails.append(("face mask", n, ch))
        print("%-10s %s" % (base, "  ".join(row)))
    print("\n== headgear per era (§7.6: none twice in one era) ==")
    for e in Q.ERAS:
        worn = {}
        for c in Q.COMMANDERS:
            m = Q.meta(d, "cmd_" + c + e)
            if m and m.get("headgear"):
                worn.setdefault(m["headgear"], []).append(c)
        dup = {k: v for k, v in worn.items() if len(v) > 1}
        print("E%s: %s%s" % (e[2:] or "1", ", ".join("%s=%s" % (v[0], k) for k, v in sorted(worn.items(), key=lambda kv: kv[1])),
                             ("  FAIL duplicates " + str(dup)) if dup else ""))
        fails += [("headgear", e + k, len(v)) for k, v in dup.items()]
    print("\n== P-A8 era details ==")

    def det(n, name):
        m = Q.meta(d, n)
        masks, _ = Q.ids(d, n)
        if not m or masks is None:
            return None, None
        return int(masks.get("detail:" + name, np.zeros(1, bool)).sum()), (m.get("details") or {}).get(name)
    for c, name, eras in (("vance", "aiguillette", Q.ERAS[1:]), ("vik", "raven", Q.ERAS), ("kort", "fur", Q.ERAS)):
        row = []
        for e in eras:
            got, need = det("cmd_" + c + e, name)
            if got is None:
                continue
            ok = need is not None and got >= need
            row.append("%s %d/%s%s" % (e[1:] or "e1", got, need, "" if ok else " FAIL"))
            if not ok:
                fails.append(("era detail", "cmd_" + c + e + ":" + name, got))
        print("%-6s %-12s %s" % (c, name, "  ".join(row)))
    row = []
    for e in Q.ERAS[:2]:
        m = Q.meta(d, "cmd_seir" + e)
        if m:
            hg = m.get("headgear")
            if hg is None and "headgear" not in m:
                # the P2 era-1 files predate the meta "headgear" key: §7.6's E1 tricorn, if the ID pass has the hat
                masks, _ = Q.ids(d, "cmd_seir" + e)
                hat = int(masks["hat"].sum()) if masks is not None and "hat" in masks else 0
                hg = "tricorn (P2 meta; hat %d px)" % hat if hat >= 1000 else None
            ok = str(hg or "").startswith("tricorn")
            row.append("%s %s%s" % (e[1:] or "e1", hg, "" if ok else " FAIL"))
            if not ok:
                fails.append(("era detail", "cmd_seir" + e + ":tricorn", 0))
    print("seir   tricorn      %s" % "  ".join(row))
    print("\n== E4 glow budget (detail:glow* <= 3 % of the opaque pixels) ==")
    for base in ids:
        n = base + "_e4"
        if n not in data:
            continue
        op = (data[n]["rgba"][..., 3] > 0.5).sum()
        g = sum(v.sum() for k, v in data[n]["masks"].items() if k.startswith("detail:glow"))
        share = g / max(1, op)
        print("%-12s %.2f%%%s" % (n, share * 100, "  FAIL" if share > 0.03 else ""))
        if share > 0.03:
            fails.append(("glow", n, share))
    print("\n== leader / ruler module lint (§7.8 rule 1) ==")
    for n in ["ldr_" + x for x in Q.LEADERS] + ["ruler"]:
        m = Q.meta(d, n)
        if not m or not m.get("modules"):
            continue
        md = m["modules"]
        bad = []
        if md.get("hair") in LOCKED["hair"]:
            bad.append("hair %s (%s)" % (md["hair"], LOCKED["hair"][md["hair"]]))
        if md.get("beard") in LOCKED["beard"]:
            bad.append("beard %s (%s)" % (md["beard"], LOCKED["beard"][md["beard"]]))
        if md.get("headgear") in LOCKED["headgear"]:
            bad.append("headgear %s (%s)" % (md["headgear"], LOCKED["headgear"][md["headgear"]]))
        bad += ["prop %s (%s)" % (p, LOCKED["props"][p]) for p in md.get("props", []) if p in LOCKED["props"]]
        bad += ["Vega's rectangular glasses" for g in md.get("glasses", []) if g == "rect"]
        print("%-14s hair %-8s beard %-8s headgear %-8s props %s%s" % (n, md.get("hair"), md.get("beard"),
                                                                      md.get("headgear"), ",".join(md.get("props", [])),
                                                                      ("  FAIL " + "; ".join(bad)) if bad else ""))
        fails += [("lint", n, b) for b in bad]
    print("RESULT", "FAIL" if fails else "PASS", len(fails))
    sys.exit(1 if fails and "strict" in opts else 0)


if __name__ == "__main__":
    main()
