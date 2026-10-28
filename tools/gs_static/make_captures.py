#!/usr/bin/env python3
"""Overlay captures for the GameShark 60 FPS / 16:9 patch code, so it is
compiled into the executable instead of running on the dirty-RAM
interpreter.

    python3 tools/gs_static/make_captures.py --exe disc/SLPS_017.98 \
        --codes src/r4_gameshark_codes.h --ranges generated/SLPS_017.98_full.ranges \
        --out tools/gs_static/gs_captures.json

Why: the patch writes ~13 KB of MIPS routines into free kernel RAM
(0x8000C000-0x8000FD00) and hooks them from the game's main loop and render
code. Code written at run time can only be interpreted unless a matching
static overlay exists, and with the PGXP hook build every interpreted
instruction also runs the PGXP hooks: that was the R4 slowdown. The same goes
for the game's own functions whose words the patch rewrites (their pages
diverge from the boot EXE, so the static image is refused for every function
in those pages).

This writes one "psxrecomp overlay capture v3" record per region:
  * the hook region, with all four features applied;
  * every patched EXE page, widened to whole functions (from the generated
    code-range manifest), with the patched bytes.
`compile_overlays.py --static` then compiles them; the runtime's static
overlay dispatch validates each region's bytes before running it, so with a
feature switched off (original bytes) the original code runs as before.
"""
import argparse
import base64
import json
import re
import struct

EXE_LOAD = 0x80010000
HOOK_LO, HOOK_HI = 0x8000C000, 0x8000FD00
PAGE = 4096


def parse_codes(path):
    s = open(path).read()
    feats = {}
    for name in re.findall(r"static const R4GsCode (\w+)\[", s):
        body = s.split("R4GsCode " + name)[1].split("};")[0]
        feats[name] = [(int(t, 16), int(a, 16), int(v, 16)) for t, a, v in
                       re.findall(r"\{0x([0-9A-F]+), 0x([0-9A-F]+)u, 0x([0-9A-F]+)u\}", body)]
    return feats


def parse_ranges(path):
    """[(entry, lo, hi)] per function from the F/R manifest."""
    funcs, cur = [], None
    for line in open(path):
        p = line.split()
        if not p or p[0].startswith("#"):
            continue
        if p[0] == "F":
            cur = [int(p[1], 16), None, None]
            funcs.append(cur)
        elif p[0] == "R" and cur is not None:
            lo, ln = int(p[1], 16), int(p[2], 16)
            cur[1] = lo if cur[1] is None else min(cur[1], lo)
            cur[2] = lo + ln if cur[2] is None else max(cur[2], lo + ln)
    return [tuple(f) for f in funcs if f[1] is not None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--codes", required=True)
    ap.add_argument("--ranges", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--observed", help="JSON list of PCs the interpreter ran "
                    "(dirty_ram_stats per_pc): added as dispatch entries")
    a = ap.parse_args()

    exe = open(a.exe, "rb").read()
    t_size = struct.unpack("<I", exe[0x1C:0x20])[0]
    mem = bytearray(0x200000)
    mem[EXE_LOAD & 0x1FFFFF:(EXE_LOAD & 0x1FFFFF) + t_size] = exe[0x800:0x800 + t_size]
    orig = bytes(mem)
    for codes in parse_codes(a.codes).values():
        skip = False
        for t, addr, val in codes:
            if t == 0xD0:
                skip = struct.unpack_from("<H", mem, addr & 0x1FFFFF)[0] != val
                continue
            if skip:
                skip = False
                continue
            if t == 0x80:
                struct.pack_into("<H", mem, addr & 0x1FFFFF, val)
    patched = [i for i in range(EXE_LOAD & 0x1FFFFF, (EXE_LOAD & 0x1FFFFF) + t_size, 4)
               if mem[i:i + 4] != orig[i:i + 4]]
    print(f"patched EXE words: {len(patched)}")

    def word(addr):
        return struct.unpack_from("<I", mem, addr & 0x1FFFFF)[0]

    def targets(lo, hi):
        """j/jal targets of words in [lo, hi)."""
        out = set()
        for pc in range(lo, hi, 4):
            w = word(pc)
            if (w >> 26) in (2, 3):
                out.add(((pc + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2))
        return out

    observed = set()
    if a.observed:
        observed = {int(x, 16) | 0x80000000 for x in json.load(open(a.observed))}

    def record(lo, hi, entries):
        data = bytes(mem[lo & 0x1FFFFF:(hi & 0x1FFFFF) + 4])      # + guard word
        ents = sorted(e for e in entries if lo <= e < hi)
        hx = [f"0x{e:08X}" for e in ents]
        disp = sorted(set(ents) | {e for e in observed if lo <= e < hi})
        dx = [f"0x{e:08X}" for e in disp]
        return {
            "schema": "psxrecomp overlay capture v3",
            "load_addr": f"0x{lo:08X}",
            "size": len(data),
            "guard_bytes": 4,
            "bytes_b64": base64.b64encode(data).decode(),
            "executed_pcs": dx,
            "dispatch_entry_pcs": dx,
            "dispatch_entry_segments": {"kuseg": [], "kseg0": dx, "kseg1": []},
            "function_entry_pcs": hx,
            "seeds": hx,
        }

    caps = []
    # 1. hook region: entries = everything the EXE patches or the region
    #    itself jumps/calls into it
    hook_entries = {t for t in targets(EXE_LOAD, EXE_LOAD + t_size)
                    if HOOK_LO <= t < HOOK_HI}
    hook_entries |= {t for t in targets(HOOK_LO, HOOK_HI) if HOOK_LO <= t < HOOK_HI}
    caps.append(record(HOOK_LO, HOOK_HI, hook_entries))
    print(f"hook region entries: {len(hook_entries)}")

    # 2. patched EXE pages, widened to whole functions
    funcs = parse_ranges(a.ranges)
    pages = sorted({(0x80000000 | p) & ~(PAGE - 1) for p in patched})
    spans = []
    for pg in pages:
        # (the last manifest range runs on into the EXE's data tail; data
        # words the patch rewrites need no compiled host)
        fs = [f for f in funcs if f[1] < pg + PAGE and f[2] > pg
              and f[2] - f[1] <= 0x4000]
        if not fs:
            continue
        lo, hi = min(f[1] for f in fs), max(f[2] for f in fs)
        spans.append([lo, hi, {f[0] for f in fs}])
    spans.sort()
    merged = []
    for s in spans:
        if merged and s[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], s[1])
            merged[-1][2] |= s[2]
        else:
            merged.append(s)
    for lo, hi, ents in merged:
        caps.append(record(lo, hi, ents))
        print(f"EXE region 0x{lo:08X}-0x{hi:08X}: {len(ents)} functions")
    json.dump(caps, open(a.out, "w"), indent=1)
    print(f"{len(caps)} captures -> {a.out}")


if __name__ == "__main__":
    main()
