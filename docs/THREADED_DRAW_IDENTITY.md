# Threaded draw identity receipt

On 2026-10-23, the moving Grand Prix race probe `analysis/worker-pixels-v13`
passed against the existing serial interpolation recipe with default PGXP
seam snapping enabled. Framework source: `9e0f325e69e924695e323838122cf3a7a73be176`.
The diagnostic runs at alpha 32768 from one immutable guest snapshot.

| Comparison | Result |
|---|---|
| Two full serial draws: raw commands and precision receipts | 19,669 commands identical |
| Full serial vs private context, plus four parallel contexts | Identical receipts |
| Full/full rendered source | 7,668 × 4,320 RGBA, zero differing pixels |
| Full/private rendered source | 7,668 × 4,320 RGBA, zero differing pixels |
| Source pixel digest (all three images) | `DA9541F91713E75B` |
| Dispatch/context faults | Zero |

The complete source includes native-wide margins and the canonical center,
captured before transaction rollback. The control comparison was necessary:
the earlier full/full run differed in 19,969 pixels despite identical command
receipts. Disabling seam snapping eliminated that mismatch. Framework fixes
`80cad60` (depth checkpoint) and `ebbf032d` (seam index checkpoint, integrated
as `9e0f325e`) now preserve both histories, including asynchronous baselines.
Snapping remains enabled. Hidden-GL regression checks passed on Windows RTX
4080 SUPER and Mac M4; the final fixture reports 23 checks, zero failures.

This is one moving Grand Prix checkpoint, not coverage of every race mode or
a frame-rate acceptance claim. Cold diagnostic timings include allocation and
readbacks. Production in this short diagnostic run averaged 7.849 ms per
executed private draw and 1.989 ms per capture; asynchronous resource admission
and on-screen distinct-frame throughput remain separate acceptance checks.

The exact combined v13 sources, including generated BIOS and both diagnostic
headers, built on Mac and passed all 31 project tests in 2.74 seconds.
Local logs: `/tmp/r4-v13-build.log` and `/tmp/r4-v13-tests.log` on the Mac.
