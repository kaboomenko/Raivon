extends SceneTree
## Headless sim worker for the API server (docs/dev/server.md): one JSON command per stdin line, one JSON
## reply per stdout line. Reuses the client's rules (scripts/sim/*) so client and server never diverge.
## Run: godot --headless --path game --script res://server/sim_worker.gd
##
## Commands:
##   {"id": 1, "cmd": "ping"}                       → {"id": 1, "ok": true, "pong": true}
##   {"id": 2, "cmd": "income", "save": {...}, "now": unix}
##        → economy of a client save advanced to `now`: income per hour, storage caps, stock totals, DL

const MapGen := preload("res://scripts/sim/map_gen.gd")
const Economy := preload("res://scripts/sim/economy.gd")

const REPLY_PREFIX := "@@"  # replies are prefixed so engine log lines on stdout can be ignored


func _initialize() -> void:
	while true:
		var line := OS.read_string_from_stdin(65536).strip_edges()
		if line == "":
			if OS.get_stdin_type() == OS.STD_HANDLE_UNKNOWN:
				break
			continue
		if line == "quit":
			break
		var reply := handle(line)
		print(REPLY_PREFIX + JSON.stringify(reply))
	quit()


func handle(line: String) -> Dictionary:
	var msg: Variant = JSON.parse_string(line)
	if typeof(msg) != TYPE_DICTIONARY:
		return {"ok": false, "error": "E_JSON"}
	var id: Variant = msg.get("id", null)
	match String(msg.get("cmd", "")):
		"ping":
			return {"id": id, "ok": true, "pong": true}
		"income":
			return income(id, msg)
	return {"id": id, "ok": false, "error": "E_CMD"}


func income(id: Variant, msg: Dictionary) -> Dictionary:
	var save: Dictionary = msg.get("save", {})
	if int(save.get("version", 0)) != 1 or not save.has("econ"):
		return {"id": id, "ok": false, "error": "E_SAVE"}
	var w = MapGen.generate_chapter_one(int(save["seed"]))
	var cells: Array = save.get("cells", [])
	if cells.size() != w.cells.size():
		return {"id": id, "ok": false, "error": "E_CELLS"}
	for i in cells.size():
		w.cells[i]["owner"] = int(cells[i][0])
		w.cells[i]["controller"] = int(cells[i][1])
		w.cells[i]["fort"] = int(cells[i][2])
	var econ = Economy.from_dict(save["econ"])
	econ.tick(w, int(msg.get("now", econ.last_tick)))
	var stock := {}
	for r in Economy.RES:
		stock[r] = econ.stock_total(r)
	return {"id": id, "ok": true, "dl": econ.dev_level(), "income_per_hour": econ.income_per_hour(w),
		"storage_cap": econ.storage_cap(), "stock": stock, "res": econ.res}
