/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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
#pragma once

#include "core/CGlobal.h"

class CGameEvent;

class CGameObject;

class CGui;

enum class CTag;

namespace fn {
template <typename T> using clean_t = std::remove_cvref_t<T>;

template <typename T>
concept SharedPtr = vstd::is_shared_ptr<clean_t<T>>::value;

template <typename T>
concept SetLike = vstd::is_set<clean_t<T>>::value;

template <typename T>
concept MapLike = vstd::is_map<clean_t<T>>::value;

template <typename T>
concept GameObjectDerived = std::derived_from<clean_t<T>, CGameObject>;

template <typename T>
concept MetaRegisteredGameObject = GameObjectDerived<T> && requires {
    { clean_t<T>::static_meta()->name() } -> std::convertible_to<std::string>;
};

template <typename T>
concept CoordsLike = requires(const clean_t<T> &coords) {
    { coords.x } -> std::convertible_to<int>;
    { coords.y } -> std::convertible_to<int>;
    { coords.z } -> std::convertible_to<int>;
};

template <typename T>
concept PriorityCostNode = requires(const clean_t<T> &node) {
    { node.priority } -> std::convertible_to<int>;
    { node.cost } -> std::convertible_to<int>;
};

template <typename T>
concept JsonObjectPointer = requires(T object, const std::string &property) {
    { object->count(property) } -> std::convertible_to<std::size_t>;
    { object->size() } -> std::convertible_to<std::size_t>;
    { (*object)[property].is_string() } -> std::convertible_to<bool>;
    { (*object)[property].is_object() } -> std::convertible_to<bool>;
};

template <typename T>
concept JsonMapPointer = JsonObjectPointer<T> && requires(T object) { object->items(); };

template <typename T>
concept JsonDumpPointer = requires(T value, int indent) {
    { value->dump(indent) } -> std::convertible_to<std::string>;
};

template <typename Range>
concept TaggablePointerRange =
    std::ranges::input_range<Range> && requires(std::ranges::range_reference_t<Range> value, CTag tag) {
        { value->hasTag(tag) } -> std::convertible_to<bool>;
    };

template <typename F>
concept FilePredicate = std::predicate<F, std::string>;

template <typename F>
concept SdlStatusCallable = std::invocable<F &> && std::same_as<std::invoke_result_t<F &>, int>;

template <typename F>
concept SdlVoidCallable = std::invocable<F &> && std::same_as<std::invoke_result_t<F &>, void>;

template <typename F>
concept SdlNullableCallable = std::invocable<F &> && !SdlStatusCallable<F> && !SdlVoidCallable<F>;

template <typename F>
concept AnimationCallback = std::is_invocable_r_v<bool, F, std::shared_ptr<CGui>, SDL_EventType, int, int, int>;

template <typename F>
concept TriggerCallback = std::is_invocable_r_v<void, F, std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>>;

template <typename T>
concept PythonWrapperBase = GameObjectDerived<T>;

template <typename T>
concept PythonReturn = std::same_as<T, void> || std::default_initializable<T>;
} // namespace fn
