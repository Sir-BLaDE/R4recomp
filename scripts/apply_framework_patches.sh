#!/bin/bash
# Apply the R4 framework patches (patches/psxrecomp/*.patch) to the psxrecomp
# submodule at the pinned commit. Idempotent: already-applied patches are
# skipped.
set -e
cd "$(dirname "$0")/.."
for p in patches/psxrecomp/*.patch; do
    if git -C psxrecomp apply --reverse --check "../$p" 2>/dev/null; then
        echo "already applied: $p"
    else
        git -C psxrecomp apply "../$p" && echo "applied: $p"
    fi
done
