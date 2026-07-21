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
#include "plugin/CPluginRegistrar.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "handler/CObjectHandler.h"

CPluginRegistrar::CPluginRegistrar(std::shared_ptr<CGame> game) : _game(std::move(game)) {}

void CPluginRegistrar::log(const std::string &message) const { vstd::logger::info("Plugin:", message); }

bool CPluginRegistrar::registerConfigJson(const std::string &id, const std::string &jsonText) const {
    if (!_game || id.empty() || jsonText.empty()) {
        vstd::logger::warning("Plugin attempted to register config without a game, id, or json text");
        return false;
    }

    auto parsed = CJsonUtil::parse_expected(jsonText, std::string("plugin config ") + id);
    if (!parsed) {
        CJsonUtil::log_parse_error(parsed.error());
        return false;
    }
    if (!(*parsed)->is_object()) {
        vstd::logger::warning("Plugin config is not an object:", id);
        return false;
    }

    _game->getObjectHandler()->registerConfig(id, *parsed);
    return true;
}

bool CPluginRegistrar::registerFactory(const std::string &name,
                                       std::function<std::shared_ptr<CGameObject>()> factory) const {
    if (!_game || name.empty() || !factory) {
        vstd::logger::warning("Plugin attempted to register a type without a game, name, or factory:", name);
        return false;
    }
    _game->getObjectHandler()->registerType(name, std::move(factory));
    return true;
}
