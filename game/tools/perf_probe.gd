extends RefCounted
## Canvas draw-call probe (docs/dev/hud_perf_plan.json H1). For the current frame it hides every canvas subtree in
## turn — each CanvasLayer, the top-level canvas items under it, then the children of the costly ones — for a frame,
## and reports how many canvas draw calls (Viewport.get_render_info(CANVAS, DRAW_CALLS_IN_FRAME)) the subtree costs.
## It also lists the SubViewports with their own draws. main._shot runs it with the user argument `--perf-tree`
## (after the screenshot is saved); tools/godot_shot.sh prints its «perf-tree» lines, and the table is written next
## to the screenshot as <shot>.tree.txt. The 3D world is switched off while it measures (canvas draws do not depend
## on it, and frames are much faster without it); the first two lines show the base with and without it.

const MIN_DEPTH_COST := 12  ## a subtree that costs at least this many draws is opened one level deeper
const MAX_DEPTH := 9


static func _draws(vp: Viewport) -> int:
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	return vp.get_render_info(Viewport.RENDER_INFO_TYPE_CANVAS, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)


static func _path(n: Node) -> String:
	var parts := PackedStringArray()
	var c := n
	while c != null and c.get_parent() != null:
		parts.insert(0, String(c.name))
		c = c.get_parent()
		if c is Window:
			break
	return "/".join(parts)


static func _label(n: Node) -> String:
	var s := "%s (%s)" % [_path(n), n.get_class()]
	if n is Control:
		var r := (n as Control).get_global_rect()
		s += " @%d,%d %dx%d" % [r.position.x, r.position.y, r.size.x, r.size.y]
	return s


## The canvas items whose parent is not a canvas item (the roots of the canvas trees), grouped by their layer.
static func _roots(n: Node, out: Array) -> void:
	for c in n.get_children():
		if c is SubViewport:
			continue  # its own canvas
		if c is CanvasItem and not (n is CanvasItem):
			out.append(c)
		else:
			_roots(c, out)


static func _layer_of(n: Node) -> CanvasLayer:
	var c := n.get_parent()
	while c != null:
		if c is CanvasLayer:
			return c
		if c is Viewport:
			return null
		c = c.get_parent()
	return null


## Hidden in the renderer only (a hidden node would move its container's other children).
static func _cost(vp: Viewport, item: CanvasItem, base: int) -> int:
	var rid := item.get_canvas_item()
	RenderingServer.canvas_item_set_visible(rid, false)
	var d := await _draws(vp)
	RenderingServer.canvas_item_set_visible(rid, item.visible and not bool(item.get_meta("kit_culled", false)))
	return base - d


static func _walk(vp: Viewport, item: CanvasItem, base: int, depth: int, lines: PackedStringArray) -> void:
	var kids: Array = []
	for c in item.get_children():
		if c is CanvasItem and (c as CanvasItem).visible and not bool(c.get_meta("kit_culled", false)):
			kids.append(c)
	var rows: Array = []
	for c in kids:
		rows.append([await _cost(vp, c, base), c])
	rows.sort_custom(func(a, b): return a[0] > b[0])
	var rest := 0
	var rest_n := 0
	for r in rows:
		if int(r[0]) < 3 and depth > 1:
			rest += int(r[0])
			rest_n += 1
			continue
		lines.append("%s%4d  %s" % ["  ".repeat(depth), int(r[0]), _label(r[1])])
		if int(r[0]) >= MIN_DEPTH_COST and depth < MAX_DEPTH:
			await _walk(vp, r[1], base, depth + 1, lines)
	if rest_n > 0:
		lines.append("%s%4d  (%d more items under 3 draws each)" % ["  ".repeat(depth), rest, rest_n])


static func run(tree: SceneTree, out_path: String) -> void:
	var vp := tree.root
	var lines := PackedStringArray()
	var with_3d := await _draws(vp)
	vp.disable_3d = true
	var base := await _draws(vp)
	lines.append("base draws_canvas=%d (with the 3D world on: %d)" % [base, with_3d])
	var roots: Array = []
	_roots(vp, roots)
	var layers := {}  # CanvasLayer (or null: the root canvas) -> [items]
	for r in roots:
		var l := _layer_of(r)
		if not layers.has(l):
			layers[l] = []
		layers[l].append(r)
	var order := layers.keys()
	order.sort_custom(func(a, b): return (a.layer if a != null else 0) < (b.layer if b != null else 0))
	for l in order:
		var lc := 0
		if l != null:
			if not (l as CanvasLayer).visible:
				continue
			(l as CanvasLayer).visible = false
			lc = base - await _draws(vp)
			(l as CanvasLayer).visible = true
		lines.append("%4d  LAYER %s layer=%d" % [lc, _path(l) if l != null else "(root canvas)", l.layer if l != null else 0])
		var rows: Array = []
		for item in layers[l]:
			if (item as CanvasItem).visible:
				rows.append([await _cost(vp, item, base), item])
		rows.sort_custom(func(a, b): return a[0] > b[0])
		for r in rows:
			lines.append("  %4d  %s" % [int(r[0]), _label(r[1])])
			if int(r[0]) >= MIN_DEPTH_COST:
				await _walk(vp, r[1], base, 2, lines)
	# the SubViewports (minimap, portraits, card art, flags): their size, update mode and own draws
	var subs: Array = []
	_find_subviewports(vp, subs)
	lines.append("subviewports: %d" % subs.size())
	for s in subs:
		var sv := s as SubViewport
		lines.append("  %s size=%s update=%d canvas=%d visible=%d" % [_path(sv), sv.size, sv.render_target_update_mode,
			sv.get_render_info(Viewport.RENDER_INFO_TYPE_CANVAS, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME),
			sv.get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)])
	vp.disable_3d = false
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	if f != null:
		f.store_string("\n".join(lines) + "\n")
	for ln in lines:
		print("perf-tree ", ln)


static func _find_subviewports(n: Node, out: Array) -> void:
	for c in n.get_children():
		if c is SubViewport:
			out.append(c)
		_find_subviewports(c, out)
