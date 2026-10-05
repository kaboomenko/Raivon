extends RefCounted
## Local save of the player's progress (user://save.json). The world is regenerated from its seed and the
## saved per-hex state is applied on top, so the file stays small. An offensive in progress is not saved:
## after a restart the war continues from the last finished offensive.

const MapGen := preload("res://scripts/sim/map_gen.gd")

const PATH := "user://save.json"
const VERSION := 1


static func save(g: Node) -> void:
	var cells: Array = []
	for c in g.sim.cells:
		cells.append([c["owner"], c["controller"], c["fort"]])
	var states: Array = []
	for st in g.sim.states:
		states.append(st["dev_level"])
	var armies: Array = []
	for a in g.armies:
		armies.append({"id": a["id"], "side": a["side"], "hex": a["hex"], "str": a["str"], "max_str": a["max_str"],
			"infantry": a["infantry"]})
	var d := {
		"version": VERSION,
		"seed": g.sim.map_seed,
		"saved_at": int(Time.get_unix_time_from_system()),
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
	}
	if g.get("econ") != null:
		d["econ"] = g.econ.to_dict()
	var f := FileAccess.open(PATH, FileAccess.WRITE)
	if f == null:
		push_warning("save failed: %s" % FileAccess.get_open_error())
		return
	f.store_string(JSON.stringify(d))


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
	var cells: Array = d["cells"]
	if cells.size() != w.cells.size():
		return false
	for i in cells.size():
		var row: Array = cells[i]
		w.cells[i]["owner"] = int(row[0])
		w.cells[i]["controller"] = int(row[1])
		w.cells[i]["fort"] = int(row[2])
	var states: Array = d.get("states", [])
	for i in mini(states.size(), w.states.size()):
		w.states[i]["dev_level"] = int(states[i])
	var armies: Array = []
	for a in d.get("armies", []):
		armies.append({"id": int(a["id"]), "side": int(a["side"]), "hex": int(a["hex"]), "str": int(a["str"]),
			"max_str": int(a["max_str"]), "infantry": int(a["infantry"]), "hold": false, "move": null,
			"start_str": int(a["str"]), "attrition": 0, "routed": false})
	var war := {}
	var sw: Dictionary = d.get("war", {})
	for k in sw:
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
	g._last_refill = int(d.get("saved_at", 0))  # armies heal while the app is closed
	if d.has("econ") and g.get("econ") != null:
		g.econ = g.econ.get_script().from_dict(d["econ"])
	return true


static func wipe() -> void:
	if FileAccess.file_exists(PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(PATH))
