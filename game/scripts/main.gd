extends Node3D
## Entry point: world + camera + lighting + HUD. `--shot=PATH` saves a screenshot and quits (CI / review).

const World := preload("res://scripts/world.gd")
const Hud := preload("res://scripts/hud.gd")

var world: Node3D
var cam: Camera3D
var zoom := 0.55  # 1 = strategic, 0 = close-up


func _ready() -> void:
	_environment()
	world = World.new()
	add_child(world)
	cam = Camera3D.new()
	add_child(cam)
	_place_camera()
	var hud := Hud.new()
	hud.world = world
	add_child(hud)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--zoom="):
			zoom = float(a.substr(7))
			_place_camera()
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


func _place_camera() -> void:
	# Strategic: high, wide. Close-up: low, near the capital. Both at ~50° like the reference.
	var target := Vector3(-0.6, 0, 0.2).lerp(Vector3(-2.6, 0, -0.6), 1.0 - zoom)
	var dist := lerpf(8.0, 24.0, zoom)
	var pitch := deg_to_rad(lerpf(42.0, 52.0, zoom))
	cam.fov = 32
	cam.position = target + Vector3(0, sin(pitch), cos(pitch)) * dist
	cam.look_at(target)


func _shot(path: String) -> void:
	for i in 8:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path)
	print("shot saved ", path)
	get_tree().quit()
