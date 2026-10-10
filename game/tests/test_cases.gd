extends SceneTree
## Headless tests for the cases / lootboxes rules module (scripts/sim/cases.gd, data/cases.json).
## Run: godot --headless --path game --script res://tests/test_cases.gd

const Cases := preload("res://scripts/sim/cases.gd")

const SEED := 20261005
const T0 := 1790000000
const CTX := {"income_per_hour": {"gold": 100, "food": 50, "metal": 40}, "dl": 3}
## The statistical runs (§9.10.11 asks for 1 M per case on the server; here a smaller headless budget).
const STAT_ROYAL := 300000
const STAT_CRATE := 250000
const STAT_ARENA := 100000
## Fixed commander state for the statistical runs, so the war crate's «not yet unlocked ×2» weights do
## not drift while shards accumulate.
const ALL_OWNED := ["cmd_bram", "cmd_lira", "cmd_olm", "cmd_vik", "cmd_vega", "cmd_kort", "cmd_seir",
	"cmd_frey", "cmd_irma", "cmd_hawk", "cmd_vance", "cmd_rai"]

var _errors: Array[String] = []
var _failed := 0
var _passed := 0
var _checks := 0


func _init() -> void:
	# Names and pity texts are checked in Russian (the reference language); _test_english switches over.
	TranslationServer.set_locale("ru")
	var tests: Array[Array] = [
		["data: every case loads, tier weights match tier p", _test_data],
		["determinism with a seed", _test_determinism],
		["war crate: cosmetic not later than the 60th opening", _test_crate_pity],
		["trophy chests share the crate counter, arena has none", _test_trophy_arena],
		["royal: epic+ every 10, ×10 guarantee, forced split by p_leg", _test_royal_epic],
		["royal: legendary soft pity from 40 (+6%), hard at 50", _test_royal_legendary],
		["effective odds match 09 §9.10.2 / §9.10.5", _test_effective],
		["«Цель»: 50% of epic / legendary shards", _test_target],
		["collection: no duplicates, 8 openings, growing legendary chance, prices", _test_collection],
		["duplicates turn into Блёстки", _test_duplicates],
		["rewards: resource hours, ×N, oil fallback, speed-ups", _test_rewards],
		["free crate timer: 6 h, stores 2", _test_free_crates],
		["history keeps the last 100", _test_history],
		["odds_items: rows sum to 100%, pools expand", _test_odds_items],
		["pity_text and price", _test_texts],
		["English names and texts (name_en, pity.* keys); name_ru stays Russian", _test_english],
		["to_dict / from_dict round trip (also via JSON)", _test_roundtrip],
		["statistics: royal rarity and item frequencies = odds()", _test_stat_royal],
		["statistics: war crate and arena frequencies = odds()", _test_stat_crate],
	]
	var t_start := Time.get_ticks_msec()
	for t in tests:
		_errors.clear()
		var t0 := Time.get_ticks_msec()
		(t[1] as Callable).call()
		var dt := Time.get_ticks_msec() - t0
		if _errors.is_empty():
			_passed += 1
			print("PASS  %s  (%d ms)" % [t[0], dt])
		else:
			_failed += 1
			print("FAIL  %s  (%d ms)" % [t[0], dt])
			for e in _errors.slice(0, 10):
				print("      - " + e)
	print("\n%d passed, %d failed (%d checks, %.1f s)" % [_passed, _failed, _checks,
		float(Time.get_ticks_msec() - t_start) / 1000.0])
	quit(1 if _failed > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checks += 1
	if not cond:
		_errors.append(msg)


func _eq(actual: Variant, expected: Variant, msg: String) -> void:
	_checks += 1
	if actual != expected:
		_errors.append("%s: expected %s, got %s" % [msg, str(expected), str(actual)])


func _near(actual: float, expected: float, tol: float, msg: String) -> void:
	_checks += 1
	if absf(actual - expected) > tol:
		_errors.append("%s: expected %.4f ± %.4f, got %.4f" % [msg, expected, tol, actual])


func _row(rows: Array, rarity: String) -> Dictionary:
	for rv in rows:
		var r: Dictionary = rv
		if String(r["rarity"]) == rarity:
			return r
	return {}


## Chi-square critical value for p = 0.001 (Wilson–Hilferty, z = 3.09).
func _chi2_crit(df: int) -> float:
	var k := float(df)
	var a := 2.0 / (9.0 * k)
	return k * pow(1.0 - a + 3.09 * sqrt(a), 3.0)


# ---------------------------------------------------------------- tests

func _test_data() -> void:
	var ids := Cases.case_ids()
	for id in ["case_war_crate", "case_trophy_bronze", "case_trophy_silver", "case_trophy_gold",
			"case_arena_chest", "case_royal", "case_collection"]:
		_check(ids.has(id), "case %s present" % id)
	for id in ["case_war_crate", "case_royal"]:
		var tiers: Dictionary = (Cases.data()["cases"] as Dictionary)[id]["tiers"]
		var psum := 0.0
		for r in Cases.RARITIES:
			var t: Dictionary = tiers[r]
			psum += float(t["p"])
			var wsum := 0.0
			for iv in (t["items"] as Array):
				wsum += float((iv as Dictionary)["w"])
			_near(wsum / 100.0, float(t["p"]), 1e-9, "%s %s: Σw = p" % [id, r])
		_near(psum, 1.0, 1e-9, "%s: Σp = 1" % id)
	var pools: Dictionary = Cases.data()["pools"]
	for pid in pools:
		for cid in (pools[pid] as Array):
			_check(not Cases.cosmetic(String(cid)).is_empty(), "%s: cosmetic %s defined" % [pid, cid])
	for cid in (Cases.data()["cases"]["case_collection"]["set"] as Array):
		_check(not Cases.cosmetic(String(cid)).is_empty(), "collection: cosmetic %s defined" % cid)
	_eq((pools["pool_crate"] as Array).size(), 6, "crate pool size")
	_eq((pools["pool_royal_rare"] as Array).size(), 6, "royal rare pool size")
	_eq((pools["pool_royal_epic"] as Array).size(), 8, "royal epic pool size")
	_eq((pools["pool_royal_legendary"] as Array).size(), 5, "royal legendary pool size")
	_eq(String(Cases.commander("cmd_vance")["name"]), "Леди Вэнс", "commander name")
	_eq(String(Cases.commander("cmd_rai")["rarity"]), "legendary", "Император Рай is legendary")


func _test_determinism() -> void:
	var a := Cases.new(SEED)
	var b := Cases.new(SEED)
	var c := Cases.new(SEED + 1)
	var sa: Array = []
	var sb: Array = []
	var sc: Array = []
	for i in range(300):
		var id := ["case_war_crate", "case_royal", "case_trophy_gold", "case_arena_chest"][i % 4] as String
		sa.append(a.open(id, CTX, T0 + i))
		sb.append(b.open(id, CTX, T0 + i))
		sc.append(c.open(id, CTX, T0 + i))
	_eq(JSON.stringify(sa), JSON.stringify(sb), "same seed → same openings")
	_check(JSON.stringify(sa) != JSON.stringify(sc), "different seed → different openings")
	_eq(JSON.stringify(a.to_dict()), JSON.stringify(b.to_dict()), "same seed → same state")


func _test_crate_pity() -> void:
	var c := Cases.new(SEED)
	var since := 0
	var worst := 0
	var hits := 0
	for i in range(30000):
		var r := c.open("case_war_crate", CTX, T0 + i)
		since += 1
		if String(r["rarity"]) == "legendary":
			hits += 1
			worst = maxi(worst, since)
			since = 0
			var kind := String((r["rewards"][0] as Dictionary)["kind"])
			_check(kind == "cosmetic" or kind == "glitter", "legendary cell gives cosmetic")
	_check(worst <= 60, "cosmetic not later than the 60th opening (worst %d)" % worst)
	_check(worst == 60, "the hard guarantee is actually reached in 30k openings")
	_check(hits > 0, "cosmetics drop")
	# State right before the guarantee.
	var d := Cases.new(SEED)
	d.pity["crate_cosmetic"] = 58
	_near(float(d.current_probs("case_war_crate")["legendary"]), 0.005, 1e-12, "59th opening: base 0,5%")
	d.pity["crate_cosmetic"] = 59
	_near(float(d.current_probs("case_war_crate")["legendary"]), 1.0, 1e-12, "60th opening: 100%")
	var r2 := d.open("case_war_crate", CTX, T0)
	_eq(String(r2["rarity"]), "legendary", "60th opening forced")
	_check(bool(r2["forced"]), "forced flag")
	_eq(int(d.pity["crate_cosmetic"]), 0, "counter reset")


func _test_trophy_arena() -> void:
	var c := Cases.new(SEED)
	c.pity["crate_cosmetic"] = 10
	var r := c.open("case_arena_chest", CTX, T0)
	_eq(int(c.pity["crate_cosmetic"]), 10, "arena chest does not move the crate counter")
	if String(r["rarity"]) != "legendary":
		c.open("case_trophy_bronze", CTX, T0)
		var v := int(c.pity["crate_cosmetic"])
		_check(v == 11 or v == 0, "bronze trophy moves the shared counter")
	c.pity["crate_cosmetic"] = 59
	var r2 := c.open("case_trophy_silver", CTX, T0)
	_eq(String(r2["rarity"]), "legendary", "silver trophy honours the shared guarantee")
	_eq(c.pity_text("case_arena_chest"), "", "arena: no pity line")
	# Arena: never forced, odds = base.
	c.pity["crate_cosmetic"] = 59
	_near(float(c.current_probs("case_arena_chest")["legendary"]), 0.005, 1e-12, "arena stays at base")
	# Gold trophy: 5 epic shards always.
	var g := Cases.new(SEED)
	for i in range(200):
		var rg := g.open("case_trophy_gold", CTX, T0 + i)
		var found := false
		for rv in (rg["rewards"] as Array):
			var rw: Dictionary = rv
			if String(rw["kind"]) == "shards" and String(rw["rarity"]) == "epic" and int(rw["n"]) == 5:
				found = true
		_check(found, "gold trophy: 5 epic shards every time")


func _test_royal_epic() -> void:
	var c := Cases.new(SEED)
	var since := 0
	var worst := 0
	var forced_total := 0
	var forced_leg := 0
	for i in range(20000):
		var r := c.open("case_royal", CTX, T0 + i)
		var rr := String(r["rarity"])
		since += 1
		if rr == "epic" or rr == "legendary":
			worst = maxi(worst, since)
			since = 0
	_check(worst <= 10, "epic+ at least every 10 openings (worst %d)" % worst)
	_eq(worst, 10, "the every-10 guarantee is reached")
	# ×10 always contains epic+, from any counter state.
	var d := Cases.new(SEED + 7)
	for k in range(1500):
		var batch := d.open_x10("case_royal", CTX, T0 + k)
		_eq(batch.size(), 10, "×10 gives 10 results")
		var has := false
		for bv in batch:
			var rr2 := String((bv as Dictionary)["rarity"])
			if rr2 == "epic" or rr2 == "legendary":
				has = true
		_check(has, "×10 #%d contains epic+" % k)
		if not has:
			break
	# Forced epic+ outside the soft zone: legendary with 1,5 / (1,5 + 8,5) = 15%.
	var p := Cases._probs_at("case_royal", 0, 9)
	_near(float(p["legendary"]), 0.15, 1e-12, "forced epic+ → legendary 15%")
	_near(float(p["epic"]), 0.85, 1e-12, "forced epic+ → epic 85%")
	_near(float(p["common"]) + float(p["rare"]), 0.0, 1e-12, "forced: no common / rare")
	# Inside the soft zone the forced draw uses p_leg(n) (§9.10.5).
	var p2 := Cases._probs_at("case_royal", 44, 9)
	_near(float(p2["legendary"]), 0.375 / (0.375 + 0.085), 1e-12, "forced epic+ at n = 45")
	# Empirical share of legendary among forced draws (outside soft pity).
	var e := Cases.new(SEED + 11)
	for i in range(40000):
		var ep := int(e.pity.get("royal_epic", 0))
		var lp := int(e.pity.get("royal_leg", 0))
		var r3 := e.open("case_royal", CTX, T0 + i)
		if ep == 9 and lp < 39:
			forced_total += 1
			if String(r3["rarity"]) == "legendary":
				forced_leg += 1
	var share := float(forced_leg) / float(forced_total)
	var sd := sqrt(0.15 * 0.85 / float(forced_total))
	_near(share, 0.15, 4.0 * sd, "legendary share among forced epic+ (%d draws)" % forced_total)


func _test_royal_legendary() -> void:
	var expect := {39: 0.015, 40: 0.075, 41: 0.135, 45: 0.375, 49: 0.615, 50: 1.0}
	for n in expect:
		var p := Cases._probs_at("case_royal", int(n) - 1, 0)
		_near(float(p["legendary"]), float(expect[n]), 1e-12, "p_leg(%d)" % n)
		if int(n) < 50:
			_near(float(p["epic"]), 0.085, 1e-12, "epic holds 8,5%% at n = %d" % n)
			var cr := float(p["common"]) + float(p["rare"])
			_near(float(p["common"]) / cr, 62.0 / 90.0, 1e-12, "common : rare = 62 : 28 at n = %d" % n)
			_near(float(p["common"]) + float(p["rare"]) + float(p["epic"]) + float(p["legendary"]), 1.0, 1e-12,
				"Σ = 1 at n = %d" % n)
	var c := Cases.new(SEED)
	var since := 0
	var worst := 0
	var soft_hits := 0
	for i in range(30000):
		var r := c.open("case_royal", CTX, T0 + i)
		since += 1
		if String(r["rarity"]) == "legendary":
			if since >= 40:
				soft_hits += 1
			worst = maxi(worst, since)
			since = 0
	_check(worst <= 50, "legendary not later than the 50th opening (worst %d)" % worst)
	_check(soft_hits > 0, "soft pity hits happen")
	var d := Cases.new(SEED)
	d.pity["royal_leg"] = 49
	var r2 := d.open("case_royal", CTX, T0)
	_eq(String(r2["rarity"]), "legendary", "50th opening forced legendary")
	_eq(int(d.pity["royal_leg"]), 0, "legendary counter reset")
	_eq(int(d.pity["royal_epic"]), 0, "legendary also resets the epic+ counter")


func _test_effective() -> void:
	var e := Cases.effective_probs("case_royal")
	_near(100.0 * float(e["legendary"]), 3.53, 0.01, "royal legendary effective 3,53%")
	_near(100.0 * float(e["epic"]), 12.51, 0.01, "royal epic effective 12,51%")
	_near(100.0 * float(e["rare"]), 26.12, 0.01, "royal rare effective 26,12%")
	_near(100.0 * float(e["common"]), 57.84, 0.01, "royal common effective 57,84%")
	var w := Cases.effective_probs("case_war_crate")
	_near(100.0 * float(w["legendary"]), 1.925, 0.001, "crate cosmetic effective 1,925%")
	_near(100.0 * float(w["common"]), 73.93, 0.01, "crate common effective (75% × 0,98568)")
	var a := Cases.effective_probs("case_arena_chest")
	_near(100.0 * float(a["legendary"]), 0.5, 1e-9, "arena: effective = base")
	var c := Cases.new(SEED)
	var rows := c.odds("case_royal")
	_eq(rows.size(), 4, "royal: 4 rarity rows")
	_near(float(_row(rows, "legendary")["base"]), 1.5, 1e-9, "odds(): base legendary 1,5")
	_near(float(_row(rows, "legendary")["effective"]), 3.53, 0.01, "odds(): effective legendary 3,53")
	_eq(String(_row(rows, "epic")["name_ru"]), "Эпическое", "rarity name")
	# Steampunk: 0,12% / 0,28% (§9.10.4).
	var items := c.odds_items("case_royal", "legendary")
	for iv in items:
		var it: Dictionary = iv
		if String(it["id"]) == "cosmetic_legendary":
			for ev in (it["entries"] as Array):
				var en: Dictionary = ev
				if String(en["id"]) == "cos_capital_skin_steampunk":
					_near(float(en["base"]), 0.12, 0.0005, "Стимпанк base")
					_near(float(en["effective"]), 0.28, 0.005, "Стимпанк effective")


func _test_target() -> void:
	var c := Cases.new(SEED)
	_check(not c.set_target("cmd_bram"), "a common commander cannot be «Цель»")
	_check(c.set_target("cmd_irma"), "Ирма Сталь can be «Цель»")
	var irma := 0
	var epic_shards := 0
	for i in range(20000):
		var r := c.open("case_royal", {"income_per_hour": CTX["income_per_hour"], "dl": 3,
			"commanders_owned": ALL_OWNED}, T0 + i)
		for rv in (r["rewards"] as Array):
			var rw: Dictionary = rv
			if String(rw["kind"]) == "shards" and String(rw["rarity"]) == "epic":
				epic_shards += 1
				if String(rw["commander"]) == "cmd_irma":
					irma += 1
	var share := float(irma) / float(epic_shards)
	var expect := 0.5 + 0.5 / 3.0
	_near(share, expect, 4.0 * sqrt(expect * (1.0 - expect) / float(epic_shards)),
		"Irma share of epic shards (%d drops)" % epic_shards)
	# «i»: Irma per opening = 8,09% × (0,5 + 0,5/3) = 5,39% (§9.10.6).
	var rows := c.odds_items("case_royal", "epic")
	for iv in rows:
		var it: Dictionary = iv
		if String(it["id"]) == "shards_epic_10":
			for ev in (it["entries"] as Array):
				var en: Dictionary = ev
				if String(en["id"]) == "cmd_irma":
					_near(float(en["effective"]), 5.39, 0.01, "Irma per opening (effective)")
					_check(bool(en["target"]), "Irma marked as target")
	# Legendary shards: target of another rarity does not apply.
	for i in range(3000):
		var r2 := c.open("case_royal", CTX, T0 + i)
		for rv in (r2["rewards"] as Array):
			var rw2: Dictionary = rv
			if String(rw2["kind"]) == "shards" and String(rw2["rarity"]) == "legendary":
				_eq(String(rw2["commander"]), "cmd_rai", "legendary shards go to Император Рай")
				_check(not bool(rw2["target"]), "epic «Цель» does not steer legendary shards")
	# Gold trophy: «Цель» applies to its epic shards too.
	var g := Cases.new(SEED)
	g.set_target("cmd_vance")
	var vance := 0
	for i in range(3000):
		var rg := g.open("case_trophy_gold", CTX, T0 + i)
		for rv in (rg["rewards"] as Array):
			var rw3: Dictionary = rv
			if String(rw3["kind"]) == "shards" and String(rw3["rarity"]) == "epic" and String(rw3["commander"]) == "cmd_vance":
				vance += 1
	_near(float(vance) / 3000.0, expect, 0.04, "gold trophy: «Цель» share of epic shards")


func _test_collection() -> void:
	var prices: Array[int] = []
	var c := Cases.new(SEED)
	var seen := {}
	for k in range(8):
		prices.append(c.price("case_collection"))
		var rows := c.odds("case_collection")
		var leg := _row(rows, "legendary")
		if not c.collection_opened.has("cos_capital_skin_ice_citadel"):
			_near(float(leg["current"]), 100.0 / float(8 - k), 1e-9, "legendary chance 1/%d" % (8 - k))
		_eq(c.pity_text("case_collection"), "Осталось %d из 8" % (8 - k), "pity text before %d" % (k + 1))
		var r := c.open("case_collection", CTX, T0 + k)
		var id := String(r["item"])
		_check(not seen.has(id), "no duplicate in the collection (%s)" % id)
		seen[id] = true
		_eq(String((r["rewards"][0] as Dictionary)["kind"]), "cosmetic", "collection gives a cosmetic")
	_eq(seen.size(), 8, "8 openings complete the set")
	_eq(prices, [100, 150, 200, 250, 300, 400, 500, 600] as Array[int], "price ladder")
	var total := 0
	for p in prices:
		total += p
	_eq(total, 2500, "whole set 2 500")
	_eq(c.price("case_collection"), 0, "no price after the set is complete")
	_eq(String(c.open("case_collection", CTX, T0)["error"]), "complete", "9th opening refused")
	_eq(c.pity_text("case_collection"), "Набор собран", "complete text")
	_eq(c.glitter, 0, "collection never gives Блёстки")
	# Unconditional: the central legendary arrives on each k-th opening with 1/8.
	var at := [0, 0, 0, 0, 0, 0, 0, 0]
	var runs := 8000
	for s in range(runs):
		var d := Cases.new(SEED + 100 + s)
		for k in range(8):
			var r2 := d.open("case_collection", CTX, T0)
			if String(r2["item"]) == "cos_capital_skin_ice_citadel":
				at[k] = int(at[k]) + 1
	var sd := sqrt(0.125 * 0.875 / float(runs))
	for k in range(8):
		_near(float(at[k]) / float(runs), 0.125, 4.0 * sd, "central legendary on opening %d" % (k + 1))
	c.reset_collection(2)
	_eq(c.price("case_collection"), 100, "new season restarts the ladder")
	_eq(c.collection_season, 2, "season stored")


func _test_duplicates() -> void:
	var c := Cases.new(SEED)
	for id in (Cases.data()["pools"]["pool_crate"] as Array):
		c.owned_cosmetics[String(id)] = true
	c.pity["crate_cosmetic"] = 59
	var r := c.open("case_war_crate", CTX, T0)
	var rw: Dictionary = r["rewards"][0]
	_eq(String(rw["kind"]), "glitter", "owned crate cosmetic → Блёстки")
	_eq(int(rw["n"]), 20, "rare duplicate = 20")
	_eq(c.glitter, 20, "glitter balance")
	for id in (Cases.data()["pools"]["pool_royal_legendary"] as Array):
		c.owned_cosmetics[String(id)] = true
	var got := false
	for i in range(20000):
		var g0 := c.glitter
		var r2 := c.open("case_royal", CTX, T0 + i)
		var rw2: Dictionary = r2["rewards"][0]
		if String(r2["item"]) == "cosmetic_legendary":
			_eq(String(rw2["kind"]), "glitter", "owned legendary → Блёстки")
			_eq(int(rw2["n"]), 300, "legendary duplicate = 300")
			_eq(c.glitter - g0, 300, "glitter +300")
			got = true
			break
	_check(got, "a legendary cosmetic dropped")
	# A fresh cosmetic goes to owned_cosmetics; the same one later is a duplicate.
	var d := Cases.new(SEED)
	d.pity["crate_cosmetic"] = 59
	var r3 := d.open("case_war_crate", CTX, T0)
	var first: Dictionary = r3["rewards"][0]
	_eq(String(first["kind"]), "cosmetic", "first copy is a cosmetic")
	_check(d.owned_cosmetics.has(String(first["id"])), "owned after the drop")
	_check(not String(first["category"]).is_empty() and not String(first["name"]).is_empty(), "cosmetic has name / category")


func _test_rewards() -> void:
	var c := Cases.new(SEED)
	var seen := {}
	for i in range(4000):
		for id in ["case_war_crate", "case_trophy_bronze", "case_trophy_silver", "case_trophy_gold", "case_arena_chest"]:
			var r := c.open(id, CTX, T0)
			var rw: Dictionary = r["rewards"][0]
			if String(rw["kind"]) != "res":
				continue
			var mult := {"case_war_crate": 1, "case_trophy_bronze": 2, "case_trophy_silver": 3,
				"case_trophy_gold": 5, "case_arena_chest": 2}[id] as int
			var item := String(r["item"])
			var base_h := {"gold_2h": 2, "food_2h": 2, "metal_2h": 2, "gold_4h": 4, "food_4h": 4,
				"metal_4h": 4, "oil_4h": 4, "all_2h": 2, "gold_8h": 8, "metal_8h": 8}[item] as int
			_eq(int(rw["hours"]), base_h * mult, "%s %s hours" % [id, item])
			var res: Dictionary = rw["res"]
			var h := base_h * mult
			if item == "all_2h":
				_eq(res, {"gold": 100 * h, "food": 50 * h, "metal": 40 * h}, "all resources")
			elif item.begins_with("food"):
				_eq(res, {"gold": 0, "food": 50 * h, "metal": 0}, "food")
			elif item.begins_with("metal"):
				_eq(res, {"gold": 0, "food": 0, "metal": 40 * h}, "metal")
			else:
				_eq(res, {"gold": 100 * h, "food": 0, "metal": 0}, "gold (oil falls back to gold below DL5)")
			seen[item] = true
	_check(seen.has("oil_4h"), "oil cell seen")
	# Royal: 8 h of all resources, 3 h + 1 h bundle.
	var bundle_ok := false
	var res_ok := false
	for i in range(3000):
		var r2 := c.open("case_royal", CTX, T0)
		if String(r2["item"]) == "speedup_3h_1h":
			var rs: Array = r2["rewards"]
			_eq(rs.size(), 2, "bundle: two speed-ups")
			_eq(int((rs[0] as Dictionary)["minutes"]) + int((rs[1] as Dictionary)["minutes"]), 240, "3 h + 1 h")
			bundle_ok = true
		elif String(r2["item"]) == "res_all_8h":
			_eq((r2["rewards"][0] as Dictionary)["res"], {"gold": 800, "food": 400, "metal": 320}, "royal 8 h")
			res_ok = true
		elif String(r2["item"]) == "speedup_1h":
			_eq(int((r2["rewards"][0] as Dictionary)["minutes"]), 60, "royal speed-up 1 h")
	_check(bundle_ok and res_ok, "royal bundle and resources seen")
	# Speed-ups of the crate.
	var d := Cases.new(SEED)
	var mins := {}
	for i in range(3000):
		var r3 := d.open("case_war_crate", CTX, T0)
		if String(r3["rarity"]) == "rare":
			mins[String(r3["item"])] = int((r3["rewards"][0] as Dictionary)["minutes"])
	_eq(mins, {"speedup_15m_x2": 30, "speedup_1h": 60, "speedup_1h_x2": 120}, "crate speed-up minutes")
	# Oil at DL5+.
	var e := Cases.new(SEED)
	var ctx5 := {"income_per_hour": {"gold": 100, "food": 50, "metal": 40, "oil": 7}, "dl": 5}
	var oil_ok := false
	for i in range(4000):
		var r4 := e.open("case_war_crate", ctx5, T0)
		if String(r4["item"]) == "oil_4h":
			_eq(int(((r4["rewards"][0] as Dictionary)["res"] as Dictionary).get("oil", 0)), 28, "oil 4 h at DL5")
			oil_ok = true
			break
	_check(oil_ok, "oil cell at DL5 seen")
	_eq(c.odds_items("case_trophy_silver", "common")[0]["name_ru"], "Золото 6 ч", "×3 item name")


func _test_free_crates() -> void:
	var c := Cases.new(SEED)
	var h := 3600
	_eq(c.claim_free_crates(T0), 0, "timer starts at the first call")
	_eq(c.free_crate_left(T0), 6 * h, "6 h to the first crate")
	_eq(c.claim_free_crates(T0 + 6 * h - 1), 0, "not yet")
	_eq(c.free_crate_left(T0 + 6 * h - 1), 1, "1 s left")
	_eq(c.claim_free_crates(T0 + 6 * h), 1, "one after 6 h")
	_eq(c.free_crate_left(T0 + 6 * h), 6 * h, "next in 6 h")
	_eq(c.claim_free_crates(T0 + 40 * h), 2, "stores at most 2")
	_eq(c.free_crate_left(T0 + 40 * h), 0, "full: timer paused")
	_eq(c.claim_free_crates(T0 + 100 * h), 2, "still 2 much later")
	_check(c.use_free_crate(T0 + 100 * h), "use one")
	_eq(c.free_crates, 1, "1 left")
	_eq(c.free_crate_left(T0 + 100 * h), 6 * h, "timer restarts from the use")
	_check(c.use_free_crate(T0 + 101 * h), "use the second")
	_check(not c.use_free_crate(T0 + 101 * h), "none left")
	_eq(c.claim_free_crates(T0 + 106 * h), 1, "accrues on the restarted timer")
	_eq(c.claim_free_crates(T0 + 112 * h), 2, "second after another 6 h")
	# Fresh account, long absence: capped at 2.
	var d := Cases.new(SEED)
	d.claim_free_crates(T0)
	_eq(d.claim_free_crates(T0 + 1000 * h), 2, "cap after a long absence")


func _test_history() -> void:
	var c := Cases.new(SEED)
	for i in range(150):
		c.open("case_war_crate", CTX, T0 + i)
	_eq(c.history.size(), 100, "history capped at 100")
	_eq(int((c.history[0] as Dictionary)["t"]), T0 + 50, "oldest kept is #51")
	_eq(int((c.history[99] as Dictionary)["t"]), T0 + 149, "newest last")
	var h: Dictionary = c.history[99]
	for k in ["t", "case", "rarity", "rewards"]:
		_check(h.has(k), "history entry has %s" % k)
	_eq(int(c.opened["case_war_crate"]), 150, "opening count")


func _test_odds_items() -> void:
	var c := Cases.new(SEED)
	for id in ["case_war_crate", "case_royal", "case_trophy_gold", "case_arena_chest"]:
		var rows := c.odds_items(id, "")
		var b := 0.0
		var e := 0.0
		var cur := 0.0
		for rv in rows:
			var r: Dictionary = rv
			if r.has("bonus"):
				continue
			b += float(r["base"])
			e += float(r["effective"])
			cur += float(r["current"])
			if r.has("entries"):
				var es := 0.0
				for ev in (r["entries"] as Array):
					es += float((ev as Dictionary)["effective"])
				_near(es, float(r["effective"]), 1e-9, "%s %s: entries sum to the row" % [id, r["id"]])
		_near(b, 100.0, 1e-9, "%s: base Σ = 100" % id)
		_near(e, 100.0, 1e-9, "%s: effective Σ = 100" % id)
		_near(cur, 100.0, 1e-9, "%s: current Σ = 100" % id)
	# War crate shard pool: not yet unlocked commanders weigh ×2.
	var rows2 := c.odds_items("case_war_crate", "epic", {"commanders_owned": ["cmd_bram"]})
	var ent: Array = (rows2[0] as Dictionary)["entries"]
	_eq(ent.size(), 8, "crate shard pool: 4 common + 4 rare commanders")
	var bram := 0.0
	var lira := 0.0
	for ev in ent:
		var en: Dictionary = ev
		if String(en["id"]) == "cmd_bram":
			bram = float(en["base"])
		elif String(en["id"]) == "cmd_lira":
			lira = float(en["base"])
	_near(lira / bram, 2.0, 1e-9, "unopened commander weighs ×2")
	# Maxed commanders leave the pool; Rai maxed → legendary is cosmetics only.
	var rows3 := c.odds_items("case_royal", "legendary", {"commanders_maxed": ["cmd_rai"]})
	_eq(rows3.size(), 1, "Rai maxed: only the cosmetic row")
	_near(float((rows3[0] as Dictionary)["base"]), 1.5, 1e-9, "legendary cosmetic takes the whole 1,5%")
	var gold := c.odds_items("case_trophy_gold", "epic")
	var bonus := false
	for rv in gold:
		if (rv as Dictionary).has("bonus"):
			bonus = true
	_check(bonus, "gold trophy shows the 100% epic shards bonus")
	# Owned cosmetic shows its duplicate value.
	c.owned_cosmetics["cos_capital_skin_steampunk"] = true
	for rv in c.odds_items("case_royal", "legendary"):
		var r4: Dictionary = rv
		if r4.has("entries") and String(r4["id"]) == "cosmetic_legendary":
			for ev in (r4["entries"] as Array):
				var en2: Dictionary = ev
				if String(en2["id"]) == "cos_capital_skin_steampunk":
					_check(bool(en2["owned"]), "owned flag")
					_eq(int(en2["glitter"]), 300, "duplicate would give 300")


func _test_texts() -> void:
	var c := Cases.new(SEED)
	_eq(c.pity_text("case_royal"), "Эпическое+ через 10 · Легендарное через 50", "royal fresh")
	c.pity["royal_epic"] = 6
	c.pity["royal_leg"] = 27
	_eq(c.pity_text("case_royal"), "Эпическое+ через 4 · Легендарное через 23", "royal example from §9.10.8")
	c.pity["crate_cosmetic"] = 37
	_eq(c.pity_text("case_war_crate"), "Косметика — осталось открытий: 23", "crate example")
	_eq(c.pity_text("case_trophy_gold"), "Косметика — осталось открытий: 23", "trophy shares the counter")
	c.collection_opened = ["cos_emote_snowman", "cos_frame_ice", "cos_border_ink_ice"]
	_eq(c.pity_text("case_collection"), "Осталось 5 из 8", "collection example")
	_eq(c.price("case_collection"), 250, "collection 4th opening price")
	_eq(c.price("case_royal"), 160, "royal price")
	_eq(c.price_x10("case_royal"), 1440, "royal ×10 price")
	_eq(c.price("case_war_crate"), 0, "war crate is free")
	_eq(c.price("case_arena_chest"), 0, "arena chest is free")
	_eq(c.price("case_trophy_gold"), 0, "trophy chest is free")
	# Current odds follow the counters.
	var cur := _row(c.odds("case_royal"), "legendary")
	_near(float(cur["current"]), 1.5, 1e-9, "current legendary at n = 28")
	c.pity["royal_leg"] = 41
	_near(float(_row(c.odds("case_royal"), "legendary")["current"]), 19.5, 1e-9, "current legendary at n = 42")


func _test_roundtrip() -> void:
	var a := Cases.new(SEED)
	a.set_target("cmd_hawk")
	for i in range(120):
		a.open(["case_war_crate", "case_royal", "case_trophy_gold"][i % 3] as String, CTX, T0 + i)
	a.open("case_collection", CTX, T0)
	a.open("case_collection", CTX, T0)
	a.claim_free_crates(T0)
	a.claim_free_crates(T0 + 7 * 3600)
	var d := a.to_dict()
	var b := Cases.from_dict(d)
	_eq(JSON.stringify(b.to_dict()), JSON.stringify(d), "direct round trip")
	var parsed: Dictionary = JSON.parse_string(JSON.stringify(d))
	var c := Cases.from_dict(parsed)
	_eq(JSON.stringify(c.to_dict()), JSON.stringify(d), "JSON round trip")
	_eq(c.history, a.history, "history equal (ints restored)")
	_check(typeof((c.history[0] as Dictionary)["t"]) == TYPE_INT, "history t is int after JSON")
	_eq(c.target_commander, "cmd_hawk", "target restored")
	_eq(c.free_crates, a.free_crates, "free crates restored")
	_eq(c.next_free_crate, a.next_free_crate, "free crate timer restored")
	_eq(c.collection_opened, a.collection_opened, "collection restored")
	_eq(c.price("case_collection"), 200, "collection step restored")
	# The RNG continues identically after a load.
	var ra: Array = []
	var rc: Array = []
	for i in range(50):
		ra.append(a.open("case_royal", CTX, T0 + i))
		rc.append(c.open("case_royal", CTX, T0 + i))
	_eq(JSON.stringify(rc), JSON.stringify(ra), "same openings after load")


## Chi-square of observed rarity counts against expected counts.
func _chi2(obs: Dictionary, expected: Dictionary) -> Array:
	var chi := 0.0
	var df := -1
	for k in expected:
		var e := float(expected[k])
		if e <= 0.0:
			continue
		var o := float(obs.get(k, 0))
		chi += (o - e) * (o - e) / e
		df += 1
	return [chi, df]


## Runs `n` openings, checks rarity frequencies against odds() "effective" (stationary) and against the
## sum of odds() "current" per opening, and cell frequencies against odds_items() "effective".
func _stat_run(case_id: String, n: int, seed_value: int) -> void:
	var c := Cases.new(seed_value)
	var ctx := {"income_per_hour": CTX["income_per_hour"], "dl": 3, "commanders_owned": ALL_OWNED}
	var obs := {}
	var obs_items := {}
	var exp_cur := {}
	for r in Cases.RARITIES:
		obs[r] = 0
		exp_cur[r] = 0.0
	for i in range(n):
		var cp := c.current_probs(case_id)
		for r in Cases.RARITIES:
			exp_cur[r] = float(exp_cur[r]) + float(cp[r])
		var res := c.open(case_id, ctx, T0)
		var rr := String(res["rarity"])
		obs[rr] = int(obs[rr]) + 1
		var it := String(res["item"])
		obs_items[it] = int(obs_items.get(it, 0)) + 1
	# Rarities vs the «i» effective odds.
	var rows := c.odds(case_id)
	var exp_eff := {}
	for rv in rows:
		var row: Dictionary = rv
		exp_eff[String(row["rarity"])] = float(row["effective"]) / 100.0 * float(n)
	var x := _chi2(obs, exp_eff)
	_check(float(x[0]) < _chi2_crit(int(x[1])), "%s rarities vs effective: χ² = %.2f (df %d, crit %.2f)" %
		[case_id, x[0], x[1], _chi2_crit(int(x[1]))])
	var y := _chi2(obs, exp_cur)
	_check(float(y[0]) < _chi2_crit(int(y[1])), "%s rarities vs Σ current: χ² = %.2f (df %d)" % [case_id, y[0], y[1]])
	var parts: Array[String] = []
	for r in Cases.RARITIES:
		parts.append("%s %.3f%% (i: %.3f%%)" % [r, 100.0 * float(obs[r]) / float(n), float(exp_eff.get(r, 0.0)) / float(n) * 100.0])
	print("      %s, %d openings: %s; χ² %.2f" % [case_id, n, ", ".join(parts), x[0]])
	# Items (cells) vs odds_items effective.
	var items := c.odds_items(case_id, "", ctx)
	var exp_items := {}
	for iv in items:
		var it2: Dictionary = iv
		if it2.has("bonus"):
			continue
		exp_items[String(it2["id"])] = float(it2["effective"]) / 100.0 * float(n)
	var z := _chi2(obs_items, exp_items)
	_check(float(z[0]) < _chi2_crit(int(z[1])), "%s items vs effective: χ² = %.2f (df %d, crit %.2f)" %
		[case_id, z[0], z[1], _chi2_crit(int(z[1]))])


func _test_stat_royal() -> void:
	_stat_run("case_royal", STAT_ROYAL, SEED + 1000)


func _test_stat_crate() -> void:
	_stat_run("case_war_crate", STAT_CRATE, SEED + 2000)
	_stat_run("case_arena_chest", STAT_ARENA, SEED + 3000)


func _test_english() -> void:
	TranslationServer.set_locale("en")
	var c := Cases.new(SEED)
	_eq(Cases.case_name("case_royal"), "Royal Case", "case name")
	_eq(Cases.commander_name("cmd_vance"), "Lady Vance", "commander name")
	_eq(Cases.rarity_name("epic"), "Epic", "rarity name")
	_eq(Cases.cosmetic_name("cos_capital_skin_steampunk"), "Steampunk", "cosmetic name")
	_eq(Cases.category_name("cos_border_ink"), "Border Ink", "category name")
	_eq(c.pity_text("case_royal"), "Epic+ in 10 · Legendary in 50", "royal pity text")
	_eq(c.pity_text("case_collection"), "8 of 8 left", "collection pity text")
	var row: Dictionary = c.odds_items("case_trophy_silver", "common")[0]
	_eq(String(row["name"]), "Gold 6 h", "×3 item name in English")
	_eq(String(row["name_ru"]), "Золото 6 ч", "name_ru stays Russian")
	_eq(String(c.odds("case_royal")[0]["name"]), "Common", "odds row name")
	var r := c.open("case_royal", CTX, T0)
	_check(not String(r["name"]).is_empty() and String(r["name"]) != String(r["name_ru"]), "open() returns the English item name")
	for rw in r["rewards"]:
		if String(rw.get("kind", "")) == "shards":
			_check(not Cases.data()["commanders"][String(rw["commander"])]["name"] == String(rw["name"]), "shard reward names the commander in English")
	TranslationServer.set_locale("ru")
