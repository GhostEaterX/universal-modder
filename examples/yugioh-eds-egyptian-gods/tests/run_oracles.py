#!/usr/bin/env python3
"""Run every in-game check of the Egyptian Gods mod in eds-decomp's headless mGBA harness.

    run_oracles.py <eds-decomp checkout> <gods.gba>    [--control original.gba]        # 2-Tribute build
    run_oracles.py <eds-decomp checkout> <gods-3t.gba> --tributes 3 [--control gods.gba]

Each check boots its own state library for the ROM (tools/emu.py states, from blank SRAM), applies the RAM
setup in the .lua next to this file, drives the game with scripted keys and reads the result from RAM.

A check passes when its regex matches the log (or, for "must not" checks, doesn't). With --control the same
checks also run on a control ROM, where each check says what must happen there:
  - the original ROM for the 2-Tribute suite, where every God check must fail;
  - the 2-Tribute build for the 3-Tribute suite, where the checks that tell the two rules apart must fail,
    and the rest (decks, password, the Blue-Eyes regressions) must pass.
That proves each check can fail. Needs the harness set up natively (EDS_NATIVE=1, MGBA_PREFIX).
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
NPC_KEYS = "0 A; 30-1490/15 A"
# duel_main1 -> pick the hand card, Summon, Yes, then the Tribute picks (the cursor starts on zone 0)
SUMMON_KEYS = "15 A; 45 RIGHT; 55 RIGHT; 70 A; 260 A; 330 A; 400 A; 620 A; 690 RIGHT; 710 A; 800 A; 900 A"
SUMMON3_KEYS = ("15 A; 45 RIGHT; 55 RIGHT; 70 A; 260 A; 330 A; 400 A; 620 A; 690 RIGHT; 710 A; 900 A; "
                "960 RIGHT; 980 A; 1100 A; 1200 A")
BACK_OUT_KEYS = ("15 A; 45 RIGHT; 55 RIGHT; 70 A; 260 A; 330 A; 400 A; 620 A; 690 RIGHT; 710 A; 900 A; "
                 "960 B; 1020 RIGHT; 1040 A")              # B at the 3rd pick, then No
END_TURN_KEYS = "30 B; 70 A"
# duel_main1 -> cursor up to the set Ultimate Offering, Activate, pick the hand God, Yes, three picks, position
OFFERING_KEYS = ("20 UP; 50 A; 80 RIGHT; 100 A; 780 A; 850 A; 950 A; 1030 A; 1100 A; 1250 A; 1400 A; "
                 "1450 RIGHT; 1470 A; 1600 A; 1650 RIGHT; 1670 A; 1850 A; 1950 A; 2100 A")


def check(name, script, state, frames, keys, env, regex, must=True, control="fails"):
    """must: the regex must (True) or must not (False) match. control: 'fails' / 'passes' / None."""
    return dict(name=name, script=script, state=state, frames=frames, keys=keys, env=env, regex=regex,
                must=must, control=control)


COMMON = [
    check("Kaiba's duel deck holds Obelisk", "npc_deck.lua", "main_menu", 1500, NPC_KEYS, {"OPP": "16"},
          r"gods in deck: Obelisk"),
    check("Yami Yugi's duel deck holds Slifer", "npc_deck.lua", "main_menu", 1500, NPC_KEYS, {"OPP": "20"},
          r"gods in deck: Slifer"),
    check("Marik's duel deck holds Ra", "npc_deck.lua", "main_menu", 1500, NPC_KEYS, {"OPP": "15"},
          r"gods in deck: Ra"),
    check("password 10000020 gives Slifer", "password.lua", "main_menu", 800, PASSWORD_KEYS, {}, r"Slifer 1"),
]

SUITE2 = COMMON + [
    check("player Tribute Summons Slifer", "player_summon.lua", "duel_main1", 1500, SUMMON_KEYS,
          {"GOD": "818"}, r"zones 818,"),
] + [check(f"CPU Tribute Summons {n}", "ai_summon.lua", "duel_main1", 3000, END_TURN_KEYS, {"GOD": g},
           r"GOD summoned by the CPU") for n, g in (("Obelisk", "817"), ("Slifer", "818"), ("Ra", "819"))]

SUITE3 = [dict(c, control="passes") for c in COMMON] + [
    check("player: Slifer takes all 3 fodder", "player_summon.lua", "duel_main1", 1800, SUMMON3_KEYS,
          {"GOD": "818", "FODDER": "3"}, r"zones 818,0,0,0,0 hand 5"),
    check("player: no Summon with only 2 monsters", "player_summon.lua", "duel_main1", 1800, SUMMON3_KEYS,
          {"GOD": "818", "FODDER": "2"}, r"zones 818,", must=False),
    check("player: B at the 3rd pick loses nothing", "player_summon.lua", "duel_main1", 1500, BACK_OUT_KEYS,
          {"GOD": "818", "FODDER": "3"}, r"hand 5|zones 818|zones 0,", must=False, control=None),
] + [check(f"CPU: {n} takes all 3 fodder", "ai_summon.lua", "duel_main1", 3000, END_TURN_KEYS,
           {"GOD": g, "FODDER": "3"}, rf"CPU zones {g},0,0,0,0, CPU hand 5[\s\S]*GOD summoned")
     for n, g in (("Obelisk", "817"), ("Slifer", "818"), ("Ra", "819"))] + [
    check("CPU: no God with only 2 fodder", "ai_summon.lua", "duel_main1", 3000, END_TURN_KEYS,
          {"GOD": "817", "FODDER": "2"}, r"GOD summoned", must=False),
    check("Ultimate Offering: God takes all 3", "offering.lua", "duel_main1", 2600, OFFERING_KEYS,
          {"GOD": "818", "FODDER": "3"}, r"zones 818,0,0,0,0,756 hand 5 LP 7500 normalSummonUsed 0"),
    check("Ultimate Offering: no God with 2", "offering.lua", "duel_main1", 2600, OFFERING_KEYS,
          {"GOD": "818", "FODDER": "2"}, r"zones 818,", must=False),
    check("regression: player Blue-Eyes still 2", "player_summon.lua", "duel_main1", 1500, SUMMON_KEYS,
          {"GOD": "82", "FODDER": "2"}, r"zones 82,", control="passes"),
    check("regression: CPU Blue-Eyes still 2", "ai_summon.lua", "duel_main1", 3000, END_TURN_KEYS,
          {"GOD": "82", "FODDER": "2", "THREAT": "675"}, r"GOD summoned", control="passes"),
]


def emu(decomp, *args, env=None):
    e = dict(os.environ, EDS_NATIVE="1", **(env or {}))
    r = subprocess.run([sys.executable, "tools/emu.py", *args], cwd=decomp, env=e, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def run_all(decomp, rom, tag, checks):
    states = f"build/emu/states-oracle-{tag}"
    code, out = emu(decomp, "states", "build", "--all", "--rom", str(rom), "--dir", states)
    if code:
        sys.exit(f"states build failed for {rom}:\n{out}")
    results = []
    for i, c in enumerate(checks):
        code, out = emu(decomp, "lua", str(HERE / c["script"]), "--rom", str(rom), "--state",
                        f"{states}/{c['state']}.ss", "--frames", str(c["frames"]), "--keys", c["keys"],
                        "--out", f"oracle-{tag}-{i}", env=c["env"])
        log = "\n".join(l for l in out.splitlines() if l.startswith("[lua]"))
        results.append((bool(re.search(c["regex"], log)) == c["must"], log))
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("decomp", type=Path)
    ap.add_argument("rom", type=Path)
    ap.add_argument("--tributes", type=int, choices=(2, 3), default=2)
    ap.add_argument("--control", type=Path,
                    help="the original ROM (2-Tribute suite) or the 2-Tribute build (3-Tribute suite)")
    ap.add_argument("-v", action="store_true", help="print the logs")
    args = ap.parse_args()
    checks = SUITE3 if args.tributes == 3 else SUITE2
    tag = f"mod{args.tributes}"
    mod = run_all(args.decomp.resolve(), args.rom.resolve(), tag, checks)
    ctl = run_all(args.decomp.resolve(), args.control.resolve(), f"control{args.tributes}", checks) \
        if args.control else None
    ok = True
    print(f"{'check':44} {'mod':5} control")
    for i, c in enumerate(checks):
        passed, log = mod[i]
        ok &= passed
        line = f"{c['name']:44} {'PASS' if passed else 'FAIL':5}"
        if ctl:
            cpassed = ctl[i][0]
            if c["control"] is None:
                line += " (not compared)"
            else:
                good = cpassed == (c["control"] == "passes")
                ok &= good
                line += f" {'passes' if cpassed else 'fails'}{', ok' if good else ' -- UNEXPECTED'}"
        print(line)
        if args.v or not passed:
            print("    " + log.replace("\n", "\n    "))
    print("ALL OK" if ok else "SOMETHING FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
