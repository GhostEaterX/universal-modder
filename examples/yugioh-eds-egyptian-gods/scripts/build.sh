#!/bin/sh
# Build the Egyptian Gods mod from your own Yu-Gi-Oh! The Eternal Duelist Soul ROM (USA, AY5E).
#
#   scripts/build.sh <your-rom.gba> <work-dir> [--tributes 2|3]
#
#   --tributes 2 (default): the Gods take EDS's two Tributes  -> WORK/gods.gba    + WORK/gods.bps
#   --tributes 3:           the Gods take three (TCG rule)    -> WORK/gods-3t.gba + WORK/gods-3t.bps
# The .bps is the only thing to share. Both variants can live in the same work dir.
#
# Needs git, python3, and eds-decomp's native toolchain on PATH: run eds-decomp's tools/setup_native.sh once,
# then `. ~/.eds-tools/env.sh` (old_agbcc, arm-none-eabi binutils, pyelftools). flips makes the .bps
# (https://github.com/Alcaro/Flips); without it you still get the .gba.
set -eu
usage() { echo "usage: $0 <your-rom.gba> <work-dir> [--tributes 2|3]" >&2; exit 2; }
[ $# -eq 2 ] || [ $# -eq 4 ] || usage
TRIBUTES=2
if [ $# -eq 4 ]; then
    [ "$3" = "--tributes" ] || usage
    case "$4" in 2|3) TRIBUTES=$4 ;; *) usage ;; esac
fi
ROM=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
mkdir -p "$2"; WORK=$(cd "$2" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=https://github.com/CosmicScribe64/eds-decomp
COMMIT=857002acd7a2e3ce98afb2992fe9761144308c9a
if [ "$TRIBUTES" = 3 ]; then MOD=mod3; OUT=gods-3t; else MOD=mod; OUT=gods; fi
export EDS_NATIVE=1

# 1. The decomp at the pinned commit: vanilla (original C) and one mod tree per variant (patched C).
[ -d "$WORK/vanilla/.git" ] || git clone -q "$REPO" "$WORK/vanilla"
git -C "$WORK/vanilla" checkout -q --detach "$COMMIT"
[ -d "$WORK/$MOD" ] || git -C "$WORK/vanilla" worktree add -q --detach "$WORK/$MOD" "$COMMIT"

# 2. Check and extract your ROM (the decomp refuses anything but USA AY5E, SHA-1 510fbba2...).
mkdir -p "$WORK/vanilla/roms"
cp "$ROM" "$WORK/vanilla/roms/base_eng.gba"
(cd "$WORK/vanilla" && tools/dr make setup)

# 3. The data: stats, passwords, ban list, NPC decks. Both trees get the same assets.
python3 "$HERE/apply_gods.py" "$WORK/vanilla"
rm -rf "$WORK/$MOD/assets" "$WORK/$MOD/roms"
cp -a "$WORK/vanilla/assets" "$WORK/$MOD/assets"
cp -a "$WORK/vanilla/roms" "$WORK/$MOD/roms"
ln -sf roms/base_eng.gba "$WORK/$MOD/baserom.gba"

# 4. The code: Divine counts as a monster type, Obelisk stops being a Ritual; optionally three Tributes.
python3 "$HERE/patch_source.py" "$WORK/$MOD"
[ "$TRIBUTES" = 3 ] && python3 "$HERE/patch_three_tributes.py" "$WORK/$MOD"

# 5. Build both. The vanilla tree keeps the original layout; the mod tree only supplies objects.
for t in vanilla "$MOD"; do
    (cd "$WORK/$t" && tools/dr make -j4 >"$WORK/make-$t.log" 2>&1) || { tail -20 "$WORK/make-$t.log"; exit 1; }
    git -C "$WORK/$t" checkout -q -- config/symbols.txt   # rewritten by every build
done

# 6. Hook the changed functions into the original layout.
python3 "$HERE/hookbuild.py" "$WORK/vanilla" "$WORK/$MOD" "$WORK/$OUT.gba"

# 7. The patch, checked by applying it back onto your ROM.
if command -v flips >/dev/null 2>&1; then
    flips --create --bps-delta "$ROM" "$WORK/$OUT.gba" "$WORK/$OUT.bps" >/dev/null
    flips --apply "$WORK/$OUT.bps" "$ROM" "$WORK/$OUT.check.gba" >/dev/null
    cmp "$WORK/$OUT.gba" "$WORK/$OUT.check.gba" && rm "$WORK/$OUT.check.gba"
    echo "patch: $WORK/$OUT.bps ($(wc -c <"$WORK/$OUT.bps") bytes)"
fi
sha1sum "$ROM" "$WORK/$OUT.gba"
