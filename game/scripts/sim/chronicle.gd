extends RefCounted
## «Летопись державы» (canon §12.5, 07 §7): 40 long goals in 6 chapters, a Raivite reward (bigger for the early
## ones), cosmetics on 6 of them. Never reset. Progress comes from the game's counters (`stats`) or a live measure
## (`@…`, computed by the caller); a goal whose system isn't in the build yet is «soon». Deterministic: the caller
## pays the reward and grants the cosmetic.

## code, chapter, metric, target, raivites, cosmetic ("" none), soon
const LIST := [
	["ach_first_peace", "map", "peaces", 1, 25, "", false],
	["ach_hexes_25", "map", "@hexes", 25, 25, "", false],
	["ach_hexes_50", "map", "@hexes", 50, 10, "", false],
	["ach_hexes_100", "map", "@hexes", 100, 20, "", false],
	["ach_hexes_200", "map", "@hexes", 200, 30, "cos_frame_empire", false],
	["ach_half_world", "map", "@half_world", 1, 25, "cos_flag_part_half_world", false],
	["ach_colonize_40", "map", "colonized", 40, 10, "", false],
	["ach_offensive_10", "war", "offensives", 10, 20, "", false],
	["ach_offensive_100", "war", "offensives", 100, 10, "", false],
	["ach_offensive_500", "war", "offensives", 500, 25, "", false],
	["ach_perfect_25", "war", "stars3", 25, 10, "", false],
	["ach_wedge_100", "war", "wedges", 100, 10, "", false],
	["ach_pocket_50", "war", "pocket_hexes", 50, 10, "", false],
	["ach_capitals_5", "war", "capitals_occupied", 5, 10, "", false],
	["ach_defense_20", "war", "defenses", 20, 10, "", false],
	["ach_raiders_50", "war", "camps", 50, 10, "", false],
	["ach_triumph_3", "war", "coalition_wins", 3, 20, "", false],
	["ach_peace_25", "peace", "peace_wins", 25, 10, "", false],
	["ach_peace_60", "peace", "peace_wins", 60, 30, "cos_peace_seal_olive_branch", false],
	["ach_mercy_5", "peace", "mercy", 5, 10, "", false],
	["ach_blueprints_25", "peace", "blueprints", 25, 10, "", true],
	["ach_first_alliance", "peace", "alliances", 1, 20, "", false],
	["ach_swap_5", "peace", "swaps", 5, 10, "", false],
	["ach_coalition_broken", "peace", "coalitions_broken", 1, 10, "", false],
	["ach_rout", "peace", "routs", 1, 10, "", false],
	["ach_dev_3", "dev", "@dl", 3, 20, "", false],
	["ach_dev_5", "dev", "@dl", 5, 30, "", false],
	["ach_dev_8", "dev", "@dl", 8, 15, "cos_flag_part_skyscraper", false],
	["ach_dev_10", "dev", "@dl", 10, 40, "cos_frame_ultra", true],
	["ach_deposits_100", "dev", "convoys", 100, 10, "", false],
	["ach_gold_1m", "dev", "gold_collected", 1000000, 10, "", false],
	["ach_research_50", "dev", "research_done", 50, 10, "", false],
	["ach_research_150", "dev", "research_done", 150, 20, "", false],
	["ach_ultrafence_5", "dev", "@fort8", 5, 15, "", false],
	["ach_vein_4", "dev", "@veins", 4, 15, "", false],
	["ach_cmd_4", "cmd", "@cmd_det", 4, 25, "", false],
	["ach_cmd_8", "cmd", "@cmd_det", 8, 15, "", false],
	["ach_cmd_level_10", "cmd", "cmd_level", 10, 10, "", true],
	["ach_arena_gold", "arena", "arena_league", 4, 10, "", true],
	["ach_arena_legend", "arena", "arena_league", 7, 30, "cos_frame_arena_legend", true],
]
const CHAPTERS := ["map", "war", "peace", "dev", "cmd", "arena"]
## The 8 commanders the Chronicle counts — only the deterministic ones (07 §7.1, 04 §15.7.1).
const DET_COMMANDERS := ["cmd_bram", "cmd_lira", "cmd_vega", "cmd_frey", "cmd_irma", "cmd_hawk", "cmd_rai", "cmd_seir"]

var claimed := {}   # code -> true
var reached := {}   # code -> true: announced once («Летопись: …» toast)
var best := {}      # code -> best value seen (live measures like hexes can drop; the goal stays reached)


static func index_of(code: String) -> int:
	for i in LIST.size():
		if LIST[i][0] == code:
			return i
	return -1


## Feeds the current values (metric -> value); returns the codes newly reached.
func update(values: Dictionary) -> Array:
	var fresh: Array = []
	for row in LIST:
		var code: String = row[0]
		if bool(row[6]):
			continue
		var v := int(values.get(row[2], 0))
		best[code] = maxi(int(best.get(code, 0)), v)
		if int(best[code]) >= int(row[3]) and not reached.has(code):
			reached[code] = true
			fresh.append(code)
	return fresh


func progress(code: String) -> int:
	var i := index_of(code)
	return mini(int(best.get(code, 0)), int(LIST[i][3])) if i >= 0 else 0


func can_claim(code: String) -> bool:
	return reached.has(code) and not claimed.has(code)


## Marks it claimed; returns [raivites, cosmetic] or [] when it can't be claimed.
func claim(code: String) -> Array:
	if not can_claim(code):
		return []
	claimed[code] = true
	var row: Array = LIST[index_of(code)]
	return [int(row[4]), String(row[5])]


func claimable() -> int:
	var n := 0
	for code in reached:
		if not claimed.has(code):
			n += 1
	return n


func to_dict() -> Dictionary:
	return {"claimed": claimed.keys(), "reached": reached.keys(), "best": best.duplicate()}


func load_dict(d: Dictionary) -> void:
	claimed = {}
	for c in d.get("claimed", []):
		claimed[String(c)] = true
	reached = {}
	for c in d.get("reached", []):
		reached[String(c)] = true
	best = {}
	var b: Dictionary = d.get("best", {})
	for k in b:
		best[String(k)] = int(b[k])
