# Yu-Gi-Oh! The Eternal Duelist Soul: Egyptian God cards modding plan

- **Game:** Yu-Gi-Oh! The Eternal Duelist Soul (EDS), Game Boy Advance, Konami 2001. Played in Delta (iOS).
- **Idea:** Obelisk the Tormentor, Slifer the Sky Dragon and The Winged Dragon of Ra can be obtained, put in a
  deck and summoned by the player, and NPC duelists have them in their decks and play them.
- **Done means:**
  1. the player gets each God from the password screen;
  2. they can put it in the deck;
  3. they can Tribute Summon it in a duel, where it fights as a 4000/4000 Level 10 monster;
  4. Kaiba, Yami Yugi and Marik summon theirs;
  5. it all checks out in a headless mGBA run and then in Delta on the user's phone;
  6. there's a short clip.

  It ships as a `.bps` patch only, never a ROM.

## Recon
- **Platform:** a GBA ROM with no anti-cheat. It's offline, and the only multiplayer is the link cable. Safe to mod.
- **Version:** only the USA release (game code `AY5E`, SHA-1 `510fbba212aca9bab95ea12f8fd933e62ee34dea`) is
  covered. The Japanese *Duel Monsters 5 Expert 1* (`AY5J`) is a different build with 928 cards, and isn't covered.
- **Source of truth:** [eds-decomp](https://github.com/CosmicScribe64/eds-decomp), MIT, read at commit
  `857002a` (2026-10-04).
  - It's a complete matching decompilation: 1,976/1,976 functions, 1,970 of them in C.
  - It contains no game data. `tools/dr make setup` extracts everything from your own ROM into editable
    JSON/CSV/PNG under `assets/`, and `tools/dr make` builds a modified ROM from them.
  - `tools/emu.py` is a headless mGBA 0.10.5 harness with input scripts, RAM checks and screenshots. It's
    the automated oracle.
  - It's cloned read-only at `~/eds-decomp-src/eds-decomp`, outside this repo.
- **Knowledge base:** nothing yet on EDS, GBA or Delta (`um kb search` 2026-10-13).
- **Older community work, before the decomp:**
  - a [PokéCommunity thread](https://www.pokecommunity.com/threads/yu-gi-oh-the-eternal-duelist-soul-rom-hacking-using-hex-maniac-advance-c.527990/)
    on hex-editing EDS with Hex Maniac Advance (it calls table expansion "a major hurdle");
  - a [Neoseeker thread](https://www.neoseeker.com/forums/4158/t2395976-yu-gi-oh-eternal-duelist-soul-hack/)
    listing the tables a new card touches.

  The decomp makes both obsolete for this mod.
- **Delta:** it supports GBA cheats in the Action Replay, Code Breaker and GameShark formats. It imports
  `.gba` files from Files, and a long-press on a game offers save import and export. A patched ROM has a
  different hash, so Delta lists it as a separate game.

## How the vanilla game blocks the Gods
The Gods exist as cards: numbers 1910/1911/1912, card IDs 817/818/819, with art and names. Seven separate
things keep them out of play:

```
 get it            build a deck        NPC decks             duel
┌──────────────┐  ┌───────────────┐   ┌──────────────────┐  ┌──────────────────────────────┐
│ no password  │  │ ban list:     │   │ not in any list, │  │ stats 0/0, level 0           │
│ (FF FF FF FF)│─▶│ limit 0       │──▶│ and over-limit   │─▶│ type Divine (24) ≠ monster   │
│ not in packs │  │               │   │ cards get removed│  │ Obelisk hard-coded "Ritual"  │
└──────────────┘  └───────────────┘   └──────────────────┘  │ "This is not able to play."  │
                                                            └──────────────────────────────┘
```

| Layer | What the ROM does | Where (eds-decomp) | Fix |
|---|---|---|---|
| Obtaining | No password (`FF FF FF FF`). The booster-pack page lists no God. | password table `0x08623120` → `assets/cards/passwords.csv` | give them their TCG passwords: Obelisk `10000000`, Slifer `10000020`, Ra `10000010` |
| Deck building | The Forbidden/Limited list gives the Gods (and the Tickets) **0** copies | `GetCardCopyLimit` (`src/collection.c`), table `0x081A78B4` → `assets/tables/rodata2/*.json` | limit 1 (anime-style) or 3 |
| NPC decks | `RemoveOverLimitDeckCards` strips over-limit cards from the CPU's deck, and no deck list holds a God | `src/ai_deck.c`, `gOpponentDecks` `0x0819DC6C` → `assets/tables/deck_lists.json` | lift the limit, then add the Gods to decks. The 0x920-byte deck region is full, so swap a card out rather than adding one. |
| Stats | 0 ATK / 0 DEF, level 0, type Divine (24), attribute 2 | `gCardStats` `0x08621DE0` → `assets/cards/stats.csv` | 4000/4000 (stored ÷10 as 400), level 10 |
| Summoning | `CanSummonFromHand` refuses any type above Reptile (20) and any Ritual-kind card. Obelisk is hard-coded as Ritual kind by card number. | `src/summon_checks.c`. The kind special case is inlined in about 10 units (`effect_activation.c`, `duel_ritual.c`, `ai_summon.c`, `summon_builders.c`, …). | see "Making them summonable" below |
| AI | The AI's hand pickers only consider type ≤ Reptile | `src/summon_builders.c`, `src/ai_summon.c`, `src/ai_deck.c` | fixed along with the type |
| Card screen | Prints "This is not able to play." for Ticket and Divine cards | `gStrNotPlayable` `0x0808158C`, `CardDetail_DrawInfo` (`src/title_menu.c`) | stop printing it for Divine |

**Leftovers that help:** EDS shares a duel engine with the other Duel Monsters games, and that engine already
treats a Divine card as 4000 ATK/DEF and level 10:
- the AI and effect helpers do this in `effect_target_collect.c`, `summon_builders.c` and `ai_summon.c`;
- the AI's tribute check (`AiHasTributesFor`) counts a God as level 10, which means two tributes.

Much of the duel-side support is already there; the gates above are what switch it off.

## Route
**Decomp: data edits plus a small C change → build → `.bps` patch against the user's own ROM → patch it on the
phone → Delta.**

```
 your ROM (USA, AY5E)
      │  tools/dr make setup          (extracts assets/, verifies SHA-1)
      ▼
 eds-decomp + this mod's changes:
   scripts/apply_gods.py   edits the extracted CSV/JSON in place (no game data is committed)
   patches/eds-decomp.diff the C changes
      │  tools/dr make  →  eds.gba (modded)
      │  tools/emu.py   →  headless duels: does it work?
      ▼
 flips/beat → gods.bps  ──▶  Rom Patcher JS (Safari) + your ROM ──▶ patched .gba ──▶ Delta
```

Rejected routes:
- **Delta cheat codes only.** A RAM code can put the Gods in the trunk: a `u32` at `0x02011C28 + id*4`, with
  the owned count in bits 0-9, i.e. `0x020128EC`/`0x020128F0`/`0x020128F4`. But the ban list, the stats and
  the summon rule live in ROM, so the Gods would still be unplayable.
- **Hand hex-editing.** That works for the data. The summon rule is code, though, and the decomp turns that
  into a few lines of C.

## Making them summonable: two options
- **Option B: re-type them as ordinary monsters (the first slice).** For Slifer and Ra this is data only:
  type → an ordinary monster type, 4000/4000, level 10. Their hard-coded kind is "Effect", which
  `CanSummonFromHand` allows. Obelisk also needs its hard-coded Ritual kind changed in the logic copies; the
  frame-colour copies can stay, so Obelisk keeps its blue frame. The cost: the cards lose the Divine type and
  icon.
- **Option A: make Divine a real monster type (recommended end state).** Keep type 24 and add one predicate,
  "type ≤ Reptile or type == Divine". It replaces 88 `CARD_TYPE_REPTILE` comparisons in 42 files. Each needs
  review: most mean "is this a monster?", while a few (the declare-a-type menus, for example) should stay
  as they are. This keeps the Divine-Beast type, the icon and the engine's own 4000/level-10 helpers.

The rule is cheapest first. Slice 1 uses B to prove the whole pipeline; phase 2 moves to A.

## Steps
0. **Lab and backups.**
   - In Delta, export the battery save, and a save state from the game's long-press menu.
   - Keep the original ROM untouched.
   - The patched ROM is a new Delta entry, so import the save into it. Card IDs don't change, so old saves stay
     valid.
1. **Toolchain.**
   - Check the ROM's SHA-1.
   - Run `tools/dr make setup`, then `tools/dr make compare`, which must print `eds.gba: OK`. That proves the
     toolchain before anything is changed.
2. **Slice 1: Slifer only, data only.**
   - Password `10000020`, limit 1, stats 4000/4000 at level 10 with an ordinary type.
   - Swap one card in Yami Yugi's 41-card deck for Slifer.
   - Build. With `tools/emu.py`:
     1. enter the password and check that the trunk word at `0x020128F0` reads 1;
     2. put Slifer in the deck;
     3. Tribute Summon it in a duel;
     4. duel Yami Yugi and watch for the CPU summoning it.
   - Then the user tries it in Delta.
3. **Phase 2: all three, Option A.**
   - Obelisk and Ra get the same data changes.
   - Apply the Divine-as-monster predicate and the Obelisk kind fix, and drop "not able to play" for Divine.
   - Battle City owners get the Gods: Kaiba gets Obelisk (42-card deck), Yami Yugi gets Slifer, Marik gets
     Ra. Each swaps out a weak card.
   - Re-run the headless duels for each, plus a regression duel with no Gods.
4. **Phase 3, optional (the user decides):**
   - TCG-accurate 3 tributes, instead of EDS's 2 for level 7 and up. That touches `CanSummonFromHand`, the
     summon step and `AiHasTributesFor`.
   - The God effects: Obelisk's tribute-two-to-wipe-the-field, Slifer's ATK from hand size, Ra's.
     `FindCardEffect` binary-searches a fixed 426-row table, so new rows also mean changing that bound.
   - Card text.
5. **Finish.** Record a showcase clip, then publish only the `.bps` patch plus a README (`um publish check`),
   and write a field note (`um kb new`).

## Unknowns to resolve first
1. **Is the user's ROM the USA `AY5E` release with that SHA-1?** Everything depends on it. The user must have
   dumped it from their own cartridge; we never download ROMs.
2. **Where to build:**
   - in this cloud session: the user uploads their ROM, which stays in the container outside the repo and
     is never committed. The container has a Docker CLI but no daemon, so this would mean
     `tools/setup_native.sh` (apt + `pret/agbcc`), untested here;
   - or on the user's own computer with Docker.
3. Copy limit: 1 each, or 3?
4. Which NPCs get which God, and which card each one gives up?
5. Two tributes (EDS rule) or three (TCG rule)?
6. Does Delta's long-press save import accept a raw `.sav` for the new entry? Check on the device.
7. Does any booster pack reference the Gods? Check `assets/tables/` after setup.
8. Once the Gods count as monsters, does the AI really summon them, or does a picker filter skip them? The
   headless duel against Kaiba answers this.
