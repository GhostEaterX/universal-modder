-- Oracle setup for the opponents' result lines. From the duel_turn2 state, makes OPP the Campaign opponent and
-- the player's record against them WINS wins, then wins the duel at once (a Blue-Eyes White Dragon in the
-- player's zone 0, the CPU at 1 LP; the keys attack and tap A through the texts). Logs:
--   dialogue event=E end=N   the dialogue record E (gDialogueTable[gMain.dialogueIndex]) has been printed to
--                            its end, N bytes into its text: every page of it was shown
--   record wins=W            the player's record against OPP, whenever it changes
local MAIN = 0x03000040
local OPP_ADDR = MAIN + 0x4870                     -- bits 1-5: gMain.opponent
local DIALOGUE_INDEX = MAIN + 0x4886               -- gMain.dialogueIndex
local DIALOGUE, RECORD_SIZE = 0x0813ADF4, 0x304   -- gDialogueTable: {u16 event; u16 speaker; char text[0x300]}
local TEXT_POS = 0x020147A0                        -- gBustup.textBox.text: the printer's position
local P0 = 0x020192E4                              -- gDuelPlayers[0]
local OPP, WINS = 1, 9
pcall(function() OPP = tonumber(os.getenv("OPP")) or OPP end)
pcall(function() WINS = tonumber(os.getenv("WINS")) or WINS end)
local RECORD = 0x02011C20 + 0x20D0 + OPP * 4      -- gSaveData.duelRecords[OPP]: wins in bits 0-10
local frame, last = 0, {}

local function say(kind, s)
    if last[kind] ~= s then
        console:log(string.format("f%d %s", frame, s))
        last[kind] = s
    end
end

callbacks:add("frame", function()
    frame = frame + 1
    if frame == 1 then
        local z = P0 + 0x28                        -- Blue-Eyes face up in zone 0, the CPU at 1 LP
        emu:write32(z, (emu:read32(z) & ~0x1FFF) | 82)
        emu:write8(z + 6, emu:read8(z + 6) | 0x2)
        emu:write16(P0 + 0xD64, 1)
        emu:write8(OPP_ADDR, (emu:read8(OPP_ADDR) & 0xC1) | (OPP << 1))
        emu:write16(RECORD, (emu:read16(RECORD) & ~0x7FF) | WINS)
    end
    say("record", string.format("record wins=%d", emu:read16(RECORD) & 0x7FF))
    local rec = DIALOGUE + emu:read16(DIALOGUE_INDEX) * RECORD_SIZE
    local pos = emu:read32(TEXT_POS) - (rec + 4)
    if pos > 0 and pos < RECORD_SIZE - 4 and emu:read8(rec + 4 + pos) == 0 then
        say("dialogue", string.format("dialogue event=%d end=%d", emu:read16(rec), pos))
    end
end)
