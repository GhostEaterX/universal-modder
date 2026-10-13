#!/usr/bin/env python3
"""Give the Egyptian Gods their effects. Run after patch_source.py (and patch_three_tributes.py for the
three-Tribute build) on eds-decomp 857002a.

    python3 patch_god_effects.py <eds-decomp checkout> [--check]

The effects themselves are this mod's own code, in ../src: god_effects.c (handlers, Slifer's drain, the CPU's
choices), god_effects.h and god_effects_table.s. This script copies them into the tree as two new units and
makes the anchored edits that connect them to the engine:
  - effect.h sends every reader of gCardEffects to gCardEffectsMod, the relocated table with the Gods' rows
    (the original ends where gTributeSummonPrompts starts, so it can't grow in place); duel_response.c's
    alias of the table follows; FindCardEffect searches 428 rows instead of 426;
  - GetZoneCardStats: Slifer's and Ra's ATK/DEF;
  - both Normal Summon executors: Ra's summon trigger; the Ultimate Offering summon skips the position menu
    for a God (a God can't be Normal Set); CanSummonFromHand: the CPU summons Slifer only with 4+ cards in
    hand;
  - SummonAction_Update: Slifer's drain, and no response window for a God's Normal Summon;
  - the card menu: Activate for a face-up Obelisk or Ra; no Set for a God in the hand;
  - CanCardTargetZone: Obelisk can't be targeted;
  - AiActivateMonsterEffects: the CPU's Obelisk and Ra.
Idempotent. Stdlib only.
"""
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
MARK = "mod (God effects)"
INCLUDE = '#include "god_effects.h"         /* universal-modder: the Egyptian Gods\' effects */\n'
FILES = {"src/god_effects.c": "god_effects.c", "include/god_effects.h": "god_effects.h",
         "data/god_effects_table.s": "god_effects_table.s"}
NEW_UNITS = ["god_effects", "god_effects_table"]

# (path, anchor, text, how): how is "after", "replace" or "before:<where>" (insert before <where>, which
# must be inside the anchor).
EDITS = [
    ("include/effect.h",
     "extern const struct CardEffect gCardEffects[];\n",
     f"""/* {MARK}: every reader goes to the relocated table with the Gods' rows (data/god_effects_table.s). */
extern const struct CardEffect gCardEffectsMod[];
#define gCardEffects gCardEffectsMod
""", "after"),
    ("src/duel_response.c",
     "#define gAnswerEffects  gAlias_0819A9D4\n",
     f"#define gAnswerEffects  gCardEffectsMod     /* {MARK}: the relocated table */\n", "replace"),
    ("src/effect_hooks.c",
     "    int hi = 425;                   /* the last row */\n",
     f"    int hi = GOD_EFFECT_ROWS - 1;   /* {MARK}: the last row of gCardEffectsMod */\n", "replace"),
    ("src/card_stats.c",
     "    if (zone > ZONE_MONSTER_4 || !ZONE_AT(player & 1, zone)->isFaceUp)\n        return;\n",
     f"    GodApplyBaseStats(player, zone, out);     /* {MARK}: Slifer's and Ra's ATK/DEF */\n", "after"),
    ("src/summon_checks.c",
     "        TriggerMysteriousPuppeteer(gSummonAction.player);\n"
     "        switch (*((gSummonAction.cardId & CARD_ID_MASK) + gCardIdToNumber)) {\n",
     f"        GodOnNormalSummon(gSummonAction.player, gSummonAction.zone, gSummonAction.cardId);   /* {MARK} */\n",
     "before:        switch (*((gSummonAction.cardId"),
    ("src/summon_checks.c",
     "        TriggerMysteriousPuppeteer(gSummonAction.player);\n"
     "        switch (ActionBNumber(gSummonAction.cardId)) {\n",
     f"        GodOnNormalSummon(gSummonAction.player, gSummonAction.zone, gSummonAction.cardId);   /* {MARK} */\n",
     "before:        switch (ActionBNumber("),
    ("src/summon_checks.c",
     "    case 0:\n        if (action->player) {\n            gTextBox.result = AiShouldSetMonster(action->cardId, 0);\n",
     f"""    case 0:
        if (GOD_IS_GOD_NUMBER(gCardIdToNumber[action->cardId & CARD_ID_MASK])) {{
            gTextBox.result = 0;    /* {MARK}: a God can't be Normal Set, so no position menu */
        }} else if (action->player) {{
            gTextBox.result = AiShouldSetMonster(action->cardId, 0);
""", "replace"),
    ("src/summon_checks.c",
     "    if (IsCardProhibited(cardId) != 0)\n        return 0;\n    if (!CARD_TYPE_IS_MONSTER(CARD_TYPE_C(cardId)))\n",
     f"    if (player == 1 && !GodAiMaySummon(cardId))   /* {MARK}: the CPU's Slifer needs a hand */\n        return 0;\n",
     "before:    if (!CARD_TYPE_IS_MONSTER("),
    ("src/summon_action.c",
     "                    EventResponse_RequestInt(1 - gSummonAction.player, event,\n"
     "                                 LOC(gSummonAction.player, gSummonAction.zone));\n",
     f"""                    /* {MARK}: Slifer's drain, which may destroy the monster; a God's Normal Summon
                     * can't be answered */
                    if (!GodOnSummoned(gSummonAction.player, gSummonAction.zone, SUMMON_FLAGS_KIND(kindFlags))
                        && !GodSummonIsUnanswerable(id, SUMMON_FLAGS_KIND(kindFlags), wasFaceUp))
""", "before:                    EventResponse_RequestInt("),
    ("src/card_command_menu.c",
     "\n    case CARD_TIME_WIZARD:\n    case CARD_MONSTER_EYE:\n",
     f"    case CARD_OBELISK_THE_TORMENTOR:      /* {MARK} */\n    case CARD_THE_WINGED_DRAGON_OF_RA:\n",
     "before:    case CARD_TIME_WIZARD:"),
    ("src/card_command_menu.c",
     "                        break;\n                    case CARD_1350:\n",
     f"""                    case CARD_OBELISK_THE_TORMENTOR:      /* {MARK}: a God can't be Normal Set */
                    case CARD_SLIFER_THE_SKY_DRAGON:
                    case CARD_THE_WINGED_DRAGON_OF_RA:
                        flags &= (u16)~CARDMENU_MASK_SET;
                        break;
""", "before:                    case CARD_1350:"),
    ("src/card_list_viewer.c",
     "        && CARD_SUBTYPE(cardId) != SPELL_EQUIP)\n        ok = 0;\n    return ok;\n",
     f"    if (GodIsUntargetable(targetId))      /* {MARK}: Obelisk */\n        ok = 0;\n",
     "before:    return ok;\n"),
    ("src/ai_deck.c",
     "                    Chain_AddPending(zoneBits | cardWord, 0);\n                    return 1;\n"
     "                }\n            }\n        }\n    }\n    return 0;\n",
     f"""                    Chain_AddPending(zoneBits | cardWord, 0);
                    return 1;
                }}
            }}
        }}
    }}
    return GodAiActivateEffects();     /* {MARK}: Obelisk and Ra */
""", "replace"),
]
INCLUDED = sorted({path for path, *_ in EDITS if path.startswith("src/")})


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
        sys.exit(f"{path}: anchor found {t.count(anchor)} times (not eds-decomp 857002a + patch_source.py?):\n"
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
    if "\ngod_effects\n" not in t:
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
    root = args.decomp
    if "CARD_TYPE_IS_MONSTER" not in (root / "include/constants/card_stats.h").read_text():
        sys.exit("run patch_source.py first")
    n, copied = apply(root, args.check)
    print(f"{'would apply' if args.check else 'applied'} {n} edits, {copied} new files"
          + (" (already applied)" if n == 0 and copied == 0 else ""))


if __name__ == "__main__":
    main()
