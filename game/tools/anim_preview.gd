extends SceneTree
## Troop animation preview (shaders/troops.gdshader): three squads close up — marching, fighting, idle — saved as
## frames for a GIF. Run with a renderer (xvfb + lavapipe): godot --path game --script res://tools/anim_preview.gd
## -- --out=DIR [--model=squad_dl3_blue] [--frames=24]


func _initialize() -> void:
	var n := Node3D.new()
	n.set_script(load("res://tools/anim_preview_node.gd"))
	root.add_child(n)
