extends CanvasLayer
## HUD frame, laid out like the owner's reference frames (docs/art_direction.md §3) in the kit's language
## (docs/ui_style.md §5, §6 HUD): resource plates on their own currency layer (above every modal dim), a soft top
## scrim instead of a dark slab, the ruler's portrait with the level hex, one family of square buttons on the
## left, the minimap well and the labelled round map tools on the right. The top group follows the safe area's
## top inset, the bottom group (tabs, tray, hex panel) the visible bottom (Kit.vb).

const CmdPortrait := preload("res://scripts/cmd_portrait.gd")
const Kit := preload("res://scripts/ui_kit.gd")
const FlagView := preload("res://scripts/flag_view.gd")
# the bottom group keeps its legacy palette until s04 / s05 rebuild it on the kit
const PANEL := Color(0.055, 0.085, 0.14, 0.92)
const EDGE := Color(0.32, 0.42, 0.58, 0.55)
const TEXT := Color(0.96, 0.97, 1.0)
const MUTED := Color(0.62, 0.68, 0.78)

## Resource plates (§4.6, §5): the icon of each resource and [x, w] in the four-plate bar (DL1–4) and in the
## five-plate bar once oil opens (DL5+). y 12, h 70.
const RES_ICON := {"gold": "coin", "food": "food", "metal": "metal", "oil": "barrel", "raivite": "raivite"}
const RES_LAYOUT_4 := {"gold": [120, 186], "food": [318, 186], "metal": [516, 186], "raivite": [714, 214]}
const RES_LAYOUT_5 := {"gold": [120, 146], "food": [278, 146], "metal": [436, 146], "oil": [594, 146], "raivite": [752, 177]}
## The left column (§5): squares 84×84 at x 16, one every 96 px; the shop is the only gold one in the HUD.
const LEFT := [["trophy", 252.0], ["book", 348.0], ["mail", 444.0], ["gear", 540.0]]
## Round map tools (§5): [signal name, icon, centre y, caption key]; centre x 885, Ø80.
const TOOLS := [["target", "swords", 356.0, "hud.tool.front"], ["pin", "pin", 468.0, "hud.tool.capital"],
	["fort", "fort", 580.0, "hud.tool.fort"], ["tower", "tower", 692.0, "hud.tool.tower"]]

var world: Node3D
var font_bold: Font
var tile_title: Label
var tile_icon: Control
var tile_pic: TextureRect
var tile_owner: Label
var tile_bonus: Label
var attack_btn: Panel
var minimap: Control
var _tab_icons := {}  # tab key -> Icon
var res_pills := {}  # res -> Kit.KitPill
var _free_builders := 0  # free / all builders: the Buildings tab badge (s04)
var _builders := 0
var level_label: Label  # the numeral of the level hex on the ruler's portrait
var ruler_face: TextureRect  # the rendered ruler portrait (assets/ui/portraits/ruler*.png), by the player's era
var _ruler_era := 1
var _ruler_frame: Panel
var _trim := ""  # brass (DL1–4) / steel (DL5–8): the only era switch in the UI (§3.2)
var mail_badge: Array = []  # [dot, number Label]
var book_badge: Array = []  # «Летопись»: rewards waiting, [dot, number Label]
var shop_dot: Control  # red dot on the shop: a free crate is ready
var _orders_chip: Panel  # the orders button (a KitButton) — hidden until today's orders exist (08 §8.6)
var _orders_lbl: Label  # «1/3» in the counter pill under it
var _orders_dot: Control  # green: an order is ready to claim
var _shop_btn: Panel
var tab_highlight: Panel
var tab_labels := {}
var _tab_keys := {}  # tab -> translation key of its label
var _attack_lbl: Label
var _tile_set := false  # false while the tile box still shows its placeholder
var _top: Control  # crest, portrait, left column, minimap, map tools: offset by the safe top inset
var _bottom: Control  # tabs, tray, hex panel: offset by VB − 1672
var _currency: CanvasLayer  # layer 3: the resource plates stay above game_ui's modal dim (layer 2)
var _pills: Control
var _scrim: TextureRect
var _buttons := {}  # name -> the frame's buttons (left column, crest, portrait, minimap)
var _tools := {}  # name -> round map tool button
var _oil_shown := -1

signal button_pressed(name: String)
var crest_flag: Control  # the realm's flag, top-left (tap — the profile)


func set_flag(f: Dictionary) -> void:
	crest_flag.set("flag", f.duplicate())
	crest_flag.queue_redraw()


func _ready() -> void:
	font_bold = Kit.font("d900")  # Rubik 900 (docs/ui_style.md §3.3)
	_build()
	get_viewport().size_changed.connect(_anchor_groups)


## The legacy palette mapped onto the kit (opaque slate surfaces, INK contour, hard shadow, lip).
func _style(bg: Color, radius := 14, border := EDGE, bw := 2) -> StyleBoxFlat:
	return Kit.legacy_style(bg, radius, border, bw)


## The ruler's portrait follows the player's era like the commanders' (a crown, a bicorne coat, a field cap, armour);
## its frame is brass up to DL4 and steel from DL5.
func set_ruler_era(dl: int) -> void:
	_set_trim("steel" if dl >= 5 else "brass")
	var era := CmdPortrait.era_of(dl)
	if ruler_face == null or era == _ruler_era:
		return
	_ruler_era = era
	var path := "res://assets/ui/portraits/ruler%s.png" % ("" if era == 1 else "_e%d" % era)
	if ResourceLoader.exists(path):
		ruler_face.texture = load(path)


func _label(text: String, size: int, color := TEXT, bold := true) -> Label:
	return Kit.label(text, size, color, bold)


func _panel(rect: Rect2, style: StyleBox, parent: Node = null) -> Panel:
	var p := Panel.new()
	p.position = rect.position
	p.size = rect.size
	p.add_theme_stylebox_override("panel", style)
	if style is StyleBoxFlat and int(style.get_meta("kit_lip", 0)) > 0 and rect.size.y >= 40.0:
		p.add_child(Kit.KitDecor.new())  # the lip / highlight line / gloss (child 0)
	(parent if parent != null else self).add_child(p)
	return p


func _group(n: String, parent: Node) -> Control:
	var g := Control.new()
	g.name = n
	g.mouse_filter = Control.MOUSE_FILTER_IGNORE
	g.size = Vector2(941, 1672)
	parent.add_child(g)
	return g


func _emit(name: String) -> void:
	button_pressed.emit(name)


func _build() -> void:
	# ---- top scrim: INK α 0.55 → 0 over y 0–150 instead of a dark slab (§5); the first child, under everything
	_scrim = TextureRect.new()
	_scrim.name = "scrim"
	_scrim.texture = Kit.vgradient(Kit.alpha(Kit.INK, 0.55), Kit.alpha(Kit.INK, 0.0))
	_scrim.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_scrim.stretch_mode = TextureRect.STRETCH_SCALE
	_scrim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_scrim.size = Vector2(941, 150)
	add_child(_scrim)
	_top = _group("top", self)
	_bottom = _group("bottom", self)
	_currency = CanvasLayer.new()
	_currency.name = "currency"
	_currency.layer = 3  # above game_ui (layer 2) and its modal dim: rewards can fly into the plates
	add_child(_currency)
	_pills = _group("pills", _currency)
	_build_pills()
	_build_crest()
	_build_left()
	_build_minimap()
	_build_tools()
	_build_bottom()
	_anchor_groups()


## Places the groups for the safe area: the top group under the status bar, the bottom group on the visible bottom
## (VB, §3.1). Runs again on every viewport size change.
func _anchor_groups() -> void:
	var top := Kit.top_inset(self)
	var vis := get_viewport().get_visible_rect()
	_top.position.y = top
	_pills.position.y = top
	_bottom.position.y = Kit.vb(self) - 1672.0
	_scrim.position = Vector2(vis.position.x, 0)
	_scrim.size = Vector2(maxf(941.0, vis.size.x), 150.0 + top)


# ---------------------------------------------------------------- resource plates (§4.6, currency layer)

func _build_pills() -> void:
	for r in ["gold", "food", "metal", "oil", "raivite"]:
		var opts := {"rate": r != "raivite"}
		if r == "raivite":
			opts["plus"] = _emit.bind("shop")  # the only «+»: opens the shop, like the shop button
		res_pills[r] = Kit.pill(_pills, Rect2(120, 12, 186, 70), String(RES_ICON[r]), opts)
	_layout_res(false)


## Lays the resource plates out: 4 across, 5 once oil appears (DL5, canon §4) with a smaller value.
func _layout_res(with_oil: bool) -> void:
	var lay: Dictionary = RES_LAYOUT_5 if with_oil else RES_LAYOUT_4
	for r in res_pills:
		var p: Kit.KitPill = res_pills[r]
		p.visible = lay.has(r)
		if not p.visible:
			continue
		p.position = Vector2(float(lay[r][0]), 12.0)
		p.size = Vector2(float(lay[r][1]), 70.0)
		p.value_size = 28 if with_oil else 32
		p.lay()


## The plates: stored amounts (exact below 10 000) with the warehouse fill (brown and a yellow number when full),
## the net income per hour, the tooltip text. Free builders are kept for the Buildings tab badge.
func set_resources(res: Dictionary, per_hour: Dictionary, caps: Dictionary, free_builders: int, builders: int) -> void:
	_free_builders = free_builders
	_builders = builders
	var with_oil := caps.has("oil")
	if int(with_oil) != _oil_shown:
		_oil_shown = int(with_oil)
		_layout_res(with_oil)
	# «+160/ч» on every plate, or «+160» on every plate when one rate does not fit (five plates, big incomes)
	var short := false
	for r in res_pills:
		var p: Kit.KitPill = res_pills[r]
		if p.visible and p.has_rate:
			short = short or not p.rate_fits(_rate_text(int(per_hour.get(r, 0)), false))
	for r in res_pills:
		var p: Kit.KitPill = res_pills[r]
		if not p.visible:
			continue
		var amount: int = int(res.get(r, 0))
		var cap: int = int(caps.get(r, 0))
		var full := cap > 0 and amount >= cap
		p.set_value(Kit.fmt_num(amount), float(amount) / float(cap) if cap > 0 else 0.0, full)
		p.tip_title = tr("res.name." + r)
		if r == "raivite":
			p.tip_text = tr("hud.tip.raivite")
			continue
		var ph: int = int(per_hour.get(r, 0))
		p.set_rate(_rate_text(ph, short), Kit.POS if ph >= 0 else Kit.NEG)
		var lines := PackedStringArray([tr("hud.tip.rate") % _rate_text(ph, false)])
		if cap > 0:
			lines.append(tr("hud.tip.cap") % [Kit.fmt_exact(amount), Kit.fmt_exact(cap)])
		lines.append(tr("hud.tip.full") if full else tr("hud.tip.src"))
		p.tip_text = "\n".join(lines)
	# one size for the numbers of the bar: the smallest any resource plate needs (raivite sizes on its own)
	var vcap := 64
	var rcap := 64
	for r in res_pills:
		var p: Kit.KitPill = res_pills[r]
		if p.visible and p.has_rate:
			vcap = mini(vcap, p.value_fit())
			rcap = mini(rcap, p.rate_fit())
	for r in res_pills:
		var p: Kit.KitPill = res_pills[r]
		if p.visible and p.has_rate:
			p.set_caps(vcap, maxi(22, mini(rcap, vcap - 2)))  # the rate stays a step under the value


## «+160/ч» (Kit.fmt_num: −8 has a real minus), or «+160» when the bar is short of room.
func _rate_text(ph: int, short: bool) -> String:
	var sign := "+" if ph >= 0 else ""
	return sign + Kit.fmt_num(ph) if short else tr("hud.per_hour") % [sign, Kit.fmt_num(ph)]


# ---------------------------------------------------------------- crest, ruler portrait, left column

func _build_crest() -> void:
	crest_flag = FlagView.new()
	crest_flag.position = Vector2(12, 4)
	crest_flag.size = Vector2(92, 118)
	crest_flag.mouse_filter = Control.MOUSE_FILTER_STOP
	crest_flag.gui_input.connect(_on_button_input.bind("profile"))
	_top.add_child(crest_flag)
	_buttons["profile"] = crest_flag
	# the ruler's portrait (the profile too, 10 §4.23): a brass / steel frame, the render on the sky (§5)
	var fr := Panel.new()
	fr.name = "ruler"
	fr.position = Vector2(14, 134)
	fr.size = Vector2(90, 96)
	fr.mouse_filter = Control.MOUSE_FILTER_STOP
	fr.gui_input.connect(_on_button_input.bind("profile"))
	_top.add_child(fr)
	fr.add_child(Kit.KitDecor.new())  # the lip (child 0)
	_ruler_frame = fr
	_buttons["ruler"] = fr
	_set_trim("brass")
	var well := Panel.new()
	well.position = Vector2(8, 8)
	well.size = Vector2(74, 72)
	var wsb := Kit.style(Kit.SKY_LOW, 14, 0, Kit.INK, 0, 0)
	wsb.set_meta("kit_kind", "")
	well.add_theme_stylebox_override("panel", wsb)
	well.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW  # the art takes the well's rounded corners
	well.mouse_filter = Control.MOUSE_FILTER_IGNORE
	fr.add_child(well)
	var sky := TextureRect.new()
	sky.texture = Kit.vgradient(Kit.SKY_TOP, Kit.SKY_LOW)
	sky.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	sky.stretch_mode = TextureRect.STRETCH_SCALE
	sky.size = well.size
	sky.mouse_filter = Control.MOUSE_FILTER_IGNORE
	well.add_child(sky)
	if ResourceLoader.exists("res://assets/ui/portraits/ruler.png"):  # the rendered king of reference frame 1
		var face := TextureRect.new()
		ruler_face = face
		face.texture = load("res://assets/ui/portraits/ruler.png")
		face.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		face.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		face.size = well.size
		face.mouse_filter = Control.MOUSE_FILTER_IGNORE
		well.add_child(face)
	var rim := Panel.new()  # an INK line between the art and the trim
	var rsb := Kit.style(Kit.alpha(Kit.INK, 0.0), 14, 3, Kit.INK, 0, 0)
	rsb.draw_center = false
	rsb.set_meta("kit_kind", "")
	rim.add_theme_stylebox_override("panel", rsb)
	rim.position = well.position
	rim.size = well.size
	rim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	fr.add_child(rim)
	# the development level: an info hex on the frame's corner (no fake XP bar)
	var hb := Kit.hex_badge(_top, Vector2(30, 224), 24, "info", "1")
	level_label = hb.get_child(0) as Label


func _set_trim(kind: String) -> void:
	if kind == _trim or _ruler_frame == null:
		return
	_trim = kind
	var sb := Kit.style(Kit.face_of(kind), 20, 4, Kit.INK, 6, 6)
	sb.set_meta("kit_kind", "")  # a frame, not a button: the lip without the gloss
	_ruler_frame.add_theme_stylebox_override("panel", sb)
	_ruler_frame.queue_redraw()


func _build_left() -> void:
	for it in LEFT:
		var n := String(it[0])
		_buttons[n] = Kit.icon_button(_top, Rect2(16, float(it[1]), 84, 84), n, "slate", false, "", _emit.bind(n))
	var md := Kit.dot(_buttons["mail"], 0, "war")
	mail_badge = [md, md.get_child(0)]
	md.visible = false
	var bd := Kit.dot(_buttons["book"], 0, "war")
	book_badge = [bd, bd.get_child(0)]
	bd.visible = false
	# the shop: the only gold button of the HUD, with its caption plate
	_shop_btn = Kit.icon_button(_top, Rect2(16, 636, 84, 84), "stall", "gold", false, tr("hud.shop"), _emit.bind("shop"))
	_buttons["shop"] = _shop_btn
	shop_dot = Kit.dot(_shop_btn, -1, "war")
	shop_dot.visible = false
	# today's orders: a square with a «1/3» counter pill and a green dot when one can be claimed
	var ob := Kit.icon_button(_top, Rect2(16, 752, 84, 84), "orders", "slate", false, "", _emit.bind("orders"))
	_buttons["orders"] = ob
	_orders_chip = ob
	var ch := 34.0
	var cnt := Panel.new()
	cnt.name = "counter"
	var csb := Kit.style(Kit.SLATE_WELL, int(ch * 0.5), 3, Kit.INK, 0, 0)
	csb.set_meta("kit_kind", "")
	cnt.add_theme_stylebox_override("panel", csb)
	cnt.position = Vector2(4, 84.0 - 14.0)
	cnt.size = Vector2(76, ch)
	cnt.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ob.add_child(cnt)
	_orders_lbl = Kit.label("0/3", 24, Kit.TEXT, true)
	_orders_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_orders_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_orders_lbl.position = Vector2(0, -1)
	_orders_lbl.size = cnt.size
	cnt.add_child(_orders_lbl)
	_orders_dot = Kit.dot(ob, -1, "go")
	_orders_dot.visible = false
	_orders_chip.visible = false


## A dot appears with BADGE_POP; hiding is immediate.
func _show_dot(d: Control, on: bool) -> void:
	if on and not d.visible:
		d.visible = true
		Kit.badge_pop(d)
	elif not on:
		d.visible = false


# ---------------------------------------------------------------- minimap, map tools

func _build_minimap() -> void:
	# a slate frame like every HUD surface, the sea well inside it clips the map and the view rectangle (§5)
	var fr := Panel.new()
	fr.name = "minimap"
	fr.position = Vector2(733, 96)
	fr.size = Vector2(196, 196)
	fr.add_theme_stylebox_override("panel", Kit.style(Kit.SLATE, 24, 4, Kit.INK, 6, 6))
	_top.add_child(fr)
	fr.add_child(Kit.KitDecor.new())
	_buttons["minimap"] = fr
	var well := Panel.new()
	well.position = Vector2(8, 8)
	well.size = Vector2(180, 174)
	var r_in := 24 - 8  # concentric with the frame's corners
	var wsb := Kit.style(Kit.SEA_WELL, r_in, 0, Kit.INK, 0, 0)
	wsb.set_meta("kit_kind", "")
	well.add_theme_stylebox_override("panel", wsb)
	well.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	well.mouse_filter = Control.MOUSE_FILTER_IGNORE
	fr.add_child(well)
	var mm := Minimap.new()
	mm.world = world
	mm.size = well.size
	mm.mouse_filter = Control.MOUSE_FILTER_IGNORE
	well.add_child(mm)
	minimap = mm


func _build_tools() -> void:
	for t in TOOLS:
		var n := String(t[0])
		var b := Kit.icon_button(_top, Rect2(845, float(t[2]) - 40.0, 80, 80), String(t[1]), "slate", true, tr(String(t[3])), _emit.bind(n))
		b.set_meta("caption_key", String(t[3]))
		_tools[n] = b


## Global rect of a round map tool (target / pin / fort / tower), for the coach.
func tool_rect(name: String) -> Rect2:
	var b: Control = _tools.get(name)
	return b.get_global_rect() if b != null else Rect2()


## Global rect of a frame element: trophy / book / mail / gear / shop / orders, profile (the crest), ruler, minimap,
## a map tool, or a resource plate by its resource (gold / food / metal / oil / raivite).
func button_rect(name: String) -> Rect2:
	var b: Control = _buttons.get(name, _tools.get(name, res_pills.get(name)))
	return b.get_global_rect() if b != null else Rect2()


# ---------------------------------------------------------------- bottom group (tabs, tray, hex panel; s04 / s05)

func _build_bottom() -> void:
	var vh := 1672.0
	var base_y := vh - 276.0
	_panel(Rect2(0, base_y, 640, 276), _style(PANEL, 16), _bottom)
	var tabs := [["tab.buildings", "castle_icon", "buildings"], ["tab.army", "helmet", "army"], ["tab.development", "hammer", "development"], ["tab.diplomacy", "hands", "diplomacy"], ["tab.world", "scales", "world"]]
	tab_highlight = _panel(Rect2(8 + 126 + 2, base_y + 6, 120, 76), _style(Color(0.12, 0.2, 0.34), 10, Color(0.35, 0.55, 0.95, 0.9)), _bottom)
	tab_highlight.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for i in tabs.size():
		var x := 8.0 + i * 126.0
		var hit := _panel(Rect2(x + 2, base_y + 6, 120, 76), StyleBoxEmpty.new(), _bottom)
		hit.gui_input.connect(_on_button_input.bind("tab_" + tabs[i][2]))
		var ic := Icon.new(tabs[i][1])
		ic.position = Vector2(x + 44, base_y + 14)
		ic.size = Vector2(36, 34)
		ic.lit = i == 1
		_bottom.add_child(ic)
		_tab_icons[tabs[i][2]] = ic
		var t := _label(tr(tabs[i][0]), 16, TEXT if i == 1 else MUTED, i == 1)
		t.position = Vector2(x + 10, base_y + 50)
		t.size = Vector2(108, 24)
		t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_bottom.add_child(t)
		tab_labels[tabs[i][2]] = t
		_tab_keys[tabs[i][2]] = tabs[i][0]

	# ---- tile info + attack button
	_panel(Rect2(652, base_y, 280, 140), _style(PANEL, 16), _bottom)
	var tile := Icon.new("tile")
	tile.position = Vector2(664, base_y + 14)
	tile.size = Vector2(70, 60)
	_bottom.add_child(tile)
	tile_icon = tile
	tile_pic = TextureRect.new()  # the rendered hex of that land (tools/blender/card_art.py tile_*)
	tile_pic.position = Vector2(658, base_y + 8)
	tile_pic.size = Vector2(84, 74)
	tile_pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	tile_pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	tile_pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bottom.add_child(tile_pic)
	var tn := _label(tr("terrain.plain"), 21)
	tile_title = tn
	tn.position = Vector2(746, base_y + 18)
	_bottom.add_child(tn)
	var to := _label(tr("tile.your_territory"), 17, Color(0.45, 0.7, 1.0), false)
	tile_owner = to
	to.position = Vector2(746, base_y + 48)
	_bottom.add_child(to)
	var shield := Icon.new("plus")
	shield.position = Vector2(674, base_y + 92)
	shield.size = Vector2(28, 28)
	_bottom.add_child(shield)
	var bonus := _label(tr("hud.tile_bonus"), 18, TEXT, false)
	tile_bonus = bonus
	bonus.position = Vector2(712, base_y + 92)
	_bottom.add_child(bonus)
	var btn := _panel(Rect2(660, vh - 122, 266, 92), _style(Color(0.13, 0.4, 0.9), 16, Color(0.55, 0.75, 1.0), 3), _bottom)
	attack_btn = btn
	var sw := Icon.new("swords")
	sw.position = Vector2(684, vh - 104)
	sw.size = Vector2(54, 54)
	_bottom.add_child(sw)
	var at := _label(tr("hud.attack"), 28)
	_attack_lbl = at
	at.position = Vector2(748, vh - 98)
	_bottom.add_child(at)


## Sets `text`, shrinking the font from `base` down through the type scale (to 20, or to `base` when a legacy
## call asks for less) until it fits `max_w` px — long hex and state names differ a lot between languages. A text
## that does not fit even then is cut with an ellipsis at `max_w` (Kit.fit_label).
func _fit(l: Label, text: String, max_w: float, base: int) -> void:
	l.text = text
	Kit.fit_label(l, base, max_w)


## Re-applies the static labels after a language switch (the rest is refreshed by the game every tick).
func retranslate() -> void:
	Kit.icon_caption(_shop_btn, tr("hud.shop"))
	for n in _tools:
		var b: Kit.KitButton = _tools[n]
		Kit.icon_caption(b, tr(String(b.get_meta("caption_key"))))
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


## 8 620 / 12,4K / 1,2M (docs/ui_style.md §3.7).
static func fmt(v: int) -> String:
	return Kit.fmt_num(v)


func set_mail(unread: int) -> void:
	_show_dot(mail_badge[0], unread > 0)
	(mail_badge[1] as Label).text = str(mini(unread, 99))


func set_orders(text: String, ready: bool, shown: bool) -> void:
	_orders_chip.visible = shown
	_orders_lbl.text = text
	_show_dot(_orders_dot, shown and ready)


func set_book(n: int) -> void:
	if book_badge.is_empty():
		return
	_show_dot(book_badge[0], n > 0)
	(book_badge[1] as Label).text = str(mini(n, 99))


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
		# only the selected tab is bold with an outline
		l.add_theme_constant_override("outline_size", 4 if k == key else 0)
		if k == key:
			l.add_theme_font_override("font", font_bold)
		else:
			l.remove_theme_font_override("font")
		if _tab_icons.has(k):
			(_tab_icons[k] as Icon).lit = k == key
			(_tab_icons[k] as Icon).queue_redraw()


func show_tile(info: Dictionary) -> void:
	_tile_set = true
	var key := String(info.get("tile", "plain"))
	var pic := "res://assets/ui/cards/tile_%s.png" % key
	if not ResourceLoader.exists(pic):  # an era tile ("capital_dl4_red") falls back to the kind's own picture
		pic = "res://assets/ui/cards/tile_%s.png" % key.get_slice("_dl", 0)
	if not ResourceLoader.exists(pic):
		pic = "res://assets/ui/cards/tile_plain.png"
	var has_pic := ResourceLoader.exists(pic)
	tile_pic.texture = load(pic) if has_pic else null
	tile_icon.visible = not has_pic
	_fit(tile_title, String(info["title"]), 176.0, 21)
	_fit(tile_owner, String(info["owner"]), 176.0, 17)
	tile_owner.add_theme_color_override("font_color", info["owner_color"])
	_fit(tile_bonus, String(info["bonus"]), 210.0, 18)
	attack_btn.modulate = Color(1, 1, 1, 1.0 if info["attackable"] else 0.45)


# ====================================================================== icons

## A rendered 3D icon (tools/blender/icon_assets.py → assets/ui/icons) drawn exactly in its box (§3.5: no 1.15×
## overflow). Only the hex panel's «tile» placeholder still has a vector stand-in (s05 removes it).
class Icon extends Control:
	var kind: String
	var lit := false  # tab icons: the selected tab's (unselected ones are not dimmed, §3.5)
	var _tex: Texture2D

	func _init(k: String) -> void:
		kind = k
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		var p := "res://assets/ui/icons/%s.png" % k
		if ResourceLoader.exists(p):
			_tex = load(p)

	func _draw() -> void:
		var c := size / 2
		if _tex != null:
			var side := minf(size.x, size.y)
			draw_texture_rect(_tex, Rect2(c - Vector2(side, side) / 2.0, Vector2(side, side)), false)
			return
		if kind == "tile":
			draw_colored_polygon(_hexagon(c, size.x * .48), Kit.GRASS.darkened(0.25))
			draw_colored_polygon(_hexagon(c + Vector2(0, size.y * .08), size.x * .4), Kit.GRASS)

	func _hexagon(c: Vector2, r: float) -> PackedVector2Array:
		var p := PackedVector2Array()
		for k in 6:
			var a := PI / 3 * k
			p.append(c + Vector2(cos(a), sin(a)) * r)
		return p


# ====================================================================== minimap

## The whole open world in the states' colours on the sea well, each hex with a light top edge; the camera's view
## is a rounded white frame over an INK one, clipped by the well.
class Minimap extends Control:
	var world: Node3D  # map_view.gd
	var view_rect := Rect2()
	var _sb := StyleBoxFlat.new()

	func _init() -> void:
		_sb.draw_center = false
		_sb.anti_aliasing = true
		_sb.corner_detail = 8

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
		var water := Kit.SEA_WELL.lightened(0.1)
		for cell in world.sim.cells:
			var p: Vector3 = world.axial_to_world(cell["q"], cell["r"])
			var col := Kit.MAP_ROCK
			if cell["terrain"] == "water":
				col = water
			elif cell["terrain"] != "mountain":
				col = world.state_color(world.owner_of(cell))
			var pts := PackedVector2Array()
			var o := c + Vector2(p.x, p.z) * sc
			for i in 6:
				var a := PI / 3 * i
				pts.append(o + Vector2(cos(a), sin(a)) * sc * 0.94)
			draw_colored_polygon(pts, col)
			if cell["terrain"] != "water":  # the upper edges catch the light, like the tiles on the map
				draw_polyline(PackedVector2Array([pts[3], pts[4], pts[5], pts[0]]), col.lightened(0.35), 1.0, true)
			if cell["controller"] != cell["owner"] and cell["controller"] != 0:
				draw_circle(o, sc * 0.35, world.state_color(cell["controller"]))
		if view_rect.size != Vector2.ZERO:
			var r := Rect2(c + view_rect.position * sc, view_rect.size * sc)
			_frame(r.grow(3.0), Kit.INK, 6, 11)
			_frame(r.grow(1.5), Kit.WHITE, 3, 8)

	func _frame(r: Rect2, col: Color, w: int, rad: int) -> void:
		_sb.border_color = col
		_sb.set_border_width_all(w)
		_sb.set_corner_radius_all(rad)
		draw_style_box(_sb, r)
