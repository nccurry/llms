#!/usr/bin/env sh
# Point mise's shims at the checkout that owns them.
#
# After any `mise install`, mise rebuilds every shim in $MISE_DATA_DIR/shims to point at the
# `mise` that comes first on PATH. A worktree may share another checkout's .tools/mise/data
# through a symbolic link; that other checkout then owns the shims, and they must keep pointing at
# its mise, which does not disappear when the worktree is removed. When the data directory is
# a link, this runs the owning checkout's mise (the one at <owner>/.tools/bin/mise) first on PATH
# to rebuild the shims. Otherwise the checkout owns its shims, and its own mise rebuilds them.
#
# Usage: MISE_DATA_DIR=... reshim_shared_data.sh <path to this checkout's mise>
set -eu
mise_bin=$1
data_dir=${MISE_DATA_DIR:?MISE_DATA_DIR must be set}
if [ ! -L "$data_dir" ]; then
    PATH="$(dirname -- "$mise_bin"):$PATH" "$mise_bin" reshim
    exit 0
fi
# <owner>/.tools/mise/data -> <owner>/.tools/bin
owner_data=$(cd -P -- "$data_dir" 2>/dev/null && pwd -P) || owner_data=
owner_bin=
if [ -n "$owner_data" ]; then owner_bin=$(cd -P -- "$owner_data/../../bin" 2>/dev/null && pwd -P) || owner_bin=; fi
if [ -n "$owner_bin" ] && [ -x "$owner_bin/mise" ]; then
    PATH="$owner_bin:$PATH" "$owner_bin/mise" reshim
else
    printf 'reshim_shared_data: no mise next to the shared data directory; shims left unchanged.\n' >&2
fi
