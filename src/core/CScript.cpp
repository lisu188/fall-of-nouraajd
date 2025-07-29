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
#include "core/CScript.h"
#include "core/CGame.h"
#include "handler/CScriptHandler.h"

std::shared_ptr<CGameObject>
CScript::invoke(std::shared_ptr<CGame> game,
                std::shared_ptr<CGameObject> self) {
  return game->getScriptHandler()
      ->call_created_function<std::shared_ptr<CGameObject>,
                              std::shared_ptr<CGameObject>>("return " + script,
                                                            {"self"}, self);
}

std::string CScript::getScript() { return script; }

void CScript::setScript(std::string script) { CScript::script = script; }