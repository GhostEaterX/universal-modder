---
kind: game
title: "Playable Egyptian God cards in Yu-Gi-Oh! The Eternal Duelist Soul via eds-decomp and function hooks"
game: "Yu-Gi-Oh! The Eternal Duelist Soul"
games_also: []
game_version: "USA AY5E (SHA-1 510fbba212aca9bab95ea12f8fd933e62ee34dea), eds-decomp 857002a"
platform: emulator
engine: unknown
route: decomp-recomp
tools: ["eds-decomp 857002a (old_agbcc, arm-none-eabi binutils)", "mGBA 0.10.5 via eds-decomp tools/emu.py", "Flips (BPS)", "Delta (iOS) as the player's emulator"]
anti_cheat: "none (GBA ROM, offline; link cable only)"
status: working
agents: ["Claude Code"]
humans: []
date: 2026-10-13
links:
  - https://github.com/CosmicScribe64/eds-decomp
  - https://github.com/rehan-remade/universal-modder/tree/main/examples/yugioh-eds-egyptian-gods
tags: [gba, decomp, rom-hack, bps, function-hooks, trampolines, card-game, ai, delta, mgba, headless-oracle, booster-packs, drop-rates, ui]
---

# Playable Egyptian God cards in Yu-Gi-Oh! The Eternal Duelist Soul via eds-decomp and function hooks

> The mod makes Obelisk, Slifer and Ra playable in EDS (GBA): Level 10, 4000/4000 monsters that the player
> can get by password, put in a deck and Tribute Summon. Kaiba, Yami Yugi and Marik carry one each, and the
> CPU summons them. It's built on the complete matching decomp eds-decomp. Data edits go through its asset
> pipeline; the C edits are hooked into the original ROM layout, because the decomp can't absorb code growth.
> Checked with 8 headless-mGBA oracles (each one also fails on the original ROM) and shipped as a 39 KB
> `.bps`. It works in Delta on iOS: the user summoned a God with two Tributes and attacked with it.
> Later builds add the TCG three-Tribute rule and the Gods' TCG effects (Obelisk's wipe, Slifer's hand-size
> ATK and drain, Ra's LP payment and destroy). The effects go through a relocated copy of the game's effect
> table.

## Setup
- **ROM:** the user's own dump of the USA cartridge (`AY5E`, 8 MiB). The JP *Duel Monsters 5* is a different
  build (928 cards) that eds-decomp doesn't cover.
- **eds-decomp** pinned at `857002a`, with the native toolchain (`tools/setup_native.sh`, Docker not needed):
  - `tools/dr make setup` checks the ROM and extracts 83 assets (CSV/JSON/PNG);
  - `tools/dr make compare` prints `eds.gba: OK` after about 15 s.
- **mGBA 0.10.5** built natively for `tools/emu.py`, with the cmake flags from `docker/emu/Dockerfile`:
  `EDS_NATIVE=1 MGBA_PREFIX=...`. The harness's `selftest` passes.

## Route and why
- **Rejected: cheat codes.** Delta supports AR, Code Breaker and GameShark codes. They can put cards in the
  trunk (RAM), but the ban list, stats and summon rules are in ROM.
- **Rejected: hand hex-editing.** The real blocker is C logic spread over about 85 sites.
- **Rejected: re-typing the Gods** as an ordinary monster type, by data alone. It loses the Divine type, and
  it makes the Gods targets of type-specific cards (Dragon Capture Jar on a Dragon Slifer, for example).
- **Taken: decomp-recomp.**
  - Edit the extracted data: stats, passwords, ban list, deck lists.
  - Make a small, rule-based C change: one monster-type predicate, and Obelisk's kind.
  - Hook the changed functions into the otherwise untouched original layout.

## How the game works (what we had to learn)
- **Two numberings.**
  - The card ID (1-820, alphabetical) is what duel state carries.
  - The card number (the Konami number) is what decks, packs, the ban list and hard-coded checks use.
  - The Gods are numbers 1910/1911/1912, IDs 817/818/819, type Divine (24). In vanilla they're 0/0 at level 0.
- **Gods in vanilla.** They're in booster packs: Obelisk in 505 *The Final Duelist*, Slifer in 509 *Limited
  Collection*, Ra in pack 802. They have no password. The Card View says "This is not able to play."
- **Ban list.** `GetCardCopyLimit` reads 47 `{number, limit}` pairs, and the Gods are at 0. The CPU's deck
  loader (`LoadOpponentDeck`) calls `RemoveOverLimitDeckCards`, so a God put in an NPC deck list vanishes
  unless the limit changes too.
- **"Is a monster" is `type <= Reptile (20)`, written out in 85 places in 42 files.** Divine (24) fails
  everywhere:
  - `CanSummonFromHand` refuses;
  - the card menu offers only Card View;
  - the AI's pickers skip the card.

  Yet the shared Duel Monsters engine still has Divine cases that value a God at 4000 ATK/DEF and level 10
  (AI and effect helpers). The support was there, just gated off.
- **Obelisk is hard-coded "Ritual kind" by card number,** Slifer and Ra "Effect kind". The same inline
  classifier is copied into about 30 units: frame graphics, deck-edit filters and gameplay rules. Ritual
  kind means no Normal Summon, so only the gameplay copies should change, or Obelisk loses its blue frame.
- **Tribute rule.** Level 5-6 takes one Tribute, 7+ takes two, and the AI's `AiHasTributesFor` treats Divine
  as 10. The AI's summon simulation supports up to four tributes.
- **AI turn.** `AiStepMainPhase` only calls `AiChooseSummonWithTribute` when `AiPlanAttack(1)` says the
  current field can't attack profitably. Otherwise it only tries no-tribute summons.
- **Deck lists.** These are sorted `u16` card numbers in a fixed 0x920-byte region that is already full. Swap
  cards rather than adding them; the build re-packs the lists.
- **Passwords.** 8-digit packed BCD per card ID; `FF FF FF FF` means none. `FindCardByPassword` scans all IDs,
  and a hit gives one copy (a `passwordUsed` flag).
- **Useful RAM addresses:**

  | What | Address |
  |---|---|
  | `gDuelPlayers` (0xD64 bytes per player) | `0x020192E4` |
  | zones | +0x28, 0x94 each, card ID in the low 12 bits |
  | hand | +0x684 |
  | deck | +0x7C4 |
  | campaign opponent | `gMain+0x4870`, bits 1-5 |
  | trunk | `0x02011C28 + id*4`, owned count in bits 0-9 |
  | duel phase byte | `0x02015EE8` |

## Build steps
`examples/yugioh-eds-egyptian-gods/scripts/build.sh <your-rom.gba> <work>` runs these steps:
1. Two checkouts of eds-decomp at the pin: vanilla and mod.
2. `make setup` with your ROM.
3. `apply_gods.py`: the data, copied to both trees.
4. `patch_source.py`: the rule-based C edits, mod tree only.
5. `make` in both trees.
6. `hookbuild.py vanilla mod gods.gba`.
7. `flips --create --bps-delta` and a round-trip check.

From a fresh clone this takes 68 s and is deterministic (the same output SHA-1 every time).

## Verification
**Oracles.** Eight checks run in `tests/run_oracles.py` (eds-decomp's mGBA harness, blank SRAM, scripted keys,
results read from RAM):
- each boss's duel deck holds its God;
- password `10000020` gives Slifer;
- the player Tribute Summons Slifer;
- the CPU Tribute Summons each God.

All pass on the mod and all fail on the original ROM (`--control`).

**Extra checks:**
- password → Deck Edit "To Main Deck" → the player's duel deck holds Slifer;
- Obelisk attacks Blue-Eyes and LP drop by exactly 1000;
- the null-hook equivalence test (gotcha 1);
- a regression run (no Gods, mod vs null hooks): EWRAM and frame counts identical.

**On a real device:** tested by the user in Delta on iOS: they summoned a God with two Tributes from the field, it showed 4000 ATK / 4000 DEF, and they attacked with it. So the 16 MiB ROM and the ARM trampolines running from ROM work there
too, not only in mGBA. Not checked in Delta: the CPU summoning a God, and the password screen.

### Second build: three Tributes (TCG rule)
`build.sh ... --tributes 3` adds `patch_three_tributes.py`: 26 anchored edits, giving 73 hooked functions and
4 new globals.
- **What the engine already had:** a third Tribute slot (`tribute3Zone`/`hasTribute3`), unused, which the
  Special-Summon-from-hand executor already Tributed.
- **Normal Summons:** the Tribute word gets a third byte, and both Normal Summon executors remove it.
- **The summon check** wants three tributable monsters.
- **The player's menu** asks "requires 3 Tributes".
- **Ultimate Offering** takes three picks for a God.
- **The AI** picks three, through a new `AiPickTributeMonsterExcept`.

Suite: 15 oracles, run with the 2-Tribute build as the control. The rule-discriminating ones fail there, and
the Blue-Eyes regressions pass on both. In a God-free duel the two builds' EWRAM is identical. The user
confirmed this build works in Delta on iOS too.

### Third and fourth builds: God effects
`build.sh ... --effects` (with either Tribute rule) adds `patch_god_effects.py`. It copies the mod's own
`src/god_effects.c` and `god_effects_table.s` into the decomp as two new units, then makes 22 anchored edits.
- **How EDS runs effects:** a 426-row table `gCardEffects` (`0x0819A9D4`, 0x18 bytes per row:
  `number, flags, resolve, check, prepare, chainA, chainB`), binary-searched by `FindCardEffect`. Its bound
  (`hi = 425`) is hard-coded. Much of a card's behaviour is *not* in the table, though: it is
  `switch (card number)` cases elsewhere:
  - stats in `GetZoneCardStats` (Muka Muka was Slifer's template);
  - Normal Summon triggers in `ExecuteSummonAction` step 2;
  - a field monster's Activate in `CanActivateMonsterEffect`;
  - reactions to every summon in `SummonAction_Update`;
  - targeting immunity in `CanCardTargetZone`;
  - the CPU's monster effects in a 4-entry ROM list inside `AiActivateMonsterEffects`.
- **The table can't grow in place:** `gTributeSummonPrompts` starts where it ends. The new unit `.incbin`s the
  decomp's own built table (made from the user's ROM, so nothing is committed) and appends the Gods' rows.
  `#define gCardEffects gCardEffectsMod` in `effect.h` sends every reader to it, so the hook builder hooks
  all 11 reader functions on its own. A check script compares the 426 rows to the original, the sort order
  and that every reader is hooked.
- **Per-card memory:** zone links. Every engine reader ignores link kinds it doesn't know, so new kinds 14
  (Ra's paid LP) and 15 (a pad) are safe. The engine's existing kind 4 (ATK bonus) is removed in the End
  Phase, so it can't hold Ra's LP.
- **Checks:** 18 effect oracles per build, each failing on the same build without effects (Card View text
  included), plus the base suite on the effects build. In a God-free duel, EWRAM is identical with and
  without effects. In Delta on iOS the user ran the three-Tribute effects
  build and summoned Ra.

### In the fourth build: a pack viewer with odds
`gods-3t-fx` also gets `patch_pack_viewer.py`. On the pick-a-pack screen after a duel, the bottom band names
the centre pack, and SELECT lists its cards with each card's chance of being in the pack you'd get.
- **How a pack is made** (`GeneratePackCards`):
  - a rarity roll `Random() % 180` over 8 slots with cumulative thresholds `{1,3,6,10,16,28,64,180}`
    (`% 270` when you pick the same pack as last time; `% 12`, a sure rare, after more than 5 commons-only
    packs, more than 10 on the same pack);
  - one card from the rolled slot;
  - four commons: the first four of a copy of the commons after 2N random swaps, skipping the rolled card.
- **The odds:**
  - 2N swaps isn't a uniform shuffle: the first commons of the list come up about 10% more often.
  - The exact chance comes from two backward-propagated Markov chains: one card's position, and the pair
    (card, rolled card). Checked against brute force over all permutations.
  - A simulation of the decomp's algorithm with the game's LCG (`x = s * 0x343FD + 0x269EC3`, rotated by 16;
    15-bit output) agreed on all 2,982 odds.
  - The table is generated at build time from the user's `booster_packs.json`, like the effect table.
- **The list** reuses the opening scene: `GetPack_InitScene`, `GetPack_DrawCardRow` and the Card Detail steps.
  It runs on new sub-states (0x20+) of `GetPack_SelectAndGenerate`, and keeps its state in `gPackOpenWork`,
  which is cleared before a pack is made.
- **Checks:** 13 oracles (`--pack-viewer`). The logger reads the odds, NEW and header text off the screen (BG0
  map plus VRAM glyph tiles, against the game's 8x8 bold font). With the RNG pinned at the pick, the viewer
  build and the build without it generate the same 5 cards, even after a trip through the viewer.

### Also in the fourth build: the TCG summon rules and quality of life
- **Rules:** a Special Summoned Obelisk or Slifer goes to the Graveyard in the End Phase, and Ra can't be
  Special Summoned (`patch_god_rules.py`, a new unit `god_rules.c`).
  - Every revival but Time Machine takes its candidates from `CanReviveGraveyardCard`. One edit there covers
    Monster Reborn, Call of the Haunted, Premature Burial, The Shallow Grave and Spear Cretin, for the player
    and the CPU.
  - The End Phase hook reads the card word's `specialSummoned` bit, on both sides.
  - On a real device (Delta on iOS), the user confirmed that Ra can't be revived. The End Phase rule hasn't
    been checked there.
- **Quality of life:**
  - the pick screen and the pack list show "23/40 owned", and each row NEW or the copies owned;
  - every Card Detail outside a duel ends with the packs that hold the card;
  - Deck Edit sorts the Gods as monsters;
  - the pack rows show a God's stats.
- **Checks:** 13 rule and Deck Edit oracles plus 4 more viewer checks, each failing on the build without
  them (or passing on both, for the regressions).

### Also in the fourth build: the Tier 1 duelists' second decks
- **Found, not added:** the ROM has a second, stronger deck for each Tier 1 duelist (Yugi, Tea, Joey,
  Tristan, Bakura): `gOpponentAltDecks`, next to `gOpponentDecks`. `LoadOpponentDeck(useAltDeck)` can load
  it, but its only caller, `Campaign_SetupDuel`, passes a constant 0.
- **The change:** one edit (`patch_second_decks.py`, a new unit `second_decks.c`). The call passes 1 when
  the opponent is duelist 1-5 and `gSaveData.duelRecords[opponent].wins` (bits 0-10 of the word at
  `0x02011C20 + 0x20D0 + id*4`) is 10 or more.
- **Checks:** 8 oracles read the CPU's deck and Fusion Deck after `LoadOpponentDeck` and compare them, sorted,
  with the checkout's `deck_lists.json`. The five second decks fail on the build without the change; Tea at 9
  wins, Rex (no second deck) and Kaiba at 10 wins pass on both.
- **The 10th-win line:** the game already shows a special line on the 10th win against each duelist
  (`gOpponentResultTexts[duelist].win10th`, picked while the record still says 9). Appending a `$c$p` page to
  those five dialogue records (fixed 0x304 bytes each) lets the duelist announce the new deck, as a data
  edit. To test dialogue, follow the printer pointer (`gBustup.textBox.text`) to the record's NUL.
- **On a real device:** the user tested the build with the second decks and the 10th-win lines in Delta on
  iOS: it works.

### Also in the fourth build: the CPU deck tuning
- **Dead cards:** 42 card slots across the CPU decks held cards the CPU can never play. A card is playable only
  if some rule plays, sets off or chains it: the spell lists (`gAiGenericSpells`, `gAiEquipSpells`,
  `gAiSimpleSpells`), `AiTryPlaySpellTrap`, `AiChainSetCard`, `AiShouldActivateSetCard`, the flip plans, or the
  scripted combos. Snatch Steal (15 decks) appears only in the hand-reading lists; in the emulator the CPU
  held it next to a target and set a monster instead.
- **The swaps:** 63 cards in 26 decks, one for one (`DECK_TUNING_3T` in `apply_gods.py`, before/after counts
  per deck). Each new card is one the CPU plays. Mai's deck now has the Harpie Lady Sisters that her scripted
  Elegant Egotist play fetches; before, the combo could never finish.
- **Checks:** the 21 tuned regular decks load card for card (fail on the old build). The recruiters, Elegant
  Egotist, Toon World with Toon Mermaid and Fissure each work in a scripted CPU turn (pass on both builds).
- **On a real device:** the user tested the tuned build in Delta on iOS: it works.

## Gotchas
1. **A naive modded build boots into a broken game.**
   - **Cause:** eds-decomp's layout is not relocatable. A lot of C reads tables through integer addresses
     (`gCardStats` at `0x08621DE0`), and one grown function moved `gCardStats` 692 bytes. The decomp's notes:
     "Relocatable data is future work".
   - **Fix:** keep the original layout and hook (`hookbuild.py`):
     - compile the vanilla C with the new assets;
     - find the changed functions by comparing objects;
     - link the edited units at 0x08800000 with `-R vanilla.elf`;
     - localize each object's globals;
     - send outgoing BLs through ARM long-branch stubs (Thumb BL reaches only ±4 MiB);
     - overwrite each changed entry with `bx pc; nop; ldr ip,[pc]; bx ip; .word new|1`, which leaves r0-r3
       and lr intact.
   - **Prove the machinery first** with `--null`: the original code relocated behind the same hooks must play
     identically. EWRAM matched except a VBlank drift counter, from 2 lag frames during the deal.
2. **`check.py <unit>` reports every function after an edit as DIFF.**
   - **Cause:** functions shift once one changes size.
   - **Fix:** detect changes by comparing the vanilla and mod `.o` per function: bytes with the relocated words
     blanked, plus the relocation list. Only 63 functions across the 43 edited units really changed.
3. **The CPU never tried the God.**
   - **Cause:** the AI only weighs Tribute Summons when `AiPlanAttack(1)` fails, and its field could already
     hit an empty player field.
   - **Fix:** give the player a Blue-Eyes (3000) in the test. The CPU then summons Obelisk and wins the battle.
4. **The AI test "passed" too early.**
   - **Cause:** `AiSimSummon` writes the candidate into the real zone RAM, then the backup/restore undoes it a
     few frames later.
   - **Fix:** count the God only after it has stayed on the field for 60 frames.
5. **Poked field cards vanished or weren't drawn.**
   - **Cause:** `DuelMainStep`'s first frame clears the zones, and the field graphics are built once.
   - **Fix:** poke right after the LP become 8000, before the field is first drawn.
6. **Every `make` rewrites `config/symbols.txt`.**
   - **Fix:** `git checkout` it before diffing or patching, or a patch of the C picks up thousands of
     unrelated lines.
7. **Docker CLI but no daemon in a cloud container.**
   - **Fix:** `tools/setup_native.sh` (EDS_MINIMAL=1).
   - The GitHub tarball download got a 403 from the proxy; `git clone --branch` worked.
8. **A third Tribute "leaks" into the next summon.**
   - **Cause:** the Special-Summon-from-hand executor reads `hasTribute3`. A God summon leaves it set, so a
     later Special Summon from hand would Tribute a monster for nothing.
   - **Fix:** every queue function writes the third byte, 0 when absent. All existing callers pass Tribute
     words of 16 bits or less; audit them before decoding new bits.
9. **No room for the third pick.**
    - **Card menu:** use `summonSeq` (4 bits, used only by the Gate Guardian and Valkyrion steps) for
      zone | owner << 3.
    - **Ultimate Offering:** `targets[]` is `u16[3]` and full, so use the free high byte of `targets[1]` (the
      zone).
10. **New functions and strings in hooked units fail to link.**
    - **Cause:** hookbuild localized every global, and its stub pass looked every BL target up in the vanilla
      ELF.
    - **Fix:** globals that vanilla lacks stay global and are never stubbed. New `.rodata` is allowed when the
      vanilla unit had none.
11. **Ultimate Offering in the harness.**
    - **Setup:** the card (ID 756) set in spell/trap zone 5 with `canActivate` (+0x91 bit 2).
    - **Activating:** one UP from the hand reaches it, then RIGHT selects Activate.
    - With nothing summonable in hand, Activate isn't offered at all.
12. **Deck Edit shows the Gods' stats as `X000`.**
   - **Cause:** that's the game's own Divine rendering. Card View and the duel show 4000. Not a bug.
13. **A text box closes as soon as it opens.**
    - **Cause:** it was opened on the same frame as the A press that made the previous cursor pick, and its
      update saw that press.
    - **Fix:** open the next prompt from a separate step, one frame later.
14. **An Equip's link outlives the Equip.**
    - **Cause:** `RemoveLinksToZone` skips the link right after any link it doesn't read as a card location
      (an engine quirk).
    - **Fix:** follow every new non-location link with a pad link (kind 15, value `0xFFFF`).
15. **A CPU test wiped the CPU's own field.**
    - **Cause:** its real hand had Time Wizard, which lost its coin toss.
    - **Fix:** give the CPU a hand of plain monsters in effect tests.
16. **No Battle Phase on turn 1.** Battle oracles start from the `duel_turn2` library state: B, then Enter
    Battle Phase, then the monster's second command (Attack).
17. **Removing a menu command shifts the keys.** Without Set, a God's hand menu is Card View / Summon, and
    two RIGHTs wrap back to Card View. Keep a separate key list per build.
18. **The pick screen's BG0 is 4bpp, not the 8bpp `PackList_InitVideo` writes.**
    - **Cause:** `ResetVideo`, called right after, sets `REG_BG0CNT = 4`. 8bpp text tiles showed up as
      cover pixels.
    - **Fix:** draw 4bpp tiles into the tile buffer's bytes after the four covers (4bpp tile 0x330), with
      palette bank 14 of `gPackListPal` (235 white, 233 pale yellow).
19. **`TextCanvasInit` clears the whole 64 KB canvas: about 3 frames.**
    - **Effect:** redrawing 5 list rows took 15 frames.
    - **Fix:** in the viewer only, the row drawer clears just the rows' tiles (`CpuFastSet`). The opening
      scene keeps the original, so its timing doesn't change.
20. **The scene runs mid-frame, so VRAM tile writes tear.**
    - **Cause:** `MainLoop` copies the BG maps and OAM in `FrameSyncUpdate` at VBlank, then runs the scene.
      Map changes show a frame later, tile and palette changes at once.
    - **Fix:**
      - blank a row's VRAM map lines before drawing it;
      - move scrolled rows' tiles in `gMain.vblankCallback`;
      - queue sprites after the change.
21. **The Latin text font is fixed-width:** half the font size per character (`TextDrawLatinString`).
    Centring needs no measuring pass.
22. **Lag frames change frame-timed RNG results.**
    - **Cause:** `FrameSyncUpdate` calls `Random()` once per main-loop pass, so one extra lag frame moves
      every later key press to a different RNG state.
    - **Fix:** to compare two builds' packs, pin `gMain.rngState` (`0x03000040`) when the pick's fade-out
      starts.
23. **The Gods' "X000" is not a blanket Divine display.** Deck Edit and Card Detail print Obelisk 4000,
    Slifer `X000` and Ra `????`, which is exactly what they mean with the effects (1000 × the hand, the LP
    paid). The real gaps were elsewhere: Deck Edit's sorts and filters treated Divine as "not a monster", and
    the pack-opening row drew nothing for Divine.
24. **Deck Edit's Monsters filter can't be selected.** `LIST_FILTER_MONSTERS` isn't in the cursor tables.
    Grouping a type with the monsters shows only in the ATK/DEF/level sorts of the whole list.
25. **Card Detail's description fits itself.** `CardDetail_RenderText` retries with a smaller line gap, then
    font 8, until the text ends above y 192, and each pass clears the whole 64 KB canvas. To add lines, draw
    them below whatever pass fitted, or join them to the description and let the retries shrink both.
26. **Telling a duel from the rest:** `gDuelScreen.active` is cleared before a duel's Card Detail opens, and
    `gDuelCtrl.phase` is never reset. Test `gMain.callback` and its step: `CB_Campaign` step 4, or
    `CB_LinkBattle` step 3.
27. **The ROM has data the game never uses.** The CPU deck loader takes a "second deck" flag that its only
    caller hard-codes to 0. The compiler can't see that across units, so the alternate table stays linked.
    Before assuming data is live, check the constant arguments at a function's only call site.
28. **A card the CPU's code mentions isn't always a card it plays.** Many lists only rate cards (the "key
    cards" for discards) or read your hand. Check for an actual play, chain or activation rule, then confirm
    in the emulator. Snatch Steal is on those lists and never played (checked in the emulator), and so is
    Sebek's Blessing (from the code).
29. **A CPU trigger can wait for you.** When the CPU's recruiter is destroyed, its chain link shows "Chain:
    Activating" and waits for A from the human player, so a scripted test needs A presses after the battle.

## Assets
None generated. The God art, names and frames are the game's own and come from the user's ROM through the
patch.

## Cost and time
One session: recon, then toolchain, data, code, hooks, oracles, a showcase clip and docs, in a few hours of
wall-clock. The three-Tribute build, the effects builds, the pack viewer and the summon rules with the
quality-of-life changes took one session each. A build takes about 1
minute; an oracle suite with its control takes a few minutes.

## Open questions
- The TCG summon rules (a Special Summoned Obelisk or Slifer leaves in the End Phase, Ra can't be Special
  Summoned) are only in the three-Tribute effects build; `gods-fx` doesn't have them.
- What the second decks were meant for isn't in the ROM. Only the five duelists open from day one have them,
  which fits "early opponents come back stronger", but that's a guess.
- The hook builder is generic enough for any non-relocatable GBA decomp. It could become a technique note
  or a `um` command.
