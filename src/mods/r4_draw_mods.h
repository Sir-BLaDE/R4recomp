#ifndef R4_DRAW_MODS_H
#define R4_DRAW_MODS_H
#include <stddef.h>
#include "cpu_state.h"
typedef struct R4WsDrawState R4WsDrawState;
/* Capture on main, execute only against the owning private context, replay
 * metadata on main inside the queued GPU transaction, then destroy. */
R4WsDrawState *r4_ws_draw_capture(void);
int r4_ws_draw_entry(R4WsDrawState *, CPUState *, uint32_t address);
int r4_ws_draw_replay_metadata(R4WsDrawState *, size_t word_index);
void r4_ws_draw_destroy(R4WsDrawState *);
#endif
