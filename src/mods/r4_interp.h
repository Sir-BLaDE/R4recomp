/* r4_interp.h - R4 (SLUS-00797) true interpolated frames: per-tick capture of
 * car and camera state and the per-mode draw-only pass sequences run inside
 * framework render passes (psx_mod_render_pass). See r4_interp.c. */
#ifndef R4_INTERP_H
#define R4_INTERP_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "mod_plugins.h"

/* Main loop call sites (r4dis 0x8001E708-0x8001E844). */
#define R4_VSYNC            0x8008B330u
#define R4_CLEAR_OTAG_R     0x80093418u
#define R4_PUT_DRAW_ENV     0x80093590u
#define R4_DRAW_OTAG        0x80093520u
#define R4_RA_LOOP_HEAD     0x8001E764u   /* first ClearOTagR */
#define R4_RA_PASS_POINT    0x8001E7E4u   /* VSync(0) */
#define R4_RA_NESTED        0x8001E7E8u   /* return address for pass calls */

/* Globals (US). */
#define R4_FRAME_COUNTER    0x800AC064u   /* buffer b = counter & 1 */
#define R4_PACING           0x800AC794u   /* 0x180 = 30 Hz races */
#define R4_BUF_BASE         0x800ADCA0u
#define R4_BUF_STRIDE       0x22778u
#define R4_CUR_BUF          0x800ACDCCu
#define R4_BUF_INDEX        0x800F4DA0u
#define R4_OT2_ENABLED      0x800ACDB0u
#define R4_STATE_TABLE      0x8009EBCCu
#define R4_STATE_MAJOR      0x800F4E1Au
#define R4_STATE_MINOR      0x800F3BD6u
#define R4_PAUSED           0x800F4E18u
#define R4_PHASE            0x800FF860u
#define R4_TICK             0x800F2F94u
#define R4_DEMO_TICK        0x800ACCC4u
#define R4_DEMO_SUBMODE     0x800ACCD0u
#define R4_FADE_OUT         0x800AC788u   /* s16 */
#define R4_REPLAY_FADE      0x800AC760u
#define R4_SHOT_DEMO        0x800ACCCCu   /* TV shot counter, reset on a cut */
#define R4_SHOT_REPLAY      0x800AC824u
#define R4_CAR_LIST         0x800FFDD0u
#define R4_CAR_COUNT        0x800AC754u   /* s16 */
#define R4_SPAD_HEAP        0x1F800000u
#define R4_SPAD_OT          0x1F800004u

/* Draw-replay projection method (r4_projection_replay.cpp): the main loop's
 * handler span is re-run from the loop head's RAM with the GTE projections
 * recorded during the real frame interpolated (psxrecomp render_pass_replay).
 * Hooks register once under the manifest [[plugin]] id
 * "r4.framerate.projection"; returns how many psxrecomp accepted (2 = both). */
int r4_projection_register_hooks(void);
void r4_projection_activate(int enabled);

/* Called once from the package's constructor: registers the two
 * function-entry hooks under the manifest [[plugin]] id "r4.framerate"
 * (psxrecomp runs them only while the mod plan activates that id). Returns how many psxrecomp accepted (2 = both). */
int r4_interp_register_hooks(void);

/* Activation resets history across sessions. */
void r4_interp_activate(int enabled);

/* Bracket the link bridge's base local draw; camera capture happens inside
 * that sandbox, end runs after restoration. Extra callbacks receive alpha>0. */
void r4_interp_local_begin(struct CPUState *cpu, unsigned seat);
void r4_interp_local_camera(void);
void r4_interp_local_end(struct CPUState *cpu, const PSXModRenderPass *rect,
                         PSXModRenderPassFn draw, void *user, int ok);

#ifdef __cplusplus
}
#endif

#endif
