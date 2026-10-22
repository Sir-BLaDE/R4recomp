/* Car effects (r4_car_effects.cpp), drawn from the race HUD's host layer
 * (r4_race_hud.cpp). */
#ifndef R4_CAR_EFFECTS_H
#define R4_CAR_EFFECTS_H

struct ImDrawList;

/* 1 while the r4.car-effects plugin is active in the running plan. */
bool r4_car_effects_active();

/* Draws the presented frame's effects into dl (window pixels W x H). */
void r4_car_effects_draw(ImDrawList *dl, int W, int H, bool split_screen);

/* Outside a race: neutral live values for the lighting chain. */
void r4_car_effects_off_race();

#endif
