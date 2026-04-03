#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-cmake-build-coverage}"
MIN_COVERAGE="${MIN_COVERAGE:-80}"
REPORT_DIR="${ROOT_DIR}/coverage"

cd "${ROOT_DIR}"

cmake_args=(
    --fresh
    -S . -B "${BUILD_DIR}" -G Ninja
    -DCMAKE_BUILD_TYPE=Debug
    -DCMAKE_CXX_COMPILER_LAUNCHER=
    -DCMAKE_CXX_FLAGS=--coverage
    -DCMAKE_EXE_LINKER_FLAGS=--coverage
    -DCMAKE_SHARED_LINKER_FLAGS=--coverage
)

cmake "${cmake_args[@]}"

cmake --build "${BUILD_DIR}" --target _game for_unit_tests -j"$(nproc)"

find "${BUILD_DIR}" -name '*.gcda' -delete
ctest --test-dir "${BUILD_DIR}" --output-on-failure
GAME_BUILD_DIR="${BUILD_DIR}" python3 test.py

mkdir -p "${REPORT_DIR}"

if command -v gcovr >/dev/null 2>&1; then
    # gcov can emit negative branch counts for some files; keep reporting and the line gate intact.
    gcovr \
        --root "${ROOT_DIR}" \
        --object-directory "${BUILD_DIR}" \
        --gcov-ignore-errors source_not_found --gcov-ignore-errors no_working_dir_found \
        --gcov-ignore-parse-errors negative_hits.warn_once_per_file \
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
else
    python3 "${ROOT_DIR}/scripts/coverage_report.py" \
        --root "${ROOT_DIR}" \
        --build-dir "${BUILD_DIR}" \
        --report-dir "${REPORT_DIR}" \
        --min-line "${MIN_COVERAGE}"
fi

echo "Coverage reports written to ${REPORT_DIR}/coverage.txt and ${REPORT_DIR}/coverage.html"
