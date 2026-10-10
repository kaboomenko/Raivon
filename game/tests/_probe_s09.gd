extends SceneTree
# temporary probe (s09): sizes of the inbox rows' labels
func _initialize() -> void:
	var g: Node = load("res://scenes/main.tscn").instantiate()
	g.save_enabled = false
	root.add_child(g)
	await process_frame
	await process_frame
	g._demo("inbox")
	await process_frame
	await process_frame
	var box: Control = g.ui._modal.get_child(1)
	for n in box.find_children("*", "Label", true, false):
		var l := n as Label
		print(l.name, " pos=", l.position, " size=", l.size, " gx=", l.global_position.x, " clip=", l.clip_text, " txt=", l.text.left(20))
	quit()
