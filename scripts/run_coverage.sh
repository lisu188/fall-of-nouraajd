#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-cmake-build-coverage}"
MIN_COVERAGE="${MIN_COVERAGE:-80}"
REPORT_DIR="${ROOT_DIR}/coverage"
SCRIPT_START=${SECONDS}

cd "${ROOT_DIR}"

format_duration() {
    local elapsed="$1"
    printf "%02d:%02d:%02d" $((elapsed / 3600)) $(((elapsed % 3600) / 60)) $((elapsed % 60))
}

log_phase() {
    printf "[coverage %s] %s\n" "$(date "+%H:%M:%S")" "$*"
}

run_phase() {
    local name="$1"
    shift
    local phase_start=${SECONDS}
    local status=0

    log_phase "START ${name}"
    set +e
    "$@"
    status=$?
    set -e

    local elapsed=$((SECONDS - phase_start))
    if [[ "${status}" -eq 0 ]]; then
        log_phase "DONE ${name} ($(format_duration "${elapsed}"))"
    else
        log_phase "FAIL ${name} ($(format_duration "${elapsed}"), exit ${status})"
    fi
    return "${status}"
}

cmake_args=(
    -S . -B "${BUILD_DIR}" -G Ninja
    -DCMAKE_BUILD_TYPE=Debug
    -DCMAKE_CXX_COMPILER_LAUNCHER=
    -DCMAKE_CXX_FLAGS=--coverage
    -DCMAKE_EXE_LINKER_FLAGS=--coverage
    -DCMAKE_SHARED_LINKER_FLAGS=--coverage
)
if [[ "${COVERAGE_FRESH_CONFIGURE:-0}" == "1" ]]; then
    cmake_args=(--fresh "${cmake_args[@]}")
fi

generate_report() {
    mkdir -p "${REPORT_DIR}" || return

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
            --fail-under-line "${MIN_COVERAGE}" || return
    else
        python3 "${ROOT_DIR}/scripts/coverage_report.py" \
            --root "${ROOT_DIR}" \
            --build-dir "${BUILD_DIR}" \
            --report-dir "${REPORT_DIR}" \
            --min-line "${MIN_COVERAGE}" || return
    fi
}

run_phase "configure" cmake "${cmake_args[@]}"
run_phase "build _game and for_unit_tests" cmake --build "${BUILD_DIR}" --target _game for_unit_tests -j"$(nproc)"
run_phase "coverage data cleanup" find "${BUILD_DIR}" -name '*.gcda' -delete
run_phase "ctest" ctest --test-dir "${BUILD_DIR}" --output-on-failure
run_phase "python test suite" env GAME_BUILD_DIR="${BUILD_DIR}" python3 test.py
run_phase "report generation" generate_report

total_elapsed=$((SECONDS - SCRIPT_START))
echo "Coverage reports written to ${REPORT_DIR}/coverage.txt and ${REPORT_DIR}/coverage.html"
log_phase "TOTAL $(format_duration "${total_elapsed}")"
