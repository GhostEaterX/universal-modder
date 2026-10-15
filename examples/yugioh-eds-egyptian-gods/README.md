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
- **TCG summon rules (`gods-3t-fx.bps`):** a Special Summoned Obelisk or Slifer (Monster Reborn, Call of the
  Haunted...) is sent to the Graveyard in the End Phase, and Ra can't be Special Summoned, for you and for the
  CPU. The card text says so. Deck Edit sorts the Gods among the monsters and lists Obelisk as an Effect
  Monster.
- **Pack viewer (`gods-3t-fx.bps`):** on the pick-a-pack screen after a duel, the bottom band names the pack
  in the centre and how many of its cards you own ("23/40 owned"). SELECT lists every card in it, with each
  card's chance of being in the pack you'd get, and either NEW (you don't own it) or how many copies you
  have. The chances follow your save: picking the same pack as last time makes rare cards less likely, and
  after a run of all-common packs the game guarantees a rare one. A opens a card's Card Detail, and B goes
  back to the pick screen.
- **Found in (`gods-3t-fx.bps`):** every Card Detail outside a duel (Trunk, Deck Edit, the pack list) ends with
  the packs that hold the card and its chance in each, e.g. "Found in: Vol.7 12.1% (locked)".
- **Second decks (`gods-3t-fx.bps`):** the original game holds a stronger second deck for each of the five
  duelists you can face from the start (Yugi, Tea, Joey, Tristan and Bakura), but never loads it. Beat one of
  them 10 times (the wins on the opponent-select screen) and from the next duel on they play their second
  deck: Yugi brings the Magnet Warriors and Valkyrion, Joey B. Skull Dragon and Red-Eyes Black Metal Dragon,
  and the others more Magic and Trap cards like Mirror Force, Raigeki and Dark Hole. After that 10th win,
  their usual 10th-win line gets a new last page that says so: "I better find some new cards and train
  more."
- **CPU deck tuning (`gods-3t-fx.bps`):** 63 cards change in 26 of the 29 CPU decks.
  - 42 of them were cards the CPU can never play, such as Snatch Steal (in 15 decks), Spellbinding Circle and
    Solemn Judgment.
  - The rest trade generic cards for ones that fit the duelist: Time Wizard for Joey, Fissure and Giant Rat for
    Rex, Barrel Dragon for Espa Roba, Mother Grizzly for Mako, and Harpie Lady Sisters for Mai, so that her
    Elegant Egotist combo can finish.
  - Every new card is one the CPU plays.
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
- `gods-3t.gba`: SHA-1 `1cb038eda3c657e4f06547adce7f775ce38b9cfa`;
- `gods-fx.gba`: SHA-1 `7e74a01ce70057d515dadd267ad7fdba93b89d99`;
- `gods-3t-fx.gba`: SHA-1 `2082fb6fd7f0b9becc9f0ef7f3c80371e0f62f88`, with the summon rules, the pack
  viewer, Found in, the second decks, their 10th-win lines and the CPU deck tuning; the user ran it in
  Delta. Earlier versions:
  - `8710dd2f4335187d5254c7a44ede052e11af77a1`: before the deck tuning; the user ran it in Delta;
  - `637b7bd60fb9a73710bdabc2ad759e9eb1ca0e8d`: the second decks without the new lines;
  - `27007baa47952ebfe051c3f1eaa399eef011ef99`: before the second decks; the user checked the summon rules on
    it in Delta;
  - `000ae97d786f1d922dd31a8d74f38a5e1ab9ae36`: the first pack viewer;
  - `471f4347758993363e2bbaac30167f1635575c43`: effects only, the one the user first ran in Delta.

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

### How the summon rules work (gods-3t-fx)
`scripts/patch_god_rules.py` runs after the effects patch, in the `gods-3t-fx` build only. It copies
`src/god_rules.c` into the decomp as a new unit and makes 7 anchored edits in 5 files.

| Where | What the edits do |
|---|---|
| `CanReviveGraveyardCard` | Ra can't come back from the Graveyard. This one check builds the target lists of Monster Reborn, Call of the Haunted, Premature Burial, The Shallow Grave and Spear Cretin, for you and for the CPU, so Ra drops out of all of them |
| Time Machine | the one revival without that check: not for Ra |
| `DuelPhase_End` | each player's face-up Special Summoned Obelisk or Slifer goes to the Graveyard |
| `AiPickDiscard` | the CPU doesn't discard a God to revive it |
| Deck Edit's filter and sort | the Gods sort among the monsters (by ATK, DEF, level...), and Obelisk is an Effect Monster, not a Ritual one (its frame stays blue) |

The other Special Summons (from the deck, the hand or the Fusion Deck) already exclude a level-10,
4000-ATK Divine monster, or name their cards. The engine marks every Special Summon on the card
(`specialSummoned`), which is what the End Phase reads. `apply_gods.py --text 3` adds the two rules to the
Gods' card text.

### How the second decks work (gods-3t-fx)
The game has two tables of CPU decks: `gOpponentDecks`, one deck per duelist, and `gOpponentAltDecks`, a
second deck for each of the five Tier 1 duelists. `LoadOpponentDeck(useAltDeck)` can read either, but its only
caller, `Campaign_SetupDuel`, always passes 0, so the second decks were never played.
`scripts/patch_second_decks.py` runs in the `gods-3t-fx` build only. It copies `src/second_decks.c` into the
decomp as a new unit and changes that one call:

```
 Campaign_SetupDuel  (every duel against the CPU)
    │
    └─ LoadOpponentDeck(OpponentUsesSecondDeck())       the original: LoadOpponentDeck(0)
          │
          ├─ 0 ─▶ gOpponentDecks[duelist]      everyone else, and Tier 1 below 10 wins
          └─ 1 ─▶ gOpponentAltDecks[duelist]   Yugi, Tea, Joey, Tristan, Bakura from 10 wins
```

`OpponentUsesSecondDeck` returns 1 when the opponent is duelist 1 to 5 (the second-deck table has no other
entries) and your record against them (`gSaveData.duelRecords[duelist].wins`, the number on the
opponent-select screen) is 10 or more. The game counts a win when a duel ends (a best-of-3 match counts once,
at its end), so the duel after your 10th win is the first against the second deck. The decks are the game's
own: each second deck keeps 25 to 32 of the first deck's cards and adds these.

| Duelist | The second deck adds |
|---|---|
| Yugi | Alpha, Beta and Gamma The Magnet Warrior, Valkyrion the Magna Warrior; Raigeki, Dark Hole, Mirror Force, Change of Heart, Snatch Steal, Imperial Order, Magic Jammer; Sangan, Witch of the Black Forest ×2 |
| Tea | Dunames Dark Witch ×2, Gemini Elf, The Unhappy Maiden, Witch of the Black Forest ×2; Dark Hole, Heavy Storm, Graceful Charity, Mirror Force, Magic Jammer, Spellbinding Circle, Trap Hole |
| Joey | B. Skull Dragon (in his Fusion Deck; he keeps Polymerization, Summoned Skull and two Red-Eyes), Red-Eyes Black Metal Dragon with Metalmorph, a second Red-Eyes B. Dragon, Cyber-Tech Alligator, Magician of Faith, Man-Eater Bug ×2, Sinister Serpent; Harpie's Feather Duster, Gryphon Wing, Kunai with Chain |
| Tristan | Summoned Skull, Darkfire Soldier #1, Man-Eater Bug ×2, Mr. Volcano, Nimble Momonga, Sinister Serpent; Raigeki, Dark Hole, Harpie's Feather Duster, Pot of Greed, Snatch Steal, Premature Burial, Swords of Revealing Light, Delinquent Duo |
| Bakura | Blast Sphere, Needle Worm ×2, Witch of the Black Forest ×2; Mirror Force, Premature Burial, Weather Control |

No second deck goes over the ban list, so `RemoveOverLimitDeckCards` loads each one whole.

**The 10th-win line.** After a duel, `Campaign_ShowDuelResult` picks the opponent's line from
`gOpponentResultTexts`, and the game already has one for your 10th win against each duelist (`win10th`, shown
when the record still says 9, just before it becomes 10). `apply_gods.py --text 3` adds a last page to the
five Tier 1 duelists' 10th-win lines, so the duelist announces the switch at the moment it happens. Each line
keeps the game's own pages; only the last page is new:

| Duelist (dialogue event) | The new last page |
|---|---|
| Yugi (1017) | "I better find some new cards and train more. Next time, I'll be ready for you!" |
| Tea (2017) | "Just kidding! I better find some new cards and train more. Next time, I'm going to win!" |
| Joey (3017) | "Nah, forget that! I better find some new cards and train more. Next time, ya won't know what hit ya!" |
| Tristan (4017) | "Then again... I better find some new cards and train more. Next time, I'm not going easy on you!" |
| Bakura (5016) | "I better find some new cards and train more. Next time, I'll give you a real challenge." |

Dialogue records are a fixed 0x304 bytes (`{u16 event; u16 speaker; char text[0x300]}`), so a longer text moves
nothing: the ROM differs from the build without the lines in those five records only. `$c$p` is the game's own
"wait for A, new page" code.

### How the CPU deck tuning works (gods-3t-fx)
The CPU only plays a card that its code has a rule for: a list it tries every turn, a condition for a Trap,
an answer to one of your cards, a flip it plans, a scripted combo. A card with no rule sits in its hand
forever. `apply_gods.py --text 3` swaps cards in the CPU decks (`deck_lists.json`), one for one, so the deck
region still fits.

**The dead slots (42 copies).**

| Card | Copies | Notes |
|---|---|---|
| Snatch Steal | 15 | Only on the CPU's lists for reading your hand and deck. Checked in the emulator: it holds it with your Blue-Eyes on the field and sets a monster instead |
| Spellbinding Circle | 5 | |
| Kunai with Chain, Solemn Judgment | 4 each | |
| Horn of Heaven, Sebek's Blessing, Metalmorph | 3 each | |
| Time Machine, 7 Completed | 2 each | |
| Megamorph | 1 | Played only in Kaiba's Cyber-Stein combo, so dead in Pegasus's deck |

**The swaps.** Every card brought in is one the CPU plays, and none goes over the ban list.

| Deck | Out → In |
|---|---|
| Yugi, 2nd deck | Snatch Steal → Call Of The Haunted |
| Tea, 2nd deck | Spellbinding Circle → Gift of The Mystical Elf |
| Joey | Raigeki → Time Wizard (2nd copy) |
| Joey, 2nd deck | Kunai with Chain → Time Wizard; Metalmorph → Skull Dice |
| Tristan, 2nd deck | Snatch Steal → Invader of the Throne; Harpie's Feather Duster → Trap Master |
| Bakura, both decks | Spellbinding Circle → Call Of The Haunted; Dark Elf → Mystic Tomato |
| Rex Raptor | Snatch Steal, Raigeki → Fissure ×2; Witch of the Black Forest ×2 → Giant Rat ×2 |
| Espa Roba | 7 Completed ×2 → Barrel Dragon ×2; Time Machine → Mechanicalchaser |
| Weevil | Snatch Steal, Gemini Elf ×2 → Flying Kamakiri #1 ×3 |
| Mako | Kunai with Chain ×2, Snatch Steal → Mother Grizzly ×3; Dark Elf → Giant Red Seasnake |
| Mai | Snatch Steal → Harpie Lady Sisters; Witch of the Black Forest ×2 → Flying Kamakiri #1 ×2 |
| Rare Hunter | Horn of Heaven → Negate Attack |
| Arkana | Snatch Steal → Dark Magician Girl; Giant Soldier of Stone ×3 → Mystical Elf ×3 |
| Strings | Snatch Steal → Call Of The Haunted |
| Umbra & Lumis | Spellbinding Circle, Horn of Heaven → Mask of Darkness ×2; Snatch Steal → Reaper of the Cards; Gemini Elf ×2 → La Jinn ×2 |
| Marik | Snatch Steal → Invader of the Throne; Sebek's Blessing → Call Of The Haunted |
| Kaiba | Solemn Judgment → Negate Attack; Snatch Steal → Premature Burial; Sebek's Blessing ×2 → Lord of D., Koumori Dragon |
| Ishizu | Metalmorph ×2 → Numinous Healer ×2; Solemn Judgment, Horn of Heaven → Negate Attack ×2 |
| Shadi | Solemn Judgment → Reaper of the Cards |
| Yami Bakura | Kunai with Chain → Reaper of the Cards; a Heavy Storm → Mystic Tomato; Vorse Raider ×3 → La Jinn ×3 |
| Yami Yugi | Snatch Steal → Call Of The Haunted |
| Duel Computer | Snatch Steal → Mask of Darkness |
| Simon | Snatch Steal → Negate Attack |
| Pegasus | Time Machine, Solemn Judgment, Megamorph → Toon Mermaid ×3 |
| Grandpa | Spellbinding Circle → Negate Attack; Snatch Steal → Call Of The Haunted |

**Left alone:**
- the regular decks of Yugi, Tea and Tristan;
- the Gods;
- the CPU's scripted combos (Cyber-Stein, the Magnet Warriors and Valkyrion, Toon World);
- the Exodia engines (Rare Hunter keeps Witch of the Black Forest and Sangan).

**Mai's combo:** the CPU already plays Elegant Egotist with a Harpie Lady out. The card brings Harpie Lady
Sisters from the deck, and Mai's deck had none, so the combo could never finish.

**The data:** `DECK_TUNING_3T` lists each changed card's count before and after, per deck. A deck is changed
only when it holds the "before" counts, and skipped when it already holds the "after" ones. The new lists are
sorted, like the original ones.

### How the pack viewer works
`scripts/patch_pack_viewer.py` runs in the `gods-3t-fx` build only. It copies `src/pack_viewer.c` into
the decomp as a new unit, writes its odds table from your ROM's pack lists, and makes 8 anchored edits in 5
files. The plan, with the research on how the game makes a pack, is `PLAN-pack-viewer.md`.

```
 pick-a-pack screen                        the pack's cards                         Card Detail
 ┌────────────────────────────────────┐    ┌──────────────────────────────────┐    ┌────────────┐
 │   [pack]      [PACK]      [pack]   │    │ Vol.1                            │    │  the card  │
 │                                    │ ─▶ │ 40 cards  rare card 35.6%        │ ─▶ │            │
 │               Vol.1                │ ◀─ │ % = chance it's in your pack     │ ◀─ │ LEFT/RIGHT:│
 │ 40 cards  -  SELECT: cards and odds│    │ ▣ Dark Magician       NEW  4.5%  │    │ next card  │
 └────────────────────────────────────┘    │ ▣ Gaia The Fierce...  NEW  4.5%  │    └────────────┘
  SELECT ─▶, B ◀─                           │ ▣ Dark Hole           NEW  2.2%  │     A ─▶, B ◀─
  LEFT/RIGHT slide and A picks, as before   └──────────────────────────────────┘
                                             UP/DOWN: a card, LEFT/RIGHT: a page
```

**How a pack is made** (`GeneratePackCards`), and so what the odds mean:
1. A rarity roll, `Random() % 180`, picks one of the pack's 8 slots (0 is the rarest, 7 the commons). It
   becomes `% 270` when you pick the same pack as last time, which makes every rare slot 2/3 as likely. After
   more than 5 packs in a row that fell back to commons (more than 10 for the same pack again), it becomes
   `% 12`, which always lands in a rare slot.
2. One card from the rolled slot.
3. Four commons: the first four of a copy of the commons slot after 2N random swaps, skipping the rolled
   card. 2N swaps don't shuffle evenly, so the first commons in the game's list come up a little more often
   (Vol.1: 16.8% instead of 15.3%).

`scripts/gen_pack_odds.py` computes each card's chance exactly: the slot sums use the RNG's 15-bit modulo
weights, and the commons use two small Markov chains (one card's position after the swaps, and the pair
card + rolled card). It checks the chains against brute force (`--selftest`), and a simulation of the game's
algorithm with its own RNG agrees on all 2,982 numbers (`--simulate 400000`: 23 packs × 3 rolls). The table
is generated at build time and never committed, like the effect table. `--show <pack id>` prints a pack's
list.

| Where | What the edits do |
|---|---|
| `PackList_HandleInput` | SELECT opens the viewer (unless the covers are sliding) |
| `GetPack_SelectAndGenerate` | the viewer runs on new sub-states (0x20 and up), before the pack is made |
| `PackList_Init` | back from the viewer, the same pack is in the centre |
| `PackList_DrawCovers` | the band text, drawn into the pick screen's 4bpp text layer |
| `GetPack_DrawCardRow` | in the viewer, a canvas clear of the row's 3 KB instead of 64 KB (3 frames per row); for a God, its Divine icon, stats and stars, which the original row leaves out |
| `CardDetail_DrawInfo` | outside a duel, the description is followed by "Found in": the three packs with the best chance (normal roll), "(locked)" for a pack you can't pick yet, and how many more |

The list is the opening scene: its video setup, its row drawer and its Card Detail steps. To avoid tearing,
a scroll moves the four rows that stay in the VBlank callback and draws only the new one, while it is blank.

Found in is a yellow paragraph under the description. When a long description leaves no room for it, it
joins the description, and the game's own text fitting (a tighter line gap, then a smaller font) makes both
fit. It is left out inside duels (the Campaign's or a Link Battle's duel step).

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

The effects builds have their own suite: `run_oracles.py ... --effects --control gods.gba` (add
`--tributes 3` and use `gods-3t.gba` for the three-Tribute pair). Its control is the same build without
effects. Every effect check must fail there, and the regressions (ordinary cards whose effects now go through
the relocated table) must pass on both. Each effects build also runs its base suite.

| Check (`gods-fx.gba`, `gods-3t-fx.gba`) | Effects build | Same build without effects |
|---|---|---|
| Obelisk: Tribute 2, all 3 CPU monsters destroyed, Obelisk can't attack | pass | fails (no Activate) |
| Obelisk: no Activate with only 1 other monster | pass | pass |
| CPU: Obelisk Tributes 2 and clears the player's Blue-Eyes and Celtic Guardian | pass | fails |
| Slifer with 3 cards in hand beats Dark Magician by 500; with 2 it loses by 500 | pass | fails |
| Slifer: a summoned 1800-ATK monster is destroyed; a 2500-ATK one drops to 500 | pass | fails |
| Ra: Yes at 8000 LP leaves 100 LP and a 7900-ATK Ra | pass | fails |
| Ra: pay 1000 LP, Blue-Eyes destroyed | pass | fails |
| CPU: Ra pays down to 100 and hits Blue-Eyes with 7900; Ra's destroy clears Blue-Eyes | pass | fails |
| CPU: no Slifer with a 3-card hand | pass | fails |
| Trap Hole can't answer a God's Normal Summon | pass | fails (Trap Hole destroys it) |
| Tribute to The Doomed can't target Obelisk | pass | fails (Obelisk destroyed) |
| A God can't be Set | pass | fails (it is Set) |
| Card text in the ROM says "Requires 2 / 3 Tributes ..." | pass | fails |
| Regression: Trap Hole still destroys Summoned Skull; Tribute to The Doomed still destroys Blue-Eyes | pass | pass |

In God-free library states, from the title screen through a full player and CPU turn, EWRAM is identical with
and without effects. IWRAM differs only in the audio DMA buffer and the stack. In Delta on iOS the user ran
`gods-3t-fx` and summoned Ra.

The pack viewer has its own suite, `--pack-viewer` (with `--tributes 3 --effects`, control `gods-3t.gba`). It
wins a duel at once from the `duel_turn2` library state to reach the pick screen. The logger reads the odds,
NEW and header text back off the screen (the BG0 map and the glyph tiles in VRAM), and the expected odds come
from your own `booster_packs.json`. The two pick checks pin the RNG when the pick starts, because the
viewer's text costs a lag frame, and the game's RNG ticks once per frame.

| Check (`gods-3t-fx.gba`) | Viewer build | Build without it |
|---|---|---|
| The band names the centre pack | pass | fails |
| SELECT opens the centre pack's list (Vol.1, 40 cards + header) | pass | fails |
| Header and odds, normal roll ("rare card 35.6%", Dark Magician 4.5%) | pass | fails |
| Scrolling through all 40 cards: each one in order, with its odds on screen | pass | fails |
| Same pack again: the header says so, rare card 23.8%, Dark Magician 3.0% | pass | fails |
| Pity roll: a rare for sure, Dark Magician 50.0% | pass | fails |
| Same pack with pity 6 is still "same pack"; with 11 it is the pity roll | pass | fails |
| The header's owned count equals the rows without NEW, over the whole list | pass | fails |
| NEW on a card you don't own; x1 once it is in your trunk | pass | fails |
| A God's row (Obelisk, The Final Duelist) shows its stats, 4000/4000 | pass | fails |
| Card Detail from the list has the Found in paragraph | pass | fails |
| Card Detail from the list, RIGHT to the next card, B back to it in the list | pass | fails |
| B goes back with the same pack in the centre, and A picks it: the same 5 cards as the original game | pass | pass |
| Regression: a pick without SELECT gives the same 5 cards | pass | pass |

Not yet checked for the viewer: a real device, and most packs other than Vol.1-3 in the emulator (the test
save unlocks only those; one check puts The Final Duelist on the pick screen, and the other lists come from
the same table and code).

The summon rules and the Deck Edit changes have their own suite, `--god-rules` (same control). Monster Reborn
is played from the hand onto a Graveyard staged in RAM; the Deck Edit checks read the Trunk list as shown,
after the List Filter; Found in is read off the text canvas, as yellow pixels.

| Check (`gods-3t-fx.gba`) | Rules build | Build without them |
|---|---|---|
| Monster Reborn still revives Blue-Eyes | pass | pass |
| Monster Reborn can't revive Ra (it can't even be activated with only Ra in the Graveyards) | pass | fails (Ra comes back) |
| The CPU's Monster Reborn, with Ra and Blue-Eyes in its Graveyard, brings back Blue-Eyes | pass | fails (it picks Ra) |
| A revived Obelisk, and a revived Slifer, go to the Graveyard in the End Phase | pass | fails (they stay) |
| A revived Blue-Eyes stays; a God that wasn't Special Summoned stays | pass | pass |
| The card text says "Cannot be Special Summoned." and "...sent to the Graveyard during the End Phase." | pass | fails |
| Deck Edit, ATK sort: Obelisk, Slifer, Ra, Blue-Eyes, Dark Magician, 7 Colored Fish, Monster Reborn | pass | fails (the Gods last) |
| Deck Edit, Effect Monsters: Obelisk, Slifer, Ra | pass | fails (no Obelisk) |
| Card Detail from Deck Edit has Found in ("Found in: Vol.7 12.1% (locked)" for 7 Colored Fish) | pass | fails |
| Card Detail inside a duel has no Found in | pass | pass |

On a real device: in Delta on iOS, the user confirmed that Ra can't be revived.

Not yet checked for the rules: the End Phase rule on a real device; Call of the Haunted, Premature Burial,
The Shallow Grave and Spear Cretin on Ra (they read the same list as Monster Reborn); Time Machine on Ra (its
own check, reviewed in the code only).

The second decks have their own suite, `--second-decks` (same control). `npc_deck.lua` sets your record
against a duelist, starts a Campaign duel against them from the main menu, and reads the CPU's deck and Fusion
Deck once they are loaded. The expected lists come from your own `deck_lists.json`.

| Check (`gods-3t-fx.gba`) | Second-deck build | Build without it |
|---|---|---|
| Yugi, Tea, Joey, Tristan and Bakura at 10 wins: the CPU's deck is their second deck, card for card (Joey's Fusion Deck: B. Skull Dragon) | pass | fails (the first deck) |
| Tea at 9 wins: her first deck | pass | pass |
| Rex at 10 wins (no second deck): his deck | pass | pass |
| Kaiba at 10 wins: his deck, with Obelisk | pass | pass |

For the 10th-win lines, `dialogue.lua` wins a duel at once against the duelist with the record at 9 and
follows the dialogue printer (`gBustup.textBox.text`) through the record on screen. A check passes when the
printer reaches the end of the line in your `dialogue.json`, so every page was shown, and the record then
says 10.

| Check (`gods-3t-fx.gba`) | Build with the lines | Build without them |
|---|---|---|
| Yugi, Tea, Joey, Tristan and Bakura: the 10th-win line is shown to the end of its new page, then the record is 10 | pass | fails (the line ends before the new page) |
| Tea's 11th win: her usual win line | pass | pass |
| Rex's 10th-win line, as before | pass | pass |

All five new pages fit the text box, checked on screenshots; Joey's and Tristan's take all four of its lines.

The deck tuning has its own suite, `--deck-tuning` (same control). `npc_deck.lua` checks the 21 tuned
regular decks card for card against your `deck_lists.json`; the five second decks are covered by the
second-deck checks, which read the same file. The CPU cards that are new to their decks get a scripted turn
each: `effects.lua` stages the field, and its `C_DECK` writes the CPU's deck so a recruit has something to
find.

| Check (`gods-3t-fx.gba`) | Tuned build | Build without it |
|---|---|---|
| The 21 tuned regular decks load card for card | pass | fails (the old decks) |
| Giant Rat, Mother Grizzly, Flying Kamakiri #1 and Mystic Tomato, destroyed in battle, summon a monster from the CPU's deck | pass | pass |
| With a Harpie Lady out, the CPU plays Elegant Egotist and brings Harpie Lady Sisters from its deck | pass | pass |
| The CPU plays Toon World (1000 LP), then summons Toon Mermaid | pass | pass |
| The CPU's Fissure destroys your face-up Blue-Eyes | pass | pass |

The behaviour checks pass on the old build too: the CPU could always play these cards; its old decks just
didn't hold them. On a real device, the user tested the tuned build in Delta on iOS: it works.

Also played: Joey's second deck through a whole duel against a player who only ends turns. The CPU summoned
Tiger Axe, Sinister Serpent and Dragon Zombie and won. On a real device, the user tested this build (with the
10th-win lines) in Delta on iOS: it works. Not yet checked in the emulator: reaching 10 wins by playing (the
tests set the record).

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
- **Effects only in the `-fx` builds.** `gods.bps` and `gods-3t.bps` have no God effects.
- **The summon rules, the pack viewer, Found in, the second decks and the deck tuning are only in
  `gods-3t-fx`.** The pack list is only on the pick-a-pack screen: the fixed packs some event duels give skip it. Found in names only
  those pick-screen packs, so a card that comes only from an event, a trade or a password says it isn't in
  them.
- **The odds are rounded** to 0.1% (0.01% below 1%). They are the chance for the next pack you pick; the
  pity counter changes after each pack.
- **The tuned decks trade some raw power for character:**
  - Rex and Joey's regular deck give up Raigeki.
  - Weevil, Umbra & Lumis and Yami Bakura trade 1900-ATK Normal monsters for themed ones with 100 to 500 less
    ATK.
  - Barrel Dragon and Time Wizard depend on coin tosses.
- **Not checked in the emulator for the tuning:** the CPU playing Time Wizard, Barrel Dragon, Call Of The Haunted,
  Negate Attack, Invader of the Throne, Trap Master, Mask of Darkness and the other swapped-in cards that have a
  rule in its code (they are in its play lists, flip plans or Trap conditions); only the cards listed in the
  verification table were played in scripted turns.
- **The 10th-win line comes once:** it is shown when your record against the duelist goes from 9 to 10. A
  save that is already past 10 wins gets the second deck without the line. A record only grows, so once a
  duelist has 10 wins they keep the second deck.
- **A little lag:** drawing the pack name costs about 1 frame when the pick screen opens and when the
  covers stop sliding.
- **The TCG summon rules are not in `gods-fx`:** there a Special Summoned Obelisk or Slifer stays, and Ra can
  be Special Summoned.
- **Obelisk's immunity uses the game's shared target check.** So a Tribute picked through it, Cannon
  Soldier's or Catapult Turtle's, can't pick Obelisk either.
- **Slifer has 0 ATK with an empty hand,** as in the TCG. The CPU only summons it with 4 or more cards in hand.
- **The CPU's effect choices are simple rules** (see "How the effects build works"), not tuned play.
- **Link Battle:** both GBAs need the same patch.
- **The Gods' printed stats:** Deck Edit and Card Detail print Obelisk 4000, Slifer `X000` and Ra `????`,
  the game's own Divine display. In the effects builds that is what they mean (1000 × your hand, the LP paid);
  in `gods.bps` and `gods-3t.bps` all three are 4000. The duel's info bar shows the current values.
- **A little lag:** the relocated code costs about 2 frames during the opening deal.

## Credits
- [eds-decomp](https://github.com/CosmicScribe64/eds-decomp) by CosmicScribe64 (MIT): the decompilation,
  asset tools and mGBA harness this is built on.
- [mGBA](https://mgba.io), [Flips](https://github.com/Alcaro/Flips),
  [Rom Patcher JS](https://github.com/marcrobledo/RomPatcher.js).
- Built by an AI coding agent (Claude Code) with the universal-modder toolkit, for and with its human.

Yu-Gi-Oh! and The Eternal Duelist Soul belong to Konami and Kazuki Takahashi. The patch is a delta against your own dump:
it carries the changed bytes and copies everything else from your ROM.
