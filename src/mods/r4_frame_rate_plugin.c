/* Presentation-only US R4 draw replay. Guest pacing remains stock.
 * Rate options: "auto" (default) is 60, or the original 30 at an 8K / 18x
 * internal scale where the GPU cannot hold 60 (owner, 2026-10-27: 18x with
 * extra frames collapsed to ~21 FPS; 13x holds 59). 60, 90, 100, 120 and 144
 * schedule extra race draws; "display" follows the display refresh; "30"
 * leaves the original frames alone (no passes, stock presenter). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "mod_plugins.h"
#include "r4_interp.h"

#define R4_FR_PACKAGE "r4.enhancement.frame-rate"
/* Internal scale from which Auto shows the original frames only. */
#define R4_FR_AUTO_ORIGINAL_SCALE 18u

static int hooks_ready, active;
/* The presentation rate the option resolves to: 0 follows the display
 * refresh, 30 means the original frames only. */
static uint32_t resolved_fps(void) {
    char value[16];
    if (!psx_mod_option_value(R4_FR_PACKAGE, "frame-rate", "rate", value,
                              sizeof value))
        return 60;
    if (strcmp(value, "auto") == 0) {
        const uint32_t scale = psx_mod_internal_scale();
        const uint32_t fps = scale >= R4_FR_AUTO_ORIGINAL_SCALE ? 30u : 60u;
        fprintf(stdout, "r4.framerate: auto -> %u FPS (internal scale %u)\n",
                (unsigned)fps, (unsigned)scale);
        return fps;
    }
    if (strcmp(value, "display") == 0) return 0;
    {
        char* end = value;
        const unsigned long parsed = strtoul(value, &end, 10);
        return (end != value && *end == '\0') ? (uint32_t)parsed : 60u;
    }
}
static void activate(void) {
    const uint32_t fps = resolved_fps();
    int ready = hooks_ready && fps != 30 &&
        psx_mod_activate_render_pass_fps(fps, PSX_MOD_RENDER_PASS_FLIP_PENDING);
    active = ready;
    psx_mod_set_render_pass_netplay(ready);
    r4_interp_activate(ready);
}

static void reset_history(void) { r4_interp_activate(0); }
static void restored(void) { r4_interp_activate(active); }

PSX_MOD_CONSTRUCTOR(r4_frame_rate_register) {
    hooks_ready = r4_interp_register_hooks() == 2;
    psx_mod_register_activation_plugin("r4.framerate", activate);
    psx_mod_register_session_reset_plugin("r4.framerate", reset_history);
    psx_mod_register_savestate_plugin("r4.framerate", restored);
}
