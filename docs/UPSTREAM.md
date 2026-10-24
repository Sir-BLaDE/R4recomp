# Upstream ledger

R4 pins `tetrisgm/psxrecomp` `r4/main` (CLAUDE.md, fork model). Every change
that fork carries over upstream master is listed here with its upstream PR.
When this table is empty, re-pin to upstream master and archive the fork.

The latest 2026-10-24 upstream-master sync is framework commit `d108e9a0` on
fork `r4/main`. It includes upstream #723, #736, #737, #710, #716, #715,
#717, #755, #758 and #174. The merge passed a Windows runtime build and five
focused tests, plus a Mac runtime build and four focused tests. R4 now pins
`d108e9a0`; regeneration changed no game C. Windows R4 32/32 and Mac R4
29/29 tests passed. The earlier v0.2.1 candidate archives still pin
`c4eb8183`. The fork-only changes below remain after the merge.

| Change | Topic branch | Upstream PR | State |
|---|---|---|---|
| Avoid postfx GL texture-size driver queries for known renderer surfaces | `fix/postfx-known-dims` | none yet | in `r4/main` (`8a3bf9f1`); exact GL pixels on Windows and Mac |
| Avoid composition-context GL framebuffer-binding queries per queued output | `fix/presenter-fbo-bindings` | none yet | in `r4/main` (`e1f2e457`); exact present-thread pixels on Windows and Mac |
| Initialize fixed textured sampler uniforms once per shader program | `fix/gl-sampler-uniforms` | none yet | in `r4/main` (`6eead0f2`); exact direct/threaded GL pixels on Windows and Mac |
| Publish the immutable PGXP seam baseline earlier during async reserve | `fix/seam-early-publish` | none yet | in `r4/main` (`c4eb8183`); more prepared seams consumed, exact PGXP verifier and Mac async timing passed |
| Dynres: hold through savestate load | `r4/main` commit `ade1ecd3` | none yet | needs topic branch + PR |
| Transactional render passes (60 fps) | `feat/render-pass-hd` | #727 | narrowed to five-file PR head `45544217`; R4 HD/local-view digest and GL abort proof linked; draft pending distinct-output/performance acceptance |
| Queued render passes, 60 FPS pacing (docs/RENDER_PASSES.md) | `feat/render-pass-queued` | none yet | in `r4/main` |
| MinGW test link fixes | `fix/mingw-test-link` | none yet | in `r4/main` (+2 r4/main-only commits) |
| PGXP seam snapping (gaps sub-pixel positions open at crests / T-junctions) | `fix/pgxp-tjunction-seams` | none yet | in `r4/main` (`3c2e76f5`) |
| Lazy seam normals (pure optimization of the fork's seam snapping) | `fix/pgxp-snap-lazy-normals` | none yet (depends on seam snapping) | in `r4/main` via fork PR #1 (`c8641551`) |
| Queued-pass seam preparation on a persistent worker (depends on seam snapping and queued passes) | `feat/pgxp-seam-batch-prep` | none yet | in `r4/main` via fork PR #2 (`0421f31e`); ordered fallback remains serial when late |
| Queued-interpolation postfx source mask/depth provenance | `feat/queued-postfx-provenance` | none yet | in `r4/main` (`990ffb00`); restores configured bloom on generated frames |
| Host threading: cached GL blend/stencil state, batched render-thread ring, disc read-ahead worker (docs/HOST_THREADING.md) | `feat/host-threading` | none yet | in `r4/main` (`ba0a839e`) |
| Threaded draw contexts, lean clones, OpenBIOS qualification and bounded worker pool | `feat/threaded-contexts` | none yet | in `r4/main`; private draw verified at 60 Hz |
| Draw-isolation gate (debug only) | `feat/draw-isolation-gate` | none yet | in `r4/main` via `6f8b4621`; R4 PR #65 merged |
| Timestamped async output, ordered presentation, depth/seam checkpoints and private GPU replay | `feat/output-timestamp-plan`, `feat/async-render-admission`, `fix/async-output-grid`, `fix/async-presentation-ownership`, `fix/async-untracked-copy` | none yet | in `r4/main`; pixel/ordering receipts in `docs/HANDOFF.md` |
| HD provenance leases and async backup transfer | `fix/hd-tracking-generation`, `perf/async-backup-transfer` | none yet | in `r4/main`; PC/Mac component checks and R4 race probe |
| Bounded presenter capacity and per-title slots | `feat/bounded-present-capacity` | none yet | in `r4/main`; eight slots at R4's 8K budget, direct fallback on allocation failure |
| Dynamic-resolution variable-work verification and optional floor start | `fix/dynres-variable-output-work`, `feat/dynres-start-floor` | none yet | in `r4/main`; R4 selects the 1080p floor start |
| Presenter cadence diagnostics and OpenBIOS stamp refresh | `feat/present-cadence-stats`, `fix/openbios-stamp-current` | none yet | in `r4/main`; stamp checked on PC/Mac |
| Windows render-thread scheduling under host load | `fix/render-thread-priority` | none yet | in `r4/main` (`688380ef`); `PSX_RENDER_THREAD_PRIORITY=0` disables it |
| Abort already-expired async GPU replay and roll back its private transaction | `fix/async-expiry` | none yet | in `r4/main` (`35b3849e`); Windows/Mac GL pixel and stencil parity, short R4 race with zero dispatch misses |
