/* Presentation-only US R4 draw replay. Guest pacing remains stock.
 * Rate options: 60 (default), 90, 100, 120 and 144 schedule extra race draws;
 * "30" leaves the original frames alone (no passes, stock presenter).
 * Method: "fields" (default) blends the car and camera values and re-runs the
 * draw-only call lists (r4_interp.c); "projection" re-runs the handler span
 * with the recorded GTE projections interpolated (r4_projection_replay.cpp). */
#include <string.h>

#include "mod_plugins.h"
#include "r4_interp.h"

#define R4_FR_PACKAGE "r4.enhancement.frame-rate"

static int hooks_ready, projection_hooks_ready, active, projection;
static int rate_is_original(void) {
    char value[16];
    return psx_mod_option_value(R4_FR_PACKAGE, "frame-rate", "rate", value,
                                sizeof value) && strcmp(value, "30") == 0;
}
static int method_is_projection(void) {
    char value[16];
    return psx_mod_option_value(R4_FR_PACKAGE, "frame-rate", "method", value,
                                sizeof value) && strcmp(value, "projection") == 0;
}
static void apply(int enabled) {
    r4_interp_activate(enabled && !projection);
    r4_projection_activate(enabled && projection);
}
static void activate(void) {
    projection = method_is_projection();
    int ready = (projection ? projection_hooks_ready : hooks_ready) &&
        !rate_is_original() &&
        psx_mod_activate_render_pass_rate(R4_FR_PACKAGE, "frame-rate", "rate",
                                          PSX_MOD_RENDER_PASS_FLIP_PENDING);
    active = ready;
    /* Only the field recipe has a verified multiplayer draw boundary. */
    psx_mod_set_render_pass_netplay(ready && !projection);
    apply(ready);
}

static void reset_history(void) { apply(0); }
static void restored(void) { apply(active); }

PSX_MOD_CONSTRUCTOR(r4_frame_rate_register) {
    hooks_ready = r4_interp_register_hooks() == 2;
    projection_hooks_ready = r4_projection_register_hooks() == 2;
    psx_mod_register_activation_plugin("r4.framerate", activate);
    psx_mod_register_session_reset_plugin("r4.framerate", reset_history);
    psx_mod_register_savestate_plugin("r4.framerate", restored);
}
