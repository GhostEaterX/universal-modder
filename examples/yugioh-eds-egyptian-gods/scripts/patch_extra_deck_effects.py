#!/usr/bin/env python3
"""Give the high-Level Fusion and Ritual monsters effects, in the three-Tribute effects build. Runs on eds-decomp
857002a after patch_boss_effects.py (it appends rows after the bosses' and calls the boss unit's hooks).

    python3 patch_extra_deck_effects.py <eds-decomp checkout> [--check]

The rules are this mod's own code, in ../src: extra_deck_effects.c and extra_deck_effects.h. This script copies
them into the tree as a new unit and makes the edits that connect them to the engine:
  - CalcBattle (campaign.c): B. Skull Dragon, Black Luster Soldier and Javelin Beetle pierce; Labyrinth Tank, Crab
    Turtle and Fortress Whale are not destroyed by battle; Kaiser Dragon gains 1000 ATK against a DARK monster;
    Garma Sword destroys a LIGHT monster it battles;
  - GetZoneCardStats (card_stats.c): Twin-Headed Thunder Dragon takes the +300 ATK rule of effect key 1516 (its
    controller's Battle Phase), Skull Knight, Zera The Mant and Dokurorider Shadow Ghoul's +100 ATK per monster
    in the Graveyard, Chakra the same over both Graveyards, and Thousand Dragon's coin link doubles or halves ATK
    as Goddess of Whim's;
  - the effect table (data/god_effects_table.s) gets rows for Magician of Black Chaos (Dark Magician's), Gaia
    the Dragon Champion and Super War-Lion (new), Thousand Dragon and its alternate art (Goddess of Whim's) and
    Bickuribox (Dream Clown's) after the bosses'; FindCardEffect looks for them after the bosses' rows;
  - the monster menu offers Activate for the activated ones (card_command_menu.c), their once-per-turn flag comes
    back every turn and Thousand Dragon's coin ends with the turn (duel_cmd_turn.c);
  - Bickuribox triggers when it is changed to Defense Position (duel_field_moves.c, Dream Clown's case) and
    asks with Dream Clown's "destroy" prompt (effect_targets1.c);
  - Skull Guardian answers an attack as Suijin does (battle_phase1.c; the link-duel question in duel_turn_end.c);
  - the CPU activates them after the bosses (ai_deck.c).
apply_gods.py --text 3 rewrites their card text (EXTRA_DECK_3T); their kind stays Fusion or Ritual, which files
them in the Extra Deck. Idempotent. Stdlib only.
"""
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
MARK = "mod (Extra Deck effects)"
INCLUDE = '#include "extra_deck_effects.h"  /* universal-modder: the Fusion and Ritual monsters\' effects */\n'
FILES = {"src/extra_deck_effects.c": "extra_deck_effects.c", "include/extra_deck_effects.h": "extra_deck_effects.h"}
NEW_UNITS = ["extra_deck_effects"]
CHAMPION_ROW = ("\t.4byte ExtraDeckChampionResolve, ExtraDeckChampionCheck, ExtraDeckChampionPrepare, 0, "
                "ExtraDeckChampionChainB\n")
THOUSAND_DRAGON_ROW = "\t.4byte ExtraDeckThousandDragonResolve, 0, BossOncePerTurnPrepare, 0, 0\n"
ACTIVATED = ("CARD_MAGICIAN_OF_BLACK_CHAOS", "CARD_GAIA_THE_DRAGON_CHAMPION", "CARD_SUPER_WAR_LION",
             "CARD_THOUSAND_DRAGON", "CARD_THOUSAND_DRAGON_ALT")


def cases(indent, numbers, comment):
    """`case X:` lines, the first one carrying the comment."""
    out = ""
    for i, n in enumerate(numbers):
        line = f"{indent}case {n}:"
        out += (line.ljust(len(indent) + 38) + f"/* {comment} */\n") if i == 0 else line + "\n"
    return out


# (path, anchor, text, how): how is "after", "replace" or "before:<where>" (insert before <where>, which
# must be inside the anchor).
EDITS = [
    # The effect rows, after the bosses'. Row: number, flags, then resolve, check, prepare, chainA, chainB.
    ("data/god_effects_table.s",
     "\t.2byte 81, 0\n"
     "\t.4byte BossRedEyesResolve, BossOpponentMonsterCheck, BossOncePerTurnPrepare, 0, BossRedEyesChainB\n",
     f"@ {MARK}: Magician of Black Chaos (Dark Magician's row), Gaia the Dragon Champion, Super\n"
     "@ War-Lion, Thousand Dragon and its alternate art (Goddess of Whim's) and Bickuribox (Dream Clown's), after\n"
     "@ the bosses' rows (EXTRA_DECK_EFFECT_ROWS).\n"
     "\t.2byte 721, 0\n"
     "\t.4byte BossDarkMagicianResolve, BossOpponentSpellTrapCheck, BossOncePerTurnPrepare, 0, BossDarkMagicianChainB\n"
     "\t.2byte 36, 0\n" + CHAMPION_ROW +
     "\t.2byte 355, 0\n" + CHAMPION_ROW +
     "\t.2byte 68, 0\n" + THOUSAND_DRAGON_ROW +
     "\t.2byte 2068, 0\n" + THOUSAND_DRAGON_ROW +
     "\t.2byte 384, 0\n"
     "\t.4byte ExtraDeckDestroyTargetResolve, BossOpponentMonsterCheck, 0, 0, BossRedEyesChainB\n",
     "after"),
    ("src/effect_hooks.c",
     "            return BossFindCardEffect(key);    /* mod (boss effects): the rows after the Gods' */\n",
     f"            return ExtraDeckFindCardEffect(key);   /* mod (boss effects), {MARK}: the rows after the Gods' */\n",
     "replace"),
    # The monster menu's Activate.
    ("src/card_command_menu.c",
     "    case CARD_DARK_MAGICIAN_ALT:\n    case CARD_BARREL_DRAGON:\n",
     cases("    ", ACTIVATED, MARK),
     "before:    case CARD_BARREL_DRAGON:"),
    # Once per turn: the flag comes back at the start of each of its controller's turns.
    ("src/duel_cmd_turn.c",
     "                case CARD_RED_EYES_B_DRAGON:\n                    monster->effectUnused = 1;\n",
     cases("                ", ACTIVATED + ("CARD_SKULL_GUARDIAN",), MARK),
     "before:                    monster->effectUnused = 1;"),
    # Thousand Dragon's coin lasts until the end of the turn.
    ("src/duel_cmd_turn.c",
     "                    QueueRemoveZoneLink(player, CardNumberToId(gEndOfTurnEffectCards[j]),\n"
     "                                        ZONE_LOC(player, i), ZONE_LINK_CARD_EFFECT);\n"
     "            }\n",
     f"            ExtraDeckEndOfTurnLinks(player, i);     /* {MARK}: Thousand Dragon's coin */\n",
     "after"),
    # Bickuribox: Dream Clown's trigger and prompt.
    ("src/duel_field_moves.c",
     "        switch (CARD_NUMBER(id)) {\n        case CARD_DREAM_CLOWN:\n        case CARD_TAINTED_WISDOM:\n",
     f"        case CARD_BICKURIBOX:             /* {MARK}: Dream Clown's trigger */\n",
     "before:        case CARD_DREAM_CLOWN:"),
    ("src/effect_targets1.c",
     "        case CARD_RED_EYES_B_DRAGON:      /* mod (boss effects) */\n        case CARD_DREAM_CLOWN:\n",
     f"        case CARD_BICKURIBOX:             /* {MARK} */\n",
     "before:        case CARD_DREAM_CLOWN:"),
    # Skull Guardian: Suijin's answer to an attack, and the link partner's question about it.
    ("src/battle_phase1.c",
     "                switch (number) {\n                case CARD_SANGA_OF_THE_THUNDER:\n",
     f"                case CARD_SKULL_GUARDIAN:         /* {MARK}: Suijin's answer */\n",
     "before:                case CARD_SANGA_OF_THE_THUNDER:"),
    ("src/duel_turn_end.c",
     "        case CARD_SANGA_OF_THE_THUNDER:\n        case CARD_KAZEJIN:\n        case CARD_SUIJIN:\n"
     "            FormatStr(text, gStrAttackTargetZeroAtkFmt",
     f"        case CARD_SKULL_GUARDIAN:         /* {MARK} */\n",
     "before:        case CARD_SANGA_OF_THE_THUNDER:"),
    ("src/duel_turn_end.c",
     "        case CARD_SUIJIN:\n        case CARD_KURIBOH:\n",
     f"        case CARD_SKULL_GUARDIAN:         /* {MARK} */\n",
     "before:        case CARD_KURIBOH:"),
    # GetZoneCardStats.
    ("src/card_stats.c",
     "            case CARD_GODDESS_OF_WHIM:\n                /* the coin toss: value 1 doubles ATK, 0 halves it.",
     cases("            ", ("CARD_THOUSAND_DRAGON", "CARD_THOUSAND_DRAGON_ALT"), f"{MARK}: its coin"),
     "before:            case CARD_GODDESS_OF_WHIM:"),
    ("src/card_stats.c",
     "    case CARD_SHADOW_GHOUL:\n        /* +100 ATK per monster in its controller's graveyard */\n",
     f"    case CARD_CHAKRA:                     /* {MARK}: +100 ATK per monster in both graveyards */\n"
     "        for (p = 0; p <= 1; p++)\n"
     "            for (i = 0; i < gDuelPlayers[p & 1].graveCount; i++)\n"
     "                if (CARD_TYPE_IS_MONSTER((u32)CARD_TYPE(GRAVEYARD_CARD(p & 1, i).id)))\n"
     "                    addAtk += 100;\n"
     "        break;\n" +
     cases("    ", ("CARD_SKULL_KNIGHT", "CARD_ZERA_THE_MANT", "CARD_DOKURORIDER"), f"{MARK}: Shadow Ghoul's"),
     "before:    case CARD_SHADOW_GHOUL:"),
    ("src/card_stats.c",
     "    case CARD_1516:\n        /* +300 ATK during its controller's Battle Phase */\n",
     f"    case CARD_TWIN_HEADED_THUNDER_DRAGON: /* {MARK}: key 1516's rule */\n",
     "before:    case CARD_1516:"),
    # CalcBattle.
    ("src/campaign.c",
     "    if (zeroAtk)\n        ATTACKER_SIDE.atk = 0;\n",
     f"    /* {MARK}: Kaiser Dragon gains 1000 ATK in a battle with a DARK monster */\n"
     "    ATTACKER_SIDE.atk += ExtraDeckBattleAtkBonus(ATTACKER_SIDE.cardId,\n"
     "                                                 GetZoneCardAttribute(1 - attacker, gBattleView.defSlot));\n"
     "    DEFENDER_SIDE.atk += ExtraDeckBattleAtkBonus(DEFENDER_SIDE.cardId,\n"
     "                                                 GetZoneCardAttribute(attacker, gBattleView.atkSlot));\n",
     "before:    if (zeroAtk)"),
    ("src/campaign.c",
     "        if (BossPierces(ATTACKER_SIDE.cardId))    /* mod (boss effects): Summoned Skull */\n"
     "            piercing = 1;\n",
     f"        if (ExtraDeckPierces(ATTACKER_SIDE.cardId))    /* {MARK} */\n"
     "            piercing = 1;\n",
     "after"),
    ("src/campaign.c",
     "    for (i = 0; i <= 1; i++) {    /* mod (boss effects): Millennium Golem survives (the damage stays) */\n",
     f"    /* {MARK}: Garma Sword destroys a LIGHT monster it battles */\n"
     "    if (ExtraDeckDestroysLight(ATTACKER_SIDE.cardId)\n"
     "        && GetZoneCardAttribute(1 - attacker, gBattleView.defSlot) == ATTRIBUTE_LIGHT)\n"
     "        DEFENDER_SIDE.destroyed = 1;\n"
     "    if (ExtraDeckDestroysLight(DEFENDER_SIDE.cardId)\n"
     "        && GetZoneCardAttribute(attacker, gBattleView.atkSlot) == ATTRIBUTE_LIGHT)\n"
     "        ATTACKER_SIDE.destroyed = 1;\n",
     "before:    for (i = 0; i <= 1; i++) {"),
    ("src/campaign.c",
     "        if (BossBattleIndestructible(gBattleView.side[i].cardId))\n",
     "        if (BossBattleIndestructible(gBattleView.side[i].cardId)\n"
     f"            || ExtraDeckBattleIndestructible(gBattleView.side[i].cardId))    /* {MARK} */\n",
     "replace"),
    # The CPU, after the bosses.
    ("src/ai_deck.c",
     "    return BossAiActivateEffects();    /* mod (boss effects): Dark Magician and Red-Eyes */\n",
     "    {\n"
     "        int done = BossAiActivateEffects();    /* mod (boss effects): Dark Magician and Red-Eyes */\n"
     "\n"
     "        if (done)\n"
     "            return done;\n"
     "    }\n"
     f"    return ExtraDeckAiActivateEffects();    /* {MARK} */\n",
     "replace"),
]
INCLUDED = ["src/ai_deck.c", "src/campaign.c", "src/duel_cmd_turn.c", "src/effect_hooks.c"]


def edit(t, path, anchor, text, how):
    if how == "after":
        new = anchor + text
    elif how == "replace":
        new = text
    else:
        where = how[len("before:"):]
        assert where in anchor, (path, where[:40])
        new = anchor.replace(where, text + where, 1)
    if new in t:
        return t, False
    if t.count(anchor) != 1:
        sys.exit(f"{path}: anchor found {t.count(anchor)} times (not eds-decomp 857002a after patch_boss_effects.py?):\n"
                 f"{anchor[:120]}")
    return t.replace(anchor, new), True


def apply(root, check):
    changed = 0
    texts = {}
    for path, anchor, text, how in EDITS:
        p = root / path
        texts[p], did = edit(texts.get(p, p.read_text()), path, anchor, text, how)
        changed += did
    for path in INCLUDED:
        p = root / path
        if INCLUDE not in texts[p]:
            texts[p], did = edit(texts[p], path, '#include "global.h"\n', INCLUDE, "after")
            changed += did
    units = root / "units.txt"
    t = units.read_text()
    if "\nextra_deck_effects\n" not in t:
        t, did = edit(t, "units.txt", "\n@libs\n", "".join(f"{u}\n" for u in NEW_UNITS), "before:@libs\n")
        texts[units] = t
        changed += did
    copies = [(root / dst, SRC / src) for dst, src in FILES.items()
              if not (root / dst).exists() or (root / dst).read_bytes() != (SRC / src).read_bytes()]
    if not check:
        for p, t in texts.items():
            p.write_text(t)
        for dst, src in copies:
            shutil.copyfile(src, dst)
    return changed, len(copies)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("decomp", type=Path)
    ap.add_argument("--check", action="store_true", help="report only")
    args = ap.parse_args()
    n, copied = apply(args.decomp, args.check)
    print(f"{'would apply' if args.check else 'applied'} {n} edits, {copied} new files"
          + (" (already applied)" if n == 0 and copied == 0 else ""))


if __name__ == "__main__":
    main()
