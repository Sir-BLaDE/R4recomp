#!/usr/bin/env python3
"""Build the R4 HD texture pack (DuckStation `texupload` names) from the
player's discs and the r4.spanish payload.

    python3 tools/r4_hd/build_pack.py --jp R4_JP.bin --eu R4_PAL.bin \
        --spanish mods/preloaded/packages/r4.spanish/1.0.0 \
        --esrgan-art RealESRGAN_x4plus_anime_6B.pth \
        --esrgan-photo RealESRGAN_x4plus.pth \
        --out mods/preloaded/packages/r4.hd/1.0.0/pack

What goes in
------------
* the Spanish message font (PAL sheet installed by r4.spanish) redrawn at
  8x/4x from TeX Gyre Heros (font_es.py), one image per palette row;
* the four Spanish ending letters rebuilt from the PAL pages at 4x;
* every 2D sheet of the menus, Grand Prix screens, HUD, logos, results and
  story backgrounds at 4x (redraw.py): the grey anti-aliased text sheets
  are redrawn as traced vector outlines (potrace) filled with the ESRGAN
  colour; colour art goes through Real-ESRGAN x4plus anime_6B and pictures
  through Real-ESRGAN x4plus (spandrel, the loader chaiNNer uses), both with
  a traced, smooth silhouette for the binary alpha.

Every name is computed offline exactly as the runtime hashes an upload:
XXH3-64 of the TIM's pixel words and of the palette row's 16 words
(`P0-15`, prefix hash), source size in VRAM words, full-rectangle crop.
The textures are read from the Japanese R4.BIN *after* the r4.spanish
overlays, so the hashes are those of what the game really uploads.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import tomllib

import numpy as np
import xxhash
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "r4_es"))
import build_es as B          # noqa: E402
import font_es                # noqa: E402
from esrgan import Esrgan     # noqa: E402
import redraw                 # noqa: E402

SECTOR = 2048
SCALE = 4

# 2D entries of the Japanese R4.BIN (menus, GP screens, story backgrounds,
# title/logo, results, HUD sheets). Course and car textures stay native.
# Kept to sheets with distinct page positions: the page matcher hashes every
# candidate rectangle a draw overlaps, and the story pictures (694-745), team
# logos (676) and 754 stack hundreds of variants on the same rectangles.
UPSCALE_ENTRIES = (
    [658, 673, 674, 675, 677, 757, 764, 765, 766] + list(range(948, 969)))
FONT_ENTRIES = (756, 758, 760, 762)     # Spanish font containers
COURSE_ENTRIES = tuple(range(0, 17))   # course textures (with the PAL billboards)
ENDING_ENTRIES = (915, 916, 917, 918)
ENDING_PAL = (896, 897, 898, 899)       # Spanish letters, same team order


def patched_r4bin(jp_disc, pack_dir):
    """Japanese R4.BIN with the r4.spanish overlays applied."""
    lba, size = jp_disc.find("R4.BIN")
    blob = bytearray(jp_disc.read(lba, size))
    man = tomllib.load(open(os.path.join(pack_dir, "manifest.toml"), "rb"))
    base = lba * SECTOR
    for ov in man.get("overlay", []):
        data = open(os.path.join(pack_dir, ov["file"]), "rb").read()
        rel = ov["offset"] - base
        blob[rel:rel + len(data)] = data
    return bytes(blob)


def tims(e):
    """Every TIM in an entry: dict(fl, rect, clut_rows[list of bytes], data)."""
    out, off = [], 0
    while True:
        off = e.find(b"\x10\x00\x00\x00", off)
        if off < 0 or off + 20 > len(e):
            return out
        fl = struct.unpack("<I", e[off + 4:off + 8])[0]
        p, rows, ok = off + 8, [], True
        if fl not in (0, 1, 2, 8, 9):
            off += 4
            continue
        if fl & 8:
            cl, cx, cy, cw, ch = struct.unpack("<I4H", e[p:p + 12])
            if not (cw and ch and cl == 12 + cw * ch * 2 and p + cl <= len(e)):
                off += 4
                continue
            words = e[p + 12:p + cl]
            per = 16 if (fl & 7) == 0 else 256
            for r in range(ch):
                row = words[r * cw * 2:(r + 1) * cw * 2]
                for k in range(0, cw, per):
                    seg = row[k * 2:(k + per) * 2]
                    if len(seg) == per * 2:
                        rows.append(seg)
            p += cl
        if p + 12 > len(e):
            off += 4
            continue
        il, x, y, w, h = struct.unpack("<I4H", e[p:p + 12])
        if not (w and h and il == 12 + w * h * 2 and p + il <= len(e)
                and x < 1024 and y < 512):
            off += 4
            continue
        out.append(dict(fl=fl & 7, rect=(x, y, w, h), rows=rows,
                        data=e[p + 12:p + il]))
        off += 4


def c15(c):
    return ((c & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31,
            ((c >> 10) & 31) * 255 // 31)


def native_rgba(t, row):
    """RGBA of a paletted TIM with one palette row (index colour 0x0000 =
    transparent, as the GPU treats it)."""
    x, y, w, h = t["rect"]
    pal = struct.unpack("<%dH" % (len(row) // 2), row)
    lut = np.array([(*c15(c), 0 if c == 0 else 255) for c in pal], np.uint8)
    d = np.frombuffer(t["data"], np.uint8)
    if t["fl"] == 0:
        idx = np.empty(d.size * 2, np.uint8)
        idx[0::2], idx[1::2] = d & 15, d >> 4
        W = w * 4
    else:
        idx, W = d, w * 2
    return Image.fromarray(lut[idx.reshape(h, W)], "RGBA")


def name(t, row):
    """DuckStation `texpage` name: R4 composes its texture pages in RAM and
    uploads whole 64x256-word pages, so upload identities depend on what else
    shares the page. A page subrectangle hashes only its own words, which are
    exactly the TIM's pixel words when the TIM lies inside one page."""
    x, y, w, h = t["rect"]
    th = xxhash.xxh3_64_hexdigest(t["data"]).upper()
    if t["fl"] == 2:
        pw, mode, tex = 256, "C16", 1
    elif t["fl"] == 0:
        pw, mode, tex = 64, "P4", 4
    else:
        pw, mode, tex = 128, "P8", 2
    px, py = x - x % pw, y - y % 256
    ox, oy = x - px, y - py
    if ox + w > pw or oy + h > 256:
        return None                          # crosses a page: not matchable
    rect = f"{pw}x256-{ox * tex}-{oy}-{w * tex}x{h}"
    if t["fl"] == 2:
        return f"texpage-{mode}-{th}-{rect}"
    ph = xxhash.xxh3_64_hexdigest(row).upper()
    top = 15 if t["fl"] == 0 else 255
    return f"texpage-{mode}-{th}-{ph}-{rect}-P0-{top}"


def upload_name(t, row):
    x, y, w, h = t["rect"]
    th = xxhash.xxh3_64_hexdigest(t["data"]).upper()
    ph = xxhash.xxh3_64_hexdigest(row).upper()
    mode, W, top = ("P4", w * 4, 15) if t["fl"] == 0 else ("P8", w * 2, 255)
    return f"texupload-{mode}-{th}-{ph}-{w}x{h}-0-0-{W}x{h}-P0-{top}"


def indices(t, row):
    """Palette indices (texel row widened to pixels) and the RGBA lut."""
    x, y, w, h = t["rect"]
    pal = struct.unpack("<%dH" % (len(row) // 2), row)
    lut = np.array([(*c15(c), 0 if c == 0 else 255) for c in pal], np.uint8)
    d = np.frombuffer(t["data"], np.uint8)
    if t["fl"] == 0:
        idx = np.empty(d.size * 2, np.uint8)
        idx[0::2], idx[1::2] = d & 15, d >> 4
        W = w * 4
    else:
        idx, W = d, w * 2
    return idx.reshape(h, W), lut


class Upscaler:
    def __init__(self, art, photo):
        self.art = Esrgan(art)
        self.photo = Esrgan(photo) if photo else self.art

    def rgb4x(self, rgb):
        return self.art.rgb(rgb)

    def sheet(self, t, row):
        idx, lut = indices(t, row)
        if redraw.is_mono_text(idx, lut):
            return redraw.redraw_mono(idx, lut, self.art), "text"
        n_used = int(sum(1 for i in np.unique(idx) if lut[i, 3]))
        kind = redraw.classify(idx, n_used, *idx.shape[::-1])
        net = self.art if kind == "flat" else self.photo
        return redraw.upscale_art(idx, lut, net), kind


def card_hd(hd, row):
    """Race-card kanji cells redrawn directly at 4x (white letters, dark rim,
    the sheet's palette), over the upscaled sheet."""
    pal = struct.unpack("<16H", row)
    white, mid, rim = c15(pal[15]), c15(pal[11]), c15(pal[2])
    a = np.array(hd)
    for rect, text in B.CARD_TEXT:
        u0, v0, u1, v1 = (k * SCALE for k in rect)
        fill, edge = (np.asarray(m) for m in B.card_layers(rect, text, SCALE))
        cell = np.zeros((v1 - v0, u1 - u0, 4), np.uint8)
        cell[edge >= 90] = (*rim, 255)
        cell[fill >= 70] = (*mid, 255)
        cell[fill >= 140] = (*white, 255)
        a[v0:v1, u0:u1] = cell
    return Image.fromarray(a, "RGBA")


def parse_texpage(stem):
    p = stem.split("-")
    if len(p) < 9 or p[0] != "texpage" or p[1] not in ("P4", "P8"):
        return None
    w, h = (int(v) for v in p[7].split("x"))
    return dict(mode=p[1], th=p[2], ph=p[3], x=int(p[5]), y=int(p[6]), w=w, h=h)


def crop_from_dump(stem, path, hd_of):
    """HD crop for a dumped texpage name that lies inside a known sheet with
    the same palette, verified texel for texel against the dump image."""
    d = parse_texpage(stem)
    if d is None:
        return None
    dimg = np.asarray(Image.open(path).convert("RGBA"))
    for sstem, (t, row, hd) in hd_of.items():
        s = parse_texpage(sstem)
        if not sstem or not s or s["mode"] != d["mode"] or s["ph"] != d["ph"]:
            continue
        ox, oy = d["x"] - s["x"], d["y"] - s["y"]
        if ox < 0 or oy < 0 or ox + d["w"] > s["w"] or oy + d["h"] > s["h"]:
            continue
        nat = np.asarray(native_rgba(t, row))[oy:oy + d["h"], ox:ox + d["w"]]
        if nat.shape[:2] != dimg.shape[:2]:
            continue
        m = (nat[:, :, 3] > 0) & (dimg[:, :, 3] > 0)
        if (nat[:, :, 3] > 0).sum() != (dimg[:, :, 3] > 0).sum():
            continue
        if np.abs(nat[m][:, :3].astype(int) - dimg[m][:, :3].astype(int)).max(initial=0) > 8:
            continue
        return hd.crop((ox * SCALE, oy * SCALE, (ox + d["w"]) * SCALE, (oy + d["h"]) * SCALE))
    return None


def build(a):
    os.makedirs(a.out, exist_ok=True)
    jp, eu = B.Disc(a.jp), B.Disc(a.eu)
    jn, joffs, je = B.archive(patched_r4bin(jp, a.spanish))
    el, es = eu.find("R4.BIN")
    _, _, ee = B.archive(eu.read(el, es))
    up = Upscaler(a.esrgan_art, a.esrgan_photo)
    written, report, hd_of = set(), [], {}

    def save(im, stem):
        if stem is None or stem in written:
            return
        written.add(stem)
        im.save(os.path.join(a.out, stem + ".png"), optimize=True)

    # 1. font
    cov = font_es.coverage_sheet()
    for i in FONT_ENTRIES:
        for t in tims(je[i]):
            if t["rect"] != (960, 0, 64, 144):
                continue
            for row in t["rows"]:
                pal = struct.unpack("<16H", row)
                if pal[1] == 0:
                    continue
                ramp = [c15(c) for c in pal]
                save(font_es.colorize(cov, ramp), name(t, row))
    report.append(("font", len(written)))

    # 2. endings
    n0 = len(written)
    for ji, pi in zip(ENDING_ENTRIES, ENDING_PAL):
        fl, fa = B.ending_frame(je[ji], ee[pi], scale=SCALE,
                                upscale=lambda im: up.rgb4x(im.convert("RGB")).convert("L"))
        ts = [t for t in tims(je[ji]) if t["fl"] == 0]
        x0 = 0
        for t in ts:
            x, y, w, h = t["rect"]
            W = w * 4
            row = t["rows"][0]
            pal = struct.unpack("<16H", row)
            ink = np.array(c15(pal[15]), np.float32)
            l = np.asarray(fl.crop((x0 * SCALE, 0, (x0 + W) * SCALE, h * SCALE)), np.float32)
            al = np.asarray(fa.crop((x0 * SCALE, 0, (x0 + W) * SCALE, h * SCALE)), np.float32)
            lum = np.where(al > 0, l / np.maximum(al, 1), 0)
            rgb = (lum[:, :, None] / 255.0 * ink[None, None, :]).clip(0, 255).astype(np.uint8)
            alpha = np.where(al >= 96, 255, 0).astype(np.uint8)
            save(Image.fromarray(np.dstack([rgb, alpha]), "RGBA"), name(t, row))
            x0 += W
    report.append(("endings", len(written) - n0))

    # 3. upscaled 2D sheets
    n0 = len(written)
    seen, kinds = set(), {}
    for i in UPSCALE_ENTRIES:
        for t in tims(je[i]):
            if t["fl"] == 2 or not t["rows"]:
                continue
            for row in t["rows"]:
                stem = name(t, row)
                if stem in written or stem in seen:
                    continue
                seen.add(stem)
                im = native_rgba(t, row)
                if not np.asarray(im)[:, :, 3].any():
                    continue
                hd, kind = up.sheet(t, row)
                kinds[kind] = kinds.get(kind, 0) + 1
                if i == 658 and t["rect"] == B.CARD_SHEET:
                    hd = card_hd(hd, row)
                save(hd, stem)
                if stem:
                    hd_of[stem] = (t, row, hd)
    report.append(("2D sheets %s" % kinds, len(written) - n0))

    # 4. course textures (Real-ESRGAN; each course reuses the same pages, at
    #    most eight candidates per rectangle)
    if a.courses:
        n0, kinds = len(written), {}
        for i in COURSE_ENTRIES:
            for t in tims(je[i]):
                if not t["rows"]:
                    continue
                for row in t["rows"][:1]:
                    stem = name(t, row)
                    if stem is None or stem in written:
                        continue
                    im = native_rgba(t, row)
                    if not np.asarray(im)[:, :, 3].any():
                        continue
                    hd, kind = up.sheet(t, row)
                    kinds[kind] = kinds.get(kind, 0) + 1
                    save(hd, stem)
                    hd_of[stem] = (t, row, hd)
        report.append(("course textures %s" % kinds, len(written) - n0))

    # 5. names observed in a dump (DumpTexturePages) whose rectangle is a part
    #    of a known sheet: the game overwrote some rows of the page, so the
    #    full-sheet name never matches; the dump's own sub-rectangle does.
    if a.dumps:
        n0 = len(written)
        for f in sorted(os.listdir(a.dumps)):
            stem = f[:-4]
            if stem in written:
                continue
            got = crop_from_dump(stem, os.path.join(a.dumps, f), hd_of)
            if got is not None:
                save(got, stem)
        report.append(("dump sub-rectangles", len(written) - n0))
    for k, v in report:
        print(f"{k}: {v} images")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--jp", required=True)
    ap.add_argument("--eu", required=True)
    ap.add_argument("--spanish", required=True)
    ap.add_argument("--esrgan-art", required=True)
    ap.add_argument("--esrgan-photo", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--courses", action="store_true", help="also upscale the course textures")
    ap.add_argument("--dumps", default=None, help="texture dump dir (DumpTexturePages) to cover partially overwritten pages")
    build(ap.parse_args())
