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

var font_bold: Font
var root: Control
var _control_bar: Control
var _control_fill: Panel
var _control_lbl: Label
var _control_lbl2: Label
var _score_lbl: Label
var _laststand: Label
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
var _drag_card := ""
var _ghost: Label
var _seal_t := -1.0
var _seal_prog: Panel


func _ready() -> void:
	layer = 2
	var f := SystemFont.new()
	f.font_names = PackedStringArray(["Noto Sans", "DejaVu Sans", "Roboto", "Arial"])
	f.font_weight = 800
	font_bold = f
	root = Control.new()
	root.size = Vector2(VW, VH)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	_build_control_bar()
	_build_battle()
	_build_action()
	_ghost = _label("", 64)
	_ghost.visible = false
	_ghost.z_index = 50
	root.add_child(_ghost)


# ------------------------------------------------------------------ helpers

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
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.75))
	l.add_theme_constant_override("outline_size", 5 if bold else 0)
	if bold:
		l.add_theme_font_override("font", font_bold)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


## Shrinks the label's font from `base` (down to 12) until its one-line text fits `max_w` px: button captions
## differ in length between languages (and some Russian ones never fit the 266 px button).
func _fit(l: Label, base: int, max_w: float) -> void:
	var f := l.get_theme_font("font")
	var s := base
	while s > 12 and f.get_string_size(l.text, HORIZONTAL_ALIGNMENT_LEFT, -1, s).x > max_w:
		s -= 1
	l.add_theme_font_size_override("font_size", s)


func _panel(parent: Control, rect: Rect2, style: StyleBox, filter := Control.MOUSE_FILTER_STOP) -> Panel:
	var p := Panel.new()
	p.position = rect.position
	p.size = rect.size
	p.add_theme_stylebox_override("panel", style)
	p.mouse_filter = filter
	parent.add_child(p)
	return p


func _at(l: Control, parent: Control, pos: Vector2, size := Vector2.ZERO) -> Control:
	l.position = pos
	if size != Vector2.ZERO:
		l.size = size
	parent.add_child(l)
	return l


# ------------------------------------------------------------------ control bar (war)

func _build_control_bar() -> void:
	_control_bar = Control.new()
	_control_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_control_bar)
	_panel(_control_bar, Rect2(108, 84, 612, 74), _style(PANEL, 12), Control.MOUSE_FILTER_IGNORE)
	var bar := _panel(_control_bar, Rect2(122, 94, 584, 30), _style(Color(0.85, 0.15, 0.13), 14, Color(1, 1, 1, 0.9), 2), Control.MOUSE_FILTER_IGNORE)
	_control_fill = _panel(bar, Rect2(2, 2, 290, 26), _style(Color(0.18, 0.45, 1.0), 12, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	_control_lbl = _at(_label("50%", 18), _control_bar, Vector2(134, 96)) as Label
	_control_lbl2 = _at(_label("50%", 18), _control_bar, Vector2(650, 96)) as Label
	_score_lbl = _at(_label(tr("ui.war_score_zero"), 15, MUTED, false), _control_bar, Vector2(126, 128)) as Label
	_laststand = _at(_label(tr("ui.last_stand"), 17, Color(1, 0.4, 0.35)), _control_bar, Vector2(350, 128)) as Label
	_control_bar.visible = false


func set_control(score: float, control: int, enemy: String, visible_bar: bool) -> void:
	_control_bar.visible = visible_bar
	if not visible_bar:
		return
	_control_fill.size.x = 580.0 * clampf(control / 100.0, 0.0, 1.0)
	_control_lbl.text = "%d%%" % control
	_control_lbl2.text = "%d%%" % (100 - control)
	_score_lbl.text = tr("ui.war_status") % [enemy, score]
	_laststand.visible = control <= 30


# ------------------------------------------------------------------ battle hand

func _build_battle() -> void:
	_battle = Control.new()
	_battle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_battle)
	_panel(_battle, Rect2(0, VH - 276, 640, 276), _style(PANEL, 16))
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
		var art := _label(CARD_ART[card], 54 if n <= 5 else 46)
		art.position = Vector2(0, 14)
		art.size = Vector2(w, 70)
		art.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		p.add_child(art)
		var nm := _label(_card_name(card), 17)
		_fit(nm, 17, w - 6.0)
		nm.position = Vector2(0, 94)
		nm.size = Vector2(w, 24)
		nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		p.add_child(nm)
		_card_names[card] = nm
		var cost := _panel(p, Rect2(w / 2.0 - 20.0, 138, 40, 40), _style(Color(0.55, 0.3, 0.95), 20, Color(1, 1, 1, 0.9), 3), Control.MOUSE_FILTER_IGNORE)
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


func _card_cost(c: String) -> int:
	return {"attack": 2, "breakthrough": 3, "airstrike": 4, "encircle": 3, "defense": 2, "corps": 3, "landing": 4, "missile": 5}[c]


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
			if pos.y < VH - 280:
				card_drop.emit(c, pos)
		else:
			card_drag.emit(_drag_card, pos, true)
		get_viewport().set_input_as_handled()


# ------------------------------------------------------------------ action buttons (bottom-right)

func _build_action() -> void:
	_action = _panel(root, Rect2(652, VH - 276, 280, 140), _style(PANEL, 16))
	_action2 = _panel(root, Rect2(660, VH - 122, 266, 92), _style(Color(0.13, 0.4, 0.9), 16, Color(0.55, 0.75, 1.0), 3))
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


func close_modal() -> void:
	if _modal:
		_modal.queue_free()
		_modal = null


func _modal_box(rect: Rect2, parchment := false) -> Panel:
	close_modal()
	_modal = Control.new()
	_modal.size = Vector2(VW, VH)
	_modal.mouse_filter = Control.MOUSE_FILTER_STOP
	root.add_child(_modal)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.0 if parchment else 0.35)
	dim.size = Vector2(VW, VH)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_modal.add_child(dim)
	var bg := Color(0.95, 0.89, 0.74) if parchment else PANEL
	return _panel(_modal, rect, _style(bg, 22, Color(0.55, 0.42, 0.2) if parchment else EDGE, 3))


func _button(parent: Control, rect: Rect2, text: String, color: Color, cb: Callable) -> Panel:
	var b := _panel(parent, rect, _style(color, 14, Color(1, 1, 1, 0.5), 2))
	var l := _label(text, 22)
	_fit(l, 22, rect.size.x - 16.0)
	l.size = rect.size
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	b.add_child(l)
	b.gui_input.connect(func(e): if _is_tap(e): cb.call())
	return b


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


func show_peace(enemy: String, budget: float, control: int, demands: Array, chosen: Dictionary, plunder := 1) -> void:
	var box := _modal_box(Rect2(30, 640, 881, 1010), true)
	var ink := Color(0.24, 0.16, 0.07)
	_at(_label(tr("peace.title") % enemy, 32, ink, false), box, Vector2(30, 24))
	var used := 0.0
	for d in demands:
		if chosen.has(d["id"]):
			used += d["cost"]
	_at(_label(tr("peace.points") % [used, budget, control], 22, ink, false), box, Vector2(30, 78))
	_at(_label(tr("peace.hint"), 17, Color(0.42, 0.32, 0.18), false), box, Vector2(30, 112))
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
		var icon := "⭕" if d["kind"] == "pocket" else ("⬢" if d["kind"] == "annex" else ("💰" if d["kind"] == "contribution" else "📜"))
		_at(_label(icon + "  " + str(d["label"]), 21, ink, false), row, Vector2(16, 14))
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
		l.size = Vector2(VW, 60)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.position = Vector2(0, 230 + i * 64)
		if i > 0:
			l.add_theme_font_size_override("font_size", 30)
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
	_at(_label(tr("inbox.title"), 34), box, Vector2(36, 26))
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
	_at(_label(tr("pass.title") % int(info["season"]), 32, Color(1.0, 0.85, 0.4)), box, Vector2(30, 22))
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
				var m := _label("✓" if state == "claimed" else "🔒", 22, Color(0.5, 1.0, 0.6) if state == "claimed" else MUTED)
				m.position = Vector2(x + 220, 18)
				m.size = Vector2(130, 40)
				m.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
				row.add_child(m)
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
			_button(box, Rect2(451, by, 400, 76), tr("cal.double"), Color(0.2, 0.55, 0.3), func(): on_claim.call(true))
		else:
			_button(box, Rect2(30, by, 821, 76), tr("ui.claim"), Color(0.75, 0.55, 0.12), func(): on_claim.call(false))
	else:
		var nx := _label(tr("cal.tomorrow"), 20, MUTED, false)
		nx.size = Vector2(821, 76)
		nx.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		nx.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		_at(nx, box, Vector2(30, by))
	_button(box, Rect2(30, by + 90, 821, 76), tr("ui.close"), Color(0.13, 0.4, 0.9), close_modal)


## AI ultimatum (canon §9.1): accept (cede the hex), pay tribute, or refuse (war).
func show_ultimatum(enemy: String, hex_name: String, tribute: int, can_pay: bool, left_sec: int, on_accept: Callable, on_pay: Callable, on_refuse: Callable) -> void:
	var box := _modal_box(Rect2(50, 380, 841, 860), true)
	var ink := Color(0.3, 0.08, 0.05)
	_at(_label(tr("ult.title") % enemy, 32, ink, false), box, Vector2(30, 26))
	var t := _label(tr("ult.text") % [hex_name, tribute, fmt_time(left_sec)], 23, Color(0.25, 0.16, 0.08), false)
	t.autowrap_mode = TextServer.AUTOWRAP_WORD
	_at(t, box, Vector2(30, 90), Vector2(780, 260))
	_button(box, Rect2(30, 380, 780, 96), tr("ult.accept") % hex_name, Color(0.45, 0.35, 0.2), on_accept)
	var pay := _button(box, Rect2(30, 494, 780, 96), tr("ult.pay") % tribute, Color(0.75, 0.55, 0.12), on_pay)
	pay.modulate.a = 1.0 if can_pay else 0.45
	_button(box, Rect2(30, 608, 780, 96), tr("ult.refuse"), Color(0.75, 0.16, 0.12), on_refuse)
	_button(box, Rect2(30, 722, 780, 84), tr("ult.later"), Color(0.3, 0.33, 0.42), close_modal)


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
func show_settings(sound_on: bool, on_sound: Callable, on_new_game: Callable, on_lang: Callable) -> void:
	var box := _modal_box(Rect2(90, 420, 761, 704))
	_at(_label(tr("settings.title"), 36), box, Vector2(40, 30))
	_button(box, Rect2(40, 110, 681, 84), tr("settings.sound_on") if sound_on else tr("settings.sound_off"), Color(0.2, 0.3, 0.45), func():
		on_sound.call()
		show_settings(not sound_on, on_sound, on_new_game, on_lang))
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
	_button(box, Rect2(40, 584, 681, 84), tr("ui.close"), Color(0.13, 0.4, 0.9), close_modal)


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


## 12345 -> "12 345" (exact amounts on the Market).
static func fmt_num(n: int) -> String:
	var t := str(absi(n))
	var out := ""
	while t.length() > 3:
		out = " " + t.substr(t.length() - 3) + out
		t = t.substr(0, t.length() - 3)
	return ("-" if n < 0 else "") + t + out


static func fmt_time(sec: int) -> String:
	if sec >= 3600:
		return L.t("time.hm") % [sec / 3600, (sec % 3600) / 60]
	if sec >= 60:
		return "%d:%02d" % [sec / 60, sec % 60]
	return L.t("time.s") % sec


## items: [{id, name, level, max, busy, left, speed, cost: {res: n}, seconds, reason}]
var _bkey := ""
var _finger_down := false


func _ensure_panel() -> void:
	if _bpanel != null:
		return
	_bpanel = Control.new()
	_bpanel.position = Vector2(0, VH - 188)
	_bpanel.size = Vector2(640, 182)
	_bpanel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_bpanel)
	root.move_child(_bpanel, 0)
	_bscroll = ScrollContainer.new()
	_bscroll.position = Vector2(8, 0)
	_bscroll.size = Vector2(626, 182)
	_bscroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_bscroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_NEVER
	_bpanel.add_child(_bscroll)
	_brow = HBoxContainer.new()
	_brow.add_theme_constant_override("separation", 8)
	_bscroll.add_child(_brow)


## Rebuilds the card row only when its content changed, and never under a finger (a rebuild between
## press and release would swallow the tap).
func _fill_panel(kind: String, items: Array, builder: Callable) -> void:
	_ensure_panel()
	_bpanel.visible = true
	var key := kind + JSON.stringify(items)
	if key == _bkey:
		return
	if _finger_down and _bkey.begins_with(kind):
		return
	_bkey = key
	var keep := _bscroll.scroll_horizontal
	for c in _brow.get_children():
		_brow.remove_child(c)
		c.queue_free()
	for it in items:
		_brow.add_child(builder.call(it))
	_bscroll.set_deferred("scroll_horizontal", keep)


func show_buildings(items: Array) -> void:
	_fill_panel("b", items, _building_card)


## Army tab: one card per army (strength, readiness, refill) and a «Новая армия» card (canon §8.1).
func show_armies(items: Array) -> void:
	_fill_panel("a", items, _army_card)


func _army_card(it: Dictionary) -> Control:
	if it.has("hand"):
		return _hand_card(it)
	var card := Panel.new()
	card.custom_minimum_size = Vector2(150, 178)
	card.add_theme_stylebox_override("panel", _style(Color(0.1, 0.15, 0.25), 12, Color(0.45, 0.58, 0.8, 0.8), 2))
	card.mouse_filter = Control.MOUSE_FILTER_PASS
	var nm := _label(it["name"], 17)
	nm.position = Vector2(0, 6)
	nm.size = Vector2(150, 24)
	nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(nm)
	var id: int = it["id"]
	if id < 0:
		if it.has("left"):
			var t := _label(fmt_time(int(it["left"])), 26, Color(1.0, 0.85, 0.4))
			t.position = Vector2(0, 60)
			t.size = Vector2(150, 40)
			t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			card.add_child(t)
			var sub := _label(tr("army.recruiting"), 15, MUTED, false)
			sub.position = Vector2(0, 104)
			sub.size = Vector2(150, 22)
			sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			card.add_child(sub)
			return card
		if it["locked"]:
			var m := _label(tr("army.locked_dl") % int(it.get("need_dl", 3)), 20, MUTED, false)
			m.position = Vector2(8, 70)
			m.size = Vector2(134, 40)
			m.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			card.add_child(m)
			return card
		var row := HBoxContainer.new()
		row.position = Vector2(26, 60)
		var ic := TextureRect.new()
		ic.texture = _icon("food")
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.custom_minimum_size = Vector2(24, 24)
		row.add_child(ic)
		row.add_child(_label(str(it["food"]), 18, TEXT, false))
		card.add_child(row)
		var tl := _label("⏱ " + fmt_time(int(it["seconds"])), 15, MUTED, false)
		tl.position = Vector2(26, 90)
		card.add_child(tl)
		_card_button(card, tr("army.train"), Color(0.2, 0.55, 0.3), func(): army_action.emit(-1, "train"), true)
		return card
	var big := _label("⚔ %d" % int(it["str"]), 28)
	big.position = Vector2(0, 34)
	big.size = Vector2(150, 40)
	big.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(big)
	var ready := float(it["str"]) / maxf(1.0, float(it["max"]))
	var bar := _panel(card, Rect2(14, 82, 122, 12), _style(Color(1, 1, 1, 0.1), 6, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	_panel(bar, Rect2(0, 0, 122 * ready, 12), _style(Color(0.3, 0.62, 1.0) if ready >= 0.5 else Color(1.0, 0.6, 0.25), 6, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	var sub2 := _label(tr("army.squads") % [int(it["slots"]), roundi(ready * 100.0)], 15, MUTED, false)
	sub2.position = Vector2(0, 100)
	sub2.size = Vector2(150, 22)
	sub2.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(sub2)
	if it.has("upkeep"):
		var up := _label(tr("army.upkeep") % int(it["upkeep"]), 13, Color(0.9, 0.8, 0.5), false)
		up.position = Vector2(0, 117)
		up.size = Vector2(150, 16)
		up.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(up)
	if it["refilling"]:
		_card_button(card, tr("army.refill"), Color(0.85, 0.55, 0.1), func(): army_action.emit(id, "refill"), true)
	else:
		var ok := _label(tr("army.ready"), 16, Color(0.5, 1.0, 0.6))
		ok.position = Vector2(0, 142)
		ok.size = Vector2(150, 24)
		ok.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(ok)
	return card


## Diplomacy tab: a card per neighbour — leader, opinion, status, war / gift buttons (canon §10.6).
## The Army tab's «Рука» card: the cards of the hand and «Настроить» (03 §5.2: «Атака» + 4 slots, 5 from DL6).
func _hand_card(it: Dictionary) -> Control:
	var card := Panel.new()
	card.custom_minimum_size = Vector2(150, 178)
	card.add_theme_stylebox_override("panel", _style(Color(0.16, 0.12, 0.24), 12, Color(0.75, 0.6, 1.0, 0.8), 2))
	card.mouse_filter = Control.MOUSE_FILTER_PASS
	var nm := _label(it["name"], 17)
	nm.position = Vector2(0, 6)
	nm.size = Vector2(150, 24)
	nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(nm)
	var glyphs := PackedStringArray()
	for c in it["hand"]:
		glyphs.append(String(CARD_ART.get(c, "?")))
	var g := _label(" ".join(glyphs), 24, Color(1.0, 0.85, 0.4))
	g.autowrap_mode = TextServer.AUTOWRAP_WORD
	g.custom_minimum_size = Vector2(140, 0)
	g.position = Vector2(5, 40)
	g.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(g)
	_card_button(card, tr("hand.edit"), Color(0.45, 0.3, 0.75), func(): army_action.emit(-2, "hand"), true)
	return card


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
		var b := _button(box, r, "%s  %s%s" % [String(CARD_ART.get(c, "?")), _card_name(c), "  ✓" if on else ""], col, func(): on_toggle.call(c))
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
	var st := _label(it["state"], 18, col.lightened(0.3))
	_fit(st, 18, 160.0)  # room for the Pact and ⇄ buttons on the right
	st.position = Vector2(12, 8)
	card.add_child(st)
	var ld := _label("%s · %s" % [it["leader"], it["archetype"]], 14, MUTED, false)
	ld.position = Vector2(12, 32)
	ld.size = Vector2(284, 20)
	ld.clip_text = true
	card.add_child(ld)
	var v: float = it["opinion"]
	var op := _label(tr("dipl.opinion") % [roundi(v), it["word"]], 16, Color(0.5, 1.0, 0.6) if v > 10.0 else (Color(1.0, 0.55, 0.45) if v < -10.0 else TEXT), false)
	op.position = Vector2(12, 56)
	card.add_child(op)
	var st_text: String = it["status"] if String(it.get("ai_ally", "")) == "" else "%s · %s" % [it["status"], tr("dipl.ai_ally") % it["ai_ally"]]
	if it.has("share"):  # a coalition member's share of the war score (06 §14.6)
		st_text = tr("dipl.share") % float(it["share"])
	var stt := _label(st_text, 16, Color(1.0, 0.85, 0.4), false)
	stt.position = Vector2(12, 82)
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
	return card


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
	return card


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
	return card


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
		pr.position = Vector2(0, 116)
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
	return card


func hide_buildings() -> void:
	if _bpanel:
		_bpanel.visible = false
	_bkey = ""


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
	var id: int = it["id"]
	if busy:
		var t := _label(fmt_time(int(it["left"])), 28, Color(1.0, 0.85, 0.4))
		t.position = Vector2(0, 62)
		t.size = Vector2(150, 40)
		t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(t)
		var sp: int = it["speed"]
		var stock: int = it.get("stock", 0)
		var txt := tr("bld.free") if sp == 0 else (tr("bld.stock") % stock if stock > 0 else "⚡ %d" % sp)
		var line_s: String = it.get("line", "")
		_card_button(card, txt, Color(0.85, 0.55, 0.1), func():
			if line_s != "":
				research_speedup.emit(line_s)
			else:
				building_speedup.emit(id), sp > 0)
		return card
	if int(it["level"]) >= int(it["max"]) and String(it["reason"]) != "":
		var m := _label(it["reason"], 15, MUTED, false)
		m.position = Vector2(8, 66)
		m.autowrap_mode = TextServer.AUTOWRAP_WORD
		m.custom_minimum_size = Vector2(134, 0)  # autowrap needs a fixed width
		m.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(m)
		return card
	var y := 54.0
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
		y += 20
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
	return card


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
	return card


func _card_button(card: Control, text: String, color: Color, cb: Callable, _enabled: bool) -> void:
	var b := _panel(card, Rect2(8, 134, 134, 38), _style(color, 10, Color(1, 1, 1, 0.45), 2))
	b.mouse_filter = Control.MOUSE_FILTER_PASS
	var l := _label(text, 17)
	_fit(l, 17, 128.0)
	l.size = Vector2(134, 38)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	b.add_child(l)
	b.gui_input.connect(func(e): if _is_tap(e): cb.call())


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
	_coach_ring = _panel(_coach, Rect2(0, 0, 120, 120), _style(Color(1, 1, 1, 0.0), 60, Color(1.0, 0.85, 0.3), 6), Control.MOUSE_FILTER_IGNORE)
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
		_coach_ring.size = Vector2(120, 120) * k
		_coach_ring.position = _coach_target - _coach_ring.size / 2
		_coach_arrow.position = _coach_target + Vector2(-20, -150 + 14 * sin(_coach_t * 5.0))
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
