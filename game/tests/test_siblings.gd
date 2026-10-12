extends SceneTree
## Sibling buttons read as one set (docs/dev/hud_perf_plan.json F1; docs/ui_style.md §4.1): opens the main windows,
## the store's tabs and the tray's tabs, groups the visible Kit buttons of each screen into rows (centres within a
## quarter of the smaller height), stacks (one left edge and width, gap ≤ 24) and lists (one place in each row of a
## list) — in the open window or the store, else in the card tray — and fails on a set whose buttons differ in height, caption size, price size, layout (the caption
## over the price) or, in a window, icon presence among the choices that can be taken. Round buttons (✕, «i», back)
## and icon-only ones are not offers; a button may stand apart from its row on purpose with the meta `sibling_solo`
## (the reason), listed.
## A tray row whose buttons differ in icon presence is printed as a NOTE (a locked card carries its lock, a busy one
## its hourglass). Run: godot --headless --path game --script res://tests/test_siblings.gd [-- --lang=ru --only=result,peace]

const Kit := preload("res://scripts/ui_kit.gd")

var fails := 0
var notes := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _initialize() -> void:
	_run.call_deferred()


## [name, demo spec ("" = none), tab to open ("" = none), extra step (Callable(g) or null)]
func _screens() -> Array:
	return [
		["result", "result", "", null],
		["peace", "peace", "", null],
		["ultimatum", "ultimatum", "", null],
		["ceremony", "ceremony:0.1", "", func(g): for i in 80: g.call("_step_ceremony", 0.1)],
		["shop_cases", "shop", "", null],
		["shop_raivite", "shop", "", func(g): _shop_tab(g, "raivite")],
		["shop_packs", "shop", "", func(g): _shop_tab(g, "packs")],
		["shop_atelier", "shop", "", func(g): _shop_tab(g, "atelier")],
		["pass", "pass", "", null],
		["calendar", "calendar", "", null],
		["cal_pick", "calendar:pick", "", null],
		["patent", "patent", "", null],
		["intro_offer", "intro_offer", "", null],
		["ally_ask", "ally_ask", "", null],
		["expansion", "expansion", "", null],
		["peace_offer", "peace_offer", "", null],
		["separate", "separate", "", null],
		["market", "market", "", null],
		["swap", "swap", "", null],
		["swap_ai", "swap_ai", "", null],
		["cmd_card", "commanders:card", "", null],
		["cmd_locked", "commanders:locked", "", null],
		["cmd_assign", "commanders:assign", "", null],
		["commanders", "commanders", "", null],
		["hand", "hand", "", null],
		["settings", "settings", "", null],
		["profile", "profile", "", null],
		["inbox_open", "inbox:open", "", null],
		["chronicle", "chronicle", "", null],
		["flag", "flag", "", null],
		["realm_name", "realm_name", "", null],
		["flag_wizard", "flag_wizard:1", "", null],
		["leader", "", "diplomacy", func(g): _leader(g)],
		["tab_buildings", "", "buildings", null],
		["tab_development", "", "development", null],
		["tab_blueprint", "blueprint", "", null],
		["tab_army", "", "army", null],
		["tab_diplomacy", "", "diplomacy", null],
		["tab_world", "world", "", null],
	]


func _shop_tab(g: Node, t: String) -> void:
	var shop: Control = g.get("shop")
	if shop == null:
		return
	shop.set("tab", t)
	shop.call("_render")


## The first neighbour's card in the Diplomacy tab tapped: the leader dialog.
func _leader(g: Node) -> void:
	var ui: Node = g.get("ui")
	var row: Control = ui.get("_brow")
	if row == null:
		return
	for c in row.get_children():
		if c is Kit.KitCard and (c as Kit.KitCard).tap_cb.is_valid():
			(c as Kit.KitCard).tap_cb.call()
			return


func _new_game() -> Node:
	var g: Node = load("res://scenes/main.tscn").instantiate()
	g.save_enabled = false
	root.add_child(g)
	await process_frame
	await process_frame
	return g


func _run() -> void:
	var only := PackedStringArray()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--only="):
			only = a.substr(7).split(",")
	for sc in _screens():
		var nm := String(sc[0])
		if not only.is_empty() and not only.has(nm):
			continue
		var g := await _new_game()
		if String(sc[2]) != "":
			g.call("_open_tab", String(sc[2]))
		if String(sc[1]) != "":
			await g.call("_demo", String(sc[1]))
		for i in 3:
			await process_frame
		if sc[3] != null:
			(sc[3] as Callable).call(g)
			for i in 3:
				await process_frame
		_check_screen(nm, g)
		g.queue_free()
		await process_frame
		await process_frame
	print("siblings: %d FAIL, %d NOTE" % [fails, notes])
	quit(1 if fails > 0 else 0)


## The scopes a row lives in: the open window or the store when one is up (what is under its dim is not looked at),
## else the card tray and the rest of the bottom group.
func _scopes(g: Node) -> Array:
	var ui: Node = g.get("ui")
	var out: Array = []
	for n in [ui.get("_modal"), g.get("shop")]:
		if n != null and is_instance_valid(n) and (n as Control).is_visible_in_tree():
			out.append(n)
	if not out.is_empty():
		return out
	for n in [ui.get("_bpanel"), ui.get("_bottom")]:
		if n != null and is_instance_valid(n) and (n as Control).is_visible_in_tree():
			out.append(n)
	return out


func _check_screen(nm: String, g: Node) -> void:
	var scopes := _scopes(g)
	var groups := {}  # scope index -> [entries]
	var all: Array = []
	_collect(g.get("ui"), all)
	var seen := 0
	for b in all:
		var kb := b as Kit.KitButton
		var si := -1
		var p: Node = kb.get_parent()
		while p != null:
			var k := scopes.find(p)
			if k >= 0:
				si = k
				break
			p = p.get_parent()
		if si < 0:
			continue
		var e := _entry(kb, scopes[si])
		if e.is_empty():
			continue
		e["window"] = scopes[si] == g.get("ui").get("_modal") or scopes[si] == g.get("shop")
		seen += 1
		if not groups.has(si):
			groups[si] = []
		(groups[si] as Array).append(e)
	var bad := 0
	var sets := 0
	for si in groups:
		for row in _rows(groups[si]) + _columns(groups[si]) + _lists(groups[si]):
			if row.size() < 2:
				continue
			sets += 1
			bad += _check_row(nm, row)
	_check(bad == 0, "%s: %d buttons, %d sets of siblings (rows and stacks), each one set" % [nm, seen, sets])


func _collect(n: Node, out: Array) -> void:
	if n is Kit.KitButton:
		out.append(n)
	for c in n.get_children():
		_collect(c, out)


## A button's row entry: its rect in the scope (positions summed, so a window's pop-in scale does not matter), its
## plan and what the plan shows; {} for what is not an offer (hidden, round, icon-only, not laid out).
func _entry(kb: Kit.KitButton, scope: Node) -> Dictionary:
	if not kb.is_visible_in_tree() or kb.round_btn:
		return {}
	if kb.caption.strip_edges() == "" and kb.price.is_empty():
		return {}
	var pl: Dictionary = kb.last_plan
	if pl.is_empty():
		return {}
	var pos := Vector2.ZERO
	var n: Node = kb
	while n != null and n != scope:
		if n is Control:
			pos += (n as Control).position
		n = n.get_parent()
	var has_text := false
	var has_price := false
	var has_icon := false
	for part in pl["parts"]:
		match String(part["kind"]):
			"text":
				has_text = has_text or String(part.get("text", "")).strip_edges() != ""
			"price":
				has_price = true
			"main_icon":
				has_icon = true
	return {"b": kb, "r": Rect2(pos, kb.size), "s": int(pl["s"]), "pn": int(pl["pn"]), "stack": bool(pl["stack"]),
		"two": String(pl["two"]) != "", "text": has_text, "price": has_price, "icon": has_icon,
		"solo": String(kb.get_meta("sibling_solo", ""))}


## Rows: entries whose vertical centres lie within a quarter of the smaller height, in reading order.
func _rows(es: Array) -> Array:
	var sorted := es.duplicate()
	sorted.sort_custom(func(a, b): return (a["r"] as Rect2).get_center().y < (b["r"] as Rect2).get_center().y)
	var rows: Array = []
	for e in sorted:
		var placed := false
		for row in rows:
			var r0: Rect2 = row[0]["r"]
			var r1: Rect2 = e["r"]
			if absf(r0.get_center().y - r1.get_center().y) <= 0.25 * minf(r0.size.y, r1.size.y):
				row.append(e)
				placed = true
				break
		if not placed:
			rows.append([e])
	for row in rows:
		row.sort_custom(func(a, b): return (a["r"] as Rect2).position.x < (b["r"] as Rect2).position.x)
	return rows


## Stacks: entries of one left edge, width and height straight under each other (gap ≤ 24) — a column of choices.
func _columns(es: Array) -> Array:
	var sorted := es.duplicate()
	sorted.sort_custom(func(a, b): return (a["r"] as Rect2).position.y < (b["r"] as Rect2).position.y)
	var cols: Array = []
	for e in sorted:
		var r1: Rect2 = e["r"]
		var placed := false
		for col in cols:
			var r0: Rect2 = col[-1]["r"]
			if absf(r0.position.x - r1.position.x) <= 0.5 and absf(r0.size.x - r1.size.x) <= 0.5 \
					and r1.position.y - r0.end.y >= -0.5 and r1.position.y - r0.end.y <= 24.0:
				col.append(e)
				placed = true
				break
		if not placed:
			cols.append([e])
	return cols


## Lists: buttons at one place in the rows of a list — each in its own row or tile, those under one parent, at one local
## x, width and height (the commander picker's «Назначить», a pack's price, a chronicle row's «Забрать») — however far
## apart the rows are. Two buttons of one parent are a row or a stack above, never a list (a window's middle button
## and its footer may share a width by chance).
func _lists(es: Array) -> Array:
	var by := {}
	for e in es:
		var kb: Kit.KitButton = e["b"]
		var p := kb.get_parent()
		if p == null or p.get_parent() == null:
			continue
		var key := "%d|%d|%d|%d" % [p.get_parent().get_instance_id(), roundi(kb.position.x), roundi(kb.size.x),
			roundi(kb.size.y)]
		if not by.has(key):
			by[key] = []
		(by[key] as Array).append(e)
	var out: Array = []
	for k in by:
		var l: Array = by[k]
		var parents := {}
		for e in l:
			parents[(e["b"] as Node).get_parent()] = true
		if l.size() >= 2 and parents.size() == l.size():
			l.sort_custom(func(a, b): return (a["r"] as Rect2).position.y < (b["r"] as Rect2).position.y)
			out.append(l)
	return out


func _desc(e: Dictionary) -> String:
	var kb: Kit.KitButton = e["b"]
	return "%s«%s»[%s h%d s%d%s%s%s]" % [kb.name, kb.caption.replace("\n", " "), kb.role, int((e["r"] as Rect2).size.y),
		int(e["s"]), (" pn%d" % int(e["pn"])) if bool(e["price"]) else "", " stack" if bool(e["stack"]) else "",
		" icon" if bool(e["icon"]) else ""]


func _check_row(nm: String, row: Array) -> int:
	var peers := row.filter(func(e): return String(e["solo"]) == "")
	var line := " ".join(row.map(func(e): return _desc(e)))
	for e in row:
		if String(e["solo"]) != "":
			print("      %s: %s stands apart: %s" % [nm, _desc(e), e["solo"]])
	if peers.size() < 2:
		return 0
	var errs := PackedStringArray()
	var h0: float = (peers[0]["r"] as Rect2).size.y
	if peers.any(func(e): return absf((e["r"] as Rect2).size.y - h0) > 0.5):
		errs.append("heights differ")
	var texts := peers.filter(func(e): return bool(e["text"]))
	if texts.size() > 1 and texts.any(func(e): return int(e["s"]) != int(texts[0]["s"])):
		errs.append("caption sizes differ")
	var prices := peers.filter(func(e): return bool(e["price"]))
	if prices.size() > 1 and prices.any(func(e): return int(e["pn"]) != int(prices[0]["pn"])):
		errs.append("price sizes differ")
	var both := peers.filter(func(e): return bool(e["text"]) and bool(e["price"]))
	if both.size() > 1 and both.any(func(e): return bool(e["stack"]) != bool(both[0]["stack"])):
		errs.append("layouts differ (caption over the price in some)")
	# icons: in a window the choices that can be taken all carry one (or none do); a locked or busy button carries its
	# lock or hourglass, and a tray row mixes states, so there it is only a note
	var live := peers.filter(func(e): return (e["b"] as Kit.KitButton).enabled and (e["b"] as Kit.KitButton).role != "lock")
	if live.any(func(e): return bool(e["icon"]) != bool(live[0]["icon"])):
		if bool(peers[0].get("window", false)):
			errs.append("icons differ")
		else:
			notes += 1
			print("NOTE  %s: icons differ in a row: %s" % [nm, line])
	if errs.is_empty():
		print("      %s: ok %s" % [nm, line])
		return 0
	print("  ×   %s: %s: %s" % [nm, ", ".join(errs), line])
	return 1
