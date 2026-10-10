extends Control
## «Лавка» — the store (canon §15.3–15.5, docs/ui_style.md §6 «Лавка»): a cream window L over an INK dim with the gold
## plate and the stall, segments «Кейсы / Райвиты / Наборы / Ателье»; offer cards in wells (the chest on a
## rarity-tinted plate, the name, one note line, a round «i» with the odds window); the free crate, the Royal case with
## its pity bar, the collection case; the opening's reveal (rays and a 300 px tile, or a grid of 10). The balance is
## not repeated: the currency plates stay over the dim. Purely a view: purchases and openings are requested through
## signals and the controller (main.gd) applies them. Payments are stubs until the store SDKs are connected.

signal open_case(case_id: String, times: int, pay: String)  # pay: "free" | "raivite" | "ad" | "key"
signal buy_sku(sku: String)
signal closed

const GameUI := preload("res://scripts/game_ui.gd")
const L := preload("res://scripts/l10n.gd")
const Kit := preload("res://scripts/ui_kit.gd")
const VW := 941.0
const VH := 1672.0

## Raivite packs (canon §15.3): price label, amount; the first purchase of each is doubled. Price labels are
## placeholders until the store SDK supplies localized prices (`_price` switches the decimal comma in English).
const RAIVITE_SKUS := [
	["iap_raivite_s", "$0,99", 80], ["iap_raivite_m", "$4,99", 500], ["iap_raivite_l", "$9,99", 1100],
	["iap_raivite_xl", "$19,99", 2400], ["iap_raivite_xxl", "$49,99", 6500], ["iap_raivite_xxxl", "$99,99", 14000],
]
## Packs: sku, name key, price, description key, optional period key appended to the price.
const PACK_SKUS := [
	["iap_starter", "pack.starter", "$1,99", "pack.starter.desc", ""],
	["iap_builder", "pack.builder", "$4,99", "pack.builder.desc", ""],
	["iap_no_ads", "pack.no_ads", "$4,99", "pack.no_ads.desc", ""],
	["iap_ration", "pack.ration", "$4,99", "pack.ration.desc", "pack.period_30d"],
	["iap_pass", "pack.pass", "$7,99", "pack.pass.desc", "pack.period_season"],
	["patent_screen", "pack.patent", "$7,99", "pack.patent.desc", "pack.period_month"],
]
const PACK_ICON := {"iap_starter": "helmet", "iap_builder": "mason", "iap_no_ads": "ad", "iap_ration": "food",
	"iap_pass": "medal", "patent_screen": "charter"}
## Each case's chest and the rarity that tints its plate (the Royal case's point is its epic guarantee).
const CASE_LOOK := {"case_war_crate": ["chest_wood", "common"], "case_royal": ["chest_royal", "epic"],
	"case_collection": ["chest_cards", "legendary"]}
const RES_ICON := {"gold": "coin", "food": "food", "metal": "metal", "oil": "barrel"}
const RARITY_ORDER := ["common", "rare", "epic", "legendary"]
const TABS := ["cases", "raivite", "packs", "atelier"]
const WIN_W := 893.0  # the window L (§4.3)
const PAD := 32.0
const BODY_Y := 176.0  # the content under the plate and the segments
const CARD_GAP := 16.0

var ui: GameUI  # toast, the shared modal (the odds window)
var cases  # scripts/sim/cases.gd
var raivite := 0
var payments := true  # false in Russia: real-money items are hidden (canon §15.11)
var now := 0
var tab := "cases"
var _body: Control
var _frame: Panel
var _reveal: Control
var _shown := false  # the window has popped in once (a tab switch or a refresh re-renders it in place)
var _closing := false
var _timer_lbl: Label  # the free crate's countdown (ticks while the store is open)
var _t0_ms := 0


func setup(p_ui: GameUI, p_cases, p_raivite: int, p_payments: bool, p_now: int) -> void:
	ui = p_ui
	cases = p_cases
	raivite = p_raivite
	payments = p_payments
	now = p_now
	size = Vector2(VW, VH)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_render()


func refresh(p_raivite: int, p_now: int) -> void:
	raivite = p_raivite
	now = p_now
	_render()


func _close() -> void:
	if _closing:
		return
	_closing = true
	closed.emit()


## A tap on the dim (outside the window) closes the store, like any window that is not a decision (§4.3).
func _gui_input(e: InputEvent) -> void:
	var up: bool = (e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT \
		and not e.pressed) or (e is InputEventScreenTouch and not e.pressed)
	if up and is_instance_valid(_frame) and not is_instance_valid(_reveal) \
			and not _frame.get_global_rect().grow(8.0).has_point(get_global_transform_with_canvas() * e.position):
		_close()


func _process(_d: float) -> void:
	if not is_instance_valid(_timer_lbl) or not _timer_lbl.is_inside_tree():
		return
	var cur := now + (Time.get_ticks_msec() - _t0_ms) / 1000
	var left: int = cases.free_crate_left(cur)
	if left <= 0 and tab == "cases":
		now = cur
		_render()
		return
	_timer_lbl.text = GameUI.fmt_time(left)


## The window band (§4.3): y 150 … VB − 24.
func _band() -> Vector2:
	return Vector2(150.0, Kit.vb(self) - 24.0)


func _render() -> void:
	var keep: Node = _reveal if is_instance_valid(_reveal) else null
	for c in get_children():
		if c != keep:
			c.queue_free()
	_timer_lbl = null
	_t0_ms = Time.get_ticks_msec()
	var vis := get_viewport().get_visible_rect() if is_inside_tree() else Rect2(0, 0, VW, VH)
	size = Vector2(maxf(VW, vis.end.x), maxf(VH, vis.end.y))  # a tall phone: the store still takes every tap
	var dim := ColorRect.new()
	dim.name = "dim"
	dim.color = Kit.alpha(Kit.INK, Kit.DIM_A)
	dim.position = vis.position
	dim.size = Vector2(maxf(VW, vis.size.x), maxf(VH, vis.size.y))
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(dim)
	# one height for every tab: the cases' (the store's main page); a sheet when they fill 70 % of it (§4.3)
	var band := _band()
	var max_h := band.y - band.x
	var h := BODY_Y + _cases_h() + PAD
	if h >= max_h * 0.7:
		h = max_h
	h = minf(h, max_h)
	_frame = ui._panel(self, Rect2((VW - WIN_W) * 0.5, band.x + (max_h - h) * 0.5, WIN_W, h), Kit.style(Kit.CREAM, 34, 5, Kit.INK, 10, 12))
	_frame.name = "frame"
	_frame.set_meta("kit_native", true)
	var first := not _shown
	_shown = true
	if first:
		Kit.pop_in(_frame)
	Kit.title_plate(_frame, tr("shop.title"), "gold", "stall", first)
	Kit.close_button(_frame, _close)
	var names: Array = []
	for k in TABS:
		names.append(tr("shop.tab." + k))
	var seg := Kit.segmented(_frame, Rect2(PAD, 72, WIN_W - 2.0 * PAD, 80), names, TABS.find(tab), func(i: int):
		if TABS[i] != tab:
			tab = TABS[i]
			_render())
	seg.name = "tabs"
	_body = Control.new()
	_body.name = "body"
	_body.position = Vector2(PAD, BODY_Y)
	_body.size = Vector2(WIN_W - 2.0 * PAD, h - BODY_Y - PAD)
	_body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_frame.add_child(_body)
	match tab:
		"cases":
			_cases_tab()
		"raivite":
			_raivite_tab()
		"packs":
			_packs_tab()
		"atelier":
			_atelier_tab()
	if not first:
		Kit.fade_in(_body)
	if is_instance_valid(_reveal):
		move_child(_reveal, get_child_count() - 1)


# ------------------------------------------------------------------ cases

const CRATE_H := 240.0
const ROYAL_H := 280.0
const COLL_H := 224.0


func _cases_h() -> float:
	return CRATE_H + CARD_GAP + ROYAL_H + CARD_GAP + COLL_H


## An offer card (§6 Лавка): a CREAM_WELL plate R 24 the body's width; at the left the chest 180 on a 220 px plate
## tinted by the case's rarity; the name (H1 36), one note line (LABEL 24 MUTED_CREAM) and the round «i» (odds) at the
## top right. Returns the card; its actions go into the right column (x ≥ COL_X).
const COL_X := 260.0


func _card(y: float, h: float, case_id: String, note: String) -> Panel:
	var w := _body.size.x
	var c := Panel.new()
	c.name = case_id
	var sb := Kit.style(Kit.CREAM_WELL, 24, 0, Kit.INK, 0, 0)
	sb.set_meta("kit_kind", "")
	c.add_theme_stylebox_override("panel", sb)
	c.position = Vector2(0, y)
	c.size = Vector2(w, h)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_body.add_child(c)
	var look: Array = CASE_LOOK.get(case_id, ["crate", "common"])
	var tint: Color = Kit.RARITY.get(String(look[1]), Kit.RARITY["common"])
	var art := Panel.new()
	art.name = "art"
	var asb := Kit.style(tint.lerp(Kit.CREAM_ROW, 0.55), 20, 4, Kit.INK, 0, 6)
	asb.set_meta("kit_kind", "")
	asb.set_meta("kit_lip_color", tint.lerp(Kit.CREAM_ROW, 0.2))
	art.add_theme_stylebox_override("panel", asb)
	art.position = Vector2(16, 16)
	art.size = Vector2(220, h - 32.0)
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.add_child(Kit.KitDecor.new())
	c.add_child(art)
	var glow := Kit.KitShape.new("rays", Kit.WHITE)
	glow.data = {"n": 12}
	glow.size = Vector2(200, 200)
	glow.position = Vector2(10, (art.size.y - 6.0) * 0.5 - 100.0)
	art.add_child(glow)
	var chest := Kit._card_rect(Kit.icon_tex(String(look[0])), Rect2(20, (art.size.y - 6.0) * 0.5 - 90.0, 180, 180))
	chest.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.add_child(chest)
	var tw := w - COL_X - 16.0 - 52.0 - 12.0
	var name := String(cases.case_name(case_id))
	var ts := Kit.fit_size(name, 36, tw, "d900", 26, false)
	var tl := Kit.label(name, ts, Kit.INK_TEXT, true)
	tl.name = "title"
	tl.add_theme_font_size_override("font_size", ts)
	tl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	tl.clip_text = Kit.text_w(name, ts, "d900", false) > tw
	tl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	tl.position = Vector2(COL_X, 14)
	tl.size = Vector2(tw, 48)
	c.add_child(tl)
	if note != "":
		var cw := w - COL_X - 16.0
		var ns := Kit.fit_size(note, 24, cw, "d800", 22, false)
		var nl := Kit.label(note, ns, Kit.MUTED_CREAM, true)
		nl.name = "note"
		nl.add_theme_font_override("font", Kit.font("d800"))
		nl.add_theme_font_size_override("font_size", ns)
		nl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		nl.clip_text = Kit.text_w(note, ns, "d800", false) > cw
		nl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		nl.position = Vector2(COL_X, 60)
		nl.size = Vector2(cw, 34)
		c.add_child(nl)
	Kit.info_button(c, Vector2(w - 16.0 - 26.0, 16.0 + 26.0), func(): _show_odds(case_id))
	return c


## A raivite price on a button: [[raivite, 1 440, short]]; a short one keeps its role, the tap shakes and says how
## many are missing (§4.1) instead of opening.
func _spend_button(parent: Control, r: Rect2, caption: String, price: int, cb: Callable, case_id: String) -> Kit.KitButton:
	var short := raivite < price
	var b := Kit.button(parent, r, "gold", caption, {"price": [["raivite", Kit.fmt_num(price), short]], "size": "M"})
	if short:
		var why := tr("shop.short") % (price - raivite)
		b.cb = func():
			Kit.shake(b)
			Kit.tooltip(b, String(cases.case_name(case_id)), why)
	else:
		b.cb = cb
	return b


func _cases_tab() -> void:
	var w := _body.size.x
	var cw := w - COL_X - 20.0
	# Военный ящик: free every 6 h (stores 2), +1 for a rewarded ad
	var free: int = cases.claim_free_crates(now)
	var c1 := _card(0.0, CRATE_H, "case_war_crate", tr("shop.crate_note"))
	if free > 0:
		var ob := Kit.button(c1, Rect2(COL_X, 108, cw, 116), "go", tr("shop.open"), {"size": "L",
			"cb": func(): open_case.emit("case_war_crate", 1, "free")})
		ob.name = "open_free"
		Kit.hex_badge(c1, Vector2(COL_X + 8.0, 112.0), 26, "info", str(free)).name = "free_count"
	else:
		var left: int = cases.free_crate_left(now)
		var chip := Kit.chip(c1, Vector2(COL_X, 112), "hourglass", GameUI.fmt_time(left), "timer")
		chip.name = "crate_timer"
		chip.position.y = 166.0 - chip.size.y * 0.5
		_timer_lbl = chip.get_node("label") as Label
		var bw := 200.0
		var ab := Kit.button(c1, Rect2(w - 20.0 - bw, 134, bw, 64), "go", "+1", {"icon": "ad", "size": "S",
			"cb": func(): open_case.emit("case_war_crate", 1, "ad")})
		ab.name = "ad_crate"
		# the chip gives way to the button: its time keeps its size, never runs under the button
		chip.size.x = minf(chip.size.x, ab.position.x - 16.0 - COL_X)
	# Королевский кейс: the pity bar «Эпик через 4», ×1 160 / ×10 1 440 (×10 guarantees an epic)
	var y2 := CRATE_H + CARD_GAP
	var tgt: String = cases.target_commander
	var tname: String = cases.commander_name(tgt) if tgt != "" else tr("shop.target_none")
	var c2 := _card(y2, ROYAL_H, "case_royal", tr("shop.target_short") % tname)
	var pity := _royal_pity()
	var every: int = pity[1]
	var e_left: int = pity[0]
	var bar := Kit.bar(c2, Rect2(COL_X + 30.0, 106, cw - 30.0, 40), clampf(float(every - e_left) / maxf(1.0, every), 0.0, 1.0),
		"info", tr("pity.epic_in") % e_left, true)
	bar.name = "pity"
	Kit.hex_badge(c2, Vector2(COL_X + 26.0, 126), 28, "", "", Kit.RARITY["epic"]).name = "epic_gem"
	var bw2 := (cw - 16.0) * 0.5
	var p1: int = cases.price("case_royal")
	var keys := int(cases.royal_keys)
	if keys > 0:
		var kb := Kit.button(c2, Rect2(COL_X, 172, bw2, 88), "go", tr("shop.open"), {"icon": "key", "size": "M",
			"cb": func(): open_case.emit("case_royal", 1, "key")})
		kb.name = "open_key"
		Kit.hex_badge(c2, Vector2(COL_X + 8.0, 176.0), 24, "info", str(keys)).name = "key_count"
	else:
		_spend_button(c2, Rect2(COL_X, 172, bw2, 88), "×1", p1, func(): open_case.emit("case_royal", 1, "raivite"), "case_royal").name = "open_x1"
	var p10: int = cases.price_x10("case_royal")
	var b10 := _spend_button(c2, Rect2(COL_X + bw2 + 16.0, 172, bw2, 88), "×10", p10, func(): open_case.emit("case_royal", 10, "raivite"), "case_royal")
	b10.name = "open_x10"
	Kit.ribbon(c2, Vector2(b10.position.x + bw2 * 0.5, 172.0), tr("shop.epic_sure"), "war")
	# Кейс коллекции (сезонный): no duplicates, 8 items
	var y3 := y2 + ROYAL_H + CARD_GAP
	var c3 := _card(y3, COLL_H, "case_collection", cases.pity_text("case_collection"))
	var p3: int = cases.price("case_collection")
	if p3 > 0:
		_spend_button(c3, Rect2(COL_X, 116, minf(cw, 320.0), 88), tr("shop.open"), p3,
			func(): open_case.emit("case_collection", 1, "raivite"), "case_collection").name = "open_collection"
	else:
		var done := Kit.chip(c3, Vector2(COL_X + 44.0, 136), "", tr("pity.collection_done"), "status")
		Kit.check_badge(c3, Vector2(COL_X + 20.0, 136.0 + done.size.y * 0.5), 40.0)


## The Royal case's epic counter: [left, every, legendary left, hard at] (cases.gd keeps the counters by name).
func _royal_pity() -> Array:
	var c: Dictionary = cases._case("case_royal")
	var pd: Dictionary = c.get("pity", {})
	var ep: Dictionary = pd.get("epic_plus", {})
	var lg: Dictionary = pd.get("legendary", {})
	var every := int(ep.get("every", 10))
	var hard := int(lg.get("hard_at", 50))
	var e_left := every - int(cases.pity.get(cases._counter_name("case_royal", "epic_plus"), 0))
	var l_left := hard - int(cases.pity.get(cases._counter_name("case_royal", "legendary"), 0))
	return [maxi(1, e_left), every, maxi(1, l_left), hard]


## «i»: odds by rarity, base and with the pity (long-run), before any purchase (canon §15.4) — a window M with a
## rarity gem per row; the pity line and the history note under the list. ✕ closes it; the store stays.
func _show_odds(case_id: String) -> void:
	var rows: Array = cases.odds(case_id)
	var row_h := 88.0
	var well_h := 16.0 + rows.size() * row_h + maxf(0, rows.size() - 1) * 12.0 + 16.0
	var pity := String(cases.pity_text(case_id))
	var h := 72.0 + 40.0 + well_h + 20.0 + (76.0 if pity != "" else 0.0) + 36.0 + 32.0
	var box: Panel = ui._modal_box(ui._win_rect("M", h), false, tr("shop.odds"), "", "info", true, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	# the two number columns (base, with the pity) end where the rows' numbers end: well 32 + row 16 + its right pad 16
	var nums_x := w - 32.0 - 16.0 - 16.0 - 330.0
	for k in 2:
		var hl := Kit.label(tr("shop.odds_base") if k == 0 else tr("shop.odds_pity"), 24, Kit.MUTED_CREAM, true)
		hl.add_theme_font_override("font", Kit.font("d800"))
		hl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		hl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		hl.position = Vector2(nums_x + k * 170.0 - 40.0, 72)
		hl.size = Vector2(200, 36)
		box.add_child(hl)
	var well := Kit.well(box, Rect2(32, 112, w - 64.0, well_h))
	for i in rows.size():
		var o: Dictionary = rows[i]
		var r := String(o["rarity"])
		var gem := Kit.hex_badge(null, Vector2(30, 30), 30, "", "", Kit.RARITY.get(r, Kit.RARITY["common"]))
		var nums := Control.new()
		nums.size = Vector2(330, 48)
		nums.mouse_filter = Control.MOUSE_FILTER_IGNORE
		for k in 2:
			var v := float(o["base"]) if k == 0 else float(o["effective"])
			var nl := Kit.label(Kit.fmt_dec(v, 2) + "%", 30, Kit.INK_TEXT, true)
			nl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			nl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			nl.position = Vector2(k * 170.0, 0)
			nl.size = Vector2(160, 48)
			nums.add_child(nl)
		var rw := Kit.row(well, Rect2(16, 16 + i * (row_h + 12.0), well.size.x - 32.0, row_h),
			{"icon_node": gem, "title": String(o.get("name", cases.rarity_name(r))), "right": nums})
		rw.name = "odds_" + r
	var y := 112.0 + well_h + 20.0
	if pity != "":
		var pl := Kit.label(pity, 26, Kit.SOFT_CREAM, false)
		pl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		pl.max_lines_visible = 2
		pl.position = Vector2(32, y)
		pl.size = Vector2(w - 64.0, 72)
		box.add_child(pl)
		y += 76.0
	var hs := Kit.label(tr("shop.history"), 22, Kit.MUTED_CREAM, false)
	hs.position = Vector2(32, y)
	hs.size = Vector2(w - 64.0, 32)
	hs.clip_text = true
	hs.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	box.add_child(hs)


# ------------------------------------------------------------------ the opening

## The reveal after an opening (§6 Лавка): a dim α 0.75 over the store, the best rarity on a hex plate of its colour,
## rays and the item's tile 300 (several rewards: a grid of tiles, 4 a row, a repeated one counted «×N» on its tile),
## «Забрать» (go L) under it.
func show_reveal(results: Array) -> void:
	if is_instance_valid(_reveal):
		_reveal.queue_free()
	var best := "common"
	var looks: Array = []  # one tile per kind of reward: repeats share it with a «×N» hex (§4.9)
	var by_key := {}
	for r in results:
		var rar := String(r.get("rarity", "common"))
		if RARITY_ORDER.find(rar) > RARITY_ORDER.find(best):
			best = rar
		for rw in r.get("rewards", []):
			var o := _reward_look(rw, rar)
			var key := "%s|%s|%s|%s" % [o.get("icon", ""), (o["tex"] as Texture2D).resource_path if o.has("tex") else "",
				o.get("title", ""), str(o.get("pill", [])) + str(o["face"])]
			if by_key.has(key):
				by_key[key]["count"] = int(by_key[key].get("count", 1)) + 1
			else:
				by_key[key] = o
				looks.append(o)
	var vis := get_viewport().get_visible_rect() if is_inside_tree() else Rect2(0, 0, VW, VH)
	_reveal = Control.new()
	_reveal.name = "reveal"
	_reveal.position = vis.position
	_reveal.size = Vector2(maxf(VW, vis.size.x), maxf(VH, vis.size.y))
	_reveal.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_reveal)
	var dim := ColorRect.new()
	dim.color = Kit.alpha(Kit.INK, 0.75)
	dim.size = _reveal.size
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_reveal.add_child(dim)
	var stage := Control.new()  # the 941 × 1672 layout, centred in the visible band
	stage.size = Vector2(VW, VH)
	stage.position = Vector2((_reveal.size.x - VW) * 0.5, (Kit.vb(self) - VH) * 0.5 - vis.position.y)
	stage.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_reveal.add_child(stage)
	var tint: Color = Kit.RARITY.get(best, Kit.RARITY["common"])
	var single := looks.size() <= 1
	var cols := mini(4, maxi(1, looks.size()))
	var tw := 206.0
	var th := 196.0
	var rows := ceili(looks.size() / float(cols))
	var grid_h := 340.0 if single else rows * th + (rows - 1) * 16.0
	var top := (VH - (104.0 + 48.0 + grid_h + 56.0 + 116.0)) * 0.5
	var holder := Control.new()  # the plate sits centred on this line
	holder.size = Vector2(VW, 1)
	holder.position = Vector2(0, top + 52.0)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stage.add_child(holder)
	var plate := Kit.title_plate(holder, String(cases.rarity_name(best)) + "!", "info", "", true, 46)
	plate.face = tint
	plate.lip = tint.darkened(0.32)
	plate.queue_redraw()
	var gy := top + 104.0 + 48.0
	if single:
		var rays := Kit.KitShape.new("rays", tint.lerp(Kit.WHITE, 0.35))
		rays.size = Vector2(760, 760)
		rays.position = Vector2(VW * 0.5 - 380.0, gy + 170.0 - 380.0)
		rays.pivot_offset = rays.size * 0.5
		stage.add_child(rays)
		if Kit._dur(1.0) > 0.0:
			rays.create_tween().set_loops().tween_property(rays, "rotation", TAU, 24.0).from(0.0)
		if not looks.is_empty():
			var o: Dictionary = (looks[0] as Dictionary).duplicate()
			o["icon_side"] = 180.0
			var t := Kit.tile(stage, Rect2(VW * 0.5 - 150.0, gy, 300, 340), o)
			t.name = "item"
			Kit.pop_in(t)
	else:
		var gx := (VW - (cols * tw + (cols - 1) * 16.0)) * 0.5
		for i in looks.size():
			var o: Dictionary = (looks[i] as Dictionary).duplicate()
			o["icon_side"] = 100.0
			var t := Kit.tile(stage, Rect2(gx + (i % cols) * (tw + 16.0), gy + (i / cols) * (th + 16.0), tw, th - 20.0), o)
			t.name = "item_%d" % i
			ui._pop_later(t, 0.05 * i)
	var by := gy + grid_h + 56.0
	var rv := _reveal
	var cb := Kit.button(stage, Rect2(VW * 0.5 - 240.0, by, 480, 116), "go", tr("ui.claim"), {"size": "L",
		"cb": func():
			if is_instance_valid(rv):
				rv.queue_free()})
	cb.name = "claim"


## How a reward shows on a tile: the picture (an icon or a commander's portrait), its name, the amount pill and the
## rarity's tinted face.
func _reward_look(rw: Dictionary, rarity: String) -> Dictionary:
	var r := String(rw.get("rarity", rarity))
	var o := {"face": (Kit.RARITY.get(r, Kit.RARITY["common"]) as Color).lerp(Kit.CREAM_ROW, 0.55)}
	match String(rw.get("kind", "")):
		"res":
			var res: Dictionary = rw.get("res", {})
			var keys: Array = res.keys().filter(func(k): return int(res[k]) > 0)
			if keys.size() == 1:
				o["icon"] = String(RES_ICON.get(String(keys[0]), "coin"))
				o["pill"] = [["", "+" + Kit.fmt_num(int(res[keys[0]]))]]
				o["title"] = tr("res.name." + String(keys[0]))
			else:
				o["icon"] = "crate"
				o["pill"] = [["", tr("time.h") % int(rw.get("hours", 1))]]
				o["title"] = tr("shop.resources")
		"speedup":
			var m := int(rw.get("minutes", 0))
			o["icon"] = "lightning"
			o["pill"] = [["", tr("time.h") % (m / 60) if m >= 60 and m % 60 == 0 else tr("time.m") % m]]
			o["title"] = tr("shop.speedup")
		"shards":
			var cmd := String(rw.get("commander", ""))
			var p := "res://assets/ui/portraits/%s.png" % cmd
			if ResourceLoader.exists(p):
				o["tex"] = load(p)
			else:
				o["icon"] = "shard"
			o["pill"] = [["shard", "×%d" % int(rw.get("n", 1))]]
			o["title"] = String(rw.get("name", cmd))
		"cosmetic":
			o["icon"] = String(Kit.COSMETIC_ICON.get(String(rw.get("category", "")), "frame"))
			o["title"] = String(rw.get("name", ""))
		"glitter":
			o["icon"] = "xp"
			o["pill"] = [["", "+%d" % int(rw.get("n", 0))]]
			o["title"] = tr("shop.glitter_name")
	return o


## One reward line in the current language (reward names come localized from cases.gd).
static func describe(rw: Dictionary) -> String:
	match String(rw.get("kind", "")):
		"res":
			var parts := PackedStringArray()
			var res: Dictionary = rw["res"]
			for k in res:
				if int(res[k]) > 0:
					parts.append("%d %s" % [int(res[k]), L.t("res.gen." + String(k))])
			return L.t("shop.rw_res") % ", ".join(parts)
		"speedup":
			return L.t("shop.rw_speedup") % int(rw["minutes"])
		"shards":
			return L.t("shop.rw_shards") % [int(rw["n"]), rw.get("name", rw["commander"])]
		"cosmetic":
			return L.t("shop.rw_cosmetic") % rw["name"]
		"glitter":
			return L.t("shop.rw_glitter") % int(rw["n"])
	return str(rw)


## Price placeholder in the UI language ("$4,99" → "$4.99" in English).
static func _price(s: String) -> String:
	return s.replace(",", ".") if L.lang() == "en" else s


## A paragraph on paper for a tab with nothing to sell here (BODY 28 SOFT_CREAM, centred, under an icon).
func _empty(icon: String, text: String) -> void:
	var w := _body.size.x
	var top := maxf(24.0, (_body.size.y - 300.0) * 0.5)
	var ic := Kit._card_rect(Kit.icon_tex(icon), Rect2(w * 0.5 - 72.0, top, 144, 144))
	ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_body.add_child(ic)
	var l := Kit.label(text, 28, Kit.SOFT_CREAM, false)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.max_lines_visible = 3
	l.position = Vector2(40, top + 166.0)
	l.size = Vector2(w - 80.0, 132)
	_body.add_child(l)


# ------------------------------------------------------------------ real-money tabs (stubs until store SDKs)

func _raivite_tab() -> void:
	if not payments:
		_empty("raivite", tr("shop.no_payments").replace("\n", " "))
		return
	var w := _body.size.x
	Kit.ribbon(_body, Vector2(w * 0.5, 20.0), tr("shop.first_x2"), "gold").name = "first_x2"
	var cols := 3
	var gap := 16.0
	var tw := (w - gap * (cols - 1)) / cols
	var rows := ceili(RAIVITE_SKUS.size() / float(cols))
	var th := minf(360.0, (_body.size.y - 56.0 - gap * (rows - 1)) / rows)
	for i in RAIVITE_SKUS.size():
		var sku: Array = RAIVITE_SKUS[i]
		var r := Rect2((i % cols) * (tw + gap), 56.0 + (i / cols) * (th + gap), tw, th)
		var t := Kit.tile(_body, r, {"icon": "raivite", "icon_side": 84.0 + (i / cols) * 16.0 + (i % cols) * 6.0,
			"value": Kit.fmt_exact(int(sku[2])), "face": Kit.CREAM_ROW})
		t.name = String(sku[0])
		# the bottom of the tile holds the price (S, full width); the picture and the amount above it
		for ch in t.get_children():
			if ch is Control and not (ch is Kit.KitDecor):
				(ch as Control).position.y -= 34.0
		var id: String = sku[0]
		var b := Kit.button(t, Rect2(12, th - 5.0 - 12.0 - 60.0, tw - 24.0, 60), "gold", _price(sku[1]), {"size": "S",
			"filter": Control.MOUSE_FILTER_PASS, "cb": func(): buy_sku.emit(id)})
		b.name = "buy"


func _packs_tab() -> void:
	if not payments:
		_empty("gift", tr("shop.no_packs"))
		return
	var w := _body.size.x
	var row_h := 112.0
	var gap := 12.0
	var content_h := 16.0 + PACK_SKUS.size() * row_h + (PACK_SKUS.size() - 1) * gap + 16.0
	var well := Kit.well(_body, Rect2(0, 0, w, minf(content_h, _body.size.y)))
	var host: Control = well
	if content_h > well.size.y + 1.0:
		host = Kit.scroller(well, content_h)["inner"]
	var rw_w := w - 32.0 - (12.0 if host != well else 0.0)
	for i in PACK_SKUS.size():
		var p: Array = PACK_SKUS[i]
		var id: String = p[0]
		var price := _price(p[2]) + (tr(p[4]) if p[4] != "" else "")
		var bw := clampf(Kit.text_w(price, 26, "d900") + 44.0, 150.0, 230.0)
		var b := Kit.button(null, Rect2(0, 0, bw, 60), "gold", price, {"size": "S", "filter": Control.MOUSE_FILTER_PASS,
			"cb": func(): buy_sku.emit(id)})
		b.name = "buy"
		var name := tr(p[1])
		var desc := tr(p[3])
		var rw := Kit.row(host, Rect2(16, 16 + i * (row_h + gap), rw_w, row_h), {"icon": String(PACK_ICON.get(id, "gift")),
			"title": name, "sub": desc, "right": b})
		rw.name = id
		rw.cb = func(): Kit.tooltip(rw.title_label, name, desc)


func _atelier_tab() -> void:
	var owned: Dictionary = cases.owned_cosmetics
	var w := _body.size.x
	var c1 := Kit.chip(_body, Vector2(0, 0), "frame", tr("shop.owned") % owned.size(), "status")
	c1.name = "owned"
	var c2 := Kit.chip(_body, Vector2(c1.size.x + 12.0, 0), "xp", tr("shop.glitter") % int(cases.glitter), "status")
	c2.name = "glitter"
	if owned.is_empty():
		var l := Kit.label(tr("shop.atelier_empty"), 28, Kit.SOFT_CREAM, false)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.max_lines_visible = 3
		var top := maxf(64.0, (_body.size.y - 300.0) * 0.5)
		var ic := Kit._card_rect(Kit.icon_tex("frame"), Rect2(w * 0.5 - 72.0, top, 144, 144))
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		_body.add_child(ic)
		l.position = Vector2(40, top + 166.0)
		l.size = Vector2(w - 80.0, 132)
		_body.add_child(l)
		return
	var cols := 3
	var gap := 12.0
	var th := 200.0
	var ids: Array = owned.keys()
	var rows := ceili(ids.size() / float(cols))
	var content_h := 16.0 + rows * th + (rows - 1) * gap + 16.0
	var well := Kit.well(_body, Rect2(0, 56, w, minf(content_h, _body.size.y - 56.0)))
	var host: Control = well
	if content_h > well.size.y + 1.0:
		host = Kit.scroller(well, content_h)["inner"]
	var tw := (w - 32.0 - (12.0 if host != well else 0.0) - gap * (cols - 1)) / cols
	for i in ids.size():
		var id := String(ids[i])
		var it: Dictionary = cases.cosmetic(id)
		var rar := String(it.get("rarity", "common"))
		var t := Kit.tile(host, Rect2(16 + (i % cols) * (tw + gap), 16 + (i / cols) * (th + gap), tw, th),
			{"icon": String(Kit.COSMETIC_ICON.get(String(it.get("category", "")), "frame")), "icon_side": 96.0,
			"title": String(cases.cosmetic_name(id)), "face": (Kit.RARITY.get(rar, Kit.RARITY["common"]) as Color).lerp(Kit.CREAM_ROW, 0.55)})
		t.name = id
		var cat := String(cases.category_name(String(it.get("category", ""))))
		t.cb = func(): Kit.tooltip(t, String(cases.cosmetic_name(id)), cat + "\n" + String(cases.rarity_name(rar)))
