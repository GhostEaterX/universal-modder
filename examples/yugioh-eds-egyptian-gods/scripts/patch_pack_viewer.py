#!/usr/bin/env python3
"""Add the pack viewer to the pick-a-pack screen. Runs on eds-decomp 857002a (after the Gods' scripts in the
gods-3t-fx build; it doesn't depend on them).

    python3 patch_pack_viewer.py <eds-decomp checkout> [--check]

The viewer is this mod's own code, in ../src: pack_viewer.c and pack_viewer.h. This script copies them into
the tree as a new unit, writes include/pack_viewer_data.h (the odds table, from the tree's own
assets/tables/rodata2/booster_packs.json, by gen_pack_odds.py), and makes the anchored edits that connect
them to the pick screen:
  - PackList_HandleInput: SELECT opens the viewer for the centre pack;
  - GetPack_SelectAndGenerate: the viewer runs on sub-states 0x20 and up, and gets the centre pack on SELECT;
  - PackList_Init: back from the viewer, the list starts with the same pack in the centre;
  - PackList_DrawCovers: the centre pack's name and the SELECT hint in the bottom band;
  - GetPack_DrawCardRow: in the viewer, a canvas clear of the row's tiles instead of all 64 KB (5 rows at
    once would take 15 frames); the opening scene keeps TextCanvasInit.
Idempotent. Stdlib only.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
MARK = "mod (pack viewer)"
INCLUDE = '#include "pack_viewer.h"         /* universal-modder: the pack viewer */\n'
FILES = {"src/pack_viewer.c": "pack_viewer.c", "include/pack_viewer.h": "pack_viewer.h"}
NEW_UNITS = ["pack_viewer"]
DATA = "include/pack_viewer_data.h"
PACKS_JSON = "assets/tables/rodata2/booster_packs.json"

# (path, anchor, text, how): how is "after", "replace" or "before:<where>" (insert before <where>, which
# must be inside the anchor).
EDITS = [
    ("src/deck_edit_panel.c",
     "    if (gMain.newKeys & A_BUTTON) {\n        PlaySE(SE_CONFIRM);\n        return 1;\n    }\n    return 0;\n}\n",
     f"""    if ((gMain.newKeys & SELECT_BUTTON) && gSceneWork.slideFrame == 0) {{     /* {MARK} */
        PlaySE(SE_CONFIRM);
        return PACKVIEW_OPEN;
    }}
""", "before:    return 0;\n}\n"),
    ("src/deck_edit_panel.c",
     "        s->firstIndex = s->packCount - 1;\n",
     f"        s->firstIndex = PackView_ListStart(s->packCount - 1);   /* {MARK}: keep the centre pack */\n",
     "replace"),
    ("src/booster_pack.c",
     '    __asm__ __volatile__("" : : "r"(state));\n    switch (*state) {\n',
     f"""    if (*state >= PACKVIEW_STATE_FIRST)     /* {MARK} */
        return PackView_Run();
""", "before:    switch (*state) {\n"),
    ("src/booster_pack.c",
     "    case 2:\n        result = PackList_HandleInputInt();\n        goto check;\n",
     f"""    case 2:
        result = PackList_HandleInputInt();
        if ((u16)result == PACKVIEW_OPEN) {{     /* {MARK}: SELECT */
            PackView_Open();
            return 0;
        }}
        goto check;
""", "replace"),
    ("src/card_canvas.c",
     "    TextCanvasInit(0x18, 2);\n",
     f"    PackView_CanvasInit(0x18, 2);     /* {MARK}: TextCanvasInit outside the viewer */\n", "replace"),
    ("src/booster_get_pack.c",
     "        sel++;\n        sel %= *cnt;\n    }\n",
     f"    PackView_DrawPickName();     /* {MARK}: the centre pack's name */\n",
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
    if "\npack_viewer\n" not in t:
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
        # the odds table, from this tree's pack lists (rewritten only when it changes)
        subprocess.run([sys.executable, str(HERE / "gen_pack_odds.py"), str(root / PACKS_JSON),
                        str(root / DATA)], check=True)
    return changed, len(copies)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("decomp", type=Path)
    ap.add_argument("--check", action="store_true", help="report only")
    args = ap.parse_args()
    root = args.decomp
    if not (root / PACKS_JSON).exists():
        sys.exit(f"{root / PACKS_JSON} is missing: run eds-decomp's `make setup` on your ROM first")
    n, copied = apply(root, args.check)
    print(f"{'would apply' if args.check else 'applied'} {n} edits, {copied} new files"
          + (" (already applied)" if n == 0 and copied == 0 else ""))


if __name__ == "__main__":
    main()
