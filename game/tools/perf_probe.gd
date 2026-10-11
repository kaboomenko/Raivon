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


## KitBake's state in one line: the canvas scale, the atlas, its images (baked, queued, not baked, waited for), the
## icons in it, resets and dropped images, and how full it is (in use / the skyline's top).
static func bake_stats(kb: Node) -> String:
	if kb == null:
		return "no kit bake"
	var icons_in := 0
	for path in kb.icons:
		if (kb.icons[path][2] as Rect2i).size.x > 0:
			icons_in += 1
	return "k=%.3f atlas=%s baked=%d queued=%d not-baked=%d waiting=%d icons=%d/%d resets=%d evicted=%d used=%.0f%% top=%d stage=%s state=%d" % [
		kb.k, kb._asize, kb.slots.size(), kb.jobs.size(), kb.never.size(), kb.waiting.size(), icons_in, kb.icons.size(),
		kb.resets, kb.evicted, kb.used() * 100.0, kb._top, kb.stage.size, kb._state]


static func run(tree: SceneTree, out_path: String) -> void:
	var vp := tree.root
	var lines := PackedStringArray()
	if OS.get_cmdline_user_args().has("--perf-smoke"):
		await smoke(tree, out_path)
		return
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
		lines.append("kit bake: %s" % bake_stats(kb))
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


# ------------------------------------------------------------------ --perf-smoke: the HUD while it moves

static var _rounds := 0
static var _was := 0


static func _frame(vp: Viewport, kb: Node) -> int:
	await RenderingServer.frame_post_draw
	if kb != null:
		if int(kb._state) == 1 and _was != 1:
			_rounds += 1
		_was = int(kb._state)
	return vp.get_render_info(Viewport.RENDER_INFO_TYPE_CANVAS, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)


static func _settle(tree: SceneTree, vp: Viewport, kb: Node) -> int:
	var last := -1
	var d := 0
	for i in 60:
		d = await _frame(vp, kb)
		d = await _frame(vp, kb)
		var idle: bool = kb == null or (kb.jobs.is_empty() and int(kb._state) == 0 and kb._moving.is_empty())
		if d == last and idle:
			break
		last = d
		await tree.create_timer(0.25).timeout
	return d


static func _spread(a: Array) -> String:
	a.sort()
	return "frames=%d min=%d median=%d p90=%d max=%d" % [a.size(), a[0], a[a.size() / 2], a[int(a.size() * 0.9)], a[-1]]


## Smoke test of what a still shot does not show (docs/dev/hud_perf_plan.json H1 review): the card row scrolled
## (each card culled exactly when it is out of the row's clip, checked against where it is drawn; the scrolled row's
## pictures after it has held still, <shot>_s37.png / _s111.png, for tools/hud_diff.py against another build), then
## the camera panned and zoomed (the canvas draws per frame, bake rounds, resets, the atlas filling). Prints
## «perf-tree smoke» lines; FAIL lines name what went wrong.
static func smoke(tree: SceneTree, out_path: String) -> void:
	var vp := tree.root
	var kb := vp.get_node_or_null("KitBake")
	var main: Node = tree.current_scene
	var args := OS.get_cmdline_user_args()
	var no3d := args.has("--hud-only")
	vp.disable_3d = no3d
	var p := func(s: String) -> void: print("perf-tree smoke ", s)
	p.call("settled: draws=%d %s" % [await _settle(tree, vp, kb), bake_stats(kb)])
	var fails := 0
	# 1. the card row: culled where it is out of the clip, drawn where it is in
	var sc: ScrollContainer = main.ui.get("_bscroll")
	var row: Container = main.ui.get("_brow")
	if sc != null and row != null and sc.is_visible_in_tree():
		var hb := sc.get_h_scroll_bar()
		p.call("row: cards=%d max=%.0f page=%.0f" % [row.get_child_count(), hb.max_value, hb.page])
		for v in [0.0, 37.0, 150.0, 400.0, 0.0, 60.0, 2000.0, 0.0]:
			hb.value = v
			for i in 3:
				await _frame(vp, kb)
			var view := sc.get_global_rect()
			var bad := PackedStringArray()
			var st := PackedStringArray()
			for c in row.get_children():
				var card := c as Control
				var r := card.get_global_rect()
				var on := card.visible and r.end.x > view.position.x and r.position.x < view.end.x
				var culled := bool(card.get_meta("kit_culled", false))
				st.append("%d..%d%s" % [r.position.x, r.end.x, "C" if culled else ""])
				if on == culled:
					bad.append("%s %d..%d %s" % [card.name, r.position.x, r.end.x, "culled in view" if on else "drawn out of view"])
			p.call("scroll %.0f (now %.0f): %s%s" % [v, hb.value, " ".join(st), ("  FAIL " + ", ".join(bad)) if not bad.is_empty() else ""])
			fails += bad.size()
		# the row held still after a scroll: its images at the new sub-pixel offsets (and the canvas without the world)
		var b0: int = kb.slots.size() if kb != null else 0
		var e0: int = kb.evicted if kb != null else 0
		vp.disable_3d = true
		for v in [37.0, 111.0]:
			hb.value = v
			if kb != null:  # every owner's place looked at (KitBake polls POLL_N a frame), then SETTLE_MS of stillness
				for i in kb.placed.size() / kb.POLL_N + 3:
					await _frame(vp, kb)
				await tree.create_timer(kb.SETTLE_MS / 1000.0 + 0.1).timeout
			var d := await _settle(tree, vp, kb)
			await _frame(vp, kb)
			vp.get_texture().get_image().save_png(out_path.trim_suffix(".tree.txt").get_basename() + "_s%d.png" % int(v))
			p.call("scrolled %.0f, held: draws=%d baked+%d evicted+%d %s" % [v, d, (kb.slots.size() - b0) if kb else 0,
				(kb.evicted - e0) if kb else 0, bake_stats(kb)])
			# the same frame with the bake off (every kit look drawn as its vectors): tools/hud_diff.py compares the
			# two — what the atlas shows against what it stands for, in this very layout
			if kb != null:
				var kit: Script = load("res://scripts/ui_kit.gd")
				kit.KitBake.off = true
				vp.propagate_call("queue_redraw")
				for i in 3:
					await _frame(vp, kb)
				vp.get_texture().get_image().save_png(out_path.trim_suffix(".tree.txt").get_basename() + "_s%d_vec.png" % int(v))
				kit.KitBake.off = false
				vp.propagate_call("queue_redraw")
				await _settle(tree, vp, kb)
		hb.value = 0.0
		vp.disable_3d = no3d
		await _settle(tree, vp, kb)
	else:
		p.call("row: not shown")
	# 2. the camera panned, then panned and zoomed: the HUD's canvas draws stay flat, no bake churn
	var rig: Node3D = main.get("rig")
	if rig != null:
		var c0: Vector3 = rig.target
		var z0: float = rig.zoom_target
		var n := 0
		for phase in ["pan 15s", "pan+zoom 20s"]:
			var a: Array = []
			var r0 := _rounds
			var res0: int = kb.resets if kb else 0
			var t0 := Time.get_ticks_msec()
			var ms := 15000 if phase == "pan 15s" else 20000
			while Time.get_ticks_msec() - t0 < ms:
				n += 1
				var t := n * 0.03
				rig.target = c0 + Vector3(sin(t) * 2.5, 0, cos(t * (1.0 if phase == "pan 15s" else 0.7)) * 2.5 - 2.5)
				if phase != "pan 15s":
					rig.zoom_target = clampf(0.55 + 0.4 * sin(t * 0.37), 0.1, 1.0)
				a.append(await _frame(vp, kb))
			var resets: int = (kb.resets - res0) if kb else 0
			p.call("%s: %s rounds+%d resets+%d %s" % [phase, _spread(a), _rounds - r0, resets, bake_stats(kb)])
			if resets > 0:
				p.call("FAIL the atlas started over while panning")
				fails += 1
		rig.target = c0
		rig.zoom_target = z0
		await tree.create_timer(1.0).timeout
		p.call("after pan, settled: draws=%d %s" % [await _settle(tree, vp, kb), bake_stats(kb)])
	# 3. which looks fill the atlas
	if kb != null:
		var hist := {}
		for key in kb.slots:
			var s0 := String(key)
			var pre := s0.substr(0, s0.find("@")) if s0.find("@") > 0 else s0
			if pre.begins_with("text|"):
				pre = "text"
			hist[pre] = int(hist.get(pre, 0)) + 1
		var keys := hist.keys()
		keys.sort_custom(func(x, y): return hist[x] > hist[y])
		for key in keys.slice(0, 6):
			p.call("looks x%d  %s" % [hist[key], String(key).substr(0, 100)])
	vp.disable_3d = false
	p.call("done fails=%d %s" % [fails, bake_stats(kb)])

