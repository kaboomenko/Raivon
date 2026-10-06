extends RefCounted
## World container (port of the World interface in packages/sim/src/types.ts).
## cells[i]["id"] == i. Cell / StateInfo layouts are documented in types.gd.

var map_seed: int = 0
var radius: int = 0
var cells: Array[Dictionary] = []
## neighbors[id][dir] = neighbor cell id or -1 (off-map); dir order = HexGrid.DIRS.
var neighbors: Array[PackedInt32Array] = []
## "q,r" -> cell id
var by_key: Dictionary = {}
## Indexed by StateId (0 = nobody/wild, 1 = player, 2 = Barons, 3 = Hamlets).
var states: Array[Dictionary] = []
## River edges (canon §5.1: a river runs along hex edges, attacks across it −25%): "a:b" (a < b) -> true.
var rivers: Dictionary = {}
## AI states allied with the player (canon §10.7): their land is open to the player's marches. state id -> true.
var player_allies: Dictionary = {}


static func edge_key(a: int, b: int) -> String:
	return "%d:%d" % [mini(a, b), maxi(a, b)]


func is_river(a: int, b: int) -> bool:
	return not rivers.is_empty() and rivers.has(edge_key(a, b))


func cell(id: int) -> Dictionary:
	return cells[id]


## Cell id at axial (q, r) or -1.
func id_at(q: int, r: int) -> int:
	return by_key.get("%d,%d" % [q, r], -1)
