"""Lets a test build more than one Game in the same process.

SDL hands out one renderer per process, so the second
pygame.display.set_mode(..., SCALED) raises "failed to create renderer"
and any suite that constructs a second Game dies part-way through with
an error that has nothing to do with what it was checking.

Importing this before creating a Game makes every set_mode after the
first return a plain Surface instead. Game draws into its own in-RAM
surface anyway (see Game.__init__) and only touches the display in
_present(), which these tests do not call, so nothing is lost.
"""
import pygame

_real_set_mode = pygame.display.set_mode
_calls = {"n": 0}


def _set_mode(size, flags=0, *args, **kwargs):
    _calls["n"] += 1
    if _calls["n"] == 1:
        return _real_set_mode(size, flags, *args, **kwargs)
    return pygame.Surface(size)


pygame.display.set_mode = _set_mode
