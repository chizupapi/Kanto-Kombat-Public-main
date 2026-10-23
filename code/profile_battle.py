"""Profile the battle so we can see what is actually slow.

Put this file next to battle_ui.py and run it from the game folder:

    python profile_battle.py Barangay 1

Then play normally for ~20-30 seconds -- pick a team, hover skills (camera
zoom), lock in actions, press KANA, let the skill animations run -- and close
the window. It prints two tables:

  * the 25 functions that used the most time themselves ("tottime")
  * the 25 heaviest including everything they call ("cumtime")

Copy both tables back to me and I can point at the exact lines.
"""
import cProfile
import pstats
import sys

import pygame

pygame.init()
pygame.display.set_mode((1284, 702))

from battle_ui import runBattle  # noqa: E402  (needs the display to exist first)

chapter = sys.argv[1] if len(sys.argv) > 1 else "Barangay"
stage = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0

profiler = cProfile.Profile()
profiler.enable()
try:
    result = runBattle(pygame.display.get_surface(), chapter, stage)
finally:
    profiler.disable()
    print("Result:", result if "result" in dir() else "(interrupted)")
    stats = pstats.Stats(profiler).strip_dirs()
    print("\n===== TOP 25 BY OWN TIME (tottime) =====")
    stats.sort_stats("tottime").print_stats(25)
    print("\n===== TOP 25 BY CUMULATIVE TIME (cumtime) =====")
    stats.sort_stats("cumtime").print_stats(25)
    pygame.quit()
