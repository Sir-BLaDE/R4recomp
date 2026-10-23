/* Exact diagnostic for the existing interpolation recipe. Include after
 * r4_interp_workers.h; debug builds only. No result is admitted to presentation. */
#ifndef PSX_NO_DEBUG_TOOLS
#include "gpu.h"

typedef struct R4VerifyCapture {
    PsxCtxGpuWord *words;
    size_t count, capacity;
    const R4Blend *blend;
    uint32_t alpha;
    int failed, entered, complete;
    uint64_t elapsed;
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
    done = 1;
    R4VerifyJob jobs[5] = {0};
    R4VerifyCapture reference = {0};
    PsxCtxSnapshot *snapshot = NULL;
    int ok = 0;
    if (!r4_workers_init() || workers.pending) goto cleanup;
    uint64_t start = pt_clock_ns();
    snapshot = psx_ctx_snapshot_capture(cpu, PSX_CTX_SNAP_PGXP);
    double snapshot_ms = (pt_clock_ns() - start) / 1000000.0;
    if (!snapshot) goto cleanup;
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
    r4_verify_private(&jobs[0]);
    SDL_Thread *threads[4] = {0};
    start = pt_clock_ns();
    for (int i = 0; i < 4; ++i) threads[i] = SDL_CreateThread(r4_verify_private, "r4-exact-check", &jobs[i + 1]);
    for (int i = 0; i < 4; ++i) if (threads[i]) SDL_WaitThread(threads[i], NULL);
    double parallel_ms = (pt_clock_ns() - start) / 1000000.0;
    ok = r4_verify_equal(reference.words, reference.count, &jobs[0], "full/private");
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
    psx_ctx_snapshot_release(snapshot); free(reference.words);
    return 1;
}
#else
static int r4_verify_draw(CPUState *cpu, const R4Blend *blend, const PSXModRenderPass *rect) {
    (void)cpu; (void)blend; (void)rect; return 0;
}
#endif
