"""Kit-side QA (§7.14): the part-ID pass and the signature mask, the landmark JSON, the contact test and the stats.

--sidecars=DIR writes, next to a render NAME.png:
  DIR/ids/NAME.png      flat-emission part-ID pass: every material replaced by an emission colour of its group
                        (style.ID_COLORS; detail:<name> colours from style.DETAIL_COLORS), the eyeball's own
                        sclera / iris / pupil split by the same gradient as its shader (the eyeball is built only
                        inside its almond, so the white never shows outside the lids); 1 sample, box filter,
                        Standard view, transparent film; glass lenses hidden (the irises behind them count)
  DIR/ids/NAME.json     {"colors": {group: [r, g, b]}}
  DIR/ids/NAME_sig.png  the signature mask (the signature objects white, everything else a holdout)
  DIR/meta/NAME.json    projected landmarks in PNG px: eye_y, chin_y, crown_y, skyline_y, head_box, sig_box, h_px,
                        iris centres, eye openings (and the design opening), the eyes' almond outlines (eye_almond),
                        brow end points and the brows' gap to the calm lash line (brow_gap_H), mouth corners (and head-local, pose-free, in H:
                        mouth_local); the floating list and contact
                        report; the P-A8 detail thresholds; for glasses the iris contrast behind the lens; stats
--contacts: the BVH contact test of P-A7 — each attached part against its parent: the gap must be <= 0.01 H, a part
  on a surface is buried <= 0.04 H over <= 60 % of its points; "embed" parts (eyes, nose, ears, beards, glasses
  temples under the hair: inside their parent by design) are checked for the gap only;
  glasses rims and bridges are registered on what they rest on (nose or face), their pads on the nose. "free" parts
  (none in P1) are skipped.
--stats: triangles per object, build and render seconds.
build_regression (portrait_assets.py --selftest): build-only runs of every kit character with the open mouths and lid
  settings later steps need (§7.3 ranges, §7.9 moods) — fails on an exception, an open mouth without its lip, teeth
  or dark pocket, or a lens with no faces; prints the build notes (fallbacks the kit took).
"""
import copy
import json
import os
import time

import bpy
import numpy as np
from mathutils import Vector

from . import core, rig, style
from .core import H


# ------------------------------------------------------------------ contacts
def contacts(ctx, max_pts=900):
    """-> (floating names, report rows)."""
    rows, floating = [], []
    gap_max = style.STYLE["contact_gap"] * H
    bur = style.STYLE["contact_buried"] * H
    share = style.STYLE["contact_buried_share"]
    trees = {}
    for p in ctx.parts:
        if p.parent is None or p.kind in ("root", "free"):
            continue
        if p.obj.name not in bpy.context.scene.objects or p.parent.name not in bpy.context.scene.objects:
            continue
        if p.parent.name not in trees:
            try:
                trees[p.parent.name] = (core.bvh_of(p.parent), p.parent.matrix_world.copy())
            except Exception:
                continue
        tree, pmw = trees[p.parent.name]
        pinv = pmw.inverted()
        try:
            verts = core.eval_verts(p.obj, faces=True)
        except RuntimeError:
            continue
        if not verts:
            continue
        step = max(1, len(verts) // max_pts)
        ds = []
        for v in verts[::step]:
            lv = pinv @ v
            loc, nor, idx, dist = tree.find_nearest(lv)
            if loc is None:
                continue
            sign = 1.0 if (lv - loc).dot(nor) >= 0 else -1.0
            ds.append(sign * dist * pmw.to_scale()[0])
        if not ds:
            continue
        ds = np.array(ds)
        gap = float(ds.min())
        buried = float((ds < -bur).mean())
        ok_gap = gap <= gap_max
        ok_bur = p.kind == "embed" or buried <= share
        status = "ok" if ok_gap and ok_bur else ("FLOATING" if not ok_gap else "BURIED")
        rows.append(dict(part=p.obj.name, detail=p.detail, parent=p.parent.name, kind=p.kind, gap_H=round(gap / H, 4),
                         buried_share=round(buried, 3), status=status))
        if status != "ok":
            floating.append(p.obj.name)
    return floating, rows


# ------------------------------------------------------------------ ID pass
def _id_color(table, group):
    if group not in table:
        used = {tuple(v) for v in table.values()}
        pool = style.COSTUME_COLORS if group.startswith("costume:") else style.DETAIL_COLORS
        for c in pool + [(200, 200, 200)]:
            if c not in used:
                table[group] = c
                break
    return table[group]


def _flat(name, rgb8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = core.rgba("#%02x%02x%02x" % tuple(rgb8))
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m


def _eye_id(name, eye_mat, table):
    """The eyeball split into sclera / iris / pupil with the same gradient (constant stops) as its shader."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    src = eye_mat.node_tree.nodes["gaze"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = src.inputs["Scale"].default_value
    mp.inputs["Location"].default_value = src.inputs["Location"].default_value
    nt.links.new(tc.outputs["Object"], mp.inputs[0])
    g = nt.nodes.new("ShaderNodeTexGradient")
    g.gradient_type = "SPHERICAL"
    nt.links.new(mp.outputs[0], g.inputs[0])
    ri, rp = eye_mat["eye_ri"], eye_mat["eye_rp"]
    hx = lambda k: "#%02x%02x%02x" % tuple(_id_color(table, k))  # noqa: E731
    stops = [(0.0, hx("sclera")), (1 - ri, hx("iris")), (1 - rp, hx("pupil"))]
    ramp = core.node_ramp(nt, g.outputs["Fac"], stops, interp="CONSTANT")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ramp, em.inputs["Color"])
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m


def _skin_id(name, ctx, table):
    """Skin with its painted details (freckles) in their detail colours."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    col = core.rgba("#%02x%02x%02x" % tuple(_id_color(table, "skin")))
    base = None
    for nm, (pts, rad, colr, k) in ctx.skin_paint.items():
        acc = None
        for q in pts:
            bl = core.node_blob(nt, q, rad)
            acc = bl if acc is None else core.node_math(nt, "MAXIMUM", acc, bl)
        sharp = core.node_math(nt, "GREATER_THAN", acc, 0.35)
        dc = "#%02x%02x%02x" % tuple(_id_color(table, "detail:" + nm))
        base = core.node_mix(nt, sharp, base if base is not None else "#%02x%02x%02x" % tuple(_id_color(table, "skin")), dc)
    em = nt.nodes.new("ShaderNodeEmission")
    if base is None:
        em.inputs["Color"].default_value = col
    else:
        nt.links.new(base, em.inputs["Color"])
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m


def _flat_settings(size):
    sc = bpy.context.scene
    sc.cycles.samples = 1
    sc.cycles.use_adaptive_sampling = False
    sc.cycles.use_denoising = False
    sc.cycles.pixel_filter_type = "BOX"
    sc.cycles.filter_width = 0.01
    sc.cycles.max_bounces = 0
    sc.cycles.transparent_max_bounces = 8
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.film_transparent = True


def id_pass(ctx, path_png, path_json, path_sig, size):
    """Render the flat part-ID pass and the signature mask. Restores nothing: run it after the beauty render."""
    sc = bpy.context.scene
    _flat_settings(size)
    table = dict(style.ID_COLORS)
    for k in [k for k in table if k not in ("skin",)]:
        pass
    by_obj = {}
    for p in ctx.parts:
        by_obj[p.obj.name] = p.group
    cache = {}
    eyes = {e["obj"].name: e for e in ctx.objs["eyes"]}
    for o in sc.objects:
        if o.type not in ("MESH", "CURVE"):
            continue
        if o.get("kit_glass"):
            o.hide_render = True
            continue
        grp = by_obj.get(o.name, "costume")
        if o is ctx.objs.get("mouth_cutter"):
            # hidden, but its material is what the boolean transfers onto the pocket's walls: the "mouth" group
            grp = "mouth"
        if o.name in eyes:
            m = _eye_id("id_" + o.name, o.data.materials[0], table)
        elif grp == "skin" and o.name == "head":
            m = _skin_id("id_skin_head", ctx, table)
        else:
            if grp not in cache:
                cache[grp] = _flat("id_" + grp, _id_color(table, grp))
            m = cache[grp]
        n_slots = len(o.data.materials)
        o.data.materials.clear()
        o.data.materials.append(m)
        if o.name == "head" and n_slots > 1:
            # slot 1 of the head: an open mouth's pocket walls (face.carve_mouth transfers the dark interior onto
            # the cut), the "mouth" group
            if "mouth" not in cache:
                cache["mouth"] = _flat("id_mouth", _id_color(table, "mouth"))
            o.data.materials.append(cache["mouth"])
    for L in [o for o in sc.objects if o.type == "LIGHT"]:
        L.hide_render = True
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    sc.render.filepath = path_png
    bpy.ops.render.render(write_still=True)
    with open(path_json, "w") as f:
        json.dump({"colors": {k: list(v) for k, v in table.items()}}, f, indent=1)
    # the signature mask: signature objects white, everything else a holdout (alpha 0 where it hides them)
    hold = bpy.data.materials.new("id_holdout")
    hold.use_nodes = True
    nt = hold.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    ho = nt.nodes.new("ShaderNodeHoldout")
    nt.links.new(ho.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    white = _flat("id_sig", (255, 255, 255))
    sig = {o.name for o in ctx.sig_objs}
    for o in sc.objects:
        if o.type not in ("MESH", "CURVE") or o.hide_render:
            continue
        o.data.materials.clear()
        o.data.materials.append(white if o.name in sig else hold)
    sc.render.filepath = path_sig
    bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------------ landmarks
def landmarks_json(ctx, path, png_path, ids_png, sig_png, size, floating, rows, stats):
    from PIL import Image
    cam = ctx.objs["cam"]

    def pj(pt):
        q = rig.project(cam, [tuple(pt)], size)[0]
        return [round(float(q[0]), 1), round(float(q[1]), 1)]

    iris = [pj(p) for p in ctx.L["iris_world"]]
    order = sorted(range(len(iris)), key=lambda i: iris[i][0])     # near (screen left) first
    iris = [iris[i] for i in order]
    chin = pj(rig.head_to_world(ctx, ctx.L["chin"]))
    crown = pj(rig.head_to_world(ctx, ctx.L["crown"]))
    hp = rig.project(cam, rig.head_points(ctx), size)
    head_box = [float(hp[:, 0].min()), float(hp[:, 1].min()), float(hp[:, 0].max()), float(hp[:, 1].max())]
    a = np.asarray(Image.open(png_path).convert("RGBA"))[..., 3] > 127
    rows_a = np.where(a.sum(1) >= 2)[0]
    skyline = int(rows_a[0]) if len(rows_a) else None
    sig_box = None
    if sig_png and os.path.exists(sig_png):
        s = np.asarray(Image.open(sig_png).convert("RGBA"))[..., 3] > 127
        if s.any():
            ys, xs = np.nonzero(s)
            sig_box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    brows = []
    for tag in ("near", "far"):
        b = ctx.L.get("brow_" + tag)
        if b:
            brows.append([pj(rig.head_to_world(ctx, b[0])), pj(rig.head_to_world(ctx, b[1]))])
    mc = [pj(rig.head_to_world(ctx, q)) for q in ctx.L.get("mouth_corners", [])]
    mc.sort(key=lambda q: q[0])
    openings, sclera_full = [], []
    if ids_png and os.path.exists(ids_png):
        im = np.asarray(Image.open(ids_png).convert("RGB")).astype(int)
        eyecols = [np.array(style.ID_COLORS[k]) for k in ("sclera", "iris", "pupil", "catch")]
        mask = np.zeros(im.shape[:2], bool)
        for c in eyecols:
            mask |= (np.abs(im - c).sum(-1) < 30)
        cut = (iris[0][0] + iris[-1][0]) / 2 if len(iris) == 2 else size[0] / 2
        for side in (0, 1):
            m = mask.copy()
            if side == 0:
                m[:, int(cut):] = False
            else:
                m[:, :int(cut)] = False
            col = m.sum(0)
            openings.append(int(col.max()) if col.any() else 0)
    almonds = []
    for e in sorted(ctx.objs["eyes"], key=lambda e: e["side"]):
        rz = e["radii"][2]
        c = e["obj"].matrix_world.translation
        top = rig.project(cam, [tuple(c + Vector((0, 0, rz)))], size)[0][1]
        bot = rig.project(cam, [tuple(c - Vector((0, 0, rz)))], size)[0][1]
        sclera_full.append(round(float(abs(bot - top)), 1))
        if e.get("almond"):
            almonds.append([pj(rig.head_to_world(ctx, q)) for q in e["almond"]])
    h_px = abs(chin[1] - crown[1])
    # the mouth corners in head units (pose-free: the expression alone, for the mood check's pose-held delta)
    mouth_local = sorted([[round(q.x / H, 4), round(q.z / H, 4)] for q in ctx.L.get("mouth_corners", [])])
    meta = dict(name=os.path.splitext(os.path.basename(png_path))[0], size=list(size), cid=ctx.cid, mood=ctx.mood,
                era=ctx.era, eye_y=round(sum(p[1] for p in iris) / len(iris), 1), chin_y=chin[1], crown_y=crown[1],
                skyline_y=skyline, head_box=[round(v, 1) for v in head_box], sig_box=sig_box, h_px=round(h_px, 1),
                iris=iris, eye_open_px=openings, sclera_full_px=sorted(sclera_full),
                eye_open_H=[round(o / h_px, 3) for o in openings],
                sclera_vis_H=[round(o / h_px / max(0.05, e["open"] - e.get("low", 0.0)), 3) for o, e in
                              zip(openings, sorted(ctx.objs["eyes"], key=lambda e: e["side"]))],
                eye_design_H=[round(ctx.P["sclera_h"] / H * (e["open"] - e.get("low", 0.0)), 3) for e in
                              sorted(ctx.objs["eyes"], key=lambda e: e["side"])],
                eye_almond=almonds,
                brow_gap_H=[round(ctx.L[k], 4) for k in ("brow_gap_near", "brow_gap_far") if k in ctx.L],
                brows=brows, mouth=mc, mouth_local=mouth_local,
                cheek_near=pj(rig.head_to_world(ctx, ctx.L["cheek_near"])) if ctx.L.get("cheek_near") else None,
                mouth_open=bool(getattr(ctx, "mouth_open", False)), glasses=bool(getattr(ctx, "glasses", False)),
                signature=ctx.ch.get("signature", {}).get("name"), floating=floating, contacts=rows,
                details=ctx.details, frame=ctx.frame, stats=stats)
    if getattr(ctx, "lens_paths", None) and ids_png:
        r = lens_ratio(ctx.lens_paths, ids_png)
        if r is not None:
            meta["lens_iris_contrast"] = round(r, 3)
    with open(path, "w") as f:
        json.dump(meta, f, indent=1)
    return meta


# ------------------------------------------------------------------ lens contrast (glasses)
def lens_renders(ctx, size, tmpdir, samples=64, name=None):
    """§7.5: an iris behind a lens keeps >= 70 % of its contrast. Renders the eye region twice with a render border
    (lenses hidden / shown); `lens_ratio` compares them inside the ID pass's iris and sclera masks."""
    sc = bpy.context.scene
    cam = ctx.objs["cam"]
    lenses = [o for o in sc.objects if o.get("kit_glass")]
    if not lenses:
        return None
    pp = rig.project(cam, [tuple(p) for p in ctx.L["iris_world"]], size)
    x0, x1 = pp[:, 0].min() - 70, pp[:, 0].max() + 70
    y0, y1 = pp[:, 1].min() - 60, pp[:, 1].max() + 60
    sc.render.use_border = True
    sc.render.use_crop_to_border = False
    sc.render.border_min_x, sc.render.border_max_x = max(0, x0 / size[0]), min(1, x1 / size[0])
    sc.render.border_min_y, sc.render.border_max_y = max(0, 1 - y1 / size[1]), min(1, 1 - y0 / size[1])
    keep = sc.cycles.samples
    sc.cycles.samples = samples
    paths = []
    for vis in (False, True):
        for o in lenses:
            o.hide_render = not vis
        p = os.path.join(tmpdir, "%s_lens%d.png" % (name or ctx.cid, vis))
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    sc.render.use_border = False
    sc.cycles.samples = keep
    for o in lenses:
        o.hide_render = False
    return paths


def lens_ratio(paths, ids_png):
    """min over the eyes of |dL*(sclera, iris)| with the lens / without it, in the ID pass's masks."""
    from PIL import Image
    ids = np.asarray(Image.open(ids_png).convert("RGB")).astype(int)

    def mask(k):
        return np.abs(ids - np.array(style.ID_COLORS[k])).sum(-1) < 30

    iris, scl = mask("iris"), mask("sclera")

    def lab_l(path):
        rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255
        c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
        y = c @ np.array([0.2126, 0.7152, 0.0722])
        return np.where(y > 216 / 24389, 116 * np.cbrt(y) - 16, y * 24389 / 27)

    L0, L1 = lab_l(paths[0]), lab_l(paths[1])
    cols = np.nonzero((iris | scl).any(0))[0]
    if not len(cols):
        return None
    # split the two eyes at the widest gap between eye columns
    gaps = np.diff(cols)
    cut = cols[int(np.argmax(gaps))] + 1 if len(gaps) and gaps.max() > 3 else None
    ratios = []
    for part in ((slice(None, cut), slice(cut, None)) if cut is not None else (slice(None),)):
        im_, sm_ = iris.copy(), scl.copy()
        sel = np.zeros_like(iris)
        sel[:, part] = True
        im_ &= sel
        sm_ &= sel
        if im_.sum() < 6 or sm_.sum() < 6:
            continue
        c0 = abs(np.median(L0[sm_]) - np.median(L0[im_]))
        c1 = abs(np.median(L1[sm_]) - np.median(L1[im_]))
        ratios.append(c1 / max(c0, 1e-6))
    return float(min(ratios)) if ratios else None


# ------------------------------------------------------------------ stats
def stats(ctx):
    dg = bpy.context.evaluated_depsgraph_get()
    rows = []
    for o in bpy.context.scene.objects:
        if o.type in ("MESH", "CURVE") and not o.hide_render:
            ev = o.evaluated_get(dg)
            try:
                me = ev.to_mesh()
            except RuntimeError:
                continue
            me.calc_loop_triangles()
            rows.append((len(me.loop_triangles), o.name))
            ev.to_mesh_clear()
    rows.sort(reverse=True)
    return dict(objects=len(rows), triangles=sum(r[0] for r in rows), top=[[n, c] for c, n in rows[:10]],
                build_s=round(ctx.t_build, 2))


def now():
    return time.time()


# ------------------------------------------------------------------ build-only regression
REGRESSION_MOUTHS = [dict(type="open", w=0.32, h=0.12, near=0.04, far=0.03, dz=-0.012),   # the usual open smile
                     dict(type="open", w=0.38, h=0.14, near=0.05, far=0.04, dz=-0.012),   # the widest (§7.3)
                     dict(type="open", w=0.26, h=0.10, near=0.0, far=0.0, dz=-0.012),     # a small shout
                     dict(type="open", w=0.24, h=0.06, near=0.0, far=0.0)]                # barely open
REGRESSION_LIDS = [dict(open=0.30), dict(open=[0.42, 0.62]), dict(open=0.50, low=0.02), dict(open=0.85),
                   dict(open=0.62, low=0.24, bow=0.35)]


def build_regression(log=print):
    """Build (no render) every kit character calm and smile, then with each REGRESSION_MOUTHS open mouth and each
    REGRESSION_LIDS lid setting as its smile; True when every build passes."""
    from . import build, chars
    ok = True
    for cid in sorted(chars.KIT_IDS):
        runs = [("calm", None), ("smile", None)]
        runs += [("smile", ("mouth", m)) for m in REGRESSION_MOUTHS]
        runs += [("smile", ("eyes", e)) for e in REGRESSION_LIDS]
        for mood, patch in runs:
            saved = copy.deepcopy(chars.CHARS[cid])
            label = "%s %s %s" % (cid, mood, "" if patch is None else "%s=%s" % (patch[0], patch[1]))
            try:
                if patch is not None:
                    chars.CHARS[cid][patch[0]]["smile"] = dict(patch[1])
                ctx = build(cid, mood, log=lambda *a: None)
                errs = []
                if getattr(ctx, "mouth_open", False):
                    lip = bpy.data.objects.get("lip_low")
                    if lip is None or len(lip.data.splines[0].points) < 3:
                        errs.append("no lower lip")
                    if bpy.data.objects.get("teeth") is None:
                        errs.append("no teeth")
                    dg = bpy.context.evaluated_depsgraph_get()
                    head = ctx.objs["head"].evaluated_get(dg)
                    me = head.to_mesh()
                    if not any(pl.material_index == 1 for pl in me.polygons):
                        errs.append("no dark pocket")
                    head.to_mesh_clear()
                for e in ctx.objs["eyes"]:
                    if not e["obj"].data.polygons:
                        errs.append("empty lens " + e["tag"])
                if errs:
                    ok = False
                log("%s %s%s%s" % ("FAIL" if errs else "ok  ", label, (" — " + ", ".join(errs)) if errs else "",
                                   "".join("\n      note: " + n for n in ctx.notes)))
            except Exception as ex:  # noqa: BLE001  (report every failure, keep going)
                ok = False
                log("FAIL %s — %s: %s" % (label, type(ex).__name__, ex))
            finally:
                chars.CHARS[cid] = saved
    log("REGRESSION %s" % ("PASS" if ok else "FAIL"))
    return ok
