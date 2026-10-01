#!/usr/bin/env bash
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

root=$(cd "$(dirname "$0")/../.." && pwd)
git_args=(-C "$root")
if ! git "${git_args[@]}" rev-parse --show-toplevel >/dev/null 2>&1; then
    # A Windows-managed worktree stores a drive-letter gitdir that Linux Git cannot interpret.
    # Resolve that pointer explicitly under WSL without changing the checkout's metadata.
    if [[ -f "$root/.git" ]] && command -v wslpath >/dev/null 2>&1; then
        git_directory=$(sed -n 's/^gitdir: //p' "$root/.git" | tr -d '\r')
        if [[ "$git_directory" =~ ^[A-Za-z]:[\\/] ]]; then
            git_args=(--git-dir="$(wslpath -u "$git_directory")" --work-tree="$root")
        fi
    fi
fi
root=$(git "${git_args[@]}" rev-parse --show-toplevel)
baseline=${1:?Usage: run-callgrind.sh BASELINE_COMMIT [OUTPUT_DIRECTORY]}
baseline=$(git "${git_args[@]}" rev-parse --verify "$baseline^{commit}")
output=${2:-"$root/cmake-build-release/navigation-callgrind"}
mkdir -p "$output"
output=$(realpath "$output")
# Keep compile inputs on the native Linux filesystem, including when the checkout is on a WSL mount.
# Retain the workspace for inspection; its exact location is recorded with the results.
workspace=$(mktemp -d "${TMPDIR:-/tmp}/nouraajd-navigation-callgrind.XXXXXX")
mkdir -p "$workspace/baseline" "$workspace/current"
printf 'baseline=%s\nworkspace=%s\n' "$baseline" "$workspace" | tee "$output/provenance.txt"
git "${git_args[@]}" archive "$baseline" src | tar -xf - -C "$workspace/baseline"
python3 - "$root" "$workspace" <<'PY'
import os
import shutil
import sys
from pathlib import Path

root, workspace = map(Path, sys.argv[1:])
for directory in ("src", "vstd", "random-dungeon-generator", "third_party/simdjson", "third_party/lua"):
    for base, directories, files in os.walk(root / directory):
        directories[:] = [name for name in directories if name not in {".git", "build", "__pycache__"}]
        for name in files:
            source = Path(base) / name
            if source.suffix not in {".h", ".hpp", ".cpp", ".c", ".inl", ".tpp"}:
                continue
            destination = workspace / "current" / source.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
shutil.copyfile(root / "scripts/navigation_profile/callgrind.cpp", workspace / "profile.cpp")
PY

cxx=${CXX:-g++}
read -r -a python_includes <<< "$(python3 -m pybind11 --includes)"
read -r -a sdl_flags <<< "$(pkg-config --cflags sdl2 SDL2_image SDL2_ttf)"
read -r -a libraries <<< "$(pkg-config --libs sdl2 SDL2_image SDL2_ttf) $(python3-config --embed --ldflags)"
current="$workspace/current"
old="$workspace/baseline/src"
flags=(-std=c++23 -O2 -g -ffunction-sections -fdata-sections -DBOOST_ALLOW_DEPRECATED_HEADERS
    -DBOOST_BIND_GLOBAL_PLACEHOLDERS -DSDL_MAIN_HANDLED -I"$current/vstd"
    -I"$current/random-dungeon-generator" -I"$current/third_party/simdjson" -I"$current/third_party/lua"
    "${python_includes[@]}" "${sdl_flags[@]}")

{
    "$cxx" --version
    valgrind --version
    python3 --version
    git "${git_args[@]}" rev-parse HEAD
    git "${git_args[@]}" ls-tree "$baseline" vstd random-dungeon-generator
    git "${git_args[@]}" ls-files --stage vstd random-dungeon-generator
} > "$output/toolchain.txt"

# Unused map/service functions are discarded. These executables exercise only the real callback API,
# not a fake map implementation, initialized game, packaged resources, window or full engine build.
"$cxx" "${flags[@]}" -I"$old" -I"$old/core" "$workspace/profile.cpp" "$old/core/CPathFinder.cpp" \
    "$old/core/CFuture.cpp" -Wl,--gc-sections "${libraries[@]}" -o "$workspace/before" \
    > "$output/build-before.log" 2>&1
"$cxx" "${flags[@]}" -I"$current/src" -I"$current/src/core" "$workspace/profile.cpp" \
    "$current/src/core/CPathFinder.cpp" "$current/src/core/CNavigationSearch.cpp" \
    "$current/src/core/CNavigation.cpp" "$current/src/core/CFuture.cpp" \
    -Wl,--gc-sections "${libraries[@]}" -o "$workspace/after" > "$output/build-after.log" 2>&1

(
    cd "$workspace"
    sha256sum profile.cpp baseline/src/core/{CPathFinder,CFuture}.cpp \
        current/src/core/{CPathFinder,CNavigationSearch,CNavigation}.{h,cpp} > "$output/source-sha256.txt"
    for version in before after; do
        SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy SDL_RENDER_DRIVER=software LIBGL_ALWAYS_SOFTWARE=1 \
            valgrind --tool=callgrind --instr-atstart=no --callgrind-out-file="$version.callgrind" \
            "./$version" > "$output/$version-output.txt" 2> "$output/$version-valgrind.txt"
        cp "$version.callgrind.1" "$output/$version.callgrind.1"
        callgrind_annotate --auto=no --inclusive=no --threshold=75 "$version.callgrind.1" \
            > "$output/$version-annotated.txt"
        cat "$output/$version-output.txt"
        tail -4 "$output/$version-valgrind.txt"
    done
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy SDL_RENDER_DRIVER=software LIBGL_ALWAYS_SOFTWARE=1 \
        valgrind --tool=memcheck --leak-check=full --show-leak-kinds=all \
        --errors-for-leak-kinds=definite,indirect --error-exitcode=97 ./after \
        > "$output/after-memcheck-output.txt" 2> "$output/after-memcheck.txt"
    tail -12 "$output/after-memcheck.txt"
)
printf 'Reports: %s\nRetained build workspace: %s\n' "$output" "$workspace"
