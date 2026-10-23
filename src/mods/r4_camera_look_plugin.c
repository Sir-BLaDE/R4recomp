/* Local right-stick camera look for R4's single-player race cameras. */
#include "mod_plugins.h"
#include "cpu_state.h"
#include "r4_camera_look.h"
#include "r4_widescreen_scene.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef R4_THREADED_DRAW
#include "r4_draw_mods.h"
#endif

#define PKG "r4.enhancement.camera-lookaround"
#define FEATURE "camera-lookaround"
#define PLUGIN_ID "r4.camera-lookaround"

#define R4_CAMERA_BUILDER     0x8006E4D0u
#define R4_RACE_PAUSED        0x800F4E18u
#define R4_CAMERA_INPUT_POS   0x1F800008u
#define R4_CAMERA_INPUT_PITCH 0x1F800018u
#define R4_CAMERA_INPUT_YAW   0x1F80001Cu
#define R4_CAR_WORLD_POS      0x800AC0C0u

static int s_hooks_registered;
static float s_deadzone = R4_CAMERA_LOOK_DEFAULT_DEADZONE;
static float s_sensitivity = 1.0f;
typedef struct {
    int enabled, restore_pending;
    R4CameraLookState look;
    uint32_t original[5], written[5];
} R4CameraState;
static R4CameraState s_main;
#ifdef R4_THREADED_DRAW
struct R4CameraDrawState { R4CameraState state; PsxExecCtx *ctx; };
static _Thread_local R4CameraDrawState *s_private;
static R4CameraState *camera_state(void) { return s_private ? &s_private->state : &s_main; }
#else
static R4CameraState *camera_state(void) { return &s_main; }
#endif
#define s_enabled (camera_state()->enabled)
#define s_look (camera_state()->look)
#define s_restore_pending (camera_state()->restore_pending)
#define s_original (camera_state()->original)
#define s_written (camera_state()->written)

static const uint32_t k_camera_inputs[5] = {
    R4_CAMERA_INPUT_POS + 0u, R4_CAMERA_INPUT_POS + 4u, R4_CAMERA_INPUT_POS + 8u,
    R4_CAMERA_INPUT_PITCH, R4_CAMERA_INPUT_YAW,
};


static uint32_t rd32(uint32_t address) {
#ifdef R4_THREADED_DRAW
    if (s_private) return psx_ctx_read32(s_private->ctx, address);
#endif
    return psx_mod_read_word(address);
}
static uint16_t rd16(uint32_t address) {
#ifdef R4_THREADED_DRAW
    if (s_private) return (uint16_t)(rd32(address & ~3u) >> ((address & 2u)*8u));
#endif
    return psx_mod_read_half(address);
}
static uint8_t rd8(uint32_t address) {
#ifdef R4_THREADED_DRAW
    if (s_private) return (uint8_t)(rd32(address & ~3u) >> ((address & 3u)*8u));
#endif
    return psx_mod_read_byte(address);
}
static void wr32(uint32_t address,uint32_t value) {
#ifdef R4_THREADED_DRAW
    if (s_private) { psx_ctx_write32(s_private->ctx,address,value); return; }
#endif
    psx_mod_write_word(address,value);
}

/* Put back the guest's own inputs. The camera builder stores a fresh eye into
 * these words after its entry, so a word that no longer holds the value we
 * wrote is the guest's newer state and stays; restoring it would pin the
 * chase eye to last frame's position. */
static void r4_camera_look_restore_inputs(void) {
    for (unsigned i = 0; i < 5; ++i)
        if (rd32(k_camera_inputs[i]) == s_written[i])
            wr32(k_camera_inputs[i], s_original[i]);
    s_restore_pending = 0;
}

static void r4_camera_look_option(const char *id, float fallback,
                                 float min_value, float max_value,
                                 float *out) {
    char value[32];
    if (!psx_mod_option_value(PKG, FEATURE, id, value, sizeof(value))) {
        *out = fallback;
        return;
    }
    char *end = NULL;
    const float parsed = strtof(value, &end);
    if (end == value || *end != '\0' || parsed < min_value ||
        parsed > max_value) {
        *out = fallback;
        return;
    }
    *out = parsed;
}

static int r4_camera_look_live(void) {
    const uint32_t phase = rd32(R4_RACE_PHASE_ADDR);
    const uint32_t handler =
        r4_frame_handler(rd32, rd16);
    const int single_player_handler =
        (handler == 0x8011729Cu || handler == 0x80114A38u) &&
        r4_is_race_handler(rd32, handler);
    return r4_camera_look_scene_eligible(
        phase, rd8(R4_RACE_PAUSED), single_player_handler);
}

static void r4_camera_look_activate(void) {
    s_enabled = 1;
    s_look.yaw_radians = 0.0f;
    s_look.pitch_radians = 0.0f;
    s_restore_pending = 0;
    r4_camera_look_option("deadzone", 18.0f, 10.0f, 35.0f,
                          &s_deadzone);
    r4_camera_look_option("sensitivity", 100.0f, 60.0f, 140.0f,
                          &s_sensitivity);
    s_deadzone *= 0.01f;
    s_sensitivity *= 0.01f;
    fprintf(stdout,
            "[r4-camera-lookaround] active: hooks=%d deadzone=%.0f%% sensitivity=%.0f%%\n",
            s_hooks_registered, s_deadzone * 100.0f,
            s_sensitivity * 100.0f);
}

/* Update only on simulated VBlank. Extra redraws at a different present rate
 * reuse the same angle and cannot make the camera move faster. */
static void r4_camera_look_vblank(void) {
    if (!s_enabled || !r4_camera_look_live()) {
        if (!s_restore_pending) {
            s_look.yaw_radians = 0.0f;
            s_look.pitch_radians = 0.0f;
        }
        return;
    }

    uint8_t sticks[4] = { 0x80, 0x80, 0x80, 0x80 };
    float target_yaw = 0.0f;
    float target_pitch = 0.0f;
    if (psx_mod_read_local_pad_sticks(0, sticks))
        r4_camera_look_target(sticks[2], sticks[3], s_deadzone,
                              s_sensitivity, &target_yaw, &target_pitch);
    r4_camera_look_step(&s_look, target_yaw, target_pitch, 1.0f / 60.0f);
}

/* The following guest function builds the actual view matrix from these
 * scratchpad inputs. The car draw starts at 0x8002E554 and its GTE work runs
 * below that entry, so restoring the eye there discards the orbit translation
 * before the player car is transformed. Keep the override through the draw;
 * restore it at the next camera-state update entry, before the guest rewrites
 * the per-frame eye. */
static void r4_camera_look_build(CPUState *cpu, uint32_t address) {
    (void)cpu;
    (void)address;
    if (!s_enabled || !r4_camera_look_live()) return;
    if (s_restore_pending) {
        /* Fail-safe for an unexpected camera call sequence. */
        r4_camera_look_restore_inputs();
    }
    if (fabsf(s_look.yaw_radians) < 0.00001f &&
        fabsf(s_look.pitch_radians) < 0.00001f)
        return;

    for (unsigned i = 0; i < 3; ++i)
        s_original[i] = rd32(R4_CAMERA_INPUT_POS + 4u * i);
    s_original[3] = rd32(R4_CAMERA_INPUT_PITCH);
    s_original[4] = rd32(R4_CAMERA_INPUT_YAW);

    R4CameraLookInput camera = {
        (int32_t)s_original[0], (int32_t)s_original[1],
        (int32_t)s_original[2], s_original[3] & 0xFFFu,
        s_original[4] & 0xFFFu,
    };
    (void)r4_camera_look_adjust(&s_look,
        (int32_t)rd32(R4_CAR_WORLD_POS + 0u),
        (int32_t)rd32(R4_CAR_WORLD_POS + 4u),
        (int32_t)rd32(R4_CAR_WORLD_POS + 8u), &camera);

    s_written[0] = (uint32_t)camera.camera_x;
    s_written[1] = (uint32_t)camera.camera_y;
    s_written[2] = (uint32_t)camera.camera_z;
    /* The guest keeps these angles sign-extended (pitch is often slightly
     * negative), so apply the change to the original word; never rewrite it
     * masked to 12 bits. */
    s_written[3] = r4_camera_look_apply_angle(s_original[3], camera.pitch_angle12);
    s_written[4] = r4_camera_look_apply_angle(s_original[4], camera.yaw_angle12);
    for (unsigned i = 0; i < 5; ++i)
        wr32(k_camera_inputs[i], s_written[i]);
    s_restore_pending = 1;
}

static void r4_camera_look_restore(CPUState *cpu, uint32_t address) {
    (void)cpu;
    (void)address;
    if (!s_restore_pending) return;
    r4_camera_look_restore_inputs();
}

/* In-game menu (psxrecomp P5): deadzone and sensitivity only scale the right
 * stick; re-read them on a running game. */
static int r4_camera_look_option_changed(const char *option_id, const char *value) {
    (void)value;
    if (strcmp(option_id, "deadzone") && strcmp(option_id, "sensitivity")) return 0;
    r4_camera_look_option("deadzone", 18.0f, 10.0f, 35.0f, &s_deadzone);
    r4_camera_look_option("sensitivity", 100.0f, 60.0f, 140.0f, &s_sensitivity);
    s_deadzone *= 0.01f;
    s_sensitivity *= 0.01f;
    return 1;
}

PSX_MOD_CONSTRUCTOR(r4_camera_look_register) {
    (void)psx_mod_register_activation_plugin(PLUGIN_ID,
                                             r4_camera_look_activate);
    (void)psx_mod_register_vblank_plugin(PLUGIN_ID,
                                        r4_camera_look_vblank);
    (void)psx_mod_register_option_changed_plugin(PLUGIN_ID,
                                                 r4_camera_look_option_changed);
    s_hooks_registered += psx_mod_register_function_entry_plugin(
        PLUGIN_ID, R4_CAMERA_BUILDER, r4_camera_look_build);
    s_hooks_registered += psx_mod_register_function_entry_plugin(
        PLUGIN_ID, R4_CAMERA_LOOK_INPUT_RESTORE_ENTRY, r4_camera_look_restore);
}

#ifdef R4_THREADED_DRAW
R4CameraDrawState *r4_camera_draw_capture(void) {
    R4CameraDrawState *p=calloc(1,sizeof *p);
    if(p) p->state=s_main;
    return p;
}
int r4_camera_draw_entry(R4CameraDrawState *p, CPUState *cpu,uint32_t address) {
    if(!p || !cpu || !cpu->ctx) return 0;
    R4CameraDrawState *prior=s_private; s_private=p; p->ctx=cpu->ctx;
    if(address==R4_CAMERA_BUILDER) r4_camera_look_build(cpu,address);
    if(address==R4_CAMERA_LOOK_INPUT_RESTORE_ENTRY) r4_camera_look_restore(cpu,address);
    s_private=prior; return 1;
}
int r4_camera_draw_register_entries(PsxCtxEntryHook callback,void *user) {
    return r4_draw_mods_register_one(R4_CAMERA_BUILDER,callback,user) &&
           r4_draw_mods_register_one(R4_CAMERA_LOOK_INPUT_RESTORE_ENTRY,callback,user);
}
void r4_camera_draw_destroy(R4CameraDrawState *p) { free(p); }
#endif
