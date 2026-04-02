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

python3 "${ROOT_DIR}/scripts/coverage_report.py" \
    --root "${ROOT_DIR}" \
    --build-dir "${BUILD_DIR}" \
    --report-dir "${REPORT_DIR}" \
    --min-line "${MIN_COVERAGE}"

echo "Coverage reports written to ${REPORT_DIR}/coverage.txt and ${REPORT_DIR}/coverage.html"
