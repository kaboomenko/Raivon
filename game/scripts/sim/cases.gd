extends RefCounted
## Deterministic cases / lootboxes of one account (canon 00_canon.md §15.4, §15.5, §15.8; details from
## 09_monetization.md §9.10.2–9.10.11 — canon wins on conflict).
##
## Owner decision (решения 7, 13): cases, including paid opening, work identically in ALL countries.
## Odds disclosure («i»), pity counters and the 100-opening history are ADDITIONS, never restrictions.
## There is no geo / age switch here and there must never be one.
##
## Single source of odds: res://data/cases.json (the docs' `cases.yaml`). The RNG draw and the «i» screen
## use the same function (_probs_at), as §9.10.11 requires.
##
## The module never spends currency: the caller checks price() / free crates and pays, then calls open().
## Time is integer unix seconds passed in by the caller; the clock is never read here.
##
## ctx for open(): {"income_per_hour": {"gold": int, "food": int, "metal": int[, "oil": int]}, "dl": int,
##   optional "commanders_owned": Array[String] (unlocked commanders; default — derived from `shards`
##   reaching the unlock cost 10/20/40/80, canon §8.4), optional "commanders_maxed": Array[String]
##   (commanders with shards for level 20 — removed from random pools, canon §8.4)}.
##
## Reward dicts (open()["rewards"]):
##   {kind:"res", res:{gold,food,metal[,oil]}, hours, item, name}  — hours × income_per_hour (×res_mult)
##   {kind:"speedup", minutes, item, n}                            — minutes = total of n items
##   {kind:"shards", commander, name, rarity, n, target}           — commander = cmd_* id
##   {kind:"cosmetic", id, name, rarity, category, category_ru}
##   {kind:"glitter", n, duplicate:true, id, name, rarity, category} — duplicate cosmetic → Блёстки

const Rng := preload("res://scripts/sim/rng.gd")
const _Self := preload("res://scripts/sim/cases.gd")

const DATA_PATH := "res://data/cases.json"
const RARITIES: Array[String] = ["common", "rare", "epic", "legendary"]
const HISTORY_MAX := 100                      # canon §15.4: history of the last 100 openings
const U32 := 4294967296.0
const DEFAULT_TARGET_SHARE := 0.5             # canon §15.4 «Цель»: 50%

static var _data: Dictionary = {}
static var _eff_cache: Dictionary = {}
static var _probs_cache: Dictionary = {}
static var _cmd_sorted: Array[String] = []
static var _counter_cache: Dictionary = {}
static var _cand_cache: Dictionary = {}

var rng: Rng
## counter name -> openings since the last hit ("crate_cosmetic", "royal_epic", "royal_leg").
var pity: Dictionary = {}
## Last 100 openings, oldest first: {t, case, rarity, item, rewards}.
var history: Array = []
## cos_* id -> true.
var owned_cosmetics: Dictionary = {}
## cmd_* id -> shards received from cases.
var shards: Dictionary = {}
## Блёстки (cur_glitter) from duplicate cosmetics.
var glitter: int = 0
## «Цель» of the Royal case (cmd_* id of an epic or legendary commander; "" = none).
var target_commander: String = ""
var free_crates: int = 0
## Unix time of the next free crate; 0 = timer not running (not started yet, or storage full).
var next_free_crate: int = 0
## Collection-case items already received this season (cos_* ids, in order).
var collection_opened: Array = []
var collection_season: int = 0
## case id -> number of openings (all time).
var opened: Dictionary = {}


func _init(seed_value: int) -> void:
	rng = Rng.new(seed_value)
	collection_season = int(_case("case_collection").get("season", 0))


# ---------------------------------------------------------------- data

static func data() -> Dictionary:
	if _data.is_empty():
		var txt := FileAccess.get_file_as_string(DATA_PATH)
		var parsed: Variant = JSON.parse_string(txt)
		if parsed is Dictionary:
			_data = parsed
		else:
			push_error("cases.json: cannot parse %s" % DATA_PATH)
	return _data


static func case_ids() -> Array[String]:
	var out: Array[String] = []
	var cs: Dictionary = data().get("cases", {})
	for k in cs:
		out.append(String(k))
	return out


static func _case(case_id: String) -> Dictionary:
	var cs: Dictionary = data().get("cases", {})
	return cs.get(case_id, {})


## The case whose tier table is rolled (trophy / arena chests roll the war crate table, §9.10.3).
static func _table_case(case_id: String) -> Dictionary:
	var c := _case(case_id)
	if c.has("roll"):
		return _case(String(c["roll"]))
	return c


static func _tiers(case_id: String) -> Dictionary:
	return _table_case(case_id).get("tiers", {})


static func _is_collection(case_id: String) -> bool:
	return bool(_case(case_id).get("collection", false))


static func case_name(case_id: String) -> String:
	return String(_case(case_id).get("name_ru", case_id))


static func rarity_name(rarity: String) -> String:
	var rs: Array = data().get("rarities", [])
	for rv in rs:
		var r: Dictionary = rv
		if String(r["id"]) == rarity:
			return String(r["name_ru"])
	return rarity


static func cosmetic(id: String) -> Dictionary:
	var cos: Dictionary = data().get("cosmetics", {})
	return cos.get(id, {})


static func commander(id: String) -> Dictionary:
	var cmds: Dictionary = data().get("commanders", {})
	return cmds.get(id, {})


static func dup_glitter(rarity: String) -> int:
	var d: Dictionary = data().get("duplicates", {})
	return int(d.get(rarity, 0))


# ---------------------------------------------------------------- probabilities

## Rarity probabilities (fractions) for one opening given the pity counters (counter values = openings
## since the last hit, before this opening). The same function drives the RNG, odds() and the
## stationary «effective» odds (§9.10.5, §9.10.11).
static func _probs_at(case_id: String, leg_c: int, epic_c: int) -> Dictionary:
	return _probs_cached(case_id, leg_c, epic_c).duplicate()


## Cached _probs_at (read-only result).
static func _probs_cached(case_id: String, leg_c: int, epic_c: int) -> Dictionary:
	var key := "%s|%d|%d" % [case_id, leg_c, epic_c]
	var hit: Variant = _probs_cache.get(key)
	if hit != null:
		return hit
	var p := _probs_compute(case_id, leg_c, epic_c)
	_probs_cache[key] = p
	return p


static func _probs_compute(case_id: String, leg_c: int, epic_c: int) -> Dictionary:
	var tiers := _tiers(case_id)
	var p := {}
	for r in RARITIES:
		var t: Dictionary = tiers.get(r, {})
		p[r] = float(t.get("p", 0.0))
	var pity_d: Dictionary = _case(case_id).get("pity", {})
	if pity_d.has("legendary"):
		var lg: Dictionary = pity_d["legendary"]
		var n := leg_c + 1
		var base_leg: float = p["legendary"]
		var pl := base_leg
		if lg.has("soft_from") and n >= int(lg["soft_from"]):
			pl = base_leg + float(lg["soft_step"]) * float(n - int(lg["soft_from"]) + 1)
		if lg.has("hard_at") and n >= int(lg["hard_at"]):
			pl = 1.0
		pl = minf(pl, 1.0)
		if pl != base_leg:
			p = _redistribute(p, pl, lg)
	if pity_d.has("epic_plus"):
		var ep: Dictionary = pity_d["epic_plus"]
		var pl2: float = p["legendary"]
		if epic_c + 1 >= int(ep["every"]) and pl2 < 1.0:
			# Forced epic+: legendary in proportion p_leg(n) : p_epic (canon §15.4: 1,5 : 8,5 outside soft pity).
			var pe: float = p["epic"]
			var s := pl2 + pe
			p = {"common": 0.0, "rare": 0.0, "epic": pe / s, "legendary": pl2 / s}
	return p


## Legendary raised to `pl`: "hold" rarities keep their base chance, "share" rarities split the rest in
## their base proportion (royal: epic holds 8,5%, common : rare = 62 : 28, §9.10.5). Without "hold"/"share"
## every other rarity shrinks proportionally.
static func _redistribute(p: Dictionary, pl: float, lg: Dictionary) -> Dictionary:
	var hold: Array = lg.get("hold", [])
	var share: Array = lg.get("share", [])
	if share.is_empty():
		for r in RARITIES:
			if r != "legendary" and not hold.has(r):
				share.append(r)
	var rest := 1.0 - pl
	var out := {"legendary": pl}
	var held := 0.0
	for r in hold:
		held += float(p[r])
	var hold_k := 1.0
	if held > rest:
		hold_k = rest / held if held > 0.0 else 0.0
	var share_left := maxf(0.0, rest - held * hold_k)
	var share_base := 0.0
	for r in share:
		share_base += float(p[r])
	for r in RARITIES:
		if r == "legendary":
			continue
		if hold.has(r):
			out[r] = float(p[r]) * hold_k
		elif share.has(r) and share_base > 0.0:
			out[r] = share_left * float(p[r]) / share_base
		else:
			out[r] = 0.0
	return out


static func _base_probs(case_id: String) -> Dictionary:
	var tiers := _tiers(case_id)
	var p := {}
	for r in RARITIES:
		var t: Dictionary = tiers.get(r, {})
		p[r] = float(t.get("p", 0.0))
	return p


## Long-run («эффективные», §9.10.2 / §9.10.5) rarity probabilities with pity, as fractions.
## Renewal-reward over the legendary counter: every legendary resets both counters, so the expected
## rarity counts of one cycle divided by its expected length give the exact stationary rates
## (war crate: legendary 1/51,95 = 1,925%; royal: 3,53% / 12,51% / 26,12% / 57,84%).
static func effective_probs(case_id: String) -> Dictionary:
	if _eff_cache.has(case_id):
		return (_eff_cache[case_id] as Dictionary).duplicate()
	var pity_d: Dictionary = _case(case_id).get("pity", {})
	var out := _base_probs(case_id)
	if pity_d.has("legendary") and (pity_d["legendary"] as Dictionary).has("hard_at"):
		var lg: Dictionary = pity_d["legendary"]
		var hard := int(lg["hard_at"])
		var every := 1
		if pity_d.has("epic_plus"):
			every = int((pity_d["epic_plus"] as Dictionary)["every"])
		var mass: Array[float] = []
		mass.resize(every)
		mass.fill(0.0)
		mass[0] = 1.0
		var counts := {"common": 0.0, "rare": 0.0, "epic": 0.0, "legendary": 0.0}
		var length := 0.0
		for leg_c in range(hard):
			var nxt: Array[float] = []
			nxt.resize(every)
			nxt.fill(0.0)
			for ec in range(every):
				var m := mass[ec]
				if m <= 0.0:
					continue
				length += m
				var pr := _probs_cached(case_id, leg_c, ec)
				for r in RARITIES:
					counts[r] = float(counts[r]) + m * float(pr[r])
				if every > 1:
					nxt[0] += m * float(pr["epic"])
					nxt[mini(ec + 1, every - 1)] += m * (float(pr["common"]) + float(pr["rare"]))
				else:
					nxt[0] += m * (1.0 - float(pr["legendary"]))
			mass = nxt
		for r in RARITIES:
			out[r] = float(counts[r]) / length
	_eff_cache[case_id] = out
	return out.duplicate()


## This opening's rarity probabilities (fractions) with the player's current pity counters.
func current_probs(case_id: String) -> Dictionary:
	return _current(case_id).duplicate()


func _current(case_id: String) -> Dictionary:
	if _is_collection(case_id):
		return _collection_probs(case_id, collection_opened)
	var lc := _counter_name(case_id, "legendary")
	var ec := _counter_name(case_id, "epic_plus")
	return _probs_cached(case_id, int(pity.get(lc, 0)) if lc != "" else 0, int(pity.get(ec, 0)) if ec != "" else 0)


static func _counter_name(case_id: String, kind: String) -> String:
	var key := case_id + "|" + kind
	var hit: Variant = _counter_cache.get(key)
	if hit != null:
		return hit
	var pity_d: Dictionary = _case(case_id).get("pity", {})
	var name := ""
	if pity_d.has(kind):
		name = String((pity_d[kind] as Dictionary).get("counter", case_id + "_" + kind))
	_counter_cache[key] = name
	return name


static func _collection_probs(case_id: String, opened_ids: Array) -> Dictionary:
	var p := {"common": 0.0, "rare": 0.0, "epic": 0.0, "legendary": 0.0}
	var left := _collection_left(case_id, opened_ids)
	if left.is_empty():
		return p
	for id in left:
		var r := String(cosmetic(String(id)).get("rarity", "rare"))
		p[r] = float(p[r]) + 1.0 / float(left.size())
	return p


static func _collection_left(case_id: String, opened_ids: Array) -> Array:
	var left: Array = []
	var set_ids: Array = _case(case_id).get("set", [])
	for id in set_ids:
		if not opened_ids.has(String(id)):
			left.append(String(id))
	return left


# ---------------------------------------------------------------- «i» screen

## Rarity rows for the «i» screen: base and effective (long-run, with pity, §9.10.2 / §9.10.5) and
## current (this opening with the player's counters). Percent.
func odds(case_id: String) -> Array:
	var out: Array = []
	if _case(case_id).is_empty():
		return out
	var base: Dictionary
	var eff: Dictionary
	var cur := current_probs(case_id)
	if _is_collection(case_id):
		base = _collection_probs(case_id, [])
		eff = cur
	else:
		base = _base_probs(case_id)
		eff = effective_probs(case_id)
	for r in RARITIES:
		if float(base[r]) <= 0.0 and float(cur[r]) <= 0.0:
			continue
		out.append({
			"rarity": r, "name_ru": rarity_name(r), "base": 100.0 * float(base[r]),
			"effective": 100.0 * float(eff[r]), "current": 100.0 * float(cur[r]),
		})
	return out


## Item rows of one rarity ("" = all) for the «i» screen, percent of one opening. Pools are expanded in
## "entries" (cosmetics with owned / duplicate Блёстки; commanders with «Цель»). Rows flagged "bonus" are
## guaranteed extras outside the roll (Золотой трофейный сундук: 5 эпических осколков, 100%).
func odds_items(case_id: String, rarity: String, ctx: Dictionary = {}) -> Array:
	var out: Array = []
	if _case(case_id).is_empty():
		return out
	if _is_collection(case_id):
		var left := _collection_left(case_id, collection_opened)
		var set_ids: Array = _case(case_id).get("set", [])
		for idv in set_ids:
			var id := String(idv)
			var c := cosmetic(id)
			if rarity != "" and String(c.get("rarity", "")) != rarity:
				continue
			var cur := 100.0 / float(left.size()) if left.has(id) else 0.0
			out.append({
				"id": id, "name_ru": String(c.get("name", id)), "rarity": String(c.get("rarity", "")),
				"category": String(c.get("category", "")), "base": 100.0 / float(set_ids.size()),
				"effective": cur, "current": cur, "owned": collection_opened.has(id),
				"central": id == String(_case(case_id).get("central", "")),
			})
		return out
	var base := _base_probs(case_id)
	var eff := effective_probs(case_id)
	var cur_p := current_probs(case_id)
	var tiers := _tiers(case_id)
	var mult := int(_case(case_id).get("res_mult", 1))
	for r in RARITIES:
		if rarity != "" and r != rarity:
			continue
		var t: Dictionary = tiers.get(r, {})
		var elig := _eligible(case_id, t.get("items", []), ctx)
		var wsum := 0.0
		for e in elig:
			wsum += float((e as Array)[1])
		for e in elig:
			var item: Dictionary = (e as Array)[0]
			var k := float((e as Array)[1]) / wsum
			var row := {
				"id": String(item.get("id", "")), "name_ru": _item_name(item, mult), "rarity": r,
				"base": 100.0 * float(base[r]) * k, "effective": 100.0 * float(eff[r]) * k,
				"current": 100.0 * float(cur_p[r]) * k,
			}
			var ent := _entry_shares(case_id, item, ctx)
			if not ent.is_empty():
				var rows: Array = []
				for sv in ent:
					var s: Dictionary = sv
					var sh := float(s["share"])
					s.erase("share")
					s["base"] = float(row["base"]) * sh
					s["effective"] = float(row["effective"]) * sh
					s["current"] = float(row["current"]) * sh
					rows.append(s)
				row["entries"] = rows
			out.append(row)
	if rarity == "" or rarity == "epic":
		var extra: Array = _case(case_id).get("extra", [])
		for xv in extra:
			var x: Dictionary = xv
			var row := {
				"id": String(x.get("id", "")), "name_ru": String(x.get("name_ru", "")), "rarity": "epic",
				"base": 100.0, "effective": 100.0, "current": 100.0, "bonus": true,
			}
			var ent := _entry_shares(case_id, x, ctx)
			for sv in ent:
				var s: Dictionary = sv
				var sh := float(s["share"])
				s.erase("share")
				s["base"] = 100.0 * sh
				s["effective"] = 100.0 * sh
				s["current"] = 100.0 * sh
			row["entries"] = ent
			out.append(row)
	return out


## Share of each pool entry inside one item (sums to 1): cosmetics uniform; commanders by weight with
## «Цель» taking 50% when it applies.
func _entry_shares(case_id: String, item: Dictionary, ctx: Dictionary) -> Array:
	var out: Array = []
	if item.has("cosmetic_pool"):
		var pool := _pool(String(item["cosmetic_pool"]))
		for idv in pool:
			var id := String(idv)
			var c := cosmetic(id)
			var r := String(c.get("rarity", "rare"))
			var own := owned_cosmetics.has(id)
			out.append({
				"id": id, "name_ru": String(c.get("name", id)), "rarity": r,
				"category": String(c.get("category", "")), "owned": own,
				"glitter": dup_glitter(r) if own else 0, "share": 1.0 / float(pool.size()),
			})
	elif item.has("shards"):
		var ents := _shard_entries(case_id, item, ctx)
		var wsum := 0.0
		for e in ents:
			wsum += float((e as Array)[1])
		var tgt := _target_for(item, ents)
		var ts := _target_share()
		for e in ents:
			var cmd := String((e as Array)[0])
			var sh := float((e as Array)[1]) / wsum
			if tgt != "":
				sh = (1.0 - ts) * sh + (ts if cmd == tgt else 0.0)
			out.append({
				"id": cmd, "name_ru": String(commander(cmd).get("name", cmd)),
				"rarity": String(commander(cmd).get("rarity", "")), "target": cmd == tgt, "share": sh,
			})
	return out


# ---------------------------------------------------------------- pity / prices / timer

## Pity line for the case screen (§9.10.8): «Эпическое+ через 4 · Легендарное через 23» (Королевский),
## «Косметика не позже чем через 23» (ящик и трофейные), «Осталось 5 из 8» (коллекция); "" — no pity.
func pity_text(case_id: String) -> String:
	var c := _case(case_id)
	match String(c.get("pity_text", "none")):
		"royal":
			var pd: Dictionary = c.get("pity", {})
			var ep: Dictionary = pd.get("epic_plus", {})
			var lg: Dictionary = pd.get("legendary", {})
			var e_left := int(ep.get("every", 10)) - int(pity.get(_counter_name(case_id, "epic_plus"), 0))
			var l_left := int(lg.get("hard_at", 50)) - int(pity.get(_counter_name(case_id, "legendary"), 0))
			return "Эпическое+ через %d · Легендарное через %d" % [e_left, l_left]
		"cosmetic":
			var lg2: Dictionary = (c.get("pity", {}) as Dictionary).get("legendary", {})
			var left := int(lg2.get("hard_at", 60)) - int(pity.get(_counter_name(case_id, "legendary"), 0))
			return "Косметика не позже чем через %d" % left
		"collection":
			var total: int = (c.get("set", []) as Array).size()
			var rest := total - collection_opened.size()
			if rest <= 0:
				return "Набор собран"
			return "Осталось %d из %d" % [rest, total]
	return ""


## Price in Райвиты (0 = free / not purchasable). Collection: price of the next opening, 0 when complete.
func price(case_id: String) -> int:
	var c := _case(case_id)
	if _is_collection(case_id):
		var prices: Array = c.get("prices", [])
		var i := collection_opened.size()
		return int(prices[i]) if i < prices.size() else 0
	return int(c.get("price", 0))


## ×10 price in Райвиты (Королевский: 1 440, canon §15.4); 0 = no ×10 offer.
func price_x10(case_id: String) -> int:
	return int(_case(case_id).get("price_x10", 0))


## Free war crate: +1 every 6 h, stored up to 2 (canon §15.4). The timer is paused while storage is full
## and restarts when a crate is used. The first call starts the timer. Returns the current count.
func claim_free_crates(now: int) -> int:
	var fc: Dictionary = data().get("free_crate", {})
	var every := int(fc.get("every_sec", 21600))
	var cap := int(fc.get("cap", 2))
	if free_crates >= cap:
		next_free_crate = 0
		return free_crates
	if next_free_crate <= 0:
		next_free_crate = now + every
		return free_crates
	while free_crates < cap and now >= next_free_crate:
		free_crates += 1
		next_free_crate += every
	if free_crates >= cap:
		next_free_crate = 0
	return free_crates


## Seconds until the next free crate; 0 when storage is full (timer paused) or one is due now.
func free_crate_left(now: int) -> int:
	var fc: Dictionary = data().get("free_crate", {})
	var every := int(fc.get("every_sec", 21600))
	var cap := int(fc.get("cap", 2))
	if free_crates >= cap:
		return 0
	if next_free_crate <= 0:
		return every
	var n := free_crates
	var nx := next_free_crate
	while n < cap and now >= nx:
		n += 1
		nx += every
	if n >= cap:
		return 0
	return nx - now


## Takes one stored free crate (the caller then opens case_war_crate). False if none is stored.
func use_free_crate(now: int) -> bool:
	claim_free_crates(now)
	if free_crates <= 0:
		return false
	var fc: Dictionary = data().get("free_crate", {})
	if free_crates >= int(fc.get("cap", 2)):
		next_free_crate = now + int(fc.get("every_sec", 21600))
	free_crates -= 1
	return true


# ---------------------------------------------------------------- «Цель»

## Commanders that can be chosen as «Цель» (epic and legendary, canon §15.4; minus maxed ones).
static func target_options(ctx: Dictionary = {}) -> Array[String]:
	var out: Array[String] = []
	var maxed: Array = ctx.get("commanders_maxed", [])
	var royal := _case("case_royal")
	var rs: Array = (royal.get("target", {}) as Dictionary).get("rarities", ["epic", "legendary"])
	for id in _sorted_commanders():
		if rs.has(String(commander(id).get("rarity", ""))) and not maxed.has(id):
			out.append(id)
	return out


## Sets «Цель» (free, any time, from the next opening; counters are not reset). "" clears it.
func set_target(cmd_id: String) -> bool:
	if cmd_id != "" and not target_options().has(cmd_id):
		return false
	target_commander = cmd_id
	return true


static func _target_share() -> float:
	var t: Dictionary = _case("case_royal").get("target", {})
	return float(t.get("share", DEFAULT_TARGET_SHARE))


# ---------------------------------------------------------------- opening

## Opens one case. Returns {case, rarity, item, name_ru, rewards: Array[Dictionary], forced: bool}
## ({"rarity": "", "rewards": [], "error": ...} for an unknown case or a completed collection).
## Does NOT spend currency.
func open(case_id: String, ctx: Dictionary, now: int) -> Dictionary:
	var c := _case(case_id)
	if c.is_empty():
		return {"case": case_id, "rarity": "", "rewards": [], "error": "unknown_case"}
	if _is_collection(case_id):
		return _open_collection(case_id, now)
	var probs := _current(case_id)
	var forced := float(probs["common"]) + float(probs["rare"]) <= 0.0
	var rarity := _pick_rarity(probs)
	var tier: Dictionary = _tiers(case_id).get(rarity, {})
	var elig := _eligible(case_id, tier.get("items", []), ctx)
	var rewards: Array = []
	var item_id := ""
	var item_name := ""
	if elig.is_empty():
		# Every item of this rarity is exhausted (e.g. all pool commanders maxed). DEFAULT (invented):
		# Блёстки at the duplicate rate of that rarity.
		var g := maxi(dup_glitter(rarity), 20)
		glitter += g
		rewards.append({"kind": "glitter", "n": g, "duplicate": false})
	else:
		var item := _pick_weighted(elig)
		item_id = String(item.get("id", ""))
		item_name = _item_name(item, int(c.get("res_mult", 1)))
		_grant(case_id, item, ctx, rewards)
	var extra: Array = c.get("extra", [])
	for xv in extra:
		_grant(case_id, xv as Dictionary, ctx, rewards)
	_advance_pity(case_id, rarity)
	opened[case_id] = int(opened.get(case_id, 0)) + 1
	_log(now, case_id, rarity, item_id, rewards)
	return {"case": case_id, "rarity": rarity, "item": item_id, "name_ru": item_name, "rewards": rewards,
		"forced": forced}


## Ten openings in a row (Королевский ×10 for 1 440; its epic+ guarantee follows from the every-10
## counter, §9.10.5). Collection: at most the items left.
func open_x10(case_id: String, ctx: Dictionary, now: int) -> Array:
	var out: Array = []
	for i in range(10):
		if _is_collection(case_id) and _collection_left(case_id, collection_opened).is_empty():
			break
		out.append(open(case_id, ctx, now))
	return out


func _open_collection(case_id: String, now: int) -> Dictionary:
	var left := _collection_left(case_id, collection_opened)
	if left.is_empty():
		return {"case": case_id, "rarity": "", "rewards": [], "error": "complete"}
	var id := String(left[rng.next_int(left.size())])
	collection_opened.append(id)
	var rewards: Array = []
	_grant_cosmetic(id, rewards)
	var rarity := String(cosmetic(id).get("rarity", "rare"))
	opened[case_id] = int(opened.get(case_id, 0)) + 1
	_log(now, case_id, rarity, id, rewards)
	return {"case": case_id, "rarity": rarity, "item": id, "name_ru": String(cosmetic(id).get("name", id)),
		"rewards": rewards, "forced": left.size() == 1}


## New season of the collection case: clears the per-season progress (owned items stay owned).
func reset_collection(season: int) -> void:
	collection_opened.clear()
	collection_season = season


func _advance_pity(case_id: String, rarity: String) -> void:
	var lc := _counter_name(case_id, "legendary")
	if lc != "":
		pity[lc] = 0 if rarity == "legendary" else int(pity.get(lc, 0)) + 1
	var ec := _counter_name(case_id, "epic_plus")
	if ec != "":
		pity[ec] = 0 if (rarity == "epic" or rarity == "legendary") else int(pity.get(ec, 0)) + 1


func _log(now: int, case_id: String, rarity: String, item_id: String, rewards: Array) -> void:
	history.append({"t": now, "case": case_id, "rarity": rarity, "item": item_id,
		"rewards": rewards.duplicate(true)})
	while history.size() > HISTORY_MAX:
		history.pop_front()


func _rand() -> float:
	return float(rng.next_u32()) / U32


func _pick_rarity(probs: Dictionary) -> String:
	var u := _rand()
	var acc := 0.0
	var last := ""
	for r in RARITIES:
		var p := float(probs[r])
		if p <= 0.0:
			continue
		acc += p
		last = r
		if u < acc:
			return r
	return last


## [[item, weight], ...] -> item.
func _pick_weighted(entries: Array) -> Dictionary:
	var total := 0.0
	for e in entries:
		total += float((e as Array)[1])
	var u := _rand() * total
	var acc := 0.0
	for e in entries:
		acc += float((e as Array)[1])
		if u < acc:
			return (e as Array)[0]
	return (entries[entries.size() - 1] as Array)[0]


## Items of a tier that can be granted now (a shards item with an empty pool drops out; the others
## keep their relative weights — «шансы в «i» пересчитываются», canon §8.4).
func _eligible(case_id: String, items: Array, ctx: Dictionary) -> Array:
	var out: Array = []
	for iv in items:
		var item: Dictionary = iv
		if item.has("shards") and _shard_entries(case_id, item, ctx).is_empty():
			continue
		out.append([item, float(item.get("w", 1.0))])
	return out


static func _pool(pool_id: String) -> Array:
	var pools: Dictionary = data().get("pools", {})
	return pools.get(pool_id, [])


static func _sorted_commanders() -> Array[String]:
	if _cmd_sorted.is_empty():
		var cmds: Dictionary = data().get("commanders", {})
		for k in cmds:
			_cmd_sorted.append(String(k))
		_cmd_sorted.sort()
	return _cmd_sorted


func _is_owned_cmd(cmd: String, ctx: Dictionary) -> bool:
	if ctx.has("commanders_owned"):
		return (ctx["commanders_owned"] as Array).has(cmd)
	var unlock: Dictionary = data().get("commander_unlock_shards", {})
	var need := int(unlock.get(String(commander(cmd).get("rarity", "common")), 10))
	return int(shards.get(cmd, 0)) >= need


## [[cmd_id, weight], ...] for a shards item. An item without "rarity" uses the case's shard_pool
## (war crate: common + rare, not yet unlocked ×2, §9.10.2); otherwise the pool of that rarity, equal
## weights (Королевский, §9.10.4). Maxed commanders are excluded (canon §8.4).
func _shard_entries(case_id: String, item: Dictionary, ctx: Dictionary) -> Array:
	var rarity := String(item.get("rarity", ""))
	var cands := _shard_candidates(case_id, rarity)
	var unopened_w := 1.0
	if rarity == "":
		var sp: Dictionary = _table_case(case_id).get("shard_pool", {})
		unopened_w = float(sp.get("unopened_weight", 1))
	var maxed: Array = ctx.get("commanders_maxed", [])
	var out: Array = []
	for cmd in cands:
		if maxed.has(cmd):
			continue
		out.append([cmd, 1.0 if unopened_w == 1.0 or _is_owned_cmd(cmd, ctx) else unopened_w])
	return out


## Commanders (sorted ids) of a shard pool before exclusions; rarity "" = the case's shard_pool rarities.
static func _shard_candidates(case_id: String, rarity: String) -> Array:
	var key := case_id + "|" + rarity
	var hit: Variant = _cand_cache.get(key)
	if hit != null:
		return hit
	var rarities: Array = [rarity]
	if rarity == "":
		var sp: Dictionary = _table_case(case_id).get("shard_pool", {})
		rarities = sp.get("rarities", ["common", "rare"])
	var out: Array = []
	for cmd in _sorted_commanders():
		if rarities.has(String(commander(cmd).get("rarity", ""))):
			out.append(cmd)
	_cand_cache[key] = out
	return out


## «Цель» for this shards item, or "" when it does not apply (canon §15.4: only items marked target,
## only a commander of the same rarity that is still in the pool).
func _target_for(item: Dictionary, entries: Array) -> String:
	if target_commander == "" or not bool(item.get("target", false)):
		return ""
	for e in entries:
		if String((e as Array)[0]) == target_commander:
			return target_commander
	return ""


func _item_name(item: Dictionary, mult: int) -> String:
	if mult == 1 or not item.has("resources_h"):
		return String(item.get("name_ru", item.get("id", "")))
	var names: Dictionary = data().get("res_names", {})
	var h := int(item["resources_h"]) * mult
	var key := String(item.get("res", "all")).trim_prefix("res_")
	if key == "all":
		return "Ресурсы %d ч (все)" % h
	var s := "%s %d ч" % [String(names.get(key, key)), h]
	if item.has("fallback"):
		var fb: Dictionary = item["fallback"]
		var fk := String(fb.get("res", "res_gold")).trim_prefix("res_")
		s += " (до УР%d — %s %d ч)" % [int(fb.get("below_dev_level", 5)), String(names.get(fk, fk)), h]
	return s


func _grant(case_id: String, item: Dictionary, ctx: Dictionary, rewards: Array) -> void:
	if item.has("bundle"):
		var parts: Array = item["bundle"]
		for pv in parts:
			_grant(case_id, pv as Dictionary, ctx, rewards)
	elif item.has("resources_h"):
		_grant_res(case_id, item, ctx, rewards)
	elif item.has("speedup"):
		var sp: Dictionary = data().get("speedups", {})
		var code := String(item["speedup"])
		var n := int(item.get("n", 1))
		rewards.append({"kind": "speedup", "minutes": int(sp.get(code, 0)) * n, "item": code, "n": n})
	elif item.has("shards"):
		var ents := _shard_entries(case_id, item, ctx)
		if ents.is_empty():
			return
		var tgt := _target_for(item, ents)
		var cmd := ""
		if tgt != "" and _rand() < _target_share():
			cmd = tgt
		else:
			var total := 0.0
			for e in ents:
				total += float((e as Array)[1])
			var u := _rand() * total
			var acc := 0.0
			cmd = String((ents[ents.size() - 1] as Array)[0])
			for e in ents:
				acc += float((e as Array)[1])
				if u < acc:
					cmd = String((e as Array)[0])
					break
		var n2 := int(item.get("n", 1))
		shards[cmd] = int(shards.get(cmd, 0)) + n2
		rewards.append({"kind": "shards", "commander": cmd, "name": String(commander(cmd).get("name", cmd)),
			"rarity": String(commander(cmd).get("rarity", "")), "n": n2, "target": cmd == tgt})
	elif item.has("cosmetic_pool"):
		var pool := _pool(String(item["cosmetic_pool"]))
		if pool.is_empty():
			return
		_grant_cosmetic(String(pool[rng.next_int(pool.size())]), rewards)
	elif item.has("cosmetic"):
		_grant_cosmetic(String(item["cosmetic"]), rewards)


func _grant_res(case_id: String, item: Dictionary, ctx: Dictionary, rewards: Array) -> void:
	var mult := int(_case(case_id).get("res_mult", 1))
	var hours := int(item["resources_h"]) * mult
	var income: Dictionary = ctx.get("income_per_hour", {})
	var dl := int(ctx.get("dl", 1))
	var key := String(item.get("res", "all")).trim_prefix("res_")
	if item.has("fallback"):
		var fb: Dictionary = item["fallback"]
		if dl < int(fb.get("below_dev_level", 5)):
			key = String(fb.get("res", "res_gold")).trim_prefix("res_")
	var res := {"gold": 0, "food": 0, "metal": 0}
	if key == "all":
		for r in ["gold", "food", "metal"]:
			res[r] = int(income.get(r, 0)) * hours
		if dl >= 5 and income.has("oil"):
			res["oil"] = int(income["oil"]) * hours
	else:
		res[key] = int(income.get(key, 0)) * hours
	rewards.append({"kind": "res", "res": res, "hours": hours, "item": String(item.get("id", "")),
		"name": _item_name(item, mult)})


func _grant_cosmetic(id: String, rewards: Array) -> void:
	var c := cosmetic(id)
	var r := String(c.get("rarity", "rare"))
	var cats: Dictionary = data().get("categories", {})
	var cat := String(c.get("category", ""))
	if owned_cosmetics.has(id):
		var g := dup_glitter(r)
		glitter += g
		rewards.append({"kind": "glitter", "n": g, "duplicate": true, "id": id,
			"name": String(c.get("name", id)), "rarity": r, "category": cat})
	else:
		owned_cosmetics[id] = true
		rewards.append({"kind": "cosmetic", "id": id, "name": String(c.get("name", id)), "rarity": r,
			"category": cat, "category_ru": String(cats.get(cat, cat))})


# ---------------------------------------------------------------- save

func to_dict() -> Dictionary:
	return {
		"rng": [rng.s0, rng.s1, rng.s2, rng.s3],
		"pity": pity.duplicate(),
		"history": history.duplicate(true),
		"owned_cosmetics": owned_cosmetics.duplicate(),
		"shards": shards.duplicate(),
		"glitter": glitter,
		"target_commander": target_commander,
		"free_crates": free_crates,
		"next_free_crate": next_free_crate,
		"collection_opened": collection_opened.duplicate(),
		"collection_season": collection_season,
		"opened": opened.duplicate(),
	}


## Accepts to_dict() output, also after a JSON round trip (float numbers).
static func from_dict(d: Dictionary) -> RefCounted:
	var c: _Self = _Self.new(0)
	var st: Array = d.get("rng", [])
	if st.size() == 4:
		c.rng.s0 = int(st[0])
		c.rng.s1 = int(st[1])
		c.rng.s2 = int(st[2])
		c.rng.s3 = int(st[3])
	c.pity = _int_values(d.get("pity", {}))
	c.history = _norm(d.get("history", []))
	var oc: Dictionary = d.get("owned_cosmetics", {})
	for k in oc:
		c.owned_cosmetics[String(k)] = true
	c.shards = _int_values(d.get("shards", {}))
	c.glitter = int(d.get("glitter", 0))
	c.target_commander = String(d.get("target_commander", ""))
	c.free_crates = int(d.get("free_crates", 0))
	c.next_free_crate = int(d.get("next_free_crate", 0))
	var co: Array = d.get("collection_opened", [])
	for id in co:
		c.collection_opened.append(String(id))
	c.collection_season = int(d.get("collection_season", c.collection_season))
	c.opened = _int_values(d.get("opened", {}))
	return c


static func _int_values(src: Dictionary) -> Dictionary:
	var out := {}
	for k in src:
		out[String(k)] = int(src[k])
	return out


## Integral floats (JSON) back to ints, recursively.
static func _norm(v: Variant) -> Variant:
	if v is float:
		var f: float = v
		if f == floorf(f) and absf(f) < 9.0e15:
			return int(f)
		return f
	if v is Dictionary:
		var out := {}
		var src: Dictionary = v
		for k in src:
			out[String(k)] = _norm(src[k])
		return out
	if v is Array:
		var arr: Array = []
		for x in (v as Array):
			arr.append(_norm(x))
		return arr
	return v
