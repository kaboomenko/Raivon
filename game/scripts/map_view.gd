extends Node3D
## Renders the live sim world (scripts/sim): terrain, official territory with neon borders,
## occupation hatching, props per hex kind, armies with strength labels, battle FX and the
## peace-ceremony ink wave. Rebuilds territory meshes whenever ownership/control changes.

const Types := preload("res://scripts/sim/types.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")

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
var _army_nodes := {}  # army id -> Node3D
var _fx: Array = []
var _dirty := true
var _snapshot := ""


static func axial_to_world(q: int, r: int) -> Vector3:
	return Vector3(1.5 * q, 0.0, SQ3 * (r + q / 2.0))


func _ready() -> void:
	rng.seed = 7
	for f in DirAccess.get_files_at("res://assets/models"):
		if f.ends_with(".glb"):
			models[f.get_basename()] = load("res://assets/models/" + f)
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


func spawn(name: String, parent: Node, pos: Vector3, rot := 0.0, s := 1.0) -> Node3D:
	if not models.has(name):
		return null
	var n: Node3D = models[name].instantiate()
	n.position = pos
	n.rotation.y = rot
	n.scale = Vector3.ONE * s
	parent.add_child(n)
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
	if s == MapGen.HAMLETS:
		return "green"
	return "red"


## Re-spawns buildings, trees and banners (after a treaty or colonization changes owners).
## Each cell has its own seed, so trees stay where they were.
func refresh_props() -> void:
	for c in _props_root.get_children():
		c.queue_free()
	_place_props()


func _place_props() -> void:
	for c in sim.cells:
		rng.seed = 7 + int(c["id"]) * 7919
		if not Types.is_passable(c):
			if c["terrain"] == "mountain":
				spawn("mountain", _props_root, cell_world(c["id"]), rng.randf() * TAU, rng.randf_range(1.2, 1.6))
			continue
		var p := cell_world(c["id"])
		var side := _faction_suffix(c["owner"])
		match c["kind"]:
			"capital":
				var model := "castle" if c["owner"] == Types.PLAYER else ("castle_green" if c["owner"] == MapGen.HAMLETS else "castle_red")
				spawn(model, _props_root, p, 0.3 if c["owner"] == Types.PLAYER else PI, 1.35)
				continue
			"city":
				var hm := "house_blue" if c["owner"] == Types.PLAYER else ("house_green" if c["owner"] == MapGen.HAMLETS else "house_red")
				for o in [Vector3(-0.3, 0, 0.15), Vector3(0.3, 0, -0.25), Vector3(0.1, 0, 0.4), Vector3(-0.25, 0, -0.35)]:
					spawn(hm, _props_root, p + o, rng.randf() * TAU, 1.05)
				continue
			"farm":
				spawn("wheat_field", _props_root, p + Vector3(0.1, 0, 0.1), 0.0, 0.95)
				spawn("windmill", _props_root, p + Vector3(-0.45, 0, -0.3), 0.4, 0.95)
				continue
			"mine":
				spawn("mine", _props_root, p, 0.2, 1.1)
				continue
		match c["terrain"]:
			"forest":
				for i in rng.randi_range(8, 12):
					var off := Vector3(rng.randf_range(-0.62, 0.62), 0, rng.randf_range(-0.62, 0.62))
					spawn("tree_pine" if rng.randf() < 0.75 else "tree_round", _props_root, p + off, rng.randf() * TAU, rng.randf_range(0.85, 1.3))
			"hills":
				for i in 3:
					spawn("rock", _props_root, p + Vector3(rng.randf_range(-0.5, 0.5), 0, rng.randf_range(-0.5, 0.5)), rng.randf() * TAU, rng.randf_range(1.2, 2.0))
				spawn("tree_pine", _props_root, p + Vector3(0.3, 0, 0.3), 0.0, 1.0)
			_:
				for i in rng.randi_range(1, 4):
					var off := Vector3(rng.randf_range(-0.6, 0.6), 0, rng.randf_range(-0.6, 0.6))
					spawn("tree_pine" if rng.randf() < 0.6 else "tree_round", _props_root, p + off, rng.randf() * TAU, rng.randf_range(0.7, 1.0))
		if c["owner"] != Types.NOBODY and rng.randf() < 0.3:
			spawn("banner_" + side, _props_root, p + Vector3(rng.randf_range(-0.4, 0.4), 0, rng.randf_range(-0.4, 0.4)))


func _build_horizon() -> void:
	var ring_mat := StandardMaterial3D.new()
	ring_mat.albedo_color = Color(0.18, 0.22, 0.2)
	for q in range(-9, 10):
		for r in range(-9, 10):
			if abs(q + r) > 9 or sim.id_at(q, r) >= 0:
				continue
			var d: int = (absi(q) + absi(r) + absi(q + r)) / 2
			if d > 8:
				continue
			var p := axial_to_world(q, r)
			var roll := rng.randf()
			var near := p.z > 3.0  # bottom of the screen: keep low so it never hides the player's land
			if near:
				for i in 3:
					spawn("tree_pine" if rng.randf() < 0.7 else "tree_round", _horizon_root, p + Vector3(rng.randf_range(-0.7, 0.7), -0.1, rng.randf_range(-0.7, 0.7)), rng.randf() * TAU, rng.randf_range(0.8, 1.1))
			elif d <= 6 and roll < 0.5:
				spawn("mountain", _horizon_root, p + Vector3(0, -0.15, 0), rng.randf() * TAU, rng.randf_range(1.7, 2.8))
			elif d <= 6:
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
			if not near and rng.randf() < 0.55 + 0.1 * (d - 5):
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
	var alive := {}
	for a in armies:
		if a["str"] <= 0:
			continue
		var id: int = a["id"]
		alive[id] = true
		var node: Node3D = _army_nodes.get(id)
		if node == null:
			node = _make_army(a)
			_army_nodes[id] = node
		var p := cell_world(a["hex"])
		if a["move"] != null:
			var to := cell_world(a["move"]["to"])
			p = p.lerp(to, 1.0 - float(a["move"]["left"]) / 15.0)
		node.position = node.position.lerp(p, 0.35) if node.position.distance_to(p) < 3.0 else p
		var lbl: Label3D = node.get_node("label")
		lbl.text = str(int(round(a["str"] / 1000.0)))
		var ready := float(a["str"]) / maxf(1.0, float(a["max_str"]))
		lbl.modulate = Color(1, 1, 1) if ready >= 0.5 else Color(1.0, 0.75, 0.4)
		node.modulate_alpha = 0.45 if a["routed"] else 1.0
		# face the nearest enemy-controlled neighbour
		var enemy_dir := Vector3.ZERO
		for n in sim.neighbors[a["hex"]]:
			if n >= 0 and sim.cells[n]["controller"] != a["side"] and Types.is_passable(sim.cells[n]) and sim.cells[n]["controller"] != Types.NOBODY:
				enemy_dir += cell_world(n) - cell_world(a["hex"])
		if enemy_dir.length() > 0.1:
			node.get_node("model").rotation.y = atan2(enemy_dir.x, enemy_dir.z) + PI
	for id in _army_nodes.keys():
		if not alive.has(id):
			_army_nodes[id].queue_free()
			_army_nodes.erase(id)


class ArmyNode extends Node3D:
	var modulate_alpha := 1.0


func _make_army(a: Dictionary) -> Node3D:
	var node := ArmyNode.new()
	add_child(node)
	var side := _faction_suffix(a["side"])
	var model := Node3D.new()
	model.name = "model"
	node.add_child(model)
	spawn("squad_" + side, model, Vector3(-0.15, 0, 0.05), 0.0, 1.15)
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
