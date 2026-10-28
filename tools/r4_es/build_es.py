#!/usr/bin/env python3
"""Build the Spanish text pack for R4 (SLPS-01798) from the player's two discs.

    python3 tools/r4_es/build_es.py --jp R4_JP.bin --eu R4_EU.bin --out mods/preloaded/packages/r4.spanish/1.0.0

Inputs are single-track MODE2/2352 images (convert a .chd with
`chdman extractcd -i x.chd -o x.cue -ob x.bin`).

What it does
------------
Both releases share the same dialogue engine (16-bit glyph codes with the same
control codes: <41xx><20xx><20yy> message headers, <6003>/<6005> face and pause
codes, 0x1000 newline). The Japanese build gives every dialogue scene its own
glyph sheet (12x24 cells, 21 per row, 11 px advance); the PAL build uses one
Latin-1 sheet (8x24 cells, 32 per row, 7 px advance) and stores the five
languages (En, Fr, De, It, Es) as fixed-size sub-blocks of each text entry.

The pack replaces, inside the Japanese R4.BIN:
  * the 8 text entries of each team's Grand Prix story with the Spanish
    sub-block of the matching PAL entry, and every per-scene glyph sheet with
    the PAL font (same VRAM spot, 960,0 / CLUT 960,255);
  * the four system-message tables (755/759/761/763) and their fonts.
Each team group (and the system group) is repacked inside its own original
sector span, so no other R4.BIN entry moves; only the entry table and those
spans change. The output is a set of disc_user overlay payloads plus a
manifest fragment with their guards. The glyph geometry/advance code patches
live in the package manifest.
"""
import argparse
import hashlib
import json
import os
import struct
import sys

SECTOR = 2048
ES = 4                       # PAL language order: En, Fr, De, It, Es
JP_DISC_SHA256 = None        # filled by --jp; recorded in the output


class Disc:
    def __init__(self, path):
        self.f = open(path, "rb")
        self.raw = os.path.getsize(path) % 2352 == 0
        if not self.raw:
            raise SystemExit(f"{path}: expected a MODE2/2352 .bin")

    def sector(self, lba):
        self.f.seek(lba * 2352)
        return self.f.read(2352)[24:24 + SECTOR]

    def read(self, lba, size):
        n = (size + SECTOR - 1) // SECTOR
        return b"".join(self.sector(lba + i) for i in range(n))[:size]

    def find(self, name):
        pvd = self.sector(16)
        root_lba = struct.unpack("<I", pvd[158:162])[0]
        root_len = struct.unpack("<I", pvd[166:170])[0]
        d = self.read(root_lba, root_len)
        i = 0
        while i < len(d):
            ln = d[i]
            if ln == 0:
                i = (i // SECTOR + 1) * SECTOR
                continue
            lba = struct.unpack("<I", d[i + 2:i + 6])[0]
            size = struct.unpack("<I", d[i + 10:i + 14])[0]
            nm = d[i + 33:i + 33 + d[i + 32]].decode("ascii", "replace")
            if nm.split(";")[0] == name:
                return lba, size
            i += ln
        raise SystemExit(f"{name} not found")


def archive(blob):
    n = struct.unpack("<I", blob[:4])[0]
    offs = list(struct.unpack("<%dI" % (n + 1), blob[4:4 + 4 * (n + 1)]))
    ents = [blob[offs[i] * SECTOR:offs[i + 1] * SECTOR] for i in range(n)]
    return n, offs, ents


def trim_words(b, pads=(0, 0xFFFF)):
    w = list(struct.unpack("<%dH" % (len(b) // 2), b))
    while w and w[-1] in pads:
        w.pop()
    return struct.pack("<%dH" % len(w), *w)


STREAM = 220                 # messages start at word 220; header offsets are relative
ELLIPSIS = 0x0A              # PAL glyph for the ellipsis character
NEWLINE, PAGE_END = 0x1000, 0x0002


def words(b):
    return list(struct.unpack("<%dH" % (len(b) // 2), b))


def pack(w):
    return struct.pack("<%dH" % len(w), *w)


def is_glyph(w):
    return 2 < w < NEWLINE


def fix_header(jp, es, report):
    """Make every message slot the Japanese engine asks for exist in Spanish.

    Slots the PAL text leaves at 0 because they duplicate another slot get
    that slot's Spanish offset. Slots with a message only the Japanese text
    has (single-glyph interjections, one conditional line) get a copy of the
    Japanese message's codes with an ellipsis as its text, appended to the
    stream, so the engine never falls back to message 0."""
    es = list(es)
    for i in range(40):
        if not jp[i] or es[i]:
            continue
        dup = [k for k in range(40) if jp[k] == jp[i] and es[k]]
        if dup:
            es[i] = es[dup[0]]
            continue
        start = STREAM + jp[i]
        later = [jp[k] for k in range(40) if jp[k] > jp[i]]
        end = STREAM + (min(later) if later else jp[i] + 64)
        msg, glyph_done = [], False
        for w in jp[start:end]:
            if is_glyph(w):
                if not glyph_done:
                    msg.append(ELLIPSIS)
                    glyph_done = True
                continue
            if w in (0, 0xFFFF):
                break
            msg.append(w)
        es[i] = len(es) - STREAM
        es += msg
        report.append((i, len(msg)))
    return es


def _is_header(w, i):
    return 0x4000 <= w[i] < 0x5000 and i + 1 < len(w) and 0x2000 <= w[i + 1] < 0x3000


def _count(body):
    """The <20yy> header word: number of words in the message body."""
    return len(body)


def _ctrl(body):
    """The <20zz> header word: number of control words (>= 0x2000) in it."""
    return sum(1 for x in body if x >= 0x2000)


def _hdr_fix(m):
    m[1] = 0x2000 | _count(m[3:])
    m[2] = 0x2000 | _ctrl(m[3:])
    return m


BOX_ROWS = 3                 # PAL page layout (three rows; the rare four-row
                             # pages are split); the r4.spanish patches draw
                             # rows 22 px apart (cell rows 4..21) so three fit
                             # the 88 px box
BOX_CHARS = 48               # 48 x 5 px pen advance = 240 px (PAL rows <= 41)
WIDE_CHARS = 54              # rewrap of over-long pages: 54 x 5 = 270 px of the 296 px box


def _rows(body):
    rows, cur = [], []
    for x in body:
        if x == NEWLINE:
            rows.append(cur)
            cur = []
        else:
            cur.append(x)
    rows.append(cur)
    return rows


def _width(row):
    return sum(1 for x in row if x < NEWLINE)


def _wrap(row, limit=BOX_CHARS):
    """Split one row at spaces (glyph 0) so no part is wider than limit.
    Control pairs (0x6xxx, arg) stay attached to the text after them."""
    words, cur, i = [], [], 0
    while i < len(row):
        x = row[i]
        if x == 0 and _width(cur):
            words.append(cur)
            cur = []
            i += 1
            continue
        cur.append(x)
        i += 1
    if cur:
        words.append(cur)
    out, line = [], []
    for wd in words:
        if line and _width(line) + 1 + _width(wd) > limit:
            out.append(line)
            line = list(wd)
        else:
            line = line + ([0] if line else []) + wd
    if line:
        out.append(line)
    return out


def reflow_messages(w, rows=BOX_ROWS, limit=BOX_CHARS):
    """Keep the PAL line breaks: split only header messages with more than
    `rows` rows into several header messages (the engine clears the box at each header), wrap rows wider
    than the JP box, and remap the 40 slot offsets onto the first piece of
    the message they pointed at. Each piece's display time is the original
    one shared out by length; header counts are recomputed."""
    w = list(w)
    s = w[STREAM:]
    while s and s[-1] in (0, 0xFFFF):
        s.pop()
    hs = [i for i in range(len(s)) if _is_header(s, i)]
    if not hs:
        return w
    pre = s[:hs[0]]
    msgs = [s[a:b] for a, b in zip(hs, hs[1:] + [len(s)])]
    out, remap = list(pre), {}
    for h, m in zip(hs, msgs):
        remap[h] = len(out)
        head, body = m[:3], m[3:]
        trail = 0
        while body and body[-1] == NEWLINE:
            body.pop()
            trail += 1
        rr = []
        for r in _rows(body):
            rr += _wrap(r, limit) if _width(r) > limit else [r]
        # A page longer than the box (PAL four-row pages): rewrap it into
        # wider rows first; several screens (team / maker / car descriptions)
        # show only the first header message, so splitting lost the end.
        if len(rr) > rows:
            joined = []
            for r in rr:
                if not _width(r):
                    continue
                if joined:
                    joined.append(0)
                joined += r
            wide = _wrap(joined, WIDE_CHARS)
            if len(wide) <= rows:
                rr = wide
        # leading empty rows only space the first page; drop the rest
        pages = [rr[i:i + rows] for i in range(0, len(rr), rows)]
        if len(pages) == 1 and rr == _rows(body):
            out += _hdr_fix(head + body + [NEWLINE] * trail)
            continue
        total = sum(_width(r) for r in rr) or 1
        t = head[0] & 0x0FFF
        for k, pg in enumerate(pages):
            piece = []
            for j, r in enumerate(pg):
                if j:
                    piece.append(NEWLINE)
                piece += r
            if k == len(pages) - 1:
                piece += [NEWLINE] * trail
            share = max(60, t * sum(_width(r) for r in pg) // total)
            hd = [0x4000 | min(share, 0x0FFF), 0x2000, 0x2000]
            out += _hdr_fix(hd + piece)
    for i in range(40):
        if w[i] and w[i] in remap:
            w[i] = remap[w[i]]
        elif w[i]:
            raise SystemExit(f"slot {i} offset {w[i]} is not a message start")
    if 0 in remap:
        pass
    return w[:STREAM] + out


def convert_info_stream(jp, es):
    """PAL plays the Grand Prix rules screen (728) as one message stream;
    the Japanese screen (763) asks for 17 messages in step with its
    animation. Split the Spanish stream at every header and page end, merge
    the shortest continuation chain until the counts match, give the
    remaining continuation fragments a header with their real character
    count, and drop the page end before them so they flow in the same box."""
    w = es[STREAM:]
    while w and w[-1] in (0, 0xFFFF):
        w.pop()
    # split: a message is [header?] body, ending at the next header or after
    # a page end (continuation fragments have no header)
    msgs, cur, i = [], [], 0
    while i < len(w):
        if _is_header(w, i) and cur:
            msgs.append(cur)
            cur = []
        cur.append(w[i])
        if w[i] == PAGE_END:
            j = i + 1
            while j < len(w) and w[j] == NEWLINE:
                j += 1
            msgs.append(cur)
            cur = []
            i = j
            continue
        i += 1
    if cur:
        msgs.append(cur)
    # trailing newlines of a message belong to it (JP style); strip leading
    for m in msgs:
        while m and m[0] == NEWLINE:
            m.pop(0)
    has_hdr = [bool(m) and _is_header(m, 0) for m in msgs]
    n = max(k for k in range(1, 40) if jp[k]) + 1        # 17 on SLPS-01798
    # merge continuation fragments into their predecessor, shortest first
    while len(msgs) > n:
        cands = [k for k in range(1, len(msgs)) if not has_hdr[k]]
        if not cands:
            break
        k = min(cands, key=lambda k: len(msgs[k]))
        prev = msgs[k - 1]
        if prev and prev[-1] == PAGE_END:
            prev = prev[:-1]
        msgs[k - 1] = prev + msgs[k]
        del msgs[k], has_hdr[k]
    while len(msgs) < n:                                 # never expected
        msgs.append(list(msgs[-1]))
        has_hdr.append(True)
    # continuation fragments: header with their own count; the fragment
    # before them stays on the same page
    for k in range(len(msgs)):
        if not has_hdr[k]:
            if msgs[k - 1] and msgs[k - 1][-1] == PAGE_END:
                msgs[k - 1] = msgs[k - 1][:-1]
            msgs[k] = [0x4064, 0x2000, 0x2000] + msgs[k]
    for m in msgs:                                        # recount every header
        _hdr_fix(m)
    out = [0] * STREAM
    for k in range(40, STREAM):                           # JP layout words
        out[k] = jp[k]
    body = []
    for k, m in enumerate(msgs):
        if k and body and body[-1] == PAGE_END:
            body.append(NEWLINE)                          # as both streams do
        out[k] = len(body)
        body += m
    return out + body


# The Grand Prix rules screen (763): 17 slots in step with the Japanese
# animation; a slot change clears the two-row box, a header inside a slot
# does not. The PAL wording (728, Spanish), laid out by hand so every slot
# fits two rows of BOX_CHARS. "/" ends a slot that closes a sentence (page
# end, as the Japanese text does), "|" breaks the row.
INFO_ES = [
    'Bienvenidos al Grand Prix: "Real|Racing Roots 99"./',
    '\u00c9stas son las normas de competici\u00f3n de|este Grand Prix./',
    'El Grand Prix consta de 3 fases,|con un total de 8 carreras./',
    'Las Fases 1 y 2 constan de 2 carreras,|y la Ronda final consta de 4./',
    'Dispones de 4 oportunidades en cada|carrera para avanzar./',
    'Deber\u00e1s clasificarte para pasar de una|carrera a otra en el Grand Prix./',
    'Si en las 4 oportunidades|no logras avanzar, deber\u00e1s retirarte./',
    'La posici\u00f3n de clasificaci\u00f3n para cada|fase es:',
    'El 3ro',
    'o mejor en cada una de las carreras|avanza hasta la 1ra Fase./',
    'El 2do',
    'o mejor en cada carrera avanza hasta|la 2da Fase./',
    'Se necesita llegar el 1ro',
    'para acceder a las 4 carreras de la|Ronda Final./',
    'Para ganar el Grand Prix, deber\u00e1s pasar|las dos primeras fases',
    'y conseguir el 1er puesto en las 4|carreras de la Ronda Final./',
    '\u00a1Buena suerte!/',
]

# PAL Latin-1 sheet order (entry 724): glyph code = index + 1, space = 0.
PAL_CHARS = (",.:;?!\u00b1\u00b0/\u2026\u2018\u2019\"()[]+-=<>\u00a5$%#&*@0123456789"
             "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz\u00bf"
             "\u00c0\u00c1\u00c2\u00c3\u00c4\u00c5\u00c6\u00c7\u00c8\u00c9\u00ca\u00cb\u00cc\u00cd\u00ce\u00cf"
             "\u00d0\u00d1\u00d2\u00d3\u00d4\u00d5\u00d6\u00d7\u00d8\u00d9\u00da\u00db\u00dc\u00dd\u00de\u00df"
             "\u00e0\u00e1\u00e2\u00e3\u00e4\u00e5\u00e6\u00e7\u00e8\u00e9\u00ea\u00eb\u00ec\u00ed\u00ee\u00ef"
             "\u00f0\u00f1\u00f2\u00f3\u00f4\u00f5\u00f6\u00f7\u00f8\u00f9\u00fa\u00fb\u00fc\u00fd\u00fe\u00ff"
             "\u0131\u0152\u0153\u0160\u0161\u0178\u0192\u00a1")


def encode_pal(text):
    out = []
    for ch in text:
        if ch == " ":
            out.append(0)
        elif ch == "|":
            out.append(NEWLINE)
        else:
            out.append(PAL_CHARS.index(ch) + 1)
    return out


def info_from_table(conv):
    """Rebuild the converted rules stream from INFO_ES, keeping each slot's
    display time (its first header) from the converted PAL stream."""
    s = conv[STREAM:]
    out = [0] * STREAM
    for k in range(40, STREAM):
        out[k] = conv[k]
    body = []
    for k, text in enumerate(INFO_ES):
        rows = text.rstrip("/").split("|")
        assert len(rows) <= BOX_ROWS and all(len(r) <= BOX_CHARS for r in rows), text
        t = s[conv[k]] if _is_header(s, conv[k]) else 0x4064
        m = [t, 0x2000, 0x2000] + encode_pal(text.rstrip("/"))
        # "/" only marks a slot that closes a sentence: the engine has no
        # page-end code (0x0002 is the '.' glyph of the PAL sheet; appending
        # it printed a second full stop)
        m.append(NEWLINE)
        out[k] = len(body)
        body += _hdr_fix(m)
    return out + body


def pad_sector(b):
    return b + b"\0" * ((-len(b)) % SECTOR)


def tim_parts(b, off=0):
    """Return (flags, clut_block_bytes, image_block_bytes) of a TIM at off."""
    magic, fl = struct.unpack("<II", b[off:off + 8])
    assert magic == 0x10, "not a TIM"
    p = off + 8
    clut = b""
    if fl & 8:
        blen = struct.unpack("<I", b[p:p + 4])[0]
        clut = b[p:p + blen]
        p += blen
    blen = struct.unpack("<I", b[p:p + 4])[0]
    return fl, clut, b[p:p + blen]


def _tim_images(e):
    """(image_data_offset, x, y, w_words, h, clut_bytes) of every 4-bit TIM
    in an entry, in order."""
    out, off = [], 0
    while True:
        off = e.find(b"\x10\x00\x00\x00\x08\x00\x00\x00", off)
        if off < 0:
            return out
        p = off + 8
        cl = struct.unpack("<I", e[p:p + 4])[0]
        clut = e[p + 12:p + cl]
        p += cl
        il, x, y, w, h = struct.unpack("<I4H", e[p:p + 12])
        if il == 12 + w * h * 2:
            out.append((p + 12, x, y, w, h, clut))
        off += 4


def _lum_pal(clut):
    pal = struct.unpack("<16H", clut[:32])
    return [((c & 31) + ((c >> 5) & 31) + ((c >> 10) & 31)) * 255 // 93 for c in pal]


def ending_composite(pal_entry):
    """The Japanese ending letter is one static 312x192 4-bit image (two TIMs
    at VRAM 320,256 and 384,256 side by side); the PAL letter is one 256-px
    column, two 256-row TIMs stacked (page 2 drawn 8 rows up), that scrolls.
    Cut the Spanish column at the blank row nearest its middle and set the
    halves side by side: returns that composite as (luminance, alpha)."""
    from PIL import Image
    pt = _tim_images(pal_entry)
    cw = pt[0][3] * 4
    overlap = 8                       # the PAL scroller draws page 2 eight rows up
    chh = sum(t[4] for t in pt) - overlap * (len(pt) - 1)
    lum = Image.new("L", (cw, chh), 0)
    alpha = Image.new("L", (cw, chh), 0)
    y0 = 0
    for n, (off, x, y, w, h, clut) in enumerate(pt):
        if n:
            y0 -= overlap
            lum.paste(0, (0, y0, cw, chh))
            alpha.paste(0, (0, y0, cw, chh))
        L = _lum_pal(clut)
        d = pal_entry[off:off + w * h * 2]
        for yy in range(h):
            row = d[yy * w * 2:(yy + 1) * w * 2]
            for xx, bt in enumerate(row):
                for k, v in ((0, bt & 15), (1, bt >> 4)):
                    if v:
                        lum.putpixel((xx * 2 + k, y0 + yy), L[v])
                        alpha.putpixel((xx * 2 + k, y0 + yy), 255)
        y0 += h
    inked = [any(alpha.getpixel((x, y)) for x in range(cw)) for y in range(chh)]
    top = inked.index(True)
    bot = chh - inked[::-1].index(True)
    mid = (top + bot) // 2
    blanks = [y for y in range(top, bot) if not inked[y]]
    cut = min(blanks, key=lambda y: abs(y - mid)) if blanks else mid
    halves = [(top, cut), (cut, bot)]
    hh = max(b2 - a2 for a2, b2 in halves)
    gutter = 16
    comp_l = Image.new("L", (cw * 2 + gutter, hh), 0)
    comp_a = Image.new("L", (cw * 2 + gutter, hh), 0)
    for k, (a2, b2) in enumerate(halves):
        while a2 < b2 and not inked[a2]:
            a2 += 1
        comp_l.paste(lum.crop((0, a2, cw, b2)), (k * (cw + gutter), 0))
        comp_a.paste(alpha.crop((0, a2, cw, b2)), (k * (cw + gutter), 0))
    return comp_l, comp_a


def ending_frame(jp_entry, pal_entry, scale=1, upscale=None):
    """(luminance x alpha, alpha) images of the Spanish letter laid into the
    Japanese 312x192 frame, at `scale` times its size. `upscale(img)` may
    enlarge the PAL composite first (the HD texture pack passes waifu2x)."""
    from PIL import Image, ImageChops
    comp_l, comp_a = ending_composite(pal_entry)
    jt = _tim_images(jp_entry)
    jw = sum(t[3] * 4 for t in jt)
    jh = jt[0][4]
    sc = min(jw / comp_l.size[0], jh / comp_l.size[1])
    tw, th = int(comp_l.size[0] * sc), int(comp_l.size[1] * sc)
    ox, oy = (jw - tw) // 2, (jh - th) // 2
    pm = ImageChops.multiply(comp_l, comp_a)
    al = comp_a
    if upscale:
        pm, al = upscale(pm), upscale(al)
    size = (tw * scale, th * scale)
    pm = pm.resize(size, Image.LANCZOS)
    al = al.resize(size, Image.LANCZOS)
    frame_l = Image.new("L", (jw * scale, jh * scale), 0)
    frame_a = Image.new("L", (jw * scale, jh * scale), 0)
    frame_l.paste(pm, (ox * scale, oy * scale))
    frame_a.paste(al, (ox * scale, oy * scale))
    return frame_l, frame_a


def ending_from_pal(jp_entry, pal_entry):
    """Write the Spanish letter (ending_frame) into the Japanese entry's two
    4-bit TIMs with the Japanese palette."""
    jt = _tim_images(jp_entry)
    frame_l, frame_a = ending_frame(jp_entry, pal_entry)
    JL = _lum_pal(jt[0][5])
    out = bytearray(jp_entry)
    x0 = 0
    for off, x, y, w, h, clut in jt:
        data = bytearray(w * h * 2)
        for yy in range(h):
            for xx in range(w * 4):
                a3 = frame_a.getpixel((x0 + xx, yy))
                v = 0
                if a3 >= 96:
                    l = frame_l.getpixel((x0 + xx, yy)) * 255 // max(a3, 1)
                    v = min(range(1, 16), key=lambda i: abs(JL[i] - l))
                data[yy * w * 2 + xx // 2] |= v << (4 * (xx & 1))
        out[off:off + len(data)] = data
        x0 += w * 4
    return bytes(out)


def _tims_any(e):
    """[(rect, tim_offset, total_bytes)] of the 4/8-bit TIMs in an entry."""
    out, off = [], 0
    while True:
        off = e.find(b"\x10\x00\x00\x00", off)
        if off < 0 or off + 20 > len(e):
            return out
        fl = struct.unpack("<I", e[off + 4:off + 8])[0]
        p = off + 8
        if fl in (8, 9):
            cl, cx, cy, cw, ch = struct.unpack("<I4H", e[p:p + 12])
            if cw and ch and cl == 12 + cw * ch * 2 and p + cl + 12 <= len(e):
                q = p + cl
                il, x, y, w, h = struct.unpack("<I4H", e[q:q + 12])
                if w and h and il == 12 + w * h * 2 and q + il <= len(e):
                    out.append(((x, y, w, h), off, q + il - off,
                                e[p + 4:p + 12], e[q + 12:q + il]))
        off += 4


def swap_course_art(je, ee, report):
    """Billboards and adverts in the course entries (0..18) differ between the
    releases (Japanese-only products and logos). A Japanese TIM whose image
    the PAL entry does not have is replaced by the PAL TIM with the same VRAM
    rectangle, size and palette size whose image the Japanese entry lacks
    (palette words and pixels are copied; the Japanese CLUT position stays)."""
    changed = {}
    for i in range(19):
        J, E = je[i], ee[i]
        jt, pt = _tims_any(J), _tims_any(E)
        jb = {t[4] for t in jt}                 # image bytes
        pb = {t[4] for t in pt}
        used, buf = set(), None
        for rect, jo, jn, jclut, jimg in jt:
            if jimg in pb:
                continue
            cand = [(po, pn) for r, po, pn, pclut, pimg in pt
                    if r == rect and pn == jn and pclut[4:] == jclut[4:]
                    and pimg not in jb and po not in used]
            if not cand:
                continue
            po, pn = cand[0]
            used.add(po)
            buf = buf or bytearray(J)
            # PAL palette words and pixels; the Japanese CLUT position stays
            cl = struct.unpack("<I", J[jo + 8:jo + 12])[0]
            buf[jo + 20:jo + 8 + cl] = E[po + 20:po + 8 + cl]
            buf[jo + 8 + cl + 12:jo + jn] = E[po + 8 + cl + 12:po + pn]
            report.append((i, rect))
        if buf is not None:
            changed[i] = bytes(buf)
    return changed


# Race title card (R4.BIN 658, the 256x108 sheet at VRAM 896,396): the date,
# heat and city words are kanji glyphs drawn one sprite each. Each kanji
# cell is redrawn in Latin letters inside its own rectangle, so the card
# reads "1999/05/01 (Sat)", "1st Heat Race 1", "[Yokohama]" with the
# Japanese layout. Rectangles are (u0, v0, u1, v1) in sheet texels.
CARD_SHEET = (896, 396, 64, 108)
CARD_TEXT = [
    ((120, 0, 134, 14), "/"), ((136, 0, 148, 14), "/"), ((148, 0, 160, 14), ""),
    ((160, 0, 172, 14), "Sat"), ((176, 0, 190, 14), "Thu"), ((192, 0, 206, 14), "Fri"),
    ((224, 0, 230, 14), "["), ((232, 0, 240, 14), "]"),
    ((52, 16, 90, 30), "st Heat"), ((92, 16, 106, 30), "Race"), ((108, 16, 122, 30), ""),
    ((124, 16, 169, 30), "Final GP"), ((172, 16, 210, 30), "Last Race"),
    ((212, 16, 226, 30), "Yoko"), ((228, 16, 242, 30), "hama"),
    ((0, 32, 14, 46), "Fuku"), ((16, 32, 28, 46), "oka"),
]
CARD_FONT = "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheroscn-bold.otf"


def card_layers(rect, text, scale):
    """(fill, rim) coverage images (scale x the cell) of `text` set in the
    cell: cap height 10/14 of the cell, baseline on its row 12, a one-texel
    rim, both condensed by the same factor to fit the cell."""
    from PIL import Image, ImageDraw, ImageFont
    u0, v0, u1, v1 = rect
    W, H = (u1 - u0) * scale, (v1 - v0) * scale
    if not text:
        return Image.new("L", (W, H), 0), Image.new("L", (W, H), 0)
    probe = ImageFont.truetype(CARD_FONT, 400)
    pb = probe.getbbox("H")
    font = ImageFont.truetype(CARD_FONT, int(round(400 * (10 * H / 14) / (pb[3] - pb[1]))))
    hb = font.getbbox("H")
    bb = font.getbbox(text)
    sw = scale
    pad = H
    layers = []
    for st in (0, sw):
        g = Image.new("L", (bb[2] - bb[0] + 8 + 2 * sw, H * 3), 0)
        ImageDraw.Draw(g).text((4 + sw - bb[0], pad), text, font=font, fill=255,
                               stroke_width=st, stroke_fill=255)
        layers.append(g)
    box = layers[1].getbbox()
    out = []
    for g in layers:
        g = g.crop((box[0], 0, box[2], g.size[1]))
        if g.size[0] > W:
            g = g.resize((W, g.size[1]), Image.LANCZOS)
        cell = Image.new("L", (W, H), 0)
        cell.paste(g, ((W - g.size[0]) // 2, 12 * H // 14 - (pad + hb[3])))
        out.append(cell)
    return out[0], out[1]


def patch_card_sheet(entry):
    """Rewrite the card sheet's kanji cells (4-bit, palette ramp 0..15)."""
    off = entry.find(struct.pack("<4H", *CARD_SHEET))
    assert off > 0, "card sheet not found"
    data = bytearray(entry)
    w = CARD_SHEET[2]
    base = off + 8
    for rect, text in CARD_TEXT:
        u0, v0, u1, v1 = rect
        size = (u1 - u0, v1 - v0)
        fill, edge = (im.resize(size, 1) for im in card_layers(rect, text, 8))
        for v in range(v0, v1):
            for u in range(u0, u1):
                c = fill.getpixel((u - u0, v - v0))
                e = edge.getpixel((u - u0, v - v0))
                # white letters with the dark rim the sheet's own glyphs have
                idx = 15 if c >= 140 else (11 if c >= 70 else (2 if e >= 90 else 0))
                o = base + v * w * 2 + u // 2
                if u & 1:
                    data[o] = (data[o] & 0x0F) | (idx << 4)
                else:
                    data[o] = (data[o] & 0xF0) | idx
    return bytes(data)


def make_font(jp_entry, eu_font):
    """PAL glyph pixels in the Japanese entry's container.

    Keeps the Japanese CLUT block when it has more palette rows than the PAL
    one (coloured system text selects rows 1..15), else uses the PAL CLUT."""
    wrapped = jp_entry[:4] != b"\x10\x00\x00\x00"
    jfl, jclut, _ = tim_parts(jp_entry, 8 if wrapped else 0)
    efl, eclut, eimg = tim_parts(eu_font, 0)
    jrows = struct.unpack("<H", jclut[10:12])[0] if jclut else 0
    erows = struct.unpack("<H", eclut[10:12])[0] if eclut else 0
    clut = jclut if jrows > erows else eclut
    tim = struct.pack("<II", 0x10, efl | 8) + clut + eimg
    if wrapped:
        hdr = struct.unpack("<4H", jp_entry[:8])
        tim = struct.pack("<4H", hdr[0], hdr[1], len(tim) & 0xFFFF, len(tim) >> 16) + tim
    return tim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jp", required=True)
    ap.add_argument("--eu", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    jp, eu = Disc(a.jp), Disc(a.eu)
    jlba, jsize = jp.find("R4.BIN")
    elba, esize = eu.find("R4.BIN")
    jblob = jp.read(jlba, jsize)
    eblob = eu.read(elba, esize)
    jn, joffs, je = archive(jblob)
    en, eoffs, ee = archive(eblob)
    if (jn, en) != (969, 950):
        raise SystemExit(f"unexpected archives (JP {jn}, PAL {en} entries)")

    eu_font = ee[724]
    new = list(je)

    def es_sub(i, size):
        return trim_words(ee[i][ES * size:(ES + 1) * size])

    # Grand Prix stories: JP team group = script, then 7 x (font, text), font.
    teams = [(678, 678), (695, 687), (712, 696), (729, 705)]
    groups = []
    for jt, et in teams:
        for k in range(8):
            new[jt + 2 * k] = es_sub(et + k, 40960)
            new[jt + 2 * k + 1] = make_font(je[jt + 2 * k + 1], eu_font)
        groups.append((jt, jt + 16))
    # System messages: (table, PAL table) and their fonts.
    report = []
    def merged(jx, es_words):
        return pack(reflow_messages(fix_header(words(je[jx]), es_words, report)))
    for jt, et in teams:
        for k in range(8):
            new[jt + 2 * k] = merged(jt + 2 * k, words(new[jt + 2 * k]))
    for jx, ex in ((755, 723), (759, 726), (761, 727)):
        new[jx] = merged(jx, words(es_sub(ex, 8192)))
    new[763] = pack(info_from_table(convert_info_stream(
        words(je[763]), words(ee[728][ES * 8192:(ES + 1) * 8192]))))
    print("JP-only slots given an ellipsis message:", report)
    for jf in (756, 758, 760, 762):
        new[jf] = make_font(je[jf], eu_font)
    groups.append((755, 764))
    # Endings: the four Japanese letters (915-918) from the Spanish PAL ones
    # (896-899; PAL order En, Fr, De, It, Es x the same four teams).
    for k in range(4):
        new[915 + k] = ending_from_pal(je[915 + k], ee[896 + k])
    groups.append((915, 919))
    art = []
    course = swap_course_art(je, ee, art)
    course[658] = patch_card_sheet(je[658])
    print("PAL billboards copied:", art)

    # Repack every group inside its original sector span.
    offs = list(joffs)
    for lo, hi in groups:
        span = joffs[hi] - joffs[lo]
        cur = joffs[lo]
        for i in range(lo, hi):
            offs[i] = cur
            cur += len(pad_sector(new[i])) // SECTOR
        if cur > joffs[hi]:
            raise SystemExit(f"group {lo}-{hi - 1} needs {cur - joffs[lo]} of {span} sectors")
        offs[hi] = joffs[hi]          # last entry absorbs the slack

    # Assemble payloads (R4.BIN-relative sector ranges -> disc LBAs).
    os.makedirs(os.path.join(a.out, "payload"), exist_ok=True)
    overlays = []

    def emit(name, rel_sector, data):
        orig = jblob[rel_sector * SECTOR:rel_sector * SECTOR + len(data)]
        path = os.path.join(a.out, "payload", name)
        with open(path, "wb") as fh:
            fh.write(data)
        overlays.append(dict(
            file="payload/" + name,
            offset=(jlba + rel_sector) * SECTOR,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            expected_sha256=hashlib.sha256(orig).hexdigest()))

    table = struct.pack("<I", jn) + struct.pack("<%dI" % (jn + 1), *offs)
    tsec = (len(table) + SECTOR - 1) // SECTOR
    tsecs = bytearray(jblob[:tsec * SECTOR])
    tsecs[:len(table)] = table
    emit("r4bin_table.bin", 0, bytes(tsecs))
    for lo, hi in groups:
        body = b"".join(pad_sector(new[i]) for i in range(lo, hi))
        span = (joffs[hi] - joffs[lo]) * SECTOR
        body += b"\0" * (span - len(body))
        emit(f"r4bin_{lo}_{hi - 1}.bin", joffs[lo], body)

    for i, data in sorted(course.items()):
        orig = je[i]
        lo = next(k for k in range(len(data)) if data[k] != orig[k])
        hi = max(k for k in range(len(data)) if data[k] != orig[k]) + 1
        s0, s1 = lo // SECTOR, (hi + SECTOR - 1) // SECTOR
        emit(f"r4bin_{i}_art.bin", joffs[i] + s0, data[s0 * SECTOR:s1 * SECTOR])

    # The original table sectors beyond the table bytes must match too.
    with open(os.path.join(a.out, "overlays.json"), "w") as fh:
        json.dump(dict(r4bin_lba=jlba, overlays=overlays), fh, indent=1)
    for o in overlays:
        print(o["file"], o["offset"] // SECTOR, o["size"])


if __name__ == "__main__":
    main()
