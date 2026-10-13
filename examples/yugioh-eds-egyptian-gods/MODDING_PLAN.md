# Yu-Gi-Oh! The Eternal Duelist Soul: Egyptian God cards modding plan

**Status: working.** Every check passes in headless mGBA (`evidence/verification.json`). Still waiting on
the user's test in Delta.

- **Game:** Yu-Gi-Oh! The Eternal Duelist Soul (EDS), Game Boy Advance, Konami 2001. Played in Delta (iOS).
- **Idea:** Obelisk, Slifer and Ra can be obtained, put in a deck and summoned by the player, and NPC duelists
  have them in their decks and play them.
- **Done means:**
  1. the player gets each God from the password screen;
  2. they can put it in the deck;
  3. they can Tribute Summon it, and it fights as a 4000/4000 Level 10 monster;
  4. Kaiba, Yami Yugi and Marik summon theirs;
  5. all of it is checked in headless mGBA, and then by the user in Delta;
  6. there's a short clip.

  It ships as a `.bps` patch only.

## Recon
- **Platform:** a GBA ROM with no anti-cheat. It's offline, and the only multiplayer is the link cable. Safe to mod.
- **Version:** USA `AY5E`, SHA-1 `510fbba212aca9bab95ea12f8fd933e62ee34dea`. The user's dump matches.
- **Source of truth:** [eds-decomp](https://github.com/CosmicScribe64/eds-decomp), MIT, pinned at `857002a`
  (2026-10-04).
  - It's a complete matching decompilation (1,976/1,976 functions).
  - `make setup` extracts the data from your ROM.
  - `tools/emu.py` drives a headless mGBA harness.
- **Knowledge base:** this is the first EDS, GBA or Delta note.
- **Delta:** it imports `.gba` files from Files and imports and exports saves from the long-press menu. A
  patched ROM is a separate game entry. It supports Action Replay, Code Breaker and GameShark cheats.

## Why the Gods couldn't be played
They exist in vanilla as card numbers 1910/1911/1912 (IDs 817/818/819), with art and names, and they're
already in booster packs:
- Obelisk in pack 505, *The Final Duelist*;
- Slifer in pack 509, *Limited Collection*;
- Ra in pack 802, which has no shop entry.

Four gates turned them off:

| Gate | Where | Fix |
|---|---|---|
| Ban list: limit 0. It also strips them from CPU decks (`RemoveOverLimitDeckCards`). | `GetCardCopyLimit`, table `0x081A78B4` | data: limit 1 |
| 0 ATK, 0 DEF, level 0 | `gCardStats` `0x08621DE0` | data: 4000/4000, level 10 |
| "Monster" means `type <= Reptile (20)` in 85 places, so Divine (24) is not a monster: no Summon/Set command, and invisible to the AI | 42 files | code: `CARD_TYPE_IS_MONSTER()` |
| Obelisk is hard-coded as a Ritual monster (by card number), and Ritual monsters can't be Normal Summoned | about a dozen copies of the kind classifier | code: Effect kind in the gameplay copies only |

The rest is extra:
- the TCG passwords (the Gods had none);
- NPC deck swaps (the deck region is full, so each God replaces a card);
- dropping "This is not able to play." from Card View.

## Route: decomp data edits plus C, hooked into the original layout
The first plan was "edit the decomp and rebuild". That fails, because the decomp's layout is not relocatable:
- much of the C reads tables through integer addresses;
- a growing function shifts every later byte (`gCardStats` moved 692 bytes in the naive build);
- the decomp's own notes say "Relocatable data is future work".

So `hookbuild.py` builds two trees:
1. the original C with the new data (the original layout);
2. the patched C.

It then finds the changed functions by comparing objects (63 of them), links the edited units at 0x08800000
with every other symbol at its original address, sends calls that leave the blob through long-branch stubs,
and writes a 16-byte jump over each changed function's original entry.

Rejected routes:
- **Delta cheats:** RAM codes can't touch the ROM's ban list, stats or rules.
- **Hand hex-editing:** the summon rule is code.
- **Data-only re-typing:** turning the Gods into Dragons would lose the Divine type, and type-specific cards
  would then affect them.

## Decisions (user defaults)
- **Copies:** 1 per deck.
- **Tributes:** EDS's two for Level 7 and up.
- **NPC Gods:**
  - Kaiba gets Obelisk for one Koumori Dragon;
  - Yami Yugi gets Slifer for Giant Soldier of Stone;
  - Marik gets Ra for one Dream Clown.
- **Effects:** none in this version.

## Open
- The user's test in Delta, which runs a VBA-M-based core: the patched ROM is 16 MiB and runs ARM trampolines
  from ROM.
- **Optional next steps:**
  - TCG-accurate three Tributes (`CanSummonFromHand`, the summon step, `AiHasTributesFor`);
  - God effects: new rows in the 426-row `FindCardEffect` table, whose bound is hard-coded;
  - God card text.
