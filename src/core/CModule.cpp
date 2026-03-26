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
#include "core/CWrapper.h"

using namespace boost::python;

int randint(int i, int j) {
    return vstd::rand(i, j); // TODO: unify and document exclusive inclusive
}

std::string jsonify(std::shared_ptr<CGameObject> x) { return JSONIFY(x); }

void logger(std::string s) {
    vstd::logger::info(std::move(s)); // TODO: add script name
}

list map_get_objects(const std::shared_ptr<CMap> &map) {
    list objects;
    for (const auto &object : map->getObjects()) {
        objects.append(object);
    }
    return objects;
}

extern void initModule1();

#define PY_WRAP_GENERIC_DOC(fcn, doc) def(#fcn, fcn, doc)

BOOST_PYTHON_MODULE(_game) {
    class_<CGameObject, boost::noncopyable, std::shared_ptr<CGameObject>>(
        "CGameObject", "Base engine object with dynamic string, numeric, bool, and object properties.")
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

    class_<Coords>("Coords", "3D integer coordinates (x, y, z).", init<int, int, int>())
        .def_readonly("x", &Coords::x)
        .def_readonly("y", &Coords::y)
        .def_readonly("z", &Coords::z);

    std::shared_ptr<CGameObject> (CGame::*createObject)(std::string) = &CGame::createObject<CGameObject>;

    class_<CGame, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGame>>(
        "CGame", "Top-level game container holding the active map, handlers, and GUI.")
        .def("getMap", &CGame::getMap, "Return the currently loaded map.")
        .def("changeMap", &CGame::changeMap, "Load and switch to another map.")
        .def("loadPlugin", &CGame::loadPlugin, "Load a plugin object into the game.")
        .def("getGuiHandler", &CGame::getGuiHandler, "Return the GUI handler service.")
        .def("getObjectHandler", &CGame::getObjectHandler, "Return the object factory/registry handler.")
        .def("getRngHandler", &CGame::getRngHandler, "Return the random encounter/loot handler.")
        .def("createObject", createObject, "Create an object by configured type id.")
        .def("getGui", &CGame::getGui, "Return the GUI root object.");

    class_<CGameGraphicsObject, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGameGraphicsObject>>(
        "CGameGraphicsObject", "Base class for GUI graphics objects.")
        .def("getGui", &CGameGraphicsObject::getGui, "Return the owning GUI object.")
        .def("getParent", &CGameGraphicsObject::getParent, "Return the parent graphics object.");

    class_<CGui, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CGui>>("CGui", "Game GUI root object.")
        .def("getGame", &CGui::getGame, "Return the owning game.");

    class_<CStatsGraphicsObject, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CStatsGraphicsObject>>(
        "CGameGraphicsObject");

    class_<CSideBar, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CSideBar>>("CSideBar");

    class_<CCreatureView, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CCreatureView>>(
        "CCreatureView", "Panel widget that renders a creature.")
        .def("getCreature", &CCreatureView::getCreature, "Return the creature shown in this view.");

    bool (CMap::*canStep)(Coords) = &CMap::canStep;
    void (CMap::*addObject)(const std::shared_ptr<CMapObject> &) = &CMap::addObject;

    class_<CMap, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMap>>(
        "CMap", "Runtime map containing tiles, map objects, triggers, and turn state.")
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

    void (CObjectHandler::*registerType)(std::string, std::function<std::shared_ptr<CGameObject>()>) =
        &CObjectHandler::registerType;
    std::shared_ptr<CGameObject> (*createObjectByType)(std::shared_ptr<CObjectHandler>, std::shared_ptr<CGame>,
                                                       std::string) =
        [](std::shared_ptr<CObjectHandler> handler, std::shared_ptr<CGame> game, std::string type) {
            return handler->createObject<CGameObject>(game, type);
        };
    class_<CObjectHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CObjectHandler>>(
        "CObjectHandler", "Factory and type/config registry for runtime objects.")
        .def("registerType", registerType, "Register a class constructor under a class name.")
        .def("createObject", createObjectByType, "Create an object by configured type id.")
        .def("getAllTypes", &CObjectHandler::getAllTypes, "Return all configured object type ids.")
        .def("getAllSubTypes", &CObjectHandler::getAllSubTypes,
             "Return configured type ids whose class inherits the given base class.");

    class_<CGuiHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGuiHandler>>(
        "CGuiHandler", "High-level helper for opening UI panels.")
        .def("showMessage", &CGuiHandler::showMessage, "Show a message panel.")
        .def("showTrade", &CGuiHandler::showTrade, "Open a trade panel.")
        .def("showDialog", &CGuiHandler::showDialog, "Open a dialog panel.")
        .def("showQuestion", &CGuiHandler::showQuestion, "Open a question/choice panel.")
        .def("showSelection", &CGuiHandler::showSelection, "Open a selection panel.")
        .def("showInfo", &CGuiHandler::showInfo, "Open an info panel.")
        .def("showLoot", &CGuiHandler::showLoot, "Show loot acquisition UI.");

    void (CRngHandler::*addRandomLoot)(const std::shared_ptr<CCreature> &, int) = &CRngHandler::addRandomLoot;
    class_<CRngHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CRngHandler>>(
        "CRngHandler", "Random loot and encounter generator.")
        .def("addRandomLoot", addRandomLoot, "Generate random loot for a creature and apply/show it.")
        .def("addRandomEncounter", &CRngHandler::addRandomEncounter,
             "Generate and place random enemy creatures on a map.");

    void (CMapObject::*moveTo)(int, int, int) = &CMapObject::moveTo;
    void (CMapObject::*move)(int, int, int) = &CMapObject::move;
    class_<CMapObject, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMapObject>>(
        "CMapObject", "Base object that exists at map coordinates.")
        .def("getMap", &CMapObject::getMap, "Return the map containing this object.")
        .def("moveTo", moveTo, "Move this object to absolute coordinates.")
        .def("move", move, "Move this object by relative coordinate delta.")
        .def("getCoords", &CMapObject::getCoords, "Return current map coordinates.")
        .def("setCoords", &CMapObject::setCoords, "Set map coordinates.");

    class_<CBuilding, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CBuilding>>("CBuildingBase",
                                                                                         "Base building object class.");
    class_<CWrapper<CBuilding>, bases<CBuilding>, boost::noncopyable, std::shared_ptr<CWrapper<CBuilding>>>(
        "CBuilding", "Python-overridable building implementation.")
        .def("onCreate", &CWrapper<CBuilding>::onCreate, "Handle onCreate game event.")
        .def("onTurn", &CWrapper<CBuilding>::onTurn, "Handle onTurn game event.")
        .def("onDestroy", &CWrapper<CBuilding>::onDestroy, "Handle onDestroy game event.")
        .def("onLeave", &CWrapper<CBuilding>::onLeave, "Handle onLeave game event.")
        .def("onEnter", &CWrapper<CBuilding>::onEnter, "Handle onEnter game event.");

    class_<CEvent, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CEvent>>("CEventBase",
                                                                                   "Base map event object class.");
    class_<CWrapper<CEvent>, bases<CEvent>, boost::noncopyable, std::shared_ptr<CWrapper<CEvent>>>(
        "CEvent", "Python-overridable map event object.")
        .def("onCreate", &CWrapper<CEvent>::onCreate, "Handle onCreate game event.")
        .def("onTurn", &CWrapper<CEvent>::onTurn, "Handle onTurn game event.")
        .def("onLeave", &CWrapper<CEvent>::onLeave, "Handle onLeave game event.")
        .def("onDestroy", &CWrapper<CEvent>::onDestroy, "Handle onDestroy game event.")
        .def("onEnter", &CWrapper<CEvent>::onEnter, "Handle onEnter game event.");

    class_<CInteraction, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CInteraction>>(
        "CInteractionBase", "Base interaction/action definition.")
        .def("onAction", &CInteraction::onAction, "Engine callback when the interaction is activated.");
    class_<CWrapper<CInteraction>, bases<CInteraction>, boost::noncopyable, std::shared_ptr<CWrapper<CInteraction>>>(
        "CInteraction", "Python-overridable interaction class.")
        .def("performAction", &CWrapper<CInteraction>::performAction,
             "Perform the interaction between source and target creatures.")
        .def("configureEffect", &CWrapper<CInteraction>::configureEffect,
             "Configure an effect instance before it is applied.");

    class_<Damage, bases<CGameObject>, boost::noncopyable, std::shared_ptr<Damage>>(
        "Damage", "Damage packet with typed damage components.");
    class_<Stats, bases<CGameObject>, boost::noncopyable, std::shared_ptr<Stats>>(
        "Stats", "Creature stat container used for combat calculations.")
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

    class_<CTile, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CTile>>("CTileBase", "Base tile class.");
    class_<CWrapper<CTile>, bases<CTile>, boost::noncopyable, std::shared_ptr<CWrapper<CTile>>>(
        "CTile", "Python-overridable tile class.")
        .def("onStep", &CWrapper<CTile>::onStep, "Handle a creature stepping on this tile.");

    class_<CItem, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CItem>>("CItem",
                                                                                 "Base inventory/equipment item.");
    class_<CPotion, bases<CItem>, boost::noncopyable, std::shared_ptr<CPotion>>("CPotionBase",
                                                                                "Base potion item class.");
    class_<CWrapper<CPotion>, bases<CPotion>, boost::noncopyable, std::shared_ptr<CWrapper<CPotion>>>(
        "CPotion", "Python-overridable potion class.")
        .def("onUse", &CWrapper<CPotion>::onUse, "Handle potion use event.");
    class_<CScroll, bases<CItem>, boost::noncopyable, std::shared_ptr<CScroll>>("CScrollBase",
                                                                                "Base scroll item class.");
    class_<CWrapper<CScroll>, bases<CScroll>, boost::noncopyable, std::shared_ptr<CWrapper<CScroll>>>(
        "CScroll", "Python-overridable scroll class.")
        .def("onUse", &CWrapper<CScroll>::onUse, "Handle scroll use event.")
        .def("isDisposable", &CWrapper<CScroll>::isDisposable, "Return whether the scroll is consumed on use.");

    class_<CGameEvent, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGameEvent>>("CGameEvent",
                                                                                            "Base event object.");
    class_<CGameEventCaused, bases<CGameEvent>, boost::noncopyable, std::shared_ptr<CGameEventCaused>>(
        "CGameEventCaused", "Event carrying a causing game object.")
        .def("getCause", &CGameEventCaused::getCause, "Return the object that caused this event.");

    class_<CTrigger, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CTrigger>>("CTriggerBase",
                                                                                        "Base trigger class.");
    class_<CWrapper<CTrigger>, bases<CTrigger>, boost::noncopyable, std::shared_ptr<CWrapper<CTrigger>>>(
        "CTrigger", "Python-overridable trigger class.")
        .def("trigger", &CWrapper<CTrigger>::trigger, "Handle trigger execution for an object and event.");

    class_<CQuest, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CQuest>>("CQuestBase", "Base quest class.");
    class_<CWrapper<CQuest>, bases<CQuest>, boost::noncopyable, std::shared_ptr<CWrapper<CQuest>>>(
        "CQuest", "Python-overridable quest class.")
        .def("isCompleted", &CWrapper<CQuest>::isCompleted, "Return whether quest objectives are completed.")
        .def("onComplete", &CWrapper<CQuest>::onComplete, "Handle quest completion callback.");

    class_<CDialog, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CDialog>>("CDialogBase",
                                                                                      "Base dialog definition.");
    class_<CWrapper<CDialog>, bases<CDialog>, boost::noncopyable, std::shared_ptr<CWrapper<CDialog>>>(
        "CDialogBase2", "Python-overridable dialog callbacks.")
        .def("invokeAction", &CWrapper<CDialog>::invokeAction, "Run a named dialog action callback.")
        .def("invokeCondition", &CWrapper<CDialog>::invokeCondition, "Evaluate a named dialog condition callback.");

    class_<CDialogOption, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CDialogOption>>(
        "CDialogOption", "Single selectable dialog option.");
    class_<CDialogState, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CDialogState>>("CDialogState",
                                                                                                "Dialog state node.");

    class_<CEventHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CEventHandler>>(
        "CEventHandler", "Dispatcher for game/map events.")
        .def("registerTrigger", &CEventHandler::registerTrigger, "Register a trigger for an event type.");

    class_<CFightHandler, boost::noncopyable, std::shared_ptr<CFightHandler>>("CFightHandler",
                                                                              "Combat resolution service.")
        .def("fight", &CFightHandler::fight, "Run a fight between two creatures.");

    class_<CMarket, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMarket>>("CMarket",
                                                                                      "Trading inventory and prices.");

    class_<CGameLoader, boost::noncopyable, std::shared_ptr<CGameLoader>>(
        "CGameLoader", "Factory helpers for loading game sessions and maps.")
        .def("loadGame", &CGameLoader::loadGame, "Create and initialize a game instance.")
        .def("startGameWithPlayer", &CGameLoader::startGameWithPlayer, "Start a map with a specific player template.")
        .def("startRandomGameWithPlayer", &CGameLoader::startRandomGameWithPlayer,
             "Start a random map with a specific player template.")
        .def("startGame", &CGameLoader::startGame, "Start a specific map with current player data.")
        .def("loadGui", &CGameLoader::loadGui, "Load and attach GUI objects for a game.")
        .def("loadSavedGame", &CGameLoader::loadSavedGame, "Load a saved game state from storage.");

    class_<CMapLoader, boost::noncopyable, std::shared_ptr<CMapLoader>>("CMapLoader",
                                                                        "Helpers for loading map resources.")
        .def("loadNewMapWithPlayer", &CMapLoader::loadNewMapWithPlayer, "Load a map and place a player template.")
        .def("loadNewMap", &CMapLoader::loadNewMap, "Load a map without changing the active player.");

    class_<CPlugin, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CPlugin>>("CPluginBase",
                                                                                      "Base plugin class.");
    class_<CWrapper<CPlugin>, bases<CPlugin>, boost::noncopyable, std::shared_ptr<CWrapper<CPlugin>>>(
        "CPlugin", "Python-overridable plugin class.")
        .def("load", &CWrapper<CPlugin>::load, "Load plugin content into a game.");

    class_<vstd::event_loop<>, boost::noncopyable, std::shared_ptr<vstd::event_loop<>>>(
        "event_loop", "Global async event loop utility.")
        .def("instance", &vstd::event_loop<>::instance, "Return the singleton event loop instance.")
        .def("run", &vstd::event_loop<>::run, "Process queued tasks/events once.")
        .def("invoke", &vstd::event_loop<>::invoke, "Queue a callable for later execution.");

    class_<std::vector<std::string>>("std::vector<std::string>", "Mutable list of strings.")
        .def(vector_indexing_suite<std::vector<std::string>>());

    class_<CResourcesProvider, boost::noncopyable, std::shared_ptr<CResourcesProvider>>(
        "CResourcesProvider", "Access to packaged resource files.")
        .def("getInstance", &CResourcesProvider::getInstance, "Return singleton resource provider.")
        .def("getFiles", &CResourcesProvider::getFiles, "List files under a resource path.");

    class_<CEffect, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CEffect>>("CEffectBase",
                                                                                      "Base status effect class.")
        .def("getBonus", &CEffect::getBonus, "Return effect stat bonus object.")
        .def("setBonus", &CEffect::setBonus, "Set effect stat bonus object.")
        .def("getCaster", &CEffect::getCaster, "Return creature that applied the effect.")
        .def("getVictim", &CEffect::getVictim, "Return creature affected by the effect.")
        .def("getTimeLeft", &CEffect::getTimeLeft, "Return remaining effect duration in turns.");
    class_<CWrapper<CEffect>, bases<CEffect>, boost::noncopyable, std::shared_ptr<CWrapper<CEffect>>>(
        "CEffect", "Python-overridable effect class.")
        .def("onEffect", &CWrapper<CEffect>::onEffect, "Apply effect behavior for one tick.");

    class_<CWeapon, bases<CItem>, boost::noncopyable, std::shared_ptr<CWeapon>>("CWeapon", "Weapon item.")
        .def("getInteraction", &CWeapon::getInteraction, "Return interaction used when this weapon is applied.");

    void (CCreature::*hurtInt)(int) = &CCreature::hurt;
    void (CCreature::*hurtFloat)(float) = &CCreature::hurt;
    void (CCreature::*hurtDmg)(std::shared_ptr<Damage>) = &CCreature::hurt;
    void (CCreature::*addItemByName)(std::string) = &CCreature::addItem;
    void (CCreature::*addItemByObject)(std::shared_ptr<CItem>) = &CCreature::addItem;
    bool (CCreature::*hasItem)(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::hasItem;
    void (CCreature::*removeItem)(std::function<bool(std::shared_ptr<CItem>)>, bool) = &CCreature::removeItem;
    void (CCreature::*removeQuestItem)(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::removeQuestItem;
    class_<CCreature, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CCreature>>(
        "CCreature", "Creature that can move, fight, and manage inventory.")
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

    class_<CPlayer, bases<CCreature>, boost::noncopyable, std::shared_ptr<CPlayer>>("CPlayer",
                                                                                    "Player-controlled creature.")
        .def("addQuest", &CPlayer::addQuest, "Add a quest to the player quest log.");

    class_<CListString, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CListString>>(
        "CListString", "String list wrapper object.")
        .def("addValue", &CListString::addValue, "Append a value to the list.");

    class_<CGamePanel, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CGamePanel>>(
        "CGamePanel", "Base in-game GUI panel.");

    class_<CGameTradePanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameTradePanel>>("CGameTradePanel",
                                                                                                     "Trade panel.")
        .def("getMarket", &CGameTradePanel::getMarket, "Return market displayed by this panel.");

    class_<CGameFightPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameFightPanel>>("CGameFightPanel",
                                                                                                     "Fight panel.")
        .def("getEnemy", &CGameFightPanel::getEnemy, "Return current enemy creature.");

    class_<CGameCharacterPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameCharacterPanel>>(
        "CGameCharacterPanel", "Character sheet panel.");

    class_<CGameQuestionPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameQuestionPanel>>(
        "CGameQuestionPanel", "Question/choice panel.");

    class_<CGameDialogPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameDialogPanel>>(
        "CGameDialogPanel", "Dialog conversation panel.");

    class_<CGameInventoryPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameInventoryPanel>>(
        "CGameInventoryPanel", "Inventory panel.");

    class_<CGameQuestPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameQuestPanel>>(
        "CGameQuestPanel", "Quest log panel.");

    class_<CGameTextPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameTextPanel>>(
        "CGameTextPanel", "Text display panel.");

    class_<CProxyTargetGraphicsObject, bases<CGameGraphicsObject>, boost::noncopyable,
           std::shared_ptr<CProxyTargetGraphicsObject>>("CProxyTargetGraphicsObject",
                                                        "Graphics object that proxies a target object.");

    class_<CListView, bases<CProxyTargetGraphicsObject>, boost::noncopyable, std::shared_ptr<CListView>>(
        "CListView", "List view widget.");
    PY_WRAP_GENERIC_DOC(randint, "randint(lower, upper) -> int: Return a random integer in engine-defined bounds.");
    PY_WRAP_GENERIC_DOC(jsonify, "jsonify(obj) -> str: Serialize a game object to JSON text.");
    PY_WRAP_GENERIC_DOC(logger, "logger(message) -> None: Write an info log message to the engine logger.");
}
