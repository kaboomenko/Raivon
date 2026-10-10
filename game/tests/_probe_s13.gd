extends SceneTree
## Temporary probe for plan step s13 (map labels; deleted when the step is done): runs main.tscn with the usual
## screenshot arguments, then adds every kind of map label next to the camera's target — chips with icons (\u26F3 \u21C4 \u21E2),
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
	var taken := {}
	for a in main.armies:
		taken[int(a["hex"])] = true
	var ring: Array = []  # hexes nearest the camera's target with no army on them
	var target: Vector3 = main.rig.target
	var ids: Array = []
	for c in sim.cells:
		ids.append(int(c["id"]))
	ids.sort_custom(func(x, y): return mv.cell_world(x).distance_to(target) < mv.cell_world(y).distance_to(target))
	for id in ids:
		if not taken.has(id) and id != cap:
			ring.append(id)
		if ring.size() >= 8:
			break
	mv.hex_label(ring[0], "\u26F3 1:23", mv.state_color(2).lightened(0.35))
	mv.hex_label(ring[1], "\u21C4 отдаём")
	mv.hex_label(ring[2], "\u21E2 0:35", Color(0.6, 0.85, 1.0))
	var nb := -1
	for n in sim.neighbors[ring[3]]:
		if n >= 0 and n != ring[0] and n != ring[1] and n != ring[2]:
			nb = n
	mv.strike_arrow(ring[3], nb, "\u2694 19:09")
	var drag: Label3D = main._drag_lbl
	drag.text = "×1.4 \u2605"
	drag.modulate = Color(0.35, 1.0, 0.45)
	drag.position = mv.cell_world(ring[6]) + Vector3(0, 1.0, 0)
	drag.visible = true
	# armies: the enemy nearest the camera in the fog, the next one routed; two player armies on one hex (stacked
	# plates), one of them with a three-digit strength
	var enemy: Array = []
	var mine: Array = []
	for a in main.armies:
		(mine if int(a["side"]) == 1 else enemy).append(a)
	enemy.sort_custom(func(x, y): return mv.cell_world(int(x["hex"])).distance_to(target) < mv.cell_world(int(y["hex"])).distance_to(target))
	var fog_hex: int = int(enemy[0]["hex"]) if enemy.size() > 0 else -1
	if enemy.size() > 1:
		enemy[1]["routed"] = true
	if mine.size() > 1:
		mine[1]["hex"] = mine[0]["hex"]  # two plates on one spot: they stack
		mine[1]["str"] = 152000
		mine[1]["max_str"] = 200000
	var next := 0
	while true:
		await process_frame
		if fog_hex >= 0:
			var vis := {}
			for c in sim.cells:
				if int(c["id"]) != fog_hex:
					vis[int(c["id"])] = true
			mv.fog_visible = vis
		if Time.get_ticks_msec() >= next:
			next = Time.get_ticks_msec() + 1600
			mv.floater(ring[5], "+86", Color(1.0, 0.88, 0.4), "coin")
			mv.floater(ring[7], "Захвачено", Color(0.75, 0.85, 1.0))
