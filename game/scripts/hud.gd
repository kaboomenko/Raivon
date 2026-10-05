extends CanvasLayer
## HUD laid out exactly like the owner's reference frames (docs/art_direction.md §3).

const PANEL := Color(0.055, 0.085, 0.14, 0.92)
const PANEL_2 := Color(0.09, 0.13, 0.2, 0.95)
const EDGE := Color(0.32, 0.42, 0.58, 0.55)
const ACCENT := Color(0.16, 0.42, 0.95)
const GOOD := Color(0.42, 0.9, 0.48)
const TEXT := Color(0.96, 0.97, 1.0)
const MUTED := Color(0.62, 0.68, 0.78)

var world: Node3D
var font_bold: Font
var tile_title: Label
var tile_owner: Label
var tile_bonus: Label
var attack_btn: Panel
var minimap: Control
var res_labels := {}  # res -> [value Label, rate Label]
var builders_label: Label
var level_label: Label
var mail_badge: Array = []
var shop_dot: Panel  # red dot: a free crate is ready
var tab_highlight: Panel
var tab_labels := {}
var _tab_keys := {}  # tab -> translation key of its label
var _shop_lbl: Label
var _attack_lbl: Label
var _tile_set := false  # false while the tile box still shows its placeholder
var unit_cards: Control  # the Army tab content (hidden while another tab is open)

signal button_pressed(name: String)


func _ready() -> void:
	var f := SystemFont.new()
	f.font_names = PackedStringArray(["Noto Sans", "DejaVu Sans", "Roboto", "Arial"])
	f.font_weight = 800
	font_bold = f
	_build()


func _style(bg: Color, radius := 14, border := EDGE, bw := 2) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.set_corner_radius_all(radius)
	s.border_color = border
	s.set_border_width_all(bw)
	s.shadow_color = Color(0, 0, 0, 0.45)
	s.shadow_size = 6
	return s


func _label(text: String, size: int, color := TEXT, bold := true) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.7))
	l.add_theme_constant_override("outline_size", 4 if bold else 0)
	if bold:
		l.add_theme_font_override("font", font_bold)
	return l


func _panel(rect: Rect2, style: StyleBox) -> Panel:
	var p := Panel.new()
	p.position = rect.position
	p.size = rect.size
	p.add_theme_stylebox_override("panel", style)
	add_child(p)
	return p


func _build() -> void:
	var vw := 941.0
	var vh := 1672.0

	# ---- top resource bar (live values from the economy, set_resources)
	_panel(Rect2(108, 10, 680, 66), _style(PANEL, 12))
	var res := [["gold", "coin"], ["food", "food"], ["metal", "metal"], ["raivite", "raivite"]]
	for i in res.size():
		var x := 120.0 + i * 168.0
		var icon := TextureRect.new()
		icon.texture = load("res://assets/ui/%s.png" % res[i][1])
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.position = Vector2(x, 18)
		icon.size = Vector2(48, 48)
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(icon)
		var v := _label("—", 22)
		v.position = Vector2(x + 52, 14)
		add_child(v)
		var d := _label("", 15, GOOD, false)
		d.position = Vector2(x + 54, 42)
		add_child(d)
		res_labels[res[i][0]] = [v, d]
	_panel(Rect2(800, 10, 130, 66), _style(PANEL, 12))
	var bi := TextureRect.new()
	bi.texture = load("res://assets/ui/builder.png")
	bi.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	bi.position = Vector2(808, 18)
	bi.size = Vector2(48, 48)
	bi.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bi)
	builders_label = _label("2/2", 24)
	builders_label.position = Vector2(860, 24)
	add_child(builders_label)

	# ---- crest banner (top-left)
	var crest := Icon.new("crest")
	crest.position = Vector2(12, 4)
	crest.size = Vector2(92, 118)
	add_child(crest)

	# ---- ruler portrait + level
	_panel(Rect2(14, 132, 86, 92), _style(PANEL_2, 10, Color(0.85, 0.7, 0.35, 0.9), 3))
	var ruler := Icon.new("ruler")
	ruler.position = Vector2(18, 136)
	ruler.size = Vector2(78, 84)
	add_child(ruler)
	var lvl := Icon.new("level")
	lvl.position = Vector2(10, 196)
	lvl.size = Vector2(40, 40)
	add_child(lvl)
	var lvl_t := _label("1", 18)
	level_label = lvl_t
	lvl_t.position = Vector2(20, 203)
	add_child(lvl_t)
	_panel(Rect2(52, 212, 44, 8), _style(Color(0.15, 0.2, 0.3), 4, Color(0, 0, 0, 0), 0))
	_panel(Rect2(52, 212, 14, 8), _style(GOOD, 4, Color(0, 0, 0, 0), 0))

	# ---- left buttons
	var left := ["trophy", "book", "mail", "gear"]
	for i in left.size():
		var y := 244.0 + i * 70.0
		var lb := _panel(Rect2(16, y, 64, 60), _style(PANEL, 14))
		lb.gui_input.connect(_on_button_input.bind(left[i]))
		var ic := Icon.new(left[i])
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ic.position = Vector2(26, y + 8)
		ic.size = Vector2(44, 44)
		add_child(ic)
		if left[i] == "mail":
			var badge := Icon.new("badge")
			badge.position = Vector2(62, y - 8)
			badge.size = Vector2(26, 26)
			add_child(badge)
			var bt := _label("", 15)
			bt.position = Vector2(62, y - 6)
			bt.size = Vector2(26, 22)
			bt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			add_child(bt)
			mail_badge = [badge, bt]

	# ---- store button (below the left column)
	var sb := _panel(Rect2(16, 524, 64, 74), _style(Color(0.35, 0.2, 0.55), 14, Color(1.0, 0.8, 0.35, 0.9), 2))
	sb.gui_input.connect(_on_button_input.bind("shop"))
	var si := TextureRect.new()
	si.texture = load("res://assets/ui/raivite.png")
	si.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	si.position = Vector2(26, 528)
	si.size = Vector2(44, 44)
	si.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(si)
	var sl := _label(tr("hud.shop"), 14)
	_shop_lbl = sl
	sl.position = Vector2(16, 572)
	sl.size = Vector2(64, 22)
	sl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(sl)
	shop_dot = Panel.new()
	shop_dot.add_theme_stylebox_override("panel", _style(Color(0.9, 0.2, 0.15), 9, Color(1, 1, 1, 0.9), 2))
	shop_dot.position = Vector2(66, 518)
	shop_dot.size = Vector2(18, 18)
	shop_dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	shop_dot.visible = false
	add_child(shop_dot)

	# ---- minimap (top-right)
	var mm_panel := _panel(Rect2(730, 90, 198, 206), _style(PANEL, 12, Color(0.4, 0.5, 0.65, 0.8)))
	var mm := Minimap.new()
	mm.world = world
	mm.position = Vector2(740, 100)
	mm.size = Vector2(178, 186)
	add_child(mm)
	minimap = mm

	# ---- right buttons
	var right := ["target", "pin", "fort", "tower"]
	for i in right.size():
		var y := 312.0 + i * 74.0
		var rb := _panel(Rect2(864, y, 62, 62), _style(PANEL, 14))
		rb.gui_input.connect(_on_button_input.bind(right[i]))
		var ic := Icon.new(right[i])
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ic.position = Vector2(873, y + 9)
		ic.size = Vector2(44, 44)
		add_child(ic)

	# ---- bottom tabs + unit cards
	var base_y := vh - 276.0
	_panel(Rect2(0, base_y, 640, 276), _style(PANEL, 16))
	var tabs := [["tab.buildings", "castle_icon", "buildings"], ["tab.army", "helmet", "army"], ["tab.development", "hammer", "development"], ["tab.diplomacy", "hands", "diplomacy"], ["tab.world", "scales", "world"]]
	tab_highlight = _panel(Rect2(8 + 126 + 2, base_y + 6, 120, 76), _style(Color(0.12, 0.2, 0.34), 10, Color(0.35, 0.55, 0.95, 0.9)))
	tab_highlight.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for i in tabs.size():
		var x := 8.0 + i * 126.0
		var hit := _panel(Rect2(x + 2, base_y + 6, 120, 76), StyleBoxEmpty.new())
		hit.gui_input.connect(_on_button_input.bind("tab_" + tabs[i][2]))
		var ic := Icon.new(tabs[i][1])
		ic.position = Vector2(x + 44, base_y + 14)
		ic.size = Vector2(36, 34)
		add_child(ic)
		var t := _label(tr(tabs[i][0]), 16, TEXT if i == 1 else MUTED, i == 1)
		t.position = Vector2(x + 10, base_y + 50)
		t.size = Vector2(108, 24)
		t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		add_child(t)
		tab_labels[tabs[i][2]] = t
		_tab_keys[tabs[i][2]] = tabs[i][0]
	unit_cards = Control.new()
	unit_cards.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(unit_cards)
	var units := [["squad_blue", "320", "20"], ["archer", "180", "15"], ["knight_blue", "40", "60"], ["catapult", "12", "80"]]
	for i in units.size():
		var x := 14.0 + i * 148.0
		var card := _panel(Rect2(x, base_y + 92, 136, 172), _style(PANEL_2, 12, Color(0.4, 0.5, 0.65, 0.7)))
		remove_child(card)
		unit_cards.add_child(card)
		var portrait := Portrait.new(units[i][0])
		portrait.position = Vector2(x + 6, base_y + 98)
		portrait.size = Vector2(124, 104)
		unit_cards.add_child(portrait)
		var n := _label(units[i][1], 22)
		n.position = Vector2(x, base_y + 204)
		n.size = Vector2(136, 28)
		n.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		unit_cards.add_child(n)
		var ci := Icon.new("coin")
		ci.position = Vector2(x + 40, base_y + 236)
		ci.size = Vector2(22, 22)
		unit_cards.add_child(ci)
		var c := _label(units[i][2], 18, TEXT)
		c.position = Vector2(x + 66, base_y + 234)
		unit_cards.add_child(c)

	# ---- tile info + attack button
	_panel(Rect2(652, base_y, 280, 140), _style(PANEL, 16))
	var tile := Icon.new("tile")
	tile.position = Vector2(664, base_y + 14)
	tile.size = Vector2(70, 60)
	add_child(tile)
	var tn := _label(tr("terrain.plain"), 21)
	tile_title = tn
	tn.position = Vector2(746, base_y + 18)
	add_child(tn)
	var to := _label(tr("tile.your_territory"), 17, Color(0.45, 0.7, 1.0), false)
	tile_owner = to
	to.position = Vector2(746, base_y + 48)
	add_child(to)
	var shield := Icon.new("plus")
	shield.position = Vector2(674, base_y + 92)
	shield.size = Vector2(28, 28)
	add_child(shield)
	var bonus := _label(tr("hud.tile_bonus"), 18, TEXT, false)
	tile_bonus = bonus
	bonus.position = Vector2(712, base_y + 92)
	add_child(bonus)
	var btn := _panel(Rect2(660, vh - 122, 266, 92), _style(Color(0.13, 0.4, 0.9), 16, Color(0.55, 0.75, 1.0), 3))
	attack_btn = btn
	var sw := Icon.new("swords")
	sw.position = Vector2(684, vh - 104)
	sw.size = Vector2(54, 54)
	add_child(sw)
	var at := _label(tr("hud.attack"), 28)
	_attack_lbl = at
	at.position = Vector2(748, vh - 98)
	add_child(at)


## Sets `text`, shrinking the font from `base` (down to 12) until it fits `max_w` px — long hex and state
## names differ a lot between languages.
func _fit(l: Label, text: String, max_w: float, base: int) -> void:
	var f := l.get_theme_font("font")
	var s := base
	while s > 12 and f.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, s).x > max_w:
		s -= 1
	l.add_theme_font_size_override("font_size", s)
	l.text = text


## Re-applies the static labels after a language switch (the rest is refreshed by the game every tick).
func retranslate() -> void:
	_shop_lbl.text = tr("hud.shop")
	_attack_lbl.text = tr("hud.attack")
	if not _tile_set:
		tile_title.text = tr("terrain.plain")
		tile_owner.text = tr("tile.your_territory")
		tile_bonus.text = tr("hud.tile_bonus")
	for k in tab_labels:
		(tab_labels[k] as Label).text = tr(String(_tab_keys[k]))


func _on_button_input(e: InputEvent, name: String) -> void:
	if (e is InputEventScreenTouch and not e.pressed) or (e is InputEventMouseButton and not e.pressed and e.button_index == MOUSE_BUTTON_LEFT):
		button_pressed.emit(name)


static func fmt(v: int) -> String:
	if absi(v) >= 1000000:
		return "%.1fM" % (v / 1000000.0)
	if absi(v) >= 10000:
		return "%dK" % (v / 1000)
	if absi(v) >= 1000:
		return "%.1fK" % (v / 1000.0)
	return str(v)


## Top bar: stored amounts (orange when the warehouse is full), net income per hour, free builders.
func set_resources(res: Dictionary, per_hour: Dictionary, caps: Dictionary, free_builders: int, builders: int) -> void:
	for r in res_labels:
		var v: Label = res_labels[r][0]
		var d: Label = res_labels[r][1]
		var amount: int = res.get(r, 0)
		v.text = fmt(amount)
		var full: bool = caps.has(r) and amount >= int(caps[r])
		v.add_theme_color_override("font_color", Color(1.0, 0.7, 0.3) if full else TEXT)
		if r == "raivite":
			d.text = ""
		else:
			var ph: int = per_hour.get(r, 0)
			d.text = (tr("hud.per_hour") % ["+" if ph >= 0 else "", fmt(ph)]) if not full else tr("hud.storage_full")
			d.add_theme_color_override("font_color", GOOD if ph >= 0 and not full else Color(1.0, 0.55, 0.4))
	builders_label.text = "%d/%d" % [free_builders, builders]


func set_mail(unread: int) -> void:
	for n in mail_badge:
		(n as Control).visible = unread > 0
	(mail_badge[1] as Label).text = str(mini(unread, 9))


func set_level(dl: int) -> void:
	level_label.text = str(dl)


func select_tab(key: String) -> void:
	var keys := tab_labels.keys()
	var i := keys.find(key)
	if i < 0:
		return
	tab_highlight.position.x = 8 + i * 126 + 2
	for k in tab_labels:
		var l: Label = tab_labels[k]
		l.add_theme_color_override("font_color", TEXT if k == key else MUTED)
	unit_cards.visible = false  # the Army tab content now comes from the game (game_ui.show_armies)


func show_tile(info: Dictionary) -> void:
	_tile_set = true
	_fit(tile_title, String(info["title"]), 176.0, 21)
	_fit(tile_owner, String(info["owner"]), 176.0, 17)
	tile_owner.add_theme_color_override("font_color", info["owner_color"])
	_fit(tile_bonus, String(info["bonus"]), 210.0, 18)
	attack_btn.modulate = Color(1, 1, 1, 1.0 if info["attackable"] else 0.45)


# ====================================================================== icons drawn in code

class Icon extends Control:
	var kind: String

	func _init(k: String) -> void:
		kind = k
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var w := size.x
		var h := size.y
		var c := size / 2
		match kind:
			"coin":
				draw_circle(c, w * 0.46, Color(0.75, 0.5, 0.08))
				draw_circle(c, w * 0.4, Color(1.0, 0.78, 0.2))
				draw_circle(c, w * 0.28, Color(0.95, 0.68, 0.12))
				draw_arc(c, w * 0.28, 0, TAU, 24, Color(1, 0.9, 0.5), 2)
			"wood":
				for i in 3:
					var y := h * (0.35 + i * 0.18) - (h * 0.09 if i == 2 else 0.0)
					var x := w * (0.12 + (0.18 if i == 2 else 0.0))
					draw_rect(Rect2(x, y - h * 0.08, w * 0.62, h * 0.16), Color(0.55, 0.33, 0.16))
					draw_circle(Vector2(x + w * 0.62, y), h * 0.09, Color(0.85, 0.62, 0.35))
					draw_circle(Vector2(x + w * 0.62, y), h * 0.05, Color(0.65, 0.42, 0.2))
			"stone":
				draw_colored_polygon(PackedVector2Array([Vector2(w * .1, h * .7), Vector2(w * .35, h * .3), Vector2(w * .65, h * .35), Vector2(w * .55, h * .8)]), Color(0.62, 0.64, 0.68))
				draw_colored_polygon(PackedVector2Array([Vector2(w * .45, h * .78), Vector2(w * .6, h * .4), Vector2(w * .9, h * .5), Vector2(w * .85, h * .82)]), Color(0.8, 0.82, 0.85))
			"wheat":
				draw_line(Vector2(w * .3, h * .9), Vector2(w * .7, h * .15), Color(0.85, 0.65, 0.2), 3)
				for i in 5:
					var t := 0.25 + i * 0.12
					var p := Vector2(w * .3, h * .9).lerp(Vector2(w * .7, h * .15), t)
					draw_circle(p + Vector2(-5, 0), 4.5, Color(0.98, 0.78, 0.3))
					draw_circle(p + Vector2(5, 2), 4.5, Color(0.92, 0.7, 0.25))
			"crystal":
				draw_colored_polygon(PackedVector2Array([Vector2(w * .5, h * .05), Vector2(w * .88, h * .38), Vector2(w * .5, h * .95), Vector2(w * .12, h * .38)]), Color(0.3, 0.6, 1.0))
				draw_colored_polygon(PackedVector2Array([Vector2(w * .5, h * .05), Vector2(w * .65, h * .38), Vector2(w * .5, h * .95), Vector2(w * .35, h * .38)]), Color(0.6, 0.85, 1.0))
			"people":
				draw_circle(Vector2(w * .38, h * .32), w * .16, MUTED_C)
				draw_rect(Rect2(w * .14, h * .52, w * .48, h * .36), MUTED_C)
				draw_circle(Vector2(w * .7, h * .36), w * .12, MUTED_C)
				draw_rect(Rect2(w * .58, h * .54, w * .32, h * .3), MUTED_C)
			"crest":
				var pts := PackedVector2Array([Vector2(w * .08, 0), Vector2(w * .92, 0), Vector2(w * .92, h * .8), Vector2(w * .5, h * .98), Vector2(w * .08, h * .8)])
				draw_colored_polygon(pts, Color(0.12, 0.3, 0.75))
				draw_polyline(pts + PackedVector2Array([pts[0]]), Color(0.9, 0.75, 0.35), 4)
				_eagle(Vector2(w * .5, h * .42), w * .32)
			"ruler":
				draw_rect(Rect2(0, 0, w, h), Color(0.25, 0.3, 0.42))
				draw_circle(Vector2(w * .5, h * .5), w * .24, Color(0.92, 0.72, 0.56))
				draw_rect(Rect2(w * .2, h * .74, w * .6, h * .26), Color(0.2, 0.32, 0.7))
				draw_colored_polygon(PackedVector2Array([Vector2(w * .28, h * .3), Vector2(w * .34, h * .12), Vector2(w * .42, h * .24), Vector2(w * .5, h * .08), Vector2(w * .58, h * .24), Vector2(w * .66, h * .12), Vector2(w * .72, h * .3)]), Color(1, 0.8, 0.2))
				draw_rect(Rect2(w * .3, h * .56, w * .4, h * .18), Color(0.45, 0.3, 0.2))
			"level":
				draw_colored_polygon(_hexagon(c, w * .48), Color(0.15, 0.4, 0.9))
				draw_polyline(_hexagon(c, w * .48) + PackedVector2Array([_hexagon(c, w * .48)[0]]), Color(0.7, 0.85, 1), 2)
			"trophy":
				draw_colored_polygon(PackedVector2Array([Vector2(w * .25, h * .15), Vector2(w * .75, h * .15), Vector2(w * .65, h * .55), Vector2(w * .35, h * .55)]), GOLD_C)
				draw_rect(Rect2(w * .45, h * .55, w * .1, h * .2), GOLD_C)
				draw_rect(Rect2(w * .3, h * .75, w * .4, h * .1), GOLD_C)
			"book":
				draw_rect(Rect2(w * .12, h * .2, w * .36, h * .6), Color(0.95, 0.85, 0.55))
				draw_rect(Rect2(w * .52, h * .2, w * .36, h * .6), Color(0.9, 0.78, 0.45))
				draw_line(Vector2(w * .5, h * .2), Vector2(w * .5, h * .8), Color(0.5, 0.35, 0.15), 3)
			"mail":
				draw_rect(Rect2(w * .1, h * .25, w * .8, h * .5), Color(0.92, 0.78, 0.45))
				draw_polyline(PackedVector2Array([Vector2(w * .1, h * .25), Vector2(w * .5, h * .55), Vector2(w * .9, h * .25)]), Color(0.6, 0.45, 0.2), 3)
			"gear":
				draw_circle(c, w * .3, Color(0.78, 0.8, 0.85))
				for i in 8:
					var a := TAU / 8 * i
					draw_line(c, c + Vector2(cos(a), sin(a)) * w * .42, Color(0.78, 0.8, 0.85), 7)
				draw_circle(c, w * .13, Color(0.08, 0.1, 0.15))
			"badge":
				draw_circle(c, w * .5, Color(0.88, 0.15, 0.15))
			"target":
				draw_arc(c, w * .32, 0, TAU, 32, TEXT_C, 3)
				draw_circle(c, w * .08, TEXT_C)
				for v in [Vector2.UP, Vector2.DOWN, Vector2.LEFT, Vector2.RIGHT]:
					draw_line(c + v * w * .22, c + v * w * .46, TEXT_C, 3)
			"pin":
				draw_colored_polygon(PackedVector2Array([Vector2(w * .1, h * .8), Vector2(w * .35, h * .45), Vector2(w * .65, h * .45), Vector2(w * .9, h * .8)]), Color(0.55, 0.62, 0.72))
				draw_circle(Vector2(w * .5, h * .3), w * .16, TEXT_C)
			"fort", "castle_icon":
				var col := TEXT_C if kind == "fort" else MUTED_C
				draw_rect(Rect2(w * .2, h * .35, w * .6, h * .5), col)
				for i in 3:
					draw_rect(Rect2(w * (.2 + i * .23), h * .2, w * .14, h * .16), col)
				draw_rect(Rect2(w * .42, h * .6, w * .16, h * .25), Color(0.06, 0.08, 0.13))
			"tower":
				draw_rect(Rect2(w * .34, h * .3, w * .32, h * .58), TEXT_C)
				draw_rect(Rect2(w * .26, h * .16, w * .48, h * .16), TEXT_C)
				for i in 3:
					draw_rect(Rect2(w * (.26 + i * .18), h * .06, w * .12, h * .12), TEXT_C)
				draw_rect(Rect2(w * .46, h * .42, w * .08, h * .18), Color(0.06, 0.08, 0.13))
			"helmet":
				draw_circle(Vector2(w * .5, h * .5), w * .34, TEXT_C)
				draw_rect(Rect2(w * .16, h * .5, w * .68, h * .35), TEXT_C)
				draw_rect(Rect2(w * .42, h * .45, w * .16, h * .4), Color(0.06, 0.08, 0.13))
			"hammer":
				draw_line(Vector2(w * .3, h * .85), Vector2(w * .62, h * .35), MUTED_C, 5)
				draw_colored_polygon(PackedVector2Array([Vector2(w * .45, h * .2), Vector2(w * .8, h * .1), Vector2(w * .9, h * .3), Vector2(w * .6, h * .45)]), MUTED_C)
			"hands":
				draw_arc(Vector2(w * .5, h * .55), w * .3, PI, TAU, 16, MUTED_C, 6)
				draw_line(Vector2(w * .2, h * .55), Vector2(w * .8, h * .55), MUTED_C, 4)
			"scales":
				draw_line(Vector2(w * .5, h * .1), Vector2(w * .5, h * .85), MUTED_C, 3)
				draw_line(Vector2(w * .15, h * .25), Vector2(w * .85, h * .25), MUTED_C, 3)
				draw_arc(Vector2(w * .22, h * .5), w * .14, 0, PI, 12, MUTED_C, 3)
				draw_arc(Vector2(w * .78, h * .5), w * .14, 0, PI, 12, MUTED_C, 3)
			"tile":
				draw_colored_polygon(_hexagon(c, w * .48), Color(0.35, 0.6, 0.25))
				draw_colored_polygon(_hexagon(c + Vector2(0, h * .08), w * .4), Color(0.45, 0.7, 0.3))
			"plus":
				draw_line(Vector2(w * .5, h * .1), Vector2(w * .5, h * .9), GOOD, 6)
				draw_line(Vector2(w * .1, h * .5), Vector2(w * .9, h * .5), GOOD, 6)
			"swords":
				draw_line(Vector2(w * .15, h * .15), Vector2(w * .85, h * .85), Color(0.92, 0.95, 1), 6)
				draw_line(Vector2(w * .85, h * .15), Vector2(w * .15, h * .85), Color(0.92, 0.95, 1), 6)
				draw_line(Vector2(w * .2, h * .62), Vector2(w * .38, h * .8), Color(0.75, 0.82, 0.95), 5)
				draw_line(Vector2(w * .8, h * .62), Vector2(w * .62, h * .8), Color(0.75, 0.82, 0.95), 5)

	const MUTED_C := Color(0.62, 0.68, 0.78)
	const TEXT_C := Color(0.96, 0.97, 1.0)
	const GOLD_C := Color(1.0, 0.78, 0.2)
	const GOOD := Color(0.42, 0.9, 0.48)

	func _hexagon(c: Vector2, r: float) -> PackedVector2Array:
		var p := PackedVector2Array()
		for k in 6:
			var a := PI / 3 * k
			p.append(c + Vector2(cos(a), sin(a)) * r)
		return p

	func _eagle(c: Vector2, s: float) -> void:
		var white := Color(0.96, 0.97, 1)
		draw_colored_polygon(PackedVector2Array([c + Vector2(0, -s * .5), c + Vector2(s * .15, -s * .1), c + Vector2(s * 1.0, -s * .55), c + Vector2(s * .7, s * .05), c + Vector2(s * .25, s * .2), c + Vector2(s * .12, s * .8), c + Vector2(-s * .12, s * .8), c + Vector2(-s * .25, s * .2), c + Vector2(-s * .7, s * .05), c + Vector2(-s * 1.0, -s * .55), c + Vector2(-s * .15, -s * .1)]), white)


# ====================================================================== 3D unit portraits rendered live

class Portrait extends SubViewportContainer:
	var model: String

	func _init(m: String) -> void:
		model = m
		stretch = true
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _ready() -> void:
		var vp := SubViewport.new()
		vp.size = Vector2i(248, 208)
		vp.own_world_3d = true
		vp.transparent_bg = false
		add_child(vp)
		var env := WorldEnvironment.new()
		var e := Environment.new()
		e.background_mode = Environment.BG_COLOR
		e.background_color = Color(0.32, 0.42, 0.58)
		e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		e.ambient_light_color = Color(0.7, 0.75, 0.85)
		e.ambient_light_energy = 0.6
		env.environment = e
		vp.add_child(env)
		var light := DirectionalLight3D.new()
		light.rotation_degrees = Vector3(-40, 35, 0)
		light.light_energy = 1.4
		vp.add_child(light)
		var path := "res://assets/models/%s.glb" % ("squad_blue" if model == "archer" else model)
		if ResourceLoader.exists(path):
			var n: Node3D = load(path).instantiate()
			vp.add_child(n)
			n.rotation.y = -0.6
		var cam := Camera3D.new()
		cam.fov = 30
		var focus := Vector3(0, 0.22, 0)
		cam.position = focus + Vector3(0.9, 0.45, 1.25) * (1.2 if model == "catapult" else 1.0)
		vp.add_child(cam)
		cam.look_at(focus)


# ====================================================================== minimap

class Minimap extends Control:
	var world: Node3D  # map_view.gd
	var view_rect := Rect2()

	func _draw() -> void:
		if world == null or world.get("sim") == null:
			return
		# fit the whole open world (it grows by chapter)
		var lo := Vector2(1e9, 1e9)
		var hi := Vector2(-1e9, -1e9)
		for cell in world.sim.cells:
			var wp: Vector3 = world.axial_to_world(cell["q"], cell["r"])
			lo = lo.min(Vector2(wp.x, wp.z))
			hi = hi.max(Vector2(wp.x, wp.z))
		var span := hi - lo + Vector2(2.0, 2.0)
		var sc := minf(size.x / span.x, size.y / span.y)
		var c := size / 2 - (lo + hi) / 2.0 * sc
		for cell in world.sim.cells:
			var p: Vector3 = world.axial_to_world(cell["q"], cell["r"])
			var col := Color(0.32, 0.36, 0.42)
			if cell["terrain"] == "water":
				col = Color(0.16, 0.32, 0.5)
			elif cell["terrain"] != "mountain":
				col = world.state_color(world.owner_of(cell)).darkened(0.15)
			var pts := PackedVector2Array()
			for i in 6:
				var a := PI / 3 * i
				pts.append(c + Vector2(p.x, p.z) * sc + Vector2(cos(a), sin(a)) * sc * 0.95)
			draw_colored_polygon(pts, col)
			if cell["controller"] != cell["owner"] and cell["controller"] != 0:
				draw_circle(c + Vector2(p.x, p.z) * sc, sc * 0.35, world.state_color(cell["controller"]))
		if view_rect.size != Vector2.ZERO:
			draw_rect(Rect2(c + view_rect.position * sc, view_rect.size * sc), Color(1, 1, 1), false, 2)
