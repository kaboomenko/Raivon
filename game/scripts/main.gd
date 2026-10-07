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
const Orders := preload("res://scripts/sim/orders.gd")
const BattlePass := preload("res://scripts/sim/battlepass.gd")
const Weekly := preload("res://scripts/sim/weekly.gd")
const Calendar := preload("res://scripts/sim/calendar.gd")
const Patent := preload("res://scripts/sim/patent.gd")
const Chronicle := preload("res://scripts/sim/chronicle.gd")
const Commanders := preload("res://scripts/sim/commanders.gd")
const FlagView := preload("res://scripts/flag_view.gd")
const March := preload("res://scripts/sim/march.gd")
const Camps := preload("res://scripts/sim/camps.gd")
const RingGen := preload("res://scripts/sim/ring_gen.gd")
const RingNext := preload("res://scripts/sim/ring_next.gd")
const Rng := preload("res://scripts/sim/rng.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")
const Net := preload("res://scripts/net.gd")
const ShopUI := preload("res://scripts/shop_ui.gd")
const L := preload("res://scripts/l10n.gd")

enum Mode { MAP, WAR, BATTLE, RESULT, PEACE, CEREMONY }

const MAP_SEED := 20261004
const HAND := ["attack", "breakthrough", "airstrike", "encircle", "defense"]
const AIRSTRIKE_DL := 6
## When each card opens (canon §9.9) — cards outside the list are open from DL1 in this build.
const CARD_DL := {"airstrike": 6, "landing": 7, "missile": 8}
const AIR_ARCHETYPES := ["wolf", "raven"]  # AI hands with «Авиаудар» (03 §19.4)
const CHAPTER_GOALS: Array[int] = [0, 20, 36, 56, 88]  # official hexes per chapter (canon §12.1)
const COLONIZE_SEC: Array[int] = [0, 60, 300, 900, 1800]  # 1 min in chapter I, 5 / 15 / 30 min later (canon §12.1)
const LAST_CHAPTER := 4  # the launch's content wall: chapter V comes with v1.2
const TRUCE_SEC := 30 * 60
## Translation keys of unnamed hexes: by kind, else by terrain.
const KIND_NAMES := {"capital": "kind.capital", "city": "kind.city", "farm": "kind.farm", "mine": "kind.mine", "port": "kind.port", "military_base": "kind.military_base",
	"raivite_vein": "kind.raivite_vein", "dark_lake": "kind.dark_lake", "oil": "kind.oil"}
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
var _flak_tick := -1
var stats_base3 := {}  # stats at the opening of chapter III (its stars count from there)
var stats_base4 := {}  # … and of chapter IV
var threat := 0.0        # «Угроза» (canon §10.8): annexations, plunder, treachery; −0.5 per hour
var threat_at := 0       # last decay time
var coalition := {}      # forming: {leader, members, at}; the war itself carries war["coalition"]
var coalition_last := 0  # last formation (not more than once in 5 days)
var _alarm_warned := false
var _swap := {}            # territory swap being set up: {state, give, get}
var swap_at := {}          # state -> last swap time (one swap with a state per 24 h)
var swap_offer_at := {}    # state -> when it next looks for a swap to propose (06 §9.1)
var swap_offer := {}       # the AI's pending proposal {state, give, get, until, auto}
var pacts := {}            # state -> non-aggression pact end (canon §10.8, 06 §11)
var _ftue_next := 0  # step to resume after the peace ceremony
var _raid := {}  # FTUE marauder raid: {hex, at}
var econ  # Economy (scripts/sim/economy.gd)
var deposits  # Deposits (scripts/sim/deposits.gd)
var first_convoy_done := false
var cases  # Cases (scripts/sim/cases.gd)
var research  # Research (scripts/sim/research.gd)
var market  # Market trader state (scripts/sim/market.gd)
var orders  # «Приказы дня» (scripts/sim/orders.gd)
var pass_xp := 0  # legacy: pass XP saved before the pass existed, moved into `bp` on load
var bp  # «Военный пропуск» (scripts/sim/battlepass.gd)
var weekly  # weekly tasks (scripts/sim/weekly.gd)
var calendar  # the 28-day login calendar (scripts/sim/calendar.gd)
var patent  # «Державный патент», the subscription (scripts/sim/patent.gd)
var chronicle  # «Летопись державы», 40 long goals (scripts/sim/chronicle.gd)
var flag: Dictionary = FlagView.DEFAULT.duplicate()  # the realm's flag (10 §4.23)
var realm_name := ""  # the player's name for the realm (canon §14.3); "" — «Ваша держава»
var commanders  # commander levels (scripts/sim/commanders.gd); the shards themselves are `cases.shards`
var hand_pick: Array = []
var installed_at := 0  # the first launch (offers that start «from D2», 09 §9.9.2)
var intro_offer_day := -1  # the game day the intro Patent offer was shown  # the player's slot cards (03 §5.2); empty — the default hand
var _cal_auto := false  # a new calendar day waits to be shown once the player is free (08 §8.8.1)
var _collect_counted := 0  # last «Собрать всё» counted for order_collect_3 (≥30 min apart)
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
var ult_check := {}  # AI state -> unix time of its next daily ultimatum roll (canon §10.4)
var allies: Array = []  # AI states allied with the player (canon §10.7)
var ai_alliances := {}  # AI state -> its AI ally (one each)
var ai_alliance_check := 0
var ai_wars: Array = []  # [{a, b, until, next}] AI-vs-AI wars (canon §10.10)
var ai_war_check := 0  # unix time of the next 6-hourly evaluation
var ai_colonizing := {}  # AI state -> {hex, at}: one settlement at a time, 3 h per hex (02 §10.2)
const WAR_CAP_SEC := 2 * 3600  # chapter I war cap (canon §9.1)
const STRIKE_WARN_SEC := 20 * 60  # strike announced 20 min ahead (canon §9.11)
var _econ_acc := 1.0
var _last_refill := 0
var training := {}  # new army being formed: {end, slots}
var stats := {}  # chapter counters for the stars: peaces, goals, pockets, colonized, forts, convoys, defenses
var stars_claimed := {}
var chapter_done := false
var chapter := 1  # open chapter: 1 «Долина», 2 «Речной край»
var stats_base := {}  # stats at the opening of chapter II (its stars count from there)
var ai_dl_at := {}  # AI state -> unix time of its last DL step (canon §9.16: +1 every 6 days)
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
	orders = Orders.new()
	bp = BattlePass.new()
	weekly = Weekly.new()
	calendar = Calendar.new()
	patent = Patent.new()
	chronicle = Chronicle.new()
	commanders = Commanders.new()
	installed_at = now_s()
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
	_fit_camera_bounds()
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
	if ftue == 0:
		_grant_bram()
	hud.set_flag(flag)
	map_view.set_flag(flag)
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


## Tilt-shift and vignette over the 3D map (art direction §1), under the HUD so the interface stays sharp.
func _add_tilt_shift() -> void:
	var layer := CanvasLayer.new()
	layer.layer = -1
	add_child(layer)
	var rect := ColorRect.new()
	rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/tilt_shift.gdshader")
	rect.material = mat
	layer.add_child(rect)


func _show_settings() -> void:
	var manage := Callable()
	if _payments_enabled():
		manage = func(): ui.toast(tr("settings.manage_soon"))  # showManageSubscriptions / the Play deep link with the SDK
	ui.show_settings(sfx.enabled, func(): sfx.enabled = not sfx.enabled, _new_game, _set_language, manage,
		func(): ui.toast(tr("patent.restored")))


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
	e.tonemap_exposure = 0.86
	# glow only on emissive things (neon borders, crystals, fire): a threshold above sunlit ground and no bloom,
	# otherwise the whole frame hazes into pastel (art direction: saturated, contrasty, CoC-like)
	e.glow_enabled = true
	e.glow_intensity = 1.0
	e.glow_strength = 1.1
	e.glow_bloom = 0.0
	e.glow_hdr_threshold = 1.1
	e.fog_enabled = true
	e.fog_light_color = Color(0.55, 0.62, 0.72)
	e.fog_density = 0.003
	e.adjustment_enabled = true
	e.adjustment_saturation = 1.28
	e.adjustment_contrast = 1.18
	we.environment = e
	add_child(we)

	_add_tilt_shift()
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -35, 0)
	sun.light_color = Color(1.0, 0.93, 0.82)
	sun.light_energy = 1.3
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
	ui.set_control(ws.get("score", 0.0), ws.get("control", 50), _state_name(enemy), not war.is_empty() and mode in [Mode.WAR, Mode.BATTLE, Mode.RESULT],
		[map_view.state_flag(Types.PLAYER), map_view.state_flag(enemy)])
	ui.set_battle(mode == Mode.BATTLE and battle != null, battle.energy[Types.PLAYER] if battle else 0, Battle.ENERGY_UNIT, _cooldowns(), battle.seconds_left() if battle else 0, battle != null and battle.is_rush())
	ui.set_corps(battle != null and (battle.opts.get("cards", []) as Array).has("corps") and not battle._corps_used.has(Types.PLAYER))
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
		elif _pact_left(c["owner"]) > 0:  # a pact is unbreakable for both sides (06 D5)
			ui.set_primary("truce", tr("dipl.pact") % GameUI.fmt_time(_pact_left(c["owner"])), Color(0.3, 0.35, 0.45), false)
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
	var enemy: int = _front()
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
	elif war.has("coalition"):
		ui.set_primary("offensive", "%s\n%s" % [tr("ui.offensive"), tr("ui.offensive_on") % _state_name(enemy)], Color(0.8, 0.22, 0.16))
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
			ui.toast(tr("toast.chapter_progress") % [_player_hexes(), _chapter_goal()])
		"book":
			_open_chronicle()
		"profile":
			if mode in [Mode.MAP, Mode.WAR]:
				_open_profile()
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
		"orders":
			_open_tab("world")
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


## Fog of war (canon §3.1, 02 §14.1): what the player sees — 2 hexes around every hex it controls and every army,
## 3 around a working tower (on its own, unoccupied land). Enemy army strength outside shows as «?».
func _fog_visible() -> Dictionary:
	var seen := {}
	var sources: Array = []  # [hex, radius]
	for c in sim.cells:
		if c["controller"] == Types.PLAYER:
			sources.append([int(c["id"]), 3 if int(c.get("tower", 0)) > 0 and c["owner"] == Types.PLAYER else 2])
	for a in _player_armies():
		sources.append([int(a["hex"]), 2])
	for src in sources:
		var frontier := [int(src[0])]
		var local := {int(src[0]): true}
		seen[int(src[0])] = true
		for step in int(src[1]):
			var nxt: Array = []
			for h in frontier:
				for n in sim.neighbors[h]:
					if n >= 0 and not local.has(n):
						local[n] = true
						seen[n] = true
						nxt.append(n)
			frontier = nxt
	return seen


## At DL5 every Dark Lake of the world wakes up as an Oil hex (canon §5.1).
func _wake_oil() -> void:
	if econ.dev_level() < Economy.OIL_DL:
		return
	var woke := 0
	for c in sim.cells:
		if c["kind"] == "dark_lake":
			c["kind"] = "oil"
			c["value"] = int(Types.KIND_VALUE["oil"])
			map_view.refresh_hex(int(c["id"]))
			woke += 1
	if woke > 0:
		map_view.mark_dirty()
		_post("inbox.oil.title", L.pack("inbox.oil.text", [woke]))
		ui.toast(tr("toast.oil_awake"))


const AI_DL_CAP: Array[int] = [0, 2, 4, 6, 8, 9, 10]  # by chapter (canon §9.16)
const AI_DL_STEP_SEC := 6 * 86400


## AI against AI (canon §10.10): every 6 h neighbouring AI states may go to war (one such war at a time,
## chance by the aggressor's archetype); every 2 h 1–3 border hexes change hands by strength, never cores;
## peace after 12–48 h annexes what is occupied. The player sees a foreign front with hatching and reports.
func _ai_wars_tick(now: int) -> void:
	if ftue != 0 or int(stats.get("peaces", 0)) < 1:
		return
	for w in ai_wars.duplicate():
		var a: int = w["a"]
		var b: int = w["b"]
		if now >= int(w["until"]):
			_ai_peace(w)
			continue
		while now >= int(w["next"]) and now < int(w["until"]):
			w["next"] = int(w["next"]) + 2 * 3600
			var pa: int = _ai_power(a) * (11 if int(w.get("boost", -1)) == a else 10)
			var pb: int = _ai_power(b) * (11 if int(w.get("boost", -1)) == b else 10)
			var strong := a if pa >= pb else b
			var weak := b if strong == a else a
			var n := 1 + _roll("aiw:%d:%d:%d" % [a, b, int(w["next"])], 3)
			var core := MapGen.core_of(sim, weak)
			var front: Array = []
			for c in sim.cells:
				if c["controller"] == weak and Types.is_passable(c) and not core.has(c["id"]) and _touches_controller(c["id"], strong):
					front.append(c)
			front.sort_custom(func(x, y): return int(x["value"]) < int(y["value"]) if int(x["value"]) != int(y["value"]) else int(x["id"]) < int(y["id"]))
			for c in front.slice(0, n):
				c["controller"] = strong
				map_view.refresh_hex(int(c["id"]))
			map_view.mark_dirty()
	if now < ai_war_check:
		return
	ai_war_check = now + 6 * 3600
	if not ai_wars.is_empty():
		return
	var at_war_with_player: int = war.get("enemy", -1)
	for a in _ai_states():
		for b in _ai_states():
			if a >= b or a == at_war_with_player or b == at_war_with_player or not _states_touch(a, b):
				continue
			if int(ai_alliances.get(a, -1)) == b:
				continue  # allies don't fight each other
			var agg: int = a if _ai_power(a) >= _ai_power(b) else b
			var chance: int = int(ULT_CHANCE.get(String(sim.states[agg]["archetype"]), 10)) / 2
			if _roll("aiwar:%d:%d:%d" % [a, b, now / (6 * 3600)], 100) < chance:
				var dur := (12 + _roll("aiwd:%d:%d" % [a, b], 37)) * 3600
				var victim: int = b if agg == a else a
				ai_wars.append({"a": agg, "b": victim, "until": now + dur, "next": now + 2 * 3600})
				_post("inbox.ai_war.title", L.pack("inbox.ai_war.text", [_state_key(agg), _state_key(victim)]))
				if allies.has(victim):
					_ally_asks(victim, agg)
				return


## Our ally is attacked by another AI (canon §10.7): support it with 4 h of gold (its armies +10% in that war,
## opinion +15) or refuse (opinion −15).
func _ally_asks(ally: int, attacker: int) -> void:
	var cost := 4 * maxi(60, int(econ.gross_per_hour(sim).get("gold", 0)))
	_post(L.pack("inbox.ally_asks.title", [_state_key(ally)]), L.pack("inbox.ally_asks.text", [_state_key(ally), _state_key(attacker)]))
	if mode != Mode.MAP or ui.has_modal():
		return
	ui.show_choice(tr("ally_ask.title") % _state_name(ally), [tr("ally_ask.text") % [_state_name(attacker), _state_name(ally)]], [
		[tr("ally_ask.support") % cost, Color(0.2, 0.55, 0.3), func():
			if econ.res["gold"] < cost:
				ui.toast(tr("toast.no_gold"))
				return
			econ.res["gold"] -= cost
			for w in ai_wars:
				if int(w["b"]) == ally or int(w["a"]) == ally:
					w["boost"] = ally
			_opinion_add(ally, 15.0)
			ui.close_modal()
			ui.toast(tr("toast.ally_supported") % _state_name(ally))
			_autosave()],
		[tr("ally_ask.refuse"), Color(0.45, 0.2, 0.18), func():
			_opinion_add(ally, -15.0)
			ui.close_modal()],
	])


func _ai_peace(w: Dictionary) -> void:
	ai_wars.erase(w)
	var a: int = w["a"]
	var b: int = w["b"]
	var moved := {a: 0, b: 0}
	for c in sim.cells:
		var o: int = c["owner"]
		var k: int = c["controller"]
		if (o == a and k == b) or (o == b and k == a):
			c["owner"] = k  # the treaty annexes what is occupied
			moved[k] = int(moved[k]) + 1
			map_view.refresh_hex(int(c["id"]))
	map_view.mark_dirty()
	var winner := a if int(moved[a]) >= int(moved[b]) else b
	var loser := b if winner == a else a
	_post("inbox.ai_peace.title", L.pack("inbox.ai_peace.text", [_state_key(winner), _state_key(loser), int(moved[winner])]))


func _states_touch(a: int, b: int) -> bool:
	for c in sim.cells:
		if c["owner"] == a and _touches_owner(c["id"], b):
			return true
	return false


## Alliances (canon §10.7): opinion ≥50 (an Owl ≥40), no war or truce between you, as many allies as the
## Embassy allows by DL (1 at DL3, 2 at DL5, 3 at DL7). "" when an alliance can be offered, else the reason.
# ---------------------------------------------------------------------- threat and coalitions (canon §10.8)

const COALITION_THRESHOLD: Array[int] = [0, 0, 60, 50]  # by chapter; none in chapter I
const COALITION_FORM_SEC := 12 * 3600
const COALITION_COOLDOWN_SEC := 5 * 86400


func _coalition_threshold() -> int:
	return COALITION_THRESHOLD[mini(chapter, COALITION_THRESHOLD.size() - 1)]


## «Тревога соседей» = threat / threshold: <0.5 calm, 0.5–1 wary (opinion −10, no new alliances), 1 — coalition.
func alarm() -> float:
	var th := _coalition_threshold()
	return 0.0 if th <= 0 else threat / float(th)


## Who would join now: AI states with opinion ≤ 0 bordering the player or an ally, not allied with us (2–4).
func _coalition_candidates() -> Array:
	var out: Array = []
	for s in _ai_states():
		if allies.has(s) or _truce_left(s) > 0 or _pact_left(s) > 0 or _opinion_of(s) > 0.0:
			continue
		var touches := false
		for c in sim.cells:
			if c["owner"] == s and Types.is_passable(c):
				for n in sim.neighbors[c["id"]]:
					if n >= 0 and (sim.cells[n]["owner"] == Types.PLAYER or allies.has(int(sim.cells[n]["owner"]))):
						touches = true
						break
			if touches:
				break
		if touches:
			out.append(s)
	out.sort_custom(func(a, b): return _opinion_of(a) < _opinion_of(b) if _opinion_of(a) != _opinion_of(b) else a < b)
	return out.slice(0, 4)


## The leader: the hegemon if it joined, else the member with the highest official value.
func _coalition_leader(members: Array) -> int:
	var best: int = members[0]
	for m in members:
		if bool(sim.states[m].get("hegemon", false)):
			return m
		if MapGen.official_value(sim, m) > MapGen.official_value(sim, best):
			best = m
	return best


func _coalition_tick(now: int) -> void:
	if threat_at == 0:
		threat_at = now
	if alarm() >= 0.5 and not _alarm_warned:
		_alarm_warned = true
		# «Тревога соседей» 50%: the neighbours start whispering (07 §3.7 — the Grey Pack's leader once it exists)
		var who := RingNext.PACK if sim.states.size() > RingNext.PACK else MapGen.BARONS
		_post("inbox.alarm.title", L.pack("inbox.alarm.text", [String(LEADERS[who][0])]))
		ui.toast(tr("toast.alarm"))
	elif alarm() < 0.4:
		_alarm_warned = false
	var hours := float(now - threat_at) / 3600.0
	if hours >= 1.0:
		threat = maxf(0.0, threat - 0.5 * floorf(hours))
		threat_at += int(floorf(hours)) * 3600
	if not coalition.is_empty():
		# members who warmed up (gifts) or made friends leave; fewer than 2 — the coalition falls apart
		var still: Array = []
		for m in coalition["members"]:
			if not allies.has(int(m)) and _pact_left(int(m)) == 0 and _opinion_of(int(m)) <= 0.0:
				still.append(int(m))
		if still.size() < 2:
			coalition = {}
			_stat("coalitions_broken")  # «Разделяй и властвуй» (07 §7.2)
			_post("inbox.coalition_broken.title", "inbox.coalition_broken.text")
			ui.toast(tr("toast.coalition_broken"))
			return
		coalition["members"] = still
		if now >= int(coalition["at"]) and war.is_empty() and mode == Mode.MAP:
			_coalition_war(now)
		return
	if _coalition_threshold() <= 0 or alarm() < 1.0 or not war.is_empty() or now - coalition_last < COALITION_COOLDOWN_SEC:
		return
	var members := _coalition_candidates()
	if members.size() < 2:
		return
	var leader := _coalition_leader(members)
	coalition = {"leader": leader, "members": members, "at": now + COALITION_FORM_SEC}
	coalition_last = now
	_post("inbox.coalition.title", L.pack("inbox.coalition.text", [_state_key(leader), members.size()]))
	ui.toast(tr("toast.coalition") % [_state_name(leader), members.size()])
	sfx.play("warn")


## The coalition strikes (canon §10.8): one war led by the leader; the others back it — the leader's armies carry
## the members' strength × m_c, m_c = clamp(k × P_player / ΣP, 0.5, 1.5), k = 1.1 / 1.2 / 1.3 for 2 / 3 / 4.
func _coalition_war(now: int) -> void:
	var members: Array = coalition["members"]
	var leader: int = coalition["leader"] if members.has(coalition["leader"]) else _coalition_leader(members)
	coalition = {}
	for m in members:
		_ensure_armies_for(int(m))
	var p_player := 0
	var p_sum := 0
	var p_leader := 0
	for a in armies:
		if a["side"] == Types.PLAYER:
			p_player += int(a["max_str"])
		elif members.has(int(a["side"])):
			p_sum += int(a["max_str"])
			if int(a["side"]) == leader:
				p_leader += int(a["max_str"])
	var k: float = [1.1, 1.1, 1.1, 1.2, 1.3][mini(members.size(), 4)]
	var mc := clampf(k * float(p_player) / maxf(1.0, float(p_sum)), 0.5, 1.5)
	var f := clampf(float(p_sum) * mc / maxf(1.0, float(p_leader)), 1.0, 2.5)
	var p_each: Array = []
	for m in members:
		var pm := 0
		for a in armies:
			if int(a["side"]) == int(m):
				pm += int(a["max_str"])
		p_each.append(pm)
	for a in armies:
		if int(a["side"]) == leader:
			a["max_str"] = roundi(float(a["max_str"]) * f)
			a["str"] = a["max_str"]
	_deploy_to_front(leader)
	var goals := War.recommend_goals(sim, leader, 1)
	if goals.is_empty():
		return
	var target := -1
	var best_v := -1
	var core := MapGen.core_of(sim, Types.PLAYER)
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and not core.has(int(c["id"])) and _touches_owner(c["id"], leader) and int(c["value"]) > best_v:
			best_v = int(c["value"])
			target = c["id"]
	war = War.declare_war(sim, leader, goals[0])
	war["by_ai"] = 1
	war["coalition"] = members
	var v0: Array = []
	for m in members:
		v0.append(MapGen.official_value(sim, int(m)))
	war["coalition_v0"] = v0  # D_M at the war's start: the members' shares of the war score (06 §14.6)
	var d_all := 0
	for v in v0:
		d_all += int(v)
	if not members.has(leader):
		d_all += int(war["enemy_value0"])
	war["coalition_d"] = d_all  # D = Σ official values of all sides at the start, fixed for the whole war
	# what a separate peace needs to take a member's strength back out of the leader's armies
	war["coalition_p"] = p_each
	war["coalition_lead_p"] = p_leader
	war["coalition_mc"] = roundi(mc * 1000.0)
	war["coalition_f"] = roundi(f * 1000.0)
	war["started"] = now
	if target >= 0:
		war["ai_goal"] = target
		war["strike_hex"] = target
		var from := target
		for n in sim.neighbors[target]:
			if n >= 0 and sim.cells[n]["owner"] == leader:
				from = n
				break
		war["strike_from"] = from
		war["strike_at"] = now + STRIKE_WARN_SEC
	for m in members:
		_opinion_add(int(m), -20.0)
	map_view.at_war_with = leader
	map_view.mark_dirty()
	map_view.sync_armies(armies, null)
	sfx.play("warn")
	var names: Array = []
	for m in members:
		names.append(_state_name(int(m)))
	_post("inbox.coalition_war.title", L.pack("inbox.coalition_war.text", [_state_key(leader), members.size()]))
	ui.toast(tr("toast.coalition_war") % ", ".join(names))
	_set_mode(Mode.WAR)


# ---------------------------------------------------------------------- separate peace and subsidies (canon §10.8)

## A member's share of the war score (06 §14.6):
## доля_M = Оккупация_M + Цель_M + Столица_M + Бои × D_M / D − Потери_M; the leader keeps the rest (Σ = ВС).
func _member_share(s: int) -> float:
	if war.is_empty() or not war.has("coalition"):
		return 0.0
	var members: Array = war["coalition"]
	var i := members.find(s)
	if i < 0:
		return 0.0
	if s == int(war["enemy"]):  # the leader's share is the rest (03 §16.4)
		var rest := float(War.war_score(sim, war)["score"])
		for m in members:
			if int(m) != s:
				rest -= _member_share(int(m))
		return Types.round1(rest)
	var v0: Array = war.get("coalition_v0", [])
	var dm := float(v0[i]) if i < v0.size() else float(MapGen.official_value(sim, s))
	var d := float(War.denominator(war))
	var occ := 0
	var lost := 0
	for c in sim.cells:
		if not Types.is_passable(c):
			continue
		if int(c["owner"]) == s and c["controller"] == Types.PLAYER:
			occ += int(c["value"])
		if c["owner"] == Types.PLAYER and int(c["controller"]) == s:
			lost += int(c["value"])
	var ws := War.war_score(sim, war)
	var share := 100.0 * occ / d - 100.0 * lost / maxf(1.0, float(war["player_value0"])) + float(ws["battles"]) * dm / d
	if int(war["goal"]) >= 0 and int(sim.cells[war["goal"]]["owner"]) == s and sim.cells[war["goal"]]["controller"] == Types.PLAYER:
		share += 10.0
	if int(war["ai_goal"]) >= 0 and int(sim.cells[war["ai_goal"]]["controller"]) == s:
		share -= 10.0
	var cap: int = sim.states[s]["capital_id"]
	if cap >= 0 and sim.cells[cap]["controller"] == Types.PLAYER:
		share += 20.0
	return Types.round1(share)


## Any coalition member other than the leader can make a separate peace; its terms follow its share (06 §14.6).
func _can_separate(s: int) -> bool:
	if war.is_empty() or not war.has("coalition") or int(war["enemy"]) == s:
		return false
	return (war["coalition"] as Array).has(s)


## What a member gives for leaving (06 §14.6): its occupied hexes outside its core by value while their price
## fits its share, then 1 h of gold per 5 points left, at most 4 h (the contribution package, 06 §3.5).
func _separate_plan(s: int) -> Dictionary:
	var share := _member_share(s)
	var white_floor := -30.0 if String(sim.states[s]["archetype"]) == "turtle" else -10.0
	if share <= white_floor:
		return _separate_defeat_plan(s, -share)
	var budget := maxf(0.0, share)
	var core := MapGen.core_of(sim, s)
	var occ: Array = []
	for c in sim.cells:
		if int(c["owner"]) == s and c["controller"] == Types.PLAYER and Types.is_passable(c) and not core.has(c["id"]):
			occ.append(c)
	occ.sort_custom(func(a, b): return int(a["value"]) > int(b["value"]) or (int(a["value"]) == int(b["value"]) and int(a["id"]) < int(b["id"])))
	var annex: Array = []
	for c in occ:
		var cost := War.hex_peace_cost(sim, war, int(c["id"]))
		if cost <= budget + 1e-9:
			annex.append(int(c["id"]))
			budget -= cost
	var hours := clampi(int(floor(budget / 5.0)), 0, 4)
	return {"annex": annex, "gold": hours * maxi(60, int(econ.gross_per_hour(sim).get("gold", 0))), "lose": []}


## A separate peace while losing to that member (share ≤ −10, the Turtle ≤ −30): it annexes what it occupies of
## the player's land outside the core, by value, while the price fits |share| — ≤1 city, as in a defeat (canon §9.14).
func _separate_defeat_plan(s: int, budget: float) -> Dictionary:
	var core := MapGen.core_of(sim, Types.PLAYER)
	var cands: Array = []
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and int(c["controller"]) == s and Types.is_passable(c) and not core.has(c["id"]):
			cands.append(c)
	cands.sort_custom(func(a, b): return int(a["value"]) > int(b["value"]) or (int(a["value"]) == int(b["value"]) and int(a["id"]) < int(b["id"])))
	var lose: Array = []
	var cities := 0
	for c in cands:
		var cost := 100.0 * int(c["value"]) / maxf(1.0, float(war["player_value0"]))
		if cost > budget + 1e-9 or (c["kind"] == "city" and cities >= 1):
			continue
		if c["kind"] == "city":
			cities += 1
		lose.append(int(c["id"]))
		budget -= cost
	return {"annex": [], "gold": 0, "lose": lose}


func _separate_gold(s: int) -> int:
	return int(_separate_plan(s)["gold"])


## Separate peace (canon §10.8): the member leaves the war with a 24 h truce and pays its contribution; its share
## of the coalition's strength leaves the leader's armies.
func _separate_peace(s: int) -> void:
	if not _can_separate(s):
		ui.toast(tr("separate.cant"))
		return
	var plan := _separate_plan(s)
	var gold: int = plan["gold"]
	var annex: Array = plan["annex"]
	var lose: Array = plan["lose"]
	for c in sim.cells:
		if not Types.is_passable(c):
			continue
		var id: int = c["id"]
		if lose.has(id):
			c["owner"] = s
			c["controller"] = s
			c["fort"] = 0
		elif annex.has(id):
			c["owner"] = Types.PLAYER
			c["controller"] = Types.PLAYER
			c["fort"] = 0
		elif int(c["owner"]) == s and c["controller"] != s:
			c["controller"] = s  # the rest of its land goes back
		elif c["owner"] == Types.PLAYER and int(c["controller"]) == s:
			c["controller"] = Types.PLAYER
		else:
			continue
		map_view.refresh_hex(id)
	map_view.mark_dirty()
	var members: Array = war["coalition"]
	var i := members.find(s)
	var ps: Array = war.get("coalition_p", [])
	var p_sum := 0
	for v in ps:
		p_sum += int(v)
	var p_out: int = int(ps[i]) if i < ps.size() else 0
	var f_old := float(war.get("coalition_f", 1000)) / 1000.0
	var mc := float(war.get("coalition_mc", 1000)) / 1000.0
	var f_new := clampf(float(p_sum - p_out) * mc / maxf(1.0, float(war.get("coalition_lead_p", 1))), 1.0, 2.5)
	for a in armies:
		if int(a["side"]) == int(war["enemy"]):
			a["max_str"] = roundi(float(a["max_str"]) * f_new / f_old)
			a["str"] = mini(int(a["str"]), int(a["max_str"]))
	members.remove_at(i)
	if i < ps.size():
		ps.remove_at(i)
	var v0: Array = war.get("coalition_v0", [])
	if i < v0.size():
		v0.remove_at(i)  # the war's D stays as it was (06 §14.6): only the member's own D_M leaves
	war["coalition_f"] = roundi(f_new * 1000.0)
	truce[s] = now_s() + TRUCE_SEC
	_opinion_add(s, 10.0)
	if gold > 0:
		econ.add_resources({"gold": gold})
	sfx.play("seal")
	_post(L.pack("inbox.separate.title", [_state_key(s)]), L.pack("inbox.separate.text", [_state_key(s), _state_key(int(war["enemy"]))]))
	if lose.is_empty() and (not annex.is_empty() or gold > 0):
		_coalition_win()
	if not lose.is_empty():
		war["sep_defeat"] = 1  # a lost separate peace: no «Триумф» for this war (06 §14.6)
		ui.toast(tr("toast.separate_lost") % [_state_name(s), lose.size()])
	elif not annex.is_empty():
		ui.toast(tr("toast.separate_land") % [_state_name(s), annex.size(), gold])
	else:
		ui.toast(tr("toast.separate") % _state_name(s) if gold == 0 else tr("toast.separate_gold") % [_state_name(s), gold])
	if int(war.get("front", -1)) == s:
		war.erase("front")
	# the player's goal stood on its land: the first recommended goal on the leader's (06 §14.6)
	if int(war["goal"]) >= 0 and int(sim.cells[war["goal"]]["owner"]) != int(war["enemy"]):
		var goals := War.recommend_goals(sim, int(war["enemy"]), 1)
		war["goal"] = goals[0] if goals.size() > 0 else -1
	if int(war["ai_goal"]) >= 0 and int(sim.cells[war["ai_goal"]]["owner"]) != Types.PLAYER:
		war["ai_goal"] = -1
	if int(war.get("strike_by", -1)) == s:
		for k in ["strike_at", "strike_hex", "strike_from", "strike_by"]:
			war.erase(k)
		map_view.strike_arrow(-1, -1, "")
	_normalize_armies()
	map_view.sync_armies(armies, null)
	_refresh_ui()
	_autosave()


## A victorious treaty in a coalition war; the second one counts «Война на два фронта» (07 §3.8).
func _coalition_win() -> void:
	if war.is_empty() or not war.has("coalition"):
		return
	war["wins"] = int(war.get("wins", 0)) + 1
	if int(war["wins"]) == 2:
		_stat("two_fronts")


## Members propose a separate peace themselves (06 §9.1, S8) once their share reaches the archetype's threshold;
## the leader never does. One proposal per member and 6 h; it waits while a battle or another window is open.
const SEPARATE_AT := {"wolf": 30.0, "fox": 15.0, "turtle": 20.0, "raven": 10.0, "owl": 25.0}
const SEPARATE_ASK_SEC := 6 * 3600


func _separate_offer_tick(now: int) -> void:
	if war.is_empty() or not war.has("coalition") or mode != Mode.WAR or ui.has_modal() or shop != null:
		return
	for m in (war["coalition"] as Array):
		var s := int(m)
		var key := "sep_ask_%d" % s
		if now < int(war.get(key, 0)) or not _can_separate(s):
			continue
		var need: float = SEPARATE_AT.get(String(sim.states[s]["archetype"]), 30.0)
		var share := _member_share(s)
		if share < need:
			continue
		war[key] = now + SEPARATE_ASK_SEC
		_post(L.pack("inbox.separate_offer.title", [_state_key(s)]), L.pack("inbox.separate_offer.text", [_state_key(s)]))
		_show_separate_offer(s)
		return


## The separate peace window: `asked` — the member proposes it; else the player opens it from Diplomacy.
func _show_separate_offer(s: int, asked := true) -> void:
	var plan := _separate_plan(s)
	var gold: int = plan["gold"]
	var n: int = (plan["annex"] as Array).size()
	var terms: String = tr("separate.terms_white")
	if n > 0:
		terms = tr("separate.terms_land") % [n, gold]
	elif gold > 0:
		terms = tr("separate.terms") % gold
	elif not (plan["lose"] as Array).is_empty():
		terms = tr("separate.terms_lose") % (plan["lose"] as Array).size()
	ui.show_choice(tr("separate.offer_title" if asked else "separate.ask_title") % _state_name(s), [
		tr("separate.offer_line") % [_state_name(s), _state_name(int(war["enemy"]))],
		tr("separate.share" if asked else "separate.share_own") % [_member_share(s), _state_name(s)],
		terms,
	], [
		[tr("separate.accept" if asked else "separate.sign"), Color(0.16, 0.55, 0.3), func():
			ui.close_modal()
			_separate_peace(s)],
		[tr("separate.decline" if asked else "ui.cancel"), Color(0.3, 0.33, 0.4), func(): ui.close_modal()],
	])


## Subsidies (canon §10.8): with the alarm at 50%+, a neighbour with opinion ≤ −25 may fund the state at war with
## the player — its armies +10% for 12 h, at most once a day per war; daily chance by archetype (06 §9).
const SUBSIDY_CHANCE := {"wolf": 0, "fox": 20, "turtle": 10, "raven": 10, "owl": 30}
const SUBSIDY_SEC := 12 * 3600


func _subsidy_tick(now: int) -> void:
	if war.is_empty():
		return
	var enemy: int = war["enemy"]
	if war.has("subsidy_until") and now >= int(war["subsidy_until"]):
		for a in armies:
			if int(a["side"]) == enemy:
				a["max_str"] = int(a["max_str"]) * 10 / 11
				a["str"] = mini(int(a["str"]), int(a["max_str"]))
		war.erase("subsidy_until")
		war.erase("subsidy_by")
		map_view.sync_armies(armies, null)
	if war.has("subsidy_until") or alarm() < 0.5 or now - int(war.get("subsidy_day", 0)) < 86400:
		return
	war["subsidy_day"] = now
	for s in _ai_states():
		if s == enemy or (war.get("coalition", []) as Array).has(s) or allies.has(s) or _opinion_of(s) > -25.0:
			continue
		var chance: int = SUBSIDY_CHANCE.get(String(sim.states[s]["archetype"]), 10)
		if _roll("subsidy:%d:%d" % [s, now / 86400], 100) >= chance:
			continue
		for a in armies:
			if int(a["side"]) == enemy:
				a["max_str"] = int(a["max_str"]) * 11 / 10
				a["str"] = int(a["str"]) * 11 / 10
		war["subsidy_until"] = now + SUBSIDY_SEC
		war["subsidy_by"] = s
		map_view.sync_armies(armies, null)
		_post("inbox.subsidy.title", L.pack("inbox.subsidy.text", [_state_key(s), _state_key(enemy)]))
		ui.toast(tr("toast.subsidy") % [_state_name(s), _state_name(enemy)])
		return


# ---------------------------------------------------------------------- non-aggression pact (canon §10.8, 06 §11)

const PACT_SEC := 48 * 3600
const PACT_REPEAT_SEC := 72 * 3600
## The lowest opinion each archetype signs a pact at (06 §9 table).
const PACT_OPINION := {"wolf": 0.0, "fox": -25.0, "turtle": -50.0, "raven": -25.0, "owl": -25.0}


func _pact_left(s: int) -> int:
	return maxi(0, int(pacts.get(s, 0)) - now_s())


func _pact_cost() -> int:
	return 8 * maxi(60, int(econ.gross_per_hour(sim).get("gold", 0)))  # 8 h of gross gold (canon)


## "" when a pact can be signed with `s`: no war or open ultimatum with it, its archetype's opinion threshold,
## one active pact at a time, the same state again 72 h after the last pact ended.
func _pact_reason(s: int) -> String:
	if _pact_left(s) > 0:
		return tr("dipl.pact") % GameUI.fmt_time(_pact_left(s))
	if not war.is_empty() and (int(war["enemy"]) == s or (war.get("coalition", []) as Array).has(s)):
		return tr("swap.war")
	if not ultimatum.is_empty() and int(ultimatum["state"]) == s:
		return tr("pact.ultimatum")
	for o in pacts:
		if _pact_left(int(o)) > 0:
			return tr("pact.one")
	var again := int(pacts.get(s, 0)) + PACT_REPEAT_SEC - now_s()
	if pacts.has(s) and again > 0:
		return tr("pact.again") % GameUI.fmt_time(again)
	var need: float = PACT_OPINION.get(String(sim.states[s]["archetype"]), -25.0)
	if _opinion_of(s) < need:
		return tr("pact.opinion") % [roundi(_opinion_of(s)), roundi(need)]
	return ""


# ---------------------------------------------------------------------- territory swap (canon §10.9, 06 §15)

const SWAP_COOLDOWN_SEC := 86400
const SWAP_MAX := 5  # hexes a side (06 §15.1)
## How often an archetype proposes a swap itself (06 §9.1): the Fox every 48 h, the Turtle and the Owl every 7 days.
const SWAP_OFFER_SEC := {"fox": 48 * 3600, "turtle": 7 * 86400, "owl": 7 * 86400}


## "" when a swap with `s` can be set up, else why not (06 §15.1: chapter II+, no war, opinion ≥ 0, 1 per 24 h).
func _swap_reason(s: int) -> String:
	if chapter < 2:
		return tr("swap.chapter")
	if not war.is_empty() and (int(war["enemy"]) == s or (war.get("coalition", []) as Array).has(s)):
		return tr("swap.war")
	if _opinion_of(s) < 0.0:
		return tr("swap.opinion") % roundi(_opinion_of(s))
	var left := int(swap_at.get(s, 0)) + SWAP_COOLDOWN_SEC - now_s()
	if left > 0:
		return tr("swap.cooldown") % GameUI.fmt_time(left)
	return ""


## A hex can change hands in a swap: official land of `side`, not in anyone's core, no colonization on it.
func _swappable(id: int, side: int) -> bool:
	var c: Dictionary = sim.cells[id]
	if c["owner"] != side or c["controller"] != side or not Types.is_passable(c) or c["kind"] == "capital":
		return false
	if MapGen.core_of(sim, side).has(id) or colonizing.has(id):
		return false
	return true


## The AI's valuation (06 §15.2): ×2 within 2 of its capital, ×0.5 for its exclave (giving) or a hex that would
## be cut off from its land (receiving; a hex next to another one of the same package counts as joined).
func _swap_value(s: int, id: int, receiving: bool, package: Array = []) -> float:
	var c: Dictionary = sim.cells[id]
	var cap: int = sim.states[s]["capital_id"]
	var v := float(c["value"])
	if cap >= 0 and HexGrid.distance(HexGrid.axial(c), HexGrid.axial(sim.cells[cap])) <= 2:
		return v * 2.0
	if receiving:
		if _touches_owner(id, s):
			return v
		for n in sim.neighbors[id]:
			if n >= 0 and package.has(n) and _touches_owner(n, s):
				return v
		return v * 0.5
	# giving: an exclave (no path over its own land to its capital) is worth half
	var seen := {id: true}
	var stack: Array = [id]
	while not stack.is_empty():
		var h: int = stack.pop_back()
		if h == cap:
			return v
		for n in sim.neighbors[h]:
			if n >= 0 and not seen.has(n) and sim.cells[n]["owner"] == s:
				seen[n] = true
				stack.append(n)
	return v * 0.5


## Edges between the player's land and `s`'s, with `over` (hex -> new owner) applied — the swap panel's
## «Граница: 21 → 15 рёбер» (06 §15.1).
func _border_len(s: int, over: Dictionary = {}) -> int:
	var n := 0
	for c in sim.cells:
		var id: int = c["id"]
		if int(over.get(id, c["owner"])) != Types.PLAYER:
			continue
		for nb in sim.neighbors[id]:
			if nb >= 0 and int(over.get(nb, sim.cells[nb]["owner"])) == s:
				n += 1
	return n


func _swap_over(s: int, give: Array, get_l: Array) -> Dictionary:
	var over := {}
	for h in give:
		over[h] = s
	for h in get_l:
		over[h] = Types.PLAYER
	return over


## The AI's verdict on a package (06 §15.2): its valuation both ways, the top-up in value units and gold, and the
## overpay it returns as opinion.
func _swap_terms(s: int, give: Array, get_l: Array) -> Dictionary:
	var v_out := 0.0   # what the AI gives up
	var v_in := 0.0    # what the AI receives
	for h in get_l:
		v_out += _swap_value(s, h, false)
	for h in give:
		v_in += _swap_value(s, h, true, give)
	var k := 0.8 if allies.has(s) else 0.9      # «≤10% not in its favour», an ally 20%
	var pay_units := maxf(0.0, ceilf((k * v_out - v_in) * 10.0) / 10.0)
	var gold := int(ceil(pay_units * 2.0 * maxf(60.0, float(econ.gross_per_hour(sim).get("gold", 0)))))
	return {"v_in": v_in, "v_out": v_out, "pay": pay_units, "gold": gold, "overpay": v_in + pay_units - k * v_out}


func _hex_list(ids: Array) -> String:
	var names := PackedStringArray()
	var v := 0
	for h in ids:
		names.append(_cell_name(h))
		v += int(sim.cells[h]["value"])
	return "%s (%s %d)" % [", ".join(names), tr("swap.value"), v]


## A tap in swap mode toggles the hex in the package: ours → «give», theirs → «get», up to 5 a side (06 §15.1).
func _swap_pick(id: int) -> void:
	var s: int = _swap["state"]
	var give: Array = _swap["give"]
	var get_l: Array = _swap["get"]
	if give.has(id) or get_l.has(id):
		give.erase(id)
		get_l.erase(id)
		map_view.hex_label(id, "")
		sfx.play("tap")
		return
	if _swappable(id, Types.PLAYER):
		if give.size() >= SWAP_MAX:
			ui.toast(tr("swap.max") % SWAP_MAX)
			return
		give.append(id)
		map_view.burst(id, MapView.C_PLAYER)
		map_view.hex_label(id, "⇄ " + tr("swap.tag_give"))
	elif _swappable(id, s):
		if get_l.size() >= SWAP_MAX:
			ui.toast(tr("swap.max") % SWAP_MAX)
			return
		get_l.append(id)
		map_view.burst(id, map_view.state_color(s))
		map_view.hex_label(id, "⇄ " + tr("swap.tag_get"))
	else:
		ui.toast(tr("swap.bad_hex"))
		return
	sfx.play("tap")
	if give.is_empty():
		ui.toast(tr("swap.pick_give"))
		return
	if get_l.is_empty():
		ui.toast(tr("swap.pick_get") % _state_name(s))
		return
	_swap_offer()


func _swap_lines(s: int, give: Array, get_l: Array, t: Dictionary) -> Array:
	return [
		tr("swap.give") % _hex_list(give),
		tr("swap.get") % _hex_list(get_l),
		tr("swap.border") % [_state_name(s), _border_len(s), _border_len(s, _swap_over(s, give, get_l))],
		tr("swap.ai_view") % [_state_name(s), float(t["v_in"]), float(t["v_out"])],
		tr("swap.pay") % int(t["gold"]) if int(t["gold"]) > 0 else tr("swap.fair"),
	]


func _swap_clear_labels() -> void:
	if _swap.is_empty():
		return
	for h in (_swap["give"] as Array) + (_swap["get"] as Array):
		map_view.hex_label(h, "")


func _swap_offer() -> void:
	var s: int = _swap["state"]
	var give: Array = _swap["give"]
	var get_l: Array = _swap["get"]
	var t := _swap_terms(s, give, get_l)
	var buttons: Array = [[tr("swap.offer"), Color(0.16, 0.42, 0.95), func():
		ui.close_modal()
		_swap_clear_labels()
		_swap = {}
		_swap_execute(s, give, get_l, int(t["gold"]), float(t["overpay"]))]]
	if give.size() < SWAP_MAX or get_l.size() < SWAP_MAX:
		buttons.append([tr("swap.more"), Color(0.2, 0.45, 0.35), func():
			ui.close_modal()
			ui.toast(tr("swap.more_hint"))])
	buttons.append([tr("ui.cancel"), Color(0.3, 0.33, 0.4), func():
		ui.close_modal()
		_swap_clear_labels()
		_swap = {}])
	ui.show_choice(tr("swap.title"), _swap_lines(s, give, get_l, t), buttons)


func _swap_execute(s: int, give: Array, get_l: Array, gold: int, overpay: float) -> bool:
	for h in give:
		if not _swappable(h, Types.PLAYER):
			return false
	for h in get_l:
		if not _swappable(h, s):
			return false
	if econ.res["gold"] < gold:
		ui.toast(tr("toast.no_gold"))
		return false
	econ.res["gold"] -= gold
	for h in give:
		sim.cells[h]["owner"] = s
		sim.cells[h]["controller"] = s
		sim.cells[h]["fort"] = 0  # forts are taken down, the hex goes empty (06 §15.1)
	for h in get_l:
		sim.cells[h]["owner"] = Types.PLAYER
		sim.cells[h]["controller"] = Types.PLAYER
		sim.cells[h]["fort"] = 0
	swap_at[s] = now_s()
	_opinion_add(s, minf(10.0, 5.0 + 2.0 * floorf(maxf(0.0, overpay))))  # op_swap: +5, +2 per unit of overpay
	_stat("swaps")
	_econ_tick()
	_normalize_armies()
	for h in give + get_l:
		map_view.hex_label(h, "")
		map_view.refresh_hex(h)
	map_view.mark_dirty()
	map_view.sync_armies(armies, null)
	for h in get_l:
		map_view.burst(h, MapView.C_PLAYER, true)
	sfx.play("seal")
	_post("inbox.swap.title", L.pack("inbox.swap.text", [_state_key(s), _cell_key(give[0]), _cell_key(get_l[0]), give.size(), get_l.size()]))
	ui.toast(tr("toast.swap") % [get_l.size(), _state_name(s)])
	_refresh_ui()
	_autosave()
	return true


## Swap offers from the AI (06 §9.1 S4): the Fox every 48 h, the Turtle and the Owl every 7 days — the best package
## of ≤2 hexes a side that shortens the player's border with it by ≥2 edges and leaves the AI's valuation
## (06 §15.2) not in deficit — with a top-up of at most 1 value unit (2 h of gold) where needed, the traders' way. The offer waits 24 h; the screen opens once the player is free.
func _ai_swap_tick(now: int) -> void:
	if not swap_offer.is_empty():
		if now > int(swap_offer["until"]):
			swap_offer = {}
		elif bool(swap_offer.get("auto", false)) and mode == Mode.MAP and not ui.has_modal() and shop == null and _swap.is_empty():
			swap_offer["auto"] = false
			_show_swap_offer()
		return
	if chapter < 2:
		return
	for s in _ai_states():
		var period: int = SWAP_OFFER_SEC.get(String(sim.states[s]["archetype"]), 0)
		if period == 0:
			continue
		if not swap_offer_at.has(s):
			swap_offer_at[s] = now + period / 2  # the first offer comes a while after meeting
			continue
		if now < int(swap_offer_at[s]):
			continue
		swap_offer_at[s] = now + period
		if _swap_reason(s) != "":
			continue
		var best := _ai_swap_package(s)
		if best.is_empty():
			continue
		swap_offer = {"state": s, "give": best["give"], "get": best["get"], "until": now + 86400, "auto": save_enabled}
		_post(L.pack("inbox.swap_offer.title", [_state_key(s)]), L.pack("inbox.swap_offer.text", [_state_key(s)]))
		return


## The package the AI proposes, or {}: `give` is what the player gives.
func _ai_swap_package(s: int) -> Dictionary:
	var mine: Array = []
	var theirs: Array = []
	for c in sim.cells:
		var id: int = c["id"]
		if _swappable(id, Types.PLAYER) and _touches_owner(id, s):
			mine.append(id)
		elif _swappable(id, s) and _touches_owner(id, Types.PLAYER):
			theirs.append(id)
	var base := _border_len(s)
	var best := {}
	var best_score := -INF
	var packs: Array = []
	for a in mine:
		for b in theirs:
			packs.append([[a], [b]])
	# two a side: pairs of neighbouring hexes on each side
	for i in mine.size():
		for j in range(i + 1, mine.size()):
			if not (sim.neighbors[mine[i]] as Array).has(mine[j]):
				continue
			for k in theirs.size():
				for l in range(k + 1, theirs.size()):
					if (sim.neighbors[theirs[k]] as Array).has(theirs[l]):
						packs.append([[mine[i], mine[j]], [theirs[k], theirs[l]]])
	for p in packs:
		var t := _swap_terms(s, p[0], p[1])
		if float(t["pay"]) > 1.0:
			continue
		var cut := base - _border_len(s, _swap_over(s, p[0], p[1]))
		var gain := 0
		for h in p[1]:
			gain += int(sim.cells[h]["value"])
		for h in p[0]:
			gain -= int(sim.cells[h]["value"])
		var score := float(cut) + 0.25 * gain - float(t["pay"])
		if cut >= 2 and score > best_score:
			best_score = score
			best = {"give": p[0], "get": p[1]}
	return best


func _show_swap_offer() -> void:
	if swap_offer.is_empty():
		return
	var s: int = swap_offer["state"]
	var give: Array = swap_offer["give"]
	var get_l: Array = swap_offer["get"]
	if _swap_reason(s) != "":
		swap_offer = {}
		return
	var t := _swap_terms(s, give, get_l)
	var lines: Array = [tr("swap.ai_offer_line")]
	var sl := _swap_lines(s, give, get_l, t)
	lines.append_array(sl.slice(0, 3))
	lines.append(sl[4])
	rig.focus(map_view.cell_world(get_l[0]), 0.5)
	ui.show_choice(tr("swap.ai_offer_title") % _state_name(s), lines, [
		[tr("swap.accept"), Color(0.16, 0.55, 0.3), func():
			ui.close_modal()
			swap_offer = {}
			_swap_execute(s, give, get_l, int(t["gold"]), float(t["overpay"]))],
		[tr("swap.decline"), Color(0.3, 0.33, 0.4), func():
			ui.close_modal()
			swap_offer = {}
			_autosave()],
	])


func _ally_reason(s: int) -> String:
	if allies.has(s):
		return tr("dipl.ally")
	var dl: int = econ.dev_level()
	var limit := 3 if dl >= 7 else (2 if dl >= 5 else (1 if dl >= 3 else 0))
	if limit == 0:
		return tr("ally.need_dl")
	if allies.size() >= limit:
		return tr("ally.limit") % limit
	if not war.is_empty() and int(war["enemy"]) == s or _truce_left(s) > 0:
		return tr("ally.not_now")
	if alarm() >= 0.5:
		return tr("ally.alarm")  # no new alliances while the neighbours are alarmed (canon §10.8)
	var need := 40.0 if String(sim.states[s]["archetype"]) == "owl" else 50.0
	if _opinion_of(s) < need:
		return tr("ally.opinion") % roundi(need)
	return ""


## Deterministic roll 0..n−1 for a key. Godot's String hash barely mixes neighbouring keys (consecutive days
## gave consecutive values), so the key seeds xoshiro, whose splitmix seeding spreads it properly.
static func _roll(key: String, n: int) -> int:
	return Rng.new(hash(key)).next_int(n)


## «Призыв» (canon §10.7): an ally with opinion ≥60 can be called into the player's offensive war (−5 opinion).
func _can_call(s: int) -> bool:
	return allies.has(s) and not war.is_empty() and not war.has("by_ai") and not war.has("called_%d" % s) \
		and int(war["enemy"]) != s and _opinion_of(s) >= 60.0


## AI–AI alliances, minimal model (canon §10.7): each AI state has at most one AI ally; once a day two AI
## neighbours that are not at war and not allied with the player may sign (Owl and Fox like it more).
func _ai_alliances_tick(now: int) -> void:
	if now < ai_alliance_check or int(stats.get("peaces", 0)) < 1:
		return
	ai_alliance_check = now + 86400
	for a in _ai_states():
		for b in _ai_states():
			if a >= b or ai_alliances.has(a) or ai_alliances.has(b) or allies.has(a) or allies.has(b) or not _states_touch(a, b):
				continue
			if ai_war_of(a) == b:
				continue
			var chance := 8
			for s in [a, b]:
				if String(sim.states[s]["archetype"]) in ["owl", "fox"]:
					chance += 6
			if _roll("aia:%d:%d:%d" % [a, b, now / 86400], 100) < chance:
				ai_alliances[a] = b
				ai_alliances[b] = a
				_post("inbox.ai_alliance.title", L.pack("inbox.ai_alliance.text", [_state_key(a), _state_key(b)]))
				return


## Allies at war on the player's side take 1–2 enemy border hexes outside its core every 2 h; they keep them
## at peace (canon §10.7). Defensive wars always, offensive ones when their opinion is ≥60.
func _allies_tick(now: int) -> void:
	if war.is_empty():
		return
	var enemy: int = war["enemy"]
	for s in allies:
		if s == enemy or not _states_touch(s, enemy):
			continue
		if not war.has("by_ai") and not war.has("called_%d" % s):
			continue  # offensive wars only on a «Призыв» (canon §10.7)
		var key := "ally_%d" % s
		if not war.has(key):
			war[key] = now + 2 * 3600
			_post(L.pack("inbox.ally_joins.title", [_state_key(s)]), L.pack("inbox.ally_joins.text", [_state_key(s), _state_key(enemy)]))
			continue
		if now < int(war[key]):
			continue
		war[key] = now + 2 * 3600
		var core := MapGen.core_of(sim, enemy)
		var front: Array = []
		for c in sim.cells:
			if c["controller"] == enemy and Types.is_passable(c) and not core.has(c["id"]) and _touches_controller(c["id"], s):
				front.append(c)
		front.sort_custom(func(x, y): return int(x["id"]) < int(y["id"]))
		var n := 1 + _roll("ally:%d:%d" % [s, now / 7200], 2)
		for c in front.slice(0, n):
			c["controller"] = s
			map_view.refresh_hex(int(c["id"]))
		map_view.mark_dirty()


## AI state fighting another AI state right now, or -1 (garrisons on the other borders −30%, canon §10.10).
func ai_war_of(s: int) -> int:
	for w in ai_wars:
		if int(w["a"]) == s:
			return int(w["b"])
		if int(w["b"]) == s:
			return int(w["a"])
	return -1


const AI_COLONIZE_SEC := 3 * 3600


## AI state settling `hex` right now, or -1.
func _ai_claimed(hex: int) -> int:
	for s in ai_colonizing:
		if int(ai_colonizing[s]["hex"]) == hex:
			return int(s)
	return -1


## AI colonization (02 §10.2): one wild hex next to its official land at a time, 3 h each; the target scores
## value × 2 + 1 next to a deposit − 2 next to the player; ties by hex id. Starts after the first peace.
func _ai_colonize(now: int) -> void:
	if ftue != 0 or int(stats.get("peaces", 0)) < 1:
		return
	for s in _ai_states():
		var cur: Dictionary = ai_colonizing.get(s, {})
		if not cur.is_empty():
			var h: int = cur["hex"]
			var c: Dictionary = sim.cells[h]
			if c["owner"] != Types.NOBODY or c["controller"] != Types.NOBODY:
				ai_colonizing.erase(s)
				map_view.hex_label(h, "")
				continue
			if now >= int(cur["at"]):
				c["owner"] = s
				c["controller"] = s
				ai_colonizing.erase(s)
				map_view.hex_label(h, "")
				map_view.refresh_hex(h)
				map_view.mark_dirty()
				map_view.burst(h, map_view.state_color(s), false)
			else:
				map_view.hex_label(h, "⛳ " + GameUI.fmt_time(int(cur["at"]) - now), map_view.state_color(s).lightened(0.35))
			continue
		var best := -1
		var best_s := -1000
		for c in sim.cells:
			var id: int = c["id"]
			if c["owner"] != Types.NOBODY or c["controller"] != Types.NOBODY or not Types.is_passable(c):
				continue
			if colonizing.has(id) or _ai_claimed(id) >= 0 or not camps.at(id).is_empty() or not _touches_owner(id, s):
				continue
			var sc: int = int(c["value"]) * 2
			for n in sim.neighbors[id]:
				if n >= 0 and not deposits.at(n).is_empty():
					sc += 1
					break
			if _touches_owner(id, Types.PLAYER):
				sc -= 2
			if sc > best_s:
				best_s = sc
				best = id
		if best >= 0:
			ai_colonizing[s] = {"hex": best, "at": now + AI_COLONIZE_SEC}


## The chapter a state was born in: Barons and Hamlets — I, League and Order — II, Alvaria, Saren, the Pack — III.
func _native_chapter(s: int) -> int:
	if s <= MapGen.HAMLETS:
		return 1
	if s <= RingGen.ORDER:
		return 2
	return 3 if s <= RingNext.PACK else 4


## DL cap of an AI state: its own chapter's cap, or the open chapter's cap minus the chapters between (§9.16).
func _ai_dl_cap(s: int) -> int:
	var nat := _native_chapter(s)
	return maxi(AI_DL_CAP[nat], AI_DL_CAP[mini(chapter, AI_DL_CAP.size() - 1)] - (chapter - nat))


## AI states grow by one DL every 6 days up to their cap; their armies and looks follow.
func _ai_growth(now: int) -> void:
	var grew := false
	for s in _ai_states():
		if not ai_dl_at.has(s):
			ai_dl_at[s] = now
			continue
		var dl: int = sim.states[s]["dev_level"]
		if dl >= _ai_dl_cap(s) or now - int(ai_dl_at[s]) < AI_DL_STEP_SEC:
			continue
		sim.states[s]["dev_level"] = dl + 1
		ai_dl_at[s] = now
		var k := Types.strength_mult(dl + 1) / maxf(0.01, Types.strength_mult(dl))
		for a in armies:
			if a["side"] == s:
				a["max_str"] = roundi(float(a["max_str"]) * k)
				a["str"] = roundi(float(a["str"]) * k)
		_post("inbox.ai_dl.title", L.pack("inbox.ai_dl.text", [sim.states[s]["name"], dl + 1]))
		grew = true
	if grew:
		map_view.refresh_props()


## Camera limits around the open world (chapter I: the original −6.5…6.5 × −7.5…4.5 box).
func _fit_camera_bounds() -> void:
	var lo := Vector2(-6.5, -7.5)
	var hi := Vector2(6.5, 4.5)
	if int(sim.radius) <= 4:
		rig.bounds = Rect2(lo, hi - lo)
		return
	for c in sim.cells:
		var p: Vector3 = MapView.axial_to_world(int(c["q"]), int(c["r"]))
		lo = lo.min(Vector2(p.x - 1.0, p.z - 3.0))
		hi = hi.max(Vector2(p.x + 1.0, p.z - 1.0))
	rig.bounds = Rect2(lo, hi - lo)


## The next chapter's ring (canon §12.1): the world grows around the old one; the map, camera and minimap follow.
func _expand_world() -> void:
	var ok := false
	match chapter:
		1:
			ok = RingGen.extend_chapter_two(sim, int(sim.map_seed) ^ 0x2)
		2:
			ok = RingNext.extend_chapter_three(sim, int(sim.map_seed) ^ 0x3)
		3:
			ok = RingNext.extend_chapter_four(sim, int(sim.map_seed) ^ 0x4)
	if not ok:
		return
	map_view.set_world(sim)
	map_view.set_camps(camps.active)
	_fit_camera_bounds()
	_minimap_snap = ""


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
	if not _swap.is_empty() and id >= 0:
		_swap_pick(id)
		return
	if id >= 0 and map_view.has_bubble(id):
		_collect_all()
		return
	_select(id)


func _select(id: int) -> void:
	selected = id
	if id >= 0 and mode == Mode.WAR and war.has("coalition"):
		var own: int = sim.cells[id]["owner"]
		if War.sides(war).has(own) and own != _front():
			war["front"] = own  # the next offensive goes against this member (06 §14.6)
			ui.toast(tr("toast.front") % _state_name(own))
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
		if c["kind"] == "raivite_vein":
			bonus = tr("tile.vein") % econ.vein_amount(id)
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
	if s == Types.PLAYER and realm_name != "":
		return realm_name
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
	return COLONIZE_SEC[clampi(chapter, 1, COLONIZE_SEC.size() - 1)]


func _chapter_goal() -> int:
	return CHAPTER_GOALS[clampi(chapter, 1, CHAPTER_GOALS.size() - 1)]


## Every AI state of the open world (chapter I: Barons, Hamlets; chapter II adds the League and the Order).
func _ai_states() -> Array:
	var out: Array = []
	for s in range(2, sim.states.size()):
		out.append(s)
	return out


## Colonization (canon §12.1): gold and a timer, one at a time, no builder needed.
func _colonize(id: int) -> void:
	if _ai_claimed(id) >= 0:
		ui.toast(tr("toast.ai_claimed") % _state_name(_ai_claimed(id)))
		return
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
	bp.gain("colonize", now_s())
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
	ui.toast(tr("toast.colonized") % [_cell_name(id), _player_hexes(), _chapter_goal()])
	_select(id)


func _declare(enemy: int, goal: int) -> void:
	if allies.has(enemy):
		allies.erase(enemy)  # war on an ally ends the alliance
		sim.player_allies.erase(enemy)
		_opinion_add(enemy, -30.0)
		threat += 5.0  # treachery (canon §10.8)
		_post(L.pack("inbox.alliance_broken.title", [_state_key(enemy)]), L.pack("inbox.alliance_broken.text", [_state_key(enemy)]))
	_ensure_armies_for(enemy)
	_deploy_to_front(enemy)
	war = War.declare_war(sim, enemy, goal)
	war["started"] = now_s()
	if ai_alliances.has(enemy):
		# the enemy's AI ally stays out but backs it: +10% army strength for the war, and it dislikes us (§10.7)
		var backer: int = ai_alliances[enemy]
		war["backer"] = backer
		for a in armies:
			if a["side"] == enemy:
				a["max_str"] = int(a["max_str"]) * 11 / 10
				a["str"] = int(a["str"]) * 11 / 10
		_opinion_add(backer, -15.0)
		ui.toast(tr("toast.enemy_backed") % [_state_name(enemy), _state_name(backer)])
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
	# as many armies as a player of that DL (2), Wolf +1, Turtle −1 (canon §9.16)
	var n: int = 2 + int({"wolf": 1, "turtle": -1}.get(String(sim.states[state]["archetype"]), 0))
	var spots: Array = front.duplicate()
	if spots.is_empty():
		spots.append(cap)
	for c in sim.cells:
		if spots.size() >= n:
			break
		if c["owner"] == state and Types.is_passable(c) and not spots.has(c["id"]):
			spots.append(c["id"])
	for i in mini(n, spots.size()):
		var a: Dictionary = Armies.infantry_army(id + i, state, int(spots[i]), 3, dl)
		if bool(sim.states[state].get("hegemon", false)):
			a["max_str"] = int(a["max_str"]) * 6 / 5  # the chapter boss: armies +20% (canon §10.4)
			a["str"] = a["max_str"]
		armies.append(a)


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

## The state the next offensive goes against: in a coalition war the member the player picked on the map
## (a tap on its hex), else the enemy.
func _front() -> int:
	if war.is_empty():
		return -1
	var f := int(war.get("front", war["enemy"]))
	return f if War.sides(war).has(f) else int(war["enemy"])


func _start_offensive() -> void:
	var enemy: int = _front()
	_ensure_armies_for(enemy)
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
	# the hegemon's energy ×1.1 (07 §3.7)
	var opts := {"attacker": Types.PLAYER, "defender": enemy, "ai_energy_mult": 660 if bool(sim.states[enemy].get("hegemon", false)) else 600, "cards": _hand()}
	if ftue > 0:
		# tutorial offensives are short and the enemy plays no cards (canon §14.3)
		opts["ai_energy_mult"] = 0
		opts["ticks"] = 60 * Battle.TICKS_PER_SEC
		ftue = 12 if ftue >= 10 else 3
	opts.merge(_apply_commanders())
	ui.cost_discount = {"landing": int(opts.get("landing_discount", 0))}
	battle = Battle.new(sim, armies, opts)
	ai = BattleAI.new(enemy)
	ai.airstrike = ftue == 0 and _state_dl(enemy) >= AIRSTRIKE_DL and String(sim.states[enemy]["archetype"]) in AIR_ARCHETYPES
	_show_hand()
	var other := ai_war_of(enemy)
	if other >= 0:
		# window of opportunity (canon §10.10): fighting another AI, its other borders hold 30% weaker garrisons
		for c in sim.cells:
			if c["controller"] == enemy and not _touches_controller(c["id"], other):
				battle.garrison[c["id"]] = int(battle.garrison[c["id"]]) * 7 / 10
	_acc = 0.0
	_ev_i = 0
	_select(-1)
	rig.focus(_front_center(), 0.5)
	_set_mode(Mode.BATTLE)
	sfx.play("warn")
	if ftue == 0:
		ui.toast(tr("toast.to_battle"))


## The war cards in hand: the base five, plus «Союзный корпус» while an ally fights in this war (canon §9.9).
## Every slot card (03 §5.2) and how many slots the hand has: 4, from DL6 5 (canon §9.9).
const SLOT_CARDS := ["breakthrough", "airstrike", "encircle", "defense", "landing", "missile"]


func _hand_slots() -> int:
	return 5 if econ.dev_level() >= 6 else 4


## The player's own hand (03 §5.2) once they pick it: «Атака» + the chosen open cards in slot order; until then
## the default below.
func _hand_display() -> Array:
	if not hand_pick.is_empty():
		var out: Array = ["attack"]
		for c in hand_pick:
			if out.size() <= _hand_slots() and econ.dev_level() >= int(CARD_DL.get(c, 1)):
				out.append(c)
		if out.size() > 1:
			return out
	return _default_hand()


## The default hand: before DL6 it teases the airstrike; from DL6 the 5th slot takes the landing (DL7 opens it),
## at DL8 the missile replaces the encirclement.
func _default_hand() -> Array:
	var dl: int = econ.dev_level()
	if dl < 6:
		return ["attack", "breakthrough", "airstrike", "encircle", "defense"]
	if dl < 8:
		return ["attack", "breakthrough", "airstrike", "encircle", "defense", "landing"]
	return ["attack", "breakthrough", "airstrike", "landing", "missile", "defense"]


## The hand row of the battle UI: the cards of this DL, those not open yet greyed with their DL.
func _show_hand() -> void:
	var locked := {}
	for c in _hand_display():
		if econ.dev_level() < int(CARD_DL.get(c, 1)):
			locked[c] = int(CARD_DL.get(c, 1))
	ui.set_hand(_hand_display())
	ui.set_locked(locked)


func _hand() -> Array:
	var hand: Array = []
	for c in _hand_display():
		if econ.dev_level() >= int(CARD_DL.get(c, 1)):
			hand.append(c)
	for k in war:
		if String(k).begins_with("ally_"):
			return hand + ["corps"]
	return hand


func _state_dl(side: int) -> int:
	return econ.dev_level() if side == Types.PLAYER else int(sim.states[side]["dev_level"])


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
		for c in _hand():
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
			if mine and bool(ev.get("river", false)):
				_stat("river_crossings")  # «Форсирование»
			if mine and sim.cells[int(ev["hex"])]["kind"] == "capital":
				_stat("capitals_occupied")  # «У ворот столицы»
			map_view.smoke(ev["hex"], 5.0, true)
			map_view.burst(ev["hex"], MapView.C_PLAYER if mine else MapView.C_WAR, true)
			map_view.floater(ev["hex"], tr("floater.occupied") if mine else tr("floater.lost"), Color(0.75, 0.85, 1.0) if mine else Color(1.0, 0.7, 0.7))
			if mine and not war.is_empty() and ev["hex"] == war["goal"]:
				_stat("goals")
				ui.toast(tr("toast.goal_taken"))
		"tower_hit":
			map_view.tower_volley(int(ev["hex"]), int(ev["target"]))
		"missile":
			if mine and int(sim.cells[int(ev["hex"])].get("tower", 0)) > 0:
				_stat("missile_towers")  # «Точный удар»: a tower knocked out
			var from_cap: int = sim.states[int(ev.get("side", Types.PLAYER))]["capital_id"]
			map_view.missile(map_view.cell_world(from_cap), int(ev["hex"]))
		"landing":
			var ls: int = int(ev.get("side", Types.PLAYER))
			map_view.airstrike(int(ev["hex"]), [], _state_dl(ls), map_view.state_color(ls) if ls != Types.PLAYER else MapView.C_PLAYER)
			map_view.floater(int(ev["hex"]), tr("floater.landing"), Color(0.75, 0.9, 1.0))
		"flak":
			map_view.flak(int(ev["hex"]))
			if int(ev["tick"]) != _flak_tick:  # one «ПВО −50%» per strike, over its first defended hex
				_flak_tick = int(ev["tick"])
				map_view.floater(int(ev["hex"]), tr("floater.air_defense"), Color(0.75, 0.9, 1.0))
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
				var side: int = int(ev.get("side", Types.PLAYER))
				map_view.airstrike(int(ev["hex"]), battle.airstrike_area(int(ev["hex"])), _state_dl(side),
					map_view.state_color(side))
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
	var camp_opts := {"attacker": Types.PLAYER, "defender": Types.NOBODY, "ai_energy_mult": 0,
		"cards": _hand(), "camp": hex, "ticks": Camps.FIGHT_TICKS}
	camp_opts.merge(_apply_commanders())
	ui.cost_discount = {"landing": int(camp_opts.get("landing_discount", 0))}
	battle = Battle.new(sim, armies, camp_opts)
	battle.garrison[hex] = camps.garrison(total / maxi(1, n), now_s())
	_show_hand()
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
		bp.gain("camp", now_s())
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
	_stat("offensives")
	bp.gain("offensive3" if stars >= 3 else ("offensive2" if stars >= 2 else "offensive"), now_s())
	if stars >= 2:
		_stat("stars2")
	if stars >= 3:
		_stat("stars3")
	stats["captures"] = int(stats.get("captures", 0)) + (res["captured"] as Array).size()
	if battle.landing_held(Types.PLAYER):
		_stat("landings_held")  # «Высадка»: the landing hex is still ours at the end
	var ws := War.war_score(sim, war)
	stats["wedges"] = int(stats.get("wedges", 0)) + int(battle.wedges.get(Types.PLAYER, 0))
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
	if ftue == 0:
		_schedule_counter()
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
		text = "×%.1f" % f + _cmd_mark([_drag_army], to)
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
	if ok and card in ["attack", "breakthrough", "encircle"]:
		var ids: Array = []
		for a in battle.adjacent_idle_armies(Types.PLAYER, id):
			ids.append(a["id"])
		if not ids.is_empty():
			var f: float = battle.forecast(Types.PLAYER, ids, id, card == "breakthrough")["f"]
			_drag_lbl.text = "×%.1f" % f + _cmd_mark(ids, id)
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
	if battle.energy_points(Types.PLAYER) < battle.card_cost(Types.PLAYER, card):
		ui.toast(tr("toast.no_energy") % battle.card_cost(Types.PLAYER, card))
	elif not battle.card_ready(Types.PLAYER, card):
		ui.toast(tr("toast.card_cooldown"))
	elif battle.issue(Types.PLAYER, {"t": "card", "card": card, "target": id}):
		if card != "attack":
			_stat("cards")
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
	var kort: Dictionary = _army_by_id(commanders.army_of("cmd_kort")) if _cmd_level("cmd_kort") > 0 else {}
	for d in _demands:
		if d["kind"] == "pocket" and not kort.is_empty() and _touches_any(int(kort["hex"]), d["hexes"]):
			d["cost"] = Types.round1(float(d["cost"]) / _cmd_v("cmd_kort", 0))  # Marshal Kort: pockets give up faster
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
	ui.show_peace(_state_name(war["enemy"]), ws["score"], ws["control"], _demands, _chosen, plunder_level,
		_leader_portrait(int(war["enemy"])), map_view.state_color(int(war["enemy"])))
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
const RESEARCH_LOSS := [0, 5, 8, 12]
var plunder_level := 1  # 0 spare, 1 light 30%, 2 medium 45%, 3 heavy 60% (canon §9.14)
const PLUNDER_PCT := [0.0, 0.30, 0.45, 0.60]
const PLUNDER_OPINION := [20.0, -10.0, -20.0, -30.0]


## Hexes the allies took from the enemy become theirs at peace (canon §10.7).
func _allies_annex(enemy: int) -> void:
	for c in sim.cells:
		if c["owner"] == enemy and allies.has(int(c["controller"])):
			c["owner"] = c["controller"]
			map_view.refresh_hex(int(c["id"]))


func _sign_peace() -> void:
	if not war.is_empty():
		_allies_annex(int(war["enemy"]))
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
	if _last_score > 0.0:
		bp.gain("peace", now_s())
		_stat("peace_wins")
		_coalition_win()
		if plunder_level == 0:
			_stat("mercy")  # «Пощадить» in a victorious treaty (07 §7.2)
		if _last_score >= 100.0:
			_stat("routs")
	if enemy == RingNext.ALVARIA and _last_score >= 30.0:
		_stat("hegemon_wins")  # «Укротитель волков»
	if enemy == RingNext.CONCLAVE and _last_score >= 30.0:
		_stat("conclave_wins")  # «Сталь против стали»
	if war.has("ult_refused"):
		_stat("ult_wins")  # «Не на тех напали»: refused an ultimatum and won the war
	for d in chosen:
		if d["kind"] == "pocket":
			_stat("pockets")
			stats["pocket_hexes"] = int(stats.get("pocket_hexes", 0)) + (d["hexes"] as Array).size()
			if (d["hexes"] as Array).size() >= 4:
				_stat("pockets4")
				if (d["hexes"] as Array).size() >= 8:
					_stat("pockets8")  # «Большой котёл»
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
		_grant_bram()
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
	lines.append(tr("ceremony.chapter") % [hexes_before, _player_hexes(), _chapter_goal()])
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
		# trophy blueprints: +1 / +2 / +3 (canon §9.14), kept up to 5 — the rest burn
		var burned: int = research.add_blueprints(plunder_level)
		stats["blueprints"] = int(stats.get("blueprints", 0)) + plunder_level
		lines.append(tr("ceremony.blueprints") % [plunder_level, research.blueprints] + (tr("ceremony.blueprints_burned") % burned if burned > 0 else ""))
	_opinion_add(enemy, PLUNDER_OPINION[plunder_level])
	# «Угроза» (canon §10.8): the value of every annexed hex (a city +4 more), plunder +5 / +10 / +15
	var annexed_threat := 0.0
	for id in annexed:
		annexed_threat += float(sim.cells[id]["value"]) + (4.0 if sim.cells[id]["kind"] == "city" else 0.0)
	threat += annexed_threat + 5.0 * plunder_level
	if war.has("coalition") and _last_score > 0.0 and not war.has("sep_defeat"):
		# «Триумф» (canon §10.8): a won coalition war pays a golden trophy chest
		var chest := 6 * maxi(60, int(gross.get("gold", 0)))
		econ.add_resources({"gold": chest})
		econ.res["raivite"] = int(econ.res["raivite"]) + 30
		lines.append(tr("ceremony.triumph") % chest)
		_stat("coalition_wins")
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
	var resume := _ftue_next
	_ftue_next = 0
	if resume == 7 and not stats.has("flag_wizard"):
		# FTUE 2:30 (canon §14.3): after the first peace the player makes the flag in 3 taps, then the tour goes on
		stats["flag_wizard"] = 1
		_open_flag_wizard(0, FlagView.random_flag(_flag_seed()), func(): _open_name_editor(func(): ftue = 7))
	elif resume > 0:
		ftue = resume
	map_view.ceremony_t = -1.0
	map_view.flip_at = {}
	map_view.prev_owner = {}
	map_view.mark_dirty()
	_ceremony = {}
	_set_mode(Mode.MAP)
	if _player_hexes() >= _chapter_goal() and not chapter_done:
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
	research.lose_progress(RESEARCH_LOSS[lvl], now_s())  # −5 / −8 / −12% of the running research (canon §9.14)
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
	_allies_annex(enemy)
	ui.close_modal()
	if ftue >= 10:
		ftue = 0  # the tutorial war ended without a treaty — let the player go on freely
	map_view.strike_arrow(-1, -1, "")
	truce[enemy] = Time.get_unix_time_from_system() + TRUCE_SEC
	for m in war.get("coalition", []):
		truce[int(m)] = Time.get_unix_time_from_system() + TRUCE_SEC  # the coalition makes peace together
	# the war's borrowed strength goes home with it: the coalition's share and a running subsidy
	var k := 1.0
	if war.has("coalition_f"):
		k /= float(war["coalition_f"]) / 1000.0
	if war.has("subsidy_until"):
		k /= 1.1
	if k < 0.999:
		for a in armies:
			if int(a["side"]) == enemy:
				a["max_str"] = maxi(1, roundi(float(a["max_str"]) * k))
				a["str"] = mini(int(a["str"]), int(a["max_str"]))
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
	if ui:
		ui.set_portrait_era(econ.dev_level())
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
	map_view.fog_visible = _fog_visible()
	_wake_oil()
	_ai_growth(now)
	_ai_colonize(now)
	_ai_wars_tick(now)
	_ai_alliances_tick(now)
	_ai_swap_tick(now)
	for h in colonizing.keys():
		if now >= int(colonizing[h]):
			_finish_colonize(h)
		else:
			map_view.hex_label(h, "⛳ " + GameUI.fmt_time(int(colonizing[h]) - now))
	hud.set_resources(econ.res, econ.income_per_hour(sim), econ.storage_cap(), econ.builders + econ.bonus_builders - econ.busy_builders(now), econ.builders + econ.bonus_builders)
	hud.set_level(econ.dev_level())
	hud.set_mail(_unread())
	_market_hint()
	_apply_remote_if_any()
	hud.shop_dot.visible = cases.claim_free_crates(now) > 0
	_patent_tick(now)
	_calendar_tick(now)
	_chronicle_tick()
	_orders_chip()
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
			if STORY_DL.has(econ.dev_level()):  # the advisor marks the big eras (07 §3.6–3.8)
				_post("inbox.advisor.title", String(STORY_DL[econ.dev_level()]))
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
		var to_lvl: int = int(tower["level"]) + 1
		# from lvl 6 the tower is also air defence (canon §7)
		ui.toast(tr("toast.tower_aa" if to_lvl == Battle.AIR_DEFENSE_LVL else "toast.tower_upgrade") % to_lvl)
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
	for h in econ.vein_secs:
		if econ.vein_amount(int(h)) >= 1:
			data[int(h)] = {"res": "raivite", "amount": econ.vein_amount(int(h))}
	map_view.set_bubbles(data)


## «Собрать всё» (canon §4): any coin collects every hex.
func _collect_all() -> void:
	econ.tick(sim, now_s())
	var shown := {}
	for h in econ.stock:
		shown[h] = econ.stock[h].duplicate()
	var veins := {}
	for h in econ.vein_secs:
		if econ.vein_amount(int(h)) > 0:
			veins[int(h)] = econ.vein_amount(int(h))
	var gained: Dictionary = econ.collect_all()
	stats["gold_collected"] = int(stats.get("gold_collected", 0)) + int(gained.get("gold", 0))
	var crystals: int = econ.collect_veins()
	if now_s() - _collect_counted >= 1800:  # order_collect_3 counts collections ≥30 min apart (08 §8.6.3)
		_collect_counted = now_s()
		_stat("collects")
	for h in veins:
		map_view.floater(int(h), "+%d" % int(veins[h]), Color(0.55, 0.85, 1.0))
	var total := crystals
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
	var maxed: Array = []
	for id in Commanders.PASSIVES:
		if Commanders.maxed(_cmd_rarity(id), int(cases.shards.get(id, 0))):
			maxed.append(id)
	return {"income_per_hour": econ.gross_per_hour(sim), "dl": econ.dev_level(), "commanders_maxed": maxed}


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
			_stat("crates")
		"ad":
			if not _rewarded("ad_free_crate", 2):
				return
		"key":
			if int(cases.royal_keys) <= 0:
				return
			cases.royal_keys -= 1
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


## Demo helper: the player settles a corridor up to a hex of `s` and wraps around it, so their border bends.
func _demo_salient(s: int) -> void:
	var core := MapGen.core_of(sim, s)
	var q := -1
	var best := 0
	for c in sim.cells:
		if c["owner"] != s or core.has(c["id"]) or not _swappable(c["id"], s):
			continue
		var free := 0
		for n in sim.neighbors[c["id"]]:
			if n >= 0 and sim.cells[n]["owner"] == Types.NOBODY and Types.is_passable(sim.cells[n]):
				free += 1
		if free > best:
			best = free
			q = c["id"]
	if q < 0:
		return
	var ring: Array = []
	for n in sim.neighbors[q]:
		if n >= 0 and sim.cells[n]["owner"] == Types.NOBODY and Types.is_passable(sim.cells[n]):
			ring.append(n)
	# breadth-first over wild land from the player's hexes to the ring
	var prev := {}
	var queue: Array = []
	for c in sim.cells:
		if c["owner"] == Types.PLAYER:
			prev[c["id"]] = -1
			queue.append(c["id"])
	var hit := -1
	while not queue.is_empty() and hit < 0:
		var h: int = queue.pop_front()
		for n in sim.neighbors[h]:
			if n < 0 or prev.has(n) or sim.cells[n]["owner"] != Types.NOBODY or not Types.is_passable(sim.cells[n]):
				continue
			prev[n] = h
			if ring.has(n):
				hit = n
				break
			queue.append(n)
	var claim: Array = ring.duplicate()
	var h2 := hit
	while h2 >= 0 and sim.cells[h2]["owner"] != Types.PLAYER:
		claim.append(h2)
		h2 = prev[h2]
	for h in claim:
		sim.cells[h]["owner"] = Types.PLAYER
		sim.cells[h]["controller"] = Types.PLAYER
		map_view.refresh_hex(h)
	map_view.mark_dirty()


## Store purchases: no billing SDK yet. Debug (test) builds grant the item so flows can be tested.
func _on_buy_sku(sku: String) -> void:
	if sku == "patent_screen":
		_open_patent()
		return
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
		"iap_pass", "iap_pass_elite", "iap_pass_elite_up":
			bp.refresh(now_s())
			if (bp.premium and sku == "iap_pass") or bp.elite:
				ui.toast(tr("toast.pass_owned"))  # a store would not sell it twice in a season
				return
			bp.buy(sku)
			if sku != "iap_pass":
				cases.owned_cosmetics[String(BattlePass.data().get("elite_cosmetic", ""))] = true
			ui.toast(tr("toast.pass_bought"))
			_open_pass()
		"iap_sub_patent", "iap_sub_trial":
			patent.buy(now_s(), sku == "iap_sub_trial")
			_patent_tick(now_s())
			ui.toast(tr("toast.patent_on") % patent.days_left(now_s()))
			_open_patent()
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
			"reason": L.t(research.can_start(line, dl, acad, econ.res, now)), "stock": speed_minutes,
			"bp": research.blueprints if busy else 0})
	items.sort_custom(func(x, y): return int(x["busy"]) > int(y["busy"]))
	return items


func _on_research_start(line: String) -> void:
	var now := now_s()
	if not research.start(line, econ.dev_level(), _academy_level(), econ.res, now):
		ui.toast(L.t(research.can_start(line, econ.dev_level(), _academy_level(), econ.res, now)))
		return
	_stat("research_starts")
	sfx.play("coin")
	ui.toast(tr("toast.research_started") % [tr(String(Research.LINES[line]["name"])), research.level(line) + 1, GameUI.fmt_time(int(research.current["end"]) - now)])
	_econ_tick()
	_autosave()


func _on_research_speedup(line: String) -> void:
	if research.current.is_empty():
		return
	var now := now_s()
	if line.begins_with("bp:"):
		# «Применить чертёж» (07 §6.1): −10% of what is left, −50% at most per research
		if research.apply_blueprint(now):
			_stat("blueprints_used")
			sfx.play("seal")
			ui.toast(tr("toast.blueprint") % [GameUI.fmt_time(int(research.current["end"]) - now), research.blueprints])
		else:
			ui.toast(tr("toast.blueprint_max"))
		_econ_tick()
		_autosave()
		return
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
	_stat("research_done")
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


## Chapter II stars (07 §3.3; rivers, oil, veins and alliances come later): progress counts from the chapter's
## opening (`stats_base`), «@ports» counts the ports the player owns.
const STARS_2 := [
	["c2_port", "star.c2_port", "@ports", 1],
	["c2_river", "star.c2_river", "river_crossings", 1],
	["c2_alliance", "star.c2_alliance", "alliances", 1],
	["c2_defense", "star.c2_defense", "defenses", 1],
	["c2_pocket4", "star.c2_pocket4", "pockets4", 1],
	["c2_ultimatum", "star.c2_ultimatum", "ult_wins", 1],
	["c2_colonize", "star.c2_colonize", "colonized", 4],
	["c2_camps", "star.c2_camps", "camps", 3],
	["c2_dl5", "star.c2_dl5", "", 5],
]


## Chapter III stars (07 §3.7; coalitions and territory swaps come later): progress from the chapter's opening.
const STARS_3 := [
	["c3_factory", "star.c3_factory", "@factories", 1],
	["c3_oil2", "star.c3_oil2", "@oil", 2],
	["c3_hegemon", "star.c3_hegemon", "hegemon_wins", 1],
	["c3_capital", "star.c3_capital", "capitals_occupied", 1],
	["c3_triumph", "star.c3_triumph", "coalition_wins", 1],
	["c3_swap", "star.c3_swap", "swaps", 1],
	["c3_vein", "star.c3_vein", "@vein3", 1],
	["c3_colonize", "star.c3_colonize", "colonized", 6],
	["c3_camps", "star.c3_camps", "camps", 5],
	["c3_dl7", "star.c3_dl7", "", 7],
]


## Chapter IV stars (07 §3.8). «Война на два фронта»: two victorious treaties in one coalition war — each member's
## separate peace is a war of its own that ran alongside the rest (06 §14.6).
const STARS_4 := [
	["c4_conclave", "star.c4_conclave", "conclave_wins", 1],
	["c4_two_fronts", "star.c4_two_fronts", "two_fronts", 1],
	["c4_landing", "star.c4_landing", "landings_held", 1],
	["c4_missile", "star.c4_missile", "missile_towers", 1],
	["c4_ultrafence", "star.c4_ultrafence", "@fort8", 1],
	["c4_pocket8", "star.c4_pocket8", "pockets8", 1],
	["c4_cities6", "star.c4_cities6", "@cities", 6],
	["c4_vein", "star.c4_vein", "@vein4", 1],
	["c4_colonize", "star.c4_colonize", "colonized", 8],
	["c4_camps", "star.c4_camps", "camps", 6],
	["c4_dl8", "star.c4_dl8", "", 8],
]


func _stars() -> Array:
	return STARS + (STARS_2 if chapter >= 2 else []) + (STARS_3 if chapter >= 3 else []) + (STARS_4 if chapter >= 4 else [])


func _star_progress(st: Array) -> int:
	var key: String = st[2]
	if key == "":
		return econ.dev_level()
	if key == "@fort8":
		var best := 0
		for c in sim.cells:
			if c["owner"] == Types.PLAYER:
				best = maxi(best, int(c["fort"]))
		return 1 if best >= 8 else 0
	if key.begins_with("@"):
		var want: String = {"@ports": "port", "@factories": "factory", "@oil": "oil", "@vein3": "raivite_vein", "@vein4": "raivite_vein", "@cities": "city"}[key]
		var vein_name: String = {"@vein3": "cell.ch3_vein", "@vein4": "cell.ch4_vein"}.get(key, "")
		var n := 0
		for c in sim.cells:
			if c["owner"] == Types.PLAYER and c["kind"] == want and (vein_name == "" or String(c["name"]) == vein_name):
				n += 1
		return n
	var base := 0
	if String(st[0]).begins_with("c2_"):
		base = int(stats_base.get(key, 0))
	elif String(st[0]).begins_with("c3_"):
		base = int(stats_base3.get(key, 0))
	elif String(st[0]).begins_with("c4_"):
		base = int(stats_base4.get(key, 0))
	return int(stats.get(key, 0)) - base


func _world_items() -> Array:
	var items: Array = [{"kind": "chapter", "hexes": _player_hexes(), "goal": _chapter_goal(), "done": chapter_done,
		"can_expand": _player_hexes() >= _chapter_goal() and war.is_empty() and not chapter_done}]
	if _orders_open():
		bp.refresh(now_s())
		items.append({"kind": "star", "id": "pass", "icon": "🎖", "open": true, "claimed": false,
			"title": tr("pass.card") % bp.level(), "progress": bp.xp % BattlePass.XP_LEVEL, "need": BattlePass.XP_LEVEL})
		if patent.active(now_s()):
			items.append({"kind": "star", "id": "patent_daily", "icon": "📜", "title": tr("patent.card") % Patent.DAILY_RAIVITE,
				"progress": 1 if patent.daily_ready(now_s()) else 0, "need": 1, "claimed": not patent.daily_ready(now_s())})
		var cd: int = maxi(1, calendar.credited)
		items.append({"kind": "star", "id": "calendar", "icon": "🗓", "open": true, "claimed": false, "ready": calendar.pending,
			"title": tr("cal.card") % Calendar.day_in_cycle(cd), "progress": Calendar.day_in_cycle(cd), "need": Calendar.LENGTH})
	items.append_array(_order_items())
	items.append_array(_weekly_items())
	var list := _stars()
	if chapter >= 4:
		list = STARS_4 + STARS_3 + STARS_2 + STARS  # the open chapter first; older stars never expire
	elif chapter >= 3:
		list = STARS_3 + STARS_2 + STARS
	elif chapter >= 2:
		list = STARS_2 + STARS
	for st in list:
		var prog := mini(_star_progress(st), int(st[3]))
		items.append({"kind": "star", "id": st[0], "title": tr(String(st[1])), "progress": prog, "need": st[3],
			"claimed": stars_claimed.has(st[0])})
	return items


func _on_world_action(id: String) -> void:
	if id == "expand":
		_complete_chapter()
		return
	if id.begins_with("swap:order:"):
		if orders.swap(int(id.split(":")[2]), _orders_ctx()):
			sfx.play("tap")
			ui.toast(tr("toast.order_swapped"))
			_open_tab("world")
			_autosave()
		return
	if id.begins_with("order"):
		_claim_order(id)
		return
	if id == "calendar":
		_open_calendar()
		return
	if id == "patent_daily":
		_claim_patent_daily()
		return
	if id.begins_with("weekly"):
		_claim_weekly(id)
		return
	if id == "pass":
		_open_pass()
		return
	for st in _stars():
		if st[0] == id and not stars_claimed.has(id) and _star_progress(st) >= int(st[3]):
			stars_claimed[id] = true
			var gross: Dictionary = econ.gross_per_hour(sim)
			econ.add_resources({"gold": int(gross.get("gold", 0)), "food": int(gross.get("food", 0)), "metal": int(gross.get("metal", 0))})
			econ.res["raivite"] = int(econ.res["raivite"]) + 10
			sfx.play("capture")
			ui.toast(tr("toast.star"))
			if stars_claimed.size() == _stars().size():
				_post("inbox.all_stars.title", "inbox.all_stars.text")
				ui.toast(tr("toast.all_stars"))
	_econ_tick()
	_autosave()


## Chapter legacy (07 §3, canon §12.1), paid once when the chapter's goal is met: I — Captain Lira + 200 Raivites,
## II — Colonel Frey + «River» border ink, III — General Hawk + the 4th builder (600 Raivites if already there),
## IV — Emperor Rai (80 shards — his unlock price) + the «Veteran» frame. A commander is unlocked with shards.
const LEGACY := {
	1: {"cmd": "cmd_lira", "raivite": 200},
	2: {"cmd": "cmd_frey", "cosmetic": "cos_border_ink_river"},
	3: {"cmd": "cmd_hawk", "builder": true},
	4: {"cmd": "cmd_rai", "cosmetic": "cos_frame_veteran"},
}
## The advisor on the era steps (07 §3.6–3.8).
const STORY_DL := {4: "story.dl4", 5: "story.dl5", 6: "story.dl6", 8: "story.dl8"}
## The new neighbours greet the player when a chapter opens (07 §3.6–3.8): [state, line key].
const STORY_OPENING := {
	2: [[4, "story.ch2_league"], [5, "story.ch2_order"]],
	3: [[6, "story.ch3_alvaria"], [7, "story.ch3_saren"]],
	4: [[9, "story.ch4_conclave"], [11, "story.ch4_lakes"]],
}


func _grant_legacy(ch: int) -> String:
	var lg: Dictionary = LEGACY.get(ch, {})
	if lg.is_empty():
		return ""
	var parts: Array = []
	var cmd: String = lg["cmd"]
	var rarity: String = Cases.commander(cmd).get("rarity", "rare")
	var need: int = int(Cases.data().get("commander_unlock_shards", {}).get(rarity, 20))
	cases.shards[cmd] = int(cases.shards.get(cmd, 0)) + need
	parts.append(Cases.commander_name(cmd))
	var rv: int = lg.get("raivite", 0)
	if lg.has("builder"):
		if econ.builders < 4:
			econ.builders += 1
			parts.append(tr("legacy.builder"))
		else:
			rv += 600
	if lg.has("cosmetic"):
		cases.owned_cosmetics[String(lg["cosmetic"])] = true
		var co: Dictionary = Cases.cosmetic(String(lg["cosmetic"]))
		parts.append("%s «%s»" % [Cases.category_name(String(co.get("category", ""))), String(co.get("name_en" if Cases.is_english() else "name", ""))])
	if rv > 0:
		econ.res["raivite"] = int(econ.res["raivite"]) + rv
		parts.append(tr("legacy.raivite") % rv)
	return tr("legacy.line") % [ch, ", ".join(parts)]


# ---------------------------------------------------------------------- «Военный пропуск» (canon §15.6, 09 §9.12)

func _pass_text(r: Array) -> String:
	if r.is_empty():
		return ""
	match String(r[0]):
		"res":
			return tr("pass.rw_res") % int(r[1])
		"crate":
			return tr("pass.rw_crate") if int(r[1]) == 1 else tr("pass.rw_crates") % int(r[1])
		"raivite":
			return tr("pass.rw_raivite") % int(r[1])
		"shards":
			return tr("pass.rw_shards") % [int(r[2]), Cases.commander_name(String(r[1]))]
		"speed":
			return tr("pass.rw_speed") % int(r[1])
		"cosmetic":
			var co: Dictionary = Cases.cosmetic(String(r[1]))
			return "%s «%s»" % [Cases.category_name(String(co.get("category", ""))), String(co.get("name_en" if Cases.is_english() else "name", ""))]
	return ""


func _pay_pass(r: Array) -> void:
	match String(r[0]):
		"res":
			var gross: Dictionary = econ.gross_per_hour(sim)
			var h: int = r[1]
			econ.add_resources({"gold": h * maxi(60, int(gross.get("gold", 0))), "food": h * maxi(30, int(gross.get("food", 0))),
				"metal": h * maxi(30, int(gross.get("metal", 0)))})
		"crate":
			cases.free_crates += int(r[1])
		"raivite":
			econ.res["raivite"] = int(econ.res["raivite"]) + int(r[1])
		"shards":
			cases.shards[String(r[1])] = int(cases.shards.get(String(r[1]), 0)) + int(r[2])
		"speed":
			speed_minutes += int(r[1]) * 60
		"cosmetic":
			cases.owned_cosmetics[String(r[1])] = true


func _open_pass() -> void:
	var now := now_s()
	bp.refresh(now)
	var rows: Array = []
	for lvl in range(1, BattlePass.LEVELS + 1):
		var fs := "claimed" if bp.claimed_free.has(lvl) else ("claim" if bp.can_claim(lvl, "free") else "locked")
		var ps := "claimed" if bp.claimed_prem.has(lvl) else ("claim" if bp.can_claim(lvl, "premium") else "locked")
		rows.append({"lvl": lvl, "free_text": _pass_text(bp.reward(lvl, "free")), "free_state": fs,
			"prem_text": _pass_text(bp.reward(lvl, "premium")), "prem_state": ps})
	ui.show_pass({"season": bp.season + 1, "days_left": int(ceil(float(BattlePass.season_end(now) - now) / 86400.0)),
		"level": bp.level(), "xp_in_level": bp.xp % BattlePass.XP_LEVEL if bp.level() < BattlePass.LEVELS else BattlePass.XP_LEVEL,
		"premium": bp.premium, "elite": bp.elite, "can_buy": _payments_enabled(), "price": "$7.99", "price_elite": "$14.99",
		"price_up": "$6.99", "rows": rows},
		func(lvl: int, track: String):
			var r: Array = bp.claim(lvl, track)
			if not r.is_empty():
				_pay_pass(r)
				sfx.play("coin")
				ui.toast(tr("toast.pass_claim") % _pass_text(r))
				_econ_tick()
				_autosave()
			_open_pass(),
		func(sku: String): _on_buy_sku(sku))


# ---------------------------------------------------------------------- «Приказы дня» (canon §14.5, 08 §8.6)

func _orders_open() -> bool:
	return ftue == 0  # after the tutorial (08 §8.6.1: first session after chapter I or D1 — the tutorial ends first)


func _orders_ctx() -> Dictionary:
	var wild := false
	for c in sim.cells:
		if c["owner"] == Types.NOBODY and Types.is_passable(c) and _touches_player(c["id"]):
			wild = true
			break
	var camp := false
	for cm in camps.active:
		if Camps.attackable(sim, int(cm["hex"])):
			camp = true
	var can_war := not war.is_empty()
	for s in _ai_states():
		if not can_war and _truce_left(s) == 0 and _pact_left(s) == 0 and War.recommend_goals(sim, s, 1).size() > 0:
			can_war = true
	return {"dl": econ.dev_level(), "stats": stats, "tags": {"camp": camp, "wild": wild, "market": Market.market_level(econ) > 0,
		"ch2": chapter >= 2, "war": can_war}}


## The World tab's first cards: today's three orders and the bonus for all three.
func _order_items() -> Array:
	if not _orders_open():
		return []
	orders.refresh(now_s(), _orders_ctx())
	var out: Array = []
	for i in orders.list.size():
		var o: Dictionary = orders.list[i]
		out.append({"kind": "star", "id": "order:%d" % i, "icon": "⚑", "title": "%s · +%d %s" % [tr("order." + String(o["code"])), int(o["xp"]), tr("pass.xp")],
			"progress": orders.progress(i, stats), "need": int(o["need"]), "claimed": bool(o["claimed"]),
			"swap": not orders.swapped and not o["claimed"] and not orders.done(i, stats)})
	var claimed_n := 0
	for o in orders.list:
		if o["claimed"]:
			claimed_n += 1
	out.append({"kind": "star", "id": "orders_all", "icon": "🎁", "title": tr("orders.all"), "progress": claimed_n, "need": 3,
		"claimed": orders.all_claimed})
	return out


func _claim_order(id: String) -> void:
	if id == "orders_all":
		if orders.claim_all():
			_stat("orders_all_days")
			cases.free_crates += 1  # a War crate (canon §14.5) waits in the Shop
			econ.res["raivite"] = int(econ.res["raivite"]) + Orders.ALL_RAIVITE
			sfx.play("fanfare")
			ui.toast(tr("toast.orders_all"))
	else:
		var xp: int = orders.claim(int(id.split(":")[1]), stats)
		if xp > 0:
			bp.add_xp(xp, now_s())
			sfx.play("coin")
			ui.toast(tr("toast.order_done") % xp)
	_open_tab("world")
	_refresh_ui()
	_autosave()


## Weekly tasks (08 §8.7) after the orders: 7 cards with their XP, then the chest's two steps.
func _weekly_items() -> Array:
	if not _orders_open():
		return []
	weekly.refresh(now_s(), econ.dev_level(), stats)
	var out: Array = []
	for i in Weekly.TASKS.size():
		var t: Array = Weekly.TASKS[i]
		out.append({"kind": "star", "id": "weekly:%d" % i, "icon": "📅", "title": "%s · +%d %s" % [tr("weekly." + String(t[0])), int(t[3]), tr("pass.xp")],
			"progress": weekly.progress(i, stats), "need": int(weekly.need[i]), "claimed": weekly.claimed.has(i)})
	for step in 2:
		out.append({"kind": "star", "id": "weekly_chest:%d" % step, "icon": "🎁", "title": tr(["weekly.chest1", "weekly.chest2"][step]),
			"progress": weekly.done_count(), "need": int(Weekly.STEP_NEED[step]), "claimed": weekly.chest.has(step)})
	return out


func _claim_weekly(id: String) -> void:
	var now := now_s()
	if id.begins_with("weekly_chest:"):
		var step := int(id.split(":")[1])
		if weekly.claim_chest(step):
			if step == 0:
				cases.free_crates += 2
				speed_minutes += 2 * 60
			else:
				_pay_pass(["res", 8])
				speed_minutes += 3 * 60
				cases.free_crates += 1
				# 10 shards of a common or rare commander not yet at level 20 (08 §8.7.2): the least advanced one
				var best := _least_commander()
				cases.shards[best] = int(cases.shards.get(best, 0)) + 10
			sfx.play("fanfare")
			ui.toast(tr("toast.weekly_chest"))
	else:
		var xp: int = weekly.claim(int(id.split(":")[1]), stats)
		if xp > 0:
			bp.add_xp(xp, now)
			sfx.play("coin")
			ui.toast(tr("toast.order_done") % xp)
	_open_tab("world")
	_refresh_ui()
	_autosave()


## The common or rare commander with the fewest shards (the weekly chest and the calendar's «on choice» shards).
func _least_commander() -> String:
	var best := "cmd_bram"
	for c in ["cmd_bram", "cmd_lira", "cmd_olm", "cmd_vik", "cmd_vega", "cmd_kort", "cmd_seir", "cmd_frey"]:
		if int(cases.shards.get(c, 0)) < int(cases.shards.get(best, 0)):
			best = c
	return best


## HUD chip «⚑ 1/3» (08 §8.6): today's claimed orders; the dot means something waits to be taken (an order, the
## bonus for all three, or the calendar's day). Tapping it opens the World tab.
func _orders_chip() -> void:
	if not _orders_open():
		hud.set_orders("", false, false)
		return
	orders.refresh(now_s(), _orders_ctx())
	var claimed_n := 0
	var ready: bool = calendar.pending
	for i in orders.list.size():
		if orders.list[i]["claimed"]:
			claimed_n += 1
		elif orders.done(i, stats):
			ready = true
	if orders.all_done() and not orders.all_claimed:
		ready = true
	hud.set_orders("%d/%d" % [claimed_n, orders.list.size()], ready, true)


# ---------------------------------------------------------------------- login calendar (canon §14.5, 08 §8.8)

const SEASON_COSMETICS := ["cos_frame_season_1", "cos_frame_ice", "cos_emote_applause", "cos_emote_snowman",
	"cos_emote_card_up_sleeve", "cos_emote_salute", "cos_emote_white_flag", "cos_emote_laugh"]


## Credits a new calendar day on the first tick of a game day after the tutorial; the screen opens by itself
## once the player is on the map with nothing else open (08 §8.8.1: after «while you were away», outside battles).
func _calendar_tick(now: int) -> void:
	if not _orders_open():
		return
	if calendar.visit(now):
		_cal_auto = save_enabled
	if _cal_auto and mode == Mode.MAP and not ui.has_modal() and shop == null:
		_cal_auto = false
		_open_calendar()


func _cal_text(r: Array) -> String:
	match String(r[0]):
		"speed":
			return tr("cal.rw_speeds") % [int(r[2]), int(r[1])] if int(r[2]) > 1 else tr("pass.rw_speed") % int(r[1])
		"builder":
			return tr("cal.rw_builder")
		"cmd":
			return tr("cal.rw_cmd") % Cases.commander_name(String(r[1]))
		"shards_pick", "shards_choice":
			return tr("cal.rw_shards_pick") % int(r[1])
		"season_cosmetic":
			return tr("cal.rw_season")
	return _pass_text(r)


## Pays one calendar reward (×mult) and returns its line for the toast.
func _pay_calendar(r: Array, mult: int) -> String:
	match String(r[0]):
		"res", "crate", "raivite":
			var x := [r[0], int(r[1]) * mult]
			_pay_pass(x)
			return _pass_text(x)
		"shards":
			var x := ["shards", r[1], int(r[2]) * mult]
			_pay_pass(x)
			return _pass_text(x)
		"shards_pick":
			var x := ["shards", _least_commander(), int(r[1]) * mult]
			_pay_pass(x)
			return _pass_text(x)
		"shards_choice":
			calendar.choice += int(r[1]) * mult  # given once the player picks the commander
			return tr("cal.rw_shards_pick") % (int(r[1]) * mult)
		"speed":
			speed_minutes += int(r[1]) * int(r[2]) * mult * 60
			return _cal_text([r[0], r[1], int(r[2]) * mult])
		"builder":
			if econ.builders < 5:  # 5 permanent builders at most (08 §8.8.4)
				econ.builders += 1
				return tr("cal.rw_builder")
			econ.res["raivite"] = int(econ.res["raivite"]) + 600
			return tr("pass.rw_raivite") % 600
		"cmd":
			# the unlock price in shards; an already open commander gets the same shards (08 §8.8.4)
			var cmd: String = r[1]
			var rarity: String = Cases.commander(cmd).get("rarity", "rare")
			var need: int = int(Cases.data().get("commander_unlock_shards", {}).get(rarity, 20))
			cases.shards[cmd] = int(cases.shards.get(cmd, 0)) + need
			return tr("cal.rw_cmd") % Cases.commander_name(cmd)
		"cosmetic":
			_pay_pass(r)
			return _pass_text(r)
		"season_cosmetic":
			for id in SEASON_COSMETICS:
				if not cases.owned_cosmetics.has(id):
					cases.owned_cosmetics[id] = true
					return _pass_text(["cosmetic", id])
			econ.res["raivite"] = int(econ.res["raivite"]) + 50
			return tr("pass.rw_raivite") % 50
	return ""


func _open_calendar() -> void:
	if calendar.choice > 0:
		_pick_cal_commander()
		return
	var n: int = calendar.credited
	var cyc := Calendar.cycle_of(maxi(1, n))
	var first := (cyc - 1) * Calendar.LENGTH
	var days: Array = []
	for d in range(1, Calendar.LENGTH + 1):
		var k := first + d
		var e: Array = Calendar.entry(k)
		var parts := PackedStringArray()
		for r in e[0]:
			parts.append(_cal_text(r))
		var state := "future"
		if k < n or (k == n and not calendar.pending):
			state = "claimed"
		elif k == n:
			state = "today"
		days.append({"day": d, "text": " + ".join(parts), "state": state, "key": not bool(e[1])})
	ui.show_calendar({"cycle": cyc, "days": days, "pending": calendar.pending, "can_double": calendar.can_double(),
		"patent": patent.active(now_s())},
		func(double: bool): _claim_calendar(double))


func _claim_calendar(double: bool) -> void:
	if not calendar.pending:
		return
	if double and not (calendar.can_double() and _rewarded("ad_daily_double", 1)):
		return
	var parts := PackedStringArray()
	for r in calendar.claim():
		parts.append(_pay_calendar(r, 2 if double else 1))
	sfx.play("fanfare")
	ui.toast(tr("toast.cal_claim") % ", ".join(parts))
	_econ_tick()
	_autosave()
	if calendar.choice > 0:
		_pick_cal_commander()
	else:
		_open_calendar()


## «15 осколков командира на выбор» (08 §8.8.2, day 26): the common and rare commanders, with the shards each has.
const CHOICE_COMMANDERS := ["cmd_bram", "cmd_lira", "cmd_olm", "cmd_vik", "cmd_vega", "cmd_kort", "cmd_seir", "cmd_frey"]


func _pick_cal_commander() -> void:
	if calendar.choice <= 0:
		return
	var n: int = calendar.choice
	var buttons: Array = []
	for c in CHOICE_COMMANDERS:
		var cmd: String = c
		buttons.append([tr("cal.pick_btn") % [Cases.commander_name(cmd), int(cases.shards.get(cmd, 0))], Color(0.2, 0.36, 0.6), func():
			_give_cal_shards(cmd)])
	ui.show_choice(tr("cal.pick_title") % n, [tr("cal.pick_line")], buttons)


func _give_cal_shards(cmd: String) -> void:
	if calendar.choice <= 0:
		return
	var n: int = calendar.choice
	calendar.choice = 0
	cases.shards[cmd] = int(cases.shards.get(cmd, 0)) + n
	ui.close_modal()
	sfx.play("coin")
	ui.toast(tr("toast.pass_claim") % _pass_text(["shards", cmd, n]))
	_autosave()
	_open_calendar()


## Content wall (canon §12.1): chapter II is not out yet — the legacy is paid and a teaser shown.
func _complete_chapter() -> void:
	if chapter_done or _player_hexes() < _chapter_goal() or not war.is_empty():
		return
	if chapter < LAST_CHAPTER:
		_world_expansion()
		return
	chapter_done = true
	ui.toast(_grant_legacy(chapter))
	map_view.fireworks(map_view.cell_world(sim.states[Types.PLAYER]["capital_id"]), 5)
	sfx.play("fanfare")
	_post("inbox.chapter_done.title", "inbox.chapter_done.text")
	ui.toast(tr("toast.chapter_done"))
	_autosave()


## «Мир расширяется» (canon §12.1, 02 §17.1, 07 §4): the chapter's legacy, the next ring with its new states and
## their forts by the AI norm, the new goal; the camera pulls back over the new world.
func _world_expansion() -> void:
	var hexes_before := _land_count()
	var old_n: int = sim.cells.size()
	var old_states: int = sim.states.size()
	var legacy := _grant_legacy(chapter)
	_expand_world()
	if sim.cells.size() == old_n:
		return
	var fresh: Array = range(old_states, sim.states.size())
	var next_ch := chapter + 1
	# the ceremony map (02 §17.1): clouds over the new ring part from the old border outward
	var ring: Array = []
	for i in range(old_n, sim.cells.size()):
		ring.append(i)
	ring.sort_custom(func(a, b): return HexGrid.distance(HexGrid.axial(sim.cells[a]), Vector2i.ZERO) < HexGrid.distance(HexGrid.axial(sim.cells[b]), Vector2i.ZERO) if HexGrid.distance(HexGrid.axial(sim.cells[a]), Vector2i.ZERO) != HexGrid.distance(HexGrid.axial(sim.cells[b]), Vector2i.ZERO) else a < b)
	map_view.veil_hexes(ring)
	map_view.part_clouds(ring, 3.2)
	chapter = next_ch
	econ.chapter = next_ch
	if next_ch == 2:
		stats_base = stats.duplicate()
	elif next_ch == 3:
		stats_base3 = stats.duplicate()
	else:
		stats_base4 = stats.duplicate()
	_ai_forts(fresh)
	map_view.refresh_props()
	map_view.set_camps(camps.active)
	var hexes_after := _land_count()
	var mid := Vector3.ZERO
	for c in sim.cells:
		mid += MapView.axial_to_world(int(c["q"]), int(c["r"]))
	mid /= float(sim.cells.size())
	# pull back until the new world fits: the portrait frame is ~0.32 × distance wide (fov 32°, 9:16)
	var lo_x := 1.0e9
	var hi_x := -1.0e9
	for c in sim.cells:
		var px: float = MapView.axial_to_world(int(c["q"]), int(c["r"])).x
		lo_x = minf(lo_x, px)
		hi_x = maxf(hi_x, px)
	var fit := ((hi_x - lo_x + 7.0) / 0.32 - 7.5) / 16.5  # + room for the HUD columns
	rig.focus(Vector3((lo_x + hi_x) / 2.0, 0, mid.z + 1.5), clampf(fit, 2.3, 6.0))
	var t := 2.2
	for s in fresh:
		var cap: int = sim.states[s]["capital_id"]
		get_tree().create_timer(t).timeout.connect(func():
			map_view.burst(cap, map_view.state_color(s), true)
			map_view.floater(cap, _state_name(s), map_view.state_color(s).lightened(0.4))
			sfx.play("capture"))
		t += 1.0
	sfx.play("fanfare")
	await get_tree().create_timer(t + 1.4).timeout
	var sfx_key := "" if next_ch == 2 else str(next_ch)
	_post("inbox.expansion.title", L.pack("inbox.expansion%s.text" % sfx_key, [hexes_before, hexes_after, _chapter_goal()]))
	var lines: Array = [tr("expansion.world") % [hexes_before, hexes_after], tr("expansion.states" + sfx_key)]
	for s in fresh:
		lines.append("· %s — %s, %s" % [_state_name(s), tr(String(LEADERS[s][1])), tr("dl.short") % int(sim.states[s]["dev_level"])])
	lines.append(tr("expansion.goal" + sfx_key) % [_chapter_goal(), _player_hexes()])
	lines.append(legacy)
	for q in STORY_OPENING.get(next_ch, []):
		lines.append("%s: «%s»" % [tr(String(LEADERS[int(q[0])][0])), tr(String(q[1]))])
	lines.append(tr("expansion.advisor" + sfx_key))
	ui.show_info(tr("expansion.title"), lines, tr("ui.continue"), func():
		ui.close_modal()
		rig.focus(map_view.cell_world(sim.states[Types.PLAYER]["capital_id"]), 0.6))
	_autosave()


func _land_count() -> int:
	var n := 0
	for c in sim.cells:
		if Types.is_passable(c):
			n += 1
	return n


## AI forts by the canon norm (§9.16): 25% of border hexes at DL − 2; Wolf 15% and −1; Turtle 40% and +2.
func _ai_forts(states: Array) -> void:
	for s in states:
		var arch: String = sim.states[s]["archetype"]
		var share := 25
		var lvl: int = int(sim.states[s]["dev_level"]) - 2
		if arch == "wolf":
			share = 15
			lvl -= 1
		elif arch == "turtle":
			share = 40
			lvl += 2
		lvl = clampi(lvl, 1, 10)
		var border: Array = []
		for c in sim.cells:
			if c["owner"] != s or not Types.is_passable(c) or c["kind"] == "capital":
				continue
			for n in sim.neighbors[c["id"]]:
				if n >= 0 and sim.cells[n]["owner"] != s and Types.is_passable(sim.cells[n]):
					border.append(c)
					break
		border.sort_custom(func(a, b): return int(a["value"]) > int(b["value"]) if int(a["value"]) != int(b["value"]) else int(a["id"]) < int(b["id"]))
		for c in border.slice(0, maxi(1, border.size() * share / 100)):
			c["fort"] = lvl


# ---------------------------------------------------------------------- diplomacy (canon §10.4–10.6)

## Leader name, archetype and character (translation keys).
const LEADERS := {2: ["leader.barons", "archetype.wolf", "leader.barons.desc"],
	3: ["leader.hamlets", "archetype.fox", "leader.hamlets.desc"],
	4: ["leader.league", "archetype.owl", "leader.league.desc"],
	5: ["leader.order", "archetype.turtle", "leader.order.desc"],
	6: ["leader.alvaria", "archetype.hegemon", "leader.alvaria.desc"],
	7: ["leader.saren", "archetype.fox", "leader.saren.desc"],
	8: ["leader.pack", "archetype.raven", "leader.pack.desc"],
	9: ["leader.conclave", "archetype.hegemon_turtle", "leader.conclave.desc"],
	10: ["leader.veilmark", "archetype.raven", "leader.veilmark.desc"],
	11: ["leader.lakes", "archetype.owl", "leader.lakes.desc"]}


## The leader's portrait id (tools/blender/portrait_assets.py «ldr_…»), "" for a state without one.
func _leader_portrait(s: int) -> String:
	return String(LEADERS[s][0]).replace("leader.", "ldr_") if LEADERS.has(s) else ""


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
	if alarm() >= 0.5:
		v -= 10.0  # «Тревога соседей» 50%+: everyone is wary (canon §10.8)
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and _touches_owner(c["id"], s):
			return v - 10.0  # a shared border, permanently
	return v


## Translation key of the opinion word.
## The face a leader shows on the diplomacy card: angry at war or when hostile, scheming when wary or in a
## coalition against the player, smiling when friendly or allied, calm otherwise.
func _leader_mood(s: int, opinion: float) -> String:
	if not war.is_empty() and (int(war["enemy"]) == s or (war.get("coalition", []) as Array).has(s)):
		return "angry"
	if not coalition.is_empty() and (coalition["members"] as Array).has(s):
		return "cunning"
	if allies.has(s) or opinion > 10.0:
		return "smile"
	if opinion <= -50.0:
		return "angry"
	if opinion < -10.0:
		return "cunning"
	return ""


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
	if _coalition_threshold() > 0:
		var a := alarm()
		var line: String = tr("alarm.calm") if a < 0.5 else (tr("alarm.wary") if a < 1.0 else tr("alarm.high"))
		if not coalition.is_empty():
			line = tr("alarm.forming") % [_state_name(int(coalition["leader"])), (coalition["members"] as Array).size() - 1, GameUI.fmt_time(maxi(0, int(coalition["at"]) - now))]
		elif not war.is_empty() and war.has("coalition"):
			line = tr("alarm.at_war") % (war["coalition"] as Array).size()
		items.append({"kind": "alarm", "pct": roundi(100.0 * a), "line": line})
	for s in _ai_states():
		var status: String = tr("dipl.peace")
		if not war.is_empty() and (int(war["enemy"]) == s or (war.get("coalition", []) as Array).has(s)):
			status = tr("dipl.war")
		elif not coalition.is_empty() and (coalition["members"] as Array).has(s):
			status = tr("dipl.in_coalition")
		elif _pact_left(s) > 0:
			status = tr("dipl.pact") % GameUI.fmt_time(_pact_left(s))
		elif _truce_left(s) > 0:
			status = tr("dipl.truce") % GameUI.fmt_time(_truce_left(s))
		var gift_left := maxi(0, int(gift_at.get(s, 0)) + 86400 - now)
		var v := _opinion_of(s)
		var it_extra := {"ally": allies.has(s), "ally_reason": _ally_reason(s), "can_call": _can_call(s), "ai_ally": _state_name(int(ai_alliances[s])) if ai_alliances.has(s) else ""}
		items.append(it_extra.merged({"id": s, "state": _state_name(s), "leader": tr(String(LEADERS[s][0])), "archetype": tr(String(LEADERS[s][1])),
			"opinion": v, "word": tr(_opinion_word(v)), "status": status,
			"can_war": war.is_empty() and _truce_left(s) == 0 and _pact_left(s) == 0, "gift_cost": _gift_cost(), "gift_left": gift_left,
			"pact_reason": _pact_reason(s), "pact_left": _pact_left(s),
			"separate": _can_separate(s),
			"swap_reason": _swap_reason(s),
			"color": map_view.state_color(s), "flag": map_view.state_flag(s),
			"portrait": _leader_portrait(s), "mood": _leader_mood(s, v)}))
		if not war.is_empty() and (war.get("coalition", []) as Array).has(s):
			(items[items.size() - 1] as Dictionary)["share"] = _member_share(s)
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
		"separate":
			if _can_separate(s):
				_show_separate_offer(s, false)
		"pact":
			var whyp := _pact_reason(s)
			if whyp != "":
				ui.toast(whyp)
				return
			var cost := _pact_cost()
			if econ.res["gold"] < cost:
				ui.toast(tr("toast.no_gold"))
				return
			econ.res["gold"] -= cost
			pacts[s] = now_s() + PACT_SEC
			if not coalition.is_empty() and (coalition["members"] as Array).has(s):
				(coalition["members"] as Array).erase(s)  # it leaves the forming coalition at once
			sfx.play("seal")
			_post(L.pack("inbox.pact.title", [_state_key(s)]), L.pack("inbox.pact.text", [_state_key(s)]))
			ui.toast(tr("toast.pact") % _state_name(s))
			_coalition_tick(now_s())
			_refresh_ui()
			_autosave()
		"swap":
			var why := _swap_reason(s)
			if why != "":
				ui.toast(why)
				return
			_swap = {"state": s, "give": [], "get": []}
			ui.close_modal()
			_open_tab("")
			ui.toast(tr("swap.pick") % _state_name(s))
		"call":
			if not _can_call(s):
				ui.toast(tr("call.cant"))
				return
			war["called_%d" % s] = 1
			_opinion_add(s, -5.0)
			sfx.play("warn")
			ui.toast(tr("toast.ally_called") % _state_name(s))
			_refresh_ui()
		"ally":
			if _ally_reason(s) != "":
				ui.toast(_ally_reason(s))
				return
			allies.append(s)
			sim.player_allies[s] = true
			_stat("alliances")
			sfx.play("seal")
			map_view.burst(int(sim.states[s]["capital_id"]), map_view.state_color(s), true)
			_post(L.pack("inbox.alliance.title", [_state_key(s)]), L.pack("inbox.alliance.text", [_state_key(s)]))
			ui.toast(tr("toast.alliance") % _state_name(s))
			_refresh_ui()
			_autosave()
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
			_stat("gifts")
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
	var lira: int = commanders.army_of("cmd_lira") if _cmd_level("cmd_lira") > 0 else -1
	for a in _player_armies():
		var missing: int = int(a["max_str"]) - int(a["str"])
		if missing <= 0:
			continue
		var sp := speed
		if int(a["id"]) == lira:
			sp *= 1.0 + _cmd_v("cmd_lira", 0) / 100.0  # Captain Lira: the «b_Командир» term of the refill (03 §9.2)
		var heal := mini(missing, int(float(a["max_str"]) * dt * sp / REFILL_FULL_SEC[dl]))
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
	var t: int = int(INF_TRAIN_SEC[dl] * slots * maxf(0.25, (1.0 - 0.05 * research.level("drill")) * (1.0 - econ.factory_pct() / 100.0)))
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
	_stat("trainings")
	_normalize_armies()
	map_view.burst(cap, MapView.C_PLAYER, true)
	sfx.play("fanfare")
	ui.toast(tr("toast.army_ready"))
	_autosave()


func _open_hand_picker() -> void:
	var open: Array = ["attack"]
	for c in SLOT_CARDS:
		if econ.dev_level() >= int(CARD_DL.get(c, 1)):
			open.append(c)
	var chosen: Array = _hand_display().slice(1)
	ui.show_hand_picker(open, chosen, _hand_slots(), func(c: String):
		if c == "attack":
			ui.toast(tr("hand.attack_fixed"))
			return
		var cur: Array = _hand_display().slice(1)
		if cur.has(c):
			if cur.size() <= 1:
				ui.toast(tr("hand.min_one"))
				return
			cur.erase(c)
		elif cur.size() >= _hand_slots():
			ui.toast(tr("hand.full") % _hand_slots())
			return
		else:
			cur.append(c)
		var ordered: Array = []
		for k in SLOT_CARDS:  # keep the slots in the canonical order (the oil is paid left to right, 03 §12.1)
			if cur.has(k):
				ordered.append(k)
		hand_pick = ordered
		sfx.play("tap")
		_show_hand()
		_autosave()
		_open_hand_picker()
		if tab == "army":
			ui.show_armies(_army_items(now_s())))


# ---------------------------------------------------------------------- «Летопись державы» (canon §12.5, 07 §7)

## The live measures of the Chronicle on top of the game's counters.
func _chronicle_values() -> Dictionary:
	var v: Dictionary = stats.duplicate()
	var hexes := _player_hexes()
	v["@hexes"] = hexes
	var land := _land_count()
	v["@half_world"] = 1 if land >= 160 and hexes * 2 >= land else 0
	v["@dl"] = econ.dev_level()
	var fort8 := 0
	var veins := 0
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and c["controller"] == Types.PLAYER:
			if int(c["fort"]) >= 8:
				fort8 += 1
			if c["kind"] == "raivite_vein":
				veins += 1
	v["@fort8"] = fort8
	v["@veins"] = veins
	var unlock: Dictionary = Cases.data().get("commander_unlock_shards", {})
	var det := 0
	for cmd in Chronicle.DET_COMMANDERS:
		if int(cases.shards.get(cmd, 0)) >= int(unlock.get(String(Cases.commander(cmd).get("rarity", "common")), 10)):
			det += 1
	v["@cmd_det"] = det
	var top := 0
	for id in Commanders.PASSIVES:
		top = maxi(top, _cmd_level(id))
	v["@cmd_level"] = top
	return v


## Counts the goals and announces the new ones — not in a battle or a ceremony (07 §7.4: the toast waits).
func _chronicle_tick() -> void:
	if mode not in [Mode.MAP, Mode.WAR]:
		return
	for code in chronicle.update(_chronicle_values()):
		ui.toast(tr("chr.toast") % tr("chr." + String(code)))
	hud.set_book(chronicle.claimable())


func _open_chronicle() -> void:
	var rows: Array = []
	for row in Chronicle.LIST:
		var code: String = row[0]
		var cos: String = row[5]
		var reward := "+%d 💎" % int(row[4])
		if cos != "":
			var co: Dictionary = Cases.cosmetic(cos)
			reward += " · «%s»" % String(co.get("name_en" if Cases.is_english() else "name", cos))
		rows.append({"code": code, "chapter": row[1], "name": tr("chr." + code), "need": int(row[3]),
			"desc": tr("chr." + code + ".d"), "progress": chronicle.progress(code), "reward": reward,
			"state": "soon" if bool(row[6]) else ("claimed" if chronicle.claimed.has(code) else ("claim" if chronicle.can_claim(code) else "open"))})
	ui.show_chronicle({"done": chronicle.reached.size(), "total": Chronicle.LIST.size(), "rows": rows},
		func(code: String): _claim_chronicle(code))


func _claim_chronicle(code: String) -> void:
	var r: Array = chronicle.claim(code)
	if r.is_empty():
		return
	econ.res["raivite"] = int(econ.res["raivite"]) + int(r[0])
	if String(r[1]) != "":
		cases.owned_cosmetics[String(r[1])] = true
	sfx.play("fanfare")
	ui.toast(tr("chr.claimed") % [tr("chr." + code), int(r[0])])
	hud.set_book(chronicle.claimable())
	_econ_tick()
	_autosave()
	_open_chronicle()


# ---------------------------------------------------------------------- commanders (canon §8.4, 04 §15)

func _cmd_rarity(id: String) -> String:
	return String(Cases.commander(id).get("rarity", "common"))


func _cmd_level(id: String) -> int:
	return commanders.level(id, _cmd_rarity(id), int(cases.shards.get(id, 0)))


func _cmd_owned_count() -> int:
	var n := 0
	for id in Commanders.PASSIVES:
		if _cmd_level(id) > 0:
			n += 1
	return n


func _cmd_block(id: String) -> String:
	return commanders.block_reason(id, _cmd_rarity(id), int(cases.shards.get(id, 0)), int(econ.res["gold"]), econ.dev_level())


func _cmd_upgradable() -> int:
	var n := 0
	for id in Commanders.PASSIVES:
		if _cmd_block(id) == "":
			n += 1
	return n


## Sergeant Bram comes with the first war of the tutorial (04 §15.3) — once; an old save gets him too.
func _grant_bram() -> void:
	if stats.has("bram_given"):
		return
	stats["bram_given"] = 1
	cases.shards["cmd_bram"] = int(cases.shards.get("cmd_bram", 0)) + int(Commanders.UNLOCK["common"])


## A passive's value as text: «+9,7%», «+7,4 п.п.», «×1,74».
func _cmd_value_text(p: Array, lvl: int) -> String:
	var v := Commanders.value(float(p[1]), float(p[2]), lvl)
	var num := ("%.2f" if String(p[3]) == "x" else "%.1f") % v
	if not Cases.is_english():
		num = num.replace(".", ",")
	match String(p[3]):
		"%":
			return "+%s%%" % num
		"pp":
			return tr("cmdr.pp") % num
		"x":
			return "×" + num
	return ""


## One line per part of the passive at a level: «Сила Пехоты: +9,7%».
func _cmd_passive_lines(id: String, lvl: int) -> Array:
	var out: Array = []
	for p in Commanders.PASSIVES.get(id, []):
		var nm := tr("cmdr.p." + String(p[0]))
		out.append(nm if String(p[3]) == "" else "%s: %s" % [nm, _cmd_value_text(p, lvl)])
	return out


## The collection (04 §15.7): albums of a 3 × N grid — portrait, level «ур. 9/16», shards to the next level.
func _open_commanders() -> void:
	var dl: int = econ.dev_level()
	ui.set_portrait_era(dl)
	var albums: Array = []
	for a in Commanders.ALBUMS:
		var cards: Array = []
		var full := true
		for id in a[1]:
			var r := _cmd_rarity(id)
			var total := int(cases.shards.get(id, 0))
			var lvl := _cmd_level(id)
			full = full and lvl > 0
			var c: Array = commanders.next_cost(id, r, total)
			var card := {"id": id, "name": Cases.commander_name(id), "rarity": r, "level": lvl, "cap": Commanders.level_cap(dl),
				"can": _cmd_block(id) == ""}
			if lvl <= 0:
				card["shards"] = [total, int(Commanders.UNLOCK[r])]
				card["src"] = tr("cmdr.src." + String(id))
			elif not c.is_empty():
				card["shards"] = [commanders.free_shards(id, r, total), int(c[0])]
			cards.append(card)
		albums.append({"name": tr("cmdr.album." + String(a[0])), "full": full, "cards": cards})
	ui.show_commanders({"title": tr("cmdr.collection") % [_cmd_owned_count(), Commanders.PASSIVES.size()], "albums": albums},
		func(id: String): _open_commander(id))


## The commander card (04 §15.7): portrait, biography, the passive by level, «Повысить», sources, «Цель».
func _open_commander(id: String, mood := "") -> void:
	var r := _cmd_rarity(id)
	var total := int(cases.shards.get(id, 0))
	var lvl := _cmd_level(id)
	var dl: int = econ.dev_level()
	var table: Array = []
	var shown: Array = Commanders.TABLE_LEVELS.duplicate()
	if lvl > 0 and not shown.has(lvl):
		shown.append(lvl)
		shown.sort()
	for l in shown:
		var vals := PackedStringArray()
		for p in Commanders.PASSIVES[id]:
			if String(p[3]) != "":
				vals.append(_cmd_value_text(p, l))
		table.append([l, " / ".join(vals)])
	var info := {"id": id, "name": Cases.commander_name(id), "rarity": r, "rarity_name": tr("cmdr.rarity." + r), "level": lvl,
		"cap": Commanders.level_cap(dl), "bio": tr("cmdr.bio." + id), "passive": _cmd_passive_lines(id, maxi(1, lvl)),
		"table": table, "src": tr("cmdr.src." + id), "album": tr("cmdr.album." + Commanders.album_of(id)), "mood": mood}
	var block := _cmd_block(id)
	var c: Array = commanders.next_cost(id, r, total)
	if lvl <= 0:
		info["button"] = tr("cmdr.locked") % [total, int(Commanders.UNLOCK[r])]
	elif c.is_empty():
		info["button"] = tr("cmdr.max")
	elif block == "dl":
		info["button"] = tr("cmdr.need_dl") % int(c[2])
	else:
		info["button"] = tr("cmdr.upgrade") % [int(c[0]), GameUI.fmt_num(int(c[1]))]
		info["shards"] = [commanders.free_shards(id, r, total), int(c[0])]
	info["can"] = block == ""
	var on_target := Callable()
	if r in ["epic", "legendary"] and not Commanders.maxed(r, total):
		info["target"] = cases.target_commander == id
		on_target = func(): _set_cmd_target(id)
	ui.show_commander(info, func(): _upgrade_commander(id), on_target, func(): _open_commanders())


func _upgrade_commander(id: String) -> void:
	var block := _cmd_block(id)
	if block != "":
		ui.toast(tr("cmdr.why." + block))
		return
	var gold: int = commanders.upgrade(id, _cmd_rarity(id), int(cases.shards.get(id, 0)), int(econ.res["gold"]), econ.dev_level())
	econ.res["gold"] = int(econ.res["gold"]) - gold
	sfx.play("fanfare")
	ui.toast(tr("cmdr.leveled") % [Cases.commander_name(id), _cmd_level(id)])
	_econ_tick()
	_autosave()
	_open_commander(id, "smile")


## A passive's value (the part `i`) at the commander's level, in its units (percent, points or a factor).
func _cmd_v(id: String, i: int) -> float:
	var p: Array = Commanders.PASSIVES[id][i]
	return Commanders.value(float(p[1]), float(p[2]), maxi(1, _cmd_level(id)))


func _cmd_pm(id: String, i: int) -> int:
	return int(_cmd_v(id, i) * 10.0)


func _touches_any(hex: int, hexes: Array) -> bool:
	if hexes.has(hex):
		return true
	for n in sim.neighbors[hex]:
		if n >= 0 and hexes.has(n):
			return true
	return false


const CMD_KEYS := ["cmd_atk", "cmd_def", "cmd_home", "cmd_forts", "cmd_port", "cmd_wedge", "cmd_breach", "cmd_forms"]

## Writes the commanders' passives onto the player's armies (04 §15.2; the battle reads the cmd_* fields) and
## returns the battle-wide ones for the offensive's options — those of a commander whose army takes part.
func _apply_commanders() -> Dictionary:
	var ids: Array = []
	for a in armies:
		for k in CMD_KEYS:
			a.erase(k)
		if a["side"] == Types.PLAYER:
			ids.append(int(a["id"]))
	commanders.keep_armies(ids)
	var opts := {}
	for army_id in commanders.assigned:
		var id: String = commanders.assigned[army_id]
		var a := _army_by_id(int(army_id))
		if a.is_empty() or _cmd_level(id) <= 0:
			continue
		match id:
			"cmd_bram":  # infantry strength on the infantry share of the army
				var v := _cmd_pm(id, 0) * int(a.get("infantry", 1000)) / 1000
				a["cmd_atk"] = v
				a["cmd_def"] = v
			"cmd_olm":
				a["cmd_forts"] = _cmd_pm(id, 0)
			"cmd_vik", "cmd_hawk", "cmd_vance":  # army strength: attack and defence
				a["cmd_atk"] = _cmd_pm(id, 1)
				a["cmd_def"] = _cmd_pm(id, 1)
				if id == "cmd_hawk":
					opts["air_pm"] = _cmd_pm(id, 0)
				if id == "cmd_vance":
					opts["energy_bonus"] = 1
			"cmd_vega":
				a["cmd_wedge"] = _cmd_pm(id, 0)
			"cmd_rai":
				a["cmd_forms"] = _cmd_pm(id, 0)
				opts["regen_pm"] = _cmd_pm(id, 1)
			"cmd_seir":
				a["cmd_port"] = _cmd_pm(id, 1)
				opts["landing_discount"] = 1
			"cmd_frey":
				a["cmd_home"] = _cmd_pm(id, 0)
			"cmd_irma":
				a["cmd_atk"] = _cmd_pm(id, 1)
				a["cmd_breach"] = true
	return opts


## « ★» after a forecast when a commander's attack passive works in this attack (04 §15.6: the effect is seen).
func _cmd_mark(army_ids: Array, target: int) -> String:
	for id in army_ids:
		var a := _army_by_id(int(id))
		if a.is_empty():
			continue
		if int(a.get("cmd_atk", 0)) > 0 or int(a.get("cmd_forms", 0)) > 0 or (int(a.get("cmd_wedge", 0)) > 0 and army_ids.size() > 1):
			return " ★"
		if int(a.get("cmd_forts", 0)) > 0 and int(sim.cells[target]["fort"]) >= 1:
			return " ★"
	return ""


## What a commander would give this army now, in Might % (the «Рекомендуем» order, 04 §15.6).
func _cmd_score(id: String, a: Dictionary) -> float:
	match id:
		"cmd_bram":
			return _cmd_v(id, 0) * float(a.get("infantry", 1000)) / 1000.0
		"cmd_vik", "cmd_seir", "cmd_irma", "cmd_hawk", "cmd_vance":
			return _cmd_v(id, 1) + (2.0 if id in ["cmd_hawk", "cmd_vance"] else 0.0)
		"cmd_frey":
			return _cmd_v(id, 0) if int(sim.cells[int(a["hex"])]["owner"]) == Types.PLAYER else 0.0
		"cmd_olm", "cmd_vega", "cmd_rai":
			return _cmd_v(id, 0) * 0.6
	return 1.0


## The commander picker of an army (04 §15.6): the recommended one first, a commander of another army marked
## with its number, «Снять» when one leads it.
func _open_cmd_picker(army_id: int) -> void:
	var a := _army_by_id(army_id)
	if a.is_empty() or mode == Mode.BATTLE:
		return
	var rows: Array = []
	var nums := {}
	var pa := _player_armies()
	for i in pa.size():
		nums[int(pa[i]["id"])] = i + 1
	for id in Commanders.PASSIVES:
		if _cmd_level(id) <= 0:
			continue
		var other: int = commanders.army_of(id)
		rows.append({"id": id, "name": Cases.commander_name(id), "rarity": _cmd_rarity(id), "level": _cmd_level(id),
			"lines": _cmd_passive_lines(id, _cmd_level(id)), "score": _cmd_score(id, a),
			"busy": tr("cmdr.in_army") % int(nums.get(other, 0)) if other >= 0 and other != army_id else "",
			"here": other == army_id})
	# the free ones first, then those of other armies; «Рекомендуем» goes to the best free one
	rows.sort_custom(func(x, y): return float(x["score"]) - (100.0 if String(x["busy"]) != "" else 0.0) > float(y["score"]) - (100.0 if String(y["busy"]) != "" else 0.0))
	if not rows.is_empty() and String(rows[0]["busy"]) == "" and not bool(rows[0]["here"]):
		rows[0]["best"] = true
	var title := tr("cmdr.pick_title") % int(nums.get(army_id, 1))
	ui.show_cmd_picker(title, rows, func(id: String): _assign_commander(army_id, id),
		func(): _unassign_commander(army_id) if commanders.cmd_of(army_id) != "" else ui.close_modal())


func _assign_commander(army_id: int, id: String) -> void:
	var other: int = commanders.army_of(id)
	if other >= 0 and other != army_id:
		var nums := {}
		var pa := _player_armies()
		for i in pa.size():
			nums[int(pa[i]["id"])] = i + 1
		ui.show_choice(tr("cmdr.move_title") % Cases.commander_name(id), [tr("cmdr.move_text") % [int(nums.get(other, 0)), int(nums.get(army_id, 0))]], [
			[tr("cmdr.move_yes"), Color(0.2, 0.55, 0.3), func(): _do_assign(army_id, id)],
			[tr("ui.cancel"), Color(0.3, 0.33, 0.42), func(): _open_cmd_picker(army_id)]])
		return
	_do_assign(army_id, id)


func _do_assign(army_id: int, id: String) -> void:
	commanders.assign(army_id, id)
	ui.close_modal()
	sfx.play("tap")
	ui.toast(tr("cmdr.assigned") % Cases.commander_name(id))
	_autosave()
	_open_tab("army")


func _unassign_commander(army_id: int) -> void:
	commanders.unassign(army_id)
	ui.close_modal()
	_autosave()
	_open_tab("army")


## «Поставить Целью» (09): the Royal case's target — the toast says so and the card refreshes.
func _set_cmd_target(id: String) -> void:
	if cases.set_target(id):
		ui.toast(tr("cmdr.target_set") % Cases.commander_name(id))
		_autosave()
	_open_commander(id)


# ---------------------------------------------------------------------- the profile (10 §4.23)

const CHAPTER_NAME_KEYS := ["", "profile.ch1", "profile.ch2", "profile.ch3", "profile.ch4"]

## The realm's profile: flag, name, DL, hexes, the chapter's share of the map, the Arena league, «Командиры 7/12»,
## «Летопись 23/40» and the 3 latest achievements; the buttons lead to the book, the collection and the settings.
func _open_profile() -> void:
	var land := _land_count()
	var hexes := _player_hexes()
	var recent: Array = []
	for code in chronicle.recent(3):
		var row: Array = Chronicle.LIST[Chronicle.index_of(String(code))]
		recent.append({"name": tr("chr." + String(code)), "chapter": tr("chr.ch." + String(row[1]))})
	var info := {"name": _state_name(Types.PLAYER), "dl": econ.dev_level(), "hexes": hexes,
		"chapter": tr(CHAPTER_NAME_KEYS[clampi(chapter, 1, CHAPTER_NAME_KEYS.size() - 1)]),
		"map_pct": roundi(100.0 * hexes / maxf(1.0, float(land))),
		"commanders": [_cmd_owned_count(), Commanders.PASSIVES.size()],
		"chronicle": [chronicle.reached.size(), Chronicle.LIST.size()], "recent": recent,
		"flag": flag, "book_badge": chronicle.claimable(), "cmd_dot": _cmd_upgradable() > 0, "wins": int(stats.get("peace_wins", 0))}
	ui.show_profile(info, {
		"chronicle": func(): _open_chronicle(),
		"commanders": func(): _open_commanders(),
		"settings": func():
			ui.close_modal()
			_show_settings(),
		"soon": func(): ui.toast(tr("profile.soon")),
		"flag": func(): _open_flag_editor(),
		"name": func(): _open_name_editor(func(): _open_profile()),
	})


## Colour schemes of the FTUE flag wizard: [field 1, field 2, emblem] (FlagView palettes; 13 white, 16 gold, 17 yellow).
var _flag_wizard_done := Callable()  # what the FTUE does after the flag wizard
const FLAG_SCHEMES := [[0, 13, 16], [5, 13, 16], [2, 14, 13], [7, 11, 13], [4, 13, 16], [1, 13, 17], [8, 13, 16], [14, 6, 13], [3, 12, 17], [11, 7, 16]]


func _flag_seed() -> int:
	return int(installed_at) if int(installed_at) > 0 else 20261004


## The 3-tap flag (canon §14.3, 10 §4.23): 6 divisions → 6 emblems → 6 colour schemes, all from the account's seed,
## then the flag with «Готово» and «Случайно»; the full constructor stays in the profile.
func _open_flag_wizard(step: int, draft: Dictionary, on_done: Callable) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = _flag_seed() + step
	var opts: Array = []
	match step:
		0, 1:
			var pool: Array = (FlagView.DIVISIONS if step == 0 else FlagView.EMBLEMS).duplicate()
			for i in range(pool.size() - 1, 0, -1):
				var j := rng.randi_range(0, i)
				var t: Variant = pool[i]
				pool[i] = pool[j]
				pool[j] = t
			for k in 6:
				var f := draft.duplicate()
				f["div" if step == 0 else "em"] = pool[k]
				opts.append(f)
		2:
			var order: Array = range(FLAG_SCHEMES.size())
			for i in range(order.size() - 1, 0, -1):
				var j := rng.randi_range(0, i)
				var t: Variant = order[i]
				order[i] = order[j]
				order[j] = t
			for k in 6:
				var sc: Array = FLAG_SCHEMES[order[k]]
				var f := draft.duplicate()
				f["c1"] = sc[0]
				f["c2"] = sc[1]
				f["ec"] = sc[2]
				opts.append(f)
		_:
			opts = [draft]
	_flag_wizard_done = on_done
	ui.show_flag_wizard(step, opts,
		func(i: int): _open_flag_wizard(step + 1, opts[i], on_done),
		func(): _open_flag_wizard(3, FlagView.random_flag(randi()), on_done),
		func(): _finish_flag_wizard(draft))


## «Готово» of the wizard: the flag goes on the HUD and the banners, then the FTUE tour goes on.
func _finish_flag_wizard(draft: Dictionary) -> void:
	flag = draft
	hud.set_flag(flag)
	map_view.set_flag(flag)
	sfx.play("seal")
	ui.close_modal()
	_autosave()
	var done := _flag_wizard_done
	_flag_wizard_done = Callable()
	if done.is_valid():
		done.call()


const REALM_NAMES := ["realm.n1", "realm.n2", "realm.n3", "realm.n4", "realm.n5", "realm.n6", "realm.n7", "realm.n8",
	"realm.n9", "realm.n10", "realm.n11", "realm.n12", "realm.n13", "realm.n14", "realm.n15", "realm.n16"]
const REALM_NAME_MAX := 20
var _name_done := Callable()


## Six name ideas from the account seed (and a shift for the die).
func _realm_name_ideas(shift: int) -> Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = _flag_seed() + 7 * shift
	var pool: Array = REALM_NAMES.duplicate()
	for i in range(pool.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var t: Variant = pool[i]
		pool[i] = pool[j]
		pool[j] = t
	var out: Array = []
	for k in 6:
		out.append(tr(String(pool[k])))
	return out


## «Название державы» (canon §14.3, 2:30–3:30): a field and 6 ideas; the name shows on the profile, the
## diplomacy and the war bar.
func _open_name_editor(on_done: Callable, shift := 0) -> void:
	_name_done = on_done
	ui.show_name_editor(realm_name if realm_name != "" else "", _realm_name_ideas(shift), REALM_NAME_MAX,
		func(n: String): _finish_name_editor(n),
		func(): _open_name_editor(on_done, shift + 1))


## A name of 2–20 characters (spaces trimmed, line breaks dropped); an empty one keeps «Ваша держава».
static func clean_realm_name(n: String) -> String:
	var t := n.replace("\n", " ").replace("\t", " ").strip_edges()
	while t.contains("  "):
		t = t.replace("  ", " ")
	return t.substr(0, REALM_NAME_MAX)


func _finish_name_editor(n: String) -> void:
	var t := clean_realm_name(n)
	if t.length() == 1:
		ui.toast(tr("realm.too_short"))
		return
	realm_name = t
	ui.close_modal()
	_autosave()
	var done := _name_done
	_name_done = Callable()
	if done.is_valid():
		done.call()


## The flag constructor (10 §4.23): every change shows at once and is kept with «Готово»; the HUD crest follows.
func _open_flag_editor(draft: Dictionary = {}) -> void:
	var f: Dictionary = flag.duplicate() if draft.is_empty() else draft
	ui.show_flag_editor(f, cases.owned_cosmetics,
		func(nf: Dictionary): _open_flag_editor(nf),
		func(): _open_flag_editor(FlagView.random_flag(randi())),
		func():
			flag = f
			hud.set_flag(flag)
			map_view.set_flag(flag)
			sfx.play("seal")
			_autosave()
			_open_profile())


# ---------------------------------------------------------------------- «Державный патент» (canon §15.7, 09 §9.13)

## Applies the subscription's perks while it is active and pays its weekly key and monthly frame.
func _patent_tick(now: int) -> void:
	var on: bool = patent.active(now)
	econ.bonus_builders = 1 if on else 0  # a task already started finishes; new ones need a free builder
	deposits.bonus_convoys = 1 if on else 0
	Economy.free_finish = Patent.FREE_FINISH_SEC if on else Economy.FREE_FINISH_SEC
	if not on:
		return
	if patent.weekly_key(now):
		cases.royal_keys += 1
		_post("inbox.patent_key.title", "inbox.patent_key.text")
	if patent.month_frame(now):
		cases.owned_cosmetics["cos_frame_patent_month"] = true
	# income is collected automatically (05 §5.4)
	if not econ.stock.is_empty():
		var got: Dictionary = econ.collect_all()
		stats["gold_collected"] = int(stats.get("gold_collected", 0)) + int(got.get("gold", 0))
		econ.collect_veins()
		if not got.is_empty() and now - _collect_counted >= 1800:  # counts for «Приказы дня» like a tap
			_collect_counted = now
			_stat("collects")


func _open_patent() -> void:
	var now := now_s()
	ui.show_patent({"active": patent.active(now), "days_left": patent.days_left(now), "trial": patent.trial_eligible(),
		"can_buy": _payments_enabled(), "price": "$7.99", "trial_price": "$1.99"},
		func(sku: String): _on_buy_sku(sku),
		func(): ui.toast(tr("patent.restored")))


func _claim_patent_daily() -> void:
	if patent.claim_daily(now_s()):
		econ.res["raivite"] = int(econ.res["raivite"]) + Patent.DAILY_RAIVITE
		sfx.play("coin")
		ui.toast(tr("toast.patent_daily") % Patent.DAILY_RAIVITE)
		_autosave()
	_open_tab("world")


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
	# the subscriber gets the reward at once, in the same caps (09 §9.13.1)
	ui.toast(tr("toast.patent_reward") if patent.active(now_s()) else tr("toast.test_ad_reward"))
	_intro_offer_check(day)
	return true


## The intro Patent offer (09 §9.13.2): on the 3rd rewarded video of a day, from D2, once a day, only to those who
## can still take it and only where payments work.
func _intro_offer_check(day: int) -> void:
	if not _payments_enabled() or patent.active(now_s()) or not patent.trial_eligible() or intro_offer_day == day:
		return
	if day < installed_at / 86400 + 1:
		return
	var total := 0
	for k in ad_counts:
		var rec: Array = ad_counts[k]
		if int(rec[0]) == day:
			total += int(rec[1])
	if total != 3:
		return
	intro_offer_day = day
	_show_intro_offer.call_deferred()


func _show_intro_offer() -> void:
	ui.show_choice(tr("patent.offer_title"), [tr("patent.offer_line") % "$1.99", tr("patent.trial") % ["$1.99", "$7.99"]], [
		[tr("patent.offer_more"), Color(0.75, 0.55, 0.12), func(): _open_patent()],
		[tr("patent.offer_later"), Color(0.3, 0.33, 0.4), func(): ui.close_modal()],
	])


func _army_items(now: int) -> Array:
	var items: Array = []
	var i := 1
	for a in _player_armies():
		items.append({"id": a["id"], "name": tr("army.name") % i, "str": int(round(float(a["str"]) / 1000.0)), "max": int(round(float(a["max_str"]) / 1000.0)),
			"slots": int(a.get("slots", 3)),
			"upkeep": roundi(int(a["max_str"]) / 10000.0 * (1.5 if not war.is_empty() else 1.0) * (1.0 - 0.03 * research.level("thrift"))),
			"refilling": int(a["str"]) < int(a["max_str"]), "cmd": commanders.cmd_of(int(a["id"])),
			"cmd_rarity": _cmd_rarity(commanders.cmd_of(int(a["id"]))) if commanders.cmd_of(int(a["id"])) != "" else "",
			"cmd_free": ftue == 0 and _cmd_owned_count() > 0})
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
	if ftue == 0:
		items.append({"id": -2, "name": tr("hand.title"), "hand": _hand_display()})
		items.append({"id": -3, "name": tr("cmdr.title"), "commanders": [_cmd_owned_count(), Commanders.PASSIVES.size()], "dot": _cmd_upgradable() > 0})
	return items


func _on_army_action(id: int, kind: String) -> void:
	if kind == "hand":
		_open_hand_picker()
		return
	if kind == "commanders":
		_open_commanders()
		return
	if kind == "cmd":
		_open_cmd_picker(id)
		return
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
	_stat("upgrades")
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
		bp.gain("defense", now_s())
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
	_ultimatum_rolls(now)
	_coalition_tick(now)
	_subsidy_tick(now)
	_separate_offer_tick(now)
	if war.is_empty():
		return
	if war.has("strike_at"):
		var left := int(war["strike_at"]) - now
		if left <= 0 and mode in [Mode.MAP, Mode.WAR]:
			_resolve_strike()
		elif left > 0:
			map_view.strike_arrow(int(war["strike_from"]), int(war["strike_hex"]), "⚔ " + GameUI.fmt_time(left))
	_member_strikes(now)
	if war.has("started") and now - int(war["started"]) >= WAR_CAP_SEC and mode in [Mode.MAP, Mode.WAR]:
		_war_cap()
		return
	_peace_offer()
	_allies_tick(now)


## Archetype ultimatums (canon §10.4): once a day each neighbour that is stronger than the player rolls its chance
## (Wolf 35%, Raven 25% while the player is at war, Fox and Owl 10%, Turtle 5%). New neighbours wait 12 h.
const ULT_CHANCE := {"wolf": 35, "raven": 25, "fox": 10, "owl": 10, "turtle": 5}


func _ultimatum_rolls(now: int) -> void:
	if ultimatum_at >= 0 or not ultimatum.is_empty() or not war.is_empty() or mode != Mode.MAP or ftue != 0:
		return
	for s in _ai_states():
		if not ult_check.has(s):
			ult_check[s] = now + (12 * 3600 if _native_chapter(s) >= 2 else 6 * 3600)
			continue
		if now < int(ult_check[s]):
			continue
		ult_check[s] = now + 86400
		if _truce_left(s) > 0 or _pact_left(s) > 0 or _ai_power(s) <= _player_power():
			continue
		var chance: int = int(ULT_CHANCE.get(String(sim.states[s]["archetype"]), 10)) + (10 if bool(sim.states[s].get("hegemon", false)) else 0)
		var roll: int = _roll("ult:%d:%d" % [s, now / 86400], 100)
		if roll < chance:
			_issue_ultimatum(now, s)
			return


## Field power: the player's armies vs what the AI state would field at its DL (2 armies, Wolf +1, Turtle −1).
func _player_power() -> int:
	var p := 0
	for a in _player_armies():
		p += int(a["max_str"])
	return p


func _ai_power(s: int) -> int:
	var n: int = 2 + int({"wolf": 1, "turtle": -1}.get(String(sim.states[s]["archetype"]), 0))
	return n * Armies.infantry_army(0, s, 0, 3, int(sim.states[s]["dev_level"]))["max_str"]


func _issue_ultimatum(now: int, state: int = MapGen.BARONS) -> void:
	if state == MapGen.BARONS:
		ultimatum_at = -1
	var core := MapGen.core_of(sim, Types.PLAYER)
	var best := -1
	for c in sim.cells:
		if c["owner"] == Types.PLAYER and Types.is_passable(c) and not core.has(c["id"]) and _touches_owner(c["id"], state):
			if best < 0 or int(c["value"]) > int(sim.cells[best]["value"]):
				best = c["id"]
	if best < 0:
		return
	var tribute := 8 * maxi(60, int(econ.gross_per_hour(sim).get("gold", 0)))
	ultimatum = {"state": state, "hex": best, "tribute": tribute, "deadline": now + 4 * 3600}
	_post(L.pack("inbox.ultimatum.title", [_state_key(state)]), L.pack("inbox.ultimatum.text", [_cell_key(best), tribute]))
	sfx.play("warn")
	sfx.haptic(60)
	rig.focus(map_view.cell_world(best))
	_show_ultimatum()


func _show_ultimatum() -> void:
	ui.show_ultimatum(_state_name(int(ultimatum["state"])), _cell_name(int(ultimatum["hex"])), int(ultimatum["tribute"]),
		econ.res["gold"] >= int(ultimatum["tribute"]), int(ultimatum["deadline"]) - now_s(),
		_answer_ultimatum.bind("accept"), _answer_ultimatum.bind("pay"), _answer_ultimatum.bind("refuse"),
		_leader_portrait(int(ultimatum["state"])), map_view.state_color(int(ultimatum["state"])))


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
			war["ult_refused"] = 1
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
	var by := int(war.get("strike_by", war["enemy"]))
	war.erase("strike_at")
	war.erase("strike_hex")
	war.erase("strike_from")
	war.erase("strike_by")
	map_view.strike_arrow(-1, -1, "")
	if int(stats.get("defenses", 0)) >= 1:
		_auto_defense(hex, by)
		return
	war["battles"] = clampi(int(war["battles"]) + 2, -10, 10)
	_stat("defenses")
	bp.gain("defense", now_s())
	var gold := int(maxi(60, int(econ.gross_per_hour(sim).get("gold", 0))) / 2.0)
	econ.add_resources({"gold": gold})
	map_view.burst(hex, MapView.C_PLAYER, true)
	map_view.floater(hex, tr("floater.repelled_short"), Color(0.75, 0.85, 1.0))
	sfx.play("repelled")
	var msg := L.pack("inbox.defense.text", [_state_key(by), _cell_key(hex), gold])
	_post("inbox.defense.title", msg)
	ui.toast(L.t(msg))
	_refresh_ui()
	_autosave()


## The AI asks for peace when the player holds the front (canon §10.4): Fox ≥60%, Owl and Turtle ≥65%,
## Raven ≥70%, Wolf ≥75% of control. Once per war; the conference opens with the recommended package.
const PEACE_AT := {"fox": 60, "owl": 65, "turtle": 65, "raven": 70, "wolf": 75}


func _peace_offer() -> void:
	if war.has("offered") or mode != Mode.WAR or ftue != 0 or ui.has_modal():
		return
	var enemy: int = war["enemy"]
	var ws := War.war_score(sim, war)
	var need: int = PEACE_AT.get(String(sim.states[enemy]["archetype"]), 70)
	if int(ws["control"]) < need or float(ws["score"]) < 10.0:
		return
	war["offered"] = 1
	sfx.play("seal")
	_post(L.pack("inbox.peace_offer.title", [_state_key(enemy)]), L.pack("inbox.peace_offer.text", [_state_key(enemy), int(ws["control"])]))
	ui.show_info(tr("peace_offer.title") % _state_name(enemy), [
		tr("peace_offer.text") % [_state_name(enemy), int(ws["control"])],
		"%s — «%s»" % [tr(String(LEADERS.get(enemy, ["", "", ""])[0])) if LEADERS.has(enemy) else _state_name(enemy), tr("peace_offer.quote")],
	], tr("peace_offer.go"), func():
		ui.close_modal()
		_open_peace())


## Auto-defense (canon §9.11): the AI's 90 s offensive is played out at once on the same engine; the player's
## armies, garrisons, forts and towers defend by themselves. Hexes it takes become occupied; a held line pays
## 30 min of gold income. The player's core is never a target.
func _auto_defense(hex: int, by := -1) -> void:
	var enemy: int = by if by >= 0 and War.sides(war).has(by) else int(war["enemy"])
	_ensure_armies_for(enemy)
	_stop_marches()
	for a in armies:
		a["routed"] = false
		a["hold"] = false
		if a["side"] != Types.PLAYER:
			a["str"] = a["max_str"]
	_normalize_armies()
	_apply_commanders()  # the player's commanders defend too (the battle-wide ones are the attacker's)
	var b := Battle.new(sim, armies, {"attacker": enemy, "defender": Types.PLAYER, "ai_energy_mult": 0, "cards": HAND})
	var bot := BattleAI.new(enemy)
	while not b.over:
		bot.think(b)
		b.step()
	var res: Dictionary = b.result()
	var taken: Array = res["captured"]
	for a in armies:
		if a["side"] == Types.PLAYER and (a["routed"] or int(a["str"]) < int(a["max_str"]) / 10):
			a["str"] = maxi(int(a["str"]), int(a["max_str"]) / 10)
			a["routed"] = false
	_normalize_armies()
	map_view.sync_armies(armies, null)
	map_view.mark_dirty()
	if taken.is_empty():
		war["battles"] = clampi(int(war["battles"]) + 2, -10, 10)
		_stat("defenses")
		bp.gain("defense", now_s())
		var gold := int(maxi(60, int(econ.gross_per_hour(sim).get("gold", 0))) / 2.0)
		econ.add_resources({"gold": gold})
		map_view.burst(hex, MapView.C_PLAYER, true)
		map_view.floater(hex, tr("floater.repelled_short"), Color(0.75, 0.85, 1.0))
		sfx.play("repelled")
		var msg := L.pack("inbox.defense.text", [_state_key(enemy), _cell_key(hex), gold])
		_post("inbox.defense.title", msg)
		ui.toast(L.t(msg))
	else:
		war["battles"] = clampi(int(war["battles"]) - 2, -10, 10)
		for h in taken:
			map_view.smoke(int(h), 5.0, true)
		sfx.play("lost")
		var msg2 := L.pack("inbox.defense_lost.text", [_state_key(enemy), taken.size()])
		_post("inbox.defense_lost.title", msg2)
		ui.toast(L.t(msg2))
	_refresh_ui()
	_autosave()


## Every coalition member strikes too (06 §14.6): every 4 h of the war the next member that borders the player's
## land announces its own strike, in turn.
const MEMBER_STRIKE_SEC := 4 * 3600


func _member_strikes(now: int) -> void:
	if war.is_empty() or not war.has("coalition") or war.has("strike_at") or mode not in [Mode.MAP, Mode.WAR]:
		return
	if not war.has("member_strike_at"):
		war["member_strike_at"] = int(war.get("started", now)) + MEMBER_STRIKE_SEC
	if now < int(war["member_strike_at"]):
		return
	war["member_strike_at"] = now + MEMBER_STRIKE_SEC
	var sides := War.sides(war)
	var i0 := int(war.get("member_strike_i", 0))
	for k in sides.size():
		var sd: int = sides[(i0 + k) % sides.size()]
		var touching := false
		for c in sim.cells:
			if c["controller"] == Types.PLAYER and _touches_controller(c["id"], sd):
				touching = true
				break
		if not touching:
			continue
		war["member_strike_i"] = (i0 + k + 1) % sides.size()
		_ensure_armies_for(sd)
		_schedule_counter(sd)
		return


## After the player's offensive the AI answers with an announced counter-strike (canon §9.11): it aims at the
## hexes it lost first, else the most valuable non-core hex on the front.
func _schedule_counter(by := -1) -> void:
	if war.is_empty() or war.has("strike_at"):
		return
	# in a coalition war the member whose land was attacked answers (06 §14.6), else the leader
	var enemy: int = by if by >= 0 else _front()
	var core := MapGen.core_of(sim, Types.PLAYER)
	var best := -1
	var best_s := -1
	for c in sim.cells:
		if c["controller"] != Types.PLAYER or not Types.is_passable(c) or core.has(c["id"]) or not _touches_controller(c["id"], enemy):
			continue
		var s: int = int(c["value"]) + (10 if c["owner"] == enemy else 0)
		if s > best_s:
			best_s = s
			best = c["id"]
	if best < 0:
		return
	var from := best
	for n in sim.neighbors[best]:
		if n >= 0 and sim.cells[n]["controller"] == enemy:
			from = n
			break
	war["strike_hex"] = best
	war["strike_from"] = from
	war["strike_at"] = now_s() + STRIKE_WARN_SEC
	war["strike_by"] = enemy
	_post("inbox.counter.title", L.pack("inbox.counter.text", [_state_key(enemy), _cell_key(best), STRIKE_WARN_SEC / 60]))


func _touches_controller(id: int, side: int) -> bool:
	for n in sim.neighbors[id]:
		if n >= 0 and sim.cells[n]["controller"] == side:
			return true
	return false


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
	map_view.set_zoom(rig.zoom)
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
		elif a.begins_with("--dl="):  # the player's development level for screenshots (the residence level)
			econ._find_type("residence")["level"] = int(a.substr(5))
			_econ_tick()
			map_view.refresh_props()
		elif a.begins_with("--focus="):  # centre the camera on a hex: --focus=q,r[,zoom]
			var fp := a.substr(8).split(",")
			rig.focus(map_view.cell_world(sim.id_at(int(fp[0]), int(fp[1]))), float(fp[2]) if fp.size() > 2 else rig.zoom)
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
	if what == "pass":  # the War Pass screen at level 4 with a reward claimed
		bp.refresh(now_s())
		bp.add_xp(4600, now_s())
		bp.claim(1, "free")
		_open_pass()
		return
	if what == "chronicle":  # the Chronicle after a little play: a few goals reached, one to take
		stats["peaces"] = 3
		stats["peace_wins"] = 3
		stats["offensives"] = 12
		stats["camps"] = 7
		stats["colonized"] = 9
		_chronicle_tick()
		chronicle.claim("ach_first_peace")
		_open_chronicle()
		return
	if what == "blueprint":  # a research running with 3 trophy blueprints in store (the Development tab)
		econ.res["gold"] = 50000
		econ.res["food"] = 50000
		econ.res["metal"] = 50000
		research.blueprints = 3
		_on_research_start("infantry")
		if not research.current.is_empty():
			research.current["end"] = now_s() + 7200  # a long one, so the blueprint matters
			research.current["dur"] = 7200
		_open_tab("development")
		return
	if what == "realm_name":  # the realm's name field with ideas
		_open_name_editor(func(): pass)
		return
	if what == "flag_wizard":  # the FTUE 3-tap flag: flag_wizard[:1|2|3] — that step
		var st := int(parts[1]) if parts.size() > 1 else 0
		_open_flag_wizard(st, FlagView.random_flag(_flag_seed()), func(): pass)
		return
	if what == "flag_map":  # the player's flag on the map's banners, close to the first army
		flag = {"div": "quarters", "c1": 0, "c2": 13, "em": "tower", "ec": 16, "frame": ""}
		hud.set_flag(flag)
		map_view.set_flag(flag)
		var pa := _player_armies()
		if not pa.is_empty():
			rig.focus(map_view.cell_world(int(pa[0]["hex"])), 0.1)
		return
	if what == "flag":  # the flag constructor: flag[:colors|em|frame] opens that tab on a sample flag
		ui._flag_tab = parts[1] if parts.size() > 1 else "div"
		cases.owned_cosmetics["cos_flag_part_recruit_star"] = true
		cases.owned_cosmetics["cos_frame_recruit"] = true
		_open_flag_editor({"div": "chevron", "c1": 6, "c2": 13, "em": "crown", "ec": 16, "frame": "cos_frame_recruit"})
		return
	if what == "profile":  # the profile after a little play: goals reached, a few commanders
		stats["peaces"] = 3
		stats["peace_wins"] = 3
		stats["offensives"] = 12
		stats["colonized"] = 9
		for id in ["cmd_lira", "cmd_vega"]:
			cases.shards[id] = int(cases.shards.get(id, 0)) + Commanders.spent(_cmd_rarity(id), 1)
		_chronicle_tick()
		_open_profile()
		return
	if what == "commanders":  # the collection mid-game (commanders:card — Vega's card; commanders:tab — the Army tab)
		econ.res["gold"] = 40000
		econ._find_type("residence")["level"] = int(parts[2]) if parts.size() > 2 else 4  # commanders:<view>:<DL>
		for id in ["cmd_lira", "cmd_vega", "cmd_frey", "cmd_seir", "cmd_irma", "cmd_bram", "cmd_vik"]:
			cases.shards[id] = int(cases.shards.get(id, 0)) + Commanders.spent(_cmd_rarity(id), 1)
		cases.shards["cmd_bram"] = int(cases.shards["cmd_bram"]) + 30
		cases.shards["cmd_vega"] = int(cases.shards["cmd_vega"]) + 20
		cases.shards["cmd_olm"] = 6
		cases.shards["cmd_rai"] = 20
		cases.shards["cmd_hawk"] = 14
		commanders.levels = {"cmd_bram": 6, "cmd_lira": 5, "cmd_vega": 4, "cmd_frey": 3, "cmd_irma": 2}
		var pa := _player_armies()
		if pa.size() > 1:
			commanders.assign(int(pa[0]["id"]), "cmd_bram")
		if parts.size() > 1 and parts[1] == "tab":
			_open_tab("army")
			return
		if parts.size() > 1 and parts[1] == "assign" and pa.size() > 1:
			_open_tab("army")
			_open_cmd_picker(int(pa[1]["id"]))
			return
		if parts.size() > 1 and parts[1] == "card":
			_open_commander("cmd_vega")
			return
		_open_commanders()
		return
	if what == "patent":  # the subscription screen (patent:on — while active)
		if parts.size() > 1 and parts[1] == "on":
			patent.buy(now_s())
			_patent_tick(now_s())
		_open_patent()
		return
	if what == "hand":  # the hand picker at DL6 (5 slots, the airstrike open); hand:tab — the Army tab card
		econ._find_type("residence")["level"] = 6
		hand_pick = ["breakthrough", "airstrike", "defense", "encircle"]
		_open_tab("army")
		_econ_tick()
		if parts.size() < 2:
			_open_hand_picker()
		return
	if what == "calendar" and parts.size() > 1 and parts[1] == "pick":  # day 26: whom to give the 15 shards
		calendar.choice = 15
		_pick_cal_commander()
		return
	if what == "calendar":  # the login calendar on day 5 (days 1–4 taken)
		var t := now_s()
		for d in 5:
			calendar.visit(t - (4 - d) * 86400)
			if d < 4:
				calendar.claim()
		_open_calendar()
		return
	if what == "world":  # the World tab: pass, calendar, orders (one swap left) and the HUD chip
		calendar.visit(now_s())
		_open_tab("world")
		_econ_tick()
		return
	if what == "settings":
		_on_hud_button("gear")
		return
	if what == "dip2":
		await _world_expansion()
		ui.close_modal()
		econ._find_type("residence")["level"] = 3
		opinion[4] = 46.0
		allies = [3]
		_open_tab("diplomacy")
		return
	if what == "oil":
		await _world_expansion()
		ui.close_modal()
		econ._find_type("residence")["level"] = 5
		_econ_tick()
		for c in sim.cells:
			if c["kind"] == "oil":
				_select(c["id"])
				rig.focus(map_view.cell_world(c["id"]), 0.4)
				break
		return
	if what == "swap":  # a territory swap offer with the Barons in chapter II
		await _world_expansion()
		ui.close_modal()
		opinion[MapGen.BARONS] = 25.0
		for c in sim.cells:  # a settled hex outside the core to offer
			if c["owner"] == Types.NOBODY and Types.is_passable(c) and _touches_player(c["id"]):
				c["owner"] = Types.PLAYER
				c["controller"] = Types.PLAYER
				map_view.refresh_hex(c["id"])
				break
		var give := -1
		var get_h := -1
		for c in sim.cells:
			if get_h < 0 and _swappable(c["id"], MapGen.BARONS) and _touches_player(c["id"]):
				get_h = c["id"]
		for c in sim.cells:
			if give < 0 and _swappable(c["id"], Types.PLAYER):
				give = c["id"]
		if give >= 0 and get_h >= 0:
			_swap = {"state": MapGen.BARONS, "give": [], "get": []}
			_swap_pick(give)
			_swap_pick(get_h)
			rig.focus(map_view.cell_world(get_h), 0.5)
		return
	if what == "swap_ai":  # a neighbour (Fox, Owl or Turtle) proposes a swap that straightens the border
		await _world_expansion()
		ui.close_modal()
		for s in _ai_states():
			opinion[s] = 30.0
		for s in _ai_states():
			if not SWAP_OFFER_SEC.has(String(sim.states[s]["archetype"])):
				continue
			_demo_salient(s)
			for t in _ai_states():
				swap_offer_at[t] = 0 if t == s else now_s() + 86400
			_ai_swap_tick(now_s())
			if not swap_offer.is_empty():
				break
		if swap_offer.is_empty():
			print("no AI swap offer found")
			return
		_show_swap_offer()
		return
	if what == "coalition" or what == "separate":  # «Тревога соседей» over 100%: a coalition is forming (Diplomacy tab);
		# separate — 12 h later the coalition is at war, the player holds a member's land and it asks for peace
		await _world_expansion()
		ui.close_modal()
		await _world_expansion()
		ui.close_modal()
		# a grown realm: it reaches the Hamlets too (a coalition needs 2+ neighbours)
		var hcap: Vector3 = map_view.cell_world(sim.states[MapGen.HAMLETS]["capital_id"])
		for step in 4:
			var touching := false
			for c in sim.cells:
				if c["owner"] == Types.PLAYER and _touches_owner(c["id"], MapGen.HAMLETS):
					touching = true
			if touching:
				break
			var pick := -1
			for c in sim.cells:
				if c["owner"] == Types.NOBODY and Types.is_passable(c) and _touches_player(c["id"]) \
						and (pick < 0 or map_view.cell_world(c["id"]).distance_to(hcap) < map_view.cell_world(pick).distance_to(hcap)):
					pick = c["id"]
			if pick < 0:
				break
			sim.cells[pick]["owner"] = Types.PLAYER
			sim.cells[pick]["controller"] = Types.PLAYER
			map_view.refresh_hex(pick)
		for st in _ai_states():
			opinion[st] = -40.0
		threat = 63.0
		threat_at = now_s()
		_coalition_tick(now_s())
		rig.focus(map_view.cell_world(sim.states[Types.PLAYER]["capital_id"]), 0.6)
		_open_tab("diplomacy")
		if what == "separate":
			time_offset += 12 * 3600 + 60
			_coalition_tick(now_s())
			if war.is_empty() or not war.has("coalition"):
				print("no coalition war")
				return
			war.erase("strike_at")
			war["battles"] = 4
			var mem := -1
			for m in war["coalition"]:
				if int(m) != int(war["enemy"]) and (mem < 0 or float(SEPARATE_AT.get(String(sim.states[int(m)]["archetype"]), 30.0)) < float(SEPARATE_AT.get(String(sim.states[mem]["archetype"]), 30.0))):
					mem = int(m)
			if parts.size() > 1 and parts[1] == "lose":  # the member holds the player's land: a losing separate peace
				var pcore := MapGen.core_of(sim, Types.PLAYER)
				var n := 0
				for c in sim.cells:
					if n < 3 and c["owner"] == Types.PLAYER and Types.is_passable(c) and not pcore.has(c["id"]) and _touches_owner(c["id"], mem):
						c["controller"] = mem
						map_view.refresh_hex(c["id"])
						n += 1
				war["battles"] = -10
				map_view.mark_dirty()
				_set_mode(Mode.WAR)
				_show_separate_offer(mem, false)
				return
			var need: float = SEPARATE_AT.get(String(sim.states[mem]["archetype"]), 30.0)
			var mcore := MapGen.core_of(sim, mem)
			for core_pass in [false, true]:
				for c in sim.cells:
					if _member_share(mem) >= need:
						break
					if int(c["owner"]) == mem and int(c["controller"]) == mem and Types.is_passable(c) and mcore.has(c["id"]) == core_pass:
						c["controller"] = Types.PLAYER
						map_view.refresh_hex(c["id"])
			map_view.mark_dirty()
			_normalize_armies()
			map_view.sync_armies(armies, null)
			_set_mode(Mode.WAR)
			rig.focus(map_view.cell_world(sim.states[mem]["capital_id"]), 0.6)
			_separate_offer_tick(now_s())
		return
	if what == "ch4":  # chapter IV «Индустриальный пояс»: the ceremony; ch4:<biome> — that biome up close
		await _world_expansion()
		ui.close_modal()
		await _world_expansion()
		ui.close_modal()
		if parts.size() > 1:
			await _world_expansion()
			ui.close_modal()
			var best := -1
			for c in sim.cells:
				if String(c.get("biome", "")) == parts[1] and c["terrain"] != "water" and c["owner"] == Types.NOBODY:
					best = c["id"]
					break
			if best >= 0:
				rig.focus(map_view.cell_world(best), 0.45)
			return
		_world_expansion()
		return
	if what == "ch3":  # chapter III «Континент»: ch3 — the ceremony, ch3:<kind> — a ring III feature up close
		await _world_expansion()
		ui.close_modal()
		econ._find_type("residence")["level"] = 5
		_econ_tick()
		if parts.size() > 1:
			await _world_expansion()
		else:
			_world_expansion()
		if parts.size() > 1:
			ui.close_modal()
			for i in range(sim.cells.size() - 1, -1, -1):
				if sim.cells[i]["kind"] == parts[1]:
					_select(i)
					rig.focus(map_view.cell_world(i), 0.4)
					break
		return
	if what == "ch2":
		if parts.size() > 1:
			await _world_expansion()
		else:
			_world_expansion()
		if parts.size() > 1:  # ch2:port / ch2:military_base / ch2:camp — look at a ring II feature
			ui.close_modal()
			for c in sim.cells:
				if (parts[1] == "camp" and not camps.at(c["id"]).is_empty()) or c["kind"] == parts[1]:
					_select(c["id"])
					rig.focus(map_view.cell_world(c["id"]), 0.4)
					break
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
		var only := int(parts[1]) if parts.size() > 1 else 0  # forts:N — every fort at level N, up close
		sim.cells[cap]["fort"] = only if only > 0 else 3
		var lv := 1
		for n in sim.neighbors[cap]:
			if n >= 0 and sim.cells[n]["owner"] == Types.PLAYER:
				sim.cells[n]["fort"] = only if only > 0 else lv
				lv = lv % 8 + 1
		map_view.refresh_props()
		rig.focus(map_view.cell_world(cap), 0.12 if only > 0 else 0.3)
		return
	if what == "fire":  # the burned FTUE mill up close
		ftue = 1
		_burned_mill()
		_select(_mill)
		rig.focus(map_view.cell_world(_mill), 0.3)
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
	if what == "missile":  # DL8 hand: a missile on a Barons tower and a landing behind the front
		econ._find_type("residence")["level"] = 8
		var tgt := -1
		for c in sim.cells:
			if tgt < 0 and battle.can_target(Types.PLAYER, c["id"]) and not battle.adjacent_idle_armies(Types.PLAYER, c["id"]).is_empty():
				tgt = c["id"]
		sim.cells[tgt]["tower"] = 3
		map_view.refresh_hex(tgt)
		_show_hand()
		rig.focus(map_view.cell_world(tgt), 0.55)
		rig.zoom = rig.zoom_target
		get_tree().create_timer(float(parts[1]) if parts.size() > 1 else 3.0).timeout.connect(func():
			battle.energy[Types.PLAYER] = 10 * Battle.ENERGY_UNIT
			battle.issue(Types.PLAYER, {"t": "card", "card": "missile", "target": tgt})
			for c in sim.cells:
				if battle.can_land(Types.PLAYER, c["id"]) and c["id"] != tgt:
					battle.issue(Types.PLAYER, {"t": "card", "card": "landing", "target": c["id"]})
					break)
		return
	if what == "air":  # the player's airstrike into a Barons tower's air defence
		var tgt := -1
		for c in sim.cells:
			if tgt < 0 and battle.can_target(Types.PLAYER, c["id"]) and not battle.adjacent_idle_armies(Types.PLAYER, c["id"]).is_empty():
				tgt = c["id"]
		for n in sim.neighbors[tgt]:
			if n >= 0 and sim.cells[n]["owner"] == enemy and sim.cells[n]["controller"] == enemy and int(sim.cells[n]["fort"]) == 0:
				sim.cells[n]["tower"] = 6
				map_view.refresh_hex(n)
				break
		ui.set_locked({})
		rig.focus(map_view.cell_world(tgt), 0.5)
		rig.zoom = rig.zoom_target
		# headless start-up frames are slow: strike 3 s in so `--shot-delay` can catch the flight
		get_tree().create_timer(float(parts[1]) if parts.size() > 1 else 3.0).timeout.connect(func():
			battle.energy[Types.PLAYER] = 6 * Battle.ENERGY_UNIT
			battle.issue(Types.PLAYER, {"t": "card", "card": "airstrike", "target": tgt}))
		return
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
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot-delay="):  # capture an animation part-way (seconds)
			await get_tree().create_timer(float(a.substr(13))).timeout
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path)
	print("shot saved ", path)
	get_tree().quit()
