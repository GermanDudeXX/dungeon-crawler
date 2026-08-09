"""Runs every regression suite and reports one line each.

    python tests/run_all.py            # everything
    python tests/run_all.py potions    # only suites whose name contains this

These live in the repository on purpose. They used to sit in a scratch
directory outside it, which Windows cleaned out - taking the whole suite
with it. Tests that protect the game across sessions have to be in the
thing they protect.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Order matters only for reading the output: cheap and foundational first.
SUITES = [
    "test_music", "test_ssl", "test_installer", "test_tiers", "test_levelup",
    "test_menu_layout", "test_run_loop", "test_map_cache", "test_depth_systems",
    "test_up_stairs", "test_loop_timing", "test_updater_swap",
    "test_wave1", "test_potions", "test_rooms", "test_enemies",
    "test_classes", "test_juice", "test_smith", "test_ui_music",
]


def main():
    wanted = sys.argv[1:]
    suites = [s for s in SUITES
              if not wanted or any(w.lower() in s.lower() for w in wanted)]
    if not suites:
        print(f"no suite matches {wanted}")
        return 1

    env = dict(os.environ)
    # Silent by default: a full sweep otherwise plays the game's music at
    # whoever is running it.
    env.setdefault("SDL_VIDEODRIVER", "dummy")
    env.setdefault("SDL_AUDIODRIVER", "dummy")

    failed = []
    started = time.perf_counter()
    for name in suites:
        path = os.path.join(HERE, name + ".py")
        if not os.path.exists(path):
            print(f"  MISSING  {name}")
            failed.append(name)
            continue
        t = time.perf_counter()
        proc = subprocess.run([sys.executable, path], cwd=ROOT, env=env,
                              capture_output=True, text=True)
        secs = time.perf_counter() - t
        tail = (proc.stdout or proc.stderr or "").strip().splitlines()
        last = tail[-1] if tail else "(no output)"
        if proc.returncode == 0 and "PASSED" in last.upper():
            print(f"  ok       {name:22s} {secs:5.1f}s")
        else:
            print(f"  FAIL     {name:22s} {secs:5.1f}s  {last[:90]}")
            failed.append(name)

    total = time.perf_counter() - started
    print(f"\n{len(suites) - len(failed)}/{len(suites)} passed in {total:.0f}s")
    if failed:
        print("failed: " + " ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
