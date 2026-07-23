import numpy as np
import pygame

SAMPLE_RATE = 44100


def _tone_array(freq_start, freq_end=None, duration=0.1, volume=0.35, wave="square"):
    freq_end = freq_start if freq_end is None else freq_end
    n = max(1, int(SAMPLE_RATE * duration))
    freqs = np.linspace(freq_start, freq_end, n)
    phase = 2 * np.pi * np.cumsum(freqs) / SAMPLE_RATE
    raw = np.sign(np.sin(phase)) if wave == "square" else np.sin(phase)
    envelope = np.linspace(1, 0, n) ** 1.5
    return (raw * envelope * volume * 32767).astype(np.int16)


def _to_sound(mono_array):
    stereo = np.column_stack([mono_array, mono_array])
    return pygame.sndarray.make_sound(np.ascontiguousarray(stereo))


class Sounds:
    def __init__(self):
        self.enabled = True
        try:
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
            self._build()
        except Exception:
            self.enabled = False

    def _build(self):
        self.hit = _to_sound(_tone_array(320, 140, 0.08, 0.35))
        self.player_hurt = _to_sound(_tone_array(160, 70, 0.14, 0.4))
        self.monster_death = _to_sound(_tone_array(420, 90, 0.25, 0.35))
        self.pickup = _to_sound(_tone_array(500, 950, 0.12, 0.3))
        self.equip = _to_sound(_tone_array(300, 550, 0.12, 0.32))
        self.stairs = _to_sound(np.concatenate([
            _tone_array(500, 500, 0.08, 0.3),
            _tone_array(750, 750, 0.14, 0.3),
        ]))
        self.levelup = _to_sound(np.concatenate([
            _tone_array(440, 440, 0.08, 0.3),
            _tone_array(554, 554, 0.08, 0.3),
            _tone_array(660, 660, 0.18, 0.35),
        ]))
        self.boss = _to_sound(_tone_array(90, 60, 0.4, 0.45, wave="sine"))
        self.death = _to_sound(np.concatenate([
            _tone_array(200, 60, 0.3, 0.4),
            _tone_array(150, 40, 0.4, 0.35),
        ]))

    def play(self, name):
        if not self.enabled:
            return
        getattr(self, name).play()
