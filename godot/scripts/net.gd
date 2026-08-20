## Two or more people in the same dungeon, over a network you own.
##
## The whole thing is host-authoritative, which for this game is not a
## compromise but the obvious shape: one machine already holds the entire
## floor - grid, monsters, loot, doors - in plain variables, and it
## already knows how to write all of that out as data, because that is
## what the save file is. So the host simply keeps playing the game it
## was playing, and everyone else sends "I want to step left" and gets
## back what the floor looks like afterwards.
##
## That means a guest can never be wrong about the world, never desync,
## and never cheat: their copy holds no authority over anything. It also
## means the host's word is final if the two ever disagree, which is
## exactly what you want when one of the two is a phone on mobile data.
##
## Two messages carry everything:
##
##   floor  - the whole floor, sent when a guest joins and whenever the
##            party changes level. It is literally `Save.floor_data()`,
##            the same dictionary the save file is made of, so there is
##            one serialiser in the game and not two.
##   pulse  - what has moved since the last action: the heroes, the
##            monsters, the loot, the doors, the last few lines of the
##            log. A few kilobytes, sent after every turn.
##
## Sight is *not* sent. Every player works out what they can see from
## their own hero and the grid they already have, which saves the largest
## dictionary in the game from crossing the wire and means one player's
## torch never lights another player's screen.
##
## Crossplay is free: the phone and the PC run the same engine and the
## same protocol, so an Android guest joining a Windows host is not a
## special case, it is the only case.
class_name Net
extends Node

## The port the game listens on unless told otherwise. Not a registered
## one; high enough to be out of the way of anything else.
const PORT := 27615
const MAX_GUESTS := 3

## How many lines of the log travel with a pulse. The whole thing would
## grow without bound; the last handful is what a guest missed.
const LOG_TAIL := 8

signal party_changed()
signal note(text: String)

var game: Node                    ## the one and only game.gd
var hosting := false
var guest := false
## Who is here. The heroes themselves live in the game - one list, owned
## by the thing that owns the world - and this is only their names.
var names := {}                   ## peer id -> what to call them


func _ready() -> void:
	multiplayer.peer_connected.connect(_someone_arrived)
	multiplayer.peer_disconnected.connect(_someone_left)
	multiplayer.connected_to_server.connect(_we_are_in)
	multiplayer.connection_failed.connect(_we_are_not)
	multiplayer.server_disconnected.connect(_host_is_gone)


## Whether this copy of the game is in charge of the world.
func in_charge() -> bool:
	return not guest


func playing_together() -> bool:
	return hosting or guest


# --- opening and closing the door -----------------------------------------

## Starts listening. The host keeps playing its own run; guests drop into
## the floor it is already standing on.
func host(port := PORT) -> bool:
	shut()
	var peer := ENetMultiplayerPeer.new()
	var error := peer.create_server(port, MAX_GUESTS)
	if error != OK:
		note.emit("Port %d lässt sich nicht öffnen (Fehler %d)." % [port, error])
		return false
	multiplayer.multiplayer_peer = peer
	hosting = true
	guest = false
	game.party.clear()
	names.clear()
	game.party[1] = game.player
	names[1] = "Gastgeber"
	party_changed.emit()
	note.emit("Warte auf Mitspieler.")
	return true


func join(address: String, port := PORT) -> bool:
	shut()
	var peer := ENetMultiplayerPeer.new()
	var error := peer.create_client(address.strip_edges(), port)
	if error != OK:
		note.emit("Verbindung nicht möglich (Fehler %d)." % error)
		return false
	multiplayer.multiplayer_peer = peer
	guest = true
	hosting = false
	note.emit("Verbinde mit %s ..." % address)
	return true


## Hangs up, whichever end this is. Leaves the game running on its own,
## because a lost connection should cost a run at most once.
func shut() -> void:
	if multiplayer.multiplayer_peer != null:
		multiplayer.multiplayer_peer.close()
	multiplayer.multiplayer_peer = null
	hosting = false
	guest = false
	if game != null:
		game.party.clear()
	names.clear()
	party_changed.emit()


# --- where to find us -----------------------------------------------------

## The address to read out to whoever wants to join.
##
## A machine has several - a loopback that only talks to itself, often a
## virtual one from some other program, sometimes an IPv6 as long as your
## arm. The one a person on the same wifi needs is the private IPv4, so
## that is the one shown first and the rest are offered underneath.
static func addresses() -> Array[String]:
	var mine: Array[String] = []
	var rest: Array[String] = []
	for entry in IP.get_local_addresses():
		var text := str(entry)
		if text.begins_with("127.") or text == "::1" or text.contains(":"):
			continue
		if text.begins_with("192.168.") or text.begins_with("10.") \
				or _is_carrier_grade(text):
			mine.append(text)
		else:
			rest.append(text)
	mine.append_array(rest)
	return mine


## 172.16.x.x through 172.31.x.x is private as well, which is the one
## range people get wrong when they write this check by hand.
static func _is_carrier_grade(text: String) -> bool:
	if not text.begins_with("172."):
		return false
	var parts := text.split(".")
	if parts.size() < 2:
		return false
	var second := int(parts[1])
	return second >= 16 and second <= 31


# --- who is here ----------------------------------------------------------

func _someone_arrived(peer: int) -> void:
	if not hosting:
		return
	note.emit("Jemand verbindet sich ...")
	# The hero is built here, not there: the host owns everything that
	# can affect the world, and a guest that picked its own numbers would
	# be a guest that picked its own strength.
	var arrival = game.spawn_guest(peer)
	game.party[peer] = arrival
	names[peer] = "Gast %d" % peer
	party_changed.emit()
	send_floor(peer)
	pulse()


func _someone_left(peer: int) -> void:
	if not hosting:
		return
	if game.party.has(peer):
		game.remove_guest(peer)
		game.party.erase(peer)
		names.erase(peer)
	party_changed.emit()
	note.emit("Ein Mitspieler hat den Dungeon verlassen.")
	pulse()


func _we_are_in() -> void:
	note.emit("Verbunden. Warte auf die Ebene ...")
	# The class was picked before joining, on this machine. The host has to
	# be told, because the host is the one who builds the hero.
	rpc_id(1, "request", "class:" + str(game.hero_class), 0, 0)
	party_changed.emit()


func _we_are_not() -> void:
	guest = false
	multiplayer.multiplayer_peer = null
	note.emit("Der Gastgeber antwortet nicht.")
	party_changed.emit()


func _host_is_gone() -> void:
	guest = false
	multiplayer.multiplayer_peer = null
	note.emit("Die Verbindung zum Gastgeber ist weg.")
	party_changed.emit()


# --- the two messages -----------------------------------------------------

## The whole floor, for one guest or for everybody.
func send_floor(to := 0) -> void:
	if not hosting:
		return
	var plan: Dictionary = game.floor_for_network()
	if to == 0:
		rpc("take_floor", plan)
	else:
		rpc_id(to, "take_floor", plan)


## What has changed, to everybody.
func pulse() -> void:
	if not hosting or game.party.size() <= 1:
		return
	rpc("take_pulse", game.pulse_for_network())


@rpc("authority", "call_remote", "reliable")
func take_floor(plan: Dictionary) -> void:
	game.apply_network_floor(plan)


@rpc("authority", "call_remote", "reliable")
func take_pulse(beat: Dictionary) -> void:
	game.apply_network_pulse(beat)


## A guest asking for something to happen. The host decides whether it
## does: the request carries no numbers, only an intent, so the worst a
## broken or dishonest guest can ask for is a move that the rules will
## refuse anyway.
@rpc("any_peer", "call_remote", "reliable")
func request(what: String, x: int, y: int) -> void:
	if not hosting:
		return
	var who := multiplayer.get_remote_sender_id()
	if not game.party.has(who):
		return
	game.guest_acts(who, what, Vector2i(x, y))


func ask(what: String, step := Vector2i.ZERO) -> void:
	if not guest:
		return
	rpc_id(1, "request", what, step.x, step.y)
