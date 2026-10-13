#!/usr/bin/env python3
"""Check the relocated effect table of an effects build (patch_god_effects.py), after hookbuild.py.

    check_effect_table.py VANILLA OUT.gba [--work OUT.hookbuild]

Every card's effect goes through this table, so the build stops unless:
  - the first 426 rows of gCardEffectsMod equal the original table at gCardEffects, byte for byte;
  - the rows after them are the Gods' (1910, 1912), the numbers stay sorted for FindCardEffect, and every
    handler pointer is 0 or a Thumb address;
  - every original function that reads gCardEffects (or its alias gAlias_0819A9D4) is hooked, so none of
    them still reads the old table.
Needs pyelftools (eds-decomp's tools/setup_native.sh installs it).
"""
import argparse
import bisect
import struct
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

ROM_BASE = 0x08000000
ROW = 0x18
ORIGINAL_ROWS = 426
GOD_ROWS = (1910, 1912)
TABLE_NAMES = {"gCardEffects", "gAlias_0819A9D4"}


def symbol(elf_path, name):
    with open(elf_path, "rb") as f:
        for s in ELFFile(f).get_section_by_name(".symtab").iter_symbols():
            if s.name == name:
                return s["st_value"]
    sys.exit(f"{elf_path}: no symbol {name}")


def table_readers(objs):
    """{(unit, function)} of the functions with a relocation against the original table."""
    out = set()
    for obj in objs:
        with open(obj, "rb") as f:
            elf = ELFFile(f)
            symtab = elf.get_section_by_name(".symtab")
            funcs = sorted((s["st_value"] & ~1, s.name) for s in symtab.iter_symbols()
                           if s["st_info"]["type"] == "STT_FUNC")
            starts = [a for a, _ in funcs]
            for sec in elf.iter_sections():
                if isinstance(sec, RelocationSection) and sec.name == ".rel.text":
                    for r in sec.iter_relocations():
                        if symtab.get_symbol(r["r_info_sym"]).name in TABLE_NAMES:
                            i = bisect.bisect_right(starts, r["r_offset"]) - 1
                            out.add((obj.stem, funcs[i][1] if i >= 0 else "?"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vanilla", type=Path)
    ap.add_argument("rom", type=Path)
    ap.add_argument("--work", type=Path, help="hookbuild.py's scratch directory (default: ROM.hookbuild/)")
    args = ap.parse_args()
    work = args.work or args.rom.with_suffix(".hookbuild")
    rom = args.rom.read_bytes()
    errors = []

    old = symbol(args.vanilla / "build" / "eds.elf", "gCardEffects") - ROM_BASE
    new = symbol(work / "blob.elf", "gCardEffectsMod") - ROM_BASE
    rows = ORIGINAL_ROWS + len(GOD_ROWS)
    if rom[new:new + ORIGINAL_ROWS * ROW] != rom[old:old + ORIGINAL_ROWS * ROW]:
        errors.append("the first 426 rows of gCardEffectsMod differ from gCardEffects")
    numbers = []
    for i in range(rows):
        number, flags, *handlers = struct.unpack_from("<HH5I", rom, new + i * ROW)
        numbers.append(number)
        if flags:
            errors.append(f"row {i} (card {number}): flags {flags}")
        for h in handlers:
            if h and (not h & 1 or not ROM_BASE <= h < ROM_BASE + len(rom)):
                errors.append(f"row {i} (card {number}): handler 0x{h:08X} is not a Thumb address in the ROM")
    if tuple(numbers[ORIGINAL_ROWS:]) != GOD_ROWS:
        errors.append(f"the added rows are {numbers[ORIGINAL_ROWS:]}, expected {list(GOD_ROWS)}")
    if numbers != sorted(numbers) or len(set(numbers)) != rows:
        errors.append("the rows are not sorted by card number")

    hooks = set()
    for line in (work / "hooks.tsv").read_text().splitlines()[1:]:
        unit, function = line.split("\t")[:2]
        hooks.add((unit, function))
    readers = table_readers(sorted((args.vanilla / "build" / "src").glob("*.o")))
    for unit, function in sorted(readers - hooks):
        errors.append(f"{unit}:{function} reads the original table and is not hooked")

    if errors:
        sys.exit("effect table check failed:\n  " + "\n  ".join(errors))
    print(f"effect table: {rows} rows at 0x{new + ROM_BASE:08X}, the first {ORIGINAL_ROWS} identical to "
          f"0x{old + ROM_BASE:08X}; all {len(readers)} readers of the old table hooked")


if __name__ == "__main__":
    main()
