import sys
import traceback

import pygame

from game import Game


def _show_crash_screen(exc_text):
    # If the game crashes for any reason, show the traceback on screen
    # instead of just vanishing - there's no easy way to pull a device
    # log otherwise, so this is the only practical way to diagnose a
    # crash that only happens on a real phone.
    try:
        pygame.init()
        screen = pygame.display.set_mode((900, 650))
        pygame.display.set_caption("Dungeon Crawler - Crash")
        font = pygame.font.Font(None, 20)
        screen.fill((20, 20, 24))

        title = font.render("The game crashed. Details below:", True, (255, 210, 90))
        screen.blit(title, (10, 10))

        lines = exc_text.strip().splitlines()
        y = 40
        for line in lines[-26:]:
            surf = font.render(line[:110], True, (255, 110, 110))
            screen.blit(surf, (10, y))
            y += 22

        hint = font.render("Tap or press any key to exit", True, (200, 200, 200))
        screen.blit(hint, (10, y + 14))
        pygame.display.flip()

        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                    waiting = False
            pygame.time.wait(50)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        Game().run()
    except Exception:
        _show_crash_screen(traceback.format_exc())
        sys.exit(1)
