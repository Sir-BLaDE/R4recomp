/*
 * R4 - Ridge Racer Type 4 (SLPS-01798 / SCPS-45356 code base)
 * GameShark "60FPS + Widescreen Patch V2" as trusted psxrecomp mod plugins.
 *
 * The original .cht (mods/source/) is applied by emulators every frame
 * ("Activation = EndFrame"). This file reproduces that contract faithfully:
 *
 *   - at the top of the PS-X EXE entry point (0x8007D4B4, listed in
 *     [recompiler] mod_function_entry_funcs) every enabled code list is
 *     applied once, so the code caves in kernel RAM (0x8000C000-0x8000FFFF)
 *     and the hooks in the executable exist before any game function runs;
 *   - on every guest VBlank the lists are applied again, exactly like the
 *     emulator's end-of-frame cheat pass (tables the patch re-seeds each
 *     frame are re-seeded here too).
 *
 * Code semantics (GameShark): 80aaaaaa vvvv writes a 16-bit value;
 * D0aaaaaa vvvv executes the next line only if the 16-bit value at aaaaaa
 * equals vvvv. The patch guards everything except the 60 FPS list with
 * D001EB86 AE40 (an instruction word of the SCPS-45356/SLPS-01798 main
 * executable). The 60 FPS list has no guard in the .cht; the same guard is
 * applied to it here so nothing is written before the game executable is in
 * RAM (an emulator rewrites it on the next frame; a recompiled BIOS must not
 * be disturbed).
 *
 * Writes go through psx_mod_write_code_word, so changed executable pages are
 * routed to the dirty-RAM interpreter / overlay-shard path instead of the
 * stale statically compiled instructions. Unchanged words are not rewritten.
 *
 * Per-feature host settings the patch's readme asks for:
 *   60 FPS     -> "CPU 300%": [timing] guest_cycle_scale = 3 (gated), the gate
 *                 is opened while this feature is active.
 *   16:9       -> 16:9 output with the emulator widescreen hack OFF: a fixed
 *                 16:9 display aspect, and the framework's own GTE/GPU
 *                 widescreen squash held at identity (plain stretched present).
 */
#include <stdint.h>
#include <stddef.h>

#include <stdlib.h>

#include "mod_plugins.h"
#include "func_override.h"
#include "psx_cycle_freeze.h"
#include "r4_gameshark_codes.h"

/* Framework presentation switch (runtime/src/gpu.c). With it set, the
 * framework's widescreen projection mode is 0: no GTE X-squash, no GPU
 * primitive squash, no widened culling; the presenter still stretches the
 * 4:3 frame into the configured 16:9 aspect. main.cpp resets it before every
 * session's plugin activation. */
extern void gpu_ws_set_local_view_only(int on);

#define R4GS_GUARD_ADDR  0x8001EB86u
#define R4GS_GUARD_VALUE 0xAE40u
#define R4GS_EXE_ENTRY   0x8007D4B4u

#define R4GS_ID_60FPS  "r4.gameshark.60fps"
#define R4GS_ID_WIDE   "r4.gameshark.widescreen"
#define R4GS_ID_MARKER "r4.gameshark.cpu-marker"
#define R4GS_ID_FMV    "r4.gameshark.fmv"

typedef struct {
    const R4GsCode* codes;
    size_t count;
    int implicit_guard;      /* list has no D0 of its own (60 FPS) */
    const char* counter;     /* "<plugin>.words" */
} R4GsList;

static const R4GsList k_60fps  = { r4gs_s_60_fps_patch,
    sizeof r4gs_s_60_fps_patch / sizeof r4gs_s_60_fps_patch[0], 1,
    "r4.gameshark.60fps.words" };
static const R4GsList k_wide   = { r4gs_s_16_9_widescreen_patch,
    sizeof r4gs_s_16_9_widescreen_patch / sizeof r4gs_s_16_9_widescreen_patch[0], 0,
    "r4.gameshark.widescreen.words" };
static const R4GsList k_marker = { r4gs_cpu_marker,
    sizeof r4gs_cpu_marker / sizeof r4gs_cpu_marker[0], 0,
    "r4.gameshark.cpu-marker.words" };
static const R4GsList k_fmv    = { r4gs_s_16_9_fmv,
    sizeof r4gs_s_16_9_fmv / sizeof r4gs_s_16_9_fmv[0], 0,
    "r4.gameshark.fmv.words" };

/* 16-bit GameShark write, merged into its aligned word. */
static uint32_t r4gs_write16(uint32_t addr, uint16_t value) {
    const uint32_t word_addr = addr & ~3u;
    const uint32_t old = psx_mod_read_word(word_addr);
    const uint32_t shift = (addr & 2u) * 8u;
    const uint32_t neu = (old & ~(0xFFFFu << shift)) | ((uint32_t)value << shift);
    if (neu == old) return 0;
    psx_mod_write_code_word(word_addr, neu);
    return 1;
}

static void r4gs_apply(const R4GsList* list) {
    if (list->implicit_guard &&
        psx_mod_read_half(R4GS_GUARD_ADDR) != R4GS_GUARD_VALUE)
        return;
    uint32_t written = 0;
    for (size_t i = 0; i < list->count; ++i) {
        const R4GsCode* c = &list->codes[i];
        if (c->type == 0xD0) {
            if (psx_mod_read_half(c->addr) != c->value) ++i;  /* skip next */
            continue;
        }
        written += r4gs_write16(c->addr, c->value);           /* 0x80 */
    }
    if (written) psx_mod_counter_add(list->counter, written);
}

/* Entry hook: the BIOS has loaded the executable, no game code has run. */
static void r4gs_entry_60fps(struct CPUState* cpu, uint32_t a)  { (void)cpu; (void)a; r4gs_apply(&k_60fps); }
static void r4gs_entry_wide(struct CPUState* cpu, uint32_t a)   { (void)cpu; (void)a; r4gs_apply(&k_wide); }
static void r4gs_entry_marker(struct CPUState* cpu, uint32_t a) { (void)cpu; (void)a; r4gs_apply(&k_marker); }
static void r4gs_entry_fmv(struct CPUState* cpu, uint32_t a)    { (void)cpu; (void)a; r4gs_apply(&k_fmv); }

/* End-of-frame cheat pass. */
static void r4gs_vblank_60fps(void)  { if (psx_mod_game_started()) r4gs_apply(&k_60fps); }
static void r4gs_vblank_wide(void)   { if (psx_mod_game_started()) r4gs_apply(&k_wide); }
static void r4gs_vblank_marker(void) { if (psx_mod_game_started()) r4gs_apply(&k_marker); }
static void r4gs_vblank_fmv(void)    { if (psx_mod_game_started()) r4gs_apply(&k_fmv); }

/* A save state restores RAM: put the lists back before the PC resumes. */
static void r4gs_restore_60fps(void)  { r4gs_apply(&k_60fps); }
static void r4gs_restore_wide(void)   { r4gs_apply(&k_wide); }
static void r4gs_restore_marker(void) { r4gs_apply(&k_marker); }
static void r4gs_restore_fmv(void)    { r4gs_apply(&k_fmv); }

static void r4gs_activate_60fps(void) {
    /* "Set CPU speed to 300%": opens the [timing] guest_cycle_scale gate. */
    psx_mod_set_guest_cycle_scale_gate(1);
}

/* The 16:9 list installs a routine at 0x8000E898 that the hooked DrawOTag
 * path calls for every ordering table: it walks every packet and rewrites
 * its X coordinates for the wider view. In a race it executes ~190,000
 * guest cycles per frame (a third of a 60 FPS frame at the patch's 300%
 * CPU), and with PGXP precise culling more packets survive and the game no
 * longer fits its frame. The routine is GameShark code, not game code: it is
 * run here to completion with all its RAM effects, but in zero guest time
 * (an uncharged span), as if the cheat device did the work. A routine that
 * would run past one VBlank of guest time is charged in full from then on.
 * R4_WS_CHARGED=1 keeps it on the guest clock (A/B). */
#define R4GS_WS_OTWALK   0x8000E898u
static const uint32_t k_ws_otwalk_words[2] = { 0x27BDFFC0u, 0xAFBF003Cu };

static int r4gs_ws_otwalk(struct CPUState* cpu) {
    static int charged = -1;
    if (charged < 0) { const char* e = getenv("R4_WS_CHARGED"); charged = e && e[0] == '1'; }
    PsxCycleFreeze save;
    if (charged || !psx_cycle_uncharged_begin(&save, 564480u)) return 0;
    func_override_call_original(cpu);
    psx_cycle_uncharged_end(&save);
    psx_mod_counter_add("r4.gameshark.widescreen.otwalk_uncharged", 1);
    return 1;
}

static void r4gs_activate_wide(void) {
    /* "Set aspect ratio to 16:9" + "Disable Widescreen Hack". */
    psx_mod_set_fixed_display_aspect(16, 9);
    gpu_ws_set_local_view_only(1);
}

static void r4gs_register(const char* id, PSXModFunctionEntryCallback entry,
                          PSXModVBlankCallback vblank,
                          PSXModActivationCallback restore,
                          PSXModActivationCallback activate) {
    psx_mod_register_function_entry_plugin(id, R4GS_EXE_ENTRY, entry);
    psx_mod_register_vblank_plugin(id, vblank);
    psx_mod_register_savestate_plugin(id, restore);
    if (activate) psx_mod_register_activation_plugin(id, activate);
}

PSX_MOD_CONSTRUCTOR(r4gs_register_plugins) {
    r4gs_register(R4GS_ID_60FPS, r4gs_entry_60fps, r4gs_vblank_60fps,
                  r4gs_restore_60fps, r4gs_activate_60fps);
    r4gs_register(R4GS_ID_WIDE, r4gs_entry_wide, r4gs_vblank_wide,
                  r4gs_restore_wide, r4gs_activate_wide);
    psx_mod_register_function_override(R4GS_ID_WIDE ":otwalk", R4GS_WS_OTWALK,
                                       r4gs_ws_otwalk, k_ws_otwalk_words, 2, 0);
    r4gs_register(R4GS_ID_MARKER, r4gs_entry_marker, r4gs_vblank_marker,
                  r4gs_restore_marker, NULL);
    r4gs_register(R4GS_ID_FMV, r4gs_entry_fmv, r4gs_vblank_fmv,
                  r4gs_restore_fmv, NULL);
}
