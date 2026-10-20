/* r4.pal.ntsc: PAL-only helpers other mods may call (PAL builds only, R4_REGION_PAL). */
#ifndef R4_PAL_NTSC_H
#define R4_PAL_NTSC_H

#ifdef __cplusplus
extern "C" {
#endif

/* The game's current message language byte: 0 English, 1 French, 2 German, 3 Spanish,
 * 4 Italian (values above 4 are returned as read). */
int r4_pal_message_language(void);

#ifdef __cplusplus
}
#endif

#endif /* R4_PAL_NTSC_H */
