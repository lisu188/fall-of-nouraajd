/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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

#include "core/CConcepts.h"
#include "core/CJsonUtil.h"
#include "core/CTags.h"

namespace core_concept_contracts {
struct LvalueAnimation {
    int *calls;
    bool operator()(std::shared_ptr<CGui>, SDL_EventType, int, int, int) & {
        ++*calls;
        return true;
    }
};

struct RvalueAnimation {
    bool operator()(std::shared_ptr<CGui>, SDL_EventType, int, int, int) &&;
};

struct MoveOnlyAnimation {
    std::unique_ptr<int> state;
    bool operator()(std::shared_ptr<CGui>, SDL_EventType, int, int, int);
};

struct CopyOnlyAnimation {
    CopyOnlyAnimation() = default;
    CopyOnlyAnimation(const CopyOnlyAnimation &) = default;
    CopyOnlyAnimation(CopyOnlyAnimation &&) = delete;
    bool operator()(std::shared_ptr<CGui>, SDL_EventType, int, int, int) &;
};

struct LvalueTrigger {
    int *calls;
    int operator()(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>) & {
        ++*calls;
        return 7;
    }
};

struct RvalueTrigger {
    void operator()(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>) &&;
};

struct MoveOnlyTrigger {
    std::unique_ptr<int> state;
    void operator()(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>);
};

struct AsyncTrigger {
    vstd::task<void> operator()(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>) &;
};

struct LvalueFilePredicate {
    bool operator()(std::string &path) & { return path.empty(); }
};

struct RvalueFilePredicate {
    bool operator()(std::string) &&;
};

struct RvaluePathPredicate {
    bool operator()(std::string &&) &;
};

struct SdlPointerCallback {
    SDL_Surface *operator()() &;
};

struct SdlStatusCallback {
    int operator()() &;
};

struct SdlVoidCallback {
    void operator()() &;
};

struct SdlStringCallback {
    std::string operator()() &;
};

struct SdlBooleanCallback {
    bool operator()() &;
};

struct SdlRvalueCallback {
    SDL_Surface *operator()() &&;
};

struct TagValue {
    bool hasTag(CTag) const;
};

struct MutableTagRange {
    std::shared_ptr<TagValue> *begin();
    std::shared_ptr<TagValue> *end();
};

struct MutableTagPointer {
    TagValue *operator->();
};

template <typename Range>
concept HasTagLookup = requires(const Range &range) { CTags::isTagPresent(range, CTag::Heal); };

struct JsonWithoutRootType {
    std::size_t count(const std::string &) const;
    std::size_t size() const;
    const json &operator[](const std::string &) const;
};

struct JsonWithoutItems : JsonWithoutRootType {
    bool is_object() const;
};

struct JsonWithInvalidItems : JsonWithoutItems {
    int items() const;
};

struct JsonPointerWithoutNullComparison {
    json *operator->() const;
    json &operator*() const;
};

template <typename T>
concept HasJsonTypeCheck = requires(T object) { CJsonUtil::isType(object); };

template <typename T>
concept HasJsonObjectCheck = requires(T object) { CJsonUtil::isObject(object); };

struct WideStepValue {
    operator std::int64_t() const;
    operator int() const = delete;
};

struct WideStepCost {
    WideStepValue operator()(const Coords &, const Coords &) const;
};

struct InvalidStepCost {
    std::string operator()(const Coords &, const Coords &) const;
};

static_assert(fn::AnimationCallback<LvalueAnimation>);
static_assert(fn::AnimationCallback<CopyOnlyAnimation>);
static_assert(!fn::AnimationCallback<RvalueAnimation>);
static_assert(!fn::AnimationCallback<MoveOnlyAnimation>);
static_assert(fn::TriggerCallback<LvalueTrigger>);
static_assert(fn::TriggerCallback<AsyncTrigger>);
static_assert(!fn::TriggerCallback<RvalueTrigger>);
static_assert(!fn::TriggerCallback<MoveOnlyTrigger>);
static_assert(fn::FilePredicate<LvalueFilePredicate>);
static_assert(fn::FilePredicate<decltype(&std::string::empty)>);
static_assert(!fn::FilePredicate<RvalueFilePredicate>);
static_assert(!fn::FilePredicate<RvaluePathPredicate>);
static_assert(fn::SdlNullableCallable<SdlPointerCallback>);
static_assert(fn::SdlStatusCallable<SdlStatusCallback>);
static_assert(fn::SdlVoidCallable<SdlVoidCallback>);
static_assert(!fn::SdlNullableCallable<SdlStatusCallback>);
static_assert(!fn::SdlNullableCallable<SdlVoidCallback>);
static_assert(!fn::SdlNullableCallable<SdlStringCallback>);
static_assert(!fn::SdlNullableCallable<SdlBooleanCallback>);
static_assert(!fn::SdlNullableCallable<SdlRvalueCallback>);
static_assert(fn::TaggablePointerRange<MutableTagRange>);
static_assert(!fn::TaggablePointerRange<const MutableTagRange>);
static_assert(!fn::TaggablePointerRange<std::vector<MutableTagPointer>>);
static_assert(!HasTagLookup<MutableTagRange>);
static_assert(HasTagLookup<std::vector<std::shared_ptr<TagValue>>>);
static_assert(fn::JsonObjectPointer<json *>);
static_assert(fn::JsonMapPointer<const json *>);
static_assert(fn::JsonMapPointer<std::shared_ptr<json>>);
static_assert(!fn::JsonObjectPointer<JsonWithoutRootType *>);
static_assert(!fn::JsonObjectPointer<JsonPointerWithoutNullComparison>);
static_assert(fn::JsonObjectPointer<JsonWithoutItems *>);
static_assert(!fn::JsonMapPointer<JsonWithoutItems *>);
static_assert(!fn::JsonMapPointer<JsonWithInvalidItems *>);
static_assert(!HasJsonTypeCheck<JsonWithoutItems *>);
static_assert(!HasJsonObjectCheck<JsonWithoutItems *>);
static_assert(HasJsonTypeCheck<const json *>);
static_assert(HasJsonObjectCheck<std::shared_ptr<const json>>);
static_assert(fn::PathStepCost<WideStepCost>);
static_assert(!fn::PathStepCost<InvalidStepCost>);
} // namespace core_concept_contracts
