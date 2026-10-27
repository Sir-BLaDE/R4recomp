/* r4_projection_replay.cpp - R4 (SLUS-00797) in-between race frames by
 * projection replay (psxrecomp render_pass_replay.hpp), the alternative to
 * the field-blend recipe in r4_interp.c (frame-rate option method =
 * "projection").
 *
 * Real frame: at the loop head (ClearOTagR entry, ra 0x8001E764) the main
 * loop's RAM, scratchpad and registers are snapshotted and the GTE begins
 * recording every RTPS/RTPT the race handler performs with its final
 * rotation/translation. At the pass point (VSync(0) entry, ra 0x8001E7E4) the
 * recording is paired with the previous tick's: a projection whose caller,
 * command and input vertices recur is matched, so its two matrices describe
 * the motion of that vertex set between the ticks.
 *
 * Pass: RAM is put back to the loop head's, the dead buffer (bp = counter & 1
 * ^ 1) is selected and cleared exactly as r4_interp.c does, and the loop's
 * handler span [0x8001E784, 0x8001E7B8) is re-run: the state-table lookup,
 * the handler's logic and draw, with every matched projection's matrix
 * swapped for its interpolation at the GTE bridge. Unmatched vertices (new
 * geometry, cuts) keep the current frame's placement. The OT it built is
 * then submitted into the dead buffer. The pad poll and the sound tick
 * (0x800128B0, 0x80050088) before the handler are skipped: their RAM
 * effects are logic, and the sandbox drops device stores anyway.
 *
 * Same gates as r4_interp.c: pacing 0x180, not paused, race phase 1..3,
 * known handler before and after the tick, consecutive ticks. */
#include "render_pass_replay.hpp"

#include "r4_interp.h"
#include "r4_interp_math.h"

namespace {
constexpr uint32_t SpanStart = 0x8001E784u;   /* after the two loop-head calls */
constexpr uint32_t SpanStop  = 0x8001E7B8u;   /* DrawSync(0): handler returned */
constexpr const char* Plugin = "r4.framerate.projection";

PSXDrawReplay replay;
struct {
    int enabled;
    int pre_valid;
    uint32_t pre_handler;
    int8_t pre_paused;
    int prev_valid;
    int prev_mode;
    uint32_t prev_tick, prev_demo_tick;
    uint32_t bp;
} P;

uint32_t handler() {
    const uint32_t major = psx_mod_read_half(R4_STATE_MAJOR);
    const uint32_t minor = psx_mod_read_half(R4_STATE_MINOR);
    const uint32_t row = psx_mod_read_word(R4_STATE_TABLE + 4u * major);
    if ((row & 0xFFE00000u) != 0x80000000u) return 0;
    return psx_mod_read_word(row + 4u * minor);
}
int mode_of(uint32_t h) {
    uint32_t words[R4_SIG_WORDS];
    if ((h & 0xFFE00003u) != 0x80000000u) return R4_MODE_NONE;
    for (unsigned i = 0; i < R4_SIG_WORDS; i++) words[i] = psx_mod_read_word(h + 4u * i);
    return r4_classify_handler(h, words);
}
int gates(int mode) {
    if (mode == R4_MODE_NONE) return 0;
    if (psx_mod_read_word(R4_PACING) != 0x180u) return 0;
    if (P.pre_paused != 0 || (int8_t)psx_mod_read_byte(R4_PAUSED) != 0) return 0;
    const uint32_t phase = psx_mod_read_word(R4_PHASE);
    if ((mode == R4_MODE_TIME_ATTACK || mode == R4_MODE_GRAND_PRIX ||
         mode == R4_MODE_SPLIT) && phase - 1u >= 3u)
        return 0;
    if (mode == R4_MODE_DEMO && psx_mod_read_word(R4_DEMO_SUBMODE) >= 2u) return 0;
    return 1;
}

void loop_head(CPUState* cpu, uint32_t) {
    if (!P.enabled || g_psx_render_pass_active || cpu->gpr[31] != R4_RA_LOOP_HEAD) return;
    P.pre_valid = 1;
    P.pre_handler = handler();
    P.pre_paused = (int8_t)psx_mod_read_byte(R4_PAUSED);
    /* Snapshot only frames that can become a pass: menus and loads cost
     * nothing. The projection capture closes at the pass point. */
    if (mode_of(P.pre_handler) == R4_MODE_NONE || P.pre_paused ||
        psx_mod_read_word(R4_PACING) != 0x180u) {
        replay.invalidate();
        return;
    }
    replay.capture(cpu, SpanStart, SpanStop);
}

int pass(CPUState* cpu, void*, uint32_t alpha) {
    if (!replay.restore(cpu, alpha)) return 0;
    /* Build and draw in the buffer the game did not build this tick: its RAM
     * is dead and its VRAM rows are the rect the flip is about to show. */
    const uint32_t buf = R4_BUF_BASE + P.bp * R4_BUF_STRIDE;
    psx_mod_write_word(R4_CUR_BUF, buf);
    psx_mod_write_word(R4_BUF_INDEX, P.bp);
    psx_mod_write_word(R4_SPAD_OT, buf + 0x70u);
    psx_mod_write_word(R4_SPAD_HEAP, buf + 0x1670u);
    PSXDrawReplay::call(cpu, R4_CLEAR_OTAG_R, buf + 0x70u, 0x2C0u);
    PSXDrawReplay::call(cpu, R4_CLEAR_OTAG_R, buf + 0xB70u, 0x2C0u);
    if (!replay.draw(cpu)) { psx_mod_counter_add("r4.proj.draw_failed", 1); return 0; }
    PSXDrawReplay::call(cpu, R4_PUT_DRAW_ENV, buf);
    PSXDrawReplay::call(cpu, R4_DRAW_OTAG, buf + 0xB6Cu);
    if (psx_mod_read_word(R4_OT2_ENABLED)) PSXDrawReplay::call(cpu, R4_DRAW_OTAG, buf + 0x166Cu);
    psx_mod_counter_add("r4.proj.interpolated_projections", replay.stats.replayed);
    return 1;
}

void pass_point(CPUState* cpu, uint32_t) {
    if (!P.enabled || g_psx_render_pass_active || cpu->gpr[31] != R4_RA_PASS_POINT ||
        cpu->gpr[4] != 0u)
        return;
    const int pre_valid = P.pre_valid;
    P.pre_valid = 0;
    if (!pre_valid) { P.prev_valid = 0; replay.invalidate(); return; }
    const uint32_t h = handler();
    const int mode = h == P.pre_handler ? mode_of(h) : R4_MODE_NONE;
    if (!gates(mode)) { P.prev_valid = 0; replay.invalidate(); return; }
    const uint32_t tick = psx_mod_read_word(R4_TICK);
    const uint32_t demo_tick = psx_mod_read_word(R4_DEMO_TICK);
    const uint32_t counter = mode == R4_MODE_DEMO ? demo_tick : tick;
    const int continuous = P.prev_valid && P.prev_mode == mode &&
        (mode == R4_MODE_DEMO ? demo_tick == P.prev_demo_tick + 1u : tick == P.prev_tick + 1u);
    const bool ready = replay.prepare(counter) && replay.ticks == 1u;
    psx_mod_counter_add("r4.proj.frames", 1);
    psx_mod_counter_add("r4.proj.projections", replay.stats.captured);
    psx_mod_counter_add("r4.proj.matched", replay.stats.matched);
    psx_mod_counter_add("r4.proj.moving", replay.stats.changed);
    psx_mod_counter_add("r4.proj.unmatched", replay.stats.unmatched);
    psx_mod_counter_add("r4.proj.discontinuities", replay.stats.discontinuities);
    if (continuous && ready) {
        const uint32_t b = psx_mod_read_word(R4_FRAME_COUNTER) & 1u;
        const uint32_t disp = R4_BUF_BASE + b * R4_BUF_STRIDE + 0x5Cu;
        PSXModRenderPassFrame frame{};
        frame.struct_size = sizeof frame;
        frame.period_vblanks = 2;        /* 30 Hz logic under a 60 Hz VBlank */
        frame.shown_after_vblanks = 1;
        /* The rect the flip shows: DISPENV of the buffer built this tick. */
        frame.x = psx_mod_read_half(disp);
        frame.y = psx_mod_read_half(disp + 2u);
        frame.w = psx_mod_read_half(disp + 4u);
        frame.h = psx_mod_read_half(disp + 6u);
        P.bp = b ^ 1u;
        psx_mod_counter_add("r4.proj.passes", psx_mod_render_pass_frame(cpu, &frame, pass, nullptr));
    }
    P.prev_valid = 1;
    P.prev_mode = mode;
    P.prev_tick = tick;
    P.prev_demo_tick = demo_tick;
}
}

extern "C" int r4_projection_register_hooks(void) {
    return psx_mod_register_function_entry_plugin(Plugin, R4_VSYNC, pass_point) +
           psx_mod_register_function_entry_plugin(Plugin, R4_CLEAR_OTAG_R, loop_head);
}

extern "C" void r4_projection_activate(int enabled) {
    replay.invalidate();
    P = {};
    P.enabled = enabled;
}
