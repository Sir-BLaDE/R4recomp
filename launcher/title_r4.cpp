// title_r4.cpp — recomp-launcher title layer for R4Recomp: R4 Ridge Racer
// Type 4 (Japan, SLPS-01798) with the Spanish text pack. Adapted from
// tetrisgm/RidgeRacerType4Recomp (MIT). Built into the launcher through
// R4L_TITLE_SOURCE (CMakeLists.txt).
#include "r4l/title.h"

#include "imgui.h"
#include "r4l/core/discfs.h"
#include "r4l/core/session.h"
#include "iso_reader.h"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>

#include <cmath>

#define R4_DISC_SERIAL "SLPS-01798"

namespace r4l {
namespace {

const ControllerProfile kControllers[] = {
    {"dualshock", "DualShock", "Analog sticks and triggers. Best with a modern gamepad.", 1,
     {nullptr, nullptr}},
    {"digital", "Digital pad", "The original PlayStation pad, no sticks.", 2, {nullptr, nullptr}},
    {"negcon", "NeGcon", "Twist steering and analog pedals, mapped from a gamepad.", 1,
     {nullptr, nullptr}},
    {"jogcon", "JogCon", "Namco's force-feedback dial (native JogCon support of the JP disc).", 1,
     {nullptr, nullptr}},
};

const FeatureRef kGraphicsFeatures[] = {
    {"r4.gameshark", "widescreen"},
    {"r4.gameshark", "60fps"},
    {"r4.enhancement.max-detail", "max-detail"},
    {"psx.enhancement.pgxp", "pgxp"},
};

const TitleNotice kNotices[] = {
    {"HD HUD (T4HDHUD)",
     "The bundled HD HUD pack is HD HUD by Kuid0us, with the palette variants and "
     "glyph repairs of RidgeRacerType4Recomp. Credit to Kuid0us.",
     "https://github.com/Kuid0us/T4HDHUD"},
    {"RidgeRacerType4Recomp",
     "Max Detail, the launcher title layer and the HD HUD pack tooling come from "
     "tetrisgm/RidgeRacerType4Recomp (MIT).",
     "https://github.com/tetrisgm/RidgeRacerType4Recomp"},
    {"GameShark 60FPS + Widescreen Patch V2",
     "60 FPS and 16:9 are the community GameShark codes, applied as mod plugins.",
     nullptr},
    {"Lato",
     "LatoLatin Regular and Bold. Copyright (c) 2010-2015 Lukasz Dziedzic, with Reserved "
     "Font Name \"Lato\". Licensed under the SIL Open Font License 1.1.",
     "https://scripts.sil.org/OFL"},
    {"Dear ImGui", "Copyright (c) 2014-2026 Omar Cornut. MIT License.",
     "https://github.com/ocornut/imgui"},
    {"psxrecomp", "Static recompilation framework for PlayStation titles. MIT License.",
     "https://github.com/RetroPortingToolKit/psxrecomp"},
    {"Ridge Racer Type 4",
     "R4: Ridge Racer Type 4 is a trademark of Bandai Namco Entertainment. This project "
     "ships no game data; you supply your own disc.",
     nullptr},
};

// R4's surfacing decisions (docs/SUPPORTED.md): as few rows as possible,
// everything else automatic. Undeclared keys follow the default rule.
const SurfaceRule kSurface[] = {
    // Graphics: the preset (Auto = detected Low..Ultra) and screen mode.
    {"graphics.preset", Vis::Shown, "auto"},
    {"graphics.redetect", Vis::Hidden, nullptr},          // Auto re-detects
    // Smooth motion is removed from R4 (owner, 2026-10-20): not drawn, pinned off.
    {"graphics.frame_generation", Vis::Auto, "0"},
    {"graphics.fullscreen", Vis::Shown, nullptr},
    {"graphics.dynamic_resolution", Vis::Auto, nullptr}, // the preset decides
    {"graphics.internal_resolution", Vis::Shown, nullptr}, // the preset seeds it; the row stays selectable
    {"graphics.title_features", Vis::Hidden, nullptr},    // widescreen Fit / max detail stay on
    // Controls: Modern / Classic and rebinding.
    {"controls.scheme", Vis::Shown, nullptr},
    {"controls.bindings", Vis::Shown, nullptr},
    {"controls.devices", Vis::Shown, nullptr},
    {"controls.assist", Vis::Hidden, nullptr},
    // Add to Steam (owner, 2026-10-28): a Steam Controller is a gamepad only in
    // a game Steam launched; the button registers R4 as a non-Steam game.
    {"controls.steam", Vis::Shown, nullptr},
    // Owner 2026-10-12: experimental JogCon wheel force feedback is a player
    // toggle, off by default (settings.toml jogcon_force_feedback). Needs a
    // launcher pin with tetrisgm/recomp-launcher#1; older pins ignore the key.
    {"controls.force_feedback", Vis::Shown, nullptr},
    // Disc: found automatically; OpenBIOS is bundled, so no BIOS prompt.
    {"disc.autoscan", Vis::Auto, "auto"},
    // No pre-game window; disc setup, netplay and options live in the
    // in-game menu (Esc / Guide / Select / Start+Select). --launcher brings
    // back the pre-game window.
    {"launcher.in_game", Vis::Auto, "auto"},
    // The menu is the first screen; Resume starts the race (owner,
    // 2026-10-27). --no-launcher / skip_launcher boot straight in.
    {"launcher.boot_menu", Vis::Auto, "auto"},
    // Select alone opens the menu: R4 has no use for Select on its own
    // (owner, 2026-10-28). Select + button shortcuts still work.
    {"launcher.select_menu", Vis::Auto, "auto"},
    // The menu opens on a main screen: Start Game / Resume Game, Save State,
    // Load State, Options (the other pages, with Back), Quit game; a first
    // run with no disc offers Select Disc only (owner, 2026-10-28).
    {"launcher.main_screen", Vis::Auto, "auto"},
    {"disc.toolchain", Vis::Hidden, nullptr},
    {"bios.select", Vis::Hidden, nullptr},
    // Settings page: volume only; memory cards use the default cards.
    {"system.memcards", Vis::Hidden, nullptr},
    {"system.language", Vis::Hidden, nullptr},
    // Netplay: host and join (lobby, chat, seats are essentials by default).
    {"netplay.host", Vis::Shown, nullptr},
    {"netplay.join", Vis::Shown, nullptr},
    {"netplay.spectators", Vis::Hidden, nullptr},  // owner: few options; spectating still works underneath
    // Mods: shown, simple (no package view, versions or resource pickers).
    {"mods.list", Vis::Shown, nullptr},
    {"mods.install", Vis::Shown, nullptr},
    {"about.updates", Vis::Hidden, nullptr},
};

// Disc-sourced skin art: the "R4 RIDGE RACER TYPE 4" logo and the menu
// font, read from R4.BIN on the player's own disc (SLUS-00797 or SCES-01706).
// Written into the local cache; nothing from the disc is ever shipped.
bool extract_r4_assets(const char* disc_path, const char* out_dir, char* err, size_t cap) {
    auto fail = [&](const std::string& m) {
        std::snprintf(err, cap, "%s", m.c_str());
        return false;
    };
    // The runtime's ISO reader: .cue/.bin, .iso and .chd (the launcher's own
    // DiscImage does not read CHD).
    std::string e;
    PS1::ISOReader iso;
    if (!iso.Open(disc_path)) return fail("cannot open the disc image");
    const size_t bin_size = iso.GetFileSize("R4.BIN");
    if (bin_size == 0) return fail("R4.BIN not found (not " R4_DISC_SERIAL "?)");
    std::vector<uint8_t> bin(bin_size);
    if (iso.ReadFile("R4.BIN", bin.data(), bin.size()) != bin_size) return fail("cannot read R4.BIN");
    // SLPS-01798: the logo sheet (same layout as the US and PAL ones) and the
    // game's bold Latin menu font (256x72: 0-9 A-K / L-Z ! ? & @ " " /
    // ' yen + - . / : ...). The JP disc has no lowercase Latin sheet, so a-z
    // reuse the capitals.
    Rgba logo_tim, font_tim;
    if (!decode_tim(bin, 0x02ecc28c, &logo_tim) || logo_tim.w != 256 || logo_tim.h != 256)
        return fail("logo image not found (not " R4_DISC_SERIAL "?)");
    if (!decode_tim(bin, 0x026a4004, &font_tim) || font_tim.w != 256 || font_tim.h != 72)
        return fail("font image not found (not " R4_DISC_SERIAL "?)");
    Rgba logo = crop(logo_tim, 34, 135, 188, 83);  // JP: the logo sits higher (text below it)
    tint(&logo, 0x77, 0x77, 0x77);  // the title menu shows the logo in grey
    logo = scale_nearest(logo, 2);
    const std::string dir = out_dir;
    if (!write_png_rgba(join_path(dir, "logo.png"), logo.w, logo.h, logo.px.data()))
        return fail("cannot write logo.png");
    Rgba font = font_tim;
    tint(&font, 0xff, 0xff, 0xff);  // white glyphs; skins tint them
    if (!write_bitmap_font(font, {{{0, 22}, "0123456789ABCDEFGHIJK"},
                                  {{24, 46}, "LMNOPQRSTUVWXYZ!?&@"},
                                  {{48, 70}, "' +-./:"}},
                           dir, "font", 22, &e))
        return fail(e);
    {
        // a-z: the capitals' glyphs.
        const std::string fnt_path = join_path(dir, "font.fnt");
        std::ifstream in(fnt_path);
        std::string line, extra;
        while (std::getline(in, line)) {
            const std::string key = "char id=";
            if (line.rfind(key, 0) != 0) continue;
            const int id = std::atoi(line.c_str() + key.size());
            if (id < 'A' || id > 'Z') continue;
            const size_t sp = line.find(' ', key.size());
            extra += key + std::to_string(id + 32) + line.substr(sp) + "\n";
        }
        in.close();
        std::ofstream(fnt_path, std::ios::app) << extra;
    }
    return true;
}

// Speed lines and a horizon: a cheap, resolution-independent hero.
void draw_hero(void* dl_v, float x0, float y0, float x1, float y1, double t) {
    ImDrawList* dl = static_cast<ImDrawList*>(dl_v);
    const float w = x1 - x0, h = y1 - y0;
    dl->AddRectFilledMultiColor(ImVec2(x0, y0), ImVec2(x1, y1), IM_COL32(18, 10, 40, 255),
                                IM_COL32(60, 12, 58, 255), IM_COL32(230, 90, 40, 255),
                                IM_COL32(20, 20, 60, 255));
    const float hy = y0 + h * 0.62f;
    dl->AddRectFilled(ImVec2(x0, hy), ImVec2(x1, y1), IM_COL32(8, 8, 18, 235));
    const ImVec2 vp(x0 + w * 0.62f, hy);
    for (int i = -9; i <= 9; ++i) {
        const float fx = vp.x + i * w * 0.12f;
        dl->AddLine(vp, ImVec2(fx, y1), IM_COL32(255, 120, 60, 70), 1.0f);
    }
    for (int i = 1; i <= 7; ++i) {
        float f = static_cast<float>(std::fmod(i / 7.0 + t * 0.25, 1.0));
        f = f * f;
        const float yy = hy + (y1 - hy) * f;
        dl->AddLine(ImVec2(x0, yy), ImVec2(x1, yy), IM_COL32(255, 120, 60, (int)(30 + 90 * f)), 1.0f);
    }
    dl->AddCircleFilled(ImVec2(vp.x, hy - h * 0.02f), h * 0.16f, IM_COL32(255, 170, 70, 200), 48);
    dl->AddRectFilled(ImVec2(x0, hy - 2), ImVec2(x1, hy), IM_COL32(255, 200, 120, 160));
}

const TitleLayer kR4 = {
    "r4",
    "R4: Ridge Racer Type 4",
    "Native PC recompilation · " R4_DISC_SERIAL,
    R4_DISC_SERIAL,
    {255, 92, 54},
    {120, 92, 255},
    4,
    4,
    {"r4.modern-controls", "modern-controls"},
    "scheme",
    "modern",
    "classic",
    kGraphicsFeatures,
    static_cast<int>(sizeof(kGraphicsFeatures) / sizeof(kGraphicsFeatures[0])),
    kControllers,
    static_cast<int>(sizeof(kControllers) / sizeof(kControllers[0])),
    kNotices,
    static_cast<int>(sizeof(kNotices) / sizeof(kNotices[0])),
    "A static recompilation of R4: Ridge Racer Type 4 (Japan, SLPS-01798) built on "
    "psxrecomp, with Spanish text, 60 FPS and 16:9 (GameShark codes), Max Detail and "
    "the HD HUD. It runs natively, with no emulator behind it.",
    kSurface,
    static_cast<int>(sizeof(kSurface) / sizeof(kSurface[0])),
    extract_r4_assets,
    draw_hero,
    "R4 Recompiled",  // Add to Steam: library name
};

}  // namespace

const TitleLayer& active_title() { return kR4; }

}  // namespace r4l

// In-game menu: R4 selects recomp-launcher as its psxrecomp menu provider
// (psx_menu_host.h). Optional on both sides: without the runtime contract or
// the launcher's adapter this compiles to nothing, and titles that do not do
// this keep their default UI.
#if defined(__has_include)
#if __has_include("psx_menu_host.h")
#include "psx_menu_host.h"
extern "C" const PsxMenuProvider* recomp_launcher_psx_menu_provider(void);
namespace {
const int g_r4_menu_provider = psx_menu_set_provider(recomp_launcher_psx_menu_provider());
}  // namespace
#endif
#endif
