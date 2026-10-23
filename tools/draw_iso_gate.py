#!/usr/bin/env python3
"""draw_iso_gate.py - R4 draw-isolation gate (docs/DRAW_ISOLATION.md).

Proves, over a whole race, that every race draw call can run against a private
copy of guest RAM / scratchpad / GTE registers without changing the game: a
run with the draw isolated (mode iso) must log the same per-tick state and
frame hashes as a stock run (mode base) from the same race savestate and
frame-exact input. Nested stock calls also require guest-write fingerprint
equality; isolated calls can differ in dead stack writes.

  python tools/draw_iso_gate.py prepare --build build --out RUNS --port 5341
      boot headless + turbo, walk the menus into a Grand Prix race (the
      tools/smoke.py route), save RUNS/race.pst
  python tools/draw_iso_gate.py run base --build build --out RUNS --port 5342
  python tools/draw_iso_gate.py run nest ...
  python tools/draw_iso_gate.py run iso ...
      load the race state, drive the route (accelerate with a steering
      pattern) until the race has ended (or --frames), and write
      RUNS/<label>/{ticks.csv, summary.txt, fingerprint.json, run.json}
  python tools/draw_iso_gate.py compare RUNS/base RUNS/iso
      0 IDENTICAL, 1 MISMATCH (first divergent tick and column), 3 INCOMPLETE
  python tools/draw_iso_gate.py gate --build build --out RUNS --port 5341
      prepare (unless RUNS/race.pst exists), run base, nest and iso, compare
      base-nest and base-iso; exit 0 only if both are IDENTICAL

Runs are headless with --no-launcher and stock mods plus the developer
package r4.debug.draw-isolation (tools/mod_state.py writes build/mods/state.toml).
Each run has its own working directory and state directory. Needs a
-DPSX_DEBUG_TOOLS=ON build.
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from dbg import cmd  # noqa: E402
from pad import mask  # noqa: E402

DISC = os.path.join(ROOT, "disc", "R4 - Ridge Racer Type 4 (USA).cue")
SLOT = 9
PHASE = 0x800FF860
# gte_hash is logged but not judged: with isolation it is the main context's
# own GTE registers, which differ from stock by design.
JUDGE = ["counter", "tick", "handler", "mode", "phase", "loop_reads_owned",
         "ot_words", "ot_hash", "ram_hash", "spad_hash"]
FP_JUDGE = ["cyc", "mmio", "mc", "sp", "sc", "wc", "ws"]


def runtime_path(build):
    for name in ("r4-runtime.exe", "r4-runtime"):
        p = os.path.join(ROOT, build, name)
        if os.path.exists(p):
            return p
    raise SystemExit(f"no r4-runtime in {build}")


def runtime_hash(build):
    with open(runtime_path(build), "rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def set_mod_state(build, defaults=False):
    argv = [sys.executable, os.path.join(HERE, "mod_state.py"), os.path.join(ROOT, build)]
    if defaults:
        subprocess.check_call(argv + ["--defaults"])
    subprocess.check_call(argv + ([] if defaults else ["--stock"]) + [
        "--enable", "r4.debug.draw-isolation/draw-isolation"])


def launch(build, port, workdir, env_extra):
    os.makedirs(workdir, exist_ok=True)
    env = dict(os.environ)
    env.update({"SDL_AUDIODRIVER": "dummy", "PSX_OVERLAY_AUTOCOMPILE_OFF": "1",
                "PSX_DEBUG_FMV_QUIET": "0"})
    env.update(env_extra)
    log = open(os.path.join(workdir, "runtime.log"), "w")
    argv = [runtime_path(build), "--game", os.path.join(ROOT, build, "game.toml"), "--disc", DISC,
            "--no-launcher", "--headless", "--debug-port", str(port),
            "--memcard-dir", os.path.join(workdir, "saves")]
    proc = subprocess.Popen(argv, cwd=workdir, env=env, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.time() + 90
    while True:
        try:
            cmd({"cmd": "turbo", "enabled": 1}, port=port, timeout=2)
            return proc
        except OSError:
            if proc.poll() is not None:
                raise SystemExit(f"runtime exited early ({proc.returncode}); see {workdir}/runtime.log")
            if time.time() > deadline:
                proc.kill()
                raise SystemExit("debug server not reachable")
            time.sleep(0.5)


def stop(proc, port):
    try:
        cmd({"cmd": "quit"}, port=port, timeout=5)
    except OSError:
        pass
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def frame(port):
    return cmd({"cmd": "frame"}, port=port).get("frame", 0)


def wait_frames(n, port, poll=0.02):
    target = frame(port) + n
    while frame(port) < target:
        time.sleep(poll)


def read_u32(port, addr):
    r = cmd({"cmd": "read_ram", "addr": "0x%08X" % addr, "len": 4}, port=port)
    h = r.get("hex") or r.get("data") or ""
    if isinstance(h, str) and len(h) >= 8:
        b = bytes.fromhex(h[:8])
        return int.from_bytes(b, "little")
    return None


def savestate(port, op, slot=SLOT, timeout=60):
    before = cmd({"cmd": "savestate_status"}, port=port).get("generation", 0)
    r = cmd({"cmd": "savestate", "op": op, "slot": slot}, port=port)
    if not r.get("ok", True) and "error" in r:
        raise SystemExit(f"savestate {op}: {r}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = cmd({"cmd": "savestate_status"}, port=port)
        if st.get("generation", 0) != before and not st.get("pending", 0):
            if st.get("last_ok") != 1:
                raise SystemExit(f"savestate {op} failed: {st}")
            return st
        time.sleep(0.1)
    raise SystemExit(f"savestate {op} timed out")


def state_files(workdir):
    return glob.glob(os.path.join(workdir, "**", "state_*_slot%02d.pst" % SLOT), recursive=True)


def prepare(args):
    from smoke import START_FRAME, STEPS
    set_mod_state(args.build, args.defaults)
    work = os.path.join(args.out, "prepare")
    if os.path.exists(work):
        raise SystemExit(f"refusing to replace existing run: {work}")
    proc = launch(args.build, args.port, work, {"R4_DRAW_ISO_MODE": "base"})
    try:
        wait_frames(max(0, START_FRAME - frame(args.port)), args.port)
        for label, buttons, hold, settle in STEPS:
            if label.startswith("race"):
                break
            if buttons:
                cmd({"cmd": "set_input", "buttons": "0x%04X" % mask(buttons)}, port=args.port)
                wait_frames(int(hold * 60), args.port)
                cmd({"cmd": "clear_input"}, port=args.port)
            wait_frames(int(settle * 60), args.port)
            if label.startswith("pre-") and read_u32(args.port, PHASE) in (1, 2):
                break
        # Menu timing can finish during countdown or the active race.
        deadline = time.time() + 120
        while time.time() < deadline:
            if read_u32(args.port, PHASE) in (1, 2):
                break
            wait_frames(10, args.port)
        print("prepare: phase", read_u32(args.port, PHASE), "frame", frame(args.port))
        if read_u32(args.port, PHASE) not in (1, 2):
            raise SystemExit("prepare: failed to reach an active race")
        savestate(args.port, "save")
        misses = cmd({"cmd": "dispatch_stats"}, port=args.port).get("miss_total")
        print("prepare: dispatch misses", misses, flush=True)
        if misses != 0:
            raise SystemExit("prepare: dispatch misses must be resolved before testing")
        cmd({"cmd": "screenshot", "path": os.path.join(work, "race_start.png")}, port=args.port)
    finally:
        stop(proc, args.port)
    files = state_files(work) or glob.glob(os.path.join(ROOT, args.build, "**",
                                                        "state_*_slot%02d.pst" % SLOT), recursive=True)
    if not files:
        raise SystemExit("prepare: no savestate file found")
    src = max(files, key=os.path.getmtime)
    shutil.copy(src, os.path.join(args.out, "race.pst"))
    with open(os.path.join(args.out, "race.pst.name"), "w") as f:
        f.write(os.path.relpath(src, work) if src.startswith(os.path.abspath(work)) else os.path.basename(src))
    with open(os.path.join(args.out, "race.runtime.sha256"), "w") as f:
        f.write(runtime_hash(args.build))
    print("prepare: saved", src)


def route_steps(drive_cycles=24):
    """Accelerate with a fixed steering pattern (the car laps, scrapes walls
    and turns around: wide draw coverage), then let go until the time limit
    ends the race (TIME OVER and the exit). Steps count pad polls, so the
    route replays on the same guest frames in every run."""
    steps = []
    pattern = [(["cross"], 240), (["cross", "left"], 40), (["cross"], 200), (["cross", "right"], 40)]
    for _ in range(drive_cycles):
        for buttons, n in pattern:
            steps.append({"buttons": "0x%04X" % mask(buttons), "frames": n})
    steps.append({"buttons": "0xFFFF", "frames": 60000})
    return steps


def run(args):
    out = os.path.join(args.out, args.label or args.mode)
    if os.path.exists(out):
        raise SystemExit(f"refusing to replace existing run: {out}")
    os.makedirs(out)
    pst = os.path.join(args.out, "race.pst")
    if not os.path.exists(pst):
        raise SystemExit("no race.pst: run prepare first")
    identity = runtime_hash(args.build)
    with open(os.path.join(args.out, "race.runtime.sha256")) as source:
        if source.read().strip() != identity:
            raise SystemExit("race savestate belongs to another build: prepare a fresh state")
    name = open(os.path.join(args.out, "race.pst.name")).read().strip()
    dest = os.path.join(out, name)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy(pst, dest)
    env = {"R4_DRAW_ISO_MODE": args.mode,
           "R4_DRAW_ISO_LOG": os.path.join(out, "ticks.csv"),
           "R4_DRAW_ISO_SUMMARY": os.path.join(out, "summary.txt")}
    for kv in args.env or []:
        k, v = kv.split("=", 1)
        env[k] = v
    set_mod_state(args.build, args.defaults)
    t0 = time.time()
    proc = launch(args.build, args.port, out, env)
    info = {"mode": args.mode, "env": env, "defaults": args.defaults, "runtime_sha256": identity}
    try:
        wait_frames(30, args.port)
        # The route and the fingerprint ring both restart at the load, so
        # every run replays the same input on the same guest frames.
        cmd({"cmd": "clear_input"}, port=args.port)
        cmd({"cmd": "input_route_clear"}, port=args.port)
        for st in route_steps():
            cmd({"cmd": "input_route_append", **st}, port=args.port)
        cmd({"cmd": "input_route_start", "on_load": 4}, port=args.port)
        cmd({"cmd": "frame_fingerprint", "reset_on_load": 1}, port=args.port)
        savestate(args.port, "load")
        start = frame(args.port)
        info["start_frame"] = start
        ended_at = None
        last_phase = None
        while True:
            f = frame(args.port)
            ph = read_u32(args.port, PHASE)
            if ph != last_phase:
                print(f"  frame {f} phase {ph}", flush=True)
                last_phase = ph
            if ph is not None and ph >= 4 and ended_at is None:
                ended_at = f
            if ended_at is not None and f >= ended_at + args.after:
                break
            if f >= start + args.frames:
                break
            if proc.poll() is not None:
                raise SystemExit(f"runtime died ({proc.returncode}); see {out}/runtime.log")
            time.sleep(0.5)
        info["end_frame"] = frame(args.port)
        info["race_ended_frame"] = ended_at
        fp = cmd({"cmd": "frame_fingerprint", "count": 32768}, port=args.port, timeout=120)
        with open(os.path.join(out, "fingerprint.json"), "w") as f:
            json.dump(fp, f)
        d = cmd({"cmd": "dispatch_stats"}, port=args.port)
        info["miss_total"] = d.get("miss_total")
        cmd({"cmd": "screenshot", "path": os.path.join(out, "end.png")}, port=args.port)
    finally:
        try:
            cmd({"cmd": "input_route_stop"}, port=args.port)
        finally:
            stop(proc, args.port)
    info["wall_s"] = round(time.time() - t0, 1)
    with open(os.path.join(out, "run.json"), "w") as f:
        json.dump(info, f, indent=1)
    print(f"run {args.mode}: frames {info['start_frame']}..{info['end_frame']}, race end {ended_at}, "
          f"misses {info['miss_total']}, {info['wall_s']} s")


def load_ticks(d):
    with open(os.path.join(d, "ticks.csv")) as f:
        return list(csv.DictReader(f))


def load_fp(d):
    """Fingerprint entries keyed by their index since the load (the frame
    counter itself is host state and differs between runs)."""
    with open(os.path.join(d, "fingerprint.json")) as f:
        fp = json.load(f)
    entries = fp.get("entries", [])
    # The server returns the oldest retained entry first. Once the ring
    # wraps, index zero is no longer the load frame.
    offset = fp.get("total", len(entries)) - fp.get("available", len(entries))
    return dict(enumerate(entries, start=offset))


def compare(a, b, quiet=False):
    with open(os.path.join(a, "run.json")) as source:
        ra = json.load(source)
    with open(os.path.join(b, "run.json")) as source:
        rb = json.load(source)
    ended = all(r.get("race_ended_frame") is not None for r in (ra, rb))
    ta, tb = load_ticks(a), load_ticks(b)
    verdict = 0
    n = min(len(ta), len(tb))
    first = None
    for i in range(n):
        diff = [c for c in JUDGE if ta[i].get(c) != tb[i].get(c)]
        if diff:
            first = (i, diff)
            break
    if first:
        i, diff = first
        print(f"MISMATCH ticks: first at seq {ta[i]['seq']} (counter {ta[i]['counter']}, "
              f"race tick {ta[i]['tick']}, phase {ta[i]['phase']}): {', '.join(diff)}")
        for c in diff:
            print(f"   {c}: {ta[i][c]} vs {tb[i][c]}")
        verdict = 1
    elif len(ta) != len(tb) and not ended:
        print(f"INCOMPLETE ticks: {len(ta)} vs {len(tb)} lines (the first {n} agree)")
        verdict = verdict or 3
    else:
        print(f"ticks: {n} race ticks identical ({', '.join(JUDGE)})")
    fa, fb = load_fp(a), load_fp(b)
    shared = sorted(set(fa) & set(fb))
    bad = None
    judge_fp = all(r.get("mode") in ("base", "nest") for r in (ra, rb))
    for fr in shared if judge_fp else []:
        diff = [c for c in FP_JUDGE if fa[fr].get(c) != fb[fr].get(c)]
        if diff:
            bad = (fr, diff)
            break
    if bad:
        print(f"MISMATCH fingerprints: first at frame {bad[0]} after the load: {', '.join(bad[1])}")
        verdict = 1
    elif judge_fp:
        print(f"fingerprints: {len(shared)} shared frames identical ({', '.join(FP_JUDGE)})"
              + ("" if set(fa) == set(fb) else f"; frame sets differ ({len(fa)} vs {len(fb)})"))
        if set(fa) != set(fb) and not ended:
            verdict = verdict or 3
    else:
        print("isolated fingerprints not judged: dead stack writes differ by design")
    if not n or not ended:
        print("INCOMPLETE: both runs must cover the race end")
        verdict = verdict or 3
    for r, d in ((ra, a), (rb, b)):
        if r.get("miss_total") != 0:
            print(f"dispatch misses in {d}: {r.get('miss_total', 'unavailable')}")
            verdict = verdict or 4
    print({0: "IDENTICAL", 1: "MISMATCH", 3: "INCOMPLETE", 4: "MISSES"}[verdict])
    return verdict


def gate(args):
    if not os.path.exists(os.path.join(args.out, "race.pst")):
        prepare(args)
    for mode in ("base", "nest", "iso"):
        args.mode, args.label = mode, mode
        run(args)
    v1 = compare(os.path.join(args.out, "base"), os.path.join(args.out, "nest"))
    v2 = compare(os.path.join(args.out, "base"), os.path.join(args.out, "iso"))
    ok = v1 == 0 and v2 == 0
    print("GATE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "run", "gate"):
        p = sub.add_parser(name)
        p.add_argument("--build", default="build")
        p.add_argument("--out", required=True)
        p.add_argument("--port", type=int, default=5341)
        p.add_argument("--frames", type=int, default=40000, help="stop after this many frames")
        p.add_argument("--after", type=int, default=600, help="frames to keep running after the race ends")
        p.add_argument("--env", action="append", help="extra K=V for the runtime")
        p.add_argument("--defaults", action="store_true", help="enable shipped default mods")
        if name == "run":
            p.add_argument("mode", choices=["base", "nest", "iso", "poison"])
            p.add_argument("--label")
    p = sub.add_parser("compare")
    p.add_argument("a")
    p.add_argument("b")
    args = ap.parse_args()
    args.out = os.path.abspath(args.out) if hasattr(args, "out") else None
    if args.cmd == "prepare":
        prepare(args)
        return 0
    if args.cmd == "run":
        run(args)
        return 0
    if args.cmd == "gate":
        return gate(args)
    return compare(args.a, args.b)


if __name__ == "__main__":
    sys.exit(main())
