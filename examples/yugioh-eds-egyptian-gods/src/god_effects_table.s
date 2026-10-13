@ The effect table with the Egyptian Gods' rows (universal-modder). It replaces gCardEffects, which ends
@ where gTributeSummonPrompts starts and so can't grow in place. The first 426 rows are the original table,
@ built by eds-decomp from your own ROM's extracted assets; Obelisk (1910) and Ra (1912) follow, and the
@ table stays sorted for FindCardEffect's binary search. Row: u16 number, u16 flags (0), then resolve,
@ check, prepare, chainA, chainB.

	.section .rodata
	.align 2, 0
	.global gCardEffectsMod
gCardEffectsMod:
	.incbin "build/assets/tables__card_effect_handlers.bin", 0x0, 0x27F0
	.2byte 1910, 0
	.4byte GodObeliskResolve, 0, GodObeliskPrepare, 0, GodObeliskChainB
	.2byte 1912, 0
	.4byte GodRaResolve, 0, GodRaPrepare, 0, GodRaChainB
