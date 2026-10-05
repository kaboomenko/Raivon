extends Node
## Procedural sound effects: every sound is synthesized once into an AudioStreamWAV (no audio files,
## no licensing). `play(name, step)` — `step` shifts the pitch by major-scale degrees (ceremony pops).
## Also wraps haptics (canon §10.3: strong vibration on the seal).

const RATE := 22050
const MAJOR := [0, 2, 4, 5, 7, 9, 11]

var enabled := true:
	set(v):
		enabled = v
		_music_volume()
var _music: Array[AudioStreamPlayer] = []
var _music_on := 0
var _music_name := ""
var _cache := {}
var _players: Array[AudioStreamPlayer] = []
var _next := 0
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.seed = 99
	for i in 10:
		var p := AudioStreamPlayer.new()
		add_child(p)
		_players.append(p)
	for i in 2:
		var m := AudioStreamPlayer.new()
		m.volume_db = -80.0
		add_child(m)
		_music.append(m)


func play(name: String, step := 0, volume_db := 0.0) -> void:
	if not enabled:
		return
	var s: AudioStreamWAV = _cache.get(name)
	if s == null:
		s = _wav(_synth(name))
		_cache[name] = s
	var p := _players[_next]
	_next = (_next + 1) % _players.size()
	var semis: int = MAJOR[posmod(step, 7)] + 12 * floori(step / 7.0)
	p.stream = s
	p.pitch_scale = pow(2.0, semis / 12.0)
	p.volume_db = volume_db
	p.play()


## Background music with a 1.2 s crossfade: "map" or "battle" (tools/audio/make_music.py).
func play_music(name: String) -> void:
	if name == _music_name:
		return
	_music_name = name
	var path := "res://assets/audio/music_%s.ogg" % name
	if not ResourceLoader.exists(path):
		return
	var stream: AudioStreamOggVorbis = load(path)
	stream.loop = true
	var old := _music[_music_on]
	_music_on = 1 - _music_on
	var cur := _music[_music_on]
	cur.stream = stream
	cur.volume_db = -40.0
	cur.play()
	var tw := create_tween()
	tw.tween_property(cur, "volume_db", _music_db(), 1.2)
	tw.parallel().tween_property(old, "volume_db", -60.0, 1.2)
	tw.tween_callback(old.stop)


func _music_db() -> float:
	return -11.0 if enabled else -80.0


func _music_volume() -> void:
	if _music.size() == 2:
		_music[_music_on].volume_db = _music_db()


func haptic(ms: int) -> void:
	if OS.has_feature("mobile"):
		Input.vibrate_handheld(ms)


# ------------------------------------------------------------------ synthesis

func _synth(name: String) -> PackedFloat32Array:
	match name:
		"tap":
			return _tone(1250.0, 0.035, 0.25, 90.0)
		"pop":
			return _mix([_tone(660.0, 0.16, 0.45, 22.0), _tone(1320.0, 0.1, 0.12, 35.0)])
		"coin":
			return _concat([_tone(1568.0, 0.07, 0.3, 30.0), _tone(2093.0, 0.16, 0.3, 18.0)])
		"clash":
			return _mix([_noise(0.12, 0.35, 40.0), _tone(2150.0, 0.3, 0.12, 12.0), _tone(3310.0, 0.3, 0.09, 14.0), _tone(4730.0, 0.22, 0.06, 16.0)])
		"attack":
			return _mix([_sweep_noise(0.28, 0.35), _tone(180.0, 0.2, 0.25, 15.0)])
		"card":
			return _sweep_noise(0.32, 0.3)
		"capture":
			return _concat([_brass(523.25, 0.08, 0.25), _brass(659.25, 0.08, 0.25), _brass(783.99, 0.08, 0.25), _brass(1046.5, 0.3, 0.28)])
		"repelled":
			return _mix([_tone(110.0, 0.22, 0.6, 14.0), _noise(0.1, 0.25, 30.0)])
		"lost":
			return _concat([_brass(392.0, 0.14, 0.25), _brass(311.13, 0.35, 0.25)])
		"seal":
			return _mix([_tone(70.0, 0.45, 0.6, 7.0), _tone(140.0, 0.2, 0.3, 14.0), _noise(0.08, 0.35, 45.0)])
		"warn":
			return _concat([_brass(220.0, 0.28, 0.35), _brass(164.81, 0.5, 0.35)])
		"fanfare":
			return _concat([_brass(392.0, 0.14, 0.3), _brass(523.25, 0.14, 0.3), _brass(659.25, 0.14, 0.3), _mix([_brass(783.99, 0.9, 0.28), _brass(523.25, 0.9, 0.18)])])
		"boom":
			return _mix([_tone(48.0, 0.9, 0.6, 4.0), _noise(0.6, 0.3, 6.0)])
		"firework":
			return _concat([_sweep_noise(0.25, 0.15), _mix([_noise(0.5, 0.35, 8.0), _tone(90.0, 0.3, 0.4, 10.0)])])
	return _tone(440.0, 0.1, 0.2, 20.0)


func _n(sec: float) -> int:
	return int(sec * RATE)


## Sine with a soft attack and exponential decay.
func _tone(freq: float, dur: float, amp: float, decay: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(_n(dur))
	for i in out.size():
		var t := float(i) / RATE
		var env := minf(1.0, t / 0.004) * exp(-decay * t)
		out[i] = sin(TAU * freq * t) * amp * env
	return out


## Brass-like note: harmonics with 1/n falloff, short attack, gentle release.
func _brass(freq: float, dur: float, amp: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(_n(dur))
	for i in out.size():
		var t := float(i) / RATE
		var env := minf(1.0, t / 0.02) * minf(1.0, (dur - t) / 0.05)
		var v := 0.0
		for h in range(1, 7):
			v += sin(TAU * freq * h * t) / h
		out[i] = v * 0.7 * amp * env
	return out


func _noise(dur: float, amp: float, decay: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(_n(dur))
	var lp := 0.0
	for i in out.size():
		var t := float(i) / RATE
		lp = lerpf(lp, _rng.randf_range(-1.0, 1.0), 0.35)
		out[i] = lp * amp * exp(-decay * t)
	return out


## Whoosh: noise through a one-pole low-pass that opens up, swelling then fading.
func _sweep_noise(dur: float, amp: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(_n(dur))
	var lp := 0.0
	for i in out.size():
		var k := float(i) / out.size()
		lp = lerpf(lp, _rng.randf_range(-1.0, 1.0), 0.04 + 0.4 * k)
		out[i] = lp * amp * sin(PI * k) * 2.0
	return out


func _mix(parts: Array) -> PackedFloat32Array:
	var n := 0
	for p in parts:
		n = maxi(n, (p as PackedFloat32Array).size())
	var out := PackedFloat32Array()
	out.resize(n)
	for p in parts:
		var a: PackedFloat32Array = p
		for i in a.size():
			out[i] += a[i]
	return out


func _concat(parts: Array) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	for p in parts:
		out.append_array(p)
	return out


func _wav(samples: PackedFloat32Array) -> AudioStreamWAV:
	var data := PackedByteArray()
	data.resize(samples.size() * 2)
	for i in samples.size():
		data.encode_s16(i * 2, int(clampf(samples[i], -1.0, 1.0) * 32000.0))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = RATE
	w.stereo = false
	w.data = data
	return w
