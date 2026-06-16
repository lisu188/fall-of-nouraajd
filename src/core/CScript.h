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
#pragma once

#include "object/CGameObject.h"
#include "vstring.h"

#include <cctype>

class CScript : public CGameObject {
    V_META(CScript, CGameObject, V_PROPERTY(CScript, std::string, script, getScript, setScript))
  public:
    static bool isSafeAccessorExpression(const std::string &expression) {
        const std::string trimmed = vstd::trim(expression);
        std::size_t pos = 0;

        auto consumeIdentifier = [&trimmed, &pos]() {
            if (pos >= trimmed.size() ||
                (!std::isalpha(static_cast<unsigned char>(trimmed[pos])) && trimmed[pos] != '_')) {
                return false;
            }
            ++pos;
            while (pos < trimmed.size() &&
                   (std::isalnum(static_cast<unsigned char>(trimmed[pos])) || trimmed[pos] == '_')) {
                ++pos;
            }
            return true;
        };

        if (!consumeIdentifier() || trimmed.substr(0, pos) != "self") {
            return false;
        }
        while (pos < trimmed.size()) {
            if (trimmed[pos++] != '.' || !consumeIdentifier()) {
                return false;
            }
            if (pos + 1 >= trimmed.size() || trimmed[pos] != '(' || trimmed[pos + 1] != ')') {
                return false;
            }
            pos += 2;
        }
        return true;
    }

    template <fn::GameObjectDerived T>
    std::shared_ptr<T> invoke(std::shared_ptr<CGame> game, std::shared_ptr<CGameObject> self) {
        return vstd::cast<T>(invoke(game, self));
    }

    std::shared_ptr<CGameObject> invoke(std::shared_ptr<CGame> game, std::shared_ptr<CGameObject> self);

    std::string getScript();

    void setScript(std::string script);

  private:
    std::string script;
};
