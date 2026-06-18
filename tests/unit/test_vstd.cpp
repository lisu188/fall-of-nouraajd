/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#include "core/CUtil.h"
#include "test_harness.h"
#include "vcache.h"
#include "vfunctional.h"
#include "vutil.h"

#include <list>
#include <memory>
#include <queue>
#include <set>
#include <string>
#include <typeindex>
#include <vector>

namespace {

int cache_value_calls = 0;

int next_cache_value() { return ++cache_value_calls; }

int cache_ttl() { return 5; }

struct CastBase {
    virtual ~CastBase() = default;
};

struct CastDerived : CastBase {};

void test_cache_helpers_reuse_and_expire_values() {
    cache_value_calls = 0;
    vstd::cache<std::string, int, next_cache_value, cache_ttl> cache;
    expect_true(cache.get("alpha", 10) == 1, "cache should populate a missing value");
    expect_true(cache.get("alpha", 12) == 1, "cache should reuse values before ttl expiry");
    expect_true(cache.get("alpha", 20) == 2, "cache should refresh values after ttl expiry");

    int callback_calls = 0;
    vstd::cache2<std::string, int, cache_ttl> callback_cache;
    auto callback = [&]() { return ++callback_calls; };
    expect_true(callback_cache.get("beta", 1, callback) == 1, "cache2 should populate from callback");
    expect_true(callback_cache.get("beta", 3, callback) == 1, "cache2 should reuse callback values before ttl expiry");
    expect_true(callback_cache.get("beta", 8, callback) == 2, "cache2 should refresh callback values after ttl expiry");
}

void test_functional_helpers_transform_iterate_and_group() {
    int void_call_result = 0;
    vstd::functional::call([&]() { void_call_result = 4; });
    expect_true(void_call_result == 4, "functional::call should invoke void callables");
    expect_true(vstd::functional::call([](int value) { return value * 2; }, 5) == 10,
                "functional::call should return non-void callable results");

    std::set<int> numbers{1, 2, 3, 4};
    auto labels = vstd::functional::map<std::set<std::string>>(
        numbers, [](int value) { return value % 2 == 0 ? "even" : "odd"; });
    expect_true(labels == std::set<std::string>({"even", "odd"}), "functional::map should transform into return set");

    int foreach_sum = 0;
    vstd::functional::foreach (numbers, [&](int value) { foreach_sum += value; });
    expect_true(foreach_sum == 10, "functional::foreach should visit every value");
    expect_true(vstd::functional::sum<int>(numbers) == 10, "functional::sum should add plain values");
    expect_true(vstd::functional::sum<int>(numbers, [](int value) { return value * 3; }) == 30,
                "functional::sum should add mapped values");

    auto grouped =
        vstd::functional::map_reduce<std::string>(numbers, [](int value) { return value % 2 == 0 ? "even" : "odd"; });
    expect_true(grouped["even"] == std::set<int>({2, 4}), "map_reduce should group even values");
    expect_true(grouped["odd"] == std::set<int>({1, 3}), "map_reduce should group odd values");
}

void test_vstd_container_and_pointer_helpers() {
    std::set<int> ordered{1, 2, 3};
    expect_true(*vstd::any(ordered) == 1, "any should return the first available element");
    expect_true(vstd::ctn(ordered, 2), "ctn should find values in set-like containers");

    std::string text = "abc";
    expect_true(vstd::ctn(text, 'b'), "ctn should find values in strings");

    std::vector<int> values{2, 4, 6};
    expect_true(vstd::ctn(values, 3, [](int target, int value) { return target * 2 == value; }),
                "ctn with comparator should use custom matching");
    expect_true(vstd::ctn_pred(values, [](int value) { return value == 4; }), "ctn_pred should use custom predicates");
    expect_true(*vstd::find_if(values, [](int value) { return value > 4; }) == 6,
                "find_if should return the first predicate match");

    int executed = 0;
    vstd::execute_if(values, [](int value) { return value == 4; }, [&](int value) { executed = value; });
    expect_true(executed == 4, "execute_if should run a callback for matching values");

    vstd::erase(values, 4, [](int left, int right) { return left == right; });
    expect_true(values == std::vector<int>({2, 6}), "erase should remove the first comparator match");
    vstd::erase_if(values, [](int value) { return value == 2; });
    expect_true(values == std::vector<int>({6}), "erase_if should remove the first predicate match");

    std::vector<int> indexed{10, 20, 30};
    const std::vector<int> const_indexed{40, 50};
    expect_true(*vstd::get(indexed, 1) == 20, "get should return a pointer for a valid mutable index");
    expect_true(vstd::get(indexed, -1) == nullptr, "get should reject negative mutable indexes");
    expect_true(*vstd::get(const_indexed, 0) == 40, "get should return a pointer for a valid const index");
    expect_true(vstd::get(const_indexed, 3) == nullptr, "get should reject out-of-bounds const indexes");

    std::shared_ptr<CastBase> base = std::make_shared<CastDerived>();
    expect_true(vstd::castable<CastDerived>(base), "castable should detect dynamic shared pointer casts");
    expect_true(vstd::type_pair<int, std::string>() ==
                    std::make_pair(std::type_index(typeid(int)), std::type_index(typeid(std::string))),
                "type_pair should return a pair of type indexes");
}

void test_vstd_queue_collection_and_function_helpers() {
    auto bound = vstd::bind([](int left, int right) { return left + right; }, 2, 3);
    expect_true(bound() == 5, "bind should store function arguments");

    auto unary = vstd::make_function([](int value) { return value + 1; });
    auto nullary = vstd::make_function([]() { return 9; });
    expect_true(unary(4) == 5, "make_function should wrap unary callables");
    expect_true(nullary() == 9, "make_function should wrap nullary callables");

    std::queue<int> queue;
    queue.push(7);
    expect_true(vstd::pop(queue) == 7, "pop should remove queue front values");

    std::priority_queue<int> priority_queue;
    priority_queue.push(3);
    priority_queue.push(9);
    expect_true(vstd::pop_p(priority_queue) == 9, "pop_p should remove priority queue top values");

    vstd::list<int> custom_list;
    custom_list.insert(4);
    expect_true(custom_list.front() == 4, "vstd::list::insert should append values");

    vstd::blocking_queue<int> blocking_queue;
    blocking_queue.push(11);
    int popped = 0;
    expect_true(blocking_queue.pop(popped) && popped == 11, "blocking_queue should pop queued values");
    blocking_queue.shutdown();
    expect_true(!blocking_queue.pop(popped), "blocking_queue should stop popping after shutdown");
    blocking_queue.reset();
    blocking_queue.push(12);
    expect_true(blocking_queue.pop(popped) && popped == 12, "blocking_queue reset should accept new values");
}

void test_vstd_allocation_random_and_value_helpers() {
    auto allocated = vstd::allocate<int>(2);
    allocated[0] = 3;
    allocated[1] = 4;
    expect_true(allocated[0] + allocated[1] == 7, "allocate should return writable storage");
    vstd::deallocate(allocated, 2);

    std::vector<int> array_source{5, 6};
    auto array = vstd::as_array(array_source);
    expect_true(array[0] == 5 && array[1] == 6, "as_array should copy vector values into allocated storage");
    vstd::deallocate(array, array_source.size());

    int observed = 0;
    auto pointer = std::make_shared<int>(13);
    vstd::if_not_null(pointer, [&](auto value) { observed = *value; });
    vstd::if_not_null(std::shared_ptr<int>(), [&](auto) { observed = -1; });
    expect_true(observed == 13, "if_not_null should only invoke callbacks for populated pointers");

    expect_true(vstd::percent(80, 25) == 20, "percent should compute a percentage of a value");
    expect_true(vstd::with<int>(pointer, [](auto value) { return *value + 1; }) == 14,
                "with should return callback values for populated pointers");
    expect_true(vstd::with<int>(std::shared_ptr<int>(), [](auto) { return 99; }) == 0,
                "with should return a default value for empty pointers");

    int void_with_value = 0;
    vstd::with<void>(pointer, [&](auto value) { void_with_value = *value; });
    expect_true(void_with_value == 13, "with<void> should run callbacks for populated pointers");

    expect_true(vstd::all_equals(3, 3, 3), "all_equals should accept matching values");
    expect_true(!vstd::all_equals(3, 4, 3), "all_equals should reject differing values");
    expect_true(vstd::set(1) == std::set<int>({1}), "set should build a std::set");
    expect_true(vstd::as_list(1).front() == 1, "as_list should build a std::list");

    std::set<int> old_values{1, 2};
    std::set<int> new_values{2, 3};
    auto [to_add, to_remove] = vstd::set_difference(old_values, new_values);
    expect_true(to_add == std::set<int>({3}) && to_remove == std::set<int>({1}),
                "set_difference should identify additions and removals");

    std::set<int> empty_choices;
    std::set<int> single_choice{42};
    expect_true(vstd::random_element(empty_choices) == empty_choices.end(),
                "random_element should return end for empty containers");
    expect_true(*vstd::random_element(single_choice) == 42, "random_element should return the only available element");

    auto components = vstd::random_components(5, std::set<int>({1, 2}));
    expect_true(vstd::functional::sum<int>(components) == 5, "random_components should decompose the requested value");
    expect_true(vstd::square_ctn(10, 10, 9, 0), "square_ctn should accept coordinates inside bounds");
    expect_true(!vstd::square_ctn(10, 10, 10, 0), "square_ctn should reject coordinates outside bounds");
}

void test_vstd_string_helpers() {
    expect_true(vstd::str(Coords(1, 2, 3)) == "1,2,3", "vstd::str should use the Coords specialization");
    expect_true(vstd::replace("red red", "red", "blue") == "blue blue", "replace should handle repeated matches");
    expect_true(vstd::trim("  text\t") == "text", "trim should remove surrounding whitespace");
    expect_true(vstd::is_empty(" \t"), "is_empty should treat whitespace as empty");
    expect_true(vstd::str("a", 1, "b") == "a1b", "variadic str should concatenate stringified values");
    expect_true(vstd::to_int("42").first == 42 && vstd::to_int("42").second, "to_int should parse integers");
    expect_true(!vstd::to_int("42x").second, "to_int should reject partially parsed integers");
    expect_true(!vstd::is_int("x"), "is_int should reject non-numeric strings");
    expect_true(vstd::join(std::list<std::string>{"a", "b"}, ",") == "a,b", "join should use separators");
    expect_true(vstd::split("a:b", ':') == std::vector<std::string>({"a", "b"}), "split should split on delimiter");
    expect_true(vstd::string_equals(5, "5"), "string_equals should compare stringified values");
    expect_true(vstd::ends_with("report.txt", ".txt"), "ends_with should detect matching suffixes");
    expect_true(!vstd::ends_with("txt", "report.txt"), "ends_with should reject longer suffixes");

    auto wide = vstd::to_wchar("abc");
    expect_true(wide[0] == L'a' && wide[2] == L'c', "to_wchar should convert narrow text");
    delete[] wide;

    const char *args[] = {"one", "two"};
    auto wide_args = vstd::to_wchar(2, args);
    expect_true(wide_args[0][0] == L'o' && wide_args[1][0] == L't', "to_wchar should convert argument arrays");
    delete[] wide_args[0];
    delete[] wide_args[1];
    delete[] wide_args;

    std::string lines = "first";
    vstd::add_line(lines, "second");
    vstd::add_line(lines, "");
    expect_true(lines == "first\nsecond", "add_line should append non-empty lines only");
    expect_true(vstd::camel("hello world") == "Hello World ", "camel should title-case space-separated words");
}

} // namespace

int main() {
    test_cache_helpers_reuse_and_expire_values();
    test_functional_helpers_transform_iterate_and_group();
    test_vstd_container_and_pointer_helpers();
    test_vstd_queue_collection_and_function_helpers();
    test_vstd_allocation_random_and_value_helpers();
    test_vstd_string_helpers();

    return finish_tests();
}
