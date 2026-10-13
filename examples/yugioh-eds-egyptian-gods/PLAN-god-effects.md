# Plan: effects for the Egyptian Gods

**Goal:** Obelisk, Slifer and Ra get their card effects, for the player and the CPU, and the God cards' text
describes them. Every other card plays exactly as before.

**Status: built.** `scripts/build.sh ... --effects` (with `--tributes 2` or `3`) gives `gods-fx.bps` and
`gods-3t-fx.bps`; the oracles are in `tests/run_oracles.py --effects`. Everything here was read in eds-decomp
`857002a`. Where the build differs from the plan, a *Built:* note says so.

**Decisions (the user's):**
- Obelisk: A, destroy all (TCG);
- Slifer: both effects;
- Ra: TCG, its ATK and DEF **become** the LP paid, and it keeps the 1000-LP destroy;
- traits: the three recommended ones (no answer to a God's Normal Summon, Obelisk can't be targeted, a God
  can't be Normal Set); not the End Phase one;
- builds: effects on both Tribute rules.

## 1. How EDS runs a card's effect
There is no single "effect" per card. A card's behaviour is split between one row in an effect table and
`switch (card number)` cases spread through the engine.

### The effect table
`gCardEffects` (`0x0819A9D4`) has 426 rows of 0x18 bytes, sorted by card number:

```
 struct CardEffect { u16 number; u16 flags (always 0);
                     resolve, check, prepare, chainA, chainB }   ← five function pointers, in this order
```

In the order the game uses them:

| Slot | Called | Job | Example |
|---|---|---|---|
| `prepare(card, chainLink, fromHand)` | before the Activate command is offered | may it be activated now? | Raigeki: the opponent has a monster |
| `check(card, pos)` | for each field position | is this a legal target? | Dragon Seeker: a face-up Dragon |
| `chainA(link)` | on activation | pay the cost | pay 500/800/1000… LP |
| `chainB(link)` | on activation | choose targets into `link->targets[3]` | Cannon Soldier: pick a monster to Tribute |
| `resolve(link)` | when the chain resolves | do it; a step machine (`EFFECT_STEP_START` … `DONE`) | Raigeki: destroy one monster per step |

`FindCardEffect` (`effect_hooks.c`) binary-searches it with a hard-coded `hi = 425` and returns the row
index. Eight units, `effect_hooks.c` included, then read `gCardEffects[index]` directly.

```
 Activate chosen ─▶ CanActivateEffect ─────────────▶ Chain_AddPending ─▶ chainA (cost) ─▶ chainB (targets)
   (card menu or    Prohibition, spell speed, damage                                         │
    CPU step)       step, then the row's prepare/check                                       ▼
                                                     resolve ◀── the opponent may respond (EventResponse)
```

### What lives outside the table
| Kind | Example | Where the game decides it |
|---|---|---|
| Ignition: a face-up monster's Activate | Barrel Dragon, Cannon Soldier | the row, plus a `case` in `CanActivateMonsterEffect` (card menu). The CPU only tries the 4 cards of `gAiEffectMonsters` (`0x0819DD64`) in `AiActivateMonsterEffects` |
| Trigger on Normal Summon | Dragon Seeker, Sonic Bird | a `case` in `ExecuteSummonAction` step 2 (and `…AskPosition` step 4) queues a `RESPONSE_SUMMONED` chain entry, which then runs the row |
| Continuous stats | Muka Muka: +300 ATK/DEF per card in hand | no row: a `case` in `GetZoneCardStats` (`card_stats.c`) |
| Reaction to any summon | Jinzo, Pumpking, key 1552 | `case`s in `SummonAction_Update`, which every summon kind (Normal, Flip, Special) passes through before the opponent's response window |
| Targeting immunity | Lord of D. protects Dragons | `CanCardTargetZone` |
| Per-card memory | Riryoku's ATK gift, key 1246's copied stats | zone links (`links[32]` and `linkKinds[32]` per zone), cleared when the card leaves the zone |

## 2. The effects, per God
The current TCG texts (Legendary Decks II era) are the reference. Each God has a recommended version and an
alternative. The templates are existing EDS handlers that already do the same thing for another card.

### Obelisk the Tormentor
| | Effect | Built from |
|---|---|---|
| **A (recommended, TCG)** | Tribute 2 other monsters: destroy all monsters the opponent controls. Obelisk can't attack this turn. | Cannon Soldier's Tribute pick, twice (`EffectTributeTargetChainB`); Raigeki's resolve; key 1552's `DUEL_CMD_SET_CANNOT_ATTACK` (the game clears it at its controller's next turn) |
| B (anime) | Tribute 2 other monsters: 4000 damage to the opponent. Can't attack this turn. | the same, with Cannon Soldier's `LoseLifePoints` |

It's an ignition effect: Activate appears in the menu of a face-up Obelisk during your Main Phase when you
have 2 other monsters to Tribute.

### Slifer the Sky Dragon
| | Effect | Built from |
|---|---|---|
| **Stats (TCG)** | ATK and DEF = 1000 × cards in its controller's hand (so 0 with an empty hand). This is what the game's own `X000` Deck Edit display means. | Muka Muka's `case` in `GetZoneCardStats` |
| **Drain (TCG)** | When the opponent Normal or Special Summons a monster in Attack Position, it loses 2000 ATK; at 0 it is destroyed. | a check in `SummonAction_Update`; the loss is a `ZONE_LINK_ATK_DOWN_200` link with a count of 10, so it lasts while the monster stays on the field |

Alternative stats: 4000 + 1000 per card in hand. It is much stronger, so it isn't recommended.

*Built:* Slifer needs no row in the effect table: neither effect is a chain effect. So the table has 428 rows
(Obelisk and Ra), not 429. The CPU summons Slifer only with at least 4 cards in hand, so it stays at 3000 ATK
or more (a check in `CanSummonFromHand` for player 1).

### The Winged Dragon of Ra
| | Effect | Built from |
|---|---|---|
| **On Normal Summon (TCG)** | You may pay LP until you have 100. Ra's ATK and DEF **become** the amount paid, and stay 4000 if you don't pay. You get a Yes/No prompt; the CPU pays when that makes Ra stronger and it can afford it. | Dragon Seeker's summon trigger; Needle Ball's Yes/No resolve; the amount is kept in a new zone-link kind |
| **Destroy (TCG)** | Pay 1000 LP, target 1 monster on the field: destroy it. Not once per turn. | Tribute to the Doomed's target check, pick and destroy (`EffectTargetableMonster*`, `EffectDestroyTargetResolve`); `EffectPayLifePointsChainA` gets a 1000-LP case |
| Alternative stats: "gains" | ATK and DEF = 4000 + the amount paid (up to 11,900). | the same |
| Alternative: anime | ATK and DEF = the combined ATK and DEF of its Tributes. | the existing `ZONE_LINK_ADD_CARD_STATS` (key 1246), one link per Tribute |

The TCG prints Ra as `?`/`?`, so "become" gives TCG numbers. Because the payment is a choice, a player with
little LP just answers No.

*Built:*
- Ra's two effects share one row; the handlers tell them apart by the chain entry's event
  (`RESPONSE_SUMMONED` for the trigger).
- The payment happens when the trigger resolves, with a Yes/No prompt, as Needle Ball does.
- The destroy pays its 1000 LP once the target is picked (in `chainB`), so the "may it be activated?" check
  still sees the LP before payment.
- Obelisk's two Tributes are paid when its effect is activated (in `chainB`), as a cost.

### Shared God traits (optional, each one separate)
| Trait (TCG) | Change | Recommended |
|---|---|---|
| Their Normal Summon can't be answered (no Trap Hole on a God) | skip the opponent's response window in `SummonAction_Update` for a God's Normal Summon | yes |
| Obelisk can't be targeted by card effects | a `case` in `CanCardTargetZone`, next to Lord of D. It covers every effect that uses the shared target check; the oracles show whether some handler skips it | yes |
| Can't be Normal Set | drop SET from the hand menu and from the CPU's set step for Gods | yes |
| A Special Summoned Obelisk or Slifer goes to the graveyard in the End Phase | `SummonAction_Update` marks it with a zone link; the End Phase loop in `duel_cmd_turn.c` sends it | optional (not built) |
| Ra can't be Special Summoned | many separate summon checks (Monster Reborn, Call of the Haunted…) | later, needs its own research |

## 3. How a new effect gets onto an existing card
This recipe works for any card, not just the Gods.

1. **Write the handlers** in a new unit that only the mod tree has (`god_effects.c`): `prepare`, `check`,
   `chainA`, `chainB` and `resolve` with the slot signatures above. The CPU's choices go inside them
   (`link->player == 1`), as in Needle Ball and Cannon Soldier.
2. **Give the card a row.** The table is full: `gTributeSummonPrompts` starts right after it, at
   `0x0819D1C4`. A second table, `gCardEffectsMod`, goes in the relocated code instead:
   ```
   gCardEffectsMod:
       .incbin "build/assets/tables__card_effect_handlers.bin"   @ the 426 original rows, built from your ROM
       .short 1910, 0
       .word  ObeliskResolve, 0, ObeliskPrepare, 0, ObeliskChainB  @ resolve, check, prepare, chainA, chainB
       @ … Slifer (1911), Ra (1912)
   ```
   The Gods' numbers (1910-1912) are higher than the table's last row (1552), so appending them keeps it
   sorted. The repository gets no game data: the `.bin` is the one the decomp builds from the user's
   extracted assets.
3. **Point the engine at it.** Add `#define gCardEffects gCardEffectsMod` to `effect.h`, repoint
   `duel_response.c`'s alias `gAlias_0819A9D4`, and change `FindCardEffect` to `hi = 428`. Every function
   that reads the table then compiles differently, so `hookbuild.py` relinks and hooks it automatically:
   `duel_main` (resolve), `duel_setup` (chainA/B), `duel_turn_end` (all three), `effect_activation`
   (prepare/check), `effect_hooks` (the search), `effect_resolve5` and `effect_resolve9` (proxy resolves) and
   `duel_response` (link duels).
4. **Wire the cases outside the table:**
   - `CanActivateMonsterEffect` for Obelisk's and Ra's Activate;
   - `ExecuteSummonAction` and `…AskPosition` for Ra's summon trigger;
   - `GetZoneCardStats` for Slifer's and Ra's ATK/DEF;
   - `SummonAction_Update` for Slifer's drain and the no-response trait;
   - `CanCardTargetZone` for Obelisk's immunity.
5. **Teach the CPU.** `AiActivateMonsterEffects` loops over a 4-entry list in ROM, so a God branch goes in
   the code rather than a longer list:
   - Obelisk: use it when the player has 2 or more monsters, or one the CPU can't beat in battle, and the CPU
     has 2 monsters to spare;
   - Ra: destroy the player's strongest monster when it has 2000 ATK or more and the CPU has more than 2000
     LP.
6. **Card text** is data. `descriptions.json` holds fixed 480-byte records (the longest vanilla text is
   473 characters), so `apply_gods.py` replaces the Gods' flavour text in place without moving anything. The
   text follows the build: "3 Tributes" in `gods-3t`, 2 in `gods`.
7. **Toolkit:**
   - `hookbuild.py` links units that only the mod tree's `units.txt` lists (C or `.s`; the decomp's Makefile
     compiles them with its own flags). Everything they define is new, so they get no stubs and no hooks.
   - A self-check fails the build unless the first 426 rows of `gCardEffectsMod` equal the original bytes at
     `0x0819A9D4`.
   - A `scripts/patch_god_effects.py` holds the anchored edits, like `patch_three_tributes.py`.

```
 blob at 0x08800000 (relocated code)
 ┌───────────────────────────────────────────────────────────────┐
 │ gCardEffectsMod  426 original rows (.incbin) + Obelisk/Slifer/Ra│
 │ god_effects.c    the new handlers and the CPU's choices        │
 │ hooked copies    FindCardEffect (hi = 428), the 8 table users, │
 │                  stats, summon, menu, CPU and target functions │
 └───────────────────────────────────────────────────────────────┘
        ▲ 16-byte jump at each original entry; every other byte stays put
```

*Built: the pad links.* `RemoveLinksToZone` skips the link after any link it doesn't read as a card location
(an engine quirk). Without a fix, an Equip put on Ra or on a drained monster later would keep a stale link
once the Equip is gone. So each new link is followed by a pad link (kind 15, value `0xFFFF`), which is the one
that gets skipped.

## 4. Builds
`build.sh --effects` adds the effects on top of either Tribute rule: `gods-fx.bps` (2 Tributes) and
`gods-3t-fx.bps` (3 Tributes). The existing `gods.bps` and `gods-3t.bps` stay as they are. Testing both
doubles the oracle runs but not the work, so the recommendation is to build both.

## 5. Tests (headless mGBA, each one shown able to fail)
The control is the same build without `--effects`.

| Oracle | Setup | Pass when |
|---|---|---|
| Obelisk, player | Obelisk + 2 fodder; CPU has 3 monsters | Activate offered; 2 fodder and all 3 CPU monsters in graveyards; no attack this turn |
| Obelisk, no fodder | Obelisk alone | no Activate |
| Obelisk, CPU | CPU Obelisk + 2 fodder; player has 2 monsters | the player's monsters are gone |
| Slifer stats | Slifer, 2 cards in hand, attacks a 2500 ATK monster | Slifer loses (2000 ATK); with 3 cards it wins |
| Slifer drain | player's Slifer face up; CPU summons a 1800 and a 2500 ATK monster | the 1800 is destroyed; the 2500 fights as 500 |
| Ra pay | player Normal Summons Ra at 8000 LP, answers Yes | LP 100; Ra fights as 7900 |
| Ra destroy | Ra face up; pay 1000 | target destroyed; LP − 1000 |
| No response | CPU has a set Trap Hole; player summons a God | the God stays (Trap Hole is never offered) |
| Text | Card View | the new text shows |
| Regression | the existing 8 and 15 oracles; a God-free duel | all pass; EWRAM and frames identical to the build without effects |

The last check matters most: every effect in the game runs through the relocated table, so a God-free duel
has to match byte for byte.

## 6. Risks
- **Hot path.** The relocated table serves every card's effect. The 426-row self-check and the byte-identical
  God-free regression cover it.
- **Slifer at 0.** The CPU values a God at 4000 when it decides to summon (`AI_DIVINE_VALUE`). It could
  summon a Slifer with an empty hand. A hand-size check goes in the CPU's God summon branch.
- **CPU heuristics** are simple rules, not the game's original AI quality.
- **Link Battle:** both GBAs must run the same patch. Link duels exchange chain entries through the table.
- **Partial immunity:** a few old handlers may not use `CanCardTargetZone`; the oracles and Card View
  wording stay honest about what is covered.

## 7. What it took
One session:
- one new unit of handlers and hooks (`src/god_effects.c`) and the relocated table (`god_effects_table.s`);
- 22 anchored edits in 10 files (`scripts/patch_god_effects.py`): 15 more hooked functions than the
  2-Tribute build (78), 13 more than the 3-Tribute build (86);
- `hookbuild.py` support for units only the mod tree has, and `check_effect_table.py`;
- 18 effect oracles plus the base suite on each effects build.
