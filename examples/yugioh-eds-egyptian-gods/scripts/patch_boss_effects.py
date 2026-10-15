#!/usr/bin/env python3
"""Give the CPU duelists' Normal-monster bosses effects, in the three-Tribute effects build. Runs on eds-decomp
857002a after patch_god_effects.py (it appends rows to the Gods' relocated effect table).

    python3 patch_boss_effects.py <eds-decomp checkout> [--check]

The rules are this mod's own code, in ../src: boss_effects.c and boss_effects.h. This script copies them into
the tree as a new unit and makes the edits that connect them to the engine:
  - CalcBattle (campaign.c): Summoned Skull pierces, Millennium Golem is not destroyed by battle, and Red-Eyes
    Black Metal Dragon adds a quarter of the attacked monster's ATK (after Metalmorph's half);
  - the effect table (data/god_effects_table.s) gets rows for Dark Magician (34 and its alternate art 2034) and
    Red-Eyes B. Dragon (81) after the Gods'; FindCardEffect looks for them when its binary search fails;
  - the monster menu offers Activate for them (card_command_menu.c); a Red-Eyes with a Metalmorph keeps the
    original upgrade to Red-Eyes Black Metal Dragon, one without uses its own effect (duel_cmd_queue.c);
  - their once-per-turn flag comes back every turn, as Barrel Dragon's (duel_cmd_turn.c);
  - Red-Eyes' target prompt is Barrel Dragon's "destroy" one (effect_targets1.c);
  - the CPU activates them after the Gods (ai_deck.c). With Red-Eyes Black Metal Dragon in its deck it plays
    Joey's Metalmorph first: onto its Red-Eyes (its Metalmorph pick in effect_targets1.c), then the upgrade, in
    the same step (ai_steps.c, the one monster effect after Main Phase 1).
apply_gods.py --text 3 makes these monsters Effect monsters (the kind gives monster effects spell speed 1)
and rewrites their card text. Idempotent. Stdlib only.
"""
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
MARK = "mod (boss effects)"
INCLUDE = '#include "boss_effects.h"        /* universal-modder: the bosses\' effects */\n'
FILES = {"src/boss_effects.c": "boss_effects.c", "include/boss_effects.h": "boss_effects.h"}
NEW_UNITS = ["boss_effects"]

# (path, anchor, text, how): how is "after", "replace" or "before:<where>" (insert before <where>, which
# must be inside the anchor).
EDITS = [
    # The effect rows, after the Gods'. Row: number, flags, then resolve, check, prepare, chainA, chainB.
    ("data/god_effects_table.s",
     "\t.2byte 1912, 0\n\t.4byte GodRaResolve, 0, GodRaPrepare, 0, GodRaChainB\n",
     f"@ {MARK}: Dark Magician, its alternate art and Red-Eyes B. Dragon. They are not in order, so\n"
     "@ FindCardEffect finds them with BossFindCardEffect (BOSS_EFFECT_ROWS).\n"
     "\t.2byte 34, 0\n"
     "\t.4byte BossDarkMagicianResolve, BossOpponentSpellTrapCheck, BossOncePerTurnPrepare, 0, BossDarkMagicianChainB\n"
     "\t.2byte 2034, 0\n"
     "\t.4byte BossDarkMagicianResolve, BossOpponentSpellTrapCheck, BossOncePerTurnPrepare, 0, BossDarkMagicianChainB\n"
     "\t.2byte 81, 0\n"
     "\t.4byte BossRedEyesResolve, BossOpponentMonsterCheck, BossOncePerTurnPrepare, 0, BossRedEyesChainB\n",
     "after"),
    ("src/effect_hooks.c",
     "        if (lo == hi)\n            return -1;\n",
     f"        if (lo == hi)\n            return BossFindCardEffect(key);    /* {MARK}: the rows after the Gods' */\n",
     "replace"),
    # The monster menu's Activate.
    ("src/card_command_menu.c",
     "    case CARD_BARREL_DRAGON:\n    case CARD_VALKYRION_THE_MAGNA_WARRIOR:\n",
     f"    case CARD_DARK_MAGICIAN:              /* {MARK} */\n    case CARD_DARK_MAGICIAN_ALT:\n",
     "before:    case CARD_BARREL_DRAGON:"),
    ("src/card_command_menu.c",
     "    case CARD_RED_EYES_B_DRAGON:\n    case CARD_ZOA:\n"
     "        if (CountZoneLinksFromCard(player, zone, CARD_METALMORPH) == 0)\n            return 0;\n",
     "    case CARD_RED_EYES_B_DRAGON:\n    case CARD_ZOA:\n"
     "        if (CountZoneLinksFromCard(player, zone, CARD_METALMORPH) == 0) {\n"
     f"            if (CARD_NUMBER_OF(id) == CARD_RED_EYES_B_DRAGON)    /* {MARK}: its own effect */\n"
     "                return CanActivateEffectInZone(player, zone, 0);\n"
     "            return 0;\n"
     "        }\n",
     "replace"),
    ("src/duel_cmd_queue.c",
     "            case CARD_RED_EYES_B_DRAGON:\n            case CARD_ZOA:\n"
     "                /* Step 0: tribute the monster; step 1: Special Summon its metal form from the deck. */\n",
     f"                /* {MARK}: without a Metalmorph, Red-Eyes' own effect, as the default case below. Only\n"
     "                 * at step 0: the upgrade's step 1 finds the zone empty, its Metalmorph gone with it. */\n"
     "                if (MENU.step == 0 && CARD_NUMBER_C(gDuel.cardMenuCard) == CARD_RED_EYES_B_DRAGON\n"
     "                    && CountZoneLinksFromCard(MENU.player, MENU.index, CARD_METALMORPH) == 0) {\n"
     "                    Chain_AddPending(((MENU.player & 1) << 31)\n"
     "                                     | (ev = (((MENU.index + MENU.area) & 0x1F) << 16) | CHAIN_KIND_MONSTER << 21)\n"
     "                                     | gDuel.cardMenuCard, 0);\n"
     "                    break;\n"
     "                }\n",
     "after"),
    # Once per turn: the flag comes back at the start of each of its controller's turns.
    ("src/duel_cmd_turn.c",
     "                case CARD_1344:\n                    if (!monster->effectUnused) {\n",
     f"                case CARD_DARK_MAGICIAN:          /* {MARK} */\n"
     "                case CARD_DARK_MAGICIAN_ALT:\n"
     "                case CARD_RED_EYES_B_DRAGON:\n"
     "                    monster->effectUnused = 1;\n"
     "                    break;\n",
     "before:                case CARD_1344:"),
    # The CPU's Metalmorph goes onto its Red-Eyes (the original takes its strongest monster).
    ("src/effect_targets1.c",
     "        switch (CARD_NUMBER(link->card)) {\n        case CARD_MEGAMORPH:\n",
     f"        case CARD_METALMORPH: {{         /* {MARK}: its Red-Eyes first, for the upgrade */\n"
     "            int zone = BossMetalmorphTarget(link);\n\n"
     "            if (zone >= 0 && TryAddEffectTarget(link, link->player, zone) != 0)\n"
     "                return 1;\n"
     "            break;\n"
     "        }\n",
     "before:        case CARD_MEGAMORPH:"),
    # Red-Eyes' target prompt: "destroy", as Barrel Dragon's.
    ("src/effect_targets1.c",
     "        case CARD_DREAM_CLOWN:\n        case CARD_BARREL_DRAGON:\n",
     f"        case CARD_RED_EYES_B_DRAGON:      /* {MARK} */\n",
     "before:        case CARD_DREAM_CLOWN:"),
    # The CPU, after the Gods.
    ("src/ai_deck.c",
     "    return GodAiActivateEffects();     /* mod (God effects): Obelisk and Ra */\n",
     "    if (GodAiActivateEffects())        /* mod (God effects): Obelisk and Ra */\n"
     "        return 1;\n"
     f"    return BossAiActivateEffects();    /* {MARK}: Dark Magician and Red-Eyes */\n",
     "replace"),
    # The CPU's one monster effect after its Main Phase 1: a Metalmorph it activates there resolves, then the
    # upgrade takes the step's place on the next pass.
    ("src/ai_steps.c",
     "    case 0:\n        AiActivateMonsterEffects();\n        st->subState = 0;\n",
     "    case 0:\n"
     f"        /* {MARK}: after a Metalmorph onto Red-Eyes, stay for the upgrade */\n"
     "        if (!BossAiUpgradeRedEyes() && AiActivateMonsterEffects() == BOSS_AI_METALMORPH)\n"
     "            return 0;\n"
     "        st->subState = 0;\n",
     "replace"),
    # CalcBattle.
    ("src/campaign.c",
     "        ATTACKER_SIDE.battleValue += HalveRoundUp(DEFENDER_SIDE.atk) * metalmorphs;\n    }\n",
     f"    /* {MARK}: Red-Eyes Black Metal Dragon adds a quarter of the attacked monster's ATK */\n"
     "    ATTACKER_SIDE.battleValue += BossAttackBonus(ATTACKER_SIDE.cardId, DEFENDER_SIDE.atk);\n",
     "after"),
    ("src/campaign.c",
     "        if (CountActiveZoneLinksFromCard(attacker, gBattleView.atkSlot, CARD_1540))\n"
     "            piercing = 1;\n",
     f"        if (BossPierces(ATTACKER_SIDE.cardId))    /* {MARK}: Summoned Skull */\n"
     "            piercing = 1;\n",
     "after"),
    ("src/campaign.c",
     "    if (CARD_NUMBER(DEFENDER_SIDE.cardId) == 1251 && ATTACKER_SIDE.atk > 1899)\n"
     "        DEFENDER_SIDE.destroyed = 0;\n",
     f"    for (i = 0; i <= 1; i++) {{    /* {MARK}: Millennium Golem survives (the damage stays) */\n"
     "        if (BossBattleIndestructible(gBattleView.side[i].cardId))\n"
     "            gBattleView.side[i].destroyed = 0;\n"
     "    }\n",
     "after"),
]
INCLUDED = ["src/ai_deck.c", "src/ai_steps.c", "src/campaign.c", "src/effect_hooks.c", "src/effect_targets1.c"]


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
        sys.exit(f"{path}: anchor found {t.count(anchor)} times (not eds-decomp 857002a after patch_god_effects.py?):\n"
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
    if "\nboss_effects\n" not in t:
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
