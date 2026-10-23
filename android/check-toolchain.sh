#!/usr/bin/env bash
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
if [[ -z "${ANDROID_NDK_HOME:-}" ]]; then
    echo "ANDROID_NDK_HOME must point to the Android NDK selected for the build." >&2
    exit 2
fi

case "$(uname -s)" in
    Linux) HOST_TAG=linux-x86_64 ;;
    Darwin) HOST_TAG=darwin-x86_64 ;;
    *) echo "Run the Android toolchain probe on Linux or macOS." >&2; exit 2 ;;
esac
COMPILER="${ANDROID_NDK_HOME}/toolchains/llvm/prebuilt/${HOST_TAG}/bin/aarch64-linux-android28-clang++"
if [[ ! -x "${COMPILER}" ]]; then
    echo "Missing Android ARM64 API 28 C++ compiler: ${COMPILER}" >&2
    exit 2
fi

PROBE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/nouraajd-android-toolchain.XXXXXX")"
PROBE_BINARY="${PROBE_DIR}/toolchain"
trap 'rm -f -- "${PROBE_BINARY}"; rmdir -- "${PROBE_DIR}"' EXIT

"${COMPILER}" -std=c++26 -Wall -Wextra -pedantic-errors -pthread -fPIE -pie \
    -I"${REPO_ROOT}/vstd" "${SCRIPT_DIR}/tests/toolchain.cpp" -o "${PROBE_BINARY}"
echo "Android C++26 and move-only callback compile/link probe passed (ARM64, API 28)."
