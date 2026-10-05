extends Node3D
## Game controller: wires the deterministic sim (scripts/sim/*) to the 3D map (map_view.gd), the camera,
## the static HUD frame (hud.gd) and the mode UI (game_ui.gd).
## Modes: MAP → (declare) WAR → BATTLE (90 s offensive) → RESULT → WAR … → PEACE → CEREMONY → MAP.
##
## Debug / CI args (after `--`): --zoom=0.6  --select=q,r  --shot=PATH
##   --demo=battle:SECONDS | result | peace | ceremony:SECONDS  — scripted states for headless screenshots.

const Types := preload("res://scripts/sim/types.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const War := preload("res://scripts/sim/war.gd")
const Battle := preload("res://scripts/sim/battle.gd")
const BattleAI := preload("res://scripts/sim/battle_ai.gd")
const Armies := preload("res://scripts/sim/armies.gd")
const Topology := preload("res://scripts/sim/topology.gd")
const MapView := preload("res://scripts/map_view.gd")
const Hud := preload("res://scripts/hud.gd")
const CameraRig := preload("res://scripts/camera_rig.gd")
const GameUI := preload("res://scripts/game_ui.gd")
const Sfx := preload("res://scripts/sfx.gd")
const Save := preload("res://scripts/save.gd")
const Economy := preload("res://scripts/sim/economy.gd")
const Deposits := preload("res://scripts/sim/deposits.gd")

enum Mode { MAP, WAR, BATTLE, RESULT, PEACE, CEREMONY }

const MAP_SEED := 20261004
const HAND := ["attack", "breakthrough", "airstrike", "encircle", "defense"]
const CHAPTER_GOAL := 20
const TRUCE_SEC := 30 * 60
const KIND_NAMES := {"capital": "Столица", "city": "Город", "farm": "Ферма", "mine": "Рудник", "port": "Порт", "military_base": "Военная база"}
const TERRAIN_NAMES := {"plain": "Равнина", "forest": "Лес", "hills": "Холмы", "water": "Озеро", "mountain": "Горы"}

var sim  # sim World
var armies: Array = []
var war := {}
var battle = null
var ai = null
var flag_hex := -1
var mode := Mode.MAP
var truce := {}  # state -> unix time when war may be declared again
var save_enabled := true  # tests switch it off before adding the scene
var ftue := 0  # first-war tutorial step (canon §14.3); 0 = finished / off
var _ftue_shown := -1
var _ftue_t := 0.0
var _mill := -1
var _ftue_next := 0  # step to resume after the peace ceremony
var _raid := {}  # FTUE marauder raid: {hex, at}
var econ  # Economy (scripts/sim/economy.gd)
var deposits  # Deposits (scripts/sim/deposits.gd)
var first_convoy_done := false
var colonizing := {}  # hex -> unix time the colonization finishes
var colonized := 0  # colonizations so far (price and timer grow, 05 §colonization)
var time_offset := 0  # debug fast-forward for demos/tests (--skip=SECONDS)
var tab := "army"
var inbox: Array = []  # reports: {t, title, text, read}
var ultimatum := {}  # active AI ultimatum: {state, hex, tribute, deadline}
var ultimatum_at := 0  # 0 = not scheduled yet, -1 = done; unix time of the scripted Barons ultimatum
const WAR_CAP_SEC := 2 * 3600  # chapter I war cap (canon §9.1)
const STRIKE_WARN_SEC := 20 * 60  # strike announced 20 min ahead (canon §9.11)
var _econ_acc := 1.0

var map_view: Node3D
var rig: Node3D
var hud: CanvasLayer
var ui: CanvasLayer
var selection: MeshInstance3D
var sfx: Node
var selected := -1

var _acc := 0.0
var _ev_i := 0
var _drag_army := -1
var _drag_line: MeshInstance3D
var _drag_lbl: Label3D
var _last_tap := {"army": -1, "t": 0}
var _demands: Array = []
var _chosen := {}
var _ceremony := {}
var _minimap_snap := ""


func _ready() -> void:
	_environment()
	sfx = Sfx.new()
	add_child(sfx)
	sim = MapGen.generate_chapter_one(MAP_SEED)
	armies = Armies.starting_armies(sim)
	econ = Economy.new(sim, now_s())
	deposits = Deposits.new(MAP_SEED ^ 0x5EED)
	save_enabled = save_enabled and not _scripted_run()
	var loaded := false
	if save_enabled:
		var d := Save.read()
		loaded = not d.is_empty() and Save.apply(self, d)
	map_view = MapView.new()
	add_child(map_view)
	map_view.set_world(sim)
	rig = CameraRig.new()
	add_child(rig)
	rig.bounds = Rect2(-6.5, -7.5, 13.0, 12.0)
	rig.hex_tapped.connect(_on_hex_tapped)
	rig.order_drag.connect(_on_order_drag)
	rig.order_filter = _order_filter
	hud = Hud.new()
	hud.world = map_view
	add_child(hud)
	hud.button_pressed.connect(_on_hud_button)
	ui = GameUI.new()
	add_child(ui)
	ui.action_pressed.connect(_on_action)
	ui.card_drop.connect(_on_card_drop)
	ui.card_drag.connect(_on_card_drag)
	ui.demand_toggled.connect(_on_demand_toggled)
	ui.seal_done.connect(_sign_peace)
	ui.building_upgrade.connect(_on_building_upgrade)
	ui.building_speedup.connect(_on_building_speedup)
	_make_selection()
	_make_drag_marker()
	_focus_front(0.7)
	map_view.sync_armies(armies, null)
	_set_mode(Mode.WAR if not war.is_empty() else Mode.MAP)
	_econ_tick()
	if loaded:
		ui.toast("С возвращением! Доход ждёт на гексах — коснитесь монеты")
	elif save_enabled:
		ftue = 1
	_burned_mill()
	await get_tree().process_frame
	_handle_args()


# ====================================================================== scene setup

func _environment() -> void:
	var we := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.13, 0.16, 0.2)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.62, 0.7, 0.85)
	e.ambient_light_energy = 0.5
	e.ssao_enabled = true
	e.ssao_radius = 1.2
	e.ssao_intensity = 2.5
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	e.tonemap_exposure = 1.05
	e.glow_enabled = true
	e.glow_intensity = 1.4
	e.glow_strength = 1.15
	e.glow_bloom = 0.08
	e.glow_hdr_threshold = 0.75
	e.fog_enabled = true
	e.fog_light_color = Color(0.55, 0.62, 0.72)
	e.fog_density = 0.003
	e.adjustment_enabled = true
	e.adjustment_saturation = 1.12
	e.adjustment_contrast = 1.06
	we.environment = e
	add_child(we)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -35, 0)
	sun.light_color = Color(1.0, 0.93, 0.82)
	sun.light_energy = 1.5
	sun.shadow_enabled = true
	sun.shadow_blur = 1.5
	sun.directional_shadow_max_distance = 60
	add_child(sun)


func _make_selection() -> void:
	selection = MeshInstance3D.new()
	var tm := TorusMesh.new()
	tm.inner_radius = 0.86
	tm.outer_radius = 0.96
	tm.rings = 6
	tm.ring_segments = 6
	selection.mesh = tm
	selection.rotation.y = PI / 6.0
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = Color(1.0, 0.95, 0.7)
	selection.material_override = m
	selection.scale = Vector3(1, 0.15, 1)
	selection.visible = false
	add_child(selection)


func _make_drag_marker() -> void:
	_drag_line = MeshInstance3D.new()
	_drag_line.mesh = ImmediateMesh.new()
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.vertex_color_use_as_albedo = true
	m.no_depth_test = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_drag_line.material_override = m
	add_child(_drag_line)
	_drag_lbl = Label3D.new()
	_drag_lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_drag_lbl.no_depth_test = true
	_drag_lbl.font_size = 72
	_drag_lbl.outline_size = 16
	_drag_lbl.pixel_size = 0.006
	_drag_lbl.visible = false
	add_child(_drag_lbl)


func _focus_front(z: float) -> void:
	var cap: int = sim.states[Types.PLAYER]["capital_id"]
	var p: Vector3 = map_view.cell_world(cap)
	var front := Vector3.ZERO
	var n := 0
	for a in armies:
		if a["side"] == Types.PLAYER:
			front += map_view.cell_world(a["hex"])
			n += 1
	if n > 0:
		p = p.lerp(front / n, 0.7)
	rig.focus(p, z)
	rig.zoom = z


# ====================================================================== modes

func _set_mode(m: Mode) -> void:
	mode = m
	_refresh_ui()
	if m in [Mode.MAP, Mode.WAR, Mode.RESULT]:
		_autosave()


func _autosave() -> void:
	if save_enabled:
		Save.save(self)


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_PAUSED or what == NOTIFICATION_WM_CLOSE_REQUEST:
		if mode != Mode.BATTLE and mode != Mode.CEREMONY:
			_autosave()


func _scripted_run() -> bool:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--demo") or a.begins_with("--shot") or a == "--fresh":
			return true
	return false


func _refresh_ui() -> void:
	var enemy: int = war.get("enemy", -1)
	map_view.at_war_with = enemy
	var ws := War.war_score(sim, war) if not war.is_empty() else {}
	ui.set_control(ws.get("score", 0.0), ws.get("control", 50), _state_name(enemy), not war.is_empty() and mode in [Mode.WAR, Mode.BATTLE, Mode.RESULT])
	ui.set_battle(mode == Mode.BATTLE and battle != null, battle.energy[Types.PLAYER] if battle else 0, Battle.ENERGY_UNIT, _cooldowns(), battle.seconds_left() if battle else 0, battle != null and battle.is_rush())
	if mode not in [Mode.MAP, Mode.WAR]:
		ui.hide_buildings()
	elif tab == "buildings" and econ != null:
		ui.show_buildings(_building_items(now_s()))
	match mode:
		Mode.MAP:
			ui.set_action("", "")
			_primary_for_selection()
		Mode.WAR:
			ui.set_action("peace", "🕊 Мир", "счёт %+.1f" % ws.get("score", 0.0), Color(0.12, 0.36, 0.2))
			ui.set_primary("offensive", "⚔ Наступление", Color(0.8, 0.22, 0.16))
		Mode.BATTLE:
			ui.set_primary("retreat", "↩ Отступить", Color(0.32, 0.36, 0.46))
		_:
			ui.set_action("", "")
			ui.set_primary("", "")


func _primary_for_selection() -> void:
	if selected < 0:
		ui.set_primary("pick_target", "⚔ Выбрать цель", Color(0.8, 0.22, 0.16))
		return
	var c: Dictionary = sim.cells[selected]
	var dep: Dictionary = deposits.at(selected)
	if not dep.is_empty():
		var cv: Dictionary = deposits.convoy_for(selected)
		if not cv.is_empty():
			ui.set_primary("", "🐴 Обоз · %s" % GameUI.fmt_time(int(cv["back"]) - now_s()), Color(0.3, 0.33, 0.42), false)
		else:
			var reason: String = deposits.can_send(sim, selected, econ.dev_level())
			ui.set_primary("convoy", "🐴 Отправить обоз" if reason == "" else reason, Color(0.8, 0.6, 0.1), reason == "")
		return
	if not Types.is_passable(c):
		ui.set_primary("", "")
	elif colonizing.has(selected):
		var left: int = int(colonizing[selected]) - now_s()
		var price := Economy.speedup_price(left)
		ui.set_primary("colonize_now", "⚡ Завершить" if price == 0 else "⚡ Ускорить · %d" % price, Color(0.85, 0.55, 0.1))
	elif c["owner"] == Types.NOBODY and _touches_player(selected):
		var cost := _colonize_cost()
		ui.set_primary("colonize", "⛳ %d зол. · %s" % [cost, GameUI.fmt_time(_colonize_seconds())], Color(0.2, 0.55, 0.3), econ.res["gold"] >= cost and colonizing.is_empty())
	elif c["owner"] != Types.PLAYER and c["owner"] != Types.NOBODY:
		var left := _truce_left(c["owner"])
		if left > 0:
			ui.set_primary("truce", "🕊 Перемирие %d:%02d" % [left / 60, left % 60], Color(0.3, 0.35, 0.45), false)
		elif MapGen.core_of(sim, c["owner"]).has(selected):
			ui.set_primary("core", "Ядро неприкосновенно", Color(0.3, 0.35, 0.45), false)
		else:
			ui.set_primary("declare", "⚔ Объявить войну", Color(0.8, 0.22, 0.16))
	elif c["owner"] == Types.PLAYER:
		ui.set_primary("upgrade", "⬆ Улучшить", Color(0.13, 0.4, 0.9))
	else:
		ui.set_primary("", "")


func _on_action(kind: String) -> void:
	match kind:
		"declare":
			_declare(sim.cells[selected]["owner"], selected)
		"colonize":
			_colonize(selected)
		"pick_target":
			_pick_target()
		"upgrade":
			_open_tab("buildings")
		"colonize_now":
			_speedup_colonize(selected)
		"convoy":
			_send_convoy(selected)
		"offensive":
			_start_offensive()
		"retreat":
			if mode == Mode.BATTLE and battle:
				battle.issue(Types.PLAYER, {"t": "retreat"})
		"peace":
			_open_peace()
		"back_to_war":
			ui.close_modal()
			_set_mode(Mode.WAR)


func _on_hud_button(name: String) -> void:
	sfx.play("tap")
	match name:
		"gear":
			if mode in [Mode.MAP, Mode.WAR]:
				ui.show_settings(sfx.enabled, func(): sfx.enabled = not sfx.enabled, _new_game)
		"target":
			rig.focus(_front_center() if mode == Mode.BATTLE else _war_or_front_center())
		"pin":
			rig.focus(map_view.cell_world(sim.states[Types.PLAYER]["capital_id"]))
		"fort":
			_fort_action()
		"trophy":
			ui.toast("Глава I «Долина»: %d / %d гексов" % [_player_hexes(), CHAPTER_GOAL])
		"book":
			ui.toast("Летопись откроется после главы I")
		"mail":
			if not ultimatum.is_empty():
				_show_ultimatum()
			else:
				ui.show_inbox(inbox, now_s())
				for it in inbox:
					it["read"] = true
				hud.set_mail(0)
		"tab_buildings", "tab_army":
			_open_tab(name.substr(4))
		"tab_development":
			ui.toast("Исследования откроются на УР2")
		"tab_diplomacy":
			ui.toast("Дипломатия: перемирия и мнение соседей — скоро")
		"tab_world":
			ui.toast("Глава I «Долина»: %d / %d гексов" % [_player_hexes(), CHAPTER_GOAL])


func _war_or_front_center() -> Vector3:
	if not war.is_empty():
		return map_view.cell_world(war["goal"])
	var g := War.recommend_goals(sim, MapGen.BARONS, 1)
	return map_view.cell_world(g[0]) if g.size() > 0 else rig.target


func _new_game() -> void:
	Save.wipe()
	get_tree().reload_current_scene()


# ====================================================================== map mode

func _on_hex_tapped(c: Vector2i) -> void:
	var id: int = sim.id_at(c.x, c.y)
	if mode == Mode.BATTLE:
		_battle_tap(id)
		return
	if mode not in [Mode.MAP, Mode.WAR]:
		return
	if id >= 0 and map_view.has_bubble(id):
		_collect_all()
		return
	_select(id)


func _select(id: int) -> void:
	selected = id
	if id < 0:
		selection.visible = false
		_refresh_ui()
		return
	selection.position = map_view.cell_world(id) + Vector3(0, 0.06, 0)
	selection.visible = true
	sfx.play("tap")
	hud.show_tile(_describe(id))
	_refresh_ui()
	if mode == Mode.WAR:
		var c: Dictionary = sim.cells[id]
		if c["controller"] != c["owner"]:
			ui.toast("%s: оккупирован (%s). Станет вашим только по мирному договору." % [_cell_name(id), _state_name(c["controller"])])


func _describe(id: int) -> Dictionary:
	var c: Dictionary = sim.cells[id]
	var own: int = c["owner"]
	var owner_text: String = "Ваша территория" if own == Types.PLAYER else _state_name(own)
	if c["controller"] != own:
		owner_text += " · оккупирован"
	var bonus := "Ценность %d" % c["value"]
	if c["terrain"] == "forest":
		bonus += " · +25% защ."
	elif c["terrain"] == "hills":
		bonus += " · +50% защ."
	if c["fort"] > 0:
		bonus += " · форт %d" % c["fort"]
	if not Types.is_passable(c):
		bonus = "Непроходимо"
	elif c["controller"] == Types.PLAYER:
		var inc: Dictionary = econ.hex_income(sim, id)
		var parts := PackedStringArray()
		for r in inc:
			if int(inc[r]) > 0:
				parts.append("+%d %s/ч" % [inc[r], {"gold": "зол.", "food": "еды", "metal": "мет."}.get(r, r)])
		if parts.size() > 0:
			bonus = " · ".join(parts)
	var dep: Dictionary = deposits.at(id) if deposits != null else {}
	if not dep.is_empty():
		var rn := {"gold": "золота", "food": "еды", "metal": "металла"}
		bonus = "Залежь: %d %s · сбор %s" % [int(dep["amount"]), rn.get(String(dep["res"]), ""), GameUI.fmt_time(int(dep["gather_sec"]))]
		return {"title": "%s (%s)" % [Deposits.NAMES.get(String(dep["res"]), "Залежь"), dep["size"]], "owner": owner_text,
			"owner_color": Color(1.0, 0.85, 0.3), "bonus": bonus, "attackable": false}
	return {
		"title": _cell_name(id),
		"owner": owner_text,
		"owner_color": map_view.state_color(own).lightened(0.25),
		"bonus": bonus,
		"attackable": own != Types.PLAYER and own != Types.NOBODY,
	}


func _cell_name(id: int) -> String:
	var c: Dictionary = sim.cells[id]
	if c["name"] != "":
		return c["name"]
	if KIND_NAMES.has(c["kind"]):
		return KIND_NAMES[c["kind"]]
	return TERRAIN_NAMES.get(c["terrain"], "Гекс")


func _state_name(s: int) -> String:
	if s < 0 or s >= sim.states.size():
		return ""
	return sim.states[s]["name"]


func _touches_player(id: int) -> bool:
	for n in sim.neighbors[id]:
		if n >= 0 and sim.cells[n]["owner"] == Types.PLAYER:
			return true
	return false


func _player_hexes() -> int:
	var n := 0
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and Types.is_passable(c):
			n += 1
	return n


func _truce_left(s: int) -> int:
	return maxi(0, int(truce.get(s, 0) - Time.get_unix_time_from_system()))


## FTUE helper: jump to the best war goal against the Barons (or a free hex to colonize during a truce).
func _pick_target() -> void:
	var target := -1
	if _truce_left(MapGen.BARONS) == 0:
		var g := War.recommend_goals(sim, MapGen.BARONS, 1)
		target = g[0] if g.size() > 0 else -1
	if target < 0:
		for c in sim.cells:
			if c["owner"] == Types.NOBODY and Types.is_passable(c) and _touches_player(c["id"]):
				target = c["id"]
				break
	if target < 0:
		ui.toast("Пока целей нет — дождитесь конца перемирия")
		return
	rig.focus(map_view.cell_world(target))
	_select(target)


func _colonize_cost() -> int:
	return int(ceil(50.0 * Economy.PROD_MULT100[econ.dev_level()] / 100.0 * (1.0 + 0.15 * colonized)))


func _colonize_seconds() -> int:
	return 60 if colonized < 3 else (300 if colonized < 6 else (900 if colonized < 10 else 1800))


## Colonization (canon §12.1): gold and a timer, one at a time, no builder needed.
func _colonize(id: int) -> void:
	if not colonizing.is_empty():
		ui.toast("Уже идёт колонизация")
		return
	var cost := _colonize_cost()
	if econ.res["gold"] < cost:
		ui.toast("Не хватает золота")
		return
	econ.res["gold"] -= cost
	colonizing[id] = now_s() + _colonize_seconds()
	sfx.play("coin")
	map_view.burst(id, Color(1.0, 0.85, 0.3))
	ui.toast("Поселенцы в пути: «%s» станет вашим через %s" % [_cell_name(id), GameUI.fmt_time(_colonize_seconds())])
	_autosave()
	_econ_tick()


func _speedup_colonize(id: int) -> void:
	if not colonizing.has(id):
		return
	var price := Economy.speedup_price(int(colonizing[id]) - now_s())
	if econ.res["raivite"] < price:
		ui.toast("Не хватает Райвитов")
		return
	econ.res["raivite"] -= price
	colonizing[id] = now_s()
	_econ_tick()


func _finish_colonize(id: int) -> void:
	colonizing.erase(id)
	map_view.hex_label(id, "")
	colonized += 1
	var c: Dictionary = sim.cells[id]
	c["owner"] = Types.PLAYER
	c["controller"] = Types.PLAYER
	map_view.burst(id, MapView.C_PLAYER, true)
	map_view.floater(id, "+1 гекс", Color(0.75, 0.85, 1.0))
	sfx.play("coin")
	sfx.haptic(20)
	map_view.refresh_hex(id)
	map_view.pop_hex(id)
	_autosave()
	map_view.mark_dirty()
	ui.toast("Колонизирован «%s» · Глава I: %d / %d" % [_cell_name(id), _player_hexes(), CHAPTER_GOAL])
	_select(id)


func _declare(enemy: int, goal: int) -> void:
	_ensure_armies_for(enemy)
	war = War.declare_war(sim, enemy, goal)
	war["started"] = now_s()
	map_view.at_war_with = enemy
	map_view.mark_dirty()
	map_view.sync_armies(armies, null)
	map_view.burst(goal, MapView.C_WAR, true)
	sfx.play("warn")
	sfx.haptic(60)
	ui.toast("Война объявлена: %s! Цель — «%s» (+10 к счёту)" % [_state_name(enemy), _cell_name(goal)])
	if ftue == 1:
		ftue = 2
	_set_mode(Mode.WAR)


## Every state at war needs field armies; Hamlets have none at the start (port of the TS client).
func _ensure_armies_for(state: int) -> void:
	for a in armies:
		if a["side"] == state:
			return
	var front: Array = []
	for c in sim.cells:
		if c["owner"] == state and Types.is_passable(c) and _touches_player(c["id"]):
			front.append(c["id"])
	var cap: int = sim.states[state]["capital_id"]
	var dl: int = sim.states[state]["dev_level"]
	var id := 100 + state * 10
	var first: int = front[0] if front.size() > 0 else cap
	armies.append(Armies.infantry_army(id, state, first, 3, dl))
	if front.size() > 1:
		armies.append(Armies.infantry_army(id + 1, state, front[1], 3, dl))


## Put every army back on a free hex its side controls (after treaties, routs, colonization).
func _normalize_armies() -> void:
	var occupied := {}
	for a in armies:
		var key := "%d:%d" % [a["side"], a["hex"]]
		var c: Dictionary = sim.cells[a["hex"]]
		if c["controller"] == a["side"] and not occupied.has(key):
			occupied[key] = true
			continue
		var seen := {a["hex"]: true}
		var q: Array = [a["hex"]]
		while not q.is_empty():
			var h: int = q.pop_front()
			var cc: Dictionary = sim.cells[h]
			if cc["controller"] == a["side"] and cc["owner"] == a["side"] and not occupied.has("%d:%d" % [a["side"], h]):
				a["hex"] = h
				occupied["%d:%d" % [a["side"], h]] = true
				break
			for n in sim.neighbors[h]:
				if n >= 0 and not seen.has(n) and Types.is_passable(sim.cells[n]):
					seen[n] = true
					q.append(n)


# ====================================================================== battle

func _start_offensive() -> void:
	var enemy: int = war["enemy"]
	for a in armies:
		# Between offensives both sides rest and refill (full game: readiness timers, canon 11 §15.1).
		a["str"] = a["max_str"]
		a["routed"] = false
		a["hold"] = false
	_normalize_armies()
	flag_hex = war["goal"] if sim.cells[war["goal"]]["controller"] == enemy else -1
	if flag_hex < 0:
		var g := War.recommend_goals(sim, enemy, 1)
		flag_hex = g[0] if g.size() > 0 else -1
	var opts := {"attacker": Types.PLAYER, "defender": enemy, "ai_energy_mult": 600, "cards": HAND}
	if ftue > 0:
		# the first offensive is short and the Barons do not play cards (canon §14.3)
		opts["ai_energy_mult"] = 0
		opts["ticks"] = 60 * Battle.TICKS_PER_SEC
		ftue = 3
	battle = Battle.new(sim, armies, opts)
	ai = BattleAI.new(enemy)
	_acc = 0.0
	_ev_i = 0
	_select(-1)
	rig.focus(_front_center(), 0.5)
	_set_mode(Mode.BATTLE)
	sfx.play("warn")
	if ftue == 0:
		ui.toast("В бой! Тяните от армии к врагу или бросьте карту на гекс")


## Middle of the fighting: the player's armies and the flag hex, nudged toward the enemy.
func _front_center() -> Vector3:
	var p := Vector3.ZERO
	var n := 0
	for a in armies:
		if a["side"] == Types.PLAYER and a["str"] > 0:
			p += map_view.cell_world(a["hex"])
			n += 1
	if flag_hex >= 0:
		p += map_view.cell_world(flag_hex)
		n += 1
	return p / n - Vector3(0, 0, 0.4) if n > 0 else rig.target


func _cooldowns() -> Dictionary:
	var out := {}
	if battle:
		for c in HAND:
			out[c] = int(battle.cooldown.get("%d:%s" % [Types.PLAYER, c], 0))
	return out


func _battle_step() -> void:
	ai.think(battle)
	battle.step()
	var ws := War.war_score(sim, war)
	battle.last_stand = Types.PLAYER if ws["control"] <= 30 else -1
	while _ev_i < battle.events.size():
		_handle_event(battle.events[_ev_i])
		_ev_i += 1


func _handle_event(ev: Dictionary) -> void:
	var mine: bool = ev.get("side", -1) == Types.PLAYER
	match ev["type"]:
		"clash":
			sfx.play("clash", 0, -6.0)
		"capture":
			sfx.play("capture" if mine else "lost")
			map_view.smoke(ev["hex"], 5.0, true)
			map_view.burst(ev["hex"], MapView.C_PLAYER if mine else MapView.C_WAR, true)
			map_view.floater(ev["hex"], "Оккупирован!" if mine else "Потерян", Color(0.75, 0.85, 1.0) if mine else Color(1.0, 0.7, 0.7))
			if mine and ev["hex"] == war["goal"]:
				ui.toast("🚩 Цель войны взята: +10 к счёту")
		"repelled":
			sfx.play("repelled")
			map_view.floater(ev["hex"], "Атака отбита" if mine else "Отбились!", Color.WHITE)
		"routed":
			var a = battle.army_by_id(ev["army"])
			if a != null:
				map_view.floater(a["hex"], "Армия разбита", Color(1.0, 0.7, 0.28))
		"card":
			sfx.play("boom" if ev["card"] == "airstrike" else "card")
			if ev["card"] == "airstrike":
				map_view.burst(ev["hex"], Color(1.0, 0.65, 0.2), true)
			else:
				map_view.burst(ev["hex"], Color(0.6, 0.82, 1.0) if mine else Color(1.0, 0.6, 0.6))
			if not mine:
				map_view.floater(ev["hex"], Battle.CARDS[ev["card"]]["name"], Color(1.0, 0.7, 0.7))


func _end_offensive() -> void:
	var res: Dictionary = battle.result()
	var stars := War.offensive_stars(res["captured"], flag_hex, res["routed_player_armies"])
	sfx.play("fanfare" if stars > 0 else "lost")
	if ftue > 0:
		ftue = 5 if stars > 0 else 2
	War.record_offensive(war, stars)
	var ws := War.war_score(sim, war)
	battle = null
	ai = null
	_normalize_armies()
	map_view.sync_armies(armies, null)
	_set_mode(Mode.RESULT)
	var reason: String = {"retreat": "Вы отступили", "wiped": "Все армии сломлены"}.get(res["reason"], "Время вышло")
	ui.show_result(stars, res["captured"].size(), res["lost"].size(), ws["score"], ws["control"], reason,
		func(): ui.close_modal(); _set_mode(Mode.WAR),
		func(): ui.close_modal(); _open_peace())


func _order_filter(screen: Vector2) -> bool:
	if mode != Mode.BATTLE or battle == null:
		return false
	var id: int = map_view.id_at_world(rig.ground_at(screen))
	return id >= 0 and battle.army_at(id, Types.PLAYER) != null


func _on_order_drag(phase: int, screen: Vector2) -> void:
	if battle == null:
		_drag_army = -1
		return
	var hex: int = map_view.id_at_world(rig.ground_at(screen))
	if phase == 0:
		var a = battle.army_at(hex, Types.PLAYER)
		_drag_army = a["id"] if a != null else -1
		return
	if _drag_army < 0:
		return
	var a = battle.army_by_id(_drag_army)
	if a == null:
		_drag_army = -1
		return
	var from: int = a["hex"]
	if phase == 1:
		_draw_order(from, hex)
		return
	# phase 2: release
	_clear_order()
	_drag_army = -1
	if hex == from or hex < 0:
		_battle_tap(from)
		return
	if not sim.neighbors[from].has(hex):
		ui.toast("Только на соседний гекс")
		return
	if battle.can_target(Types.PLAYER, hex):
		if battle.issue(Types.PLAYER, {"t": "attack", "army": a["id"], "target": hex}):
			sfx.play("attack")
			sfx.haptic(15)
			_ftue_attacked()
		else:
			ui.toast("Не хватает энергии (нужно 2)")
	elif sim.cells[hex]["controller"] == Types.PLAYER:
		if not battle.issue(Types.PLAYER, {"t": "move", "army": a["id"], "to": hex}):
			ui.toast("Гекс занят")


func _draw_order(from: int, to: int) -> void:
	var im: ImmediateMesh = _drag_line.mesh
	im.clear_surfaces()
	if to < 0 or to == from:
		_drag_lbl.visible = false
		return
	var col := Color(0.6, 0.8, 1.0)
	var text := ""
	var ok: bool = sim.neighbors[from].has(to)
	if ok and battle.can_target(Types.PLAYER, to):
		var f: float = battle.forecast(Types.PLAYER, [_drag_army], to)["f"]
		col = Color(0.35, 1.0, 0.45) if f >= 1.2 else (Color(1.0, 0.85, 0.3) if f >= 0.8 else Color(1.0, 0.35, 0.3))
		text = "×%.1f" % f
	elif not ok:
		col = Color(1, 1, 1, 0.4)
	var a: Vector3 = map_view.cell_world(from) + Vector3(0, 0.25, 0)
	var b: Vector3 = map_view.cell_world(to) + Vector3(0, 0.25, 0)
	var dir := (b - a).normalized()
	var side := dir.cross(Vector3.UP) * 0.13
	var tip := b - dir * 0.35
	im.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
	for v in [a + side, tip + side, tip - side, a + side, tip - side, a - side, tip + side * 2.6, b, tip - side * 2.6]:
		im.surface_set_color(col)
		im.surface_add_vertex(v)
	im.surface_end()
	_drag_lbl.visible = text != ""
	_drag_lbl.text = text
	_drag_lbl.modulate = col
	_drag_lbl.position = b + Vector3(0, 1.0, 0)


func _clear_order() -> void:
	(_drag_line.mesh as ImmediateMesh).clear_surfaces()
	_drag_lbl.visible = false


func _battle_tap(id: int) -> void:
	if id < 0 or battle == null:
		return
	var a = battle.army_at(id, Types.PLAYER)
	if a == null:
		var c: Dictionary = sim.cells[id]
		ui.toast("%s · ценность %d · %s" % [_cell_name(id), c["value"], _state_name(c["controller"])])
		return
	var now := Time.get_ticks_msec()
	if _last_tap["army"] == a["id"] and now - int(_last_tap["t"]) < 350:
		battle.issue(Types.PLAYER, {"t": "hold", "army": a["id"]})
		ui.toast("Держать позицию: +10% к защите" if not a["hold"] else "Позиция снята")
	else:
		ui.toast("Армия: сила %d / %d · двойной тап — держать позицию" % [roundi(a["str"] / 1000.0), roundi(a["max_str"] / 1000.0)])
	_last_tap = {"army": a["id"], "t": now}


func _on_card_drag(_card: String, screen: Vector2, active: bool) -> void:
	if not active or screen.y > GameUI.VH - 280:
		selection.visible = false
		return
	var id: int = map_view.id_at_world(rig.ground_at(screen))
	if id < 0:
		selection.visible = false
		return
	selection.position = map_view.cell_world(id) + Vector3(0, 0.06, 0)
	selection.visible = true


func _on_card_drop(card: String, screen: Vector2) -> void:
	selection.visible = false
	if battle == null:
		return
	var id: int = map_view.id_at_world(rig.ground_at(screen))
	if id < 0:
		return
	if battle.energy_points(Types.PLAYER) < Battle.CARDS[card]["cost"]:
		ui.toast("Не хватает энергии (нужно %d)" % Battle.CARDS[card]["cost"])
	elif not battle.card_ready(Types.PLAYER, card):
		ui.toast("Карта перезаряжается")
	elif battle.issue(Types.PLAYER, {"t": "card", "card": card, "target": id}):
		_ftue_attacked()
	else:
		ui.toast("Сюда нельзя: %s" % ("нужен свой гекс" if Battle.CARDS[card]["target"] == "own" else "нужен вражеский гекс рядом с армией"))


# ====================================================================== peace

func _open_peace() -> void:
	var ws := War.war_score(sim, war)
	if ws["score"] <= 0:
		_open_defeat_or_white(ws["score"])
		return
	_demands = War.available_demands(sim, war)
	for d in _demands:
		if d["kind"] == "annex":
			var h: int = d["hexes"][0]
			d["label"] = "%s (ценн. %d)" % [_cell_name(h), sim.cells[h]["value"]] + (" 🚩" if h == war["goal"] else "")
	_chosen = {}
	for d in War.recommend_package(sim, war, _demands, ws["score"]):
		_chosen[d["id"]] = true
	if ftue > 0:
		ftue = 6
	_set_mode(Mode.PEACE)
	_show_peace()


func _show_peace() -> void:
	var ws := War.war_score(sim, war)
	ui.show_peace(_state_name(war["enemy"]), ws["score"], ws["control"], _demands, _chosen)
	_highlight_demands()


func _highlight_demands() -> void:
	for d in _demands:
		if _chosen.has(d["id"]):
			for h in d["hexes"]:
				map_view.burst(h, Color(0.5, 0.8, 1.0))


func _on_demand_toggled(id: String) -> void:
	if _chosen.has(id):
		_chosen.erase(id)
	else:
		var used := 0.0
		var cost := 0.0
		for d in _demands:
			if _chosen.has(d["id"]):
				used += d["cost"]
			if d["id"] == id:
				cost = d["cost"]
		if used + cost > War.war_score(sim, war)["score"] + 0.0001:
			ui.toast("Не хватает военного счёта")
			return
		_chosen[id] = true
	_show_peace()


func _sign_peace() -> void:
	var before := MapGen.official_value(sim, Types.PLAYER)
	var hexes_before := _player_hexes()
	var old_player := {}
	for c in sim.cells:
		if c["owner"] == Types.PLAYER:
			old_player[c["id"]] = true
	var chosen: Array = []
	for d in _demands:
		if _chosen.has(d["id"]):
			chosen.append(d)
	var prev := {}
	for d in chosen:
		for h in d["hexes"]:
			prev[h] = sim.cells[h]["owner"]
	var enemy: int = war["enemy"]
	var res: Dictionary = War.apply_treaty(sim, war, chosen)
	sfx.play("seal")
	sfx.haptic(120)
	if ftue > 0:
		ftue = 0
		_ftue_next = 7
		ui.coach_hide()
		if _mill >= 0:
			map_view.clear_smoke(_mill)
	_normalize_armies()
	ui.close_modal()
	# Ink wave: hexes touching the old territory flip first, ~0.25 s per ring (canon §10.3).
	var annexed: Array = res["annexed"]
	var annexed_set := {}
	for id in annexed:
		annexed_set[id] = true
	var seeds: Array = []
	for id in annexed:
		for n in sim.neighbors[id]:
			if old_player.has(n):
				seeds.append(id)
				break
	if seeds.is_empty() and annexed.size() > 0:
		seeds = [annexed[0]]
	var rings := Topology.rings_from(sim, seeds, annexed_set)
	var flip := {}
	var max_ring := 0
	for id in annexed:
		var r: int = rings.get(id, 0)
		max_ring = maxi(max_ring, r)
		flip[id] = 1.6 + 0.25 * r + float((id * 37) % 7) * 0.02
	var cities := 0
	for id in annexed:
		if sim.cells[id]["kind"] == "city":
			cities += 1
	var lines: Array = []
	lines.append(("+%d гекс." % annexed.size() + (" · +%d город" % cities if cities > 0 else "")) if annexed.size() > 0 else "Земли не присоединены")
	lines.append("Держава %d → %d" % [before, MapGen.official_value(sim, Types.PLAYER)])
	lines.append("Глава I: %d → %d из %d" % [hexes_before, _player_hexes(), CHAPTER_GOAL])
	if res.get("gold_packs", 0) > 0:
		# a package = 4 h of the enemy's gold production (canon §10.1); the enemy economy is not modelled yet
		var gold := int(res["gold_packs"]) * 4 * maxi(60, int(econ.gross_per_hour(sim).get("gold", 0)))
		var got: Dictionary = econ.add_resources({"gold": gold})
		lines.append("💰 Контрибуция: +%d золота" % int(got.get("gold", 0)))
	if res.get("reparations", false):
		lines.append("📜 Репарации: 10% производства на 24 ч")
	truce[enemy] = Time.get_unix_time_from_system() + TRUCE_SEC
	if ultimatum_at == 0:
		ultimatum_at = now_s() + 2 * 3600  # scripted Barons ultimatum ~2 h later (canon §14.3)
	map_view.strike_arrow(-1, -1, "")
	map_view.prev_owner = prev
	map_view.flip_at = flip
	map_view.ceremony_t = 0.0
	var max_d := 0.0
	var center := _centroid(annexed)
	for id in annexed:
		max_d = maxf(max_d, map_view.cell_world(id).distance_to(center))
	# whole war zone + 2 hexes in frame (canon §10.3 step 2)
	var zoom_out := clampf(((max_d + 3.4) / 0.29 - 7.5) / 16.5, rig.zoom_target, 1.0)
	var last_flip := 1.6
	for id in flip:
		last_flip = maxf(last_flip, flip[id])
	_ceremony = {"t": 0.0, "lines": lines, "popped": {}, "counters": false, "zoom0": rig.zoom_target, "zoom1": zoom_out,
		"center": center, "counters_at": maxf(4.0, last_flip + 0.5), "goal_taken": annexed.has(war["goal"]),
		"gold_packs": int(res.get("gold_packs", 0))}
	war = {}
	flag_hex = -1
	_set_mode(Mode.CEREMONY)
	if annexed.size() > 0:
		rig.focus(center)


func _centroid(ids: Array) -> Vector3:
	if ids.is_empty():
		return rig.target
	var p := Vector3.ZERO
	for id in ids:
		p += map_view.cell_world(id)
	return p / ids.size()


func _step_ceremony(delta: float) -> void:
	_ceremony["t"] += delta
	var t: float = _ceremony["t"]
	map_view.ceremony_t = t
	var k := clampf((t - 0.8) / 0.8, 0.0, 1.0)
	rig.zoom_target = lerpf(float(_ceremony["zoom0"]), float(_ceremony["zoom1"]), k * k * (3.0 - 2.0 * k))
	for id in map_view.flip_at:
		if t >= map_view.flip_at[id] and not _ceremony["popped"].has(id):
			_ceremony["popped"][id] = true
			map_view.refresh_hex(id)  # buildings and flags switch to the player's style
			map_view.pop_hex(id)
			map_view.burst(id, MapView.C_PLAYER, true)
			sfx.play("pop", _ceremony["popped"].size() - 1)
			sfx.haptic(10)
	if t >= float(_ceremony["counters_at"]) and not _ceremony["counters"]:
		_ceremony["counters"] = true
		var cap: int = sim.states[Types.PLAYER]["capital_id"]
		var volleys := 5 if _ceremony["goal_taken"] else 2
		map_view.fireworks(map_view.cell_world(cap), volleys)
		sfx.play("fanfare")
		for i in volleys:
			get_tree().create_timer(0.45 * i + 0.3).timeout.connect(sfx.play.bind("firework", 0, -8.0))
		var active_after := maxf(0.5, 7.0 - t)
		ui.show_ceremony_counters(_ceremony["lines"], _end_ceremony, _double_trophies if int(_ceremony["gold_packs"]) > 0 else Callable(), active_after)


## Rewarded ad «×2 трофеи» — SDK stub until monetization lands (canon §14.10).
func _double_trophies() -> void:
	ui.toast("Тестовая сборка: реклама не подключена — трофеи удвоены")
	econ.add_resources({"gold": int(_ceremony["gold_packs"]) * 4 * maxi(60, int(econ.gross_per_hour(sim).get("gold", 0)))})
	_ceremony["gold_packs"] = 0
	_end_ceremony()


func _end_ceremony() -> void:
	ui.close_modal()
	if _ftue_next > 0:
		ftue = _ftue_next
		_ftue_next = 0
	map_view.ceremony_t = -1.0
	map_view.flip_at = {}
	map_view.prev_owner = {}
	map_view.mark_dirty()
	_ceremony = {}
	_set_mode(Mode.MAP)
	if _player_hexes() >= CHAPTER_GOAL:
		ui.toast("🌍 Глава I пройдена! Мир расширяется (скоро)")


func _open_defeat_or_white(score: float) -> void:
	var enemy: int = war["enemy"]
	if absf(score) < 10.0:
		ui.show_result(0, 0, 0, score, War.war_score(sim, war)["control"], "Белый мир: всё вернётся владельцам",
			func(): ui.close_modal(); _set_mode(Mode.WAR),
			func():
				War.white_peace(sim)
				_finish_war(enemy, "🕊 Белый мир подписан"))
		return
	var lost := _defeat_losses(enemy)
	ui.show_result(0, 0, lost.size(), score, War.war_score(sim, war)["control"], "Поражение: −%d гекс., грабёж 60%%" % lost.size(),
		func(): ui.close_modal(); _set_mode(Mode.WAR),
		func(): _apply_defeat(enemy, lost))


## Defeat (canon §9.14): the AI annexes what it occupies, ≤20% of value, ≤1 city, never the core.
func _defeat_losses(enemy: int) -> Array:
	var core := MapGen.core_of(sim, Types.PLAYER)
	var limit := int(MapGen.official_value(sim, Types.PLAYER) * 0.2)
	var cands: Array = []
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and c["controller"] == enemy:
			cands.append(c)
	cands.sort_custom(func(x, y): return x["value"] > y["value"])
	var taken := 0
	var cities := 0
	var lost: Array = []
	for c in cands:
		if core.has(c["id"]) or taken + int(c["value"]) > limit or (c["kind"] == "city" and cities >= 1):
			continue
		taken += c["value"]
		if c["kind"] == "city":
			cities += 1
		lost.append(c["id"])
	return lost


func _apply_defeat(enemy: int, lost: Array) -> void:
	for id in lost:
		sim.cells[id]["owner"] = enemy
		sim.cells[id]["controller"] = enemy
	War.white_peace(sim)
	var looted: Dictionary = econ.plunder(0.6)
	var msg := "Мир с потерями: −%d гекс., разграблено %d золота, %d еды, %d металла. Щит 24 ч и «Реванш» +15%%" % [lost.size(), int(looted.get("gold", 0)), int(looted.get("food", 0)), int(looted.get("metal", 0))]
	_post("Поражение в войне", msg)
	_finish_war(enemy, msg)


func _finish_war(enemy: int, msg: String) -> void:
	ui.close_modal()
	map_view.strike_arrow(-1, -1, "")
	truce[enemy] = Time.get_unix_time_from_system() + TRUCE_SEC
	war = {}
	_normalize_armies()
	map_view.sync_armies(armies, null)
	map_view.refresh_props()
	map_view.mark_dirty()
	_set_mode(Mode.MAP)
	ui.toast(msg)


# ====================================================================== economy (canon §4, §7)

func now_s() -> int:
	return int(Time.get_unix_time_from_system()) + time_offset


func _econ_tick() -> void:
	var now := now_s()
	for ev in econ.tick(sim, now):
		_econ_event(ev)
	for ev in deposits.tick(sim, econ.gross_per_hour(sim), now):
		if ev["type"] == "convoy_back":
			var got: Dictionary = econ.add_resources({String(ev["res"]): int(ev["amount"])})
			var n := int(got.get(String(ev["res"]), 0))
			var cap: int = sim.states[Types.PLAYER]["capital_id"]
			map_view.floater(cap, "+%d" % n, Color(1.0, 0.88, 0.4))
			sfx.play("coin")
			ui.toast("Обоз привёз: +%d %s" % [n, {"gold": "золота", "food": "еды", "metal": "металла"}.get(String(ev["res"]), "")])
	for h in colonizing.keys():
		if now >= int(colonizing[h]):
			_finish_colonize(h)
		else:
			map_view.hex_label(h, "⛳ " + GameUI.fmt_time(int(colonizing[h]) - now))
	hud.set_resources(econ.res, econ.income_per_hour(sim), econ.storage_cap(), econ.builders - econ.busy_builders(now), econ.builders)
	hud.set_level(econ.dev_level())
	hud.set_mail(_unread())
	_ai_tick(now)
	_update_bubbles()
	if tab == "buildings" and mode in [Mode.MAP, Mode.WAR]:
		ui.show_buildings(_building_items(now))
	if mode == Mode.MAP and selected >= 0:
		_primary_for_selection()


func _econ_event(ev: Dictionary) -> void:
	match ev.get("type", ""):
		"upgrade_done":
			var b: Dictionary = econ.building(int(ev["building"]))
			if String(b.get("type", "")) in ["fort", "tower"] and int(b.get("hex", -1)) >= 0:
				map_view.refresh_hex(int(b["hex"]))
				map_view.pop_hex(int(b["hex"]))
			var name: String = Economy.BUILDINGS[String(ev.get("building_type", b.get("type", "")))]["name"]
			ui.toast("%s: уровень %d готов!" % [name, int(ev["level"])])
			sfx.play("capture")
			if int(b.get("hex", -1)) >= 0:
				map_view.burst(int(b["hex"]), Color(1.0, 0.85, 0.3), true)
		"dev_level":
			ui.toast("🏰 Держава достигла УР %d! Новые постройки и уровни" % econ.dev_level())
			sfx.play("fanfare")
			_dl_ceremony()
		"building_unlocked":
			ui.toast("Открыто: %s" % Economy.BUILDINGS[String(ev.get("building_type", "market"))]["name"])
		"fort_refund":
			ui.toast("Укрепление на потерянном гексе разобрано, металл возвращён")


## DL-up (canon §6): the capital rebuilds first, then the rest of the land in rings, ~6 s in total.
func _dl_ceremony() -> void:
	var own := {}
	for c in sim.cells:
		if c["owner"] == Types.PLAYER:
			own[c["id"]] = true
	var cap: int = sim.states[Types.PLAYER]["capital_id"]
	var rings := Topology.rings_from(sim, [cap], own)
	var max_r := 1
	for id in rings:
		max_r = maxi(max_r, int(rings[id]))
	var step := minf(0.35, 5.0 / max_r)
	rig.focus(map_view.cell_world(cap))
	map_view.fireworks(map_view.cell_world(cap), 3)
	for id in rings:
		var t := 0.2 + step * int(rings[id])
		var tw := map_view.create_tween()
		tw.tween_interval(t)
		tw.tween_callback(map_view.refresh_hex.bind(id))
		tw.tween_callback(map_view.pop_hex.bind(id))
		tw.tween_callback(map_view.burst.bind(id, Color(1.0, 0.85, 0.35), int(rings[id]) == 0))
		tw.tween_callback(sfx.play.bind("pop", int(rings[id]), -4.0))


## Fort button: build a fortification on the selected own hex or upgrade the one standing there.
func _fort_action() -> void:
	if selected < 0 or sim.cells[selected]["owner"] != Types.PLAYER:
		ui.toast("Выберите свой гекс, чтобы поставить укрепление")
		return
	var now := now_s()
	econ.tick(sim, now)
	var fort: Dictionary = {}
	for b in econ.buildings_at(selected):
		if b["type"] == "fort":
			fort = b
	if fort.is_empty():
		var reason: String = econ.can_build(sim, "fort", selected, now)
		if reason != "" or not econ.start_build(sim, "fort", selected, now):
			ui.toast(reason if reason != "" else "Нельзя построить")
			return
		ui.toast("Укрепление строится: %s" % GameUI.fmt_time(int(econ.buildings_at(selected)[-1]["upgrade_end"]) - now))
	else:
		var reason2: String = econ.can_upgrade(fort, now)
		if reason2 != "" or not econ.start_upgrade(fort["id"], now):
			ui.toast(reason2 if reason2 != "" else "Нельзя улучшить")
			return
		ui.toast("Укрепление → ур. %d" % (int(fort["level"]) + 1))
	sfx.play("coin")
	map_view.burst(selected, Color(1.0, 0.85, 0.3))
	if ftue == 9:
		# scripted marauder raid breaks against the new fence (canon §14.3, 5:00–6:00)
		ftue = 0
		_raid = {"hex": selected, "at": now + 25}
		ui.coach_hide()
	_econ_tick()
	_autosave()


func _sync_deposits() -> void:
	var now := now_s()
	var view: Array = []
	for cv in deposits.convoys:
		var v: Dictionary = cv.duplicate()
		v["phase"] = Deposits.convoy_phase(cv, now)
		view.append(v)
	map_view.set_deposits(deposits.active if mode in [Mode.MAP, Mode.WAR] else [], view)


func _send_convoy(hex: int) -> void:
	var reason: String = deposits.can_send(sim, hex, econ.dev_level())
	if reason != "":
		ui.toast(reason)
		return
	deposits.send(sim, hex, econ.dev_level(), now_s(), not first_convoy_done)
	first_convoy_done = true
	if ftue == 8:
		ftue = 9
	var cv: Dictionary = deposits.convoy_for(hex)
	sfx.play("tap")
	ui.toast("Обоз в пути: вернётся через %s" % GameUI.fmt_time(int(cv["back"]) - now_s()))
	_primary_for_selection()
	_autosave()


func _update_bubbles() -> void:
	if mode not in [Mode.MAP, Mode.WAR]:
		map_view.set_bubbles({})
		return
	var data := {}
	for h in econ.stock:
		var st: Dictionary = econ.stock[h]
		var inc: Dictionary = econ.hex_income(sim, int(h))
		var best := ""
		for r in st:
			if best == "" or int(st[r]) > int(st[best]):
				best = r
		if best == "":
			continue
		var amount: int = st[best]
		if amount >= 10 and amount * 4 >= int(inc.get(best, 0)):
			data[int(h)] = {"res": best, "amount": amount}
	map_view.set_bubbles(data)


## «Собрать всё» (canon §4): any coin collects every hex.
func _collect_all() -> void:
	econ.tick(sim, now_s())
	var shown := {}
	for h in econ.stock:
		shown[h] = econ.stock[h].duplicate()
	var gained: Dictionary = econ.collect_all()
	var total := 0
	for r in gained:
		total += int(gained[r])
	if total == 0:
		ui.toast("Склад полон — улучшите Склад")
		return
	for h in shown:
		if map_view.has_bubble(int(h)):
			var st: Dictionary = shown[h]
			var best := ""
			for r in st:
				if best == "" or int(st[r]) > int(st[best]):
					best = r
			map_view.floater(int(h), "+%d" % int(st[best]), Color(1.0, 0.88, 0.4) if best == "gold" else (Color(0.95, 0.85, 0.5) if best == "food" else Color(0.85, 0.9, 1.0)))
	sfx.play("coin")
	sfx.haptic(15)
	ui.toast("Собрано: +%d золота · +%d еды · +%d металла" % [int(gained.get("gold", 0)), int(gained.get("food", 0)), int(gained.get("metal", 0))])
	_econ_tick()
	_autosave()


func _open_tab(t: String) -> void:
	tab = t
	hud.select_tab(t)
	if t == "buildings":
		ui.show_buildings(_building_items(now_s()))
	else:
		ui.hide_buildings()


func _building_items(now: int) -> Array:
	var items: Array = []
	for b in econ.buildings:
		var info: Dictionary = Economy.BUILDINGS[b["type"]]
		if info["class"] == "defense":
			continue
		var reason: String = econ.can_upgrade(b, now)
		if Economy.NO_HEX_REASON.values().has(reason):
			continue
		var cost: Dictionary = econ.upgrade_cost(b).duplicate()
		var secs: int = int(cost.get("seconds", 0))
		cost.erase("seconds")
		for r in cost.keys():
			if int(cost[r]) <= 0:
				cost.erase(r)
		var busy: bool = int(b["upgrade_end"]) > now
		items.append({"id": b["id"], "name": info["name"], "level": b["level"], "max": econ.max_level(b),
			"busy": busy, "left": int(b["upgrade_end"]) - now, "speed": econ.speedup_cost(b, now),
			"cost": cost, "seconds": secs, "reason": reason})
	items.sort_custom(func(x, y): return int(x["busy"]) > int(y["busy"]))
	return items


func _on_building_upgrade(id: int) -> void:
	var now := now_s()
	econ.tick(sim, now)
	var b: Dictionary = econ.building(id)
	var reason: String = econ.can_upgrade(b, now)
	if reason != "" or not econ.start_upgrade(id, now):
		ui.toast(reason if reason != "" else "Нельзя улучшить")
		return
	sfx.play("coin")
	sfx.haptic(20)
	ui.toast("%s → ур. %d · %s" % [Economy.BUILDINGS[b["type"]]["name"], int(b["level"]) + 1, GameUI.fmt_time(int(b["upgrade_end"]) - now)])
	if ftue == 7 and b["type"] == "residence":
		ftue = 8
	_econ_tick()
	_autosave()


func _on_building_speedup(id: int) -> void:
	var now := now_s()
	var b: Dictionary = econ.building(id)
	if econ.res["raivite"] < econ.speedup_cost(b, now):
		ui.toast("Не хватает Райвитов")
		return
	if econ.finish_now(id, now):
		_econ_tick()
		_autosave()


# ====================================================================== AI aggression (chapter I: scripted only)

func _post(title: String, text: String) -> void:
	inbox.append({"t": now_s(), "title": title, "text": text, "read": false})
	if inbox.size() > 40:
		inbox.pop_front()
	hud.set_mail(_unread())
	# TODO(push): local notification when the app is in background (decision 21: raids always notify)


func _unread() -> int:
	var n := 0
	for it in inbox:
		if not it.get("read", false):
			n += 1
	return n


func _ai_tick(now: int) -> void:
	if not _raid.is_empty() and now >= int(_raid["at"]) and mode in [Mode.MAP, Mode.WAR]:
		var h: int = _raid["hex"]
		_raid = {}
		map_view.burst(h, Color(1.0, 0.6, 0.3), true)
		map_view.floater(h, "Набег отбит!", Color(0.75, 0.85, 1.0))
		sfx.play("repelled")
		_post("Набег мародёров", "Мародёры с диких земель налетели на «%s» и разбились о плетень. Укрепления защищают гексы и склады." % _cell_name(h))
		ui.toast("Мародёры разбились о плетень! Обучение пройдено — дальше держава ваша.")
	if ultimatum_at > 0 and now >= ultimatum_at and ultimatum.is_empty() and war.is_empty() and mode == Mode.MAP and _truce_left(MapGen.BARONS) == 0:
		_issue_ultimatum(now)
	if not ultimatum.is_empty() and now >= int(ultimatum["deadline"]) and mode in [Mode.MAP, Mode.WAR]:
		_answer_ultimatum("refuse")
	if war.is_empty():
		return
	if war.has("strike_at"):
		var left := int(war["strike_at"]) - now
		if left <= 0 and mode in [Mode.MAP, Mode.WAR]:
			_resolve_strike()
		elif left > 0:
			map_view.strike_arrow(int(war["strike_from"]), int(war["strike_hex"]), "⚔ " + GameUI.fmt_time(left))
	if war.has("started") and now - int(war["started"]) >= WAR_CAP_SEC and mode in [Mode.MAP, Mode.WAR]:
		_war_cap()


func _issue_ultimatum(now: int) -> void:
	ultimatum_at = -1
	var core := MapGen.core_of(sim, Types.PLAYER)
	var best := -1
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and Types.is_passable(c) and not core.has(c["id"]) and _touches_owner(c["id"], MapGen.BARONS):
			if best < 0 or int(c["value"]) > int(sim.cells[best]["value"]):
				best = c["id"]
	if best < 0:
		return
	var tribute := 8 * maxi(60, int(econ.gross_per_hour(sim).get("gold", 0)))
	ultimatum = {"state": MapGen.BARONS, "hex": best, "tribute": tribute, "deadline": now + 4 * 3600}
	_post("Ультиматум: %s" % _state_name(MapGen.BARONS), "Требуют «%s» или %d золота. Ответ — 4 ч, иначе война." % [_cell_name(best), tribute])
	sfx.play("warn")
	sfx.haptic(60)
	rig.focus(map_view.cell_world(best))
	_show_ultimatum()


func _show_ultimatum() -> void:
	ui.show_ultimatum(_state_name(int(ultimatum["state"])), _cell_name(int(ultimatum["hex"])), int(ultimatum["tribute"]),
		econ.res["gold"] >= int(ultimatum["tribute"]), int(ultimatum["deadline"]) - now_s(),
		_answer_ultimatum.bind("accept"), _answer_ultimatum.bind("pay"), _answer_ultimatum.bind("refuse"))


func _answer_ultimatum(kind: String) -> void:
	if ultimatum.is_empty():
		return
	var enemy: int = ultimatum["state"]
	var hex: int = ultimatum["hex"]
	var now := now_s()
	match kind:
		"accept":
			sim.cells[hex]["owner"] = enemy
			sim.cells[hex]["controller"] = enemy
			truce[enemy] = now + 24 * 3600
			map_view.refresh_hex(hex)
			map_view.mark_dirty()
			_normalize_armies()
			_post("Уступка", "«%s» отдан. Перемирие 24 ч." % _cell_name(hex))
		"pay":
			if econ.res["gold"] < int(ultimatum["tribute"]):
				ui.toast("Не хватает золота")
				return
			econ.res["gold"] -= int(ultimatum["tribute"])
			truce[enemy] = now + 24 * 3600
			_post("Дань уплачена", "%d золота. Перемирие 24 ч." % int(ultimatum["tribute"]))
		"refuse":
			_ensure_armies_for(enemy)
			var goals := War.recommend_goals(sim, enemy, 1)
			war = War.declare_war(sim, enemy, goals[0] if goals.size() > 0 else hex)
			war["ai_goal"] = hex
			war["by_ai"] = 1
			war["started"] = now
			# the AI's first strike is announced at the start of a war it began (canon §9.11)
			war["strike_hex"] = hex
			var from := hex
			for n in sim.neighbors[hex]:
				if n >= 0 and sim.cells[n]["owner"] == enemy:
					from = n
					break
			war["strike_from"] = from
			war["strike_at"] = now + STRIKE_WARN_SEC
			map_view.at_war_with = enemy
			map_view.mark_dirty()
			sfx.play("warn")
			_post("Война!", "%s объявили войну. Удар по «%s» через 20 мин — укрепите гекс или наступайте первыми." % [_state_name(enemy), _cell_name(hex)])
			ultimatum = {}
			ui.close_modal()
			_set_mode(Mode.WAR)
			return
	ultimatum = {}
	ui.close_modal()
	_econ_tick()
	_autosave()


## The announced strike lands. Chapter I strikes are scripted and the first AI counterattack in the game
## is always repelled (canon §9.11); the deterministic auto-defense battle comes with chapter II.
func _resolve_strike() -> void:
	var hex: int = war["strike_hex"]
	war.erase("strike_at")
	war.erase("strike_hex")
	war.erase("strike_from")
	map_view.strike_arrow(-1, -1, "")
	war["battles"] = clampi(int(war["battles"]) + 2, -10, 10)
	var gold := int(maxi(60, int(econ.gross_per_hour(sim).get("gold", 0))) / 2.0)
	econ.add_resources({"gold": gold})
	map_view.burst(hex, MapView.C_PLAYER, true)
	map_view.floater(hex, "Отбито!", Color(0.75, 0.85, 1.0))
	sfx.play("repelled")
	var msg := "%s атаковали «%s» — атака отбита! +2 к военному счёту, +%d золота." % [_state_name(int(war["enemy"])), _cell_name(hex), gold]
	_post("Оборона", msg)
	ui.toast(msg)
	_refresh_ui()
	_autosave()


## War cap (canon §9.13): the recommended package at ВС ≥ +10, white peace at |ВС| < 10, defeat at ≤ −10.
func _war_cap() -> void:
	var ws := War.war_score(sim, war)
	var enemy: int = war["enemy"]
	ui.close_modal()
	if ws["score"] >= 10.0:
		_demands = War.available_demands(sim, war)
		_chosen = {}
		for d in War.recommend_package(sim, war, _demands, ws["score"]):
			_chosen[d["id"]] = true
		_post("Кап войны", "Война длилась 2 ч — подписан рекомендованный мир.")
		_sign_peace()
	elif ws["score"] > -10.0:
		War.white_peace(sim)
		_post("Кап войны", "Война длилась 2 ч — белый мир.")
		_finish_war(enemy, "Кап войны: белый мир")
	else:
		_apply_defeat(enemy, _defeat_losses(enemy))


# ====================================================================== FTUE (canon §14.3)

const FTUE_TEXT := {
	1: "Бароны сожгли нашу пограничную мельницу! Объявите им войну.",
	7: "Держава растёт! Откройте «Здания» и улучшите Резиденцию — халупы станут избами.",
	8: "Жёлтый контур — бесплатные ресурсы. Коснитесь жилы и отправьте обоз.",
	9: "Укрепите границу: выберите свой гекс у Баронов и нажмите кнопку «форт» справа.",
	2: "Начните наступление: у вас 60 секунд.",
	3: "Тяните от своей армии на вражеский гекс — армия пойдёт в атаку.",
	4: "Отлично! Карта «Атака» бросает в бой все армии рядом. Захватите ещё!",
	5: "Захваченное пока лишь оккупировано. Подпишите мир — и граница сдвинется.",
	6: "Удерживайте печать, чтобы подписать договор.",
}


## FTUE hook (canon §14.3): the Barons burned the player's border mill — it smokes until the first peace.
func _burned_mill() -> void:
	if ftue <= 0:
		return
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and c["kind"] == "farm" and _touches_owner(c["id"], MapGen.BARONS):
			map_view.smoke(c["id"], -1.0, true)
			_mill = c["id"]
			return


func _touches_owner(id: int, s: int) -> bool:
	for n in sim.neighbors[id]:
		if n >= 0 and sim.cells[n]["owner"] == s:
			return true
	return false


func _residence_busy() -> bool:
	for b in econ.buildings:
		if b["type"] == "residence" and int(b["upgrade_end"]) > now_s():
			return true
	return false


## The FTUE gold vein: a small deposit on the player's land, reachable by the first (fast) convoy.
func _ftue_deposit() -> int:
	for d in deposits.active:
		if sim.cells[d["hex"]]["owner"] == Types.PLAYER and int(d["convoy"]) < 0:
			return d["hex"]
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and c["kind"] == "plain" and int(c["fort"]) == 0 and deposits.at(c["id"]).is_empty():
			deposits.spawn_at(sim, c["id"], "gold", "S", econ.gross_per_hour(sim), now_s())
			return c["id"]
	return -1


func _ftue_attacked() -> void:
	if ftue == 3:
		ftue = 4


func _ftue_tick(delta: float) -> void:
	if ftue <= 0:
		if _ftue_shown != 0:
			_ftue_shown = 0
			ui.coach_hide()
		return
	var target := Vector2(-1, -1)
	match ftue:
		1:
			if selected < 0 and mode == Mode.MAP:
				_pick_target()
			target = Vector2(793, GameUI.VH - 76)
		2:
			target = Vector2(793, GameUI.VH - 76) if mode == Mode.WAR else Vector2(285, 998)
		4:
			target = Vector2(70, GameUI.VH - 124)
		5:
			target = Vector2(655, 998)
		6:
			target = Vector2(470, 1488)
		7:
			if econ.dev_level() >= 2 or _residence_busy():
				ftue = 8
				return
			var why: String = econ.can_upgrade(econ.buildings[0], now_s())
			if why != "" and why.begins_with("Нужно"):
				ftue = 8  # not enough land for DL2 yet — the convoy step comes first
				return
			target = Vector2(70, 1440) if tab != "buildings" else Vector2(83, GameUI.VH - 35)
		8:
			var dh := _ftue_deposit()
			if dh >= 0 and _ftue_shown != 8:
				rig.focus(map_view.cell_world(dh))
			if dh >= 0:
				target = rig.cam.unproject_position(map_view.cell_world(dh) + Vector3(0, 0.8, 0))
		9:
			target = Vector2(895, 486)
	if _ftue_shown != ftue:
		_ftue_shown = ftue
		_ftue_t = 0.0
		ui.coach(FTUE_TEXT[ftue], target)
	_ftue_t += delta
	ui.coach_target(target)
	if ftue == 4 and _ftue_t > 6.0:
		ui.coach_hide()
	if ftue == 3 and battle != null:
		# show the easiest win: the best forecast among idle army → adjacent target pairs
		var from := -1
		var to := -1
		var best := -1.0
		for a in armies:
			if a["side"] != Types.PLAYER or battle.army_at(a["hex"], Types.PLAYER) == null:
				continue
			for n in sim.neighbors[a["hex"]]:
				if n >= 0 and battle.can_target(Types.PLAYER, n):
					var f: float = battle.forecast(Types.PLAYER, [a["id"]], n)["f"]
					if f > best:
						best = f
						from = a["hex"]
						to = n
		if from >= 0:
			var cam: Camera3D = rig.cam
			ui.coach_ghost(cam.unproject_position(map_view.cell_world(from) + Vector3(0, 0.3, 0)), cam.unproject_position(map_view.cell_world(to) + Vector3(0, 0.3, 0)))


# ====================================================================== frame

func _process(delta: float) -> void:
	if selection.visible:
		var k := 1.0 + 0.03 * sin(Time.get_ticks_msec() / 160.0)
		selection.scale = Vector3(k, 0.15, k)
	if mode == Mode.BATTLE and battle != null:
		_acc += delta
		var steps := 0
		while _acc >= 0.1 and steps < 5 and not battle.over:
			_acc -= 0.1
			steps += 1
			_battle_step()
		_refresh_ui()
		if battle.over:
			_end_offensive()
	elif mode == Mode.CEREMONY:
		_step_ceremony(delta)
	map_view.sync_armies(armies, battle)
	_sync_deposits()
	_ftue_tick(delta)
	_econ_acc += delta
	if _econ_acc >= 1.0:
		_econ_acc = 0.0
		_econ_tick()
	_update_minimap()


func _update_minimap() -> void:
	var parts := PackedStringArray()
	for c in sim.cells:
		parts.append("%d%d" % [map_view.owner_of(c), c["controller"]])
	var snap := ",".join(parts) + str(map_view.at_war_with)
	var mm: Control = hud.minimap
	var half := Vector2(lerpf(2.2, 6.5, rig.zoom), lerpf(3.2, 9.0, rig.zoom))
	var r := Rect2(Vector2(rig.target.x, rig.target.z) - half, half * 2.0)
	if snap != _minimap_snap or r != mm.view_rect:
		_minimap_snap = snap
		mm.view_rect = r
		mm.queue_redraw()


# ====================================================================== debug / CI

func _handle_args() -> void:
	var shot := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--zoom="):
			rig.zoom = float(a.substr(7))
			rig.zoom_target = rig.zoom
		elif a.begins_with("--select="):
			var parts := a.substr(9).split(",")
			_select(sim.id_at(int(parts[0]), int(parts[1])))
		elif a.begins_with("--skip="):
			time_offset += int(a.substr(7))
			_econ_tick()
		elif a.begins_with("--tab="):
			_open_tab(a.substr(6))
		elif a.begins_with("--demo="):
			_demo(a.substr(7))
		elif a.begins_with("--shot="):
			shot = a.substr(7)
	if shot != "":
		_shot(shot)


## Scripted states for screenshots: plays the offensive with a simple bot (same as tests/test_sim.gd).
func _demo(spec: String) -> void:
	var parts := spec.split(":")
	var what := parts[0]
	if what.begins_with("ftue"):
		ftue = 1
		_burned_mill()
		var step := int(parts[1]) if parts.size() > 1 else 1
		if step >= 2:
			_declare(MapGen.BARONS, War.recommend_goals(sim, MapGen.BARONS, 1)[0])
		if step >= 3:
			_start_offensive()
		for i in 3:
			_ftue_tick(0.4)
		return
	if what == "ultimatum" or what == "strike":
		_demo("ceremony:0.1")
		for i in 80:
			_step_ceremony(0.1)
		_end_ceremony()
		truce = {}
		ultimatum_at = now_s() - 1
		_ai_tick(now_s())
		if what == "strike":
			_answer_ultimatum("refuse")
			rig.focus(map_view.cell_world(int(war["strike_hex"])), 0.45)
		return
	if what == "settings":
		_on_hud_button("gear")
		return
	var enemy := MapGen.BARONS
	_declare(enemy, War.recommend_goals(sim, enemy, 1)[0])
	if what == "war":
		return
	_start_offensive()
	var ticks := Battle.OFFENSIVE_TICKS + 1 if what != "battle" else int(float(parts[1] if parts.size() > 1 else "30") * Battle.TICKS_PER_SEC)
	while battle != null and not battle.over and battle.tick < ticks:
		if battle.tick % 20 == 0:
			_bot_move()
		_battle_step()
	if what == "battle":
		rig.focus(_front_center())
		rig.zoom = rig.zoom_target
		_refresh_ui()
		return
	_end_offensive()
	if what == "result":
		return
	ui.close_modal()
	_open_peace()
	if what == "peace":
		return
	_sign_peace()
	var t := float(parts[1]) if parts.size() > 1 else 2.2
	_step_ceremony(t)


func _bot_move() -> void:
	var best_id := -1
	var best_f := 0.0
	for c in sim.cells:
		if not battle.can_target(Types.PLAYER, c["id"]):
			continue
		var ids: Array = []
		for a in battle.adjacent_idle_armies(Types.PLAYER, c["id"]):
			ids.append(a["id"])
		if ids.is_empty():
			continue
		var f: float = battle.forecast(Types.PLAYER, ids, c["id"])["f"] + (0.3 if c["id"] == war["goal"] else 0.0)
		if f >= 1.2 and (best_id < 0 or f > best_f):
			best_id = c["id"]
			best_f = f
	if best_id >= 0:
		battle.issue(Types.PLAYER, {"t": "card", "card": "attack", "target": best_id})


func _shot(path: String) -> void:
	for i in 10:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path)
	print("shot saved ", path)
	get_tree().quit()
