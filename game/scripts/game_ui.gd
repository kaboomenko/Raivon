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
	set_action("timer", "%d:%02d" % [seconds_left / 60, seconds_left % 60], "Финальный рывок!" if rush else "до конца наступления", Color(0.5, 0.2, 0.2) if rush else Color(0.2, 0.25, 0.4))


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
		buttons.append(_button(_modal, Rect2(60, VH - 262, 821, 92), "🎬 ×2 трофеи (реклама)", Color(0.85, 0.55, 0.1), dbl))
	buttons.append(_button(_modal, Rect2(60, VH - 150, 821, 96), "Продолжить", Color(0.13, 0.4, 0.9), done))
	for b in buttons:
		b.modulate.a = 0.0
		var tw2 := create_tween()
		tw2.tween_interval(1.2)
		tw2.tween_property(b, "modulate:a", 0.5, 0.3)
		tw2.tween_interval(maxf(0.0, active_after - 1.5))
		tw2.tween_property(b, "modulate:a", 1.0, 0.2)
	get_tree().create_timer(active_after).timeout.connect(func(): gate["open"] = true)


## Inbox (mail button): reports of raids, defenses, ultimatums. items: [{title, text, t (unix), read}]
func show_inbox(items: Array, now: int) -> void:
	var box := _modal_box(Rect2(50, 300, 841, 1060))
	_at(_label("✉ Донесения", 34), box, Vector2(36, 26))
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
		col.add_child(_label("Пока тихо. Здесь появятся донесения о набегах и обороне.", 22, MUTED, false))
	for i in range(items.size() - 1, -1, -1):
		var it: Dictionary = items[i]
		var card := PanelContainer.new()
		card.add_theme_stylebox_override("panel", _style(Color(0.1, 0.15, 0.25) if it.get("read", false) else Color(0.14, 0.22, 0.38), 12, EDGE, 2))
		var v := VBoxContainer.new()
		card.add_child(v)
		var ago := maxi(0, now - int(it["t"]))
		var when := "только что" if ago < 60 else ("%d мин назад" % (ago / 60) if ago < 3600 else "%d ч назад" % (ago / 3600))
		v.add_child(_label("%s  ·  %s" % [it["title"], when], 22))
		var body := _label(it["text"], 19, MUTED, false)
		body.autowrap_mode = TextServer.AUTOWRAP_WORD
		body.custom_minimum_size = Vector2(760, 0)
		v.add_child(body)
		col.add_child(card)
	_button(box, Rect2(24, 950, 793, 84), "Закрыть", Color(0.13, 0.4, 0.9), close_modal)


## AI ultimatum (canon §9.1): accept (cede the hex), pay tribute, or refuse (war).
func show_ultimatum(enemy: String, hex_name: String, tribute: int, can_pay: bool, left_sec: int, on_accept: Callable, on_pay: Callable, on_refuse: Callable) -> void:
	var box := _modal_box(Rect2(50, 380, 841, 860), true)
	var ink := Color(0.3, 0.08, 0.05)
	_at(_label("⚔ Ультиматум: %s" % enemy, 32, ink, false), box, Vector2(30, 26))
	var t := _label("«Отдай нам «%s» — или заплати дань %d золота. Иначе — война.»\n\nНа ответ: %s. Без ответа — война." % [hex_name, tribute, fmt_time(left_sec)], 23, Color(0.25, 0.16, 0.08), false)
	t.autowrap_mode = TextServer.AUTOWRAP_WORD
	_at(t, box, Vector2(30, 90), Vector2(780, 260))
	_button(box, Rect2(30, 380, 780, 96), "Принять: отдать «%s» (перемирие 24 ч)" % hex_name, Color(0.45, 0.35, 0.2), on_accept)
	var pay := _button(box, Rect2(30, 494, 780, 96), "Откупиться: %d золота" % tribute, Color(0.75, 0.55, 0.12), on_pay)
	pay.modulate.a = 1.0 if can_pay else 0.45
	_button(box, Rect2(30, 608, 780, 96), "⚔ Отказать — война!", Color(0.75, 0.16, 0.12), on_refuse)
	_button(box, Rect2(30, 722, 780, 84), "Подумать (ответ позже)", Color(0.3, 0.33, 0.42), close_modal)


func show_settings(sound_on: bool, on_sound: Callable, on_new_game: Callable) -> void:
	var box := _modal_box(Rect2(90, 470, 761, 600))
	_at(_label("Настройки", 36), box, Vector2(40, 30))
	_button(box, Rect2(40, 110, 681, 84), "🔊 Звук: вкл" if sound_on else "🔇 Звук: выкл", Color(0.2, 0.3, 0.45), func():
		on_sound.call()
		show_settings(not sound_on, on_sound, on_new_game))
	var hold := _panel(box, Rect2(40, 214, 681, 84), _style(Color(0.55, 0.16, 0.14), 14, Color(1, 1, 1, 0.5), 2))
	var prog := _panel(hold, Rect2(0, 0, 0, 84), _style(Color(1, 1, 1, 0.25), 14, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	var hl := _label("Новая игра (удерживайте)", 22)
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
	_at(_label("Прогресс сохраняется автоматически на устройстве.", 18, MUTED, false), box, Vector2(40, 330))
	_at(_label("Raivon: Territory Wars · тестовая сборка %s" % ProjectSettings.get_setting("application/config/version", "0.3"), 18, MUTED, false), box, Vector2(40, 366))
	_button(box, Rect2(40, 480, 681, 84), "Закрыть", Color(0.13, 0.4, 0.9), close_modal)


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


static func fmt_time(sec: int) -> String:
	if sec >= 3600:
		return "%d ч %02d мин" % [sec / 3600, (sec % 3600) / 60]
	if sec >= 60:
		return "%d:%02d" % [sec / 60, sec % 60]
	return "%d с" % sec


## items: [{id, name, level, max, busy, left, speed, cost: {res: n}, seconds, reason}]
func show_buildings(items: Array) -> void:
	if _bpanel == null:
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
	_bpanel.visible = true
	var keep := _bscroll.scroll_horizontal
	for c in _brow.get_children():
		_brow.remove_child(c)
		c.queue_free()
	for it in items:
		_brow.add_child(_building_card(it))
	_bscroll.set_deferred("scroll_horizontal", keep)


## Army tab: one card per army (strength, readiness, refill) and a «Новая армия» card (canon §8.1).
func show_armies(items: Array) -> void:
	show_buildings([])
	for c in _brow.get_children():
		c.queue_free()
	for it in items:
		_brow.add_child(_army_card(it))


func _army_card(it: Dictionary) -> Control:
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
			var sub := _label("сбор новобранцев", 15, MUTED, false)
			sub.position = Vector2(0, 104)
			sub.size = Vector2(150, 22)
			sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			card.add_child(sub)
			return card
		if it["locked"]:
			var m := _label("🔒 с УР%d" % int(it.get("need_dl", 3)), 20, MUTED, false)
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
		_card_button(card, "➕ Собрать", Color(0.2, 0.55, 0.3), func(): army_action.emit(-1, "train"), true)
		return card
	var big := _label("⚔ %d" % int(it["str"]), 28)
	big.position = Vector2(0, 34)
	big.size = Vector2(150, 40)
	big.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(big)
	var ready := float(it["str"]) / maxf(1.0, float(it["max"]))
	var bar := _panel(card, Rect2(14, 82, 122, 12), _style(Color(1, 1, 1, 0.1), 6, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	_panel(bar, Rect2(0, 0, 122 * ready, 12), _style(Color(0.3, 0.62, 1.0) if ready >= 0.5 else Color(1.0, 0.6, 0.25), 6, Color(0, 0, 0, 0), 0), Control.MOUSE_FILTER_IGNORE)
	var sub2 := _label("%d отр. · %d%%" % [int(it["slots"]), roundi(ready * 100.0)], 15, MUTED, false)
	sub2.position = Vector2(0, 100)
	sub2.size = Vector2(150, 22)
	sub2.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_child(sub2)
	if it["refilling"]:
		_card_button(card, "🎬 Пополнить", Color(0.85, 0.55, 0.1), func(): army_action.emit(id, "refill"), true)
	else:
		var ok := _label("Готова к бою", 16, Color(0.5, 1.0, 0.6))
		ok.position = Vector2(0, 142)
		ok.size = Vector2(150, 24)
		ok.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(ok)
	return card


## Diplomacy tab: a card per neighbour — leader, opinion, status, war / gift buttons (canon §10.6).
func show_diplomacy(items: Array) -> void:
	show_buildings([])
	for c in _brow.get_children():
		c.queue_free()
	for it in items:
		_brow.add_child(_diplomacy_card(it))


func _diplomacy_card(it: Dictionary) -> Control:
	var card := Panel.new()
	card.custom_minimum_size = Vector2(304, 178)
	var col: Color = it["color"]
	card.add_theme_stylebox_override("panel", _style(Color(0.1, 0.14, 0.22), 12, col, 3))
	card.mouse_filter = Control.MOUSE_FILTER_PASS
	var st := _label(it["state"], 18, col.lightened(0.3))
	st.position = Vector2(12, 6)
	card.add_child(st)
	var ld := _label("%s · %s" % [it["leader"], it["archetype"]], 14, MUTED, false)
	ld.position = Vector2(12, 32)
	ld.size = Vector2(284, 20)
	ld.clip_text = true
	card.add_child(ld)
	var v: float = it["opinion"]
	var op := _label("Мнение: %+d · %s" % [roundi(v), it["word"]], 16, Color(0.5, 1.0, 0.6) if v > 10.0 else (Color(1.0, 0.55, 0.45) if v < -10.0 else TEXT), false)
	op.position = Vector2(12, 56)
	card.add_child(op)
	var stt := _label(it["status"], 16, Color(1.0, 0.85, 0.4), false)
	stt.position = Vector2(12, 82)
	card.add_child(stt)
	var id: int = it["id"]
	var bw := _panel(card, Rect2(10, 128, 136, 40), _style(Color(0.75, 0.2, 0.15) if it["can_war"] else Color(0.3, 0.33, 0.4), 10, Color(1, 1, 1, 0.45), 2))
	bw.mouse_filter = Control.MOUSE_FILTER_PASS
	var lw := _label("⚔ Война", 17)
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
	var gl: int = it["gift_left"]
	var bg := _panel(card, Rect2(156, 128, 138, 40), _style(Color(0.2, 0.5, 0.35) if gl == 0 else Color(0.3, 0.33, 0.4), 10, Color(1, 1, 1, 0.45), 2))
	bg.mouse_filter = Control.MOUSE_FILTER_PASS
	var lg := _label(("🎁 %d зол." % int(it["gift_cost"])) if gl == 0 else "🎁 " + fmt_time(gl), 16)
	lg.size = Vector2(138, 40)
	lg.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lg.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	bg.add_child(lg)
	bg.gui_input.connect(func(e): if _is_tap(e): diplomacy_action.emit(id, "gift"))
	return card


func hide_buildings() -> void:
	if _bpanel:
		_bpanel.visible = false


func _building_card(it: Dictionary) -> Control:
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
	var lv := _label("ур. %d / %d" % [it["level"], it["max"]], 15, MUTED, false)
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
		_card_button(card, "⚡ бесплатно" if sp == 0 else "⚡ %d" % sp, Color(0.85, 0.55, 0.1), func(): building_speedup.emit(id), sp > 0)
		return card
	if int(it["level"]) >= int(it["max"]) and String(it["reason"]) != "":
		var m := _label(it["reason"], 15, MUTED, false)
		m.position = Vector2(8, 66)
		m.size = Vector2(134, 70)
		m.autowrap_mode = TextServer.AUTOWRAP_WORD
		m.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.add_child(m)
		return card
	var y := 60.0
	var cost: Dictionary = it["cost"]
	for r in cost:
		var row := HBoxContainer.new()
		row.position = Vector2(26, y)
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var ic := TextureRect.new()
		ic.texture = _icon(r)
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.custom_minimum_size = Vector2(24, 24)
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(ic)
		row.add_child(_label(str(cost[r]), 18, TEXT, false))
		card.add_child(row)
		y += 26
	var tl := _label("⏱ " + fmt_time(int(it["seconds"])), 15, MUTED, false)
	tl.position = Vector2(26, y)
	card.add_child(tl)
	var ok: bool = String(it["reason"]) == ""
	_card_button(card, "⬆ Улучшить", Color(0.2, 0.55, 0.3) if ok else Color(0.3, 0.33, 0.4), func():
		if ok:
			building_upgrade.emit(id)
		else:
			toast(it["reason"]), true)
	return card


func _card_button(card: Control, text: String, color: Color, cb: Callable, _enabled: bool) -> void:
	var b := _panel(card, Rect2(8, 134, 134, 38), _style(color, 10, Color(1, 1, 1, 0.45), 2))
	b.mouse_filter = Control.MOUSE_FILTER_PASS
	var l := _label(text, 17)
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
	_coach_lbl.size = Vector2(576, 76)
	_coach_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD
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
	_process_coach(delta)
	if _seal_t >= 0.0 and _seal_prog:
		_seal_t += delta
		_seal_prog.size.x = 829.0 * clampf(_seal_t / 0.8, 0.0, 1.0)
		if _seal_t >= 0.8:
			_seal_t = -1.0
			seal_done.emit()
