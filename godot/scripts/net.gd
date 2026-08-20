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
signal traced()

var game: Node                    ## the one and only game.gd
var hosting := false
var guest := false
## Who is here. The heroes themselves live in the game - one list, owned
## by the thing that owns the world - and this is only their names.
var names := {}                   ## peer id -> what to call them
var _dialing := -1.0              ## seconds spent knocking on a door
var _floorless := false           ## a guest that has not been handed a floor yet
var _asked := 0.0
var _asks := 0
var trail: Array[String] = []     ## the last few steps, for reading
var _dialled := ""                ## the address currently being tried


func _ready() -> void:
	multiplayer.peer_connected.connect(_someone_arrived)
	multiplayer.peer_disconnected.connect(_someone_left)
	multiplayer.connected_to_server.connect(_we_are_in)
	multiplayer.connection_failed.connect(_we_are_not)
	multiplayer.server_disconnected.connect(_host_is_gone)


## Gives up knocking after a while.
##
## ENet keeps trying for a long time and says nothing, so a guest that
## typed one digit wrong - or whose host is behind a firewall that never
## answered - sits on "connecting ..." for ever and has no idea which of
## the two it is. Twelve seconds is long enough for any wifi and short
## enough to still be a message rather than a hang.
func _process(delta: float) -> void:
	_keep_asking(delta)
	if _dialing < 0.0:
		return
	_dialing += delta
	if _dialing < 12.0:
		return
	_dialing = -1.0
	shut()
	note.emit("Kein Kontakt zum Gastgeber.\nBeide im selben WLAN?"
		+ " Adresse richtig abgetippt?\nAuf einem Windows-Gastgeber muss die"
		+ " Freigabe der Firewall erlaubt sein.")


## Writes down one step of the connection, on the screen and into the log
## file.
##
## "It does not work" is not something anyone can act on, and a network
## has a dozen ways to half-work. So every step says so: the port opened,
## somebody knocked, the floor went out and how big it was, the floor came
## in. Printed as well as shown, because print reaches the log file and a
## log file can be sent to somebody who was not in the room.
func trace(text: String) -> void:
	var line := "%6.2f s  %s" % [Time.get_ticks_msec() / 1000.0, text]
	print("[Netz] " + line)
	trail.append(line)
	while trail.size() > 8:
		trail.remove_at(0)
	traced.emit()


## Whether this copy of the game is in charge of the world.
func in_charge() -> bool:
	return not guest


func playing_together() -> bool:
	return hosting or guest


## Asking again, and again, until the floor is actually here.
##
## The host sends it the moment somebody connects, which on one machine
## is instant and in order. Across a real network that first packet can
## go out before the guest has finished setting itself up - and then it
## is simply gone, and the guest waits for ever for something nobody is
## going to send again. A guest that keeps asking cannot get stuck that
## way.
func _keep_asking(delta: float) -> void:
	if not guest or not _floorless:
		return
	_asked += delta
	if _asked < 2.0:
		return
	_asked = 0.0
	_asks += 1
	rpc_id(1, "request", "hello", 0, 0)
	trace("frage nach der Ebene (Versuch %d)" % _asks)
	if _asks == 3:
		note.emit("Verbunden, aber es kommt keine Ebene zurück."
			+ "\nLäuft auf beiden Geräten dieselbe Version?")


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
	trace("Port %d offen" % port)
	game.party.clear()
	names.clear()
	game.party[1] = game.player
	names[1] = "Gastgeber"
	party_changed.emit()
	note.emit("Warte auf Mitspieler.")
	return true


## `address` may carry a port - "10.0.0.5:27615" - because that is how
## everybody writes an address down, and typing it out in full should
## not be the thing that fails.
func join(address: String, port := PORT) -> bool:
	shut()
	var where := address.strip_edges()
	if where.count(":") == 1:
		var parts := where.split(":")
		where = parts[0]
		if parts[1].is_valid_int():
			port = int(parts[1])
	var peer := ENetMultiplayerPeer.new()
	var error := peer.create_client(where, port)
	if error != OK:
		note.emit("Verbindung nicht möglich (Fehler %d)." % error)
		return false
	multiplayer.multiplayer_peer = peer
	guest = true
	hosting = false
	_dialing = 0.0
	_floorless = true
	_asked = 1.6
	_asks = 0
	_dialled = where
	trace("wähle %s:%d" % [where, port])
	note.emit("Verbinde mit %s ..." % where)
	return true


## Hangs up, whichever end this is. Leaves the game running on its own,
## because a lost connection should cost a run at most once.
func shut() -> void:
	if hosting or guest:
		trace("shut() aufgerufen")
	_dialing = -1.0
	_floorless = false
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
	trace("Peer %d verbunden" % peer)
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
	trace("Peer %d ist weg" % peer)
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
	_dialing = -1.0
	trace("verbunden, ich bin %d" % multiplayer.get_unique_id())
	game.remember_host(_dialled)
	note.emit("Verbunden. Warte auf die Ebene ...")
	# The class was picked before joining, on this machine. The host has to
	# be told, because the host is the one who builds the hero.
	rpc_id(1, "request", "class:" + str(game.hero_class), 0, 0)
	party_changed.emit()


func _we_are_not() -> void:
	trace("Verbindung abgelehnt")
	_dialing = -1.0
	guest = false
	multiplayer.multiplayer_peer = null
	note.emit("Der Gastgeber antwortet nicht.")
	party_changed.emit()


func _host_is_gone() -> void:
	trace("Gastgeber weg (server_disconnected)")
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
	trace("Ebene %d raus an %s (%d Bytes)" % [game.depth,
		"alle" if to == 0 else str(to), var_to_bytes(plan).size()])
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
	_floorless = false
	trace("Ebene angekommen (%d Bytes)" % var_to_bytes(plan).size())
	note.emit("Im Dungeon.")
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
	if what == "hello":
		# Somebody is still waiting for a floor. Sending it again costs
		# fifteen kilobytes and fixes every way the first one could have
		# gone missing.
		trace("Peer %d fragt nach der Ebene" % who)
		send_floor(who)
		pulse()
		return
	game.guest_acts(who, what, Vector2i(x, y))


func ask(what: String, step := Vector2i.ZERO) -> void:
	if not guest:
		return
	rpc_id(1, "request", what, step.x, step.y)
