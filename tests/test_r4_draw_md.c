#define R4_THREADED_DRAW 1
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/r4_max_detail_plugin.c"
#undef NDEBUG
#include <assert.h>
#include <pthread.h>
static uint8_t main_ram[0x200000];
static int margin=100;
uint64_t psx_cycle_count;
int r4_draw_mods_register_one(uint32_t a,PsxCtxEntryHook h,void *u) { (void)a;(void)h;(void)u;return 1; }
uint32_t psx_mod_read_word(uint32_t a) { uint32_t v; memcpy(&v,main_ram+(a&0x1ffffc),4); return v; }
uint16_t psx_mod_read_half(uint32_t a) { return psx_mod_read_word(a&~3u)>>((a&2u)*8u); }
void psx_mod_write_word(uint32_t a,uint32_t v) { memcpy(main_ram+(a&0x1ffffc),&v,4); }
void psx_mod_write_half(uint32_t a,uint16_t v) { memcpy(main_ram+(a&0x1ffffe),&v,2); }
int32_t psx_mod_widescreen_x_margin(void) { return margin; }
int psx_ram_8mb_active(void) { return 0; }
int psx_mod_draw_distance_clamp_enabled(void) { return 1; }
uint32_t psx_ctx_read32(PsxExecCtx *x,uint32_t a) { uint32_t v; uint8_t *p=(a&0x1ffffc00)==0x1f800000 ? x->scratch+(a&0x3fc) : x->ram+(a&0x1ffffc); memcpy(&v,p,4); return v; }
void psx_ctx_write32(PsxExecCtx *x,uint32_t a,uint32_t v) { uint8_t *p=(a&0x1ffffc00)==0x1f800000 ? x->scratch+(a&0x3fc) : x->ram+(a&0x1ffffc); memcpy(p,&v,4); }
static void *run(void *arg) {
    R4MdDrawState *p=arg;
    PsxExecCtx *x=calloc(1,sizeof *x); assert(x); x->ram=calloc(1,0x200000); assert(x->ram); x->cpu.ctx=x;
    psx_ctx_write32(x,R4_MD_COURSE_FAR_ADDR&~3u,0xdeadbeef);
    psx_ctx_write32(x,R4_MD_COURSE_2P_ADDR&~3u,0xdeadbeef);
    assert(r4_md_draw_entry(p,&x->cpu,R4_MD_COURSE_DISPATCH_FN));
    assert((uint16_t)(psx_ctx_read32(x,R4_MD_COURSE_FAR_ADDR&~3u)>>((R4_MD_COURSE_FAR_ADDR&2u)*8u)) == (uint16_t)R4_MD_COURSE_FAR_FULL);
    assert((uint16_t)(psx_ctx_read32(x,R4_MD_COURSE_2P_ADDR&~3u)>>((R4_MD_COURSE_2P_ADDR&2u)*8u)) == 0);
    free(x->ram); free(x); return NULL;
}
int main(void) {
    s_enabled=1; s_opt.course_full=1; s_opt.split_same=1;
    R4MdDrawState *p[4]; for(int i=0;i<4;i++) { p[i]=r4_md_draw_capture(); assert(p[i]); }
    s_enabled=0; s_opt.course_full=0; s_opt.split_same=0; margin=0;
    pthread_t t[4]; for(int i=0;i<4;i++) assert(!pthread_create(&t[i],NULL,run,p[i]));
    for(int i=0;i<4;i++) { assert(!pthread_join(t[i],NULL)); r4_md_draw_destroy(p[i]); }
    for(size_t i=0;i<sizeof main_ram;i++) assert(main_ram[i]==0);
    puts("private max-detail options and scratch writes: four contexts passed");
}
