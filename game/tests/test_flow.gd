extends SceneTree
## Headless smoke test of the game controller (scripts/main.gd): drives every mode transition and
## fails on script errors or broken invariants. Run:
##   godot --headless --path game --script res://tests/test_flow.gd

const Types := preload("res://scripts/sim/types.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const War := preload("res://scripts/sim/war.gd")
const Kit := preload("res://scripts/ui_kit.gd")
const CameraRig := preload("res://scripts/camera_rig.gd")
const L := preload("res://scripts/l10n.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	if cond:
		print("PASS  ", msg)
	else:
		fails += 1
		print("FAIL  ", msg)


func _new_game() -> Node:
	var g: Node = load("res://scenes/main.tscn").instantiate()
	g.save_enabled = false
	root.add_child(g)
	await process_frame
	await process_frame
	return g


## A game at the tutorial's step 1 as a first launch has it: `ftue` set before _ready, so the tutorial's end
## (stats.ftue_done), the free crate's timer and Bram all wait for it (playtest 2 review: tests that set ftue after
## _ready ran a tutorial already counted as over).
func _new_tutorial() -> Node:
	var g: Node = load("res://scenes/main.tscn").instantiate()
	g.save_enabled = false
	g.ftue = 1
	root.add_child(g)
	await process_frame
	await process_frame
	return g


## A game right after the first victorious peace, truce expired (the player owns land beyond the core).
func _after_first_peace() -> Node:
	var g := await _new_game()
	g._demo("ceremony:0.1")
	for i in 80:
		g._step_ceremony(0.1)
	g._end_ceremony()
	g.truce = {}
	g.inbox = []
	return g


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	# 1. Full victory loop: declare → offensive → result → peace → ceremony → map
	var g := await _new_game()
	var hexes0: int = g._player_hexes()
	g._demo("ceremony:0.1")
	_check(g.mode == g.Mode.CEREMONY, "victory loop reaches the ceremony")
	_check(g.war.is_empty(), "war closed after treaty")
	for i in 80:
		g._step_ceremony(0.1)
	_check(g._ceremony["counters"], "ceremony counters shown")
	g._end_ceremony()
	_check(g.mode == g.Mode.MAP, "back to map after ceremony")
	_check(g._player_hexes() > hexes0, "treaty annexed hexes (%d → %d)" % [hexes0, g._player_hexes()])
	_check(g._truce_left(MapGen.BARONS) > 0, "truce with the Barons after peace")
	for c in g.sim.cells:
		if c["controller"] != c["owner"]:
			_check(false, "no occupation left after the treaty (hex %d)" % c["id"])
			break
	var core := MapGen.core_of(g.sim, MapGen.BARONS)
	var core_ok := true
	for id in core:
		if g.sim.cells[id]["owner"] != MapGen.BARONS:
			core_ok = false
	_check(core_ok, "the Barons keep their core")
	var Save = load("res://scripts/save.gd")
	var path_backup := ""
	if FileAccess.file_exists(Save.PATH):
		path_backup = FileAccess.get_file_as_string(Save.PATH)
	Save.save(g)
	var owners_before: Array = []
	for c in g.sim.cells:
		owners_before.append(c["owner"])
	var g2: Node = load("res://scenes/main.tscn").instantiate()
	g2.save_enabled = false
	_check(Save.apply(g2, Save.read()), "save applies to a new game")
	var same := true
	for i in owners_before.size():
		if g2.sim.cells[i]["owner"] != owners_before[i]:
			same = false
	_check(same and g2.truce.has(MapGen.BARONS), "save round trip keeps borders and truce")
	g2.free()
	if path_backup != "":
		var f := FileAccess.open(Save.PATH, FileAccess.WRITE)
		f.store_string(path_backup)
	else:
		Save.wipe()

	# 2. Truce blocks a new war; colonization of a free hex
	var bh := -1
	for c in g.sim.cells:
		if c["owner"] == MapGen.BARONS and not core.has(c["id"]):
			bh = c["id"]
			break
	if bh >= 0:
		g._select(bh)
		_check(g.ui._action2_kind == "", "declare disabled during the truce")
	# «Выбрать цель»: a war goal of a state the player may attack (the Hamlets, no truce) before land to settle
	var ham_goals: Array = War.recommend_goals(g.sim, MapGen.HAMLETS, 1)
	g._select(-1)
	_check(g.ui._action2_kind == "pick_target", "nothing selected: «Выбрать цель»")
	g._pick_target()
	if ham_goals.size() > 0:
		_check(g.selected == ham_goals[0] and g.ui._action2_kind == "declare" and g.ui._action2.hold,
			"«Выбрать цель» goes to the war goal of a state without a truce; «Война!» is held (hex %d)" % g.selected)
	g.truce[MapGen.HAMLETS] = int(Time.get_unix_time_from_system()) + 1800
	# a wild hex an AI is settling is never a target, and never a green «Занять» (02 §10.2)
	var claim := -1
	for c in g.sim.cells:
		if c["owner"] == Types.NOBODY and Types.is_passable(c) and g._touches_player(c["id"]) and g.camps.at(c["id"]).is_empty():
			claim = c["id"]
			break
	if claim >= 0:
		g.ai_colonizing[MapGen.HAMLETS] = {"hex": claim, "at": g.now_s() + 3 * 3600}
		g._select(claim)
		_check(g.ui._action2_kind == "" and String(g.ui._primary_args[0]) == "ai_claimed" and g.ui._primary_reason.contains("·"),
			"a hex an AI settles: «Занять» locked with the AI and its time (%s: %s)" % [String(g.ui._primary_args[0]), g.ui._primary_reason])
	g._select(-1)
	g._pick_target()
	_check(g.selected >= 0 and g.sim.cells[g.selected]["owner"] == Types.NOBODY and g._ai_claimed(g.selected) < 0,
		"every neighbour under a truce: «Выбрать цель» goes to a wild hex free to settle (hex %d)" % g.selected)
	g.ai_colonizing = {}
	if g.selected >= 0 and g.sim.cells[g.selected]["owner"] == Types.NOBODY:
		var n0: int = g._player_hexes()
		var gold0: int = g.econ.res["gold"]
		g._on_action("colonize")
		_check(g.colonizing.size() == 1 and g.econ.res["gold"] < gold0, "colonization starts: gold paid, timer running")
		g.time_offset += 3600
		g._econ_tick()
		_check(g._player_hexes() == n0 + 1 and g.colonizing.is_empty(), "colonization timer adds a hex")

	# 2b. Economy: income accrues, «collect all», building upgrade with a timer (the scripted Barons ultimatum stays away:
	# the truce after the first peace runs on the game's clock now, and these checks jump it by hours)
	g.ultimatum_at = g.now_s() + 3650 * 86400
	var econ = g.econ
	g.time_offset += 2 * 3600
	g._econ_tick()
	var stock_before: int = econ.stock_total("gold")
	_check(stock_before > 0 and g.map_view._bubbles.size() > 0, "income accrues on hexes and shows bubbles")
	var gold_before: int = econ.res["gold"]
	g._collect_all()
	var cap_gold: int = econ.storage_cap()["gold"]
	_check(econ.stock_total("gold") < stock_before and (econ.res["gold"] > gold_before or gold_before >= cap_gold),
		"collect all moves stock into storage (gold %d → %d, cap %d, stock %d → %d)" % [gold_before, econ.res["gold"], cap_gold, stock_before, econ.stock_total("gold")])
	# a tap on a coin collects whatever ground lies under it (B4 fix2): the coin floats over its hex's upper half, and
	# the camera's ground pick alone took the hex behind it. A coin of the capital's (stock put there, the clock left
	# alone), the camera on it at the default zoom; the gold is put back after, so what follows sees the same realm
	var cap_h: int = g.sim.states[Types.PLAYER]["capital_id"]
	var gold_keep: int = econ.res["gold"]
	econ.res["gold"] = 0
	econ.stock[cap_h] = {"gold": 400}
	g.rig.focus(g.map_view.cell_world(cap_h), 0.45)
	g.rig.zoom = g.rig.zoom_target
	await process_frame
	g._update_bubbles()
	await create_timer(0.4).timeout  # the coin grows in
	var cam3: Camera3D = g.get_viewport().get_camera_3d()
	var bub_on: bool = g.map_view.has_bubble(cap_h) and g.map_view.on_screen(cap_h)
	var bbox: Rect2 = g.map_view._bubble_box(cap_h, cam3)
	var bub_p := Vector2(bbox.get_center().x, bbox.position.y + 6.0)  # the coin's top edge: over the hex behind
	var bub_ground: Vector2i = CameraRig.world_to_axial(g.rig.ground_at(bub_p))
	var bub_hit: int = g.map_view.bubble_at(bub_p)
	var stock1: int = econ.stock_total("gold")
	g._select(-1)
	g._on_hex_tapped(bub_ground, bub_p)
	var bub_gid: int = g.sim.id_at(bub_ground.x, bub_ground.y)
	_check(bub_on and bub_hit == cap_h and bub_gid != cap_h and econ.stock_total("gold") < stock1 and econ.res["gold"] > 0 and g.selected == -1,
		"a tap on a coin's top collects, though the ground under it is the hex behind (capital %d: coin shown %s, hit %d, ground hex %d, gold stock %d → %d, selected %d)" % [cap_h, str(bub_on), bub_hit, bub_gid, stock1, econ.stock_total("gold"), g.selected])
	# … and the rest of a coin hex's ground selects the hex (B4r3 review: a ground fallback collected on every tap there,
	# 73–80 % of the hex outside the coin, so with the storage full the hex was never selected); a tap on the coin with
	# the storage full moves nothing and selects the hex under the finger (tutorial steps 8 and 9)
	var cap_ax := Vector2i(int(g.sim.cells[cap_h]["q"]), int(g.sim.cells[cap_h]["r"]))
	econ.stock[cap_h] = {"gold": 400}
	g._update_bubbles()
	await create_timer(0.4).timeout
	bbox = g.map_view._bubble_box(cap_h, cam3)
	var below := Vector2(-1.0, -1.0)
	var by: float = bbox.end.y + g.map_view.BUBBLE_TAP_SLOP + 2.0
	while below.x < 0.0 and by < bbox.end.y + 160.0:
		var bp := Vector2(bbox.get_center().x, by)
		if g.map_view.bubble_at(bp) < 0 and CameraRig.world_to_axial(g.rig.ground_at(bp)) == cap_ax:
			below = bp
		by += 4.0
	var stock2: int = econ.stock_total("gold")
	g._select(-1)
	if below.x >= 0.0:
		g._on_hex_tapped(cap_ax, below)
	_check(below.x >= 0.0 and g.selected == cap_h and econ.stock_total("gold") >= stock2 and g.map_view.has_bubble(cap_h),
		"a tap on a coin hex's ground below the coin selects the hex and collects nothing (capital %d, tap %s, gold stock %d → %d, selected %d)" % [cap_h, str(below.round()), stock2, econ.stock_total("gold"), g.selected])
	var res_keep: Dictionary = econ.res.duplicate()
	var veins_keep: Dictionary = econ.vein_secs.duplicate()
	var cap_all: Dictionary = econ.storage_cap()
	for r in cap_all:
		if r != "raivite":
			econ.res[r] = int(cap_all[r])
	for vh in econ.vein_secs:
		econ.vein_secs[vh] = 0
	var mid_p: Vector2 = bbox.get_center()
	var mid_ax: Vector2i = CameraRig.world_to_axial(g.rig.ground_at(mid_p))
	var mid_id: int = g.sim.id_at(mid_ax.x, mid_ax.y)
	var mid_hit: int = g.map_view.bubble_at(mid_p)
	g._select(-1)
	g._on_hex_tapped(mid_ax, mid_p)
	_check(mid_hit == cap_h and mid_id >= 0 and g.selected == mid_id and econ.stock_total("gold") >= stock2 and g.map_view.has_bubble(cap_h),
		"storage full: a tap on the coin moves nothing and selects the hex under the finger (hit %d, ground hex %d, selected %d, gold stock %d → %d)" % [mid_hit, mid_id, g.selected, stock2, econ.stock_total("gold")])
	for r in res_keep:
		econ.res[r] = res_keep[r]
	for vh in veins_keep:
		econ.vein_secs[vh] = veins_keep[vh]
	# the camera's touches (camera_rig): a tap is one finger on a still camera. A pinch ends with one finger lifting a
	# few px after the other and that lift was a tap (B4r3 review: it collected, or selected a hex); a finger put down on
	# a gliding camera only stops it
	var taps := [0]
	var count_tap := func(_c: Vector2i, _s: Vector2) -> void: taps[0] += 1
	g.rig.hex_tapped.connect(count_tap)
	var touch := func(i: int, p: Vector2, down: bool) -> void:
		var ev := InputEventScreenTouch.new()
		ev.index = i
		ev.position = p
		ev.pressed = down
		g.rig._unhandled_input(ev)
	var drag := func(i: int, p: Vector2, rel: Vector2) -> void:
		var ev := InputEventScreenDrag.new()
		ev.index = i
		ev.position = p
		ev.relative = rel
		g.rig._unhandled_input(ev)
	g.rig._velocity = Vector3.ZERO
	g._select(-1)
	var stock3: int = econ.stock_total("gold")
	touch.call(0, mid_p, true)
	touch.call(0, mid_p, false)
	_check(taps[0] == 1 and econ.stock_total("gold") < stock3 and g.selected == -1,
		"camera: a one-finger tap on the coin is a tap and collects (taps %d, gold stock %d → %d)" % [taps[0], stock3, econ.stock_total("gold")])
	econ.stock[cap_h] = {"gold": 400}
	g._update_bubbles()
	await create_timer(0.4).timeout
	var stock4: int = econ.stock_total("gold")
	var pin_a := mid_p + Vector2(-20.0, 120.0)
	var pin_b := mid_p + Vector2(20.0, -260.0)
	taps[0] = 0
	g._select(-1)
	touch.call(0, pin_a, true)
	touch.call(1, pin_b, true)
	for i in 8:
		pin_a += Vector2(-3.0, 6.0)
		pin_b += Vector2(3.0, -9.0)
		drag.call(0, pin_a, Vector2(-3.0, 6.0))
		drag.call(1, pin_b, Vector2(3.0, -9.0))
	touch.call(1, pin_b, false)
	drag.call(0, mid_p, Vector2(2.0, 2.0))  # the last finger ends on the coin after 3 px
	touch.call(0, mid_p, false)
	_check(taps[0] == 0 and econ.stock_total("gold") >= stock4 and g.selected == -1 and g.rig._touches.is_empty(),
		"camera: a pinch never ends in a tap, though its last finger lifts on a coin (taps %d, gold stock %d → %d, selected %d)" % [taps[0], stock4, econ.stock_total("gold"), g.selected])
	g.rig.focus(g.map_view.cell_world(cap_h), 0.45)
	g.rig.zoom = g.rig.zoom_target
	g.rig._velocity = Vector3(8.0, 0.0, 0.0)  # a fling's inertia
	var glide: float = g.rig._glide_px()
	touch.call(0, mid_p, true)
	touch.call(0, mid_p, false)
	_check(glide > g.rig.GLIDE_STOP_PX and taps[0] == 0 and g.rig._velocity == Vector3.ZERO and econ.stock_total("gold") >= stock4 and g.selected == -1,
		"camera: a tap on a gliding camera only stops it (glide %d px/s, taps %d, gold stock %d → %d)" % [roundi(glide), taps[0], stock4, econ.stock_total("gold")])
	g.rig.hex_tapped.disconnect(count_tap)
	g.rig.focus(g.map_view.cell_world(cap_h), 0.45)
	g.rig.zoom = g.rig.zoom_target
	econ.res["gold"] = gold_keep
	g._open_tab("buildings")
	var items: Array = g._building_items(g.now_s())
	_check(items.size() >= 5, "buildings tab lists buildings (%d)" % items.size())
	var target_b: Dictionary = {}
	for it in items:
		if it["reason"] == "" and not it["busy"]:
			target_b = it
			break
	if not target_b.is_empty():
		var lvl0: int = econ.building(target_b["id"])["level"]
		g._on_building_upgrade(target_b["id"])
		_check(econ.busy_builders(g.now_s()) == 1, "upgrade occupies a builder")
		g.time_offset += 2 * 3600
		g._econ_tick()
		_check(econ.building(target_b["id"])["level"] == lvl0 + 1, "upgrade completes after its timer (%s)" % target_b["name"])
	# chapter stars and completion (canon §12.1)
	var rv0: int = econ.res["raivite"]
	g._on_world_action("peace")
	_check(econ.res["raivite"] == rv0 + 10 and g.stars_claimed.has("peace"), "peace star claimed: +10 Raivites")
	g._on_world_action("peace")
	_check(econ.res["raivite"] == rv0 + 10, "a star is claimed only once")
	for c in g.sim.cells:
		if g._player_hexes() >= g._chapter_goal():
			break
		if c["owner"] == Types.NOBODY and Types.is_passable(c):
			c["owner"] = Types.PLAYER
			c["controller"] = Types.PLAYER
	# the goal met at war (07 §3.1 goal_met, E1): no «откройте «Мир»» yet — the war's own line; the World card's
	# «Расширить» grey with its reason; the signal itself waits for the peace
	g.ui.close_modal()
	g.war = {"enemy": MapGen.BARONS, "goal": -1, "ai_goal": -1}
	g.ui._toast_queue = []
	g.ui._toast_cur = {}
	g._check_chapter_goal()
	var wtexts: Array = g.ui._toast_queue.map(func(t): return String(t["text"])) + [String(g.ui._toast_cur.get("text", ""))]
	var wcard: Dictionary = g._world_items()[0]
	_check(int(g.stats.get("goal_signal", 0)) == 0 and int(g.stats.get("goal_war_signal", 0)) == 1 and not bool(wcard["can_expand"]) \
		and bool(wcard["goal_met"]) and not " ".join(wtexts).contains(g.tr("toast.chapter_goal") % "I") \
		and " ".join(wtexts).contains(g.tr("toast.chapter_goal_war") % "I"),
		"chapter goal met at war: the war's line, no «откройте «Мир»», «Расширить» waits (%s)" % str(wtexts))
	g.war = {}
	# a tap's answer (a locked card, a refused drag) goes ahead of the waiting toasts and the one on screen lets itself
	# out at once: no ~3 s behind the battle's how-to
	g.ui._toast_queue = []
	g.ui._toast_cur = {}
	for tt in ["A", "B", "C"]:
		g.ui.toast(tt)
	g.ui.toast("D", "lock", "info", true)
	var tq: Array = g.ui._toast_queue.map(func(t): return String(t["text"]))
	_check(tq.size() > 0 and tq[0] == "D" and String(g.ui._toast_cur.get("text", "")) == "A" and g.ui._toast_shown == INF,
		"a tap's toast jumps the queue, the one on screen goes (%s)" % str(tq))
	g.ui._toast_queue = []
	# the goal met (07 §3.1): signalled once, the «Мир» tab's dot, «Расширить мир» on the big button with nothing selected
	g.mode = g.Mode.MAP
	g._econ_tick()
	g._select(-1)
	_check(int(g.stats.get("goal_signal", 0)) == 1 and g.ui._action2_kind == "expand" and g.hud.tab_dot_rect("world").size.x > 0.0,
		"chapter goal met: signalled, the World tab's dot, «Расширить мир» (%s)" % g.ui._action2_kind)
	g._on_action("expand")
	_check(g.tab == "world" and g.chapter == 1, "«Расширить мир» opens the World tab at the chapter card")
	g._on_action("expand")  # the big button again, the tab already on the chapter's card (B-L: it did nothing)
	var ex2: int = g.chapter
	if g.chapter == 1:
		g._on_world_action("expand")
	_check(ex2 == 2, "the big «Расширить мир» with the World tab open starts the expansion")
	_check(g.chapter == 2 and econ.res["raivite"] >= rv0 + 210, "chapter I completes: legacy +200 Raivites, chapter II opens")
	g.ui.close_modal()

	# research: Taxes level 1 raises gold income by 2% (canon §12.3)
	var inc0: int = econ.gross_per_hour(g.sim)["gold"]
	econ.res["gold"] = maxi(econ.res["gold"], 2000)
	g._on_research_start("taxes")
	_check(not g.research.current.is_empty(), "research started")
	g.time_offset += 120
	g._econ_tick()
	_check(g.research.level("taxes") == 1 and econ.gross_per_hour(g.sim)["gold"] > inc0, "Taxes researched: gold income %d → %d" % [inc0, econ.gross_per_hour(g.sim)["gold"]])
	g._open_tab("development")
	_check(g._research_items(g.now_s()).size() == 10, "development tab lists research lines")

	# store: free war crate after 6 h, paid Royal case, speed-up items
	g._open_shop()
	g.time_offset += 6 * 3600 + 5
	g.cases.claim_free_crates(g.now_s())
	g.time_offset += 6 * 3600 + 5
	var crates: int = g.cases.claim_free_crates(g.now_s())
	_check(crates >= 1, "free war crate accrues every 6 h (%d)" % crates)
	var hist0: int = g.cases.history.size()
	g._on_open_case("case_war_crate", 1, "free")
	_check(g.cases.history.size() == hist0 + 1, "free crate opened")
	econ.res["raivite"] = 500
	g._on_open_case("case_royal", 1, "raivite")
	_check(econ.res["raivite"] == 340, "Royal case costs 160 Raivites")
	g.shop.queue_free()
	g.shop = null

	# fortification on an own non-capital hex via the fort button
	var fhex := -1
	for c in g.sim.cells:
		if c["owner"] == Types.PLAYER and c["kind"] == "plain" and c["fort"] == 0:
			fhex = c["id"]
			break
	if fhex >= 0:
		g._select(fhex)
		var dk := String(g.ui._primary_args[0])
		_check(dk in ["tower", "fort"] and not (g.ui._action2.price as Array).is_empty(),
			"an own hex without a building offers its defence with a price (%s)" % dk)
		g._fort_action()
		g.time_offset += 3600
		g._econ_tick()
		_check(g.sim.cells[fhex]["fort"] == 1, "fort button builds a level-1 fortification")
	# deposit + convoy (canon §5.2): the first convoy is the fast FTUE one
	# the big button on the player's own deposit; on a wild one next to the realm it is «Занять», the convoy beside it
	var dhex := -1
	for dep in g.deposits.active:
		if g.deposits.can_send(g.sim, dep["hex"], econ.dev_level()) == "" and (dhex < 0 or g.sim.cells[dep["hex"]]["owner"] == Types.PLAYER):
			dhex = dep["hex"]
	if dhex >= 0:
		var res_key: String = g.deposits.at(dhex)["res"]
		var before: int = econ.res[res_key]
		g._select(dhex)
		var wild_next: bool = g.sim.cells[dhex]["owner"] == Types.NOBODY and g._touches_player(dhex)
		_check(g.ui._action2_kind == "convoy" or (wild_next and g.ui._action_kind == "convoy" and String(g.ui._primary_args[0]) == "colonize"),
			"deposit hex offers a convoy (%s / %s, mode %d, war %s, ultimatum %s)" % [str(g.ui._primary_args.slice(0, 4)), g.ui._action_kind, g.mode, str(g.war.get("enemy", -1)), str(g.ultimatum.get("state", -1))])
		g._on_action("convoy")
		g.time_offset += 61
		g._econ_tick()
		_check(econ.res[res_key] > before or before >= econ.storage_cap()[res_key], "convoy brings the deposit home (%s %d → %d)" % [res_key, before, econ.res[res_key]])
	# armies heal over time for food (canon §8.1)
	var pa: Dictionary = g._player_armies()[0]
	pa["str"] = int(pa["max_str"]) / 2
	var food0: int = econ.res["food"]
	g.time_offset += 1300
	g._econ_tick()
	_check(int(pa["str"]) == int(pa["max_str"]) and econ.res["food"] < food0 + 5000, "army refills in ~20 min, paying food (%d → %d)" % [food0, econ.res["food"]])
	g._open_tab("army")
	_check(g._army_items(g.now_s()).size() == g._player_armies().size() + (1 if g.ftue > 0 else 3), "army tab lists armies plus «new army» (and the hand and commanders after the tutorial)")
	# Settings → language: applies at once to the HUD, the open tab and the inbox, and reopens Settings
	var lang0 := TranslationServer.get_locale()
	g._post("inbox.raid.title", g.L.pack("inbox.raid.text", [g._cell_key(g.sim.states[Types.PLAYER]["capital_id"])]))
	g._open_tab("buildings")
	g._set_language("en")
	var names_en: Array = []
	for it in g._building_items(g.now_s()):
		names_en.append(it["name"])
	_check(g.hud.tab_labels["buildings"].text == "Buildings" and names_en.has("Residence") and g.ui._modal != null,
		"language switch to English re-labels the HUD and the buildings tab")
	var raid_en := ""
	for it in g.inbox:
		if String(it["title"]) == "inbox.raid.title":
			raid_en = g.L.t(String(it["text"]))
	_check(raid_en.begins_with("Marauders") and raid_en.contains("“Capital”"), "stored reports follow the language (%s)" % raid_en)
	g._set_language("ru")
	_check(g.hud.tab_labels["buildings"].text == "Здания" and g._state_name(MapGen.BARONS) == "Кремнёвые Бароны", "and back to Russian")
	g.ui.close_modal()
	TranslationServer.set_locale(lang0)
	g.queue_free()
	await process_frame

	# 3. War on the Hamlets (they get armies on demand), immediate peace → white peace / defeat paths
	g = await _new_game()
	var ham_goal := -1
	var hcore := MapGen.core_of(g.sim, MapGen.HAMLETS)
	for c in g.sim.cells:
		if c["owner"] == MapGen.HAMLETS and not hcore.has(c["id"]) and Types.is_passable(c):
			ham_goal = c["id"]
			break
	g._declare(MapGen.HAMLETS, ham_goal)
	var ham_armies := 0
	for a in g.armies:
		if a["side"] == MapGen.HAMLETS:
			ham_armies += 1
	_check(ham_armies > 0, "Hamlets receive field armies on war")
	g._start_offensive()
	_check(g.mode == g.Mode.BATTLE, "offensive starts")
	_check(g.ui._action2.visible and g.ui._action2.hold and is_equal_approx(g.ui._action2.hold_sec, 0.5),
		"«Отступить» is held 0.5 s (a double tap on «В атаку!» does not retreat)")
	g._on_action("retreat")
	for i in 30:
		g._process(0.1)
	_check(g.mode == g.Mode.RESULT, "retreat ends the offensive")
	g.ui.close_modal()
	g._set_mode(g.Mode.WAR)
	g._open_peace()
	_check(g.ui._modal != null, "peace with non-positive score opens white/defeat offer")
	War.white_peace(g.sim)
	g._finish_war(MapGen.HAMLETS, "test")
	_check(g.mode == g.Mode.MAP and g.war.is_empty(), "white peace returns to the map")

	# 4. Army drag order during a battle
	g.truce = {}
	g._declare(MapGen.BARONS, War.recommend_goals(g.sim, MapGen.BARONS, 1)[0])
	g._start_offensive()
	# cards open by DL (canon §9.9): at DL1 the hand is «Атака» and «Оборона», the next card (Котёл, DL2) shows locked
	# at the tray's end as a teaser outside the hand; the Barons (Wolf) play the airstrike only from DL6
	_check(not g._hand().has("airstrike") and not g._hand().has("encircle") and g.ui._locked.has("encircle")
		and g.ui._locked.size() == 1 and g._hand_display() == ["attack", "defense"], "airstrike locked below DL6")
	_check(not g.ai.airstrike, "DL1 Barons don't fly")
	var army: Dictionary = {}
	for a in g.armies:
		if a["side"] == Types.PLAYER:
			army = a
			break
	var target := -1
	for n in g.sim.neighbors[army["hex"]]:
		if n >= 0 and g.battle.can_target(Types.PLAYER, n):
			target = n
			break
	if target >= 0:
		g._drag_army = army["id"]
		g._draw_order(army["hex"], target)
		var ok: bool = g.battle.issue(Types.PLAYER, {"t": "attack", "army": army["id"], "target": target})
		_check(ok, "drag order issues an attack")
	for i in 60:
		g._process(0.1)
	_check(g.battle == null or g.battle.tick > 0, "battle ticks in _process")
	g.queue_free()
	await process_frame

	# 4b. Scripted Barons ultimatum (canon §9.1, §14.3), first strike always repelled, war cap
	g = await _after_first_peace()
	g.ultimatum_at = g.now_s() - 1
	g._ai_tick(g.now_s())
	_check(not g.ultimatum.is_empty() and g._unread_letters() == 1 and g._unread() == 2, "ultimatum issued and posted to the inbox (the mail stays lit while it waits)")
	var uhex: int = g.ultimatum["hex"]
	g._answer_ultimatum("refuse")
	_check(not g.war.is_empty() and g.war["ai_goal"] == uhex and g.war.has("strike_at"), "refusal starts an AI war with an announced strike")
	var battles0: int = g.war["battles"]
	g.time_offset += 21 * 60
	g._econ_tick()
	_check(not g.war.has("strike_at") and g.war["battles"] == battles0 + 2, "the first strike is repelled (+2 war score)")
	g.time_offset += 2 * 3600
	g._econ_tick()
	_check(g.war.is_empty(), "war cap closes the war after 2 h (mode %d)" % g.mode)
	if g.mode == g.Mode.CEREMONY:
		for i in 80:
			g._step_ceremony(0.1)
		g._end_ceremony()
	g.queue_free()
	await process_frame
	g = await _after_first_peace()
	g.ultimatum_at = g.now_s() - 1
	g._ai_tick(g.now_s())
	var ahex: int = g.ultimatum["hex"]
	g._answer_ultimatum("accept")
	_check(g.sim.cells[ahex]["owner"] == MapGen.BARONS and g._truce_left(MapGen.BARONS) > 0, "accepting cedes the hex and gives a truce")
	g.queue_free()
	await process_frame

	# 4z. A fresh install (playtest 2, A-high 1): saves on and no save file yet — the tutorial is decided before the first
	# tick: step 1 with no window over it, no calendar day credited, no orders chip, no free crate's timer, Bram not yet
	# (he comes with the first peace). The test's own save and settings files: the player's real ones are never touched.
	var SaveF = load("res://scripts/save.gd")
	SaveF.path = "user://test_flow_fresh_save.json"
	SaveF.settings_path = "user://test_flow_fresh_settings.json"
	SaveF.wipe()
	var gf: Node = load("res://scenes/main.tscn").instantiate()
	root.add_child(gf)
	await process_frame
	await process_frame
	gf._econ_tick()
	_check(gf.save_enabled and gf.ftue == 1 and not gf.ui.has_modal() and gf.calendar.credited == 0 and not gf.calendar.pending
		and not gf._orders_open() and not gf.hud._orders_chip.visible,
		"fresh install: step 1 with no window over it, no calendar day credited, no orders (credited %d, modal %s)" % [gf.calendar.credited, str(gf.ui.has_modal())])
	_check(not gf.stats.has("bram_given") and not gf.cases.free_started and not gf.stats.has("ftue_done"),
		"fresh install: Bram, the free crate's timer and the tutorial's end all wait")
	gf._ftue_tick(0.1)
	_check(gf.ui._coach.visible and gf.ui._action2_kind == "declare", "fresh install: the step-1 coach on «Война!» from the first frame")
	# the tutorial's end (its card's «Вперёд»): the first War Crate an hour later, the calendar's day 1 a few seconds
	# after the colonize hint — once
	gf.ftue = 0
	gf._finish_tutorial()
	gf._econ_tick()
	_check(gf.cases.free_started and gf.cases.free_crate_left(gf.now_s()) == 3600 and gf.calendar.credited == 1 and not gf.ui.has_modal()
		and gf._orders_open(), "after the tutorial: the first War Crate in 1 h, calendar day 1 credited, its screen not yet")
	gf.time_offset += 6
	gf._econ_tick()
	var cal_early: bool = gf.ui.has_modal()
	# the colonize hint acted on (settlers sent): the calendar comes a moment later, not over the hint being read
	var wild := -1
	for c in gf.sim.cells:
		if wild < 0 and int(c["owner"]) == Types.NOBODY and int(c["controller"]) == Types.NOBODY and Types.is_passable(c) \
				and gf._touches_player(int(c["id"])) and gf.camps.at(int(c["id"])).is_empty() and gf._ai_claimed(int(c["id"])) < 0:
			wild = int(c["id"])
	gf.econ.res["gold"] = maxi(int(gf.econ.res["gold"]), gf._colonize_cost())
	gf._colonize(wild)
	gf.time_offset += gf.CAL_AFTER_HINT_SEC
	gf._econ_tick()
	var cal_open: bool = gf.ui.has_modal()
	gf.ui.close_modal()
	gf._econ_tick()
	_check(not cal_early and wild >= 0 and cal_open and not gf.ui.has_modal() and gf.calendar.credited == 1,
		"the calendar opens once with day 1: not 6 s after the tutorial, %d s after the colonize hint is acted on" % gf.CAL_AFTER_HINT_SEC)
	gf.queue_free()
	await process_frame
	# a save made in a gap of the tour (the first peace's ceremony: ftue 0, the next step waiting) resumes it on load —
	# never «the tutorial is over» (the orders and the calendar would open over it)
	var gapd: Dictionary = SaveF.read()
	gapd["ftue"] = 0
	gapd["ftue_next"] = 7
	gapd["stats"] = {"flag_wizard": 1}
	SaveF.write_raw(gapd)
	var gr: Node = load("res://scenes/main.tscn").instantiate()
	root.add_child(gr)
	await process_frame
	await process_frame
	_check(gr.ftue == 7 and not gr.stats.has("ftue_done") and not gr._orders_open(), "a save made in the tour's gap resumes it (ftue %d)" % gr.ftue)
	gr.queue_free()
	await process_frame
	# an old save past the tutorial (no ftue_next, ftue 0) gets the tutorial's end on load: its orders and calendar stay
	var oldd: Dictionary = gapd.duplicate(true)
	oldd.erase("ftue_next")
	oldd["stats"] = {}
	var go2: Node = load("res://scenes/main.tscn").instantiate()
	go2.save_enabled = false
	_check(SaveF.apply(go2, oldd) and go2.stats.has("ftue_done") and go2.ftue == 0, "an old save past the tutorial gets stats.ftue_done (migrated)")
	go2.free()
	SaveF.wipe()
	if FileAccess.file_exists(SaveF.settings_path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SaveF.settings_path))
	SaveF.path = SaveF.PATH
	SaveF.settings_path = SaveF.SETTINGS_PATH

	# 4y. War 1 cannot be lost (playtest 2, A-high 2; 08 §8.3 F06/F08): an idle player — no gesture at all — ends on ★★★
	# with the flag and the first treaty's land; no ghost ever points at a fight it loses (F ≥ 1.1)
	var gi := await _new_tutorial()
	gi._ftue_tick(0.1)
	gi._on_action("declare")
	gi._on_action("offensive")
	var red := 0
	var lv3 := false
	while gi.battle != null and not gi.battle.over:
		if gi.battle.tick % 10 == 0:
			gi._ftue_tick(1.0)
			var bgi: Dictionary = gi._ftue_battle_goal()
			if not bgi.is_empty() and String(bgi["kind"]) == "army":
				var ai = gi.battle.army_at(int(bgi["from"]), Types.PLAYER)
				if ai == null or gi.battle.forecast(Types.PLAYER, [ai["id"]], int(bgi["to"]))["f"] < gi.FTUE_GHOST_F:
					red += 1
			lv3 = lv3 or gi._ftue_level() >= 3
		gi._battle_step()
	var ri: Dictionary = gi.battle.result()
	var fhi: int = gi.flag_hex
	_check(War.offensive_stars(ri["captured"], fhi, ri["routed_player_armies"]) == 3 and gi._ftue_haul().size() >= gi.FTUE_PEACE1_HEXES and red == 0 and lv3,
		"FTUE war 1 idle: ★★★ with the flag and %d hexes at 0:55 (F08), no ghost under F 1.1, the help ladder reached level 3 (%s, red %d)" % [gi.FTUE_PEACE1_HEXES, str(ri["captured"]), red])
	gi._end_offensive()
	_check(gi.ftue == 5, "FTUE war 1 idle: the result goes on to the treaty (step %d)" % gi.ftue)
	gi.queue_free()
	await process_frame
	# the ladder's level 3: a tap on the coached hex plays the drag; a failed offensive's «Ещё бой» starts the war over
	var gl := await _new_tutorial()
	gl._ftue_tick(0.1)
	gl._on_action("declare")
	var arm0: Dictionary = {}
	for a in gl.armies:
		arm0[int(a["id"])] = [int(a["hex"]), int(a["str"])]
	gl._on_action("offensive")
	var gtap: Dictionary = gl._ftue_battle_goal()
	gl._battle_tap(int(gtap["to"]))
	var lv_a: int = gl._ftue_level()
	gl._battle_tap(int(gtap["to"]))
	var lv_b: int = gl._ftue_level()
	_check(gl.ftue == 3 and lv_a == 1 and lv_b == 2,
		"a tap on the coached hex before the ladder's level 3 does nothing; each wrong gesture lifts the help (08 §8.3.2: levels %d, %d)" % [lv_a, lv_b])
	# the ladder's level 2 drop zone: 1.5 hex radii round the coached hex on screen — not any neighbour of it
	var zcam: Camera3D = gl.rig.cam
	var zc: Vector2 = zcam.unproject_position(gl.map_view.cell_world(int(gtap["to"])))
	var zstep := INF
	var zfar := -1
	for zn in gl.sim.neighbors[int(gtap["to"])]:
		if zn >= 0:
			var zd: float = zc.distance_to(zcam.unproject_position(gl.map_view.cell_world(zn)))
			zstep = minf(zstep, zd)
			if zn != int(gtap["from"]):
				zfar = zn
	var zp: Vector2 = zcam.unproject_position(gl.map_view.cell_world(zfar))
	var znear: Vector2 = zc + (zp - zc).normalized() * zstep / sqrt(3.0) * 1.2  # just over the hex's edge, on its neighbour
	_check(gl._ftue_in_zone(int(gtap["to"]), znear) and not gl._ftue_in_zone(int(gtap["to"]), zp),
		"the ladder's wider drop zone: just past the coached hex's edge counts, the next hex's centre does not")
	gl._battle_tap(int(gtap["to"]))
	_check(gl.ftue == 3 and gl._ftue_level() == 3 and gl._ftue_idle < 1.0, "three wrong gestures: the help ladder's level 3 without the 20 s")
	gl._battle_tap(int(gtap["to"]))
	_check(gl.ftue == 4, "the help ladder's level 3: a tap on the coached hex counts as the drag (step %d)" % gl.ftue)
	for i in 30:
		gl._battle_step()
	gl.battle._finish("time")  # (a war 1 that failed some other way: «Ещё бой» must start it over)
	gl.battle._captured = {}
	gl._end_offensive()
	_check(gl.ftue == 2, "a failed tutorial offensive asks for «Ещё бой» (step %d)" % gl.ftue)
	gl.ui.close_modal()
	gl._ftue_retry()
	var same_armies := true
	for a in gl.armies:
		if arm0.has(int(a["id"])):
			same_armies = same_armies and int(a["hex"]) == int(arm0[int(a["id"])][0]) and int(a["str"]) == int(arm0[int(a["id"])][1])
	var land_back := true
	for c in gl.sim.cells:
		land_back = land_back and (int(c["owner"]) != MapGen.BARONS or int(c["controller"]) == MapGen.BARONS)
	_check(same_armies and land_back and int(gl.war["battles"]) == 0, "«Ещё бой» restores both sides' armies, the land and the war's points to the war's start")
	gl.queue_free()
	await process_frame
	# a player who follows the coach, then waits (playtest 2, A-medium): the flag falls with time left, step 4b points at
	# a third hex (F ≥ 1.1), and at 0:55 it falls by script — +3, the first treaty's land, the Residence lesson after it
	var gw4 := await _new_tutorial()
	gw4._ftue_tick(0.1)
	gw4._on_action("declare")
	gw4._on_action("offensive")
	var cp4: Array = gw4._ftue_ghost_pair()
	gw4.battle.issue(Types.PLAYER, {"t": "attack", "army": gw4.battle.army_at(cp4[0], Types.PLAYER)["id"], "target": cp4[1]})
	gw4._ftue_attacked()
	for i in 120:
		if gw4.sim.cells[cp4[1]]["controller"] == Types.PLAYER:
			break
		gw4._battle_step()
	gw4.battle.issue(Types.PLAYER, {"t": "card", "card": "attack", "target": gw4.flag_hex})
	gw4._ftue_attacked()
	var saw4b := false
	var f4b := true
	while gw4.battle != null and not gw4.battle.over:
		if gw4.battle.tick % 10 == 0:
			gw4._ftue_tick(1.0)
			if gw4.ui._coach.visible and gw4.ui._coach_lbl.text == gw4.tr("ftue.4b"):
				saw4b = true
				var b4: Dictionary = gw4._ftue_battle_goal()
				if not b4.is_empty():
					var a4 = gw4.battle.army_at(int(b4["from"]), Types.PLAYER)
					f4b = f4b and a4 != null and gw4.battle.forecast(Types.PLAYER, [a4["id"]], int(b4["to"]))["f"] >= gw4.FTUE_GHOST_F
		gw4._battle_step()
	var r4: Dictionary = gw4.battle.result()
	_check(saw4b and f4b and (r4["captured"] as Array).size() >= 3 and r4["reason"] == "goals",
		"FTUE war 1 followed then waited: step 4b points at a winnable third hex, +3 by 0:55 (%s)" % str(r4["captured"]))
	gw4.queue_free()
	await process_frame

	# a later peace at a full gold store (playtest 2, B low: «Склад не вместит 4 430 золота» with 3× «Контрибуция»): the
	# recommended package takes no indemnity the warehouse cannot hold — its points go to opinion; with room, it does
	var gpk := await _new_game()
	gpk._declare(MapGen.BARONS, War.recommend_goals(gpk.sim, MapGen.BARONS, 1)[0])
	gpk._on_action("offensive")
	while gpk.battle != null and not gpk.battle.over:
		if gpk.battle.tick % 20 == 0:
			gpk._bot_move()
		gpk._battle_step()
	gpk._end_offensive()
	gpk.ui.close_modal()
	var count_contrib := func(game) -> int:
		var n := 0
		for d in game._demands:
			n += int(String(d["kind"]) == "contribution" and game._chosen.has(d["id"]))
		return n
	if War.war_score(gpk.sim, gpk.war)["score"] > 0.0:
		gpk.econ.res["gold"] = int(gpk.econ.storage_cap()["gold"])
		gpk._open_peace()
		var full_n: int = count_contrib.call(gpk)
		gpk.ui.close_modal()
		gpk._set_mode(gpk.Mode.WAR)
		gpk.econ.res["gold"] = 0
		gpk._open_peace()
		var empty_n: int = count_contrib.call(gpk)
		_check(full_n == 0 and (empty_n > 0 or War.war_score(gpk.sim, gpk.war)["score"] < 20.0),
			"a peace at a full gold store recommends no indemnity; an empty one does (%d / %d packages)" % [full_n, empty_n])
	gpk.queue_free()
	await process_frame

	# 5a. FTUE war 1 as the coach leads it (08 §8.3 F04–F07): the ghost's drag brings a second army beside the flag,
	# «Атака» onto the flag takes it — the first offensive ends on ★★★
	var gw := await _new_tutorial()
	gw._ftue_tick(0.1)
	gw._on_action("declare")
	gw._on_action("offensive")
	gw._ftue_tick(0.1)
	var cp: Array = gw._ftue_ghost_pair()
	var ca = gw.battle.army_at(cp[0], Types.PLAYER) if cp.size() == 2 else null
	if ca != null:
		gw.battle.issue(Types.PLAYER, {"t": "attack", "army": ca["id"], "target": cp[1]})
		gw._ftue_attacked()
		for i in 120:
			if gw.sim.cells[cp[1]]["controller"] == Types.PLAYER:
				break
			gw._battle_step()
	var fh1: int = gw.flag_hex
	gw._ftue_tick(7.0)  # past step 4's 6 s: no more ghost
	_check(gw.ftue == 4 and gw.battle.issue(Types.PLAYER, {"t": "card", "card": "attack", "target": fh1}), "step 4: «Атака» onto the flag")
	while gw.battle != null and not gw.battle.over:  # then the player goes on attacking
		if gw.battle.tick % 20 == 0 and gw.sim.cells[fh1]["controller"] == Types.PLAYER:
			gw._bot_move()
		gw._battle_step()
	var res1: Dictionary = gw.battle.result()
	_check(War.offensive_stars(res1["captured"], fh1, res1["routed_player_armies"]) == 3, "FTUE war 1 as coached ends on ★★★ (flag taken, %s)" % str(res1["captured"]))
	_check(res1["reason"] == "goals" and (res1["captured"] as Array).size() == gw.FTUE_PEACE1_HEXES and gw.battle.tick < gw.battle.duration_ticks(),
		"FTUE war 1 as coached ends once the flag and %d hexes are taken (08 F09: %s at tick %d)" % [gw.FTUE_PEACE1_HEXES, str(res1["captured"]), gw.battle.tick])
	gw.queue_free()
	await process_frame

	# 5. FTUE: guided first war (canon §14.3)
	g = await _new_tutorial()
	_check(not g.stats.has("ftue_done") and not g.cases.free_started and not g.stats.has("bram_given") and not g._orders_open(),
		"a tutorial game: its end, the free crate's timer, Bram and the orders all wait")
	g._ftue_tick(0.1)
	_check(g.selected >= 0 and g.ui._action2_kind == "declare", "FTUE preselects a war goal (sel %d, kind %s)" % [g.selected, g.ui._action2_kind])
	g._on_action("declare")
	_check(g.ftue == 2, "FTUE step: declared")
	g._on_action("offensive")
	_check(g.ftue == 3 and g.battle.duration_ticks() == 600, "FTUE offensive is 60 s")
	_check(not g.ui._action2.visible, "no «Отступить» in the tutorial's offensive")
	_check(g._hand() == ["attack", "defense"] and g.ui._locked.is_empty(), "FTUE war 1 hand: «Атака» and «Оборона», no locked card")
	_check(g.battle.garrison[g.flag_hex] == 0, "FTUE war 1: the flag's garrison stands down")
	g._ftue_tick(0.1)
	_check(g.ui._ghost_from.x >= 0, "FTUE ghost finger shown")
	var gp: Array = g._ftue_ghost_pair()
	_check(gp.size() == 2 and g.sim.neighbors[gp[1]].has(g.flag_hex), "FTUE ghost leads to a hex beside the flag (%s)" % str(gp))
	_check(g._goal_tag == g.flag_hex and g.ui._coach_lbl.text == g.tr("ftue.3") % g._cell_name(g.flag_hex),
		"FTUE war 1: the coach names the goal and a chip marks it («%s»)" % g.ui._coach_lbl.text)
	var fh5: int = g.flag_hex
	while g.battle != null and not g.battle.over:
		if g.battle.tick % 20 == 0:
			g._bot_move()
		g._battle_step()
	var r5: Dictionary = g.battle.result()
	var c5: Array = r5["captured"]
	_check((r5["reason"] == "goals") == (c5.has(fh5) and c5.size() >= g.FTUE_PEACE1_HEXES),
		"FTUE war 1 ends early only on its targets (%s, %s at tick %d)" % [r5["reason"], str(c5), g.battle.tick])
	g._end_offensive()
	_check(g.ftue == 5 or g.ftue == 2, "FTUE after the offensive (step %d)" % g.ftue)
	if g.ftue == 5:
		g.ui.close_modal()
		g._open_peace()
		_check(g.ftue == 6, "FTUE peace step")
		_check(g.plunder_level == 0, "the first treaty spares: no plunder preselected (08 §8.3 F31; level %d)" % g.plunder_level)
		# the parchment takes the war's whole haul; the points left over say they become the Barons' opinion
		var pk: Array = []
		var spent := 0.0
		var land_v := 0
		for d in g._demands:
			if g._chosen.has(d["id"]):
				pk.append_array(d["hexes"])
				spent += float(d["cost"])
				for h in d["hexes"]:
					land_v += int(g.sim.cells[h]["value"])
		var all_in := true
		for h in pk:
			all_in = all_in and c5.has(h)
		var sc5: float = War.war_score(g.sim, g.war)["score"]
		var bud: Node = g.ui._modal.find_child("budget", true, false)
		var cap5 := String((bud.get_node("label") as Label).text) if bud != null else ""
		# the bar says the treaty's whole opinion change (A-low): the land −2 a value, the leftover +1 a point, mercy +20
		var net5: float = maxf(-2.0 * land_v, -40.0) + Types.round1(sc5 - spent) + float(g.PLUNDER_OPINION[0])
		_check(all_in and pk.size() == mini(c5.size(), g.FTUE_PEACE1_HEXES) and cap5 == g.tr("peace.budget_rest") % [Kit.fmt_dec(spent, 1), Kit.fmt_dec(sc5, 1), g._signed_dec(net5)],
			"the first treaty takes the haul (3 hexes at most), its bar says the opinion it brings (%s of %s; «%s»)" % [str(pk), str(c5), cap5])
		var op5: float = g._opinion_of(MapGen.BARONS)
		var pl5: int = g.plunder_level
		g._sign_peace()
		var want5: float = maxf(-2.0 * land_v, -40.0) + Types.round1(sc5 - spent) + float(g.PLUNDER_OPINION[pl5])
		_check(absf(g._opinion_of(MapGen.BARONS) - op5 - want5) < 0.2,
			"the treaty changes the Barons' opinion as its bar said (%.1f → %.1f, want %+.1f)" % [op5, g._opinion_of(MapGen.BARONS), want5])
		var dove5 := ""
		for it in g._ceremony.get("items", []):
			if String((it as Dictionary).get("icon", "")) == "dove":
				dove5 = String(it.get("text", ""))
		_check(dove5 == g._signed_dec(want5) and absf(want5 - net5) < 0.05,
			"the ceremony's dove says the same change as the bar («%s», bar %s)" % [dove5, g._signed_dec(net5)])
		_check(g.ftue == 0, "FTUE coach hidden during the ceremony")
		for i in 80:
			g._step_ceremony(0.1)
		var dbl = g.ui._modal.find_child("double", true, false) if g.ui._modal != null else null
		_check(dbl == null, "no rewarded «×2» on the tutorial's treaty (canon §14.3: no ads in the FTUE)")
		g._end_ceremony()
		# FTUE 2:30 (canon §14.3): the 3-tap flag comes first, the tour resumes on «Готово»
		_check(g.ui.has_modal() and g.stats.has("flag_wizard"), "the flag wizard opens after the first peace")
		var fw_flag: Dictionary = g.FlagView.random_flag(3)
		g._finish_flag_wizard(fw_flag)
		_check(g.flag == fw_flag, "the wizard's flag becomes the realm's flag")
		# then the name (canon §14.3)
		_check(g.ui.has_modal() and g.ftue != 7, "the name comes after the flag")
		g._finish_name_editor("  Лазурная   Марка ")
		_check(g._state_name(Types.PLAYER) == "Лазурная Марка", "the realm's name is trimmed and shown as its name")
		_check(g.clean_realm_name("Очень длинное название державы") .length() == 20 and g.clean_realm_name("a\nb") == "a b", "names: 20 characters at most, one line")
		_check(g.research.blueprints >= 1 or g.plunder_level == 0, "a plundered peace brings trophy blueprints (%d)" % g.research.blueprints)
		_check(g.ftue == 7, "FTUE resumes after the ceremony (residence step)")
		# never skipped for want of land (playtest 2: 9 hexes after a slow war 1 lost the lesson): the DL2 gate waits
		var lose: Array = []
		for c in g.sim.cells:
			if lose.size() < 2 and int(c["owner"]) == Types.PLAYER and String(c["kind"]) == "plain" and not g._touches_owner(int(c["id"]), MapGen.BARONS) \
					and g.deposits.at(int(c["id"])).is_empty() and c["id"] != g.sim.states[Types.PLAYER]["capital_id"]:
				lose.append(int(c["id"]))
		for h in lose:
			g.sim.cells[h]["owner"] = Types.NOBODY
			g.sim.cells[h]["controller"] = Types.NOBODY
		g._econ_tick()
		g._ftue_tick(0.1)
		_check(g.ftue == 7 and g._player_hexes() < 10 and g.econ.can_upgrade(g.econ.buildings[0], g.now_s()) == "",
			"FTUE step 7 short of land (%d hexes): the DL2 gate waits, the lesson stays" % g._player_hexes())
		for h in lose:
			g.sim.cells[h]["owner"] = Types.PLAYER
			g.sim.cells[h]["controller"] = Types.PLAYER
		g._econ_tick()
		g._open_tab("buildings")
		g._ftue_tick(0.1)
		g._on_building_upgrade(g.econ.buildings[0]["id"])
		g._ftue_tick(0.1)
		g._ftue_tick(0.1)
		var res_id: int = g.econ.buildings[0]["id"]
		_check(g.ftue == 7 and g._residence_busy() and g.ui._coach_lbl.text == g.tr("ftue.7c") and g.econ.speedup_cost(g.econ.buildings[0], g.now_s()) == 0,
			"FTUE step 7c: the upgrade runs and the coach rings its free finish («%s»)" % g.ui._coach_lbl.text)
		g._on_building_speedup(res_id)
		g._ftue_tick(0.1)
		_check(g.ftue == 8 and g.econ.dev_level() == 2 and not g.stats.has("dl_pending") and g._dl_wave_end > Time.get_ticks_msec(),
			"FTUE: the free finish plays the DL2 ceremony at once (the wave), then step 8")
		g._ftue_tick(0.1)
		var dh: int = g._ftue_deposit()
		g._select(dh)
		g._on_action("convoy")
		_check(g.ftue == 9, "FTUE: convoy sent to the gold vein")
		var fh := -1
		for c in g.sim.cells:
			if c["owner"] == Types.PLAYER and c["kind"] == "plain" and int(c["fort"]) == 0 and g.deposits.at(c["id"]).is_empty() and g._touches_owner(c["id"], MapGen.BARONS):
				fh = c["id"]
				break
		if fh < 0:
			for c in g.sim.cells:
				if c["owner"] == Types.PLAYER and c["kind"] == "plain" and int(c["fort"]) == 0 and g.deposits.at(c["id"]).is_empty():
					fh = c["id"]
					break
		g._select(fh)
		g._fort_action()
		_check(g.ftue == 0 and not g._raid.is_empty() and int(g._raid["at"]) - g.now_s() <= g.RAID_SEC, "FTUE: fence started, marauder raid scheduled")
		g._ftue_tick(0.1)
		_check(g.ui._coach.visible and g.ui._coach_lbl.text == g.tr("ftue.raid"), "FTUE: the advisor counts the raid down")
		g.time_offset += 60
		g._econ_tick()
		var raided := false
		for it in g.inbox:
			if String(it["title"]) == "inbox.raid.title":
				raided = true
		_check(raided and g._raid.is_empty(), "FTUE: the raid breaks against the fence")
		_check(g.ftue == 0 and g._raid_hold > 0, "FTUE: the lesson holds on the fence before war 2")
		g.time_offset += g.RAID_HOLD_SEC
		g._econ_tick()
		# war 2 with the Hamlets: encirclement card, then spare or plunder (canon §14.3, 6:00–9:30)
		# war 1 ended on its targets, far from the Hamlets: they come up to our border (ftue.10's provocation)
		_check(g.ftue != 10 or g._hamlets_target() >= 0, "FTUE war 2 has a front with the Hamlets (goal %d)" % g._hamlets_target())
		if g.ftue == 10:
			g.truce = {}
			g._ftue_tick(0.1)
			_check(g.selected >= 0 and g.sim.cells[g.selected]["owner"] == MapGen.HAMLETS, "FTUE war 2: Hamlets goal selected")
			g._on_action("declare")
			_check(g.ftue == 11, "FTUE war 2 declared")
			g._on_action("offensive")
			_check(g.ftue == 12 and g.battle.duration_ticks() == 600, "FTUE war 2 offensive (encircle hint)")
			_check(g._hand() == ["attack", "encircle", "defense"], "FTUE war 2 hand brings «Котёл» in")
			var g2h: int = g.flag_hex
			var g2f := false
			var mil_ok := true
			for a2 in g.armies:
				g2f = g2f or (int(a2["side"]) == MapGen.HAMLETS and int(a2["hex"]) == g2h)
				if int(a2["side"]) == MapGen.HAMLETS:
					mil_ok = mil_ok and int(a2["str"]) <= int(a2["max_str"]) / 2
			_check(g2h >= 0 and g.battle.garrison[g2h] == 0 and not g2f, "FTUE war 2: its goal holds no garrison and no army (08 F27)")
			# the pocket war 2 teaches (08 §8.3 F28–F30): a neck beside the goal whose fall cuts FTUE_POCKET_HEXES hexes of
			# theirs off; step 12's ghost drags «Котёл» onto the neck, a «Котёл: 2» chip sits over the land behind it
			var neck: int = g._ftue_neck
			var pk2: Array = g._ftue_pocket.duplicate()
			g._ftue_tick(0.1)
			_check(neck >= 0 and (neck == g2h or g.sim.neighbors[g2h].has(neck)) and pk2.size() == g.FTUE_POCKET_HEXES and g._pocket_tag == int(pk2[0]) \
				and g.ui._coach_lbl.text == g.tr("ftue.12_pocket") and g.ui._ghost_from.x >= 0 and mil_ok,
				"FTUE war 2 plans a pocket: «Котёл» onto the neck %d cuts off %s (coach «%s»)" % [neck, str(pk2), g.ui._coach_lbl.text])
			# played as coached: «Котёл» onto the neck, then the army the ghost drags — the goal, then the neck
			_check(g.battle.issue(Types.PLAYER, {"t": "card", "card": "encircle", "target": neck}), "FTUE war 2: «Котёл» plays on the neck")
			g._ftue_attacked()
			var lines2 := {}
			while g.battle != null and not g.battle.over:
				if g.battle.tick % 10 == 0:
					g._ftue_tick(0.1)
					lines2[g.ui._coach_lbl.text] = true
					var p2: Array = g._ftue_ghost_pair2()
					var ga = g.battle.army_at(p2[0], Types.PLAYER) if not p2.is_empty() else null
					if ga != null and g.battle.attacking(ga) == null:
						g.battle.issue(Types.PLAYER, {"t": "attack", "army": ga["id"], "target": p2[1]})
				if g.battle.tick % 20 == 0:
					g._bot_move()
				g._battle_step()
			var r52: Dictionary = g.battle.result()
			var c52: Array = r52["captured"]
			var haul2: Array = g._ftue_haul()
			var core2 := MapGen.core_of(g.sim, MapGen.HAMLETS)
			var in_pocket := true
			for h in pk2:
				in_pocket = in_pocket and g._pocket_land().has(h)
			_check(neck == g2h or lines2.has(g.tr("ftue.13_neck")), "FTUE war 2: the coach turns to the neck once the goal is ours (%s)" % str(lines2.keys()))
			_check((r52["reason"] == "goals") == (haul2.size() >= g.FTUE_PEACE2_HEXES and c52.has(g2h)),
				"FTUE war 2 ends once its goal and %d hexes are taken (%s, %s)" % [g.FTUE_PEACE2_HEXES, r52["reason"], str(c52)])
			_check(r52["reason"] == "goals" and in_pocket and haul2.size() == g.FTUE_PEACE2_HEXES and haul2.filter(func(h): return core2.has(h)).is_empty(),
				"FTUE war 2 as coached closes its pocket: the haul is %d hexes, none of their core (captured %s, pocket %s)" % [haul2.size(), str(c52), str(g._pocket_land())])
			g._end_offensive()
			var mil_back := true
			for a2 in g.armies:
				if int(a2["side"]) == MapGen.HAMLETS:
					mil_back = mil_back and int(a2["str"]) > int(a2["max_str"]) / 2
			_check(mil_back and g._ftue_militia.is_empty(), "FTUE war 2's militia gets its strength back after the offensive")
			if g.ftue == 14:
				g.ui.close_modal()
				g._open_peace()
				_check(g.ftue == 15, "FTUE war 2 peace with plunder choice")
				var gold_pk := false
				for d in g._demands:
					gold_pk = gold_pk or (String(d["kind"]) in ["contribution", "reparations"] and g._chosen.has(d["id"]))
				_check(not gold_pk and g._peace_overflow().is_empty() and g.ui._modal.find_child("storage_warn", true, false) == null,
					"FTUE treaty 2: land by default (08 §8.3 F30), no gold package, no storage warning")
				var seal2 = g.ui._seal_btn
				_check(g.plunder_level == -1 and seal2 != null and not seal2.enabled, "FTUE treaty 2: no plunder preselected, the seal waits for the choice (F31)")
				g.ui.plunder_selected.emit(0)
				_check(g.plunder_level == 0 and g.ui._seal_btn.enabled, "FTUE treaty 2: «Пощадить» picked, the seal opens")
				var pk_on := false
				for d in g._demands:
					pk_on = pk_on or (String(d["kind"]) == "pocket" and g._chosen.has(d["id"]))
				_check(pk_on, "FTUE treaty 2 takes the pocket (08 F30: «… + котёл + 1 гекс»)")
				# the store near its cap (playtest 2 review: a gold roll ×2–3 filled it at ceremony 2, «Склад полон»): the
				# tutorial's trophy chest rolls only what the warehouse can hold — the ceremony burns nothing
				g.econ.res["gold"] = int(g.econ.storage_cap()["gold"]) - 300
				var res_b: Dictionary = g.econ.res.duplicate()
				var room_b: Dictionary = g._store_room()
				g._sign_peace()
				var chest_ok := true
				var chest_got := {}
				for rw in g.cases.history[-1]["rewards"]:
					if String(rw["kind"]) == "res":
						for k in rw["res"]:
							chest_got[k] = int(rw["res"][k])
							chest_ok = chest_ok and int(rw["res"][k]) <= int(room_b.get(k, 0)) \
								and int(g.econ.res[k]) == int(res_b[k]) + int(rw["res"][k])
				_check(chest_ok and int(g.econ.res["gold"]) < int(g.econ.storage_cap()["gold"]),
					"FTUE treaty 2 at a near-full store: the trophy chest burns nothing (%s, gold %d)" % [str(chest_got), int(g.econ.res["gold"])])
				_check(g.ftue == 0, "FTUE complete after war 2")
				for i in 80:
					g._step_ceremony(0.1)
				g._end_ceremony()
				_check(g.ui.has_modal() and g.ui._modal.find_child("ok", true, false) != null, "the tutorial closes on Bram's card")
				var crate_left: int = g.cases.free_crate_left(g.now_s())
				_check(crate_left > 0 and crate_left <= 3600 and not g._orders_open() and g._quiet() and not g.cases.free_started \
					and not g.stats.has("ftue_done"),
					"the tutorial's card: the first War Crate within 1 h (%d s), its timer, the orders and the end wait, toasts held" % crate_left)
				g.ui.toast("held")  # (a toast while the card shows waits for its «Вперёд»)
				_check(g.ui._toast_cur.is_empty() or String(g.ui._toast_cur.get("text", "")) != "held", "no toast over the tutorial's card")
				print("NOTE  the tutorial ends at %d / %d hexes" % [g._player_hexes(), g._chapter_goal()])
				_check(g._player_hexes() == 14, "the tutorial ends at 14 / 20 (canon §14.3: «Глава I: 14/20»)")
				var go_btn = g.ui._modal.find_child("ok", true, false)
				go_btn.cb.call()  # «Вперёд»
				_check(g.stats.has("ftue_done") and g.cases.free_started and g.cases.free_crate_left(g.now_s()) == 3600 and g._orders_open()
					and not g._tut_card, "«Вперёд» ends the tutorial: the first War Crate 1 h from then, the orders open")
				g.ui.close_modal()
				_check(g._star_progress(g.STARS[2]) >= 1 and not g.stars_claimed.has("pocket"), "the chapter star «Котёл по договору» can be claimed after the tutorial")
				g._on_world_action("pocket")
				_check(g.stars_claimed.has("pocket"), "the pocket star claimed")
		else:
			print("NOTE  FTUE war 2 skipped (ftue=%d)" % g.ftue)
	# Market (05 §13): card in the Buildings tab, exchange, trader lot once a day
	if g.Market.market_level(g.econ) == 0:
		g.econ._find_type("residence")["upgrade_end"] = 1  # finish a DL2 upgrade (unlocks the Market)
		g.econ.tick(g.sim, g.now_s())
	_check(g.Market.market_level(g.econ) == 1, "Market unlocked at DL2")
	if g.Market.market_level(g.econ) > 0:
		g.mode = g.Mode.MAP
		g._open_tab("buildings")
		var mitems: Array = g._building_items(g.now_s())
		_check(mitems.size() > 0 and mitems[0].has("market"), "Market card leads the Buildings tab")
		g.econ.res["food"] = 3000
		g.econ.res["metal"] = 0
		g.market_sel = {"give": "food", "get": "metal", "pct": 50}
		g._open_market()
		_check(g.ui.has_modal(), "Market opens")
		g._on_market_exchange("food", "metal", 1500)
		_check(int(g.econ.res["metal"]) == 500 and int(g.econ.res["food"]) <= 1500, "Market exchange at 3:1 (food %d, metal %d)" % [int(g.econ.res["food"]), int(g.econ.res["metal"])])
		g.econ.res.merge({"gold": 4000, "food": 4000, "metal": 4000}, true)
		var lot: Dictionary = g.market.lots[0]
		var had: int = g.econ.res[lot["get"]]
		g.econ.res[lot["get"]] = 0
		g._on_market_lot(0)
		_check(int(g.econ.res[lot["get"]]) == int(lot["get_amt"]) and g.market.lots[0]["bought"], "trader lot bought (had %d)" % had)
		g.ui.close_modal()
	# March (canon §8.1): select an army, press March, tap a hex; it walks 20–40 s per hex
	g.ui.close_modal()
	g.war = {}
	g.mode = g.Mode.MAP
	var ma: Dictionary = g._player_armies()[0]
	var dest := -1
	for c in g.sim.cells:
		if int(c["owner"]) == Types.PLAYER and g._army_at(c["id"]).is_empty() and not g.March.route(g.sim, Types.PLAYER, int(ma["hex"]), c["id"]).is_empty():
			if dest < 0 or g.March.route(g.sim, Types.PLAYER, int(ma["hex"]), c["id"])["seconds"] > g.March.route(g.sim, Types.PLAYER, int(ma["hex"]), dest)["seconds"]:
				dest = c["id"]
	g._select(int(ma["hex"]))
	g._on_action("march")
	_check(g._march_pick == int(ma["id"]), "March: waiting for a destination")
	g._on_hex_tapped(Vector2i(int(g.sim.cells[dest]["q"]), int(g.sim.cells[dest]["r"])))
	_check(g.March.is_marching(ma), "March ordered to hex %d" % dest)
	_check(g.selected == dest and g.ui._action2_kind == "march_stop", "the destination stays selected with «Стоп» and the time")
	var secs: int = g.March.seconds_left(g.sim, ma, g.now_s())
	g.time_offset += secs
	g._step_marches()
	_check(int(ma["hex"]) == dest and not g.March.is_marching(ma), "army arrived after %d s" % secs)
	# war outside the tutorial: armies march to the front, the offensive waits for the first arrival
	g.truce = {}
	g.ftue = 0
	var goals: Array = War.recommend_goals(g.sim, MapGen.BARONS, 1)
	if goals.size() > 0:
		for a in g._player_armies():
			a["hex"] = g.sim.states[Types.PLAYER]["capital_id"] if a == ma else a["hex"]
		g._declare(MapGen.BARONS, goals[0])
		var marching := 0
		for a in g._player_armies():
			if g.March.is_marching(a):
				marching += 1
		if marching > 0:
			g._select(-1)
			g._refresh_ui()
			var ready_now := false
			for a in g._player_armies():
				if g._touches_owner(int(a["hex"]), MapGen.BARONS) and not g.March.is_marching(a):
					ready_now = true
			_check(ready_now or g.ui._action2_kind == "", "offensive waits while the armies march (%d marching)" % marching)
			g.time_offset += 600
			g._step_marches()
			g._refresh_ui()
			_check(g.ui._action2_kind == "offensive", "offensive available once the armies reach the front")
		else:
			print("NOTE  no march needed for the Barons front")
	# defeat with heavy plunder: ruin and damaged buildings, repair on the hex (canon §9.14)
	g._apply_defeat(MapGen.BARONS, [])
	# now_s() follows the real clock: a second may tick between the defeat and this check
	_check(absi(g.econ.ruin_left(g.now_s()) - 8 * 3600) <= 2 and g.econ.ruin_pct == 40, "defeat: ruin −40% for 8 h")
	_check(g.econ.damaged.size() > 0, "defeat: %d hex buildings damaged" % g.econ.damaged.size())
	if g.econ.damaged.size() > 0:
		var dh: int = g.econ.damaged.keys()[0]
		g.econ.res.merge({"gold": 99999, "food": 99999, "metal": 99999}, true)
		g._select(dh)
		_check(g.ui._action2_kind == "repair" and g.ui._action_kind == "repair_ad", "damaged hex offers repair (and a free ad repair)")
		g._on_action("repair")
		_check(int(g.econ.damaged.get(dh, 0)) > g.now_s(), "repair under way")
		g.time_offset += 601
		g._econ_tick()
		_check(not g.econ.damaged.has(dh), "building repaired after 10 min")
		var left0: int = g.econ.ruin_left(g.now_s())
		g._select(g.sim.states[Types.PLAYER]["capital_id"])
		_check(g.ui._action_kind == "ruin_halve", "own hex offers to halve the ruin")
		g._on_action("ruin_halve")
		_check(absi(g.econ.ruin_left(g.now_s()) - left0 / 2) <= 1, "ruin halved (%d -> %d s)" % [left0, g.econ.ruin_left(g.now_s())])
	# Marauder camp: 60 s fight, loot, the hex is wild again (canon §5.1, 03 §5.7)
	g.ui.close_modal()
	g.war = {}
	g.mode = g.Mode.MAP
	g._camps_tick(g.now_s())
	_check(g.camps.active.size() >= 2, "marauder camps on the map (%d)" % g.camps.active.size())
	var camp: int = g.camps.active[0]["hex"]
	var near := -1
	for n in g.sim.neighbors[camp]:
		if n >= 0 and Types.is_passable(g.sim.cells[n]) and g._army_at(n).is_empty():
			near = n
			break
	g.sim.cells[near]["owner"] = Types.PLAYER
	g.sim.cells[near]["controller"] = Types.PLAYER
	var fa: Dictionary = g._player_armies()[0]
	# no army beside the camp: «Разбить лагерь» is a lock with the reason, «Марш» sends the nearest army (B-L: red and
	# enabled, its tap only toasted)
	var cfar: Array = g._player_armies().filter(func(a): return g.sim.neighbors[camp].has(int(a["hex"])))
	if cfar.is_empty():
		g._select(camp)
		var cm: Dictionary = g._camp_marcher(camp)
		_check(String(g.ui._primary_args[0]) == "camp_army" and String(g.ui._primary_args[2]) == "lock" and String(g.ui._primary_args[6]) == g.tr("camp.need_army_near") \
				and g.ui._action_kind == ("camp_march" if not cm.is_empty() else ""),
			"no army by the camp: the raid is locked with its reason, «Марш» offered (%s / %s)" % [str(g.ui._primary_args.slice(0, 3)), g.ui._action_kind])
		if not cm.is_empty():
			g._on_action("camp_march")
			_check(g._march_dest.get(int(cm["army"]["id"]), -1) == int(cm["hex"]) or g.sim.neighbors[camp].has(int(cm["army"]["hex"])),
				"«Марш» sends the nearest army next to the camp")
			g._stop_marches()
	fa["hex"] = near
	fa["str"] = fa["max_str"]
	g._select(camp)
	_check(g.ui._action2_kind == "camp", "camp offers a raid")
	g._colonize(camp)
	_check(g.colonizing.is_empty() or not g.colonizing.has(camp), "a camp blocks colonization")
	g.econ.res.merge({"gold": 0, "food": 0, "metal": 0}, true)  # room in the warehouse for the loot
	var res_before: Dictionary = g.econ.res.duplicate()
	g._on_action("camp")
	_check(g.mode == g.Mode.BATTLE and g.battle != null and g.battle.duration_ticks() == 600, "camp fight is 60 s")
	g.battle.issue(Types.PLAYER, {"t": "attack", "army": fa["id"], "target": camp})
	while g.battle != null and not g.battle.over:
		g._battle_step()
	g._end_camp_fight()
	_check(g.camps.at(camp).is_empty() and g.sim.cells[camp]["owner"] == Types.NOBODY and g.sim.cells[camp]["controller"] == Types.NOBODY, "camp destroyed, hex wild again")
	_check(int(fa["hex"]) != camp, "the army does not enter the wild hex")
	var gained := 0
	for r in ["gold", "food", "metal"]:
		gained += int(g.econ.res[r]) - int(res_before[r])
	_check(gained > 0, "camp loot credited (+%d)" % gained)
	# fog of war (canon §3.1): far enemy hexes are out of sight, near ones in sight
	var fog: Dictionary = g._fog_visible()
	var cap0: int = g.sim.states[Types.PLAYER]["capital_id"]
	_check(fog.has(cap0) and fog.size() < g.sim.cells.size(), "fog of war: %d of %d hexes in sight" % [fog.size(), g.sim.cells.size()])
	# Chapter II: «Мир расширяется» (canon §12.1, 02 §17)
	g.ui.close_modal()
	var n_before: int = 61
	if g.chapter == 1:
		g._world_expansion()
	_check(g.chapter == 2 and g.sim.states.size() == 6 and g._land_count() == 90, "world expanded to 90 land hexes, 2 new states")
	_check(g._chapter_goal() == 36 and g._colonize_seconds() == 300, "chapter II goal 36, colonization 5 min")
	var wi: Array = g._world_items().filter(func(x): return not (String(x.get("id", "")).begins_with("order") or String(x.get("id", "")).begins_with("weekly") or String(x.get("id", "")) in ["pass", "calendar"]))
	_check(wi.size() == 1 + 8 + 9 and String(wi[1]["id"]) == "c2_port", "World tab lists chapter II stars first (%d items)" % wi.size())
	var oi: Array = g._world_items().filter(func(x): return String(x.get("id", "")).begins_with("order"))
	_check(oi.size() == 4, "the World tab opens with today's 3 orders and the bonus")
	# the day's roll depends on the date: earlier steps of this test may already have finished an order, so
	# use the first one still open; a finished or claimed order never offers the swap
	var sw_i := -1
	for i in g.orders.list.size():
		var done_i: bool = g.orders.done(i, g.stats) or bool(g.orders.list[i]["claimed"])
		_check(bool(oi[i].get("swap", false)) == (not done_i), "order %d: swap offered only while unfinished" % i)
		if sw_i < 0 and not done_i:
			sw_i = i
	if sw_i >= 0:
		var code0: String = g.orders.list[sw_i]["code"]
		g._on_world_action("swap:order:%d" % sw_i)
		_check(g.orders.swapped and String(g.orders.list[sw_i]["code"]) != code0, "the free swap replaces the order")
		_check(not g._order_items().any(func(x): return bool(x.get("swap", false))), "one free swap a day")
	g._orders_chip()
	_check(g.hud._orders_chip.visible and g.hud._orders_lbl.text.ends_with("/3"), "the HUD chip shows today's orders")
	# «Державный патент» (09 §9.13): perks while active
	var pt_b0: int = g.econ.builders + g.econ.bonus_builders
	g._on_buy_sku("iap_sub_trial")
	g.ui.close_modal()
	_check(g.patent.active(g.now_s()) and g.econ.bonus_builders == 1 and g.deposits.bonus_convoys == 1, "the subscription adds a builder and a convoy")
	_check(g.Economy.speedup_price(500) == 0 and g.Economy.speedup_price(700) > 0, "timers ≤10 min finish for free")
	var pt_rv0: int = g.econ.res["raivite"]
	g._claim_patent_daily()
	_check(int(g.econ.res["raivite"]) == pt_rv0 + 40, "the day's 40 Raivites")
	_check(g.cases.royal_keys >= 1 and g.cases.owned_cosmetics.has("cos_frame_patent_month"), "the week's Royal key and the month's frame")
	g._open_patent()
	_check(g.ui.has_modal(), "the subscription screen opens")
	g.ui.close_modal()
	g.patent.until = 0
	g._patent_tick(g.now_s())
	_check(g.econ.bonus_builders == 0 and g.Economy.speedup_price(500) > 0 and g.econ.builders + g.econ.bonus_builders == pt_b0, "perks stop when it ends")
	# the intro Patent offer on the 3rd rewarded video of a day, from D2 (09 §9.13.2)
	g.installed_at = g.now_s() - 2 * 86400
	g.ad_counts = {}
	g.intro_offer_day = -1
	var io_trial: bool = g.patent.trial_used
	g.patent.trial_used = false
	g._rewarded("t_a", 5)
	g._rewarded("t_b", 5)
	_check(g.intro_offer_day == -1, "no offer before the 3rd video")
	g._rewarded("t_c", 5)
	await process_frame
	_check(not g._payments_enabled() or (g.intro_offer_day >= 0 and g.ui.has_modal()), "the 3rd video of the day brings the intro offer")
	g.ui.close_modal()
	g.patent.trial_used = io_trial
	g.ad_counts = {}
	# «Летопись державы» (07 §7): the first peace and the hexes are counted, the book opens, a reward is taken
	g._chronicle_tick()
	_check(g.chronicle.reached.has("ach_first_peace"), "the Chronicle counts the first peace")
	g._open_chronicle()
	_check(g.ui.has_modal(), "the Chronicle opens from the book")
	var chr_rv: int = g.econ.res["raivite"]
	if g.chronicle.can_claim("ach_first_peace"):
		g._claim_chronicle("ach_first_peace")
	_check(g.chronicle.claimed.has("ach_first_peace") and int(g.econ.res["raivite"]) >= chr_rv + 25, "its reward is paid")
	g.ui.close_modal()
	# the profile (10 §4.23): «Летопись N/40» and the latest achievements, newest first
	_check(not g.chronicle.recent(3).is_empty() and g.chronicle.recent(3)[0] == g.chronicle.order[g.chronicle.order.size() - 1], "the latest achievement comes first")
	g._open_profile()
	_check(g.ui.has_modal(), "the profile opens from the ruler's portrait")
	g.ui.close_modal()
	# the flag constructor (10 §4.23): a random flag is valid, «Готово» keeps it and it survives a save
	var fl_rand: Dictionary = g.FlagView.random_flag(7)
	_check(fl_rand["c1"] != fl_rand["c2"] and g.FlagView.DIVISIONS.has(fl_rand["div"]) and int(fl_rand["c1"]) < g.FlagView.FIELD.size(), "a random flag: two field colours from the field palette")
	g._open_flag_editor(fl_rand)
	_check(g.ui.has_modal(), "the flag constructor opens")
	g.flag = fl_rand
	var gfl: Node = load("res://scenes/main.tscn").instantiate()
	gfl.save_enabled = false
	Save.apply(gfl, Save.save(g))
	_check(gfl.flag["div"] == fl_rand["div"] and int(gfl.flag["c2"]) == int(fl_rand["c2"]), "the flag survives a save")
	gfl.free()
	g.ui.close_modal()
	# commanders (04 §15): Bram after the tutorial, a level for shards + gold, the collection and the card open
	_check(g._cmd_level("cmd_bram") >= 1, "Sergeant Bram is open after the tutorial's war")
	var cm_items: Array = g._army_items(g.now_s()).filter(func(x): return x.has("commanders"))
	_check(cm_items.size() == 1 and int(cm_items[0]["commanders"][0]) >= 1, "the Army tab shows the commanders card")
	g.cases.shards["cmd_bram"] = int(g.cases.shards["cmd_bram"]) + 1
	g.econ.res["gold"] = maxi(int(g.econ.res["gold"]), 1000)
	var cm_gold: int = g.econ.res["gold"]
	var cm_lvl: int = g._cmd_level("cmd_bram")
	g._upgrade_commander("cmd_bram")
	_check(g._cmd_level("cmd_bram") == cm_lvl + 1 and int(g.econ.res["gold"]) == cm_gold - 250, "level 2 for a shard and 250 gold")
	g._open_commanders()
	_check(g.ui.has_modal(), "the collection opens")
	g._open_commander("cmd_rai")
	_check(g.ui.has_modal(), "a locked commander's card opens")
	g.ui.close_modal()
	_check((g._case_ctx()["commanders_maxed"] as Array).is_empty(), "nobody is maxed yet")
	# assignment (04 §15.6) and the passive in battle (04 §15.2)
	var cm_army: int = int(g._player_armies()[0]["id"])
	g._open_cmd_picker(cm_army)
	_check(g.ui.has_modal(), "the commander picker opens from the army card")
	g._assign_commander(cm_army, "cmd_bram")
	_check(g.commanders.cmd_of(cm_army) == "cmd_bram", "Bram leads the first army")
	var cm_opts: Dictionary = g._apply_commanders()
	_check(int(g._army_by_id(cm_army).get("cmd_atk", 0)) > 0 and cm_opts.is_empty(), "his infantry bonus is on the army; nothing battle-wide")
	var cm_card: Array = g._army_items(g.now_s()).filter(func(x): return int(x["id"]) == cm_army)
	_check(cm_card.size() == 1 and cm_card[0]["cmd"] == "cmd_bram", "the army card shows his portrait")
	# the hand (03 §5.2): «Атака» + 4 slots of the player's choice
	var hand0: Array = g._hand_display()
	_check(hand0[0] == "attack" and hand0.size() <= 1 + g._hand_slots(), "the default hand: «Атака» + slots")
	var res_b: Dictionary = g.econ._find_type("residence")
	var lvl_b: int = int(res_b["level"])
	res_b["level"] = 6
	_check(g._default_hand() == ["attack", "breakthrough", "airstrike", "encircle", "defense"] and g._hand_teaser() == "landing",
		"DL6 default hand: open cards only (4 of 5 slots), «Десант» only teases (%s)" % str(g._default_hand()))
	res_b["level"] = lvl_b
	g._open_hand_picker()
	_check(g.ui.has_modal(), "the hand picker opens")
	g.ui.close_modal()
	g.hand_pick = ["defense"]
	_check(g._hand_display() == ["attack", "defense"], "a chosen hand replaces the default")
	g.hand_pick = ["missile", "defense"]
	_check(not g._hand_display().has("missile") or g.econ.dev_level() >= 8, "cards above the DL stay out of the hand")
	var hitems: Array = g._army_items(g.now_s()).filter(func(x): return x.has("hand"))
	_check(hitems.size() == 1 and (hitems[0]["hand"] as Array)[0] == "attack", "the Army tab shows the hand card")
	g.hand_pick = []
	g.calendar = g.Calendar.new()
	g._calendar_tick(g.now_s())
	_check(g.calendar.pending and not g.ui.has_modal(), "a calendar day is credited (no auto screen in tests)")
	var bld: int = g.econ.builders
	var cal_crates: int = g.cases.free_crates
	g._open_calendar()
	_check(g.ui.has_modal(), "the calendar screen opens")
	g._claim_calendar(true)
	_check(not g.calendar.pending and g.cases.free_crates == cal_crates + 2, "day 1 taken with ×2 (2 crates)")
	g.calendar.last_day -= 1
	g._calendar_tick(g.now_s())
	g._claim_calendar(true)
	_check(g.calendar.pending, "no ×2 on a key day")
	g._claim_calendar(false)
	_check(g.econ.builders == bld + 1, "day 2: the 3rd builder")
	g.ui.close_modal()
	# day 26: «15 осколков на выбор» — the player picks the commander
	g.calendar.credited = 25
	g.calendar.pending = false
	g.calendar.last_day -= 1
	g._calendar_tick(g.now_s())
	g._claim_calendar(false)
	_check(g.calendar.choice == 15 and g.ui.has_modal(), "day 26 asks whom to give the shards")
	var kort0 := int(g.cases.shards.get("cmd_kort", 0))
	g._give_cal_shards("cmd_kort")
	_check(g.calendar.choice == 0 and int(g.cases.shards.get("cmd_kort", 0)) == kort0 + 15, "the chosen commander gets 15 shards")
	g.ui.close_modal()
	g.stats["camps"] = int(g.stats_base.get("camps", 0)) + 3
	var rvs: int = g.econ.res["raivite"]
	g._on_world_action("c2_camps")
	_check(g.stars_claimed.has("c2_camps") and int(g.econ.res["raivite"]) == rvs + 10, "chapter II star claimed")
	# alliance with the River League (canon §10.7): opinion 50+ (Owl 40+), DL3+
	g.truce = {}
	g.war = {}
	if g.econ.dev_level() < 3:
		g.econ._find_type("residence")["level"] = 3
	g.opinion[4] = 10.0
	_check(g._ally_reason(4) != "", "no alliance at low opinion")
	g._opinion_set(4, 45.0)
	_check(g._ally_reason(4) != "", "no alliance at opinion 45: the canon's 50 for every archetype (06 §13.1; %.1f)" % g._opinion_of(4))
	g._opinion_set(4, 50.0)
	g._on_diplomacy_action(4, "ally")
	_check(g.allies.has(4) and int(g.stats.get("alliances", 0)) >= 1, "alliance with the River League signed")
	_check(g.sim.player_allies.has(4), "the ally's land opens to our marches")
	g.ui.close_modal()
	g.mode = g.Mode.MAP
	g.ai_wars = [{"a": 2, "b": 4, "until": g.now_s() + 86400, "next": g.now_s() + 7200}]
	g.econ.res["gold"] = maxi(int(g.econ.res["gold"]), 5000)
	var op4: float = g._opinion_of(4)
	g._ally_asks(4, 2)
	_check(g.ui.has_modal(), "the ally asks for help")
	g.ui.close_modal()
	g.ai_wars = []
	# «Призыв»: an ally with opinion 60+ joins our offensive war for −5 opinion
	var wg: Array = War.recommend_goals(g.sim, 2, 1)
	g.war = War.declare_war(g.sim, 2, wg[0] if wg.size() > 0 else 0)
	g._opinion_set(4, 70.0)
	_check(g._can_call(4), "the ally can be called into our war")
	g._on_diplomacy_action(4, "call")
	_check(g.war.has("called_4") and absf(g._opinion_of(4) - 65.0) < 0.6, "ally called in (opinion %.0f)" % g._opinion_of(4))
	g.war = {}
	# AI–AI alliances (minimal model)
	if not g._states_touch(MapGen.BARONS, MapGen.HAMLETS):
		var pc := MapGen.core_of(g.sim, Types.PLAYER)
		for c in g.sim.cells:
			if int(c["owner"]) == MapGen.BARONS and not MapGen.core_of(g.sim, MapGen.BARONS).has(c["id"]):
				for n in g.sim.neighbors[c["id"]]:
					if n >= 0 and Types.is_passable(g.sim.cells[n]) and int(g.sim.cells[n]["owner"]) == Types.NOBODY and not pc.has(n):
						g.sim.cells[n]["owner"] = MapGen.HAMLETS
						g.sim.cells[n]["controller"] = MapGen.HAMLETS
						break
				if g._states_touch(MapGen.BARONS, MapGen.HAMLETS):
					break
	g.ai_wars = []
	var aia := false
	for k in 60:
		g.ai_alliance_check = 0
		g.time_offset += 86400
		g._ai_alliances_tick(g.now_s())
		if not g.ai_alliances.is_empty():
			aia = true
			break
	_check(aia, "AI neighbours sign an alliance (%s)" % str(g.ai_alliances))
	var dip: Array = g._diplomacy_items(g.now_s()).filter(func(x): return not x.has("kind"))
	_check(dip.size() == 4, "diplomacy lists 4 neighbours (after the alarm bar)")
	var forts := 0
	for c in g.sim.cells:
		if int(c["owner"]) == 5 and int(c["fort"]) > 0:
			forts += 1
	_check(forts >= 2, "the Order of Stone builds forts (%d)" % forts)
	# AI DL grows by 1 every 6 days up to the cap (canon §9.16): Barons in chapter II cap at 3, the League at 4
	g._ai_growth(g.now_s())
	var b_dl: int = g.sim.states[2]["dev_level"]
	for i in 6:
		g.time_offset += 6 * 86400 + 1
		g._ai_growth(g.now_s())
	_check(int(g.sim.states[2]["dev_level"]) == 3 and int(g.sim.states[4]["dev_level"]) == 4, "AI DL growth to the caps (Barons %d -> %d, League -> %d)" % [b_dl, int(g.sim.states[2]["dev_level"]), int(g.sim.states[4]["dev_level"])])
	# AI wars of chapter II (canon §9.11, §10.4): counter-strike after an offensive, auto-defense, ultimatums
	g.ui.close_modal()
	g.truce = {}
	g.mode = g.Mode.MAP
	var bg: Array = War.recommend_goals(g.sim, MapGen.BARONS, 1)
	if bg.size() > 0:
		g.ftue = 0
		g._declare(MapGen.BARONS, bg[0])
		g.war.erase("strike_at")
		g.time_offset += 3600
		g._step_marches()
		g._start_offensive()
		while g.battle != null and not g.battle.over:
			if g.battle.tick % 20 == 0:
				g._bot_move()
			g._battle_step()
		g._end_offensive()
		_check(g.war.has("strike_at"), "the AI announces a counter-strike after the offensive")
		g.ui.close_modal()
		g._set_mode(g.Mode.WAR)
		var occ0 := 0
		for c in g.sim.cells:
			if int(c["owner"]) == Types.PLAYER and int(c["controller"]) != Types.PLAYER:
				occ0 += 1
		var d0: int = int(g.stats.get("defenses", 0))
		g._resolve_strike()
		var occ1 := 0
		for c in g.sim.cells:
			if int(c["owner"]) == Types.PLAYER and int(c["controller"]) != Types.PLAYER:
				occ1 += 1
		_check(int(g.stats.get("defenses", 0)) == d0 + 1 or occ1 > occ0, "auto-defense resolved (defenses %d -> %d, our hexes occupied %d -> %d)" % [d0, int(g.stats.get("defenses", 0)), occ0, occ1])
		var core_safe := true
		for id in MapGen.core_of(g.sim, Types.PLAYER):
			if int(g.sim.cells[id]["controller"]) != Types.PLAYER:
				core_safe = false
		_check(core_safe, "the player's core is never taken in auto-defense")
		# the Barons (Wolf) ask for peace once the player holds ≥75% of the front
		var bcore := MapGen.core_of(g.sim, MapGen.BARONS)
		for c in g.sim.cells:
			if (int(c["owner"]) == MapGen.BARONS and not bcore.has(c["id"]) or int(c["owner"]) == Types.PLAYER) and Types.is_passable(c):
				c["controller"] = Types.PLAYER
		g.ui.close_modal()
		g._set_mode(g.Mode.WAR)
		g.war["battles"] = 10
		g._peace_offer()
		_check(g.war.has("offered") and g.ui.has_modal(), "the Wolf offers peace at %d%% control" % int(War.war_score(g.sim, g.war)["control"]))
		g.ui.close_modal()
		War.white_peace(g.sim)
		g._finish_war(MapGen.BARONS, "")
	g.truce = {}
	g.ultimatum = {}
	g.ultimatum_at = -1
	g.mode = g.Mode.MAP
	for a in g._player_armies():
		a["max_str"] = 1000  # a weak player: every neighbour is stronger
	var issued := false
	for day in 40:
		g.time_offset += 86400
		for s2 in g._ai_states():
			g.ult_check[s2] = 0
		g._ultimatum_rolls(g.now_s())
		if not g.ultimatum.is_empty():
			issued = true
			break
	_check(issued, "a stronger neighbour issues an ultimatum by its archetype chance")
	g.ultimatum = {}
	g.ui.close_modal()
	# AI colonization: one wild hex per state every 3 h (02 §10.2)
	g.stats["peaces"] = maxi(1, int(g.stats.get("peaces", 0)))
	g.ftue = 0
	g._ai_colonize(g.now_s())  # finishes settlements left from earlier time jumps
	g._ai_colonize(g.now_s())  # and starts new ones
	var ai_land0 := 0
	for c in g.sim.cells:
		if int(c["owner"]) >= 2:
			ai_land0 += 1
	_check(g.ai_colonizing.size() >= 1, "AI states start settling wild hexes (%d)" % g.ai_colonizing.size())
	var claimed: int = g.ai_colonizing.values()[0]["hex"] if g.ai_colonizing.size() > 0 else -1
	if claimed >= 0:
		var gold_pre: int = g.econ.res["gold"]
		g._colonize(claimed)
		_check(not g.colonizing.has(claimed) and int(g.econ.res["gold"]) == gold_pre, "a hex the AI settles is reserved")
	g.time_offset += 3 * 3600 + 1
	g._ai_colonize(g.now_s())
	var ai_land1 := 0
	for c in g.sim.cells:
		if int(c["owner"]) >= 2:
			ai_land1 += 1
	_check(ai_land1 > ai_land0, "AI land grows by colonization (%d -> %d)" % [ai_land0, ai_land1])
	# AI against AI (canon §10.10): a war between neighbours moves border hexes, peace annexes them
	g.war = {}
	g.ai_alliances = {}
	g.ai_alliance_check = 1 << 40  # no new alliances during this check
	if not g._states_touch(MapGen.BARONS, MapGen.HAMLETS):
		# give the two a shared border for the test: a non-core wild/AI hex next to the Barons goes to the Hamlets
		var pcore := MapGen.core_of(g.sim, Types.PLAYER)
		for c in g.sim.cells:
			if int(c["owner"]) == MapGen.BARONS and not MapGen.core_of(g.sim, MapGen.BARONS).has(c["id"]):
				for n in g.sim.neighbors[c["id"]]:
					if n >= 0 and Types.is_passable(g.sim.cells[n]) and int(g.sim.cells[n]["owner"]) in [Types.NOBODY, MapGen.HAMLETS] and not pcore.has(n):
						g.sim.cells[n]["owner"] = MapGen.HAMLETS
						g.sim.cells[n]["controller"] = MapGen.HAMLETS
						break
				if g._states_touch(MapGen.BARONS, MapGen.HAMLETS):
					break
	var started_aw := false
	for k in 60:
		g.ai_war_check = 0
		g.time_offset += 6 * 3600
		g._ai_wars_tick(g.now_s())
		if not g.ai_wars.is_empty():
			started_aw = true
			break
	_check(started_aw, "neighbouring AI states go to war")
	if started_aw:
		var aw: Dictionary = g.ai_wars[0]
		var aa: int = aw["a"]
		var bb: int = aw["b"]
		var occ := 0
		g.time_offset += 7 * 3600
		g._ai_wars_tick(g.now_s())
		for c in g.sim.cells:
			if (int(c["owner"]) == aa and int(c["controller"]) == bb) or (int(c["owner"]) == bb and int(c["controller"]) == aa):
				occ += 1
		_check(occ >= 1, "the AI front moves (%d hexes occupied)" % occ)
		var cores_ok := true
		for s3 in [aa, bb]:
			for id in MapGen.core_of(g.sim, s3):
				if int(g.sim.cells[id]["controller"]) != s3:
					cores_ok = false
		_check(cores_ok, "AI cores never change hands")
		g.time_offset += 50 * 3600
		g._ai_wars_tick(g.now_s())
		var still := 0
		for c in g.sim.cells:
			if int(c["owner"]) != int(c["controller"]) and int(c["owner"]) >= 2 and int(c["controller"]) >= 2:
				still += 1
		_check(g.ai_wars.is_empty() and still == 0, "AI peace annexes the occupied hexes")
	Save.save(g)
	var g3: Node = load("res://scenes/main.tscn").instantiate()
	g3.save_enabled = false
	_check(Save.apply(g3, Save.read()) and g3.sim.cells.size() == g.sim.cells.size() and g3.chapter == 2, "chapter II save restores the ring (%d -> %d cells)" % [n_before, g3.sim.cells.size()])
	g3.free()
	# Chapter III «Континент» (canon §12.1, 07 §3.7)
	g.war = {}
	g.ai_wars = []
	g.ui.close_modal()
	g._world_expansion()
	g.ui.close_modal()
	_check(g.chapter == 3 and g.sim.states.size() == 9 and g._land_count() == 160, "world expanded to 160 land hexes, 3 new states (%d)" % g._land_count())
	_check(g._chapter_goal() == 56 and g._colonize_seconds() == 900, "chapter III goal 56, colonization 15 min")
	_check(bool(g.sim.states[6]["hegemon"]) and int(g.sim.states[6]["dev_level"]) == 6 and int(g.sim.states[7]["dev_level"]) == 5, "Alvaria the hegemon at DL6, Saren at DL5")
	var wi3: Array = g._world_items().filter(func(x): return not (String(x.get("id", "")).begins_with("order") or String(x.get("id", "")).begins_with("weekly") or String(x.get("id", "")) in ["pass", "calendar"]))
	_check(String(wi3[1]["id"]) == "c3_factory", "World tab lists chapter III stars first")
	g._ensure_armies_for(6)
	var heg_ok := false
	for a in g.armies:
		if int(a["side"]) == 6:
			heg_ok = int(a["max_str"]) > 0
	_check(heg_ok, "the hegemon fields armies")
	# a factory of ours: 10 metal/h and −5% timers from DL5
	var fac := -1
	for c in g.sim.cells:
		if c["kind"] == "factory":
			fac = c["id"]
			break
	_check(fac >= 0, "ring III has factories")
	var cost0: int = int(g.econ.build_cost("tower")["seconds"])
	g.sim.cells[fac]["owner"] = Types.PLAYER
	g.sim.cells[fac]["controller"] = Types.PLAYER
	g.econ._find_type("residence")["level"] = 5
	g._econ_tick()
	_check(g.econ.factory_pct() == 5 and int(g.econ.build_cost("tower")["seconds"]) == cost0 * 95 / 100, "a factory cuts timers by 5%% (%d -> %d)" % [cost0, int(g.econ.build_cost("tower")["seconds"])])
	_check(g._star_progress(g.STARS_3[0]) == 1, "«Индустриализация» counts the factory")
	# Territory swap (canon §10.9, 06 §15): opinion ≥ 0, cores excluded, one per 24 h, the AI's valuation
	var sw_state := -1
	var sw_get := -1
	var sw_give := -1
	for st in g._ai_states():
		g.opinion[st] = 30.0
		for c in g.sim.cells:
			if sw_state < 0 and g._swappable(c["id"], st) and g._touches_player(c["id"]):
				sw_state = st
				sw_get = c["id"]
	for c in g.sim.cells:
		if sw_give < 0 and g._swappable(c["id"], Types.PLAYER):
			sw_give = c["id"]
	_check(sw_state >= 0 and sw_give >= 0, "a swap pair exists (%d: %d <-> %d)" % [sw_state, sw_give, sw_get])
	if sw_state >= 0 and sw_give >= 0:
		_check(g._swap_reason(sw_state) == "", "swap allowed at opinion 30")
		var cap_s: int = g.sim.states[sw_state]["capital_id"]
		_check(not g._swappable(cap_s, sw_state) and not g._swappable(g.sim.states[Types.PLAYER]["capital_id"], Types.PLAYER), "capitals never swap")
		g.econ.res["gold"] = 100000
		g._swap = {"state": sw_state, "give": [], "get": []}
		g._swap_pick(sw_give)
		g._swap_pick(sw_give)
		_check((g._swap["give"] as Array).is_empty(), "a second tap drops the hex from the package")
		g._swap_pick(sw_give)
		g._swap_pick(sw_get)
		_check(g.ui.has_modal() and (g._swap["give"] as Array) == [sw_give], "both sides picked: the offer panel")
		var b0: int = g._border_len(sw_state)
		var b1: int = g._border_len(sw_state, g._swap_over(sw_state, [sw_give], [sw_get]))
		_check(b0 > 0 and b1 >= 0, "border length before %d, after %d" % [b0, b1])
		g.ui.close_modal()
		g._swap = {}
		var terms: Dictionary = g._swap_terms(sw_state, [sw_give], [sw_get])
		_check(g._swap_execute(sw_state, [sw_give], [sw_get], int(terms["gold"]), float(terms["overpay"])), "the swap goes through")
		_check(int(g.sim.cells[sw_get]["owner"]) == Types.PLAYER and int(g.sim.cells[sw_give]["owner"]) == sw_state, "the hexes changed hands")
		_check(g._swap_reason(sw_state) != "", "one swap per 24 h")
		_check(int(g.stats.get("swaps", 0)) >= 1, "«Выгодная сделка» counts the swap")
	# AI swap offers (06 §9.1 S4): the Fox looks every 48 h for a border-straightening package
	var fox := -1
	for st in g._ai_states():
		if String(g.sim.states[st]["archetype"]) == "fox" and g._swap_reason(st) == "":
			fox = st
	_check(not g.SWAP_OFFER_SEC.has("wolf") and int(g.SWAP_OFFER_SEC["fox"]) == 48 * 3600, "the Fox offers every 48 h, the Wolf never")
	_check(fox >= 0, "a Fox neighbour to offer swaps")
	if fox >= 0:
		var pk: Dictionary = g._ai_swap_package(fox)
		var bent := {}  # hex -> [owner, controller] before the border was bent
		if pk.is_empty():
			# a straight border leaves nothing to straighten: bend it into a salient the swap_ai demo's way (the owners
			# go back after the offer, the tests below see the same world)
			for c in g.sim.cells:
				bent[c["id"]] = [c["owner"], c["controller"]]
			g._demo_salient(fox)
			pk = g._ai_swap_package(fox)
		_check(not pk.is_empty(), "the Fox finds a package that asks no top-up%s" % (" (border bent)" if not bent.is_empty() else ""))
		if not pk.is_empty():
			var t_ai: Dictionary = g._swap_terms(fox, pk["give"], pk["get"])
			var cut: int = g._border_len(fox) - g._border_len(fox, g._swap_over(fox, pk["give"], pk["get"]))
			_check(cut >= 0 and (pk["give"] as Array).size() <= 2 and (pk["get"] as Array).size() <= 2 and float(t_ai["pay"]) <= 0.0 and int(t_ai["gold"]) == 0,
				"the AI package (%d for %d) shortens the border by %d edges and asks no top-up (B4)" % [(pk["give"] as Array).size(), (pk["get"] as Array).size(), cut])
			g.swap_offer = {"state": fox, "give": pk["give"], "get": pk["get"], "until": g.now_s() + 86400, "auto": false}
			g._show_swap_offer()
			_check(g.ui.has_modal() and not g.swap_offer.is_empty(), "the AI offer opens")
			g.ui.close_modal()
			for h in pk["give"] + pk["get"]:
				g.map_view.hex_label(h, "")
		for id in bent:
			if int(g.sim.cells[id]["owner"]) != int(bent[id][0]) or int(g.sim.cells[id]["controller"]) != int(bent[id][1]):
				g.sim.cells[id]["owner"] = bent[id][0]
				g.sim.cells[id]["controller"] = bent[id][1]
				g.map_view.refresh_hex(id)
		g.swap_offer_at[fox] = 0
		g.swap_offer = {}
		g._ai_swap_tick(g.now_s())
		_check(int(g.swap_offer_at[fox]) > g.now_s(), "the Fox's next look is scheduled")
		g.swap_offer = {}
	# Non-aggression pact (06 §11): 8 h of gold, 48 h, archetype threshold, one at a time, no war in the pair
	var pst: int = g._ai_states()[0]
	g.ultimatum = {}  # an open ultimatum blocks a pact with its sender; the daily rolls depend on the clock
	g._opinion_set(pst, 10.0)
	g.econ.res["gold"] = 100000
	_check(g._pact_reason(pst) == "", "a pact can be signed at opinion 10 (%s, %.1f)" % [g._pact_reason(pst), g._opinion_of(pst)])
	g._on_diplomacy_action(pst, "pact")
	_check(g._pact_left(pst) > 0 and not bool(g._diplomacy_items(g.now_s()).filter(func(x): return int(x.get("id", -1)) == pst)[0]["can_war"]), "the pact holds: no war with them")
	_check(g._pact_reason(g._ai_states()[1]) != "", "only one pact at a time")
	g.pacts = {}
	# Threat and coalitions (canon §10.8): threshold 50 in chapter III; ≥50% — wary, 100% — a coalition forms
	g.truce = {}
	g.war = {}
	g.allies = []
	g._set_mode(g.Mode.MAP)
	g.threat = 30.0
	g.threat_at = g.now_s()
	_check(absf(g.alarm() - 0.6) < 0.01 and g._ally_reason(4) == g.tr("ally.alarm"), "alarm 60 percent: no new alliances")
	for st in g._ai_states():
		g.opinion[st] = -40.0
	g.threat = 60.0
	g.coalition_last = 0
	g._coalition_tick(g.now_s())
	_check(not g.coalition.is_empty() and (g.coalition["members"] as Array).size() >= 2, "a coalition forms at 120%% (%s)" % str(g.coalition.get("members", [])))
	var dipc: Array = g._diplomacy_items(g.now_s())
	_check(String(dipc[0].get("kind", "")) == "alarm" and int(dipc[0]["pct"]) == 120, "Diplomacy shows the alarm bar first")
	g.time_offset += 12 * 3600 + 60
	g._coalition_tick(g.now_s())
	_check(not g.war.is_empty() and g.war.has("coalition") and g.war.has("strike_at"), "after 12 h the coalition declares war with a first strike")
	_check(int(g.war["enemy"]) == g._coalition_leader(g.war["coalition"]), "the leader fights the war")
	# members' shares of the war score (06 §14.6), battles on a member's land and a member asking for a separate
	# peace (06 §9.1 S8)
	g.war["battles"] = 4
	g._set_mode(g.Mode.WAR)
	g.ui.close_modal()
	var mem := -1
	for m in g.war["coalition"]:
		if int(m) != int(g.war["enemy"]) and (mem < 0 or float(g.SEPARATE_AT.get(String(g.sim.states[int(m)]["archetype"]), 30.0)) < float(g.SEPARATE_AT.get(String(g.sim.states[mem]["archetype"]), 30.0))):
			mem = int(m)
	var mem_hex := -1
	for c in g.sim.cells:
		if int(c["owner"]) == mem and Types.is_passable(c):
			mem_hex = c["id"]
	g._select(mem_hex)
	_check(g._front() == mem, "a tap on a member's hex makes it the front")
	g._select(-1)
	var need_sh: float = g.SEPARATE_AT.get(String(g.sim.states[mem]["archetype"]), 30.0)
	var mem_core: Dictionary = g.MapGen.core_of(g.sim, mem)
	var taken: Array = []
	for core_pass in [false, true]:  # its outer land first, then the core and the capital (occupied, never annexed)
		for c in g.sim.cells:
			if g._member_share(mem) >= need_sh:
				break
			if int(c["owner"]) == mem and int(c["controller"]) == mem and Types.is_passable(c) and mem_core.has(c["id"]) == core_pass:
				c["controller"] = Types.PLAYER
				taken.append(c["id"])
	var ws_c: float = float(g.War.war_score(g.sim, g.war)["score"])
	var shares := 0.0
	for m in g.war["coalition"]:
		if int(m) != int(g.war["enemy"]):
			shares += g._member_share(int(m))
	_check(ws_c > 0.0 and shares > 0.0 and shares <= ws_c + 0.2, "members' shares are part of the score (%.1f of %.1f)" % [shares, ws_c])
	var reached: bool = g._member_share(mem) >= need_sh
	g._separate_offer_tick(g.now_s())
	_check(g.ui.has_modal() == reached, "the member over its threshold asks for a separate peace (%.1f / %.1f)" % [g._member_share(mem), need_sh])
	_check((g._diplomacy_items(g.now_s()).filter(func(x): return x.has("share")) as Array).size() == (g.war["coalition"] as Array).size(), "Diplomacy shows the members' shares")
	g.ui.close_modal()
	if reached:
		var plan: Dictionary = g._separate_plan(mem)
		g._separate_peace(mem)
		var ours := 0
		for h in plan["annex"]:
			if int(g.sim.cells[h]["owner"]) == Types.PLAYER:
				ours += 1
		_check(ours == (plan["annex"] as Array).size() and int(plan["gold"]) >= 0, "the separate peace cedes %d occupied hexes, %d gold" % [ours, int(plan["gold"])])
		for h in plan["annex"]:
			_check(not mem_core.has(h), "no core hex is ceded")
		var back := true
		for h in taken:
			if not (plan["annex"] as Array).has(h) and int(g.sim.cells[h]["controller"]) != mem:
				back = false
		_check(back and not (g.war["coalition"] as Array).has(mem), "the rest of its land goes back, it leaves the war")
		_check(int(g.war.get("wins", 0)) == 1, "a victorious separate peace counts as one won war")
		var tf0 := int(g.stats.get("two_fronts", 0))
		g._coalition_win()
		_check(int(g.stats.get("two_fronts", 0)) == tf0 + 1, "a second win in the same coalition war: «Война на два фронта»")
	g.war["battles"] = 0
	# separate peace with a non-leader member: it leaves, the leader's armies lose its share
	var lead: int = g.war["enemy"]
	var other := -1
	for m in g.war["coalition"]:
		if int(m) != lead:
			other = int(m)
	var lead_str_before := 0
	for a in g.armies:
		if int(a["side"]) == lead:
			lead_str_before += int(a["max_str"])
	_check(other >= 0 and g._can_separate(other), "a member can make a separate peace")
	# every member strikes in turn (06 §14.6)
	for k in ["strike_at", "strike_hex", "strike_from", "strike_by"]:
		g.war.erase(k)
	g.war["member_strike_at"] = 0
	g._member_strikes(g.now_s())
	_check(not g.war.has("strike_at") or g.War.sides(g.war).has(int(g.war.get("strike_by", -1))), "a coalition side announces its strike (%d)" % int(g.war.get("strike_by", -1)))
	var first_by := int(g.war.get("strike_by", -1))
	for k in ["strike_at", "strike_hex", "strike_from", "strike_by"]:
		g.war.erase(k)
	g.war["member_strike_at"] = 0
	g._member_strikes(g.now_s())
	_check(first_by < 0 or int(g.war.get("strike_by", -1)) != first_by or g.War.sides(g.war).size() == 1, "the next strike comes from another member")
	for k in ["strike_at", "strike_hex", "strike_from", "strike_by"]:
		g.war.erase(k)
	if other >= 0:
		# a losing separate peace (06 §14.6: share ≤ −10): it keeps the player's land it holds, no «Триумф»
		var pcore: Dictionary = g.MapGen.core_of(g.sim, Types.PLAYER)
		var held: Array = []
		for c in g.sim.cells:
			if held.size() >= 3:
				break
			if int(c["owner"]) == Types.PLAYER and Types.is_passable(c) and not pcore.has(c["id"]) and c["kind"] != "city":
				c["controller"] = other
				held.append(c["id"])
		var sep_battles: int = g.war["battles"]
		g.war["battles"] = -10
		var lplan: Dictionary = g._separate_plan(other)
		_check(g._member_share(other) <= -10.0 and not (lplan["lose"] as Array).is_empty(), "share %.1f: a defeat, %d hexes to give" % [g._member_share(other), (lplan["lose"] as Array).size()])
		g._on_diplomacy_action(other, "separate")
		_check(g.ui.has_modal(), "the player's separate peace shows its terms first")
		g.ui.close_modal()
		g._separate_peace(other)
		var gone := 0
		for h in lplan["lose"]:
			if int(g.sim.cells[h]["owner"]) == other:
				gone += 1
		_check(gone == (lplan["lose"] as Array).size() and g.war.has("sep_defeat"), "the member annexes them, no «Триумф» this war")
		for h in held:
			if int(g.sim.cells[h]["owner"]) == Types.PLAYER:
				g.sim.cells[h]["controller"] = Types.PLAYER
		g.war["battles"] = sep_battles
		var lead_str_after := 0
		for a in g.armies:
			if int(a["side"]) == lead:
				lead_str_after += int(a["max_str"])
		_check(not (g.war["coalition"] as Array).has(other) and g._truce_left(other) > 0, "the member left with a truce")
		_check(lead_str_after <= lead_str_before, "the leader's armies lose its share (%d -> %d)" % [lead_str_before, lead_str_after])
	# a won coalition war counts its battles double («Триумф»)
	g.war["battles"] = 4
	_check(int(g.War.war_score(g.sim, g.war)["battles"]) == 8, "Triumph: battles count double")
	g.war["battles"] = 0
	Save.save(g)
	var gc: Node = load("res://scenes/main.tscn").instantiate()
	gc.save_enabled = false
	_check(Save.apply(gc, Save.read()) and (gc.war.get("coalition", []) as Array).size() == (g.war["coalition"] as Array).size(), "a coalition war survives a save")
	gc.free()
	g._finish_war(int(g.war["enemy"]), "test")
	_check(g.war.is_empty(), "the coalition war ends")
	Save.save(g)
	var g4: Node = load("res://scenes/main.tscn").instantiate()
	g4.save_enabled = false
	_check(Save.apply(g4, Save.read()) and g4.sim.cells.size() == g.sim.cells.size() and g4.chapter == 3 and g4.sim.states.size() == 9, "chapter III save restores ring III (%d cells)" % g4.sim.cells.size())
	g4.free()
	# Chapter IV «Индустриальный пояс» — the last chapter of the launch (canon §12.1)
	g.war = {}
	g.ai_wars = []
	g._world_expansion()
	g.ui.close_modal()
	_check(g.chapter == 4 and g.sim.states.size() == 12 and g._land_count() == 250, "world expanded to 250 land hexes, 3 more states (%d)" % g._land_count())
	_check(g._chapter_goal() == 88 and g._colonize_seconds() == 1800, "chapter IV goal 88, colonization 30 min")
	_check(String(g._world_items().filter(func(x): return not (String(x.get("id", "")).begins_with("order") or String(x.get("id", "")).begins_with("weekly") or String(x.get("id", "")) in ["pass", "calendar"]))[1]["id"]) == "c4_conclave", "World tab lists chapter IV stars first")
	Save.save(g)
	var g5: Node = load("res://scenes/main.tscn").instantiate()
	g5.save_enabled = false
	_check(Save.apply(g5, Save.read()) and g5.sim.cells.size() == g.sim.cells.size() and g5.chapter == 4, "chapter IV save restores ring IV (%d cells)" % g5.sim.cells.size())
	g5.free()
	g.queue_free()
	await process_frame

	# Q2 (playtest 2, wars and diplomacy in chapters II–IV) ----------------------------------------------------------
	# (1) an ultimatum never replaces a war (B-H1): «Война!» waits for its answer, an AI war holds it, a refusal comes after
	g = await _after_first_peace()
	g.ultimatum_at = -1
	g._issue_ultimatum(g.now_s(), MapGen.BARONS)
	g.ui.close_modal()
	_check(g._ult_buyout() == 0 and String(g.inbox[-1]["text"]).begins_with("inbox.ultimatum.text_hex|"),
		"the Wolf's ultimatum has no buyout, its letter names the hex alone (canon §9.1; %s)" % String(g.inbox[-1]["text"]))
	g._select(-1)
	g._refresh_ui()
	_check(g.ui._status_args.size() > 0 and String(g.ui._status_args[0]) == "ultimatum" and g._unread() >= 1,
		"an ultimatum closed with ✕ keeps its deadline on the map and the mail lit (%s)" % str(g.ui._status_args.slice(0, 3)))
	var q2h: Array = War.recommend_goals(g.sim, MapGen.HAMLETS, 1)
	if q2h.size() > 0:
		g._select(q2h[0])
		g._refresh_ui()
		_check(g.ui._action2_kind == "ult_wait" and String(g.ui._primary_args[2]) == "lock", "«Война!» on the Hamlets is locked while the Barons' ultimatum waits (%s)" % g.ui._action2_kind)
		g._on_action("ult_wait")
		_check(g.ui.has_modal(), "the locked «Война!» opens the ultimatum again")
		g.ui.close_modal()
		g._declare(MapGen.HAMLETS, q2h[0])
		_check(g.war.is_empty(), "no war is declared while an ultimatum waits")
	g._answer_ultimatum("refuse")
	g._set_mode(g.Mode.WAR)
	var q2w0: Dictionary = g.war.duplicate()
	var q2ph := -1
	for c in g.sim.cells:
		if q2ph < 0 and int(c["owner"]) == Types.PLAYER and Types.is_passable(c) and g._touches_owner(c["id"], MapGen.HAMLETS) and not MapGen.core_of(g.sim, Types.PLAYER).has(c["id"]):
			q2ph = c["id"]
	g.ultimatum = {"state": MapGen.HAMLETS, "hex": maxi(0, q2ph), "tribute": 100000, "deadline": g.now_s() + 60}
	_check(g._ult_buyout() == mini(50000, int(g.econ.storage_cap()["gold"]) * 9 / 10), "a Fox's buyout is half the tribute, at most 90%% of the gold cap (%d)" % g._ult_buyout())
	# the demand is a hex: its gold equivalent is max(8; 4 × value) h of gold (canon §9.1) — 12 h for a value-3 hex
	var q2uh: int = int(g.ultimatum["hex"])
	var q2v0: int = int(g.sim.cells[q2uh]["value"])
	g.sim.cells[q2uh]["value"] = 3
	g.ultimatum["tribute"] = 800
	_check(g._ult_buyout() == 600, "the buyout is half the demanded hex's gold equivalent, 12 h for a value-3 hex (%d)" % g._ult_buyout())
	g.sim.states[MapGen.HAMLETS]["archetype"] = "raven"
	_check(g._ult_buyout() == 900, "the Raven's buyout is 75%% (%d)" % g._ult_buyout())
	g.sim.states[MapGen.HAMLETS]["archetype"] = "fox"
	g.sim.cells[q2uh]["value"] = q2v0
	g.ultimatum["tribute"] = 100000
	g.war.erase("strike_at")
	g.war.erase("strike_hex")
	g.time_offset += 1800
	g._econ_tick()
	_check(int(g.war.get("enemy", -1)) == MapGen.BARONS and int(g.war.get("started", 0)) == int(q2w0["started"]) and int(g.ultimatum.get("held", 0)) == 1 and g._ult_left() > 0,
		"an ultimatum due during the Barons' war is held: the running war is never replaced (enemy %s)" % str(g.war.get("enemy", -1)))
	# the demanded hex lost meanwhile: the demand moves to another hex of ours on that border, or lapses with none
	var q2ul: Dictionary = g.ultimatum.duplicate()
	g.sim.cells[q2uh]["owner"] = MapGen.BARONS
	g._ultimatum_tick(g.now_s())
	_check(g.ultimatum.is_empty() == (g._ult_target(MapGen.HAMLETS) < 0) and (g.ultimatum.is_empty() or (int(g.ultimatum["hex"]) != q2uh and int(g.sim.cells[int(g.ultimatum["hex"])]["owner"]) == Types.PLAYER)),
		"a demanded hex lost during the hold: the ultimatum demands another of ours, or lapses (%s)" % str(g.ultimatum.get("hex", -1)))
	g.sim.cells[q2uh]["owner"] = Types.PLAYER
	g.ultimatum = q2ul
	g._answer_ultimatum("refuse")
	_check(int(g.war.get("enemy", -1)) == MapGen.BARONS and int(g.ultimatum.get("refused", 0)) == 1, "a refusal during a war waits for that war's end")
	War.white_peace(g.sim)
	g._finish_war(MapGen.BARONS, "test", "", true)
	g.time_offset += 60
	g._econ_tick()
	_check(int(g.war.get("enemy", -1)) == MapGen.HAMLETS and g.war.has("ult_refused") and g.ultimatum.is_empty(),
		"the refused ultimatum's war comes once the running war ended by its own treaty (enemy %s)" % str(g.war.get("enemy", -1)))
	g.war = {}
	g._set_mode(g.Mode.MAP)
	# (2) the war table by the war's chapter (canon §9.1, §9.15; 03 §2.4)
	g.truce = {}
	g.ultimatum = {}
	g.chapter = 2
	g._demo_touch(MapGen.BARONS)
	var q2bg := func() -> int:
		for c in g.sim.cells:
			if int(c["owner"]) == MapGen.BARONS and Types.is_passable(c) and g._touches_player(c["id"]) and not MapGen.core_of(g.sim, MapGen.BARONS).has(c["id"]):
				return int(c["id"])
		for c in g.sim.cells:
			if int(c["owner"]) == MapGen.BARONS and Types.is_passable(c) and g._touches_player(c["id"]):
				return int(c["id"])
		return int(g.sim.states[MapGen.BARONS]["capital_id"])
	g._declare(MapGen.BARONS, q2bg.call())
	_check(int(g.war.get("chapter", 0)) == 2 and g._ai_energy(MapGen.BARONS) == 800 and int(g._war_rule("cap")) == 24 * 3600 and int(g._war_rule("truce")) == 8 * 3600,
		"a chapter II war: cap 24 h, truce 8 h, AI energy ×0.8 (%d)" % g._ai_energy(MapGen.BARONS))
	g.sim.states[MapGen.BARONS]["hegemon"] = true
	g.war["chapter"] = 3
	_check(int(g._war_rule("cap")) == 72 * 3600 and int(g._war_rule("truce")) == 24 * 3600 and g._ai_energy(MapGen.BARONS) == 1100,
		"chapter III+: cap 72 h, truce 24 h, the hegemon's energy ×1.1 (%d)" % g._ai_energy(MapGen.BARONS))
	g.sim.states[MapGen.BARONS].erase("hegemon")
	g.war["chapter"] = 2
	g.war.erase("strike_at")
	g._schedule_counter(-1, true)
	var q2left: int = int(g.war.get("strike_at", 0)) - g.now_s()
	_check(q2left >= 4 * 3600 and q2left <= 6 * 3600 and not g.war.has("strike_hex"), "chapter II: the counter-strike lands 4–6 h after an offensive (%.2f h), not yet announced" % (q2left / 3600.0))
	var q2n: int = g.inbox.size()
	g.time_offset += q2left - 19 * 60
	g._econ_tick()
	_check(g.war.has("strike_hex") and g.inbox.size() > q2n, "the strike is announced 20 min ahead: the arrow and the letter")
	g.war["chapter"] = 3
	g.war.erase("strike_at")
	g.war.erase("strike_hex")
	g._schedule_counter(-1, true)
	q2left = int(g.war.get("strike_at", 0)) - g.now_s()
	_check(q2left >= 3 * 3600 and q2left <= 4 * 3600, "chapter III: the Wolf strikes 3–4 h after an offensive (%.2f h)" % (q2left / 3600.0))
	g.war["chapter"] = 1
	g.war.erase("strike_at")
	g.war.erase("strike_hex")
	g.war["strikes"] = 1
	g._schedule_counter(-1, true)
	_check(not g.war.has("strike_at"), "chapter I: no counter-strike after the war's one scripted strike")
	g.war["chapter"] = 2
	g.war["started"] = g.now_s()
	g.war.erase("strike_at")
	g.time_offset += 2 * 3600 + 60
	g._set_mode(g.Mode.WAR)
	g._econ_tick()
	_check(not g.war.is_empty(), "a chapter II war goes on past chapter I's 2 h cap")
	g.war.erase("strike_at")
	g.war.erase("strike_hex")
	g.time_offset += 22 * 3600
	g._econ_tick()
	if g.mode == g.Mode.CEREMONY:
		for i in 80:
			g._step_ceremony(0.1)
		g._end_ceremony()
	var q2cap := ""
	for it in g.inbox:
		if String(it["title"]) == "inbox.war_cap.title":
			q2cap = L.t(it["text"])
	_check(g.war.is_empty() and absf(g._truce_left(MapGen.BARONS) - 8 * 3600) < 120 and q2cap.contains("24"),
		"the chapter II war closes at 24 h, an 8 h truce, the letter says 24 h («%s», truce %d s)" % [q2cap, g._truce_left(MapGen.BARONS)])
	# a cap that ran out while the player was away 24 h+ is a white peace (canon §9.11)
	g.truce = {}
	g._set_mode(g.Mode.MAP)
	g._declare(MapGen.BARONS, q2bg.call())
	g.war.erase("strike_at")
	g.war["battles"] = 10
	g._away = [g.now_s() + 3600, g.now_s() + 3600 + 30 * 3600]
	g.time_offset += 30 * 3600 + 3600
	g._econ_tick()
	var q2away := false
	for it in g.inbox:
		q2away = q2away or String(L.t(it["text"])).begins_with(String(g.tr("inbox.war_cap.away")).get_slice("%", 0))
	_check(g.war.is_empty() and q2away, "a war cap that ran out in a 24 h absence closes with a white peace")
	g._away = [0, 0]
	g.chapter = 1
	g.truce = {}
	g._set_mode(g.Mode.MAP)
	# (3) the opinion model (06 §11): base, decay by archetype, memories saved
	g.opinion = {}
	var q2b: float = g._opinion_of(MapGen.HAMLETS)
	var q2parts: Array = g._opinion_parts(MapGen.HAMLETS)
	_check(q2parts.any(func(p): return p[0] == "op_base" and absf(float(p[1]) - 5.0) < 0.01), "a Fox's character: op_base +5 (%s)" % str(q2parts))
	g._opinion_add(MapGen.HAMLETS, 10.0, "op_gift")
	g.time_offset += 10 * 3600
	_check(absf(g._opinion_of(MapGen.HAMLETS) - q2b - (10.0 - 10.0 * 0.25 * 1.25)) < 0.11, "a gift fades 0.25 × the Fox's 1.25 an hour (%.2f)" % (g._opinion_of(MapGen.HAMLETS) - q2b))
	g._opinion_add(MapGen.BARONS, 10.0, "op_gift")
	var q2w: float = g._opinion_of(MapGen.BARONS)
	g.time_offset += 10 * 3600
	_check(absf(q2w - g._opinion_of(MapGen.BARONS) - 3.75) < 0.11, "the Wolf forgets 1.5× as fast: −3.75 in 10 h (%.2f)" % (q2w - g._opinion_of(MapGen.BARONS)))
	for i in 3:
		g._opinion_add(MapGen.BARONS, -30.0, "op_annexed")
	var q2an := 0.0
	for p in g._opinion_parts(MapGen.BARONS):
		if p[0] == "op_annexed":
			q2an = float(p[1])
	_check(q2an >= -40.05 and q2an <= -39.0, "annexations together never cost more than −40 (%.1f)" % q2an)
	var q2d: Dictionary = JSON.parse_string(JSON.stringify(Save.to_dict(g)))
	var q2g2: Node = load("res://scenes/main.tscn").instantiate()
	q2g2.save_enabled = false
	Save.apply(q2g2, q2d)
	q2g2.time_offset = g.time_offset
	_check(absf(q2g2._opinion_of(MapGen.BARONS) - g._opinion_of(MapGen.BARONS)) < 0.05 and q2g2._op_mems(MapGen.BARONS).size() == g._op_mems(MapGen.BARONS).size(),
		"opinion memories survive a save (%.1f, %d memories)" % [q2g2._opinion_of(MapGen.BARONS), q2g2._op_mems(MapGen.BARONS).size()])
	q2d["opinion"] = {str(MapGen.HAMLETS): 30.0}
	Save.apply(q2g2, q2d)
	var q2m: Array = q2g2.opinion.get(MapGen.HAMLETS, [])
	_check(q2m.size() == 1 and String(q2m[0]["c"]) == "op_legacy" and absf(float(q2m[0]["v"]) - 30.0) < 0.01, "an older save's opinion number becomes one legacy memory")
	q2g2.free()
	# (4) readiness (canon §2.2 #3): below 50% an army sits the offensive out; none ready — the button waits
	g._declare(MapGen.BARONS, q2bg.call())
	g.war.erase("strike_at")
	g._set_mode(g.Mode.WAR)
	var q2pa: Array = g._player_armies()
	for a in q2pa:
		a["str"] = int(a["max_str"]) / 5
	g._refresh_ui()
	_check(String(g.ui._primary_args[0]) == "recovering" and not bool(g.ui._primary_args[3]), "no army at 50%%: «В атаку!» waits for the refill (%s)" % str(g.ui._primary_args.slice(0, 2)))
	g._start_offensive()
	_check(g.battle == null, "no offensive with every army below 50%")
	q2pa[0]["str"] = q2pa[0]["max_str"]
	g._refresh_ui()
	g._start_offensive()
	_check(g.battle != null and (q2pa.size() < 2 or (bool(q2pa[1].get("rest", false)) and bool(q2pa[1]["routed"]) and not bool(q2pa[0].get("rest", false)))),
		"an army below 50% sits the offensive out")
	while g.battle != null and not g.battle.over:
		g._battle_step()
	g._end_offensive()
	_check(q2pa.all(func(a): return not a.has("rest") and not bool(a["routed"])), "after the offensive every army is back with the rest")
	g.ui.close_modal()
	g.war = {}
	g._set_mode(g.Mode.MAP)
	# (5) coalitions never join two states at war with each other; the pact's price; the AI settlers' neutral chip
	g.ai_wars = [{"a": MapGen.BARONS, "b": MapGen.HAMLETS, "until": g.now_s() + 86400, "next": g.now_s() + 7200}]
	var q2nf: Array = g._no_feuds([MapGen.BARONS, MapGen.HAMLETS])
	_check(q2nf.size() == 1, "of two states at war with each other only the stronger joins a coalition (%s)" % str(q2nf))
	g.ai_wars = []
	var q2it: Dictionary = {}
	for it in g._diplomacy_items(g.now_s()):
		if int((it as Dictionary).get("id", -1)) == MapGen.HAMLETS:
			q2it = it
	_check(int(q2it.get("pact_cost", 0)) == g._pact_cost() and q2it.has("opinion_parts") and bool(q2it.get("pact_over_cap", true)) == (g._pact_cost() > int(g.econ.storage_cap()["gold"])),
		"the leader card carries the pact's price and the opinion's parts")
	g.pacts = {}
	g._opinion_set(MapGen.HAMLETS, 10.0)
	for it in g._diplomacy_items(g.now_s()):
		if int((it as Dictionary).get("id", -1)) == MapGen.HAMLETS:
			q2it = it
	var q2ct: Dictionary = g.ui._diplomacy_cta(q2it, g.ui._relation(q2it))
	var q2g0 := int(g.econ.res["gold"])
	var q2pact: bool = String(q2ct.get("caption", "")) == g.tr("dipl.pact_btn") and q2ct.has("cb")
	if q2pact:
		(q2ct["cb"] as Callable).call()
	_check(q2pact and q2ct.get("price", []).size() == 1 and g.ui.has_modal() and int(g.econ.res["gold"]) == q2g0 and g._pact_left(MapGen.HAMLETS) == 0,
		"the neighbour card's «Пакт» shows its price and opens the leader's window: nothing is charged by a tap (%s)" % str(q2ct.get("price", [])))
	g.ui.close_modal()
	g.econ.res["gold"] = 0
	g._on_diplomacy_action(MapGen.HAMLETS, "pact")
	_check(g._pact_left(MapGen.HAMLETS) == 0 and int(g.econ.res["gold"]) == 0, "a pact short of gold is not signed")
	g.queue_free()
	await process_frame

	print("\n%s" % ("ALL FLOW CHECKS PASSED" if fails == 0 else "%d FLOW CHECK(S) FAILED" % fails))
	quit(1 if fails > 0 else 0)
