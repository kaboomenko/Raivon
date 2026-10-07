extends RefCounted
## Academy research (canon §12.3, numbers 11 §9). One research at a time, no builder needed.
## Cost(line, L) = W × C(L), C(L) = 6000 × 1,35^(2L−3) × k(L); level ≤ min(DL, ⌈Academy level / 2⌉).
## Only lines whose effects the game models are listed; the rest arrive with their systems.

## id -> {name, branch, max, w, shares: {res: share}, desc, unlock_dl}
const LINES := {
	"infantry": {"name": "rs.infantry", "branch": "rs.branch.army", "max": 10, "w": 1.0, "shares": {"gold": 0.6, "food": 0.4}, "desc": "rs.infantry.desc", "unlock_dl": 1},
	"reserve": {"name": "rs.reserve", "branch": "rs.branch.army", "max": 5, "w": 0.8, "shares": {"gold": 0.6, "food": 0.4}, "desc": "rs.reserve.desc", "unlock_dl": 1},
	"drill": {"name": "rs.drill", "branch": "rs.branch.army", "max": 5, "w": 0.8, "shares": {"gold": 0.6, "metal": 0.4}, "desc": "rs.drill.desc", "unlock_dl": 1},
	"taxes": {"name": "rs.taxes", "branch": "rs.branch.economy", "max": 10, "w": 1.0, "shares": {"gold": 0.4, "food": 0.3, "metal": 0.3}, "desc": "rs.taxes.desc", "unlock_dl": 1},
	"harvest": {"name": "rs.harvest", "branch": "rs.branch.economy", "max": 10, "w": 0.8, "shares": {"gold": 0.4, "food": 0.3, "metal": 0.3}, "desc": "rs.harvest.desc", "unlock_dl": 1},
	"metallurgy": {"name": "rs.metallurgy", "branch": "rs.branch.economy", "max": 10, "w": 0.8, "shares": {"gold": 0.4, "food": 0.3, "metal": 0.3}, "desc": "rs.metallurgy.desc", "unlock_dl": 1},
	"cellars": {"name": "rs.cellars", "branch": "rs.branch.economy", "max": 5, "w": 0.6, "shares": {"gold": 0.4, "food": 0.3, "metal": 0.3}, "desc": "rs.cellars.desc", "unlock_dl": 1},
	"logistics": {"name": "rs.logistics", "branch": "rs.branch.economy", "max": 10, "w": 0.8, "shares": {"gold": 0.4, "food": 0.3, "metal": 0.3}, "desc": "rs.logistics.desc", "unlock_dl": 1},
	"thrift": {"name": "rs.thrift", "branch": "rs.branch.economy", "max": 5, "w": 0.8, "shares": {"gold": 0.4, "food": 0.3, "metal": 0.3}, "desc": "rs.thrift.desc", "unlock_dl": 3},
	"colonization": {"name": "rs.colonization", "branch": "rs.branch.economy", "max": 3, "w": 0.5, "shares": {"gold": 0.4, "food": 0.3, "metal": 0.3}, "desc": "rs.colonization.desc", "unlock_dl": 1},
}
const ORDER: Array[String] = ["taxes", "infantry", "harvest", "metallurgy", "reserve", "logistics", "cellars", "colonization", "drill", "thrift"]
const K: Array[float] = [0.0, 0.15, 0.22, 0.30, 0.48]
## Level timers by the line's length (11 §9.1): 10-level, 5-level and 3-level lines.
const TIME_10: Array[int] = [0, 30, 120, 1200, 3600, 10800, 21600, 28800, 57600, 86400, 129600]
const TIME_5: Array[int] = [0, 60, 600, 1800, 7200, 14400]
const TIME_3: Array[int] = [0, 300, 900, 1800]

var levels := {}  # line -> level
var current := {}  # {line, end, dur (the full time), cut (seconds taken off by blueprints)}
var blueprints := 0  # «Трофейные чертежи» (canon §9.14, 07 §6.1): at most 5 in store

const BLUEPRINT_MAX := 5


static func base_cost(level: int) -> float:
	var k: float = K[level] if level < K.size() else 1.0
	return 6000.0 * pow(1.35, 2 * level - 3) * k


func level(line: String) -> int:
	return int(levels.get(line, 0))


func cost(line: String) -> Dictionary:
	var spec: Dictionary = LINES[line]
	var next := level(line) + 1
	var total := float(spec["w"]) * base_cost(next)
	var out := {}
	var shares: Dictionary = spec["shares"]
	for r in shares:
		out[r] = int(ceil(total * float(shares[r])))
	return out


## Academy −4% per level (canon §7).
func seconds(line: String, academy_level: int) -> int:
	var spec: Dictionary = LINES[line]
	var next := level(line) + 1
	var table: Array[int] = TIME_10 if int(spec["max"]) == 10 else (TIME_5 if int(spec["max"]) == 5 else TIME_3)
	var base: int = table[mini(next, table.size() - 1)]
	return maxi(5, int(base * (1.0 - 0.04 * academy_level)))


func max_level(line: String, dl: int, academy_level: int) -> int:
	return mini(int(LINES[line]["max"]), mini(dl, ceili(academy_level / 2.0)))


## "" when the next level can start; otherwise a reason key ("key|arg|…", translated by the UI).
func can_start(line: String, dl: int, academy_level: int, res: Dictionary, now: int) -> String:
	var spec: Dictionary = LINES[line]
	if dl < int(spec["unlock_dl"]):
		return "err.unlock_dl|%d" % int(spec["unlock_dl"])
	if not current.is_empty() and int(current["end"]) > now:
		return "err.academy_busy"
	if level(line) >= int(spec["max"]):
		return "err.max"
	if level(line) >= max_level(line, dl, academy_level):
		return "err.need_academy|%d" % (2 * (level(line) + 1) - 1)
	var c := cost(line)
	for r in c:
		if int(res.get(r, 0)) < int(c[r]):
			return "err.not_enough|res.gen.%s" % r
	return ""


## Starts the next level and spends resources from `res` (the economy's dictionary).
func start(line: String, dl: int, academy_level: int, res: Dictionary, now: int) -> bool:
	if can_start(line, dl, academy_level, res, now) != "":
		return false
	var c := cost(line)
	for r in c:
		res[r] = int(res[r]) - int(c[r])
	var dur := seconds(line, academy_level)
	current = {"line": line, "end": now + dur, "dur": dur, "cut": 0}
	return true


## Trophy blueprints won by plunder: kept up to 5, the rest burn. Returns how many burned.
func add_blueprints(n: int) -> int:
	var room := BLUEPRINT_MAX - blueprints
	blueprints = mini(BLUEPRINT_MAX, blueprints + n)
	return maxi(0, n - room)


## «Применить чертёж»: −10% of the remaining time, at most −50% of the research in all. False when it can't.
func apply_blueprint(now: int) -> bool:
	if current.is_empty() or blueprints <= 0:
		return false
	var left := int(current["end"]) - now
	var dur := int(current.get("dur", left))
	var room := dur / 2 - int(current.get("cut", 0))
	var cut := mini(left / 10, room)
	if cut <= 0:
		return false
	current["end"] = int(current["end"]) - cut
	current["cut"] = int(current.get("cut", 0)) + cut
	blueprints -= 1
	return true


## A plundered defeat costs `pct`% of the running research's full time in progress (never below zero progress).
func lose_progress(pct: int, now: int) -> int:
	if current.is_empty():
		return 0
	var dur := int(current.get("dur", int(current["end"]) - now))
	var before := int(current["end"])
	current["end"] = mini(before + dur * pct / 100, now + dur)
	return int(current["end"]) - before


## Completes the running research when due; returns the finished line or "".
func tick(now: int) -> String:
	if current.is_empty() or now < int(current["end"]):
		return ""
	var line: String = current["line"]
	levels[line] = level(line) + 1
	current = {}
	return line


## Economy-side effects for economy.research (canon §12.3).
func economy_levels() -> Dictionary:
	return {"gold": level("taxes"), "food": level("harvest"), "metal": level("metallurgy"),
		"cellars": level("cellars"), "thrift": level("thrift")}


func to_dict() -> Dictionary:
	return {"levels": levels, "current": current, "blueprints": blueprints}


static func from_dict(d: Dictionary):
	var r = load("res://scripts/sim/research.gd").new()
	var lv: Dictionary = d.get("levels", {})
	for k in lv:
		r.levels[String(k)] = int(lv[k])
	var cur: Dictionary = d.get("current", {})
	if not cur.is_empty():
		r.current = {"line": String(cur["line"]), "end": int(cur["end"]), "dur": int(cur.get("dur", 0)), "cut": int(cur.get("cut", 0))}
	r.blueprints = int(d.get("blueprints", 0))
	return r
