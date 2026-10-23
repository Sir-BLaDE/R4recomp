#include "r4_draw_mods.h"
#include "r4_hide_rear_view_mirror.h"
#include <stdlib.h>
#ifdef R4_THREADED_DRAW
struct R4DrawMods {
    R4WsDrawState *ws;
    R4MdDrawState *md;
    R4CameraDrawState *camera;
    int hide_mirror;
};
/* Registration is main-thread setup only. Shared entry addresses must invoke
 * the aggregate once, in the same plugin order as the main draw. */
static uint32_t registered[128];
static size_t registered_count;
int r4_draw_mods_register_one(uint32_t address, PsxCtxEntryHook cb, void *user) {
    for(size_t i=0;i<registered_count;i++) if(registered[i]==address) return 1;
    if(registered_count==128 || !psx_ctx_register_entry_hook(address,cb,user)) return 0;
    registered[registered_count++]=address;
    return 1;
}
int r4_draw_mods_register_entries(PsxCtxEntryHook cb,void *user) {
    registered_count=0;
    return r4_ws_draw_register_entries(cb,user) && r4_md_draw_register_entries(cb,user) &&
           r4_camera_draw_register_entries(cb,user) &&
           r4_draw_mods_register_one(R4_REAR_MIRROR_ENTRY,cb,user);
}
R4DrawMods *r4_draw_mods_capture(void) {
    if(r4_optional_draw_hooks_active()) return NULL;
    R4DrawMods *p=calloc(1,sizeof *p);
    if(!p) return NULL;
    p->ws=r4_ws_draw_capture(); p->md=r4_md_draw_capture();
    p->camera=r4_camera_draw_capture(); p->hide_mirror=r4_hide_mirror_draw_enabled();
    if(!p->ws || !p->md || !p->camera) { r4_draw_mods_destroy(p); return NULL; }
    return p;
}
int r4_draw_mods_entry(R4DrawMods *p,CPUState *cpu,uint32_t address) {
    if(!p || !cpu || !cpu->ctx) return 0;
    if(!r4_camera_draw_entry(p->camera,cpu,address)) return 0;
    R4RearMirrorEntryState mirror={cpu->gpr[4],psx_ctx_read32(cpu->ctx,R4_REAR_MIRROR_GATE)};
    if(r4_rear_mirror_suppress_entry(p->hide_mirror,address,&mirror)) {
        cpu->gpr[4]=mirror.argument; psx_ctx_write32(cpu->ctx,R4_REAR_MIRROR_GATE,mirror.gate_value);
    }
    return r4_md_draw_entry(p->md,cpu,address) && r4_ws_draw_entry(p->ws,cpu,address);
}
int r4_draw_mods_replay_metadata(R4DrawMods *p,size_t index) {
    return p && r4_ws_draw_replay_metadata(p->ws,index);
}
void r4_draw_mods_destroy(R4DrawMods *p) {
    if(p) { r4_ws_draw_destroy(p->ws); r4_md_draw_destroy(p->md);
        r4_camera_draw_destroy(p->camera); free(p); }
}
#endif
