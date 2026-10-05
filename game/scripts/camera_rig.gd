extends Node3D
## Strategy camera: one-finger pan with inertia, pinch / wheel zoom between the strategic and close-up views,
## tap to pick a hex. The view is a continuous blend: zoom 1 = strategic (high, wide), 0 = close-up.

signal hex_tapped(cell: Vector2i)
signal order_drag(phase: int, screen: Vector2)  # 0 = start, 1 = move, 2 = end

## When set and it returns true for the press position, a one-finger drag issues orders instead of panning.
var order_filter: Callable
var _ordering := false

const SQ3 := 1.7320508

var cam: Camera3D
var zoom := 0.55
var zoom_target := 0.55
var target := Vector3(-0.6, 0, 0.2)
var bounds := Rect2(-9.0, -11.0, 18.0, 22.0)  # XZ limits for the look-at point

var _touches := {}
var _pinch_start_dist := 0.0
var _pinch_start_zoom := 0.0
var _drag_moved := 0.0
var _velocity := Vector3.ZERO
var _press_pos := Vector2.ZERO


func _ready() -> void:
	cam = Camera3D.new()
	cam.fov = 32
	add_child(cam)
	_apply()


func _process(delta: float) -> void:
	zoom = lerpf(zoom, zoom_target, 1.0 - pow(0.001, delta))
	if _touches.is_empty() and _velocity.length() > 0.01:
		target += _velocity * delta
		_velocity *= pow(0.02, delta)
	_clamp()
	_apply()


func _apply() -> void:
	var dist := lerpf(7.5, 24.0, zoom)
	var pitch := deg_to_rad(lerpf(40.0, 52.0, zoom))
	cam.position = target + Vector3(0, sin(pitch), cos(pitch)) * dist
	cam.look_at(target)


func _clamp() -> void:
	target.x = clampf(target.x, bounds.position.x, bounds.end.x)
	target.z = clampf(target.z, bounds.position.y, bounds.end.y)


## World point on the ground plane under a screen position.
func ground_at(screen: Vector2) -> Vector3:
	var from := cam.project_ray_origin(screen)
	var dir := cam.project_ray_normal(screen)
	if absf(dir.y) < 1e-5:
		return target
	var t := -from.y / dir.y
	return from + dir * t


static func world_to_axial(p: Vector3) -> Vector2i:
	var q := p.x / 1.5
	var r := p.z / SQ3 - q / 2.0
	# cube rounding
	var s := -q - r
	var rq := roundf(q)
	var rr := roundf(r)
	var rs := roundf(s)
	var dq := absf(rq - q)
	var dr := absf(rr - r)
	var ds := absf(rs - s)
	if dq > dr and dq > ds:
		rq = -rr - rs
	elif dr > ds:
		rr = -rq - rs
	return Vector2i(int(rq), int(rr))


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			zoom_target = clampf(zoom_target - 0.08, 0.0, 1.0)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			zoom_target = clampf(zoom_target + 0.08, 0.0, 1.0)
	elif event is InputEventScreenTouch:
		var t := event as InputEventScreenTouch
		if t.pressed:
			_touches[t.index] = t.position
			if _touches.size() == 1:
				_press_pos = t.position
				_drag_moved = 0.0
				_velocity = Vector3.ZERO
				_ordering = order_filter.is_valid() and order_filter.call(t.position)
				if _ordering:
					order_drag.emit(0, t.position)
			elif _touches.size() == 2:
				_pinch_start_dist = _touch_dist()
				_pinch_start_zoom = zoom_target
		else:
			var was_single := _touches.size() == 1
			_touches.erase(t.index)
			if _ordering and was_single:
				_ordering = false
				order_drag.emit(2, t.position)
				return
			if was_single and _drag_moved < 12.0:
				hex_tapped.emit(world_to_axial(ground_at(t.position)))
	elif event is InputEventScreenDrag:
		var d := event as InputEventScreenDrag
		_touches[d.index] = d.position
		if _touches.size() == 1 and _ordering:
			_drag_moved += d.relative.length()
			order_drag.emit(1, d.position)
		elif _touches.size() == 1:
			var before := ground_at(d.position - d.relative)
			var after := ground_at(d.position)
			var delta := before - after
			delta.y = 0
			target += delta
			_drag_moved += d.relative.length()
			_velocity = delta / maxf(get_process_delta_time(), 1.0 / 120.0) * 0.6
		elif _touches.size() == 2 and _pinch_start_dist > 0:
			var k := _pinch_start_dist / maxf(_touch_dist(), 1.0)
			zoom_target = clampf(_pinch_start_zoom + (k - 1.0) * 0.6, 0.0, 1.0)
	elif event is InputEventMagnifyGesture:
		var g := event as InputEventMagnifyGesture
		zoom_target = clampf(zoom_target - (g.factor - 1.0), 0.0, 1.0)
	elif event is InputEventPanGesture:
		var p := event as InputEventPanGesture
		target += Vector3(p.delta.x, 0, p.delta.y) * 0.05


func _touch_dist() -> float:
	var pts := _touches.values()
	if pts.size() < 2:
		return 0.0
	return (pts[0] as Vector2).distance_to(pts[1])


## Smoothly fly to a world point (used by «центрировать» and selection).
func focus(p: Vector3, z := -1.0) -> void:
	target = Vector3(p.x, 0, p.z)
	if z >= 0:
		zoom_target = z
