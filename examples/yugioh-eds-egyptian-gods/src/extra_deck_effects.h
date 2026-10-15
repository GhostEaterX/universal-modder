#ifndef GUARD_EXTRA_DECK_EFFECTS_H
#define GUARD_EXTRA_DECK_EFFECTS_H

/*
 * Extra Deck effects (universal-modder, examples/yugioh-eds-egyptian-gods), in the three-Tribute effects build:
 * the high-Level Fusion and Ritual monsters (all in the Extra Deck, EDS's Fusion Deck, in this build) get an
 * effect that makes their summon worth its cards. patch_extra_deck_effects.py copies this header and
 * src/extra_deck_effects.c into an eds-decomp tree that already has the God and boss effects
 * (patch_boss_effects.py); the edited engine functions call the hooks below. Some effects need no hook: the
 * patch adds their cards to the engine's own lists (card_stats.c, battle_phase1.c, duel_field_moves.c).
 */

#include "global.h"

struct ChainEntry;

/* Rows appended to gCardEffectsMod after the bosses' (data/god_effects_table.s): Magician of Black Chaos, Gaia
 * the Dragon Champion, Super War-Lion, Thousand Dragon (68 and its alternate art 2068) and Bickuribox. Like the
 * bosses' rows they break the table's order. */
#define EXTRA_DECK_EFFECT_ROWS  6

/* effect_hooks.c FindCardEffect, when the binary search finds no row: the boss rows, then these; -1 if the
 * number has no appended row. */
int ExtraDeckFindCardEffect(u16 number);

/* campaign.c CalcBattle. B. Skull Dragon, Black Luster Soldier and Javelin Beetle: piercing battle damage. */
int ExtraDeckPierces(u16 cardId);
/* Labyrinth Tank, Crab Turtle and Fortress Whale: never destroyed by battle (the damage stays). */
int ExtraDeckBattleIndestructible(u16 cardId);
/* Kaiser Dragon: 1000 ATK more in a battle with a DARK monster (`foeAttribute` is the other monster's). */
int ExtraDeckBattleAtkBonus(u16 cardId, int foeAttribute);
/* Garma Sword: 1 if the monster it battles is destroyed when it is LIGHT. */
int ExtraDeckDestroysLight(u16 cardId);

/* duel_cmd_turn.c DuelCmd_TurnEnd, for each monster zone: Thousand Dragon's coin lasts until the end of the
 * turn, as Goddess of Whim's (whose links the ROM's list gEndOfTurnEffectCards ends). */
void ExtraDeckEndOfTurnLinks(int player, int zone);

/* The effect rows. Gaia the Dragon Champion and Super War-Lion: once per turn, in Main Phase 1, destroy 1
 * face-up monster the opponent controls with less ATK; the monster can't attack that turn. Thousand Dragon:
 * Goddess of Whim's once-per-turn coin. Bickuribox: Dream Clown's trigger (destroy 1 monster when it is
 * changed to Defense Position). Magician of Black Chaos takes Dark Magician's row, and the rows reuse the boss
 * unit's wrappers of the once-per-turn prepare and of the opponent's-monster check and pick (boss_effects.c). */
int ExtraDeckChampionPrepare(struct ChainEntry *card, struct ChainEntry *chainLink, u16 fromHand);
u16 ExtraDeckChampionCheck(struct ChainEntry *card, u16 pos);
int ExtraDeckChampionChainB(struct ChainEntry *link, struct ChainEntry *prevLink);
int ExtraDeckChampionResolve(struct ChainEntry *link, struct ChainEntry *chainedTo);
int ExtraDeckThousandDragonResolve(struct ChainEntry *link, struct ChainEntry *chainedTo);
int ExtraDeckDestroyTargetResolve(struct ChainEntry *link, struct ChainEntry *chainedTo);

/* ai_deck.c AiActivateMonsterEffects, after the bosses: a face-up Magician of Black Chaos, Thousand Dragon (in
 * Attack Position), Gaia or Super War-Lion of the CPU uses its effect when it can be activated; Gaia and
 * Super War-Lion only when their target is in Defense Position or the human controls two or more monsters
 * (else attacking the target also deals damage). A face-up Attack Position Bickuribox goes to Defense Position
 * when the human controls a face-up monster with at least its ATK, which triggers it. 1 if it did one of these. */
int ExtraDeckAiActivateEffects(void);

#endif /* GUARD_EXTRA_DECK_EFFECTS_H */
