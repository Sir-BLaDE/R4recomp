"""Write game_pal.toml (SCES-01706) from the USA game.toml of this project.

- Identity, digests and netplay gate are replaced by those of the PAL disc (probe JSON).
- [recompiler]: seeds seeds/pal_funcs.txt, output generated_pal/.
- Every 0x8XXXXXXX address outside a comment is translated (r4map). A list element that cannot
  be translated is commented out; a [[draw_distance.clamp]] block whose `expected` word is not
  found in PAL is commented out. An untranslatable scalar value is an error.
- Translation report: OUTPUT.report.txt

Usage: python make_game_pal.py GAME_TOML PROBE_JSON GENERATED_USA SCES_017.06 OUTPUT [EXTRA_TOML...]
The EXTRA_TOML files (NTSC patches, manual patches) are appended verbatim.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r4map import AddressMap  # noqa: E402

PAL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDR = re.compile(r"0x(8[0-9A-Fa-f]{7})")


def split_comment(l):
    """(code, comment): split at the first # outside a string."""
    in_str = False
    for i, ch in enumerate(l):
        if ch == '"':
            in_str = not in_str
        elif ch == "#" and not in_str:
            return l[:i], l[i:]
    return l, ""


def read_list(path):
    """Non-comment entries of a one-address-per-line file (empty when the file is absent)."""
    if not os.path.exists(path):
        return []
    entries = [l.split("#")[0].strip() for l in open(path, encoding="utf-8")]
    return [x for x in entries if x]


def main():
    if len(sys.argv) < 6:
        raise SystemExit(__doc__)
    src, probe, gen, exe, output = sys.argv[1:6]
    p = json.load(open(probe, encoding="utf-8"))
    amap = AddressMap(gen, exe, os.path.join(PAL_DIR, "manual_addresses.txt"))
    lines = open(src, encoding="utf-8").read().split("\n")
    out, report = [], []
    section = ""
    clamp_start = None   # index in `out` where the current [[draw_distance.clamp]] block starts
    stats = {"ok": 0, "list-removed": 0, "block-removed": 0}

    def tr(a, line_no):
        r, reason = amap.translate(a)
        if r is not None and "word-differs" in reason:
            r = None
        report.append(f"{line_no:4d} 0x{a:08X} -> {('0x%08X' % r) if r else '----------'} {reason}")
        return r, reason

    for no, l in enumerate(lines, 1):
        st = l.strip()
        if st.startswith("["):
            section = st.strip("[]")
            clamp_start = len(out) if st == "[[draw_distance.clamp]]" else None
            out.append(l)
            continue
        code, com = split_comment(l)
        key = code.split("=")[0].strip() if "=" in code else ""
        # --- PAL identity
        if section == "game":
            repl = {"name": '"R4: Ridge Racer Type 4 (Europe)"', "id": '"SCES-01706"',
                    "exe": '"disc/SCES_017.06"', "disc": f'"disc/{p["cue_name"]}"',
                    "entry_pc": f'"{p["entry_pc"]}"', "text_size": f'"{p["text_size"]}"'}
            if key in repl:
                out.append(f"{key} = {repl[key]}")
                continue
        if section == "prepare_disc" and key:
            repl = {"bin_name": f'"{p["bin_name"]}"', "cue_name": f'"{p["cue_name"]}"',
                    "boot_exe": f'"{p["boot_exe"]}"', "known_sizes": f'[{p["data_track_size"]}]'}
            if key in repl:
                out.append(f"{key} = {repl[key]}")
                continue
            if key in ("known_md5", "known_sha1", "known_crc32"):
                v = p["data_track_" + key.split("_")[1]]
                out.append(f'{key} = ["{v}"]')
                section = "prepare_disc:skip"
                continue
        if section == "prepare_disc:skip":
            if st.startswith('"') or st == "]":
                continue
            section = "prepare_disc"
        if section == "netplay" and key == "required_disc_fp":
            out.append(f'required_disc_fp = "{p["required_disc_fp"]}"')
            continue
        if section == "recompiler" and key == "seeds":
            out.append('seeds = "seeds/pal_funcs.txt"')
            continue
        if section == "recompiler" and key == "out_dir":
            out.append('out_dir = "generated_pal"')
            continue
        # --- addresses
        addrs = ADDR.findall(code)
        if not addrs:
            out.append(l)
            continue
        if st.startswith('"') and section not in ("widescreen.cull",):
            # address list: translate element by element, drop only the failures
            kept, dropped = [], []
            for h in addrs:
                r, reason = tr(int(h, 16), no)
                (kept.append(f'"0x{r:08X}"') if r is not None else dropped.append(f"0x{h}({reason})"))
            stats["ok"] += len(kept)
            stats["list-removed"] += len(dropped)
            indent = l[:len(l) - len(l.lstrip())]
            if kept:
                out.append(indent + ", ".join(kept) + "," + (" " + com if com else ""))
            if dropped:
                out.append(f"{indent}# PAL: not translated: {' '.join(dropped)}")
            continue
        new, failure = code, None
        for h in addrs:
            a = int(h, 16)
            r, reason = tr(a, no)
            if r is None:
                failure = (h, reason)
                break
            new = new.replace("0x" + h, f"0x{r:08X}", 1)
        if failure is None:
            # culling / clamp sites: the PAL instruction must have the same shape
            if section.startswith("widescreen") or section.startswith("draw_distance"):
                for h in addrs:
                    a = int(h, 16)
                    w = amap.usa.get(a)
                    r, _ = amap.translate(a)
                    if w is not None and amap.pal_word(r) != w:
                        failure = (h, f"PAL instruction {amap.pal_word(r):08X} != USA {w:08X}")
            if failure is None:
                stats["ok"] += 1
                out.append(new + com)
                continue
        h, reason = failure
        if st.startswith('"'):
            stats["list-removed"] += 1
            out.append(f"  # PAL: not translated ({reason}) {l.strip()}")
        elif clamp_start is not None:
            stats["block-removed"] += 1
            for i in range(clamp_start, len(out)):
                out[i] = "# PAL removed: " + out[i]
            out.append(f"# PAL removed ({reason}): {l}")
            clamp_start = len(out)  # following lines of the block
            section = "draw_distance.clamp:removed"
        else:
            raise SystemExit(f"line {no}: untranslatable scalar address 0x{h} ({reason}): {l}")
    # remaining lines of a removed clamp block
    final, removed = [], False
    for l in out:
        if l.startswith("# PAL removed ("):
            removed = True
            final.append(l)
            continue
        if removed and (l.strip().startswith("[") or not l.strip()):
            removed = False
        final.append(("# PAL removed: " + l) if removed and l.strip() else l)
    # PAL-only hooks
    extra = read_list(os.path.join(PAL_DIR, "mod_entries_pal.txt"))
    if extra:
        for i, l in enumerate(final):
            if l.startswith("mod_function_entry_funcs = ["):
                final.insert(i + 1, "  # pal/mod_entries_pal.txt")
                final.insert(i + 2, "  " + ", ".join(f'"{x}"' for x in extra) + ",")
                break
    sites = read_list(os.path.join(PAL_DIR, "instruction_sites_pal.txt"))
    if sites:
        i = final.index("[recompiler]")
        final.insert(i + 1, "# pal/instruction_sites_pal.txt: instruction hooks of the r4.pal.ntsc package")
        final.insert(i + 2, "mod_instruction_sites = [" + ", ".join(f'"{x}"' for x in sites) + "]")
    header = ["# R4: Ridge Racer Type 4 (Europe, SCES-01706). GENERATED by pal/tools/make_game_pal.py",
              "# from game.toml (USA). Do not edit: regenerate with pal/tools/regen_pal.sh.", ""]
    text = "\n".join(header + final)
    for f in sys.argv[6:]:
        text += "\n" + open(f, encoding="utf-8").read()
    open(output, "w", encoding="utf-8", newline="\n").write(text)
    open(output + ".report.txt", "w", encoding="utf-8", newline="\n").write("\n".join(report) + "\n")
    print(f"{output}: {stats}")


if __name__ == "__main__":
    main()
