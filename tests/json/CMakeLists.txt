# Copyright (C) 2026 Andrzej Lis
# Standalone JSON checks intentionally avoid SDL, Python and the full game build.
cmake_minimum_required(VERSION 3.20)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(nouraajd_json_checks LANGUAGES CXX)
    enable_testing()
endif()

get_filename_component(GAME_JSON_DEFAULT_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
set(GAME_JSON_REPO_ROOT "${GAME_JSON_DEFAULT_ROOT}" CACHE PATH "Game source root for focused JSON checks")
find_package(Threads REQUIRED)

if(TARGET simdjson_vendor)
    set(GAME_JSON_SIMDJSON_TARGET simdjson_vendor)
else()
    add_library(json_check_simdjson STATIC "${GAME_JSON_REPO_ROOT}/third_party/simdjson/simdjson.cpp")
    target_compile_features(json_check_simdjson PUBLIC cxx_std_17)
    target_include_directories(json_check_simdjson SYSTEM PUBLIC "${GAME_JSON_REPO_ROOT}/third_party/simdjson")
    set(GAME_JSON_SIMDJSON_TARGET json_check_simdjson)
endif()

add_library(json_check_adapter STATIC "${GAME_JSON_REPO_ROOT}/src/core/CJson.cpp")
target_compile_features(json_check_adapter PUBLIC cxx_std_17)
target_compile_definitions(json_check_adapter PUBLIC GAME_JSON_DIAGNOSTICS)
target_include_directories(json_check_adapter PUBLIC "${GAME_JSON_REPO_ROOT}/src")
target_link_libraries(json_check_adapter PUBLIC ${GAME_JSON_SIMDJSON_TARGET})

add_executable(json_parse_regression JsonParseRegression.cpp LegacyJsonParser.cpp)
target_link_libraries(json_parse_regression PRIVATE json_check_adapter Threads::Threads)
add_test(NAME for_unit_tests.json_parse_regression COMMAND json_parse_regression)
set_tests_properties(for_unit_tests.json_parse_regression PROPERTIES LABELS "for_unit_tests;unit;json" TIMEOUT 60)
add_test(NAME json_parse_performance COMMAND json_parse_regression --performance)
set_tests_properties(json_parse_performance PROPERTIES LABELS "performance;json" TIMEOUT 20)

# Opt-in: compile the adapter without diagnostic counters for timing evidence.
add_executable(json_parse_benchmark EXCLUDE_FROM_ALL JsonParseBenchmark.cpp LegacyJsonParser.cpp
    "${GAME_JSON_REPO_ROOT}/src/core/CJson.cpp")
target_compile_features(json_parse_benchmark PRIVATE cxx_std_17)
target_include_directories(json_parse_benchmark PRIVATE "${GAME_JSON_REPO_ROOT}/src")
target_link_libraries(json_parse_benchmark PRIVATE ${GAME_JSON_SIMDJSON_TARGET})
if(WIN32)
    target_link_libraries(json_parse_benchmark PRIVATE Psapi)
endif()
