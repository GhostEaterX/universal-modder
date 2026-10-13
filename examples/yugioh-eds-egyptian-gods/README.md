# Playable Egyptian God cards: Yu-Gi-Oh! The Eternal Duelist Soul (GBA)

In the original game, Obelisk the Tormentor, Slifer the Sky Dragon and The Winged Dragon of Ra are cards you
can own but never use. This mod makes them real monsters, for you and for the CPU:

- **Stats:** each God is a Level 10, 4000 ATK / 4000 DEF monster that keeps its Divine type, attribute icon
  and card art. Obelisk keeps its blue frame.
- **Summoning:** pick a build:
  - `gods.bps`: a God takes the game's Level 7+ rule of two Tributes;
  - `gods-3t.bps`: a God takes **three**, the TCG rule. That holds for you, for the CPU and for Ultimate
    Offering's extra summon. Every other monster keeps the game's rules, so Blue-Eyes still takes two.
- **Effects:** `gods-fx.bps` (two Tributes) and `gods-3t-fx.bps` (three) add the Gods' TCG effects, for you
  and for the CPU, and their card text says so:
  - **Obelisk the Tormentor:** Tribute 2 other monsters to destroy all monsters your opponent controls;
    Obelisk can't attack that turn. Card effects can't target it.
  - **Slifer the Sky Dragon:** its ATK and DEF are 1000 × the cards in your hand. When your opponent Normal
    or Special Summons a monster in Attack Position, that monster loses 2000 ATK, and is destroyed if that
    takes it to 0.
  - **The Winged Dragon of Ra:** when you Normal Summon it, you may pay LP until you have 100; its ATK and
    DEF become the amount paid. You can also pay 1000 LP to destroy 1 monster on the field.
  - **All three:** their Normal Summon can't be answered (no Trap Hole on a God), and they can't be Set.
- **Deck building:** up to one copy of each God per deck (the original ban list allowed zero).
- **Getting them:** the password screen gives one copy each, using the TCG passwords: Obelisk `10000000`,
  Slifer `10000020`, Ra `10000010`. The booster packs that already contained them (Obelisk in *The Final
  Duelist*, Slifer in *Limited Collection*) still do, so you may already own them.
- **NPCs:** three opponents each trade one weak card for their God:
  - Kaiba gives up a Koumori Dragon for Obelisk;
  - Yami Yugi gives up Giant Soldier of Stone for Slifer;
  - Marik gives up a Dream Clown for Ra.

  The CPU Tribute Summons the Gods when it needs a bigger monster.
- **Without effects:** `gods.bps` and `gods-3t.bps` keep the Gods effect-less, as the original data defines
  them.

It ships as four patches for your own ROM, `gods.bps`, `gods-3t.bps`, `gods-fx.bps` and `gods-3t-fx.bps`, and
only works with the USA release (game code `AY5E`,
SHA-1 `510fbba212aca9bab95ea12f8fd933e62ee34dea`). You have to dump the ROM from your own cartridge; no ROM is
included or linked here.

## Install on Delta (iPhone / iPad)
1. **Back up your save first.** In Delta, long-press the game and export its save file.
2. **Patch your ROM.**
   - Open [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/) in Safari.
   - Pick your `.gba` as the ROM and one of the four `.bps` files as the patch.
   - Tap **Apply patch** and save the result to Files.
   - The patch carries your ROM's checksum, so the patcher warns you if you pick the wrong ROM.
3. **Import into Delta.** Tap **+**, choose Files and pick the patched `.gba`. It shows up as a separate game,
   because its contents changed.
4. **Bring your save over.** Long-press the new game, import a save file and pick the one you exported. Card
   IDs are unchanged, so your collection and decks carry over.

Any desktop patcher works too: `flips --apply gods.bps your.gba gods.gba`, or the patcher built into your
emulator. The patched ROM is 16 MiB, double the original, because the changed code lives past the old end of
the cartridge.

## How it works
```
 your ROM ──▶ eds-decomp (matching decompilation, MIT) ──▶ assets/ (CSV/JSON) + src/ (C)
                                                             │                 │
                     scripts/apply_gods.py  stats, passwords,│                 │ scripts/patch_source.py
                                            ban list, decks  ▼                 ▼ Divine counts as a monster type,
                                        original layout + new data      Obelisk stops being a "Ritual"
                                                             │                 │
                                                             └──▶ scripts/hookbuild.py ◀┘
                                     63 changed functions re-linked at 0x08800000, each original entry
                                     overwritten with a 16-byte jump to its new copy; every other byte
                                     stays where it was ──▶ gods.gba ──▶ flips ──▶ gods.bps (39 KB)
```

Four things kept the Gods out of play, and the mod changes each one:

| Layer | Original game | Change |
|---|---|---|
| Ban list (`GetCardCopyLimit`) | 0 copies | 1 copy (data) |
| Stats | 0 ATK, 0 DEF, level 0 | 4000 ATK, 4000 DEF, level 10 (data) |
| "Is it a monster?" | 85 checks in 42 files test `type <= Reptile (20)`, so Divine (24) is never a monster | one predicate that also accepts Divine (code) |
| Card kind | Obelisk is hard-coded as a Ritual monster, and those can't be Normal Summoned | an Effect monster like Slifer and Ra, except in the frame-drawing code (code) |

The CPU builds its duel deck with `RemoveOverLimitDeckCards`, so the ban list hid the Gods from NPCs too. The
shared Duel Monsters engine already valued a Divine card at 4000 ATK and level 10; the checks above had just
switched it off.

Why the hooks? eds-decomp rebuilds the ROM byte for byte, but much of its C reads tables through integer
addresses (`0x08621DE0` is the card stats table). The decomp's own notes list relocatable data as future work.
A function that grows by a few bytes shifts every later function and table, and those reads break: the first
naive build moved `gCardStats` by 692 bytes. So the original layout stays put, and only the changed functions
move.

## Build it yourself
Needs Linux, WSL or macOS with git and python3. Then:
1. Install eds-decomp's native toolchain once (`tools/setup_native.sh` in a clone of
   [eds-decomp](https://github.com/CosmicScribe64/eds-decomp)) and source it: `. ~/.eds-tools/env.sh`.
2. Optionally, install [Flips](https://github.com/Alcaro/Flips) for the `.bps`.
3. Run:
   ```sh
   scripts/build.sh /path/to/your-eds-usa.gba ./work                           # gods.gba / .bps
   scripts/build.sh /path/to/your-eds-usa.gba ./work --tributes 3              # gods-3t
   scripts/build.sh /path/to/your-eds-usa.gba ./work --effects                 # gods-fx
   scripts/build.sh /path/to/your-eds-usa.gba ./work --tributes 3 --effects    # gods-3t-fx
   ```
   Each takes about a minute, and all four can share one work directory.

The build pins eds-decomp to commit `857002a` (2026-10-04). Starting from the same ROM, it reproduces the
tested ROMs byte for byte:
- `gods.gba`: SHA-1 `2b905f0111c72fd45fa0745e9c4c9c02b20645e7`;
- `gods-3t.gba`: SHA-1 `1cb038eda3c657e4f06547adce7f775ce38b9cfa`.

### How the three-Tribute build works
`scripts/patch_three_tributes.py` runs after `patch_source.py`. The engine already had a third Tribute slot
in its pending-summon record, unused. The Special Summon from hand even removed it.

| Where | What the edits do |
|---|---|
| Summon check | a God needs three tributable monsters before Summon/Set is offered |
| Player's card menu | "requires **3** Tributes?", then the 1st, 2nd and 3rd picks; B goes back to the question |
| Ultimate Offering | the same three picks for a God; the third rides in a spare byte of the chain entry |
| CPU | a third tribute pick (`AiPickTributeMonsterExcept`) in its summon check, its summon simulation, and its summon and set steps |
| Summon queues and executors | a third byte in the Tribute word, written by every queue so a stale third Tribute never leaks into a later summon; the Normal Summon executors remove it |

The two new prompts are new strings in the relocated code, which `hookbuild.py` now allows when the unit
had no read-only data of its own.

### How the effects build works
`scripts/patch_god_effects.py` runs last. It copies this mod's own code (`src/`) into the decomp as two new
units, and makes 22 anchored edits that connect them to the engine. The plan with all the engine research is
`PLAN-god-effects.md`.

A card's behaviour in EDS is split in two:
- **Its row in an effect table.** Five handlers decide whether it can be activated, check targets, pay
  the cost, pick targets and resolve.
- **`switch (card number)` cases across the engine** for everything else.

```
 Obelisk's Activate          Ra's Normal Summon          Slifer
 (card menu / CPU step)      (summon executor)           (no chain effect)
        │                           │                        │
        ▼                           ▼                        ├─ ATK/DEF ──── GetZoneCardStats
 CanActivateEffect ──┐       Chain_AddPending                │
                     ▼              │                        └─ drain ────── SummonAction_Update
          FindCardEffect (428 rows) ◀┘                                       (after every summon)
                     │
                     ▼
          gCardEffectsMod: 426 original rows (copied from your ROM at build time) + Obelisk + Ra
                     │
                     ▼
          prepare → chainA (cost) → chainB (targets) → the opponent may respond → resolve
```

The original table can't grow: other data starts right where it ends. So the build makes a new one in the
relocated code: the decomp's own copy of the 426 original rows, built from your ROM, plus the two Gods' rows.
A `#define` sends every reader of the old table to the new one, so `hookbuild.py` hooks all 11 of those
functions automatically. `check_effect_table.py` then stops the build unless:
- the 426 copied rows are byte for byte the original;
- the table is sorted;
- every function that read the old table is hooked.

| Where | What the edits do |
|---|---|
| Effect table | Obelisk's and Ra's rows; `FindCardEffect` searches 428 rows |
| Stats (`GetZoneCardStats`) | Slifer: 1000 × hand size; Ra: the LP paid, kept as a zone link that leaves with the card |
| Normal Summon executors | queue Ra's summon trigger; Ultimate Offering's summon skips the position menu for a God |
| After every summon (`SummonAction_Update`) | Slifer's drain; no response window for a God's Normal Summon |
| Card menu | Activate for a face-up Obelisk or Ra; no Set for a God in the hand |
| Target check (`CanCardTargetZone`) | Obelisk can't be targeted |
| CPU | uses Obelisk when it clears more ATK than it Tributes, and Ra's destroy against a 2000+ ATK monster while it keeps more than 2000 LP; pays for Ra when that makes Ra stronger than 4000; summons Slifer only with 4+ cards in hand |
| Card text | the Gods' text in Card View describes the effects (data, in place) |

## Verification
These checks run in eds-decomp's headless mGBA 0.10.5 harness: `tests/run_oracles.py`, with the `.lua` setups
next to it. Each check sets up the duel through RAM, plays with scripted keys and reads the result from RAM.
Every check also runs on the original ROM, where it must fail.

| Check | Mod | Original |
|---|---|---|
| Kaiba's duel deck holds Obelisk | pass | fails |
| Yami Yugi's duel deck holds Slifer | pass | fails |
| Marik's duel deck holds Ra | pass | fails |
| Password `10000020` gives Slifer | pass | fails |
| Player Tribute Summons Slifer | pass | fails (only Card View is offered) |
| CPU Tribute Summons Obelisk / Slifer / Ra | pass | fails |

The three-Tribute build has its own suite: `run_oracles.py ... --tributes 3 --control gods.gba`. Its control
is the two-Tribute build, where every check that tells the rules apart must fail and the shared ones must
pass.

| Check (`gods-3t.gba`) | 3-Tribute build | 2-Tribute build |
|---|---|---|
| Deck, password checks (4) | pass | pass |
| Player: Slifer takes all three fodder | pass | fails (one fodder left) |
| Player: no Summon with only two monsters | pass | fails (it summons) |
| Player: B at the 3rd pick loses nothing | pass | (not compared) |
| CPU: Obelisk / Slifer / Ra take all three fodder | pass | fails |
| CPU: no God with only two fodder | pass | fails |
| Ultimate Offering: a God takes all three | pass | fails |
| Ultimate Offering: no God with two | pass | fails |
| Regression: player's and CPU's Blue-Eyes still take two | pass | pass |

In a duel without Gods, the two builds' EWRAM and frame timing are identical. The user also confirmed the
three-Tribute build works in Delta on iOS.

Also checked:
- **Full player path:** password → Trunk → Deck Edit → Main Deck → the player's 41-card duel deck holds
  Slifer.
- **Battle:** the CPU's Obelisk destroys a Blue-Eyes White Dragon, and the player's LP go from 8000 to 7000.
- **Hook test:** a ROM with the same hooks but the original code relocated (`hookbuild.py --null`) plays
  exactly like the original. Boot, menus, the deal and a full turn with a summon, a battle and the CPU's
  turn leave EWRAM identical except the background drift counter, which is off by 3 because of 2 lag frames
  during the opening deal.
- **Regression:** in a duel without Gods, the mod ROM's EWRAM and frame timing match the hook-test ROM
  exactly.
- **On a real device:** tested by the user in Delta on iOS: they summoned a God with two Tributes from the field, it showed 4000 ATK / 4000 DEF, and they attacked with it.

## Known limits
- **No God effects:** no Obelisk wipe, no Slifer hand-size ATK.
- **X000 in Deck Edit:** the deck list shows the Gods' ATK and DEF as `X000`, the game's own Divine display.
  Card View and duels show 4000.
- **A little lag:** the relocated code costs about 2 frames during the opening deal.

## Credits
- [eds-decomp](https://github.com/CosmicScribe64/eds-decomp) by CosmicScribe64 (MIT): the decompilation,
  asset tools and mGBA harness this is built on.
- [mGBA](https://mgba.io), [Flips](https://github.com/Alcaro/Flips),
  [Rom Patcher JS](https://github.com/marcrobledo/RomPatcher.js).
- Built by an AI coding agent (Claude Code) with the universal-modder toolkit, for and with its human.

Yu-Gi-Oh! and The Eternal Duelist Soul belong to Konami and Kazuki Takahashi. The patch is a delta against your own dump:
it carries the changed bytes and copies everything else from your ROM.
