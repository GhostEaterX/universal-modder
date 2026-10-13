#!/usr/bin/env python3
"""Build a modded EDS ROM from eds-decomp without moving any original byte.

eds-decomp matches the ROM byte for byte, but its layout is not relocatable: much of the C reads data
through integer constants (gCardStats at 0x08621DE0, for example), so a code edit that grows one function
shifts every later function and table and breaks those reads. This tool keeps the original layout and
hooks the edited code in instead:

  1. VANILLA is an eds-decomp tree with the original C and the modded assets, built with `make`: the
     original layout with the new data. MOD is the same tree with the edited C, also built.
  2. Units whose src/<unit>.c differ are the edited units. A function counts as changed when its bytes or
     relocations differ between VANILLA/build/src/<unit>.o and MOD/build/src/<unit>.o.
  3. The edited units' objects are linked at --base (past the original 8 MiB), with every symbol they don't
     define taken from VANILLA's ELF (original addresses). Their own globals are made local, so calls
     inside a unit stay in the new copy. A Thumb BL can only reach 4 MiB, so every BL that leaves the blob
     goes through a generated long-branch stub.
  4. The entry of each changed function in VANILLA's ROM is overwritten with a jump to its new copy
     (Thumb `bx pc` -> ARM `ldr ip, [pc]; bx ip`; r0-r3 and lr are untouched).

    hookbuild.py VANILLA MOD OUT.gba [--base 0x08800000] [--pad 0x1000000] [--null]

--null links VANILLA's own objects instead of MOD's: the same hooks, the original code. That ROM must play
exactly like VANILLA's, which tests the hooking itself.

Needs arm-none-eabi binutils on PATH and pyelftools (eds-decomp's tools/setup_native.sh installs both).
"""
import argparse
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

ROM_BASE = 0x08000000
TRAMP_ALIGNED = bytes.fromhex("7847" "c046" "00c09fe5" "1cff2fe1")  # bx pc; nop; ldr ip,[pc]; bx ip
TRAMP_UNALIGNED = bytes.fromhex("c046") + TRAMP_ALIGNED[:2] + bytes.fromhex("c046") + TRAMP_ALIGNED[4:]
THUMB_BL = "R_ARM_THM_CALL"


def run(*cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"failed: {' '.join(map(str, cmd))}\n{r.stdout}{r.stderr}")
    return r.stdout


def units_of(tree):
    out = []
    for line in (tree / "units.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line and not line.startswith("@") and (tree / "src" / f"{line}.c").exists():
            out.append(line)
    return out


def functions(obj):
    """{name: (offset, size)} of the .text functions in an object (offsets without the Thumb bit)."""
    with open(obj, "rb") as f:
        elf = ELFFile(f)
        text = elf.get_section_index(".text")
        out = {}
        for s in elf.get_section_by_name(".symtab").iter_symbols():
            if s["st_info"]["type"] == "STT_FUNC" and s["st_shndx"] == text:
                out[s.name] = (s["st_value"] & ~1, s["st_size"])
        return out


def text_and_relocs(obj):
    """(.text bytes, [(offset, type, symbol name or section+addend-free)])."""
    with open(obj, "rb") as f:
        elf = ELFFile(f)
        data = elf.get_section_by_name(".text").data()
        symtab = elf.get_section_by_name(".symtab")
        relocs = []
        for sec in elf.iter_sections():
            if isinstance(sec, RelocationSection) and sec.name == ".rel.text":
                for r in sec.iter_relocations():
                    sym = symtab.get_symbol(r["r_info_sym"])
                    name = sym.name if sym["st_info"]["type"] != "STT_SECTION" else f"<sect {sym['st_shndx']}>"
                    relocs.append((r["r_offset"], r.entry["r_info_type"], name))
        return data, relocs


def changed_functions(vobj, mobj):
    vf, mf = functions(vobj), functions(mobj)
    vt, vr = text_and_relocs(vobj)
    mt, mr = text_and_relocs(mobj)
    changed = []
    for name, (voff, vsize) in vf.items():
        if name not in mf:
            changed.append(name)        # gone from MOD: keep it hooked to be safe (should not happen)
            continue
        moff, msize = mf[name]
        vb, mb = vt[voff:voff + vsize], mt[moff:moff + msize]
        vrel = [(o - voff, t, n) for o, t, n in vr if voff <= o < voff + vsize]
        mrel = [(o - moff, t, n) for o, t, n in mr if moff <= o < moff + msize]
        # REL relocations keep their addends in the bytes: blank the relocated words before comparing.
        def blank(b, rel):
            b = bytearray(b)
            for o, _, _ in rel:
                b[o:o + 4] = b"\0\0\0\0"
            return bytes(b)
        if vsize != msize or vrel != mrel or blank(vb, vrel) != blank(mb, mrel):
            changed.append(name)
    return changed


def map_text_bases(map_file):
    """{object path suffix: .text address} from a GNU ld map."""
    bases = {}
    for m in re.finditer(r"^ \.text\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S+\.o)$", map_file.read_text(), re.M):
        bases[Path(m.group(3)).name] = int(m.group(1), 16)
    return bases


def bl_targets(obj):
    """Undefined symbols that the object reaches with a Thumb BL."""
    with open(obj, "rb") as f:
        elf = ELFFile(f)
        symtab = elf.get_section_by_name(".symtab")
        out = set()
        for sec in elf.iter_sections():
            if isinstance(sec, RelocationSection):
                for r in sec.iter_relocations():
                    sym = symtab.get_symbol(r["r_info_sym"])
                    if r.entry["r_info_type"] == 10 and sym["st_shndx"] == "SHN_UNDEF":   # R_ARM_THM_CALL
                        out.add(sym.name)
        return out


def defined_globals(obj):
    with open(obj, "rb") as f:
        elf = ELFFile(f)
        return sorted(s.name for s in elf.get_section_by_name(".symtab").iter_symbols()
                      if s.name and s["st_info"]["bind"] == "STB_GLOBAL" and s["st_shndx"] != "SHN_UNDEF")


def localize_all(obj, work):
    """Make every symbol the object defines local, so the -R symbols of VANILLA can't clash with it."""
    names = defined_globals(obj)
    if names:
        lst = work / "localize.txt"
        lst.write_text("\n".join(names) + "\n")
        run("arm-none-eabi-objcopy", f"--localize-symbols={lst}", str(obj))
    if defined_globals(obj):
        sys.exit(f"{obj}: could not localize its symbols")


def symbol_values(elf_path):
    with open(elf_path, "rb") as f:
        elf = ELFFile(f)
        return {s.name: s["st_value"] for s in elf.get_section_by_name(".symtab").iter_symbols()
                if s.name and s["st_shndx"] != "SHN_UNDEF" and s["st_info"]["bind"] == "STB_GLOBAL"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vanilla", type=Path)
    ap.add_argument("mod", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x08800000)
    ap.add_argument("--pad", type=lambda s: int(s, 0), default=0x1000000, help="pad the ROM to this size with 0xFF")
    ap.add_argument("--null", action="store_true", help="link VANILLA's objects (hook test)")
    ap.add_argument("--work", type=Path, help="scratch directory (default: OUT.hookbuild/)")
    args = ap.parse_args()
    van, mod = args.vanilla.resolve(), args.mod.resolve()
    work = (args.work or args.out.with_suffix(".hookbuild")).resolve()
    shutil.rmtree(work, ignore_errors=True)
    (work / "objs").mkdir(parents=True)

    rom = bytearray((van / "eds.gba").read_bytes())
    vsyms = symbol_values(van / "build" / "eds.elf")
    vbases = map_text_bases(van / "build" / "eds.map")

    units = [u for u in units_of(mod) if (van / "src" / f"{u}.c").read_bytes() != (mod / "src" / f"{u}.c").read_bytes()]
    hooks = {}      # unit -> [function]
    for u in units:
        hooks[u] = changed_functions(van / "build" / "src" / f"{u}.o", mod / "build" / "src" / f"{u}.o")
    nhooks = sum(map(len, hooks.values()))
    print(f"{len(units)} edited units, {nhooks} changed functions")

    # Objects for the blob: localize their globals, route outgoing BLs through stubs.
    stubs = set()
    for u in units:
        src = (van if args.null else mod) / "build" / "src" / f"{u}.o"
        dst = work / "objs" / f"{u}.o"
        targets = bl_targets(src)
        stubs |= targets
        redefs = [f"--redefine-sym={t}=__hookstub_{t}" for t in sorted(targets)]
        run("arm-none-eabi-objcopy", *redefs, str(src), str(dst))
        localize_all(dst, work)

    lines = ["\t.text", "\t.syntax unified"]
    for t in sorted(stubs):
        if t not in vsyms:
            sys.exit(f"BL target {t} is not in VANILLA's ELF")
        lines += ["\t.align 2, 0", "\t.thumb", f"\t.global __hookstub_{t}", f"__hookstub_{t}:", "\tbx pc", "\tnop", "\t.arm",
                  "\tldr ip, [pc]", "\tbx ip", f"\t.word 0x{vsyms[t] | 1:08X}"]
    (work / "stubs.s").write_text("\n".join(lines) + "\n")
    run("arm-none-eabi-as", "-mcpu=arm7tdmi", "-mthumb-interwork", "-o", str(work / "stubs.o"), str(work / "stubs.s"))

    objs = " ".join(f"objs/{u}.o(.text)" for u in units)
    (work / "hook.ld").write_text(f"""OUTPUT_ARCH(arm)
SECTIONS
{{
    . = 0x{args.base:08X};
    .text : {{ stubs.o(.text) {objs} }}
    /DISCARD/ : {{ *(.comment) *(.note*) *(.ARM.attributes) }}
}}
""")
    run("arm-none-eabi-ld", "-T", "hook.ld", "-R", str(van / "build" / "eds.elf"), "-Map", "blob.map",
        "-o", "blob.elf", cwd=work)
    for sec in ("data", "bss", "rodata"):
        out = run("arm-none-eabi-size", "-A", str(work / "blob.elf"))
        if re.search(rf"^\.{sec}\s+[1-9]", out, re.M):
            sys.exit(f"blob has a .{sec} section: an edited unit defines data, which this tool cannot move")
    run("arm-none-eabi-objcopy", "-O", "binary", "-j", ".text", "blob.elf", "blob.bin", cwd=work)
    blob = (work / "blob.bin").read_bytes()
    bbases = map_text_bases(work / "blob.map")

    # Trampolines.
    report = []
    for u in units:
        vfun = functions(van / "build" / "src" / f"{u}.o")
        bfun = functions(work / "objs" / f"{u}.o")
        for name in hooks[u]:
            voff, vsize = vfun[name]
            orig = vbases[f"{u}.o"] + voff
            new = bbases[f"{u}.o"] + bfun[name][0]
            tramp = TRAMP_ALIGNED if orig % 4 == 0 else TRAMP_UNALIGNED
            if vsize < len(tramp) + 4:
                sys.exit(f"{u}:{name} is {vsize} bytes, too small for a {len(tramp) + 4}-byte jump")
            code = tramp + struct.pack("<I", new | 1)
            o = orig - ROM_BASE
            rom[o:o + len(code)] = code
            report.append(f"{u}\t{name}\t0x{orig:08X}\t0x{new:08X}\t{vsize}")

    start = args.base - ROM_BASE
    if len(rom) > start:
        sys.exit("VANILLA's ROM already reaches --base")
    rom += b"\xFF" * (start - len(rom)) + blob
    if args.pad and len(rom) < args.pad:
        rom += b"\xFF" * (args.pad - len(rom))
    args.out.write_bytes(rom)
    (work / "hooks.tsv").write_text("unit\tfunction\toriginal\tnew\toriginal_size\n" + "\n".join(report) + "\n")
    print(f"blob {len(blob)} bytes at 0x{args.base:08X}, {len(stubs)} stubs, {len(report)} hooks -> {args.out}"
          + (" (null: original code)" if args.null else ""))


if __name__ == "__main__":
    main()
