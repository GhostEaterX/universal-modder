-- Oracle setup for a save made before the Extra Deck rituals. From the main_menu state, adds cards to the saved
-- Deck and Fusion Deck, fixes the checksum, writes the save to SRAM and resets, so the game boots from that save:
--   DECK_ADD    card IDs appended to the saved Deck (gSaveData.deck, deckCopies)
--   FUSION_ADD  card IDs appended to the saved Fusion Deck (fusionDeck, fusionCopies)
-- After the reset it logs, whenever it changes:
--   save deck=ID,ID,... fusion=ID,... trunk=T checksum=ok|bad   (trunk: trunkSize; the lists in save order)
--   copies ID=deck/fusion/trunk ...                              (for each card of DECK_ADD)
local SAVE, SIZE = 0x02011C20, 0x2170
local DECK, DECK_SIZE = SAVE + 0x2008, SAVE + 0x20C8
local FUSION, FUSION_SIZE = SAVE + 0x209E, SAVE + 0x20CC
local TRUNK_SIZE, CHECKSUM = SAVE + 0x20C6, SAVE + 0x216E
local SRAM = 0x0E000000
local frame, last, added = 0, "", {}

local function env(name)
    local v
    pcall(function() v = os.getenv(name) end)
    if v == "" then v = nil end
    return v
end

local function entry(id) return SAVE + 8 + id * 4 end     -- gSaveData.trunk[id]: count bits 0-9, deck 10-11,
                                                           -- side 12-13, fusion 14-15
local function add(list, size, shift, spec)
    for id in (spec or ""):gmatch("%d+") do
        id = tonumber(id)
        local n = emu:read16(size)
        emu:write16(list + n * 2, id)
        emu:write16(size, n + 1)
        local e = emu:read16(entry(id))
        emu:write16(entry(id), e + (1 << shift))
        if list == DECK then added[#added + 1] = id end
    end
end

local function sum()
    local s = 0
    for off = 0, 0x216B, 2 do s = s + emu:read16(SAVE + off) end
    return s
end

local function ids(list, size)
    local t = {}
    for i = 0, emu:read16(size) - 1 do t[#t + 1] = tostring(emu:read16(list + i * 2)) end
    return table.concat(t, ",")
end

callbacks:add("frame", function()
    frame = frame + 1
    if frame == 1 then
        add(DECK, DECK_SIZE, 10, env("DECK_ADD"))
        add(FUSION, FUSION_SIZE, 14, env("FUSION_ADD"))
        emu:write16(CHECKSUM, (-sum()) & 0xFFFF)
        for i = 0, SIZE - 1 do emu:write8(SRAM + i, emu:read8(SAVE + i)) end
        emu:reset()
        return
    end
    if frame < 4 then return end
    local ok = ((sum() + emu:read16(CHECKSUM)) & 0xFFFF) == 0
    local s = string.format("save deck=%s fusion=%s trunk=%d checksum=%s", ids(DECK, DECK_SIZE),
        ids(FUSION, FUSION_SIZE), emu:read16(TRUNK_SIZE), ok and "ok" or "bad")
    local c = {}
    for _, id in ipairs(added) do
        local e = emu:read16(entry(id))
        c[#c + 1] = string.format("%d=%d/%d/%d", id, (e >> 10) & 3, (e >> 14) & 3, e & 0x3FF)
    end
    s = s .. "\n[lua] copies " .. table.concat(c, " ")
    if s ~= last then
        console:log(string.format("f%d %s", frame, s))
        last = s
    end
end)
