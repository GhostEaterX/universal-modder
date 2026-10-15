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

## 2026-10-13: build and verification
- **ROM:** the user uploaded their USA dump; the SHA-1 matches `510fbba2…` and the header says `AY5E`. It lives in
  `~/eds-decomp-src/eds-decomp/roms/` (gitignored by the decomp) and is never committed.
- **Toolchain:** Docker has a CLI but no daemon, so `tools/setup_native.sh` (EDS_MINIMAL=1: apt plus
  `pret/agbcc`). `make setup` then `make compare` gave `eds.gba: OK` in 15 s.
- **mGBA 0.10.5 for `tools/emu.py`:** the GitHub tarball got a 403 from the proxy, so `git clone --branch
  0.10.5` and the cmake flags from `docker/emu/Dockerfile`, installed to `~/.mgba`. It runs with
  `EDS_NATIVE=1 MGBA_PREFIX=~/.mgba`. The venv needs Pillow for contact sheets.
- **Data (`scripts/apply_gods.py`, 119 changed bytes, layout unchanged):**
  - stats 400/400 (÷10), level 10;
  - TCG passwords;
  - copy limit 1;
  - deck swaps.

  Its JSON writer copies the extractor's style (`tables_game._dumps`), so diffs stay minimal.
- **Code (`scripts/patch_source.py`):**
  - 85 monster-type tests now go through `CARD_TYPE_IS_MONSTER`; the Card View attribute icon test is left
    as it was;
  - 12 Obelisk-kind cases;
  - the IsEffectMonster and IsSpecialSummonOnly special cases;
  - Card View text.
- **Gotcha 1, layout not relocatable.** The naive build put `gCardStats` at `0x08622094` instead of
  `0x08621DE0` (+692 bytes), and the ROM grew. Code reads tables through integer constants, so that ROM is
  broken. Fix: `scripts/hookbuild.py`:
  - vanilla C plus the new assets gives the original layout;
  - the changed functions (object compare: bytes with relocated words blanked, plus the relocation list)
    are relinked at `0x08800000` with `-R vanilla.elf`;
  - each object's own globals are localized;
  - the 536 BL targets outside the blob go through ARM `ldr ip,[pc]; bx ip` stubs, because Thumb BL only
    reaches ±4 MiB;
  - each changed entry gets the trampoline `bx pc; nop; ldr ip,[pc]; bx ip; .word new|1` (16 bytes, or 18
    when the entry is 2 mod 4).

  The game never compares function pointers except to NULL, so duplicate copies are safe.
- **Gotcha 2, symbols file:** every `make` rewrites `config/symbols.txt`. Restore it before diffing or
  patching.
- **Gotcha 3, `check.py` isn't a change detector:** once a function changes size, every later function in
  the unit shows as DIFF, so its per-function report can't say what changed. Compare the objects instead.
- **Null-hook test:** the vanilla objects relinked behind the same 63 hooks give identical EWRAM at every
  library state, except `gDuelScreen.fieldBgScroll` (VBlank drift). The cause is 2 lag frames during the deal
  (duel_main1 is reached at frame 3165 instead of 3163). The hook machinery itself is proven.
- **Gotcha 4, the AI only weighs Tribute Summons when its field can't already attack well**
  (`AiStepMainPhase`: `AiPlanAttack(1) != 0` means no-tribute summons only). An AI test against an empty
  player field never reaches `AiChooseSummonWithTribute`. Giving the player a Blue-Eyes does.
- **Gotcha 5, AI simulation:** `AiSimSummon` writes candidate cards into the real zone RAM and restores them
  within a few frames. An oracle must require the God to stay on the field (60 frames), or it passes on the
  simulation.
- **Gotcha 6, staging:** the first `DuelMainStep` frame clears the zones (LP go 0 → 8000), so poke after that.
  Poked zones only get drawn if the poke lands before the field is first drawn.
- **Gotcha 7, Ritual kind:** Obelisk's Ritual kind is used for frames *and* rules. `card_detail.c` serves both,
  so its frame keeps Ritual and its two rule functions special-case Obelisk.
- **Results:** all 8 oracles pass on the mod and fail on the original (`tests/run_oracles.py --control`).
  - Full player path: password → Deck Edit → duel deck.
  - Battle: Obelisk beats BEWD, 8000 → 7000.
  - Regression: in a duel without Gods, the mod matches null hooks byte for byte.
- **Build:** a fresh `scripts/build.sh` takes 68 s and gives the same SHA-1 `2b905f01…`. `gods.bps` from
  `flips --bps-delta` is 39,158 bytes, round-trip checked.
- **Showcase:** a 35 s silent clip from the harness (`um video compile`), sent to the user rather than
  committed (19 MB).
- **Next:** the user tests in Delta. Then, with their OK: the field note PR, and maybe 3 Tributes or God effects.

## 2026-10-13: real device
- **Delta on iOS (user's test):** the patched ROM boots. They summoned a God with two Tributes from the
  field; it showed 4000 ATK / 4000 DEF, and they attacked with it. So the 16 MiB ROM and the ARM
  trampolines running from ROM work in Delta's core, not only in mGBA.
- **Not checked in Delta yet:** the CPU summoning its God, the password screen.
- **Next:** the user's call: a PR (fork `main` or upstream), 3 Tributes, God effects.

## 2026-10-13: three Tributes (second build)
- **User's decisions:** keep both builds (`gods.bps` = 2, `gods-3t.bps` = 3); Ultimate Offering also takes 3.
- **The engine had half of it:**
  - `SummonAction.tribute3Zone` and `hasTribute3`, never set; bit 30 (`unk0_30`) is unused and is now
    `tribute3Player`;
  - `SummonStep_SpecialFromHand` already Tributes a third monster.
- **`scripts/patch_three_tributes.py` (26 anchored edits in 10 files):**
  - a third byte in the Tribute word (bits 16-23) for `QueueNormalSummon`, the new
    `QueueNormalSummonChoosePositionEx` (the old entry point wraps it) and `QueueSpecialSummonFromHand`;
  - both Normal Summon executors remove the third Tribute;
  - `CanSummonFromHand` wants more than 2 tributable monsters for a God;
  - the card menu gets steps 90-97;
  - Ultimate Offering gets steps 0x7A/0x79/0x73/0x72;
  - the AI gets `AiPickTributeMonsterExcept` plus God branches in `AiHasTributesFor`,
    `AiChooseSummonWithTribute` and both `AiStepMainPhase` paths.
- **Gotcha, stale third Tribute:** the kind-6 executor reads `hasTribute3`. A God summon leaves it set, so
  every queue must write the third byte (0 when there is none), or a later Special Summon from hand eats a
  monster. All callers pass ≤16-bit words (audited), so decoding byte 2 is safe.
- **Gotcha, storing the third pick:**
  - in the card menu: `summonSeq` (4 bits, used only by the Gate Guardian and Valkyrion steps);
  - in Ultimate Offering, whose `targets[]` is only `u16[3]`: the high byte of `targets[1]`.
- **`hookbuild.py`:**
  - globals that VANILLA lacks (new functions and strings) stay global and get no stub;
  - `.rodata` is allowed for a unit whose vanilla object has none;
  - units are detected by object comparison too, in case a header edit changes code.

  The 2-Tribute ROM still rebuilds to `2b905f01…`.
- **Result:** 45 units, 73 hooks, 555 stubs, a 226,390-byte blob. `gods-3t.gba` has SHA-1 `1cb038ed…` (fresh
  build = dev build); `gods-3t.bps` is 45,617 bytes.
- **Ultimate Offering in the harness:**
  - setup: a set card 756 in spell/trap zone 5 with `canActivate` (+0x91 bit 2);
  - one UP puts the cursor on it, then RIGHT selects Activate.

  It pays 500 LP and asks for a hand monster. With only 2 fodder it offers no Activate at all, because nothing
  is summonable.
- **Oracles (`run_oracles.py --tributes 3 --control gods.gba`):** 15/15 pass. Every discriminating check fails
  on the 2-Tribute build; the shared ones pass on both. In a God-free duel, 3t and 2t EWRAM and frame counts
  are identical at every library state. The 2-Tribute suite is still 8/8 vs the original.
- **Showcase:** a 23 s clip of the three-Tribute summon, sent to the user.
- **Next:** the user tries `gods-3t` in Delta.

## 2026-10-13: three Tributes on a real device
- **Delta on iOS (user's test):** the 3-Tribute build works. Both builds are now confirmed on the user's
  device.
- **Next:** the user's call: a PR (fork `main` or upstream), God effects.

## 2026-10-13: God effects, planning
- **User's ask:** plan the God effects: how EDS handles a card's effect, which effects each God gets, how a
  new effect goes onto an existing card. The plan is `PLAN-god-effects.md`; nothing is built yet.
- **The effect table can't grow in place:** `gCardEffects` (426 rows × 0x18 at `0x0819A9D4`) ends exactly
  where `gTributeSummonPrompts` starts (`0x0819D1C4`). `FindCardEffect` hard-codes `hi = 425`, and eight units
  index the table directly. Plan: a relocated copy (`.incbin` of the decomp's own built table, plus three
  rows) and a `#define` that sends every reader to it, so `hookbuild.py` hooks them all.
- **Most of a card's behaviour isn't in the table.** It is `switch (card number)` cases:
  - `GetZoneCardStats` for continuous stats (Muka Muka is Slifer's template);
  - `ExecuteSummonAction` step 2 for Normal Summon triggers (Dragon Seeker);
  - `CanActivateMonsterEffect` for a monster's Activate command;
  - `SummonAction_Update` for reactions to any summon (Jinzo, Pumpking);
  - `CanCardTargetZone` for targeting immunity (Lord of D.).
- **Per-card memory:** zone links (`links[32]`, `linkKinds[32]`). They are cleared with the zone, and only
  kinds 1, 2, 5, 7 and 10 are read as card locations, so a new kind can hold Ra's paid LP safely. Kind 4
  (`ATK_BONUS`) is removed in the End Phase, so it can't.
- **CPU:** `AiActivateMonsterEffects` loops over a 4-entry list in ROM (`0x0819DD64`), so the God branch has
  to be code.
- **Card text:** fixed 480-byte records, so new text replaces the old in place.
- **Not reachable from this container:** yugipedia.com (DNS). The TCG texts came from search results.
- **Next:** the user picks the variants (Obelisk wipe or damage, Ra "become" or "gains", traits, builds).

## 2026-10-13: God effects (third and fourth builds)
- **User's decisions:**
  - Obelisk: destroy all (TCG);
  - Slifer: both effects;
  - Ra: its ATK/DEF *become* the LP paid, and it keeps the 1000-LP destroy;
  - the three recommended traits;
  - effects on both Tribute rules: `gods-fx.bps` and `gods-3t-fx.bps`.
- **Code:** our own unit `src/god_effects.c`, a relocated table `src/god_effects_table.s` (`.incbin` of the
  decomp's built table, then Obelisk's and Ra's rows), and `scripts/patch_god_effects.py` (22 anchored edits
  in 10 files).
- **`hookbuild.py`:** links units that only the mod tree's `units.txt` lists. Everything they define must be
  new.
- **`check_effect_table.py`:** every build checks:
  - the 426 copied rows against the original;
  - the sort order and Thumb pointers;
  - that all 11 functions reading the old table are hooked.
- **Gotcha, a prompt that closes itself:** a text box opened on the frame of the A press that picked the
  first Tribute sees that press and closes at once. Open the next prompt one frame later (a separate step).
- **Gotcha, the link-removal quirk:** `RemoveLinksToZone` skips the link after any link it doesn't read as a
  location. Ra's LP link and Slifer's drain link are each followed by a pad link (kind 15, `0xFFFF`), so a
  later Equip's link is still removed.
- **Gotcha, test hands:** the CPU played a Time Wizard from its real hand, lost the coin toss and wiped its own
  field. CPU tests get a hand of plain monsters (`C_HAND`).
- **Gotcha, turn 1 has no Battle Phase:** battle checks start from `duel_turn2`. B, then Enter Battle Phase,
  then the monster's second command (Attack).
- **Gotcha, the God menu lost Set:** in the effects builds a God's hand menu is Card View / Summon, so the God
  summon keys take one RIGHT, not two. With the old keys the cursor wraps to Card View.
- **Gotcha, shared assets:** `build.sh` re-extracts and re-applies the data on every run, and the card text
  depends on `--text`. A dev rebuild that skips `build.sh` gets whatever text the vanilla tree last had.
- **CPU Slifer:** with a 3-card hand the CPU traded three monsters for a 2000-ATK Slifer. `CanSummonFromHand`
  now refuses the CPU's Slifer below 4 cards in hand.
- **Regression:** in God-free library states (title through the CPU's turn 1), EWRAM is identical with and
  without effects. IWRAM differs only in the audio DMA buffer and the stack. Trap Hole and Tribute to The
  Doomed behave the same frame for frame on both.

## 2026-10-13: effects on a real device
- **Delta on iOS (user's test):** `gods-3t-fx.bps` works; they summoned Ra. Patches are complete on their
  own: each `-fx` patch includes its base build's changes and goes onto the original ROM.
- **Next:** the user's call: a PR (fork `main` or upstream), the End Phase trait, "Ra can't be Special
  Summoned".

## 2026-10-13: pack viewer, planning
- **User's ask:** after a duel, see what each pack on the pick-a-pack screen contains, with each card's odds.
  The plan is `PLAN-pack-viewer.md`; nothing is built yet.
- **Flow:** `Campaign_GiveRewards` either gives an event duel's fixed pack (`GetRewardPack`, no list) or runs
  `CB_GetPack`. That is the list of unlocked packs (`IsPackUnlocked`, at most 23 with covers), then
  `GeneratePackCards`, then the 5-card opening scene. The pick screen reads only LEFT, RIGHT and A, and shows
  no pack names.
- **Odds:**
  - the first card comes from the rolled slot: thresholds `{1,3,6,10,16,28,64,180}` out of 180, or 270 when
    you pick the same pack as last time; a pity rule switches to `% 12` after more than 5 commons-only packs;
  - the other four are the first four of a 2×N-swap shuffle of the commons, which isn't uniform. In a
    300,000-pack simulation of Vol.1 the first four commons came out at about 16.8% each, the rest about
    15.2%.
- **Harness:** the pick-a-pack screen is reached from `duel_turn2` by giving the CPU 1 LP and attacking, then
  pressing A through the win dialogue. `--until` didn't fire under `emu.py lua`, so a frame-timed key list
  stops the A presses before the list.
- **Next:** the user's choices (button, row style, live or base odds, names, extras, builds).

## 2026-10-13: pack viewer, built (in `gods-3t-fx`)
- **User's decisions:** the recommendations (SELECT, the opening scene's rows, live odds, full names, the NEW
  mark), only in `gods-3t-fx`.
- **Code:**
  - `src/pack_viewer.c`, a new unit;
  - `scripts/patch_pack_viewer.py`, with 6 anchored edits in 4 files: SELECT, the viewer's sub-states, the
    kept centre pack, the band text and the row drawer's canvas clear;
  - `scripts/gen_pack_odds.py`, which writes the odds table into the tree from its own `booster_packs.json`.
- **Odds model:**
  - The rarity roll and the rolled card are exact sums over the 15-bit `Random()`'s modulo weights.
  - The 4 commons come from two Markov chains propagated backwards: one card's position after the 2N
    transpositions, and the pair (card, rolled card).
  - Checked against brute force over all permutations (N = 5, 6, uneven weights): error 1e-15.
  - A numpy simulation of `GeneratePackCards` with the game's LCG agrees on 2,982 odds (23 packs × 3 rolls,
    400,000 packs each): max |z| 3.5, as noise predicts.
- **Gotcha, the pick screen's BG0 is 4bpp:** `PackList_InitVideo` sets BG0 to 8bpp, but `ResetVideo` right
  after resets it to `4` (4bpp, char block 1). 8bpp text came out as cover pixels. The band text is 4bpp
  tiles in the tile buffer's bytes after the four covers (8bpp tile 0x198 = 4bpp tile 0x330), palette bank
  14 of `gPackListPal`, where 235 is white and 233 pale yellow.
- **Gotcha, `TextCanvasInit` clears 64 KB:** about 3 frames per call, so redrawing 5 rows took 15 frames. In
  the viewer (`seqIndex1 == 0`, `seqState1 >= 0x20`) the row drawer clears only the row's 3 KB. The opening
  scene keeps the original call.
- **Gotcha, tearing:** `MainLoop` copies the BG maps and OAM in `FrameSyncUpdate` at VBlank, and only then runs
  the scene, which reaches the visible frame. Tile and palette writes show at once, map writes a frame
  later. So:
  - a row is drawn after its VRAM map lines are blanked;
  - a scroll's four row moves (tiles, icon palettes) run in `gMain.vblankCallback`, and only the new row is
    drawn, a frame later;
  - sprites are queued after the change.
  The screenshots show no mixed frames.
- **Gotcha, the Latin font is fixed-width:** half the font size per character (5 px at size 10, in
  `TextDrawLatinString`), so centring needs no measuring draw.
- **Gotcha, frame-timed tests and the RNG:** `FrameSyncUpdate` calls `Random()` once per main-loop pass. A
  lag frame (the band text costs about 1 at the list's start) moves every later key press to another RNG
  state, so the same keys pick a different pack. The regression oracles pin `rngState` when the pick starts
  its fade-out; then the viewer build and the build without it generate the same 5 cards, with or without a
  trip through the viewer.
- **Oracles (`--pack-viewer`, `tests/pack_viewer.lua`):** 13 checks. The logger reads the odds, NEW and header
  text back from the BG0 map and the VRAM glyph tiles, against the game's 8x8 bold font. Every viewer check
  fails on the build without the viewer, and the two pick checks pass on both.

## 2026-10-14: summon rules and quality of life (in `gods-3t-fx`)
- **User's decisions:** the recommendations:
  - the Gods' two missing TCG rules;
  - owned counts in the pack list;
  - "Found in" on Card Detail;
  - the Gods' stats in Deck Edit.
- **Correction while building:**
  - The "X000" in Deck Edit isn't a blanket Divine display. The game prints Obelisk 4000, Slifer `X000` and Ra `????`, in both Deck Edit and Card Detail.
  - In the effects build that is what the cards mean (Slifer = 1000 × the hand, Ra = the LP paid), so it stays.
  - What was really off: Deck Edit sorted the Gods after the spells and filed Obelisk under Ritual, and the pack rows drew nothing for a God.
- **Code:**
  - `src/god_rules.c`, a new unit;
  - `scripts/patch_god_rules.py`, with 7 edits in 5 files:
    - `CanReviveGraveyardCard`;
    - Time Machine;
    - `DuelPhase_End`;
    - `AiPickDiscard`;
    - three in Deck Edit's filter;
  - the pack viewer gets 2 more edits: the God row in `GetPack_DrawCardRow`, and Found in in `CardDetail_DrawInfo`;
  - `apply_gods.py --text 3` adds the rules to the card text.
  
  The new units are linked only into `gods-3t-fx`, so the other three ROMs stay byte for byte as published.
- **Where Special Summons come from:** every revival but Time Machine lists its candidates through
  `CanReviveGraveyardCard`. That one list is what Prepare counts, what the player's list shows and what the
  CPU picks from (it picks the best ATK + DEF, so without the rule it always took Ra). Summons from the deck,
  the hand or the Fusion Deck already exclude a level-10, 4000-ATK Divine monster, or name their cards.
- **End Phase:** `DuelPhase_End`'s low-level step, for both players: a God Special Summoned on the
  opponent's turn still leaves at the next End Phase. The card word's `specialSummoned` bit is set by every
  Special Summon builder, and it is cleared when the card goes back to the hand or the deck.
- **Gotcha, the Monsters filter:** Deck Edit's `LIST_FILTER_MONSTERS` can't be selected (it isn't in the cursor
  tables). The visible effects of treating the Gods as monsters are the ATK/DEF/level sorts of the whole
  Trunk and the Effect/Ritual filters.
- **Gotcha, Card Detail text:**
  - `CardDetail_RenderText` retries with a tighter line gap, then font 8, until the text ends above y 192. Each pass clears the whole 64 KB canvas.
  - Found in is drawn as its own paragraph (yellow, font 8) below whatever pass fitted.
  - When there's no room (the Gods' long effect texts), it joins the description inline, and the retries shrink both.
  - The tests count yellow pixels on the canvas.
- **Gotcha, duel or not:** `gDuelScreen.active` and `gDuelCtrl.phase` don't tell you whether you're in a duel. They are cleared before Card Detail opens, or never reset. `gMain.callback` plus the duel step (`CB_Campaign` step 4, `CB_LinkBattle` step 3) does.
- **Harness:**
  - `effects.lua` gained graveyard staging (`P_GRAVE`, `C_GRAVE`);
  - Monster Reborn is Activate (two RIGHTs), OK, then LEFT to the list's "designate" icon;
  - `deck_edit.lua` puts cards in the Trunk before Deck Edit builds its lists, and reads the shown list (`gDeckEdit.lists[1].trunk`);
  - `pack_viewer.lua` can put any pack in the pick screen's centre slot (`PICK_PACK`).

## 2026-10-15: summon rules on a real device; the CPU's aces
- **Delta on iOS (user's test):** in `gods-3t-fx`, Ra can't be revived. The End Phase rule hasn't been checked
  on the device.
- **The user's question: do the duelists have boss monsters?** From the original deck lists
  (`deck_lists.json`) and the AI code:
  - most of the 24 decks have a signature ace: Kaiba's three Blue-Eyes, Yugi's Dark Magician and Buster
    Blader, Joey's Red-Eyes, Pegasus's Toons and Relinquished, Mai's Harpies, Arkana's three Dark Magicians;
  - the CPU has scripted plays for five of them (`AiChooseStrategy`): Cyber-Stein into Blue-Eyes Ultimate
    Dragon (Kaiba), Valkyrion from the three Magnets (Yami Yugi), Harpie Lady into Elegant Egotist (Mai),
    Toon World (Pegasus), and an Exodia flag for Rare Hunter (`LoadOpponentDeck`);
  - Fusion monsters in a CPU list go to its Fusion Deck (`AddCardNumberToDeckTop`). Kaiba's Blue-Eyes Ultimate
    Dragons come out only through Cyber-Stein: his deck has no Polymerization;
  - the second decks of Yugi, Tea, Joey, Tristan and Bakura (`gOpponentAltDecks`) are never used: the one
    caller passes 0;
  - Marik's original deck has no ace (Millennium Golem and Dragon Seeker at 2000 ATK); this mod's Ra is its
    only big monster. The Duel Computer, the last tier, tops out at Gemini Elf: a Morphing Jar and Mask of
    Darkness deck.

## 2026-10-15: second decks (in `gods-3t-fx`)
- **User's ask:** after the player beats a Tier 1 duelist 10 times, that duelist plays their second deck
  (`gOpponentAltDecks`), only in `gods-3t-fx`.
- **Why the decks were dead:** `LoadOpponentDeck(useAltDeck)` has one caller, `Campaign_SetupDuel`, which
  passes a constant 0 (`mov r0, #0` before the `bl`). No other code reads the table. The loader and its caller
  are separate units, so the compiler kept the branch and the table.
- **The change:**
  - `src/second_decks.c` (a new unit): `OpponentUsesSecondDeck()` is 1 for duelists 1-5 with
    `duelRecords[id].wins >= 10`. The range check matters: the table has 6 entries, so another duelist would
    read past it.
  - `patch_second_decks.py`: one edit, `LoadOpponentDeck(0)` becomes `LoadOpponentDeck(OpponentUsesSecondDeck())`.
  - `build.sh` runs it for `--tributes 3 --effects` only.
- **Data check:** no first or second Tier 1 deck goes over the ban list, so `RemoveOverLimitDeckCards` (which
  drops every copy of a card over its limit, not just the extras) leaves them whole. Joey's second deck puts
  B. Skull Dragon in his Fusion Deck; the deck keeps Polymerization, Summoned Skull and two Red-Eyes.
- **Harness:** `npc_deck.lua` takes `WINS` (the record against `OPP`, poked every frame until the deck loads)
  and logs the deck and the Fusion Deck sorted. `run_oracles.py --second-decks` compares them with the
  checkout's `deck_lists.json`.
- **Smoke test:** Joey at 10 wins through a whole duel, the player only ending turns: the CPU summoned Tiger Axe,
  Sinister Serpent and Dragon Zombie from the second deck and won. The first try stalled in the player's Draw
  Phase: a B, A pattern doesn't draw; A, B, A, B, A every 150 frames ends turns.
- **Results:**
  - the whole `gods-3t-fx` suite is 70/70 (18 effect, 15 base, 16 viewer, 13 rules and Deck Edit, 8 second
    decks) against `gods-3t`, every control comparison as expected;
  - `gods-3t-fx` is `637b7bd6...` from two fresh work dirs; `gods-3t` and `gods-fx` rebuild unchanged.

## 2026-10-15: the 10th-win lines (in `gods-3t-fx`)
- **User's ask:** after the 10th win against one of the five, the duelist says something like "I better find
  some new cards and train more", the moment their second deck switches on.
- **Found:** the game already has a 10th-win line per duelist. `Campaign_ShowDuelResult` picks
  `gOpponentResultTexts[opp].win10th` (`0x080817FC`, 16 bytes per duelist) when the record still says 9;
  `Campaign_GiveRewards` then records the win. So the line shows exactly when the second deck switches on. The
  events are 1017, 2017, 3017, 4017 and 5016 (Bakura's isn't X017; read from the ROM table, not guessed).
- **The change:** data only. Dialogue records are a fixed 0x304 bytes (`text[0x300]`, the longest original
  341), so `apply_gods.py --text 3` appends `$c$p` and a new page to those five texts in `text/dialogue.json`.
  The ROM differs from the second-deck build in those five records only (468 bytes).
- **Wording:** the user's sentence on every page, with a short lead-in that answers the duelist's own last
  page and a "next time" in their voice. The longest page in the game is 127 characters; the new ones are
  79-103, and the screenshots show them inside the box (Joey's and Tristan's use all four lines).
- **Harness:** `dialogue.lua` wins at once from `duel_turn2` against `OPP` with the record at `WINS`, and
  follows the printer (`gBustup.textBox.text`, `0x020147A0`) through the record at `gMain.dialogueIndex`. It
  logs the event and the offset when the printer reaches the NUL: the whole line, every page, was shown.
  Seven checks: the five lines to their new end (they fail on the build without the lines), Tea's 11th win
  (her usual line) and Rex's 10th-win line (unchanged).
- **Results:** the whole `gods-3t-fx` suite is 77/77 against `gods-3t` (70 before, plus the 7 dialogue
  checks), every control comparison as expected. `gods-3t-fx` is `8710dd2f...` from two fresh work dirs.

## 2026-10-15: second decks and 10th-win lines on a real device
- **Delta on iOS (user's test):** `gods-3t-fx` `8710dd2f...` works.
- **The user's question:** how many CPU decks hold Dark Hole, Raigeki, Heavy Storm or Harpie's Feather Duster?
  From the build's `deck_lists.json`: 22 of the 24 first decks hold at least one (not Yugi's or Tristan's),
  and all 5 second decks. None goes over the ban list for them (Heavy Storm, limit 2, appears twice in Yami
  Bakura's and Simon's), so `RemoveOverLimitDeckCards` leaves them in.

## 2026-10-15: CPU deck tuning (in `gods-3t-fx`)
- **User's ask:** adjust the existing cards before adding new ones. The top 20 cards across the CPU decks are
  mostly the same staples (Monster Reborn in 28 of 29 decks, Change of Heart 26, Raigeki 24). The user
  approved a per-duelist change list.
- **Dead cards:** a strict scan counts a Magic/Trap card as playable only when some rule plays, chains or
  activates it: the spell lists, `AiTryPlaySpellTrap`, `AiChainSetCard`, `AiShouldActivateSetCard`, the
  strategies. That leaves 41 copies of 9 cards, plus Pegasus's Megamorph (played only in the Cyber-Stein
  combo). Snatch Steal is the big one (15 decks): it shows up only in the lists that read the human's hand and
  deck and in the key-card list. In the emulator, the CPU held it with a Blue-Eyes to take and set a monster
  instead; Change of Heart in the same setup took the Blue-Eyes and attacked.
- **The change:** `DECK_TUNING_3T` in `apply_gods.py`, applied with `--text 3`. For each deck it gives the
  count before and after of every card that changes, so a rerun is a no-op and a ROM with other decks stops
  the build. 63 cards in 26 decks; the lists stay sorted and the same size.
- **Harness:**
  - `effects.lua` takes `C_DECK`, written over the CPU's deck.
  - A recruiter's chain link waits for A from the human player ("Chain: Activating ... Opposite"), so its
    test presses A after the battle.
  - Results: all four recruiters summon from the deck; Elegant Egotist brings Harpie Lady Sisters; the CPU
    plays Toon World, then Toon Mermaid; Fissure takes the face-up Blue-Eyes.
  - Rex's and Kaiba's "keeps his deck" second-deck checks are now not compared on the control, whose decks
    differ.
- **Results:**
  - the whole `gods-3t-fx` suite is 105/105 against `gods-3t`, every control comparison as expected;
  - `gods-3t-fx` is `2082fb6f...`, the same ROM and `.bps` from two fresh work dirs;
  - `gods-3t` and `gods-fx` rebuild unchanged.
- **Gotcha, editing a running script:** `sh` reads `build.sh` as it goes, so editing its comments during a
  build broke the tail ("Syntax error") after the ROM was already written. Don't touch a script while it runs.

## 2026-10-15: deck tuning on a real device
- **Delta on iOS (user's test):** `gods-3t-fx` `2082fb6f...` (the tuned CPU decks) works.

## 2026-10-15: Ritual monsters in the Extra Deck (in `gods-3t-fx`)
- **User's ask:** see how the Extra Deck works and what goes in it; then make Ritual monsters belong there
  instead of in the Main Deck. The user approved the plan (Senju searches a Ritual Magic card, Cyber-Stein
  keeps to Fusion monsters, old saves are moved).
- **Found:**
  - EDS's Extra Deck is the Fusion Deck: `gSaveData.fusionDeck[20]` (+0x209E) and the duel's
    `fusionDeck[80]` (+0xA44, `fusionCount` +5). It takes Fusion monsters only (52 card IDs), outside the
    40-60-card Deck, never drawn, and Deck Edit refuses them the Side Deck.
  - "Fusion Deck or not" is decided by the card kind (stats bits 18-19) in about a dozen places, each with its
    own inline copy of the kind classifier: Deck Edit's filing, its copy counts and its Side Deck command;
    `AddCardNumberToDeckTop` for the CPU's lists; `IsFusionMonster` (bounce, return to the Deck, their
    animations), `AddCardToHand` and the graveyard-to-hand animation.
  - The Ritual Magic cards (15 recipes in `gRitualRecipes`, the Tributes' levels at least the monster's
    level) need the monster in the hand: `HandHasRitualMonster` in the prepare and the resolve, and the
    resolve's take step copies it out of the hand. Polymerization already takes its monster out of the Fusion
    Deck with `DUEL_CMD_REMOVE_CARD_FROM_FUSION_DECK`, a card word in two halves.
  - Three CPU decks hold rituals: Bakura (Dokurorider), Mako (Fortress Whale), Pegasus (two Relinquished).
  - Fusion Deck users that aren't Polymerization: Cyber-Stein and Gale Dogra list every card of it, and
    Senju of the Thousand Hands searches the Deck for a Ritual monster. Sonic Bird already searches a Ritual
    Magic card, with its own prompt string.
- **The change:** a new unit, `src/extra_deck_rituals.c`, and 16 edits in 12 files
  (`patch_extra_deck_rituals.py`). `IsExtraDeckMonster` (a Fusion or Ritual monster, not a God, from the stats:
  Obelisk's code kind is Ritual only for its frame) replaces the Fusion-kind test where a card is filed. The
  Ritual Magic cards look in the Fusion Deck first and keep the hand path. Cyber-Stein counts and lists Fusion
  monsters only. Senju lists Ritual Magic cards with Sonic Bird's prompt; its card text is new
  (`apply_gods.py --text 3`).
- **Old saves:** `GameInit` reads the save from SRAM and nothing checks it until the title screen asks for
  Continue (`IsSaveChecksumValid`). Right after the read, `MoveSavedRitualMonsters` moves the saved Deck's
  Ritual monsters to the saved Fusion Deck (the trunk when it's full or at the copy limit) and updates the
  checksum, so Continue still shows. A save with a bad checksum is left alone.
- **Gotcha, `patch_source.py` on a rerun:** it rewrites every `<= CARD_TYPE_REPTILE` / `> CARD_TYPE_REPTILE`
  in `src/` and stops when the count isn't 85. A new unit with such a test would break a rerun on a patched
  tree, so `IsExtraDeckMonster` uses `CARD_TYPE_IS_MONSTER(type) && type != CARD_TYPE_DIVINE`.
- **Gotcha, the CPU and its spells:** the first CPU ritual test never played the Ritual Magic card, on the old
  build too with the monster in hand. A trace of `gAiState` (0x02015EF0) showed why: when the CPU plans an
  attack it Normal Summons in `AI_MAIN_SUMMON`, which ends Main Phase 1 (step 2 -> 3), and Main Phase 2 plays
  no spells. With only Level 8 monsters in hand it can't summon, reaches `AiPlaySpells`, and plays the ritual.
- **Harness:**
  - `effects.lua` takes `P_DECK`, `P_FUSION` and `C_FUSION`, and logs both Fusion Decks.
  - `deck_edit.lua` logs the saved Deck, Side Deck, Fusion Deck and Trunk sizes.
  - `save_migration.lua` (new): from `main_menu`, adds cards to the saved Deck and Fusion Deck, fixes the
    checksum, writes the save to SRAM (bus writes to 0x0E000000 work in mGBA's Lua) and calls `emu:reset()`,
    so `GameInit` boots from that save.
- **Gotcha, a frame can end mid-shuffle:** the first full run failed one check, Kaiba's tuned deck card for
  card: one Cyber-Stein short, a fourth Koumori Dragon. It was the test, not the deck. `npc_deck.lua` read the
  deck on the first frame it was loaded, and the CPU's shuffle runs across a few frames; the new build's
  trampolines shift the timing enough that this frame ended in the middle of a swap (one card briefly in two
  slots). A trace per frame showed the right counts one frame later. `npc_deck.lua` now logs once two frames
  in a row hold the same cards.
- **Results:**
  - the whole `gods-3t-fx` suite is 124/124 against `gods-3t` (105 before, plus 19 Extra Deck checks), every
    control comparison as expected;
  - `gods-3t-fx` is `9372e6d5...` (`.bps` 74,253 bytes), the same ROM and `.bps` from two fresh work dirs;
  - `gods-3t` and `gods-fx` rebuild unchanged; pytest, `um kb check --index` and `um publish check .` pass.

## 2026-10-15: Extra Deck rituals on a real device
- **Delta on iOS (user's test):** `gods-3t-fx` `9372e6d5...` (the Ritual monsters in the Extra Deck) works.

## 2026-10-15: a Polymerization for Kaiba (in `gods-3t-fx`)
- **User's ask:** give Kaiba a Polymerization so his Blue-Eyes Ultimate Dragons can come out. His Fusion Deck
  has two, but the original deck had no Polymerization, so only the scripted Cyber-Stein play (5000 LP) could
  summon one.
- **The change:** `DECK_TUNING_3T`. His second dead Sebek's Blessing becomes Polymerization instead of a third
  Koumori Dragon, which stays at two. Still 63 cards in 26 decks, one for one; the ROM differs from
  `9372e6d5...` in 18 bytes of the deck table only.
- **The CPU:** Polymerization is on its generic spell list. With three Blue-Eyes in hand (so it can't summon to
  attack first) it plays Polymerization, summons Blue-Eyes Ultimate Dragon and attacks for 4500. A new tuning
  check covers it (it passes on the old build too: the CPU could always fuse).
- **Results:** the `gods-3t-fx` suite is 125/125 against `gods-3t`; `gods-3t-fx` is `27e5fdee...` from two fresh
  work dirs.

## 2026-10-15: Kaiba's Polymerization on a real device
- **Delta on iOS (user's test):** `gods-3t-fx` `27e5fdee...` works.

## 2026-10-15: the bosses' effects (in `gods-3t-fx`)
- **User's ask:** make the CPU's boss monsters worth their Tributes, with effects that fit each one and keep
  paying while it stays on the field, like Suijin or Jinzo, and that still leave it open to Trap Hole, Dark
  Hole, Hane-Hane or Penguin Knight. Their picks: Summoned Skull pierces; Millennium Golem can't be destroyed by
  battle; Dark Magician destroys 1 Spell or Trap card once per turn; Red-Eyes B. Dragon tosses a coin once per
  turn to destroy a monster; Red-Eyes Black Metal Dragon gets a weaker Metalmorph (+¼ of the attacked
  monster's ATK, Metalmorph gives ½); the Duel Computer gets two Barrel Dragons for two White Magical Hats.
- **The design rule:** reuse a mechanic the engine already runs, so the CPU uses it with no new AI. Piercing,
  survival and the bonus are three lines in `CalcBattle`. The two activated effects copy Barrel Dragon's
  row shape (once-per-turn prepare, opponent check, pick), with Dust Tornado's prompt for Dark Magician and
  Barrel Dragon's for Red-Eyes, Mystical Space Typhoon's destroy, and Time Wizard's one-coin scene.
- **The code:** `src/boss_effects.c` (new unit) and `scripts/patch_boss_effects.py`, 11 anchored edits in 8
  files:
  - three effect rows after the Gods' in `gCardEffectsMod` (Dark Magician 34, its alternate art 2034, Red-Eyes
    81). They break the sort, so `FindCardEffect` falls back to a linear `BossFindCardEffect` when its binary
    search fails, and `check_effect_table.py --boss-rows` checks them (Thumb handlers, numbers not in the
    sorted part);
  - every handler in those rows is a wrapper in the new unit, so all row pointers stay Thumb addresses in the
    new code, as the table check requires;
  - the monster menu, the menu's Activate dispatch, the turn-start reset of `effectUnused`, Red-Eyes' prompt,
    and the CPU after `GodAiActivateEffects`.
- **The data (`apply_gods.py --text 3`, `BOSSES_3T`):** Summoned Skull, Millennium Golem, both Dark Magicians
  and Red-Eyes B. Dragon go from kind Normal to Effect. Without that, a monster effect has no spell speed and
  the menu never offers it; it also gives the orange frame and "[Fiend/Effect]". All six get new text in my
  own wording. The Duel Computer's swap is in `DECK_TUNING_3T` (65 cards in 26 decks now).
- **Gotcha, Red-Eyes already had an Activate:** the original menu offers it on a Red-Eyes with Metalmorph
  equipped, to Tribute it for Red-Eyes Black Metal Dragon from the Deck (two steps in `duel_cmd_queue.c`).
  The fork: without a Metalmorph, the menu asks the effect row and the dispatch adds the chain link; with one,
  the upgrade as before.
- **Bug found by the regression test:** the first build tossed the coin after the upgrade's Tribute, and Red-Eyes
  Black Metal Dragon never came. The dispatch runs once per step; at step 1 the zone is empty, so "no
  Metalmorph" was true. The fork now runs only at step 0.
- **Harness:** `effects.lua` flags `e` / `u` stage a monster's once-per-turn effect unused or used (zone byte
  7, bit 5), `PIN_RNG` writes gMain's RNG state at frame 1, and a coin toss logs "coin heads" / "coin tails"
  from `gDuelScene` (0x02017A30: scene 0, arg bits 8-14 the count, bit i coin i). The CPU checks give it five
  Blue-Eyes it can't summon (and a deck of them), so its turn goes to its effects and its attack.
- **Seen in the emulator:** the CPU's Dark Magician takes a set card first; the CPU's Red-Eyes targets your
  strongest monster (Barrel Dragon's pick); a used Dark Magician's menu has two commands (no Activate).
- **An old check met the new kind:** the first full run failed one rules check, "Deck Edit: Effect Monsters
  lists Obelisk": the Trunk of the test save holds a Dark Magician, and the filter listed it with the Gods
  (n=4). That is the kind change working. `rules_suite(bosses)` now expects it with `--boss-effects`, and the
  check still expects the three Gods alone on the build before (run on `27e5fdee...`: n=3).
- **Results:**
  - the whole `gods-3t-fx` suite is 146/146 against `gods-3t` (125 before, plus 21 boss checks), every control
    comparison as expected; the Duel Computer's tuned deck loads card for card with its two Barrel Dragons;
  - `gods-3t-fx` is `79361de1...` (`.bps` 77,643 bytes), the same ROM and `.bps` from two fresh work dirs;
  - `gods`, `gods-3t` and `gods-fx` rebuild unchanged; pytest, `um kb check --index` and `um publish check .`
    pass.

## 2026-10-15: the bosses' effects on a real device
- **Delta on iOS (user's test):** `gods-3t-fx` `79361de1...` (the bosses' effects) works.

## 2026-10-15: Joey's Metalmorph, played by the CPU (in `gods-3t-fx`)
- **User's ask:** give Joey's second deck its Metalmorph back, so the CPU upgrades Red-Eyes. The deck tuning
  had traded it for Skull Dice, because the CPU never played it.
- **What the original AI does with Metalmorph:** `AiStepSetSpellTraps` sets any Trap from its hand, so it gets
  set; nothing ever activates it (it is on no list and has no response condition), and the upgrade is a
  monster-menu command, which only the human gets.
- **The change:**
  - `DECK_TUNING_3T`: Joey's second deck keeps Metalmorph (Kunai with Chain -> Time Wizard stays). 64 cards in
    26 decks, 41 of them dead.
  - `BossAiActivateEffects` first upgrades a Red-Eyes that has Metalmorph, or flips a set, activatable
    Metalmorph (canActivate, +0x91 bit 2) onto a face-up Red-Eyes, when Red-Eyes Black Metal Dragon is in the
    CPU's deck; only then Dark Magician's and Red-Eyes' own effects.
  - `EffectEquipTargetChainB`: the CPU's Metalmorph takes its Red-Eyes; the original takes its strongest
    monster.
  - `AiStepChangePositions`: see the gotcha below.
- **Gotcha, one monster effect after Main Phase 1:** the first build equipped Metalmorph and never upgraded.
  On a turn the CPU plans an attack, `AI_MAIN_SUMMON` Normal Summons and ends Main Phase 1 before its
  monster-effect phase. Step 3 (`AiStepChangePositions`) then calls `AiActivateMonsterEffects` exactly once,
  and the Metalmorph used that call. The step now stays while a Metalmorph it activated resolves, and its next
  pass does the upgrade instead of another effect.
- **Correction:** that same step 3 means the CPU uses one monster effect even on a turn it summons to attack.
  The README said its effects come only on turns it doesn't (true for its spells, not for monster effects).
  A check now covers it: its Dark Magician destroys a set card on a summon turn.
- **Gotcha, no RAM for the upgrade's two steps:** the menu runs it over two frames (Tribute, then the deck
  summon), and `hookbuild.py` can't place new data, so the CPU can't remember a pending upgrade. It does both
  steps in one call. `QueueSpecialSummonChoosePosition` takes `FindFreeMonsterZone` while the Tribute is still
  queued, so the CPU needs another free zone, and the new monster lands there; the CPU picks its position
  (`AiShouldSetMonster`).
- **Harness:** the two-turn check plays the human's turn 2 with eds-decomp's `duel_turn2` recipe cadence (A
  every 20 frames on the deck through the draw and the Standby Phase), from a 5-card hand. From the state's 6
  cards the run never drew, and the extra A presses opened Card View.
- **Results:**
  - the whole `gods-3t-fx` suite is 151/151 against `gods-3t` (146 before, plus 5 checks: the CPU's upgrade,
    its pick of Red-Eyes over Blue-Eyes, the two turns from its hand, Metalmorph left set without Black Metal
    Dragon, Dark Magician on a summon turn), every control comparison as expected; Joey's second deck loads card
    for card with its Metalmorph;
  - `gods-3t-fx` is `eabd901f...` (`.bps` 78,463 bytes), the same ROM and `.bps` from two fresh work dirs;
  - `gods`, `gods-3t` and `gods-fx` rebuild unchanged; pytest, `um kb check --index` and `um publish check .`
    pass.

## 2026-10-15: the CPU's Metalmorph on a real device
- **Delta on iOS (user's test):** `gods-3t-fx` `eabd901f...` (Joey's Metalmorph, played by the CPU) works.

## 2026-10-15: the Fusion and Ritual monsters' effects (in `gods-3t-fx`)
- **User's ask:** apply the bosses' five rules (worth its cost, keeps paying, still answerable, usable by the
  CPU, scales) to the Fusion and Ritual monsters; find the effects the engine already has and cross-reference
  them with the Fusion Deck inventory. The analysis went on a shared page: 67 Fusion Deck cards, 21 reviewed
  (Level 7+ and Dokurorider), 19 effects proposed, sized by the gap between the card's ATK and a bar (3000 for
  three cards, +300 for a Ritual, +500 for a Fusion of two 2000+ ATK materials), and capped by the tier of a
  CPU duelist that plays the card. The user approved the scope and all three large effects (Gaia, Super
  War-Lion, Skull Guardian). Giving CPU decks some of these cards was left open.
- **The code:** `src/extra_deck_effects.c` (new unit) and `scripts/patch_extra_deck_effects.py`, 18 anchored
  edits in 11 files, after the boss patch:
  - battle (`CalcBattle`): piercing and survival through `ExtraDeckPierces` and
    `ExtraDeckBattleIndestructible` next to the bosses' hooks; Kaiser Dragon's +1000 beside Insect Soldiers'
    boost, for the attacker and the defender; Garma Sword's LIGHT rule before the survival loop, so a
    battle-proof monster would still survive it;
  - stats (`GetZoneCardStats`): only case labels added to the engine's own cases (key 1516's Battle Phase
    boost, Shadow Ghoul's Graveyard count, Goddess of Whim's coin link), and a Chakra case over both
    Graveyards;
  - six effect rows after the bosses' (721, 36, 355, 68, 2068, 384); `ExtraDeckFindCardEffect` scans the boss
    rows, then these; `check_effect_table.py --extra-deck-rows` checks them (437 rows);
  - Bickuribox and Skull Guardian join Dream Clown's and Suijin's case lists (and the link duel's question);
  - the once-per-turn reset, the Activate list, Thousand Dragon's end-of-turn link removal and the CPU.
- **The data (`apply_gods.py --text 3`, `EXTRA_DECK_3T`):** 20 texts in my own wording, each naming the Fusion
  Material Monsters or the Ritual Magic card with its Levels first. The kind stays Fusion or Ritual: it files
  them in the Extra Deck, and its missing spell speed only matters when an effect answers a chain link.
- **Refinements while building:**
  - Gaia and Super War-Lion take a face-up monster only: a set monster's ATK would show through the pick.
  - "This card can't attack the turn you use it": nothing reliable marks "attacked this turn" (`attackedMask`
    clears when the Battle Phase starts, `positionLocked` also comes from a summon), so the effect is gated
    to Main Phase 1, then sets Obelisk's cannot-attack flag.
  - The CPU's Gaia uses it on a Defense Position target or with two or more targets; against one Attack
    Position monster it attacks, which also deals damage.
  - The CPU's Thousand Dragon tosses only in Attack Position.
  - Skull Guardian's answer resets at its controller's turn start (Suijin's never resets).
- **Gotcha, the CPU never goes to Defense Position:** the first build's CPU Bickuribox just sat there. The
  original AI raises Defense Position monsters to attack and flips set ones, but never moves one down, so a
  Dream Clown never triggers for it either. `ExtraDeckAiActivateEffects` now switches a face-up Attack
  Position Bickuribox (`ChangeBattlePosition`, `positionLocked`, the menu's own checks) when the human has a
  face-up monster at least as strong.
- **Gotcha, rebuilding in place:** `build.sh` reuses the mod worktree, and `patch_god_effects.py` couldn't find
  its `ai_deck.c` anchor under the newer edits. Removing the worktree first fixed it.
- **Gotcha, the Gods are DARK** in EDS's stats: Kaiser Dragon gets its +1000 against them (3300 still loses to
  Obelisk), Garma Sword's LIGHT rule never touches them.
- **Checks that changed:** the Goddess of Whim regression now accepts either side of the coin (the pinned
  state lands tails on the control build, heads on this one; the check is that the coin still links). The
  Extra Deck rituals' bounce check (Black Luster Soldier into a set Hane-Hane) now expects 2500 piercing
  damage with `--extra-deck-effects`: the first full run failed there only, with the bounce itself working.
- **Seen on screenshots:** the new texts in Card View ("[Dragon/Fusion]", "[Warrior/Ritual]"), Gaia's pick
  moving from Blue-Eyes to Dark Magician, Bickuribox's "destroy" prompt, Skull Guardian's question, Thousand
  Dragon's coin.
- **Results:**
  - the whole `gods-3t-fx` suite is 219/219 against `gods-3t` (151 before, plus 68: 48 played checks and the
    20 card texts), every control comparison as expected (17 not compared);
  - `gods-3t-fx` is `32a5568d...` (`.bps` 82,537 bytes), the same ROM and `.bps` from two fresh work dirs (the
    second cloned eds-decomp from GitHub); `gods`, `gods-3t` and `gods-fx` rebuild unchanged;
  - pytest, `um kb check --index` and `um publish check .` pass.
