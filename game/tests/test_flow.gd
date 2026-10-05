extends SceneTree
## Headless smoke test of the game controller (scripts/main.gd): drives every mode transition and
## fails on script errors or broken invariants. Run:
##   godot --headless --path game --script res://tests/test_flow.gd

const Types := preload("res://scripts/sim/types.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const War := preload("res://scripts/sim/war.gd")

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
	g._pick_target()
	if g.selected >= 0 and g.sim.cells[g.selected]["owner"] == Types.NOBODY:
		var n0: int = g._player_hexes()
		var gold0: int = g.econ.res["gold"]
		g._on_action("colonize")
		_check(g.colonizing.size() == 1 and g.econ.res["gold"] < gold0, "colonization starts: gold paid, timer running")
		g.time_offset += 3600
		g._econ_tick()
		_check(g._player_hexes() == n0 + 1 and g.colonizing.is_empty(), "colonization timer adds a hex")

	# 2b. Economy: income accrues, «collect all», building upgrade with a timer
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
		_check(econ.building(target_b["id"])["level"] == lvl0 + 1, "upgrade completes after its timer")
	g._open_tab("army")
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

	# 5. FTUE: guided first war (canon §14.3)
	g = await _new_game()
	g.ftue = 1
	g._ftue_tick(0.1)
	_check(g.selected >= 0 and g.ui._action2_kind == "declare", "FTUE preselects a war goal")
	g._on_action("declare")
	_check(g.ftue == 2, "FTUE step: declared")
	g._on_action("offensive")
	_check(g.ftue == 3 and g.battle.duration_ticks() == 600, "FTUE offensive is 60 s")
	g._ftue_tick(0.1)
	_check(g.ui._ghost_from.x >= 0, "FTUE ghost finger shown")
	while g.battle != null and not g.battle.over:
		if g.battle.tick % 20 == 0:
			g._bot_move()
		g._battle_step()
	g._end_offensive()
	_check(g.ftue == 5 or g.ftue == 2, "FTUE after the offensive (step %d)" % g.ftue)
	if g.ftue == 5:
		g.ui.close_modal()
		g._open_peace()
		_check(g.ftue == 6, "FTUE peace step")
		g._sign_peace()
		_check(g.ftue == 0, "FTUE finished after the seal")
	g.queue_free()
	await process_frame

	print("\n%s" % ("ALL FLOW CHECKS PASSED" if fails == 0 else "%d FLOW CHECK(S) FAILED" % fails))
	quit(1 if fails > 0 else 0)
