/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#pragma once
#include "core/CGlobal.h"
#include <set>

namespace UiPreferences {
inline json defaults() {
    return {{"uiScale", 100},
            {"textScale", 100},
            {"highContrast", false},
            {"reducedMotion", true},
            {"fullscreen", false},
            {"tooltipDelayMs", 300},
            {"bindings",
             {{"north", "Up"},
              {"south", "Down"},
              {"west", "Left"},
              {"east", "Right"},
              {"wait", "Space"},
              {"save", "S"},
              {"inventory", "I"},
              {"journal", "J"},
              {"character", "C"},
              {"pause", "Escape"},
              {"console", "F12"}}}};
}

inline bool validate(const json &value) {
    if (!value.is_object())
        return false;
    const auto baseline = defaults();
    for (const auto &[key, field] : value.items()) {
        if (!baseline.contains(key))
            return false;
        const auto &expected = baseline.at(key);
        if ((expected.is_number_integer() && !field.is_number_integer()) ||
            (expected.is_boolean() && !field.is_boolean()) || (expected.is_object() && !field.is_object()))
            return false;
    }
    auto merged = baseline;
    for (const auto &[key, field] : value.items())
        merged[key] = field;
    for (const auto *key : {"uiScale", "textScale"}) {
        auto n = merged.at(key).get<long long>();
        if (n < 100 || n > 200 || n % 25 != 0)
            return false;
    }
    const auto delay = merged.at("tooltipDelayMs").get<long long>();
    if (delay < 0 || delay > 1500)
        return false;
    const auto &bindings = merged.at("bindings");
    if (!bindings.is_object() || bindings.size() != baseline.at("bindings").size())
        return false;
    std::set<SDL_Keycode> keys;
    for (const auto &[action, key] : bindings.items()) {
        if (!baseline.at("bindings").contains(action) || !key.is_string())
            return false;
        auto code = SDL_GetKeyFromName(key.get<std::string>().c_str());
        if (code == SDLK_UNKNOWN || code == SDLK_TAB || code == SDLK_RETURN || code == SDLK_KP_ENTER ||
            code == SDLK_m || !keys.insert(code).second)
            return false;
    }
    return true;
}
} // namespace UiPreferences
