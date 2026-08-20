## A thumbstick for the left half of the screen.
##
## Replaces the four-button pad, which could only ever send four
## directions - and four directions is most of what makes a game feel
## nailed to a grid, even when the sprites glide between the tiles.
##
## The stick appears wherever the thumb lands rather than sitting in a
## fixed corner: on a phone held in landscape there is no one place that
## is comfortable for every hand, and a control you have to find is a
## control you fight.
class_name Stick
extends Control

## How far the thumb has to travel before it counts as a direction. Below
## this it is a tap, not a push, and the hero stands still.
const DEADZONE := 26.0
const RADIUS := 92.0        ## how far out the knob can be dragged
const BASE_ALPHA := 0.22

signal aimed(direction: Vector2i)

var _touching := -1         ## the finger currently on the stick
var _origin := Vector2.ZERO
var _knob := Vector2.ZERO
var _direction := Vector2i.ZERO


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP


func _gui_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		var touch := event as InputEventScreenTouch
		if touch.pressed and _touching < 0:
			_touching = touch.index
			_grab(touch.position)
		elif not touch.pressed and touch.index == _touching:
			_release()
		accept_event()
	elif event is InputEventScreenDrag:
		var drag := event as InputEventScreenDrag
		if drag.index == _touching:
			_move(drag.position)
			accept_event()
	# The same with a mouse, so the stick can be tried on the machine it
	# is built on rather than only on the phone.
	elif event is InputEventMouseButton:
		var click := event as InputEventMouseButton
		if click.button_index == MOUSE_BUTTON_LEFT:
			if click.pressed:
				_touching = 0
				_grab(click.position)
			else:
				_release()
			accept_event()
	elif event is InputEventMouseMotion and _touching >= 0:
		_move((event as InputEventMouseMotion).position)
		accept_event()


func _grab(where: Vector2) -> void:
	_origin = where
	_knob = where
	_aim(Vector2i.ZERO)
	queue_redraw()


func _move(where: Vector2) -> void:
	_knob = where
	var away: Vector2 = where - _origin
	if away.length() < DEADZONE:
		_aim(Vector2i.ZERO)
		queue_redraw()
		return
	# Snapped to the eight directions the game can actually walk in.
	# Sixteen would only produce steps the dungeon cannot take.
	var angle := away.angle()
	var eighth := int(round(angle / (TAU / 8.0))) % 8
	if eighth < 0:
		eighth += 8
	const STEPS := [Vector2i(1, 0), Vector2i(1, 1), Vector2i(0, 1), Vector2i(-1, 1),
		Vector2i(-1, 0), Vector2i(-1, -1), Vector2i(0, -1), Vector2i(1, -1)]
	_aim(STEPS[eighth])
	queue_redraw()


func _release() -> void:
	_touching = -1
	_aim(Vector2i.ZERO)
	queue_redraw()


func _aim(direction: Vector2i) -> void:
	if direction == _direction:
		return
	_direction = direction
	aimed.emit(direction)


func direction() -> Vector2i:
	return _direction


## How far the thumb has been pushed, and which way, before the snap to
## eight directions. Needed by whoever has to decide which single axis a
## diagonal was mostly meant as - the snapped direction has thrown that
## away by then.
func pull() -> Vector2:
	if _touching < 0:
		return Vector2.ZERO
	return _knob - _origin


func _draw() -> void:
	if _touching < 0:
		return
	draw_circle(_origin, RADIUS, Color(1, 1, 1, BASE_ALPHA * 0.5))
	draw_circle(_origin, RADIUS, Color(1, 1, 1, BASE_ALPHA), false, 3.0)
	var away: Vector2 = _knob - _origin
	if away.length() > RADIUS:
		away = away.normalized() * RADIUS
	draw_circle(_origin + away, 34.0, Color(1, 1, 1, BASE_ALPHA * 1.8))
