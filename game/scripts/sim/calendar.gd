extends RefCounted
## Login calendar (canon §14.5, 08 §8.8): a soft streak — a calendar day is credited on the first visit of a game
## day (04:00 reset), a missed day pauses it and never resets it. The credited day's reward waits until taken
## (a new day is not credited while it waits). Cycle 1 «Новобранец» is the 28-day table of 08 §8.8.2; then cycle 2+
## «Державный календарь» (08 §8.8.3) repeats. `ad_daily_double` doubles the day's reward except on key days.
## Deterministic; the caller pays the rewards out.

const DAY := 86400
const REFRESH_SEC := 4 * 3600
const LENGTH := 28

## Each day: [rewards, ×2 allowed]. A reward is [kind, …]: res h · crate n · raivite n · speed h count · builder ·
## cmd id (the unlock shards) · shards id n · shards_pick n (the least advanced common/rare commander) ·
## shards_choice n (the player picks a common/rare commander) · cosmetic id · season_cosmetic (a not yet owned rare
## frame or emote).
const CYCLE_1 := [
	[[["res", 2], ["crate", 1]], true],
	[[["builder"]], false],
	[[["raivite", 30]], true],
	[[["cmd", "cmd_vega"]], false],
	[[["speed", 1, 2]], true],
	[[["crate", 2]], true],
	[[["cmd", "cmd_irma"]], false],
	[[["res", 4]], true],
	[[["raivite", 40]], true],
	[[["speed", 3, 1]], true],
	[[["shards", "cmd_vega", 10]], true],
	[[["cosmetic", "cos_flag_part_recruit_star"]], false],
	[[["res", 6]], true],
	[[["raivite", 300]], false],
	[[["crate", 3]], true],
	[[["speed", 3, 2]], true],
	[[["shards", "cmd_irma", 10]], true],
	[[["res", 8]], true],
	[[["raivite", 50]], true],
	[[["cosmetic", "cos_frame_recruit"]], false],
	[[["cosmetic", "cos_border_ink_flame"]], false],
	[[["speed", 8, 1]], true],
	[[["crate", 3]], true],
	[[["raivite", 60]], true],
	[[["res", 12]], true],
	[[["shards_choice", 15]], true],
	[[["cosmetic", "cos_emote_drumroll"]], false],
	[[["shards", "cmd_rai", 20]], false],
]
## Cycle 2+: the week pattern (days 1–7 repeat; day 28 replaces the 4th week's 7th day).
const WEEK_2 := [
	[[["res", 4]], true],
	[[["crate", 1]], true],
	[[["raivite", 20]], true],
	[[["speed", 1, 1]], true],
	[[["shards_pick", 5]], true],
	[[["speed", 3, 1]], true],
	[[["raivite", 10], ["crate", 1]], true],
]
const DAY_28 := [[["season_cosmetic"]], false]

var credited := 0        # calendar days credited in total (the next reward is day `credited`)
var last_day := -1       # the game day of the last credit
var pending := false     # the credited day's reward waits to be taken
var choice := 0          # shards taken but not yet given: the player still picks the commander


static func game_day(now: int) -> int:
	return int(floor(float(now - REFRESH_SEC) / DAY))


## Cycle number (1-based) and day in the cycle (1..28) of calendar day n (1-based).
static func cycle_of(n: int) -> int:
	return (n - 1) / LENGTH + 1


static func day_in_cycle(n: int) -> int:
	return (n - 1) % LENGTH + 1


static func entry(n: int) -> Array:
	var d := day_in_cycle(n)
	if cycle_of(n) == 1:
		return CYCLE_1[d - 1]
	if d == LENGTH:
		return DAY_28
	return WEEK_2[(d - 1) % 7]


## Credits a new calendar day on the first visit of a game day. True when a reward became ready.
func visit(now: int) -> bool:
	var d := game_day(now)
	if d == last_day:
		return false
	last_day = d
	if pending:
		return false  # the day goes to the waiting reward — days don't pile up (08 §8.8.1)
	credited += 1
	pending = true
	return true


## The waiting day's rewards ([] when nothing waits); marks it taken.
func claim() -> Array:
	if not pending:
		return []
	pending = false
	return (entry(credited)[0] as Array).duplicate(true)


func can_double() -> bool:
	return pending and bool(entry(credited)[1])


func to_dict() -> Dictionary:
	return {"credited": credited, "last_day": last_day, "pending": pending, "choice": choice}


func load_dict(d: Dictionary) -> void:
	credited = int(d.get("credited", 0))
	last_day = int(d.get("last_day", -1))
	pending = bool(d.get("pending", false))
	choice = int(d.get("choice", 0))
