#ifndef R4_DRAW_MODS_H
#define R4_DRAW_MODS_H
#include <stddef.h>
#include "cpu_state.h"
#include "psx_exec_ctx.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct R4WsDrawState R4WsDrawState;
typedef struct R4MdDrawState R4MdDrawState;
typedef struct R4CameraDrawState R4CameraDrawState;
typedef struct R4DrawMods R4DrawMods;
int r4_draw_mods_register_one(uint32_t, PsxCtxEntryHook, void *);
int r4_draw_mods_register_entries(PsxCtxEntryHook, void *);
R4DrawMods *r4_draw_mods_capture(void);
int r4_draw_mods_entry(R4DrawMods *, CPUState *, uint32_t);
int r4_draw_mods_replay_metadata(R4DrawMods *, size_t word_index);
void r4_draw_mods_destroy(R4DrawMods *);
/* Capture on main, execute only against the owning private context, replay
 * metadata on main inside the queued GPU transaction, then destroy. */
R4WsDrawState *r4_ws_draw_capture(void);
int r4_ws_draw_register_entries(PsxCtxEntryHook callback, void *user);
int r4_ws_draw_entry(R4WsDrawState *, CPUState *, uint32_t address);
int r4_ws_draw_replay_metadata(R4WsDrawState *, size_t word_index);
void r4_ws_draw_destroy(R4WsDrawState *);
R4MdDrawState *r4_md_draw_capture(void);
int r4_md_draw_register_entries(PsxCtxEntryHook callback, void *user);
int r4_md_draw_entry(R4MdDrawState *, CPUState *, uint32_t address);
void r4_md_draw_destroy(R4MdDrawState *);
R4CameraDrawState *r4_camera_draw_capture(void);
int r4_camera_draw_register_entries(PsxCtxEntryHook, void *);
int r4_camera_draw_entry(R4CameraDrawState *, CPUState *, uint32_t);
void r4_camera_draw_destroy(R4CameraDrawState *);
int r4_hide_mirror_draw_enabled(void);
int r4_optional_draw_hooks_active(void);
#ifdef __cplusplus
}
#endif
#endif
