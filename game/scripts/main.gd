extends Node3D
## Game controller: wires the deterministic sim (scripts/sim/*) to the 3D map (map_view.gd), the camera,
## the static HUD frame (hud.gd) and the mode UI (game_ui.gd).
## Modes: MAP → (declare) WAR → BATTLE (90 s offensive) → RESULT → WAR … → PEACE → CEREMONY → MAP.
##
## Debug / CI args (after `--`): --lang=ru|en (read first, before the UI is built)  --zoom=0.6  --select=q,r  --shot=PATH
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
const Cases := preload("res://scripts/sim/cases.gd")
const Research := preload("res://scripts/sim/research.gd")
const Market := preload("res://scripts/sim/market.gd")
const March := preload("res://scripts/sim/march.gd")
const Camps := preload("res://scripts/sim/camps.gd")
const Net := preload("res://scripts/net.gd")
const ShopUI := preload("res://scripts/shop_ui.gd")
const L := preload("res://scripts/l10n.gd")

enum Mode { MAP, WAR, BATTLE, RESULT, PEACE, CEREMONY }

const MAP_SEED := 20261004
const HAND := ["attack", "breakthrough", "airstrike", "encircle", "defense"]
const CHAPTER_GOAL := 20
const TRUCE_SEC := 30 * 60
## Translation keys of unnamed hexes: by kind, else by terrain.
const KIND_NAMES := {"capital": "kind.capital", "city": "kind.city", "farm": "kind.farm", "mine": "kind.mine", "port": "kind.port", "military_base": "kind.military_base"}
const TERRAIN_NAMES := {"plain": "terrain.plain", "forest": "terrain.forest", "hills": "terrain.hills", "water": "terrain.water", "mountain": "terrain.mountain"}

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
var cases  # Cases (scripts/sim/cases.gd)
var research  # Research (scripts/sim/research.gd)
var market  # Market trader state (scripts/sim/market.gd)
var camps  # marauder camps (scripts/sim/camps.gd)
var _camp_fight := {}  # running camp fight: hex, fort before, army hexes before
var market_sel := {"give": "food", "get": "metal", "pct": 25}
var _march_pick := -1  # army id waiting for a destination tap (canon §8.1 march)
var _march_dest := {}  # army id -> destination hex (timer label)
var _full_hinted := {}  # resource -> true once the «warehouse full → Market» hint was shown
var net: Node  # cloud saves (scripts/net.gd)
var _remote_pending := {}
var shop: Control
var speed_minutes := 0  # speed-up items from cases, used on building timers
var purchases := {}  # test-build purchases (sku -> count), first Raivite pack ×2
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
var _last_refill := 0
var training := {}  # new army being formed: {end, slots}
var stats := {}  # chapter counters for the stars: peaces, goals, pockets, colonized, forts, convoys, defenses
var stars_claimed := {}
var chapter_done := false
var opinion := {}  # AI state -> opinion of the player, decays toward 0 (canon §10.5)
var gift_at := {}  # AI state -> unix time of the last gift
var _last_opinion := 0
var ad_counts := {}  # rewarded placement -> [day, views] (daily caps, canon §15.2)
var lang := ""  # UI language chosen in Settings ("" = follow the device), kept in user://settings.json

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
	cases = Cases.new(int(Time.get_unix_time_from_system()) & 0x7FFFFFFF)
	research = Research.new()
	market = Market.new()
	camps = Camps.new(MAP_SEED ^ 0xCA4B)
	save_enabled = save_enabled and not _scripted_run()
	_init_language()
	var loaded := false
	if save_enabled:
		var d := Save.read()
		loaded = not d.is_empty() and Save.apply(self, d)
	net = Net.new()
	add_child(net)
	if save_enabled:
		net.remote_newer.connect(_on_remote_save)
		net.start()
	map_view = MapView.new()
	add_child(map_view)
	map_view.set_world(sim)
	_show_damage()
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
	ui.army_action.connect(_on_army_action)
	ui.diplomacy_action.connect(_on_diplomacy_action)
	ui.world_action.connect(_on_world_action)
	ui.plunder_selected.connect(func(l: int):
		plunder_level = l
		_show_peace())
	ui.research_start.connect(_on_research_start)
	ui.research_speedup.connect(_on_research_speedup)
	ui.market_open.connect(_open_market)
	_make_selection()
	_make_drag_marker()
	_focus_front(0.7)
	map_view.sync_armies(armies, null)
	_set_mode(Mode.WAR if not war.is_empty() else Mode.MAP)
	_open_tab("army")
	_econ_tick()
	if loaded:
		ui.toast(tr("toast.welcome_back"))
	elif save_enabled:
		ftue = 1
	_burned_mill()
	await get_tree().process_frame
	_handle_args()


# ====================================================================== language (scripts/l10n.gd)

## UI language: a `--lang=ru|en` user arg (screenshots) wins, then the choice saved in Settings, then the
## device language (Russian for ru/uk/be/kk devices, English elsewhere).
func _init_language() -> void:
	if save_enabled:
		lang = String(Save.read_settings().get("lang", ""))
	var forced := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--lang="):
			forced = a.substr(7)
	L.apply(forced if L.LANGS.has(forced) else lang)


## Settings → language: applies at once, remembers the choice and re-renders what is on screen.
func _set_language(code: String) -> void:
	lang = code
	L.apply(code)
	if save_enabled:
		Save.write_settings({"lang": code})
	hud.retranslate()
	ui.retranslate()
	_ftue_shown = -1  # the coach line comes back in the new language
	if selected >= 0:
		hud.show_tile(_describe(selected))
	_open_tab(tab)
	_econ_tick()
	_refresh_ui()
	_show_settings()


func _show_settings() -> void:
	ui.show_settings(sfx.enabled, func(): sfx.enabled = not sfx.enabled, _new_game, _set_language)


# ====================================================================== scene setup

func _environment() -> void:
	var we := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.13, 0.16, 0.2)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.62, 0.7, 0.85)
	e.ambient_light_energy = 0.45
	e.ssao_enabled = true
	e.ssao_radius = 1.2
	e.ssao_intensity = 2.5
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	e.tonemap_exposure = 1.05
	e.glow_enabled = true
	e.glow_intensity = 1.2
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
	sun.light_energy = 1.35
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
	sfx.play_music("battle" if m == Mode.BATTLE else "map")
	_refresh_ui()
	if m in [Mode.MAP, Mode.WAR, Mode.RESULT]:
		_autosave()


func _autosave() -> void:
	if save_enabled:
		var d := Save.save(self)
		if net:
			net.push(d)


## A newer save arrived from the cloud (another device or a reinstall): apply it on the map, never mid-battle.
func _on_remote_save(data: Dictionary) -> void:
	var local := Save.read()
	if not local.is_empty() and int(local.get("saved_at", 0)) > int(data.get("saved_at", 0)):
		return  # our copy is newer; the next autosave uploads it
	_remote_pending = data


func _apply_remote_if_any() -> void:
	if _remote_pending.is_empty() or mode not in [Mode.MAP, Mode.WAR]:
		return
	Save.write_raw(_remote_pending)
	_remote_pending = {}
	ui.toast(tr("toast.cloud_loaded"))
	get_tree().create_timer(0.8).timeout.connect(get_tree().reload_current_scene)


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
	elif tab == "army" and econ != null:
		ui.show_armies(_army_items(now_s()))
	elif tab == "diplomacy" and econ != null:
		ui.show_diplomacy(_diplomacy_items(now_s()))
	elif tab == "world" and econ != null:
		ui.show_world(_world_items())
	elif tab == "development" and econ != null:
		ui.show_buildings(_research_items(now_s()))
	match mode:
		Mode.MAP:
			ui.set_action("", "")
			_primary_for_selection()
		Mode.WAR:
			ui.set_action("peace", tr("ui.peace_btn"), tr("ui.score") % ws.get("score", 0.0), Color(0.12, 0.36, 0.2))
			if not _march_primary():
				_offensive_primary()
		Mode.BATTLE:
			ui.set_primary("retreat", tr("ui.retreat"), Color(0.32, 0.36, 0.46))
		_:
			ui.set_action("", "")
			ui.set_primary("", "")


func _primary_for_selection() -> void:
	ui.set_action("", "")
	if selected < 0:
		ui.set_primary("pick_target", tr("ui.pick_target"), Color(0.8, 0.22, 0.16))
		return
	var c: Dictionary = sim.cells[selected]
	if c["owner"] == Types.PLAYER and econ.damaged.has(selected):
		var re: int = econ.damaged[selected]
		if re > now_s():
			ui.set_primary("repairing", tr("ui.repairing") % GameUI.fmt_time(re - now_s()), Color(0.3, 0.35, 0.45), false)
		else:
			var cost: Dictionary = econ.repair_cost(sim, selected)
			var parts := PackedStringArray()
			for r in cost:
				parts.append("%d %s" % [int(cost[r]), tr("res.short." + String(r))])
			ui.set_primary("repair", tr("ui.repair") % ", ".join(parts), Color(0.85, 0.55, 0.1), econ.can_repair(sim, selected) == "")
			ui.set_action("repair_ad", tr("ui.repair_ad"), tr("ui.ad_sub"), Color(0.2, 0.4, 0.25))
		return
	var dep: Dictionary = deposits.at(selected)
	if not dep.is_empty():
		var cv: Dictionary = deposits.convoy_for(selected)
		if not cv.is_empty():
			ui.set_primary("", tr("ui.convoy_status") % GameUI.fmt_time(int(cv["back"]) - now_s()), Color(0.3, 0.33, 0.42), false)
		else:
			var reason: String = deposits.can_send(sim, selected, econ.dev_level())
			ui.set_primary("convoy", tr("ui.send_convoy") if reason == "" else L.t(reason), Color(0.8, 0.6, 0.1), reason == "")
		return
	if not Types.is_passable(c):
		ui.set_primary("", "")
	elif not camps.at(selected).is_empty():
		if not war.is_empty():
			ui.set_primary("camp_wait", tr("camp.after_war"), Color(0.3, 0.35, 0.45), false)
		elif not Camps.attackable(sim, selected):
			ui.set_primary("camp_far", tr("camp.approach"), Color(0.3, 0.35, 0.45), false)
		else:
			ui.set_primary("camp", tr("ui.attack_camp"), Color(0.8, 0.22, 0.16))
	elif colonizing.has(selected):
		var left: int = int(colonizing[selected]) - now_s()
		var price := Economy.speedup_price(left)
		ui.set_primary("colonize_now", tr("ui.finish") if price == 0 else tr("ui.speedup") % price, Color(0.85, 0.55, 0.1))
	elif c["owner"] == Types.NOBODY and _touches_player(selected):
		var cost := _colonize_cost()
		ui.set_primary("colonize", tr("ui.colonize") % [cost, GameUI.fmt_time(_colonize_seconds())], Color(0.2, 0.55, 0.3), econ.res["gold"] >= cost and colonizing.is_empty())
	elif c["owner"] != Types.PLAYER and c["owner"] != Types.NOBODY:
		var left := _truce_left(c["owner"])
		if left > 0:
			ui.set_primary("truce", tr("ui.truce_timer") % [left / 60, left % 60], Color(0.3, 0.35, 0.45), false)
		elif MapGen.core_of(sim, c["owner"]).has(selected):
			ui.set_primary("core", tr("ui.core_protected"), Color(0.3, 0.35, 0.45), false)
		else:
			ui.set_primary("declare", tr("ui.declare_war"), Color(0.8, 0.22, 0.16))
	elif _march_primary():
		pass
	elif c["owner"] == Types.PLAYER:
		ui.set_primary("upgrade", tr("ui.upgrade"), Color(0.13, 0.4, 0.9))
	else:
		ui.set_primary("", "")
	if c["owner"] == Types.PLAYER and econ.ruin_left(now_s()) > 0:
		ui.set_action("ruin_halve", tr("ui.ruin_halve"), tr("ui.ruin_left") % [econ.ruin_pct, GameUI.fmt_time(econ.ruin_left(now_s()))], Color(0.35, 0.22, 0.12))


## «Наступление», or a march timer while every army is still on its way to the front (none touches the enemy).
func _offensive_primary() -> void:
	var enemy: int = war.get("enemy", -1)
	var wait := 0
	for a in _player_armies():
		if _touches_owner(int(a["hex"]), enemy) and not March.is_marching(a):
			wait = 0
			break
		if March.is_marching(a):
			var left := March.seconds_left(sim, a, now_s())
			wait = left if wait == 0 else mini(wait, left)
	if wait > 0:
		ui.set_primary("wait", tr("ui.armies_marching") % GameUI.fmt_time(wait), Color(0.3, 0.35, 0.45), false)
	else:
		ui.set_primary("offensive", tr("ui.offensive"), Color(0.8, 0.22, 0.16))


## March button for an own army on the selected hex (MAP and WAR). True when it took the primary slot.
func _march_primary() -> bool:
	var a := _army_at(selected)
	if a.is_empty():
		return false
	if _march_pick == int(a["id"]):
		ui.set_primary("march_cancel", tr("march.pick"), Color(0.3, 0.35, 0.45))
	elif March.is_marching(a):
		ui.set_primary("march_stop", tr("ui.marching") % GameUI.fmt_time(March.seconds_left(sim, a, now_s())), Color(0.3, 0.35, 0.45))
	else:
		ui.set_primary("march", tr("ui.march"), Color(0.16, 0.42, 0.95))
	return true


## The player's army standing on (or last reached) `hex`, else {}.
func _army_at(hex: int) -> Dictionary:
	if hex < 0:
		return {}
	for a in _player_armies():
		if int(a["hex"]) == hex and int(a["str"]) > 0:
			return a
	return {}


func _army_by_id(id: int) -> Dictionary:
	for a in armies:
		if int(a["id"]) == id:
			return a
	return {}


func _march_to(hex: int) -> void:
	var a := _army_by_id(_march_pick)
	_march_pick = -1
	if a.is_empty() or hex == int(a["hex"]):
		_refresh_ui()
		return
	for b in _player_armies():
		if b != a and (int(b["hex"]) == hex or _march_dest.get(int(b["id"]), -1) == hex):
			ui.toast(tr("march.busy"))
			_refresh_ui()
			return
	var r: Dictionary = March.order(sim, a, hex, now_s())
	if r.is_empty():
		ui.toast(tr("march.no_route"))
		sfx.play("warn")
		_refresh_ui()
		return
	_march_dest[int(a["id"])] = hex
	sfx.play("attack")
	ui.toast(tr("march.started") % GameUI.fmt_time(int(r["seconds"])))
	_select(hex)
	_autosave()


## Moves marching armies on and keeps their destination timers up to date.
func _step_marches() -> void:
	var now := now_s()
	var now_f := float(now) + fmod(Time.get_unix_time_from_system(), 1.0)
	var paths := {}
	for a in _player_armies():
		var id: int = a["id"]
		if March.is_marching(a) and March.step(sim, a, now):
			if _march_dest.has(id):
				map_view.hex_label(int(_march_dest[id]), "")
				_march_dest.erase(id)
			if mode in [Mode.MAP, Mode.WAR]:
				ui.toast(tr("march.arrived"))
				_refresh_ui()
		a["march_vis"] = March.progress(a, now_f)
		if March.is_marching(a):
			paths[id] = [int(a["hex"])] + (a["march"]["path"] as Array)
			var dest: int = (a["march"]["path"] as Array).back()
			_march_dest[id] = dest
			map_view.hex_label(dest, "⇢ " + GameUI.fmt_time(March.seconds_left(sim, a, now)), Color(0.6, 0.85, 1.0))
		elif _march_dest.has(id):
			map_view.hex_label(int(_march_dest[id]), "")
			_march_dest.erase(id)
	map_view.set_march_paths(paths)


## Offensives fight from where the armies stand (04 §7.2): marches end on the last hex reached.
func _stop_marches() -> void:
	_march_pick = -1
	for a in _player_armies():
		March.stop(a)
		a["march_vis"] = {}
	for id in _march_dest:
		map_view.hex_label(int(_march_dest[id]), "")
	_march_dest.clear()
	map_view.set_march_paths({})


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
		"march":
			var ma := _army_at(selected)
			if not ma.is_empty():
				_march_pick = int(ma["id"])
				ui.toast(tr("march.pick"))
				_refresh_ui()
		"camp":
			_start_camp_fight(selected)
		"repair":
			_repair(selected, false)
		"repair_ad":
			_repair(selected, true)
		"ruin_halve":
			if _rewarded("ad_ruin_halve", 1):  # once a day (canon §15.2)
				econ.halve_ruin(now_s())
				_econ_tick()
				_refresh_ui()
				_autosave()
		"march_cancel":
			_march_pick = -1
			_refresh_ui()
		"march_stop":
			var ms := _army_at(selected)
			if not ms.is_empty():
				March.stop(ms)
				_step_marches()
				_refresh_ui()
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
				_show_settings()
		"target":
			rig.focus(_front_center() if mode == Mode.BATTLE else _war_or_front_center())
		"pin":
			rig.focus(map_view.cell_world(sim.states[Types.PLAYER]["capital_id"]))
		"fort":
			_fort_action()
		"tower":
			_tower_action()
		"trophy":
			ui.toast(tr("toast.chapter_progress") % [_player_hexes(), CHAPTER_GOAL])
		"book":
			ui.toast(tr("toast.chronicle_locked"))
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
		"shop":
			_open_shop()
		"tab_diplomacy":
			_open_tab("diplomacy")
		"tab_development":
			_open_tab("development")
		"tab_world":
			_open_tab("world")


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
	if _march_pick >= 0 and id >= 0:
		_march_to(id)
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
			ui.toast(tr("toast.occupied_hex") % [_cell_name(id), _state_name(c["controller"])])


func _describe(id: int) -> Dictionary:
	var c: Dictionary = sim.cells[id]
	var own: int = c["owner"]
	var owner_text: String = tr("tile.your_territory") if own == Types.PLAYER else _state_name(own)
	if c["controller"] != own:
		owner_text = tr("tile.occupied") % owner_text
	var bonus: String = tr("tile.value") % c["value"]
	if c["terrain"] == "forest":
		bonus += " · " + tr("tile.forest_def")
	elif c["terrain"] == "hills":
		bonus += " · " + tr("tile.hills_def")
	if c["fort"] > 0:
		bonus += " · " + tr("tile.fort") % c["fort"]
	if not Types.is_passable(c):
		bonus = tr("tile.impassable")
	elif c["controller"] == Types.PLAYER:
		var inc: Dictionary = econ.hex_income(sim, id)
		var parts := PackedStringArray()
		for r in inc:
			if int(inc[r]) > 0:
				parts.append(tr("tile.income") % [inc[r], tr("res.short." + String(r))])
		if parts.size() > 0:
			bonus = " · ".join(parts)
		if own == Types.PLAYER and econ.damaged.has(id):
			bonus += " · " + tr("tile.damaged")
		if own == Types.PLAYER and econ.ruin_left(now_s()) > 0:
			bonus += " · " + tr("tile.ruin") % [econ.ruin_pct, GameUI.fmt_time(econ.ruin_left(now_s()))]
	var cm: Dictionary = camps.at(id) if camps != null else {}
	if not cm.is_empty():
		return {"title": tr("tile.camp"), "owner": owner_text, "owner_color": Color(0.75, 0.72, 0.68),
			"bonus": tr("tile.camp_loot") % [tr("res.name." + String(cm["res"])), camps.rewards_left(now_s())], "attackable": false}
	var dep: Dictionary = deposits.at(id) if deposits != null else {}
	if not dep.is_empty():
		bonus = tr("tile.deposit") % [int(dep["amount"]), tr("res.gen." + String(dep["res"])), GameUI.fmt_time(int(dep["gather_sec"]))]
		return {"title": "%s (%s)" % [tr(String(Deposits.NAMES.get(String(dep["res"]), "tile.deposit_name"))), dep["size"]], "owner": owner_text,
			"owner_color": Color(1.0, 0.85, 0.3), "bonus": bonus, "attackable": false}
	return {
		"title": _cell_name(id),
		"owner": owner_text,
		"owner_color": map_view.state_color(own).lightened(0.25),
		"bonus": bonus,
		"attackable": own != Types.PLAYER and own != Types.NOBODY,
	}


## Translation key of a hex name (stored in reports so they follow a later language switch).
func _cell_key(id: int) -> String:
	var c: Dictionary = sim.cells[id]
	if c["name"] != "":
		return c["name"]
	if KIND_NAMES.has(c["kind"]):
		return KIND_NAMES[c["kind"]]
	return TERRAIN_NAMES.get(c["terrain"], "tile.hex")


func _cell_name(id: int) -> String:
	return tr(_cell_key(id))


func _state_key(s: int) -> String:
	if s < 0 or s >= sim.states.size():
		return ""
	return sim.states[s]["name"]


func _state_name(s: int) -> String:
	var k := _state_key(s)
	return tr(k) if k != "" else ""


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
		ui.toast(tr("toast.no_targets"))
		return
	rig.focus(map_view.cell_world(target))
	_select(target)


func _colonize_cost() -> int:
	return int(ceil(50.0 * Economy.PROD_MULT100[econ.dev_level()] / 100.0 * (1.0 + 0.15 * colonized) * (1.0 - 0.1 * research.level("colonization"))))


## 1 min in chapter I, 5 / 15 / 30 min in later chapters (canon §12.1).
func _colonize_seconds() -> int:
	return 60


## Colonization (canon §12.1): gold and a timer, one at a time, no builder needed.
func _colonize(id: int) -> void:
	if not camps.at(id).is_empty():
		ui.toast(tr("camp.blocks"))
		return
	if not colonizing.is_empty():
		ui.toast(tr("toast.colonizing"))
		return
	var cost := _colonize_cost()
	if econ.res["gold"] < cost:
		ui.toast(tr("toast.no_gold"))
		return
	econ.res["gold"] -= cost
	colonizing[id] = now_s() + _colonize_seconds()
	sfx.play("coin")
	map_view.burst(id, Color(1.0, 0.85, 0.3))
	ui.toast(tr("toast.settlers") % [_cell_name(id), GameUI.fmt_time(_colonize_seconds())])
	_autosave()
	_econ_tick()


func _speedup_colonize(id: int) -> void:
	if not colonizing.has(id):
		return
	var price := Economy.speedup_price(int(colonizing[id]) - now_s())
	if econ.res["raivite"] < price:
		ui.toast(tr("toast.no_raivite"))
		return
	econ.res["raivite"] -= price
	colonizing[id] = now_s()
	_econ_tick()


func _finish_colonize(id: int) -> void:
	_stat("colonized")
	colonizing.erase(id)
	map_view.hex_label(id, "")
	colonized += 1
	var c: Dictionary = sim.cells[id]
	c["owner"] = Types.PLAYER
	c["controller"] = Types.PLAYER
	map_view.burst(id, MapView.C_PLAYER, true)
	map_view.floater(id, tr("floater.plus_hex"), Color(0.75, 0.85, 1.0))
	sfx.play("coin")
	sfx.haptic(20)
	map_view.refresh_hex(id)
	map_view.pop_hex(id)
	_autosave()
	map_view.mark_dirty()
	ui.toast(tr("toast.colonized") % [_cell_name(id), _player_hexes(), CHAPTER_GOAL])
	_select(id)


func _declare(enemy: int, goal: int) -> void:
	_ensure_armies_for(enemy)
	_deploy_to_front(enemy)
	war = War.declare_war(sim, enemy, goal)
	war["started"] = now_s()
	_opinion_add(enemy, -50.0)
	map_view.at_war_with = enemy
	map_view.mark_dirty()
	map_view.sync_armies(armies, null)
	map_view.burst(goal, MapView.C_WAR, true)
	sfx.play("warn")
	sfx.haptic(60)
	ui.toast(tr("toast.war_declared") % [_state_name(enemy), _cell_name(goal)])
	if ftue == 1:
		ftue = 2
	elif ftue == 10:
		ftue = 11
	_set_mode(Mode.WAR)


## Armies that don't touch the new enemy march to free front hexes facing it (instant in v1; the canon's
## 20 s per hex march across the strategic map comes with the march system).
func _deploy_to_front(enemy: int) -> void:
	var front: Array = []
	for c in sim.cells:
		if c["controller"] == Types.PLAYER and c["owner"] == Types.PLAYER and Types.is_passable(c) and _touches_owner(c["id"], enemy):
			front.append(c)
	front.sort_custom(func(x, y): return int(x["value"]) > int(y["value"]))
	var taken := {}
	for a in _player_armies():
		if _touches_owner(int(a["hex"]), enemy):
			taken[int(a["hex"])] = true
	var moved := 0
	var longest := 0
	for a in _player_armies():
		if _touches_owner(int(a["hex"]), enemy):
			continue
		for c in front:
			if not taken.has(c["id"]):
				taken[c["id"]] = true
				# canon §8.1: armies march to the new front (20 s/hex); the tutorial skips the walk
				if ftue != 0 or March.order(sim, a, int(c["id"]), now_s()).is_empty():
					March.stop(a)
					a["hex"] = c["id"]
				else:
					longest = maxi(longest, March.seconds_left(sim, a, now_s()))
				moved += 1
				break
	if longest > 0:
		ui.toast(tr("toast.armies_marching") % GameUI.fmt_time(longest))
	elif moved > 0:
		ui.toast(tr("toast.armies_deployed"))


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
	_stop_marches()
	for a in armies:
		# The AI refills between offensives (canon 11 §15.1); the player's armies heal over time for food.
		if a["side"] != Types.PLAYER:
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
		# tutorial offensives are short and the enemy plays no cards (canon §14.3)
		opts["ai_energy_mult"] = 0
		opts["ticks"] = 60 * Battle.TICKS_PER_SEC
		ftue = 12 if ftue >= 10 else 3
	battle = Battle.new(sim, armies, opts)
	ai = BattleAI.new(enemy)
	_acc = 0.0
	_ev_i = 0
	_select(-1)
	rig.focus(_front_center(), 0.5)
	_set_mode(Mode.BATTLE)
	sfx.play("warn")
	if ftue == 0:
		ui.toast(tr("toast.to_battle"))


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
	if ai != null:
		ai.think(battle)
	battle.step()
	if not war.is_empty():
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
			map_view.floater(ev["hex"], tr("floater.occupied") if mine else tr("floater.lost"), Color(0.75, 0.85, 1.0) if mine else Color(1.0, 0.7, 0.7))
			if mine and not war.is_empty() and ev["hex"] == war["goal"]:
				_stat("goals")
				ui.toast(tr("toast.goal_taken"))
		"tower_hit":
			map_view.tower_volley(int(ev["hex"]), int(ev["target"]))
		"repelled":
			sfx.play("repelled")
			map_view.floater(ev["hex"], tr("floater.repelled") if mine else tr("floater.held"), Color.WHITE)
		"routed":
			var a = battle.army_by_id(ev["army"])
			if a != null:
				map_view.floater(a["hex"], tr("floater.routed"), Color(1.0, 0.7, 0.28))
		"card":
			sfx.play("boom" if ev["card"] == "airstrike" else "card")
			if ev["card"] == "airstrike":
				map_view.burst(ev["hex"], Color(1.0, 0.65, 0.2), true)
			else:
				map_view.burst(ev["hex"], Color(0.6, 0.82, 1.0) if mine else Color(1.0, 0.6, 0.6))
			if not mine:
				map_view.floater(ev["hex"], tr(String(Battle.CARDS[ev["card"]]["name"])), Color(1.0, 0.7, 0.7))


# ---------------------------------------------------------------- marauder camps (canon §5.1, 03 §5.7)

func _camps_tick(now: int) -> void:
	var taken := {}
	for d in deposits.active:
		taken[int(d["hex"])] = true
	for h in colonizing:
		taken[int(h)] = true
	var before: int = camps.active.size()
	camps.tick(sim, taken, now)
	if camps.active.size() != before or map_view.camp_count() != camps.active.size():
		map_view.set_camps(camps.active)


func _start_camp_fight(hex: int) -> void:
	if mode != Mode.MAP or camps.at(hex).is_empty():
		return
	var ready := false
	var total := 0
	var n := 0
	for a in _player_armies():
		total += int(a["max_str"])
		n += 1
		if sim.neighbors[hex].has(int(a["hex"])) and not March.is_marching(a) and int(a["str"]) * 2 >= int(a["max_str"]):
			ready = true
	if not ready:
		ui.toast(tr("camp.need_army"))
		return
	_stop_marches()
	var homes := {}
	for a in armies:
		homes[int(a["id"])] = int(a["hex"])
		a["routed"] = false
		a["hold"] = false
	_camp_fight = {"hex": hex, "fort": int(sim.cells[hex]["fort"]), "homes": homes}
	sim.cells[hex]["fort"] = Camps.fort_level(econ.dev_level())
	battle = Battle.new(sim, armies, {"attacker": Types.PLAYER, "defender": Types.NOBODY, "ai_energy_mult": 0,
		"cards": HAND, "camp": hex, "ticks": Camps.FIGHT_TICKS})
	battle.garrison[hex] = camps.garrison(total / maxi(1, n), now_s())
	ai = null
	flag_hex = hex
	_acc = 0.0
	_ev_i = 0
	_select(-1)
	rig.focus(map_view.cell_world(hex), 0.45)
	_set_mode(Mode.BATTLE)
	sfx.play("warn")
	ui.toast(tr("camp.fight"))


func _end_camp_fight() -> void:
	var hex: int = _camp_fight["hex"]
	var won: bool = battle.end_reason == "camp"
	battle = null
	var c: Dictionary = sim.cells[hex]
	c["owner"] = Types.NOBODY
	c["controller"] = Types.NOBODY  # armies never enter a wild hex: the camp is just gone (03 §5.7)
	c["fort"] = int(_camp_fight["fort"])
	var homes: Dictionary = _camp_fight["homes"]
	for a in armies:
		if a["side"] == Types.PLAYER:
			if int(a["hex"]) == hex or sim.cells[int(a["hex"])]["controller"] != Types.PLAYER:
				a["hex"] = int(homes.get(int(a["id"]), a["hex"]))
			if a["routed"] or int(a["str"]) < int(a["max_str"]) / 10:
				a["str"] = maxi(int(a["str"]), int(a["max_str"]) / 10)
				a["routed"] = false
	_camp_fight = {}
	_last_refill = now_s()
	_normalize_armies()
	map_view.sync_armies(armies, null)
	map_view.mark_dirty()
	_set_mode(Mode.MAP)
	if won:
		var rw: Dictionary = camps.defeat(hex, econ.gross_per_hour(sim), now_s())
		map_view.set_camps(camps.active)
		map_view.burst(hex, Color(1.0, 0.85, 0.3), true)
		sfx.play("fanfare")
		_stat("camps")
		var amt: int = int(rw.get("amount", 0))
		if amt > 0:
			var got: Dictionary = econ.add_resources({String(rw["res"]): amt})
			var n: int = int(got.get(String(rw["res"]), 0))
			map_view.floater(hex, "+%d" % n, Color(1.0, 0.88, 0.4))
			ui.toast(tr("camp.won") % [n, tr("res.gen." + String(rw["res"]))])
		else:
			ui.toast(tr("camp.won_no_loot"))
	else:
		sfx.play("lost")
		ui.toast(tr("camp.lost"))
	_select(hex)
	_autosave()


func _end_offensive() -> void:
	var res: Dictionary = battle.result()
	var stars := War.offensive_stars(res["captured"], flag_hex, res["routed_player_armies"])
	sfx.play("fanfare" if stars > 0 else "lost")
	if ftue >= 10:
		ftue = 14 if stars > 0 else 11
	elif ftue > 0:
		ftue = 5 if stars > 0 else 2
	War.record_offensive(war, stars)
	var ws := War.war_score(sim, war)
	battle = null
	ai = null
	for a in armies:
		# a broken army is never lost: it comes back with 10% strength (canon §8.1)
		if a["side"] == Types.PLAYER and (a["routed"] or int(a["str"]) < int(a["max_str"]) / 10):
			a["str"] = maxi(int(a["str"]), int(a["max_str"]) / 10)
			a["routed"] = false
	_last_refill = now_s()
	_normalize_armies()
	map_view.sync_armies(armies, null)
	_set_mode(Mode.RESULT)
	var reason: String = tr(String({"retreat": "result.retreat", "wiped": "result.wiped"}.get(res["reason"], "result.timeout")))
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
		ui.toast(tr("toast.adjacent_only"))
		return
	if battle.can_target(Types.PLAYER, hex):
		if battle.issue(Types.PLAYER, {"t": "attack", "army": a["id"], "target": hex}):
			sfx.play("attack")
			sfx.haptic(15)
			_ftue_attacked()
		else:
			ui.toast(tr("toast.no_energy") % 2)
	elif sim.cells[hex]["controller"] == Types.PLAYER:
		if not battle.issue(Types.PLAYER, {"t": "move", "army": a["id"], "to": hex}):
			ui.toast(tr("toast.hex_busy"))


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
		ui.toast(tr("toast.hex_info") % [_cell_name(id), c["value"], _state_name(c["controller"])])
		return
	var now := Time.get_ticks_msec()
	if _last_tap["army"] == a["id"] and now - int(_last_tap["t"]) < 350:
		battle.issue(Types.PLAYER, {"t": "hold", "army": a["id"]})
		ui.toast(tr("toast.hold_on") if not a["hold"] else tr("toast.hold_off"))
	else:
		ui.toast(tr("toast.army_info") % [roundi(a["str"] / 1000.0), roundi(a["max_str"] / 1000.0)])
	_last_tap = {"army": a["id"], "t": now}


## Card drag preview: the hex under the finger turns green/red by whether the card can be played there,
## with the attack forecast (×1.4) for cards that strike an enemy hex.
func _on_card_drag(card: String, screen: Vector2, active: bool) -> void:
	var sel_mat := selection.material_override as StandardMaterial3D
	if not active or screen.y > GameUI.VH - 280 or battle == null:
		selection.visible = false
		sel_mat.albedo_color = Color(1.0, 0.95, 0.7)
		_drag_lbl.visible = false
		return
	var id: int = map_view.id_at_world(rig.ground_at(screen))
	if id < 0:
		selection.visible = false
		_drag_lbl.visible = false
		return
	selection.position = map_view.cell_world(id) + Vector3(0, 0.06, 0)
	selection.visible = true
	var ok: bool = battle.validate(Types.PLAYER, {"t": "card", "card": card, "target": id})
	sel_mat.albedo_color = Color(0.45, 1.0, 0.5) if ok else Color(1.0, 0.35, 0.3)
	_drag_lbl.visible = false
	if ok and Battle.CARDS[card]["target"] == "enemy" and card != "airstrike":
		var ids: Array = []
		for a in battle.adjacent_idle_armies(Types.PLAYER, id):
			ids.append(a["id"])
		if not ids.is_empty():
			var f: float = battle.forecast(Types.PLAYER, ids, id, card == "breakthrough")["f"]
			_drag_lbl.text = "×%.1f" % f
			_drag_lbl.modulate = Color(0.35, 1.0, 0.45) if f >= 1.2 else (Color(1.0, 0.85, 0.3) if f >= 0.8 else Color(1.0, 0.35, 0.3))
			_drag_lbl.position = map_view.cell_world(id) + Vector3(0, 1.0, 0)
			_drag_lbl.visible = true


func _on_card_drop(card: String, screen: Vector2) -> void:
	selection.visible = false
	_drag_lbl.visible = false
	(selection.material_override as StandardMaterial3D).albedo_color = Color(1.0, 0.95, 0.7)
	if battle == null:
		return
	var id: int = map_view.id_at_world(rig.ground_at(screen))
	if id < 0:
		return
	if battle.energy_points(Types.PLAYER) < Battle.CARDS[card]["cost"]:
		ui.toast(tr("toast.no_energy") % Battle.CARDS[card]["cost"])
	elif not battle.card_ready(Types.PLAYER, card):
		ui.toast(tr("toast.card_cooldown"))
	elif battle.issue(Types.PLAYER, {"t": "card", "card": card, "target": id}):
		_ftue_attacked()
	else:
		ui.toast(tr("toast.cant_target") % (tr("card.need_own") if Battle.CARDS[card]["target"] == "own" else tr("card.need_enemy")))


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
			d["label"] = tr("peace.annex") % [_cell_name(h), sim.cells[h]["value"]] + (" 🚩" if h == war["goal"] else "")
		else:
			d["label"] = L.t(String(d["label"]))
	_chosen = {}
	for d in War.recommend_package(sim, war, _demands, ws["score"]):
		_chosen[d["id"]] = true
	if ftue >= 14:
		ftue = 15
	elif ftue > 0:
		ftue = 6
	_set_mode(Mode.PEACE)
	_show_peace()


func _show_peace() -> void:
	var ws := War.war_score(sim, war)
	ui.show_peace(_state_name(war["enemy"]), ws["score"], ws["control"], _demands, _chosen, plunder_level)
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
			ui.toast(tr("toast.no_score"))
			return
		_chosen[id] = true
	_show_peace()


var _last_score := 0.0
var plunder_level := 1  # 0 spare, 1 light 30%, 2 medium 45%, 3 heavy 60% (canon §9.14)
const PLUNDER_PCT := [0.0, 0.30, 0.45, 0.60]
const PLUNDER_OPINION := [20.0, -10.0, -20.0, -30.0]


func _sign_peace() -> void:
	_last_score = War.war_score(sim, war)["score"] if not war.is_empty() else 0.0
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
	var annexed_value := 0
	for d in chosen:
		for h in d["hexes"]:
			annexed_value += int(sim.cells[h]["value"])
	_opinion_add(enemy, -2.0 * annexed_value)
	_stat("peaces")
	for d in chosen:
		if d["kind"] == "pocket":
			_stat("pockets")
	var res: Dictionary = War.apply_treaty(sim, war, chosen)
	sfx.play("seal")
	sfx.haptic(120)
	if ftue >= 15:
		ftue = 0
		ui.coach_hide()
		ui.toast(tr("toast.tutorial_done"))
	elif ftue > 0:
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
	var land: String = tr("ceremony.no_land")
	if annexed.size() > 0:
		land = tr("ceremony.hex") if annexed.size() == 1 else tr("ceremony.hexes") % annexed.size()
		if cities > 0:
			land += " · " + (tr("ceremony.city") if cities == 1 else tr("ceremony.cities") % cities)
	lines.append(land)
	lines.append(tr("ceremony.realm") % [before, MapGen.official_value(sim, Types.PLAYER)])
	lines.append(tr("ceremony.chapter") % [hexes_before, _player_hexes(), CHAPTER_GOAL])
	# plunder (canon §9.14): % of the loser's exposed treasury; the AI economy is not simulated yet, so its
	# treasury is taken as 8 h of comparable production with the 40% protected share; 12 h loss cap for all
	var gross: Dictionary = econ.gross_per_hour(sim)
	var loot := {}
	var contrib_gold := 0
	if res.get("gold_packs", 0) > 0:
		contrib_gold = int(res["gold_packs"]) * 4 * maxi(60, int(gross.get("gold", 0)))
	if plunder_level > 0:
		for r in ["gold", "food", "metal"]:
			var ph: int = maxi(30, int(gross.get(r, 0)))
			var exposed := int(ph * 8 * 0.6)
			var cap_left: int = ph * 12 - (contrib_gold if r == "gold" else 0)
			loot[r] = maxi(0, mini(int(exposed * PLUNDER_PCT[plunder_level]), cap_left))
		econ.add_resources(loot)
		lines.append(tr("ceremony.plunder") % [int(loot["gold"]), int(loot["food"]), int(loot["metal"])])
	_opinion_add(enemy, PLUNDER_OPINION[plunder_level])
	if res.get("gold_packs", 0) > 0:
		# a package = 4 h of the enemy's gold production (canon §10.1); the enemy economy is not modelled yet
		var gold := int(res["gold_packs"]) * 4 * maxi(60, int(econ.gross_per_hour(sim).get("gold", 0)))
		var got: Dictionary = econ.add_resources({"gold": gold})
		lines.append(tr("ceremony.indemnity") % int(got.get("gold", 0)))
	if res.get("reparations", false):
		lines.append(tr("ceremony.reparations"))
	# trophy chest for a victorious peace: bronze < 30, silver < 60, gold ≥ 60 war score (canon §15.4)
	var score: float = _last_score  # war score at signing (the war dict is cleared below)
	var chest := "case_trophy_gold" if score >= 60.0 else ("case_trophy_silver" if score >= 30.0 else "case_trophy_bronze")
	var opened: Dictionary = cases.open(chest, _case_ctx(), now_s())
	_apply_case_rewards([opened])
	lines.append("🎁 %s: %s" % [Cases.case_name(chest), ShopUI.describe(opened["rewards"][0]) if opened["rewards"].size() > 0 else "—"])
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
		"gold_packs": int(res.get("gold_packs", 0)), "loot": loot}
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
		ui.show_ceremony_counters(_ceremony["lines"], _end_ceremony, _double_trophies if int(_ceremony["gold_packs"]) > 0 or not _ceremony.get("loot", {}).is_empty() else Callable(), active_after)


## Rewarded ad «×2 трофеи» — SDK stub until monetization lands (canon §14.10).
func _double_trophies() -> void:
	ui.toast(tr("toast.test_ad_double"))
	econ.add_resources(_ceremony.get("loot", {}))
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
	if _player_hexes() >= CHAPTER_GOAL and not chapter_done:
		ui.toast(tr("toast.chapter_goal"))


func _open_defeat_or_white(score: float) -> void:
	var enemy: int = war["enemy"]
	if absf(score) < 10.0:
		ui.show_result(0, 0, 0, score, War.war_score(sim, war)["control"], tr("result.white_peace"),
			func(): ui.close_modal(); _set_mode(Mode.WAR),
			func():
				War.white_peace(sim)
				_opinion_add(enemy, 25.0)
				_finish_war(enemy, tr("toast.white_peace_signed")))
		return
	var lost := _defeat_losses(enemy)
	ui.show_result(0, 0, lost.size(), score, War.war_score(sim, war)["control"], tr("result.defeat") % lost.size(),
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
	var g12 := {}
	var gph: Dictionary = econ.gross_per_hour(sim)
	for r in ["gold", "food", "metal"]:
		g12[r] = 12 * maxi(30, int(gph.get(r, 0)))
	# plunder level by the winner's archetype (canon §10.4): Wolf 60%, Raven 45%, Fox / Turtle / Owl 30%
	var lvl: int = AI_PLUNDER_LVL.get(String(sim.states[enemy]["archetype"]), 3)
	var looted: Dictionary = econ.plunder(PLUNDER_PCT[lvl], g12)  # 12 h loss cap (canon §9.14, decision 20)
	var msg := L.pack("inbox.defeat.text", [lost.size(), int(looted.get("gold", 0)), int(looted.get("food", 0)), int(looted.get("metal", 0))])
	_post("inbox.defeat.title", msg)
	# plunder also brings ruin (−20/30/40% for 4/6/8 h) and 1–3 damaged hex buildings (canon §9.14)
	econ.apply_ruin(RUIN_PCT[lvl], RUIN_HOURS[lvl] * 3600, now_s())
	var dmg: Array = econ.damage_buildings(sim, lvl)
	_show_damage()
	_post("inbox.ruin.title", L.pack("inbox.ruin.text", [RUIN_PCT[lvl], RUIN_HOURS[lvl], dmg.size()]))
	_finish_war(enemy, L.t(msg))


const AI_PLUNDER_LVL := {"wolf": 3, "raven": 2, "fox": 1, "turtle": 1, "owl": 1}
const RUIN_PCT: Array[int] = [0, 20, 30, 40]  # by plunder level: light / medium / heavy (canon §9.14)
const RUIN_HOURS: Array[int] = [0, 4, 6, 8]


## Smoke over damaged hex buildings until they are repaired.
func _show_damage() -> void:
	for h in econ.damaged:
		map_view.smoke(int(h), 1.0e9)


func _repair(hex: int, free: bool) -> void:
	var now := now_s()
	econ.tick(sim, now)
	if free:
		if not _rewarded("ad_repair", 3) or not econ.start_repair(sim, hex, now, true):
			return
		_repaired(hex)
	else:
		var reason: String = econ.can_repair(sim, hex)
		if reason != "" or not econ.start_repair(sim, hex, now):
			ui.toast(L.t(reason) if reason != "" else tr("toast.cant_upgrade"))
			return
		sfx.play("coin")
		ui.toast(tr("toast.repair_started") % GameUI.fmt_time(Economy.REPAIR_SEC))
	_econ_tick()
	_refresh_ui()
	_autosave()


func _repaired(hex: int) -> void:
	map_view.clear_smoke(hex)
	map_view.burst(hex, Color(1.0, 0.85, 0.3), true)
	sfx.play("capture")
	ui.toast(tr("toast.repaired"))


func _finish_war(enemy: int, msg: String) -> void:
	ui.close_modal()
	if ftue >= 10:
		ftue = 0  # the tutorial war ended without a treaty — let the player go on freely
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

## Server-aligned time when online (device clock changes don't skip timers), plus the debug offset.
func now_s() -> int:
	return int(Time.get_unix_time_from_system()) + time_offset + (int(net.server_offset) if net != null else 0)


func _econ_tick() -> void:
	var now := now_s()
	var done_line: String = research.tick(now)
	if done_line != "":
		_on_research_done(done_line)
	econ.research = research.economy_levels()
	econ.army_food_milli = _army_food_milli()
	for ev in econ.tick(sim, now):
		_econ_event(ev)
	_army_refill(now)
	_opinion_decay(now)
	if not training.is_empty() and now >= int(training["end"]):
		_finish_training()
	for ev in deposits.tick(sim, econ.gross_per_hour(sim), now):
		if ev["type"] == "convoy_back":
			_stat("convoys")
			var cargo: int = int(round(int(ev["amount"]) * (1.0 + 0.05 * research.level("logistics"))))
			var got: Dictionary = econ.add_resources({String(ev["res"]): cargo})
			var n := int(got.get(String(ev["res"]), 0))
			var cap: int = sim.states[Types.PLAYER]["capital_id"]
			map_view.floater(cap, "+%d" % n, Color(1.0, 0.88, 0.4))
			sfx.play("coin")
			ui.toast(tr("toast.convoy_back") % [n, tr("res.gen." + String(ev["res"]))])
	_camps_tick(now)
	for h in colonizing.keys():
		if now >= int(colonizing[h]):
			_finish_colonize(h)
		else:
			map_view.hex_label(h, "⛳ " + GameUI.fmt_time(int(colonizing[h]) - now))
	hud.set_resources(econ.res, econ.income_per_hour(sim), econ.storage_cap(), econ.builders - econ.busy_builders(now), econ.builders)
	hud.set_level(econ.dev_level())
	hud.set_mail(_unread())
	_market_hint()
	_apply_remote_if_any()
	hud.shop_dot.visible = cases.claim_free_crates(now) > 0
	_ai_tick(now)
	_update_bubbles()
	if tab == "buildings" and mode in [Mode.MAP, Mode.WAR]:
		ui.show_buildings(_building_items(now))
	elif tab == "army" and mode in [Mode.MAP, Mode.WAR]:
		ui.show_armies(_army_items(now))
	elif tab == "diplomacy" and mode in [Mode.MAP, Mode.WAR]:
		ui.show_diplomacy(_diplomacy_items(now))
	elif tab == "world" and mode in [Mode.MAP, Mode.WAR]:
		ui.show_world(_world_items())
	elif tab == "development" and mode in [Mode.MAP, Mode.WAR]:
		ui.show_buildings(_research_items(now))
	if mode == Mode.MAP and selected >= 0:
		_primary_for_selection()
	elif mode == Mode.WAR and not _march_primary():
		_offensive_primary()


func _econ_event(ev: Dictionary) -> void:
	match ev.get("type", ""):
		"upgrade_done":
			var b: Dictionary = econ.building(int(ev["building"]))
			if String(b.get("type", "")) in ["fort", "tower"] and int(b.get("hex", -1)) >= 0:
				map_view.refresh_hex(int(b["hex"]))
				map_view.pop_hex(int(b["hex"]))
			var name: String = Economy.BUILDINGS[String(ev.get("building_type", b.get("type", "")))]["name"]
			ui.toast(tr("toast.level_done") % [tr(name), int(ev["level"])])
			sfx.play("capture")
			if int(b.get("hex", -1)) >= 0:
				map_view.burst(int(b["hex"]), Color(1.0, 0.85, 0.3), true)
		"dev_level":
			_rescale_armies()
			ui.toast(tr("toast.dl_up") % econ.dev_level())
			sfx.play("fanfare")
			_dl_ceremony()
		"building_unlocked":
			ui.toast(tr("toast.unlocked") % tr(String(Economy.BUILDINGS[String(ev.get("building_type", "market"))]["name"])))
		"fort_refund":
			ui.toast(tr("toast.fort_refund"))
		"repair_done":
			_repaired(int(ev["hex"]))


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
## Tower on the selected own plain hex: build, or upgrade the one standing there (canon §7).
func _tower_action() -> void:
	if selected < 0 or sim.cells[selected]["owner"] != Types.PLAYER:
		ui.toast(tr("toast.pick_own_hex"))
		return
	var now := now_s()
	econ.tick(sim, now)
	var tower: Dictionary = {}
	for b in econ.buildings_at(selected):
		if b["type"] == "tower":
			tower = b
	if tower.is_empty():
		var reason: String = econ.can_build(sim, "tower", selected, now)
		if reason != "" or not econ.start_build(sim, "tower", selected, now):
			ui.toast(L.t(reason) if reason != "" else tr("toast.cant_build"))
			return
		ui.toast(tr("toast.tower_building") % GameUI.fmt_time(int(econ.buildings_at(selected)[-1]["upgrade_end"]) - now))
	else:
		var reason2: String = econ.can_upgrade(tower, now)
		if reason2 != "" or not econ.start_upgrade(tower["id"], now):
			ui.toast(L.t(reason2) if reason2 != "" else tr("toast.cant_upgrade"))
			return
		ui.toast(tr("toast.tower_upgrade") % (int(tower["level"]) + 1))
	sfx.play("coin")
	map_view.burst(selected, Color(1.0, 0.85, 0.3))
	_stat("towers")
	_econ_tick()
	_autosave()


func _fort_action() -> void:
	if selected < 0 or sim.cells[selected]["owner"] != Types.PLAYER:
		ui.toast(tr("toast.pick_own_hex"))
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
			ui.toast(L.t(reason) if reason != "" else tr("toast.cant_build"))
			return
		ui.toast(tr("toast.fort_building") % GameUI.fmt_time(int(econ.buildings_at(selected)[-1]["upgrade_end"]) - now))
	else:
		var reason2: String = econ.can_upgrade(fort, now)
		if reason2 != "" or not econ.start_upgrade(fort["id"], now):
			ui.toast(L.t(reason2) if reason2 != "" else tr("toast.cant_upgrade"))
			return
		ui.toast(tr("toast.fort_upgrade") % (int(fort["level"]) + 1))
	sfx.play("coin")
	map_view.burst(selected, Color(1.0, 0.85, 0.3))
	_stat("forts")
	if ftue == 9:
		# scripted marauder raid breaks against the new fence (canon §14.3, 5:00–6:00)
		ftue = 0
		_ftue_next = 10  # then war 2 with the Hamlets
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
		ui.toast(L.t(reason))
		return
	deposits.send(sim, hex, econ.dev_level(), now_s(), not first_convoy_done)
	first_convoy_done = true
	if ftue == 8:
		ftue = 9
	var cv: Dictionary = deposits.convoy_for(hex)
	sfx.play("tap")
	ui.toast(tr("toast.convoy_sent") % GameUI.fmt_time(int(cv["back"]) - now_s()))
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
		ui.toast(tr("toast.storage_full"))
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
	ui.toast(tr("toast.collected") % [int(gained.get("gold", 0)), int(gained.get("food", 0)), int(gained.get("metal", 0))])
	_econ_tick()
	_autosave()


func _open_tab(t: String) -> void:
	tab = t
	hud.select_tab(t)
	if t == "buildings":
		ui.show_buildings(_building_items(now_s()))
	elif t == "army":
		ui.show_armies(_army_items(now_s()))
	elif t == "diplomacy":
		ui.show_diplomacy(_diplomacy_items(now_s()))
	elif t == "world":
		ui.show_world(_world_items())
	elif t == "development":
		ui.show_buildings(_research_items(now_s()))
	else:
		ui.hide_buildings()


# ---------------------------------------------------------------------- store & cases (canon §15)

func _case_ctx() -> Dictionary:
	return {"income_per_hour": econ.gross_per_hour(sim), "dl": econ.dev_level()}


## Real-money items are hidden in Russia (decision 16; the store country comes from the store SDK later,
## the device locale stands in for it now). Raivite items and cases work everywhere (decisions 7, 13).
func _payments_enabled() -> bool:
	return not OS.get_locale().to_upper().ends_with("RU")


func _open_shop() -> void:
	if shop:
		shop.queue_free()
	shop = ShopUI.new()
	ui.root.add_child(shop)
	shop.setup(ui, cases, int(econ.res["raivite"]), _payments_enabled(), now_s())
	shop.open_case.connect(_on_open_case)
	shop.buy_sku.connect(_on_buy_sku)
	shop.closed.connect(func():
		shop.queue_free()
		shop = null)


func _on_open_case(case_id: String, times: int, pay: String) -> void:
	var now := now_s()
	match pay:
		"free":
			if not cases.use_free_crate(now):
				ui.toast(tr("toast.crate_not_ready"))
				return
		"ad":
			if not _rewarded("ad_free_crate", 2):
				return
		"raivite":
			var price: int = cases.price_x10(case_id) if times == 10 else cases.price(case_id)
			if int(econ.res["raivite"]) < price:
				ui.toast(tr("toast.no_raivite"))
				return
			econ.res["raivite"] = int(econ.res["raivite"]) - price
	var results: Array = cases.open_x10(case_id, _case_ctx(), now) if times == 10 else [cases.open(case_id, _case_ctx(), now)]
	_apply_case_rewards(results)
	sfx.play("capture")
	sfx.haptic(30)
	shop.refresh(int(econ.res["raivite"]), now)
	shop.show_reveal(results)
	_autosave()


func _apply_case_rewards(results: Array) -> void:
	for r in results:
		for rw in r.get("rewards", []):
			match String(rw.get("kind", "")):
				"res":
					econ.add_resources(rw["res"])
				"speedup":
					speed_minutes += int(rw["minutes"])
				_:
					pass  # shards, cosmetics and glitter are kept by the cases module itself


## Store purchases: no billing SDK yet. Debug (test) builds grant the item so flows can be tested.
func _on_buy_sku(sku: String) -> void:
	if not OS.is_debug_build():
		ui.toast(tr("toast.purchases_soon"))
		return
	var first: bool = not purchases.has(sku)
	purchases[sku] = int(purchases.get(sku, 0)) + 1
	for row in ShopUI.RAIVITE_SKUS:
		if row[0] == sku:
			var n: int = int(row[2]) * (2 if first else 1)
			econ.res["raivite"] = int(econ.res["raivite"]) + n
			ui.toast(tr("toast.test_raivite") % n)
	match sku:
		"iap_builder":
			if first:
				econ.builders += 1
				econ.res["raivite"] = int(econ.res["raivite"]) + 300
				ui.toast(tr("toast.test_builder"))
		"iap_starter":
			econ.res["raivite"] = int(econ.res["raivite"]) + 250
			var g: Dictionary = econ.gross_per_hour(sim)
			econ.add_resources({"gold": int(g.get("gold", 0)) * 8, "food": int(g.get("food", 0)) * 8, "metal": int(g.get("metal", 0)) * 8})
			ui.toast(tr("toast.test_starter"))
		"iap_no_ads":
			econ.res["raivite"] = int(econ.res["raivite"]) + 200
			ui.toast(tr("toast.test_no_ads"))
		"iap_ration":
			econ.res["raivite"] = int(econ.res["raivite"]) + 300
			ui.toast(tr("toast.test_ration"))
	sfx.play("coin")
	if shop:
		shop.refresh(int(econ.res["raivite"]), now_s())
	_econ_tick()
	_autosave()


# ---------------------------------------------------------------------- research (canon §12.3)

func _academy_level() -> int:
	for b in econ.buildings:
		if b["type"] == "academy":
			return int(b["level"])
	return 1


func _research_items(now: int) -> Array:
	var items: Array = []
	var dl: int = econ.dev_level()
	var acad := _academy_level()
	for line in Research.ORDER:
		var spec: Dictionary = Research.LINES[line]
		var busy: bool = not research.current.is_empty() and research.current["line"] == line
		var left := int(research.current["end"]) - now if busy else 0
		var maxed: bool = research.level(line) >= int(spec["max"])
		items.append({"id": -1, "line": line, "name": tr(String(spec["name"])), "level": research.level(line),
			"max": research.max_level(line, dl, acad), "busy": busy, "left": left,
			"speed": Economy.speedup_price(left) if busy else 0, "cost": research.cost(line) if not maxed else {},
			"seconds": research.seconds(line, acad) if not maxed else 0,
			"reason": L.t(research.can_start(line, dl, acad, econ.res, now)), "stock": speed_minutes})
	items.sort_custom(func(x, y): return int(x["busy"]) > int(y["busy"]))
	return items


func _on_research_start(line: String) -> void:
	var now := now_s()
	if not research.start(line, econ.dev_level(), _academy_level(), econ.res, now):
		ui.toast(L.t(research.can_start(line, econ.dev_level(), _academy_level(), econ.res, now)))
		return
	sfx.play("coin")
	ui.toast(tr("toast.research_started") % [tr(String(Research.LINES[line]["name"])), research.level(line) + 1, GameUI.fmt_time(int(research.current["end"]) - now)])
	_econ_tick()
	_autosave()


func _on_research_speedup(_line: String) -> void:
	if research.current.is_empty():
		return
	var now := now_s()
	var left := int(research.current["end"]) - now
	if speed_minutes > 0 and left > Economy.FREE_FINISH_SEC:
		var use := mini(speed_minutes, int(ceil(left / 60.0)))
		speed_minutes -= use
		research.current["end"] = int(research.current["end"]) - use * 60
	else:
		var price := Economy.speedup_price(left)
		if int(econ.res["raivite"]) < price:
			ui.toast(tr("toast.no_raivite"))
			return
		econ.res["raivite"] = int(econ.res["raivite"]) - price
		research.current["end"] = now
	_econ_tick()
	_autosave()


func _on_research_done(line: String) -> void:
	ui.toast(tr("toast.research_done") % [tr(String(Research.LINES[line]["name"])), research.level(line), tr(String(Research.LINES[line]["desc"]))])
	sfx.play("capture")
	if line == "infantry":
		_rescale_armies()


# ---------------------------------------------------------------------- chapter (canon §12.1)

## Chapter I stars: 10 Raivites + 1 h of production each; all stars give a cosmetic (canon §12.1).
const STARS := [
	["peace", "star.peace", "peaces", 1],
	["goal", "star.goal", "goals", 1],
	["pocket", "star.pocket", "pockets", 1],
	["colonize", "star.colonize", "colonized", 3],
	["fort", "star.fort", "forts", 1],
	["convoy", "star.convoy", "convoys", 3],
	["defense", "star.defense", "defenses", 1],
	["dl3", "star.dl3", "", 3],
]


func _stat(key: String) -> void:
	stats[key] = int(stats.get(key, 0)) + 1


func _star_progress(st: Array) -> int:
	if String(st[2]) == "":
		return econ.dev_level()
	return int(stats.get(String(st[2]), 0))


func _world_items() -> Array:
	var items: Array = [{"kind": "chapter", "hexes": _player_hexes(), "goal": CHAPTER_GOAL, "done": chapter_done,
		"can_expand": _player_hexes() >= CHAPTER_GOAL and war.is_empty() and not chapter_done}]
	for st in STARS:
		var prog := mini(_star_progress(st), int(st[3]))
		items.append({"kind": "star", "id": st[0], "title": tr(String(st[1])), "progress": prog, "need": st[3],
			"claimed": stars_claimed.has(st[0])})
	return items


func _on_world_action(id: String) -> void:
	if id == "expand":
		_complete_chapter()
		return
	for st in STARS:
		if st[0] == id and not stars_claimed.has(id) and _star_progress(st) >= int(st[3]):
			stars_claimed[id] = true
			var gross: Dictionary = econ.gross_per_hour(sim)
			econ.add_resources({"gold": int(gross.get("gold", 0)), "food": int(gross.get("food", 0)), "metal": int(gross.get("metal", 0))})
			econ.res["raivite"] = int(econ.res["raivite"]) + 10
			sfx.play("capture")
			ui.toast(tr("toast.star"))
			if stars_claimed.size() == STARS.size():
				_post("inbox.all_stars.title", "inbox.all_stars.text")
				ui.toast(tr("toast.all_stars"))
	_econ_tick()
	_autosave()


## Content wall (canon §12.1): chapter II is not out yet — the legacy is paid and a teaser shown.
func _complete_chapter() -> void:
	if chapter_done or _player_hexes() < CHAPTER_GOAL or not war.is_empty():
		return
	chapter_done = true
	econ.res["raivite"] = int(econ.res["raivite"]) + 200
	map_view.fireworks(map_view.cell_world(sim.states[Types.PLAYER]["capital_id"]), 5)
	sfx.play("fanfare")
	_post("inbox.chapter_done.title", "inbox.chapter_done.text")
	ui.toast(tr("toast.chapter_done"))
	_autosave()


# ---------------------------------------------------------------------- diplomacy (canon §10.4–10.6)

## Leader name, archetype and character (translation keys).
const LEADERS := {2: ["leader.barons", "archetype.wolf", "leader.barons.desc"],
	3: ["leader.hamlets", "archetype.fox", "leader.hamlets.desc"]}


func _opinion_add(s: int, v: float) -> void:
	opinion[s] = float(opinion.get(s, 0.0)) + v


## Memory fades by 0.5 per hour toward zero (canon §10.5).
func _opinion_decay(now: int) -> void:
	if _last_opinion == 0:
		_last_opinion = now
	var hours := float(now - _last_opinion) / 3600.0
	_last_opinion = now
	if hours <= 0.0:
		return
	for k in opinion.keys():
		var v: float = opinion[k]
		opinion[k] = move_toward(v, 0.0, 0.5 * hours)


func _opinion_of(s: int) -> float:
	var v: float = opinion.get(s, 0.0)
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and _touches_owner(c["id"], s):
			return v - 10.0  # a shared border, permanently
	return v


## Translation key of the opinion word.
static func _opinion_word(v: float) -> String:
	if v <= -50.0:
		return "opinion.hostile"
	if v < -10.0:
		return "opinion.wary"
	if v <= 10.0:
		return "opinion.neutral"
	if v <= 50.0:
		return "opinion.friendly"
	return "opinion.ally"


func _diplomacy_items(now: int) -> Array:
	var items: Array = []
	for s in [MapGen.BARONS, MapGen.HAMLETS]:
		var status: String = tr("dipl.peace")
		if not war.is_empty() and int(war["enemy"]) == s:
			status = tr("dipl.war")
		elif _truce_left(s) > 0:
			status = tr("dipl.truce") % GameUI.fmt_time(_truce_left(s))
		var gift_left := maxi(0, int(gift_at.get(s, 0)) + 86400 - now)
		var v := _opinion_of(s)
		items.append({"id": s, "state": _state_name(s), "leader": tr(String(LEADERS[s][0])), "archetype": tr(String(LEADERS[s][1])),
			"opinion": v, "word": tr(_opinion_word(v)), "status": status,
			"can_war": war.is_empty() and _truce_left(s) == 0, "gift_cost": _gift_cost(), "gift_left": gift_left,
			"color": map_view.state_color(s)})
	return items


func _gift_cost() -> int:
	return maxi(50, int(econ.gross_per_hour(sim).get("gold", 0)))


func _on_diplomacy_action(s: int, kind: String) -> void:
	match kind:
		"war":
			var g := War.recommend_goals(sim, s, 1)
			if g.is_empty():
				ui.toast(tr("toast.no_border"))
				return
			rig.focus(map_view.cell_world(g[0]))
			_select(g[0])
			ui.toast(tr("toast.target_chosen"))
		"gift":
			var cost := _gift_cost()
			if int(gift_at.get(s, 0)) + 86400 > now_s():
				ui.toast(tr("toast.gift_daily"))
				return
			if econ.res["gold"] < cost:
				ui.toast(tr("toast.no_gold"))
				return
			econ.res["gold"] -= cost
			var emb := 0
			for b in econ.buildings:
				if b["type"] == "embassy":
					emb = int(b["level"])
			_opinion_add(s, 10.0 * (1.0 + 0.05 * emb))
			gift_at[s] = now_s()
			sfx.play("coin")
			ui.toast(tr("toast.gift_thanks") % tr(String(LEADERS[s][0])))
		"alliance":
			ui.toast(tr("toast.alliances_later"))
	_econ_tick()
	_autosave()


# ---------------------------------------------------------------------- armies (canon §8.1)

const ARMY_LIMIT: Array[int] = [2, 2, 2, 3, 3, 3, 4, 4, 5, 5, 6]  # index = DL
const SLOT_LIMIT: Array[int] = [3, 3, 3, 3, 4, 4, 4, 5, 5, 5, 5]
const INF_TRAIN_SEC: Array[int] = [20, 20, 60, 180, 360, 600, 900, 1500, 2400, 3000, 3600]
const REFILL_FULL_SEC: Array[int] = [1200, 1200, 1200, 2400, 2400, 3600, 3600, 5400, 5400, 7200, 7200]


## Army food upkeep, thousandths per hour (04 §6.1): 0.1 × max strength, ×1.5 while at war, −3% per Thrift level.
func _army_food_milli() -> int:
	var total := 0
	for a in _player_armies():
		total += int(a["max_str"]) / 10  # max_str is in thousandths: 0.1 × (max_str / 1000) food/h
	if not war.is_empty():
		total = total * 3 / 2
	return total * (100 - 3 * research.level("thrift")) / 100


func _player_armies() -> Array:
	var out: Array = []
	for a in armies:
		if a["side"] == Types.PLAYER:
			out.append(a)
	return out


## Healing costs 1 food per point of Strength × М_произв / М_силы; full in 20–120 min by DL; Лазарет +5%/ур.
func _army_refill(now: int) -> void:
	if _last_refill == 0:
		_last_refill = now
	var dt := now - _last_refill
	_last_refill = now
	if dt <= 0 or mode == Mode.BATTLE:
		return
	var dl: int = econ.dev_level()
	var inf_lvl := 1
	for b in econ.buildings:
		if b["type"] == "infirmary":
			inf_lvl = int(b["level"])
	var speed: float = (1.0 + 0.05 * inf_lvl) * (1.0 + 0.05 * research.level("reserve"))
	var food_per_fx := float(Economy.PROD_MULT100[dl]) / 100.0 / Types.strength_mult(maxi(1, dl)) / 1000.0
	for a in _player_armies():
		var missing: int = int(a["max_str"]) - int(a["str"])
		if missing <= 0:
			continue
		var heal := mini(missing, int(float(a["max_str"]) * dt * speed / REFILL_FULL_SEC[dl]))
		var afford := int(floor(float(econ.res["food"]) / maxf(food_per_fx, 1e-9)))
		heal = mini(heal, afford)
		if heal <= 0:
			continue
		a["str"] = int(a["str"]) + heal
		econ.res["food"] = maxi(0, int(econ.res["food"]) - int(ceil(heal * food_per_fx)))


## New DL raises max Strength; readiness in % is kept (canon §8.1).
func _rescale_armies() -> void:
	var dl: int = econ.dev_level()
	var fam: float = 1.0 + 0.06 * research.level("infantry")  # family level 1 + researched levels (canon §8.1)
	for a in _player_armies():
		var slots: int = int(a.get("slots", 3))
		var ready := float(a["str"]) / maxf(1.0, float(a["max_str"]))
		var mx := Types.js_round(Armies.INFANTRY_BASE * slots * Types.strength_mult(dl) * fam * Types.FX)
		a["max_str"] = mx
		a["str"] = int(round(float(mx) * ready))


func _train_cost() -> Dictionary:
	var dl: int = econ.dev_level()
	var slots: int = SLOT_LIMIT[dl]
	var t: int = int(INF_TRAIN_SEC[dl] * slots * maxf(0.25, 1.0 - 0.05 * research.level("drill")))
	return {"food": int(ceil(40.0 * slots * Economy.PROD_MULT100[dl] / 100.0)), "seconds": t, "slots": slots}


func _train_army() -> void:
	var dl: int = econ.dev_level()
	if _player_armies().size() >= ARMY_LIMIT[dl]:
		ui.toast(tr("toast.army_limit"))
		return
	if not training.is_empty():
		ui.toast(tr("toast.army_training"))
		return
	var cost := _train_cost()
	if econ.res["food"] < int(cost["food"]):
		ui.toast(tr("toast.no_food"))
		return
	econ.res["food"] -= int(cost["food"])
	training = {"end": now_s() + int(cost["seconds"]), "slots": int(cost["slots"])}
	sfx.play("coin")
	ui.toast(tr("toast.recruits") % GameUI.fmt_time(int(cost["seconds"])))
	_autosave()


func _finish_training() -> void:
	var cap: int = sim.states[Types.PLAYER]["capital_id"]
	var id := 1
	for a in armies:
		id = maxi(id, int(a["id"]) + 1)
	var fresh := Armies.infantry_army(id, Types.PLAYER, cap, int(training["slots"]), econ.dev_level())
	fresh["slots"] = int(training["slots"])
	armies.append(fresh)
	_rescale_armies()
	training = {}
	_normalize_armies()
	map_view.burst(cap, MapView.C_PLAYER, true)
	sfx.play("fanfare")
	ui.toast(tr("toast.army_ready"))
	_autosave()


## Rewarded placement with a daily cap (canon §15.2). Test builds grant the reward without an SDK.
func _rewarded(key: String, cap: int) -> bool:
	var day := now_s() / 86400
	var rec: Array = ad_counts.get(key, [day, 0])
	if int(rec[0]) != day:
		rec = [day, 0]
	if int(rec[1]) >= cap:
		ui.toast(tr("toast.ad_limit"))
		return false
	rec[1] = int(rec[1]) + 1
	ad_counts[key] = rec
	ui.toast(tr("toast.test_ad_reward"))
	return true


func _army_items(now: int) -> Array:
	var items: Array = []
	var i := 1
	for a in _player_armies():
		items.append({"id": a["id"], "name": tr("army.name") % i, "str": int(round(float(a["str"]) / 1000.0)), "max": int(round(float(a["max_str"]) / 1000.0)),
			"slots": int(a.get("slots", 3)),
			"upkeep": roundi(int(a["max_str"]) / 10000.0 * (1.5 if not war.is_empty() else 1.0) * (1.0 - 0.03 * research.level("thrift"))),
			"refilling": int(a["str"]) < int(a["max_str"])})
		i += 1
	var dl: int = econ.dev_level()
	var cost := _train_cost()
	var need := dl
	while need < 10 and ARMY_LIMIT[need] <= _player_armies().size():
		need += 1
	var new_item := {"id": -1, "name": tr("army.new"), "locked": _player_armies().size() >= ARMY_LIMIT[dl], "need_dl": need, "food": cost["food"], "seconds": cost["seconds"]}
	if not training.is_empty():
		new_item["left"] = int(training["end"]) - now
	items.append(new_item)
	return items


func _on_army_action(id: int, kind: String) -> void:
	if kind == "train":
		_train_army()
	elif kind == "refill" and _rewarded("ad_army_refill", 3):
		for a in armies:
			if int(a["id"]) == id:
				a["str"] = a["max_str"]
	_econ_tick()


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
		items.append({"id": b["id"], "name": tr(String(info["name"])), "level": b["level"], "max": econ.max_level(b),
			"busy": busy, "left": int(b["upgrade_end"]) - now, "speed": econ.speedup_cost(b, now),
			"cost": cost, "seconds": secs, "reason": L.t(reason), "stock": speed_minutes})
	items.sort_custom(func(x, y): return int(x["busy"]) > int(y["busy"]))
	if Market.market_level(econ) > 0:
		items.push_front({"id": -100, "market": true, "name": tr("bld.market"), "rate": Market.rate_milli(Market.market_level(econ))})
	return items


# ---------------------------------------------------------------- market (05 §13)

func _open_market() -> void:
	if Market.market_level(econ) <= 0:
		ui.toast(tr("market.locked"))
		return
	var now := now_s()
	econ.tick(sim, now)
	market.refresh(econ, sim, now)
	var lots: Array = []
	for i in market.lots.size():
		var lot: Dictionary = market.lots[i].duplicate()
		lot["ok"] = market.can_buy(econ, i) == ""
		lots.append(lot)
	var lvl: int = Market.market_level(econ)
	var info := {"level": lvl, "rate": Market.rate_milli(lvl), "res": econ.res.duplicate(), "cap": econ.storage_cap(),
		"lots": lots, "refresh_left": Market.refresh_left(now), "sel": market_sel}
	ui.show_market(info, func(g: String, r: String, amt: int) -> Dictionary: return Market.quote(econ, g, r, amt),
		_on_market_exchange, _on_market_lot)


func _on_market_exchange(give: String, get_res: String, amount: int) -> void:
	var q: Dictionary = Market.exchange(econ, give, get_res, amount)
	if q.is_empty():
		ui.toast(tr("market.no_space"))
		return
	_market_done(give, int(q["give"]), get_res, int(q["get"]))


func _on_market_lot(i: int) -> void:
	var reason: String = market.can_buy(econ, i)
	if reason != "":
		ui.toast(tr(reason))
		return
	var lot: Dictionary = market.lots[i]
	market.buy(econ, i)
	_market_done(String(lot["give"]), int(lot["give_amt"]), String(lot["get"]), int(lot["get_amt"]))


func _market_done(give: String, gave: int, get_res: String, got: int) -> void:
	_stat("trades")
	sfx.play("coin")
	sfx.haptic(20)
	_econ_tick()
	_open_market()
	ui.toast(tr("market.done") % [GameUI.fmt_num(gave), tr("res.gen." + give), GameUI.fmt_num(got), tr("res.gen." + get_res)])
	_autosave()


## «Склад почти полон → Рынок» (05 §13.4): once per resource each time it climbs to ≥90% of the cap;
## the Market then opens with that resource under «Отдаю».
func _market_hint() -> void:
	if Market.market_level(econ) <= 0 or mode != Mode.MAP or ftue != 0 or ui.has_modal():
		return
	var cap: Dictionary = econ.storage_cap()
	for r in Economy.RES:
		var full := float(econ.res.get(r, 0)) / maxf(1.0, float(cap[r]))
		if full >= 0.9 and not _full_hinted.has(r):
			_full_hinted[r] = true
			ui.toast(tr("market.full_hint") % tr("res.gen." + r))
			if market_sel["get"] == r:
				market_sel["get"] = market_sel["give"]
			market_sel["give"] = r
			return
		elif full < 0.8:
			_full_hinted.erase(r)


func _on_building_upgrade(id: int) -> void:
	var now := now_s()
	econ.tick(sim, now)
	var b: Dictionary = econ.building(id)
	var reason: String = econ.can_upgrade(b, now)
	if reason != "" or not econ.start_upgrade(id, now):
		ui.toast(L.t(reason) if reason != "" else tr("toast.cant_upgrade"))
		return
	sfx.play("coin")
	sfx.haptic(20)
	ui.toast(tr("toast.upgrade_started") % [tr(String(Economy.BUILDINGS[b["type"]]["name"])), int(b["level"]) + 1, GameUI.fmt_time(int(b["upgrade_end"]) - now)])
	if ftue == 7 and b["type"] == "residence":
		ftue = 8
	_econ_tick()
	_autosave()


func _on_building_speedup(id: int) -> void:
	var now := now_s()
	var b: Dictionary = econ.building(id)
	# speed-up items from cases go first (whole minutes), then Raivites for the rest
	var left := int(b["upgrade_end"]) - now
	if speed_minutes > 0 and left > Economy.FREE_FINISH_SEC:
		var use := mini(speed_minutes, int(ceil(left / 60.0)))
		speed_minutes -= use
		b["upgrade_end"] = int(b["upgrade_end"]) - use * 60
		ui.toast(tr("toast.stock_used") % [use, speed_minutes])
		_econ_tick()
		_autosave()
		return
	if econ.res["raivite"] < econ.speedup_cost(b, now):
		ui.toast(tr("toast.no_raivite"))
		return
	if econ.finish_now(id, now):
		_econ_tick()
		_autosave()


# ====================================================================== AI aggression (chapter I: scripted only)

## Inbox report: title / text are translation keys, optionally packed with arguments (L.pack), so old
## reports follow a later language switch.
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
		map_view.floater(h, tr("floater.raid_repelled"), Color(0.75, 0.85, 1.0))
		_stat("defenses")
		sfx.play("repelled")
		_post("inbox.raid.title", L.pack("inbox.raid.text", [_cell_key(h)]))
		ui.toast(tr("toast.raid_repelled"))
		if _ftue_next == 10:
			_ftue_next = 0
			ftue = 10 if _hamlets_target() >= 0 else 0
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
	_post(L.pack("inbox.ultimatum.title", [_state_key(MapGen.BARONS)]), L.pack("inbox.ultimatum.text", [_cell_key(best), tribute]))
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
			_opinion_add(enemy, 20.0)
			map_view.refresh_hex(hex)
			map_view.mark_dirty()
			_normalize_armies()
			_post("inbox.ceded.title", L.pack("inbox.ceded.text", [_cell_key(hex)]))
		"pay":
			if econ.res["gold"] < int(ultimatum["tribute"]):
				ui.toast(tr("toast.no_gold"))
				return
			econ.res["gold"] -= int(ultimatum["tribute"])
			truce[enemy] = now + 24 * 3600
			_post("inbox.tribute.title", L.pack("inbox.tribute.text", [int(ultimatum["tribute"])]))
		"refuse":
			_ensure_armies_for(enemy)
			_deploy_to_front(enemy)
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
			_opinion_add(enemy, -50.0)
			map_view.at_war_with = enemy
			map_view.mark_dirty()
			sfx.play("warn")
			_post("inbox.war.title", L.pack("inbox.war.text", [_state_key(enemy), _cell_key(hex)]))
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
	_stat("defenses")
	var gold := int(maxi(60, int(econ.gross_per_hour(sim).get("gold", 0))) / 2.0)
	econ.add_resources({"gold": gold})
	map_view.burst(hex, MapView.C_PLAYER, true)
	map_view.floater(hex, tr("floater.repelled_short"), Color(0.75, 0.85, 1.0))
	sfx.play("repelled")
	var msg := L.pack("inbox.defense.text", [_state_key(int(war["enemy"])), _cell_key(hex), gold])
	_post("inbox.defense.title", msg)
	ui.toast(L.t(msg))
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
		_post("inbox.war_cap.title", "inbox.war_cap.peace")
		_sign_peace()
	elif ws["score"] > -10.0:
		War.white_peace(sim)
		_post("inbox.war_cap.title", "inbox.war_cap.white")
		_finish_war(enemy, tr("toast.war_cap_white"))
	else:
		_apply_defeat(enemy, _defeat_losses(enemy))


# ====================================================================== FTUE (canon §14.3)

## Coach lines by FTUE step (translation keys).
const FTUE_TEXT := {
	1: "ftue.1",
	7: "ftue.7",
	8: "ftue.8",
	9: "ftue.9",
	10: "ftue.10",
	11: "ftue.11",
	12: "ftue.12",
	13: "ftue.13",
	14: "ftue.14",
	15: "ftue.15",
	2: "ftue.2",
	3: "ftue.3",
	4: "ftue.4",
	5: "ftue.5",
	6: "ftue.6",
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
	elif ftue == 12:
		ftue = 13


## FTUE war 2 goal (canon §14.3): the Hamlets' mine at the border, else their best border hex.
func _hamlets_target() -> int:
	if not war.is_empty() or _truce_left(MapGen.HAMLETS) > 0:
		return -1
	var core := MapGen.core_of(sim, MapGen.HAMLETS)
	var goals := War.recommend_goals(sim, MapGen.HAMLETS, 3)
	for g in goals:
		if sim.cells[g]["kind"] == "mine" and not core.has(g):
			return g
	return goals[0] if goals.size() > 0 else -1


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
			if why.begins_with("err.need_hexes"):
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
		10:
			var ht := _hamlets_target()
			if ht < 0 and mode == Mode.MAP:
				ftue = 0
				return
			if mode == Mode.MAP and (selected < 0 or sim.cells[selected]["owner"] != MapGen.HAMLETS) and ht >= 0:
				rig.focus(map_view.cell_world(ht))
				_select(ht)
			target = Vector2(793, GameUI.VH - 76)
		11:
			target = Vector2(793, GameUI.VH - 76) if mode == Mode.WAR else Vector2(285, 998)
		12:
			target = Vector2(445, GameUI.VH - 124)
		14:
			target = Vector2(655, 998) if mode == Mode.RESULT else Vector2(793, GameUI.VH - 200)
		15:
			target = Vector2(274, 1380)
	if _ftue_shown != ftue:
		_ftue_shown = ftue
		_ftue_t = 0.0
		ui.coach(tr(String(FTUE_TEXT[ftue])), target)
	_ftue_t += delta
	ui.coach_target(target)
	if (ftue == 4 or ftue == 13) and _ftue_t > 6.0:
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
			if _camp_fight.is_empty():
				_end_offensive()
			else:
				_end_camp_fight()
	elif mode == Mode.CEREMONY:
		_step_ceremony(delta)
	_step_marches()
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

## `--lang=ru|en` is consumed first, by _init_language() in _ready, before the HUD and UI are built.
func _handle_args() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot(a.substr(7))  # starts first: a failing argument below can't leave the process hanging
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
	if what == "shop" or what == "royal":
		econ.res["raivite"] = 2000
		_open_shop()
		if what == "royal":
			_on_open_case("case_royal", 10, "raivite")
		return
	if what == "settings":
		_on_hud_button("gear")
		return
	if what == "camp":
		_camps_tick(now_s())
		var best := -1
		var cap: int = sim.states[Types.PLAYER]["capital_id"]
		for cm in camps.active:
			var h: int = cm["hex"]
			if best < 0 or map_view.cell_world(h).distance_to(map_view.cell_world(cap)) < map_view.cell_world(best).distance_to(map_view.cell_world(cap)):
				best = h
		_select(best)
		rig.focus(map_view.cell_world(best), 0.4)
		return
	if what == "forts":
		var cap: int = sim.states[Types.PLAYER]["capital_id"]
		sim.cells[cap]["fort"] = 3
		var lv := 1
		for n in sim.neighbors[cap]:
			if n >= 0 and sim.cells[n]["owner"] == Types.PLAYER:
				sim.cells[n]["fort"] = lv
				lv = lv % 8 + 1
		map_view.refresh_props()
		rig.focus(map_view.cell_world(cap), 0.3)
		return
	if what == "tower":
		var cap: int = sim.states[Types.PLAYER]["capital_id"]
		for n in sim.neighbors[cap]:
			if n >= 0 and sim.cells[n]["kind"] == "plain" and econ.can_build(sim, "tower", n, now_s()) == "":
				_select(n)
				_tower_action()
				econ.buildings_at(n)[-1]["upgrade_end"] = 1
				_econ_tick()
				rig.focus(map_view.cell_world(n), 0.4)
				break
		return
	if what == "ruin":
		_apply_defeat(MapGen.BARONS, [])
		var dh: int = econ.damaged.keys()[0]
		_select(dh)
		rig.focus(map_view.cell_world(dh), 0.4)
		return
	if what == "march":
		var ma: Dictionary = _player_armies()[0]
		var far := -1
		var far_s := 0
		for c in sim.cells:
			var r: Dictionary = March.route(sim, Types.PLAYER, int(ma["hex"]), c["id"])
			if not r.is_empty() and int(r["seconds"]) > far_s and int(r["seconds"]) <= 160:
				far = c["id"]
				far_s = r["seconds"]
		_select(int(ma["hex"]))
		_on_action("march")
		_march_to(far)
		time_offset += 30
		_step_marches()
		rig.focus(map_view.cell_world(far), 0.55)
		return
	if what == "market":
		var r: Dictionary = econ._find_type("residence")
		r["upgrade_end"] = 1
		econ.tick(sim, now_s())
		econ.res.merge({"gold": 3200, "food": 4700, "metal": 900}, true)
		_open_market()
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
