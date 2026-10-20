/* r4.pal.ntsc: functions of R4 PAL (SCES-01706) that Namco rewrote for 25 Hz, replaced by their
 * USA (SLUS-00797) 30 Hz equivalent. The rest of the NTSC-isation is done at recompile time
 * (pal/ntsc_patches.toml). Compiled only in the PAL build (R4_REGION=PAL). */
#include "cpu_state.h"
#include "mod_plugins.h"
#include "r4_pal_ntsc.h"

#include <stddef.h>
#include <stdio.h>
#include <string.h>

#define PLUGIN_ID "r4.pal.ntsc"
#define LANGUAGE_PLUGIN_ID "r4.pal.language"
#define PACKAGE_ID "r4.pal.ntsc"
#define LANGUAGE_FEATURE "message-language"
#define LANGUAGE_OPTION "language"

/* PAL 0x8002B574 (USA 0x8002B9D0): race frames -> lap timer milliseconds.
 * PAL: s = n / 25; ms = s * 1000 + (n % 25) * 40 + a1.
 * USA: s = n / 30; ms = s * 1000 + ((n % 30) * 100) / 3 + a1 (truncating signed divisions). */
#define R4_PAL_FRAMES_TO_MS 0x8002B574u

static int r4_pal_frames_to_ms(CPUState *cpu, uint32_t address)
{
    (void)address;
    const int32_t n = (int32_t)cpu->gpr[4];
    const int32_t extra = (int32_t)cpu->gpr[5];
    const int32_t s = n / 30;
    const int32_t rest = n - s * 30;
    cpu->gpr[2] = (uint32_t)(s * 1000 + (rest * 100) / 3 + extra);
    return 1;
}

/* PAL 0x8001ECE8 (USA 0x8001ECE0): display initialisation. PAL allocates frame buffers of
 * (n+1) * 256 lines (USA (n+1) * 240, with no room for the longer USA sequence): s2 / s4 are
 * brought back to 240 right before their first read. The vertical offset read from the settings
 * table (16 by default in PAL) is re-centred for the NTSC screen (0 by default). */
#define R4_PAL_DISP_S2_SITE 0x8001ED20u   /* srl a1,s2,1 */
#define R4_PAL_DISP_S2_WORD 0x00122842u
#define R4_PAL_DISP_S4_SITE 0x8001ED34u   /* sw ra,76(sp) (s4 has just been computed) */
#define R4_PAL_DISP_S4_WORD 0xAFBF004Cu
#define R4_PAL_DISP_Y_SITE  0x8001EE5Cu   /* sh v1,102(s0): DISPENV.screen.y */
#define R4_PAL_DISP_Y_WORD  0xA6030066u
#define R4_PAL_SCREEN_Y_PAL 16

/* PAL 0x8001FC28 (USA 0x8001FC20): draw area (DR_AREA) of a race primitive, moved to the buffer
 * being drawn. USA: y + n * 240 (sll 4; subu; sll 4); PAL: y + n * 256 (sll 8). Left at 256,
 * the second buffer's area starts 16 lines too low and the first buffer overflows into those
 * 16 lines: a band flickers at the top of the screen every other frame. */
#define R4_PAL_DRAW_AREA_SITE 0x8001FC7Cu  /* addu v0,a3,v0 (v0 = n * 256) */
#define R4_PAL_DRAW_AREA_WORD 0x00E21021u

static uint32_t ntsc_height(uint32_t h) { return h - (h >> 4); }  /* 256 -> 240, 512 -> 480 */

static void r4_pal_disp_s2(CPUState *cpu, uint32_t address)
{
    (void)address;
    cpu->gpr[18] = ntsc_height(cpu->gpr[18]);
}

static void r4_pal_disp_s4(CPUState *cpu, uint32_t address)
{
    (void)address;
    cpu->gpr[20] = ntsc_height(cpu->gpr[20]);
}

static void r4_pal_draw_area(CPUState *cpu, uint32_t address)
{
    (void)address;
    cpu->gpr[2] = ntsc_height(cpu->gpr[2]);
}

static void r4_pal_disp_y(CPUState *cpu, uint32_t address)
{
    (void)address;
    cpu->gpr[3] = (uint32_t)(int32_t)((int16_t)cpu->gpr[3] - R4_PAL_SCREEN_Y_PAL);
}

/* Message language (0 English, 1 French, 2 German, 3 Spanish, 4 Italian). The byte at
 * 0x800AD564 is in BSS (0 = English at boot); a setting loaded from the memory card overwrites
 * it later as usual. The "Message language" option picks the value written at R4_Main while the
 * byte is still 0. */
#define R4_PAL_MAIN          0x8001E684u   /* R4_Main (USA 0x8001E67C) */
#define R4_PAL_LANGUAGE      0x800AD564u

static const char *const k_languages[] = { "english", "french", "german", "spanish", "italian" };
static uint8_t s_language;   /* option value, 0 when the feature is off */

/* Race viewports (read by FUN_8006EF8C): PAL data tables computed for 256-line buffers. Main
 * view (0, 0, 320, 256) / (0, 256, 320, 256) with the buffers NTSC-ised at 0 / 240: the first
 * buffer overflows into the first 16 lines of the second (a band flickers at the top of the
 * screen) and the view, centred at y = 128, loses its last 16 lines. Brought back to 240 lines
 * per buffer (rear-view mirror unchanged except for its buffer), before the first race. */
static const struct { uint32_t address; int16_t v[28]; uint32_t n; } k_ntsc_viewports[] = {
    /* RECT per view (main, mirror, top/bottom split screen, left/right, interlaced) and per buffer */
    { 0x800A3C20u, {   0,   0, 320, 240,   98,  18, 124,  28,    0,   0, 320, 120,    0, 120, 320, 120,
                       0,   0, 160, 240,  160,   0, 160, 240,    0,   0, 320, 480 }, 28 },
    { 0x800A3C58u, {   0, 240, 320, 240,   98, 258, 124,  28,    0, 240, 320, 120,    0, 360, 320, 120,
                       0, 240, 160, 240,  160, 240, 160, 240,    0,   0, 320, 480 }, 28 },
    { 0x800A3BB4u, { 120,  32,  60, 180,  120, 120, 240,   0 }, 8 },   /* vertical centre (SetGeomOffset) */
    { 0x800A3BF0u, {   0,   0,   0, 120,    0,   0,   0,   0 }, 8 },   /* viewport top */
    { 0x800A3C10u, { 240,  28, 120, 240,  240, 240, 480,   0 }, 8 },   /* viewport bottom */
};

/* HUD (sprite templates x, y, w, h, u, v, clut: 20 bytes, y at +2), PAL data placed for 256
 * lines. One player: tachometer, digits and "km/h" anchored at the bottom of the screen (-16,
 * like the speed digits already restored to the USA values by ntsc_patches). Split screen:
 * bottom view at +128 instead of +120 (the tachometer, speed digits and laps already are):
 * "km/h"/"rpm" fell on the digits and "rpm" left the screen. */
static const struct { uint32_t address; int16_t y; } k_ntsc_hud[] = {
    { 0x8009EA92u, 218 }, { 0x8009EAA6u, 166 }, { 0x8009EABAu, 156 },   /* 1P: km/h, digits, tachometer */
    { 0x8009EAF6u, 212 }, { 0x8009EB0Au, 228 },                         /* 2P bottom: km/h, rpm */
    { 0x8009ECC2u, 134 }, { 0x8009ECD6u, 134 }, { 0x8009ECEAu, 146 },   /* 2P bottom: RANK, position */
    { 0x8009ECFEu, 146 }, { 0x8009ED12u, 152 }, { 0x8009ED26u, 144 },   /*            TIME LIMIT */
};

/* PAL 0x80021C94 (USA 0x80021C38): split-screen lap counter y. PAL (n - 1) * 128 + 12 (sll 7),
 * USA (n - 1) * 120 + 12 (sll 4; subu; sll 3). Fixed before the next instruction. */
#define R4_PAL_LAPS_SITE 0x80021CE8u   /* addiu s4,v1,2928 (s5 has just been computed) */
#define R4_PAL_LAPS_WORD 0x24740B70u

/* PAL 0x800225DC (USA 0x8002258C): race message y. 2P: PAL (n - 1) * 128 + 56,
 * USA (n - 1) * 120 + 52; 1P: PAL 120, USA 112. */
#define R4_PAL_MSG2P_SITE 0x80022614u   /* addiu v0,zero,1 (a3 has just been computed) */
#define R4_PAL_MSG2P_WORD 0x24020001u
#define R4_PAL_MSG1P_SITE 0x80022644u   /* addiu s0,v0,112 (after addiu a3,zero,120) */
#define R4_PAL_MSG1P_WORD 0x24500070u

static void r4_pal_laps(CPUState *cpu, uint32_t address)
{
    (void)address;
    cpu->gpr[21] = (uint32_t)(((int32_t)cpu->gpr[4] - 1) * 120 + 12);
}

static void r4_pal_msg2p(CPUState *cpu, uint32_t address)
{
    (void)address;
    cpu->gpr[7] = (uint32_t)(((int32_t)cpu->gpr[4] - 1) * 120 + 52);
}

static void r4_pal_msg1p(CPUState *cpu, uint32_t address)
{
    (void)address;
    cpu->gpr[7] = 112;
}

static void r4_pal_main_entry(CPUState *cpu, uint32_t address)
{
    (void)cpu; (void)address;
    if (s_language != 0 && psx_mod_read_byte(R4_PAL_LANGUAGE) == 0)
        psx_mod_write_byte(R4_PAL_LANGUAGE, s_language);
    for (size_t t = 0; t < sizeof k_ntsc_viewports / sizeof k_ntsc_viewports[0]; ++t)
        for (uint32_t i = 0; i + 1 < k_ntsc_viewports[t].n; i += 2)
            psx_mod_write_word(k_ntsc_viewports[t].address + 2 * i,
                               (uint16_t)k_ntsc_viewports[t].v[i] | (uint32_t)(uint16_t)k_ntsc_viewports[t].v[i + 1] << 16);
    for (size_t t = 0; t < sizeof k_ntsc_hud / sizeof k_ntsc_hud[0]; ++t)
        psx_mod_write_half(k_ntsc_hud[t].address, (uint16_t)k_ntsc_hud[t].y);
}

int r4_pal_message_language(void)
{
    return (int)psx_mod_read_byte(R4_PAL_LANGUAGE);
}

static int s_registered;

static void r4_pal_ntsc_activate(void)
{
    if (s_registered != 9)
        fprintf(stderr, "[r4.pal.ntsc] only %d of 9 hooks registered\n", s_registered);
}

/* "Message language" feature: before each plan, back to the game's own default (English); when
 * the feature is in the plan, its activation reads the chosen language. */
static void r4_pal_language_reset(void)
{
    s_language = 0;
}

static void r4_pal_language_activate(void)
{
    char value[16];
    s_language = 0;
    if (!psx_mod_option_value(PACKAGE_ID, LANGUAGE_FEATURE, LANGUAGE_OPTION, value, sizeof value))
        return;
    for (size_t i = 0; i < sizeof k_languages / sizeof k_languages[0]; ++i)
        if (strcmp(value, k_languages[i]) == 0)
            s_language = (uint8_t)i;
}

PSX_MOD_CONSTRUCTOR(r4_register_pal_ntsc)
{
    s_registered += psx_mod_register_function_filter_plugin(
        PLUGIN_ID, R4_PAL_FRAMES_TO_MS, r4_pal_frames_to_ms);
    s_registered += psx_mod_register_instruction_plugin(
        PLUGIN_ID, R4_PAL_DISP_S2_SITE, R4_PAL_DISP_S2_WORD, r4_pal_disp_s2);
    s_registered += psx_mod_register_instruction_plugin(
        PLUGIN_ID, R4_PAL_DISP_S4_SITE, R4_PAL_DISP_S4_WORD, r4_pal_disp_s4);
    s_registered += psx_mod_register_instruction_plugin(
        PLUGIN_ID, R4_PAL_DISP_Y_SITE, R4_PAL_DISP_Y_WORD, r4_pal_disp_y);
    s_registered += psx_mod_register_instruction_plugin(
        PLUGIN_ID, R4_PAL_DRAW_AREA_SITE, R4_PAL_DRAW_AREA_WORD, r4_pal_draw_area);
    s_registered += psx_mod_register_function_entry_plugin(
        PLUGIN_ID, R4_PAL_MAIN, r4_pal_main_entry);
    s_registered += psx_mod_register_instruction_plugin(
        PLUGIN_ID, R4_PAL_LAPS_SITE, R4_PAL_LAPS_WORD, r4_pal_laps);
    s_registered += psx_mod_register_instruction_plugin(
        PLUGIN_ID, R4_PAL_MSG2P_SITE, R4_PAL_MSG2P_WORD, r4_pal_msg2p);
    s_registered += psx_mod_register_instruction_plugin(
        PLUGIN_ID, R4_PAL_MSG1P_SITE, R4_PAL_MSG1P_WORD, r4_pal_msg1p);
    (void)psx_mod_register_activation_plugin(PLUGIN_ID, r4_pal_ntsc_activate);
    (void)psx_mod_register_session_reset_plugin(LANGUAGE_PLUGIN_ID, r4_pal_language_reset);
    (void)psx_mod_register_activation_plugin(LANGUAGE_PLUGIN_ID, r4_pal_language_activate);
}
