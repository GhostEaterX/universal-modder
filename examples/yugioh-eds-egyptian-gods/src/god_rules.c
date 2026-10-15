#include "global.h"
#include "card_data.h"              /* gCardIdToNumber, CARD_ID_MASK */
#include "constants/duel.h"         /* ZONE_MONSTER_* */
#include "constants/duel_cmds.h"    /* DUEL_CMD_SHOW_CARD_EFFECT, DUEL_CMD_PLAYER */
#include "duel.h"                   /* gDuelPlayers */
#include "duel_cmd.h"               /* DuelCmd_Push */
#include "duel_actions.h"           /* SendFieldCardToGrave */
#include "god_effects.h"            /* GOD_NUMBER_*, GOD_IS_GOD_NUMBER */
#include "god_rules.h"

/*
 * The Egyptian Gods' TCG summon rules (universal-modder), in the three-Tribute effects build only:
 *
 *   Obelisk, Slifer  If this card is Special Summoned, it is sent to the Graveyard during the End Phase.
 *   Ra               Cannot be Special Summoned.
 *
 * Every way back from the Graveyard but Time Machine lists its candidates through CanReviveGraveyardCard,
 * which also decides what the CPU can pick, so Ra drops out of those lists for both players. The other
 * Special Summons (from the deck, the hand, the Fusion Deck) already exclude a level-10, 4000-ATK Divine
 * monster, or name their cards.
 */

#define NUMBER_OF(id)       (gCardIdToNumber[(id) & CARD_ID_MASK])
#define CMD(player, cmd)    ((player) ? DUEL_CMD_PLAYER | (cmd) : (cmd))

int GodCannotBeSpecialSummoned(u16 cardId)
{
    return NUMBER_OF(cardId) == GOD_NUMBER_RA;
}

void GodEndPhase(void)
{
    int player;
    int zone;

    for (player = 0; player <= 1; player++) {
        for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++) {
            struct DuelZone *z = &gDuelPlayers[player].zones[zone];
            u16 number;

            if (!z->card.id || !z->isFaceUp || !z->card.specialSummoned)
                continue;
            number = NUMBER_OF(z->card.id);
            if (number != GOD_NUMBER_OBELISK && number != GOD_NUMBER_SLIFER)
                continue;
            DuelCmd_Push(CMD(player, DUEL_CMD_SHOW_CARD_EFFECT), z->card.id, 1, 0);
            SendFieldCardToGrave(player, zone, 0, 1);
        }
    }
}

int GodAiMayDiscardToRevive(u16 cardId)
{
    return !GOD_IS_GOD_NUMBER(NUMBER_OF(cardId));
}
