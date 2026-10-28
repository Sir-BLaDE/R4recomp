#!/usr/bin/env python3
"""HD redraw of the PAL Latin-1 message font (R4.BIN entry 724 on SCES-01706,
the sheet the r4.spanish package installs at VRAM 960,0).

The native sheet is 256x144 4-bit texels: 8x24 cells, 32 per row, drawn in
320x480 mode, so one texel is twice as wide as it is tall. The HD image keeps
that geometry at 8x horizontal / 4x vertical scale (a cell is 64x96 px, square
pixels on screen) and is drawn from TeX Gyre Heros (GUST Font License) with
the metrics of the r4.spanish layout patches, which show cell rows 4..21
with rows 22 px apart (three rows per message box, as PAL) and a 5-texel
pen advance: bold, widened 1.1x, cap height 11 rows (7..17), baseline under
row 17, accents in rows 4..6, descenders in rows 18..21, ink inside columns
0..4 (wider letters are condensed to fit).
"""
from PIL import Image, ImageDraw, ImageFont

CELL_W, CELL_H = 8, 24
SX, SY = 8, 4                       # HD px per texel
COLS, ROWS = 32, 6
FONT = "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheros-bold.otf"
WIDEN = 1.1                         # horizontal stretch (fills the fixed pen advance)

CHARS = list(",.:;?!±°/…‘’\"()[]+-=<>¥$%#&*@0123456789"
             "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz¿"
             "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß"
             "àáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿıŒœŠšŸƒ¡")
assert len(CHARS) == 164, len(CHARS)

CAP_ROWS = 11                      # cap height (rows 7..17)
BASE_ROW = 18                      # first row under the baseline
TOP_ROW, BOTTOM_ROW = 4, 22        # visible cell rows [4, 22)
INK_X0, INK_X1 = 0, 5              # ink columns [0, 5)


def coverage_sheet(font_path=FONT, weight_px=0):
    W, H = COLS * CELL_W * SX, ROWS * CELL_H * SY
    sheet = Image.new("L", (W, H), 0)
    # size the font so the cap height is CAP_ROWS rows tall in HD px
    probe = ImageFont.truetype(font_path, 400)
    cap = probe.getbbox("H")[3] - probe.getbbox("H")[1]
    size = 400 * CAP_ROWS * SY / cap
    font = ImageFont.truetype(font_path, int(round(size)))
    asc = font.getbbox("H")
    max_w = (INK_X1 - INK_X0) * SX
    for i, ch in enumerate(CHARS):
        cx, cy = (i % COLS) * CELL_W * SX, (i // COLS) * CELL_H * SY
        bb = font.getbbox(ch)
        gw, gh = bb[2] - bb[0], bb[3] - bb[1]
        if gw <= 0:
            continue
        # render the glyph alone, baseline-aligned
        pad = 40
        g = Image.new("L", (gw + 2 * pad, int(size * 3)), 0)
        ImageDraw.Draw(g).text((pad - bb[0], pad), ch, font=font, fill=255,
                               stroke_width=weight_px, stroke_fill=255)
        # baseline in g: pad + (asc bottom of 'H')
        base_y = pad + asc[3]
        gbox = g.getbbox()
        if not gbox:
            continue
        g = g.crop((gbox[0], 0, gbox[2], g.size[1]))
        g = g.resize((max(1, int(round(g.size[0] * WIDEN))), g.size[1]), Image.LANCZOS)
        w = g.size[0]
        if w > max_w:                      # condense wide glyphs
            g = g.resize((max_w, g.size[1]), Image.LANCZOS)
            w = max_w
        x = cx + INK_X0 * SX + ((INK_X1 - INK_X0) * SX - w) // 2
        y = cy + BASE_ROW * SY - base_y
        # clip into the cell
        top = max(0, cy + TOP_ROW * SY - y)
        bottom = min(g.size[1], cy + BOTTOM_ROW * SY - y)
        if bottom <= top:
            continue
        sheet.paste(g.crop((0, top, w, bottom)), (x, y + top),
                    g.crop((0, top, w, bottom)))
    return sheet


def colorize(cov, palette_rgb, threshold=48):
    """Coverage -> RGBA with the native palette ramp: index 1 is full ink,
    2..15 a ramp from the darkest to the lightest edge shade. Alpha is binary
    (texture-pack rule: < 128 cutout)."""
    ramp = palette_rgb
    out = Image.new("RGBA", cov.size, (0, 0, 0, 0))
    px = cov.load()
    o = out.load()
    for y in range(cov.size[1]):
        for x in range(cov.size[0]):
            c = px[x, y]
            if c < threshold:
                continue
            if c >= 235:
                r, g, b = ramp[1]
            else:
                k = 2 + (c - threshold) * 13 // (235 - threshold)
                r, g, b = ramp[min(15, k)]
            o[x, y] = (r, g, b, 255)
    return out


if __name__ == "__main__":
    import sys
    s = coverage_sheet()
    s.save(sys.argv[1] if len(sys.argv) > 1 else "font_es_cov.png")
