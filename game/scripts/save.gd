extends RefCounted
## Local save of the player's progress (user://save.json). The world is regenerated from its seed and the
## saved per-hex state is applied on top, so the file stays small. An offensive in progress is not saved:
## after a restart the war continues from the last finished offensive.

const MapGen := preload("res://scripts/sim/map_gen.gd")

const PATH := "user://save.json"
const VERSION := 1
## Player settings that outlive a «Новая игра» (the UI language): {"lang": "ru" | "en"}.
const SETTINGS_PATH := "user://settings.json"


## Writes the save file and returns the same dictionary (net.gd uploads it to the cloud).
static func save(g: Node) -> Dictionary:
	var d := to_dict(g)
	var f := FileAccess.open(PATH, FileAccess.WRITE)
	if f == null:
		push_warning("save failed: %s" % FileAccess.get_open_error())
		return d
	f.store_string(JSON.stringify(d))
	return d


## Writes a save received from the cloud (applied on the next load).
static func write_raw(d: Dictionary) -> void:
	var f := FileAccess.open(PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(d))


static func to_dict(g: Node) -> Dictionary:
	var cells: Array = []
	for c in g.sim.cells:
		cells.append([c["owner"], c["controller"], c["fort"], int(c.get("tower", 0))])
	var states: Array = []
	for st in g.sim.states:
		states.append(st["dev_level"])
	var armies: Array = []
	for a in g.armies:
		armies.append({"id": a["id"], "side": a["side"], "hex": a["hex"], "str": a["str"], "max_str": a["max_str"],
			"infantry": a["infantry"], "slots": a.get("slots", 3), "march": a.get("march")})
	var d := {
		"version": VERSION,
		"seed": g.sim.map_seed,
		"saved_at": int(g.now_s()) if g.has_method("now_s") else int(Time.get_unix_time_from_system()),
		"cells": cells,
		"states": states,
		"armies": armies,
		"war": g.war,
		"truce": g.truce,
		"ftue": g.ftue,
		"colonizing": g.colonizing,
		"colonized": g.colonized,
		"inbox": g.inbox,
		"ultimatum": g.ultimatum,
		"ultimatum_at": g.ultimatum_at,
		"deposits": g.deposits.to_dict(),
		"first_convoy_done": g.first_convoy_done,
		"training": g.training,
		"ad_counts": g.ad_counts,
		"opinion": g.opinion,
		"gift_at": g.gift_at,
		"stats": g.stats,
		"stars_claimed": g.stars_claimed,
		"chapter_done": g.chapter_done,
		"chapter": g.chapter,
		"ai_dl_at": g.ai_dl_at,
		"stats_base": g.stats_base,
		"stats_base3": g.stats_base3,
		"stats_base4": g.stats_base4,
		"threat": g.threat,
		"threat_at": g.threat_at,
		"coalition": g.coalition,
		"coalition_last": g.coalition_last,
		"swap_at": g.swap_at,
		"pacts": g.pacts,
		"ult_check": g.ult_check,
		"ai_colonizing": g.ai_colonizing,
		"ai_wars": g.ai_wars,
		"allies": g.allies,
		"ai_alliances": g.ai_alliances,
		"ai_alliance_check": g.ai_alliance_check,
		"ai_war_check": g.ai_war_check,
		"cases": g.cases.to_dict(),
		"speed_minutes": g.speed_minutes,
		"purchases": g.purchases,
		"research": g.research.to_dict(),
		"market": g.market.to_dict() if g.market != null else {},
		"camps": g.camps.to_dict() if g.camps != null else {},
	}
	if g.get("econ") != null:
		d["econ"] = g.econ.to_dict()
	return d


## Returns {} when there is no usable save.
static func read() -> Dictionary:
	if not FileAccess.file_exists(PATH):
		return {}
	var txt := FileAccess.get_file_as_string(PATH)
	var parsed: Variant = JSON.parse_string(txt)
	if typeof(parsed) != TYPE_DICTIONARY or int(parsed.get("version", 0)) != VERSION:
		return {}
	return parsed


## Applies a save read by `read()` to a freshly generated world; returns false if it does not fit.
static func apply(g: Node, d: Dictionary) -> bool:
	var w = MapGen.generate_chapter_one(int(d["seed"]))
	if int(d.get("chapter", 1)) >= 2:
		load("res://scripts/sim/ring_gen.gd").extend_chapter_two(w, int(w.map_seed) ^ 0x2)
	if int(d.get("chapter", 1)) >= 3:
		load("res://scripts/sim/ring_next.gd").extend_chapter_three(w, int(w.map_seed) ^ 0x3)
	if int(d.get("chapter", 1)) >= 4:
		load("res://scripts/sim/ring_next.gd").extend_chapter_four(w, int(w.map_seed) ^ 0x4)
	var cells: Array = d["cells"]
	if cells.size() != w.cells.size():
		return false
	for i in cells.size():
		var row: Array = cells[i]
		w.cells[i]["owner"] = int(row[0])
		w.cells[i]["controller"] = int(row[1])
		w.cells[i]["fort"] = int(row[2])
		w.cells[i]["tower"] = int(row[3]) if row.size() > 3 else 0
	var states: Array = d.get("states", [])
	for i in mini(states.size(), w.states.size()):
		w.states[i]["dev_level"] = int(states[i])
	var armies: Array = []
	for a in d.get("armies", []):
		armies.append({"id": int(a["id"]), "side": int(a["side"]), "hex": int(a["hex"]), "str": int(a["str"]),
			"max_str": int(a["max_str"]), "infantry": int(a["infantry"]), "hold": false, "move": null,
			"start_str": int(a["str"]), "attrition": 0, "routed": false, "slots": int(a.get("slots", 3))})
		var mv: Variant = a.get("march")
		if typeof(mv) == TYPE_DICTIONARY and typeof(mv.get("path")) == TYPE_ARRAY and not (mv["path"] as Array).is_empty():
			var mpath: Array = []
			for h in mv["path"]:
				mpath.append(int(h))
			armies.back()["march"] = {"path": mpath, "t0": int(mv.get("t0", 0)), "leg": int(mv.get("leg", 20))}
	var war := {}
	var sw: Dictionary = d.get("war", {})
	for k in sw:
		if typeof(sw[k]) == TYPE_ARRAY:  # war["coalition"]: the member states
			var arr: Array = []
			for v in sw[k]:
				arr.append(int(v))
			war[k] = arr
		else:
			war[k] = int(sw[k])
	var truce := {}
	var st: Dictionary = d.get("truce", {})
	for k in st:
		truce[int(k)] = float(st[k])
	g.sim = w
	g.armies = armies
	g.war = war
	g.truce = truce
	g.ftue = int(d.get("ftue", 0))
	var col := {}
	var sc: Dictionary = d.get("colonizing", {})
	for k in sc:
		col[int(k)] = int(sc[k])
	g.colonizing = col
	g.colonized = int(d.get("colonized", 0))
	g.inbox = d.get("inbox", [])
	var ult := {}
	var su: Dictionary = d.get("ultimatum", {})
	for k in su:
		ult[k] = int(su[k])
	g.ultimatum = ult
	g.ultimatum_at = int(d.get("ultimatum_at", 0))
	if d.has("deposits"):
		g.deposits = load("res://scripts/sim/deposits.gd").from_dict(d["deposits"], int(d["seed"]) ^ 0x5EED)
	g.first_convoy_done = bool(d.get("first_convoy_done", false))
	var tr := {}
	var st2: Dictionary = d.get("training", {})
	for k in st2:
		tr[k] = int(st2[k])
	g.training = tr
	g.ad_counts = d.get("ad_counts", {})
	var op := {}
	var so: Dictionary = d.get("opinion", {})
	for k in so:
		op[int(k)] = float(so[k])
	g.opinion = op
	var ga := {}
	var sg: Dictionary = d.get("gift_at", {})
	for k in sg:
		ga[int(k)] = int(sg[k])
	g.gift_at = ga
	g._last_opinion = int(d.get("saved_at", 0))
	var sts := {}
	var ss: Dictionary = d.get("stats", {})
	for k in ss:
		sts[k] = int(ss[k])
	g.stats = sts
	g.stars_claimed = d.get("stars_claimed", {})
	g.chapter_done = bool(d.get("chapter_done", false))
	g.chapter = int(d.get("chapter", 1))
	g.allies = []
	for a in d.get("allies", []):
		g.allies.append(int(a))
		w.player_allies[int(a)] = true
	var aia: Dictionary = d.get("ai_alliances", {})
	g.ai_alliances = {}
	for k in aia:
		g.ai_alliances[int(k)] = int(aia[k])
	g.ai_alliance_check = int(d.get("ai_alliance_check", 0))
	g.ai_wars = []
	for aw in d.get("ai_wars", []):
		if typeof(aw) == TYPE_DICTIONARY:
			g.ai_wars.append({"a": int(aw["a"]), "b": int(aw["b"]), "until": int(aw["until"]), "next": int(aw["next"]), "boost": int(aw.get("boost", -1))})
	g.ai_war_check = int(d.get("ai_war_check", 0))
	var aic: Dictionary = d.get("ai_colonizing", {})
	g.ai_colonizing = {}
	for k in aic:
		var v: Dictionary = aic[k]
		g.ai_colonizing[int(k)] = {"hex": int(v.get("hex", -1)), "at": int(v.get("at", 0))}
	var ulc: Dictionary = d.get("ult_check", {})
	g.ult_check = {}
	for k in ulc:
		g.ult_check[int(k)] = int(ulc[k])
	var sb: Dictionary = d.get("stats_base", {})
	g.stats_base = {}
	for k in sb:
		g.stats_base[String(k)] = int(sb[k])
	var sb3: Dictionary = d.get("stats_base3", {})
	g.stats_base3 = {}
	for k in sb3:
		g.stats_base3[String(k)] = int(sb3[k])
	g.threat = float(d.get("threat", 0.0))
	g.threat_at = int(d.get("threat_at", 0))
	g.coalition_last = int(d.get("coalition_last", 0))
	var pc: Dictionary = d.get("pacts", {})
	g.pacts = {}
	for k in pc:
		g.pacts[int(k)] = int(pc[k])
	var sw_at: Dictionary = d.get("swap_at", {})
	g.swap_at = {}
	for k in sw_at:
		g.swap_at[int(k)] = int(sw_at[k])
	var co: Dictionary = d.get("coalition", {})
	g.coalition = {}
	if not co.is_empty():
		var mem: Array = []
		for m in co.get("members", []):
			mem.append(int(m))
		g.coalition = {"leader": int(co.get("leader", -1)), "members": mem, "at": int(co.get("at", 0))}
	var sb4: Dictionary = d.get("stats_base4", {})
	g.stats_base4 = {}
	for k in sb4:
		g.stats_base4[String(k)] = int(sb4[k])
	var dla: Dictionary = d.get("ai_dl_at", {})
	g.ai_dl_at = {}
	for k in dla:
		g.ai_dl_at[int(k)] = int(dla[k])
	if d.has("cases"):
		g.cases = load("res://scripts/sim/cases.gd").from_dict(d["cases"])
	g.speed_minutes = int(d.get("speed_minutes", 0))
	g.purchases = d.get("purchases", {})
	if d.has("research"):
		g.research = load("res://scripts/sim/research.gd").from_dict(d["research"])
	if typeof(d.get("camps")) == TYPE_DICTIONARY:
		if g.camps == null:
			g.camps = load("res://scripts/sim/camps.gd").new(int(d["seed"]) ^ 0xCA4B)
		g.camps.load_dict(d["camps"])
	if typeof(d.get("market")) == TYPE_DICTIONARY:
		if g.market == null:
			g.market = load("res://scripts/sim/market.gd").new()
		g.market.load_dict(d["market"])
	g._last_refill = int(d.get("saved_at", 0))  # armies heal while the app is closed
	if d.has("econ") and g.get("econ") != null:
		g.econ = g.econ.get_script().from_dict(d["econ"])
	return true


## Settings saved with write_settings(); {} when there are none.
static func read_settings() -> Dictionary:
	if not FileAccess.file_exists(SETTINGS_PATH):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(SETTINGS_PATH))
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}


## Merges `d` into the saved settings.
static func write_settings(d: Dictionary) -> void:
	var s := read_settings()
	s.merge(d, true)
	var f := FileAccess.open(SETTINGS_PATH, FileAccess.WRITE)
	if f == null:
		push_warning("settings save failed: %s" % FileAccess.get_open_error())
		return
	f.store_string(JSON.stringify(s))


## Removes the game progress (settings such as the language stay).
static func wipe() -> void:
	if FileAccess.file_exists(PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(PATH))
