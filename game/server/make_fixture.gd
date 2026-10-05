extends SceneTree
## Prints a minimal client-format save (scripts/save.gd v1) for server tests.
const MapGen := preload("res://scripts/sim/map_gen.gd")
const Economy := preload("res://scripts/sim/economy.gd")

func _initialize() -> void:
	var w = MapGen.generate_chapter_one(20261004)
	var cells: Array = []
	for c in w.cells:
		cells.append([c["owner"], c["controller"], c["fort"]])
	var econ = Economy.new(w, 1_800_000_000)
	print("@@" + JSON.stringify({"version": 1, "seed": 20261004, "saved_at": 1_800_000_000, "cells": cells, "econ": econ.to_dict()}))
	quit()
