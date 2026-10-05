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
	_make_selection()
	_make_drag_marker()
	_focus_front(0.7)
	map_view.sync_armies(armies, null)
	_set_mode(Mode.WAR if not war.is_empty() else Mode.MAP)
	if loaded:
		ui.toast("С возвращением! Прогресс загружен")
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
	if not Types.is_passable(c):
		ui.set_primary("", "")
	elif c["owner"] == Types.NOBODY and _touches_player(selected):
		ui.set_primary("colonize", "⛳ Колонизировать", Color(0.2, 0.55, 0.3))
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
			ui.toast("Постройки и улучшения откроются в следующей версии")
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
			ui.toast("Укрепления — в следующей версии")
		"trophy":
			ui.toast("Глава I «Долина»: %d / %d гексов" % [_player_hexes(), CHAPTER_GOAL])
		"book":
			ui.toast("Летопись откроется после главы I")
		"mail":
			ui.toast("Писем от соседей пока нет")


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


func _colonize(id: int) -> void:
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
	ui.toast("Колонизирован «%s» · Глава I: %d / %d" % [_cell_name(id), _player_hexes(), CHAPTER_GOAL])
	_select(id)


func _declare(enemy: int, goal: int) -> void:
	_ensure_armies_for(enemy)
	war = War.declare_war(sim, enemy, goal)
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
		lines.append("💰 Контрибуция: %d × 4 ч золота" % res["gold_packs"])
	if res.get("reparations", false):
		lines.append("📜 Репарации: 10% производства на 24 ч")
	truce[enemy] = Time.get_unix_time_from_system() + TRUCE_SEC
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
	_ceremony["gold_packs"] = 0
	_end_ceremony()


func _end_ceremony() -> void:
	ui.close_modal()
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
	# Defeat (canon §9.14): the AI annexes what it occupies, ≤20% of value, ≤1 city, never the core.
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
	ui.show_result(0, 0, lost.size(), score, War.war_score(sim, war)["control"], "Поражение: −%d гекс., грабёж 60%%" % lost.size(),
		func(): ui.close_modal(); _set_mode(Mode.WAR),
		func():
			for id in lost:
				sim.cells[id]["owner"] = enemy
				sim.cells[id]["controller"] = enemy
			War.white_peace(sim)
			_finish_war(enemy, "Мир с потерями. Щит восстановления 24 ч и «Реванш» +15%"))


func _finish_war(enemy: int, msg: String) -> void:
	ui.close_modal()
	truce[enemy] = Time.get_unix_time_from_system() + TRUCE_SEC
	war = {}
	_normalize_armies()
	map_view.sync_armies(armies, null)
	map_view.refresh_props()
	map_view.mark_dirty()
	_set_mode(Mode.MAP)
	ui.toast(msg)


# ====================================================================== FTUE (canon §14.3)

const FTUE_TEXT := {
	1: "Бароны сожгли нашу пограничную мельницу! Объявите им войну.",
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
	_ftue_tick(delta)
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
