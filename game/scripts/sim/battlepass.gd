extends RefCounted
## «Военный пропуск» (canon §15.6, 09 §9.12): a 28-day season of 40 levels, 1 000 XP each; a free and a premium
## track (premium `iap_pass`, elite `iap_pass_elite` = premium + 15 levels at once + the animated season ink).
## XP comes only from play (09 §9.12.2): daily orders, offensives (40 / ★★ 55 / ★★★ 70, full for the first 8 a day,
## then 10), a held live defence 50, a victorious peace 80 (3 a day), a marauder camp 15 (3 a day), a settled hex
## 10 (5 a day). Ads, purchases and Raivites never buy XP. Deterministic; the caller pays the rewards out.

const DATA_PATH := "res://data/pass_s1.json"
const DAY := 86400
const EPOCH := 1790827200  # 2026-10-01 04:00 UTC: season 1 starts here, then every 28 days
const XP_LEVEL := 1000
const LEVELS := 40
## source -> [xp, full daily count, xp after the cap]
const SOURCES := {
	"offensive": [40, 8, 10], "offensive2": [55, 8, 10], "offensive3": [70, 8, 10],
	"defense": [50, 1000, 50], "peace": [80, 3, 0], "camp": [15, 3, 0], "colonize": [10, 5, 0],
}

static var _data: Dictionary = {}

var season := -1
var xp := 0
var premium := false
var elite := false
var claimed_free := {}   # level -> true
var claimed_prem := {}
var daily := {}          # {day, counts: {source: n}}


static func data() -> Dictionary:
	if _data.is_empty():
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(DATA_PATH))
		if parsed is Dictionary:
			_data = parsed
	return _data


static func season_of(now: int) -> int:
	return int(floor(float(now - EPOCH) / (28.0 * DAY)))


static func season_end(now: int) -> int:
	return EPOCH + (season_of(now) + 1) * 28 * DAY


## A new season starts from zero: XP, claims and the bought tracks (they are per season, canon §15.3).
func refresh(now: int) -> bool:
	var s := season_of(now)
	if s == season:
		return false
	season = s
	xp = 0
	premium = false
	elite = false
	claimed_free = {}
	claimed_prem = {}
	daily = {}
	return true


func level() -> int:
	return mini(LEVELS, xp / XP_LEVEL)


## XP for a play event, with the daily caps of 09 §9.12.2. Returns the XP added.
func gain(source: String, now: int) -> int:
	refresh(now)
	var d := int(floor(float(now - 4 * 3600) / DAY))
	if int(daily.get("day", -1)) != d:
		daily = {"day": d, "counts": {}}
	var counts: Dictionary = daily["counts"]
	var key := "offensive" if source.begins_with("offensive") else source
	var spec: Array = SOURCES.get(source, [0, 0, 0])
	var n: int = counts.get(key, 0)
	counts[key] = n + 1
	var add: int = int(spec[0]) if n < int(spec[1]) else int(spec[2])
	xp += add
	return add


func add_xp(n: int, now: int) -> void:
	refresh(now)
	xp += n


func reward(lvl: int, track: String) -> Array:
	var levels: Array = data().get("levels", [])
	if lvl < 1 or lvl > levels.size():
		return []
	return levels[lvl - 1].get(track, [])


func can_claim(lvl: int, track: String) -> bool:
	if lvl < 1 or lvl > level():
		return false
	if track == "premium":
		return premium and not claimed_prem.has(lvl)
	return not claimed_free.has(lvl)


## Marks the reward claimed and returns it ([] when not claimable).
func claim(lvl: int, track: String) -> Array:
	if not can_claim(lvl, track):
		return []
	if track == "premium":
		claimed_prem[lvl] = true
	else:
		claimed_free[lvl] = true
	return reward(lvl, track)


func buy(sku: String) -> void:
	premium = true
	if sku.begins_with("iap_pass_elite") and not elite:
		elite = true
		xp += int(data().get("elite_levels", 15)) * XP_LEVEL


func to_dict() -> Dictionary:
	return {"season": season, "xp": xp, "premium": premium, "elite": elite, "free": claimed_free.keys(),
		"prem": claimed_prem.keys(), "daily": daily.duplicate(true)}


func load_dict(d: Dictionary) -> void:
	season = int(d.get("season", -1))
	xp = int(d.get("xp", 0))
	premium = bool(d.get("premium", false))
	elite = bool(d.get("elite", false))
	claimed_free = {}
	for l in d.get("free", []):
		claimed_free[int(l)] = true
	claimed_prem = {}
	for l in d.get("prem", []):
		claimed_prem[int(l)] = true
	var dl: Dictionary = d.get("daily", {})
	var counts := {}
	var dc: Dictionary = dl.get("counts", {})
	for k in dc:
		counts[String(k)] = int(dc[k])
	daily = {"day": int(dl.get("day", -1)), "counts": counts} if not dl.is_empty() else {}
