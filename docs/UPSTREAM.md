# Upstream ledger

R4 pins `tetrisgm/psxrecomp` `r4/main` (CLAUDE.md, fork model). Every change
that fork carries over upstream master is listed here with its upstream PR.
When this table is empty, re-pin to upstream master and archive the fork.

| Change | Topic branch | Upstream PR | State |
|---|---|---|---|
| Windows GL wall-clock pacing (NVIDIA + GL + render thread) | `fix/windows-gl-dwm-vsync` | #723 | review fixes pushed |
| DuckStation pack: no quadratic work per VRAM write | `fix/duck-retire-linear` | #732 | open, CI green |
| Windows: independent sleeper timers | `fix/windows-sleeper-timers` | #733 | open, CI green |
| `supersample_disable_at_lines` | `feat/supersample-display-policy` | #734 | open, CI green |
| PGXP: full depth, unclamped XY far | `fix/pgxp-far-projection` | #735 | open, CI green |
| HD pack preload (bounded) | `feat/hd-preload` | #736 | review fixes pushed |
| Live internal resolution / supersampling | `feat/live-resolution` | #737 | review fixes pushed |
| Dynres: hold through savestate load | `r4/main` commit `ade1ecd3` | none yet | needs topic branch + PR |
| Host HUD layer (yacineolivier-maker) | PR head | #710 | open |
| Postfx depth / history / live uniforms (yacineolivier-maker) | PR head | #716 | open |
| Transactional render passes (60 fps) | `feat/render-pass-hd` | #727 | split per review |
