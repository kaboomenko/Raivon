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
const CARD_ART := {"attack": "⚔", "breakthrough": "➶", "airstrike": "✈", "encircle": "◎", "defense": "⛨", "corps": "⚑", "landing": "⇓", "missile": "✦"}
const CARD_ORDER := ["attack", "breakthrough", "airstrike", "encircle", "defense"]
var _locked := {}  # card -> DL it opens at
var _hand_order: Array = []
const CARD_NAME_KEYS := {"attack": "card.attack", "breakthrough": "card.breakthrough", "airstrike": "card.airstrike", "encircle": "card.encircle", "defense": "card.defense", "corps": "card.corps", "landing": "card.landing", "missile": "card.missile"}
const L := preload("res://scripts/l10n.gd")
const CmdPortrait := preload("res://scripts/cmd_portrait.gd")
const HudScript := preload("res://scripts/hud.gd")
const FlagView := preload("res://scripts/flag_view.gd")
const Kit := preload("res://scripts/ui_kit.gd")

var font_bold: Font
var root: Control
var _control_bar: Control
var _control_fill: Panel
var _control_lbl: Label
var _control_lbl2: Label
var _score_lbl: Label
var _laststand: Label
var _war_flags: Array = []  # [player FlagView, enemy FlagView] at the ends of the control bar (concept panel 7)
var _war_swords: Label
var _battle: Control
var _energy_lbl: Label
var _energy_segs: Array = []
var _cards := {}
var _card_names := {}  # card -> name Label (re-translated on a language switch)
var _timer_lbl: Label
var _action: Control
var _action_lbl: Label
var _action_sub: Label
var _action_kind := ""
var _action2: Control
var _action2_lbl: Label
var _action2_kind := ""
var _modal: Control
var _bottom: Control  # the bottom group (card row, battle hand, status / big buttons): moved to VB − 1672 (§3.1)
var _drag_card := ""
var _ghost: Label
var _seal_t := -1.0
var _seal_prog: Panel


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
	_ghost = _label("", 64)
	_ghost.visible = false
	_ghost.z_index = 50
	root.add_child(_ghost)
	get_viewport().size_changed.connect(_anchor_bottom)
	_anchor_bottom()


## The bottom group follows the visible bottom (VB, §3.1) like the HUD's tabs and tray under it.
func _anchor_bottom() -> void:
	_bottom.position.y = Kit.vb(self) - VH


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


# ------------------------------------------------------------------ control bar (war)

func _build_control_bar() -> void:
	_control_bar = Control.new()
	_control_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_control_bar)
	_panel(_control_bar, Rect2(108, 84, 612, 74), _style(PANEL, 12), Control.MOUSE_FILTER_IGNORE)
	var bar := _panel(_control_bar, Rect2(156, 94, 516, 30), _style(Color(0.85, 0.15, 0.13), 14, Color(1, 1, 1, 0.9), 2), Control.MOUSE_FILTER_IGNORE)
	_control_fill = _panel(bar, Rect2(2, 2, 256, 26), _style(Color(0.18, 0.45, 1.0), 12, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	_control_lbl = _at(_label("50%", 18), _control_bar, Vector2(168, 96)) as Label
	_control_lbl2 = _at(_label("50%", 18), _control_bar, Vector2(616, 96)) as Label
	# the two sides' flags at the ends and crossed swords on the front line, as on the concept's Last Stand panel
	for x in [116.0, 678.0]:
		var fv := FlagView.new(FlagView.DEFAULT)
		fv.position = Vector2(x, 90)
		fv.size = Vector2(32, 40)
		fv.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_control_bar.add_child(fv)
		_war_flags.append(fv)
	_war_swords = _at(_label("⚔", 26), _control_bar, Vector2(400, 90), Vector2(32, 34)) as Label
	_war_swords.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_score_lbl = _at(_label(tr("ui.war_score_zero"), 15, MUTED, false), _control_bar, Vector2(126, 128)) as Label
	_laststand = _at(_label(tr("ui.last_stand"), 17, Color(1, 0.4, 0.35)), _control_bar, Vector2(350, 128)) as Label
	_control_bar.visible = false


func set_control(score: float, control: int, enemy: String, visible_bar: bool, flags: Array = []) -> void:
	_control_bar.visible = visible_bar
	if not visible_bar:
		return
	_control_fill.size.x = 512.0 * clampf(control / 100.0, 0.0, 1.0)
	_war_swords.position.x = 158.0 + _control_fill.size.x - 16.0
	for i in mini(flags.size(), _war_flags.size()):
		var fv: Control = _war_flags[i]
		if fv.get("flag") != flags[i]:
			fv.set("flag", flags[i])
			fv.queue_redraw()
	_control_lbl.text = "%d%%" % control
	_control_lbl2.text = "%d%%" % (100 - control)
	_score_lbl.text = tr("ui.war_status") % [enemy, score]
	_laststand.visible = control <= 30


# ------------------------------------------------------------------ battle hand

func _build_battle() -> void:
	_battle = Control.new()
	_battle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bottom.add_child(_battle)
	# up to y 1364: the hand covers the HUD's folder tabs (they reach 1370 with a dot) until s06 rebuilds this tray
	_panel(_battle, Rect2(0, VH - 308, 640, 308), _style(PANEL, 16))
	_energy_lbl = _at(_label("5", 26), _battle, Vector2(26, VH - 262)) as Label
	var orb := _panel(_battle, Rect2(14, VH - 268, 46, 46), _style(Color(0.55, 0.3, 0.95), 23, Color(1, 1, 1, 0.9), 3), Control.MOUSE_FILTER_IGNORE)
	_battle.move_child(orb, _battle.get_child_count() - 2)
	for i in 10:
		var seg := _panel(_battle, Rect2(72 + i * 55, VH - 256, 50, 20), _style(Color(1, 1, 1, 0.1), 6, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
		var fill := _panel(seg, Rect2(0, 0, 50, 20), _style(Color(0.62, 0.38, 1.0), 6, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
		_energy_segs.append(fill)
	_build_cards(CARD_ORDER)
	# «Союзный корпус»: a compact extra card above the hand, shown only with an ally in the war
	var cp := _panel(_battle, Rect2(512, VH - 352, 116, 120), _style(Color(0.14, 0.24, 0.2), 14, Color(0.5, 1.0, 0.7, 0.9), 2))
	cp.gui_input.connect(_on_card_input.bind("corps"))
	var ca := _label(CARD_ART["corps"], 40)
	ca.position = Vector2(0, 4)
	ca.size = Vector2(116, 50)
	ca.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cp.add_child(ca)
	var cn := _label(_card_name("corps"), 15)
	_fit(cn, 15, 110.0)
	cn.position = Vector2(0, 54)
	cn.size = Vector2(116, 22)
	cn.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cp.add_child(cn)
	_card_names["corps"] = cn
	var cc := _panel(cp, Rect2(43, 80, 30, 30), _style(Color(0.55, 0.3, 0.95), 15, Color(1, 1, 1, 0.9), 2), Control.MOUSE_FILTER_IGNORE)
	var ccl := _label("3", 16)
	ccl.size = Vector2(30, 30)
	ccl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ccl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	cc.add_child(ccl)
	var ccd := _label("", 26)
	ccd.name = "cd"
	ccd.size = Vector2(116, 60)
	ccd.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cp.add_child(ccd)
	cp.visible = false
	_cards["corps"] = cp
	_battle.visible = false


## The hand's card row (canon §9.9: «Атака» + 4 slots, 5 from DL6): the cards share the 628 px row.
func _build_cards(order: Array) -> void:
	for c in _cards.keys():
		if c != "corps":
			(_cards[c] as Control).queue_free()
			_cards.erase(c)
			_card_names.erase(c)
	_hand_order = order.duplicate()
	var n := order.size()
	var step := 628.0 / n
	var w := step - 9.0
	for i in n:
		var card: String = order[i]
		var x := 12.0 + i * step
		var p := _panel(_battle, Rect2(x, VH - 222, w, 196), _style(Color(0.12, 0.17, 0.28), 14, Color(0.5, 0.62, 0.85, 0.8), 2))
		p.gui_input.connect(_on_card_input.bind(card))
		var pic := "res://assets/ui/cards/%s.png" % card
		var name_y := 94.0
		if ResourceLoader.exists(pic):
			# the painted scene of the card (tools/blender/card_art.py), as on the «War Cards» concept panel
			var tr_ := TextureRect.new()
			tr_.texture = load(pic)
			tr_.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			tr_.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
			tr_.position = Vector2(5, 5)
			tr_.size = Vector2(w - 10, 112)
			tr_.clip_contents = true
			tr_.mouse_filter = Control.MOUSE_FILTER_IGNORE
			p.add_child(tr_)
			name_y = 118.0
		else:
			var art := _label(CARD_ART[card], 54 if n <= 5 else 46)
			art.position = Vector2(0, 14)
			art.size = Vector2(w, 70)
			art.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			p.add_child(art)
		var nm := _label(_card_name(card), 17)
		_fit(nm, 17, w - 6.0)
		nm.position = Vector2(0, name_y)
		nm.size = Vector2(w, 24)
		nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		p.add_child(nm)
		_card_names[card] = nm
		var cost := _panel(p, Rect2(w / 2.0 - 20.0, 146 if name_y > 100.0 else 138, 40, 40), _style(Color(0.55, 0.3, 0.95), 20, Color(1, 1, 1, 0.9), 3), Control.MOUSE_FILTER_IGNORE)
		var cl := _label(str(_card_cost(card)), 20)
		cl.position = Vector2(0, 5)
		cl.size = Vector2(40, 30)
		cl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cost.add_child(cl)
		var cd := _label("", 34)
		cd.name = "cd"
		cd.position = Vector2(0, 40)
		cd.size = Vector2(w, 60)
		cd.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		p.add_child(cd)
		_cards[card] = p


## The offensive's hand in order (cards not open yet included, shown locked); rebuilt only when it changes.
func set_hand(order: Array) -> void:
	if order != _hand_order:
		_build_cards(order)
		set_locked(_locked)


## Cards not open yet: {card: DL it opens at} — shown greyed with «УР N» in place of the name; a tap explains.
func set_locked(locked: Dictionary) -> void:
	_locked = locked
	for c in _card_names:
		var nm: Label = _card_names[c]
		nm.text = tr("dl.short") % int(locked[c]) if locked.has(c) else _card_name(c)


## Shows the «Союзный корпус» card when an ally fights in this war and it was not played yet.
func set_corps(available: bool) -> void:
	if _cards.has("corps"):
		(_cards["corps"] as Control).visible = available


func _card_name(c: String) -> String:
	return tr(String(CARD_NAME_KEYS[c]))


## Static labels built once in _ready, re-applied after a language switch.
func retranslate() -> void:
	_laststand.text = tr("ui.last_stand")
	for c in _card_names:
		var nm: Label = _card_names[c]
		nm.text = tr("dl.short") % int(_locked[c]) if _locked.has(c) else _card_name(c)
		_fit(nm, 17, 110.0)


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
		var f: Panel = _energy_segs[i]
		f.size.x = 50.0 if i < pts else (50.0 * frac if i == pts else 0.0)
	for c in _cards:
		var p: Panel = _cards[c]
		var cd: int = cooldowns.get(c, 0)
		if _locked.has(c):
			p.modulate = Color(0.6, 0.6, 0.6, 0.8)
			(p.get_node("cd") as Label).text = ""  # greyed, «УР N» in place of the name
			continue
		p.modulate = Color(1, 1, 1, 0.45 if (pts < _card_cost(c) or cd > 0) else 1.0)
		(p.get_node("cd") as Label).text = str(int(ceil(cd / 10.0))) if cd > 0 else ""
	set_action("timer", "%d:%02d" % [seconds_left / 60, seconds_left % 60], tr("ui.final_rush") if rush else tr("ui.offensive_left"), Color(0.5, 0.2, 0.2) if rush else Color(0.2, 0.25, 0.4))


func _on_card_input(event: InputEvent, card: String) -> void:
	if _locked.has(card):
		if event is InputEventScreenTouch or event is InputEventMouseButton:
			if event.pressed:
				toast(tr("err.unlock_dl") % int(_locked[card]))
		return
	if event is InputEventScreenTouch or event is InputEventMouseButton:
		var pressed: bool = event.pressed
		var pos: Vector2 = (event as InputEventScreenTouch).position if event is InputEventScreenTouch else (event as InputEventMouseButton).position
		pos += (_cards[card] as Control).global_position
		if pressed:
			_drag_card = card
			_ghost.text = CARD_ART[card]
			_ghost.visible = true
			_ghost.position = pos - Vector2(30, 90)
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
		_ghost.position = pos - Vector2(30, 90)
		if released:
			var c := _drag_card
			_drag_card = ""
			_ghost.visible = false
			card_drag.emit(c, pos, false)
			if pos.y < _bottom.position.y + VH - 280:  # above the hand (it moves with the bottom group)
				card_drop.emit(c, pos)
		else:
			card_drag.emit(_drag_card, pos, true)
		get_viewport().set_input_as_handled()


# ------------------------------------------------------------------ action buttons (bottom-right)

func _build_action() -> void:
	_action = _panel(_bottom, Rect2(652, VH - 276, 280, 140), _style(PANEL, 16))
	_action2 = _panel(_bottom, Rect2(660, VH - 122, 266, 92), _style(Color(0.13, 0.4, 0.9), 16, Color(0.55, 0.75, 1.0), 3))
	_action_lbl = _label("", 34)
	_action_lbl.position = Vector2(0, 22)
	_action_lbl.size = Vector2(280, 50)
	_action_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_action.add_child(_action_lbl)
	_action_sub = _label("", 18, MUTED, false)
	_action_sub.position = Vector2(0, 80)
	_action_sub.size = Vector2(280, 40)
	_action_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_action.add_child(_action_sub)
	_action2_lbl = _label("", 26)
	_action2_lbl.position = Vector2(0, 26)
	_action2_lbl.size = Vector2(266, 40)
	_action2_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_action2.add_child(_action2_lbl)
	_action.gui_input.connect(func(e): if _is_tap(e): action_pressed.emit(_action_kind))
	_action2.gui_input.connect(func(e): if _is_tap(e): action_pressed.emit(_action2_kind))
	_action.visible = false
	_action2.visible = false


func _is_tap(e: InputEvent) -> bool:
	return (e is InputEventScreenTouch and not e.pressed) or (e is InputEventMouseButton and not e.pressed and e.button_index == MOUSE_BUTTON_LEFT)


## Upper box (status/secondary) — kind "" hides it.
func set_action(kind: String, title: String, sub := "", bg := PANEL) -> void:
	_action_kind = kind
	_action.visible = kind != ""
	_action_lbl.text = title
	_action_sub.text = sub
	_fit(_action_lbl, 34, 264.0)
	_fit(_action_sub, 18, 264.0)
	_action.add_theme_stylebox_override("panel", _style(bg, 16))


## Big blue button — kind "" hides it (the HUD's own «Атаковать» shows through).
func set_primary(kind: String, title: String, color := Color(0.13, 0.4, 0.9), enabled := true) -> void:
	_action2_kind = kind if enabled else ""
	_action2.visible = kind != ""
	_action2_lbl.text = title
	if title.contains("\n"):  # two lines (e.g. «Наступление / на «Кремнёвые Бароны»»): each fitted to the width
		var f := _action2_lbl.get_theme_font("font")
		var fs := 22
		for line in title.split("\n"):
			while fs > 14 and f.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x > 250.0:
				fs -= 1
		_action2_lbl.add_theme_font_size_override("font_size", fs)
		_action2_lbl.position = Vector2(0, 10)
		_action2_lbl.size = Vector2(266, 72)
		_action2_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	else:
		_action2_lbl.position = Vector2(0, 26)
		_action2_lbl.size = Vector2(266, 40)
		_action2_lbl.vertical_alignment = VERTICAL_ALIGNMENT_TOP
		_fit(_action2_lbl, 26, 250.0)
	_action2.add_theme_stylebox_override("panel", _style(color, 16, Color(1, 1, 1, 0.6), 3))
	_action2.modulate = Color(1, 1, 1, 1) if enabled else Color(0.72, 0.72, 0.72, 1)  # opaque: the HUD button below must not show through


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
func _modal_box(rect: Rect2, parchment := false, title := "", icon := "", role := "info", closable := false, blocking := false) -> Panel:
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
	if swap or DisplayServer.get_name() == "headless" or Kit.reduce_motion:
		dim.color.a = Kit.DIM_A
	else:
		dim.create_tween().tween_property(dim, "color:a", Kit.DIM_A, 0.14)
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


func show_result(stars: int, captured: int, lost: int, score: float, control: int, reason: String, on_continue: Callable, on_peace: Callable) -> void:
	var box := _modal_box(Rect2(70, 420, 800, 640))
	var t := _label(tr("result.title"), 36)
	_at(t, box, Vector2(40, 30))
	var st := ""
	for i in 3:
		st += "★" if i < stars else "☆"
	var sl := _label(st, 90, Color(1.0, 0.82, 0.25))
	sl.size = Vector2(800, 110)
	sl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_at(sl, box, Vector2(0, 90))
	var rows := [[tr("result.reason"), reason], [tr("result.captured"), str(captured)], [tr("result.lost"), str(lost)], [tr("result.score"), "%+.1f" % score], [tr("result.control"), "%d%%" % control]]
	for i in rows.size():
		_at(_label(rows[i][0], 24, MUTED, false), box, Vector2(60, 230 + i * 50))
		var v := _label(rows[i][1], 24)
		v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		_at(v, box, Vector2(440, 230 + i * 50), Vector2(300, 34))
	_at(_label(tr("result.note"), 19, MUTED, false), box, Vector2(60, 490))
	_button(box, Rect2(40, 540, 350, 76), tr("result.continue"), Color(0.25, 0.3, 0.42), on_continue)
	_button(box, Rect2(410, 540, 350, 76), tr("result.peace") % score, Color(0.2, 0.6, 0.3), on_peace)


const PLUNDER_NAMES := ["plunder.spare", "plunder.light", "plunder.medium", "plunder.heavy"]


func show_peace(enemy: String, budget: float, control: int, demands: Array, chosen: Dictionary, plunder := 1, portrait := "", plate := Color(0, 0, 0, 0)) -> void:
	var box := _modal_box(Rect2(30, 640, 881, 1010), true)
	var ink := Color(0.24, 0.16, 0.07)
	if portrait != "":
		_leader_seal(box, portrait, plate, Rect2(881 - 120, 14, 96, 116), "tired")  # the loser, worn out by the war
	_title(box, tr("peace.title") % enemy, 32, ink, Vector2(30, 24), "hands", false, 700.0 if portrait != "" else 820.0)
	var used := 0.0
	for d in demands:
		if chosen.has(d["id"]):
			used += d["cost"]
	_at(_label(tr("peace.points") % [used, budget, control], 22, ink, false), box, Vector2(30, 78))
	var ph := _label(tr("peace.hint"), 17, Color(0.42, 0.32, 0.18), false)
	_fit(ph, 17, 700.0 if portrait != "" else 820.0)
	_at(ph, box, Vector2(30, 112))
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(26, 150)
	scroll.size = Vector2(829, 548)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	var list := VBoxContainer.new()
	list.custom_minimum_size = Vector2(820, 0)
	list.add_theme_constant_override("separation", 6)
	scroll.add_child(list)
	for d in demands:
		var on: bool = chosen.has(d["id"])
		var fits: bool = on or used + float(d["cost"]) <= budget + 0.0001
		var row := Panel.new()
		row.custom_minimum_size = Vector2(820, 58)
		row.add_theme_stylebox_override("panel", _style(Color(0.3, 0.55, 0.3, 0.25) if on else Color(0.3, 0.2, 0.1, 0.08), 12, Color(0.25, 0.5, 0.25) if on else Color(0, 0, 0, 0), 3))
		row.mouse_filter = Control.MOUSE_FILTER_PASS
		row.modulate = Color(1, 1, 1, 1.0 if fits else 0.45)
		if d["kind"] == "pocket" or d["kind"] == "annex":
			_at(_label(("⭕" if d["kind"] == "pocket" else "⬢") + "  " + str(d["label"]), 21, ink, false), row, Vector2(16, 14))
		else:  # gold or a share of production: the 3D coin / the treaty scroll
			_at(_icon_rect("res://assets/ui/coin.png" if d["kind"] == "contribution" else "res://assets/ui/icons/hands.png", 34.0), row, Vector2(10, 10))
			_at(_label(str(d["label"]), 21, ink, false), row, Vector2(52, 14))
		var c := _label("%.1f" % d["cost"], 23, ink)
		c.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		_at(c, row, Vector2(590, 12), Vector2(210, 34))
		var id: String = d["id"]
		row.gui_input.connect(func(e): if _is_tap(e): demand_toggled.emit(id))
		list.add_child(row)
	# plunder: the winner's free right, level chosen by the player (canon §9.14)
	_at(_label(tr("peace.plunder"), 20, ink, false), box, Vector2(30, 722))
	for i in 4:
		var on := i == plunder
		var pb := _panel(box, Rect2(190 + i * 168, 712, 160, 56), _style(Color(0.55, 0.25, 0.12) if on and i > 0 else (Color(0.25, 0.5, 0.3) if on else Color(0.3, 0.2, 0.1, 0.12)), 12, Color(0.4, 0.25, 0.1, 0.6), 2))
		var pl := _label(tr(PLUNDER_NAMES[i]), 16, Color.WHITE if on else ink, on)
		pl.size = Vector2(160, 56)
		pl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		pl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		pb.add_child(pl)
		var lvl := i
		pb.gui_input.connect(func(e): if _is_tap(e): plunder_selected.emit(lvl))
	var seal := _panel(box, Rect2(26, 800, 829, 96), _style(Color(0.2, 0.55, 0.28), 16, Color(1, 1, 1, 0.6), 3))
	_seal_prog = _panel(seal, Rect2(0, 0, 0, 96), _style(Color(1, 1, 1, 0.3), 16, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	var sl := _label(tr("peace.seal"), 26)
	sl.size = Vector2(829, 96)
	sl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	seal.add_child(sl)
	seal.gui_input.connect(func(e):
		if e is InputEventScreenTouch or e is InputEventMouseButton:
			_seal_t = 0.0 if e.pressed else -1.0)
	_button(box, Rect2(26, 908, 829, 70), tr("peace.back"), Color(0.45, 0.35, 0.2), func(): action_pressed.emit("back_to_war"))


## Ceremony counters and rewards (canon §10.3 steps 4–5). Buttons appear early but accept taps only
## after `active_after` seconds (no ad may start before the ceremony ends, §14.10).
func show_ceremony_counters(lines: Array, on_done: Callable, on_double := Callable(), active_after := 3.0) -> void:
	close_modal()
	_modal = Control.new()
	_modal.size = Vector2(VW, VH)
	_modal.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_modal)
	var back := _panel(_modal, Rect2(40, 200, VW - 80, 60 + lines.size() * 64), _style(Color(0.04, 0.07, 0.13, 0.82), 22, Color(0.45, 0.65, 1.0, 0.8), 3), Control.MOUSE_FILTER_IGNORE)
	back.modulate.a = 0.0
	create_tween().tween_property(back, "modulate:a", 1.0, 0.3)
	for i in lines.size():
		var l := _label(lines[i], 40)
		l.size = Vector2(VW - 100, 60)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.position = Vector2(50, 230 + i * 64)
		_fit(l, 40 if i == 0 else 30, VW - 110.0)  # long lines (a chest's contents) shrink inside the panel
		l.modulate.a = 0.0
		l.scale = Vector2(1.0, 1.0)
		_modal.add_child(l)
		var tw := create_tween()
		tw.tween_interval(i * 0.25)
		tw.tween_property(l, "modulate:a", 1.0, 0.35)
	var shade := _panel(_modal, Rect2(0, VH - 290 if on_double.is_valid() else VH - 175, VW, 290), _style(Color(0.03, 0.05, 0.1, 0.9), 0, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	shade.modulate.a = 0.0
	var tw0 := create_tween()
	tw0.tween_interval(1.0)
	tw0.tween_property(shade, "modulate:a", 1.0, 0.3)
	var buttons: Array = []
	var gate := {"open": false}
	var done := func(): if gate["open"]: on_done.call()
	if on_double.is_valid():
		var dbl := func(): if gate["open"]: on_double.call()
		buttons.append(_button(_modal, Rect2(60, VH - 262, 821, 92), tr("ceremony.double"), Color(0.85, 0.55, 0.1), dbl))
	buttons.append(_button(_modal, Rect2(60, VH - 150, 821, 96), tr("ui.continue"), Color(0.13, 0.4, 0.9), done))
	for b in buttons:
		b.modulate.a = 0.0
		var tw2 := create_tween()
		tw2.tween_interval(1.2)
		tw2.tween_property(b, "modulate:a", 0.5, 0.3)
		tw2.tween_interval(maxf(0.0, active_after - 1.5))
		tw2.tween_property(b, "modulate:a", 1.0, 0.2)
	get_tree().create_timer(active_after).timeout.connect(func(): gate["open"] = true)


## Inbox (mail button): reports of raids, defenses, ultimatums. items: [{title, text, t (unix), read}];
## title / text are translation keys packed with their arguments (l10n.gd `pack`), shown in the current language.
func show_inbox(items: Array, now: int) -> void:
	var box := _modal_box(Rect2(50, 300, 841, 1060))
	_title(box, tr("inbox.title"), 34, TEXT, Vector2(36, 26), "mail")
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(24, 90)
	scroll.size = Vector2(793, 830)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	var col := VBoxContainer.new()
	col.custom_minimum_size = Vector2(780, 0)
	col.add_theme_constant_override("separation", 10)
	scroll.add_child(col)
	if items.is_empty():
		var empty := _label(tr("inbox.empty"), 22, MUTED, false)
		empty.autowrap_mode = TextServer.AUTOWRAP_WORD
		empty.custom_minimum_size = Vector2(760, 0)
		col.add_child(empty)
	for i in range(items.size() - 1, -1, -1):
		var it: Dictionary = items[i]
		var card := PanelContainer.new()
		card.add_theme_stylebox_override("panel", _style(Color(0.1, 0.15, 0.25) if it.get("read", false) else Color(0.14, 0.22, 0.38), 12, EDGE, 2))
		var v := VBoxContainer.new()
		card.add_child(v)
		var ago := maxi(0, now - int(it["t"]))
		var when := tr("time.just_now") if ago < 60 else (tr("time.min_ago") % (ago / 60) if ago < 3600 else tr("time.h_ago") % (ago / 3600))
		v.add_child(_label("%s  ·  %s" % [L.t(String(it["title"])), when], 22))
		var body := _label(L.t(String(it["text"])), 19, MUTED, false)
		body.autowrap_mode = TextServer.AUTOWRAP_WORD
		body.custom_minimum_size = Vector2(760, 0)
		v.add_child(body)
		col.add_child(card)
	_button(box, Rect2(24, 950, 793, 84), tr("ui.close"), Color(0.13, 0.4, 0.9), close_modal)


## «Военный пропуск» (canon §15.6): season header with the level bar, buy buttons (only where payments work), and
## the 40 levels — free and premium rewards side by side with their claim buttons.
## info: {season, days_left, level, xp_in_level, premium, elite, can_buy, price, price_elite,
##   rows: [{lvl, free_text, free_state, prem_text, prem_state}]} — state: "claim" | "claimed" | "locked"
func show_pass(info: Dictionary, on_claim: Callable, on_buy: Callable) -> void:
	var box := _modal_box(Rect2(30, 170, 881, 1330))
	_title(box, tr("pass.title") % int(info["season"]), 32, Color(1.0, 0.85, 0.4), Vector2(30, 22), "medal", true, 600.0)
	var dl := _label(tr("pass.days_left") % int(info["days_left"]), 18, MUTED, false)
	_at(dl, box, Vector2(30, 66))
	var lv := _label(tr("pass.level") % int(info["level"]), 26)
	lv.position = Vector2(560, 24)
	lv.size = Vector2(290, 36)
	lv.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	box.add_child(lv)
	var bar := _panel(box, Rect2(30, 100, 821, 18), _style(Color(1, 1, 1, 0.1), 9, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	_panel(bar, Rect2(0, 0, 821.0 * clampf(int(info["xp_in_level"]) / 1000.0, 0.0, 1.0), 18), _style(Color(0.95, 0.72, 0.2), 9, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	var xl := _label("%d / 1000 %s" % [int(info["xp_in_level"]), tr("pass.xp")], 15, TEXT, false)
	xl.position = Vector2(30, 120)
	box.add_child(xl)
	var top := 150.0
	if not info["premium"] and info["can_buy"]:
		_button(box, Rect2(30, top, 400, 64), tr("pass.buy") % String(info["price"]), Color(0.75, 0.5, 0.1), func(): on_buy.call("iap_pass"))
		_button(box, Rect2(451, top, 400, 64), tr("pass.buy_elite") % String(info["price_elite"]), Color(0.55, 0.25, 0.8), func(): on_buy.call("iap_pass_elite"))
		top += 78.0
	elif info["premium"]:
		var pl := _label(tr("pass.elite_on") if info["elite"] else tr("pass.premium_on"), 18, Color(1.0, 0.82, 0.3), false)
		_at(pl, box, Vector2(30, top))
		top += 34.0
		if not info["elite"] and info["can_buy"]:  # premium → elite for the difference (09 §9.12)
			_button(box, Rect2(30, top, 821, 60), tr("pass.upgrade") % String(info["price_up"]), Color(0.55, 0.25, 0.8), func(): on_buy.call("iap_pass_elite_up"))
			top += 72.0
	var head_f := _label(tr("pass.free"), 18, MUTED)
	_at(head_f, box, Vector2(140, top))
	var head_p := _label(tr("pass.premium"), 18, Color(1.0, 0.82, 0.3))
	_at(head_p, box, Vector2(505, top))
	top += 32.0
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(20, top)
	scroll.size = Vector2(841, 1330 - top - 110)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	var col := VBoxContainer.new()
	col.custom_minimum_size = Vector2(830, 0)
	col.add_theme_constant_override("separation", 8)
	scroll.add_child(col)
	for r in info["rows"]:
		var row := Panel.new()
		row.custom_minimum_size = Vector2(830, 76)
		var reached: bool = int(r["lvl"]) <= int(info["level"])
		row.add_theme_stylebox_override("panel", _style(Color(0.14, 0.2, 0.32) if reached else Color(0.09, 0.12, 0.2), 12, EDGE, 1))
		var ln := _label(str(int(r["lvl"])), 26, Color(1.0, 0.85, 0.4) if reached else MUTED)
		ln.position = Vector2(0, 18)
		ln.size = Vector2(90, 40)
		ln.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		row.add_child(ln)
		for k in 2:
			var track: String = ["free", "premium"][k]
			var x := 100.0 + 365.0 * k
			var txt: String = r["free_text" if k == 0 else "prem_text"]
			var state: String = r["free_state" if k == 0 else "prem_state"]
			var t := _label(txt, 16, TEXT if state != "locked" else MUTED, false)
			t.autowrap_mode = TextServer.AUTOWRAP_WORD
			t.custom_minimum_size = Vector2(210, 0)
			t.position = Vector2(x, 10)
			row.add_child(t)
			var lvl: int = r["lvl"]
			if state == "claim":
				var b := _panel(row, Rect2(x + 220, 16, 130, 44), _style(Color(0.75, 0.55, 0.12), 10, Color(1, 1, 1, 0.45), 2))
				var bl := _label(tr("ui.claim"), 17)
				bl.size = Vector2(130, 44)
				bl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
				bl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
				b.add_child(bl)
				b.mouse_filter = Control.MOUSE_FILTER_PASS
				b.gui_input.connect(func(e): if _is_tap(e): on_claim.call(lvl, track))
			else:
				if state == "claimed":
					var m := _label("✓", 22, Color(0.5, 1.0, 0.6))
					m.position = Vector2(x + 220, 18)
					m.size = Vector2(130, 40)
					m.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
					row.add_child(m)
				else:
					var lk := _icon_rect(INLINE_ICONS["🔒"], 30.0)
					lk.position = Vector2(x + 270, 23)
					lk.modulate = Color(1, 1, 1, 0.8)
					row.add_child(lk)
		col.add_child(row)
	_button(box, Rect2(30, 1330 - 96, 821, 76), tr("ui.close"), Color(0.13, 0.4, 0.9), close_modal)


## The 28-day login calendar (08 §8.8): a 7 × 4 grid — taken days ticked, today's glowing, key days (no ×2) in
## gold; «Take» and, where allowed, «×2 for an ad».
func show_calendar(info: Dictionary, on_claim: Callable) -> void:
	var box := _modal_box(Rect2(30, 250, 881, 1150))
	var title := _label(tr("cal.title1") if int(info["cycle"]) == 1 else tr("cal.title2"), 32, Color(1.0, 0.85, 0.4))
	_fit(title, 32, 821)
	_at(title, box, Vector2(30, 22))
	var sub := _label(tr("cal.rule"), 17, MUTED, false)
	sub.autowrap_mode = TextServer.AUTOWRAP_WORD
	sub.custom_minimum_size = Vector2(821, 0)
	_at(sub, box, Vector2(30, 68))
	var cw := 110.0
	var ch := 196.0
	for d in info["days"]:
		var i: int = int(d["day"]) - 1
		var st: String = d["state"]
		var key: bool = d["key"]
		var bg := Color(0.09, 0.12, 0.2)
		var edge := Color(0.4, 0.5, 0.68, 0.7)
		if st == "today":
			bg = Color(0.2, 0.17, 0.08)
			edge = Color(1.0, 0.85, 0.3)
		elif key:
			edge = Color(0.85, 0.65, 0.25, 0.9)
		if st == "claimed":
			bg = Color(0.08, 0.16, 0.12)
		var cell := _panel(box, Rect2(30 + (i % 7) * (cw + 8.5), 130 + (i / 7) * (ch + 8), cw, ch), _style(bg, 12, edge, 3 if st == "today" else 2), Control.MOUSE_FILTER_IGNORE)
		var n := _label(str(int(d["day"])), 20, Color(1.0, 0.85, 0.4) if key else (TEXT if st != "future" else MUTED))
		n.size = Vector2(cw, 30)
		n.position = Vector2(0, 6)
		n.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cell.add_child(n)
		var t := _label(d["text"], 14, TEXT if st != "future" else Color(0.75, 0.8, 0.88), false)
		t.autowrap_mode = TextServer.AUTOWRAP_WORD
		t.custom_minimum_size = Vector2(cw - 10, 0)
		t.position = Vector2(5, 40)
		t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cell.add_child(t)
		if st == "claimed":
			var ok := _label("✓", 30, Color(0.45, 1.0, 0.55))
			ok.size = Vector2(cw, 40)
			ok.position = Vector2(0, ch - 46)
			ok.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			cell.add_child(ok)
		elif key:
			var kx := _label("★", 22, Color(1.0, 0.8, 0.3))
			kx.size = Vector2(cw, 30)
			kx.position = Vector2(0, ch - 38)
			kx.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			cell.add_child(kx)
	var by := 130.0 + 4 * (ch + 8) + 12
	if info["pending"]:
		if info["can_double"]:
			_button(box, Rect2(30, by, 400, 76), tr("ui.claim"), Color(0.75, 0.55, 0.12), func(): on_claim.call(false))
			_button(box, Rect2(451, by, 400, 76), tr("cal.double_patent" if info.get("patent", false) else "cal.double"), Color(0.2, 0.55, 0.3), func(): on_claim.call(true))
		else:
			_button(box, Rect2(30, by, 821, 76), tr("ui.claim"), Color(0.75, 0.55, 0.12), func(): on_claim.call(false))
	else:
		var nx := _label(tr("cal.tomorrow"), 20, MUTED, false)
		nx.size = Vector2(821, 76)
		nx.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		nx.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		_at(nx, box, Vector2(30, by))
	_button(box, Rect2(30, by + 90, 821, 76), tr("ui.close"), Color(0.13, 0.4, 0.9), close_modal)


## «Державный патент» (09 §9.13.4, Apple 3.1.2): name and term, the renewal price biggest, the intro offer on one
## line next to its button, the perks, the auto-renewal terms, the legal links, «Restore purchases», a close
## cross visible at once.
func show_patent(info: Dictionary, on_buy: Callable, on_restore: Callable) -> void:
	var box := _modal_box(Rect2(30, 230, 881, 1060))
	_button(box, Rect2(881 - 86, 18, 64, 56), "✕", Color(0.3, 0.33, 0.42), close_modal)
	_title(box, tr("patent.title"), 30, Color(1.0, 0.85, 0.4), Vector2(30, 26), "crown", true, 740.0)
	var price := _label(tr("patent.price") % String(info["price"]), 46)
	_at(price, box, Vector2(30, 76))
	var y := 150.0
	if info["active"]:
		_at(_label(tr("patent.active") % int(info["days_left"]), 22, Color(0.5, 1.0, 0.6)), box, Vector2(30, y))
		y += 40.0
	var perks := ["patent.p_ads", "patent.p_builder", "patent.p_convoy", "patent.p_collect", "patent.p_timers",
		"patent.p_raivite", "patent.p_key", "patent.p_frame"]
	var icons := ["icons/ad", "builder", "icons/cart", "coin", "icons/hourglass", "raivite", "icons/key", "icons/frame"]
	for i in perks.size():
		_at(_icon_rect("res://assets/ui/%s.png" % icons[i], 40.0), box, Vector2(26, y - 6))
		var row := _label(tr(perks[i]), 21, TEXT, false)
		row.autowrap_mode = TextServer.AUTOWRAP_WORD
		row.custom_minimum_size = Vector2(771, 0)
		_at(row, box, Vector2(80, y))
		y += maxf(_line_h(tr(perks[i])), 34.0) + 8.0
	y += 10.0
	if info["can_buy"]:
		_button(box, Rect2(30, y, 821, 80), tr("patent.buy") % String(info["price"]), Color(0.75, 0.55, 0.12), func(): on_buy.call("iap_sub_patent"))
		y += 92.0
		if info["trial"]:
			_button(box, Rect2(30, y, 821, 70), tr("patent.trial") % [String(info["trial_price"]), String(info["price"])], Color(0.2, 0.45, 0.35), func(): on_buy.call("iap_sub_trial"))
			y += 82.0
	else:
		_at(_label(tr("patent.unavailable"), 20, MUTED, false), box, Vector2(30, y))
		y += 40.0
	var terms := _label(tr("patent.renewal"), 16, MUTED, false)
	terms.autowrap_mode = TextServer.AUTOWRAP_WORD
	terms.custom_minimum_size = Vector2(821, 0)
	_at(terms, box, Vector2(30, y))
	y += 70.0
	_button(box, Rect2(30, y, 260, 56), tr("patent.terms_link"), Color(0.2, 0.25, 0.36), func(): toast(tr("patent.doc_soon")))
	_button(box, Rect2(310, y, 260, 56), tr("patent.privacy_link"), Color(0.2, 0.25, 0.36), func(): toast(tr("patent.doc_soon")))
	_button(box, Rect2(590, y, 261, 56), tr("patent.restore"), Color(0.2, 0.25, 0.36), func(): on_restore.call())


## «Летопись державы» (07 §7.4): a book of 6 chapters; a row — name, condition, progress «37/50», reward, «Забрать».
func show_chronicle(info: Dictionary, on_claim: Callable) -> void:
	var box := _modal_box(Rect2(30, 150, 881, 1370))
	_button(box, Rect2(881 - 86, 18, 64, 56), "✕", Color(0.3, 0.33, 0.42), close_modal)
	_title(box, tr("chr.title") % [int(info["done"]), int(info["total"])], 30, Color(1.0, 0.85, 0.4), Vector2(30, 26), "book", true, 740.0)
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(20, 90)
	scroll.size = Vector2(841, 1260)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	var col := VBoxContainer.new()
	col.custom_minimum_size = Vector2(830, 0)
	col.add_theme_constant_override("separation", 8)
	scroll.add_child(col)
	var chapter := ""
	for r in info["rows"]:
		if String(r["chapter"]) != chapter:
			chapter = r["chapter"]
			var hl := _label(tr("chr.ch." + chapter), 22, Color(1.0, 0.85, 0.4))
			hl.custom_minimum_size = Vector2(830, 40)
			hl.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
			col.add_child(hl)
		var st: String = r["state"]
		var row := Panel.new()
		row.custom_minimum_size = Vector2(830, 96)
		var bg := Color(0.16, 0.14, 0.08) if st == "claim" else Color(0.1, 0.14, 0.23)
		row.add_theme_stylebox_override("panel", _style(bg, 12, Color(1.0, 0.8, 0.3) if st == "claim" else EDGE, 1))
		var nm := _label(String(r["name"]), 19, TEXT if st != "soon" else MUTED)
		_fit(nm, 19, 520)
		nm.position = Vector2(14, 8)
		row.add_child(nm)
		var ds := _label(String(r["desc"]), 15, MUTED, false)
		_fit(ds, 15, 540)
		ds.position = Vector2(14, 36)
		row.add_child(ds)
		var rw := _inline(String(r["reward"]), 15, Color(0.75, 0.85, 1.0), false, 540)
		rw.position = Vector2(14, 60)
		row.add_child(rw)
		var need: int = r["need"]
		var prog: int = r["progress"]
		if st == "claim":
			var b := _panel(row, Rect2(650, 22, 166, 52), _style(Color(0.75, 0.55, 0.12), 10, Color(1, 1, 1, 0.45), 2))
			var bl := _label(tr("ui.claim"), 18)
			bl.size = Vector2(166, 52)
			bl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			bl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			b.add_child(bl)
			b.mouse_filter = Control.MOUSE_FILTER_PASS
			var code: String = r["code"]
			b.gui_input.connect(func(e): if _is_tap(e): on_claim.call(code))
		else:
			var txt := "✓" if st == "claimed" else (tr("chr.soon") if st == "soon" else "%s / %s" % [fmt_num(prog), fmt_num(need)])
			var pl := _label(txt, 18 if st != "claimed" else 26, Color(0.5, 1.0, 0.6) if st == "claimed" else MUTED)
			pl.position = Vector2(600, 18)
			pl.size = Vector2(216, 32)
			pl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			row.add_child(pl)
			if st == "open":
				var bar := _panel(row, Rect2(600, 58, 216, 12), _style(Color(1, 1, 1, 0.1), 6, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
				_panel(bar, Rect2(0, 0, 216.0 * clampf(float(prog) / maxf(1.0, float(need)), 0.0, 1.0), 12), _style(Color(0.95, 0.72, 0.2), 6, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
		col.add_child(row)


## AI ultimatum (canon §9.1): accept (cede the hex), pay tribute, or refuse (war).
func show_ultimatum(enemy: String, hex_name: String, tribute: int, can_pay: bool, left_sec: int, on_accept: Callable, on_pay: Callable, on_refuse: Callable, portrait := "", plate := Color(0, 0, 0, 0)) -> void:
	var box := _modal_box(Rect2(50, 380, 841, 860), true)
	var ink := Color(0.3, 0.08, 0.05)
	var text_w := 780.0
	if portrait != "":
		_leader_seal(box, portrait, plate, Rect2(841 - 166, 22, 136, 162), "angry")
		text_w = 620.0
	_title(box, tr("ult.title") % enemy, 32, ink, Vector2(30, 26), "target", false, text_w)
	var t := _label(tr("ult.text") % [hex_name, tribute, fmt_time(left_sec)], 23, Color(0.25, 0.16, 0.08), false)
	t.autowrap_mode = TextServer.AUTOWRAP_WORD
	_at(t, box, Vector2(30, 90), Vector2(text_w, 260))
	_button(box, Rect2(30, 380, 780, 96), tr("ult.accept") % hex_name, Color(0.45, 0.35, 0.2), on_accept)
	var pay := _button(box, Rect2(30, 494, 780, 96), tr("ult.pay") % tribute, Color(0.75, 0.55, 0.12), on_pay)
	pay.modulate.a = 1.0 if can_pay else 0.45
	_button(box, Rect2(30, 608, 780, 96), tr("ult.refuse"), Color(0.75, 0.16, 0.12), on_refuse)
	_button(box, Rect2(30, 722, 780, 84), tr("ult.later"), Color(0.3, 0.33, 0.42), close_modal)


## The enemy leader's portrait on a parchment (ultimatum, peace conference): the face on the state's colour in a
## dark wooden frame.
func _leader_seal(box: Control, portrait: String, plate: Color, r: Rect2, mood := "") -> void:
	_panel(box, r.grow(6), _style(Color(0.35, 0.22, 0.1), 10, Color(0.75, 0.55, 0.25), 3), Control.MOUSE_FILTER_IGNORE)
	var lp := CmdPortrait.new(portrait)
	lp.plate = plate
	lp.mood = mood
	lp.position = r.position
	lp.size = r.size
	box.add_child(lp)


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


## Settings: sound, language (applies at once: `on_lang` gets "ru" / "en" and re-renders the game, then this
## modal is shown again by the caller), new game, build info.
func show_settings(sound_on: bool, on_sound: Callable, on_new_game: Callable, on_lang: Callable, on_manage := Callable(), on_restore := Callable()) -> void:
	var box := _modal_box(Rect2(90, 380, 761, 804))
	_title(box, tr("settings.title"), 36, TEXT, Vector2(40, 30), "gear")
	_button(box, Rect2(40, 110, 681, 84), tr("settings.sound_on") if sound_on else tr("settings.sound_off"), Color(0.2, 0.3, 0.45), func():
		on_sound.call()
		show_settings(not sound_on, on_sound, on_new_game, on_lang, on_manage, on_restore))
	var ll := _label(tr("settings.language"), 24)
	ll.size = Vector2(250, 84)
	ll.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_at(ll, box, Vector2(40, 214))
	var cur := L.lang()
	for i in L.LANGS.size():
		var code: String = L.LANGS[i]
		_button(box, Rect2(300 + i * 215, 214, 205, 84), String(L.LANG_NAMES[code]), Color(0.16, 0.42, 0.95) if code == cur else Color(0.14, 0.18, 0.27), func():
			if code != L.lang():
				on_lang.call(code))
	var hold := _panel(box, Rect2(40, 318, 681, 84), _style(Color(0.55, 0.16, 0.14), 14, Color(1, 1, 1, 0.5), 2))
	var prog := _panel(hold, Rect2(0, 0, 0, 84), _style(Color(1, 1, 1, 0.25), 14, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	var hl := _label(tr("settings.new_game"), 22)
	hl.size = Vector2(681, 84)
	hl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	hold.add_child(hl)
	var state := {"tw": null}
	hold.gui_input.connect(func(e):
		if e is InputEventScreenTouch or e is InputEventMouseButton:
			if e.pressed:
				var tw := create_tween()
				state["tw"] = tw
				tw.tween_property(prog, "size:x", 681.0, 1.2)
				tw.tween_callback(func(): close_modal(); on_new_game.call())
			elif state["tw"] != null:
				(state["tw"] as Tween).kill()
				state["tw"] = null
				prog.size.x = 0.0)
	_at(_label(tr("settings.autosave"), 18, MUTED, false), box, Vector2(40, 434))
	_at(_label(tr("settings.build") % ProjectSettings.get_setting("application/config/version", "0.3"), 18, MUTED, false), box, Vector2(40, 470))
	# store purchases (09 §9.13.4, Apple 3.1.1): the system subscription screen and «Restore purchases»
	if on_manage.is_valid():
		_button(box, Rect2(40, 530, 333, 70), tr("settings.manage_sub"), Color(0.2, 0.25, 0.36), on_manage)
	if on_restore.is_valid():
		_button(box, Rect2(388, 530, 333, 70), tr("patent.restore"), Color(0.2, 0.25, 0.36), on_restore)
	_button(box, Rect2(40, 684, 681, 84), tr("ui.close"), Color(0.13, 0.4, 0.9), close_modal)


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

const RES_ICON := {"gold": "coin", "food": "food", "metal": "metal", "oil": "metal", "raivite": "raivite"}
var _bpanel: Control
var _bscroll: ScrollContainer
var _brow: HBoxContainer
var _icon_cache := {}


func _icon(res: String) -> Texture2D:
	var k: String = RES_ICON.get(res, "coin")
	if not _icon_cache.has(k):
		_icon_cache[k] = load("res://assets/ui/%s.png" % k)
	return _icon_cache[k]


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


## The right-edge fade shows only while cards are hidden past the right edge.
func _update_fade(_v := 0.0) -> void:
	if _bfade == null:
		return
	var hb := _bscroll.get_h_scroll_bar()
	_bfade.visible = hb.max_value - hb.page - hb.value > 4.0


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
		if card.has_meta("legacy_dx"):
			for c in card.get_children():
				if c is Control and not (c as Control).has_meta("card_btn"):
					(c as Control).position.x += float(card.get_meta("legacy_dx"))
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
	var ready := clampf(float(it["str"]) / maxf(1.0, float(it["max"])), 0.0, 1.0)
	var pct := roundi(ready * 100.0)
	if it["refilling"]:  # «str» / «max» come rounded to thousands: a refilling army never reads 100 %
		pct = mini(pct, 99)
		ready = minf(ready, 0.99)
	var tip := PackedStringArray([tr("army.tip.str") % [int(it["str"]), int(it["max"])], tr("army.tip.squads") % int(it["slots"]),
		tr("army.tip.ready") % pct])
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
		opts["cta"] = {"role": "go", "caption": tr("army.train"), "price": [["food", fmt_num(int(it["food"]))]],
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


## The Army tab's «Командиры» card: a fan of three faces, «7/12», a green dot when a level can be bought.
func _commanders_card(it: Dictionary) -> Control:
	var faces := [["cmd_lira", "common"], ["cmd_rai", "legendary"], ["cmd_vega", "rare"]]
	var pics: Array = []
	for f in faces:
		pics.append(CmdPortrait.new(f[0], f[1]))
	var n: Array = it["commanders"]
	var up := bool(it.get("dot", false))
	var opts := {"art_node": _fan(pics), "tag": "%d/%d" % [int(n[0]), int(n[1])],
		"details": tr("cmdr.collection") % [int(n[0]), int(n[1])] + ("\n" + tr("cmdr.tip_up") if up else ""),
		"cta": {"role": "info", "caption": tr("cmdr.open"), "cb": func(): army_action.emit(-3, "commanders")}}
	if up:
		opts["dot"] = "go"
	return Kit.card(null, String(it["name"]), opts)


## Three small framed pictures (the hand's cards, the collection's faces) fanned out at −8 / 0 / +8° in a card's
## art window (172×104); the middle one on top.
func _fan(pics: Array) -> Control:
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
		fr.position = Vector2(86.0 + k * 42.0 - 32.0, 8.0 + absf(k) * 6.0)
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


## A card of a tab not rebuilt on Kit.card yet (s07): the row's 172 px height; a 150 px card is widened to 180 and
## its content centred (_fill_panel moves it once the card is in the tree: moved earlier, an autowrapped label takes
## its one-line width for good). Its XS button, placed by _card_button, already spans the new width.
func _legacy_card(card: Control) -> Control:
	var w := card.custom_minimum_size.x
	if w < 180.0:
		card.set_meta("legacy_dx", (180.0 - w) * 0.5)
		card.custom_minimum_size.x = 180.0
	card.custom_minimum_size.y = 172.0
	card.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	return card


## The realm's profile (10 §4.23): the flag, name, chapter and DL; tiles — realm size, the chapter's map share, the
## Arena league, «Командиры 7/12» and «Летопись 23/40» (these two open their screens); the 3 latest achievements;
## «Таймлапс», «Сравнить державы», «Друзья» (with the server) and «Настройки».
func show_profile(info: Dictionary, cb: Dictionary) -> void:
	var box := _modal_box(Rect2(30, 170, 881, 1300))
	_button(box, Rect2(881 - 86, 18, 64, 56), "✕", Color(0.3, 0.33, 0.42), close_modal)
	_at(_label(tr("profile.title"), 24, MUTED), box, Vector2(30, 26))
	var crest := FlagView.new(info.get("flag", {}))
	crest.position = Vector2(34, 84)
	crest.size = Vector2(130, 168)
	crest.mouse_filter = Control.MOUSE_FILTER_STOP
	crest.gui_input.connect(func(e): if _is_tap(e): (cb["flag"] as Callable).call())
	box.add_child(crest)
	var edit := _label("✎", 26, Color(1.0, 0.85, 0.4))
	_at(edit, box, Vector2(150, 222))
	var nm := _label(String(info["name"]) + "  ✎", 38, Color(1.0, 0.85, 0.4))
	_fit(nm, 38, 640)
	_at(nm, box, Vector2(190, 92))
	nm.mouse_filter = Control.MOUSE_FILTER_STOP
	nm.gui_input.connect(func(e): if _is_tap(e): (cb["name"] as Callable).call())
	var ch := _label(String(info["chapter"]), 22, TEXT, false)
	_fit(ch, 22, 640)
	_at(ch, box, Vector2(190, 148))
	_at(_label(tr("profile.dl") % int(info["dl"]), 22, Color(0.55, 0.75, 1.0)), box, Vector2(190, 186))
	# tiles
	var cm: Array = info["commanders"]
	var cr: Array = info["chronicle"]
	var tiles := [
		[tr("profile.hexes"), tr("profile.hexes_v") % int(info["hexes"]), "", false],
		[tr("profile.map"), "%d%%" % int(info["map_pct"]), "", false],
		[tr("profile.arena"), tr("profile.arena_v"), "", false],
		[tr("profile.commanders"), "%d / %d" % [int(cm[0]), int(cm[1])], "commanders", bool(info["cmd_dot"])],
		[tr("profile.chronicle"), "%d / %d" % [int(cr[0]), int(cr[1])], "chronicle", int(info["book_badge"]) > 0],
		[tr("profile.wins"), str(int(info["wins"])), "", false],
	]
	for i in tiles.size():
		var t: Array = tiles[i]
		var r := Rect2(30 + (i % 3) * 277, 280 + (i / 3) * 150, 263, 136)
		var link := String(t[2]) != ""
		var tile := _panel(box, r, _style(Color(0.12, 0.17, 0.28) if link else Color(0.09, 0.12, 0.2), 14, Color(1.0, 0.8, 0.35, 0.8) if link else EDGE, 2 if link else 1))
		var tl := _label(String(t[0]), 18, MUTED, false)
		_fit(tl, 18, 240)
		_at(tl, tile, Vector2(16, 14))
		var tv := _label(String(t[1]), 34, TEXT)
		_fit(tv, 34, 240)
		_at(tv, tile, Vector2(16, 52))
		if link:
			var go := _label("›", 34, Color(1.0, 0.85, 0.4))
			_at(go, tile, Vector2(232, 48))
			var key: String = t[2]
			tile.gui_input.connect(func(e): if _is_tap(e): (cb[key] as Callable).call())
		if bool(t[3]):
			_panel(tile, Rect2(236, 10, 18, 18), _style(Color(0.3, 0.9, 0.4), 9, Color(1, 1, 1, 0.8), 2), Control.MOUSE_FILTER_IGNORE)
	# the latest achievements
	_at(_label(tr("profile.recent"), 22, Color(1.0, 0.85, 0.4)), box, Vector2(30, 600))
	var y := 646.0
	if (info["recent"] as Array).is_empty():
		_at(_label(tr("profile.none"), 19, MUTED, false), box, Vector2(30, y))
	for a in info["recent"]:
		var row := _panel(box, Rect2(30, y, 821, 84), _style(Color(0.16, 0.14, 0.08), 12, Color(1.0, 0.8, 0.3, 0.7), 1), Control.MOUSE_FILTER_IGNORE)
		_at(_label("✦", 34, Color(1.0, 0.8, 0.3)), row, Vector2(20, 16))
		var an := _label(String(a["name"]), 21, TEXT)
		_fit(an, 21, 700)
		_at(an, row, Vector2(72, 10))
		_at(_label(String(a["chapter"]), 16, MUTED, false), row, Vector2(72, 46))
		y += 96.0
	# buttons
	var bs := [[tr("profile.timelapse"), "soon"], [tr("profile.compare"), "soon"], [tr("profile.friends"), "soon"], [tr("profile.settings"), "settings"]]
	for i in bs.size():
		var key: String = bs[i][1]
		_button(box, Rect2(30 + (i % 2) * 416, 1300 - 216 + (i / 2) * 96, 405, 82), String(bs[i][0]),
			Color(0.13, 0.4, 0.9) if key != "soon" else Color(0.22, 0.26, 0.36), cb[key])


var _flag_tab := "div"


## The commander portraits follow the player's DL era (04 §15.4).
func set_portrait_era(dl: int) -> void:
	CmdPortrait.era = CmdPortrait.era_of(dl)


## The flag constructor (10 §4.23): the preview on top; tabs «Деление» (12), «Цвета» (2 field colours of 16, the
## emblem's of 18 — gold and yellow only for the emblem), «Эмблема» (24 free + premium `cos_flag_part`), «Рамка»
## (`cos_frame`); locked items show a lock; «Случайно» and «Готово». Each tap calls on_change with the new flag.
func show_flag_editor(flag: Dictionary, owned: Dictionary, on_change: Callable, on_random: Callable, on_done: Callable) -> void:
	var box := _modal_box(Rect2(30, 120, 881, 1430))
	_at(_label(tr("flag.title"), 30, Color(1.0, 0.85, 0.4)), box, Vector2(30, 26))
	var prev := FlagView.new(flag)
	prev.position = Vector2(330, 80)
	prev.size = Vector2(220, 280)
	box.add_child(prev)
	var tabs := [["div", tr("flag.tab_div")], ["colors", tr("flag.tab_colors")], ["em", tr("flag.tab_em")], ["frame", tr("flag.tab_frame")]]
	for i in tabs.size():
		var key: String = tabs[i][0]
		var on := key == _flag_tab
		_button(box, Rect2(30 + i * 207, 380, 195, 64), String(tabs[i][1]), Color(0.2, 0.42, 0.85) if on else Color(0.16, 0.2, 0.3), func():
			_flag_tab = key
			show_flag_editor(flag, owned, on_change, on_random, on_done))
	var area := Control.new()
	area.position = Vector2(30, 470)
	area.size = Vector2(821, 800)
	box.add_child(area)
	var set_key := func(k: String, v: Variant) -> void:
		var f := flag.duplicate()
		f[k] = v
		on_change.call(f)
	match _flag_tab:
		"div":
			for i in FlagView.DIVISIONS.size():
				var d: String = FlagView.DIVISIONS[i]
				var f := flag.duplicate()
				f["div"] = d
				f["em"] = ""
				_flag_tile(area, Rect2((i % 4) * 207, (i / 4) * 250, 195, 238), f, d == String(flag["div"]), false, func(): set_key.call("div", d))
		"colors":
			var groups := [["c1", tr("flag.field1"), FlagView.FIELD], ["c2", tr("flag.field2"), FlagView.FIELD], ["ec", tr("flag.emblem_c"), FlagView.emblem_colors()]]
			var y := 0.0
			for g in groups:
				var key: String = g[0]
				_at(_label(String(g[1]), 20, MUTED), area, Vector2(0, y))
				y += 36.0
				var cols: Array = g[2]
				for i in cols.size():
					var r := Rect2((i % 9) * 91, y + (i / 9) * 91, 80, 80)
					var sel := int(flag[key]) == i
					var sw := _panel(area, r, _style(cols[i], 12, Color(1.0, 0.85, 0.3) if sel else Color(1, 1, 1, 0.25), 5 if sel else 2))
					var idx := i
					sw.gui_input.connect(func(e): if _is_tap(e): set_key.call(key, idx))
				y += ceilf(cols.size() / 9.0) * 91.0 + 18.0
		"em":
			var all: Array = FlagView.EMBLEMS + FlagView.PREMIUM.keys()
			var ecs := FlagView.emblem_colors()
			var ec: Color = ecs[clampi(int(flag["ec"]), 0, ecs.size() - 1)]
			var bg := FlagView.field_color(int(flag["c1"]))
			for i in all.size():
				var em: String = all[i]
				var locked := FlagView.PREMIUM.has(em) and not owned.has(em)
				var sel := em == String(flag["em"])
				var r := Rect2((i % 6) * 137, (i / 6) * 137, 125, 125)
				var tile := _panel(area, r, _style(bg, 14, Color(1.0, 0.85, 0.3) if sel else (Color(0.8, 0.55, 1.0) if FlagView.PREMIUM.has(em) else Color(1, 1, 1, 0.2)), 5 if sel else 2))
				var art := Control.new()
				art.size = r.size
				art.mouse_filter = Control.MOUSE_FILTER_IGNORE
				var draw_em := String(FlagView.PREMIUM.get(em, em))
				art.draw.connect(func(): FlagView.draw_emblem(art, draw_em, art.size / 2, 40.0, ec))
				tile.add_child(art)
				if locked:
					tile.modulate = Color(1, 1, 1, 0.45)
					_at(_icon_rect(INLINE_ICONS["🔒"], 28.0), tile, Vector2(86, 4))
				tile.gui_input.connect(func(e):
					if _is_tap(e):
						if locked:
							toast(tr("flag.locked"))
						else:
							set_key.call("em", em))
		"frame":
			var ids: Array = FlagView.FRAMES.keys()
			for i in ids.size():
				var fid: String = ids[i]
				var locked := fid != "" and not owned.has(fid)
				var f := flag.duplicate()
				f["frame"] = fid
				_flag_tile(area, Rect2((i % 4) * 207, (i / 4) * 262, 195, 250), f, fid == String(flag["frame"]), locked, func():
					if locked:
						toast(tr("flag.locked"))
					else:
						set_key.call("frame", fid))
	_button(box, Rect2(30, 1430 - 110, 400, 84), tr("flag.random"), Color(0.45, 0.3, 0.75), on_random)
	_button(box, Rect2(451, 1430 - 110, 400, 84), tr("flag.done"), Color(0.2, 0.6, 0.3), on_done)


## «Название державы» (canon §14.3): a text field (the system keyboard on a phone), 6 ideas as chips, a die for
## new ideas, «Готово». An empty field keeps «Ваша держава».
func show_name_editor(current: String, ideas: Array, max_len: int, on_done: Callable, on_more: Callable) -> void:
	var box := _modal_box(Rect2(60, 340, 821, 680))
	var t := _label(tr("realm.title"), 32, Color(1.0, 0.85, 0.4))
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_at(t, box, Vector2(0, 30), Vector2(821, 44))
	var field := LineEdit.new()
	field.text = current
	field.placeholder_text = tr("state.player")
	field.max_length = max_len
	field.position = Vector2(40, 100)
	field.size = Vector2(741, 84)
	field.add_theme_font_size_override("font_size", 34)
	if font_bold:
		field.add_theme_font_override("font", font_bold)
	field.add_theme_stylebox_override("normal", _style(Color(0.08, 0.11, 0.18), 14, Color(1.0, 0.8, 0.35, 0.8), 2))
	field.add_theme_stylebox_override("focus", _style(Color(0.1, 0.14, 0.22), 14, Color(1.0, 0.85, 0.4), 3))
	field.alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(field)
	_at(_label(tr("realm.ideas"), 20, MUTED), box, Vector2(40, 210))
	for i in ideas.size():
		var idea: String = ideas[i]
		_button(box, Rect2(40 + (i % 2) * 376, 250 + (i / 2) * 96, 365, 82), idea, Color(0.16, 0.22, 0.34), func():
			field.text = idea)
	_button(box, Rect2(40, 680 - 120, 300, 84), tr("realm.more"), Color(0.45, 0.3, 0.75), on_more)
	_button(box, Rect2(361, 680 - 120, 420, 84), tr("flag.done"), Color(0.2, 0.6, 0.3), func(): on_done.call(field.text))


## The FTUE flag wizard (canon §14.3: 3 taps): step dots, 6 flags to pick from (division, emblem, colours), then
## the chosen flag with «Готово» and «Случайно»; «Можно изменить в профиле».
func show_flag_wizard(step: int, opts: Array, on_pick: Callable, on_random: Callable, on_done: Callable) -> void:
	var box := _modal_box(Rect2(30, 170, 881, 1300))
	var titles := [tr("flagw.title0"), tr("flagw.title1"), tr("flagw.title2"), tr("flagw.title3")]
	var t := _label(String(titles[mini(step, 3)]), 32, Color(1.0, 0.85, 0.4))
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_at(t, box, Vector2(0, 30), Vector2(881, 44))
	for i in 3:
		var on := i <= step
		_panel(box, Rect2(380 + i * 44, 90, 30, 30), _style(Color(1.0, 0.8, 0.3) if on else Color(0.2, 0.24, 0.34), 15, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	if step < 3:
		for i in opts.size():
			var r := Rect2(40 + (i % 3) * 272, 150 + (i / 3) * 430, 256, 410)
			_flag_tile(box, r, opts[i], false, false, func(): on_pick.call(i))
		_button(box, Rect2(240, 1300 - 120, 400, 84), tr("flag.random"), Color(0.45, 0.3, 0.75), on_random)
		return
	var big := FlagView.new(opts[0])
	big.position = Vector2(270, 160)
	big.size = Vector2(340, 440)
	box.add_child(big)
	var hint := _label(tr("flagw.later"), 20, MUTED, false)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_at(hint, box, Vector2(0, 640), Vector2(881, 30))
	_button(box, Rect2(40, 1300 - 120, 390, 84), tr("flag.random"), Color(0.45, 0.3, 0.75), on_random)
	_button(box, Rect2(451, 1300 - 120, 390, 84), tr("flag.done"), Color(0.2, 0.6, 0.3), on_done)


func _flag_tile(parent: Control, r: Rect2, f: Dictionary, sel: bool, locked: bool, cb: Callable) -> void:
	var tile := _panel(parent, r, _style(Color(0.1, 0.14, 0.23), 14, Color(1.0, 0.85, 0.3) if sel else EDGE, 4 if sel else 1))
	var fv := FlagView.new(f)
	fv.position = Vector2(r.size.x * 0.18, 12)
	fv.size = Vector2(r.size.x * 0.64, r.size.y - 24)
	tile.add_child(fv)
	if locked:
		tile.modulate = Color(1, 1, 1, 0.45)
		_at(_icon_rect(INLINE_ICONS["🔒"], 30.0), tile, Vector2(r.size.x - 40, 6))
	tile.gui_input.connect(func(e): if _is_tap(e): cb.call())


## The commander picker of an army (04 §15.6): a row per open commander — portrait, level, the passive now, the
## best one marked «Рекомендуем», one of another army marked with its number; «Снять» at the bottom.
func show_cmd_picker(title: String, rows: Array, on_pick: Callable, on_remove: Callable) -> void:
	var h := minf(1370.0, 200.0 + rows.size() * 142.0 + 110.0)
	var box := _modal_box(Rect2(30, maxf(150.0, (VH - h) / 2.0 - 60.0), 881, h))
	_button(box, Rect2(881 - 86, 18, 64, 56), "✕", Color(0.3, 0.33, 0.42), close_modal)
	var t := _label(title, 30, Color(1.0, 0.85, 0.4))
	_at(t, box, Vector2(30, 26))
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(20, 90)
	scroll.size = Vector2(841, h - 210)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	var col := VBoxContainer.new()
	col.custom_minimum_size = Vector2(830, 0)
	col.add_theme_constant_override("separation", 10)
	scroll.add_child(col)
	for r in rows:
		var here := bool(r["here"])
		var best := bool(r.get("best", false))
		var row := Panel.new()
		row.custom_minimum_size = Vector2(830, 132)
		row.mouse_filter = Control.MOUSE_FILTER_PASS
		row.add_theme_stylebox_override("panel", _style(Color(0.15, 0.24, 0.16) if here else Color(0.1, 0.14, 0.23), 12, Color(0.3, 0.9, 0.4) if here else (Color(1.0, 0.8, 0.3) if best else EDGE), 2))
		var pr := CmdPortrait.new(String(r["id"]), String(r["rarity"]))
		pr.position = Vector2(10, 10)
		pr.size = Vector2(96, 112)
		row.add_child(pr)
		var nm := _label("%s · %s" % [String(r["name"]), tr("cmdr.lvl_n") % int(r["level"])], 20)
		_fit(nm, 20, 520)
		nm.position = Vector2(124, 10)
		row.add_child(nm)
		var y := 44.0
		for ln in r["lines"]:
			var pl := _label(String(ln), 16, Color(0.75, 0.88, 1.0), false)
			_fit(pl, 16, 690)
			pl.position = Vector2(124, y)
			row.add_child(pl)
			y += 26.0
		var tag := tr("cmdr.leads") if here else (String(r["busy"]) if String(r["busy"]) != "" else (tr("cmdr.recommend") if best else ""))
		if tag != "":
			var tl := _label(tag, 16, Color(0.5, 1.0, 0.6) if here else (Color(1.0, 0.85, 0.4) if best else MUTED))
			tl.position = Vector2(560, 12)
			tl.size = Vector2(256, 24)
			tl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			row.add_child(tl)
		var id: String = r["id"]
		row.gui_input.connect(func(e): if _is_tap(e) and not here: on_pick.call(id))
		col.add_child(row)
	var any_here := rows.any(func(r): return bool(r["here"]))
	_button(box, Rect2(30, h - 106, 821, 80), tr("cmdr.remove") if any_here else tr("ui.close"), Color(0.55, 0.2, 0.2) if any_here else Color(0.13, 0.4, 0.9), on_remove)


## The collection (04 §15.7): albums, each a 3 × N grid of commander cards; a tap opens the commander.
func show_commanders(info: Dictionary, on_pick: Callable) -> void:
	var box := _modal_box(Rect2(30, 150, 881, 1370))
	_button(box, Rect2(881 - 86, 18, 64, 56), "✕", Color(0.3, 0.33, 0.42), close_modal)
	_at(_label(String(info["title"]), 30, Color(1.0, 0.85, 0.4)), box, Vector2(30, 26))
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(20, 90)
	scroll.size = Vector2(841, 1260)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	var col := VBoxContainer.new()
	col.custom_minimum_size = Vector2(830, 0)
	col.add_theme_constant_override("separation", 10)
	scroll.add_child(col)
	for a in info["albums"]:
		var hl := _label(String(a["name"]) + ("  ✦" if bool(a["full"]) else ""), 22, Color(1.0, 0.85, 0.4) if bool(a["full"]) else MUTED)
		hl.custom_minimum_size = Vector2(830, 40)
		hl.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
		col.add_child(hl)
		var grid := GridContainer.new()
		grid.columns = 3
		grid.add_theme_constant_override("h_separation", 13)
		grid.add_theme_constant_override("v_separation", 13)
		col.add_child(grid)
		for c in a["cards"]:
			grid.add_child(_commander_tile(c, on_pick))


func _commander_tile(c: Dictionary, on_pick: Callable) -> Control:
	var lvl: int = c["level"]
	var tile := Panel.new()
	tile.custom_minimum_size = Vector2(268, 350)
	tile.add_theme_stylebox_override("panel", _style(Color(0.1, 0.14, 0.23), 14, Color(0.3, 0.9, 0.4) if bool(c["can"]) else EDGE, 3 if bool(c["can"]) else 1))
	tile.mouse_filter = Control.MOUSE_FILTER_PASS
	var p := CmdPortrait.new(String(c["id"]), String(c["rarity"]), lvl <= 0)
	p.position = Vector2(8, 8)
	p.size = Vector2(252, 222)
	tile.add_child(p)
	var nm := _label(String(c["name"]), 19, TEXT if lvl > 0 else MUTED)
	_fit(nm, 19, 252)
	nm.position = Vector2(8, 236)
	nm.size = Vector2(252, 28)
	nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tile.add_child(nm)
	var sub := _label(tr("cmdr.lvl") % [lvl, int(c["cap"])] if lvl > 0 else String(c.get("src", "")), 16 if lvl > 0 else 14, Color(1.0, 0.85, 0.4) if lvl > 0 else MUTED, lvl > 0)
	_fit(sub, 16 if lvl > 0 else 14, 252)
	sub.position = Vector2(8, 266)
	sub.size = Vector2(252, 24)
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tile.add_child(sub)
	if c.has("shards"):
		var sh: Array = c["shards"]
		var bar := _panel(tile, Rect2(20, 300, 228, 18), _style(Color(1, 1, 1, 0.1), 9, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
		var fill := clampf(float(sh[0]) / maxf(1.0, float(sh[1])), 0.0, 1.0)
		_panel(bar, Rect2(0, 0, 228.0 * fill, 18), _style(Color(0.3, 0.85, 0.45) if fill >= 1.0 else Color(0.35, 0.6, 1.0), 9, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
		var st := _label("%d / %d" % [int(sh[0]), int(sh[1])], 14)
		st.size = Vector2(228, 18)
		st.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		st.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		st.mouse_filter = Control.MOUSE_FILTER_IGNORE
		bar.add_child(st)
	elif lvl > 0:
		var mx := _label(tr("cmdr.max_short"), 15, Color(0.5, 1.0, 0.6))
		mx.position = Vector2(8, 298)
		mx.size = Vector2(252, 22)
		mx.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		tile.add_child(mx)
	if bool(c["can"]):
		var up := _label("▲", 22, Color(0.3, 0.95, 0.45))
		up.position = Vector2(226, 12)
		tile.add_child(up)
	var id: String = c["id"]
	tile.gui_input.connect(func(e): if _is_tap(e): on_pick.call(id))
	return tile


## The commander card (04 §15.7): portrait, rarity and album, biography, the passive now and by level (the current
## row marked), «Повысить: N осколков + G золота», where the shards come from, «Поставить Целью» (epic, legendary).
func show_commander(info: Dictionary, on_upgrade: Callable, on_target: Callable, on_back: Callable) -> void:
	var box := _modal_box(Rect2(30, 150, 881, 1370))
	_button(box, Rect2(881 - 86, 18, 64, 56), "✕", Color(0.3, 0.33, 0.42), close_modal)
	_button(box, Rect2(22, 18, 64, 56), "‹", Color(0.3, 0.33, 0.42), on_back)
	var t := _label(String(info["name"]), 32, Color(1.0, 0.85, 0.4))
	_fit(t, 32, 680)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_at(t, box, Vector2(100, 22), Vector2(681, 50))
	var lvl: int = info["level"]
	var p := CmdPortrait.new(String(info["id"]), String(info["rarity"]), lvl <= 0)
	p.mood = String(info.get("mood", ""))  # a smile right after a level-up
	p.position = Vector2(30, 92)
	p.size = Vector2(330, 390)
	box.add_child(p)
	var rc: Color = CmdPortrait.RARITY.get(String(info["rarity"]), MUTED)
	var x := 384.0
	_at(_label(String(info["rarity_name"]), 22, rc), box, Vector2(x, 96))
	var al := _label(String(info["album"]), 17, MUTED, false)
	_fit(al, 17, 470)
	_at(al, box, Vector2(x, 130))
	var lv := _label(tr("cmdr.lvl") % [lvl, int(info["cap"])] if lvl > 0 else tr("cmdr.locked_short"), 30, TEXT)
	_at(lv, box, Vector2(x, 164))
	if info.has("shards"):
		var sh: Array = info["shards"]
		var bar := _panel(box, Rect2(x, 214, 460, 22), _style(Color(1, 1, 1, 0.1), 11, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
		var fill := clampf(float(sh[0]) / maxf(1.0, float(sh[1])), 0.0, 1.0)
		_panel(bar, Rect2(0, 0, 460.0 * fill, 22), _style(Color(0.3, 0.85, 0.45) if fill >= 1.0 else Color(0.35, 0.6, 1.0), 11, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
		var st := _label(tr("cmdr.shards") % [int(sh[0]), int(sh[1])], 15)
		st.size = Vector2(460, 22)
		st.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		st.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		bar.add_child(st)
	var py := 254.0
	for ln in info["passive"]:
		var pl := _label("• " + String(ln), 19, Color(0.75, 0.88, 1.0), false)
		pl.autowrap_mode = TextServer.AUTOWRAP_WORD
		pl.custom_minimum_size = Vector2(470, 0)
		pl.position = Vector2(x, py)
		box.add_child(pl)
		py += _line_h(String(ln)) * 0.9
	var bio := _label(String(info["bio"]), 19, TEXT, false)
	bio.autowrap_mode = TextServer.AUTOWRAP_WORD
	bio.custom_minimum_size = Vector2(821, 0)
	bio.position = Vector2(30, 500)
	box.add_child(bio)
	# the passive by level
	var ty := 650.0
	_at(_label(tr("cmdr.by_level"), 20, Color(1.0, 0.85, 0.4)), box, Vector2(30, ty))
	ty += 40.0
	var cur_row := 0  # the highest table level the commander has reached
	for row in info["table"]:
		if int(row[0]) <= lvl:
			cur_row = int(row[0])
	for row in info["table"]:
		var l: int = row[0]
		var cur := l == cur_row
		var bg := _panel(box, Rect2(30, ty, 821, 42), _style(Color(0.2, 0.3, 0.16) if cur else Color(0.09, 0.12, 0.2), 8, Color(0.5, 0.9, 0.4) if cur else Color(0, 0, 0, 0), 2 if cur else 0), Control.MOUSE_FILTER_IGNORE)
		var future := l > lvl
		var lab := _label(tr("cmdr.lvl_n") % l + ("  ·  " + tr("cmdr.launch_cap") if l == 16 else ""), 17, MUTED if future else TEXT, false)
		_at(lab, bg, Vector2(16, 9))
		var val := _label(String(row[1]), 17, MUTED if future else Color(0.75, 0.88, 1.0))
		val.size = Vector2(380, 24)
		val.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		_at(val, bg, Vector2(425, 9), Vector2(380, 24))
		ty += 48.0
	var src := _label(tr("cmdr.where") % String(info["src"]), 17, MUTED, false)
	src.autowrap_mode = TextServer.AUTOWRAP_WORD
	src.custom_minimum_size = Vector2(821, 0)
	src.position = Vector2(30, ty + 10)
	box.add_child(src)
	var can := bool(info["can"])
	var by := 1370.0 - 110.0
	if on_target.is_valid():
		var on := bool(info.get("target", false))
		_button(box, Rect2(30, by - 96, 821, 80), tr("cmdr.target_on") if on else tr("cmdr.target"), Color(0.45, 0.3, 0.75) if not on else Color(0.25, 0.25, 0.32), on_target)
	var b := _button(box, Rect2(30, by, 821, 86), String(info["button"]), Color(0.2, 0.6, 0.3) if can else Color(0.25, 0.28, 0.36), on_upgrade)
	if not can:
		b.modulate = Color(1, 1, 1, 0.85)


## Hand picker (03 §5.2): every open card as a toggle; «Атака» is fixed, `slots` more can be chosen.
func show_hand_picker(cards: Array, chosen: Array, slots: int, on_toggle: Callable) -> void:
	var rows := ceili(cards.size() / 2.0)
	var h := 200.0 + rows * 96.0 + 110.0
	var box := _modal_box(Rect2(60, maxf(200.0, (VH - h) / 2.0 - 80.0), 821, h))
	var t := _label(tr("hand.title_full"), 32, Color(1.0, 0.85, 0.4))
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_at(t, box, Vector2(0, 24), Vector2(821, 44))
	var sub := _label(tr("hand.rule") % [chosen.size(), slots], 19, MUTED, false)
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub.autowrap_mode = TextServer.AUTOWRAP_WORD
	_at(sub, box, Vector2(30, 76), Vector2(761, 60))
	for i in cards.size():
		var c: String = cards[i]
		var on := chosen.has(c) or c == "attack"
		var r := Rect2(30 + (i % 2) * 391, 150 + (i / 2) * 96, 370, 80)
		var col := Color(0.2, 0.42, 0.28) if on else Color(0.14, 0.18, 0.27)
		var pic := "res://assets/ui/cards/%s.png" % c
		var has_pic := ResourceLoader.exists(pic)
		var label := "%s%s" % [_card_name(c), "  ✓" if on else ""] if has_pic else "%s  %s%s" % [String(CARD_ART.get(c, "?")), _card_name(c), "  ✓" if on else ""]
		var b := _button(box, r, label, col, func(): on_toggle.call(c))
		if has_pic:  # the card's painted scene on the left, the name beside it
			var tr_ := TextureRect.new()
			tr_.texture = load(pic)
			tr_.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			tr_.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
			tr_.clip_contents = true
			tr_.position = Vector2(8, 6)
			tr_.size = Vector2(62, 68)
			tr_.mouse_filter = Control.MOUSE_FILTER_IGNORE
			b.add_child(tr_)
			for ch in b.get_children():
				if ch is Label:
					(ch as Label).position.x = 40.0  # centred in the room right of the picture
		if c == "attack":
			b.modulate = Color(1, 1, 1, 0.75)  # fixed
	_button(box, Rect2(30, h - 100, 761, 76), tr("ui.close"), Color(0.13, 0.4, 0.9), close_modal)


func show_diplomacy(items: Array) -> void:
	_fill_panel("d", items, _diplomacy_card)


func _diplomacy_card(it: Dictionary) -> Control:
	if String(it.get("kind", "")) == "alarm":
		return _alarm_card(it)
	var card := Panel.new()
	card.custom_minimum_size = Vector2(304, 178)
	var col: Color = it["color"]
	card.add_theme_stylebox_override("panel", _style(Color(0.1, 0.14, 0.22), 12, col, 3))
	card.mouse_filter = Control.MOUSE_FILTER_PASS
	var fx := 12.0
	if not (it.get("flag", {}) as Dictionary).is_empty():
		var fl := FlagView.new(it["flag"])
		fl.position = Vector2(10, 6)
		fl.size = Vector2(20, 26)
		card.add_child(fl)
		fx = 36.0
	var st := _label(it["state"], 18, col.lightened(0.3))
	_fit(st, 18, 172.0 - fx)  # room for the Pact and ⇄ buttons on the right
	st.position = Vector2(fx, 8)
	card.add_child(st)
	var tx := 12.0
	if String(it.get("portrait", "")) != "":
		# the leader's face from the portrait kit (canon §10.4), on a plate of the state's colour
		var lp := CmdPortrait.new(String(it["portrait"]))
		lp.mood = String(it.get("mood", ""))
		lp.plate = col.darkened(0.1)
		lp.position = Vector2(10, 36)
		lp.size = Vector2(54, 66)
		card.add_child(lp)
		tx = 72.0
	var ld := _label("%s · %s" % [it["leader"], it["archetype"]], 14, MUTED, false)
	ld.position = Vector2(tx, 32)
	ld.size = Vector2(296 - tx, 20)
	ld.clip_text = true
	card.add_child(ld)
	var v: float = it["opinion"]
	var op := _label(tr("dipl.opinion") % [roundi(v), it["word"]], 16, Color(0.5, 1.0, 0.6) if v > 10.0 else (Color(1.0, 0.55, 0.45) if v < -10.0 else TEXT), false)
	_fit(op, 16, 296 - tx)
	op.position = Vector2(tx, 56)
	card.add_child(op)
	var st_text: String = it["status"] if String(it.get("ai_ally", "")) == "" else "%s · %s" % [it["status"], tr("dipl.ai_ally") % it["ai_ally"]]
	if it.has("share"):  # a coalition member's share of the war score (06 §14.6)
		st_text = tr("dipl.share") % float(it["share"])
	var stt := _label(st_text, 16, Color(1.0, 0.85, 0.4), false)
	_fit(stt, 16, 196 - tx)
	stt.position = Vector2(tx, 82)
	card.add_child(stt)
	var id: int = it["id"]
	if it.get("separate", false):
		# «Сепаратный мир» with a coalition member (canon §10.8)
		var bsp := _panel(card, Rect2(176, 78, 118, 36), _style(Color(0.2, 0.55, 0.35), 10, Color(1, 1, 1, 0.45), 2))
		bsp.mouse_filter = Control.MOUSE_FILTER_PASS
		var lsp := _label(tr("dipl.separate"), 14)
		lsp.size = Vector2(118, 36)
		lsp.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lsp.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		bsp.add_child(lsp)
		bsp.gui_input.connect(func(e): if _is_tap(e): diplomacy_action.emit(id, "separate"))
	elif it.get("can_call", false):
		var bc := _panel(card, Rect2(196, 78, 98, 36), _style(Color(0.85, 0.55, 0.1), 10, Color(1, 1, 1, 0.45), 2))
		bc.mouse_filter = Control.MOUSE_FILTER_PASS
		var lc := _label(tr("dipl.call"), 15)
		lc.size = Vector2(98, 36)
		lc.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lc.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		bc.add_child(lc)
		bc.gui_input.connect(func(e): if _is_tap(e): diplomacy_action.emit(id, "call"))
	elif it.get("ally", false):
		var al := _label(tr("dipl.ally"), 16, Color(0.5, 1.0, 0.6))
		al.position = Vector2(190, 82)
		al.size = Vector2(104, 24)
		al.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		card.add_child(al)
	elif it.has("ally_reason"):
		var why: String = it["ally_reason"]
		var ba := _panel(card, Rect2(196, 78, 98, 36), _style(Color(0.16, 0.42, 0.95) if why == "" else Color(0.3, 0.33, 0.4), 10, Color(1, 1, 1, 0.45), 2))
		ba.mouse_filter = Control.MOUSE_FILTER_PASS
		var la := _label(tr("dipl.alliance"), 15)
		la.size = Vector2(98, 36)
		la.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		la.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		ba.add_child(la)
		ba.gui_input.connect(func(e): if _is_tap(e):
			if why == "":
				diplomacy_action.emit(id, "ally")
			else:
				toast(why))
	var bw := _panel(card, Rect2(10, 128, 136, 40), _style(Color(0.75, 0.2, 0.15) if it["can_war"] else Color(0.3, 0.33, 0.4), 10, Color(1, 1, 1, 0.45), 2))
	bw.mouse_filter = Control.MOUSE_FILTER_PASS
	var lw := _label(tr("dipl.war"), 17)
	lw.size = Vector2(136, 40)
	lw.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lw.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	bw.add_child(lw)
	var can_war: bool = it["can_war"]
	bw.gui_input.connect(func(e): if _is_tap(e):
		if can_war:
			diplomacy_action.emit(id, "war")
		else:
			toast(it["status"]))
	if it.has("pact_reason"):
		# «Пакт о ненападении» (06 §11): a small button left of ⇄; shows its timer while it holds
		var why_p: String = it["pact_reason"]
		var pl: int = it.get("pact_left", 0)
		var bp := _panel(card, Rect2(176, 6, 70, 34), _style(Color(0.55, 0.42, 0.2) if why_p == "" else Color(0.3, 0.33, 0.4), 9, Color(1, 1, 1, 0.45), 2))
		bp.mouse_filter = Control.MOUSE_FILTER_PASS
		var lp := _label(tr("dipl.pact_btn") if pl == 0 else fmt_time(pl), 14)
		lp.size = Vector2(70, 34)
		lp.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lp.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		bp.add_child(lp)
		bp.gui_input.connect(func(e): if _is_tap(e):
			if why_p == "":
				diplomacy_action.emit(id, "pact")
			else:
				toast(why_p))
	if it.has("swap_reason"):
		# «Обмен территориями» (06 §15): a compact ⇄ in the corner, greyed with the reason when not possible
		var why_s: String = it["swap_reason"]
		var bs := _panel(card, Rect2(250, 6, 44, 34), _style(Color(0.2, 0.45, 0.6) if why_s == "" else Color(0.3, 0.33, 0.4), 9, Color(1, 1, 1, 0.45), 2))
		bs.mouse_filter = Control.MOUSE_FILTER_PASS
		var ls := _label("⇄", 20)
		ls.size = Vector2(44, 34)
		ls.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		ls.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		bs.add_child(ls)
		bs.gui_input.connect(func(e): if _is_tap(e):
			if why_s == "":
				diplomacy_action.emit(id, "swap")
			else:
				toast(why_s))
	var gl: int = it["gift_left"]
	var bg := _panel(card, Rect2(156, 128, 138, 40), _style(Color(0.2, 0.5, 0.35) if gl == 0 else Color(0.3, 0.33, 0.4), 10, Color(1, 1, 1, 0.45), 2))
	bg.mouse_filter = Control.MOUSE_FILTER_PASS
	var lg := _label((tr("dipl.gift") % int(it["gift_cost"])) if gl == 0 else "🎁 " + fmt_time(gl), 16)
	lg.size = Vector2(138, 40)
	lg.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lg.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	bg.add_child(lg)
	bg.gui_input.connect(func(e): if _is_tap(e): diplomacy_action.emit(id, "gift"))
	return _legacy_card(card)


## «Тревога соседей» (canon §10.8): threat / coalition threshold as a bar, what it means now, how to calm it.
func _alarm_card(it: Dictionary) -> Control:
	var card := Panel.new()
	card.custom_minimum_size = Vector2(304, 178)
	var pct: int = it["pct"]
	var hot := Color(0.95, 0.3, 0.25) if pct >= 100 else (Color(1.0, 0.7, 0.2) if pct >= 50 else Color(0.4, 0.8, 0.5))
	card.add_theme_stylebox_override("panel", _style(Color(0.1, 0.14, 0.22), 12, hot, 3))
	card.mouse_filter = Control.MOUSE_FILTER_PASS
	var t := _label(tr("alarm.title"), 18, hot.lightened(0.3))
	t.position = Vector2(12, 6)
	card.add_child(t)
	var pl := _label("%d%%" % mini(pct, 999), 18, hot.lightened(0.3))
	pl.position = Vector2(220, 6)
	pl.size = Vector2(72, 26)
	pl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	card.add_child(pl)
	var bar := _panel(card, Rect2(12, 38, 280, 14), _style(Color(1, 1, 1, 0.1), 7, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	_panel(bar, Rect2(0, 0, 280.0 * clampf(pct / 100.0, 0.0, 1.0), 14), _style(hot, 7, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	_panel(bar, Rect2(139, -3, 2, 20), _style(Color(1, 1, 1, 0.55), 1, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)  # 50%
	var ln := _label(it["line"], 15, TEXT, false)
	ln.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	ln.custom_minimum_size = Vector2(284, 0)
	ln.position = Vector2(12, 60)
	ln.size = Vector2(284, 44)
	card.add_child(ln)
	var h := _label(tr("alarm.hint"), 13, MUTED, false)
	h.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	h.custom_minimum_size = Vector2(284, 0)
	h.position = Vector2(12, 108)
	h.size = Vector2(284, 64)
	card.add_child(h)
	return _legacy_card(card)


## World tab: chapter progress and the chapter stars (canon §12.1).
func show_world(items: Array) -> void:
	_fill_panel("w", items, func(it): return _chapter_card(it) if it["kind"] == "chapter" else _star_card(it))


func _chapter_card(it: Dictionary) -> Control:
	var card := Panel.new()
	card.custom_minimum_size = Vector2(250, 178)
	card.add_theme_stylebox_override("panel", _style(Color(0.1, 0.16, 0.26), 12, Color(0.45, 0.65, 1.0), 3))
	card.mouse_filter = Control.MOUSE_FILTER_PASS
	_at(_label(tr("world.chapter1"), 18), card, Vector2(12, 6))
	var h: int = it["hexes"]
	var g: int = it["goal"]
	_at(_label(tr("world.hexes") % [h, g], 17, TEXT, false), card, Vector2(12, 36))
	var bar := _panel(card, Rect2(12, 66, 226, 14), _style(Color(1, 1, 1, 0.1), 7, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	_panel(bar, Rect2(0, 0, 226.0 * clampf(float(h) / g, 0.0, 1.0), 14), _style(Color(0.3, 0.62, 1.0), 7, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	if it["done"]:
		_at(_label(tr("world.chapter_done"), 16, Color(0.5, 1.0, 0.6)), card, Vector2(12, 96))
	elif it["can_expand"]:
		var b := _panel(card, Rect2(10, 128, 230, 40), _style(Color(0.2, 0.55, 0.3), 10, Color(1, 1, 1, 0.5), 2))
		b.mouse_filter = Control.MOUSE_FILTER_PASS
		var l := _label(tr("world.expand"), 17)
		l.size = Vector2(230, 40)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		b.add_child(l)
		b.gui_input.connect(func(e): if _is_tap(e): world_action.emit("expand"))
	else:
		var hint := _label(tr("world.hint"), 14, MUTED, false)
		hint.position = Vector2(12, 96)
		hint.autowrap_mode = TextServer.AUTOWRAP_WORD
		hint.custom_minimum_size = Vector2(226, 0)  # autowrap needs a fixed width
		card.add_child(hint)
	return _legacy_card(card)


func _star_card(it: Dictionary) -> Control:
	var card := Panel.new()
	card.custom_minimum_size = Vector2(150, 178)
	var done: bool = int(it["progress"]) >= int(it["need"])
	var claimed: bool = it["claimed"]
	card.add_theme_stylebox_override("panel", _style(Color(0.16, 0.14, 0.08) if done and not claimed else Color(0.1, 0.15, 0.25), 12, Color(1.0, 0.8, 0.3) if done else Color(0.45, 0.58, 0.8, 0.7), 2))
	card.mouse_filter = Control.MOUSE_FILTER_PASS
	var glyph: String = it.get("icon", "")  # «Приказы дня» carry their own icon instead of the star
	var star := _label(glyph if glyph != "" else ("★" if claimed else "☆"), 30, Color(1.0, 0.82, 0.25) if done else MUTED)
	star.position = Vector2(0, 4)
	star.size = Vector2(150, 40)
	star.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(star)
	var t := _label(it["title"], 15, TEXT, false)
	t.position = Vector2(8, 46)
	t.autowrap_mode = TextServer.AUTOWRAP_WORD
	t.custom_minimum_size = Vector2(134, 0)  # autowrap needs a fixed width
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(t)
	var id: String = it["id"]
	if it.get("swap", false):  # the day's one free swap of an order (08 §8.6)
		var sw := _panel(card, Rect2(112, 6, 32, 32), _style(Color(0.2, 0.28, 0.42), 8, Color(0.6, 0.72, 0.95, 0.8), 1))
		var sl := _label("⇄", 18)
		sl.size = Vector2(32, 32)
		sl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		sl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		sw.add_child(sl)
		sw.gui_input.connect(func(e): if _is_tap(e): world_action.emit("swap:" + id))
	if it.get("ready", false):  # something waits inside (the calendar's day)
		var dot := _panel(card, Rect2(124, 8, 18, 18), _style(Color(0.9, 0.2, 0.15), 9, Color(1, 1, 1, 0.9), 2), Control.MOUSE_FILTER_IGNORE)
		dot.name = "ReadyDot"
	if it.get("open", false):
		_card_button(card, tr("ui.open"), Color(0.55, 0.25, 0.8), func(): world_action.emit(id), true)
		var pr := _label("%d / %d" % [int(it["progress"]), int(it["need"])], 15, MUTED)
		pr.position = Vector2(0, 94)
		pr.size = Vector2(150, 22)
		pr.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(pr)
	elif claimed:
		var ok := _label(tr("world.claimed"), 16, Color(0.5, 1.0, 0.6))
		ok.position = Vector2(0, 140)
		ok.size = Vector2(150, 24)
		ok.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(ok)
	elif done:
		_card_button(card, tr("ui.claim"), Color(0.75, 0.55, 0.12), func(): world_action.emit(id), true)
	else:
		var p := _label("%d / %d" % [int(it["progress"]), int(it["need"])], 18, MUTED)
		p.position = Vector2(0, 138)
		p.size = Vector2(150, 28)
		p.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(p)
	return _legacy_card(card)


func hide_buildings() -> void:
	if _bpanel:
		_bpanel.visible = false
	_bkey = ""
	_bfam = ""


## The rendered icon of each building on its card (tools/blender/icon_assets.py → assets/ui/icons).
const BUILDING_ICONS := {"residence": "castle_icon", "barracks": "helmet", "academy": "book", "warehouse": "crate",
	"infirmary": "flask", "convoy_yard": "cart", "market": "stall", "embassy": "hands", "quarters": "houses",
	"farm": "food", "mine": "metal", "port": "anchor", "military_base": "target",
	# the Academy's research lines (the Development tab uses the same cards)
	"rs_infantry": "helmet", "rs_reserve": "fort", "rs_drill": "target", "rs_taxes": "coin", "rs_harvest": "food",
	"rs_metallurgy": "metal", "rs_cellars": "crate", "rs_logistics": "cart", "rs_thrift": "stall", "rs_colonization": "pin"}


func _building_card(it: Dictionary) -> Control:
	if it.has("market"):
		return _market_card(it)
	var card := Panel.new()
	card.custom_minimum_size = Vector2(150, 178)
	var busy: bool = it["busy"]
	card.add_theme_stylebox_override("panel", _style(Color(0.1, 0.15, 0.25) if not busy else Color(0.16, 0.14, 0.1), 12, Color(0.45, 0.58, 0.8, 0.8) if not busy else Color(0.95, 0.7, 0.25, 0.9), 2))
	card.mouse_filter = Control.MOUSE_FILTER_PASS
	var nm := _label(it["name"], 17)
	nm.position = Vector2(0, 6)
	nm.size = Vector2(150, 24)
	nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	nm.clip_text = true
	card.add_child(nm)
	var lv := _label(tr("bld.level") % [it["level"], it["max"]], 15, MUTED, false)
	lv.position = Vector2(0, 32)
	lv.size = Vector2(150, 22)
	lv.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(lv)
	var icon_name := String(BUILDING_ICONS.get(String(it.get("type", "")), ""))
	var pic_path := "res://assets/ui/icons/%s.png" % icon_name
	if not ResourceLoader.exists(pic_path):  # the resource icons (coin, food, metal) sit one folder up
		pic_path = "res://assets/ui/%s.png" % icon_name
	if not busy and icon_name != "" and ResourceLoader.exists(pic_path):  # the building's picture beside the cost (reference HUD cards)
		var pic := TextureRect.new()
		pic.texture = load(pic_path)
		pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		pic.position = Vector2(86, 52)
		pic.size = Vector2(58, 58)
		pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(pic)
	var id: int = it["id"]
	if busy:
		var t := _label(fmt_time(int(it["left"])), 28, Color(1.0, 0.85, 0.4))
		t.position = Vector2(0, 52)
		t.size = Vector2(150, 40)
		t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(t)
		var sp: int = it["speed"]
		var stock: int = it.get("stock", 0)
		var txt := tr("bld.free") if sp == 0 else (tr("bld.stock") % stock if stock > 0 else "⚡ %d" % sp)
		var line_s: String = it.get("line", "")
		if int(it.get("bp", 0)) > 0:
			# «Применить чертёж» (07 §6.1)
			var bpb := _panel(card, Rect2(20, 86, 110, 30), _style(Color(0.45, 0.32, 0.18), 8, Color(1.0, 0.85, 0.5, 0.7), 2))
			var bpl := _label(tr("bld.blueprint") % int(it["bp"]), 15)
			bpl.size = Vector2(110, 30)
			bpl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			bpl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			bpl.mouse_filter = Control.MOUSE_FILTER_IGNORE
			bpb.add_child(bpl)
			bpb.gui_input.connect(func(e): if _is_tap(e): research_speedup.emit("bp:" + line_s))
		_card_button(card, txt, Color(0.85, 0.55, 0.1), func():
			if line_s != "":
				research_speedup.emit(line_s)
			else:
				building_speedup.emit(id), sp > 0)
		return _legacy_card(card)
	if int(it["level"]) >= int(it["max"]) and String(it["reason"]) != "":
		var m := _label(it["reason"], 15, MUTED, false)
		m.position = Vector2(8, 66)
		m.autowrap_mode = TextServer.AUTOWRAP_WORD
		m.custom_minimum_size = Vector2(134, 0)  # autowrap needs a fixed width
		m.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(m)
		return _legacy_card(card)
	var y := 50.0
	var cost: Dictionary = it["cost"]
	for r in cost:
		var row := HBoxContainer.new()
		row.position = Vector2(26, y)
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var ic := TextureRect.new()
		ic.texture = _icon(r)
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.custom_minimum_size = Vector2(20, 20)
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(ic)
		row.add_child(_label(str(cost[r]), 16, TEXT, false))
		card.add_child(row)
		y += 18
	var tl := _label("⏱ " + fmt_time(int(it["seconds"])), 14, MUTED, false)
	tl.position = Vector2(26, y)
	card.add_child(tl)
	var ok: bool = String(it["reason"]) == ""
	var line: String = it.get("line", "")
	_card_button(card, tr("bld.research") if line != "" else tr("ui.upgrade"), Color(0.2, 0.55, 0.3) if ok else Color(0.3, 0.33, 0.4), func():
		if ok and line != "":
			research_start.emit(line)
		elif ok:
			building_upgrade.emit(id)
		else:
			toast(it["reason"]), true)
	return _legacy_card(card)


## First card of the Buildings tab once the Market stands: current rate and an «open» button.
func _market_card(it: Dictionary) -> Control:
	var card := Panel.new()
	card.custom_minimum_size = Vector2(150, 178)
	card.add_theme_stylebox_override("panel", _style(Color(0.17, 0.14, 0.08), 12, Color(0.95, 0.75, 0.3, 0.9), 2))
	card.mouse_filter = Control.MOUSE_FILTER_PASS
	var nm := _label(tr("bld.market"), 17)
	nm.position = Vector2(0, 6)
	nm.size = Vector2(150, 24)
	nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(nm)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 2)
	row.position = Vector2(14, 44)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for r in MARKET_RES:
		var ic := TextureRect.new()
		ic.texture = _icon(r)
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.custom_minimum_size = Vector2(38, 38)
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(ic)
	card.add_child(row)
	var rl := _label(tr("market.rate") % _rate_txt(int(it["rate"])), 15, MUTED, false)
	rl.position = Vector2(0, 92)
	rl.size = Vector2(150, 22)
	rl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(rl)
	_card_button(card, tr("market.open"), Color(0.85, 0.55, 0.1), func(): market_open.emit(), true)
	return _legacy_card(card)


## The XS button at the bottom of a legacy tray card (6, 120, 168, 46 on the 180×172 card; PASS: a drag still
## scrolls the row). The legacy «can't» grey shows the lock role but still runs `cb` (the callers explain the
## reason in a toast). `_enabled` stays unused as before: the speed-up card passes false for its free speed-up.
func _card_button(card: Control, text: String, color: Color, cb: Callable, _enabled: bool) -> void:
	var role := "lock" if Kit.is_legacy_disabled(color) else Kit.role_of(color)
	var b := Kit.button(card, Rect2(6, 120, 168, 46), role, text, {"cb": cb, "size": "XS", "filter": Control.MOUSE_FILTER_PASS})
	b.set_meta("card_btn", true)


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
## Screen rects of the buttons the coach points at (the big action button of hud.gd): framed instead of circled.
const COACH_FRAMES := [Rect2(660, VH - 122, 266, 92)]


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
	if _seal_t >= 0.0 and _seal_prog:
		_seal_t += delta
		_seal_prog.size.x = 829.0 * clampf(_seal_t / 0.8, 0.0, 1.0)
		if _seal_t >= 0.8:
			_seal_t = -1.0
			seal_done.emit()
