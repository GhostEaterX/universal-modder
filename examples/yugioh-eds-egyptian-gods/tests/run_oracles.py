#!/usr/bin/env python3
"""Run every in-game check of the Egyptian Gods mod in eds-decomp's headless mGBA harness.

    run_oracles.py <eds-decomp checkout> <gods.gba>    [--control original.gba]        # 2-Tribute build
    run_oracles.py <eds-decomp checkout> <gods-3t.gba> --tributes 3 [--control gods.gba]
    run_oracles.py <eds-decomp checkout> <gods-fx.gba> --effects [--control gods.gba]   # effects builds
    run_oracles.py <eds-decomp checkout> <gods-3t-fx.gba> --tributes 3 --effects --pack-viewer --god-rules \
                   --second-decks --deck-tuning --extra-deck-rituals --boss-effects --extra-deck-effects \
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
    every rule check must fail there, and the regressions must pass;
  - with --second-decks, the same control for the Tier 1 duelists' second decks (npc_deck.lua): a duelist
    beaten 10 times must play the second deck, which the control never loads, and the other decks must be
    the same as there. The expected decks come from the checkout's own deck_lists.json. Their 10th-win lines
    (dialogue.lua) must be shown to their new last page, and the other result lines must be as there;
  - with --deck-tuning, the same control for the CPU deck tuning: each tuned deck must load card for card as
    in the checkout's deck_lists.json (the control has the old decks), and the CPU must play the cards the
    tuning brings in that it didn't hold before (recruiters, Elegant Egotist, Toon Mermaid, Fissure,
    Polymerization), which it does on both;
  - with --extra-deck-rituals, the same control for the Ritual monsters in the Extra Deck: the CPU's rituals
    load into its Fusion Deck (the decks of the two suites above expect that too), Deck Edit files them there
    and refuses them the Side Deck, a save from before moves them there at boot (save_migration.lua), the
    Ritual Magic cards summon them from there for both players, a bounced one goes back there (Black Luster
    Soldier, which with --extra-deck-effects also pierces the Hane-Hane that bounces it), Senju searches
    a Ritual Magic card and Cyber-Stein keeps to Fusion monsters; all of that fails on the control, and the
    regressions (a ritual from the hand, a Normal monster to the Side Deck, a save without rituals) pass;
  - with --boss-effects, the same control for the bosses' effects: Summoned Skull's piercing damage, Millennium
    Golem surviving battle, Dark Magician's once-per-turn Spell/Trap destruction and Red-Eyes B. Dragon's coin
    (heads and tails, with a pinned RNG state), each for the player and the CPU, Red-Eyes Black Metal
    Dragon's quarter bonus, and the CPU's Metalmorph onto Red-Eyes and its upgrade; all of that fails on the
    control, and the regressions (Raigeki on Golem, the player's Metalmorph upgrade, B. Skull Dragon's fusion,
    Black Metal Dragon attacked, a set Metalmorph without Black Metal Dragon in the deck) pass. It also makes the rules
    suite's Effect Monsters filter expect the Trunk's Dark Magician, an Effect monster now.
  - with --extra-deck-effects, the same control for the Fusion and Ritual monsters' effects: piercing (B. Skull
    Dragon, Black Luster Soldier, Javelin Beetle), surviving battle (Labyrinth Tank, Crab Turtle, Fortress
    Whale), the ATK rules (Twin-Headed Thunder Dragon in its Battle Phase, +100 per Graveyard monster for Skull
    Knight, Zera The Mant, Dokurorider and Chakra, Kaiser Dragon against DARK), Garma Sword against LIGHT,
    Magician of Black Chaos' destroy, Thousand Dragon's coin (both calls, both arts, until the end of the turn),
    Bickuribox's trigger, Skull Guardian's answer (also once Ritual Summoned) and Gaia's and Super War-Lion's
    destroy and its limits, each for the CPU where it plays it; all of that fails on the control, and the
    regressions (the cards they borrow from, the cases where the effect must not change the result) pass.
A check with a control key list (ckeys) plays those keys on the control instead, where the menus differ.
That proves each check can fail. Needs the harness set up natively (EDS_NATIVE=1, MGBA_PREFIX).
"""
import argparse
import csv
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
DIALOGUE_KEYS = WIN_KEYS.replace("1300-1960/60 A", "1300-2640/60 A")   # the win, then A through the texts
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


def rules_suite(bosses=False):
    """bosses: the ROM has the bosses' effects, so the Trunk's Dark Magician is an Effect monster too."""
    effect_monsters = "n=4 ids=150,817,818,819" if bosses else "n=3 ids=817,818,819"
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
              "480 A; 560 A", TRUNK, rf"trunk {effect_monsters}"),
        check("Card Detail: Found in, from Deck Edit", DE, "main_menu", 500, "0 DOWN; 15 DOWN; 30 A; 200 A; 240 A",
              {"TRUNK": "1,82"}, r"detail id=1 found=[1-9]"),
        check("Card Detail: no Found in inside a duel", E, "duel_main1", 400, "15 A; 60 A", {"P_HAND": SIX("82")},
              r"detail id=82 found=0", control="passes"),
    ]


def cpu_deck_re(which, duelist, rituals=False):
    """The CPU's deck as npc_deck.lua logs it, from the checkout's deck_lists.json: deck `duelist` of
    "opponent_decks" (the first decks) or "alternate_decks" (the second decks), Fusion monsters (and with
    rituals, the Extra Deck rituals build, Ritual monsters) in the Fusion Deck. No Tier 1 deck goes over the ban
    list, so RemoveOverLimitDeckCards takes nothing out."""
    def regex(decomp):
        assets = decomp / "assets"
        with open(assets / "tables/deck_lists.json") as f:
            cards = json.load(f)[which][duelist]["cards"]
        with open(assets / "cards/number_to_id.json") as f:
            number_to_id = json.load(f)
        with open(assets / "cards/stats.csv") as f:
            stats = {int(r["id"]): r for r in csv.DictReader(f)}
        deck, fusion = [], []
        for number, _ in cards:
            card = number_to_id[number]
            s = stats[card]
            extra = int(s["type"]) <= 20 and s["kind"] in (("2", "3") if rituals else ("2",))
            (fusion if extra else deck).append(card)
        line = lambda name, ids: re.escape(f"{name}: {' '.join(map(str, sorted(ids)))}")
        return line("sorted ids", deck) + r"\n\[lua\] " + line("fusion ids", fusion) + r"(\n|$)"
    return regex


TIER1 = ((1, "Yugi"), (2, "Tea"), (3, "Joey"), (4, "Tristan"), (5, "Bakura"))
# gOpponentResultTexts[duelist].win10th: the line after the player's 10th win
WIN10TH = {1: 1017, 2: 2017, 3: 3017, 4: 4017, 5: 5016, 6: 6016}


def dialogue_re(event, wins):
    """dialogue.lua's log once the record `event` has been printed to the end of its text in the checkout's
    dialogue.json (so every page was shown), and the record after the duel."""
    def regex(decomp):
        with open(decomp / "assets/text/dialogue.json") as f:
            text = next(r["text"] for r in json.load(f) if r["event"] == event)
        return rf"dialogue event={event} end={len(text.encode('ascii'))}\n[\s\S]*record wins={wins}\b"
    return regex


def second_decks_suite(rituals=False):
    deck = lambda which, opp, wins: dict(script="npc_deck.lua", state="main_menu", frames=1500, keys=NPC_KEYS,
                                         env={"OPP": str(opp), "WINS": str(wins)},
                                         regex=cpu_deck_re(which, opp, rituals))
    return [check(f"second decks: {name} at 10 wins plays it", **deck("alternate_decks", opp, 10))
            for opp, name in TIER1] + [
        check("second decks: Tea at 9 wins keeps her deck", control="passes", **deck("opponent_decks", 2, 9)),
        # Rex's and Kaiba's decks are tuned too (--deck-tuning), so the control loads other cards: not compared.
        check("second decks: Rex at 10 wins keeps his deck", control=None, **deck("opponent_decks", 6, 10)),
        check("second decks: Kaiba at 10 wins keeps his deck", control=None, **deck("opponent_decks", 16, 10)),
    ] + [check(f"second decks: {name}'s 10th-win line, to its end", "dialogue.lua", "duel_turn2", 2700,
               DIALOGUE_KEYS, {"OPP": str(opp), "WINS": "9"}, dialogue_re(WIN10TH[opp], 10))
         for opp, name in TIER1] + [
        check("second decks: Tea's 11th win, her usual line", "dialogue.lua", "duel_turn2", 2700, DIALOGUE_KEYS,
              {"OPP": "2", "WINS": "10"}, dialogue_re(2014, 11), control="passes"),
        check("second decks: Rex's 10th-win line as before", "dialogue.lua", "duel_turn2", 2700, DIALOGUE_KEYS,
              {"OPP": "6", "WINS": "9"}, dialogue_re(WIN10TH[6], 10), control="passes"),
    ]


DUELISTS = {1: "Yugi", 2: "Tea", 3: "Joey", 4: "Tristan", 5: "Bakura", 6: "Rex", 7: "Espa Roba", 8: "Weevil",
            9: "Mako", 10: "Mai", 11: "Rare Hunter", 12: "Arkana", 13: "Strings", 14: "Umbra & Lumis", 15: "Marik",
            16: "Kaiba", 17: "Ishizu", 18: "Shadi", 19: "Yami Bakura", 20: "Yami Yugi", 21: "Duel Computer",
            22: "Simon", 23: "Pegasus", 24: "Grandpa"}
# duel_turn2: Blue-Eyes attacks the CPU's zone 0, then A through the chain of its trigger
RECRUIT_KEYS = BATTLE_KEYS + "; 1300-1600/60 A"


def deck_tuning_suite(rituals=False):
    sys.path.insert(0, str(HERE.parent / "scripts"))
    from apply_gods import DECK_TUNING_3T, O
    tuned = sorted(i for table, i in DECK_TUNING_3T if table == O)
    recruit = lambda name, card, target: check(
        f"deck tuning: the CPU's {name} recruits", E, "duel_turn2", 1700, RECRUIT_KEYS,
        {"P_ZONES": "0:82", "C_ZONES": f"0:{card}", "C_DECK": str(target)}, rf"C {target},0,0,0,0", control="passes")
    return [check(f"deck tuning: {DUELISTS[i]}'s deck, card for card", "npc_deck.lua", "main_menu", 1500, NPC_KEYS,
                  {"OPP": str(i)}, cpu_deck_re("opponent_decks", i, rituals)) for i in tuned] + [
        recruit("Giant Rat", 272, 418),             # Little D
        recruit("Mother Grizzly", 490, 545),        # Penguin Knight
        recruit("Flying Kamakiri #1", 240, 316),    # Harpie Lady
        recruit("Mystic Tomato", 505, 38),          # Armored Zombie
        check("deck tuning: Elegant Egotist brings Harpie Lady Sisters", E, "duel_main1", 4000, END_TURN_KEYS,
              {"C_ZONES": "0:316", "C_HAND": "199,1,1,1,1", "C_DECK": "317", "P_HAND": "1,1,1,1,1"}, r"C 316,317,",
              control="passes"),
        check("deck tuning: Toon World, then Toon Mermaid", E, "duel_main1", 4000, END_TURN_KEYS,
              {"C_HAND": "733,731,1,1,1", "P_HAND": "1,1,1,1,1"}, r"C 731,[^\n]*LP \d+ 7000", control="passes"),
        check("deck tuning: the CPU's Fissure destroys Blue-Eyes", E, "duel_main1", 4000, END_TURN_KEYS,
              {"P_ZONES": "0:82", "C_HAND": "230,1,1,1,1", "P_HAND": "1,1,1,1,1"},
              r"P 0,0,0,0,0 C [^\n]*grave 1 1", control="passes"),
        # Kaiba's Polymerization: three Blue-Eyes in hand, Blue-Eyes Ultimate Dragon in the Fusion Deck
        check("deck tuning: Polymerization brings Blue-Eyes Ultimate Dragon", E, "duel_main1", 4000, END_TURN_KEYS,
              {"C_HAND": "552,82,82,82,82", "C_FUSION": "81", "P_HAND": "1,1,1,1,1"},
              r"C 81,0,0,0,0 [^\n]*grave 0 4 links P\{\} C\{\} fusion P\{\} C\{\}", control="passes"),
    ]


# duel_main1, a hand of Black Illusion Ritual -> Activate, OK, the chain resolves, Tribute zone 0's monster
# (the cursor starts there), Attack Position
RITUAL_KEYS = "15 A; 45 RIGHT; 55 RIGHT; 70 A; 250 A; 400 A; 750 A; 950 A"
SENJU_KEYS = FISH_KEYS + "; 950 A; 1100 A; 1200 LEFT; 1220 A; 1370 A"    # Yes, OK, the list's designate icon, card 1
# duel_main1 -> cursor up to zone 0, its menu, Activate; through the chain and Cyber-Stein's prompt to its list
CYBER_STEIN_KEYS = "20 UP; 40 UP; 70 A; 120 RIGHT; 180 RIGHT; 240 A; 450 A; 600 A; 750 A; 900 A"
CYBER_STEIN_PICK_KEYS = CYBER_STEIN_KEYS + "; 1000 LEFT; 1020 A; 1170 A"   # the designate icon, the first card
# main_menu -> Deck Edit (the Trunk's first card), the command bar: To Main Deck / To Side Deck
TO_DECK_KEYS = "0 DOWN; 15 DOWN; 30 A; 200 A; 260 RIGHT; 300 A"
TO_SIDE_KEYS = "0 DOWN; 15 DOWN; 30 A; 200 A; 260 RIGHT; 300 RIGHT; 340 A"
# then R to the Deck list, down to the card (5th by name in the main_menu save), To Trunk
BACK_TO_TRUNK_KEYS = TO_DECK_KEYS + "; 450 R; 550 DOWN; 580 DOWN; 610 DOWN; 640 DOWN; 700 RIGHT; 750 A"
HANE_KEYS = BATTLE_KEYS + "; 1300-1900/60 A"    # duel_turn2: attack the CPU's zone 0, then A through the chain
BLS, MOBC, RELINQUISHED, BLACK_LUSTER_RITUAL, BLACK_ILLUSION_RITUAL = "71", "433", "582", "70", "69"
FULL_FUSION_DECK = "10,10,10,14,14,14,28,28,28,42,42,42,46,46,46,63,63,63,89,89"   # 20 Fusion monsters


def extra_deck_rituals_suite(effects=False):
    sys.path.insert(0, str(HERE.parent / "scripts"))
    from apply_gods import SENJU_TEXT_3T
    fusion_deck = lambda name, opp, ids: check(
        f"Extra Deck: {name}'s rituals load into his Fusion Deck", "npc_deck.lua", "main_menu", 1500, NPC_KEYS,
        {"OPP": str(opp)}, rf"fusion ids: {ids}(\n|$)")
    return [
        fusion_deck("Bakura", 5, "176"),                # Dokurorider
        fusion_deck("Mako", 9, "245"),                  # Fortress Whale
        fusion_deck("Pegasus", 23, "582 582"),          # two Relinquished
        check("Extra Deck: Deck Edit files a ritual in the Fusion Deck", DE, "main_menu", 700, TO_DECK_KEYS,
              {"TRUNK": BLS}, r"saved deck=40 side=0 fusion=1 trunk=0"),
        check("Extra Deck: and takes it back out to the Trunk", DE, "main_menu", 1100, BACK_TO_TRUNK_KEYS,
              {"TRUNK": BLS}, r"fusion=1 trunk=0\n[\s\S]*saved deck=40 side=0 fusion=0 trunk=1"),
        check("Extra Deck: no ritual in the Side Deck", DE, "main_menu", 700, TO_SIDE_KEYS, {"TRUNK": BLS},
              r"side=1", must=False),
        check("Extra Deck: a Normal monster still goes to the Side Deck", DE, "main_menu", 700, TO_SIDE_KEYS,
              {"TRUNK": "1"}, r"saved deck=40 side=1 fusion=0", control="passes"),
        check("Extra Deck: a God still goes to the Main Deck", DE, "main_menu", 700, TO_DECK_KEYS, {"TRUNK": "817"},
              r"saved deck=41 side=0 fusion=0 trunk=0", control="passes"),
        check("Extra Deck: an old save's rituals move to its Fusion Deck", "save_migration.lua", "main_menu", 400,
              "", {"DECK_ADD": ",".join((BLS, MOBC, RELINQUISHED))},
              r"save deck=(\d+,){39}\d+ fusion=71,433,582 trunk=0 checksum=ok\n"
              r"\[lua\] copies 71=0/1/0 433=0/1/0 582=0/1/0$"),
        check("Extra Deck: ... to the Trunk when its Fusion Deck is full", "save_migration.lua", "main_menu", 400,
              "", {"DECK_ADD": BLS, "FUSION_ADD": FULL_FUSION_DECK},
              rf"save deck=(\d+,){{39}}\d+ fusion={FULL_FUSION_DECK} trunk=1 checksum=ok\n"
              r"\[lua\] copies 71=0/0/1$"),
        check("Extra Deck: a save without rituals is left alone", "save_migration.lua", "main_menu", 400, "",
              {"DECK_ADD": "1"}, r"save deck=(\d+,){40}1 fusion= trunk=0 checksum=ok\n\[lua\] copies 1=1/0/0$",
              control="passes"),
        check("Extra Deck: Ritual Summon from the Fusion Deck", E, "duel_main1", 1200, RITUAL_KEYS,
              {"P_HAND": SIX(BLACK_ILLUSION_RITUAL), "P_ZONES": "0:1", "P_FUSION": RELINQUISHED},
              r"P 582,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 5 5 grave 2 0 links P\{\} C\{\} fusion P\{\} C\{\}"),
        check("Extra Deck: a ritual in the hand still works", E, "duel_main1", 1200, RITUAL_KEYS,
              {"P_HAND": "582," + ",".join([BLACK_ILLUSION_RITUAL] * 5), "P_ZONES": "0:1"},
              r"P 582,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 4 5 grave 2 0", control="passes"),
        # The CPU plays its spells only on a turn it doesn't Normal Summon to attack first: no Level 4 or lower.
        check("Extra Deck: the CPU's Ritual Summon from its Fusion Deck", E, "duel_main1", 3000, END_TURN_KEYS,
              {"C_HAND": "69,82,82,82,82", "C_FUSION": RELINQUISHED, "P_HAND": SIX("1")},
              r"C 582,0,0,0,0 [^\n]*fusion P\{\} C\{\}"),
        # the CPU's set Hane-Hane; with the Extra Deck effects, Black Luster Soldier pierces it (3000 - 500 DEF)
        check("Extra Deck: a bounced ritual goes back to the Fusion Deck", E, "duel_turn2", 2200, HANE_KEYS,
              {"P_ZONES": "0:" + BLS, "C_ZONES": "0:312:s"},
              rf"P 0,0,0,0,0 C 0,0,0,0,0 LP 7900 {5500 if effects else 8000} hand 6 5 grave 1 \d links P\{{\}} "
              r"C\{\} fusion P\{71\}"),
        check("Extra Deck: Senju adds a Ritual Magic card", E, "duel_main1", 1700, SENJU_KEYS,
              {"P_HAND": SIX("621"), "P_DECK": BLACK_LUSTER_RITUAL}, r"P 621,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 6 5"),
        check("Extra Deck: Senju's card text", None, None, 0, None, {}, SENJU_TEXT_3T.encode("ascii")),
        check("Extra Deck: Cyber-Stein can't take a ritual", E, "duel_main1", 1800, CYBER_STEIN_KEYS,
              {"P_ZONES": "0:137", "P_FUSION": BLS, "P_HAND": SIX("1")}, r"LP 3000", must=False),
        check("Extra Deck: Cyber-Stein takes the Fusion monster", E, "duel_main1", 1800, CYBER_STEIN_PICK_KEYS,
              {"P_ZONES": "0:137", "P_FUSION": BLS + ",81", "P_HAND": SIX("1")}, r"P 137,81,0,0,0"),
    ]


# The bosses' effects. Zone 0's menu, Activate (the third command), A through the prompt; then the target:
ACTIVATE_KEYS = "20 UP; 40 UP; 70 A; 120 RIGHT; 180 RIGHT; 240 A; 450 A"
DARK_MAGICIAN_KEYS = ACTIVATE_KEYS + "; 600 A"              # the CPU's Spell/Trap card the cursor starts on
# after it resolves, back down to zone 0 (the cursor stays on the CPU's side), its menu, the same commands
DARK_MAGICIAN_TWICE_KEYS = DARK_MAGICIAN_KEYS + ("; 1250 DOWN; 1300 DOWN; 1350 LEFT; 1380 LEFT; 1410 LEFT; 1440 LEFT; "
                                                 "1500 A; 1550 RIGHT; 1600 RIGHT; 1650 A; 1850 A; 2000 A")
RED_EYES_KEYS = ACTIVATE_KEYS + "; 500 UP; 540 A"           # the CPU's zone 0
# the set Metalmorph in zone 5: Activate, on Red-Eyes; then Red-Eyes' Activate, Attack Position
METALMORPH_UPGRADE_KEYS = ("20 UP; 50 A; 80 RIGHT; 100 A; 350 A; 450 A; 1100 A; 1150 RIGHT; 1200 RIGHT; 1250 A; "
                           "1500 A")
QUIET_CPU = {"C_HAND": "82,82,82,82,82", "C_DECK": "82"}     # Blue-Eyes it can't summon: no Normal Summon
# end turn 1; turn 2 (a 5-card hand, so there is a draw): A on the deck through the draw and the Standby Phase, as
# eds-decomp's duel_turn2 recipe does, then end it
METALMORPH_TWO_TURNS_KEYS = END_TURN_KEYS + "; 2600-2800/20 A; 3000 B; 3040 A"
HEADS, TAILS = {"PIN_RNG": "1234ABCD"}, {"PIN_RNG": "00000002"}     # the player's coin from these RNG states
CPU_TAILS = {"PIN_RNG": "00000001"}                                 # the CPU's coin (its turn draws first)


def boss_effects_suite():
    sys.path.insert(0, str(HERE.parent / "scripts"))
    from apply_gods import BOSSES_3T
    texts = {text: name for name, _, text in BOSSES_3T.values()}
    set_cards = "5:737:s,6:476:s"                            # Trap Hole, Mirror Force
    return [
        check("bosses: Summoned Skull pierces", E, "duel_turn2", 1800, BATTLE_KEYS,
              {"P_ZONES": "0:675", "C_ZONES": "0:1:d"}, r"P 675,0,0,0,0 C 0,0,0,0,0 LP 7900 6300"),
        check("bosses: the CPU's Summoned Skull pierces", E, "duel_main1", 4000, END_TURN_KEYS,
              dict(QUIET_CPU, C_ZONES="0:675", P_ZONES="0:1:d"), r"P 0,0,0,0,0 C 675,0,0,0,0 LP 6300 8000"),
        check("bosses: Millennium Golem survives Blue-Eyes", E, "duel_turn2", 1800, BATTLE_KEYS,
              {"P_ZONES": "0:82", "C_ZONES": "0:471"}, r"P 82,0,0,0,0 C 471,0,0,0,0 LP 7900 7000"),
        check("bosses: ... and the CPU's Blue-Eyes", E, "duel_main1", 4000, END_TURN_KEYS,
              dict(QUIET_CPU, C_ZONES="0:82", P_ZONES="0:471"), r"P 471,0,0,0,0 C 82,0,0,0,0 LP 7000 8000"),
        check("bosses: Raigeki still destroys Golem", E, "duel_main1", 1500, RITUAL_KEYS,
              {"P_HAND": SIX("570"), "C_ZONES": "0:471"}, r"C 0,0,0,0,0 LP 8000 8000 hand 5 5 grave 1 1",
              control="passes"),
        check("bosses: Dark Magician destroys a set card", E, "duel_main1", 1600, DARK_MAGICIAN_KEYS,
              {"P_ZONES": "0:150:e", "C_ZONES": set_cards}, r"P 150,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 6 5 grave 0 1"),
        check("bosses: Dark Magician once per turn", E, "duel_main1", 2500, DARK_MAGICIAN_TWICE_KEYS,
              {"P_ZONES": "0:150:e", "C_ZONES": set_cards}, r"grave 0 1 [\s\S]*detail id=150",
              verify=lambda log: "grave 0 2" not in log),
        check("bosses: the CPU's Dark Magician, ready again", E, "duel_main1", 4000, END_TURN_KEYS,
              dict(QUIET_CPU, C_ZONES="0:150:u", P_ZONES="5:737:s"),
              r"P 0,0,0,0,0 C 150,0,0,0,0 LP 5500 8000 hand 6 6 grave 1 0"),
        check("bosses: Red-Eyes, heads destroys", E, "duel_main1", 2200, RED_EYES_KEYS,
              dict(HEADS, P_ZONES="0:579:e", C_ZONES="0:82"),
              r"coin heads\n.*P 579,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 6 5 grave 0 1"),
        check("bosses: Red-Eyes, tails doesn't", E, "duel_main1", 2200, RED_EYES_KEYS,
              dict(TAILS, P_ZONES="0:579:e", C_ZONES="0:82"), r"C 82,0,0,0,0 .*\n.*coin tails$"),
        check("bosses: the CPU's Red-Eyes, heads", E, "duel_main1", 4000, END_TURN_KEYS,
              dict(QUIET_CPU, **HEADS, C_ZONES="0:579:u", P_ZONES="0:82"),
              r"coin heads\n[\s\S]*P 0,0,0,0,0 C 579,0,0,0,0 LP 5600 8000"),
        check("bosses: the CPU's Red-Eyes, tails", E, "duel_main1", 4000, END_TURN_KEYS,
              dict(QUIET_CPU, **CPU_TAILS, C_ZONES="0:579:u", P_ZONES="0:82"), r"P 82,0,0,0,0 C 579,.*\n.*coin tails$"),
        check("bosses: Metalmorph still upgrades Red-Eyes", E, "duel_main1", 2000, METALMORPH_UPGRADE_KEYS,
              {"P_ZONES": "0:579:e,5:466:sa", "P_DECK": "580"}, r"P 580,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 6 5 grave 2 0",
              control="passes", verify=lambda log: "coin" not in log),
        check("bosses: Black Metal Dragon + 1/4 beats Blue-Eyes", E, "duel_turn2", 1800, BATTLE_KEYS,
              {"P_ZONES": "0:580", "C_ZONES": "0:82"}, r"P 580,0,0,0,0 C 0,0,0,0,0 LP 7900 7450"),
        check("bosses: ... but not when it's attacked", E, "duel_main1", 4000, END_TURN_KEYS,
              dict(QUIET_CPU, C_ZONES="0:82", P_ZONES="0:580"), r"P 0,0,0,0,0 C 82,0,0,0,0 LP 7800 8000",
              control="passes"),
        # Joey's Metalmorph: the CPU's set Metalmorph onto its Red-Eyes, then the upgrade from its deck
        check("bosses: the CPU's Metalmorph upgrades Red-Eyes", E, "duel_main1", 4500, END_TURN_KEYS,
              dict(QUIET_CPU, C_ZONES="0:579:u,5:466:sa", C_DECK="580,82"),
              r"C\{0\[1/0=1281\]\}[\s\S]*P 0,0,0,0,0 C 0,580,0,0,0 LP 5200 8000 hand 6 6 grave 0 2"),
        check("bosses: ... onto Red-Eyes, not its Blue-Eyes", E, "duel_main1", 5000, END_TURN_KEYS,
              dict(QUIET_CPU, C_ZONES="0:579:u,1:82,5:466:sa", C_DECK="580,82"),
              r"P 0,0,0,0,0 C 0,82,580,0,0 LP 2200 8000"),
        check("bosses: ... and keeps it set without one", E, "duel_main1", 4500, END_TURN_KEYS,
              dict(QUIET_CPU, C_ZONES="0:579:u,5:466:sa"),
              r"P 0,0,0,0,0 C 579,0,0,0,0 LP 5600 8000 hand 6 6 grave 0 0 links P\{\} C\{\}", control="passes"),
        # from the hand: the CPU sets it on its turn (the original rule for any Trap), and plays it on the next
        check("bosses: ... and from its hand over two turns", E, "duel_main1", 7500, METALMORPH_TWO_TURNS_KEYS,
              dict(QUIET_CPU, P_HANDN="5", C_ZONES="0:579", C_HAND="466,82,82,82,82", C_DECK="580,82"),
              r"LP 5600 8000[\s\S]*C\{0\[1/0=1281\]\}[\s\S]*C 0,580,0,0,0 LP 2800 8000"),
        # the one monster effect after Main Phase 1 comes on a turn the CPU summons to attack too
        check("bosses: the CPU's Dark Magician on a summon turn", E, "duel_main1", 4500, END_TURN_KEYS,
              {"C_ZONES": "0:150:u", "P_ZONES": "5:570:s", "C_HAND": "1,1,1,1,1"}, r"C 150,1,0,0,0 [^\n]*grave 1 0"),
        check("bosses: the CPU still fuses B. Skull Dragon", E, "duel_main1", 4000, END_TURN_KEYS,
              {"C_HAND": "552,675,579,82,82", "C_FUSION": "42", "P_HAND": "1,1,1,1,1"}, r"C 42,0,0,0,0",
              control="passes"),
    ] + [check(f"bosses: {name}'s card text", None, None, 0, None, {}, text.encode("ascii"))
         for text, name in texts.items()]


# The Fusion and Ritual monsters' effects. Zone 0's menu: Def Pos is the second command (Card View, Def Pos).
DEF_POS_KEYS = "20 UP; 40 UP; 70 A; 120 RIGHT; 240 A"
BICKURIBOX_KEYS = DEF_POS_KEYS + "; 720 A; 820 A"            # A through the "destroy" prompt, the CPU's zone 0
THOUSAND_DRAGON_KEYS = ACTIVATE_KEYS + "; 700 A"             # call Heads (the cursor's first choice)
CHAMPION_KEYS = RED_EYES_KEYS                                # Activate, A through the prompt, the CPU's zone 0
SKULL_GUARDIAN_KEYS = END_TURN_KEYS + "; 1100 A"             # Yes, when the CPU's attack asks
DOKURORIDER_GRAVE = ",".join(["1"] * 12)


def extra_deck_effects_suite():
    sys.path.insert(0, str(HERE.parent / "scripts"))
    from apply_gods import EXTRA_DECK_3T
    texts = {text: name for name, text in EXTRA_DECK_3T.values()}
    battle = lambda name, env, regex, **kw: check(f"Extra Deck: {name}", E, "duel_turn2", 1800, BATTLE_KEYS, env,
                                                  regex, **kw)
    cpu = lambda name, env, regex, frames=4000, keys=END_TURN_KEYS, **kw: check(
        f"Extra Deck: {name}", E, "duel_main1", frames, keys, dict(QUIET_CPU, **env), regex, **kw)
    main = lambda name, frames, keys, env, regex, **kw: check(f"Extra Deck: {name}", E, "duel_main1", frames, keys,
                                                               env, regex, **kw)
    return [
        # always on, in battle (the player attacks the CPU's zone 0 in duel_turn2)
        battle("B. Skull Dragon pierces", {"P_ZONES": "0:42", "C_ZONES": "0:1:d"},
               r"P 42,0,0,0,0 C 0,0,0,0,0 LP 7900 5600"),
        battle("Black Luster Soldier pierces", {"P_ZONES": "0:71", "C_ZONES": "0:1:d"},
               r"P 71,0,0,0,0 C 0,0,0,0,0 LP 7900 5800"),
        battle("Javelin Beetle pierces", {"P_ZONES": "0:356", "C_ZONES": "0:1:d"},
               r"P 356,0,0,0,0 C 0,0,0,0,0 LP 7900 6350"),
        cpu("the CPU's B. Skull Dragon pierces", {"C_ZONES": "0:42", "P_ZONES": "0:1:d"},
            r"P 0,0,0,0,0 C 42,0,0,0,0 LP 5600 8000"),
        battle("Labyrinth Tank survives Blue-Eyes", {"P_ZONES": "0:395", "C_ZONES": "0:82"},
               r"P 395,0,0,0,0 C 82,0,0,0,0 LP 7300 8000"),
        battle("Crab Turtle survives Blue-Eyes", {"P_ZONES": "0:120", "C_ZONES": "0:82"},
               r"P 120,0,0,0,0 C 82,0,0,0,0 LP 7450 8000"),
        battle("Fortress Whale survives Blue-Eyes", {"P_ZONES": "0:245", "C_ZONES": "0:82"},
               r"P 245,0,0,0,0 C 82,0,0,0,0 LP 7250 8000"),
        cpu("... and the CPU's Blue-Eyes", {"C_ZONES": "0:82", "P_ZONES": "0:245"},
            r"P 245,0,0,0,0 C 82,0,0,0,0 LP 7350 8000"),
        battle("Twin-Headed Thunder Dragon: 3100 in its Battle Phase", {"P_ZONES": "0:749", "C_ZONES": "0:82"},
               r"P 749,0,0,0,0 C 0,0,0,0,0 LP 7900 7900"),
        cpu("... 2800 in the CPU's", {"C_ZONES": "0:82", "P_ZONES": "0:749"},
            r"P 0,0,0,0,0 C 82,0,0,0,0 LP 7800 8000", control="passes"),
        battle("Skull Knight: +100 per monster in the Graveyard (4)",
               {"P_ZONES": "0:637", "C_ZONES": "0:82", "P_GRAVE": "1,1,1,1"}, r"P 637,0,0,0,0 C 0,0,0,0,0 LP 7900 7950"),
        battle("... and 2950 with 3", {"P_ZONES": "0:637", "C_ZONES": "0:82", "P_GRAVE": "1,1,1"},
               r"P 0,0,0,0,0 C 82,0,0,0,0 LP 7850 8000"),
        cpu("the CPU's Skull Knight counts its Graveyard", {"C_ZONES": "0:637", "C_GRAVE": "1,1,1,1", "P_ZONES": "0:82"},
            r"P 0,0,0,0,0 C 637,0,0,0,0 LP 7950 8000"),
        battle("Zera The Mant: +100 per monster in the Graveyard",
               {"P_ZONES": "0:810", "C_ZONES": "0:82", "P_GRAVE": "1,1,1"}, r"P 810,0,0,0,0 C 0,0,0,0,0 LP 7900 7900"),
        battle("Dokurorider: +100 per monster in the Graveyard",
               {"P_ZONES": "0:176", "C_ZONES": "0:82", "P_GRAVE": DOKURORIDER_GRAVE},
               r"P 176,0,0,0,0 C 0,0,0,0,0 LP 7900 7900"),
        battle("Chakra counts both Graveyards",
               {"P_ZONES": "0:109", "C_ZONES": "0:82", "P_GRAVE": "1,1,1", "C_GRAVE": "1,1,1"},
               r"P 109,0,0,0,0 C 0,0,0,0,0 LP 7900 7950"),
        battle("... 2750 with its own 3 only", {"P_ZONES": "0:109", "C_ZONES": "0:82", "P_GRAVE": "1,1,1"},
               r"P 0,0,0,0,0 C 82,0,0,0,0 LP 7650 8000"),
        battle("Kaiser Dragon: +1000 against DARK Dark Magician", {"P_ZONES": "0:368", "C_ZONES": "0:150"},
               r"P 368,0,0,0,0 C 0,0,0,0,0 LP 7900 7200"),
        cpu("... also when Dark Magician attacks it", {"C_ZONES": "0:150", "P_ZONES": "0:368"},
            r"P 368,0,0,0,0 C 0,0,0,0,0 LP 8000 7200"),
        battle("... not against LIGHT Blue-Eyes", {"P_ZONES": "0:368", "C_ZONES": "0:82"},
               r"P 0,0,0,0,0 C 82,0,0,0,0 LP 7200 8000", control="passes"),
        battle("Garma Sword takes LIGHT Blue-Eyes with it", {"P_ZONES": "0:257", "C_ZONES": "0:82"},
               r"P 0,0,0,0,0 C 0,0,0,0,0 LP 7450 8000"),
        cpu("... also when Blue-Eyes attacks it", {"C_ZONES": "0:82", "P_ZONES": "0:257"},
            r"P 0,0,0,0,0 C 0,0,0,0,0 LP 7550 8000"),
        # Magician of Black Chaos: Dark Magician's effect
        main("Magician of Black Chaos destroys a set card", 1600, DARK_MAGICIAN_KEYS,
             {"P_ZONES": "0:433:e", "C_ZONES": "5:737:s,6:476:s"}, r"P 433,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 6 5 grave 0 1"),
        cpu("the CPU's Magician of Black Chaos", {"C_ZONES": "0:433:u", "P_ZONES": "5:737:s"},
            r"P 0,0,0,0,0 C 433,0,0,0,0 LP 5200 8000 hand 6 6 grave 1 0"),
        # Thousand Dragon: Goddess of Whim's coin, both arts; the link ends with the turn
        main("Thousand Dragon: a right call doubles ATK", 1300, THOUSAND_DRAGON_KEYS,
             dict(HEADS, P_ZONES="0:715:e", C_ZONES="0:82"), r"coin heads\n.*links P\{0\[3/1=715\]\}"),
        main("... a wrong one halves it", 1300, THOUSAND_DRAGON_KEYS,
             dict(CPU_TAILS, P_ZONES="0:715:e", C_ZONES="0:82"), r"coin tails\n.*links P\{0\[3/0=715\]\}"),
        main("... the alternate art too", 1300, THOUSAND_DRAGON_KEYS,
             dict(HEADS, P_ZONES="0:716:e", C_ZONES="0:82"), r"links P\{0\[3/1=716\]\}"),
        main("... until the end of the turn", 2600, THOUSAND_DRAGON_KEYS + "; 1300 B; 1340 A",
             dict(QUIET_CPU, **HEADS, P_ZONES="0:715:e"), r"links P\{0\[3/1=715\]\}[\s\S]*links P\{\} C\{\}"),
        cpu("the CPU's Thousand Dragon, right: 4800 on Blue-Eyes", dict(PIN_RNG="DEADBEEF", C_ZONES="0:715:u",
                                                                       P_ZONES="0:82"),
            r"C\{0\[3/1=715\]\}[\s\S]*P 0,0,0,0,0 C 715,0,0,0,0 LP 6200 8000"),
        cpu("the CPU's Thousand Dragon, wrong: no attack", dict(CPU_TAILS, C_ZONES="0:715:u", P_ZONES="0:82"),
            r"C\{0\[3/0=715\]\}[\s\S]*P 82,0,0,0,0 C 715,0,0,0,0 LP 8000 8000 [^\n]*links P\{\} C\{\}"),
        # Bickuribox: Dream Clown's trigger, and the CPU makes the change itself
        main("Bickuribox to Defense destroys Blue-Eyes", 1500, BICKURIBOX_KEYS, {"P_ZONES": "0:63", "C_ZONES": "0:82"},
             r"P 63,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 6 5 grave 0 1"),
        cpu("the CPU's Bickuribox goes to Defense on Blue-Eyes", {"C_ZONES": "0:63", "P_ZONES": "0:82"},
            r"P 0,0,0,0,0 C 63,0,0,0,0 LP 8000 8000 hand 6 6 grave 1 0"),
        cpu("... and attacks a weaker monster", {"C_ZONES": "0:63", "P_ZONES": "0:1"},
            r"P 0,0,0,0,0 C 63,0,0,0,0 LP 7500 8000", control="passes"),
        # Skull Guardian: Suijin's answer, once per turn
        cpu("Skull Guardian zeroes the attacking Blue-Eyes", {"P_ZONES": "0:636:e", "C_ZONES": "0:82"},
            r"P 636,0,0,0,0 C 0,0,0,0,0 LP 8000 5950", keys=SKULL_GUARDIAN_KEYS),
        cpu("... once per turn", {"P_ZONES": "0:636:e", "C_ZONES": "0:82,1:82"},
            r"P 0,0,0,0,0 C 0,82,0,0,0 LP 7050 5950", frames=5000, keys=SKULL_GUARDIAN_KEYS),
        cpu("... ready when Ritual Summoned", {"P_HAND": SIX("524"), "P_ZONES": "0:150", "P_FUSION": "636",
                                                "C_ZONES": "0:82"},
            r"P 636,0,0,0,0 C 0,0,0,0,0 LP 8000 5950", frames=3500,
            keys=RITUAL_KEYS + "; 1300 B; 1340 A; 2400 A"),
        # Gaia the Dragon Champion and Super War-Lion
        main("Gaia destroys a weaker monster and can't attack", 1500, CHAMPION_KEYS,
             {"P_ZONES": "0:251:e", "C_ZONES": "0:150"},
             r"P 251,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 6 5 grave 0 1 links P\{0\[ noatk\]\}"),
        main("... no Activate against a stronger one", 1500, CHAMPION_KEYS, {"P_ZONES": "0:251:e", "C_ZONES": "0:82"},
             r"grave 0 1", must=False, control="passes"),
        main("... or a face-down one", 1500, CHAMPION_KEYS, {"P_ZONES": "0:251:e", "C_ZONES": "0:1:s"},
             r"grave 0 1", must=False, control="passes"),
        main("... or once its effect is used", 1500, CHAMPION_KEYS, {"P_ZONES": "0:251:u", "C_ZONES": "0:150"},
             r"grave 0 1", must=False, control="passes"),
        main("... refuses the stronger pick, takes the weaker", 1800, CHAMPION_KEYS + "; 700 RIGHT; 760 A",
             {"P_ZONES": "0:251:e", "C_ZONES": "0:82,1:150"}, r"P 251,0,0,0,0 C 82,0,0,0,0 [^\n]*grave 0 1"),
        main("Super War-Lion destroys a weaker monster", 1500, CHAMPION_KEYS, {"P_ZONES": "0:676:e", "C_ZONES": "0:1"},
             r"P 676,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 6 5 grave 0 1 links P\{0\[ noatk\]\}"),
        cpu("the CPU's Gaia takes a Defense Position monster", {"C_ZONES": "0:251:u", "P_ZONES": "0:1:d"},
            r"P 0,0,0,0,0 C 251,0,0,0,0 LP 8000 8000 hand 6 6 grave 1 0 links P\{\} C\{0\[ noatk\]\}"),
        cpu("... one of two monsters", {"C_ZONES": "0:251:u", "P_ZONES": "0:1,1:1"},
            r"P 0,1,0,0,0 C 251,0,0,0,0 LP 8000 8000 hand 6 6 grave 1 0 links P\{\} C\{0\[ noatk\]\}", frames=4500),
        cpu("... and attacks a lone Attack Position one", {"C_ZONES": "0:251:u", "P_ZONES": "0:1"},
            r"P 0,0,0,0,0 C 251,0,0,0,0 LP 7200 8000", control="passes"),
        # the cards they borrow from
        main("regression: Dream Clown still destroys", 1500, BICKURIBOX_KEYS, {"P_ZONES": "0:186", "C_ZONES": "0:82"},
             r"P 186,0,0,0,0 C 0,0,0,0,0 LP 8000 8000 hand 6 5 grave 0 1", control="passes"),
        cpu("regression: Suijin still zeroes", {"P_ZONES": "0:674:e", "C_ZONES": "0:82"},
            r"P 674,0,0,0,0 C 0,0,0,0,0 LP 8000 5500", keys=SKULL_GUARDIAN_KEYS, control="passes"),
        # either side of the coin (the pinned state lands differently on the control): it still links
        main("regression: Goddess of Whim's coin", 1300, THOUSAND_DRAGON_KEYS,
             dict(HEADS, P_ZONES="0:284:e", C_ZONES="0:82"), r"coin (heads|tails)\n.*links P\{0\[3/[01]=284\]\}",
             control="passes"),
        battle("regression: Mechanical Spider takes DARK Dark Magician", {"P_ZONES": "0:453", "C_ZONES": "0:150"},
               r"P 0,0,0,0,0 C 0,0,0,0,0 LP 5800 8000", control="passes"),
    ] + [check(f"Extra Deck: {name}'s card text", None, None, 0, None, {}, text.encode("ascii"))
         for text, name in texts.items()]


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
    ap.add_argument("--second-decks", action="store_true", help="the ROM has the second decks (gods-3t-fx)")
    ap.add_argument("--deck-tuning", action="store_true", help="the ROM has the CPU deck tuning (gods-3t-fx)")
    ap.add_argument("--extra-deck-rituals", action="store_true",
                    help="the ROM has the Ritual monsters in the Extra Deck (gods-3t-fx)")
    ap.add_argument("--boss-effects", action="store_true", help="the ROM has the bosses' effects (gods-3t-fx)")
    ap.add_argument("--extra-deck-effects", action="store_true",
                    help="the ROM has the Fusion and Ritual monsters' effects (gods-3t-fx)")
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
        checks = checks + rules_suite(args.boss_effects)
        tag += "gr"
    rituals = args.extra_deck_rituals
    if args.second_decks:
        checks = checks + second_decks_suite(rituals)
        tag += "sd"
    if args.deck_tuning:
        checks = checks + deck_tuning_suite(rituals)
        tag += "dt"
    if rituals:
        checks = checks + extra_deck_rituals_suite(args.extra_deck_effects)
        tag += "edr"
    if args.boss_effects:
        checks = checks + boss_effects_suite()
        tag += "boss"
    if args.extra_deck_effects:
        checks = checks + extra_deck_effects_suite()
        tag += "xde"
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
