#!/bin/sh
# Build the Egyptian Gods mod from your own Yu-Gi-Oh! The Eternal Duelist Soul ROM (USA, AY5E):
# WORK/gods.gba (the modded ROM) and WORK/gods.bps (the patch, the only thing to share).
#
#   scripts/build.sh <your-rom.gba> <work-dir>
#
# Needs git, python3, and eds-decomp's native toolchain on PATH: run eds-decomp's tools/setup_native.sh once,
# then `. ~/.eds-tools/env.sh` (old_agbcc, arm-none-eabi binutils, pyelftools). flips makes the .bps
# (https://github.com/Alcaro/Flips); without it you still get gods.gba.
set -eu
[ $# -eq 2 ] || { echo "usage: $0 <your-rom.gba> <work-dir>" >&2; exit 2; }
ROM=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
mkdir -p "$2"; WORK=$(cd "$2" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=https://github.com/CosmicScribe64/eds-decomp
COMMIT=857002acd7a2e3ce98afb2992fe9761144308c9a
export EDS_NATIVE=1

# 1. The decomp at the pinned commit, twice: vanilla (original C) and mod (patched C).
[ -d "$WORK/vanilla/.git" ] || git clone -q "$REPO" "$WORK/vanilla"
git -C "$WORK/vanilla" checkout -q --detach "$COMMIT"
[ -d "$WORK/mod" ] || git -C "$WORK/vanilla" worktree add -q --detach "$WORK/mod" "$COMMIT"

# 2. Check and extract your ROM (the decomp refuses anything but USA AY5E, SHA-1 510fbba2...).
mkdir -p "$WORK/vanilla/roms"
cp "$ROM" "$WORK/vanilla/roms/base_eng.gba"
(cd "$WORK/vanilla" && tools/dr make setup)

# 3. The data: stats, passwords, ban list, NPC decks. Both trees get the same assets.
python3 "$HERE/apply_gods.py" "$WORK/vanilla"
rm -rf "$WORK/mod/assets" "$WORK/mod/roms"
cp -a "$WORK/vanilla/assets" "$WORK/mod/assets"
cp -a "$WORK/vanilla/roms" "$WORK/mod/roms"
ln -sf roms/base_eng.gba "$WORK/mod/baserom.gba"

# 4. The code: Divine counts as a monster type, Obelisk stops being a Ritual.
python3 "$HERE/patch_source.py" "$WORK/mod"

# 5. Build both. The vanilla tree keeps the original layout; the mod tree only supplies objects.
for t in vanilla mod; do
    (cd "$WORK/$t" && tools/dr make -j4 >"$WORK/make-$t.log" 2>&1) || { tail -20 "$WORK/make-$t.log"; exit 1; }
    git -C "$WORK/$t" checkout -q -- config/symbols.txt   # rewritten by every build
done

# 6. Hook the changed functions into the original layout.
python3 "$HERE/hookbuild.py" "$WORK/vanilla" "$WORK/mod" "$WORK/gods.gba"

# 7. The patch, checked by applying it back onto your ROM.
if command -v flips >/dev/null 2>&1; then
    flips --create --bps-delta "$ROM" "$WORK/gods.gba" "$WORK/gods.bps" >/dev/null
    flips --apply "$WORK/gods.bps" "$ROM" "$WORK/gods.check.gba" >/dev/null
    cmp "$WORK/gods.gba" "$WORK/gods.check.gba" && rm "$WORK/gods.check.gba"
    echo "patch: $WORK/gods.bps ($(wc -c <"$WORK/gods.bps") bytes)"
fi
sha1sum "$ROM" "$WORK/gods.gba"
