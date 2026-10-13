#!/bin/sh
# Build the Egyptian Gods mod from your own Yu-Gi-Oh! The Eternal Duelist Soul ROM (USA, AY5E).
#
#   scripts/build.sh <your-rom.gba> <work-dir> [--tributes 2|3] [--effects]
#
#   --tributes 2 (default): the Gods take EDS's two Tributes  -> WORK/gods.gba    + WORK/gods.bps
#   --tributes 3:           the Gods take three (TCG rule)    -> WORK/gods-3t.gba + WORK/gods-3t.bps
#   --effects:              add the Gods' effects and text    -> WORK/gods-fx.*, WORK/gods-3t-fx.*
# gods-3t-fx (--tributes 3 --effects) also gets the pack viewer: on the pick-a-pack screen after a duel,
# SELECT lists the centre pack's cards and each card's chance of being in the pack.
# The .bps is the only thing to share. All four variants can live in the same work dir.
#
# Needs git, python3, and eds-decomp's native toolchain on PATH: run eds-decomp's tools/setup_native.sh once,
# then `. ~/.eds-tools/env.sh` (old_agbcc, arm-none-eabi binutils, pyelftools). flips makes the .bps
# (https://github.com/Alcaro/Flips); without it you still get the .gba.
set -eu
usage() { echo "usage: $0 <your-rom.gba> <work-dir> [--tributes 2|3] [--effects]" >&2; exit 2; }
[ $# -ge 2 ] || usage
ROM=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
mkdir -p "$2"; WORK=$(cd "$2" && pwd)
shift 2
TRIBUTES=2
EFFECTS=0
while [ $# -gt 0 ]; do
    case "$1" in
        --tributes) [ $# -ge 2 ] || usage; case "$2" in 2|3) TRIBUTES=$2 ;; *) usage ;; esac; shift 2 ;;
        --effects) EFFECTS=1; shift ;;
        *) usage ;;
    esac
done
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=https://github.com/CosmicScribe64/eds-decomp
COMMIT=857002acd7a2e3ce98afb2992fe9761144308c9a
if [ "$TRIBUTES" = 3 ]; then MOD=mod3; OUT=gods-3t; else MOD=mod; OUT=gods; fi
if [ "$EFFECTS" = 1 ]; then MOD=$MOD-fx; OUT=$OUT-fx; TEXT="--text $TRIBUTES"; else TEXT=; fi
export EDS_NATIVE=1

# 1. The decomp at the pinned commit: vanilla (original C) and one mod tree per variant (patched C).
[ -d "$WORK/vanilla/.git" ] || git clone -q "$REPO" "$WORK/vanilla"
git -C "$WORK/vanilla" checkout -q --detach "$COMMIT"
[ -d "$WORK/$MOD" ] || git -C "$WORK/vanilla" worktree add -q --detach "$WORK/$MOD" "$COMMIT"

# 2. Check and extract your ROM (the decomp refuses anything but USA AY5E, SHA-1 510fbba2...).
mkdir -p "$WORK/vanilla/roms"
cp "$ROM" "$WORK/vanilla/roms/base_eng.gba"
(cd "$WORK/vanilla" && tools/dr make setup)

# 3. The data: stats, passwords, ban list, NPC decks (and with --effects the Gods' card text). Both trees get
#    the same assets.
# shellcheck disable=SC2086
python3 "$HERE/apply_gods.py" "$WORK/vanilla" $TEXT
rm -rf "$WORK/$MOD/assets" "$WORK/$MOD/roms"
cp -a "$WORK/vanilla/assets" "$WORK/$MOD/assets"
cp -a "$WORK/vanilla/roms" "$WORK/$MOD/roms"
ln -sf roms/base_eng.gba "$WORK/$MOD/baserom.gba"

# 4. The code: Divine counts as a monster type, Obelisk stops being a Ritual; optionally three Tributes and
#    the Gods' effects (two new units, src/god_effects.c and data/god_effects_table.s), and for gods-3t-fx
#    the pack viewer (src/pack_viewer.c, with its odds table generated from your booster_packs.json).
python3 "$HERE/patch_source.py" "$WORK/$MOD"
if [ "$TRIBUTES" = 3 ]; then python3 "$HERE/patch_three_tributes.py" "$WORK/$MOD"; fi
if [ "$EFFECTS" = 1 ]; then python3 "$HERE/patch_god_effects.py" "$WORK/$MOD"; fi
if [ "$TRIBUTES" = 3 ] && [ "$EFFECTS" = 1 ]; then python3 "$HERE/patch_pack_viewer.py" "$WORK/$MOD"; fi

# 5. Build both. The vanilla tree keeps the original layout; the mod tree only supplies objects.
for t in vanilla "$MOD"; do
    (cd "$WORK/$t" && tools/dr make -j4 >"$WORK/make-$t.log" 2>&1) || { tail -20 "$WORK/make-$t.log"; exit 1; }
    git -C "$WORK/$t" checkout -q -- config/symbols.txt   # rewritten by every build
done

# 6. Hook the changed functions into the original layout.
python3 "$HERE/hookbuild.py" "$WORK/vanilla" "$WORK/$MOD" "$WORK/$OUT.gba"
if [ "$EFFECTS" = 1 ]; then python3 "$HERE/check_effect_table.py" "$WORK/vanilla" "$WORK/$OUT.gba"; fi

# 7. The patch, checked by applying it back onto your ROM.
if command -v flips >/dev/null 2>&1; then
    flips --create --bps-delta "$ROM" "$WORK/$OUT.gba" "$WORK/$OUT.bps" >/dev/null
    flips --apply "$WORK/$OUT.bps" "$ROM" "$WORK/$OUT.check.gba" >/dev/null
    cmp "$WORK/$OUT.gba" "$WORK/$OUT.check.gba" && rm "$WORK/$OUT.check.gba"
    echo "patch: $WORK/$OUT.bps ($(wc -c <"$WORK/$OUT.bps") bytes)"
fi
sha1sum "$ROM" "$WORK/$OUT.gba"
