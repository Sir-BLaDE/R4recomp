/*
 * r4.spanish: runtime half of the Spanish text package (mods/preloaded/
 * packages/r4.spanish). The declarative half (disc overlays + guarded code
 * patches) enlarges the message window's per-glyph state array from 64 to
 * 200 entries, as the PAL build does: window #1 lives in a bump-allocated
 * arena whose allocation size the package patches, but window #2 is a static
 * 0x128-byte object at 0x80104848 with other data right behind it.
 *
 * This plugin gives window #2 a 0x348-byte home in enhancement memory and
 * points the game at it: at the PS-X EXE entry it replaces
 *     0x8003BFE0  addiu s0, s0, 0x4e20     (s0 = 0x800FFA28 -> 0x80104848)
 *     0x8003BFE4  move  a0, s0
 * with
 *     lui a0, hi(window)  /  ori a0, a0, lo(window)
 * (s0 is not read again before that function returns). The window is only
 * ever reached through the pointer the following code stores at
 * 0x800AC378, so nothing else needs to change.
 */
#include <stdint.h>
#include <stddef.h>

#include "mod_plugins.h"

#define R4ES_ID          "r4.spanish"
#define R4ES_EXE_ENTRY   0x8007D4B4u
#define R4ES_SITE        0x8003BFE0u
#define R4ES_STOCK0      0x26104E20u   /* addiu s0, s0, 0x4e20 */
#define R4ES_STOCK1      0x02002021u   /* move  a0, s0 (addu a0, s0, zero) */
#define R4ES_WINDOW_SIZE 0x348u

static uint32_t s_window;   /* guest address of the relocated window #2 */

static void r4es_install(void) {
    if (!s_window) return;
    const uint32_t lui = 0x3C040000u | (s_window >> 16);           /* lui a0 */
    const uint32_t ori = 0x34840000u | (s_window & 0xFFFFu);       /* ori a0, a0 */
    const uint32_t w0 = psx_mod_read_word(R4ES_SITE);
    const uint32_t w1 = psx_mod_read_word(R4ES_SITE + 4);
    if (w0 == lui && w1 == ori) return;                 /* already installed */
    if (w0 != R4ES_STOCK0 || w1 != R4ES_STOCK1) {       /* not our executable */
        psx_mod_counter_add("r4.spanish.guard_failed", 1);
        return;
    }
    psx_mod_write_code_word(R4ES_SITE, lui);
    psx_mod_write_code_word(R4ES_SITE + 4, ori);
    psx_mod_counter_add("r4.spanish.window_relocated", 1);
}

static void r4es_activate(void) {
    if (!s_window)
        s_window = psx_mod_alloc_guest_memory(R4ES_WINDOW_SIZE, 16);
    if (!s_window) psx_mod_counter_add("r4.spanish.alloc_failed", 1);
}

static void r4es_entry(struct CPUState* cpu, uint32_t address) {
    (void)cpu; (void)address;
    r4es_install();
}

static void r4es_restore(void) { r4es_install(); }

PSX_MOD_CONSTRUCTOR(r4es_register_plugin) {
    psx_mod_register_activation_plugin(R4ES_ID, r4es_activate);
    psx_mod_register_function_entry_plugin(R4ES_ID, R4ES_EXE_ENTRY, r4es_entry);
    psx_mod_register_savestate_plugin(R4ES_ID, r4es_restore);
}
