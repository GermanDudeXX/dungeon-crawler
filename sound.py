import math
from array import array

import pygame

SAMPLE_RATE = 44100


def _tone_samples(freq_start, freq_end=None, duration=0.1, volume=0.35, wave="square"):
    freq_end = freq_start if freq_end is None else freq_end
    n = max(1, int(SAMPLE_RATE * duration))
    samples = array("h")
    phase = 0.0
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        freq = freq_start + (freq_end - freq_start) * t
        phase += 2 * math.pi * freq / SAMPLE_RATE
        s = math.sin(phase)
        raw = s if wave != "square" else (1.0 if s >= 0 else -1.0)
        envelope = (1 - t) ** 1.5
        samples.append(int(raw * envelope * volume * 32767))
    return samples


def _concat(*sample_arrays):
    out = array("h")
    for a in sample_arrays:
        out.extend(a)
    return out


def _to_sound(mono_samples):
    stereo = array("h")
    for s in mono_samples:
        stereo.append(s)
        stereo.append(s)
    return pygame.mixer.Sound(buffer=stereo.tobytes())


class Sounds:
    def __init__(self):
        self.enabled = True
        try:
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
            self._build()
        except Exception:
            self.enabled = False

    def _build(self):
        self.hit = _to_sound(_tone_samples(320, 140, 0.08, 0.35))
        self.player_hurt = _to_sound(_tone_samples(160, 70, 0.14, 0.4))
        self.monster_death = _to_sound(_tone_samples(420, 90, 0.25, 0.35))
        self.pickup = _to_sound(_tone_samples(500, 950, 0.12, 0.3))
        self.equip = _to_sound(_tone_samples(300, 550, 0.12, 0.32))
        self.stairs = _to_sound(_concat(
            _tone_samples(500, 500, 0.08, 0.3),
            _tone_samples(750, 750, 0.14, 0.3),
        ))
        self.levelup = _to_sound(_concat(
            _tone_samples(440, 440, 0.08, 0.3),
            _tone_samples(554, 554, 0.08, 0.3),
            _tone_samples(660, 660, 0.18, 0.35),
        ))
        self.boss = _to_sound(_tone_samples(90, 60, 0.4, 0.45, wave="sine"))
        self.death = _to_sound(_concat(
            _tone_samples(200, 60, 0.3, 0.4),
            _tone_samples(150, 40, 0.4, 0.35),
        ))

    def play(self, name):
        if not self.enabled:
            return
        getattr(self, name).play()
