extends RefCounted
## xoshiro128** — seeded deterministic PRNG (canon §16.1), port of packages/sim/src/rng.ts.
## Bit-identical to the TS version: all state is kept as unsigned 32-bit values in 64-bit ints.

const MASK := 0xFFFFFFFF

var s0: int
var s1: int
var s2: int
var s3: int
var _x: int


func _init(seed_value: int) -> void:
	# splitmix32 to spread the seed over the state
	_x = seed_value & MASK
	s0 = _splitmix_next()
	s1 = _splitmix_next()
	s2 = _splitmix_next()
	s3 = _splitmix_next()


func _splitmix_next() -> int:
	_x = (_x + 0x9e3779b9) & MASK
	var z := _x
	z = _imul(z ^ (z >> 16), 0x85ebca6b)
	z = _imul(z ^ (z >> 13), 0xc2b2ae35)
	return (z ^ (z >> 16)) & MASK


func next_u32() -> int:
	var result := _imul(_rotl(_imul(s1, 5), 7), 9)
	var t := (s1 << 9) & MASK
	s2 = (s2 ^ s0) & MASK
	s3 = (s3 ^ s1) & MASK
	s1 = (s1 ^ s2) & MASK
	s0 = (s0 ^ s3) & MASK
	s2 = (s2 ^ t) & MASK
	s3 = _rotl(s3, 11)
	return result


## Integer in [0, n).
func next_int(n: int) -> int:
	return next_u32() % n


func pick(arr: Array) -> Variant:
	return arr[next_int(arr.size())]


## Fisher–Yates in place (same draw order as the TS version); returns `arr`.
func shuffle(arr: Array) -> Array:
	var i := arr.size() - 1
	while i > 0:
		var j := next_int(i + 1)
		var tmp: Variant = arr[i]
		arr[i] = arr[j]
		arr[j] = tmp
		i -= 1
	return arr


## Math.imul(a, b) >>> 0 without overflowing 64-bit ints.
static func _imul(a: int, b: int) -> int:
	a &= MASK
	b &= MASK
	var lo := a * (b & 0xFFFF)
	var hi := ((a * (b >> 16)) & 0xFFFF) << 16
	return (lo + hi) & MASK


static func _rotl(x: int, k: int) -> int:
	x &= MASK
	return ((x << k) & MASK) | (x >> (32 - k))
