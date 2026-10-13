# Plan: see what's in a pack, and the odds, before you pick it

**Goal:** on the pick-a-pack screen after a duel, the hovered (centre) pack shows its name, and one button
opens a list of every card in that pack. Each card shows its chance of being in the pack you'd get. From the
list you can open any card's Card Detail and go back to the pick screen.

**Status: plan only. Nothing is built.** It waits for the user's choices (below). Everything here was read
in eds-decomp `857002a` and checked in the headless emulator.

## 1. How the pack reward works today
```
 duel ends ─▶ Campaign_GiveRewards (campaign_steps.c)
                │
                ├─ event duel won (holiday, Rare Hunter, Grandpa Cup...) ─▶ GetRewardPack(fixed id) ─┐
                │                                                         (no list: straight to opening)
                └─ any other win or loss ─▶ "new packs" text if any ─▶ CB_GetPack                    │
                                                                         │                           │
          GetPack_SelectAndGenerate (booster_pack.c), sub-states:         │                           │
            0  PackList_AddUnlockedPacks: the 27-entry list, each gated   ◀┘                           │
               by IsPackUnlocked (your duel record); 23 can ever appear                               │
            1  PackList_Init        three covers, centre highlighted  ◀── the screen to change        │
            2  PackList_HandleInput LEFT / RIGHT slide, A picks (nothing else is read)                │
            3  PackList_FadeOut                                                                       │
            4  GeneratePackCards(centre pack) ◀────────────────────────────────────────────────────────┘
                 RollPackRarity → one card from the rolled rarity slot
                 + four from a shuffled copy of the commons slot; SaveGame
          then the opening scene: reveal 5 rows (GetPack_DrawCardRow), UP/DOWN, A = Card Detail,
          B = done → the cards go into the trunk
```
What the pick screen shows today: three covers (56×112 px each) between two empty bands. No pack names, and no
other buttons.

## 2. The systems involved
| System | Where | What it holds or does |
|---|---|---|
| Pack covers and names | `gPackInfo` `0x080865DC`, 23 × `{id, image, name[0x40]}` | the game's own abbreviations, typos included: "Pharao'sSurvant", "CursrOfAnubis" |
| Pack contents | `gPackContents` `0x081A562C`, 28 × `{PackSlots *, id}`; extracted to `tables/rodata2/booster_packs.json` | 8 rarity slots per pack, slot 0 rarest, slot 7 commons; card **numbers** |
| Rarity thresholds | `0x081A570C`: `{1, 3, 6, 10, 16, 28, 64, 180}` | cumulative, out of 180 |
| Unlocking | `IsPackUnlocked` (`booster_get_pack.c`), `gUnlockablePackIds` `0x081A5758` | Vol.1-3 always, the rest from your record against each duelist |
| Generator | `RollPackRarity`, `PickPackSlotCard`, `GeneratePackCards` (`booster_pack.c`) | see section 3 |
| Save state used by the roll | `gSaveData.lastPackId`, `gSaveData.packPityCount` | the "same pack again" and pity rules |
| Owned check | `IsCardNumberOwned` (`booster_pack.c`) | can mark the cards you don't have yet |
| Card rows | `GetPack_DrawCardRow` (`card_canvas.c`) | name, attribute and type icons, ATK/DEF, level; the rare card in another colour |
| Card Detail | `CardDetail_*`, driven by `GetPack_ShowCardDetail` | the full card view, already reachable from the opening scene |

## 3. How the game picks the cards, and the real odds
1. **The roll.** `r = Random() % 180`. Slots 0-6 are walked in order, and the first *non-empty* slot whose
   threshold is above `r` wins; anything left over goes to the commons. An empty slot's range falls through to
   the next filled one. For Vol.1 (slots 4-7 filled) the rolled card is:

   | Slot | Odds |
   |---|---|
   | slot 4 | 16/180 = 8.9% |
   | slot 5 | 12/180 = 6.7% |
   | slot 6 | 36/180 = 20% |
   | commons | 116/180 = 64.4% |

2. **The rolled card** is a uniform pick from that slot.
3. **The other four** are the first four of a shuffled copy of the commons, skipping copies of the rolled card.
4. **Modifiers, from the save:**
   - **Same pack as last time:** `% 270` instead of `% 180`, so every rare slot is 2/3 as likely.
   - **Pity:** `packPityCount` counts packs that fell back to commons. A roll into slots 0-4 resets it; slots
     5 and 6 don't touch it. Once it is above 5 (above 10 when you pick the same pack again), the roll becomes
     `% 12`. That lands in the first filled slot whose threshold is above it: for Vol.1, a guaranteed slot-4
     card (Dark Magician or Gaia, 50% each).
5. **A quirk worth showing honestly:** the shuffle is only 2 × N random swaps, not a real shuffle, so cards
   near the top of the commons list tend to stay there. A simulation of the game's algorithm (300,000 Vol.1
   packs) gives the first four commons about 16.8% each and the other 26 about 15.2%. A simple formula says
   15.5% for all of them. The displayed odds should come from a model of the game's actual algorithm.

Per-card chance of being in the pack (normal roll), as the viewer would show it for Vol.1:

| Card | Slot | In the pack |
|---|---|---|
| Dark Magician, Gaia The Fierce Knight | 4 | 4.4% each |
| Dark Hole, Fissure, Trap Hole | 5 | 2.2% each |
| Legendary Sword, Beast Fangs, Violet Crystal, Book of Secret Arts, Power of Kaishin | 6 | 4.0% each |
| the 30 commons | 7 | 15.2-16.8% each |

Other facts:
- The pick screen can show at most 23 packs. The largest, Phantom of G, has 65 cards.
- Its rarest card is 0.42%.
- Obelisk (The Final Duelist) and Slifer (Limited Collection) are each 3.33% per pack, 2.22% if you pick the
  same pack again.
- Ra is only in the Yu-Gi-Oh! Magazine pack (802), which an event gives directly; it never appears on the
  pick screen.

## 4. The feature
```
 pick-a-pack screen                       pack contents (new)                 Card Detail (existing)
 ┌──────────────────────────────┐          ┌──────────────────────────────┐    ┌──────────────────┐
 │            SELECT: cards ▸   │  SELECT  │ Vol.1 · 40 cards     ▲       │ A  │                  │
 │  [pack]   [PACK]   [pack]    │ ───────▶ │ ▣ Dark Magician        4.4%  │──▶ │   the card       │
 │  LEFT/RIGHT, A = pick        │          │ ▣ Gaia The Fierce...   4.4%  │ B  │                  │
 │  Vol.1 (40 cards)            │ ◀─────── │ ▣ Dark Hole       NEW  2.2%  │◀── └──────────────────┘
 └──────────────────────────────┘    B     │   UP/DOWN scroll    ▼        │
    the bottom band names the              └──────────────────────────────┘
    hovered pack; it updates as
    the covers slide
```
- **Hover:** the empty bottom band names the centre pack and its card count. The top band shows the button
  hint.
- **The list:** every card in the pack, rarest slot first. Each row uses the game's own pack-opening row
  (picture frame, name, attribute and type, ATK/DEF, level) plus the percentage, and a mark on cards you don't
  own yet. The top-tier cards are coloured like the opening scene colours its rare card.
- **Odds for this pick:** the percentages follow the save. A short line says when a modifier applies: "You
  picked this pack last time: rarer cards are 2/3 as likely", or "Lucky pack: a top-tier card is guaranteed".
- **A** opens Card Detail; **B** goes back to the pick screen with the same pack in the centre. Picking still
  works exactly as before.

## 5. How it would be built
- **The odds table** is computed at build time from the user's extracted `booster_packs.json`. It is generated
  into the mod tree, never committed, the same way as the relocated effect table.
  - It holds three odds per card, in 0.01% steps: normal, same pack again, and pity.
  - The common odds come from an exact model of the 2×N-swap shuffle (each card's position after the swaps is
    a simple Markov chain), cross-checked by a large simulation of the game's own algorithm and RNG.
- **Code** (a new unit, `src/pack_viewer.c`, plus anchored edits like the God effects):
  - `PackList_HandleInput`: SELECT opens the list. It returns a new code that `GetPack_SelectAndGenerate` maps
    to new sub-states. The sub-states are free: today 4 and up mean "generate".
  - `PackList_Init` / the slide's end: draw the centre pack's name in the bottom band. The text uses the
    game's own text drawer (`TextDrawString`).
  - The list scene: the opening scene's video setup and row drawer, with a ring of rows that are redrawn as you
    scroll (the opening scene only ever shows 5).
  - Card Detail: reuse `CardDetail_*` as `GetPack_ShowCardDetail` does.
  - Coming back: re-enter `PackList_Init` with the centre pack kept. Today it resets it in its state 0.
- **Builds:** independent of the Gods, so it can go in every build; see the decisions.

## 6. Tests (headless mGBA, each one shown able to fail on the build without it)
- **Pick screen:** SELECT opens the list for the centre pack; the row count matches the pack; B returns with
  the same pack centred; A still picks it.
- **Rows:** the list's card numbers, in RAM, are the pack's cards in the planned order.
- **Odds:**
  - the shown odds, in RAM, equal the generated table for each save state (fresh, same pack again, pity);
  - a statistical check: open a few thousand packs in the emulator from saved states, and compare the counts
    with the table.
- **Owned mark:** a card added to the trunk loses its mark.
- **Regression:** a duel and a pack pick without pressing SELECT play exactly as before (EWRAM identical).

To reach the pick-a-pack screen in the harness: from the `duel_turn2` library state, give the CPU 1 LP, attack
with a poked Blue-Eyes, and press A through the win dialogue (planning runs did this).

## 7. Risks
- **Room for text on the pick screen.** All four BG layers and sprites are in use (`PackList_InitVideo`).
  - The bottom-band name needs either free tiles in one of those layers, or sprites.
  - Fallback: show the name only in the list header.
- **The long list:** a scrolling ring of rows is new code. The opening scene's row drawer assumes slots 0-4,
  each with its own text tiles, so the ring has to fit in VRAM next to the frames.
- **Odds precision:** the table is a model of the game's code. Simulation and an emulator count check keep it
  honest, and the percentages are shown rounded to 0.1%.

## 8. Effort
About two sessions:
- the generator for the odds table;
- one new unit;
- about 5 anchored edits;
- the list scene;
- the oracles and docs.

## Decisions (waiting for the user)
1. **Button:** SELECT (recommended: unused, and doesn't clash with A to pick) or R?
2. **Row style:** the game's pack-opening rows, 5 per screen with picture frame and stats (recommended), or a
   compact text list, about 9 per screen?
3. **Odds:**
   - live odds for this pick, following the "same pack again" and pity rules (recommended), or the base odds
     only?
   - Show the per-slot summary too ("a slot-4 card: 8.9%")?
4. **Pack names:** the game's own abbreviations ("Pharao'sSurvant") or full names ("Pharaoh's Servant",
   recommended)?
5. **Extras:**
   - the "not owned" mark (recommended);
   - percentages on the opening screen for the cards you just got;
   - the same list for the fixed event packs (they skip the pick screen).
6. **Builds:** in all four builds (new versions of each), or only `gods-3t-fx`, the one you play?
