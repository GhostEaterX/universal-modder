#!/usr/bin/env python3
"""Put the Ritual monsters in the Extra Deck (EDS's Fusion Deck), in the three-Tribute effects build. Runs on
eds-decomp 857002a after patch_source.py (it uses CARD_TYPE_IS_MONSTER and the Gods' kind rewrite).

    python3 patch_extra_deck_rituals.py <eds-decomp checkout> [--check]

The rule is this mod's own code, in ../src: extra_deck_rituals.c and extra_deck_rituals.h. This script copies
them into the tree as a new unit and makes the edits that connect them to the engine:
  - where a card is filed, the "kind == Fusion" test becomes IsExtraDeckMonster (Fusion or Ritual, not a God):
      Deck Edit           DeckEdit_IsFusionMonster (Deck vs Fusion Deck, its 20-card limit), the two copy
                          counts of a Deck-list card, and the Side Deck refusal (deck_edit_widgets/view.c);
      the CPU's decks     AddCardNumberToDeckTop (ai_summon.c), which loads the deck lists;
      a duel              IsFusionMonster (returning a monster to the hand or the deck, and the animation),
                          AddCardToHand (duel_piles.c), the graveyard-to-hand animation (duel_cmd_piles.c);
  - the Ritual Magic cards find their monster in the Fusion Deck: HandHasRitualMonster also looks there, and
    EffectRitualSummonResolve takes it from there first (duel_ritual.c);
  - Cyber-Stein summons a Fusion monster only: its activation check, its resolve and its list
    (effect_activation.c, effect_resolve1.c, effect_target_collect.c);
  - Senju of the Thousand Hands searches the Deck for a Ritual Magic card, with Sonic Bird's prompt
    (effect_target_collect.c, effect_resolve6.c); apply_gods.py --text 3 rewrites its card text;
  - GameInit moves the Ritual monsters of a save made before the mod from its Deck to its Fusion Deck (main.c).
Idempotent. Stdlib only.
"""
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
MARK = "mod (Extra Deck rituals)"
INCLUDE = '#include "extra_deck_rituals.h"  /* universal-modder: the Ritual monsters in the Extra Deck */\n'
FILES = {"src/extra_deck_rituals.c": "extra_deck_rituals.c", "include/extra_deck_rituals.h": "extra_deck_rituals.h"}
NEW_UNITS = ["extra_deck_rituals"]

# (path, anchor, text, how): how is "after", "replace" or "before:<where>" (insert before <where>, which
# must be inside the anchor).
EDITS = [
    # Filing: Fusion or Ritual instead of Fusion.
    ("src/duel_card_lists.c",
     "    if (CARD_TYPE_IS_MONSTER(CARD_TYPE_C(cardId)) && GetCardKind(cardId) == CARD_KIND_FUSION)\n",
     f"    if (IsExtraDeckMonster(cardId))    /* {MARK}: Fusion or Ritual; was a Fusion-kind test */\n",
     "replace"),
    ("src/duel_piles.c",
     "    if (GetCardKind(card->id) == CARD_KIND_FUSION) {\n",
     f"    if (IsExtraDeckMonster(card->id)) {{    /* {MARK}: was a Fusion-kind test */\n",
     "replace"),
    ("src/duel_cmd_piles.c",
     "        if (GetCardKind(CMD_CARD->id) == CARD_KIND_FUSION) {\n",
     f"        if (IsExtraDeckMonster(CMD_CARD->id)) {{    /* {MARK}: was a Fusion-kind test */\n",
     "replace"),
    ("src/ai_summon.c",
     "        if (kind == CARD_KIND_FUSION) {\n            for (n = PLAYER(player).fusionCount; n > 0; n--)\n",
     f"        if (IsExtraDeckMonster(id)) {{    /* {MARK}: was kind == CARD_KIND_FUSION */\n"
     "            for (n = PLAYER(player).fusionCount; n > 0; n--)\n",
     "replace"),
    ("src/deck_edit_widgets.c",
     "    if (kind == CARD_KIND_FUSION)\n        return 1;\n    return 0;\n}\n",
     f"    if (IsExtraDeckMonster(id))    /* {MARK}: was kind == CARD_KIND_FUSION */\n"
     "        return 1;\n    return 0;\n}\n",
     "replace"),
    ("src/deck_edit_widgets.c",
     "        if (frameKind == CARD_KIND_FUSION) {\n            trunk = (u8 *)&gSaveDeckSizes;\n",
     f"        if (IsExtraDeckMonster(id)) {{    /* {MARK}: the Fusion Deck copies; was a frame-kind test */\n"
     "            trunk = (u8 *)&gSaveDeckSizes;\n",
     "replace"),
    ("src/deck_edit_widgets.c",
     "            if (frameKind == CARD_KIND_FUSION) {\n                u8 *trunk = (u8 *)&gSaveDeckSizes;\n",
     f"            if (IsExtraDeckMonster(id)) {{    /* {MARK}: the Fusion Deck copies; was a frame-kind test */\n"
     "                u8 *trunk = (u8 *)&gSaveDeckSizes;\n",
     "replace"),
    ("src/deck_edit_view.c",
     "                        if (kind != CARD_KIND_FUSION) {\n",
     f"                        if (!IsExtraDeckMonster(card)) {{    /* {MARK}: was kind != CARD_KIND_FUSION */\n",
     "replace"),
    # The Ritual Magic cards: the monster comes from the Fusion Deck.
    ("src/duel_ritual.c",
     "int HandHasRitualMonster(int player, int recipeIdx)\n{\n    u16 i;\n",
     f"    if (FusionDeckHasRitualMonster(player, recipeIdx))    /* {MARK}: or the Fusion Deck */\n"
     "        return 1;\n",
     "after"),
    ("src/duel_ritual.c",
     "    case RITUAL_STEP_TAKE_MONSTER:\n        for (i = 0; i < gDuelPlayers[link->player & 1].handCount; i++) {\n",
     f"        if (TakeRitualMonsterFromFusionDeck(link))    /* {MARK}: the Fusion Deck first */\n"
     "            return RITUAL_STEP_SUMMON;\n",
     "before:        for (i = 0;"),
    # Cyber-Stein: a Fusion monster only.
    ("src/effect_activation.c",
     "        if (players[one & (playerBit >> 31)].fusionCount == 0)\n            goto fail;\n",
     f"        if (CountFusionDeckFusionMonsters(playerBit >> 31) == 0)    /* {MARK}: was fusionCount */\n"
     "            goto fail;\n",
     "replace"),
    ("src/effect_resolve1.c",
     "            case CARD_CYBER_STEIN:\n                if (CountFreeMonsterZones(link->player) == 0)\n"
     "                    return EFFECT_STEP_DONE;\n",
     f"                if (CountFusionDeckFusionMonsters(link->player) == 0)    /* {MARK} */\n"
     "                    return EFFECT_STEP_DONE;\n",
     "after"),
    ("src/effect_target_collect.c",
     "    case CARD_CYBER_STEIN:\n    case CARD_GALE_DOGRA:\n    case CARD_1512:\n",
     f"    case CARD_CYBER_STEIN:    /* {MARK}: its Fusion monsters only */\n"
     "        CollectFusionDeckFusionMonsters(player);\n        break;\n"
     "    case CARD_GALE_DOGRA:\n    case CARD_1512:\n",
     "replace"),
    # Senju of the Thousand Hands: a Ritual Magic card, as Sonic Bird.
    ("src/effect_target_collect.c",
     "        /* Deck Ritual monsters. */\n"
     "        for (i = 0; i < PLAYER(player).deckCount; i++) {\n"
     "            u16 id = CARD_ID(*PILE_WORD_FLAT(gDuelDecks, i, player));\n\n"
     "            if (CARD_TYPE_IS_MONSTER(CardType(id)) && CardKind16(id) == CARD_KIND_RITUAL)\n",
     f"        /* {MARK}: Deck Ritual Magic cards, as Sonic Bird (the Ritual monsters are in the Fusion\n"
     "           Deck now; the original took Deck Ritual monsters). */\n"
     "        for (i = 0; i < PLAYER(player).deckCount; i++) {\n"
     "            u16 id = CARD_ID(*PILE_WORD_FLAT(gDuelDecks, i, player));\n\n"
     "            if (CardType(id) == CARD_TYPE_MAGIC && CardSpellSubtypeNv(id) == SPELL_RITUAL)\n",
     "replace"),
    ("src/effect_resolve6.c",
     "                            gStrSenjuAddRitualMonsterPrompt);\n",
     f"                            gStrSonicBirdAddRitualMagicPrompt);    /* {MARK}: was Senju's own */\n",
     "replace"),
    # Saves from before the mod.
    ("src/main.c",
     "    ReadSram((void *)SRAM, &gSaveData, 0x2170);\n",
     f"    MoveSavedRitualMonsters();    /* {MARK}: a save made before the mod */\n",
     "after"),
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
        sys.exit(f"{path}: anchor found {t.count(anchor)} times (not eds-decomp 857002a after patch_source.py?):\n"
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
    if "\nextra_deck_rituals\n" not in t:
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
