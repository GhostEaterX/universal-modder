#!/usr/bin/env python3
"""Run every in-game check of the Egyptian Gods mod in eds-decomp's headless mGBA harness.

    run_oracles.py <eds-decomp checkout> <gods.gba>    [--control original.gba]        # 2-Tribute build
    run_oracles.py <eds-decomp checkout> <gods-3t.gba> --tributes 3 [--control gods.gba]
    run_oracles.py <eds-decomp checkout> <gods-fx.gba> --effects [--control gods.gba]   # effects builds
    run_oracles.py <eds-decomp checkout> <gods-3t-fx.gba> --tributes 3 --effects [--control gods-3t.gba]

Each check boots its own state library for the ROM (tools/emu.py states, from blank SRAM), applies the RAM
setup in the .lua next to this file, drives the game with scripted keys and reads the result from RAM.

A check passes when its regex matches the log (or, for "must not" checks, doesn't). With --control the same
checks also run on a control ROM, where each check says what must happen there:
  - the original ROM for the 2-Tribute suite, where every God check must fail;
  - the 2-Tribute build for the 3-Tribute suite, where the checks that tell the two rules apart must fail,
    and the rest (decks, password, the Blue-Eyes regressions) must pass;
  - the same build without effects for an effects suite: every effect check must fail there and the
    regressions (ordinary cards whose effects go through the relocated table) must pass. The effects suite
    also runs its build's base suite, uncompared; in it a God's hand menu has no Set, so the God summons
    take one RIGHT less.
A check with a control key list (ckeys) plays those keys on the control instead, where the menus differ.
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


def check(name, script, state, frames, keys, env, regex, must=True, control="fails", ckeys=None):
    """must: the regex must (True) or must not (False) match. control: 'fails' / 'passes' / None.
    script None: regex is bytes the ROM file itself must contain."""
    return dict(name=name, script=script, state=state, frames=frames, keys=keys, env=env, regex=regex,
                must=must, control=control, ckeys=ckeys)


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


# Effects builds. All from duel_main1 unless noted; effects.lua stages the field (see its header).
E = "effects.lua"
# cursor up to the monster in zone 0, its menu, Activate (the third command), the prompt, then the picks
OBELISK_KEYS = ("20 UP; 40 UP; 70 A; 120 RIGHT; 180 RIGHT; 240 A; 450 A; 520 RIGHT; 560 A; 720 A; 780 RIGHT; "
                "820 A")                                    # Tribute zones 1 and 2
RA_DESTROY_KEYS = "20 UP; 40 UP; 70 A; 120 RIGHT; 180 RIGHT; 240 A; 450 A; 500 UP; 540 A"   # the CPU's zone 0
# duel_turn2 (the player's turn 2): B, Enter Battle Phase, zone 0's Attack, the CPU's zone 0
BATTLE_KEYS = "20 B; 80 A; 380 A; 430 RIGHT; 470 A; 560 A; 650 A; 750 A"
FISH_KEYS = "15 A; 45 RIGHT; 55 RIGHT; 70 A; 200 A"         # Normal Summon a Level 4 from the hand
SKULL_KEYS = "15 A; 45 RIGHT; 55 RIGHT; 70 A; 260 A; 330 A; 400 A; 620 A; 800 A; 900 A"   # one Tribute (zone 1)
# Tribute to The Doomed from the hand: Activate, discard, the CPU's zone 0
TTTD_KEYS = "15 A; 60 RIGHT; 100 RIGHT; 140 A; 450 A; 600 A; 660 UP; 700 UP; 740 UP; 780 A"
CARD_TEXT = b"Requires %d Tributes to Normal Summon (cannot be Normal Set)."
GODS = ("817", "818", "819")


def no_set(keys):
    """A God's hand menu in an effects build: Card View, Summon (no Set), so Summon is one RIGHT away."""
    return keys.replace("45 RIGHT; 55 RIGHT; 70 A", "45 RIGHT; 70 A")


def fx_suite(tributes):
    summon = SUMMON3_KEYS if tributes == 3 else SUMMON_KEYS
    fodder = ",".join(f"{z}:1" for z in range(tributes))
    ra_yes = no_set(summon) + ("; 2150 A" if tributes == 3 else "; 1800 A")
    six = lambda card: ",".join([card] * 6)
    return [
        check("Obelisk: Tribute 2, destroy the CPU's monsters", E, "duel_main1", 1800, OBELISK_KEYS,
              {"P_ZONES": "0:817,1:1,2:1", "C_ZONES": "0:1,1:104,2:507"},
              r"P 817,0,0,0,0 C 0,0,0,0,0 .*grave 2 3 links P\{0\[ noatk\]\}"),
        check("Obelisk: no Activate with 1 other monster", E, "duel_main1", 1800, OBELISK_KEYS,
              {"P_ZONES": "0:817,1:1", "C_ZONES": "0:1,1:104,2:507"}, r"grave \d+ [1-9]", must=False,
              control="passes"),
        check("CPU: Obelisk clears the player's monsters", E, "duel_main1", 3000, END_TURN_KEYS,
              {"C_ZONES": "0:817,1:1,2:1", "P_ZONES": "0:82,1:104", "C_HAND": "1,1,1,1,1"},
              r"P 0,0,0,0,0 C 817,0,0,\d+,\d+ LP 8000 8000 .*grave 2 2 links P\{\} C\{0\[ noatk\]\}"),
        check("Slifer: 3 cards in hand = 3000, beats 2500", E, "duel_turn2", 1800, BATTLE_KEYS,
              {"P_ZONES": "0:818", "C_ZONES": "0:150", "P_HANDN": "3"},
              r"P 818,0,0,0,0 C 0,0,0,0,0 LP 7900 7500 hand 3 5 grave 1 1"),   # settled: LP count down first
        check("Slifer: 2 cards in hand = 2000, loses", E, "duel_turn2", 1800, BATTLE_KEYS,
              {"P_ZONES": "0:818", "C_ZONES": "0:150", "P_HANDN": "2"}, r"P 0,0,0,0,0 C 150,0,0,0,0 LP 7400 8000"),
        check("Slifer: an 1800 ATK summon is destroyed", E, "duel_main1", 1200, FISH_KEYS,
              {"C_ZONES": "0:818", "P_HAND": six("1")}, r"P 0,0,0,0,0 C 818,0,0,0,0 LP 8000 8000 hand 5 5 grave 1 0"),
        check("Slifer: a 2500 ATK summon loses 2000", E, "duel_main1", 1400, SKULL_KEYS,
              {"C_ZONES": "0:818", "P_HAND": six("675"), "P_ZONES": "1:1"},
              r"P 0,675,0,0,0 .*P\{1\[12/10=818 15/0=65535\]\}"),
        check("Ra: pay LP on Normal Summon, ATK 7900", E, "duel_main1", 2800, ra_yes,
              {"P_HAND": six("819"), "P_ZONES": fodder}, r"P 819,0,0,0,0 .*LP 100 8000 .*P\{0\[14/0=7900 15/0=65535\]\}",
              ckeys=summon),
        check("Ra: pay 1000 LP, destroy a monster", E, "duel_main1", 1800, RA_DESTROY_KEYS,
              {"P_ZONES": "0:819", "C_ZONES": "0:82"}, r"P 819,0,0,0,0 C 0,0,0,0,0 LP 7000 8000"),
        check("CPU: Ra pays LP, attacks with 7900", E, "duel_main1", 4000, END_TURN_KEYS,
              {"C_HAND": "819,1,1,1,1", "C_ZONES": fodder, "P_ZONES": "0:82"},
              r"C\{0\[14/0=7900 15/0=65535\]\}[\s\S]*LP 3100 100 "),
        check("CPU: Ra destroys the player's monster", E, "duel_main1", 4000, END_TURN_KEYS,
              {"C_HAND": "1,1,1,1,1", "C_ZONES": "0:819", "P_ZONES": "0:82"}, r"P 0,0,0,0,0 C 819,1,0,0,0 LP 2200 7000"),
        check("CPU: no Slifer with a 3-card hand", E, "duel_main1", 4000, END_TURN_KEYS,
              {"C_HAND": "818,1", "C_HANDN": "2", "C_ZONES": fodder, "P_ZONES": "0:82"}, r"C 818", must=False),
        check("trait: no Trap Hole on a God's Normal Summon", E, "duel_main1", 2600, no_set(summon),
              {"C_ZONES": "5:737:sa", "P_HAND": six("818"), "P_ZONES": fodder}, r"grave \d+ 1 ", must=False,
              ckeys=summon),
        check("trait: Obelisk can't be targeted", E, "duel_main1", 1800, TTTD_KEYS,
              {"C_ZONES": "0:817", "P_HAND": six("742")}, r"C 0,0,0,0,0", must=False),
        check("trait: a God can't be Set", E, "duel_main1", 2000, no_set(summon),
              {"P_HAND": six("818"), "P_ZONES": fodder}, r"P 818s", must=False),
        check("card text in the ROM", None, None, 0, None, {}, CARD_TEXT % tributes),
        check("regression: Trap Hole still hits Summoned Skull", E, "duel_main1", 2000, SKULL_KEYS,
              {"C_ZONES": "5:737:sa", "P_HAND": six("675"), "P_ZONES": "1:1"},
              r"P 0,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 5 5 grave 2 1", control="passes"),
        check("regression: Tribute to The Doomed still works", E, "duel_main1", 1800, TTTD_KEYS,
              {"C_ZONES": "0:82", "P_HAND": six("742")}, r"P 0,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 4 5 grave 2 1",
              control="passes"),
    ]


def base_on_fx(suite):
    """The base suite on an effects build, uncompared, with the God summons' keys for a menu without Set."""
    out = []
    for c in suite:
        if c["script"] == "player_summon.lua" and c["env"].get("GOD", "818") in GODS:
            c = dict(c, keys=no_set(c["keys"]))
        out.append(dict(c, name="base: " + c["name"], control=None))
    return out


def emu(decomp, *args, env=None):
    e = dict(os.environ, EDS_NATIVE="1", **(env or {}))
    r = subprocess.run([sys.executable, "tools/emu.py", *args], cwd=decomp, env=e, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def run_all(decomp, rom, tag, checks, control=False):
    states = f"build/emu/states-oracle-{tag}"
    code, out = emu(decomp, "states", "build", "--all", "--rom", str(rom), "--dir", states)
    if code:
        sys.exit(f"states build failed for {rom}:\n{out}")
    results = []
    for i, c in enumerate(checks):
        if control and c["control"] is None:
            results.append((None, ""))
            continue
        if c["script"] is None:
            found = c["regex"] in Path(rom).read_bytes()
            results.append((found == c["must"], f"ROM {'contains' if found else 'lacks'} {c['regex']!r}"))
            continue
        keys = c["ckeys"] if control and c["ckeys"] else c["keys"]
        code, out = emu(decomp, "lua", str(HERE / c["script"]), "--rom", str(rom), "--state",
                        f"{states}/{c['state']}.ss", "--frames", str(c["frames"]), "--keys", keys,
                        "--out", f"oracle-{tag}-{i}", env=c["env"])
        log = "\n".join(l for l in out.splitlines() if l.startswith("[lua]"))
        results.append((bool(re.search(c["regex"], log)) == c["must"], log))
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("decomp", type=Path)
    ap.add_argument("rom", type=Path)
    ap.add_argument("--tributes", type=int, choices=(2, 3), default=2)
    ap.add_argument("--effects", action="store_true", help="the ROM is an effects build (build.sh --effects)")
    ap.add_argument("--control", type=Path,
                    help="the original ROM (2-Tribute suite), the 2-Tribute build (3-Tribute suite), or the "
                         "build without effects (effects suites)")
    ap.add_argument("-v", action="store_true", help="print the logs")
    args = ap.parse_args()
    checks = SUITE3 if args.tributes == 3 else SUITE2
    tag = f"mod{args.tributes}"
    if args.effects:
        checks = fx_suite(args.tributes) + base_on_fx(checks)
        tag += "fx"
    mod = run_all(args.decomp.resolve(), args.rom.resolve(), tag, checks)
    ctl = run_all(args.decomp.resolve(), args.control.resolve(), f"control-{tag}", checks, control=True) \
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
