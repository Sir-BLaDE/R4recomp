/* Exact diagnostic for the existing interpolation recipe. Include after
 * r4_interp_workers.h; debug builds only. No result is admitted to presentation. */
#ifndef PSX_NO_DEBUG_TOOLS
#include "gpu.h"
/* Debug renderer contract: active pass source, including native-wide margins. */
extern size_t gl_renderer_pass_debug_capture(uint8_t *, size_t, uint32_t *, uint32_t *, int *);
typedef struct R4VerifyImage {
    uint8_t *rgba;
    size_t bytes;
    uint32_t width, height;
    int wide;
} R4VerifyImage;
static int r4_verify_image(R4VerifyImage *image) {
    size_t required = gl_renderer_pass_debug_capture(NULL, 0, &image->width, &image->height, &image->wide);
    if (!required || required > 512u * 1024u * 1024u) return 0;
    image->rgba = malloc(required);
    if (!image->rgba) return 0;
    image->bytes = gl_renderer_pass_debug_capture(image->rgba, required, &image->width, &image->height, &image->wide);
    return image->bytes == required;
}

typedef struct R4VerifyCapture {
    PsxCtxGpuWord *words;
    size_t count, capacity;
    const R4Blend *blend;
    uint32_t alpha;
    int failed, entered, complete;
    uint64_t elapsed;
    R4VerifyImage image;
} R4VerifyCapture;
typedef struct R4VerifyJob {
    R4DrawJob hook;
    const PsxCtxSnapshot *snapshot;
    const R4Blend *blend;
    uint32_t alpha;
    int complete;
    uint64_t elapsed;
} R4VerifyJob;

static void r4_verify_word(uint32_t word, uint32_t source, void *user) {
    R4VerifyCapture *c = user;
    if (c->failed) return;
    if (c->count == c->capacity) {
        size_t capacity = c->capacity ? c->capacity * 2 : 4096;
        if (capacity > (1u << 22)) { c->failed = 1; return; }
        void *p = realloc(c->words, capacity * sizeof *c->words);
        if (!p) { c->failed = 1; return; }
        c->words = p; c->capacity = capacity;
    }
    PsxCtxGpuWord *w = &c->words[c->count++];
    memset(w, 0, sizeof *w);
    w->word = word;
    w->src = source >= PSX_CTX_SRC_GP1 ? source : source & 0x1fffffffu;
    PgxpCtxVertex *v = &w->vertex;
    int32_t x = (int32_t)((word & 0x7ffu) ^ 0x400u) - 0x400;
    int32_t y = (int32_t)(((word >> 16) & 0x7ffu) ^ 0x400u) - 0x400;
    v->x16 = x * 65536; v->y16 = y * 65536;
    if (!pgxp_enabled() || source >= PSX_CTX_SRC_GP1) return;
    v->source = (uint16_t)pgxp_get_precise_vertex(w->src, word, x, y, &v->x16, &v->y16, &v->sz);
    v->raw_valid = pgxp_load_precise_word(w->src, word, &v->raw_x16, &v->raw_y16, &v->raw_sz);
    v->unclamped_depth = pgxp_get_unclamped_depth(w->src, word);
    v->projection_valid = pgxp_load_projection(w->src, word, &v->projection);
}
static int r4_verify_reference(CPUState *cpu, void *user, uint32_t alpha) {
    R4VerifyCapture *c = user;
    c->entered = 1;
    uint64_t start = pt_clock_ns();
    gpu_set_command_tap(r4_verify_word, c);
    c->complete = r4_pass(cpu, (void *)c->blend, alpha);
    gpu_set_command_tap(NULL, NULL);
    c->elapsed = pt_clock_ns() - start;
    if (c->complete && !r4_verify_image(&c->image)) c->failed = 1;
    return 0; /* checkpoint restores/discards this diagnostic image */
}
static int r4_verify_private(void *user) {
    R4VerifyJob *j = user;
    uint64_t start = pt_clock_ns();
    if (psx_ctx_begin(j->hook.context, j->snapshot)) {
        worker_job = &j->hook;
        j->complete = r4_pass(psx_ctx_cpu(j->hook.context), (void *)j->blend, j->alpha);
        worker_job = NULL;
    }
    j->elapsed = pt_clock_ns() - start;
    return 0;
}
typedef struct R4VerifyReplay {
    const GpuReplayState *gpu;
    R4VerifyJob *job;
    R4VerifyImage image;
    int complete;
} R4VerifyReplay;
static int r4_verify_replay(CPUState *cpu, void *user, uint32_t alpha) {
    (void)cpu; (void)alpha;
    R4VerifyReplay *r = user;
    GpuReplayProvider provider = {0};
    provider.user = &r->job->hook;
    provider.count = r->job->hook.context->gpu_n;
    provider.word = r4_worker_word; provider.read = r4_worker_read;
    provider.prepare_metadata = r4_worker_metadata; provider.finish = r4_worker_finish;
    r->complete = gpu_replay_execute(r->gpu, &provider);
    if (r->complete && !r4_verify_image(&r->image)) r->complete = 0;
    return 0; /* restore the same initial VRAM after capturing the replay */
}
static void r4_verify_crop(const R4VerifyImage *image, size_t first, const char *path) {
    uint32_t x=(uint32_t)(first%image->width), y=(uint32_t)(first/image->width);
    x=x>128?x-128:0; y=y>128?y-128:0;
    uint32_t w=image->width-x, h=image->height-y;
    if(w>1024) w=1024; if(h>1024) h=1024;
    FILE *f=fopen(path,"wb"); if(!f) return;
    fprintf(f,"P6\n# source crop %u %u\n%u %u\n255\n",x,y,w,h);
    for(uint32_t row=0;row<h;row++) for(uint32_t col=0;col<w;col++)
        fwrite(image->rgba+((size_t)(y+row)*image->width+x+col)*4,1,3,f);
    fclose(f);
}
static int r4_verify_pixels(const R4VerifyImage *a, const R4VerifyImage *b, const char *label) {
    if (!a->bytes || a->bytes != b->bytes || a->width != b->width ||
        a->height != b->height || a->wide != b->wide) {
        fprintf(stderr, "R4 exact pixels %s: unavailable or unequal capture geometry %ux%u/%ux%u wide=%d/%d bytes=%zu/%zu\n",
                label, a->width, a->height, b->width, b->height, a->wide, b->wide, a->bytes, b->bytes);
        return 0;
    }
    uint64_t ah = 1469598103934665603ull, bh = ah;
    size_t different = 0, first = SIZE_MAX;
    uint32_t minx=a->width,miny=a->height,maxx=0,maxy=0;
    for (size_t i = 0; i < a->bytes; ++i) {
        ah = (ah ^ a->rgba[i]) * 1099511628211ull;
        bh = (bh ^ b->rgba[i]) * 1099511628211ull;
    }
    for (size_t i = 0; i < a->bytes; i += 4) {
        if (!memcmp(a->rgba + i, b->rgba + i, 4)) continue;
        if (first == SIZE_MAX) first = i / 4;
        uint32_t x=(uint32_t)((i/4)%a->width), y=(uint32_t)((i/4)/a->width);
        if(x<minx)minx=x; if(y<miny)miny=y; if(x>maxx)maxx=x; if(y>maxy)maxy=y;
        ++different;
    }
    fprintf(stderr, "R4 exact pixels %s: %s %ux%u wide=%d different=%zu first=%zu hash=%016llX/%016llX\n",
            label, different ? "FAIL" : "PASS", a->width, a->height, a->wide, different, first,
            (unsigned long long)ah, (unsigned long long)bh);
    if(different) {
        fprintf(stderr,"R4 exact pixel bounds %s: %u,%u..%u,%u\n",label,minx,miny,maxx,maxy);
        const char *prefix=!strcmp(label,"full/full")?"full-full":"full-private";
        char path[80]; snprintf(path,sizeof path,"%s-reference.ppm",prefix); r4_verify_crop(a,first,path);
        snprintf(path,sizeof path,"%s-candidate.ppm",prefix); r4_verify_crop(b,first,path);
    }
    return different == 0;
}
static int r4_verify_equal(const PsxCtxGpuWord *expected, size_t count,
                           R4VerifyJob *job, const char *label) {
    size_t actual_count = 0;
    const PsxCtxGpuWord *actual = psx_ctx_gpu_words(job->hook.context, &actual_count);
    if (!job->complete || actual_count != count) {
        uint32_t pc = 0; const char *reason = NULL;
        PsxCtxStatus status = psx_ctx_status(job->hook.context, &pc, &reason);
        fprintf(stderr, "R4 exact check %s: complete=%d words=%zu expected=%zu status=%d pc=%08X reason=%s\n",
                label, job->complete, actual_count, count, status, pc, reason ? reason : "none");
        return 0;
    }
    for (size_t i = 0; i < count; ++i) {
        if (!memcmp(&expected[i], &actual[i], sizeof expected[i])) continue;
        fprintf(stderr, "R4 exact check %s: mismatch=%zu word=%08X/%08X src=%08X/%08X precision=%u/%u xy=%d,%d/%d,%d\n",
                label, i, expected[i].word, actual[i].word, expected[i].src, actual[i].src,
                expected[i].vertex.source, actual[i].vertex.source,
                expected[i].vertex.x16, expected[i].vertex.y16, actual[i].vertex.x16, actual[i].vertex.y16);
        return 0;
    }
    return 1;
}
/* Return 1 after an attempted diagnostic: caller skips normal submission for
 * this tick. Return 0 when disabled or not yet at a supported render-pass point. */
static int r4_verify_draw(CPUState *cpu, const R4Blend *blend, const PSXModRenderPass *rect) {
    static int done;
    const char *opt = getenv("R4_VERIFY_DRAW");
    if (done || !opt || !*opt || !strcmp(opt, "0") ||
        psx_mod_render_pass_status() != PSX_MOD_RENDER_PASS_READY) return 0;
    if (workers.pending) { r4_workers_poll(NULL); return 1; }
    uint32_t planned[R4_MAX_PASSES];
    /* The renderer must open a real generation, exactly as the serial path
     * does. Queued callback completion alone cannot attest GL admission. */
    if (!psx_mod_render_pass_plan(2u, 1u, planned, R4_MAX_PASSES)) return 1;
    done = 1;
    R4VerifyJob jobs[5] = {0};
    R4VerifyCapture reference = {0};
    R4VerifyCapture control = {0};
    PsxCtxSnapshot *snapshot = NULL;
    GpuReplayState *gpu = NULL;
    R4VerifyReplay replay = {0};
    int ok = 0, control_ok = 0;
    if (!r4_workers_init() || workers.pending) goto cleanup;
    uint64_t start = pt_clock_ns();
    snapshot = psx_ctx_snapshot_capture(cpu, PSX_CTX_SNAP_PGXP);
    double snapshot_ms = (pt_clock_ns() - start) / 1000000.0;
    gpu = gpu_replay_capture();
    if (!snapshot || !gpu) goto cleanup;
    for (int i = 0; i < 5; ++i) {
        jobs[i].snapshot = snapshot; jobs[i].blend = blend; jobs[i].alpha = 32768;
        jobs[i].hook.context = psx_ctx_create();
        jobs[i].hook.mods = r4_draw_mods_capture();
        if (!jobs[i].hook.context || !jobs[i].hook.mods) goto cleanup;
    }
    reference.blend = blend;
    PSXModRenderPass pass = *rect; pass.alpha_q16 = 32768;
    (void)psx_mod_render_pass(cpu, &pass, r4_verify_reference, &reference);
    /* A checkpoint fault may longjmp past the callback cleanup. */
    gpu_set_command_tap(NULL, NULL); R.in_pass = 0;
    if (!reference.entered || !reference.complete || reference.failed || !reference.count) goto cleanup;
    /* An identical second full draw distinguishes transaction/renderer state
     * leakage from a private replay difference. It is discarded identically. */
    control.blend = blend;
    (void)psx_mod_render_pass(cpu, &pass, r4_verify_reference, &control);
    gpu_set_command_tap(NULL, NULL); R.in_pass = 0;
    control_ok = control.entered && control.complete && !control.failed &&
        control.count == reference.count &&
        !memcmp(control.words, reference.words, reference.count * sizeof *reference.words);
    fprintf(stderr, "R4 exact full/full receipts: %s words=%zu/%zu complete=%d capture_failed=%d\n",
            control_ok ? "PASS" : "FAIL", reference.count, control.count, control.complete, control.failed);
    if (!r4_verify_pixels(&reference.image, &control.image, "full/full")) control_ok = 0;
    free(control.words); control.words = NULL;
    free(control.image.rgba); control.image.rgba = NULL;
    fflush(stderr);
    r4_verify_private(&jobs[0]);
    if (jobs[0].complete) {
        replay.gpu = gpu; replay.job = &jobs[0];
        (void)psx_mod_render_pass(cpu, &pass, r4_verify_replay, &replay);
        R.in_pass = 0;
    }
    SDL_Thread *threads[4] = {0};
    start = pt_clock_ns();
    for (int i = 0; i < 4; ++i) threads[i] = SDL_CreateThread(r4_verify_private, "r4-exact-check", &jobs[i + 1]);
    for (int i = 0; i < 4; ++i) if (threads[i]) SDL_WaitThread(threads[i], NULL);
    double parallel_ms = (pt_clock_ns() - start) / 1000000.0;
    ok = r4_verify_equal(reference.words, reference.count, &jobs[0], "full/private");
    if (!control_ok) ok = 0;
    if (!replay.complete) {
        fprintf(stderr, "R4 exact pixels: replay/capture incomplete GPU error=%d\n", gpu_replay_last_error());
        ok = 0;
    } else if (!r4_verify_pixels(&reference.image, &replay.image, "full/private")) ok = 0;
    size_t serial_count = 0;
    const PsxCtxGpuWord *serial = psx_ctx_gpu_words(jobs[0].hook.context, &serial_count);
    for (int i = 1; i < 5; ++i) {
        char label[32]; snprintf(label, sizeof label, "serial/worker%d", i);
        if (!threads[i - 1] || !r4_verify_equal(serial, serial_count, &jobs[i], label)) ok = 0;
    }
    fprintf(stderr, "R4 exact check: %s mode=%d alpha=32768 words=%zu snapshot_ms=%.3f full_ms=%.3f private_ms=%.3f four_wall_ms=%.3f\n",
            ok ? "PASS" : "FAIL", blend->mode, reference.count, snapshot_ms,
            reference.elapsed / 1000000.0, jobs[0].elapsed / 1000000.0, parallel_ms);
cleanup:
    if (!ok) fprintf(stderr, "R4 exact check: verification incomplete or unequal (reference entered=%d complete=%d capture_failed=%d)\n",
                     reference.entered, reference.complete, reference.failed);
    for (int i = 0; i < 5; ++i) {
        r4_draw_mods_destroy(jobs[i].hook.mods); psx_ctx_destroy(jobs[i].hook.context);
    }
    psx_ctx_snapshot_release(snapshot); gpu_replay_release(gpu); free(reference.words);
    free(reference.image.rgba); free(replay.image.rgba);
    free(control.words); free(control.image.rgba);
    fflush(stderr);
    return 1;
}
#else
static int r4_verify_draw(CPUState *cpu, const R4Blend *blend, const PSXModRenderPass *rect) {
    (void)cpu; (void)blend; (void)rect; return 0;
}
#endif
