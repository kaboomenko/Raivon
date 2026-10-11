"""Portrait kit v2 (docs/art_direction.md §7.5): commander, AI-leader and ruler busts built from character data.

Modules: style (the §7.3–7.4 numbers), core (materials, rays, curves, metaballs, lofts, shells), head (cages and
landmarks), face (eyes, lids, brows, nose, ears, mouths, marks, skin paint), hair, beard, body, garments, headgear,
props, rig (pose, gaze, light, camera and framing, render), chars (the characters as data, the signature registry
and its lint), qa (ID pass, landmark JSON, contacts, stats). The entry point stays tools/blender/portrait_assets.py
(its CLI and the three regeneration commands of its docstring are unchanged); `build` / `render_id` are what it calls
for the ids in chars.KIT_IDS.

Build order of one portrait (§7.5): head cage + brushes (the mood's cheek lift) -> landmarks -> skin paint ->
mouth boolean (open mouths) -> nose, ears, eyes + lids + lashes, brows, mouth, scar -> hair -> headgear -> beard ->
torso + arms -> costume layers -> braid (lies on the costume) -> props -> pose -> light, camera, framing -> gaze and
catchlights -> render -> (sidecars) lens contrast, contacts, ID pass + signature mask, landmark JSON.
"""
import os
import time

import bpy  # noqa: F401  (bpy before bmesh, everywhere in the kit)

from . import beard, body, chars, core, face, garments, hair, head, headgear, props, qa, rig, style  # noqa: F401


def supports(cid, era=1):
    return cid in chars.KIT_IDS and era in chars.KIT_ERAS.get(cid, ())


def build(cid, mood="calm", era=1, log=print):
    """Build one portrait's scene (the factory scene is reset first). Returns the context."""
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    chars.lint()
    ch = chars.CHARS[cid]
    ctx = core.Ctx(cid, ch, mood, era)
    ctx.t0 = t0
    h = head.build_head(ctx, None)
    head.landmarks(ctx)
    face.plan_skin_paint(ctx)
    face.add_freckles(ctx)
    core.set_mat(h, face.skin_mat(ctx))
    face.carve_mouth(ctx)
    core.update()
    face.build_nose(ctx)
    face.build_ears(ctx)
    face.build_eyes(ctx)
    face.build_brows(ctx)
    face.build_mouth(ctx)
    face.build_scar(ctx)
    core.update()
    hair.build_hair(ctx)
    headgear.build_headgear(ctx)
    beard.build_beard(ctx)
    base = garments.base_materials(ctx)
    body.build_body(ctx, base)
    garments.build_layers(ctx)
    hair.build_braid(ctx)
    props.build_props(ctx)
    core.update()
    rig.pose(ctx)
    rig.light_rig()
    rig.camera(ctx)
    ctx.t_build = time.time() - t0
    return ctx


def render_id(cid, out_png, mood="calm", era=1, size=(512, 588), samples=64, frame="bust", sidecars=None,
              contacts=False, want_stats=False, log=print):
    """Build and render one portrait to out_png; with `sidecars` (a folder) also the ID pass, the signature mask
    and the landmark JSON (P-A3/P-A5/P-A6/P-A7 inputs). Returns a dict with the frame, stats and timings."""
    ctx = build(cid, mood, era, log)
    rig.solve_frame(ctx, size, frame, log)
    rig.solve_gaze(ctx)
    rig.setup_render(size, samples)
    st = qa.stats(ctx) if (want_stats or sidecars) else None
    t_render = rig.render(out_png)
    if st is not None:
        st["render_s"] = round(t_render, 2)
        st["samples"] = samples
    floating, rows = ([], [])
    if contacts or sidecars:
        floating, rows = qa.contacts(ctx)
    name = os.path.splitext(os.path.basename(out_png))[0]
    meta = None
    if sidecars:
        os.makedirs(os.path.join(sidecars, "ids"), exist_ok=True)
        os.makedirs(os.path.join(sidecars, "meta"), exist_ok=True)
        if getattr(ctx, "glasses", False):
            ctx.lens_paths = qa.lens_renders(ctx, size, os.path.join(sidecars, "ids"), name=name)
        ids_png = os.path.join(sidecars, "ids", name + ".png")
        sig_png = os.path.join(sidecars, "ids", name + "_sig.png")
        qa.id_pass(ctx, ids_png, os.path.join(sidecars, "ids", name + ".json"), sig_png, size)
        meta = qa.landmarks_json(ctx, os.path.join(sidecars, "meta", name + ".json"), out_png, ids_png, sig_png, size,
                                 floating, rows, st)
    return dict(frame=ctx.frame, stats=st, floating=floating, contacts=rows, render_s=t_render, build_s=ctx.t_build,
                meta=meta, notes=ctx.notes)
