#!/usr/bin/env sh
# Install the pinned mise tools, unless this checkout shares its mise data directory.
#
# After any `mise install`, mise rebuilds every shim in $MISE_DATA_DIR/shims to point at the
# `mise` that runs it, even when the install then fails part way. A worktree may share another
# checkout's data directory through a symbolic link (at .tools, .tools/mise or .tools/mise/data);
# those shims must keep pointing at the checkout that owns them, which outlives the worktree.
#
# - The data directory physically inside this checkout: run `mise install` with the arguments
#   given, then rebuild the shims with this checkout's own mise.
# - The data directory physically elsewhere: never install. Succeed if `mise ls --missing`
#   (read only) lists none of the tools, and otherwise stop with an error naming the owner.
#
# Usage: MISE_DATA_DIR=... ensure_mise_tools.sh <mise> install [options] [tool...]
# Names that do not start with "-" after `install` are the tools to check; none means all.
set -eu
mise_bin=$1
shift
data_dir=${MISE_DATA_DIR:?MISE_DATA_DIR must be set}
checkout=$(cd -P -- "$(dirname -- "$0")/.." && pwd -P)

# Resolve a path physically (links at any level, relative links, chains), even when the last
# folders do not exist yet: resolve the nearest existing parent and put the rest back.
resolve() {
    rest=
    path=$1
    while [ ! -e "$path" ]; do
        rest=/$(basename -- "$path")$rest
        path=$(dirname -- "$path")
    done
    printf '%s%s\n' "$(cd -P -- "$path" && pwd -P)" "$rest"
}

data_real=$(resolve "$data_dir")
case "$data_real/" in
    "$checkout"/*)
        "$mise_bin" "$@"
        PATH="$(dirname -- "$mise_bin"):$PATH" "$mise_bin" reshim
        exit 0
        ;;
esac

tools=
seen_install=
for argument in "$@"; do
    if [ -z "$seen_install" ]; then seen_install=1; continue; fi
    case "$argument" in -*) ;; *) tools="$tools $argument" ;; esac
done
# The word list is the tool names; none of them has spaces or glob characters.
# shellcheck disable=SC2086
missing=$("$mise_bin" ls --missing $tools)
if [ -z "$missing" ]; then exit 0; fi
owner=${data_real%/.tools/mise/data}
printf '%s\n' "This checkout shares its mise data directory with $owner (it resolves to $data_real)." \
    "These tools are not installed there:" "$missing" \
    "Run ./bootstrap.sh deps:tools in $owner, then try again." >&2
exit 1
