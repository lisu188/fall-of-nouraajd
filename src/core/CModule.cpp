#include "core/CLoader.h"
#include "core/CWrapper.h"
#include "core/CEventLoop.h"

using namespace boost::python;

BOOST_PYTHON_MODULE (_game) {
    def("randint", randint);

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
            .def("clone", &CGameObject::clone<CGameObject>);

    class_<Coords>("Coords", init<int, int, int>())
            .def_readonly("x", &Coords::x)
            .def_readonly("y", &Coords::y)
            .def_readonly("z", &Coords::z);

    class_<CGame, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGame>>("CGame", no_init)
            .def("getMap", &CGame::getMap)
            .def("changeMap", &CGame::changeMap)
            .def("load_plugin", &CGame::load_plugin)
//TODO:            .def ( "getGuiHandler", &CGame::getGuiHandler )
            .def("getObjectHandler", &CGame::getObjectHandler);

    class_<CMap, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMap>>("CMap", no_init)
            .def("addObjectByName", &CMap::addObjectByName)
            .def("removeObjectByName", &CMap::removeObjectByName)
            .def("removeObject", &CMap::removeObject)
            .def("replaceTile", &CMap::replaceTile)
            .def("getPlayer", &CMap::getPlayer)
            .def("getLocationByName", &CMap::getLocationByName)
            .def("removeAll", &CMap::removeObjects)
            .def("getObjectHandler", &CMap::getObjectHandler)
            .def("getEventHandler", &CMap::getEventHandler)
            .def("addObject", &CMap::addObject)
            .def("createObject", &CMap::createObject<CGameObject>)
            .def("getGame", &CMap::getGame)
            .def("load_plugin", &CMap::load_plugin)
            .def("move", &CMap::move);

    void ( CObjectHandler::*registerType )(std::string,
                                           std::function<std::shared_ptr<CGameObject>()>) = &CObjectHandler::registerType;
    class_<CObjectHandler, boost::noncopyable, std::shared_ptr<CObjectHandler>>("CObjectHandler", no_init)
            .def("registerType", registerType);

    void ( CMapObject::*moveTo )(int, int, int) = &CMapObject::moveTo;
    void ( CMapObject::*move )(int, int, int) = &CMapObject::move;
    class_<CMapObject, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMapObject>>("CMapObject", no_init)
            .def("getMap", &CMapObject::getMap)
            .def("moveTo", moveTo)
            .def("move", move)
            .def("getCoords", &CMapObject::getCoords)
            .def("setCoords", &CMapObject::setCoords);


    class_<CEffect, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CEffect>>("CEffectBase")
            .def("getBonus", &CEffect::getBonus)
            .def("setBonus", &CEffect::setBonus)
            .def("getCaster", &CEffect::getCaster)
            .def("getVictim", &CEffect::getVictim)
            .def("getTimeLeft", &CEffect::getTimeLeft);
    class_<CWrapper<CEffect>, bases<CEffect>, boost::noncopyable, std::shared_ptr<CWrapper<CEffect>>>("CEffect")
            .def("onEffect", &CWrapper<CEffect>::onEffect);

    class_<CItem, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CItem>>("CItem");

    class_<CWeapon, bases<CItem>, boost::noncopyable, std::shared_ptr<CWeapon>>("CWeapon")
            .def("getInteraction", &CWeapon::getInteraction);

    void ( CCreature::*hurtInt )(int) = &CCreature::hurt;
    void ( CCreature::*hurtFloat )(float) = &CCreature::hurt;
    void ( CCreature::*hurtDmg )(std::shared_ptr<Damage>) = &CCreature::hurt;
    class_<CCreature, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CCreature>>("CCreature", no_init)
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
            .def("trade", &CCreature::trade);
    class_<CPlayer, bases<CCreature>, boost::noncopyable, std::shared_ptr<CPlayer>>("CPlayer")
            .def("addQuest", &CPlayer::addQuest);
    class_<CMonster, bases<CCreature>, boost::noncopyable, std::shared_ptr<CMonster>>("CMonster");

    class_<CBuilding, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CBuilding>>("CBuildingBase");
    class_<CWrapper<CBuilding>, bases<CBuilding>, boost::noncopyable, std::shared_ptr<CWrapper<CBuilding>>>("CBuilding")
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
    class_<CWrapper<CInteraction>, bases<CInteraction>, boost::noncopyable, std::shared_ptr<CWrapper<CInteraction>>>(
            "CInteraction")
            .def("performAction", &CWrapper<CInteraction>::performAction)
            .def("configureEffect", &CWrapper<CInteraction>::configureEffect);

    class_<Damage, bases<CGameObject>, boost::noncopyable, std::shared_ptr<Damage>>("Damage");
    class_<Stats, bases<CGameObject>, boost::noncopyable, std::shared_ptr<Stats>>("Stats");
    //TODO: panels
//    class_<AGamePanel, boost::noncopyable, std::shared_ptr<AGamePanel>> ( "AGamePanel", no_init )
//            .def ( "showPanel", &AGamePanel::showPanel );
//    class_<CTextPanel, bases<AGamePanel>, boost::noncopyable, std::shared_ptr<CTextPanel>> ( "CTextPanel" );
//    class_<CFightPanel, bases<AGamePanel>, boost::noncopyable, std::shared_ptr<CFightPanel>> ( "CFightPanel" );
//    class_<CCharPanel, bases<AGamePanel>, boost::noncopyable, std::shared_ptr<CCharPanel>> ( "CCharPanel" );
//    class_<CTradePanel, bases<AGamePanel>, boost::noncopyable, std::shared_ptr<CTradePanel>> ( "CTradePanel" );
//    class_<CGuiHandler, boost::noncopyable, std::shared_ptr<CGuiHandler>> ( "CGuiHandler", no_init )
//            .def ( "showMessage", &CGuiHandler::showMessage )
//            .def ( "showPanel", &CGuiHandler::showPanel )
//            .def ( "hidePanel", &CGuiHandler::hidePanel )
//            .def ( "flipPanel", &CGuiHandler::flipPanel );
    class_<CTile, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CTile>>("CTileBase");
    class_<CWrapper<CTile>, bases<CTile>, boost::noncopyable, std::shared_ptr<CWrapper<CTile>>>("CTile").
            def("onStep", &CWrapper<CTile>::onStep);

    class_<CPotion, bases<CItem>, boost::noncopyable, std::shared_ptr<CPotion>>("CPotionBase");
    class_<CWrapper<CPotion>, bases<CPotion>, boost::noncopyable, std::shared_ptr<CWrapper<CPotion>>>("CPotion").
            def("onUse", &CWrapper<CPotion>::onUse);

    //TODO: use CGameObject
    class_<CGameEvent, boost::noncopyable, std::shared_ptr<CGameEvent>>("CGameEvent", no_init);
    class_<CGameEventCaused, bases<CGameEvent>, boost::noncopyable, std::shared_ptr<CGameEventCaused>>(
            "CGameEventCaused", no_init)
            .def("getCause", &CGameEventCaused::getCause);

    class_<CTrigger, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CTrigger>>("CTriggerBase", no_init);
    class_<CWrapper<CTrigger>, bases<CTrigger>, boost::noncopyable, std::shared_ptr<CWrapper<CTrigger>>>("CTrigger")
            .def("trigger", &CWrapper<CTrigger>::trigger);

    class_<CQuest, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CQuest>>("CQuestBase", no_init);
    class_<CWrapper<CQuest>, bases<CQuest>, boost::noncopyable, std::shared_ptr<CWrapper<CQuest>>>("CQuest")
            .def("isCompleted", &CWrapper<CQuest>::isCompleted)
            .def("onComplete", &CWrapper<CQuest>::onComplete);

    class_<CEventHandler, boost::noncopyable, std::shared_ptr<CEventHandler>>("CEventHandler", no_init)
            .def("registerTrigger", &CEventHandler::registerTrigger);

    class_<CMarket, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMarket> >("CMarket");

    class_<CGameLoader, boost::noncopyable, std::shared_ptr<CGameLoader>>("CGameLoader", no_init)
            .def("loadGame", &CGameLoader::loadGame)
            .def("startGame", &CGameLoader::startGame);
    class_<CMapLoader, boost::noncopyable, std::shared_ptr<CMapLoader>>("CMapLoader", no_init)
            .def("loadMap", &CMapLoader::loadNewMapWithPlayer);

    class_<CPlugin, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CPlugin>>("CPluginBase", no_init);
    class_<CWrapper<CPlugin>, bases<CPlugin>, boost::noncopyable, std::shared_ptr<CWrapper<CPlugin>>>("CPlugin").
            def("load", &CWrapper<CPlugin>::load);

    class_<CMapPlugin, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMapPlugin>>("CMapPluginBase", no_init);
    class_<CWrapper<CMapPlugin>, bases<CMapPlugin>, boost::noncopyable, std::shared_ptr<CWrapper<CMapPlugin>>>(
            "CMapPlugin").
            def("load", &CWrapper<CMapPlugin>::load);

    class_<CEventLoop, boost::noncopyable, std::shared_ptr<CEventLoop>>("CEventLoop", no_init)
            .def("instance", &CEventLoop::instance)
            .def("run", &CEventLoop::run)
            .def("invoke", &CEventLoop::invoke);
}
