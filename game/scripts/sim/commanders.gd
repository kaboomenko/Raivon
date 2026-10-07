extends RefCounted
## Commander levels (canon §8.4, 04 §15.1, §15.5): a commander opens once the shards received reach the unlock price
## (10/20/40/80) and is levelled 2..20 with shards + gold, instantly, no builder; level ≤ 2 × DL (16 at launch, DL8).
## `cases.shards` stays the total ever received — the shards spent are derived from the level, so «owned» and
## «maxed» (enough for level 20 — out of random pools) keep reading from the totals. The passive grows linearly
## v(L) = v1 + (v20 − v1) × (L − 1) / 19 (×1000, rounded down). Deterministic; the caller takes the gold.

const MAX_LEVEL := 20
const UNLOCK := {"common": 10, "rare": 20, "epic": 40, "legendary": 80}
## Shards for levels 2..20 (04 §15.5: ceil(s(L) × m(rarity))).
const SHARDS := {
	"common": [1, 2, 2, 3, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 23, 26],
	"rare": [2, 3, 3, 4, 4, 5, 7, 8, 9, 10, 12, 13, 15, 18, 20, 23, 25, 29, 33],
	"epic": [2, 3, 3, 5, 5, 6, 8, 9, 11, 12, 14, 15, 18, 21, 24, 27, 30, 35, 39],
	"legendary": [2, 4, 4, 6, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 46, 52],
}
## Gold for levels 2..20 — the same for every rarity.
const GOLD := [250, 450, 550, 900, 1000, 1600, 1750, 2750, 3000, 4550, 4900, 7200, 7650, 11250, 11900, 16000, 16800, 22000, 23000]
## The passives (04 §15.2): [string key, v1, v20, unit] — unit "%" (a percent), "pp" (points), "x" (a factor);
## a fixed part without growth has v1 == v20 == 0 and is shown as text only.
const PASSIVES := {
	"cmd_bram": [["inf", 5.0, 15.0, "%"]],
	"cmd_lira": [["refill", 5.0, 15.0, "%"]],
	"cmd_olm": [["forts", 5.0, 15.0, "%"]],
	"cmd_vik": [["scout", 0.0, 0.0, ""], ["power", 0.0, 10.0, "%"]],
	"cmd_vega": [["wedge", 5.0, 10.0, "pp"]],
	"cmd_kort": [["pocket", 1.5, 2.0, "x"]],
	"cmd_seir": [["landing", 0.0, 0.0, ""], ["port", 0.0, 10.0, "%"]],
	"cmd_frey": [["home", 5.0, 15.0, "%"]],
	"cmd_irma": [["breach", 0.0, 0.0, ""], ["attack", 0.0, 10.0, "%"]],
	"cmd_hawk": [["air", 5.0, 15.0, "%"], ["power", 0.0, 8.0, "%"]],
	"cmd_vance": [["energy", 0.0, 0.0, ""], ["power", 0.0, 8.0, "%"]],
	"cmd_rai": [["forms", 5.0, 10.0, "pp"], ["regen", 5.0, 10.0, "%"]],
}
## Albums (04 §15.7.1): a seal on the cover and a lore page only — no resources, cosmetics or power.
const ALBUMS := [
	["valley", ["cmd_bram", "cmd_lira", "cmd_olm", "cmd_vik"]],
	["staff", ["cmd_vega", "cmd_kort", "cmd_frey", "cmd_vance"]],
	["steel", ["cmd_irma", "cmd_hawk", "cmd_seir"]],
	["founder", ["cmd_rai"]],
]
## The levels shown in the passive table of the commander card.
const TABLE_LEVELS := [1, 5, 10, 15, 16, 20]

var levels := {}  # cmd id -> level bought (≥ 2); level 1 comes with the unlock


static func level_cap(dl: int) -> int:
	return clampi(2 * dl, 1, MAX_LEVEL)


## Shards a commander at level `lvl` has consumed: the unlock plus the levels 2..lvl (0 while locked).
static func spent(rarity: String, lvl: int) -> int:
	if lvl <= 0:
		return 0
	var s := int(UNLOCK.get(rarity, 10))
	var t: Array = SHARDS.get(rarity, SHARDS["common"])
	for l in range(2, mini(lvl, MAX_LEVEL) + 1):
		s += int(t[l - 2])
	return s


## Enough shards received for level 20: the commander leaves the random pools (canon §8.4).
static func maxed(rarity: String, total: int) -> bool:
	return total >= spent(rarity, MAX_LEVEL)


## The passive value at a level (×1000 rounded down, canon).
static func value(v1: float, v20: float, lvl: int) -> float:
	var l := clampi(lvl, 1, MAX_LEVEL)
	return floorf((v1 + (v20 - v1) * float(l - 1) / 19.0) * 1000.0 + 0.0001) / 1000.0


func level(cmd: String, rarity: String, total: int) -> int:
	if total < int(UNLOCK.get(rarity, 10)):
		return 0
	return maxi(1, int(levels.get(cmd, 1)))


## Shards toward the next level (received minus consumed).
func free_shards(cmd: String, rarity: String, total: int) -> int:
	return maxi(0, total - spent(rarity, level(cmd, rarity, total)))


## [shards, gold, need_dl] of the next level, or [] at level 20 or while locked.
func next_cost(cmd: String, rarity: String, total: int) -> Array:
	var l := level(cmd, rarity, total)
	if l <= 0 or l >= MAX_LEVEL:
		return []
	var t: Array = SHARDS.get(rarity, SHARDS["common"])
	return [int(t[l - 1]), int(GOLD[l - 1]), ceili((l + 1) / 2.0)]


## "" when the next level can be bought now; otherwise why not: "locked" · "max" · "dl" · "shards" · "gold".
func block_reason(cmd: String, rarity: String, total: int, gold: int, dl: int) -> String:
	var l := level(cmd, rarity, total)
	if l <= 0:
		return "locked"
	var c := next_cost(cmd, rarity, total)
	if c.is_empty():
		return "max"
	if l + 1 > level_cap(dl):
		return "dl"
	if free_shards(cmd, rarity, total) < int(c[0]):
		return "shards"
	if gold < int(c[1]):
		return "gold"
	return ""


## Buys the next level; returns the gold to take (-1 when it can't be bought).
func upgrade(cmd: String, rarity: String, total: int, gold: int, dl: int) -> int:
	if block_reason(cmd, rarity, total, gold, dl) != "":
		return -1
	var c := next_cost(cmd, rarity, total)
	levels[cmd] = level(cmd, rarity, total) + 1
	return int(c[1])


static func album_of(cmd: String) -> String:
	for a in ALBUMS:
		if (a[1] as Array).has(cmd):
			return String(a[0])
	return ""


func to_dict() -> Dictionary:
	return {"levels": levels.duplicate()}


func load_dict(d: Dictionary) -> void:
	levels = {}
	var l: Dictionary = d.get("levels", {})
	for k in l:
		levels[String(k)] = int(l[k])
