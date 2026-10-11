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


## Hidden in the renderer only (a hidden node would move its container's other children); the count with it shown
## is taken again right before (toasts and the like come and go while the probe runs).
static func _cost(vp: Viewport, item: CanvasItem, _base: int) -> int:
	var rid := item.get_canvas_item()
	var on := await _draws(vp)
	RenderingServer.canvas_item_set_visible(rid, false)
	var d := await _draws(vp)
	RenderingServer.canvas_item_set_visible(rid, item.visible and not bool(item.get_meta("kit_culled", false)))
	return on - d


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
	# the kit's bakes still landing (ui_kit.gd KitBake) would shrink the count while it measures: wait until the bake
	# queue is idle and the count holds (at most ~10 s)
	var kb0 := vp.get_node_or_null("KitBake")
	var last := -1
	for i in 40:
		var d0 := await _draws(vp)
		var idle: bool = kb0 == null or (kb0.jobs.is_empty() and int(kb0._state) == 0)
		if d0 == last and idle:
			break
		last = d0
		await tree.create_timer(0.25).timeout
	var live: Array = []  # kit labels drawing their own glyphs now (not from the bake atlas)
	_live_labels(vp, live)
	lines.append("live kit labels: %d  %s" % [live.size(), ", ".join(live.slice(0, 40))])
	var kbd := vp.get_node_or_null("KitBake")
	if kbd != null and not live.is_empty():  # why: are their bakes there, queued, waited for, held?
		var nodes: Array = []
		_live_nodes(vp, nodes)
		var kit: Script = load("res://scripts/ui_kit.gd")
		for l in nodes.slice(0, 6):
			var key: String = "text|" + String(kit.label_key(l))
			var in_slots: int = kbd.slots.keys().filter(func(x): return String(x).begins_with(key)).size()
			var in_jobs: int = kbd.jobs.keys().filter(func(x): return String(x).begins_with(key)).size()
			var in_wait: int = kbd.waiting.keys().filter(func(x): return String(x).begins_with(key)).size()
			var seen: Variant = kbd.seen.get(key)
			var t: Node = l.get_node("KitText")
			lines.append("  «%s»: baked %d queued %d waited %d seen %s now %d armed %s" % [l.text, in_slots, in_jobs, in_wait,
				str(seen), Time.get_ticks_msec(), str(t.get("_armed"))])
		lines.append("  bake: baked=%d queued=%d waiting=%d state=%d seen=%d" % [kbd.slots.size(), kbd.jobs.size(),
			kbd.waiting.size(), kbd._state, kbd.seen.size()])
	tree.paused = true  # the game holds still while it measures (the HUD's own drawing does not depend on it)
	if OS.get_cmdline_user_args().has("--perf-stale"):  # which items draw less once redrawn (missed bake news)
		vp.disable_3d = true
		var roots0: Array = []
		_roots(vp, roots0)
		for r in roots0:
			await _stale(vp, r, 1, lines)
		vp.disable_3d = false
	var with_3d := await _draws(vp)
	# what a full redraw gives (every canvas item drawn again now): equal to the count above unless something drew
	# before its bake landed and was not told
	vp.propagate_call("queue_redraw")
	await _draws(vp)
	var redrawn := await _draws(vp)
	vp.disable_3d = true
	var base := await _draws(vp)
	lines.append("base draws_canvas=%d (with the 3D world on: %d; before a full redraw: %d)" % [base, with_3d, with_3d])
	if redrawn != with_3d:
		lines.append("NOTE: a full redraw changed the count %d -> %d" % [with_3d, redrawn])
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
			var on := await _draws(vp)
			(l as CanvasLayer).visible = false
			lc = on - await _draws(vp)
			(l as CanvasLayer).visible = true
			await _draws(vp)  # (shown again, its items draw anew)
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
	var kb := vp.get_node_or_null("KitBake")  # the kit's bake atlas (ui_kit.gd KitBake)
	if kb != null:
		lines.append("kit bake: k=%.3f atlas=%s baked=%d queued=%d not-baked=%d waiting=%d icons=%d resets=%d state=%d shelf=%s" % [
			kb.k, kb._asize, kb.slots.size(), kb.jobs.size(), kb.never.size(), kb.waiting.size(), kb.icons.size(), kb.resets,
			kb._state, kb._shelf])
	vp.disable_3d = false
	tree.paused = false
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	if f != null:
		f.store_string("\n".join(lines) + "\n")
	for ln in lines:
		print("perf-tree ", ln)


## Redraws each visible canvas item alone and reports those that then draw less (they missed the news that their
## bake had landed).
static func _stale(vp: Viewport, item: Node, depth: int, lines: PackedStringArray) -> void:
	if item is SubViewport or (item is CanvasItem and not (item as CanvasItem).visible):
		return
	if item is CanvasItem:
		var before := await _draws(vp)
		(item as CanvasItem).queue_redraw()
		var after := await _draws(vp)
		if before != after:
			lines.append("STALE %+d  %s" % [after - before, _label(item)])
	for c in item.get_children():
		await _stale(vp, c, depth + 1, lines)


static func _live_labels(n: Node, out: Array) -> void:
	for c in n.get_children():
		if c is SubViewport:
			continue
		if c is Label and (c as Label).is_visible_in_tree() and c.get_node_or_null("KitText") != null \
				and (c as Label).visible_characters != 0:
			out.append("«%s» %s" % [(c as Label).text.replace("\n", " "), _path(c).get_file()])
		_live_labels(c, out)


static func _live_nodes(n: Node, out: Array) -> void:
	for c in n.get_children():
		if c is SubViewport:
			continue
		if c is Label and (c as Label).is_visible_in_tree() and c.get_node_or_null("KitText") != null \
				and (c as Label).visible_characters != 0 and (c as Label).text.strip_edges() != "":
			out.append(c)
		_live_nodes(c, out)


static func _find_subviewports(n: Node, out: Array) -> void:
	for c in n.get_children():
		if c is SubViewport:
			out.append(c)
		_find_subviewports(c, out)
