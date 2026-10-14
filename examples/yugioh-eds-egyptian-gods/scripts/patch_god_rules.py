#!/usr/bin/env python3
"""Give the Egyptian Gods their TCG summon rules, in the three-Tribute effects build. Run after
patch_god_effects.py on eds-decomp 857002a.

    python3 patch_god_rules.py <eds-decomp checkout> [--check]

The rules are this mod's own code, in ../src: god_rules.c and god_rules.h. This script copies them into the
tree as a new unit and makes the anchored edits that connect them to the engine:
  - CanReviveGraveyardCard: Ra can't be Special Summoned from the Graveyard. This one check builds the target
    lists of Monster Reborn, Call of the Haunted, Premature Burial, The Shallow Grave and Spear Cretin, for
    the player and for the CPU;
  - Time Machine, which revives without that check: not Ra;
  - DuelPhase_End: a face-up Special Summoned Obelisk or Slifer goes to the Graveyard, on either side;
  - AiPickDiscard: the CPU doesn't discard a God in order to revive it.
  - Deck Edit's filters and sorts: the Gods are monsters (the Monsters filter, the ATK/DEF/level sorts of the
    whole list), and Obelisk is an Effect monster, not a Ritual one.
Idempotent. Stdlib only.
"""
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
MARK = "mod (God rules)"
INCLUDE = '#include "god_rules.h"           /* universal-modder: the Gods\' TCG summon rules */\n'
FILES = {"src/god_rules.c": "god_rules.c", "include/god_rules.h": "god_rules.h"}
NEW_UNITS = ["god_rules"]

# (path, anchor, text, how): how is "after", "replace" or "before:<where>" (insert before <where>, which
# must be inside the anchor).
EDITS = [
    ("src/duel_ritual.c",
     "    u32 cardId = (*(u32 *)(graveIdx * 4 + sideOffset + base) << 20) >> 20;\n"
     "    int kind = GetCardKind(cardId);\n\n",
     f"    if (GodCannotBeSpecialSummoned(cardId))     /* {MARK}: Ra */\n        return 0;\n", "after"),
    ("src/effect_resolve3.c",
     "                /* destroyedCopy (bit 5) tested as the sign bit: lsl #26 */\n",
     f"                if (GodCannotBeSpecialSummoned(side->cardId))   /* {MARK}: Ra */\n"
     "                    canSummon = 0;\n",
     "before:                /* destroyedCopy"),
    ("src/battle_phase3.c",
     "    case END_STEP_LOW_LEVEL_CHECK:\n        EndPhase_DestroyLowLevelMonsters(player);\n",
     f"        GodEndPhase();      /* {MARK}: a Special Summoned Obelisk or Slifer leaves */\n",
     "before:        EndPhase_DestroyLowLevelMonsters"),
    ("src/deck_edit_filter.c",
     "            case CARD_TYPE_TICKET:\n            case CARD_TYPE_DIVINE:\n                base[n2++] = card;\n",
     f"            case CARD_TYPE_TICKET:      /* {MARK}: a God sorts among the monsters */\n"
     "                base[n2++] = card;\n", "replace"),
    ("src/deck_edit_filter.c",
     "            case CARD_TYPE_TICKET:\n            case CARD_TYPE_DIVINE:\n                break;\n",
     f"            case CARD_TYPE_TICKET:      /* {MARK}: the Gods are monsters */\n                break;\n",
     "replace"),
    ("src/deck_edit_filter.c",
     "    case CARD_OBELISK_THE_TORMENTOR: return CARD_KIND_RITUAL;\n",
     f"    case CARD_OBELISK_THE_TORMENTOR:    /* {MARK}: an Effect monster, whatever its frame */\n", "replace"),
    ("src/summon_builders.c",
     "            pick = AiPickStrongestHandMonster(gDuelPlayers, 1);\n            if (pick >= 0)\n",
     f"            pick = AiPickStrongestHandMonster(gDuelPlayers, 1);\n"
     f"            if (pick >= 0 && GodAiMayDiscardToRevive(gDuelPlayers[1].hand[pick].id))    /* {MARK} */\n",
     "replace"),
]
INCLUDED = sorted({path for path, *_ in EDITS})


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
        sys.exit(f"{path}: anchor found {t.count(anchor)} times (not eds-decomp 857002a + the God effects?):\n"
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
    if "\ngod_rules\n" not in t:
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
    if not (root / "include/god_effects.h").exists():
        sys.exit("run patch_god_effects.py first")
    n, copied = apply(root, args.check)
    print(f"{'would apply' if args.check else 'applied'} {n} edits, {copied} new files"
          + (" (already applied)" if n == 0 and copied == 0 else ""))


if __name__ == "__main__":
    main()
