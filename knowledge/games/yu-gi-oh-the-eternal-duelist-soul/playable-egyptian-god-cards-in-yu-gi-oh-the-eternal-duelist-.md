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
tags: [gba, decomp, rom-hack, bps, function-hooks, trampolines, card-game, ai, delta, mgba, headless-oracle]
---

# Playable Egyptian God cards in Yu-Gi-Oh! The Eternal Duelist Soul via eds-decomp and function hooks

> The mod makes Obelisk, Slifer and Ra playable in EDS (GBA): Level 10, 4000/4000 monsters that the player
> can get by password, put in a deck and Tribute Summon. Kaiba, Yami Yugi and Marik carry one each, and the
> CPU summons them. It's built on the complete matching decomp eds-decomp. Data edits go through its asset
> pipeline; the C edits are hooked into the original ROM layout, because the decomp can't absorb code growth.
> Checked with 8 headless-mGBA oracles (each one also fails on the original ROM) and shipped as a 39 KB
> `.bps`. It works in Delta on iOS: the user summoned a God with two Tributes and attacked with it.

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

## Assets
None generated. The God art, names and frames are the game's own and come from the user's ROM through the
patch.

## Cost and time
One session: recon, then toolchain, data, code, hooks, oracles, a showcase clip and docs, in a few hours of
wall-clock. The build takes about 1 minute; the oracle suite with controls takes about 45 s.

## Open questions
- God effects would need new rows in the 426-row effect-handler table, whose binary-search bound is
  hard-coded in `FindCardEffect`.
- The hook builder is generic enough for any non-relocatable GBA decomp. It could become a technique note
  or a `um` command.
