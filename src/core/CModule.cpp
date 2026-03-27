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
#include <utility>
#include <cctype>
#include <stdexcept>

#include "../../vstd/vstd.h"
#include "../gui/CGui.h"
#include "../gui/object/CSideBar.h"
#include "../gui/object/CStatsGraphicsObject.h"
#include "../gui/panel/CCreatureView.h"
#include "../gui/panel/CGameCharacterPanel.h"
#include "../gui/panel/CGameDialogPanel.h"
#include "../gui/panel/CGameFightPanel.h"
#include "../gui/panel/CGameInventoryPanel.h"
#include "../gui/panel/CGameQuestPanel.h"
#include "../gui/panel/CGameQuestionPanel.h"
#include "../gui/panel/CGameTextPanel.h"
#include "../gui/panel/CGameTradePanel.h"
#include "../gui/panel/CListView.h"
#include "../handler/CHandler.h"
#include "../handler/CRngHandler.h"
#include "../object/CDialog.h"
#include "CGame.h"
#include "CList.h"
#include "CMap.h"
#include "CProvider.h"
#include "core/CJsonUtil.h"
#include "core/CLoader.h"
#include "core/CPythonOverrides.h"
#include "core/CWrapper.h"
#include <pybind11/stl_bind.h>

namespace py = pybind11;

PYBIND11_MAKE_OPAQUE(std::vector<std::string>);

int randint(int i, int j) {
    return vstd::rand(i, j); // TODO: unify and document exclusive inclusive
}

std::string jsonify(std::shared_ptr<CGameObject> x) { return JSONIFY(x); }

void logger(std::string s) {
    vstd::logger::info(std::move(s)); // TODO: add script name
}

static vstd::logger::sink parse_logger_sink(const std::string &sink_name) {
    std::string normalized;
    normalized.reserve(sink_name.size());
    for (char ch : sink_name) {
        normalized.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
    }
    if (normalized == "stdout") {
        return vstd::logger::sink::stdout_sink;
    }
    if (normalized == "stderr") {
        return vstd::logger::sink::stderr_sink;
    }
    if (normalized == "file") {
        return vstd::logger::sink::file_sink;
    }
    if (normalized == "disabled") {
        return vstd::logger::sink::disabled;
    }
    throw std::invalid_argument("Unknown logger sink: " + sink_name);
}

void set_logger_sink(const std::string &sink_name, const std::string &path) {
    const auto target = parse_logger_sink(sink_name);
    if (target == vstd::logger::sink::file_sink && path.empty()) {
        throw std::invalid_argument("File logger sink requires a path");
    }
    vstd::logger::set_sink(target, path);
}

void set_logger_sink_py(const std::string &sink_name, py::object path = py::none()) {
    std::string file_path;
    if (!path.is_none()) {
        file_path = path.cast<std::string>();
    }
    set_logger_sink(sink_name, file_path);
}

py::list map_get_objects(const std::shared_ptr<CMap> &map) {
    py::list objects;
    for (const auto &object : map->getObjects()) {
        objects.append(object);
    }
    return objects;
}

std::shared_ptr<CGameObject> cast_registered_python_object(
    const py::object &instance) {
    if (py::isinstance<CBuilding>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CBuilding>>());
    }
    if (py::isinstance<CEvent>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CEvent>>());
    }
    if (py::isinstance<CInteraction>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CInteraction>>());
    }
    if (py::isinstance<CEffect>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CEffect>>());
    }
    if (py::isinstance<CTile>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CTile>>());
    }
    if (py::isinstance<CPotion>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CPotion>>());
    }
    if (py::isinstance<CScroll>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CScroll>>());
    }
    if (py::isinstance<CTrigger>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CTrigger>>());
    }
    if (py::isinstance<CQuest>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CQuest>>());
    }
    if (py::isinstance<CPlugin>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CPlugin>>());
    }
    if (py::isinstance<CDialog>(instance)) {
        return std::static_pointer_cast<CGameObject>(
            instance.cast<std::shared_ptr<CDialog>>());
    }
    return instance.cast<std::shared_ptr<CGameObject>>();
}

extern void initModule1();

#define PY_WRAP_GENERIC_DOC(fcn, doc) m.def(#fcn, fcn, doc)

PYBIND11_MODULE(_game, m) {
    py::class_<CGameObject, std::shared_ptr<CGameObject>>(m, "CGameObject", "Base engine object with dynamic string, numeric, bool, and object properties.")
        .def("getName", &CGameObject::getName, "Return the object name.")
        .def("getType", &CGameObject::getType, "Return the runtime class/type name.")
        .def("getTypeId", &CGameObject::getTypeId, "Return the configured type id used to spawn this object.")
        .def("getGame", &CGameObject::getGame, "Return the owning game instance.")
        .def("getStringProperty", &CGameObject::getStringProperty, "Return a string property by name.")
        .def("getNumericProperty", &CGameObject::getNumericProperty, "Return an integer property by name.")
        .def("getBoolProperty", &CGameObject::getBoolProperty, "Return a boolean property by name.")
        .def("setStringProperty", &CGameObject::setStringProperty, "Set a string property by name.")
        .def("setNumericProperty", &CGameObject::setNumericProperty, "Set an integer property by name.")
        .def("setBoolProperty", &CGameObject::setBoolProperty, "Set a boolean property by name.")
        .def("getObjectProperty", &CGameObject::getObjectProperty<CGameObject>, "Return an object property by name.")
        .def("setObjectProperty", &CGameObject::setObjectProperty<CGameObject>, "Set an object property by name.")
        .def("incProperty", &CGameObject::incProperty, "Increment an integer property by value.")
        .def("ptr", &CGameObject::ptr<CGameObject>, "Return this object as a shared pointer.")
        .def("clone", &CGameObject::clone<CGameObject>, "Clone this object using engine serialization.")
        .def("addTag", &CGameObject::addTag, "Add a tag to this object.")
        .def("removeTag", &CGameObject::removeTag, "Remove a tag from this object.")
        .def("hasTag", &CCreature::hasTag, "Return whether this object has the given tag.")
        .def("__setattr__", &CGameObject::setStringProperty, "Alias for setStringProperty(name, value).")
        .def("__setattr__", &CGameObject::setNumericProperty, "Alias for setNumericProperty(name, value).")
        .def("__getattr__", &CGameObject::getStringProperty, "Alias for getStringProperty(name).")
        .def("__getattr__", &CGameObject::getNumericProperty, "Alias for getNumericProperty(name).");

    py::class_<Coords>(m, "Coords", "3D integer coordinates (x, y, z).")
        .def(py::init<int, int, int>())
        .def_readonly("x", &Coords::x)
        .def_readonly("y", &Coords::y)
        .def_readonly("z", &Coords::z);

    std::shared_ptr<CGameObject> (CGame::*createObject)(std::string) = &CGame::createObject<CGameObject>;

    py::class_<CGame, CGameObject, std::shared_ptr<CGame>>(m, "CGame", "Top-level game container holding the active map, handlers, and GUI.")
        .def("getMap", &CGame::getMap, "Return the currently loaded map.")
        .def("changeMap", &CGame::changeMap, "Load and switch to another map.")
        .def("loadPlugin", &CGame::loadPlugin, "Load a plugin object into the game.")
        .def("getGuiHandler", &CGame::getGuiHandler, "Return the GUI handler service.")
        .def("getObjectHandler", &CGame::getObjectHandler, "Return the object factory/registry handler.")
        .def("getRngHandler", &CGame::getRngHandler, "Return the random encounter/loot handler.")
        .def("createObject", createObject, "Create an object by configured type id.")
        .def("getGui", &CGame::getGui, "Return the GUI root object.");

    py::class_<CGameGraphicsObject, CGameObject, std::shared_ptr<CGameGraphicsObject>>(m, "CGameGraphicsObject", "Base class for GUI graphics objects.")
        .def("getGui", &CGameGraphicsObject::getGui, "Return the owning GUI object.")
        .def("getParent", &CGameGraphicsObject::getParent, "Return the parent graphics object.");

    py::class_<CGui, CGameGraphicsObject, std::shared_ptr<CGui>>(m, "CGui", "Game GUI root object.")
        .def("getGame", &CGui::getGame, "Return the owning game.");

    py::class_<CStatsGraphicsObject, CGameGraphicsObject, std::shared_ptr<CStatsGraphicsObject>>(m, "CStatsGraphicsObject");

    py::class_<CSideBar, CGameGraphicsObject, std::shared_ptr<CSideBar>>(m, "CSideBar");

    py::class_<CCreatureView, CGameGraphicsObject, std::shared_ptr<CCreatureView>>(m, "CCreatureView", "Panel widget that renders a creature.")
        .def("getCreature", &CCreatureView::getCreature, "Return the creature shown in this view.");

    bool (CMap::*canStep)(Coords) = &CMap::canStep;
    void (CMap::*addObject)(const std::shared_ptr<CMapObject> &) = &CMap::addObject;

    py::class_<CMap, CGameObject, std::shared_ptr<CMap>>(m, "CMap", "Runtime map containing tiles, map objects, triggers, and turn state.")
        .def("addObjectByName", &CMap::addObjectByName, "Create and add an object by type id at coordinates.")
        .def("removeObjectByName", &CMap::removeObjectByName, "Remove an object by its name.")
        .def("removeObject", &CMap::removeObject, "Remove a map object instance.")
        .def("replaceTile", &CMap::replaceTile, "Replace a tile at coordinates with a tile type id.")
        .def("getPlayer", &CMap::getPlayer, "Return the player object assigned to this map.")
        .def("getLocationByName", &CMap::getLocationByName, "Return Coords for a named location object.")
        .def("removeAll", &CMap::removeObjects, "Remove objects matching a predicate.")
        .def("getEventHandler", &CMap::getEventHandler, "Return the map event handler.")
        .def("addObject", addObject, "Add an existing map object to this map.")
        .def("getGame", &CMap::getGame, "Return the owning game instance.")
        .def("move", &CMap::move, "Advance map simulation by one turn.")
        .def("getObjectByName", &CMap::getObjectByName, "Return a map object by name or None.")
        .def("forObjects", &CMap::forObjects, "Apply a callback for objects matching an optional predicate.")
        .def("canStep", canStep, "Return whether coordinates are walkable.")
        .def("dumpPaths", &CMap::dumpPaths, "Write pathfinding diagnostics to a file path.")
        .def("getEntryX", &CMap::getEntryX, "Return map entry X coordinate.")
        .def("getEntryY", &CMap::getEntryY, "Return map entry Y coordinate.")
        .def("getEntryZ", &CMap::getEntryZ, "Return map entry Z coordinate.")
        .def("getObjects", &map_get_objects, "Return a Python list of map objects.")
        .def("getTurn", &CMap::getTurn, "Return the current turn counter.");

    std::shared_ptr<CGameObject> (*createObjectByType)(std::shared_ptr<CObjectHandler>, std::shared_ptr<CGame>,
                                                       std::string) =
        [](std::shared_ptr<CObjectHandler> handler, std::shared_ptr<CGame> game, std::string type) {
            return handler->createObject<CGameObject>(game, type);
        };
    py::class_<CObjectHandler, CGameObject, std::shared_ptr<CObjectHandler>>(m, "CObjectHandler", "Factory and type/config registry for runtime objects.")
        .def("registerType",
             [](CObjectHandler &self, std::string name, py::object constructor) {
                 self.registerType(std::move(name), [constructor]() {
                     py::gil_scoped_acquire gil;
                     py::object instance = constructor();
                     auto object = cast_registered_python_object(instance);
                     CPythonOverrides::retain(object, instance);
                     return object;
                 });
             },
             "Register a class constructor under a class name.")
        .def("createObject", createObjectByType, "Create an object by configured type id.")
        .def("getAllTypes", &CObjectHandler::getAllTypes, "Return all configured object type ids.")
        .def("getAllSubTypes", &CObjectHandler::getAllSubTypes,
             "Return configured type ids whose class inherits the given base class.");

    py::class_<CGuiHandler, CGameObject, std::shared_ptr<CGuiHandler>>(m, "CGuiHandler", "High-level helper for opening UI panels.")
        .def("showMessage", &CGuiHandler::showMessage, "Show a message panel.")
        .def("showTrade", &CGuiHandler::showTrade, "Open a trade panel.")
        .def("showDialog", &CGuiHandler::showDialog, "Open a dialog panel.")
        .def("showQuestion", &CGuiHandler::showQuestion, "Open a question/choice panel.")
        .def("showSelection", &CGuiHandler::showSelection, "Open a selection panel.")
        .def("showInfo", &CGuiHandler::showInfo, "Open an info panel.")
        .def("showLoot", &CGuiHandler::showLoot, "Show loot acquisition UI.");

    void (CRngHandler::*addRandomLoot)(const std::shared_ptr<CCreature> &, int) = &CRngHandler::addRandomLoot;
    py::class_<CRngHandler, CGameObject, std::shared_ptr<CRngHandler>>(m, "CRngHandler", "Random loot and encounter generator.")
        .def("addRandomLoot", addRandomLoot, "Generate random loot for a creature and apply/show it.")
        .def("addRandomEncounter", &CRngHandler::addRandomEncounter,
             "Generate and place random enemy creatures on a map.");

    void (CMapObject::*moveTo)(int, int, int) = &CMapObject::moveTo;
    void (CMapObject::*move)(int, int, int) = &CMapObject::move;
    py::class_<CMapObject, CGameObject, std::shared_ptr<CMapObject>>(m, "CMapObject", "Base object that exists at map coordinates.")
        .def("getMap", &CMapObject::getMap, "Return the map containing this object.")
        .def("moveTo", moveTo, "Move this object to absolute coordinates.")
        .def("move", move, "Move this object by relative coordinate delta.")
        .def("getCoords", &CMapObject::getCoords, "Return current map coordinates.")
        .def("setCoords", &CMapObject::setCoords, "Set map coordinates.");

    auto cbuilding = py::class_<CBuilding, CWrapper<CBuilding>, std::shared_ptr<CBuilding>, CMapObject>(m, "CBuilding",
                                                                                                        "Base building object class.");
    cbuilding
        .def(py::init_alias<>())
        .def("onCreate", &CBuilding::onCreate, "Handle onCreate game event.")
        .def("onTurn", &CBuilding::onTurn, "Handle onTurn game event.")
        .def("onDestroy", &CBuilding::onDestroy, "Handle onDestroy game event.")
        .def("onLeave", &CBuilding::onLeave, "Handle onLeave game event.")
        .def("onEnter", &CBuilding::onEnter, "Handle onEnter game event.");
    m.attr("CBuildingBase") = cbuilding;

    auto cevent = py::class_<CEvent, CWrapper<CEvent>, std::shared_ptr<CEvent>, CMapObject>(m, "CEvent",
                                                                                           "Base map event object class.");
    cevent
        .def(py::init_alias<>())
        .def("onCreate", &CEvent::onCreate, "Handle onCreate game event.")
        .def("onTurn", &CEvent::onTurn, "Handle onTurn game event.")
        .def("onLeave", &CEvent::onLeave, "Handle onLeave game event.")
        .def("onDestroy", &CEvent::onDestroy, "Handle onDestroy game event.")
        .def("onEnter", &CEvent::onEnter, "Handle onEnter game event.");
    m.attr("CEventBase") = cevent;

    auto cinteraction = py::class_<CInteraction, CWrapper<CInteraction>, std::shared_ptr<CInteraction>, CGameObject>(m, "CInteraction",
                                                                                                                     "Base interaction/action definition.")
        .def(py::init_alias<>())
        .def("onAction", &CInteraction::onAction, "Engine callback when the interaction is activated.");
    cinteraction
        .def("performAction", &CInteraction::performAction,
             "Perform the interaction between source and target creatures.")
        .def("configureEffect", &CInteraction::configureEffect,
             "Configure an effect instance before it is applied.");
    m.attr("CInteractionBase") = cinteraction;

    py::class_<Damage, CGameObject, std::shared_ptr<Damage>>(m, "Damage", "Damage packet with typed damage components.");
    py::class_<Stats, CGameObject, std::shared_ptr<Stats>>(m, "Stats", "Creature stat container used for combat calculations.")
        .def("setStrength", &Stats::setStrength, "Set strength.")
        .def("setAgility", &Stats::setAgility, "Set agility.")
        .def("setStamina", &Stats::setStamina, "Set stamina.")
        .def("setIntelligence", &Stats::setIntelligence, "Set intelligence.")
        .def("setArmor", &Stats::setArmor, "Set armor reduction percentage.")
        .def("setBlock", &Stats::setBlock, "Set block chance percentage.")
        .def("setDmgMin", &Stats::setDmgMin, "Set minimum base damage.")
        .def("setDmgMax", &Stats::setDmgMax, "Set maximum base damage.")
        .def("setHit", &Stats::setHit, "Set hit chance modifier.")
        .def("setCrit", &Stats::setCrit, "Set critical chance percentage.");

    auto ctile = py::class_<CTile, CWrapper<CTile>, std::shared_ptr<CTile>, CGameObject>(m, "CTile", "Base tile class.");
    ctile
        .def(py::init_alias<>())
        .def("onStep", &CTile::onStep, "Handle a creature stepping on this tile.");
    m.attr("CTileBase") = ctile;

    py::class_<CItem, CMapObject, std::shared_ptr<CItem>>(m, "CItem",
                                                                                 "Base inventory/equipment item.");
    auto cpotion = py::class_<CPotion, CWrapper<CPotion>, std::shared_ptr<CPotion>, CItem>(m, "CPotion",
                                                                                           "Base potion item class.");
    cpotion
        .def(py::init_alias<>())
        .def("onUse", &CPotion::onUse, "Handle potion use event.");
    m.attr("CPotionBase") = cpotion;
    auto cscroll = py::class_<CScroll, CWrapper<CScroll>, std::shared_ptr<CScroll>, CItem>(m, "CScroll",
                                                                                           "Base scroll item class.");
    cscroll
        .def(py::init_alias<>())
        .def("onUse", &CScroll::onUse, "Handle scroll use event.")
        .def("isDisposable", &CScroll::isDisposable, "Return whether the scroll is consumed on use.");
    m.attr("CScrollBase") = cscroll;

    py::class_<CGameEvent, CGameObject, std::shared_ptr<CGameEvent>>(m, "CGameEvent",
                                                                                            "Base event object.");
    py::class_<CGameEventCaused, CGameEvent, std::shared_ptr<CGameEventCaused>>(m, "CGameEventCaused", "Event carrying a causing game object.")
        .def("getCause", &CGameEventCaused::getCause, "Return the object that caused this event.");

    auto ctrigger = py::class_<CTrigger, CWrapper<CTrigger>, std::shared_ptr<CTrigger>, CGameObject>(m, "CTrigger",
                                                                                                     "Base trigger class.");
    ctrigger
        .def(py::init_alias<>())
        .def("trigger", &CTrigger::trigger, "Handle trigger execution for an object and event.");
    m.attr("CTriggerBase") = ctrigger;

    auto cquest = py::class_<CQuest, CWrapper<CQuest>, std::shared_ptr<CQuest>, CGameObject>(m, "CQuest", "Base quest class.");
    cquest
        .def(py::init_alias<>())
        .def("isCompleted", &CQuest::isCompleted, "Return whether quest objectives are completed.")
        .def("onComplete", &CQuest::onComplete, "Handle quest completion callback.");
    m.attr("CQuestBase") = cquest;

    auto cdialog = py::class_<CDialog, CWrapper<CDialog>, std::shared_ptr<CDialog>, CGameObject>(m, "CDialog",
                                                                                                "Base dialog definition.");
    cdialog
        .def(py::init_alias<>())
        .def("invokeAction", &CDialog::invokeAction, "Run a named dialog action callback.")
        .def("invokeCondition", &CDialog::invokeCondition, "Evaluate a named dialog condition callback.");
    m.attr("CDialogBase") = cdialog;
    m.attr("CDialogBase2") = cdialog;

    py::class_<CDialogOption, CGameObject, std::shared_ptr<CDialogOption>>(m, "CDialogOption", "Single selectable dialog option.");
    py::class_<CDialogState, CGameObject, std::shared_ptr<CDialogState>>(m, "CDialogState",
                                                                                                "Dialog state node.");

    py::class_<CEventHandler, CGameObject, std::shared_ptr<CEventHandler>>(m, "CEventHandler", "Dispatcher for game/map events.")
        .def("registerTrigger", &CEventHandler::registerTrigger, "Register a trigger for an event type.");

    py::class_<CFightHandler, std::shared_ptr<CFightHandler>>(m, "CFightHandler",
                                                                              "Combat resolution service.")
        .def("fight", &CFightHandler::fight, "Run a fight between two creatures.");

    py::class_<CMarket, CGameObject, std::shared_ptr<CMarket>>(m, "CMarket",
                                                                                      "Trading inventory and prices.");

    py::class_<CGameLoader, std::shared_ptr<CGameLoader>>(m, "CGameLoader", "Factory helpers for loading game sessions and maps.")
        .def("loadGame", &CGameLoader::loadGame, "Create and initialize a game instance.")
        .def("startGameWithPlayer", &CGameLoader::startGameWithPlayer, "Start a map with a specific player template.")
        .def("startRandomGameWithPlayer", &CGameLoader::startRandomGameWithPlayer,
             "Start a random map with a specific player template.")
        .def("startGame", &CGameLoader::startGame, "Start a specific map with current player data.")
        .def("loadGui", &CGameLoader::loadGui, "Load and attach GUI objects for a game.")
        .def("loadSavedGame", &CGameLoader::loadSavedGame, "Load a saved game state from storage.");

    py::class_<CMapLoader, std::shared_ptr<CMapLoader>>(m, "CMapLoader",
                                                                        "Helpers for loading map resources.")
        .def("loadNewMapWithPlayer", &CMapLoader::loadNewMapWithPlayer, "Load a map and place a player template.")
        .def("loadNewMap", &CMapLoader::loadNewMap, "Load a map without changing the active player.");

    auto cplugin = py::class_<CPlugin, CWrapper<CPlugin>, std::shared_ptr<CPlugin>, CGameObject>(m, "CPlugin",
                                                                                                 "Base plugin class.");
    cplugin
        .def(py::init_alias<>())
        .def("load", &CPlugin::load, "Load plugin content into a game.");
    m.attr("CPluginBase") = cplugin;

    py::class_<vstd::event_loop<>, std::shared_ptr<vstd::event_loop<>>>(m, "event_loop", "Global async event loop utility.")
        .def("instance", &vstd::event_loop<>::instance, "Return the singleton event loop instance.")
        .def("run", &vstd::event_loop<>::run, "Process queued tasks/events once.")
        .def("invoke", &vstd::event_loop<>::invoke, "Queue a callable for later execution.");

    auto vector_string = py::bind_vector<std::vector<std::string>>(m, "std::vector<std::string>");
    vector_string.doc() = "Mutable list of strings.";

    py::class_<CResourcesProvider, std::shared_ptr<CResourcesProvider>>(m, "CResourcesProvider", "Access to packaged resource files.")
        .def("getInstance", &CResourcesProvider::getInstance, "Return singleton resource provider.")
        .def("getFiles", &CResourcesProvider::getFiles, "List files under a resource path.");

    auto ceffect = py::class_<CEffect, CWrapper<CEffect>, std::shared_ptr<CEffect>, CGameObject>(m, "CEffect",
                                                                                                "Base status effect class.")
        .def(py::init_alias<>())
        .def("getBonus", &CEffect::getBonus, "Return effect stat bonus object.")
        .def("setBonus", &CEffect::setBonus, "Set effect stat bonus object.")
        .def("getCaster", &CEffect::getCaster, "Return creature that applied the effect.")
        .def("getVictim", &CEffect::getVictim, "Return creature affected by the effect.")
        .def("getTimeLeft", &CEffect::getTimeLeft, "Return remaining effect duration in turns.")
        .def("onEffect", &CEffect::onEffect, "Apply effect behavior for one tick.");
    m.attr("CEffectBase") = ceffect;

    py::class_<CWeapon, CItem, std::shared_ptr<CWeapon>>(m, "CWeapon", "Weapon item.")
        .def("getInteraction", &CWeapon::getInteraction, "Return interaction used when this weapon is applied.");

    void (CCreature::*hurtInt)(int) = &CCreature::hurt;
    void (CCreature::*hurtFloat)(float) = &CCreature::hurt;
    void (CCreature::*hurtDmg)(std::shared_ptr<Damage>) = &CCreature::hurt;
    void (CCreature::*addItemByName)(std::string) = &CCreature::addItem;
    void (CCreature::*addItemByObject)(std::shared_ptr<CItem>) = &CCreature::addItem;
    bool (CCreature::*hasItem)(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::hasItem;
    void (CCreature::*removeItem)(std::function<bool(std::shared_ptr<CItem>)>, bool) = &CCreature::removeItem;
    void (CCreature::*removeQuestItem)(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::removeQuestItem;
    py::class_<CCreature, CMapObject, std::shared_ptr<CCreature>>(m, "CCreature", "Creature that can move, fight, and manage inventory.")
        .def("getDmg", &CCreature::getDmg, "Roll outgoing attack damage.")
        .def("hurt", hurtInt, "Apply raw damage value (int).")
        .def("hurt", hurtDmg, "Apply structured Damage object.")
        .def("hurt", hurtFloat, "Apply damage value (float), rounded to int.")
        .def("getWeapon", &CCreature::getWeapon, "Return equipped weapon or None.")
        .def("getHpRatio", &CCreature::getHpRatio, "Return HP percentage (0-100).")
        .def("isAlive", &CCreature::isAlive, "Return whether HP is above zero.")
        .def("getMana", &CCreature::getMana, "Return current mana.")
        .def("healProc", &CCreature::healProc, "Restore HP by percentage of max HP.")
        .def("heal", &CCreature::heal, "Restore HP by fixed amount (0 means full heal).")
        .def("getHpMax", &CCreature::getHpMax, "Return maximum HP.")
        .def("getLevel", &CCreature::getLevel, "Return level.")
        .def("getStats", &CCreature::getStats, "Return aggregated combat stats.")
        .def("addManaProc", &CCreature::addManaProc, "Restore mana by percentage of max mana.")
        .def("isPlayer", &CCreature::isPlayer, "Return whether this creature is the active player.")
        .def("isNpc", &CCreature::isNpc, "Return whether this creature is marked as NPC.")
        .def("setHp", &CCreature::setHp, "Set current HP.")
        .def("setMana", &CCreature::setMana, "Set current mana.")
        .def("addExp", &CCreature::addExp, "Add experience and trigger level ups when thresholds are reached.")
        .def("useAction", &CCreature::useAction, "Use an interaction/action against another creature.")
        .def("hasItem", hasItem, "Return whether any inventory item matches predicate(item) -> bool.")
        .def("addItem", addItemByName, "Create and add an item by type id.")
        .def("addItem", addItemByObject, "Add an existing item object.")
        .def("addItems", &CCreature::addItems, "Add all items from a set to inventory.")
        .def("removeItem", removeItem,
             "Remove the first inventory item matching predicate(item). Optional second arg allows quest removal.")
        .def("removeQuestItem", removeQuestItem, "Remove first matching quest item predicate from inventory.")
        .def("countItems", &CCreature::countItems, "Count inventory items by type id.");

    py::class_<CPlayer, CCreature, std::shared_ptr<CPlayer>>(m, "CPlayer",
                                                                                    "Player-controlled creature.")
        .def("addQuest", &CPlayer::addQuest, "Add a quest to the player quest log.");

    py::class_<CListString, CGameObject, std::shared_ptr<CListString>>(m, "CListString", "String list wrapper object.")
        .def("addValue", &CListString::addValue, "Append a value to the list.");

    py::class_<CGamePanel, CGameGraphicsObject, std::shared_ptr<CGamePanel>>(m, "CGamePanel", "Base in-game GUI panel.");

    py::class_<CGameTradePanel, CGamePanel, std::shared_ptr<CGameTradePanel>>(m, "CGameTradePanel",
                                                                                                     "Trade panel.")
        .def("getMarket", &CGameTradePanel::getMarket, "Return market displayed by this panel.");

    py::class_<CGameFightPanel, CGamePanel, std::shared_ptr<CGameFightPanel>>(m, "CGameFightPanel",
                                                                                                     "Fight panel.")
        .def("getEnemy", &CGameFightPanel::getEnemy, "Return current enemy creature.");

    py::class_<CGameCharacterPanel, CGamePanel, std::shared_ptr<CGameCharacterPanel>>(m, "CGameCharacterPanel", "Character sheet panel.");

    py::class_<CGameQuestionPanel, CGamePanel, std::shared_ptr<CGameQuestionPanel>>(m, "CGameQuestionPanel", "Question/choice panel.");

    py::class_<CGameDialogPanel, CGamePanel, std::shared_ptr<CGameDialogPanel>>(m, "CGameDialogPanel", "Dialog conversation panel.");

    py::class_<CGameInventoryPanel, CGamePanel, std::shared_ptr<CGameInventoryPanel>>(m, "CGameInventoryPanel", "Inventory panel.");

    py::class_<CGameQuestPanel, CGamePanel, std::shared_ptr<CGameQuestPanel>>(m, "CGameQuestPanel", "Quest log panel.");

    py::class_<CGameTextPanel, CGamePanel, std::shared_ptr<CGameTextPanel>>(m, "CGameTextPanel", "Text display panel.");

    py::class_<CProxyTargetGraphicsObject, CGameGraphicsObject,
           std::shared_ptr<CProxyTargetGraphicsObject>>(m, "CProxyTargetGraphicsObject",
                                                        "Graphics object that proxies a target object.");

    py::class_<CListView, CProxyTargetGraphicsObject, std::shared_ptr<CListView>>(m, "CListView", "List view widget.");
    PY_WRAP_GENERIC_DOC(randint, "randint(lower, upper) -> int: Return a random integer in engine-defined bounds.");
    PY_WRAP_GENERIC_DOC(jsonify, "jsonify(obj) -> str: Serialize a game object to JSON text.");
    PY_WRAP_GENERIC_DOC(logger, "logger(message) -> None: Write an info log message to the engine logger.");
    m.def("set_logger_sink", set_logger_sink_py,
          "set_logger_sink(sink, path=None) -> None: Configure the native logger output target.");
}
