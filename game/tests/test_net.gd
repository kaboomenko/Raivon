extends SceneTree
## Cloud save round trip against a running server (apps/server). Skips when no server answers.
## Run: (cd apps/server && PORT=8091 npx tsx src/index.ts &) ; godot --headless --path game --script res://tests/test_net.gd -- --server=http://127.0.0.1:8091

const Net := preload("res://scripts/net.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	if FileAccess.file_exists(Net.STATE_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(Net.STATE_PATH))
	var a: Node = Net.new()
	root.add_child(a)
	await a.start()
	if not a.online:
		print("SKIP  no server (pass --server=URL)")
		quit(0)
		return
	_check(a.token != "" and a.device_id.length() == 32, "guest login with a random install id")
	_check(absi(a.server_offset) < 5, "server time offset is sane (%d s)" % a.server_offset)
	var save := {"version": 1, "seed": 20261004, "saved_at": int(Time.get_unix_time_from_system()), "cells": [[1, 1, 0]],
		"econ": {"res": {"gold": 1234, "food": 1, "metal": 1, "raivite": 50}}}
	await a.push(save)
	_check(a.rev == 1, "first upload gets revision 1")
	save["econ"]["res"]["gold"] = 2000
	await a.push(save)
	_check(a.rev == 2, "second upload gets revision 2")
	# a second install of the same account (same install id, fresh local state) restores the cloud save
	var b: Node = Net.new()
	root.add_child(b)
	b.url = a.url
	b.device_id = a.device_id
	var got := {"data": {}}
	b.remote_newer.connect(func(d: Dictionary): got["data"] = d)
	var auth: Dictionary = await b._request(HTTPClient.METHOD_POST, "/v1/auth/guest", {"device_id": b.device_id})
	b.token = String(auth["json"]["token"])
	b.online = true
	b.rev = 0
	await b.pull()
	_check(int(got["data"].get("econ", {}).get("res", {}).get("gold", 0)) == 2000 and b.rev == 2, "another device restores the newest cloud save")
	# a stale writer (base rev 0) is rejected, then reconciles: the newer save wins
	var c: Node = Net.new()
	root.add_child(c)
	c.url = a.url
	c.token = a.token
	c.online = true
	c.rev = 1
	var newer := save.duplicate(true)
	newer["saved_at"] = int(Time.get_unix_time_from_system()) + 100
	newer["econ"]["res"]["gold"] = 3000
	await c.push(newer)
	await root.get_tree().create_timer(0.5).timeout
	_check(c.rev == 3, "a stale but newer save reconciles to revision 3 (got %d)" % c.rev)
	print("\n%s" % ("ALL NET CHECKS PASSED" if fails == 0 else "%d NET CHECK(S) FAILED" % fails))
	quit(1 if fails > 0 else 0)
