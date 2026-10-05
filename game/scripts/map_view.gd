extends Node3D
## Renders the live sim world (scripts/sim): terrain, official territory with neon borders,
## occupation hatching, props per hex kind, armies with strength labels, battle FX and the
## peace-ceremony ink wave. Rebuilds territory meshes whenever ownership/control changes.

const Types := preload("res://scripts/sim/types.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")

const SQ3 := 1.7320508
const DIRS := [Vector2i(1, 0), Vector2i(1, -1), Vector2i(0, -1), Vector2i(-1, 0), Vector2i(-1, 1), Vector2i(0, 1)]

const C_PLAYER := Color(0.15, 0.5, 1.0)
const C_WAR := Color(1.0, 0.14, 0.1)
const C_WILD := Color(0.75, 0.72, 0.62)

var sim  # World (RefCounted)
var at_war_with := -1
var models := {}
var rng := RandomNumberGenerator.new()

# ceremony: hex id -> flip time (s); before flip the hex is drawn with prev_owner
var ceremony_t := -1.0
var flip_at := {}
var prev_owner := {}

var _terrain_mi: MeshInstance3D
var _overlay_root: Node3D
var _props_root: Node3D
var _horizon_root: Node3D
var _hex_props := {}
var _sails: Array = []  # windmill sail nodes, spun in _process  # hex id -> Node3D holder of that hex's props
var _army_nodes := {}  # army id -> Node3D
var _fx: Array = []
var _dirty := true
var _snapshot := ""


static func axial_to_world(q: int, r: int) -> Vector3:
	return Vector3(1.5 * q, 0.0, SQ3 * (r + q / 2.0))


func _ready() -> void:
	rng.seed = 7
	_overlay_root = Node3D.new()
	add_child(_overlay_root)
	_props_root = Node3D.new()
	add_child(_props_root)
	_horizon_root = Node3D.new()
	add_child(_horizon_root)


func set_world(w) -> void:
	sim = w
	for c in _horizon_root.get_children():
		c.queue_free()
	_build_terrain()
	refresh_props()
	rng.seed = 11
	_build_horizon()
	_dirty = true


func cell_world(id: int) -> Vector3:
	var c: Dictionary = sim.cells[id]
	return axial_to_world(c["q"], c["r"])


func id_at_world(p: Vector3) -> int:
	var q := p.x / 1.5
	var r := p.z / SQ3 - q / 2.0
	var s := -q - r
	var rq := roundf(q)
	var rr := roundf(r)
	var rs := roundf(s)
	if absf(rq - q) > absf(rr - r) and absf(rq - q) > absf(rs - s):
		rq = -rr - rs
	elif absf(rr - r) > absf(rs - s):
		rr = -rq - rs
	return sim.id_at(int(rq), int(rr))


func owner_of(c: Dictionary) -> int:
	var id: int = c["id"]
	if ceremony_t >= 0.0 and flip_at.has(id) and ceremony_t < flip_at[id]:
		return prev_owner[id]
	return c["owner"]


func state_color(s: int) -> Color:
	if s == Types.PLAYER:
		return C_PLAYER
	if s == Types.NOBODY:
		return C_WILD
	if s == at_war_with or s == MapGen.BARONS:  # the Barons are the hostile neighbour: always red
		return C_WAR
	return Color.hex((int(sim.states[s]["color"]) << 8) | 0xff)


## Models load on first use (there are ~150 of them across all development levels).
func has_model(name: String) -> bool:
	return models.has(name) or ResourceLoader.exists("res://assets/models/%s.glb" % name)


func spawn(name: String, parent: Node, pos: Vector3, rot := 0.0, s := 1.0) -> Node3D:
	if not models.has(name):
		if not ResourceLoader.exists("res://assets/models/%s.glb" % name):
			return null
		models[name] = load("res://assets/models/%s.glb" % name)
	var n: Node3D = models[name].instantiate()
	n.position = pos
	n.rotation.y = rot
	n.scale = Vector3.ONE * s
	parent.add_child(n)
	if name == "windmill":
		var sails := n.get_node_or_null("sails")
		if sails:
			_sails.append(sails)
	return n


# ------------------------------------------------------------------ static terrain

func _hex_pts(center: Vector3, radius: float) -> Array:
	var pts := []
	for k in 6:
		var a := PI / 3.0 * k
		pts.append(center + Vector3(radius * cos(a), 0, radius * sin(a)))
	return pts


func _build_terrain() -> void:
	if _terrain_mi:
		_terrain_mi.queue_free()
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for c in sim.cells:
		var center := axial_to_world(c["q"], c["r"])
		var top := 0.0
		var col := Color(0.29, 0.52, 0.18)
		match c["terrain"]:
			"forest":
				col = Color(0.22, 0.44, 0.16)
			"hills":
				col = Color(0.48, 0.5, 0.26)
			"mountain":
				col = Color(0.42, 0.4, 0.36)
			"water":
				col = Color(0.12, 0.36, 0.52)
				top = -0.2
		col = col * (0.94 + rng.randf() * 0.12)
		col.a = 1.0
		var pts := _hex_pts(center + Vector3(0, top, 0), 0.995)
		for k in 6:
			st.set_color(col)
			st.set_normal(Vector3.UP)
			st.add_vertex(center + Vector3(0, top, 0))
			st.add_vertex(pts[k])
			st.add_vertex(pts[(k + 1) % 6])
		var side := col.darkened(0.45)
		for k in 6:
			var a: Vector3 = pts[k]
			var b: Vector3 = pts[(k + 1) % 6]
			var n := ((a + b) / 2.0 - center).normalized()
			st.set_color(side)
			st.set_normal(n)
			st.add_vertex(a); st.add_vertex(b + Vector3(0, -1.4, 0)); st.add_vertex(b)
			st.add_vertex(a); st.add_vertex(a + Vector3(0, -1.4, 0)); st.add_vertex(b + Vector3(0, -1.4, 0))
	_terrain_mi = MeshInstance3D.new()
	_terrain_mi.mesh = st.commit()
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/terrain.gdshader")
	mat.set_shader_parameter("noise_big", _noise_tex(0.9, 3, 101))
	mat.set_shader_parameter("noise_fine", _noise_tex(6.0, 2, 202))
	_terrain_mi.material_override = mat
	add_child(_terrain_mi)
	var water := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(90, 90)
	water.mesh = plane
	water.position = Vector3(0, -0.25, 0)
	var wm := StandardMaterial3D.new()
	wm.albedo_color = Color(0.07, 0.27, 0.42)
	wm.metallic = 0.3
	wm.roughness = 0.12
	water.material_override = wm
	add_child(water)


func _noise_tex(freq: float, octaves: int, seed_: int) -> NoiseTexture2D:
	var n := FastNoiseLite.new()
	n.seed = seed_
	n.frequency = freq / 64.0
	n.fractal_octaves = octaves
	var t := NoiseTexture2D.new()
	t.width = 256
	t.height = 256
	t.seamless = true
	t.generate_mipmaps = true
	t.noise = n
	return t


# ------------------------------------------------------------------ props per hex

func _faction_suffix(s: int) -> String:
	if s == Types.PLAYER:
		return "blue"
	if s == MapGen.HAMLETS or s == 4:  # Hamlets, River League
		return "green"
	return "red"


## Re-spawns buildings, trees and banners (after a treaty or colonization changes owners).
## Each cell has its own seed, so trees stay where they were.
func refresh_props() -> void:
	for c in _props_root.get_children():
		c.queue_free()
	_place_props()


func _place_props() -> void:
	_hex_props.clear()
	for c in sim.cells:
		_place_hex_props(c)


## Rebuilds one hex's props in its current owner's style (the ceremony flips them one by one).
func refresh_hex(id: int, neighbours := true) -> void:
	var old: Node3D = _hex_props.get(id)
	if old:
		old.queue_free()
	_place_hex_props(sim.cells[id])
	if neighbours:
		# forts next door draw walls only towards foreign land: their outer edges may have changed
		for n in sim.neighbors[id]:
			if n >= 0 and int(sim.cells[n]["fort"]) > 0:
				refresh_hex(n, false)


## Ceremony «pop»: the hex's buildings jump to 1.08 and settle back.
func pop_hex(id: int) -> void:
	var holder: Node3D = _hex_props.get(id)
	if holder == null:
		return
	holder.scale = Vector3.ONE * 1.12
	var tw := create_tween()
	tw.tween_property(holder, "scale", Vector3.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


## Model name for `kind` ("city", "residence") in the style of the owner's development level
## (canon §6: every DL changes how the state looks); falls back to lower levels, "" if none exist.
func evolved(kind: String, owner: int) -> String:
	if owner <= Types.NOBODY or owner >= sim.states.size():
		return ""
	var dl: int = clampi(int(sim.states[owner]["dev_level"]), 1, 10)
	var side := _faction_suffix(owner)
	for n in range(dl, 0, -1):
		var name := "%s_dl%d_%s" % [kind, n, side]
		if has_model(name):
			return name
	return ""


## Fortification around the hex edge by its own level (canon §6.1: forts look like their level).
func _place_fort(c: Dictionary, holder: Node3D) -> void:
	_place_tower(c, holder)
	var lvl: int = c["fort"]
	if lvl <= 0:
		return
	for n in range(mini(lvl, 8), 0, -1):
		if has_model("fort_l%d_edge" % n) and has_model("fort_l%d_post" % n):
			_place_fort_edges(c, holder, n)
			return
		if has_model("fort_l%d" % n):
			spawn("fort_l%d" % n, holder, Vector3.ZERO, 0.0, 1.0)
			return


## Walls only on the edges that face foreign or wild land (canon §7), corner posts where those walls meet.
## An inner fort (every neighbour is ours) shows just its corner posts, so it stays visible.
func _place_fort_edges(c: Dictionary, holder: Node3D, n: int) -> void:
	var own: int = c["owner"]
	var corners := {}  # corner index 0..5 (angle k·60°) -> true
	var outer := 0
	for i in 6:
		var d: Vector2i = HexGrid.DIRS[i]
		var nid: int = sim.id_at(int(c["q"]) + d.x, int(c["r"]) + d.y)
		if nid >= 0 and int(sim.cells[nid]["owner"]) == own:
			continue
		outer += 1
		var dv := axial_to_world(int(c["q"]) + d.x, int(c["r"]) + d.y) - axial_to_world(int(c["q"]), int(c["r"]))
		var ang := atan2(-dv.z, dv.x)  # Blender angle of the edge normal (Godot −Z is Blender +Y)
		spawn("fort_l%d_edge" % n, holder, Vector3.ZERO, ang - PI / 2.0, 1.0)  # the edge piece faces 90°
		var k := posmod(roundi(rad_to_deg(ang) / 60.0 - 0.5), 6)  # corners at normal ± 30°
		corners[k] = true
		corners[(k + 1) % 6] = true
	if outer == 0:
		for k in 6:
			corners[k] = true
	for k in corners:
		spawn("fort_l%d_post" % n, holder, Vector3.ZERO, int(k) * PI / 3.0, 1.0)


func _place_camp(hex: int, holder: Node3D) -> void:
	if has_model("raider_camp"):
		spawn("raider_camp", holder, Vector3.ZERO, rng.randf_range(-0.4, 0.4), 1.0)
		_camp_icon(hex, holder)
		return
	for o in [Vector3(-0.28, 0, 0.12), Vector3(0.3, 0, 0.05), Vector3(0.0, 0, -0.32)]:
		var t := spawn("tent_red", holder, o, rng.randf() * TAU, 0.85)
		if t:
			_tint(t, Color(0.62, 0.6, 0.56))
	for i in 9:
		var a := TAU * i / 9.0
		var post := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.025
		cm.bottom_radius = 0.035
		cm.height = 0.26
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(0.42, 0.3, 0.2)
		cm.material = m
		post.mesh = cm
		post.position = Vector3(cos(a) * 0.62, 0.13, sin(a) * 0.62)
		post.rotation.z = 0.15 * sin(a * 3.0)
		holder.add_child(post)
	_camp_icon(hex, holder)


## Rotation that turns a port model's water inlet (+X in the model) toward the hex's water neighbour.
func _water_side(c: Dictionary) -> float:
	for i in 6:
		var d: Vector2i = HexGrid.DIRS[i]
		var nid: int = sim.id_at(int(c["q"]) + d.x, int(c["r"]) + d.y)
		if nid >= 0 and sim.cells[nid]["terrain"] == "water":
			var dv := axial_to_world(int(c["q"]) + d.x, int(c["r"]) + d.y) - axial_to_world(int(c["q"]), int(c["r"]))
			return atan2(-dv.z, dv.x)  # Blender +X rotated onto the neighbour direction
	return 0.0


func _camp_icon(hex: int, holder: Node3D) -> void:
	var icon := Sprite3D.new()
	var res: String = camp_hexes[hex]
	icon.texture = load("res://assets/ui/%s.png" % {"gold": "coin", "food": "food", "metal": "metal"}.get(res, "coin"))
	icon.pixel_size = 0.0035
	icon.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	icon.no_depth_test = true
	icon.position = Vector3(0, 1.05, 0)
	holder.add_child(icon)


## Greys out an imported model (camp tents are the red tent recoloured).
func _tint(n: Node, col: Color) -> void:
	if n is MeshInstance3D:
		var mi: MeshInstance3D = n
		var m := StandardMaterial3D.new()
		m.albedo_color = col
		mi.material_override = m
	for ch in n.get_children():
		_tint(ch, col)


## Defensive tower (canon §7): stands at the back of the hex, grows a little with its level.
func _place_tower(c: Dictionary, holder: Node3D) -> void:
	var lvl: int = int(c.get("tower", 0))
	if lvl <= 0:
		return
	# its own look per level (canon §6.1): slinger lookout → archer tower → ballista … → laser turret
	for n in range(mini(lvl, 8), 0, -1):
		if has_model("tower_l%d" % n):
			spawn("tower_l%d" % n, holder, Vector3(0.42, 0, -0.36), 0.0, 1.35)
			return
	if has_model("watchtower"):
		spawn("watchtower", holder, Vector3(0.38, 0, -0.32), 0.6, 1.0 + 0.06 * (lvl - 1))


func _place_hex_props(c: Dictionary) -> void:
	var holder := Node3D.new()
	holder.position = cell_world(c["id"])
	_props_root.add_child(holder)
	_hex_props[c["id"]] = holder
	_place_hex_props_into(c, holder)


func _place_hex_props_into(c: Dictionary, holder: Node3D) -> void:
	rng.seed = 7 + int(c["id"]) * 7919
	if camp_hexes.has(int(c["id"])):
		_place_camp(int(c["id"]), holder)
		return
	if not Types.is_passable(c):
		if c["terrain"] == "mountain":
			spawn("mountain", holder, Vector3.ZERO, rng.randf() * TAU, rng.randf_range(1.2, 1.6))
		return
	var p := Vector3.ZERO
	var side := _faction_suffix(c["owner"])
	match c["kind"]:
		"capital":
			var rm := evolved("residence", c["owner"])
			if rm != "":
				var early := rm.contains("_dl1_") or rm.contains("_dl2_") or rm.contains("_dl3_")
				spawn(rm, holder, p, 0.3 if c["owner"] == Types.PLAYER else PI, 1.3 if early else 1.0)  # small early buildings fill the hex
			else:
				var model := "castle" if c["owner"] == Types.PLAYER else ("castle_green" if c["owner"] == MapGen.HAMLETS else "castle_red")
				spawn(model, holder, p, 0.3 if c["owner"] == Types.PLAYER else PI, 1.35)
			_place_fort(c, holder)
			return
		"city":
			var cm := evolved("city", c["owner"])
			if cm != "":
				spawn(cm, holder, p, rng.randf_range(-0.25, 0.25), 1.15)  # tall towers stay at the back
			else:
				var hm := "house_blue" if c["owner"] == Types.PLAYER else ("house_green" if c["owner"] == MapGen.HAMLETS else "house_red")
				for o in [Vector3(-0.3, 0, 0.15), Vector3(0.3, 0, -0.25), Vector3(0.1, 0, 0.4), Vector3(-0.25, 0, -0.35)]:
					spawn(hm, holder, p + o, rng.randf() * TAU, 1.05)
			_place_fort(c, holder)
			return
		"farm":
			spawn("wheat_field", holder, p + Vector3(0.1, 0, 0.1), 0.0, 0.95)
			spawn("windmill", holder, p + Vector3(-0.45, 0, -0.3), 0.4, 0.95)
			return
		"mine":
			spawn("mine", holder, p, 0.2, 1.1)
			return
		"port":
			if has_model("port"):
				spawn("port", holder, p, _water_side(c), 1.0)
				_place_fort(c, holder)
				return
		"military_base":
			if has_model("military_base"):
				spawn("military_base", holder, p, 0.3, 1.0)
				_place_fort(c, holder)
				return
	match c["terrain"]:
		"forest":
			for i in rng.randi_range(8, 12):
				var off := Vector3(rng.randf_range(-0.62, 0.62), 0, rng.randf_range(-0.62, 0.62))
				spawn("tree_pine" if rng.randf() < 0.75 else "tree_round", holder, p + off, rng.randf() * TAU, rng.randf_range(0.85, 1.3))
			for i in rng.randi_range(1, 2):
				spawn("bush", holder, p + Vector3(rng.randf_range(-0.6, 0.6), 0, rng.randf_range(-0.6, 0.6)), rng.randf() * TAU, rng.randf_range(1.0, 1.25))
		"hills":
			for i in 3:
				spawn("rock", holder, p + Vector3(rng.randf_range(-0.5, 0.5), 0, rng.randf_range(-0.5, 0.5)), rng.randf() * TAU, rng.randf_range(1.2, 2.0))
			spawn("tree_pine", holder, p + Vector3(0.3, 0, 0.3), 0.0, 1.0)
		_:
			for i in rng.randi_range(1, 4):
				var off := Vector3(rng.randf_range(-0.6, 0.6), 0, rng.randf_range(-0.6, 0.6))
				spawn("tree_pine" if rng.randf() < 0.6 else "tree_round", holder, p + off, rng.randf() * TAU, rng.randf_range(0.7, 1.0))
			if rng.randf() < 0.55:
				spawn("bush", holder, p + Vector3(rng.randf_range(-0.55, 0.55), 0, rng.randf_range(-0.55, 0.55)), rng.randf() * TAU, rng.randf_range(1.0, 1.3))
			if rng.randf() < 0.45:
				spawn("flowers", holder, p + Vector3(rng.randf_range(-0.5, 0.5), 0, rng.randf_range(-0.5, 0.5)), rng.randf() * TAU, rng.randf_range(1.0, 1.3))
	_place_fort(c, holder)
	if c["owner"] != Types.NOBODY and rng.randf() < 0.3:
		spawn("banner_" + side, holder, p + Vector3(rng.randf_range(-0.4, 0.4), 0, rng.randf_range(-0.4, 0.4)))


func _build_horizon() -> void:
	var ring_mat := StandardMaterial3D.new()
	ring_mat.albedo_color = Color(0.18, 0.22, 0.2)
	var rr: int = maxi(4, int(sim.radius))  # the horizon ring sits around the open world (grows by chapter)
	for q in range(-rr - 5, rr + 6):
		for r in range(-rr - 5, rr + 6):
			if abs(q + r) > rr + 5 or sim.id_at(q, r) >= 0:
				continue
			var d: int = (absi(q) + absi(r) + absi(q + r)) / 2
			if d > rr + 4:
				continue
			var p := axial_to_world(q, r)
			var roll := rng.randf()
			var near := p.z > 3.0  # bottom of the screen: keep low so it never hides the player's land
			if near:
				for i in 3:
					spawn("tree_pine" if rng.randf() < 0.7 else "tree_round", _horizon_root, p + Vector3(rng.randf_range(-0.7, 0.7), -0.1, rng.randf_range(-0.7, 0.7)), rng.randf() * TAU, rng.randf_range(0.8, 1.1))
			elif d <= rr + 2 and roll < 0.5:
				spawn("mountain", _horizon_root, p + Vector3(0, -0.15, 0), rng.randf() * TAU, rng.randf_range(1.7, 2.8))
			elif d <= rr + 2:
				for i in 5:
					spawn("tree_pine", _horizon_root, p + Vector3(rng.randf_range(-0.7, 0.7), -0.1, rng.randf_range(-0.7, 0.7)), rng.randf() * TAU, rng.randf_range(0.9, 1.4))
			var base := MeshInstance3D.new()
			var cm := CylinderMesh.new()
			cm.top_radius = 1.0
			cm.bottom_radius = 1.0
			cm.height = 1.0
			cm.radial_segments = 6
			base.mesh = cm
			base.position = p + Vector3(0, -0.62, 0)
			base.material_override = ring_mat
			_horizon_root.add_child(base)
			if not near and rng.randf() < 0.55 + 0.1 * (d - rr - 1):
				_cloud(p + Vector3(rng.randf_range(-0.5, 0.5), rng.randf_range(1.0, 2.6), rng.randf_range(-0.5, 0.5)), rng.randf_range(3.5, 6.0))


var _cloud_mat: StandardMaterial3D

func _cloud(pos: Vector3, size: float) -> void:
	if _cloud_mat == null:
		var tex := GradientTexture2D.new()
		var g := Gradient.new()
		g.set_color(0, Color(1, 1, 1, 0.92))
		g.set_color(1, Color(1, 1, 1, 0.0))
		tex.gradient = g
		tex.fill = GradientTexture2D.FILL_RADIAL
		tex.fill_from = Vector2(0.5, 0.5)
		tex.fill_to = Vector2(0.5, 0.0)
		_cloud_mat = StandardMaterial3D.new()
		_cloud_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_cloud_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_cloud_mat.albedo_texture = tex
		_cloud_mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
		_cloud_mat.albedo_color = Color(0.9, 0.92, 0.95, 0.85)
	var q := QuadMesh.new()
	q.size = Vector2(size, size * 0.6)
	var mi := MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = _cloud_mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = pos
	_horizon_root.add_child(mi)


# ------------------------------------------------------------------ territory overlay (rebuilt on change)

func mark_dirty() -> void:
	_dirty = true


func _territory_snapshot() -> String:
	var parts := PackedStringArray()
	for c in sim.cells:
		parts.append("%d%d%d" % [owner_of(c), c["controller"], 1 if ceremony_t >= 0.0 else 0])
	return ",".join(parts) + str(at_war_with)


func _rebuild_overlay() -> void:
	for n in _overlay_root.get_children():
		n.queue_free()
	var tints := {}
	var hatch := {}
	var lines := {}
	var borders := {}
	for c in sim.cells:
		if not Types.is_passable(c):
			continue
		var own := owner_of(c)
		var center := cell_world(c["id"]) + Vector3(0, 0.03, 0)
		var pts := _hex_pts(center, 0.995)
		if own != Types.NOBODY:
			var st: SurfaceTool = tints.get(own)
			if st == null:
				st = SurfaceTool.new()
				st.begin(Mesh.PRIMITIVE_TRIANGLES)
				tints[own] = st
			# inner-glow look of the references: faint in the middle, saturated at the rim
			var tc := state_color(own)
			var base := 0.2 if own == Types.PLAYER else 0.34
			var c_in := Color(tc.r, tc.g, tc.b, base * 0.45)
			var c_rim := Color(tc.r, tc.g, tc.b, base * 1.45)
			for k in 6:
				st.set_color(c_in); st.add_vertex(center)
				st.set_color(c_rim); st.add_vertex(pts[k])
				st.set_color(c_rim); st.add_vertex(pts[(k + 1) % 6])
		# occupation hatch in the occupier colour (canon §3.1)
		if c["controller"] != own and c["controller"] != Types.NOBODY:
			var hs: SurfaceTool = hatch.get(c["controller"])
			if hs == null:
				hs = SurfaceTool.new()
				hs.begin(Mesh.PRIMITIVE_TRIANGLES)
				hatch[c["controller"]] = hs
			var hc := center + Vector3(0, 0.01, 0)
			var hp := _hex_pts(hc, 0.96)
			for k in 6:
				hs.add_vertex(hc); hs.add_vertex(hp[k]); hs.add_vertex(hp[(k + 1) % 6])
		for d in 6:
			var n: int = sim.neighbors[c["id"]][d]
			var other := -1
			if n >= 0 and Types.is_passable(sim.cells[n]):
				other = owner_of(sim.cells[n])
			if own == Types.NOBODY:
				continue
			var e := _edge_pts(center, n, d)
			if other == own:
				_strip(_st(lines, own), e[0], e[1], 0.035, center.y + 0.005)
			else:
				var w := 0.12
				var prog := 1.0
				if ceremony_t >= 0.0 and flip_at.has(c["id"]):
					prog = clampf((ceremony_t - flip_at[c["id"]]) / 0.3, 0.0, 1.0)
				if prog > 0.0:
					_strip(_st(borders, own), e[0], e[0].lerp(e[1], prog), w, center.y + 0.012)
	for o in tints:
		_add(tints[o], _tint_mat(Color.WHITE, 1.0))
	for o in hatch:
		_add(hatch[o], _hatch_mat(state_color(o)))
	for o in lines:
		_add(lines[o], _glow_mat(state_color(o), 0.8, 0.65))
	for o in borders:
		var e := 4.5 if (o == Types.PLAYER or o == at_war_with) else 2.0
		_add(borders[o], _glow_mat(state_color(o), e, 1.0))


func _st(dict: Dictionary, key: int) -> SurfaceTool:
	var st: SurfaceTool = dict.get(key)
	if st == null:
		st = SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		dict[key] = st
	return st


func _edge_pts(center: Vector3, n: int, d: int) -> Array:
	var nc := center + Vector3(1.5 * DIRS[d].x, 0, SQ3 * (DIRS[d].y + DIRS[d].x / 2.0))
	var pts := _hex_pts(center, 0.965)
	pts.sort_custom(func(a, b): return a.distance_to(nc) < b.distance_to(nc))
	return [pts[0], pts[1]]


func _strip(st: SurfaceTool, a: Vector3, b: Vector3, w: float, y: float) -> void:
	if a.distance_to(b) < 0.001:
		return
	var dir := (b - a).normalized()
	var n := Vector3(-dir.z, 0, dir.x) * w * 0.5
	a.y = y
	b.y = y
	var a0 := a - dir * w * 0.5
	var b0 := b + dir * w * 0.5
	st.add_vertex(a0 - n); st.add_vertex(b0 - n); st.add_vertex(b0 + n)
	st.add_vertex(a0 - n); st.add_vertex(b0 + n); st.add_vertex(a0 + n)


func _add(st: SurfaceTool, m: Material) -> void:
	st.generate_normals()
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_overlay_root.add_child(mi)


func _tint_mat(c: Color, alpha: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(c.r, c.g, c.b, alpha)
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.roughness = 0.9
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m


func _glow_mat(c: Color, energy: float, alpha: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0, 0, 0, alpha)
	if alpha < 1.0:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.emission_enabled = true
	m.emission = c
	m.emission_energy_multiplier = energy
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m


var _hatch_shader: Shader

func _hatch_mat(c: Color) -> ShaderMaterial:
	if _hatch_shader == null:
		_hatch_shader = Shader.new()
		_hatch_shader.code = """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled;
uniform vec4 col : source_color;
varying vec3 wp;
void vertex() { wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	float s = step(0.55, fract((wp.x + wp.z) * 2.6));
	ALBEDO = col.rgb * 1.6;
	ALPHA = s * 0.7;
}
"""
	var m := ShaderMaterial.new()
	m.shader = _hatch_shader
	m.set_shader_parameter("col", c)
	return m


# ------------------------------------------------------------------ armies

func sync_armies(armies: Array, battle) -> void:
	var t := Time.get_ticks_msec() / 1000.0
	var cam := get_viewport().get_camera_3d()
	# who is fighting where (canon §9.5: clashes on a target hex)
	var fighting := {}  # army id -> target hex (attackers) or -2 (defender)
	var live_clashes := {}
	if battle != null:
		for cl in battle.clashes:
			for aid in cl["attackers"]:
				fighting[aid] = cl["target"] if cl["entering"] == 0 else -3
			if cl["defender"] >= 0:
				fighting[cl["defender"]] = -2
			if cl["entering"] == 0 and cl["attackers"].size() > 0:
				var a0 = battle.army_by_id(cl["attackers"][0])
				if a0 != null:
					live_clashes[cl["id"]] = cell_world(a0["hex"]).lerp(cell_world(cl["target"]), 0.5)
					_clash_dst[cl["id"]] = cell_world(cl["target"])
	_sync_clash_fx(live_clashes)
	var alive := {}
	for a in armies:
		if a["str"] <= 0:
			continue
		var id: int = a["id"]
		alive[id] = true
		var node: Node3D = _army_nodes.get(id)
		var dl: int = int(sim.states[a["side"]]["dev_level"]) if a["side"] < sim.states.size() else 1
		if node != null and int(node.get_meta("dl", dl)) != dl:
			var keep := node.position
			node.queue_free()
			node = _make_army(a)
			node.position = keep
			_army_nodes[id] = node
		if node == null:
			node = _make_army(a)
			_army_nodes[id] = node
		var p := cell_world(a["hex"])
		var model: Node3D = node.get_node("model")
		var hop := 0.0
		var sway := 0.0
		var face_to := Vector3.ZERO
		var mv: Dictionary = a.get("march_vis", {}) if typeof(a.get("march_vis")) == TYPE_DICTIONARY else {}
		if battle == null and not mv.is_empty():
			var mto := cell_world(int(mv["to"]))
			p = p.lerp(mto, float(mv["f"]))  # strategic march, 20–40 s per hex (canon §8.1)
			hop = absf(sin(t * 8.0 + id)) * 0.06
			face_to = mto - cell_world(a["hex"])
		elif a["move"] != null:
			var to := cell_world(a["move"]["to"])
			p = p.lerp(to, 1.0 - float(a["move"]["left"]) / 15.0)
			hop = absf(sin(t * 11.0 + id)) * 0.07  # marching
			face_to = to - cell_world(a["hex"])
		elif fighting.has(id) and int(fighting[id]) >= 0:
			var tgt := cell_world(int(fighting[id]))
			p = p.lerp(tgt, 0.36)  # pressed against the enemy line
			hop = absf(sin(t * 9.0 + id * 1.7)) * 0.05
			sway = sin(t * 13.0 + id) * 0.09
			face_to = tgt - cell_world(a["hex"])
		elif fighting.has(id) and int(fighting[id]) == -3:
			hop = absf(sin(t * 11.0 + id)) * 0.06  # advancing into the clash
		elif fighting.has(id):
			sway = sin(t * 12.0 + id) * 0.06  # holding against an attack
		node.position = node.position.lerp(p, 0.3) if node.position.distance_to(p) < 3.0 else p
		model.position.y = hop
		model.rotation.z = sway
		var ready := float(a["str"]) / maxf(1.0, float(a["max_str"]))
		var lbl: Label3D = node.get_node("label")
		lbl.text = str(int(round(a["str"] / 1000.0))) if not a["routed"] else "✖"
		lbl.modulate = Color(1, 1, 1) if ready >= 0.5 else Color(1.0, 0.75, 0.4)
		var bar: Node3D = node.get_node("bar")
		bar.visible = battle != null and not a["routed"]
		if cam:
			bar.global_basis = cam.global_basis
		var fill: MeshInstance3D = bar.get_node("fill")
		fill.scale.x = maxf(0.02, ready)
		fill.position.x = -0.32 * (1.0 - fill.scale.x)
		model.scale = Vector3.ONE * (0.8 if a["routed"] else 1.0)
		node.modulate_alpha = 0.45 if a["routed"] else 1.0
		# face the enemy (the clash target, or the enemy-controlled neighbours)
		if face_to == Vector3.ZERO:
			for n in sim.neighbors[a["hex"]]:
				if n >= 0 and sim.cells[n]["controller"] != a["side"] and Types.is_passable(sim.cells[n]) and sim.cells[n]["controller"] != Types.NOBODY:
					face_to += cell_world(n) - cell_world(a["hex"])
		if face_to.length() > 0.1:
			var want := atan2(face_to.x, face_to.z)  # models face +Z
			model.rotation.y = lerp_angle(model.rotation.y, want, 0.25)
	for id in _army_nodes.keys():
		if not alive.has(id):
			_army_nodes[id].queue_free()
			_army_nodes.erase(id)


var _clash_fx := {}  # clash id -> CPUParticles3D
var _clash_dst := {}  # clash id -> target hex position

var _volley_t := {}  # clash id -> seconds until the next volley
var _volleys: Array = []  # {node, from, to, t, dur}


## Arrow volleys arcing onto the clash target (canon §9 «бой виден»): 5 shafts per volley, every ~0.7 s.
## Arrows from a tower top onto an adjacent hex (battle event tower_hit).
func tower_volley(tower_hex: int, target_hex: int) -> void:
	_volley(cell_world(tower_hex) + Vector3(0.38, 1.0, -0.32), cell_world(target_hex))


func _volley(from: Vector3, to: Vector3) -> void:
	for i in 5:
		var shaft := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(0.022, 0.022, 0.2)
		shaft.mesh = bm
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.albedo_color = Color(0.25, 0.18, 0.1)
		shaft.material_override = m
		shaft.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(shaft)
		var jitter := Vector3(rng.randf_range(-0.25, 0.25), 0, rng.randf_range(-0.25, 0.25))
		_volleys.append({"node": shaft, "from": from + jitter * 0.5, "to": to + jitter, "t": -0.06 * i, "dur": 0.55})


func _step_volleys(delta: float) -> void:
	for v in _volleys.duplicate():
		v["t"] += delta
		var n: MeshInstance3D = v["node"]
		var k: float = clampf(float(v["t"]) / float(v["dur"]), 0.0, 1.0)
		n.visible = float(v["t"]) >= 0.0
		var a: Vector3 = v["from"]
		var b: Vector3 = v["to"]
		var p := a.lerp(b, k) + Vector3(0, 0.5 + 1.1 * sin(PI * k), 0)
		var p2 := a.lerp(b, minf(1.0, k + 0.03)) + Vector3(0, 0.5 + 1.1 * sin(PI * minf(1.0, k + 0.03)), 0)
		n.position = p
		if p2.distance_to(p) > 0.0001:
			n.look_at(p2, Vector3.UP)
		if k >= 1.0:
			n.queue_free()
			_volleys.erase(v)


func _sync_clash_fx(live: Dictionary) -> void:
	for cid in _clash_fx.keys():
		if not live.has(cid):
			var old: CPUParticles3D = _clash_fx[cid]
			old.emitting = false
			get_tree().create_timer(0.8).timeout.connect(old.queue_free)
			_clash_fx.erase(cid)
	for cid in live:
		var fx: CPUParticles3D = _clash_fx.get(cid)
		if fx == null:
			fx = _make_sparks()
			add_child(fx)
			_clash_fx[cid] = fx
		fx.position = live[cid] + Vector3(0, 0.35, 0)
		var vt: float = _volley_t.get(cid, 0.0) - get_process_delta_time()
		if vt <= 0.0:
			vt = 0.6 + rng.randf() * 0.3
			var mid: Vector3 = live[cid]
			_volley(mid + (mid - _clash_dst.get(cid, mid)).normalized() * 0.8, _clash_dst.get(cid, mid))
		_volley_t[cid] = vt


func _make_sparks() -> CPUParticles3D:
	var fx := CPUParticles3D.new()
	fx.amount = 28
	fx.lifetime = 0.55
	fx.randomness = 0.5
	fx.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	fx.emission_sphere_radius = 0.28
	fx.direction = Vector3.UP
	fx.spread = 70.0
	fx.initial_velocity_min = 1.2
	fx.initial_velocity_max = 2.6
	fx.gravity = Vector3(0, -7.0, 0)
	fx.scale_amount_min = 0.5
	fx.scale_amount_max = 1.2
	var g := Gradient.new()
	g.set_color(0, Color(1.0, 0.95, 0.6))
	g.set_color(1, Color(1.0, 0.35, 0.05, 0.0))
	fx.color_ramp = g
	var mesh := SphereMesh.new()
	mesh.radius = 0.025
	mesh.height = 0.05
	mesh.radial_segments = 4
	mesh.rings = 2
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.emission_enabled = true
	m.emission = Color(1.0, 0.6, 0.2)
	m.emission_energy_multiplier = 3.0
	mesh.material = m
	fx.mesh = mesh
	fx.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return fx


class ArmyNode extends Node3D:
	var modulate_alpha := 1.0


func _make_army(a: Dictionary) -> Node3D:
	var node := ArmyNode.new()
	add_child(node)
	var side := _faction_suffix(a["side"])
	var model := Node3D.new()
	model.name = "model"
	node.add_child(model)
	# troops look like their state's development level (canon §6.1); fall back to the base models
	var dl: int = int(sim.states[a["side"]]["dev_level"]) if a["side"] < sim.states.size() else 1
	node.set_meta("dl", dl)
	var squad := ""
	var assault := ""
	for n in range(dl, 0, -1):
		if squad == "" and has_model("squad_dl%d_%s" % [n, side]):
			squad = "squad_dl%d_%s" % [n, side]
		if assault == "" and has_model("assault_dl%d_%s" % [n, side]):
			assault = "assault_dl%d_%s" % [n, side]
	spawn(squad if squad != "" else "squad_" + side, model, Vector3(-0.15, 0, 0.05), 0.0, 1.15)
	if assault != "":
		spawn(assault, model, Vector3(0.32, 0, 0.25), 0.0, 1.25)
	elif dl >= 2 or squad == "":
		spawn("knight_" + ("blue" if side == "blue" else "red"), model, Vector3(0.32, 0, 0.25), 0.0, 1.25)
	spawn("banner_" + side, model, Vector3(0.05, 0, -0.35), 0.0, 0.9)
	var lbl := Label3D.new()
	lbl.name = "label"
	lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lbl.no_depth_test = true
	lbl.font_size = 64
	lbl.outline_size = 14
	lbl.pixel_size = 0.006
	lbl.position = Vector3(0, 1.15, 0)
	lbl.outline_modulate = Color(0.05, 0.1, 0.25) if side == "blue" else Color(0.3, 0.05, 0.05)
	node.add_child(lbl)
	var bar := Node3D.new()
	bar.name = "bar"
	bar.position = Vector3(0, 0.92, 0)
	node.add_child(bar)
	var team := Color(0.3, 0.62, 1.0) if side == "blue" else (Color(0.3, 0.8, 0.35) if side == "green" else Color(1.0, 0.25, 0.2))
	for part in [["bg", Color(0.03, 0.05, 0.1, 0.85), Vector2(0.7, 0.1), 0.0], ["fill", team, Vector2(0.64, 0.06), 0.002]]:
		var q := QuadMesh.new()
		q.size = part[2]
		var mi := MeshInstance3D.new()
		mi.name = part[0]
		mi.mesh = q
		mi.position.z = part[3]
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.albedo_color = part[1]
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.no_depth_test = true
		m.render_priority = 2 if part[0] == "fill" else 1
		mi.material_override = m
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		bar.add_child(mi)
	return node


# ------------------------------------------------------------------ FX

func burst(hex: int, color: Color, big := false) -> void:
	var p := cell_world(hex) + Vector3(0, 0.1, 0)
	var mi := MeshInstance3D.new()
	var tm := TorusMesh.new()
	tm.inner_radius = 0.8
	tm.outer_radius = 0.95
	tm.ring_segments = 6
	tm.rings = 24
	mi.mesh = tm
	mi.rotation.y = PI / 6
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0, 0, 0, 1)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = 6.0
	mi.material_override = m
	mi.position = p
	add_child(mi)
	_fx.append({"node": mi, "t": 0.0, "dur": 0.9 if big else 0.6, "big": big})


# ------------------------------------------------------------------ resource bubbles & hex labels

var _bubbles := {}  # hex -> Node3D
var _hex_labels := {}  # hex -> Label3D
var _tex_cache := {}


func _tex(name: String) -> Texture2D:
	if not _tex_cache.has(name):
		_tex_cache[name] = load("res://assets/ui/%s.png" % name)
	return _tex_cache[name]


## CoC-style bubbles over hexes with uncollected income: data = {hex: {"res": "gold", "amount": n}}.
func set_bubbles(data: Dictionary) -> void:
	for h in _bubbles.keys():
		if not data.has(h):
			_bubbles[h].queue_free()
			_bubbles.erase(h)
	for h in data:
		var node: Node3D = _bubbles.get(h)
		var icon_name: String = {"gold": "coin", "food": "food", "metal": "metal"}.get(data[h]["res"], "coin")
		if node == null:
			node = Node3D.new()
			node.position = cell_world(h) + Vector3(0, 2.0, 0)
			add_child(node)
			for part in [["bg", "bubble", 0.0046, 0], ["icon", icon_name, 0.0032, 1]]:
				var sp := Sprite3D.new()
				sp.name = part[0]
				sp.texture = _tex(part[1])
				sp.pixel_size = part[2]
				sp.billboard = BaseMaterial3D.BILLBOARD_ENABLED
				sp.no_depth_test = true
				sp.render_priority = 3 + part[3]
				sp.shaded = false
				node.add_child(sp)
			var lbl := Label3D.new()
			lbl.name = "amount"
			lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			lbl.no_depth_test = true
			lbl.render_priority = 5
			lbl.font_size = 44
			lbl.outline_size = 12
			lbl.pixel_size = 0.005
			lbl.position = Vector3(0, -0.42, 0)
			node.add_child(lbl)
			_bubbles[h] = node
		(node.get_node("icon") as Sprite3D).texture = _tex(icon_name)
		(node.get_node("amount") as Label3D).text = "+%d" % int(data[h]["amount"])


func has_bubble(hex: int) -> bool:
	return _bubbles.has(hex)


## Text floating over a hex (colonization timers); "" removes it.
var _march_paths := {}  # army id -> {"key": String, "node": Node3D}
var camp_hexes := {}  # hex -> resource shown over the tents (marauder camps, canon §5.1)


func camp_count() -> int:
	return camp_hexes.size()


## Marauder camps: grey tents, palisade, campfire smoke and the loot icon over them (02 §13.2).
func set_camps(active: Array) -> void:
	var now := {}
	for cm in active:
		now[int(cm["hex"])] = String(cm["res"])
	var changed: Array = []
	for h in camp_hexes:
		if not now.has(h):
			changed.append(h)
			clear_smoke(int(h))
	for h in now:
		if not camp_hexes.has(h) or camp_hexes[h] != now[h]:
			changed.append(h)
	camp_hexes = now
	for h in changed:
		refresh_hex(int(h), false)
		if camp_hexes.has(h):
			smoke(int(h), 1.0e9)


## Dotted routes of marching armies (canon §8.1: a march is visible on the map). `paths`: army id -> Array of
## hex ids from the army's hex to the destination. Dots are rebuilt only when a route changes.
func set_march_paths(paths: Dictionary) -> void:
	for id in _march_paths.keys():
		if not paths.has(id):
			(_march_paths[id]["node"] as Node3D).queue_free()
			_march_paths.erase(id)
	for id in paths:
		var hexes: Array = paths[id]
		var key := str(hexes)
		if _march_paths.has(id) and String(_march_paths[id]["key"]) == key:
			continue
		if _march_paths.has(id):
			(_march_paths[id]["node"] as Node3D).queue_free()
		var root := Node3D.new()
		add_child(root)
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = Color(0.75, 0.9, 1.0, 0.9)
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.no_depth_test = true
		var dot := CylinderMesh.new()
		dot.top_radius = 0.06
		dot.bottom_radius = 0.06
		dot.height = 0.02
		dot.material = mat
		for i in range(hexes.size() - 1):
			var a := cell_world(int(hexes[i]))
			var b := cell_world(int(hexes[i + 1]))
			for k in range(1, 5):
				var m := MeshInstance3D.new()
				m.mesh = dot
				m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				m.position = a.lerp(b, k / 5.0) + Vector3(0, 0.12, 0)
				root.add_child(m)
		var ring := MeshInstance3D.new()
		var tm := TorusMesh.new()
		tm.inner_radius = 0.28
		tm.outer_radius = 0.36
		tm.material = mat
		ring.mesh = tm
		ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		ring.position = cell_world(int(hexes.back())) + Vector3(0, 0.12, 0)
		root.add_child(ring)
		_march_paths[id] = {"key": key, "node": root}


func hex_label(hex: int, text: String, color := Color(1, 0.9, 0.5)) -> void:
	var l: Label3D = _hex_labels.get(hex)
	if text == "":
		if l:
			l.queue_free()
			_hex_labels.erase(hex)
		return
	if l == null:
		l = Label3D.new()
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.no_depth_test = true
		l.font_size = 52
		l.outline_size = 14
		l.pixel_size = 0.005
		l.position = cell_world(hex) + Vector3(0, 0.9, 0)
		add_child(l)
		_hex_labels[hex] = l
	l.text = text
	l.modulate = color


# ------------------------------------------------------------------ deposits & convoys (canon §5.2)

const C_DEPOSIT := Color(1.0, 0.82, 0.15)
var _dep_nodes := {}  # hex -> Node3D
var _carts := {}  # convoy id -> Node3D


## deposits: [{hex, res, ...}], convoys: [{id, hex, ...} + "phase": {phase, progress, left}].
func set_deposits(deposits: Array, convoys: Array) -> void:
	var seen := {}
	for d in deposits:
		var h: int = d["hex"]
		seen[h] = true
		if not _dep_nodes.has(h):
			_dep_nodes[h] = _make_deposit(h, String(d["res"]))
	for h in _dep_nodes.keys():
		if not seen.has(h):
			_dep_nodes[h].queue_free()
			_dep_nodes.erase(h)
	var cap := cell_world(sim.states[Types.PLAYER]["capital_id"])
	var live := {}
	for cv in convoys:
		var id: int = cv["id"]
		live[id] = true
		var cart: Node3D = _carts.get(id)
		if cart == null:
			cart = _make_cart()
			_carts[id] = cart
		var ph: Dictionary = cv["phase"]
		var target := cell_world(int(cv["hex"]))
		var p: Vector3
		match String(ph["phase"]):
			"out":
				p = cap.lerp(target, float(ph["progress"]))
				(cart.get_node("body") as Node3D).rotation.y = atan2(target.x - cap.x, target.z - cap.z)
			"gather":
				p = target + Vector3(0.3, 0, 0.25)
			_:
				p = target.lerp(cap, float(ph["progress"]))
				(cart.get_node("body") as Node3D).rotation.y = atan2(cap.x - target.x, cap.z - target.z)
		cart.position = p
		var lbl: Label3D = cart.get_node("label")
		lbl.text = ("⛏ " if String(ph["phase"]) == "gather" else "") + _fmt_left(int(ph["left"]))
	for id in _carts.keys():
		if not live.has(id):
			_carts[id].queue_free()
			_carts.erase(id)


static func _fmt_left(sec: int) -> String:
	if sec >= 3600:
		return "%d:%02d:%02d" % [sec / 3600, (sec % 3600) / 60, sec % 60]
	return "%d:%02d" % [sec / 60, sec % 60]


func _make_deposit(hex: int, res: String) -> Node3D:
	var node := Node3D.new()
	add_child(node)
	var center := cell_world(hex) + Vector3(0, 0.05, 0)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var pts := _hex_pts(center, 0.86)
	for k in 6:
		_strip(st, pts[k], pts[(k + 1) % 6], 0.11, center.y + 0.02)
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = _glow_mat(C_DEPOSIT, 1.15, 1.0)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	node.add_child(mi)
	var sp := Sprite3D.new()
	sp.name = "icon"
	sp.texture = _tex({"gold": "coin", "food": "food", "metal": "metal"}.get(res, "coin"))
	sp.pixel_size = 0.0034
	sp.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	sp.shaded = false
	sp.position = center + Vector3(0, 0.75, 0)
	node.add_child(sp)
	return node


func _make_cart() -> Node3D:
	var cart := Node3D.new()
	add_child(cart)
	var body := Node3D.new()
	body.name = "body"
	cart.add_child(body)
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.55, 0.36, 0.2)
	var box := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(0.22, 0.12, 0.34)
	box.mesh = bm
	box.material_override = wood
	box.position = Vector3(0, 0.14, 0)
	body.add_child(box)
	var sack := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.1
	sm.height = 0.16
	sack.mesh = sm
	var sackm := StandardMaterial3D.new()
	sackm.albedo_color = Color(0.9, 0.78, 0.45)
	sack.material_override = sackm
	sack.position = Vector3(0, 0.25, 0)
	body.add_child(sack)
	for x in [-0.13, 0.13]:
		for z in [-0.1, 0.1]:
			var wheel := MeshInstance3D.new()
			var cm := CylinderMesh.new()
			cm.top_radius = 0.06
			cm.bottom_radius = 0.06
			cm.height = 0.03
			wheel.mesh = cm
			wheel.material_override = wood
			wheel.rotation.z = PI / 2
			wheel.position = Vector3(x, 0.06, z)
			body.add_child(wheel)
	var lbl := Label3D.new()
	lbl.name = "label"
	lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lbl.no_depth_test = true
	lbl.font_size = 40
	lbl.outline_size = 10
	lbl.pixel_size = 0.005
	lbl.modulate = C_DEPOSIT
	lbl.position = Vector3(0, 0.55, 0)
	cart.add_child(lbl)
	return cart


# ------------------------------------------------------------------ AI strike arrow (canon §9.11)

var _strike: Node3D


## Red arrow from the attacker's hex to the target with a countdown; from < 0 removes it.
func strike_arrow(from: int, to: int, text: String) -> void:
	if from < 0:
		if _strike:
			_strike.queue_free()
			_strike = null
		return
	if _strike == null:
		_strike = Node3D.new()
		add_child(_strike)
		var a := cell_world(from) + Vector3(0, 0.7, 0)
		var b := cell_world(to) + Vector3(0, 0.7, 0)
		var dir := (b - a).normalized()
		var side := dir.cross(Vector3.UP) * 0.22
		var tip := b - dir * 0.45
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		for v in [a + side, tip + side, tip - side, a + side, tip - side, a - side, tip + side * 2.4, b - dir * 0.05, tip - side * 2.4]:
			st.add_vertex(v)
		var mi := MeshInstance3D.new()
		mi.mesh = st.commit()
		var am := _glow_mat(C_WAR, 1.4, 0.95)
		am.no_depth_test = true
		am.render_priority = 4
		mi.material_override = am
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_strike.add_child(mi)
		var l := Label3D.new()
		l.name = "label"
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.no_depth_test = true
		l.font_size = 56
		l.outline_size = 14
		l.pixel_size = 0.006
		l.modulate = Color(1.0, 0.55, 0.5)
		l.position = a.lerp(b, 0.5) + Vector3(0, 1.2, 0)
		_strike.add_child(l)
	(_strike.get_node("label") as Label3D).text = text


var _smoke_mat: StandardMaterial3D
var _smokes := {}  # hex id -> CPUParticles3D (persistent smoke, e.g. the burned FTUE mill)


## Gradient from explicit stops (add_point() reorders indices, so never mix it with set_color(i)).
func _ramp(offsets: Array, colors: Array) -> Gradient:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array(offsets)
	g.colors = PackedColorArray(colors)
	return g


func _soft_tex() -> GradientTexture2D:
	var tex := GradientTexture2D.new()
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	tex.gradient = g
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(0.5, 0.0)
	tex.width = 64
	tex.height = 64
	return tex


## Rising smoke column over a hex (with embers when `fire`). `seconds` < 0 keeps it until clear_smoke().
func smoke(hex: int, seconds: float, fire := false) -> void:
	if _smoke_mat == null:
		_smoke_mat = StandardMaterial3D.new()
		_smoke_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_smoke_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		# BILLBOARD_PARTICLES draws not-yet-spawned particles as black quads at the emitter; keep_scale avoids it
		_smoke_mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
		_smoke_mat.billboard_keep_scale = true
		_smoke_mat.vertex_color_use_as_albedo = true
		_smoke_mat.albedo_texture = _soft_tex()
	var root := Node3D.new()
	root.position = cell_world(hex) + Vector3(0.15, 0.2, -0.1)
	add_child(root)
	var sm := CPUParticles3D.new()
	sm.amount = 22
	sm.lifetime = 3.2
	sm.direction = Vector3(0.25, 1, 0)
	sm.spread = 12.0
	sm.initial_velocity_min = 0.35
	sm.initial_velocity_max = 0.6
	sm.gravity = Vector3(0.12, 0.05, 0)
	sm.scale_amount_min = 0.6
	sm.scale_amount_max = 1.0
	var curve := Curve.new()
	curve.add_point(Vector2(0, 0.35))
	curve.add_point(Vector2(1, 1.6))
	sm.scale_amount_curve = curve
	var ramp := _ramp([0.0, 0.15, 0.6, 1.0], [Color(0.5, 0.47, 0.44, 0.0), Color(0.5, 0.48, 0.46, 0.34), Color(0.7, 0.7, 0.72, 0.18), Color(0.85, 0.85, 0.88, 0.0)])
	sm.color_ramp = ramp
	var q := QuadMesh.new()
	q.size = Vector2(0.7, 0.7)
	q.material = _smoke_mat
	sm.mesh = q
	sm.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(sm)
	if fire:
		var fl := CPUParticles3D.new()
		fl.amount = 26
		fl.lifetime = 0.7
		fl.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
		fl.emission_sphere_radius = 0.18
		fl.direction = Vector3.UP
		fl.spread = 15.0
		fl.initial_velocity_min = 0.5
		fl.initial_velocity_max = 0.9
		fl.gravity = Vector3(0, 0.6, 0)
		fl.scale_amount_min = 0.3
		fl.scale_amount_max = 0.55
		var fr := _ramp([0.0, 0.4, 1.0], [Color(1.0, 0.95, 0.5, 0.95), Color(1.0, 0.45, 0.1, 0.8), Color(0.6, 0.1, 0.05, 0.0)])
		fl.color_ramp = fr
		var fm := _smoke_mat.duplicate() as StandardMaterial3D
		fm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
		var fq := QuadMesh.new()
		fq.size = Vector2(0.45, 0.45)
		fq.material = fm
		fl.mesh = fq
		fl.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(fl)
	if seconds >= 0.0:
		var tw := root.create_tween()
		tw.tween_interval(seconds)
		tw.tween_callback(func():
			for c in root.get_children():
				(c as CPUParticles3D).emitting = false)
		tw.tween_interval(3.3)
		tw.tween_callback(root.queue_free)
	else:
		clear_smoke(hex)
		_smokes[hex] = root


func clear_smoke(hex: int) -> void:
	var root: Node3D = _smokes.get(hex)
	if root == null:
		return
	_smokes.erase(hex)
	for c in root.get_children():
		(c as CPUParticles3D).emitting = false
	var tw := root.create_tween()
	tw.tween_interval(3.3)
	tw.tween_callback(root.queue_free)


## Fireworks («салют», canon §10.3) over a point: `volleys` bursts 0.45 s apart.
func fireworks(pos: Vector3, volleys: int) -> void:
	var palette := [Color(1.0, 0.85, 0.3), Color(0.45, 0.75, 1.0), Color(1.0, 0.45, 0.4), Color(0.6, 1.0, 0.6), Color(1.0, 1.0, 1.0)]
	for i in volleys:
		var fx := CPUParticles3D.new()
		fx.one_shot = true
		fx.amount = 70
		fx.lifetime = 1.3
		fx.explosiveness = 0.95
		fx.direction = Vector3.UP
		fx.spread = 180.0
		fx.initial_velocity_min = 2.2
		fx.initial_velocity_max = 3.0
		fx.gravity = Vector3(0, -2.2, 0)
		fx.damping_min = 1.5
		fx.damping_max = 2.5
		var col: Color = palette[(i * 2 + 1) % palette.size()]
		var g := _ramp([0.0, 0.25, 1.0], [Color(1, 1, 1), col, Color(col.r, col.g, col.b, 0.0)])
		fx.color_ramp = g
		var mesh := SphereMesh.new()
		mesh.radius = 0.04
		mesh.height = 0.08
		mesh.radial_segments = 4
		mesh.rings = 2
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.vertex_color_use_as_albedo = true
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mesh.material = m
		fx.mesh = mesh
		fx.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		fx.position = pos + Vector3(rng.randf_range(-1.2, 1.2), rng.randf_range(2.6, 3.6), rng.randf_range(-1.0, 0.6))
		fx.emitting = false
		add_child(fx)
		var tw := fx.create_tween()  # bound to fx: dies with it, never touches a freed node
		tw.tween_interval(0.45 * i + 0.01)
		tw.tween_callback(fx.set.bind("emitting", true))
		tw.tween_interval(2.0)
		tw.tween_callback(fx.queue_free)


func floater(hex: int, text: String, color := Color.WHITE) -> void:
	var lbl := Label3D.new()
	lbl.text = text
	lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lbl.no_depth_test = true
	lbl.font_size = 56
	lbl.outline_size = 12
	lbl.modulate = color
	lbl.pixel_size = 0.006
	lbl.position = cell_world(hex) + Vector3(0, 1.4, 0)
	add_child(lbl)
	_fx.append({"node": lbl, "t": 0.0, "dur": 1.4, "float": true})


func _process(delta: float) -> void:
	if sim == null:
		return
	var snap := _territory_snapshot()
	if _dirty or snap != _snapshot or ceremony_t >= 0.0:
		_snapshot = snap
		_dirty = false
		_rebuild_overlay()
	var bt := Time.get_ticks_msec() / 1000.0
	for h in _bubbles:
		var bn: Node3D = _bubbles[h]
		bn.position.y = 2.0 + 0.07 * sin(bt * 3.0 + h)
	_step_volleys(delta)
	for i in range(_sails.size() - 1, -1, -1):
		var obj: Variant = _sails[i]
		if not is_instance_valid(obj):
			_sails.remove_at(i)
			continue
		(obj as Node3D).rotate_object_local(Vector3.FORWARD, -1.1 * delta)
	for h in _dep_nodes:
		var ic: Node3D = _dep_nodes[h].get_node("icon")
		ic.position.y = cell_world(h).y + 0.8 + 0.06 * sin(bt * 2.5 + h * 0.7)
	for f in _fx.duplicate():
		f["t"] += delta
		var k: float = f["t"] / f["dur"]
		var n: Node3D = f["node"]
		if k >= 1.0:
			n.queue_free()
			_fx.erase(f)
			continue
		if f.get("float", false):
			n.position.y += delta * 0.8
			(n as Label3D).modulate.a = 1.0 - k * k
		else:
			var s := 0.6 + k * (1.6 if f["big"] else 0.7)
			n.scale = Vector3(s, 0.3, s)
			((n as MeshInstance3D).material_override as StandardMaterial3D).albedo_color.a = 1.0 - k
			((n as MeshInstance3D).material_override as StandardMaterial3D).emission_energy_multiplier = 6.0 * (1.0 - k)
