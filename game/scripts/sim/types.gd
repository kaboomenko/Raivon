extends RefCounted
## Core world constants and helpers (port of packages/sim/src/types.ts).
## Strength is fixed-point: 1 unit of Strength = 1000 (canon §16.1, ×1000).
##
## Cell (Dictionary):
##   {id:int, q:int, r:int, terrain:String ("plain"|"forest"|"hills"|"water"|"mountain"),
##    kind:String ("plain"|"farm"|"mine"|"city"|"capital"|"military_base"|"port"),
##    value:int (hex_value 1..10), owner:int (official owner, changes by treaty),
##    controller:int (actual controller, changes during war), fort:int (0..10), name:String (translation key, "" = none)}
## StateInfo (Dictionary):
##   {id:int, name:String (translation key), color:int (0xRRGGBB), archetype:String, capital_id:int, dev_level:int}

const FX := 1000

const NOBODY := 0
const PLAYER := 1

## M_силы by dev level (canon §6.2)
const STRENGTH_MULT: Array[float] = [0.0, 1.0, 1.25, 1.55, 1.9, 2.35, 2.9, 3.6, 4.4, 5.4, 6.6]

const KIND_VALUE := {
	"plain": 1,
	"farm": 2,
	"mine": 2,
	"port": 3,
	"military_base": 3,
	"city": 4,
	"capital": 10,
	"raivite_vein": 5,  # 2 Raivites every 12 h, holds up to 4 (canon §5.1)
	"dark_lake": 1,  # dormant oil in chapters I–II
	"oil": 3,  # 25 oil/h from DL5
	"factory": 4,  # 10 metal/h, −5% build and training timers each (max −30%), asleep before DL5 (canon §5.1)
}


static func is_passable(c: Dictionary) -> bool:
	return c["terrain"] != "water" and c["terrain"] != "mountain"


## M_силы for a dev level, 1.0 when out of range (TS: STRENGTH_MULT[dl] ?? 1).
static func strength_mult(dev_level: int) -> float:
	if dev_level >= 0 and dev_level < STRENGTH_MULT.size():
		return STRENGTH_MULT[dev_level]
	return 1.0


## JavaScript Math.round semantics: nearest integer, ties toward +infinity.
static func js_round(x: float) -> int:
	var f := floorf(x)
	if x - f >= 0.5:
		return int(f) + 1
	return int(f)


## Rounds to one decimal like the TS round1 helper: Math.round(x * 10) / 10.
static func round1(x: float) -> float:
	return float(js_round(x * 10.0)) / 10.0


## Stable in-place sort (JS Array.prototype.sort is stable; Godot's sort_custom is not).
## `cmp(a, b)` returns a number: < 0 keeps a before b, > 0 puts b first, 0 keeps the input order.
static func stable_sort(arr: Array, cmp: Callable) -> Array:
	for i in range(1, arr.size()):
		var x: Variant = arr[i]
		var j := i - 1
		while j >= 0 and cmp.call(arr[j], x) > 0:
			arr[j + 1] = arr[j]
			j -= 1
		arr[j + 1] = x
	return arr
