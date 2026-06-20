#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-cmake-build-coverage}"
MIN_COVERAGE="${MIN_COVERAGE:-95}"
REPORT_DIR="${ROOT_DIR}/coverage"
COVERAGE_INCLUDE_PREFIXES="${COVERAGE_INCLUDE_PREFIXES:-src native_plugins}"
COVERAGE_JOBS="${COVERAGE_JOBS:-$(nproc)}"
COVERAGE_REPORTER="${COVERAGE_REPORTER:-python}"
COVERAGE_PYTHON_TIMEOUT_SECONDS="${COVERAGE_PYTHON_TIMEOUT_SECONDS:-1800}"
COVERAGE_GCOV_TIMEOUT_SECONDS="${COVERAGE_GCOV_TIMEOUT_SECONDS:-120}"
GAME_TEST_JOBS="${GAME_TEST_JOBS:-${COVERAGE_JOBS}}"
GAME_XVFB_JOBS="${GAME_XVFB_JOBS:-4}"
GAME_TEST_OUTPUT_DIR="${GAME_TEST_OUTPUT_DIR:-${REPORT_DIR}/test-output}"
SCRIPT_START=${SECONDS}

cd "${ROOT_DIR}"

if [[ ! "${COVERAGE_JOBS}" =~ ^[1-9][0-9]*$ ]]; then
    echo "COVERAGE_JOBS must be a positive integer, got: ${COVERAGE_JOBS}" >&2
    exit 2
fi
if [[ ! "${GAME_TEST_JOBS}" =~ ^[1-9][0-9]*$ ]]; then
    echo "GAME_TEST_JOBS must be a positive integer, got: ${GAME_TEST_JOBS}" >&2
    exit 2
fi
if [[ ! "${GAME_XVFB_JOBS}" =~ ^[1-9][0-9]*$ ]]; then
    echo "GAME_XVFB_JOBS must be a positive integer, got: ${GAME_XVFB_JOBS}" >&2
    exit 2
fi
if [[ ! "${COVERAGE_PYTHON_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]]; then
    echo "COVERAGE_PYTHON_TIMEOUT_SECONDS must be a positive integer, got: ${COVERAGE_PYTHON_TIMEOUT_SECONDS}" >&2
    exit 2
fi
if [[ ! "${COVERAGE_GCOV_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]]; then
    echo "COVERAGE_GCOV_TIMEOUT_SECONDS must be a positive integer, got: ${COVERAGE_GCOV_TIMEOUT_SECONDS}" >&2
    exit 2
fi
if [[ -v COVERAGE_LINE_EXCLUSIONS && -n "${COVERAGE_LINE_EXCLUSIONS}" ]]; then
    echo "COVERAGE_LINE_EXCLUSIONS is no longer supported; line coverage exclusions are disallowed." >&2
    exit 2
fi
if [[ -v COVERAGE_AUDIT_EXCLUSIONS && "${COVERAGE_AUDIT_EXCLUSIONS}" != "0" ]]; then
    echo "COVERAGE_AUDIT_EXCLUSIONS is no longer supported; line coverage exclusions are disallowed." >&2
    exit 2
fi

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

run_with_timeout() {
    local timeout_seconds="$1"
    shift

    if ! command -v timeout >/dev/null 2>&1; then
        echo "warning: timeout command not found; running without outer timeout" >&2
        "$@"
        return
    fi

    timeout --kill-after=30s "${timeout_seconds}s" "$@"
}

list_recent_test_artifacts() {
    if [[ ! -d "${GAME_TEST_OUTPUT_DIR}" ]]; then
        echo "No test output directory was created at ${GAME_TEST_OUTPUT_DIR}" >&2
        return
    fi

    echo "Recent test output files under ${GAME_TEST_OUTPUT_DIR}:" >&2
    find "${GAME_TEST_OUTPUT_DIR}" -maxdepth 4 -type f -printf '%T@ %p\n' 2>/dev/null \
        | sort -n \
        | tail -n 40 \
        | cut -d' ' -f2- >&2 || true
}

cmake_launcher_args=()
if [[ -v COVERAGE_CXX_COMPILER_LAUNCHER ]]; then
    cmake_launcher_args=(-DCMAKE_CXX_COMPILER_LAUNCHER="${COVERAGE_CXX_COMPILER_LAUNCHER}")
elif command -v ccache >/dev/null 2>&1; then
    cmake_launcher_args=(-DCMAKE_CXX_COMPILER_LAUNCHER=ccache)
fi

cmake_args=(
    -S . -B "${BUILD_DIR}" -G Ninja
    -DCMAKE_BUILD_TYPE=Debug
    "${cmake_launcher_args[@]}"
    -DCMAKE_CXX_FLAGS=--coverage
    -DCMAKE_EXE_LINKER_FLAGS=--coverage
    -DCMAKE_SHARED_LINKER_FLAGS=--coverage
)
if [[ "${COVERAGE_FRESH_CONFIGURE:-0}" == "1" ]]; then
    cmake_args=(--fresh "${cmake_args[@]}")
fi

generate_report() {
    mkdir -p "${REPORT_DIR}" || return

    if [[ "${COVERAGE_REPORTER}" == "gcovr" ]]; then
        if ! command -v gcovr >/dev/null 2>&1; then
            echo "COVERAGE_REPORTER=gcovr requested, but gcovr was not found" >&2
            return 2
        fi

        gcovr_args=()
        gcovr_help="$(gcovr --help 2>/dev/null || true)"
        if grep -q -- "--gcov-parallel" <<<"${gcovr_help}"; then
            gcovr_args+=(--gcov-parallel "${COVERAGE_JOBS}")
        elif grep -q -- "-j \\[GCOV_PARALLEL\\]" <<<"${gcovr_help}"; then
            gcovr_args+=(-j "${COVERAGE_JOBS}")
        fi
        if grep -q -- "--merge-lines" <<<"${gcovr_help}"; then
            gcovr_args+=(--merge-lines)
        fi
        if grep -q -- "--merge-mode-functions" <<<"${gcovr_help}"; then
            gcovr_args+=(--merge-mode-functions merge-use-line-min)
        fi

        # Detailed HTML needs every generated native source file to exist at report time.
        # Summary HTML keeps the line gate intact without failing on those transient paths.
        # gcov can emit negative branch counts for some files; keep reporting and the line gate intact.
        gcovr \
            "${gcovr_args[@]}" \
            --root "${ROOT_DIR}" \
            --object-directory "${BUILD_DIR}" \
            --gcov-ignore-errors source_not_found --gcov-ignore-errors no_working_dir_found \
            --gcov-ignore-parse-errors negative_hits.warn_once_per_file \
            --print-summary \
            --txt "${REPORT_DIR}/coverage.txt" \
            --html "${REPORT_DIR}/coverage.html" \
            --fail-under-line "${MIN_COVERAGE}" || return
    elif [[ "${COVERAGE_REPORTER}" == "python" ]]; then
        coverage_report_args=(
            --root "${ROOT_DIR}"
            --build-dir "${BUILD_DIR}"
            --report-dir "${REPORT_DIR}"
            --min-line "${MIN_COVERAGE}"
            --jobs "${COVERAGE_JOBS}"
            --gcov-timeout "${COVERAGE_GCOV_TIMEOUT_SECONDS}"
        )
        if [[ -n "${COVERAGE_INCLUDE_PREFIXES}" ]]; then
            read -r -a coverage_include_prefixes <<<"${COVERAGE_INCLUDE_PREFIXES}"
            for include_prefix in "${coverage_include_prefixes[@]}"; do
                coverage_report_args+=(--include-prefix "${include_prefix}")
            done
        fi
        python3 "${ROOT_DIR}/scripts/coverage_report.py" \
            "${coverage_report_args[@]}" || return
    else
        echo "Unknown COVERAGE_REPORTER '${COVERAGE_REPORTER}'. Expected 'python' or 'gcovr'." >&2
        return 2
    fi
}

run_python_coverage_tests() {
    mkdir -p "${GAME_TEST_OUTPUT_DIR}"
    run_with_timeout "${COVERAGE_PYTHON_TIMEOUT_SECONDS}" env \
        GAME_BUILD_DIR="${BUILD_DIR}" \
        GAME_COVERAGE_RUN=1 \
        GAME_TEST_JOBS="${GAME_TEST_JOBS}" \
        GAME_XVFB_JOBS="${GAME_XVFB_JOBS}" \
        GAME_TEST_OUTPUT_DIR="${GAME_TEST_OUTPUT_DIR}" \
        python3 test.py --suite coverage-safe --jobs "${GAME_TEST_JOBS}"
    local status=$?
    if [[ "${status}" -eq 124 || "${status}" -eq 137 ]]; then
        echo "Coverage Python test phase timed out or was killed after ${COVERAGE_PYTHON_TIMEOUT_SECONDS}s." >&2
        echo "The bounded command was: python3 test.py --suite coverage-safe --jobs ${GAME_TEST_JOBS}" >&2
        list_recent_test_artifacts
    fi
    return "${status}"
}

run_phase "configure" cmake "${cmake_args[@]}"
run_phase "build _game, for_unit_tests, and performance_guard_tests" \
    cmake --build "${BUILD_DIR}" --target _game for_unit_tests performance_guard_tests -j"${COVERAGE_JOBS}"
run_phase "coverage data cleanup" find "${BUILD_DIR}" -name '*.gcda' -delete
run_phase "ctest" ctest --test-dir "${BUILD_DIR}" --output-on-failure
run_phase "python test suite" run_python_coverage_tests
run_phase "report generation" generate_report

total_elapsed=$((SECONDS - SCRIPT_START))
echo "Coverage reports written to ${REPORT_DIR}/coverage.txt and ${REPORT_DIR}/coverage.html"
log_phase "TOTAL $(format_duration "${total_elapsed}")"
