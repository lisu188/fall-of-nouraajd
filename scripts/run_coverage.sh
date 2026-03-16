#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-cmake-build-coverage}"
MIN_COVERAGE="${MIN_COVERAGE:-80}"
REPORT_DIR="${ROOT_DIR}/coverage"

cd "${ROOT_DIR}"

cmake -S . -B "${BUILD_DIR}" -G Ninja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
    -DCMAKE_CXX_FLAGS='--coverage' \
    -DCMAKE_EXE_LINKER_FLAGS='--coverage' \
    -DCMAKE_SHARED_LINKER_FLAGS='--coverage'

cmake --build "${BUILD_DIR}" --target _game -j"$(nproc)"

find "${BUILD_DIR}" -name '*.gcda' -delete
GAME_BUILD_DIR="${BUILD_DIR}" python3 test.py

mkdir -p "${REPORT_DIR}"

gcovr \
    --root "${ROOT_DIR}" \
    --object-directory "${BUILD_DIR}" \
    --gcov-ignore-errors source_not_found --gcov-ignore-errors no_working_dir_found \
    --filter "${ROOT_DIR}/src/core" \
    --filter "${ROOT_DIR}/src/handler" \
    --filter "${ROOT_DIR}/src/object" \
    --exclude "${ROOT_DIR}/src/gui" \
    --exclude "${ROOT_DIR}/vstd" \
    --exclude "${ROOT_DIR}/random-dungeon-generator" \
    --exclude "${ROOT_DIR}/src/core/CModule.cpp" \
    --exclude "${ROOT_DIR}/src/core/CWrapper.h" \
    --exclude "${ROOT_DIR}/src/core/CTypes.cpp" \
    --exclude "${ROOT_DIR}/src/core/CTypes.h" \
    --exclude "${ROOT_DIR}/src/core/CJsonUtil.h" \
    --exclude "${ROOT_DIR}/cmake-build.*" \
    --exclude "${ROOT_DIR}/build.*" \
    --exclude "${ROOT_DIR}/package.*" \
    --print-summary \
    --txt "${REPORT_DIR}/coverage.txt" \
    --html-details "${REPORT_DIR}/coverage.html" \
    --fail-under-line "${MIN_COVERAGE}"

echo "Coverage reports written to ${REPORT_DIR}/coverage.txt and ${REPORT_DIR}/coverage.html"
