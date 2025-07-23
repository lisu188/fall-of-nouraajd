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
#include <utility>

#include "core/CLoader.h"
#include "core/CWrapper.h"
#include "core/CJsonUtil.h"
#include "CGame.h"
#include "CMap.h"
#include "CList.h"
#include "../gui/CGui.h"
#include "../gui/panel/CCreatureView.h"
#include "../gui/panel/CGameCharacterPanel.h"
#include "../gui/panel/CGameTradePanel.h"
#include "../gui/panel/CGameFightPanel.h"
#include "../gui/panel/CGameInventoryPanel.h"
#include "../gui/panel/CGameQuestionPanel.h"
#include "../gui/panel/CGameQuestPanel.h"
#include "../gui/panel/CGameTextPanel.h"
#include "../gui/panel/CGameDialogPanel.h"
#include "../gui/panel/CListView.h"
#include "../gui/object/CStatsGraphicsObject.h"
#include "../gui/object/CSideBar.h"
#include "../handler/CRngHandler.h"
#include "../object/CDialog.h"
#include "CProvider.h"
#include "../handler/CHandler.h"
#include "../../vstd/vstd.h"

using namespace boost::python;

int randint(int i, int j) {
    return vstd::rand(i, j);//TODO: unify and document exclusive inclusive
}

std::string jsonify(std::shared_ptr<CGameObject> x) {
    return JSONIFY(x);
}

void logger(std::string s) {
    vstd::logger::info(std::move(s));//TODO: add script name
}

extern void initModule1();



#define PY_WRAP_GENERIC(fcn) def(#fcn,boost::python::make_function(fcn))

BOOST_PYTHON_MODULE (_game) {
     class_<CGameObject, boost::noncopyable, std::shared_ptr<CGameObject>>("CGameObject")
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

        std::shared_ptr<CGameObject> (CGame::*createObject)(std::string) = &CGame::createObject<CGameObject>;

        class_<CGame, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGame>>("CGame")
                .def("getMap", &CGame::getMap)
                .def("changeMap", &CGame::changeMap)
                .def("loadPlugin", &CGame::loadPlugin)
                .def("getGuiHandler", &CGame::getGuiHandler)
                .def("getObjectHandler", &CGame::getObjectHandler)
                .def("getRngHandler", &CGame::getRngHandler)
                .def("createObject", createObject)
                .def("getGui", &CGame::getGui);

        class_<CGameGraphicsObject, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGameGraphicsObject>>(
                        "CGameGraphicsObject")
                .def("getGui", &CGameGraphicsObject::getGui)
                .def("getParent", &CGameGraphicsObject::getParent);

        class_<CGui, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CGui>>("CGui")
                .def("getGame", &CGui::getGame);

        class_<CStatsGraphicsObject, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<
                       CStatsGraphicsObject>>("CGameGraphicsObject");

        class_<CSideBar, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CSideBar>>("CSideBar");

        class_<CCreatureView, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CCreatureView>>(
                        "CCreatureView")
                .def("getCreature", &CCreatureView::getCreature);

        bool (CMap::*canStep)(Coords) = &CMap::canStep;
        void (CMap::*addObject)(const std::shared_ptr<CMapObject>&) = &CMap::addObject;

        class_<CMap, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMap>>("CMap")
                .def("addObjectByName", &CMap::addObjectByName)
                .def("removeObjectByName", &CMap::removeObjectByName)
                .def("removeObject", &CMap::removeObject)
                .def("replaceTile", &CMap::replaceTile)
                .def("getPlayer", &CMap::getPlayer)
                .def("getLocationByName", &CMap::getLocationByName)
                .def("removeAll", &CMap::removeObjects)
                .def("getEventHandler", &CMap::getEventHandler)
                .def("addObject", addObject)
                .def("getGame", &CMap::getGame)
                .def("move", &CMap::move)
                .def("getObjectByName", &CMap::getObjectByName)
                .def("forObjects", &CMap::forObjects)
                .def("canStep", canStep)
                .def("dumpPaths", &CMap::dumpPaths)
                .def("getEntryX", &CMap::getEntryX)
                .def("getEntryY", &CMap::getEntryY)
                .def("getEntryZ", &CMap::getEntryZ)
                .def("getObjects", &CMap::getObjects)
                .def("getTurn", &CMap::getTurn);

        void (CObjectHandler::*registerType)(std::string, std::function<std::shared_ptr<CGameObject>()>) = &
                CObjectHandler::registerType;
        class_<CObjectHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CObjectHandler>>(
                        "CObjectHandler")
                .def("registerType", registerType)
                .def("getAllTypes", &CObjectHandler::getAllTypes)
                .def("getAllSubTypes", &CObjectHandler::getAllSubTypes);

        class_<CGuiHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGuiHandler>>("CGuiHandler")
                .def("showMessage", &CGuiHandler::showMessage)
                .def("showTrade", &CGuiHandler::showTrade)
                .def("showDialog", &CGuiHandler::showDialog)
                .def("showQuestion", &CGuiHandler::showQuestion)
                .def("showSelection", &CGuiHandler::showSelection)
                .def("showInfo", &CGuiHandler::showInfo)
                .def("showLoot", &CGuiHandler::showLoot);

        void (CRngHandler::*addRandomLoot)(const std::shared_ptr<CCreature>&, int) = &CRngHandler::addRandomLoot;
        class_<CRngHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CRngHandler>>("CRngHandler")
                .def("addRandomLoot", addRandomLoot)
                .def("addRandomEncounter", &CRngHandler::addRandomEncounter);

        void (CMapObject::*moveTo)(int, int, int) = &CMapObject::moveTo;
        void (CMapObject::*move)(int, int, int) = &CMapObject::move;
        class_<CMapObject, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMapObject>>("CMapObject")
                .def("getMap", &CMapObject::getMap)
                .def("moveTo", moveTo)
                .def("move", move)
                .def("getCoords", &CMapObject::getCoords)
                .def("setCoords", &CMapObject::setCoords);

        class_<CBuilding, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CBuilding>>("CBuildingBase");
        class_<CWrapper<CBuilding>, bases<CBuilding>, boost::noncopyable, std::shared_ptr<CWrapper<CBuilding>>>(
                        "CBuilding")
                .def("onCreate", &CWrapper<CBuilding>::onCreate)
                .def("onTurn", &CWrapper<CBuilding>::onTurn)
                .def("onDestroy", &CWrapper<CBuilding>::onDestroy)
                .def("onLeave", &CWrapper<CBuilding>::onLeave)
                .def("onEnter", &CWrapper<CBuilding>::onEnter);

        class_<CEvent, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CEvent>>("CEventBase");
        class_<CWrapper<CEvent>, bases<CEvent>, boost::noncopyable, std::shared_ptr<CWrapper<CEvent>>>("CEvent")
                .def("onCreate", &CWrapper<CEvent>::onCreate)
                .def("onTurn", &CWrapper<CEvent>::onTurn)
                .def("onLeave", &CWrapper<CEvent>::onLeave)
                .def("onDestroy", &CWrapper<CEvent>::onDestroy)
                .def("onEnter", &CWrapper<CEvent>::onEnter);

        class_<CInteraction, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CInteraction>>("CInteractionBase")
                .def("onAction", &CInteraction::onAction);
        class_<CWrapper<CInteraction>, bases<CInteraction>, boost::noncopyable, std::shared_ptr<CWrapper<
                       CInteraction>>>("CInteraction")
                .def("performAction", &CWrapper<CInteraction>::performAction)
                .def("configureEffect", &CWrapper<CInteraction>::configureEffect);

        class_<Damage, bases<CGameObject>, boost::noncopyable, std::shared_ptr<Damage>>("Damage");
        class_<Stats, bases<CGameObject>, boost::noncopyable, std::shared_ptr<Stats>>("Stats");

        class_<CTile, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CTile>>("CTileBase");
        class_<CWrapper<CTile>, bases<CTile>, boost::noncopyable, std::shared_ptr<CWrapper<CTile>>>("CTile")
                .def("onStep", &CWrapper<CTile>::onStep);

        class_<CItem, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CItem>>("CItem");
        class_<CPotion, bases<CItem>, boost::noncopyable, std::shared_ptr<CPotion>>("CPotionBase");
        class_<CWrapper<CPotion>, bases<CPotion>, boost::noncopyable, std::shared_ptr<CWrapper<CPotion>>>("CPotion")
                .def("onUse", &CWrapper<CPotion>::onUse);
        class_<CScroll, bases<CItem>, boost::noncopyable, std::shared_ptr<CScroll>>("CScrollBase");
        class_<CWrapper<CScroll>, bases<CScroll>, boost::noncopyable, std::shared_ptr<CWrapper<CScroll>>>("CScroll")
                .def("onUse", &CWrapper<CScroll>::onUse)
                .def("isDisposable", &CWrapper<CScroll>::isDisposable);

        class_<CScroll, bases<CItem>, boost::noncopyable, std::shared_ptr<CScroll>>("CScrollBase");
        class_<CWrapper<CScroll>, bases<CScroll>, boost::noncopyable, std::shared_ptr<CWrapper<CScroll>>>("CScroll")
                .def("onUse", &CWrapper<CScroll>::onUse)
                .def("isDisposable", &CWrapper<CScroll>::isDisposable);

        class_<CGameEvent, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGameEvent>>("CGameEvent");
        class_<CGameEventCaused, bases<CGameEvent>, boost::noncopyable, std::shared_ptr<CGameEventCaused>>(
                        "CGameEventCaused")
                .def("getCause", &CGameEventCaused::getCause);

        class_<CTrigger, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CTrigger>>("CTriggerBase");
        class_<CWrapper<CTrigger>, bases<CTrigger>, boost::noncopyable, std::shared_ptr<CWrapper<CTrigger>>>("CTrigger")
                .def("trigger", &CWrapper<CTrigger>::trigger);

        class_<CQuest, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CQuest>>("CQuestBase");
        class_<CWrapper<CQuest>, bases<CQuest>, boost::noncopyable, std::shared_ptr<CWrapper<CQuest>>>("CQuest")
                .def("isCompleted", &CWrapper<CQuest>::isCompleted)
                .def("onComplete", &CWrapper<CQuest>::onComplete);

        class_<CDialog, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CDialog>>("CDialogBase");
        class_<CWrapper<CDialog>, bases<CDialog>, boost::noncopyable, std::shared_ptr<CWrapper<CDialog>>>(
                        "CDialogBase2")
                .def("invokeAction", &CWrapper<CDialog>::invokeAction)
                .def("invokeCondition", &CWrapper<CDialog>::invokeCondition);

        class_<CDialogOption, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CDialogOption>>("CDialogOption");
        class_<CDialogState, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CDialogState>>("CDialogState");

        class_<CEventHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CEventHandler>>("CEventHandler")
                .def("registerTrigger", &CEventHandler::registerTrigger);

        class_<CFightHandler, boost::noncopyable, std::shared_ptr<CFightHandler>>("CFightHandler")
                .def("fight", &CFightHandler::fight);

        class_<CMarket, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMarket>>("CMarket");

        class_<CGameLoader, boost::noncopyable, std::shared_ptr<CGameLoader>>("CGameLoader")
                .def("loadGame", &CGameLoader::loadGame)
                .def("startGameWithPlayer", &CGameLoader::startGameWithPlayer)
                .def("startRandomGameWithPlayer", &CGameLoader::startRandomGameWithPlayer)
                .def("startGame", &CGameLoader::startGame)
                .def("loadGui", &CGameLoader::loadGui)
                .def("loadSavedGame", &CGameLoader::loadSavedGame);

        class_<CMapLoader, boost::noncopyable, std::shared_ptr<CMapLoader>>("CMapLoader")
                .def("loadNewMapWithPlayer", &CMapLoader::loadNewMapWithPlayer)
                .def("loadNewMap", &CMapLoader::loadNewMap);

        class_<CPlugin, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CPlugin>>("CPluginBase");
        class_<CWrapper<CPlugin>, bases<CPlugin>, boost::noncopyable, std::shared_ptr<CWrapper<CPlugin>>>("CPlugin")
                .def("load", &CWrapper<CPlugin>::load);

        class_<vstd::event_loop<>, boost::noncopyable, std::shared_ptr<vstd::event_loop<>>>("event_loop")
                .def("instance", &vstd::event_loop<>::instance)
                .def("run", &vstd::event_loop<>::run)
                .def("invoke", &vstd::event_loop<>::invoke);

        class_<std::vector<std::string>>("std::vector<std::string>")
                .def(vector_indexing_suite<std::vector<std::string>>());

        class_<CResourcesProvider, boost::noncopyable, std::shared_ptr<CResourcesProvider>>("CResourcesProvider")
                .def("getInstance", &CResourcesProvider::getInstance)
                .def("getFiles", &CResourcesProvider::getFiles);

        class_<CEffect, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CEffect>>("CEffectBase")
                .def("getBonus", &CEffect::getBonus)
                .def("setBonus", &CEffect::setBonus)
                .def("getCaster", &CEffect::getCaster)
                .def("getVictim", &CEffect::getVictim)
                .def("getTimeLeft", &CEffect::getTimeLeft);
        class_<CWrapper<CEffect>, bases<CEffect>, boost::noncopyable, std::shared_ptr<CWrapper<CEffect>>>("CEffect")
                .def("onEffect", &CWrapper<CEffect>::onEffect);

        class_<CWeapon, bases<CItem>, boost::noncopyable, std::shared_ptr<CWeapon>>("CWeapon")
                .def("getInteraction", &CWeapon::getInteraction);

        void (CCreature::*hurtInt)(int) = &CCreature::hurt;
        void (CCreature::*hurtFloat)(float) = &CCreature::hurt;
        void (CCreature::*hurtDmg)(std::shared_ptr<Damage>) = &CCreature::hurt;
        void (CCreature::*addItem)(std::string) = &CCreature::addItem;
        bool (CCreature::*hasItem)(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::hasItem;
        void (CCreature::*removeItem)(std::function<bool(std::shared_ptr<CItem>)>, bool) = &CCreature::removeItem;
        void (CCreature::*removeQuestItem)(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::removeQuestItem;
        class_<CCreature, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CCreature>>("CCreature")
                .def("getDmg", &CCreature::getDmg)
                .def("hurt", hurtInt)
                .def("hurt", hurtDmg)
                .def("hurt", hurtFloat)
                .def("getWeapon", &CCreature::getWeapon)
                .def("getHpRatio", &CCreature::getHpRatio)
                .def("isAlive", &CCreature::isAlive)
                .def("getMana", &CCreature::getMana)
                .def("healProc", &CCreature::healProc)
                .def("heal", &CCreature::heal)
                .def("getHpMax", &CCreature::getHpMax)
                .def("getLevel", &CCreature::getLevel)
                .def("getStats", &CCreature::getStats)
                .def("addManaProc", &CCreature::addManaProc)
                .def("isPlayer", &CCreature::isPlayer)
                .def("addExp", &CCreature::addExp)
                .def("useAction", &CCreature::useAction)
                .def("hasItem", hasItem)
                .def("addItem", addItem)
                .def("addItems", &CCreature::addItems)
                .def("removeItem", removeItem)
                .def("removeQuestItem", removeQuestItem);

        class_<CPlayer, bases<CCreature>, boost::noncopyable, std::shared_ptr<CPlayer>>("CPlayer")
                .def("addQuest", &CPlayer::addQuest);

        class_<CListString, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CListString>>("CListString")
                .def("addValue", &CListString::addValue);

        class_<CGamePanel, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CGamePanel>>("CGamePanel");

        class_<CGameTradePanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameTradePanel>>(
                        "CGameTradePanel")
                .def("getMarket", &CGameTradePanel::getMarket);

        class_<CGameFightPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameFightPanel>>(
                        "CGameFightPanel")
                .def("getEnemy", &CGameFightPanel::getEnemy);

        class_<CGameCharacterPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameCharacterPanel>>(
                "CGameCharacterPanel");

        class_<CGameQuestionPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameQuestionPanel>>(
                "CGameQuestionPanel");

        class_<CGameDialogPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameDialogPanel>>(
                "CGameDialogPanel");

        class_<CGameInventoryPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameInventoryPanel>>(
                "CGameInventoryPanel");

        class_<CGameQuestPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameQuestPanel>>(
                "CGameQuestPanel");

        class_<CGameTextPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<
                       CGameTextPanel>>("CGameTextPanel");

        class_<CProxyTargetGraphicsObject, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<
                       CProxyTargetGraphicsObject>>("CProxyTargetGraphicsObject");

        class_<CListView, bases<CProxyTargetGraphicsObject>, boost::noncopyable, std::shared_ptr<CListView>>(
                "CListView");
    PY_WRAP_GENERIC(randint);
    PY_WRAP_GENERIC(jsonify);
    PY_WRAP_GENERIC(logger);
}
