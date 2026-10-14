/*
 * Pack viewer (universal-modder, examples/yugioh-eds-egyptian-gods).
 *
 * On the pick-a-pack screen after a duel, the bottom band names the centre pack. SELECT opens a list of every
 * card in it, rarest slot first. Each row is drawn like a row of the pack-opening scene, plus the chance that
 * the card is in the pack you'd get, and NEW on cards you don't own (else how many copies you have). The odds follow the save: picking
 * the same pack as last time makes the rare slots 2/3 as likely, and the pity roll guarantees a rare card.
 * A opens Card Detail (LEFT/RIGHT go through the list), and B goes back to the pick screen with the same pack
 * in the centre.
 *
 * Elsewhere: every Card Detail outside a duel ends with the packs that hold the card and its chance in each
 * ("Found in: Vol.3 1.7%, ..."), and the pack rows show a God's stats, which the original row drawer leaves
 * out.
 *
 * The list runs inside GetPack_SelectAndGenerate, on sub-states PACKVIEW_STATE_FIRST and up. It uses the
 * pack-opening scene's video setup (GetPack_InitScene) and row drawer (GetPack_DrawCardRow), and keeps its
 * state in gPackOpenWork, which is cleared before a pack is generated. The odds table, pack_viewer_data.h, is
 * generated at build time from the tree's booster_packs.json by scripts/gen_pack_odds.py.
 */
#include "global.h"
#include "gba.h"
#include "main.h"
#include "booster.h"
#include "card_data.h"
#include "card_detail.h"
#include "constants/sound.h"
#include "palette.h"
#include "save.h"
#include "sound.h"
#include "sprite.h"
#include "text.h"
#include "bg.h"
#include "campaign.h"
#include "pack_viewer.h"
#include "pack_viewer_data.h"   /* generated: sPackViewCards, sPackViewPacks */

extern struct PackListWork gSceneWork;              /* 0x02020310, the pick screen's work area */
extern const u16 gPackCursorSlideOffsets[8];        /* 0x0808658C, the highlight frame's slide */
int GetCardIconObjTile(u16 cardId);                 /* card_canvas.c */

/* The list's state, in gPackOpenWork from +4 (4-aligned, inside commonPool). */
struct PackViewWork {
    u16 packRows[0x20];     /* the pick screen's list, kept in case Card Detail reuses gSceneWork */
    u16 packCount;
    u16 firstIndex;
    u16 pack;               /* row of sPackViewPacks */
    u16 entries;            /* entry 0 is the header, entry e > 0 the pack's card e - 1 */
    u16 top;                /* entry shown in row 0 */
    u16 sel;                /* entry of the open Card Detail */
    u16 rowId[5];           /* card ID of each row, 0 for the header */
    u8 mode;                /* odds column: PACKVIEW_ODDS_* */
    s8 moveDir;             /* rows whose tiles move at the next VBlank: 1 up, -1 down, 0 none */
    u8 dirty;               /* rows still to draw, one per frame (bit n = row n) */
    u16 owned;              /* cards of the pack you own at least one copy of */
};
#define sView ((struct PackViewWork *)((u8 *)&gPackOpenWork + 4))
typedef char pack_viewer_check_work[sizeof(struct PackViewWork) + 4 <= 0x102 ? 1 : -1];   /* commonPool */

enum {
    PACKVIEW_ODDS_NORMAL = 0,
    PACKVIEW_ODDS_SAME_PACK = 1,    /* Random() % 270 */
    PACKVIEW_ODDS_PITY = 2,         /* Random() % 12 */
};

enum {
    PV_PICK_FADE_OUT = PACKVIEW_STATE_FIRST,
    PV_INIT,
    PV_FADE_IN,
    PV_INPUT,
    PV_CLOSE,
    PV_DETAIL_SETUP,
    PV_DETAIL_VIDEO,
    PV_DETAIL_FADE_IN,
    PV_DETAIL_INPUT,
    PV_DETAIL_CLOSE,
    PV_DETAIL_SWITCH,
};

#define GOD_NUMBER_SLIFER_PV    1911    /* CARD_SLIFER_THE_SKY_DRAGON */
#define GOD_NUMBER_RA_PV        1912    /* CARD_THE_WINGED_DRAGON_OF_RA */

#define PV_ROWS         5           /* rows of 32 pixels, as in the opening scene */
#define PV_TILE_ROW     0x220       /* 4bpp tiles of char block 1 the opening scene leaves free: */
#define PV_TILE_HEADER  0x250       /*   8 per row (odds and NEW), then the header's name and two lines */
#define PV_HEADER_NAME_W 28         /* header name canvas, in tiles */
#define PV_COLORS       7           /* palette 0 colour of the opening scene's text */
#define PV_NEW_COLORS   6           /* yellow (15 is the colour-cycled one of the rare names) */

/* The pick screen's BG0 is a 4bpp layer (ResetVideo leaves it so) on the same char block as the 8bpp covers.
 * Its text goes in the tile buffer's bytes after the four covers (8bpp tile 0x198 = 4bpp tile 0x330). */
#define PV_PICK_TILE    0x330
#define PV_PICK_ROW     17          /* the bottom band: rows 17-19 */
#define PV_PICK_PAL     14          /* gPackListPal 224-239, where */
#define PV_PICK_WHITE   11          /*   235 is white */
#define PV_PICK_YELLOW  9           /*   and 233 pale yellow */

/* BIOS CpuFastSet copies and clears (sizes in bytes, multiples of 32). */
static void FastCopy(void *dst, const void *src, u32 size)
{
    CpuFastSet(src, dst, size / 4);
}

static void FastClear(void *dst, u32 size)
{
    vu32 zero = 0;
    CpuFastSet((const void *)&zero, dst, CPU_FAST_SET_SRC_FIXED | size / 4);
}

/* TextCanvasInit for the tiles in use only: the rest of the 64 KB canvas is never read. */
static void CanvasInit(u32 widthTiles, u32 heightTiles)
{
    gTextCanvas.width = widthTiles;
    gTextCanvas.height = heightTiles;
    gTextCanvas.layout.raw = 0;
    FastClear(gTextCanvas.pixels, widthTiles * heightTiles * 64);
}

void PackView_CanvasInit(u32 widthTiles, u32 heightTiles)
{
    if (gMain.seqIndex1 == GETPACK_STEP_SELECT && gMain.seqState1 >= PACKVIEW_STATE_FIRST)
        CanvasInit(widthTiles, heightTiles);
    else
        TextCanvasInit(widthTiles, heightTiles);
}

static u16 CardNumberToId(u16 number)
{
    if (number == 0xFFFF)
        return 0;
    if (number < CARD_NUMBER_ALT_ART)
        return gCardNumberToId[number & CARD_ID_MASK];
    return gCardNumberToId[(number - CARD_NUMBER_ALT_ART) & CARD_ID_MASK] + 1;
}

/* The centre pack of the pick screen's list. */
static u16 PickedPackId(void)
{
    struct PackListWork *s = &gSceneWork;
    return gPackInfo[s->packRows[(s->firstIndex + s->centerSlot) % s->packCount]].id;
}

static int FindPack(u16 packId)
{
    int i;
    for (i = 0; i < PACKVIEW_PACK_COUNT; i++) {
        if (sPackViewPacks[i].id == packId)
            return i;
    }
    return -1;
}

/* Which roll the next pack of packId gets (RollPackRarity). */
static int OddsMode(u16 packId)
{
    if (gSaveData.packPityCount > 5 && (gSaveData.lastPackId != packId || gSaveData.packPityCount > 10))
        return PACKVIEW_ODDS_PITY;
    if (gSaveData.lastPackId == packId)
        return PACKVIEW_ODDS_SAME_PACK;
    return PACKVIEW_ODDS_NORMAL;
}

static const struct PackViewCard *EntryCard(int entry)
{
    struct PackViewWork *v = sView;
    return &sPackViewCards[sPackViewPacks[v->pack].first + entry - 1];
}

/* Copies of a card you own: the trunk's spare copies plus those in the saved Deck, Side Deck and Fusion Deck
 * (IsCardNumberOwned tests the same four fields). */
static u32 OwnedCopies(u16 number)
{
    struct TrunkEntry *entry = &gSaveData.trunk[CardNumberToId(number)];
    return entry->count + entry->deckCopies + entry->sideCopies + entry->fusionCopies;
}

/* Cards of a pack you own at least one copy of. */
static int OwnedInPack(int pack)
{
    const struct PackViewCard *card = &sPackViewCards[sPackViewPacks[pack].first];
    int n = 0;
    int i;
    for (i = 0; i < sPackViewPacks[pack].count; i++, card++) {
        if (OwnedCopies(card->number) != 0)
            n++;
    }
    return n;
}

/* "16.8%", " 4.4%", "0.42%", " 100%" or "   0%" for a chance in 0.01% steps. */
static void FormatOdds(char *s, u32 odds)
{
    u32 t;
    s[4] = '%';
    s[5] = 0;
    if (odds == 0) {
        s[0] = s[1] = s[2] = ' ';
        s[3] = '0';
        return;
    }
    if (odds < 100) {
        s[0] = '0';
        s[1] = '.';
        s[2] = '0' + odds / 10;
        s[3] = '0' + odds % 10;
        return;
    }
    t = (odds + 5) / 10;
    if (t >= 1000) {
        s[0] = ' ';
        s[1] = '1';
        s[2] = s[3] = '0';
        return;
    }
    s[0] = t >= 100 ? '0' + t / 100 : ' ';
    s[1] = '0' + t / 10 % 10;
    s[2] = '.';
    s[3] = '0' + t % 10;
}

static char *AppendString(char *s, const char *add)
{
    while (*add != 0)
        *s++ = *add++;
    *s = 0;
    return s;
}

static char *AppendNumber(char *s, u32 n)
{
    char digits[6];
    int i = 0;
    do {
        digits[i++] = '0' + n % 10;
        n /= 10;
    } while (n != 0);
    while (i > 0)
        *s++ = digits[--i];
    *s = 0;
    return s;
}

/*
 * Drawing without tearing. The main loop copies the BG map buffers to VRAM at the start of each frame
 * (FrameSyncUpdate, in VBlank), then runs the scene, well into the visible frame; tiles and palettes written by
 * the scene show at once. So:
 *   - a row is drawn while its VRAM map is blank: its map lines are cleared in VRAM first, the tiles drawn,
 *     and the new map lines reach VRAM with the next frame's copy;
 *   - a scroll moves the four rows that stay: their new map lines go to the buffer, and their tiles and icon
 *     palettes move in the VBlank callback, just before the copy (PackViewVBlank); the new row is drawn on
 *     the next frame;
 *   - a page redraws the rows one per frame (v->dirty); the first draw, still black, draws them all at once.
 * The card sprites are queued after any change, so they reach OAM with the same copy as the maps.
 */
#define ROW_MAP(row)        (&gMain.bgMapBuffer[0][(row) * 4 * 32])
#define ROW_VRAM_MAP(row)   ((u16 *)VRAM + (row) * 4 * 32)
#define ROW_TILES(tile)     ((void *)(VRAM + 0x4000 + (tile) * 32))

/* Row 0 of the list: the pack's full name, how many of its cards you own, the rare chance, and what the save
 * does to the odds. */
static void DrawHeader(int row)
{
    struct PackViewWork *v = sView;
    const struct PackViewPack *pack = &sPackViewPacks[v->pack];
    char line[32];
    char odds[6];
    char *s;
    int i;
    int k;
    u16 tile = PV_TILE_HEADER;

    CanvasInit(PV_HEADER_NAME_W, 2);
    TextDrawString(2, 6, PV_COLORS | TEXT_SIZE(10), (const u8 *)pack->name);
    TextCanvasToTiles((u16 *)ROW_TILES(tile), 0);
    for (i = 0; i <= 1; i++) {
        for (k = 0; k < PV_HEADER_NAME_W; k++)
            gMain.bgMapBuffer[0][(row * 4 + i) * 32 + 1 + k] = tile + k + i * PV_HEADER_NAME_W;
    }
    tile += PV_HEADER_NAME_W * 2;

    s = AppendNumber(line, v->owned);
    s = AppendString(s, "/");
    s = AppendNumber(s, pack->count);
    s = AppendString(s, " owned  ");
    if (pack->rare[0] == 0) {
        AppendString(s, "all commons");
    } else {
        s = AppendString(s, "rare card ");
        FormatOdds(odds, pack->rare[v->mode]);
        AppendString(s, odds[0] == ' ' ? odds + 1 : odds);
    }
    DrawBgString((row * 4 + 2) * 32 + 1, PV_COLORS, tile, line);
    tile += 29;
    if (pack->rare[0] == 0 || v->mode == PACKVIEW_ODDS_NORMAL)
        AppendString(line, "% = chance it's in your pack");
    else if (v->mode == PACKVIEW_ODDS_SAME_PACK)
        AppendString(line, "Same pack again: rares x2/3");
    else
        AppendString(line, "Lucky pack: a rare for sure");
    DrawBgString((row * 4 + 3) * 32 + 1, PV_COLORS, tile, line);
}

/* NEW for a card you don't own, else how many copies you have: "x1" to "x99", "99+". */
static void DrawCopies(int row, u32 copies)
{
    char text[4];
    if (copies == 0) {
        DrawBgString((row * 4 + 3) * 32 + 20, PV_NEW_COLORS, PV_TILE_ROW + row * 8 + 5, "NEW");
        return;
    }
    if (copies > 99) {
        AppendString(text, "99+");
    } else {
        text[0] = 'x';
        AppendNumber(text + 1, copies);
    }
    DrawBgString((row * 4 + 3) * 32 + 20, PV_COLORS, PV_TILE_ROW + row * 8 + 5, text);
}

/* Draws the row for entry top + row: blank in VRAM now, the new map lines from the next frame. */
static void DrawRow(int row)
{
    struct PackViewWork *v = sView;
    int entry = v->top + row;
    const struct PackViewCard *card;
    char odds[6];
    u16 id;

    FastClear(ROW_VRAM_MAP(row), 4 * 32 * 2);
    FastClear(ROW_MAP(row), 4 * 32 * 2);
    v->rowId[row] = 0;
    if (entry == 0) {
        DrawHeader(row);
        return;
    }
    if (entry >= v->entries)
        return;
    card = EntryCard(entry);
    id = CardNumberToId(card->number);
    v->rowId[row] = id;
    /* the opening scene colours the rolled card's name when it came from a rarer slot */
    gPackOpenWork.rareCardNumber = card->slot != sPackViewPacks[v->pack].commonSlot ? card->number : 9999;
    GetPack_DrawCardRow(row, id);
    FormatOdds(odds, card->odds[v->mode]);
    DrawBgString((row * 4 + 3) * 32 + 25, PV_COLORS, PV_TILE_ROW + row * 8, odds);
    DrawCopies(row, OwnedCopies(card->number));
}

static void DrawRows(void)
{
    int row;
    for (row = 0; row < PV_ROWS; row++)
        DrawRow(row);
}

/* A map entry of row src, moved to row src + rel: the per-row tiles and palettes of GetPack_DrawCardRow (name
 * 0x40 + row * 0x30, icons 0x300/0x320 + row * 4 in palettes row + 5 and row + 10, ATK/DEF digits 0x1A0/0x1C8
 * + row * 8) and of this file (PV_TILE_ROW + row * 8) follow; the shared ones (stars, ATK/DEF label) stay. */
static u16 MovedMapEntry(u16 entry, int src, int rel)
{
    int tile = entry & 0x3FF;
    if (tile >= 0x40 + src * 0x30 && tile < 0x70 + src * 0x30)
        return entry + rel * 0x30;
    if ((tile >= 0x300 + src * 4 && tile < 0x304 + src * 4) || (tile >= 0x320 + src * 4 && tile < 0x324 + src * 4))
        return entry + rel * 4 + rel * 0x1000;
    if ((tile >= 0x1A0 + src * 8 && tile < 0x1A8 + src * 8) || (tile >= 0x1C8 + src * 8 && tile < 0x1D0 + src * 8)
        || (tile >= PV_TILE_ROW + src * 8 && tile < PV_TILE_ROW + 8 + src * 8))
        return entry + rel * 8;
    return entry;
}

static void MoveRowMap(int src, int dst)
{
    u16 *from = ROW_MAP(src);
    u16 *to = ROW_MAP(dst);
    int i;
    for (i = 0; i < 4 * 32; i++)
        to[i] = from[i] != 0 ? MovedMapEntry(from[i], src, dst - src) : 0;
}

static void MoveRowTiles(int src, int dst)
{
    FastCopy(ROW_TILES(0x40 + dst * 0x30), ROW_TILES(0x40 + src * 0x30), 0x30 * 32);
    FastCopy(ROW_TILES(0x300 + dst * 4), ROW_TILES(0x300 + src * 4), 4 * 32);
    FastCopy(ROW_TILES(0x320 + dst * 4), ROW_TILES(0x320 + src * 4), 4 * 32);
    FastCopy(ROW_TILES(0x1A0 + dst * 8), ROW_TILES(0x1A0 + src * 8), 8 * 32);
    FastCopy(ROW_TILES(0x1C8 + dst * 8), ROW_TILES(0x1C8 + src * 8), 8 * 32);
    FastCopy(ROW_TILES(PV_TILE_ROW + dst * 8), ROW_TILES(PV_TILE_ROW + src * 8), 8 * 32);
    FastCopy((void *)(BG_PLTT + (dst + 5) * 32), (void *)(BG_PLTT + (src + 5) * 32), 32);
    FastCopy((void *)(BG_PLTT + (dst + 10) * 32), (void *)(BG_PLTT + (src + 10) * 32), 32);
}

/* gMain.vblankCallback while the list is up: a scroll's tile moves, each row read before it is overwritten. */
static void PackViewVBlank(void)
{
    struct PackViewWork *v = sView;
    int row;
    if (v->moveDir > 0) {
        for (row = 0; row < PV_ROWS - 1; row++)
            MoveRowTiles(row + 1, row);
    } else if (v->moveDir < 0) {
        for (row = PV_ROWS - 1; row > 0; row--)
            MoveRowTiles(row - 1, row);
    }
    v->moveDir = 0;
}

/* UP/DOWN past the first or last row: one entry further. */
static void ScrollRows(int dir)
{
    struct PackViewWork *v = sView;
    int row;
    int fresh;
    v->top += dir;
    if (dir > 0) {
        for (row = 0; row < PV_ROWS - 1; row++) {
            MoveRowMap(row + 1, row);
            v->rowId[row] = v->rowId[row + 1];
        }
        fresh = PV_ROWS - 1;
    } else {
        for (row = PV_ROWS - 1; row > 0; row--) {
            MoveRowMap(row - 1, row);
            v->rowId[row] = v->rowId[row - 1];
        }
        fresh = 0;
    }
    FastClear(ROW_MAP(fresh), 4 * 32 * 2);  /* blank until drawn: its tiles are still the source of a move */
    v->rowId[fresh] = 0;
    v->dirty |= 1 << fresh;
    v->moveDir = dir;
}

static void DrawSprites(void)
{
    struct PackViewWork *v = sView;
    int row;
    for (row = 0; row < PV_ROWS; row++) {
        if (v->rowId[row] != 0)
            AddSpriteXY((u16)-4, row * 32, 0x80, 0x1000 | GetCardIconObjTile(v->rowId[row]));
    }
}

static void StopHBlank(void)
{
    REG_IME = 0;
    REG_IE &= ~INTR_FLAG_HBLANK;
    REG_IME = 1;
    IntrTable[INTR_SLOT_HBLANK] = 0;
}

/* LEFT/RIGHT: a page up or down; at the first or last page, the cursor goes to the first or last row. */
static void Page(int dir)
{
    struct PackViewWork *v = sView;
    int last = v->entries > PV_ROWS ? v->entries - PV_ROWS : 0;
    int top = v->top + dir * PV_ROWS;
    int row;
    if (top < 0)
        top = 0;
    if (top > last)
        top = last;
    if (top != v->top) {
        v->top = top;
        v->dirty = (1 << PV_ROWS) - 1;
        PlaySE(SE_CURSOR);
        return;
    }
    row = dir > 0 ? v->entries - 1 - v->top : 0;
    if (row > PV_ROWS - 1)
        row = PV_ROWS - 1;
    if (row != gPackOpenWork.cursorRow) {
        gPackOpenWork.cursorRow = row;
        PlaySE(SE_CURSOR);
    } else {
        PlaySE(SE_ERROR);
    }
}

static void HandleKeys(void)
{
    struct PackViewWork *v = sView;
    int entry = v->top + gPackOpenWork.cursorRow;
    if (gMain.newKeys & DPAD_UP) {
        if (gPackOpenWork.cursorRow != 0) {
            gPackOpenWork.cursorRow--;
            gPackOpenWork.cursorAnimStep = 7;
            gPackOpenWork.cursorAnimDir = PACK_CURSOR_ANIM_UP;
            PlaySE(SE_CURSOR);
        } else if (v->top != 0) {
            ScrollRows(-1);
            PlaySE(SE_CURSOR);
        } else {
            PlaySE(SE_ERROR);
        }
    } else if (gMain.newKeys & DPAD_DOWN) {
        if (entry + 1 >= v->entries) {
            PlaySE(SE_ERROR);
        } else if (gPackOpenWork.cursorRow < PV_ROWS - 1) {
            gPackOpenWork.cursorAnimStep = 0;
            gPackOpenWork.cursorAnimDir = PACK_CURSOR_ANIM_DOWN;
            PlaySE(SE_CURSOR);
        } else {
            ScrollRows(1);
            PlaySE(SE_CURSOR);
        }
    } else if (gMain.newKeys & DPAD_RIGHT) {
        Page(1);
    } else if (gMain.newKeys & DPAD_LEFT) {
        Page(-1);
    } else if (gMain.newKeys & A_BUTTON) {
        if (entry == 0) {
            PlaySE(SE_ERROR);
        } else {
            PlaySE(SE_CONFIRM);
            v->sel = entry;
            gMain.seqState1 = PV_DETAIL_SETUP;
        }
    } else if (gMain.newKeys & (B_BUTTON | SELECT_BUTTON)) {
        PlaySE(SE_CANCEL);
        gMain.seqState1 = PV_CLOSE;
    }
}

static void HandleInput(void)
{
    struct PackViewWork *v = sView;
    int row;

    GetPack_ScrollBg();
    /* the highlight frame, as in GetPack_HandleInput */
    gMain.bgVofs[1] = -(gPackOpenWork.cursorRow << 5) - gPackCursorSlideOffsets[gPackOpenWork.cursorAnimStep];
    if (gPackOpenWork.cursorAnimDir == PACK_CURSOR_ANIM_UP) {
        if (gPackOpenWork.cursorAnimStep != 0)
            gPackOpenWork.cursorAnimStep--;
        else
            gPackOpenWork.cursorAnimDir = PACK_CURSOR_ANIM_NONE;
    } else if (gPackOpenWork.cursorAnimDir == PACK_CURSOR_ANIM_DOWN) {
        gPackOpenWork.cursorAnimStep++;
        if (gPackOpenWork.cursorAnimStep == 0) {
            gPackOpenWork.cursorAnimDir = PACK_CURSOR_ANIM_NONE;
            gPackOpenWork.cursorRow++;
        }
    }
    if (gPackOpenWork.cursorAnimDir == PACK_CURSOR_ANIM_NONE && v->moveDir == 0) {
        if (v->dirty != 0) {
            for (row = 0; !(v->dirty & (1 << row)); row++)
                ;
            DrawRow(row);
            v->dirty &= ~(1 << row);    /* after: a draw can run past the end of the frame */
        } else {
            HandleKeys();
        }
    }
    DrawSprites();
}

/* Back to the pick screen: PackList_Init from its first sub-state, with the same pack in the centre. */
static void BackToPicks(void)
{
    struct PackViewWork *v = sView;
    struct PackListWork *s = &gSceneWork;
    int i;
    gMain.vblankCallback = NULL;
    StopHBlank();
    for (i = 0; i < 0x20; i++)
        s->packRows[i] = v->packRows[i];
    s->packCount = v->packCount;
    s->flags = 0;
    s->slideFrame = 0;
    s->slideDir = 0;
    s->slideTo = 0;
    s->slideFrom = 0;
    s->unused8 = v->firstIndex + 1;     /* read by PackView_ListStart */
    s->state = 0;
    s->unused4 = 0;
    gMain.seqState1 = 1;
}

void PackView_Open(void)
{
    struct PackViewWork *v = sView;
    struct PackListWork *s = &gSceneWork;
    u16 packId = PickedPackId();
    int pack = FindPack(packId);
    int i;
    if (pack < 0) {         /* the generator lists every pack of gPackInfo, so this doesn't happen */
        PlaySE(SE_ERROR);
        return;
    }
    for (i = 0; i < 0x20; i++)
        v->packRows[i] = s->packRows[i];
    v->packCount = s->packCount;
    v->firstIndex = s->firstIndex;
    v->pack = pack;
    v->entries = sPackViewPacks[pack].count + 1;
    v->top = 0;
    v->sel = 1;
    v->mode = OddsMode(packId);
    v->owned = OwnedInPack(pack);
    v->moveDir = 0;
    v->dirty = 0;
    gPackOpenWork.cursorRow = 1;
    gPackOpenWork.cursorAnimStep = 0;
    gPackOpenWork.cursorAnimDir = PACK_CURSOR_ANIM_NONE;
    gMain.seqState1 = PV_PICK_FADE_OUT;
}

int PackView_Run(void)
{
    struct PackViewWork *v = sView;
    switch (gMain.seqState1) {
    case PV_PICK_FADE_OUT:
        if (PackList_FadeOut() != 0)
            gMain.seqState1 = PV_INIT;
        break;
    case PV_INIT:
        GetPack_InitScene();            /* black until the fade-in, so all rows at once */
        v->moveDir = 0;
        v->dirty = 0;
        DrawRows();
        gMain.vblankCallback = PackViewVBlank;
        gMain.seqState1 = PV_FADE_IN;
        break;
    case PV_FADE_IN:
        REG_DISPCNT |= 0x1F00;
        GetPack_ScrollBg();
        DrawSprites();
        if ((u16)FadeFromBlack(4) != 0)
            gMain.seqState1 = PV_INPUT;
        break;
    case PV_INPUT:
        HandleInput();
        break;
    case PV_CLOSE:
        GetPack_ScrollBg();
        DrawSprites();
        if ((u16)FadeToBlack(2) != 0)
            BackToPicks();
        break;
    case PV_DETAIL_SETUP:
        gMain.vblankCallback = NULL;
        StopHBlank();
        CardDetail_Init(CardNumberToId(EntryCard(v->sel)->number), 0, 0);
        gMain.seqState1 = PV_DETAIL_VIDEO;
        break;
    case PV_DETAIL_VIDEO:
        if (CardDetail_InitVideo() != 0) {
            CardDetail_DrawCard();
            gMain.seqState1 = PV_DETAIL_FADE_IN;
        }
        break;
    case PV_DETAIL_FADE_IN:
        if (CardDetail_FadeIn() != 0)
            gMain.seqState1 = PV_DETAIL_INPUT;
        break;
    case PV_DETAIL_INPUT:
        if (CardDetail_HandleInput() != 0)
            gMain.seqState1 = PV_DETAIL_CLOSE;
        if (gMain.newKeys & DPAD_RIGHT) {
            v->sel = v->sel + 1 < v->entries ? v->sel + 1 : 1;
            gMain.seqState1 = PV_DETAIL_SWITCH;
        }
        if (gMain.newKeys & DPAD_LEFT) {
            v->sel = v->sel > 1 ? v->sel - 1 : v->entries - 1;
            gMain.seqState1 = PV_DETAIL_SWITCH;
        }
        break;
    case PV_DETAIL_CLOSE:
        if (CardDetail_FadeOut() != 0) {
            /* back to the list with the last card shown under the cursor */
            if (v->sel < v->top)
                v->top = v->sel;
            else if (v->sel >= v->top + PV_ROWS)
                v->top = v->sel - (PV_ROWS - 1);
            gPackOpenWork.cursorRow = v->sel - v->top;
            gMain.seqState1 = PV_INIT;
        }
        break;
    case PV_DETAIL_SWITCH:
        if (CardDetail_FadeOut() != 0)
            gMain.seqState1 = PV_DETAIL_SETUP;
        break;
    default:
        gMain.seqState1 = PV_CLOSE;
        break;
    }
    return 0;
}

s32 PackView_ListStart(s32 firstIndex)
{
    struct PackListWork *s = &gSceneWork;
    if (s->unused8 != 0) {
        firstIndex = s->unused8 - 1;
        s->unused8 = 0;
    }
    return firstIndex;
}

/* The pick screen's text: the 10-pixel font on gTextCanvas, each line centred on the 240-pixel band. The Latin
 * font is fixed-width, half its size per character (TextDrawLatinString). */
#define PV_PICK_CANVAS_W    30
#define PV_PICK_CANVAS_ROWS 3       /* the band's three tile rows */
#define PV_PICK_FONT        10

static void DrawPickLine(int y, u16 color, const char *str)
{
    int n = 0;
    int x;
    while (str[n] != 0)
        n++;
    x = (PV_PICK_CANVAS_W * 8 - n * (PV_PICK_FONT / 2)) / 2;
    if (x < 0)
        x = 0;
    TextDrawString(x, y, color | TEXT_SIZE(PV_PICK_FONT), (const u8 *)str);
}

void PackView_DrawPickName(void)
{
    int pack = FindPack(PickedPackId());
    u16 *map = gMain.bgMapBuffer[0];
    char line[48];
    char *s;
    int i;
    if (pack < 0)
        return;
    CanvasInit(PV_PICK_CANVAS_W, PV_PICK_CANVAS_ROWS);
    DrawPickLine(1, PV_PICK_WHITE, sPackViewPacks[pack].name);
    s = AppendNumber(line, OwnedInPack(pack));
    s = AppendString(s, "/");
    s = AppendNumber(s, sPackViewPacks[pack].count);
    AppendString(s, " owned  -  SELECT: cards and odds");
    DrawPickLine(13, PV_PICK_YELLOW, line);
    TextCanvasToTiles((u16 *)&gSceneWork.bgTiles[PV_PICK_TILE * 32], 0);
    for (i = 0; i < PV_PICK_CANVAS_W * PV_PICK_CANVAS_ROWS; i++)
        map[(PV_PICK_ROW + i / PV_PICK_CANVAS_W) * 32 + i % PV_PICK_CANVAS_W] = (PV_PICK_PAL << 12) | (PV_PICK_TILE + i);
}

/* ---- God rows --------------------------------------------------------------------------------------- */

#define PV_DIVINE_ICON      9           /* gAttributeIconImages: 0 none, 1-6 Light..Wind, 7 Trap, 8 Magic, 9 Divine */
#define PV_GOD_LEVEL        10

void PackView_DrawGodStats(int row, u16 id)
{
    u32 line = (u16)(row * 4 + 2) << 5;
    const char *stat;
    int i;
    /* the stats Card Detail and Deck Edit print: Slifer's ATK is 1000 x the hand, Ra's the LP paid */
    switch (gCardIdToNumber[id & CARD_ID_MASK]) {
    case GOD_NUMBER_SLIFER_PV:
        stat = "X000";
        break;
    case GOD_NUMBER_RA_PV:
        stat = "????";
        break;
    default:
        stat = "4000";
        break;
    }
    LoadBgImage4bpp(line + 3, (row + 5) * 16, row * 4 + 0x300, gAttributeIconImages[PV_DIVINE_ICON]);
    LoadBgImage4bpp(line + 8, 0xF0, 0x340, (const u16 *)0x0863CA1C);     /* the ATK/DEF label of the rows */
    DrawBgString(line + 9, PV_COLORS, row * 8 + 0x1A0, (char *)stat);
    DrawBgString(line + 32 + 9, PV_COLORS, row * 8 + 0x1C8, (char *)stat);
    for (i = 0; i < PV_GOD_LEVEL; i++)
        SetBgMapEntry(0, i + 0xE + line, 2);
}

/* ---- Card Detail: where to find the card ------------------------------------------------------------- */

/* The description box of CardDetail_DrawInfo: 18 x 24 tiles from tile 0x248 at (13, 4) of BG3's map. */
#define PV_DESC_SIZE        ((24 << 8) | 18)
#define PV_DESC_MAP_X       13
#define PV_DESC_MAP_Y       4
#define PV_DESC_ROWS        24
#define PV_DESC_TILE        0x248
#define PV_DESC_COLORS      ((9 << 8) | 7)
#define PV_DESC_POS         ((2 << 16) | 4)
#define PV_DESC_FONT        10
#define PV_DESCRIPTION(id)  ((const u8 *)0x082461A0 + (id) * CARD_DESCRIPTION_SIZE)   /* gCardDescriptions */
#define PV_FOUND_COLOR      6           /* yellow */
#define PV_FOUND_FONT       8
#define PV_FOUND_GAP        4           /* pixels between the description and the packs */
#define PV_FOUND_MAX        3           /* packs named, best chance first; the rest are counted */

/* A Card Detail inside a duel: the duel step of the Campaign or of a Link Battle (both run DuelMainStep). */
static int InDuel(void)
{
    return (gMain.callback == CB_Campaign && gMain.seqIndexCampaign == 4)
        || ((void *)gMain.callback == (void *)CB_LinkBattle && gMain.seqState0 == 3);
}

/* "Found in: Vol.3 1.7%, Rare Selections 0.8% (locked), +2 more", or that no pack you pick holds it. */
static void BuildFoundIn(u16 cardId, char *s)
{
    u16 number = gCardIdToNumber[cardId & CARD_ID_MASK];
    u8 best[PV_FOUND_MAX];
    u16 bestOdds[PV_FOUND_MAX];
    char odds[6];
    int found = 0;
    int pack;
    int i;
    int k;

    for (pack = 0; pack < PACKVIEW_PACK_COUNT; pack++) {
        const struct PackViewCard *card = &sPackViewCards[sPackViewPacks[pack].first];
        for (i = 0; i < sPackViewPacks[pack].count; i++, card++) {
            if (card->number != number)
                continue;
            /* keep the PV_FOUND_MAX best normal-roll chances, in order */
            for (k = found < PV_FOUND_MAX ? found : PV_FOUND_MAX; k > 0 && bestOdds[k - 1] < card->odds[0]; k--) {
                if (k < PV_FOUND_MAX) {
                    best[k] = best[k - 1];
                    bestOdds[k] = bestOdds[k - 1];
                }
            }
            if (k < PV_FOUND_MAX) {
                best[k] = pack;
                bestOdds[k] = card->odds[0];
            }
            found++;
            break;
        }
    }
    if (found == 0) {
        AppendString(s, "Not in the packs you pick after a duel.");
        return;
    }
    s = AppendString(s, "Found in: ");
    for (k = 0; k < found && k < PV_FOUND_MAX; k++) {
        if (k > 0)
            s = AppendString(s, ", ");
        s = AppendString(s, sPackViewPacks[best[k]].name);
        s = AppendString(s, " ");
        FormatOdds(odds, bestOdds[k]);
        for (i = 0; odds[i] == ' '; i++)
            ;
        s = AppendString(s, odds + i);
        if (!IsPackUnlocked(sPackViewPacks[best[k]].id))
            s = AppendString(s, " (locked)");
    }
    if (found > PV_FOUND_MAX) {
        s = AppendString(s, ", +");
        s = AppendNumber(s, found - PV_FOUND_MAX);
        AppendString(s, " more");
    }
}

static void DrawDescriptionBox(const u8 *str)
{
    CardDetail_DrawTextBox(4, (PV_DESC_MAP_Y << 8) | PV_DESC_MAP_X, PV_DESC_SIZE, PV_DESC_TILE, PV_DESC_COLORS,
                           PV_DESC_FONT, PV_DESC_POS, str, 1, 0);
}

void PackView_DrawDescription(u16 cardId)
{
    const u8 *description = PV_DESCRIPTION(cardId);
    char found[128];
    char both[CARD_DESCRIPTION_SIZE + 128];
    char *s;
    int row;
    int col;
    u16 tile;

    if (InDuel()) {
        DrawDescriptionBox(description);
        return;
    }
    found[0] = 0;
    BuildFoundIn(cardId, found);
    /* the description as the game fits it, then the packs as a paragraph in the canvas space left below it */
    CardDetail_RenderText(PV_DESC_SIZE, PV_DESC_POS, description, PV_DESC_COLORS, PV_DESC_FONT, 1);
    if (gTextCanvas.bottom + PV_FOUND_GAP + PV_FOUND_FONT <= PV_DESC_ROWS * 8) {
        TextDrawString(4, gTextCanvas.bottom + PV_FOUND_GAP, PV_FOUND_COLOR | TEXT_SIZE(PV_FOUND_FONT),
                       (const u8 *)found);
        if (gTextCanvas.bottom <= PV_DESC_ROWS * 8) {
            gCardDetail.textHeight = (gTextCanvas.bottom - PV_FOUND_FONT) & ~1;    /* the last line's top */
            TextCanvasToTiles((u16 *)ROW_TILES(PV_DESC_TILE), 0);
            tile = PV_DESC_TILE;
            for (row = 0; row < PV_DESC_ROWS; row++)
                for (col = 0; col < 18; col++)
                    gMain.bgMapBuffer[4][(row + PV_DESC_MAP_Y) * 32 + PV_DESC_MAP_X + col] = tile++;
            return;
        }
    }
    /* no room: one text, which CardDetail_RenderText shrinks to fit; if even that doesn't fit, the description */
    s = AppendString(both, (const char *)description);
    s = AppendString(s, "  ");
    AppendString(s, found);
    DrawDescriptionBox((const u8 *)both);
    if (gTextCanvas.bottom >= 0xC0)
        DrawDescriptionBox(description);
}
