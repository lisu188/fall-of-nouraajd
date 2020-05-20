/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2020  Andrzej Lis

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

class CScript : public CGameObject {
V_META(CScript, CGameObject,
       V_PROPERTY(CScript, std::string, script, getScript, setScript)
)
public:
    std::shared_ptr<CGameObject> invoke(std::shared_ptr<CGame> game, std::shared_ptr<CGameObject> self);

    std::string getScript();

    void setScript(std::string script);

private:
    std::string script;

};