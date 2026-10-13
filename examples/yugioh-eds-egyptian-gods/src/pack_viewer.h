#ifndef GUARD_PACK_VIEWER_H
#define GUARD_PACK_VIEWER_H

/*
 * Pack viewer (universal-modder, examples/yugioh-eds-egyptian-gods): on the pick-a-pack screen after a duel,
 * the bottom band names the centre pack, and SELECT lists every card in it, with the chance that the card is in
 * the pack you'd get. patch_pack_viewer.py copies this header and src/pack_viewer.c into an eds-decomp tree,
 * generates include/pack_viewer_data.h from the tree's booster_packs.json (scripts/gen_pack_odds.py) and makes
 * the edits that call the hooks below.
 */

#include "global.h"

/* One card of a pack's list. agbcc pads it to 12 bytes; the generated table only uses initialisers. */
struct PackViewCard {
    u16 number;     /* card number */
    u8 slot;        /* its rarest slot: 0 is the rarest, the commons slot the last */
    u8 pad;
    u16 odds[3];    /* chance it is in the pack, in 0.01%: normal roll, same pack as last time, pity roll */
};

/* One pack of the pick-a-pack screen. */
struct PackViewPack {
    u16 id;             /* pack id (gPackInfo) */
    u16 count;          /* cards in its list */
    u16 first;          /* index of its first card in the card table */
    u8 commonSlot;      /* GetPackCommonSlot */
    u8 pad;
    u16 rare[3];        /* chance that the rolled card comes from a rarer slot, per roll, 0.01% */
    u16 pad2;
    const char *name;   /* full name */
};

/* gMain.seqState1 values of GetPack_SelectAndGenerate that the viewer runs (vanilla uses 0-4). */
#define PACKVIEW_STATE_FIRST    0x20
/* PackList_HandleInput's return value for SELECT. */
#define PACKVIEW_OPEN           2

/* booster_pack.c GetPack_SelectAndGenerate, sub-state 2: SELECT was pressed on the pick screen. */
void PackView_Open(void);
/* GetPack_SelectAndGenerate, sub-states PACKVIEW_STATE_FIRST and up. Returns 0; once the list closes it puts
 * the sub-state back to 1 (PackList_Init). */
int PackView_Run(void);
/* deck_edit_panel.c PackList_Init, sub-state 0: the left slot's pack, which is firstIndex unless the list
 * is coming back from the viewer. */
s32 PackView_ListStart(s32 firstIndex);
/* booster_get_pack.c PackList_DrawCovers: the centre pack's name and the SELECT hint in the bottom band. */
void PackView_DrawPickName(void);
/* card_canvas.c GetPack_DrawCardRow: TextCanvasInit, except in the viewer, where only the row's tiles of the
 * canvas are cleared (TextCanvasInit clears all 64 KB, about 3 frames, and the list redraws 5 rows at once). */
void PackView_CanvasInit(u32 widthTiles, u32 heightTiles);

#endif /* GUARD_PACK_VIEWER_H */
