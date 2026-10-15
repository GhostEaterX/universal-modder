-- Oracle setup for the pack viewer. From the duel_turn2 state, wins the duel at once (a Blue-Eyes White Dragon
-- in the player's zone 0, the CPU at 1 LP) so that the pick-a-pack screen comes up, applies the save setup
-- from environment variables, and logs what is on screen whenever it changes:
--   LAST_PACK / PITY   gSaveData.lastPackId / packPityCount: the "same pack again" and pity rules
--   OWN                card numbers, comma separated, to put in the trunk, one copy each (NEW becomes x1)
--   PICK_PACK          a pack id put in the pick screen's centre slot when the screen comes up (the test save
--                      unlocks only Vol.1-3)
--   PIN_RNG            an RNG state (hex) written when the pick starts its fade-out, so that two ROMs whose
--                      frames drift apart generate from the same state
-- Log lines:
--   pick centre=ID band=0|1      the pick screen's centre pack, band=1 once its name is in the bottom band
--   view pack=ID entries=N mode=M top=T row=R      the list (mode: 0 normal, 1 same pack, 2 pity)
--   header 'LINE 3' 'LINE 4'     the header row's two text lines, as drawn
--   cursor e=E n=NUM odds='TEXT' new=0|1 mark='M'  the card under the cursor once its row is drawn; mark is
--                                                NEW or the copies you own (x1, x2, ...)
--   detail n=NUM                 Card Detail opened from the list; then "detail id=ID found=N" (below)
--   cursor ... stats='ATK/DEF'   also the row's ATK and DEF text ('    /    ' for a Magic or Trap card)
--   generated pack=ID cards=a,b,c,d,e              the pack GeneratePackCards made (the pick)
-- The text is read back from the screen: the BG0 map buffer and the 4bpp glyph tiles in VRAM, matched against
-- the game's 8x8 bold font (DrawBgString).
local MAIN = 0x03000040
local MAP0 = MAIN + 0x41C                          -- gMain.bgMapBuffer[0]
local SEQ_INDEX, SEQ_STATE = MAIN + 0x4859, MAIN + 0x485A
local SAVE = 0x02011C20
local LAST_PACK, PITY = SAVE + 0x2154, SAVE + 0x2156
local SCENE = 0x02020310                           -- gSceneWork (PackListWork)
local PACK_INFO = 0x080865DC
local OPEN = 0x02015160                            -- gPackOpenWork
local VIEW = OPEN + 4                              -- struct PackViewWork (src/pack_viewer.c)
local DETAIL = 0x02013D90                          -- gCardDetail
local ID_TO_NUMBER, NUMBER_TO_ID = 0x08622AB4, 0x08623DF4
local FONT = 0x0822BB00                            -- gFontLatin8x8Bold
local P0 = 0x020192E4                              -- gDuelPlayers[0]
local frame, last, picked, pinned, placed = 0, {}, false, false, false

local function env(name)
    local v
    pcall(function() v = os.getenv(name) end)
    if v == "" then v = nil end
    return v
end

local glyphs = {}
for c = 32, 126 do
    local key = {}
    for y = 0, 7 do key[#key + 1] = string.format("%02x", emu:read8(FONT + c * 8 + y)) end
    key = table.concat(key)
    if not glyphs[key] then glyphs[key] = string.char(c) end   -- ' ' before '`', '0' before 'O'
end

local function cell(line, col)
    local entry = emu:read16(MAP0 + (line * 32 + col) * 2)
    if entry == 0 then return " " end
    local base = 0x06004000 + (entry & 0x3FF) * 32
    local key = {}
    for y = 0, 7 do
        local bits = 0
        for x = 0, 7 do
            local b = emu:read8(base + y * 4 + (x >> 1))
            local px = (x & 1) == 0 and (b & 0xF) or (b >> 4)
            if px ~= 0 then bits = bits | (0x80 >> x) end
        end
        key[#key + 1] = string.format("%02x", bits)
    end
    return glyphs[table.concat(key)] or "?"
end

local function text(line, col, n)
    local s = {}
    for i = 0, n - 1 do s[#s + 1] = cell(line, col + i) end
    return (table.concat(s):gsub("%s+$", ""))
end

local function say(kind, s)
    if last[kind] ~= s then
        console:log(string.format("f%d %s", frame, s))
        last[kind] = s
    end
end

local function setup()
    -- the duel: Blue-Eyes face up in zone 0, the CPU at 1 LP
    local z = P0 + 0x28
    emu:write32(z, (emu:read32(z) & ~0x1FFF) | 82)
    emu:write8(z + 6, emu:read8(z + 6) | 0x2)
    emu:write16(P0 + 0xD64, 1)
    if env("LAST_PACK") then emu:write16(LAST_PACK, tonumber(env("LAST_PACK"))) end
    if env("PITY") then emu:write16(PITY, tonumber(env("PITY"))) end
    for n in (env("OWN") or ""):gmatch("%d+") do
        local id = emu:read16(NUMBER_TO_ID + tonumber(n) * 2)
        local a = SAVE + 8 + id * 4
        emu:write16(a, (emu:read16(a) & ~0x3FF) | 1)
    end
end

-- the pack the list shows: the saved pick-screen list (packRows, packCount) at the saved centre
local function viewedPack()
    local n = emu:read16(VIEW + 0x40)
    local r = emu:read16(VIEW + ((emu:read16(VIEW + 0x42) + 1) % n) * 2)
    return emu:read16(PACK_INFO + r * 0x48)
end

-- Card Detail: once its description box is in the BG3 map buffer (gMain.bgMapBuffer[4], cell (13, 4) = tile
-- 0x248), "detail id=ID found=N": N is the yellow (colour 6) pixels left on the text canvas, which the "Found
-- in" paragraph draws and the description (colour 7, shadow 9) doesn't.
local DETAIL_ID, DESC_CELL, CANVAS = 0x02013D92, 0x0300245C + (4 * 32 + 13) * 2, 0x02000000
local shownDetail = -1
local function logDetail(say)
    local id = emu:read16(DETAIL_ID)
    if emu:read16(DESC_CELL) ~= 0x248 or id == 0 then
        shownDetail = -1
        return
    end
    if id == shownDetail then return end
    shownDetail = id
    local n = 0
    for i = 0, 18 * 24 * 64 - 1 do
        if emu:read8(CANVAS + i) == 6 then n = n + 1 end
    end
    say(string.format("detail id=%d found=%d", id, n))
end

callbacks:add("frame", function()
    frame = frame + 1
    if frame == 1 then setup() end
    local index, state = emu:read8(SEQ_INDEX), emu:read8(SEQ_STATE)
    local count = emu:read16(SCENE + 0x6C)
    -- the pick screen: GetPack_SelectAndGenerate sub-state 2 (PackList_HandleInput)
    if index == 0 and state == 2 and count > 0 and count <= 32 then
        local slot = SCENE + 0x2C + ((emu:read32(SCENE + 0x10) + emu:read32(SCENE + 0x0C)) % count) * 2
        if env("PICK_PACK") and not placed then
            for r = 0, 22 do
                if emu:read16(PACK_INFO + r * 0x48) == tonumber(env("PICK_PACK")) then emu:write16(slot, r) end
            end
            placed = true
        end
        local row = emu:read16(slot)
        local band = emu:read16(MAP0 + 17 * 64) == ((14 << 12) | 0x330) and 1 or 0
        say("pick", string.format("pick centre=%d band=%d", emu:read16(PACK_INFO + row * 0x48), band))
        picked = true
    end
    if index == 0 and state >= 0x20 then
        local top, rowIndex = emu:read16(VIEW + 0x48), emu:read8(OPEN + 0x114) & 7
        local busy = (emu:read8(VIEW + 0x57) ~= 0) or (emu:read8(VIEW + 0x58) ~= 0) or (emu:read8(OPEN + 0x114) >> 6) ~= 0
        if state == 0x23 then
            say("view", string.format("view pack=%d entries=%d mode=%d top=%d row=%d", viewedPack(),
                emu:read16(VIEW + 0x46), emu:read8(VIEW + 0x56), top, rowIndex))
            if top == 0 and not busy then
                say("header", string.format("header '%s' '%s'", text(2, 1, 29), text(3, 1, 29)))
            end
            if not busy and top + rowIndex > 0 then
                local id = emu:read16(VIEW + 0x4C + rowIndex * 2)
                local line = rowIndex * 4 + 3
                local mark = text(line, 20, 3)
                say("cursor", string.format("cursor e=%d n=%d odds='%s' new=%d mark='%s' stats='%s/%s'",
                    top + rowIndex, emu:read16(ID_TO_NUMBER + id * 2), text(line, 25, 5), mark == "NEW" and 1 or 0,
                    mark, text(line - 1, 9, 4), text(line, 9, 4)))
            end
        elseif state == 0x28 then   -- PV_DETAIL_INPUT
            say("detail", string.format("detail n=%d", emu:read16(ID_TO_NUMBER + emu:read16(DETAIL + 2) * 2)))
        end
    end
    if index == 0 and state == 3 and env("PIN_RNG") and not pinned then   -- PackList_FadeOut after A
        emu:write32(MAIN, tonumber(env("PIN_RNG"), 16))
        pinned = true
    end
    logDetail(function(line) say("cardDetail", line) end)
    -- after the pick: GETPACK_STEP_INIT_SCENE onwards, the generated pack
    if picked and index >= 1 and index <= 5 then
        local cards = {}
        for i = 0, 4 do cards[#cards + 1] = tostring(emu:read16(OPEN + 0x102 + i * 2)) end
        say("generated", string.format("generated pack=%d cards=%s", emu:read16(LAST_PACK), table.concat(cards, ",")))
    end
end)
