#define R4_THREADED_DRAW 1
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/r4_widescreen_plugin.c"
#include <assert.h>
#include <pthread.h>
static uint8_t main_ram[0x200000];
static int margin = 100, tag_calls;
uint32_t psx_mod_read_word(uint32_t a) { uint32_t v; memcpy(&v, main_ram + (a & 0x1ffffc), 4); return v; }
uint16_t psx_mod_read_half(uint32_t a) { return psx_mod_read_word(a & ~3u) >> ((a & 2u)*8u); }
void psx_mod_write_word(uint32_t a, uint32_t v) { memcpy(main_ram+(a&0x1ffffc), &v,4); }
int32_t psx_mod_widescreen_x_margin(void) { return margin; }
void psx_mod_tag_hud_primitive(uint32_t a, int edge) { (void)a; (void)edge; ++tag_calls; }
uint32_t psx_ctx_read32(PsxExecCtx *x,uint32_t a) { uint32_t v; uint8_t *p=(a&0x1ffffc00)==0x1f800000 ? x->scratch+(a&0x3fc) : x->ram+(a&0x1ffffc); memcpy(&v,p,4); return v; }
void psx_ctx_write32(PsxExecCtx *x,uint32_t a,uint32_t v) { uint8_t *p=(a&0x1ffffc00)==0x1f800000 ? x->scratch+(a&0x3fc) : x->ram+(a&0x1ffffc); memcpy(p,&v,4); }
const PsxCtxGpuWord *psx_ctx_gpu_words(const PsxExecCtx *x,size_t *n) { *n=x->gpu_n; return NULL; }
static void *run(void *arg) {
    R4WsDrawState *p=arg;
    PsxExecCtx *x=calloc(1,sizeof *x); assert(x);
    x->ram=calloc(1,0x200000); assert(x->ram); x->cpu.ctx=x;
    const uint32_t heap=R4_BUF0+R4_BUF_HEAP;
    psx_ctx_write32(x,R4_HANDLER_TABLE_ADDR,0x80010000);
    psx_ctx_write32(x,0x80010000,0x8005e118);
    psx_ctx_write32(x,R4_CUR_BUF_ADDR,R4_BUF0);
    psx_ctx_write32(x,R4_HEAP_PTR_ADDR,heap);
    x->cpu.gpr[4]=R4_BUF0+R4_BUF_OT1;
    assert(r4_ws_draw_entry(p,&x->cpu,R4_CLEAR_OTAG_FN));
    assert(r4_ws_draw_entry(p,&x->cpu,0x80021ddc));
    psx_ctx_write32(x,heap,0x03000000);
    psx_ctx_write32(x,heap+4,0x60000000);
    psx_ctx_write32(x,heap+8,0x000a000a);
    psx_ctx_write32(x,heap+12,0x00080008);
    psx_ctx_write32(x,R4_HEAP_PTR_ADDR,heap+16);
    x->gpu_n=7;
    x->cpu.gpr[4]=R4_BUF0+R4_BUF_OT1_HEAD;
    assert(r4_ws_draw_entry(p,&x->cpu,R4_DRAW_OTAG_FN));
    assert(p->count==1 && p->tags[0].key==heap && p->tags[0].edge==-1 && p->tags[0].word_index==7);
    free(x->ram); free(x); return NULL;
}
int main(void) {
    s_enabled=1;
    R4WsDrawState *p[4]; for(int i=0;i<4;i++) { p[i]=r4_ws_draw_capture(); assert(p[i]); }
    /* Mutating main after capture cannot alter any worker's enable/margin. */
    s_enabled=0; margin=0;
    pthread_t t[4]; for(int i=0;i<4;i++) assert(!pthread_create(&t[i],NULL,run,p[i]));
    for(int i=0;i<4;i++) assert(!pthread_join(t[i],NULL));
    assert(tag_calls==0 && s_buf[0].nranges==0 && !s_open.open);
    for(int i=0;i<4;i++) {
        assert(r4_ws_draw_replay_metadata(p[i],0)); assert(tag_calls==i);
        assert(r4_ws_draw_replay_metadata(p[i],7)); assert(tag_calls==i+1);
        r4_ws_draw_destroy(p[i]);
    }
    puts("private widescreen HUD state and ordered tags: four contexts passed");
}
