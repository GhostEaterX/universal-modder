# MODLOG: EDS Egyptian God cards

## 2026-10-13: recon
- **Knowledge base:** `um kb search "yu-gi-oh"` and `"gba"` found nothing, so this is the first EDS note.
- **Decomp:** found [CosmicScribe64/eds-decomp](https://github.com/CosmicScribe64/eds-decomp) (MIT), a complete
  matching decomp of the USA ROM (`AY5E`, SHA-1 `510fbba212aca9bab95ea12f8fd933e62ee34dea`).
  - Shallow clone at `~/eds-decomp-src/eds-decomp`, commit `857002a` (2026-10-04). It is kept outside this
    repo and holds no game data.
  - With no ROM here, nothing has been built yet.
- **God identity:** card numbers 1910/1911/1912 = card IDs 817/818/819 (`include/constants/cards.h`). The
  stats word is `0x41800000`: Divine (type 24), attribute 2, level 0, 0/0.
- **Blocking layers.** Each was checked in source, and the table is in `MODDING_PLAN.md`:
  - `GetCardCopyLimit`: limit 0, table `0x081A78B4`;
  - `RemoveOverLimitDeckCards` (CPU decks);
  - `CanSummonFromHand`: type > 20 refused, Ritual kind refused, Obelisk hard-coded Ritual;
  - no password;
  - `gStrNotPlayable`.
- **Helpful leftovers:** the engine already values Divine at 4000 ATK/DEF and level 10
  (`DIVINE_STAT`/`AI_DIVINE_VALUE`).
- **Passwords:** `FindCardByPassword` scans all 821 IDs, and a match gives one copy via `AddCardToTrunk`.
  Setting the TCG passwords is enough to hand the Gods to the player.
- **Deck lists:** `u16` card numbers, sorted, packed into a full 0x920-byte region. Swap cards rather than
  add them. Kaiba's deck has 42 cards, Yami Yugi's 41, Marik's 40.
- **Trunk RAM:** `0x02011C28 + id*4`, owned count in bits 0-9. The Gods sit at `0x020128EC`/`F0`/`F4`.
- **Monster test:** 88 type comparisons against `CARD_TYPE_REPTILE` across 42 files decide "is a monster".
  That's the cost of Option A.
- **Container:** the Docker CLI is present but there's no daemon (`/var/run/docker.sock` missing). Fallback:
  `tools/setup_native.sh` (apt plus `git clone pret/agbcc`).
- **Not fetched:** tcrf.net and pokecommunity.com gave DNS failures from this container.

**Next:**
1. The user confirms the ROM version and where to build.
2. Then run `tools/dr make setup` and `compare`.
3. Then Slice 1 (Slifer, data only).

## 2026-10-13: build and verification
- **ROM:** the user uploaded their USA dump; the SHA-1 matches `510fbba2…` and the header says `AY5E`. It lives in
  `~/eds-decomp-src/eds-decomp/roms/` (gitignored by the decomp) and is never committed.
- **Toolchain:** Docker has a CLI but no daemon, so `tools/setup_native.sh` (EDS_MINIMAL=1: apt plus
  `pret/agbcc`). `make setup` then `make compare` gave `eds.gba: OK` in 15 s.
- **mGBA 0.10.5 for `tools/emu.py`:** the GitHub tarball got a 403 from the proxy, so `git clone --branch
  0.10.5` and the cmake flags from `docker/emu/Dockerfile`, installed to `~/.mgba`. It runs with
  `EDS_NATIVE=1 MGBA_PREFIX=~/.mgba`. The venv needs Pillow for contact sheets.
- **Data (`scripts/apply_gods.py`, 119 changed bytes, layout unchanged):**
  - stats 400/400 (÷10), level 10;
  - TCG passwords;
  - copy limit 1;
  - deck swaps.

  Its JSON writer copies the extractor's style (`tables_game._dumps`), so diffs stay minimal.
- **Code (`scripts/patch_source.py`):**
  - 85 monster-type tests now go through `CARD_TYPE_IS_MONSTER`; the Card View attribute icon test is left
    as it was;
  - 12 Obelisk-kind cases;
  - the IsEffectMonster and IsSpecialSummonOnly special cases;
  - Card View text.
- **Gotcha 1, layout not relocatable.** The naive build put `gCardStats` at `0x08622094` instead of
  `0x08621DE0` (+692 bytes), and the ROM grew. Code reads tables through integer constants, so that ROM is
  broken. Fix: `scripts/hookbuild.py`:
  - vanilla C plus the new assets gives the original layout;
  - the changed functions (object compare: bytes with relocated words blanked, plus the relocation list)
    are relinked at `0x08800000` with `-R vanilla.elf`;
  - each object's own globals are localized;
  - the 536 BL targets outside the blob go through ARM `ldr ip,[pc]; bx ip` stubs, because Thumb BL only
    reaches ±4 MiB;
  - each changed entry gets the trampoline `bx pc; nop; ldr ip,[pc]; bx ip; .word new|1` (16 bytes, or 18
    when the entry is 2 mod 4).

  The game never compares function pointers except to NULL, so duplicate copies are safe.
- **Gotcha 2, symbols file:** every `make` rewrites `config/symbols.txt`. Restore it before diffing or
  patching.
- **Gotcha 3, `check.py` isn't a change detector:** once a function changes size, every later function in
  the unit shows as DIFF, so its per-function report can't say what changed. Compare the objects instead.
- **Null-hook test:** the vanilla objects relinked behind the same 63 hooks give identical EWRAM at every
  library state, except `gDuelScreen.fieldBgScroll` (VBlank drift). The cause is 2 lag frames during the deal
  (duel_main1 is reached at frame 3165 instead of 3163). The hook machinery itself is proven.
- **Gotcha 4, the AI only weighs Tribute Summons when its field can't already attack well**
  (`AiStepMainPhase`: `AiPlanAttack(1) != 0` means no-tribute summons only). An AI test against an empty
  player field never reaches `AiChooseSummonWithTribute`. Giving the player a Blue-Eyes does.
- **Gotcha 5, AI simulation:** `AiSimSummon` writes candidate cards into the real zone RAM and restores them
  within a few frames. An oracle must require the God to stay on the field (60 frames), or it passes on the
  simulation.
- **Gotcha 6, staging:** the first `DuelMainStep` frame clears the zones (LP go 0 → 8000), so poke after that.
  Poked zones only get drawn if the poke lands before the field is first drawn.
- **Gotcha 7, Ritual kind:** Obelisk's Ritual kind is used for frames *and* rules. `card_detail.c` serves both,
  so its frame keeps Ritual and its two rule functions special-case Obelisk.
- **Results:** all 8 oracles pass on the mod and fail on the original (`tests/run_oracles.py --control`).
  - Full player path: password → Deck Edit → duel deck.
  - Battle: Obelisk beats BEWD, 8000 → 7000.
  - Regression: in a duel without Gods, the mod matches null hooks byte for byte.
- **Build:** a fresh `scripts/build.sh` takes 68 s and gives the same SHA-1 `2b905f01…`. `gods.bps` from
  `flips --bps-delta` is 39,158 bytes, round-trip checked.
- **Showcase:** a 35 s silent clip from the harness (`um video compile`), sent to the user rather than
  committed (19 MB).
- **Next:** the user tests in Delta. Then, with their OK: the field note PR, and maybe 3 Tributes or God effects.
