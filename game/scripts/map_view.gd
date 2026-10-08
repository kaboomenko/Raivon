extends Node3D
## Renders the live sim world (scripts/sim): terrain, official territory with neon borders,
## occupation hatching, props per hex kind, armies with strength labels, battle FX and the
## peace-ceremony ink wave. Rebuilds territory meshes whenever ownership/control changes.

const Types := preload("res://scripts/sim/types.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")
const FlagView := preload("res://scripts/flag_view.gd")

const SQ3 := 1.7320508
const DIRS := [Vector2i(1, 0), Vector2i(1, -1), Vector2i(0, -1), Vector2i(-1, 0), Vector2i(-1, 1), Vector2i(0, 1)]

const C_PLAYER := Color(0.15, 0.5, 1.0)
const C_WAR := Color(1.0, 0.14, 0.1)
const C_WILD := Color(0.75, 0.72, 0.62)

var sim  # World (RefCounted)
var at_war_with := -1:
	set(v):
		if v == at_war_with:
			return
		at_war_with = v
		if sim != null and _props_root != null and _props_root.get_child_count() > 0:
			refresh_props.call_deferred()  # the enemy's land flies more banners while at war
var models := {}
var flag: Dictionary = FlagView.DEFAULT.duplicate()  # the player's flag, painted on the player's banners
var _flag_mats := {}  # owner -> [SubViewport, FlagView, material]: one texture per state
var rng := RandomNumberGenerator.new()

# ceremony: hex id -> flip time (s); before flip the hex is drawn with prev_owner
var ceremony_t := -1.0
var flip_at := {}
var prev_owner := {}

var _terrain_mi: MeshInstance3D
var _overlay_root: Node3D
var _props_root: Node3D
var _horizon_root: Node3D
var _bay_root: Node3D  # warships off the near shore: rebuilt with the props, so they follow the states' eras
var _bay_spots: Array = []  # [q, r, world position] of the sea hexes that hold a ship
var _hex_props := {}  # hex id -> Node3D holder of that hex's props
var _sails: Array = []  # windmill sail nodes, spun in _process (meta "still" = a burning mill)
var _blazing := {}  # hex id -> true while a long fire burns there
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
	_bay_root = Node3D.new()
	add_child(_bay_root)


func set_world(w) -> void:
	sim = w
	for c in _horizon_root.get_children():
		c.queue_free()
	_bay_spots = []
	_build_terrain()
	_build_rivers()
	_build_water()
	refresh_props()
	rng.seed = 11
	_build_horizon()
	_build_bay()
	_dirty = true


var _river_mi: MeshInstance3D
var _water_mi: MeshInstance3D


## Water surface over water hexes (animated ripples, foam where an edge meets land).
func _build_water() -> void:
	if _water_mi:
		_water_mi.queue_free()
		_water_mi = null
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var any := false
	for c in sim.cells:
		if c["terrain"] != "water":
			continue
		any = true
		var center := axial_to_world(c["q"], c["r"]) + Vector3(0, -0.07, 0)
		var pts := _hex_pts(center, 1.0)
		# land on each edge k (between corners k and k+1)
		var land: Array = []
		for k in 6:
			var mid: Vector3 = (pts[k] + pts[(k + 1) % 6]) / 2.0
			var other := id_at_world(center + 2.0 * (mid - center))
			land.append(other < 0 or sim.cells[other]["terrain"] != "water")
		for k in 6:
			var ca := 1.0 if (land[k] or land[(k + 5) % 6]) else 0.0  # corner k touches edges k−1 and k
			var cb := 1.0 if (land[k] or land[(k + 1) % 6]) else 0.0
			st.set_normal(Vector3.UP)
			st.set_color(Color(0, 0, 0))
			st.add_vertex(center)
			st.set_color(Color(ca, 0, 0))
			st.add_vertex(pts[k])
			st.set_color(Color(cb, 0, 0))
			st.add_vertex(pts[(k + 1) % 6])
	if not any:
		return
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/water.gdshader")
	mat.set_shader_parameter("noise_tex", _noise_tex(2.0, 3, 303))
	_water_mi = MeshInstance3D.new()
	_water_mi.mesh = st.commit()
	_water_mi.material_override = mat
	_water_mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_water_mi)
	_build_waterfalls()


var _falls_mi: MeshInstance3D

## Waterfalls where a water hex meets the edge of the open world (the reference frames: water pouring off the
## plateau): a curtain from the water surface down the cliff with scrolling streaks, mist at the foot.
func _build_waterfalls() -> void:
	if _falls_mi:
		_falls_mi.queue_free()
		_falls_mi = null
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var any := false
	for c in sim.cells:
		if c["terrain"] != "water":
			continue
		var center := axial_to_world(c["q"], c["r"])
		var pts := _hex_pts(center + Vector3(0, -0.07, 0), 1.0)
		for k in 6:
			var a: Vector3 = pts[k]
			var b: Vector3 = pts[(k + 1) % 6]
			var mid := (a + b) / 2.0
			if id_at_world(center + 2.0 * (mid - center)) >= 0:
				continue
			any = true
			var out := Vector3(mid.x - center.x, 0, mid.z - center.z).normalized()
			var a2 := a + out * 0.12 + Vector3(0, -0.27, 0)
			var b2 := b + out * 0.12 + Vector3(0, -0.27, 0)
			for v in [[a, Vector2(0, 0)], [b, Vector2(1, 0)], [b2, Vector2(1, 1)], [a, Vector2(0, 0)], [b2, Vector2(1, 1)], [a2, Vector2(0, 1)]]:
				st.set_uv(v[1])
				st.set_normal(out)
				st.add_vertex((v[0] as Vector3) + out * 0.01)
			if _smoke_mat == null:
				_smoke_mat = _fx_mat(_puff_tex(), false)
			var mist := CPUParticles3D.new()  # spray where the fall hits the fog below
			mist.amount = 6
			mist.lifetime = 2.2
			mist.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
			mist.emission_box_extents = Vector3(0.4, 0.02, 0.1)
			mist.direction = Vector3(0, 1, 0)
			mist.initial_velocity_min = 0.05
			mist.initial_velocity_max = 0.12
			mist.gravity = Vector3.ZERO
			mist.scale_amount_curve = _curve(0.4, 1.3)
			mist.color_ramp = _ramp([0.0, 0.3, 1.0], [Color(1, 1, 1, 0.0), Color(0.95, 0.98, 1.0, 0.45), Color(1, 1, 1, 0.0)])
			var q := QuadMesh.new()
			q.size = Vector2(0.35, 0.35)
			q.material = _smoke_mat
			mist.mesh = q
			mist.preprocess = 2.2
			mist.position = (a2 + b2) / 2.0 + Vector3(0, 0.05, 0)
			mist.rotation.y = atan2(-(b - a).z, (b - a).x)
			mist.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			_horizon_root.add_child(mist)
	if not any:
		return
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/waterfall.gdshader")
	m.set_shader_parameter("noise_tex", _noise_tex(3.0, 2, 404))
	_falls_mi = MeshInstance3D.new()
	_falls_mi.mesh = st.commit()
	_falls_mi.material_override = m
	_falls_mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_falls_mi)


## Rivers run along hex edges (canon §5.1): a blue ribbon on every river edge with round joints.
func _build_rivers() -> void:
	if _river_mi:
		_river_mi.queue_free()
		_river_mi = null
	if sim.rivers.is_empty():
		return
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var y := 0.05
	var w := 0.11
	for e in sim.rivers:
		var ab: PackedStringArray = String(e).split(":")
		var ca := cell_world(int(ab[0]))
		var cb := cell_world(int(ab[1]))
		var mid := (ca + cb) / 2.0
		var across := (cb - ca).normalized()
		var along := Vector3(-across.z, 0, across.x)
		var p := mid - along * 0.5
		var q := mid + along * 0.5
		# two strips, bank to mid-stream (vertex colour r: 1 at a bank, 0 mid-stream) for the shader's foam
		for half in [[p - across * w, q - across * w, q, p], [p + across * w, q + across * w, q, p]]:
			var cols := [1.0, 1.0, 0.0, 0.0]
			for i in [0, 1, 2, 0, 2, 3]:
				st.set_normal(Vector3.UP)
				st.set_color(Color(cols[i], 0, 0))
				st.add_vertex((half[i] as Vector3) + Vector3(0, y, 0))
		for c in [p, q]:
			for k in 8:
				var a0 := TAU * k / 8.0
				var a1 := TAU * (k + 1) / 8.0
				var yc := y - 0.002  # the round joints sit under the strips: only their outer arcs show at a bend
				st.set_normal(Vector3.UP)
				st.set_color(Color(0, 0, 0))
				st.add_vertex(c + Vector3(0, yc, 0))
				st.set_color(Color(1, 0, 0))
				st.add_vertex(c + Vector3(cos(a1) * w, yc, sin(a1) * w))
				st.add_vertex(c + Vector3(cos(a0) * w, yc, sin(a0) * w))
	var m := ShaderMaterial.new()  # flowing ripples and foam along the banks (unshaded: the faces point down)
	m.shader = load("res://shaders/river.gdshader")
	m.set_shader_parameter("noise_tex", _noise_tex(2.0, 3, 303))
	_river_mi = MeshInstance3D.new()
	_river_mi.mesh = st.commit()
	_river_mi.material_override = m
	_river_mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_river_mi)


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


func spawn(name: String, parent: Node, pos: Vector3, rot := 0.0, s := 1.0, owner := -99) -> Node3D:
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
	if name.begins_with("banner_"):
		_paint_flag(n, Types.PLAYER if name == "banner_blue" else owner)
	for m in n.find_children("smoke*", "", true, false):
		_chimney_smoke(m as Node3D)
	if owner != -99:
		for m in n.find_children("flag*", "", true, false):
			_flag_cloth(m as Node3D, owner)
	return n


## The state's own flag over a cloth marker baked into a building model (evolution_assets.flag_at): the node's
## scale is the cloth (x width, y height, z thickness), so a unit quad on each face covers it. "flagw…" is a
## wide flag on a pole, "flagt…" a tall hanging banner.
func _flag_cloth(at: Node3D, owner: int) -> void:
	if at == null:
		return
	var mat := _flag_material(owner, String(at.name).begins_with("flagw"))
	if mat == null:
		return
	var quad := QuadMesh.new()
	for face in [1.0, -1.0]:
		var mi := MeshInstance3D.new()
		mi.mesh = quad
		mi.material_override = mat
		mi.position = Vector3(0, 0, 0.5 * face)
		mi.rotation.y = 0.0 if face > 0 else PI
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		at.add_child(mi)


## A thin lazy plume over a chimney marker baked into a village model (tools/blender/evolution_assets.py
## smoke_at): the lived-in look of the close reference frames.
func _chimney_smoke(at: Node3D) -> void:
	if at == null:
		return
	var sm := CPUParticles3D.new()
	sm.amount = 5
	sm.lifetime = 3.2
	sm.direction = Vector3(0.25, 1, 0.1)
	sm.spread = 6.0
	sm.initial_velocity_min = 0.07
	sm.initial_velocity_max = 0.11
	sm.gravity = Vector3(0.05, 0.015, 0.02)
	sm.scale_amount_curve = _curve(0.25, 1.15)
	sm.color_ramp = _ramp([0.0, 0.18, 1.0], [Color(0.8, 0.79, 0.77, 0.0), Color(0.82, 0.81, 0.8, 0.42), Color(0.92, 0.92, 0.94, 0.0)])
	var q := QuadMesh.new()
	q.size = Vector2(0.2, 0.2)
	if _smoke_mat == null:
		_smoke_mat = _fx_mat(_puff_tex(), false)
	q.material = _smoke_mat
	sm.mesh = q
	sm.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	sm.preprocess = 3.2
	at.add_child(sm)


## The player's flag (10 §4.23) on both faces of a banner's cloth (tools/blender/export_assets.py: the cloth is
## 0.26 × 0.416 from x 0, its top at y 0.98, 0.012 thick): one viewport texture shared by every banner, so a new
## flag repaints them all at once.
func _paint_flag(banner: Node3D, owner: int) -> void:
	if owner < 0 and owner != Types.PLAYER:
		return
	var mat := _flag_material(owner)
	if mat == null:
		return
	var quad := QuadMesh.new()
	quad.size = Vector2(0.25, 0.4)
	for face in [1.0, -1.0]:
		var mi := MeshInstance3D.new()
		mi.mesh = quad
		mi.material_override = mat
		mi.position = Vector3(0.13, 0.775, 0.0095 * face)
		mi.rotation.y = 0.0 if face > 0 else PI
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		banner.add_child(mi)


## The flag a state flies: the player's own, or an AI state's from its name (FlagView.ai_flag).
func state_flag(owner: int) -> Dictionary:
	if owner == Types.PLAYER:
		return flag
	if sim == null or owner < 0 or owner >= sim.states.size():
		return {}
	return FlagView.ai_flag(String(sim.states[owner]["name"]), state_color(owner))


func _flag_material(owner: int, wide := false) -> StandardMaterial3D:
	var key := owner + (1000 if wide else 0)  # wide: a flag on a pole (3:2), else a tall banner
	if not _flag_mats.has(key):
		var f := state_flag(owner)
		if f.is_empty():
			return null
		var vp := SubViewport.new()
		var px := Vector2i(208, 136) if wide else Vector2i(130, 208)
		vp.size = px
		vp.transparent_bg = true
		vp.disable_3d = true
		vp.render_target_update_mode = SubViewport.UPDATE_ONCE
		var view := FlagView.new(f)
		view.size = Vector2(px)
		vp.add_child(view)
		add_child(vp)
		var mat := StandardMaterial3D.new()
		mat.albedo_texture = vp.get_texture()
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		mat.alpha_scissor_threshold = 0.5
		mat.roughness = 0.75
		_flag_mats[key] = [vp, view, mat]
	return _flag_mats[key][2]


func set_flag(f: Dictionary) -> void:
	flag = f.duplicate()
	for key in [Types.PLAYER, Types.PLAYER + 1000]:
		if _flag_mats.has(key):
			var view: Control = _flag_mats[key][1]
			view.set("flag", flag)
			view.queue_redraw()
			(_flag_mats[key][0] as SubViewport).render_target_update_mode = SubViewport.UPDATE_ONCE


# ------------------------------------------------------------------ static terrain

func _hex_pts(center: Vector3, radius: float) -> Array:
	var pts := []
	for k in 6:
		var a := PI / 3.0 * k
		pts.append(center + Vector3(radius * cos(a), 0, radius * sin(a)))
	return pts


## Ground colours of the biomes (02 §4.2): meadow is the default palette above; the taiga is darker and cooler,
## the steppe golden, the badlands rust-red.
const BIOME_GROUND := {
	"taiga": {"plain": Color(0.24, 0.43, 0.24), "forest": Color(0.15, 0.33, 0.18), "hills": Color(0.36, 0.41, 0.31), "mountain": Color(0.4, 0.41, 0.42)},
	"steppe": {"plain": Color(0.6, 0.58, 0.27), "forest": Color(0.42, 0.5, 0.22), "hills": Color(0.62, 0.52, 0.3)},
	"badlands": {"plain": Color(0.72, 0.47, 0.29), "forest": Color(0.58, 0.47, 0.26), "hills": Color(0.74, 0.39, 0.23), "mountain": Color(0.56, 0.36, 0.28)},
}


func _build_terrain() -> void:
	if _terrain_mi:
		_terrain_mi.queue_free()
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for c in sim.cells:
		var center := axial_to_world(c["q"], c["r"])
		var top := 0.0
		var col := Color(0.31, 0.33, 0.16)  # a muted, warm meadow: hue measured against the reference greens (~73°), not lime
		var pal: Dictionary = BIOME_GROUND.get(String(c.get("biome", "meadow")), {})
		match c["terrain"]:
			"forest":
				col = Color(0.16, 0.2, 0.11)
			"hills":
				col = Color(0.45, 0.46, 0.27)
			"mountain":
				col = Color(0.42, 0.4, 0.36)
			"water":
				col = Color(0.12, 0.36, 0.52)
				top = -0.2
		col = pal.get(String(c["terrain"]), col)
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
	_build_grass()
	_cloud_shadows()
	var water := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(90, 90)
	water.mesh = plane
	water.position = Vector3(0, -0.25, 0)
	var wm := ShaderMaterial.new()  # the open sea round the world (reference frame 1: ships on rippling water)
	wm.shader = load("res://shaders/water.gdshader")
	wm.set_shader_parameter("noise_tex", _noise_tex(2.0, 3, 303))
	wm.set_shader_parameter("shore_k", 0.0)
	water.material_override = wm
	add_child(water)


var _grass_mi: MultiMeshInstance3D
var _pebble_mi: MultiMeshInstance3D

## Grass tint by biome: tufts a shade lighter than the ground, so empty land reads as a meadow, not plastic.
const GRASS_TINT := {"meadow": Color(0.37, 0.39, 0.19), "taiga": Color(0.3, 0.5, 0.28), "steppe": Color(0.72, 0.68, 0.34), "badlands": Color(0.66, 0.55, 0.3)}


## Grass tufts and pebbles over the land (one MultiMesh each): a whole meadow on an empty plain, a fringe along
## the edge of hexes with buildings (the pads stay clean), sparse ones in forests and on hills. They rise above the
## territory fill (+0.03), so the land keeps its texture under the colour, as in the close reference frames.
func _build_grass() -> void:
	for mi in [_grass_mi, _pebble_mi]:
		if mi != null:
			mi.queue_free()
	var xf: Array = []
	var cols: Array = []
	var peb: Array = []
	var g := RandomNumberGenerator.new()
	g.seed = 4242
	for c in sim.cells:
		var t: String = c["terrain"]
		if not t in ["plain", "forest", "hills"]:
			continue
		var biome := String(c.get("biome", "meadow"))
		var tint: Color = GRASS_TINT.get(biome, GRASS_TINT["meadow"])
		var empty: bool = c["kind"] == "plain" and not camp_hexes.has(int(c["id"]))
		var n := 28
		if t == "plain" and empty:
			n = 100  # a carpet of tufts (reference frame 3: no bare earth between the farms)
		elif t == "hills":
			n = 32
		if biome == "badlands":
			n = n / 2
		var center := axial_to_world(c["q"], c["r"])
		for i in n:
			var r := sqrt(g.randf()) * 0.86 if empty else g.randf_range(0.7, 0.9)
			var a := g.randf() * TAU
			var pos := center + Vector3(cos(a) * r, 0.0, sin(a) * r)
			var sc := g.randf_range(0.75, 1.3)
			var basis := Basis(Vector3.UP, g.randf() * TAU).scaled(Vector3(sc, sc * g.randf_range(0.8, 1.3), sc))
			xf.append(Transform3D(basis, pos))
			var tc := tint * g.randf_range(0.82, 1.18)
			if g.randf() < 0.3:  # sunlit yellow-green tips here and there
				tc = tc.lerp(Color(0.62, 0.62, 0.26), 0.35)
			cols.append(tc)
		if t != "forest" and g.randf() < (0.9 if t == "hills" else 0.5):
			for i in g.randi_range(1, 3):
				var r2 := g.randf_range(0.3, 0.85)
				var a2 := g.randf() * TAU
				var s2 := g.randf_range(0.6, 1.4)
				var bp := Basis(Vector3.UP, g.randf() * TAU).scaled(Vector3(s2, s2 * 0.55, s2 * g.randf_range(0.7, 1.0)))
				peb.append(Transform3D(bp, center + Vector3(cos(a2) * r2, 0.0, sin(a2) * r2)))
	_grass_mi = _multi(_tuft_mesh(), xf, cols)
	var pm := SphereMesh.new()
	pm.radius = 0.025
	pm.height = 0.05
	pm.radial_segments = 6
	pm.rings = 3
	var stone := StandardMaterial3D.new()
	stone.albedo_color = Color(0.6, 0.58, 0.54)
	stone.roughness = 0.95
	pm.material = stone
	_pebble_mi = _multi(pm, peb, [])


func _multi(mesh: Mesh, xf: Array, cols: Array) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = not cols.is_empty()
	mm.mesh = mesh
	mm.instance_count = xf.size()
	for i in xf.size():
		mm.set_instance_transform(i, xf[i])
		if mm.use_colors:
			mm.set_instance_color(i, cols[i])
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi


## One tuft: seven tapered blades fanned around the centre, dark at the root and light at the tip.
func _tuft_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for k in 7:
		var a := k * TAU / 7.0 + 0.3
		var lean := Vector3(cos(a), 0, sin(a)) * 0.03
		var side := Vector3(-sin(a), 0, cos(a)) * 0.016
		var h := 0.1 if k % 2 == 0 else 0.078
		var root := Vector3(cos(a), 0, sin(a)) * 0.008
		st.set_normal(Vector3.UP)
		st.set_color(Color(0.62, 0.64, 0.58))
		st.add_vertex(root - side)
		st.add_vertex(root + side)
		st.set_color(Color(0.95, 0.98, 0.85))
		st.add_vertex(root + lean + Vector3(0, h, 0))
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/grass.gdshader")
	var mesh := st.commit()
	mesh.surface_set_material(0, mat)
	return mesh


var _cloud_noise: ImageTexture
var _cloud_plane: MeshInstance3D


## Drifting cloud shadows over the whole map (shaders/cloud_shadows.gdshader), between the territory fills (+0.03)
## and the borders (+0.042); drawn after the fills.
func _cloud_shadows() -> void:
	if _cloud_plane != null:
		return
	_cloud_plane = MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(140, 140)
	_cloud_plane.mesh = pm
	_cloud_plane.position = Vector3(0, 0.036, 0)
	_cloud_plane.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/cloud_shadows.gdshader")
	m.set_shader_parameter("cloud_noise", _cloud_tex())
	m.render_priority = 1
	_cloud_plane.material_override = m
	add_child(_cloud_plane)


## Soft round cloud shapes for the drifting cloud shadows (terrain and water share it). Built synchronously:
## a NoiseTexture2D fills in on a thread and samples as white until then.
func _cloud_tex() -> ImageTexture:
	if _cloud_noise == null:
		var n := FastNoiseLite.new()
		n.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		n.seed = 4242
		n.frequency = 0.012
		n.fractal_octaves = 3
		var img: Image = n.get_seamless_image(256, 256, false, false, 0.1, true)
		img.generate_mipmaps()
		_cloud_noise = ImageTexture.create_from_image(img)
	return _cloud_noise


## Seamless noise for the ground and water shaders, built synchronously: a NoiseTexture2D fills in on a thread
## and samples as white until then, so the meadow patches popped in late (or not at all in a first frame).
func _noise_tex(freq: float, octaves: int, seed_: int) -> ImageTexture:
	var n := FastNoiseLite.new()
	n.seed = seed_
	n.frequency = freq / 64.0
	n.fractal_octaves = octaves
	var img: Image = n.get_seamless_image(256, 256, false, false, 0.1, true)
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


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
	_build_bay()


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


## A pillar of light from the sci-fi capital's spire into the sky (reference frame 2), in the state's colour,
## slowly breathing; drawn without depth writes so it reads as light, not a solid.
func _sky_beam(holder: Node3D, owner: int) -> void:
	var col := state_color(owner).lerp(Color(0.7, 0.9, 1.0), 0.45)
	for layer in [[0.05, 1.0], [0.16, 0.28]]:  # a bright core and a soft halo
		var mi := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = layer[0] * 0.6
		cm.bottom_radius = layer[0]
		cm.height = 14.0
		cm.radial_segments = 12
		cm.cap_top = false
		cm.cap_bottom = false
		mi.mesh = cm
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		m.no_depth_test = false
		m.albedo_color = Color(col.r, col.g, col.b, layer[1])
		mi.material_override = m
		mi.position = Vector3(0, 2.2 + 7.0, 0)
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		holder.add_child(mi)
		var tw := mi.create_tween().set_loops()
		tw.tween_property(m, "albedo_color:a", layer[1] * 0.55, 1.6).set_trans(Tween.TRANS_SINE)
		tw.tween_property(m, "albedo_color:a", layer[1], 1.6).set_trans(Tween.TRANS_SINE)


## Guards of the owner's era drilling in front of the capital gate (reference frame 4: soldiers in the castle yard
## and at the gate), small and animated like the field armies.
func _place_guards(c: Dictionary, holder: Node3D, rot: float) -> void:
	var sq := evolved("squad", int(c["owner"]))
	if sq == "":
		return
	var fwd := Vector3(sin(rot), 0, cos(rot))  # the model's −Y front in Godot space after the turn
	var side := Vector3(fwd.z, 0, -fwd.x)
	var anim: Array = []
	for k in [-1, 1]:
		var g := spawn(sq, holder, fwd * 0.78 + side * 0.34 * k, rot, 0.5)
		if g:
			_animate_troops(g, false, anim)


## The farmstead of an owner's era: a stone cottage (DL1–5), a panel house with greenhouses (DL6–7), a neon habitat
## pod (DL8+); "" for no owner.
func _homestead(owner: int, side: String) -> String:
	if owner <= Types.NOBODY or owner >= sim.states.size():
		return ""
	var dl: int = int(sim.states[owner]["dev_level"])
	var name := "homestead_scifi_" if dl >= 8 else ("homestead_modern_" if dl >= 6 else "homestead_")
	return name + side if has_model(name + side) else ""


## A later-era model of a production building: "<kind>_scifi_<side>" from DL8, "<kind>_modern_<side>" from DL6;
## "" when the owner's era has none (the base model is used).
func _era_model(kind: String, owner: int, side: String) -> String:
	if owner <= Types.NOBODY or owner >= sim.states.size():
		return ""
	var dl: int = int(sim.states[owner]["dev_level"])
	for name in (["%s_scifi_%s" % [kind, side]] if dl >= 8 else []) + (["%s_modern_%s" % [kind, side]] if dl >= 6 else []):
		if has_model(name):
			return name
	return ""


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


## Raivite vein: a cluster of glowing blue crystals on a rocky outcrop (until a baked model exists).
func _place_vein(holder: Node3D) -> void:
	var rock := StandardMaterial3D.new()
	rock.albedo_color = Color(0.45, 0.43, 0.4)
	var glow := StandardMaterial3D.new()
	glow.albedo_color = Color(0.12, 0.42, 1.0)
	glow.metallic = 0.3
	glow.roughness = 0.15
	glow.emission_enabled = true
	glow.emission = Color(0.05, 0.3, 0.95)
	glow.emission_energy_multiplier = 0.7
	var base := MeshInstance3D.new()
	var bm := CylinderMesh.new()
	bm.top_radius = 0.42
	bm.bottom_radius = 0.55
	bm.height = 0.14
	bm.radial_segments = 7
	bm.material = rock
	base.mesh = bm
	base.position.y = 0.07
	holder.add_child(base)
	for i in 7:
		var cr := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.0
		cm.bottom_radius = 0.07 + 0.03 * float(i % 3)
		cm.height = 0.35 + 0.12 * float((i * 5) % 4)
		cm.radial_segments = 6
		cm.material = glow
		cr.mesh = cm
		var a := TAU * i / 7.0
		var r := 0.0 if i == 0 else 0.22
		cr.position = Vector3(cos(a) * r, 0.14 + cm.height / 2.0, sin(a) * r)
		cr.rotation = Vector3(sin(a) * 0.35 * (1 if i else 0), 0, cos(a) * 0.35 * (1 if i else 0))
		holder.add_child(cr)
	var light := OmniLight3D.new()
	light.light_color = Color(0.4, 0.75, 1.0)
	light.omni_range = 1.4
	light.light_energy = 0.8
	light.position.y = 0.5
	holder.add_child(light)


## Dark Lake: a still black-violet pool with an oily sheen — dormant oil (canon §5.1).
func _place_dark_lake(holder: Node3D) -> void:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.07, 0.06, 0.12)
	m.metallic = 0.6
	m.roughness = 0.08
	var pool := MeshInstance3D.new()
	var pm := CylinderMesh.new()
	pm.top_radius = 0.62
	pm.bottom_radius = 0.62
	pm.height = 0.03
	pm.radial_segments = 9
	pm.material = m
	pool.mesh = pm
	pool.position.y = 0.02
	holder.add_child(pool)
	for o in [Vector3(-0.55, 0, 0.3), Vector3(0.5, 0, -0.35), Vector3(0.1, 0, 0.6)]:
		spawn("rock", holder, o, rng.randf() * TAU, 0.9)


## Oil: a timber derrick over the black pool (until a baked model exists).
func _place_derrick(holder: Node3D) -> void:
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.42, 0.28, 0.16)
	var top := Vector3(0.0, 1.05, 0.0)
	for k in 4:
		var a := TAU * k / 4.0 + PI / 4.0
		var foot := Vector3(cos(a) * 0.32, 0.0, sin(a) * 0.32)
		var leg := MeshInstance3D.new()
		var lm := CylinderMesh.new()
		lm.top_radius = 0.025
		lm.bottom_radius = 0.035
		lm.height = foot.distance_to(top)
		lm.material = wood
		leg.mesh = lm
		var yv := (top - foot).normalized()
		var xv := yv.cross(Vector3.FORWARD).normalized()
		leg.basis = Basis(xv, yv, xv.cross(yv))
		leg.position = (foot + top) / 2.0
		holder.add_child(leg)
	var cap := MeshInstance3D.new()
	var cm := BoxMesh.new()
	cm.size = Vector3(0.16, 0.08, 0.16)
	cm.material = wood
	cap.mesh = cm
	cap.position = top
	holder.add_child(cap)


## Factory (canon §5.1, «кирпичный цех» of the early eras): a brick hall under a sawtooth roof, two chimneys
## with a lazy plume of light smoke.
func _place_factory(holder: Node3D) -> void:
	var brick := _flat_mat(Color(0.62, 0.3, 0.22))
	var roof := _flat_mat(Color(0.32, 0.33, 0.36))
	var trim := _flat_mat(Color(0.86, 0.8, 0.68))
	var glass := _flat_mat(Color(0.95, 0.8, 0.45))
	var root := Node3D.new()
	root.rotation.y = 0.35
	holder.add_child(root)
	_box(root, Vector3(0.86, 0.34, 0.5), Vector3(0.05, 0.17, 0.05), brick)
	_box(root, Vector3(0.9, 0.04, 0.54), Vector3(0.05, 0.35, 0.05), trim)
	for i in 3:
		var tooth := MeshInstance3D.new()
		var pm := PrismMesh.new()
		pm.left_to_right = 0.0  # a sawtooth: the steep side faces the light
		pm.size = Vector3(0.28, 0.18, 0.5)
		pm.material = roof
		tooth.mesh = pm
		tooth.position = Vector3(-0.24 + 0.29 * i, 0.46, 0.05)
		root.add_child(tooth)
	for i in 4:
		_box(root, Vector3(0.12, 0.12, 0.01), Vector3(-0.28 + 0.2 * i, 0.17, 0.305), glass)
	for i in 2:
		var ch := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.05
		cm.bottom_radius = 0.07
		cm.height = 0.85
		cm.radial_segments = 10
		cm.material = brick
		ch.mesh = cm
		var cp := Vector3(-0.3 + 0.18 * i, 0.425, -0.22)
		ch.position = cp
		root.add_child(ch)
		_box(root, Vector3(0.13, 0.04, 0.13), cp + Vector3(0, 0.42, 0), trim)
		var sm := CPUParticles3D.new()
		sm.amount = 7
		sm.lifetime = 2.6
		sm.direction = Vector3(0.3, 1, 0)
		sm.spread = 8.0
		sm.initial_velocity_min = 0.18
		sm.initial_velocity_max = 0.28
		sm.gravity = Vector3(0.08, 0.03, 0)
		sm.scale_amount_curve = _curve(0.3, 1.2)
		sm.color_ramp = _ramp([0.0, 0.2, 1.0], [Color(0.75, 0.74, 0.72, 0.0), Color(0.78, 0.77, 0.76, 0.5), Color(0.9, 0.9, 0.92, 0.0)])
		var q := QuadMesh.new()
		q.size = Vector2(0.4, 0.4)
		if _smoke_mat == null:
			_smoke_mat = _fx_mat(_puff_tex(), false)
		q.material = _smoke_mat
		sm.mesh = q
		sm.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		sm.position = cp + Vector3(0, 0.46, 0)
		sm.preprocess = 2.6
		root.add_child(sm)


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
	if _blazing.has(c["id"]):
		_still_sails(c["id"], true)


## A burning windmill stops turning.
func _still_sails(hex: int, still: bool) -> void:
	var holder: Node3D = _hex_props.get(hex)
	if holder == null:
		return
	for obj in _sails:
		if is_instance_valid(obj) and holder.is_ancestor_of(obj as Node):
			(obj as Node).set_meta("still", still)


func _place_hex_props_into(c: Dictionary, holder: Node3D) -> void:
	rng.seed = 7 + int(c["id"]) * 7919
	if camp_hexes.has(int(c["id"])):
		_place_camp(int(c["id"]), holder)
		return
	if not Types.is_passable(c):
		if c["terrain"] == "mountain":
			spawn("mountain", holder, Vector3.ZERO, rng.randf() * TAU, rng.randf_range(1.5, 1.75))  # massifs that rise over the map, as in the reference
		elif c["terrain"] == "water":
			_place_ship(c, holder)
		return
	var p := Vector3.ZERO
	var side := _faction_suffix(c["owner"])
	match c["kind"]:
		"capital":
			var rm := evolved("residence", c["owner"])
			if rm != "":
				var early := rm.contains("_dl1_") or rm.contains("_dl2_") or rm.contains("_dl3_")
				spawn(rm, holder, p, 0.3 if c["owner"] == Types.PLAYER else PI, 1.3 if early else 1.0, int(c["owner"]))  # small early buildings fill the hex
				_place_guards(c, holder, 0.3 if c["owner"] == Types.PLAYER else PI)
				if c["owner"] == Types.PLAYER and (rm.contains("_dl8_") or rm.contains("_dl9_") or rm.contains("_dl10_")):  # one beam, the player's
					_sky_beam(holder, int(c["owner"]))
			else:
				var model := "castle" if c["owner"] == Types.PLAYER else ("castle_green" if c["owner"] == MapGen.HAMLETS else "castle_red")
				spawn(model, holder, p, 0.3 if c["owner"] == Types.PLAYER else PI, 1.35)
			_place_fort(c, holder)
			return
		"city":
			var cm := evolved("city", c["owner"])
			if cm != "":
				spawn(cm, holder, p, rng.randf_range(-0.25, 0.25), 1.15, int(c["owner"]))  # tall towers stay at the back
			else:
				var hm := "house_blue" if c["owner"] == Types.PLAYER else ("house_green" if c["owner"] == MapGen.HAMLETS else "house_red")
				for o in [Vector3(-0.3, 0, 0.15), Vector3(0.3, 0, -0.25), Vector3(0.1, 0, 0.4), Vector3(-0.25, 0, -0.35)]:
					spawn(hm, holder, p + o, rng.randf() * TAU, 1.05)
			_place_fort(c, holder)
			return
		"farm":
			var era := _era_model("farm", int(c["owner"]), side)
			if era != "":  # DL6–7 strip fields and a silo, DL8 hydroponics (reference frame 2)
				spawn(era, holder, p, 0.2, 1.0)
				return
			# a patchwork of walled fields round the mill (reference frame 3): the big field, two smaller plots turned
			# a little against it, a hay barn
			# (the field is ~0.96 × 0.76 at scale 1: these sizes keep the three apart and inside the hex)
			spawn("wheat_field", holder, p + Vector3(0.16, 0, 0.16), 0.0, 0.72)
			spawn("wheat_field", holder, p + Vector3(-0.42, 0, 0.28), PI, 0.42)
			spawn("wheat_field", holder, p + Vector3(0.46, 0, -0.32), 0.0, 0.45)
			spawn("windmill", holder, p + Vector3(-0.45, 0, -0.3), 0.4, 0.95)
			_place_sentries(c, holder, p + Vector3(-0.02, 0, 0.62))
			_place_fort(c, holder)
			return
		"mine":
			var era_m := _era_model("mine", int(c["owner"]), side)
			spawn(era_m if era_m != "" else "mine", holder, p, 0.2, 1.0 if era_m != "" else 1.1)  # DL8: a raivite crystal pit
			_place_sentries(c, holder, p + Vector3(0.36, 0, 0.56))
			_place_fort(c, holder)
			return
		"raivite_vein":
			_place_vein(holder)
			_place_fort(c, holder)
			return
		"dark_lake":
			_place_dark_lake(holder)
			_place_fort(c, holder)
			return
		"oil":
			_place_dark_lake(holder)
			_place_derrick(holder)
			_place_fort(c, holder)
			return
		"factory":
			_place_factory(holder)
			_place_fort(c, holder)
			return
		"port":
			var era_p := _era_model("port", int(c["owner"]), side)  # a container port (DL6–7), a hover dock (DL8+)
			if era_p != "" or has_model("port"):
				spawn(era_p if era_p != "" else "port", holder, p, _water_side(c), 1.0)
				_place_fort(c, holder)
				return
		"military_base":
			var era_b := _era_model("military_base", int(c["owner"]), side)  # a concrete compound (DL6–7), a neon one (DL8+)
			if era_b != "" or has_model("military_base"):
				spawn(era_b if era_b != "" else "military_base", holder, p, 0.3, 1.0)
				_place_fort(c, holder)
				return
	var biome: String = c.get("biome", "meadow")
	if biome != "meadow" and String(c["terrain"]) in ["plain", "forest", "hills"]:
		_place_biome_props(c, holder, p, biome)
		_place_fort(c, holder)
		if c["owner"] != Types.NOBODY and rng.randf() < _banner_chance(int(c["owner"])):
			spawn("banner_" + side, holder, p + Vector3(rng.randf_range(-0.4, 0.4), 0, rng.randf_range(-0.4, 0.4)), 0.0, 1.0, int(c["owner"]))
		return
	match c["terrain"]:
		"forest":
			# a thick wood as in the reference frames: more, closer trees, a few tall ones above the canopy
			for i in rng.randi_range(12, 16):
				var off := Vector3(rng.randf_range(-0.66, 0.66), 0, rng.randf_range(-0.66, 0.66))
				var tall := rng.randf() < 0.2
				spawn("tree_pine" if rng.randf() < 0.8 else "tree_round", holder, p + off, rng.randf() * TAU, rng.randf_range(1.2, 1.45) if tall else rng.randf_range(0.8, 1.15))
			for i in rng.randi_range(1, 2):
				spawn("bush", holder, p + Vector3(rng.randf_range(-0.6, 0.6), 0, rng.randf_range(-0.6, 0.6)), rng.randf() * TAU, rng.randf_range(1.0, 1.25))
		"hills":
			if has_model("crag"):  # a grey rocky outcrop with pines (the reference frames' cliffs)
				spawn("crag", holder, p + Vector3(rng.randf_range(-0.08, 0.08), 0, rng.randf_range(-0.08, 0.08)), rng.randf() * TAU, rng.randf_range(1.3, 1.5))
			else:
				for i in 3:
					spawn("rock", holder, p + Vector3(rng.randf_range(-0.5, 0.5), 0, rng.randf_range(-0.5, 0.5)), rng.randf() * TAU, rng.randf_range(1.2, 2.0))
				spawn("tree_pine", holder, p + Vector3(0.3, 0, 0.3), 0.0, 1.0)
		_:
			var district := _era_model("district", int(c["owner"]), side)
			if district != "":  # the built-up land of the sci-fi stage (reference frame 2): a neon district, a tree or two
				var variant: String = ["", "_b", "_c"][int(c["id"]) % 3]  # three layouts so neighbouring hexes don't repeat
				var dname := district.replace("district_scifi_", "district_scifi%s_" % variant)
				spawn(dname if has_model(dname) else district, holder, p, rng.randi_range(0, 5) * PI / 3.0, 1.0)
				for i in rng.randi_range(0, 2):
					spawn("tree_round", holder, p + Vector3(rng.randf_range(-0.6, 0.6), 0, rng.randf_range(-0.6, 0.6)), rng.randf() * TAU, 0.7)
				_place_fort(c, holder)
				if rng.randf() < _banner_chance(int(c["owner"])):
					spawn("banner_" + side, holder, p + Vector3(rng.randf_range(-0.4, 0.4), 0, rng.randf_range(-0.4, 0.4)), 0.0, 1.0, int(c["owner"]))
				return
			if _front_gun(c, holder, p):
				_place_fort(c, holder)
				return
			var hs := _homestead(int(c["owner"]), side)
			if hs != "" and rng.randf() < 0.55:
				# settled countryside (the reference frames): a farmstead in the owner's colours and era on open land
				spawn(hs, holder, p + Vector3(rng.randf_range(-0.25, 0.25), 0, rng.randf_range(-0.25, 0.25)), rng.randf() * TAU, 1.25)
			if hs != "" and not hs.begins_with("homestead_scifi") and rng.randf() < 0.4:
				# a small field on the near edge (reference frame 3: the player's land is patched with fields): a walled
				# wheat plot up to DL5, a fenced crop field with a tractor from DL6; half the size of a farm hex's
				# field, so a real farm still reads as one
				var fa := (1.0 + 2.0 * rng.randi_range(0, 2)) * PI / 6.0  # an edge midpoint at 30°, 90° or 150°
				var plot := "crop_field" if hs.begins_with("homestead_modern") and has_model("crop_field") else "wheat_field"
				spawn(plot, holder, p + Vector3(cos(fa), 0, sin(fa)) * 0.5, -fa + PI / 2.0, 0.5)
			# a copse crowding the far edge (reference frame 3: woods fill every gap between the farms and towns);
			# behind the centre, so it never hides a farmstead or an army from the camera at +Z
			var ca := (7.0 + 2.0 * rng.randi_range(0, 2)) * PI / 6.0  # an edge midpoint at 210°, 270° or 330°
			var cn := rng.randi_range(4, 7)
			# trees never stand in front of a capital, a town or a farm behind this hex (they would hide its front):
			# no copse at such an edge, and the lone trees keep to the near half of the hex
			var busy := false
			for k in [7.0, 9.0, 11.0]:
				var a: float = k * PI / 6.0
				var nb := id_at_world(p + Vector3(cos(a), 0, sin(a)) * SQ3)
				if nb >= 0 and sim.cells[nb]["kind"] != "plain":
					busy = true
					if is_equal_approx(a, ca):
						cn = 0
			var cc := p + Vector3(cos(ca), 0, sin(ca)) * 0.58
			for i in cn:
				var off := Vector3(rng.randf_range(-0.16, 0.16), 0, rng.randf_range(-0.24, 0.24)).rotated(Vector3.UP, -ca)
				spawn("tree_pine" if rng.randf() < 0.8 else "tree_round", holder, cc + off, rng.randf() * TAU, rng.randf_range(0.75, 1.1))
			for i in rng.randi_range(1, 3):
				var off := Vector3(rng.randf_range(-0.6, 0.6), 0, rng.randf_range(-0.05 if busy else -0.6, 0.6))
				spawn("tree_pine" if rng.randf() < 0.6 else "tree_round", holder, p + off, rng.randf() * TAU, rng.randf_range(0.7, 1.0))
			if rng.randf() < 0.55:
				spawn("bush", holder, p + Vector3(rng.randf_range(-0.55, 0.55), 0, rng.randf_range(-0.55, 0.55)), rng.randf() * TAU, rng.randf_range(1.0, 1.3))
			if rng.randf() < 0.45:
				spawn("flowers", holder, p + Vector3(rng.randf_range(-0.5, 0.5), 0, rng.randf_range(-0.5, 0.5)), rng.randf() * TAU, rng.randf_range(1.0, 1.3))
	_place_fort(c, holder)
	if c["owner"] != Types.NOBODY and rng.randf() < _banner_chance(int(c["owner"])):
		spawn("banner_" + side, holder, p + Vector3(rng.randf_range(-0.4, 0.4), 0, rng.randf_range(-0.4, 0.4)), 0.0, 1.0, int(c["owner"]))


## Siege works along a front (reference frames 1 and 3: catapults stand on the land by the border, aimed across
## it): an open hex of the player or of the state at war with them that touches the other side gets, one time in
## two, a big siege engine of its owner's era turned toward the enemy, with a few trees behind it. True if placed.
func _front_gun(c: Dictionary, holder: Node3D, p: Vector3) -> bool:
	var own: int = int(c["owner"])
	if at_war_with < 0 or not (own == Types.PLAYER or own == at_war_with) or (int(c["id"]) * 5) % 2 == 1:
		return false
	var foe: int = at_war_with if own == Types.PLAYER else Types.PLAYER
	var aim := Vector3.ZERO
	for nb in sim.neighbors[c["id"]]:
		if nb >= 0 and Types.is_passable(sim.cells[nb]) and owner_of(sim.cells[nb]) == foe:
			aim += cell_world(nb) - p
	if aim == Vector3.ZERO:
		return false
	var dl: int = int(sim.states[own]["dev_level"]) if own < sim.states.size() else 1
	var gun := "rocket_launcher" if dl >= 8 else ("howitzer" if dl >= 6 else ("cannon" if dl >= 4 else "catapult"))
	if not has_model(gun):
		return false
	var yaw := atan2(aim.x, aim.z) + PI  # the models face −Z; turn the muzzle toward the enemy
	spawn(gun, holder, p + Vector3(rng.randf_range(-0.12, 0.12), 0, rng.randf_range(-0.12, 0.12)), yaw, 1.45)
	var back := -aim.normalized()
	for i in rng.randi_range(2, 3):
		var off := back * rng.randf_range(0.45, 0.62) + Vector3(back.z, 0, -back.x) * rng.randf_range(-0.4, 0.4)
		spawn("tree_pine", holder, p + off, rng.randf() * TAU, rng.randf_range(0.75, 1.0))
	spawn("banner_" + _faction_suffix(own), holder, p + back * 0.3 + Vector3(back.z, 0, -back.x) * 0.25, 0.0, 1.0, own)
	return true


## A pair of sentries of the owner's era guarding a farm or a quarry (reference frames 3–4: single soldiers stand
## about the fields and the quarry yard), on two hexes in three; none on unowned land.
func _place_sentries(c: Dictionary, holder: Node3D, at: Vector3) -> void:
	if int(c["owner"]) <= Types.NOBODY or (int(c["id"]) * 7) % 3 == 0:
		return
	var model := evolved("sentry", int(c["owner"]))
	if model != "":
		spawn(model, holder, at, rng.randf_range(-0.4, 0.4), 0.98)


## How often an owned open hex flies a banner: thicker on the land of the state at war with the player (reference
## frame 3: the enemy side bristles with red banners).
func _banner_chance(owner: int) -> float:
	return 0.55 if owner == at_war_with and owner != Types.PLAYER else 0.3


## A warship of a coastal state on some water hexes along its shore (reference frame 1: ships under blue sails),
## sitting low in the water and rocking gently.
func _place_ship(c: Dictionary, holder: Node3D) -> void:
	if rng.randf() > 0.45:
		return
	for nid in sim.neighbors[c["id"]]:
		if nid < 0:
			continue
		var own: int = owner_of(sim.cells[nid])
		if own <= Types.NOBODY or not Types.is_passable(sim.cells[nid]):
			continue
		var name := _ship_model(own)
		if name == "":
			return
		var ship := spawn(name, holder, Vector3(rng.randf_range(-0.25, 0.25), -0.08, rng.randf_range(-0.25, 0.25)), (PI / 2.0 if rng.randf() < 0.5 else -PI / 2.0) + rng.randf_range(-0.7, 0.7), 1.75)  # bow toward or away from the camera: the sails face it
		if ship:
			var tw := ship.create_tween().set_loops()
			var r0 := ship.rotation
			tw.tween_property(ship, "rotation", r0 + Vector3(0.05, 0, 0.03), 1.8 + rng.randf()).set_trans(Tween.TRANS_SINE)
			tw.tween_property(ship, "rotation", r0 - Vector3(0.05, 0, 0.03), 1.8 + rng.randf()).set_trans(Tween.TRANS_SINE)
		return


## Plain / forest / hills props of a non-meadow biome: dense dark pines in the taiga; grass, shrubs and a few
## broad-leaved trees in the steppe; rocks and dry scrub in the badlands.
func _place_biome_props(c: Dictionary, holder: Node3D, p: Vector3, biome: String) -> void:
	var t: String = c["terrain"]
	var rnd := func(r: float) -> Vector3:
		return p + Vector3(rng.randf_range(-r, r), 0, rng.randf_range(-r, r))
	match biome:
		"taiga":
			var n := rng.randi_range(10, 14) if t == "forest" else (rng.randi_range(3, 5) if t == "plain" else 2)
			for i in n:
				spawn("tree_pine", holder, rnd.call(0.64), rng.randf() * TAU, rng.randf_range(0.9, 1.45))
			if t == "hills" or rng.randf() < 0.4:
				for i in (3 if t == "hills" else 1):
					spawn("rock", holder, rnd.call(0.5), rng.randf() * TAU, rng.randf_range(1.0, 1.8))
		"steppe":
			if t == "forest":
				for i in rng.randi_range(4, 6):
					spawn("tree_round", holder, rnd.call(0.6), rng.randf() * TAU, rng.randf_range(0.8, 1.15))
			elif t == "hills":
				for i in 3:
					spawn("rock", holder, rnd.call(0.5), rng.randf() * TAU, rng.randf_range(1.1, 1.8))
			if t != "hills" or rng.randf() < 0.5:
				for i in rng.randi_range(1, 3):
					spawn("bush", holder, rnd.call(0.58), rng.randf() * TAU, rng.randf_range(0.8, 1.2))
			if t == "plain" and rng.randf() < 0.6:
				spawn("flowers", holder, rnd.call(0.5), rng.randf() * TAU, rng.randf_range(1.0, 1.4))
		"badlands":
			var rocks := 4 if t == "hills" else (2 if t == "plain" else 1)
			for i in rocks:
				spawn("rock", holder, rnd.call(0.55), rng.randf() * TAU, rng.randf_range(1.2, 2.3))
			var scrub := rng.randi_range(3, 5) if t == "forest" else rng.randi_range(0, 1)
			for i in scrub:
				spawn("bush", holder, rnd.call(0.6), rng.randf() * TAU, rng.randf_range(0.7, 1.0))
			if t == "forest" and rng.randf() < 0.6:
				spawn("tree_round", holder, rnd.call(0.5), rng.randf() * TAU, rng.randf_range(0.6, 0.85))


func _build_horizon() -> void:
	_bay_spots = []
	var ring_mat := StandardMaterial3D.new()
	ring_mat.albedo_color = Color(0.13, 0.2, 0.12)  # dark forest floor, as the wooded rim of the references
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
			if d <= rr + 2:
				if near:  # below the player's land the open sea of the bay shows instead (reference frame 1)
					if d == rr + 1 and roll < 0.3:
						_bay_spots.append([q, r, p])
					continue
				# the unexplored land next to the open world (reference frame 1): dark slate hexes with a faint grid,
				# drifting low clouds and a peak here and there
				var tile := MeshInstance3D.new()
				var tm := CylinderMesh.new()
				tm.top_radius = 0.985
				tm.bottom_radius = 0.985
				tm.height = 1.0
				tm.radial_segments = 6
				tile.mesh = tm
				tile.rotation.y = PI / 6.0
				tile.position = p + Vector3(0, -0.7 - rng.randf() * 0.04, 0)  # a step below the open world (its cliffs and waterfalls show), just above the sea
				tile.material_override = _fog_hex_mat()
				_horizon_root.add_child(tile)
				if d == rr + 2 and roll < 0.3:
					spawn("mountain", _horizon_root, p + Vector3(0, -0.2, 0), rng.randf() * TAU, rng.randf_range(1.5, 2.4))
				elif rng.randf() < 0.3:
					_cloud(p + Vector3(rng.randf_range(-0.5, 0.5), rng.randf_range(0.25, 0.7), rng.randf_range(-0.5, 0.5)), rng.randf_range(1.4, 2.4))
				continue
			if near:
				for i in 5:
					spawn("tree_pine" if rng.randf() < 0.7 else "tree_round", _horizon_root, p + Vector3(rng.randf_range(-0.7, 0.7), -0.1, rng.randf_range(-0.7, 0.7)), rng.randf() * TAU, rng.randf_range(0.8, 1.1))
			elif d <= rr + 2 and roll < 0.5:
				spawn("mountain", _horizon_root, p + Vector3(0, -0.15, 0), rng.randf() * TAU, rng.randf_range(1.7, 2.8))
			elif d <= rr + 2:
				for i in 5:
					spawn("tree_pine", _horizon_root, p + Vector3(rng.randf_range(-0.7, 0.7), -0.1, rng.randf_range(-0.7, 0.7)), rng.randf() * TAU, rng.randf_range(0.9, 1.4))
			var base := MeshInstance3D.new()
			var cm := CylinderMesh.new()
			cm.top_radius = 1.16  # overlap: with the exact radius the sky showed through as blue triangles
			cm.bottom_radius = 1.16
			cm.height = 1.0
			cm.radial_segments = 6
			base.mesh = cm
			base.position = p + Vector3(0, -0.62, 0)
			base.material_override = ring_mat
			_horizon_root.add_child(base)
			if not near and rng.randf() < 0.3 + 0.1 * (d - rr - 1):  # a lighter veil: the reference keeps its peaks in view
				_cloud(p + Vector3(rng.randf_range(-0.5, 0.5), rng.randf_range(1.0, 2.6), rng.randf_range(-0.5, 0.5)), rng.randf_range(2.5, 4.5))


## The warship of a state's era: a sailing ship under its colours (DL1–5), a steel destroyer (DL6–7), a hover
## cruiser with neon strips (DL8+); "" when there is no model.
func _ship_model(own: int) -> String:
	var side := _faction_suffix(own)
	var dl: int = int(sim.states[own]["dev_level"]) if own >= 0 and own < sim.states.size() else 1
	for name in (["cruiser_scifi_" + side] if dl >= 8 else []) + (["destroyer_" + side] if dl >= 6 else []) + ["warship_" + side]:
		if has_model(name):
			return name
	return ""


## The bay's warships, one per recorded sea hex, each in its state's current era; a per-hex seed keeps them in
## place across rebuilds.
func _build_bay() -> void:
	for c in _bay_root.get_children():
		c.queue_free()
	for spot in _bay_spots:
		var lr := RandomNumberGenerator.new()
		lr.seed = int(spot[0]) * 73 + int(spot[1]) * 19 + 5
		_horizon_ship(int(spot[0]), int(spot[1]), spot[2], lr)


## A warship of the coastal state off the world's near shore (reference frame 1: ships under the state's sails in
## the bay below the land), rocking on the open sea.
func _horizon_ship(q: int, r: int, p: Vector3, lr: RandomNumberGenerator) -> void:
	for d in 6:
		var nb: int = sim.id_at(q + int(DIRS[d].x), r + int(DIRS[d].y))
		if nb < 0:
			continue
		var own := owner_of(sim.cells[nb])
		if own <= Types.NOBODY or not Types.is_passable(sim.cells[nb]):
			continue
		var name := _ship_model(own)
		if name == "":
			return
		var ship := spawn(name, _bay_root, p + Vector3(lr.randf_range(-0.3, 0.3), -0.26, lr.randf_range(-0.2, 0.2)), (PI / 2.0 if lr.randf() < 0.5 else -PI / 2.0) + lr.randf_range(-0.6, 0.6), 1.75)
		if ship:
			var tw := ship.create_tween().set_loops()
			var r0 := ship.rotation
			tw.tween_property(ship, "rotation", r0 + Vector3(0.05, 0, 0.03), 1.8 + lr.randf()).set_trans(Tween.TRANS_SINE)
			tw.tween_property(ship, "rotation", r0 - Vector3(0.05, 0, 0.03), 1.8 + lr.randf()).set_trans(Tween.TRANS_SINE)
		return


var _fog_mat: StandardMaterial3D


func _fog_hex_mat() -> StandardMaterial3D:
	if _fog_mat == null:
		_fog_mat = StandardMaterial3D.new()
		_fog_mat.albedo_color = Color(0.2, 0.22, 0.25)
		_fog_mat.roughness = 0.95
	return _fog_mat


var _cloud_mat: StandardMaterial3D

## World expansion (02 §17.1): every new hex starts under a cloud; `part_clouds` blows them away from the
## old border outward (`order`: hex ids, nearest first) over `seconds`.
var _veil := {}  # hex -> cloud node


func veil_hexes(ids: Array) -> void:
	for h in ids:
		var p := cell_world(int(h))
		var mi := _cloud(p + Vector3(0, 0.9, 0), 3.2, false)
		mi.material_override = _cloud_mat.duplicate()
		(mi.material_override as StandardMaterial3D).albedo_color = Color(0.93, 0.95, 0.98, 1.0)
		_veil[int(h)] = mi


func part_clouds(order: Array, seconds: float) -> void:
	var n := maxi(1, order.size())
	for i in order.size():
		var mi: MeshInstance3D = _veil.get(int(order[i]))
		if mi == null:
			continue
		_veil.erase(int(order[i]))
		var tw := mi.create_tween()
		tw.tween_interval(seconds * float(i) / float(n))
		var out := (mi.position - Vector3(0, mi.position.y, 0)).normalized() * 1.6
		tw.tween_property(mi, "position", mi.position + out + Vector3(0, 0.8, 0), 0.6).set_ease(Tween.EASE_IN)
		tw.parallel().tween_property(mi.material_override, "albedo_color:a", 0.0, 0.6)
		tw.tween_callback(mi.queue_free)


func _cloud(pos: Vector3, size: float, horizon := true) -> MeshInstance3D:
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
	(_horizon_root if horizon else _props_root.get_parent()).add_child(mi)
	return mi


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
	var washes := {}  # owner -> the strategic-zoom fill: the rim gradient spread over the whole hex (reference frame 1)
	var scorch := {}  # owner -> darkening layer under the fills (burnt ground under AI land, cooler under the player's)
	var hatch := {}
	var lines := {}
	var borders := {}
	var cores := {}
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
			# the reference frames (docs/reference): a light tint over the land that deepens toward the territory's
			# border — per territory, not per hex, so the inner hexes don't read as tiles
			var tc := Color(0.16, 0.33, 0.86) if own == Types.PLAYER else state_color(own).darkened(0.25)  # royal blue (measured against the reference), crimson
			var built: bool = own >= 0 and own < sim.states.size() and int(sim.states[own]["dev_level"]) >= 8
			var c_in := Color(tc.r, tc.g, tc.b, 0.08 if built else (0.07 if own == Types.PLAYER else 0.14))  # built-up sci-fi land: a lighter veil, the city shows
			var c_rim := Color(tc.r, tc.g, tc.b, 0.38 if built else 0.5)
			var rim := [false, false, false, false, false, false]
			for d in 6:
				var nb: int = sim.neighbors[c["id"]][d]
				if nb >= 0 and Types.is_passable(sim.cells[nb]) and owner_of(sim.cells[nb]) == own:
					continue
				var nc := center + Vector3(1.5 * DIRS[d].x, 0, SQ3 * (DIRS[d].y + DIRS[d].x / 2.0))
				for k in 6:
					if (pts[k] as Vector3).distance_to(nc) < 1.3:
						rim[k] = true
			var ws := _st(washes, own)
			var w_in := Color(tc.r, tc.g, tc.b, 0.08 if built else 0.14)
			for k in 6:
				ws.set_color(w_in); ws.add_vertex(center)
				ws.set_color(c_rim if rim[k] else w_in); ws.add_vertex(pts[k])
				ws.set_color(c_rim if rim[(k + 1) % 6] else w_in); ws.add_vertex(pts[(k + 1) % 6])
			# close up the glow hugs the border (reference frame 3: a narrow band, the land inside keeps its own
			# colours): a flat-tinted core and a band over the outer quarter of the radius fading from the rim inward
			var inner := _hex_pts(center, 0.74)
			for k in 6:
				var k2 := (k + 1) % 6
				st.set_color(c_in); st.add_vertex(center); st.add_vertex(inner[k]); st.add_vertex(inner[k2])
				var o1 := c_rim if rim[k] else c_in
				var o2 := c_rim if rim[k2] else c_in
				st.set_color(o1); st.add_vertex(pts[k])
				st.set_color(o2); st.add_vertex(pts[k2])
				st.set_color(c_in); st.add_vertex(inner[k2])
				st.set_color(o1); st.add_vertex(pts[k])
				st.set_color(c_in); st.add_vertex(inner[k2])
				st.set_color(c_in); st.add_vertex(inner[k])
			# a multiply layer under every fill: burnt ground for AI states, a cool deepening for the player
			var ss := _st(scorch, own)
			var sc := center - Vector3(0, 0.006, 0)
			var sp := _hex_pts(sc, 0.995)
			for k in 6:
				ss.add_vertex(sc); ss.add_vertex(sp[k]); ss.add_vertex(sp[(k + 1) % 6])
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
				_strip(_st(lines, own), e[0], e[1], 0.028, center.y + 0.005)
			else:
				var w := 0.12
				var prog := 1.0
				if ceremony_t >= 0.0 and flip_at.has(c["id"]):
					prog = clampf((ceremony_t - flip_at[c["id"]]) / 0.3, 0.0, 1.0)
				if prog > 0.0:
					_strip(_st(borders, own), e[0], e[0].lerp(e[1], prog), 0.2, center.y + 0.011)  # the coloured halo
					_strip(_st(cores, own), e[0], e[0].lerp(e[1], prog), 0.045, center.y + 0.013)  # the white-hot neon core
	for o in scorch:
		var m := StandardMaterial3D.new()
		m.blend_mode = BaseMaterial3D.BLEND_MODE_MUL
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.albedo_color = Color(0.72, 0.62, 0.6) if o == at_war_with else Color(0.86, 0.8, 0.78)
		if o >= 0 and o < sim.states.size() and o != at_war_with and int(sim.states[o]["dev_level"]) >= 8:
			m.albedo_color = Color(0.8, 0.85, 0.95)  # the sci-fi stage: built-up, cool steel-grey land (reference frame 2)
		elif o == Types.PLAYER:
			m.albedo_color = Color(0.96, 0.98, 1.0)  # a cool deepening: the land reads bluish without losing its colours
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		_add(scorch[o], m)
	_tint_mats = []
	_wash_mats = []
	for o in tints:
		var tm := _tint_mat(Color.WHITE, _tint_k * (1.0 - _wash_w))
		_tint_mats.append(tm)
		_add(tints[o], tm)
	for o in washes:
		var wm := _tint_mat(Color.WHITE, _tint_k * _wash_w)
		_wash_mats.append(wm)
		_add(washes[o], wm)
	for o in hatch:
		_add(hatch[o], _hatch_mat(state_color(o)))
	for o in lines:
		_add(lines[o], _glow_mat(state_color(o), 0.8, 0.5))  # the faint inner hex grid of the references
	for o in borders:
		var e := 2.6 if (o == Types.PLAYER or o == at_war_with) else 1.6  # strong enough to glow, still coloured
		_add(borders[o], _glow_mat(state_color(o), e * 0.8, 0.5))
	for o in cores:
		_add(cores[o], _glow_mat(state_color(o).lerp(Color.WHITE, 0.6), 3.2, 1.0))
	_build_roads()
	_sync_war_scars()


var _scars := {}  # occupied hex -> Node3D (smoke and embers)

## Occupied land smoulders (reference frame 3: the enemy side of the front is on fire): a dark smoke column, a small
## fire and a scorched patch on every hex held by another state's troops; gone once the hex is freed or annexed.
func _sync_war_scars() -> void:
	var want := {}
	for c in sim.cells:
		if Types.is_passable(c) and c["controller"] != c["owner"] and c["controller"] != Types.NOBODY and c["owner"] != Types.NOBODY:
			want[int(c["id"])] = true
	for h in _scars.keys():
		if not want.has(h):
			(_scars[h] as Node3D).queue_free()
			_scars.erase(h)
	for h in want:
		if _scars.has(h):
			continue
		var root := Node3D.new()
		var g := RandomNumberGenerator.new()
		g.seed = int(h) * 31 + 7
		root.position = cell_world(int(h)) + Vector3(g.randf_range(-0.35, 0.35), 0.0, g.randf_range(-0.35, 0.35))
		add_child(root)
		_scars[h] = root
		var patch := MeshInstance3D.new()
		var pm := CylinderMesh.new()
		pm.top_radius = 0.22
		pm.bottom_radius = 0.22
		pm.height = 0.004
		pm.radial_segments = 10
		var dm := StandardMaterial3D.new()
		dm.albedo_color = Color(0.1, 0.08, 0.07)
		dm.roughness = 1.0
		pm.material = dm
		patch.mesh = pm
		patch.position.y = 0.036
		root.add_child(patch)
		if _smoke_mat == null:
			_smoke_mat = _fx_mat(_puff_tex(), false)
		var sm := CPUParticles3D.new()
		sm.amount = 5  # a thin trail: the reference reads a war by its armies and banners, not by a pall of smoke
		sm.lifetime = 3.4
		sm.direction = Vector3(0.25, 1, 0)
		sm.spread = 8.0
		sm.initial_velocity_min = 0.25
		sm.initial_velocity_max = 0.4
		sm.gravity = Vector3(0.1, 0.04, 0)
		sm.scale_amount_curve = _curve(0.35, 1.6)
		sm.color_ramp = _ramp([0.0, 0.12, 0.55, 1.0], [Color(0.18, 0.15, 0.14, 0.0), Color(0.22, 0.19, 0.17, 0.42),
			Color(0.4, 0.38, 0.37, 0.18), Color(0.6, 0.6, 0.62, 0.0)])
		var q := QuadMesh.new()
		q.size = Vector2(0.42, 0.42)
		q.material = _smoke_mat
		sm.mesh = q
		sm.position.y = 0.25
		sm.preprocess = 3.4
		sm.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(sm)
		if g.randf() < 0.5:  # every other occupied hex still burns
			continue
		var fm := _fx_mat(_flame_tex(), false)
		fm.render_priority = 1
		var fl := CPUParticles3D.new()
		fl.amount = 7
		fl.lifetime = 0.55
		fl.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
		fl.emission_sphere_radius = 0.06
		fl.direction = Vector3.UP
		fl.spread = 8.0
		fl.initial_velocity_min = 0.2
		fl.initial_velocity_max = 0.35
		fl.gravity = Vector3(0, 0.7, 0)
		fl.scale_amount_curve = _curve(1.0, 0.25)
		fl.color_ramp = _ramp([0.0, 0.2, 0.6, 1.0], [Color(1.0, 0.8, 0.35, 0.0), Color(1.0, 0.6, 0.14, 1.0),
			Color(0.95, 0.3, 0.04, 0.85), Color(0.6, 0.08, 0.02, 0.0)])
		var fq := QuadMesh.new()
		fq.size = Vector2(0.2, 0.3)
		fq.material = fm
		fl.mesh = fq
		fl.position.y = 0.1
		fl.preprocess = 0.6
		fl.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(fl)


const ROAD_W := 0.1
var bridge_spots: Array = []  # world positions of the bridges (screenshots, tests)

## Dirt roads (the close reference frames: carts on country roads): from every building hex to its owner's capital
## along the shortest way over the owner's land, as wavy ribbons that stop at the building pads; rebuilt with the
## borders, so a conquered town joins the new owner's roads.
func _build_roads() -> void:
	bridge_spots = []
	var tools := {}  # era 0 dirt (DL1–5), 1 asphalt (DL6–7), 2 dark neon road (DL8+) -> SurfaceTool
	var dashes := SurfaceTool.new()
	dashes.begin(Mesh.PRIMITIVE_TRIANGLES)
	var any_dash := false
	var done := {}
	var joints := {}  # hex -> era
	for c in sim.cells:
		if c["kind"] in ["plain", "capital"] or not Types.is_passable(c):
			continue
		var own := owner_of(c)
		if own <= Types.NOBODY or own >= sim.states.size():
			continue
		var cap: int = int(sim.states[own]["capital_id"])
		if cap < 0 or owner_of(sim.cells[cap]) != own:
			continue
		var path := _land_path(int(c["id"]), cap, own)
		if path.size() < 2 or path.size() > 7:
			continue
		var dl: int = int(sim.states[own]["dev_level"])
		var era := 2 if dl >= 8 else (1 if dl >= 6 else 0)
		if not tools.has(era):
			var t := SurfaceTool.new()
			t.begin(Mesh.PRIMITIVE_TRIANGLES)
			tools[era] = t
		var st: SurfaceTool = tools[era]
		for i in path.size() - 1:
			var a: int = path[i]
			var b: int = path[i + 1]
			var key := "%d-%d" % [mini(a, b), maxi(a, b)]
			if done.has(key):
				continue
			done[key] = true
			_road_segment(st, a, b, ROAD_W, dashes if era == 1 else null)
			any_dash = any_dash or era == 1
			if era == 0 and (sim.rivers.has("%d:%d" % [a, b]) or sim.rivers.has("%d:%d" % [b, a])):
				# a stone arch bridge where the road crosses a river (the reference frames)
				var pa := cell_world(a)
				var pb := cell_world(b)
				var dv := (pb - pa).normalized()
				spawn("bridge", _overlay_root, (pa + pb) / 2.0, atan2(-dv.z, dv.x), 1.0)
				bridge_spots.append((pa + pb) / 2.0)
			for h in [a, b]:
				if not _road_stop(h):
					joints[h] = era
	# footpaths (reference frame 3: trails tie every farmstead into the road net): an open meadow hex next to a road
	# of the dirt-road era gets a narrow trail from that road to its centre
	var net := {}
	for key in done:
		for part in String(key).split("-"):
			net[int(part)] = true
	for c in sim.cells:
		var h := int(c["id"])
		if net.has(h) or _road_stop(h) or c["terrain"] != "plain" or not Types.is_passable(c) or (h * 7) % 10 >= 7:
			continue
		var own := owner_of(c)
		if own <= Types.NOBODY or own >= sim.states.size() or int(sim.states[own]["dev_level"]) >= 6:
			continue
		for nb in sim.neighbors[h]:
			if nb >= 0 and net.has(nb) and owner_of(sim.cells[nb]) == own:
				if not tools.has(0):
					var t0 := SurfaceTool.new()
					t0.begin(Mesh.PRIMITIVE_TRIANGLES)
					tools[0] = t0
				_road_segment(tools[0], nb, h, ROAD_W * 0.55)
				if not _road_stop(nb):
					joints[nb] = 0
				break
	for h in joints:  # a round patch where roads meet in an open hex hides the joints
		var st: SurfaceTool = tools[joints[h]]
		var cc := cell_world(int(h)) + Vector3(0, 0.033, 0)
		for k in 10:
			var a0 := k * TAU / 10.0
			var a1 := (k + 1) * TAU / 10.0
			st.set_normal(Vector3.UP)
			st.add_vertex(cc)
			st.add_vertex(cc + Vector3(cos(a0), 0, sin(a0)) * ROAD_W * 0.62)
			st.add_vertex(cc + Vector3(cos(a1), 0, sin(a1)) * ROAD_W * 0.62)
	for era in tools:
		var mi := MeshInstance3D.new()
		mi.mesh = (tools[era] as SurfaceTool).commit()
		var m := StandardMaterial3D.new()
		m.albedo_color = [Color(0.64, 0.5, 0.32), Color(0.42, 0.43, 0.45), Color(0.12, 0.14, 0.18)][era]
		m.roughness = 1.0 if era == 0 else 0.6
		if era == 2:  # the glowing roads of reference frame 2
			m.emission_enabled = true
			m.emission = Color(0.1, 0.55, 1.0)
			m.emission_energy_multiplier = 0.9
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		mi.material_override = m
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_overlay_root.add_child(mi)
	if any_dash:
		var dm := MeshInstance3D.new()
		dm.mesh = dashes.commit()
		var wm := StandardMaterial3D.new()
		wm.albedo_color = Color(0.92, 0.9, 0.82)
		wm.roughness = 0.8
		wm.cull_mode = BaseMaterial3D.CULL_DISABLED
		dm.material_override = wm
		dm.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_overlay_root.add_child(dm)


## A road ends at the edge of a building's pad; through open land it runs to the hex centre.
func _road_stop(h: int) -> bool:
	return sim.cells[h]["kind"] != "plain" or camp_hexes.has(h)


func _road_segment(st: SurfaceTool, a: int, b: int, w := ROAD_W, dash: SurfaceTool = null) -> void:
	var pa := cell_world(a)
	var pb := cell_world(b)
	var dir := (pb - pa).normalized()
	if _road_stop(a):
		pa += dir * 0.55
	if _road_stop(b):
		pb -= dir * 0.55
	var side := Vector3(-dir.z, 0, dir.x)
	var seed_ := float((a * 31 + b * 17) % 97)
	var n := 8
	var prev_l := Vector3.ZERO
	var prev_r := Vector3.ZERO
	for i in n + 1:
		var t := float(i) / n
		var wob := sin(t * PI) * sin(t * TAU + seed_) * 0.06  # a gentle meander, none at the ends
		var p := pa.lerp(pb, t) + side * wob + Vector3(0, 0.033, 0)  # over the fill, under the hex grid lines
		var l := p - side * w * 0.5
		var r := p + side * w * 0.5
		if i > 0:
			st.set_normal(Vector3.UP)
			st.add_vertex(prev_l); st.add_vertex(r); st.add_vertex(prev_r)
			st.add_vertex(prev_l); st.add_vertex(l); st.add_vertex(r)
			if dash and i % 2 == 1:  # a dashed centre line on the asphalt roads of DL6–7
				var c0 := (prev_l + prev_r) / 2.0 + Vector3(0, 0.002, 0)
				var c1 := (l + r) / 2.0 + Vector3(0, 0.002, 0)
				var m0 := c0.lerp(c1, 0.2)
				var m1 := c0.lerp(c1, 0.8)
				var sd := side * 0.007
				dash.set_normal(Vector3.UP)
				dash.add_vertex(m0 - sd); dash.add_vertex(m1 + sd); dash.add_vertex(m0 + sd)
				dash.add_vertex(m0 - sd); dash.add_vertex(m1 - sd); dash.add_vertex(m1 + sd)
		prev_l = l
		prev_r = r


## Shortest way from `from` to `to` over passable hexes of `own` (-99: anyone's), breadth first; [] if there is none.
func _land_path(from: int, to: int, own: int) -> Array:
	var prev := {from: -1}
	var queue: Array = [from]
	while not queue.is_empty():
		var h: int = queue.pop_front()
		if h == to:
			break
		for nb in sim.neighbors[h]:
			if nb < 0 or prev.has(nb):
				continue
			var cn: Dictionary = sim.cells[nb]
			if not Types.is_passable(cn) or (own != -99 and owner_of(cn) != own):
				continue
			prev[nb] = h
			queue.append(nb)
	if not prev.has(to):
		return []
	var path: Array = []
	var cur := to
	while cur != -1:
		path.push_front(cur)
		cur = int(prev[cur])
	return path


var _tint_mats: Array = []
var _wash_mats: Array = []
var _tint_k := 1.0
var _wash_w := 1.0  # 1 = the wide strategic fill, 0 = the narrow close-up rim band


## The territory fills follow the zoom (art direction §1): rich colour on the strategic view, see-through up close
## where the land, buildings and troops are the point. zoom: 0 close … 1 far (camera_rig.gd).
func set_zoom(zoom: float) -> void:
	var k := lerpf(0.3, 1.0, smoothstep(0.1, 0.6, zoom))
	var w := smoothstep(0.3, 0.6, zoom)  # reference frame 1 (far) washes the land in the state colour, frame 3 (near) doesn't
	if absf(k - _tint_k) < 0.01 and absf(w - _wash_w) < 0.01:
		return
	_tint_k = k
	_wash_w = w
	for m in _tint_mats:
		(m as StandardMaterial3D).albedo_color.a = k * (1.0 - w)
	for m in _wash_mats:
		(m as StandardMaterial3D).albedo_color.a = k * w


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
	m.vertex_color_is_srgb = true  # the fill colours are picked in sRGB: read as linear, royal blue went pastel azure
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
		var marching := 1.0 if (a["move"] != null or not mv.is_empty() or (fighting.has(id) and int(fighting[id]) == -3)) else 0.0
		var in_fight := 1.0 if fighting.has(id) and int(fighting[id]) != -3 else 0.0
		for mi in node.get_meta("anim", []):
			if is_instance_valid(mi):
				(mi as GeometryInstance3D).set_instance_shader_parameter("march", marching)
				(mi as GeometryInstance3D).set_instance_shader_parameter("fight", in_fight)
		model.position.y = hop
		model.rotation.z = sway
		var ready := float(a["str"]) / maxf(1.0, float(a["max_str"]))
		var lbl: Label3D = node.get_node("label")
		var hidden: bool = a["side"] != Types.PLAYER and not fog_visible.is_empty() and not fog_visible.has(int(a["hex"]))
		lbl.text = ("?" if hidden else str(int(round(a["str"] / 1000.0)))) if not a["routed"] else "✖"
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
			fx.add_child(_make_clash_dust())  # a churned-up dust cloud and muzzle flashes over the melee
			fx.add_child(_make_flashes())
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


## Dust kicked up by the melee: wide low puffs that drift and fade (reference frame 3: dust around the fighting).
func _make_clash_dust() -> CPUParticles3D:
	if _smoke_mat == null:
		_smoke_mat = _fx_mat(_puff_tex(), false)
	var d := CPUParticles3D.new()
	d.amount = 12
	d.lifetime = 1.8
	d.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	d.emission_box_extents = Vector3(0.35, 0.02, 0.25)
	d.direction = Vector3(0, 1, 0)
	d.spread = 60.0
	d.initial_velocity_min = 0.08
	d.initial_velocity_max = 0.2
	d.gravity = Vector3(0.05, 0.02, 0)
	d.scale_amount_curve = _curve(0.4, 1.5)
	d.color_ramp = _ramp([0.0, 0.2, 1.0], [Color(0.62, 0.53, 0.4, 0.0), Color(0.6, 0.52, 0.4, 0.5), Color(0.7, 0.65, 0.58, 0.0)])
	var q := QuadMesh.new()
	q.size = Vector2(0.45, 0.45)
	q.material = _smoke_mat
	d.mesh = q
	d.position = Vector3(0, -0.3, 0)
	d.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return d


## Short bright flashes scattered over the fight (shots, struck steel): additive, a fraction of a second each.
func _make_flashes() -> CPUParticles3D:
	var f := CPUParticles3D.new()
	f.amount = 5
	f.lifetime = 0.18
	f.explosiveness = 0.0
	f.randomness = 1.0
	f.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	f.emission_box_extents = Vector3(0.35, 0.08, 0.25)
	f.direction = Vector3.UP
	f.initial_velocity_min = 0.0
	f.initial_velocity_max = 0.05
	f.gravity = Vector3.ZERO
	f.scale_amount_curve = _curve(1.0, 0.2)
	f.color_ramp = _ramp([0.0, 1.0], [Color(1.0, 0.95, 0.7, 1.0), Color(1.0, 0.5, 0.1, 0.0)])
	var q := QuadMesh.new()
	q.size = Vector2(0.22, 0.22)
	q.material = _fx_mat(_flame_tex(), true)
	f.mesh = q
	f.position = Vector3(0, -0.15, 0)
	f.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return f


class ArmyNode extends Node3D:
	var modulate_alpha := 1.0


var _troop_shader: Shader
var _troop_mats := {}  # [texture id, solid] -> ShaderMaterial


## Swaps a troop model's baked material for the animated troop shader (march bob, fight thrust); glowing
## parts keep their own material. The mesh instances go into `out` so sync_armies can drive them.
func _animate_troops(n: Node, solid: bool, out: Array) -> void:
	if _troop_shader == null:
		_troop_shader = load("res://shaders/troops.gdshader")
	if n is MeshInstance3D:
		var mi: MeshInstance3D = n
		var used := false
		for i in mi.mesh.get_surface_count():
			var m: Material = mi.get_active_material(i)
			if not (m is StandardMaterial3D):
				continue
			var sm: StandardMaterial3D = m
			if sm.emission_enabled or sm.albedo_texture == null:
				continue
			var key := "%d:%d" % [sm.albedo_texture.get_instance_id(), int(solid)]
			if not _troop_mats.has(key):
				var shm := ShaderMaterial.new()
				shm.shader = _troop_shader
				shm.set_shader_parameter("albedo_tex", sm.albedo_texture)
				shm.set_shader_parameter("roughness_v", sm.roughness)
				shm.set_shader_parameter("solid", solid)
				_troop_mats[key] = shm
			mi.set_surface_override_material(i, _troop_mats[key])
			used = true
		if used:
			out.append(mi)
	for ch in n.get_children():
		_animate_troops(ch, solid, out)


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
	var anim: Array = []
	# the reference frames: an army is a handful of big readable soldiers and riders (frame 3: four to eight men a
	# hex), not a crowd — two loose eight-man squads, slightly turned against each other
	var sq_name := squad if squad != "" else "squad_" + side
	for g in [[Vector3(-0.26, 0, 0.2), 0.12], [Vector3(-0.02, 0, -0.18), 0.05]]:
		var sq := spawn(sq_name, model, g[0], g[1], 0.98)
		if sq:
			_animate_troops(sq, false, anim)
	var rider: Node3D = null
	if assault != "":
		rider = spawn(assault, model, Vector3(0.4, 0, 0.16), 0.0, 1.1)
	elif dl >= 2 or squad == "":
		rider = spawn("knight_" + ("blue" if side == "blue" else "red"), model, Vector3(0.4, 0, 0.16), 0.0, 1.1)
	if rider:
		_animate_troops(rider, true, anim)
		if assault != "" and dl <= 5:  # cavalry rides in pairs (reference frame 3: horsemen on both sides of the front)
			var r2 := spawn(assault, model, Vector3(0.5, 0, -0.22), 0.12, 1.05)
			if r2:
				_animate_troops(r2, true, anim)
	var gun := ""
	if dl == 2 or dl == 3:  # the medieval armies drag a mangonel along (tools/blender/export_assets.py catapult)
		gun = "catapult"
	elif dl == 4 or dl == 5:  # the bicorne era: a bronze field gun
		gun = "cannon"
	elif dl == 6 or dl == 7:  # the trench era: a field howitzer
		gun = "howitzer"
	elif dl >= 8:  # the late era: a six-wheeled rocket launcher
		gun = "rocket_launcher"
	if gun != "":
		spawn(gun, model, Vector3(-0.46, 0, -0.22), 0.3, 0.85)
	if dl >= 8 and has_model("mech_" + side):  # walkers among the infantry (reference frames 2 and 5)
		for mp in [Vector3(0.24, 0, 0.42), Vector3(-0.42, 0, 0.32)]:
			var mech := spawn("mech_" + side, model, mp, 0.0, 1.05)
			if mech:
				_animate_troops(mech, true, anim)
	if dl >= 6:  # air cover circling over the army (reference frame 2): a fighter (DL6–7) or a hover gunship (DL8+)
		var orbit := Node3D.new()
		orbit.position = Vector3(0, 0.95, 0)
		model.add_child(orbit)
		var plane := spawn("gunship" if dl >= 8 else "fighter", orbit, Vector3(0.45, 0, 0), PI / 2.0, 1.6)
		if plane:
			plane.rotation.z = -0.35  # banked into the turn
			var tw := orbit.create_tween().set_loops()
			tw.tween_property(orbit, "rotation:y", -TAU, 7.0).from(0.0)
	node.set_meta("anim", anim)
	spawn("banner_" + side, model, Vector3(0.05, 0, -0.35), 0.0, 0.9, int(a["side"]))
	var lbl := Label3D.new()
	lbl.name = "label"
	lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lbl.no_depth_test = true
	lbl.font_size = 64
	lbl.outline_size = 14
	lbl.pixel_size = 0.0036  # a small tag over the bar: the reference frames show bars, not big numbers
	lbl.position = Vector3(0, 1.04, 0)
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
	burst_at(cell_world(hex), color, big)


func burst_at(pos: Vector3, color: Color, big := false) -> void:
	var p := pos + Vector3(0, 0.1, 0)
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
		var icon_name: String = {"gold": "coin", "food": "food", "metal": "metal", "raivite": "raivite"}.get(data[h]["res"], "coin")
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
var fog_visible := {}  # hexes in the player's sight (canon §3.1); empty = everything visible
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
		var route: Array = cart.get_meta("route", [])
		if route.is_empty():  # along the hexes (and so the roads) instead of straight over the woods
			var hexes := _land_path(int(sim.states[Types.PLAYER]["capital_id"]), int(cv["hex"]), -99)
			for h in hexes:
				route.append(cell_world(int(h)))
			if route.size() < 2:
				route = [cap, target]
			cart.set_meta("route", route)
		var p: Vector3
		match String(ph["phase"]):
			"out":
				p = _along(cart, route, float(ph["progress"]), false)
			"gather":
				p = target + Vector3(0.3, 0, 0.25)
			_:
				p = _along(cart, route, float(ph["progress"]), true)
		cart.position = p
		var lbl: Label3D = cart.get_node("label")
		lbl.text = ("⛏ " if String(ph["phase"]) == "gather" else "") + _fmt_left(int(ph["left"]))
	for id in _carts.keys():
		if not live.has(id):
			_carts[id].queue_free()
			_carts.erase(id)


## A point at `f` (0..1) of the way along the route polyline (backwards on the way home); turns the cart along it.
func _along(cart: Node3D, route: Array, f: float, back: bool) -> Vector3:
	var pts := route.duplicate()
	if back:
		pts.reverse()
	var total := 0.0
	for i in pts.size() - 1:
		total += (pts[i] as Vector3).distance_to(pts[i + 1])
	var want := clampf(f, 0.0, 1.0) * total
	for i in pts.size() - 1:
		var a: Vector3 = pts[i]
		var b: Vector3 = pts[i + 1]
		var d := a.distance_to(b)
		if want <= d or i == pts.size() - 2:
			(cart.get_node("body") as Node3D).rotation.y = atan2(b.x - a.x, b.z - a.z)
			return a.lerp(b, clampf(want / maxf(d, 0.001), 0.0, 1.0))
		want -= d
	return pts[pts.size() - 1]


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
		_strip(st, pts[k], pts[(k + 1) % 6], 0.065, center.y + 0.02)
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = _glow_mat(C_DEPOSIT, 1.0, 0.9)
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


var _puff: ImageTexture
var _flame: ImageTexture
var _flames: Array = []  # [{light, glow, base, phase}] flickering fire lights


## Billowy smoke puff: a few soft blobs inside a round falloff, lit from the upper left (fixed seed).
func _puff_tex() -> ImageTexture:
	if _puff != null:
		return _puff
	var n := 64
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var blobs: Array = []
	for i in 7:
		var a := rng.randf() * TAU
		var r := rng.randf_range(0.0, 0.42) * (0.0 if i == 0 else 1.0)
		blobs.append([0.5 + cos(a) * r * 0.5, 0.5 + sin(a) * r * 0.5, rng.randf_range(0.2, 0.3)])
	for y in n:
		for x in n:
			var u := (x + 0.5) / n
			var v := (y + 0.5) / n
			var d := 0.0
			for b in blobs:
				var dx: float = (u - float(b[0])) / float(b[2])
				var dy: float = (v - float(b[1])) / float(b[2])
				d = maxf(d, clampf(1.0 - (dx * dx + dy * dy), 0.0, 1.0))
			var edge := clampf(1.0 - Vector2(u - 0.5, v - 0.5).length() * 2.0, 0.0, 1.0)
			var a := smoothstep(0.0, 0.6, d) * smoothstep(0.0, 0.25, edge)
			var lit := clampf(1.05 - 0.45 * (u + v - 0.6), 0.7, 1.0)
			img.set_pixel(x, y, Color(lit, lit, lit, a))
	_puff = ImageTexture.create_from_image(img)
	return _puff


## Flame tongue: a teardrop, wide and hot at the bottom, a thin flickering tip at the top.
func _flame_tex() -> ImageTexture:
	if _flame != null:
		return _flame
	var w := 32
	var h := 64
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	for y in h:
		var t := 1.0 - (y + 0.5) / h  # 0 bottom .. 1 top
		var half := 0.5 * sqrt(clampf(t * 5.0, 0.0, 1.0)) * pow(1.0 - t, 0.9)
		for x in w:
			var u := absf((x + 0.5) / w - 0.5)
			var a := 0.0 if half <= 0.0 else clampf(1.0 - u / half, 0.0, 1.0)
			a = pow(a, 0.7) * smoothstep(0.0, 0.12, t)
			var core := clampf(1.0 - u / maxf(0.001, half * 0.5), 0.0, 1.0) * (1.0 - t)
			img.set_pixel(x, y, Color(1.0, 0.62 + 0.38 * core, 0.3 + 0.6 * core, a))  # red-orange rim, yellow-white core
	_flame = ImageTexture.create_from_image(img)
	return _flame


func _fx_mat(tex: Texture2D, additive: bool) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	# BILLBOARD_PARTICLES draws not-yet-spawned particles as black quads at the emitter; keep_scale avoids it
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.billboard_keep_scale = true
	m.vertex_color_use_as_albedo = true
	m.albedo_texture = tex
	if additive:
		m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	return m


func _curve(a: float, b: float) -> Curve:
	var c := Curve.new()
	c.max_value = maxf(2.0, maxf(a, b))
	c.add_point(Vector2(0, a))
	c.add_point(Vector2(1, b))
	return c


## Smoke over a hex; with `fire` a real blaze: flame tongues at the building, rising sparks, thick dark smoke,
## a scorched patch and a flickering warm light. `seconds` < 0 keeps it until clear_smoke().
func smoke(hex: int, seconds: float, fire := false) -> void:
	if _smoke_mat == null:
		_smoke_mat = _fx_mat(_puff_tex(), false)
	var root := Node3D.new()
	root.position = cell_world(hex) + _fire_spot(hex) if fire else cell_world(hex) + Vector3(0.15, 0.2, -0.1)
	add_child(root)
	var sm := CPUParticles3D.new()
	sm.amount = 12 if fire else 18
	sm.lifetime = 2.6 if fire else 3.0  # a capture's smoke stays low: it must not veil the front
	sm.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	sm.emission_sphere_radius = 0.12
	sm.direction = Vector3(0.25, 1, 0)
	sm.spread = 10.0
	sm.initial_velocity_min = 0.4 if fire else 0.3
	sm.initial_velocity_max = 0.65 if fire else 0.5
	sm.gravity = Vector3(0.14, 0.06, 0)
	sm.damping_min = 0.05
	sm.damping_max = 0.12
	sm.scale_amount_min = 0.7
	sm.scale_amount_max = 1.1
	sm.scale_amount_curve = _curve(0.4, 1.9)
	if fire:
		sm.color_ramp = _ramp([0.0, 0.1, 0.45, 1.0], [Color(0.16, 0.13, 0.12, 0.0), Color(0.2, 0.17, 0.15, 0.55),
			Color(0.36, 0.34, 0.33, 0.28), Color(0.55, 0.55, 0.57, 0.0)])
	else:
		sm.color_ramp = _ramp([0.0, 0.15, 0.6, 1.0], [Color(0.5, 0.47, 0.44, 0.0), Color(0.5, 0.48, 0.46, 0.4),
			Color(0.68, 0.68, 0.7, 0.2), Color(0.85, 0.85, 0.88, 0.0)])
	var q := QuadMesh.new()
	q.size = Vector2(0.6, 0.6) if fire else Vector2(0.75, 0.75)
	q.material = _smoke_mat
	sm.mesh = q
	sm.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	sm.position.y = 0.7 if fire else 0.0  # fire smoke starts above the flames instead of veiling them
	root.add_child(sm)
	if fire:
		_add_blaze(root, hex)
	if seconds >= 0.0:
		var tw := root.create_tween()
		tw.tween_interval(seconds)
		tw.tween_callback(func(): _douse(root))
		tw.tween_interval(3.7)
		tw.tween_callback(root.queue_free)
	else:
		clear_smoke(hex)
		_smokes[hex] = root
		if fire:
			_blazing[hex] = true
			_still_sails(hex, true)


## Where a hex burns: on its building (a farm's windmill), else at the back of the hex — the army stands in
## the middle and would hide the flames.
func _fire_spot(hex: int) -> Vector3:
	if String(sim.cells[hex]["kind"]) == "farm":
		return Vector3(-0.45, 0.2, -0.3)
	return Vector3(0.2, 0.2, -0.42)


func _add_blaze(root: Node3D, hex: int) -> void:
	# alpha-blended, not additive: on sunlit ground additive flames wash out to white
	var fm := _fx_mat(_flame_tex(), false)
	fm.render_priority = 1  # over the smoke
	# on the roof and the camera-facing walls, so the building itself doesn't hide them
	var spots: Array[Vector3] = [Vector3(0, 0.42, 0.12), Vector3(-0.2, 0.18, 0.2), Vector3(0.18, 0.24, 0.18)]
	for i in spots.size():
		var fl := CPUParticles3D.new()
		fl.amount = 18 if i == 0 else 12
		fl.lifetime = 0.65 if i == 0 else 0.5
		fl.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
		fl.emission_sphere_radius = 0.07
		fl.direction = Vector3.UP
		fl.spread = 8.0
		fl.initial_velocity_min = 0.3
		fl.initial_velocity_max = 0.5
		fl.gravity = Vector3(0, 0.9, 0)
		fl.scale_amount_min = 0.75
		fl.scale_amount_max = 1.15
		fl.scale_amount_curve = _curve(1.0, 0.25)
		fl.color_ramp = _ramp([0.0, 0.18, 0.6, 1.0], [Color(1.0, 0.8, 0.35, 0.0), Color(1.0, 0.62, 0.14, 1.0),
			Color(0.95, 0.3, 0.04, 0.9), Color(0.6, 0.08, 0.02, 0.0)])
		var fq := QuadMesh.new()
		fq.size = Vector2(0.5, 0.8) * (1.0 if i == 0 else 0.8)
		fq.material = fm
		fl.mesh = fq
		fl.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		fl.position = spots[i]
		fl.preprocess = 0.6
		root.add_child(fl)
	var sp := CPUParticles3D.new()
	sp.amount = 12
	sp.lifetime = 1.5
	sp.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	sp.emission_sphere_radius = 0.2
	sp.direction = Vector3(0.15, 1, 0)
	sp.spread = 25.0
	sp.initial_velocity_min = 0.6
	sp.initial_velocity_max = 1.1
	sp.gravity = Vector3(0.2, 0.15, 0)
	sp.damping_min = 0.3
	sp.damping_max = 0.6
	sp.scale_amount_min = 0.6
	sp.scale_amount_max = 1.0
	sp.color_ramp = _ramp([0.0, 0.5, 1.0], [Color(1.0, 0.95, 0.6, 1.0), Color(1.0, 0.55, 0.15, 0.9), Color(0.9, 0.25, 0.05, 0.0)])
	var spq := QuadMesh.new()
	spq.size = Vector2(0.06, 0.06)
	spq.material = _fx_mat(_soft_tex(), true)
	sp.mesh = spq
	sp.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	sp.position.y = 0.2
	root.add_child(sp)
	# scorched ground and the warm glow of the fire on it
	var scorch := MeshInstance3D.new()
	scorch.name = "scorch"
	var sq := PlaneMesh.new()
	sq.size = Vector2(1.1, 1.1)
	scorch.mesh = sq
	var scm := StandardMaterial3D.new()
	scm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	scm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	scm.albedo_texture = _soft_tex()
	scm.albedo_color = Color(0.08, 0.06, 0.05, 0.5)
	scm.render_priority = -1
	scorch.material_override = scm
	scorch.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	scorch.position.y = 0.025
	root.add_child(scorch)
	var glow := MeshInstance3D.new()
	var gq := PlaneMesh.new()
	gq.size = Vector2(1.3, 1.3)
	glow.mesh = gq
	var gm := StandardMaterial3D.new()
	gm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	gm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	gm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	gm.albedo_texture = _soft_tex()
	gm.albedo_color = Color(1.0, 0.45, 0.12, 0.45)
	glow.material_override = gm
	glow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	glow.position.y = 0.04
	root.add_child(glow)
	var light := OmniLight3D.new()
	light.light_color = Color(1.0, 0.55, 0.2)
	light.omni_range = 1.8
	light.light_energy = 1.4
	light.position.y = 0.45
	root.add_child(light)
	_flames.append({"light": light, "glow": gm, "base": 1.4, "phase": float(hex) * 1.7})


## Stops a fire: flames, sparks and smoke stop emitting, the glow dies down, the scorch stays until freed.
func _douse(root: Node3D) -> void:
	for c in root.get_children():
		if c is CPUParticles3D:
			(c as CPUParticles3D).emitting = false
	for f in _flames:
		var l: Variant = f["light"]
		if is_instance_valid(l) and (l as Node).get_parent() == root:
			f["base"] = 0.0


func _step_flames(t: float) -> void:
	for i in range(_flames.size() - 1, -1, -1):
		var f: Dictionary = _flames[i]
		var obj: Variant = f["light"]
		if not is_instance_valid(obj):
			_flames.remove_at(i)
			continue
		var l := obj as OmniLight3D
		var ph: float = f["phase"]
		var k := 0.82 + 0.1 * sin(t * 11.0 + ph) + 0.08 * sin(t * 23.0 + ph * 2.3)
		var target: float = float(f["base"]) * k
		l.light_energy = lerpf(l.light_energy, target, 0.35)
		(f["glow"] as StandardMaterial3D).albedo_color.a = 0.45 * l.light_energy / 1.4


func clear_smoke(hex: int) -> void:
	var root: Node3D = _smokes.get(hex)
	if root == null:
		return
	_smokes.erase(hex)
	if _blazing.has(hex):
		_blazing.erase(hex)
		_still_sails(hex, false)
	_douse(root)
	var tw := root.create_tween()
	tw.tween_interval(3.7)
	tw.tween_callback(root.queue_free)


# ------------------------------------------------------------------ airstrike & air defence

var _planes: Array = []  # [{node, from, to, t, dur}]


func _flat_mat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.6
	return m


func _box(parent: Node3D, size: Vector3, pos: Vector3, m: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = m
	mi.position = pos
	parent.add_child(mi)
	return mi


## A low-poly aircraft of the era (canon §10 table): biplane at DL6, propeller attack plane at DL7, jet from DL8.
## Faces −Z; `tint` is the side's colour on the wings.
func _aircraft(dl: int, tint: Color) -> Node3D:
	var root := Node3D.new()
	var body := _flat_mat(Color(0.42, 0.45, 0.4) if dl <= 7 else Color(0.62, 0.65, 0.7))
	var wing := _flat_mat(tint)
	var dark := _flat_mat(Color(0.12, 0.12, 0.14))
	if dl <= 6:
		_box(root, Vector3(0.12, 0.12, 0.62), Vector3.ZERO, body)
		_box(root, Vector3(0.9, 0.025, 0.16), Vector3(0, 0.1, -0.08), wing)
		_box(root, Vector3(0.82, 0.025, 0.15), Vector3(0, -0.05, -0.06), wing)
		for x in [-0.32, 0.32]:
			_box(root, Vector3(0.015, 0.15, 0.015), Vector3(x, 0.025, -0.08), dark)
		_box(root, Vector3(0.32, 0.02, 0.1), Vector3(0, 0.02, 0.27), wing)
		_box(root, Vector3(0.02, 0.13, 0.1), Vector3(0, 0.08, 0.27), wing)
		_box(root, Vector3(0.3, 0.03, 0.02), Vector3(0, 0, -0.32), dark).name = "prop"
	elif dl == 7:
		_box(root, Vector3(0.13, 0.13, 0.7), Vector3.ZERO, body)
		_box(root, Vector3(1.0, 0.03, 0.18), Vector3(0, -0.02, -0.05), wing)
		_box(root, Vector3(0.36, 0.02, 0.1), Vector3(0, 0.02, 0.3), wing)
		_box(root, Vector3(0.02, 0.16, 0.12), Vector3(0, 0.09, 0.3), wing)
		_box(root, Vector3(0.08, 0.06, 0.14), Vector3(0, 0.08, -0.08), _flat_mat(Color(0.5, 0.75, 0.9)))
		_box(root, Vector3(0.34, 0.03, 0.02), Vector3(0, 0, -0.36), dark).name = "prop"
	else:
		_box(root, Vector3(0.11, 0.11, 0.8), Vector3.ZERO, body)
		for sx in [-1.0, 1.0]:
			var w := _box(root, Vector3(0.45, 0.025, 0.3), Vector3(sx * 0.24, -0.01, 0.08), wing)
			w.rotation.y = sx * 0.45
		_box(root, Vector3(0.02, 0.2, 0.16), Vector3(0, 0.1, 0.32), wing)
		_box(root, Vector3(0.07, 0.05, 0.16), Vector3(0, 0.07, -0.2), _flat_mat(Color(0.5, 0.75, 0.9)))
		var exhaust := _box(root, Vector3(0.07, 0.07, 0.05), Vector3(0, 0, 0.42), _flat_mat(Color(1.0, 0.6, 0.2)))
		(exhaust.material_override as StandardMaterial3D).emission_enabled = true
		(exhaust.material_override as StandardMaterial3D).emission = Color(1.0, 0.5, 0.15)
		(exhaust.material_override as StandardMaterial3D).emission_energy_multiplier = 3.0
	return root


## «Авиаудар» (03 §12.2, 10 §airstrike): a flight of three crosses the map over the target, bombs burst over the
## 7 hexes one after another. `dl` picks the era of the aircraft, `tint` the side's colour.
func airstrike(target: int, area: Array, dl: int, tint: Color) -> void:
	var c := cell_world(target)
	var dir := Vector3(0.8, 0, -0.6).normalized()
	var dur := 2.0
	var perp := Vector3(-dir.z, 0, dir.x)
	var offsets: Array[Vector3] = [Vector3.ZERO, perp * 0.65 - dir * 0.55, -perp * 0.65 - dir * 0.55]  # a «V» of three
	for i in 3:
		var off := offsets[i]
		var plane := _aircraft(dl, tint)
		add_child(plane)
		var from := c - dir * 7.0 + off + Vector3(0, 1.9, 0)
		var to := c + dir * 7.0 + off + Vector3(0, 1.9, 0)
		plane.position = from
		plane.look_at(to, Vector3.UP)
		plane.scale = Vector3.ONE * 0.95
		_planes.append({"node": plane, "from": from, "to": to, "t": 0.0, "dur": dur})
	# bombs fall as the flight passes overhead (mid-path), centre first
	var tw := create_tween()
	tw.tween_interval(dur * 0.45)
	for k in area.size():
		var h: int = area[k]
		tw.tween_callback(func(): explosion(cell_world(h)))
		tw.tween_interval(0.09)


func _step_planes(delta: float) -> void:
	for pl in _planes.duplicate():
		pl["t"] += delta
		var n: Node3D = pl["node"]
		var k: float = clampf(float(pl["t"]) / float(pl["dur"]), 0.0, 1.0)
		n.visible = float(pl["t"]) >= 0.0
		n.position = (pl["from"] as Vector3).lerp(pl["to"], k)
		var prop: Node3D = n.get_node_or_null("prop")
		if prop:
			prop.rotate_object_local(Vector3.FORWARD, 40.0 * delta)
		if k >= 1.0:
			n.queue_free()
			_planes.erase(pl)


## «Ракетный удар»: a missile climbs from `from` in a high arc with a smoke trail and bursts on the hex, which
## then burns for a while.
func missile(from: Vector3, hex: int) -> void:
	var to := cell_world(hex)
	var body := Node3D.new()
	add_child(body)
	_box(body, Vector3(0.09, 0.09, 0.42), Vector3.ZERO, _flat_mat(Color(0.85, 0.86, 0.88)))
	var tip := _box(body, Vector3(0.1, 0.1, 0.1), Vector3(0, 0, -0.24), _flat_mat(Color(0.8, 0.15, 0.1)))
	tip.rotation.z = PI / 4.0
	var flame := _box(body, Vector3(0.07, 0.07, 0.12), Vector3(0, 0, 0.27), _flat_mat(Color(1.0, 0.7, 0.25)))
	(flame.material_override as StandardMaterial3D).emission_enabled = true
	(flame.material_override as StandardMaterial3D).emission = Color(1.0, 0.55, 0.15)
	(flame.material_override as StandardMaterial3D).emission_energy_multiplier = 4.0
	var trail := CPUParticles3D.new()
	trail.amount = 30
	trail.lifetime = 0.9
	trail.local_coords = false
	trail.direction = Vector3.UP
	trail.spread = 20.0
	trail.initial_velocity_min = 0.05
	trail.initial_velocity_max = 0.15
	trail.gravity = Vector3(0, 0.15, 0)
	trail.scale_amount_curve = _curve(0.4, 1.4)
	trail.color_ramp = _ramp([0.0, 0.2, 1.0], [Color(0.9, 0.9, 0.9, 0.0), Color(0.85, 0.85, 0.85, 0.6), Color(0.7, 0.7, 0.72, 0.0)])
	var tq := QuadMesh.new()
	tq.size = Vector2(0.3, 0.3)
	tq.material = _fx_mat(_puff_tex(), false)
	trail.mesh = tq
	trail.position = Vector3(0, 0, 0.3)
	body.add_child(trail)
	var dur := 1.3
	var tw := create_tween()
	tw.tween_method(func(k: float):
		var p := from.lerp(to, k) + Vector3(0, 0.6 + 4.0 * sin(PI * k), 0)
		var p2 := from.lerp(to, minf(1.0, k + 0.02)) + Vector3(0, 0.6 + 4.0 * sin(PI * minf(1.0, k + 0.02)), 0)
		body.position = p
		if p2.distance_to(p) > 0.0001:
			body.look_at(p2, Vector3.UP), 0.0, 1.0, dur)
	tw.tween_callback(func():
		explosion(to)
		explosion(to + Vector3(0.25, 0, 0.15))
		smoke(hex, 6.0, true)
		trail.emitting = false
		body.get_child(0).visible = false
		body.get_child(1).visible = false
		body.get_child(2).visible = false)
	tw.tween_interval(1.0)
	tw.tween_callback(body.queue_free)


## A bomb burst on the ground: a fireball, a shock ring and a puff of dark smoke.
func explosion(pos: Vector3) -> void:
	var root := Node3D.new()
	root.position = pos + Vector3(0, 0.15, 0)
	add_child(root)
	var fb := CPUParticles3D.new()
	fb.one_shot = true
	fb.explosiveness = 0.9
	fb.amount = 16
	fb.lifetime = 0.55
	fb.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	fb.emission_sphere_radius = 0.15
	fb.direction = Vector3.UP
	fb.spread = 70.0
	fb.initial_velocity_min = 0.8
	fb.initial_velocity_max = 1.6
	fb.gravity = Vector3(0, 0.5, 0)
	fb.damping_min = 2.0
	fb.damping_max = 3.0
	fb.scale_amount_curve = _curve(0.6, 1.4)
	fb.color_ramp = _ramp([0.0, 0.3, 1.0], [Color(1.0, 0.95, 0.6, 1.0), Color(1.0, 0.5, 0.1, 0.9), Color(0.4, 0.1, 0.05, 0.0)])
	var fq := QuadMesh.new()
	fq.size = Vector2(0.55, 0.55)
	fq.material = _fx_mat(_puff_tex(), true)
	fb.mesh = fq
	fb.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(fb)
	var sm := CPUParticles3D.new()
	sm.one_shot = true
	sm.explosiveness = 0.7
	sm.amount = 10
	sm.lifetime = 1.6
	sm.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	sm.emission_sphere_radius = 0.2
	sm.direction = Vector3.UP
	sm.spread = 40.0
	sm.initial_velocity_min = 0.3
	sm.initial_velocity_max = 0.7
	sm.gravity = Vector3(0.1, 0.1, 0)
	sm.scale_amount_curve = _curve(0.5, 1.6)
	sm.color_ramp = _ramp([0.0, 0.2, 1.0], [Color(0.2, 0.17, 0.15, 0.0), Color(0.22, 0.2, 0.18, 0.75), Color(0.5, 0.5, 0.5, 0.0)])
	var sq := QuadMesh.new()
	sq.size = Vector2(0.6, 0.6)
	sq.material = _fx_mat(_puff_tex(), false)
	sm.mesh = sq
	sm.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(sm)
	fb.emitting = true
	sm.emitting = true
	burst_at(pos, Color(1.0, 0.6, 0.2))
	var tw := root.create_tween()
	tw.tween_interval(2.0)
	tw.tween_callback(root.queue_free)


## Air defence fire (04 §AA): tracers from the ground and dark flak bursts in the air over a defended hex.
func flak(hex: int) -> void:
	var c := cell_world(hex)
	# the guns: the defending tower (lvl ≥ 6) on this hex or next to it
	var gun := c + Vector3(0, 0.5, 0)
	var around: Array = [hex]
	around.append_array(sim.neighbors[hex])
	for h in around:
		if h >= 0 and int(sim.cells[h].get("tower", 0)) >= 6 and sim.cells[h]["controller"] == sim.cells[hex]["controller"]:
			gun = cell_world(h) + Vector3(0.42, 1.1, -0.36)  # the tower stands at the back-right of its hex
			break
	for i in 6:
		var p := c + Vector3(rng.randf_range(-0.7, 0.7), rng.randf_range(1.5, 2.3), rng.randf_range(-0.6, 0.6))
		var from := gun + Vector3(rng.randf_range(-0.08, 0.08), 0, rng.randf_range(-0.08, 0.08))
		var tw := create_tween()
		tw.tween_interval(0.45 + 0.16 * i)
		tw.tween_callback(func(): _flak_puff(p, from))


func _flak_puff(p: Vector3, from: Vector3) -> void:
	var tracer := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(0.025, 0.025, from.distance_to(p))
	tracer.mesh = bm
	var tm := StandardMaterial3D.new()
	tm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	tm.albedo_color = Color(1.0, 0.85, 0.4)
	tracer.material_override = tm
	tracer.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(tracer)
	tracer.position = from.lerp(p, 0.5)
	tracer.look_at(p, Vector3.UP)
	var root := Node3D.new()
	root.position = p
	add_child(root)
	var puff := CPUParticles3D.new()
	puff.one_shot = true
	puff.explosiveness = 1.0
	puff.amount = 6
	puff.lifetime = 1.1
	puff.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	puff.emission_sphere_radius = 0.08
	puff.spread = 180.0
	puff.initial_velocity_min = 0.1
	puff.initial_velocity_max = 0.3
	puff.gravity = Vector3.ZERO
	puff.scale_amount_curve = _curve(0.5, 1.3)
	puff.color_ramp = _ramp([0.0, 0.08, 0.2, 1.0], [Color(1.0, 0.7, 0.3, 1.0), Color(0.3, 0.25, 0.22, 0.9),
		Color(0.16, 0.15, 0.15, 0.85), Color(0.3, 0.3, 0.3, 0.0)])
	var q := QuadMesh.new()
	q.size = Vector2(0.4, 0.4)
	q.material = _fx_mat(_puff_tex(), false)
	puff.mesh = q
	puff.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(puff)
	puff.emitting = true
	var tw := root.create_tween()
	tw.tween_interval(0.08)
	tw.tween_callback(tracer.queue_free)
	tw.tween_interval(1.2)
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
	_step_planes(delta)
	_step_flames(bt)
	for i in range(_sails.size() - 1, -1, -1):
		var obj: Variant = _sails[i]
		if not is_instance_valid(obj):
			_sails.remove_at(i)
			continue
		if not (obj as Node3D).get_meta("still", false):
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
