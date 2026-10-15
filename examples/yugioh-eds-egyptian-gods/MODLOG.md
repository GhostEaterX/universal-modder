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
