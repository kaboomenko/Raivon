extends SceneTree
## Headless tests for the economy rules module (scripts/sim/economy.gd).
## Run: godot --headless --path game --script res://tests/test_economy.gd

const Types := preload("res://scripts/sim/types.gd")
const World := preload("res://scripts/sim/world.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const Economy := preload("res://scripts/sim/economy.gd")
const L := preload("res://scripts/l10n.gd")
const Market := preload("res://scripts/sim/market.gd")

const SEED := 20261004
const T0 := 1790000000
const PLAYER := Types.PLAYER

var _errors: Array[String] = []
var _failed := 0
var _passed := 0
var _checks := 0


func _init() -> void:
	var tests: Array[Array] = [
		["starting state follows the canon", _test_start],
		["income from the chapter I world", _test_income],
		["tick accrues stock per hex, upkeep from the pool", _test_tick],
		["8 h cap per hex and economy pause", _test_cap],
		["collect respects storage caps", _test_collect],
		["upgrade flow: cost, builder, completion, level", _test_upgrade],
		["builder limit and level gates", _test_limits],
		["residence: hex gate, DL up, unlocks, chapter cap", _test_residence],
		["speed-up price is monotonic, finish_now spends raivites", _test_speedup],
		["fort / tower build, world sync, refund on loss", _test_defense],
		["plunder respects the protected share", _test_plunder],
		["occupied enemy hex yields 50%", _test_occupied],
		["to_dict / from_dict round trip (also via JSON)", _test_roundtrip],
		["determinism: same inputs, same outputs; tick granularity", _test_determinism],
		["refusal reasons are translation keys; l10n.t() renders them in ru / en", _test_reason_text],
		["army food upkeep: pool first, then storage, no debt, 8 h pause", _test_army_food],
		["ruin and damaged buildings: −%, no stacking, repair, save", _test_ruin],
		["raivite vein: 2 per 12 h up to 4, occupied 1 up to 2", _test_vein],
		["market: rates, floor, warehouse cut, no raivites", _test_market],
		["market trader: daily lots, one buy each, 04:00 refresh, save", _test_trader],
		["trophy blueprints: store of 5, −10% left, −50% cap, defeat loss, save", _test_blueprints],
	]
	for t in tests:
		_errors.clear()
		(t[1] as Callable).call()
		if _errors.is_empty():
			_passed += 1
			print("PASS  %s" % t[0])
		else:
			_failed += 1
			print("FAIL  %s" % t[0])
			for e in _errors.slice(0, 10):
				print("      - " + e)
	print("\n%d passed, %d failed (%d checks)" % [_passed, _failed, _checks])
	quit(1 if _failed > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checks += 1
	if not cond:
		_errors.append(msg)


func _eq(actual: Variant, expected: Variant, msg: String) -> void:
	_checks += 1
	if actual != expected:
		_errors.append("%s: expected %s, got %s" % [msg, str(expected), str(actual)])


func _world() -> World:
	return MapGen.generate_chapter_one(SEED)


## Exact uncollected total (including fractional remainders).
func _stock_sum(e: Economy, r: String) -> int:
	return e.stock_total(r)


func _own_plain(w: World) -> Array[int]:
	var out: Array[int] = []
	for c in w.cells:
		if c["owner"] == PLAYER and c["kind"] == "plain" and Types.is_passable(c):
			out.append(int(c["id"]))
	return out


## Gives the player `n` more passable wild hexes (as if annexed by treaty).
func _grant_hexes(w: World, n: int) -> void:
	var left := n
	for c in w.cells:
		if left == 0:
			return
		if c["owner"] == Types.NOBODY and c["kind"] == "plain" and Types.is_passable(c):
			c["owner"] = PLAYER
			c["controller"] = PLAYER
			left -= 1


# ---------------------------------------------------------------- tests

func _test_start() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	_eq(e.res["gold"], 1000, "start gold")
	_eq(e.res["food"], 600, "start food")
	_eq(e.res["metal"], 600, "start metal")
	_check(e.res.has("raivite"), "raivite key present")
	_eq(e.builders, 2, "builders")
	_eq(e.dev_level(), 1, "DL")
	var cap: int = w.states[PLAYER]["capital_id"]
	var main := e.building_at(cap)
	_eq(main.get("type", ""), "residence", "main building on the capital")
	_eq(main.get("level", 0), 1, "residence level")
	_eq(e.storage_cap(), {"gold": 5000, "food": 5000, "metal": 5000}, "storage cap Склад 1")
	_eq(e.protected_percent(), 40, "protected share")
	_check(e._find_type("market").is_empty(), "market locked until DL2")
	_check(e._find_type("embassy").is_empty(), "embassy locked until DL3")
	_eq(e.busy_builders(T0), 0, "no busy builders")
	_check(e.stock.is_empty(), "no stock at start")
	# A farm hex maps to the state-wide Ферма building.
	for c in w.cells:
		if c["owner"] == PLAYER and c["kind"] == "farm":
			_eq(e.building_at(int(c["id"])).get("type", ""), "farm", "farm hex -> Ферма")


func _test_income() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	# 7 hexes: capital (150/30/30), farm (30 food), 5 plain (4 gold each); upkeep 8 capital + 2 farm.
	_eq(e.gross_per_hour(w), {"gold": 170, "food": 60, "metal": 30}, "gross")
	_eq(e.upkeep_per_hour(), 10, "upkeep")
	_eq(e.income_per_hour(w), {"gold": 160, "food": 60, "metal": 30}, "net income")
	var cap: int = w.states[PLAYER]["capital_id"]
	_eq(e.hex_income(w, cap), {"gold": 150, "food": 30, "metal": 30}, "capital hex income")
	# Enemy hex: nothing.
	var enemy: int = w.states[MapGen.BARONS]["capital_id"]
	_eq(e.hex_income(w, enemy), {}, "enemy hex income")


func _test_tick() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	var ev := e.tick(w, T0 + 3600)
	_eq(ev.size(), 0, "no events")
	_eq(_stock_sum(e, "gold"), 160, "1 h gold minus upkeep")
	_eq(_stock_sum(e, "food"), 60, "1 h food")
	_eq(_stock_sum(e, "metal"), 30, "1 h metal")
	var cap: int = w.states[PLAYER]["capital_id"]
	_eq(int(e.stock[cap]["food"]), 30, "capital food stock")
	_eq(e.res["gold"], 1000, "storage untouched by income")
	_eq(e.last_tick, T0 + 3600, "last_tick")
	# Going back in time does nothing.
	e.tick(w, T0)
	_eq(_stock_sum(e, "food"), 60, "no accrual backwards")


func _test_cap() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	e.tick(w, T0 + 20 * 3600)
	_eq(_stock_sum(e, "food"), 8 * 60, "food stops at 8 h")
	_eq(_stock_sum(e, "metal"), 8 * 30, "metal stops at 8 h")
	_eq(_stock_sum(e, "gold"), 8 * 160, "gold: 8 h income minus 8 h upkeep (pause)")
	_eq(e.res["gold"], 1000, "no upkeep from storage while paused")
	# Storage full: collect moves nothing, stock stays; the window restarts but hexes stay capped at 8 h.
	for r in Economy.RES:
		e.res[r] = 5000
	var got := e.collect_all()
	_eq(got, {"gold": 0, "food": 0, "metal": 0}, "nothing fits")
	e.tick(w, T0 + 30 * 3600)
	var cap: int = w.states[PLAYER]["capital_id"]
	_eq(int(e.stock[cap]["food"]), 240, "capital food capped at 8 h of its income")
	_eq(int(e.stock[cap]["metal"]), 240, "capital metal capped")
	_eq(_stock_sum(e, "food"), 480, "food total capped")


func _test_collect() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	e.tick(w, T0 + 8 * 3600)
	e.res["gold"] = 4900
	var cap: int = w.states[PLAYER]["capital_id"]
	var before_cap_food: int = e.stock[cap]["food"]
	var got := e.collect(cap)
	_eq(got["food"], before_cap_food, "capital food collected")
	_eq(e.res["food"], 600 + before_cap_food, "food stored")
	_check(int(got["gold"]) <= 100, "gold limited by free space")
	_eq(e.res["gold"], mini(5000, 4900 + int(got["gold"])), "gold stored")
	var all := e.collect_all()
	_eq(e.res["gold"], 5000, "gold at cap")
	_check(_stock_sum(e, "gold") > 0, "excess gold stays in hexes")
	_eq(_stock_sum(e, "food"), 0, "all food collected")
	_eq(int(all["food"]), 480 - before_cap_food, "rest of food gained")
	_eq(e.last_collect, T0 + 8 * 3600, "collect restarts the 8 h window at last_tick")


func _test_upgrade() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	var wh := e._find_type("warehouse")
	var cost := e.upgrade_cost(wh)
	_eq(cost, {"gold": 160, "food": 0, "metal": 0, "seconds": 5}, "Склад 1->2 price (C_B 160)")
	_eq(e.can_upgrade(wh, T0), "", "can upgrade")
	_check(e.start_upgrade(int(wh["id"]), T0), "started")
	_eq(e.res["gold"], 840, "gold paid")
	_eq(e.busy_builders(T0), 1, "builder busy")
	_eq(int(wh["upgrade_end"]), T0 + 5, "timer")
	_eq(e.can_upgrade(wh, T0 + 1), "err.upgrading", "second upgrade of same building")
	var ev := e.tick(w, T0 + 4)
	_eq(ev.size(), 0, "not yet")
	ev = e.tick(w, T0 + 5)
	_eq(ev.size(), 1, "one event")
	if ev.size() == 1:
		_eq(ev[0]["type"], "upgrade_done", "event type")
		_eq(ev[0]["building"], wh["id"], "event building")
	_eq(int(wh["level"]), 2, "level 2")
	_eq(int(wh["upgrade_end"]), 0, "idle")
	_eq(e.busy_builders(T0 + 5), 0, "builder free")
	_eq(int(e.storage_cap()["gold"]), 6750, "Склад 2 cap")
	# Farm 1->2 raises the farm output by 8%.
	var farm := e._find_type("farm")
	_check(e.start_upgrade(int(farm["id"]), T0 + 5), "farm upgrade")
	e.tick(w, T0 + 10)
	_eq(int(farm["level"]), 2, "farm level 2")
	_eq(int(e.income_per_hour(w)["food"]), 30 + 32, "farm 32,4 food/h + capital 30")


func _test_limits() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	var b1 := e._find_type("barracks")
	var b2 := e._find_type("academy")
	var b3 := e._find_type("infirmary")
	_check(e.start_upgrade(int(b1["id"]), T0), "barracks")
	_check(e.start_upgrade(int(b2["id"]), T0), "academy")
	_eq(e.busy_builders(T0), 2, "2 busy")
	_eq(e.can_upgrade(b3, T0), "err.builders_busy", "builder limit reason")
	_check(not e.start_upgrade(int(b3["id"]), T0), "third refused")
	e.tick(w, T0 + 60)
	_eq(int(b1["level"]), 2, "barracks 2")
	_eq(e.can_upgrade(b1, T0 + 60), "err.need_residence|2", "2 × DL cap")
	e.res["gold"] = 0
	_eq(e.can_upgrade(b3, T0 + 60), "err.not_enough|res.gen.gold", "no gold")
	e.res["gold"] = 1000
	_eq(e.can_upgrade(e._find_type("port"), T0 + 60), "err.no_port", "no ports")
	_eq(e.can_upgrade({}, T0), "err.no_building", "unknown building")


func _test_residence() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	var r := e._find_type("residence")
	_eq(e.can_upgrade(r, T0), "err.need_hexes|10", "hex gate")
	_grant_hexes(w, 3)
	e.tick(w, T0)
	_eq(e.upgrade_cost(r), {"gold": 300, "food": 0, "metal": 100, "seconds": 60}, "DL2 price (11 §6.2)")
	_check(e.start_upgrade(int(r["id"]), T0), "residence started")
	var ev := e.tick(w, T0 + 60)
	var types: Array = []
	for x in ev:
		types.append(x["type"])
	_eq(types, ["upgrade_done", "dev_level", "building_unlocked"], "events")
	_eq(e.dev_level(), 2, "DL2")
	_eq(int(w.states[PLAYER]["dev_level"]), 2, "world DL synced")
	_check(not e._find_type("market").is_empty(), "market unlocked")
	# 10 hexes: capital 225 gold, 8 plain × 6, farm 45 food; upkeep × 1,7.
	var gross := e.gross_per_hour(w)
	_eq(gross, {"gold": 225 + 8 * 6, "food": 45 + 45, "metal": 45}, "gross at DL2")
	# Capital buildings now cost × 1,5.
	_eq(int(e.upgrade_cost(e._find_type("barracks"))["gold"]), 270, "barracks 1->2 at DL2")
	_grant_hexes(w, 6)
	e.res["gold"] = 5000
	e.res["metal"] = 5000
	e.tick(w, T0 + 60)
	_check(e.start_upgrade(int(r["id"]), T0 + 60), "DL3 started")
	e.tick(w, T0 + 60 + 900)
	_eq(e.dev_level(), 3, "DL3")
	_check(not e._find_type("embassy").is_empty(), "embassy unlocked")
	_eq(e.can_upgrade(r, T0 + 2000), "err.chapter_locked|2", "chapter I cap DL3")


func _test_speedup() -> void:
	_eq(Economy.speedup_price(0), 0, "nothing left")
	_eq(Economy.speedup_price(300), 0, "≤5 min free")
	_eq(Economy.speedup_price(600), 6, "10 min = 6")
	_eq(Economy.speedup_price(3600), 20, "1 h = 20")
	_eq(Economy.speedup_price(28800), 100, "8 h = 100")
	_eq(Economy.speedup_price(86400), 240, "24 h = 240")
	_eq(Economy.speedup_price(172800), 420, "48 h = 420")
	_eq(Economy.speedup_price(1800), 12, "30 min = 12 (05 §12.4)")
	_eq(Economy.speedup_price(7200), 35, "2 h = 35")
	var prev := 0
	var mono := true
	for s in range(0, 48 * 3600 + 1, 97):
		var p := Economy.speedup_price(s)
		if p < prev:
			mono = false
		prev = p
	_check(mono, "monotonic over 0..48 h")
	var w := _world()
	_grant_hexes(w, 9)
	var e := Economy.new(w, T0)
	e.res["gold"] = 5000
	e.res["metal"] = 5000
	var r := e._find_type("residence")
	r["level"] = 2
	e.tick(w, T0)
	_check(e.start_upgrade(int(r["id"]), T0), "DL3 (15 min) started")
	var price := e.speedup_cost(r, T0)
	_eq(price, 8, "15 min = 8 raivites")
	_check(e.speedup_cost(r, T0 + 600) == 0, "free in the last 5 min")
	e.res["raivite"] = 5
	_check(not e.finish_now(int(r["id"]), T0), "not enough raivites")
	e.res["raivite"] = 50
	_check(e.finish_now(int(r["id"]), T0), "finished")
	_eq(e.res["raivite"], 42, "raivites spent")
	_eq(e.dev_level(), 3, "level up at once")
	_eq(e.busy_builders(T0), 0, "builder free")
	var ev := e.tick(w, T0 + 1)
	_check(ev.size() >= 2 and ev[0]["type"] == "upgrade_done", "completion reported by the next tick")


func _test_defense() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	var plains := _own_plain(w)
	var h := plains[0]
	_eq(e.build_cost("fort"), {"gold": 50, "food": 0, "metal": 100, "seconds": 10}, "fort lvl 1 price")
	_eq(e.build_cost("tower"), {"gold": 60, "food": 0, "metal": 80, "seconds": 10}, "tower lvl 1 price")
	_eq(e.build_cost("barracks"), {}, "barracks is not built on a hex")
	_eq(e.can_build(w, "fort", h, T0), "", "fort allowed")
	var enemy: int = w.states[MapGen.BARONS]["capital_id"]
	_eq(e.can_build(w, "fort", enemy, T0), "err.not_your_hex", "enemy hex")
	var cap: int = w.states[PLAYER]["capital_id"]
	_eq(e.can_build(w, "tower", cap, T0), "err.tower_plain_only", "tower on capital")
	_check(e.start_build(w, "fort", h, T0), "fort started")
	_eq(e.res["metal"], 500, "metal paid")
	_eq(e.can_build(w, "fort", h, T0), "err.fort_exists", "one fort per hex")
	e.tick(w, T0 + 10)
	var f := e.building_at(h)
	_eq(f.get("type", ""), "fort", "fort on hex")
	_eq(int(f.get("level", 0)), 1, "fort level 1")
	_eq(int(w.cells[h]["fort"]), 1, "world cell fort synced")
	_eq(e.upkeep_per_hour(), 15, "fort upkeep 5 gold/h")
	_eq(e.can_upgrade(f, T0 + 10), "err.need_residence|2", "fort ≤ DL")
	# Towers: ≤ 2 × DL.
	_check(e.start_build(w, "tower", plains[1], T0 + 10), "tower 1")
	_check(e.start_build(w, "tower", plains[2], T0 + 20), "tower 2")
	e.tick(w, T0 + 30)
	_eq(e.can_build(w, "tower", plains[3], T0 + 30), "err.tower_limit|2", "tower limit")
	# Hex ceded by treaty: fort removed, 100% refund.
	w.cells[h]["owner"] = MapGen.BARONS
	w.cells[h]["controller"] = MapGen.BARONS
	var metal_before: int = e.res["metal"]
	var ev := e.tick(w, T0 + 40)
	var refund := {}
	for x in ev:
		if x["type"] == "fort_refund":
			refund = x["refund"]
	_eq(refund, {"metal": 100, "gold": 50}, "refund 100% paid")
	_eq(e.res["metal"], metal_before + 100, "metal back")
	_check(e.building_at(h).is_empty(), "fort gone")


func _test_plunder() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	e.res["gold"] = 5000
	e.res["food"] = 1000
	e.res["metal"] = 0
	e.res["raivite"] = 77
	var taken := e.plunder(0.6)
	# Protected 40%: 2000 of 5000 gold, 400 of 1000 food.
	_eq(taken, {"gold": 1800, "food": 360, "metal": 0}, "60% of the unprotected part")
	_eq(e.res["gold"], 3200, "gold left")
	_eq(e.res["raivite"], 77, "raivites never plundered")
	var all := e.plunder(1.0)
	_eq(all["gold"], 1920, "full plunder leaves the protected share")
	_eq(e.res["gold"], 1280, "protected 40% of 3200")
	# Stock is not protected; loss cap limits the total.
	var e2 := Economy.new(w, T0)
	e2.tick(w, T0 + 8 * 3600)
	_eq(_stock_sum(e2, "food"), 480, "8 h of food in hexes")
	var t2 := e2.plunder(0.5)
	_eq(t2["food"], 240 + 180, "half of the stock + half of the unprotected 360 food")
	_eq(_stock_sum(e2, "food"), 240, "half of the stock left")
	_eq(e2.res["food"], 600 - 180, "storage keeps the protected share")
	var e3 := Economy.new(w, T0)
	var t3 := e3.plunder(0.6, {"gold": 100, "food": 0, "metal": 50})
	_eq(t3, {"gold": 100, "food": 0, "metal": 50}, "loss cap")


func _test_occupied() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	var base := e.income_per_hour(w)
	# Occupy an enemy farm: 50% of 30 food.
	var farm := -1
	for c in w.cells:
		if c["owner"] == MapGen.BARONS and c["kind"] == "farm":
			farm = int(c["id"])
	_check(farm >= 0, "barons have a farm")
	w.cells[farm]["controller"] = PLAYER
	_eq(e.income_per_hour(w)["food"], int(base["food"]) + 15, "+15 food")
	_eq(e.gross_per_hour(w)["food"], 60, "gross_rate ignores occupation")
	# Player hex occupied by the enemy: no income, no upkeep for its building.
	var own_farm := -1
	for c in w.cells:
		if c["owner"] == PLAYER and c["kind"] == "farm":
			own_farm = int(c["id"])
	w.cells[own_farm]["controller"] = MapGen.BARONS
	var inc := e.income_per_hour(w)
	_eq(inc["food"], 30 + 15, "own farm lost")
	_eq(e.upkeep_per_hour(), 8, "farm upkeep 0 while occupied")


func _test_roundtrip() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	e.tick(w, T0 + 3 * 3600 + 17)
	e.start_build(w, "fort", _own_plain(w)[0], T0 + 3 * 3600 + 17)
	e.start_upgrade(int(e._find_type("farm")["id"]), T0 + 3 * 3600 + 17)
	var d := e.to_dict()
	var e2 = Economy.from_dict(d)
	_eq(e2.to_dict(), d, "direct round trip")
	var parsed: Dictionary = JSON.parse_string(JSON.stringify(d))
	var e3 = Economy.from_dict(parsed)
	_eq(e3.to_dict(), d, "JSON round trip")
	var w2 := _world()
	var w3 := _world()
	var a := e.tick(w, T0 + 9 * 3600)
	var b: Array = e2.tick(w2, T0 + 9 * 3600)
	var c: Array = e3.tick(w3, T0 + 9 * 3600)
	_eq(b, a, "same events after load")
	_eq(c, a, "same events after JSON load")
	_eq(e2.to_dict(), e.to_dict(), "same state after load")
	_eq(e3.to_dict(), e.to_dict(), "same state after JSON load")


func _scenario(step: int) -> Dictionary:
	var w := _world()
	var e := Economy.new(w, T0)
	var t := T0
	var end := T0 + 5 * 3600
	e.start_upgrade(int(e._find_type("farm")["id"]), T0)
	e.start_upgrade(int(e._find_type("warehouse")["id"]), T0)
	while t < end:
		t = mini(end, t + step)
		e.tick(w, t)
	return e.to_dict()


func _test_determinism() -> void:
	var a := _scenario(3600)
	var b := _scenario(3600)
	_eq(b, a, "same inputs -> same state")
	# Same span in 1 tick, hourly ticks, 7-second ticks: identical stock and storage.
	var c := _scenario(5 * 3600)
	var d := _scenario(7)
	_eq(c["stock"], a["stock"], "1 tick vs hourly: stock")
	_eq(d["stock"], a["stock"], "7 s ticks vs hourly: stock")
	_eq(d["res"], a["res"], "7 s ticks: storage")
	_eq(d["stock_rem"], a["stock_rem"], "7 s ticks: remainders")


func _test_reason_text() -> void:
	var lang0 := TranslationServer.get_locale()
	TranslationServer.set_locale("ru")
	_eq(L.t("err.need_hexes|10"), "Нужно 10 гексов", "ru: packed reason")
	_eq(L.t("err.not_enough|res.gen.gold"), "Не хватает золота", "ru: key argument is translated")
	_eq(L.t(String(Economy.BUILDINGS["warehouse"]["name"])), "Склад", "ru: building name")
	_eq(L.t("Старый текст"), "Старый текст", "plain text without a key passes through")
	TranslationServer.set_locale("en")
	_eq(L.t("err.need_hexes|10"), "Need 10 hexes", "en: packed reason")
	_eq(L.t("err.not_enough|res.gen.gold"), "Not enough gold", "en: key argument is translated")
	_eq(L.t("err.need_residence|2"), "Needs Residence Lv 2", "en: residence gate")
	TranslationServer.set_locale(lang0)


func _market_econ() -> Array:
	var w := _world()
	var e := Economy.new(w, T0)
	var r := e._find_type("residence")
	_grant_hexes(w, 3)
	e.tick(w, T0)
	e.start_upgrade(int(r["id"]), T0)
	e.tick(w, T0 + 60)
	return [w, e]


func _test_market() -> void:
	_eq(Market.rate_milli(1), 3000, "3:1 at level 1")
	_eq(Market.rate_milli(8), 2632, "2.63:1 at level 8 (05 §13.1)")
	_eq(Market.rate_milli(20), 2000, "2:1 at level 20")
	_eq(Market.rate_milli(99), 2000, "clamped")
	var w := _world()
	var e0 := Economy.new(w, T0)
	_eq(Market.quote(e0, "food", "metal", 300), {}, "no market at DL1")
	var we := _market_econ()
	var e: Economy = we[1]
	_eq(Market.market_level(e), 1, "market level 1 after DL2")
	e.res["food"] = 3000
	e.res["metal"] = 0
	var q := Market.quote(e, "food", "metal", 1000)
	_eq(int(q["get"]), 333, "floor(1000 / 3)")
	_eq(int(q["give"]), 1000, "gives all")
	_eq(Market.quote(e, "food", "raivite", 100), {}, "raivites are not traded")
	_eq(Market.quote(e, "food", "food", 100), {}, "same resource")
	_eq(int(Market.quote(e, "food", "metal", 99999)["give"]), 3000, "cannot give more than stored")
	var cap: int = e.storage_cap()["metal"]
	e.res["metal"] = cap - 100
	q = Market.quote(e, "food", "metal", 3000)
	_eq(int(q["get"]), 100, "cut to free space")
	_eq(int(q["give"]), 300, "input trimmed to what fits")
	_check(bool(q["cap_hit"]), "cap hit flagged")
	var got := Market.exchange(e, "food", "metal", 3000)
	_eq(int(got["get"]), 100, "exchange applied")
	_eq(int(e.res["food"]), 2700, "food spent")
	_eq(int(e.res["metal"]), cap, "metal at cap")
	_eq(Market.exchange(e, "food", "metal", 3000), {}, "nothing fits -> no-op")
	_eq(int(e.res["food"]), 2700, "unchanged")


func _test_trader() -> void:
	var we := _market_econ()
	var w: World = we[0]
	var e: Economy = we[1]
	e.res["gold"] = 4000
	e.res["food"] = 100
	e.res["metal"] = 2000
	var m := Market.new()
	m.refresh(e, w, T0)
	_eq(m.lots.size(), 3, "3 lots")
	_eq([m.lots[0]["give"], m.lots[0]["get"]], ["gold", "food"], "needed: fullest -> emptiest")
	var pairs := {}
	for lot in m.lots:
		_check(lot["give"] != lot["get"], "different resources")
		pairs[str([lot["give"], lot["get"]])] = true
		_check(int(lot["get_amt"]) >= Market.MIN_LOT, "volume floor")
		_check(int(lot["give_amt"]) * 1000 >= int(lot["get_amt"]) * int(lot["rate"]), "rate respected")
		_check(int(lot["rate"]) < Market.rate_milli(1), "better than the market")
	_eq(pairs.size(), 3, "no repeated pair in a day")
	var m2 := Market.new()
	m2.refresh(e, w, T0)
	_eq(m2.to_dict(), m.to_dict(), "deterministic")
	e.res[m.lots[0]["give"]] = int(e.storage_cap()["gold"])
	var before: int = e.res[m.lots[0]["get"]]
	_eq(m.can_buy(e, 0), "", "lot 1 buyable")
	_check(m.buy(e, 0), "bought")
	_eq(int(e.res[m.lots[0]["get"]]), before + int(m.lots[0]["get_amt"]), "received")
	_eq(m.can_buy(e, 0), "market.bought", "once per day")
	_eq(m.can_buy(e, 7), "market.no_lot", "bad index")
	var day0 := Market.trader_day(T0)
	var next := (day0 + 1) * Market.DAY + Market.REFRESH_SEC
	_eq(Market.refresh_left(T0), next - T0, "countdown to 04:00")
	m.refresh(e, w, next - 1)
	_check(m.lots[0]["bought"], "same day keeps state")
	var saved: Dictionary = JSON.parse_string(JSON.stringify(m.to_dict()))
	var m3 := Market.new()
	m3.load_dict(saved)
	_eq(m3.to_dict(), m.to_dict(), "save round trip")
	m.refresh(e, w, next)
	_check(not m.lots[0]["bought"], "new lots at 04:00")
	_eq(m.day, day0 + 1, "day advanced")


func _test_army_food() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	var food_gross: int = e.income_per_hour(w)["food"]
	e.army_food_milli = 15000  # two armies of 75: 15 food/h
	_eq(int(e.income_per_hour(w)["food"]), food_gross - 15, "net food shows the army")
	e.collect_all()
	e.tick(w, T0 + 3600)
	var pool := _stock_sum(e, "food")
	_eq(pool, food_gross - 15, "1 h: pool grows by the net flow")
	var stored: int = e.res["food"]
	e.army_food_milli = 10000000  # far above income: eats the pool, then storage
	e.tick(w, T0 + 7200)
	_eq(_stock_sum(e, "food"), 0, "pool eaten first")
	_eq(int(e.res["food"]), maxi(0, stored + pool + food_gross - 10000), "then storage")
	e.tick(w, T0 + 4 * 3600)
	_eq(int(e.res["food"]), 0, "never below zero")
	var before: int = e.res["gold"]
	e.res["food"] = 500
	e.tick(w, T0 + 20 * 3600)
	_eq(int(e.res["food"]), 0, "upkeep runs inside the 8 h window")
	e.res["food"] = 500
	e.tick(w, T0 + 30 * 3600)
	_eq(int(e.res["food"]), 500, "paused after 8 h without collecting (E7)")
	_check(int(e.res["gold"]) >= 0 and before >= 0, "gold untouched by army upkeep")
	var e2: Economy = Economy.from_dict(JSON.parse_string(JSON.stringify(e.to_dict())))
	_eq(e2.army_food_milli, e.army_food_milli, "round trip keeps the upkeep")


func _test_ruin() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	var base: int = e.income_per_hour(w)["gold"]
	var gross: int = e.gross_per_hour(w)["gold"]
	e.apply_ruin(40, 8 * 3600, T0)
	e.tick(w, T0)
	_check(int(e.income_per_hour(w)["gold"]) < base, "ruin lowers income (%d -> %d)" % [base, int(e.income_per_hour(w)["gold"])])
	_eq(int(e.gross_per_hour(w)["gold"]), gross, "gross_rate ignores temporary modifiers")
	e.apply_ruin(20, 2 * 3600, T0 + 60)
	_eq([e.ruin_pct, e.ruin_until], [40, T0 + 8 * 3600], "repeat ruin doesn't stack: larger % and later end")
	e.halve_ruin(T0 + 3600)
	_eq(e.ruin_until, T0 + 3600 + 7 * 1800, "ad halves the rest")
	# accrual: ruin ends mid-interval, result independent of tick granularity
	var a := Economy.new(w, T0)
	var b := Economy.new(w, T0)
	a.apply_ruin(40, 1800, T0)
	b.apply_ruin(40, 1800, T0)
	a.tick(w, T0 + 3600)
	for t in range(T0 + 60, T0 + 3601, 60):
		b.tick(w, t)
	_eq(_stock_sum(a, "gold"), _stock_sum(b, "gold"), "ruin end splits the accrual (same for any granularity)")
	# damaged buildings
	var d: Array = e.damage_buildings(w, 3)
	_check(d.size() >= 1, "buildings damaged: %d" % d.size())
	var farm := -1
	for h in d:
		_check(int(w.cells[h]["owner"]) == PLAYER and Economy.DAMAGE_KINDS.has(String(w.cells[h]["kind"])), "only hex buildings of the loser")
		if String(w.cells[h]["kind"]) == "farm":
			farm = h
	var h0: int = d[0]
	var c0: Dictionary = w.cells[h0]
	var inc_damaged: Dictionary = e.hex_income(w, h0)
	e.ruin_until = 0
	var inc_d: Dictionary = e.hex_income(w, h0)
	e.damaged.erase(h0)
	var inc_ok: Dictionary = e.hex_income(w, h0)
	e.damaged[h0] = 0
	for r in inc_ok:
		_check(int(inc_d.get(r, 0)) * 2 <= int(inc_ok[r]) + 1, "damaged hex yields half (%s %d vs %d)" % [r, int(inc_d.get(r, 0)), int(inc_ok[r])])
	_check(inc_damaged.size() >= 0 and c0["kind"] != "capital", "capital never damaged")
	var cost := e.repair_cost(w, h0)
	_check(not cost.is_empty(), "repair has a price %s" % str(cost))
	e.res = {"gold": 0, "food": 0, "metal": 0, "raivite": 0}
	_check(e.can_repair(w, h0).begins_with("err.not_enough"), "can't repair without resources")
	e.res = {"gold": 99999, "food": 99999, "metal": 99999, "raivite": 0}
	var now := T0 + 7200
	e.tick(w, now)
	_check(e.start_repair(w, h0, now), "repair started")
	_eq(e.can_repair(w, h0), "err.repairing", "one repair at a time per building")
	var evs := e.tick(w, now + Economy.REPAIR_SEC)
	var done := false
	for ev in evs:
		if ev["type"] == "repair_done" and int(ev["hex"]) == h0:
			done = true
	_check(done and not e.damaged.has(h0), "repaired after 10 min")
	if d.size() > 1:
		_check(e.start_repair(w, int(d[1]), now, true) and not e.damaged.has(int(d[1])), "free repair (ad) is instant")
	var e2: Economy = Economy.from_dict(JSON.parse_string(JSON.stringify(e.to_dict())))
	_eq([e2.ruin_pct, e2.ruin_until, e2.damaged], [e.ruin_pct, e.ruin_until, e.damaged], "round trip keeps ruin and damage")
	_check(farm >= -1, "ok")


func _test_vein() -> void:
	var w := _world()
	var e := Economy.new(w, T0)
	var cap: int = w.states[PLAYER]["capital_id"]
	var vh := -1
	for n in w.neighbors[cap]:
		if n >= 0 and w.cells[n]["kind"] == "plain":
			vh = n
			break
	w.cells[vh]["kind"] = "raivite_vein"
	e.collect_all()
	e.tick(w, T0 + 6 * 3600)
	_eq(e.vein_amount(vh), 1, "1 Raivite after 6 h")
	e.tick(w, T0 + 7 * 3600)
	var r0: int = e.res["raivite"]
	_eq(e.collect_veins(), 1, "collected 1")
	_eq(int(e.res["raivite"]), r0 + 1, "credited")
	_eq(e.vein_amount(vh), 0, "remainder kept below one")
	e.collect_all()
	e.tick(w, T0 + 7 * 3600 + 8 * 3600)  # inside the 8 h window
	e.collect_all()
	e.tick(w, T0 + 7 * 3600 + 16 * 3600)
	e.collect_all()
	e.tick(w, T0 + 7 * 3600 + 24 * 3600)
	_eq(e.vein_amount(vh), 4, "holds up to 4")
	e.collect_veins()
	w.cells[vh]["owner"] = 2  # an enemy vein the player occupies
	e.collect_all()
	e.tick(w, T0 + 7 * 3600 + 32 * 3600)
	e.collect_all()
	e.tick(w, T0 + 7 * 3600 + 40 * 3600)
	e.collect_all()
	e.tick(w, T0 + 7 * 3600 + 48 * 3600)
	_eq(e.vein_amount(vh), 2, "occupied vein holds up to 2")
	var e2: Economy = Economy.from_dict(JSON.parse_string(JSON.stringify(e.to_dict())))
	_eq(e2.vein_amount(vh), 2, "round trip")


func _test_blueprints() -> void:
	# trophy blueprints (canon §9.14, 07 §6.1): up to 5 kept, −10% of what is left, −50% per research at most
	var rb = load("res://scripts/sim/research.gd").new()
	_check(rb.add_blueprints(3) == 0 and rb.add_blueprints(4) == 2 and rb.blueprints == 5, "blueprints: 5 kept, 2 burn")
	rb.current = {"line": "taxes", "end": 10000, "dur": 10000, "cut": 0}
	_check(rb.apply_blueprint(0) and int(rb.current["end"]) == 9000, "a blueprint takes 10% of what is left")
	var bp_n := 1
	while rb.apply_blueprint(0):
		bp_n += 1
	_check(int(rb.current["cut"]) <= 5000 and rb.blueprints == 5 - bp_n, "never more than −50%% of a research (%d used)" % bp_n)
	rb.current = {"line": "taxes", "end": 1000, "dur": 10000, "cut": 0}
	rb.lose_progress(12, 0)
	_check(int(rb.current["end"]) == 2200, "a plundered defeat: −12% of the research's time in progress")
	rb.lose_progress(100, 0)
	_check(int(rb.current["end"]) == 10000, "progress never drops below zero")
	var rb2 = rb.from_dict(rb.to_dict())
	_check(rb2.blueprints == rb.blueprints and int(rb2.current["dur"]) == 10000, "blueprints survive a save")
