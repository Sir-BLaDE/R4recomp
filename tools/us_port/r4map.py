"""R4 address translation, USA (SLUS_007.97) -> PAL (SCES_017.06).

Inputs: the USA generated C of this project (instruction words are in its comments) and the
PAL boot executable.
  amap = AddressMap(GENERATED_DIR, SCES_017.06)
  amap.translate(0x8002C0F8) -> (0x8002BC7C, "code:unique:0.97") or (None, reason)

Code: the containing USA function is matched to a PAL function -> same offset inside it.
Unmatched functions: the displacements of matched neighbours are tried, accepted when >= 80 %
of the known (masked) words agree.
Data: LUI/lo pairs of the identical functions -> intervals with a constant displacement.
"""
import bisect
import glob
import re
import struct
from collections import Counter, defaultdict

BASE = 0x80010000
OPS_IMM = (0x08, 0x09, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B, 0x22, 0x26, 0x2A, 0x2E, 0x32, 0x3A, 0x0D)
OPS_LO = {0x09, 0x0D, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B, 0x32, 0x3A}


def mask(w):
    """Instruction word with its relocatable fields (jump target, immediate) cleared."""
    op = w >> 26
    if op in (2, 3):
        return w & 0xFC000000
    if op == 0x0F or op in OPS_IMM:
        return w & 0xFFFF0000
    return w


def lui_pairs(words):
    """[(index, address)] for each lo instruction completing a LUI high half."""
    res, hi = [], {}
    for k, w in enumerate(words):
        if w is None:
            continue
        op, rs, rt = w >> 26, (w >> 21) & 31, (w >> 16) & 31
        if op == 0x0F:
            hi[rt] = (w & 0xFFFF) << 16
            continue
        if op in OPS_LO and rs in hi:
            lo = w & 0xFFFF
            if op != 0x0D and lo & 0x8000:
                lo -= 0x10000
            res.append((k, (hi[rs] + lo) & 0xFFFFFFFF))
        # destination register overwritten: it no longer holds the high half (rs == rt for
        # lw/addiu is handled here too: after addiu rX,rX,lo, rX is no longer a LUI base)
        if op == 0:
            hi.pop((w >> 11) & 31, None)
        elif op not in (0x28, 0x29, 0x2A, 0x2B, 0x2E, 0x3A, 1, 2, 3, 4, 5, 6, 7):
            hi.pop(rt, None)
    return res


def read_manual_addresses(path):
    """{usa: pal} from a `USA PAL  # reason` file."""
    manual = {}
    for l in open(path, encoding="utf-8"):
        l = l.split("#")[0].split()
        if len(l) >= 2:
            manual[int(l[0], 16)] = int(l[1], 16)
    return manual


class AddressMap:
    def __init__(self, gen_dir, pal_exe, manual_path=None):
        self.manual = read_manual_addresses(manual_path) if manual_path else {}
        self.usa, self.size = {}, {}
        for f in glob.glob(gen_dir + "/*_full_*.c"):
            t = open(f, encoding="utf-8", errors="replace").read()
            for a, w in re.findall(r"/\* 0x([0-9A-F]{8}): 0x([0-9A-F]{8}) \*/", t):
                self.usa[int(a, 16)] = int(w, 16)
            for a, s in re.findall(r"/\* Address: 0x([0-9A-F]{8}), Size: (\d+) bytes", t):
                self.size[int(a, 16)] = int(s)
        d = open(pal_exe, "rb").read()
        self.pal_tsize = struct.unpack_from("<I", d, 0x1C)[0]
        d = d[0x800:0x800 + self.pal_tsize]
        self.pal = [struct.unpack_from("<I", d, i)[0] for i in range(0, len(d) - 3, 4)]
        self.palm = [mask(w) for w in self.pal]
        self.starts = sorted(self.size)
        self._match()
        self._data()

    def pal_word(self, a):
        i = (a - BASE) >> 2
        return self.pal[i] if 0 <= i < len(self.pal) else None

    def _score(self, a, p):
        n = self.size[a] // 4
        i0 = (p - BASE) >> 2
        ok = known = 0
        for k in range(n):
            w = self.usa.get(a + 4 * k)
            if w is None:
                continue
            known += 1
            if 0 <= i0 + k < len(self.palm) and self.palm[i0 + k] == mask(w):
                ok += 1
        return (ok / known if known else 0.0), known

    def _match(self):
        index = defaultdict(list)
        for i in range(len(self.palm) - 4):
            index[tuple(self.palm[i:i + 4])].append(i)
        cand = {}
        for a in self.starts:
            n = self.size[a] // 4
            mm = [mask(self.usa[a + 4 * k]) if (a + 4 * k) in self.usa else None for k in range(n)]
            win = next((k for k in range(n - 3) if None not in mm[k:k + 4]), None)
            if win is None:
                continue
            sc = []
            for i in index.get(tuple(mm[win:win + 4]), []):
                p = BASE + 4 * (i - win)
                s, c = self._score(a, p)
                if s >= 0.9:
                    sc.append((s, p))
            cand[a] = sorted(sc, reverse=True)
        self.fn = {}
        for a, sc in cand.items():
            if sc and (len(sc) == 1 or sc[1][0] < sc[0][0]):
                self.fn[a] = (sc[0][1], sc[0][0], "unique")
        # neighbours: ambiguous matches, then short/incomplete functions checked at a
        # neighbour's displacement
        for pass_no in range(4):
            for j, a in enumerate(self.starts):
                if a in self.fn:
                    continue
                neighbours = [self.fn[b][0] - b for b in self.starts[max(0, j - 8):j + 9] if b in self.fn]
                for disp, _ in Counter(neighbours).most_common():
                    s, c = self._score(a, a + disp)
                    if (c >= 2 and s >= 0.8) or (c == 1 and s == 1.0 and pass_no >= 2):
                        self.fn[a] = (a + disp, s, "neighbour")
                        break

    def _data(self):
        pairs = defaultdict(Counter)
        for a, (p, s, _) in self.fn.items():
            if s < 1.0:
                continue
            n = self.size[a] // 4
            mu = [self.usa.get(a + 4 * k) for k in range(n)]
            mp = [self.pal_word(p + 4 * k) if mu[k] is not None else None for k in range(n)]
            for (ku, au), (kp, ap) in zip(lui_pairs(mu), lui_pairs(mp)):
                if ku == kp and 0x80000000 <= au < 0x80200000:
                    pairs[au][ap - au] += 1
        self.data = sorted((au, c.most_common(1)[0][0]) for au, c in pairs.items())
        self._dkeys = [x[0] for x in self.data]

    def containing_function(self, a):
        i = bisect.bisect_right(self.starts, a) - 1
        if i >= 0 and a < self.starts[i] + self.size[self.starts[i]]:
            return self.starts[i]
        return None

    def translate(self, a):
        """(pal_address, reason), or (None, reason) when the address cannot be translated."""
        a &= 0xFFFFFFFF
        if a in self.manual:
            return self.manual[a], "manual"
        if 0x1F800000 <= a < 0x1F800400 or a <= 0x80010000 and a >= 0x80000000:
            return a, "fixed"         # scratchpad / kernel: identical
        if a >= 0x801F0000:
            return a, "fixed:stack"   # top of RAM (stack): identical
        if a >= 0x801149A8:
            return None, "overlay"    # R4.BIN overlays (USA 0x801149A8, PAL 0x80114878): no USA reference
        f = self.containing_function(a)
        if f is not None:
            if f in self.fn:
                p, s, meth = self.fn[f]
                r = p + (a - f)
                w = self.usa.get(a)
                if w is not None and mask(w) != mask(self.pal_word(r) or 0):
                    return r, f"code:{meth}:{s:.2f}:word-differs"
                return r, f"code:{meth}:{s:.2f}"
            return None, "code:unmatched-function"
        if a < BASE + self.pal_tsize + 0x400 and a in self.usa:
            return None, "code:outside-function"
        # data: known interval, or bracketed by two points with the same displacement
        i = bisect.bisect_right(self._dkeys, a) - 1
        if i >= 0 and self.data[i][0] == a:
            return a + self.data[i][1], "data:exact"
        if 0 <= i < len(self.data) - 1 and self.data[i][1] == self.data[i + 1][1]:
            return a + self.data[i][1], "data:bracketed"
        if i >= 0 and i == len(self.data) - 1 and a < 0x80114000:
            return a + self.data[i][1], "data:after-last"
        prev = self.data[i] if i >= 0 else None
        nxt = self.data[i + 1] if i + 1 < len(self.data) else None
        return None, f"data:uncertain({prev and hex(prev[1])},{nxt and hex(nxt[1])})"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        raise SystemExit("usage: python r4map.py GENERATED_USA SCES_017.06 [ADDRESS...]")
    amap = AddressMap(sys.argv[1], sys.argv[2])
    print(f"matched functions: {len(amap.fn)}/{len(amap.starts)}; data points: {len(amap.data)}")
    for x in sys.argv[3:]:
        r, reason = amap.translate(int(x, 16))
        print(x, "->", f"0x{r:08X}" if r is not None else "----------", reason)
