#!/usr/bin/env python3
"""Switch on the Tier 1 duelists' second decks, in the three-Tribute effects build. Runs on eds-decomp 857002a
(after the Gods' scripts in the gods-3t-fx build; it doesn't depend on them).

    python3 patch_second_decks.py <eds-decomp checkout> [--check]

The rule is this mod's own code, in ../src: second_decks.c and second_decks.h. This script copies them into
the tree as a new unit and makes the one edit that connects them to the engine:
  - Campaign_SetupDuel: LoadOpponentDeck gets OpponentUsesSecondDeck() instead of 0, so Yugi, Tea, Joey,
    Tristan and Bakura play their second deck (gOpponentAltDecks, never loaded by the original game) once the
    player has beaten them 10 times.
Idempotent. Stdlib only.
"""
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
MARK = "mod (second decks)"
INCLUDE = '#include "second_decks.h"        /* universal-modder: the Tier 1 duelists\' second decks */\n'
FILES = {"src/second_decks.c": "second_decks.c", "include/second_decks.h": "second_decks.h"}
NEW_UNITS = ["second_decks"]

# (path, anchor, text, how): how is "after", "replace" or "before:<where>" (insert before <where>, which
# must be inside the anchor).
EDITS = [
    ("src/campaign_steps.c",
     "    ShuffleDeck(0, 8);\n    LoadOpponentDeck(0);\n",
     f"    ShuffleDeck(0, 8);\n    LoadOpponentDeck(OpponentUsesSecondDeck());    /* {MARK}: 0 in the original */\n",
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
        sys.exit(f"{path}: anchor found {t.count(anchor)} times (not eds-decomp 857002a?):\n{anchor[:120]}")
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
    if "\nsecond_decks\n" not in t:
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
