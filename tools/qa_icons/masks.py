"""ID passes for C-5 of docs/art_direction.md §7.14: which pixels of an icon are its lock, its dark iron, its crates.

Run (bpy as a Python module): python3 tools/qa_icons/masks.py OUT_DIR [names ...]
(default names: chest_wood chest_silver chest_royal chest_cards crate gift)

Builds each icon with tools/blender/icon_assets.py (read-only), frames it with the icon's own camera and renders flat
emission colours at the raw size (256) instead of the materials:
- OUT_DIR/<name>_ids.png    red = the lock (parts named lock*, keyhole*, keyslot*, hole*, slot*, gem*), green = dark
                            iron (materials named iron*), blue = everything else;
- OUT_DIR/<name>_units.png  (only when parts carry o["unit"], the crate's boxes) unit 0 red, 1 green, 2 blue.
The masks match the shipped icon pixel for pixel before its 256 → 128 downscale and ink rim (chest_qa.py --masks=DIR).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "blender"))
sys.path.insert(0, HERE)
import bpy  # noqa: E402

from measure_lean import build, camera  # noqa: E402  (imports tools/blender/icon_assets)

LOCK = ("lock", "keyhole", "keyslot", "hole", "slot", "gem")
DEFAULT = ["chest_wood", "chest_silver", "chest_royal", "chest_cards", "crate", "gift"]


def flat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*rgb, 1)
    e.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    return m


def paint(classify):
    cache = {}
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        rgb = classify(o)
        if rgb not in cache:
            cache[rgb] = flat("id%s" % (rgb,), rgb)
        o.data.materials.clear()
        o.data.materials.append(cache[rgb])
        for p in o.data.polygons:
            p.material_index = 0


def shoot(path):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 16
    sc.cycles.seed = 0
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.world = None
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def part_class(o):
    if o.name.split(".")[0].startswith(LOCK):
        return (1.0, 0.0, 0.0)
    if any(m and m.name.startswith("iron") for m in o.data.materials):
        return (0.0, 1.0, 0.0)
    return (0.0, 0.0, 1.0)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out, names = os.path.abspath(args[0]), args[1:] or DEFAULT
    os.makedirs(out, exist_ok=True)
    for n in names:
        build(n)
        camera(n)
        has_units = any(o.get("unit") is not None for o in bpy.context.scene.objects)
        paint(part_class)
        shoot(os.path.join(out, n + "_ids.png"))
        if has_units:
            colours = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
            build(n)
            camera(n)
            paint(lambda o: colours[int(o.get("unit", 0)) % 3])
            shoot(os.path.join(out, n + "_units.png"))
        print("MASK", n, flush=True)


if __name__ == "__main__":
    main()
