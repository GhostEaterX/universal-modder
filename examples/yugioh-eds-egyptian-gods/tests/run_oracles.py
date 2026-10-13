#!/usr/bin/env python3
"""Run every in-game check of the Egyptian Gods mod in eds-decomp's headless mGBA harness.

    run_oracles.py <eds-decomp checkout> <modded.gba> [--control original.gba]

Each check boots its own state library for the ROM (tools/emu.py states, from blank SRAM), applies the RAM
setup in the .lua next to this file, drives the game with scripted keys and reads the result from RAM.
With --control, the same checks run on the original ROM too, where the God checks must fail: that proves
each check can fail. Needs the harness set up natively (EDS_NATIVE=1, MGBA_PREFIX).
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PASSWORD_KEYS = ("10 DOWN; 25 DOWN; 40 DOWN; 55 DOWN; 70 DOWN; 85 DOWN; 110 A; 230 UP; 240 A; 250 DOWN; "
                 "260 A; 270 A; 280 A; 290 A; 300 A; 310 UP; 320 RIGHT; 330 A; 340 LEFT; 350 DOWN; 360 A; "
                 "400 A; 420 A; 460 A; 520 A")             # main menu -> Password -> 10000020 -> GET CARD
SUMMON_KEYS = "15 A; 45 RIGHT; 55 RIGHT; 70 A; 260 A; 330 A; 400 A; 620 A; 690 RIGHT; 710 A; 800 A; 900 A"

CHECKS = [
    # name, script, start state, frames, keys, env, regex the log must match on the modded ROM
    ("Kaiba's duel deck holds Obelisk", "npc_deck.lua", "main_menu", 1500, "0 A; 30-1490/15 A",
     {"OPP": "16"}, r"gods in deck: Obelisk"),
    ("Yami Yugi's duel deck holds Slifer", "npc_deck.lua", "main_menu", 1500, "0 A; 30-1490/15 A",
     {"OPP": "20"}, r"gods in deck: Slifer"),
    ("Marik's duel deck holds Ra", "npc_deck.lua", "main_menu", 1500, "0 A; 30-1490/15 A",
     {"OPP": "15"}, r"gods in deck: Ra"),
    ("password 10000020 gives Slifer", "password.lua", "main_menu", 800, PASSWORD_KEYS, {}, r"Slifer 1"),
    ("player Tribute Summons Slifer", "player_summon.lua", "duel_main1", 1500, SUMMON_KEYS,
     {"GOD": "818"}, r"zones 818,"),
    ("CPU Tribute Summons Obelisk", "ai_summon.lua", "duel_main1", 3000, "30 B; 70 A", {"GOD": "817"},
     r"GOD summoned by the CPU"),
    ("CPU Tribute Summons Slifer", "ai_summon.lua", "duel_main1", 3000, "30 B; 70 A", {"GOD": "818"},
     r"GOD summoned by the CPU"),
    ("CPU Tribute Summons Ra", "ai_summon.lua", "duel_main1", 3000, "30 B; 70 A", {"GOD": "819"},
     r"GOD summoned by the CPU"),
]


def emu(decomp, *args, env=None):
    e = dict(os.environ, EDS_NATIVE="1", **(env or {}))
    r = subprocess.run([sys.executable, "tools/emu.py", *args], cwd=decomp, env=e, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def run_all(decomp, rom, tag):
    states = f"build/emu/states-oracle-{tag}"
    code, out = emu(decomp, "states", "build", "--all", "--rom", str(rom), "--dir", states)
    if code:
        sys.exit(f"states build failed for {rom}:\n{out}")
    results = []
    for name, script, state, frames, keys, env, want in CHECKS:
        code, out = emu(decomp, "lua", str(HERE / script), "--rom", str(rom), "--state", f"{states}/{state}.ss",
                        "--frames", str(frames), "--keys", keys, "--out", f"oracle-{tag}-{len(results)}", env=env)
        log = "\n".join(l for l in out.splitlines() if l.startswith("[lua]"))
        results.append((name, bool(re.search(want, log)), log))
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("decomp", type=Path)
    ap.add_argument("rom", type=Path)
    ap.add_argument("--control", type=Path, help="original ROM: every God check must fail there")
    ap.add_argument("-v", action="store_true", help="print the logs")
    args = ap.parse_args()
    ok = True
    mod = run_all(args.decomp.resolve(), args.rom.resolve(), "mod")
    ctl = run_all(args.decomp.resolve(), args.control.resolve(), "control") if args.control else None
    print(f"{'check':40} {'mod':6} {'original':8}")
    for i, (name, passed, log) in enumerate(mod):
        line = f"{name:40} {'PASS' if passed else 'FAIL':6}"
        ok &= passed
        if ctl:
            cpassed = ctl[i][1]
            line += f" {'fails, ok' if not cpassed else 'PASSES?!':8}"
            ok &= not cpassed
        print(line)
        if args.v or not passed:
            print("    " + log.replace("\n", "\n    "))
    print("ALL OK" if ok else "SOMETHING FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
