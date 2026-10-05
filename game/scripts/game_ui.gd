extends CanvasLayer
## Mode-dependent game UI layered over the static HUD frame (hud.gd): control bar, battle hand,
## action button, result modal, peace parchment, ceremony counters. Emits intents; game.gd decides.

signal action_pressed(kind: String)
signal card_drop(card: String, screen: Vector2)
signal card_drag(card: String, screen: Vector2, active: bool)
signal demand_toggled(id: String)
signal seal_done

const PANEL := Color(0.055, 0.085, 0.14, 0.95)
const EDGE := Color(0.32, 0.42, 0.58, 0.6)
const TEXT := Color(0.96, 0.97, 1.0)
const MUTED := Color(0.62, 0.68, 0.78)
const VW := 941.0
const VH := 1672.0
const CARD_ART := {"attack": "⚔", "breakthrough": "➶", "airstrike": "✈", "encircle": "◎", "defense": "⛨"}
const CARD_ORDER := ["attack", "breakthrough", "airstrike", "encircle", "defense"]

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
	_score_lbl = _at(_label("Военный счёт: 0", 15, MUTED, false), _control_bar, Vector2(126, 128)) as Label
	_laststand = _at(_label("ВЫ НА ГРАНИ ПОРАЖЕНИЯ! Последний рубеж +25%", 17, Color(1, 0.4, 0.35)), _control_bar, Vector2(350, 128)) as Label
	_control_bar.visible = false


func set_control(score: float, control: int, enemy: String, visible_bar: bool) -> void:
	_control_bar.visible = visible_bar
	if not visible_bar:
		return
	_control_fill.size.x = 580.0 * clampf(control / 100.0, 0.0, 1.0)
	_control_lbl.text = "%d%%" % control
	_control_lbl2.text = "%d%%" % (100 - control)
	_score_lbl.text = "Война: %s · счёт %+.1f" % [enemy, score]
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
	for i in CARD_ORDER.size():
		var card: String = CARD_ORDER[i]
		var x := 12.0 + i * 125.0
		var p := _panel(_battle, Rect2(x, VH - 222, 116, 196), _style(Color(0.12, 0.17, 0.28), 14, Color(0.5, 0.62, 0.85, 0.8), 2))
		p.gui_input.connect(_on_card_input.bind(card))
		var art := _label(CARD_ART[card], 54)
		art.position = Vector2(0, 14)
		art.size = Vector2(116, 70)
		art.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		p.add_child(art)
		var nm := _label(_card_name(card), 17)
		nm.position = Vector2(0, 94)
		nm.size = Vector2(116, 24)
		nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		p.add_child(nm)
		var cost := _panel(p, Rect2(38, 138, 40, 40), _style(Color(0.55, 0.3, 0.95), 20, Color(1, 1, 1, 0.9), 3), Control.MOUSE_FILTER_IGNORE)
		var cl := _label(str(_card_cost(card)), 20)
		cl.position = Vector2(0, 5)
		cl.size = Vector2(40, 30)
		cl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cost.add_child(cl)
		var cd := _label("", 34)
		cd.name = "cd"
		cd.position = Vector2(0, 40)
		cd.size = Vector2(116, 60)
		cd.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		p.add_child(cd)
		_cards[card] = p
	_battle.visible = false


func _card_name(c: String) -> String:
	return {"attack": "Атака", "breakthrough": "Прорыв", "airstrike": "Авиаудар", "encircle": "Окружение", "defense": "Оборона"}[c]


func _card_cost(c: String) -> int:
	return {"attack": 2, "breakthrough": 3, "airstrike": 4, "encircle": 3, "defense": 2}[c]


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
		p.modulate = Color(1, 1, 1, 0.45 if (pts < _card_cost(c) or cd > 0) else 1.0)
		(p.get_node("cd") as Label).text = str(int(ceil(cd / 10.0))) if cd > 0 else ""
	set_action("timer", "%d:%02d" % [seconds_left / 60, seconds_left % 60], "Финальный рывок!" if rush else "Отступить ↩", Color(0.5, 0.2, 0.2) if rush else Color(0.2, 0.25, 0.4))


func _on_card_input(event: InputEvent, card: String) -> void:
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
	_action.add_theme_stylebox_override("panel", _style(bg, 16))


## Big blue button — kind "" hides it (the HUD's own «Атаковать» shows through).
func set_primary(kind: String, title: String, color := Color(0.13, 0.4, 0.9), enabled := true) -> void:
	_action2_kind = kind if enabled else ""
	_action2.visible = kind != ""
	_action2_lbl.text = title
	_action2.add_theme_stylebox_override("panel", _style(color, 16, Color(1, 1, 1, 0.6), 3))
	_action2.modulate = Color(1, 1, 1, 1.0 if enabled else 0.5)


# ------------------------------------------------------------------ modals

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
	l.size = rect.size
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	b.add_child(l)
	b.gui_input.connect(func(e): if _is_tap(e): cb.call())
	return b


func show_result(stars: int, captured: int, lost: int, score: float, control: int, reason: String, on_continue: Callable, on_peace: Callable) -> void:
	var box := _modal_box(Rect2(70, 420, 800, 640))
	var t := _label("Итоги наступления", 36)
	_at(t, box, Vector2(40, 30))
	var st := ""
	for i in 3:
		st += "★" if i < stars else "☆"
	var sl := _label(st, 90, Color(1.0, 0.82, 0.25))
	sl.size = Vector2(800, 110)
	sl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_at(sl, box, Vector2(0, 90))
	var rows := [["Причина", reason], ["Захвачено гексов", str(captured)], ["Потеряно своих", str(lost)], ["Военный счёт", "%+.1f" % score], ["Контроль фронта", "%d%%" % control]]
	for i in rows.size():
		_at(_label(rows[i][0], 24, MUTED, false), box, Vector2(60, 230 + i * 50))
		var v := _label(rows[i][1], 24)
		v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		_at(v, box, Vector2(440, 230 + i * 50), Vector2(300, 34))
	_at(_label("Захваченное оккупировано. Граница сдвинется после мира.", 19, MUTED, false), box, Vector2(60, 490))
	_button(box, Rect2(40, 540, 350, 76), "Продолжить войну", Color(0.25, 0.3, 0.42), on_continue)
	_button(box, Rect2(410, 540, 350, 76), "🕊 Мир (%.1f)" % score, Color(0.2, 0.6, 0.3), on_peace)


func show_peace(enemy: String, budget: float, control: int, demands: Array, chosen: Dictionary) -> void:
	var box := _modal_box(Rect2(30, 640, 881, 1010), true)
	var ink := Color(0.24, 0.16, 0.07)
	_at(_label("📜 Мирный договор: %s" % enemy, 32, ink, false), box, Vector2(30, 24))
	var used := 0.0
	for d in demands:
		if chosen.has(d["id"]):
			used += d["cost"]
	_at(_label("Очки: %.1f / %.1f · Контроль фронта %d%%" % [used, budget, control], 22, ink, false), box, Vector2(30, 78))
	_at(_label("ИИ согласится, если сумма не больше счёта. Ядро врага требовать нельзя.", 17, Color(0.42, 0.32, 0.18), false), box, Vector2(30, 112))
	var y := 150.0
	for d in demands:
		if y > 760:
			break
		var on: bool = chosen.has(d["id"])
		var fits: bool = on or used + float(d["cost"]) <= budget + 0.0001
		var row := _panel(box, Rect2(26, y, 829, 64), _style(Color(0.3, 0.55, 0.3, 0.25) if on else Color(0.3, 0.2, 0.1, 0.08), 12, Color(0.25, 0.5, 0.25) if on else Color(0, 0, 0, 0), 3))
		row.modulate = Color(1, 1, 1, 1.0 if fits else 0.45)
		var icon := "⭕" if d["kind"] == "pocket" else ("⬢" if d["kind"] == "annex" else ("💰" if d["kind"] == "contribution" else "📜"))
		_at(_label(icon + "  " + str(d["label"]), 22, ink, false), row, Vector2(16, 16))
		var c := _label("%.1f" % d["cost"], 24, ink)
		c.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		_at(c, row, Vector2(600, 14), Vector2(210, 34))
		var id: String = d["id"]
		row.gui_input.connect(func(e): if _is_tap(e): demand_toggled.emit(id))
		y += 72
	var seal := _panel(box, Rect2(26, 800, 829, 96), _style(Color(0.2, 0.55, 0.28), 16, Color(1, 1, 1, 0.6), 3))
	_seal_prog = _panel(seal, Rect2(0, 0, 0, 96), _style(Color(1, 1, 1, 0.3), 16, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	var sl := _label("🔏 Удерживайте печать — подписать мир", 26)
	sl.size = Vector2(829, 96)
	sl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	seal.add_child(sl)
	seal.gui_input.connect(func(e):
		if e is InputEventScreenTouch or e is InputEventMouseButton:
			_seal_t = 0.0 if e.pressed else -1.0)
	_button(box, Rect2(26, 908, 829, 70), "Назад к войне", Color(0.45, 0.35, 0.2), func(): action_pressed.emit("back_to_war"))


func show_ceremony_counters(lines: Array, on_done: Callable) -> void:
	close_modal()
	_modal = Control.new()
	_modal.size = Vector2(VW, VH)
	_modal.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_modal)
	for i in lines.size():
		var l := _label(lines[i], 40)
		l.size = Vector2(VW, 60)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.position = Vector2(0, 230 + i * 64)
		l.modulate.a = 0.0
		_modal.add_child(l)
		var tw := create_tween()
		tw.tween_interval(i * 0.25)
		tw.tween_property(l, "modulate:a", 1.0, 0.35)
	var b := _button(_modal, Rect2(120, VH - 150, 700, 96), "Продолжить", Color(0.13, 0.4, 0.9), on_done)
	b.modulate.a = 0.0
	var tw2 := create_tween()
	tw2.tween_interval(1.2)
	tw2.tween_property(b, "modulate:a", 1.0, 0.3)


func toast(text: String) -> void:
	var l := _label(text, 24)
	l.size = Vector2(VW - 80, 40)
	l.position = Vector2(40, 300)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.autowrap_mode = TextServer.AUTOWRAP_WORD
	var bg := _panel(root, Rect2(30, 290, VW - 60, 70), _style(Color(0.05, 0.08, 0.14, 0.92), 14), Control.MOUSE_FILTER_IGNORE)
	root.add_child(l)
	var tw := create_tween()
	tw.tween_interval(2.0)
	tw.tween_property(l, "modulate:a", 0.0, 0.4)
	tw.parallel().tween_property(bg, "modulate:a", 0.0, 0.4)
	tw.tween_callback(func(): l.queue_free(); bg.queue_free())


func _process(delta: float) -> void:
	if _seal_t >= 0.0 and _seal_prog:
		_seal_t += delta
		_seal_prog.size.x = 829.0 * clampf(_seal_t / 0.8, 0.0, 1.0)
		if _seal_t >= 0.8:
			_seal_t = -1.0
			seal_done.emit()
