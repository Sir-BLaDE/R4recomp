#define R4_THREADED_DRAW 1
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/r4_camera_look_plugin.c"
#undef NDEBUG
#include <assert.h>
#include <pthread.h>
static uint8_t main_ram[0x200000];
int r4_draw_mods_register_one(uint32_t a,PsxCtxEntryHook h,void *u) { (void)a;(void)h;(void)u;return 1; }
uint32_t psx_mod_read_word(uint32_t a) { uint32_t v; memcpy(&v,main_ram+(a&0x1ffffc),4); return v; }
uint16_t psx_mod_read_half(uint32_t a) { return psx_mod_read_word(a&~3u)>>((a&2u)*8u); }
uint8_t psx_mod_read_byte(uint32_t a) { return psx_mod_read_word(a&~3u)>>((a&3u)*8u); }
void psx_mod_write_word(uint32_t a,uint32_t v) { memcpy(main_ram+(a&0x1ffffc),&v,4); }
uint32_t psx_ctx_read32(PsxExecCtx *x,uint32_t a) { uint32_t v; uint8_t *p=(a&0x1ffffc00)==0x1f800000 ? x->scratch+(a&0x3fc) : x->ram+(a&0x1ffffc); memcpy(&v,p,4); return v; }
void psx_ctx_write32(PsxExecCtx *x,uint32_t a,uint32_t v) { uint8_t *p=(a&0x1ffffc00)==0x1f800000 ? x->scratch+(a&0x3fc) : x->ram+(a&0x1ffffc); memcpy(p,&v,4); }
static void *run(void *arg) {
    R4CameraDrawState *p=arg;
    PsxExecCtx *x=calloc(1,sizeof *x); assert(x); x->ram=calloc(1,0x200000); assert(x->ram); x->cpu.ctx=x;
    psx_ctx_write32(x,R4_HANDLER_TABLE_ADDR,0x80010000);
    psx_ctx_write32(x,0x80010000,0x80114a38);
    psx_ctx_write32(x,0x80114a38,0x27bdffc8); psx_ctx_write32(x,0x80114a3c,0x3c03800f);
    psx_ctx_write32(x,R4_RACE_PHASE_ADDR,2);
    for(unsigned i=0;i<5;i++) psx_ctx_write32(x,k_camera_inputs[i],i*100);
    assert(r4_camera_draw_entry(p,&x->cpu,R4_CAMERA_BUILDER));
    assert(p->state.restore_pending);
    assert(psx_ctx_read32(x,R4_CAMERA_INPUT_YAW)!=400);
    assert(r4_camera_draw_entry(p,&x->cpu,R4_CAMERA_LOOK_INPUT_RESTORE_ENTRY));
    for(unsigned i=0;i<5;i++) assert(psx_ctx_read32(x,k_camera_inputs[i])==i*100);
    assert(!p->state.restore_pending);
    free(x->ram); free(x); return NULL;
}
int main(void) {
    s_enabled=1; s_look.yaw_radians=0.3f;
    R4CameraDrawState *p[4]; for(int i=0;i<4;i++) { p[i]=r4_camera_draw_capture(); assert(p[i]); }
    s_enabled=0; s_look.yaw_radians=0;
    pthread_t t[4]; for(int i=0;i<4;i++) assert(!pthread_create(&t[i],NULL,run,p[i]));
    for(int i=0;i<4;i++) { assert(!pthread_join(t[i],NULL)); r4_camera_draw_destroy(p[i]); }
    for(size_t i=0;i<sizeof main_ram;i++) assert(main_ram[i]==0);
    assert(!s_restore_pending);
    puts("private camera look snapshot and input restoration: four contexts passed");
}
