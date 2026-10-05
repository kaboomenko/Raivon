extends Node
## Cloud saves through the Raivon server (apps/server, docs/dev/server.md): guest login by a random install id,
## server time, upload after every autosave with optimistic revisions, restore when the cloud copy is newer.
## Off when no server is configured (project setting raivon/server_url or the --server=URL argument).

signal remote_newer(data: Dictionary)
signal status_changed(online: bool)

const STATE_PATH := "user://net.json"

var url := ""
var token := ""
var device_id := ""
var rev := 0  # server revision our local save is based on
var server_offset := 0  # server time − device time, seconds
var online := false
var _queued: Dictionary = {}
var _busy := false


func start() -> void:
	url = String(ProjectSettings.get_setting("raivon/server_url", ""))
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--server="):
			url = a.substr(9)
	url = url.trim_suffix("/")
	if url == "":
		return
	_load_state()
	if device_id == "":
		device_id = Crypto.new().generate_random_bytes(16).hex_encode()
		_save_state()
	var boot := await _request(HTTPClient.METHOD_GET, "/v1/bootstrap")
	if boot["code"] != 200:
		_set_online(false)
		return
	server_offset = int(boot["json"].get("server_time", 0)) - int(Time.get_unix_time_from_system())
	var auth := await _request(HTTPClient.METHOD_POST, "/v1/auth/guest", {"device_id": device_id})
	if auth["code"] != 200:
		_set_online(false)
		return
	token = String(auth["json"]["token"])
	_save_state()
	_set_online(true)
	await pull()
	if not _queued.is_empty():
		var d := _queued
		_queued = {}
		push(d)


## Fetches the cloud save; emits remote_newer when the server has a revision we haven't seen.
func pull() -> void:
	var r := await _request(HTTPClient.METHOD_GET, "/v1/save")
	if r["code"] != 200:
		return
	var remote_rev := int(r["json"].get("rev", 0))
	var data: Variant = r["json"].get("data", null)
	if remote_rev > rev and typeof(data) == TYPE_DICTIONARY:
		rev = remote_rev
		_save_state()
		remote_newer.emit(data)


## Uploads a save (the same dictionary scripts/save.gd writes). Coalesces while a request is in flight.
func push(data: Dictionary) -> void:
	if url == "":
		return
	if not online or _busy:
		_queued = data
		return
	_busy = true
	var r := await _request(HTTPClient.METHOD_PUT, "/v1/save", {"base_rev": rev, "data": data})
	_busy = false
	if r["code"] == 200:
		rev = int(r["json"]["rev"])
		_save_state()
	elif r["code"] == 409:
		# another device wrote first: the newer save wins
		var remote := await _request(HTTPClient.METHOD_GET, "/v1/save")
		if remote["code"] == 200:
			var rd: Variant = remote["json"].get("data", null)
			var remote_at := int(remote["json"].get("saved_at", 0))
			rev = int(remote["json"].get("rev", rev))
			_save_state()
			if typeof(rd) == TYPE_DICTIONARY and remote_at > int(data.get("saved_at", 0)):
				remote_newer.emit(rd)
			else:
				push(data)
	elif r["code"] == 401:
		_set_online(false)
	if not _queued.is_empty() and not _busy:
		var q := _queued
		_queued = {}
		push(q)


func _request(method: int, path: String, body: Variant = null) -> Dictionary:
	var http := HTTPRequest.new()
	http.timeout = 10.0
	add_child(http)
	var headers := PackedStringArray(["Content-Type: application/json"])
	if token != "":
		headers.append("Authorization: Bearer " + token)
	var payload := "" if body == null else JSON.stringify(body)
	var err := http.request(url + path, headers, method, payload)
	if err != OK:
		http.queue_free()
		return {"code": 0, "json": {}}
	var res: Array = await http.request_completed
	http.queue_free()
	var code: int = res[1]
	var text: String = (res[3] as PackedByteArray).get_string_from_utf8()
	var parsed: Variant = JSON.parse_string(text) if text != "" else {}
	return {"code": code, "json": parsed if typeof(parsed) == TYPE_DICTIONARY else {}}


func _set_online(v: bool) -> void:
	online = v
	status_changed.emit(v)


func _load_state() -> void:
	if not FileAccess.file_exists(STATE_PATH):
		return
	var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(STATE_PATH))
	if typeof(d) == TYPE_DICTIONARY:
		device_id = String(d.get("device_id", ""))
		rev = int(d.get("rev", 0))


func _save_state() -> void:
	var f := FileAccess.open(STATE_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify({"device_id": device_id, "rev": rev}))
