#include "core/CGame.h"
#include "object/CGameObject.h"
#include "core/CMap.h"

using namespace boost::python;

void initModule1() {
    class_<CGameObject, boost::noncopyable, std::shared_ptr<CGameObject>>("CGameObject", no_init)
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
            .def("removeTag", &CGameObject::removeTag);

    class_<Coords>("Coords", init<int, int, int>())
            .def_readonly("x", &Coords::x)
            .def_readonly("y", &Coords::y)
            .def_readonly("z", &Coords::z);

    class_<CGame, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGame>>("CGame", no_init)
            .def("getMap", &CGame::getMap)
            .def("changeMap", &CGame::changeMap)
            .def("load_plugin", &CGame::load_plugin)
            .def("getGuiHandler", &CGame::getGuiHandler)
            .def("getObjectHandler", &CGame::getObjectHandler)
            .def("createObject", &CGame::createObject<CGameObject>);

    bool (CMap::*canStep)(Coords)=&CMap::canStep;

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
            .def("dumpPaths", &CMap::dumpPaths);

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
            .def("showTrade", &CGuiHandler::showTrade);

    void ( CMapObject::*moveTo )(int, int, int) = &CMapObject::moveTo;
    void ( CMapObject::*move )(int, int, int) = &CMapObject::move;
    class_<CMapObject, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMapObject>>("CMapObject", no_init)
            .def("getMap", &CMapObject::getMap)
            .def("moveTo", moveTo)
            .def("move", move)
            .def("getCoords", &CMapObject::getCoords)
            .def("setCoords", &CMapObject::setCoords);
}