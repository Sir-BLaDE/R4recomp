"""Run isolated draw sequences against a fresh headless race session.

This is a context determinism/coverage probe, not an isolation gate or proof
of stock-frame identity. Read arguments come from live RAM before ctx_draw
takes its snapshot. --full executes on the main machine: disposable runs only.
"""
import argparse
import json
from dbg import cmd

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--port', type=int, default=5151)
p.add_argument('--seq', choices=('min', 'course', 'gp'), default='course')
p.add_argument('--threads', type=int, default=4)
p.add_argument('--reps', type=int, default=1)
p.add_argument('--full', action='store_true')
p.add_argument('--output')
a = p.parse_args()

def read(address, size=4, signed=False):
    data = cmd({'cmd': 'read_ram', 'addr': hex(address), 'len': size}, port=a.port)
    return int.from_bytes(bytes.fromhex(data['hex']), 'little', signed=signed) & 0xffffffff

frame = read(0x800AC064)
bp = (frame & 1) ^ 1
buf = 0x800ADCA0 + bp * 0x22778
writes = [(0x800ACDCC, buf), (0x800F4DA0, bp),
          (0x1F800004, buf + 0x70), (0x1F800000, buf + 0x1670),
          (0x1F800078, read(0x800F2C14))]
calls = [(0x80093418, [buf + 0x70, 0x2C0]), (0x80093418, [buf + 0xB70, 0x2C0])]
if a.seq == 'gp':
    car = 0x800AC0B0
    speed = read(car + 0x1D8, 2, True)
    if speed & 0x80000000:
        speed -= 0x100000000
    speed = int(speed * 160 / 1168) & 0xffffffff
    calls += [(0x8006F2B0, [0]), (0x80034444, [buf + 0x70, read(0x800F2F94)]),
              (0x80039C04, [car]), (0x8002BEA4, [0]), (0x8002C0F8, [read(0x800AC75C)]),
              (0x800212E0, [read(0x800F4E20, 2, True), 0]), (0x80021134, [0]),
              (0x80021614, [speed, 0]), (0x80021960, [read(car + 0x27A, 2, True), 0]),
              (0x80021A20, [read(car + 0x1EE, 2, True), 0]), (0x80021DDC, [0]),
              (0x80022048, [buf + 0x70, 0]), (0x80021BA4, [0]),
              (0x80020A98, [read(0x800F4EF4, 2, True)]), (0x8006E4D0, []),
              (0x8002E554, [0])]
    if read(car + 0x1EA, 2, True) != read(0x800AD6DA, 2, True):
        calls.append((0x8002258C, [0]))
if a.seq in ('course', 'gp'):
    calls.append((0x8006F00C, [0]))
if a.seq == 'gp':
    calls += [(0x80074AD8, [0]), (0x800374F8, [0]), (0x80070A58, [read(0x800AC068)])]
calls += [(0x80093590, [buf]), (0x80093520, [buf + 0xB6C])]
request = {'cmd': 'ctx_draw', 'threads': a.threads, 'reps': a.reps, 'full': int(a.full),
           'calls': ';'.join(hex(fn) + ':' + ','.join(hex(v) for v in av + [0] * (4-len(av))) for fn,av in calls),
           'writes': ';'.join(hex(at) + '=' + hex(v) for at,v in writes)}
result = cmd(request, port=a.port, timeout=600)
result['input_frame'] = frame
result['sequence'] = a.seq
result['request'] = request
text = json.dumps(result, indent=2)
if a.output:
    from pathlib import Path
    Path(a.output).write_text(text + '\n')
print(text)
raise SystemExit(0 if result.get('ok') and result.get('identical') else 1)
