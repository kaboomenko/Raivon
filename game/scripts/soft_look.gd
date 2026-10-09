extends RefCounted
## «Raivon Soft» materials for every imported model, without re-exporting one (docs/art_direction.md §6.5).
## Each GLB ships exactly one albedo-baked StandardMaterial3D (plus emissive and metal slots) and all lighting
## happens in Godot, so swapping that material for the soft_model shader restyles the whole model set:
## - the baked material -> a ShaderMaterial on soft_model.gdshader (half-wrapped light with a warm terminator, rim,
##   lilac shade fill, saturation, height gradient), one per albedo texture, carrying the original in meta "src"
##   (map_view._animate_troops reads it);
## - emissive materials keep their emission, get Godot's wrapped diffuse and lose the highlight;
## - metal becomes painted steel: metallic <= 0.25, roughness >= 0.55, wrapped diffuse.
## The swap is made on the meshes of the PackedScene (shared sub-resources), so every instance, the scenery
## MultiMeshes (map_view._decor_parts reads the same meshes) and the HUD portraits get it.

const SHADER := preload("res://shaders/soft_model.gdshader")

static var _toon := {}  # "albedo texture id|albedo colour" -> ShaderMaterial
static var _seen := {}  # material instance id -> true: an emissive / metal material already softened
static var swapped := 0  # surfaces moved to the soft_model shader
static var emissive := 0  # emissive surfaces (wrapped diffuse, no highlight)
static var metal := 0  # metal surfaces (painted steel)
static var other := 0  # untextured plain surfaces (wrapped diffuse)
static var overrides := 0  # node material overrides inside a model (none in the current set)
static var _reported := false


## Restyles a model once (the PackedScene keeps a "soft" meta, so it survives any number of calls).
static func soften(scene: PackedScene) -> void:
	if scene == null or scene.has_meta("soft"):
		return
	scene.set_meta("soft", true)
	var root := scene.instantiate()
	for n in root.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n
		if mi.mesh == null:
			continue
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m is StandardMaterial3D:
				var t := _soften_material(m)
				if t != null:
					mi.mesh.surface_set_material(i, t)
			# a node override lives on this throwaway instance, not on the shared mesh: count it, so a model that
			# starts using them shows up in the report instead of silently keeping the hard look
			if mi.get_surface_override_material(i) != null:
				overrides += 1
		if mi.material_override != null:
			overrides += 1
	root.free()


## Softens one model material in place, or returns the soft_model ShaderMaterial that replaces it.
static func _soften_material(sm: StandardMaterial3D) -> ShaderMaterial:
	if sm.emission_enabled:
		emissive += 1
		if not _seen.has(sm.get_instance_id()):
			_seen[sm.get_instance_id()] = true
			sm.diffuse_mode = BaseMaterial3D.DIFFUSE_LAMBERT_WRAP
			sm.specular_mode = BaseMaterial3D.SPECULAR_DISABLED
		return null
	if sm.metallic >= 0.5:
		metal += 1
		if not _seen.has(sm.get_instance_id()):
			_seen[sm.get_instance_id()] = true
			sm.metallic = minf(sm.metallic, 0.25)
			sm.roughness = maxf(sm.roughness, 0.55)
			sm.diffuse_mode = BaseMaterial3D.DIFFUSE_LAMBERT_WRAP
		return null
	if sm.albedo_texture == null:
		other += 1
		if not _seen.has(sm.get_instance_id()):
			_seen[sm.get_instance_id()] = true
			matte(sm)
		return null
	swapped += 1
	return toon(sm)


## The soft_model material for a baked StandardMaterial3D (cached per albedo texture and colour).
static func toon(src: StandardMaterial3D) -> ShaderMaterial:
	var key := "%d|%s" % [src.albedo_texture.get_instance_id(), src.albedo_color.to_html()]
	if not _toon.has(key):
		var t := ShaderMaterial.new()
		t.shader = SHADER
		t.set_shader_parameter("albedo_tex", src.albedo_texture)
		t.set_shader_parameter("albedo_color", src.albedo_color)
		t.set_meta("src", src)
		_toon[key] = t
	return _toon[key]


## The original StandardMaterial3D behind a material (itself when it was never swapped).
static func source(m: Material) -> Material:
	if m is ShaderMaterial and m.has_meta("src"):
		return m.get_meta("src")
	return m


## A procedural solid (aircraft, carts, camp posts, tinted tents): Godot's wrapped diffuse and no highlight,
## matched to the half wrap of soft_light.gdshaderinc that the baked models next to it get.
## Godot's LAMBERT_WRAP is energy-conserving with roughness r as the wrap: (N·L + r) / (1 + r)². At r = 0.15 a
## face square to the sun gets 0.87, a front wall (N·L ≈ 0.47) 0.47 as with Lambert and the terminator 0.11, as on
## the models (1.0 / 0.47 / 0.11); r = 0.5 had left the sunny side at 2/3, duller than the models.
## metallic_specular 0: a low roughness would otherwise mirror the sky as a pale sheen at grazing angles.
static func matte(m: BaseMaterial3D) -> BaseMaterial3D:
	m.diffuse_mode = BaseMaterial3D.DIFFUSE_LAMBERT_WRAP
	m.specular_mode = BaseMaterial3D.SPECULAR_DISABLED
	m.roughness = 0.15
	m.metallic_specular = 0.0
	return m


## One line with the counts so far, printed once per run (map_view.set_world).
static func report() -> void:
	if _reported:
		return
	_reported = true
	print("soft_look: %d surfaces on soft_model (%d materials), %d emissive, %d metal, %d plain, %d node overrides" % [
			swapped, _toon.size(), emissive, metal, other, overrides])
