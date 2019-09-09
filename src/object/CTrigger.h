/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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

#include "CGameObject.h"

class CTrigger : public CGameObject {
V_META(CTrigger, CGameObject,
       V_PROPERTY(CTrigger, std::string, object, getObject, setObject),
       V_PROPERTY(CTrigger, std::string, event, getEvent, setEvent))
public:
    CTrigger();

    virtual void trigger(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>);

private:
    std::string object;
    std::string event;
public:
    std::string getObject();

    void setObject(std::string object);

    std::string getEvent();

    void setEvent(std::string event);


};


