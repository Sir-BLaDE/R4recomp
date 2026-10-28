"""HD redraw of R4's flat 2D art (text sheets, logos, icons, HUD).

Each paletted sheet is split into its colour layers (one per palette index
that is actually used). Every layer's coverage is upscaled 4x with an
ESRGAN model (spandrel, as chaiNNer does), then traced to smooth vector
outlines with potrace and re-rendered at 4x with cairo, so edges are real
curves and straight lines instead of magnified texels. The layers are
composited back in palette order with their exact palette colours: the
redraw keeps the original design, colours and UV layout texel for texel.

Pictures with gradients or photographic content are not traced; they go
through the ESRGAN model directly (see classify()).
"""
import io

import numpy as np
import potrace
import cairosvg
from PIL import Image

SCALE = 4


def classify(idx, n_used, w, h):
    """'flat' for few-colour art with large uniform runs, else 'picture'."""
    if n_used <= 1:
        return "flat"
    # fraction of texels equal to their right neighbour: high for flat art
    same = (idx[:, 1:] == idx[:, :-1]).mean() if w > 1 else 1.0
    return "flat" if (n_used <= 10 and same > 0.55) else "picture"


def trace_mask(mask, turd=2, alpha=1.0, opt=0.2):
    """Binary mask (HxW bool, already at target scale) -> path list."""
    bm = potrace.Bitmap(~mask)          # potracer traces the False pixels
    return bm.trace(turdsize=turd, alphamax=alpha, opticurve=True, opttolerance=opt)


def paths_svg(plist, w, h, color, k=1.0):
    d = []
    for curve in plist:
        s = curve.start_point
        d.append(f"M{s.x*k:.2f},{s.y*k:.2f}")
        for seg in curve.segments:
            if seg.is_corner:
                d.append(f"L{seg.c.x*k:.2f},{seg.c.y*k:.2f}L{seg.end_point.x*k:.2f},{seg.end_point.y*k:.2f}")
            else:
                d.append(f"C{seg.c1.x*k:.2f},{seg.c1.y*k:.2f} {seg.c2.x*k:.2f},{seg.c2.y*k:.2f} "
                         f"{seg.end_point.x*k:.2f},{seg.end_point.y*k:.2f}")
        d.append("Z")
    r, g, b = color
    return (f'<path fill="rgb({r},{g},{b})" fill-rule="evenodd" d="{"".join(d)}"/>')


def render_svg(body, w, h):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'shape-rendering="geometricPrecision">{body}</svg>')
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=w, output_height=h)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def merge_shades(idx, lut, share=0.04, kmax=6, sep=70.0):
    """Collapse anti-aliasing / dither shades onto the sheet's dominant
    colours (and dark edge shades onto transparency), so every layer is a
    clean shape.

    Grey-scale art (text sheets drawn with a grey ramp): one light ink
    (shades at >= half the brightest level) plus, only when the sheet really
    has one (> 10% of the opaque texels), a dark outline ink.
    Colour art: palette entries covering >= `share` of the opaque texels are
    the inks (at most kmax, closer than `sep` merged); every other shade goes
    to the nearest ink, near-black ones to transparency."""
    opaque = lut[idx, 3] > 0
    tot = max(1, int(opaque.sum()))
    ids, cnt = np.unique(idx[opaque], return_counts=True)
    if not len(ids):
        return idx
    count = dict(zip((int(i) for i in ids), (int(c) for c in cnt)))
    tr = int(np.where(lut[:, 3] == 0)[0][0]) if (lut[:, 3] == 0).any() else -1
    col = lut[:, :3].astype(float)
    lum = col @ np.array([0.299, 0.587, 0.114])
    chroma = col.max(1) - col.min(1)
    remap = np.arange(len(lut))
    if max(chroma[i] for i in count) <= 40:
        top = max(lum[i] for i in count)
        light = [i for i in count if lum[i] >= top * 0.5]
        dark = [i for i in count if lum[i] < top * 0.5]
        ink = max(light, key=lambda i: count[i])
        dshare = sum(count[i] for i in dark) / tot
        dink = max(dark, key=lambda i: count[i]) if dark and dshare > 0.10 else tr
        for i in light:
            remap[i] = ink
        for i in dark:
            remap[i] = dink if dink >= 0 else i
        return remap[idx]
    order = []
    for i in sorted(count, key=lambda i: -count[i]):
        if count[i] / tot < share or len(order) >= kmax:
            break
        if all(((col[i] - col[j]) ** 2).sum() ** 0.5 >= sep for j in order):
            order.append(i)
    reps = [(-1, np.zeros(3))] + [(i, col[i]) for i in order]
    for i in count:
        if i in order:
            continue
        best = min(reps, key=lambda r: ((r[1] - col[i]) ** 2).sum())[0]
        remap[i] = best if best >= 0 else (tr if tr >= 0 else i)
    return remap[idx]


def redraw_flat(idx, lut, esr=None):
    """idx: HxW palette indices (native texels, already widened to pixels);
    lut: Nx4 RGBA uint8 (alpha 0 = transparent index). Returns 4x RGBA."""
    h, w = idx.shape
    H, W = h * SCALE, w * SCALE
    idx = merge_shades(idx, lut)
    used = [int(i) for i in np.unique(idx) if lut[i, 3]]
    # paint order: larger layers first so thin details stay on top
    used.sort(key=lambda i: -(idx == i).sum())
    body = []
    for k, i in enumerate(used):
        # stacked layers: each layer covers itself and everything painted
        # over it, so neighbouring colours never leave a gap between them
        m = np.isin(idx, used[k:]).astype(np.uint8) * 255
        col = tuple(int(c) for c in lut[i, :3])
        if esr is not None:      # ESRGAN-upscaled coverage, traced at 4x
            up = np.asarray(esr.rgb(Image.fromarray(np.dstack([m, m, m]))))[:, :, 0]
            body.append(paths_svg(trace_mask(up >= 128), W, H, col))
        else:                    # traced at native resolution, drawn at 4x
            body.append(paths_svg(trace_mask(m > 0, turd=0, alpha=1.0, opt=0.2),
                                  W, H, col, k=SCALE))
    out = render_svg("".join(body), W, H)
    a = np.array(out)
    a[:, :, 3] = np.where(a[:, :, 3] >= 128, 255, 0)
    # un-premultiplied edge colour: snap partially covered texels to their
    # dominant opaque colour (alpha is binary in the pack)
    return Image.fromarray(a, "RGBA")


def is_mono_text(idx, lut):
    """Grey-ramp anti-aliased art (R4's text sheets): every opaque colour is
    grey and at least six grey levels are used."""
    used = [int(i) for i in np.unique(idx) if lut[i, 3]]
    if len(used) < 6:
        return False
    c = lut[used, :3].astype(int)
    if int((c.max(1) - c.min(1)).max()) > 40:
        return False
    # text sits on transparency and is mostly full-strength ink; opaque
    # plates, star fields and grey textures are pictures
    opaque = lut[idx, 3] > 0
    if opaque.mean() > 0.7:
        return False
    lum = lut[:, :3].astype(float) @ np.array([0.299, 0.587, 0.114])
    top = lum[used].max()
    strong = (lum[idx] >= top * 0.8) & opaque
    if strong.sum() < 0.3 * opaque.sum():
        return False
    # anti-aliasing greys sit on the edge of the ink; greys inside the ink
    # (embossed / shaded lettering such as the race HUD) carry detail that a
    # single traced ink would erase
    l = lum[idx]
    mid = opaque & (l > top * 0.25) & (l < top * 0.75)
    inner = opaque.copy()
    inner[1:, :] &= opaque[:-1, :]
    inner[:-1, :] &= opaque[1:, :]
    inner[:, 1:] &= opaque[:, :-1]
    inner[:, :-1] &= opaque[:, 1:]
    return (mid & inner).sum() <= 0.56 * max(1, mid.sum())


def coverage_mask(cov, thresh=0.5):
    """cov: HxW float 0..1 at native size -> 4x boolean mask (Lanczos)."""
    h, w = cov.shape
    im = Image.fromarray((cov * 255).astype(np.uint8), "L").resize(
        (w * SCALE, h * SCALE), Image.LANCZOS)
    return np.asarray(im) >= int(255 * thresh)


def redraw_mono(idx, lut, esr=None):
    """Anti-aliased grey text: coverage = brightness relative to the local
    ink level (sheets mix white headings with dimmer help lines), traced at
    4x. Filled with the ESRGAN colour (keeps interior shading) or, without a
    model, the sheet's brightest ink."""
    from scipy import ndimage
    h, w = idx.shape
    col = lut[:, :3].astype(float)
    lum = (col @ np.array([0.299, 0.587, 0.114])) * (lut[:, 3] > 0)
    top = lum.max() or 1.0
    l = lum[idx]
    ref = np.maximum(ndimage.maximum_filter(l, size=7), top * 0.3)
    cov = l / ref
    mask = coverage_mask(cov, 0.62)
    ink = tuple(int(c) for c in lut[int(np.argmax(lum)), :3])
    out = render_svg(paths_svg(trace_mask(mask), w * SCALE, h * SCALE, ink),
                     w * SCALE, h * SCALE)
    a = np.array(out)
    a[:, :, 3] = np.where(a[:, :, 3] >= 128, 255, 0)
    if esr is None:
        a[:, :, :3] = ink
    else:
        rgb = lut[idx][:, :, :3] * (lut[idx][:, :, 3:] > 0)
        up = np.asarray(esr.rgb(Image.fromarray(rgb.astype(np.uint8))), np.float32)
        k = np.ones((SCALE, SCALE), np.float32)
        ref_up = np.kron(ref.astype(np.float32), k)
        # the traced outline can close the narrow counters of tiny glyphs
        # (h -> b, E -> 8): keep only what the network also sees as ink...
        ulum = up @ np.array([0.299, 0.587, 0.114], np.float32)
        # ...but the network dims one-texel strokes: texels that are mostly
        # ink stay ink, with at least their native colour (counters are
        # background texels)
        full = np.kron((cov >= 0.6).astype(np.float32), k) > 0
        a[:, :, 3] = np.where(((a[:, :, 3] > 0) & (ulum >= ref_up * 0.45)) | full, 255, 0)
        # lift the edge darkening the network leaves inside the traced shape
        mx = up.max(2)
        gain = np.clip(ref_up * 0.9 / np.maximum(mx, 1), 1, 3)
        up = np.where((mx > 0)[:, :, None], up * gain[:, :, None], up)
        nat = np.kron(rgb.astype(np.float32), np.ones((SCALE, SCALE, 1), np.float32))
        up = np.where(full[:, :, None], np.maximum(up, nat), up)
        a[:, :, :3] = np.clip(up, 0, 255).astype(np.uint8)
        # dark opaque texels are part of the glyphs (drop shadows, outlines:
        # under the game's colour modulation they print as the darker half
        # of the letter): the traced silhouette of every opaque texel goes
        # underneath, in the network's colour
        opaque = lut[idx, 3] > 0
        if (opaque & (cov < 0.45)).sum() > 0.05 * max(1, opaque.sum()):
            sil = render_svg(paths_svg(trace_mask(coverage_mask(opaque.astype(np.float32))),
                                       w * SCALE, h * SCALE, (255, 255, 255)), w * SCALE, h * SCALE)
            under = (np.asarray(sil)[:, :, 3] >= 128) & (a[:, :, 3] == 0)
            raw = np.asarray(esr.rgb(Image.fromarray(rgb.astype(np.uint8))), np.uint8)
            a[under, :3] = raw[under]
            a[under, 3] = 255
    return Image.fromarray(a, "RGBA")


SHADOW_OFFSETS = [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (2, 2)]


def _shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    out[dy:, dx:] = m[:h - dy, :w - dx]
    return out


def shadow_offset(idx, lut):
    """Grey text drawn as light ink over a dark copy of itself moved by a
    texel or two (R4's small race-card and date fonts). Returns (dx, dy, ink
    mask, shadow colour) when the dark texels are that shifted copy, else
    None. Such glyphs are 5-8 texels tall: tracing or a network merges ink
    and shadow and closes the counters, so they are redrawn per layer."""
    used = [int(i) for i in np.unique(idx) if lut[i, 3]]
    if len(used) < 3:
        return None
    c = lut[used, :3].astype(int)
    if int((c.max(1) - c.min(1)).max()) > 40:
        return None
    lum = lut[:, :3].astype(float) @ np.array([0.299, 0.587, 0.114])
    opaque = lut[idx, 3] > 0
    if opaque.mean() > 0.8:          # text sits on transparency; plates,
        return None                  # grilles and concrete are pictures
    top = lum[used].max()
    if top < 200:                    # R4's lettering is light
        return None
    l = lum[idx]
    ink = opaque & (l >= top * 0.4)
    dark = opaque & ~ink
    if ink.sum() < 20 or dark.sum() < 0.2 * ink.sum():
        return None
    best = None
    for dx, dy in SHADOW_OFFSETS:
        pred = _shift(ink, dx, dy) & ~ink
        inter = (pred & dark).sum()
        union = (pred | dark).sum()
        iou = inter / max(1, union)
        if best is None or iou > best[0]:
            best = (iou, dx, dy)
    if best[0] < 0.6:
        return None
    dcol = np.median(lut[idx[dark], :3], axis=0).astype(np.uint8)
    return best[1], best[2], ink, dcol


def thick_strokes(ink, share=0.38):
    """Share of ink texels with ink on all four sides: ~0.45 for the date
    font, ~0.27 for the 6-texel race-card font, whose shading inside the
    strokes does not separate from the shadow (plain xBRZ is cleaner)."""
    inner = ink.copy()
    inner[1:] &= ink[:-1]
    inner[:-1] &= ink[1:]
    inner[:, 1:] &= ink[:, :-1]
    inner[:, :-1] &= ink[:, 1:]
    return inner.sum() >= share * max(1, ink.sum())


def xbrz_art(idx, lut):
    """Small anti-aliased pixel text: xBRZ 4x keeps every glyph's shape and
    counters; binary alpha."""
    import xbrz
    up = np.array(xbrz.scale_pillow(Image.fromarray(lut[idx], "RGBA"), SCALE))
    up[:, :, 3] = np.where(up[:, :, 3] >= 128, 255, 0)
    return Image.fromarray(up, "RGBA")


def redraw_shadowed(idx, lut, info):
    """Ink layer upscaled with xBRZ (keeps glyph topology, smooth diagonals),
    the shadow rebuilt as the HD ink moved by the native offset."""
    import xbrz
    dx, dy, ink, dcol = info
    h, w = idx.shape
    rgba = lut[idx].copy()
    rgba[~ink] = 0
    up = np.array(xbrz.scale_pillow(Image.fromarray(rgba, "RGBA"), SCALE))
    a_ink = up[:, :, 3] >= 128
    a_sh = _shift(a_ink, dx * SCALE, dy * SCALE) & ~a_ink
    out = np.zeros((h * SCALE, w * SCALE, 4), np.uint8)
    out[a_sh] = (*dcol, 255)
    out[a_ink, :3] = up[a_ink, :3]
    out[a_ink, 3] = 255
    return Image.fromarray(out, "RGBA")


def upscale_art(idx, lut, esr):
    """Colour art and pictures: ESRGAN colour (transparent texels filled
    from their neighbours first, so no dark fringes) and a traced, smooth
    silhouette for the binary alpha."""
    from scipy import ndimage
    h, w = idx.shape
    rgba = lut[idx]
    alpha = rgba[:, :, 3] > 0
    rgb = rgba[:, :, :3]
    if alpha.any() and not alpha.all():
        _, (iy, ix) = ndimage.distance_transform_edt(~alpha, return_indices=True)
        rgb = rgb[iy, ix]
    up = np.asarray(esr.rgb(Image.fromarray(rgb.astype(np.uint8))))
    if alpha.all():
        al = np.full(up.shape[:2], 255, np.uint8)
    else:
        mask = coverage_mask(alpha.astype(np.float32))
        sil = render_svg(paths_svg(trace_mask(mask), w * SCALE, h * SCALE, (255, 255, 255)),
                         w * SCALE, h * SCALE)
        al = np.where(np.asarray(sil)[:, :, 3] >= 128, 255, 0).astype(np.uint8)
    return Image.fromarray(np.dstack([up, al]), "RGBA")
