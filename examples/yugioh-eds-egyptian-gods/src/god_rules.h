#ifndef GUARD_GOD_RULES_H
#define GUARD_GOD_RULES_H

/*
 * The Egyptian Gods' TCG summon rules (universal-modder, examples/yugioh-eds-egyptian-gods), for the
 * three-Tribute effects build: a Special Summoned Obelisk or Slifer is sent to the Graveyard in the End Phase,
 * and Ra can't be Special Summoned. patch_god_rules.py copies this header and src/god_rules.c into an
 * eds-decomp tree that already has the God effects (god_effects.h); the edited engine functions call the
 * hooks below.
 */

#include "global.h"

/* duel_ritual.c CanReviveGraveyardCard (Monster Reborn, Call of the Haunted, Premature Burial, The Shallow
 * Grave, Spear Cretin: their target lists, the CPU's choices) and effect_resolve3.c Time Machine: 1 for Ra. */
int GodCannotBeSpecialSummoned(u16 cardId);
/* battle_phase3.c DuelPhase_End: each player's face-up Special Summoned Obelisk and Slifer go to the
 * Graveyard. */
void GodEndPhase(void);
/* summon_builders.c AiPickDiscard: 0 for a God, which the CPU shouldn't discard to revive (Ra can't come
 * back, Obelisk and Slifer leave at the End Phase). */
int GodAiMayDiscardToRevive(u16 cardId);

#endif /* GUARD_GOD_RULES_H */
