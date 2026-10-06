extends Node3D
## The scene of tools/anim_preview.gd (a SceneTree script cannot await, a node can).


func _ready() -> void:
	var out := "/tmp"
	var model := "squad_dl3_blue"
	var frames := 24
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a.begins_with("--model="):
			model = a.substr(8)
		elif a.begins_with("--frames="):
			frames = int(a.substr(9))
	var we := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.36, 0.55, 0.32)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.7, 0.75, 0.85)
	e.ambient_light_energy = 0.6
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	we.environment = e
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	sun.light_energy = 1.3
	sun.shadow_enabled = true
	add_child(sun)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(4, 4)
	ground.mesh = pm
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.42, 0.62, 0.3)
	ground.material_override = gm
	add_child(ground)
	var shader: Shader = load("res://shaders/troops.gdshader")
	var modes := [[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]
	for i in 3:
		var inst: Node3D = (load("res://assets/models/%s.glb" % model) as PackedScene).instantiate()
		inst.position = Vector3((i - 1) * 0.75, 0, 0)
		add_child(inst)
		for mi in _meshes(inst):
			for s in mi.mesh.get_surface_count():
				var m: Material = mi.get_active_material(s)
				if m is StandardMaterial3D and (m as StandardMaterial3D).albedo_texture != null and not (m as StandardMaterial3D).emission_enabled:
					var shm := ShaderMaterial.new()
					shm.shader = shader
					shm.set_shader_parameter("albedo_tex", (m as StandardMaterial3D).albedo_texture)
					shm.set_shader_parameter("roughness_v", 0.8)
					mi.set_surface_override_material(s, shm)
			mi.set_instance_shader_parameter("march", modes[i][0])
			mi.set_instance_shader_parameter("fight", modes[i][1])
	var cam := Camera3D.new()
	cam.position = Vector3(0, 0.55, 1.25)
	cam.look_at_from_position(cam.position, Vector3(0, 0.12, 0))
	cam.fov = 42
	add_child(cam)
	for k in 6:
		await get_tree().process_frame
	for f in frames:
		await get_tree().create_timer(0.06).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("%s/f%03d.png" % [out, f])
	print("frames saved ", out)
	get_tree().quit()


func _meshes(n: Node) -> Array:
	var out: Array = []
	if n is MeshInstance3D:
		out.append(n)
	for c in n.get_children():
		out.append_array(_meshes(c))
	return out
