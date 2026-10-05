extends Node3D
## Builds the strategic hex world: terrain, territory tint, glowing borders, fog of war, props, armies.
## Flat-top axial hexes, radius 1.0 (docs/gdd/02_map_territory.md). Godot Y is up; map plane is XZ.

const SQ3 := 1.7320508
const HEX_R := 1.0
const TILE_TOP := 0.0

enum Owner { WILD, PLAYER, ENEMY, FOG }

const BLUE := Color(0.25, 0.55, 1.0)
const RED := Color(1.0, 0.22, 0.2)

var cells := {}          # Vector2i(q, r) -> {owner, terrain, kind}
var models := {}         # name -> PackedScene
var rng := RandomNumberGenerator.new()

const DIRS := [Vector2i(1, 0), Vector2i(1, -1), Vector2i(0, -1), Vector2i(-1, 0), Vector2i(-1, 1), Vector2i(0, 1)]


static func axial_to_world(q: int, r: int) -> Vector3:
	return Vector3(1.5 * HEX_R * q, 0.0, SQ3 * HEX_R * (r + q / 2.0))


func _ready() -> void:
	rng.seed = 20261005
	_load_models()
	_make_map()
	_build_terrain()
	_build_territory()
	_place_props()
	_place_armies()
	_build_clouds()


func _load_models() -> void:
	for f in DirAccess.get_files_at("res://assets/models"):
		if f.ends_with(".glb"):
			models[f.get_basename()] = load("res://assets/models/" + f)


func spawn(name: String, pos: Vector3, rot_y := 0.0, s := 1.0) -> Node3D:
	if not models.has(name):
		return null
	var n: Node3D = models[name].instantiate()
	n.position = pos
	n.rotation.y = rot_y
	n.scale = Vector3.ONE * s
	add_child(n)
	return n


# ------------------------------------------------------------------ map layout

func _make_map() -> void:
	# A strategic slice like the reference: player west, enemy east, a glowing front between, fog at the far edges.
	for q in range(-7, 8):
		for r in range(-9, 10):
			var p := axial_to_world(q, r)
			if abs(p.x) > 10.5 or abs(p.z) > 13.0:
				continue
			var owner := Owner.WILD
			var front_x := 1.2 + sin(p.z * 0.45) * 1.6
			if p.x < front_x - 0.2:
				owner = Owner.PLAYER
			elif p.x > front_x + 0.9:
				owner = Owner.ENEMY
			if p.z > 9.0 and p.x > -2.0:
				owner = Owner.FOG
			if p.z < -10.5:
				owner = Owner.FOG
			var terrain := "grass"
			var roll := rng.randf()
			if roll < 0.18:
				terrain = "forest"
			elif roll < 0.24:
				terrain = "mountain"
			if p.x < -7.0 and p.z > 2.0:
				terrain = "water"
			cells[Vector2i(q, r)] = {"owner": owner, "terrain": terrain, "kind": ""}
	# fixed landmarks
	_mark(Vector2i(-2, 0), "grass", "castle")
	_mark(Vector2i(-1, 0), "grass", "house")
	_mark(Vector2i(-3, 2), "grass", "house")
	_mark(Vector2i(-3, -1), "grass", "mine")
	_mark(Vector2i(-1, 2), "grass", "field")
	_mark(Vector2i(-2, 2), "grass", "windmill")
	_mark(Vector2i(-1, -2), "grass", "barracks")
	_mark(Vector2i(0, 3), "grass", "watchtower")
	_mark(Vector2i(0, -3), "grass", "watchtower")
	_mark(Vector2i(-5, -2), "grass", "house")
	_mark(Vector2i(-1, 5), "grass", "field")
	_mark(Vector2i(4, -2), "grass", "enemy_camp")
	_mark(Vector2i(5, 0), "grass", "enemy_castle")
	_mark(Vector2i(4, 3), "grass", "enemy_camp")


func _mark(c: Vector2i, terrain: String, kind: String) -> void:
	if cells.has(c):
		cells[c]["terrain"] = terrain
		cells[c]["kind"] = kind


# ------------------------------------------------------------------ terrain

func _hex_points(center: Vector3, radius: float) -> Array:
	var pts := []
	for k in 6:
		var a := PI / 3.0 * k
		pts.append(center + Vector3(radius * cos(a), 0, radius * sin(a)))
	return pts


func _build_terrain() -> void:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for c in cells:
		var cell: Dictionary = cells[c]
		var center := axial_to_world(c.x, c.y)
		var top := TILE_TOP
		var col := Color(0.27, 0.5, 0.17)
		match cell["terrain"]:
			"forest":
				col = Color(0.24, 0.47, 0.18)
			"mountain":
				col = Color(0.45, 0.43, 0.38)
			"water":
				col = Color(0.12, 0.38, 0.55)
				top = -0.18
		if cell["owner"] == Owner.ENEMY:
			col = col.lerp(Color(0.32, 0.22, 0.16), 0.5).lerp(Color(0.75, 0.12, 0.1), 0.35)  # scorched, red-tinted
		elif cell["owner"] == Owner.PLAYER:
			col = col.lerp(Color(0.1, 0.28, 0.8), 0.3)  # blue-tinted own land
		if cell["owner"] == Owner.FOG:
			col = Color(0.18, 0.19, 0.21)
		col = col * (0.92 + rng.randf() * 0.16)
		col.a = 1.0
		var pts := _hex_points(center + Vector3(0, top, 0), HEX_R * 0.995)
		# top fan
		for k in 6:
			st.set_color(col)
			st.set_normal(Vector3.UP)
			st.add_vertex(center + Vector3(0, top, 0))
			st.add_vertex(pts[k])
			st.add_vertex(pts[(k + 1) % 6])
		# skirt
		var side := col.darkened(0.45)
		for k in 6:
			var a: Vector3 = pts[k]
			var b: Vector3 = pts[(k + 1) % 6]
			var a2 := a + Vector3(0, -1.2, 0)
			var b2 := b + Vector3(0, -1.2, 0)
			var n := ((a + b) / 2.0 - center).normalized()
			st.set_color(side)
			st.set_normal(n)
			st.add_vertex(a); st.add_vertex(b2); st.add_vertex(b)
			st.add_vertex(a); st.add_vertex(a2); st.add_vertex(b2)
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.vertex_color_is_srgb = true
	mat.roughness = 0.95
	mi.material_override = mat
	add_child(mi)
	# water surface
	var water := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(80, 80)
	water.mesh = plane
	water.position = Vector3(0, -0.22, 0)
	var wm := StandardMaterial3D.new()
	wm.albedo_color = Color(0.08, 0.3, 0.45)
	wm.metallic = 0.2
	wm.roughness = 0.15
	water.material_override = wm
	add_child(water)


# ------------------------------------------------------------------ territory: tint, inner grid, glowing border

func _flat_mat(color: Color, emission := 0.0, alpha := 1.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = Color(color.r, color.g, color.b, alpha)
	if alpha < 1.0:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if emission > 0.0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = emission
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m


func _build_territory() -> void:
	var tint := {Owner.PLAYER: SurfaceTool.new(), Owner.ENEMY: SurfaceTool.new(), Owner.FOG: SurfaceTool.new()}
	for o in tint:
		tint[o].begin(Mesh.PRIMITIVE_TRIANGLES)
	var lines := {Owner.PLAYER: SurfaceTool.new(), Owner.ENEMY: SurfaceTool.new()}
	var borders := {Owner.PLAYER: SurfaceTool.new(), Owner.ENEMY: SurfaceTool.new()}
	for o in lines:
		lines[o].begin(Mesh.PRIMITIVE_TRIANGLES)
		borders[o].begin(Mesh.PRIMITIVE_TRIANGLES)
	for c in cells:
		var owner: int = cells[c]["owner"]
		if owner == Owner.WILD:
			continue
		var y := 0.03 if cells[c]["terrain"] != "water" else -0.15
		var center := axial_to_world(c.x, c.y) + Vector3(0, y, 0)
		var pts := _hex_points(center, HEX_R * 0.995)
		for k in 6:
			tint[owner].add_vertex(center)
			tint[owner].add_vertex(pts[(k + 1) % 6])
			tint[owner].add_vertex(pts[k])
		if owner == Owner.FOG:
			continue
		for d in 6:
			var nb: Vector2i = c + DIRS[d]
			var other: int = cells[nb]["owner"] if cells.has(nb) else -1
			var e := _edge(center, nb)
			if other == owner:
				_strip(lines[owner], e[0], e[1], 0.035, y + 0.01)
			else:
				_strip(borders[owner], e[0], e[1], 0.15, y + 0.02)
			_add_mesh(tint[Owner.FOG], _flat_mat(Color(0.08, 0.09, 0.11), 0.0, 0.55))
	_add_mesh(lines[Owner.PLAYER], _flat_mat(BLUE.lightened(0.3), 2.2, 0.75))
	_add_mesh(lines[Owner.ENEMY], _flat_mat(RED.lightened(0.2), 2.2, 0.7))
	_add_mesh(borders[Owner.PLAYER], _flat_mat(Color(0.45, 0.75, 1.0), 7.0))
	_add_mesh(borders[Owner.ENEMY], _flat_mat(Color(1.0, 0.35, 0.3), 7.0))


func _edge(center: Vector3, nb: Vector2i) -> Array:
	var nc := axial_to_world(nb.x, nb.y)
	var pts := _hex_points(center, HEX_R * 0.97)
	pts.sort_custom(func(a, b): return a.distance_to(Vector3(nc.x, center.y, nc.z)) < b.distance_to(Vector3(nc.x, center.y, nc.z)))
	return [pts[0], pts[1]]


func _strip(st: SurfaceTool, a: Vector3, b: Vector3, w: float, y: float) -> void:
	var dir := (b - a).normalized()
	var n := Vector3(-dir.z, 0, dir.x) * w * 0.5
	a.y = y
	b.y = y
	var ext := dir * w * 0.5
	var a0 := a - ext
	var b0 := b + ext
	st.add_vertex(a0 - n); st.add_vertex(b0 - n); st.add_vertex(b0 + n)
	st.add_vertex(a0 - n); st.add_vertex(b0 + n); st.add_vertex(a0 + n)


func _add_mesh(st: SurfaceTool, m: Material) -> void:
	st.generate_normals()
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)


# ------------------------------------------------------------------ props

func _place_props() -> void:
	for c in cells:
		var cell: Dictionary = cells[c]
		var p := axial_to_world(c.x, c.y)
		var owner: int = cell["owner"]
		match cell["kind"]:
			"castle":
				spawn("castle", p, 0.3, 1.6)
				continue
			"house":
				spawn("house_blue", p + Vector3(-0.3, 0, 0.2), rng.randf() * TAU, 1.1)
				spawn("house_blue", p + Vector3(0.35, 0, -0.25), rng.randf() * TAU, 1.0)
				spawn("tree_round", p + Vector3(0.3, 0, 0.45))
				continue
			"mine":
				spawn("mine", p, 0.2, 1.1)
				continue
			"field":
				spawn("wheat_field", p, 0.0, 1.0)
				continue
			"windmill":
				spawn("windmill", p + Vector3(-0.2, 0, 0), 0.4, 1.2)
				spawn("wheat_field", p + Vector3(0.35, 0, 0.35), 0.5, 0.6)
				continue
			"barracks":
				spawn("barracks", p, 0.0, 1.1)
				continue
			"watchtower":
				spawn("watchtower", p, 0.0, 1.0)
				spawn("banner_blue", p + Vector3(0.45, 0, 0.3))
				continue
			"enemy_castle":
				var cn := spawn("castle", p, PI, 1.2)
				_tint_roofs(cn, Color(0.62, 0.12, 0.12))
				continue
			"enemy_camp":
				spawn("tent_red", p + Vector3(-0.3, 0, -0.2))
				spawn("tent_red", p + Vector3(0.3, 0, 0.1), 1.0)
				spawn("catapult", p + Vector3(0.0, 0, 0.45), PI, 1.2)
				continue
		match cell["terrain"]:
			"forest":
				for i in rng.randi_range(7, 11):
					var off := Vector3(rng.randf_range(-0.6, 0.6), 0, rng.randf_range(-0.6, 0.6))
					spawn("tree_pine" if rng.randf() < 0.7 else "tree_round", p + off, rng.randf() * TAU, rng.randf_range(0.8, 1.25))
			"mountain":
				spawn("mountain", p, rng.randf() * TAU, rng.randf_range(1.1, 1.5))
			"grass":
				if owner != Owner.FOG and rng.randf() < 0.8:
					for i in rng.randi_range(2, 5):
						var off := Vector3(rng.randf_range(-0.6, 0.6), 0, rng.randf_range(-0.6, 0.6))
						spawn("tree_pine", p + off, rng.randf() * TAU, rng.randf_range(0.7, 1.0))
				if rng.randf() < 0.35:
					spawn("rock", p + Vector3(rng.randf_range(-0.5, 0.5), 0, rng.randf_range(-0.5, 0.5)), rng.randf() * TAU)
		if owner == Owner.ENEMY and rng.randf() < 0.25:
			spawn("banner_red", p + Vector3(rng.randf_range(-0.4, 0.4), 0, rng.randf_range(-0.4, 0.4)))
		if owner == Owner.PLAYER and rng.randf() < 0.12:
			spawn("banner_blue", p + Vector3(rng.randf_range(-0.4, 0.4), 0, rng.randf_range(-0.4, 0.4)))


func _tint_roofs(node: Node, color: Color) -> void:
	if node == null:
		return
	for child in node.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = child
		for s in mi.mesh.get_surface_count():
			var m: Material = mi.mesh.surface_get_material(s)
			if m is StandardMaterial3D and m.albedo_color.b > 0.4 and m.albedo_color.r < 0.25:
				var m2: StandardMaterial3D = m.duplicate()
				m2.albedo_color = color
				mi.set_surface_override_material(s, m2)


# ------------------------------------------------------------------ armies on the front

func _place_armies() -> void:
	for c in cells:
		var owner: int = cells[c]["owner"]
		if owner != Owner.PLAYER and owner != Owner.ENEMY:
			continue
		var touches_front := false
		for d in DIRS:
			var nb: Vector2i = c + d
			if cells.has(nb) and cells[nb]["owner"] != owner and cells[nb]["owner"] != Owner.FOG:
				touches_front = true
		if not touches_front or cells[c]["kind"] != "" or cells[c]["terrain"] == "water":
			continue
		var p := axial_to_world(c.x, c.y)
		var face := -PI / 2 if owner == Owner.PLAYER else PI / 2
		var side := "blue" if owner == Owner.PLAYER else "red"
		if rng.randf() < 0.75:
			spawn("squad_" + side, p + Vector3(-0.2, 0, -0.15), face, 1.6)
			if rng.randf() < 0.6:
				spawn("knight_" + side, p + Vector3(0.25, 0, 0.3), face, 1.8)
			if rng.randf() < 0.4:
				spawn("squad_" + side, p + Vector3(0.3, 0, -0.4), face, 1.4)


# ------------------------------------------------------------------ clouds at the edges of the known world

func _build_clouds() -> void:
	var tex := GradientTexture2D.new()
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 0.85))
	g.set_color(1, Color(1, 1, 1, 0.0))
	tex.gradient = g
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(0.5, 0.0)
	tex.width = 128
	tex.height = 128
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_texture = tex
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	mat.albedo_color = Color(0.92, 0.94, 0.97, 0.9)
	for c in cells:
		if cells[c]["owner"] != Owner.FOG:
			continue
		for i in 2:
			var q := QuadMesh.new()
			q.size = Vector2.ONE * rng.randf_range(2.2, 3.6)
			var mi := MeshInstance3D.new()
			mi.mesh = q
			mi.material_override = mat
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mi.position = axial_to_world(c.x, c.y) + Vector3(rng.randf_range(-0.6, 0.6), rng.randf_range(0.6, 1.4), rng.randf_range(-0.6, 0.6))
			add_child(mi)
