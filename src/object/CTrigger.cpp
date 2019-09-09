//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
#include "CTrigger.h"

CTrigger::CTrigger() {
}

void CTrigger::trigger(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>) {

}

std::string CTrigger::getObject() {
    return object;
}

void CTrigger::setObject(std::string object) {
    CTrigger::object = object;
}

std::string CTrigger::getEvent() {
    return event;
}

void CTrigger::setEvent(std::string event) {
    CTrigger::event = event;
}
