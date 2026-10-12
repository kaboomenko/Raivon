extends RefCounted
## Canvas draw-call probe (docs/dev/hud_perf_plan.json H1). For the current frame it hides every canvas subtree in
## turn — each CanvasLayer, the top-level canvas items under it, then the children of the costly ones — for a frame,
## and reports how many canvas draw calls (Viewport.get_render_info(CANVAS, DRAW_CALLS_IN_FRAME)) the subtree costs.
## It also lists the SubViewports with their own draws. main._shot runs it with the user argument `--perf-tree`
## (after the screenshot is saved); tools/godot_shot.sh prints its «perf-tree» lines, and the table is written next
## to the screenshot as <shot>.tree.txt. The 3D world is switched off while it measures (canvas draws do not depend
## on it, and frames are much faster without it); the first two lines show the base with and without it.

const MIN_DEPTH_COST := 12  ## a subtree that costs at least this many draws is opened one level deeper
## `--perf-deep=N`: open subtrees from N draws instead (a finer breakdown)
static var min_cost := MIN_DEPTH_COST
const MAX_DEPTH := 14


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
		if int(r[0]) >= min_cost and depth < MAX_DEPTH:
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
	var deferred: Variant = kb.get("_defer")  # (images waiting for a piece of a fragmented atlas; an older kit has none)
	return "k=%.3f atlas=%s baked=%d queued=%d deferred=%d not-baked=%d waiting=%d icons=%d/%d resets=%d evicted=%d used=%.0f%% top=%d stage=%s state=%d" % [
		kb.k, kb._asize, kb.slots.size(), kb.jobs.size(), (deferred as Dictionary).size() if deferred is Dictionary else 0,
		kb.never.size(), kb.waiting.size(), icons_in, kb.icons.size(),
		kb.resets, kb.evicted, kb.used() * 100.0, kb._top, kb.stage.size, kb._state]


## What the atlas holds, by look (the key's kind: text, flat, decor, shape, still, …): images and share of the atlas,
## then the largest images.
static func census(kb: Node) -> String:
	var by := {}
	var big: Array = []
	var area := float(kb._asize.x * kb._asize.y)
	for key in kb.slots:
		var s0 := String(key)
		var kind := s0.get_slice("|", 0)
		var r: Rect2i = kb.slots[key]
		var e: Array = by.get(kind, [0, 0])
		e[0] += 1
		e[1] += r.get_area()
		by[kind] = e
		big.append([r.get_area(), "%dx%d %s" % [r.size.x, r.size.y, s0.substr(0, 60).replace("\n", " ")]])
	var kinds := by.keys()
	kinds.sort_custom(func(a, b): return by[a][1] > by[b][1])
	var out := PackedStringArray()
	for k_ in kinds:
		out.append("%s %d %.1f%%" % [k_, by[k_][0], by[k_][1] * 100.0 / area])
	big.sort_custom(func(a, b): return a[0] > b[0])
	var tops := PackedStringArray()
	for b in big.slice(0, 6):
		tops.append(String(b[1]))
	return "%s; icons %d %.1f%%; largest: %s" % [", ".join(out), kb.icons.size(),
		kb.icons.size() * 132.0 * 132.0 * 100.0 / area, " | ".join(tops)]


## `--perf-tabs` (docs/dev/hud_perf_plan.json H2): the store's other tabs in turn — each one rendered, held still,
## shot (<shot>_<tab>.png, with the 3D world), its «perf» line printed and its breakdown written
## (<shot>_<tab>.png.tree.txt).
static func shop_tabs(tree: SceneTree, out_path: String) -> void:
	var vp := tree.root
	var main: Node = tree.current_scene
	var shop: Control = main.get("shop") if main != null else null
	if shop == null or not is_instance_valid(shop):
		print("perf-tree no store open")
		return
	var base := out_path.trim_suffix(".tree.txt").get_basename()
	for t in shop.get("TABS"):
		if String(t) == String(shop.get("tab")):
			continue
		shop.set("tab", t)
		shop.call("_render")
		var kb := vp.get_node_or_null("KitBake")
		var last := -1
		for i in 40:  # (its bakes landing, then the count holding)
			var d0 := await _draws(vp)
			var idle: bool = kb == null or (kb.jobs.is_empty() and int(kb._state) == 0)
			if d0 == last and idle and i > 2:
				break
			last = d0
			await tree.create_timer(0.25).timeout
		await RenderingServer.frame_post_draw
		var png := "%s_%s.png" % [base, t]
		vp.get_texture().get_image().save_png(png)
		print("perf tab=%s draw_calls=%d draws_3d=%d draws_shadow=%d draws_canvas=%d" % [t,
			Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
			vp.get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME),
			vp.get_render_info(Viewport.RENDER_INFO_TYPE_SHADOW, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME),
			vp.get_render_info(Viewport.RENDER_INFO_TYPE_CANVAS, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)])
		print("shot saved ", png)
		await run(tree, png + ".tree.txt", false)


static func run(tree: SceneTree, out_path: String, tabs := true) -> void:
	var vp := tree.root
	var lines := PackedStringArray()
	if OS.get_cmdline_user_args().has("--perf-smoke"):
		await smoke(tree, out_path)
		return
	if tabs and OS.get_cmdline_user_args().has("--perf-late"):
		await late(tree, out_path)
	if OS.get_cmdline_user_args().has("--perf-trans"):
		await trans(tree, out_path)
		return
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--perf-deep="):
			min_cost = maxi(2, int(a.get_slice("=", 1)))
	if tabs and OS.get_cmdline_user_args().has("--perf-tabs"):
		await run(tree, out_path, false)
		await shop_tabs(tree, out_path)
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
	if OS.get_cmdline_user_args().has("--perf-scroll"):
		await scroll_test(tree, out_path)
	var live: Array = []  # kit labels drawing their own glyphs now (not from the bake atlas; those out of sight left out)
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
	if OS.get_cmdline_user_args().has("--perf-vec"):
		await vec_pair(tree, out_path)
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
	if OS.get_cmdline_user_args().has("--perf-nobreak"):  # the counts (and --perf-vec's pair) only, no breakdown
		lines.append("kit bake: %s" % bake_stats(vp.get_node_or_null("KitBake")))
		vp.disable_3d = false
		tree.paused = false
		for ln in lines:
			print("perf-tree ", ln)
		return
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
			if int(r[0]) >= min_cost:
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


## `--perf-vec` (H2 parity): the canvas alone (no 3D world), held still, twice in a row — as drawn (<shot>_bake.png)
## and with the bake atlas off, every kit look drawn as its vectors (<shot>_vec.png) — for tools/hud_diff.py: a look
## that comes from the atlas must match the vectors it stands for. Prints its canvas draws both ways.
static func vec_pair(tree: SceneTree, out_path: String) -> void:
	var vp := tree.root
	var base := out_path.trim_suffix(".tree.txt").get_basename()
	var kit: Script = load("res://scripts/ui_kit.gd")
	vp.disable_3d = true
	var d_bake := await _draws(vp)
	await RenderingServer.frame_post_draw
	vp.get_texture().get_image().save_png(base + "_bake.png")
	kit.KitBake.off = true
	vp.propagate_call("queue_redraw")
	await _draws(vp)
	var d_vec := await _draws(vp)
	await RenderingServer.frame_post_draw
	vp.get_texture().get_image().save_png(base + "_vec.png")
	kit.KitBake.off = false
	vp.propagate_call("queue_redraw")
	await _draws(vp)
	await _draws(vp)
	vp.disable_3d = false
	print("perf-tree vec pair: draws_canvas baked=%d vectors=%d -> %s_bake.png / _vec.png" % [d_bake, d_vec, base])


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
				and (c as Label).visible_characters != 0 and _seen(c as Label):
			out.append("«%s» %s" % [(c as Label).text.replace("\n", " "), _path(c).get_file()])
		_live_labels(c, out)


static func _live_nodes(n: Node, out: Array) -> void:
	for c in n.get_children():
		if c is SubViewport:
			continue
		if c is Label and (c as Label).is_visible_in_tree() and c.get_node_or_null("KitText") != null \
				and (c as Label).visible_characters != 0 and (c as Label).text.strip_edges() != "" and _seen(c as Label):
			out.append(c)
		_live_nodes(c, out)


## A label the bake atlas would bake now (KitBake.in_sight: on the screen — a scroll's clip does not count).
static func _seen(l: Label) -> bool:
	var kit: Script = load("res://scripts/ui_kit.gd")
	if not (kit.KitBake as Script).get_script_method_list().any(func(m): return m["name"] == "in_sight"):
		return true  # (an older kit: every label counts)
	return kit.KitBake.in_sight(l, Rect2(Vector2.ZERO, l.size), 16.0)


## `--perf-scroll` (H2): the open window's list (its first vertical ScrollContainer with more than a page) scrolled to
## the end and back in half-page steps, four frames a step, then held at the end: the bake atlas must not start over
## (no reset) and what came into sight must end up baked. Prints «perf-tree scroll» lines (a FAIL line on a reset),
## and saves the held end as <shot>_end_bake.png / _end_vec.png (tools/hud_diff.py: the atlas against the vectors).
static func scroll_test(tree: SceneTree, out_path: String) -> void:
	var vp := tree.root
	var kb := vp.get_node_or_null("KitBake")
	var main: Node = tree.current_scene
	var ui: Node = main.get("ui") if main != null else null
	var modal: Control = ui.get("_modal") if ui != null else null
	var shop: Control = main.get("shop") if main != null else null
	var sc := _find_scroll(modal if modal != null else shop)
	if sc == null:
		print("perf-tree scroll: no list in the window")
		return
	var bar := sc.get_v_scroll_bar()
	var end := maxf(0.0, bar.max_value - bar.page)
	var r0: int = kb.resets if kb != null else 0
	var e0: int = kb.evicted if kb != null else 0
	print("perf-tree scroll: %s content=%.0f page=%.0f %s" % [_path(sc), bar.max_value, bar.page, bake_stats(kb)])
	var a: Array = []
	var v := 0.0
	var step := maxf(40.0, bar.page * 0.5)
	for dir in [1.0, -1.0]:
		while true:
			v = clampf(v + step * dir, 0.0, end)
			sc.scroll_vertical = int(v)
			for i in 4:
				a.append(await _frame(vp, kb))
			if (dir > 0.0 and v >= end) or (dir < 0.0 and v <= 0.0):
				break
	print("perf-tree scroll: there and back %s resets+%d evicted+%d %s" % [_spread(a), (kb.resets - r0) if kb else 0,
		(kb.evicted - e0) if kb else 0, bake_stats(kb)])
	sc.scroll_vertical = int(end)
	var d := await _settle(tree, vp, kb)
	await tree.create_timer(0.5).timeout
	d = await _settle(tree, vp, kb)
	print("perf-tree scroll: held at the end draws=%d resets+%d evicted+%d %s" % [d, (kb.resets - r0) if kb else 0,
		(kb.evicted - e0) if kb else 0, bake_stats(kb)])
	if kb != null:
		print("perf-tree scroll census: %s" % census(kb))
	if kb != null and kb.resets > r0 + 1:  # (once is the compaction a full atlas falls back to; more is churn)
		print("perf-tree scroll FAIL the atlas started over %d times while the list scrolled (last: %s)" % [kb.resets - r0, String(kb.get("why"))])
	elif kb != null and kb.resets > r0:
		print("perf-tree scroll NOTE the atlas started over once (%s)" % String(kb.get("why")))
	tree.paused = true
	await vec_pair(tree, out_path.trim_suffix(".tree.txt").get_basename() + "_end.tree.txt")
	tree.paused = false
	sc.scroll_vertical = 0
	await _settle(tree, vp, kb)


static func _find_scroll(n: Node) -> ScrollContainer:
	if n == null:
		return null
	for c in n.get_children():
		if c is ScrollContainer and (c as ScrollContainer).is_visible_in_tree():
			var b := (c as ScrollContainer).get_v_scroll_bar()
			if b.max_value > b.page + 1.0:
				return c
		var f := _find_scroll(c)
		if f != null:
			return f
	return null


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


static func _settle(tree: SceneTree, vp: Viewport, kb: Node, tries := 60) -> int:
	var last := -1
	var d := 0
	for i in tries:
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
	for a in args:
		if a.begins_with("--perf-small-atlas=") and kb != null:  # a small atlas: the HUD fills it, eviction must cope
			var side := int(a.get_slice("=", 1))
			kb._asize = Vector2i(side, side)
			kb.atlas.size = kb._asize
			kb.reset()
			await tree.create_timer(1.5).timeout
			p.call("small atlas %d: draws=%d %s" % [side, await _settle(tree, vp, kb), bake_stats(kb)])
	if kb != null and args.has("--perf-dump"):  # the atlas as it is, and where each look is in it
		var base := out_path.trim_suffix(".tree.txt").get_basename()
		kb.atlas.get_texture().get_image().save_png(base + "_atlas.png")
		var fd := FileAccess.open(base + "_atlas.txt", FileAccess.WRITE)
		for key in kb.slots:
			fd.store_line("%s\t%s\t%s" % [kb.slots[key], str(kb.made[key]), key])
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



# ------------------------------------------------------------------ --perf-late: the screens in a late-game state

## `--perf-late` (H2 review): the open screen again in the state a player reaches late in a season or a cycle — the
## login calendar on day 27 (days 1–26 taken), the Chronicle with every goal reached and taken, the War Pass at level
## 30 (premium) with everything up to it taken — rows and tiles under their «taken» α. Picked by the shot's --demo
## (calendar, chronicle, pass); the state is set, the screen opened again and held still, then shot over <shot>.png
## (a «perf late» line with its draws); the breakdown that follows is of that state.
static func late(tree: SceneTree, out_path: String) -> void:
	var main: Node = tree.current_scene
	var vp := tree.root
	var kb := vp.get_node_or_null("KitBake")
	var demo := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--demo="):
			demo = a.get_slice("=", 1).get_slice(":", 0)
	var now: int = main.call("now_s")
	match demo:
		"calendar":
			var cal: Object = main.get("calendar").get_script().new()
			main.set("calendar", cal)
			for d in 27:
				cal.call("visit", now - (26 - d) * 86400)
				if d < 26:
					cal.call("claim")
			main.call("_open_calendar")
		"chronicle":
			var ch: Object = main.get("chronicle")
			var list: Array = ch.get_script().get_script_constant_map()["LIST"]
			for i in list.size():
				var code: String = list[i][0]
				ch.get("reached")[code] = true
				ch.get("claimed")[code] = true
				if not (ch.get("order") as Array).has(code):
					(ch.get("order") as Array).append(code)
			main.call("_open_chronicle")
		"pass":
			var bp: Object = main.get("bp")
			bp.call("add_xp", maxi(0, 30500 - int(bp.get("xp"))), now)
			bp.set("premium", true)
			for lv in range(1, 31):
				for track in ["free", "premium"]:
					if bp.call("can_claim", lv, track):
						bp.call("claim", lv, track)
			main.call("_open_pass")
		_:
			print("perf-tree late: no late state for --demo=%s" % demo)
			return
	await tree.create_timer(1.0).timeout
	var d := await _settle(tree, vp, kb)
	await RenderingServer.frame_post_draw
	var png := out_path.trim_suffix(".tree.txt")
	vp.get_texture().get_image().save_png(png)
	print("perf late=%s draw_calls=%d draws_3d=%d draws_shadow=%d draws_canvas=%d" % [demo,
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		vp.get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME),
		vp.get_render_info(Viewport.RENDER_INFO_TYPE_SHADOW, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME),
		vp.get_render_info(Viewport.RENDER_INFO_TYPE_CANVAS, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)])
	print("perf-tree late %s settled: draws=%d %s" % [demo, d, bake_stats(kb)])


# ------------------------------------------------------------------ --perf-trans: transitions frame by frame

static func _rec(vp: Viewport, kb: Node, n: int) -> Array:
	var a: Array = []
	for i in n:
		a.append(await _frame(vp, kb))
	return a


static func _fmt(a: Array, settled: int) -> String:
	var mx := 0
	var over := 0
	var sum := 0
	for v in a:
		mx = maxi(mx, int(v))
		sum += int(v)
		if int(v) > settled + 20:
			over += 1
	return "max=%d frames>settled+20=%d sum=%d seq=%s" % [mx, over, sum, str(a.slice(0, 30))]


const TRANS_SETTLE := 12  ## --perf-trans waits at most this many settle steps (a breathing element never holds still)


## `--perf-trans` (H2 review; run with --fixed-fps=60): the canvas draws of each frame while things fade — the open
## window closed and opened again twice (`--perf-trans-open=<main's opener>`, e.g. _open_calendar), the bottom tabs
## switched in turn, two toasts — 40 frames each, then held still. Prints «perf-tree trans» lines: the peak, the
## frames more than 20 over the settled count, the sequence.
static func trans(tree: SceneTree, _out_path: String) -> void:
	var vp := tree.root
	var kb := vp.get_node_or_null("KitBake")
	var main: Node = tree.current_scene
	var ui: Node = main.get("ui")
	vp.disable_3d = true
	var p := func(s: String) -> void: print("perf-tree trans ", s)
	var s0 := await _settle(tree, vp, kb, TRANS_SETTLE)
	p.call("settled: draws=%d %s" % [s0, bake_stats(kb)])
	var opener := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--perf-trans-open="):
			opener = a.get_slice("=", 1)
	if ui.get("_modal") != null and opener != "":
		for round_ in 2:
			ui.call("close_modal")
			var c := await _rec(vp, kb, 40)
			var sc := await _settle(tree, vp, kb, TRANS_SETTLE)
			p.call("close %d: %s  settled=%d resets=%d" % [round_, _fmt(c, sc), sc, kb.resets if kb else 0])
			main.call(opener)
			var o := await _rec(vp, kb, 40)
			var so := await _settle(tree, vp, kb, TRANS_SETTLE)
			p.call("open %d: %s  settled=%d resets=%d" % [round_, _fmt(o, so), so, kb.resets if kb else 0])
		ui.call("close_modal")
		await _settle(tree, vp, kb, TRANS_SETTLE)
	for t in ["buildings", "development", "diplomacy", "world", "army", "buildings", "diplomacy", "development"]:
		main.call("_open_tab", t)
		var a := await _rec(vp, kb, 40)
		var d := await _settle(tree, vp, kb, TRANS_SETTLE)
		p.call("tab %s: %s  settled=%d resets=%d %s" % [t, _fmt(a, d), d, kb.resets if kb else 0, bake_stats(kb)])
	for i in 2:
		ui.call("toast", "Проверка уведомления", "gold", "info")
		var a := await _rec(vp, kb, 40)
		var d := await _settle(tree, vp, kb, TRANS_SETTLE)
		p.call("toast %d: %s  settled=%d" % [i, _fmt(a, d), d])
	vp.disable_3d = false
	p.call("done %s" % bake_stats(kb))
