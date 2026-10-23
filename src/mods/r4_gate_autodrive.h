/* Test-only closed-loop driver, adapted from the owner's timing harness
 * (R4 commit 8e83dd8, src/mods/r4_autodrive.h).
 *
 * With R4_AUTODRIVE=1 in the environment, the isolation package drives
 * player 1 itself during a race: accelerate held, steering toward the course
 * centreline LOOKAHEAD segments ahead of the nearest one. Unset (the
 * default), nothing changes. The caller supplies r4_gate_ad_read and resets
 * motion history when loading a savestate; this package never ships.
 *
 * Centreline: r4_pvs.h (segment x/z at +8/+0xC, world >> 8; racing runs
 * toward lower segment numbers). The chase camera (scratchpad 0x1F800008,
 * /4 = centreline units) stands in for the car; its motion gives the heading.
 */
#ifndef R4_AUTODRIVE_H
#define R4_AUTODRIVE_H

#include <math.h>
#include <stdint.h>
#include <stdlib.h>

#include "mod_plugins.h"
#include "r4_pvs.h"

#define R4_AD_CAMERA        0x1F800008u
#define R4_AD_LOOKAHEAD     4
#define R4_AD_DEADZONE      0.04
#define R4_AD_ACCEL         0xBFFFu   /* Cross held (active-low) */
#define R4_AD_RIGHT         0xBFDFu
#define R4_AD_LEFT          0xBF7Fu
#define R4_AD_COAST_RIGHT   0xFFDFu   /* steer off the throttle */
#define R4_AD_COAST_LEFT    0xFF7Fu
#define R4_AD_SHARP         0.30      /* radians: lift in sharp corners */

static int r4_autodrive_enabled(void) {
    static int on = -1;
    if (on < 0) {
        const char *e = getenv("R4_AUTODRIVE");
        on = e && e[0] && e[0] != '0';
    }
    return on;
}

/* Buttons for this poll; 0 when the course data is not readable. */
static struct { double px, pz; int have_prev, seg; } r4_ad_state[2] = {{0, 0, 0, -1}, {0, 0, 0, -1}};
static void r4_autodrive_reset(void) {
    for (unsigned p = 0; p < 2; ++p) {
        r4_ad_state[p].px = r4_ad_state[p].pz = 0;
        r4_ad_state[p].have_prev = 0; r4_ad_state[p].seg = -1;
    }
}
static uint32_t r4_autodrive_buttons(unsigned player, uint32_t camera) {
    double px = r4_ad_state[player].px, pz = r4_ad_state[player].pz;
    int have_prev = r4_ad_state[player].have_prev, seg = r4_ad_state[player].seg;
    const uint32_t n = r4_gate_ad_read(R4_TRACK_SEGMENT_COUNT_ADDR);
    const uint32_t tab = r4_gate_ad_read(R4_TRACK_SEGMENT_TABLE_ADDR);
    if (n == 0 || n > 5u * R4_PVS_SECTIONS_MAX || (tab & 0xFFE00003u) != 0x80000000u)
        return 0;
    const double x = (double)(int32_t)r4_gate_ad_read(camera) / 4.0;
    const double z = (double)(int32_t)r4_gate_ad_read(camera + 8u) / 4.0;
#define R4_AD_SEG(i, off) ((double)(int32_t)r4_gate_ad_read( \
        tab + R4_TRACK_SEGMENT_STRIDE * (uint32_t)(i) + (off)))
    /* Nearest segment: the whole circuit once, then a window around it. */
    int lo = seg < 0 ? 0 : seg - 20, hi = seg < 0 ? (int)n - 1 : seg + 20, best = 0;
    double best_d = 1e300;
    for (int k = lo; k <= hi; k++) {
        const int i = ((k % (int)n) + (int)n) % (int)n;
        const double dx = R4_AD_SEG(i, R4_TRACK_SEGMENT_X) - x;
        const double dz = R4_AD_SEG(i, R4_TRACK_SEGMENT_Z) - z;
        if (dx * dx + dz * dz < best_d) { best_d = dx * dx + dz * dz; best = i; }
    }
    seg = best;
    const int t = ((seg - R4_AD_LOOKAHEAD) % (int)n + (int)n) % (int)n;
    double hx = x - px, hz = z - pz;
    const int moving = have_prev && hx * hx + hz * hz >= 16.0;   /* else never lift */
    if (!have_prev || hx * hx + hz * hz < 1.0) {   /* barely moving: track direction */
        const int a = (seg - 1 + (int)n) % (int)n;
        hx = R4_AD_SEG(a, R4_TRACK_SEGMENT_X) - R4_AD_SEG(seg, R4_TRACK_SEGMENT_X);
        hz = R4_AD_SEG(a, R4_TRACK_SEGMENT_Z) - R4_AD_SEG(seg, R4_TRACK_SEGMENT_Z);
    }
    const double want = atan2(R4_AD_SEG(t, R4_TRACK_SEGMENT_X) - x,
                              R4_AD_SEG(t, R4_TRACK_SEGMENT_Z) - z);
#undef R4_AD_SEG
    double err = want - atan2(hx, hz);
    while (err > 3.14159265358979) err -= 6.28318530717959;
    while (err < -3.14159265358979) err += 6.28318530717959;
    r4_ad_state[player].px = x; r4_ad_state[player].pz = z; r4_ad_state[player].have_prev = 1; r4_ad_state[player].seg = seg;
    if (moving && err > R4_AD_SHARP) return R4_AD_COAST_RIGHT;
    if (moving && err < -R4_AD_SHARP) return R4_AD_COAST_LEFT;
    if (err > R4_AD_DEADZONE) return R4_AD_RIGHT;
    if (err < -R4_AD_DEADZONE) return R4_AD_LEFT;
    return R4_AD_ACCEL;
}

#endif /* R4_AUTODRIVE_H */
