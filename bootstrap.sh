#!/usr/bin/env sh
set -eu

# Bootstrap owns mise and Task only. Task owns the rest of the installation.
if [ -z "${LLMS_ORIGINAL_PATH:-}" ]; then
    LLMS_ORIGINAL_PATH=$PATH
    export LLMS_ORIGINAL_PATH
fi
if [ -z "${LLMS_CALLER_CWD:-}" ]; then
    LLMS_CALLER_CWD=$(pwd)
    export LLMS_CALLER_CWD
fi
repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$repo_root"

case "$(uname -s)" in
    Linux) operating_system=linux ;;
    Darwin) operating_system=macos ;;
    *) printf '%s\n' 'Use bootstrap.sh on Linux/macOS or bootstrap.ps1 on Windows.' >&2; exit 1 ;;
esac
case "$(uname -m)" in
    x86_64|amd64) architecture=x64 ;;
    aarch64|arm64) architecture=arm64 ;;
    *) printf 'Unsupported CPU: %s\n' "$(uname -m)" >&2; exit 1 ;;
esac
platform="$operating_system-$architecture"

export MISE_DATA_DIR="$repo_root/.tools/mise/data"
export MISE_CACHE_DIR="$repo_root/.tools/mise/cache"
export MISE_CONFIG_DIR="$repo_root/.tools/mise/config"
export MISE_STATE_DIR="$repo_root/.tools/mise/state"
export MISE_SYSTEM_CONFIG_DIR="$repo_root/.tools/mise/system"
MISE_CEILING_PATHS=$(dirname -- "$repo_root")
export MISE_CEILING_PATHS
export MISE_TMP_DIR="$repo_root/.tools/tmp"
export UV_PYTHON_INSTALL_DIR="$repo_root/.tools/python"
export UV_CACHE_DIR="$repo_root/.tools/uv-cache"
bin_dir="$repo_root/.tools/bin"
mkdir -p "$bin_dir" "$MISE_TMP_DIR"
export PATH="$bin_dir:$PATH"

mise_version=$(sed -n 's/^mise_version = "\([0-9.]*\)"$/\1/p' mise.toml)
if [ -z "$mise_version" ]; then
    printf '%s\n' 'mise.toml must pin vars.mise_version to an exact release.' >&2
    exit 1
fi
mise_bin="$bin_dir/mise"

download() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 3 "$1" -o "$2"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$1" -O "$2"
    else
        printf '%s\n' 'Install curl or wget to download mise.' >&2
        exit 1
    fi
}

check_checksum() {
    if command -v sha256sum >/dev/null 2>&1; then
        actual_checksum=$(sha256sum "$1" | cut -d ' ' -f 1)
    elif command -v shasum >/dev/null 2>&1; then
        actual_checksum=$(shasum -a 256 "$1" | cut -d ' ' -f 1)
    else
        printf '%s\n' 'Install sha256sum or shasum to verify mise.' >&2
        exit 1
    fi
    if [ "$actual_checksum" != "$2" ]; then
        printf '%s\n' 'Release checksum verification failed for mise.' >&2
        exit 1
    fi
}

installed_version=''
if [ -x "$mise_bin" ]; then
    if version_output=$("$mise_bin" --version); then
        installed_version=${version_output%% *}
    fi
fi
if [ "$installed_version" != "$mise_version" ]; then
    temporary_dir=$(mktemp -d "$MISE_TMP_DIR/mise.XXXXXX")
    trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM
    asset="mise-v$mise_version-$platform"
    release="https://github.com/jdx/mise/releases/download/v$mise_version"
    printf 'Installing project-local mise %s\n' "$mise_version"
    download "$release/$asset" "$temporary_dir/mise"
    download "$release/SHASUMS256.txt" "$temporary_dir/checksums"
    checksum=$(awk -v asset="./$asset" '$2 == asset { print $1 }' "$temporary_dir/checksums")
    if [ -z "$checksum" ]; then
        printf 'No release checksum for %s\n' "$asset" >&2
        exit 1
    fi
    check_checksum "$temporary_dir/mise" "$checksum"
    chmod +x "$temporary_dir/mise"
    mv "$temporary_dir/mise" "$mise_bin"
    rm -rf "$temporary_dir"
    trap - EXIT HUP INT TERM
fi

"$mise_bin" trust --yes --quiet mise.toml
"$mise_bin" install task --locked --quiet

# This optional PATH entry forwards ordinary Task calls through the pinned runtime.
if [ ! -f "$bin_dir/task" ]; then
    cat > "$bin_dir/task" <<'TASK_COMMAND'
#!/usr/bin/env sh
set -eu
repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
if [ "$#" -eq 0 ]; then set -- default; fi
exec "$repo_root/bootstrap.sh" "$@"
TASK_COMMAND
    chmod +x "$bin_dir/task"
fi

if [ "$#" -eq 0 ]; then set -- deps:install; fi
exec "$mise_bin" exec -- task "$@"
