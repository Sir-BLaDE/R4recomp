"""NTSC-isation of the PAL code: [[recompiler.patch]] entries restoring the USA values.

For every matched USA function (r4map), each instruction word that differs is classified:
- relocation: LUI/lo pair, JAL or gp access whose PAL address is the translation of the USA
  address -> ignored;
- constant: same instruction, same registers, another immediate / offset -> PATCH (USA value);
- anything else (other registers, PAL address != translation, ...) -> not patched, listed in
  the report.

Usage: python make_ntsc_patches.py GENERATED_USA SCES_017.06 MANUAL_ADDRESSES OUTPUT_TOML
Writes OUTPUT_TOML and its report (OUTPUT without .toml + .report.txt). Exclusions are read
from pal/ntsc_exclusions.txt.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r4map import AddressMap, lui_pairs  # noqa: E402

PAL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NAMES = {0x08: "addi", 0x09: "addiu", 0x0A: "slti", 0x0B: "sltiu", 0x0C: "andi", 0x0D: "ori",
         0x0E: "xori", 0x0F: "lui", 0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu",
         0x28: "sb", 0x29: "sh", 0x2B: "sw"}


# Sites whose instruction changes shape but whose equivalence was established by hand.
FORCED = {
    0x8001E6A8: 0x00002021,   # R4_Main: SetVideoMode(1 = PAL) -> SetVideoMode(0 = NTSC) (move a0,zero)
}


def _address_hi(w):
    """LUI whose immediate looks like the high half of a PS1 address (RAM, scratchpad, I/O, BIOS)."""
    h = w & 0xFFFF
    return 0x7FFF <= h <= 0x8021 or 0x9FFF <= h <= 0xA021 or h in (0x1F80, 0x1F81, 0x1F00, 0xBFC0, 0x0000)


def _is_address(v):
    v &= 0xFFFFFFFF
    return (0x80000000 <= v < 0x80200000 or 0xA0000000 <= v < 0xA0200000 or 0x00000000 <= v < 0x00200000
            or 0x1F800000 <= v < 0x1F802000 or 0xBFC00000 <= v < 0xBFC80000)


def _sx(w):
    v = w & 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


MEMORY_OPS = {0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x28, 0x29, 0x2A, 0x2B, 0x2E, 0x32, 0x3A}


def describe(w):
    op = w >> 26
    if op == 0:
        return f"special fn=0x{w & 63:02X} sa={(w >> 6) & 31}"
    return f"{NAMES.get(op, 'op%02X' % op)} imm=0x{w & 0xFFFF:04X}"


def read_exclusions(path):
    """{(start, end)}: end is None for a whole function (see pal/ntsc_exclusions.txt)."""
    excl = set()
    if os.path.exists(path):
        for l in open(path, encoding="utf-8"):
            l = l.split("#")[0].strip()
            if l:
                lo, _, hi = l.partition("-")
                excl.add((int(lo, 16), int(hi, 16) if hi else None))
    return excl


def main():
    if len(sys.argv) < 5:
        raise SystemExit(__doc__)
    gen, exe, manual, output = sys.argv[1:5]
    c = AddressMap(gen, exe, manual)
    excl = read_exclusions(os.path.join(PAL_DIR, "ntsc_exclusions.txt"))
    patches, others, seen = [], [], set()
    classes = Counter()
    for a, (p, score, meth) in sorted(c.fn.items()):
        if score < (0.9 if meth == "unique" else 0.95) or any(lo == p and hi is None for lo, hi in excl):
            continue   # match too weak: offset inside the function uncertain
        n = c.size[a] // 4
        local, others_f = [], []
        mu = [c.usa.get(a + 4 * k) for k in range(n)]
        mp = [c.pal_word(p + 4 * k) for k in range(n)]
        mpz = [mp[k] if mu[k] is not None else None for k in range(n)]
        # registers holding (approximately) a LUI value before each instruction
        lui_regs, cur = [], set()
        for k in range(n):
            lui_regs.append(set(cur))
            w0 = mu[k] if mu[k] is not None else mp[k]
            if w0 is None:
                continue
            op0 = w0 >> 26
            if op0 == 0x0F:
                if _address_hi(w0):
                    cur.add((w0 >> 16) & 31)
                else:
                    cur.discard((w0 >> 16) & 31)
            elif op0 in (0x08, 0x09, 0x0D) and ((w0 >> 21) & 31) in cur:
                cur.add((w0 >> 16) & 31)
            elif op0 == 0 and (w0 & 63) in (0x21, 0x25) and ((w0 >> 21) & 31) in cur and ((w0 >> 16) & 31) == 0:
                cur.add((w0 >> 11) & 31)
            else:
                dst = (((w0 >> 11) & 31) if op0 == 0 else
                       ((w0 >> 16) & 31) if op0 not in (0x28, 0x29, 0x2B, 2, 3, 4, 5, 1, 6, 7) else None)
                if dst is not None:
                    cur.discard(dst)
        reloc_u = dict(lui_pairs(mu))
        reloc_p = dict(lui_pairs(mpz))
        for k in range(n):
            u, w = mu[k], mp[k]
            if u is None or w is None or u == w:
                continue
            op_u, op_w = u >> 26, w >> 26
            site = p + 4 * k
            if op_u == op_w == 0x0F:
                if ((u >> 16) == (w >> 16)) and not (_address_hi(u) or _address_hi(w)):
                    local.append((site, w, u, a + 4 * k))   # constant (e.g. division magic number)
                    continue
                classes["lui"] += 1
                continue
            if op_u == op_w == 3:
                cu = ((u & 0x3FFFFFF) << 2) | 0x80000000
                cw = ((w & 0x3FFFFFF) << 2) | 0x80000000
                if c.translate(cu)[0] == cw:
                    classes["jal-reloc"] += 1
                    continue
                others_f.append(f"0x{site:08X} jal USA->0x{cu:08X} PAL->0x{cw:08X}")
                continue
            if (k in reloc_u and k in reloc_p and not (_is_address(reloc_u[k]) or _is_address(reloc_p[k]))
                    and (u >> 16) == (w >> 16)):
                local.append((site, w, u, a + 4 * k))   # LUI/ORI pair forming a constant
                continue
            if k in reloc_u and k in reloc_p:
                t = c.translate(reloc_u[k])[0]
                if t == reloc_p[k]:
                    classes["lo-reloc"] += 1
                    continue
                others_f.append(f"0x{site:08X} address USA 0x{reloc_u[k]:08X} PAL 0x{reloc_p[k]:08X} "
                                f"(translated {t and hex(t)})")
                continue
            if op_u != op_w or (u >> 16) != (w >> 16) and op_u != 0:
                if site in FORCED:
                    local.append((site, w, FORCED[site], a + 4 * k))
                    continue
                others_f.append(f"0x{site:08X} different shape USA {u:08X} PAL {w:08X}")
                continue
            if op_u == 0 and (u & 0xFFFF003F) != (w & 0xFFFF003F) and (u ^ w) & ~0x7C0 & 0xFFFFF83F:
                others_f.append(f"0x{site:08X} different registers USA {u:08X} PAL {w:08X}")
                continue
            if op_u in MEMORY_OPS:
                classes["memory-access"] += 1
                continue   # lb/lh/lw/sb/sh/sw: the immediate is an address or a field, never patched
            if op_u in (0x08, 0x09, 0x0D) and ((u >> 21) & 31) in lui_regs[k]:
                classes["lo-address"] += 1
                continue   # addiu/ori on a register loaded by LUI: relocation
            if (op_u in (0x08, 0x09, 0x0D) and ((u >> 21) & 31) != 0
                    and max(abs(_sx(u)), abs(_sx(w))) >= 0x800):
                others_f.append(f"0x{site:08X} ambiguous immediate USA {u:08X} PAL {w:08X}")
                continue
            if (u >> 21) & 31 == 28 or (w >> 21) & 31 == 28:
                classes["gp"] += 1
                others_f.append(f"0x{site:08X} gp access USA {u:08X} PAL {w:08X}")
                continue
            local.append((site, w, u, a + 4 * k))
        shapes = sum(1 for x in others_f if "shape" in x or "registers" in x)
        if shapes > 2:
            # rewritten or misaligned function: no patch, everything is reported
            others.append(f"-- USA function 0x{a:08X} -> PAL 0x{p:08X} skipped ({shapes} shape differences)")
            others.extend("   " + x for x in others_f)
            continue
        others.extend(others_f)
        for site, w, u, usa in local:
            if any(hi is not None and lo <= site < hi for lo, hi in excl):
                continue
            if site in seen:
                continue
            seen.add(site)
            classes["constant"] += 1
            patches.append((site, w, u, usa))
    # debugging bisection: R4_PATCH_RANGE="i:j" keeps only patches[i:j]
    rng = os.environ.get("R4_PATCH_RANGE")
    if rng:
        i, j = (int(x) for x in rng.split(":"))
        patches = patches[i:j]
    with open(output, "w", encoding="utf-8", newline="\n") as o:
        o.write("# GENERATED by pal/tools/make_ntsc_patches.py: NTSC-isation of the PAL code (SCES-01706).\n")
        o.write("# Each word restores the USA (SLUS-00797) instruction value at the same site:\n")
        o.write("# SetVideoMode NTSC, 30 Hz logic (25 -> 30 Hz constants), 240-line screen.\n\n")
        for k, (site, w, u, usa) in enumerate(patches):
            o.write(("\n" if k else "") + "[[recompiler.patch]]\n")
            o.write(f'id = "ntsc-{site:08x}"\n')
            o.write(f'address = "0x{site:08X}"\n')
            o.write(f'expected = "0x{w:08X}"\n')
            o.write(f'replacement = "0x{u:08X}"\n')
            o.write(f'note = "USA 0x{usa:08X}: {describe(w)} -> {describe(u)}"\n')
    report = (output[:-5] if output.endswith(".toml") else output) + ".report.txt"
    with open(report, "w", encoding="utf-8", newline="\n") as o:
        o.write(f"{dict(classes)}\n{len(patches)} patches; {len(others)} differences not patched:\n")
        o.write("\n".join(others) + "\n")
    print(dict(classes), "patches", len(patches), "not patched", len(others))


if __name__ == "__main__":
    main()
