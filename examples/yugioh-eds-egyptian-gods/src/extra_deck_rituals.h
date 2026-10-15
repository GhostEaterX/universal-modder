#ifndef GUARD_EXTRA_DECK_RITUALS_H
#define GUARD_EXTRA_DECK_RITUALS_H

/*
 * Ritual monsters in the Extra Deck (universal-modder, examples/yugioh-eds-egyptian-gods), in the three-Tribute
 * effects build: Ritual monsters live in the Fusion Deck (EDS's Extra Deck) next to the Fusion monsters, and a
 * Ritual Magic card summons its monster from there. patch_extra_deck_rituals.py copies this header and
 * src/extra_deck_rituals.c into an eds-decomp tree; the edited engine functions call the hooks below.
 */

#include "global.h"

struct ChainEntry;

/* 1 for a Fusion or Ritual monster: a card that lives in the Fusion Deck. The Gods (Divine, and Obelisk with
 * its Ritual frame) are not. Replaces the "kind == Fusion" pile tests: Deck Edit (DeckEdit_IsFusionMonster, the
 * copy counts, the Side Deck refusal), the CPU's deck lists (AddCardNumberToDeckTop), and a monster going back
 * to the hand or the deck in a duel (IsFusionMonster, AddCardToHand, the graveyard-to-hand animation). */
u32 IsExtraDeckMonster(u16 cardId);

/* duel_ritual.c HandHasRitualMonster (the Ritual Magic cards' activation and resolve checks): 1 if player's
 * Fusion Deck holds the ritual monster of gRitualRecipes[recipeIdx]. */
int FusionDeckHasRitualMonster(int player, int recipeIdx);
/* duel_ritual.c EffectRitualSummonResolve, RITUAL_STEP_TAKE_MONSTER: take the ritual monster out of the Fusion
 * Deck into gChain.effectCard (DUEL_CMD_REMOVE_CARD_FROM_FUSION_DECK). 0 if it isn't there (then the original
 * code looks in the hand). */
int TakeRitualMonsterFromFusionDeck(struct ChainEntry *link);

/* Cyber-Stein Special Summons a Fusion monster only. effect_activation.c and effect_resolve1.c: the Fusion
 * monsters in player's Fusion Deck (the original tested fusionCount). */
u32 CountFusionDeckFusionMonsters(int player);
/* effect_target_collect.c CollectEffectTargets, Cyber-Stein: list those Fusion monsters (gCardListView). */
void CollectFusionDeckFusionMonsters(int player);

/* main.c GameInit, right after the save is read: a save made before this mod keeps its Ritual monsters in the
 * saved Deck. Move them to the saved Fusion Deck, or back to the trunk when it is full, and update the
 * checksum. Leaves a save whose checksum is wrong (none yet, or damaged) alone. */
void MoveSavedRitualMonsters(void);

#endif /* GUARD_EXTRA_DECK_RITUALS_H */
