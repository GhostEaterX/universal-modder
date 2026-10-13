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
