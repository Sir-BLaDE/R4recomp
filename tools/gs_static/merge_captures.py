#!/usr/bin/env python3
"""Merge the GameShark code-captures and the runtime overlay captures.

The runtime writes every dirty-RAM image it executes to
`overlay_captures.json` (and a per-content history in `overlay_captures.json.d`).
Those are the menu/loader/movie regions that would otherwise run on the
dirty-RAM interpreter. Compiling them statically (compile_overlays.py --static)
turns them into native shards guarded by their first bytes.

Usage:
  python tools/gs_static/merge_captures.py --out tools/gs_static/all_captures.json \
      --runtime build-release/overlay_captures.json \
      --runtime-dir build-release/overlay_captures.json.d \
      --gs tools/gs_static/gs_captures.json
"""
import argparse
import base64
import hashlib
import json
import os
import sys


def load_records(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        for key in ("captures", "records", "overlays"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    return data


def content_key(rec):
    raw = base64.b64decode(rec.get("bytes_b64", ""))
    return (rec.get("load_addr"), hashlib.sha256(raw).hexdigest()[:16], len(raw))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gs", action="append", default=[])
    ap.add_argument("--runtime", action="append", default=[])
    ap.add_argument("--runtime-dir", action="append", default=[])
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    seen = {}
    order = []
    sources = []

    def add(path, label):
        if not path or not os.path.exists(path):
            return
        n = 0
        for rec in load_records(path):
            if not rec.get("load_addr") or "bytes_b64" not in rec:
                continue
            key = content_key(rec)
            if key in seen:
                continue
            seen[key] = rec
            order.append(key)
            n += 1
        if n:
            sources.append(f"{label}: {path} (+{n})")

    for p in args.gs:
        add(p, "gs")
    for p in args.runtime:
        add(p, "runtime")
    for d in args.runtime_dir:
        if os.path.isdir(d):
            for name in sorted(os.listdir(d)):
                if name.endswith(".json"):
                    add(os.path.join(d, name), "runtime-history")

    out = [seen[k] for k in order]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    by_addr = {}
    for rec in out:
        by_addr.setdefault(rec["load_addr"], 0)
        by_addr[rec["load_addr"]] += 1
    print(f"{len(out)} captures -> {args.out}")
    for line in sources:
        print("  ", line)
    print("  regions:")
    for addr in sorted(by_addr, key=lambda a: int(a, 16)):
        sizes = sorted({r["size"] for r in out if r["load_addr"] == addr})
        print(f"    {addr}: {by_addr[addr]} image(s), size {sizes}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
