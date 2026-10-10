extends SceneTree
## Temporary probe for plan step s13 (map labels; deleted when the step is done): runs main.tscn with the usual
## screenshot arguments, then adds every kind of map label next to the camera's target — chips with icons (⛳ ⇄ ⇢),
## the strike chip, floaters, the drag forecast's star, a routed army, an army in the fog and two plates stacked.

var main: Node


func _initialize() -> void:
	main = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)
	current_scene = main
	_go()


func _go() -> void:
	for i in 4:
		await process_frame
	var mv = main.map_view
	var sim = main.sim
	var cap: int = sim.states[0]["capital_id"]
	var ring: Array = []
	for n in sim.neighbors[cap]:
		if n >= 0:
			ring.append(n)
	mv.hex_label(ring[0], "⛳ 1:23", mv.state_color(2).lightened(0.35))
	mv.hex_label(ring[1], "⇄ отдаём")
	mv.hex_label(ring[2], "⇢ 0:35", Color(0.6, 0.85, 1.0))
	mv.strike_arrow(ring[3], cap, "⚔ 19:09")
	var drag: Label3D = main._drag_lbl
	drag.text = "×1.4 ★"
	drag.modulate = Color(0.35, 1.0, 0.45)
	drag.position = mv.cell_world(ring[4]) + Vector3(0, 1.0, 0)
	drag.visible = true
	# armies: the first enemy routed, the second in the fog, the third moved onto a player army (stacked plates)
	var enemy: Array = []
	var mine: Array = []
	for a in main.armies:
		(mine if int(a["side"]) == 0 else enemy).append(a)
	if enemy.size() > 0:
		enemy[0]["routed"] = true
	if enemy.size() > 2 and mine.size() > 0:
		enemy[2]["hex"] = mine[0]["hex"]
	var fog_hex: int = int(enemy[1]["hex"]) if enemy.size() > 1 else -1
	var t := 0.0
	while true:
		await process_frame
		t += 0.016
		if fog_hex >= 0:
			var vis := {}
			for c in sim.cells:
				if int(c["id"]) != fog_hex:
					vis[int(c["id"])] = true
			mv.fog_visible = vis
		if fmod(t, 0.5) < 0.017:
			mv.floater(ring[5], "+86", Color(1.0, 0.88, 0.4), "coin")
			mv.floater(cap, "Захвачено", Color(0.75, 0.85, 1.0))
