#ifndef GUARD_BOSS_EFFECTS_H
#define GUARD_BOSS_EFFECTS_H

/*
 * Boss effects (universal-modder, examples/yugioh-eds-egyptian-gods), in the three-Tribute effects build: the
 * Normal monsters that are the CPU duelists' bosses get effects, and Red-Eyes Black Metal Dragon gets a
 * weaker Metalmorph of its own. patch_boss_effects.py copies this header and src/boss_effects.c into an
 * eds-decomp tree that already has the God effects (god_effects.h, the relocated effect table); the edited
 * engine functions call the hooks below. Nothing here makes a boss immune to removal: Trap Hole, Dark Hole,
 * Raigeki, Hane-Hane, Penguin Soldier and Change of Heart work on them as before.
 */

#include "global.h"

struct ChainEntry;

/* Rows appended to gCardEffectsMod after the Gods' (data/god_effects_table.s): Dark Magician (34 and its
 * alternate art 2034) and Red-Eyes B. Dragon (81). They break the table's order, so FindCardEffect looks for
 * them with BossFindCardEffect when its binary search of the sorted rows fails. */
#define BOSS_EFFECT_ROWS    3

/* effect_hooks.c FindCardEffect, when the binary search finds no row: the index of the appended row for
 * card number `number`, or -1. */
int BossFindCardEffect(u16 number);

/* campaign.c CalcBattle. Summoned Skull: piercing battle damage. */
int BossPierces(u16 cardId);
/* Millennium Golem: never destroyed by battle (its controller still takes the damage). */
int BossBattleIndestructible(u16 cardId);
/* Red-Eyes Black Metal Dragon: when it attacks a monster, a quarter of that monster's ATK (Metalmorph gives
 * half), during damage calculation only. 0 for any other card. */
int BossAttackBonus(u16 cardId, int targetAtk);

/* The effect rows. Dark Magician: once per turn, destroy 1 Spell or Trap card the opponent controls. Red-Eyes
 * B. Dragon: once per turn, toss a coin; on heads, destroy 1 monster the opponent controls. */
int BossOncePerTurnPrepare(struct ChainEntry *card, struct ChainEntry *chainLink, u16 fromHand);
u16 BossOpponentSpellTrapCheck(struct ChainEntry *card, u16 pos);
u16 BossOpponentMonsterCheck(struct ChainEntry *card, u16 pos);
int BossDarkMagicianChainB(struct ChainEntry *link, struct ChainEntry *prevLink);
int BossRedEyesChainB(struct ChainEntry *link, struct ChainEntry *prevLink);
int BossDarkMagicianResolve(struct ChainEntry *link, struct ChainEntry *chainedTo);
int BossRedEyesResolve(struct ChainEntry *link, struct ChainEntry *chainedTo);

/* ai_deck.c AiActivateMonsterEffects, after the Gods: the CPU uses a face-up Dark Magician's or Red-Eyes'
 * effect whenever it can be activated (the original list of such monsters holds four cards in a fixed loop). */
int BossAiActivateEffects(void);

#endif /* GUARD_BOSS_EFFECTS_H */
