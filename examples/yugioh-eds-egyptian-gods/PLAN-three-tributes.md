# Plan: three Tributes for the Egyptian Gods

**Goal:** Obelisk, Slifer and Ra need **three** Tributes to Normal Summon or Set, as in the TCG. Every other
monster keeps EDS's rules: no Tribute at levels 1-4, one at 5-6, two at 7+. The rule holds everywhere a God
can be summoned: the player's card menu, the CPU's summon and set steps, and the summon-check that decides
whether "Summon" is offered at all.

**Status: built and verified.** `scripts/build.sh ... --tributes 3` → `gods-3t.bps`. All 15 checks of
`tests/run_oracles.py --tributes 3` pass, and the ones that tell the rules apart fail on the two-Tribute
build. The user confirmed it works in Delta on iOS.

**Decisions (the user's):** ship both builds, and give Ultimate Offering the three-Tribute rule too.

Everything below was read in eds-decomp `857002a`. Where the build differs from the plan, a note says so.

## What the engine already has
The shared Duel Monsters engine still has half of a three-Tribute summon:
- **The record has room.** The pending summon record (`struct SummonAction`) has `tribute3Zone` and
  `hasTribute3` ("never set"), and an unused bit 30 that can hold the third Tribute's owner.
- **Some paths already remove a third Tribute.** The Special Summon from hand (`SummonStep_SpecialFromHand`)
  does. The Normal Summon executors (`ExecuteSummonAction`, `ExecuteSummonActionAskPosition`) remove only
  two.
- **The AI's simulation handles it.** `AiSimSummon` takes up to four Tributes, one nibble each with bit 3 as
  the presence marker.
- **Gods can be Tributes.** `IsTributableMonster` uses the monster test this mod already rewrote.
- **The pattern exists.** Gate Guardian and Valkyrion are three-Tribute summons with their own prompts.

## Where "two" is hard-coded

```
 player                                   CPU
 ──────                                   ───
 CanSummonFromHand  (7+ → 2 tributable)   AiHasTributesFor          (7+ → 2 picks)
        │                                 AiChooseSummonWithTribute (7+ → 2 picks, sim mask)
        ▼                                 AiStepMainPhase  summon    (7+ → 2 picks, packed word)
 CardMenu_SummonMonster                   AiStepMainPhase  set       (7+ → 2 picks, packed word)
   "requires 2 Tributes?" → 1st → 2nd              │
        │                                          │
        └──────────────┬───────────────────────────┘
                       ▼
      QueueNormalSummon / …ChoosePosition   decodes 2 tribute bytes
                       ▼
      ExecuteSummonAction / …AskPosition    tributes 2 monsters
```

## Changes

| # | Unit / function | Change |
|---|---|---|
| 1 | `summon_checks` `CanSummonFromHand` | a God needs more than two tributable monsters (`CountTributableMonsters(player, -1) > 2`) |
| 2 | `effect_hooks` `CardMenu_SummonMonster` | God branch, new steps: "requires **3** Tributes?" → 1st → 2nd → 3rd pick, with B back to the question at each pick. Picks 1-2 stay in `summonTributes`. *Built:* pick 3 waits in `summonSeq` (zone \| owner << 3), which only the Gate Guardian and Valkyrion steps use, rather than `placeZone`. Then queue with a 3-byte Tribute word |
| 3 | `summon_action` `QueueNormalSummon`, `QueueNormalSummonChoosePosition` | decode byte 2 of the Tribute word into `tribute3Zone` / `hasTribute3`, with the owner in bit 30 |
| 4 | `summon_checks` `ExecuteSummonAction`, `ExecuteSummonActionAskPosition` | Tribute the third monster too |
| 5 | `summon_builders` `AiPickTributeMonster` | add a variant that skips two zones (the third pick) |
| 6 | `summon_builders` `AiHasTributesFor` | God: three different picks |
| 7 | `ai_summon` `AiChooseSummonWithTribute` | God: three picks, three nibbles in the simulation mask |
| 8 | `ai_steps` `AiStepMainPhase` (summon and set steps) | God: three picks packed into the Tribute word |
| 9 | `effect_resolve4` `EffectUltimateOfferingResolve` | *Built:* the same three-pick branch for a God. The third pick rides in the high byte of `targets[1]` (the summon zone), and the queue goes through a new `QueueNormalSummonChoosePositionEx`, which takes a 32-bit Tribute word. With only two monsters, Ultimate Offering can't even be activated for a God |
| 10 | new text | "Summoning this monster requires @33 @0Tributes. Do you wish to @2Summon@0?" and "Please select 3rd monster as @3Tribute@0.", in the game's own `@` colour codes |

All of these are functions the hook build already handles. Gods are told apart by card number (1910-1912)
everywhere, not by level, so a future level-10 monster would keep two Tributes.

## Toolkit changes
- **`hookbuild.py`:** allow a `.rodata` section in the blob, placed after `.text`, when the vanilla unit has
  none. New strings are referenced only by blob code, so moving them can't break anything. Data that
  original code expects at a fixed address still stays refused.
- **Patch script:** these edits are hand-written, not rule-based like `patch_source.py`. Put them in their
  own `patch_three_tributes.py`, with short anchors and our own new code, and pin it to `857002a`.
- **`build.sh --tributes 2|3`** builds either variant: `gods.bps` (two Tributes, as shipped) or
  `gods-3t.bps`.

## Tests (headless mGBA, each one shown able to fail)
| Oracle | Setup | Pass when |
|---|---|---|
| Player, 2 monsters | God in hand, 2 fodder | Summon/Set is not offered (only Card View) |
| Player, 3 monsters | God in hand, 3 fodder | "requires 3 Tributes" prompt; three picks; God on the field; 3 fodder in the graveyard |
| Player, back out | B at the 2nd and the 3rd pick | the question comes back; no monster lost |
| CPU, 2 fodder | God in hand, player has Blue-Eyes | the God never reaches the field |
| CPU, 3 fodder | same, with 3 fodder | the God stays on the field 60 frames; 3 fodder gone |
| Regression | Blue-Eyes (level 8) in hand, 2 fodder, player and CPU | still a two-Tribute summon |
| Existing 8 oracles | updated to 3 fodder where they summon | all pass |
| Null-hook / no-God regression | as before | EWRAM identical |

Then a new showcase cut (three Tributes going down) and the user's check in Delta.

## Risks
- **The CPU will summon Gods far less often.** Holding three monsters at once is rare in EDS duels. That's
  the TCG rule working as intended, but it changes how the NPC decks feel. Keeping the two-Tribute build as
  its own patch covers anyone who prefers that.
- **Link Battle:** both GBAs must run the same patch, as with the current mod.
- **The Tribute word's third byte:** every caller that builds that word has to be found. The grep above
  found all of them (the player menu, Ultimate Offering, two AI steps), and the regression oracles cover the
  rest.

## Effort
About one session: 10 function edits, the `.rodata` support in `hookbuild.py`, 6 new oracles and the docs.
