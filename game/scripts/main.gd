extends Node3D
## Entry point: world + camera + lighting + HUD. `--shot=PATH` saves a screenshot and quits (CI / review).

const World := preload("res://scripts/world.gd")
const Hud := preload("res://scripts/hud.gd")
const CameraRig := preload("res://scripts/camera_rig.gd")

var world: Node3D
var rig: Node3D
var hud: CanvasLayer
var selection: MeshInstance3D


func _ready() -> void:
	_environment()
	world = World.new()
	add_child(world)
	rig = CameraRig.new()
	add_child(rig)
	rig.hex_tapped.connect(_on_hex_tapped)
	hud = Hud.new()
	hud.world = world
	add_child(hud)
	_make_selection()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--zoom="):
			rig.zoom = float(a.substr(7))
			rig.zoom_target = rig.zoom
		if a.begins_with("--select="):
			var parts := a.substr(9).split(",")
			_on_hex_tapped(Vector2i(int(parts[0]), int(parts[1])))
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot(a.substr(7))


func _environment() -> void:
	var we := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.13, 0.16, 0.2)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.62, 0.7, 0.85)
	e.ambient_light_energy = 0.5
	e.ssao_enabled = true
	e.ssao_radius = 1.2
	e.ssao_intensity = 2.5
	e.ssil_enabled = false
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	e.tonemap_exposure = 1.05
	e.glow_enabled = true
	e.glow_intensity = 1.4
	e.glow_strength = 1.15
	e.glow_bloom = 0.08
	e.glow_hdr_threshold = 0.75
	e.fog_enabled = true
	e.fog_light_color = Color(0.55, 0.62, 0.72)
	e.fog_density = 0.003
	e.adjustment_enabled = true
	e.adjustment_saturation = 1.12
	e.adjustment_contrast = 1.06
	we.environment = e
	var attrs := CameraAttributesPractical.new()
	attrs.dof_blur_far_enabled = false
	attrs.dof_blur_far_distance = 34.0
	attrs.dof_blur_far_transition = 12.0
	attrs.dof_blur_near_enabled = false
	attrs.dof_blur_near_distance = 12.0
	attrs.dof_blur_near_transition = 5.0
	attrs.dof_blur_amount = 0.04
	we.camera_attributes = attrs
	add_child(we)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -35, 0)
	sun.light_color = Color(1.0, 0.93, 0.82)
	sun.light_energy = 1.5
	sun.shadow_enabled = true
	sun.shadow_blur = 1.5
	sun.directional_shadow_max_distance = 60
	add_child(sun)


func _make_selection() -> void:
	selection = MeshInstance3D.new()
	var tm := TorusMesh.new()
	tm.inner_radius = 0.86
	tm.outer_radius = 0.96
	tm.rings = 6
	tm.ring_segments = 6
	selection.mesh = tm
	selection.rotation.y = PI / 6.0
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = Color(1.0, 0.95, 0.7)
	m.emission_enabled = true
	m.emission = Color(1.0, 0.9, 0.55)
	m.emission_energy_multiplier = 3.0
	selection.material_override = m
	selection.scale = Vector3(1, 0.15, 1)
	selection.visible = false
	add_child(selection)


func _process(_delta: float) -> void:
	if selection.visible:
		var k := 1.0 + 0.03 * sin(Time.get_ticks_msec() / 160.0)
		selection.scale = Vector3(k, 0.15, k)


func _on_hex_tapped(c: Vector2i) -> void:
	if not world.cells.has(c):
		selection.visible = false
		return
	var p: Vector3 = world.axial_to_world(c.x, c.y)
	selection.position = p + Vector3(0, 0.06, 0)
	selection.visible = true
	hud.show_tile(world.describe(c))


func _shot(path: String) -> void:
	for i in 8:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path)
	print("shot saved ", path)
	get_tree().quit()
