"""Commander portraits (04 §15.4, docs/art_direction.md §7): 3/4 busts rendered on a transparent background (the game
draws the rarity plate and frame). Run: python3 tools/blender/portrait_assets.py OUTDIR [ids...] [--size=N]
[--eras=1,2,3,4] [--moods=calm,smile,...]. The game's set (game/assets/ui/portraits, 150 files) is exactly what these
three commands write (add --force to overwrite the files already in OUTDIR):
- the 96 commanders (512×588):
  python3 tools/blender/portrait_assets.py game/assets/ui/portraits cmd_bram cmd_lira cmd_olm cmd_vik cmd_vega
  cmd_kort cmd_seir cmd_frey cmd_irma cmd_hawk cmd_vance cmd_rai --eras=1,2,3,4 --moods=calm,smile
- the 50 AI leaders (256×294):
  python3 tools/blender/portrait_assets.py game/assets/ui/portraits ldr_barons ldr_hamlets ldr_league ldr_order
  ldr_alvaria ldr_saren ldr_pack ldr_conclave ldr_veilmark ldr_lakes --moods=calm,angry,cunning,smile,tired
- the 4 rulers (256×294): python3 tools/blender/portrait_assets.py game/assets/ui/portraits ruler --eras=1,2,3,4
Without ids every kit id is rendered (each in era 1, calm, unless --eras / --moods say otherwise). Without --force every
file that already exists is skipped, so an interrupted batch resumes and the three commands do nothing on a full folder.
Every id goes through the portrait kit v2 (tools/blender/portrait_kit/, §7.5; portrait_kit/chars.py KIT_IDS, KIT_ERAS:
the twelve commanders and the ruler in eras 1–4, the ten AI leaders in era 1 with their five moods), Cycles 64 samples,
AgX Punchy, seed 0: commanders 512×588; the leaders and the ruler rendered at the same 512 master and shipped as
256×294 by the premultiplied Lanczos downscale of portrait_kit.core.downscale (§7.12; with --sidecars the masters and
their sidecars stay in SIDECARS/master/, the shipped-size sidecars are scaled into SIDECARS/). An id or era the kit
does not list (a leader with --eras=2..4, an unknown id) is reported as FAILED and the run exits 1 (the old primitive
builder is gone since P4). The hand poses of §7.5 (Vance, Seir, Irma, Vega) follow chars.py ("hands"); the
environment's KIT_HANDS=0/1 forces the hand-free fallbacks / the hands for the side-by-side review (§7.15 q3).
Flags: --size=N (render width; height = int(N × 1.15), the 0.8707 aspect; no downscale), --samples=N, --frame=bust|face
(face = a square face crop, not shipped), --sidecars=DIR (DIR/ids/NAME.png part-ID pass + NAME.json colours +
NAME_sig.png signature mask, DIR/meta/NAME.json projected landmarks and the contact report; read by
tools/qa_portraits), --contacts (print the P-A7 contact report), --stats (triangles, build and render seconds),
--force (re-render files that exist). `python3 tools/blender/portrait_assets.py --selftest` (no OUTDIR) builds every
kit character with the open mouths and lids later steps need, every era look (E2–E4) and every leader mood, runs the
chars.py lint, renders nothing, and exits 1 when a build or the lint fails (portrait_kit.qa.build_regression).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402,F401  (bpy before the kit's bmesh)
import portrait_kit  # noqa: E402

# every kit id in the order of chars.py: the twelve commanders, the ten AI leaders, the ruler
IDS = list(portrait_kit.chars.CHARS)


def _opts():
    return dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = _opts()
    if "selftest" in opts:  # build-only regression of the kit (no OUTDIR, nothing written)
        sys.exit(0 if portrait_kit.qa.build_regression() else 1)
    size_opt = int(opts["size"]) if "size" in opts else None
    eras = [int(x) for x in opts["eras"].split(",")] if "eras" in opts else [1]
    moods = ["" if m == "calm" else m for m in opts["moods"].split(",")] if "moods" in opts else [""]
    samples_opt = int(opts["samples"]) if "samples" in opts else None
    frame = opts.get("frame", "bust")
    sidecars = opts.get("sidecars")
    out = args[0]
    ids = args[1:] or IDS
    os.makedirs(out, exist_ok=True)
    failed = []
    for cid in ids:
        for era in eras:
            for mood in moods:
                name = cid if era == 1 else "%s_e%d" % (cid, era)  # era 1 keeps the plain name
                if mood:
                    name += "_" + mood
                path = os.path.join(out, name + ".png")
                if os.path.exists(path) and "force" not in opts:
                    print("skipped", name, "(exists; --force re-renders)")
                    continue
                if not portrait_kit.supports(cid, era):
                    print("FAILED", name, "- not a kit id or era (portrait_kit.chars.KIT_IDS / KIT_ERAS)")
                    failed.append(name)
                    continue
                # commanders render at 512x588; the leaders and the ruler at the same 512 master, shipped as
                # 256x294 by the premultiplied Lanczos downscale (§7.12); --size renders straight at that width
                ship = portrait_kit.ship_size(cid)
                downscale = size_opt is None and frame == "bust" and ship[0] < 512
                w = size_opt or 512
                rpath, rside = path, sidecars
                tmp = None
                if downscale:
                    if sidecars:
                        rside = os.path.join(sidecars, "master")
                        os.makedirs(rside, exist_ok=True)
                        rpath = os.path.join(rside, name + ".png")
                    else:
                        import tempfile
                        tmp = tempfile.mkdtemp(prefix="portrait_master_")
                        rpath = os.path.join(tmp, name + ".png")
                try:
                    r = portrait_kit.render_id(cid, rpath, mood or "calm", era,
                                               (w, w) if frame == "face" else (w, int(w * 1.15)),
                                               samples_opt or portrait_kit.style.RENDER["samples"], frame, rside,
                                               "contacts" in opts, "stats" in opts)
                except RuntimeError as e:  # the framing solver's "does not fit": report, go on, exit 1 at the end
                    print("FAILED", name, "-", e)
                    failed.append(name)
                    continue
                if downscale:
                    portrait_kit.core.downscale(rpath, ship[0], path)
                    if sidecars:
                        portrait_kit.qa.scale_sidecars(rside, sidecars, name, ship)
                    if tmp:
                        import shutil
                        shutil.rmtree(tmp, ignore_errors=True)
                print("rendered", name, "(kit v2) build %.1fs render %.1fs" % (r["build_s"], r["render_s"]))
                for nt in r.get("notes") or []:
                    print("NOTE", name, "-", nt)
                if "stats" in opts and r["stats"]:
                    st = r["stats"]
                    print("STATS %s triangles %d objects %d build %.1fs render %.1fs samples %d" % (
                        name, st["triangles"], st["objects"], r["build_s"], r["render_s"], st["samples"]))
                if "contacts" in opts:
                    bad = [c for c in r["contacts"] if c["status"] != "ok"]
                    print("CONTACTS %s: %d parts checked, %d floating or buried%s" % (
                        name, len(r["contacts"]), len(bad), "".join(
                            "\n  %s on %s: %s (gap %.4f H, buried %.0f%%)" % (c["part"], c["parent"], c["status"],
                                                                           c["gap_H"], c["buried_share"] * 100)
                            for c in bad)))
    if failed:
        print("FAILED %d: %s" % (len(failed), " ".join(failed)))
        sys.exit(1)


if __name__ == "__main__":
    main()
