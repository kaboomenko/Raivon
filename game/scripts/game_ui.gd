extends CanvasLayer
## Mode-dependent game UI layered over the static HUD frame (hud.gd): control bar, battle hand,
## action button, result modal, peace parchment, ceremony counters. Emits intents; game.gd decides.

signal action_pressed(kind: String)
signal card_drop(card: String, screen: Vector2)
signal card_drag(card: String, screen: Vector2, active: bool)
signal demand_toggled(id: String)
signal seal_done
signal building_upgrade(id: int)
signal building_speedup(id: int)
signal army_action(id: int, kind: String)
signal diplomacy_action(state: int, kind: String)
signal world_action(id: String)
signal research_start(line: String)
signal plunder_selected(level: int)
signal research_speedup(line: String)
signal market_open

const PANEL := Color(0.055, 0.085, 0.14, 0.95)
const EDGE := Color(0.32, 0.42, 0.58, 0.6)
const TEXT := Color(0.96, 0.97, 1.0)
const MUTED := Color(0.62, 0.68, 0.78)
const VW := 941.0
const VH := 1672.0
const CARD_ORDER := ["attack", "breakthrough", "airstrike", "encircle", "defense"]
var _locked := {}  # card -> DL it opens at
var _hand_order: Array = []
const CARD_NAME_KEYS := {"attack": "card.attack", "breakthrough": "card.breakthrough", "airstrike": "card.airstrike", "encircle": "card.encircle", "defense": "card.defense", "corps": "card.corps", "landing": "card.landing", "missile": "card.missile"}
const L := preload("res://scripts/l10n.gd")
const CmdPortrait := preload("res://scripts/cmd_portrait.gd")
const HudScript := preload("res://scripts/hud.gd")
const FlagView := preload("res://scripts/flag_view.gd")
const Kit := preload("res://scripts/ui_kit.gd")
const OrdersSim := preload("res://scripts/sim/orders.gd")  ## the order codes (World cards' short names)
const WeeklySim := preload("res://scripts/sim/weekly.gd")  ## the week's task codes
const ChronicleSim := preload("res://scripts/sim/chronicle.gd")  ## the Chronicle's goals (rewards, ladders)
const CasesSim := preload("res://scripts/sim/cases.gd")  ## names of commanders and cosmetics (pass rewards)

var font_bold: Font
var root: Control
var _top: Control  # the war bar's group: moved down by the safe top inset (§3.1)
var _control_bar: Control
var _control_track: Panel  # the enemy's part of the war bar (the whole inner track)
var _control_fill: Panel  # the player's part, from the left: 484 px × control
var _control_lbl: Label
var _control_lbl2: Label
var _score_chip: Panel  # the signed war score under the junction
var _score_txt := ""
var _laststand: Panel  # the «Последний рубеж» chip
var _war_flags: Array = []  # [player FlagView, enemy FlagView] in the round chips at the ends of the war bar
var _war_swords: TextureRect  # the junction
var _bar_colors: Array = []
var _battle: Control
var _energy_lbl: Label
var _energy_segs: Array = []  # the fill of each energy pip (a clipping Control sized from the bottom)
var _cards := {}  # card -> its Panel (child Label "cd": the cooldown seconds)
var _card_names := {}  # card -> name Label (re-translated on a language switch)
var _card_look := {}  # card -> {art, cost, veil, lock, state}: the parts set_battle / set_locked restyle
var _timer_lbl: Label
var _action: Control  # the status slot: the status button or the battle timer plate (visible while its kind is not "")
var _action_kind := ""
var _action2: Control  # the big button (Kit.KitButton)
var _action2_kind := ""
var _modal: Control
var _bottom: Control  # the bottom group (card row, battle hand, status / big buttons): moved to VB − 1672 (§3.1)
var _drag_card := ""
var _ghost: Control  # the dragged card: its art at 0.9× with a shadow and the name
var _ghost_name: Label
var _ghost_art: TextureRect
var _trim := "brass"  # the leader portrait frames: brass (DL1–4) / steel (DL5–8), §3.2


func _ready() -> void:
	layer = 2
	font_bold = Kit.font("d900")  # Rubik 900 (docs/ui_style.md §3.3)
	root = Control.new()
	root.size = Vector2(VW, VH)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	_bottom = Control.new()
	_bottom.name = "bottom"
	_bottom.size = Vector2(VW, VH)
	_bottom.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_bottom)
	_build_control_bar()
	_build_battle()
	_build_action()
	_build_ghost()
	get_viewport().size_changed.connect(_anchor_bottom)
	_anchor_bottom()


## The bottom group follows the visible bottom (VB, §3.1) like the HUD's tabs and tray under it.
func _anchor_bottom() -> void:
	_bottom.position.y = Kit.vb(self) - VH
	_top.position.y = Kit.top_inset(self)


# ------------------------------------------------------------------ helpers

## The legacy palette mapped onto the kit (opaque slate / cream / role faces, INK contour, hard shadow, lip).
## Callers may still mutate the result (shadow_size, corner radii).
func _style(bg: Color, radius := 14, border := EDGE, bw := 2) -> StyleBoxFlat:
	return Kit.legacy_style(bg, radius, border, bw)


func _label(text: String, size: int, color := TEXT, bold := true) -> Label:
	return Kit.label(text, size, color, bold)


## Shrinks the label's font from `base` down through the type scale (to 20, or to `base` when a legacy call
## asks for less) until its one-line text fits `max_w` px: captions differ in length between languages. A text
## that does not fit even then is cut with an ellipsis at `max_w` (Kit.fit_label).
func _fit(l: Label, base: int, max_w: float) -> void:
	Kit.fit_label(l, base, max_w)


func _panel(parent: Control, rect: Rect2, style: StyleBox, filter := Control.MOUSE_FILTER_STOP) -> Panel:
	var p := Panel.new()
	p.position = rect.position
	p.size = rect.size
	p.add_theme_stylebox_override("panel", style)
	p.mouse_filter = filter
	if style is StyleBoxFlat and int(style.get_meta("kit_lip", 0)) > 0 and rect.size.y >= 40.0:
		p.add_child(Kit.KitDecor.new())  # the lip / highlight line / gloss (child 0)
	parent.add_child(p)
	return p


func _at(l: Control, parent: Control, pos: Vector2, size := Vector2.ZERO) -> Control:
	l.position = pos
	if size != Vector2.ZERO:
		l.size = size
	parent.add_child(l)
	return l


## Pictographs that are drawn as the rendered 3D icons inside rows (paths kept for the call sites that use them;
## the full mapping, vector chrome included, is Kit.PICTO / Kit.split_icons).
const INLINE_ICONS := {"💎": "res://assets/ui/raivite.png", "🔒": "res://assets/ui/icons/lock.png", "🎬": "res://assets/ui/icons/ad.png"}


## A rendered icon in a square box. `path` is a res:// path or a kit icon name (Kit.icon_tex, with stand-ins).
func _icon_rect(path: String, side: float) -> TextureRect:
	var ic := TextureRect.new()
	if path.begins_with("res://"):
		ic.texture = load(path) if ResourceLoader.exists(path) else Kit.icon_tex(path.get_file().get_basename())
	else:
		ic.texture = Kit.icon_tex(path)
	ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	ic.custom_minimum_size = Vector2(side, side)
	ic.size = Vector2(side, side)
	ic.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return ic


## A window title with its rendered 3D icon in front (1.4× the text size, 12 px before the text).
func _title(parent: Control, text: String, size: int, color: Color, pos: Vector2, icon: String, bold := true, max_w := 0.0) -> Label:
	var tex := Kit.icon_tex(icon)
	if tex != null:
		var side := roundf(size * 1.4)
		var ic := _icon_rect(icon, side)
		ic.position = pos + Vector2(0, Kit.snap_size(size) * 0.7 - side / 2.0)  # centred on the first text line
		parent.add_child(ic)
		pos.x += side + 12.0
		max_w -= side + 12.0
	var l := _label(text, size, color, bold)
	if max_w > 0.0:
		_fit(l, size, max_w)
	return _at(l, parent, pos) as Label


func _has_inline(text: String) -> bool:
	for p in Kit.split_icons(text):
		if not (p as Dictionary).has("t"):
			return true
	return false


## One line of text whose pictographs are drawn as the 3D icons / vector chrome; the font steps down the type
## scale (to 20) to fit max_w.
func _inline(text: String, size: int, color := TEXT, bold := true, max_w := 0.0) -> HBoxContainer:
	var parts := Kit.split_icons(text)
	var kind := ("d900" if Kit.snap_size(size) >= 26 else "d800") if bold else "b800"
	var s: int = Kit.snap_size(size) if size >= 21 else size
	var cut := false  # even the floor does not fit: the text pieces are cut with an ellipsis inside max_w
	if max_w > 0.0:
		var steps := Kit.fit_steps(size, mini(Kit.FIT_FLOOR, size))
		s = steps[-1]
		cut = true
		for v in steps:
			var w := 0.0
			for p in parts:
				w += (Kit.text_w(String(p["t"]), v, kind, bold) if p.has("t") else v * 1.2) + 6.0
			if w <= max_w:
				s = v
				cut = false
				break
	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 6)
	hb.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for p in parts:
		if p.has("i"):
			hb.add_child(_icon_rect(String(p["i"]), roundf(s * 1.2)))
		elif p.has("v"):
			var sh := Kit.KitShape.new(String(p["v"]))
			sh.custom_minimum_size = Vector2(roundf(s * 1.1), roundf(s * 1.1))
			sh.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			hb.add_child(sh)
		else:
			var l := _label(String(p["t"]), s, color, bold)
			l.add_theme_font_size_override("font_size", s)
			l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			l.size_flags_vertical = Control.SIZE_FILL
			if cut:
				l.clip_text = true
				l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
				l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				l.size_flags_stretch_ratio = maxf(1.0, Kit.text_w(l.text, s, kind, bold))
			hb.add_child(l)
	if cut:
		hb.size.x = max_w
	return hb


# ------------------------------------------------------------------ control bar (war, §5)

const BAR_RECT := Rect2(176, 106, 492, 44)  # the war bar: INK R 22, inside it a 484×36 track
const BAR_IN := 484.0
const BAR_X0 := 180.0  # where the player's fill starts (the bar's left + 4)
const FLAG_CHIPS := [Vector2(152, 128), Vector2(692, 128)]  # round SLATE Ø64 chips with the two flags
const FLAG_D := 64.0


## The war bar (§5): the two flags in round chips at the ends, the INK bar between them — the player's colour from
## the left (`_control_fill`, 484 px × control), the enemy's for the rest — the percentages inside both ends, the
## swords on the junction, the signed war score in a chip under it and «Последний рубеж» on the right under the bar.
func _build_control_bar() -> void:
	_top = Control.new()
	_top.name = "top"
	_top.size = Vector2(VW, 200)
	_top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_top)
	_control_bar = Control.new()
	_control_bar.name = "control_bar"
	_control_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_top.add_child(_control_bar)
	var body := Panel.new()
	var bsb := Kit.style(Kit.INK, int(BAR_RECT.size.y * 0.5), 0, Kit.INK, 4, 0)  # a pill (h/2)
	bsb.set_meta("kit_kind", "")
	body.add_theme_stylebox_override("panel", bsb)
	body.position = BAR_RECT.position
	body.size = BAR_RECT.size
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_control_bar.add_child(body)
	_control_track = _bar_part(body, BAR_IN)
	_control_fill = _bar_part(body, BAR_IN * 0.5)
	_set_bar_colors([Kit.face_of("info"), Kit.face_of("war")])
	var gloss := Panel.new()  # the bars' gloss strip (§4.7): white α 0.3 over the top 30 % of the track
	var gsb := Kit.style(Kit.alpha(Kit.WHITE, 0.3), 8, 0, Kit.INK, 0, 0)
	gsb.set_meta("kit_kind", "")
	gloss.add_theme_stylebox_override("panel", gsb)
	gloss.position = Vector2(18, 8)
	gloss.size = Vector2(BAR_IN - 28.0, 9)
	gloss.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(gloss)
	_control_lbl = _bar_pct(Vector2(BAR_RECT.position.x + 18.0, BAR_RECT.position.y), HORIZONTAL_ALIGNMENT_LEFT)
	_control_lbl2 = _bar_pct(Vector2(BAR_RECT.end.x - 18.0 - 110.0, BAR_RECT.position.y), HORIZONTAL_ALIGNMENT_RIGHT)
	_war_swords = TextureRect.new()
	_war_swords.name = "swords"
	_war_swords.texture = Kit.icon_tex("swords")
	_war_swords.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_war_swords.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_war_swords.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_war_swords.size = Vector2(56, 56)
	_war_swords.position = Vector2(BAR_X0 + BAR_IN * 0.5 - 28.0, 100)
	_control_bar.add_child(_war_swords)
	for c in FLAG_CHIPS:
		var chip := Panel.new()
		var csb := Kit.style(Kit.SLATE, int(FLAG_D * 0.5), 4, Kit.INK, 4, 0)  # round
		csb.set_meta("kit_kind", "")
		chip.add_theme_stylebox_override("panel", csb)
		chip.size = Vector2(FLAG_D, FLAG_D)
		chip.position = (c as Vector2) - chip.size * 0.5
		chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_control_bar.add_child(chip)
		var fv := FlagView.new(FlagView.DEFAULT)
		fv.position = Vector2(14, 9)
		fv.size = Vector2(36, 46)
		fv.mouse_filter = Control.MOUSE_FILTER_IGNORE
		chip.add_child(fv)
		_war_flags.append(fv)
	_laststand = Kit.caption_pill(_control_bar, tr("ui.last_stand"), 30.0, Kit.face_of("war"), 22, 3)
	_laststand.name = "last_stand"
	_laststand.position = Vector2(BAR_RECT.end.x - _laststand.size.x, 152)
	_laststand.visible = false
	_control_bar.visible = false


## A part of the war bar's track: a pill with a darker bottom (§4.7), inside the INK body.
func _bar_part(body: Control, w: float) -> Panel:
	var p := Panel.new()
	p.position = Vector2(4, 4)
	p.size = Vector2(w, 36)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(p)
	return p


func _set_bar_colors(colors: Array) -> void:
	if colors == _bar_colors:
		return
	_bar_colors = colors.duplicate()
	for i in 2:
		var face: Color = colors[i]
		var sb := StyleBoxFlat.new()
		sb.bg_color = face
		sb.set_corner_radius_all(18)
		sb.corner_detail = 8
		sb.anti_aliasing = true
		sb.border_width_bottom = 6  # the darker bottom 18 % of a bar's fill (§4.7)
		sb.border_color = face.darkened(0.22)
		(_control_fill if i == 0 else _control_track).add_theme_stylebox_override("panel", sb)


## The percentage at one end of the war bar: NUM_S 26 white, outlined.
func _bar_pct(pos: Vector2, align: HorizontalAlignment) -> Label:
	var l := Kit.label("50%", 26)
	l.horizontal_alignment = align
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.position = pos + Vector2(0, -1)
	l.size = Vector2(110, BAR_RECT.size.y)
	_control_bar.add_child(l)
	return l


## `colors`: [player, enemy] fills (the states' colours on the map); the kit's info / war faces by default.
func set_control(score: float, control: int, enemy: String, visible_bar: bool, flags: Array = [], colors: Array = []) -> void:
	_control_bar.visible = visible_bar
	if not visible_bar:
		return
	if colors.size() >= 2:
		_set_bar_colors(colors)
	var k := clampf(control / 100.0, 0.0, 1.0)
	_control_fill.size.x = maxf(36.0, BAR_IN * k)
	_control_fill.visible = k > 0.0
	_control_track.visible = k < 1.0 or not _control_fill.visible
	var jx := BAR_X0 + BAR_IN * k  # the junction
	_war_swords.position.x = clampf(jx, BAR_X0 + 14.0, BAR_X0 + BAR_IN - 14.0) - 28.0
	for i in mini(flags.size(), _war_flags.size()):
		var fv: Control = _war_flags[i]
		if fv.get("flag") != flags[i]:
			fv.set("flag", flags[i])
			fv.queue_redraw()
	_control_lbl.text = "%d%%" % control
	_control_lbl2.text = "%d%%" % (100 - control)
	# a percentage gives way to the swords (56 wide on the junction) when they would touch it
	_control_lbl.visible = jx - 30.0 > _control_lbl.position.x + Kit.text_w(_control_lbl.text, 26, "d900")
	_control_lbl2.visible = jx + 30.0 < _control_lbl2.position.x + _control_lbl2.size.x - Kit.text_w(_control_lbl2.text, 26, "d900")
	var txt := "" if absf(score) < 0.05 else ("+" if score > 0.0 else "") + Kit.fmt_dec(score, 1)
	if txt != _score_txt:
		_score_txt = txt
		if is_instance_valid(_score_chip):
			_score_chip.queue_free()
		_score_chip = null
		if txt != "":
			_score_chip = Kit.caption_pill(_control_bar, txt, 30.0, Kit.alpha(Kit.INK, 0.85), 22)
			_score_chip.name = "score"
			var sl := _score_chip.get_child(0) as Label
			Kit.style_label(sl, 22, Kit.POS if score > 0.0 else Kit.NEG, true)
			sl.add_theme_font_override("font", Kit.font("d900"))  # MICRO: Rubik 900
	if _score_chip != null:
		var w := _score_chip.size.x
		_score_chip.position = Vector2(clampf(jx - w * 0.5, 196.0, 648.0 - w), 152)
	_laststand.visible = control <= 30
	if _laststand.visible and _score_chip != null and _score_chip.get_rect().intersects(_laststand.get_rect().grow(6.0)):
		_score_chip.position.x = _laststand.position.x - 8.0 - _score_chip.size.x


# ------------------------------------------------------------------ battle hand (§5, §6 «Бой»)

const HAND_RECT := Rect2(12, 1374, 628, 286)  # the battle tray (on the 1672 canvas, inside _bottom)
const ENERGY_C := Vector2(56, 1416)  # the energy counter: an energy hex R 32
const PIP_X0 := 116.0  # 10 hex pips R 20, centres x = 116 + i·50, y 1416
const CARD_Y := 1452.0
const CARD_H := 196.0
const CORPS_RECT := Rect2(524, 1206, 116, 160)  # «Союзный корпус»: over the tray, while an ally fights


func _build_battle() -> void:
	_battle = Control.new()
	_battle.name = "battle"
	_battle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bottom.add_child(_battle)
	var tray := _panel(_battle, HAND_RECT, Kit.style(Kit.SLATE, 24, 4, Kit.INK, 6, 6), Control.MOUSE_FILTER_STOP)
	tray.name = "hand_tray"  # stops taps from reaching the map under the hand
	var badge := Kit.hex_badge(_battle, ENERGY_C, 32, "energy", "0")
	badge.name = "energy"
	_energy_lbl = badge.get_child(0) as Label
	for i in 10:
		var c := Vector2(PIP_X0 + i * 50.0, ENERGY_C.y)
		var pip := Kit.hex_badge(_battle, c, 20, "energy", "", Kit.SLATE_WELL)  # empty: a sunken slate hex, INK 3
		pip.name = "pip_%d" % i
		pip.lip = Kit.SLATE_WELL
		pip.data["gloss"] = false
		var fill := Control.new()  # clips the full pip from the bottom: a partial pip fills up like a glass
		fill.name = "fill"
		fill.clip_contents = true
		fill.mouse_filter = Control.MOUSE_FILTER_IGNORE
		fill.size = Vector2(40, 40)
		pip.add_child(fill)
		var full := Kit.hex_badge(fill, Vector2(20, 20), 20, "energy")
		full.name = "full"
		_energy_segs.append(fill)
	_build_cards(CARD_ORDER)
	var cp := _battle_card("corps", CORPS_RECT, true)
	cp.visible = false
	_battle.visible = false


## The hand's card row (canon §9.9: «Атака» + 4 slots, 5 from DL6): n cards share the tray, w = (612 − 8(n − 1))/n.
func _build_cards(order: Array) -> void:
	for c in _cards.keys():
		if c != "corps":
			(_cards[c] as Control).queue_free()
			_cards.erase(c)
			_card_names.erase(c)
			_card_look.erase(c)
	_hand_order = order.duplicate()
	var n := maxi(1, order.size())
	var w := (612.0 - 8.0 * (n - 1)) / n
	for i in order.size():
		_battle_card(String(order[i]), Rect2(20.0 + i * (w + 8.0), CARD_Y, w, CARD_H))


## A card of the hand (§6 «Бой»): a slate card (R 20, INK 4, lip 6) whose art fills the face (R 14), the name in
## MICRO 22 on an INK scrim at the art's bottom, the energy cost in an ENERGY hex R 22 on the top-left corner, and a
## Label «cd» for the cooldown seconds (NUM_L 44) over an INK α 0.6 veil. Unaffordable: the art dimmed and the cost
## hex grey; not open yet (set_locked): a dark art, a lock 56 and the DL in a grey hex.
func _battle_card(card: String, r: Rect2, two_lines := false) -> Panel:
	var p := _panel(_battle, r, Kit.style(Kit.SLATE, 20, 4, Kit.INK, 5, 6))
	p.name = "card_" + card
	p.gui_input.connect(_on_card_input.bind(card))
	var w := r.size.x
	var art := Panel.new()
	art.name = "art"
	var asb := Kit.style(Kit.SKY_LOW, 14, 0, Kit.INK, 0, 0)
	asb.set_meta("kit_kind", "")
	art.add_theme_stylebox_override("panel", asb)
	art.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.position = Vector2(4, 4)
	art.size = Vector2(w - 8.0, r.size.y - 14.0)
	p.add_child(art)
	var pic := TextureRect.new()
	pic.name = "pic"
	pic.texture = _card_art(card)
	pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pic.size = art.size
	art.add_child(pic)
	var scrim := TextureRect.new()
	scrim.texture = Kit.vgradient(Kit.alpha(Kit.INK, 0.0), Kit.alpha(Kit.INK, 0.9))
	scrim.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	scrim.stretch_mode = TextureRect.STRETCH_SCALE
	scrim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sh := 84.0 if two_lines else 62.0
	scrim.position = Vector2(0, art.size.y - sh)
	scrim.size = Vector2(art.size.x, sh)
	art.add_child(scrim)
	var veil := Panel.new()  # the cooldown veil
	veil.name = "veil"
	var vsb := Kit.style(Kit.alpha(Kit.INK, 0.6), 14, 0, Kit.INK, 0, 0)
	vsb.set_meta("kit_kind", "")
	veil.add_theme_stylebox_override("panel", vsb)
	veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	veil.size = art.size
	veil.visible = false
	art.add_child(veil)
	var nm := Kit.label(_card_name(card), 22)
	nm.name = "name"
	nm.add_theme_font_override("font", Kit.font("d900"))  # MICRO: Rubik 900
	nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	nm.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	nm.position = Vector2(2, art.position.y + art.size.y - 64.0)  # on the card, over the scrim: the full width
	nm.size = Vector2(w - 4.0, 60)
	if two_lines:
		nm.autowrap_mode = TextServer.AUTOWRAP_WORD
		nm.max_lines_visible = 2
		nm.add_theme_constant_override("line_spacing", -5)
	p.add_child(nm)
	nm.set_meta("box", Vector2(2, w - 4.0))  # the room the name may take: x, width
	_fit_card_name(nm)
	_card_names[card] = nm
	var lk := TextureRect.new()
	lk.name = "lock"
	lk.texture = Kit.icon_tex("lock")
	lk.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	lk.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	lk.mouse_filter = Control.MOUSE_FILTER_IGNORE
	lk.size = Vector2(56, 56)
	lk.position = Vector2((art.size.x - 56.0) * 0.5, (art.size.y - 56.0) * 0.5 - 18.0)
	lk.visible = false
	art.add_child(lk)
	var cost := Kit.hex_badge(p, Vector2(16, 16), 22, "energy", str(_card_cost(card)))
	cost.name = "cost"
	var cd := Kit.label("", 44)  # NUM_L 44
	cd.name = "cd"
	cd.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cd.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	cd.position = Vector2(0, 4)
	cd.size = Vector2(w, art.size.y - 50.0)
	p.add_child(cd)
	_cards[card] = p
	_card_look[card] = {"pic": pic, "cost": cost, "veil": veil, "lock": lk, "state": ""}
	return p


## The painted scene of a card (tools/blender/card_art.py), or the swords on the sky while it has none.
func _card_art(card: String) -> Texture2D:
	var path := "res://assets/ui/cards/%s.png" % card
	return load(path) if ResourceLoader.exists(path) else Kit.icon_tex("swords")


## A card name: MICRO 22, down to 20 (§3.3: only the hand's names may), then cut with an ellipsis.
## Six cards (DL6+) leave a card 95 px: a long one-word name («Авиаудар») is condensed up to 16 % rather than cut.
## The label's meta «box» (x, width) is the room it may take.
func _fit_card_name(nm: Label) -> void:
	var box: Vector2 = nm.get_meta("box", Vector2(nm.position.x, nm.size.x))
	var max_w := box.y
	var probe := nm.text
	if nm.autowrap_mode != TextServer.AUTOWRAP_OFF:  # two lines: the widest word must fit
		probe = ""
		for wd in nm.text.split(" "):
			if Kit.text_w(wd, 22, "d900", false) > Kit.text_w(probe, 22, "d900", false):
				probe = wd
	var s := 20
	var tw := 0.0
	for v: int in [22, 20]:  # the outline may run into the 2 px margins: one outline counted, not two
		s = v
		tw = Kit.text_w(probe, v, "d900", false) + Kit.outline_for(v)
		if tw <= max_w:
			break
	nm.add_theme_font_size_override("font_size", s)
	var sx := clampf(max_w / tw, 0.84, 1.0) if tw > max_w else 1.0
	var lw := tw if sx < 1.0 else max_w  # condensed: the label holds the whole line, squeezed about its centre
	nm.size.x = lw
	nm.position.x = box.x + (max_w - lw) * 0.5
	nm.pivot_offset = Vector2(lw * 0.5, nm.size.y)
	nm.scale = Vector2(sx, 1.0)
	var cut := nm.autowrap_mode == TextServer.AUTOWRAP_OFF and tw * sx > max_w + 0.5
	nm.clip_text = cut
	nm.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS if cut else TextServer.OVERRUN_NO_TRIMMING


## A card's look: "" ready, "short" (not enough energy: dimmed art, grey cost hex), "cool" (the cooldown veil and its
## seconds over the art as it is), "locked" (not open yet). `short` greys the cost hex in any state: during a
## cooldown it still tells whether the energy will be there. Restyled only when it changes (set_battle runs every
## frame in battle).
func _card_state(card: String, state: String, short := false) -> void:
	var lk: Dictionary = _card_look.get(card, {})
	short = short or state == "short"
	var key := state + ("+short" if short else "")
	if lk.is_empty() or lk["state"] == key:
		return
	lk["state"] = key
	(lk["pic"] as Control).modulate = Kit.LOCK_ART if state == "locked" else (Kit.LOCK_MOD if state == "short" else Color.WHITE)
	(lk["veil"] as Control).visible = state == "cool"
	(lk["lock"] as Control).visible = state == "locked"
	var hex := lk["cost"] as Kit.KitShape
	var role := "lock" if state == "locked" or short else "energy"
	hex.face = Kit.face_of(role)
	hex.lip = Kit.lip_of(role)
	hex.queue_redraw()
	var hl := hex.get_child(0) as Label
	hl.text = str(int(_locked[card])) if state == "locked" else str(_card_cost(card))


## The offensive's hand in order (cards not open yet included, shown locked); rebuilt only when it changes.
func set_hand(order: Array) -> void:
	if order != _hand_order:
		_build_cards(order)
		set_locked(_locked)


## Cards not open yet: {card: DL it opens at} — a dark art, a lock and the DL in a grey hex (the name stays: the
## player learns the cards by name, §2); a tap says when it opens.
func set_locked(locked: Dictionary) -> void:
	_locked = locked
	for c in _cards:
		if locked.has(c):
			_card_state(c, "locked")
		elif String((_card_look.get(c, {}) as Dictionary).get("state", "")) == "locked":
			_card_state(c, "")


## Shows the «Союзный корпус» card when an ally fights in this war and it was not played yet.
func set_corps(available: bool) -> void:
	if _cards.has("corps"):
		(_cards["corps"] as Control).visible = available


func _card_name(c: String) -> String:
	return tr(String(CARD_NAME_KEYS[c]))


## Static labels built once in _ready, re-applied after a language switch.
func retranslate() -> void:
	var lp := _laststand.get_child(0) as Label
	lp.text = tr("ui.last_stand")
	var tw := Kit.text_w(lp.text, 22, "d900")
	_laststand.size.x = tw + 30.0
	lp.size = _laststand.size
	_laststand.position.x = BAR_RECT.end.x - _laststand.size.x
	for c in _card_names:
		var nm: Label = _card_names[c]
		nm.text = _card_name(c)
		_fit_card_name(nm)


var cost_discount := {}  # card -> energy off its price in this battle (Admiral Seir: «Десант» −1)


func _card_cost(c: String) -> int:
	var base: int = {"attack": 2, "breakthrough": 3, "airstrike": 4, "encircle": 3, "defense": 2, "corps": 3, "landing": 4, "missile": 5}[c]
	return maxi(1, base - int(cost_discount.get(c, 0)))


func set_battle(visible_hand: bool, energy_units: int, unit: int, cooldowns: Dictionary, seconds_left: int, rush: bool) -> void:
	_battle.visible = visible_hand
	if not visible_hand:
		return
	var pts := energy_units / unit
	var frac := float(energy_units % unit) / unit
	_energy_lbl.text = str(pts)
	for i in 10:
		var f: Control = _energy_segs[i]
		var k := 1.0 if i < pts else (frac if i == pts else 0.0)
		f.size.y = 40.0 * k
		f.position.y = 40.0 - f.size.y
		(f.get_child(0) as Control).position.y = -f.position.y  # the full pip stays put while its window grows
	for c in _cards:
		var p: Panel = _cards[c]
		var cd: int = cooldowns.get(c, 0)
		var cdl := p.get_node("cd") as Label
		if _locked.has(c):
			cdl.text = ""
			_card_state(c, "locked")
			continue
		cdl.text = str(int(ceil(cd / 10.0))) if cd > 0 else ""
		var short := pts < _card_cost(c)
		_card_state(c, "cool" if cd > 0 else ("short" if short else ""), short)
	set_action("timer", "%d:%02d" % [seconds_left / 60, seconds_left % 60], tr("ui.final_rush") if rush else tr("ui.offensive_left"), "war" if rush else "slate")


## The drop line of a dragged card: above the battle tray's top (it moves with the bottom group, §5).
func drop_y() -> float:
	return HAND_RECT.position.y + (Kit.vb(self) - VH)


## The dragged card (§6 «Бой»): its art at 0.9× (104×176) on an INK card with a hard shadow, the name on a scrim.
func _build_ghost() -> void:
	_ghost = Control.new()
	_ghost.name = "ghost"
	_ghost.size = Vector2(104, 176)
	_ghost.pivot_offset = Vector2(52, 176)
	_ghost.rotation_degrees = -4.0
	_ghost.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ghost.z_index = 50
	_ghost.visible = false
	root.add_child(_ghost)
	var body := Panel.new()
	var bsb := Kit.style(Kit.INK, 14, 0, Kit.INK, 8, 0)
	bsb.set_meta("kit_kind", "")
	body.add_theme_stylebox_override("panel", bsb)
	body.size = _ghost.size
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ghost.add_child(body)
	var art := Panel.new()
	var asb := Kit.style(Kit.SKY_LOW, 14, 0, Kit.INK, 0, 0)
	asb.set_meta("kit_kind", "")
	asb.set_corner_radius_all(11)
	art.add_theme_stylebox_override("panel", asb)
	art.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.position = Vector2(4, 4)
	art.size = _ghost.size - Vector2(8, 8)
	body.add_child(art)
	_ghost_art = TextureRect.new()
	_ghost_art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_ghost_art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_ghost_art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ghost_art.size = art.size
	art.add_child(_ghost_art)
	var scrim := TextureRect.new()
	scrim.texture = Kit.vgradient(Kit.alpha(Kit.INK, 0.0), Kit.alpha(Kit.INK, 0.9))
	scrim.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	scrim.stretch_mode = TextureRect.STRETCH_SCALE
	scrim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	scrim.position = Vector2(0, art.size.y - 58.0)
	scrim.size = Vector2(art.size.x, 58)
	art.add_child(scrim)
	_ghost_name = Kit.label("", 22)
	_ghost_name.add_theme_font_override("font", Kit.font("d900"))
	_ghost_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_ghost_name.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	_ghost_name.position = Vector2(2, art.size.y - 56.0)
	_ghost_name.size = Vector2(art.size.x - 4.0, 50)
	_ghost_name.set_meta("box", Vector2(2, art.size.x - 4.0))
	art.add_child(_ghost_name)


## The ghost floats above the finger (its bottom 18 px over the touch), so the finger never hides the card.
func _place_ghost(pos: Vector2) -> void:
	_ghost.position = pos - Vector2(52, 194)


func _on_card_input(event: InputEvent, card: String) -> void:
	if _locked.has(card):
		if event is InputEventScreenTouch or event is InputEventMouseButton:
			if event.pressed:
				toast(tr("err.unlock_dl") % int(_locked[card]))  # «Откроется на уровне развития 6» (no «УР6», §3.7)
		return
	if event is InputEventScreenTouch or event is InputEventMouseButton:
		var pressed: bool = event.pressed
		var pos: Vector2 = (event as InputEventScreenTouch).position if event is InputEventScreenTouch else (event as InputEventMouseButton).position
		pos += (_cards[card] as Control).global_position
		if pressed and _drag_card == "":
			_drag_card = card
			_ghost_art.texture = _card_art(card)
			_ghost_name.text = _card_name(card)
			_fit_card_name(_ghost_name)
			_place_ghost(pos)
			_ghost.visible = true
			var src := _cards[card] as Control
			src.pivot_offset = src.size * 0.5
			src.scale = Vector2(0.94, 0.94)  # the card in the hand sinks while its ghost flies
			card_drag.emit(card, pos, true)


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		_finger_down = (event as InputEventScreenTouch).pressed
	elif event is InputEventMouseButton and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		_finger_down = (event as InputEventMouseButton).pressed
	if _drag_card != "":
		var pos := Vector2.ZERO
		var released := false
		if event is InputEventScreenDrag:
			pos = (event as InputEventScreenDrag).position
		elif event is InputEventMouseMotion:
			pos = (event as InputEventMouseMotion).position
		elif event is InputEventScreenTouch and not (event as InputEventScreenTouch).pressed:
			pos = (event as InputEventScreenTouch).position
			released = true
		elif event is InputEventMouseButton and not (event as InputEventMouseButton).pressed:
			pos = (event as InputEventMouseButton).position
			released = true
		else:
			return
		_place_ghost(pos)
		if released:
			var c := _drag_card
			_drag_card = ""
			_ghost.visible = false
			if _cards.has(c):
				(_cards[c] as Control).scale = Vector2.ONE
			card_drag.emit(c, pos, false)
			if pos.y < drop_y():  # above the hand
				card_drop.emit(c, pos)
		else:
			card_drag.emit(_drag_card, pos, true)
		get_viewport().set_input_as_handled()


# ------------------------------------------------------------------ action buttons (bottom-right, §5)

## The big button's look by kind (docs/ui_style.md §6 HUD): [role, icon]. It wins over the caller's colour; a kind
## not listed keeps the caller's role and icon. «colonize_now» is gold only while it costs Raivites (free: go); the
## lock kinds are the disabled ones (their reason is in the tooltip). «pick_target» shows swords, not the target
## render: its crossed arrows read as a «forbidden» sign on the red face at phone size.
const PRIMARY_LOOK := {
	"pick_target": ["war", "swords"], "declare": ["war", "swords"], "offensive": ["war", "swords"], "camp": ["war", "swords"],
	"upgrade": ["go", "arrow_up"], "colonize": ["go", "orders"], "colonize_now": ["gold", "lightning"], "convoy": ["go", "cart"],
	"repair": ["go", "hammer"], "march": ["info", "orders"], "march_cancel": ["info", "x"], "march_stop": ["info", "hourglass"],
	"retreat": ["info", "white_flag"],
	"truce": ["lock", "hourglass"], "core": ["lock", "lock"], "camp_far": ["lock", "lock"], "camp_wait": ["lock", "hourglass"],
	"wait": ["lock", "hourglass"], "repairing": ["lock", "hourglass"], "convoy_status": ["lock", "hourglass"],
}
## The status button's look by kind: [role, icon, the plate's icon]. Both ad buttons are secondary (info, §2: an ad
## button is the secondary one when a main action stands beside it — the paid repair / «Улучшить» on the big button),
## so the big button stays the one loud thing (§1.1). The ruin's plate carries an hourglass: «−50%» of that time.
const STATUS_LOOK := {"peace": ["go", "dove", ""], "repair_ad": ["info", "ad", ""], "ruin_halve": ["info", "ad", "hourglass"]}
const BIG_RECT := Rect2(652, 1536, 277, 124)  # the big button: L, the one loud thing on the map (§1.1)
const RETREAT_RECT := Rect2(652, 1564, 277, 96)  # «Отступить» in battle: M, a secondary action
const STATUS_RECT := Rect2(652, 1438, 277, 88)  # the status button: M, in the hex panel's slot
const TIMER_RECT := Rect2(652, 1374, 277, 162)  # the battle timer plate, in the hex panel's slot

var _status_btn: Panel  # the status button (Kit.KitButton) inside _action
var _timer_plate: Panel  # the battle timer plate inside _action
var _timer_num: Label
var _timer_sub: Label
var _timer_tw: Tween  # the «final push» pulse
var _primary_args: Array = []  # the last set_primary / set_action arguments: both run every frame in battle
var _status_args: Array = []
var _primary_reason := ""  # the tooltip of a disabled big button


func _build_action() -> void:
	# _action: the status slot — the status button or the battle timer plate; visible while its kind is not ""
	_action = Control.new()
	_action.name = "status"
	_action.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_action.size = Vector2(VW, VH)
	_bottom.add_child(_action)
	_status_btn = Kit.button(_action, STATUS_RECT, "go", "", {"size": "M", "cb": func(): action_pressed.emit(_action_kind)})
	_status_btn.name = "status_button"
	_timer_plate = _panel(_action, TIMER_RECT, Kit.style(Kit.SLATE, 24, 4, Kit.INK, 6, 6), Control.MOUSE_FILTER_STOP)
	_timer_plate.name = "timer"
	var hg := TextureRect.new()
	hg.texture = Kit.icon_tex("hourglass")
	hg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	hg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	hg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hg.position = Vector2(16, 22)
	hg.size = Vector2(64, 64)
	_timer_plate.add_child(hg)
	_timer_num = _label("", 60)  # TIMER 60
	_timer_num.position = Vector2(88, 14)
	_timer_num.size = Vector2(TIMER_RECT.size.x - 88.0 - 12.0, 80)
	_timer_num.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_timer_num.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_timer_num.pivot_offset = _timer_num.size * 0.5
	_timer_plate.add_child(_timer_num)
	_timer_sub = _label("", 24, Kit.SOFT)  # LABEL 24, SOFT
	_timer_sub.position = Vector2(12, 104)
	_timer_sub.size = Vector2(TIMER_RECT.size.x - 24.0, 34)
	_timer_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_timer_sub.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_timer_plate.add_child(_timer_sub)
	# _action2: the big button
	_action2 = Kit.button(_bottom, BIG_RECT, "info", "", {"size": "L", "cb": _on_primary})
	_action2.name = "big_button"
	(_action2 as Kit.KitButton).denied.connect(_on_primary_denied)
	_action.visible = false
	_action2.visible = false


func _is_tap(e: InputEvent) -> bool:
	return (e is InputEventScreenTouch and not e.pressed) or (e is InputEventMouseButton and not e.pressed and e.button_index == MOUSE_BUTTON_LEFT)


## The status slot (§5, §6 HUD) — kind "" hides it. Kind «timer»: the battle timer plate (hourglass, the time in
## TIMER 60, `sub` under it; bg "war" is the final push: the number turns red and pulses every second). Any other
## kind: a button M in the hex panel's slot («peace»: go + dove, `sub` the war score in a chip; «repair_ad»: info + the
## ad icon; «ruin_halve»: info + the ad icon, `sub` the ruin's time left in a chip with an hourglass). `bg` is a role
## name or, from older callers, a colour (Kit.role_of); STATUS_LOOK wins over it.
func set_action(kind: String, title: String, sub := "", bg: Variant = "go") -> void:
	_action_kind = kind
	_action.visible = kind != ""
	var role := String(bg) if bg is String else Kit.role_of(bg)
	var args := [kind, title, sub, role]
	if args == _status_args:
		return
	var was_timer := _status_args.size() > 0 and String(_status_args[0]) == "timer"
	_status_args = args
	_timer_plate.visible = kind == "timer"
	_status_btn.visible = kind != "timer" and kind != ""
	if kind != "timer" and _timer_tw != null:  # the pulse stops with the plate
		_timer_tw.kill()
		_timer_tw = null
		_timer_num.scale = Vector2.ONE
	if kind == "timer":
		_timer_num.text = title
		_timer_sub.text = sub
		var rush := role == "war"
		_timer_num.add_theme_color_override("font_color", Kit.NEG if rush else Kit.TEXT)
		var ss := Kit.fit_size(sub, 24, _timer_sub.size.x, "d800", 22)  # LABEL 24, down to 22, then cut
		_timer_sub.add_theme_font_size_override("font_size", ss)
		_timer_sub.clip_text = Kit.text_w(sub, ss, "d800") > _timer_sub.size.x
		_timer_sub.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		if rush and (_timer_tw == null or not _timer_tw.is_valid()):
			_timer_tw = _timer_num.create_tween().set_loops()  # one beat a second
			_timer_tw.tween_property(_timer_num, "scale", Vector2(1.08, 1.08), 0.15).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			_timer_tw.tween_property(_timer_num, "scale", Vector2.ONE, 0.25).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
			_timer_tw.tween_interval(0.6)
		elif not rush and _timer_tw != null:
			_timer_tw.kill()
			_timer_tw = null
			_timer_num.scale = Vector2.ONE
		if not was_timer:
			Kit.fade_in(_timer_plate)
		return
	if kind == "":
		return
	var look: Array = STATUS_LOOK.get(kind, [role, "", ""])
	var b := _status_btn as Kit.KitButton
	b.role = String(look[0]) if Kit.ROLE.has(String(look[0])) else "go"
	b.icon = String(look[1])
	b.caption = title
	b.price = [[String(look[2]), sub, sub.begins_with(Kit.MINUS)]] if sub != "" else []  # a negative war score reads red
	b.enabled = true
	b.rebuild()


## The big button (§5, §6 HUD) — kind "" hides it. The only primary renderer on the map: a Kit button L (M for
## «retreat») whose role and icon come from PRIMARY_LOOK by kind (`color` — a role name or a legacy colour — and
## `icon` only for kinds it does not list). `price`: the plate's items [[icon, text, short], …] — a cost (two at
## most; `short` paints a missing amount red) or a time ([["", "2:57"]]). Disabled, it is grey and a tap shakes it
## and shows `reason` in a tooltip; disabled only for want of a resource (a `short` item), it keeps its role and the
## red number instead (§4.1 «Не хватает»). `_action2_kind` is the kind only while enabled (the tests read it).
func set_primary(kind: String, title: String, color: Variant = "info", enabled := true, icon := "", price: Array = [], reason := "") -> void:
	_action2_kind = kind if enabled else ""
	_action2.visible = kind != ""
	var args := [kind, title, color, enabled, icon, price, reason]
	if args == _primary_args:
		return
	_primary_args = args
	_primary_reason = reason if reason != "" else title
	if kind == "":
		return
	var role := String(color) if color is String else Kit.role_of(color)
	var look: Array = PRIMARY_LOOK.get(kind, [role, icon])
	role = String(look[0])
	if kind == "colonize_now" and price.is_empty():  # finishing for free is no spending: not gold (§3.2)
		role = "go"
	var short := false
	for p in price:
		short = short or ((p as Array).size() > 2 and bool(p[2]))
	var b := _action2 as Kit.KitButton
	var r := RETREAT_RECT if kind == "retreat" else BIG_RECT
	b.size_class = "M" if kind == "retreat" else "L"
	b.position = r.position
	b.size = r.size
	b.role = role
	b.icon = String(look[1]) if String(look[1]) != "" else icon
	b.caption = title
	b.price = price
	b.enabled = enabled or (short and role != "lock")
	b.rebuild()


func _on_primary() -> void:
	if _action2_kind == "":  # shown as available but short of a resource: shake and say what is missing
		Kit.shake(_action2)
		_on_primary_denied()
		return
	action_pressed.emit(_action2_kind)


func _on_primary_denied() -> void:
	Kit.tooltip(_action2, (_action2 as Kit.KitButton).caption.replace("\n", " "), _primary_reason if _primary_reason != (_action2 as Kit.KitButton).caption else "")


# ------------------------------------------------------------------ modals

func has_modal() -> bool:
	return _modal != null


var _closing: Control  # the window fading out
var _closed_frame := -1


## Closes the window at once for the game (`has_modal()` is false right away); the node fades out (120 ms).
func close_modal() -> void:
	var m := _modal
	_modal = null
	if m:
		_closing = m
		_closed_frame = Engine.get_process_frames()
		Kit.close_fx(m)


## A cream window (docs/ui_style.md §4.3) over an INK dim; every modal is paper now (`parchment` is ignored).
## title / icon / role: the hex title plate; closable: the round ✕ and a tap on the dim close it (not for
## `blocking` decision windows). Returns the frame Panel; its children keep their local coordinates.
func _modal_box(rect: Rect2, parchment := false, title := "", icon := "", role := "info", closable := false, blocking := false, dim_a := -1.0) -> Panel:
	# a window replaced in the same frame (a screen re-rendering itself) swaps without the pop-in
	var swap := _modal != null or _closed_frame == Engine.get_process_frames()
	close_modal()
	if swap and is_instance_valid(_closing):
		_closing.queue_free()
	_modal = Control.new()
	var vis := get_viewport().get_visible_rect() if is_inside_tree() else Rect2(0, 0, VW, VH)
	_modal.position = vis.position
	_modal.size = Vector2(maxf(VW, vis.size.x), maxf(VH, vis.size.y))
	_modal.mouse_filter = Control.MOUSE_FILTER_STOP
	root.add_child(_modal)
	var dim := ColorRect.new()
	dim.color = Color(Kit.INK, 0.0)
	dim.size = _modal.size
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_modal.add_child(dim)
	var da := Kit.DIM_A if dim_a < 0.0 else dim_a  # the ceremony dims deeper (α 0.75)
	if swap or DisplayServer.get_name() == "headless" or Kit.reduce_motion:
		dim.color.a = da
	else:
		dim.create_tween().tween_property(dim, "color:a", da, 0.14)
	var frame := _panel(_modal, Rect2(rect.position - _modal.position, rect.size), Kit.style(Kit.CREAM, 34, 5, Kit.INK, 10, 12))
	frame.set_meta("paper", true)
	if not swap:
		Kit.pop_in(frame)
	if title != "":
		Kit.title_plate(frame, title, role, icon, not swap)
	if closable and not blocking:
		Kit.close_button(frame, close_modal)
		var m := _modal
		_modal.gui_input.connect(func(e): if _is_tap(e) and _modal == m: close_modal())
	Kit.paperize.call_deferred(frame)
	return frame


## A kit button (§4.1) whose role follows the legacy colour; returns the KitButton (a Panel). A lone «✕» is a
## close button: role war with the vector cross.
func _button(parent: Control, rect: Rect2, text: String, color: Color, cb: Callable) -> Panel:
	var close := text.strip_edges() == "✕"
	return Kit.button(parent, rect, "war" if close else Kit.role_of(color), text,
		{"cb": cb, "hit_pad": maxf(0.0, (96.0 - rect.size.y) * 0.5) if close else 0.0})


## A window's rect by width class (§4.3: L 893 at x 24, M 781 at x 80, S 661 at x 140), `h` tall (at most the band),
## centred in the band y 150 … VB − 24.
func _win_rect(cls: String, h: float) -> Rect2:
	var w: float = {"L": 893.0, "M": 781.0, "S": 661.0}.get(cls, 781.0)
	var top := 150.0
	var bot := Kit.vb(self) - 24.0
	h = minf(h, bot - top)
	return Rect2((VW - w) * 0.5, top + (bot - top - h) * 0.5, w, h)


const PAPER_CHIP_H := 44.0


## A chip on paper: CREAM_DEEP pill h 44, an icon 34 and Rubik 800 26 INK_TEXT (fit to 22, then cut), centred at
## `center` (the result's reason, an option's «мир 24ч»). With `disc`, the icon (30) sits on a round disc of that
## colour in an INK 3 ring — a light icon (the white dove) then reads on the paper.
func _paper_chip(parent: Control, center: Vector2, icon: String, text: String, max_w := 600.0, disc := Kit.CLEAR) -> Panel:
	var p := Panel.new()
	p.name = "chip"
	var sb := Kit.style(Kit.CREAM_DEEP, int(PAPER_CHIP_H * 0.5), 0, Kit.INK, 0, 0)  # a pill (h/2)
	sb.set_meta("kit_kind", "")
	p.add_theme_stylebox_override("panel", sb)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var x := 14.0
	var tex := Kit.icon_tex(icon)
	if tex != null and disc.a > 0.0:
		var d := Panel.new()
		d.name = "disc"
		var dsb := Kit.style(disc, 20, 3, Kit.INK, 0, 0)
		dsb.set_meta("kit_kind", "")
		d.add_theme_stylebox_override("panel", dsb)
		d.mouse_filter = Control.MOUSE_FILTER_IGNORE
		d.position = Vector2(2, 2)
		d.size = Vector2(40, 40)
		p.add_child(d)
		var di := _icon_rect(icon, 30)
		di.position = Vector2(5, 5)
		d.add_child(di)
		x = 52.0
	elif tex != null:
		var ic := _icon_rect(icon, 34)
		ic.position = Vector2(10, 5)
		p.add_child(ic)
		x = 50.0
	var room := max_w - x - 16.0
	var s := Kit.fit_size(text, 26, room, "d800", 22, false)
	var l := Kit.label(text, s, Kit.INK_TEXT, true)
	l.add_theme_font_override("font", Kit.font("d800"))
	l.add_theme_font_size_override("font_size", s)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	var tw := minf(Kit.text_w(text, s, "d800", false) + 2.0, room)
	l.clip_text = true
	l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	l.position = Vector2(x, -1)
	l.size = Vector2(tw, 44)
	p.add_child(l)
	p.size = Vector2(x + tw + 16.0, 44)
	p.position = center - p.size * 0.5
	parent.add_child(p)
	return p


## A node pops in after `delay` s (0 → 1.15 → 1, BADGE_POP); at once when headless or with reduced motion.
func _pop_later(node: Control, delay: float) -> void:
	node.pivot_offset = node.size * 0.5
	if Kit._dur(0.24) <= 0.0:
		return
	node.scale = Vector2.ZERO
	var tw := node.create_tween()
	tw.tween_interval(delay)
	tw.tween_property(node, "scale", Vector2(1.15, 1.15), 0.14).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_property(node, "scale", Vector2.ONE, 0.1)


var _result_peace: Control  # the result's «К миру» (the FTUE points at it)


## Offensive results (§6 «Итоги наступления»): a decision window M without ✕. The plate: gold «Успех!» (a star and land
## taken), war «Поражение» (more lost than taken), info «Ничья» otherwise; three vector stars (the middle one bigger and
## raised); the reason in a chip (`reason_icon`: hourglass — time is up, white_flag — retreat, …); a well with the tiles [captured] [front] [peace points] (+ [lost] when not 0); the
## border note when land was taken; «Ещё бой» (info) and «К миру» (go). `defeat`: the war is lost whatever was taken
## (the defeat offer: the plate is «Поражение» even when the enemy holds no land to annex).
func show_result(stars: int, captured: int, lost: int, score: float, control: int, reason: String, on_continue: Callable, on_peace: Callable, reason_icon := "hourglass", defeat := false) -> void:
	defeat = defeat or lost > captured
	var won := stars >= 1 and captured > 0 and not defeat
	var role := "gold" if won else ("war" if defeat else "info")
	var title := tr("result.win") if won else (tr("result.defeat_title") if defeat else tr("result.draw"))
	var note := captured > 0
	var h := 776.0 if note else 736.0
	var box := _modal_box(_win_rect("M", h), false, title, "", role, false, true)
	box.set_meta("kit_native", true)
	var w := box.size.x
	for i in 3:
		var big := i == 1
		var st := Kit.star(box, Vector2(w * 0.5 + (i - 1) * 165.0, 176.0 - (28.0 if big else 0.0)), 85.0 if big else 70.0, i < stars)
		st.name = "star_%d" % i
		_pop_later(st, 0.18 + 0.12 * i)
	_paper_chip(box, Vector2(w * 0.5, 284), reason_icon, reason, w - 64.0)
	var tiles: Array = [
		{"icon": "hex_tile", "value": ("+%d" % captured) if captured > 0 else "0", "caption": tr("result.captured")},
		{"icon": "orders", "value": "%d%%" % control, "caption": tr("result.control")},
		{"icon": "treaty", "value": ("+" if score > 0.05 else "") + Kit.fmt_dec(score, 1), "caption": tr("result.score"),
			"value_color": Kit.NEG_CREAM if score < -0.05 else Kit.INK_TEXT},
	]
	if lost > 0:
		tiles.append({"icon": "hex_tile", "value": Kit.MINUS + str(lost), "caption": tr("result.lost"), "value_color": Kit.NEG_CREAM})
	var well := Kit.well(box, Rect2(32, 326, w - 64.0, 214))
	var n := tiles.size()
	var tw := (well.size.x - 32.0 - 12.0 * (n - 1)) / n
	for i in n:
		var o: Dictionary = tiles[i]
		o["icon_side"] = 72.0 if n <= 3 else 64.0
		Kit.tile(well, Rect2(16.0 + i * (tw + 12.0), 16, tw, 182), o)
	if note:
		var nl := Kit.label(tr("result.note"), 28, Kit.SOFT_CREAM, false)
		nl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		nl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		nl.position = Vector2(32, 554)
		nl.size = Vector2(w - 64.0, 44)
		box.add_child(nl)
	var fy := h - 32.0 - 116.0
	Kit.button(box, Rect2(32, fy, 280, 116), "info", tr("result.continue"), {"icon": "swords", "size": "L", "cb": on_continue})
	_result_peace = Kit.button(box, Rect2(328, fy, w - 360.0, 116), "go", tr("result.peace"), {"icon": "treaty", "size": "L", "cb": on_peace})


## The centre of the result's «К миру» on the screen (where the FTUE points); the old spot when it is not shown.
func result_peace_center() -> Vector2:
	if is_instance_valid(_result_peace) and _result_peace.is_inside_tree():
		return _coach_point(_result_peace.get_global_rect().get_center())
	return Vector2(655, 998)


const PLUNDER_NAMES := ["plunder.spare", "plunder.light", "plunder.medium", "plunder.heavy"]
static var _hold_hints := 0  # the treaties opened so far: «Удерживайте, чтобы подписать» shows for the first 3
var _seal_btn: Control  # «Подписать мир» (the FTUE points at it)
var _plunder_seg: Control
var _sealed := false  # seal_done fires once per treaty


## The peace treaty (§6 «Мирный договор»): a decision window L that hugs its content. The enemy leader (cunning) with
## the line «Подпишу, если не больше 54,6», the budget bar L (used / budget, red when over), «Требования» — a grid of
## 3 tiles per row (render or icon, name, cost; chosen: a green rim and a check; the indemnity packages collapse into
## one tile «×N»), «Грабёж» in segments, «К войне» (info S) and «Подписать мир» (go L, hold 0.8 s → seal_done; lock
## while the demands cost more than the budget). Rows that do not fit the screen scroll inside the well.
func show_peace(enemy: String, budget: float, control: int, demands: Array, chosen: Dictionary, plunder := 1, portrait := "", plate := Kit.CLEAR) -> void:
	var fresh := not (_modal != null and _modal.has_meta("peace"))
	if fresh:
		_hold_hints += 1
		_sealed = false
	var used := 0.0
	for d in demands:
		if chosen.has(d["id"]):
			used += float(d["cost"])
	var over := used > budget + 0.0001
	# one tile per demand; the repeated indemnity packages share one («×N» chosen)
	var groups: Array = []
	var by_key := {}
	for d in demands:
		var key := "contribution" if d["kind"] == "contribution" else String(d["id"])
		if not by_key.has(key):
			by_key[key] = {"d": d, "ids": [], "on": [], "i": groups.size()}
			groups.append(by_key[key])
		(by_key[key]["ids"] as Array).append(d["id"])
		if chosen.has(d["id"]):
			(by_key[key]["on"] as Array).append(d["id"])
	# the order on the grid: pockets, the war's goal, the money (indemnity, reparations), then the other hexes by
	# value — a long list scrolls, and what it hides is the least of the land, never the gold; the recommended
	# package (War.recommend_package ranks the same way) fills the first tiles
	var rank := func(g: Dictionary) -> int:
		var d: Dictionary = g["d"]
		match String(d["kind"]):
			"pocket":
				return 0
			"contribution":
				return 2
			"reparations":
				return 3
		return 1 if bool(d.get("goal", false)) else 4
	groups.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var ra: int = rank.call(a)
		var rb: int = rank.call(b)
		if ra != rb:
			return ra < rb
		var ca := float(a["d"]["cost"])
		var cb := float(b["d"]["cost"])
		if ra == 4 and absf(ca - cb) > 0.001:
			return ca > cb
		return int(a["i"]) < int(b["i"]))
	var hint := _hold_hints <= 3
	var rows := maxi(1, ceili(groups.size() / 3.0))
	var row_h := 212.0
	var head := 258.0  # leader, bubble, budget
	var tail := 24.0 + 48.0 + 12.0 + 80.0 + (52.0 if hint else 0.0) + 24.0 + 116.0 + 32.0  # plunder, hint, footer
	var max_h := Kit.vb(self) - 24.0 - 150.0
	var room := max_h - head - 60.0 - tail  # the most the well may take
	var well_h := 32.0 + rows * row_h - 12.0
	var scroll := well_h > room
	if scroll:  # the rows that fit, and the top of the next one peeking out under the fade (§4.3)
		var vis := clampi(floori((room - 16.0 - PEACE_PEEK) / row_h), 1, rows - 1)
		well_h = 16.0 + vis * row_h + PEACE_PEEK
	var h := head + 60.0 + well_h + tail
	var keep_scroll := 0 if fresh else _peace_scroll  # a tap re-renders the treaty: the list stays where it was
	var box := _modal_box(_win_rect("L", h), false, tr("peace.title"), "", "go", false, true)
	_modal.set_meta("peace", true)
	box.set_meta("kit_native", true)
	var w := box.size.x
	_leader_seal(box, portrait, plate, Rect2(32, 64, 156, 170), "cunning", enemy)
	var bx := 32.0 + 156.0 + 28.0
	Kit.bubble(box, Rect2(bx, 70, w - 32.0 - bx, 96), tr("peace.offer") % Kit.fmt_dec(budget, 1), "left")
	var ti := _icon_rect("treaty", 52)
	ti.position = Vector2(bx, 180)
	box.add_child(ti)
	var frac := used / budget if budget > 0.0 else 0.0
	var bud := Kit.bar(box, Rect2(bx + 60.0, 186, w - 32.0 - bx - 60.0, 40), minf(frac, 1.0), "war" if over else "go",
		"%s / %s" % [Kit.fmt_dec(used, 1), Kit.fmt_dec(budget, 1)], true)
	bud.name = "budget"
	# the demands; a list longer than the screen holds says so: «✓ chosen/all» on the header
	var sec_w := w - 64.0
	if scroll:
		var on_n := 0
		for g in groups:
			on_n += int(not (g["on"] as Array).is_empty())
		var cc := Kit.chip(box, Vector2.ZERO, "", "%d/%d" % [on_n, groups.size()], "status")
		cc.name = "demand_count"
		cc.position = Vector2(w - 32.0 - cc.size.x, head + 7.0)
		Kit.check_badge(box, Vector2(cc.position.x - 14.0, head + 24.0), 36.0)
		sec_w -= cc.size.x + 48.0
	Kit.section(box, Vector2(32, head), sec_w, tr("peace.demands"))
	var well := Kit.well(box, Rect2(32, head + 60.0, w - 64.0, well_h))
	var grid: Control = well
	if scroll:
		grid = _peace_scroller(well, 20.0 + rows * row_h, keep_scroll)
	var tw := (well.size.x - 32.0 - 24.0 - (PEACE_BAR_ROOM if scroll else 0.0)) / 3.0
	for i in groups.size():
		var g: Dictionary = groups[i]
		var d: Dictionary = g["d"]
		var ids: Array = g["ids"]
		var on: Array = g["on"]
		var cost := float(d["cost"])
		var fits := used + cost <= budget + 0.0001
		var o := {"title": String(d["label"]), "icon_side": 100.0, "pill_inside": true,
			"pill": [["treaty", Kit.fmt_dec(cost, 1), on.is_empty() and not fits]],
			"selected": not on.is_empty(), "count": on.size() if ids.size() > 1 else 0, "dim": on.is_empty() and not fits}
		var tex := _tile_tex(String(d.get("tile", "")))
		if tex != null:
			o["tex"] = tex
			o["icon_side"] = 124.0  # a hex render has a wide transparent margin: drawn larger, the name rises into it
			o["pic_overlap"] = 16.0
		else:
			o["icon"] = String(d.get("icon", {"pocket": "hex_tile", "contribution": "coins", "reparations": "treaty"}.get(String(d["kind"]), "hex_tile")))
		o["cb"] = func():
			if ids.size() == 1:
				demand_toggled.emit(String(ids[0]))
			elif on.size() < ids.size() and (fits or on.is_empty()):  # one more package while the points allow
				for id in ids:
					if not on.has(id):
						demand_toggled.emit(String(id))
						break
			else:  # all taken, or no points for another: take them back
				for id in on:
					demand_toggled.emit(String(id))
		var t := Kit.tile(grid, Rect2(16.0 + (i % 3) * (tw + 12.0), 16.0 + (i / 3) * row_h, tw, 200), o)
		t.name = "demand_%d" % i
		if bool(d.get("goal", false)):  # the war's goal: a pin on the corner
			var pin := _icon_rect("pin", 48)
			pin.position = Vector2(4, 2)
			t.add_child(pin)
	# plunder (canon §9.14): the winner's free right, its level chosen by the player
	var y := head + 60.0 + well_h + 24.0
	Kit.section(box, Vector2(32, y), w - 64.0, tr("peace.plunder"))
	var names: Array = []
	for k in PLUNDER_NAMES:
		names.append(tr(k))
	_plunder_seg = Kit.segmented(box, Rect2(32, y + 60.0, w - 64.0, 80), names, plunder, func(i: int):
		if i != plunder:
			plunder_selected.emit(i))
	y += 60.0 + 80.0
	if hint:
		var hl := Kit.label(tr("peace.hold_hint"), 26, Kit.MUTED_CREAM, false)
		hl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		hl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		hl.position = Vector2(32, y + 14.0)
		hl.size = Vector2(w - 64.0, 36)
		box.add_child(hl)
	var fy := h - 32.0 - 116.0
	# «К войне»: secondary, a step quieter than the L beside it, still a full thumb target (§1.4: ≥ 84 standalone)
	Kit.button(box, Rect2(32, fy + 14.0, 240, 88), "info", tr("peace.back"), {"size": "M", "hit_pad": 6.0,
		"cb": func(): action_pressed.emit("back_to_war")})
	var sb := Kit.button(box, Rect2(288, fy, w - 320.0, 116), "go", tr("peace.seal"), {"icon": "treaty", "size": "L",
		"hold": true, "hold_sec": 0.8, "enabled": not over, "cb": _on_seal})
	sb.name = "seal"
	sb.denied.connect(func(): Kit.tooltip(sb, tr("peace.seal"), tr("peace.over")))
	_seal_btn = sb


func _on_seal() -> void:
	if _sealed:
		return
	_sealed = true
	seal_done.emit()


const PEACE_PEEK := 76.0  # how much of the first hidden row shows under the well's bottom fade (the list goes on)
const PEACE_BAR_ROOM := 12.0  # the scroll bar's lane on the well's right (the tiles step aside for it)
const FADE_H := 24.0  # the scroll fades (§4.3)
var _peace_scroll := 0  # the treaty list's scroll (kept while the treaty re-renders after a tap)


## The scrolling inside a treaty's well (§4.3): a ScrollContainer over the whole well holding a Control
## `content_h` tall (returned: the tiles go in it), 24 px CREAM_WELL fades at the bottom (and at the top once
## scrolled), an 8 px INK α 0.4 pill bar on the right; it opens at `at` px.
func _peace_scroller(well: Control, content_h: float, at: int) -> Control:
	var sc := ScrollContainer.new()
	sc.name = "scroll"
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	sc.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_NEVER
	sc.size = well.size
	well.add_child(sc)
	var inner := Control.new()
	inner.custom_minimum_size = Vector2(well.size.x, content_h)
	inner.mouse_filter = Control.MOUSE_FILTER_PASS
	sc.add_child(inner)
	var fades: Array = []
	for top in [true, false]:
		var f := TextureRect.new()
		f.name = "fade_top" if top else "fade_bottom"
		f.texture = Kit.vgradient(Kit.CREAM_WELL, Kit.alpha(Kit.CREAM_WELL, 0.0)) if top \
			else Kit.vgradient(Kit.alpha(Kit.CREAM_WELL, 0.0), Kit.CREAM_WELL)
		f.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		f.stretch_mode = TextureRect.STRETCH_SCALE
		f.mouse_filter = Control.MOUSE_FILTER_IGNORE
		f.position = Vector2(10, 0.0 if top else well.size.y - FADE_H)  # 10 in: clear of the well's round corners
		f.size = Vector2(well.size.x - 20.0, FADE_H)
		well.add_child(f)
		fades.append(f)
	var track := Rect2(well.size.x - 12.0, 12.0, 8.0, well.size.y - 24.0)
	var bar := Panel.new()
	bar.name = "scroll_bar"
	var bsb := Kit.style(Kit.alpha(Kit.INK, 0.4), 8, 0, Kit.INK, 0, 0)  # a pill: R 8 on an 8 px bar (Godot fits it to w/2)
	bsb.set_meta("kit_kind", "")
	bar.add_theme_stylebox_override("panel", bsb)
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar.size = Vector2(track.size.x, maxf(48.0, track.size.y * minf(1.0, well.size.y / content_h)))
	bar.position = track.position
	well.add_child(bar)
	var span := maxf(1.0, content_h - well.size.y)
	var show_at := func(v: float) -> void:
		var k := clampf(v / span, 0.0, 1.0)
		bar.position.y = track.position.y + k * (track.size.y - bar.size.y)
		(fades[0] as Control).visible = v > 1.0
		(fades[1] as Control).visible = v < span - 1.0
		_peace_scroll = int(v)
	sc.get_v_scroll_bar().value_changed.connect(show_at)
	show_at.call(0.0)
	if at > 0:  # once the container has laid out its content (its scroll range is known then)
		var restore := func() -> void:
			if is_instance_valid(sc):
				sc.scroll_vertical = at
				show_at.call(float(sc.scroll_vertical))
		restore.call_deferred()
	return inner


## The centre of «Подписать мир» / of the plunder segments on the screen (where the FTUE points).
func peace_seal_center() -> Vector2:
	if is_instance_valid(_seal_btn) and _seal_btn.is_inside_tree():
		return _coach_point(_seal_btn.get_global_rect().get_center())
	return Vector2(470, 1488)


func peace_plunder_center() -> Vector2:
	if is_instance_valid(_plunder_seg) and _plunder_seg.is_inside_tree():
		var r := _plunder_seg.get_global_rect()
		return _coach_point(Vector2(r.position.x + r.size.x * 0.125, r.get_center().y))  # «Нет»: sparing is the choice taught
	return Vector2(274, 1380)


## A point on the screen as the coach takes its targets: on the 1672 canvas inside the bottom band (the coach adds
## the bottom group's offset back there, _process_coach).
func _coach_point(p: Vector2) -> Vector2:
	var dy := _bottom.position.y
	return p - Vector2(0, dy) if p.y - dy >= VH - 332.0 else p


## A tile's render (tools/blender/card_art.py tile_*) by its key; an era tile («capital_dl4_red») falls back to the
## kind's own picture; null when there is none.
func _tile_tex(key: String) -> Texture2D:
	if key == "":
		return null
	for k in [key, key.get_slice("_dl", 0)]:
		var p := "res://assets/ui/cards/tile_%s.png" % k
		if ResourceLoader.exists(p):
			return load(p)
	return null


## Ceremony counters and rewards (canon §10.3 steps 4–5, §6 «Церемония»): a window L over a dim α 0.75 (the currency
## plates stay above it), the gold plate «Победа!» (HERO 64), the realm's value counting up (crown, HERO 64, a «+14»
## chip), the chapter bar L and the reward tiles — 3 a row, popping in one after another, at most 6 (then «+N»).
## `items`: [{kind: hero | bar | tile, icon, text, from, to, max, frac, pill}] (main builds them with the lines);
## without items the lines are listed. «Забрать» (go L) and «×2» with the ad icon (info M) accept taps only after
## `active_after` s (no ad may start before the ceremony ends, §14.10): grey until then.
func show_ceremony_counters(lines: Array, on_done: Callable, on_double := Callable(), active_after := 3.0, items: Array = []) -> void:
	var hero: Dictionary = {}
	var bar: Dictionary = {}
	var tiles: Array = []
	for it in items:
		match String((it as Dictionary).get("kind", "tile")):
			"hero":
				hero = it
			"bar":
				bar = it
			_:
				tiles.append(it)
	if tiles.size() > 6:  # two rows at most: 5 tiles and one more counting the rest («+3», §6 «Церемония»; main puts the minor ones last)
		var more := tiles.size() - 5
		var rest: Array = []
		for it in tiles.slice(5):
			var pill: Array = (it as Dictionary).get("pill", [["", String((it as Dictionary).get("text", ""))]])
			var parts: Array = []
			for pi in pill:
				parts.append(String((pi as Array)[1]))
			rest.append(String((it as Dictionary).get("name", "")) + " " + " ".join(parts) if (it as Dictionary).has("name") else " ".join(parts))
		var icons: Array = []
		for it in tiles.slice(5):
			icons.append(String((it as Dictionary).get("icon", "")))
		tiles = tiles.slice(0, 5)
		tiles.append({"kind": "more", "text": "+%d" % more, "rest": rest, "icons": icons})
	var listed: Array = lines if items.is_empty() else []
	var rows := ceili(tiles.size() / 3.0)
	var y := 76.0
	var hero_y := y
	if not hero.is_empty():
		y += 120.0
	var bar_y := y
	if not bar.is_empty():
		y += 64.0
	var well_y := y + 8.0
	var well_h := 0.0
	if rows > 0:
		well_h = 16.0 + rows * 150.0 + (rows - 1) * 32.0 + 32.0
	elif not listed.is_empty():
		well_h = 24.0 + listed.size() * 44.0
	var h := well_y + well_h + 32.0 + 116.0 + 32.0
	var box := _modal_box(_win_rect("L", h), false, "", "", "gold", false, true, 0.75)
	box.set_meta("kit_native", true)
	var w := box.size.x
	Kit.title_plate(box, tr("ceremony.title"), "gold", "", true, 64)
	if not hero.is_empty():
		var from := int(hero.get("from", 0))
		var to := int(hero.get("to", 0))
		var num := Kit.label(Kit.fmt_num(to), 64, Kit.INK_TEXT, true)  # HERO 64
		num.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		var nw := Kit.text_w(Kit.fmt_num(maxi(from, to)), 64, "d900", false) + 8.0
		var gain := to - from
		var chip_w := 0.0
		var chip: Panel = null
		if gain != 0:
			chip = Kit.caption_pill(null, ("+" if gain > 0 else Kit.MINUS) + Kit.fmt_num(absi(gain)), 40.0, Kit.face_of("go" if gain > 0 else "war"), 28, 3)
			chip_w = chip.size.x + 16.0
		var gw := 80.0 + 12.0 + nw + chip_w
		var x0 := (w - gw) * 0.5
		var ic := _icon_rect(String(hero.get("icon", "crown")), 80)
		ic.position = Vector2(x0, hero_y)
		box.add_child(ic)
		num.position = Vector2(x0 + 92.0, hero_y - 2.0)
		num.size = Vector2(nw, 84)
		box.add_child(num)
		Kit.count_up(num, from, to, 900)
		if chip != null:
			chip.position = Vector2(x0 + 92.0 + nw + 16.0, hero_y + 20.0)
			box.add_child(chip)
			_pop_later(chip, 0.9)
		var cap := Kit.label(String(hero.get("text", "")), 26, Kit.MUTED_CREAM, true)
		cap.add_theme_font_override("font", Kit.font("d800"))
		cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cap.position = Vector2(32, hero_y + 80.0)
		cap.size = Vector2(w - 64.0, 34)
		box.add_child(cap)
	if not bar.is_empty():
		var bl := Kit.label(String(bar.get("text", "")), 28, Kit.INK_TEXT, true)
		bl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		var lw := Kit.text_w(bl.text, 28, "d900", false) + 8.0
		var bic := _icon_rect(String(bar.get("icon", "hex_tile")), 52)
		bic.position = Vector2(40, bar_y - 6.0)
		box.add_child(bic)
		bl.position = Vector2(100, bar_y - 2.0)
		bl.size = Vector2(lw, 44)
		box.add_child(bl)
		var bx := 100.0 + lw + 16.0
		var to_v := int(bar.get("to", 0))
		var mx := maxi(1, int(bar.get("max", 1)))
		var kb := Kit.bar(box, Rect2(bx, bar_y, w - 40.0 - bx, 40), clampf(float(bar.get("frac", float(to_v) / mx)), 0.0, 1.0), "gold",
			"%d/%d" % [to_v, mx], true)
		kb.name = "chapter"
	var flyers: Array = []  # [tile, res, icon]: the resource rewards fly into their plates when claimed
	if rows > 0:
		var well := Kit.well(box, Rect2(32, well_y, w - 64.0, well_h))
		var tw := (well.size.x - 32.0 - 24.0) / 3.0
		for i in tiles.size():
			var it: Dictionary = tiles[i]
			var in_row := mini(3, tiles.size() - (i / 3) * 3)  # a short last row is centred
			var x0 := 16.0 + (3 - in_row) * (tw + 12.0) * 0.5
			var r := Rect2(x0 + (i % 3) * (tw + 12.0), 16.0 + (i / 3) * 182.0, tw, 150)
			var t: Control
			if String(it.get("kind", "")) == "more":  # the hidden rewards' icons fanned, «+N» on the edge; a tap lists them
				t = Kit.tile(well, r, {"pill": [["", String(it["text"])]]})
				var icons: Array = it.get("icons", [])
				var n := mini(3, icons.size())
				for k in n:
					var fi := _icon_rect(String(icons[k]), 76)
					fi.position = Vector2(r.size.x * 0.5 - 38.0 + (k - (n - 1) * 0.5) * 50.0, 22.0 + absf(k - (n - 1) * 0.5) * 6.0)
					fi.rotation_degrees = (k - (n - 1) * 0.5) * 10.0
					fi.pivot_offset = Vector2(38, 60)
					t.add_child(fi)
				var rest: Array = it.get("rest", [])
				var tt := t
				(t as Kit.KitTile).cb = func(): Kit.tooltip(tt, "", "\n".join(rest))
			else:
				var pill: Array = it.get("pill", [["", String(it.get("text", ""))]])
				t = Kit.tile(well, r, {"icon": String(it.get("icon", "")), "icon_side": 92.0, "pill": pill})
				if it.has("res"):
					flyers.append([t, String(it["res"]), String(it.get("icon", ""))])
			t.name = "reward_%d" % i
			_pop_later(t, 0.35 + 0.08 * i)
	elif not listed.is_empty():
		var well := Kit.well(box, Rect2(32, well_y, w - 64.0, well_h))
		for i in listed.size():
			var l := Kit.label(String(listed[i]), 28, Kit.INK_TEXT, false)
			l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			l.position = Vector2(16, 12.0 + i * 44.0)
			l.size = Vector2(well.size.x - 32.0, 44)
			_fit(l, 28, well.size.x - 32.0)
			well.add_child(l)
	var gate := {"open": false}
	var fy := h - 32.0 - 116.0
	var buttons: Array = []
	var dbl: Kit.KitButton = null
	if on_double.is_valid():
		dbl = Kit.button(box, Rect2(32, fy + 12.0, 280, 92), "info", tr("ceremony.double"), {"icon": "ad", "size": "M", "enabled": false,
			"cb": func(): _claim(gate, flyers, on_double)})
		dbl.name = "double"
		buttons.append(dbl)
	var main_r := Rect2(328, fy, w - 360.0, 116) if dbl != null else Rect2((w - 480.0) * 0.5, fy, 480, 116)
	var done := Kit.button(box, main_r, "go", tr("ceremony.claim"), {"size": "L", "enabled": false,
		"cb": func(): _claim(gate, flyers, on_done)})
	done.name = "claim"
	buttons.append(done)
	var open := func():
		gate["open"] = true
		for b in buttons:
			if is_instance_valid(b):
				(b as Kit.KitButton).enabled = true
				(b as Kit.KitButton).rebuild()
	if active_after <= 0.0:
		open.call()
	else:
		get_tree().create_timer(active_after).timeout.connect(open)


## «Забрать» / «×2» of the ceremony once open: the rewards fly into their plates, then `cb` runs.
func _claim(gate: Dictionary, flyers: Array, cb: Callable) -> void:
	if not gate["open"]:
		return
	_fly_rewards(flyers)
	cb.call()


var pill_of := Callable()  # res -> the HUD's resource plate (main wires hud.res_pills): the ceremony's rewards fly into it


## The claimed rewards fly into their resource plates (§3.6 COUNT_UP, §6 «Церемония»): each tile's icon arcs up to
## its plate in 450 ms (60 ms apart), shrinking, and the plate bumps 1 → 1.1 → 1 (180 ms) as it lands. On a layer
## above the currency plates, so it outlives the closing window; nothing with reduced motion or headless.
func _fly_rewards(srcs: Array) -> void:
	if not pill_of.is_valid() or Kit._dur(0.45) <= 0.0 or srcs.is_empty():
		return
	var layer := CanvasLayer.new()
	layer.name = "reward_fly"
	layer.layer = 4
	add_child(layer)
	var k := 0
	for s in srcs:
		var src: Control = s[0]
		var pill: Control = pill_of.call(String(s[1]))
		var tex := Kit.icon_tex(String(s[2]))
		if not is_instance_valid(src) or pill == null or not pill.is_visible_in_tree() or tex == null:
			continue
		var ic := TextureRect.new()
		ic.texture = tex
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ic.size = Vector2(92, 92)
		ic.pivot_offset = ic.size * 0.5
		var from := src.get_global_rect().get_center() + Vector2(0, -12)
		var pr := pill.get_global_rect()
		var to := Vector2(pr.position.x + 30.0, pr.get_center().y)  # the plate's icon
		var via := Vector2(from.x + (to.x - from.x) * 0.15, to.y + (from.y - to.y) * 0.3)  # up first, then across
		ic.position = from - ic.size * 0.5
		layer.add_child(ic)
		var tw := ic.create_tween()
		tw.tween_interval(0.06 * k)
		tw.tween_method(func(t: float) -> void:
			var p := from.lerp(via, t).lerp(via.lerp(to, t), t)
			ic.position = p - ic.size * 0.5
			ic.scale = Vector2.ONE * lerpf(1.0, 0.62, t), 0.0, 1.0, 0.45).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
		tw.tween_callback(func() -> void:
			ic.queue_free()
			if is_instance_valid(pill):
				pill.pivot_offset = pill.size * 0.5
				var bump := pill.create_tween()
				bump.tween_property(pill, "scale", Vector2(1.1, 1.1), 0.09).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
				bump.tween_property(pill, "scale", Vector2.ONE, 0.09))
		k += 1
	get_tree().create_timer(0.45 + 0.06 * k + 0.4).timeout.connect(layer.queue_free)


## Inbox (the mail button, docs/ui_style.md §6 «Почта»): a window L with the info plate and the mail icon; the reports
## newest first as rows — the sender's picture 72 (the advisor's face, else the report's kind as an icon), the title, the
## time in a chip («5 мин»), one muted line of the text. An unread report is a light row with a red dot, a read one sits
## in the well's colour. A tap opens the whole text (BODY 28) in the row, a second tap folds it.
## items: [{title, text, t (unix), read}]; title / text are translation keys packed with their arguments (l10n.gd
## `pack`), shown in the current language.
const INBOX_ICON := {"raid": "swords", "defense": "shield", "defense_lost": "shield", "defeat": "white_flag",
	"war": "swords", "ai_war": "swords", "counter": "swords", "coalition_war": "swords", "ultimatum": "seal",
	"ceded": "hex_tile", "tribute": "coins", "war_cap": "treaty", "peace_offer": "dove", "ai_peace": "dove",
	"separate": "dove", "separate_offer": "dove", "ruin": "hammer", "expansion": "globe", "all_stars": "trophy",
	"chapter_done": "trophy", "ai_dl": "crown", "oil": "barrel", "alliance": "handshake", "alliance_broken": "handshake",
	"ally_joins": "handshake", "ally_asks": "handshake", "ai_alliance": "handshake", "pact": "handshake",
	"coalition": "horn", "coalition_broken": "horn", "alarm": "horn", "swap": "scales", "swap_offer": "scales",
	"subsidy": "coins", "patent_key": "key"}
const INBOX_ROW := 104.0
const INBOX_PAD := Vector2(20, 16)
var _inbox_open := -1  # the report opened in the list (its index in items)
var _inbox_unread := {}  # index -> true: unread when the inbox opened (they keep that look while it re-renders)
var _inbox_scroll := 0


func show_inbox(items: Array, now: int) -> void:
	var again := _modal != null and _modal.has_meta("inbox")
	if not again:
		_inbox_open = -1
		_inbox_scroll = 0
		_inbox_unread = {}
		for i in items.size():
			if not bool((items[i] as Dictionary).get("read", false)):
				_inbox_unread[i] = true
	var w := 893.0
	var rw := w - 64.0 - 12.0  # the rows leave the scroll bar's lane
	var text_w := rw - INBOX_PAD.x * 2.0 - 72.0 - 16.0
	var body_f := Kit.font("b800")
	var heights := {}
	var content_h := 0.0
	for i in range(items.size() - 1, -1, -1):
		var rh := INBOX_ROW
		if i == _inbox_open:
			var body := L.t(String(items[i]["text"]))
			rh = INBOX_PAD.y + 40.0 + 6.0 + body_f.get_multiline_string_size(body, HORIZONTAL_ALIGNMENT_LEFT, text_w, 28).y * 1.02 + INBOX_PAD.y + 5.0
			rh = maxf(INBOX_ROW, rh)
		heights[i] = rh
		content_h += rh + 12.0
	content_h = maxf(0.0, content_h - 12.0) + 8.0
	var empty := items.is_empty()
	var box := _modal_box(_win_rect("L", 72.0 + (220.0 if empty else content_h) + 32.0), false, tr("inbox.title"), "mail", "info", true, false)
	_modal.set_meta("inbox", true)
	box.set_meta("kit_native", true)
	w = box.size.x
	if empty:
		var ic := _icon_rect("mail", 96)
		ic.position = Vector2((w - 96.0) * 0.5, 84)
		box.add_child(ic)
		var el := Kit.label(tr("inbox.empty"), 28, Kit.MUTED_CREAM, false)
		el.name = "empty"
		el.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		el.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		el.position = Vector2(48, 192)
		el.size = Vector2(w - 96.0, 80)
		box.add_child(el)
		return
	var list := Control.new()
	list.name = "list"
	list.mouse_filter = Control.MOUSE_FILTER_IGNORE
	list.position = Vector2(32, 72)
	list.size = Vector2(w - 64.0, box.size.y - 72.0 - 32.0)
	box.add_child(list)
	var host: Control = list
	if content_h > list.size.y + 1.0:
		var sc: Dictionary = Kit.scroller(list, content_h, Kit.CREAM)
		host = sc["inner"]
		var scroll: ScrollContainer = sc["scroll"]
		scroll.get_v_scroll_bar().value_changed.connect(func(v: float): _inbox_scroll = int(v))
		Kit.scroll_to(scroll, float(_inbox_scroll))
	var y := 0.0
	for i in range(items.size() - 1, -1, -1):
		var it: Dictionary = items[i]
		var rh: float = heights[i]
		_inbox_row(host, Rect2(0, y, rw, rh), it, now, i, items)
		y += rh + 12.0


func _inbox_row(host: Control, r: Rect2, it: Dictionary, now: int, idx: int, items: Array) -> void:
	var unread := _inbox_unread.has(idx)
	var open := idx == _inbox_open
	var face := Kit.CREAM_ROW if unread else Kit.CREAM_WELL
	var t := Kit.KitTile.new()
	t.name = "report_%d" % idx
	var sb := Kit.style(face, 20, 0, Kit.INK, 0, 5)
	sb.set_meta("kit_kind", "")
	sb.set_meta("kit_lip_color", Kit.ROW_LIP if unread else Kit.CREAM_DEEP)
	t.add_theme_stylebox_override("panel", sb)
	t.add_child(Kit.KitDecor.new())
	t.position = r.position
	t.size = r.size
	t.cb = func():
		_inbox_open = -1 if open else idx
		show_inbox(items, now)
	host.add_child(t)
	var title_key := String(it["title"]).split("|")[0]
	var kind := title_key.trim_prefix("inbox.").trim_suffix(".title")
	var pic: Control
	if kind == "advisor" and ResourceLoader.exists("res://assets/ui/portraits/cmd_bram_smile.png"):
		pic = _cmd_face("cmd_bram", "common", 72.0)
		(pic.get_child(0) as Control).set("mood", "smile")
	else:
		pic = _icon_rect(String(INBOX_ICON.get(kind, "mail")), 72)
	pic.name = "pic"
	pic.position = Vector2(INBOX_PAD.x, INBOX_PAD.y)
	t.add_child(pic)
	if unread:
		Kit.dot(pic, -1, "war").name = "new"
	var x := INBOX_PAD.x + 72.0 + 16.0
	var ago := maxi(0, now - int(it["t"]))
	var when := tr("time.just_now") if ago < 60 else (tr("time.m") % (ago / 60) if ago < 3600 else (tr("time.h") % (ago / 3600) if ago < 86400 else tr("time.d") % (ago / 86400)))
	var tc := Kit.chip(t, Vector2.ZERO, "", when, "status", Kit.CLEAR, {"size": 22})
	tc.name = "time"
	tc.position = Vector2(r.size.x - INBOX_PAD.x - tc.size.x, INBOX_PAD.y + 3.0)
	var tw := tc.position.x - 16.0 - x
	var title := L.t(String(it["title"]))
	var ts := Kit.fit_size(title, 30, tw, "d900", 26, false)
	var tl := Kit.label(title, ts, Kit.INK_TEXT, true)
	tl.name = "title"
	tl.add_theme_font_size_override("font_size", ts)
	tl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	tl.clip_text = true
	tl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	tl.position = Vector2(x, INBOX_PAD.y - 2.0)
	tl.size = Vector2(tw, 40)
	t.add_child(tl)
	var body := L.t(String(it["text"]))
	var bl := Kit.label(body, 28 if open else 26, Kit.SOFT_CREAM if open else Kit.MUTED_CREAM, false)
	bl.name = "body" if open else "preview"
	bl.position = Vector2(x, INBOX_PAD.y + 40.0 + 2.0)
	if open:
		bl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		bl.size = Vector2(r.size.x - INBOX_PAD.x - x, r.size.y - bl.position.y - INBOX_PAD.y - 5.0)
	else:
		bl.text = body.replace("\n", " ")
		bl.clip_text = true
		bl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		bl.size = Vector2(r.size.x - INBOX_PAD.x - x, 36)
	t.add_child(bl)


## «Военный пропуск» (canon §15.6, docs/ui_style.md §6 «Военный пропуск»): a sheet L with the gold plate. The header: the
## level hex R 40, the XP bar L with the star, the season's time left in a chip. The track scrolls in a well: a spine of
## level hexes down the middle (the reached ones filled info), the free rewards (tiles 150) on the left, the premium ones
## on the right on a gold-tinted well whose header has a lock while premium is not bought (and every premium tile a
## small lock). A reward to take breathes in a gold outline and a tap takes it (on_claim(level, track)); a taken one has
## a check and fades to 60 %; a tap on any other tile says what it is and when it opens. The list opens at the first
## reward to take, else at the current level. The purchase in the footer (only where payments work): «Премиум» gold L
## with its price, «Элитный» gold M with the ribbon «+15 уровней» (after premium: «Элитный» alone for the difference).
## info: {season, days_left, level, xp_in_level, premium, elite, can_buy, price, price_elite, price_up,
##   rows: [{lvl, free_text, free_state, prem_text, prem_state, free_rw?, prem_rw?}]} — state: "claim" | "claimed" |
##   "locked"; *_rw: the reward as the pass keeps it ([kind, …]); without it the text is read back
const PASS_ROW := 174.0  # a level's row on the track: a tile 150 and its amount pill hanging under it
const PASS_SPINE_R := 30.0


func show_pass(info: Dictionary, on_claim: Callable, on_buy: Callable) -> void:
	var level := int(info["level"])
	var premium := bool(info["premium"])
	var elite := bool(info.get("elite", false))
	var can_buy := bool(info.get("can_buy", false))
	var foot := ""
	if can_buy and not premium:
		foot = "both"
	elif can_buy and not elite:
		foot = "up"
	var keep := _modal != null and _modal.has_meta("pass")
	var at := _pass_scroll if keep else -1
	var box := _modal_box(_win_rect("L", 4000.0), false, tr("pack.pass"), "medal", "gold", true, false)
	_modal.set_meta("pass", true)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var h := box.size.y
	# ---- the header: level, XP, the season's time left
	var lv := Kit.hex_badge(box, Vector2(32 + 40, 72 + 40), 40, "info", str(level))
	lv.name = "level"
	var tc := _paper_chip(box, Vector2.ZERO, "hourglass", tr("pass.days_chip") % int(info.get("days_left", 0)), 220.0)
	tc.name = "season_left"
	tc.position = Vector2(w - 32.0 - tc.size.x, 112.0 - tc.size.y * 0.5)
	var xp := clampi(int(info.get("xp_in_level", 0)), 0, 1000)
	var bx := 32.0 + 80.0 + 40.0
	var xb := Kit.bar(box, Rect2(bx, 92, tc.position.x - 20.0 - bx, 40), xp / 1000.0, "gold",
		"%s/%s" % [fmt_num(xp), fmt_num(1000)], true)
	xb.name = "xp"
	var star := _icon_rect("xp", 60)
	star.position = Vector2(bx - 30.0, 82)
	box.add_child(star)
	# ---- the footer: the purchase
	var fy := h - 32.0 - 116.0
	if foot == "both":
		var eb := Kit.button(box, Rect2(32, fy + 14.0, 300, 88), "gold", tr("pass.elite"),
			{"size": "M", "price": [["", Kit.store_price(String(info.get("price_elite", "")))]], "cb": func(): on_buy.call("iap_pass_elite")})
		eb.name = "buy_elite"
		Kit.ribbon(box, Vector2(eb.position.x + eb.size.x * 0.5, eb.position.y), tr("pass.plus15"), "war")
		var pb := Kit.button(box, Rect2(348, fy, w - 380.0, 116), "gold", tr("pass.premium"),
			{"size": "L", "icon": "medal", "price": [["", Kit.store_price(String(info.get("price", "")))]], "cb": func(): on_buy.call("iap_pass")})
		pb.name = "buy_premium"
	elif foot == "up":  # premium → elite for the difference (09 §9.12)
		var ub := Kit.button(box, Rect2((w - 480.0) * 0.5, fy, 480, 116), "gold", tr("pass.elite"),
			{"size": "L", "icon": "medal", "price": [["", Kit.store_price(String(info.get("price_up", "")))]], "cb": func(): on_buy.call("iap_pass_elite_up")})
		ub.name = "buy_elite"
		Kit.ribbon(box, Vector2(ub.position.x + ub.size.x * 0.5, ub.position.y), tr("pass.plus15"), "war")
	# ---- the track
	var wy := 168.0
	var wb := (fy - 28.0) if foot != "" else h - 32.0
	var well := Kit.well(box, Rect2(32, wy, w - 64.0, wb - wy))
	var ww := well.size.x
	var cx := roundf(ww * 0.5) - 6.0  # the spine (the scroll bar's lane takes the right 12 px)
	var col_free := (16.0 + cx - 46.0) * 0.5
	var prem_x := cx + 46.0
	var prem := Panel.new()  # the premium column: a gold-tinted well from the header down
	prem.name = "premium_well"
	var psb := Kit.style(Kit.PREMIUM_WELL, 20, 0, Kit.INK, 0, 0)
	psb.set_meta("kit_kind", "")
	prem.add_theme_stylebox_override("panel", psb)
	prem.mouse_filter = Control.MOUSE_FILTER_IGNORE
	prem.position = Vector2(prem_x, 8)
	prem.size = Vector2(ww - 20.0 - prem_x, well.size.y - 16.0)
	well.add_child(prem)
	var col_prem := prem_x + prem.size.x * 0.5
	var head_h := 56.0
	for k in 2:
		var hl := Kit.label(tr("pass.free") if k == 0 else tr("pass.premium"), 28, Kit.MUTED_CREAM if k == 0 else Kit.WARN_CREAM, true)
		hl.name = "head_free" if k == 0 else "head_premium"
		hl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		hl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		var hw := Kit.text_w(hl.text, 28, "d900", false) + 8.0
		var ccx: float = col_free if k == 0 else col_prem
		var lock_w := 44.0 if k == 1 and not premium else 0.0
		hl.position = Vector2(roundf(ccx - (hw + lock_w) * 0.5 + lock_w), 10)
		hl.size = Vector2(hw, 40)
		well.add_child(hl)
		if lock_w > 0.0:
			var lk := _icon_rect("lock", 38)
			lk.name = "premium_lock"
			lk.position = Vector2(hl.position.x - 44.0, 11)
			well.add_child(lk)
	var list := Control.new()  # the scrolling part under the column headers
	list.name = "track"
	list.position = Vector2(0, head_h)
	list.size = Vector2(ww, well.size.y - head_h)
	list.mouse_filter = Control.MOUSE_FILTER_IGNORE
	well.add_child(list)
	var rows: Array = info["rows"]
	var content_h := 8.0 + rows.size() * PASS_ROW + 8.0
	var sc: Dictionary = Kit.scroller(list, content_h, Kit.CREAM_WELL)
	var host: Control = sc["inner"]
	for f in ["fade_top", "fade_bottom"]:  # the fades stop at the premium column (it has its own colour)
		var fd := list.get_node(f) as Control
		fd.size.x = prem_x - fd.position.x
	for f2 in ["fade_top", "fade_bottom"]:
		var src := list.get_node(f2) as TextureRect
		var pf := TextureRect.new()
		pf.name = f2 + "_premium"
		pf.texture = Kit.vgradient(Kit.PREMIUM_WELL, Kit.alpha(Kit.PREMIUM_WELL, 0.0)) if f2 == "fade_top" \
			else Kit.vgradient(Kit.alpha(Kit.PREMIUM_WELL, 0.0), Kit.PREMIUM_WELL)
		pf.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		pf.stretch_mode = TextureRect.STRETCH_SCALE
		pf.mouse_filter = Control.MOUSE_FILTER_IGNORE
		pf.position = Vector2(prem_x, src.position.y)
		pf.size = Vector2(prem.size.x, src.size.y)
		list.add_child(pf)
		src.visibility_changed.connect(func(): pf.visible = src.visible)
		pf.visible = src.visible
	var scroll: ScrollContainer = sc["scroll"]
	scroll.get_v_scroll_bar().value_changed.connect(func(v: float): _pass_scroll = int(v))
	# the spine: a CREAM_DEEP track, filled info down to the current level
	var y0 := 8.0 + PASS_ROW * 0.5 - 12.0
	var y1 := 8.0 + (rows.size() - 1) * PASS_ROW + PASS_ROW * 0.5 - 12.0
	var spine := Panel.new()
	spine.name = "spine"
	var ssb := Kit.style(Kit.CREAM_DEEP, 8, 0, Kit.INK, 0, 0)  # a pill: Godot fits R 8 to the 12 px bar
	ssb.set_meta("kit_kind", "")
	spine.add_theme_stylebox_override("panel", ssb)
	spine.mouse_filter = Control.MOUSE_FILTER_IGNORE
	spine.position = Vector2(cx - 6.0, y0)
	spine.size = Vector2(12, maxf(0.0, y1 - y0))
	host.add_child(spine)
	var reach := clampi(level, 0, rows.size())
	if reach > 1:
		var fill := Panel.new()
		fill.name = "spine_fill"
		var fsb := Kit.style(Kit.face_of("info"), 8, 0, Kit.INK, 0, 0)
		fsb.set_meta("kit_kind", "")
		fill.add_theme_stylebox_override("panel", fsb)
		fill.mouse_filter = Control.MOUSE_FILTER_IGNORE
		fill.position = spine.position
		fill.size = Vector2(12, (reach - 1) * PASS_ROW)
		host.add_child(fill)
	var first_claim := -1
	for i in rows.size():
		var r: Dictionary = rows[i]
		var lvl := int(r["lvl"])
		var ty := 8.0 + i * PASS_ROW
		var hy := ty + PASS_ROW * 0.5 - 12.0
		var reached := lvl <= level
		var hb := Kit.hex_badge(host, Vector2(cx, hy), PASS_SPINE_R, "info", str(lvl), Kit.CLEAR if reached else Kit.CREAM_DEEP)
		hb.name = "lvl_%d" % lvl
		for k in 2:
			var track: String = ["free", "premium"][k]
			var state := String(r["free_state" if k == 0 else "prem_state"])
			var txt := String(r["free_text" if k == 0 else "prem_text"])
			var rw: Array = r.get("free_rw" if k == 0 else "prem_rw", [])
			var look := _pass_look_rw(rw) if not rw.is_empty() else _pass_look(txt)
			# only the first reward to take breathes (§3.6: one per screen); the others keep the gold outline
			var o := {"icon_side": 88.0, "claimable": state == "claim", "taken": state == "claimed",
				"still": state == "claim" and first_claim >= 0}
			if look.has("tex"):
				o["tex"] = look["tex"]
				o["icon_side"] = 108.0
			else:
				o["icon"] = String(look.get("icon", "gift"))
			if String(look.get("pill", "")) != "":
				o["pill"] = [["", String(look["pill"])]]
			if k == 1:
				o["face"] = Kit.CREAM_ROW
			var tx: float = (col_free if k == 0 else col_prem) - 75.0
			var t := Kit.tile(host, Rect2(tx, ty, 150, 150), o)
			t.name = "%s_%d" % [track, lvl]
			if state == "claim":
				if first_claim < 0:
					first_claim = i
				t.cb = func(): on_claim.call(lvl, track)
			else:
				var why := tr("pass.taken") if state == "claimed" else (tr("pass.prem_lock") if k == 1 and not premium \
					else tr("pass.at_level") % lvl)
				t.cb = func(): Kit.tooltip(t, txt, why)
			if k == 1 and not premium and state != "claimed":
				var lb := _icon_rect("lock", 40)
				lb.name = "lock"
				lb.position = Vector2(150.0 - 34.0, -8.0)
				t.add_child(lb)
	# open at the first reward to take, else at the current level (a refresh after a claim keeps the place)
	var target := first_claim if first_claim >= 0 else maxi(0, level - 1)
	var y := float(at) if at >= 0 else 8.0 + target * PASS_ROW - 8.0
	Kit.scroll_to(scroll, y)


var _pass_scroll := 0  # the track's scroll (kept while the pass re-renders after a claim)
var _tmpl_cache := {}


## A localized template (pass.rw_res: «Ресурсы %d ч») as a pattern that reads its numbers / names back.
func _tmpl_re(key: String) -> RegEx:
	return _tmpl_re_text(tr(key))


## The same from a template already in the current language (a count's plural form put into a line).
func _tmpl_re_text(t: String) -> RegEx:
	if _tmpl_cache.has(t):
		return _tmpl_cache[t]
	var pat := ""
	var i := 0
	while i < t.length():
		if t[i] == "%" and i + 1 < t.length() and t[i + 1] in ["d", "s"]:
			pat += "(\\d+)" if t[i + 1] == "d" else "(.+)"
			i += 2
			continue
		var ch := t[i]
		pat += ("\\" + ch) if "\\^$.|?*+()[]{}".contains(ch) else ch
		i += 1
	var re := RegEx.create_from_string("^" + pat + "$")
	_tmpl_cache[t] = re
	return re


## How a pass reward shows on a tile: {icon | tex, pill}. From the pass's own reward ([kind, …]).
func _pass_look_rw(rw: Array) -> Dictionary:
	match String(rw[0]):
		"res":
			return {"icon": "crate", "pill": tr("time.h") % int(rw[1])}
		"crate":
			return {"icon": "chest_wood", "pill": "×%d" % int(rw[1]) if int(rw[1]) > 1 else ""}
		"raivite":
			return {"icon": "raivite", "pill": fmt_num(int(rw[1]))}
		"shards":
			var p := "res://assets/ui/portraits/%s.png" % String(rw[1])
			var o := {"pill": "×%d" % int(rw[2])}
			if ResourceLoader.exists(p):
				o["tex"] = load(p)
			else:
				o["icon"] = "shard"
			return o
		"speed":
			return {"icon": "lightning", "pill": tr("time.h") % int(rw[1])}
		"cosmetic":
			return {"icon": String(Kit.COSMETIC_ICON.get(String(CasesSim.cosmetic(String(rw[1])).get("category", "")), "frame")), "pill": ""}
	return {"icon": "gift", "pill": ""}


## The same from the reward's text (what main passes today): the text is matched against the pass.rw_* templates.
func _pass_look(text: String) -> Dictionary:
	if text == "":
		return {"icon": "gift", "pill": ""}
	var m := _tmpl_re("pass.rw_res").search(text)
	if m:
		return _pass_look_rw(["res", int(m.get_string(1))])
	if text == tr("pass.rw_crate"):
		return _pass_look_rw(["crate", 1])
	m = _tmpl_re("pass.rw_crates").search(text)
	if m:
		return _pass_look_rw(["crate", int(m.get_string(1))])
	m = _tmpl_re("pass.rw_raivite").search(text)
	if m:
		return _pass_look_rw(["raivite", int(m.get_string(1))])
	m = _tmpl_re("pass.rw_shards").search(text)
	for f in ["one", "few", "many", "other"]:  # «4 осколка: Генерал Вега» (L.plural, pass.rw_shards_n)
		if m == null:
			m = _tmpl_re_text(tr("pass.rw_shards_n") % [tr("plural.shards." + f), "%s"]).search(text)
	if m:
		var who := m.get_string(2)
		var cmds: Dictionary = CasesSim.data().get("commanders", {})
		for id in cmds:
			if CasesSim.commander_name(String(id)) == who:
				return _pass_look_rw(["shards", String(id), int(m.get_string(1))])
		return {"icon": "shard", "pill": "×%d" % int(m.get_string(1))}
	m = _tmpl_re("pass.rw_speed").search(text)
	if m:
		return _pass_look_rw(["speed", int(m.get_string(1))])
	var cats: Dictionary = CasesSim.data().get("categories", {})
	for cat in cats:  # a cosmetic: «<category> «<name>»»
		if text.begins_with(CasesSim.category_name(String(cat)) + " "):
			return {"icon": String(Kit.COSMETIC_ICON.get(String(cat), "frame")), "pill": ""}
	return {"icon": "gift", "pill": ""}

## The 28-day login calendar (08 §8.8, docs/ui_style.md §6 «Календарь»): a window L with the gold plate. A header line
## with the day chip and the «i» that holds the rules; a well of 7 × 4 tiles — the day in a hex, the reward's icon 64 and
## its amount in a pill. Days 7/14/21/28 are gold-backed with the ribbon «Приз»; today glows in a gold outline (and
## breathes), a taken day has a check and fades to 55 %. A tap on a tile tells the reward. The footer: «Забрать» (go)
## and, where allowed, «×2» (info, with the ad icon — or the Patent's) on the left; when nothing waits, when the next one
## comes.
## info: {cycle, days: [{day, text, state: claimed|today|future, key, rw?}], pending, can_double, patent}
const CAL_TILE := Vector2(109, 132)
const CAL_ROW_GAP := 22.0


func show_calendar(info: Dictionary, on_claim: Callable) -> void:
	var days: Array = info["days"]
	var pending := bool(info["pending"])
	var grid_h := 12.0 + 4.0 * CAL_TILE.y + 3.0 * CAL_ROW_GAP + 26.0
	var h := 72.0 + 52.0 + 16.0 + grid_h + 32.0 + 112.0 + 32.0
	var title := tr("cal.title1") if int(info["cycle"]) == 1 else tr("cal.title2")
	var box := _modal_box(_win_rect("L", h), false, title, "calendar", "gold", true, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	# ---- the header: which day it is, the rules in the «i»
	var today := 0  # the waiting day, else the last one taken
	for d in days:
		if String(d["state"]) == "today":
			today = int(d["day"])
			break
		if String(d["state"]) == "claimed":
			today = maxi(today, int(d["day"]))
	var dc := Kit.chip(box, Vector2(32, 72 + 9), "calendar", tr("cal.day_of") % [maxi(1, today), days.size()], "status")
	dc.name = "day"
	var ib := Kit.info_button(box, Vector2(w - 32.0 - 26.0, 72 + 26), Callable())
	ib.cb = func(): Kit.tooltip(ib, title, tr("cal.rule"))
	# ---- the 28 days
	var well := Kit.well(box, Rect2(32, 72.0 + 52.0 + 16.0, w - 64.0, grid_h))
	well.name = "days"
	var gx := (well.size.x - 24.0 - 7.0 * CAL_TILE.x) / 6.0
	for d in days:
		var day := int(d["day"])
		var i := day - 1
		var st := String(d["state"])
		var key := day % 7 == 0
		var look := _cal_look(d.get("rw", []), String(d.get("text", "")))
		var o := {"icon_side": 64.0, "pill_inside": true, "face": Kit.PREMIUM_WELL if key else Kit.CREAM_ROW,
			"claimable": st == "today" and pending, "taken": st == "claimed"}
		if look.has("tex"):
			o["tex"] = look["tex"]
		else:
			o["icon"] = String(look.get("icon", "gift"))
		if String(look.get("pill", "")) != "":
			o["pill"] = [["", String(look["pill"])]]
		var r := Rect2(12.0 + (i % 7) * (CAL_TILE.x + gx), 12.0 + (i / 7) * (CAL_TILE.y + CAL_ROW_GAP), CAL_TILE.x, CAL_TILE.y)
		var t := Kit.tile(well, r, o)
		t.name = "day_%d" % day
		if st == "claimed":
			t.modulate.a = 0.55
		var role := "gold" if key else ("info" if st != "future" else "")
		var hb := Kit.hex_badge(t, Vector2(14, 14), 18, role if role != "" else "info", str(day), Kit.CLEAR if role != "" else Kit.CREAM_DEEP.darkened(0.2))
		hb.name = "num"
		var second := String(look.get("second", ""))
		if second != "":
			var si := _icon_rect(second, 40)
			si.name = "second"
			si.position = Vector2(CAL_TILE.x - 42.0, 2)
			t.add_child(si)
		if key:
			var rb := Kit.ribbon(t, Vector2(CAL_TILE.x * 0.5, CAL_TILE.y + 2.0), tr("cal.prize"), "war")
			rb.name = "prize"
		var tip_t := tr("cal.day_n") % day
		var tip := String(d.get("text", ""))
		t.cb = func(): Kit.tooltip(t, tip_t, tip)
	# ---- the footer
	var fy := box.size.y - 32.0 - 112.0
	if pending:
		var main_r := Rect2((w - 480.0) * 0.5, fy, 480, 112)
		if bool(info.get("can_double", false)):
			var pat := bool(info.get("patent", false))
			var dw := (w - 64.0 - 16.0) * 0.4
			var db := Kit.button(box, Rect2(32, fy, dw, 112), "info", "×2", {"size": "L", "icon": "charter" if pat else "ad",
				"cb": func(): on_claim.call(true)})
			db.name = "double"
			main_r = Rect2(32.0 + dw + 16.0, fy, w - 64.0 - dw - 16.0, 112)
		var cb_ := Kit.button(box, main_r, "go", tr("ui.claim"), {"size": "L", "cb": func(): on_claim.call(false)})
		cb_.name = "claim"
	else:
		var nx := _paper_chip(box, Vector2(w * 0.5, fy + 56.0), "hourglass", tr("cal.tomorrow"), w - 64.0)
		nx.name = "next"


## How a calendar day shows on its tile: {icon | tex, pill, second} from its rewards ([kind, …], calendar.gd); the
## first reward is the picture, a second one a small icon in the corner. Without them, the reward's text is read back.
func _cal_look(rw: Array, text: String) -> Dictionary:
	if rw.is_empty():
		return _pass_look(text)
	var r: Array = rw[0]
	var o := {}
	match String(r[0]):
		"speed":
			var cnt := int(r[2]) if r.size() > 2 else 1
			o = {"icon": "lightning", "pill": tr("time.h") % int(r[1]) + (" ×%d" % cnt if cnt > 1 else "")}
		"builder":
			o = {"icon": "mason", "pill": "+1"}
		"cmd":
			var p := "res://assets/ui/portraits/%s.png" % String(r[1])
			o = {"tex": load(p)} if ResourceLoader.exists(p) else {"icon": "frame"}
		"shards_pick", "shards_choice":
			o = {"icon": "shard", "pill": "×%d" % int(r[1])}
		"season_cosmetic":
			o = {"icon": "frame"}
		_:
			o = _pass_look_rw(r)
	if rw.size() > 1:
		var r2: Array = rw[1]
		var l2 := _pass_look_rw(r2)
		o["second"] = String(l2.get("icon", "gift"))
	return o


## «15 осколков на выбор» (08 §8.8.2, the calendar's day 26): a decision window L with the gold plate — no ✕, the shards
## must go to someone. One option card per common and rare commander: the portrait with its level, the name, the
## shards it has in a chip, «Выбрать» (go S) → on_pick(id).
## rows: [{id, name, rarity, have, level}]
func show_shard_pick(n: int, rows: Array, on_pick: Callable) -> void:
	var cols := 4
	var ch := 320.0
	var lines := maxi(1, ceili(rows.size() / float(cols)))
	var grid_h := 16.0 + lines * ch + (lines - 1) * 16.0 + 16.0
	var h := 72.0 + 44.0 + 16.0 + grid_h + 32.0
	var box := _modal_box(_win_rect("L", h), false, tr("cal.pick_title2") % L.plural(n, "plural.shards"), "shard", "gold", false, true)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var q := Kit.label(tr("cal.pick_q"), 28, Kit.SOFT_CREAM, false)
	q.name = "question"
	q.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	q.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	q.position = Vector2(32, 72)
	q.size = Vector2(w - 64.0, 44)
	box.add_child(q)
	var well := Kit.well(box, Rect2(32, 72.0 + 44.0 + 16.0, w - 64.0, grid_h))
	var cw := (well.size.x - 32.0 - (cols - 1) * 12.0) / cols
	for i in rows.size():
		var r: Dictionary = rows[i]
		var id := String(r["id"])
		var cr := Rect2(16.0 + (i % cols) * (cw + 12.0), 16.0 + (i / cols) * (ch + 16.0), cw, ch)
		var card := Kit.tile(well, cr, {})
		card.name = id
		var face := _cmd_face(id, String(r["rarity"]), 120.0, int(r.get("level", 0)))
		face.position = Vector2((cw - 120.0) * 0.5, 12)
		card.add_child(face)
		var nm := String(r["name"])
		var two := Kit.text_w(nm, 22, "d900", false) > cw - 16.0
		var fs := 22 if two else Kit.fit_size(nm, 26, cw - 16.0, "d900", 22, false)
		var nl := Kit.label(nm, fs, Kit.INK_TEXT, true)
		nl.name = "name"
		nl.add_theme_font_size_override("font_size", fs)
		nl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		nl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		if two:
			nl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			nl.max_lines_visible = 2
			nl.add_theme_constant_override("line_spacing", -4)
		nl.position = Vector2(8, 136)
		nl.size = Vector2(cw - 16.0, 54)
		card.add_child(nl)
		var chip := _paper_chip(card, Vector2(cw * 0.5, 214), "shard", tr("cal.has") % int(r.get("have", 0)), cw - 16.0)
		chip.name = "have"
		var b := Kit.button(card, Rect2(12, ch - 5.0 - 12.0 - 60.0, cw - 24.0, 60), "go", tr("cal.pick_btn2"), {"size": "S",
			"cb": func(): on_pick.call(id)})
		b.name = "pick"


## «Державный патент» (09 §9.13.4, Apple 3.1.2; docs/ui_style.md §6 «Патент»): a window M with the gold plate, the
## charter as its hero, the perks as 8 tiles (icon 80 + two lines; a tap gives the whole perk), the purchase — the trial
## «7 дней» as gold L with its price and the ribbon «Пробный», the month as info M (each price shown once; without a
## trial the month is the gold L itself) — the legal links in one row of text and the renewal terms. While active: a
## chip with the days left instead of the purchase. ✕ closes it.
const PATENT_PERKS := [["patent.k_ads", "patent.p_ads", "ad"], ["patent.k_builder", "patent.p_builder", "builder"],
	["patent.k_convoy", "patent.p_convoy", "cart"], ["patent.k_collect", "patent.p_collect", "coin"],
	["patent.k_timers", "patent.p_timers", "hourglass"], ["patent.k_raivite", "patent.p_raivite", "raivite"],
	["patent.k_key", "patent.p_key", "key"], ["patent.k_frame", "patent.p_frame", "frame"]]


func show_patent(info: Dictionary, on_buy: Callable, on_restore: Callable) -> void:
	var active := bool(info.get("active", false))
	var can_buy := bool(info.get("can_buy", false))
	var trial := bool(info.get("trial", false))
	var buy := can_buy and not active
	var hero := 232.0
	var perk_h := 156.0
	var well_h := 16.0 + 2.0 * perk_h + 12.0 + 16.0
	var legal := tr("patent.renewal")
	var legal_h := 96.0
	var foot_h := (34.0 + 116.0) if buy else (56.0 if active or not can_buy else 0.0)
	var h := 56.0 + hero + 16.0 + well_h + 24.0 + foot_h + 20.0 + 48.0 + 12.0 + legal_h + 32.0
	var box := _modal_box(_win_rect("M", h), false, tr("pack.patent"), "", "gold", true, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var art := _icon_rect("charter", hero)
	art.name = "charter"
	art.position = Vector2((w - hero) * 0.5, 50)
	box.add_child(art)
	var y := 56.0 + hero + 16.0
	var well := Kit.well(box, Rect2(32, y, w - 64.0, well_h))
	var cols := 4
	var tw := (well.size.x - 32.0 - 12.0 * (cols - 1)) / cols
	for i in PATENT_PERKS.size():
		var p: Array = PATENT_PERKS[i]
		var t := _perk_tile(well, Rect2(16.0 + (i % cols) * (tw + 12.0), 16.0 + (i / cols) * (perk_h + 12.0), tw, perk_h),
			String(p[2]), tr(p[0]))
		t.name = "perk_%d" % i
		var full := tr(p[1])
		var short := tr(p[0])
		t.cb = func(): Kit.tooltip(t, short, full)
	y += well_h + 24.0
	if buy:
		var fy := y + 34.0
		var price := Kit.store_price(String(info.get("price", "")))  # RU «7,99 $», EN «$7.99» (§3.7), as in the store
		if trial:
			var mb := Kit.button(box, Rect2(32, fy + 14.0, 260, 88), "info", tr("patent.month_btn") % price,
				{"size": "M", "cb": func(): on_buy.call("iap_sub_patent")})
			mb.name = "buy_month"
			var tb := Kit.button(box, Rect2(308, fy, w - 340.0, 116), "gold", tr("patent.trial_btn"),
				{"size": "L", "price": [["", Kit.store_price(String(info.get("trial_price", "")))]], "cb": func(): on_buy.call("iap_sub_trial")})
			tb.name = "buy_trial"
			Kit.ribbon(box, Vector2(tb.position.x + tb.size.x * 0.5, fy), tr("patent.trial_tag"), "war")
		else:
			var sb := Kit.button(box, Rect2((w - 480.0) * 0.5, fy, 480, 116), "gold", tr("patent.subscribe"),
				{"size": "L", "price": [["", tr("patent.month_btn") % price]], "cb": func(): on_buy.call("iap_sub_patent")})
			sb.name = "buy_month"
		y = fy + 116.0 + 20.0
	elif active:
		var ac := Kit.chip(box, Vector2.ZERO, "", tr("patent.active") % int(info.get("days_left", 0)), "owner",
			Kit.face_of("go"), {"size": 26, "max_w": w - 140.0})
		ac.name = "active"
		ac.position = Vector2(roundf((w - ac.size.x) * 0.5 + 24.0), y + 28.0 - ac.size.y * 0.5)
		Kit.check_badge(box, Vector2(ac.position.x - 24.0, y + 28.0), 44.0)
		y += 56.0 + 20.0
	elif not can_buy:
		var ul := Kit.label(tr("patent.unavailable"), 26, Kit.MUTED_CREAM, false)
		ul.name = "unavailable"
		ul.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		ul.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		ul.position = Vector2(32, y)
		ul.size = Vector2(w - 64.0, 56)
		box.add_child(ul)
		y += 56.0 + 20.0
	var doc := func(): toast(tr("patent.doc_soon"))
	Kit.links(box, Rect2(32, y, w - 64.0, 48), [[tr("patent.terms_link"), doc], [tr("patent.privacy_link"), doc],
		[tr("patent.restore_short"), func(): on_restore.call()]], 26)
	y += 48.0 + 12.0
	var ll := Kit.label(legal, 22, Kit.MUTED_CREAM, false)
	ll.name = "legal"
	ll.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	ll.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ll.max_lines_visible = 4
	ll.position = Vector2(32, y)
	ll.size = Vector2(w - 64.0, legal_h)
	box.add_child(ll)


## A perk on paper: a tile with the icon 80 at the top and two lines of LABEL 24 INK_TEXT under it.
func _perk_tile(parent: Control, r: Rect2, icon: String, text: String) -> Kit.KitTile:
	var t := Kit.tile(parent, r, {"icon": icon, "icon_side": 80.0})
	var pic := t.get_node_or_null("pic") as Control
	if pic:
		pic.position.y = 10.0
	var l := Kit.label(text, 24, Kit.INK_TEXT, true)
	l.add_theme_font_override("font", Kit.font("d800"))
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.max_lines_visible = 2
	l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.add_theme_constant_override("line_spacing", -4)
	l.position = Vector2(6, 92)
	l.size = Vector2(r.size.x - 12.0, r.size.y - 5.0 - 96.0)
	t.add_child(l)
	return t


## «Летопись державы» (07 §7.4, docs/ui_style.md §6 «Летопись»): a sheet L with the info plate, the book and the count
## «2/40» on a chip under it. The rewards to take come first (a section of their own), then the six chapters as section
## headers. A row: the medal of the goal's difficulty (bronze, silver, gold), the name, the progress as an M bar «7/25»,
## the reward tile at the right; a goal reached — go XS «Забрать» with the Raivites in it; taken — a check, the row at
## α 0.7; not in the build yet — a lock. A tap on a row tells the condition and the reward.
const CHR_ICONS := {"map": "hex_tile", "war": "swords", "peace": "dove", "dev": "flask", "cmd": "frame", "arena": "trophy"}
const CHR_ROW := 112.0
const CHR_GAP := 12.0
const CHR_HEAD := 60.0  # a section header (48) and its gap


func show_chronicle(info: Dictionary, on_claim: Callable) -> void:
	var rows: Array = info["rows"]
	var ready: Array = rows.filter(func(r): return String(r["state"]) == "claim")
	var items: Array = []  # [kind, data]: ["head", [text, icon]] | ["row", row]
	if not ready.is_empty():
		items.append(["head", [tr("chr.ready"), "gift"]])
		for r in ready:
			items.append(["row", r])
	var chapter := ""
	for r in rows:
		if String(r["state"]) == "claim":
			continue
		if String(r["chapter"]) != chapter:
			chapter = String(r["chapter"])
			items.append(["head", [tr("chr.ch." + chapter), String(CHR_ICONS.get(chapter, "book"))]])
		items.append(["row", r])
	var content_h := 16.0
	for it in items:
		content_h += CHR_HEAD if it[0] == "head" else CHR_ROW + CHR_GAP
	content_h += 4.0
	var keep := _modal != null and _modal.has_meta("chronicle")
	var at := _chr_scroll if keep else 0
	var box := _modal_box(_win_rect("L", 96.0 + content_h + 32.0), false, tr("chr.name"), "book", "info", true, false)
	_modal.set_meta("chronicle", true)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var cc := Kit.chip(box, Vector2.ZERO, "", "%d/%d" % [int(info["done"]), int(info["total"])], "status")
	cc.name = "count"
	cc.position = Vector2((w - cc.size.x) * 0.5, 34)
	var well := Kit.well(box, Rect2(32, 88, w - 64.0, box.size.y - 88.0 - 32.0))
	var host: Control = well
	var lane := 0.0
	if content_h > well.size.y + 1.0:
		var sc: Dictionary = Kit.scroller(well, content_h)
		host = sc["inner"]
		lane = 12.0
		var scroll: ScrollContainer = sc["scroll"]
		scroll.get_v_scroll_bar().value_changed.connect(func(v: float): _chr_scroll = int(v))
		Kit.scroll_to(scroll, float(at))
	var rw_w := well.size.x - 32.0 - lane
	var y := 16.0
	for it in items:
		if it[0] == "head":
			var hd: Array = it[1]
			Kit.section(host, Vector2(16, y), rw_w, String(hd[0]), String(hd[1]))
			y += CHR_HEAD
			continue
		var r: Dictionary = it[1]
		_chr_row(host, Rect2(16, y, rw_w, CHR_ROW), r, on_claim)
		y += CHR_ROW + CHR_GAP


var _chr_scroll := 0  # the book's scroll (kept while it re-renders after a claim)


func _chr_row(host: Control, rect: Rect2, r: Dictionary, on_claim: Callable) -> Kit.KitRow:
	var code := String(r["code"])
	var st := String(r["state"])
	var need := int(r["need"])
	var prog := mini(int(r["progress"]), need)
	var i := ChronicleSim.index_of(code)
	var rv := int(ChronicleSim.LIST[i][4]) if i >= 0 else 0
	var cos := String(ChronicleSim.LIST[i][5]) if i >= 0 else ""
	var o := {"icon": _chr_medal(code), "title": String(r["name"])}
	var once := need <= 1 and st != "soon"  # a one-time goal: what to do, not a 0/1 bar
	match st:
		"claim":
			o["state"] = "claim"
			o["bar"] = {"frac": 1.0, "role": "go", "text": "%s/%s" % [fmt_num(need), fmt_num(need)]}
			var b := Kit.button(null, Rect2(0, 0, 224, 48), "go", tr("ui.claim"), {"size": "XS",
				"price": [["raivite", str(rv)]], "filter": Control.MOUSE_FILTER_PASS, "cb": func(): on_claim.call(code)})
			b.name = "claim"
			o["right"] = b
		"claimed":
			o["state"] = "done"
			o["bar"] = {"frac": 1.0, "role": "go", "text": "%s/%s" % [fmt_num(need), fmt_num(need)]}
		"soon":
			o["state"] = "locked"
			o["sub"] = tr("chr.soon")
		_:
			o["bar"] = {"frac": float(prog) / maxf(1.0, need), "role": "info", "text": "%s/%s" % [fmt_num(prog), fmt_num(need)]}
	var desc := String(r.get("desc", ""))
	if once:  # the claim row's button leaves little room: «Выполнено!» there, the task itself elsewhere
		o.erase("bar")
		o["sub"] = tr("chr.done_once") if st == "claim" else desc
	if st == "open":  # the reward tile 80, its amount on the bottom edge (§4.9) under the crystal, not over it
		var holder := Control.new()
		holder.name = "reward"
		holder.size = Vector2(88, 100)
		holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var t := Kit.tile(holder, Rect2(4, 0, 80, 80), {"icon": "raivite", "icon_side": 52.0, "pill": [["", str(rv)]],
			"face": Kit.CREAM_WELL})
		t.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if cos != "":  # the goal also gives a cosmetic: its picture on the tile's corner
			var ci := _icon_rect(String(Kit.COSMETIC_ICON.get(String(CasesSim.cosmetic(cos).get("category", "")), "frame")), 40)
			ci.position = Vector2(50, -12)
			t.add_child(ci)
		o["right"] = holder
	var row := Kit.row(host, rect, o)
	row.name = code
	var reward := tr("chr.reward") % rv
	if cos != "":
		reward += "\n" + tr("chr.reward_cos") % CasesSim.cosmetic_name(cos)
	row.cb = func(): Kit.tooltip(row.title_label, String(r["name"]), desc + "\n" + reward)
	return row


## A Chronicle goal's medal (§6 Летопись): its step on the ladder of goals that count the same thing — the first
## bronze, the second silver, the third and on gold; a goal alone on its counter is gold with a cosmetic, silver from a
## target of 20, else bronze.
static func _chr_medal(code: String) -> String:
	var tiers := ["medal_bronze", "medal_silver", "medal_gold"]
	var i := ChronicleSim.index_of(code)
	if i < 0:
		return "medal"
	var row: Array = ChronicleSim.LIST[i]
	var ladder: Array = ChronicleSim.LIST.filter(func(x): return x[2] == row[2])
	if ladder.size() > 1:
		ladder.sort_custom(func(a, b): return int(a[3]) < int(b[3]))
		for k in ladder.size():
			if ladder[k][0] == code:
				return tiers[mini(k, 2)]
	if String(row[5]) != "":
		return tiers[2]
	return tiers[1] if int(row[3]) >= 20 else tiers[0]

## AI ultimatum (canon §9.1, §6 «Ультиматум»): a window L with the war plate; ✕ is «later». The angry leader says it in
## one sentence, a red timer chip counts the time left; three equal choices as option cards in a well — give the hex
## (24 h of peace), pay the tribute (grey when the gold is short: the amount turns red, a tap says how much is
## missing — `short`, in gold), or refuse (war). `hex_tile`: the hex's render key (the card shows the hex itself).
func show_ultimatum(enemy: String, hex_name: String, tribute: int, can_pay: bool, left_sec: int, on_accept: Callable, on_pay: Callable, on_refuse: Callable, portrait := "", plate := Kit.CLEAR, hex_tile := "", short := 0) -> void:
	var h := 64.0 + 170.0 + 40.0 + 332.0 + 32.0
	var box := _modal_box(_win_rect("L", h), false, tr("ult.title"), "", "war", true, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	_leader_seal(box, portrait, plate, Rect2(32, 64, 156, 170), "angry", enemy)
	var bx := 32.0 + 156.0 + 28.0
	Kit.bubble(box, Rect2(bx, 72, w - 32.0 - bx, 100), tr("ult.text") % hex_name, "left")
	var tc := Kit.chip(box, Vector2(bx, 190), "hourglass", Kit.fmt_time(left_sec), "timer_war")
	tc.name = "timer"
	var well := Kit.well(box, Rect2(32, 274, w - 64.0, 332))
	var cw := 255.0
	var gap := (well.size.x - 32.0 - 3.0 * cw) / 2.0
	var hex_tex := _tile_tex(hex_tile)
	var opts := [
		{"tex": hex_tex, "icon": "hex_tile", "title": hex_name, "chip": ["dove", tr("ult.truce")], "role": "go", "cap": tr("ult.accept"),
			"cb": on_accept, "enabled": true},
		{"icon": "coins", "title": Kit.fmt_num(tribute), "role": "go", "cap": tr("ult.pay"), "cb": on_pay, "enabled": can_pay,
			"reason": tr("ult.no_gold") % Kit.fmt_num(short) if short > 0 else tr("toast.no_gold"), "title_color": Kit.NEG_CREAM},
		{"icon": "swords", "title": tr("ult.refuse_title"), "role": "war", "cap": tr("ult.refuse"), "cb": on_refuse, "enabled": true},
	]
	for i in 3:
		var o: Dictionary = opts[i]
		var card := Kit.tile(well, Rect2(16.0 + i * (cw + gap), 16, cw, 300), {})
		card.name = "option_%d" % i
		var tex: Texture2D = o.get("tex") if o.get("tex") != null else Kit.icon_tex(String(o["icon"]))
		var pic := TextureRect.new()
		pic.texture = tex
		pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		pic.position = Vector2((cw - 116.0) * 0.5, 14)
		pic.size = Vector2(116, 116)
		if not bool(o["enabled"]):
			pic.modulate = Kit.LOCK_MOD
		card.add_child(pic)
		var title := String(o["title"])
		var s := Kit.fit_size(title, 30, cw - 24.0, "d900", 22, false)
		var tl := Kit.label(title, s, Kit.INK_TEXT if bool(o["enabled"]) else o.get("title_color", Kit.INK_TEXT), true)
		tl.add_theme_font_size_override("font_size", s)
		tl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		tl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		tl.clip_text = true
		tl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		tl.position = Vector2(12, 134)
		tl.size = Vector2(cw - 24.0, 40)
		card.add_child(tl)
		if o.has("chip"):
			_paper_chip(card, Vector2(cw * 0.5, 196), String(o["chip"][0]), String(o["chip"][1]), cw - 24.0)
		var b := Kit.button(card, Rect2(14, 300 - 5.0 - 14.0 - 64.0, cw - 28.0, 64), String(o["role"]), String(o["cap"]),
			{"size": "S", "cb": o["cb"], "enabled": bool(o["enabled"])})
		b.name = "choice"
		if not bool(o["enabled"]):  # the tip stands over the whole card: the coins and the amount stay in sight
			var why := String(o.get("reason", ""))
			b.denied.connect(func(): Kit.tooltip(card, String(o["cap"]), why))


## An enemy leader's portrait (ultimatum, peace): the face on the state's colour in a TRIM frame (brass DL1–4, steel
## DL5–8; R 20, INK 4, lip 6) and, when given, the state's name in an owner chip on its bottom edge.
func _leader_seal(box: Control, portrait: String, plate: Color, r: Rect2, mood := "", enemy := "") -> void:
	var team: Color = plate if plate.a > 0.0 else Kit.face_of("war")
	var fr := Panel.new()
	fr.name = "leader"
	var sb := Kit.style(Kit.face_of(_trim), 20, 4, Kit.INK, 6, 6)
	sb.set_meta("kit_kind", "")  # a frame, not a button: the lip without the gloss
	fr.add_theme_stylebox_override("panel", sb)
	fr.position = r.position
	fr.size = r.size
	fr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(fr)
	fr.add_child(Kit.KitDecor.new())
	var well := Panel.new()
	var wsb := Kit.style(team, 14, 0, Kit.INK, 0, 0)
	wsb.set_meta("kit_kind", "")
	well.add_theme_stylebox_override("panel", wsb)
	well.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	well.mouse_filter = Control.MOUSE_FILTER_IGNORE
	well.position = Vector2(9, 9)
	well.size = r.size - Vector2(18, 24)
	fr.add_child(well)
	if portrait != "":
		var lp := CmdPortrait.new(portrait)
		lp.plate = team
		lp.mood = mood
		lp.size = well.size
		well.add_child(lp)
	else:
		var ic := _icon_rect("crown", well.size.x * 0.6)
		ic.position = (well.size - ic.size) * 0.5
		well.add_child(ic)
	var rim := Panel.new()  # an INK line between the art and the trim
	var rsb := Kit.style(Kit.alpha(Kit.INK, 0.0), 14, 3, Kit.INK, 0, 0)
	rsb.draw_center = false
	rsb.set_meta("kit_kind", "")
	rim.add_theme_stylebox_override("panel", rsb)
	rim.position = well.position
	rim.size = well.size
	rim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	fr.add_child(rim)
	if enemy != "":
		var oc := Kit.chip(box, Vector2.ZERO, "", enemy, "owner", team, {"max_w": r.size.x + 56.0})
		oc.name = "enemy"
		oc.position = Vector2(r.position.x + (r.size.x - oc.size.x) * 0.5, r.end.y - 20.0)


## Simple announcement: title, lines of text, one button (world expansion, chapter cards).
## Height of a wrapped 22 px line block, so long lines (leaders' quotes) push the next ones down.
func _line_h(text: String) -> float:
	var probe := _label(text, 22, TEXT, false)
	var f := probe.get_theme_font("font")
	var sz := f.get_multiline_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, 741.0, 22, -1, TextServer.BREAK_MANDATORY | TextServer.BREAK_WORD_BOUND)
	probe.free()
	return maxf(52.0, sz.y + 22.0)


func show_info(title: String, lines: Array, button: String, on_button: Callable) -> void:
	var text_h := 0.0
	for ln in lines:
		text_h += _line_h(String(ln))
	var h := 230.0 + text_h
	var box := _modal_box(Rect2(60, maxf(120.0, (VH - h) / 2.0 - 80.0), 821, h))
	var t := _label(title, 36, Color(1.0, 0.85, 0.4))
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_at(t, box, Vector2(0, 28), Vector2(821, 48))
	var y := 100.0
	for ln in lines:
		var l := _label(String(ln), 22, TEXT, false)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD
		l.custom_minimum_size = Vector2(741, 0)
		l.position = Vector2(40, y)
		box.add_child(l)
		y += _line_h(String(ln))
	_button(box, Rect2(40, h - 110, 741, 84), button, Color(0.13, 0.4, 0.9), on_button)


## A choice: title, lines, several buttons [[text, color, callable], …] stacked under the text.
func show_choice(title: String, lines: Array, buttons: Array) -> void:
	var text_h := 0.0
	for ln in lines:
		text_h += _line_h(String(ln))
	var h := 150.0 + text_h + 96.0 * buttons.size()
	var box := _modal_box(Rect2(60, maxf(200.0, (VH - h) / 2.0 - 80.0), 821, h))
	var t := _label(title, 34, Color(1.0, 0.85, 0.4))
	_fit(t, 34, 780.0)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_at(t, box, Vector2(0, 28), Vector2(821, 46))
	var y := 96.0
	for ln in lines:
		var l := _label(String(ln), 22, TEXT, false)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD
		l.custom_minimum_size = Vector2(741, 0)
		l.position = Vector2(40, y)
		box.add_child(l)
		y += _line_h(String(ln))
	y += 16.0
	for b in buttons:
		_button(box, Rect2(40, y, 741, 80), String(b[0]), b[1], b[2])
		y += 96.0


## Settings (docs/ui_style.md §6 «Настройки»): a window M with the info plate; changes apply at once and ✕ closes it.
## Well 1: «Звук» with a switch, «Язык» with segments Русский | English (`on_lang` gets "ru" / "en" and re-renders the
## game, then the caller shows this window again). Well 2: the store's subscription screen and «Restore purchases» as
## rows with a chevron (when given). Well 3, the danger zone: «Новая игра» — war S held 1.2 s. The build line at the
## bottom (LEGAL).
func show_settings(sound_on: bool, on_sound: Callable, on_new_game: Callable, on_lang: Callable, on_manage := Callable(), on_restore := Callable()) -> void:
	var store_rows := int(on_manage.is_valid()) + int(on_restore.is_valid())
	var row_h := 96.0
	var w1 := 16.0 + 2.0 * row_h + 12.0 + 16.0
	var w2 := (16.0 + store_rows * row_h + (store_rows - 1) * 12.0 + 16.0) if store_rows > 0 else 0.0
	var w3 := 16.0 + 64.0 + 8.0 + 30.0 + 12.0  # the button, then the hint «hold it» (LEGAL)
	var h := 72.0 + w1 + 16.0 + (w2 + 16.0 if w2 > 0.0 else 0.0) + w3 + 16.0 + 32.0 + 32.0
	var box := _modal_box(_win_rect("M", h), false, tr("settings.title"), "gear", "info", true, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var rw := w - 64.0 - 32.0
	# ---- sound and language
	var well1 := Kit.well(box, Rect2(32, 72, w - 64.0, w1))
	well1.name = "general"
	var sw := Kit.toggle(null, Vector2.ZERO, sound_on)
	var srow := Kit.row(well1, Rect2(16, 16, rw, row_h), {"icon": "sound_on" if sound_on else "sound_off",
		"title": tr("settings.sound"), "right": sw})
	srow.name = "sound"
	sw.cb = func(on: bool):
		on_sound.call()
		(srow.icon_node as TextureRect).texture = Kit.icon_tex("sound_on" if on else "sound_off")
	srow.cb = func():
		sw.set_on(not sw.on)
		sw.cb.call(sw.on)
	var names: Array = []
	for code in L.LANGS:
		names.append(String(L.LANG_NAMES[code]))
	var seg_holder := Control.new()
	seg_holder.size = Vector2(minf(360.0, rw - 260.0), 64)
	seg_holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var seg := Kit.segmented(seg_holder, Rect2(Vector2.ZERO, seg_holder.size), names, L.LANGS.find(L.lang()), func(i: int):
		var code: String = L.LANGS[i]
		if code != L.lang():
			on_lang.call(code))
	seg.name = "lang"
	var lrow := Kit.row(well1, Rect2(16, 16 + row_h + 12.0, rw, row_h), {"icon": "globe", "title": tr("settings.language"),
		"right": seg_holder})
	lrow.name = "language"
	var y := 72.0 + w1 + 16.0
	# ---- the store: the subscription screen, restore purchases
	if store_rows > 0:
		var well2 := Kit.well(box, Rect2(32, y, w - 64.0, w2))
		well2.name = "store"
		var ry := 16.0
		if on_manage.is_valid():
			Kit.row(well2, Rect2(16, ry, rw, row_h), {"icon": "charter", "title": tr("settings.manage_sub"), "right": "chevron",
				"cb": on_manage}).name = "manage"
			ry += row_h + 12.0
		if on_restore.is_valid():
			Kit.row(well2, Rect2(16, ry, rw, row_h), {"icon": "key", "title": tr("patent.restore"), "right": "chevron",
				"cb": on_restore}).name = "restore"
		y += w2 + 16.0
	# ---- the danger zone: a new game, held
	var well3 := Kit.well(box, Rect2(32, y, w - 64.0, w3))
	well3.name = "danger"
	var nb := Kit.button(well3, Rect2((well3.size.x - 400.0) * 0.5, 16, 400, 64), "war", tr("settings.new_game"), {"size": "S",
		"hold": true, "hold_sec": 1.2})
	nb.name = "new_game"
	nb.cb = func():
		close_modal()
		on_new_game.call()
	nb.released_early.connect(func(): Kit.tooltip(nb, tr("settings.new_game"), tr("settings.hold_hint")))
	var hh := Kit.label(tr("settings.hold_hint"), 22, Kit.MUTED_CREAM, false)  # it must be held: said before, not after
	hh.name = "hold_hint"
	hh.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hh.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	hh.position = Vector2(16, 16 + 64 + 8)
	hh.size = Vector2(well3.size.x - 32.0, 30)
	well3.add_child(hh)
	y += w3 + 16.0
	var vl := Kit.label(tr("settings.build") % ProjectSettings.get_setting("application/config/version", "0.3"), 22, Kit.MUTED_CREAM, false)
	vl.name = "build"
	vl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	vl.position = Vector2(32, y)
	vl.size = Vector2(w - 64.0, 32)
	box.add_child(vl)

# ------------------------------------------------------------------ market (05 §13)

const MARKET_RES: Array[String] = ["gold", "food", "metal"]
const MARKET_PCT: Array[int] = [10, 25, 50, 100]


## 2632 -> "2.63" ("2,63" in Russian).
static func _rate_txt(milli: int) -> String:
	var t := "%.2f" % (milli / 1000.0)
	return t.replace(".", ",") if L.lang() == "ru" else t

## Market: «give / get» resource pickers, amount presets, live quote and the daily trader's 3 lots.
## `info`: level, rate (thousandths), res, cap, lots [{key, give, get, give_amt, get_amt, rate, bought, ok}],
## refresh_left, sel {give, get, pct}. `quote_fn(give, get, amount) -> {give, get, cap_hit}`;
## `on_exchange(give, get, amount)`, `on_lot(i)` — the caller re-opens the modal with fresh info.
func show_market(info: Dictionary, quote_fn: Callable, on_exchange: Callable, on_lot: Callable) -> void:
	var box := _modal_box(Rect2(40, 330, 861, 1180))
	var sel: Dictionary = info["sel"]
	var res: Dictionary = info["res"]
	var cap: Dictionary = info["cap"]
	var rerender := func(): show_market(info, quote_fn, on_exchange, on_lot)
	_at(_label(tr("market.title") % int(info["level"]), 34), box, Vector2(36, 26))
	var rl := _label(tr("market.rate") % _rate_txt(int(info["rate"])), 22, Color(1.0, 0.85, 0.4))
	rl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_at(rl, box, Vector2(430, 34), Vector2(395, 34))
	for row in 2:
		var y := 96.0 + row * 170.0
		var side := "give" if row == 0 else "get"
		_at(_label(tr("market." + side), 22, MUTED, false), box, Vector2(36, y))
		for i in MARKET_RES.size():
			var r: String = MARKET_RES[i]
			var on: bool = String(sel[side]) == r
			var other := "get" if side == "give" else "give"
			var b := _panel(box, Rect2(36 + i * 268, y + 36, 254, 116), _style(Color(0.16, 0.42, 0.95) if on else Color(0.14, 0.18, 0.27), 14, Color(1, 1, 1, 0.6 if on else 0.25), 2))
			var ic := TextureRect.new()
			ic.texture = _icon(r)
			ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			ic.size = Vector2(44, 44)
			ic.position = Vector2(14, 14)
			ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
			b.add_child(ic)
			var nl := _label(tr("res.name." + r), 22)
			nl.mouse_filter = Control.MOUSE_FILTER_IGNORE
			_at(nl, b, Vector2(66, 20))
			var amount: int = int(res.get(r, 0)) if side == "give" else maxi(0, int(cap.get(r, 0)) - int(res.get(r, 0)))
			var sub := _label(tr("market.stock" if side == "give" else "market.free") % fmt_num(amount), 17, Color(0.85, 0.9, 1.0) if on else MUTED, false)
			sub.mouse_filter = Control.MOUSE_FILTER_IGNORE
			_at(sub, b, Vector2(14, 70))
			b.gui_input.connect(func(e):
				if _is_tap(e) and String(sel[side]) != r:
					if String(sel[other]) == r:
						sel[other] = sel[side]
					sel[side] = r
					rerender.call())
	var give: String = sel["give"]
	var get_r: String = sel["get"]
	for i in MARKET_PCT.size():
		var pct: int = MARKET_PCT[i]
		var on2: bool = int(sel["pct"]) == pct
		_button(box, Rect2(36 + i * 200, 448, 188, 70), "%d%%" % pct if pct < 100 else tr("market.max"), Color(0.16, 0.42, 0.95) if on2 else Color(0.14, 0.18, 0.27), func():
			sel["pct"] = pct
			rerender.call())
	var want: int = int(res.get(give, 0)) * int(sel["pct"]) / 100
	var q: Dictionary = quote_fn.call(give, get_r, want)
	var qg: int = int(q.get("give", 0))
	var qr: int = int(q.get("get", 0))
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 12)
	line.alignment = BoxContainer.ALIGNMENT_CENTER
	line.position = Vector2(0, 540)
	line.size = Vector2(861, 56)
	for part in [[give, "−" + fmt_num(qg)], ["", "→"], [get_r, "+" + fmt_num(qr)]]:
		if String(part[0]) != "":
			var ic2 := TextureRect.new()
			ic2.texture = _icon(String(part[0]))
			ic2.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			ic2.custom_minimum_size = Vector2(44, 44)
			line.add_child(ic2)
		line.add_child(_label(String(part[1]), 34))
	box.add_child(line)
	if bool(q.get("cap_hit", false)):
		var ch := _label(tr("market.fits") % fmt_num(qr), 18, Color(1.0, 0.7, 0.35), false)
		ch.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_at(ch, box, Vector2(0, 600), Vector2(861, 26))
	var can := qr > 0
	var ex := _button(box, Rect2(36, 636, 789, 92), tr("market.exchange"), Color(0.2, 0.6, 0.3) if can else Color(0.3, 0.33, 0.4), func():
		if can:
			on_exchange.call(give, get_r, qg))
	ex.modulate.a = 1.0 if can else 0.6
	var tl := _label(tr("market.trader") % fmt_time(int(info["refresh_left"])), 22, Color(1.0, 0.85, 0.4))
	tl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_at(tl, box, Vector2(0, 752), Vector2(861, 32))
	var lots: Array = info["lots"]
	for i in lots.size():
		var lot: Dictionary = lots[i]
		var y2 := 796.0 + i * 100.0
		var row_p := _panel(box, Rect2(36, y2, 789, 88), _style(Color(0.12, 0.16, 0.24), 12, Color(0.95, 0.75, 0.3, 0.6), 2), Control.MOUSE_FILTER_IGNORE)
		var nm := _label(tr(String(lot["key"])), 20, Color(1.0, 0.85, 0.4))
		_at(nm, row_p, Vector2(16, 6))
		var lr := HBoxContainer.new()
		lr.add_theme_constant_override("separation", 8)
		lr.position = Vector2(16, 38)
		for part2 in [[String(lot["give"]), fmt_num(int(lot["give_amt"]))], ["", "→"], [String(lot["get"]), fmt_num(int(lot["get_amt"]))]]:
			if String(part2[0]) != "":
				var ic3 := TextureRect.new()
				ic3.texture = _icon(String(part2[0]))
				ic3.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
				ic3.custom_minimum_size = Vector2(32, 32)
				lr.add_child(ic3)
			lr.add_child(_label(String(part2[1]), 24))
		row_p.add_child(lr)
		var rate_l := _label(_rate_txt(int(lot["rate"])) + " : 1", 17, MUTED, false)
		_at(rate_l, row_p, Vector2(380, 44))
		var bought: bool = lot["bought"]
		var ok: bool = lot.get("ok", false)
		var idx := i
		var bb := _button(row_p, Rect2(560, 12, 214, 64), tr("market.bought") if bought else tr("market.buy"), Color(0.3, 0.33, 0.4) if bought or not ok else Color(0.85, 0.55, 0.1), func():
			if not bought:
				on_lot.call(idx))
		bb.mouse_filter = Control.MOUSE_FILTER_STOP
	_button(box, Rect2(36, 1100, 789, 64), tr("ui.close"), Color(0.13, 0.4, 0.9), close_modal)


# ------------------------------------------------------------------ buildings tab (canon §7)

const RES_ICON := {"gold": "coin", "food": "food", "metal": "metal", "oil": "barrel", "raivite": "raivite"}
var _bpanel: Control
var _bscroll: ScrollContainer
var _brow: HBoxContainer


func _icon(res: String) -> Texture2D:
	return Kit.icon_tex(String(RES_ICON.get(res, "coin")))


## 8 620 / 12,4K / 1,2M (docs/ui_style.md §3.7).
static func fmt_num(n: int) -> String:
	return Kit.fmt_num(n)


## 42 с / 1:06 / 2ч 57м / 3д 4ч
static func fmt_time(sec: int) -> String:
	return Kit.fmt_time(sec)


## items: [{id, name, level, max, busy, left, speed, cost: {res: n}, seconds, reason}]
var _bkey := ""
var _bfam := ""  # the tab whose cards the row shows (a switch fades the new cards in)
var _bfade: TextureRect
var _finger_down := false


## The card row inside the HUD's slate tray (§5): a horizontal scroll over the tray's face (16, 1468, 620, 186);
## the cards (180×172, 12 apart) start at (20, 1476), so 3 whole cards and 40 px of the 4th show, and a 40 px fade
## into the slate on the right says that more follow. The badges and chips that stand out of the cards' corners
## stay inside the scroll's clip.
func _ensure_panel() -> void:
	if _bpanel != null:
		return
	_bpanel = Control.new()
	_bpanel.name = "cards"
	_bpanel.size = Vector2(VW, VH)
	_bpanel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bottom.add_child(_bpanel)
	_bottom.move_child(_bpanel, 0)
	_bscroll = ScrollContainer.new()
	_bscroll.position = Vector2(16, 1468)
	_bscroll.size = Vector2(620, 186)
	_bscroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_bscroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_NEVER
	_bpanel.add_child(_bscroll)
	var pad := MarginContainer.new()
	pad.mouse_filter = Control.MOUSE_FILTER_PASS
	for m in [["margin_left", 4], ["margin_top", 8], ["margin_right", 4], ["margin_bottom", 0]]:
		pad.add_theme_constant_override(m[0], m[1])
	_bscroll.add_child(pad)
	_brow = HBoxContainer.new()
	_brow.mouse_filter = Control.MOUSE_FILTER_PASS
	_brow.add_theme_constant_override("separation", 12)
	pad.add_child(_brow)
	_bfade = TextureRect.new()
	_bfade.name = "fade"
	_bfade.texture = Kit.hgradient(Kit.alpha(Kit.SLATE, 0.0), Kit.SLATE)
	_bfade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_bfade.stretch_mode = TextureRect.STRETCH_SCALE
	_bfade.position = Vector2(596, 1468)
	_bfade.size = Vector2(40, 180)
	_bfade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bpanel.add_child(_bfade)
	var hb := _bscroll.get_h_scroll_bar()
	hb.value_changed.connect(_update_fade)
	hb.changed.connect(_update_fade.bind(0.0))


## The right-edge fade shows only while at least its own width of cards is hidden past the right edge: a row a few
## px too wide (two 304 px diplomacy cards) would otherwise dim the last card's buttons for nothing to scroll to.
func _update_fade(_v := 0.0) -> void:
	if _bfade == null:
		return
	var hb := _bscroll.get_h_scroll_bar()
	_bfade.visible = hb.max_value - hb.page - hb.value >= _bfade.size.x


## Rebuilds the card row only when its content changed, and never under a finger (a rebuild between
## press and release would swallow the tap). Another tab's cards start from the left and fade in (TAB, 120 ms).
func _fill_panel(kind: String, items: Array, builder: Callable) -> void:
	_ensure_panel()
	_bpanel.visible = true
	var key := kind + JSON.stringify(items)
	if key == _bkey:
		return
	if _finger_down and _bkey.begins_with(kind):
		return
	_bkey = key
	# the Development tab fills the row through show_buildings too: its items carry a research line
	var fam := kind + ("r" if items.any(func(x): return x is Dictionary and (x as Dictionary).has("line")) else "")
	var switched := fam != _bfam
	_bfam = fam
	var keep := 0 if switched else _bscroll.scroll_horizontal
	for c in _brow.get_children():
		_brow.remove_child(c)
		c.queue_free()
	var ns := 26  # the names of a row share one size: the smallest any card needed
	for it in items:
		var card: Control = builder.call(it)
		_brow.add_child(card)
		if card is Kit.KitCard:
			ns = mini(ns, (card as Kit.KitCard).name_label.get_theme_font_size("font_size"))
	for card in _brow.get_children():
		if card is Kit.KitCard:
			(card as Kit.KitCard).name_label.add_theme_font_size_override("font_size", ns)
	_bscroll.set_deferred("scroll_horizontal", keep)
	if switched:
		Kit.fade_in(_brow)
	_update_fade.call_deferred()


func show_buildings(items: Array) -> void:
	_fill_panel("b", items, _building_card)


## Army tab (§6 Армия): a card per army, «Новая армия», then «Рука» and «Командиры» (canon §8.1). The armies are
## numbered in order for their badges.
func show_armies(items: Array) -> void:
	var shown: Array = []
	var n := 0
	for it in items:
		var d: Dictionary = it
		if int(d.get("id", -1)) >= 0:
			n += 1
			d = d.duplicate()
			d["num"] = n
		shown.append(d)
	_fill_panel("a", shown, _army_card)


## An army (Kit.card): its era's troops as the art, its number on the hex badge, the commander's face (or a «+» to
## assign one) on the chip, the readiness bar under the name; at the bottom its strength with a check when it is
## full, or — while it refills — the refill-for-an-ad button. Squads, readiness and upkeep are in the tooltip.
func _army_card(it: Dictionary) -> Control:
	if it.has("hand"):
		return _hand_card(it)
	if it.has("commanders"):
		return _commanders_card(it)
	var id: int = it["id"]
	if id < 0:
		return _new_army_card(it)
	var pic := "res://assets/ui/cards/unit_dl%d.png" % clampi(int(it.get("dl", 1)), 1, 8)
	var tex: Texture2D = load(pic) if ResourceLoader.exists(pic) else Kit.icon_tex("helmet")
	# the readiness: the exact share when the item carries one («ready»), else from «str» / «max», which come rounded
	# to thousands — so a refilling army never reads 100 %
	var ready := clampf(float(it["ready"]) if it.has("ready") else float(it["str"]) / maxf(1.0, float(it["max"])), 0.0, 1.0)
	var pct := roundi(ready * 100.0)
	if it["refilling"]:
		pct = mini(pct, 99)
		ready = minf(ready, 0.99)
	# the tooltip keeps to 4 lines (§4.11): strength, squads, upkeep, the refill; the readiness is the bar's
	var tip := PackedStringArray([tr("army.tip.str") % [int(it["str"]), int(it["max"])], tr("army.tip.squads") % int(it["slots"])])
	if int(it.get("upkeep", 0)) > 0:
		tip.append(tr("army.tip.upkeep") % int(it["upkeep"]))
	var opts := {"badge": str(int(it.get("num", 1))), "details": "\n".join(tip),
		"art_bar": {"frac": ready, "role": "go" if ready >= 0.5 else ("gold" if ready >= 0.25 else "war")}}
	if not ResourceLoader.exists(pic):
		opts["art_side"] = 72.0
	var cid: String = it.get("cmd", "")
	if cid != "" or bool(it.get("cmd_free", false)):
		# the commander frame (04 §15.6): a portrait, or «+» while the army has none
		opts["chip"] = {"node": CmdPortrait.new(cid, String(it.get("cmd_rarity", "common")))} if cid != "" else {"plus": true}
		opts["chip_cb"] = func(): army_action.emit(id, "cmd")
	if it["refilling"]:
		# [ad] +29%: what the video gives (the word «Пополнить» does not fit an XS button beside the ad icon); the
		# time to a full army instead once the game passes it
		var cap := "+%d%%" % (100 - pct) if not it.has("refill_left") else fmt_time(int(it["refill_left"]))
		opts["cta"] = {"role": "go", "caption": cap, "icon": "ad", "cb": func(): army_action.emit(id, "refill")}
		tip.append(tr("army.tip.refill"))
		opts["details"] = "\n".join(tip)
	else:
		opts["stat"] = {"icon": "swords", "text": fmt_num(int(it["str"])), "check": true}
	return Kit.card(tex, String(it["name"]), opts)


## «Новая армия»: the helmet on the sky; closed — dark with the lock and a lock «УР3» (its tap says when it opens);
## open — go «Собрать» with the food price; recruiting — the hourglass and the time left.
func _new_army_card(it: Dictionary) -> Control:
	var opts := {"art_side": 76.0, "art_y": 40.0, "details": tr("army.tip.time") % fmt_time(int(it.get("seconds", 0)))}
	if it.has("left"):
		opts["details"] = tr("army.recruiting")
		opts["cta"] = {"role": "info", "caption": fmt_time(int(it["left"])), "icon": "hourglass"}
	elif it["locked"]:
		var need := int(it.get("need_dl", 3))
		opts["locked"] = true
		opts["lock_caption"] = tr("dl.short") % need
		opts["reason"] = tr("army.locked_dl") % need
		opts["details"] = opts["reason"]
	else:
		# «food_short» (not enough food, when the item says so) paints the price NEG (§4.1 «Не хватает»)
		opts["cta"] = {"role": "go", "caption": tr("army.train"), "price": [["food", fmt_num(int(it["food"])), bool(it.get("food_short", false))]],
			"cb": func(): army_action.emit(-1, "train")}
	return Kit.card(Kit.icon_tex("helmet"), String(it["name"]), opts)


## The Army tab's «Рука» card: a fan of three of its cards, the hand's size on the badge, «Колода» opens the picker
## (03 §5.2: «Атака» + 4 slots, 5 from DL6).
func _hand_card(it: Dictionary) -> Control:
	var hand: Array = it["hand"]
	var shown: Array = hand.slice(1, 4) if hand.size() >= 4 else hand.slice(0, 3)
	var pics: Array = []
	var names := PackedStringArray()
	for c in hand:
		if CARD_NAME_KEYS.has(c):
			names.append(_card_name(String(c)))
	for c in shown:
		var p := "res://assets/ui/cards/%s.png" % c
		var tr_ := TextureRect.new()
		tr_.texture = load(p) if ResourceLoader.exists(p) else Kit.icon_tex("cards")
		tr_.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr_.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		tr_.mouse_filter = Control.MOUSE_FILTER_IGNORE
		pics.append(tr_)
	return Kit.card(null, String(it["name"]), {"art_node": _fan(pics), "badge": str(hand.size()),
		"details": tr("hand.tip") % ", ".join(names),
		"cta": {"role": "info", "caption": tr("hand.deck"), "cb": func(): army_action.emit(-2, "hand")}})


## The Army tab's «Командиры» card: a fan of three faces, «7/12», a green dot when a level can be bought. Only as
## many faces are lit as the player owns commanders, the rest are silhouettes. «faces» ([[id, rarity]], the owned
## ones), when the item carries it, picks the faces; else the order most players meet them in: Bram (the tutorial),
## Lira (calendar day 1), Rai (day 4).
func _commanders_card(it: Dictionary) -> Control:
	var n: Array = it["commanders"]
	var faces: Array = (it.get("faces", []) as Array).slice(0, 3)
	for f in [["cmd_bram", "common"], ["cmd_lira", "common"], ["cmd_rai", "legendary"]]:
		if faces.size() < 3 and not faces.any(func(x): return String(x[0]) == f[0]):
			faces.append(f)
	var pics: Array = [null, null, null]
	var slot := [1, 0, 2]  # the middle face is drawn on top (_fan): it is lit first, then the left, then the right
	for r in 3:
		pics[slot[r]] = CmdPortrait.new(String(faces[r][0]), String(faces[r][1]), r >= int(n[0]))
	var up := bool(it.get("dot", false))
	var opts := {"art_node": _fan(pics, 12.0), "tag": "%d/%d" % [int(n[0]), int(n[1])],
		"details": tr("cmdr.collection") % [int(n[0]), int(n[1])] + ("\n" + tr("cmdr.tip_up") if up else ""),
		"cta": {"role": "info", "caption": tr("cmdr.open"), "cb": func(): army_action.emit(-3, "commanders")}}
	if up:
		opts["dot"] = "go"
	return Kit.card(null, String(it["name"]), opts)


## Three small framed pictures (the hand's cards, the collection's faces) fanned out at −8 / 0 / +8° in a card's
## art window (172×104); the middle one on top. `dy` lowers the fan (below a counter pill in the corner).
func _fan(pics: Array, dy := 0.0) -> Control:
	var fan := Control.new()
	fan.mouse_filter = Control.MOUSE_FILTER_IGNORE
	fan.size = Vector2(172, 104)
	var n := pics.size()
	var order: Array = [0, 2, 1] if n == 3 else range(n)
	for i in order:
		var k := float(i) - (n - 1) * 0.5
		var fr := Panel.new()  # an INK frame with a hard shadow
		fr.add_theme_stylebox_override("panel", Kit.style(Kit.INK, 8, 0, Kit.INK, 3, 0))
		fr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		fr.size = Vector2(64, 76)
		fr.position = Vector2(86.0 + k * 42.0 - 32.0, 8.0 + dy + absf(k) * 6.0)
		fr.pivot_offset = Vector2(32, 76)
		fr.rotation_degrees = k * 8.0
		# the picture 3 px inside the frame (not clipped round: the art window already clips its children, and
		# Godot does not nest clip_children)
		var p: Control = pics[i]
		p.position = Vector2(3, 3)
		p.size = Vector2(58, 70)
		fr.add_child(p)
		fan.add_child(fr)
	return fan


## The realm's profile (10 §4.23, docs/ui_style.md §6 «Профиль»): a window L with the info plate «Держава». The header:
## the flag 120 and the ruler's portrait 120 (its level hex on the corner), a round info pencil on the flag (the flag
## constructor) and one after the realm's name (H1 36; the name editor), the chapter under it. Six stat tiles 3 × 2 — the
## tappable ones («Командиры», «Летопись») with a chevron and their dot; the 3 latest achievements as rows with their
## medal. Unreleased features (the Arena league, the timelapse, comparing realms, friends) are not shown, and Settings
## live on the HUD's gear.
## info: {name, dl, hexes, chapter, map_pct, commanders [n, of], chronicle [n, of], recent [{name, chapter, code?}],
##   flag, book_badge, cmd_dot, wins}; cb: {flag, name, commanders, chronicle, …}
const PROFILE_TILE_H := 150.0


func show_profile(info: Dictionary, cb: Dictionary) -> void:
	var recent: Array = info.get("recent", [])
	var rec_n := maxi(1, recent.size())
	var rec_h := (16.0 + rec_n * 96.0 + (rec_n - 1) * 12.0 + 16.0) if not recent.is_empty() else 56.0
	var stats_h := 16.0 + 2.0 * PROFILE_TILE_H + 12.0 + 16.0
	var h := 72.0 + 160.0 + 24.0 + stats_h + 24.0 + 48.0 + 12.0 + rec_h + 32.0
	var box := _modal_box(_win_rect("L", h), false, tr("profile.title"), "crown", "info", true, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	# ---- the header: flag, ruler, name
	var crest := FlagView.new(info.get("flag", {}))
	crest.name = "flag"
	crest.position = Vector2(32, 72)
	crest.size = Vector2(120, 154)
	crest.mouse_filter = Control.MOUSE_FILTER_STOP
	box.add_child(crest)
	var rf := Panel.new()
	rf.name = "ruler"
	var rsb := Kit.style(Kit.face_of(_trim), 20, 4, Kit.INK, 6, 6)
	rsb.set_meta("kit_kind", "")
	rf.add_theme_stylebox_override("panel", rsb)
	rf.mouse_filter = Control.MOUSE_FILTER_IGNORE
	rf.position = Vector2(176, 80)
	rf.size = Vector2(120, 130)
	box.add_child(rf)
	rf.add_child(Kit.KitDecor.new())
	var sky := Panel.new()
	var ssb := Kit.style(Kit.SKY_TOP, 14, 0, Kit.INK, 0, 0)
	ssb.set_meta("kit_kind", "")
	sky.add_theme_stylebox_override("panel", ssb)
	sky.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	sky.mouse_filter = Control.MOUSE_FILTER_IGNORE
	sky.position = Vector2(8, 8)
	sky.size = Vector2(104, 104)
	rf.add_child(sky)
	var era := CmdPortrait.era
	var rp := "res://assets/ui/portraits/ruler%s.png" % ("" if era <= 1 else "_e%d" % era)
	if not ResourceLoader.exists(rp):
		rp = "res://assets/ui/portraits/ruler.png"
	if ResourceLoader.exists(rp):
		var face := TextureRect.new()
		face.texture = load(rp)
		face.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		face.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		face.mouse_filter = Control.MOUSE_FILTER_IGNORE
		face.size = sky.size
		sky.add_child(face)
	else:
		var cr := _icon_rect("crown", 72)
		cr.position = Vector2(16, 16)
		sky.add_child(cr)
	var lv := Kit.hex_badge(box, Vector2(176 + 10, 80 + 130 - 6), 24, "info", str(int(info.get("dl", 1))))
	lv.name = "dl"
	var nx := 176.0 + 120.0 + 28.0
	var nw := w - 32.0 - nx - (64.0 if cb.has("name") else 0.0)
	var nm := String(info["name"])
	var ns := Kit.fit_size(nm, 36, nw, "d900", 26, false)
	var nl := Kit.label(nm, ns, Kit.INK_TEXT, true)
	nl.name = "realm_name"
	nl.add_theme_font_size_override("font_size", ns)
	nl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	nl.clip_text = true
	nl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	var tw := minf(Kit.text_w(nm, ns, "d900", false) + 4.0, nw)
	nl.position = Vector2(nx, 92)
	nl.size = Vector2(tw, 48)
	box.add_child(nl)
	if cb.has("name"):
		nl.mouse_filter = Control.MOUSE_FILTER_STOP
		nl.gui_input.connect(func(e): if _is_tap(e): (cb["name"] as Callable).call())
		var np := _pencil(box, Vector2(nx + tw + 14.0 + 26.0, 116), cb["name"])
		np.name = "edit_name"
	if cb.has("flag"):
		crest.gui_input.connect(func(e): if _is_tap(e): (cb["flag"] as Callable).call())
		var fp := _pencil(box, Vector2(32 + 120 - 10, 72 + 154 - 22), cb["flag"])
		fp.name = "edit_flag"
	var chl := Kit.label(String(info.get("chapter", "")), 26, Kit.MUTED_CREAM, false)
	chl.name = "chapter"
	chl.clip_text = true
	chl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	chl.position = Vector2(nx, 148)
	chl.size = Vector2(w - 32.0 - nx, 36)
	box.add_child(chl)
	# ---- the stats
	var sw := Kit.well(box, Rect2(32, 72.0 + 160.0 + 24.0, w - 64.0, stats_h))
	sw.name = "stats"
	var cm: Array = info["commanders"]
	var cr2: Array = info["chronicle"]
	var tiles := [
		["hex_tile", str(int(info["hexes"])), tr("profile.hexes"), "", false],
		["globe", "%d%%" % int(info["map_pct"]), tr("profile.map"), "", false],
		["crown", str(int(info.get("dl", 1))), tr("profile.dl_short"), "", false],
		["frame", "%d/%d" % [int(cm[0]), int(cm[1])], tr("profile.commanders"), "commanders", bool(info.get("cmd_dot", false))],
		["book", "%d/%d" % [int(cr2[0]), int(cr2[1])], tr("profile.chronicle"), "chronicle", int(info.get("book_badge", 0)) > 0],
		["swords", str(int(info["wins"])), tr("profile.wins"), "", false],
	]
	var tw3 := (sw.size.x - 32.0 - 2.0 * 12.0) / 3.0
	for i in tiles.size():
		var tdef: Array = tiles[i]
		var key := String(tdef[3])
		var r := Rect2(16.0 + (i % 3) * (tw3 + 12.0), 16.0 + (i / 3) * (PROFILE_TILE_H + 12.0), tw3, PROFILE_TILE_H)
		var o := {"icon": String(tdef[0]), "icon_side": 52.0, "value": String(tdef[1]), "caption": String(tdef[2])}
		if key != "" and cb.has(key):
			o["cb"] = cb[key]
		var t := Kit.tile(sw, r, o)
		t.name = "stat_%d" % i
		if key != "" and cb.has(key):
			var chev := Kit.chrome(t, "chevron_right", Rect2(tw3 - 46.0, (PROFILE_TILE_H - 5.0) * 0.5 - 18.0, 36, 36), Kit.WHITE)
			chev.name = "chevron"
			if bool(tdef[4]):
				Kit.dot(t, -1, "go").name = "dot"
	# ---- the latest achievements
	var ry := 72.0 + 160.0 + 24.0 + stats_h + 24.0
	Kit.section(box, Vector2(32, ry), w - 64.0, tr("profile.recent"), "medal")
	ry += 60.0
	if recent.is_empty():
		var none := Kit.label(tr("profile.none"), 28, Kit.MUTED_CREAM, false)
		none.name = "none"
		none.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		none.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		none.position = Vector2(32, ry)
		none.size = Vector2(w - 64.0, 44)
		box.add_child(none)
		return
	var rw_ := Kit.well(box, Rect2(32, ry, w - 64.0, rec_h))
	rw_.name = "recent"
	var y := 16.0
	for a in recent:
		var code := String(a.get("code", ""))
		var row := Kit.row(rw_, Rect2(16, y, rw_.size.x - 32.0, 96), {"icon": _chr_medal(code) if code != "" else "medal",
			"title": String(a["name"]), "sub": String(a.get("chapter", ""))})
		row.name = "medal"
		y += 96.0 + 12.0


## A round info button Ø52 with the pencil (the profile's «edit»), centred at `c`; a 96 px touch zone.
func _pencil(parent: Control, c: Vector2, cb: Callable) -> Kit.KitButton:
	return Kit.button(parent, Rect2(c - Vector2(26, 26), Vector2(52, 52)), "info", "", {"icon": "pencil", "round": true,
		"size": "XS", "icon_scale": 0.66, "hit_pad": 22.0, "cb": cb})


var _flag_tab := "div"


## The commander portraits follow the player's DL era (04 §15.4).
func set_portrait_era(dl: int) -> void:
	CmdPortrait.era = CmdPortrait.era_of(dl)
	_trim = "steel" if dl >= 5 else "brass"  # the leader frames switch with the era too (§3.2)


## The flag constructor (10 §4.23, docs/ui_style.md §6 «Флаг, имя, мастер флага»): a paper window L with the info plate.
## The preview on top, segments «Деление | Цвета | Эмблема | Рамка», the options of the tab as tiles in a well (a flag
## 120, a colour swatch, an emblem on the field) — the chosen one with a go outline and check, a closed premium one
## with a lock (a tap says so). Each tap calls on_change with the new flag (the caller shows the editor again). The
## footer: «Случайно» (info, the die) → on_random, «Готово» (go) → on_done; ✕ leaves without keeping the draft.
const FLAG_TILE := Vector2(120, 150)


func show_flag_editor(flag: Dictionary, owned: Dictionary, on_change: Callable, on_random: Callable, on_done: Callable) -> void:
	var area_h := 16.0 + 5.0 * 120.0 + 4.0 * 12.0 + 16.0  # the tallest tab: 27 emblems, 6 in a row
	var h := 72.0 + 196.0 + 20.0 + 80.0 + 20.0 + area_h + 32.0 + 112.0 + 32.0
	var box := _modal_box(_win_rect("L", h), false, tr("flag.title"), "", "info", true, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var prev := FlagView.new(flag)
	prev.name = "preview"
	prev.position = Vector2((w - 152.0) * 0.5, 72)
	prev.size = Vector2(152, 196)
	box.add_child(prev)
	var keys := ["div", "colors", "em", "frame"]
	var names := [tr("flag.tab_div"), tr("flag.tab_colors"), tr("flag.tab_em"), tr("flag.tab_frame")]
	var seg := Kit.segmented(box, Rect2(32, 72.0 + 196.0 + 20.0, w - 64.0, 80), names, maxi(0, keys.find(_flag_tab)), func(i: int):
		if keys[i] != _flag_tab:
			_flag_tab = keys[i]
			show_flag_editor(flag, owned, on_change, on_random, on_done))
	seg.name = "tabs"
	var area := Kit.well(box, Rect2(32, 72.0 + 196.0 + 20.0 + 80.0 + 20.0, w - 64.0, area_h))
	area.name = "options"
	var aw := area.size.x - 32.0
	var set_key := func(k: String, v: Variant) -> void:
		var f := flag.duplicate()
		f[k] = v
		on_change.call(f)
	var locked_tip := func(node: Control) -> void: Kit.tooltip(node, tr("flag.locked"))
	match _flag_tab:
		"div":
			var gx := (aw - 6.0 * FLAG_TILE.x) / 5.0
			for i in FlagView.DIVISIONS.size():
				var d: String = FlagView.DIVISIONS[i]
				var f := flag.duplicate()
				f["div"] = d
				var r := Rect2(16.0 + (i % 6) * (FLAG_TILE.x + gx), 16.0 + (i / 6) * (FLAG_TILE.y + 16.0), FLAG_TILE.x, FLAG_TILE.y)
				_flag_tile(area, r, f, d == String(flag["div"]), false, func(): set_key.call("div", d))
		"colors":
			var groups := [["c1", tr("flag.field1"), FlagView.FIELD], ["c2", tr("flag.field2"), FlagView.FIELD], ["ec", tr("flag.emblem_c"), FlagView.emblem_colors()]]
			var y := 12.0
			var side := 72.0
			var per := 9
			var gx := (aw - per * side) / (per - 1)
			for g in groups:
				var key: String = g[0]
				Kit.section(area, Vector2(16, y), aw, String(g[1]))
				y += 52.0
				var cols: Array = g[2]
				for i in cols.size():
					var r := Rect2(16.0 + (i % per) * (side + gx), y + (i / per) * (side + 12.0), side, side)
					var idx := i
					var sw := Kit.tile(area, r, {"face": cols[i], "selected": int(flag[key]) == i, "cb": func(): set_key.call(key, idx)})
					sw.name = "%s_%d" % [key, i]
				y += ceilf(cols.size() / float(per)) * (side + 12.0) + 8.0
		"em":
			var all: Array = FlagView.EMBLEMS + FlagView.PREMIUM.keys()
			var ecs := FlagView.emblem_colors()
			var ec: Color = ecs[clampi(int(flag["ec"]), 0, ecs.size() - 1)]
			var bg := FlagView.field_color(int(flag["c1"]))
			var side := 120.0
			var gx := (aw - 6.0 * side) / 5.0
			for i in all.size():
				var em: String = all[i]
				var locked := FlagView.PREMIUM.has(em) and not owned.has(em)
				var r := Rect2(16.0 + (i % 6) * (side + gx), 16.0 + (i / 6) * (side + 12.0), side, side)
				var t := Kit.tile(area, r, {"face": bg, "selected": em == String(flag["em"])})
				t.name = "em_%s" % em
				var art := Control.new()
				art.size = Vector2(side, side - 5.0)
				art.mouse_filter = Control.MOUSE_FILTER_IGNORE
				var draw_em := String(FlagView.PREMIUM.get(em, em))
				art.draw.connect(func(): FlagView.draw_emblem(art, draw_em, art.size / 2, 36.0, ec))
				if locked:
					art.modulate = Kit.LOCK_MOD
				t.add_child(art)
				t.move_child(art, 1)
				if locked:
					var lk := _icon_rect("lock", 40)
					lk.position = Vector2(side - 46.0, side - 50.0)
					t.add_child(lk)
					t.cb = func(): locked_tip.call(t)
				else:
					t.cb = func(): set_key.call("em", em)
		"frame":
			var ids: Array = FlagView.FRAMES.keys()
			var gx := (aw - 6.0 * FLAG_TILE.x) / 5.0
			for i in ids.size():
				var fid: String = ids[i]
				var locked := fid != "" and not owned.has(fid)
				var f := flag.duplicate()
				f["frame"] = fid
				var r := Rect2(16.0 + (i % 6) * (FLAG_TILE.x + gx), 16.0 + (i / 6) * (FLAG_TILE.y + 16.0), FLAG_TILE.x, FLAG_TILE.y)
				var holder := [null]
				holder[0] = _flag_tile(area, r, f, fid == String(flag["frame"]), locked, func():
					if locked:
						locked_tip.call(holder[0])
					else:
						set_key.call("frame", fid))
	var fy := box.size.y - 32.0 - 112.0
	var rw_ := (w - 64.0 - 16.0) * 0.4
	Kit.button(box, Rect2(32, fy, rw_, 112), "info", tr("flag.random"), {"size": "L", "icon": "dice", "cb": on_random}).name = "random"
	Kit.button(box, Rect2(32.0 + rw_ + 16.0, fy, w - 64.0 - rw_ - 16.0, 112), "go", tr("flag.done"), {"size": "L", "cb": on_done}).name = "done"


## «Название державы» (canon §14.3, §6 «Флаг, имя»): a paper window M with the info plate; the name field is a well
## (INK 3, R 20, Nunito 800 30 — the system keyboard on a phone); six ideas as option tiles (the one in the field has a go
## outline and check; a tap puts it in the field). The footer: «Ещё идеи» (info, the die) → on_more, «Готово» (go) →
## on_done(text). An empty field keeps «Ваша держава».
func show_name_editor(current: String, ideas: Array, max_len: int, on_done: Callable, on_more: Callable) -> void:
	var rows := ceili(ideas.size() / 2.0)
	var ideas_h := 16.0 + rows * 72.0 + (rows - 1) * 12.0 + 16.0
	var h := 72.0 + 88.0 + 24.0 + 60.0 + ideas_h + 32.0 + 112.0 + 32.0
	var box := _modal_box(_win_rect("M", h), false, tr("realm.title"), "pencil", "info", false, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var field := LineEdit.new()
	field.name = "field"
	field.text = current
	field.placeholder_text = tr("state.player")
	field.max_length = max_len
	field.position = Vector2(32, 72)
	field.size = Vector2(w - 64.0, 88)
	field.alignment = HORIZONTAL_ALIGNMENT_CENTER
	field.add_theme_font_override("font", Kit.font("b800"))
	field.add_theme_font_size_override("font_size", 30)
	field.add_theme_color_override("font_color", Kit.INK_TEXT)
	field.add_theme_color_override("font_placeholder_color", Kit.MUTED_CREAM)
	field.add_theme_color_override("caret_color", Kit.INK_TEXT)
	field.add_theme_color_override("selection_color", Kit.alpha(Kit.face_of("info"), 0.35))
	for st in ["normal", "focus", "read_only"]:
		var sb := Kit.style(Kit.CREAM_WELL, 20, 3, Kit.face_of("info") if st == "focus" else Kit.INK, 0, 0)
		sb.set_meta("kit_kind", "")
		sb.content_margin_left = 20
		sb.content_margin_right = 20
		field.add_theme_stylebox_override(st, sb)
	box.add_child(field)
	Kit.section(box, Vector2(32, 72.0 + 88.0 + 24.0), w - 64.0, tr("realm.ideas"), "dice")
	var well := Kit.well(box, Rect2(32, 72.0 + 88.0 + 24.0 + 60.0, w - 64.0, ideas_h))
	well.name = "ideas"
	var draw_ideas := func(self_ref: Callable) -> void:
		for ch in well.get_children():
			ch.queue_free()
		var iw := (well.size.x - 32.0 - 12.0) / 2.0
		for i in ideas.size():
			var idea := String(ideas[i])
			var r := Rect2(16.0 + (i % 2) * (iw + 12.0), 16.0 + (i / 2) * 84.0, iw, 72)
			var t := Kit.tile(well, r, {"title": idea, "selected": field.text.strip_edges() == idea})
			t.name = "idea_%d" % i
			t.cb = func():
				field.text = idea
				self_ref.call(self_ref)
	draw_ideas.call(draw_ideas)
	field.text_changed.connect(func(_t: String): draw_ideas.call(draw_ideas))
	var fy := box.size.y - 32.0 - 112.0
	var rw_ := (w - 64.0 - 16.0) * 0.4
	Kit.button(box, Rect2(32, fy, rw_, 112), "info", tr("realm.more"), {"size": "L", "icon": "dice", "cb": on_more}).name = "more"
	Kit.button(box, Rect2(32.0 + rw_ + 16.0, fy, w - 64.0 - rw_ - 16.0, 112), "go", tr("flag.done"), {"size": "L",
		"cb": func(): on_done.call(field.text)}).name = "done"


## The FTUE flag wizard (canon §14.3: 3 taps, §6 «Флаг, имя, мастер флага»): a paper window L with the info plate. The
## steps as three hexes under it (the passed ones go, the current info); 6 flags to pick from as option tiles (division,
## emblem, colours) → on_pick(i), «Случайно» under them; then the chosen flag big with «Можно изменить в профиле»,
## «Случайно» and «Готово».
func show_flag_wizard(step: int, opts: Array, on_pick: Callable, on_random: Callable, on_done: Callable) -> void:
	var titles := [tr("flagw.title0"), tr("flagw.title1"), tr("flagw.title2"), tr("flagw.title3")]
	var tile := Vector2(256, 320)
	var grid_h := 16.0 + 2.0 * tile.y + 16.0 + 16.0
	var body_h := grid_h if step < 3 else 420.0 + 16.0 + 44.0
	var h := 72.0 + 48.0 + 16.0 + body_h + 32.0 + 112.0 + 32.0
	var box := _modal_box(_win_rect("L", h), false, String(titles[mini(step, 3)]), "", "info", false, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	# the steps: three hexes on a line
	var line := Panel.new()
	var lsb := Kit.style(Kit.CREAM_DEEP, 4, 0, Kit.INK, 0, 0)
	lsb.set_meta("kit_kind", "")
	line.add_theme_stylebox_override("panel", lsb)
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	line.position = Vector2(w * 0.5 - 72.0, 72.0 + 24.0 - 4.0)
	line.size = Vector2(144, 8)
	box.add_child(line)
	for i in 3:
		var role := "go" if i < step else ("info" if i == step else "")
		var hb := Kit.hex_badge(box, Vector2(w * 0.5 + (i - 1) * 72.0, 72.0 + 24.0), 22, role if role != "" else "info", str(i + 1),
			Kit.CLEAR if role != "" else Kit.CREAM_DEEP.darkened(0.2))
		hb.name = "step_%d" % i
	var y0 := 72.0 + 48.0 + 16.0
	var fy := box.size.y - 32.0 - 112.0
	if step < 3:
		var well := Kit.well(box, Rect2(32, y0, w - 64.0, grid_h))
		well.name = "options"
		var gx := (well.size.x - 32.0 - 3.0 * tile.x) / 2.0
		for i in opts.size():
			var r := Rect2(16.0 + (i % 3) * (tile.x + gx), 16.0 + (i / 3) * (tile.y + 16.0), tile.x, tile.y)
			var idx := i
			_flag_tile(well, r, opts[i], false, false, func(): on_pick.call(idx))
		Kit.button(box, Rect2((w - 480.0) * 0.5, fy, 480, 112), "info", tr("flag.random"), {"size": "L", "icon": "dice",
			"cb": on_random}).name = "random"
		return
	var big := FlagView.new(opts[0])
	big.name = "flag"
	big.position = Vector2((w - 326.0) * 0.5, y0)
	big.size = Vector2(326, 420)
	box.add_child(big)
	var hint := _paper_chip(box, Vector2(w * 0.5, y0 + 420.0 + 16.0 + 22.0), "pencil", tr("flagw.later"), w - 64.0)
	hint.name = "hint"
	var rw_ := (w - 64.0 - 16.0) * 0.4
	Kit.button(box, Rect2(32, fy, rw_, 112), "info", tr("flag.random"), {"size": "L", "icon": "dice", "cb": on_random}).name = "random"
	Kit.button(box, Rect2(32.0 + rw_ + 16.0, fy, w - 64.0 - rw_ - 16.0, 112), "go", tr("flag.done"), {"size": "L",
		"cb": on_done}).name = "done"


## A flag as an option tile (§4.9): the banner on a paper tile; the chosen one with a go outline and check; a closed one
## (a frame not owned yet) with its banner dimmed and a lock. A tap calls `cb`.
func _flag_tile(parent: Control, r: Rect2, f: Dictionary, sel: bool, locked: bool, cb: Callable) -> Control:
	var t := Kit.tile(parent, r, {"selected": sel, "cb": cb})
	t.name = "flag_" + String(f.get("div", "")) + "_" + String(f.get("em", ""))
	var fh := r.size.y - 5.0 - 20.0
	var fw := minf(r.size.x - 24.0, fh * 0.78)
	fh = fw / 0.78
	var fv := FlagView.new(f)
	fv.position = Vector2((r.size.x - fw) * 0.5, (r.size.y - 5.0 - fh) * 0.5)
	fv.size = Vector2(fw, fh)
	if locked:
		fv.modulate = Kit.LOCK_MOD
	t.add_child(fv)
	t.move_child(fv, 1)  # under the check badge
	if locked:
		var lk := _icon_rect("lock", 40)
		lk.position = Vector2(r.size.x - 46.0, r.size.y - 54.0)
		t.add_child(lk)
	return t


## The commander picker of an army (04 §15.6, docs/ui_style.md §6): a window M with a row per open commander —
## the portrait 72 with its level, the name, the skill in a chip, «Назначить» go XS at the right; the commander who
## leads this army is the selected row (a go outline and a check); the best free one wears the ribbon «Рекомендуем»,
## one of another army a chip with its number. «Снять» (info S) under the list while one leads it; ✕ closes.
## rows: [{id, name, rarity, level, lines, skills?, busy, here, best?}]
const PICK_ROW := 112.0


func show_cmd_picker(title: String, rows: Array, on_pick: Callable, on_remove: Callable) -> void:
	var any_here := rows.any(func(r): return bool(r["here"]))
	var list_h := 16.0 + rows.size() * (PICK_ROW + 12.0) - 12.0 + 16.0 + 14.0  # the first row's ribbon pokes up 14
	var foot := 16.0 + 64.0 if any_here else 0.0
	var box := _modal_box(_win_rect("M", 72.0 + list_h + foot + 32.0), false, title, "frame", "info", true, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var well := Kit.well(box, Rect2(32, 72, w - 64.0, box.size.y - 72.0 - foot - 32.0))
	var host: Control = well
	var lane := 0.0
	if list_h > well.size.y + 1.0:
		host = Kit.scroller(well, list_h)["inner"]
		lane = 12.0
	var rw := well.size.x - 32.0 - lane
	var y := 30.0
	for r in rows:
		var here := bool(r["here"])
		var id := String(r["id"])
		var pic := _cmd_face(id, String(r["rarity"]), 72.0, int(r["level"]))
		var o := {"icon_node": pic, "title": String(r["name"]), "sub": " "}
		if here:
			o["state"] = "selected"
		else:
			var b := Kit.button(null, Rect2(0, 0, 196, 48), "go", tr("cmdr.assign"), {"size": "XS", "filter": Control.MOUSE_FILTER_PASS,
				"cb": func(): on_pick.call(id)})
			b.name = "assign"
			o["right"] = b
		var row := Kit.row(host, Rect2(16, y, rw, PICK_ROW), o)
		row.name = id
		var sub := row.get_node_or_null("sub")
		if sub:
			sub.queue_free()
		var skills: Array = r.get("skills", [])
		if not skills.is_empty():
			var sk: Dictionary = skills[0]
			var room := (row.right.position.x if row.right else rw - 16.0) - row.title_label.position.x - 16.0
			var chip := _paper_chip(row, Vector2.ZERO, _skill_icon(sk), _skill_text(sk), room)
			chip.position = Vector2(row.title_label.position.x, roundf((PICK_ROW - 5.0) * 0.5 + 2.0))
		if not here:
			row.cb = func(): on_pick.call(id)
		var busy := String(r.get("busy", ""))
		if busy != "":
			var bc := Kit.chip(row, Vector2.ZERO, "", busy, "status")
			bc.name = "busy"
			bc.position = Vector2(rw - 24.0 - bc.size.x, -17)
		elif bool(r.get("best", false)) and not here:
			var rb := Kit.ribbon(row, Vector2.ZERO, tr("cmdr.recommend"), "gold")
			rb.position = Vector2(rw - 24.0 - rb.size.x, -17)
		y += PICK_ROW + 12.0
	if any_here:
		var rm := Kit.button(box, Rect2((w - 320.0) * 0.5, box.size.y - 32.0 - 64.0, 320, 64), "info", tr("cmdr.remove"),
			{"size": "S", "cb": on_remove})
		rm.name = "remove"


## A commander's face in a small slot (a picker row, a choice card): the portrait with its rarity frame and, when
## open, the level in an info hex on the bottom-right corner.
func _cmd_face(id: String, rarity: String, side: float, level := 0, locked := false) -> Control:
	var holder := Control.new()
	holder.name = "face"
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.size = Vector2(side, side)
	var p := CmdPortrait.new(id, rarity, locked)
	p.size = holder.size
	holder.add_child(p)
	if level > 0:
		var hb := Kit.hex_badge(holder, Vector2(side - 6.0, side - 6.0), 18, "info", str(level))
		hb.name = "level"
	return holder


## A commander skill's icon by its passive key (sim/commanders.gd PASSIVES).
const SKILL_ICON := {"inf": "helmet", "refill": "crate", "forts": "fort", "scout": "target", "power": "swords",
	"wedge": "target", "pocket": "target", "landing": "anchor", "port": "anchor", "home": "shield", "breach": "hammer",
	"attack": "swords", "air": "lightning", "energy": "lightning", "forms": "orders", "regen": "lightning"}


static func _skill_icon(sk: Dictionary) -> String:
	return String(sk.get("icon", SKILL_ICON.get(String(sk.get("key", "")), "frame")))


## «Клин +5,8%»: a skill's short name and its value now (a fixed part — «Разведка» — has no value).
static func _skill_text(sk: Dictionary) -> String:
	var v := String(sk.get("value", ""))
	return String(sk.get("name", "")) + (" " + v if v != "" else "")


## The collection (04 §15.7, docs/ui_style.md §6 «Командиры»): a window L with the info plate and the frame, the
## «owned/total» chip under it; an album is a section with its «3/4» chip, then tiles 3 in a row (a short last row
## centred). A tap on a tile opens the commander (on_pick(id)). The list scrolls in its well and keeps its place when
## the player comes back from a card.
## info: {title, owned?, total?, albums: [{name, full, cards: [{id, name, rarity, level, cap, can, shards?, src}]}]}
const CMD_TILE := Vector2(250, 320)
const CMD_GAP_Y := 18.0
const CMD_HEAD := 60.0  # an album's section header (48) and its gap
var _cmd_scroll := 0  # the collection's scroll (kept across the trip to a card and back)


func show_commanders(info: Dictionary, on_pick: Callable) -> void:
	var albums: Array = info["albums"]
	var owned := 0
	var total := 0
	for a in albums:
		for c in a["cards"]:
			total += 1
			if int(c["level"]) > 0:
				owned += 1
	owned = int(info.get("owned", owned))
	total = int(info.get("total", total))
	var content_h := 16.0
	for a in albums:
		content_h += CMD_HEAD + ceili((a["cards"] as Array).size() / 3.0) * (CMD_TILE.y + CMD_GAP_Y)
	content_h += 18.0  # the ribbon of a tile in the first row pokes up; the last row's shadow
	var keep := _modal != null and (_modal.has_meta("commanders") or _modal.has_meta("commander"))
	var at := _cmd_scroll if keep else 0
	var box := _modal_box(_win_rect("L", 88.0 + content_h + 32.0), false, tr("cmdr.title"), "frame", "info", true, false)
	_modal.set_meta("commanders", true)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var cc := Kit.chip(box, Vector2.ZERO, "", "%d/%d" % [owned, total], "status")
	cc.name = "count"
	cc.position = Vector2((w - cc.size.x) * 0.5, 34)
	var well := Kit.well(box, Rect2(32, 88, w - 64.0, box.size.y - 88.0 - 32.0))
	var host: Control = well
	var lane := 0.0
	if content_h > well.size.y + 1.0:
		var sc: Dictionary = Kit.scroller(well, content_h)
		host = sc["inner"]
		lane = 12.0
		var scroll: ScrollContainer = sc["scroll"]
		scroll.get_v_scroll_bar().value_changed.connect(func(v: float): _cmd_scroll = int(v))
		Kit.scroll_to(scroll, float(at))
	_cmd_scroll = at
	var rw := well.size.x - 32.0 - lane
	var gap_x := (rw - 3.0 * CMD_TILE.x) / 2.0
	var y := 16.0
	for a in albums:
		var cards: Array = a["cards"]
		var have := cards.filter(func(c): return int(c["level"]) > 0).size()
		var chip := Kit.chip(null, Vector2.ZERO, "", "%d/%d" % [have, cards.size()], "status")
		chip.name = "album_count"
		Kit.section(host, Vector2(16, y), rw - chip.size.x - 12.0, String(a["name"]))
		chip.position = Vector2(16 + rw - chip.size.x, y + 7.0)
		host.add_child(chip)
		y += CMD_HEAD
		for i in cards.size():
			var row_n := mini(3, cards.size() - (i / 3) * 3)  # how many tiles share this row
			var x0 := 16.0 + (rw - (row_n * CMD_TILE.x + (row_n - 1) * gap_x)) * 0.5
			var t := _commander_tile(cards[i], on_pick)
			t.position = Vector2(x0 + (i % 3) * (CMD_TILE.x + gap_x), y + 14.0 + (i / 3) * (CMD_TILE.y + CMD_GAP_Y))
			host.add_child(t)
		y += ceili(cards.size() / 3.0) * (CMD_TILE.y + CMD_GAP_Y)


## The sources of a commander's shards (cmdr.src.* says the same in words): [icon, key, arg] — the card's «Где взять»
## chips and, as icons alone, a locked tile's.
const CMD_SRC := {
	"cmd_bram": [["swords", "cmdr.s.tutorial", 0]],
	"cmd_lira": [["trophy", "cmdr.s.chapter", 1]],
	"cmd_olm": [["chest_wood", "cmdr.s.crates", 0], ["swords", "cmdr.s.arena", 0]],
	"cmd_vik": [["chest_wood", "cmdr.s.crates", 0], ["orders", "cmdr.s.orders", 0]],
	"cmd_vega": [["calendar", "cmdr.s.calendar", 4], ["chest_wood", "cmdr.s.crates", 0]],
	"cmd_kort": [["horn", "cmdr.s.events", 0], ["chest_wood", "cmdr.s.crates", 0]],
	"cmd_seir": [["medal", "cmdr.s.pass", 0], ["chest_wood", "cmdr.s.crates", 0]],
	"cmd_frey": [["trophy", "cmdr.s.chapter", 2], ["chest_wood", "cmdr.s.crates", 0]],
	"cmd_irma": [["calendar", "cmdr.s.calendar", 7], ["chest_royal", "cmdr.s.royal", 0]],
	"cmd_hawk": [["trophy", "cmdr.s.chapter", 3], ["chest_royal", "cmdr.s.royal", 0]],
	"cmd_vance": [["gift", "cmdr.s.recruit", 0], ["horn", "cmdr.s.events", 0], ["chest_royal", "cmdr.s.royal", 0]],
	"cmd_rai": [["trophy", "cmdr.s.chapter", 4], ["calendar", "cmdr.s.calendar", 28], ["medal", "cmdr.s.pass", 0],
		["chest_royal", "cmdr.s.cases", 0]],
}


func _src_text(s: Array) -> String:
	var k := String(s[1])
	match k:
		"cmdr.s.chapter":
			return tr(k) % ROMAN[clampi(int(s[2]), 0, ROMAN.size() - 1)]
		"cmdr.s.calendar":
			return tr(k) % int(s[2])
	return tr(k)


## A tile of the collection (§6 «Командиры», 250×320): the portrait full-bleed on its rarity gradient in an INK body,
## the rarity gem (a hex of the rarity's colour) top-left and the level hex top-right, the name on a scrim, the shard
## bar M at the bottom — full «4/4» in go with the go ribbon «Повысить!» when a level can be bought (never «29/4»),
## gold at the top level. A locked one: the faint silhouette, a lock, the sources as icon chips and the shards toward
## the unlock. A tap opens the card.
func _commander_tile(c: Dictionary, on_pick: Callable) -> Control:
	var lvl := int(c["level"])
	var locked := lvl <= 0
	var can := bool(c.get("can", false))
	var rarity := String(c["rarity"])
	var w := CMD_TILE.x
	var h := CMD_TILE.y
	var t := Kit.KitTile.new()
	t.name = String(c["id"])
	var sb := Kit.style(Kit.INK, 24, 0, Kit.INK, 5, 0)
	sb.set_meta("kit_kind", "")
	t.add_theme_stylebox_override("panel", sb)
	t.size = CMD_TILE
	var id := String(c["id"])
	t.cb = func(): on_pick.call(id)
	var p := CmdPortrait.new(id, rarity, locked)
	p.name = "portrait"
	p.position = Vector2(4, 4)
	p.size = Vector2(w - 8.0, h - 8.0)
	t.add_child(p)
	var clip := Panel.new()  # the scrim follows the frame's inner corners
	var csb := Kit.style(Kit.INK, 16, 0, Kit.INK, 0, 0)
	csb.set_meta("kit_kind", "")
	clip.add_theme_stylebox_override("panel", csb)
	clip.clip_children = CanvasItem.CLIP_CHILDREN_ONLY
	clip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	clip.position = Vector2(8, 8)
	clip.size = Vector2(w - 16.0, h - 16.0)
	t.add_child(clip)
	var scrim := TextureRect.new()
	scrim.texture = Kit.vgradient(Kit.alpha(Kit.INK, 0.0), Kit.alpha(Kit.INK, 0.92))
	scrim.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	scrim.stretch_mode = TextureRect.STRETCH_SCALE
	scrim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	scrim.position = Vector2(0, clip.size.y - 150.0)
	scrim.size = Vector2(clip.size.x, 150)
	clip.add_child(scrim)
	var gem := Kit.hex_badge(t, Vector2(24, 24), 20, "", "", Kit.RARITY.get(rarity, Kit.RARITY["common"]))
	gem.name = "rarity"
	if not locked:
		var lh := Kit.hex_badge(t, Vector2(w - 26.0, 26), 22, "info", str(lvl))
		lh.name = "level"
	else:
		var lk := _icon_rect("lock", 72)
		lk.name = "lock"
		lk.position = Vector2((w - 72.0) * 0.5, 74)
		t.add_child(lk)
		var srcs: Array = CMD_SRC.get(id, [])
		var n := mini(3, srcs.size())
		var d := 48.0
		var sx := (w - (n * d + (n - 1) * 8.0)) * 0.5
		for i in n:
			var s: Array = srcs[i]
			var disc := Panel.new()
			disc.name = "src_%d" % i
			var dsb := Kit.style(Kit.alpha(Kit.INK, 0.85), 24, 3, Kit.INK, 0, 0)
			dsb.set_meta("kit_kind", "")
			disc.add_theme_stylebox_override("panel", dsb)
			disc.mouse_filter = Control.MOUSE_FILTER_IGNORE
			disc.position = Vector2(sx + i * (d + 8.0), 164)
			disc.size = Vector2(d, d)
			t.add_child(disc)
			var ic := _icon_rect(String(s[0]), 34)
			ic.position = Vector2(7, 7)
			disc.add_child(ic)
	var nm := String(c["name"])
	var ns := Kit.fit_size(nm, 26, w - 28.0, "d900", 22)
	var nl := Kit.label(nm, ns, Kit.TEXT, true)
	nl.name = "name"
	nl.add_theme_font_size_override("font_size", ns)
	nl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	nl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	nl.clip_text = true
	nl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	nl.position = Vector2(14, h - 20.0 - 28.0 - 8.0 - 36.0)
	nl.size = Vector2(w - 28.0, 36)
	t.add_child(nl)
	var br := Rect2(18, h - 20.0 - 28.0, w - 36.0, 28)
	if c.has("shards"):
		var sh: Array = c["shards"]
		var need := maxi(1, int(sh[1]))
		var have := mini(int(sh[0]), need)  # «4/4», never «29/4»
		var full := int(sh[0]) >= need
		var bar := Kit.bar(t, br, float(have) / need, "go" if full else "info", "%d/%d" % [have, need])
		bar.name = "shards"
	elif not locked:
		var bar := Kit.bar(t, br, 1.0, "gold", tr("cmdr.max_short"))
		bar.name = "shards"
	if can:
		var rb := Kit.ribbon(t, Vector2(w * 0.5, 2), tr("cmdr.up_ribbon"), "go")
		rb.name = "upgrade"
	return t


## The commander card (04 §15.7, docs/ui_style.md §6 «Карточка командира»): a sub-page of the collection — the back
## button (on_back) top-left, ✕ top-right. The portrait 320×360 on the left; at the right the rarity chip, the album, the
## level hex R 40 with the cap, the shard bar L and the skill chips («Клин +5,8%»; a tap tells the whole skill). The
## biography; a track of 8 level nodes (2…16, the reached ones filled, those past the era's cap locked; a tap tells
## the value there); «Где взять» as source chips. The footer: go L «Повысить» with its price [shard N][coin G] →
## on_upgrade (the short number red; grey with the reason when the era caps it or the commander is locked), and the
## Royal case target as info L on the left (epic, legendary; on_target).
## info: {id, name, rarity, rarity_name, level, cap, bio, album, mood, can, block, cost [shards, gold], need_dl,
##   shards [have, need]?, unlock, skills [{icon, name, value, full}], track [[level, text]], target?}
const TRACK_LEVELS: Array[int] = [2, 4, 6, 8, 10, 12, 14, 16]


func show_commander(info: Dictionary, on_upgrade: Callable, on_target: Callable, on_back: Callable) -> void:
	var id := String(info["id"])
	var lvl := int(info["level"])
	var locked := lvl <= 0
	var rarity := String(info["rarity"])
	var cap := int(info.get("cap", 16))
	var block := String(info.get("block", "" if bool(info.get("can", false)) else "locked" if locked else "max"))
	var srcs: Array = CMD_SRC.get(id, [])
	var bio := String(info.get("bio", ""))
	var bio_h := 0.0
	if bio != "":
		var f := Kit.font("b800")
		bio_h = minf(3.0, ceilf(f.get_multiline_string_size(bio, HORIZONTAL_ALIGNMENT_LEFT, 829.0, 26).y / (26.0 * 1.36))) * 36.0 + 20.0
	# the source chips' rows (they wrap)
	var src_rows := 1
	var sxw := 0.0
	for s in srcs:
		var cw := _paper_chip_w(String(s[0]), _src_text(s))
		if sxw > 0.0 and sxw + cw > 829.0:
			src_rows += 1
			sxw = 0.0
		sxw += cw + 12.0
	var y_bio := 72.0 + 360.0 + 20.0
	var y_track := y_bio + bio_h
	var y_src := y_track + 48.0 + 12.0 + 112.0 + 20.0
	var h := y_src + 48.0 + 12.0 + src_rows * 56.0 - 12.0 + 32.0 + 112.0 + 32.0
	var box := _modal_box(_win_rect("L", h), false, String(info["name"]), "", "info", true, false)
	_modal.set_meta("commander", true)
	box.set_meta("kit_native", true)
	var w := box.size.x
	if on_back.is_valid():
		Kit.back_button(box, on_back).name = "back"
	# ---- the portrait
	var pf := Panel.new()
	pf.name = "portrait_frame"
	var psb := Kit.style(Kit.INK, 24, 0, Kit.INK, 6, 0)
	psb.set_meta("kit_kind", "")
	pf.add_theme_stylebox_override("panel", psb)
	pf.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pf.position = Vector2(32, 72)
	pf.size = Vector2(320, 360)
	box.add_child(pf)
	var p := CmdPortrait.new(id, rarity, locked)
	p.name = "portrait"
	p.mood = String(info.get("mood", ""))  # a smile right after a level-up
	p.position = Vector2(4, 4)
	p.size = pf.size - Vector2(8, 8)
	pf.add_child(p)
	if locked:
		var lk := _icon_rect("lock", 96)
		lk.position = (pf.size - lk.size) * 0.5
		pf.add_child(lk)
	# ---- the right column
	var x0 := 32.0 + 320.0 + 28.0
	var cw0 := w - 32.0 - x0
	var rc := Kit.chip(box, Vector2(x0, 76), "", String(info.get("rarity_name", "")), "owner", Kit.RARITY.get(rarity, Kit.RARITY["common"]))
	rc.name = "rarity"
	var album := String(info.get("album", ""))
	if album != "":
		var al := Kit.label(album, 26, Kit.MUTED_CREAM, false)
		al.name = "album"
		al.clip_text = true
		al.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		al.position = Vector2(x0, 118)
		al.size = Vector2(cw0, 36)
		box.add_child(al)
	var hx := Kit.hex_badge(box, Vector2(x0 + 40.0, 212), 40, "info" if not locked else "lock", str(lvl) if not locked else "")
	hx.name = "level"
	if locked:
		var hl := _icon_rect("lock", 44)
		hl.position = Vector2(18, 16)
		hx.add_child(hl)
	var lt := Kit.label(tr("cmdr.level") if not locked else tr("cmdr.locked_short"), 30, Kit.INK_TEXT, true)
	lt.name = "level_title"
	lt.position = Vector2(x0 + 96.0, 178)
	lt.size = Vector2(cw0 - 96.0, 38)
	box.add_child(lt)
	var cl := Kit.label(tr("cmdr.cap") % cap if not locked else tr("cmdr.unlock_at") % L.plural(int(info.get("unlock", 10)), "plural.shards"), 24, Kit.MUTED_CREAM, true)
	cl.name = "cap"
	cl.add_theme_font_override("font", Kit.font("d800"))
	cl.position = Vector2(x0 + 96.0, 216)
	cl.size = Vector2(cw0 - 96.0, 32)
	box.add_child(cl)
	if info.has("shards"):
		var sh: Array = info["shards"]
		var need := maxi(1, int(sh[1]))
		var have := mini(int(sh[0]), need)
		var full := int(sh[0]) >= need
		var bar := Kit.bar(box, Rect2(x0 + 26.0, 276, cw0 - 26.0, 40), float(have) / need, "go" if full else "info", "%d/%d" % [have, need], true)
		bar.name = "shards"
		var si := _icon_rect("shard", 56)
		si.position = Vector2(x0 - 6.0, 268)
		box.add_child(si)
	elif not locked:
		var mc := _paper_chip(box, Vector2.ZERO, "medal_gold", tr("cmdr.max_short"), cw0)
		mc.name = "max"
		mc.position = Vector2(x0, 274)
	var sy := 336.0
	for sk in info.get("skills", []):
		var chip := _paper_chip(box, Vector2.ZERO, _skill_icon(sk), _skill_text(sk), cw0)
		chip.name = "skill"
		chip.position = Vector2(x0, sy)
		chip.mouse_filter = Control.MOUSE_FILTER_STOP
		var full_text := String(sk.get("full", ""))
		var title := _skill_text(sk)
		chip.gui_input.connect(func(e): if _is_tap(e): Kit.tooltip(chip, title, full_text if full_text != title else ""))
		sy += 52.0
	# ---- the biography
	if bio != "":
		var bl := Kit.label(bio, 26, Kit.SOFT_CREAM, false)
		bl.name = "bio"
		bl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		bl.max_lines_visible = 3
		bl.position = Vector2(32, y_bio)
		bl.size = Vector2(w - 64.0, bio_h - 20.0)
		box.add_child(bl)
	# ---- the level track
	Kit.section(box, Vector2(32, y_track), w - 64.0, tr("cmdr.levels"), "xp")
	var tw := Kit.well(box, Rect2(32, y_track + 60.0, w - 64.0, 112))
	tw.name = "track"
	var track: Array = info.get("track", [])
	var vals := {}
	for tv in track:
		vals[int(tv[0])] = String(tv[1])
	var x_a := 56.0
	var x_b := tw.size.x - 56.0
	var step := (x_b - x_a) / (TRACK_LEVELS.size() - 1)
	var line_y := 56.0
	var line := Panel.new()
	var lsb := Kit.style(Kit.CREAM_DEEP, 6, 0, Kit.INK, 0, 0)
	lsb.set_meta("kit_kind", "")
	line.add_theme_stylebox_override("panel", lsb)
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	line.position = Vector2(x_a, line_y - 6.0)
	line.size = Vector2(x_b - x_a, 12)
	tw.add_child(line)
	var reach := 0.0  # how far along the line the commander is: between the nodes when the level is odd
	for i in TRACK_LEVELS.size():
		if lvl >= TRACK_LEVELS[i]:
			reach = float(i)
	if lvl > TRACK_LEVELS[0] and lvl < TRACK_LEVELS[-1] and lvl % 2 == 1:
		reach += 0.5
	if lvl >= TRACK_LEVELS[0]:
		var fill := Panel.new()
		var fsb := Kit.style(Kit.face_of("info"), 6, 0, Kit.INK, 0, 0)
		fsb.set_meta("kit_kind", "")
		fill.add_theme_stylebox_override("panel", fsb)
		fill.mouse_filter = Control.MOUSE_FILTER_IGNORE
		fill.position = line.position
		fill.size = Vector2(maxf(12.0, reach * step), 12)
		tw.add_child(fill)
	for i in TRACK_LEVELS.size():
		var lv: int = TRACK_LEVELS[i]
		var c := Vector2(x_a + i * step, line_y)
		var role := "info" if lvl >= lv else ("lock" if lv > cap else "")
		var face := Kit.CLEAR if role != "" else Kit.CREAM_DEEP.darkened(0.18)
		var node := Kit.hex_badge(tw, c, 30, role if role != "" else "info", str(lv), face)
		node.name = "lv_%d" % lv
		var hit := Control.new()
		hit.position = c - Vector2(46, 46)
		hit.size = Vector2(92, 92)
		hit.mouse_filter = Control.MOUSE_FILTER_STOP
		tw.add_child(hit)
		var tip := String(vals.get(lv, ""))
		if lv > cap:
			tip += ("\n" if tip != "" else "") + tr("cmdr.need_dl") % ceili(lv / 2.0)
		var tt := tr("cmdr.lvl_n") % lv
		hit.gui_input.connect(func(e): if _is_tap(e): Kit.tooltip(node, tt, tip))
	# ---- where the shards come from
	Kit.section(box, Vector2(32, y_src), w - 64.0, tr("cmdr.where_title"), "shard")
	var cx := 32.0
	var cy := y_src + 60.0
	for s in srcs:
		var txt := _src_text(s)
		var cwid := _paper_chip_w(String(s[0]), txt)
		if cx > 32.0 and cx + cwid > w - 32.0:
			cx = 32.0
			cy += 56.0
		var chip := _paper_chip(box, Vector2.ZERO, String(s[0]), txt, w - 64.0)
		chip.name = "source"
		chip.position = Vector2(cx, cy)
		cx += chip.size.x + 12.0
	# ---- the footer: «Повысить» with its price, the Royal case target
	var fy := box.size.y - 32.0 - 112.0
	var main_r := Rect2((w - 480.0) * 0.5, fy, 480, 112)
	if on_target.is_valid():
		var tw2 := (w - 64.0 - 16.0) * 0.4
		var on := bool(info.get("target", false))
		var tb := Kit.button(box, Rect2(32, fy, tw2, 112), "info", tr("cmdr.target_btn"), {"size": "L",
			"icon": "check" if on else "chest_royal", "cb": on_target})
		tb.name = "target"
		main_r = Rect2(32.0 + tw2 + 16.0, fy, w - 64.0 - tw2 - 16.0, 112)
	var cost: Array = info.get("cost", [])
	var price: Array = []
	if cost.size() >= 2:
		price = [["shard", str(int(cost[0])), block == "shards"], ["coin", fmt_num(int(cost[1])), block == "gold"]]
	var b: Kit.KitButton
	match block:
		"", "shards", "gold":
			b = Kit.button(box, main_r, "go", tr("cmdr.upgrade_btn"), {"size": "L", "icon": "arrow_up", "price": price,
				"cb": on_upgrade})
		"dl":
			b = Kit.button(box, main_r, "go", tr("cmdr.upgrade_btn"), {"size": "L", "icon": "arrow_up", "price": price,
				"enabled": false})
			var why := tr("cmdr.need_dl") % int(info.get("need_dl", ceili((lvl + 1) / 2.0)))
			b.denied.connect(func(): Kit.tooltip(b, tr("cmdr.upgrade_btn"), why))
		"locked":
			var left := maxi(0, int(info.get("unlock", 10)) - (int((info["shards"] as Array)[0]) if info.has("shards") else 0))
			b = Kit.button(box, main_r, "go", tr("cmdr.locked_short"), {"size": "L", "icon": "lock", "enabled": false})
			var why2 := tr("cmdr.unlock_left") % L.plural(left, "plural.shards")
			b.denied.connect(func(): Kit.tooltip(b, tr("cmdr.locked_short"), why2))
		_:
			b = Kit.button(box, main_r, "go", tr("cmdr.max_btn"), {"size": "L", "icon": "medal_gold", "enabled": false})
			b.denied.connect(func(): Kit.tooltip(b, tr("cmdr.max_short"), ""))
	b.name = "upgrade"


## The width a paper chip will take for this icon and text (lays chips out in rows before making them).
func _paper_chip_w(icon: String, text: String) -> float:
	var x := 50.0 if Kit.icon_tex(icon) != null else 14.0
	return x + Kit.text_w(text, 26, "d800", false) + 2.0 + 16.0


## Hand picker (03 §5.2, docs/ui_style.md §6 «Выбор руки»): a window L with the info plate «Рука» and the chip
## «chosen/slots». On top a well of sockets 116×150 — «Атака» pinned in the first with a lock badge, the chosen cards in
## the next ones, the free ones empty with their number in a hex; under it a well with every other open card (180×230,
## its energy cost in a hex), the chosen ones with a go check. A tap on a card calls on_toggle(card) (the caller shows
## the picker again; the card that moved pops in for 160 ms); a tap on «Атака» lets the caller say it is fixed.
## The sockets explain the rule — no paragraph; «Готово» (go) closes it.
const HAND_SOCKET := Vector2(116, 150)
const HAND_CARD := Vector2(180, 230)
var _hand_last := ""  # the card the last tap toggled: it pops in after the picker shows again


func show_hand_picker(cards: Array, chosen: Array, slots: int, on_toggle: Callable) -> void:
	var grid_cards: Array = cards.filter(func(c): return String(c) != "attack")
	var rows := maxi(1, ceili(grid_cards.size() / 4.0))
	var sock_h := 16.0 + HAND_SOCKET.y + 16.0
	var grid_h := 16.0 + rows * HAND_CARD.y + (rows - 1) * 16.0 + 16.0
	var h := 88.0 + sock_h + 20.0 + grid_h + 32.0 + 112.0 + 32.0
	var again := _modal != null and _modal.has_meta("hand")
	var last := _hand_last if again else ""
	_hand_last = ""
	var box := _modal_box(_win_rect("L", h), false, tr("hand.plate"), "cards", "info", true, false)
	_modal.set_meta("hand", true)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var cc := Kit.chip(box, Vector2.ZERO, "", "%d/%d" % [chosen.size(), slots], "status")
	cc.name = "count"
	cc.position = Vector2((w - cc.size.x) * 0.5, 34)
	var tap := func(c: String) -> void:
		_hand_last = c
		on_toggle.call(c)
	# ---- the sockets
	var sw := Kit.well(box, Rect2(32, 88, w - 64.0, sock_h))
	sw.name = "sockets"
	var n := 1 + slots
	var gap := minf(16.0, (sw.size.x - 32.0 - n * HAND_SOCKET.x) / maxf(1.0, n - 1.0))
	var x0 := (sw.size.x - (n * HAND_SOCKET.x + (n - 1) * gap)) * 0.5
	for i in n:
		var r := Rect2(x0 + i * (HAND_SOCKET.x + gap), 16, HAND_SOCKET.x, HAND_SOCKET.y)
		var sock := Panel.new()
		sock.name = "socket_%d" % i
		var ssb := Kit.style(Kit.CREAM_DEEP, 20, 0, Kit.INK, 0, 0)
		ssb.set_meta("kit_kind", "")
		sock.add_theme_stylebox_override("panel", ssb)
		sock.mouse_filter = Control.MOUSE_FILTER_IGNORE
		sock.position = r.position
		sock.size = r.size
		sw.add_child(sock)
		var card := "attack" if i == 0 else (String(chosen[i - 1]) if i - 1 < chosen.size() else "")
		if card == "":
			var hb := Kit.hex_badge(sock, r.size * 0.5, 26, "info", str(i + 1), Kit.CREAM_DEEP.darkened(0.2))
			hb.name = "num"
			continue
		var t := _hand_tile(sock, Rect2(Vector2.ZERO, r.size), card, func(): tap.call(card))
		if i == 0:  # «Атака» is pinned: a lock badge, at full opacity
			var lb := Panel.new()
			lb.name = "pinned"
			var lsb := Kit.style(Kit.INK, 20, 3, Kit.INK, 0, 0)
			lsb.set_meta("kit_kind", "")
			lb.add_theme_stylebox_override("panel", lsb)
			lb.mouse_filter = Control.MOUSE_FILTER_IGNORE
			lb.size = Vector2(40, 40)
			lb.position = Vector2(r.size.x - 30.0, -10)
			t.add_child(lb)
			var li := _icon_rect("lock", 28)
			li.position = Vector2(6, 5)
			lb.add_child(li)
		if card == last:
			_hand_pop(t)
	# ---- every other open card
	var gw := Kit.well(box, Rect2(32, 88.0 + sock_h + 20.0, w - 64.0, grid_h))
	gw.name = "cards"
	var gx := (gw.size.x - 32.0 - 4.0 * HAND_CARD.x) / 3.0
	for i in grid_cards.size():
		var c := String(grid_cards[i])
		var r := Rect2(16.0 + (i % 4) * (HAND_CARD.x + gx), 16.0 + (i / 4) * (HAND_CARD.y + 16.0), HAND_CARD.x, HAND_CARD.y)
		var t := _hand_tile(gw, r, c, func(): tap.call(c))
		if chosen.has(c):
			var ck := Kit.check_badge(t, Vector2(r.size.x - 8.0, 8.0), 44.0)
			if c == last:
				Kit.badge_pop(ck)
		elif c == last:
			_hand_pop(t)
	var done := Kit.button(box, Rect2((w - 480.0) * 0.5, box.size.y - 32.0 - 112.0, 480, 112), "go", tr("flag.done"),
		{"size": "L", "cb": close_modal})
	done.name = "done"


## A hand card on paper: the card's painted scene full-bleed in a SLATE card (INK 4, lip 6), its name on a scrim and
## its energy cost in an ENERGY hex on the top-left corner; a tap (not a swipe) calls `cb`.
func _hand_tile(parent: Control, r: Rect2, card: String, cb: Callable) -> Kit.KitTile:
	var small := r.size.x < 150.0
	var t := Kit.KitTile.new()
	t.name = card
	var sb := Kit.style(Kit.SLATE, 20, 4, Kit.INK, 5, 6)
	sb.set_meta("kit_kind", "")
	t.add_theme_stylebox_override("panel", sb)
	t.position = r.position
	t.size = r.size
	t.cb = cb
	t.add_child(Kit.KitDecor.new())
	var art := Panel.new()
	art.name = "art"
	var asb := Kit.style(Kit.SKY_LOW, 14, 0, Kit.INK, 0, 0)
	asb.set_meta("kit_kind", "")
	art.add_theme_stylebox_override("panel", asb)
	art.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.position = Vector2(4, 4)
	art.size = Vector2(r.size.x - 8.0, r.size.y - 14.0)
	t.add_child(art)
	var pic := TextureRect.new()
	pic.texture = _card_art(card)
	pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pic.size = art.size
	art.add_child(pic)
	var scrim := TextureRect.new()
	scrim.texture = Kit.vgradient(Kit.alpha(Kit.INK, 0.0), Kit.alpha(Kit.INK, 0.9))
	scrim.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	scrim.stretch_mode = TextureRect.STRETCH_SCALE
	scrim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	scrim.position = Vector2(0, art.size.y - (56.0 if small else 72.0))
	scrim.size = Vector2(art.size.x, 56.0 if small else 72.0)
	art.add_child(scrim)
	var name_txt := _card_name(card)
	var base := 22 if small else 26
	var fs := Kit.fit_size(name_txt, base, r.size.x - 12.0, "d900", 22 if not small else 20)
	var nm := Kit.label(name_txt, fs, Kit.TEXT, true)
	nm.name = "name"
	nm.add_theme_font_override("font", Kit.font("d900"))
	nm.add_theme_font_size_override("font_size", fs)
	nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	nm.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	nm.clip_text = true
	nm.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	nm.position = Vector2(4, r.size.y - 10.0 - 40.0)
	nm.size = Vector2(r.size.x - 8.0, 36)
	t.add_child(nm)
	var cost := Kit.hex_badge(t, Vector2(16, 16) if small else Vector2(18, 18), 20 if small else 24, "energy", str(_card_cost(card)))
	cost.name = "cost"
	return t


## The card that just moved: 0.86 → 1 in 160 ms (BACK/OUT).
func _hand_pop(node: Control) -> void:
	var d := Kit._dur(0.16)
	if d <= 0.0:
		return
	node.pivot_offset = node.size * 0.5
	node.scale = Vector2(0.86, 0.86)
	node.create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT).tween_property(node, "scale", Vector2.ONE, d)


## Соседи (§6): the alarm first, then a card per neighbour.
func show_diplomacy(items: Array) -> void:
	_fill_panel("d", items, _diplomacy_card)


## The status chip of a neighbour's card by the relation (§6 Соседи): its icon and its fill.
const RELATION_LOOK := {"war": ["swords", "war"], "coalition": ["horn", "war"], "pact": ["handshake", "go"],
	"ally": ["handshake", "go"], "truce": ["dove", "info"], "peace": ["dove", "info"]}


## A neighbour's relation with the player from its item: "war", "coalition" (one forming against us), "ally",
## "pact", "truce" or "peace".
func _relation(it: Dictionary) -> String:
	var st := String(it.get("status", ""))
	if st == tr("dipl.war"):
		return "war"
	if st == tr("dipl.in_coalition"):
		return "coalition"
	if bool(it.get("ally", false)):
		return "ally"
	if int(it.get("pact_left", 0)) > 0:
		return "pact"
	if st != "" and st != tr("dipl.peace"):
		return "truce"
	return "peace"


## The leader's mood by the relation and the opinion (§6 Соседи): angry at war or at −30 and below, a smile from +30,
## cunning while plotting in a coalition, calm otherwise.
func _leader_face(it: Dictionary) -> String:
	var rel := _relation(it)
	var v := float(it.get("opinion", 0.0))
	if rel == "war" or v <= -30.0:
		return "angry"
	if v >= 30.0:
		return "smile"
	return "cunning" if rel == "coalition" else ""


## «+46» / «−10» / «0» (a real minus).
static func _signed(v: int) -> String:
	return ("+" if v > 0 else "") + Kit.fmt_num(v)


## A neighbour's card (§6 Соседи): the leader in their mood on the state's colour, the state's short name; the relation on
## the left chip, the opinion on the right one (green / red); exactly one button for the moment — «Мир» at war,
## «Призыв» for an ally we may call into our war, a gift while they dislike us (or to an ally), else «Пакт» (grey
## with the reason while it cannot be signed). A tap on the card opens the leader's window with every action.
func _diplomacy_card(it: Dictionary) -> Control:
	if String(it.get("kind", "")) == "alarm":
		return _alarm_card(it)
	var rel := _relation(it)
	var v := roundi(float(it.get("opinion", 0.0)))
	var look: Array = RELATION_LOOK[rel]
	var opts := {"backdrop": "team", "team": it.get("color", Kit.face_of("war")),
		"art_node": _leader_bust(it, Rect2(22, -14, 128, 147)),
		"corner": {"icon": look[0], "fill": Kit.face_of(String(look[1]))},
		"tag_r": {"text": _signed(v), "role": "go" if v > 0 else ("war" if v < 0 else "")},
		"tap_cb": func(): _leader_dialog(it),
		"cta": _diplomacy_cta(it, rel)}
	return Kit.card(null, _state_short(String(it.get("state", ""))), opts)


const STATE_KEYS: Array[String] = ["barons", "hamlets", "league", "order", "pack", "conclave", "lakes", "alvaria",
	"saren", "veilmark"]


## A state's short name for its card («Кремнёвые Бароны» → «Бароны», as on the map's owner chips): one line under
## the leader's face, which a two-line name would cover; the full name titles the leader's window.
func _state_short(name: String) -> String:
	for k in STATE_KEYS:
		if tr("state." + k) == name:
			var sk := "state." + k + ".short"
			return tr(sk) if tr(sk) != sk else name
	return name


## A leader's bust in their mood (the portrait render) laid at `r` inside an art window, or a crown without one.
func _leader_bust(it: Dictionary, r: Rect2) -> Control:
	var pid := String(it.get("portrait", ""))
	var tex: Texture2D = CmdPortrait._render(pid, _leader_face(it)) if pid != "" else null
	var t := TextureRect.new()
	t.texture = tex if tex != null else Kit.icon_tex("crown")
	t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	t.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	t.position = r.position
	t.size = r.size
	return t


const CALL_OPINION := 60.0  ## an ally from this opinion can be called into the player's war (canon §10.7)


## The one button of a neighbour's card (see _diplomacy_card).
func _diplomacy_cta(it: Dictionary, rel: String) -> Dictionary:
	var id: int = it["id"]
	if rel == "war":
		return {"role": "go", "caption": tr("dipl.peace"), "icon": "dove", "cb": _peace_cb(it)}
	if bool(it.get("can_call", false)):
		return {"role": "info", "caption": tr("dipl.call"), "icon": "horn", "cb": func(): diplomacy_action.emit(id, "call")}
	# a gift while they dislike us — or for an ally below the goodwill (60) that lets us call them into a war
	var op := float(it.get("opinion", 0.0))
	if (op < 0.0 or (rel == "ally" and op < CALL_OPINION)) and int(it.get("gift_left", 0)) == 0:
		var g := _gift_price(it)
		var ct := {"role": "go", "caption": tr("dipl.gift"), "icon": "gift", "price": [g[0]], "cb": func(): diplomacy_action.emit(id, "gift")}
		if String(g[1]) != "":
			ct["short_reason"] = g[1]
		return ct
	var why := String(it.get("pact_reason", ""))
	if why == "":
		return {"role": "info", "caption": tr("dipl.pact_btn"), "icon": "treaty", "cb": func(): diplomacy_action.emit(id, "pact")}
	if int(it.get("pact_left", 0)) > 0:  # the pact holds: its time left
		return {"role": "lock", "caption": fmt_time(int(it["pact_left"])), "icon": "hourglass", "enabled": false, "reason": why}
	return {"role": "lock", "caption": tr("dipl.pact_btn"), "icon": "treaty", "enabled": false, "reason": why}


## «Мир» with a neighbour at war: a coalition member's separate peace, else the treaty of the war (the status
## button's «peace»).
func _peace_cb(it: Dictionary) -> Callable:
	var id: int = it["id"]
	if bool(it.get("separate", false)):
		return func(): diplomacy_action.emit(id, "separate")
	return func(): action_pressed.emit("peace")


## The gift's price item [coin, N, short] and, when the gold is surely short, the reason («Не хватает золота»).
func _gift_price(it: Dictionary) -> Array:
	var cost := int(it.get("gift_cost", 0))
	var st := _stock("gold")
	var short := int(st[1]) >= 0 and cost > int(st[1])
	return [["coin", fmt_num(cost), short], L.t("err.not_enough|res.gen.gold") if short else ""]


## A neighbour's leader (§6 Соседи): a window M with the state's name. The face in its mood with the leader's name,
## a line by the mood, the relation and the opinion; the actions the relation allows on a 2×2 grid of M buttons —
## «Пакт», «Союз» (never for a hostile state or a coalition member; «Призыв» for an ally while we may call them),
## «Обмен», «Подарок» — a temporarily blocked one grey, its tap says why; at the bottom «Объявить войну» (war L), or
## «Мир» (go L) while at war with them. An action closes the window and emits the existing diplomacy_action.
func _leader_dialog(it: Dictionary) -> void:
	var id: int = it["id"]
	var rel := _relation(it)
	var v := float(it.get("opinion", 0.0))
	var hostile := rel in ["war", "coalition"] or v < -10.0
	var acts: Array = []  # {kind, cap, icon, on, why, price, short}
	if rel != "war" and it.has("pact_reason"):
		var why_p := String(it["pact_reason"])
		acts.append({"kind": "pact", "cap": tr("dipl.pact_btn"), "icon": "treaty", "on": why_p == "", "why": why_p})
	if rel == "ally":
		if bool(it.get("can_call", false)):
			acts.append({"kind": "call", "cap": tr("dipl.call"), "icon": "horn", "on": true, "why": ""})
	elif not hostile and it.has("ally_reason"):
		var why_a := String(it["ally_reason"])
		acts.append({"kind": "ally", "cap": tr("dipl.alliance"), "icon": "handshake", "on": why_a == "", "why": why_a})
	if rel != "war" and it.has("swap_reason"):
		var why_s := String(it["swap_reason"])
		acts.append({"kind": "swap", "cap": tr("dipl.swap"), "icon": "swap", "on": why_s == "", "why": why_s})
	var gl := int(it.get("gift_left", 0))
	var g := _gift_price(it)
	acts.append({"kind": "gift", "cap": tr("dipl.gift"), "icon": "gift", "on": gl == 0,
		"why": tr("dipl.gift_wait") % fmt_time(gl), "price": [g[0]], "short": g[1]})
	var rows := ceili(acts.size() / 2.0)
	var grid_y := 280.0
	var foot_y := grid_y + rows * 88.0 + (rows - 1) * 16.0 + 36.0
	var h := foot_y + 116.0 + 32.0
	var box := _modal_box(_win_rect("M", h), false, String(it.get("state", "")), "", "info", true, false)
	box.set_meta("kit_native", true)
	var w := box.size.x
	var team: Color = it.get("color", Kit.face_of("info"))
	_leader_seal(box, String(it.get("portrait", "")), team, Rect2(32, 64, 156, 170), _leader_face(it))
	# the right column: who speaks (H2), their line by the mood, then the relation and the opinion
	var bx := 32.0 + 156.0 + 28.0
	var cw := w - 32.0 - bx
	var leader := String(it.get("leader", ""))
	var ns := Kit.fit_size(leader, 30, cw, "d900", 24, false)
	var nl := Kit.label(leader, ns, Kit.INK_TEXT, true)
	nl.name = "leader_name"
	nl.add_theme_font_size_override("font_size", ns)
	nl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	nl.clip_text = true
	nl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	nl.position = Vector2(bx - 4.0, 60)
	nl.size = Vector2(cw + 4.0, 40)
	box.add_child(nl)
	var say: String = "dipl.say.war" if rel == "war" else {"angry": "dipl.say.angry", "smile": "dipl.say.smile",
		"cunning": "dipl.say.cunning"}.get(_leader_face(it), "dipl.say.calm")
	Kit.bubble(box, Rect2(bx, 106, cw, 88), tr(say), "left")
	# the relation and the opinion under the line
	# the relation's chip says the most telling thing: a coalition member's share of the war score (06 §14.6), an AI
	# alliance, our alliance, else the status
	var look: Array = RELATION_LOOK[rel]
	var st_text := String(it.get("status", ""))
	var st_icon := String(look[0])
	if it.has("share"):
		st_text = tr("dipl.share") % Kit.fmt_dec(float(it["share"]), 1)
	elif String(it.get("ai_ally", "")) != "":
		st_text = tr("dipl.ai_ally") % String(it["ai_ally"])
		st_icon = "handshake"
	elif rel == "ally":
		st_text = tr("dipl.ally")
	# the icon on a disc of the relation's colour, as on the card's corner (a white dove on bare paper did not read)
	var st_fill := Kit.face_of("go" if st_icon == "handshake" else String(look[1]))
	var sc := _paper_chip(box, Vector2.ZERO, st_icon, st_text, cw * 0.58, st_fill)
	sc.name = "status"
	sc.position = Vector2(bx, 208)
	var vi := roundi(v)
	var oc := Kit.chip(box, Vector2.ZERO, "", tr("dipl.opinion") % _signed(vi), "owner",
		Kit.face_of("go") if vi > 0 else (Kit.face_of("war") if vi < 0 else Kit.SLATE_FILL), {"max_w": cw - sc.size.x - 12.0})
	oc.name = "opinion"
	oc.position = Vector2(sc.position.x + sc.size.x + 12.0, sc.position.y + (sc.size.y - oc.size.y) * 0.5)
	# the actions: two per row, the last one alone in the middle
	var bw := (w - 64.0 - 16.0) * 0.5
	for i in acts.size():
		var a: Dictionary = acts[i]
		var col := i % 2
		var row := i / 2
		var x := 32.0 + col * (bw + 16.0)
		if i == acts.size() - 1 and col == 0:
			x = (w - bw) * 0.5
		var kind := String(a["kind"])
		# the gift is go here as on the card (one role per action); the treaties are secondary info
		var b := Kit.button(box, Rect2(x, grid_y + row * 104.0, bw, 88), "go" if kind == "gift" else "info", String(a["cap"]),
			{"icon": String(a["icon"]), "price": a.get("price", []), "enabled": bool(a["on"]), "size": "M"})
		b.name = "act_" + kind
		var why := String(a["why"])
		if why != "":
			b.denied.connect(func(): Kit.tooltip(b, String(a["cap"]), why))
		if String(a.get("short", "")) != "":
			var short_why := String(a["short"])
			b.cb = func():
				Kit.shake(b)
				Kit.tooltip(b, String(a["cap"]), short_why)
		else:
			b.cb = func():
				close_modal()
				diplomacy_action.emit(id, kind)
	# the footer: one action in the middle
	var fr := Rect2((w - 480.0) * 0.5, foot_y, 480, 116)
	if rel == "war":
		var pcb := _peace_cb(it)
		var pb := Kit.button(box, fr, "go", tr("dipl.separate") if bool(it.get("separate", false)) else tr("dipl.peace"),
			{"icon": "dove", "size": "L"})
		pb.name = "peace"
		pb.cb = func():
			close_modal()
			pcb.call()
	else:
		var can_war := bool(it.get("can_war", false))
		var why_w := ""
		if not can_war:
			why_w = String(it.get("status", "")) if rel in ["pact", "truce"] else tr("dipl.war_busy")
		var wb := Kit.button(box, fr, "war", tr("dipl.declare"), {"icon": "swords", "size": "L", "enabled": can_war})
		wb.name = "declare"
		wb.cb = func():
			close_modal()
			diplomacy_action.emit(id, "war")
		if why_w != "":
			wb.denied.connect(func(): Kit.tooltip(wb, tr("dipl.declare"), why_w))


## «Тревога соседей» (canon §10.8, §6 Соседи), the first card: the horn on paper, the threat in per cent with a red
## bar; a tap on the card says what the threat means now, «i» how it grows and falls (the rules).
func _alarm_card(it: Dictionary) -> Control:
	var pct := int(it.get("pct", 0))
	var rules := tr("alarm.hint")
	var line := String(it.get("line", ""))
	var stat := {"text": "%d%%" % mini(pct, 999), "bar_frac": clampf(pct / 100.0, 0.0, 1.0), "bar_role": "war"}
	# while a coalition forms (alarm.forming: «… · 3ч 12м»), its countdown is the most urgent thing: the hourglass
	# and the time take the stat line over the threat bar; the per cent goes to the tooltip
	var fmt := tr("alarm.forming")
	var head := fmt.left(fmt.find("%"))
	if head != "" and line.begins_with(head) and line.contains(" · "):
		stat["icon"] = "hourglass"
		stat["text"] = line.rsplit(" · ", true, 1)[1]
		line += "\n" + tr("alarm.title") + ": %d%%" % pct
	var opts := {"backdrop": "cream", "art_side": 72.0, "art_y": 38.0, "details": line,
		"chip": {"btn": {"caption": "i", "role": "info"}}, "stat": stat}
	var card := Kit.card(Kit.icon_tex("horn"), tr("alarm.title"), opts)
	if card.chip is Kit.KitButton:
		var ib := card.chip as Kit.KitButton
		ib.cb = func(): Kit.tooltip(ib, tr("alarm.title"), rules)  # its tail points at the «i»
	return card


## World tab (§6 Мир, canon §12.1): the chapter, the War Pass, the patent's daily gift, the calendar, the day's orders,
## the week's tasks and chests, the chapter stars. The chapter's number is the newest chapter whose stars are listed.
var _world_chapter := 1


func show_world(items: Array) -> void:
	var ch := 1
	for it in items:
		var id := String((it as Dictionary).get("id", ""))
		for k in [2, 3, 4]:
			if id.begins_with("c%d_" % k):
				ch = maxi(ch, k)
	_world_chapter = ch
	_fill_panel("w", items, func(it): return _chapter_card(it) if it["kind"] == "chapter" else _star_card(it))


## The chapter (§6 Мир): the hex on paper, «Глава I», its hexes on a bar; «Расширить» once the goal is met and the
## war is over; a check when it is done.
func _chapter_card(it: Dictionary) -> Control:
	var h := int(it.get("hexes", 0))
	var g := maxi(1, int(it.get("goal", 1)))
	var title := tr("world.chapter") % ROMAN[clampi(_world_chapter, 1, ROMAN.size() - 1)]
	var stat := {"icon": "hex_tile", "text": "%d/%d" % [mini(h, g), g], "bar_frac": clampf(float(h) / g, 0.0, 1.0), "bar_role": "info"}
	var opts := {"backdrop": "cream", "art_side": 80.0, "art_y": 40.0,
		"details": tr("world.hexes") % [h, g] + "\n" + tr("world.hint")}
	if bool(it.get("done", false)):
		stat.erase("bar_frac")
		stat["check"] = true
		opts["stat"] = stat
		opts["details"] = tr("world.chapter_done")
	elif bool(it.get("can_expand", false)):
		opts["cta"] = {"role": "go", "caption": tr("world.expand"), "icon": "globe", "cb": func(): world_action.emit("expand")}
	else:
		opts["stat"] = stat
	return Kit.card(Kit.icon_tex("hex_tile"), title, opts)


## «Задание · +40 ОП» (the orders, the week's tasks) → [the task, 40]; [title, 0] without that tail.
func _xp_split(title: String) -> Array:
	var i := title.rfind(" · +")
	if i < 0 or not title.ends_with(tr("pass.xp")):
		return [title, 0]
	var m := _num_re.search(title, i)
	return [title.left(i), int(m.get_string()) if m != null else 0]


## A short name for a card from a task's text: the part before «:» («Выход к морю: присоедините порт»), or after it
## when the part before is only a frame («За неделю: …»); without a «(…)» remark.
func _task_name(text: String, after := false) -> String:
	var t := text
	var c := t.find(": ")
	if c > 0:
		t = t.substr(c + 2) if after else t.left(c)
		if after and t.length() > 0:
			t = t.left(1).to_upper() + t.substr(1)
	var p := t.find(" (")
	if p > 0:
		t = t.left(p)
	return t.strip_edges()


## A World card's name: the task's `.short` key when it has one (its full text stays for the tooltip), else the
## task's text cut by _task_name. The orders and the week's tasks carry an index, not their code, in the id: the key
## is found among the sim's codes by its translated text.
func _short_title(id: String, text: String) -> String:
	var keys: Array = ["star." + id]
	if id.begins_with("order:"):
		keys = OrdersSim.POOL.map(func(t): return "order." + String(t[0]))
	elif id.begins_with("weekly:"):
		keys = WeeklySim.TASKS.map(func(t): return "weekly." + String(t[0]))
	for k in keys:
		if tr(String(k)) == text:
			var sk := String(k) + ".short"
			if tr(sk) != sk:
				return tr(sk)
			break
	return _task_name(text, id.begins_with("weekly:"))


## A card of the World tab other than the chapter (§6 Мир): its picture on paper, a short name, the progress on a
## bar or the reward; «Забрать» only when there is something to take; a check once taken. The War Pass and the
## calendar open their screens from the whole card; the others explain themselves in the tooltip.
func _star_card(it: Dictionary) -> Control:
	var id := String(it.get("id", ""))
	var prog := int(it.get("progress", 0))
	var need := maxi(1, int(it.get("need", 1)))
	var claimed := bool(it.get("claimed", false))
	var done := prog >= need
	var full := String(it.get("title", ""))
	var xs := _xp_split(full)
	var text := String(xs[0])
	var xp := int(xs[1])
	var claim_cb := func(): world_action.emit(id)
	var title := _short_title(id, text)
	var icon := "xp"
	var opts := {"backdrop": "cream", "art_side": 62.0, "art_y": 34.0}  # above a two-line name
	var tip := PackedStringArray([text])
	var progress := {"text": "%d/%d" % [mini(prog, need), need], "bar_frac": clampf(float(prog) / need, 0.0, 1.0), "bar_role": "info"}
	var stat := progress
	if id == "pass":
		icon = "medal"
		title = tr("world.pass")
		var lv := _num_re.search(full)
		opts["badge"] = lv.get_string() if lv != null else "1"
		stat = {"icon": "xp", "text": progress["text"], "bar_frac": progress["bar_frac"], "bar_role": "gold"}
		tip = PackedStringArray([full])
		opts["tap_cb"] = claim_cb
		done = false
	elif id == "calendar":
		icon = "calendar"
		title = tr("world.calendar")
		stat = {"text": tr("world.day") % prog}
		tip = PackedStringArray([full])
		opts["tap_cb"] = claim_cb
		done = bool(it.get("ready", false))
		claimed = false
		if done:
			opts["dot"] = "go"
	elif id == "patent_daily":
		icon = "charter"
		title = tr("world.patent")
		var n := _num_re.search(full)
		stat = {"icon": "raivite", "text": "+" + (n.get_string() if n != null else ""), "check": claimed}
	elif id.begins_with("order:") or id.begins_with("weekly:"):
		var weekly := id.begins_with("weekly:")
		icon = "medal_silver" if weekly else "orders"
		title = _short_title(id, text)
		if xp > 0:
			tip.append(tr("world.tip.xp") % xp)
		if bool(it.get("swap", false)):  # the day's one free swap of an order (08 §8.6)
			opts["chip"] = {"btn": {"icon": "swap", "role": "info"}}
			opts["chip_cb"] = func(): world_action.emit("swap:" + id)
	elif id == "orders_all":
		icon = "chest_wood"
	elif id.begins_with("weekly_chest:"):
		var step := int(id.get_slice(":", 1))
		icon = "chest_silver" if step > 0 else "chest_wood"
		title = tr("world.chest")
		opts["badge"] = str(step + 1)
	else:
		# a chapter star: the vector star, gold once reached
		icon = ""
		var holder := Control.new()
		holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
		holder.size = Vector2(172, 104)
		Kit.star(holder, Vector2(86, 32), 30.0, done or claimed)
		opts["art_node"] = holder
	if claimed:
		stat = stat.duplicate()
		stat.erase("bar_frac")
		stat["check"] = true
		if not stat.has("icon") and id != "patent_daily":
			stat["text"] = tr("world.claimed")
		opts["stat"] = stat
	elif done:
		opts["cta"] = {"role": "go", "caption": tr("ui.claim"), "cb": claim_cb}
	else:
		opts["stat"] = stat
	if not claimed and not (id in ["pass", "calendar", "patent_daily"]):
		tip.append(tr("world.tip.progress") % [mini(prog, need), need])
	opts["details"] = "\n".join(tip)
	return Kit.card(Kit.icon_tex(icon) if icon != "" else null, title, opts)


func hide_buildings() -> void:
	if _bpanel:
		_bpanel.visible = false
	_bkey = ""
	_bfam = ""


## The fallback picture of a building with no render (assets/ui/cards/bld_<type>.png) — never a tab's icon (castle,
## helmet, flask, handshake, globe).
const BUILDING_ICONS := {"residence": "crown", "barracks": "swords", "academy": "book", "warehouse": "crate",
	"infirmary": "shield", "convoy_yard": "cart", "market": "stall", "embassy": "seal", "quarters": "houses",
	"farm": "food", "mine": "metal", "port": "anchor", "military_base": "target"}
## The Development tab's art (§6 Развитие): what a line does — the ledger of taxes, the harvest's sack, the convoy's
## cart — on the blueprint; never its price's icon or the tab's flask.
const RESEARCH_ICONS := {"taxes": "book", "harvest": "food", "metallurgy": "metal", "infantry": "swords",
	"reserve": "shield", "drill": "target", "logistics": "cart", "cellars": "crate", "colonization": "pin",
	"thrift": "coins"}
## A line whose effect a render shows better than an icon: the harvest is the fields (its price is food, so the food
## sack would repeat the price; there is no plough render yet)
const RESEARCH_ART := {"harvest": "res://assets/ui/cards/tile_farm.png"}
const PRICE_ICON := {"gold": "coin", "food": "food", "metal": "metal", "oil": "barrel", "raivite": "raivite"}
const RES_ORDER: Array[String] = ["gold", "food", "metal", "oil"]

var stock_of := Callable()  ## res -> the player's stock (int); while unset, the HUD's plates are read back
var _num_re := RegEx.create_from_string("\\d+")


## The player's stock of a resource as [lowest, highest]: exact through `stock_of`, else read back from the HUD's
## plate (pill_of), where «12,4K» stands for 12 400–12 499; [-1, -1] when unknown.
func _stock(res: String) -> Array:
	if stock_of.is_valid():
		var v := int(stock_of.call(res))
		return [v, v]
	if pill_of.is_valid():
		var p: Variant = pill_of.call(res)
		if p is Kit.KitPill and (p as Kit.KitPill).value != null:
			return Kit.parse_num((p as Kit.KitPill).value.text)
	return [-1, -1]


## A card's price (§4.1, §4.4) as [[icon, number, short], …], the scarcest first — by the share of the stock each
## cost takes — so the button's two places (one when compact, with «+1») show what holds the player back.
## `short_res`, the resource the game's reason names, is short for sure; while something stops the action
## (`blocked`), another one is short only when its cost surely exceeds the stock read back.
func _price_items(cost: Dictionary, short_res := "", blocked := false) -> Array:
	var rows: Array = []
	for r in cost:
		var n := int(cost[r])
		if n <= 0:
			continue
		var st := _stock(String(r))
		var ratio := float(n) / maxf(1.0, float(st[0])) if int(st[0]) >= 0 else 0.0
		var short := String(r) == short_res or (blocked and int(st[1]) >= 0 and n > int(st[1]))
		rows.append({"r": String(r), "n": n, "ratio": ratio, "short": short})
	rows.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if bool(a["short"]) != bool(b["short"]):
			return bool(a["short"])
		if not is_equal_approx(float(a["ratio"]), float(b["ratio"])):
			return float(a["ratio"]) > float(b["ratio"])
		return RES_ORDER.find(String(a["r"])) < RES_ORDER.find(String(b["r"])))
	var out: Array = []
	for x in rows:
		out.append([PRICE_ICON.get(x["r"], "coin"), fmt_num(int(x["n"])), bool(x["short"])])
	return out


## «300 золота, 100 металла» — the whole price in words for a tooltip.
func _cost_words(cost: Dictionary) -> String:
	var parts := PackedStringArray()
	for r in RES_ORDER + ["raivite"]:
		if int(cost.get(r, 0)) > 0:
			parts.append("%s %s" % [fmt_num(int(cost[r])), tr("res.gen." + r)])
	return ", ".join(parts)


## What stops an upgrade or a research (the game passes its reason translated): [kind, arg] — "short" (arg: the
## resource missing), "level" (the development level needed), "academy" (its level), "hexes" (how many), "chapter",
## "max", "wait" (builders, the academy or the treasury are busy), or "" when nothing does.
func _reason_kind(reason: String) -> Array:
	if reason == "":
		return ["", ""]
	for r in RES_ORDER:
		if reason == L.t("err.not_enough|res.gen." + r):
			return ["short", r]
	if reason == L.t("err.max_level") or reason == L.t("err.max"):
		return ["max", ""]
	var m := _num_re.search(reason)
	if m != null:
		var n := m.get_string()
		for k in [["err.need_residence", "level"], ["err.unlock_dl", "level"], ["err.need_academy", "academy"],
				["err.need_hexes", "hexes"], ["err.chapter_locked", "chapter"]]:
			if reason == L.t(String(k[0]) + "|" + n):
				return [k[1], n]
	return ["wait", ""]


const ROMAN: Array[String] = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII"]


## A building or a research line (§6 Здания, Развитие) on Kit.card: the building's render on the sky (its icon
## when there is none) or the line's effect on the blueprint, the level on the hex. The button: the price (two
## places at most, the scarcest first; a short one red, its tap says what is missing); while it builds — the time
## left (a free «Готово» under 5 min), its tap speeds it up; blocked — lock with a short reason («УР2»), its tap
## gives the whole one. The time, the full price and the effect are in the card's tooltip.
func _building_card(it: Dictionary) -> Control:
	if it.has("market"):
		return _market_card(it)
	var line := String(it.get("line", ""))
	var research := line != ""
	var typ := String(it.get("type", ""))
	var busy: bool = it["busy"]
	var lvl := int(it["level"])
	var cost: Dictionary = it.get("cost", {})
	var reason := String(it.get("reason", ""))
	var rk := _reason_kind(reason)
	var id: int = it["id"]
	var opts := {"badge": str(lvl)}
	var tex: Texture2D = null
	if research:
		opts["backdrop"] = "blueprint"
		var rart := String(RESEARCH_ART.get(line, ""))
		tex = load(rart) if rart != "" and ResourceLoader.exists(rart) else Kit.icon_tex(String(RESEARCH_ICONS.get(line, "book")))
		opts["art_side"] = 72.0
		opts["art_y"] = 40.0
	else:
		var pic := "res://assets/ui/cards/bld_%s.png" % typ
		if ResourceLoader.exists(pic):
			tex = load(pic)
		else:
			tex = Kit.icon_tex(String(BUILDING_ICONS.get(typ, "houses")))
			opts["art_side"] = 72.0
			opts["art_y"] = 40.0
	# the tooltip (§4.11, 4 lines at most): the effect, the level, the time and the price; while busy the time left,
	# the speed-up and the blueprints
	var tip := PackedStringArray()
	if research:
		tip.append(tr("rs." + line + ".desc"))  # what a level gives (Research.LINES[line].desc)
	if not busy:  # while it builds the time left and the speed-up matter more than the level
		tip.append(tr("bld.level") % [lvl, int(it["max"])])
	if busy:
		var sp := int(it.get("speed", 0))
		tip.append(tr("bld.tip.left") % fmt_time(int(it["left"])))
		if sp == 0:
			tip.append(tr("bld.free"))
		elif int(it.get("stock", 0)) > 0:
			tip.append(tr("bld.stock") % int(it["stock"]))
		else:
			tip.append(tr("bld.tip.speed") % sp)
		if int(it.get("bp", 0)) > 0:
			tip.append(tr("bld.blueprint") % int(it["bp"]))
	elif not cost.is_empty() and rk[0] != "max":
		tip.append(tr("bld.tip.time") % fmt_time(int(it.get("seconds", 0))))
		tip.append(tr("bld.tip.cost") % _cost_words(cost))
	if reason != "" and rk[0] != "short" and not busy:
		tip.append(reason)
	opts["details"] = "\n".join(tip.slice(0, 4))
	if busy:
		var speed_cb := func():
			if research:
				research_speedup.emit(line)
			else:
				building_speedup.emit(id)
		var sp := int(it.get("speed", 0))
		if sp == 0:
			opts["cta"] = {"role": "go", "caption": tr("ui.finish"), "icon": "lightning", "cb": speed_cb}
		elif int(it.get("stock", 0)) > 0:
			# the speed-up stock from cases pays first: the tap is free, the time left on the info face (§4.4)
			opts["cta"] = {"role": "info", "caption": fmt_time(int(it["left"])), "icon": "hourglass", "cb": speed_cb}
		else:
			# the tap spends Raivites at once: gold with the lightning and their price on a plate (§1 rule 7, §4.1); the
			# time left moves onto the art, over the name (it never fits beside the price); not enough — the number
			# red, the tap says so and spends nothing
			var rv := _stock("raivite")
			var short := int(rv[1]) >= 0 and sp > int(rv[1])
			opts["timer"] = fmt_time(int(it["left"]))
			var ct := {"role": "gold", "icon": "lightning", "cb": speed_cb, "price": [["raivite", fmt_num(sp), short]]}
			if short:
				ct["short_reason"] = L.t("err.not_enough|res.gen.raivite")
			opts["cta"] = ct
		var bp := int(it.get("bp", 0))
		if bp > 0:
			# «Применить чертёж» (07 §6.1): a round go button with the blueprint on the chip's corner — a free item
			# speeds the research up — and the stock on a plate under it («×3»; «−10% each» is in the tooltip)
			opts["chip"] = {"btn": {"icon": "blueprint", "role": "go"}, "count": "×%d" % bp}
			opts["chip_cb"] = func(): research_speedup.emit("bp:" + line)
	elif rk[0] == "max" or cost.is_empty():
		opts["stat"] = {"text": tr("err.max"), "check": true}
	elif rk[0] in ["level", "academy", "chapter"]:
		var cap := tr("dl.short") % int(rk[1])
		if rk[0] == "academy":
			cap = tr("bld.academy")
		elif rk[0] == "chapter":
			cap = tr("world.chapter") % ROMAN[clampi(int(rk[1]), 0, ROMAN.size() - 1)]
		if research and lvl == 0 and rk[0] == "level":
			# a line the realm has not reached yet: closed (§4.4) — the dark art, the lock and «УР3»
			opts["locked"] = true
			opts["lock_caption"] = cap
			opts["reason"] = reason
		else:
			opts["cta"] = {"role": "lock", "icon": "lock", "caption": cap, "enabled": false, "reason": reason}
	elif rk[0] == "hexes":
		opts["cta"] = {"role": "lock", "icon": "hex_tile", "caption": String(rk[1]), "enabled": false, "reason": reason}
	else:
		var go_cb := func():
			if research:
				research_start.emit(line)
			else:
				building_upgrade.emit(id)
		var ct := {"role": "go", "caption": tr("bld.research") if research else "", "cb": go_cb,
			"price": _price_items(cost, String(rk[1]) if rk[0] == "short" else "", reason != "")}
		if rk[0] == "short":
			ct["short_reason"] = reason  # the role stays: the scarce number turns red, the tap says what is missing
		elif rk[0] == "wait":
			ct["enabled"] = false  # builders, the academy or the treasury are busy: grey, the tap says which
			ct["reason"] = reason
		opts["cta"] = ct
	return Kit.card(tex, String(it["name"]), opts)


## The Buildings tab's first card once the Market stands (05 §13): the stall on paper, «Обмен» opens the Market;
## the rate is in the tooltip.
func _market_card(it: Dictionary) -> Control:
	return Kit.card(Kit.icon_tex("stall"), String(it.get("name", tr("bld.market"))), {"backdrop": "cream",
		"art_side": 76.0, "art_y": 40.0, "details": tr("market.tip") % _rate_txt(int(it["rate"])),
		"cta": {"role": "info", "caption": tr("market.open"), "icon": "swap", "cb": func(): market_open.emit()}})


# ------------------------------------------------------------------ coach (FTUE, canon §14.3)

var _coach: Control
var _coach_lbl: Label
var _coach_ring: Panel
var _coach_arrow: Label
var _coach_target := Vector2(-1, -1)
var _ghost_from := Vector2(-1, -1)
var _ghost_to := Vector2(-1, -1)
var _ghost_dot: Panel
var _coach_t := 0.0
## Rects (on the 1672 canvas) of the buttons the coach points at — the big button, the status button: framed
## instead of circled.
const COACH_FRAMES := [BIG_RECT, STATUS_RECT]


func _build_coach() -> void:
	_coach = Control.new()
	_coach.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_coach.z_index = 40
	root.add_child(_coach)
	var box := _panel(_coach, Rect2(108, 166, 612, 96), _style(Color(0.98, 0.93, 0.78, 0.97), 16, Color(0.75, 0.55, 0.2), 3), Control.MOUSE_FILTER_IGNORE)
	_coach_lbl = _label("", 23, Color(0.22, 0.14, 0.05), false)
	_coach_lbl.position = Vector2(18, 10)
	_coach_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD
	_coach_lbl.custom_minimum_size = Vector2(576, 0)  # autowrap needs a fixed width
	_coach_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	box.add_child(_coach_lbl)
	var ring_sb := _style(Color(1, 1, 1, 0.0), 60, Color(1.0, 0.85, 0.3), 6)
	ring_sb.shadow_size = 0  # through the empty middle the shadow darkened the very button it points at
	_coach_ring = _panel(_coach, Rect2(0, 0, 120, 120), ring_sb, Control.MOUSE_FILTER_IGNORE)
	_coach_arrow = _label("▼", 56, Color(1.0, 0.85, 0.3))
	_coach.add_child(_coach_arrow)
	_ghost_dot = _panel(_coach, Rect2(0, 0, 64, 64), _style(Color(1, 1, 1, 0.7), 32, Color(1.0, 0.85, 0.3), 5), Control.MOUSE_FILTER_IGNORE)
	_coach.visible = false


## Shows an advisor line; `target` (screen px) gets a pulsing ring and a bouncing arrow.
func coach(text: String, target := Vector2(-1, -1)) -> void:
	if _coach == null:
		_build_coach()
	_coach.visible = true
	_coach_lbl.text = text
	_coach_target = target
	_ghost_from = Vector2(-1, -1)


func coach_target(target: Vector2) -> void:
	_coach_target = target


## Ghost finger dragging from → to (screen px), looping; call every frame while the camera moves.
func coach_ghost(from: Vector2, to: Vector2) -> void:
	_ghost_from = from
	_ghost_to = to


func coach_hide() -> void:
	if _coach:
		_coach.visible = false


func _process_coach(delta: float) -> void:
	if _coach == null or not _coach.visible:
		return
	_coach_t += delta
	var has_t := _coach_target.x >= 0
	_coach_ring.visible = has_t
	_coach_arrow.visible = has_t
	if has_t:
		var k := 1.0 + 0.12 * sin(_coach_t * 6.0)
		var sb := _coach_ring.get_theme_stylebox("panel") as StyleBoxFlat
		# targets given on the 1672 canvas inside the bottom band (tabs, cards, big button) follow the bottom group
		# down to the visible bottom on a tall screen
		var dy := _bottom.position.y
		var tgt := _coach_target + Vector2(0, dy if _coach_target.y >= VH - 332.0 else 0.0)
		var frame := Rect2()
		for f in COACH_FRAMES:
			if (f as Rect2).has_point(_coach_target):
				frame = Rect2((f as Rect2).position + Vector2(0, dy), (f as Rect2).size)
		if frame.size != Vector2.ZERO:  # a button: a pulsing frame around it, not a circle across its label
			var g := 8.0 + 6.0 * (k - 1.0) / 0.12
			_coach_ring.position = frame.position - Vector2(g, g)
			_coach_ring.size = frame.size + Vector2(g, g) * 2.0
			sb.set_corner_radius_all(22)
		else:
			_coach_ring.size = Vector2(120, 120) * k
			_coach_ring.position = tgt - _coach_ring.size / 2
			sb.set_corner_radius_all(int(60 * k))
		_coach_arrow.position = tgt + Vector2(-20, -150 + 14 * sin(_coach_t * 5.0))
	var has_g := _ghost_from.x >= 0
	_ghost_dot.visible = has_g
	if has_g:
		var u := fmod(_coach_t, 1.6) / 1.2
		var e := clampf(u, 0.0, 1.0)
		e = e * e * (3.0 - 2.0 * e)
		_ghost_dot.position = _ghost_from.lerp(_ghost_to, e) - Vector2(32, 32)
		_ghost_dot.modulate.a = 1.0 if u <= 1.05 else 0.35


var _toast_nodes: Array = []


## Short message under the top bar; a new toast replaces the one still showing.
func toast(text: String) -> void:
	for n in _toast_nodes:
		if is_instance_valid(n):
			(n as Node).queue_free()
	_toast_nodes.clear()
	var l := _label(text, 24)
	l.position = Vector2(40, 300)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.autowrap_mode = TextServer.AUTOWRAP_WORD
	l.custom_minimum_size = Vector2(VW - 80, 0)  # autowrap needs a fixed width
	var lines_h := font_bold.get_multiline_string_size(text, HORIZONTAL_ALIGNMENT_CENTER, VW - 80, 24).y
	var bg := _panel(root, Rect2(30, 290, VW - 60, maxf(70.0, lines_h + 24.0)), _style(Color(0.05, 0.08, 0.14, 0.92), 14), Control.MOUSE_FILTER_IGNORE)
	root.add_child(l)
	_toast_nodes = [bg, l]
	var tw := bg.create_tween()  # dies with the node when a newer toast replaces it
	tw.tween_interval(2.0)
	tw.tween_property(l, "modulate:a", 0.0, 0.4)
	tw.parallel().tween_property(bg, "modulate:a", 0.0, 0.4)
	tw.tween_callback(func(): l.queue_free(); bg.queue_free())


func _process(delta: float) -> void:
	_process_coach(delta)
