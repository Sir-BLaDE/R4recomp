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
    """Anti-aliased grey text: coverage = brightness, traced at 4x. Filled
    with the ESRGAN colour (keeps interior shading) or, without a model,
    the sheet's brightest ink."""
    h, w = idx.shape
    col = lut[:, :3].astype(float)
    lum = (col @ np.array([0.299, 0.587, 0.114])) * (lut[:, 3] > 0)
    top = lum.max() or 1.0
    cov = lum[idx] / top
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
        # the traced outline can close the narrow counters of tiny glyphs
        # (h -> b, E -> 8): keep only what the network also sees as ink
        ulum = up @ np.array([0.299, 0.587, 0.114], np.float32)
        a[:, :, 3] = np.where((a[:, :, 3] > 0) & (ulum >= top * 0.45), 255, 0)
        # lift the edge darkening the network leaves inside the traced shape
        l = up.max(2, keepdims=True)
        up = np.where(l > 0, up * np.clip(top * 0.9 / np.maximum(l, 1), 1, 3), up)
        a[:, :, :3] = np.clip(up, 0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


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
