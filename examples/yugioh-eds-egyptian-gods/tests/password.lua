-- Oracle 4: does the password screen hand out the Gods?
-- Logs the trunk (card collection) count of each God whenever it changes. The trunk is a u32 per card ID
-- at 0x02011C28 + id*4 (gSaveData.trunk), owned count in bits 0-9. Drive the password screen with --keys.
local TRUNK = 0x02011C28
local GODS = { { 817, "Obelisk" }, { 818, "Slifer" }, { 819, "Ra" } }
local frame, last = 0, ""

callbacks:add("frame", function()
    frame = frame + 1
    local t = {}
    for _, g in ipairs(GODS) do
        t[#t + 1] = string.format("%s %d", g[2], emu:read32(TRUNK + g[1] * 4) & 0x3FF)
    end
    local s = table.concat(t, ", ")
    if s ~= last then
        console:log(string.format("f%d trunk: %s", frame, s))
        last = s
    end
end)
