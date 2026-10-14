#!/usr/bin/env python3
"""Run every in-game check of the Egyptian Gods mod in eds-decomp's headless mGBA harness.

    run_oracles.py <eds-decomp checkout> <gods.gba>    [--control original.gba]        # 2-Tribute build
    run_oracles.py <eds-decomp checkout> <gods-3t.gba> --tributes 3 [--control gods.gba]
    run_oracles.py <eds-decomp checkout> <gods-fx.gba> --effects [--control gods.gba]   # effects builds
    run_oracles.py <eds-decomp checkout> <gods-3t-fx.gba> --tributes 3 --effects --pack-viewer --god-rules \
                   [--control gods-3t.gba]

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
  - with --pack-viewer, the same control for the pack viewer suite (pack_viewer.lua): every viewer check
    must fail there, and the pick must give the same pack as there. The expected odds come from the
    checkout's own booster_packs.json, through scripts/gen_pack_odds.py;
  - with --god-rules, the same control for the Gods' summon rules and Deck Edit (effects.lua, deck_edit.lua):
    every rule check must fail there, and the regressions must pass.
A check with a control key list (ckeys) plays those keys on the control instead, where the menus differ.
That proves each check can fail. Needs the harness set up natively (EDS_NATIVE=1, MGBA_PREFIX).
"""
import argparse
import json
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


def check(name, script, state, frames, keys, env, regex, must=True, control="fails", ckeys=None, verify=None):
    """must: the regex must (True) or must not (False) match. control: 'fails' / 'passes' / None.
    script None: regex is bytes the ROM file itself must contain. regex may be a function of the checkout
    (expected values from its data). verify(log): an extra test of the log, ANDed with the regex."""
    return dict(name=name, script=script, state=state, frames=frames, keys=keys, env=env, regex=regex,
                must=must, control=control, ckeys=ckeys, verify=verify)


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


PV = "pack_viewer.lua"
# duel_turn2 -> Battle Phase, Blue-Eyes attacks the CPU at 1 LP, A through the win: the pick screen by f2000
WIN_KEYS = "20 B; 80 A; 380 A; 430 RIGHT; 470 A; 560 A; 650 A; 750 A; 1300-1960/60 A"
PIN = {"PIN_RNG": "1234ABCD"}
VANILLA_PACK = r"generated pack=2 cards=79,177,339,154,117"   # Vol.2 from RNG state 0x1234ABCD


def odds_text(units):
    """FormatOdds (src/pack_viewer.c) of a chance in 0.01% steps."""
    if units == 0:
        return "   0%"
    if units < 100:
        return f"0.{units // 10}{units % 10}%"
    t = (units + 5) // 10
    if t >= 1000:
        return " 100%"
    return f"{t // 100 if t >= 100 else ' '}{t // 10 % 10}.{t % 10}%"


def pack_table(decomp, pack_id):
    """The viewer's list for a pack, from the checkout's booster_packs.json: [(card number, odds per mode)],
    and the rare chance per mode, in 0.01% steps."""
    sys.path.insert(0, str(HERE.parent / "scripts"))
    import gen_pack_odds as g
    with open(decomp / "assets/tables/rodata2/booster_packs.json") as f:
        pack = next(p for p in g.listed_packs(json.load(f)) if p["id"] == pack_id)
    odds, rare = g.pack_odds(pack)
    slot = g.rarest_slot(pack)
    order = sorted(odds, key=lambda c: slot[c])
    return [(c, [g.units(x) for x in odds[c]]) for c in order], [g.units(x) for x in rare]


def header_re(decomp, pack_id, mode):
    cards, rare = pack_table(decomp, pack_id)
    line4 = ["% = chance it's in your pack", "Same pack again: rares x2/3", "Lucky pack: a rare for sure"][mode]
    first = cards[0]
    return ("header '" + r"\d+" + re.escape(f"/{len(cards)} owned  rare card {odds_text(rare[mode]).lstrip()}' '{line4}'")
            + r"[\s\S]*" + re.escape(f"cursor e=1 n={first[0]} odds='{odds_text(first[1][mode])}'"))


def list_re(decomp, pack_id, mode):
    cards, _ = pack_table(decomp, pack_id)
    return r"[\s\S]*".join(re.escape(f"cursor e={e} n={c} odds='{odds_text(o[mode])}' new=") + "[01]"
                            for e, (c, o) in enumerate(cards, 1))


def owned_matches_rows(log):
    """The header's owned count equals the rows without NEW, over a scroll through the whole list."""
    header = re.search(r"header '(\d+)/(\d+) owned", log)
    rows = dict(re.findall(r"cursor e=(\d+) n=\d+ odds='[^']*' new=([01])", log))   # the last line per row wins
    return bool(header) and len(rows) == int(header.group(2)) and \
        sum(v == "0" for v in rows.values()) == int(header.group(1))


def pv_suite():
    sel = WIN_KEYS + "; 2100 SELECT"
    return [
        check("viewer: the band names the centre pack", PV, "duel_turn2", 2100, WIN_KEYS, {},
              r"pick centre=1 band=1"),
        check("viewer: SELECT opens the centre pack", PV, "duel_turn2", 2200, sel, {},
              r"view pack=1 entries=41 mode=0 top=0 row=1"),
        check("viewer: header and odds, normal roll", PV, "duel_turn2", 2200, sel, {},
              lambda d: header_re(d, 1, 0)),
        check("viewer: every card in order, with its odds", PV, "duel_turn2", 2800, sel + "; 2200-2700/12 DOWN",
              {}, lambda d: list_re(d, 1, 0)),
        check("viewer: owned count = the rows without NEW", PV, "duel_turn2", 2800, sel + "; 2200-2700/12 DOWN",
              {"OWN": "34,335"}, r"header '\d+/40 owned", verify=owned_matches_rows),
        check("viewer: same pack again, rares 2/3", PV, "duel_turn2", 2200, sel, {"LAST_PACK": "1"},
              lambda d: header_re(d, 1, 1)),
        check("viewer: pity roll, a rare for sure", PV, "duel_turn2", 2200, sel, {"PITY": "6"},
              lambda d: header_re(d, 1, 2)),
        check("viewer: same pack, pity needs 11", PV, "duel_turn2", 2200, sel, {"LAST_PACK": "1", "PITY": "6"},
              lambda d: header_re(d, 1, 1)),
        check("viewer: same pack, pity at 11", PV, "duel_turn2", 2200, sel, {"LAST_PACK": "1", "PITY": "11"},
              lambda d: header_re(d, 1, 2)),
        check("viewer: NEW on a card you don't own", PV, "duel_turn2", 2200, sel, {},
              r"cursor e=1 n=34 odds='[ .0-9]{4}%' new=1"),
        check("viewer: x1 instead of NEW once you own it", PV, "duel_turn2", 2200, sel, {"OWN": "34"},
              r"cursor e=1 n=34 odds='[ .0-9]{4}%' new=0 mark='x1'"),
        check("viewer: a God's row shows its stats", PV, "duel_turn2", 2200, sel, {"PICK_PACK": "505"},
              r"cursor e=1 n=1910 [^\n]*stats='4000/4000'"),
        check("viewer: Card Detail says where else to find it", PV, "duel_turn2", 2500,
              sel + "; 2200 DOWN; 2220 DOWN; 2300 A", {},
              r"detail n=335\n[\s\S]*detail id=147 found=[1-9]|detail id=147 found=[1-9]\d*\n[^\n]*detail n=335"),
        check("viewer: Card Detail, RIGHT, back to the list", PV, "duel_turn2", 2600,
              sel + "; 2200 A; 2350 RIGHT; 2450 B", {},
              r"detail n=34[\s\S]*detail n=37[\s\S]*view pack=1 entries=41 mode=0 top=0 row=2"),
        check("viewer: back with the same pack, which A picks", PV, "duel_turn2", 2600,
              WIN_KEYS + "; 2100 RIGHT; 2160 SELECT; 2300 DOWN; 2400 B; 2500 A", PIN, VANILLA_PACK,
              control="passes"),
        check("regression: a pick without SELECT", PV, "duel_turn2", 2400, WIN_KEYS + "; 2100 RIGHT; 2200 A",
              PIN, VANILLA_PACK, control="passes"),
    ]


DE = "deck_edit.lua"
SIX = lambda card: ",".join([card] * 6)
REBORN = "482"      # Monster Reborn's card ID
# duel_main1, a hand of Monster Reborn -> Activate, OK, the list's "designate" icon, the first card, the chain
# resolves, Attack Position
REBORN_KEYS = ("15 A; 45 RIGHT; 55 RIGHT; 70 A; 250 A; 400 A; 480 LEFT; 500 A; 650 A; 800 A; 1100 A; 1250 A")
REBORN_END_KEYS = REBORN_KEYS + "; 1400 B; 1440 A"       # then end the turn
# main_menu -> Deck Edit (the Trunk), the command bar, three RIGHTs to List Filter
FILTER_KEYS = "0 DOWN; 15 DOWN; 30 A; 200 A; 260 RIGHT; 300 RIGHT; 340 RIGHT; 380 A"
TRUNK = {"TRUNK": "1,82,817,818,819,482,150"}   # 7 Colored Fish, Blue-Eyes, the Gods, Monster Reborn, Dark Magician
RULES_TEXT = (b"Cannot be Special Summoned.", b"If this card is Special Summoned, it is sent to the Graveyard "
              b"during the End Phase.")


def rules_suite():
    gone = lambda god: (rf"P {god},0,0,0,0 [^\n]*\n[\s\S]*"
                        r"P 0,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 5 5 grave 2 0")
    return [
        check("rules: Monster Reborn still revives Blue-Eyes", E, "duel_main1", 1500, REBORN_KEYS,
              {"P_HAND": SIX(REBORN), "P_GRAVE": "82"}, r"P 82,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 5 5 grave 1 0",
              control="passes"),
        check("rules: Monster Reborn can't revive Ra", E, "duel_main1", 1500, REBORN_KEYS,
              {"P_HAND": SIX(REBORN), "P_GRAVE": "819"}, r"P 819", must=False),
        check("rules: the CPU's Monster Reborn skips Ra", E, "duel_main1", 2500, END_TURN_KEYS,
              {"C_HAND": "482,482,482,482,482", "C_GRAVE": "819,82"}, r"C 82,0,0,0,0"),
        check("rules: a revived Obelisk leaves in the End Phase", E, "duel_main1", 2000, REBORN_END_KEYS,
              {"P_HAND": SIX(REBORN), "P_GRAVE": "817"}, gone(817)),
        check("rules: a revived Slifer leaves in the End Phase", E, "duel_main1", 2000, REBORN_END_KEYS,
              {"P_HAND": SIX(REBORN), "P_GRAVE": "818"}, gone(818)),
        check("rules: a revived Blue-Eyes stays", E, "duel_main1", 2000, REBORN_END_KEYS,
              {"P_HAND": SIX(REBORN), "P_GRAVE": "82"}, r"P 82,0,0,0,0 C [^\n]*hand 5 6", control="passes"),
        check("rules: a God summoned normally stays", E, "duel_main1", 1500, END_TURN_KEYS,
              {"P_ZONES": "0:817", "C_HAND": "1,1,1,1,1"}, r"P 817,0,0,0,0 C [^\n]*hand \d+ 6", control="passes"),
        check("rules: the card text says so", None, None, 0, None, {}, RULES_TEXT[0]),
        check("rules: the card text says so (End Phase)", None, None, 0, None, {}, RULES_TEXT[1]),
        check("Deck Edit: ATK sort puts the Gods first", DE, "main_menu", 700, FILTER_KEYS + "; 480 A; 520 DOWN; 560 A",
              TRUNK, r"trunk n=7 ids=817,818,819,82,150,1,482"),
        check("Deck Edit: Effect Monsters lists Obelisk", DE, "main_menu", 700, FILTER_KEYS + "; 440 DOWN; 460 DOWN; "
              "480 A; 560 A", TRUNK, r"trunk n=3 ids=817,818,819"),
        check("Card Detail: Found in, from Deck Edit", DE, "main_menu", 500, "0 DOWN; 15 DOWN; 30 A; 200 A; 240 A",
              {"TRUNK": "1,82"}, r"detail id=1 found=[1-9]"),
        check("Card Detail: no Found in inside a duel", E, "duel_main1", 400, "15 A; 60 A", {"P_HAND": SIX("82")},
              r"detail id=82 found=0", control="passes"),
    ]


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
        regex = c["regex"](decomp) if callable(c["regex"]) else c["regex"]
        found = bool(re.search(regex, log)) and (c["verify"] is None or c["verify"](log))
        results.append((found == c["must"], log))
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
    ap.add_argument("--pack-viewer", action="store_true", help="the ROM has the pack viewer (gods-3t-fx)")
    ap.add_argument("--god-rules", action="store_true", help="the ROM has the Gods' summon rules (gods-3t-fx)")
    ap.add_argument("-v", action="store_true", help="print the logs")
    args = ap.parse_args()
    checks = SUITE3 if args.tributes == 3 else SUITE2
    tag = f"mod{args.tributes}"
    if args.effects:
        checks = fx_suite(args.tributes) + base_on_fx(checks)
        tag += "fx"
    if args.pack_viewer:
        checks = checks + pv_suite()
        tag += "pv"
    if args.god_rules:
        checks = checks + rules_suite()
        tag += "gr"
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
