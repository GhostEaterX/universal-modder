#!/usr/bin/env python3
"""Apply the C side of the Egyptian Gods mod to an eds-decomp checkout (commit 857002a).

    python3 patch_source.py <eds-decomp checkout> [--check]

The changes are made by rule rather than shipped as a diff, so this repo carries no decompiled source:
  1. include/constants/card_stats.h gets CARD_TYPE_IS_MONSTER(type): type <= Reptile, or Divine (24).
  2. Every `X <= CARD_TYPE_REPTILE` / `X > CARD_TYPE_REPTILE` (and CARD_TYPE_LAST_MONSTER) in src/ becomes
     CARD_TYPE_IS_MONSTER(X) / !CARD_TYPE_IS_MONSTER(X). One display test is left alone: the Card View
     attribute icon (title_menu.c), where Divine already has its own icon case.
  3. In the gameplay copies of the card-kind classifier, Obelisk stops being a Ritual monster and falls
     through to Slifer's and Ra's Effect kind. The frame-drawing copies keep Ritual, so Obelisk keeps its blue
     frame; card_detail.c serves both, so its two gameplay users special-case Obelisk instead.
  4. Card View prints "This is not able to play." for the Tickets only.
Idempotent: a patched tree reports 0 changes. Stdlib only.
"""
import argparse
import re
import sys
from pathlib import Path

EXPECTED_REWRITES = 85
OP_ANY = re.compile(r"(<=|>)[ \t]*(CARD_TYPE_REPTILE|CARD_TYPE_LAST_MONSTER)\b")
KEEP = [("title_menu.c", "attr <= ATTRIBUTE_WIND && CARD_TYPE(cardId) <= CARD_TYPE_REPTILE")]
CASTS = {"u8", "u16", "u32", "s8", "s16", "s32", "int"}
HIGHER = (">>", "<<", "+", "-", "*", "/", "%")       # binary operators that bind tighter than <= and >
KIND_UNITS = ["effect_activation", "summon_builders", "effect_fusion", "duel_ritual", "ai_summon",
              "effect_target_collect", "duel_piles", "duel_cmd_piles", "effect_checks", "duel_card_lists",
              "summon_checks"]
KIND_NOTE = "  /* mod: a playable God is an Effect monster (frames keep Obelisk's Ritual blue) */"
KIND = re.compile(r"(case CARD_OBELISK_THE_TORMENTOR:)\n[ \t]*(?:return CARD_KIND_RITUAL;|kind = CARD_KIND_RITUAL;\n"
                  r"[ \t]*break;)\n(?=[ \t]*case CARD_SLIFER_THE_SKY_DRAGON:)")
PREDICATE = """
/* Mod (playable Egyptian Gods): a card type that is a monster. The original code tests type <= CARD_TYPE_REPTILE
 * everywhere, which leaves the Divine cards out; every such test now goes through this. */
#define CARD_TYPE_IS_MONSTER(type) ((u32)(type) <= CARD_TYPE_REPTILE || (u32)(type) == CARD_TYPE_DIVINE)
"""
GOD_NOTE = "    /* mod: Ritual only for its frame */"


def skip_ws(t, i):
    while i > 0 and t[i - 1] in " \t\n":
        i -= 1
    return i


def primary_start(t, end):
    """Start of the primary expression (call, macro, member access, parenthesized group, cast) ending at end."""
    i = skip_ws(t, end)
    while True:
        if i > 0 and t[i - 1] == ")":
            depth, j = 0, i - 1
            while j >= 0:
                depth += {")": 1, "(": -1}.get(t[j], 0)
                if depth == 0:
                    break
                j -= 1
            i = j
        while i > 0 and (t[i - 1].isalnum() or t[i - 1] in "_.[]" or t[i - 2:i] == "->"):
            i -= 2 if t[i - 2:i] == "->" else 1
        k = skip_ws(t, i)
        m = re.search(r"\((\w+)\)$", t[:k])
        if m and m.group(1) in CASTS:
            i = m.start()
            continue
        return i


def operand_start(t, end):
    i = primary_start(t, end)
    while True:
        k = skip_ws(t, i)
        for op in HIGHER:
            if t[k - len(op):k] == op and t[k - len(op) - 1:k - len(op)] not in "<>=!&|-+":
                i = primary_start(t, k - len(op))
                break
        else:
            return i


def rewrite_types(path):
    t = path.read_text()
    out, pos, n = [], 0, 0
    for m in OP_ANY.finditer(t):
        line_start = t.rfind("\n", 0, m.start()) + 1
        line = t[line_start:t.find("\n", m.end())]
        if line.lstrip().startswith(("*", "/*")) or any(path.name == f and s in line for f, s in KEEP):
            continue
        end = skip_ws(t, m.start())
        start = operand_start(t, end)
        operand = t[start:end]
        if not operand.strip() or start < pos:
            sys.exit(f"{path.name}: cannot find the operand before {m.group(0)!r} near: {line.strip()}")
        neg = "!" if m.group(1) == ">" else ""
        out.append(t[pos:start] + f"{neg}CARD_TYPE_IS_MONSTER({operand.strip()})")
        pos = m.end()
        n += 1
    out.append(t[pos:])
    return "".join(out), n


def edit_once(text, old, new, what):
    if new in text:
        return text, 0
    if text.count(old) != 1:
        sys.exit(f"{what}: expected one match, found {text.count(old)} (not eds-decomp 857002a?)")
    return text.replace(old, new), 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("decomp", type=Path)
    ap.add_argument("--check", action="store_true", help="report only")
    args = ap.parse_args()
    root = args.decomp
    writes = {}

    hdr = root / "include" / "constants" / "card_stats.h"
    t = hdr.read_text()
    if "CARD_TYPE_IS_MONSTER" not in t:
        anchor = "    CARD_TYPE_DIVINE = 24,      /* the three Egyptian God cards */\n};\n"
        t, _ = edit_once(t, anchor, anchor + PREDICATE, "card_stats.h enum")
        writes[hdr] = t

    total = 0
    for path in sorted((root / "src").glob("*.c")):
        t, n = rewrite_types(path)
        if n:
            writes[path] = t
            total += n
    if total not in (0, EXPECTED_REWRITES):
        sys.exit(f"{total} monster-type tests found, expected {EXPECTED_REWRITES} (not eds-decomp 857002a?)")

    kinds = 0
    for unit in KIND_UNITS:
        path = root / "src" / f"{unit}.c"
        t = writes.get(path, path.read_text())
        t, n = KIND.subn(lambda m: m.group(1) + KIND_NOTE + "\n", t)
        if n:
            writes[path] = t
            kinds += n
    if kinds not in (0, 12):
        sys.exit(f"{kinds} Obelisk kind cases changed, expected 12")

    path = root / "src" / "card_detail.c"
    t = writes.get(path, path.read_text())
    t, a = edit_once(t, "    switch (CARD_NUMBER(cardId)) {\n    case CARD_RELINQUISHED:",
                     "    switch (CARD_NUMBER(cardId)) {\n    case CARD_OBELISK_THE_TORMENTOR:" + GOD_NOTE +
                     "\n    case CARD_RELINQUISHED:", "IsEffectMonster")
    t, b = edit_once(t, "        return 0;\n    kind = GetCardKind(cardId);",
                     "        return 0;\n    if (CARD_NUMBER(cardId) == CARD_OBELISK_THE_TORMENTOR)" + GOD_NOTE +
                     "\n        return 0;\n    kind = GetCardKind(cardId);", "IsSpecialSummonOnly")
    if a or b:
        writes[path] = t
    path = root / "src" / "title_menu.c"
    t = writes.get(path, path.read_text())
    t, c = edit_once(t, "        if (CARD_TYPE(cardId) > CARD_TYPE_MAGIC)\n",
                     "        if (CARD_TYPE(cardId) == CARD_TYPE_TICKET)    /* mod: the Gods are playable */\n",
                     "Card View text")
    if c:
        writes[path] = t

    print(f"{'would change' if args.check else 'changed'} {len(writes)} files: {total} monster-type tests, "
          f"{kinds} Obelisk kind cases, {a + b} card_detail edits, {c} Card View edit")
    if not args.check:
        for path, text in writes.items():
            path.write_text(text)


if __name__ == "__main__":
    main()
