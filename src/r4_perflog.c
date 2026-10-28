/*
 * r4.perflog: a small performance log the player can send back.
 *
 * Measured over 1-second windows (60 guest VBlanks):
 *   late  host VBlanks that arrived > 20 ms after the previous one (the
 *         emulator could not keep up: host-side slowdown)
 *   fps   frames the game itself finished (display-buffer flips). With the
 *         60 FPS patch this is ~60 in a race; a drop with no late VBlanks means
 *         the GAME ran out of guest CPU time (guest-side slowdown, cured by a
 *         higher CPU overclock, not by a faster PC)
 *   emu   busy share of the emulation thread (CPU time / wall time): near
 *         100% with late VBlanks = CPU-bound; low with late VBlanks = waiting
 *         on the GPU / render thread
 *   interp + top: run-time code the dirty-RAM interpreter ran (no compiled
 *         copy), hottest addresses first
 *
 * A line is appended to R4_perf_log.txt (next to the executable) for every
 * window with late VBlanks or a partial frame-rate drop (32..56 fps; steady 30 fps menus and movies are not drops), capped
 * at 20000 lines per session. R4_PERFLOG_ALL=1 logs every window.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#if defined(_WIN32)
#include <windows.h>
#endif

#include "mod_plugins.h"
#include "dirty_ram_interp.h"
#include "gpu.h"

#define R4PL_ID          "r4.perflog"
#define R4PL_LATE_NS     20000000ull      /* 20 ms */
#define R4PL_WINDOW      60u              /* VBlanks per window (~1 s) */
#define R4PL_TOP         6
#define R4PL_MAX_LINES   20000u

static uint64_t s_last_ns, s_frame, s_window_start_frame;
static uint32_t s_late, s_window_frames, s_flips, s_lines;
static uint64_t s_worst_ns, s_sum_ns, s_insns_at_window;
static uint64_t s_cpu_at_window, s_wall_at_window;
static uint32_t s_last_disp = 0xFFFFFFFFu;
static uint64_t *s_prev_insns;            /* per PC-table slot, last window */
static FILE *s_log;
static int s_all = -1;

static uint64_t now_ns(void) {
#if defined(_WIN32)
    static LARGE_INTEGER f;
    LARGE_INTEGER c;
    if (!f.QuadPart) QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return (uint64_t)((double)c.QuadPart * 1e9 / (double)f.QuadPart);
#else
    struct timespec ts;
    timespec_get(&ts, TIME_UTC);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
#endif
}

static uint64_t thread_cpu_ns(void) {
#if defined(_WIN32)
    FILETIME c, e, k, u;
    if (!GetThreadTimes(GetCurrentThread(), &c, &e, &k, &u)) return 0;
    const uint64_t kk = ((uint64_t)k.dwHighDateTime << 32) | k.dwLowDateTime;
    const uint64_t uu = ((uint64_t)u.dwHighDateTime << 32) | u.dwLowDateTime;
    return (kk + uu) * 100ull;
#elif defined(CLOCK_THREAD_CPUTIME_ID)
    struct timespec ts;
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts)) return 0;
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
#else
    return 0;
#endif
}

static void open_log(void) {
    if (s_log) return;
    s_log = fopen("R4_perf_log.txt", "a");
    if (!s_log) return;
    time_t t = time(NULL);
    char buf[64];
    strftime(buf, sizeof buf, "%Y-%m-%d %H:%M:%S", localtime(&t));
    fprintf(s_log, "# R4Recomp perf log, session %s (cpu overclock x%u)\n"
                   "# time frame late/vblanks worst avg fps emu%% emu_ms(per vblank) interp top\n",
            buf, psx_mod_guest_cycle_scale());
    fflush(s_log);
}

static void sample_top(uint32_t top_pc[R4PL_TOP], uint64_t top_n[R4PL_TOP]) {
    if (!s_prev_insns)
        s_prev_insns = (uint64_t *)calloc(DIRTY_RAM_PC_TABLE_SIZE, sizeof(uint64_t));
    if (!s_prev_insns) return;
    for (uint32_t i = 0; i < DIRTY_RAM_PC_TABLE_SIZE; i++) {
        const DirtyRamPcEntry *e = &g_dirty_ram_pc_table[i];
        if (!e->pc) continue;
        const uint64_t d = e->insns - s_prev_insns[i];
        s_prev_insns[i] = e->insns;
        if (d <= top_n[R4PL_TOP - 1]) continue;
        int k = R4PL_TOP - 1;
        while (k > 0 && d > top_n[k - 1]) {
            top_n[k] = top_n[k - 1];
            top_pc[k] = top_pc[k - 1];
            k--;
        }
        top_n[k] = d;
        top_pc[k] = e->pc;
    }
}

static void end_window(uint64_t wall_now) {
    if (s_all < 0) { const char *e = getenv("R4_PERFLOG_ALL"); s_all = e && e[0] == '1'; }
    uint32_t top_pc[R4PL_TOP] = {0};
    uint64_t top_n[R4PL_TOP] = {0};
    sample_top(top_pc, top_n);                  /* always: keeps the baseline current */
    const uint64_t cpu = thread_cpu_ns();
    const uint64_t wall = wall_now - s_wall_at_window;
    const double emu = (wall && cpu) ? 100.0 * (double)(cpu - s_cpu_at_window) / (double)wall : 0.0;
    const uint64_t s_cpu_prev = s_cpu_at_window;
    s_cpu_at_window = cpu;
    s_wall_at_window = wall_now;
    const int partial = s_flips >= 32u && s_flips <= 56u;   /* 30 fps menus/FMV excluded */
    if (!(s_late || partial || s_all) || s_lines >= R4PL_MAX_LINES) return;
    open_log();
    if (!s_log) return;
    time_t t = time(NULL);
    char ts[16];
    strftime(ts, sizeof ts, "%H:%M:%S", localtime(&t));
    fprintf(s_log, "%s frame=%llu late=%u/%u worst=%.1fms avg=%.1fms fps=%u emu=%.0f%% emu_ms=%.2f interp=%llu top=",
            ts, (unsigned long long)s_window_start_frame, s_late, s_window_frames,
            s_worst_ns / 1e6, s_window_frames ? s_sum_ns / 1e6 / s_window_frames : 0.0,
            s_flips, emu, s_window_frames ? (double)(cpu - s_cpu_prev) / 1e6 / s_window_frames : 0.0,
            (unsigned long long)(g_dirty_ram_insns_run - s_insns_at_window));
    for (int k = 0; k < R4PL_TOP && top_n[k]; k++)
        fprintf(s_log, "%s%08X:%llu", k ? "," : "", top_pc[k] | 0x80000000u,
                (unsigned long long)top_n[k]);
    fputc('\n', s_log);
    fflush(s_log);
    s_lines++;
}

static void r4pl_vblank(void) {
    const uint64_t t = now_ns();
    s_frame++;
    GpuDisplayInfo di;
    gpu_get_display_info(&di);
    const uint32_t disp = di.display_x | (di.display_y << 16);
    if (disp != s_last_disp) { s_flips++; s_last_disp = disp; }
    if (s_last_ns) {
        const uint64_t dt = t - s_last_ns;
        if (dt < 5000000000ull) {          /* ignore pauses / long loads */
            s_sum_ns += dt;
            if (dt > R4PL_LATE_NS) s_late++;
            if (dt > s_worst_ns) s_worst_ns = dt;
        }
    }
    s_window_frames++;
    s_last_ns = t;
    if (s_window_frames >= R4PL_WINDOW) {
        end_window(t);
        s_late = s_window_frames = s_flips = 0;
        s_worst_ns = s_sum_ns = 0;
        s_insns_at_window = g_dirty_ram_insns_run;
        s_window_start_frame = s_frame;
    }
}

static void r4pl_activate(void) {
    if (!s_prev_insns)
        s_prev_insns = (uint64_t *)calloc(DIRTY_RAM_PC_TABLE_SIZE, sizeof(uint64_t));
    if (s_prev_insns)
        for (uint32_t i = 0; i < DIRTY_RAM_PC_TABLE_SIZE; i++)
            s_prev_insns[i] = g_dirty_ram_pc_table[i].insns;
    s_last_ns = 0;
    s_late = s_window_frames = s_flips = 0;
    s_worst_ns = s_sum_ns = 0;
    s_insns_at_window = g_dirty_ram_insns_run;
    s_cpu_at_window = thread_cpu_ns();
    s_wall_at_window = now_ns();
}

static void r4pl_restore(void) { s_last_ns = 0; }

PSX_MOD_CONSTRUCTOR(r4pl_register_plugin) {
    psx_mod_register_activation_plugin(R4PL_ID, r4pl_activate);
    psx_mod_register_vblank_plugin(R4PL_ID, r4pl_vblank);
    psx_mod_register_savestate_plugin(R4PL_ID, r4pl_restore);
}
