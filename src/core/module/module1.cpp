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
#include "gui/panel/CCreatureView.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "gui/CGui.h"
#include "gui/object/CStatsGraphicsObject.h"

using namespace boost::python;

void initModule1() {
    class_<CGameObject, boost::noncopyable, std::shared_ptr<CGameObject>>("CGameObject", no_init)
            .def("getName", &CGameObject::getName)
            .def("getType", &CGameObject::getType)
            .def("getGame", &CGameObject::getGame)
            .def("getStringProperty", &CGameObject::getStringProperty)
            .def("getNumericProperty", &CGameObject::getNumericProperty)
            .def("getBoolProperty", &CGameObject::getBoolProperty)
            .def("setStringProperty", &CGameObject::setStringProperty)
            .def("setNumericProperty", &CGameObject::setNumericProperty)
            .def("setBoolProperty", &CGameObject::setBoolProperty)
            .def("getObjectProperty", &CGameObject::getObjectProperty<CGameObject>)
            .def("setObjectProperty", &CGameObject::setObjectProperty<CGameObject>)
            .def("incProperty", &CGameObject::incProperty)
            .def("ptr", &CGameObject::ptr<CGameObject>)
            .def("clone", &CGameObject::clone<CGameObject>)
            .def("addTag", &CGameObject::addTag)
            .def("removeTag", &CGameObject::removeTag)
            .def("hasTag", &CCreature::hasTag)
            .def("__setattr__", &CGameObject::setStringProperty)
            .def("__setattr__", &CGameObject::setNumericProperty)
            .def("__getattr__", &CGameObject::getStringProperty)
            .def("__getattr__", &CGameObject::getNumericProperty);

    class_<Coords>("Coords", init<int, int, int>())
            .def_readonly("x", &Coords::x)
            .def_readonly("y", &Coords::y)
            .def_readonly("z", &Coords::z);

    std::shared_ptr<CGameObject>(CGame::*
    createObject)(std::string) = &CGame::createObject<CGameObject>;

    class_<CGame, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGame>>("CGame", no_init)
            .def("getMap", &CGame::getMap)
            .def("changeMap", &CGame::changeMap)
            .def("loadPlugin", &CGame::loadPlugin)
            .def("getGuiHandler", &CGame::getGuiHandler)
            .def("getObjectHandler", &CGame::getObjectHandler)
            .def("createObject", createObject)
            .def("getGui", &CGame::getGui);

    class_<CGameGraphicsObject, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGameGraphicsObject>>(
            "CGameGraphicsObject", no_init)
            .def("getGui", &CGameGraphicsObject::getGui)
            .def("getParent", &CGameGraphicsObject::getParent);
    class_<CGui, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CGui>>("CGui", no_init)
            .def("getGame", &CGui::getGame);

    class_<CStatsGraphicsObject, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CStatsGraphicsObject>>(
            "CGameGraphicsObject", no_init);

    class_<CCreatureView, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CCreatureView>>(
            "CCreatureView", no_init);

    bool (CMap::*canStep)(Coords) =&CMap::canStep;

    class_<CMap, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMap>>("CMap", no_init)
            .def("addObjectByName", &CMap::addObjectByName)
            .def("removeObjectByName", &CMap::removeObjectByName)
            .def("removeObject", &CMap::removeObject)
            .def("replaceTile", &CMap::replaceTile)
            .def("getPlayer", &CMap::getPlayer)
            .def("getLocationByName", &CMap::getLocationByName)
            .def("removeAll", &CMap::removeObjects)
            .def("getEventHandler", &CMap::getEventHandler)
            .def("addObject", &CMap::addObject)
            .def("getGame", &CMap::getGame)
            .def("move", &CMap::move)
            .def("getObjectByName", &CMap::getObjectByName)
            .def("forObjects", &CMap::forObjects)
            .def("canStep", canStep)
            .def("dumpPaths", &CMap::dumpPaths)
            .def("getObjects", &CMap::getObjects)
            .def("getTurn", &CMap::getTurn);

    void ( CObjectHandler::*registerType )(std::string,
                                           std::function<std::shared_ptr<CGameObject>()>) = &CObjectHandler::registerType;
    class_<CObjectHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CObjectHandler>>("CObjectHandler",
                                                                                                    no_init)
            .def("registerType", registerType)
            .def("getAllTypes", &CObjectHandler::getAllTypes)
            .def("getAllSubTypes", &CObjectHandler::getAllSubTypes);

    class_<CGuiHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGuiHandler>>("CGuiHandler",
                                                                                              no_init)
            .def("showMessage", &CGuiHandler::showMessage)
            .def("showTrade", &CGuiHandler::showTrade)
            .def("showDialog", &CGuiHandler::showDialog)
            .def("showSelection", &CGuiHandler::showSelection);

    void ( CMapObject::*moveTo )(int, int, int) = &CMapObject::moveTo;
    void ( CMapObject::*move )(int, int, int) = &CMapObject::move;
    class_<CMapObject, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMapObject>>("CMapObject", no_init)
            .def("getMap", &CMapObject::getMap)
            .def("moveTo", moveTo)
            .def("move", move)
            .def("getCoords", &CMapObject::getCoords)
            .def("setCoords", &CMapObject::setCoords);
}