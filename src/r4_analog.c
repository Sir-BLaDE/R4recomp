/*
 * r4.analog: analog steering for R4 through a controller it supports
 * natively. R4 reads a DualShock's sticks as a plain digital pad; its analog
 * steering exists for the Namco JogCon (shipped with this edition) and the
 * NeGcon.
 *
 * Default: the gamepad is presented as a JogCon (tested in a Grand Prix race:
 * menus, steering, throttle and brake):
 *   dial (steering) <- left stick X (small deadzone, full lock kept)
 *   R1 (accelerate) <- R1, right trigger, or Cross
 *   L1 (brake)      <- L1, left trigger, or Square
 *   every other button keeps its place (Circle confirms in the menus).
 * R4_ANALOG_MODE=negcon presents a NeGcon instead (analog I/II), which the
 * game detects but whose menus did not accept I/A at team select in testing.
 * Keyboard play gets the stock pad.
 */
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#include "mod_plugins.h"

#define R4AN_ID "r4.analog"

/* PSX pad bits (active low in the frame) */
#define BTN_L1       (1u << 10)
#define BTN_R1       (1u << 11)
#define BTN_CROSS    (1u << 14)
#define BTN_SQUARE   (1u << 15)

#define TWIST_DEADZONE 10      /* of 128 */

static uint32_t clamp255(int v) { return v < 0 ? 0u : v > 255 ? 255u : (uint32_t)v; }

static uint32_t twist_from_stick(uint32_t lx) {
    int d = (int)lx - 128;
    int mag = d < 0 ? -d : d;
    if (mag <= TWIST_DEADZONE) return 128u;
    /* rescale (deadzone..128) onto (0..128) so full lock stays reachable */
    int out = (mag - TWIST_DEADZONE) * 128 / (128 - TWIST_DEADZONE);
    return clamp255(128 + (d < 0 ? -out : out));
}

static int s_test = -1;
static int s_jog = -1;      /* R4_ANALOG_MODE=negcon selects the NeGcon */
static int s_mode_jogcon(void) {
    if (s_jog < 0) { const char *e = getenv("R4_ANALOG_MODE"); s_jog = !(e && e[0] == 'n'); }
    return s_jog;
}     /* R4_ANALOG_TEST=1: keyboard D-pad drives the twist */

static int r4an_transform(const PSXModPadFrame *f, PSXModPadOutput *o) {
    if (s_test < 0) { const char *e = getenv("R4_ANALOG_TEST"); s_test = e && e[0] == '1'; }
    const uint32_t pressed = ~f->buttons & 0xFFFFu; /* active high */
    if (!(f->host_flags & PSX_MOD_PAD_HOST_GAMEPAD) &&
        !(f->host_flags & PSX_MOD_PAD_HOST_SOURCE) && !s_test)
        return 0;                                   /* keyboard: stock pad */
    uint32_t gas = (f->host_flags & PSX_MOD_PAD_HOST_RT) ? f->host_rt : 0u;
    uint32_t brake = (f->host_flags & PSX_MOD_PAD_HOST_LT) ? f->host_lt : 0u;
    if (pressed & BTN_CROSS) gas = 255u;
    if (pressed & BTN_SQUARE) brake = 255u;
    if (s_mode_jogcon()) {
        if (pressed & BTN_R1) gas = 255u;
        if (pressed & BTN_L1) brake = 255u;
    }
    if (s_mode_jogcon()) {
        /* JogCon: the dial position is the steering; buttons stay the pad's,
         * the triggers press Cross / Square (R4's accelerate / brake). */
        uint32_t b = f->buttons & 0xFFFFu;
        if (gas >= 64u) b &= ~BTN_R1;           /* R4 JogCon: R1 accelerates */
        if (brake >= 64u) b &= ~BTN_L1;         /*            L1 brakes      */
        o->type = PSX_MOD_PAD_JOGCON;
        o->buttons = b;
        o->lx = twist_from_stick(f->lx);
        if (s_test) {
            if (pressed & (1u << 7)) o->lx = 0u;
            if (pressed & (1u << 5)) o->lx = 255u;
        }
        o->ly = o->rx = o->ry = 128u;
        o->negcon_i = o->negcon_ii = o->negcon_l = 0u;
        return 1;
    }
    o->type = PSX_MOD_PAD_NEGCON;
    o->buttons = f->buttons & 0xFFFFu;
    o->lx = twist_from_stick(f->lx);
    if (s_test) {                                   /* test hook only */
        if (pressed & (1u << 7)) o->lx = 0u;       /* Left  */
        if (pressed & (1u << 5)) o->lx = 255u;     /* Right */
    }
    o->ly = 128u;
    o->rx = 128u;
    o->ry = 128u;
    o->negcon_i = gas;
    o->negcon_ii = brake;
    o->negcon_l = (pressed & BTN_L1) ? 255u : 0u;
    return 1;
}

static const PSXModPadTransform k_xf = {
    sizeof(PSXModPadTransform),
    PSX_MOD_PAD_TYPE_BIT(PSX_MOD_PAD_NEGCON) | PSX_MOD_PAD_TYPE_BIT(PSX_MOD_PAD_DIGITAL) |
        PSX_MOD_PAD_TYPE_BIT(PSX_MOD_PAD_DUALSHOCK) | PSX_MOD_PAD_TYPE_BIT(PSX_MOD_PAD_JOGCON),
    PSX_MOD_PAD_JOGCON,
    r4an_transform,
};

static void r4an_activate(void) {
    if (psx_mod_set_pad_transform(0, &k_xf))
        psx_mod_counter_add("r4.analog.player1", 1);
    if (psx_mod_set_pad_transform(1, &k_xf))
        psx_mod_counter_add("r4.analog.player2", 1);
}

PSX_MOD_CONSTRUCTOR(r4an_register_plugin) {
    psx_mod_register_activation_plugin(R4AN_ID, r4an_activate);
}
