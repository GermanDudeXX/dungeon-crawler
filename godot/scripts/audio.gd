## The noise the game makes, generated rather than shipped.
##
## The same nine sounds as sound.py, built from the same formula: a
## square wave sliding from one frequency to another under a decaying
## envelope. Nine tiny WAVs cost nothing to build at startup and mean
## there are no sound files to keep in step with the Python build - if a
## sound changes there, the numbers here are the diff.
##
## Music is the one thing that is a file: the three tracks are the same
## mp3s the pygame build plays, one per tier, so the floor sounds the
## way it looks.
class_name Audio
extends Node

const SAMPLE_RATE := 22050
const MASTER := 0.4
const MUSIC_DIR := "res://assets/music/"

## start Hz, end Hz, seconds, volume, square?  Chained entries play
## back to back, which is how the stairs and the level-up get a rising
## two- and three-note figure instead of one slide.
const TONES := {
	"hit": [[320.0, 140.0, 0.08, 0.35, true]],
	"player_hurt": [[160.0, 70.0, 0.14, 0.40, true]],
	"monster_death": [[420.0, 90.0, 0.25, 0.35, true]],
	"pickup": [[500.0, 950.0, 0.12, 0.30, true]],
	"equip": [[300.0, 550.0, 0.12, 0.32, true]],
	"stairs": [[500.0, 500.0, 0.08, 0.30, true], [750.0, 750.0, 0.14, 0.30, true]],
	"levelup": [[440.0, 440.0, 0.08, 0.30, true], [554.0, 554.0, 0.08, 0.30, true],
		[660.0, 660.0, 0.18, 0.35, true]],
	"boss": [[90.0, 60.0, 0.40, 0.45, false]],
	"death": [[200.0, 60.0, 0.30, 0.40, true], [150.0, 40.0, 0.40, 0.35, true]],
	"trap": [[220.0, 90.0, 0.18, 0.38, true]],
	"coin": [[700.0, 1200.0, 0.10, 0.28, true]],
	"denied": [[180.0, 180.0, 0.10, 0.30, true]],
	# A turn spent standing still. Quiet on purpose - it is the sound of
	# nothing happening - but there has to be one, or waiting is
	# indistinguishable from a button that does not work.
	"wait": [[300.0, 210.0, 0.07, 0.18, true]],
}

var enabled := true
var music_enabled := true
var volume := 0.75              ## 0 to 1, in tenths, set by the player
var music_volume := 0.55

var _streams := {}
var _voices: Array[AudioStreamPlayer] = []
var _next_voice := 0
var _music: AudioStreamPlayer
var _music_track := ""


func _ready() -> void:
	for name in TONES:
		_streams[name] = _build(TONES[name])
	# A handful of players, used round-robin. One player would cut its
	# own sound off every time two things happen in the same turn, which
	# in this game is most turns: you hit, it dies, gold drops.
	for _i in 6:
		var voice := AudioStreamPlayer.new()
		voice.volume_db = linear_to_db(MASTER * volume)
		add_child(voice)
		_voices.append(voice)

	_music = AudioStreamPlayer.new()
	_music.volume_db = linear_to_db(MASTER * music_volume)
	add_child(_music)


## Sets how loud everything is, in the same tenths the settings screen
## shows. Zero is silence rather than a very quiet game: linear_to_db(0)
## is negative infinity, which some drivers do not take kindly to.
func set_volume(level: float) -> void:
	volume = clampf(level, 0.0, 1.0)
	for voice in _voices:
		voice.volume_db = -80.0 if volume <= 0.0 else linear_to_db(MASTER * volume)


func set_music_volume(level: float) -> void:
	music_volume = clampf(level, 0.0, 1.0)
	if _music != null:
		_music.volume_db = (-80.0 if music_volume <= 0.0
			else linear_to_db(MASTER * music_volume))


func play(name: String) -> void:
	if not enabled or volume <= 0.0 or not _streams.has(name):
		return
	var voice: AudioStreamPlayer = _voices[_next_voice]
	_next_voice = (_next_voice + 1) % _voices.size()
	voice.stream = _streams[name]
	voice.play()


## Switches tracks only when the track actually changes, so walking down
## a staircase inside the same tier does not restart the music.
func play_music(file: String) -> void:
	if file == "" or not music_enabled:
		return
	if file == _music_track and _music.playing:
		return
	# Loaded past the resource cache: a cached track outlives the node
	# that plays it and Godot reports it as leaked at exit. Nothing else
	# in the game wants these three files, so there is nothing to share.
	var stream: Variant = ResourceLoader.load(
		MUSIC_DIR + file, "", ResourceLoader.CACHE_MODE_IGNORE)
	if stream == null:
		return
	if stream is AudioStreamMP3:
		stream.loop = true
	_music_track = file
	_music.stream = stream
	_music.play()


func set_music_enabled(on: bool) -> void:
	music_enabled = on
	if not on:
		_music.stop()
		_music_track = ""
	elif _music.stream != null:
		_music.play()


## One sound, as a 16-bit mono WAV. The envelope is (1-t)^1.5, the same
## decay curve as the Python build - a flat tone sounds like a mistake,
## a decaying one sounds like a hit.
func _build(parts: Array) -> AudioStreamWAV:
	var data := PackedByteArray()
	var phase := 0.0
	for part in parts:
		var from: float = part[0]
		var to: float = part[1]
		var count: int = maxi(1, int(SAMPLE_RATE * float(part[2])))
		var volume: float = part[3]
		var square: bool = part[4]
		for i in count:
			var t := float(i) / float(count - 1) if count > 1 else 0.0
			var freq: float = from + (to - from) * t
			phase += TAU * freq / float(SAMPLE_RATE)
			var wave := sin(phase)
			if square:
				wave = 1.0 if wave >= 0.0 else -1.0
			var value := int(wave * pow(1.0 - t, 1.5) * volume * 32767.0)
			# Little-endian 16-bit, which is what FORMAT_16_BITS means.
			var unsigned: int = value & 0xFFFF
			data.append(unsigned & 0xFF)
			data.append((unsigned >> 8) & 0xFF)

	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = SAMPLE_RATE
	stream.stereo = false
	stream.data = data
	return stream


## Lets go of the track on the way out, so it is not still playing when
## the tree is torn down under it.
func _exit_tree() -> void:
	_music.stop()
	_music.stream = null

