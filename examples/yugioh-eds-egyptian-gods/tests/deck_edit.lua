-- Oracle setup for Deck Edit's filters and sorts. From the main_menu state, puts cards in the Trunk before Deck
-- Edit builds its lists, and logs the Trunk list as Deck Edit shows it (after its filter and sort) whenever it
-- changes:
--   TRUNK    card IDs, comma separated, one copy each
-- Log lines: "trunk n=N ids=a,b,c,..." with the first 12 card IDs of the shown list, and "detail id=ID found=N"
-- for a Card Detail (below).
local SAVE = 0x02011C20
local DECK_EDIT = 0x0201DB20                       -- gDeckEdit
local SHOWN = DECK_EDIT + 0x644 + 0x728            -- lists[1].trunk: the filtered and sorted Trunk list
local SHOWN_COUNT = DECK_EDIT + 0x1494 + 3 * 2     -- listCount[1][DECKEDIT_LIST_TRUNK]
local frame, last = 0, ""

local function env(name)
    local v
    pcall(function() v = os.getenv(name) end)
    if v == "" then v = nil end
    return v
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
    if frame == 1 then
        local n = 0
        for id in (env("TRUNK") or ""):gmatch("%d+") do
            local a = SAVE + 8 + tonumber(id) * 4
            emu:write16(a, (emu:read16(a) & ~0x3FF) | 1)
            n = n + 1
        end
        emu:write16(SAVE + 0x20C6, emu:read16(SAVE + 0x20C6) + n)   -- trunkSize
    end
    local count = emu:read16(SHOWN_COUNT)
    local ids = {}
    for i = 0, math.min(count, 12) - 1 do ids[#ids + 1] = tostring(emu:read16(SHOWN + i * 2)) end
    local s = string.format("trunk n=%d ids=%s", count, table.concat(ids, ","))
    if s ~= last then
        console:log(string.format("f%d %s", frame, s))
        last = s
    end
    logDetail(function(line) console:log(string.format("f%d %s", frame, line)) end)
end)
