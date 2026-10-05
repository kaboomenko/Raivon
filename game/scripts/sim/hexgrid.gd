extends RefCounted
## Axial hex coordinates, flat-top orientation (port of packages/sim/src/hex.ts).
## Axial coords are Vector2i(q, r). Screen: x grows with q, y grows with r (+ q/2).

## Order matters for edge indexing: edge i of a hex is shared with neighbor DIRS[i].
const DIRS: Array[Vector2i] = [
	Vector2i(1, 0), # 0: lower-right
	Vector2i(1, -1), # 1: upper-right
	Vector2i(0, -1), # 2: up
	Vector2i(-1, 0), # 3: upper-left
	Vector2i(-1, 1), # 4: lower-left
	Vector2i(0, 1), # 5: down
]


static func hex_key(q: int, r: int) -> String:
	return "%d,%d" % [q, r]


static func distance(a: Vector2i, b: Vector2i) -> int:
	var dq := a.x - b.x
	var dr := a.y - b.y
	return (absi(dq) + absi(dr) + absi(dq + dr)) / 2


## Axial coordinate of a cell Dictionary ({q, r, ...}).
static func axial(c: Dictionary) -> Vector2i:
	return Vector2i(c["q"], c["r"])


static func neighbor_of(h: Vector2i, dir: int) -> Vector2i:
	return h + DIRS[dir]


static func disk(radius: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for q in range(-radius, radius + 1):
		var r1 := maxi(-radius, -q - radius)
		var r2 := mini(radius, -q + radius)
		for r in range(r1, r2 + 1):
			out.append(Vector2i(q, r))
	return out


## Direction index from a to an adjacent b, or -1.
static func dir_to(a: Vector2i, b: Vector2i) -> int:
	for i in 6:
		if a + DIRS[i] == b:
			return i
	return -1
