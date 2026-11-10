#!/usr/bin/env python3
"""Shrink a DuckStation-format replacement pack without changing a pixel.

  hd_pack_optimize.py <pack-in> <pack-out> [--method 0..6] [--jobs N]

<pack-in>/replacements/*.png are re-encoded as lossless WebP (exact: the RGB
under transparent pixels is kept too) and every image whose decoded pixels
equal an earlier one becomes an `Aliases:` entry of <pack-out>/config.yaml
instead of a second file. Every written WebP is decoded again and compared
with its source; a mismatch aborts. Other files of the pack (the upload-CRC
PNGs at its root, existing config.yaml options) are copied unchanged.

The runtime reads PNG, JPEG and static WebP replacements and config.yaml
aliases (psxrecomp docs/DUCKSTATION_TEXTURE_FORMAT.md).
"""
import argparse
import hashlib
import io
import os
import shutil
import sys
from multiprocessing import Pool

from PIL import Image

METHOD = 4


def digest(path):
    im = Image.open(path).convert('RGBA')
    h = hashlib.sha256(('%dx%d:' % im.size).encode())
    h.update(im.tobytes())
    return path, h.hexdigest()


def encode(job):
    src, dst = job
    im = Image.open(src).convert('RGBA')
    buf = io.BytesIO()
    im.save(buf, 'WEBP', lossless=True, quality=75, method=METHOD, exact=True)
    data = buf.getvalue()
    back = Image.open(io.BytesIO(data)).convert('RGBA')
    if back.size != im.size or back.tobytes() != im.tobytes():
        raise RuntimeError('lossless round trip failed: ' + src)
    with open(dst, 'wb') as f:
        f.write(data)
    return os.path.getsize(src), len(data)


def main():
    global METHOD
    ap = argparse.ArgumentParser()
    ap.add_argument('pack_in')
    ap.add_argument('pack_out')
    ap.add_argument('--method', type=int, default=4)
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    a = ap.parse_args()
    METHOD = a.method
    rin = os.path.join(a.pack_in, 'replacements')
    rout = os.path.join(a.pack_out, 'replacements')
    if os.path.exists(a.pack_out):
        sys.exit('output exists: ' + a.pack_out)
    os.makedirs(rout)
    names = sorted(n for n in os.listdir(rin) if n.lower().endswith('.png'))
    other = sorted(n for n in os.listdir(rin) if not n.lower().endswith('.png'))
    with Pool(a.jobs, initializer=_init, initargs=(a.method,)) as pool:
        first = {}
        aliases = []
        jobs = []
        for path, d in pool.imap(digest, [os.path.join(rin, n) for n in names], chunksize=32):
            name = os.path.basename(path)
            stem = name[:-4]
            if d in first:
                aliases.append((stem, first[d]))
            else:
                first[d] = stem + '.webp'
                jobs.append((path, os.path.join(rout, stem + '.webp')))
        before = after = 0
        for b, w in pool.imap_unordered(encode, jobs, chunksize=8):
            before += b
            after += w
    for n in other:
        shutil.copy2(os.path.join(rin, n), os.path.join(rout, n))
    for n in sorted(os.listdir(a.pack_in)):
        p = os.path.join(a.pack_in, n)
        if os.path.isfile(p) and n != 'config.yaml':
            shutil.copy2(p, os.path.join(a.pack_out, n))
    lines = []
    cfg = os.path.join(a.pack_in, 'config.yaml')
    if os.path.exists(cfg):
        keep = True
        for line in open(cfg, encoding='utf-8').read().splitlines():
            if line and not line[0].isspace():
                keep = not line.startswith('Aliases:')
            if keep:
                lines.append(line)
    if aliases:
        lines.append('Aliases:')
        lines += ['  %s: %s' % (stem, target) for stem, target in aliases]
    with open(os.path.join(a.pack_out, 'config.yaml'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    dup = sum(os.path.getsize(os.path.join(rin, s + '.png')) for s, _ in aliases)
    print('%d images: %d WebP files (%.1f -> %.1f MiB), %d aliases (%.1f MiB of duplicates)'
          % (len(names), len(jobs), before / 2**20, after / 2**20, len(aliases), dup / 2**20))


def _init(method):
    global METHOD
    METHOD = method


if __name__ == '__main__':
    main()
