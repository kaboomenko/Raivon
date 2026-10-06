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
	g._on_world_action("expand")
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
		g._fort_action()
		g.time_offset += 3600
		g._econ_tick()
		_check(g.sim.cells[fhex]["fort"] == 1, "fort button builds a level-1 fortification")
	# deposit + convoy (canon §5.2): the first convoy is the fast FTUE one
	var dhex := -1
	for dep in g.deposits.active:
		if g.deposits.can_send(g.sim, dep["hex"], econ.dev_level()) == "":
			dhex = dep["hex"]
			break
	if dhex >= 0:
		var res_key: String = g.deposits.at(dhex)["res"]
		var before: int = econ.res[res_key]
		g._select(dhex)
		_check(g.ui._action2_kind == "convoy", "deposit hex offers a convoy")
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
	_check(g._army_items(g.now_s()).size() == g._player_armies().size() + 1, "army tab lists armies plus «new army»")
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
	# Airstrike opens at DL6 (canon §9.9): locked in the hand before; the Barons (Wolf) play it only from DL6
	_check(not g._hand().has("airstrike") and g.ui._locked.has("airstrike"), "airstrike locked below DL6")
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
	_check(not g.ultimatum.is_empty() and g._unread() == 1, "ultimatum issued and posted to the inbox")
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

	# 5. FTUE: guided first war (canon §14.3)
	g = await _new_game()
	g.ftue = 1
	g._ftue_tick(0.1)
	_check(g.selected >= 0 and g.ui._action2_kind == "declare", "FTUE preselects a war goal (sel %d, kind %s)" % [g.selected, g.ui._action2_kind])
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
		_check(g.ftue == 0, "FTUE coach hidden during the ceremony")
		for i in 80:
			g._step_ceremony(0.1)
		g._end_ceremony()
		_check(g.ftue == 7, "FTUE resumes after the ceremony (residence step)")
		g._ftue_tick(0.1)
		if g.ftue == 7:
			g._on_building_upgrade(g.econ.buildings[0]["id"])
		_check(g.ftue == 8, "FTUE: residence step done (or skipped for lack of land)")
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
		_check(g.ftue == 0 and not g._raid.is_empty(), "FTUE: fence started, marauder raid scheduled")
		g.time_offset += 60
		g._econ_tick()
		var raided := false
		for it in g.inbox:
			if String(it["title"]) == "inbox.raid.title":
				raided = true
		_check(raided and g._raid.is_empty(), "FTUE: the raid breaks against the fence")
		# war 2 with the Hamlets: encirclement card, then spare or plunder (canon §14.3, 6:00–9:30)
		if g.ftue == 10:
			g.truce = {}
			g._ftue_tick(0.1)
			_check(g.selected >= 0 and g.sim.cells[g.selected]["owner"] == MapGen.HAMLETS, "FTUE war 2: Hamlets goal selected")
			g._on_action("declare")
			_check(g.ftue == 11, "FTUE war 2 declared")
			g._on_action("offensive")
			_check(g.ftue == 12 and g.battle.duration_ticks() == 600, "FTUE war 2 offensive (encircle hint)")
			while g.battle != null and not g.battle.over:
				if g.battle.tick % 20 == 0:
					g._bot_move()
				g._battle_step()
			g._end_offensive()
			if g.ftue == 14:
				g.ui.close_modal()
				g._open_peace()
				_check(g.ftue == 15, "FTUE war 2 peace with plunder choice")
				g._sign_peace()
				_check(g.ftue == 0, "FTUE complete after war 2")
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
	_check(g.econ.ruin_left(g.now_s()) == 8 * 3600 and g.econ.ruin_pct == 40, "defeat: ruin −40% for 8 h")
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
	var code0: String = g.orders.list[0]["code"]
	_check(bool(oi[0].get("swap", false)), "an unfinished order offers the free swap")
	g._on_world_action("swap:order:0")
	_check(g.orders.swapped and String(g.orders.list[0]["code"]) != code0, "the free swap replaces the order")
	_check(not bool(g._order_items()[1].get("swap", true)), "one free swap a day")
	g._orders_chip()
	_check(g.hud._orders_chip.visible and g.hud._orders_lbl.text.ends_with("/3"), "the HUD chip shows today's orders")
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
	g.opinion[4] = 45.0
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
	g.opinion[4] = 70.0
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
	if fox >= 0:
		var pk: Dictionary = g._ai_swap_package(fox)
		if not pk.is_empty():
			var cut: int = g._border_len(fox) - g._border_len(fox, g._swap_over(fox, pk["give"], pk["get"]))
			_check(cut >= 2 and (pk["give"] as Array).size() <= 2 and float(g._swap_terms(fox, pk["give"], pk["get"])["pay"]) <= 1.0,
				"the AI package shortens the border by %d edges, top-up ≤ 1 unit" % cut)
			g.swap_offer = {"state": fox, "give": pk["give"], "get": pk["get"], "until": g.now_s() + 86400, "auto": false}
			g._show_swap_offer()
			_check(g.ui.has_modal(), "the AI offer opens")
			g.ui.close_modal()
		g.swap_offer_at[fox] = 0
		g.swap_offer = {}
		g._ai_swap_tick(g.now_s())
		_check(int(g.swap_offer_at[fox]) > g.now_s(), "the Fox's next look is scheduled")
		g.swap_offer = {}
	# Non-aggression pact (06 §11): 8 h of gold, 48 h, archetype threshold, one at a time, no war in the pair
	var pst: int = g._ai_states()[0]
	g.ultimatum = {}  # an open ultimatum blocks a pact with its sender; the daily rolls depend on the clock
	g.opinion[pst] = 10.0
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

	print("\n%s" % ("ALL FLOW CHECKS PASSED" if fails == 0 else "%d FLOW CHECK(S) FAILED" % fails))
	quit(1 if fails > 0 else 0)
